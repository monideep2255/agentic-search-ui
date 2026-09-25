# Review rounds: the judge, the adversary, and the budget

Read this before dispatching a judge or an adversary, and again before dispatching any fix agent or verifier. Nothing else in this skill needs it, which is why it is a separate file: a reviewer reads it alone rather than finding it buried in a phase-open checklist.

This file is the canonical home of the four review-loop rules. `docs/build/Build_workflow_cadence.md` carries a condensed version and points here.

What changed on 2026-09-24, from the product owner's acceptance of `docs/build/Bossman_mode_redesign.md`:

- One judge round and one adversary round, then one fix-and-verify round. No third round, ever, even with the owner's authorisation.
- Premise gates, mutation harness files and coverage claims are gone for everything except answer behaviour. Breaking a control to see a test go red is one line on the judge's checklist, not a file and not a dispatch.
- Findings live as ledger rows in the phase file, not in per-round report files.

## Table of contents

- [The judge produces evidence, not a verdict](#the-judge-produces-evidence-not-a-verdict)
- [The adversary attacks what the judge certifies](#the-adversary-attacks-what-the-judge-certifies)
- [The review loop has a budget](#the-review-loop-has-a-budget)
- [Reviewing a fix, and reviewing a gate](#reviewing-a-fix-and-reviewing-a-gate)
- [When the findings are about the checks](#when-the-findings-are-about-the-checks)
- [Shared-ledger coordination](#shared-ledger-coordination)
- [Why judge and adversary never tier down](#why-judge-and-adversary-never-tier-down)

## The judge produces evidence, not a verdict

A judge that reports "looks good, all checks pass" without showing its work is the maker-checker failure `self-eval-loop.md` warns about: a grader that knows the rubric drifts toward approving everything. Force the judge to produce evidence, and default it to fail when evidence is absent.

For every claim, the judge's report must:

- Cite the exact `file:line` for a code finding, not "the agent loop looks fine".
- Paste the actual command output for a functional or test claim (the `pytest -q` result line, the lint output), not "tests pass".
- Quote the specific offending line for a security or quality finding, not "no security issues found".

If the judge cannot produce evidence for a check, that check fails. "I could not verify X" is a fail, never a pass.

The judge's checklist, one round, on the diff:

- Correctness: does each ticket meet its acceptance sentence, run the way production runs?
- Security and the `production-standards` gates: parameterized Cypher and SQL, schema validation at every agent-loop hop, cite-or-refuse on generated answers, no secrets in logs, a timeout on every tool call.
- The split: does the set of finished tickets satisfy the phase's done-when, or did every builder succeed at its own task while the tickets together miss the point (`goal-contracts.md`, "rigor about the wrong layer")?
- Break it, does a test go red: for each control the phase adds or changes, break one property of it and confirm a test fails. A test that stays green is a finding.

The judge does not close tickets. Tickets merge at `in-review` and reach `done` only on the product owner's verdict on develop. The judge may set a ticket to `rejected`, with a one-line reason and its evidence, which returns it to `in-progress`; the `task-tracker` skill owns the states. The judge also confirms or rejects the adversary's findings, never its own.

A phase that ships user-facing interface does not pass on a code review alone. The product reviewer drives the deployed screens at 1280 and 390 beside the prototype after merge, and the owner decides whether it actually feels right. An agent can verify that a button exists. It cannot verify that the thing is good.

## The adversary attacks what the judge certifies

The judge is scripted verification. It catches the failures someone thought to specify and is blind to the failure nobody wrote a check for. For System 3 that blind spot is the dangerous one: the failure mode here is a fluent wrong answer, not a failed assertion.

The adversary is the unscripted half. It uses the running system in hostile ways the spec never imagined:

- Malformed and boundary input.
- Out-of-order operations.
- Above all, queries engineered to draw a confident wrong answer, especially where the graph returns nothing and the system should refuse rather than answer from priors.
- The lying trust signal: a pill, an outcome or a status line that says something the answer does not bear out.

- It runs one round, after the judge, on any phase that changes runnable code. It does not run on a documentation-only change, and it never runs a second round.
- It over-reports on purpose, because for a biomedical user a false alarm is cheap and a missed wrong answer is not.
- It files every finding to the ledger AS IT FINDS IT, not in a batch at the end, and stops there. It never fixes, triages or closes its own findings.

This is the maker-cannot-sign-off split of `self-eval-loop.md` applied to verification itself: the finder is never the closer. Source: the Personal Space autonomous build harness, analyzed in the personal-os Reference-repos set, which pairs a scripted qa role with a separate unscripted adversary.

## The review loop has a budget

The review loop, not the build, is where phases lost their day. Build phase 2.1 took five rounds and build phase 4.2 took six, and in both, every round found its worst defect inside the previous round's fix. Rising scrutiny did not lower the recurrence rate. The two-round cap added on 2026-08-18 then held in only 4 of the 13 phases reviewed after it, because a third round could be authorised, and 17 extra rounds followed; build phase 5.0 ran seven on one control.

Four rules, each traceable to a measured failure rather than to principle.

Rule 1, fan out on files and go serial on findings. Two builders fixing two findings in the same file are each individually correct and structurally blind to the sibling editing the same function. Two correct fixes compose into a defect, and no reviewer of either one sees it. Build phase 4.2 measured this directly:

- Rounds 1 through 4 ran parallel fix agents, one per module, and each round's fix produced the next round's worst finding.
- Round 5, run deliberately as a single agent holding every finding at once, found a sixth defect on a fallback path four parallel rounds had walked past.

So:

- Two findings in different files: parallel fix agents, as usual.
- Two or more findings touching the same file: one fix agent, holding all of them, serially. Never one agent per finding.
- The lead states the file-to-finding map before dispatching any fix, the same way it states the file fence of a build ticket.

Rule 2, fix by category, never by enumeration. The shape that kept failing here is a defense that lists instances instead of naming the class:

- C0 and C1 control characters rather than the Unicode category.
- Three exception types rather than the base class.
- Five write sites rather than every write site.

Every one of those shipped and passed its own test. Each was then bypassed by the sixth case. A fix that enumerates is rejected at review, even when every listed case is handled correctly. The ticket says which of three accepted forms the fix takes:

- By category.
- By base class.
- By an exhaustive sweep of the call sites.

Rule 3, two rounds, then stop. The budget is one judge round and one adversary round, then one fix-and-verify round. The fix-and-verify round is the fix agents from Rule 1, then one fresh verifier that re-derives each verdict from the code and tests. If the verifier still finds a blocking item, the phase stops and hands the owner:

- Which findings remain open, with severity.
- What each fix attempt changed, as a diff summary per attempt.
- Whether any open finding sits inside a fix made in this phase, named explicitly.
- Exactly two options with a recommendation: merge with the open item named, as an open flag with an owner and a trigger, or revert this phase's changes and re-split.

A third round is not an option, and the owner's authorisation does not create one (DECISIONS.md, 2026-09-24). Build phase 4.4's third round was authorised so a reachable major would not merge open. Under this rule it merges named or it reverts. A blocked stop is a valid, honest end state. Escalation must be cheaper than fighting the loop.

Rule 4, a regression inside a prior fix stops the round immediately. Do not finish the round, and do not batch it with the round's other findings. When a reviewer locates a finding inside code written to fix an earlier finding in this same phase, the phase escalates on the spot, even in round 1, because that is the signal that the fix approach itself is wrong rather than incomplete. The escalation carries the same two options as Rule 3. The finding is filed with `Regression of: F-N.M-XX` so the pattern is visible in the ledger rather than reconstructed afterwards.

Filed BEFORE the round stops, not as part of stopping. On 2026-08-27 the re-verifier established a regression and announced the stop. It then moved on to tidying up before reporting, and died mid-sentence with the finding held only in its own context. Write the finding, then stop.

## Reviewing a fix, and reviewing a gate

A fix is the most dangerous code in the phase, not the safest. It is the newest and least-exercised thing in the build, and it is written with the defect freshly in mind, which feels like safety and is not. So the verifier's brief names the fix commits explicitly and says the newest code is the most dangerous code. Three consequences:

- A code comment that claims a security or correctness property is a claim to be tested, never documentation. Build phase 2.1's F-2.1-J5-01 was a comment asserting an invariant directly above code that never implemented it, and it survived review because a confident comment is exactly where the next reader stops checking. Where a comment asserts a property, a test must assert the same property, or the comment gets deleted.
- When a fix adds a new code path that produces the same class of output, every prior finding about that output class is re-tested against the new path.
- Never resume the judge to re-verify its own findings. Resuming is cheaper on context and silently makes the judge both raiser and closer. Route re-verification to a fresh agent with no prior context.

Mutate one property, never revert the change. This is how the judge's "break it, does a test go red" line is run. It is the whole of what survives of the old mutation machinery.

- An arm that fails when the whole change is REVERTED has not been shown to test anything. It usually fails on a missing symbol before it ever evaluates its assertion, so the red proves only that a symbol went away.
- The honest check breaks ONE property and leaves every symbol intact.
- Measured on 2026-09-20: applied across one day's work, it found that one of three notes arms was load-bearing rather than three. The lead made the revert error in commit `9d20438`'s own message and corrected it in `3a3c455`.

Two questions go with it. Does the test read the property itself, or a correlate that usually moves with it? Would it still pass pointed at a subject that had done nothing at all?

No mutation harness file is written for this, and none is dispatched. The judge runs it by hand in its own shared-checkout probe:

1. Break the property.
2. Observe the red.
3. Restore the file.
4. Record the result in its finding.

Answer behaviour is the exception the owner kept. An answer-path phase may still carry a premise gate for a behaviour the golden questions cannot see, written first and seen failing. The golden consistency run in `reference/Product_review.md` blocks regardless.

## When the findings are about the checks

By the last third of the build, 43 to 45 percent of review findings were defects in the harness's own tests, docstrings and board rows rather than in the product. Build phase 6.0 is the clearest case: 8 of its 12 findings, and every judge finding left open at merge said the gate did not pin the wiring while both features were verified working by execution.

So the lead counts, after each round, how many findings are about the phase's own tests or documents. If that is more than half, the phase stops writing checks and escalates: the effort has moved off the product. The escalation says:

- What the product findings were.
- What the instrument findings were.
- Whether any product defect is still open.

Coverage sentences are not written. A docstring, board row or commit message that claims a check covers every case is the "confident sentence" class, seven instances by build phase 6.2. Build phase 4.15 fixed its own case by deleting the claim. A test says what it checks by what it asserts.

## Shared-ledger coordination

When agents share findings or task state, they coordinate through one shared markdown ledger, not by each writing wherever they like.

- The ledger is `tracker/phase_N.M.md`, the same phase file the tickets live in, under its Findings section. That section stays the last in the file, so an append lands in it.
- Reviewers write ledger rows there and nowhere else. No per-round report file is written under `tracker/`.
- The 50 per-round report files the old cadence produced held 20,465 lines. The phase file already carried the finding id of all but one finding in them (`docs/build/Bossman_redesign_deletion_inventory.md`).
- The `task-tracker` skill owns the format.

Five rules:

- Write first, then continue. A finding is written to the ledger the MOMENT it is established, before the agent does anything else. On 2026-08-27 a re-verifier found the phase's blocking regression, said "the stop condition has fired, let me verify tree cleanliness and clean up before reporting", and died to an infrastructure error mid-sentence; four agents died that day. An unwritten finding is not a finding, it is a memory in a process that can end between two sentences.
- Single writer per state: each state in the ledger has exactly one role authorized to set it. The adversary files findings, the judge confirms or rejects them, the fresh verifier closes what it verified, and the lead records what merges open.
- Mandatory reason on judgment states: any state that reflects a judgment call (accepted, rejected, closed, disputed) carries a one-line reason.
- Append-only history line per transition: every transition appends a who-what-why line to the item's history. History is never rewritten, only extended.
- The raiser never closes: the party that raised an item is never the party that closes it.

## Why judge and adversary never tier down

Both roles run on the Depth tier at high effort. Every other role was re-tiered downward on 2026-08-02 against measured evidence. These two did not move, for one reason: this repository has direct evidence that a weaker review costs entire rounds, not just latency.

- Build phase 2.1 failed four consecutive judge and adversary reviews behind a fully green test suite before the real defect was found.
- The fifth pass found a defect class, every two-hop question unanswerable, that the phase's own checks could not see.

Two consequences bind dispatch:

- A judge or adversary pass run on the alternate metered backend records findings and closes nothing, because that backend sets a session-wide subagent model that silently overrides the per-dispatch tier. If the same model both built and graded the work because that was the only session available, the grade is not a check. The review re-runs on the primary provider before anything merges, and that re-run counts against the 8 dispatches.
- Raising or lowering a tier needs a specific cited miss recorded as a finding or a `LEARNINGS.md` entry, never a feeling. The tier-to-model mapping is in `docs/build/Build_workflow_cadence.md` under "Provider mapping", which is the only place a product name appears.
