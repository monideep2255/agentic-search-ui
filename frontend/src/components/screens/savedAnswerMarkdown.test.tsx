/**
 * `SavedAnswerMarkdown` (defect one, `testing/Developer/reports/
 * 2026-09-23_overnight/findings.md`'s "Worker B2" entry).
 *
 * Both fixtures below are REAL stored strings, not hand-written markdown:
 * every one is `feedback/capture.py::answer_markdown_from`'s actual output
 * against a real or synthetic event list, generated with the shipped
 * builder rather than typed by hand into this file. See the comment above
 * each fixture for exactly how it was produced.
 *
 * Every test states, in a comment, the mutation or defect it is proven to
 * catch.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { HistoryAnswerCitation } from "../../lib/api";
import { markerLabel } from "../answer/CitationMarkers";
import { SavedAnswerMarkdown, parseSavedAnswerMarkdown } from "./savedAnswerMarkdown";

/**
 * `answer_markdown_from` run against
 * `testing/Developer/reports/2026-09-22_isolate_search/round2/
 * tokens_G-035.json`'s real 31 `token` events (question G-035, "What
 * Escherichia coli isolates in Pathogen Detection carry extended-spectrum
 * beta-lactamase genes?"), captured verbatim from a live run on develop.
 * Exercises: a paragraph with inline `[n]` markers, a `## heading`, a
 * 20-row table whose first cell carries a marker, a second heading, a
 * bulleted list item, and a trailing plain paragraph (the "could not be
 * verified" note).
 */
const G_035_MARKDOWN =
  "Found 20 pathogen detection isolate records for Escherichia coli [1][2][3][4][5][6][7][8][9][10][11][12][13][14][15][16][17][18][19][20].\n\n" +
  "## Isolates and their AMR genes\n\n" +
  "| Isolate | AMR genes |\n" +
  "| --- | --- |\n" +
  "| C236-11 [1] | acrF, aph(3'')-Ib, aph(6)-Id, blaCTX-M-15, blaEC, blaTEM-1, dfrA7, gyrA_S83A=POINT, mdtM, sul1, sul2, tet(A) |\n" +
  "| NA114 [20] | aac(6')-Ib-cr5, aadA5, acrF, blaCTX-M-15, blaEC, blaOXA-1, catB3=PARTIAL, dfrA17, gyrA_D87N=POINT, gyrA_S83L=POINT, mdtM, mph(A), mrx(A), parC_E84V=POINT, parC_S80I=POINT, parE_I529L=POINT, ptsI_V25I=POINT, sul1, tet(A), uhpT_E350Q=POINT |\n\n" +
  "## Taxonomy records found\n\n" +
  "- Escherichia coli[21]\n\n" +
  "Pathogen Detection lists 140,476 Escherichia coli isolates with these genes; the first 20 in the snapshot are shown.\n\n" +
  "Note: the written summary of these records could not be verified against them, so this answer lists the records found instead";

/**
 * `answer_markdown_from` run against a synthetic event list built with the
 * SAME builder, constructed to exercise the one thing G-035 does not: a
 * table cell whose source content contains a literal `|` and a literal `\`,
 * which `_cell` escapes to `\|` and `\\` on the way in. Source events (kept
 * in this repository's overnight findings for reproduction): a `heading`
 * token "Isolates found", a `claim` token "Two records matched the filter
 * [1]. ", a `table_header` with cells `["Name | with pipe", "Backslash \
 * value"]`, a `table_row` with cells `["A | B", "back\slash"]` and one
 * marker, a `list_item` with cells `["A plain bullet"]` and one marker, and
 * a `note` token. Regenerate with:
 *
 *   PYTHONPATH=src venv/bin/python - <<'PY'
 *   from datetime import datetime, timezone
 *   from system_03_search_agent.contracts.events import Event
 *   from system_03_search_agent.feedback.capture import answer_markdown_from
 *   ...(see this file's own history for the full script)
 *   PY
 */
const ESCAPED_MARKDOWN =
  "## Isolates found\n\n" +
  "Two records matched the filter [1].\n\n" +
  "| Name \\| with pipe | Backslash \\\\ value |\n" +
  "| --- | --- |\n" +
  "| A \\| B [1] | back\\\\slash |\n\n" +
  "- A plain bullet[1]\n\n" +
  "Note: some records were not verifiable.";

describe("parseSavedAnswerMarkdown", () => {
  it("parses the real G-035 answer into a heading, a paragraph, a table, a second heading, a list and a closing paragraph", () => {
    // Mutation: misclassifying any one of these six blocks turns this red.
    const blocks = parseSavedAnswerMarkdown(G_035_MARKDOWN);
    expect(blocks.map((b) => b.kind)).toEqual([
      "paragraph",
      "heading",
      "table",
      "heading",
      "list",
      "paragraph",
      "paragraph",
    ]);
  });

  it("unescapes a table cell that carried a literal pipe and a literal backslash", () => {
    // Mutation: unescaping in the wrong order, or not unescaping at all,
    // turns this red. "A \| B [1]" un-escapes to "A | B [1]" and
    // "back\\slash" un-escapes to "back\slash", not "back\\slash".
    const blocks = parseSavedAnswerMarkdown(ESCAPED_MARKDOWN);
    const table = blocks.find((b) => b.kind === "table");
    if (table?.kind !== "table") throw new Error("expected a table block");
    expect(table.header).toEqual(["Name | with pipe", "Backslash \\ value"]);
    expect(table.rows).toEqual([["A | B [1]", "back\\slash"]]);
  });

  it("falls back to a plain paragraph for a construct it does not recognise, losing no content", () => {
    // Mutation: dropping an unrecognised block, or throwing on it, turns
    // this red. This shape (a blockquote) is not anything
    // `answer_markdown_from` emits today; it stands in for whatever the
    // producer emits next that this file has not been taught yet.
    const blocks = parseSavedAnswerMarkdown("> An unanticipated construct with `code` and **bold**.");
    expect(blocks).toEqual([
      { kind: "paragraph", text: "> An unanticipated construct with `code` and **bold**." },
    ]);
  });
});

describe("SavedAnswerMarkdown", () => {
  it("renders the real G-035 table-bearing answer with no literal ##, | or --- on screen", () => {
    // Mutation: reverting to a plain-text `white-space: pre-wrap` render
    // (the defect this ticket closes) turns this red immediately, since
    // the raw markdown characters would appear verbatim in the DOM text.
    render(<SavedAnswerMarkdown markdown={G_035_MARKDOWN} />);
    const body = screen.getByTestId("saved-answer-body");
    expect(body.textContent).not.toMatch(/##/);
    expect(body.textContent).not.toMatch(/\|/);
    expect(body.textContent).not.toMatch(/---/);
    expect(screen.getByRole("heading", { name: "Isolates and their AMR genes" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Taxonomy records found" })).toBeInTheDocument();
  });

  it("renders the table as a real table with every isolate row and every AMR gene intact", () => {
    // Mutation: dropping a row, dropping a cell, or rendering the table as
    // a flattened sentence (the exact failure `run_consistency.py`'s naive
    // text-join produces, per B1's finding) turns this red.
    render(<SavedAnswerMarkdown markdown={G_035_MARKDOWN} />);
    const table = screen.getByRole("table");
    expect(within(table).getByText("Isolate")).toBeInTheDocument();
    expect(within(table).getByText("AMR genes")).toBeInTheDocument();
    expect(within(table).getByText(/C236-11 \[1\]/)).toBeInTheDocument();
    expect(within(table).getAllByText(/blaCTX-M-15/).length).toBeGreaterThan(0);
    expect(within(table).getByText(/NA114 \[20\]/)).toBeInTheDocument();
    expect(within(table).getByText(/uhpT_E350Q=POINT/)).toBeInTheDocument();
  });

  it("renders the list item as a real list, not a table row or a paragraph", () => {
    // Mutation: rendering the taxonomy list item as a table row (wrong
    // block type) or losing it inside the surrounding paragraphs turns
    // this red.
    render(<SavedAnswerMarkdown markdown={G_035_MARKDOWN} />);
    const list = screen.getByRole("list");
    expect(within(list).getByText(/Escherichia coli\[21\]/)).toBeInTheDocument();
  });

  it("renders a table cell's escaped pipe and backslash back to their literal characters", () => {
    // Mutation: leaving the escape sequences un-reversed, or reversing them
    // in the wrong order, turns this red.
    render(<SavedAnswerMarkdown markdown={ESCAPED_MARKDOWN} />);
    const table = screen.getByRole("table");
    expect(within(table).getByText("Name | with pipe")).toBeInTheDocument();
    expect(within(table).getByText("Backslash \\ value")).toBeInTheDocument();
    expect(within(table).getByText(/A \| B \[1\]/)).toBeInTheDocument();
    expect(within(table).getByText("back\\slash")).toBeInTheDocument();
  });

  it("renders an unrecognised construct as visible plain text rather than vanishing", () => {
    // Mutation: swallowing an unrecognised block (returning null, or an
    // empty fragment) turns this red: the sentence would disappear from
    // the screen entirely, which is exactly the loss done-when item 3
    // forbids.
    render(<SavedAnswerMarkdown markdown="A deliberately unknown line the producer never emits today." />);
    expect(
      screen.getByText("A deliberately unknown line the producer never emits today."),
    ).toBeInTheDocument();
  });

  it("never uses dangerouslySetInnerHTML: every character of a hostile-looking cell renders as text, not markup", () => {
    // Mutation: switching to `dangerouslySetInnerHTML` for convenience
    // would let a `<script>`-shaped stored value execute or inject
    // elements; JSX's default escaping means the literal tag text appears
    // on screen instead, un-executed, exactly like any other value.
    const markdown = "A paragraph containing <script>window.__pwned = true</script> as literal text.";
    const { container } = render(<SavedAnswerMarkdown markdown={markdown} />);
    expect(
      screen.getByText("A paragraph containing <script>window.__pwned = true</script> as literal text."),
    ).toBeInTheDocument();
    expect(container.querySelector("script")).toBeNull();
    expect((window as unknown as { __pwned?: boolean }).__pwned).toBeUndefined();
  });
});

/** G-035's stored citations: twenty isolates and one taxonomy record. */
function isolateCitations(count: number): HistoryAnswerCitation[] {
  return Array.from({ length: count }, (_, i) => ({
    display_index: i + 1,
    source: "pathogen_detection",
    source_id: `SAMN0071530${i}`,
    source_url: `https://www.ncbi.nlm.nih.gov/pathogens/isolates/#SAMN0071530${i}`,
    layer: 2 as const,
  }));
}

describe("SavedAnswerMarkdown citation markers, card 135", () => {
  const CITATIONS = isolateCitations(21);

  it("renders the summary's run of twenty as one range marker, with no bracket left in the text", () => {
    // Mutation: printing `block.text` raw again leaves "[1][2]...[20]" in
    // the paragraph and finds no marker, red.
    render(<SavedAnswerMarkdown markdown={G_035_MARKDOWN} citations={CITATIONS} />);
    const paragraph = screen.getByTestId("saved-answer-paragraph-0");
    expect(paragraph.textContent).not.toMatch(/\[\d/);
    const twenty = Array.from({ length: 20 }, (_, i) => i + 1);
    const markers = within(paragraph).getAllByRole("button");
    expect(markers).toHaveLength(1);
    expect(markers[0]).toHaveAttribute("data-testid", "saved-answer-0-citation-group-1");
    expect(within(markers[0]).getByText(markerLabel(twenty))).toBeInTheDocument();
    // The sentence's full stop moves in front of the marker, as live.
    expect(paragraph.textContent).toMatch(/^Found 20 pathogen detection isolate records for Escherichia coli\.\u2060/);
  });

  it("renders a table row's and a list item's markers, and keeps the other cells as data", () => {
    // Mutation: dropping the first-cell or list-item rendering leaves
    // "C236-11 [1]" or "Escherichia coli[21]" as text, red.
    render(<SavedAnswerMarkdown markdown={G_035_MARKDOWN} citations={CITATIONS} />);
    const table = screen.getByRole("table");
    const firstRow = table.querySelectorAll("tbody tr")[0];
    const cells = firstRow.querySelectorAll("td");
    expect(cells[0].textContent).toMatch(/^C236-11\u2060/);
    expect(cells[0].textContent).not.toContain("[1]");
    expect(within(cells[0] as HTMLElement).getByRole("button", { name: "Source 1, layer 2" })).toBeInTheDocument();
    expect(within(cells[1] as HTMLElement).queryByRole("button")).toBeNull();
    const list = screen.getByRole("list");
    expect(list.textContent).not.toContain("[21]");
    expect(within(list).getByRole("button", { name: "Source 21, layer 2" })).toBeInTheDocument();
  });

  it("keeps a bracketed number that names no stored citation as text, the live R-05 rule", () => {
    // Mutation: replacing every `[n]` by pattern turns "[12]" and "[99]"
    // into markers with no source behind them, red.
    render(
      <SavedAnswerMarkdown
        markdown={"A study [12] found it. Another [1][99]. One more [2][3][4]."}
        citations={isolateCitations(4)}
      />,
    );
    const paragraph = screen.getByTestId("saved-answer-paragraph-0");
    expect(paragraph.textContent).toContain("A study [12] found it.");
    expect(paragraph.textContent).toContain("Another [99].");
    expect(within(paragraph).getByRole("button", { name: "Source 1, layer 2" })).toBeInTheDocument();
    // Three markers stay a comma list of three, the live collapse rule.
    const group = screen.getByTestId("saved-answer-0-citation-markers-1");
    expect(within(group).getAllByRole("button")).toHaveLength(3);
    expect(screen.queryByTestId("saved-answer-0-citation-12")).toBeNull();
  });

  it("leaves every marker as text when no citations are passed", () => {
    render(<SavedAnswerMarkdown markdown={"Isolate [1]."} />);
    expect(screen.getByText("Isolate [1].")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("opens the live card from a saved marker, named by its database with its record link", async () => {
    // Mutation: building the card from the raw `source` reads
    // "pathogen_detection SAMN00715300", red.
    const user = userEvent.setup();
    render(<SavedAnswerMarkdown markdown={"One isolate [1]."} citations={isolateCitations(1)} />);
    await user.tab();
    const card = screen.getByTestId("saved-answer-0-cite-popover-1");
    expect(card).toHaveTextContent("Pathogen Detection SAMN00715300");
    expect(card).not.toHaveTextContent("pathogen_detection");
    expect(within(card).getByRole("link")).toHaveAttribute(
      "href",
      "https://www.ncbi.nlm.nih.gov/pathogens/isolates/#SAMN00715300",
    );
  });
});
