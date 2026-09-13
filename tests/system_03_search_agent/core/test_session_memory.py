"""Deterministic unit tests for `core.session_memory` (build phase 4.5 fixes).

WHY THIS FILE EXISTS. Until now `core/session_memory.py` had no unit test
file at all (F-4.5-J-07). Five hundred lines covering an authorization
check, a hard token cap, a compaction order, an idempotence guarantee and a
row-key mapping were guarded by exactly one premise-gate arm, and the two
criticals of the phase both lived in this module. Every test here is offline:
no live model, no live graph, no database, and nothing marked
`premise_gate`, because a security check that skips on a machine without a
tunnel is a security check that does not run.

WHAT EACH TEST PINS. Every test's docstring names the control in the real
source whose deletion turns that test red, and every one of them was run
with that control actually deleted and seen failing before being kept. A
test that cannot go red is worse than no test, because it reports coverage
that does not exist.

WHAT THIS FILE DELIBERATELY DOES NOT COVER, stated so a green run is not
read as more than it is (`.claude/rules/goal-contracts.md`):

- `_PostgresSessionMemoryStore`. Both of its methods are exercised only
  through the Protocol by hand-written doubles here. The `with_for_update`
  row lock, the JSONB round trip and the primary-key collision between two
  concurrent first turns need a real Postgres and are not asserted.
- The tokenizer's ACCURACY. These tests pin which branch of
  `count_tokens_for_tier` runs and that the fail-safe over-counts. They
  cannot check that any given model's count is right, because that is
  `litellm`'s answer and not this module's.
- Anything in `core/graph.py` or `core/run.py`, including whether the
  callers actually pass an owner identity. That is a call-site change owned
  by another agent and is a hand-off, not a fix, at the time this file was
  written.
"""

from __future__ import annotations

import asyncio
import inspect
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from system_03_search_agent.contracts.query import (
    MAX_CITATION_ID_LENGTH,
    MAX_CITATION_IDS_PER_FINDING,
    MAX_REPORTED_RECORD_IDS,
    SESSION_MEMORY_TOKEN_BUDGET,
    CompressedFinding,
    ResolvedEntity,
    SessionMemorySummary,
)
from system_03_search_agent.core import session_memory as sm

GUEST_A = "guest:11111111-1111-1111-1111-111111111111"
GUEST_B = "guest:22222222-2222-2222-2222-222222222222"
USER_A = "user:33333333-3333-3333-3333-333333333333"


def _now() -> datetime:
    return datetime(2026, 8, 20, 12, 0, 0, tzinfo=UTC)


def _summary(**overrides: Any) -> SessionMemorySummary:
    base: dict[str, Any] = {
        "session_id": "s-1",
        "resolved_entities": [
            ResolvedEntity(mention="BRCA1", curie="NCBIGene:672", entity_type="Gene")
        ],
        "last_updated": _now(),
    }
    base.update(overrides)
    return SessionMemorySummary(**base)


def _finding(claim: str, trace: str = "trace-1") -> CompressedFinding:
    return CompressedFinding(claim_summary=claim, trace_id=trace, citation_ids=["1"])


@pytest.fixture
def char_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Count one token per character, so budget arithmetic is exact.

    Used by every test whose subject is the compaction ORDER or the
    idempotence rule rather than the tokenizer itself. A real tokenizer would
    make those tests depend on a model id and a `litellm` version, which is
    how a deterministic assertion turns into a flaky one.
    """
    monkeypatch.setattr(sm, "count_tokens_for_tier", lambda text, *, tier: len(text))


# ---------------------------------------------------------------------------
# Store doubles.
# ---------------------------------------------------------------------------


class _KeyedStore:
    """A store that keys rows exactly as the shipped one does.

    Models the real separation: the row key is derived from the owner AND the
    session id, so two principals naming the same session id address two
    different rows.
    """

    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, dict[str, Any]] = {}

    async def get(
        self, session_id: str, *, owner_id: str
    ) -> tuple[str | None, dict[str, Any] | None] | None:
        key = sm.session_row_key(session_id, owner_id=owner_id)
        if key not in self.rows:
            return None
        return sm._unwrap(self.rows[key])

    async def update(
        self, session_id: str, *, owner_id: str, apply: sm.ApplyMemory
    ) -> None:
        key = sm.session_row_key(session_id, owner_id=owner_id)
        stored_owner, stored_payload = sm._unwrap(self.rows.get(key))
        new_payload = apply(stored_owner, stored_payload)
        if new_payload is None:
            return
        self.rows[key] = sm._wrap(owner_id, new_payload)


class _FlatStore:
    """A store that keys rows on the session id ALONE, ignoring the owner.

    Deliberately weaker than the shipped store, and that is the point. It is
    the shape a future store, a hand-written double, or build phase 4.6's
    history migration could take, and it is what proves the ownership
    comparison in `load_for_caller` and `_check_owner_before_write` is doing
    real work rather than being made redundant by the row key. A check that
    only holds because something else already made it unreachable is not a
    check.
    """

    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    def seed(self, session_id: str, owner_id: str, summary: SessionMemorySummary) -> None:
        self.rows[session_id] = sm._wrap(owner_id, summary.model_dump(mode="json"))

    async def get(
        self, session_id: str, *, owner_id: str
    ) -> tuple[str | None, dict[str, Any] | None] | None:
        del owner_id
        if session_id not in self.rows:
            return None
        return sm._unwrap(self.rows[session_id])

    async def update(
        self, session_id: str, *, owner_id: str, apply: sm.ApplyMemory
    ) -> None:
        stored_owner, stored_payload = sm._unwrap(self.rows.get(session_id))
        new_payload = apply(stored_owner, stored_payload)
        if new_payload is None:
            return
        self.rows[session_id] = sm._wrap(owner_id, new_payload)


# ---------------------------------------------------------------------------
# The critical: ownership. F-4.5-J-02, F-4.5-A-02, F-4.5-A-22.
# ---------------------------------------------------------------------------


class TestOwnership:
    """The defect: `(owner_id or None) != (user_id or None)`.

    Every guest carries `user_id = None` and every guest-owned row stored
    `user_id` NULL, so the comparison was `None != None`, which is False, and
    all guests were one principal. Any anonymous caller naming another
    guest's session id read and overwrote their conversation. This is the
    case premise-gate arm P11's five cases were arranged around and did not
    construct.
    """

    @pytest.mark.asyncio
    async def test_a_guest_cannot_read_another_guests_session(self) -> None:
        """Pins the `stored_owner != owner` raise in `load_for_caller`.

        Run against `_FlatStore`, which ignores the row key, so the ONLY
        thing that can refuse this read is the comparison itself.
        """
        store = _FlatStore()
        store.seed("shared", GUEST_A, _summary(session_id="shared"))

        mine = await sm.load_for_caller(
            session_id="shared", owner_id=GUEST_A, store=store
        )
        assert mine is not None and mine.resolved_entities[0].curie == "NCBIGene:672"

        with pytest.raises(sm.SessionOwnershipError) as caught:
            await sm.load_for_caller(
                session_id="shared", owner_id=GUEST_B, store=store
            )
        message = str(caught.value)
        assert GUEST_A not in message and GUEST_B not in message, (
            f"the refusal leaks a principal identifier: {message!r}"
        )
        assert "retry" in message.lower(), (
            "the refusal does not say what to do next, which the retry-safety "
            f"gate requires because the reader is an agent step: {message!r}"
        )

    @pytest.mark.asyncio
    async def test_a_guest_cannot_overwrite_another_guests_session(self) -> None:
        """Pins `_check_owner_before_write` on both write entry points.

        The write direction is the half that composes with the reference
        resolution defect: an attacker who can write another guest's memory
        plants a CURIE that the victim's next unresolvable question binds to.
        """
        store = _FlatStore()
        store.seed("shared", GUEST_A, _summary(session_id="shared"))

        with pytest.raises(sm.SessionOwnershipError):
            await sm.save_for_caller(
                _summary(
                    session_id="shared",
                    resolved_entities=[
                        ResolvedEntity(
                            mention="attacker", curie="NCBIGene:1", entity_type="Gene"
                        )
                    ],
                ),
                owner_id=GUEST_B,
                store=store,
            )

        with pytest.raises(sm.SessionOwnershipError):
            await sm.remember_turn_for_caller(
                session_id="shared",
                owner_id=GUEST_B,
                now=_now(),
                resolved=[
                    ResolvedEntity(
                        mention="attacker", curie="NCBIGene:1", entity_type="Gene"
                    )
                ],
                findings=[],
                store=store,
            )

        surviving = await sm.load_for_caller(
            session_id="shared", owner_id=GUEST_A, store=store
        )
        assert surviving is not None
        assert [e.curie for e in surviving.resolved_entities] == ["NCBIGene:672"]

    @pytest.mark.asyncio
    async def test_two_guests_naming_one_session_id_address_different_rows(
        self,
    ) -> None:
        """Pins the owner in `session_row_key`.

        The second, structural half of the fix. Even with the comparison
        deleted, guest B must not be able to ADDRESS guest A's row, because
        `--session-id` is a documented CLI flag, MCP accepts any string, and
        GraphQL documents "No minimum", so two scripted callers both sending
        `shared` is the ordinary case rather than an attack.
        """
        store = _KeyedStore()
        await sm.save_for_caller(
            _summary(session_id="shared"), owner_id=GUEST_A, store=store
        )
        assert len(store.rows) == 1

        assert (
            await sm.load_for_caller(
                session_id="shared", owner_id=GUEST_B, store=store
            )
            is None
        )
        await sm.save_for_caller(
            _summary(
                session_id="shared",
                resolved_entities=[
                    ResolvedEntity(
                        mention="TP53", curie="NCBIGene:7157", entity_type="Gene"
                    )
                ],
            ),
            owner_id=GUEST_B,
            store=store,
        )
        assert len(store.rows) == 2, (
            "guest B's write landed on guest A's row: the row key is not "
            "owner-scoped"
        )
        a_side = await sm.load_for_caller(
            session_id="shared", owner_id=GUEST_A, store=store
        )
        assert a_side is not None
        assert [e.curie for e in a_side.resolved_entities] == ["NCBIGene:672"]

    @pytest.mark.asyncio
    async def test_an_account_and_a_guest_are_still_separate(self) -> None:
        """The property P11 did assert, kept so the fix does not lose it."""
        store = _FlatStore()
        store.seed("s-1", USER_A, _summary())
        with pytest.raises(sm.SessionOwnershipError):
            await sm.load_for_caller(session_id="s-1", owner_id=GUEST_A, store=store)

        store.seed("s-2", GUEST_A, _summary(session_id="s-2"))
        with pytest.raises(sm.SessionOwnershipError):
            await sm.load_for_caller(session_id="s-2", owner_id=USER_A, store=store)

    @pytest.mark.asyncio
    async def test_an_unknown_session_is_not_a_refusal(self) -> None:
        """No existence oracle: unknown and not-yours look the same outside.

        Pins the `if record is None: return None` branch. Distinguishing the
        two would turn this into a probe for which session ids are live.
        """
        store = _KeyedStore()
        assert (
            await sm.load_for_caller(
                session_id="never-used", owner_id=GUEST_A, store=store
            )
            is None
        )

    @pytest.mark.parametrize("identity", [None, "", "   ", "  guest:x  ", 7])
    @pytest.mark.asyncio
    async def test_a_missing_or_blank_identity_is_a_loud_failure(
        self, identity: Any
    ) -> None:
        """Pins `_require_owner_id` on the read path.

        F-4.5-A-22: `("" or None)` is None, so an empty-string identity
        collapsed into the anonymous bucket and read an anonymous row. The
        truthiness coercion was doing security work. Nothing here may
        silently become "anonymous": a caller that cannot name itself gets an
        exception.
        """
        with pytest.raises(sm.CallerIdentityRequired):
            await sm.load_for_caller(
                session_id="s-1", owner_id=identity, store=_KeyedStore()
            )

    @pytest.mark.parametrize("identity", [None, ""])
    @pytest.mark.asyncio
    async def test_a_missing_identity_is_a_loud_failure_on_the_write_paths(
        self, identity: Any
    ) -> None:
        """Same control, both write entry points.

        Read and write are separate code paths and only one of them was ever
        the finding, which is why the check is asserted on each rather than
        once.
        """
        store = _KeyedStore()
        with pytest.raises(sm.CallerIdentityRequired):
            await sm.save_for_caller(_summary(), owner_id=identity, store=store)
        with pytest.raises(sm.CallerIdentityRequired):
            await sm.remember_turn_for_caller(
                session_id="s-1",
                owner_id=identity,
                now=_now(),
                resolved=[],
                findings=[],
                store=store,
            )
        assert store.rows == {}

    @pytest.mark.asyncio
    async def test_the_old_user_id_call_shape_cannot_silently_reach_the_module(
        self,
    ) -> None:
        """The pre-fix call must break loudly, not default to anonymous.

        Pins the parameter NAME. `user_id` is the value that made every guest
        one principal, so a call site that still passes it has to fail at the
        call rather than type-check its way back into the insecure
        behaviour. This is what makes the pending call-site change visible
        instead of optional.
        """
        with pytest.raises(TypeError):
            await sm.load_for_caller(session_id="s-1", user_id=None)  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            await sm.save_for_caller(_summary(), user_id=None)  # type: ignore[call-arg]

    @pytest.mark.asyncio
    async def test_memory_written_before_the_owner_envelope_is_never_served(
        self,
    ) -> None:
        """Pins `_unwrap`'s version check.

        A row written by the pre-fix code holds a bare summary with no
        recorded owner. There is no principal it can honestly be handed to,
        so it is retired rather than given to the first caller who asks, and
        the row may then be claimed by a write because its contents were
        never readable in the first place.
        """
        store = _FlatStore()
        store.rows["legacy"] = _summary(session_id="legacy").model_dump(mode="json")

        assert (
            await sm.load_for_caller(
                session_id="legacy", owner_id=GUEST_A, store=store
            )
            is None
        )
        await sm.save_for_caller(
            _summary(session_id="legacy"), owner_id=GUEST_A, store=store
        )
        claimed = await sm.load_for_caller(
            session_id="legacy", owner_id=GUEST_A, store=store
        )
        assert claimed is not None


class TestOwnershipCheckPlacement:
    """F-4.5-J-16: the check ran between two awaits, not inside one."""

    @pytest.mark.asyncio
    async def test_the_write_check_sees_the_owner_the_write_lands_against(
        self,
    ) -> None:
        """Pins that ownership is checked INSIDE the store's locked update.

        The double answers `get` with a friendly owner and `update` with the
        real one, which is the observable shape of an owner that changes
        between the two awaits. A pre-read check passes and writes onto
        someone else's row; a check inside `apply` refuses. Build phase 4.6's
        history migration is exactly this owner change, so it is a scheduled
        race rather than a hypothetical one.
        """

        class _ShiftingStore:
            def __init__(self) -> None:
                self.written = False

            async def get(
                self, session_id: str, *, owner_id: str
            ) -> tuple[str | None, dict[str, Any] | None] | None:
                del session_id
                return (owner_id, None)

            async def update(
                self, session_id: str, *, owner_id: str, apply: sm.ApplyMemory
            ) -> None:
                del session_id, owner_id
                payload = apply(GUEST_B, None)
                if payload is not None:
                    self.written = True

        store = _ShiftingStore()
        with pytest.raises(sm.SessionOwnershipError):
            await sm.save_for_caller(_summary(), owner_id=GUEST_A, store=store)
        assert store.written is False


class TestConcurrentTurns:
    """F-4.5-A-15: load, merge and save were three separate operations."""

    @pytest.mark.asyncio
    async def test_two_concurrent_turns_do_not_lose_each_others_findings(
        self, char_counter: None
    ) -> None:
        """Pins that the merge happens inside the store's `apply` callback.

        The double yields control between reading the payload and writing it,
        which is the interleaving a real lock-free read-modify-write suffers.
        If the merge is computed from a payload read before the update, the
        second write discards the first turn and the loss is silent: it looks
        identical to the feature simply not remembering.
        """

        class _InterleavingStore:
            def __init__(self) -> None:
                self.payload: dict[str, Any] | None = None
                self.owner: str | None = None
                self.lock = asyncio.Lock()

            async def get(
                self, session_id: str, *, owner_id: str
            ) -> tuple[str | None, dict[str, Any] | None] | None:
                del session_id, owner_id
                if self.payload is None:
                    return None
                return (self.owner, self.payload)

            async def update(
                self, session_id: str, *, owner_id: str, apply: sm.ApplyMemory
            ) -> None:
                del session_id
                async with self.lock:
                    new_payload = apply(self.owner, self.payload)
                    await asyncio.sleep(0)
                    if new_payload is not None:
                        self.owner = owner_id
                        self.payload = new_payload

        store = _InterleavingStore()

        async def turn(trace: str, curie: str) -> None:
            await sm.remember_turn_for_caller(
                session_id="s-1",
                owner_id=GUEST_A,
                now=_now(),
                resolved=[
                    ResolvedEntity(mention=curie, curie=curie, entity_type="Gene")
                ],
                findings=[_finding(f"claim from {trace}", trace)],
                store=store,
            )

        await asyncio.gather(
            turn("trace-1", "NCBIGene:672"), turn("trace-2", "NCBIGene:7157")
        )

        final = await sm.load_for_caller(
            session_id="s-1", owner_id=GUEST_A, store=store
        )
        assert final is not None
        assert {e.curie for e in final.resolved_entities} == {
            "NCBIGene:672",
            "NCBIGene:7157",
        }
        assert {f.trace_id for f in final.compressed_findings} == {
            "trace-1",
            "trace-2",
        }


# ---------------------------------------------------------------------------
# F-4.5-J-20: idempotence.
# ---------------------------------------------------------------------------


class TestMergeTurnIdempotence:
    """The dedup key was `(trace_id, claim_summary)` and compaction rewrites
    `claim_summary`, so replaying a turn re-appended both originals and the
    content duplicated in place on every replay."""

    def test_replaying_a_turn_after_compaction_changes_nothing(
        self, char_counter: None
    ) -> None:
        """Pins the trace-level dedup in `merge_turn`.

        The budget is set low enough that the findings merge fires, which is
        the precondition the shipped key could not survive. Three folds,
        because the first replay is what breaks and the second is what shows
        it growing rather than settling.
        """
        turn = [
            _finding("alpha claim text " * 4, "trace-1"),
            _finding("beta claim text " * 4, "trace-1"),
        ]
        first = sm.merge_turn(
            _summary(token_budget=200),
            session_id="s-1",
            now=_now(),
            resolved=[],
            findings=turn,
        )
        assert len(first.compressed_findings) == 1, (
            "the budget did not force a merge, so this test is not exercising "
            "the case it exists for"
        )

        replay_one = sm.merge_turn(
            first, session_id="s-1", now=_now(), resolved=[], findings=turn
        )
        replay_two = sm.merge_turn(
            replay_one, session_id="s-1", now=_now(), resolved=[], findings=turn
        )
        assert [f.claim_summary for f in replay_one.compressed_findings] == [
            f.claim_summary for f in first.compressed_findings
        ]
        assert [f.claim_summary for f in replay_two.compressed_findings] == [
            f.claim_summary for f in first.compressed_findings
        ]

    def test_a_new_turn_is_still_recorded(self, char_counter: None) -> None:
        """The negative control for the test above.

        A dedup rule that skipped everything would pass an idempotence test
        perfectly and record nothing, which is the failure mode a fix for an
        over-appending bug is most likely to introduce.
        """
        first = sm.merge_turn(
            None,
            session_id="s-1",
            now=_now(),
            resolved=[],
            findings=[_finding("first turn claim", "trace-1")],
        )
        second = sm.merge_turn(
            first,
            session_id="s-1",
            now=_now(),
            resolved=[],
            findings=[_finding("second turn claim", "trace-2")],
        )
        assert {f.trace_id for f in second.compressed_findings} == {
            "trace-1",
            "trace-2",
        }

    def test_entities_dedup_on_the_curie(self, char_counter: None) -> None:
        """The entity half of the natural key, unchanged and still asserted."""
        entity = ResolvedEntity(
            mention="BRCA1", curie="NCBIGene:672", entity_type="Gene"
        )
        once = sm.merge_turn(
            None, session_id="s-1", now=_now(), resolved=[entity], findings=[]
        )
        twice = sm.merge_turn(
            once, session_id="s-1", now=_now(), resolved=[entity], findings=[]
        )
        assert len(twice.resolved_entities) == 1


# ---------------------------------------------------------------------------
# F-4.5-J-22 and F-4.5-A-07: the tokenizer.
# ---------------------------------------------------------------------------


class TestTokenCounting:
    """`litellm.token_counter` does not raise for a model it cannot map: it
    falls back to a default encoder and returns a number, so the documented
    fail-safe branch was unreachable and the `tier` argument selected a model
    id the counting call then ignored."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> None:
        sm._tokenizer_is_model_specific.cache_clear()
        yield
        sm._tokenizer_is_model_specific.cache_clear()

    def test_a_default_encoder_count_is_floored_by_the_safe_estimate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pins the `max(counted, _char_estimate(text))` branch.

        The stub returns the same count for every model, which is exactly
        what the shipped `litellm` was measured doing: an identical number for
        the configured plan model, for two unrelated vendors, for a
        fabricated model name and for the empty string. A number that does not
        vary with the model carries no information about the model's
        vocabulary, so the cap must not be set by it alone.
        """
        monkeypatch.setattr(sm, "_litellm_token_count", lambda model, text: 1)
        text = "x" * 300
        assert sm._tokenizer_is_model_specific("any-model") is False
        assert sm.count_tokens_for_tier(text, tier="plan") == 100

    def test_a_model_specific_count_is_used_as_is(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The other side of the same branch.

        Without this, a fix that always over-counted would pass the test
        above and would have quietly turned the whole cap into a character
        count, which is the thing Section 14.4 forbids. The count is
        deliberately set BELOW the character estimate for the same text, so
        an implementation that took the larger of the two unconditionally
        would be caught here rather than silently accepted.
        """

        def counter(model: str, text: str) -> int:
            return 7 if model == sm._UNMAPPED_MODEL_PROBE else 42

        monkeypatch.setattr(sm, "_litellm_token_count", counter)
        assert sm._tokenizer_is_model_specific("real-model") is True
        assert sm._char_estimate("x" * 300) == 100
        assert sm.count_tokens_for_tier("x" * 300, tier="plan") == 42

    def test_no_count_at_all_falls_back_to_the_safe_estimate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pins the `if counted is None` branch, which used to be dead code.

        It was unreachable because `litellm.token_counter` never raised. It
        is reachable now because `_litellm_token_count` reports the absence of
        a count as None instead of swallowing it into a guess, and this
        branch is what turns that None into a number rather than into a
        TypeError one layer down.
        """
        monkeypatch.setattr(sm, "_litellm_token_count", lambda model, text: None)
        assert sm.count_tokens_for_tier("x" * 301, tier="plan") == 101

    def test_the_estimate_over_counts_rather_than_under_counts(self) -> None:
        """Failing safe here means failing small.

        English prose averages roughly four characters per token, so dividing
        by three is deliberately high. An under-count silently defeats the cap
        the estimate exists to serve; an over-count costs a shorter block.
        """
        assert sm._SAFE_CHARS_PER_TOKEN < 4
        assert sm._char_estimate("x" * 12) == 4

    def test_the_worst_case_count_covers_every_injection_tier(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pins `count_tokens_worst_case` taking the max, not the plan tier.

        A stored summary has no receiving tier: Think reads it at the guard
        tier and Plan at the plan tier. Counting against one and injecting
        into the other is the shape of F-4.5-J-22.
        """
        monkeypatch.setattr(
            sm,
            "count_tokens_for_tier",
            lambda text, *, tier: {"guard": 900, "plan": 100}[tier],
        )
        assert sm._INJECTION_TIERS == ("guard", "plan")
        assert sm.count_tokens_worst_case("anything") == 900

    def test_compaction_decisions_use_the_receiving_tier(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pins `compact(summary, tier=tier)` in `build_session_context`.

        The shipped `compact` hardcoded `tier = "plan"` for every `fits()`
        decision and `build_session_context` then re-measured against the
        caller's tier, so for Think the choices about which threads to drop
        and which findings to merge were computed for a model that was never
        going to read them. Here the guard tier counts ten times higher than
        the plan tier, so a summary that fits at the plan tier must still be
        compacted for the guard tier.
        """
        monkeypatch.setattr(
            sm,
            "count_tokens_for_tier",
            lambda text, *, tier: len(text) * (10 if tier == "guard" else 1),
        )
        summary = _summary(
            token_budget=400,
            compressed_findings=[
                _finding("alpha " * 6, "trace-1"),
                _finding("beta " * 6, "trace-2"),
                _finding("gamma " * 6, "trace-3"),
            ],
        )
        assert len(sm.compact(summary, tier="plan").compressed_findings) == 3
        assert len(sm.compact(summary, tier="guard").compressed_findings) < 3


# ---------------------------------------------------------------------------
# F-4.5-A-24: the budget is not the caller's to raise.
# ---------------------------------------------------------------------------


class TestTokenBudgetIsHard:
    def test_the_contract_refuses_a_budget_above_the_section_cap(self) -> None:
        """Pins `le=SESSION_MEMORY_TOKEN_BUDGET` on the field.

        The ceiling used to be 8000, which is not a bound on a 1500-token
        cap.
        """
        _summary(token_budget=SESSION_MEMORY_TOKEN_BUDGET)
        with pytest.raises(ValidationError):
            _summary(token_budget=SESSION_MEMORY_TOKEN_BUDGET + 1)
        with pytest.raises(ValidationError):
            _summary(token_budget=0)

    def test_enforcement_clamps_a_budget_the_contract_never_saw(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pins `_effective_budget`, the second layer.

        A stored row written by an older version never passes through the
        field validator on its way out, and `model_construct` skips it too.
        The clamp at the point of use is what makes the cap hold for a
        summary the contract never got to check, which is what "enforced
        server-side, never a client-supplied number" has to mean.
        """
        monkeypatch.setattr(sm, "count_tokens_for_tier", lambda text, *, tier: len(text))
        smuggled = SessionMemorySummary.model_construct(
            session_id="s-1",
            resolved_entities=[
                ResolvedEntity(
                    mention="e" * 100, curie=f"NCBIGene:{i}", entity_type="Gene"
                )
                for i in range(40)
            ],
            compressed_findings=[],
            open_threads=[],
            token_budget=8000,
            last_updated=_now(),
        )
        block = sm.build_session_context(smuggled, tier="plan")
        assert len(block) <= SESSION_MEMORY_TOKEN_BUDGET

    @pytest.mark.asyncio
    async def test_a_stored_budget_above_the_cap_is_clamped_on_read(self) -> None:
        """Pins `_clamp_stored_budget`.

        A stored preference is untrusted input on the way back OUT, the same
        posture `auth/preferences.py` takes for the depth key. Clamped rather
        than rejected, so a pre-existing row degrades to the correct budget
        instead of failing validation and losing the conversation.
        """
        store = _FlatStore()
        payload = _summary().model_dump(mode="json")
        payload["token_budget"] = 8000
        store.rows["s-1"] = sm._wrap(GUEST_A, payload)

        loaded = await sm.load_for_caller(
            session_id="s-1", owner_id=GUEST_A, store=store
        )
        assert loaded is not None
        assert loaded.token_budget == SESSION_MEMORY_TOKEN_BUDGET


# ---------------------------------------------------------------------------
# F-4.5-A-14: the row-key mapping.
# ---------------------------------------------------------------------------


class TestSessionRowKey:
    def test_eight_distinct_caller_strings_map_to_eight_distinct_rows(self) -> None:
        """Pins hashing the exact bytes instead of parsing a UUID first.

        `uuid.UUID` strips `urn:`, `uuid:`, braces and every hyphen anywhere
        in its input before parsing, so all of these landed on one row. Build
        phase 4.6 reuses this mapping for `interactions.session_id`, which is
        why the equivalence classes had to be closed before they propagate.
        """
        forms = [
            "550e8400-e29b-41d4-a716-446655440000",
            "550E8400-E29B-41D4-A716-446655440000",
            "550e8400e29b41d4a716446655440000",
            "{550e8400-e29b-41d4-a716-446655440000}",
            "urn:uuid:550e8400-e29b-41d4-a716-446655440000",
            "5-5-0-e-8-4-0-0-e29b41d4a716446655440000",
            "uuid:550e8400-e29b-41d4-a716-446655440000",
            "urn:550e8400-e29b-41d4-a716-446655440000",
        ]
        keys = {sm.session_row_key(f, owner_id=GUEST_A) for f in forms}
        assert len(keys) == len(forms)

    def test_the_empty_session_id_is_not_a_well_known_row(self) -> None:
        """The empty string used to map to one fixed, derivable UUID."""
        assert sm.session_row_key("", owner_id=GUEST_A) != sm.session_row_key(
            "", owner_id=GUEST_B
        )

    def test_the_key_is_stable_across_calls(self) -> None:
        """The property that makes it safe to derive rather than store.

        A key that changed per call would create a new row per turn and lose
        the conversation, which is the failure the uuid5 mapping replaced.
        """
        assert sm.session_row_key("s-1", owner_id=GUEST_A) == sm.session_row_key(
            "s-1", owner_id=GUEST_A
        )

    def test_the_key_requires_an_identity(self) -> None:
        with pytest.raises(sm.CallerIdentityRequired):
            sm.session_row_key("s-1", owner_id="")


# ---------------------------------------------------------------------------
# Bounds, compaction order, and the field with no producer.
# ---------------------------------------------------------------------------


class TestBounds:
    def test_one_citation_id_cannot_be_unbounded(self) -> None:
        """F-4.5-J-19. Pins the per-item validator on `citation_ids`.

        `max_length` on a `list[str]` bounds the number of items, never the
        length of each, and a `SessionMemorySummary` therefore had no upper
        bound on serialized size at all: 20 findings times 5 unbounded
        strings into a JSONB column.
        """
        CompressedFinding(
            claim_summary="c", trace_id="t", citation_ids=["x" * MAX_CITATION_ID_LENGTH]
        )
        with pytest.raises(ValidationError):
            CompressedFinding(
                claim_summary="c",
                trace_id="t",
                citation_ids=["x" * (MAX_CITATION_ID_LENGTH + 1)],
            )

    def test_merging_two_findings_keeps_the_citation_id_cap(
        self, char_counter: None
    ) -> None:
        """F-4.5-A-26. Pins the slice in `_merge_two_findings` being a real
        bound rather than a decorative one.

        Two findings at the five-id ceiling produce ten ids, and the merged
        entry must still carry five. Without the slice the model rejects the
        merge outright, which turns a compaction into a crash.
        """
        ids = [str(i) for i in range(MAX_CITATION_IDS_PER_FINDING)]
        merged = sm._merge_two_findings(
            CompressedFinding(claim_summary="a", trace_id="t1", citation_ids=ids),
            CompressedFinding(claim_summary="b", trace_id="t2", citation_ids=ids),
        )
        assert len(merged.citation_ids) == MAX_CITATION_IDS_PER_FINDING
        assert merged.trace_id == "t1"

    def test_a_merged_claim_that_hits_the_ceiling_says_so(self) -> None:
        """A raw 280-character slice can cut a claim mid-word and read as a
        complete one. The marker is the same disclose-rather-than-truncate
        discipline the entity list already had."""
        merged = sm._merge_two_findings(
            _finding("a" * 200, "t1"), _finding("b" * 200, "t2")
        )
        assert merged.claim_summary.endswith(sm._TRUNCATION_MARKER)
        assert len(merged.claim_summary) <= 280

    def test_the_block_never_exceeds_the_budget(self, char_counter: None) -> None:
        """The cap's directional guarantee, on an input nothing can fit."""
        summary = _summary(
            token_budget=20,
            resolved_entities=[
                ResolvedEntity(
                    mention="m" * 100, curie=f"NCBIGene:{i}", entity_type="Gene"
                )
                for i in range(50)
            ],
        )
        block = sm.build_session_context(summary, tier="plan")
        assert len(block) <= 20


class TestCompactionOrder:
    def test_threads_go_before_findings(self, char_counter: None) -> None:
        """Section 14.3's order, asserted on a summary that cannot fit both.

        Pins the two loops in `compact` being in this sequence. Note what
        this test has to construct to run at all: the threads. Nothing in
        `src/` writes `open_threads`, so this arm is testing a specified
        branch that real data never reaches.
        """
        summary = _summary(
            token_budget=300,
            open_threads=["t" * 100, "u" * 100],
            compressed_findings=[
                _finding("alpha " * 15, "trace-1"),
                _finding("beta " * 15, "trace-2"),
            ],
        )
        compacted = sm.compact(summary, tier="plan")
        assert compacted.open_threads == []
        assert len(compacted.compressed_findings) >= 1

    def test_entities_are_never_dropped_from_the_summary_for_budget(
        self, char_counter: None
    ) -> None:
        """Section 14.3's rule 3. `compact` shrinks the stored summary; only
        the RENDERED block leaves entities out, and it discloses when it
        does."""
        entities = [
            ResolvedEntity(mention="m" * 50, curie=f"NCBIGene:{i}", entity_type="Gene")
            for i in range(30)
        ]
        compacted = sm.compact(_summary(token_budget=50, resolved_entities=entities))
        assert len(compacted.resolved_entities) == 30

    def test_a_shortened_entity_list_is_disclosed(self, char_counter: None) -> None:
        entities = [
            ResolvedEntity(mention="m", curie=f"NCBIGene:{i}", entity_type="Gene")
            for i in range(30)
        ]
        block = sm.build_session_context(
            _summary(token_budget=200, resolved_entities=entities), tier="plan"
        )
        assert "omitted for budget" in block


class TestOpenThreadsHaveNoProducer:
    """RENAMED IN SPIRIT, kept in place: open_threads HAS a producer now.

    This class used to pin the ABSENCE of one. That was correct and
    deliberate: build phase 4.5 scoped a producer out under
    `.claude/rules/v1-scope-boundary.md`, and the arm existed so that
    whoever added one would have to come here, see it, and update the
    module docstring in the same change. It worked exactly as designed,
    which is why this comment exists rather than a quiet deletion.

    Build phase 6.2's T-6.2-07 added the producer on a product-owner
    decision, so the arm below now pins the OPPOSITE contract. The
    docstring assertion is kept and inverted rather than dropped, because
    the thing worth protecting was never "there is no producer": it was
    that the code and the docstring agree about whether there is one.
    """

    def test_merge_turn_records_the_question_as_an_open_thread(
        self, char_counter: None
    ) -> None:
        """The producer exists, and the docstring says so.

        A follow-up resolves a pronoun only if the earlier QUESTION reached
        Think. Memory already carried the entities a turn resolved and the
        facts it established; the sentence the user typed was the missing
        piece.
        """
        assert "question" in inspect.signature(sm.merge_turn).parameters
        assert "no producer" not in sm.__doc__, (
            "the docstring still claims open_threads has no producer while "
            "merge_turn takes a question: the two must not disagree"
        )
        assert "HAS A PRODUCER" in sm.__doc__

        folded = sm.merge_turn(
            None,
            session_id="s-1",
            now=_now(),
            resolved=[],
            findings=[],
            question="Which diseases are associated with BRCA1?",
        )
        assert folded.open_threads == ["Which diseases are associated with BRCA1?"]

    def test_the_thread_accumulates_in_order_and_is_bounded(
        self, char_counter: None
    ) -> None:
        """The whole thread, oldest first, up to the cap already declared.

        Order is load-bearing beyond readability: `compact` drops the OLDEST
        threads first when the token budget bites, so a list in the wrong
        order would discard the most recent turn, which is the one a pronoun
        most likely points at.
        """
        summary = None
        for index in range(1, 15):
            summary = sm.merge_turn(
                summary,
                session_id="s-1",
                now=_now(),
                resolved=[],
                findings=[],
                question=f"question {index}",
            )

        assert summary is not None
        assert len(summary.open_threads) <= 10, (
            f"the thread must stay inside MAX_OPEN_THREADS, got "
            f"{len(summary.open_threads)}"
        )
        assert summary.open_threads[-1] == "question 14", (
            "the newest turn must survive: it is the one a pronoun points at"
        )
        assert "question 1" not in summary.open_threads, (
            "the OLDEST turns are the ones that fall off, not the newest"
        )

    def test_an_immediate_repeat_does_not_duplicate(self, char_counter: None) -> None:
        """Asking the same thing twice in a row adds nothing to the thread.

        Deliberately only an IMMEDIATE repeat. Asking a question again after
        three other turns is a real return to a topic, and the thread should
        show that it happened rather than silently collapsing it.
        """
        first = sm.merge_turn(
            None, session_id="s", now=_now(), resolved=[], findings=[], question="same"
        )
        second = sm.merge_turn(
            first, session_id="s", now=_now(), resolved=[], findings=[], question="same"
        )
        assert second.open_threads == ["same"]

        third = sm.merge_turn(
            second, session_id="s", now=_now(), resolved=[], findings=[], question="other"
        )
        fourth = sm.merge_turn(
            third, session_id="s", now=_now(), resolved=[], findings=[], question="same"
        )
        assert fourth.open_threads == ["same", "other", "same"], (
            "a return to an earlier topic is a real event and must be visible"
        )

    def test_a_turn_with_no_question_adds_nothing(self, char_counter: None) -> None:
        """The default is empty, so an existing caller that does not pass a
        question is unchanged rather than writing a blank thread."""
        folded = sm.merge_turn(
            _summary(open_threads=["existing"]),
            session_id="s-1",
            now=_now(),
            resolved=[],
            findings=[],
        )
        assert folded.open_threads == ["existing"]

    def test_merge_turn_carries_an_existing_thread_list_forward(
        self, char_counter: None
    ) -> None:
        """It does not invent threads, and it does not silently discard one a
        caller managed to put there."""
        base = _summary(open_threads=["compare to BRCA2 not yet run"])
        folded = sm.merge_turn(
            base,
            session_id="s-1",
            now=_now(),
            resolved=[],
            findings=[_finding("new claim", "trace-9")],
        )
        assert folded.open_threads == ["compare to BRCA2 not yet run"]


class TestInjectionSurface:
    def test_memory_is_declared_for_think_and_plan_only(self) -> None:
        """Unchanged by this fix branch and re-asserted so it stays that way.

        This arm asserts the DECLARATION, not the behaviour: `injected_steps`
        returns a module constant and no production code consults it to
        decide whether to inject. That gap is F-4.5-J-04 and it belongs to
        `core/graph.py`, which this file does not own.
        """
        # "guardrail" joined the declaration for a few hours on 2026-09-13
        # (UI fix set 7, item 7.1) and left it the same day: the guard
        # prompt carries no memory block. The two steps that may never read
        # memory are the ones asserted absent below.
        assert sm.injected_steps(_summary()) == ("think", "plan")
        assert "act" not in sm.injected_steps(_summary())
        assert "write" not in sm.injected_steps(_summary())


class TestReportedRecords:
    """UI fix set 7, item 7.2 (2026-09-13): memory records which records an
    answer showed, so a go-deeper turn can show the others first."""

    _URL = "https://www.ncbi.nlm.nih.gov/clinvar/variation/{}/"

    def test_merge_turn_records_what_the_answer_showed(self, char_counter: None) -> None:
        """MUTATION PROOF: dropping `reported_record_ids=reported[...]` from
        the `SessionMemorySummary(...)` `merge_turn` builds turns this red."""
        written = sm.merge_turn(
            None,
            session_id="s-1",
            now=_now(),
            resolved=[ResolvedEntity(mention="BRCA1", curie="NCBIGene:672", entity_type="Gene")],
            findings=[],
            reported_record_ids=[self._URL.format(1), self._URL.format(2)],
        )
        assert written.reported_record_ids == [self._URL.format(1), self._URL.format(2)]

    def test_reported_records_accumulate_without_duplicates(self, char_counter: None) -> None:
        first = sm.merge_turn(
            None, session_id="s-1", now=_now(), resolved=[], findings=[],
            reported_record_ids=[self._URL.format(1), self._URL.format(2)],
        )
        second = sm.merge_turn(
            first, session_id="s-1", now=_now(), resolved=[], findings=[],
            reported_record_ids=[self._URL.format(2), self._URL.format(3), ""],
        )
        assert second.reported_record_ids == [self._URL.format(i) for i in (1, 2, 3)]

    def test_reported_records_are_fifo_capped(self, char_counter: None) -> None:
        base = _summary(reported_record_ids=[self._URL.format(i) for i in range(100)])
        written = sm.merge_turn(
            base, session_id="s-1", now=_now(), resolved=[], findings=[],
            reported_record_ids=[self._URL.format(100)],
        )
        assert len(written.reported_record_ids) == MAX_REPORTED_RECORD_IDS
        assert written.reported_record_ids[-1] == self._URL.format(100)
        assert self._URL.format(0) not in written.reported_record_ids

    def test_reported_records_never_reach_the_rendered_block(self, char_counter: None) -> None:
        """Orchestration data only: it costs nothing against the token budget
        and can never be read by a model."""
        summary = _summary(reported_record_ids=[self._URL.format(7)])
        block = sm.build_session_context(summary, tier="plan")
        assert block, "the block must still render the entity"
        assert self._URL.format(7) not in block
        assert "clinvar" not in block
