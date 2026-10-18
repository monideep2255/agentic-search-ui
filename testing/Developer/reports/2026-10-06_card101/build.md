# Card 101 build: keep limiting words, match word forms

Builder report, 2026-10-06, branch `fix/card101-keep-limit-words` from develop f5729ec5. The owner decided on 2026-10-06 to keep card 99 and have card 101 cut its cost (`DECISIONS.md`, last rows). Two changes, both inside the brief's fence: one line in the writer's rule 3a (`synthesis/findings.py`) and a word-form rule in the pair check (`synthesis/sentence_check.py`, `check_phrases` and its helpers).

## Table of contents

- [Verdict](#verdict)
- [The change in the person's words](#the-change-in-the-persons-words)
- [What changed](#what-changed)
- [Choices for the lead to log](#choices-for-the-lead-to-log)
- [Tests and mutations](#tests-and-mutations)
- [Offline: the labelled set](#offline-the-labelled-set)
- [Replay: the 304 recorded sentences](#replay-the-304-recorded-sentences)
- [Live answers](#live-answers)
- [Gates](#gates)
- [Cache miss](#cache-miss)
- [Spend](#spend)
- [What is not covered](#what-is-not-covered)

## Verdict

| Done-when line | Result |
|---|---|
| Offline: no labelled A item gets fewer proposed pairs | Met. 0 of 18 A items get fewer; 1 gets one more; 3 trade one pair for its neighbour |
| Replay: "young children" shown as "children" and dropped "potentially" stay at 0 | Met. 0 and 0 in both runs |
| Replay: faithful sentences recovered | Small. The "variant" sentence is recovered in 2 of 2 runs; the "effective" sentence is not (its item question rejected it in both runs). Plain language 48 and 47 sentences becomes 50 and 49 |
| Live: GERD plain at least 3.0 sentences on average | Met. 5.17 counted as card 99 counts (4.5 without four copied publication lines in one answer) |
| Live: the risk-factor sentence in at least 4 of 6 GERD plain answers | Missed. 2 of 6, and both reach the screen by leaving the sphincter clause out |
| Live: "children" for "young children", dropped "potentially" | 0 and 0 in all 8 answers |
| Live: Researcher not worse than 5 sentences | Mean 5.5 (7 and 4); one answer at 4 |
| Tests red when their property is mutated | Met, 7 mutations, each red, each restored |
| Gates 02, 03, 04 | Pass |
| Spend at most $0.40 | $0.30 |

The writer line works for "young" and for the hedge and does nothing for "transient". In 6 plain-language rewordings that mention the sphincter relaxations, the writer kept "transient" in none, the same as on 2026-10-05 (0 of 9). So the risk-factor sentence, the cost the reader notices most, is still held back whenever the writer names the relaxations. That goal is missed; I did not tune the prompt toward that sentence.

## The change in the person's words

- A plain-language GERD answer now nearly always says "young children" where the paper does: the writer kept "young" in 7 of 8 such sentences, against 1 of 12 on 2026-10-05. The sentence that says it is shown instead of held back.
- A sentence such as "Symptoms that may be caused by GERD are among the most common reasons people visit primary care doctors" keeps its hedge: 7 of 7 such rewordings, against 9 of 11.
- A sentence that says "the most effective treatment" where the paper says "most effectively treated", or "specific variants" for "a specific variant", is no longer held back for that difference alone.
- Unchanged: a sentence that drops "transient" from "abnormal transient relaxations" is still held back, and the writer still drops it in plain language.

## What changed

| File | Change |
|---|---|
| `synthesis/findings.py` | Rule 3a gains one line after the nothing-more sentence: "Keep every word of the quote that limits who, how surely, how often, how long or where a claim holds, such as "young", "potentially", "transient" or "in the outpatient setting"." Fixed text in `SYNTH_SYSTEM_INSTRUCTION`, with a comment above it saying why |
| `synthesis/sentence_check.py` | New `_word_forms(word)`: the word plus what is left after taking off one ending of `PAIR_WORD_FORM_ENDINGS` (ment, ies to y, ied to y, ing, es, ed, ly, s), then a final "e", each kept only when at least `PAIR_WORD_FORM_MIN_CHARS` (5) long. In `_proposed_pairs`, a quote word counts as used when its forms share a member with the forms of any sentence word |

The plain-language depth line (card 88, beside line 1556 before this change) says "in everyday words" and "putting it in simpler words with the exact supporting words inside the marker, as rule 3a says". It defers to rule 3a and names no word to drop, so it does not contradict the new line; it is unchanged.

Commits:

- `cd9500fe` fix(sentence-check): Count another form of a quote word as used in the pair check
- `13cbb5f5` fix(writer): Ask the writer to keep every word that limits a quoted claim
- `56098e1d` fix(sentence-check): Count a ment noun as a form of its verb in the pair check
- this report, in its own commit

## Choices for the lead to log

| Choice | Alternatives considered | Why |
|---|---|---|
| Symmetric word forms: two words match when their sets of forms share a member | Strip one ending from each word and compare stems | A one-way stem gives "setting" and "settings" different stems at a five-letter floor ("sett" is too short, "setting" is kept); comparing sets matches them and the result on the labelled set is otherwise identical |
| Shortest shared part 5 characters | 3, 4 or 6 | No A item gets fewer pairs at 3 to 6. At 4, "mainly" counts as "main", "likely" as "like" and "highly" as "high", where the ending carries the limit; 4 also turned 6 existing pair-check tests red. At 6, one more faithful pair stays proposed than at 5. Price of 5: a short plural such as "bones" still differs from "bone" |
| Inflectional endings plus "ment" | Inflections only; also "ation", "ity", "er", "est" | Inflections only was run first (two replay runs, `raw/replay/inflections_only/`): "the most effective treatment" traded "most effectively" for "effectively treated" and lost its approval twice. "ment" makes "treatment" count as "treated". "er" and "est" change a degree ("younger" is not "young"), so they stay out by test. Other derivational endings were not needed by any measured case |
| One ending taken off, never two | Strip repeatedly | Bounded and predictable. Cost: "treatments" does not match "treated" |
| Writer line examples: the five limit categories plus the four measured words | Categories only; only the measured words | The brief names both. The measured words are the ones card 99 saw dropped; no test sentence is in the prompt |
| Raw live answers kept outside the repository | Commit them as card 89 did | They carry whole record text. Committed: the scripts, the per-answer summary and the candidate verdicts, which hold only the writer's sentences |

## Tests and mutations

New tests, in `tests/system_03_search_agent/synthesis/test_sentence_pair_check.py` and `test_answer_quality.py`. Each mutation was applied by a scratch runner, the named tests ran red, and the file was restored (`git diff` clean after each).

| Test | What it proves |
|---|---|
| `test_a_quote_word_the_sentence_carries_in_another_form_counts_as_used` (5 cases) | effective and effectively, variants and variant, relaxation and relaxations, treatment and treated, study and studies: no pair for the phrase |
| `test_a_word_form_match_still_asks_about_the_limit_the_sentence_drops` | The risk-factor sentence without "transient" still gets "abnormal transient" and now "transient relaxations"; "relaxations of" is gone |
| `test_a_stem_shorter_than_the_minimum_must_match_exactly` | "likely reduces" and "mainly affects" are still asked when the sentence says "like" or "main" |
| `test_a_degree_ending_is_not_a_word_form` | "younger children" for "young children" is still asked |
| `test_word_forms_are_symmetric_and_keep_the_word_itself` | Six pairs of forms match whichever side carries the ending |
| `test_rule_3a_asks_the_writer_to_keep_every_limiting_word` | Rule 3a carries the line, its categories and its four examples, with no interpolation |

| Mutation | Tests red |
|---|---|
| M1, `_word_forms` returns only the word | 6: the four inflection cases, the transient test, the symmetry test |
| M2, shortest shared part 4 | 7: the short-stem test and six existing pair-check tests whose fixture gains a pair ("bones" now matches "bone") |
| M3, "er" added to the endings | 1: the degree test |
| M4, one-sided match (quote word looked up in the sentence's forms only) | 4: three inflection cases and the transient test |
| M5, no final "e" step | 1: the symmetry test (reduce and reduced) |
| M6, "ment" removed | 2: the treatment case and the symmetry test |
| M7, the rule 3a line removed | 1: the rule 3a test |

## Offline: the labelled set

`raw/offline_word_forms.py`, no model call, the 205 items of `2026-10-05_qualifier_check/raw/eval_set.jsonl`, pairs proposed by develop f5729ec5 against this branch. Output: `raw/offline_word_forms.jsonl` and `.txt`.

| Label | Items | Pairs before | Pairs after | Items with fewer | Items with more |
|---|---|---|---|---|---|
| A, says more than its record | 18 | 108 | 109 | 0 | 1 |
| F, faithful | 144 | 765 | 737 | 19 | 6 |
| B, borderline | 23 | 223 | 227 | 1 | 3 |
| R, beyond the widened quote | 20 | 99 | 103 | 0 | 3 |

The four A items whose pairs change:

| Item | Removed | Added | Note |
|---|---|---|---|
| `d-med3-c1-i6` | none | "most affected" | One more pair |
| `w-gp1-c2-i6`, `w-gp4-c2-i6` | "most commonly" | "commonly reported" | "common" now counts as "commonly"; "symptoms potentially", the pair that catches them, stays |
| `w-cm5-c1-i8` | "10 variants" | "variants seen" | The added pair sits on the dropped "seen in greater than 1% of patients" |

Every "young children" and "symptoms potentially" pair of the labelled set is still proposed (the card 99 tests pass unchanged).

The 19 F items whose proposals shrink, by the pair removed:

- "gerd include", "include defects": `d-gerd2-c1-i5`, `w-gr1-c2-i2`, `w-gr3-c1-i6`, `w-cr4-c1-i6`.
- "infection oxidative", "oxidative stressor" (and "stressor in"): `d-med1-c2-i2`, `d-med2-c1-i1`, `w-md2-c1-i2`.
- "most effectively", "treated with": `w-gr1-c2-i3`, `w-gr4-c1-i4`, `w-gr5-c1-i6`.
- "most commonly" with "commonly reported" or "reported to": `w-gp1-c1-i5`, `w-cp3-c1-i5`.
- "outpatient setting": `d-gerd3-c2-i3`, `w-cr3-c2-i3`.
- "contributes to", "specific variant": `w-md2-c2-i3`.
- "affects quality", "gerd affects": `w-cp2-c1-i2`.
- One pair each: "limit complications" and "to limit" (`w-gr3-c1-i9`), "affected worldwide" (`w-md2-c2-i1`), "fmf variant" (`w-md2-c2-i4`).

Six F items gain pairs, the next word along now that a form matches: "infection oxidative" (`d-med3-c1-i1`, `w-md4-c1-i3`), "specific variant" and "variant contributes" (`w-md4-c2-i3`), "mediterranean fever" and "recurrent fever" (`w-md3-c2-i3`), "gastroenterology specialists" (`w-cr3-c2-i6`), and three referral pairs for `w-gr5-c2-i6`.

## Replay: the 304 recorded sentences

Scripts copied from `2026-10-06_card99/raw/live_ab/` into `raw/replay/` with only their paths changed (the .env path, the item arms read from card 99's folder). The 56 recorded checks through the shipped check with this branch's word forms, live Jev, twice. The item-question-alone arms are card 99's own runs. Final rule: 142 calls a run (56 item, 86 pair), 1,735 pairs, none unasked (inflections only: 145 calls, 1,741 pairs; card 99: 141 calls, 1,753 pairs). No check failed.

| Measure | Item question alone (card 99) | Card 99 pair check | Card 101, inflections only | Card 101, final |
|---|---|---|---|---|
| Plain language, 20 answers, sentences shown | 62 and 61 | 48 and 47 | 47 and 49 | 50 and 49 |
| GERD plain, 10 answers | 33 and 33 | 21 and 21 | 21 and 21 | 22 and 21 |
| Mediterranean plain, 10 answers | 29 and 28 | 27 and 26 | 26 and 28 | 28 and 28 |
| GERD Researcher, 9 answers | 49 and 50 | 49 and 49 | 50 and 49 | 48 and 50 |
| Sentences approved, of 304 | 145 and 143 | 122 and 122 | 119 and 119 | 121 and 127 |
| Approved by the item call, held back by a pair | | 22 and 26 | 26 and 24 | 21 and 20 |
| "young children" shown as "children" | 8 and 7 | 0 and 0 | 0 and 0 | 0 and 0 |
| Dropped "potentially" | 3 and 2 | 0 and 0 | 0 and 0 | 0 and 0 |

The "young" and hedge counts are by `raw/replay/count_limits.py` over every approved sentence; its hedge pattern counted 3 and 2 in the item arms where card 99's report says 3 and 3.

The faithful sentences card 99 lost to a word form:

| Sentence | Card 99, runs 1 and 2 | Card 101 final | Why |
|---|---|---|---|
| `md2c2i3`, "how specific variants contribute to clinical findings" | held back, held back | shown, shown | "specific variant" and "contributes to" are no longer asked; "to certain" passed both runs |
| `cp1c2i5`, "the most effective treatment, carries risks" | held back, held back | not approved, not approved | Its item question rejected it in both runs this time; a "treated with" pair voted 0.48 in run 1 |
| `gp2c1i5`, "The most effective treatment is a class of drugs" | shown, shown | shown, shown | With inflections only it lost both runs to "effectively treated"; "ment" restored it |

Of card 99's 16 costed sentences, 7 are approved in both final runs and one in one run, but only `md2c2i3` had a pair removed by this change; the others moved with Jev's run-to-run spread, as card 99's own noise table shows. Two sentences card 99 showed are held back in both final runs: `gp1c1i5` ("the outpatient" 0.29 and 0.34) and `md3c2i5` ("and their" 0.26 and 0.23). Neither had its own pair added; the batch they were asked in changed. Per sentence: `raw/replay/compare_card99.txt`.

In the person's words: on the recorded sentences the word-form rule is safe and nearly neutral, about one sentence more across ten plain-language answers. It cannot help the GERD risk-factor sentence, whose missing word is "transient", not a word form.

## Live answers

The 2026-10-05 method (`2026-10-05_wave3/sentence_check.md`): `core.run.run` locally with the real models, tools and graph, `CLASSIFIER_PROVIDER=jev`, the trace script copied to `raw/live/trace_run.py` with only its paths changed. The user database was a throwaway Postgres on port 5433 in the session scratchpad, migrated with the repository's alembic and stopped afterwards. Raw answers stay outside the repository; `raw/live/live_summary.txt` has each answer's sentences and `raw/live/live_candidates.txt` every risk-factor, "young children" and "potentially" candidate with its verdict.

Counted as card 99 counts: claim sentences on screen, without the "I found N" line.

| Answer | Seconds | Sentences shown | Risk-factor sentence shown | "children" for "young children" | Dropped "potentially" |
|---|---|---|---|---|---|
| gp1, GERD plain | 22.5 | 5 | No | 0 | 0 |
| gp2, GERD plain | 25.8 | 5 | No | 0 | 0 |
| gp3, GERD plain | 25.0 | 7 (3 written, 4 "Publication pmid ... is included") | Yes, no sphincter, adds "in children" | 0 | 0 |
| gp4, GERD plain | 18.9 | 4 | No | 0 | 0 |
| gp5, GERD plain | 20.0 | 5 | No | 0 | 0 |
| gp6, GERD plain | 37.8 | 5 | Yes, no sphincter | 0 | 0 |
| gr1, GERD Researcher | 17.0 | 7 | Yes, keeps "transient" | 0 | 0 |
| gr2, GERD Researcher | 16.6 | 4 | Yes, keeps "transient" | 0 | 0 |

| Goal | Result |
|---|---|
| GERD plain, mean sentences at least 3.0 | 5.17 (4.5 without gp3's four publication lines). Card 99's deployed proof showed 3, 4, 4, 2, 6 (mean 3.8), so part of this is run-to-run spread, not the change |
| Risk-factor sentence in at least 4 of 6 | 2 of 6. Missed |
| Researcher not worse than 5 | Mean 5.5; gr2 at 4 |
| Any widened sentence on screen | None: 0 dropped "young", 0 dropped hedge |

What the writer did with the limiting words, every check candidate counted, against the 2026-10-05 recorded runs (`gp`, `cp` and `gr`, `cr`):

| Limiting word | GERD plain, 2026-10-05 | GERD plain, card 101 | GERD Researcher, 2026-10-05 | GERD Researcher, card 101 |
|---|---|---|---|---|
| "young" kept in a sentence about children | 1 of 12 | 7 of 8 | 13 of 15 | 2 of 2 |
| A hedge kept where the quote says "potentially" | 9 of 11 | 7 of 7 | 3 of 8 | 0 of 1 |
| "transient" kept where the sentence names the relaxations | 0 of 9 | 0 of 6 | 16 of 16 | 3 of 3 |

Why the risk-factor sentence is still missing, from `raw/live/live_candidates.txt`:

- 11 plain risk-factor candidates were written. 6 name the sphincter relaxations; none keeps "transient". 4 of those were approved by the item question and held back by "abnormal transient" or "transient relaxations" (0.20 to 0.33); the other 2 were rejected by the item question.
- The other 5 leave the sphincter out. 4 were approved, and 2 of those reached the screen; the other 2 were in a draft the answer did not keep.
- The shown gp3 sentence says "Risk factors for GERD in children" where the quote names no population, and the item question approved it. That is the borderline "narrowed" class of the labelled set, not a widening.

In the person's words: the reader no longer sees "children" for "young children", and now sees the young-children sentence instead of losing it. The reader still usually does not see the list of risk factors in a plain-language answer, because the plain writer treats "transient" as a technical word to simplify, and the check treats its loss as a dropped limit. Card 99's labelled set calls that omission faithful (`w-gp5-c1-i5`). Whether a dropped "transient" should hold a sentence back is a judgement on the pair question, outside this card's fence, and is the owner's call.

## Gates

Run from the worktree with the main checkout's virtual environment first on PATH.

| Gate | Result |
|---|---|
| `gate02_import_order.sh` | Pass |
| `gate03_lint.sh` (ruff, whole repository) | Pass, "All checks passed!", after fixing four lint findings in this report's own scripts |
| `gate04_unit_suite.sh` (whole suite) | Pass: 6,996 passed, 143 skipped, 24 deselected, 1 xfailed, 0 failed, in 343 s. Load average 3.15 at the start, 8.90 at the end |

## Cache miss

Rule 3a lives in `SYNTH_SYSTEM_INSTRUCTION`, the fixed system block at the head of the cached prefix. The new line is fixed text with no interpolation, so the prefix stays byte-identical from query to query (`test_prompt_cache_prefix.py` passes). The cost is one cache miss: the first write-step call after deploy bills the prefix at the uncached rate, and later calls hit the cache again. `sentence_check.py` adds no prompt text; the pair questions are unchanged.

## Spend

| Item | Cost |
|---|---|
| Replay, inflections only, 2 runs of 145 Jev calls | $0.0847 |
| Replay, final rule, 2 runs of 142 Jev calls | $0.0844 |
| 8 live answers, by each answer's own reported total | $0.1349 |
| Total | $0.304 of $0.40 |

The model router's account usage rose $0.096 across the 8 live answers, below their own reported total, so $0.30 is the upper figure. Seven live-run launches failed on a shell word-splitting slip before any model call, at no cost.

## What is not covered

- The goal of a risk-factor sentence in 4 of 6 plain answers is missed. The two levers left are outside this card's fence: the pair question's view of "transient", or a writer change aimed at that word, which the brief rules out.
- Six plain answers and two Researcher answers, one question, one afternoon, no paired control on develop. Card 99's deployed proof (3, 4, 4, 2, 6) is the nearest baseline and is not paired.
- The Mediterranean question was not run live; the replay shows it unchanged or one sentence better.
- A hedged primary-care sentence ("Symptoms possibly caused by GERD ...") was approved by the check in the kept draft of 3 plain answers (gp2, gp3, gp5) and reached the screen in none: the grounding pass after the check did not keep it. Not investigated; it is outside the sentence check.
- Each local run ended with a `CallerIdentityRequired` error from session memory after the last event, because the trace script passes no caller identity. It is after the answer and does not change it.
- The word-form rule can still let a sentence count a hedge as kept when it uses another form of the word elsewhere ("large" for "largely"); this holds for exact matches already. No labelled item does this.
- Deep technical depth was not run.
