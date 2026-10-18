/**
 * UI fix plan item 12.3: the four ready-made questions a bare-topic
 * clarification ("reflux disease", "GERD") carries alongside its question.
 *
 * `clarifying_options` is optional and nullable on `ThinkPayload`, exactly
 * like `clarifying_question` was described in `useRunView.clarification
 * .test.ts` before item 7.5 started reading it, so this file follows that
 * one's own shape: fixtures are raw `AgentEvent[]`, the wire shape the SSE
 * stream actually delivers, because the derivation lives in the hook.
 *
 * COVERAGE STATEMENT, per `goal-contracts`:
 *
 *   Exercised     that four options on the `think` payload become
 *                 `view.clarificationOptions`, in order; that absent and
 *                 null both resolve to an empty array, matching every run
 *                 before this field existed (including item 7.5's own
 *                 clarification, which never sets it); and that the
 *                 options are read from the SAME `think` event
 *                 `clarification` itself reads, never a separate search.
 *
 *   NOT exercised what the options look like on screen or that clicking
 *                 one asks it (`FollowUp.clarifyingOptions.test.tsx` owns
 *                 both).
 */

import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AgentEvent } from "../lib/events";
import { useRunView } from "./useRunView";

let seq = 0;

function envelope<TType extends AgentEvent["type"]>(
  type: TType,
  payload: Extract<AgentEvent, { type: TType }>["payload"],
): AgentEvent {
  seq += 1;
  return {
    type,
    version: "v1",
    trace_id: "trace-clarify-options",
    seq,
    ts: `2026-09-23T12:00:0${seq % 10}Z`,
    payload,
  } as AgentEvent;
}

const QUESTION = "What would you like to know about reflux disease?";
const OPTIONS = [
  "What is reflux disease and what are its symptoms?",
  "Which genes or variants are linked to reflux disease?",
  "Are there clinical trials for reflux disease?",
  "What does recent research say about reflux disease?",
];

function bareTopicRun(clarifyingOptions: string[] | null | undefined): AgentEvent[] {
  const thinkPayload: Record<string, unknown> = {
    narrative: "the question is a bare topic of three words or fewer",
    query_class: "lookup",
    resolved_entities: [],
    clarifying_question: QUESTION,
  };
  if (clarifyingOptions !== undefined) {
    thinkPayload.clarifying_options = clarifyingOptions;
  }
  return [
    envelope("guard", { passed: true, category: "ok", reason: null }),
    envelope("think", thinkPayload as never),
    envelope("plan", { narrative: "", tool_calls: [] }),
    envelope("token", { text: QUESTION, marker_ids: [] }),
    envelope("trust_signal", {
      outcome: "refuse",
      risk_tier: "unknown",
      grounded: false,
      triangulated: null,
      scope: "answer",
      message: QUESTION,
      fallback_link: "https://www.ncbi.nlm.nih.gov/search/all/?term=reflux+disease",
    }),
    envelope("done", {
      total_cost_usd: 0.0,
      total_tool_calls: 0,
      elapsed_ms: 5,
      trust_outcome: "refuse",
    }),
  ];
}

const viewFor = (events: AgentEvent[]) => renderHook(() => useRunView(events)).result.current;

describe("useRunView: the bare-topic clarification's four options", () => {
  it("carries all four options, in order", () => {
    const view = viewFor(bareTopicRun(OPTIONS));

    // POPULATE-CHECK: the clarification itself landed, so "four options"
    // below describes a real clarification run, not an empty fixture.
    expect(view.clarification).toBe(QUESTION);

    expect(view.clarificationOptions).toEqual(OPTIONS);
    expect(view.clarificationOptions).toHaveLength(4);
  });

  it("is an empty array when the think event carries none, absent and null both", () => {
    // Absent: item 7.5's own clarification, and every run before this
    // field existed.
    expect(viewFor(bareTopicRun(undefined)).clarificationOptions).toEqual([]);
    // Null: the wire field is nullable as well as optional.
    expect(viewFor(bareTopicRun(null)).clarificationOptions).toEqual([]);
    // An explicit empty list behaves identically to both.
    expect(viewFor(bareTopicRun([])).clarificationOptions).toEqual([]);
  });

  it("is empty on a grounded answer that carries no clarification at all", () => {
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
    // POPULATE-CHECK: this really is an answered run.
    expect(view.refusal).toBeNull();
    expect(view.clarificationOptions).toEqual([]);
  });

  it("matches the EMPTY_RUN_VIEW shape before any event arrives", () => {
    expect(viewFor([]).clarificationOptions).toEqual([]);
  });
});
