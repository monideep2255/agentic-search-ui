# Synth effort none, measured, 2026-09-14

Fixer: the harness-measurement sub-agent, working alone. The main agent
already made the one approved edit before this session started:
`src/system_03_search_agent/harness/harness.py`,
`_TIER_REASONING["synth"] = {"effort": "none"}`. This report does not touch
that line, any other tier, cap, timeout, or budget. It pins the change with
a test, measures it live with 35 real runs plus a small supplementary probe,
and reports where the remaining wait goes.

## Table of contents

- [Summary](#summary)
- [The regression test](#the-regression-test)
- [Live measurement setup](#live-measurement-setup)
- [Errors, out of 35](#errors-out-of-35)
- [Quality compared against effort low](#quality-compared-against-effort-low)
- [Live-run table](#live-run-table)
- [Per-step time breakdown](#per-step-time-breakdown)
- [Speed proposals, ranked](#speed-proposals-ranked)
- [Verify commands](#verify-commands)
- [Files in this folder](#files-in-this-folder)

## Summary

- The write-step transient error the product owner approved this change
  for: ZERO of 35 runs, and zero of the worst individual Synth calls (the
  worst single call was 22.9 seconds, a repair call, well under the
  45-second write budget and under half of "low" effort's measured 45.0s
  worst case).
- Two OTHER step-scoped transient errors fired, neither caused by this
  change: one plan-tier timeout (45.2s, the tier's own step budget) and one
  guard-tier timeout (15.08s, that tier's own step budget). Both are the
  same class of provider-latency spike the answer-quality report already
  named open (AQ-09, AQ-10) and the pre-existing plan-tier comment in
  `core/graph.py` already documents. See "Errors, out of 35" below.
- Quality is unchanged from the answer-quality report's fixes, measured
  fresh at effort "none" rather than assumed: every answered run's first
  sentence is the code-built "Found N ... records" summary, BRCA1 disease
  prose names diseases before trials, source sets match the answer-quality
  report's own pre-change and post-change captures exactly, every claim
  carries a marker (0 unmarked claims across 35 runs), no raw `MedGen:C`
  code and no "source URL" sentence appeared anywhere, and the two
  non-write errors are refusals (`ask`/`refuse` outcomes), never a
  fabricated answer.
- Median total elapsed: 21.2s. Worst: 60.8s. Best: 11.8s. Median first
  Synth call: 5.0s (was 4.8 to 23.5s at effort "low" per the answer-quality
  report). The write step still dominates the median (10.66s of 18.1s of
  accounted-for step time), but not because of reasoning any more: it is
  now dominated by a SECOND full Synth call, the completeness repair,
  which fired on 33 of 33 answered runs (100% in this batch) at a median
  cost of 4.8s and a worst cost of 22.9s. That is the single largest lever
  left, detailed in "Speed proposals" below.

## The regression test

`tests/system_03_search_agent/harness/test_harness.py` gained two tests,
both pinning the product owner's 2026-09-14 decision:

- `test_synth_reasoning_effort_is_none`: asserts
  `harness_module._TIER_REASONING["synth"] == {"effort": "none"}`, with a
  docstring naming the write-step transient error this fixes and pointing
  at the answer-quality report's measurement.
- `test_call_tier_sends_synth_reasoning_effort_none_to_litellm`: the
  populate check. Fakes `litellm.acompletion`, calls
  `Harness.call_tier("synth", ...)`, and asserts the `reasoning` kwarg
  actually sent is `{"effort": "none"}`, so the test proves the configured
  value reaches the real LiteLLM call rather than only sitting correctly in
  the dict `call_tier` reads from.

Demonstrated failure, then restored. `_TIER_REASONING["synth"]`'s value in
`harness.py` was flipped to `{"effort": "low"}`, both new tests were run and
both FAILED with the expected assertion diff, then the file was restored
byte-for-byte to the product owner's approved value and the full harness
suite was re-run green:

```
$ python -m pytest tests/system_03_search_agent/harness -q -p no:cacheprovider -k synth_reasoning
[value flipped to "low"]
FAILED test_synth_reasoning_effort_is_none
    assert {'effort': 'low'} == {'effort': 'none'}
FAILED test_call_tier_sends_synth_reasoning_effort_none_to_litellm
    assert {'effort': 'low'} == {'effort': 'none'}
2 failed, 195 deselected in 4.07s

[value restored to "none"]
$ python -m pytest tests/system_03_search_agent/harness -q -p no:cacheprovider
197 passed in 6.68s
```

## Live measurement setup

Script: `measure_write2.py`, a copy of
`testing/Developer/reports/2026-09-14_answer_quality/measure_write.py`
extended additively with one field, `step_seconds`: a per-step wall-time
breakdown (guard, think, plan, act, write) derived from each yielded
event's own `ts` (stamped at emit time in `core/graph.py`'s
`_EventSink.emit`). Wrapping the node functions directly, the brief's other
suggested approach, does not work in this codebase and was tried first:
`_build_graph()` calls `add_node("guardrail", guardrail_node)` with the
bare function object at IMPORT time inside `core/graph.py` itself, so
monkeypatching `graph_module.guardrail_node` after import never reaches the
already-built `compiled_graph`, which closed over the original function at
module load. Event timestamps are the externally observable per-step
boundary available without editing `core/graph.py`, which is outside this
task's file list.

`python3 tracker/preflight.py`: READY (product model, harness model, and
graph all answered) before the batch started.

No session memory (`user_id=None`, no `owner_id`), real models and the real
graph, matching the answer-quality report's own setup. (The
`CallerIdentityRequired` warnings visible in the raw logs are the same
best-effort session-memory/analytics no-op the answer-quality report's own
script also produces for a caller with no `owner_id`; they do not affect
the measured run.) At most two concurrent processes, one queue of 15
researcher runs and one queue of 20 runs (5 researcher + 10
plain_language), so no more than two questions hit NCBI at once.

- Queue A (researcher): "Which diseases are associated with BRCA1?" (5),
  "What variants cause disease in BRCA1?" (5), "Variants in GCK causing
  MODY" (5).
- Queue B: "Which diseases are associated with BRCA1 and BRCA2?" (5,
  researcher), "what diseases are linked to brca1?" (5, researcher),
  "Which diseases are associated with BRCA1?" (5, plain_language),
  "Variants in GCK causing MODY" (5, plain_language).

35 runs in all, one JSON line each: `smoke_test.jsonl` (BRCA1 diseases,
researcher, the first case; the file keeps its smoke-test name from an
initial single-run check plus 4 more runs to reach 5), `r2.jsonl` through
`r5.jsonl`, `p1.jsonl`, `p2.jsonl`.

A separate, supplementary probe (`measure_tools.py`, NOT part of the 35)
ran 3 more researcher-mode runs of the BRCA1-and-BRCA2 disease question
afterward, alone (no concurrent stream), to time each individual tool call
inside Act by pairing `tool_start`/`tool_result` timestamps on `call_id`.
Output: `tools_probe.jsonl`.

## Errors, out of 35

Two runs hit a step-scoped transient error, both `fatal: true`, neither
at the write step:

| File | Question | Step | Wall time absorbed | Same class as |
|---|---|---|---|---|
| r2.jsonl run 1 | "What variants cause disease in BRCA1?" (researcher) | plan | 45.2s (the plan tier's own 45s step budget) | AQ-10 in the answer-quality report: "a plan-model latency spike... outside this fix", and the `core/graph.py` comment on `plan_node`'s discarded call, which documents this exact failure mode reproducing live on Railway |
| p2.jsonl run 2 | "Variants in GCK causing MODY" (plain_language) | guardrail | 15.08s (the guard tier's own 15s step budget) | AQ-09's class: a live provider/lookup latency spike unrelated to the synth change |

Zero runs hit a write-step transient error. This is the direct measurement
against the change's own goal: the answer-quality report measured 1 of 55
runs dying at the write step at effort "low" (worst single Synth call
45.0s, `finish_reason: length`, empty content), plus 2 of 6 direct probe
calls spending their whole token ceiling on reasoning. At effort "none",
35 of 35 runs reached a terminal outcome with no write-step failure, and
the worst single Synth call across the batch was 22.9 seconds (a repair
call, not a first call, and not truncated).

Both of the errors that did fire are pre-existing, measured-elsewhere
failure modes in tiers this change does not touch (guard and plan both
already ran at `effort: "none"` before this change), not a new defect this
change introduced.

## Quality compared against effort low

Checked against the answer-quality report's own stated goals and its
live-run table for the same five researcher questions and two
plain_language questions, all measured after AQ-01 through AQ-05 landed
(this change touches only the reasoning-effort dial, none of that logic):

| Check | Result at effort "none" |
|---|---|
| First sentence is the code-built "Found N ... records" summary | Yes, on all 33 answered runs (2 refused before Write ran, for the unrelated guard/plan errors above) |
| BRCA1 disease prose names diseases before trials | Yes. Example (smoke_test.jsonl run 1): "BRCA1 is associated with Familial cancer of breast [1], Familial breast-ovarian cancer susceptibility 1 [2], Pancreatic cancer susceptibility 4 [3], a..." follows the summary sentence directly |
| Source set identical across runs and to the answer-quality report's captures | Yes. BRCA1 diseases (both phrasings, both depths): 11 sources every run. BRCA1 and BRCA2 diseases: 20 every run. GCK MODY variants (both depths): 20 every run. BRCA1 variants (disease-cause question): 20 every run. All match the answer-quality report's own recorded sets exactly (11 and 20 respectively) |
| Every claim and list row carries a marker | Yes, 0 unmarked claims across all 35 runs (`unmarked_claims` field, checked programmatically, not sampled) |
| No raw `MedGen:C` code in answer words | Yes, 0 of 35 |
| No "has a source URL of" sentence | Yes, 0 of 35 (`has_source_url_sentence`, checked programmatically) |
| Refusal rate same or better | Better or equal. At effort "low" the answer-quality report's 55-run batch had 1 write-step death plus 2 unrelated think-step refusals (AQ-09) and 1 unrelated plan-step death (AQ-10) baked into its own numbers. At effort "none", this 35-run batch has 0 write-step failures and 2 unrelated non-write errors (one plan, one guard), the same pre-existing failure class, at a similar or lower rate (2/35 = 5.7% vs. roughly 4/55 = 7.3% in the larger prior batch, not a like-for-like comparison given the different run counts and question mix, but not worse) |

No regression found on any of the five items the blocked-stop condition
names. Quality is unchanged; the failure mode the product owner approved
this change to fix is gone in this batch, and no new one appeared.

## Live-run table

Words count prose plus list values with markers removed, notes and
headings excluded, matching the answer-quality report's own convention.
"Sources" is the count of unique cited source ids per run (all runs of the
same case cite the same set; see "Quality" above). "Synth1 s/w" and
"Repair s/w" are the first and repair Synth call's wall time in seconds and
reply word count. `step_seconds` reads `g`uard `t`hink `p`lan `a`ct `w`rite
in that order, seconds each; a step is omitted when the run never reached
it (the two error rows below). For the two error rows, the step letter
shown is the step that ACTUALLY absorbed the trailing wall time, corrected
from the raw event-timestamp gap (see `analyze.py`'s `_fixed_step_seconds`
docstring): a step that errors before emitting its own event leaves no
timestamp marker, so the next real timestamp (the crash-fallback
`error`/`done` pair) would otherwise be misattributed to Write.

| Case | Mode | Run | Outcome | First sentence | Words | Headings | List rows | Sources | Synth1 s/w | Repair s/w | Elapsed | step_seconds | Errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BRCA1 diseases | researcher | 1 | ask | Found 4 disease records for BRCA1... | 129 | 4 | 11 | 11 | 11.3/201 | 10.1/215 | 60.8 | g4.54 t4.652 p27.004 a0.528 w24.094 | none |
| BRCA1 diseases | researcher | 2 | ask | Found 4 disease records for BRCA1... | 139 | 4 | 11 | 11 | 3.2/222 | 3.3/192 | 14.6 | g2.003 t3.265 p1.016 a1.259 w7.048 | none |
| BRCA1 diseases | researcher | 3 | ask | Found 4 disease records for BRCA1... | 142 | 5 | 11 | 11 | 4.8/230 | 11.1/240 | 20.1 | g1.064 t1.427 p1.073 a0.522 w16.002 | none |
| BRCA1 diseases | researcher | 4 | ask | Found 4 disease records for BRCA1... | 131 | 4 | 11 | 11 | 6.8/169 | 4.3/136 | 29.2 | g14.113 t2.533 p0.916 a0.514 w11.094 | none |
| BRCA1 diseases | researcher | 5 | ask | Found 4 disease records for BRCA1... | 146 | 4 | 11 | 11 | 7.1/236 | 4.8/263 | 17.5 | g1.085 t2.835 p1.138 a0.517 w11.881 | none |
| BRCA1 variants (disease-cause) | researcher | 1 | refuse | (none) | 0 | 0 | 0 | 0 | none | none | 51.3 | g1.513 t4.48 p45.2 | plan/transient |
| BRCA1 variants (disease-cause) | researcher | 2 | ask | Found 13 sequence variant records for BRCA1, of 15310 available. | 99 | 4 | 20 | 20 | 7.5/212 | 6.2/185 | 23.4 | g2.611 t3.096 p1.071 a2.559 w13.947 | none |
| BRCA1 variants (disease-cause) | researcher | 3 | answer | Found 13 sequence variant records for BRCA1, of 15310 available. | 132 | 4 | 20 | 20 | 7.7/188 | 6.9/218 | 35.2 | g13.175 t1.584 p2.814 a2.897 w14.672 | none |
| BRCA1 variants (disease-cause) | researcher | 4 | answer | Found 13 sequence variant records for BRCA1, of 15310 available. | 99 | 4 | 20 | 20 | 17.5/234 | 6.0/182 | 32.3 | g1.123 t3.217 p1.53 a2.766 w23.664 | none |
| BRCA1 variants (disease-cause) | researcher | 5 | answer | Found 13 sequence variant records for BRCA1, of 15310 available. | 106 | 4 | 20 | 20 | 8.2/160 | 8.7/213 | 26.2 | g1.594 t2.639 p2.174 a2.53 w17.162 | none |
| GCK MODY variants | researcher | 1 | ask | Found 13 sequence variant records for GCK, of 1333 available. | 99 | 4 | 20 | 20 | 22.0/195 | 22.5/193 | 56.7 | g6.606 t2.044 p0.914 a2.307 w44.685 | none |
| GCK MODY variants | researcher | 2 | ask | Found 13 sequence variant records for GCK, of 1333 available. | 99 | 4 | 20 | 20 | 6.9/197 | 6.6/202 | 24.1 | g3.327 t3.407 p0.596 a3.043 w13.685 | none |
| GCK MODY variants | researcher | 3 | answer | Found 13 sequence variant records for GCK, of 1333 available. | 99 | 4 | 20 | 20 | 6.2/276 | 3.4/263 | 17.7 | g2.389 t1.552 p1.1 a2.824 w9.845 | none |
| GCK MODY variants | researcher | 4 | ask | Found 13 sequence variant records for GCK, of 1333 available. | 99 | 4 | 20 | 20 | 3.5/181 | 4.2/221 | 16.2 | g2.447 t2.463 p0.842 a2.453 w7.908 | none |
| GCK MODY variants | researcher | 5 | answer | Found 13 sequence variant records for GCK, of 1333 available. | 109 | 5 | 20 | 20 | 4.6/174 | 5.1/158 | 21.9 | g2.381 t6.715 p0.734 a2.338 w9.77 | none |
| BRCA1 and BRCA2 diseases | researcher | 1 | ask | Found 2 gene records and 11 disease records for BRCA1 and BRCA2. | 153 | 4 | 20 | 20 | 5.3/220 | 22.9/323 | 59.5 | g1.03 t3.672 p25.525 a0.492 w28.782 | none |
| BRCA1 and BRCA2 diseases | researcher | 2 | ask | Found 2 gene records and 11 disease records for BRCA1 and BRCA2. | 122 | 4 | 20 | 20 | 11.4/204 | 6.8/261 | 36.4 | g2.543 t14.152 p0.602 a0.635 w18.445 | none |
| BRCA1 and BRCA2 diseases | researcher | 3 | ask | Found 2 gene records and 11 disease records for BRCA1 and BRCA2. | 184 | 4 | 20 | 20 | 4.3/181 | 16.1/332 | 28.9 | g3.567 t1.663 p1.838 a1.037 w20.64 | none |
| BRCA1 and BRCA2 diseases | researcher | 4 | ask | Found 2 gene records and 11 disease records for BRCA1 and BRCA2. | 122 | 4 | 20 | 20 | 5.0/245 | 4.1/213 | 21.2 | g8.612 t0.754 p1.92 a0.712 w9.148 | none |
| BRCA1 and BRCA2 diseases | researcher | 5 | ask | Found 2 gene records and 11 disease records for BRCA1 and BRCA2. | 122 | 4 | 20 | 20 | 4.6/201 | 3.3/178 | 15.4 | g2.509 t2.049 p2.019 a0.738 w8.062 | none |
| BRCA1 diseases (lowercase phrasing) | researcher | 1 | ask | Found 4 disease records for brca1... | 147 | 4 | 11 | 11 | 6.1/254 | 6.8/211 | 26.0 | g4.676 t1.511 p5.263 a0.65 w13.7 | none |
| BRCA1 diseases (lowercase phrasing) | researcher | 2 | ask | Found 4 disease records for BRCA1... | 106 | 4 | 11 | 11 | 2.1/144 | 6.5/240 | 15.8 | g1.608 t4.164 p0.828 a0.542 w8.615 | none |
| BRCA1 diseases (lowercase phrasing) | researcher | 3 | ask | Found 4 disease records for brca1... | 106 | 4 | 11 | 11 | 2.3/200 | 2.5/206 | 13.0 | g1.305 t4.554 p1.263 a0.803 w5.016 | none |
| BRCA1 diseases (lowercase phrasing) | researcher | 4 | ask | Found 4 disease records for brca1... | 116 | 5 | 11 | 11 | 6.2/204 | 1.7/127 | 20.1 | g5.818 t2.211 p1.409 a2.644 w7.989 | none |
| BRCA1 diseases (lowercase phrasing) | researcher | 5 | ask | Found 4 disease records for BRCA1... | 144 | 4 | 11 | 11 | 2.2/180 | 14.8/250 | 22.9 | g1.882 t1.868 p1.56 a0.511 w17.079 | none |
| BRCA1 diseases | plain_language | 1 | ask | Found 4 disease records for BRCA1... | 139 | 0 | 0 | 11 | 20.1/126 | 2.2/168 | 31.8 | g2.549 t2.95 p2.483 a0.525 w23.028 | none |
| BRCA1 diseases | plain_language | 2 | ask | Found 4 disease records for BRCA1... | 141 | 0 | 0 | 11 | 1.6/150 | 2.0/189 | 11.8 | g1.622 t1.585 p4.011 a0.851 w3.769 | none |
| BRCA1 diseases | plain_language | 3 | ask | Found 4 disease records for BRCA1... | 153 | 0 | 0 | 11 | 1.7/172 | 2.4/219 | 16.5 | g9.258 t1.106 p1.056 a0.797 w4.25 | none |
| BRCA1 diseases | plain_language | 4 | ask | Found 4 disease records for BRCA1... | 138 | 0 | 0 | 11 | 5.3/131 | 1.9/147 | 12.6 | g0.755 t0.74 p2.674 a1.14 w7.28 | none |
| BRCA1 diseases | plain_language | 5 | ask | Found 4 disease records for BRCA1... | 138 | 0 | 0 | 11 | 1.7/191 | 2.4/164 | 20.1 | g9.686 t4.418 p1.146 a0.597 w4.237 | none |
| GCK MODY variants | plain_language | 1 | ask | Found 13 sequence variant records for GCK, of 1333 available. | 154 | 0 | 0 | 20 | 2.4/167 | 2.4/161 | 21.4 | g2.486 t3.883 p7.53 a2.547 w4.919 | none |
| GCK MODY variants | plain_language | 2 | refuse | (none) | 0 | 0 | 0 | 0 | none | none | 15.1 | g15.083 | guardrail/transient |
| GCK MODY variants | plain_language | 3 | ask | Found 13 sequence variant records for GCK, of 1333 available. | 154 | 0 | 0 | 20 | 2.2/210 | 4.4/221 | 13.9 | g2.035 t1.903 p1.084 a2.245 w6.591 | none |
| GCK MODY variants | plain_language | 4 | answer | Found 13 sequence variant records for GCK, of 1333 available. | 143 | 0 | 0 | 20 | 4.7/176 | 5.9/214 | 18.4 | g0.967 t2.767 p1.638 a2.373 w10.659 | none |
| GCK MODY variants | plain_language | 5 | ask | Found 13 sequence variant records for GCK, of 1333 available. | 154 | 0 | 0 | 20 | 2.5/141 | 4.2/228 | 13.5 | g2.335 t0.73 p1.385 a2.263 w6.736 | none |

Worst single Synth call: 22.9s (repair call, BRCA1 and BRCA2 diseases run
1). Worst total elapsed: 60.8s (driven by a 27.0s plan-tier spike plus a
24.1s write step, not by the synth reasoning setting this task pins).
Median elapsed: 21.2s. Best: 11.8s.

## Per-step time breakdown

Computed over the corrected `step_seconds` (see the live-run table's own
note on the two error rows) across all 35 runs, at least 33 to 35 data
points per step:

| Step | Median (s) | Worst (s) | n | Note |
|---|---|---|---|---|
| Guard | 2.45 | 15.08 | 35 | Worst is the guard-tier timeout error above, an unrelated pre-existing spike |
| Think | 2.59 | 14.15 | 34 | |
| Plan | 1.40 | 45.20 | 34 | Worst is the plan-tier timeout error above. Excluding both errors, the tail is still heavy: 4 of 34 runs spent 4.0 to 27.0s on this step (sorted values: ...2.67, 2.81, 4.01, 5.26, 7.53, 25.53, 27.00, 45.20), against a P50 of 1.4s. This tier's own model call output is discarded (see Speed proposal 2) |
| Act | 1.04 | 3.04 | 33 | Fast and tight; confirmed by the supplementary per-tool probe below |
| Write | 10.66 | 44.69 | 33 | Still the largest single median contributor, now because of the completeness repair (see Speed proposal 1), not reasoning |

Supplementary per-tool probe (`tools_probe.jsonl`, 3 runs, NOT part of the
35, run afterward and alone): every individual tool call inside Act
finished in 0.17 to 0.60 seconds (`pubtator_annotate` 0.17-0.37s,
`clinicaltrials_search` 0.28-0.40s, `ncbi_efetch` 0.28-0.37s,
`cypher_query` 0.52-0.60s, all `status: ok`). Four tools run per query on
this question shape; their sum (roughly 1.0 to 1.9s) matches the Act
step's own measured range above. Act is not a bottleneck.

Sum of medians (guard+think+plan+act+write): 18.14s, close to the 21.2s
median total elapsed (the gap is scheduler/event-loop overhead and rounding
across steps, not a missing step).

## Speed proposals, ranked

Proposals only. Nothing beyond the regression test in the first section is
implemented here; every number below is measured from this batch or the
supplementary probe, not assumed.

### 1. Gate the completeness repair when the code-built listing already covers every admitted finding

Measured: the repair Synth call fired on 33 of 33 answered runs in this
batch (100%), adding a median 4.8s and up to 22.9s to the write step on
top of the first call's own median 5.0s. Summed across the batch, 216.5
seconds were spent on repair calls alone, roughly a third of all wall time
this batch spent inside Write.

Why it fires every time now: `write_node`'s repair trigger
(`core/graph.py`, "T-4.5-07, finding F-4.5-06 breach 2") checks which
findings the MODEL'S OWN PROSE grounded a claim against
(`unreported_findings`), not which findings the CODE-BUILT summary and
listing already display. Since the 2026-09-14 answer-quality fix moved
most of the "every record is represented" job onto the deterministic
summary sentence and, in Researcher mode, the record listing
(`answer_layout.py`), the model's own prose now typically grounds only a
handful of claims while the listing separately displays all `list_rows`
(11 or 20 in this batch, matching `source_count` exactly, i.e. every
admitted finding is already shown). The repair's omission check has not
been told about that second, deterministic completeness path, so it
almost always finds "omitted" findings that are not actually omitted from
the answer, and fires.

What this suggests, not implemented here: in Researcher mode, treat a
finding as reported if it appears either in the model's grounded claims OR
in the code-built listing/summary, before computing `omitted_findings`.
Risk: Plain language mode has no list (`list_rows` is 0 on every
plain_language row in this batch), so this gate would not reduce its
repair rate; a plain_language-specific completeness mechanism (widen the
summary's `MAX_SUMMARY_NAMES`, or build a plain-language equivalent of the
list) would be a separate, smaller follow-on. Also worth checking:
whether the repair still catches a genuine case the list does not cover
(the answer-quality report's own `_answer_call_ids` scoping, or truncated
Layer 2 results at the cap boundary) before removing the check, only
narrowing it.

Estimated saving if fully gated for Researcher mode (25 of the 33 answered
runs in this batch were Researcher): roughly halves the write step's
median cost on those runs (10.66s to roughly 5.0 to 6.0s), and removes the
single worst-case cost this batch measured (22.9s).

### 2. Delete plan_node's already-discarded Plan-tier call

Measured: this call's own reply is never read (`core/graph.py` says so
directly: "F-4.5-A-09... this call's RESPONSE IS DISCARDED too" and later
"THE REAL FIX IS TO DELETE THIS CALL, and it is deliberately not done
here... Filed rather than taken unilaterally", a pre-existing,
already-documented finding this task did not create). In this batch its
own step (Plan) had a median of 1.40s but a heavy tail: 4 of 34 runs spent
4.0 to 27.0 seconds on it, and one run (r2, run 1) hit the tier's full
45-second step budget and died with a transient error, refusing a
question that should have answered. That is not a hypothetical risk: it
is the one plan-tier failure this very batch reproduced, on a bare,
open-ended prompt whose only instruction is "Reply with the single word:
ok" and whose reply nothing reads.

Estimated saving: removes an entire model call from every query (median
1.4s, P90 7.5s), and removes the failure mode that produced one of this
batch's two non-write errors outright. Risk, per the code's own comment:
this call is also what triggers the per-query cost-cap pre-flight check,
so deleting it moves where that enforcement happens, which the comment
already flags as a product decision rather than a deployment one, and
that flag stands here too. Not touched in this task, since it requires
editing `core/graph.py` (outside this task's file list) and a product
decision, not just a deployment change.

### 3. Run Guard and Think concurrently

Measured: Guard's median is 2.45s, Think's is 2.59s, run strictly
sequentially today. If the two ran concurrently (Think's own tier and
entity-resolution work does not read Guard's verdict content, only
whether the query is admitted at all), the common path's cost would drop
from roughly guard+think (about 5.0s median) to max(guard, think) (about
2.6s median), a roughly 2.4-second median saving.

Risk, why this is ranked last: it is a bigger structural change than the
other two. `system-design-patterns.md` pattern 2 frames Guardrail as
gating what reaches downstream steps; running Think's real work (which
includes live NCBI symbol-resolution calls per the answer-quality report's
AQ-09) concurrently with, rather than after, Guard's admission decision
means a small fraction of guard-declined queries would still pay for a
live Think call that gets thrown away, and the LangGraph node structure
(`_build_graph`, sequential `add_node` edges) would need a fan-out/join
rather than a straight line, which is more invasive than deleting an
already-unread call. Worth doing only after items 1 and 2, and only with
an explicit measurement of how often Guard actually declines a query that
reaches it (this batch, guard declined zero of 35, but that is not
enough runs to bound the wasted-Think-call rate with confidence).

### Ruled out: Act step's slowest tool

The supplementary per-tool probe (above) measured every individual tool
call at 0.17 to 0.60 seconds, and the Act step overall at a median of
1.04s and a worst of 3.04s across the full 35-run batch. Act is not a
meaningful lever; no proposal here.

## Verify commands

Each on its own exit code, from the repository root:

```
$ python -m pytest tests/system_03_search_agent/harness -q -p no:cacheprovider
197 passed in 9.30s

$ ruff check .
All checks passed!

$ isort --check-only src tests
Skipped 2 files
```

## Files in this folder

- `measure_write2.py`: the extended measurement script (copy of the
  answer-quality report's `measure_write.py` plus `step_seconds`).
- `measure_tools.py`: the supplementary, not-part-of-the-35 per-tool timing
  probe, run after the main batch so it never shares NCBI rate-limit
  headroom with it.
- `analyze.py`: reads all 7 case files, prints the per-step breakdown, the
  live-run table, and the error/quality summaries in this report.
- `smoke_test.jsonl`, `r2.jsonl`..`r5.jsonl`, `p1.jsonl`, `p2.jsonl`: the
  35 measured runs, one JSON line each.
- `tools_probe.jsonl`: the 3 supplementary per-tool timing runs.
- `queueA.sh`, `queueB.sh`, `queueA.log`, `queueB.log`: the batch drivers
  and their stdout.
- `analysis_output.txt`: `analyze.py`'s raw stdout, the source for every
  number in this report.
