# Live check after e5947e0, 2026-09-14

Develop was checked after commit e5947e0 deployed: the answer layout, the writing banner, clean copy, the variant-to-disease and gene-to-disease tables, and the GCK and MODY fixes. Railway reported SUCCESS for `search-agent-api` at 18:24:55 UTC and `search-agent-web` at 18:25:08 UTC. The checks were run by sub-agents, whose own report writes were refused, so the main agent recorded their findings here.

## Table of contents

- [Browser check](#browser-check)
- [Repeated questions](#repeated-questions)
- [Errors](#errors)
- [Files](#files)

## Browser check

The build was confirmed by its bundle content, not its file name: the bundle carries `writing-banner`, `is writing the answer` and `answer-table`, and has no `spine-segment`. The bundle file name did not change for this deploy.

| Item | Result | Evidence |
|---|---|---|
| a. BRCA1, Plain language and Researcher, 1280 | Pass | The banner showed before the first sentence in both modes; 4 headings, 4 tables, 11 table rows |
| b. HNF1A, Researcher, 1280 | Pass | "Variant-to-disease mapping" heading; 5 tables, 18 table rows |
| c. Variants in GCK causing MODY, 1280 | Pass | Answered: "Found 12 sequence variant records for GCK and MODY, linked to 1 disease: Maturity-onset diabetes of the young type 2" |
| d. What genes are associated with MODY?, 1280 | Pass | Answered: "Found 6 gene records for MODY"; 2 tables, 13 table rows |
| e. Copy | Pass | A 1,703 character selection holds no "Source N, layer" or "Sources X to" text |
| f. BRCA1, Plain language, 390 | Pass | 0 tables, 4 stacked record lists, 11 rows; scrollWidth 390, clientWidth 390 |

`live_check.mjs` also ran four cases:

- BRCA1 Plain language at 1280: answered in 34.6 s.
- The follow-up "What variants cause it?": answered in 161.1 s, past the script's own 150 s window.
- GCK Researcher: answered in 34.3 s.
- BRCA1 Plain language at 390: failed, "This run could not be completed", with 0 tools after 30.1 s.

## Repeated questions

`flagship_measure.py 5` plus three extra questions, 5 runs each, two processes at once (logs beside this file):

| Question (depth) | Answered | Distinct source sets | Median s | Max s |
|---|---|---|---|---|
| Which diseases are associated with BRCA1? (researcher) | 5 of 5 | 1 | 13.7 | 17.4 |
| What variants cause disease in BRCA1? (researcher) | 4 of 5 | 1 | 18.4 | 55.1 |
| Variants in GCK causing MODY (researcher) | 4 of 5 | 1 | 29.6 | 53.2 |
| Which diseases are associated with BRCA1 and BRCA2? (researcher) | 5 of 5 | 1 | 17.8 | 34.9 |
| what diseases are linked to brca1? (researcher) | 5 of 5 | 1 | 23.1 | 26.3 |
| What diseases are caused by variants in the HNF1A gene? (researcher) | 4 of 5 | 1 | 16.8 | 64.1 |
| What genes are associated with MODY? (researcher) | 5 of 5 | 1 | 24.3 | 26.1 |
| Which diseases are associated with BRCA1? (plain_language) | 4 of 5 | 1 | 15.6 | 19.8 |

A reproduction probe then asked the four questions that errored, 3 rounds, three at a time: 12 of 12 answered, no error event, 8.4 to 62.3 s.

## Errors

- Five of 53 live runs on this build failed: four in the measurement (15.6 to 64.1 s) and one in `live_check.mjs` (30.1 s, no tools run).
- None reproduced in the 12-run probe.
- The error text was not captured. `flagship_measure.py` prints only the outcome word, and the API's Railway logs show HTTP access lines only.
- The cause is therefore unknown. The earlier flagship run on `674b7b9` answered 25 of 25.
- Next step: capture the `error` event payload on every measured run, so the next failure names its step and class.

## Files

- `flagship_measure_e5947e0.log`, `extra_measure.py`, `extra_measure.log`: the repeated questions.
- `check.mjs`, `results.json`, `e_selection_text.txt` and the `a_` to `f_` screenshots: the browser check.
- `writetest.txt`: an empty file a sub-agent created to test write access. It carries nothing.
