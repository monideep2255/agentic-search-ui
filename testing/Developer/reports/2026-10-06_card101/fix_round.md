# Card 101 fix round

Fix agent, one fix-and-verify round, 2026-10-06, branch `fix/card101-keep-limit-words`. The owner decided (`DECISIONS.md`, last row): drop the word-form matching entirely, keep the writer line with neutral examples taken from no test question, and measure on GERD and on a question outside the test set.

## Table of contents

- [Verdict](#verdict)
- [Per finding](#per-finding)
- [What changed](#what-changed)
- [The examples and their grep](#the-examples-and-their-grep)
- [Test and mutation](#test-and-mutation)
- [GERD plain language, branch](#gerd-plain-language-branch)
- [Held-out question, branch against develop](#held-out-question-branch-against-develop)
- [Gates](#gates)
- [Cache miss](#cache-miss)
- [Spend](#spend)
- [What is not covered](#what-is-not-covered)

## Verdict

| Check | Result |
|---|---|
| Word-form matching removed | Yes. `git diff origin/develop` on `sentence_check.py` and its test file is empty |
| Writer line examples neutral | Yes. "elderly", "probably", "rarely", "for up to a week", "in mice": 0 hits in the test questions, both golden files, the 2026-10-05 recorded records and card 99's labelled set |
| GERD: "children" for "young children" on screen | 0 in 6 answers |
| GERD: dropped "potentially" on screen | 0 in 6 answers |
| Held-out: widened claims on screen | 0 on the branch, 0 on develop |
| Held-out: the writer keeps more limiting words | No. The branch writer dropped a limit in 8 of 15 sentences, develop's in 4 of 15 |
| Gates 02, 03, 04 | Pass |
| Spend at most $0.40 | $0.187 |

In the person's words: no reader in these 14 answers was shown a claim wider than its paper. That protection comes from card 99's check, which this round leaves as develop has it. The neutral writer line does not measurably help the writer keep limiting words. With the GERD words gone from the prompt, the writer kept "young" in 2 of 8 sentences about young children, against 7 of 8 with the lifted examples. On the held-out question the branch writer kept "usually" and "for children" less often than develop's. Four runs per arm is too few to call that a harm. It is too few to call it a help either.

## Per finding

| Finding | Status | By |
|---|---|---|
| J-101-01, an "ly" limit word not asked about when the sentence uses its adjective | Fixed | The revert: exact matching only, as on develop |
| J-101-02, one patient or one study widened to a plural not asked about | Fixed | The revert |
| J-101-03, the four rule 3a examples are GERD record phrases | Fixed | The new line: five neutral examples, each grepped absent; the test fails if a lifted phrase returns |
| J-101-04, a past-tense finding restated in the present not asked about | Fixed | The revert |
| J-101-05, two bounds of the word-form rule untested | Moot | The revert removes both bounds' code (`_word_forms` and the rewritten sentence read) |
| A-101-01, the "ly" ending silences the pair check on a dropped hedge | Fixed | The revert |
| A-101-01b, live, the branch approved four widened sentences develop held back | Fixed | The revert: the pair check proposes develop's pairs again, byte for byte the same code |
| A-101-01c, A-101-01b holds in 3 of 3 runs each | Fixed | The revert |
| A-101-02, recorded sentences lose the "most commonly" and "most affected" pairs | Fixed | The revert |

The adversary report refers to an A-101-05 about the shared worktree; no such section was written, so there is nothing to answer for it.

## What changed

| Commit | Change |
|---|---|
| `b3b98432` fix(sentence-check): Revert counting a ment noun as a form of its verb | Reverts 56098e1d |
| `91d23ed3` fix(sentence-check): Revert counting another form of a quote word as used | Reverts cd9500fe |
| `50ff11dd` fix(writer): Give the limiting-words line neutral examples from no test question | Rewrites rule 3a's line in `synthesis/findings.py` and its test |

The reverts were made with `git revert`, then committed with Conventional Commit subjects in place of the default "Revert" subject. Each body names the commit it reverts.

The rule 3a line now reads: "Keep every word of the quote that limits who, how surely, how often or how long, or where a claim holds, such as "elderly", "probably", "rarely", "for up to a week" or "in mice"." That is the four categories in words, with one example for who, how surely and where, and two for how often or how long.

## The examples and their grep

Counted with `grep -iw` (whole word, any case): lines in `testing/Test_queries_and_workflows.md`, matches in `eval/golden/golden_dataset.json`, matches across every recorded run of `testing/Developer/reports/2026-10-05_wave3/sentence_check_raw/` (gp, gr, md and the develop control's cm, cp, cr, md files), and matches in card 99's labelled set (`2026-10-05_qualifier_check/raw/eval_set.jsonl`).

| Example | Test questions | Golden set | 2026-10-05 records | Card 99 labelled set |
|---|---|---|---|---|
| "elderly" | 0 | 0 | 0 | 0 |
| "probably" | 0 | 0 | 0 | 0 |
| "rarely" | 0 | 0 | 0 | 0 |
| "for up to a week" | 0 | 0 | 0 | 0 |
| "in mice" (and "mice") | 0 | 0 | 0 | 0 |
| "may", rejected | 10 | 0 | 339 | 304 |

The suggested "may" was replaced by "probably" because it appears in 10 test-question lines and 339 times in the recorded records. Other words checked and also absent: "perhaps", "presumably", "unlikely", "older adults", "in rats", "seldom", "briefly". "elderly", "may reduce" and "rarely severe" also appear in the pair check's own `PERPAIR_INSTRUCTIONS`, which are neutral by the same rule.

## Test and mutation

`test_rule_3a_asks_the_writer_to_keep_every_limiting_word` in `tests/system_03_search_agent/synthesis/test_answer_quality.py` checks three things. The line and its four categories are present. Each of the five examples is present. None of the lifted phrases ("young", "potentially", "transient", "outpatient setting") is in rule 3a. It also checks that the system instruction has no interpolation.

| Mutation | Result |
|---|---|
| The rule 3a line removed from `SYNTH_SYSTEM_INSTRUCTION` | 1 failed (this test), 590 passed across `tests/system_03_search_agent/synthesis/` |
| Restored | 591 passed; `test_prompt_cache_prefix.py` and `test_answer_quality.py` 36 passed |

## GERD plain language, branch

The question "What are the typical symptoms and risk factors of GERD?", plain language, through `core.run.run` locally with the real models, tools and graph, `CLASSIFIER_PROVIDER=jev`, as `build.md` ran it. The user database was a throwaway Postgres on port 5433 in the session scratchpad, migrated to head with the repository's alembic and stopped afterwards. The trace script is the build's, copied to `raw/fix/trace_run.py` with one question added. Raw answers stay outside the repository. `raw/fix/gerd_summary.txt` has each answer's shown sentences, and `raw/fix/gerd_candidates.txt` has every risk-factor, "young children" and "potentially" candidate with its verdict.

Run gp5 ended before the write step: the guard model timed out twice (10 s and 5 s) and the answer was "a step in this query hit a temporary error". It says nothing about this card, so gp7 replaced it.

| Answer | Seconds | Sentences shown | "children" for "young children" | Dropped "potentially" | Risk-factor sentence |
|---|---|---|---|---|---|
| gp1 | 32.5 | 3 | 0 | 0 | Yes, no sphincter clause |
| gp2 | 28.1 | 4 | 0 | 0 | No |
| gp3 | 30.9 | 2 | 0 | 0 | Yes, no sphincter clause |
| gp4 | 16.6 | 3 | 0 | 0 | No |
| gp6 | 21.6 | 3 | 0 | 0 | No |
| gp7 | 17.7 | 3 (one a copied record-name line) | 0 | 0 | No |
| Mean or total | 24.6 | 3.0 (2.83 without the name line) | 0 | 0 | 2 of 6 |

What the writer did with the limiting words, every check candidate counted with the build's patterns:

| Limiting word | 2026-10-05, before card 101 | Card 101 build, GERD examples | This round, neutral examples |
|---|---|---|---|
| "young" kept in a sentence about children | 1 of 12 | 7 of 8 | 2 of 8 |
| A hedge kept where the quote says "potentially" | 9 of 11 | 7 of 7 | 4 of 9 (3 by hand: gp6's "may" sits on another clause) |
| "transient" kept where the sentence names the relaxations | 0 of 9 | 0 of 6 | 0 of 7 |

Every candidate that dropped "young" or the hedge was held back, by the pair check ("in young" and "young children" at no 0.16 to 0.30, "symptoms potentially" at 0.16 to 0.36) or by the item question. So the reader saw none of them, and lost those sentences instead. Mean sentences shown is 3.0, against the build's 5.17 with the lifted examples and card 99's deployed proof of 3, 4, 4, 2, 6 (mean 3.8). The young-children recovery the build measured came from the lifted examples. With neutral examples it is gone.

Only 2 of 6 answers met the 20-second target (gp4 16.6 s, gp7 17.7 s). The build's own runs ranged 18.9 to 37.8 s, and every held-out answer took under 12 s on both arms. The prompt adds one line, so this reads as load and model latency on GERD, not the change. It was not measured further.

## Held-out question, branch against develop

The question: "What causes bronchiolitis in babies, and how is it usually treated?", plain language. It was chosen because it is about a condition in infants. Its likely records (a review abstract) carry the who, how-often and how-surely limits this card is about: "in healthy infants and children", "usually symptomatic", "becoming common for children with severe bronchiolitis", "infants younger than 3 months". Grep, any case: "bronchiolitis" has 0 lines in `testing/Test_queries_and_workflows.md`, 0 in `eval/golden/golden_dataset.json`, 0 in `golden_dataset_v1_baseline.json`, and the same for "infant". The develop arm ran `origin/develop` (f5729ec5) exported with `git archive` to a scratch folder outside the repository. `diff -r` against the branch's `src` shows only `synthesis/findings.py` differs. Per answer, shown sentences, candidates, verdicts and the record sentences quoted are in `raw/fix/held_out_answers.txt`.

A widened claim is a sentence that leaves out a word of its quote that limits who, how surely, how often or how long, or where. I judged each one against the quoted record sentence. Narrowing ("babies" for "infants and children") is not counted. A sentence that moves "usually" from the treatment clause onto the recovery clause ("it usually goes away on its own, and care focuses on ...") counts as dropping it from the treatment claim. That is a judgement call, and it applies the same way to both arms.

| Run | Sentences shown | Widened on screen | Writer sentences checked | Widened among them | Widened and approved by the check |
|---|---|---|---|---|---|
| Branch hb1 | 4 (all copied record sentences) | 0 | 2 | 2 | 0 |
| Branch hb2 | 2 (copied) | 0 | 4 | 2 | 2 |
| Branch hb3 | 4 (1 reworded, 3 copied) | 0 | 3 | 2 | 0 |
| Branch hb4 | 3 (2 copied, 1 reworded outside the check) | 0 | 6 | 2 | 1 |
| Branch total | 13, mean 3.25 | 0 | 15 | 8 | 3 |
| Develop hd1 | 2 (reworded) | 0 | 4 | 0 | 0 |
| Develop hd2 | 3 (copied) | 0 | 2 | 0 | 0 |
| Develop hd3 | 0, record list only | 0 | 3 | 2 | 0 |
| Develop hd4 | 0, record list only | 0 | 6 | 2 | 0 |
| Develop total | 5, mean 1.25 | 0 | 15 | 4 | 0 |

The widened writer sentences, by the limit dropped:

| Limit in the record | Branch kept | Develop kept | Example of the drop |
|---|---|---|---|
| "usually" (treatment is usually symptomatic) | 0 of 4 | 3 of 4 | "Treatment focuses on relieving symptoms and keeping oxygen and fluid levels adequate" (hb2, approved) |
| "for children" (high-flow nasal cannula for children with severe bronchiolitis) | 0 of 4 | 1 of 4 | "For severe cases, a high-flow nasal cannula is increasingly used" (hb2 and hb4, approved) |
| "healthy" (self-limited in healthy infants and children) | 5 of 5 | 3 of 4 | "a common lower respiratory tract infection in babies and toddlers that usually clears up on its own" (hd3, held back) |

What the person sees: in all 8 answers, no sentence on screen said more than its paper. On the branch the check approved 3 widened writer sentences, and none reached the screen: each answer showed record sentences copied whole instead. On develop the check approved none. Two of develop's four answers showed only the record list, because every written sentence of the draft was stripped for its citations, an earlier step than the sentence check. That is why develop's mean is lower, and it is not this card's doing.

Read honestly: on this question the neutral line did not make the writer keep "usually" or "for children". The branch writer dropped them more often than develop's, 0 of 8 kept against 4 of 8. With 4 runs per arm and one record, this may be run-to-run spread. It is not evidence the line helps. Nothing was tuned toward this question.

## Gates

Run from the worktree with the main checkout's virtual environment first on PATH.

| Gate | Result |
|---|---|
| `gate02_import_order.sh` | Pass, exit 0 |
| `gate03_lint.sh` (ruff, whole repository) | Pass, "All checks passed!" |
| `gate04_unit_suite.sh` (whole suite) | Pass, exit 0: 6,987 passed, 143 skipped, 24 deselected, 1 xfailed, 0 failed, in 351 s. Load average 2.85 at the start |

## Cache miss

Rule 3a lives in `SYNTH_SYSTEM_INSTRUCTION`, the fixed system block at the head of the cached prefix. The new line is fixed text with no interpolation, so the prefix stays byte-identical from query to query, and `test_prompt_cache_prefix.py` passes. The cost is one cache miss: the first write-step call after deploy bills the prefix at the uncached rate. Later calls hit the cache again. The reverts add no prompt text, and the pair questions are develop's.

## Spend

| Item | Cost, each answer's own reported total |
|---|---|
| 7 GERD launches (6 answers and the guard timeout) | $0.1018 |
| 4 held-out answers, branch | $0.0422 |
| 4 held-out answers, develop | $0.0429 |
| Total | $0.187 of $0.40 |

## What is not covered

- The decision this measurement points to is the owner's: whether to ship a writer line that measurably changes nothing, or park card 101. On these runs the neutral line neither recovers the young-children sentence nor keeps "usually" on the held-out question.
- Run counts are small: 6 GERD answers with no paired develop arm (card 99's deployed proof is the nearest baseline), and 4 against 4 on one held-out question with one record.
- Branch hb4 showed "For babies with severe bronchiolitis, use of a high-flow nasal cannula is becoming common". The record says "children", and the sentence did not appear among the sentence check's candidates. It narrows rather than widens, but it changes the population, and how it reached the screen without the check was not traced. It is outside this round's fence.
- Each local run ended with a `CallerIdentityRequired` error from session memory after the last event, as in the build, because the trace script passes no caller identity. It comes after the answer and does not change it.
- Researcher depth and the Mediterranean question were not run.
