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
      QueryClass, budget_for_query_class)
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
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from langgraph.graph import END, StateGraph

from system_03_search_agent.contracts.events import (
    DonePayload,
    ErrorPayload,
    Event,
    GuardPayload,
    PlanPayload,
    ThinkPayload,
    TokenPayload,
    ToolCall,
)
from system_03_search_agent.core.state import GraphState
from system_03_search_agent.data.session import session_scope
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness.cache import build_stable_prefix
from system_03_search_agent.harness.coordinator_worker import (
    ToolExecutionResult,
    coordinator_worker_execute,
)
from system_03_search_agent.harness.harness import (
    Harness,
    HarnessCallError,
    QueryClass,
    budget_for_query_class,
)
from system_03_search_agent.tools.cypher_query import cypher_query
from system_03_search_agent.tools.cypher_schemas import CypherQueryInput, CypherQueryOutput

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
            [{"role": "user", "content": query.text}],
            budget_s=budget_for_query_class("lookup"),
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
            [{"role": "user", "content": query.text}],
            budget_s=budget_for_query_class("lookup"),
        )
    except cost_control.QueryCapExceededError:
        return {"cap_exceeded": True}
    except HarnessCallError as exc:
        return {"step_error": _step_error_kwargs("think", exc)}

    # Stub only: real query-intent classification and entity resolution
    # are a later phase's job. `query_class="lookup"` is a fixed,
    # documented placeholder, never an actual classification of
    # `query.text`; it still drives every later node's real timeout
    # budget via `budget_for_query_class`, since that mapping needs some
    # concrete `query_class` value to resolve against regardless of
    # whether the value itself is real yet.
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


def _select_planned_tool_call(
    query_text: str, query_class: QueryClass
) -> _PlannedToolCall | None:
    """Deterministically select `cypher_query`, or nothing, for one query.

    Returns None for empty or plainly non-substantive text
    (`_NO_TOOL_QUERY_TEXTS`). Otherwise returns a `_PlannedToolCall`
    carrying a `CypherQueryInput` built from the raw query text as
    `query_intent` (capped to Section 6.1's 1000-char bound),
    `query_class` from Think's classification, no `target_entities` (no
    entity resolution exists yet), and the default row_limit.
    """
    normalized = query_text.strip().lower()
    if not normalized or normalized in _NO_TOOL_QUERY_TEXTS:
        return None

    cypher_input = CypherQueryInput(
        query_intent=query_text[:_PLAN_TOOL_CALL_MAX_INTENT_CHARS],
        query_class=query_class,
        target_entities=[],
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
            budget_s=budget_for_query_class(query_class),
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
    only (Section 6.1, T-2.1-07's contract), and a `Finding` is what a
    later Write-step ticket reads to build the actual event payload a
    client sees. The main agent, and by extension Write, must never
    receive raw Cypher in a payload rendered to a user.
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
            output: CypherQueryOutput = await harness.enforce_timeout(
                "act",
                cypher_query(harness, planned.cypher_input),
                budget_for_query_class(query_class),
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
    result: dict[str, Any] = {"findings_count": len(findings)}
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
# ---------------------------------------------------------------------------


async def write_node(state: GraphState) -> dict[str, Any]:
    harness = state["harness"]
    query = state["query"]
    trace_id = query.trace_id
    sink = _EventSink(trace_id, state["seq"])
    elapsed_ms = _elapsed_ms(state)
    total_tool_calls = state.get("findings_count", 0)

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
            budget_s=budget_for_query_class(query_class),
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

    # Stub only: real citation-grounded synthesis is phase 2.2's job. No
    # citation or trust_signal event is fabricated here (none has been
    # earned: no real tool ran, no real passage was retrieved).
    sink.emit("cost", cost_control.build_cost_event_payload(harness, trace_id, "synth"))
    sink.emit(
        "done",
        DonePayload(
            total_cost_usd=harness.get_query_cost_usd(trace_id),
            total_tool_calls=total_tool_calls,
            elapsed_ms=elapsed_ms,
            trust_outcome="answer",
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
