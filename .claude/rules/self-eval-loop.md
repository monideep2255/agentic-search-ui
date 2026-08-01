---
description: "For skills or agent runs producing substantial output, grade with a second agent that has fresh context against pass/fail criteria. The agent that produced the output never signs off on it."
scope: portable
alwaysApply: true
---

## Self-eval loop

For skills producing substantial output, use a two-agent pattern. A second agent with fresh context grades the output against pass/fail criteria. This is more reliable than single-shot self-review because fresh context removes the "I wrote it so it must be good" bias.

This is the maker/checker split: the model that produced the output must never be the one that signs off on it, because a model grading its own work just agrees with itself. The checking signal has to come from somewhere the maker does not control: a different agent, a test, a grep, a count.

### The pattern

1. First agent produces the output (doc, analysis, multi-file change)
2. Second agent with fresh context receives only the output and the pass/fail criteria
3. Second agent grades each criterion as pass or fail with a one-line justification
4. If any criterion fails, iterate: fix the issue, then re-grade

### When to apply

- Docs, proposals, or architecture writeups with 3+ sections
- Multi-file system changes (new tools, agent-loop changes, rule rewrites)
- Any output that will be reviewed by someone else
- The bossman-mode judge step (see `.claude/skills/bossman-mode/SKILL.md`), which already uses this pattern

### When NOT to apply

- Quick edits, single-file patches, or formatting fixes
- Meeting notes and checklists (capture tasks, not judgment)
- When the user explicitly says "skip review" or "good enough"
- When time constraint makes iteration impractical (user waiting, urgent fix)

### Context isolation matters

The second agent must start with a clean context window. Do not pass the first agent's reasoning, draft history, or conversation context. The grading agent receives:

1. The final output (file paths or inline content)
2. The pass/fail criteria (a numbered checklist)
3. Nothing else

This isolation is what makes the pattern work. A self-reviewer that inherits the author's context inherits the author's blind spots.

### Two verification modes: scripted checker and unscripted adversary

The grading agent above is a scripted checker. It runs the output against a fixed pass/fail checklist and owns the accept or reject call. That is the right default, and it has a blind spot: it only tests what the checklist names, so a failure nobody wrote a criterion for slips through. A fluent-but-wrong answer, a bad-input crash, an odd-sequence corruption, all pass a green checklist.

The second mode is an unscripted adversary. Instead of grading against known criteria, it uses the running output in hostile ways the checklist never imagined: malformed and boundary input, out-of-order operations, edge cases, and for a question-answering system, queries engineered to draw a confident wrong answer. It over-reports on purpose, because a false alarm is cheap and a missed defect is not. Critically, the finder is never the closer: the adversary files findings, it does not fix, triage, or close them. A separate role verifies and closes, the same maker-cannot-sign-off split that governs the scripted checker.

When each applies:
- Always run the scripted checker for substantial output. It is the accept or reject gate.
- Add an adversary when the output is runnable and a plausible-but-wrong result is worse than an obvious failure. Agentic search is the clear case: a confident wrong answer is more dangerous than a crash, so the cite-or-refuse gate needs an adversary throwing hostile queries at it before it is trusted.

Adversary findings land in a shared-ledger file, not scattered across agent outputs. Each state has a single writer, judgment states carry a reason, and every transition appends a history line, so the finder-is-not-closer rule holds by construction. The full convention is the "Shared-ledger coordination" subsection in `.claude/skills/bossman-mode/SKILL.md`. Source: the Personal Space autonomous build harness, analyzed in the personal-os Reference-repos set, which pairs a scripted qa role with a separate unscripted adversary.

### Review a fix harder than new code

A fix landing in the same phase as the finding it repairs deserves MORE
scrutiny than untouched code, not less. This is counter-intuitive, because
a fix is written with the defect freshly in mind and feels safer than
unreviewed new work.

Build phase 2.1 measured it: across six review rounds, the worst defect
found in every single round was in the code written to fix the previous
round. The same invariant was defeated three separate times, each time by
its own replacement. Findings F-2.1-J4-03, J4-05, J4-06, J5-01 and A5-01
were all regressions in fixes, and one entire review round existed only to
catch the previous round's damage.

Two practices follow:

- Say so in the review brief. A judge or adversary told "the newest code is
  the most dangerous code, and here are the commits that are new" hunts
  where the defects actually are.
- Treat a code comment that CLAIMS a property as a claim to be tested, not
  as documentation. F-2.1-J5-01 was a comment asserting "a WITH does not
  launder an unanchored variable" sitting directly above code that never
  read WITH at all. It survived review because a confident comment is
  exactly where the next reader stops checking. Where a comment asserts a
  security or correctness property, a test must assert the same property,
  or the comment is a liability rather than an aid.

### Relationship to goal-contracts and objective-review

This rule is the verify surface `goal-contracts.md` points to whenever the check is "a second-agent grade" rather than a test or a grep: the contract names it, this rule defines how to run it. The two compose on any substantial autonomous output: write the done-when and pass/fail criteria first, then grade against them with a fresh-context agent.

`objective-review` is the user-facing sibling, not a substitute. It critiques work the user produced and hands feedback back for the user to weigh, per `preserve-your-thinking.md`. This rule grades agent-produced output against a fixed checklist and iterates until it passes. Different target, different exit condition: objective-review ends in a conversation the user owns, self-eval-loop ends in a pass or a fix.

### Three-state permissions

Allow:
- Dispatch a grading agent for any substantial output without asking
- Iterate on failed criteria without asking

Ask:
- Before running a third iteration (if two rounds of fixes have not resolved a failing criterion, the criterion itself may be wrong)

Deny:
- Never skip the grading step for substantial output in bossman mode
- Never pass conversation history to the grading agent

The test: did my substantial output get graded by a fresh-context agent, or did I only self-review in the same context?
