"""GraphState: the state threaded through the five-node LangGraph loop (T-2.0-07).

Spec: Technical_specification.md Section 3.2 (429-448); tracker/phase_2.0.md
T-2.0-07.

Depends on:
    - system_03_search_agent.contracts.events (Event)
    - system_03_search_agent.contracts.query (Query, RequestContext)
    - system_03_search_agent.harness.harness (Harness, QueryClass)

Reads:
    - Nothing at import time.

Writes:
    - Nothing. A pure type declaration.

A plain `TypedDict` rather than a dataclass: LangGraph's `StateGraph`
constructor is built around annotated `TypedDict` (or Pydantic model)
schemas so it can tell, field by field, whether a key uses the default
"last write wins" merge or a custom reducer. `events` is the one field
that needs a reducer: each node emits only the new events it produced,
and `Annotated[list[Event], add]` tells LangGraph to concatenate those
onto whatever the graph has accumulated so far, rather than overwriting
the whole history with just the latest node's slice. Every other field
here is a scalar or a small structure a node fully replaces, so plain
"last write wins" (no `Annotated` wrapper) is correct for those: the one
node that sets a field is always the one whose value should stick, since
the graph runs one node at a time with no concurrent writers to the same
key in this five-node linear sequence.

`total=False`: no single node call ever needs to supply every key, since
each node returns a partial update dict (LangGraph merges it onto the
running state), not a full snapshot.

Field lifecycle:
    Set once, by `core.run.run()`, before the graph is ever invoked:
        query, context, harness, seq, events (starts as `[]`),
        start_monotonic

    Set by individual nodes as the loop progresses:
        query_class: set by `think`, read by `plan`/`act`/`write` (via
            `harness.harness.budget_for_query_class`) to resolve every
            later node's per-step timeout budget from Think's emitted
            classification (T-2.0-04's mapping), per the ticket's
            explicit instruction that Think's stub `query_class` output
            still drives real budget resolution downstream even though
            the classification itself is not real yet.
        tool_calls: set by `plan` (empty in this stub, since no tool
            exists until phase 2.1+).
        findings_count: set by `act`, the length of the (empty, in this
            stub) `Finding` list `coordinator_worker_execute` returns.
        cap_exceeded: set True by whichever of guardrail/think/plan/write
            first catches a `QueryCapExceededError` from its own
            pre-flight `check_per_query_cap` call. Once set, the graph's
            conditional routing sends control straight to `write` instead
            of continuing the guardrail-think-plan-act sequence (Section
            19.1's per-query-cap trigger behavior).
        step_error: set (to a dict of `ErrorPayload` constructor kwargs,
            not an `ErrorPayload` instance itself, since a `TypedDict`
            value has to stay a plain, easily-mergeable structure) by
            whichever of guardrail/think/plan first catches a
            `HarnessCallError` (a per-step timeout, or a classified
            call_tier failure) from its own model call. `write` reads
            this to build the actual `ErrorPayload` event and to decide
            it must ship a refusal rather than attempt its own synthesis
            call, since a working answer cannot be produced without a
            working guardrail/think/plan step ahead of it.
        daily_cap_declined: set True by `guardrail` only, the one node
            that checks the per-user daily query cap and the system-wide
            daily dollar cap (both against the real `interactions` table,
            before any per-query model call fires for this query at all).
            When True, the graph routes straight to the graph's `END`
            node, past even `write`, since Section 19.1 declines the
            whole query outright for these two caps rather than shipping
            a partial result.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from system_03_search_agent.contracts.events import Event
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.harness.harness import Harness, QueryClass


class GraphState(TypedDict, total=False):
    """The single state object LangGraph threads through every node.

    See the module docstring for which fields are set once at
    graph-invocation time versus set incrementally by individual nodes.
    """

    query: Query
    context: RequestContext
    harness: Harness
    seq: int
    events: Annotated[list[Event], add]
    start_monotonic: float
    query_class: QueryClass
    tool_calls: list[Any]
    findings_count: int
    cap_exceeded: bool
    step_error: dict[str, Any] | None
    daily_cap_declined: bool
