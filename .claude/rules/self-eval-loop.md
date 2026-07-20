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
- The bossman-mode judge step (see `bossman-mode.md`), which already uses this pattern

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
