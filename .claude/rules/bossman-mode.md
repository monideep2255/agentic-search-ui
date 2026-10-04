---
description: "Autonomous execution mode - suspends deliberation rules, runs one cadence with a risk dial inside 8 hours, 8 dispatches and two review rounds, ends every change on a product review of develop"
paths: ["tracker/phase_*.md", ".claude/skills/bossman-mode/**/*"]
---
## Bossman mode rule

Applies only while bossman mode is active. Read the full text at activation: `.claude/rules-reference/bossman-mode.md`.

Suspended while active:

- The pause to check whether clarification is needed.
- Asking what the user thinks before acting.
- Socratic clarification before drafting.
- Asking "X or Y?". Pick the better path, note the choice, keep moving.

Preserved regardless:

- File protection, dependency tracking, writing style.
- Git workflow: a branch and a pull request for every numbered phase and for dial position three, clean commits, no co-author lines.
- Parallel builders, and doing the whole job.
- The v1 scope boundary.
- The skill chain at the end of a change: the judge, adversary and one fix-and-verify round where the dial runs them, then `precommit`, `ship`, and the product review of develop.

Every phase runs inside 8 hours and 8 agent dispatches, with at most two review rounds, the golden run blocking any answer-path change, and work ordered by what a person sees first.
