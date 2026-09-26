---
description: "For skills or agent runs producing substantial output, grade with a second agent that has fresh context against pass/fail criteria. The agent that produced the output never signs off on it."
scope: portable
alwaysApply: false
paths: ["HANDOFF.md", "DECISIONS.md", "LEARNINGS.md", "testing/UI_fix_plan.md", "testing/UI_fixes_done.md", "docs/build/*", ".claude/skills/bossman-mode/*", ".claude/skills/bossman-mode/reference/*", "{tracker,requirements}/**/*"]
---
## Self-eval loop

For skills producing substantial output, use a two-agent pattern. A second agent with fresh context grades the output against pass/fail criteria. This is more reliable than single-shot self-review because fresh context removes the "I wrote it so it must be good" bias.

This is the maker/checker split: the model that produced the output must never be the one that signs off on it, because a model grading its own work just agrees with itself. The checking signal has to come from somewhere the maker does not control: a different agent, a test, a grep, a count.

### The pattern

1. First agent produces the output (doc, analysis, multi-file change)
2. Second agent with fresh context receives only the output and the pass/fail criteria
3. Second agent grades each criterion as pass or fail with a one-line justification
4. If any criterion fails, iterate: fix the issue, then re-grade. At most two rounds. If a criterion still fails after the second, stop: ship with the failing criterion named as open, or revert. There is no third round

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

Adversary findings land in a shared-ledger file, not scattered across agent outputs. Each state has a single writer, judgment states carry a reason, and every transition appends a history line, so the finder-is-not-closer rule holds by construction.

A finding is written the moment it is established, before the finder does anything else with it. Not after the round finishes, not while composing a report, not after one more check to be sure. An agent's context is not storage: it ends without warning, and on 2026-08-27 four agents in one session ended to sleep interruptions and a watchdog stall, one of them mid-sentence holding the phase's blocking regression. It was recovered only because a human noticed the agent's last line and resumed it with an instruction to write before doing anything else, which is a rescue rather than a mechanism. The cheapest possible durability, an append to a markdown file, is available at the moment of discovery and costs nothing. The full convention is the "Shared-ledger coordination" subsection in `.claude/skills/bossman-mode/reference/Review_rounds.md`. Source: the Personal Space autonomous build harness, analyzed in the personal-os Reference-repos set, which pairs a scripted qa role with a separate unscripted adversary.

### Review a fix harder than new code

A fix landing in the same phase as the finding it repairs deserves MORE
scrutiny than untouched code, not less. This is counter-intuitive, because
a fix is written with the defect freshly in mind and feels safer than
unreviewed new work.

Build phase 2.1 measured it: across six review rounds, the worst defect in
every round was a regression in the previous round's fix, the same
invariant defeated three separate times by its own replacement (findings
F-2.1-J4-03, J4-05, J4-06, J5-01, A5-01). Full account: LEARNINGS.md's
retrospective ("why build phase 2.1 took five review rounds").

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
- Iterate on failed criteria without asking, up to two rounds

Ask:
- When a criterion still fails after the second round: name it and ask whether to ship with it named as open or revert. Those are the only two options

Deny:
- Never run a third iteration, even with the owner's authorisation. After two rounds, ship with the failing criterion named as open, or revert
- Never skip the grading step for substantial output in bossman mode
- Never pass conversation history to the grading agent
- Never hold an established finding in context while doing something else first. Write it, then continue. A finding that exists only in a running process is one interruption away from never having been found

Why the third iteration moved from Ask to Deny, on 2026-09-24:

- The two-round cap added on 2026-08-18 held in only 4 of the 13 build phases reviewed after it, because an Ask let each extra round be authorised.
- 17 extra rounds followed. Build phase 5.0 ran seven on one control.
- The product owner accepted "No third review round, even with the product owner's authorisation" (DECISIONS.md, 2026-09-24).

If two rounds have not resolved a criterion, the criterion itself may be wrong. A third round was never the way to find that out.

The test: did my substantial output get graded by a fresh-context agent, or did I only self-review in the same context?

The second test, added 2026-08-27: if this agent died right now, would anything it has established still exist?
