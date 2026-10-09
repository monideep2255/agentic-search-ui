/**
 * The answer page, records first. Build phase 8.7, T-8.7-03 (card 50).
 *
 * The owner's acceptance: records with their citations show at about eight
 * seconds, the summary appears above them without the list jumping, and a
 * Stop after the records keeps them. These arms drive the real view
 * (`useRunView`) into the real `AnswerScreen`, the way `App` does, so the
 * placement a token carries is what decides where it lands.
 *
 * WHAT THIS PINS:
 * - listing claims render the moment they arrive, citations included, with the
 *   "writing" mark standing where the summary will land, above them;
 * - the summary lands ABOVE the records, and no record row is rebuilt when it
 *   does, nor when the run lands (a rebuilt row is a list that jumps);
 * - a token with no placement renders in arrival order, with no listing
 *   attribute and the writing mark after the text, exactly as before;
 * - the "no written summary" note (#168, owner decision D1) still shows in the
 *   two-region layout, wherever the server places it;
 * - stopped with records on screen: the records stay and no writing mark shows.
 *
 * WHAT IT DOES NOT PIN: the Stop rule across the app (`App.stopUntilAnswer`),
 * what `useRunView` derives (`useRunView.placement.test.ts`) or how it looks
 * (the /verify screenshots against `streaming.html`).
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AgentEvent } from "../../lib/events";
import { useRunView } from "../../hooks/useRunView";
import AnswerScreen from "./AnswerScreen";

let seq = 0;
function ev(type: string, payload: Record<string, unknown>): AgentEvent {
  seq += 1;
  return { type, version: "v1", trace_id: "t87", seq, ts: "2026-10-08T00:00:00Z", payload } as unknown as AgentEvent;
}

const citation = (n: number): AgentEvent =>
  ev("citation", {
    citation_id: `k${n}`,
    display_index: n,
    source: "MedGen",
    source_id: `C00${n}`,
    source_url: `https://www.ncbi.nlm.nih.gov/medgen/C00${n}`,
    layer: "layer_2_api",
    field: "name",
    claim_text: `Disease ${n}`,
    evidence_kind: "curated assertion",
    assertion_confidence: "high",
    population_ancestry_context: null,
    license: "public domain",
  });

const withPlacement = (placement: "listing" | "summary" | null, payload: Record<string, unknown>): AgentEvent =>
  ev("token", placement === null ? payload : { ...payload, placement });

/**
 * Two records, as the server sends them once the searches end. The count line
 * is not among them: the server sends it with the summary, placed "summary"
 * (`core/graph.py` `_answer_parts`; fix round, F-8.7-J07 and F-8.7-J09).
 */
const listingEvents = (placement: "listing" | null = "listing"): AgentEvent[] => [
  withPlacement(placement, { text: "Disease name: Alpha disease [1].", marker_ids: ["k1"], kind: "claim" }),
  withPlacement(placement, { text: "Disease name: Beta disease [2].", marker_ids: ["k2"], kind: "claim" }),
  citation(1),
  citation(2),
];

const COUNT_LINE = "Found 2 disease records for BRCA1: Alpha disease [1] and Beta disease [2].";

/** The count line, then the written summary, as the server sends them after the writer. */
const summaryEvents = (): AgentEvent[] => [
  withPlacement("summary", { text: COUNT_LINE, marker_ids: ["k1", "k2"], kind: "claim" }),
  withPlacement("summary", { text: "BRCA1 is linked to two inherited conditions [1].", marker_ids: ["k1"], kind: "claim" }),
];

/** `core/graph.py` `_build_writer_failed_note`, word for word. */
const WRITER_FAILED_NOTE =
  "Note: the written summary could not be finished this time, so this answer lists the records found";

const doneEvent = (): AgentEvent =>
  ev("done", { total_cost_usd: 0.01, total_tool_calls: 1, elapsed_ms: 9000, trust_outcome: "answer" });

const NO_SUMMARY_NOTE =
  "Note: no written summary could be checked against the records, so the records found are listed below with their sources";

function Screen({
  events,
  running = true,
  stopped = false,
}: {
  events: AgentEvent[];
  running?: boolean;
  stopped?: boolean;
}) {
  const view = useRunView(events);
  return (
    <AnswerScreen
      question="What diseases are linked to BRCA1?"
      claims={view.claims}
      sources={view.sources}
      systemNotes={view.systemNotes}
      progress={running ? <div data-testid="progress" /> : undefined}
      stopped={stopped}
    />
  );
}

/** True when `a` comes before `b` in the document. */
const before = (a: Element, b: Element) =>
  Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);

const listingRows = () => Array.from(document.querySelectorAll('[data-placement="listing"]'));

describe("the answer page shows the records first (build phase 8.7)", () => {
  it("shows the records and their citations at once, with the writing mark above them", () => {
    render(<Screen events={listingEvents()} />);
    // Populate-check: the records are on screen, with a citation each.
    expect(screen.getByText(/Alpha disease/)).toBeInTheDocument();
    expect(screen.getByText(/Beta disease/)).toBeInTheDocument();
    expect(listingRows().length, "no row carried the listing attribute").toBeGreaterThan(0);

    const mark = screen.getByTestId("streaming-writing-indicator");
    expect(mark, "the writing mark is not in the summary's slot").toHaveAttribute("data-writing-slot");
    expect(before(mark, listingRows()[0]!), "the writing mark stands below the records").toBe(true);
  });

  it("places the summary above the records without rebuilding a record row", () => {
    const { rerender } = render(<Screen events={listingEvents()} />);
    const rowsBefore = listingRows();
    expect(rowsBefore.length).toBeGreaterThan(0);

    rerender(<Screen events={[...listingEvents(), ...summaryEvents()]} />);
    const summary = screen.getByText(/linked to two inherited conditions/);
    expect(before(summary, listingRows()[0]!), "the summary landed below the records").toBe(true);
    // The list did not jump: every row is the SAME element it was before.
    const rowsAfter = listingRows();
    expect(rowsAfter.length).toBe(rowsBefore.length);
    rowsBefore.forEach((row, i) => expect(rowsAfter[i], `row ${i} was rebuilt`).toBe(row));
  });

  it("keeps every record row when the run lands", () => {
    const events = [...listingEvents(), ...summaryEvents()];
    const { rerender } = render(<Screen events={events} />);
    const rowsBefore = listingRows();
    expect(rowsBefore.length).toBeGreaterThan(0);

    rerender(<Screen events={[...events, doneEvent()]} running={false} />);
    expect(screen.queryByTestId("progress")).toBeNull();
    const rowsAfter = listingRows();
    rowsBefore.forEach((row, i) => expect(rowsAfter[i], `row ${i} was rebuilt at landing`).toBe(row));
  });

  it("renders a token with no placement in arrival order, as before this phase", () => {
    render(<Screen events={listingEvents(null)} />);
    expect(screen.getByText(/Alpha disease/)).toBeInTheDocument();
    expect(listingRows(), "an older producer's token was tagged as the listing").toEqual([]);
    const mark = screen.getByTestId("streaming-writing-indicator");
    expect(mark).not.toHaveAttribute("data-writing-slot");
    expect(before(screen.getByText(/Beta disease/), mark), "the writing mark moved above the text").toBe(true);
  });

  it("shows #168's no-written-summary note in the two-region layout, wherever the server places it", () => {
    for (const placement of [null, "listing", "summary"] as const) {
      const { unmount } = render(
        <Screen
          running={false}
          events={[
            ...listingEvents(),
            withPlacement(placement, { text: NO_SUMMARY_NOTE, marker_ids: [] }),
            doneEvent(),
          ]}
        />,
      );
      expect(screen.getByText(NO_SUMMARY_NOTE), `the note was hidden with placement ${placement}`).toBeInTheDocument();
      expect(screen.getByText(/Alpha disease/), "the records were taken back").toBeInTheDocument();
      unmount();
    }
  });

  it("shows the writer-failed note under records sent early, with the count line above them", () => {
    // Fix round, F-8.7-J09: the server's own order when the writer fails
    // after the records were sent (`test_a_writer_failing_after_the_listing_
    // keeps_the_listing_as_the_answer`): the listing, its citations, the
    // count line placed "summary", then a paragraph break and the note,
    // both placed "listing", then `done`. Mutation that turns this red: add
    // the note to `HIDDEN_NOTE_PATTERNS`, or drop listing-placed notes.
    render(
      <Screen
        running={false}
        events={[
          withPlacement("listing", { text: "\n\n", marker_ids: [], kind: "paragraph_break" }),
          withPlacement("listing", { text: "Disease records found\n\n", marker_ids: [], kind: "heading" }),
          withPlacement("listing", { text: "Alpha disease [1].", marker_ids: ["k1"], kind: "list_item", cells: ["Alpha disease"] }),
          withPlacement("listing", { text: "Beta disease [2].", marker_ids: ["k2"], kind: "list_item", cells: ["Beta disease"] }),
          citation(1),
          citation(2),
          withPlacement("summary", { text: COUNT_LINE, marker_ids: ["k1", "k2"], kind: "claim" }),
          withPlacement("listing", { text: "\n\n", marker_ids: [], kind: "paragraph_break" }),
          withPlacement("listing", { text: WRITER_FAILED_NOTE, marker_ids: [], kind: "note" }),
          ev("done", { total_cost_usd: 0.01, total_tool_calls: 1, elapsed_ms: 9000, trust_outcome: "ask" }),
        ]}
      />,
    );
    expect(screen.getByText(WRITER_FAILED_NOTE), "the writer-failed note is not on screen").toBeInTheDocument();
    expect(screen.getAllByText(/Alpha disease/).length, "the records were taken back").toBeGreaterThan(0);
    const countLine = screen.getByText(/Found 2 disease records for BRCA1/);
    expect(listingRows().length, "no row carried the listing attribute").toBeGreaterThan(0);
    expect(before(countLine, listingRows()[0]!), "the count line landed below the records").toBe(true);
  });

  it("keeps the records under a Stop and shows no writing mark", () => {
    render(<Screen events={listingEvents()} stopped />);
    expect(screen.getByText(/Alpha disease/)).toBeInTheDocument();
    expect(screen.queryByTestId("streaming-writing-indicator")).toBeNull();
  });
});
