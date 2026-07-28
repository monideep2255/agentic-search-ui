"""The run() entry point: Section 2.1, Technical_specification.md.

T-2.0-07: `run()` is now backed by a real LangGraph `StateGraph`
(`core.graph.compiled_graph`), the five-node Guardrail -> Think -> Plan ->
Act -> Write loop, integrating every harness component built earlier in
this phase (tier resolution, `call_tier`, cost caps, per-step timeouts,
the coordinator-worker split, the prompt-cache stable-prefix scaffold).
This replaces the phase 1.0 scaffold that emitted exactly one `guard`
event then one `done` event with no real model call, no cost tracking,
and no cap enforcement; see `tests/system_03_search_agent/core/test_run.py`
for the updated event-sequence assertions this ticket requires.

Depends on:
    - system_03_search_agent.core.graph (compiled_graph)
    - system_03_search_agent.core.state (GraphState)
    - system_03_search_agent.harness.harness (Harness): one instance is
      constructed per query here, holding that query's trace_id and tier
      resolution/cost-accumulation state for the duration of the graph
      invocation (system-design-patterns.md pattern 11;
      prompt-cache-discipline.md obligation 1).

Reads:
    - Nothing directly; every environment read (model ids, cost caps,
      USER_DB_URL) happens inside the harness and cost_control modules
      the graph's nodes call.

Writes:
    - Nothing directly.

F-2.0-11 (adversary, confirmed medium, 2026-07-28): `compiled_graph.ainvoke`
accumulates every node's events inside the returned `GraphState` and only
this function ever yields them, all at once, after `ainvoke` returns. If
any node raises an exception LangGraph does not itself catch (an
unreachable `USER_DB_URL`, or any other bug in a node this phase's stub
logic did not anticipate), that exception propagates out of `ainvoke`
uncaught, and every event already produced for this query is lost with
it: the caller gets a raw exception and zero typed events, a blank
failure production-standards.md's graceful-degradation gate forbids.
`run()` wraps its `ainvoke` call in `try`/`except Exception` and, on any
otherwise-uncaught failure, yields a synthetic `error` plus `done` pair
(`trust_outcome="refuse"`) instead of letting the exception propagate.
This is a floor, not the ideal fix: it cannot recover whatever partial
events existed inside the crashed graph invocation, since `ainvoke`
gives no access to in-flight state on failure. The complete fix is
switching to `compiled_graph.astream()` so each node's events are
yielded incrementally as they are produced, which would let a crash
after node N still surface nodes 1..N's real events; that is a bigger
change appropriate for whichever phase builds real SSE streaming
(1.2/4.0), not a silent scope expansion of this fix.

T-1.2-01: `run_streaming()` below is that complete fix, landing in this
phase. `compiled_graph.astream(initial_state, stream_mode="updates")`
yields one dict per completed node, shaped `{node_name: partial_state}`,
in node-completion order, as each node actually finishes (verified
against this exact LangGraph version, 1.2.9, in an ad hoc probe script
before writing this function: a two-node graph's `astream(...,
stream_mode="updates")` yielded `{"a": {...}}` then `{"b": {...}}`, one
dict per completed node, never the whole run's history at once).
`partial_state["events"]` is that node's own new-events slice (the same
slice `_EventSink.result()` returns; see `core/graph.py`), so pulling it
out of each yielded update and yielding those `Event` objects onward
reproduces `run()`'s exact event stream, only incrementally: a consumer
iterating `run_streaming()` observes an earlier node's events before a
later, still-running node has produced its own. `run()` itself is left
completely unchanged, per this ticket's explicit instruction; the two
functions share only the crash-fallback event builder
(`_crash_fallback_events`), extracted once below and taking an optional
`start_seq` so a crash mid-stream (after some real events already
yielded) still produces a monotonically increasing `error`/`done` pair
instead of restarting the sequence at 0, which `run()`'s own call site
does not need since a crash there means `ainvoke` never returned
anything, so no real event was ever yielded before the synthetic pair.

Tracing scope note: LangSmith tracing is a phase 5.0/5.1 deliverable
(CLAUDE.md's priority table: "System 3: eval and tracing -- PLANNED"),
not built yet. LangGraph auto-attaches a LangSmith tracer to every
`ainvoke()` call whenever `LANGCHAIN_TRACING_V2`/`LANGSMITH_TRACING` is
truthy in the environment, which this repo's local `.env` sets to `true`
(with no `LANGSMITH_API_KEY`) ahead of the real tracing integration. Left
alone, running this graph would make a real, unreviewed outbound HTTPS
call to `api.smith.langchain.com` on every single query, purely as a side
effect of `.env`'s pre-existing tracing flag, with no actual tracing
project, sampling, or redaction configured on this end yet. `run()` wraps
its one `ainvoke()` call in `langsmith.run_helpers.tracing_context
(enabled=False)`, which forces tracing off for this call only (no process-
wide env mutation, so it does not disturb `.env`'s setting for whatever
component phase 5.0/5.1 eventually wires up for real). Logged in
DECISIONS.md (T-2.0-07): remove this wrapper only when a phase 5.0/5.1
ticket replaces it with an intentionally configured tracer.
"""

import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from langsmith.run_helpers import tracing_context

from system_03_search_agent.contracts.events import DonePayload, ErrorPayload, Event
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.graph import compiled_graph
from system_03_search_agent.core.state import GraphState
from system_03_search_agent.harness.harness import Harness


def _crash_fallback_events(trace_id: str, elapsed_ms: int, start_seq: int = 0) -> list[Event]:
    """Build the synthetic error/done pair yielded on an otherwise-uncaught
    exception from the graph invocation (F-2.0-11). See the module
    docstring for why this is a floor fix, not full recovery of whatever
    events the crashed invocation had already produced.

    Shared by both `run()` and `run_streaming()` (T-1.2-01), which is why
    this takes `start_seq` rather than hardcoding `seq=0`/`seq=1`: `run()`
    always calls this with the default, since a crash there means
    `ainvoke` never returned anything and no real event was ever yielded
    first. `run_streaming()` may have already yielded any number of real,
    correctly-sequenced events before a crash partway through the
    `astream` iteration, so it passes the next unused `seq` value forward
    to keep the synthetic pair monotonic with whatever real events
    preceded it, rather than restarting the sequence at 0 and violating
    the no-repeat-seq guarantee every other event in this stream holds.
    """
    error_payload = ErrorPayload(
        fatal=True,
        scope="run",
        source="core.run.run",
        error_class="unexpected",
        message="This query failed unexpectedly before it could complete.",
        retry_after_s=0,
    )
    done_payload = DonePayload(
        total_cost_usd=0.0,
        total_tool_calls=0,
        elapsed_ms=elapsed_ms,
        trust_outcome="refuse",
    )
    now = datetime.now(UTC)
    return [
        Event(
            type="error", version="v1", trace_id=trace_id, seq=start_seq, ts=now,
            payload=error_payload.model_dump(),
        ),
        Event(
            type="done", version="v1", trace_id=trace_id, seq=start_seq + 1, ts=now,
            payload=done_payload.model_dump(),
        ),
    ]


async def run(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """The single internal interface every surface calls.

    Never returns a bare string or a raw model completion. Every unit of
    output is a typed Event from the taxonomy in Section 2.3, produced by
    the real five-node graph and yielded here in the order the graph
    accumulated them (the graph's own `seq` bookkeeping, threaded through
    `GraphState.seq` and each node's `_EventSink`, already guarantees a
    monotonic, no-repeat sequence across every node that ran).

    One `Harness` is constructed per call, scoped to this query's
    `trace_id` for the duration of the graph invocation; the compiled
    graph itself is built once at import time (`core.graph.compiled_graph`)
    since its structure never varies per query.

    Never raises: an otherwise-uncaught exception from the graph
    invocation is caught here and converted into a synthetic error/done
    pair (F-2.0-11), so a caller always receives at least one schema-valid
    event sequence, never a raw exception and zero events.
    """
    start = time.monotonic()
    harness = Harness(trace_id=query.trace_id)
    initial_state: GraphState = {
        "query": query,
        "context": context,
        "harness": harness,
        "seq": 0,
        "events": [],
        "start_monotonic": start,
    }
    try:
        with tracing_context(enabled=False):
            final_state = await compiled_graph.ainvoke(initial_state)
    except Exception:  # noqa: BLE001 - the deliberate last-resort catch F-2.0-11 requires
        elapsed_ms = int((time.monotonic() - start) * 1000)
        for event in _crash_fallback_events(query.trace_id, elapsed_ms):
            yield event
        return
    for event in final_state["events"]:
        yield event


async def run_streaming(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """The incremental-streaming sibling of `run()` (T-1.2-01).

    Same inputs, same event taxonomy, same never-raises guarantee. The
    only difference is *when* the caller sees each event: `run()` drives
    `compiled_graph.ainvoke()` to completion first and only then yields
    the whole accumulated list, so a consumer sees nothing until the
    entire guardrail-think-plan-act-write loop has finished. This
    function drives `compiled_graph.astream(initial_state,
    stream_mode="updates")` instead, which yields one `{node_name:
    partial_state}` dict per node as that node itself completes (verified
    against this repo's pinned LangGraph version; see the module
    docstring). Pulling `partial_state["events"]` out of each yielded
    update and yielding those `Event` objects immediately means a
    consumer observes an earlier node's events (e.g. `guard`, `think`)
    before a later, still-running node (e.g. `plan`, `write`) has
    produced its own, real incremental streaming rather than a buffered
    replay with no observable gap.

    This is the intended entry point for a real SSE surface (`run_registry.py`,
    and the endpoints T-1.2-02 builds on top of it): a consumer that wants
    to react to each event as it happens (render a pipeline step, forward
    an SSE frame) uses this function; `run()` and the existing buffered
    `/query` endpoint are unchanged and continue to serve callers that
    only want the final, complete event list.

    Never raises, matching `run()`: any otherwise-uncaught exception from
    the `astream` iteration (F-2.0-11's crash scenario, reachable here
    too, potentially mid-stream rather than only before the first event)
    is caught and converted into a synthetic `error`/`done` pair via the
    same `_crash_fallback_events` helper `run()` uses, with `start_seq`
    advanced past whatever real events this generator already yielded so
    the synthetic pair's `seq` values stay monotonic with them.
    """
    start = time.monotonic()
    harness = Harness(trace_id=query.trace_id)
    initial_state: GraphState = {
        "query": query,
        "context": context,
        "harness": harness,
        "seq": 0,
        "events": [],
        "start_monotonic": start,
    }
    next_seq = 0
    try:
        with tracing_context(enabled=False):
            async for update in compiled_graph.astream(initial_state, stream_mode="updates"):
                for partial_state in update.values():
                    for event in partial_state.get("events", []):
                        next_seq = max(next_seq, event.seq + 1)
                        yield event
    except Exception:  # noqa: BLE001 - mirrors run()'s deliberate last-resort catch, F-2.0-11
        elapsed_ms = int((time.monotonic() - start) * 1000)
        for event in _crash_fallback_events(query.trace_id, elapsed_ms, start_seq=next_seq):
            yield event
