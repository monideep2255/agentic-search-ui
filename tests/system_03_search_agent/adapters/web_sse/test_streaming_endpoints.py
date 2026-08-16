"""Tests for the three streaming endpoints (T-1.2-02): `POST /v1/query`
(create), `GET /v1/query/{run_id}/events` (SSE), `POST
/v1/query/{run_id}/stop` (stop).

Hits the real local PostgreSQL `search_agent_users` database through the
actual FastAPI app, the same pattern `test_query_endpoint.py` already uses:
`get_current_user` resolves a real `User` row via the session dependency,
which cannot be verified against a mock. The whole module skips cleanly
(does not fail) when USER_DB_URL is unreachable.

Uses `httpx.AsyncClient` over `ASGITransport` rather than
`starlette.testclient.TestClient`: every test here needs the background
task `RunRegistry.create_run` starts (via `asyncio.create_task`) to run on
the *same* event loop the test itself awaits on, so that awaiting
`entry.queue.get()` inside the events endpoint actually yields control
back to that task rather than racing an unrelated portal-thread loop.
`AsyncClient` + `ASGITransport` runs the ASGI app directly on the calling
coroutine's own event loop; `TestClient`'s thread-portal model does not
give that guarantee as directly, and every real test below depends on the
task genuinely draining into the run's queue while the test awaits it.

Every test uses a freshly generated email (uuid4-based) so reruns never
collide with rows a prior run left behind, the same convention
`test_router.py`/`test_query_endpoint.py` already use for this database.

Most tests here drive the real (mocked-litellm) five-node graph via
`RunRegistry`, the same pattern `test_run_registry.py`'s
`TestRunRegistryEndToEndWithTheRealGraph` and `test_query_endpoint.py`
already use, so the events these tests observe (`guard`, `done`, `cost`)
are genuinely produced by the real loop, not a hand-built fixture. The one
exception is `TestStopEndpoint::test_stops_a_still_running_run_and_returns_200`,
which needs a run that reliably never finishes on its own long enough for
`cancel_run` to catch it mid-flight; that test monkeypatches
`run_registry_module.run_streaming` directly with a fake generator that
hangs after its first event, the same technique
`test_run_registry.py`'s own cancellation tests use.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient

USER_DB_URL = os.environ.get("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")
os.environ.setdefault("USER_DB_URL", USER_DB_URL)


def _can_connect() -> bool:
    try:
        probe_engine = sa.create_engine(USER_DB_URL)
        with probe_engine.connect():
            pass
        probe_engine.dispose()
        return True
    except Exception:  # noqa: BLE001 - a reachability probe must catch any failure mode
        return False


if not _can_connect():
    pytest.skip(
        "search_agent_users PostgreSQL database is not reachable; "
        "set USER_DB_URL and ensure the server is running to run this suite",
        allow_module_level=True,
    )

from system_03_search_agent.adapters.web_sse.app import app
from system_03_search_agent.contracts.events import DonePayload, Event, GuardPayload
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import run_registry as run_registry_module
from system_03_search_agent.harness import harness as harness_module

_TEST_AUTH_SECRET = "test-only-auth-secret-for-streaming-endpoint-tests-do-not-reuse"


def _fake_response(content: str = "ok", prompt_tokens: int = 10, completion_tokens: int = 5):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


@pytest.fixture(autouse=True)
def _harness_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """T-2.0-07: run_streaming() drives real Harness.call_tier invocations
    through the five-node graph; pin every tier's model and cap so this
    file's tests get a stable, fast (mocked) round trip."""
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("PER_USER_DAILY_QUERY_CAP", "100")
    monkeypatch.setenv("ANON_DAILY_RUN_CAP", "10000")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")


@pytest.fixture(autouse=True)
def _mock_litellm(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    # T-3.0-06: dispatches per tier. See `tests/system_03_search_agent/
    # model_stub.py`.
    from tests.system_03_search_agent.model_stub import install_dispatching_acompletion

    return install_dispatching_acompletion(monkeypatch, harness_module)


@pytest.fixture(autouse=True)
def _stub_symbol_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Finding 4 (MAJOR, re-review, build phase 3.1): `_create_body`'s
    default query text names BRCA1 by symbol, and `core.graph.
    resolve_symbol_to_curie` is a live NCBI call (T-3.1-11). This file
    drives the real graph loop through `RunRegistry`, so without a
    stand-in a plain `pytest tests/ -q` run reached out to
    `api.ncbi.nlm.nih.gov` for real, silently burning E-utilities quota
    and making the suite's green depend on NCBI being up. Same fix
    `test_graph.py`, `test_run.py`, and `test_query_endpoint.py` already
    apply, for the identical reason; this file was the one agent-loop
    test file that had not received it.
    """
    from system_03_search_agent.core import graph as graph_module

    known = {"BRCA1": "NCBIGene:672", "TP53": "NCBIGene:7157"}

    async def _fake_resolve_symbol_to_curie(symbol: str, **kwargs: object) -> str | None:
        return known.get(symbol.strip().upper())

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _fake_resolve_symbol_to_curie)


@pytest.fixture(autouse=True)
def _stub_ncbi_efetch_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """T-3.4-05/T-3.1-28: `plan_node` now also dispatches a second, Layer 2
    `ncbi_efetch` call whenever a resolved target entity is Gene-shaped,
    and `_create_body`'s default query text names BRCA1 (a Gene) by
    symbol. Same rationale as `_stub_symbol_resolution` above: without a
    stand-in, this file's real graph loop would reach out to
    `api.ncbi.nlm.nih.gov` for real. Stubbed to a genuine, never-fabricated
    "empty" result, which contributes no citation or trust signal, so no
    pre-existing assertion here is affected.
    """
    from system_03_search_agent.core import graph as graph_module
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput

    async def _fake_ncbi_efetch(tool_input: object, **kwargs: object) -> NcbiEfetchOutput:
        return NcbiEfetchOutput(
            status="empty",
            action="dataset_report",
            records=[],
            record_count=0,
            total_available=None,
            truncated=False,
            error=None,
        )

    monkeypatch.setattr(graph_module, "ncbi_efetch", _fake_ncbi_efetch)


@pytest.fixture(autouse=True)
def _auth_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_SECRET", _TEST_AUTH_SECRET)


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _unique_email() -> str:
    return f"{uuid.uuid4()}@example.com"


async def _signup_and_login(client: AsyncClient) -> tuple[str, dict[str, str]]:
    """Create a fresh user, log in, and return (user_id, tokens)."""
    email = _unique_email()
    password = "Str0ngPassw0rd!"
    signup = await client.post("/auth/signup", json={"email": email, "password": password})
    assert signup.status_code == 201
    user_id = signup.json()["id"]
    login = await client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return user_id, login.json()


async def _auth_headers(client: AsyncClient) -> tuple[str, dict[str, str]]:
    """Create a fresh authenticated user and return (user_id, headers)."""
    user_id, tokens = await _signup_and_login(client)
    return user_id, {"Authorization": f"Bearer {tokens['access_token']}"}


def _create_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {"text": "What gene is BRCA1?", "session_id": "session-1"}
    body.update(overrides)
    return body


async def _create_run(client: AsyncClient, headers: dict[str, str], **overrides: object) -> str:
    response = await client.post("/v1/query", json=_create_body(**overrides), headers=headers)
    assert response.status_code == 202
    return response.json()["run_id"]


async def _drain_run_task(run_id: str) -> None:
    """Wait for `run_id`'s background task to actually finish.

    Every test that does not itself need to observe the run mid-flight
    calls this before the test ends, so a still-running task never leaks
    into a later test as a background coroutine racing a monkeypatch (an
    env var, a mocked `litellm.acompletion`) that test has already undone.
    """
    entry = run_registry_module.default_registry.get_run(run_id)
    await asyncio.wait_for(entry.task, timeout=5.0)


def _parse_sse_frames(raw_text: str) -> list[dict[str, str]]:
    """Parse a raw `text/event-stream` body into a list of {field: value} frames.

    Handles sse-starlette's default `"\\r\\n"` line separator, with each
    frame terminated by a blank line. Sufficient for this file's
    controlled, single-line JSON payloads (the mocked litellm content is
    always `"ok"`, so no payload string here ever contains a literal
    newline); this is not a general-purpose SSE parser.
    """
    frames: list[dict[str, str]] = []
    normalized = raw_text.replace("\r\n", "\n")
    for block in normalized.split("\n\n"):
        block = block.strip("\n")
        if not block:
            continue
        frame: dict[str, str] = {}
        for line in block.split("\n"):
            if not line:
                continue
            field, _, value = line.partition(": ")
            frame[field] = value
        frames.append(frame)
    return frames


def _fake_event(event_type: str, trace_id: str, seq: int) -> Event:
    if event_type == "guard":
        payload = GuardPayload(passed=True, category="ok", reason=None)
    elif event_type == "done":
        payload = DonePayload(
            total_cost_usd=0.0, total_tool_calls=0, elapsed_ms=1, trust_outcome="answer"
        )
    else:  # pragma: no cover - only "guard"/"done" are used by this file's fake stream
        raise ValueError(event_type)
    return Event(
        type=event_type,
        version="v1",
        trace_id=trace_id,
        seq=seq,
        ts=datetime.now(UTC),
        payload=payload.model_dump(),
    )


class TestCreateRun:
    """`POST /v1/query`: run creation, the 202 response, and the
    run_id/trace_id/ownership wiring."""

    @pytest.mark.asyncio
    async def test_returns_202_with_a_run_id_and_the_stub_persona_name(self) -> None:
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            response = await client.post("/v1/query", json=_create_body(), headers=headers)

            assert response.status_code == 202
            body = response.json()
            uuid.UUID(body["run_id"])  # raises ValueError if not a well-formed UUID
            assert body["persona_name"] == "Assistant"

            await _drain_run_task(body["run_id"])

    @pytest.mark.asyncio
    async def test_requires_auth(self) -> None:
        async with _client() as client:
            response = await client.post("/v1/query", json=_create_body())
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_session_id_returns_422(self) -> None:
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            body = _create_body()
            del body["session_id"]
            response = await client.post("/v1/query", json=body, headers=headers)
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_unknown_top_level_field_rejected(self) -> None:
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            body = _create_body(extra_field="nope")
            response = await client.post("/v1/query", json=body, headers=headers)
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_text_returns_422(self) -> None:
        """F-1.2-05 (adversarial pass): an empty `text` used to return 202
        and burn a full four-call pipeline run for no real query."""
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            response = await client.post("/v1/query", json=_create_body(text=""), headers=headers)
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_whitespace_only_text_returns_422(self) -> None:
        """F-1.2-05: `min_length=1` alone accepts a whitespace-only string;
        the same rejection must catch this too."""
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            response = await client.post(
                "/v1/query", json=_create_body(text="   \t\n  "), headers=headers
            )
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_the_created_run_is_owned_by_the_authenticated_caller(self) -> None:
        async with _client() as client:
            user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)

            entry = run_registry_module.default_registry.get_run(run_id)
            assert entry.user_id == user_id

            await _drain_run_task(run_id)

    @pytest.mark.asyncio
    async def test_run_id_and_the_events_trace_id_are_the_same_identifier(self) -> None:
        """Section 13.1 frames run_id and Query.trace_id as "the same
        identifier under two names"; every event this run produces must
        carry that exact run_id as its trace_id."""
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)
            await _drain_run_task(run_id)

            entry = run_registry_module.default_registry.get_run(run_id)
            events: list[Event] = []
            while not entry.queue.empty():
                item = entry.queue.get_nowait()
                if item is not None:
                    events.append(item)

            assert len(events) > 0
            assert all(event.trace_id == run_id for event in events)

    @pytest.mark.asyncio
    async def test_returns_before_the_graph_has_finished(
        self, _mock_litellm: AsyncMock
    ) -> None:
        """A deliberately slow mocked model call proves the 202 response
        does not wait for the graph: every call sleeps well past the
        response, so a fast response can only mean the endpoint returned
        without awaiting run_streaming()'s completion (the same
        asyncio.sleep-in-mocked-call trick test_run.py's
        TestRunStreamingIsGenuinelyIncremental uses)."""
        delay_s = 0.5

        async def _slow_response(*_args: object, **_kwargs: object):
            await asyncio.sleep(delay_s)
            return _fake_response()

        _mock_litellm.side_effect = _slow_response

        async with _client() as client:
            _user_id, headers = await _auth_headers(client)

            start = time.monotonic()
            response = await client.post("/v1/query", json=_create_body(), headers=headers)
            elapsed_s = time.monotonic() - start

            assert response.status_code == 202
            assert elapsed_s < delay_s * 0.5, (
                f"POST /v1/query took {elapsed_s:.3f}s to respond, expected "
                f"well under the mocked model call's {delay_s}s delay, "
                "proving the response does not wait for the graph to finish"
            )

            await _drain_run_task(response.json()["run_id"])


class TestEventsEndpoint:
    """`GET /v1/query/{run_id}/events`: SSE streaming, ownership, cost
    filtering."""

    @pytest.mark.asyncio
    async def test_requires_auth(self) -> None:
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)
            await _drain_run_task(run_id)

            response = await client.get(f"/v1/query/{run_id}/events")
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_404s_for_an_unknown_run_id(self) -> None:
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            response = await client.get(f"/v1/query/{uuid.uuid4()}/events", headers=headers)
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_403s_for_a_different_users_run(self) -> None:
        async with _client() as client:
            _owner_id, owner_headers = await _auth_headers(client)
            run_id = await _create_run(client, owner_headers)
            await _drain_run_task(run_id)

            _other_id, other_headers = await _auth_headers(client)
            response = await client.get(f"/v1/query/{run_id}/events", headers=other_headers)
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_owner_can_still_read_their_own_run(self) -> None:
        async with _client() as client:
            _owner_id, owner_headers = await _auth_headers(client)
            run_id = await _create_run(client, owner_headers)

            response = await client.get(f"/v1/query/{run_id}/events", headers=owner_headers)
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_streams_events_as_text_event_stream_ending_in_done(self) -> None:
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)

            response = await client.get(f"/v1/query/{run_id}/events", headers=headers)

            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            frames = _parse_sse_frames(response.text)
            assert len(frames) > 0
            event_types = [frame["event"] for frame in frames]
            assert event_types[-1] == "done"
            assert "guard" in event_types

    @pytest.mark.asyncio
    async def test_sse_data_frame_is_the_full_event_envelope_as_json(self) -> None:
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)

            response = await client.get(f"/v1/query/{run_id}/events", headers=headers)
            frames = _parse_sse_frames(response.text)

            done_frame = next(frame for frame in frames if frame["event"] == "done")
            done_event = json.loads(done_frame["data"])
            assert done_event["type"] == "done"
            assert done_event["version"] == "v1"
            assert done_event["trace_id"] == run_id
            assert "payload" in done_event

    @pytest.mark.asyncio
    async def test_never_carries_a_cost_event_for_a_non_operator_caller(self) -> None:
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)

            response = await client.get(f"/v1/query/{run_id}/events", headers=headers)
            frames = _parse_sse_frames(response.text)

            assert all(frame["event"] != "cost" for frame in frames)

    @pytest.mark.asyncio
    async def test_done_total_cost_usd_is_redacted_to_zero_for_a_non_operator_caller(
        self,
    ) -> None:
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)

            response = await client.get(f"/v1/query/{run_id}/events", headers=headers)
            frames = _parse_sse_frames(response.text)

            done_frame = next(frame for frame in frames if frame["event"] == "done")
            done_event = json.loads(done_frame["data"])
            assert done_event["payload"]["total_cost_usd"] == 0.0

    @pytest.mark.asyncio
    async def test_the_real_unfiltered_run_did_produce_a_cost_event(self) -> None:
        """Proves the filtering above is doing real work, not passing
        vacuously because run_streaming() never emitted a cost event in
        the first place: reads the run's own queue directly (never through
        the filtered SSE endpoint) after the run has finished, the same
        style of proof test_query_endpoint.py's
        TestPostQueryFiltersCostEvents uses for the buffered endpoint."""
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)
            await _drain_run_task(run_id)

            entry = run_registry_module.default_registry.get_run(run_id)
            unfiltered_events: list[Event] = []
            while not entry.queue.empty():
                item = entry.queue.get_nowait()
                if item is not None:
                    unfiltered_events.append(item)

            assert any(event.type == "cost" for event in unfiltered_events)


class TestStopEndpoint:
    """`POST /v1/query/{run_id}/stop`: cancellation, ownership, idempotency."""

    @pytest.mark.asyncio
    async def test_requires_auth(self) -> None:
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)
            await _drain_run_task(run_id)

            response = await client.post(f"/v1/query/{run_id}/stop")
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_404s_for_an_unknown_run_id(self) -> None:
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            response = await client.post(f"/v1/query/{uuid.uuid4()}/stop", headers=headers)
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_403s_for_a_different_users_run(self) -> None:
        async with _client() as client:
            _owner_id, owner_headers = await _auth_headers(client)
            run_id = await _create_run(client, owner_headers)
            await _drain_run_task(run_id)

            _other_id, other_headers = await _auth_headers(client)
            response = await client.post(f"/v1/query/{run_id}/stop", headers=other_headers)
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_stops_a_still_running_run_and_returns_200(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Monkeypatches run_registry_module.run_streaming directly with a
        fake generator that hangs after its first event (the same
        technique test_run_registry.py's own cancellation tests use), so
        cancel_run reliably catches the background task mid-flight rather
        than racing a fast real-graph completion."""
        started = asyncio.Event()

        async def _fake_stream_never_finishes(query: Query, context: RequestContext):
            yield _fake_event("guard", query.trace_id, 0)
            started.set()
            await asyncio.sleep(3600)
            yield _fake_event("done", query.trace_id, 1)  # pragma: no cover - unreachable

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream_never_finishes)

        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)
            entry = run_registry_module.default_registry.get_run(run_id)
            await asyncio.wait_for(started.wait(), timeout=5.0)

            response = await client.post(f"/v1/query/{run_id}/stop", headers=headers)

            assert response.status_code == 200
            assert response.json()["stopped"] is True

            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(entry.task, timeout=5.0)
            assert entry.task.cancelled()

    @pytest.mark.asyncio
    async def test_stopping_an_already_finished_run_is_idempotent_and_returns_200_both_times(
        self,
    ) -> None:
        """production-standards.md's retry-safety gate: a write the agent
        loop (or a client retry) may issue more than once must produce the
        same end state, never an error, on the second call."""
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)
            await _drain_run_task(run_id)

            first = await client.post(f"/v1/query/{run_id}/stop", headers=headers)
            second = await client.post(f"/v1/query/{run_id}/stop", headers=headers)

            assert first.status_code == 200
            assert first.json()["stopped"] is True
            assert second.status_code == 200
            assert second.json()["stopped"] is True


class TestAllowanceEndpoint:
    """`GET /v1/allowance` (T-4.10-04): valid, invalid, and null input for
    both principal classes. The guest admit/refuse shape and the exact
    used-increments-by-one property are the phase 4.10 premise gate's job
    (test_phase_4_10_premise.py); this class covers the input-validation
    surface T-1.2-02's established convention requires for every endpoint.
    """

    @pytest.mark.asyncio
    async def test_valid_input_registered_caller_reports_the_real_cap_uncounted(self) -> None:
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            response = await client.get("/v1/allowance", headers=headers)
            assert response.status_code == 200
            body = response.json()
            # Still an EXACT match. Build phase 4.10 design decision 8
            # added `blocked_reason`, so the expected value gains it
            # rather than the comparison being loosened to a subset
            # check: what makes this assertion worth having is that an
            # unexpected field fails it.
            assert body == {
                "kind": "user", "used": 0, "total": 100, "counted": False,
                "blocked_reason": None,
            }

    @pytest.mark.asyncio
    async def test_valid_input_guest_caller_reports_a_real_counted_allowance(self) -> None:
        async with _client() as client:
            guest = await client.post("/auth/guest")
            assert guest.status_code == 201
            headers = {"Authorization": f"Bearer {guest.json()['guest_token']}"}

            response = await client.get("/v1/allowance", headers=headers)
            assert response.status_code == 200
            # Still an EXACT match. Build phase 4.10 design decision 8
            # added `blocked_reason`, so the expected value gains it
            # rather than the comparison being loosened to a subset
            # check: what makes this assertion worth having is that an
            # unexpected field fails it.
            assert response.json() == {
                "kind": "guest", "used": 0, "total": 5, "counted": True,
                "blocked_reason": None,
            }

    @pytest.mark.asyncio
    async def test_invalid_input_a_tampered_token_returns_401(self) -> None:
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            tampered = headers["Authorization"][:-2] + "zz"
            response = await client.get("/v1/allowance", headers={"Authorization": tampered})
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_null_input_no_authorization_header_returns_401(self) -> None:
        async with _client() as client:
            response = await client.get("/v1/allowance")
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_a_migrated_guest_session_is_never_reported_as_a_live_allowance(
        self,
    ) -> None:
        """F-4.10-A-03 / F-4.10-J-07 (adversary and judge round 1).

        This endpoint used to read `runs_used` alone and never `revoked_at`,
        so a guest whose session had been migrated and revoked at signup was
        told `{"used": 2, "total": 5, "counted": true}` and then refused 401
        by the very next `POST /v1/query`. `counted: true` is design
        decision 6's honesty field: it means the number is a real,
        server-side measurement, and for a session that can no longer spend,
        no number is. This is not cosmetic; the five dots in the UI render
        exactly this number.

        The assertion is that the REPORTING path and the ENFORCEMENT path
        now give the same answer, checked by asking both.
        """
        async with _client() as client:
            guest = await client.post("/auth/guest")
            assert guest.status_code == 201
            guest_token = guest.json()["guest_token"]
            headers = {"Authorization": f"Bearer {guest_token}"}

            before = await client.get("/v1/allowance", headers=headers)
            assert before.status_code == 200, "a fresh guest must still be reported"

            email = f"{uuid.uuid4()}@example.com"
            signup = await client.post(
                "/auth/signup",
                json={
                    "email": email,
                    "password": "Str0ngPassw0rd!",
                    "guest_token": guest_token,
                },
            )
            assert signup.status_code == 201

            reported = await client.get("/v1/allowance", headers=headers)
            enforced = await client.post("/v1/query", json=_create_body(), headers=headers)

            assert enforced.status_code == 401, (
                "precondition: the migrated session must be unspendable, or this "
                "test is not exercising the disagreement it was written for"
            )
            assert reported.status_code == 401, (
                "the allowance endpoint promised searches the very next request "
                "refused; the two paths must agree on what a live session is"
            )

    @pytest.mark.asyncio
    async def test_an_unknown_guest_id_is_never_reported_as_five_searches_left(self) -> None:
        """F-4.10-A-03, the second measured shape: a validly signed guest
        token whose `guest_id` has no row at all was reported as
        `{"used": 0, "total": 5, "counted": true}`, literally "five of five
        left", and then refused on the first query."""
        import jwt

        from system_03_search_agent.auth.guest import guest_signing_key

        orphan = jwt.encode(
            {
                "guest_id": str(uuid.uuid4()),
                "typ": "guest",
                "iat": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(days=1),
            },
            guest_signing_key(),
            algorithm="HS256",
        )
        headers = {"Authorization": f"Bearer {orphan}"}
        async with _client() as client:
            reported = await client.get("/v1/allowance", headers=headers)
            enforced = await client.post("/v1/query", json=_create_body(), headers=headers)

            assert enforced.status_code == 401
            assert reported.status_code == 401, (
                "a guest id with no session row must not be advertised as a full, "
                "counted allowance"
            )


class TestConcurrentRunCap:
    """T-4.10-05: reproduces F-4.0-A-10's original shape (rapid repeated
    run creation from one caller, with nothing bounding it) and asserts
    creation is now bounded. F-4.0-A-10's own repro measured 9,615 runs
    accepted from one account with zero rejections; this test's cap is
    `RunRegistry.DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER` (5), several orders of
    magnitude tighter, and the assertion is exact: the cap fires at
    exactly that boundary, not merely "eventually rejects something".
    """

    @pytest.mark.asyncio
    async def test_rapid_repeated_run_creation_from_one_caller_is_now_bounded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from system_03_search_agent.core.run_registry import DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER

        started = asyncio.Event()

        async def _fake_stream_never_finishes(query: Query, context: RequestContext):
            # Every created run stays ACTIVE (never `finished`) for the
            # whole test, so count_active_runs_for_owner keeps counting
            # every one of them, the same "still in flight" shape F-4.0-
            # A-10's burst produced (its runs also outlived the burst
            # window; here that is forced rather than incidental).
            yield _fake_event("guard", query.trace_id, 0)
            started.set()
            await asyncio.sleep(3600)
            yield _fake_event("done", query.trace_id, 1)  # pragma: no cover - unreachable

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream_never_finishes)

        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            created_run_ids: list[str] = []

            for i in range(DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER):
                response = await client.post(
                    "/v1/query", json=_create_body(session_id=f"cap-{i}"), headers=headers
                )
                assert response.status_code == 202, (
                    f"run {i + 1} of {DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER} should still be "
                    "within the concurrent-run cap"
                )
                created_run_ids.append(response.json()["run_id"])

            over_cap = await client.post(
                "/v1/query", json=_create_body(session_id="cap-over"), headers=headers
            )
            assert over_cap.status_code == 429, (
                "F-4.0-A-10: rapid repeated run creation from one caller must "
                "now be bounded, not accepted unconditionally"
            )
            body = over_cap.json()
            assert "concurrent_run_cap_exceeded" in str(body)
            assert "Retry-After" in over_cap.headers

            # Cleanup: cancel every still-hanging background task so it does
            # not outlive this test process.
            for run_id in created_run_ids:
                run_registry_module.default_registry.get_run(run_id).task.cancel()

    @pytest.mark.asyncio
    async def test_a_completed_run_does_not_count_against_the_cap(self) -> None:
        """F-1.2-01's own fix ("how long", not "how many") and T-4.10-05's
        acceptance criterion composed: creating and finishing
        DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER + 1 runs one at a time (draining
        each before the next starts) must never hit the cap, since none
        of them are ever concurrently active."""
        from system_03_search_agent.core.run_registry import DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER

        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            for i in range(DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER + 3):
                response = await client.post(
                    "/v1/query", json=_create_body(session_id=f"seq-{i}"), headers=headers
                )
                assert response.status_code == 202
                await _drain_run_task(response.json()["run_id"])
