/**
 * A closed-vocabulary renderer for `answer_markdown` (fix-plan item 10.2,
 * defect one in the overnight run's findings file).
 *
 * WHY NOT A MARKDOWN LIBRARY: `answer_markdown` is produced by our own
 * code, `feedback/capture.py::answer_markdown_from`, never by a model and
 * never from arbitrary user or external text. Reading that function shows
 * it can only ever emit five constructs, each built from one `TokenPayload`
 * kind:
 *
 *   - a heading, `"## " + text` (`kind: "heading"`)
 *   - a plain paragraph, one or more `claim`/`note` tokens' text joined with
 *     no separator (`kind: "claim"`, `kind: "note"`, or no kind at all)
 *   - a table, a `| header | ... |` row, a `| --- | ... |` separator row,
 *     then one or more `| cell | ... |` rows (`kind: "table_header"` then
 *     `kind: "table_row"`)
 *   - a bulleted list item, `"- " + label + markers` (`kind: "list_item"`,
 *     or a `table_row` with no header before it)
 *
 * A general parser (remark, marked, or similar) would cover those five and
 * an unbounded number of constructs this producer can never emit: nested
 * lists, code fences, images, raw HTML, link syntax. Every one of those is
 * pure attack surface with zero payoff here, a new dependency needing the
 * `supply-chain-security` pre-install review, bundle weight, and a
 * `dangerouslySetInnerHTML`-shaped temptation to render HTML output.
 * `production-standards.md` forbids `dangerouslySetInnerHTML` outright, and
 * this module never uses it: every block below becomes React elements, so
 * JSX's default escaping is the actual control, not a sanitizer bolted on
 * after the fact.
 *
 * Table-cell escaping matches `feedback/capture.py::_cell` exactly, in
 * reverse: that function replaces a literal backslash with two, then a
 * literal pipe with a backslash-pipe. `unescapeCell` below undoes both in
 * one left-to-right pass, character by character, which is the only way to
 * invert an escape scheme correctly: two sequential `String.replace` calls
 * can each re-match text the other one just produced.
 *
 * ANYTHING THIS PARSER DOES NOT RECOGNISE FALLS BACK TO A PLAIN PARAGRAPH,
 * never dropped. `parseBlocks`'s default branch is exactly this: a raw
 * block that matches none of heading, table or list renders as its own
 * literal text. A person must never lose a word because a future producer
 * change emits a shape this file was not updated for.
 */

import { Fragment, type ReactElement } from "react";
import { Box, Typography } from "@mui/material";

import { designTokens } from "../../theme";

type Block =
  | { kind: "heading"; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "table"; header: string[]; rows: string[][] }
  | { kind: "list"; items: string[] };

const SEPARATOR_LINE = /^\|(?:\s*-+\s*\|)+$/;

/**
 * Undo `_cell`'s two-step escape (`\` -> `\\`, then `|` -> `\|`) in one
 * left-to-right pass. A backslash is only ever followed by another
 * backslash or a pipe in output `_cell` can produce, so those are the only
 * two escapes this ever has to reverse.
 */
function unescapeCell(raw: string): string {
  let out = "";
  for (let i = 0; i < raw.length; i += 1) {
    const ch = raw[i];
    if (ch === "\\" && i + 1 < raw.length && (raw[i + 1] === "\\" || raw[i + 1] === "|")) {
      out += raw[i + 1];
      i += 1;
      continue;
    }
    out += ch;
  }
  return out;
}

/**
 * Split one `| a | b |` line into its unescaped cells, respecting an
 * escaped `\|` inside a cell as content rather than a column delimiter.
 */
function splitTableRow(line: string): string[] {
  const trimmed = line.trim();
  const inner = trimmed.replace(/^\|/, "").replace(/\|$/, "");
  const cells: string[] = [];
  let current = "";
  for (let i = 0; i < inner.length; i += 1) {
    const ch = inner[i];
    if (ch === "\\" && i + 1 < inner.length) {
      current += ch + inner[i + 1];
      i += 1;
      continue;
    }
    if (ch === "|") {
      cells.push(unescapeCell(current.trim()));
      current = "";
      continue;
    }
    current += ch;
  }
  cells.push(unescapeCell(current.trim()));
  return cells;
}

/** One raw, blank-line-delimited chunk of `answer_markdown` into one `Block`. */
function parseRawBlock(raw: string): Block {
  if (raw.startsWith("## ")) {
    return { kind: "heading", text: raw.slice(3).trim() };
  }

  const lines = raw.split("\n");
  if (lines.length >= 2 && lines[0].trim().startsWith("|") && SEPARATOR_LINE.test(lines[1].trim())) {
    return {
      kind: "table",
      header: splitTableRow(lines[0]),
      rows: lines.slice(2).filter((line) => line.trim().length > 0).map(splitTableRow),
    };
  }

  if (lines.length > 0 && lines.every((line) => line.startsWith("- "))) {
    // List-item labels went through `_cell` too (`capture.py`'s
    // `list_item` and headerless-`table_row` branches both call it), so
    // the same unescape applies, even though a bullet carries no column
    // delimiter to protect.
    return { kind: "list", items: lines.map((line) => unescapeCell(line.slice(2))) };
  }

  // The fallback: an unrecognised construct is shown verbatim rather than
  // dropped. Never reached by anything `answer_markdown_from` emits today;
  // reached the moment a future change adds a sixth token kind this file
  // has not been taught yet.
  return { kind: "paragraph", text: raw };
}

/**
 * Consecutive single-item list blocks (`capture.py` flushes one block per
 * `list_item` token, never grouping them) collapse into one `<ul>`, so five
 * bullet points render as one list rather than five one-item lists.
 */
function groupConsecutiveLists(blocks: Block[]): Block[] {
  const grouped: Block[] = [];
  for (const block of blocks) {
    const previous = grouped[grouped.length - 1];
    if (block.kind === "list" && previous?.kind === "list") {
      previous.items.push(...block.items);
      continue;
    }
    grouped.push(block.kind === "list" ? { kind: "list", items: [...block.items] } : block);
  }
  return grouped;
}

export function parseSavedAnswerMarkdown(markdown: string): Block[] {
  const rawBlocks = markdown
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter((block) => block.length > 0);
  return groupConsecutiveLists(rawBlocks.map(parseRawBlock));
}

const SAM_HEADING_SX = {
  fontSize: 11,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  fontWeight: 700,
  color: designTokens.inkFaint,
  m: "22px 0 10px",
  pb: "6px",
  borderBottom: `1px solid ${designTokens.line}`,
  "&:first-of-type": { mt: 0 },
} as const;

const SAM_PARAGRAPH_SX = {
  m: "0 0 14px",
  fontSize: 14.5,
  lineHeight: 1.6,
  color: designTokens.ink,
  "&:last-child": { mb: 0 },
} as const;

const SAM_TABLE_SX = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 13,
  border: `1px solid ${designTokens.line}`,
  bgcolor: designTokens.surface,
  "& tbody tr:last-child td": { borderBottom: 0 },
} as const;

const SAM_TABLE_CELL_SX = {
  textAlign: "left",
  p: "6px 9px",
  borderBottom: `1px solid ${designTokens.line}`,
  verticalAlign: "top",
} as const;

const SAM_TABLE_HEAD_SX = {
  ...SAM_TABLE_CELL_SX,
  fontSize: 10.5,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: designTokens.inkFaint,
  bgcolor: designTokens.surfaceSunk,
  fontWeight: 700,
} as const;

const SAM_LIST_SX = { m: "0 0 14px", pl: "22px", "&:last-child": { mb: 0 } } as const;

const SAM_LIST_ITEM_SX = {
  fontSize: 14.5,
  lineHeight: 1.6,
  color: designTokens.ink,
  mb: "4px",
  "&:last-child": { mb: 0 },
} as const;

/**
 * `answer_markdown`, rendered as React elements. Never
 * `dangerouslySetInnerHTML`: every construct below is a typed React node,
 * so JSX's own escaping is the XSS control, exactly as
 * `production-standards.md` requires.
 */
export function SavedAnswerMarkdown({ markdown }: { markdown: string }): ReactElement {
  const blocks = parseSavedAnswerMarkdown(markdown);
  return (
    <Box data-testid="saved-answer-body">
      {blocks.map((block, index) => {
        if (block.kind === "heading") {
          return (
            <Typography key={index} component="h2" data-testid={`saved-answer-heading-${index}`} sx={SAM_HEADING_SX}>
              {block.text}
            </Typography>
          );
        }
        if (block.kind === "table") {
          return (
            <Box key={index} sx={{ overflowX: "auto", m: "0 0 16px" }}>
              <Box component="table" data-testid={`saved-answer-table-${index}`} sx={SAM_TABLE_SX}>
                {block.header.length > 0 ? (
                  <thead>
                    <tr>
                      {block.header.map((label, c) => (
                        <Box component="th" key={c} scope="col" sx={SAM_TABLE_HEAD_SX}>
                          {label}
                        </Box>
                      ))}
                    </tr>
                  </thead>
                ) : null}
                <tbody>
                  {block.rows.map((row, r) => (
                    <Fragment key={r}>
                      <Box component="tr">
                        {row.map((cell, c) => (
                          <Box component="td" key={c} sx={SAM_TABLE_CELL_SX}>
                            {cell}
                          </Box>
                        ))}
                      </Box>
                    </Fragment>
                  ))}
                </tbody>
              </Box>
            </Box>
          );
        }
        if (block.kind === "list") {
          return (
            <Box component="ul" key={index} data-testid={`saved-answer-list-${index}`} sx={SAM_LIST_SX}>
              {block.items.map((item, i) => (
                <Box component="li" key={i} sx={SAM_LIST_ITEM_SX}>
                  {item}
                </Box>
              ))}
            </Box>
          );
        }
        return (
          <Typography key={index} component="p" data-testid={`saved-answer-paragraph-${index}`} sx={SAM_PARAGRAPH_SX}>
            {block.text}
          </Typography>
        );
      })}
    </Box>
  );
}
