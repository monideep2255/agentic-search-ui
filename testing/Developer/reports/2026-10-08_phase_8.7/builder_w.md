# Builder W, phase 8.7, steps 5 and 6

Builder W's running record for build phase 8.7, steps 5 (card 2, the first sentence) and 6 (card 50, the summary sooner), merged by hand from commit 32e5945e onto today's write step.

## Table of contents

- [Base](#base)
- [Findings](#findings)
- [Deviations from the plan](#deviations-from-the-plan)
- [Open questions](#open-questions)
- [Learnings](#learnings)

## Base

- Worktree branch `feat/8.7-w`, cut from `phase/8.7-answers-sooner` at 586d715183733f94c2a2059c18222732caccbb57.

## Findings

- Step 5 lifted cleanly by hand: `harness/decide.py`, `synthesis/answer_layout.py` and the `_answer_tokens` summary block had not moved in a way that conflicts. Today's `answer_summary_sentence` has four `return` points (plain and technical, with and without the fold clause); all four go through `finish`.
- The lead decision runs only with `CLASSIFIER_PROVIDER=jev`. A deployment where the guard tier decides alone keeps today's count line leading, as the plan says.
- Mutation checks for step 5: passing `lead_index=None` turns 4 lead-sentence arms red; passing `asked_field=None` turns the honest-gap wiring arm red.

## Deviations from the plan

- Step 5: the three lead-sentence functions and the two budget constants sit just above `_answer_tokens`, under their own card 2 banner, rather than inside builder A's single 8.7 block, so step 5 can be read and reverted alone.
- Step 5: three arms added that 32e5945e did not have: the honest gap reaching the count line from `think.asks_features` on the write path, the count line unchanged when nothing was asked for, and the closed lead options. The first fails on code that does not pass `asked_field`.

## Open questions

## Learnings
