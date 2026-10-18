# Local traces: where the seconds go, call by call

Eight golden questions run locally against develop's code with develop's tier models and Jev mode (local_trace.py). Local absolute times include this machine's own start-up and network, so read the durations of calls, not the wall total.

## Step and call durations, seconds

| Question | Withdrawn | Think step | Act (plan to last tool) | Write step | Name lookups before writer | Writer call 1 | Check 1 (grounding and Jev) | Writer call 2 (repair) | Check 2 | Name lookups after | Reader pass in Act | Writer output tokens |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| G-001 | False | 3.0 | 3.2 | 9.4 | 0.0 | 3.7 | 0.0 | 5.6 | 0.0 | 0 | 0 | [503, 1331] |
| G-003 | True | 1.8 | 1.7 | 5.8 | 0.0 | 2.8 | 0.0 | 3.0 | 0.0 | 0 | 0 | [527, 619] |
| G-013 | False | 2.0 | 2.3 | 7.7 | 0.7 | 2.6 | 0.5 | 3.4 | 0.4 | 0 | 0 | [418, 682] |
| G-025 | True | 4.2 | 3.1 | 18.5 | 0.0 | 6.3 | 0.0 | 12.0 | 0.0 | 0 | 0 | [404, 1057] |
| G-026 | False | 2.0 | 0.8 | 4.5 | 0 | 2.5 | 0.0 | 2.0 | 0.0 | 0 | 0 | [451, 376] |
| G-032 | False | n/a | n/a | n/a | 0 | 8.9 | 0.4 | 9.2 | 0.0 | 0 | 0 | [900, 791] |
| G-034 | True | n/a | n/a | n/a | 0 | 1.0 | 0.0 | 2.0 | 0.0 | 0.6 | 0 | [147, 137] |
| G-038 | False | 1.9 | 0.8 | 9.3 | 0.0 | 3.0 | 0.3 | 5.6 | 0.4 | 0 | 0 | [559, 1153] |

Writer call 1: median 2.9 s. Writer call 2 fired on 8 of 8: median 4.5 s. Both writer calls together are a median 99 percent of the write step where it was bounded (6 questions).

Writer throughput: median 169 output tokens per second (range 64 to 236); output length median 543 tokens (range 137 to 1331).

## Provider prompt cache, every model call

| Call site | Calls | Prompt tokens, median | Share of prompt tokens served from cache | Calls with any cache hit |
|---|---|---|---|---|
| other: You are an input classifier for a biomedical evidence search | 8 | 801 | 35% | 4 of 8 |
| other: You are the Cypher generation step for a read-only biomedica | 1 | 1198 | 100% | 1 of 1 |
| think: classification | 8 | 994 | 62% | 6 of 8 |
| write: sentence check (guard) | 5 | 724 | 0% | 0 of 5 |
| write: synth | 16 | 11563 | 63% | 11 of 16 |

## Sentence check: Jev against the old guard-tier judge on the same sentences

| Question | Check | Candidate sentences | Jev approved | Guard judge approved | Jev call s |
|---|---|---|---|---|---|
| G-013 | 1 | 2 | 0 | 2 | 0.439 |
| G-013 | 2 | 2 | 0 | 2 | 0.39 |
| G-032 | 1 | 6 | 1 | 6 | 0.341 |
| G-038 | 1 | 8 | 1 | 8 | 0.259 |
| G-038 | 2 | 12 | 5 | 12 | 0.34 |

Totals: 30 candidates, Jev approved 7, guard judge approved 30.

## Duplicate HTTP requests inside one question (NCBI, PubTator, trials, graph)

| Question | Requests | Exact repeats | Seconds spent on repeats |
|---|---|---|---|
| G-001 | 17 | 0 | 0 |
| G-003 | 11 | 1 | 0.13 |
| G-013 | 14 | 0 | 0 |
| G-025 | 12 | 0 | 0 |
| G-026 | 11 | 1 | 0.13 |
| G-032 | 12 | 0 | 0 |
| G-034 | 11 | 1 | 0.17 |
| G-038 | 3 | 0 | 0 |
