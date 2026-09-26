# The UI fix loop: a card alone

Read this when the work is one card on `testing/UI_fix_plan.md`, built and pushed alone. The loop began as a product-owner decision of 2026-09-12 (`DECISIONS.md`): a fix to the deployed develop app lands on `develop` at once, and the owner's live retest is the verification. Since 2026-09-25 it is the cadence for a card alone at dial positions 1 and 2 (`SKILL.md`, "Set the dial first"):

- Position 1, a copy or layout fix: builder, clerk, product review, the owner's retest.
- Position 2, a change to runnable behaviour: the judge and the adversary read the change before it is pushed, then one fix-and-verify, then the same landing and the same retest.
- Position 3, auth, the graph credential, the event schema or `.claude/`: not this loop. A branch and a pull request, per `reference/Phase_execution.md` step 7.

This file describes what the team actually ran from 2026-09-12 onward, taken from `testing/UI_fix_plan.md` and the commit history, plus what the build harness review of 2026-09-25 changed. It is not an idealized version.

## Table of contents

- [When this applies](#when-this-applies)
- [The loop](#the-loop)
- [No fix without a diagnosis](#no-fix-without-a-diagnosis)
- [What the lead decides, and what reaches the owner](#what-the-lead-decides-and-what-reaches-the-owner)
- [One feature per push](#one-feature-per-push)
- [Parallel agents: fence by file](#parallel-agents-fence-by-file)
- [What verification means here](#what-verification-means-here)
- [Where things get written](#where-things-get-written)
- [What does not change](#what-does-not-change)

## When this applies

Use it when all of these hold:

- The card is in the To do column of `testing/UI_fix_plan.md`, or is about to be added. A card is written before it is built.
- It can land alone: nothing else has to land with it for a person to see it whole.
- Its dial position is 1 or 2.

Open a numbered phase instead (`reference/Phase_execution.md`) when cards must land together or the work is a technical specification Section 25 deliverable. A defect the product owner hit is not automatically small: row 10.2 looked like a frontend change and turned out to need a schema migration and a data-retention decision, so it was escalated rather than fixed.

## The loop

There is no branch and no pull request. The product owner's live retest is the verification step, and at position 2 the judge and the adversary read the change first.

1. The product owner tests on develop and drops feedback.
2. The feedback becomes numbered cards in the To do column of `testing/UI_fix_plan.md`, one card per item, each with its detail in `testing/UI_fixes_done.md`'s "Detail for items on the board" section.
3. The lead sets the dial and, when the cause is unknown, opens a diagnosis first (below).
4. The fix is built and committed on `develop` locally, one card at a time. A builder dispatched for it starts from `origin/develop`'s tip (`reference/Phase_execution.md`, the agent prompt template).
5. At position 2: one judge round and one adversary round on the unpushed commits (`git diff origin/develop...HEAD`), then one fix-and-verify, per `reference/Review_rounds.md`. Findings go to a dated report folder. At position 1 this step does not run.
6. Run the quick checks that fit the change, then push. One card per push.
7. Confirm it live: the deployment reports SUCCESS, the served app carries the change, and a browser check at 1280px and 390px. The product reviewer (`.claude/agents/product-reviewer.md`) is that check's agent form: it pre-screens the change on develop and files what the owner should look at first, and closes nothing.
8. The product owner retests and gives a verdict. That verdict, not an agent's grade, moves the card off the board. Once a card is live it sits in the Retest column and its detail already sits in `testing/UI_fixes_done.md`; the verdict removes the card from Retest and sets the done file's status to Approved. One exception, the product owner's decision of 2026-09-25 (DECISIONS.md, "A wording or layout card closes by itself seven days after reaching Retest"): a wording or layout card closes by itself seven days after reaching Retest once the product reviewer has passed it at 1280 and 390 pixels, unless the owner objects. The lead writes the "closes on" date on the card when the reviewer's pass exists, removes the card on that date and sets the done file's status to closed after seven days with no objection. The owner can reopen it, and a reopened card goes back to To do with their words. Every other card, and every card that changes answers, waits for the owner's verdict.

Tickets reach `in-review` on merge and reach `done` only on the product owner's verdict. This is the same rule build phase 6.2 adopted when it dropped its judge round: the person testing on develop is the verification step, so nothing an agent runs can close a card on its own. The seven-day close in step 8 is the one exception, and it is the owner's own standing rule, not an agent's grade: it applies only to wording and layout cards the product reviewer passed at both widths, and only when the owner has not objected.

## No fix without a diagnosis

A card whose cause is unknown becomes a diagnosis ticket, and only that. Its output is a written diagnosis in a dated report folder naming the cause and the evidence. A fix ticket opens only after the lead has read it. The lead may write the diagnosis itself when the cause is plain.

Why, from the night of 2026-09-25: the plan said three cards had "no diagnosed cause yet" and all three were dispatched as fixes anyway. All three were reverted after the judge and the adversary found they made answers less trustworthy, and a fourth card ended as a diagnosis only. Work that starts before the cause is known is the pattern behind three of that night's five reverts.

## What the lead decides, and what reaches the owner

Added 2026-09-25 from the build harness review (A1, parts one and three), under the product owner's delegation of that day. The owner's own rule of 2026-09-22 (`decide-from-the-users-chair`) already covers the first half. The loop did not use it: 11 of the 19 questions the overnight plan put to the owner were inside the lead's remit.

The lead decides, per that rule:

- Wording, placement and housekeeping cards inside its remit: a label, a note's position, a test file, a lock file, a count's caption, which filters an isolate question offers.
- Each such choice is made from the user's chair and reported in the user's words, what the person typing a question will notice, in the card's detail and the session report. "A question about one gene never shows records for a different gene", not "wire the filter into the act result path".

The owner decides, and these reach them as one list:

- Scope, a cost cap, a design placement the owner owns, copy the owner owns, a new dependency, anything on the v1 boundary, the security layer, and any drop in the golden answered count.
- The list is written once a day, in the session report and on the board's To do cards marked "Your decision", with at most ten items. Each item is a yes, a no or a pick-one, with the lead's recommendation and its reason in one line.
- In conversation the items are still asked one at a time, in the list's order, per `communication-style`. The list is the queue; each question is still single.
- An eleventh question waits for the next day, unless it blocks work in progress, in which case it displaces the least urgent item on the list and the lead says so.

## One feature per push

This is the loop's hardest-won rule and the one most likely to be relaxed under time pressure.

Items 11.27 and 11.28 shared a merge. CI failed on one of them. The merge was reverted, and the innocent item went with it and sat unavailable for a week. So each item lands alone and is confirmed live alone, and it can be rolled back alone.

A corollary from the same week: a merge cannot omit a file, but copying files out of one can. An overnight worker ported two of three test-isolation fixes into a worktree by copying files across. It watched the failure persist and recorded the cause as unknown. The third fix lived in a file it never copied. Merge rather than copy.

## Parallel agents: fence by file

Parallel work is allowed here and it works. File fencing held across eight concurrent agents in one day with zero collisions. Two rules:

- No two agents own one file. State the file map before dispatching, the same discipline the build cadence applies to fix agents.
- The machine's CPU is the one shared resource that cannot be fenced, and checking load before a run is a race rather than a queue. Two agents both saw a quiet machine, started together, and drove the load average to 20. Any suite result measured under that load is not trustworthy and gets re-run.

## What verification means here

Dropping the branch does not drop the standard of evidence. Three things carry over from the numbered-phase cadence, and one is specific to this loop.

- Mutate one property, never revert the change. An arm that fails when the whole change is reverted has not been shown to test anything, because it usually fails on a missing symbol before it ever evaluates its assertion. The full statement, with the measured case, is in `reference/Review_rounds.md` under "Reviewing a fix, and reviewing a gate".
- Write a finding the moment it is established, before doing anything else with it. Findings go to a dated report folder, not into an agent's context.
- Answer quality outranks presentation. From the product owner's verdict of 2026-09-13, prefer answer-path work over presentation work, and prove an answer-path fix with five or more repeated live runs rather than one. A single green run does not establish a behaviour that was intermittent.
- A defect in what the answer SAYS about what it found is as serious as a retrieval defect. Four defects found in one live TP53 answer were every one of them reporting defects: the agent found the records, cited them and rendered them, and what it said about them was wrong or unreadable. A false note teaches a reader to distrust the true ones.

## Where things get written

The one table is in `SKILL.md`, "Where everything is written". For a card alone, the rows that matter most:

- The board, `testing/UI_fix_plan.md`, with the detail and the cutoff in `testing/UI_fixes_done.md`.
- A diagnosis or a finding: `testing/Developer/reports/<date>_<topic>/findings.md`, written the moment it is established.
- A choice between alternatives: `DECISIONS.md`. What broke and what fixed it: `LEARNINGS.md`, before continuing past a failure that cost more than five minutes.

"Where we stopped" in `testing/UI_fixes_done.md` is the durable plan. It exists so the next session starts from a record rather than reconstructing one from a conversation that has disappeared, and so the product owner and the agent read the same thing. Update it at the end of every session.

## What does not change

Dropping the branch and the pull request does not drop anything else. These still bind, in full:

- Every rule under `.claude/rules/`, which is unaffected by which position the dial sits at. `v1-scope-boundary` binds hardest when no one is reviewing each step.
- `design-consistency`: find the surface's design before styling it, and name the gap out loud rather than inventing a look when there is none.
- `production-standards`: the security, schema, layer-authority and cite-or-refuse gates hold on a one-line fix exactly as they hold on a phase.
- File protection: never delete without informing first.

Escalate to the product owner, rather than fixing autonomously, when an item turns out to need a schema migration, a data-retention decision, a change to a locked requirements document, or a widening of a security control such as the citation host pin.
