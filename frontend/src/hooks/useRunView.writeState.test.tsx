/**
 * The Write state starts when Act ends, 2026-09-14.
 *
 * Measured on develop: every token arrives in one burst after a silent gap of
 * 1.9 to 22.6 seconds following Act's last `tool_result`. Keyed on the first
 * token, the stepper sat on Act through the whole gap and "is writing the
 * answer" never showed.
 *
 * WHAT THIS PINS:
 * - with two tools, Act holds until BOTH results land, then Write, with no
 *   token yet;
 * - the writing banner is on screen during that gap, naming the helpers and
 *   the record count;
 * - a plan that selects no tool enters Write (the refusal path);
 * - a plan that names a tool not yet started stays on Plan;
 * - a tool started after Write reopens Act;
 * - a guardrail refusal lands with no live step;
 * - a stopped run shows no banner.
 *
 * WHAT IT DOES NOT PIN: a live Write `step` frame (none exists on the wire yet;
 * `useAgentRun.forwardCompat.test.ts` pins that one would be ignored).
 */

import { render, renderHook, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AgentEvent } from "../lib/events";
import { useRunView } from "./useRunView";
import { RunProgress } from "../components/screens/RunProgress";

let seq = 0;
function envelope<TType extends AgentEvent["type"]>(
  type: TType,
  payload: Extract<AgentEvent, { type: TType }>["payload"],
): AgentEvent {
  seq += 1;
  return { type, version: "v1", trace_id: "t", seq, ts: "2026-09-14T12:00:00Z", payload } as AgentEvent;
}

const GUARD = envelope("guard", { passed: true, category: "ok", reason: null });
const THINK = envelope("think", {
  narrative: "Resolving BRCA1.",
  query_class: "single_hop",
  resolved_entities: [],
  clarifying_question: null,
});
const PLAN_TWO = envelope("plan", {
  narrative: "Two layers.",
  tool_calls: [
    { tool: "ncbi_efetch", call_id: "c1", layer: "layer_2_api", persona: "Salk" },
    { tool: "clinicaltrials_search", call_id: "c2", layer: "layer_3_enrichment", persona: "Nightingale" },
  ],
});
const start = (id: string, tool: "ncbi_efetch" | "clinicaltrials_search", layer: "layer_2_api" | "layer_3_enrichment", persona: string) =>
  envelope("tool_start", { call_id: id, tool, layer, status: "running", persona });
const result = (id: string, tool: "ncbi_efetch" | "clinicaltrials_search", layer: "layer_2_api" | "layer_3_enrichment", persona: string, count: number) =>
  envelope("tool_result", { call_id: id, tool, layer, status: "ok", persona, summary: "", result_count: count, truncated: false });

const ACT_OPEN = [
  GUARD,
  THINK,
  PLAN_TWO,
  start("c1", "ncbi_efetch", "layer_2_api", "Salk"),
  start("c2", "clinicaltrials_search", "layer_3_enrichment", "Nightingale"),
  result("c1", "ncbi_efetch", "layer_2_api", "Salk", 6),
];
const ACT_CLOSED = [...ACT_OPEN, result("c2", "clinicaltrials_search", "layer_3_enrichment", "Nightingale", 5)];

describe("the Write state", () => {
  it("holds Act until every opened call has a result, then enters Write before any token", () => {
    const open = renderHook(() => useRunView(ACT_OPEN)).result.current;
    expect(open.activeStep).toBe("Act");

    const closed = renderHook(() => useRunView(ACT_CLOSED)).result.current;
    expect(closed.claims).toHaveLength(0);
    expect(closed.activeStep).toBe("Write");
    expect(closed.reachedSteps).toContain("Write");
    expect(closed.landed).toBe(false);
  });

  it("shows the writing banner in the gap between the last tool_result and the first token", () => {
    const view = renderHook(() => useRunView(ACT_CLOSED)).result.current;
    render(
      <RunProgress
        question="Which diseases are associated with BRCA1?"
        activeStep={view.activeStep}
        reachedSteps={view.reachedSteps}
        toolCalls={view.toolCalls}
        startedAt={Date.now()}
        personaName="Levi-Montalcini"
      />,
    );
    const banner = screen.getByTestId("writing-banner");
    expect(banner).toHaveTextContent("Levi-Montalcini is writing the answer...");
    expect(banner).toHaveTextContent("Salk and Nightingale found 11 records");
    expect(screen.getByTestId("step-Write")).toHaveAttribute("data-state", "live");
    expect(screen.getByTestId("step-Act")).toHaveAttribute("data-state", "done");
    // The banner replaces the handoff lines and the tool chips while it writes.
    expect(screen.queryByTestId("handoff")).toBeNull();
    expect(screen.queryByTestId("tool-ncbi_efetch")).toBeNull();
  });

  it("enters Write when the plan selects no tool (the no-data refusal path)", () => {
    const view = renderHook(() =>
      useRunView([GUARD, THINK, envelope("plan", { narrative: "Nothing to look up.", tool_calls: [] })]),
    ).result.current;
    expect(view.activeStep).toBe("Write");
    render(<RunProgress question="q" activeStep={view.activeStep} startedAt={Date.now()} personaName="Mendel" />);
    const banner = screen.getByTestId("writing-banner");
    expect(banner).toHaveTextContent("Mendel is writing the answer");
    // No tool ran, so no record count is claimed.
    expect(banner).not.toHaveTextContent(/found/);
  });

  it("stays on Plan while a planned tool has not started", () => {
    const view = renderHook(() => useRunView([GUARD, THINK, PLAN_TWO])).result.current;
    expect(view.activeStep).toBe("Plan");
  });

  it("returns to Act when another tool starts after Write began", () => {
    const view = renderHook(() =>
      useRunView([...ACT_CLOSED, start("c3", "ncbi_efetch", "layer_2_api", "Salk")]),
    ).result.current;
    expect(view.activeStep).toBe("Act");
  });

  it("a guardrail refusal lands with no live step", () => {
    const view = renderHook(() =>
      useRunView([
        envelope("guard", { passed: false, category: "off_topic", reason: null }),
        envelope("done", { total_cost_usd: 0, total_tool_calls: 0, elapsed_ms: 10, trust_outcome: "refuse" }),
      ]),
    ).result.current;
    expect(view.landed).toBe(true);
    expect(view.activeStep).toBeNull();
  });

  it("shows no banner once Stop latches", () => {
    render(<RunProgress question="q" activeStep={null} startedAt={null} stopped personaName="Mendel" />);
    expect(screen.getByTestId("run-stopped")).toBeInTheDocument();
    expect(screen.queryByTestId("writing-banner")).toBeNull();
  });
});
