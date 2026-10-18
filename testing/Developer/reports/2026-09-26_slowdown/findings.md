# Where the golden run's median time to answer went, phase 8.1 to phase 8.2

The golden run's median slowdown traces almost entirely to the write step: write start to the done event grew by roughly 2.8s at the median versus 0.22s for guard-to-think and near zero for think-to-plan and plan-to-first-tool, the stages that carry the four new Jev decisions, and Jev's own recorded latency (low hundreds of milliseconds per decision) is far too small to explain it. At p90 a second, smaller effect also appears, a roughly 4.8s tail in before_guard and guard_to_think consistent with the guard tier's one-second comparison grace being hit, but it sits beside a much larger 10.3s write_to_done tail, so the growth is chiefly in answer generation, not in the new decision seam.

## Table of contents

- [Stage timing, medians and p90, both runs](#stage-timing-medians-and-p90-both-runs)
- [Stage growth by query class](#stage-growth-by-query-class)
- [Stage growth by category](#stage-growth-by-category)
- [Top-line seconds, sanity check against summary.md](#top-line-seconds-sanity-check-against-summarymd)
- [Biggest single-question growth](#biggest-single-question-growth)
- [Jev's own latency, phase 8.2 done events](#jevs-own-latency-phase-82-done-events)
- [Decisions actually recorded, versus four expected](#decisions-actually-recorded-versus-four-expected)
- [Why the new decisions mostly do not cost time, per the code](#why-the-new-decisions-mostly-do-not-cost-time-per-the-code)
- [Load and error signals, run to run](#load-and-error-signals-run-to-run)
- [Answer size and the missing token events](#answer-size-and-the-missing-token-events)
- [Confidence: what this data can and cannot show](#confidence-what-this-data-can-and-cannot-show)
- [Method](#method)
- [Lead's note, added after the analysis](#leads-note-added-after-the-analysis)

## Stage timing, medians and p90, both runs

Seconds. Pairs is the count of (question, pass) keys present in both runs with a measurable value for that stage. Delta is phase 8.2 minus phase 8.1, computed pair by pair on the matched (question, pass) keys present in both runs, then the median/p90 of those per-pair deltas is reported (not the difference of the two medians), so a delta reflects consistent per-question movement rather than distribution shift alone.

| Stage | Median 8.1 | Median 8.2 | Median delta | p90 8.1 | p90 8.2 | p90 delta | Pairs |
|---|---|---|---|---|---|---|---|
| Before guard (dispatch, queueing) | 2.07 | 2.34 | 0.20 | 3.54 | 7.40 | 4.80 | 149 |
| Guard to think | 2.21 | 2.74 | 0.22 | 4.15 | 8.80 | 4.84 | 116 |
| Think to plan | 0.00 | 0.00 | -0.00 | 0.02 | 0.01 | -0.00 | 116 |
| Plan to first tool | 0.00 | 0.00 | -0.00 | 0.01 | 0.00 | -0.00 | 104 |
| Tools (first start to last result) | 2.00 | 1.69 | -0.16 | 16.06 | 8.43 | 0.46 | 104 |
| Last tool to write start | 0.00 | 0.00 | -0.00 | 0.01 | 0.01 | 0.00 | 104 |
| Write start to done | 11.61 | 16.00 | 2.78 | 21.16 | 23.94 | 10.33 | 104 |

No token or trust_signal event is present in either run's saved raw event stream (checked across all 300 files), so "last tool to first token" as literally asked cannot be isolated from "last tool to write started" plus "write started to done": the write step only emits one event, step/write/started, at its beginning, and the next event in the saved file is done. The two stages requested that fall inside the writing step are reported here as one combined pair: last tool to write start (essentially instantaneous, the write step starts immediately after the tools return) and write start to done (the Synth-tier model call and its streaming, which is where the growth sits). See the answer-size section below for why the token and trust_signal events are missing from these files specifically, and what that does and does not limit.

## Stage growth by query class

Median per-pair delta in seconds, phase 8.2 minus phase 8.1, by the question's query_class.

| Query class | Before guard (dispatch, queueing) | Guard to think | Think to plan | Plan to first tool | Tools (first start to last result) | Last tool to write start | Write start to done | Pairs (write_to_done) |
|---|---|---|---|---|---|---|---|---|
| aggregate | 0.39 | 0.92 | -0.00 | -0.00 | -0.74 | -0.00 | -1.70 | 3 |
| exploratory | 0.45 | 0.06 | -0.00 | -0.00 | -2.94 | -0.00 | -0.47 | 9 |
| lookup | 0.25 | 0.30 | -0.00 | -0.00 | -0.01 | -0.00 | 1.86 | 14 |
| multi_hop | 0.16 | 0.77 | -0.00 | -0.00 | -0.25 | -0.00 | 3.52 | 36 |
| single_hop | 0.17 | -0.01 | -0.00 | -0.00 | -0.10 | -0.00 | 3.93 | 42 |

write_to_done growth concentrates in single_hop and multi_hop, the two classes that make up most of the answered questions in this dataset. Aggregate and exploratory questions, a much smaller slice, show a negative median delta (faster in phase 8.2), and lookup sits in between. The slowdown is not spread evenly across question types; it tracks the query classes that were already answering most often and taking the most write-step time.

## Stage growth by category

Median per-pair delta in seconds, phase 8.2 minus phase 8.1, by the golden dataset's category (kiss, kisses, discovery).

| Category | Before guard (dispatch, queueing) | Guard to think | Think to plan | Plan to first tool | Tools (first start to last result) | Last tool to write start | Write start to done | Pairs (write_to_done) |
|---|---|---|---|---|---|---|---|---|
| discovery | -0.05 | 1.42 | -0.00 | -0.00 | -0.27 | -0.00 | 2.58 | 15 |
| kiss | 0.39 | 0.18 | -0.00 | -0.00 | -0.07 | -0.00 | 3.13 | 35 |
| kisses | 0.17 | 0.06 | -0.00 | -0.00 | -0.17 | -0.00 | 2.37 | 54 |

## Top-line seconds, sanity check against summary.md

The `seconds` field from runs.jsonl (client-observed wall time per run), recomputed here from the raw files, matched against the two summary.md reports to confirm this analysis is reading the same numbers the summary already reported.

| Run | Median (this analysis) | Median (summary.md) | p90 (this analysis) | p90 (summary.md) |
|---|---|---|---|---|
| Phase 8.1 | 17.1 | 17.1 | 32.7 | 32.7 |
| Phase 8.2 | 21.9 | 21.9 | 36.4 | 36.4 |

Note this analysis's median/p90 are computed over all outcomes (answered and refused alike, whatever coincides with the matched-pair set), the same population summary.md's "Overall" row uses, so the two should and do agree closely.

## Biggest single-question growth

The 10 (question, pass) pairs whose `seconds` grew the most from phase 8.1 to phase 8.2, with the write_to_done delta for the same pair alongside, to show whether the biggest jumps in total time line up with the writing stage.

| Question | Pass | 8.1 seconds | 8.2 seconds | Seconds delta | write_to_done delta | Query class | Outcome (8.2) |
|---|---|---|---|---|---|---|---|
| G-038 | 1 | 0.6 | 39.4 | 38.8 | n/a | exploratory | answered |
| G-038 | 3 | 0.8 | 34.1 | 33.3 | n/a | exploratory | answered |
| G-017 | 2 | 20.2 | 47.6 | 27.4 | 29.7 | single_hop | answered |
| G-017 | 3 | 30.8 | 57.2 | 26.4 | 17.2 | single_hop | answered |
| G-027 | 1 | 19.8 | 45.9 | 26.1 | 11.4 | single_hop | answered |
| G-006 | 3 | 96.5 | 121.6 | 25.1 | 0.1 | multi_hop | refused_no_evidence |
| G-031 | 3 | 16.0 | 39.6 | 23.6 | 8.5 | single_hop | answered |
| G-028 | 1 | 24.3 | 45.5 | 21.2 | 16.3 | multi_hop | answered |
| G-020 | 1 | 14.0 | 34.5 | 20.5 | 8.5 | lookup | answered |
| G-028 | 2 | 14.4 | 34.0 | 19.6 | 18.4 | multi_hop | answered |

The two G-038 rows show 'n/a' for write_to_done because that question changed outcome bucket between runs, not because the write step itself slowed: phase 8.1 refused it as off-topic in 0.6 to 0.8 seconds (guard straight to done, no write step at all), and phase 8.2's guardrail.relevancy classifier judged the same question ('Tell me about the tree of life') on-topic, so it ran the full pipeline and took 34 to 39 seconds. That is a behaviour change in what gets answered, not a slowdown of the same computation.

Across all 150 matched pairs, only 4 changed outcome bucket (answered, refused, or other) between the two runs. Excluding those from the top-line seconds comparison barely moves it: median seconds on the 146 same-bucket pairs is 17.2 for phase 8.1 and 21.8 for phase 8.2, against 17.1 and 21.9 for the full population. The outcome-bucket mix shift is real (worth knowing about on its own, since one of the four flips is arguably a guardrail quality improvement) but it is not what moved the median.

| Question | Pass | 8.1 outcome | 8.2 outcome | 8.1 seconds | 8.2 seconds |
|---|---|---|---|---|---|
| G-006 | 2 | refused_no_evidence | answered | 96.7 | 26.8 |
| G-038 | 1 | refused_offtopic | answered | 0.6 | 39.4 |
| G-038 | 3 | refused_offtopic | answered | 0.8 | 34.1 |
| G-046 | 1 | refused_compute_request | error | 1.7 | 15.4 |

## Jev's own latency, phase 8.2 done events

Across 245 recorded jev_latency_ms values on 127 runs that carried at least one decision:

| Measure | Value (ms) |
|---|---|
| Median | 144 |
| p90 | 216 |
| Max | 688 |
| Sum, all decisions, one run (typical, 2 decisions) | 0.29 s |

By decision name:

| Decision | n | Median ms | p90 ms | Max ms |
|---|---|---|---|---|
| guardrail.relevancy | 11 | 147 | 187 | 352 |
| plan.literature | 116 | 144 | 207 | 675 |
| think.recent_years | 118 | 144 | 226 | 688 |

Even at the p90 and summed across every decision seen on one run, Jev's own latency stays under one second, well short of the multi-second median growth measured in write_to_done. This points away from Jev as the mechanism, on the data available: Jev's calls are cheap and finish before the guard tier's own one-second grace period would even expire.

## Decisions actually recorded, versus four expected

The question states Jev decides four choices per question. The phase 8.2 done events actually carry at most 3 decisions per run, and most carry exactly 2. Counted across all 150 phase 8.2 runs:

| Decisions on the done event | Runs |
|---|---|
| 0 | 23 |
| 1 | 10 |
| 2 | 115 |
| 3 | 2 |

Decision names seen, with count and fallback reasons where the guard tier did not answer in time:

| Decision name | Runs carrying it | Fallback reason, when present |
|---|---|---|
| guardrail.relevancy | 11 | guard_not_ready (5) |
| plan.literature | 117 | guard_not_ready (80), timeout (1) |
| think.recent_years | 118 | guard_not_ready (74) |

guardrail.relevancy appears only on a minority of runs (the ones where the guard tier's own classification was itself ambiguous enough to need Jev's tie-break), and no think.ask_back decision was observed in this dataset at all, so "four choices per question" describes the decision surface Jev is wired to, not what fires on every question. The data cannot confirm or rule out a per-call cost for a decision that never actually ran in this sample.

## Why the new decisions mostly do not cost time, per the code

This section reads `src/system_03_search_agent/harness/decide.py` and `src/system_03_search_agent/core/graph.py` directly, as a static check of the mechanism the timing data already points away from. No live service was called for this; it is a source read, the same as reading any other file in this repository.

The four decision points are wired at fixed call sites: `guardrail.relevancy` in `guardrail_node`, `think.ask_back` and `think.recent_years` in `think_node`, and `plan.literature` also started by `think_node` and handed to Plan still running. Two things in the code explain why the median guard/think/plan stages barely move even though a new model call was added to each:

First, every decision after the guardrail one is fired as a background asyncio task at the moment its owning node starts, not awaited inline, so it runs concurrently with whatever that node was already going to do (entity resolution, tool-plan assembly). The `think_node` docstring states the intent directly: "both start the moment the node does, so they overlap everything Think does before either is needed... the person waits for one decision, not three." `guardrail.relevancy` is narrower still: `guardrail_node` only starts it for a question that fails a fast biomedical-vocabulary allowlist check, which is why it appears on only 11 of 150 phase 8.2 runs rather than on every run.

Second, `decide()` documents a real, non-zero wait even after Jev has already answered. Its module docstring says: "once Jev has answered the comparison waits at most `GUARD_COMPARISON_GRACE_S` for the guard, so the person never waits on a pick that is only recorded." The constant is `GUARD_COMPARISON_GRACE_S = 1.0`, and the code does exactly what the first half of that sentence says: `await asyncio.wait({guard_task}, timeout=GUARD_COMPARISON_GRACE_S)` runs before `decide()` returns, even though Jev's choice is already known and will be used regardless of what the guard tier says. The trailing clause, "the person never waits," is best read as relative to a longer, uncapped wait this fix round removed, not as zero added time: this is a documented one-second cap, not an oversight, but it is a real cost inside a background task whenever it fires. The fallback_reason counts say it fires often: `guard_not_ready` (the grace expired before the guard tier answered) accounts for 159 of the 245 decisions recorded in phase 8.2. That extra wait only shows up in a node's own wall-clock time when it outlasts whatever else that node was doing concurrently, which is plausibly why the guard_to_think stage's median barely moved (0.22s) while its p90 grew by 4.84s: most questions keep the node busy longer than one second anyway, and a tail of questions do not.

Separately, comparing the two runs' exact deployed commits (5bac18a for phase 8.1, 566e1ab for phase 8.2) shows zero changed lines under `src/system_03_search_agent/synthesis/`, the answer-writing module. The write step's own code did not change between these two deployments. Whatever grew write_to_done, it was not a direct edit to the write step's logic or prompt-building code in this diff.

The same folder as this report's inputs already carries an independent cross-check: `decisions_comparison.md`, next to phase 8.2's raw files, tallies the same three decision points from the same 150 runs (11, 117 and 118 decisions, with guard_not_ready at 5, 80 and 74) and notes in its own words that "letting the comparison land before the done event is a To do card," meaning the guard-comparison wait not finishing before the answer is already a known, tracked gap, not a new finding of this report. That document counts decisions; it does not measure stage timing, which is this report's addition.

## Load and error signals, run to run

| Signal | Phase 8.1 | Phase 8.2 |
|---|---|---|
| rate_limit_signals, summed | 0 | 0 |
| tool_errors, summed | 5 | 3 |
| runs with an error event | 0 | 1 |
| started_at span | 2026-09-25T09:46:23+00:00 to 2026-09-25T10:13:18+00:00 | 2026-09-25T13:01:31+00:00 to 2026-09-25T13:33:27+00:00 |

Outcome counts, both runs:

| Outcome | Phase 8.1 | Phase 8.2 |
|---|---|---|
| answered | 99 | 102 |
| error | 0 | 1 |
| refused_compute_request | 5 | 4 |
| refused_injection | 6 | 6 |
| refused_medical_advice | 6 | 6 |
| refused_no_evidence | 18 | 16 |
| refused_offtopic | 13 | 12 |
| refused_write_seeking | 3 | 3 |

Phase 8.2 introduces an outcome value not present in phase 8.1: 'error'. One instance was inspected directly (G-046, run 1): a fatal, transient, step-scoped error from the guardrail source, message 'A step in this query hit a temporary error.' This is consistent with the new guard-versus-Jev race (the guard tier given a one-second grace beside Jev) occasionally tripping a guardrail-side fault, but one instance is not enough to attribute the median latency growth to it, since the growth shows up broadly across answered runs, not concentrated in the handful of error runs.

Both runs were started within about 27 minutes of each other on the same day (see the started_at spans above), both against the same class of golden-run harness, so a large time-of-day load difference is unlikely to explain the shift, though the two runs were not simultaneous and a shared external dependency (the graph host, an NCBI endpoint, the model provider) could still have been under different load at each start time. Neither run recorded any rate_limit_signals, and the tool_errors counts are low and similar in the both runs, which argues against a rate-limiting or tool-availability explanation for the bulk of the growth.

## Answer size and the missing token events

Ruling out "answers just got longer": on the 99 matched (question, pass) pairs where both runs answered, the median per-pair delta in answer_words is 0 words. Citation counts and total tool calls are identical at the median in both runs. Answer content size is not growing between the two runs, so the write_to_done growth is not simply "the model had more to say."

| Measure | Median 8.1 | Median 8.2 | Median per-pair delta |
|---|---|---|---|
| answer_words | 342 | 364 | 0 |
| citations | 24 | 24 | n/a |
| total_tool_calls | 10 | 10 | n/a |

On the missing token and trust_signal events: each raw/*.json file's own `record.event_types` field counts every event type the live run actually emitted, including token and trust_signal, but the saved `events` array is shorter than that count by exactly the token-plus-trust_signal total. Checked on G-001, run 1: phase 8.1's event_types sums to 239 declared events (`token`: 85, `trust_signal`: 60, and 94 others), but the saved events array holds exactly 94 entries, a gap of 145, precisely token (85) plus trust_signal (60). The same shape holds across both runs: token and trust_signal fired during the live run and were counted, but were not written into raw/*.json.

| Run | Runs with event_types | Declared events (sum) | Saved events (raw array) | token+trust_signal declared |
|---|---|---|---|---|
| Phase 8.1 | 150 | 15135 | 6116 | 9019 (60% of declared) |
| Phase 8.2 | 150 | 15311 | 6168 | 9143 (60% of declared) |

This means the token stream's timestamps genuinely do not exist in either saved dataset, so a true time-to-first-token split is not reconstructable after the fact for this report. It also means it is not a phase 8.2-specific gap: both runs' raw files were captured the same way, so this limits this analysis symmetrically rather than hiding something that changed between the two runs.

## Confidence: what this data can and cannot show

Can show: which named stage's timestamp-to-timestamp interval grew between the two runs, at the median and p90, matched on the same 50 questions and 3 passes; that Jev's own recorded latency is small (low hundreds of milliseconds) and cannot itself account for the multi-second median growth; that the growth concentrates in write_to_done (the Synth-tier answer generation and its streaming) rather than in guard, think, plan or the tool-calling span, where the new decisions actually run; that answer length, citation count and tool-call count did not grow between the two runs, so a longer answer is not the explanation either; that only 4 of 150 matched pairs changed outcome bucket (answered, refused, other) between runs, so the median growth is not chiefly an answered-versus-refused mix shift; and, from the source rather than the logs, that the write step's own code is byte-for-byte unchanged between the two runs' exact deployed commits, and that the decision calls are deliberately run in the background so their design intent is to add little to the critical path, which the near-zero median growth in guard_to_think and think_to_plan is consistent with.

Cannot show: the root cause inside the write step itself. No token-level timestamps exist in either run (see above), so this analysis cannot say whether the Synth-tier model call slowed (a model, prompt, or provider-side change), whether time-to-first-token grew, whether the streaming phase itself took longer per token, or whether the dynamic suffix handed to Synth grew in some way that does not show up in answer_words (for example carrying the new decision outputs, per prompt-cache-discipline's rule that new content belongs in the dynamic suffix). The 'no synthesis code changed' finding rules out a direct edit to the write step, but not an indirect effect: if Jev's and the guard tier's concurrent decide() calls share a connection pool, a thread pool, or another bounded concurrency resource with the Synth call, contention could slow Synth's dispatch even though Synth's own code is untouched and even though the decide() calls finish in a different pipeline step. This report cannot confirm or rule out that hypothesis without live tracing across concurrent requests, which is out of scope here. Also cannot show causation from a single before/after pair of runs: a two-point comparison cannot rule out that the phase 8.1 run happened to sample a faster period for reasons entirely outside this repository, such as the model provider's own load at 09:44 UTC versus 13:01 UTC on the same day.

## Method

Every raw/*.json file in both report directories was parsed. Each file's `events` array was reduced to one timestamp per named point: the guard event, the think event, the plan event, the first tool_start, the last tool_result, the step/write/started event, and the done event. Stage durations are the difference between consecutive named points, computed in Python from the ISO 8601 timestamps on each event (UTC, microsecond resolution). Two runs were matched on (question id, pass number) so a stage's growth is a per-pair delta (8.2 minus 8.1), and the median and p90 reported for growth are the median and p90 of those per-pair deltas, not the difference between the two runs' independent medians. The before_guard stage is `record.seconds` (the client-observed total wall time, already present in runs.jsonl) minus the guard-to-done wall span computed from event timestamps, so it depends on the client and server clocks agreeing, which a single golden-run harness calling a single deployed API over a short span should satisfy at one-second resolution. Jev latency figures come directly from `jev_latency_ms` on each decision object inside the phase 8.2 done event's `decisions` list. Load signals come from the `rate_limit_signals` and `tool_errors` fields already recorded per run, plus a scan for `error` type events. Answer-size figures (answer_words, citations, total_tool_calls) come from the same per-run record already used for outcome and latency. The event-capture-gap check sums `record.event_types` and compares it against the length of the saved `events` array on the same file. The 'why the new decisions mostly do not cost time' section is the one part of this report drawn from reading source code (`harness/decide.py`, `core/graph.py`) rather than from the run logs, cited by file and by the exact constant and call names quoted; it was cross-checked against a `git log`/`git diff --stat` between the two runs' exact deployed commits (5bac18a, 566e1ab) restricted to `src/system_03_search_agent/`, read-only and with no live service called. No file outside this report's own output directory was written.


## Lead's note, added after the analysis

Added by the lead on 2026-09-25, after reading this report. The analysis above is left as the analyst wrote it; this section corrects one statement and records what follows from the report.

- Correction: "Both runs were started within about 27 minutes of each other" is wrong. Each run lasted about 27 to 32 minutes, but phase 8.1's started at 09:46 UTC and phase 8.2's at 13:01 UTC, 3 hours 15 minutes apart, as the started_at table above shows. The second run started as the United States workday began, so a slower writing model at a busier hour is the leading explanation for the write step's growth, since the write step's code, the answer length, the citations and the tool calls did not change.
- The part the product controls: the one-second wait for the guard tier's comparison pick, which produces the p90 growth before Think and the one error run (G-046). Phase 8.6, T-8.6-01, removes the comparison from the live path.
- What the next golden run records: the UTC start time beside the median, so two runs hours apart are not read as a code change. The token events the saved files drop (see "Answer size and the missing token events") are why the time to the first word cannot be measured today; recording the first token's time in the golden run is the fix, and it belongs with the golden-run change in phase 8.7.
