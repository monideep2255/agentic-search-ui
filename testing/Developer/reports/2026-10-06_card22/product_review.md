# Card 22 product review (pre-screen, develop)

Reviewer: product reviewer agent, 2026-10-07. Pre-screen only; nothing here closes an item.

## Target

- API `/health` at 04:27 UTC: `{"status":"ok","app_env":"develop"}`.
- Railway at 04:27 UTC: d94604fb (PR #197) BUILDING on search-agent-web and search-agent-api; live was 5301cc6e. Captures wait for d94604fb to read SUCCESS.

## Findings

Progress note: at 04:32 UTC Railway reads d94604fb SUCCESS on both search-agent-web and search-agent-api; `/health` reads `app_env: develop`. Captures start now. The history rail and the saved answer need a signed-in account (`App.tsx` `railAvailable = signedIn && ...`), and no accounts file was named, so the capture signs up one throwaway test account at example.com, as live journey 8 does; its password is generated in the script and never written down.

### PR-card22-01: the reopened saved BRCA1 answer scrolls sideways on a phone
- Kind: screen
- Verdict: fail
- What: at 390 wide, the saved answer for "Which diseases are associated with BRCA1?" (opened from Your searches) is 33 px wider than the screen. The element past the edge is the answer's table, `saved-answer-table-12`, whose right edge measures 524 px against a 390 px viewport. The live answer screen of the same question at 390 measures 0.
- Evidence: `product_390_saved_q107.png`; `product_measurements.json` entry for that shot: `"overflow": 33`, `"wide": ["saved-answer-table-12 right=524", ...]`. Live answer at 390: `product_390_q107_researcher.png`, `"overflow": 0`.
- Why a person would care: on a phone the reopened answer slides left and right under their thumb, and the table's last column is cut off at the edge. Not introduced by card 22 as far as I can tell (the table is the saved answer's markdown, not a count), but it is on the screen card 22 changed.
- NOT CLOSED

### PR-card22-02: a reopened saved answer shows no source rows at all under "Based on N sources cited"
- Kind: screen
- Verdict: fail
- What: query 107 says "Open it: the saved answer lists S source rows under its 'Based on S sources cited' line, the gene page once." On deployed develop the reopened saved answer ends with the trust line and then "+ New search". There is no Sources heading and no rows, at either width. The saved trust line itself agrees with the live answer (17 for the gene question, 21 for query 107). `SavedAnswerScreen.tsx` renders the Sources list only when `answer.citations.length > 0`, so the reopened answer reached the screen with no citations, or the list failed to render; I did not see which (see PR-card22-03's evidence if appended).
- Evidence: `product_1280_saved_2.png` (gene question, 1280: last lines "Based on 17 sources cited" then "+ New search"); `product_390_saved_q107.png` (query 107, 390: "Based on 21 sources cited, not yet confirmed" then "+ New search"). `product_measurements.json`: `"savedRows": []` for both.
- Why a person would care: they reopen yesterday's answer, read "Based on 21 sources cited" and find nothing to open or count. The card's own promise, one row per page under that line, cannot be checked by the reader, and the saved answer is the one place a researcher goes back to for the references.
- NOT CLOSED

### PR-card22-03: the BRCA1 gene record is listed twice in the answer's own record tables, though Sources shows it once
- Kind: answer
- Verdict: needs your eye
- What: in query 107 at Researcher, "Gene records found" has two rows "BRCA1 NCBIGene:672" (citations 8 and 12), while Sources shows one card "[5][8][12] gene 672". The gene question's saved answer has "BRCA1 DNA repair associated [2] NCBIGene:672" and "BRCA1 [3] NCBIGene:672". The 390 saved query 107 answer shows "BRCA1 [11]" and "BRCA1 [14]", both NCBIGene:672.
- Evidence: `product_1280_q107_researcher.png` (Gene records found table); `product_1280_saved_2.png`; `product_390_saved_q107.png`; card text in `product_measurements.json`: "[5][8][12]gene 672".
- Why a person would care: the sources count now says one page, and the table above it still names that one gene twice, so "one record per page" holds in the sources and not in the answer they read. Query 107's own words: "The opening line counts one record per page"; the opening line does ("Found 4 disease records"), the table does not.
- NOT CLOSED

PR-card22-02 addendum, the cause, measured: two further test-account runs of "What does the BRCA1 gene do?" captured the deployed `GET /v1/history/{trace_id}/answer` reply. It carries 19 citations over 17 distinct links and `trust_line` "Based on 17 sources cited", so the server has the sources. Every citation's `layer` is a string, `"layer_1_graph"`, `"layer_2_api"` or `"layer_3_enrichment"`. The web client's `isHistoryAnswerCitation` (`frontend/src/lib/api.ts:516-524`) keeps only a citation whose `layer` is the number 1, 2 or 3, so 0 of 19 pass, `citations` arrives empty, and the Sources list never renders. Evidence: `product_saved_api_probe2.json` (`"citations":19`, `"passValidator":0`, the three layer types), `product_1280_saved_gene_probe2.png`. `frontend/src/lib/api.ts` is not in PR #197's diff, so this predates card 22 by all appearances, but it means card 22's one-row-per-page saved list has never been visible on develop, and its unit tests (numeric layers) cannot see it. NOT CLOSED.

### PR-card22-04: the Sources group badges add up to one more than the Sources total when a page is cited from two layers
- Kind: screen
- Verdict: needs your eye
- What: "What does the BRCA1 gene do?" reads Sources 17, and its groups read Knowledge graph 1, Live NCBI APIs 12, Enrichment 5, which add to 18. The Live NCBI APIs 12 counts eleven live-only cards plus the line "[1][3] NCBIGene 672: one card for this page, listed under Knowledge graph". Same at 1280 and 390.
- Evidence: `product_two_layer_measurements.json` (`"count":"17"`, `"groupCounts":["sources-group-1-count=1","sources-group-2-count=12","sources-group-3-count=5"]`); `product_390_gene_sources_expanded.png`, `product_1280_gene_sources_expanded.png`; the earlier run's card list in `product_measurements.json` has 11 L2-only cards under that group.
- Why a person would care: card 22's whole promise is "every total agrees". A reader who adds the three badges gets 18 under a heading of 17. Query 107 asks only that the Live group "still shows and names it", so this may be the intended reading; it is the owner's call.
- NOT CLOSED

### PR-card22-05: the BRCA1 disease answer says its list of four diseases twice in a row
- Kind: answer
- Verdict: needs your eye
- What: the opening line "Found 4 disease records for BRCA1: Familial cancer of breast, Familial breast-ovarian cancer susceptibility 1, Pancreatic cancer susceptibility 4 and Fanconi anemia complementation group S." is followed at once by "BRCA1 is associated with familial cancer of breast, familial breast-ovarian cancer susceptibility 1, pancreatic cancer susceptibility 4, and Fanconi anemia complementation group S." (1280) and "BRCA1 is associated with four diseases: Familial cancer of breast, ..." (390). The gene answer's first sentence, "Found 1 gene record for BRCA1: BRCA1 DNA repair associated.", lists what was found rather than saying what the gene does (rubric line 1), and its Gene records table then shows two rows for that one record.
- Evidence: `product_1280_q107_researcher.png`, `product_390_q107_researcher.png` (top), `product_1280_gene_researcher.png`.
- Why a person would care: the first thing they read is the same list twice, and the gene question opens with a record count instead of an answer. Card 22 touched the restatement gate (`answer_layout.py`), so this is worth a look beside it; I cannot say whether it is new.
- NOT CLOSED

### PR-card22-06: every answer took longer than 20 seconds to finish on screen
- Kind: answer
- Verdict: needs your eye
- What: seven live runs. The meta line's own time read 29.8 s, 22.1 s, 17.1 s, 13.0 s, 22.5 s, 20.0 s and 18.6 s. Measured from the click to the trust line appearing, in one-second polls, the same runs took 32.1, 33.1, 31.1, 30.1, 32.2, 30.2 and 30.1 s. Over 25 s on the meta line: query 107 at Researcher, 1280 (29.8 s).
- Evidence: `product_measurements.json` (`"secs"` and `"metas"`), `product_saved_api_probe.json`, `product_saved_api_probe2.json`, `product_two_layer_measurements.json`.
- Why a person would care: the owner's standing bar is every answer within 20 seconds; on screen the wait was about 30 seconds every time. Card 22 is not a speed change, and I have no before number, so this is a reading, not a regression claim.
- NOT CLOSED

### PR-card22-07: before a reload Your searches shows a repeated question once; after a reload it shows each run
- Kind: screen
- Verdict: needs your eye
- What: after asking query 107 at Researcher then at Plain language, the rail listed it once ("13 tool calls · 21 sources cited from 2 layers"). After the reload it listed it twice ("21 sources cited · Oct 7" each). At 390 with a third run, two rows before the reload, four after. The prototype also folds repeats (`app.html` `start()`: `st.history.filter(x => x.key !== item.key)`), so the before state matches the design; the after state does not. The count S itself is the same before and after on every row (21 and 17).
- Evidence: `product_1280_q107_plain.png` / `product_1280_after_reload.png`; `product_390_rail_open.png` / `product_390_rail_after_reload.png`; `"rail"` arrays in `product_measurements.json`. The history rail has no design card (`docs/build/design/README.md` coverage table, "History rail and its collapsed strip: NO"), so the prototype is the only reference.
- Why a person would care: the list of their searches changes length when they reload. Not card 22's change; noted because query 107 asks for the rail before and after a reload.
- NOT CLOSED

### PR-card22-08: the saved answer screen has no design
- Kind: missing design
- Verdict: needs your eye
- What: `docs/build/design/README.md`'s coverage table has no row for a saved-answer view; `SavedAnswerScreen.tsx`'s own header says "NO DESIGN EXISTS FOR THIS SCREEN". Card 22 changed its rows. Judged only for agreement of totals and overflow, never against an invented look. The history rail is likewise "NO" in the table.
- Evidence: `product_1280_saved_2.png`, `product_390_saved_q107.png`.
- Why a person would care: no one has said what this screen should look like at 390, which is where it overflows (PR-card22-01).
- NOT CLOSED

## What query 107 asked, and what develop shows

| Check | Researcher, 1280 | Plain language, 1280 | Researcher, 390 | Gene question, 1280 and 390 |
|---|---|---|---|---|
| Line under the question | "13 tool calls · 21 sources cited from 2 layers" | same, 21, 2 layers | same, 21, 2 layers | "13 tool calls · 17 sources cited from 3 layers" |
| Sources heading | 21 | 21 | 21 | 17 |
| Source cards counted | 21 | 21 | 21 | 17 |
| Trust line | "Based on 21 sources cited, not yet confirmed" | same | same | "Based on 17 sources cited" |
| Gene 672 page | one card "[5][8][12] gene 672" | one card "[1][6][10]" | one card "[5][11][14]" | one card "[1][2][3] NCBIGene 672", "L1 · graph, L2 · live", Live group names it |
| Rail before reload | "13 tool calls · 21 sources cited from 2 layers" | same | same | "13 tool calls · 17 sources cited from 3 layers" |
| Rail after reload | "21 sources cited · Oct 7" | same | same | "17 sources cited · Oct 7" |
| Saved answer trust line | "Based on 21 sources cited, not yet confirmed" (390) | not opened | as left | "Based on 17 sources cited" (1280) |
| Saved answer rows | none shown (PR-card22-02) | not opened | none shown | none shown; API sends 19 citations over 17 links |
| Horizontal overflow | 0 | 0 | 0 live, 33 saved | 0 at both widths |

Every number that says "sources" agrees on the live answer and the rail, before and after reload. The opening line counts records ("Found 4 disease records", "I found 4 conditions related to BRCA1"). No answer was confirmed, so "Confirmed by N independent databases" was never on screen.

Design comparison: `product_prototype_answer_1280.png` and `product_prototype_answer_390.png` beside the develop answers. The meta line sits under the question, Sources sits under the answer and the trust line under Sources, in the prototype's order at both widths; the meta line wraps to two lines at 390 without clipping (`product_390_q107_researcher.png`). The wording differs from the prototype ("3 tools · 3 layers · 3 sources") by card 22's intent. The prototype itself measures 4 px of overflow at 390.

## Report

1. Golden result: not run. The brief named no accounts file and no floor, and card 22 changes which records are counted as confirming, which is answer-path by `Product_review.md`'s definition (it can change the trust line). Answered against the floor, answered well of the fixed ten, questions that got worse: none measured. Time to answer, my seven runs only (not the golden set): meta line median 20.0 s, worst 29.8 s; click to trust line about 30 to 33 s every run; over 25 s on the meta line: query 107 Researcher at 1280.
2. Look at first: fails PR-card22-02 (saved answer lists no sources; cause measured: string `layer` values filtered out by `frontend/src/lib/api.ts:516-524`), PR-card22-01 (saved answer 33 px overflow at 390). Then needs your eye: PR-card22-04 (group badges 1+12+5 under Sources 17), PR-card22-03 (gene 672 twice in the record tables), PR-card22-05 (disease list said twice; gene answer opens with a record count), PR-card22-06 (about 30 s per answer), PR-card22-07 (rail row count changes on reload), PR-card22-08 (no design for the saved answer or rail).
3. Overflow at 390: the saved query 107 answer, 33 px (`saved-answer-table-12`). Every other develop screen measured 0. No design: the saved answer screen and the history rail.
4. Not captured: the golden run (above); a confirmed answer, so "Confirmed by N independent databases" was not seen live; the Plain language saved answer; the history rail at 1280 against the prototype's rail (my prototype capture stayed signed out, so its rail is empty); the 1280 saved query 107 answer (the 1280 clicks opened the gene answer; the query 107 saved answer was opened at 390 only). Four throwaway accounts at example.com were created on develop (`card22-review+...@example.com`), each with one to four searches; passwords were generated in the scripts and never stored.

What I read myself: every screenshot named above, the saved-answer API reply's field types (`product_saved_api_probe2.json`), the measurement JSON files, and the source of `SavedAnswerScreen.tsx`, `lib/api.ts` and the prototype's `start()`. Nothing rests only on a summary. The full-page screenshots show the app bar and footer part way down the page; that is how a full-page capture draws fixed bars, not a defect.

