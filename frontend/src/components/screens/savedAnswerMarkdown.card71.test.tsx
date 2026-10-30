/**
 * Card 71: a reopened answer's table behaves like the live one. It pages
 * ten rows at a time with the live bar, and on a phone it stacks each row.
 */

import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { HistoryAnswerCitation } from "../../lib/api";
import { SavedAnswerMarkdown } from "./savedAnswerMarkdown";

const ROWS = Array.from({ length: 20 }, (_, i) => `| Isolate-${i + 1} [${i + 1}] | gene${i + 1} |`);
const MARKDOWN = ["## Isolates", "| Isolate | Genes |\n| --- | --- |\n" + ROWS.join("\n")].join("\n\n");
/** The stored citations behind the rows' markers (card 135). */
const CITATIONS: HistoryAnswerCitation[] = Array.from({ length: 20 }, (_, i) => ({
  display_index: i + 1,
  source: "pathogen_detection",
  source_id: `SAMN${i + 1}`,
  source_url: `https://www.ncbi.nlm.nih.gov/pathogens/isolates/#SAMN${i + 1}`,
  layer: 2 as const,
}));

function mockMatchMedia(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

describe("a saved table of 20 rows", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows ten rows and the live bar, then rows 11 to 20 on page 2", () => {
    // Catches: the saved table mapping every row with no paging.
    mockMatchMedia(false);
    render(<SavedAnswerMarkdown markdown={MARKDOWN} />);
    const table = screen.getByTestId("saved-answer-table-1");
    expect(table.querySelectorAll("tbody tr")).toHaveLength(10);
    expect(screen.getByTestId("saved-answer-table-1-status").textContent).toBe("Showing 1–10 of 20");
    expect(screen.getByText("Page 1 of 2")).toBeTruthy();
    fireEvent.click(screen.getByTestId("saved-answer-table-1-next"));
    const rows = screen.getByTestId("saved-answer-table-1").querySelectorAll("tbody tr");
    expect(rows).toHaveLength(10);
    expect(rows[0].textContent).toContain("Isolate-11");
    expect(rows[9].textContent).toContain("Isolate-20");
    expect(screen.getByTestId("saved-answer-table-1-status").textContent).toBe("Showing 11–20 of 20");
  });

  it("shows no bar for ten rows or fewer", () => {
    mockMatchMedia(false);
    render(<SavedAnswerMarkdown markdown={"| A | B |\n| --- | --- |\n| x | y |"} />);
    expect(screen.queryByTestId("saved-answer-table-0-pagination")).toBeNull();
  });

  it("stacks each row on a phone, ten at a time, with no table", () => {
    // Catches: the saved table staying an overflow-scroll table on a phone.
    mockMatchMedia(true);
    render(<SavedAnswerMarkdown markdown={MARKDOWN} citations={CITATIONS} />);
    const list = screen.getByTestId("saved-answer-table-1");
    expect(list.tagName).toBe("UL");
    expect(list.querySelector("table")).toBeNull();
    expect(list.querySelectorAll("li")).toHaveLength(10);
    // Card 135: the row's "[1]" is the live marker now, not text.
    const first = list.querySelector("li") as HTMLElement;
    expect(first.textContent).toMatch(/^Isolate-1\u2060/);
    expect(first.textContent).not.toContain("[1]");
    expect(within(first).getByRole("button", { name: "Source 1, layer 2" })).toBeInTheDocument();
    expect(screen.getByTestId("saved-answer-table-1-status").textContent).toBe("Showing 1–10 of 20");
  });

  it("shows no bar for exactly ten rows", () => {
    // Catches: the boundary drifting from "more than ten" to "ten or more".
    const ten = Array.from({ length: 10 }, (_, i) => `| r${i} | v${i} |`).join("\n");
    for (const phone of [false, true]) {
      mockMatchMedia(phone);
      const { unmount } = render(<SavedAnswerMarkdown markdown={`| A | B |\n| --- | --- |\n${ten}`} />);
      expect(screen.queryByTestId("saved-answer-table-0-pagination")).toBeNull();
      expect(screen.queryByTestId("saved-answer-table-0-status")).toBeNull();
      unmount();
    }
  });

  it("lets long values wrap inside the stacked phone row", () => {
    // Catches: the wrap rule on stacked cells being deleted.
    mockMatchMedia(true);
    render(<SavedAnswerMarkdown markdown={MARKDOWN} />);
    const spans = screen.getByTestId("saved-answer-table-1").querySelectorAll("li")[0].querySelectorAll("span");
    expect(spans.length).toBe(2);
    spans.forEach((span) => expect(getComputedStyle(span).overflowWrap).toBe("anywhere"));
  });

  it("labels each stacked value with its column name, empty cells included", () => {
    // Catches: the phone row dropping column names or skipping empty cells.
    mockMatchMedia(true);
    const md = "| Isolate | AMR genes | Country |\n| --- | --- | --- |\n| Iso-1 [1] |  | USA |\n| Iso-2 [2] | blaKPC |  |";
    render(<SavedAnswerMarkdown markdown={md} citations={CITATIONS} />);
    const items = screen.getByTestId("saved-answer-table-0").querySelectorAll("li");
    // Card 135: "Iso-1 [1]" was pinned here as text; the first cell now
    // carries the live marker, so each row's cells are read one by one.
    const cells = (item: Element) => Array.from(item.children).map((cell) => cell as HTMLElement);
    expect(cells(items[0])[0].textContent).toMatch(/^Iso-1\u2060/);
    expect(within(cells(items[0])[0]).getByRole("button", { name: "Source 1, layer 2" })).toBeInTheDocument();
    expect(cells(items[0]).slice(1).map((cell) => cell.textContent)).toEqual(["AMR genes: \u2013", "Country: USA"]);
    expect(cells(items[1])[0].textContent).toMatch(/^Iso-2\u2060/);
    expect(within(cells(items[1])[0]).getByRole("button", { name: "Source 2, layer 2" })).toBeInTheDocument();
    expect(cells(items[1]).slice(1).map((cell) => cell.textContent)).toEqual(["AMR genes: blaKPC", "Country: \u2013"]);
  });

  it("opens on page 1 when given a different table or answer, without unmounting", () => {
    // Catches: the page number carrying over to different content.
    mockMatchMedia(false);
    const other = MARKDOWN.replace(/Isolate-/g, "Other-");
    const { rerender } = render(<SavedAnswerMarkdown markdown={MARKDOWN} />);
    fireEvent.click(screen.getByTestId("saved-answer-table-1-next"));
    expect(screen.getByTestId("saved-answer-table-1-status").textContent).toBe("Showing 11–20 of 20");
    rerender(<SavedAnswerMarkdown markdown={other} />);
    expect(screen.getByTestId("saved-answer-table-1-status").textContent).toBe("Showing 1–10 of 20");
    expect(screen.getByTestId("saved-answer-table-1").querySelector("tbody tr")?.textContent).toContain("Other-1 ");
  });
});
