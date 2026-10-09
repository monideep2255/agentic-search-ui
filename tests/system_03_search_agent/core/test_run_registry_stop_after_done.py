"""Card 59: a stop that reaches the server after the run's `done` leaves it alone.

Owner decision D18: an answer that finished before Stop arrived stands. The
web client shows that answer whenever the server's stream ends in `done`, so
the server must then keep it too: saved to history and remembered by the
conversation. Otherwise the screen shows an answer that history and memory
have lost.

THE REAL ORDER, read from `core/run.py`'s `run_streaming` and pinned by the
populate-checks below: `done` is yielded to readers FIRST. Only then does the
run fold the turn into session memory (`_remember_turn`, after the graph
loop) and write the history row (`_capture_interaction`, in the `finally`).
So a stop can reach the server after the reader already has `done` while
both writes are still to come. Before card 59 `RunRegistry.cancel_run`
cancelled the run's task whenever it was still running, which cut those
writes short.

Arms:

- A1: stop while the memory write is in progress after `done`. The memory
  write completes, the history row is built from the run's own `done`, no `cancelled`
  error follows `done`, and the run is not marked cancelled.
- A2: stop while the history write is in progress after `done`. The row is
  written in full.
- B: stop before `done`, during the writing call. Today's behaviour exactly:
  no `done`, the `cancelled` error, no memory write, a `refuse` row.

The fix round (judge and adversary round 1):

- C1, J-59-02: the abandonment timer fires while the memory write after
  `done` is in progress (the browser closes its stream on `done`, so a
  finished run is always unwatched then). The write completes, as for a
  stop.
- C2 and C3, A-59-01 and A-59-03: GraphQL `stopRun` and the REST stop
  endpoint on a run that already sent `done` answer `stopped: false`, "it
  had already finished", never `stopped: true` for a run the server kept.

Each write is parked on a gate so the stop provably lands inside it, rather
than racing a fast offline run.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import system_03_search_agent.adapters.graphql.schema as graphql_schema_module
import system_03_search_agent.adapters.web_sse.app as web_app_module
import system_03_search_agent.core.run as run_module
import system_03_search_agent.feedback as feedback_module
from system_03_search_agent.contracts.events import DonePayload, Event
from system_03_search_agent.core.run_registry import RunEntry, RunRegistry

# The 4.16 gate's autouse fixtures and run shape, re-registered the same way
# card 58's stop-mid-write arms reuse them.
from tests.system_03_search_agent.core.test_phase_4_16_premise import (  # noqa: F401
    _context,
    _env,
    _install_tool_spy,
    _mock_litellm,
    _no_op_daily_caps,
    _query,
    _stub_symbol_resolution,
)
from tests.system_03_search_agent.core.test_run_registry_stop_mid_write import (
    _stop_mid_write,
)

_WAIT_SECONDS = 10.0


class _ParkedWrite:
    """A write that parks until released, recording how it ended."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0
        self.finished = 0
        self.cancelled = False
        self.events: list[Event] = []

    async def __call__(self, _query: object, events: list[Event]) -> None:
        self.calls += 1
        self.events = list(events)
        self.started.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        self.finished += 1


def _own_done(entry: RunEntry) -> Event:
    """The `done` the run itself sent to readers."""
    return next(event for event in entry.events if event.type == "done")


async def _wait_for_task(entry: RunEntry) -> None:
    finished, _ = await asyncio.wait({entry.task}, timeout=_WAIT_SECONDS)
    if not finished:
        entry.task.cancel()
        await asyncio.wait({entry.task}, timeout=_WAIT_SECONDS)
        pytest.fail(f"the run did not end within {_WAIT_SECONDS}s")


async def _stop_after_done_while(
    parked: _ParkedWrite,
    *,
    owner_id: str,
    registry: RunRegistry | None = None,
    stop: Callable[[RunRegistry, str], object] | None = None,
) -> tuple[RunRegistry, str, object]:
    """Start a real run, wait until it sent `done` and `parked` is in
    progress, stop it with `stop` (the registry's own `cancel_run` unless a
    surface is named), and return what the stop answered."""
    registry = registry if registry is not None else RunRegistry()
    run_id = registry.create_run(_query(), _context(), owner_id=owner_id)
    entry = registry.get_run(run_id)

    await asyncio.wait_for(parked.started.wait(), timeout=_WAIT_SECONDS)
    # POPULATE-CHECK: `done` was already on the read path before the write
    # began, so this is the moment a reader has the answer.
    assert any(event.type == "done" for event in entry.events), (
        "populate-check failed: the write began before `done` reached readers, "
        "so this is not a stop after done."
    )
    assert not entry.task.done(), "populate-check failed: the run had already ended."

    answer = (stop or (lambda reg, rid: reg.cancel_run(rid)))(registry, run_id)
    if asyncio.iscoroutine(answer):
        answer = await answer
    for _ in range(5):
        await asyncio.sleep(0)
    parked.release.set()
    await _wait_for_task(entry)
    return registry, run_id, answer


@pytest.mark.asyncio
async def test_a1_a_stop_after_done_lets_the_memory_write_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation: remove card 59's `done` check from `cancel_run`. The stop
    then cancels the parked memory write and this arm goes red."""
    memory = _ParkedWrite()
    monkeypatch.setattr(run_module, "_remember_turn", memory)
    capture = AsyncMock(return_value=None)
    monkeypatch.setattr(feedback_module, "capture_run", capture)

    registry, run_id, stopped = await _stop_after_done_while(
        memory, owner_id="guest:stop-after-done-1"
    )
    entry = registry.get_run(run_id)
    # The fix round, A-59-01: `cancel_run` says it stopped nothing.
    assert stopped is False, "cancel_run claimed to stop a run it left alone."

    # The real order: memory is written after `done`, history after memory.
    assert memory.events[-1].type == "done"
    assert memory.finished == 1 and not memory.cancelled, (
        "a stop that arrived after `done` cut the memory write short, so the "
        "conversation forgets an answer the screen shows."
    )
    assert capture.await_count == 1
    _query_arg, captured = capture.await_args.args
    # The row is built from the run's own `done`, the one the reader got,
    # never a stand-in synthesized for a stopped run.
    assert captured[-1] == _own_done(entry)
    assert not entry.cancelled, "a run that finished was marked cancelled."
    assert entry.events[-1].type == "done", (
        f"events after done: {[event.type for event in entry.events]}; a "
        "cancelled error followed an answer the reader already has."
    )


@pytest.mark.asyncio
async def test_a2_a_stop_after_done_lets_the_history_write_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation: as A1. The stop then cancels the parked history write."""
    remembered: list[list[Event]] = []

    async def _remember(_query: object, events: list[Event]) -> None:
        remembered.append(list(events))

    monkeypatch.setattr(run_module, "_remember_turn", _remember)
    history = _ParkedWrite()
    monkeypatch.setattr(feedback_module, "capture_run", history)

    registry, run_id, _stopped = await _stop_after_done_while(
        history, owner_id="guest:stop-after-done-2"
    )

    assert len(remembered) == 1, "populate-check failed: memory was not written before history."
    assert history.finished == 1 and not history.cancelled, (
        "a stop that arrived after `done` cut the history write short, so "
        "history loses an answer the screen shows."
    )
    entry = registry.get_run(run_id)
    assert history.events[-1] == _own_done(entry)
    assert not entry.cancelled


@pytest.mark.asyncio
async def test_b_a_stop_before_done_still_stops_and_records_nothing_answered(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Today's behaviour, unchanged: card 59 must not weaken a real stop.

    Mutation: make `cancel_run` a no-op. The run then finishes, `done`
    arrives and memory is written, and this arm goes red.
    """
    remembered: list[list[Event]] = []

    async def _remember(_query: object, events: list[Event]) -> None:
        remembered.append(list(events))

    monkeypatch.setattr(run_module, "_remember_turn", _remember)
    capture = AsyncMock(return_value=None)
    monkeypatch.setattr(feedback_module, "capture_run", capture)

    registry, run_id, _synth, _at_stop = await _stop_mid_write(monkeypatch, request)
    entry = registry.get_run(run_id)

    assert not any(event.type == "done" for event in entry.events)
    assert entry.events[-1].payload["error_class"] == "cancelled"
    assert entry.cancelled
    assert remembered == [], "a stopped run was folded into session memory."
    assert capture.await_count == 1
    _query_arg, captured = capture.await_args.args
    assert DonePayload.model_validate(captured[-1].payload).trust_outcome == "refuse"


@pytest.mark.asyncio
async def test_c1_the_abandonment_timer_lets_the_memory_write_after_done_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """J-59-02. The browser closes its stream the moment `done` arrives, so
    the run is unwatched while it saves its answer, and the abandonment
    timer runs out inside that save.

    Mutation: give `_cancel_if_still_abandoned` back its own
    `entry.task.cancel()` instead of the shared guard. The timer then
    cancels the parked memory write and this arm goes red.
    """
    memory = _ParkedWrite()
    monkeypatch.setattr(run_module, "_remember_turn", memory)
    capture = AsyncMock(return_value=None)
    monkeypatch.setattr(feedback_module, "capture_run", capture)

    grace = 0.2
    registry = RunRegistry(abandon_grace_seconds=grace)
    run_id = registry.create_run(_query(), _context(), owner_id="guest:abandon-after-done")
    entry = registry.get_run(run_id)

    # A reader that stops at `done`, the way the browser does.
    seen: list[str] = []
    async for event in registry.subscribe(run_id):
        seen.append(event.type)
    await asyncio.wait_for(memory.started.wait(), timeout=_WAIT_SECONDS)
    assert seen[-1] == "done", f"populate-check failed: the reader ended on {seen[-1:]}"
    assert entry.subscriber_count == 0, "populate-check failed: the reader is still attached."
    assert entry.abandonment_check is not None, (
        "populate-check failed: no abandonment timer was started after the reader left."
    )

    # Let the timer run out, with room to spare, while the save is parked.
    await asyncio.wait_for(entry.abandonment_check, timeout=_WAIT_SECONDS)
    await asyncio.sleep(grace)
    assert not entry.task.done(), (
        "the abandonment timer ended the run while it was saving an answer "
        "the reader already has."
    )
    memory.release.set()
    await _wait_for_task(entry)

    assert memory.finished == 1 and not memory.cancelled, (
        "the abandonment timer cut the memory write after `done` short, so the "
        "conversation forgets an answer the screen shows."
    )
    assert capture.await_count == 1
    assert not entry.cancelled, "a run that finished was marked cancelled by the timer."
    assert entry.events[-1].type == "done", (
        f"events after done: {[event.type for event in entry.events]}"
    )


@pytest.mark.asyncio
async def test_c2_graphql_stop_run_after_done_says_it_had_already_finished(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A-59-01, through the real `stopRun` resolver and a real registry.

    Mutation: restore the resolver's `stopped = not entry.task.done()`
    read. It then answers `stopped: true` for a run the server kept, and
    this arm goes red.
    """
    memory = _ParkedWrite()
    monkeypatch.setattr(run_module, "_remember_turn", memory)
    monkeypatch.setattr(feedback_module, "capture_run", AsyncMock(return_value=None))
    registry = RunRegistry()
    monkeypatch.setattr(graphql_schema_module, "default_registry", registry)
    info = SimpleNamespace(context=SimpleNamespace(principal=SimpleNamespace(id="gql-59")))

    def _stop(_registry: RunRegistry, run_id: str) -> object:
        return graphql_schema_module.Mutation().stop_run(info, run_id)

    registry, run_id, result = await _stop_after_done_while(
        memory, owner_id="user:gql-59", registry=registry, stop=_stop
    )

    assert result.run_id == run_id
    assert result.stopped is False, (
        "stopRun said stopped for a run whose answer the server kept in history and memory."
    )
    assert memory.finished == 1
    assert not registry.get_run(run_id).cancelled


@pytest.mark.asyncio
async def test_c3_rest_stop_after_done_says_it_had_already_finished(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A-59-03, through the real `POST /v1/query/{run_id}/stop` handler.

    Mutation: restore the fixed `StopRunResponse(stopped=True)`. It then
    answers `stopped: true`, which the command line prints as "run
    stopped", for a run the server kept, and this arm goes red.
    """
    memory = _ParkedWrite()
    monkeypatch.setattr(run_module, "_remember_turn", memory)
    monkeypatch.setattr(feedback_module, "capture_run", AsyncMock(return_value=None))
    registry = RunRegistry()
    monkeypatch.setattr(web_app_module, "default_registry", registry)
    caller = SimpleNamespace(owner_id="guest:rest-59")

    def _stop(_registry: RunRegistry, run_id: str) -> object:
        return web_app_module.post_v1_query_stop(run_id, caller)

    registry, run_id, response = await _stop_after_done_while(
        memory, owner_id="guest:rest-59", registry=registry, stop=_stop
    )

    assert response.stopped is False, (
        "the REST stop said stopped for a run whose answer the server kept."
    )
    assert memory.finished == 1
    assert not registry.get_run(run_id).cancelled
