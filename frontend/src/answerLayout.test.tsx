/**
 * The approved answer layout, 2026-09-14 (`design/Main.dc.html`,
 * `Researcher.dc.html`, `Mobile.dc.html`).
 *
 * LEVEL CHOSEN: events go through `useRunView`, then `AnswerScreen` renders
 * the view, so a record line is classified by the same code a live run uses.
 *
 * WHAT THIS PINS:
 * - findings-tail record lines ("Disease name: X") render as a record block
 *   under their label, never as inline prose, for a typed AND a kind-less
 *   producer, and each row shows the claim text minus only the label;
 * - two adjacent record lines group even with no tail note; a lone one stays prose;
 * - `list_item` and `table_row` claims render as table rows, never run together;
 * - a table header of any width renders, plus a narrow Sources column;
 * - copying the answer yields no "Source N, layer L" strings, while every
 *   marker keeps its accessible name;
 * - an uncited sentence has a non-colour cue: no marker, muted ink, and its
 *   screen-reader statement;
 * - Notes render as a list under "Notes", then the medical line, then Sources;
 * - on a phone, a record table becomes stacked rows with the marker after the name.
 *
 * WHAT IT DOES NOT PIN: pixel layout (Playwright screenshots in
 * `e2e/answer-layout.spec.ts`) or clipboard behaviour in a real browser.
 */

import { render, renderHook, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AgentEvent } from "./lib/events";
import { useRunView } from "./hooks/useRunView";
import { AnswerScreen, buildAnswerBlocks, parseRecordLine } from "./components/screens/AnswerScreen";

let seq = 0;
function envelope<TType extends AgentEvent["type"]>(
  type: TType,
  payload: Extract<AgentEvent, { type: TType }>["payload"],
): AgentEvent {
  seq += 1;
  return { type, version: "v1", trace_id: "layout", seq, ts: "2026-09-14T12:00:00Z", payload } as AgentEvent;
}

function citation(id: string, n: number, layer: "layer_2_api" | "layer_3_enrichment" = "layer_2_api") {
  return envelope("citation", {
    citation_id: id,
    display_index: n,
    source: "MedGen",
    source_id: `MedGen:C${n}`,
    source_url: `https://www.ncbi.nlm.nih.gov/medgen/C${n}`,
    layer,
    field: "ncbi_efetch",
    claim_text: "x",
    evidence_kind: "primary_assertion",
    assertion_confidence: "asserted",
    population_ancestry_context: null,
    license: "public_domain_us_gov",
  });
}

const TAIL = "Note: the records below were retrieved for this question and are listed as found.";
const MEDICAL = "This is a research summary, not medical advice.";
const DONE = envelope("done", {
  total_cost_usd: 0,
  total_tool_calls: 1,
  elapsed_ms: 900,
  trust_outcome: "answer",
  trust_line: "Based on 4 sources, not yet confirmed",
});

function tailStream(typed: boolean): AgentEvent[] {
  const k = <T extends object>(extra: T) => (typed ? extra : {});
  return [
    envelope("token", { text: "BRCA1 is linked to four diseases [1]. ", marker_ids: ["c1"], ...k({ kind: "claim" as const }) }),
    ...(typed ? [envelope("token", { text: "\n\n", marker_ids: [], kind: "paragraph_break" })] : []),
    envelope("token", { text: TAIL, marker_ids: [], ...k({ kind: "note" as const }) }),
    envelope("token", { text: "Disease name: Familial cancer of breast [2]. ", marker_ids: ["c2"], ...k({ kind: "claim" as const }) }),
    envelope("token", { text: "Disease name: Fanconi anemia complementation group S [3]. ", marker_ids: ["c3"], ...k({ kind: "claim" as const }) }),
    envelope("token", { text: "gene symbol: BRCA1 [4]. ", marker_ids: ["c4"], ...k({ kind: "claim" as const }) }),
    ...(typed ? [envelope("token", { text: "\n\n", marker_ids: [], kind: "paragraph_break" })] : []),
    envelope("token", { text: "Note: this result was truncated. Showing 4 of 9 matching rows.", marker_ids: [], ...k({ kind: "note" as const }) }),
    envelope("token", { text: MEDICAL, marker_ids: [], ...k({ kind: "note" as const }) }),
    citation("c1", 1),
    citation("c2", 2),
    citation("c3", 3),
    citation("c4", 4),
    envelope("trust_signal", { outcome: "answer", risk_tier: "high", grounded: true, triangulated: null, scope: "answer" }),
    DONE,
  ];
}

function renderEvents(events: AgentEvent[]) {
  const view = renderHook(() => useRunView(events)).result.current;
  render(
    <AnswerScreen
      question="Which diseases are associated with BRCA1?"
      claims={view.claims}
      sources={view.sources}
      meta={view.meta}
      trust={view.trust}
      systemNotes={view.systemNotes}
    />,
  );
  return view;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("parseRecordLine", () => {
  it("recognises the listed labels and leaves everything else alone", () => {
    expect(parseRecordLine("Disease name: Familial cancer of breast.")).toEqual({
      label: "Disease name",
      value: "Familial cancer of breast.",
    });
    expect(parseRecordLine("Clinical trial name: BRCA1 haploinsufficiency.")?.label).toBe("Clinical trial name");
    expect(parseRecordLine("gene symbol: BRCA1.")?.label).toBe("gene symbol");
    expect(parseRecordLine("Literature entity name: BRCA1.")?.label).toBe("Literature entity name");
    expect(parseRecordLine("Note: this result was truncated.")).toBeNull();
    expect(parseRecordLine("BRCA1 is associated with: breast cancer.")).toBeNull();
    expect(parseRecordLine("Disease name:")).toBeNull();
  });
});

describe("records never render inline", () => {
  for (const typed of [true, false]) {
    it(`groups findings-tail record lines under their label (${typed ? "typed" : "kind-less"} producer)`, () => {
      renderEvents(tailStream(typed));
      // Populate-check.
      expect(screen.getByTestId("claim-text-0")).toHaveTextContent("BRCA1 is linked to four diseases");

      const diseases = screen.getByTestId("answer-records-0");
      expect(diseases).toHaveAttribute("data-record-source", "record_line");
      expect(screen.getByRole("heading", { name: "Disease name", level: 2 })).toBeInTheDocument();
      const rows = within(diseases).getAllByTestId(/^claim-text-\d+$/);
      expect(rows.map((row) => row.tagName.toLowerCase())).toEqual(["tr", "tr"]);
      expect(rows[0]).toHaveTextContent("Familial cancer of breast.");
      expect(rows[0]).not.toHaveTextContent("Disease name:");
      expect(screen.getByTestId("answer-records-1")).toHaveTextContent("BRCA1.");
      expect(screen.getByRole("heading", { name: "gene symbol", level: 2 })).toBeInTheDocument();

      // The failure the product owner saw: labels run together as one line of text.
      expect(screen.getByTestId("claims").textContent).not.toMatch(/Disease name:/);
      // One prose paragraph; the inline tail note is its own element, not prose.
      const prose = Array.from(screen.getByTestId("claims").querySelectorAll("p")).filter(
        (node) => !node.getAttribute("data-testid")?.includes("inline-note"),
      );
      expect(prose).toHaveLength(1);
    });
  }

  it("groups two adjacent record lines with no tail note, and leaves a lone one as prose", () => {
    const blocks = buildAnswerBlocks([
      { text: "Disease name: A.", layer: 2, citations: [1] },
      { text: "Disease name: B.", layer: 2, citations: [2] },
      { text: "Clinical trial name: C.", layer: 3, citations: [3] },
    ]);
    expect(blocks.map((block) => block.type)).toEqual(["records", "records"]);

    const lone = buildAnswerBlocks([
      { text: "BRCA1 is a gene.", layer: 2, citations: [1] },
      { text: "Clinical trial name: C.", layer: 3, citations: [3] },
    ]);
    expect(lone.map((block) => block.type)).toEqual(["prose", "prose"]);
  });

  it("renders list items and table rows as rows of one table each, header of any width", () => {
    renderEvents([
      envelope("token", { text: "Summary sentence [1]. ", marker_ids: ["c1"], kind: "claim" }),
      envelope("token", { text: "\n\n", marker_ids: [], kind: "paragraph_break" }),
      envelope("token", { text: "Disease records found\n\n", marker_ids: [], kind: "heading" }),
      envelope("token", { text: "", marker_ids: [], kind: "table_header", cells: ["Disease", "MedGen record", "Source layer"] }),
      envelope("token", { text: "Disease name: X [1]. ", marker_ids: ["c1"], kind: "table_row", cells: ["X", "C0346153", "L2 · live"] }),
      envelope("token", { text: "Disease name: Y [2]. ", marker_ids: ["c2"], kind: "table_row", cells: ["Y", "C2676676", "L2 · live"] }),
      envelope("token", { text: "Gene records found\n\n", marker_ids: [], kind: "heading" }),
      envelope("token", { text: "Gene BRCA1 [3]. ", marker_ids: ["c3"], kind: "list_item", cells: ["BRCA1"] }),
      envelope("token", { text: "Gene BRCA2 [4]. ", marker_ids: ["c4"], kind: "list_item", cells: ["BRCA2"] }),
      citation("c1", 1),
      citation("c2", 2),
      citation("c3", 3),
      citation("c4", 4),
      DONE,
    ]);
    const tables = screen.getAllByTestId("answer-table");
    expect(tables).toHaveLength(2);
    const headers = within(tables[0]!).getAllByRole("columnheader");
    expect(headers.map((th) => th.textContent)).toEqual(["Disease", "MedGen record", "Source layer", ""]);
    expect(headers[3]).toHaveAccessibleName("Sources");
    expect(within(tables[0]!).getAllByRole("row")).toHaveLength(3);
    // The identifier cell is set in mono, the name cell is not.
    const firstRow = screen.getByTestId("claim-text-1");
    const cells = within(firstRow).getAllByRole("cell");
    expect(getComputedStyle(cells[1]!).fontFamily).toMatch(/monospace/);
    expect(getComputedStyle(cells[0]!).fontFamily).not.toMatch(/monospace/);
    // The marker sits in the narrow last column.
    expect(within(cells[3]!).getByRole("button", { name: "Source 1, layer 2" })).toBeInTheDocument();
    // List items: rows of the second table, never text run together.
    expect(screen.getByTestId("claim-text-3").tagName.toLowerCase()).toBe("tr");
    expect(tables[1]).toContainElement(screen.getByTestId("claim-text-4"));
  });

  /*
   * Item 12.9 (2026-09-23): a Researcher table's "Identifier" column is the
   * design's identifier cell (`.rtab td.g`) whatever the id looks like. RED
   * before: "@GENE_BRCA1" and "omim 138079" fail `isIdentifierCell`'s shape
   * test, so they rendered in body type beside a mono CURIE. Populate-checked:
   * the name and status cells in the same rows stay out of mono.
   */
  it("sets every cell under the Identifier header in mono, whatever the id looks like", () => {
    renderEvents([
      envelope("token", { text: "Records found\n\n", marker_ids: [], kind: "heading" }),
      envelope("token", { text: "", marker_ids: [], kind: "table_header", cells: ["Record", "Identifier", "Status"] }),
      envelope("token", {
        text: "Literature entity name: BRCA1 [1]. ",
        marker_ids: ["c1"],
        kind: "table_row",
        cells: ["BRCA1", "@GENE_BRCA1", "Recruiting"],
      }),
      envelope("token", {
        text: "omim title: BREAST-OVARIAN CANCER [2]. ",
        marker_ids: ["c2"],
        kind: "table_row",
        cells: ["BREAST-OVARIAN CANCER", "omim 138079", ""],
      }),
      citation("c1", 1),
      citation("c2", 2),
      DONE,
    ]);
    for (const index of [0, 1]) {
      const cells = within(screen.getByTestId(`claim-text-${index}`)).getAllByRole("cell");
      expect(getComputedStyle(cells[1]!).fontFamily).toMatch(/monospace/);
      expect(getComputedStyle(cells[0]!).fontFamily).not.toMatch(/monospace/);
    }
    const first = within(screen.getByTestId("claim-text-0")).getAllByRole("cell");
    expect(first[1]).toHaveTextContent("@GENE_BRCA1");
    expect(getComputedStyle(first[2]!).fontFamily).not.toMatch(/monospace/);
  });
});

describe("clean copy and accessible citations", () => {
  it("keeps 'Source N, layer L' out of the text while every marker keeps its name", () => {
    renderEvents(tailStream(true));
    const text = screen.getByTestId("claims").textContent ?? "";
    // Populate-check: the prose and its markers rendered.
    expect(text).toContain("BRCA1 is linked to four diseases");
    expect(screen.getAllByRole("button", { name: /^Source \d+, layer 2$/ })).toHaveLength(4);
    expect(text).not.toMatch(/Source \d+, layer/);
    expect(text).not.toMatch(/Sources \d+ to \d+/);
  });

  it("marks an uncited sentence without colour: no marker, muted ink, and a spoken statement", () => {
    renderEvents([
      envelope("token", { text: "BRCA1 is a gene [1]. ", marker_ids: ["c1"], kind: "claim" }),
      envelope("token", { text: "It is widely discussed. ", marker_ids: [], kind: "claim" }),
      citation("c1", 1),
      DONE,
    ]);
    const uncited = screen.getByTestId("claim-text-1");
    expect(uncited).toHaveAttribute("data-layer", "none");
    expect(within(uncited).queryByRole("button")).toBeNull();
    expect(uncited).toHaveTextContent("This sentence has no source.");
    expect(getComputedStyle(uncited).color).toBe("rgb(86, 92, 101)");
    expect(getComputedStyle(screen.getByTestId("claim-text-0")).color).not.toBe("rgb(86, 92, 101)");
    // The spoken statement is kept out of a selection.
    const statement = uncited.querySelector('[data-uncited="true"]') as HTMLElement;
    expect(getComputedStyle(statement).userSelect).toBe("none");
  });
});

describe("notes, the medical line and sources", () => {
  it("lists notes under Notes, then the medical line, then Sources", () => {
    renderEvents(tailStream(true));
    const notes = screen.getByTestId("answer-notes");
    expect(within(notes).getByRole("heading", { name: "Notes" })).toBeInTheDocument();
    expect(within(notes).getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getByTestId("answer-note-0")).toHaveTextContent("this result was truncated");
    expect(notes).not.toHaveTextContent("medical advice");
    const medical = screen.getByTestId("answer-medical-note");
    expect(medical).toHaveTextContent(MEDICAL);
    const sources = screen.getByTestId("sources-disclosure");
    expect(notes.compareDocumentPosition(medical) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(medical.compareDocumentPosition(sources) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

describe("on a phone", () => {
  it("stacks a record table into rows with the marker after the name", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("max-width:720px"),
        media: query,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    );
    renderEvents([
      envelope("token", { text: "Diseases linked to BRCA1\n\n", marker_ids: [], kind: "heading" }),
      envelope("token", { text: "", marker_ids: [], kind: "table_header", cells: ["Disease", "MedGen record"] }),
      envelope("token", { text: "Disease name: X [1]. ", marker_ids: ["c1"], kind: "table_row", cells: ["Familial cancer of breast", "C0346153"] }),
      citation("c1", 1),
      DONE,
    ]);
    expect(screen.queryByTestId("answer-table")).toBeNull();
    const row = screen.getByTestId("claim-text-0");
    expect(row.tagName.toLowerCase()).toBe("li");
    const [name, id] = Array.from(row.children) as HTMLElement[];
    expect(name).toHaveTextContent("Familial cancer of breast");
    expect(within(name!).getByRole("button", { name: "Source 1, layer 2" })).toBeInTheDocument();
    expect(id).toHaveTextContent("C0346153");
  });

  it("keeps the Identifier column in mono on a stacked row too (item 12.9)", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("max-width:720px"),
        media: query,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    );
    renderEvents([
      envelope("token", { text: "", marker_ids: [], kind: "table_header", cells: ["Record", "Identifier"] }),
      envelope("token", {
        text: "Literature entity name: BRCA1 [1]. ",
        marker_ids: ["c1"],
        kind: "table_row",
        cells: ["BRCA1", "@GENE_BRCA1"],
      }),
      citation("c1", 1),
      DONE,
    ]);
    const [name, id] = Array.from(screen.getByTestId("claim-text-0").children) as HTMLElement[];
    expect(name).toHaveTextContent("BRCA1");
    expect(id).toHaveTextContent("@GENE_BRCA1");
    expect(getComputedStyle(id!).fontFamily).toMatch(/monospace/);
    expect(getComputedStyle(name!).fontFamily).not.toMatch(/monospace/);
  });
});

/*
 * Card 23's second part (J-23-01, A-23-01, 2026-10-07). The line under the
 * variant-to-disease table describes that one table, so it sits directly
 * under it. RED before: when the table ended the answer, the line had no
 * claim after it to attach to and showed first in the Notes list instead.
 * Mutation run: dropping the `noteAfter` branch in `useRunView` turns the
 * table-last arms red; dropping the prefix guard turns the answer-wide arm red.
 */
describe("card 23: the variant-to-disease source line stays under its table", () => {
  const SOURCE_LINE =
    "Each row lists the conditions the variant's ClinVar record names; the record's classification " +
    "(for example pathogenic, benign or uncertain) is not shown here. Disease names are MedGen titles looked up from NCBI.";
  const PLACEHOLDER = "2 variant links to ClinVar placeholder conditions (not provided, not specified) are not listed.";

  function variantTable(): AgentEvent[] {
    return [
      envelope("token", { text: "HNF1A variants are linked to two diseases [1]. ", marker_ids: ["c1"], kind: "claim" }),
      envelope("token", { text: "\n\n", marker_ids: [], kind: "paragraph_break" }),
      envelope("token", { text: "Variant-to-disease mapping\n\n", marker_ids: [], kind: "heading" }),
      envelope("token", { text: "", marker_ids: [], kind: "table_header", cells: ["Variant", "Identifier", "Linked disease"] }),
      envelope("token", {
        text: "Sequence variant name: c.737T>G [1]. ",
        marker_ids: ["c1"],
        kind: "table_row",
        cells: ["c.737T>G", "ClinVar:1134661", "Maturity-onset diabetes of the young type 3; Monogenic diabetes"],
      }),
      envelope("token", {
        text: "Sequence variant name: c.1011C>T [2]. ",
        marker_ids: ["c2"],
        kind: "table_row",
        cells: ["c.1011C>T", "ClinVar:1036297", "Maturity-onset diabetes of the young"],
      }),
      envelope("token", { text: "\n\n", marker_ids: [], kind: "paragraph_break" }),
      envelope("token", { text: SOURCE_LINE, marker_ids: [], kind: "note" }),
    ];
  }

  const answerWideNotes = (): AgentEvent[] => [
    envelope("token", { text: "\n\n", marker_ids: [], kind: "paragraph_break" }),
    envelope("token", { text: PLACEHOLDER, marker_ids: [], kind: "note" }),
  ];

  function expectLineDirectlyUnderTable(tableNode: HTMLElement) {
    const line = screen.getByText(SOURCE_LINE);
    expect(line.dataset.testid).toMatch(/answer-inline-note-\d+$/);
    expect(tableNode.compareDocumentPosition(line) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // Directly under: the next element after the table's own block is the line.
    let block: HTMLElement = tableNode;
    while (block.parentElement && !block.parentElement.contains(line)) block = block.parentElement;
    while (block.parentElement && block.parentElement !== line.parentElement) block = block.parentElement;
    expect(block.nextElementSibling).toBe(line);
    expect(screen.getAllByText(SOURCE_LINE)).toHaveLength(1);
  }

  it("keeps the line under the table when the table ends the answer", () => {
    const view = renderEvents([...variantTable(), ...answerWideNotes(), citation("c1", 1), citation("c2", 2), DONE]);
    expect(view.systemNotes).toEqual([PLACEHOLDER]);
    expect(view.claims[2]!.noteAfter).toBe(SOURCE_LINE);
    expectLineDirectlyUnderTable(screen.getByTestId("answer-table"));
    expect(screen.getByTestId("answer-notes")).not.toHaveTextContent("ClinVar record names");
    expect(screen.getByTestId("answer-note-0")).toHaveTextContent(PLACEHOLDER);
  });

  it("keeps the line under the table, and before the next heading, when more records follow", () => {
    renderEvents([
      ...variantTable(),
      envelope("token", { text: "\n\n", marker_ids: [], kind: "paragraph_break" }),
      envelope("token", { text: "Gene records found\n\n", marker_ids: [], kind: "heading" }),
      envelope("token", { text: "Gene HNF1A [3]. ", marker_ids: ["c3"], kind: "list_item", cells: ["HNF1A"] }),
      citation("c1", 1),
      citation("c2", 2),
      citation("c3", 3),
      DONE,
    ]);
    const [variants] = screen.getAllByTestId("answer-table");
    expectLineDirectlyUnderTable(variants!);
    const next = screen.getByRole("heading", { name: "Gene records found" });
    expect(screen.getByText(SOURCE_LINE).compareDocumentPosition(next) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("keeps the line under the stacked rows on a phone when the table ends the answer", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("max-width:720px"),
        media: query,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    );
    renderEvents([...variantTable(), ...answerWideNotes(), citation("c1", 1), citation("c2", 2), DONE]);
    const stacked = screen.getByTestId("claim-text-2").parentElement!;
    expect(stacked).toContainElement(screen.getByTestId("claim-text-1"));
    expectLineDirectlyUnderTable(stacked);
    expect(screen.getByTestId("answer-notes")).not.toHaveTextContent("ClinVar record names");
  });

  it("leaves an answer-wide note after any table in the Notes list", () => {
    const view = renderEvents([
      envelope("token", { text: "Gene-to-disease mapping\n\n", marker_ids: [], kind: "heading" }),
      envelope("token", { text: "", marker_ids: [], kind: "table_header", cells: ["Gene", "Linked disease"] }),
      envelope("token", { text: "Gene HNF1A [1]. ", marker_ids: ["c1"], kind: "table_row", cells: ["HNF1A", "MODY3"] }),
      ...answerWideNotes(),
      citation("c1", 1),
      DONE,
    ]);
    expect(view.systemNotes).toEqual([PLACEHOLDER]);
    expect(view.claims[0]!.noteAfter).toBeUndefined();
    expect(screen.queryAllByTestId(/answer-inline-note-\d+$/)).toHaveLength(0);
    expect(screen.getByTestId("answer-note-0")).toHaveTextContent(PLACEHOLDER);
  });
});
