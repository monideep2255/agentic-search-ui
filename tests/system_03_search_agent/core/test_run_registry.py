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

from system_03_search_agent.contracts.events import (
    CostPayload,
    DonePayload,
    ErrorPayload,
    Event,
    GuardPayload,
)
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import run_registry as run_registry_module
from system_03_search_agent.core.run_registry import (
    RunEntry,
    RunNotFoundError,
    RunNotOwnedError,
    RunRegistry,
)
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


class TestConcurrentRunCapExceededErrorBound:
    """T-4.3-05, build phase 4.3: `ConcurrentRunCapExceededError` gains a
    structural `bound` attribute, and `retry_after_s` gains a default, so
    a caller (this repository's own GraphQL adapter, and any future one)
    can construct it with just a message and still have a catch site
    branch on WHICH bound was hit without parsing the message string.
    """

    def test_bound_defaults_to_concurrency(self) -> None:
        # Mutation that turns this red: drop the `bound` attribute, or
        # default it to anything other than "concurrency", the only bound
        # this exception represents today.
        exc = run_registry_module.ConcurrentRunCapExceededError("too many active runs")
        assert exc.bound == "concurrency"

    def test_retry_after_s_defaults_without_being_passed(self) -> None:
        # Mutation that turns this red: make `retry_after_s` required
        # again. A caller that only knows the message (the shape a
        # monkeypatched raise site in an adapter's own tests uses) must
        # still be able to construct this exception.
        exc = run_registry_module.ConcurrentRunCapExceededError("too many active runs")
        assert exc.retry_after_s == run_registry_module.CONCURRENT_RUN_CAP_RETRY_AFTER_S

    def test_bound_and_retry_after_s_are_still_overridable(self) -> None:
        exc = run_registry_module.ConcurrentRunCapExceededError(
            "too many active runs", retry_after_s=42, bound="a-future-bound"
        )
        assert exc.retry_after_s == 42
        assert exc.bound == "a-future-bound"

    @pytest.mark.asyncio
    async def test_create_run_raises_with_bound_concurrency(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: raise the bare exception with no
        # `bound` kwarg at the real production raise site inside
        # `create_run`, silently relying on the default rather than
        # stating the bound explicitly.
        async def _never_finishes(query: Query, context: RequestContext):
            yield _fake_event("guard", query.trace_id, 0)
            await asyncio.sleep(3600)
            yield _fake_event("done", query.trace_id, 1)  # pragma: no cover

        monkeypatch.setattr(run_registry_module, "run_streaming", _never_finishes)
        registry = RunRegistry(max_active_runs_per_owner=1)
        held_run_id = registry.create_run(_valid_query(), _valid_context(), owner_id="user:cap-test")

        with pytest.raises(run_registry_module.ConcurrentRunCapExceededError) as excinfo:
            registry.create_run(_valid_query(), _valid_context(), owner_id="user:cap-test")

        assert excinfo.value.bound == "concurrency"
        assert excinfo.value.retry_after_s == run_registry_module.CONCURRENT_RUN_CAP_RETRY_AFTER_S

        registry.get_run(held_run_id).task.cancel()


class TestConcurrentRunCapDecoupledFromTheFreeAllowance:
    """T-4.3-05, build phase 4.3 (closes the shared-number half of
    F-4.10-A-10 / F-4.10-J-02): the concurrency cap this module enforces
    must not be the free-allowance ceiling `data.guest_sessions` enforces,
    and it must exceed the guest ATTEMPT ceiling so a bursting guest
    always hits the allowance wall first, never an ambiguous concurrency
    refusal.
    """

    def test_the_cap_is_not_the_free_allowance(self) -> None:
        # Mutation that turns this red: restore DEFAULT_MAX_ACTIVE_RUNS_
        # PER_OWNER to 5, the exact value F-4.10-J-02 measured making a
        # concurrency test clause unable to fail.
        from system_03_search_agent.data.guest_sessions import FREE_RUN_ALLOWANCE

        assert run_registry_module.DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER != FREE_RUN_ALLOWANCE

    def test_the_cap_exceeds_the_guest_attempt_ceiling(self) -> None:
        # Mutation that turns this red: pick a cap between the allowance
        # (5) and the attempt ceiling (10), which would still be numerically
        # distinct from FREE_RUN_ALLOWANCE and still leave a guest able to
        # burst past this cap before ATTEMPTS_EXHAUSTED ever fires, which
        # is the exact ambiguous-refusal shape this phase closes.
        from system_03_search_agent.data.guest_sessions import ATTEMPT_ALLOWANCE

        assert run_registry_module.DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER > ATTEMPT_ALLOWANCE


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


class TestRunRegistryResolveOwnedRun:
    """T-4.3-07: THE ownership rule, promoted here so more than one
    delivery surface enforces the same one rather than each carrying a
    copy. `adapters/web_sse/app.py`'s `_get_owned_run` is now the HTTP
    mapping of these two errors, and its own tests still assert the 404
    and 403 it produces; these arms pin the rule itself.
    """

    @pytest.mark.asyncio
    async def test_the_owner_gets_its_own_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Mutation that turns this red: reject every caller. A rule that
        # refuses everyone passes every attack arm and destroys the
        # product, so this arm exists beside the two refusal arms below.
        async def _fake_stream(query: Query, context: RequestContext):
            yield _fake_event("done", query.trace_id, 0)

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream)
        registry = RunRegistry()
        run_id = registry.create_run(_valid_query(), _valid_context(), owner_id="user:owner-1")

        entry = registry.resolve_owned_run(run_id, "user:owner-1")

        assert entry.run_id == run_id
        await _drain_until_sentinel(entry.queue)

    @pytest.mark.asyncio
    async def test_a_different_owner_is_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Mutation that turns this red: drop the owner comparison, which
        # would let any authenticated caller read any run by id.
        async def _fake_stream(query: Query, context: RequestContext):
            yield _fake_event("done", query.trace_id, 0)

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream)
        registry = RunRegistry()
        run_id = registry.create_run(_valid_query(), _valid_context(), owner_id="user:owner-1")
        entry = registry.get_run(run_id)

        with pytest.raises(RunNotOwnedError):
            registry.resolve_owned_run(run_id, "user:someone-else")

        await _drain_until_sentinel(entry.queue)

    def test_an_unknown_run_reports_missing_not_forbidden(self) -> None:
        # Mutation that turns this red: check ownership before existence,
        # which would report an unknown id as forbidden. The ordering is
        # preserved from `_get_owned_run`, whose 404-before-403 behavior
        # T-1.2-02's acceptance criteria fixed and whose tests assert it.
        registry = RunRegistry()

        with pytest.raises(RunNotFoundError):
            registry.resolve_owned_run("does-not-exist", "user:owner-1")

    @pytest.mark.asyncio
    async def test_a_guest_and_a_user_are_never_confused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: compare a bare uuid rather than the
        # namespaced owner_id, which would let `guest:<uuid>` match
        # `user:<uuid>` for the same uuid. T-4.10-03's design decision 2.
        async def _fake_stream(query: Query, context: RequestContext):
            yield _fake_event("done", query.trace_id, 0)

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream)
        registry = RunRegistry()
        shared_uuid = "11111111-2222-3333-4444-555555555555"
        run_id = registry.create_run(
            _valid_query(), _valid_context(), owner_id=f"guest:{shared_uuid}"
        )
        entry = registry.get_run(run_id)

        with pytest.raises(RunNotOwnedError):
            registry.resolve_owned_run(run_id, f"user:{shared_uuid}")

        await _drain_until_sentinel(entry.queue)

    def test_run_not_owned_error_is_a_permission_error(self) -> None:
        # Mutation that turns this red: make it subclass KeyError like its
        # sibling, which would let one `except RunNotFoundError` swallow an
        # authorization failure as if the run simply did not exist.
        assert issubclass(RunNotOwnedError, PermissionError)
        assert not issubclass(RunNotOwnedError, KeyError)


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
            # T-4.6-06: `RunEntry` now holds the `Query` its task is running,
            # so the guest-to-account migration can rewrite the run's own
            # identity and not only this entry's copy of it (F-4.6-J-01). A
            # real `Query` rather than a stand-in, because `reassign_owner`
            # writes to `entry.query.owner_id` and a stand-in would let a
            # mutation to that line pass unnoticed here.
            query=Query(
                text="what is this",
                session_id="bare-entry",
                trace_id=run_id,
                owner_id=owner_id,
            ),
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


class TestTheZeroOutputRefundFiresOnTheRightEndStates:
    """F-4.10-V-02, at the one place the decision actually lives.

    `_fire_guard_refusal_callback` now fires for a run that ended on a FATAL
    error as well as one that ended on a guardrail refusal, because a visitor
    who got nothing got nothing either way. What that must NOT do is fire for
    a run that emitted a non-fatal error and then streamed a real answer,
    which several perfectly good runs do: `write_node` reports a truncated
    tool result and an uncited `ok` result as `fatal=False` and then writes
    the narrative.

    Driven through the function directly rather than through the app, because
    a non-fatal error followed by a real answer is not a shape the stubbed
    end-to-end harness produces, and a gate that could only be exercised
    end to end would leave `fatal is True` untested. That gap was measured: a
    mutation removing the `fatal` check left all 36 clauses of the phase
    premise gate green.

    COVERAGE. Exercised: the fatal arm fires, the non-fatal arm does not, and
    the `charged` argument is carried correctly on the fatal arm. NOT
    exercised here: a cancelled run, whose exclusion is structural rather
    than conditional (`_drain_into_entry` never routes its cancellation event
    through this function, and a cancelled run reaches no `done` event), and
    the at-most-once disarm, which `TestRunEntry` above already owns.
    """

    @staticmethod
    def _event(event_type: str, payload: object) -> Event:
        """A real, schema-valid Event.

        Payloads are built from the contract models rather than from bare
        dicts, so a clause cannot pass against a shape the wire could never
        carry, and so `fatal` is the genuine field the production path reads
        rather than a key this test invented.
        """
        return Event(
            type=event_type,
            version="v1",
            trace_id="trace-1",
            seq=0,
            ts=datetime.now(UTC),
            payload=payload.model_dump(),  # type: ignore[attr-defined]
        )

    @staticmethod
    def _error(*, fatal: bool, scope: str, source: str) -> ErrorPayload:
        return ErrorPayload(
            fatal=fatal,
            scope=scope,  # type: ignore[arg-type]
            source=source,
            error_class="unexpected",
            message="something went wrong",
            retry_after_s=0,
        )

    @staticmethod
    def _cost() -> CostPayload:
        return CostPayload(
            query_cost_usd=0.002, query_cap_usd=0.1, cap_fraction=0.02, model_tier="guard"
        )

    @staticmethod
    def _done() -> DonePayload:
        return DonePayload(
            total_cost_usd=0.0, total_tool_calls=0, elapsed_ms=1, trust_outcome="refuse"
        )

    def _drive(self, events: list[Event]) -> list[bool]:
        fired: list[bool] = []
        entry = RunEntry(
            run_id="run-1",
            user_id=None,
            query=Query(
                text="what is this",
                session_id="refund-probe",
                trace_id="run-1",
                owner_id="guest:11111111-1111-1111-1111-111111111111",
            ),
            owner_id="guest:11111111-1111-1111-1111-111111111111",
            queue=asyncio.Queue(),
            task=SimpleNamespace(),  # type: ignore[arg-type]
            on_guard_refused=fired.append,
        )
        for event in events:
            run_registry_module._fire_guard_refusal_callback(entry, event)
        return fired

    def test_a_fatal_error_then_done_refunds(self) -> None:
        fired = self._drive([
            self._event("error", self._error(fatal=True, scope="step", source="guardrail")),
            self._event("done", self._done()),
        ])
        assert fired == [False], (
            "a run that died before producing an answer did not refund the "
            "visitor; measured on the running app, that cost them one of five "
            "free searches for a failure that was not theirs (F-4.10-V-02)"
        )

    def test_a_fatal_error_after_a_model_call_leaves_the_shared_day_charged(self) -> None:
        fired = self._drive([
            self._event("cost", self._cost()),
            self._event("error", self._error(fatal=True, scope="step", source="write")),
            self._event("done", self._done()),
        ])
        assert fired == [True], (
            "the refund was told no model call had been made, so the shared "
            "daily budget would be given back for money that was actually "
            "spent, which is the free-compute path the asymmetry exists to "
            "close"
        )

    def test_a_non_fatal_error_on_an_otherwise_good_run_refunds_nothing(self) -> None:
        """The arm the `fatal is True` check exists for.

        `write_node` emits `fatal=False` errors on runs that go on to stream
        a real answer (a truncated tool result, an uncited `ok` result).
        Refunding those gives back a search the visitor actually received,
        which is the free-answer class F-4.10-R-01 was filed for, reached
        from the opposite direction.
        """
        fired = self._drive([
            self._event(
                "error", self._error(fatal=False, scope="tool", source="cypher_query")
            ),
            self._event("done", self._done()),
        ])
        assert fired == [], (
            "a run that emitted a non-fatal note and then answered the "
            "question was refunded; only a FATAL end state means the visitor "
            "got nothing"
        )

    def test_a_guardrail_refusal_still_fires_it(self) -> None:
        """The original arm, re-proved rather than assumed to have survived
        having a second trigger added beside it."""
        fired = self._drive([
            self._event(
                "guard",
                GuardPayload(passed=False, category="injection", reason="refused"),
            ),
            self._event("done", self._done()),
        ])
        assert fired == [False]

    def test_a_clean_run_fires_nothing(self) -> None:
        """The arm that catches a refund firing unconditionally, which would
        hand every visitor unlimited free searches."""
        fired = self._drive([
            self._event("guard", GuardPayload(passed=True, category="ok", reason=None)),
            self._event("cost", self._cost()),
            self._event("done", self._done()),
        ])
        assert fired == []


# ---------------------------------------------------------------------------
# F-4.6-A-02 and F-4.6-J-01: the registry's two halves of the fix.
# ---------------------------------------------------------------------------


class TestACancelledRunIsFinalizedRatherThanAbandoned:
    """`_drain_into_entry` closes the stream it consumed, on every exit.

    F-4.6-A-02. Cancelling this task used to leave `run_streaming` suspended
    at the `yield` its `__anext__` was serving, with the run's own epilogue
    (session memory, and capture) unexecuted until the collector happened to
    finalize it. Twelve queries stopped through `POST /v1/query/{run_id}/stop`
    against a per-user cap of three were all accepted and left zero rows.
    """

    @pytest.mark.asyncio
    async def test_a_stopped_run_finalizes_the_stream_it_was_consuming(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The ordinary stop: the cancellation lands inside the generator,
        which is where a draining run is nearly always awaiting.

        Control: the `try`/`finally` around `run_streaming`'s body. Delete
        it and this arm goes red, because the run's epilogue would then sit
        after the last `yield`, which a cancelled generator never reaches.

        WHAT THIS ARM DOES NOT GRADE, stated because the first version of
        it claimed otherwise. Deleting `await stream.aclose()` from
        `_drain_into_entry`'s `finally` leaves this arm GREEN. Measured, not
        reasoned: with the close removed, the end-to-end reproduction still
        produced three rows for three stopped runs. A cancellation is
        delivered to the innermost awaitable, so it lands inside the
        generator, Python runs its `finally` on the spot, and the explicit
        close has nothing left to do. `test_a_run_suspended_at_a_yield_is_
        finalized_by_the_explicit_close` below is the arm that grades the
        close, and it exists because this one cannot."""
        finalized: list[bool] = []

        async def _fake_stream(query, context):
            try:
                yield _fake_event("guard", query.trace_id, 0)
                await asyncio.sleep(3600)
            finally:
                finalized.append(True)

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream)

        registry = RunRegistry()
        run_id = registry.create_run(
            _valid_query(), _valid_context(), owner_id="guest:cancel-probe"
        )
        await asyncio.sleep(0.01)
        registry.cancel_run(run_id)
        entry = registry.get_run(run_id)
        try:
            await entry.task
        except asyncio.CancelledError:
            pass

        assert finalized == [True], (
            "a stopped run left its stream unfinalized, so the run's own "
            "epilogue (capture) never ran (F-4.6-A-02)"
        )

    @pytest.mark.asyncio
    async def test_a_run_suspended_at_a_yield_is_finalized_by_the_explicit_close(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The case `await stream.aclose()` exists for, and the ONLY one
        that grades it. Recorded this way because the obvious version of
        this arm does not grade it at all.

        MEASURED, NOT REASONED. Removing `await stream.aclose()` from
        `_drain_into_entry`'s `finally` and re-running the end-to-end
        stopped-run reproduction left every row in place: three stopped runs
        still produced three rows. The reason is that a cancellation is
        delivered to the INNERMOST awaitable, which for a run being drained
        is almost always something inside the generator itself, so Python
        runs the generator's own `finally` on the spot and the explicit
        close has nothing left to do. An arm built on that shape would pass
        with the close deleted, which is the definition of a decorative
        assertion.

        The window the close actually covers is the other one: the
        generator suspended at its `yield` while the CONSUMER is awaiting.
        `_drain_into_entry` does await in its loop body (the queue put, and
        the condition it notifies on), so a cancellation landing there
        leaves the generator untouched and unfinalized. This arm produces
        exactly that state by holding the entry's own condition lock, which
        is where the drain loop blocks, then cancelling while it waits.

        Mutation: delete `await stream.aclose()`. Ran it. This arm goes red
        on `finalized == [True]`, reading `[]`: the run's epilogue, and
        therefore its capture, never ran at all."""
        finalized: list[bool] = []

        async def _fake_stream(query, context):
            try:
                yield _fake_event("guard", query.trace_id, 0)
                yield _fake_event("done", query.trace_id, 1)
            finally:
                finalized.append(True)

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream)

        registry = RunRegistry()
        run_id = registry.create_run(
            _valid_query(), _valid_context(), owner_id="guest:suspend-probe"
        )
        entry = registry.get_run(run_id)

        # Block the drain loop inside its own body, with the generator
        # parked at the yield it just served.
        await entry.new_event.acquire()
        await asyncio.sleep(0.01)
        assert entry.events, "the drain loop never got an event, so it is not blocked"
        assert not finalized, (
            "the generator finalized before the cancellation, so this arm is "
            "not producing the state it claims to"
        )

        entry.task.cancel()
        await asyncio.sleep(0)
        entry.new_event.release()
        try:
            await entry.task
        except asyncio.CancelledError:
            pass

        assert finalized == [True], (
            "a run cancelled while its generator was suspended at a yield was "
            "never finalized, so its epilogue (capture) never ran (F-4.6-A-02)"
        )


class TestGuestMigrationMovesTheRunsOwnIdentity:
    @pytest.mark.asyncio
    async def test_reassign_owner_rewrites_the_query_the_task_is_running(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T-4.6-06, F-4.6-J-01 and F-4.6-A-03. `reassign_owner` used to
        rewrite `entry.owner_id` and `entry.user_id` only, which migrated
        what the HTTP layer's ownership check reads and left what the RUN
        reads behind, so an in-flight run captured its `interactions` row
        under the revoked guest principal.

        Asserted on the object the RUNNING TASK holds, not on
        `entry.query`, because those are only the same object while the fix
        is correct and asserting on `entry.query` would pass on a version
        that rebound the entry to a copy.

        Mutation: delete the two `entry.query.*` assignments from
        `reassign_owner`. This test goes red on the first assertion below."""
        observed: list[Query] = []

        async def _fake_stream(query, context):
            observed.append(query)
            yield _fake_event("guard", query.trace_id, 0)
            await asyncio.sleep(3600)

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream)

        registry = RunRegistry()
        run_id = registry.create_run(
            _valid_query(owner_id="guest:g-migrate"),
            _valid_context(),
            owner_id="guest:g-migrate",
        )
        await asyncio.sleep(0.01)
        assert observed, "the fake stream never started, so nothing is being graded"

        reassigned = registry.reassign_owner(
            old_owner_id="guest:g-migrate",
            new_owner_id="user:new-account",
            new_user_id="new-account",
        )

        assert observed[0].owner_id == "user:new-account", (
            "the run is still holding the revoked guest principal, so its "
            "captured row will be owned by an identity that no longer exists"
        )
        assert observed[0].user_id == "new-account"
        assert reassigned == 1
        assert registry.get_run(run_id).owner_id == "user:new-account"

        registry.cancel_run(run_id)
        entry = registry.get_run(run_id)
        try:
            await entry.task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_reassign_owner_leaves_another_guests_run_alone(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The F-4.5-A-02 guard on the new half: a migration must move the
        one named principal's runs and nobody else's. Mutation: change the
        `if entry.owner_id == old_owner_id` test in `reassign_owner` to
        `if entry.owner_id.startswith("guest:")`. This test goes red because
        the bystander's run would then be handed to the new account."""
        observed: dict[str, Query] = {}

        async def _fake_stream(query, context):
            observed[query.trace_id] = query
            yield _fake_event("guard", query.trace_id, 0)
            await asyncio.sleep(3600)

        monkeypatch.setattr(run_registry_module, "run_streaming", _fake_stream)

        registry = RunRegistry()
        mine = registry.create_run(
            _valid_query(trace_id="mine", owner_id="guest:mine"),
            _valid_context(),
            owner_id="guest:mine",
        )
        theirs = registry.create_run(
            _valid_query(trace_id="theirs", owner_id="guest:theirs"),
            _valid_context(),
            owner_id="guest:theirs",
        )
        await asyncio.sleep(0.01)

        registry.reassign_owner(
            old_owner_id="guest:mine",
            new_owner_id="user:new-account",
            new_user_id="new-account",
        )

        assert observed["mine"].owner_id == "user:new-account"
        assert observed["theirs"].owner_id == "guest:theirs", (
            "a bystanding guest's run was handed to the migrating account"
        )

        for run_id in (mine, theirs):
            registry.cancel_run(run_id)
            entry = registry.get_run(run_id)
            try:
                await entry.task
            except asyncio.CancelledError:
                pass
