# Card 102 build: a reopened saved answer lists its sources

Card 102, found by card 22's product review on deployed develop (PR-card22-02): a reopened saved answer showed "Based on 21 sources cited" and then nothing, so none of its facts linked to a record. Branch `fix/card102-saved-answer-sources`, from develop at d94604fb. Built 2026-10-07.

## Table of contents

- [Cause](#cause)
- [Fix](#fix)
- [Tests and mutations](#tests-and-mutations)
- [End to end at 1280 and 390](#end-to-end-at-1280-and-390)
- [Gates](#gates)
- [Found along the way](#found-along-the-way)

## Cause

The server was right and the web client was wrong.

| Side | What it does with a citation's layer |
|---|---|
| Live stream | `contracts/events.py` types `layer` as `"layer_1_graph"`, `"layer_2_api"` or `"layer_3_enrichment"`; the client checks it with `isLayer` and maps it to 1, 2 or 3 with `layerNumber` |
| Stored answer | The run's `CitationPayload` dicts are stored as they were, so `layer` stays the wire string |
| `GET /v1/history/{trace_id}/answer` | Returns the stored dicts unchanged (`adapters/web_sse/app.py`, `get_v1_history_answer`) |
| Saved-answer parser, before | `isHistoryAnswerCitation` in `frontend/src/lib/api.ts` kept a citation only if `layer` was the number 1, 2 or 3, so it dropped every one; the screen draws Sources only when `citations.length > 0` |

The review's probe measured it on develop: 19 citations in the reply, 0 passing the parser. Card 22's own saved-answer unit test built its citations with numeric layers by hand, past the parser, so it stayed green over the defect.

## Fix

One mapping for both paths, in the parser, with no backend change.

- `frontend/src/lib/events.ts:56`: `layerNumber` moved here from `hooks/useRunView.ts`, beside the `Layer` type, and `isLayer` (line 384) is now exported. `hooks/useRunView.ts:29` imports it, so the live answer is unchanged.
- `frontend/src/lib/api.ts:540`: `toHistoryAnswerCitation` replaces `isHistoryAnswerCitation`. A citation needs its number, source name and link to be kept; its layer is read at line 553 through `isLayer` and `layerNumber`, and `fetchHistoryAnswer` maps every citation through it (line 633).
- The honest fallback: a layer that is none of the three keeps the source, with `layer: null`. The row shows its number, name and link and no layer word, with the neutral dot `layerColour(null)` already draws for a gap. Why: the link is what a person opens to check a fact; dropping the source leaves a numbered marker pointing at nothing, and guessing a layer would be a confident wrong label.
- `frontend/src/components/screens/SavedAnswerScreen.tsx:117` adds no layer for a null one when grouping rows by page, and line 138 picks the dot colour.

Decision row: `DECISIONS.md`, 2026-10-07, card 102.

## Tests and mutations

Every value in the fixtures is obviously fake; the stored shape carries all 14 keys the deployed reply carried.

| Test | What it proves |
|---|---|
| `frontend/src/lib/api.fetchHistoryAnswer.test.ts`, "reads the stored layer names as 1, 2 and 3 and keeps every citation" | The three wire strings parse to 1, 2 and 3, and `source_id` and `entity_name` come through |
| Same file, "keeps a citation whose layer it does not recognise" | `"layer_4_new"` and a bare `2` are kept with `layer: null` |
| `frontend/src/components/screens/SavedAnswerScreen.card102.test.tsx`, "lists one row per page under its trust line" | Card 22's 18 citations, stored shape, through the real parser into the real screen: 16 rows under "Based on 16 sources cited", the gene page once as "1, 6, 9.", four graph rows and five literature rows |
| Same file, "still lists a source whose stored layer is not recognised" | The row shows with its link and no layer word |

The existing parser tests now send string layers, the real wire shape.

Each mutation was applied, run against both files, then restored and checked byte for byte against the saved copy.

| Mutation | Result |
|---|---|
| M1: restore the numeric-only layer check | 6 of 11 red, both screen tests read 0 rows |
| M2: drop a citation whose layer is not recognised | 2 red, the two unknown-layer tests |
| M3: guess layer 3 for an unrecognised value | 2 red |
| M4: in the screen, give a null layer the number 3 | 1 red, the no-layer-word test |
| Restored | 11 of 11 green |

No backend file changed, so no backend test was added.

## End to end at 1280 and 390

`frontend/e2e/card102-saved-answer-sources.spec.ts`, run with `CI=1 npx playwright test` on ports 5273 and 8931, both free first. The fake-model backend handles sign-up for real; the spec serves the history list and the saved answer, because the fake model's runs cite nothing.

| Width | Trust line | Rows | Gene page | Links | Sideways scroll |
|---|---|---|---|---|---|
| 1280 | Based on 16 sources cited, not yet confirmed | 16 | once, "1, 6, 9." | 15, and the OMIM row says "Not linked" | 0 |
| 390 | same | 16 | once | 15, OMIM "Not linked" | 0 |

- Both widths pass, and both read 0 rows with M1 applied.
- Screenshots: `saved_answer_1280.png` and `saved_answer_390.png` in this folder. The app bar and footer drawn part way down are how a full-page capture draws fixed bars.
- The OMIM link is outside the citation host allowlist, as on the live answer; not changed by this card.

Wider run, the same six related specs on this branch and on develop's code (the four changed source files swapped back to d94604fb):

| Spec | Develop's code | This branch |
|---|---|---|
| card102, card22, citations-and-writing | not run on develop | all pass |
| trust-surface | 5 of 5 fail | 5 of 5 fail |
| history-reload | fails | fails |
| rail-collapse, phone panel test | fails | fails |
| rail-collapse, other 10 | pass | pass on the rerun; 2 timed out at 30 s on the first run, which then also ran a real answer, and passed on the second |

So the 7 failures are on develop already and are not caused by this card.

## Gates

| Gate | Command | Tail |
|---|---|---|
| gate02 isort | `.github/gates/gate02_import_order.sh` | "Skipped 2 files", exit 0 |
| gate03 ruff, whole repository | `.github/gates/gate03_lint.sh` | "All checks passed!" |
| gate04 unit suite | `.github/gates/gate04_unit_suite.sh` | 7078 passed, 143 skipped, 24 deselected, 1 xfailed |
| gate08 frontend | `.github/gates/gate08_frontend_build_and_test.sh` (build, `npm test`, license notice check) | 60 files, 517 tests passed; license notices ok |
| Leak scan | `python3 .claude/skills/ship/scripts/check_public_leaks.py --base origin/develop` | "PASS: nothing to publish looks like a secret or a private value"; the two screenshots were looked at by eye: the test account's address is masked at 1280 and not on screen at 390 |
| Doc sync | `python3 tracker/check_doc_sync.py` | "ok: the board, the done file, the test queries, the board plan, the Factory brief, the handoff and the registry agree" |

## Found along the way

- On a phone, tapping a past search leaves the Your searches panel open over the answer, and the page behind it is hidden from screen readers until the panel is closed. Measured at 390: one open dialog and `#root` `aria-hidden` after the tap. The spec closes the panel the way a person would. Not fixed here; it is a separate card if the owner wants it.
- `e2e/citations-and-writing.spec.ts` rewrites six committed screenshots under `testing/Developer/reports/2026-09-14_citations_and_writing/` every time it runs. They were restored, not committed.
- The board row for card 102 points at `testing/Developer/reports/2026-10-06_card22/product_review.md`, which is still untracked in the main checkout.
