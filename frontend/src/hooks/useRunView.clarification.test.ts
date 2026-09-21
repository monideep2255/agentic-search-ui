/**
 * UI fix set 7 item 7.5: the agent asks back instead of refusing blankly.
 *
 * The product owner on 2026-09-13, retesting fix set 7 on develop: "the
 * follow up must retain context or ask clarification if the question is not
 * clear. Because if this is a discussion, it must flow."
 *
 * `clarifying_question` has been a nullable string on `ThinkPayload` since
 * the event contract was written, validated by `isThinkPayload`, and read by
 * NOTHING. A run that could not tell which reading of a question was meant
 * asked its question into the void and then refused as though it had nothing
 * to say. These arms are where that field starts mattering.
 *
 * LEVEL CHOSEN, the same reasoning `useRunView.refusal.test.ts` states for
 * its own level: the classification lives in the hook, so a component test
 * handed a hand-built `refusalLabel` prop would pass against a hook that
 * never reads the field at all. The fixtures below are raw `AgentEvent[]`,
 * the shape the SSE stream actually delivers.
 *
 * COVERAGE STATEMENT, per `goal-contracts`:
 *
 *   Exercised     that a non-empty `clarifying_question` becomes the
 *                 refusal's text and gets the clarification LABEL rather
 *                 than the generic dead-end one, including on a run that
 *                 also carries the generic answer-level refusal signal,
 *                 which is the shape the backend actually emits; that
 *                 `null`, `""` and whitespace all behave identically to
 *                 absent; that a grounded answer carrying no clarification
 *                 is untouched; and that a failed guardrail still wins.
 *
 *   NOT exercised what the refusal LOOKS like, and whether the follow-up
 *                 field takes focus. Both are the component's, and live in
 *                 `AnswerScreen.previousTurnBody.test.tsx`.
 */

import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AgentEvent } from "../lib/events";
import { ANSWER_REFUSAL_LABEL, CLARIFICATION_LABEL, useRunView } from "./useRunView";

let seq = 0;

/** One event envelope, matching the wire shape the other hook tests use. */
function envelope<TType extends AgentEvent["type"]>(
  type: TType,
  payload: Extract<AgentEvent, { type: TType }>["payload"],
): AgentEvent {
  seq += 1;
  return {
    type,
    version: "v1",
    trace_id: "trace-clarify",
    seq,
    ts: `2026-09-13T12:00:0${seq % 10}Z`,
    payload,
  } as AgentEvent;
}

const QUESTION = "Do you mean the human BRCA1 gene, or the mouse Brca1 gene?";

/** `synthesis/refuse.py`'s `REFUSE_MESSAGE`, the generic refusal sentence. */
const GENERIC_REFUSAL =
  "I could not find grounded evidence for this. Try NCBI's cross-database search:";
const FALLBACK_LINK = "https://www.ncbi.nlm.nih.gov/search/all/?term=BRCA1";

/**
 * The run the backend actually emits for a clarification: the question on
 * the `think` payload, and the refusal path's own `trust_signal` plus
 * `done{trust_outcome:"refuse"}` underneath it. Both halves are present on
 * purpose, because "prefer the clarification when both are there" is the
 * property, and a fixture carrying only the think event could not state it.
 */
function clarifyingRun(clarifying: string | null): AgentEvent[] {
  return [
    envelope("guard", { passed: true, category: "ok", reason: null }),
    envelope("think", {
      narrative: "Two species share this symbol.",
      query_class: "lookup",
      resolved_entities: [],
      clarifying_question: clarifying,
    }),
    envelope("plan", { narrative: "", tool_calls: [] }),
    envelope("token", { text: `${GENERIC_REFUSAL} ${FALLBACK_LINK}`, marker_ids: [] }),
    envelope("trust_signal", {
      outcome: "refuse",
      risk_tier: "unknown",
      grounded: false,
      triangulated: null,
      scope: "answer",
      message: GENERIC_REFUSAL,
      fallback_link: FALLBACK_LINK,
    }),
    envelope("done", {
      total_cost_usd: 0.01,
      total_tool_calls: 0,
      elapsed_ms: 900,
      trust_outcome: "refuse",
    }),
  ];
}

const viewFor = (events: AgentEvent[]) =>
  renderHook(() => useRunView(events)).result.current;

describe("useRunView: a clarification the agent asked for", () => {
  it("shows the agent's question under the clarification label", () => {
    const view = viewFor(clarifyingRun(QUESTION));

    // POPULATE-CHECK. Without it an arm whose fixture stopped producing a
    // refusal at all would read as "the label is not the generic one",
    // which is true of null and proves nothing.
    expect(view.landed).toBe(true);
    expect(view.refusal).not.toBeNull();

    expect(view.clarification).toBe(QUESTION);
    expect(view.refusal).toBe(QUESTION);
    expect(view.refusalLabel).toBe(CLARIFICATION_LABEL);
    expect(view.refusalLabel).toBe("One more detail needed");

    // THE PREFERENCE, stated directly. This run carries the generic
    // answer-level refusal too, and before this change that sentence and
    // that label were what a reader got: "No answer found in NCBI records"
    // above a question they could have answered in one word.
    expect(view.refusalLabel).not.toBe(ANSWER_REFUSAL_LABEL);
    expect(view.refusal).not.toBe(GENERIC_REFUSAL);

    // A clarification is a refusal, so the trust strip and the outcome word
    // stay silent, exactly as R13 requires of every other refusal shape.
    expect(view.trust).toHaveLength(0);
    expect(view.outcome).toBeNull();
  });

  /*
   * THE OTHER HALF, and it is the half that catches a hook which simply
   * hardcoded the clarification label. Absent, empty and whitespace must
   * all reach the generic refusal, or a backend sending `""` would put a
   * blank question under "One more detail needed".
   */
  for (const [name, value] of [
    ["null", null],
    ["an empty string", ""],
    ["whitespace", "   \n "],
  ] as const) {
    it(`falls back to the generic refusal when the question is ${name}`, () => {
      const view = viewFor(clarifyingRun(value));

      expect(view.clarification).toBeNull();
      expect(view.refusal).toBe(GENERIC_REFUSAL);
      expect(view.refusalLabel).toBe(ANSWER_REFUSAL_LABEL);
      expect(view.refusalLink).toBe(FALLBACK_LINK);
    });
  }

  it("leaves a grounded answer alone", () => {
    const events: AgentEvent[] = [
      envelope("guard", { passed: true, category: "ok", reason: null }),
      envelope("think", {
        narrative: "",
        query_class: "lookup",
        resolved_entities: [],
        clarifying_question: null,
      }),
      envelope("plan", { narrative: "", tool_calls: [] }),
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
      envelope("trust_signal", {
        outcome: "answer",
        risk_tier: "low",
        grounded: true,
        triangulated: null,
        scope: "answer",
      }),
      envelope("done", {
        total_cost_usd: 0.01,
        total_tool_calls: 1,
        elapsed_ms: 700,
        trust_outcome: "answer",
      }),
    ];

    const view = viewFor(events);
    // POPULATE-CHECK: this really is an answered run, so "no clarification"
    // below is a statement about a working path rather than about an empty
    // fixture.
    expect(view.claims).toHaveLength(1);
    expect(view.clarification).toBeNull();
    expect(view.refusal).toBeNull();
    expect(view.refusalLabel).toBeNull();
  });

  it("lets a failed guardrail win over a clarification", () => {
    const events: AgentEvent[] = [
      envelope("guard", { passed: false, category: "off_topic", reason: "not biomedical" }),
      // A guardrail refusal never reaches Think, so this event is
      // impossible in production. It is here precisely because the
      // precedence must not depend on that: a stray or replayed think
      // payload must not talk the guardrail's reviewed copy off the screen.
      envelope("think", {
        narrative: "",
        query_class: "lookup",
        resolved_entities: [],
        clarifying_question: QUESTION,
      }),
      envelope("done", {
        total_cost_usd: 0.0,
        total_tool_calls: 0,
        elapsed_ms: 120,
        trust_outcome: "refuse",
      }),
    ];

    const view = viewFor(events);
    expect(view.clarification).toBe(QUESTION);
    expect(view.refusalLabel).toBe("Outside biomedical research");
    expect(view.refusal).not.toBe(QUESTION);
  });
});
