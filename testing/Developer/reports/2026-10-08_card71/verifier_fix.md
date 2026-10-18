# Card 71 fix round: fresh verifier

Independent check of the fix round at 27cd7742 (pull request #203) against the first verifier's V-71-03, V-71-04 and V-71-05. Findings are appended as they are established.

## Findings

### VF-71-01: on a phone the first column's name is still never shown, and a row with an empty first cell has no name and no label
- Severity: minor
- Regression: yes against develop's saved table on a phone (develop showed every column name, the first included, in the sideways-scrolling header); no against the live phone view, which also shows the first cell bare. Sits inside this round's V-71-04 fix.
- What: the phone branch labels only `row.slice(1)` (`frontend/src/components/screens/savedAnswerMarkdown.tsx` lines 269 to 281, `header[c + 1]`); the first cell renders bare at lines 263 to 268 (`{row[0] ?? ""}`), with no label and no dash when empty.
- Reproduction: own probe, matchMedia true, header "| Isolate | Genes | Link |", 12 rows. First item's text: "Iso-1 [1]Genes: g1Link: https://www.ncbi.nlm.nih.gov/pathogens/isolates/#PDT1". The word "Isolate" appears nowhere on the page. With "| Isolate | AMR genes | Country |" and the row "|  | blaKPC | USA |": item text "AMR genes: blaKPCCountry: USA", first span text "" (an empty line at the top of the item, no "Isolate: –").
- Why it matters: the brief's "each stacked saved row shows Column: value" holds for every column but the first. For a record-name column this is usually self-evident, so I rate it minor; a reader cannot tell what the first column was if its values are codes. The empty first cell case is the one place where a value vanishes without trace, which the fix's own dash rule was meant to stop. The card's test pins this exact text ("Iso-1 [1]AMR genes: –Country: USA"), so the omission is by design, not by accident.

### VF-71-02: a short row on a phone drops its missing columns silently, while an empty cell shows "Column: –"
- Severity: unsure (likely unreachable)
- Regression: no (develop's table also just rendered fewer cells)
- What: the label loop walks the row's cells, not the header (line 269), so a row with fewer cells than the header shows no label for the missing columns.
- Reproduction: own probe, matchMedia true, header of three columns and row "| Iso-2 | x |": item text "Iso-2AMR genes: x", no "Country" line. The row "| Iso-1 [1] |  | USA |" in the same table shows "AMR genes: –".
- Why it matters: little today. `capture.py` lines 205 to 223 write each row from the payload's own cells, so a short row needs `write_node` to send fewer cells than the header, which I did not see happen. Filed so the inconsistency is known.

### VF-71-03: the content key can collide for two different tables, so a different table can keep the old page
- Severity: unsure (latent; needs contrived content and an in-place swap the app does not do)
- Regression: no. Sits inside this round's V-71-03 fix.
- What: the key is `${index}:${header.join("␟")}:${rows...}` (`savedAnswerMarkdown.tsx` line 344). The plain colon between the header part and the rows part is not escaped, and colons are common in cells (HGVS names, chromosome positions). A header ending "X:a" with first cell "b" gives the same key as a header ending "X" with first cell "a:b".
- Reproduction: own probe, desktop. Table A "| H |" with 12 rows, the first "a:b"; Next; rerender with table B "| H:a |" with 12 rows, the first "b". Status after the rerender: "Showing 11–12 of 12" with header "H:a", so table B opened on page 2.
- What does not collide: two tables in one answer. The key starts with the block index, so table keys differ by position, and a heading or paragraph key (the bare index) never contains a colon. Own probe with two identical 12-row tables at blocks 1 and 2: paging table 1 left table 2 at "Showing 1–10 of 12", and React logged no duplicate-key error.
- Also by design, not a collision: an identical table at the same position in a different saved answer keeps its page (own probe, intro paragraph changed, table unchanged: "Showing 11–20 of 25" before and after). Through the app this cannot happen, because opening a saved answer passes through the loading state and unmounts the table (`App.tsx` rail handler, read only, as the first verifier recorded).
- Why it matters: practically nothing today. Filed because the fix's comment claims "a different table or answer opens on page 1", and that claim is not unconditional.

### VF-71-04: keying by content does not reset the page while a person is reading (no defect)
- Severity: none, a pass
- Reproduction: own probe, 25-row table on page 3 ("Showing 21–25 of 25"). Rerender with an equal markdown string built fresh: still page 3. Rerender with only the paragraph before the table changed: still page 3. Phone to desktop switch on page 2 (matchMedia flipped, rerender): stays "Showing 11–20 of 25", the element changes from UL to TABLE, so rotating a phone keeps the reader's place.
- Regression: no.

### VF-71-05: the new tests go red under each mutation the first verifier named, and under three more (no defect)
- Severity: none, a pass
- Regression: no
- Reproduction: one-line `sed` edits to `savedAnswerMarkdown.tsx`, each run against `savedAnswerMarkdown.card71.test.tsx` alone, each restored with `git checkout` and `git status` confirmed clean after.

| Mutation | Result | Test that caught it |
|---|---|---|
| `totalRows > RECORDS_PAGE_SIZE` to `>=` (line 228) | 1 of 7 red | shows no bar for exactly ten rows |
| `overflowWrap: "anywhere"` deleted on both stacked spans (lines 265, 275) | 1 of 7 red | lets long values wrap inside the stacked phone row |
| wrap deleted on the value span only (line 275) | 1 of 7 red | same |
| `key={contentKey}` back to `key={index}` (line 345) | 1 of 7 red | opens on page 1 when given a different table or answer |
| label prefix removed (line 277) | 1 of 7 red | labels each stacked value with its column name |
| `{cell \|\| "–"}` back to `{cell}` (line 278) | 1 of 7 red | same |

- Limit: the wrap test reads jsdom's computed `overflow-wrap`, so it proves the rule is present, not that a 390 px phone shows no sideways scroll. That still needs a real browser on deployed develop.

### VF-71-06: the live answer screen and the shared bar are untouched by the fix round (no defect)
- Severity: none, a pass
- Regression: no
- Reproduction: `git diff --quiet 5dec7134 HEAD -- frontend/src/components/screens/AnswerScreen.tsx frontend/src/components/answer/RecordsPaginationBar.tsx` exits 0. `git diff --name-only 5dec7134 HEAD` lists only the saved table, its card 71 test and three report files. The live screen's change against develop (the bar extracted into `RecordsPaginationBar.tsx`) is from the first round, where the first verifier's V-71-01 byte-compared the live markup against develop; I did not repeat that comparison.

## Tests run

| What | Files | Result |
|---|---|---|
| Saved answer suites | `savedAnswerMarkdown.card71`, `savedAnswerMarkdown`, `SavedAnswerScreen`, `SavedAnswerScreen.card102` | 4 files, 26 of 26 passed |
| Live paging and layout suites | `src/answerPagination`, `src/answerLayout` | 2 files, 18 of 18 passed |
| Own probe | throwaway test file, moved out of the worktree after each run | 8 probes, results in VF-71-01 to VF-71-04 |
| Mutations | six one-line edits, each restored | VF-71-05 |
| `npm run build` | frontend | exit 0; the existing over-500 kB chunk warning only |

`git status` shows only this report as untracked; `git diff` is empty.

## Compared with develop

- Desktop: the saved table looks as on develop (same header, cells and styles; own probe text "IsolateAMR genesCountryIso-1 [1]USA"), except that a table over ten rows now pages, which is the card's purpose. A side effect of paging, by design and shared with the live answer: printing or searching the page in the browser reaches only the ten rows on screen.
- Phone: better overall (no sideways scrolling, every value but the first labelled, empty cells marked), worse in one narrow way: the first column's name, shown in develop's header, is gone (VF-71-01).
- Citation markers: still part of the first cell's text and shown unchanged ("Iso-1 [1]"). Links: plain text in a cell, as on develop; no anchors on either (own probe, zero anchors).

## Verified by my own probes, against only read

- Probed: phone row text with labels and dashes; first column unlabelled; empty first cell; short row; desktop cell text; page held across an identical rerender, a changed paragraph and a phone to desktop switch; two tables in one answer paging independently with no key error; the colon key collision; identical table in a different answer; all six mutations; live files unchanged across the fix round (git); the build.
- Read only: that the app unmounts the table between two saved answers (`App.tsx` rail handler); that the producer never emits a short row (`capture.py` lines 205 to 223); that the live markup still matches develop (the first verifier's byte comparison, not repeated); width at 390 px in a real browser (not testable here).

## Verdict

MERGE WITH NAMED ITEMS.

The fix round does what it says: stacked values carry their column names, empty cells show a dash, a different table opens on page 1, the page holds while reading and across rotation, and the new tests are sensitive to every mutation tried. Named items:

- VF-71-01 (minor, regression against develop on a phone, inside this round's V-71-04 fix): the first column is still unlabelled, and an empty first cell leaves a blank line. Because it sits inside a fix made this phase, it meets the review loop's stop condition: the owner decides whether to accept it or have the first cell labelled too.
- VF-71-03 (unsure, latent, inside this round's V-71-03 fix): the content key can collide on an unescaped colon; not reachable through the app.
- VF-71-02 (unsure): a short row drops its missing columns silently.
- After merge, a 390 px check on deployed develop remains the only real proof of no sideways scroll.

Worse than develop: yes (narrowly: on a phone the first column's name is no longer shown, VF-71-01)
