# Live check: develop after five days idle (2026-09-19)

## Table of contents

- [Summary](#summary)
- [Health check](#health-check)
- [Reliability measurement](#reliability-measurement)
- [Error payloads](#error-payloads)
- [Answer quality spot check](#answer-quality-spot-check)
- [Files in this report](#files-in-this-report)

## Summary

The develop web app and API were checked after five days idle, both on commit ba38cc9 with Railway reporting SUCCESS. The API answers and reports the correct environment. Reliability today is 15 of 15 runs completing cleanly with no fatal error event, across five questions asked three times each in fresh guest sessions. That is a change from 2026-09-14, when about 1 in 10 of 53 live searches failed with an uncaptured cause. No error was reproduced in this run, so no cause is reported for today, but the measurement now captures the full error payload and the last step seen before any future failure, which the prior script did not do.

A separate finding, not a reliability failure: 14 of the 15 runs returned trust_outcome `ask` rather than `answer`, including all three researcher-depth BRCA1 runs and both plain_language BRCA1 runs. Only the HNF1A researcher run's third repetition returned a final `answer`. The measurement script counts `answer`, `ask` and `flag` as answered, so the 15 of 15 figure is correct by that definition, but a directly factual question such as "Which diseases are associated with BRCA1?" resolving to a clarifying question in all three of its researcher-depth repetitions is worth separate attention from whoever owns the think or plan step next.

## Health check

`GET https://search-agent-api-develop-43b3.up.railway.app/health` returned HTTP 200 with body `{"status":"ok","app_env":"develop"}`. The API answers and is running the develop environment.

## Reliability measurement

Method: a copy of the tracked `testing/Developer/scripts/flagship_measure.py`, at `testing/Developer/reports/2026-09-19_verification/measure_with_errors.py`, changed only in printing and collection. It now records the full payload of any `error` event, the ordered sequence of event types seen in the run, and the step last seen immediately before a fatal error. The tracked script itself was not edited. Runs were fired strictly one at a time (never more than 1 in flight, under the 2-run cap), each in a fresh guest session, at audience_depth researcher unless noted.

| Question | Depth | Answered of 3 | Distinct citation source sets | Sizes | Median elapsed | Max elapsed |
|---|---|---|---|---|---|---|
| Which diseases are associated with BRCA1? | researcher | 3 of 3 | 1 | [11] | 13.9s | 26.8s |
| What diseases are caused by variants in the HNF1A gene? | researcher | 3 of 3 | 2 | [13, 18] | 14.1s | 16.2s |
| Variants in GCK causing MODY | researcher | 3 of 3 | 1 | [20] | 11.3s | 28.6s |
| What genes are associated with MODY? | researcher | 3 of 3 | 1 | [13] | 6.5s | 15.2s |
| Which diseases are associated with BRCA1? | plain_language | 3 of 3 | 1 | [11] | 6.4s | 22.3s |

Current failure rate: 0 of 15 runs failed (0 percent), against roughly 1 in 10 on 2026-09-14. No cause is reported because no failure occurred in this measurement window to capture a cause from.

Per-run outcomes were `ask` for 14 runs and `answer` for 1 run (HNF1A researcher, run 3). Every run reached a `done` event. Every run's step sequence followed the same shape: `guard`, `think`, `plan`, one or more `tool_start`/`tool_result` pairs, `step`, a run of `token` events, a run of `citation` events, a run of `trust_signal` events, then `done`. No run stopped short of `done` and no run contained an `error` event.

## Error payloads

None captured. Zero of the 15 runs produced an `error` event, so `error_payload` is `null` and `last_step_before_error` is `null` for every row in `run_detail.json`. The instrumentation added to `measure_with_errors.py` for this check (verbatim payload capture plus the preceding step) did not fire because nothing failed in this window.

## Answer quality spot check

Method: two additional single, paced queries reused the same request and streaming mechanics as the reliability measurement (`fetch_answer_text.py`, a separate one-off read-only helper in this report folder, not the tracked script) so the full reassembled answer text could be inspected. One BRCA1 researcher run and the HNF1A researcher run were checked for markdown heading syntax, a pipe table, the "Variant-to-disease mapping" heading, and raw MedGen codes such as C0342276.

| Check | BRCA1 researcher (outcome: ask) | HNF1A researcher (outcome: answer) |
|---|---|---|
| Markdown heading syntax (`#`) | Not present | Not present |
| Pipe table (`\|`) | Not present | Not present |
| "Variant-to-disease mapping" heading | Not present (not applicable to this question) | Present |
| Raw MedGen codes (e.g. C0342276) in the answer words | None found | None found |

Both answers use plain-text section labels ("Disease records found", "Gene records found", "Clinical trial records found") rather than markdown heading syntax, and list records as inline sentences rather than as a table. Neither answer leaked a raw MedGen concept code; the HNF1A answer instead names variants by their ClinVar id (for example "SequenceVariant ClinVar:1025247"), which is the intended non-CURIE form. The HNF1A answer, the one full `answer` outcome captured today, does carry the "Variant-to-disease mapping" section as expected. The BRCA1 answer is a clarifying question (`ask`), not a final synthesized answer, so the table-and-headings shape does not apply to it the same way; that itself is downstream of the ask-versus-answer finding in the summary above.

## Files in this report

- `measure_with_errors.py`: the modified measurement script (throwaway copy, tracked script untouched)
- `run_output.log`: console output of the 15-run measurement
- `run_detail.json`: full structured detail per run, including verbatim error payloads (all null) and step sequences
- `fetch_answer_text.py`: one-off helper for the two answer-quality queries
- `answer_text.json`: the two reassembled answer texts checked above

## Correction by the main agent, 2026-09-19

Two claims above are wrong, and they are corrected here rather than deleted, because the mistake is the useful part.

- "A directly factual question resolves to a clarifying question every time" is FALSE. `trust_outcome: "ask"` is the trust tier, rendered to the reader as "Based on 4 sources, not yet confirmed". It is not a question put back to the reader, and `think.clarifying_question` was null.
- "No markdown heading syntax, no pipe table" is the wrong instrument rather than a finding. Answers ship typed `heading`, `table_header`, `table_row` and `list_item` tokens, which the web app renders. Markdown was never expected in the token text.

Measured directly on develop at `ba38cc9`, one guest run of "Which diseases are associated with BRCA1?" at researcher depth, 7.5 seconds:

| Property | Value |
|---|---|
| trust_outcome | ask, with trust line "Based on 4 sources, not yet confirmed" |
| think.clarifying_question | none |
| token kinds | claim 5, heading 5, list_item 6, table_header 1, table_row 5, paragraph_break 7 |
| citations | 11 |
| first claim | "Found 4 disease records for BRCA1: Familial cancer of breast [1], Familial breast-ovarian cancer susceptibility 1 [2], Pancreatic cancer susceptibility 4 [3] ..." |

So the answer is a full, cited, structured answer. The reliability result in this report stands: 15 of 15 runs answered, no error event captured. The trust-line wording ("not yet confirmed") is an open product-owner question, not a defect.

The general lesson, the same one recorded for the 2026-09-14 instruments: a checker that reads a status word without knowing what the word means will report a plausible wrong conclusion, and it reads as a finding rather than as a bug in the checker.
