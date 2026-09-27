"""Card 58: Stop pressed while the answer is being written.

The product owner, 2026-09-27: "a user should be able to stop the answer at
any point of time until the answer pops out." The web client now offers Stop
for the whole Write step, so the server's half of that promise needs its own
proof: a stop that lands while the synth (writing) model call is still
running must really stop the question.

WHAT A STOP MID-WRITE MUST DO, one arm each:

- S1: the writing model call is cancelled, not left to finish in the
  background, and no task of the run is still running afterwards.
- S2: no answer arrives afterwards. No `token`, `citation`, `trust_signal`
  or `done` reaches either read path; the run's last event is the
  `cancelled` fatal error the web client words as "This run was stopped
  before it finished, so no answer was written."
- S3: the run is recorded as stopped. The capture row is written once, with
  `trust_outcome` `refuse` (which the review ritual reads as abstain, never
  as an answer), and with the cost already spent, including the cancelled
  writing call, so neither daily cap can be dodged by stopping late.

HOW THE STOP LANDS MID-WRITE. The real registry drives the real
`run_streaming()` and the real five-node graph, offline: the model tiers
are the shared compliant stub, the tools are the 4.16 gate's spy, and the
synth call is made slow (`_SLOW_WRITE_SECONDS`). The stop is issued the
moment the synth call has started and the `step` event announcing Write is
on the read path, which is the moment the reader sees "is writing the
answer". The write is slow rather than endless on purpose: a Stop that did
nothing would let the answer through inside the wait, so each arm fails on
its own assertion rather than on a timeout.

EVERY ARM CARRIES A POPULATE-CHECK, per build phases 4.7 and 4.11: the
synth call really started, and the Write step really announced itself,
before the stop was sent. Without them a stop that landed during Act would
pass every assertion here while proving nothing about writing.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.contracts.events import CostPayload, DonePayload, Event
from system_03_search_agent.core.run_registry import RunRegistry
from system_03_search_agent.synthesis.findings import SYNTH_SYSTEM_INSTRUCTION

# The 4.16 gate's autouse fixtures and run shape, re-registered rather than
# copied, the same way `test_write_streaming_premise.py` reuses them: one
# definition each, so this file grades the same setup those gates grade.
from tests.system_03_search_agent.core.test_phase_4_16_premise import (  # noqa: F401
    _context,
    _env,
    _install_tool_spy,
    _mock_litellm,
    _no_op_daily_caps,
    _query,
    _stub_symbol_resolution,
)

# The answer's own event types. None of them may reach a reader after Stop.
_ANSWER_EVENT_TYPES = frozenset({"token", "citation", "trust_signal", "done"})

# How long the faked writing call takes when nothing stops it. Long enough
# that a stop issued the moment it starts lands well inside it, and short
# enough that a stop which does nothing lets the answer through within
# `_WAIT_SECONDS`, which is what lets every arm below go red on its own
# assertion rather than on a timeout.
_SLOW_WRITE_SECONDS = 2.0

# Generous, because the offline graph is fast; only a hang would reach it.
_WAIT_SECONDS = 10.0


class _SlowSynth:
    """Makes the stubbed synth (writing) call slow, and records what
    happened to it: whether it started, was cancelled, or ran to the end."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = False
        self.finished = False

    def install(self, monkeypatch: pytest.MonkeyPatch, mock_acompletion: AsyncMock) -> None:
        original = mock_acompletion.side_effect
        synth = self

        async def _slow_dispatch(*args: object, **kwargs: object):
            messages = kwargs.get("messages") or []
            joined = "\n".join(
                message.get("content") or "" for message in messages  # type: ignore[union-attr]
            )
            if SYNTH_SYSTEM_INSTRUCTION in joined:
                synth.started.set()
                try:
                    await asyncio.sleep(_SLOW_WRITE_SECONDS)
                except asyncio.CancelledError:
                    synth.cancelled = True
                    raise
                synth.finished = True
            return await original(*args, **kwargs)

        monkeypatch.setattr(mock_acompletion, "side_effect", _slow_dispatch)


def _mock_capture_run(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Patch `feedback.capture_run` where `core.run._capture_interaction`
    reads it (a deferred import, so the package attribute is the seam),
    the same seam `test_run_capture.py` uses."""
    import system_03_search_agent.feedback as feedback_module

    mock = AsyncMock(return_value=None)
    monkeypatch.setattr(feedback_module, "capture_run", mock)
    return mock


async def _stop_mid_write(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> tuple[RunRegistry, str, _SlowSynth, int]:
    """Start a real run, wait until it is writing, stop it, and let it end.

    Returns the registry, the run id, the slow synth, and how many events
    the run had produced at the moment Stop was pressed.
    """
    synth = _SlowSynth()
    synth.install(monkeypatch, request.getfixturevalue("_mock_litellm"))
    spy = _install_tool_spy(monkeypatch)

    registry = RunRegistry()
    run_id = registry.create_run(_query(), _context(), owner_id="guest:stop-mid-write")
    entry = registry.get_run(run_id)

    await asyncio.wait_for(synth.started.wait(), timeout=_WAIT_SECONDS)

    # POPULATE-CHECKS: the run reached Write for real before the stop.
    assert spy.calls > 0, "populate-check failed: no faked tool was invoked."
    assert any(
        event.type == "step" and event.payload == {"step": "write", "status": "started"}
        for event in entry.events
    ), (
        "populate-check failed: the synth call started but the Write step never "
        "announced itself, so this is not the moment the reader sees writing."
    )
    assert not any(event.type in _ANSWER_EVENT_TYPES for event in entry.events), (
        "populate-check failed: answer events existed before the stop, so the "
        "stop did not land before the answer."
    )

    at_stop = len(entry.events)
    registry.cancel_run(run_id)
    # `asyncio.wait`, not `wait_for`: `wait_for` cancels what it waits on at
    # the timeout, which would end the run itself and hide a Stop that did
    # nothing.
    finished, _ = await asyncio.wait({entry.task}, timeout=_WAIT_SECONDS)
    if not finished:
        entry.task.cancel()
        await asyncio.wait({entry.task}, timeout=_WAIT_SECONDS)
        pytest.fail(
            f"Stop did not end the run within {_WAIT_SECONDS}s: its task was still "
            "running with the writing call in flight."
        )
    return registry, run_id, synth, at_stop


@pytest.mark.asyncio
async def test_s1_a_stop_mid_write_cancels_the_writing_call_and_leaves_no_task_running(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """The writing model call is cancelled, never left to finish.

    Mutation: make `RunRegistry.cancel_run` a no-op. The synth call is then
    never cancelled and the task never ends, so this arm goes red at the
    helper's "Stop did not end the run" check.
    """
    _mock_capture_run(monkeypatch)
    registry, run_id, synth, _ = await _stop_mid_write(monkeypatch, request)

    assert synth.cancelled, (
        "the writing model call was not cancelled by Stop, so the model kept "
        "writing an answer nobody will see, and it is billed."
    )
    assert not synth.finished, "the writing model call ran to completion after Stop."

    # Nothing of the run may still be running: a detached node task, a
    # still-sleeping abandonment check, or the synth call itself.
    for _ in range(5):
        await asyncio.sleep(0)
    leftovers = [
        task
        for task in asyncio.all_tasks()
        if task is not asyncio.current_task() and not task.done()
    ]
    assert not leftovers, f"tasks still running after Stop: {leftovers}"
    entry = registry.get_run(run_id)
    assert entry.task.cancelled(), "the run's task ended some way other than by Stop."
    assert entry.finished and entry.cancelled


@pytest.mark.asyncio
async def test_s2_no_answer_reaches_a_reader_after_a_stop_mid_write(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Both read paths end on the `cancelled` error, and nothing of the
    answer follows it.

    Mutation: a writing call that swallows the cancellation and returns its
    reply anyway (the shape `Harness.call_tier`'s re-raise exists to
    prevent). The answer's tokens and its `done` then land in
    `entry.events` after the stop and this arm goes red.
    """
    _mock_capture_run(monkeypatch)
    registry, run_id, _synth, at_stop = await _stop_mid_write(monkeypatch, request)
    entry = registry.get_run(run_id)

    after_stop = entry.events[at_stop:]
    assert [event.type for event in after_stop] == ["error"], (
        f"after Stop the run produced {[event.type for event in after_stop]}, "
        "expected exactly one error event and nothing else."
    )
    terminal = after_stop[0]
    assert terminal.payload["fatal"] is True
    assert terminal.payload["error_class"] == "cancelled"
    assert not any(event.type in _ANSWER_EVENT_TYPES for event in entry.events), (
        "an answer event reached the replay buffer of a stopped run, so a "
        "reconnecting reader would be shown an answer after Stop."
    )

    # The subscriber path, which is what the SSE endpoint streams: a full
    # replay ends on the cancelled error and yields no answer event.
    replayed: list[Event] = [event async for event in registry.subscribe(run_id)]
    assert replayed[-1].type == "error"
    assert replayed[-1].payload["error_class"] == "cancelled"
    assert not any(event.type in _ANSWER_EVENT_TYPES for event in replayed)

    # And the live queue, which the drain feeds in the same order.
    queued: list[Event] = []
    while True:
        item = entry.queue.get_nowait()
        if item is None:
            break
        queued.append(item)
    assert not any(event.type in _ANSWER_EVENT_TYPES for event in queued)
    assert queued[-1].payload["error_class"] == "cancelled"


@pytest.mark.asyncio
async def test_s3_a_stop_mid_write_is_recorded_as_stopped_with_its_cost(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """One capture row, recorded as no answer, carrying the cost already
    spent including the cancelled writing call.

    Mutation: pass `metered_cost_usd=0.0` from `run_streaming`'s `finally`,
    which is the code before card 58. Measured red: the row recorded
    0.000100 USD, exactly what was spent before Write.
    """
    capture = _mock_capture_run(monkeypatch)
    await _stop_mid_write(monkeypatch, request)

    assert capture.await_count == 1, (
        f"capture ran {capture.await_count} times for one stopped run; the "
        "daily query cap counts rows, so a stopped run must leave exactly one."
    )
    _query_arg, captured = capture.await_args.args
    done = captured[-1]
    assert done.type == "done"
    payload = DonePayload.model_validate(done.payload)
    assert payload.trust_outcome == "refuse", (
        "a run stopped while writing was recorded as "
        f"{payload.trust_outcome!r}, so it would read as an answer."
    )
    assert not any(event.type in {"token", "citation", "trust_signal"} for event in captured)

    last_cost_before_stop = max(
        (
            CostPayload.model_validate(event.payload).query_cost_usd
            for event in captured
            if event.type == "cost"
        ),
        default=0.0,
    )
    assert last_cost_before_stop > 0.0, (
        "populate-check failed: no model cost was recorded before Write, so "
        "the cost comparison below is inert."
    )
    assert payload.total_cost_usd > last_cost_before_stop, (
        f"the stopped run recorded {payload.total_cost_usd:.6f} USD, no more "
        f"than the {last_cost_before_stop:.6f} USD spent before Write, so the "
        "cancelled writing call the provider already billed is invisible to "
        "the system-wide daily cost cap."
    )
