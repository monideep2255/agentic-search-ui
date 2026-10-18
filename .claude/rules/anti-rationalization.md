---
description: "Block the LLM from rationalizing away steps in multi-step skills by naming common shortcuts and countering them."
scope: portable
alwaysApply: true
---

## Anti-rationalization

Models skip steps in multi-step skills when a step feels like extra work. Naming the excuse and blocking it works. Repeating the instruction does not.

Before acting, check which rules apply and whether something must be asked first. Then execute.

| The excuse | The counter |
|---|---|
| The user already validated this | Run every step the skill names. |
| Too simple to need the review | Simple tasks hide errors. Run it. |
| I remember what the file says | Memory goes stale. Read the file. |
| The user is in a hurry | Speed is not permission to skip. |
| This step repeats the last one | Similar is not identical. Run it. |
| Good enough without the final pass | The exit checklist is the bar. |
| Combine steps to save time | Combining loses the checks between them. |

Applies to any skill with four or more steps or an exit checklist (`/ship`, `/release`, `/dev-standards`, `/precommit`, `/verify`, bossman-mode phases). Not to single-step tasks, or when the user says to skip a step. Full text, and how to extend the table: `.claude/rules-reference/anti-rationalization.md`.

The test: did I run every step in the skill, or did I skip one with a plausible excuse?
