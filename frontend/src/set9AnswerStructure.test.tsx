/**
 * UI fix set 9: answers worth reading, from the wire to the screen.
 *
 * LEVEL CHOSEN: each arm feeds a real `AgentEvent[]` through `useRunView` and,
 * where it is about what a reader sees, renders `AnswerScreen` with the view
 * that produced. The classification (what is a claim, a heading, a note) lives
 * in the hook, so a component test with hand-built props would assert its own
 * fixture.
 *
 * Mutations each arm was run against before being kept, results recorded in
 * `testing/Developer/reports/2026-09-13_set_9/report.md`:
 * - Dropping the `kind === "note"` branch in `useRunView`: four arms red (the
 *   notes become claims and the paragraphs shift).
 * - The 9.8 arm is guarded by TWO independent controls, the kind-less
 *   "Note:" fallback and the "Note: one further" prefix. Removing either one
 *   alone leaves it green, which is the redundancy working; removing both
 *   turns it red.
 * - Ignoring `done.trust_line`: the trust-line arm red.
 * - Removing the after-the-answer notes block: the notes arm red. That proves
 *   the notes render there; the order itself is asserted by
 *   `compareDocumentPosition`, not by a separate mutation.
 */

import { render, renderHook, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AgentEvent } from "./lib/events";
import { useRunView } from "./hooks/useRunView";
import type { RunView } from "./hooks/useRunView";
import { AnswerScreen } from "./components/screens/AnswerScreen";

let seq = 0;

function envelope<TType extends AgentEvent["type"]>(
  type: TType,
  payload: Extract<AgentEvent, { type: TType }>["payload"],
): AgentEvent {
  seq += 1;
  return {
    type,
    version: "v1",
    trace_id: "trace-set9",
    seq,
    ts: `2026-09-13T12:00:${String(seq % 60).padStart(2, "0")}Z`,
    payload,
  } as AgentEvent;
}

function citation(id: string, n: number, layer: "layer_1_graph" | "layer_2_api" = "layer_1_graph") {
  return envelope("citation", {
    citation_id: id,
    display_index: n,
    source: "MedGen",
    source_id: `MedGen:C${n}`,
    source_url: `https://www.ncbi.nlm.nih.gov/medgen/C${n}`,
    layer,
    field: "name",
    claim_text: "x",
    evidence_kind: "primary_assertion",
    assertion_confidence: "asserted",
    population_ancestry_context: null,
    license: "public_domain_us_gov",
  });
}

const MEDICAL = "This is a research summary, not medical advice.";
const TAIL_NOTE = "Note: the records below were retrieved for this question and are listed as found.";

function researcherStream(extraDone: Record<string, unknown> = {}): AgentEvent[] {
  return [
    envelope("guard", { passed: true, category: "ok", reason: null }),
    envelope("token", {
      text: "BRCA1 is associated with Familial cancer of breast [1]. ",
      marker_ids: ["c1"],
      kind: "claim",
      emphasis: ["BRCA1", "Familial cancer of breast"],
    }),
    envelope("token", {
      text: "It is also associated with Fanconi anemia [2]. ",
      marker_ids: ["c2"],
      kind: "claim",
    }),
    envelope("token", { text: "\n\n", marker_ids: [], kind: "paragraph_break" }),
    envelope("token", { text: "Disease records found\n\n", marker_ids: [], kind: "heading" }),
    envelope("token", {
      text: "Disease MedGen:C1, name: Familial cancer of breast [1]. ",
      marker_ids: ["c1"],
      kind: "list_item",
      cells: ["Familial cancer of breast"],
    }),
    envelope("token", {
      text: "Disease MedGen:C2, name: Fanconi anemia [2]. ",
      marker_ids: ["c2"],
      kind: "list_item",
      cells: ["Fanconi anemia"],
    }),
    envelope("token", {
      text: "Note: this result was truncated. Showing 2 of 9 matching rows.",
      marker_ids: [],
      kind: "note",
    }),
    citation("c1", 1),
    citation("c2", 2),
    envelope("trust_signal", {
      outcome: "ask",
      risk_tier: "high",
      grounded: true,
      triangulated: null,
      scope: "answer",
    }),
    envelope("done", {
      total_cost_usd: 0,
      total_tool_calls: 1,
      elapsed_ms: 1200,
      trust_outcome: "ask",
      trust_line: "Based on 1 source, not yet confirmed",
      ...extraDone,
    } as Extract<AgentEvent, { type: "done" }>["payload"]),
  ];
}

function renderView(view: RunView) {
  return render(
    <AnswerScreen
      question="Which diseases are associated with BRCA1?"
      claims={view.claims}
      sources={view.sources}
      meta={view.meta}
      trust={view.trust}
      systemNotes={view.systemNotes}
    />,
  );
}

describe("set 9: structure travels on the wire and reaches the screen", () => {
  it("groups prose into paragraphs, attaches the heading and keeps list cells", () => {
    const { result } = renderHook(() => useRunView(researcherStream()));
    const claims = result.current.claims;
    expect(claims.map((c) => c.kind)).toEqual(["claim", "claim", "list_item", "list_item"]);
    expect(claims[0].paragraph).toBe(claims[1].paragraph);
    expect(claims[2].paragraph).not.toBe(claims[1].paragraph);
    expect(claims[2].heading).toBe("Disease records found");
    expect(claims[2].cells).toEqual(["Familial cancer of breast"]);
    expect(claims.every((c) => c.citations.length > 0)).toBe(true);
    expect(result.current.systemNotes).toEqual([
      "Note: this result was truncated. Showing 2 of 9 matching rows.",
    ]);
  });

  it("renders paragraphs as prose, the heading as a heading, the listing as a list, bold terms bold", () => {
    const { result } = renderHook(() => useRunView(researcherStream()));
    renderView(result.current);

    const firstParagraph = screen.getByTestId("claim-text-0").closest("p");
    expect(firstParagraph).not.toBeNull();
    expect(firstParagraph).toContainElement(screen.getByTestId("claim-text-1"));
    expect(screen.getByRole("heading", { name: "Disease records found", level: 2 })).toBeInTheDocument();
    expect(screen.getByTestId("claim-text-2").tagName.toLowerCase()).toBe("li");
    expect(screen.getByTestId("claim-text-2")).toHaveTextContent("Familial cancer of breast");
    expect(screen.getByTestId("claim-text-2")).not.toHaveTextContent("MedGen:C1, name:");
    const bold = within(screen.getByTestId("claim-text-0")).getAllByText(/BRCA1|Familial cancer of breast/);
    expect(bold.every((element) => element.tagName.toLowerCase() === "strong")).toBe(true);
    // One spine segment per claim, still.
    expect(screen.getAllByTestId(/^spine-segment-\d+$/)).toHaveLength(4);
  });

  it("shows notes after the answer, never before the first sentence", () => {
    const { result } = renderHook(() => useRunView(researcherStream()));
    renderView(result.current);
    const note = screen.getByTestId("answer-note-0");
    const claims = screen.getByTestId("claims");
    // DOCUMENT_POSITION_FOLLOWING (4): the note comes after the claims.
    expect(claims.compareDocumentPosition(note) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("places the findings-tail note in position and ends a Plain language answer on the medical note", () => {
    const events = [
      envelope("token", { text: "BRCA1 is linked to Fanconi anemia [1]. ", marker_ids: ["c1"], kind: "claim" }),
      envelope("token", { text: "\n\n", marker_ids: [], kind: "paragraph_break" }),
      envelope("token", { text: TAIL_NOTE, marker_ids: [], kind: "note" }),
      envelope("token", { text: "gene symbol: BRCA1 [2]. ", marker_ids: ["c2"], kind: "claim" }),
      envelope("token", { text: "\n\n", marker_ids: [], kind: "paragraph_break" }),
      envelope("token", { text: MEDICAL, marker_ids: [], kind: "note" }),
      citation("c1", 1),
      citation("c2", 2),
      envelope("done", { total_cost_usd: 0, total_tool_calls: 1, elapsed_ms: 1, trust_outcome: "answer" }),
    ];
    const { result } = renderHook(() => useRunView(events));
    expect(result.current.claims.map((c) => c.text)).not.toContain(TAIL_NOTE);
    expect(result.current.claims[1].noteBefore).toBe(TAIL_NOTE);
    expect(result.current.systemNotes).toEqual([MEDICAL]);
    renderView(result.current);
    expect(screen.getByTestId("answer-inline-note-0")).toHaveTextContent(TAIL_NOTE);
  });

  it("never shows a kind-less 'one further gene record' note as an uncited claim (9.8)", () => {
    const note = "Note: one further gene record was found for this question and is not described above";
    const events = [
      envelope("token", { text: "BRCA1 is linked to Fanconi anemia [1]. ", marker_ids: ["c1"] }),
      envelope("token", { text: note, marker_ids: [] }),
      citation("c1", 1),
      envelope("done", { total_cost_usd: 0, total_tool_calls: 1, elapsed_ms: 1, trust_outcome: "ask" }),
    ];
    const { result } = renderHook(() => useRunView(events));
    expect(result.current.claims.map((c) => c.text)).toEqual(["BRCA1 is linked to Fanconi anemia."]);
    expect(result.current.systemNotes).toEqual([note]);
  });

  it("replaces the pills with one plain trust line, keeping high risk visible (9.9)", () => {
    const { result } = renderHook(() => useRunView(researcherStream()));
    expect(result.current.trust).toEqual([
      { kind: "plain", label: "Based on 1 source, not yet confirmed" },
      { kind: "risk", label: "High-risk claim" },
    ]);
    renderView(result.current);
    const line = screen.getByTestId("trust-line");
    expect(line).toHaveTextContent("Based on 1 source, not yet confirmed");
    expect(line).not.toHaveTextContent(/every claim cited/i);
    expect(within(line).getByRole("button", { name: /about trust signals/i })).toBeInTheDocument();
  });

  it("never states the caution twice: the status word defers to the trust line", () => {
    const withLine = renderHook(() => useRunView(researcherStream())).result.current;
    expect(withLine.outcome).toBe("Answered");
    expect(withLine.outcomeTone).toBe("warn");
    const without = renderHook(() => useRunView(researcherStream({ trust_line: undefined }))).result
      .current;
    expect(without.outcome).toBe("Single source, not independently confirmed");
  });

  it("keeps the old pills for a backend that sends no trust line", () => {
    const { result } = renderHook(() => useRunView(researcherStream({ trust_line: undefined })));
    expect(result.current.trust.map((t) => t.label)).toContain("Grounded · every claim cited");
  });
});
