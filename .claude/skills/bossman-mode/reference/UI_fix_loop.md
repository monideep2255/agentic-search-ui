# The UI fix loop

Read this instead of the build-phase protocol when the work is a defect the product owner hit on the deployed develop app. It is a product-owner decision dated 2026-09-12, recorded in `DECISIONS.md`, and it replaces the build-phase cadence for UI fixes only. It does not replace it for anything else.

This file describes what the team actually ran from 2026-09-12 onward, taken from `testing/UI_fix_plan.md` and the commit history, not an idealized version.

## Table of contents

- [When this mode applies](#when-this-mode-applies)
- [The loop](#the-loop)
- [One feature per push](#one-feature-per-push)
- [Parallel agents: fence by file](#parallel-agents-fence-by-file)
- [What verification means here](#what-verification-means-here)
- [Where things get written](#where-things-get-written)
- [What does not change](#what-does-not-change)

## When this mode applies

Use it when all of these hold:

- The defect was found by the product owner testing the deployed develop app, or derives directly from that testing.
- The fix is scoped to an existing surface rather than delivering a numbered build phase from technical specification Section 25.
- There is a row for it in `testing/UI_fix_plan.md`, or one is about to be added.

Use the build-phase cadence instead when the work delivers a Section 25 phase, changes the agent loop's contract, adds a tool, or touches auth, the graph credential, or the event schema. A defect the product owner hit is not automatically small: row 10.2 looked like a frontend change and turned out to need a schema migration and a data-retention decision, so it was escalated rather than fixed.

## The loop

There is no branch, no pull request, no judge round and no adversary round. The product owner's live retest is the verification step.

1. The product owner tests on develop and drops feedback.
2. The feedback becomes numbered rows in `testing/UI_fix_plan.md`, one row per item, each with its own status.
3. Fixes land directly on `develop`. No phase branch, no pull request.
4. Run the quick checks that fit the change, then push. One item per push.
5. Confirm it live: the deployment reports SUCCESS, the served app carries the change, and a browser check at 1280px and 390px.
6. The product owner retests and gives a verdict. That verdict, not an agent's grade, moves the row to done. Once an item is live its row and detail already sit in `testing/UI_fixes_done.md`; the verdict closes the one "Your retest" row the plan keeps for it.

Tickets reach `in-review` on merge and reach `done` only on the product owner's verdict. This is the same rule build phase 6.2 adopted when it dropped its judge round: the person testing on develop is the verification step, so nothing an agent runs can close a row on its own.

## One feature per push

This is the loop's hardest-won rule and the one most likely to be relaxed under time pressure.

Items 11.27 and 11.28 shared a merge. CI failed on one of them, the merge was reverted, and the innocent item was reverted with it and sat unavailable for a week. So each item lands alone, is confirmed live alone, and can be rolled back alone.

A corollary from the same week: a merge cannot omit a file, but copying files out of one can. An overnight worker ported two of three test-isolation fixes into a worktree by copying files across, watched the failure persist, and recorded the cause as unknown. The third fix lived in a file it never copied. Merge rather than copy.

## Parallel agents: fence by file

Parallel work is allowed here and it works. File fencing held across eight concurrent agents in one day with zero collisions. Two rules:

- No two agents own one file. State the file map before dispatching, the same discipline the build cadence applies to fix agents.
- The machine's CPU is the one shared resource that cannot be fenced, and checking load before a run is a race rather than a queue. Two agents both saw a quiet machine, started together, and drove the load average to 20. Any suite result measured under that load is not trustworthy and gets re-run.

## What verification means here

Dropping the judge round does not drop the standard of evidence. Three things carry over from the build cadence, and one is specific to this loop.

- Mutate one property, never revert the change. An arm that fails when the whole change is reverted has not been shown to test anything, because it usually fails on a missing symbol before it ever evaluates its assertion. The full statement, with the measured case, is in `reference/Review_rounds.md` under "Reviewing a fix, and reviewing a gate".
- Write a finding the moment it is established, before doing anything else with it. Findings go to a dated report folder, not into an agent's context.
- Answer quality outranks presentation. From the product owner's verdict of 2026-09-13, prefer answer-path work over presentation work, and prove an answer-path fix with five or more repeated live runs rather than one. A single green run does not establish a behaviour that was intermittent.
- A defect in what the answer SAYS about what it found is as serious as a retrieval defect. Four defects found in one live TP53 answer were every one of them reporting defects: the agent found the records, cited them and rendered them, and what it said about them was wrong or unreadable. A false note teaches a reader to distrust the true ones.

## Where things get written

| What | Where |
|------|-------|
| The item list, one row per fix, with status | `testing/UI_fix_plan.md` while being built or to do; `testing/UI_fixes_done.md` once live |
| The running cutoff and the shared plan | `testing/UI_fix_plan.md`, the "Where we stopped" section, updated at the end of every session |
| Evidence for a defect or an investigation | `testing/Developer/reports/<date>_<topic>/findings.md` |
| A choice between alternatives | `DECISIONS.md` |
| What broke and what fixed it | `LEARNINGS.md` |

"Where we stopped" is the durable plan. It exists so the next session starts from a record rather than reconstructing one from a conversation that has disappeared, and so the product owner and the agent read the same thing. Update it at the end of every session.

## What does not change

Dropping the branch, the pull request and the review rounds does not drop anything else. These still bind, in full:

- Every rule under `.claude/rules/`, which auto-loads and is unaffected by which mode is running. `v1-scope-boundary` binds hardest when no one is reviewing each step.
- `design-consistency`: find the surface's design before styling it, and name the gap out loud rather than inventing a look when there is none.
- `production-standards`: the security, schema, layer-authority and cite-or-refuse gates hold on a one-line fix exactly as they hold on a build phase.
- File protection: never delete without informing first.

Escalate to the product owner, rather than fixing autonomously, when an item turns out to need a schema migration, a data-retention decision, a change to a locked requirements document, or a widening of a security control such as the citation host pin.
