"""UI fix set 11.16's premise gate: the Write step must be visible on the wire.

WHAT THIS GATE IS FOR. Measured on develop on 2026-09-14 (`testing/Developer/
reports/2026-09-14_handover_inputs/streamcheck/findings.md`), six live runs:
every `token`, `citation` and `trust_signal` of an answer arrived within 1.3
to 216.7 ms of each other, after a silent gap of 1.9 to 22.6 seconds
following Act's last `tool_result`. The cause is the same shape build phase
4.16 fixed for `act_node`: `write_node` emitted every answer event with
`_EventSink.emit`, which only appends to the node's list, so nothing left
the node until it returned.

Two things change, and each has an arm here:

- `write_node` announces that it has begun, as a `step` event, the moment
  its normal answer path starts and BEFORE the synth call. That is the one
  new envelope type this set adds, additive under system-design-patterns
  pattern 10, and the shape the web client's `FORWARD_COMPATIBLE_EVENT_NAMES`
  already skips by name.
- Every grounded `token`, and its `citation` and `trust_signal` events, go
  through `_EventSink.emit_live` at the point they are produced, so they
  reach a reader while the node is still running its own bookkeeping.

WHAT DOES NOT CHANGE, and W3 and W4 pin it: the grounding pass, cite-or-
refuse and every refusal path. Only the emit MECHANISM changes for output
that is already grounded. Nothing here streams a model's raw draft.

THE ARM THAT MATTERS IS W1, and this docstring says so up front for the same
reason 4.16's did: the plausible wrong fix passes a presence gate. If
someone reverts `emit_live` back to `emit` inside `write_node`, every event
still exists, in the right order, with the right payloads, and every arm
that only reads the finished event list stays green. W1 therefore records
what actually passed through LangGraph's stream writer DURING the run and
asserts each grounded write event was handed to it before `write_node`
called `result()`. The populate-check for that arm is deliberately
independent of the code under test: it requires a live write from
`act_node`, which build phase 4.16 already proved, so a mutation that
degrades `write_node` alone goes red at the assertion and not at the
populate-check.

EVERY ARM CARRIES A POPULATE-CHECK, per build phases 4.7 and 4.11.

COVERAGE, stated so a gap in it is arguable rather than discovered:

  Exercised:
    - The production BRCA1 shape from 4.16's gate: two tool calls across
      two layers, a grounded narrative that cites its findings, so tokens,
      citations and trust signals are all present to be measured.
    - Which channel each grounded write event took (W1), the ARRIVAL TIME of
      the `step` event relative to a synth call that is made to block (W2),
      content and order parity between the buffered and live paths (W3), and
      a refusal decided before the synth call (W4).

  Deliberately NOT exercised, and named rather than implied:
    - Arrival TIME of the tokens themselves. Nothing in `write_node` awaits
      after the token loop, so a token written live and one flushed at
      return reach the consumer microseconds apart; the channel is the
      measurable property, which is why W1 records the writer rather than
      a clock. W2 measures time only for the `step` event, which precedes
      a real await (the synth call).
    - The real model and the real graph. Offline, like 4.16's gate.
    - The frontend. Whether `useRunView` reads the `step` frame is a later
      set; this set only proves the frame cannot end a run there, which
      `useAgentRun.forwardCompat.test.ts` already owns.
    - The `cap_exceeded` and `step_error` early returns. Both keep plain
      `emit` and return immediately, so there is no live-versus-buffered
      distinction to measure; W4 covers the refusal family through the
      unresolved-symbol branch, which shares that shape.
"""

from __future__ import annotations

import asyncio
import json
import re
import time

import pytest

from system_03_search_agent.contracts.events import PAYLOAD_MODEL_BY_TYPE, Event
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.core.run import run, run_streaming
from system_03_search_agent.synthesis.findings import SYNTH_SYSTEM_INSTRUCTION

# The gate's autouse fixtures and the run shape, re-registered here rather
# than copied, for the reason `test_phase_4_16_mutation.py` records: one
# definition each, so this gate grades the same setup as 4.16's.
from tests.system_03_search_agent.core.test_phase_4_16_premise import (  # noqa: F401
    _context,
    _env,
    _install_tool_spy,
    _mock_litellm,
    _no_op_daily_caps,
    _query,
    _stub_symbol_resolution,
)

# The three answer event types `write_node` produces from grounded output,
# plus the marker it announces itself with. Every one is produced by
# `write_node` and by no other node, which is what lets W1 attribute a live
# write to the code under test by type alone.
_WRITE_EVENT_TYPES = frozenset({"token", "citation", "trust_signal"})

# How long the faked synth call blocks for in W2. Same reasoning as 4.16's
# `_SLOW_TOOL_SECONDS`: long enough that a frame flushed at node return is
# unambiguous, short enough for the offline suite, threshold at half.
_SLOW_SYNTH_SECONDS = 1.5
_ARRIVAL_MARGIN_SECONDS = _SLOW_SYNTH_SECONDS / 2


class _WriterRecorder:
    """Records every event handed to LangGraph's stream writer, in order,
    interleaved with a marker for each node return.

    The marker is taken at `_EventSink.result`, which is the last thing a
    node does before returning its update. So an entry recorded before the
    write node's marker was handed to the writer while `write_node` was
    still running, which is the property this set exists to establish.
    """

    def __init__(self) -> None:
        self.timeline: list[tuple[str, object]] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import langgraph.config as langgraph_config

        real_get_stream_writer = langgraph_config.get_stream_writer
        recorder = self

        def _recording_get_stream_writer():
            real_writer = real_get_stream_writer()

            def _writer(payload: object) -> None:
                event = payload.get("event") if isinstance(payload, dict) else None
                recorder.timeline.append(("live", event))
                real_writer(payload)

            return _writer

        original_result = graph_module._EventSink.result

        def _marking_result(sink: graph_module._EventSink, **extra: object):
            recorder.timeline.append(
                ("return", frozenset(event.type for event in sink.new_events))
            )
            return original_result(sink, **extra)

        # `emit_live` imports `get_stream_writer` from `langgraph.config` at
        # call time, so patching the module attribute is the seam it reads.
        monkeypatch.setattr(langgraph_config, "get_stream_writer", _recording_get_stream_writer)
        monkeypatch.setattr(graph_module._EventSink, "result", _marking_result)

    def live_seqs(self) -> set[int]:
        return {
            entry.seq
            for kind, entry in self.timeline
            if kind == "live" and isinstance(entry, Event)
        }

    def live_types(self) -> set[str]:
        return {
            entry.type
            for kind, entry in self.timeline
            if kind == "live" and isinstance(entry, Event)
        }

    def index_of_write_node_return(self) -> int | None:
        for index, (kind, entry) in enumerate(self.timeline):
            if kind == "return" and "done" in entry:
                return index
        return None


class _SynthDelay:
    """Makes the stubbed synth call block, and records that it did."""

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        self.slept = 0.0
        self.synth_calls = 0

    def install(self, monkeypatch: pytest.MonkeyPatch, mock_acompletion) -> None:
        original = mock_acompletion.side_effect
        delay = self

        async def _slow_dispatch(*args: object, **kwargs: object):
            messages = kwargs.get("messages") or []
            joined = "\n".join(
                message.get("content") or "" for message in messages  # type: ignore[union-attr]
            )
            if SYNTH_SYSTEM_INSTRUCTION in joined:
                delay.synth_calls += 1
                started = time.monotonic()
                await asyncio.sleep(delay.seconds)
                delay.slept += time.monotonic() - started
            return await original(*args, **kwargs)

        monkeypatch.setattr(mock_acompletion, "side_effect", _slow_dispatch)


def _stable_payload(payload: dict) -> str:
    """A payload with the one per-run value removed: `plan_node` mints a
    fresh `cq-<12 hex>` call id every run, and it threads into each token's
    `marker_ids` and each citation's `citation_id`. Two runs therefore never
    match byte for byte, and that id is minted upstream of Write, so W3
    compares everything else."""
    return re.sub(r"cq-[0-9a-f]{12}", "cq-X", json.dumps(payload, sort_keys=True))


async def _collect_with_arrival_times(query, context) -> list[tuple[float, Event]]:
    """Arrival time at the CONSUMER, never the event's own `ts`, for the
    reason 4.16's gate records: `ts` is stamped at emit, so a batch flushed
    at node return carries well-separated stamps while arriving together."""
    started = time.monotonic()
    collected: list[tuple[float, Event]] = []
    async for event in run_streaming(query, context):
        collected.append((time.monotonic() - started, event))
    return collected


# ---------------------------------------------------------------------------
# W1: THE ARM THAT DISTINGUISHES THE TWO FIXES.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_w1_every_grounded_write_event_reaches_the_stream_writer_before_write_node_returns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each `token`, `citation` and `trust_signal` the run produced was handed
    to LangGraph's stream writer, and was handed to it before `write_node`
    built its return value. A `write_node` that still uses `sink.emit` for
    them produces the identical event list and fails here, because those
    events never touch the writer at all."""
    recorder = _WriterRecorder()
    recorder.install(monkeypatch)
    spy = _install_tool_spy(monkeypatch)

    events = [event async for event in run_streaming(_query(), _context())]

    # POPULATE-CHECK, three halves. A tool ran; the run produced every
    # write event type this arm measures; and the recorder saw at least
    # one live write from a node OTHER than write_node (act_node's
    # `tool_start`, build phase 4.16's control), which proves the seam is
    # live in this run without relying on the code under test.
    assert spy.calls > 0, "populate-check failed: no faked tool was invoked."
    produced = {event.type for event in events}
    assert _WRITE_EVENT_TYPES <= produced, (
        "populate-check failed: the run did not produce every write event "
        f"type this arm measures; saw {sorted(produced)}. Fix the fixture, "
        "not the assertion."
    )
    assert "tool_start" in recorder.live_types(), (
        "populate-check failed: no live write from act_node reached the "
        "recorder, so the writer seam is not live in this run and the "
        "assertion below could not take the passing value."
    )
    write_return_index = recorder.index_of_write_node_return()
    assert write_return_index is not None, (
        "populate-check failed: write_node's return was never marked."
    )

    expected = {event.seq for event in events if event.type in _WRITE_EVENT_TYPES}
    live_before_return = {
        entry.seq
        for kind, entry in recorder.timeline[:write_return_index]
        if kind == "live" and isinstance(entry, Event)
    }
    missing = sorted(expected - live_before_return)
    assert not missing, (
        f"{len(missing)} of {len(expected)} grounded write events (seq {missing}) "
        "were never handed to the stream writer before write_node returned: "
        "they were flushed at node return. The event list is correct and the "
        "reader still watches a silent screen until the whole answer lands, "
        "which is the defect this set was opened for."
    )


# ---------------------------------------------------------------------------
# W2: the Write step announces itself before the synth call returns.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_w2_the_step_event_reaches_the_consumer_while_the_synth_call_is_still_running(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """The one place in `write_node` where a live write is measurable by
    time: the `step` marker is written before the synth call, and the synth
    call is a real await. Made to block here, so a marker flushed at node
    return arrives with `done` and a marker written live arrives first."""
    delay = _SynthDelay(_SLOW_SYNTH_SECONDS)
    delay.install(monkeypatch, request.getfixturevalue("_mock_litellm"))
    spy = _install_tool_spy(monkeypatch)

    arrivals = await _collect_with_arrival_times(_query(), _context())

    # POPULATE-CHECK: the synth call actually blocked for the time this arm
    # measures against. Without it every arrival collapses toward zero.
    assert spy.calls > 0, "populate-check failed: no faked tool was invoked."
    assert delay.synth_calls > 0, "populate-check failed: the synth call never ran."
    assert delay.slept >= _SLOW_SYNTH_SECONDS * 0.9, (
        f"populate-check failed: the faked synth call blocked {delay.slept:.2f}s "
        f"against an intended {_SLOW_SYNTH_SECONDS}s, so the comparison is inert."
    )

    steps = [(at, event) for at, event in arrivals if event.type == "step"]
    assert steps, (
        "no step event was emitted at all, so the Write step is silent from "
        "Act's last tool_result until the answer lands."
    )
    step_at, step_event = steps[0]
    PAYLOAD_MODEL_BY_TYPE["step"].model_validate(step_event.payload)
    assert step_event.payload == {"step": "write", "status": "started"}, (
        f"the step event carries {step_event.payload!r}; the web client's "
        "forward-compatibility test expects step=write, status=started."
    )

    done_at = next(at for at, event in arrivals if event.type == "done")
    lead = done_at - step_at
    assert lead >= _ARRIVAL_MARGIN_SECONDS, (
        f"the step event reached the consumer {lead:.2f}s before done, against "
        f"a required {_ARRIVAL_MARGIN_SECONDS:.2f}s. The synth call blocked for "
        f"{delay.slept:.2f}s, so a marker arriving this late was flushed at "
        "node return rather than written at Write's start."
    )
    first_token_at = next(at for at, event in arrivals if event.type == "token")
    assert step_at <= first_token_at, (
        "the step event arrived after the first answer token, so it announced "
        "a step that had already finished."
    )


# ---------------------------------------------------------------------------
# W3: the live path changes WHEN, never WHAT.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_w3_the_live_path_yields_the_same_write_events_in_the_same_order_as_the_buffered_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`run()` never uses the live channel (`get_stream_writer` is a no-op
    under `ainvoke`), so it is the reference for what the node's own state
    holds. `run_streaming` must yield the same types in the same order, the
    same grounded payloads, every seq exactly once and strictly increasing.
    Volatile fields (`elapsed_ms`, costs) are excluded by comparing only the
    write event payloads plus the full type sequence."""
    _install_tool_spy(monkeypatch)
    buffered = [event async for event in run(_query(), _context())]
    _install_tool_spy(monkeypatch)
    live = [event async for event in run_streaming(_query(), _context())]

    assert any(event.type == "token" for event in buffered), (
        "populate-check failed: the buffered run produced no answer token."
    )
    assert any(event.type == "citation" for event in buffered), (
        "populate-check failed: the buffered run produced no citation."
    )

    assert [event.type for event in live] == [event.type for event in buffered], (
        "the live path yields a different event sequence from the buffered "
        f"path:\n live     {[e.type for e in live]}\n buffered {[e.type for e in buffered]}"
    )
    compared = _WRITE_EVENT_TYPES | {"step"}
    assert [
        (event.type, _stable_payload(event.payload)) for event in live if event.type in compared
    ] == [
        (event.type, _stable_payload(event.payload))
        for event in buffered
        if event.type in compared
    ], "a grounded write event differs in content between the live and buffered paths."
    for stream_name, stream in (("live", live), ("buffered", buffered)):
        seqs = [event.seq for event in stream]
        assert seqs == sorted(set(seqs)), (
            f"the {stream_name} stream's seq is not strictly increasing with no "
            f"repeats: {seqs}. run_streaming de-duplicates by seq, so a repeat "
            "here means a live-written event escaped that guard."
        )

    # The Section 8 order a consuming surface relies on, unchanged: every
    # token before the first citation, every citation before the first
    # trust signal, the answer-scope verdict last among them.
    types = [event.type for event in live]
    assert max(i for i, t in enumerate(types) if t == "token") < min(
        i for i, t in enumerate(types) if t == "citation"
    ), "a token followed a citation."
    assert max(i for i, t in enumerate(types) if t == "citation") < min(
        i for i, t in enumerate(types) if t == "trust_signal"
    ), "a citation followed a trust signal."
    trust = [event for event in live if event.type == "trust_signal"]
    assert trust[-1].payload.get("scope") == "answer", (
        "the last trust signal is not the answer-scope verdict."
    )
    step_index = types.index("step")
    assert step_index < types.index("token") and types[step_index - 1] in {
        "tool_result",
        "cost",
        "plan",
    }, f"the step marker is not at Write's start: {types}"


# ---------------------------------------------------------------------------
# W4: a refusal decided before the synth call is untouched.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_w4_a_refusal_decided_before_the_synth_call_never_announces_write_and_never_calls_synth(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """The unresolved-symbol refusal (T-3.1-13) returns from `write_node`
    before its normal answer path begins. It must keep its three-event
    shape, carry no `step` marker, and spend no synth call."""

    async def _nothing_resolves(symbol: str, **kwargs: object) -> str | None:
        return None

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _nothing_resolves)
    delay = _SynthDelay(0.0)
    delay.install(monkeypatch, request.getfixturevalue("_mock_litellm"))
    spy = _install_tool_spy(monkeypatch)

    events = [event async for event in run_streaming(_query(), _context())]

    refusals = [
        event
        for event in events
        if event.type == "trust_signal" and event.payload.get("outcome") == "refuse"
    ]
    assert refusals, (
        "populate-check failed: the run did not refuse, so it never took the "
        f"branch this arm pins. Types were {[e.type for e in events]}."
    )
    assert spy.calls == 0, (
        "populate-check failed: a tool ran, so this was not the pre-Act refusal."
    )

    assert not any(event.type == "step" for event in events), (
        "a refusal that never began the answer path announced that Write "
        "had started."
    )
    assert delay.synth_calls == 0, "the refusal path spent a synth call."
    write_types = [event.type for event in events if event.type in _WRITE_EVENT_TYPES | {"done"}]
    assert write_types == ["token", "trust_signal", "done"], (
        f"the refusal's event shape changed: {write_types}."
    )
