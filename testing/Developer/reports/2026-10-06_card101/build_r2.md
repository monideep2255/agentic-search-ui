# Card 101 build round 2: every reworded sentence goes to the sentence check

Builder, 2026-10-06, branch `fix/card101-check-every-rewording` from develop 3d6947ff. The owner decided (`DECISIONS.md`, last row) that every reworded sentence goes to the sentence check: code may still hold a sentence back, but never approves a rewording on its own. The diagnosis behind it is `diagnosis.md` in this folder.

## Table of contents

- [Verdict](#verdict)
- [The change in the user's words](#the-change-in-the-users-words)
- [What changed](#what-changed)
- [Choices for the lead to log](#choices-for-the-lead-to-log)
- [The copied cut finding](#the-copied-cut-finding)
- [Tests and mutations](#tests-and-mutations)
- [Offline rescan of the recorded answers](#offline-rescan-of-the-recorded-answers)
- [Live runs](#live-runs)
- [Against develop](#against-develop)
- [Gates](#gates)
- [Spend](#spend)
- [Not covered](#not-covered)

## Verdict

| Check | Result |
|---|---|
| hb4's "For babies with severe bronchiolitis" | Now a check candidate, offline from the recorded trace and in a unit test; not shown without the check's approval |
| Copied record words | Still shown with no model call |
| Check cannot run (failure, unreadable reply, cost cap, too little time, approves none) | None of the moved sentences is shown; the copied ones still are |
| Completeness repair | Same rule: its rewording reaches the check, shown only when approved |
| Offline, 51 recorded answers | 20 shown sentences in 12 answers move to the check; 0 answers need a new check call; 0 sentences pushed past the pair-call cap |
| Live, 15 plain-language answers | 12 sentences code would have shown went to the check: 10 approved, 2 held back (both faithful) |
| Widened claims on screen from the path this card closes | 0 |
| Widened claims on screen in total | 2 clear, in one GERD answer, and 1 borderline. All three were check candidates on develop too (code's word check would not have approved any of them), so this change neither caused nor could have stopped them. See [Live runs](#live-runs) |
| Answers that lost all their prose | 0 |
| Gates 02, 03, 04 | Pass |
| Spend at most $0.50 | $0.244 |

## The change in the user's words

No sentence the app writes in its own words reaches the screen unless the sentence check has read it against its paper. A sentence copied word for word from the record still shows at once, with no extra call. When the check cannot run, the reworded sentences it would have judged are not shown, as the check already did for the rest.

Correction after review (judge J2-101-01, adversary A2-101-01 to 03): that holds for sentences the writer rewords. Three shapes still show without the check, on develop and on this branch alike. They stay on card 101:

- A copied cut that drops a clause at either end, including "There is no evidence that".
- Two copied clauses joined into a new claim.
- A short record value, such as a title, wrapped in the question's words.

So "babies" can no longer replace the paper's "children" just because the person asked about babies, and a dropped "usually" or "healthy" now meets card 99's dropped-limit check like every other rewording.

## What changed

| Commit | Change |
|---|---|
| `c7f7192b` docs(card101): Add the diagnosis of the unchecked rewording path | `diagnosis.md`, with only the four formatting fixes the style checker asked for |
| `9e9bf6a5` fix(grounding): Send every reworded sentence to the sentence check | `synthesis/grounding.py`, `run_grounding_pass`: `synthesized` starts False, and every clause that fails the strict copy test and passes the exact checks becomes a candidate. Docstrings of `SynthesisCandidate` and `synthesis_is_supported_by` updated. Tests below |
| This report's commit | `build_r2.md` and `raw/check_every/` (scripts and count-only outputs) |

`core/graph.py` was not touched. The repair already grounds through `_ground_with_sentence_check`, so it needed no change.

## Choices for the lead to log

| Choice | Taken | Alternatives considered | Why |
|---|---|---|---|
| What code's word check does now | Nothing in the grounding pass: it is no longer called there | Keep it as a code rejection, holding back a sentence whose words it cannot license | It never held a sentence back: a sentence that failed it already went to the model. Turning it into a rejection would drop the faithful plain-language rewordings the 2026-09-23 measurement showed code cannot license (0 of 53) |
| `synthesis_is_supported_by` itself | Kept, documented as no longer an acceptance path | Delete it | Its unit tests and the measurement scripts compare against it, and the live trace uses it to count what code would have shown. Deleting it is a wider change than the decision asks |
| Moved sentences when the check cannot run | Not shown | Show them unchecked as before | The brief and the owner's decision: the check's existing fail-closed rule |
| `core/graph.py` wording | Left as is | Update two comments | Outside the fence unless strictly needed. Two now read slightly stale: `_ground_with_sentence_check`'s docstring says candidates "failed only the word check", and the comment above `_SENTENCE_CHECK_MIN_BUDGET_S` says that below the floor "the answer is what code alone accepts, exactly as before the check existed". Behaviour is right; the lead may want the wording fixed |
| Where the repair test lives | `tests/system_03_search_agent/synthesis/test_check_every_rewording.py`, reusing `test_write_completeness.py`'s state and helpers by import | A copy under `tests/system_03_search_agent/core/` | The fence allows `core/` tests only for a `graph.py` change, and there is none |
| The copied cut (P1) | Not changed | Send copied cuts to the check (the diagnosis's option D) | Next section |

## The copied cut finding

The diagnosis's P1: a copied cut can drop a limiting clause at either end, and the capital-letter exemption (`grounding.py`, `_opens_on_record_fragment`) lets a cut that starts mid-sentence through.

- This change does not cover it. A copied cut passes the strict copy test, and the brief keeps copied record words showing without a model call.
- Covering it is not the same few lines: it needs a new rule in the strict path deciding when a contiguous copy is a cut, plus routing it to the check. That is the diagnosis's option D.
- Decided: not widened. The one recorded borderline cut ("Out of 176 solved families" dropped) was approved by the check 3 of 3 in the diagnosis, so the value now is low. It stays open for its own card if the owner wants it.

## Tests and mutations

New file `tests/system_03_search_agent/synthesis/test_check_every_rewording.py`, 12 cases, offline, no model. hb4 is rebuilt from the diagnosis: the record sentence, the title "Acute bronchiolitis.", the question and the writer's sentence with the record sentence as its quote. A populate-check asserts code's word check still approves it, so the arm tests the path that matters.

| Arm | Property |
|---|---|
| `test_the_babies_sentence_becomes_a_check_candidate` | hb4's sentence is collected for the check and not shown on the first pass |
| `test_the_babies_sentence_shows_only_with_the_checks_approval` | Shown with its quote once its key is approved |
| `test_a_copied_record_sentence_shows_without_a_call` (2 cases) | A copied record sentence, with and without a quote, shows with no model call |
| `test_a_check_that_cannot_approve_shows_none_of_the_moved_sentences` (5 cases) | Approves none, unreadable reply, failed call, cost cap, too little time: "babies" not shown, the copied sentence still shown |
| `test_the_check_approving_it_shows_it` | One call, sentence shown |
| `test_the_repairs_rewording_goes_to_the_check_and_is_hidden_when_it_fails` | Through the real `write_node`: the repair's code-approvable rewording reaches the check and is not shown when the check fails |
| `test_the_repairs_rewording_shows_when_the_check_approves_it` | The same rewording is shown when approved |

Each mutation was applied by `raw/check_every/mutate.py`, the file run, the result recorded, the source restored (`raw/check_every/mutations.txt`).

| Mutation | Arms red |
|---|---|
| M1, code approves again (the old `synthesized = ... synthesis_is_supported_by(...)` restored) | 10 of 12: both hb4 arms, all 5 fail-closed cases, the approval arm, both repair arms |
| M2, copied sentences go to the check (`not strict_ok` dropped from the candidate condition) | 1: the copied sentence with a quote (a call is made) |
| M3, collect and accept on the first pass (a "show unchecked when the check cannot run" fallback) | 7: the hb4 candidate arm, all 5 fail-closed cases, the repair failure arm |
| M4, the repair grounds with a plain `run_grounding_pass` in `core/graph.py` | 2: both repair arms |

Existing tests: two arms in `test_quote_anchored_synthesis.py` asserted code acceptance of a rewording.

- They now ground through both passes with an approving check, and assert that code alone does not show the sentence.
- The file's mutation arm now switches off the exact checks instead of the word check.
- Whole synthesis folder after the change: 602 passed, 10 skipped, 1 xfailed.

## Offline rescan of the recorded answers

The diagnosis's scan, rerun with the new rule over the same 51 traced answers (`raw/check_every/scan_new_rule.py`, `scan_new_rule.txt`). The six name and identifier lines ("Publication pmid ... is included", trial names) are excluded, as the diagnosis counted them apart: they carry no quote and take the strict path.

| Source | Answers | Shown | Move to the check, shown | Move, every first pass | Answers affected | New check calls | Joined an existing call |
|---|---|---|---|---|---|---|---|
| 2026-10-05, card 89 branch | 15 | 62 | 9 | 10 | 7 | 0 | 8 |
| 2026-10-05, develop control | 14 | 43 | 8 | 10 | 6 | 0 | 7 |
| 2026-10-06, card 101 build | 8 | 42 | 2 | 7 | 3 | 0 | 4 |
| 2026-10-06, card 101 fix round | 14 | 36 | 1 | 3 | 3 | 0 | 3 |
| Total | 51 | 183 | 20 | 30 | 12 shown, 16 any | 0 | 22 |

Per affected answer, 1 to 4 shown sentences move (cr1 the most, 4). "Every first pass" adds sentences that were approved but later dropped by other rules or by a repair draft that was not kept.

Cost and time:

- Calls: every first pass that kept a code-approved sentence already had other candidates, so the change adds no call to any recorded answer. The moved sentences join the call that was going to happen.
- Time per call does not grow with items: median 0.28 s at 1 item, 0.33 s at 4, 0.36 s at 8, 0.34 s at 10 (93 recorded checks, `check_time_by_items.txt`). So the added time per answer is near zero.
- Pair-call cap: the 22 affected checks plus their moved sentences, run through the shipped `build_pair_calls` with the moved sentences first (worst case) and last, leave 0 sentences unasked; the most pair calls any check needs is 3 of 4 (`pair_cap_pressure.txt`).

## Live runs

Method:

- `core.run.run` locally with the real models, tools and graph, `CLASSIFIER_PROVIDER=jev`, plain language, as `build.md` and `fix_round.md` ran it.
- The user database was the throwaway Postgres on port 5433 in the session scratchpad, confirmed at alembic head (`0010_interactions_saved_answer`), started for the runs and stopped afterwards.
- The trace script is the fix round's with one spy added (`raw/check_every/trace_run.py`): per check candidate, whether code's old word check would have approved it alone.
- Questions were interleaved, one round of three at a time. Load average 6 to 8 throughout.
- Raw answers stay outside the repository.

| Answer | Seconds | Shown | Reworded shown | Code would have approved | Of them held back | Of them approved and shown |
|---|---|---|---|---|---|---|
| GERD 1 | 20.0 | 4 | 4 | 0 | 0 | 0 |
| GERD 2 | 18.4 | 4 | 4 | 0 | 0 | 0 |
| GERD 3 | 14.4 | 3 | 2 | 0 | 0 | 0 |
| GERD 4 | 19.8 | 3 | 3 | 0 | 0 | 0 |
| GERD 5 | 21.2 | 3 | 3 | 0 | 0 | 0 |
| Mediterranean 1 | 20.7 | 2 | 2 | 1 | 1 | 0 |
| Mediterranean 2 | 24.5 | 7 | 6 | 3 | 0 | 2 |
| Mediterranean 3 | 21.2 | 1 | 1 | 0 | 0 | 0 |
| Mediterranean 4 | 18.4 | 7 | 7 | 2 | 0 | 2 |
| Mediterranean 5 | 20.9 | 5 | 5 | 3 | 1 | 0 |
| Bronchiolitis 1 | 15.0 | 1 | 0 | 0 | 0 | 0 |
| Bronchiolitis 2 | 15.2 | 3 | 1 | 1 | 0 | 1 |
| Bronchiolitis 3 | 13.1 | 3 | 1 | 1 | 0 | 1 |
| Bronchiolitis 4 | 19.2 | 4 | 4 | 0 | 0 | 0 |
| Bronchiolitis 5 | 9.8 | 5 | 2 | 1 | 0 | 1 |

"Shown" excludes the code-built opening "I found N" line. Counts of code-approvable sentences are distinct sentences across the first draft and the repair. Totals: 12 such sentences went to the check, 10 approved, 2 held back, 7 of the approved ones on screen.

What the check held back that code would have shown: both are G6PD sentences that join two record sentences ("the most common enzyme deficiency worldwide" and "most commonly affects persons of African, Asian, Mediterranean, or Middle-Eastern descent"). Judged by hand against the records, both are faithful. That is the cost the diagnosis predicted: here 2 of 12 code-approvable sentences, both faithful, were lost; in the diagnosis's measurement 4 of 36 judgements held back a faithful sentence.

The 7 moved sentences on screen, judged by hand: all faithful. Three are "For children with severe bronchiolitis, use of a high-flow nasal cannula is becoming common" or the self-limited sentence, with the paper's "children" and "healthy" kept. No bronchiolitis answer wrote "babies" for the paper's "children".

Widened claims on screen, every shown sentence judged against its quoted record sentences with the fix round's definition (a dropped word that limits who, how surely, how often or how long, or where):

| Answer | Sentence on screen | Record | Judgement | Path |
|---|---|---|---|---|
| GERD 2 | "Risk factors that contribute to GERD include the lower esophageal sphincter relaxing abnormally, ..." | "abnormal transient relaxations of the lower esophageal sphincter" | Widened: "transient" dropped, the case the owner ruled a dropped limit on 2026-10-06 | Check candidate, approved. Code would not have approved it |
| GERD 2 | "... long-term use carries risks including bone fractures, kidney disease, pneumonia, and intestinal infection" | "is associated with ... Clostridium difficile intestinal infection" | Widened: the named infection becomes any intestinal infection, and an association becomes a risk | Check candidate, approved. Code would not have approved it |
| Bronchiolitis 4 | "... it usually goes away on its own in healthy children with treatment focused on keeping oxygen levels and hydration adequate" | "Treatment is usually symptomatic, and the goal of therapy is ..." | Borderline: "usually" moved from the treatment claim to the recovery claim, the fix round's judgement call | Check candidate, approved. Code would not have approved it |

None of these came through the path this card closes, and each would have met the check the same way on develop. They are misses of the check itself (the item question and card 99's pair check). The first one contradicts a standing owner ruling, so the lead may want it filed against the check.

No answer lost all its prose. The two thinnest, Bronchiolitis 1 and Mediterranean 3 with one sentence each, had no code-approvable candidate, so this change did not thin them.

## Against develop

Develop was not rerun side by side; these are the recorded develop numbers the brief names, plus the 2026-10-05 develop control traces. Load differs between the sets.

| Question | This branch, 5 answers | Develop, recorded |
|---|---|---|
| GERD, sentences shown | Mean 3.40, range 3 to 4 | Card 101 fix round (develop's grounding, its own writer line): mean 3.0. Card 99 replay with the pair check: 2.1 an answer. 2026-10-05 develop control, before card 99: mean 2.8 |
| GERD, seconds | Mean 18.8, range 14.4 to 21.2; 4 of 5 within 20 s | Fix round: mean 24.6, 2 of 6 within 20 s. 2026-10-05 develop control: mean 18.3 |
| Mediterranean, sentences shown | Mean 4.40, range 1 to 7 | Card 99 replay with the pair check: 2.7 and 2.6 an answer. 2026-10-05 develop control, before card 99: mean 2.0 |
| Mediterranean, seconds | Mean 21.1, range 18.4 to 24.5; 1 of 5 within 20 s | 2026-10-05 develop control: mean 17.3 |
| Bronchiolitis, sentences shown | Mean 3.20, range 1 to 5 | Fix round develop arm (4 answers): mean 1.25, range 0 to 3 |
| Bronchiolitis, seconds | Mean 14.5, range 9.8 to 19.2; 5 of 5 within 20 s | Fix round develop arm: mean 8.6, range 6.7 to 9.7 |
| "babies" for "children" on screen | 0 in 5 | Fix round: 1 in 8 (hb4, the branch arm, develop's grounding) |

On time, the check itself adds little. It took 0.47 to 1.02 s in total per answer here, against 0.20 to 0.64 s in the fix round's bronchiolitis answers (`check_share.txt`). No answer gained a check call because of this change. The rest of the gap is outside the check:

- The time before the write step, which this change cannot touch, was 6.5 to 11.0 s for bronchiolitis here against 5.3 to 7.5 s in the fix round.
- 4 of 5 bronchiolitis answers ran the completeness repair, a second writer call, against 1 of 4 on develop's recorded arm. None of those four had a code-approvable sentence held back, so the change did not trigger the repair.

The Mediterranean answers miss the 20-second target in 4 of 5. The same reasoning applies. It was not measured further.

## Gates

Run from the worktree with the main checkout's virtual environment first on PATH, after the code commit.

| Gate | Result |
|---|---|
| `gate02_import_order.sh` | Pass, exit 0 |
| `gate03_lint.sh` (ruff, whole repository) | Pass, exit 0 |
| `gate04_unit_suite.sh` (whole suite) | Pass, exit 0: 6,998 passed, 143 skipped, 24 deselected, 1 xfailed, 0 failed, in 343 s. Load average 7.7 at the start |

The report's scripts were added after that run. Ruff and isort pass on `raw/check_every/`. Gates 02 and 03 were rerun before the report commit.

## Spend

| Item | Cost |
|---|---|
| 15 live answers, each answer's own reported total (the check's calls are charged to the question) | $0.2436 |
| Offline rescan, replays, tests, mutations | $0 |
| Total, limit $0.50 | $0.244 |

## Not covered

- Researcher depth: no live run.
- Guard-tier mode of the check (`CLASSIFIER_PROVIDER` unset): unit-tested only; the live runs used the classifier, as develop does.
- Develop side by side at the same load: recorded numbers only.
- The strict path that wraps a short record value with question words (the diagnosis's P2, option E) and copied cuts (P1, option D): unchanged.
- The deployed app: not measured.
- `core/graph.py` comment wording: see [Choices for the lead to log](#choices-for-the-lead-to-log).
