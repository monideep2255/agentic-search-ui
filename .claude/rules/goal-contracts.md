---
description: "Before any autonomous or multi-step run, write a goal contract (done-when, verify, output, constraints, blocked-stop). Stop on verified evidence, not on feel."
scope: portable
alwaysApply: true
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

### Meta-prompt the contract for long runs

Hand-written contracts under-specify. For any run over roughly 30 minutes of autonomous work, do not write the contract from memory. Dispatch a fresh-context agent to read the target files first, surface hidden assumptions, constraints, and edge cases, then draft the five elements. Review its draft, tighten it, then launch. A second agent writing the contract is a maker-checker split applied upstream of execution instead of after it, and the file reads are independent work that parallelize (see `parallel-first`).

The inline variant: let the executing agent write its own goal from your high-level intent. It works only when you hand it the same raw materials (the files to read, the exact validation command, the constraints) and tell it to ask before committing when the intent is underspecified. Otherwise the self-set goal drifts.

### The anti-patterns this blocks

"Feels done" is not done. Marking a multi-step task complete because the model judges it finished, with no artifact, test, or count checked, is the failure mode. Tie completion to evidence from the verify surface. This reinforces the maker-checker discipline (a second agent grades) and anti-rationalization (do not skip the check).

Reward hacking is the second failure mode, and it is subtler. An agent graded on "tests pass" or "eval score above X" can reach done-when by corrupting the check instead of doing the work: deleting a failing test, weakening an assertion, narrowing an eval set, or lowering a count threshold. The run then reports success while the thing the check existed to guarantee is now false. Changing the check so the check passes is a failed run, not a completed one. Name the shortcut and forbid it before the loop starts.

Budget or iteration caps are checkpoints, not success. When a cap is hit, the run stops and reports progress plus blockers. It does not declare done.

Rigor about the wrong layer is the third failure mode, and it hides behind a verify surface that is genuinely real. A check can audit every leaf output honestly and still certify a wrong answer, because the premise that generated those outputs was never checked. A measured instance: a research run verified all twenty of its facts against two independent authoritative sources each, an honest and rigorous verify surface, and still shipped a wrong answer, because the premise that produced the fact list (the list itself, built from model memory) went unverified. The rigor was real and pointed one layer too low. When the decomposition or premise matters, the verify surface must cover it, not only the leaves. Done-when should name the premise as a checkable element, or the contract certifies a confident wrong answer with a clean audit trail.

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
