"""Tests for `core.run_registry` (T-1.2-01).

Most tests here monkeypatch `run_registry.run_streaming` with a small,
fully-controlled fake async generator, so they exercise exactly the
registry's own logic (run creation, queue draining, lookup, cancellation,
ownership tracking) without also depending on the full guardrail-think-
plan-act-write graph or a mocked LiteLLM call. One test at the end
(`TestRunRegistryEndToEndWithTheRealGraph`) wires a real `RunRegistry` to
the real `run_streaming()`, with `litellm.acompletion`/`get_model_info`
monkeypatched the same way `test_run.py`/`test_graph.py` do, to prove the
registry is actually wired to the real streaming entry point and not just
internally consistent with its own fake.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.contracts.events import DonePayload, Event, GuardPayload
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import run_registry as run_registry_module
from system_03_search_agent.core.run_registry import RunEntry, RunNotFoundError, RunRegistry
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import harness as harness_module


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
    base: dict[str, object] = {
        "surface": "web_ui",
        "session_memory": None,
        "operator_mode": False,
    }
    base.update(overrides)
    return RequestContext(**base)


def _fake_event(event_type: str, trace_id: str, seq: int) -> Event:
    if event_type == "guard":
        payload = GuardPayload(passed=True, category="ok", reason=None)
    elif event_type == "done":
        payload = DonePayload(
            total_cost_usd=0.0, total_tool_calls=0, elapsed_ms=1, trust_outcome="answer"
        )
    else:  # pragma: no cover - only "guard"/"done" are used by these tests
        raise ValueError(event_type)
    return Event(
        type=event_type,
        version="v1",
        trace_id=trace_id,
        seq=seq,
        ts=datetime.now(UTC),
        payload=payload.model_dump(),
    )


async def _drain_until_sentinel(queue: asyncio.Queue[Event | None]) -> list[Event]:
    events: list[Event] = []
    while True:
        item = await asyncio.wait_for(queue.get(), timeout=5.0)
        if item is None:
            return events
        events.append(item)


class TestRunRegistryCreateRun:
    @pytest.mark.asyncio
    async def test_create_run_returns_a_string_run_id_shaped_like_a_uuid4(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _fake_stream(query: Query, context: RequestContext):
            yield _fake_event("guard", query.trace_id, 0)
            yield _fake_event("done", query.trace_id, 1)

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream)
        registry = RunRegistry()

        run_id = registry.create_run(_valid_query(), _valid_context())

        assert isinstance(run_id, str)
        import uuid

        parsed = uuid.UUID(run_id)  # raises ValueError if not a well-formed UUID
        assert str(parsed) == run_id
        await _drain_until_sentinel(registry.get_run(run_id).queue)

    @pytest.mark.asyncio
    async def test_background_task_pushes_every_event_then_a_none_sentinel(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _fake_stream(query: Query, context: RequestContext):
            yield _fake_event("guard", query.trace_id, 0)
            yield _fake_event("done", query.trace_id, 1)

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream)
        registry = RunRegistry()

        run_id = registry.create_run(_valid_query(trace_id="trace-registry"), _valid_context())
        entry = registry.get_run(run_id)

        events = await _drain_until_sentinel(entry.queue)

        assert [event.type for event in events] == ["guard", "done"]
        assert all(event.trace_id == "trace-registry" for event in events)
        # The task itself finishes shortly after the sentinel is queued;
        # give it one scheduling tick and confirm it actually completed
        # rather than hanging.
        await asyncio.wait_for(entry.task, timeout=5.0)
        assert entry.task.done()

    @pytest.mark.asyncio
    async def test_ownership_is_recorded_from_query_user_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _fake_stream(query: Query, context: RequestContext):
            yield _fake_event("done", query.trace_id, 0)

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream)
        registry = RunRegistry()

        owned_run_id = registry.create_run(
            _valid_query(user_id="11111111-1111-1111-1111-111111111111"), _valid_context()
        )
        anonymous_run_id = registry.create_run(_valid_query(user_id=None), _valid_context())

        assert (
            registry.get_run(owned_run_id).user_id
            == "11111111-1111-1111-1111-111111111111"
        )
        assert registry.get_run(anonymous_run_id).user_id is None

        await _drain_until_sentinel(registry.get_run(owned_run_id).queue)
        await _drain_until_sentinel(registry.get_run(anonymous_run_id).queue)


class TestRunRegistryGetRun:
    @pytest.mark.asyncio
    async def test_get_run_returns_a_run_entry_with_the_expected_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _fake_stream(query: Query, context: RequestContext):
            yield _fake_event("done", query.trace_id, 0)

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream)
        registry = RunRegistry()

        run_id = registry.create_run(_valid_query(), _valid_context())
        entry = registry.get_run(run_id)

        assert isinstance(entry, RunEntry)
        assert entry.run_id == run_id
        assert isinstance(entry.queue, asyncio.Queue)
        assert isinstance(entry.task, asyncio.Task)

        await _drain_until_sentinel(entry.queue)

    def test_get_run_raises_run_not_found_error_for_an_unknown_id(self) -> None:
        registry = RunRegistry()

        with pytest.raises(RunNotFoundError):
            registry.get_run("does-not-exist")

    def test_run_not_found_error_is_a_key_error(self) -> None:
        assert issubclass(RunNotFoundError, KeyError)


class TestRunRegistryCancelRun:
    @pytest.mark.asyncio
    async def test_cancel_run_cancels_a_still_running_background_task(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        started = asyncio.Event()

        async def _fake_stream_never_finishes(query: Query, context: RequestContext):
            yield _fake_event("guard", query.trace_id, 0)
            started.set()
            await asyncio.sleep(3600)
            yield _fake_event("done", query.trace_id, 1)  # pragma: no cover - unreachable

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream_never_finishes)
        registry = RunRegistry()

        run_id = registry.create_run(_valid_query(), _valid_context())
        entry = registry.get_run(run_id)
        await asyncio.wait_for(started.wait(), timeout=5.0)

        registry.cancel_run(run_id)

        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(entry.task, timeout=5.0)
        assert entry.task.cancelled()

    @pytest.mark.asyncio
    async def test_cancel_run_on_an_already_finished_run_does_not_raise(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _fake_stream(query: Query, context: RequestContext):
            yield _fake_event("guard", query.trace_id, 0)
            yield _fake_event("done", query.trace_id, 1)

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream)
        registry = RunRegistry()

        run_id = registry.create_run(_valid_query(), _valid_context())
        entry = registry.get_run(run_id)
        await _drain_until_sentinel(entry.queue)
        await asyncio.wait_for(entry.task, timeout=5.0)
        assert entry.task.done()

        registry.cancel_run(run_id)  # must not raise (production-standards.md retry-safety gate)

    @pytest.mark.asyncio
    async def test_cancel_run_called_twice_is_idempotent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        started = asyncio.Event()

        async def _fake_stream_never_finishes(query: Query, context: RequestContext):
            started.set()
            await asyncio.sleep(3600)
            yield _fake_event("done", query.trace_id, 0)  # pragma: no cover - unreachable

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream_never_finishes)
        registry = RunRegistry()

        run_id = registry.create_run(_valid_query(), _valid_context())
        await asyncio.wait_for(started.wait(), timeout=5.0)

        registry.cancel_run(run_id)
        entry = registry.get_run(run_id)
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(entry.task, timeout=5.0)

        registry.cancel_run(run_id)  # second call, already cancelled: must not raise

    def test_cancel_run_on_an_unknown_run_id_raises_run_not_found_error(self) -> None:
        registry = RunRegistry()

        with pytest.raises(RunNotFoundError):
            registry.cancel_run("does-not-exist")


class TestRunRegistryEndToEndWithTheRealGraph:
    """Wires a real `RunRegistry` to the real `run_streaming()` (not the
    fake used everywhere else in this file), with only `litellm` mocked,
    the same pattern `test_run.py`/`test_graph.py` use. Proves the
    registry is actually wired to the real streaming entry point."""

    @pytest.fixture(autouse=True)
    def _env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
        monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
        monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
        monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
        monkeypatch.setenv("PER_USER_DAILY_QUERY_CAP", "100")
        monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")
        monkeypatch.setenv("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")

    @pytest.fixture(autouse=True)
    def _no_op_daily_caps(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _user_check(session, user_id, **kwargs):
            return None

        def _system_check(session, **kwargs):
            return None

        monkeypatch.setattr(cost_control, "check_user_daily_query_cap", _user_check)
        monkeypatch.setattr(cost_control, "check_system_daily_cost_cap", _system_check)

    @pytest.fixture(autouse=True)
    def _mock_litellm(self, monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
        def _fake_response(content: str = "ok") -> SimpleNamespace:
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
            )

        mock_acompletion = AsyncMock(return_value=_fake_response())
        monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)
        monkeypatch.setattr(
            harness_module.litellm,
            "get_model_info",
            lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
        )
        return mock_acompletion

    @pytest.mark.asyncio
    async def test_create_run_drains_the_real_five_node_loop_to_a_terminal_done_event(
        self,
    ) -> None:
        registry = RunRegistry()

        run_id = registry.create_run(_valid_query(trace_id="trace-e2e"), _valid_context())
        entry = registry.get_run(run_id)

        events = await _drain_until_sentinel(entry.queue)

        assert len(events) > 0
        assert all(isinstance(event, Event) for event in events)
        assert events[-1].type == "done"
        assert all(event.trace_id == "trace-e2e" for event in events)
        await asyncio.wait_for(entry.task, timeout=5.0)


class TestReassignOwnerOffTheEventLoop:
    """F-4.10-J-03 (judge round 1, build phase 4.10).

    `reassign_owner` is the only `_runs` walker that does NOT run on the
    event loop thread: its only caller, `auth/router.py`'s
    `_migrate_guest_session`, is reached from `POST /auth/signup` and
    `POST /auth/login`, which are plain `def` path operations and so run
    on an AnyIO worker thread while `create_run` keeps inserting from the
    loop. That broke the no-lock invariant this module's docstring
    asserted, and an unguarded `for entry in self._runs.values()` raised
    `RuntimeError: dictionary changed size during iteration` in the
    window.

    Nothing anywhere asserted that invariant still held, which is why the
    break was invisible. This does.
    """

    @staticmethod
    def _bare_entry(run_id: str, owner_id: str) -> RunEntry:
        """A `RunEntry` with no live task or loop behind it.

        This test is about dict iteration, not about running a run, and
        building a real background task would need an event loop that
        would then also have to be shared across the two threads below,
        which is the very thing under test.
        """
        return RunEntry(
            run_id=run_id,
            user_id=None,
            owner_id=owner_id,
            queue=asyncio.Queue(),
            task=None,  # type: ignore[arg-type]
        )

    def test_reassign_owner_survives_inserts_landing_from_another_thread(self) -> None:
        import threading

        registry = RunRegistry()
        for index in range(400):
            run_id = f"seed-{index}"
            registry._runs[run_id] = self._bare_entry(run_id, "guest:g1")

        stop = threading.Event()
        insert_failures: list[BaseException] = []

        def _keep_inserting() -> None:
            index = 0
            try:
                while not stop.is_set():
                    run_id = f"late-{index}"
                    registry._runs[run_id] = self._bare_entry(run_id, "guest:other")
                    index += 1
            except BaseException as exc:  # noqa: BLE001 - reported, never swallowed
                insert_failures.append(exc)

        inserter = threading.Thread(target=_keep_inserting, daemon=True)
        inserter.start()
        try:
            for _ in range(200):
                # Under the unguarded version this raises RuntimeError:
                # dictionary changed size during iteration, well before
                # 200 sweeps.
                registry.reassign_owner(
                    old_owner_id="guest:g1",
                    new_owner_id="user:u1",
                    new_user_id="u1",
                )
        finally:
            stop.set()
            inserter.join(timeout=5.0)

        assert insert_failures == []
        assert all(
            entry.owner_id != "guest:g1" for entry in list(registry._runs.values())
        ), "every seeded run should have been reassigned by the first sweep"
