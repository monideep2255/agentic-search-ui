"""The persona draw, the persona identity every surface reports, and the
server-side audience-depth default: the fix round for build phase 4.5's
judge and adversary findings F-4.5-J-10, F-4.5-J-12, F-4.5-J-15,
F-4.5-A-11, F-4.5-A-12, F-4.5-A-13 and F-4.5-A-20.

WHAT THIS FILE EXERCISES, and what it deliberately does not. Stated here
rather than left to be re-derived, per `.claude/rules/goal-contracts.md`:
"a verify surface must state its own coverage", and per F-4.5-J-07, whose
finding was that a phase's controls were correct in the code and unguarded
by anything that runs.

Exercised:

    The draw's stability when the curated list GROWS (F-4.5-J-10). The
    baseline half of that arm runs against the SHIPPED data file through
    the real loader, with nothing patched, so it is the production path.
    The extended half writes a second file and points the loader at it,
    which is the only way to vary a list this repository ships as a
    constant.

    The draw's indifference to the ORDER of the file, which is the second
    thing a modulus over the list length gets wrong.

    Which identity the draw keys on: the account when there is one, the
    session otherwise.

    That `GET /v1/persona` reports the SAME name as `POST /v1/query` for
    one signed-in caller (F-4.5-J-12), and that it still answers an
    anonymous or bad-credential caller rather than refusing.

    That `POST /auth/guest` keys its `persona_name` on the session id the
    caller supplies, so it matches that guest's first answer (F-4.5-A-12).

    That the audience depth a run uses is resolved by the SERVER from the
    account row when the caller names none (F-4.5-J-15, F-4.5-A-13), that
    an explicitly named depth still wins, and that a REFUSED run does not
    record a preference (F-4.5-A-20).

    That the CLI neutralizes control bytes in the server-supplied persona
    name before writing it to a terminal (F-4.5-A-11).

NOT exercised, and named so the gap is arguable rather than invisible:

    Nothing here runs a model or reaches the graph. Every arm is a pure
    function or a FastAPI handler driven with its own dependencies
    overridden, so the whole file runs offline in under a second and none
    of it is behind a live-environment skip.

    The database is not reached either. `get_session` is overridden with a
    stub in every endpoint arm, so these arms prove what the HANDLER does
    with a row, never that the row round-trips through PostgreSQL. The
    JSONB write itself is covered by the existing preferences tests.

    Section 14.5's "before auth, it defaults per session" is NOT covered,
    because it is not implemented. There is no per-session depth store.
    That is carried as an open finding, not as a tested property.

    The GraphQL surface's own depth default is not covered here. It still
    hardcodes `"researcher"` in `adapters/graphql/schema.py`, a file this
    fix round did not own, so F-4.5-J-15 remains open for that surface.

    The persona is not asserted to be STORED. It is recomputed per request
    from a stable function. T-4.5-09's "drawn once at first login and
    stored on the users row" needs a migration this fix round did not own.
"""

from __future__ import annotations

import io
import json
import random
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from system_03_search_agent.core import persona as persona_module
from system_03_search_agent.core.persona import load_persona_list, persona_for_session

# ---------------------------------------------------------------------------
# Helpers for varying the curated list.
#
# The list is loaded once per process behind an `lru_cache`, which is the
# property `prompt-cache-discipline` requires and which makes it awkward to
# vary in a test. Varying it by pointing `_PERSONA_FILE` at a temporary file
# and clearing the cache keeps the REAL loader in the path, including its
# duplicate-name and year-of-death validation, rather than substituting a
# fake list for the thing that produces one.
# ---------------------------------------------------------------------------

_SHIPPED_FILE = Path(persona_module.__file__).resolve().parent.parent / "data" / "personas_v1.json"


def _shipped_entries() -> list[dict[str, Any]]:
    return list(json.loads(_SHIPPED_FILE.read_text(encoding="utf-8"))["personas"])


def _write_list(tmp_path: Path, entries: list[dict[str, Any]], name: str) -> Path:
    target = tmp_path / name
    target.write_text(json.dumps({"version": 1, "basis": "test", "personas": entries}))
    return target


def _draw_against(path: Path | None, identities: list[str], monkeypatch: Any) -> dict[str, str]:
    """Draw for every identity against `path`, or the shipped file if None."""
    load_persona_list.cache_clear()
    try:
        if path is not None:
            monkeypatch.setattr(persona_module, "_PERSONA_FILE", path)
        return {i: persona_for_session(session_id=i, user_id=None) for i in identities}
    finally:
        monkeypatch.undo()
        load_persona_list.cache_clear()


_IDENTITIES = [f"identity-{n}" for n in range(600)]


class TestTheDrawSurvivesTheListGrowing:
    """F-4.5-J-10, and the product decision it breaches.

    Pins: `persona_for_session`'s rendezvous selection, specifically that it
    is NOT `int.from_bytes(digest) % len(personas)`. Deleting the control
    means replacing the argmax loop with that modulus, which is what shipped.
    """

    def test_growing_the_list_only_ever_moves_an_identity_onto_a_new_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The 2026-08-20 decision, restated as an assertion.

        The list ships at roughly 30 names and is SIZED for 100 so that a
        later extension is a data change and not a code change. A draw whose
        modulus is the list length reassigns essentially every identity the
        moment the file grows, which makes the extension a rewrite of every
        user's identity. This asserts the property that decision assumed:
        growing the file moves an identity only ONTO one of the names that
        were just added, never from one pre-existing scientist to another.

        The baseline half runs against the shipped file with nothing
        patched, so the mapping under test is obtained exactly as production
        obtains it.
        """
        shipped = _shipped_entries()
        added = [
            {
                "name": f"Added{n}",
                "full_name": f"Added Scientist {n}",
                "died": 1900 + n,
                "basis": "test extension",
            }
            for n in range(20)
        ]
        added_names = {entry["name"] for entry in added}
        extended_file = _write_list(tmp_path, shipped + added, "extended.json")

        before = _draw_against(None, _IDENTITIES, monkeypatch)
        after = _draw_against(extended_file, _IDENTITIES, monkeypatch)

        moved = {i for i in _IDENTITIES if before[i] != after[i]}
        landed_on_an_old_name = {i for i in moved if after[i] not in added_names}

        # The property itself.
        assert landed_on_an_old_name == set(), (
            f"{len(landed_on_an_old_name)} of {len(_IDENTITIES)} identities were "
            "reassigned between two scientists that BOTH already existed. Growing "
            "the curated file is supposed to be a data change; this is a rewrite "
            "of every affected user's identity. Examples: "
            + ", ".join(
                f"{i}: {before[i]} -> {after[i]}" for i in sorted(landed_on_an_old_name)[:3]
            )
        )
        # Non-vacuity, both directions. Without these the arm would pass on a
        # draw that never moved anyone (which no useful draw can be, since a
        # newly added name nobody is drawn for is dead weight in the file) and
        # on one that moved everyone onto new names.
        assert moved, "no identity moved at all, so the arm asserted nothing"
        assert len(moved) < len(_IDENTITIES) // 2, (
            f"{len(moved)} of {len(_IDENTITIES)} identities moved; adding 20 names "
            "to 32 should move roughly the share of the probability mass the new "
            "names carry, not a majority"
        )

    def test_reordering_the_file_changes_no_assignment(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The second thing a positional draw gets wrong.

        Pins: that the score is keyed on the persona NAME and never on its
        index in the file. A modulus over the list length reads position, so
        shuffling the file rebinds nearly everyone while the list's contents
        are byte-for-byte the same set.
        """
        shuffled = _shipped_entries()
        random.Random(20260820).shuffle(shuffled)
        shuffled_file = _write_list(tmp_path, shuffled, "shuffled.json")

        before = _draw_against(None, _IDENTITIES, monkeypatch)
        after = _draw_against(shuffled_file, _IDENTITIES, monkeypatch)

        assert before == after, (
            "reordering the curated file changed "
            f"{sum(1 for i in _IDENTITIES if before[i] != after[i])} assignments. "
            "The same names in a different order is the same list"
        )

    def test_every_name_the_shipped_list_hands_out_is_in_the_shipped_list(self) -> None:
        """The production path, with nothing patched and nothing handed in.

        Pins: that `persona_for_session` returns a member of the curated
        list rather than any string. Weak on its own, and kept because the
        two arms above both patch the file, and an arm that never touches
        the loader is what proves those two are varying something real.
        """
        curated = {p.name for p in load_persona_list()}
        drawn = {persona_for_session(session_id=i, user_id=None) for i in _IDENTITIES}

        assert drawn <= curated
        assert len(drawn) > 1, "600 identities all drew one name; the draw is not distributing"


class TestWhichIdentityTheDrawKeysOn:
    """Section 14.2's split: the account when there is one, the session
    otherwise. This is the property `GET /v1/persona` violated by passing a
    hardcoded `user_id=None` (F-4.5-J-12).

    Pins: the `identity = user_id or session_id` line.
    """

    def test_an_account_keeps_its_name_across_different_sessions(self) -> None:
        first = persona_for_session(session_id="session-a", user_id="account-1")
        second = persona_for_session(session_id="session-b", user_id="account-1")

        assert first == second

    def test_an_account_and_a_bare_session_are_different_identities(self) -> None:
        """Asserted as a specific property, not as "something differed".

        The account-keyed name for `account-1` must be the name the draw
        gives the string `account-1`, and the session-keyed name must be the
        name it gives the session string. That is what makes an arm that
        merely observed inequality useless here: two different inputs to a
        hash differ for reasons that have nothing to do with the routing.
        """
        assert persona_for_session(session_id="session-a", user_id="account-1") == (
            persona_for_session(session_id="account-1", user_id=None)
        )


# ---------------------------------------------------------------------------
# Endpoint arms. Every dependency that would reach PostgreSQL is overridden,
# so these run offline and deterministically; what they exercise is the
# handler's own decision, which is where every one of these findings lived.
# ---------------------------------------------------------------------------

_ACCOUNT_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")


class _FakeUser:
    """Enough of a `User` row for the two things these handlers read."""

    def __init__(self, profile: dict[str, Any] | None = None) -> None:
        self.id = _ACCOUNT_ID
        self.profile: dict[str, Any] = {} if profile is None else dict(profile)


class _FakeResult:
    def __init__(self, row: Any) -> None:
        self._row = row

    def scalar_one_or_none(self) -> Any:
        return self._row


class _FakeSession:
    """A `Session` stand-in covering only what these handlers call."""

    def __init__(self, user: Any) -> None:
        self._user = user
        self.commits = 0

    def execute(self, _statement: Any) -> _FakeResult:
        return _FakeResult(self._user)

    def get(self, _model: Any, _pk: Any) -> Any:
        return self._user

    def commit(self) -> None:
        self.commits += 1

    def add(self, _obj: Any) -> None:
        return None

    def flush(self) -> None:
        return None


@pytest.fixture
def app_client(monkeypatch: pytest.MonkeyPatch) -> Any:
    # A signing key for the two arms that mint or verify a bearer token.
    # Deterministic and local to this process; nothing here is a credential
    # for anything that exists.
    monkeypatch.setenv("AUTH_SECRET", "persona arms deterministic signing input")
    from system_03_search_agent.adapters.web_sse.app import app

    return app


class TestThePersonaEndpointAgreesWithTheQueryEndpoint:
    """F-4.5-J-12 and F-4.5-A-12's first disagreement.

    Pins: that `GET /v1/persona` reads the caller's credential and passes
    the resolved `user_id` into the draw. Deleting the control means
    restoring `user_id=None`, which is what shipped.
    """

    def test_a_signed_in_caller_gets_the_account_keyed_name(self, app_client: Any) -> None:
        """The landing chip and the first answer must name one scientist.

        The account-keyed name is computed here from `persona_for_session`
        with the account id, which is exactly how `POST /v1/query` computes
        the name it puts on its response body. The arm also asserts the
        anonymous name for the same session id is a DIFFERENT name, because
        otherwise a handler that still hardcoded `user_id=None` could pass
        by coincidence for whichever session string the test happened to
        pick.
        """
        from system_03_search_agent.auth.tokens import mint_access_token
        from system_03_search_agent.data.session import get_session

        session_id = "landing-session-1"
        account_name = persona_for_session(session_id=session_id, user_id=str(_ACCOUNT_ID))
        anonymous_name = persona_for_session(session_id=session_id, user_id=None)
        assert account_name != anonymous_name, (
            "this session id happens to draw the same name signed in and out, "
            "so it cannot distinguish the two keyings; pick another"
        )

        app_client.dependency_overrides[get_session] = lambda: _FakeSession(_FakeUser())
        try:
            client = TestClient(app_client)
            response = client.get(
                "/v1/persona",
                params={"session_id": session_id},
                headers={"Authorization": f"Bearer {mint_access_token(str(_ACCOUNT_ID))}"},
            )
        finally:
            app_client.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["persona_name"] == account_name

    def test_no_credential_still_answers_with_the_session_keyed_name(
        self, app_client: Any
    ) -> None:
        """The endpoint's original job must survive the fix.

        Pins: that reading the header is optional, not required. This is the
        anonymous landing screen, which has no credential by design
        (T-4.10-08 mints the guest token lazily on the first question).
        """
        from system_03_search_agent.data.session import get_session

        session_id = "landing-session-2"
        app_client.dependency_overrides[get_session] = lambda: _FakeSession(None)
        try:
            client = TestClient(app_client)
            response = client.get("/v1/persona", params={"session_id": session_id})
        finally:
            app_client.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["persona_name"] == persona_for_session(
            session_id=session_id, user_id=None
        )

    def test_a_bad_credential_degrades_instead_of_refusing(self, app_client: Any) -> None:
        """A stale token must not break the landing screen.

        Pins: the `except InvalidCallerError` fallback. Without it the
        exception escapes the handler as a 500, because `InvalidCallerError`
        is not an `HTTPException`. A landing chip is not worth failing a page
        load over, and the response discloses nothing either way.
        """
        from system_03_search_agent.data.session import get_session

        session_id = "landing-session-3"
        app_client.dependency_overrides[get_session] = lambda: _FakeSession(None)
        try:
            client = TestClient(app_client)
            response = client.get(
                "/v1/persona",
                params={"session_id": session_id},
                headers={"Authorization": "Bearer not-a-real-token"},
            )
        finally:
            app_client.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["persona_name"] == persona_for_session(
            session_id=session_id, user_id=None
        )


class TestTheGuestMintReportsAUsableName:
    """F-4.5-A-12's second disagreement: the mint's `persona_name` was keyed
    on the guest row id while every later query from that guest keys on the
    client-chosen session id, so the two could never match.

    Pins: that `create_guest` keys on the caller-supplied `session_id`.
    """

    def test_the_mint_name_is_the_one_that_sessions_first_answer_will_carry(
        self, app_client: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from system_03_search_agent.auth import router as auth_router_module
        from system_03_search_agent.data.session import get_session

        session_id = "guest-session-1"
        # F-4.7-04: `guest_id` was `uuid.uuid4()`, and the populate-check below
        # asserts the two keyings produce DIFFERENT personas. `persona_for_session`
        # maps onto 32 curated scientists, so a random id collided with this
        # fixed `session_id` about 1 run in 32 and turned the whole arm red for
        # a reason unrelated to what it tests. MEASURED rather than reasoned:
        # 628 collisions in 20000 random uuids, a rate of 0.0314 against
        # 1/32 = 0.03125.
        #
        # The lesson is worth more than the fix and is kept here rather than
        # only in the tracker. The unstable line was the arm's OWN ANTI-VACUITY
        # CHECK, the thing added to stop the arm proving nothing. A
        # populate-check written with a random value against a small codomain
        # trades one failure mode for another: it can now fail when nothing is
        # wrong, which is how a suite teaches people to ignore red. A
        # populate-check must be DETERMINISTIC.
        #
        # So the id is chosen, not drawn, and the loop below proves the choice
        # satisfies the property instead of assuming it. A hardcoded literal
        # would work today and break silently the moment the persona list or
        # the hashing changes; searching a fixed, ordered sequence cannot.
        guest_id = next(
            candidate
            for candidate in (
                uuid.UUID(int=seed) for seed in range(1, 200)
            )
            if persona_for_session(session_id=str(candidate), user_id=None)
            != persona_for_session(session_id=session_id, user_id=None)
        )
        # The mint throttle is module-level and keyed on the source hash, so
        # sixty guest mints from any other test in the same process inside the
        # same sixty-second window would turn this arm into a 429 and make it
        # fail for a reason that has nothing to do with what it asserts. Reset
        # rather than skipped: `test_phase_4_10_premise.py` clears the same
        # structure for the same reason.
        auth_router_module._mint_throttle._hits.clear()
        monkeypatch.setattr(
            auth_router_module,
            "create_guest_session",
            lambda _session: SimpleNamespace(id=guest_id, runs_used=0),
        )
        # The two keyings must be distinguishable, or the arm proves nothing.
        assert persona_for_session(session_id=session_id, user_id=None) != persona_for_session(
            session_id=str(guest_id), user_id=None
        )

        app_client.dependency_overrides[get_session] = lambda: _FakeSession(None)
        try:
            client = TestClient(app_client)
            response = client.post("/auth/guest", params={"session_id": session_id})
        finally:
            app_client.dependency_overrides.clear()

        assert response.status_code == 201
        assert response.json()["persona_name"] == persona_for_session(
            session_id=session_id, user_id=None
        )


class TestTheServerResolvesTheStoredAudienceDepth:
    """F-4.5-J-15 and F-4.5-A-13.

    Pins: that `POST /v1/query` reads the account row and calls
    `resolve_audience_depth`, rather than trusting a request field that used
    to default to the literal `"researcher"`. Deleting the control means
    restoring that default and passing `request.audience_depth` straight
    into the `Query`.
    """

    def _post(
        self,
        app_client: Any,
        monkeypatch: pytest.MonkeyPatch,
        *,
        user: _FakeUser,
        body: dict[str, Any],
        create_run_raises: Exception | None = None,
    ) -> tuple[Any, list[Any]]:
        from system_03_search_agent.adapters.web_sse import app as app_module
        from system_03_search_agent.auth.dependencies import Principal, get_caller
        from system_03_search_agent.data.session import get_session

        captured: list[Any] = []

        def _fake_create_run(query: Any, _context: Any, **_kwargs: Any) -> None:
            captured.append(query)
            if create_run_raises is not None:
                raise create_run_raises

        monkeypatch.setattr(app_module.default_registry, "create_run", _fake_create_run)
        app_client.dependency_overrides[get_session] = lambda: _FakeSession(user)
        app_client.dependency_overrides[get_caller] = lambda: Principal(
            owner_id=f"user:{_ACCOUNT_ID}", user_id=str(_ACCOUNT_ID), kind="user"
        )
        try:
            client = TestClient(app_client)
            response = client.post("/v1/query", json=body)
        finally:
            app_client.dependency_overrides.clear()
        return response, captured

    def test_a_caller_that_names_no_depth_gets_the_accounts_stored_one(
        self, app_client: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Section 14.5: "depth defaults to the user's last-used value".

        The request body omits `audience_depth` entirely, which is what a
        CLI, GraphQL, MCP or bare REST caller does. Before the fix the field
        defaulted to `"researcher"` in `CreateRunRequest`, so the handler
        could not tell "named nothing" from "asked for researcher" and the
        stored preference reached only the one client that re-echoed it.
        """
        user = _FakeUser({"audience_depth": "deep_technical"})
        response, captured = self._post(
            app_client,
            monkeypatch,
            user=user,
            body={"text": "What gene is BRCA1?", "session_id": "s-1"},
        )

        assert response.status_code in (200, 201, 202), response.text
        assert len(captured) == 1
        assert captured[0].audience_depth == "deep_technical"

    def test_an_explicitly_named_depth_still_wins(
        self, app_client: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Section 14.5: "always overridable per query".

        The stored preference must never be able to override what the caller
        asked for on this request, which is the failure a "stored preference
        wins" implementation would introduce while fixing the first arm.
        """
        user = _FakeUser({"audience_depth": "deep_technical"})
        response, captured = self._post(
            app_client,
            monkeypatch,
            user=user,
            body={
                "text": "What gene is BRCA1?",
                "session_id": "s-2",
                "audience_depth": "clinical_brief",
            },
        )

        assert response.status_code in (200, 201, 202), response.text
        assert captured[0].audience_depth == "clinical_brief"

    def test_a_refused_run_does_not_change_the_stored_preference(
        self, app_client: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-4.5-A-20.

        Pins: that the `write_audience_depth` call sits AFTER `create_run`
        returns. The write and its commit used to run before the run id was
        even minted, so a request the authoritative concurrent-run cap then
        refused had already permanently changed the account's default depth.
        A preference is a record of a choice that took effect.
        """
        from system_03_search_agent.core.run_registry import ConcurrentRunCapExceededError

        user = _FakeUser({"audience_depth": "researcher"})
        response, _ = self._post(
            app_client,
            monkeypatch,
            user=user,
            body={
                "text": "What gene is BRCA1?",
                "session_id": "s-3",
                "audience_depth": "deep_technical",
            },
            create_run_raises=ConcurrentRunCapExceededError(
                "too many active runs", retry_after_s=5, bound="per_owner"
            ),
        )

        assert response.status_code == 429
        assert (
            user.profile["audience_depth"] == "researcher"
        ), "a refused request rewrote the account's default depth"


class TestTheCliSanitizesTheServerSuppliedPersona:
    """F-4.5-A-11.

    Pins: the `_sanitize_untrusted` call in `Renderer._status_prefix`. The
    name is parsed off the `POST /v1/query` response body, so it is
    server-supplied freeform text reaching a terminal, which is an execution
    surface. It shipped raw under a comment asserting it came from this
    process's own curated list, which this process never imports.
    """

    def test_a_control_sequence_in_the_persona_name_never_reaches_the_terminal(
        self,
    ) -> None:
        from system_03_search_agent.adapters.cli.render import Renderer
        from system_03_search_agent.contracts.events import Event, ThinkPayload

        err = io.StringIO()
        renderer = Renderer(
            io.StringIO(),
            err,
            operator=False,
            persona_name="\x1b[31mCrick\x07",
        )
        renderer.handle(
            Event(
                type="think",
                version="v1",
                trace_id="trace-1",
                seq=1,
                ts=datetime(2026, 8, 20, tzinfo=UTC),
                payload=ThinkPayload(narrative="classifying", query_class="lookup").model_dump(),
            )
        )
        written = err.getvalue()

        assert "\x1b" not in written, "a raw ESC byte reached stderr"
        assert "\x07" not in written, "a raw BEL byte reached stderr"
        # The name is still shown, escaped, rather than dropped: the point is
        # a visible, inert rendering, not censorship.
        assert "Crick" in written
        assert "\\x1b" in written
