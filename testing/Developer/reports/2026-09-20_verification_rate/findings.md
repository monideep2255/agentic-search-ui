# Verification-rate measurement, 2026-09-20

## Table of contents

- [What this measures](#what-this-measures)
- [Result](#result)
- [Breakdown by question](#breakdown-by-question)
- [Breakdown by depth](#breakdown-by-depth)
- [Quoted evidence](#quoted-evidence)
- [The other two notes](#the-other-two-notes)
- [The single most useful thing the data says](#the-single-most-useful-thing-the-data-says)
- [Method](#method)
- [Reviewer's independent recomputation, and one correction to the lead's own hypothesis](#reviewers-independent-recomputation-and-one-correction-to-the-leads-own-hypothesis)

## What this measures

`src/system_03_search_agent/core/graph.py`, `_build_structured_fallback_note()`, emits the note "Note: the written summary of these records could not be verified against them, so this answer lists the records found instead" only when `write_node` discarded the model's prose and shipped a code-built, per-finding narrative instead. This run measures how often that happens on live develop, against 30 real runs: the five named questions, each run three times in `researcher` and three times in `plain_language`.

## Result

Fallback note fired on 7 of 30 runs (23 percent).

| Note | Runs it fired on | Rate |
|------|-------------------|------|
| Structured fallback (`could not be verified`) | 7 / 30 | 23% |
| Truncation (`this result was truncated`) | 24 / 30 | 80% |
| Partial answer / placeholder (`are not described above`) | 22 / 30 | 73% |

All 30 runs completed with `trust_outcome: ask` and returned at least 13 sources. No transport errors, no fatal errors, no blocked runs.

## Breakdown by question

| Question | Fallback fired | Total |
|----------|-----------------|-------|
| Which diseases are associated with BRCA1? | 0 | 6 |
| What diseases are caused by variants in the HNF1A gene? | 1 | 6 |
| Variants in GCK causing MODY | 0 | 6 |
| What genes are associated with MODY? | 5 | 6 |
| Show the dbSNP record for rs28934578 in TP53 | 1 | 6 |

"What genes are associated with MODY?" carried the fallback note in 5 of its 6 runs, by far the concentration point. Two of the five questions (BRCA1, GCK) never triggered it at all across 6 runs each.

## Breakdown by depth

| Depth | Fallback fired | Total | Rate |
|-------|-----------------|-------|------|
| researcher | 5 | 15 | 33% |
| plain_language | 2 | 15 | 13% |

Researcher depth fired the note roughly 2.5x as often as plain_language, though the sample is small (15 runs each) and the effect is dominated by one question (MODY genes) rather than spread evenly.

## Quoted evidence

Positive case, "What diseases are caused by variants in the HNF1A gene?" [researcher] run 3 (elapsed 127.1s, an outlier versus the other 29 runs which ran 7 to 23 seconds):

```
ws; the rest are not shown above.

Note: the written summary of these records could not be verified against them, so this answer lists the records found instead

Note: this answer does not address
```

The exact substring `could not be verified` is present verbatim in the reassembled token stream. Full per-run answer text and the raw event-derived fields are in `runs.json`.

## The other two notes

Both of the other notes fire far more often than the fallback note: truncation on 24 of 30 runs, and the partial-answer/placeholder note on 22 of 30. These are not the same signal as the fallback note. Truncation only says the graph result set was larger than what got shown; partial-answer only says the question named more entities than the answer addressed. Neither implies the model's own prose was thrown away. They co-occur with fallback in some runs (see the HNF1A run 3 quote above, where both fire together) but are independently much more common, meaning most runs are NOT losing their synthesized narrative, they are just disclosing an incomplete or capped result set on top of a real, kept narrative.

## The single most useful thing the data says

The fallback note is not the dominant story: it fired on less than a quarter of runs (23%), heavily concentrated in one question ("What genes are associated with MODY?", 5 of 6 runs) rather than spread across the board. Two of five questions never triggered it at all. This means the product owner's "answers look surface level" complaint is NOT well explained by synthesis being discarded in general. It IS well explained for MODY-gene-style multi-entity list questions specifically, where something about that query shape (broad, multi-hop, high entity count) is reliably defeating grounding. The much higher rates for the truncation and partial-answer notes (80% and 73%) suggest incompleteness disclosure, not verification failure, is the more universal source of a "thin" reading experience: most answers keep their synthesized prose but immediately follow it with a note that the result set was capped or partial, which reads as surface-level even when the underlying sentences were model-written and grounded.

## Method

- Script: an adapted copy of `testing/Developer/reports/2026-09-19_verification/measure_with_errors.py`'s auth/post/stream mechanics (unchanged), with new collection logic that reassembles every `token` event's `payload.text` in emission order into one string per run and searches it for the three note substrings by exact match.
- Base URL confirmed live and reachable before the full run: `https://search-agent-api-develop-43b3.up.railway.app` (`POST /auth/guest` returned 201).
- 30 runs total, 3-second pacing between runs, fresh guest session per run.
- No credential value logged or written anywhere; only the fact that a guest token was obtained.
- Raw per-run data, including full reassembled answer text (capped at 4000 chars for file size, none needed it) and the boolean flag for each note per run: `runs.json` in this directory.
- Console log of the live run: `run_log.txt` in this directory.

## Reviewer's independent recomputation, and one correction to the lead's own hypothesis

Added by the lead after the measurement, recomputing every rate from each run's
raw `answer_text` rather than from the booleans the measuring agent wrote. The
numbers match exactly, which is what makes them worth acting on:

| Note | Runs | Rate |
|---|---|---|
| `could not be verified` (synthesis discarded) | 7 of 30 | 23 percent |
| `this result was truncated` | 24 of 30 | 80 percent |
| `are not described above` | 22 of 30 | 73 percent |

THE LEAD'S HYPOTHESIS WAS WRONG AND IS RECORDED RATHER THAN QUIETLY DROPPED.
Going in, the reasoning was that the verification-discard note explained the
product owner's "answers look surface level" verdict, because when it fires the
reader is served a code-built record list instead of a synthesized answer. It
fires on under a quarter of runs, and it is not spread evenly: five of its seven
occurrences are one question, "What genes are associated with MODY?", and two of
the five questions never triggered it once in six runs each. It is a real defect
with a specific shape, not the general cause.

TWO THINGS THE RAW DATA SAYS THAT THE RATES ALONE DO NOT.

First, the source count across all 30 runs ranges from 13 to 20 with a mean of
15.8, and 20 is exactly the citation cap. Answers are routinely reaching the
ceiling, which is why the incompleteness notes fire on three quarters of runs.
The cap is not a background setting here, it is the thing generating the
dominant reader-visible symptom, and it is already on the product owner's own
open-decision list.

Second, one run took 127.1 seconds against a median of 13.6 and a stated latency
budget of 53 seconds. That is not a rounding error and nothing currently owns it.

WHAT THIS REDIRECTS. The universal symptom is not discarded synthesis, it is
answers that keep their prose and then immediately tell the reader the result
was capped and some records were not described. The question worth asking next
is not "why is synthesis discarded" in general, but two narrower ones: why a
broad multi-entity list question defeats grounding specifically, and whether the
20-source cap is set where the product owner actually wants it.
