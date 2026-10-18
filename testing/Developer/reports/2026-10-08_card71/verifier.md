# Card 71 verifier report

Fresh verifier for pull request 203, branch fix/card71-reopened-matches-live, against develop. Findings are appended as they are established.

## Findings

### V-71-01: the live answer's paging bar is byte-identical to develop (no defect)
- Severity: none, a pass recorded for the record
- Claim checked: the bar moved to `frontend/src/components/answer/RecordsPaginationBar.tsx` (lines 14 to 86) with the same markup, test ids, text and behaviour; `AnswerScreen.tsx` now calls it at lines 1314 to 1322.
- Reproduction: a throwaway probe rendered the live `AnswerScreen` through `useRunView` for 12 and 21 rows, desktop and phone (matchMedia mocked), captured the bar on page 1, clicked Next, captured the bar and the whole records block on page 2, plus every emotion style rule in the document. Run once on the branch, then once with develop's `AnswerScreen.tsx` swapped in (restored with `git checkout` immediately after). The two 32,577-byte captures are identical by `cmp`, including class hashes and CSS. The captures contain the four test ids eight times each and "Showing 11–12 of 12", "Showing 11–20 of 21", so they are not empty.
- Regression: no.

### V-71-02: saved table paging is correct at 10, 11, 20 and 21 rows, desktop and phone (no defect)
- Severity: none, a pass recorded for the record
- Claim checked: `SavedTable` in `frontend/src/components/screens/savedAnswerMarkdown.tsx` lines 223 to 241 (slice and bar).
- Reproduction: own probe, both with matchMedia false and true. 10 rows: 10 rows shown, no pagination element. 11 rows: "Showing 1–10 of 11", Previous disabled; Next gives one row "Iso-11 [11]", "Showing 11–11 of 11", "Page 2 of 2", Next disabled; Previous returns row "Iso-1 [1]". 20 rows: page 2 is "Showing 11–20 of 20", 10 rows, Next disabled, last row carries "Iso-20 [20]" and its full link text. 21 rows: "Page 1 of 3", two Nexts give one row and "Showing 21–21 of 21"; a click on the disabled Next changes nothing. Two 12-row tables in one saved answer page independently (table 1 at "Showing 11–12 of 12", table 3 still "Showing 1–10 of 12"). 13 of 13 probe tests passed.
- Citation markers: the producer (`src/system_03_search_agent/feedback/capture.py` lines 218 to 221) puts the `[n]` markers as plain text on the first cell, so they are part of the row string and survive both paging and stacking; the probe saw "[11]", "[20]" and "[21]" on later pages. A cell link is plain text, never an anchor, exactly as on develop (develop also rendered `{cell}` as a string), so there is no link to lose.
- Non-record tables: `answer_markdown_from` has one table path (`table_header` then `table_row`, capture.py lines 199 to 222), so every saved table is a record table; there is no other table kind to break.
- Regression: no.

### V-71-03: a saved table keeps its page number if a different saved answer reaches it without the loading state in between
- Severity: minor (latent; not reachable through the app's only open path today)
- What: `SavedTable` holds `page` in `useState` keyed only by the block index (`savedAnswerMarkdown.tsx` line 226, mounted at line 341 with `key={index}`), and nothing resets it when the markdown changes. The live screen resets explicitly on a new question (`AnswerScreen.tsx` lines 1281 to 1284); the saved table relies on being unmounted.
- Reproduction: own probe. `SavedAnswerMarkdown` rendered with a 25-row table, Next twice, then rerendered with a different 25-row markdown: status reads "Showing 21–25 of 25" for the new answer. `SavedAnswerScreen` with answer A, Next once, rerendered straight to answer B: "Showing 11–20 of 25". Rerendered through `loading={true} answer={null}` first, then answer C: "Showing 1–10 of 25".
- Why it is not reachable today (read, not run end to end): the rail's open handler (`frontend/src/App.tsx` lines 2024 to 2028) sets the saved answer to null and loading to true in the same batched update before fetching, so `SavedAnswerScreen` renders the loading line and the table unmounts. The only other writer of the saved answer is the fetch result at line 2032. Any future path that swaps the answer in place (for example a prefetch or cache) would open the next answer on a later page with no sign it was paged.
- Why it matters: a reader opening a second saved answer would start on page 2 or 3 of it. The brief's "page resets when a different saved answer opens" holds only through App's current sequencing, not through the component.
- Regression: no (new code; develop had no paging to carry over).

### V-71-04: on a phone a stacked saved table drops its column names, and an empty cell leaves no gap, so a value's column is unlabelled
- Severity: minor (unsure whether the owner wants this; it matches the live phone view, and the diagnosis proposed something else)
- What: the phone branch of `SavedTable` (`savedAnswerMarkdown.tsx` lines 241 to 286) never renders `header`, and it skips empty cells (`cell ? ... : null`, line 270). The diagnosis's stated fix for item 5 was "a short stack of label: value"; the build copied the live phone layout instead, which also has no labels (`AnswerScreen.tsx` lines 1369 to 1384).
- Reproduction: own probe at matchMedia true with "| Isolate | AMR genes | Country |" and rows "| Iso-1 [1] |  | USA |", "| Iso-2 [2] | blaKPC | |". Whole page text: "Iso-1 [1]USAIso-2 [2]blaKPC"; "AMR genes" appears nowhere. At matchMedia false the header is present.
- Why it matters: on develop a phone reader of a saved table saw the column names (in a sideways-scrolling table). Now they see "USA" under one isolate and "blaKPC" under the next with nothing saying which is a country and which a gene. For self-describing values this is fine; for numeric or coded columns (counts, dates, accession types) it is ambiguous. It is the same trade the live phone view already makes, so the two screens do match, which was the card's goal.
- Regression: yes, relative to develop's saved table on a phone (the column names were visible there); no, relative to the live answer.

### V-71-05: the new tests catch a removed slice and a removed stacking branch, but not the exact ten-row boundary or the wrapping rule
- Severity: minor (test gap, the shipped code is correct)
- Reproduction, each a one-line local edit to `savedAnswerMarkdown.tsx`, run against `savedAnswerMarkdown.card71.test.tsx` only, then restored with `git checkout` and `git diff` confirmed empty:
  - `const visibleRows = isPaginated` changed to `const visibleRows = false` (every row shown): 2 of 3 red (the 20-row paging test and the phone test). Caught.
  - `if (phone) {` changed to `if (false) {` (no stacking): 1 of 3 red (the phone test). Caught.
  - `totalRows > RECORDS_PAGE_SIZE` changed to `>=` (a 10-row table gets a bar): 3 of 3 green. Not caught, because the "no bar" test uses a one-row table. My own 10-row probe went red on it, desktop and phone.
  - The `overflowWrap: "anywhere"` rule on the stacked cells (lines 260 and 268) is asserted by no test in the pull request; deleting it would leave all three green. My probe read the computed style: all 20 stacked spans report `anywhere`.
- Why it matters: the boundary the product owner asked for ("more than ten rows pages") and the property card 71 exists for (nothing past the phone's edge) can both regress with the card's own tests green.
- Regression: no.

### V-71-06: at phone width nothing in a stacked saved table can force the page wider, as far as jsdom can tell (no defect)
- Severity: none, a pass with a named limit
- Reproduction: own probe at matchMedia true with a 12-row table whose second column is a 90-character unbroken link. No `table` element is rendered; every one of the 20 stacked cell spans has computed `overflow-wrap: anywhere`; the pagination bar has `flex-wrap: wrap`; no element in the document has a pixel `width` or `min-width` or `white-space: nowrap`.
- What jsdom cannot show: jsdom does no layout, so it cannot measure that the rendered page is no wider than 390 px, that a long unbroken link actually breaks, or that the surrounding saved screen (unchanged by this pull request) leaves enough room. Only a real browser on deployed develop at 390 px can confirm: no sideways scroll on a reopened answer with a 20-row table, the long identifiers and links breaking inside the screen, the bar's "‹ Previous Page 1 of 2 Next ›" fitting on one line or wrapping cleanly, and the stack switching at 720 px exactly like the live answer (both read `PHONE_LAYOUT_QUERY`, `AnswerScreen.tsx` line 200).
- Regression: no.

## Tests run

| What | Files | Result |
|---|---|---|
| Live and saved suites named in the brief | `answerPagination`, `answerLayout`, `answerBold`, `savedAnswerMarkdown.card71`, `savedAnswerMarkdown`, `SavedAnswerScreen`, `SavedAnswerScreen.card102` | 7 files, 45 of 45 passed |
| Further live screen suites | `AnswerScreen.card22`, `AnswerScreen.previousTurnBody`, `AnswerScreen.thread` | 3 files, 36 of 36 passed |
| Own probe, live markup develop against branch | throwaway, removed from the worktree | identical captures (V-71-01) |
| Own probe, saved edges, reset, phone | throwaway, removed from the worktree | 14 tests written; 14 pass on the branch, findings V-71-02 to V-71-06 |
| Mutations | three one-line edits, each restored | V-71-05 |
| `npm run build` (`tsc -b && vite build`) | frontend | exit 0; the existing over-500 kB chunk warning only |

The worktree was left with `git diff` empty; the only untracked file is this report.

## Verified by my own probes, against only read

- Probed: live bar unchanged (byte comparison against develop); saved paging at 10, 11, 20, 21 rows on desktop and phone; markers surviving paging and stacking; two tables paging independently; page carry-over at component level; phone stack has no table, wraps cells, drops headers; the card's tests' sensitivity to three mutations; the build.
- Read only: that the app's rail handler unmounts the table between two saved answers (`App.tsx` lines 2024 to 2033); that `answer_markdown` has a single table kind (`capture.py` lines 199 to 222); real-browser width at 390 px (not testable here).

## Verdict

MERGE WITH NAMED ITEMS.

The reader's change works: a reopened table pages ten at a time with the live bar, the live screen is byte-for-byte unchanged, and at phone width the saved table stacks with wrapping cells. Nothing found makes a reopened answer wrong. The named items all sit inside this pull request's own new code, which is the card 71 fix itself:

- V-71-04 (minor, a regression against develop on a phone): column names vanish from a stacked saved table. It matches the live phone view, which was the card's aim, but it departs from the diagnosis's "label: value" proposal. The owner should know the trade.
- V-71-05 (minor): the card's tests do not pin the ten-row boundary or the wrapping rule.
- V-71-03 (minor, latent): the saved table's page resets only because App unmounts it; the component does not reset itself as the live screen does.
- After merge, the lead's product check at 390 px on deployed develop is the only confirmation of V-71-06's layout claims.
