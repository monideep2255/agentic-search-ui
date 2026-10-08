/**
 * Card 71: a reopened answer's table behaves like the live one. It pages
 * ten rows at a time with the live bar, and on a phone it stacks each row.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SavedAnswerMarkdown } from "./savedAnswerMarkdown";

const ROWS = Array.from({ length: 20 }, (_, i) => `| Isolate-${i + 1} [${i + 1}] | gene${i + 1} |`);
const MARKDOWN = ["## Isolates", "| Isolate | Genes |\n| --- | --- |\n" + ROWS.join("\n")].join("\n\n");

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
    render(<SavedAnswerMarkdown markdown={MARKDOWN} />);
    const list = screen.getByTestId("saved-answer-table-1");
    expect(list.tagName).toBe("UL");
    expect(list.querySelector("table")).toBeNull();
    expect(list.querySelectorAll("li")).toHaveLength(10);
    expect(list.querySelector("li")?.textContent).toContain("Isolate-1 [1]");
    expect(screen.getByTestId("saved-answer-table-1-status").textContent).toBe("Showing 1–10 of 20");
  });
});
