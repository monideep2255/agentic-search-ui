"""GraphState: the state threaded through the five-node LangGraph loop (T-2.0-07).

Spec: Technical_specification.md Section 3.2 (429-448); tracker/phase_2.0.md
T-2.0-07.

Depends on:
    - system_03_search_agent.contracts.events (Event, ResolvedEntity)
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
            classification (T-2.0-04's mapping). Through build phase 4.6
            this was always the stub literal `"lookup"`; build phase 4.7
            (T-4.7-04) makes it a real classification of the question,
            produced by a Plan-tier model call, so the same downstream
            budget resolution now selects on something true.
        resolved_entities: set by `think` (T-4.7-05, build phase 4.7),
            the real, live-confirmed or exact-ID-resolved entities Think's
            own `_EntityResolution` produced: Section 17's deterministic
            exact-ID pre-pass (`core.graph.resolve_exact_identifiers`)
            plus a Plan-tier typed-extraction call for whatever text the
            pre-pass left unresolved. A list of `contracts.events.
            ResolvedEntity` (the locked `{text, curie, confidence}`
            shape), never a fabricated CURIE for a span a live lookup
            could not confirm. `plan` reads this (T-4.7-06) for
            `CypherQueryInput.target_entities`, replacing the deterministic
            regex-token guess that used to compute it independently inside
            `plan_node` itself. Unset or empty means Think resolved
            nothing this turn, which is not necessarily a problem: session
            memory may still supply an antecedent (`plan_node`'s
            `_antecedent_curie`).
        tool_calls: set by `plan` (empty in this stub, since no tool
            exists until phase 2.1+).
        findings_count: set by `act`, the length of the `Finding` list
            `coordinator_worker_execute` returns.
        findings: set by `act`, the real `Finding` list itself (T-2.1
            rework, findings A5/F-02). `write` reads this to classify
            what Act actually found (no tool selected, a real result, an
            empty result, or a tool error) via
            `core.graph._tool_execution_outcome`, and to build real
            `citation` events via `core.graph._citations_from_findings`,
            rather than emitting `trust_outcome="answer"` off a bare
            count with no way to tell a real result from an empty or
            errored one.
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
        guard_refused: set True by `guardrail` only, when a Section 10
            admission check refuses the query: the pre-filter (10.2), the
            Guard-tier injection classifier (10.4), or the forbidden-type
            screen (10.5). Routes straight to `END` for the same reason
            `daily_cap_declined` does, and is kept as a SEPARATE flag
            rather than reusing that one because the two are different
            events that happen to share a route. A cap decline says the
            query was never eligible to run; a guard refusal says it was
            eligible and was judged. Collapsing them would make the
            audit trail unable to tell a rate-limited user from a
            rejected query.
        unresolved_entity_symbols: set by `think` as of build phase 4.7
            (T-3.1-13/F-2.1-B10; previously set by `plan`, before entity
            resolution moved to `think` in T-4.7-05), when the query text
            carries at least one gene-shaped span that was looked up live
            against NCBI (`core.graph.resolve_symbol_to_curie`) and
            resolved to nothing, and no other entity rescues the query.
            `write` reads this BEFORE its own synth call, the same
            early-exit shape `step_error` and `cap_exceeded` already use,
            and ships a refusal naming the unresolved symbol rather than
            letting an unbound Cypher parameter reach the graph and fail
            there as an opaque `UndefinedParameter`. Unset or empty means
            every candidate either resolved or none was found at all,
            which is not the same thing: "no gene mentioned" answers
            normally, "a gene-shaped token was mentioned and NCBI does not
            know it" refuses.
        layer2_raw_outputs: set by `act` (T-3.4-05/T-3.1-28), the real,
            typed Layer 2 tool output (currently only ever `NcbiEfetchOutput`,
            this phase's one wired Layer 2 tool) behind each dispatched
            Layer 2 `ToolCall`, keyed by that call's `call_id`. Exists
            because `act` also shapes that same output into the generic,
            tool-agnostic pseudo-row dict every `Finding.structured_fields`
            carries (so `build_synth_findings` and the rest of the
            grounding pipeline need no tool-specific branching), and that
            shaping is lossy in the other direction: `write` needs the
            ORIGINAL typed output back to build a real Section 9.2 Layer 2
            citation via a tool's own `build_layer2_citation`-shaped
            function, and reconstructing a validated Pydantic model by
            hand from the generic dict it was flattened into would be
            strictly worse than never having flattened it in the first
            place. Unset or empty means no Layer 2 tool was dispatched
            this query, which is the common case: `core/graph.py`'s
            `_citations_from_grounded_claims` falls back to a generic,
            tool-agnostic citation construction whenever a Layer 2 claim's
            raw output cannot be found here, so a missing entry degrades
            rather than crashes.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from system_03_search_agent.contracts.events import Event, ResolvedEntity
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
    resolved_entities: list[ResolvedEntity]
    tool_calls: list[Any]
    findings_count: int
    findings: list[Any]
    cap_exceeded: bool
    step_error: dict[str, Any] | None
    daily_cap_declined: bool
    guard_refused: bool
    unresolved_entity_symbols: list[str]
    # UI fix set 7, item 7.5 (2026-09-13): set by `think` when the question
    # refers back to something no entity, no unresolved symbol and no
    # remembered antecedent can supply. `plan` then selects no tool and
    # `write` asks the question instead of refusing or guessing.
    clarification_needed: str
    layer2_raw_outputs: dict[str, Any]
    # UI fix set 7, item 7.2 (2026-09-13). Both set by `plan`, both read by
    # `write`, both plain data so that `write` never reads session memory
    # itself (Section 14.4, asserted by the personalization premise gate's
    # call-site walk). `deferred_record_ids` is the `source_url` of every
    # record an earlier answer in this session already showed, populated
    # ONLY when the query is the go-deeper follow-up
    # (`core.next_step.is_go_deeper_query`) and empty otherwise, so an
    # ordinary question is never reordered. `next_step_entity_label` is the
    # mention the turn's first target entity was resolved from ("BRCA1", or
    # the CURIE when no mention is known), which `write` puts into
    # `DonePayload.next_step_query`.
    deferred_record_ids: list[str]
    next_step_entity_label: str
