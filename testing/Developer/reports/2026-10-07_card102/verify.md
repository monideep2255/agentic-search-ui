# Card 102 fresh verifier's report

Branch fix/card102-saved-answer-sources at c5c36ec4 against origin/develop 055b639c. Fresh context, 2026-10-07. Findings are appended as they are established; the verdict is at the end.

## Findings

Evidence log, written as each probe lands (the verifier's own probe file, kept outside the repository, copied into detached worktrees of c5c36ec4 and origin/develop 055b639c):

- Check 1, unit level. 19 stored citations with all 14 stored keys and string layers (card 22's 18 plus one PubMed page, so 17 pages, the deployed probe's numbers), through the real `fetchHistoryAnswer` into the real `SavedAnswerScreen`. Branch: parsed 19, 17 rows, indices 1 to 19 each listed exactly once, every row names a layer, gene page once as "1, 6, 9.". Develop: parsed 0, rows 0. The defect reproduces on develop and is gone on the branch.
- Check 2, malformed input. 20 entries: missing link, null link, string number, numeric source, null / object / "LAYER_1_GRAPH" / numeric 1 / "toString" / "__proto__" / "layer_4_new" layers, numeric entity_name, `javascript:` link, empty link, and a bare string, null, array and number in the list. No crash. Only the 4 non-objects and the 4 with no number, no name or no link were dropped; every other one is a row. Unknown layers show no layer word and a neutral dot; `javascript:` and empty links render "Not linked" with no href. All-unknown layers: 3 of 3 rows, no layer word (develop: 0 rows).

- Check 4, mutations, full vitest suite (60 files, 521 tests, all green unmutated) per mutation, restored with `git checkout` in the scratch worktree after each. Red: numeric-only layer kept (3 red), develop's numeric-only drop (6 red), drop unknown layer (2 red), guess 3 in the parser (2 red), guess 3 for a new row in the screen (1 red), swap `layerNumber`'s layer 2 to 3 (10 red, 8 of them live-answer tests), drop `source_id` passthrough (1 red), drop `entity_name` passthrough (1 red). Survivors: three, filed below as F-102-V-01 to F-102-V-03.

### F-102-V-01: Guessing a layer for an unknown citation on an already-listed page survives every test
- Severity: minor (test gap inside this card's fix; the shipped code is correct)
- Where: `frontend/src/components/screens/SavedAnswerScreen.tsx:120-121`, the merge branch of `savedSourceRows`
- What: replacing `if (layer !== null && !row.layers.includes(layer)) { row.layers = [...row.layers, layer]` with a version that adds `layer ?? 3` (so an unrecognised layer on a page already listed is named "literature") leaves all 521 tests green. Only the new-row branch (line 127) is pinned, by the card 102 screen test.
- Reproduction: mutation M5 applied in a detached worktree of c5c36ec4, `npx vitest run`: "Tests 521 passed (521)". Unmutated code checked by probe: a page cited as `layer_4_new` (n 15) then `layer_2_api` (n 16) renders one row "15, 16. ... live", no guessed word, so the code is right today.
- Why it matters: the card's own promise, "guessing a layer would be a confident wrong label", is unguarded on one of its two code paths; a later edit could reintroduce the wrong label with CI green.
- Regression against develop: no (develop dropped these citations entirely).
- NOT FIXED

### F-102-V-02: The neutral dot for an unrecognised layer is not tested
- Severity: minor (test gap inside this card's fix)
- Where: `frontend/src/components/screens/SavedAnswerScreen.tsx:137-138`
- What: replacing `layerColour(citation.layer ?? row.layers[0] ?? null)` with `layerColour(citation.layer ?? 3)` (an unknown-layer source drawn in the literature colour) leaves all 521 tests green. The comment on line 137 states the neutral colour as behaviour; nothing checks it.
- Reproduction: mutation M6, `npx vitest run`: "Tests 521 passed (521)".
- Why it matters: the dot is a layer signal a sighted reader uses; a colour guess is the same mislabel the card rules out, by colour instead of word.
- Regression against develop: no.
- NOT FIXED

### F-102-V-03: Dropping the "source name required" rule survives every test
- Severity: minor (test gap; behaviour unchanged from develop)
- Where: `frontend/src/lib/api.ts:544`, `typeof value.source !== "string"` in `toHistoryAnswerCitation`
- What: deleting that condition leaves all 521 tests green. The "drops a malformed citation" test covers only a missing link.
- Reproduction: mutation M10, `npx vitest run`: "Tests 521 passed (521)".
- Why it matters: small. The docstring at api.ts:528-530 names number, name and link as the three things a row needs; one of the three is unenforced by tests.
- Regression against develop: no.
- NOT FIXED

### F-102-V-04: A stored numeric layer (1, 2 or 3) now shows no layer word, where develop named it
- Severity: unsure (no real stored data is known to carry numbers)
- Where: `frontend/src/lib/api.ts:553`
- What: develop's parser accepted the numbers 1, 2 and 3 and showed their layer word. The branch reads only the three wire strings, so a numeric layer becomes `null`: the source is kept with its link but names no layer. The build's own test pins this (bare `2` kept as `null`).
- Reproduction: probe P2, entry `{display_index: 9, layer: 1, ...}`: branch parses `[9, null]` and renders "9. Ent 9https://www.ncbi.nlm.nih.gov/gene/9" with no word. Develop's parser keeps it as layer 1.
- Why it matters: only if some stored row carries numbers. I found none: the endpoint returns stored `CitationPayload` dicts unchanged (`src/system_03_search_agent/adapters/web_sse/app.py:1116`), the backend endpoint test stores `"layer_1_graph"`, the deployed probe saw only strings, and no e2e mock sends numbers. Filed so the owner can confirm no older rows were written with numbers.
- Regression against develop: technically yes for a numeric input, in practice no known reachable case; and the source stays listed either way.
- NOT FIXED

- Check 3, live answer, unit level. Two SSE streams built through the real `parseAgentEvent` (tool start and result for each of the three layers, card 22's 18 citations with all three wire layers, and a 6-citation stream with layers rotated), fed to `useRunView` at two cut points each, the four view models serialised. Branch and develop outputs are byte-identical (24345 bytes each), and they are not vacuous: they carry 28 layer-1, 46 layer-2 and 30 layer-3 values. The `layerNumber` move also has teeth: swapping its layer 2 to 3 turns 8 live-answer tests red (mutation M7 above).

### F-102-V-05: On a phone, source links run past their row and the card, and a real pathogen-isolate link makes the saved answer scroll sideways
- Severity: major (user-visible at 390; the brief's check 1 names "no sideways scroll")
- Where: `frontend/src/components/screens/SavedAnswerScreen.tsx:177-185`, the row's `<a>`: no `overflowWrap` or `wordBreak`, unlike the live answer's source text (`AnswerScreen.tsx:2089`, `CitationMarkers.tsx:430`, which break long strings)
- What: a URL has no spaces, so it never wraps. At 390 the ClinVar links in card 22's own fixture already spill past their row border and over the card edge; any link longer than about 50 characters pushes the whole page sideways.
- Reproduction: verifier's Playwright probe on c5c36ec4 (the card 102 spec's sign-in and routes, the stored 18 citations plus one page cited from Pathogen Detection, `https://www.ncbi.nlm.nih.gov/pathogens/isolates#/search/biosample_acc:SAMN02147118`, the exact shape `src/system_03_search_agent/tools/pathogen_detection.py:641` builds). At 390: `document.scrollWidth - clientWidth` = 193, that link's right edge at x=583, 6 links wider than their row. At 1280: 0 and 0. With a 180-character PubTator-style URL: 646 at 390, 92 at 1280. The build's own committed `testing/Developer/reports/2026-10-07_card102/saved_answer_390.png` shows the overspill: "clinvar/variation/4823850/" and "/4848411/" run over the card's right border.
- Why the card's e2e spec misses it: it measures only document overflow, and the fixture's longest link fits inside 390 even though it overflows its row, so the check passes while the row visibly breaks.
- Why it matters: a person on a phone reopening an answer that cited a pathogen isolate, a taxonomy page or a long query link gets a page that slides sideways, the thing the brief's check 1 rules out.
- Regression against develop: not in code (the row markup is card 22's, unchanged here), but newly visible: deployed develop draws no rows, so its saved answer has 0 overflow at 390 for the same input (measured: 0). From the reader's chair the branch is still a large net gain: sources a person can open, against none.
- NOT FIXED

- Check 1, browser, verifier's own Playwright probe (sign-in for real on the fake-model backend, history routes served with the stored shape: 19 citations, 17 pages, string layers, long and short entity names). Branch at 1280 and at 390: trust line "Based on 17 sources cited, not yet confirmed", 17 rows, indices 1 to 19 each once, every row names its layer, 16 links plus OMIM "Not linked". Develop, same input: 0 rows under the same trust line. The card's own spec passes on the branch, 2 of 2. Sideways scroll: see F-102-V-05.
- Check 3 and 5, e2e, same nine spec files on the branch and eight on develop (card 102's spec only on the branch), `CI=1`, ports 5273 and 8931 free first. Branch 32 passed and 16 failed; develop 31 passed and 15 failed. The 15 develop failures are a subset of the branch's: trust-surface 5, history-reload 1, rail-collapse phone panel 1, and second-turn 8, which the build report did not list (it did not run second-turn); all fail identically on develop. The one extra branch failure, rail-collapse "sits to the left of the screen's content" (line 95), is a timing flake at the 30 s limit: with 4 parallel repeats it failed 4 of 4 on the branch and 3 of 4 on develop; run with one worker it passed 2 of 2 on both, at 27 s each. Live-answer specs citations-and-writing, card22-name-every-total, card23-source-note and answer-layout pass on both.

### F-102-V-06: Develop's e2e suite fails 8 second-turn tests the build report's pre-existing list does not name
- Severity: minor (information for the lead; not caused by this branch)
- What: `e2e/second-turn.spec.ts` fails 8 tests on origin/develop 055b639c and identically on c5c36ec4 (lines 172, 211, 260, 363 x2, 425 x2, 546). The build report lists only trust-surface x5, history-reload and the rail-collapse phone test as pre-existing, because it did not run second-turn.
- Reproduction: `CI=1 npx playwright test e2e/second-turn.spec.ts ...` in detached worktrees of both commits; the failing test set is identical.
- Why it matters: a later card touching the follow-up flow could read these as its own breakage, or hide a real one among them.
- Regression against develop: no.
- NOT FIXED

### F-102-V-07: A saved answer citing more than 50 citations would list fewer rows than its trust line names
- Severity: unsure (read, not probed end to end; not caused by this branch)
- Where: `src/system_03_search_agent/adapters/web_sse/app.py:1124`, `citations=citations[:50]`
- What: the endpoint truncates the stored citations to the first 50, while the stored trust line ("Based on N sources cited") counts every page. Before card 102 no row rendered so the cap was invisible; now an answer with more than 50 citations would show "Based on N" above fewer than N rows. The server's page key (`contracts/events.py:220`) and the client's `sourcePageKey` agree, so below the cap the numbers match (deployed probe: 19 citations, 17 pages, "Based on 17").
- Reproduction: code read only. The largest real answer in the card 22 evidence has 23 citations, so I could not show a real answer over the cap.
- Why it matters: only for very long answers; the trust line would promise sources the list does not show.
- Regression against develop: no.
- NOT FIXED

- Check 6, gates on c5c36ec4 in the scratch worktree: gate02 isort "Skipped 2 files", exit 0; gate03 ruff over the whole repository "All checks passed!", exit 0; gate08 (build, `npm test` 60 files 521 tests passed, license notices ok), exit 0; doc sync "ok"; doc drift "No drift found". Leak scan `--base origin/develop`: "PASS", 0 findings, 21 binary files listed. I looked at all 21 PNGs: every visible email is a `card22-review+<digits>@example.com` test account, the card 102 1280 shot masks the account, the 390 shot does not show it; no local path, server address or real name seen. The two 390 full-page captures of expanded sources (780x8344 and 780x15048) are too tall to read every line at display scale; their text runs passed the scanner. A grep of the whole diff for email addresses finds only `example.com` and `example.invalid`.

- Check 6 continued: gate04 unit suite (`pytest -m "not integration" -q -rs`, `PYTHONPATH=src`) on c5c36ec4: 7093 passed, 143 skipped, 24 deselected, 1 xfailed, exit 0.
- Cleanup: both scratch worktrees' `node_modules` symlinks unlinked (the shared folder is intact) and both worktrees removed with `git worktree remove`. Nothing was run in asu-card102 except appends to this file.

## Verdict

PASS for merge: no regression against develop found. The one major finding, F-102-V-05, should be the next card.

| Claim | How checked | Result |
|---|---|---|
| The stored shape (string layers, 14 keys) parses and every citation is listed | Own probe, unit and browser, branch against develop | Verified: 19 of 19 kept, 17 rows, every index once. Develop: 0 |
| One row per page, the trust line's number matches the rows | Own probe, 1280 and 390 | Verified for the stored shape. Above 50 citations the server's cap would break the match, F-102-V-07, not caused here |
| No sideways scroll at 1280 and 390 | Own probe | Verified at 1280. Fails at 390 for any link over about 50 characters, such as a real pathogen-isolate link (193 px), and links spill past the card even in the build's own 390 screenshot: F-102-V-05. Not a code regression, because develop draws no rows |
| An unknown layer is kept, with no layer word, and is never mislabelled | Own probe with 9 bad layer values | Verified in behaviour. Two of the three code paths are unguarded by tests: F-102-V-01 and F-102-V-02 |
| Malformed citations are dropped one at a time, with no crash | Own probe, 20 entries | Verified |
| The live answer is unchanged after `layerNumber` moved | Own probe: `useRunView` view models byte-identical to develop's, and they are not vacuous. Plus mutation M7, and the live e2e specs passing on both | Verified |
| Each part of the fix has a test that goes red | Own 11 mutations, full suite | 8 of 11 red. Survivors: F-102-V-01, V-02 and V-03 |
| The build's pre-existing e2e failures are not caused by this branch | Same specs on both commits | Verified. The set also includes 8 second-turn failures the build did not list (F-102-V-06). The rail-collapse line 95 test is a timing flake on both commits |
| gate02, gate03, gate04, gate08, doc sync, leak scan | Exact commands, run by me | All green. All 21 PNGs looked at: only `@example.com` test accounts |

Read only, not probed: the claim that no stored row carries a numeric layer (F-102-V-04), and the 50-citation cap (F-102-V-07).

Is any finding inside a fix made during this phase? No. V-01 to V-03 are test gaps in this card's new code, which behaves correctly. V-05 sits in the row markup from 2026-09-23, which this card makes reachable for the first time. That markup is older than card 22's grouping fix and is not part of it.
