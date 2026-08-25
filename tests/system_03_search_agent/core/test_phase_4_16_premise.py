"""Build phase 4.16's premise gate: the Act step must be visible on the wire.

WHAT THIS GATE IS FOR. The product owner ran the deployed demo on
2026-08-24 and reported "streaming does not work properly" and "the search
is super super super super slow". Measured on the deployed API on
2026-08-25 by timestamping each SSE frame as it arrived:

    [ 0.15s] guard
    [ 0.15s] think
    [ 1.41s] plan
    [12.32s] token, token, citation x3, trust_signal x4, done   (10ms apart)

Ten point nine seconds of total silence, which is the whole Act step. The
wire is not buffered, and `useAgentRun` consumes it correctly. The cause is
that `core/graph.py` never calls `sink.emit` with `tool_start` or
`tool_result`. Both types are in `contracts/events.py` and the CLI, MCP and
GraphQL adapters all handle them; only the producer is missing.

THE ARM THAT MATTERS IS THE TIMING ONE, and this docstring says so up front
because the obvious gate would pass the wrong fix. Events are accumulated
per node by `_EventSink` and flushed when the node RETURNS, since
`run_streaming` drives `astream(stream_mode="updates")`. So emitting
`tool_start` inside `act_node`'s loop, which is the fix that first suggests
itself, would deliver every tool event in one burst immediately before the
tokens and leave the silence exactly as long. A gate that only asserted
PRESENCE would go green on that fix while the defect a person reported
stayed unchanged.

So A3 below patches the tool to sleep and asserts the `tool_start` frame
ARRIVED while the tool was still running. That is a fact about when the
reader sees it, not about whether the list contains it, and it is the
difference between the two fixes. This is build phase 4.3's lesson applied
before the fact: check the value, not a correlate of it.

EVERY ARM CARRIES A POPULATE-CHECK, per build phases 4.7 and 4.11. Three
phases running have produced vacuous arms, and in 4.7 the repair for a
vacuous arm was itself vacuous. A negative or comparative assertion here
must first prove the thing it measures was available to be measured: that a
tool was actually dispatched, and in A3 that the sleep actually happened.
An arm that cannot distinguish "the control held" from "nothing happened"
is not an arm.

WHAT THIS GATE CANNOT YET PROVE ABOUT ITSELF, recorded at the moment it was
watched failing rather than left for a reviewer to find. All five arms go
red against the current tree for the right reason, with every populate-check
passing FIRST, which is the property that makes them arms rather than
decoration. But A3 currently stops at its "no tool_start was emitted at all"
line and never reaches its timing comparison. So the timing assertion, which
is the whole reason A3 exists and the only thing separating the correct fix
from the one that changes nothing, is UNEXERCISED today. Presence alone
cannot demonstrate it can fail for a timing reason.

That is not closed by reading it. T-4.16-07's mutation harness must carry a
mutation that emits both tool frames from inside `act_node` and flushes them
at node return, the plausible wrong fix, and assert A3 goes red on the
TIMING branch specifically rather than on the presence branch. Until that
mutation exists and has been seen red, treat A3 as an assertion of intent.
A4 has the same shape in weaker form: its populate-check is currently what
fails, so it proves nothing today that A1 does not already prove.

COVERAGE, stated here so a gap in it is arguable rather than discovered
(`goal-contracts`, and build phase 4.4's stated-blind-spot lesson):

  Exercised:
    - A run that dispatches two tools across two layers (cypher_query on
      Layer 1, ncbi_efetch on Layer 2), which is the shape the reported
      BRCA1 question actually produces in production.
    - Arrival TIME of a tool frame relative to the tool's own runtime.
    - Pairing of tool_start to tool_result by call_id.
    - Schema validity of both new payload types.

  Deliberately NOT exercised, and named rather than implied:
    - The real model and the real graph. This gate runs offline against
      the dispatching model stub, so it proves the EVENTS are produced and
      when, never that a tool returned correct biomedical content. That is
      what the live tool gates already own.
    - A zero-tool run. A query that dispatches nothing correctly emits no
      tool events, so it cannot distinguish the fix from the defect and is
      not an arm here.
    - The frontend. Whether `useRunView` renders a chip from these frames
      is build phase 4.16's separate frontend gate, not this file.
    - Wall-clock latency of the Act step itself. This gate asserts the wait
      is LEGIBLE, never that it is short. T-4.16-08 owns whether any
      residue of "slow" survives once the wait is visible.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.contracts.events import PAYLOAD_MODEL_BY_TYPE
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.run import run_streaming
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.tools.cypher_schemas import (
    CypherQueryOutput,
    CypherQueryRow,
)

# The question this phase was opened against. It resolves BRCA1 and plans
# two tool calls, one per layer, which is the production shape the reported
# defect was observed on rather than a shape chosen for convenience.
_QUERY_TEXT = "What gene is associated with BRCA1?"

# How long the faked Layer 1 tool blocks for in A3. Long enough that a
# frame flushed at node return is unambiguously distinguishable from one
# written at dispatch, short enough not to slow the offline suite. The
# assertion threshold is half of it, so ordinary scheduling jitter cannot
# flip the arm either way.
_SLOW_TOOL_SECONDS = 1.5
_ARRIVAL_MARGIN_SECONDS = _SLOW_TOOL_SECONDS / 2


def _fake_response(content: str = "ok", prompt_tokens: int = 10, completion_tokens: int = 5):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        ),
    )


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("PER_USER_DAILY_QUERY_CAP", "100")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")
    monkeypatch.setenv("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")


@pytest.fixture(autouse=True)
def _no_op_daily_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same rationale as `test_run.py`'s identical fixture: the two
    DB-backed daily caps have their own suite in `test_cost_control.py`
    and this file is not re-proving them.

    Both replacements are SYNC, because both call sites are sync. The
    first draft of this fixture made them `async` and every run logged
    `coroutine ... was never awaited` while the cap silently did not run.
    That is a stub whose shape does not match the seam it replaces, which
    passes quietly and would have made any cap-related arm here vacuous.
    """

    def _user_check(session, user_id, **kwargs):
        return None

    def _system_check(session, **kwargs):
        return None

    monkeypatch.setattr(cost_control, "check_user_daily_query_cap", _user_check)
    monkeypatch.setattr(cost_control, "check_system_daily_cost_cap", _system_check)


@pytest.fixture(autouse=True)
def _stub_symbol_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """T-3.1-11 made gene-symbol resolution a live NCBI call and
    `_QUERY_TEXT` names BRCA1. Same fixture as `test_run.py`."""
    from system_03_search_agent.core import graph as graph_module

    known = {"BRCA1": "NCBIGene:672", "TP53": "NCBIGene:7157"}

    async def _fake_resolve_symbol_to_curie(symbol: str, **kwargs: object) -> str | None:
        return known.get(symbol.strip().upper())

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _fake_resolve_symbol_to_curie)


@pytest.fixture(autouse=True)
def _mock_litellm(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    from tests.system_03_search_agent.model_stub import install_dispatching_acompletion

    return install_dispatching_acompletion(monkeypatch, harness_module)


def _cypher_output() -> CypherQueryOutput:
    return CypherQueryOutput(
        status="ok",
        row_count=1,
        total_available=1,
        truncated=False,
        rows=[
            CypherQueryRow(
                node_or_edge_type="Gene",
                curie="NCBIGene:672",
                fields={"name": "BRCA1 DNA repair associated"},
                source_url="https://www.ncbi.nlm.nih.gov/gene/672",
                graph_snapshot_version="v1",
            )
        ],
        error=None,
    )


class _ToolSpy:
    """Records that the faked tool actually ran, and for how long.

    This exists for the populate-checks rather than for the assertions.
    Every arm below that compares a timing or asserts a pairing first reads
    this to prove the dispatch it is reasoning about really happened. An
    arm that merely found no `tool_start` in a run that dispatched no tool
    would pass while proving nothing, which is the exact vacuity shape
    build phases 4.7 and 4.11 both shipped.
    """

    def __init__(self, sleep_seconds: float = 0.0) -> None:
        self.sleep_seconds = sleep_seconds
        self.calls = 0
        self.elapsed = 0.0

    async def cypher_query(self, *args: object, **kwargs: object) -> CypherQueryOutput:
        self.calls += 1
        started = time.monotonic()
        if self.sleep_seconds:
            await asyncio.sleep(self.sleep_seconds)
        self.elapsed += time.monotonic() - started
        return _cypher_output()

    async def ncbi_efetch(self, *args: object, **kwargs: object):
        from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput

        self.calls += 1
        return NcbiEfetchOutput(
            status="empty",
            action="dataset_report",
            records=[],
            record_count=0,
            total_available=None,
            truncated=False,
            error=None,
        )


def _install_tool_spy(monkeypatch: pytest.MonkeyPatch, sleep_seconds: float = 0.0) -> _ToolSpy:
    from system_03_search_agent.core import graph as graph_module

    spy = _ToolSpy(sleep_seconds=sleep_seconds)
    monkeypatch.setattr(graph_module, "cypher_query", spy.cypher_query)
    monkeypatch.setattr(graph_module, "ncbi_efetch", spy.ncbi_efetch)
    return spy


def _query() -> Query:
    return Query(
        text=_QUERY_TEXT,
        session_id="session-4-16",
        trace_id="trace-4-16",
        user_id=None,
        audience_depth="researcher",
    )


def _context() -> RequestContext:
    return RequestContext(surface="web_ui", session_memory=None, operator_mode=False)


async def _collect_with_arrival_times(
    query: Query, context: RequestContext
) -> list[tuple[float, object]]:
    """Drive the real loop and record WHEN each event reached the consumer.

    The arrival time is taken here, at the consumer, not from the event's
    own `ts` field. `ts` is stamped inside `_EventSink.emit`, so a batch of
    events emitted during a node and flushed at its return carry
    well-separated timestamps while arriving together. Reading `ts` would
    therefore make A3 pass on the very fix A3 exists to reject. This is the
    same distinction as DOM order versus visual order in build phase 4.8's
    F-4.8-P-03: the field that looks like the measurement is not it.
    """
    started = time.monotonic()
    collected: list[tuple[float, object]] = []
    async for event in run_streaming(query, context):
        collected.append((time.monotonic() - started, event))
    return collected


def _planned_tool_count(events: list[object]) -> int:
    plan_events = [e for e in events if e.type == "plan"]
    if not plan_events:
        return 0
    return len(plan_events[-1].payload.get("tool_calls", []))


# ---------------------------------------------------------------------------
# A1: the Act step produces events at all.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a1_a_dispatching_run_emits_a_tool_start_for_every_planned_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spy = _install_tool_spy(monkeypatch)
    events = [event async for event in run_streaming(_query(), _context())]

    # POPULATE-CHECK. Without this, a run that planned nothing and
    # dispatched nothing would make the assertion below trivially true of
    # zero, and the arm would be green on a broken build.
    planned = _planned_tool_count(events)
    assert planned > 0, (
        "populate-check failed: the run planned no tool calls, so this arm "
        "cannot distinguish a missing tool_start from a run that never "
        "dispatched. Fix the fixture, not the assertion."
    )
    assert spy.calls > 0, (
        "populate-check failed: no faked tool was actually invoked, so no "
        "tool_start could have been produced by any implementation."
    )

    tool_starts = [e for e in events if e.type == "tool_start"]
    assert len(tool_starts) == planned, (
        f"the plan dispatched {planned} tool call(s) and the stream carried "
        f"{len(tool_starts)} tool_start event(s). The Act step is invisible "
        "to every consumer of this stream."
    )


@pytest.mark.asyncio
async def test_a2_every_tool_start_is_closed_by_a_tool_result_for_the_same_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spy = _install_tool_spy(monkeypatch)
    events = [event async for event in run_streaming(_query(), _context())]

    planned = _planned_tool_count(events)
    assert planned > 0, "populate-check failed: no tool call was planned."
    assert spy.calls > 0, "populate-check failed: no faked tool was invoked."

    starts = [e for e in events if e.type == "tool_start"]
    results = [e for e in events if e.type == "tool_result"]
    assert starts, "no tool_start event was emitted at all."

    start_ids = [e.payload["call_id"] for e in starts]
    result_ids = [e.payload["call_id"] for e in results]
    assert sorted(start_ids) == sorted(result_ids), (
        "tool_start and tool_result must pair 1:1 by call_id: "
        f"started {sorted(start_ids)}, resulted {sorted(result_ids)}. An "
        "unclosed call leaves a chip spinning for ever."
    )
    for call_id in start_ids:
        first_start = next(i for i, e in enumerate(events) if e.type == "tool_start" and e.payload["call_id"] == call_id)
        first_result = next(i for i, e in enumerate(events) if e.type == "tool_result" and e.payload["call_id"] == call_id)
        assert first_start < first_result, (
            f"call {call_id} reported its result before it reported starting."
        )


# ---------------------------------------------------------------------------
# A3: THE ARM THAT DISTINGUISHES THE TWO FIXES.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a3_tool_start_reaches_the_consumer_while_the_tool_is_still_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reported defect, stated as a property of arrival time.

    A `tool_start` emitted inside `act_node` and flushed at node return
    arrives with `done`, which is what the reader experiences as silence.
    A `tool_start` written to the stream at dispatch arrives while the tool
    is still working, which is what both design artifacts show.

    Only the second passes this arm, and that is the entire point of it.
    """
    spy = _install_tool_spy(monkeypatch, sleep_seconds=_SLOW_TOOL_SECONDS)
    arrivals = await _collect_with_arrival_times(_query(), _context())
    events = [event for _, event in arrivals]

    # POPULATE-CHECK, two halves. The first proves a tool ran; the second
    # proves it actually blocked for the time this arm measures against. If
    # the sleep did not happen, every arrival collapses toward zero and the
    # comparison below reads a value that CANNOT take the failing value,
    # which is precisely the shape that survived its own repair in build
    # phase 4.7.
    assert spy.calls > 0, "populate-check failed: no faked tool was invoked."
    assert spy.elapsed >= _SLOW_TOOL_SECONDS * 0.9, (
        f"populate-check failed: the faked tool reported {spy.elapsed:.2f}s of "
        f"work against an intended {_SLOW_TOOL_SECONDS}s. This arm compares "
        "arrival times against that runtime, so without it the comparison is "
        "inert."
    )

    starts = [(at, e) for at, e in arrivals if e.type == "tool_start"]
    assert starts, (
        "no tool_start event was emitted at all, so the Act step is silent "
        "for its entire duration."
    )

    done_at = next(at for at, e in arrivals if e.type == "done")
    first_start_at = starts[0][0]
    lead = done_at - first_start_at

    assert lead >= _ARRIVAL_MARGIN_SECONDS, (
        f"the first tool_start reached the consumer {lead:.2f}s before done, "
        f"against a required {_ARRIVAL_MARGIN_SECONDS:.2f}s. The tool blocked "
        f"for {spy.elapsed:.2f}s, so a frame arriving this late was flushed at "
        "node return rather than written at dispatch. The event list is "
        "correct and the reader still watches a silent screen, which is the "
        "defect this phase was opened for."
    )

    # And the same property stated against the answer rather than the end of
    # the run, because a reader's complaint is about the wait before content.
    token_arrivals = [at for at, e in arrivals if e.type == "token"]
    if token_arrivals:
        assert first_start_at <= token_arrivals[0], (
            "a tool_start arrived after the first answer token, so the tool "
            "chip would appear underneath an answer that is already written."
        )
    _ = events


# ---------------------------------------------------------------------------
# A4: the frames are well-formed and say which layer was read.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a4_every_tool_frame_is_schema_valid_and_names_its_tool_and_layer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spy = _install_tool_spy(monkeypatch)
    events = [event async for event in run_streaming(_query(), _context())]

    assert spy.calls > 0, "populate-check failed: no faked tool was invoked."
    frames = [e for e in events if e.type in {"tool_start", "tool_result"}]
    assert frames, "populate-check failed: no tool frame was produced to validate."

    for event in frames:
        PAYLOAD_MODEL_BY_TYPE[event.type].model_validate(event.payload)

    tools = {e.payload["tool"] for e in frames}
    layers = {e.payload["layer"] for e in frames}
    assert "cypher_query" in tools, (
        f"the Layer 1 call is not named on any tool frame; saw {sorted(tools)}. "
        "The chip's colour is driven by the layer, so an unnamed tool renders "
        "as an uncoloured chip."
    )
    assert "layer_1_graph" in layers, (
        f"no tool frame reports Layer 1; saw {sorted(layers)}."
    )


# ---------------------------------------------------------------------------
# A5: the reported defect, stated exactly as a person experiences it.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a5_no_silent_gap_between_plan_and_the_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """"The search is super super super super slow."

    Stated as a checkable property: after `plan` lands, something must
    reach the reader before the answer does. This is the arm that is
    written in the reporter's terms rather than the implementation's, so
    that a future fix which satisfies A1 to A4 by some other mechanism
    still has to satisfy the complaint.
    """
    spy = _install_tool_spy(monkeypatch, sleep_seconds=_SLOW_TOOL_SECONDS)
    events = [event async for event in run_streaming(_query(), _context())]

    assert spy.calls > 0, "populate-check failed: no faked tool was invoked."
    types = [e.type for e in events]
    assert "plan" in types, "populate-check failed: the run produced no plan event."

    plan_index = len(types) - 1 - types[::-1].index("plan")
    terminal = next(
        (i for i, t in enumerate(types) if t in {"token", "done"} and i > plan_index),
        None,
    )
    assert terminal is not None, "populate-check failed: the run never reached an answer."

    between = [t for t in types[plan_index + 1 : terminal] if t != "cost"]
    assert between, (
        "nothing at all is emitted between plan and the answer, so the reader "
        f"sees a frozen stepper for the whole Act step. Event types were "
        f"{types}."
    )
