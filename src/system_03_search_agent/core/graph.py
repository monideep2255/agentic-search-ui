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
    - system_03_search_agent.harness.cache (build_stable_prefix,
      REGISTERED_TOOL_SCHEMAS): called once at import time
      (`_STABLE_PREFIX`, module-level below) and passed as every model
      call's `cache_prefix`, closing the gap the phase 2.0 judge review
      flagged (F-2.0-03): T-2.0-06 built the prefix-assembly scaffold but
      nothing called it until this fix. T-3.1-12 (this file's half)
      passes `REGISTERED_TOOL_SCHEMAS` through, the fixed, alphabetically
      ordered tuple `cache.py` already built but that no live call ever
      threaded in: before this change `ncbi_efetch`'s own schema had been
      live since its own build phase and still never reached a model's
      prompt.
    - system_03_search_agent.tools.ncbi_efetch (ncbi_efetch),
      system_03_search_agent.tools.ncbi_efetch_schemas (NcbiEfetchInput):
      T-3.1-11's live Layer 2 entity resolution
      (`resolve_symbol_to_curie`, below) routes every gene-symbol lookup
      through this tool, never a second HTTP path.

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

Adversary pass, third pass, 2026-07-31 (tracker/phase_2.1.md F-2.1-C12,
F-2.1-C13):

    - F-2.1-C12: `_ok_finding_was_truncated` above read only the byte-
      ceiling flag, one of three independent truncations on the path from
      the graph to the user (the tool's own row-limit cap, the byte
      ceiling, and `_MAX_CITATIONS_PER_ANSWER`). A result cut by the
      row-limit cap alone, comfortably under the byte ceiling, reached
      the user as 20 of 15,310 rows with no signal at all. It now reads
      `structured_fields["truncated"]` (the tool's own flag) as well, and
      `_citations_from_findings` reports whether the citation cap itself
      cut anything. The emitted note states the scale of what is missing
      (`_build_truncated_answer_note`), not just that a cut happened.
      Separately, `coordinator_worker._reconcile_row_count` keeps
      `row_count` honest against the rows a capped `Finding` actually
      carries, which used to disagree by a wide margin (measured:
      `row_count=500` reported for 118 surviving rows).
    - F-2.1-C13: `act_node` used to set `contains_untrusted_free_text=
      False` unconditionally for every `cypher_query` result, so
      coordinator_worker's isolated Guard-tier reader (system-design-
      patterns.md pattern 8) could never fire for any Layer 1 result, by
      construction, even though an Article row's own `fields["name"]` is
      raw, third-party-authored PubMed text, not graph-curated data.
      `_split_rows_by_trust` now partitions a result's rows before
      `_cypher_output_to_structured_fields` runs: trusted rows still pass
      straight through as before; any Article rows are quarantined into a
      second, reader-bound `ToolCall`/`ToolExecutionResult` pair
      (`contains_untrusted_free_text=True`), so their raw content can
      never reach `structured_fields`, and from there a citation's
      `claim_text`, unmediated.

Fourth judge pass, 2026-07-31 (tracker/phase_2.1.md F-2.1-J4-06): C13's
own fix above over-corrected. Excluding an Article row from
`_cypher_output_to_structured_fields` entirely, not just its untrusted
`fields`, made `row_count` disagree with `total_available` on the
`Finding` (F-2.1-C07's exact contradiction, reintroduced one layer up),
and made a query whose only matching rows were Article rows refuse
outright, silently: `tool_outcome` still read `"ok"` off the structured
Finding, so the refusal carried none of F-2.1-11's distinguishing
signal, indistinguishable from the graph genuinely finding nothing.
Excluding the whole row also traded away more than production-
standards.md's untrusted-source-reader gate ever asked for: the gate
requires the row's own free-text field content never reach a citation
unmediated, not that the record itself become uncitable.

`_sanitized_citeable_row` now replaces that exclusion. An Article row
still counts toward `row_count`/`total_available` and still earns a
real citation to its real `source_url`, but with `fields` dropped to
empty before it is ever placed in `structured_fields`: not summarized
by a reader, not truncated, simply never carried past `act_node` at
all, which is a stronger "never reach unmediated" than routing it
through a model first. `_citation_for_row`'s existing empty-fields
fallback (`f"{node_or_edge_type} {curie}"`) already handles the rest:
the citation reads "Article PMID:12345", never the title. The separate
reader-bound quarantine call (`_untrusted_rows_free_text`, still built
from the row's real, un-sanitized fields) is unchanged and still runs
against the same rows, for whatever future entity-extraction use a
later phase makes of it; it was never what made the record citable or
uncitable, so leaving it in place changes nothing about this fix.

Fifth adversary pass, 2026-08-01 (F-2.1-A5-06, F-2.1-A5-02): both findings
sit inside the F-2.1-B07 confidence-downgrade path this same docstring
already covers above.

    - F-2.1-A5-06: `_is_vocabulary_token_artifact("")` returns False on
      its own first line, so an empty or whitespace-only field value was
      never "suspect" and therefore outranked every flagged candidate in
      `_pick_representative_field`. Every `Disease` row this system's
      flagship question returns carries both empty fields (`xrefs`,
      `agent_type`, `knowledge_level`) and vocabulary-artifact fields
      (`name`, `source`, ...) side by side, so the picked field was
      always the empty one, cited at full `assertion_confidence` on
      every row of a correct answer: the exact rows the B07 hedge exists
      to catch. `_pick_representative_field` now excludes a blank
      candidate from consideration before the artifact check ever runs,
      so the ranking is a clean value, else a suspect-but-non-empty
      value (flagged), else the same "nothing to cite" fallback a row
      with no fields at all already used.
    - F-2.1-A5-02: `_is_vocabulary_token_artifact` protects the citation
      object `write_node` builds. It never touched
      `_cypher_output_to_structured_fields`'s own output, the `Finding.
      structured_fields` payload this docstring already documents as
      what a future phase's synthesis prompt reads, so that payload
      carried `fields: {"name": "MeSH", ...}` with no marker at all. A
      consumer reading `fields` directly, never the separate citation
      object, would see the corrupted value with nothing to say it is
      not a genuine name. `_dump_row_for_synthesis` now adds an
      additive `vocabulary_artifact_fields` key to each dumped row,
      naming which of that row's field keys tripped the same shape rule,
      without altering any existing key or value: `_pick_representative_
      field` still reads the identical, unmodified `fields` dict off the
      same dumped row (via `_citations_from_findings`) to make its own,
      separately-fixed decision.

Build phase 3.1, T-3.1-11/T-3.1-13/T-3.1-12 (this file's half), 2026-08-05.
F-2.1-07: `_KNOWN_GENE_SYMBOL_CURIES` held exactly one entry (BRCA1), so
every gene symbol other than BRCA1, roughly 20,000 of them, resolved to
nothing. Five realistic gene queries (TP53, BRCA2, EGFR, KRAS, MECP2)
tested by a judge all failed. Fixed by replacing the table outright, not
widening it:

    - `resolve_symbol_to_curie(symbol, *, taxon="human")`: the single
      chokepoint every live gene-symbol lookup passes through (case 14 of
      `tests/system_03_search_agent/tools/test_ncbi_efetch_premise.py`
      monkeypatches this exact module-level name to count calls, so it
      must stay a plain function other code calls by this name, never a
      bound alias captured at import time). Tries NCBI Datasets v2's
      `gene/symbol/{symbol}/taxon/{taxon}` first (one call, and it
      confirms the organism, per the same ortholog lesson build phase 2.1
      already paid for once), falling back to ESearch on `db=gene` with
      `{symbol}[sym] AND human[orgn]` when Datasets returns anything
      other than a clean, single, human match. Every call goes through
      `ncbi_efetch`, never a second HTTP path. Results are cached
      in-process for the life of the run (`_SYMBOL_CURIE_CACHE`): a
      symbol-to-CURIE mapping is about as stable as data gets, and this
      is a resolution-result cache, not the prompt-cache stable prefix
      `prompt-cache-discipline.md` governs, so it is not subject to that
      rule.
    - `resolve_entity_curies(query_text)`: the public entry point the
      premise gate's cases 12 and 13 import directly. `_extract_target_
      entities` (the name `_select_planned_tool_call` and `write_node`
      already called) is now a thin async alias for this function, kept
      so neither call site needed renaming, only awaiting.
    - F-3.1-01: arming T-3.1-11 without a filter turns the existing
      `_GENE_SYMBOL_TOKEN_PATTERN` scan, matched against
      `query_text.upper()` and therefore matching every 2-to-10-character
      word, into up to one live NCBI call per word in the query.
      `_SYMBOL_CANDIDATE_STOPWORDS` drops common English and domain
      filler words before any network call, a verbatim CURIE match's own
      text span is excluded from the symbol scan so an identifier already
      resolved exactly is never also fuzzy-matched, and
      `_MAX_LIVE_SYMBOL_LOOKUPS` (3) hard-caps live calls per query
      regardless of how complete the stopword list is. Case 14 of the
      premise gate pins the cap.
    - T-3.1-13/F-2.1-B10: before this fix, a gene-symbol-shaped token
      that failed to resolve still reached `cypher_query` with an empty
      `target_entities` list, the model still wrote Cypher referencing an
      unbound parameter, and AGE failed with `UndefinedParameter` after
      two model calls and roughly 21.7 seconds, surfaced to the user as a
      graph failure that was never true: the graph was never the thing
      that broke. `_select_planned_tool_call` now returns
      `_UnresolvedEntityRefusal` when at least one plausible candidate
      was looked up live and resolved to nothing and no other entity
      rescues the query; `plan_node` stores the attempted symbols on
      `GraphState.unresolved_entity_symbols` instead of building a tool
      call at all; `write_node` checks that field before its own synth
      call (the same early-exit shape `step_error` and `cap_exceeded`
      already use) and ships a refusal naming the unresolved symbol,
      spending zero synth calls and zero graph calls on a question that
      was never answerable. This is deliberately narrower than "empty
      `target_entities`": a query with no gene-shaped token at all (for
      example a disease named in plain English) still reaches
      `cypher_query` exactly as before, since an absent candidate and a
      candidate that was tried and failed are different facts.
    - write_node's own refusal-branch fallback-link decision (previously
      `resolved = _extract_target_entities(query.text)`, now a live call):
      re-resolving here would spend a second live NCBI lookup and its
      latency purely to build a link for a refusal already decided by
      other means. `write_node` now reuses the resolution `plan_node`
      already performed, read off `state["tool_calls"][0].cypher_input.
      target_entities`, since every branch reaching that line already ran
      `plan_node` (`cap_exceeded` and `step_error` both return earlier).
    - T-3.1-12 (this file's half): `_STABLE_PREFIX` now passes
      `list(REGISTERED_TOOL_SCHEMAS)` to `build_stable_prefix`, so both
      registered tool schemas (`cypher_query`, `ncbi_efetch`) actually
      reach the model's prompt for the first time; `cache.py`'s own
      docstring recorded this as the still-missing half since build phase
      2.1.
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
    TrustSignalPayload,
)
from system_03_search_agent.core.state import GraphState
from system_03_search_agent.data.session import session_scope
from system_03_search_agent.guardrail import classifier, forbidden, prefilter
from system_03_search_agent.guardrail.verdict import GuardVerdict
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness.cache import REGISTERED_TOOL_SCHEMAS, build_stable_prefix
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
from system_03_search_agent.synthesis.findings import (
    SynthFinding,
    build_synth_findings,
    build_synth_messages,
)
from system_03_search_agent.synthesis.grounding import (
    GroundingResult,
    display_index_by_citation_id,
    run_grounding_pass,
)
from system_03_search_agent.synthesis.refuse import (
    REFUSE_MESSAGE,
    build_fallback_link,
    build_refusal_text,
)
from system_03_search_agent.synthesis.trust import (
    ClaimTrust,
    aggregate,
    trust_for_claims,
)
from system_03_search_agent.tools.cypher_query import cypher_query
from system_03_search_agent.tools.cypher_schemas import (
    CypherQueryInput,
    CypherQueryOutput,
    CypherQueryRow,
)
from system_03_search_agent.tools.graph_schema_constants import (
    CURIE_PREFIXES,
    CYPHER_QUERY_TIMEOUT_SECONDS,
)
from system_03_search_agent.tools.ncbi_efetch import ncbi_efetch
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchInput

Message = dict[str, str]

# Built once at import time, matching `compiled_graph` below: the stable
# prefix is a deterministic function of `tool_schemas` alone (prompt-
# cache-discipline.md), so this is the same prefix for every
# guardrail/think/plan/write call the process makes. Rebuilding it per
# call would cost nothing functionally, since it is byte-identical every
# time, but computing it once removes any chance of it silently drifting
# between calls within a session, which is exactly what
# `prompt-cache-discipline.md` requires the harness to guarantee.
#
# T-3.1-12 (this file's half): `REGISTERED_TOOL_SCHEMAS` is
# `cache.py`'s own fixed, alphabetically-ordered tuple
# (`cypher_query`, then `ncbi_efetch`); passing it through here is what
# actually makes either tool's schema reach a model's prompt for the
# first time. Never re-order this tuple at call time: obligation 2 of
# `prompt-cache-discipline.md` requires the sort to be fixed in code, and
# `build_stable_prefix` itself re-sorts alphabetically by name regardless,
# so a call-site reorder here would change nothing except invite drift
# between the two orderings.
_STABLE_PREFIX = build_stable_prefix(list(REGISTERED_TOOL_SCHEMAS))


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

    # T-3.0-06. Section 10.1's remaining steps, each gating the next.
    #
    # The two daily caps above are Section 10.1's step 5 and run FIRST here,
    # not fifth. Recorded as finding F-3.0-02 rather than silently kept: the
    # existing order is strictly cheaper, since a capped user costs zero model
    # calls where the spec's order pays for a classification before finding
    # out the query cannot run at all. Reordering to match the spec would
    # spend money to be less correct.

    # Step 1, Section 10.2. No model call, so a confident match is free.
    # Returns None meaning UNDECIDED, never meaning admitted.
    prefilter_verdict = prefilter.screen(query.text)
    if prefilter_verdict is not None:
        return _decline_for_guardrail(state, sink, prefilter_verdict, charged=False)

    # Step 3, Section 10.4. The first and only model call this node makes.
    # Dispatched through `_dispatch_tier_call` rather than calling the
    # classifier's own helper, so this call gets the per-query cap pre-flight,
    # the step timeout, and `cache_prefix=_STABLE_PREFIX` like every other
    # model call in the loop. `guardrail/classifier.py` deliberately exposes
    # no wrapper that would let a caller skip this.
    try:
        response = await _dispatch_tier_call(
            harness,
            trace_id,
            "guard",
            "guardrail",
            classifier.build_messages(query.text),
            budget_s=budget_for_step("guardrail", "lookup"),
        )
    except cost_control.QueryCapExceededError:
        return {"cap_exceeded": True}
    except HarnessCallError as exc:
        return {"step_error": _step_error_kwargs("guardrail", exc)}

    try:
        classifier_verdict = classifier.verdict_for(
            classifier.parse_classification(response.content)
        )
    except classifier.ClassificationUnavailableError as exc:
        # The model answered, and the answer was unusable. Deliberately a
        # step error rather than a refusal: the classifier reached no verdict
        # about this query, so reporting one would tell the user something
        # false. What matters for safety is that this path does not admit,
        # and it does not.
        return {
            "step_error": {
                "source": "guardrail",
                "error_class": "recoverable",
                "message": str(exc)[:256],
                "retry_after_s": 0,
            }
        }

    if not classifier_verdict.admitted:
        return _decline_for_guardrail(state, sink, classifier_verdict, charged=True)

    # Step 4, Section 10.5. Runs after classification clears, per 10.1.
    forbidden_verdict = forbidden.screen(query.text)
    if forbidden_verdict is not None:
        return _decline_for_guardrail(state, sink, forbidden_verdict, charged=True)

    # Step 6. Nothing tripped.
    sink.emit("guard", GuardPayload(passed=True, category="ok", reason=None))
    sink.emit("cost", cost_control.build_cost_event_payload(harness, trace_id, "guard"))
    return sink.result()


def _decline_for_guardrail(
    state: GraphState,
    sink: _EventSink,
    verdict: GuardVerdict,
    *,
    charged: bool,
) -> dict[str, Any]:
    """Section 10.1's refusal path: emit the `guard` verdict, then stop.

    Distinct from `_decline_for_daily_cap`, which emits an `error` event. A
    guardrail refusal is not an error: the system worked exactly as designed
    and reached a judgement about the query. Emitting `error` would put a
    refused query and a broken run in the same bucket for every consumer
    downstream, including the premise gate that has to tell them apart.

    `charged` says whether a model call already happened, and therefore
    whether a `cost` event is owed. A pre-filter refusal costs nothing, and
    emitting a zero-dollar cost event for it would imply a call was made.
    """
    query = state["query"]
    harness = state["harness"]

    sink.emit(
        "guard",
        GuardPayload(
            passed=False,
            category=verdict.category,
            reason=verdict.reason,
        ),
    )
    if charged:
        sink.emit(
            "cost",
            cost_control.build_cost_event_payload(harness, query.trace_id, "guard"),
        )
    sink.emit(
        "done",
        DonePayload(
            total_cost_usd=(
                harness.get_query_cost_usd(query.trace_id) if charged else 0.0
            ),
            total_tool_calls=0,
            elapsed_ms=_elapsed_ms(state),
            trust_outcome="refuse",
        ),
    )
    return sink.result(guard_refused=True)


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
# T-3.0-06: now the same set the guardrail exempts from its Section 10.2
# off-topic check, imported rather than duplicated. Keeping two copies would
# let them drift into the worst possible state: a text the guardrail admits
# and the planner then sends to `cypher_query`, or a text the planner treats
# as small talk that the guardrail already refused.
_NO_TOOL_QUERY_TEXTS: frozenset[str] = prefilter.CONVERSATIONAL_TEXTS

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
# F-2.1-J04: `:` used to be inside the local-id character class, so a CURIE
# followed by ordinary sentence punctuation swallowed it. "NCBIGene:672: how
# many variants?" extracted `NCBIGene:672:`, which is not a CURIE that exists
# anywhere, and the greedy match REPLACED the correct one rather than sitting
# beside it, so a perfectly valid question silently queried nothing. Worse,
# `source_url_for_curie` still built a host-pinned URL for it
# (.../gene/672%3A), which passes the citation gate and resolves to a dead
# page: the pattern that guarantees a citation is NCBI-hosted cannot tell
# whether the record exists.
#
# A trailing `.` or `-` is excluded for the same reason. A CURIE's local id
# may contain them internally, so they stay in the class, but the match no
# longer ends on one.
_CURIE_IN_TEXT_PATTERN = re.compile(
    r"\b(?:"
    + "|".join(re.escape(prefix) for prefix in CURIE_PREFIXES)
    + r"):[A-Za-z0-9_](?:[A-Za-z0-9_.:-]*[A-Za-z0-9_])?"
)

# An ALL-CAPS alphanumeric token, 2 to 10 characters: the shape a live
# gene-symbol candidate must have before it is worth a network call.
# Matched against `query_text.upper()`, so it matches every 2-to-10-
# character word in the query, not just symbols (F-3.1-01). See
# `_SYMBOL_CANDIDATE_STOPWORDS` and `_gene_symbol_candidates` below for
# the filter that runs before any candidate this pattern finds reaches
# `resolve_symbol_to_curie`.
_GENE_SYMBOL_TOKEN_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]{1,9}\b")

# F-3.1-01: common English function words plus domain filler words that
# would otherwise pass `_GENE_SYMBOL_TOKEN_PATTERN`'s bare ALL-CAPS shape
# check and each cost one live NCBI call. Verified live: "What diseases
# are linked to TP53?" yields ['WHAT','DISEASES','ARE','LINKED','TO',
# 'TP53'] from the pattern alone. Deliberately over-inclusive rather than
# a precise part-of-speech filter, since a false exclusion here (a real
# gene symbol that happens to collide with a stopword, none currently
# known in this list) costs a missed resolution, while a false inclusion
# costs a wasted network call bounded by `_MAX_LIVE_SYMBOL_LOOKUPS`
# regardless. Not exhaustive; extend it when a new filler word is
# observed reaching a live call in practice.
_SYMBOL_CANDIDATE_STOPWORDS: frozenset[str] = frozenset(
    {
        # function / question words
        "WHAT", "WHICH", "WHO", "WHOM", "WHOSE", "WHERE", "WHEN", "WHY", "HOW",
        "IS", "ARE", "WAS", "WERE", "BE", "BEEN", "BEING", "AM",
        "DO", "DOES", "DID", "DOING", "DONE",
        "HAS", "HAVE", "HAD", "HAVING",
        "WILL", "WOULD", "SHALL", "SHOULD", "CAN", "COULD", "MAY", "MIGHT", "MUST",
        "THE", "A", "AN", "AND", "OR", "NOR", "BUT", "SO", "IF", "THEN", "ELSE",
        "TO", "OF", "IN", "ON", "AT", "BY", "FOR", "WITH", "FROM", "AS", "ABOUT",
        "INTO", "OVER", "UNDER", "BETWEEN", "AMONG", "THROUGH", "DURING",
        "BEFORE", "AFTER", "ABOVE", "BELOW", "UP", "DOWN", "OUT", "OFF", "AGAIN",
        "THIS", "THAT", "THESE", "THOSE", "IT", "ITS", "EACH", "EVERY", "ALL",
        "ANY", "SOME", "NO", "NOT", "ONLY", "OWN", "SAME", "SUCH", "MORE",
        "MOST", "OTHER", "FEW", "TOO", "VERY", "JUST", "ALSO", "THAN",
        "ONE", "TWO", "THREE", "MANY", "MUCH",
        # domain filler: not a symbol shape a `dataset_report`/ESearch
        # lookup would ever confirm, and asking anyway is a wasted call.
        "LINKED", "LINK", "LINKS", "RELATED", "RELATE", "RELATES",
        "ASSOCIATED", "ASSOCIATE", "ASSOCIATES", "ASSOCIATION", "ASSOCIATIONS",
        "DISEASE", "DISEASES", "DISORDER", "DISORDERS", "CONDITION", "CONDITIONS",
        "GENE", "GENES", "GENETIC", "GENOME", "GENOMES",
        "PROTEIN", "PROTEINS", "MUTATION", "MUTATIONS", "VARIANT", "VARIANTS",
        "EVIDENCE", "SUPPORTS", "SUPPORT", "SUPPORTED",
        "CAUSE", "CAUSES", "CAUSED", "CAUSING",
        "RISK", "RISKS", "FACTOR", "FACTORS",
        "SYMPTOM", "SYMPTOMS", "TREATMENT", "TREATMENTS", "TREAT", "TREATS",
        "PATIENT", "PATIENTS", "HUMAN", "HUMANS",
        "STUDY", "STUDIES", "RESEARCH", "PAPER", "PAPERS", "ARTICLE", "ARTICLES",
        "SHOW", "SHOWS", "SHOWN", "KNOWN", "KNOW", "TELL", "GIVE", "GIVEN",
        "LIST", "LISTS", "FIND", "FINDS", "LOOK", "LOOKS", "SEE", "SEES",
        "MEAN", "MEANS", "MEANING", "EXPLAIN", "EXPLAINS", "DESCRIBE",
        "COMPARE", "COMPARES", "COMPARED",
        "TIMES", "TYPE", "TYPES", "KIND", "KINDS",
        "PART", "PARTS", "ROLE", "ROLES", "USE", "USES", "USED", "USING",
        "NEW", "OLD", "GOOD", "BAD", "BETTER", "WORSE", "BEST", "WORST",
        "QUESTION", "QUESTIONS", "ANSWER", "ANSWERS",
    }
)

# F-3.1-01: a hard ceiling on live symbol lookups per query, independent
# of how complete the stopword list above is. Case 14 of the ncbi_efetch
# premise gate pins this at 3 for a 10-word question.
_MAX_LIVE_SYMBOL_LOOKUPS = 3

# In-process cache: a symbol-to-CURIE mapping is about as stable as data
# gets, so resolving a symbol once per process lifetime rather than once
# per query is the right cost/staleness trade. This is a resolution-
# result cache, not the prompt-cache stable prefix
# `prompt-cache-discipline.md` governs, so that rule does not apply to
# it. Keyed on the upper-cased symbol; `None` is a valid cached value,
# but ONLY when it is a genuinely confirmed non-resolution (both Datasets
# and ESearch answered and neither found the symbol), never when the
# lookup could not be completed at all. Distinguished from "not yet
# looked up" by key presence, not by the value's truthiness.
#
# Finding 2 (CRITICAL, re-review, 2026-08-05): before this fix, EVERY
# outcome from `_resolve_symbol_to_curie_uncached`, including a
# `status == "error"` from a timeout, connection failure, 5xx, or rate
# limit, was cached as `None` here unconditionally, permanently. During a
# transient NCBI outage a symbol would resolve to `None`, get cached, and
# stay unresolved forever, even after NCBI fully recovered, because the
# cache lookup at the top of `resolve_symbol_to_curie` short-circuits
# before any network call is attempted again. This comment used to claim
# "None is a valid cached value (an already-confirmed non-resolution)"
# while the code cached every `None`, confirmed or not, which is exactly
# the `self-eval-loop`'s "a comment that claims a property is a claim to
# be tested" pattern. `_resolve_symbol_to_curie_uncached` now returns
# `(curie, cacheable)`, and only a `cacheable=True` result is written
# here.
_SYMBOL_CURIE_CACHE: dict[str, str | None] = {}


async def resolve_symbol_to_curie(symbol: str, *, taxon: str = "human") -> str | None:
    """Resolve one gene symbol to its NCBIGene CURIE via a live Layer 2 call.

    T-3.1-11, replacing `_KNOWN_GENE_SYMBOL_CURIES` (F-2.1-07): that table
    held exactly one entry, BRCA1, so every other gene symbol, roughly
    20,000 of them, resolved to nothing. This is the single chokepoint
    every live gene-symbol lookup passes through: case 14 of
    `tests/system_03_search_agent/tools/test_ncbi_efetch_premise.py`
    monkeypatches this exact module-level name to count calls, so any
    caller must reach it by this name at call time (a plain module-level
    `await resolve_symbol_to_curie(...)`, never a reference captured once
    at import time), or the monkeypatch, and this docstring's own
    contract, silently stop applying.

    Two sources, in order, both reached only through `ncbi_efetch`
    (never a second HTTP path):

    1. NCBI Datasets v2, `dataset_report` with `report_type="gene"`. One
       call resolves a symbol straight to a `gene_id`, and its response
       carries `taxname`, so the organism is confirmed in the same round
       trip. Requiring `taxname == "Homo sapiens"` here is deliberate,
       not incidental: build phase 2.1's flagship failure was a query
       that silently answered from a non-human ortholog, and skipping
       this check would reopen exactly that class of defect one layer
       up, in resolution rather than in query generation.
    2. ESearch on `db="gene"` with `term="{symbol}[sym] AND human[orgn]"`,
       tried only when Datasets does not return a clean single human
       match (a bad symbol is a live-verified HTTP 200 with an empty
       body there, not an error, so this is the expected path for an
       unresolvable symbol, not a failure path). Only an UNAMBIGUOUS
       single id is accepted; zero or multiple ids resolve to `None`
       rather than guessing among them, matching this whole system's
       existing rule that an unrecognized or ambiguous token contributes
       nothing rather than a fabricated CURIE.

    Never raises: `ncbi_efetch` itself never raises (see that module's
    own docstring), so nothing here needs its own try/except around the
    network call.

    Cached in `_SYMBOL_CURIE_CACHE` for the life of the process, but ONLY
    when `_resolve_symbol_to_curie_uncached` reports the result as a
    genuinely confirmed non-resolution (Finding 2, CRITICAL, re-review):
    a symbol both Datasets and ESearch answered and neither could find is
    cached as `None` forever, since that is stable data. A symbol neither
    call could even ask about, a timeout, connection failure, 5xx, or
    rate limit, is never cached, so the next query for the same symbol
    retries the live lookup rather than replaying a stale outage.
    """
    cache_key = symbol.strip().upper()
    if cache_key in _SYMBOL_CURIE_CACHE:
        return _SYMBOL_CURIE_CACHE[cache_key]

    curie, cacheable = await _resolve_symbol_to_curie_uncached(cache_key, taxon)
    if cacheable:
        _SYMBOL_CURIE_CACHE[cache_key] = curie
    return curie


async def _resolve_symbol_to_curie_uncached(symbol: str, taxon: str) -> tuple[str | None, bool]:
    """Returns `(curie, cacheable)`.

    `cacheable` is `True` only when the `None` (or resolved) result is a
    genuine, confirmed answer the live APIs actually gave, never when a
    branch had to give up because a call errored out. See Finding 2's
    account above `_SYMBOL_CURIE_CACHE`'s declaration.
    """
    dataset_output = await ncbi_efetch(
        NcbiEfetchInput.model_validate(
            {
                "action": "dataset_report",
                "report_type": "gene",
                "symbol": symbol,
                "taxon": taxon,
            }
        )
    )
    # Finding 5 (MAJOR, re-review): mirror the ESearch guard below
    # exactly. Before this fix, `dataset_output.records[0]` was taken
    # with no ambiguity check at all, while the ESearch fallback twenty
    # lines below explicitly refuses on `len(idlist) != 1` ("never
    # fabricate a CURIE by guessing among candidates"). `dataset_report`
    # can return up to 100 records, so an ambiguous Datasets response
    # used to silently pick an arbitrary first record instead of falling
    # through to the ESearch path the way a genuinely ambiguous match
    # should. Zero records or more than one record both fall through to
    # the ESearch path below; only exactly one resolves here.
    if dataset_output.status == "ok" and len(dataset_output.records) == 1:
        fields = dataset_output.records[0].fields
        gene_id = fields.get("gene_id")
        taxname = fields.get("taxname")
        if gene_id and taxname == "Homo sapiens":
            return f"NCBIGene:{gene_id}", True

    search_output = await ncbi_efetch(
        NcbiEfetchInput.model_validate(
            {
                "action": "search",
                "db": "gene",
                "term": f"{symbol}[sym] AND human[orgn]",
                "retmax": 5,
            }
        )
    )
    if search_output.status == "error":
        # Finding 2: a transient failure (timeout, connection error, 5xx,
        # rate limit), not a confirmed non-resolution. Never cache this;
        # the next query for the same symbol must retry live rather than
        # replaying a stale outage forever.
        return None, False
    if search_output.status != "ok" or not search_output.records:
        # A genuine zero-hit search (status "empty", or "ok" with no
        # records): both APIs answered and neither found the symbol. A
        # confirmed non-resolution, safe to cache.
        return None, True

    idlist = search_output.records[0].fields.get("idlist")
    if not isinstance(idlist, list) or len(idlist) != 1:
        # Zero hits, or an ambiguous multi-id match: never fabricate a
        # CURIE by guessing among candidates. Both are confirmed answers
        # from a successful call, safe to cache.
        return None, True

    gene_id = idlist[0]
    return (f"NCBIGene:{gene_id}", True) if gene_id else (None, True)


def _span_overlaps_any(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    return any(span[0] < end and start < span[1] for start, end in spans)


@dataclass(frozen=True)
class _EntityResolution:
    """The full result of resolving one query text's entities.

    `curies` is what `resolve_entity_curies` (the public entry point) and
    `_extract_target_entities` (the back-compat alias every existing call
    site uses) return. `unresolved_symbols` is the extra signal T-3.1-13
    needs and neither of those two names carries: which gene-symbol-
    shaped candidates were looked up live and confirmed to resolve to
    nothing. Computed once, in one pass, so `_select_planned_tool_call`
    never pays for a second round of live lookups just to learn what the
    first round already knew.
    """

    curies: list[str]
    unresolved_symbols: list[str]


async def _resolve_query_entities(query_text: str) -> _EntityResolution:
    """Deterministically extract candidate CURIEs referenced by `query_text`.

    Fixes findings A3/F-02: `plan_node` used to hand `cypher_query` an
    unconditionally empty `target_entities` list, so the generated
    Cypher's named parameter never had a value to bind, and every query
    dead-ended in `status: "error"` (an unbound parameter) or a validator
    rejection (a literal interpolated instead). Two sources:

    1. A CURIE the caller already typed verbatim, matched against
       `_CURIE_IN_TEXT_PATTERN`, taken as given. No network call.
    2. An ALL-CAPS token matched against `_GENE_SYMBOL_TOKEN_PATTERN`,
       filtered through `_SYMBOL_CANDIDATE_STOPWORDS` and de-duplicated
       against any span a verbatim CURIE match already covers (F-3.1-01:
       an identifier already resolved exactly is never also fuzzy-
       matched as a bare symbol), then resolved live via
       `resolve_symbol_to_curie`, capped at `_MAX_LIVE_SYMBOL_LOOKUPS`
       live calls regardless of how many candidates survive filtering
       (T-3.1-11, replacing `_KNOWN_GENE_SYMBOL_CURIES`).

    A candidate that resolves to nothing contributes nothing to `curies`
    but is recorded in `unresolved_symbols`: this function never guesses
    or fabricates a CURIE for a symbol it cannot confirm. That distinction
    is what T-3.1-13 needs: "no gene-shaped token in the query" and "a
    gene-shaped token was tried and NCBI does not know it" are different
    facts, and only the second one is what F-2.1-B10 requires a refusal
    for.

    `curies` is capped at `_TARGET_ENTITIES_MAX_ITEMS`, matching
    `CypherQueryInput.target_entities`'s own schema bound, and
    de-duplicated while preserving first-seen order.
    """
    found: list[str] = []
    seen: set[str] = set()
    matched_spans: list[tuple[int, int]] = []

    for match in _CURIE_IN_TEXT_PATTERN.finditer(query_text):
        curie = match.group(0)
        matched_spans.append(match.span())
        if curie not in seen:
            seen.add(curie)
            found.append(curie)

    unresolved: list[str] = []
    live_lookups = 0
    for token_match in _GENE_SYMBOL_TOKEN_PATTERN.finditer(query_text.upper()):
        if live_lookups >= _MAX_LIVE_SYMBOL_LOOKUPS:
            break
        token = token_match.group(0)
        if token in _SYMBOL_CANDIDATE_STOPWORDS:
            continue
        if _span_overlaps_any(token_match.span(), matched_spans):
            continue

        live_lookups += 1
        curie = await resolve_symbol_to_curie(token)
        if curie is not None:
            if curie not in seen:
                seen.add(curie)
                found.append(curie)
        else:
            unresolved.append(token)

    return _EntityResolution(
        curies=found[:_TARGET_ENTITIES_MAX_ITEMS], unresolved_symbols=unresolved
    )


async def resolve_entity_curies(query_text: str) -> list[str]:
    """The public entry point T-3.1-11's premise gate imports directly
    (cases 12 and 13). See `_resolve_query_entities` for the full
    contract; this returns only the resolved CURIE list, the same shape
    `_extract_target_entities` always returned.
    """
    resolution = await _resolve_query_entities(query_text)
    return resolution.curies


async def _extract_target_entities(query_text: str) -> list[str]:
    """Back-compat alias for `resolve_entity_curies`.

    Kept so `_select_planned_tool_call` and `write_node`'s refusal
    branch, both already calling this name before T-3.1-11, needed only
    an `await` added at their call sites, not a rename. The real
    implementation and its docstring live on `resolve_entity_curies` and
    `_resolve_query_entities`.
    """
    return await resolve_entity_curies(query_text)


@dataclass(frozen=True)
class _UnresolvedEntityRefusal:
    """T-3.1-13/F-2.1-B10: at least one gene-symbol-shaped candidate in
    the query text was looked up live and confirmed to resolve to
    nothing, and no other entity (a verbatim CURIE, or a different
    candidate that did resolve) rescues the query.

    Before this fix, this case still reached `cypher_query` with an
    empty `target_entities` list. The model still wrote Cypher
    referencing an unbound parameter for the gene name, and AGE failed
    with an opaque `UndefinedParameter` after two model calls and
    roughly 21.7 seconds, a graph failure that was never true: the graph
    never had a chance to fail, because there was nothing to look up.
    `_select_planned_tool_call` returns this instead of a
    `_PlannedToolCall` in that case, so `plan_node` can refuse before
    either the graph or a second model call is ever reached.
    """

    attempted_symbols: list[str]


async def _select_planned_tool_call(
    query_text: str, query_class: QueryClass
) -> _PlannedToolCall | _UnresolvedEntityRefusal | None:
    """Deterministically select `cypher_query`, refuse, or select nothing.

    Returns `None` for empty or plainly non-substantive text
    (`_NO_TOOL_QUERY_TEXTS`): unchanged from before this ticket.

    Returns `_UnresolvedEntityRefusal` (T-3.1-13) when
    `_resolve_query_entities` found no usable CURIE at all but did find
    at least one gene-symbol-shaped candidate that a live lookup
    confirmed does not resolve. This is deliberately narrower than "empty
    `target_entities`": a query with no gene-shaped token whatsoever (for
    example a disease named in plain English, which this module's
    resolution never attempts to look up) still falls through to the
    normal `_PlannedToolCall` branch below with an empty
    `target_entities` list, exactly as before this ticket. Only a
    candidate that was tried and failed triggers a refusal.

    Otherwise returns a `_PlannedToolCall` carrying a `CypherQueryInput`
    built from the raw query text as `query_intent` (capped to Section
    6.1's 1000-char bound), `query_class` from Think's classification,
    `target_entities` from `_resolve_query_entities` (T-3.1-11: real,
    live-resolved CURIEs, never fabricated), and the default row_limit.
    """
    normalized = query_text.strip().lower()
    if not normalized or normalized in _NO_TOOL_QUERY_TEXTS:
        return None

    resolution = await _resolve_query_entities(query_text)
    if not resolution.curies and resolution.unresolved_symbols:
        return _UnresolvedEntityRefusal(attempted_symbols=resolution.unresolved_symbols)

    cypher_input = CypherQueryInput(
        query_intent=query_text[:_PLAN_TOOL_CALL_MAX_INTENT_CHARS],
        query_class=query_class,
        target_entities=resolution.curies,
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

    planned = await _select_planned_tool_call(query.text, query_class)
    if isinstance(planned, _UnresolvedEntityRefusal):
        # T-3.1-13/F-2.1-B10: refuse now, before act_node ever dispatches
        # a tool call and before write_node's own synth call, rather than
        # letting an unbound Cypher parameter reach the graph and fail
        # there as an opaque `UndefinedParameter`.
        plan_payload = PlanPayload(
            narrative=(
                "no tool selected; unresolved gene symbol candidate(s): "
                + ", ".join(planned.attempted_symbols)
            )[:500],
            tool_calls=[],
        )
        sink.emit("plan", plan_payload)
        sink.emit("cost", cost_control.build_cost_event_payload(harness, trace_id, "plan"))
        return sink.result(
            tool_calls=[], unresolved_entity_symbols=planned.attempted_symbols
        )
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


def _dump_row_for_synthesis(row: CypherQueryRow) -> dict[str, Any]:
    """Serialize one row exactly as `model_dump` always has, plus the
    F-2.1-A5-02 marker: `vocabulary_artifact_fields`, the keys of `row.
    fields` whose value is a known ETL vocabulary-token artifact
    (`_is_vocabulary_token_artifact`, F-2.1-B07).

    Additive only. Every existing key and value is unchanged, in
    particular `fields` itself: `_citation_for_row` reads this exact
    dumped dict (via `_citations_from_findings`, which iterates
    `finding.structured_fields["rows"]`, the list this function builds),
    and `_pick_representative_field`'s own F-2.1-A5-06 fix already
    decides, from those unmodified values, which field a citation is
    built from and whether to hedge it. This function does not duplicate
    or override that decision; it gives a consumer of the row as a whole
    (the future synthesis prompt, per this module's docstring, which
    already notes `fields` is what gets serialized there) an explicit
    signal to act on instead of reading, for example, `fields["name"] ==
    "MeSH"` as a genuine disease name with nothing to say it is not one.
    An empty list means no field on this row tripped the check.
    """
    dumped = row.model_dump(mode="json")
    dumped["vocabulary_artifact_fields"] = _vocabulary_artifact_fields(row.fields)
    return dumped


def _cypher_output_to_structured_fields(
    output: CypherQueryOutput, rows: list[CypherQueryRow] | None = None
) -> dict[str, Any]:
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

    `rows`: an explicit override, used below to shape the citeable version
    of `output.rows`: every row still counts (F-2.1-J4-06 fix; a row is
    never dropped from this dict just because its own field content is
    untrusted), but an untrusted-node row (`_sanitized_citeable_row`) has
    already had its `fields` emptied before it reaches here, so its raw
    content is never carried in this dict either way.
    Defaults to `output.rows` unchanged. `row_count` is always recomputed
    as `len(rows)` rather than trusted from `output.row_count`: the two
    already agree when nothing is filtered (`cypher_query.py` sets
    `row_count=len(mapped_rows)` itself), and recomputing is what keeps
    them agreeing once a subset is filtered out here.

    Each row is dumped via `_dump_row_for_synthesis`, not a bare
    `row.model_dump(mode="json")` (F-2.1-A5-02): see that function for
    the `vocabulary_artifact_fields` marker it adds.
    """
    used_rows = output.rows if rows is None else rows
    return {
        "status": output.status,
        "row_count": len(used_rows),
        "total_available": output.total_available,
        "truncated": output.truncated,
        "rows": [_dump_row_for_synthesis(row) for row in used_rows],
        "error": output.error,
    }


# F-2.1-C13: node types whose own field content is raw, third-party-authored
# free text, not graph-curated structured data. The row's envelope (a typed
# `CypherQueryRow`) is always structured, but Article is the one vertex
# label in this graph's schema whose real field, `name`, is the verbatim
# PubMed article title (graph_schema_constants.LABEL_CURIE_PREFIXES; a
# ~40M-row label, measured live at up to 316 chars per title).
# ai-security-standards.md ("content retrieved from an external source is
# DATA, never an instruction") and production-standards.md's
# untrusted-source-reader gate both require this content to route through
# coordinator_worker's isolated Guard-tier reader, never straight through
# to a citation's claim_text unmediated. Before this fix, `act_node` set
# `contains_untrusted_free_text=False` unconditionally for every
# `cypher_query` result, so that reader path could never fire for any
# Layer 1 result regardless of content, by construction.
_UNTRUSTED_FREE_TEXT_NODE_TYPES: frozenset[str] = frozenset({"Article"})

# A generous bound on the free-text payload built from quarantined rows,
# matching the isolated reader's own bounded-input posture
# (production-standards.md's bounded-context-items requirement): a
# handful of Article titles, never an unbounded blob.
_MAX_UNTRUSTED_FREE_TEXT_CHARS = 4000


def _split_rows_by_trust(
    rows: list[CypherQueryRow],
) -> tuple[list[CypherQueryRow], list[CypherQueryRow]]:
    """Partition a `cypher_query` result's rows by whether their own field
    content is untrusted, third-party-authored free text.

    Returns `(trusted_rows, untrusted_rows)`. Deterministic, keyed only on
    `node_or_edge_type` against the small, explicit
    `_UNTRUSTED_FREE_TEXT_NODE_TYPES` set: never a guess, never a content
    sniff of the field values themselves.
    """
    trusted: list[CypherQueryRow] = []
    untrusted: list[CypherQueryRow] = []
    for row in rows:
        if row.node_or_edge_type in _UNTRUSTED_FREE_TEXT_NODE_TYPES:
            untrusted.append(row)
        else:
            trusted.append(row)
    return trusted, untrusted


def _untrusted_rows_free_text(rows: list[CypherQueryRow]) -> str:
    """Render quarantined untrusted rows as the one free-text payload
    `coordinator_worker`'s isolated reader is given.

    This string is passed to `ToolExecutionResult.free_text` only.
    `coordinator_worker._reader_pass`/`_parse_reader_response` read it
    solely to build the reader's own bounded prompt and never copy it
    onto the returned `Finding` (that module's own docstring guarantee);
    it never reaches `structured_fields`, `claim_text`, or any other field
    `write_node` reads to build a citation.
    """
    lines = [f"{row.curie}: {row.fields.get('name', '')}" for row in rows]
    return "\n".join(lines)[:_MAX_UNTRUSTED_FREE_TEXT_CHARS]


def _sanitized_citeable_row(row: CypherQueryRow) -> CypherQueryRow:
    """F-2.1-J4-06 fix: an untrusted-type row's own record must still be
    countable and citeable; only its own free-text field content must
    never reach `structured_fields` unmediated.

    C13's original fix dropped an untrusted row (Article) out of
    `_cypher_output_to_structured_fields` entirely, not just its `fields`.
    That made `row_count` disagree with `total_available` on the `Finding`
    (F-2.1-C07's exact contradiction, one layer up) and made an
    Article-only result refuse outright, silently, since `write_node`
    never learned the drop was the cause. `fields` is the only untrusted
    part of the row (an Article's `name` is the verbatim PubMed title;
    see the module docstring's fourth-judge-pass note); `node_or_edge_type`,
    `curie`, `source_url`, and `graph_snapshot_version` are graph-curated
    structured data, never third-party-authored text, and are kept as-is.
    Emptying `fields` here means the raw title is never carried into
    `structured_fields` at all, not merely mediated through a reader
    first: `_citation_for_row`'s existing empty-fields fallback
    (`f"{node_or_edge_type} {curie}"`) still earns the record a real
    citation to its real `source_url`, just with no title text in it.
    """
    return row.model_copy(update={"fields": {}})


def _rows_for_citation(rows: list[CypherQueryRow]) -> list[CypherQueryRow]:
    """Shape every row of a `cypher_query` result into the version that
    counts toward `row_count`/`total_available` and is citation-eligible.

    F-2.1-J4-06 fix: every row is kept, in its original order, so a query
    whose result happens to be entirely Article rows still reports the
    real row count and still earns real citations. An untrusted-type row
    is replaced with its sanitized copy (`_sanitized_citeable_row`); every
    other row passes through unchanged, exactly as before this fix.
    """
    return [
        row
        if row.node_or_edge_type not in _UNTRUSTED_FREE_TEXT_NODE_TYPES
        else _sanitized_citeable_row(row)
        for row in rows
    ]


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

        # F-2.1-C13: a Cypher row's envelope is structured data (Section
        # 6.1's typed output schema), but an Article row's own field
        # content (the raw PubMed title) is untrusted external free text.
        # F-2.1-J4-06 fix: C13's original split excluded an Article row
        # from the structured pass-through payload entirely, which made
        # row_count disagree with total_available (F-2.1-C07's
        # contradiction, one layer up) and made an Article-only result
        # refuse outright, silently. Every row, trusted or not, now goes
        # into the structured pass-through payload via `_rows_for_citation`
        # (an untrusted row's `fields` already emptied, never its whole
        # row dropped), so row_count and total_available always agree and
        # a real record is never silently disappeared. The untrusted rows'
        # own free-text content is separately quarantined into a second,
        # reader-bound tool_call/result pair, same as before this fix, so
        # that content still never reaches structured_fields or a
        # citation's claim_text unmediated; it just no longer gates
        # whether the record itself is countable and citeable.
        _, untrusted_rows = _split_rows_by_trust(output.rows)
        results.append(
            ToolExecutionResult(
                contains_untrusted_free_text=False,
                structured_fields=_cypher_output_to_structured_fields(
                    output, _rows_for_citation(output.rows)
                ),
            )
        )
        if untrusted_rows:
            untrusted_call = ToolCall(
                tool=planned.tool_call.tool,
                call_id=f"{planned.tool_call.call_id}-articles"[:64],
                layer=planned.tool_call.layer,
            )
            tool_calls.append(untrusted_call)
            results.append(
                ToolExecutionResult(
                    contains_untrusted_free_text=True,
                    free_text=_untrusted_rows_free_text(untrusted_rows),
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


# F-2.1-B07: `docs/data-engineering/Knowledge_graph_on_server_reference.md`
# section M documents the root cause directly: "MedGen Disease nodes have
# `name` populated with source-vocabulary codes such as `SNOMEDCT_US`
# instead of human-readable disease names... Root cause is in the MedGen
# ETL parser." That is System 1/2's data defect, out of this repo's
# scope to fix at the source (file-protection.md forbids touching ETL
# code). What is this repo's own defect is stapling
# `assertion_confidence="asserted"` onto a citation built from one of
# these corrupted values: asserting high confidence in a value that is
# actually a controlled-vocabulary system name, not the disease name it
# claims to be, is a trust-signal defect regardless of who introduced the
# bad value.
#
# Confirmed live (BRCA1's four MedGen-associated diseases): "MeSH",
# "MONDO", "MedGen", "MedGen". The doc above independently names
# "SNOMEDCT_US" as the same class of defect. A fix keyed to those literal
# strings would miss the next UMLS source-vocabulary abbreviation this
# ETL bug produces, so `_is_vocabulary_token_artifact` below is a shape
# rule, not a lookup table: every confirmed bad value is a single token
# (no whitespace) that either exactly names a known source vocabulary
# already canonical in this codebase (`CURIE_PREFIXES`, which already
# lists "MedGen"/"MeSH"/"MONDO" as this graph's own source-database
# prefixes) or fails to read as an ordinary English word (not all
# lowercase, not simple Title Case, and either mixed-case in a way no
# disease name in this data is written (`MeSH`, `MedGen`) or fully
# upper-case and longer than a real standalone medical abbreviation would
# plausibly be ("MONDO", "SNOMEDCT_US" versus "HIV", "AIDS", "COPD",
# "SIDS")). A short, fully upper-case value is deliberately let through
# as plausibly legitimate: downgrading confidence is the safe failure
# mode this system prefers (production-standards.md's cite-or-refuse
# ethos: under-confidence is cheap, over-confidence is the trust moat),
# so the one acknowledged residual gap, a longer legitimate all-caps name
# (for example "COVID-19") being downgraded as a false positive, is an
# accepted, documented trade rather than a silent one.
_MAX_PLAUSIBLE_ABBREVIATION_CHARS = 4

# F-2.1-J5-04. The shape rule above is real, and an exhaustive census of
# all 200,845 `Disease` rows on 2026-07-31 showed it still missed 15,466
# of them, because three of the leaked tokens are short all-caps values
# the rule deliberately lets through in order to protect genuine short
# abbreviations.
#
# Measured, with row counts: the two largest leaked names were already
# caught; three short all-caps vocabulary names totalling 13,384 rows were
# missed, one Title Case vocabulary name of 968 rows was missed, three
# multi-word qualifier forms totalling 1,103 rows were missed, and the ETL
# stub placeholders were missed entirely.
#
# These are source-vocabulary abbreviations that leaked into MedGen's name
# column. The graph's own `source` field cannot separate them, since it
# reads "MedGen" for every one of those rows regardless of which
# vocabulary leaked, so it is not the discriminator it first appears to be.
#
# The set below is census-derived, not invented: every entry was read off
# the live graph with its row count. Stated plainly as the residual, a
# strictly better rule exists and is not built here. A genuine disease
# name is close to unique, so a name shared by tens of thousands of
# distinct records is by definition not one, and a precomputed name
# frequency table would catch the next leaked vocabulary with no list at
# all. That needs a build-time artifact this phase does not have, and is
# filed for build phase 2.2.
_LEAKED_VOCABULARY_NAMES = frozenset(
    {"HPO", "GARD", "OMIM", "Orphanet", "SNOMEDCT_US", "UMLS", "ORDO"}
)
_ETL_STUB_PREFIX = "[stub]"


def _is_vocabulary_token_artifact(value: str) -> bool:
    """True when `value` looks like a bare controlled-vocabulary system
    name or source-abbreviation code rather than a genuine, human-
    readable field value. See the module comments above for the reasoning
    and the confirmed examples this rule is built from.
    """
    text = value.strip()
    if not text:
        return False

    # An ETL stub placeholder is never a disease name, whatever its shape.
    if text.startswith(_ETL_STUB_PREFIX):
        return True

    # F-2.1-J5-04: a vocabulary token followed by a qualifier is still a
    # vocabulary token, so the multi-word qualifier forms are caught
    # alongside the bare token. The token must be the whole first word, so
    # a genuine name that merely begins with the same letters is
    # unaffected.
    first_token = text.split(" ", 1)[0]
    if first_token in _LEAKED_VOCABULARY_NAMES or first_token in CURIE_PREFIXES:
        return True

    if " " in text:
        return False
    if text.islower():
        return False
    if text[0].isupper() and text[1:].islower():
        return False
    return not (text.isupper() and len(text) <= _MAX_PLAUSIBLE_ABBREVIATION_CHARS)


def _vocabulary_artifact_fields(fields: dict[str, Any]) -> list[str]:
    """List every key in a row's `fields` dict whose value trips
    `_is_vocabulary_token_artifact`, sorted for a deterministic order.

    F-2.1-A5-02: `_pick_representative_field`/`_citation_for_row` only
    ever look at ONE field per row, and only ever act on what they find
    by downgrading a `CitationPayload`'s `assertion_confidence`. That
    protects the citation object built in `write_node`. It says nothing
    about `_cypher_output_to_structured_fields`'s own output, the
    `Finding.structured_fields` payload this module's docstring already
    documents as what a future phase's synthesis prompt reads: a row
    there carries `fields: {"name": "MeSH", ...}` with no marker
    distinguishing it from a genuine disease name, so a consumer that
    reads `fields` directly (never inspecting the separate citation
    object) sees the corrupted value with no qualification at all. This
    function is called from `_dump_row_for_synthesis` to attach that
    qualification as an explicit, additive key on the dumped row, so a
    synthesis-prompt consumer has something to act on beyond the raw
    string. It never removes or rewrites a field value: `_pick_
    representative_field` still needs the original values, unmodified,
    to keep doing its own job on the very same dumped `fields` dict (see
    `_citations_from_findings`, which reads `finding.structured_fields
    ["rows"]`, the output of this same dump, to build every citation).
    """
    return sorted(
        key
        for key, value in fields.items()
        if isinstance(value, str) and _is_vocabulary_token_artifact(value)
    )


def _pick_representative_field(
    fields: dict[str, Any],
) -> tuple[str, Any, bool] | tuple[None, None, bool]:
    """Pick one field off a row to ground a citation's `claim_text` in,
    and report whether the picked value looks like a vocabulary-token
    parse artifact rather than a genuine field value.

    Deterministic, never a model judgment: prefer a `name` field when
    present (the most human-readable field most rows carry), else the
    row's own insertion order, exactly as before F-2.1-B07. The one
    change that finding requires: a candidate field whose value trips
    `_is_vocabulary_token_artifact` is skipped in favor of the next
    candidate first ("preferring a different representative field when
    the name is an artifact"), and only returned, flagged, when every
    candidate is equally suspect, so the record still gets a real citation
    rather than none, but `_citation_for_row` can downgrade
    `assertion_confidence` instead of asserting it at full strength. A row
    with no fields at all yields `(None, None, False)`; the caller falls
    back to citing the row's bare identity (its type and CURIE).

    F-2.1-A5-06: an empty or whitespace-only string is never a citeable
    claim, so it must never be preferred over a suspect-but-present
    value, let alone a clean one. Before this fix `_is_vocabulary_token_
    artifact("")` returned False on its first line (a blank string is not
    "suspect"), so a genuinely empty field such as `xrefs=''` outranked
    every flagged candidate and was cited at full `assertion_confidence`,
    exactly on the rows the B07 hedge exists to catch (every `Disease`
    row this system's flagship question returns carries both empty
    fields and vocabulary-artifact fields side by side). Empty candidates
    are excluded from consideration entirely, before the artifact check
    ever runs, so the ranking is: a clean non-empty value, else a
    suspect-but-non-empty value (flagged), else the same `(None, None,
    False)` "nothing to cite" fallback a row with no fields at all
    already used, since a field that is only ever an empty string is, for
    citation purposes, no field at all.
    """
    if not fields:
        return None, None, False

    def _is_artifact(value: Any) -> bool:
        return isinstance(value, str) and _is_vocabulary_token_artifact(value)

    def _is_blank(value: Any) -> bool:
        return isinstance(value, str) and not value.strip()

    preferred_keys = (["name"] if "name" in fields else []) + [
        key for key in fields if key != "name"
    ]
    usable_keys = [key for key in preferred_keys if not _is_blank(fields[key])]

    for key in usable_keys:
        if not _is_artifact(fields[key]):
            return key, fields[key], False

    if usable_keys:
        # Every non-empty candidate looked like a vocabulary-token
        # artifact. Still cite the first-preference one (a suspect real
        # value beats no value), flagged so the caller downgrades
        # confidence rather than asserting it.
        key = usable_keys[0]
        return key, fields[key], True

    # Every candidate field was empty or whitespace-only. There is
    # nothing here to ground a claim in beyond the row's own type and
    # CURIE, the identical fallback a row with no fields at all uses.
    return None, None, False


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
    NCBI-native, US-federal-government record).
    `assertion_confidence` is Section 9.2's default, "asserted", for a
    plain field with no hedge or conflict signal, EXCEPT when
    `_pick_representative_field` flags the picked value as a
    vocabulary-token parse artifact (F-2.1-B07: a `Disease`/`OntologyClass`
    row's stored `name` is sometimes a source-vocabulary code such as
    "MeSH" or "SNOMEDCT_US", not the disease name it claims to be, a
    documented MedGen ETL defect, `docs/data-engineering/
    Knowledge_graph_on_server_reference.md` section M). Section 9.2's
    three-value enum has no dedicated state for "the value itself looks
    corrupted"; "hedged" (Section 9.2: reduced confidence with no known
    conflicting record) is the closer, spec-compliant fit versus
    "contested" (which implies a specific conflicting interpretation this
    case does not have) or leaving it at "asserted" (which is exactly the
    trust-signal defect this fix closes). `population_ancestry_context`
    stays None: no population or ancestry field exists on a Layer 1 graph
    row.
    """
    source_url = row.get("source_url")
    if not source_url:
        return None
    curie = str(row.get("curie", ""))[:100]
    prefix = curie.split(":", 1)[0] if ":" in curie else "cypher_query"
    fields = row.get("fields") or {}
    field_name, field_value, field_is_suspect = _pick_representative_field(fields)
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
        assertion_confidence="hedged" if field_is_suspect else "asserted",
        population_ancestry_context=None,
        license="public_domain_us_gov",
    )


def _citations_from_findings(findings: list[Finding]) -> tuple[list[CitationPayload], bool]:
    """Build every citation earned by this query's real, `"ok"` tool results.

    Only `structured_pass_through` findings with `status == "ok"`
    contribute: a `cypher_query` row is structured data, never routed
    through the free-text reader (`coordinator_worker.py`'s own module
    docstring), so every row this phase can cite arrives this way.
    Capped at `_MAX_CITATIONS_PER_ANSWER`, the same defense-in-depth
    posture every other emitted list in this module already carries
    (production-standards.md's multi-agent pipeline gate).

    Returns `(citations, capped_by_citation_limit)`. F-2.1-C12: the old
    version returned only the capped list, so a caller had no way to tell
    "every citeable row is shown" from "there were more citeable rows than
    `_MAX_CITATIONS_PER_ANSWER` and the rest were silently dropped". The
    full citeable list is built first so the comparison is exact (never a
    false positive from stopping exactly at the cap with nothing left).
    """
    citations: list[CitationPayload] = []
    for finding in findings:
        fields = finding.structured_fields
        if fields is None or fields.get("status") != "ok":
            continue
        for row in fields.get("rows", []):
            citation = _citation_for_row(finding.call_id, finding.layer, row, len(citations) + 1)
            if citation is not None:
                citations.append(citation)
    capped_by_citation_limit = len(citations) > _MAX_CITATIONS_PER_ANSWER
    return citations[:_MAX_CITATIONS_PER_ANSWER], capped_by_citation_limit


# F-2.1-10 fix: `Finding.truncated` (coordinator_worker.py's F-03 fix) was
# added specifically so a caller could tell "the tool succeeded and this
# is everything it found" from "the tool succeeded but the result was cut
# to fit the 50,000-byte defense-in-depth ceiling". The judge found
# nothing in `core/` or `adapters/` ever read the field, so a capped
# `Finding` reached this module indistinguishable from a complete one.
# This is that reader.
def _ok_finding_was_truncated(findings: list[Finding]) -> bool:
    """True when at least one `"ok"` structured-pass-through `Finding` in
    this query's result set was cut, by either of two independent
    truncations that can fire before a `Finding` reaches this module.

    F-2.1-C12: the pre-fix version read only `finding.truncated`, the
    byte-ceiling flag `coordinator_worker._cap_structured_fields` sets.
    It never read `structured_fields["truncated"]`, `cypher_query`'s own
    row-limit flag (`CypherQueryOutput.truncated`, set whenever the
    graph's true match count exceeds `row_limit`), sitting in the same
    dict. Measured: a 15,310-row match capped to 100 rows by the tool's
    own row limit, comfortably under the 50,000-byte ceiling, so the old
    check saw `truncated=False` and emitted no note at all for a result
    the user was shown 100 of 15,310 rows of. Both flags now gate the
    same signal, since either one means the user is not seeing the whole
    answer.

    Scoped to `"ok"` findings only: an `"empty"` or `"error"` finding is
    already refused for its own, unrelated reason, and `truncated` on a
    `"reader"`-sourced finding (`structured_fields is None`) is never
    meaningful, since that path has no `structured_fields` to have cut in
    the first place.
    """
    return any(
        finding.truncated or bool(finding.structured_fields.get("truncated"))
        for finding in findings
        if finding.structured_fields is not None
        and finding.structured_fields.get("status") == "ok"
    )


def _known_total_available(findings: list[Finding]) -> int | None:
    """Sum `total_available` across this query's `"ok"` findings.

    Returns `None` when any contributing finding's own `total_available`
    is unknown (`cypher_query._fetch_true_total` abstained rather than
    guessing, e.g. a UNION or an aliased multi-item `DISTINCT`), since
    summing a known figure with an unknown one is not itself a knowable
    total. A caller reading `None` states scale honestly as "more than
    shown, exact total unavailable" rather than fabricating a number.
    """
    total = 0
    saw_any = False
    for finding in findings:
        fields = finding.structured_fields
        if fields is None or fields.get("status") != "ok":
            continue
        saw_any = True
        available = fields.get("total_available")
        if available is None:
            return None
        total += available
    return total if saw_any else None


def _build_truncated_answer_note(shown: int, total_available: int | None) -> str:
    """F-2.1-C12: state the scale of what is not shown, not just that a
    cut happened. "Results were truncated" said nothing when the user was
    shown 20 of 15,310 rows; a note that omits the scale is technically
    true and practically useless.
    """
    if total_available is not None and total_available > shown:
        return (
            f"Note: this result was truncated. Showing {shown} of "
            f"{total_available} matching rows; the rest are not shown above."
        )
    return (
        f"Note: this result was truncated. Showing {shown} matching rows, "
        "but more exist than are shown above; the exact total is not "
        "available for this query."
    )


_TRUNCATED_REFUSAL_MESSAGE = (
    "The graph query found matching data, but the result was cut to fit "
    "the response size limit before any row kept a citeable source_url. "
    "This is not the same as the graph returning no matching data. Retry "
    "with a narrower query_intent or a smaller row_limit."
)

# F-2.1-J4-06: the general form of the same "never a silent refuse beside
# status='ok'" principle F-2.1-11 established for the truncation case.
# `tool_outcome == "ok"` alongside zero citations can also happen with no
# truncation involved at all, for example every row a query matched
# carried no resolvable `source_url` (an unmapped CURIE prefix). Before
# this fix that case fell through both branches below with no error
# event at all, identical to `tool_outcome == "empty"`'s genuine "the
# graph found nothing" refusal. This message is deliberately distinct
# from `_TRUNCATED_REFUSAL_MESSAGE`: it never claims a cut happened,
# since none did.
_UNCITED_OK_REFUSAL_MESSAGE = (
    "The graph query found matching data, but no returned row carried a "
    "citeable source_url. This is not the same as the graph returning no "
    "matching data."
)

# F-2.1-C07, "matched plenty, cited none". Build phase 2.1 could not tell
# this case from the one above, because it had no grounding pass: a row
# either carried a `source_url` and was cited, or it did not. Build phase
# 2.2 introduces a third way to reach a refusal with `tool_outcome == "ok"`,
# and it is the most important of the three to name precisely, because it is
# the only one where the DATA was fine and the ANSWER was not.
#
# Reached when citable findings were built and handed to Synth, and not one
# clause of what came back survived Section 8.2. The retrieval succeeded.
# The synthesis produced nothing a reader could trace. Collapsing this into
# either message above would tell an operator to go and look at the graph,
# which is the one place the defect is not.
#
# `.claude/rules/tool-call-budgets.md`: an error message is an instruction
# to the next agent step, not just a failure signal, so this one names the
# stage that actually failed and what to do about it.
_UNGROUNDED_SYNTHESIS_REFUSAL_MESSAGE = (
    "The graph query returned citeable data, but no statement in the "
    "generated answer could be matched to it, so the answer was withheld "
    "rather than shown ungrounded. The retrieval succeeded; the synthesis "
    "did not. Retrying may succeed."
)

# T-3.1-13/F-2.1-B10. Deliberately a different sentence from every
# message above, and from "the graph query failed": none of them are
# true here. The graph was never reached at all, so "the graph query
# failed" misattributes the failure to a component that never ran; "I
# could not identify that gene" is the honest, actionable statement, and
# it is the adversary's own required wording (tracker/phase_3.1.md).
_UNRESOLVED_ENTITY_REFUSAL_MESSAGE = (
    "I could not identify that gene. NCBI has no record matching the "
    "name in your question, so no graph query was attempted."
)


def _build_unresolved_entity_refusal_text(attempted_symbols: list[str]) -> str:
    """The user-facing refusal for T-3.1-13, naming what was tried.

    Mirrors `synthesis.refuse.build_refusal_text`'s shape (message, then
    an NCBI fallback link) without importing it: that helper always
    prepends the generic `REFUSE_MESSAGE`, and this refusal needs its own
    distinct wording, per this ticket's acceptance criterion that "I
    could not identify that gene" and "the graph query failed" are
    different messages and only one is true here.
    """
    query_term = " ".join(attempted_symbols) if attempted_symbols else ""
    return f"{_UNRESOLVED_ENTITY_REFUSAL_MESSAGE} {build_fallback_link(query_term)}"


def _response_text(response: Any) -> str:
    """Pull the completion text out of whatever `_dispatch_tier_call` returned.

    `call_tier` returns an `LLMResponse`, but this stays tolerant of a bare
    string and of None on purpose: every existing Write-step test in this
    repo patches the dispatch with a mock whose return value is whatever
    that test needed, and a Write step that raises `AttributeError` on an
    unexpected shape would turn a synthesis defect into a crash. An
    unreadable response yields an empty narrative, which the grounding pass
    then refuses, which is the honest outcome.
    """
    if response is None:
        return ""
    content = getattr(response, "content", response)
    return content if isinstance(content, str) else ""


def _node_or_edge_type_by_citation_id(
    findings: list[Finding], synth_findings: list[SynthFinding]
) -> dict[str, str]:
    """Map each finding's `citation_id` to the graph row type behind it.

    Section 8.3.1 classifies risk on the source field OR the relationship
    type, and `SynthFinding` deliberately carries only the seven Section
    8.1 fields, none of which is the row type. Rather than widen that
    schema (it is the shape handed to a model, and every field in it is a
    field the model can misread), the type is looked up here, on the
    harness side, keyed by the `source_url`/`field`/`field_value` identity
    the finding was built from.

    Without this, `gene_associated_with_condition` edges, the graph's own
    mechanistic gene-to-disease mapping and a Section 8.3.1 high-risk row,
    would classify `low` and answer confidently on a single origin.
    """
    by_identity: dict[tuple[str, str], str] = {}
    for finding in findings:
        fields = finding.structured_fields
        if fields is None or fields.get("status") != "ok":
            continue
        for row in fields.get("rows", []):
            source_url = str(row.get("source_url") or "")
            if not source_url:
                continue
            by_identity[(source_url, str(row.get("curie") or ""))] = str(
                row.get("node_or_edge_type") or ""
            )

    out: dict[str, str] = {}
    for synth_finding in synth_findings:
        for (source_url, curie), row_type in by_identity.items():
            if source_url != synth_finding.source_url:
                continue
            if synth_finding.curie_fallback and curie != synth_finding.field_value:
                continue
            out[synth_finding.citation_id] = row_type
            break
    return out


def _citations_from_grounded_claims(
    grounding: GroundingResult, findings: list[Finding]
) -> list[CitationPayload]:
    """Build one `CitationPayload` per surviving grounded claim.

    This replaces build phase 2.1's `_citations_from_findings` on the live
    path, and the difference is the whole point of this phase: 2.1 emitted
    a citation for every row that carried a `source_url`, whether or not
    the answer said anything about it. That is how the flagship question
    shipped twenty-five chips over an answer to a different question, each
    one resolving perfectly.

    A citation now exists only where a claim survived Section 8.2, so a
    chip is evidence that a specific sentence was checked against a
    specific field value, not that a row was fetched. `claim_text` is the
    surviving clause itself rather than a machine-built
    `"{type} {curie}: {field}={value}"` string, which is what makes the
    citation legible to a reader and checkable by the premise gate.

    `_citations_from_findings` is deliberately left in place: it is the
    reader for the truncation and cap accounting, and several 2.1 tests
    assert on it directly.
    """
    display_slots = display_index_by_citation_id(grounding)
    suspect_by_citation_id = {
        claim.finding.citation_id: claim.finding.value_is_suspect
        for claim in grounding.claims
    }
    claim_text_by_citation_id: dict[str, str] = {}
    finding_by_citation_id: dict[str, SynthFinding] = {}
    for claim in grounding.claims:
        citation_id = claim.finding.citation_id
        finding_by_citation_id.setdefault(citation_id, claim.finding)
        # A finding cited by two clauses keeps the first clause as its
        # claim_text; both clauses were independently grounded against the
        # same field value, so either is true, and picking deterministically
        # beats concatenating into a claim no single sentence made.
        claim_text_by_citation_id.setdefault(citation_id, claim.claim_text)

    citations: list[CitationPayload] = []
    for citation_id, display_index in sorted(display_slots.items(), key=lambda kv: kv[1]):
        synth_finding = finding_by_citation_id[citation_id]
        curie = (
            synth_finding.field_value
            if synth_finding.curie_fallback
            else _curie_for_citation(citation_id, findings, synth_finding)
        )
        prefix = curie.split(":", 1)[0] if ":" in curie else synth_finding.tool
        citations.append(
            CitationPayload(
                citation_id=citation_id,
                display_index=display_index,
                source=(prefix or synth_finding.tool)[:128],
                source_id=(curie or "unknown")[:128],
                source_url=synth_finding.source_url,
                layer=synth_finding.layer,  # type: ignore[arg-type]
                field=synth_finding.field[:128],
                claim_text=claim_text_by_citation_id[citation_id][:1000],
                # Section 9.2's per-tool static defaults for a cypher_query
                # graph property: a value copied from an NCBI-native record,
                # which is a US federal government work.
                evidence_kind="primary_assertion",
                # F-2.1-B07's hedge, preserved. A row whose representative
                # value was a vocabulary-token artifact is cited on its
                # CURIE now rather than on the artifact, but the record
                # itself is still known to carry a corrupted field, so the
                # confidence downgrade still applies.
                assertion_confidence="hedged" if suspect_by_citation_id[citation_id] else "asserted",
                # No Layer 1 graph row carries a population or ancestry
                # field. Section 9.2: null is a normal, honest state here,
                # never inferred or guessed.
                population_ancestry_context=None,
                license="public_domain_us_gov",
            )
        )
    return citations


def _curie_for_citation(
    citation_id: str, findings: list[Finding], synth_finding: SynthFinding
) -> str:
    """Recover the CURIE of the row a non-fallback finding was built from.

    A finding whose citable value is a real field (a gene name, a count)
    does not carry its own CURIE, but `source_id` on the citation must be
    the record identifier, not the field value. Looked up by `source_url`,
    which is derived from the CURIE and is therefore unique per record.
    """
    for finding in findings:
        fields = finding.structured_fields
        if fields is None or fields.get("status") != "ok":
            continue
        for row in fields.get("rows", []):
            if str(row.get("source_url") or "") == synth_finding.source_url:
                return str(row.get("curie") or "")
    return ""


# One `token` event per sentence rather than per answer. Section 6 of
# `system-design-patterns` requires time-to-first-token under a second and
# citation chips emitted inline as the model references sources; a single
# token event carrying the whole answer satisfies neither. Real per-token
# streaming out of the model call is build phase 4.0's, and this is the
# sentence-granular step toward it that does not require restructuring the
# harness call.
def _narrative_chunks(
    grounding: GroundingResult, citations: list[CitationPayload]
) -> list[tuple[str, list[str]]]:
    """Split the grounded narrative into `(text, marker_ids)` token chunks.

    `marker_ids` carries `citation_id` values, never display numbers
    (Section 9.4: the wire-level marker is the stable opaque key, and
    `display_index` is only what a surface prints). A surface binds a token
    to its citation by that key, then looks up the number.
    """
    if not grounding.narrative.strip():
        return []
    citation_id_by_display = {c.display_index: c.citation_id for c in citations}
    chunks: list[tuple[str, list[str]]] = []
    for sentence in re.split(r"(?<=[.;?!])\s+", grounding.narrative.strip()):
        if not sentence.strip():
            continue
        marker_ids = [
            citation_id_by_display[int(number)]
            for number in re.findall(r"\[(\d{1,3})\]", sentence)
            if int(number) in citation_id_by_display
        ]
        text = sentence if sentence.endswith(" ") else sentence + " "
        chunks.append((text[:1000], marker_ids[:20]))
    return chunks


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

    unresolved_entity_symbols = state.get("unresolved_entity_symbols")
    if unresolved_entity_symbols:
        # T-3.1-13/F-2.1-B10: `plan_node` already determined this query's
        # only candidate entity does not resolve, before act_node ever
        # dispatched a tool call. Ship the refusal here, before the synth
        # call, the same early-exit shape `step_error` and `cap_exceeded`
        # already use: there is nothing for Synth to honestly write about
        # a query that was never sent to the graph.
        sink.emit(
            "token",
            TokenPayload(
                text=_build_unresolved_entity_refusal_text(unresolved_entity_symbols)[:1000],
                marker_ids=[],
            ),
        )
        sink.emit(
            "trust_signal",
            TrustSignalPayload(
                outcome="refuse",
                risk_tier="low",
                grounded=False,
                triangulated=None,
                scope="answer",
                message=_UNRESOLVED_ENTITY_REFUSAL_MESSAGE,
                fallback_link=build_fallback_link(" ".join(unresolved_entity_symbols)),
            ),
        )
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

    query_class: QueryClass = state.get("query_class", "lookup")

    # Section 8.1: the findings list is code-built before the model is ever
    # called, and it is the only thing Synth can draw a fact from. Built
    # here, before the call, so a zero-finding query never spends a synth
    # call at all: there is nothing it could honestly write.
    # `max_findings` is the citation cap, deliberately, not the findings
    # module's own larger default. A citation exists only where a claim
    # grounded against a finding, so the number of findings handed to Synth
    # is an upper bound on the number of citations that can be emitted, and
    # setting the two to different values would let the citation cap be
    # exceeded by construction. Build phase 2.1's cap is not weakened by
    # this phase's rewrite of how citations are built.
    synth_findings, findings_capped = build_synth_findings(
        findings, _pick_representative_field, max_findings=_MAX_CITATIONS_PER_ANSWER
    )
    row_types = _node_or_edge_type_by_citation_id(findings, synth_findings)

    try:
        synth_text = await _dispatch_tier_call(
            harness,
            trace_id,
            "synth",
            "write",
            build_synth_messages(query.text, synth_findings),
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

    # A5/F-02 (build phase 2.1) established that the terminal
    # trust_outcome must reflect what Act actually found. Build phase 2.2
    # replaces the row-count proxy that stood in for grounding with the
    # real thing: Section 8.2 runs over the narrative Synth just wrote,
    # and the outcome comes from Section 8.3's decision table over what
    # survived, not from whether any row happened to carry a source_url.
    tool_outcome = _tool_execution_outcome(findings)

    grounding = run_grounding_pass(
        _response_text(synth_text),
        synth_findings,
        core_ask_required=True,
        question=query.text,
    )

    if tool_outcome == "no_tool":
        # No tool was selected at all, so there is nothing to ground
        # against and nothing to refuse about. Preserved from 2.1
        # unchanged; build phase 3.0's Guardrail owns the queries that
        # legitimately reach Write with no tool call.
        citations = []
        claim_trusts: list[ClaimTrust] = []
        trust_outcome: TrustOutcome = "answer"
    else:
        claim_trusts = trust_for_claims(grounding.claims, synth_findings, row_types)
        citations = _citations_from_grounded_claims(grounding, findings)
        trust_outcome = aggregate([trust.outcome for trust in claim_trusts])

    # `citations_capped` keeps its 2.1 meaning: the user is being shown
    # fewer facts than exist. Its two sources are now the findings cap
    # (more citable rows than one prompt may carry) and the citation cap.
    citations_capped = findings_capped or len(citations) >= _MAX_CITATIONS_PER_ANSWER

    # F-2.1-10/F-2.1-11/F-2.1-C12 fix: a result the user is shown only part
    # of must never look identical to one they are shown in full.
    # `_ok_finding_was_truncated` is the reader `Finding.truncated` and
    # `structured_fields["truncated"]` were both missing (F-2.1-10,
    # F-2.1-C12: the byte ceiling and the tool's own row-limit cap are two
    # independent truncations, and the pre-fix code read only the first).
    # `citations_capped` is the third: `_MAX_CITATIONS_PER_ANSWER` cutting
    # an already-fetched row list down further still. Any one of the three
    # means the user is not seeing the whole answer. Two cases:
    #   - The cut still left a citeable row: the query genuinely succeeded
    #     (trust_outcome is already "answer" above) and cite-or-refuse is
    #     not weakened, but the cut is acknowledged rather than silently
    #     dropped, so a user is never shown a partial result as if it were
    #     complete. The note states the scale (shown vs. total_available),
    #     not just that a cut happened.
    #   - The cut left nothing citeable: cite-or-refuse still refuses (a
    #     truncated Finding earns no exemption from that gate), but the
    #     refusal names the real cause, so it is never confused with the
    #     graph genuinely returning no matching data (F-2.1-11's exact
    #     failure mode: both cases used to reach an identical, silent
    #     "refuse").
    #
    # Build phase 2.2 changes one thing here: the note is no longer emitted
    # at this point in the function. There is a real narrative now, and a
    # "showing 20 of 15,310" note that arrives BEFORE the prose it
    # qualifies reads as a header rather than as a caveat on what follows.
    # It is held in `truncation_note` and emitted after the narrative
    # chunks below. The two `error` branches are unchanged and stay here:
    # they fire on refusals, where there is no narrative to sequence
    # against.
    #
    # The `answer` test also widens to "anything that is not a refusal".
    # Section 8.3.3 added `flag` and `ask` to the reachable outcomes this
    # phase, and a flagged or ask-tiered answer is still an answer the user
    # is being shown part of; leaving the test at `== "answer"` would have
    # silently dropped the note on exactly the higher-stakes answers that
    # most need it.
    truncated_ok_finding = tool_outcome == "ok" and (
        _ok_finding_was_truncated(findings) or citations_capped
    )
    truncation_note: str | None = None
    if truncated_ok_finding and trust_outcome != "refuse":
        truncation_note = _build_truncated_answer_note(
            shown=len(citations), total_available=_known_total_available(findings)
        )
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
    elif tool_outcome == "ok" and trust_outcome == "refuse":
        # F-2.1-J4-06: a status="ok" tool result that still refuses must
        # not look identical to a genuinely empty tool result. F-2.1-C07
        # splits this branch in two, because build phase 2.2 makes the two
        # causes genuinely different things an operator would act on
        # differently. `synth_findings` is the discriminator, and it is the
        # right one: it is non-empty exactly when at least one row was
        # citeable, so an empty list means the rows were uncitable and a
        # non-empty list means the rows were fine and the answer was not.
        ungrounded_synthesis = bool(synth_findings)
        sink.emit(
            "error",
            ErrorPayload(
                fatal=False,
                scope="step" if ungrounded_synthesis else "tool",
                source="write" if ungrounded_synthesis else "cypher_query",
                error_class="recoverable",
                message=(
                    _UNGROUNDED_SYNTHESIS_REFUSAL_MESSAGE
                    if ungrounded_synthesis
                    else _UNCITED_OK_REFUSAL_MESSAGE
                ),
                retry_after_s=0,
            ),
        )

    # Section 8: the answer itself. Order matters to a consuming surface
    # and is fixed here: the narrative first (so a reader sees prose as
    # soon as it exists), then the citations the markers in it resolve
    # against, then the per-claim trust verdicts joined to those
    # citations by `citation_id`, then the answer-level verdict.
    if trust_outcome == "refuse":
        # Section 8.4. A refusal is a content-safety outcome, not a
        # failure, and it always carries somewhere to go next.
        #
        # Step 2 offers two sources for `query_term`, the raw query text or
        # the resolved entity string, and the choice is not cosmetic. The
        # raw text is echoed back to the user inside a link, so a question
        # carrying an injected instruction gets that instruction
        # percent-encoded into a URL the UI renders. The premise gate
        # caught exactly that: a refusal whose fallback link contained
        # "...causes%20Marfan%20syndrome...". Nothing is executed and
        # nothing is asserted, but reflecting attacker-supplied text into a
        # user-visible link is a gap worth not having, and the resolved
        # entity is the better search term anyway.
        #
        # Falls back to the raw text only when nothing resolved, since a
        # link built from an empty term is a link to nothing.
        #
        # T-3.1-13 decision: reuse plan_node's own resolution rather than
        # re-resolving here. Before T-3.1-11 this was a free, deterministic
        # re-computation; now `_extract_target_entities` is a live NCBI
        # call, and every branch that reaches this line already ran
        # plan_node (`cap_exceeded` and `step_error` both return earlier,
        # above, before this point, and `unresolved_entity_symbols` also
        # returns earlier), so `state["tool_calls"]` already carries the
        # `CypherQueryInput.target_entities` plan_node resolved via
        # `resolve_entity_curies`. Re-resolving here would spend a second
        # live lookup and its latency purely to build a fallback link for
        # a refusal already decided by other means.
        planned_tool_calls: list[_PlannedToolCall] = state.get("tool_calls", [])
        resolved = (
            planned_tool_calls[0].cypher_input.target_entities
            if planned_tool_calls
            else []
        )
        query_term = " ".join(resolved) if resolved else query.text
        fallback_link = build_fallback_link(query_term)
        sink.emit(
            "token",
            TokenPayload(text=build_refusal_text(query_term)[:1000], marker_ids=[]),
        )
        sink.emit(
            "trust_signal",
            TrustSignalPayload(
                outcome="refuse",
                risk_tier="low",
                grounded=False,
                triangulated=None,
                scope="answer",
                message=REFUSE_MESSAGE,
                fallback_link=fallback_link,
            ),
        )
    else:
        for chunk, marker_ids in _narrative_chunks(grounding, citations):
            sink.emit("token", TokenPayload(text=chunk, marker_ids=marker_ids))

        if truncation_note is not None:
            sink.emit("token", TokenPayload(text=truncation_note, marker_ids=[]))

        for citation in citations:
            sink.emit("citation", citation)

        for trust in claim_trusts:
            sink.emit(
                "trust_signal",
                TrustSignalPayload(
                    outcome=trust.outcome,
                    risk_tier=trust.risk_tier,
                    grounded=trust.grounded,
                    triangulated=trust.triangulated,
                    citation_id=trust.citation_id,
                    scope="claim",
                ),
            )
        if claim_trusts:
            sink.emit(
                "trust_signal",
                TrustSignalPayload(
                    outcome=trust_outcome,
                    risk_tier=(
                        "high"
                        if any(t.risk_tier == "high" for t in claim_trusts)
                        else "low"
                    ),
                    grounded=True,
                    triangulated=None,
                    scope="answer",
                ),
            )

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
    # T-3.0-06. A Section 10 refusal terminates the run exactly as a daily-cap
    # decline does: straight to END, past `write`. Section 10.1 requires that a
    # query failing any step "never reaches Think, Plan, or Act", and routing a
    # refusal through `write` would hand the synthesis step a query the
    # guardrail already rejected.
    #
    # Checked before the cap and step-error branches, not after. A query can be
    # both refused and carrying a step error (the classifier's own call can
    # fail on a later retry path), and a refusal is the stronger, more specific
    # outcome: it is a decision about the query, where a step error is a
    # statement about the machinery.
    if state.get("guard_refused", False) or state.get("daily_cap_declined", False):
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
