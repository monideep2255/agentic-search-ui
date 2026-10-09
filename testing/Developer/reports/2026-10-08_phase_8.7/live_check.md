# Phase 8.7 live check, the writer's finalist round

The small finalist check the owner asked for in place of a full bench (`DECISIONS.md`, 2026-10-08), run by the lead on the phase branch at 72ab2cd9 on the night of 2026-10-08 to 09. The agent loop ran locally against the real models, the live graph (read only) and the live NCBI and enrichment APIs, with `SYNTH_MODEL=anthropic/claude-opus-5.5` and `PER_QUERY_COST_CAP_USD=0.25`.

## Table of contents

- [In one minute](#in-one-minute)
- [What was run](#what-was-run)
- [Results](#results)
- [What this does not cover](#what-this-does-not-cover)

## In one minute

| Question | Answer |
|---|---|
| Spend | $3.67 of the $20 ceiling, read from the credits endpoint before (00:11 UTC, $36.11 left) and after (02:00 UTC, $32.44 left) |
| Any question over 25 cents? | No. The most expensive was $0.208; the mean answered question $0.151 |
| Records on screen sooner? | Yes, on the streaming path the web app uses: first records at a median 9.3 s (2.9 to 14.1 s), the whole answer at a median 27.3 s (14.1 to 30.9 s) |
| Does the first sentence answer? | With the Jev classifier on, as develop runs: in 2 of 8 runs a checked sentence leads (the Marfan features question, both modes); in the other 6 the count line leads, as design C keeps it when no accepted sentence answers better |
| Hidden instructions refused? | Yes, query 88's forged transcript, 2 of 2 |
| Written summary kept? | Every answered run carried 2 to 8 written paragraphs beyond the count line, by a rough count over the saved answer texts; a withdrawn summary was not measured directly. Outcomes were answer or ask throughout, and refuse only for query 88 and query 75's ask-back |

## What was run

- Two passes of twelve questions through the buffered path (`run()`), with the classifier the local settings name (the guard tier). This path yields every event at the end, so its timings are the whole answer's, not the records'.
- One pass of eight of them through the streaming path (`run_streaming()`, as the web app), with `CLASSIFIER_PROVIDER=jev`, as develop sets it.
- Questions, from `testing/Test_queries_and_workflows.md`: 1 (both modes), 16, 22, 23, 64, 66 (both modes), 72, 73, 75 and 88.
- Raw rows: `live/buffered_runs.jsonl` and `live/streaming_runs.jsonl`; the runner: `live/runner.py`.

## Results

| Query | Mode | First records (s) | Whole answer (s) | Cost ($) | How it opens |
|---|---|---|---|---|---|
| 1 | Researcher | 9.17 | 27.88 | 0.183 | Count line naming the four diseases |
| 1 | Plain | 11.58 | 30.88 | 0.184 | "I found 4 conditions related to BRCA1" |
| 16 | Researcher | 11.79 | 20.31 | 0.087 | Count line |
| 22 | Researcher | 6.15 | 14.11 | 0.083 | Count line |
| 66 | Plain | 14.13 | 30.44 | 0.174 | "MedGen lists these clinical features: Aortic regurgitation, Arachnodactyly, ..." |
| 66 | Researcher | 9.46 | 26.77 | 0.178 | The same features sentence |
| 72 | Plain | 2.92 | 24.39 | 0.191 | "I found 5 clinical trials related to GERD" |
| 73 | Plain | 6.59 | 28.52 | 0.208 | "I found 5 published papers on this topic" |

Streaming pass only. The buffered passes add query 23 (rs334 still lists its near misses on this branch, since card 37 merged to develop separately tonight), 64, 75 (asked back "How far back should I search?") and 88 (refused).

## What this does not cover

- Eight streaming runs and 24 buffered runs, not the plan's five repeated runs per step; the owner set the $20 ceiling and a small finalist check.
- The local runs carry no signed-in owner, so their history capture was refused by design; saving and reopening are covered by the unit suite and by the product check after merge.
- No golden run, at the owner's choice.
- Card 14: no run passed 60 seconds; the slowest whole answer was 58.6 s (query 66 in Plain language, buffered pass).
