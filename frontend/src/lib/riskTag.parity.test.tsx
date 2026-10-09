/**
 * Card 71 fix round: the live answer and the reopened answer show the same
 * trust words for the same run (A-71T-01, A-71T-07, A-71T-09, A-71T-10,
 * J-71T-01, J-71T-02, J-71T-03).
 *
 * Each case in `e2e/fixtures/card71_risk_tier_parity.json` is a run's
 * trust_signal tiers in arrival order and the tier capture stores for it.
 * The Python side (`test_capture_saved_answer.py`) checks capture stores
 * exactly that tier. This side feeds the tiers to the real `useRunView` and
 * the stored tier to the real `SavedAnswerScreen`, and checks the two trust
 * lines read the same. Together they bind live and saved through capture.
 *
 * Mutations this catches: capture filtering the empty tier again (the
 * fixture's `stored` then disagrees with the Python reduction), either
 * screen changing the tag's words or its exclusions, and the saved
 * fallback drifting from the live words.
 */

import { readFileSync } from "node:fs";
import path from "node:path";

import { render, renderHook, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SavedAnswerScreen } from "../components/screens/SavedAnswerScreen";
import { useRunView } from "../hooks/useRunView";
import type { AgentEvent, TrustOutcome } from "./events";
import type { HistoryAnswerResponse } from "./api";

interface ParityCase {
  tiers: string[];
  stored: string | null;
}

const FIXTURE = JSON.parse(
  readFileSync(path.resolve(__dirname, "../../e2e/fixtures/card71_risk_tier_parity.json"), "utf8"),
) as { cases: ParityCase[] };

let seq = 0;

function envelope<TType extends AgentEvent["type"]>(
  type: TType,
  payload: Extract<AgentEvent, { type: TType }>["payload"],
): AgentEvent {
  seq += 1;
  return { type, version: "v1", trace_id: "trace-71", seq, ts: "2026-10-08T12:00:00Z", payload } as AgentEvent;
}

function runEvents(tiers: string[], outcome: TrustOutcome, trustLine: string | null): AgentEvent[] {
  return [
    envelope("token", { text: "BRCA1 is a gene.", marker_ids: [] }),
    ...tiers.map((tier) =>
      envelope("trust_signal", { outcome, risk_tier: tier, grounded: true, triangulated: null }),
    ),
    envelope("done", {
      total_cost_usd: 0.01,
      total_tool_calls: 1,
      elapsed_ms: 1000,
      trust_outcome: outcome,
      trust_line: trustLine,
    }),
  ];
}

/** The live trust line as text: a tick before a "good" span, spans joined by the middle dot. */
function liveText(events: AgentEvent[]): string {
  const { result } = renderHook(() => useRunView(events));
  return result.current.trust
    .map((span) => `${span.kind === "good" ? "✓" : ""}${span.label}`)
    .join("·");
}

function savedText(outcome: string, trustLine: string | null, stored: string | null): string {
  const answer: HistoryAnswerResponse = {
    trace_id: "trace-71",
    question: "What is BRCA1?",
    asked_at: "2026-10-08T12:00:00Z",
    depth: "researcher",
    answer_markdown: "BRCA1 is a gene.",
    citations: [],
    trust_signal: outcome,
    trust_line: trustLine,
    risk_tier: stored,
  };
  render(<SavedAnswerScreen question={answer.question} loading={false} answer={answer} onRunAgain={() => undefined} />);
  return screen.getByTestId("saved-answer-trust-line").textContent ?? "";
}

const TRUST_LINE = "Based on 2 sources cited, not yet confirmed";

describe("the live and the reopened answer show the same trust words", () => {
  it("the fixture has cases, including an empty tier beside high", () => {
    // POPULATE CHECK: an emptied fixture would pass every arm below.
    expect(FIXTURE.cases.length).toBeGreaterThanOrEqual(10);
    expect(FIXTURE.cases.some((c) => c.tiers.includes("") && c.tiers.includes("high"))).toBe(true);
  });

  it.each(FIXTURE.cases.filter((c) => c.tiers.length > 0).map((c) => [c.tiers.join(","), c] as const))(
    "with a trust line, tiers [%s]",
    (_name, c) => {
      const live = liveText(runEvents(c.tiers, "answer", TRUST_LINE));
      expect(live).toContain(TRUST_LINE); // POPULATE CHECK: the summary branch ran
      expect(savedText("answer", TRUST_LINE, c.stored)).toBe(live);
    },
  );

  it.each(FIXTURE.cases.map((c) => [c.tiers.join(","), c] as const))(
    "with no trust line, tiers [%s]",
    (_name, c) => {
      const live = liveText(runEvents(c.tiers, "answer", null));
      expect(savedText("answer", null, c.stored)).toBe(live);
    },
  );

  it("a capped run (done flag, no trust line, no trust signal) reads Not verified on both", () => {
    // A-71T-10, with the events `_partial_result_for_cap` emits. Capture
    // stores no tier for it (no trust_signal).
    const live = liveText(runEvents([], "flag", null));
    expect(live).toBe("Not verified · no grounding check was recorded");
    expect(savedText("flag", null, null)).toBe(live);
  });

  it("a high tier reads High-risk claim on both trust-line branches", () => {
    // J-71T-02: the live branch without a trust line used to read
    // "high risk claim". Mutation: restoring that string in useRunView turns
    // this red.
    expect(liveText(runEvents(["high"], "answer", null))).toBe(
      "✓Grounded · every claim cited·High-risk claim",
    );
    expect(liveText(runEvents(["high"], "answer", TRUST_LINE))).toBe(`${TRUST_LINE}·High-risk claim`);
  });
});
