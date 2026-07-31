"""The five-node LangGraph loop with stub nodes (T-2.0-07).

Spec: Technical_specification.md Section 3.2 (429-448), Section 25 row 2.0
(line 3181); CLAUDE.md's agent-loop pattern; tracker/phase_2.0.md T-2.0-07.

Depends on:
    - langgraph.graph (StateGraph, START, END): pinned >=0.2 in
      requirements.txt.
    - system_03_search_agent.core.state (GraphState)
    - system_03_search_agent.contracts.events (Event and the payload
      models this module constructs: GuardPayload, ThinkPayload,
      PlanPayload, TokenPayload, ErrorPayload, DonePayload)
    - system_03_search_agent.data.session (session_scope): one DB session
      per guardrail invocation, for the two daily caps.
    - system_03_search_agent.harness.cost_control: every cap check, the
      cost-event builder, and the partial-result note string. Imported as
      a module (`cost_control.check_per_query_cap(...)`, not a bare
      `from ... import check_per_query_cap`) so a test can monkeypatch an
      individual cap-check function on the module object the same way
      `test_harness.py` patches `harness_module.litellm`.
    - system_03_search_agent.harness.coordinator_worker
      (coordinator_worker_execute): the Act step's one call, proving the
      integration point exists even though `plan`'s stub `tool_calls` is
      always empty this phase.
    - system_03_search_agent.harness.harness (Harness, HarnessCallError,
      QueryClass, budget_for_step)
    - system_03_search_agent.harness.cache (build_stable_prefix): called
      once at import time (`_STABLE_PREFIX`, module-level below) and
      passed as every model call's `cache_prefix`, closing the gap the
      phase 2.0 judge review flagged (F-2.0-03): T-2.0-06 built the
      prefix-assembly scaffold but nothing called it until this fix.

Reads:
    - Nothing at import time beyond the modules above. USER_DB_URL and the
      three cap env vars are read lazily, inside the guardrail node, only
      when a query actually reaches it.

Writes:
    - Nothing at import time. `compiled_graph` (module-level, see below)
      has no side effects of its own; each per-query DB session it opens
      via `session_scope()` is opened and closed inside the guardrail
      node's own call.

Five nodes, fixed sequence, matching Section 3.2's step-to-tier table
exactly: `guardrail` and `think` call `tier="guard"`, `plan` calls
`tier="plan"`, `write` calls `tier="synth"`. `act` fires no model call at
all (Section 3.2: Act is non-LLM code that dispatches tool calls).

Every model-calling node (guardrail, think, plan, write) follows the same
three-step pattern in this order, never reordered:
    1. `cost_control.check_per_query_cap(harness, trace_id, tier)`, the
       pre-flight per-query cap check, called immediately before, never
       after, the model call it guards (Section 19.2).
    2. `harness.enforce_timeout(step, harness.call_tier(tier, ...),
       budget_s)`, the actual model call under its per-step timeout
       budget (T-2.0-04).
    3. `cost_control.build_cost_event_payload(harness, trace_id, tier)`,
       emitted as a `cost` event immediately after a successful call.

Two ways a node's own step can end early instead of falling through to
the next node in sequence, both structural (a conditional edge), never a
node silently skipping its own downstream sibling:

    - `QueryCapExceededError` (Section 19.1's per-query cap): the graph
      routes straight to `write`, which ships a partial result carrying
      `cost_control.PER_QUERY_CAP_PARTIAL_RESULT_NOTE` and a `done` event
      with `trust_outcome="flag"`, never a blank failure. `write` itself
      also runs this same check before its own `call_tier`, so a cap hit
      discovered only at Write is handled inline, not just when routed in
      from an earlier node.
    - `HarnessCallError` (a per-step timeout, or a classified call_tier
      failure that reached its retry ceiling): the graph likewise routes
      straight to `write`, which surfaces the real error via an `error`
      event and ships a refusal (`trust_outcome="refuse"`), since a
      genuinely broken upstream step (not merely a spent budget) means
      Write cannot honestly synthesize an answer at all. This is a
      judgment call beyond this ticket's one required test (the cap-hit
      short circuit): production-standards.md's "graceful degradation is
      mandatory; a blank failure is not acceptable" gate applies to a
      step failure exactly as much as to a cap hit, so an unhandled
      `HarnessCallError` crashing `run()` outright would not be
      acceptable here either.

A third, separate early-exit path lives only in `guardrail`: the two
daily caps (`check_user_daily_query_cap`, `check_system_daily_cost_cap`,
both read live against the `interactions` table via a real DB session)
are checked before any per-query model call fires for this query at all,
per the ticket's explicit instruction ("Before the graph even starts, or
as the first thing the guardrail node does"). A decline here routes
straight past even `write`, to the graph's `END`, since Section 19.1
declines the whole query outright for these two caps (a "come back
later" decline, not a partial answer), and the ticket requires exactly an
`error` event plus a `done` event, then stop.

`query.user_id` may be `None` (an unauthenticated caller on some future
surface, or a client that omitted it and the current surface did not
override it). The decision: `check_user_daily_query_cap` is skipped in
that case, but `check_system_daily_cost_cap` always runs regardless of
`user_id`, since the system-wide cap protects the whole deployment, not
one user's quota, and has no per-user identity to key off in the first
place.

`compiled_graph` is compiled once at module import time, not per call in
`core.run.run()`. The graph's node functions and edges are entirely
static (never re-derived from a request), so there is nothing per-query
to bake into a fresh compile: a `Harness` instance, a `trace_id`, and
every other per-query value all live in the `GraphState` passed to
`ainvoke()`, never in the compiled graph object itself. Compiling once
avoids repeating LangGraph's (small but nonzero) graph-validation work on
every single query.

T-2.1 rework (judge/adversary findings A3, A5, F-02, F-04, F-05, F-06, dated
2026-07-29, on top of T-2.1-08's original wiring): the judge and an
independent adversary found the wired loop could not actually reach the
graph, and that its terminal `trust_outcome` never reflected what Act
found. Fixed here:

    - A3/F-02: `plan_node` used to hardcode `target_entities=[]`
      unconditionally, so `cypher_query`'s generated parameter never had
      a value to bind and every query dead-ended in `status: "error"`.
      `_extract_target_entities` now pulls real CURIEs out of the query
      text deterministically (see its own docstring for the narrow,
      documented scope of what it currently recognizes).
    - A5/F-02: `act_node` used to discard every `Finding` and hand
      `write_node` only a bare count, so `write_node` emitted
      `trust_outcome="answer"` unconditionally on its success path
      regardless of whether the tool found anything. `act_node` now
      carries the real `Finding` list through `GraphState.findings`, and
      `write_node`'s `_tool_execution_outcome` classifies what actually
      happened (no tool selected, a real result, an empty result, or a
      tool error) before deciding `answer` versus `refuse`, and
      `_citations_from_findings` emits a real `citation` event per row
      that earned one, never a fabricated one.
    - F-05: `act_node` used to wrap `cypher_query` in a budget resolved
      from `think_node`'s stub `"lookup"` classification alone, which
      was well under `cypher_query`'s own declared budget and under live
      graph latency. The tool's own declared budget is the floor; the
      caller's budget is what gives: `act_node` wraps the call in
      `max(budget_for_step("act", query_class),
      CYPHER_QUERY_TIMEOUT_SECONDS)`, so a `query_class` that already
      budgets more is untouched and one that budgets less is raised to
      the tool's floor rather than starving it. Note the budget function
      itself was later replaced: `budget_for_step` resolves a
      model-calling step against its own TIER and `act` against the
      query class, because those are two different axes. See
      `harness.harness._TIER_STEP_BUDGET_S` for the measurements.
    - F-04: `cypher_query` may issue up to two plan-tier calls internally
      through `generate_cypher` (the initial attempt plus one repair
      retry), neither individually gated by
      `cost_control.check_per_query_cap`. That gap can only be closed
      inside `cypher_query.py`/`cypher_generation.py` (mirroring
      `coordinator_worker.py`'s own `_reader_pass`, which already checks
      the cap before its one call), both out of this file's scope this
      pass. Not fixed here; a handoff, not a silent gap.
    - F-06: `generate_cypher` never accepts or forwards `cache_prefix`,
      so up to 2 of the query's model calls (both `generate_cypher`
      attempts) bypass the stable prefix
      `.claude/rules/prompt-cache-discipline.md` requires. Fixing this
      requires `cypher_generation.py` to accept a `cache_prefix`
      parameter and thread it into its own `harness.call_tier` call; out
      of this file's scope this pass. Not fixed here; a handoff, not a
      silent gap. `tests/system_03_search_agent/core/test_graph.py`
      asserts the current, honest split (4 of 6 calls carry the prefix)
      rather than concealing it behind a vacuous filter.

Second judge pass, 2026-07-31 (tracker/phase_2.1.md F-2.1-10, F-2.1-11):

    - F-2.1-10: `coordinator_worker.Finding.truncated` (the F-03 fix's own
      "truncation is never silent" field) had no reader anywhere in
      `core/` or `adapters/`, so a `Finding` cut by the 50,000-byte
      ceiling reached `write_node` indistinguishable from a complete one.
      `_ok_finding_was_truncated` below is that reader.
    - F-2.1-11: `_cap_structured_fields`'s binary search can shrink a
      real, `status="ok"` result's `rows` list down to zero while
      `status` itself stays `"ok"`, so `_citations_from_findings` yields
      no citations and `write_node` used to emit an identical, silent
      `trust_outcome="refuse"` whether the tool found nothing or found
      something the byte ceiling then erased. `write_node` now checks
      `_ok_finding_was_truncated` alongside `tool_outcome` and `citations`:
      a cut that still left a citeable row still answers, but emits a
      `token` note acknowledging the cut; a cut that left nothing
      citeable still refuses (cite-or-refuse is not weakened), but emits
      a non-fatal `error` event naming the real cause, so the two
      "refuse" cases are never confused with each other downstream.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from langgraph.graph import END, StateGraph

from system_03_search_agent.contracts.events import (
    CitationPayload,
    DonePayload,
    ErrorPayload,
    Event,
    GuardPayload,
    PlanPayload,
    ThinkPayload,
    TokenPayload,
    ToolCall,
    TrustOutcome,
)
from system_03_search_agent.core.state import GraphState
from system_03_search_agent.data.session import session_scope
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness.cache import build_stable_prefix
from system_03_search_agent.harness.coordinator_worker import (
    Finding,
    ToolExecutionResult,
    coordinator_worker_execute,
)
from system_03_search_agent.harness.harness import (
    Harness,
    HarnessCallError,
    QueryClass,
    budget_for_step,
)
from system_03_search_agent.tools.cypher_query import cypher_query
from system_03_search_agent.tools.cypher_schemas import CypherQueryInput, CypherQueryOutput
from system_03_search_agent.tools.graph_schema_constants import (
    CURIE_PREFIXES,
    CYPHER_QUERY_TIMEOUT_SECONDS,
)

Message = dict[str, str]

# Built once at import time, matching `compiled_graph` below: the stable
# prefix is a deterministic function of `tool_schemas` alone (prompt-
# cache-discipline.md), and no tool exists yet to pass one (phase 2.1+
# is the first to register a real tool schema), so this is the same
# prefix for every guardrail/think/plan/write call this phase makes.
# Rebuilding it per call would cost nothing functionally, since it is
# byte-identical every time, but computing it once removes any chance of
# it silently drifting between calls within a session, which is exactly
# what `prompt-cache-discipline.md` requires the harness to guarantee.
_STABLE_PREFIX = build_stable_prefix()


class _EventSink:
    """Accumulates one node's new events with a continuously incrementing seq.

    A node reads its starting `seq` from the merged state (whatever the
    previously-run node left it at) and returns only the new events it
    itself produced; `GraphState.events`'s `Annotated[list[Event], add]`
    reducer concatenates those onto the graph's running event list. This
    class is the per-node bookkeeping for that pattern so no node hand-
    increments `seq` inline.
    """

    def __init__(self, trace_id: str, seq: int) -> None:
        self.trace_id = trace_id
        self.seq = seq
        self.new_events: list[Event] = []

    def emit(self, event_type: str, payload: Any) -> Event:
        event = Event(
            type=event_type,
            version="v1",
            trace_id=self.trace_id,
            seq=self.seq,
            ts=datetime.now(UTC),
            payload=payload.model_dump(),
        )
        self.new_events.append(event)
        self.seq += 1
        return event

    def result(self, **extra: Any) -> dict[str, Any]:
        """Build this node's partial-state return value."""
        return {"events": self.new_events, "seq": self.seq, **extra}


async def _dispatch_tier_call(
    harness: Harness,
    trace_id: str,
    tier: str,
    step: str,
    messages: list[Message],
    budget_s: float,
) -> Any:
    """The shared cap-check-then-call-then-timeout sequence every model-
    calling node uses, in the fixed order the module docstring states.

    Raises:
        cost_control.QueryCapExceededError: the pre-flight per-query cap
            check refused to dispatch this call.
        HarnessCallError: the call timed out, or failed and exhausted its
            retry (both classified; see `harness.harness.Harness`).
    """
    cost_control.check_per_query_cap(harness, trace_id, tier)  # type: ignore[arg-type]
    return await harness.enforce_timeout(
        step,
        harness.call_tier(tier, messages, cache_prefix=_STABLE_PREFIX),  # type: ignore[arg-type]
        budget_s,
    )


# F-2.0-12 (adversary, confirmed low, 2026-07-28): HarnessCallError's own
# message deliberately includes the resolved model id (harness.py's
# call_tier and _price_per_token both build it that way, on purpose, so
# an operator reading a log or trace can see exactly which model
# answered). That message reaches the end user unmodified today, since
# `error` events are not in cost_control's builder-only filter set,
# letting a client enumerate the guard/plan/synth tier-to-model mapping
# by forcing one failure per tier. The fix is at the boundary where an
# internal exception becomes a client-visible payload, not in the
# exception itself: keep HarnessCallError's message exactly as built
# (still useful once real logging/tracing lands, Section 20), and build
# a separate, generic, actionable end-user message here instead of
# forwarding `str(exc)` verbatim.
_STEP_ERROR_END_USER_MESSAGES: dict[str, str] = {
    "transient": "A step in this query hit a temporary error. Retrying the query may succeed.",
    "recoverable": "A step in this query could not complete as requested.",
    "unexpected": "A step in this query failed unexpectedly.",
}


def _step_error_kwargs(step: str, exc: HarnessCallError) -> dict[str, Any]:
    """Build the `ErrorPayload` constructor kwargs for a step's `HarnessCallError`.

    Stored on `GraphState.step_error` as a plain dict (not an `ErrorPayload`
    instance) so the state stays a simple, mergeable structure; `write`
    constructs the real `ErrorPayload` from this when it emits the event.
    `retry_after_s=0`: neither a per-step timeout nor an exhausted-retry
    call failure carries a meaningful wait-and-retry estimate at this
    ticket's stub scope (no real backoff schedule exists yet beyond
    `call_tier`'s own single internal retry), so 0 documents "no wait
    recommended" rather than fabricating a number.

    `message` is deliberately NOT `str(exc)`: see the module-level note on
    `_STEP_ERROR_END_USER_MESSAGES` above (F-2.0-12).
    """
    return {
        "fatal": True,
        "scope": "step",
        "source": step,
        "error_class": exc.error_class,
        "message": _STEP_ERROR_END_USER_MESSAGES[exc.error_class],
        "retry_after_s": 0,
    }


def _elapsed_ms(state: GraphState) -> int:
    return int((time.monotonic() - state["start_monotonic"]) * 1000)


# ---------------------------------------------------------------------------
# guardrail: the two daily caps (once, here only), then tier="guard".
# ---------------------------------------------------------------------------


# The instruction the two stub Guard-tier steps send alongside the query.
#
# Both `guardrail_node` and `think_node` make a real model call whose
# response they then discard: the guardrail emits a hardcoded
# `passed=True` and think a hardcoded `query_class="lookup"`, because the
# real classification logic is build phase 3.0's and a later phase's work
# respectively. The call exists to prove the harness path end to end, not
# to produce an answer.
#
# Until this constant existed the call sent only `query.text` with no
# instruction at all, so the model did the obvious thing with a bare
# question and wrote a full essay, running to the 1000-token ceiling on
# every query. Measured: `out=1000` exactly, roughly 10 to 15 seconds per
# call, which then blew the step budget and killed the query at the
# guardrail. Section 3.1 specifies this tier as "sub-second, fractions of
# a cent", so an essay per step was wrong on latency, on cost, and on the
# tier's stated purpose.
#
# This is deliberately NOT guardrail logic. It does not classify, detect
# injection, or influence the emitted payload, all of which remain phase
# 3.0's job per `.claude/rules/v1-scope-boundary.md`. It only stops a
# throwaway call from generating a thousand tokens nobody reads.
_STUB_TIER_PROBE_SYSTEM = (
    "Reply with exactly one word: ok. Do not explain, do not answer the "
    "user's question, do not add punctuation."
)


# Step timeouts now come from `harness.budget_for_step`, which resolves a
# model-calling step against its own tier and `act` against the query
# class. See that function for the measurements and the provisional-value
# caveat.


def _stub_probe_messages(query_text: str) -> list[dict[str, str]]:
    """Messages for a stub Guard-tier call whose response is discarded."""
    return [
        {"role": "system", "content": _STUB_TIER_PROBE_SYSTEM},
        {"role": "user", "content": query_text},
    ]


async def guardrail_node(state: GraphState) -> dict[str, Any]:
    harness = state["harness"]
    query = state["query"]
    trace_id = query.trace_id
    sink = _EventSink(trace_id, state["seq"])

    with session_scope() as session:
        try:
            if query.user_id is not None:
                try:
                    parsed_user_id = uuid.UUID(query.user_id)
                except ValueError:
                    # F-2.0-13 (adversary, confirmed low, 2026-07-28): a
                    # malformed user_id (not a well-formed UUID) used to
                    # crash run() with an uncaught ValueError. Not
                    # reachable via POST /query today, since T-2.0-08
                    # always overwrites user_id with the authenticated
                    # user's real UUID, but Query is the shared contract
                    # every future surface (MCP, CLI) also constructs, so
                    # validate it here rather than trust every future
                    # caller to supply a well-formed one.
                    return _decline_for_daily_cap(
                        state,
                        sink,
                        "core.graph.guardrail_node",
                        "user_id must be a well-formed UUID or omitted entirely",
                    )
                cost_control.check_user_daily_query_cap(session, parsed_user_id)
            cost_control.check_system_daily_cost_cap(session)
        except cost_control.UserDailyQueryCapExceededError as exc:
            source = "cost_control.check_user_daily_query_cap"
            return _decline_for_daily_cap(state, sink, source, str(exc))
        except cost_control.SystemDailyCostCapExceededError as exc:
            source = "cost_control.check_system_daily_cost_cap"
            return _decline_for_daily_cap(state, sink, source, str(exc))

    try:
        await _dispatch_tier_call(
            harness,
            trace_id,
            "guard",
            "guardrail",
            _stub_probe_messages(query.text),
            budget_s=budget_for_step("guardrail", "lookup"),
        )
    except cost_control.QueryCapExceededError:
        return {"cap_exceeded": True}
    except HarnessCallError as exc:
        return {"step_error": _step_error_kwargs("guardrail", exc)}

    # Stub only: real guardrail validation (prompt-injection detection,
    # off-topic/medical-advice classification, rate limiting) is phase
    # 3.0's job. `passed=True, category="ok"` is the one schema-valid,
    # non-fabricated stub outcome available before that logic exists.
    sink.emit("guard", GuardPayload(passed=True, category="ok", reason=None))
    sink.emit("cost", cost_control.build_cost_event_payload(harness, trace_id, "guard"))
    return sink.result()


def _decline_for_daily_cap(
    state: GraphState, sink: _EventSink, source: str, message: str
) -> dict[str, Any]:
    """Section 19.1's decline path for the two daily caps: an `error` event
    plus a `done` event, then stop -- the graph never reaches `write`.

    Also reused for `guardrail`'s malformed-`user_id` short-circuit
    (F-2.0-13): the shape needed is identical (stop immediately, emit
    `error` then `done`, never reach `write`), even though a bad
    `user_id` is a contract-validation failure, not a cap decline. The
    `daily_cap_declined` flag this sets is what `_route_after_guardrail`
    reads to route straight to `END` in both cases.
    """
    sink.emit(
        "error",
        ErrorPayload(
            fatal=True,
            scope="run",
            source=source,
            error_class="recoverable",
            message=message[:256],
            retry_after_s=0,
        ),
    )
    sink.emit(
        "done",
        DonePayload(
            total_cost_usd=0.0,
            total_tool_calls=0,
            elapsed_ms=_elapsed_ms(state),
            trust_outcome="refuse",
        ),
    )
    return sink.result(daily_cap_declined=True)


# ---------------------------------------------------------------------------
# think: tier="guard", stub query_class, drives every later node's budget.
# ---------------------------------------------------------------------------


async def think_node(state: GraphState) -> dict[str, Any]:
    harness = state["harness"]
    query = state["query"]
    trace_id = query.trace_id
    sink = _EventSink(trace_id, state["seq"])

    try:
        await _dispatch_tier_call(
            harness,
            trace_id,
            "guard",
            "think",
            _stub_probe_messages(query.text),
            budget_s=budget_for_step("think", "lookup"),
        )
    except cost_control.QueryCapExceededError:
        return {"cap_exceeded": True}
    except HarnessCallError as exc:
        return {"step_error": _step_error_kwargs("think", exc)}

    # Stub only: real query-intent classification and entity resolution
    # are a later phase's job. `query_class="lookup"` is a fixed,
    # documented placeholder, never an actual classification of
    # `query.text`; it still drives every later node's real timeout
    # budget via `budget_for_step`, which resolves `act` against the
    # query class, so that mapping still needs some concrete
    # `query_class` value regardless of whether the value is real yet.
    stub_query_class: QueryClass = "lookup"
    think_payload = ThinkPayload(
        narrative="stub: real query classification lands in a later phase",
        query_class=stub_query_class,
        resolved_entities=[],
        clarifying_question=None,
    )
    sink.emit("think", think_payload)
    sink.emit("cost", cost_control.build_cost_event_payload(harness, trace_id, "guard"))
    return sink.result(query_class=stub_query_class)


# ---------------------------------------------------------------------------
# plan: tier="plan". T-2.1-08 replaces the phase 2.0 stub (an always-empty
# tool_calls list) with real, deterministic cypher_query selection: this
# phase has exactly one tool, so a query with substantive content selects
# it and a query that plainly needs no graph lookup (a greeting, a
# thanks) selects nothing. Real intent classification and entity
# resolution (which would populate CypherQueryInput.target_entities from
# Think's resolved_entities) are a later phase's job; think_node's own
# query_class output is still a fixed "lookup" stub (T-2.0-07).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _PlannedToolCall:
    """Pairs one Section 2.3 `ToolCall` (the locked event-contract shape,
    carrying only `tool`/`call_id`/`layer`) with the full structured
    `CypherQueryInput` Act actually executes. `GraphState.tool_calls` is
    declared `list[Any]` (core.state.GraphState), so storing this richer
    pairing there needs no change to that TypedDict.
    """

    tool_call: ToolCall
    cypher_input: CypherQueryInput


# Query texts that plainly need no graph lookup at all. Deliberately
# small and exact-match, not a fuzzy classifier: a false negative here
# (treating a real question as small talk) is worse than a false
# positive (attempting cypher_query on a genuine greeting, which the
# pipeline will simply answer "empty" or "error" for), so this list only
# excludes unambiguous non-questions.
_NO_TOOL_QUERY_TEXTS: frozenset[str] = frozenset(
    {"hello", "hi", "hey", "thanks", "thank you", "who are you", "what can you do"}
)

_PLAN_TOOL_CALL_MAX_INTENT_CHARS = 1000
_PLAN_TOOL_CALL_ROW_LIMIT = 100

# Mirrors CypherQueryInput.target_entities's own max_length=10 (Section
# 6.1). Enforced here too so a pathological query text can never build a
# list Pydantic would reject at construction; cypher_schemas.py owns the
# schema-level cap, this is a pre-cap on the same bound, not a
# duplicated decision.
_TARGET_ENTITIES_MAX_ITEMS = 10

# A CURIE the caller already typed verbatim, e.g. "NCBIGene:672". Built
# from the same nine prefixes the live graph actually uses
# (graph_schema_constants.CURIE_PREFIXES), so this can never invent a
# prefix the graph would reject.
_CURIE_IN_TEXT_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(prefix) for prefix in CURIE_PREFIXES) + r"):[A-Za-z0-9_.:-]+"
)

# A narrow, explicitly verified seed table mapping an ALL-CAPS gene
# symbol to its real NCBIGene CURIE. This is not entity resolution or
# NER: it is a small, honest stopgap that lets phase 2.1's wiring
# actually reach the graph for the one symbol this ticket's e2e verify
# surface exercises (test_cypher_query_e2e.py's BRCA1 fixtures), without
# fabricating a CURIE for any symbol not listed here. Real entity
# resolution against the graph or an external vocabulary (turning
# Think's stub `resolved_entities=[]` into something real) is explicitly
# a later phase's job; see this module's own docstring note on
# think_node. Extend this table only with a symbol whose CURIE has been
# independently verified against the live graph, never a guessed id: a
# wrong mapping here is the "confidently wrong answer" this whole system
# exists to prevent, worse than the symbol resolving to nothing at all.
_KNOWN_GENE_SYMBOL_CURIES: dict[str, str] = {
    "BRCA1": "NCBIGene:672",
}

# An ALL-CAPS alphanumeric token, 2 to 10 characters, used only to probe
# `_KNOWN_GENE_SYMBOL_CURIES`; a token that is not a key in that table
# contributes nothing (see `_extract_target_entities`).
_GENE_SYMBOL_TOKEN_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]{1,9}\b")


def _extract_target_entities(query_text: str) -> list[str]:
    """Deterministically extract candidate CURIEs referenced by `query_text`.

    Fixes findings A3/F-02: `plan_node` used to hand `cypher_query` an
    unconditionally empty `target_entities` list, so the generated
    Cypher's named parameter never had a value to bind, and every query
    dead-ended in `status: "error"` (an unbound parameter) or a validator
    rejection (a literal interpolated instead). Two deterministic
    sources, no model call and no fuzzy matching:

    1. A CURIE the caller already typed verbatim, matched against
       `_CURIE_IN_TEXT_PATTERN`, taken as given.
    2. An ALL-CAPS token matched against the small, explicitly verified
       `_KNOWN_GENE_SYMBOL_CURIES` seed table.

    An unrecognized token contributes nothing: this function never
    guesses or fabricates a CURIE for a symbol it does not recognize.
    That is intentional, not a gap to silently patch over. A query whose
    only entity is unrecognized ends up with an empty `target_entities`
    list, which `cypher_query` and `write_node`'s cite-or-refuse logic
    already turn into a refusal rather than a wrong answer bound to the
    wrong entity.

    Capped at `_TARGET_ENTITIES_MAX_ITEMS`, matching
    `CypherQueryInput.target_entities`'s own schema bound, and
    de-duplicated while preserving first-seen order.
    """
    found: list[str] = []
    seen: set[str] = set()

    for match in _CURIE_IN_TEXT_PATTERN.finditer(query_text):
        curie = match.group(0)
        if curie not in seen:
            seen.add(curie)
            found.append(curie)

    for token_match in _GENE_SYMBOL_TOKEN_PATTERN.finditer(query_text.upper()):
        curie = _KNOWN_GENE_SYMBOL_CURIES.get(token_match.group(0))
        if curie is not None and curie not in seen:
            seen.add(curie)
            found.append(curie)

    return found[:_TARGET_ENTITIES_MAX_ITEMS]


def _select_planned_tool_call(
    query_text: str, query_class: QueryClass
) -> _PlannedToolCall | None:
    """Deterministically select `cypher_query`, or nothing, for one query.

    Returns None for empty or plainly non-substantive text
    (`_NO_TOOL_QUERY_TEXTS`). Otherwise returns a `_PlannedToolCall`
    carrying a `CypherQueryInput` built from the raw query text as
    `query_intent` (capped to Section 6.1's 1000-char bound),
    `query_class` from Think's classification, `target_entities` from
    `_extract_target_entities` (A3/F-02's fix: real CURIEs when this
    module can deterministically recognize one, otherwise empty, never
    fabricated), and the default row_limit.
    """
    normalized = query_text.strip().lower()
    if not normalized or normalized in _NO_TOOL_QUERY_TEXTS:
        return None

    cypher_input = CypherQueryInput(
        query_intent=query_text[:_PLAN_TOOL_CALL_MAX_INTENT_CHARS],
        query_class=query_class,
        target_entities=_extract_target_entities(query_text),
        row_limit=_PLAN_TOOL_CALL_ROW_LIMIT,
    )
    tool_call = ToolCall(
        tool="cypher_query",
        call_id=f"cq-{uuid.uuid4().hex[:12]}",
        layer="layer_1_graph",
    )
    return _PlannedToolCall(tool_call=tool_call, cypher_input=cypher_input)


async def plan_node(state: GraphState) -> dict[str, Any]:
    harness = state["harness"]
    query = state["query"]
    trace_id = query.trace_id
    sink = _EventSink(trace_id, state["seq"])
    query_class: QueryClass = state.get("query_class", "lookup")

    try:
        await _dispatch_tier_call(
            harness,
            trace_id,
            "plan",
            "plan",
            [{"role": "user", "content": query.text}],
            budget_s=budget_for_step("plan", query_class),
        )
    except cost_control.QueryCapExceededError:
        return {"cap_exceeded": True}
    except HarnessCallError as exc:
        return {"step_error": _step_error_kwargs("plan", exc)}

    planned = _select_planned_tool_call(query.text, query_class)
    if planned is None:
        plan_payload = PlanPayload(
            narrative="no graph-answerable content detected; no tool selected",
            tool_calls=[],
        )
        planned_tool_calls: list[_PlannedToolCall] = []
    else:
        plan_payload = PlanPayload(
            narrative="selected cypher_query for a Layer 1 graph lookup",
            tool_calls=[planned.tool_call],
        )
        planned_tool_calls = [planned]

    sink.emit("plan", plan_payload)
    sink.emit("cost", cost_control.build_cost_event_payload(harness, trace_id, "plan"))
    return sink.result(tool_calls=planned_tool_calls)


# ---------------------------------------------------------------------------
# act: non-LLM (no call_tier of its own), but T-2.1-08 makes it a real
# tool dispatcher: it executes whatever cypher_query call plan_node
# selected, subject to the per-query cost cap and a per-step timeout
# (F-2.0-08's Act-side half; coordinator_worker.py's own reader pass
# carries the other half), then hands the result to
# coordinator_worker_execute for the structured pass-through path (a
# Cypher row is structured data; it never goes through the free-text
# reader).
# ---------------------------------------------------------------------------


def _cypher_output_to_structured_fields(output: CypherQueryOutput) -> dict[str, Any]:
    """Shape a `cypher_query` result into `ToolExecutionResult.structured_fields`.

    Deliberately omits `cypher_executed`: that field is an audit trail
    only (Section 6.1, T-2.1-07's contract), and a `Finding` built from
    this dict is what `write_node` reads (via `GraphState.findings`) to
    build the actual citation and trust-outcome events a client sees. The
    main agent, and by extension Write, must never receive raw Cypher in
    a payload rendered to a user. `status` (`"ok"`/`"empty"`/`"error"`)
    is kept, unlike `cypher_executed`: `write_node`'s
    `_tool_execution_outcome` reads it to decide `answer` versus
    `refuse` (A5/F-02's fix), so it is exactly the one internal-pipeline
    field that must survive into the `Finding`.
    """
    return {
        "status": output.status,
        "row_count": output.row_count,
        "total_available": output.total_available,
        "truncated": output.truncated,
        "rows": [row.model_dump(mode="json") for row in output.rows],
        "error": output.error,
    }


async def act_node(state: GraphState) -> dict[str, Any]:
    harness = state["harness"]
    trace_id = state["query"].trace_id
    query_class: QueryClass = state.get("query_class", "lookup")
    planned_tool_calls: list[_PlannedToolCall] = state.get("tool_calls", [])

    tool_calls: list[ToolCall] = []
    results: list[ToolExecutionResult] = []
    cap_exceeded = False

    for planned in planned_tool_calls:
        # F-2.0-08 (Act's own half): checked immediately before dispatch,
        # never after, matching _dispatch_tier_call's own discipline. A
        # call that would breach the cap is never issued at all: it is
        # excluded from both tool_calls and results (never a placeholder
        # pair), so the two lists coordinator_worker_execute requires to
        # stay paired 1:1 never drift apart.
        try:
            cost_control.check_per_query_cap(harness, trace_id, "plan")
        except cost_control.QueryCapExceededError:
            cap_exceeded = True
            break

        tool_calls.append(planned.tool_call)
        try:
            # F-05 fix: cypher_query's own declared budget
            # (CYPHER_QUERY_TIMEOUT_SECONDS, 30s, tool-call-budgets.md)
            # is the locked number; think_node's stub "lookup"
            # classification resolves `budget_for_step("act", ...)` to a
            # figure well under both the tool's own budget and live
            # graph latency alone. The caller's budget is what gives:
            # never let a query_class's own budget starve the tool below its
            # own floor, but let a query_class that already budgets more
            # (multi_hop, aggregate, exploratory) keep that larger
            # number.
            act_timeout_s = max(budget_for_step("act", query_class), CYPHER_QUERY_TIMEOUT_SECONDS)
            output: CypherQueryOutput = await harness.enforce_timeout(
                "act",
                cypher_query(harness, planned.cypher_input),
                act_timeout_s,
            )
        except HarnessCallError:
            results.append(
                ToolExecutionResult(
                    contains_untrusted_free_text=False,
                    structured_fields={
                        "status": "error",
                        "error": "cypher_query call did not complete within its per-step timeout budget",
                    },
                )
            )
            continue

        # A Cypher row is structured data (Section 6.1's typed output
        # schema, not free text), so this always routes through the
        # structured pass-through path in coordinator_worker_execute,
        # never the isolated free-text reader.
        results.append(
            ToolExecutionResult(
                contains_untrusted_free_text=False,
                structured_fields=_cypher_output_to_structured_fields(output),
            )
        )

    findings = await coordinator_worker_execute(harness, tool_calls, results)
    # A5/F-02 fix: the real Finding list now survives into GraphState
    # (not just its length), so write_node can read what Act actually
    # found instead of fabricating trust_outcome="answer" over nothing.
    result: dict[str, Any] = {"findings_count": len(findings), "findings": findings}
    if cap_exceeded:
        # Section 19.1: the query still ships an answer, a partial one,
        # ready with whatever findings already exist; write_node already
        # knows how to turn this flag into that partial result.
        result["cap_exceeded"] = True
    return result


# ---------------------------------------------------------------------------
# write: tier="synth", the terminal `done` event. Also the single place
# that turns an upstream cap-hit or step-error flag into the actual
# partial-result or refusal events.
#
# A5/F-02 fix: this used to read only `findings_count` (a bare int) and
# emit `trust_outcome="answer"` unconditionally on its success path,
# regardless of whether Act's tool call found anything, came back empty,
# or errored outright. `_tool_execution_outcome` and
# `_citations_from_findings` below now read the real `Finding` list
# `act_node` carries through `GraphState.findings` and ground the
# terminal outcome, and every emitted citation, in what actually
# happened.
# ---------------------------------------------------------------------------

_MAX_CITATIONS_PER_ANSWER = 20


def _tool_execution_outcome(
    findings: list[Finding],
) -> Literal["no_tool", "ok", "empty", "error"]:
    """Classify Act's overall outcome across every dispatched tool call.

    Deterministic, no fuzzy scoring: reads only the `status` a structured
    `cypher_query` result already carries
    (`_cypher_output_to_structured_fields`). `"ok"` wins if any dispatched
    call found real rows, even if a sibling call in the same query
    errored or came back empty; short of an `"ok"`, an `"error"` beats an
    `"empty"`, since a tool call that broke is a materially different,
    worse signal than a tool call that ran cleanly and genuinely found
    nothing. `"no_tool"` means Plan selected no tool at all for this
    query (a greeting, a thanks, `_NO_TOOL_QUERY_TEXTS`): there is no
    factual graph claim to ground in the first place, so Write's stub
    synthesis may still answer.

    A `Finding` whose `structured_fields` carries no `status` key at all
    (not reachable from this phase's one tool, `cypher_query`, but a
    future tool might route through the free-text reader instead, whose
    `Finding`s never carry `structured_fields`) is simply not counted
    either way, rather than crashing on a missing key.
    """
    statuses = [
        fields["status"]
        for finding in findings
        if (fields := finding.structured_fields) is not None
        and isinstance(fields.get("status"), str)
    ]
    if not statuses:
        return "no_tool"
    if "ok" in statuses:
        return "ok"
    if "error" in statuses:
        return "error"
    return "empty"


def _pick_representative_field(fields: dict[str, Any]) -> tuple[str, Any] | tuple[None, None]:
    """Pick one field off a row to ground a citation's `claim_text` in.

    Deterministic, never a model judgment: prefer a `name` field when
    present (the most human-readable field most rows carry), else the
    first key in the row's own insertion order. A row with no fields at
    all yields `(None, None)`; the caller falls back to citing the row's
    bare identity (its type and CURIE).
    """
    if not fields:
        return None, None
    if "name" in fields:
        return "name", fields["name"]
    first_key = next(iter(fields))
    return first_key, fields[first_key]


def _citation_for_row(
    call_id: str, layer: str, row: dict[str, Any], display_index: int
) -> CitationPayload | None:
    """Build one `CitationPayload` from a real, already-fetched graph row.

    Returns None, never a fabricated citation, when the row carries no
    `source_url`: production-standards.md's cite-or-refuse gate treats an
    uncited row as unusable content, not as content to cite anyway (a row
    can reach here with no `source_url` when `cypher_provenance.
    to_output_row` could not resolve one, e.g. a GO/HP/MONDO CURIE; see
    that module's own docstring).

    `source`/`source_id` are read straight off the row's own CURIE, never
    guessed: the CURIE prefix (e.g. "NCBIGene") names the source
    database, the full CURIE is the source id. `evidence_kind=
    "primary_assertion"` and `license="public_domain_us_gov"` are Section
    9.2's documented defaults for a `cypher_query` graph property (an
    NCBI-native, US-federal-government record);
    `assertion_confidence="asserted"` is Section 9.2's default for a
    plain field with no hedge or conflict signal (no ClinVar
    review_status lookup or hedge-lexicon scan exists yet at this phase).
    `population_ancestry_context` stays None: no population or ancestry
    field exists on a Layer 1 graph row.
    """
    source_url = row.get("source_url")
    if not source_url:
        return None
    curie = str(row.get("curie", ""))[:100]
    prefix = curie.split(":", 1)[0] if ":" in curie else "cypher_query"
    fields = row.get("fields") or {}
    field_name, field_value = _pick_representative_field(fields)
    node_or_edge_type = str(row.get("node_or_edge_type", ""))
    claim_text = (
        f"{node_or_edge_type} {curie}: {field_name}={field_value}"
        if field_name is not None
        else f"{node_or_edge_type} {curie}"
    )

    return CitationPayload(
        citation_id=f"{call_id}-{display_index}"[:64],
        display_index=display_index,
        source=(prefix or "cypher_query")[:128],
        source_id=(curie or "unknown")[:128],
        source_url=source_url,
        layer=layer,  # type: ignore[arg-type]
        field=(field_name or "curie")[:128],
        claim_text=claim_text[:1000],
        evidence_kind="primary_assertion",
        assertion_confidence="asserted",
        population_ancestry_context=None,
        license="public_domain_us_gov",
    )


def _citations_from_findings(findings: list[Finding]) -> list[CitationPayload]:
    """Build every citation earned by this query's real, `"ok"` tool results.

    Only `structured_pass_through` findings with `status == "ok"`
    contribute: a `cypher_query` row is structured data, never routed
    through the free-text reader (`coordinator_worker.py`'s own module
    docstring), so every row this phase can cite arrives this way.
    Capped at `_MAX_CITATIONS_PER_ANSWER`, the same defense-in-depth
    posture every other emitted list in this module already carries
    (production-standards.md's multi-agent pipeline gate).
    """
    citations: list[CitationPayload] = []
    for finding in findings:
        fields = finding.structured_fields
        if fields is None or fields.get("status") != "ok":
            continue
        for row in fields.get("rows", []):
            if len(citations) >= _MAX_CITATIONS_PER_ANSWER:
                return citations
            citation = _citation_for_row(finding.call_id, finding.layer, row, len(citations) + 1)
            if citation is not None:
                citations.append(citation)
    return citations


# F-2.1-10 fix: `Finding.truncated` (coordinator_worker.py's F-03 fix) was
# added specifically so a caller could tell "the tool succeeded and this
# is everything it found" from "the tool succeeded but the result was cut
# to fit the 50,000-byte defense-in-depth ceiling". The judge found
# nothing in `core/` or `adapters/` ever read the field, so a capped
# `Finding` reached this module indistinguishable from a complete one.
# This is that reader.
def _ok_finding_was_truncated(findings: list[Finding]) -> bool:
    """True when at least one `"ok"` structured-pass-through `Finding` in
    this query's result set was cut by
    `coordinator_worker._cap_structured_fields`.

    Scoped to `"ok"` findings only: an `"empty"` or `"error"` finding is
    already refused for its own, unrelated reason, and `truncated` on a
    `"reader"`-sourced finding (`structured_fields is None`) is never
    meaningful, since that path has no `structured_fields` to have cut in
    the first place.
    """
    return any(
        finding.truncated
        for finding in findings
        if finding.structured_fields is not None
        and finding.structured_fields.get("status") == "ok"
    )


_TRUNCATED_ANSWER_NOTE = (
    "Note: this result was larger than the response size limit and was "
    "truncated; not every matching row is shown above."
)
_TRUNCATED_REFUSAL_MESSAGE = (
    "The graph query found matching data, but the result was cut to fit "
    "the response size limit before any row kept a citeable source_url. "
    "This is not the same as the graph returning no matching data. Retry "
    "with a narrower query_intent or a smaller row_limit."
)


async def write_node(state: GraphState) -> dict[str, Any]:
    harness = state["harness"]
    query = state["query"]
    trace_id = query.trace_id
    sink = _EventSink(trace_id, state["seq"])
    elapsed_ms = _elapsed_ms(state)
    total_tool_calls = state.get("findings_count", 0)
    findings: list[Finding] = state.get("findings", [])

    step_error = state.get("step_error")
    if step_error is not None:
        # An earlier step (guardrail/think/plan) failed for a non-cap
        # reason (a per-step timeout, or a classified call_tier failure
        # that exhausted its retry). Write cannot honestly synthesize an
        # answer without a working step ahead of it, so this ships a
        # refusal with the real error surfaced, never a fabricated
        # citation or trust_signal (production-standards.md's cite-or-
        # refuse gate).
        sink.emit("error", ErrorPayload(**step_error))
        sink.emit(
            "done",
            DonePayload(
                total_cost_usd=harness.get_query_cost_usd(trace_id),
                total_tool_calls=total_tool_calls,
                elapsed_ms=elapsed_ms,
                trust_outcome="refuse",
            ),
        )
        return sink.result()

    if state.get("cap_exceeded", False):
        # Routed straight here from an earlier node's per-query cap hit;
        # ship the partial result per Section 19.1, never a blank failure.
        return _partial_result_for_cap(sink, harness, trace_id, elapsed_ms, total_tool_calls)

    query_class: QueryClass = state.get("query_class", "lookup")
    try:
        await _dispatch_tier_call(
            harness,
            trace_id,
            "synth",
            "write",
            [{"role": "user", "content": query.text}],
            budget_s=budget_for_step("write", query_class),
        )
    except cost_control.QueryCapExceededError:
        # A cap hit discovered only here, at Write's own call, not routed
        # in from an earlier node: handled inline with the same partial-
        # result shape.
        return _partial_result_for_cap(sink, harness, trace_id, elapsed_ms, total_tool_calls)
    except HarnessCallError as exc:
        sink.emit("error", ErrorPayload(**_step_error_kwargs("write", exc)))
        sink.emit(
            "done",
            DonePayload(
                total_cost_usd=harness.get_query_cost_usd(trace_id),
                total_tool_calls=total_tool_calls,
                elapsed_ms=elapsed_ms,
                trust_outcome="refuse",
            ),
        )
        return sink.result()

    # A5/F-02 fix: the terminal trust_outcome now reflects what Act
    # actually found, never a fabricated "answer" over an empty or
    # errored tool result (production-standards.md's cite-or-refuse
    # gate). Real citation-grounded narrative synthesis (a token-by-token
    # written answer) is still phase 2.2's job; what this phase can
    # honestly do now is refuse to say "answer" when nothing was found,
    # and emit a real citation for every row that earned one.
    tool_outcome = _tool_execution_outcome(findings)
    citations = _citations_from_findings(findings) if tool_outcome == "ok" else []
    trust_outcome: TrustOutcome
    if tool_outcome == "no_tool" or (tool_outcome == "ok" and citations):
        trust_outcome = "answer"
    else:
        # "empty" (zero rows), "error" (the tool call broke), or "ok"
        # with rows that carried no citeable source_url: none of these
        # earned a confident answer, so this refuses rather than
        # answering with nothing behind it.
        trust_outcome = "refuse"

    # F-2.1-10/F-2.1-11 fix: a `Finding` the byte ceiling actually cut must
    # never look identical to one it left alone. `_ok_finding_was_truncated`
    # is the reader `Finding.truncated` was missing (F-2.1-10). Two cases:
    #   - The cut still left a citeable row: the query genuinely succeeded
    #     (trust_outcome is already "answer" above) and cite-or-refuse is
    #     not weakened, but the cut is acknowledged rather than silently
    #     dropped, so a user is never shown a partial result as if it were
    #     complete.
    #   - The cut left nothing citeable: cite-or-refuse still refuses (a
    #     truncated Finding earns no exemption from that gate), but the
    #     refusal names the real cause, so it is never confused with the
    #     graph genuinely returning no matching data (F-2.1-11's exact
    #     failure mode: both cases used to reach an identical, silent
    #     "refuse").
    truncated_ok_finding = tool_outcome == "ok" and _ok_finding_was_truncated(findings)
    if truncated_ok_finding and trust_outcome == "answer":
        sink.emit("token", TokenPayload(text=_TRUNCATED_ANSWER_NOTE, marker_ids=[]))
    elif truncated_ok_finding and trust_outcome == "refuse":
        sink.emit(
            "error",
            ErrorPayload(
                fatal=False,
                scope="tool",
                source="cypher_query",
                error_class="recoverable",
                message=_TRUNCATED_REFUSAL_MESSAGE,
                retry_after_s=0,
            ),
        )

    for citation in citations:
        sink.emit("citation", citation)

    sink.emit("cost", cost_control.build_cost_event_payload(harness, trace_id, "synth"))
    sink.emit(
        "done",
        DonePayload(
            total_cost_usd=harness.get_query_cost_usd(trace_id),
            total_tool_calls=total_tool_calls,
            elapsed_ms=elapsed_ms,
            trust_outcome=trust_outcome,
        ),
    )
    return sink.result()


def _partial_result_for_cap(
    sink: _EventSink, harness: Harness, trace_id: str, elapsed_ms: int, total_tool_calls: int
) -> dict[str, Any]:
    sink.emit(
        "token",
        TokenPayload(text=cost_control.PER_QUERY_CAP_PARTIAL_RESULT_NOTE, marker_ids=[]),
    )
    sink.emit(
        "done",
        DonePayload(
            total_cost_usd=harness.get_query_cost_usd(trace_id),
            total_tool_calls=total_tool_calls,
            elapsed_ms=elapsed_ms,
            trust_outcome="flag",
        ),
    )
    return sink.result()


# ---------------------------------------------------------------------------
# Routing: cap_exceeded or step_error short-circuits straight to write;
# daily_cap_declined (guardrail only) short-circuits straight to END.
# ---------------------------------------------------------------------------


def _route_after_guardrail(state: GraphState) -> str:
    if state.get("daily_cap_declined", False):
        return "end"
    if state.get("cap_exceeded", False) or state.get("step_error") is not None:
        return "write"
    return "think"


def _route_after_think(state: GraphState) -> str:
    if state.get("cap_exceeded", False) or state.get("step_error") is not None:
        return "write"
    return "plan"


def _route_after_plan(state: GraphState) -> str:
    if state.get("cap_exceeded", False) or state.get("step_error") is not None:
        return "write"
    return "act"


def _build_graph() -> StateGraph:
    graph = StateGraph(GraphState)
    graph.add_node("guardrail", guardrail_node)
    graph.add_node("think", think_node)
    graph.add_node("plan", plan_node)
    graph.add_node("act", act_node)
    graph.add_node("write", write_node)

    graph.set_entry_point("guardrail")
    graph.add_conditional_edges(
        "guardrail", _route_after_guardrail, {"think": "think", "write": "write", "end": END}
    )
    graph.add_conditional_edges("think", _route_after_think, {"plan": "plan", "write": "write"})
    graph.add_conditional_edges("plan", _route_after_plan, {"act": "act", "write": "write"})
    graph.add_edge("act", "write")
    graph.add_edge("write", END)
    return graph


# Compiled once at import time; see the module docstring for why this is
# safe (the graph structure is static, every per-query value lives in the
# GraphState passed to ainvoke(), never in the compiled object itself).
compiled_graph = _build_graph().compile()
