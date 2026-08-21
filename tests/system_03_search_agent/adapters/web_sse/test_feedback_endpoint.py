"""Tests for `POST /v1/query/{run_id}/feedback` (T-4.6-08,
tracker/phase_4.6.md).

`system_03_search_agent.feedback.record_feedback` is monkeypatched to a
fake, in-memory implementation for every test here, keyed by `trace_id`, so
this file only exercises what T-4.6-08 actually owns: ownership derivation
(via `_get_owned_run`, the same rule `POST /v1/query/{run_id}/stop` already
enforces), the request body's Pydantic validation
(`feedback.contracts.FeedbackPayload`, fixed elsewhere and used here as-is,
not rebuilt), and the mapping from `InteractionNotFound` /
`FeedbackOwnershipError` to their HTTP responses. `feedback/writer.py` and
`feedback/capture.py` are being built concurrently by other agents this
phase; this file never imports either.

Runs are seeded directly through `RunRegistry.create_run` (in-process, no
database), the same non-HTTP technique `test_run_registry.py` uses for its
own registry-level tests, with `run_registry_module.run_streaming`
monkeypatched to a fake generator that finishes immediately so no real
Guard/Plan/Synth call happens. `get_caller` is overridden via
`app.dependency_overrides` rather than a real signup/login or `POST
/auth/guest` round trip: nothing this endpoint touches (the registry, the
mocked writer) needs a genuine `User` or `GuestSession` row, unlike
`test_streaming_endpoints.py`, which also exercises real auth and allowance
logic. No skip-if-database-unreachable guard is needed here, and none is
used.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from system_03_search_agent.adapters.web_sse.app import app
from system_03_search_agent.auth.dependencies import Principal, get_caller
from system_03_search_agent.contracts.events import DonePayload, Event
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import run_registry as run_registry_module
from system_03_search_agent.feedback import FeedbackOwnershipError, InteractionNotFound

_RECORD_FEEDBACK_TARGET = "system_03_search_agent.adapters.web_sse.app.record_feedback"


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _fake_stream_finishes_immediately(
    query: Query, context: RequestContext
) -> AsyncIterator[Event]:
    yield Event(
        type="done",
        version="v1",
        trace_id=query.trace_id,
        seq=0,
        ts=datetime.now(UTC),
        payload=DonePayload(
            total_cost_usd=0.0, total_tool_calls=0, elapsed_ms=1, trust_outcome="answer"
        ).model_dump(),
    )


class _FakeFeedbackStore:
    """Stand-in for `feedback.record_feedback`, keyed by `trace_id`.

    `owned_by` fixes which `owner_id` may write each `trace_id`, so
    ownership and the not-yet-captured race are both test-controllable
    without a real `interactions` row. `calls` records every invocation so
    a test can assert `record_feedback` was never reached at all, the
    strongest available proof that a refused write did not happen, rather
    than only that the HTTP response looked like a refusal
    (`.claude/rules/goal-contracts.md`'s "assert on the stored value").
    """

    def __init__(self) -> None:
        self.captured: set[str] = set()
        self.owned_by: dict[str, str] = {}
        self.stored: dict[str, dict[str, object]] = {}
        self.calls: list[dict[str, object]] = []

    def mark_captured(self, trace_id: str, owner_id: str) -> None:
        self.captured.add(trace_id)
        self.owned_by[trace_id] = owner_id

    async def __call__(
        self,
        *,
        trace_id: str,
        owner_id: str,
        rating: str | None = None,
        comment: str | None = None,
        flagged_reason: str | None = None,
        citation_flags: list[dict[str, str]] | None = None,
    ) -> None:
        self.calls.append({"trace_id": trace_id, "owner_id": owner_id})
        if trace_id not in self.captured:
            raise InteractionNotFound(trace_id)
        if self.owned_by[trace_id] != owner_id:
            raise FeedbackOwnershipError(trace_id)
        # Replaces rather than appends, matching the real record_feedback's
        # own documented behavior (feedback/__init__.py).
        self.stored[trace_id] = {
            "rating": rating,
            "comment": comment,
            "flagged_reason": flagged_reason,
            "citation_flags": citation_flags or [],
        }


@pytest.fixture
def fake_feedback(monkeypatch: pytest.MonkeyPatch) -> _FakeFeedbackStore:
    store = _FakeFeedbackStore()
    monkeypatch.setattr(_RECORD_FEEDBACK_TARGET, store)
    return store


@pytest.fixture(autouse=True)
def _no_real_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        run_registry_module, "run_streaming", _fake_stream_finishes_immediately
    )


@pytest.fixture(autouse=True)
def _clear_caller_override() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.pop(get_caller, None)


def _set_caller(principal: Principal) -> None:
    app.dependency_overrides[get_caller] = lambda: principal


async def _seed_run(owner_id: str, user_id: str | None = None) -> str:
    """Create a run directly in the registry (no HTTP call, no database)
    and return its run_id, which is also its trace_id by construction: see
    `post_v1_query`'s "run_id/trace_id wiring" comment in app.py."""
    run_id = str(uuid.uuid4())
    query = Query(
        text="what gene is BRCA1",
        session_id=f"session-{run_id}",
        trace_id=run_id,
        user_id=user_id,
        owner_id=owner_id,
    )
    context = RequestContext(surface="rest_sse")
    run_registry_module.default_registry.create_run(
        query, context, run_id=run_id, owner_id=owner_id
    )
    entry = run_registry_module.default_registry.get_run(run_id)
    await asyncio.wait_for(entry.task, timeout=5.0)
    return run_id


_OWNER_ID = "user:11111111-1111-1111-1111-111111111111"
_OWNER_USER_ID = "11111111-1111-1111-1111-111111111111"
_OTHER_OWNER_ID = "user:22222222-2222-2222-2222-222222222222"
_OTHER_USER_ID = "22222222-2222-2222-2222-222222222222"
_GUEST_OWNER_ID = "guest:33333333-3333-3333-3333-333333333333"


def _owner_principal() -> Principal:
    return Principal(owner_id=_OWNER_ID, user_id=_OWNER_USER_ID, kind="user")


def _other_principal() -> Principal:
    return Principal(owner_id=_OTHER_OWNER_ID, user_id=_OTHER_USER_ID, kind="user")


def _guest_principal() -> Principal:
    return Principal(owner_id=_GUEST_OWNER_ID, user_id=None, kind="guest")


class TestValidInput:
    @pytest.mark.asyncio
    async def test_full_payload_returns_204_and_stores_every_field(
        self, fake_feedback: _FakeFeedbackStore
    ) -> None:
        """Mutation: changing the response status code line to `status.
        HTTP_200_OK` makes this test's status assertion fail; changing the
        `comment=payload.comment` call argument to `comment=payload.
        flagged_reason` (a field swap) makes the stored-value assertion
        fail. Both were applied by hand, confirmed red, and reverted."""
        run_id = await _seed_run(_OWNER_ID, _OWNER_USER_ID)
        fake_feedback.mark_captured(run_id, _OWNER_ID)
        _set_caller(_owner_principal())

        body = {
            "rating": "down",
            "comment": "the second citation does not support the claim",
            "flagged_reason": "hallucinated_citation",
            "citation_flags": [{"citation_id": "PMID:12345", "reason": "off_topic"}],
        }
        async with _client() as client:
            response = await client.post(f"/v1/query/{run_id}/feedback", json=body)

        assert response.status_code == 204
        assert response.content == b""
        assert fake_feedback.stored[run_id] == {
            "rating": "down",
            "comment": "the second citation does not support the claim",
            "flagged_reason": "hallucinated_citation",
            "citation_flags": [{"citation_id": "PMID:12345", "reason": "off_topic"}],
        }

    @pytest.mark.asyncio
    async def test_all_null_fields_is_valid_and_stores_nulls(
        self, fake_feedback: _FakeFeedbackStore
    ) -> None:
        """Mutation: hardcoding `rating="up"` instead of `rating=payload.
        rating` in the record_feedback call makes this test's stored-value
        assertion fail. Applied, confirmed red, reverted."""
        run_id = await _seed_run(_OWNER_ID, _OWNER_USER_ID)
        fake_feedback.mark_captured(run_id, _OWNER_ID)
        _set_caller(_owner_principal())

        body = {
            "rating": None,
            "comment": None,
            "flagged_reason": None,
            "citation_flags": [],
        }
        async with _client() as client:
            response = await client.post(f"/v1/query/{run_id}/feedback", json=body)

        assert response.status_code == 204
        assert fake_feedback.stored[run_id] == {
            "rating": None,
            "comment": None,
            "flagged_reason": None,
            "citation_flags": [],
        }

    @pytest.mark.asyncio
    async def test_missing_optional_fields_defaults_and_succeeds(
        self, fake_feedback: _FakeFeedbackStore
    ) -> None:
        """An empty body `{}` is valid: every FeedbackPayload field is
        optional or defaulted. Mutation: inserting `if payload.rating is
        None and payload.comment is None: raise HTTPException(400, ...)`
        right after the ownership check (an endpoint-level "must say
        something" guard the contract does not ask for) makes this test
        fail with 400 instead of 204. Applied, confirmed red, reverted."""
        run_id = await _seed_run(_OWNER_ID, _OWNER_USER_ID)
        fake_feedback.mark_captured(run_id, _OWNER_ID)
        _set_caller(_owner_principal())

        async with _client() as client:
            response = await client.post(f"/v1/query/{run_id}/feedback", json={})

        assert response.status_code == 204
        assert fake_feedback.stored[run_id] == {
            "rating": None,
            "comment": None,
            "flagged_reason": None,
            "citation_flags": [],
        }


class TestInvalidInput:
    @pytest.mark.asyncio
    async def test_rejects_a_rating_outside_the_closed_enum(
        self, fake_feedback: _FakeFeedbackStore
    ) -> None:
        """Mutation: swapping the request body parameter's type annotation
        from `FeedbackPayload` to `dict` (accept-anything, with `.get(...)`
        field access in place of attribute access) makes this test fail,
        since an arbitrary dict is not validated at all: the response
        becomes 204 instead of 422. Applied to all three tests in this
        class together, confirmed all three went red, reverted."""
        run_id = await _seed_run(_OWNER_ID, _OWNER_USER_ID)
        fake_feedback.mark_captured(run_id, _OWNER_ID)
        _set_caller(_owner_principal())

        async with _client() as client:
            response = await client.post(
                f"/v1/query/{run_id}/feedback", json={"rating": "sideways"}
            )

        assert response.status_code == 422
        assert fake_feedback.calls == []

    @pytest.mark.asyncio
    async def test_rejects_a_comment_over_the_length_cap(
        self, fake_feedback: _FakeFeedbackStore
    ) -> None:
        """FeedbackPayload.comment caps at 2000 characters
        (feedback/contracts.py). Mutation: same `dict`-typed body swap as
        the sibling tests in this class (applied and reverted together);
        an uncapped comment then passes through as 204 instead of being
        rejected as 422."""
        run_id = await _seed_run(_OWNER_ID, _OWNER_USER_ID)
        fake_feedback.mark_captured(run_id, _OWNER_ID)
        _set_caller(_owner_principal())

        async with _client() as client:
            response = await client.post(
                f"/v1/query/{run_id}/feedback", json={"comment": "x" * 2001}
            )

        assert response.status_code == 422
        assert fake_feedback.calls == []

    @pytest.mark.asyncio
    async def test_rejects_an_unknown_extra_field(
        self, fake_feedback: _FakeFeedbackStore
    ) -> None:
        """FeedbackPayload is `extra="forbid"`. Mutation: same `dict`-typed
        body swap as the two tests above (applied and reverted together);
        the extra field is then silently accepted, returning 204 instead
        of 422."""
        run_id = await _seed_run(_OWNER_ID, _OWNER_USER_ID)
        fake_feedback.mark_captured(run_id, _OWNER_ID)
        _set_caller(_owner_principal())

        async with _client() as client:
            response = await client.post(
                f"/v1/query/{run_id}/feedback", json={"totally_unexpected_field": "x"}
            )

        assert response.status_code == 422
        assert fake_feedback.calls == []


class TestOwnership:
    @pytest.mark.asyncio
    async def test_a_guest_can_rate_their_own_answer(
        self, fake_feedback: _FakeFeedbackStore
    ) -> None:
        """Build phase 4.10's anonymous run path: a guest must be able to
        rate an answer they own. Mutation: adding `if caller.kind ==
        "guest": raise HTTPException(403, ...)` before the record_feedback
        call makes this test fail. Applied, confirmed red, reverted."""
        run_id = await _seed_run(_GUEST_OWNER_ID, None)
        fake_feedback.mark_captured(run_id, _GUEST_OWNER_ID)
        _set_caller(_guest_principal())

        async with _client() as client:
            response = await client.post(
                f"/v1/query/{run_id}/feedback", json={"rating": "up"}
            )

        assert response.status_code == 204
        assert fake_feedback.stored[run_id]["rating"] == "up"

    @pytest.mark.asyncio
    async def test_a_different_principal_is_refused_and_the_stored_value_is_unchanged(
        self, fake_feedback: _FakeFeedbackStore
    ) -> None:
        """Asserts on the stored value and the call count, not only the
        status code (`.claude/rules/goal-contracts.md`: "a surface that
        refuses loudly and writes anyway passes a status-code assertion").

        Mutation: replacing `entry = _get_owned_run(run_id, caller)` with
        `entry = default_registry.get_run(run_id)` (existence check only,
        no ownership enforcement) leaves the status code at 403 (the fake
        store's own FeedbackOwnershipError still fires), but
        `fake_feedback.calls` grows from 1 to 2 and `stored[run_id]` is
        untouched only because the fake happens to reject unowned writes;
        a real writer with a looser check would not be caught by the
        status-code assertion alone. Applied, confirmed the call-count
        assertion below goes red while the status-code assertion alone
        would have stayed green, reverted.
        """
        run_id = await _seed_run(_OWNER_ID, _OWNER_USER_ID)
        fake_feedback.mark_captured(run_id, _OWNER_ID)
        _set_caller(_owner_principal())

        async with _client() as client:
            first = await client.post(
                f"/v1/query/{run_id}/feedback", json={"rating": "up"}
            )
            assert first.status_code == 204
            assert fake_feedback.stored[run_id]["rating"] == "up"

            _set_caller(_other_principal())
            second = await client.post(
                f"/v1/query/{run_id}/feedback", json={"rating": "down"}
            )

        assert second.status_code == 403
        assert second.json()["detail"] == "you do not own this run"
        # The write from the rejected caller never reached record_feedback
        # at all: still exactly the one call the owner made above.
        assert fake_feedback.calls == [{"trace_id": run_id, "owner_id": _OWNER_ID}]
        assert fake_feedback.stored[run_id]["rating"] == "up"

    @pytest.mark.asyncio
    async def test_a_row_level_ownership_refusal_is_403_and_writes_nothing(
        self, fake_feedback: _FakeFeedbackStore
    ) -> None:
        """The `except FeedbackOwnershipError` branch, which had no arm at all.

        Filed as J-07 in `tracker/phase_4.6_judge_report.md`: turning that
        handler into a silent 204 left this file at `11 passed`. It is the
        one untested control of the three the judge found that is not
        academic, because J-01, the phase's worst finding, IS that branch
        firing in production, and nothing here could see it.

        The branch is reached only when the two ownership checks DISAGREE:
        `_get_owned_run` says the caller owns the run at the registry layer,
        and the row-level check inside `record_feedback` says they do not.
        Seeded here by marking the captured row as owned by a different
        principal than the registry run, which is the shape a stale or
        reassigned `interactions.owner_id` produces.

        Two properties, not one. The status is 403, and the detail string is
        byte-identical to the registry-level refusal the sibling test above
        asserts: `app.py`'s own comment says a more specific message would
        let a caller tell the two refusals apart and learn something about
        the row's real state. A separate "feedback ownership" wording would
        pass a status-code-only assertion and leak exactly that.

        Control: the `except FeedbackOwnershipError` handler in
        `post_v1_query_feedback`. Mutations run and confirmed red, and what
        ACTUALLY happened is recorded rather than what was predicted:

        - Replacing the handler body with `return Response(status_code=
          status.HTTP_204_NO_CONTENT)` (the judge's EP2) fails on the status
          assertion with 204, and the caller's rating is silently discarded.
        - Deleting the handler entirely does NOT produce a 500 here. The
          exception propagates out of the endpoint and httpx's ASGI
          transport re-raises it, so the test errors with
          `FeedbackOwnershipError` at the `client.post` call rather than
          failing on an assertion. Red either way, and worth naming because
          the obvious prediction (a 500 response) is not what happens.
        - Changing the detail string to a distinct "you do not own this
          feedback" fails on the detail assertion alone while the status
          assertion stays green, which is the disclosure half of this arm.
        """
        run_id = await _seed_run(_OWNER_ID, _OWNER_USER_ID)
        # Captured, but the ROW says a different principal owns it.
        fake_feedback.mark_captured(run_id, _OTHER_OWNER_ID)
        _set_caller(_owner_principal())

        async with _client() as client:
            response = await client.post(
                f"/v1/query/{run_id}/feedback", json={"rating": "up"}
            )

        assert response.status_code == 403
        assert response.json()["detail"] == "you do not own this run", (
            "the row-level refusal uses a different message than the "
            "registry-level one, so a caller can tell the two apart and "
            "learn that the run exists and was captured"
        )
        # The attempt DID reach record_feedback, which is what distinguishes
        # this branch from the `_get_owned_run` 403 the sibling test covers.
        assert fake_feedback.calls == [{"trace_id": run_id, "owner_id": _OWNER_ID}]
        assert run_id not in fake_feedback.stored, (
            "a refused caller's rating was stored anyway; a surface can "
            "refuse loudly and write regardless"
        )

    @pytest.mark.asyncio
    async def test_an_unknown_run_id_is_404(
        self, fake_feedback: _FakeFeedbackStore
    ) -> None:
        """Mutation: catching RunNotFoundError inside `_get_owned_run` and
        mapping it to 403 instead of 404 makes this test fail. Applied,
        confirmed red, reverted."""
        _set_caller(_owner_principal())

        async with _client() as client:
            response = await client.post(
                f"/v1/query/{uuid.uuid4()}/feedback", json={"rating": "up"}
            )

        assert response.status_code == 404
        assert fake_feedback.calls == []


class TestNotYetCapturedRace:
    @pytest.mark.asyncio
    async def test_feedback_for_a_run_not_yet_captured_returns_409_with_retry_after(
        self, fake_feedback: _FakeFeedbackStore
    ) -> None:
        """Capture is a background task dispatched after the `done` event
        (Section 16 stage 1), so a caller can genuinely race it. Mutation:
        removing the `except InteractionNotFound` clause lets the exception
        propagate unhandled, turning this into an unhandled-exception 500
        instead of a 409. Applied, confirmed red (500), reverted."""
        run_id = await _seed_run(_OWNER_ID, _OWNER_USER_ID)
        # Deliberately NOT marked captured: simulates the race window.
        _set_caller(_owner_principal())

        async with _client() as client:
            response = await client.post(
                f"/v1/query/{run_id}/feedback", json={"rating": "up"}
            )

        assert response.status_code == 409
        assert "Retry-After" in response.headers
        assert int(response.headers["Retry-After"]) > 0
        # The attempt reached record_feedback (it is not silently
        # discarded); it simply could not be written yet.
        assert fake_feedback.calls == [{"trace_id": run_id, "owner_id": _OWNER_ID}]
        assert run_id not in fake_feedback.stored


class TestCitationFlagsBounds:
    """F-4.6-A-07 (`tracker/phase_4.6_adversary_report.md`), replayed
    through the real endpoint rather than at the type level
    (`tests/system_03_search_agent/feedback/test_contracts.py` owns the
    type-level version). The adversary's measured result against the
    shipped endpoint: a body with 50 `citation_flags` entries of roughly
    2 MB each returned 204 and was stored. `FeedbackPayload.citation_flags`
    is now `list[FeedbackCitationFlag]` (feedback/contracts.py), bounding
    `citation_id` and `reason` inside each entry, not just how many
    entries the list may hold.
    """

    @pytest.mark.asyncio
    async def test_the_adversarys_oversized_payload_is_now_rejected(
        self, fake_feedback: _FakeFeedbackStore
    ) -> None:
        """Reproduces F-4.6-A-07's exact shape: 50 entries, each carrying a
        1,000,000-character `citation_id` and a 1,000,000-character
        `reason`. Mutation, run in two steps because the fix touches two
        files that are coupled at this call boundary: (1) reverting only
        `FeedbackPayload.citation_flags`'s field type in
        `feedback/contracts.py` back to the pre-fix `list[dict[str, str]]`,
        with `app.py`'s `.model_dump()` call left in place, turned this
        into an unhandled 500 (`AttributeError: 'dict' object has no
        attribute 'model_dump'`), not the adversary's 204, because the
        dump call assumes typed entries. (2) Reverting `app.py`'s call
        too, back to the bare `citation_flags=payload.citation_flags` it
        used before the fix, reproduced the adversary's result exactly:
        204. Both reverted immediately after confirming red; the assertion
        below is the fixed, passing state."""
        run_id = await _seed_run(_OWNER_ID, _OWNER_USER_ID)
        fake_feedback.mark_captured(run_id, _OWNER_ID)
        _set_caller(_owner_principal())

        oversized_entry = {
            "citation_id": "A" * 1_000_000,
            "reason": "B" * 1_000_000,
        }
        body = {"rating": "down", "citation_flags": [oversized_entry] * 50}

        async with _client() as client:
            response = await client.post(f"/v1/query/{run_id}/feedback", json=body)

        assert response.status_code == 422
        assert fake_feedback.calls == []
        assert run_id not in fake_feedback.stored

    @pytest.mark.asyncio
    async def test_arbitrary_keys_in_a_citation_flag_entry_are_rejected(
        self, fake_feedback: _FakeFeedbackStore
    ) -> None:
        """The adversary's second probe against this same endpoint:
        entries with no `citation_id`/`reason` at all. Mutation: the same
        two-file reversion as the test above, applied and reverted
        together. With both files reverted, this arbitrary-keys entry also
        validated and returned 204, not 422, matching the adversary's
        second measured result exactly."""
        run_id = await _seed_run(_OWNER_ID, _OWNER_USER_ID)
        fake_feedback.mark_captured(run_id, _OWNER_ID)
        _set_caller(_owner_principal())

        body = {
            "rating": "down",
            "citation_flags": [{"anything": "x", "xxxx" * 50: "y"}],
        }

        async with _client() as client:
            response = await client.post(f"/v1/query/{run_id}/feedback", json=body)

        assert response.status_code == 422
        assert fake_feedback.calls == []

    @pytest.mark.asyncio
    async def test_fifty_maximum_length_entries_is_a_legitimate_payload(
        self, fake_feedback: _FakeFeedbackStore
    ) -> None:
        """The bound must not reject the real worst case, only the
        adversarial one: 50 entries at exactly the per-field max (64 +
        200 characters) is the number `FeedbackPayload.citation_flags`'s
        own comment names as the legitimate worst case. Also proves the
        endpoint dumps each `FeedbackCitationFlag` model instance back to a
        plain dict before calling `record_feedback`
        (`adapters/web_sse/app.py`'s `[flag.model_dump() for flag in
        payload.citation_flags]`), not a model instance the fake store
        would fail to compare against a dict literal. Mutation: changing
        that call argument back to the bare `payload.citation_flags` (no
        `.model_dump()`) makes the stored-value equality assertion below
        fail, since a `FeedbackCitationFlag` instance does not equal an
        identical plain dict. Applied, confirmed red, reverted."""
        run_id = await _seed_run(_OWNER_ID, _OWNER_USER_ID)
        fake_feedback.mark_captured(run_id, _OWNER_ID)
        _set_caller(_owner_principal())

        entry = {"citation_id": "x" * 64, "reason": "y" * 200}
        body = {"rating": "down", "citation_flags": [entry] * 50}

        async with _client() as client:
            response = await client.post(f"/v1/query/{run_id}/feedback", json=body)

        assert response.status_code == 204
        stored_flags = fake_feedback.stored[run_id]["citation_flags"]
        assert stored_flags == [entry] * 50
        assert all(isinstance(flag, dict) for flag in stored_flags)


class TestIdempotentRetry:
    @pytest.mark.asyncio
    async def test_repeat_submission_replaces_rather_than_appends(
        self, fake_feedback: _FakeFeedbackStore
    ) -> None:
        """production-standards.md's retry-safety gate: a client retry (or
        a caller changing their mind) must produce the same end state, not
        an accumulating history. record_feedback itself owns replace-not-
        append behavior (feedback/__init__.py); this test only proves the
        endpoint does not add a second layer on top that would reject a
        second submission. Mutation: adding `if run_id in fake_feedback.
        stored: raise HTTPException(409, ...)` before the record_feedback
        call (simulating an endpoint-level "already rated" guard the
        contract does not ask for) makes the second POST fail with 409
        instead of 204. Applied, confirmed red, reverted."""
        run_id = await _seed_run(_OWNER_ID, _OWNER_USER_ID)
        fake_feedback.mark_captured(run_id, _OWNER_ID)
        _set_caller(_owner_principal())

        async with _client() as client:
            first = await client.post(
                f"/v1/query/{run_id}/feedback", json={"rating": "up"}
            )
            second = await client.post(
                f"/v1/query/{run_id}/feedback",
                json={"rating": "down", "comment": "changed my mind"},
            )

        assert first.status_code == 204
        assert second.status_code == 204
        assert len(fake_feedback.calls) == 2
        # One stored row, holding only the latest submission.
        assert fake_feedback.stored[run_id] == {
            "rating": "down",
            "comment": "changed my mind",
            "flagged_reason": None,
            "citation_flags": [],
        }
