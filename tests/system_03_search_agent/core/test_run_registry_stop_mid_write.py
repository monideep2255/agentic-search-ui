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
- S4: that cost is charged once. The row carries the harness's own total,
  which already includes everything spent before Write, never that total
  plus the spend before Write again (F-58-J01).

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

BUILD PHASE 8.7 MOVED WHAT IS ON SCREEN WHEN THE WRITING CALL RUNS. The
code-built record listing and its citations are now sent before the synth
call (card 50, option E, each token `placement` "listing"), so a stop
during the writing call lands AFTER the records are on screen. The product
owner decided that case on 2026-09-27: "Search stopped" appears above the
records already shown and nothing new appears after it; a stop before any
records arrive still shows only "Search stopped", as card 58 does. So:

- S1 to S4 still stop during the writing call, now with the listing on the
  read path. Their populate-check says exactly that: the records are there,
  and no summary token, trust signal or `done` is. S2 pins the owner's
  rule on the server: the records already sent stay in both read paths,
  and nothing follows the `cancelled` error. S3 and S4 pin that the run is
  still recorded as stopped, never answered, with its cost, charged once.
- S5 to S7 keep card 58's original premise, a stop in Write before any
  answer event, by parking Write's one wait before the listing is built,
  the read of the `think.asks_features` decision. Their assertions are
  card 58's own: no answer event reaches any reader at all.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.contracts.events import CostPayload, DonePayload, Event
from system_03_search_agent.contracts.token_order import LISTING, placement_of
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.core.run_registry import RunRegistry
from system_03_search_agent.harness.harness import Harness
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


def _is_listing_token(event: Event) -> bool:
    """A token of the record listing, sent before the writing call."""
    return event.type == "token" and placement_of(event.payload) == LISTING


def _is_summary_or_verdict(event: Event) -> bool:
    """An answer event that only the written answer produces: a summary
    token, a trust signal or `done`. None may exist on a stopped run."""
    if event.type == "token":
        return not _is_listing_token(event)
    return event.type in {"trust_signal", "done"}

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
    # Build phase 8.7: the records are on screen before the writing call
    # starts, and nothing of the written answer is.
    assert any(_is_listing_token(event) for event in entry.events) and any(
        event.type == "citation" for event in entry.events
    ), (
        "populate-check failed: the listing and its citations were not on the "
        "read path when the writing call started, so this is not a stop after "
        "the records are on screen."
    )
    assert not any(_is_summary_or_verdict(event) for event in entry.events), (
        "populate-check failed: summary tokens, a trust signal or `done` existed "
        "before the stop, so the stop did not land before the written answer."
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

    Build phase 8.7: the records sent before the writing call stay, as the
    owner decided on 2026-09-27 ("Search stopped" above the records already
    shown, nothing new after it). They are exactly what was on the read path
    at the stop, in both read paths; no summary token, trust signal or
    `done` exists anywhere.

    Mutation: a writing call that swallows the cancellation and returns its
    reply anyway (the shape `Harness.call_tier`'s re-raise exists to
    prevent). The answer's tokens and its `done` then land in
    `entry.events` after the stop and this arm goes red.
    """
    _mock_capture_run(monkeypatch)
    registry, run_id, _synth, at_stop = await _stop_mid_write(monkeypatch, request)
    entry = registry.get_run(run_id)
    shown = [
        (event.seq, event.type)
        for event in entry.events[:at_stop]
        if event.type in _ANSWER_EVENT_TYPES
    ]

    after_stop = entry.events[at_stop:]
    assert [event.type for event in after_stop] == ["error"], (
        f"after Stop the run produced {[event.type for event in after_stop]}, "
        "expected exactly one error event and nothing else."
    )
    terminal = after_stop[0]
    assert terminal.payload["fatal"] is True
    assert terminal.payload["error_class"] == "cancelled"
    assert not any(_is_summary_or_verdict(event) for event in entry.events), (
        "a summary token, trust signal or `done` reached the replay buffer of a "
        "stopped run, so a reconnecting reader would be shown an answer after Stop."
    )

    # The subscriber path, which is what the SSE endpoint streams: a full
    # replay ends on the cancelled error, keeps the records that were on
    # screen, and yields nothing of the written answer.
    replayed: list[Event] = [event async for event in registry.subscribe(run_id)]
    assert replayed[-1].type == "error"
    assert replayed[-1].payload["error_class"] == "cancelled"
    assert not any(_is_summary_or_verdict(event) for event in replayed)
    assert [
        (event.seq, event.type) for event in replayed if event.type in _ANSWER_EVENT_TYPES
    ] == shown, "a reconnecting reader is not shown the records that were on screen at Stop."

    # And the live queue, which the drain feeds in the same order.
    queued: list[Event] = []
    while True:
        item = entry.queue.get_nowait()
        if item is None:
            break
        queued.append(item)
    assert not any(_is_summary_or_verdict(event) for event in queued)
    assert [
        (event.seq, event.type) for event in queued if event.type in _ANSWER_EVENT_TYPES
    ] == shown, "the live reader is not shown the records that were on screen at Stop."
    assert queued[-1].payload["error_class"] == "cancelled"


@pytest.mark.asyncio
async def test_s3_a_stop_mid_write_is_recorded_as_stopped_with_its_cost(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """One capture row, recorded as no answer, carrying the cost already
    spent including the cancelled writing call.

    Build phase 8.7: the row may carry the records that were on screen at
    the stop (the listing's tokens and citations), and nothing more; it is
    still `refuse`, which saves no answer text.

    Mutation: pass `metered_cost_usd=0.0` from `run_streaming`'s `finally`,
    which is the code before card 58. Measured red: the row recorded
    0.000100 USD, exactly what was spent before Write.
    """
    capture = _mock_capture_run(monkeypatch)
    registry, run_id, _synth, at_stop = await _stop_mid_write(monkeypatch, request)
    shown_seqs = {
        event.seq
        for event in registry.get_run(run_id).events[:at_stop]
        if event.type in _ANSWER_EVENT_TYPES
    }

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
    assert not any(_is_summary_or_verdict(event) for event in captured[:-1]), (
        "the stopped run's row carries part of a written answer."
    )
    assert {
        event.seq for event in captured[:-1] if event.type in _ANSWER_EVENT_TYPES
    } <= shown_seqs, "the row carries answer events the reader never saw before Stop."

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


def _record_harness_totals(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record every value `Harness.get_query_cost_usd` returns, unchanged.

    The harness total only ever grows, so the largest value read is the
    run's final total, the one `run_streaming`'s `finally` hands to capture.
    """
    seen: list[float] = []
    original = Harness.get_query_cost_usd

    def _recording(self: Harness, trace_id: str) -> float:
        value = original(self, trace_id)
        seen.append(value)
        return value

    monkeypatch.setattr(Harness, "get_query_cost_usd", _recording)
    return seen


@pytest.mark.asyncio
async def test_s4_a_stopped_run_is_charged_once_not_twice(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """The row carries the harness total, once, F-58-J01.

    S3 proves the cancelled writing call is counted. It cannot tell counted
    once from counted twice, because both are more than the spend before
    Write. The harness total already includes every earlier `cost` event,
    so adding the last `cost` event to it charges the spend before Write a
    second time, against both daily caps, for a question the person stopped.

    Mutation: record `_observed_cost_usd(events) + metered_cost_usd` in
    `_terminal_events_for_capture` instead of the larger of the two. The row
    then carries the harness total plus the spend before Write, and this arm
    goes red.
    """
    capture = _mock_capture_run(monkeypatch)
    harness_totals = _record_harness_totals(monkeypatch)
    await _stop_mid_write(monkeypatch, request)

    assert capture.await_count == 1
    _query_arg, captured = capture.await_args.args
    payload = DonePayload.model_validate(captured[-1].payload)
    last_cost_before_stop = max(
        (
            CostPayload.model_validate(event.payload).query_cost_usd
            for event in captured
            if event.type == "cost"
        ),
        default=0.0,
    )
    assert harness_totals, "populate-check failed: the harness total was never read."
    harness_total = max(harness_totals)

    # POPULATE-CHECKS: something was spent before Write, and the cancelled
    # writing call added to it. Without both, once and twice cannot differ.
    assert last_cost_before_stop > 0.0, (
        "populate-check failed: no model cost was recorded before Write."
    )
    assert harness_total > last_cost_before_stop, (
        "populate-check failed: the harness total does not include the "
        "cancelled writing call, so this arm cannot see a double charge."
    )

    assert payload.total_cost_usd == pytest.approx(harness_total, rel=1e-9), (
        f"the stopped run recorded {payload.total_cost_usd:.6f} USD, but it "
        f"spent {harness_total:.6f} USD in all, of which "
        f"{last_cost_before_stop:.6f} USD before Write. A row above the "
        "harness total charges the person's daily allowance and the system "
        "cap twice for the same model calls."
    )


# ---------------------------------------------------------------------------
# S5 to S7: a stop in Write BEFORE the listing is sent. Card 58's original
# premise, kept now that a stop during the writing call lands after the
# records are on screen (build phase 8.7).
# ---------------------------------------------------------------------------


class _SlowFeaturesRead:
    """Makes Write's read of the `think.asks_features` decision slow.

    That read is Write's one wait between announcing the step and building
    the listing (`_write_answer`, `await _clinical_features_asked`), the
    wait a real run makes when the decision is still running. Slow rather
    than endless for the same reason as `_SlowSynth`: a Stop that did
    nothing lets the answer through inside the wait, so each arm fails on
    its own assertion rather than on a timeout. Returns the decision's
    fail-open value, False, when it is let finish.
    """

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = False
        self.finished = False

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        reader = self

        async def _slow_read(_harness: object, _deadline: float | None = None) -> bool:
            reader.started.set()
            try:
                await asyncio.sleep(_SLOW_WRITE_SECONDS)
            except asyncio.CancelledError:
                reader.cancelled = True
                raise
            reader.finished = True
            return False

        monkeypatch.setattr(graph_module, "_clinical_features_asked", _slow_read)


async def _stop_before_listing(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> tuple[RunRegistry, str, _SlowFeaturesRead, _SlowSynth, int]:
    """Start a real run, wait until Write has begun but sent nothing of the
    answer, stop it, and let it end.

    Returns the registry, the run id, the parked read, the synth recorder,
    and how many events the run had produced at the moment Stop was pressed.
    """
    reader = _SlowFeaturesRead()
    reader.install(monkeypatch)
    synth = _SlowSynth()
    synth.install(monkeypatch, request.getfixturevalue("_mock_litellm"))
    spy = _install_tool_spy(monkeypatch)

    registry = RunRegistry()
    run_id = registry.create_run(_query(), _context(), owner_id="guest:stop-before-listing")
    entry = registry.get_run(run_id)

    await asyncio.wait_for(reader.started.wait(), timeout=_WAIT_SECONDS)

    def _write_announced() -> bool:
        return any(
            event.type == "step" and event.payload == {"step": "write", "status": "started"}
            for event in entry.events
        )

    # The `step` event is written live the line before the read begins; the
    # registry's drain moves it into `entry.events` on its next turn, well
    # inside the parked read.
    for _ in range(100):
        if _write_announced():
            break
        await asyncio.sleep(0.01)

    # POPULATE-CHECKS: the run reached Write for real, and nothing of the
    # answer, not even the listing, had been sent.
    assert spy.calls > 0, "populate-check failed: no faked tool was invoked."
    assert _write_announced(), "populate-check failed: Write never announced itself before the stop."
    assert not reader.finished, "populate-check failed: the parked read had already finished."
    assert not any(event.type in _ANSWER_EVENT_TYPES for event in entry.events), (
        "populate-check failed: answer events existed before the stop, so the "
        "stop did not land before the answer."
    )
    assert not synth.started.is_set(), (
        "populate-check failed: the writing call had started, so this is not "
        "a stop before the listing."
    )

    at_stop = len(entry.events)
    registry.cancel_run(run_id)
    finished, _ = await asyncio.wait({entry.task}, timeout=_WAIT_SECONDS)
    if not finished:
        entry.task.cancel()
        await asyncio.wait({entry.task}, timeout=_WAIT_SECONDS)
        pytest.fail(f"Stop did not end the run within {_WAIT_SECONDS}s.")
    return registry, run_id, reader, synth, at_stop


@pytest.mark.asyncio
async def test_s5_a_stop_before_the_listing_ends_write_and_leaves_no_task_running(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Write's wait is cancelled, the writing call never starts, and no task
    of the run is left running.

    Mutation: make `RunRegistry.cancel_run` a no-op. The read then finishes,
    the writing call starts, and this arm goes red.
    """
    _mock_capture_run(monkeypatch)
    registry, run_id, reader, synth, _ = await _stop_before_listing(monkeypatch, request)

    assert reader.cancelled and not reader.finished, "Write's wait was not cancelled by Stop."
    assert not synth.started.is_set(), "the writing call started after Stop."
    for _ in range(5):
        await asyncio.sleep(0)
    leftovers = [
        task
        for task in asyncio.all_tasks()
        if task is not asyncio.current_task() and not task.done()
    ]
    assert not leftovers, f"tasks still running after Stop: {leftovers}"
    entry = registry.get_run(run_id)
    assert entry.task.cancelled() and entry.finished and entry.cancelled


@pytest.mark.asyncio
async def test_s6_no_answer_at_all_reaches_a_reader_after_a_stop_before_the_listing(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Card 58's S2, unchanged, for a stop before the records arrive: both
    read paths end on the `cancelled` error and no answer event exists.

    Mutation: as S5. The listing, the summary and `done` then land after
    the stop and this arm goes red.
    """
    _mock_capture_run(monkeypatch)
    registry, run_id, _reader, _synth, at_stop = await _stop_before_listing(monkeypatch, request)
    entry = registry.get_run(run_id)

    after_stop = entry.events[at_stop:]
    assert [event.type for event in after_stop] == ["error"], (
        f"after Stop the run produced {[event.type for event in after_stop]}, "
        "expected exactly one error event and nothing else."
    )
    assert after_stop[0].payload["error_class"] == "cancelled"
    assert not any(event.type in _ANSWER_EVENT_TYPES for event in entry.events)

    replayed: list[Event] = [event async for event in registry.subscribe(run_id)]
    assert replayed[-1].payload["error_class"] == "cancelled"
    assert not any(event.type in _ANSWER_EVENT_TYPES for event in replayed)

    queued: list[Event] = []
    while True:
        item = entry.queue.get_nowait()
        if item is None:
            break
        queued.append(item)
    assert not any(event.type in _ANSWER_EVENT_TYPES for event in queued)
    assert queued[-1].payload["error_class"] == "cancelled"


@pytest.mark.asyncio
async def test_s7_a_stop_before_the_listing_is_recorded_as_stopped_and_charged_once(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """One capture row, `refuse`, with no answer event, carrying the
    harness's own total once.

    Mutation: record `_observed_cost_usd(events) + metered_cost_usd` in
    `_terminal_events_for_capture`, F-58-J01's double charge. The row then
    carries twice the spend before Write and this arm goes red.
    """
    capture = _mock_capture_run(monkeypatch)
    harness_totals = _record_harness_totals(monkeypatch)
    await _stop_before_listing(monkeypatch, request)

    assert capture.await_count == 1
    _query_arg, captured = capture.await_args.args
    payload = DonePayload.model_validate(captured[-1].payload)
    assert payload.trust_outcome == "refuse"
    assert not any(event.type in _ANSWER_EVENT_TYPES for event in captured[:-1])
    assert harness_totals, "populate-check failed: the harness total was never read."
    harness_total = max(harness_totals)
    assert harness_total > 0.0, "populate-check failed: nothing was spent before Write."
    assert payload.total_cost_usd == pytest.approx(harness_total, rel=1e-9), (
        f"the stopped run recorded {payload.total_cost_usd:.6f} USD against "
        f"{harness_total:.6f} USD spent."
    )


# ---------------------------------------------------------------------------
# S8: a stop while two drafts are being written (build phase 8.7, card 50,
# option B). No writing call may outlive the stop.
# ---------------------------------------------------------------------------


class _CountingSlowSynth:
    """`_SlowSynth` for more than one writing call: counts how many started,
    were cancelled, and ran to the end."""

    def __init__(self) -> None:
        self.two_started = asyncio.Event()
        self.started = 0
        self.cancelled = 0
        self.finished = 0

    def install(self, monkeypatch: pytest.MonkeyPatch, mock_acompletion: AsyncMock) -> None:
        original = mock_acompletion.side_effect
        synth = self

        async def _slow_dispatch(*args: object, **kwargs: object):
            messages = kwargs.get("messages") or []
            joined = "\n".join(
                message.get("content") or "" for message in messages  # type: ignore[union-attr]
            )
            if SYNTH_SYSTEM_INSTRUCTION in joined:
                synth.started += 1
                if synth.started >= 2:
                    synth.two_started.set()
                try:
                    await asyncio.sleep(_SLOW_WRITE_SECONDS)
                except asyncio.CancelledError:
                    synth.cancelled += 1
                    raise
                synth.finished += 1
            return await original(*args, **kwargs)

        monkeypatch.setattr(mock_acompletion, "side_effect", _slow_dispatch)


@pytest.mark.asyncio
async def test_s8_a_stop_while_two_drafts_are_written_cancels_both_and_charges_once(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Both writing calls are cancelled, no task is left running, and the
    one row carries the harness total, both cancelled drafts included, once.

    The second draft starts beside the first only when the listing cannot
    cite a finding the writer is shown and both drafts fit the cap; both
    conditions are set here, since the offline fixture's listing cites
    every finding.

    Mutation: make `write_node`'s `finally` skip `_drop_second_draft`. The
    second draft then outlives the stop and this arm goes red.
    """
    capture = _mock_capture_run(monkeypatch)
    harness_totals = _record_harness_totals(monkeypatch)
    monkeypatch.setattr(
        graph_module,
        "_listing_uncitable",
        lambda prompt_findings, _listing_grounding: list(prompt_findings),
    )
    monkeypatch.setattr(graph_module, "_two_drafts_fit_cap", lambda _harness, _trace_id: True)
    synth = _CountingSlowSynth()
    synth.install(monkeypatch, request.getfixturevalue("_mock_litellm"))
    _install_tool_spy(monkeypatch)

    registry = RunRegistry()
    run_id = registry.create_run(_query(), _context(), owner_id="guest:stop-two-drafts")
    entry = registry.get_run(run_id)
    await asyncio.wait_for(synth.two_started.wait(), timeout=_WAIT_SECONDS)
    assert synth.started == 2, f"populate-check failed: {synth.started} writing calls started."

    at_stop = len(entry.events)
    registry.cancel_run(run_id)
    finished, _ = await asyncio.wait({entry.task}, timeout=_WAIT_SECONDS)
    if not finished:
        entry.task.cancel()
        await asyncio.wait({entry.task}, timeout=_WAIT_SECONDS)
        pytest.fail(f"Stop did not end the run within {_WAIT_SECONDS}s.")

    for _ in range(5):
        await asyncio.sleep(0)
    leftovers = [
        task
        for task in asyncio.all_tasks()
        if task is not asyncio.current_task() and not task.done()
    ]
    assert not leftovers, f"tasks still running after Stop: {leftovers}"
    assert synth.cancelled == 2 and synth.finished == 0, (
        f"of two writing calls, {synth.cancelled} were cancelled and "
        f"{synth.finished} ran to the end after Stop."
    )
    assert [event.type for event in entry.events[at_stop:]] == ["error"]
    assert not any(_is_summary_or_verdict(event) for event in entry.events)

    assert capture.await_count == 1
    _query_arg, captured = capture.await_args.args
    payload = DonePayload.model_validate(captured[-1].payload)
    assert payload.trust_outcome == "refuse"
    assert payload.total_cost_usd == pytest.approx(max(harness_totals), rel=1e-9)
