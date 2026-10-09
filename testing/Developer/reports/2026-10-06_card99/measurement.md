# Card 99: the pair check measured on the full evaluation set

Lead measurement, 2026-10-06, the step the owner asked for on 2026-10-05: measure the pair check (option 4 of `testing/Developer/reports/2026-10-05_qualifier_check/design.md`) on all 144 faithful rewordings before deciding whether to ship it.

## Table of contents

- [What the person sees](#what-the-person-sees)
- [How it was run](#how-it-was-run)
- [Results](#results)
- [The faithful rewordings it loses](#the-faithful-rewordings-it-loses)
- [The addition it misses](#the-addition-it-misses)
- [What was not covered](#what-was-not-covered)

## What the person sees

| Today | With the pair check |
|---|---|
| 9 of the 13 sentences that drop or loosen a limit from the record are shown, "young children" as "children" among them | None of the 13 is shown, in two runs |
| 125 of 144 faithful rewordings are shown | 119 of 144 are shown: 6 more are held back, mostly sentences that leave out a setting such as "in the outpatient setting" |

## How it was run

- The script and evaluation set of 2026-10-05, unchanged: `testing/Developer/reports/2026-10-05_qualifier_check/raw/offline_qualifier_judge.py perpair`, with `PERPAIR_ITEMS` set to all 205 items.
- 1,194 pairs, 40 Jev calls a run, two runs: `raw/offline_perpair_full1.jsonl` and `raw/offline_perpair_full2.jsonl` in that folder. Run 2 lost one call to a Jev timeout and resumed from the saved pairs.
- A sentence ships only when today's sentence check approves it and every pair says no. Today's verdicts are the baseline already measured in `offline_second.jsonl` (`says_more_ok`).
- Spend: about $0.025 a run, $0.05 in all. Latency 293 to 1,293 ms a call of 30 pairs.

## Results

| Label | Items | Today's check approves | Both approve, run 1 | Both approve, run 2 | Target |
|---|---|---|---|---|---|
| A, a sentence that says more than its record | 18 | 10 | 1 | 1 | 0 |
| F, faithful rewording | 144 | 125 | 119 | 119 | as many as possible |
| R, beyond the widened quote | 20 | 2 | 2 | 2 | 0 |
| B, borderline | 23 | 14 | 10 | 9 | reported only |

The A items by kind:

| Kind | Items | Today approves | Both approve, both runs |
|---|---|---|---|
| Dropped qualifier ("young children" as "children") | 9 | 8 | 0 |
| Dropped hedge | 3 | 1 | 0 |
| Dropped condition, loosened frequency, reframed, other record, added explanation | 5 | 0 | 0 |
| Added population ("in adults") | 1 | 1 | 1 |

Stability: the two runs disagree on 10 of 1,194 pair verdicts and on no A outcome; two faithful items swap (w-cr4-c2-i5 lost in run 1 only, w-gp1-c1-i5 in run 2 only).

## The faithful rewordings it loses

Six in each run, seven distinct across the two:

| Item | Pair flagged | What the sentence leaves out |
|---|---|---|
| w-gp1-c1-i5 (run 2 only) | the outpatient | the outpatient setting |
| w-gp3-c1-i6 | the outpatient (and, in run 1, attributable to) | the outpatient setting |
| w-cp3-c2-i4 | the outpatient | the outpatient setting |
| d-med2-c2-i4, w-md2-c2-i3 | to certain, certain clinical | "certain" clinical features |
| w-gp5-c1-i5 | from abnormal, abnormal transient, transient relaxations | "abnormal transient" relaxations |
| w-cr4-c2-i5 (run 1 only) | gerd in | a "GERD in" phrase |

Most are a setting or a "certain" the writer left out. The design labelled these faithful, but each is a limit the record sets, so a reader could fairly call several of them correct rejections.

## The addition it misses

d-gerd1-c1-i2: "Heartburn and regurgitation are the hallmark clinical features of GERD in adults", where the record never says "in adults". The pair check looks for a word the sentence drops, so an added word is outside what it can see. On 2026-10-05 it was rejected only because an unrelated pair, "the typical", came out at 0.49 against 0.51 in both runs. So the earlier "0 of 18 twice" was partly luck, and the honest figure is 1 of 18. An added population is today's sentence check's job, and it misses this one too.

## What was not covered

- Batches of 30 pairs, not the live 4 to 8 items; batch size is known to move Jev's verdicts.
- No live answer was run; the design's next step after a yes is five or more live runs a question at plain language.
- Option 5, the writer's prompt line to keep limiting words, was not measured.
