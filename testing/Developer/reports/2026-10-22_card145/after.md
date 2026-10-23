# Card 145 after: a first question is read again before it is asked back

Card 145's change, measured on 2026-10-22 with develop's pinned models (Jev classifier, guard and plan tier deepseek-v4-flash, synth tier glm-5.2), the 25-cent per-question cap and live NCBI. The change: when Think is about to ask "which gene, variant or condition do you mean?" on a first question because it read no subject, it runs the Think classification and live confirmation once more (`_read_question_again`, `core/graph.py`), and asks back only if that reading also resolves nothing. The baseline is `before.md`.

## Table of contents

- [Summary](#summary)
- [Fix round](#fix-round)
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

In the person's words: the bronchiolitis question was asked which gene they meant on 3 of 10 readings before, and on 2 of 25 after the first build. An ordinary question never paid for the second reading, and no measured answer passed 20 seconds. The fix round's numbers are in [Fix round](#fix-round); the sections after it are the first build's.

## Fix round

The judge (`judge.md`) and adversary (`adversary.md`) failed the first build. The owner's terms for the one fix round (`DECISIONS.md`, 2026-10-22): "the second reading counts only if every subject it names is written word for word in the question, it runs the same organism checks as the first reading, it gets at most 4 s, the answer's record says it was used, and each trigger condition gets a test".

### What changed

| Finding | What the person would have seen | Fix |
|---|---|---|
| A-145-01 | "Is it dangerous?" answered about cystic fibrosis, a subject they never named | A second reading is taken only if every span a record was bound from, every organism span and every rejected symbol is written in the question as a whole phrase, ignoring case (`_written_in_question`, `_second_reading_usable`) |
| A-145-04 | A SARS-CoV-2 sequencing question answered with records about the disease SARS | "SARS" inside "SARS-CoV-2" is not a whole phrase, so that reading is discarded; and the second reading now runs the first reading's own checks (below) |
| A-145-05 | A second reading that named the organism correctly still asked for a gene | Think's per-reading resolution moved verbatim into `_resolve_reading`, which both readings run: confirmation, organism spans, gene fallback, card 56's organism anchor, disease fallback with its joined-name skip |
| J-145-01 | An ask-back question could wait up to about 45 s | The second reading gets min(4 s, what is left of Think's deadline), then asks back |
| A-145-02 | No trace that a second reading was used | A `think.second_reading` entry in the `done` event's decisions, for example `resolved: croup` (the record's contract allows only "jev" or "guard" as decider, so it carries "guard" with a `fallback_reason` saying the plan tier read again) |
| J-145-04 | An NCBI error in the second confirmation turned an ask-back into a failed query | Any error in the second reading asks back |
| J-145-05 | A failed second reading logged "step failed step=think" | `_run_think_classification(second_reading=True)` logs at info |
| A-145-06 | An invented subject written to session memory | Follows from A-145-01; a test pins that the plan event and citations stay empty |
| J-145-02, J-145-03, J-145-06 | Trigger conditions and the call-site deadline unpinned | One test per trigger condition (memory, window, accession, isolate, organism, typed identifier, resolved, rejected symbol, referring word), a 4 s cap test, a call-site deadline test. Each of 16 code mutations turns at least one test red |

Left as they were, by the coordinator's instruction: J-145-02's narrowing to first turns, J-145-08 (Layer 2 calls charged to the question) and J-145-09 (two draws on a dangling question). Not covered by word for word, and named here so it is not read as fixed: A-145-03, a second reading that tags an ordinary word the question does contain ("dangerous" in "Is it dangerous?") as a disease still binds MedGen records titled with that word, exactly as a first reading that did so would.

### Measured after the fix round

| Run | Result |
|---|---|
| Think alone, 10 readings (`raw/fix_think.jsonl`) | Second reading fired on 3 (runs 2, 5, 6), recovered 2 (bronchiolitis, word for word), asked back 1 (both readings empty, 6.0 s of Think) |
| Full runs, 3 of the bronchiolitis question (`raw/fix_full_bronch.jsonl`) | 3 of 3 answered, 20 citations each, 6.7, 8.4 and 8.3 s to done; the first reading resolved each time, so the second reading did not fire and no `think.second_reading` entry was recorded |
| Slowest Think | 12.1 s on run 10 of the Think-alone batch, a first reading alone (the second did not fire) |

Across both rounds, after the change, the bronchiolitis question was asked back on 3 of 38 measured readings and runs, against 3 of 10 before. The recovered path end to end through Write is still unmeasured live (J-145-07): no full run drew an empty first reading.

Spend this round: 0.0181 dollars by the key's usage read before and after each batch (0.0008 and 0.0173); the three full runs' own cost fields sum to 0.0289, so the key's usage figure may lag.

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
