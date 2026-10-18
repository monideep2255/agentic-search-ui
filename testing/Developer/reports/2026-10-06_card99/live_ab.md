# Card 99 live A/B: the pair check on the same sentences

Measured on 2026-10-06 on develop at b930512a, which contains card 99 (merged as #184).

The question: does the pair check change how many of the same sentences a person sees? Every answer was counted at both depths.

Each arm ran twice, so the difference can be set against the model's own run-to-run noise. The evidence is in `raw/live_ab/`:

- `ab_run.py` rebuilds the checks and runs the arms.
- `ab_analyse.py` builds the tables.
- `run_<arm>_<run>.jsonl` holds every call's answers and probabilities.

## Table of contents

- [Answer](#answer)
- [Method](#method)
- [Sentences shown, per depth](#sentences-shown-per-depth)
- [Every sentence the pair check dropped](#every-sentence-the-pair-check-dropped)
- [Noise floor](#noise-floor)
- [Calls, time and spend](#calls-time-and-spend)
- [What is not covered](#what-is-not-covered)

## Answer

| Question | Plain language (20 answers) | Researcher depth (9 answers) |
|---|---|---|
| Sentences shown, item question alone, run 1 and run 2 | 62 and 61 (mean 3.10 and 3.05 an answer, range 0 to 7) | 49 and 50 (mean 5.44 and 5.56, range 2 to 9 and 3 to 9) |
| Sentences shown, item question plus pairs, run 1 and run 2 | 48 and 47 (mean 2.40 and 2.35, range 0 to 6) | 49 and 49 (mean 5.44, range 2 to 9) |
| Change | 14 fewer each run, about one sentence in four | None |
| Noise between two identical item-only runs | 1 sentence in total (one answer, by one) | 1 sentence in total (three answers, by one each, net 1) |
| Answers that lose all written prose only because of the pair check | None | None |
| Sentences lost because the call cap left them unasked | 0 | 0 |

In the person's words:

- A Researcher depth answer is unchanged. Researcher sentences keep "young children" and keep the hedge, so no pair objects.
- A plain-language GERD answer shows about one sentence fewer: an average of 3.3 sentences becomes 2.1.
  - Half of what goes is the widening card 99 was built to stop: "In children" for "in young children", and a symptom the paper only suspects of being GERD's shown as GERD's.
  - The other half is faithful sentences, mostly the risk-factor sentence.
- A plain-language Mediterranean answer barely moves: 29 and 28 sentences across ten answers become 27 and 26.
- No answer falls to the bare record list because of the pair check.

The cost a reader would notice most is in the GERD question, which asks for symptoms and risk factors. One sentence lists the risk factors ("abnormal relaxations of the lower esophageal sphincter, ... hiatal hernia").

- It is shown in 6 of 10 plain-language GERD answers with the item question alone, and in 1 of 10 with the pair check.
- The writer drops "transient" from the record's "abnormal transient relaxations" in almost every plain rewording, and the pair check holds that back.
- The one that survives (cp2) leaves the sphincter out altogether. It shares no word with the phrase, so no pair is asked about it.

## Method

- Source: `testing/Developer/reports/2026-10-05_wave3/sentence_check_raw/`, the branch runs (gp, gr, md) and the develop control runs (`develop_control/`: cp, cr, cm). Each `CHECK_IN` line is one call of `check_reworded_sentences`, with every candidate's sentence, quotes and writer quotes.
- Recovered: 56 checks and 304 candidates across 29 answers (cr2 failed before its check). Plain language: 39 checks, 199 candidates, 20 answers. Researcher: 17 checks, 105 candidates, 9 answers.
- Proof the input is what the check received: the shipped `build_jev_state` builds an item state byte-identical to the live recorded one in all 56 checks, and the shipped packing proposes 1,753 pairs in 85 pair calls, the verifier's figure.
- Arms, both through the shipped module with live Jev calls: item question alone (`_proposed_pairs` patched in the script to return no pairs, exactly the check before card 99, 56 calls a run), and item question plus pairs (unchanged, 141 calls a run). Order: item 1, pairs 1, item 2, pairs 2. `PER_QUERY_COST_CAP_USD` was 1.0 for the replay.
- What "shown" means: the writer and grounding were not rerun, so the draft shown live is rebuilt from the trace. Model A, used in every table unless named: the same draft is shown in every arm. Model B, a bound: the draft with more sentences in that arm is shown; it moves plain language to 64 and 63 with the item question alone against 54 and 53 with pairs.

## Sentences shown, per depth

| Depth | Arm | Run 1 total | Run 2 total | Mean an answer | Range |
|---|---|---|---|---|---|
| Plain language, 20 answers | Recorded live on 2026-10-05 | 58 | | 2.90 | 0 to 6 |
| Plain language | Item question alone | 62 | 61 | 3.10, 3.05 | 0 to 7 |
| Plain language | Item question plus pairs | 48 | 47 | 2.40, 2.35 | 0 to 6 |
| Plain language | Same pairs run, its item call alone | 62 | 64 | 3.10, 3.20 | 0 to 7 |
| Plain language, model B | Item alone against pairs | 64 against 54 | 63 against 53 | 3.20 against 2.70 | 0 to 7 against 0 to 6 |
| Researcher, 9 answers | Recorded live on 2026-10-05 | 47 | | 5.22 | 1 to 9 |
| Researcher | Item question alone | 49 | 50 | 5.44, 5.56 | 2 to 9, 3 to 9 |
| Researcher | Item question plus pairs | 49 | 49 | 5.44 | 2 to 9 |

Plain language by question:

| Question | Item alone, run 1 and 2 | With pairs, run 1 and 2 |
|---|---|---|
| GERD, plain (gp, cp, 10 answers) | 33 and 33 (3.3 an answer) | 21 and 21 (2.1 an answer) |
| Mediterranean, plain (md, cm, 10 answers) | 29 and 28 | 27 and 26 |

Across all 56 checks:

| Class | Item alone, run 1 and 2 | With pairs, run 1 and 2 |
|---|---|---|
| Sentences approved, of 304 | 145 and 143 | 122 and 122 |
| "young children" shown as "children" | 8 and 7 | 0 and 0 |
| "Symptoms potentially attributable to GERD" stated as GERD's symptoms | 3 and 3 | 0 and 0 |
| Sentences on that primary care record that keep the hedge | 10 and 10 | 7 and 7 |

## Every sentence the pair check dropped

27 distinct sentences, all plain language, that a pairs run's own item call approved and a pair then vetoed. The full table, with each sentence, its quote, the vetoing pairs and their probabilities, is `raw/live_ab/dropped_rows.md`. Tally, one reader's verdicts:

| Verdict | Sentences | On screen in run 1 | In run 2 |
|---|---|---|---|
| Good, "young children" to "children" | 8 | 7 | 8 |
| Good, the "potentially attributable" hedge dropped | 3 | 1 | 1 |
| Cost, "transient" dropped from the risk-factor list | 7 | 5 | 5 |
| Cost, primary care sentence that kept its hedge | 4 | 0 | 0 |
| Cost, other faithful wording | 5 | 1 | 3 |
| Total | 27 | 14 | 17 |

- Good: 11 of 27, every one in the two classes card 99 targets. With pairs, neither class was approved in either run.
- Cost: 16 of 27. Five also carry a separate borderline wording the pair did not name. Two come from word forms the pair builder treats as different words: "effective" and "effectively", "variants" and "variant".
- "Transient" is judged a cost because card 99's labelled set labels that omission faithful (`w-gp5-c1-i5`). A reader who counts it as a dropped limit would move 7 sentences from cost to good.

## Noise floor

| Comparison | Plain language, answer totals | Researcher, answer totals | Candidate verdicts that differ, of 304 |
|---|---|---|---|
| Item alone, run 1 against run 2 | 62 against 61; 1 answer differs, by 1 | 49 against 50; 3 answers differ, by 1 each | 10 |
| With pairs, run 1 against run 2 | 48 against 47; 5 answers differ, by 1 each | 49 against 49; none | 10 |
| Four item-question readings | 62, 61, 62, 64 | 49, 50, 49, 49 | 20 change at least once |

At plain language the pair check removes 14 sentences each run, more than ten times the item question's own run-to-run movement. At Researcher depth the difference is inside the noise.

## Calls, time and spend

| Run | Checks | Calls | Pairs asked | Median check time | Slowest check | Spend |
|---|---|---|---|---|---|---|
| Item alone 1 | 56 | 56 | 0 | 234 ms | 357 ms | $0.0051 |
| Item alone 2 | 56 | 56 | 0 | 236 ms | 405 ms | $0.0051 |
| With pairs 1 | 56 | 141 | 1,753 | 328 ms | 444 ms | $0.0425 |
| With pairs 2 | 56 | 141 | 1,753 | 332 ms | 1,390 ms | $0.0425 |

One check failed closed (pairs run 1, cr5 check 2, an `http_error` on the item call) and was rerun once. The call cap left no sentence unasked; the most pair calls any check needed was 3. Total spend $0.096 across 396 billed calls.

## What is not covered

- Only the sentence check was replayed; "shown" is rebuilt from the live trace.
- Two questions from one recorded day. Deep technical depth was not run.
- The control runs carry the writer's narrow quotes from before card 89; the GERD plain result holds for both (gp 18 to 10 and 11, cp 15 to 11 and 10).
