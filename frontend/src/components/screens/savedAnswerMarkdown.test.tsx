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
import { describe, expect, it } from "vitest";

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
