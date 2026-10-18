# Cards 23 and 102 product review (pre-screen, develop)

Reviewer: product reviewer agent, 2026-10-07. Pre-screen only; nothing here closes an item.

## Target

- API `/health` at 06:20 UTC: `{"status":"ok","app_env":"develop"}`.
- Railway at 06:20 UTC: fde37ddf (PR #199) BUILDING on search-agent-web and search-agent-api; live was 055b639c (PR #198, card 23). Captures wait for fde37ddf to read SUCCESS on both.

## Findings

Progress note: at 06:21 UTC Railway reads fde37ddf SUCCESS on both search-agent-web and search-agent-api, and `/health` reads `app_env: develop`. Captures start now, signed in with one throwaway account (`card102-review+<timestamp>@example.com`), its password generated in the script and never written down.

### PR-card102-01: the reopened HNF1A answer says "Based on 61 sources cited" and lists 49 rows
- Kind: screen
- Verdict: fail
- What: "What diseases are caused by variants in the HNF1A gene?" at Researcher answered live with "61 sources cited from 3 layers", a SOURCES heading of 61 and "Based on 61 sources cited, not yet confirmed". After a reload, Your searches lists it as "49 sources cited · Oct 7". Reopened, the saved answer's trust line reads "Based on 61 sources cited, not yet confirmed" and the list under it holds 49 rows. Same at 1280 and 390. The BRCA1 saved answer agrees (21 in the line, 21 rows, gene 672 once as "5, 9."), so the rows render now; the count disagrees only on the larger answer.
- Evidence: `product_measurements.json`, `saved` entries `1280_saved_hnf1a` and `390_saved_hnf1a`: `"trust": "Based on 61 sources cited, not yet confirmed"`, `"rowCount": 49`; `railText` "49 sources cited · Oct 7"; live run `1280_hnf1a_researcher`: `"sourcesCount": "61"`. Screenshots `product_1280_saved_hnf1a.png`, `product_390_saved_hnf1a.png`, `product_1280_hnf1a_researcher.png`.
- Why a person would care: card 102's promise is that the rows match the "Based on N sources cited" line. A researcher reopening the HNF1A answer counts 49 sources under a line that says 61, and the search list beside it says 49. Twelve sources the live answer showed are not there to open.
- NOT CLOSED

PR-card102-01 addendum, where the two numbers come from (read from source, not measured on the server): the rail's count is `_citation_count` over the stored `interactions.citations` (`feedback/history.py`), so the stored list holds 49 distinct pages; the saved trust line is the stored `trust_line`, computed at answer time over the answer's grounded claims (`synthesis/trust.py`, 61). So the saved citations are a smaller set than the claims the line counted, for this answer. I did not probe the API reply to see which 12 pages are missing. NOT CLOSED.

### PR-card102-02: on a phone the reopened BRCA1 answer's tables are cut off at the screen edge
- Kind: screen
- Verdict: needs your eye
- What: at 390 the page itself no longer scrolls sideways (overflow 0, was 33 px on 2026-10-07 for card 22), but the saved answer's tables still run past the screen: `saved-answer-table-9` ends at 524 px on a 390 px screen. In the screenshot the Clinical trial table's Status column reads "COMPLETE" and "TERMINATE", cut mid-word, and the ClinVar variant names run off the right edge. I did not test whether the table scrolls sideways under a finger.
- Evidence: `product_390_saved_brca1.png` (Clinical trial and ClinVar tables); `product_measurements.json`, `390_saved_brca1`: `"overflow": 0`, `"wide": ["saved-answer-table-9 right=524"]`.
- Why a person would care: they read "COMPLETE" or half an identifier with nothing telling them there is more to the right. Not card 102's change (it changed the source rows, which wrap cleanly), and the saved answer has no design to judge against.
- NOT CLOSED

PR-card102-01 second addendum, measured: the saved HNF1A list holds every citation numbered 1 to 50 (gene 6927 once as "45, 49.") and none above 50. The live answer's own tables cite up to 62: PubMed 51, 54, 57, 60; ClinVar 52, 55, 58, 61; trials 53, 56, 59, 62 (`product_1280_hnf1a_researcher.png`). The backend keeps at most 50 citations when it stores a run (`feedback/capture.py` `_MAX_CITATIONS = 50`, `adapters/web_sse/app.py` `citations=citations[:50]`), so any answer with more than 50 citations reopens with fewer rows than its line names. This predates card 102; card 102 made the rows visible, which is what exposed it. NOT CLOSED.

### PR-card23-01: the line says each row lists conditions, and five rows on the first page list none
- Kind: answer
- Verdict: needs your eye
- What: on page 1 of the HNF1A "Variant-to-disease mapping" table at Researcher, the rows ClinVar:1048822, 1051750, 1098821, 1104934 and 1105252 have an empty "Associated disease(s)" cell. The line under the table reads "Each row lists the conditions the variant's ClinVar record names". The Notes list says "39 variant links to ClinVar placeholder conditions ('not provided', 'not specified' or 'see cases') are not listed.", which is probably why those cells are blank, but that note sits far below in Notes, not by the table.
- Evidence: `product_1280_hnf1a_researcher.png` (the table, rows 6 to 10 of page 1); notes text in `product_measurements.json`, `1280_hnf1a_researcher`.
- Why a person would care: the sentence directly under the table promises conditions on every row, and half the rows they just read have an empty disease column with no word on why.
- NOT CLOSED

### PR-card23-02: the line is in place, but below the table where the design puts its source line above
- Kind: screen
- Verdict: needs your eye
- What: develop shows the line directly under the table's "Showing 1–10 of 38 / Page 1 of 4" bar, 16 px below it at both widths, as its own paragraph in muted 13.5 px text, before "Gene records found", and not in the Notes list. The prototype's only results table (rs334, "Genotype to phenotype") carries its source line as a caption ABOVE the table ("Genotype to phenotype, as recorded in the curated sources", caption top 690 px, header top 716 px at 1280). Query 79 asks for "directly under that table", so develop follows the owner's written check; I note the difference from the design only so it is a decision, not drift.
- Evidence: `product_1280_hnf1a_researcher.png`, `product_390_hnf1a_researcher.png`; `product_measurements.json` `"linePrevTestId": "answer-records-1-pagination"`, `"lineGapPx": 16`, `"lineInNotes": false`; `product_prototype_answer_1280.png`, `product_prototype_answer_390.png`.
- Why a person would care: little; the line reads well where it is. It is the owner's call whether the design or query 79 is the reference.
- NOT CLOSED

### PR-card23-03: the Researcher HNF1A answer is a record list with no written summary, and its trust line differs from Plain language
- Kind: answer
- Verdict: needs your eye
- What: at Researcher the answer opens "Found 38 sequence variant records for HNF1A, linked to 6 diseases: ..." and the Notes say "Note: no written summary could be checked against the records, so the records found are listed below with their sources". It ends "Based on 61 sources cited, not yet confirmed". The same question at Plain language, same 61 sources, ends "Based on 61 sources cited" with no "not yet confirmed", and the meta line reads "✓ Answered" where Researcher reads "? Answered".
- Evidence: `product_1280_hnf1a_researcher.png`, `product_390_hnf1a_researcher.png`, `product_390_hnf1a_plain.png`; `product_measurements.json` `trust` and `meta` for the three runs.
- Why a person would care: rubric line 1 and 2: the first sentence lists what was found rather than saying which diseases HNF1A variants cause, and the deeper mode is the one marked less certain. Not card 23's change.
- NOT CLOSED

### PR-card23-04: every answer took about 31 to 36 seconds on screen
- Kind: answer
- Verdict: needs your eye
- What: four runs. The meta line read 14.8 s, 24.9 s, 18.8 s and 16.6 s; from the click to the trust line appearing the same runs took 32.5, 36.0, 33.0 and 31.5 s. Over 25 s on the meta line: none (BRCA1 at 24.9 s is closest).
- Evidence: `product_measurements.json` (`secs`, `meta`).
- Why a person would care: the owner's bar is 20 seconds; the wait a person sits through is 30 or more every time. Same reading as card 22's review; no before number, so not a regression claim.
- NOT CLOSED

### PR-card102-03: the saved answer screen and the history rail have no design
- Kind: missing design
- Verdict: needs your eye
- What: `docs/build/design/README.md`'s coverage table has no row for a saved answer, and lists "History rail and its collapsed strip" as NO. Judged for counts, wrapping and overflow only.
- Evidence: `product_1280_saved_brca1.png`, `product_390_saved_brca1.png`, `product_1280_saved_hnf1a.png`, `product_390_saved_hnf1a.png`.
- Why a person would care: no one has said what the reopened answer should look like on a phone.
- NOT CLOSED

PR-card102-02 addendum: the reopened HNF1A answer at 390 has three more tables past the screen edge (`saved-answer-table-4` right=517, `-11` right=396, `-15` right=457), page overflow still 0. NOT CLOSED.

## What the two cards asked, and what develop shows

| Check | 1280 | 390 |
|---|---|---|
| Card 23: line under "Variant-to-disease mapping" (HNF1A, Researcher) | Directly under the table's page bar, 16 px, before "Gene records found" | Same, 16 px, before "Gene records found" |
| Card 23: line in the Notes list | No | No |
| Card 23: line shown once | Yes (`answer-inline-note-0` only) | Yes |
| Card 23: Plain language (no table) | not run | No table, no line |
| Card 23: table ends the answer | Not seen live: HNF1A puts five more record tables after it | Same |
| Card 102: BRCA1 saved, line vs rows | "Based on 21 sources cited, not yet confirmed", 21 rows, gene 672 once ("5, 9.") | Same |
| Card 102: HNF1A saved, line vs rows | "Based on 61 sources cited, not yet confirmed", 49 rows (PR-card102-01) | Same |
| Card 102: links inside their rows | 0 spill | 0 spill, links wrap |
| Horizontal page overflow | 0 on every screen | 0 on every develop screen; prototype rs334 answer 322 px |

## Report

1. Golden result: not run. The brief named no accounts file and no floor. Card 23 changes `synthesis/answer_layout.py` and `core/graph.py`, an answer-path change by `Product_review.md`'s definition (it adds a line to the answer), so the golden run is owed and was not measured here: answered against the floor, answered well of the fixed ten, questions that got worse, all unmeasured. Time to answer, my four runs only: meta line 14.8, 16.6, 18.8, 24.9 s (median about 17.7 s, worst 24.9 s, none over 25 s); click to trust line 31.5 to 36.0 s.
2. Look at first: fail PR-card102-01 (HNF1A reopened: line says 61, 49 rows; stored citations capped at 50). Then needs your eye: PR-card23-01 (blank disease cells under "Each row lists the conditions"), PR-card102-02 (saved tables cut at the phone's edge), PR-card23-03 (Researcher answer is a record list; trust differs by depth), PR-card23-04 (31 to 36 s on screen), PR-card23-02 (line below the table, design caption above), PR-card102-03 (no design for saved answer or rail).
3. Overflow at 390: no develop screen scrolls sideways (0 everywhere). Tables wider than the screen inside the saved answer: PR-card102-02. The prototype's own answer overflows 322 px at 390. No design: the saved answer screen and the history rail.
4. Not captured: the golden run (above); the card 23 case where the variant table ends the answer, since the live HNF1A answer always has more tables after it (the build's stubbed spec covers it, I did not see it live); Plain language at 1280; whether the cut-off saved tables scroll under a finger; the API reply for the HNF1A saved answer (the 50 cap is read from source and matches the measured 1 to 50 numbering). One throwaway account at example.com was created on develop (`card102-review+<timestamp>@example.com`), four searches; its password was generated in the script and never stored.

What I read myself: every screenshot named above (full page 1280 HNF1A, 390 HNF1A at reduced scale, 390 saved BRCA1 and a crop of its tables, a crop of the 1280 saved HNF1A rows, the prototype at 1280), and `product_measurements.json`. The line's position at 390 rests on the DOM measurement more than on the reduced 390 screenshot. The 50-citation cap rests on reading the source, not on a server probe. Full-page screenshots draw the fixed footer part way down the page; that is the capture method, not a defect.
