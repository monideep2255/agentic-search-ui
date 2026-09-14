/**
 * A streaming sentence never shows raw "[1][2]" markers, 2026-09-14.
 *
 * Product-owner complaint: the wait was cluttered. Until a sentence's citation
 * frames arrived, its `[N]` markers matched nothing and rendered as raw text
 * beside a grey "uncited" spine segment.
 *
 * WHAT THIS PINS, each with a populate-check so an empty render cannot pass:
 * - mid-stream, a sentence with `[1][2]` and no citation frames yet renders no
 *   bracket text, shows quiet pending markers, and is NOT called uncited;
 * - the same sentence switches to real, focusable markers once its citation
 *   frames arrive;
 * - a sentence that lands genuinely uncited still says "This sentence has no
 *   source.";
 * - a LANDED answer is unchanged: an unresolved marker stays as prose, the
 *   F-4.8-R-05 rule that nothing is stripped by pattern alone.
 *
 * WHAT IT DOES NOT PIN: the backend's frame order. It scripts the order the
 * complaint describes, tokens first and citation frames later.
 */

import { render, renderHook, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AgentEvent } from "./lib/events";
import { useRunView } from "./hooks/useRunView";
import { AnswerScreen } from "./components/screens/AnswerScreen";
import { RunProgress } from "./components/screens/RunProgress";

let seq = 0;
function envelope<TType extends AgentEvent["type"]>(
  type: TType,
  payload: Extract<AgentEvent, { type: TType }>["payload"],
): AgentEvent {
  seq += 1;
  return {
    type,
    version: "v1",
    trace_id: "trace-pending",
    seq,
    ts: "2026-09-14T12:00:00Z",
    payload,
  } as AgentEvent;
}

function citation(id: string, n: number): AgentEvent {
  return envelope("citation", {
    citation_id: id,
    display_index: n,
    source: "MedGen",
    source_id: `MedGen:C${n}`,
    source_url: `https://www.ncbi.nlm.nih.gov/medgen/C${n}`,
    layer: "layer_2_api",
    field: "name",
    claim_text: "x",
    evidence_kind: "primary_assertion",
    assertion_confidence: "asserted",
    population_ancestry_context: null,
    license: "public_domain_us_gov",
  });
}

const SENTENCE = "BRCA1 is associated with Familial cancer of breast [1][2]. ";
const UNCITED = "It is widely discussed in the popular press. ";

const HEAD = [envelope("guard", { passed: true, category: "ok", reason: null })];
const TOKEN = envelope("token", { text: SENTENCE, marker_ids: ["c1", "c2"] });
const UNCITED_TOKEN = envelope("token", { text: UNCITED, marker_ids: [] });
const DONE = envelope("done", {
  total_cost_usd: 0.01,
  total_tool_calls: 1,
  elapsed_ms: 900,
  trust_outcome: "answer",
});

function renderStreaming(events: AgentEvent[]) {
  const { result } = renderHook(() => useRunView(events));
  const view = result.current;
  render(
    <AnswerScreen
      question="Which diseases are associated with BRCA1?"
      progress={<RunProgress activeStep="Write" startedAt={Date.now()} personaName="Mendel" />}
      claims={view.claims}
      sources={view.sources}
    />,
  );
  return view;
}

describe("a streaming sentence with markers but no citation frames yet", () => {
  it("renders no bracket text, shows pending markers, and is not called uncited", () => {
    const view = renderStreaming([...HEAD, TOKEN]);
    expect(view.landed).toBe(false);
    expect(view.claims[0].pendingCitations).toBe(2);
    expect(view.claims[0].citations).toEqual([]);

    const claim = screen.getByTestId("claim-text-0");
    // Populate-check: the sentence itself rendered.
    expect(claim).toHaveTextContent("BRCA1 is associated with Familial cancer of breast");
    expect(claim.textContent).not.toMatch(/\[\d+\]/);

    const pending = screen.getByTestId("citation-pending-0");
    expect(pending).toHaveTextContent("2 sources pending.");
    // Nothing to open yet, so nothing to focus.
    expect(pending.querySelector("button")).toBeNull();
    expect(claim).not.toHaveTextContent("This sentence has no source.");
    expect(screen.getByTestId("spine-segment-0")).toHaveAttribute("data-layer", "pending");
  });

  it("switches to real markers once its citation frames arrive", () => {
    const view = renderStreaming([...HEAD, TOKEN, citation("c1", 1), citation("c2", 2)]);
    expect(view.claims[0].pendingCitations).toBeUndefined();
    expect(view.claims[0].citations).toEqual([1, 2]);

    const claim = screen.getByTestId("claim-text-0");
    expect(claim).toHaveTextContent("BRCA1 is associated with Familial cancer of breast");
    expect(claim.textContent).not.toMatch(/\[\d+\]/);
    expect(screen.queryByTestId("citation-pending-0")).toBeNull();
    expect(screen.getByRole("button", { name: "Source 1, layer 2" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Source 2, layer 2" })).toBeInTheDocument();
    expect(screen.getByTestId("spine-segment-0")).toHaveAttribute("data-layer", "2");
  });

  it("handles one citation arriving before the other", () => {
    const view = renderStreaming([...HEAD, TOKEN, citation("c1", 1)]);
    expect(view.claims[0].citations).toEqual([1]);
    expect(view.claims[0].pendingCitations).toBe(1);
    expect(screen.getByTestId("claim-text-0").textContent).not.toMatch(/\[\d+\]/);
  });
});

describe("the landed answer is unchanged", () => {
  it("still says an uncited sentence has no source", () => {
    const events = [...HEAD, TOKEN, citation("c1", 1), citation("c2", 2), UNCITED_TOKEN, DONE];
    const { result } = renderHook(() => useRunView(events));
    expect(result.current.landed).toBe(true);
    render(
      <AnswerScreen question="q" claims={result.current.claims} sources={result.current.sources} />,
    );
    // Populate-check: both claims rendered.
    expect(screen.getByTestId("claim-text-0")).toHaveTextContent("Familial cancer of breast");
    expect(screen.getByTestId("claim-text-1")).toHaveTextContent("widely discussed");
    expect(screen.getByTestId("claim-text-1")).toHaveTextContent("This sentence has no source.");
    expect(screen.getByTestId("spine-segment-1")).toHaveAttribute("data-layer", "none");
    expect(screen.queryByTestId(/^citation-pending-/)).toBeNull();
  });

  it("keeps a marker that never resolved as prose once landed (F-4.8-R-05)", () => {
    const { result } = renderHook(() => useRunView([...HEAD, TOKEN, DONE]));
    expect(result.current.landed).toBe(true);
    expect(result.current.claims[0].pendingCitations).toBeUndefined();
    expect(result.current.claims[0].text).toContain("[1][2]");
  });
});
