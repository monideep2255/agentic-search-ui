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

from langsmith.run_helpers import tracing_context

from system_03_search_agent.contracts.events import Event
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.graph import compiled_graph
from system_03_search_agent.core.state import GraphState
from system_03_search_agent.harness.harness import Harness


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
    """
    harness = Harness(trace_id=query.trace_id)
    initial_state: GraphState = {
        "query": query,
        "context": context,
        "harness": harness,
        "seq": 0,
        "events": [],
        "start_monotonic": time.monotonic(),
    }
    with tracing_context(enabled=False):
        final_state = await compiled_graph.ainvoke(initial_state)
    for event in final_state["events"]:
        yield event
