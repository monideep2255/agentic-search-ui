/**
 * 2026-09-05 product-owner decision: a no-data refusal (an entity did not
 * resolve, synthesis was ungrounded, or a truncated result left nothing
 * citeable) must render identically to a guardrail refusal, through the
 * same `refusal` notice, never as a claim on the provenance spine.
 *
 * LEVEL CHOSEN: this test feeds a raw `AgentEvent[]` fixture straight into
 * `useRunView`, the same shape the SSE stream actually delivers, rather
 * than rendering `AnswerScreen` with a hand-built `refusal` prop. The
 * defect this fix closes is upstream of any component: `write_node`
 * (`core/graph.py`) emits the refusal sentence as an ordinary `token`
 * event, and the bug was in how `useRunView` CLASSIFIED that token, not in
 * how a component painted a `refusal` string once handed one. A
 * component-level test with a hand-made `refusal` prop would pass against
 * the broken hook, since it never exercises the classification step at
 * all. Testing `useRunView` directly is the one level that can actually
 * fail on the original defect, and the mutation proof below confirms it
 * does.
 *
 * Fixture text is taken from the real backend constants rather than
 * invented, per this ticket's instruction to cite rather than guess:
 * `synthesis/refuse.py`'s `REFUSE_MESSAGE` and `FALLBACK_BASE`, and
 * `core/graph.py`'s `_UNRESOLVED_ENTITY_REFUSAL_MESSAGE`.
 */

import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AgentEvent } from "../lib/events";
import { useRunView } from "./useRunView";

let seq = 0;

/** One event envelope, matching the wire shape `useAgentRun.test.ts` uses. */
function envelope<TType extends AgentEvent["type"]>(
  type: TType,
  payload: Extract<AgentEvent, { type: TType }>["payload"],
): AgentEvent {
  seq += 1;
  return {
    type,
    version: "v1",
    trace_id: "trace-1",
    seq,
    ts: `2026-09-05T12:00:0${seq}Z`,
    payload,
  } as AgentEvent;
}

// `synthesis/refuse.py`'s `REFUSE_MESSAGE` and `FALLBACK_BASE`, and the
// `build_fallback_link` construction: base plus the URL-encoded term.
const REFUSE_MESSAGE =
  "I could not find grounded evidence for this. Try NCBI's cross-database " +
  "search:";
const FALLBACK_LINK = "https://www.ncbi.nlm.nih.gov/search/all/?term=BRCA9";
const REFUSAL_TOKEN_TEXT = `${REFUSE_MESSAGE} ${FALLBACK_LINK}`;

describe("useRunView: no-data refusal", () => {
  it("routes an ungrounded-synthesis refusal into `refusal`, never into `claims`", () => {
    const events: AgentEvent[] = [
      envelope("guard", { passed: true, category: "ok", reason: null }),
      envelope("think", {
        narrative: "",
        query_class: "lookup",
        resolved_entities: [],
        clarifying_question: null,
      }),
      envelope("plan", { narrative: "", tool_calls: [] }),
      envelope("tool_start", {
        call_id: "c1",
        tool: "cypher_query",
        layer: "layer_1_graph",
        status: "running",
      }),
      envelope("tool_result", {
        call_id: "c1",
        tool: "cypher_query",
        layer: "layer_1_graph",
        status: "ok",
        summary: "",
        result_count: 3,
        truncated: false,
      }),
      // The exact shape `write_node`'s general refuse branch emits: the
      // refusal sentence as a bare token, no marker_ids, because there is
      // no citation to bind it to.
      envelope("token", { text: REFUSAL_TOKEN_TEXT, marker_ids: [] }),
      // The structured Section 8.4 refuse payload, emitted alongside the
      // token above at the same call site (`core/graph.py`'s
      // `sink.emit("trust_signal", TrustSignalPayload(outcome="refuse",
      // ... scope="answer", message=REFUSE_MESSAGE,
      // fallback_link=fallback_link))`).
      envelope("trust_signal", {
        outcome: "refuse",
        risk_tier: "unknown",
        grounded: false,
        triangulated: null,
        scope: "answer",
        message: REFUSE_MESSAGE,
        fallback_link: FALLBACK_LINK,
      }),
      envelope("done", {
        total_cost_usd: 0.01,
        total_tool_calls: 1,
        elapsed_ms: 800,
        trust_outcome: "refuse",
      }),
    ];

    const { result } = renderHook(() => useRunView(events));
    const view = result.current;

    // The whole point: no claim, uncited or otherwise, exists on the spine.
    expect(view.claims).toHaveLength(0);
    expect(view.systemNotes).toHaveLength(0);

    // The refusal renders through the same channel a guardrail refusal
    // uses, built from the trust_signal's own fields.
    expect(view.refusal).toBe(REFUSAL_TOKEN_TEXT);
    // The NCBI fallback link must survive and stay usable inside it.
    expect(view.refusal).toContain(FALLBACK_LINK);
  });

  it("routes an unresolved-entity refusal into `refusal`, never into `claims`", () => {
    const message =
      "I could not identify that gene. NCBI has no record matching the " +
      "name in your question, so no graph query was attempted.";
    const link = "https://www.ncbi.nlm.nih.gov/search/all/?term=NOTAGENE";
    const tokenText = `${message} ${link}`;

    const events: AgentEvent[] = [
      envelope("guard", { passed: true, category: "ok", reason: null }),
      envelope("think", {
        narrative: "",
        query_class: "lookup",
        resolved_entities: [],
        clarifying_question: null,
      }),
      envelope("plan", { narrative: "", tool_calls: [] }),
      // T-3.1-13's early exit: no tool_start, no tool_result. `act_node`
      // never ran because the only candidate entity did not resolve.
      envelope("token", { text: tokenText, marker_ids: [] }),
      envelope("trust_signal", {
        outcome: "refuse",
        risk_tier: "unknown",
        grounded: false,
        triangulated: null,
        scope: "answer",
        message,
        fallback_link: link,
      }),
      envelope("done", {
        total_cost_usd: 0.0,
        total_tool_calls: 0,
        elapsed_ms: 300,
        trust_outcome: "refuse",
      }),
    ];

    const { result } = renderHook(() => useRunView(events));
    const view = result.current;

    expect(view.claims).toHaveLength(0);
    expect(view.refusal).toBe(tokenText);
    expect(view.refusal).toContain(link);
  });

  it("leaves a genuinely grounded, cited answer untouched (no false positive)", () => {
    const events: AgentEvent[] = [
      envelope("guard", { passed: true, category: "ok", reason: null }),
      envelope("think", {
        narrative: "",
        query_class: "lookup",
        resolved_entities: [],
        clarifying_question: null,
      }),
      envelope("plan", { narrative: "", tool_calls: [] }),
      envelope("tool_result", {
        call_id: "c1",
        tool: "cypher_query",
        layer: "layer_1_graph",
        status: "ok",
        summary: "",
        result_count: 1,
        truncated: false,
      }),
      envelope("token", {
        text: "BRCA1 is associated with hereditary breast cancer [1].",
        marker_ids: ["cid-1"],
      }),
      envelope("citation", {
        citation_id: "cid-1",
        display_index: 1,
        source: "NCBIGene",
        source_id: "672",
        source_url: "https://www.ncbi.nlm.nih.gov/gene/672",
        layer: "layer_1_graph",
        field: "cypher_query",
        claim_text: "BRCA1 is associated with hereditary breast cancer",
        evidence_kind: "curated_assertion",
        assertion_confidence: "high",
        population_ancestry_context: null,
        license: "public_domain_us_gov",
      }),
      // The claim-scope AND answer-scope trust_signal a real grounded
      // answer emits. Neither has `outcome === "refuse"`, so the new
      // `answerRefusalSignal` check must not fire on either of them.
      envelope("trust_signal", {
        outcome: "answer",
        risk_tier: "low",
        grounded: true,
        triangulated: null,
        scope: "claim",
      }),
      envelope("trust_signal", {
        outcome: "answer",
        risk_tier: "low",
        grounded: true,
        triangulated: null,
        scope: "answer",
      }),
      envelope("done", {
        total_cost_usd: 0.02,
        total_tool_calls: 1,
        elapsed_ms: 900,
        trust_outcome: "answer",
      }),
    ];

    const { result } = renderHook(() => useRunView(events));
    const view = result.current;

    expect(view.refusal).toBeNull();
    expect(view.claims).toHaveLength(1);
    expect(view.claims[0]?.text).toContain("BRCA1 is associated");
  });

  it("still classifies a guardrail refusal from CATEGORY_COPY, unaffected by the new signal", () => {
    const events: AgentEvent[] = [
      envelope("guard", {
        passed: false,
        category: "off_topic",
        reason: "asked about a recipe",
      }),
      envelope("done", {
        total_cost_usd: 0.0,
        total_tool_calls: 0,
        elapsed_ms: 50,
        trust_outcome: "refuse",
      }),
    ];

    const { result } = renderHook(() => useRunView(events));
    const view = result.current;

    expect(view.claims).toHaveLength(0);
    expect(view.refusal).toBe(
      "This looks outside biomedical research. I can help with a gene, variant, pathogen, or paper question.",
    );
  });

  it("classifies the repair-cap note as a system note, not a claim (F-2.1... sibling defect)", () => {
    const events: AgentEvent[] = [
      envelope("guard", { passed: true, category: "ok", reason: null }),
      envelope("tool_result", {
        call_id: "c1",
        tool: "cypher_query",
        layer: "layer_1_graph",
        status: "ok",
        summary: "",
        result_count: 1,
        truncated: false,
      }),
      envelope("token", {
        text: "BRCA1 is associated with hereditary breast cancer [1].",
        marker_ids: ["cid-1"],
      }),
      envelope("citation", {
        citation_id: "cid-1",
        display_index: 1,
        source: "NCBIGene",
        source_id: "672",
        source_url: "https://www.ncbi.nlm.nih.gov/gene/672",
        layer: "layer_1_graph",
        field: "cypher_query",
        claim_text: "BRCA1 is associated with hereditary breast cancer",
        evidence_kind: "curated_assertion",
        assertion_confidence: "high",
        population_ancestry_context: null,
        license: "public_domain_us_gov",
      }),
      // `_build_repair_cap_note`'s exact opening, `core/graph.py`.
      envelope("token", {
        text:
          "Note: this answer's completeness check could not run to the end " +
          "because the query reached its cost limit, so the omission " +
          "described above was not repaired",
        marker_ids: [],
      }),
      envelope("done", {
        total_cost_usd: 0.03,
        total_tool_calls: 1,
        elapsed_ms: 950,
        trust_outcome: "answer",
      }),
    ];

    const { result } = renderHook(() => useRunView(events));
    const view = result.current;

    expect(view.claims).toHaveLength(1);
    expect(view.systemNotes).toHaveLength(1);
    expect(view.systemNotes[0]).toContain("completeness check could not run to the end");
  });
});
