# Review rounds: the judge, the adversary, and the budget

Read this at cadence stages 8 and 9, before dispatching a judge or an adversary, and again before dispatching any fix agent. Nothing else in this skill needs it, which is why it is a separate file: a reviewer reads it alone rather than finding it buried in a phase-open checklist.

This file is the canonical home of the four review-loop rules. `docs/build/Build_workflow_cadence.md` carries a condensed version and says so: "bossman-mode holds the full statement of all four rules."

## Table of contents

- [The judge produces evidence, not a verdict](#the-judge-produces-evidence-not-a-verdict)
- [The adversary attacks what the judge certifies](#the-adversary-attacks-what-the-judge-certifies)
- [The review loop has a budget](#the-review-loop-has-a-budget)
- [Reviewing a fix, and reviewing a gate](#reviewing-a-fix-and-reviewing-a-gate)
- [Shared-ledger coordination](#shared-ledger-coordination)
- [Why judge and adversary never tier down](#why-judge-and-adversary-never-tier-down)

## The judge produces evidence, not a verdict

A judge that reports "looks good, all checks pass" without showing its work is the maker-checker failure `self-eval-loop.md` warns about: a grader that knows the rubric drifts toward approving everything. Force the judge to produce evidence, and default it to fail when evidence is absent.

For every claim, the judge's report must:

- Cite the exact `file:line` for a code finding, not "the agent loop looks fine".
- Paste the actual command output for a functional or test claim (the `pytest -q` result line, the lint output), not "tests pass".
- Quote the specific offending line for a security or quality finding, not "no security issues found". Grade against the `production-standards` and `ai-security-standards` gates: parameterized Cypher and SQL, schema validation at every agent-loop hop, cite-or-refuse on generated answers, no secrets in logs.

If the judge cannot produce evidence for a check, that check fails. "I could not verify X" is a fail, never a pass.

Verify the premise, not only the leaves. The judge's default instinct is to check each artifact against its assigned task: did builder 3 produce the file it was told to. That is leaf verification, and it passes even when the decomposition itself was wrong. Add one level up: does the set of completed tasks actually satisfy the phase done-when from the goal contract? A phase where every builder succeeded at its own task but the tasks together miss the phase's stated outcome is a failed phase, not a passed one (the plan-big-execute-small park-list failure, `goal-contracts.md`, "rigor about the wrong layer").

## The adversary attacks what the judge certifies

The judge is scripted verification. It checks the artifact against the plan, the tests, and the `production-standards` and `ai-security-standards` gates, so it catches the failures someone thought to specify. It is blind to the failure nobody wrote a check for. For System 3 that blind spot is the dangerous one: the failure mode here is a fluent wrong answer, not a failed assertion, and a green judge verdict does not touch it.

The adversary is the unscripted half. It uses the running system in hostile ways the spec never imagined: malformed and boundary input, out-of-order operations, edge cases, and above all queries engineered to draw a confident wrong answer, especially queries where the graph returns nothing and the system should refuse rather than answer from priors. It is the pressure the cite-or-refuse gate needs before it is trusted: does the system actually refuse, or does it fabricate a fluent, uncited, biomedically plausible answer? It over-reports on purpose, because for a biomedical user a false alarm is cheap and a missed wrong answer is not. It files every finding to a shared ledger AS IT FINDS IT, not in a batch at the end, and stops there. It never fixes, triages, or closes its own findings; the judge or a fix agent triages them, and only the ledger's designated closer closes them. This is the maker-cannot-sign-off split of `self-eval-loop.md` applied to verification itself: the finder is never the closer.

Two obligations sit on the judge beyond producing evidence.

- The judge closes the board. It is the only role permitted to move a ticket from `in-review` to `done`, and the only one permitted to set `rejected`, each with a one-line reason and its evidence pasted into the ticket. If the judge does not touch the board, the phase does not close, because nothing else may write that state. The `task-tracker` skill owns the state table and the transitions.
- A phase that ships user-facing interface does not pass on a code review alone. It needs a Playwright run proving the flow works in a browser, and it is marked product owner required so a human decides whether it actually feels right. An agent can verify that a button exists. It cannot verify that the thing is good.

Run the adversary after the judge, only on a phase that produced a runnable artifact. A green judge verdict is necessary but not sufficient; the adversary is what decides whether the answer path is actually trustworthy. Source: the Personal Space autonomous build harness, analyzed in the personal-os Reference-repos set, which pairs a scripted qa role with a separate unscripted adversary.

## The review loop has a budget

This section exists because the review loop, not the build, is where phases actually lose their day. Build phase 2.1 took five rounds and build phase 4.2 took six, and in both, every round found its worst defect inside the previous round's fix. That is not a scrutiny problem. Five rounds of increasing scrutiny did not lower the recurrence rate.

Four rules, each traceable to a measured failure rather than to principle.

Rule 1, fan out on files and go serial on findings. Parallelism is a throughput lever for independent work and an active hazard for work that shares a seam. Two builders fixing two findings in the same file are each individually correct and structurally blind to the sibling editing the same function, so two correct fixes compose into a defect and no reviewer of either one sees it. Build phase 4.2 measured this directly: rounds 1 through 4 ran parallel fix agents, one per module, and each round's fix produced the next round's worst finding. Round 5 was run deliberately as a single agent holding every finding at once, closed both assigned findings, and found a sixth defect on a fallback path that four parallel rounds had walked past. So:

- Two findings in different files: parallel fix agents, as usual.
- Two or more findings touching the same file: one fix agent, holding all of them, serially. Never one agent per finding.
- The lead states the file-to-finding map before dispatching any fix, the same way it states the file scope of a build ticket.

Rule 2, fix by category, never by enumeration. The shape that keeps failing here is a defense that lists instances instead of naming the class: C0 and C1 control characters rather than the Unicode category, three exception types rather than the base class, five write sites rather than every write site. Every one of those shipped, passed its own test, and was bypassed by the sixth case. A fix that enumerates is rejected at review, even when every listed case is handled correctly. Fix by category, by base class, or by an exhaustive sweep of the call sites, and say in the ticket which of the three it is.

Rule 3, two rounds, then stop. The budget is one judge round plus one fix-and-reverify round. If round 2 still returns a blocking finding, the phase stops and escalates to the product owner instead of opening round 3. What it hands over is not "still failing":

- Which findings remain open, with severity.
- What each fix attempt changed, as a diff summary per attempt.
- Whether any round-2 finding sits inside a round-1 fix, named explicitly.
- Two or three options with a recommendation, one of which is always "revert this phase's fixes and re-decompose".

A phase that would have taken six rounds now costs two and a decision. This is the `goal-contracts` blocked-stop applied to review: a blocked stop is a valid, honest end state, and escalation must be cheaper than fighting the loop.

Rule 4, a regression inside a prior fix stops the round immediately. Do not finish the round, do not batch it with the round's other findings. When a reviewer locates a finding inside code written to fix an earlier finding in this same phase, the phase escalates on the spot, even in round 1, because that is the signal that the fix approach itself is wrong rather than incomplete. The finding is filed with `Regression of: F-N.M-XX` so the pattern is visible in the ledger rather than reconstructed afterwards from five reports.

Filed BEFORE the round stops, not as part of stopping. The order is written down because it was got wrong the first time this rule ever fired: on 2026-08-27 the re-verifier established the regression, announced the stop, moved on to tidying up before reporting, and died mid-sentence with the finding held only in its own context. Stopping is not an action that takes precedence over recording. Write the finding, then stop.

## Reviewing a fix, and reviewing a gate

Two additions to the judge's brief, both measured, both cheap to state and expensive to omit.

A fix is the most dangerous code in the phase, not the safest. It is the newest and least-exercised thing in the build, and it is written with the defect freshly in mind, which feels like safety and is not. So the review brief names the fix commits explicitly and says the newest code is the most dangerous code. Two consequences:

- A code comment that claims a security or correctness property is a claim to be tested, never documentation. Build phase 2.1's F-2.1-J5-01 was a comment asserting an invariant sitting directly above code that never implemented it, and it survived review because a confident comment is exactly where the next reader stops checking. Where a comment asserts a property, a test must assert the same property, or the comment gets deleted.
- When a fix adds a new code path that produces the same class of output, every prior finding about that output class is re-tested against the new path. A regression test proves the old route is shut and says nothing about a route that did not exist when it was written.

Never resume the judge to re-review its own findings. Resuming is cheaper on context and silently violates the raiser-never-closes rule, because the judge is then both raiser and closer even when a different agent authored the fix. Route re-verification to a fresh agent with no prior context, which re-derives the verdict from the code and tests rather than from anyone's summary.

Mutation-test every gate before it counts as evidence. Assertions that cannot fail are the single most repeated failure in `LEARNINGS.md`, eleven separate instances by 2026-08-14, and a gate's greenness on the day it is written proves nothing: four of the eleven were caught only by a mutation, not by reading the assertions. This is one line item on the judge's checklist, not a separate agent dispatch. For every new or changed gate the judge asks: break the thing this gate exists to catch, and does the gate go red? If it stays green, the gate fails and the finding is a vacuous gate arm, regardless of what the suite total says. Build phase 4.3 alone carried fourteen of them, several written by the lead.

Mutate one property, never revert the change. Added 2026-09-20 from a measured error that cost a published correction. An arm that fails when the whole change is REVERTED has not been shown to test anything: it usually fails with a missing function, parameter or test id, before it ever evaluates its assertion, so the red proves only that a symbol went away. The honest check mutates ONE property and leaves every symbol intact. Applied across one day's work it found that one of three notes arms was load-bearing rather than three, and that six of eight source-grouping arms discriminate while two are deliberate invariants. The lead made this error too, in commit `9d20438`'s own message, and corrected it in `3a3c455` rather than leaving it.

The populate-check, from build phase 4.11, on every bound arm: an arm that cannot distinguish the control holding from nothing having happened is not an arm. Three vacuous arms in that phase were caught by mutation and none by reading, one of them vacuous twice while quoting the lesson against vacuous arms in its own docstring.

Beware safety-by-proxy. A repair whose check verifies a correlate of the property rather than the property itself survives its own fix. Build phase 4.3 shipped this shape as a critical twice, and build phase 4.7's first vacuous-arm repair reproduced it. The test: does the assertion read the property the gate exists to protect, or something that usually moves with it?

## Shared-ledger coordination

When parallel agents share findings, defects, or task state, they coordinate through one shared markdown ledger, not by each writing wherever they like. Without a convention, two agents writing status to the same file overwrite each other, and an agent that raised an item can quietly close it. A single-writer-per-state ledger removes both races by construction and leaves an auditable trail.

The ledger is a real file, not an abstraction: `tracker/phase_N.M.md`, the same phase file the tickets live in, under its Findings section. Adversary findings and builder defects both land there. Keeping findings beside tickets in one file is deliberate, since a confirmed finding usually becomes a fix ticket, and that transition should not cross a file boundary. The `task-tracker` skill owns the format. Five rules:

- Write first, then continue. A finding is written to the ledger the MOMENT it is established, before the agent does anything else: before it verifies tree cleanliness, before it finishes the round, before it composes a report, before it reruns anything to be sure. This is the newest rule and the only one added from a loss rather than from a principle. On 2026-08-27 a re-verifier found the phase's blocking regression, said "the stop condition has fired, let me verify tree cleanliness and clean up before reporting", and died to an infrastructure error mid-sentence. The finding existed in exactly one place, that agent's context, and nowhere on disk. It was recovered only because the lead noticed the last line, resumed the agent, and told it to write before doing anything else. That recovery depended on a human-shaped judgment call at the right moment, which is not a mechanism. Four agents died that day to sleep interruptions and a watchdog stall, so the loss was not rare; it was survived once. An unwritten finding is not a finding, it is a memory in a process that can end between two sentences.
- Single writer per state: each state in the ledger has exactly one role authorized to set it. The adversary files findings, the judge or a fix agent triages, only the designated closer closes. No state has two writers.
- Mandatory reason on judgment states: any state that reflects a judgment call (accepted, rejected, closed, disputed) carries a one-line reason. A bare status change with no reason is invalid.
- Append-only history line per transition: every transition appends a who-what-why line to the item's history. History is never rewritten, only extended, so the trail reconstructs the full life of the item.
- The raiser never closes: the party that raised an item is never the party that closes it. The finder reports, a different role verifies and closes. This is the same finder-is-not-closer rule the adversary follows.

## Why judge and adversary never tier down

Both roles run on the Depth tier, judge at high or extra high effort and adversary at high. Every other role in this harness was re-tiered downward on 2026-08-02 against measured evidence. These two did not move, for one reason: this repository has direct evidence that a weaker review costs entire rounds, not just latency.

- Build phase 2.1 failed four consecutive judge and adversary reviews behind a fully green test suite before the real defect was found.
- The fifth pass found a defect class, every two-hop question unanswerable, that the phase's own premise gate could not see.

Two consequences bind dispatch:

- A judge or adversary pass run on the alternate metered backend records findings and closes nothing, because that backend sets a session-wide subagent model that silently overrides the per-dispatch tier. A judge dispatched at Depth there runs on whatever the builders ran on, and nothing reports the substitution. If the same model both built and graded the work because that was the only session available, the grade is not a check. Stages 8 and 9 re-run on the primary provider before anything merges.
- Raising or lowering a tier needs a specific cited miss recorded as a finding or a `LEARNINGS.md` entry, never a feeling. The tier-to-model mapping is in `docs/build/Build_workflow_cadence.md` under "Provider mapping", which is the only place a product name appears.
