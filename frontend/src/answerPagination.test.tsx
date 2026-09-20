/**
 * Table pagination, product-owner request 2026-09-20: "why are we
 * truncating, if the data is relevant, all the data should show, instead
 * if it is a table, we create a pagination." Page size 10, fixed.
 *
 * LEVEL CHOSEN: same as `answerLayout.test.tsx`, events through
 * `useRunView` then `AnswerScreen`, so a table is paged by the same code a
 * live run uses.
 *
 * WHAT THIS PINS:
 * - a table of more than 10 rows shows 10 at a time, and every later row is
 *   reachable through the Next control, with its own citation marker intact;
 * - a table of 10 or fewer rows renders with no pagination control at all;
 * - two tables in one answer page independently of each other.
 *
 * WHAT IT DOES NOT PIN: pixel layout or a real-browser keyboard trace
 * (Playwright's job).
 */

import { fireEvent, render, renderHook, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AgentEvent } from "./lib/events";
import { useRunView } from "./hooks/useRunView";
import { AnswerScreen } from "./components/screens/AnswerScreen";

let seq = 0;
function envelope<TType extends AgentEvent["type"]>(
  type: TType,
  payload: Extract<AgentEvent, { type: TType }>["payload"],
): AgentEvent {
  seq += 1;
  return { type, version: "v1", trace_id: "pagination", seq, ts: "2026-09-20T12:00:00Z", payload } as AgentEvent;
}

function citation(id: string, n: number) {
  return envelope("citation", {
    citation_id: id,
    display_index: n,
    source: "MedGen",
    source_id: `MedGen:C${n}`,
    source_url: `https://www.ncbi.nlm.nih.gov/medgen/C${n}`,
    layer: "layer_2_api",
    field: "ncbi_efetch",
    claim_text: "x",
    evidence_kind: "primary_assertion",
    assertion_confidence: "asserted",
    population_ancestry_context: null,
    license: "public_domain_us_gov",
  });
}

const DONE = envelope("done", {
  total_cost_usd: 0,
  total_tool_calls: 1,
  elapsed_ms: 900,
  trust_outcome: "answer",
  trust_line: "Based on sources, not yet confirmed",
});

/** One table's worth of events: a header, `rows` table_row tokens, and a citation per row. */
function tableEvents(label: string, rows: number, firstCitationN: number): AgentEvent[] {
  const events: AgentEvent[] = [
    envelope("token", { text: "", marker_ids: [], kind: "table_header", cells: [label, "Record"] }),
  ];
  for (let i = 1; i <= rows; i++) {
    const n = firstCitationN + i - 1;
    const id = `c${n}`;
    events.push(
      envelope("token", {
        text: `${label} row ${i} [${n}]. `,
        marker_ids: [id],
        kind: "table_row",
        cells: [`${label} row ${i}`, `C${n}`],
      }),
    );
  }
  for (let i = 1; i <= rows; i++) {
    const n = firstCitationN + i - 1;
    events.push(citation(`c${n}`, n));
  }
  return events;
}

function renderEvents(events: AgentEvent[]) {
  const view = renderHook(() => useRunView(events)).result.current;
  render(
    <AnswerScreen
      question="Which variants are associated with this gene?"
      claims={view.claims}
      sources={view.sources}
      meta={view.meta}
      trust={view.trust}
      systemNotes={view.systemNotes}
    />,
  );
  return view;
}

describe("table pagination", () => {
  it("shows 10 rows of a 12-row table, and the remaining rows are reachable through Next", () => {
    renderEvents([...tableEvents("Variant", 12, 1), DONE]);

    const table = screen.getByTestId("answer-records-0");
    expect(within(table).getAllByTestId(/^claim-text-\d+$/)).toHaveLength(10);
    expect(screen.getByTestId("answer-records-0-status")).toHaveTextContent("Showing 1–10 of 12");

    const prev = screen.getByTestId("answer-records-0-prev");
    const next = screen.getByTestId("answer-records-0-next");
    expect(prev).toBeDisabled();
    expect(next).not.toBeDisabled();

    // Row 11 is not reachable yet.
    expect(screen.queryByText("Variant row 11")).toBeNull();

    fireEvent.click(next);

    expect(screen.getByTestId("answer-records-0-status")).toHaveTextContent("Showing 11–12 of 12");
    const pageTwoRows = within(screen.getByTestId("answer-records-0")).getAllByTestId(/^claim-text-\d+$/);
    expect(pageTwoRows).toHaveLength(2);
    expect(screen.getByText("Variant row 11")).toBeInTheDocument();
    expect(screen.getByText("Variant row 12")).toBeInTheDocument();
    // Every row keeps its own citation marker after paging.
    expect(within(pageTwoRows[0]!).getByRole("button", { name: "Source 11, layer 2" })).toBeInTheDocument();
    expect(prev).not.toBeDisabled();
    expect(next).toBeDisabled();

    fireEvent.click(prev);
    expect(screen.getByTestId("answer-records-0-status")).toHaveTextContent("Showing 1–10 of 12");
    expect(screen.getByText("Variant row 1")).toBeInTheDocument();
  });

  it("renders no pagination control for a table of exactly 10 rows", () => {
    renderEvents([...tableEvents("Gene", 10, 1), DONE]);

    const table = screen.getByTestId("answer-records-0");
    expect(within(table).getAllByTestId(/^claim-text-\d+$/)).toHaveLength(10);
    expect(screen.queryByTestId("answer-records-0-pagination")).toBeNull();
    expect(screen.getByText("Gene row 10")).toBeInTheDocument();
  });

  it("pages two tables in one answer independently", () => {
    renderEvents([
      envelope("token", { text: "First table\n\n", marker_ids: [], kind: "heading" }),
      ...tableEvents("Disease", 11, 1),
      envelope("token", { text: "Second table\n\n", marker_ids: [], kind: "heading" }),
      ...tableEvents("Trial", 11, 12),
      DONE,
    ]);

    const firstNext = screen.getByTestId("answer-records-0-next");
    const secondNext = screen.getByTestId("answer-records-1-next");

    fireEvent.click(firstNext);

    // First table moved to its second page; second table is untouched.
    expect(screen.getByTestId("answer-records-0-status")).toHaveTextContent("Showing 11–11 of 11");
    expect(screen.getByTestId("answer-records-1-status")).toHaveTextContent("Showing 1–10 of 11");
    expect(screen.getByText("Disease row 11")).toBeInTheDocument();
    expect(screen.queryByText("Trial row 11")).toBeNull();

    fireEvent.click(secondNext);
    expect(screen.getByTestId("answer-records-1-status")).toHaveTextContent("Showing 11–11 of 11");
    expect(screen.getByText("Trial row 11")).toBeInTheDocument();
    // First table's page did not move as a side effect of paging the second.
    expect(screen.getByTestId("answer-records-0-status")).toHaveTextContent("Showing 11–11 of 11");
  });
});
