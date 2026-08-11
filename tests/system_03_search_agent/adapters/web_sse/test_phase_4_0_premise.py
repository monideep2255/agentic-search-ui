"""Phase 4.0 premise gate: `tracker/phase_4.0.md`.

The done-when this file pins: resumability (`Last-Event-ID` replay with no
gap and no duplicate), multi-consumer reads (F-1.2-03), eviction
(F-1.2-01), abandonment cancellation (F-1.2-02), the `/citations` export
endpoint, and `operator_mode` server-side derivation on the finalized
`/v1/query` family, plus confirmation that the legacy `POST /query`
endpoint is gone.

Not covered here, per `.claude/rules/goal-contracts.md`'s coverage-
declaration discipline (see `tracker/phase_4.0.md`'s own "Not covered by
this gate" note): session-cookie auth (out of scope, a documented spec-
versus-reality gap), true multi-process registry state, and load-scale
behavior under many concurrent runs (build phase 6.0's job).

Two fixture styles, matching the two things this phase changes:

    - `TestEviction` and `TestAbandonment` construct their own
      `RunRegistry()` directly with a fast-fake `run_streaming`
      (`test_run_registry.py`'s established pattern), since eviction and
      abandonment are registry-level behaviors with no HTTP surface of
      their own and no need for a real database.
    - Everything else drives the real FastAPI app over `httpx.AsyncClient`
      + `ASGITransport` (`test_streaming_endpoints.py`'s established
      pattern), since resumability, multi-consumer reads, the citations
      endpoint, and operator-mode derivation are all endpoint-level
      behavior. This half needs `search_agent_users` PostgreSQL reachable
      (real auth) and skips cleanly, not failing, when it is not.

Citation and error-termination arms use a monkeypatched `run_streaming`
fake rather than the real five-node graph: the real `cypher_query` tool
reaches the live Hetzner AGE graph over an SSH tunnel that cannot be
opened from a sandboxed coding session (the same environment constraint
`tracker/BOARD.md`'s T-3.0-07 and LEARNINGS.md's "Layer 1 read-only
access" entry already name), so a real run in this environment never
actually produces a `citation` event to test against. A controlled fake
is also the more correct test design for these two arms regardless: they
verify the export endpoint reads the buffered log correctly, not that a
particular NCBI query happens to return a citable result.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import UTC, datetime

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


from system_03_search_agent.contracts.events import Event
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.run_registry import RunNotFoundError, RunRegistry

_TEST_AUTH_SECRET = "test-only-auth-secret-for-phase-4-0-premise-tests-do-not-reuse"


def _valid_query(**overrides: object) -> Query:
    base: dict[str, object] = {
        "text": "What gene is BRCA1?",
        "session_id": "session-1",
        "trace_id": "trace-1",
        "user_id": None,
        "audience_depth": "researcher",
    }
    base.update(overrides)
    return Query(**base)


def _valid_context(**overrides: object) -> RequestContext:
    base: dict[str, object] = {"surface": "rest_sse", "session_memory": None, "operator_mode": False}
    base.update(overrides)
    return RequestContext(**base)


def _fake_event(event_type: str, trace_id: str, seq: int, **payload_overrides: object) -> Event:
    from system_03_search_agent.contracts.events import DonePayload, ErrorPayload, GuardPayload

    if event_type == "guard":
        payload = GuardPayload(passed=True, category="ok", reason=None)
    elif event_type == "done":
        payload = DonePayload(
            total_cost_usd=0.0,
            total_tool_calls=0,
            elapsed_ms=1,
            trust_outcome=payload_overrides.get("trust_outcome", "answer"),
        )
    elif event_type == "error":
        payload = ErrorPayload(
            fatal=payload_overrides.get("fatal", True),
            scope="run",
            source="test",
            error_class="unexpected",
            message="synthetic fatal error for a premise-gate test",
            retry_after_s=0,
        )
    else:  # pragma: no cover - only guard/done/error are used by these tests
        raise ValueError(event_type)
    return Event(
        type=event_type, version="v1", trace_id=trace_id, seq=seq, ts=datetime.now(UTC),
        payload=payload.model_dump(),
    )


def _fake_citation_event(trace_id: str, seq: int, *, citation_id: str) -> Event:
    from system_03_search_agent.contracts.events import CitationPayload

    payload = CitationPayload(
        citation_id=citation_id,
        display_index=seq,
        source="ncbi_gene",
        source_id="672",
        source_url="https://www.ncbi.nlm.nih.gov/gene/672",
        layer="layer_1_graph",
        field="symbol",
        claim_text="BRCA1 is a protein-coding gene.",
        evidence_kind="direct",
        assertion_confidence="high",
        population_ancestry_context=None,
        license="public-domain",
    )
    return Event(
        type="citation", version="v1", trace_id=trace_id, seq=seq, ts=datetime.now(UTC),
        payload=payload.model_dump(),
    )


class TestEviction:
    """F-1.2-01: a finished run's entry is dropped after `retention_seconds`."""

    @pytest.mark.asyncio
    async def test_a_finished_run_is_evicted_after_the_retention_window_and_reads_404(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from system_03_search_agent.core import run_registry as run_registry_module

        async def _fake_stream(query: Query, context: RequestContext):
            yield _fake_event("done", query.trace_id, 0)

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream)
        registry = RunRegistry(retention_seconds=0.05, abandon_grace_seconds=999.0)

        run_id = registry.create_run(_valid_query(), _valid_context())
        entry = registry.get_run(run_id)
        await asyncio.wait_for(entry.task, timeout=5.0)

        await asyncio.sleep(0.2)  # past the 0.05s retention window

        with pytest.raises(RunNotFoundError):
            registry.get_run(run_id)

    @pytest.mark.asyncio
    async def test_a_run_still_within_the_retention_window_is_not_evicted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from system_03_search_agent.core import run_registry as run_registry_module

        async def _fake_stream(query: Query, context: RequestContext):
            yield _fake_event("done", query.trace_id, 0)

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream)
        registry = RunRegistry(retention_seconds=999.0, abandon_grace_seconds=999.0)

        run_id = registry.create_run(_valid_query(), _valid_context())
        await asyncio.wait_for(registry.get_run(run_id).task, timeout=5.0)

        # Still retrievable well within the window.
        assert registry.get_run(run_id).run_id == run_id


class TestAbandonment:
    """F-1.2-02: a run nobody subscribes to (or nobody is still subscribed
    to) is cancelled after the grace window."""

    @pytest.mark.asyncio
    async def test_a_run_nobody_ever_subscribes_to_is_cancelled_after_the_grace_window(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from system_03_search_agent.core import run_registry as run_registry_module

        started = asyncio.Event()

        async def _fake_stream_never_finishes(query: Query, context: RequestContext):
            yield _fake_event("guard", query.trace_id, 0)
            started.set()
            await asyncio.sleep(3600)
            yield _fake_event("done", query.trace_id, 1)  # pragma: no cover - unreachable

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream_never_finishes)
        registry = RunRegistry(retention_seconds=999.0, abandon_grace_seconds=0.05)

        run_id = registry.create_run(_valid_query(), _valid_context())
        entry = registry.get_run(run_id)
        await asyncio.wait_for(started.wait(), timeout=5.0)

        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(entry.task, timeout=5.0)
        assert entry.task.cancelled()

    @pytest.mark.asyncio
    async def test_a_run_a_subscriber_dropped_from_is_cancelled_after_the_grace_window(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from system_03_search_agent.core import run_registry as run_registry_module

        started = asyncio.Event()

        async def _fake_stream_never_finishes(query: Query, context: RequestContext):
            yield _fake_event("guard", query.trace_id, 0)
            started.set()
            await asyncio.sleep(3600)
            yield _fake_event("done", query.trace_id, 1)  # pragma: no cover - unreachable

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream_never_finishes)
        registry = RunRegistry(retention_seconds=999.0, abandon_grace_seconds=0.05)

        run_id = registry.create_run(_valid_query(), _valid_context())
        await asyncio.wait_for(started.wait(), timeout=5.0)

        # Attach and immediately drop a subscriber (reads exactly one event,
        # then stops iterating, simulating a dropped connection).
        subscriber = registry.subscribe(run_id, after_seq=-1)
        first = await anext(subscriber)
        assert first.type == "guard"
        await subscriber.aclose()

        entry = registry.get_run(run_id)
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(entry.task, timeout=5.0)
        assert entry.task.cancelled()

    @pytest.mark.asyncio
    async def test_a_new_subscriber_before_the_grace_window_elapses_prevents_cancellation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from system_03_search_agent.core import run_registry as run_registry_module

        async def _fake_stream(query: Query, context: RequestContext):
            yield _fake_event("guard", query.trace_id, 0)
            yield _fake_event("done", query.trace_id, 1)

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream)
        registry = RunRegistry(retention_seconds=999.0, abandon_grace_seconds=0.2)

        run_id = registry.create_run(_valid_query(), _valid_context())

        # Attach before the 0.2s grace window (started at create_run) elapses.
        events = [event async for event in registry.subscribe(run_id, after_seq=-1)]
        assert [event.type for event in events] == ["guard", "done"]

        await asyncio.sleep(0.3)  # past the original grace window
        entry = registry.get_run(run_id)
        assert not entry.task.cancelled()
        assert entry.task.done()  # finished normally, not cancelled

    @pytest.mark.asyncio
    async def test_rapid_churn_does_not_hold_a_run_alive_past_cumulative_grace_time(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-4.0-A-01 (adversary round 1, build phase 4.0): the original
        version of `_reschedule_abandonment_check` scheduled a brand new
        full-length grace window on every subscribe/unsubscribe, so a
        reconnect cadence shorter than the grace window (attach,
        immediately detach, repeat, never consuming an event) reset the
        clock every time and held the run alive indefinitely, defeating
        F-1.2-02's entire purpose. The fix tracks cumulative real
        unwatched time across every interval instead of resetting it, so
        churn no longer bypasses the check."""
        from system_03_search_agent.core import run_registry as run_registry_module

        started = asyncio.Event()

        async def _fake_stream_never_finishes(query: Query, context: RequestContext):
            yield _fake_event("guard", query.trace_id, 0)
            started.set()
            await asyncio.sleep(3600)
            yield _fake_event("done", query.trace_id, 1)  # pragma: no cover - unreachable

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream_never_finishes)
        registry = RunRegistry(retention_seconds=999.0, abandon_grace_seconds=0.3)

        run_id = registry.create_run(_valid_query(), _valid_context())
        await asyncio.wait_for(started.wait(), timeout=5.0)

        # Churn: attach and immediately detach every 0.15s, well under the
        # 0.3s grace window, never consuming more than the one already-
        # buffered event. A naive full-reset timer would survive this
        # forever; the cumulative-time fix should not.
        for _ in range(12):
            if registry.get_run(run_id).task.done():
                break
            subscriber = registry.subscribe(run_id, after_seq=-1)
            await anext(subscriber)
            await subscriber.aclose()
            await asyncio.sleep(0.15)

        entry = registry.get_run(run_id)
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(entry.task, timeout=5.0)
        assert entry.task.cancelled()


if not _can_connect():
    pytest.skip(
        "search_agent_users PostgreSQL database is not reachable; "
        "set USER_DB_URL and ensure the server is running to run the HTTP-level "
        "half of the phase 4.0 premise gate (resumability, multi-consumer, "
        "citations, operator-mode derivation, legacy endpoint removal)",
        allow_module_level=True,
    )

from system_03_search_agent.adapters.web_sse.app import app
from system_03_search_agent.core import run_registry as run_registry_module
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import harness as harness_module


@pytest.fixture(autouse=True)
def _harness_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("PER_USER_DAILY_QUERY_CAP", "100")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")


@pytest.fixture(autouse=True)
def _mock_litellm(monkeypatch: pytest.MonkeyPatch):
    from tests.system_03_search_agent.model_stub import install_dispatching_acompletion

    return install_dispatching_acompletion(monkeypatch, harness_module)


@pytest.fixture(autouse=True)
def _stub_symbol_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    from system_03_search_agent.core import graph as graph_module

    known = {"BRCA1": "NCBIGene:672", "TP53": "NCBIGene:7157"}

    async def _fake_resolve_symbol_to_curie(symbol: str, **kwargs: object) -> str | None:
        return known.get(symbol.strip().upper())

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _fake_resolve_symbol_to_curie)


@pytest.fixture(autouse=True)
def _stub_ncbi_efetch_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    from system_03_search_agent.core import graph as graph_module
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput

    async def _fake_ncbi_efetch(tool_input: object, **kwargs: object) -> NcbiEfetchOutput:
        return NcbiEfetchOutput(
            status="empty", action="dataset_report", records=[], record_count=0,
            total_available=None, truncated=False, error=None,
        )

    monkeypatch.setattr(graph_module, "ncbi_efetch", _fake_ncbi_efetch)


@pytest.fixture(autouse=True)
def _no_op_daily_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cost_control, "check_user_daily_query_cap", lambda session, user_id, **kw: None)
    monkeypatch.setattr(cost_control, "check_system_daily_cost_cap", lambda session, **kw: None)


@pytest.fixture(autouse=True)
def _auth_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_SECRET", _TEST_AUTH_SECRET)


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _unique_email() -> str:
    return f"{uuid.uuid4()}@example.com"


async def _auth_headers(client: AsyncClient) -> tuple[str, dict[str, str]]:
    email, password = _unique_email(), "Str0ngPassw0rd!"
    signup = await client.post("/auth/signup", json={"email": email, "password": password})
    assert signup.status_code == 201
    user_id = signup.json()["id"]
    login = await client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return user_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


def _create_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {"text": "What gene is BRCA1?", "session_id": "session-1"}
    body.update(overrides)
    return body


async def _create_run(client: AsyncClient, headers: dict[str, str]) -> str:
    response = await client.post("/v1/query", json=_create_body(), headers=headers)
    assert response.status_code == 202
    return response.json()["run_id"]


async def _drain_run_task(run_id: str) -> None:
    entry = run_registry_module.default_registry.get_run(run_id)
    await asyncio.wait_for(entry.task, timeout=5.0)


def _parse_sse_frames(raw_text: str) -> list[dict[str, str]]:
    frames: list[dict[str, str]] = []
    for block in raw_text.replace("\r\n", "\n").split("\n\n"):
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


class TestResumability:
    """Section 13.1: `Last-Event-ID` replays everything past it, no gap, no
    duplicate."""

    @pytest.mark.asyncio
    async def test_reconnecting_with_last_event_id_replays_only_what_was_missed(self) -> None:
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)
            await _drain_run_task(run_id)

            first = await client.get(f"/v1/query/{run_id}/events", headers=headers)
            first_events = [json.loads(f["data"]) for f in _parse_sse_frames(first.text)]
            assert len(first_events) >= 2
            cutoff_seq = first_events[0]["seq"]

            second = await client.get(
                f"/v1/query/{run_id}/events",
                headers={**headers, "Last-Event-ID": str(cutoff_seq)},
            )
            second_events = [json.loads(f["data"]) for f in _parse_sse_frames(second.text)]

            assert all(e["seq"] > cutoff_seq for e in second_events)
            expected = [e["seq"] for e in first_events if e["seq"] > cutoff_seq]
            assert [e["seq"] for e in second_events] == expected

    @pytest.mark.asyncio
    async def test_reconnect_also_receives_events_that_arrived_after_the_previous_reader_left(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Proves buffered replay covers events that arrived after a
        previous subscriber detached, not only a snapshot taken at detach
        time. Detaches via `RunRegistry.subscribe` directly (`.aclose()`)
        rather than abandoning a real HTTP stream mid-flight: an httpx
        `client.stream()` response left partially read over `ASGITransport`
        does not reliably signal the server-side task to unwind on
        `__aexit__`, which hung this test outright when tried (see
        LEARNINGS.md's 2026-08-10 phase 4.0 entry). The registry-level
        detach below is deterministic and exercises the exact same
        buffered-replay code path `GET /events` itself calls."""
        release = asyncio.Event()

        async def _fake_stream(query: Query, context: RequestContext):
            yield _fake_event("guard", query.trace_id, 0)
            await release.wait()
            yield _fake_event("done", query.trace_id, 1)

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream)

        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)

            subscriber = run_registry_module.default_registry.subscribe(run_id, after_seq=-1)
            first = await anext(subscriber)
            assert first.type == "guard"
            await subscriber.aclose()  # detach while the run is still mid-flight

            release.set()  # the run produces its remaining event with nobody watching
            await _drain_run_task(run_id)

            # F-4.0-A-02/A-03 fix round: `Last-Event-ID` must now be the
            # strict digit grammar `seq` actually is (`ge=0`), so the
            # literal string "-1" (previously honored only as a side
            # effect of lenient `int()` parsing) is correctly rejected.
            # Omitting the header is the real, spec-shaped way a client
            # asks for a full replay.
            reconnected = await client.get(f"/v1/query/{run_id}/events", headers=headers)
            events = [json.loads(f["data"]) for f in _parse_sse_frames(reconnected.text)]
            assert [e["type"] for e in events] == ["guard", "done"]

    @pytest.mark.asyncio
    async def test_every_frame_carries_a_wire_id_line_matching_its_own_seq(self) -> None:
        """F-4.0-J-01 (judge review, build phase 4.0): the earlier version
        of this gate proved resumability only by reading `seq` out of the
        JSON body and hand-building the `Last-Event-ID` header from it, the
        exact workaround the judge's wire capture showed was necessary
        because no frame carried a real `id:` line. A standards-conforming
        SSE client (a native `EventSource`, or any off-the-shelf library) has
        no channel but `id:` for `Last-Event-ID`, so this arm pins the wire
        field directly rather than the payload."""
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)
            await _drain_run_task(run_id)

            response = await client.get(f"/v1/query/{run_id}/events", headers=headers)
            frames = _parse_sse_frames(response.text)
            assert len(frames) >= 2
            for frame in frames:
                assert "id" in frame, f"frame missing wire id: line: {frame}"
                assert frame["id"] == str(json.loads(frame["data"])["seq"])

    @pytest.mark.asyncio
    async def test_reconnecting_using_only_the_wire_id_line_yields_zero_duplicates(self) -> None:
        """F-4.0-J-01: the judge's own repro, ported into the gate. A
        reconnect driven exclusively by the wire `id:` line (never the JSON
        body's `seq`, which a real `EventSource`-based client cannot read)
        must deliver exactly what a resuming client is missing: everything
        past its cutoff, once each, no gap, no duplicate."""
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)
            await _drain_run_task(run_id)

            first = await client.get(f"/v1/query/{run_id}/events", headers=headers)
            first_frames = _parse_sse_frames(first.text)
            assert len(first_frames) >= 2
            # Cut off after the FIRST frame, not the last, so the reconnect
            # below has real remaining events to replay: a trivial "connect
            # after everything already happened" cutoff would pass on an
            # empty response even with the bug this arm exists to catch.
            cutoff_wire_id = first_frames[0]["id"]

            second = await client.get(
                f"/v1/query/{run_id}/events",
                headers={**headers, "Last-Event-ID": cutoff_wire_id},
            )
            second_frames = _parse_sse_frames(second.text)
            assert second_frames, "reconnect past the first frame returned nothing to replay"

            # `first_frames` is a full, undisconnected read (httpx's `.get()`
            # drains the whole response), not a client that actually stopped
            # partway through, so comparing its full id set against the
            # reconnect's id set for ANY overlap is the wrong check: the
            # reconnect is legitimately expected to reproduce most of what
            # `first` already contains, since `first` saw everything. The
            # property that actually matters is exact: everything strictly
            # after the cutoff, once each, no gap and no duplicate relative
            # to that resume point (the same shape
            # `test_reconnecting_with_last_event_id_replays_only_what_was_missed`
            # already proves using the JSON body's `seq`; this is that same
            # proof driven by the wire `id:` line instead).
            first_ids = {f["id"] for f in first_frames}
            second_ids = {f["id"] for f in second_frames}
            assert second_ids == first_ids - {cutoff_wire_id}

    @pytest.mark.asyncio
    async def test_a_last_event_id_beyond_this_runs_highest_seq_is_rejected_with_400(
        self,
    ) -> None:
        """F-4.0-J-03 (judge review, build phase 4.0): a `Last-Event-ID`
        claiming to have already seen a `seq` this run has not produced yet
        cannot be a genuine client cursor. Before the fix, such a value
        still counted toward `subscriber_count`, silently defeating
        F-1.2-02's abandonment check for a subscriber that could never be
        served."""
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)
            await _drain_run_task(run_id)

            response = await client.get(
                f"/v1/query/{run_id}/events",
                headers={**headers, "Last-Event-ID": "999999"},
            )
            assert response.status_code == 400
            assert "exceeds" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_a_malformed_last_event_id_is_rejected_not_silently_full_replayed(
        self,
    ) -> None:
        """F-4.0-A-02/A-03 (adversary round 1, build phase 4.0): a
        present-but-malformed cursor used to fall back to the same
        full-replay default as a genuinely absent header, silently
        producing exactly the duplicate delivery the phase premise
        forbids ("never a gap, never a duplicate"). Every shape below is
        a cursor this run cannot honor and must be rejected the same way
        an out-of-range one already is, never silently reinterpreted as
        "start over"."""
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)
            await _drain_run_task(run_id)

            malformed_cursors = [
                "1_0",  # PEP 515 underscore separator, int() accepts it
                "+3",  # explicit sign
                "-1",  # negative, even though it is subscribe()'s own sentinel
                "0x3",  # hex
                "3.0",  # float
                "inf",
                "nan",
                "",  # empty but present (distinct from an absent header)
                "abc",
            ]
            for malformed in malformed_cursors:
                response = await client.get(
                    f"/v1/query/{run_id}/events",
                    headers={**headers, "Last-Event-ID": malformed},
                )
                assert response.status_code == 400, (
                    f"Last-Event-ID={malformed!r} should be rejected 400, "
                    f"got {response.status_code}: {response.text}"
                )

            # Confirm the one legitimate case still works: a genuinely
            # ABSENT header (not a malformed present one) is a real full
            # replay, not an error.
            fresh_headers = dict(headers)
            fresh_headers.pop("Last-Event-ID", None)
            response = await client.get(f"/v1/query/{run_id}/events", headers=fresh_headers)
            assert response.status_code == 200


class TestMultiConsumer:
    """F-1.2-03: two independent readers of the same run each get the full
    stream, not zero events for the second."""

    @pytest.mark.asyncio
    async def test_two_concurrent_readers_of_the_same_run_each_see_the_complete_stream(
        self,
    ) -> None:
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)

            first_response, second_response = await asyncio.gather(
                client.get(f"/v1/query/{run_id}/events", headers=headers),
                client.get(f"/v1/query/{run_id}/events", headers=headers),
            )

            first_types = [f["event"] for f in _parse_sse_frames(first_response.text)]
            second_types = [f["event"] for f in _parse_sse_frames(second_response.text)]

            assert len(first_types) > 0
            assert first_types[-1] == "done"
            assert len(second_types) > 0
            assert second_types[-1] == "done"


class TestCitationsEndpoint:
    @pytest.mark.asyncio
    async def test_returns_every_citation_for_a_run_that_reached_done(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _fake_stream(query: Query, context: RequestContext):
            yield _fake_event("guard", query.trace_id, 0)
            yield _fake_citation_event(query.trace_id, 1, citation_id="c1")
            yield _fake_citation_event(query.trace_id, 2, citation_id="c2")
            yield _fake_event("done", query.trace_id, 3)

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream)

        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)
            await _drain_run_task(run_id)

            response = await client.get(f"/v1/query/{run_id}/citations", headers=headers)

            assert response.status_code == 200
            citation_ids = {c["citation_id"] for c in response.json()}
            assert citation_ids == {"c1", "c2"}

    @pytest.mark.asyncio
    async def test_a_run_that_finished_via_a_fatal_error_is_also_a_terminal_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _fake_stream(query: Query, context: RequestContext):
            yield _fake_event("guard", query.trace_id, 0)
            yield _fake_event("error", query.trace_id, 1, fatal=True)

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream)

        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)
            await _drain_run_task(run_id)

            response = await client.get(f"/v1/query/{run_id}/citations", headers=headers)
            assert response.status_code == 200
            assert response.json() == []

    @pytest.mark.asyncio
    async def test_409s_with_an_actionable_message_for_a_run_still_in_flight(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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

            response = await client.get(f"/v1/query/{run_id}/citations", headers=headers)

            assert response.status_code == 409
            detail = response.json()["detail"].lower()
            # F-4.0-A-06 fix round: reworded so the message never names
            # "the done event" as the only way a run ends, since a
            # stopped or abandonment-cancelled run does not emit one
            # (F-4.0-A-04). "terminal state" replaces "not finished".
            assert "terminal state" in detail or "not complete" in detail
            assert "done" in detail or "events" in detail  # names what to do next

            run_registry_module.default_registry.cancel_run(run_id)
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(entry.task, timeout=5.0)

    @pytest.mark.asyncio
    async def test_404s_for_an_unknown_run_id(self) -> None:
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            response = await client.get(f"/v1/query/{uuid.uuid4()}/citations", headers=headers)
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_403s_for_a_different_users_run(self) -> None:
        async with _client() as client:
            _owner_id, owner_headers = await _auth_headers(client)
            run_id = await _create_run(client, owner_headers)
            await _drain_run_task(run_id)

            _other_id, other_headers = await _auth_headers(client)
            response = await client.get(f"/v1/query/{run_id}/citations", headers=other_headers)
            assert response.status_code == 403


class TestCancellationTerminalState:
    """F-4.0-A-04/A-05 (adversary round 1, build phase 4.0): a stopped run
    used to end its SSE stream with no terminal event at all, and its
    citations export was silently indistinguishable from a genuinely
    empty one. Both are now disclosed."""

    @pytest.mark.asyncio
    async def test_a_stopped_run_emits_a_real_terminal_event_not_silence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
            await asyncio.wait_for(started.wait(), timeout=5.0)

            stop_response = await client.post(f"/v1/query/{run_id}/stop", headers=headers)
            assert stop_response.status_code == 200

            entry = run_registry_module.default_registry.get_run(run_id)
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(entry.task, timeout=5.0)

            events_response = await client.get(f"/v1/query/{run_id}/events", headers=headers)
            events = [json.loads(f["data"]) for f in _parse_sse_frames(events_response.text)]
            assert events, "a cancelled run's replay must not be empty"
            terminal = events[-1]
            assert terminal["type"] == "error"
            assert terminal["payload"]["fatal"] is True
            assert terminal["payload"]["error_class"] == "cancelled"

    @pytest.mark.asyncio
    async def test_citations_export_discloses_cancellation_via_response_header(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
            await asyncio.wait_for(started.wait(), timeout=5.0)

            await client.post(f"/v1/query/{run_id}/stop", headers=headers)
            entry = run_registry_module.default_registry.get_run(run_id)
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(entry.task, timeout=5.0)

            response = await client.get(f"/v1/query/{run_id}/citations", headers=headers)
            assert response.status_code == 200
            assert response.json() == []
            assert response.headers.get("X-Run-Cancelled") == "true"


class TestOperatorModeServerDerivation:
    """Section 19.4/19.5: operator visibility on the finalized streaming
    path is derived purely from the authenticated caller's allowlist
    membership, never from anything in the request."""

    @pytest.mark.asyncio
    async def test_an_operator_allowlisted_caller_sees_cost_events_and_the_real_total(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with _client() as client:
            user_id, headers = await _auth_headers(client)
            monkeypatch.setenv("OPERATOR_USER_IDS", user_id)

            run_id = await _create_run(client, headers)
            response = await client.get(f"/v1/query/{run_id}/events", headers=headers)
            frames = _parse_sse_frames(response.text)

            event_types = [f["event"] for f in frames]
            assert "cost" in event_types
            done_event = json.loads(next(f["data"] for f in frames if f["event"] == "done"))
            assert done_event["payload"]["total_cost_usd"] > 0.0

    @pytest.mark.asyncio
    async def test_a_non_allowlisted_caller_never_sees_cost_regardless_of_the_allowlist_being_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            # A real operator allowlist exists, just not for this caller:
            # proves the check is per-caller, not "an allowlist is configured
            # at all".
            monkeypatch.setenv("OPERATOR_USER_IDS", str(uuid.uuid4()))

            run_id = await _create_run(client, headers)
            response = await client.get(f"/v1/query/{run_id}/events", headers=headers)
            frames = _parse_sse_frames(response.text)

            assert all(f["event"] != "cost" for f in frames)
            done_event = json.loads(next(f["data"] for f in frames if f["event"] == "done"))
            assert done_event["payload"]["total_cost_usd"] == 0.0

    @pytest.mark.asyncio
    async def test_the_allowlist_is_per_user_not_all_or_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ported from the retired test_query_endpoint.py's
        TestPostQueryOperatorMode: two authenticated users, only one on the
        allowlist, must not both see the same visibility."""
        async with _client() as client:
            operator_id, operator_headers = await _auth_headers(client)
            monkeypatch.setenv("OPERATOR_USER_IDS", operator_id)
            _other_id, other_headers = await _auth_headers(client)

            operator_run_id = await _create_run(client, operator_headers)
            other_run_id = await _create_run(client, other_headers)

            operator_response = await client.get(
                f"/v1/query/{operator_run_id}/events", headers=operator_headers
            )
            other_response = await client.get(
                f"/v1/query/{other_run_id}/events", headers=other_headers
            )

            operator_types = [f["event"] for f in _parse_sse_frames(operator_response.text)]
            other_types = [f["event"] for f in _parse_sse_frames(other_response.text)]
            assert "cost" in operator_types
            assert "cost" not in other_types


class TestEventEnvelopeVersion:
    """Ported from the retired test_query_endpoint.py: not previously
    asserted anywhere against the `/v1/query` family."""

    @pytest.mark.asyncio
    async def test_every_event_declares_v1_version(self) -> None:
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)

            response = await client.get(f"/v1/query/{run_id}/events", headers=headers)
            events = [json.loads(f["data"]) for f in _parse_sse_frames(response.text)]

            assert len(events) > 0
            assert all(event["version"] == "v1" for event in events)


class TestLegacyQueryEndpointRemoved:
    @pytest.mark.asyncio
    async def test_post_query_no_longer_exists(self) -> None:
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            response = await client.post(
                "/query",
                json={
                    "query": {
                        "text": "What gene is BRCA1?", "session_id": "session-1",
                        "trace_id": "trace-1", "user_id": None, "audience_depth": "researcher",
                    },
                    "context": {"surface": "web_ui", "session_memory": None, "operator_mode": False},
                },
                headers=headers,
            )
            assert response.status_code == 404


class TestCorsExposedHeaders:
    """F-4.0-J3-01 (judge round 3, build phase 4.0): `allow_headers`
    governs what a browser may SEND; `expose_headers` is the separate
    control for what it may READ back off the response. Without it, a
    browser JS client cannot see the citations endpoint's disclosure
    headers at all, which would silently defeat F-4.0-A-05/A-13's fixes
    for exactly the audience (a future frontend consumer) they exist for.
    """

    @pytest.mark.asyncio
    async def test_citation_disclosure_headers_are_exposed_to_browser_clients(
        self,
    ) -> None:
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            run_id = await _create_run(client, headers)
            await _drain_run_task(run_id)

            # `Access-Control-Expose-Headers` is a SIMPLE-request response
            # header, not a preflight one: Starlette's `CORSMiddleware`
            # only adds it to the actual response, so this is a real GET
            # with `Origin` set, not an `OPTIONS` preflight.
            response = await client.get(
                f"/v1/query/{run_id}/citations",
                headers={**headers, "Origin": "http://localhost:5173"},
            )
            assert response.status_code == 200
            exposed = response.headers.get("access-control-expose-headers", "")
            assert "X-Run-Cancelled" in exposed
            assert "X-Citations-Export-Truncated" in exposed
