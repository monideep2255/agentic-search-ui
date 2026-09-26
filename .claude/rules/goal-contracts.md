---
description: "Before any autonomous or multi-step run, write a goal contract (done-when, verify, output, constraints, blocked-stop). Stop on verified evidence, not on feel."
scope: portable
alwaysApply: false
paths: ["HANDOFF.md", "DECISIONS.md", "LEARNINGS.md", "testing/UI_fix_plan.md", "testing/UI_fixes_done.md", "docs/build/*", ".claude/skills/bossman-mode/*", ".claude/skills/bossman-mode/reference/*", "{tracker,requirements}/**/*"]
---
## Goal contracts

Before you run any "keep going until it's done" task, write the finish line down first. An agent that starts looping without a verifiable definition of done will stop when it feels done, which is the single most common way autonomous work goes wrong: it overclaims completion.

This rule names the contract. The loop does not start until the contract exists.

### When to apply

- Any autonomous or multi-step task that runs to completion without a human in each step (bossman-mode phases, deep research, any background or long-running subagent)
- Any task you hand to a subagent with the instruction "do X until done"
- Any skill with an exit checklist (the checklist is the contract's verify surface)

### When NOT to apply

- Single-step lookups, quick edits, formatting fixes (done is obvious)
- Conversational turns where the user is steering each step
- Capture tasks (meeting notes, session notes) where there is no "done" to verify

### The contract (five elements)

Write these before the first action, not after:

1. Done when: the outcome in one testable sentence. Not "improve the docs" but "every new file has 5/5 frontmatter fields and 0 em dashes".
2. Verify: the concrete surface that proves it, a grep, a test, a file count, a second-agent grade. If you cannot name how you would check it, the goal is not yet a contract. The verify surface is immutable for the duration of the run: you may add checks, never weaken them.
3. Output: what artifact the run produces and where it lands (file path, table, commit).
4. Constraints: what must stay true throughout (no deletions without asking, no secrets in logs, style rules hold).
5. Blocked-stop: the condition under which you stop and report rather than guess. A blocked stop is a valid, honest end state, not a failure to hide.

### Completeness is part of done-when

When AI compresses a task from days to minutes, the old instinct to do 80 percent and iterate becomes wrong: if the full version costs 15 more minutes, do the full version. A task completable in one pass is a lake. Do it 100 percent, not a representative sample:

- User stories: write every one.
- Edge cases: cover every one.
- Acceptance criteria: cover every one.
- Agenda items: address every one.
- Action plans: list every task, not a shortlist.

A task that spans multiple weeks or quarters is an ocean: flag it as out of scope for a single done-when and plan it in phases instead.

This does not apply when:

- The task requires human judgment at each step: interviews, negotiations.
- The task has an external dependency blocking completion: waiting on another person.
- The task has hit genuine diminishing returns: a tenth draft of the same paragraph.

### Meta-prompt the contract for long runs

Hand-written contracts under-specify. For any run over roughly 30 minutes of autonomous work, do not write the contract from memory. Dispatch a fresh-context agent to read the target files first, surface hidden assumptions, constraints, and edge cases, then draft the five elements. Review its draft, tighten it, then launch. A second agent writing the contract is a maker-checker split applied upstream of execution instead of after it, and the file reads are independent work that parallelize (see `plan-then-fan-out`'s "Check for parallelism first" section).

The inline variant: let the executing agent write its own goal from your high-level intent. It works only when you hand it the same raw materials (the files to read, the exact validation command, the constraints) and tell it to ask before committing when the intent is underspecified. Otherwise the self-set goal drifts.

### The anti-patterns this blocks

"Feels done" is not done. Marking a multi-step task complete because the model judges it finished, with no artifact, test, or count checked, is the failure mode. Tie completion to evidence from the verify surface. This reinforces the maker-checker discipline (a second agent grades) and anti-rationalization (do not skip the check).

Reward hacking is the second failure mode, and it is subtler. An agent graded on "tests pass" or "eval score above X" can reach done-when by corrupting the check instead of doing the work: deleting a failing test, weakening an assertion, narrowing an eval set, or lowering a count threshold. The run then reports success while the thing the check existed to guarantee is now false. Changing the check so the check passes is a failed run, not a completed one. Name the shortcut and forbid it before the loop starts.

Budget or iteration caps are checkpoints, not success. When a cap is hit, the run stops and reports progress plus blockers. It does not declare done.

Rigor about the wrong layer is the third failure mode, and it hides behind a verify surface that is genuinely real. A check can audit every leaf output honestly and still certify a wrong answer, because the premise that generated those outputs was never checked. A measured instance: a research run verified all twenty of its facts against two independent authoritative sources each, an honest and rigorous verify surface, and still shipped a wrong answer, because the premise that produced the fact list (the list itself, built from model memory) went unverified. The rigor was real and pointed one layer too low. When the decomposition or premise matters, the verify surface must cover it, not only the leaves. Done-when should name the premise as a checkable element, or the contract certifies a confident wrong answer with a clean audit trail.

### The inverse: never corrupt the subject to satisfy the check

The reward-hacking rule above forbids weakening the CHECK so it passes. The
mirror image is just as damaging and reads as diligence rather than as a
shortcut: changing the SUBJECT so a correct-looking check goes green, when
the subject was right and the check was measuring something else.

Measured on 2026-08-25. `tracker/check_doc_drift.py` reported
`requirements/Plan.md` stale for saying build phase 3.1 merged as PR #22,
computing PR #23. Git showed PR #22 merged `phase/3.1-ncbi-efetch` and PR
#23 merged a separate `fix/3.1-rereview-round1-critical-regressions`
branch. The document was describing the phase merge, the checker defines a
phase's PR as the last one that closed it, and both were right about
different events. Editing the document to say #23 would have turned a true
sentence into a false one and produced a green gate certifying a wrong
record. The sentence was rewritten to state both parts instead, and
`tracker/BOARD.md` and `tracker/phase_4.16.md` were deliberately LEFT
UNCHANGED where the same ambiguity exists for build phase 4.12.

So when a gate fires, establish which of three things is true before
editing anything:

- The subject is wrong: fix the subject. The ordinary case.
- The check is wrong: fix the check, and say so out loud rather than
  routing around it.
- Both are right and they are measuring different things: make the subject
  unambiguous, and change neither definition.

The third case is the one that gets mishandled, because the second and
third are indistinguishable from the gate's output alone. A red gate is a
question, not an instruction.

Deny:
- Never edit a document, a fixture, or a data file so a check passes when
  the thing you edited was correct. That is the same failed run as
  weakening the check, arrived at from the other side.

### A verify surface must state its own coverage

The failure above says a verify surface can point one layer too low. This
one says it can point at the right layer and still have a hole, because
nothing forces it to declare what it does not test.

Build phase 2.1's premise gate caught two regressions before a reviewer
did, and still missed finding F-2.1-A5-03, a defect that made every
two-hop question unanswerable, because all nine of its questions happened
to be one hop from a single anchor type, the same blind spot as the code
it graded. Full account: LEARNINGS.md's retrospective ("why build phase
2.1 took five review rounds").

So a verify surface must state, in its own file, which shapes of input it
exercises and which it deliberately omits. That statement is what makes a
gap arguable. Without it, a green gate reads as "this class is covered"
when it may mean "the cases someone happened to think of are covered".

The test: if someone asked "what would this gate miss", could they answer
from the gate itself, or would they have to re-derive it?

### Three-state permissions

Allow:
- Write the contract inline at the top of any autonomous run without asking
- Treat a named blocked-stop as a clean end state

Ask:
- Before continuing past a blocked-stop by guessing at the missing input

Deny:
- Never start an autonomous loop with no testable done-when and no verify surface
- Never mark a multi-step task complete on feel, with no evidence from the verify surface
- Never change, weaken, delete, narrow, or skip the verify surface (tests, assertions, eval cases, count thresholds) to reach done-when. Changing the check so the check passes is a failed run
- Never treat a leaf-level verify surface as complete when the premise or decomposition that generated the leaves is itself unverified. The premise is part of the verify surface

The test: before I started running to completion, did I write a testable done-when and name how I would verify it?
