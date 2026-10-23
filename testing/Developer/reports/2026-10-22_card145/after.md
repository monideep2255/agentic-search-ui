# Card 145 after: a first question is read again before it is asked back

Card 145's change, measured on 2026-10-22 with develop's pinned models (Jev classifier, guard and plan tier deepseek-v4-flash, synth tier glm-5.2), the 25-cent per-question cap and live NCBI. The change: when Think is about to ask "which gene, variant or condition do you mean?" on a first question because it read no subject, it runs the Think classification and live confirmation once more (`_read_question_again`, `core/graph.py`), and asks back only if that reading also resolves nothing. The baseline is `before.md`.

## Table of contents

- [Summary](#summary)
- [Think alone, 20 readings](#think-alone-20-readings)
- [Full runs of the bronchiolitis question](#full-runs-of-the-bronchiolitis-question)
- [Full runs of two ordinary questions](#full-runs-of-two-ordinary-questions)
- [Spend](#spend)
- [What this does not settle](#what-this-does-not-settle)

## Summary

| Measure | Before | After |
|---|---|---|
| Bronchiolitis asked back, Think alone | 3 of 10 | 1 of 20 |
| Bronchiolitis asked back, full runs | not run | 1 of 5 |
| Second reading fired, bronchiolitis (all after runs) | not built | 3 of 25, recovered 1 |
| Second reading fired, ordinary questions | not built | 0 of 6 |
| Think calls per ordinary question | 1 | 1 on every run |
| Slowest measured answer to done | not run | 12.0 s |

In the person's words: the bronchiolitis question was asked which gene they meant on 3 of 10 readings before, and on 2 of 25 after. An ordinary question never paid for the second reading, and no measured answer passed 20 seconds.

## Think alone, 20 readings

`think_probe.py`, the same script as `before.md`, run twice for 10 readings each because the first batch never reached the new path (raw rows: `raw/after_think.jsonl`, `raw/after_think_b.jsonl`).

| Batch | First reading empty | Second reading resolved | Asked back | Slowest Think |
|---|---|---|---|---|
| a | 0 of 10 | not reached | 0 | 2.6 s |
| b | 2 of 10 (runs 4 and 7) | 1 of 2 (run 7: bronchiolitis, disease) | 1 (run 4: both readings empty) | 7.9 s (run 4, both readings) |

When the second reading resolved, it bound the same 8 MedGen records the first reading binds when it names the condition.

## Full runs of the bronchiolitis question

`full_runs.py`, five first questions through `core.run.run_streaming()` (the web app's path, `reads_placement=True`, Plain language). Raw rows: `raw/after_full_bronch.jsonl`.

| Run | Answered | Trust outcome | Citations | First token | Done | Think calls | Second reading |
|---|---|---|---|---|---|---|---|
| 1 | yes | answer | 20 | 4.1 s | 10.4 s | 1 | no |
| 2 | yes | ask | 19 | 2.9 s | 5.7 s | 1 | no |
| 3 | yes | ask | 12 | 5.8 s | 7.9 s | 1 | no |
| 4 | no, asked back | refuse | 0 | 6.0 s | 6.0 s | 2 | yes, found nothing |
| 5 | yes | answer | 20 | 3.5 s | 5.7 s | 1 | no |

Run 4's two readings both returned no entity, so it was asked back as before, in 6.0 s.

## Full runs of two ordinary questions

Three first questions each, the same path. Raw rows: `raw/after_full_brca1.jsonl`, `raw/after_full_q1.jsonl`. Query 1 is from `testing/Test_queries_and_workflows.md`.

| Question | Run | Trust outcome | Citations | First token | Done | Think calls | Second reading |
|---|---|---|---|---|---|---|---|
| What does the BRCA1 gene do? | 1 | answer | 19 | 2.4 s | 6.3 s | 1 | no |
| What does the BRCA1 gene do? | 2 | flag | 21 | 2.5 s | 12.0 s | 1 | no |
| What does the BRCA1 gene do? | 3 | answer | 19 | 5.1 s | 9.0 s | 1 | no |
| Which diseases are associated with BRCA1? | 1 | ask | 27 | 5.9 s | 9.2 s | 1 | no |
| Which diseases are associated with BRCA1? | 2 | ask | 29 | 4.1 s | 6.8 s | 1 | no |
| Which diseases are associated with BRCA1? | 3 | ask | 27 | 3.2 s | 6.0 s | 1 | no |

The second reading never fired and each run made one Think call, so these questions made exactly the model calls they made before the change; the only added work on their path is the trigger's condition check. No before-change full runs of these two were made tonight, so "times unchanged" rests on the identical call count, not on a timed comparison.

## Spend

Read from the key's usage before and after each batch.

| Batch | Dollars |
|---|---|
| Before, trial reading and 10 readings | 0.0109 |
| After, Think alone, 20 readings | 0.0242 |
| After, 5 bronchiolitis full runs | 0.0460 |
| After, 3 plus 3 ordinary full runs | 0.0554 |
| Total | 0.1365 |

## What this does not settle

- The rate is lowered, not ended: two readings that both return no entity still ask back (2 of 25 after). On this question both readings ran on the same messages to the same model, and the 3 second readings measured recovered only 1, so the two readings may not fail independently. Fix B in the diagnosis (the own-subject classifier) is the complement and was not built, by the owner's decision.
- The second reading is bounded by what is left of Think's own step budget (45 s from Think's start), the same deadline the first reading runs under. Measured, the path with both readings took 7.9 s of Think and 6.0 s to done, but the bound itself is wider than the 20-second answer rule.
- 25 bronchiolitis readings is a small sample for a rate near one in ten.
