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

Each write is parked on a gate so the stop provably lands inside it, rather
than racing a fast offline run.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

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
    parked: _ParkedWrite, *, owner_id: str
) -> tuple[RunRegistry, str]:
    """Start a real run, wait until it sent `done` and `parked` is in progress, stop it."""
    registry = RunRegistry()
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

    registry.cancel_run(run_id)
    for _ in range(5):
        await asyncio.sleep(0)
    parked.release.set()
    await _wait_for_task(entry)
    return registry, run_id


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

    registry, run_id = await _stop_after_done_while(memory, owner_id="guest:stop-after-done-1")
    entry = registry.get_run(run_id)

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

    registry, run_id = await _stop_after_done_while(history, owner_id="guest:stop-after-done-2")

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
