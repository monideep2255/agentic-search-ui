---
description: "Autonomous execution mode - suspends deliberation rules when bossman mode is active"
alwaysApply: true
depends_on:
  - .claude/skills/bossman-mode/SKILL.md
  - .claude/rules/pause-before-acting.md
  - .claude/rules/preserve-your-thinking.md
  - .claude/rules/clarify-before-drafting.md
depended_by:
  - CLAUDE.md
  - .claude/README.md
---

## Bossman mode rule

When bossman mode is active (user has invoked `/bossman` and activation checklist passed):

### Suspended behaviors

- **Do not pause to check if clarification is needed** (overrides pause-before-acting step 2). Rules still apply, but you do not stop to ask.
- **Do not ask what the user thinks before acting** (overrides preserve-your-thinking). Decisions were made during planning. Execute.
- **Do not run Socratic clarification before drafting** (overrides clarify-before-drafting). Scope is defined.
- **Do not ask "should I do X or Y?"** - pick the better path, note the choice, keep moving.

### Preserved behaviors

- File protection: never delete without informing.
- Dependency tracking: track what you build.
- Writing style: output quality stays high.
- Git workflow: clean commits, no co-author lines.
- Parallel-first: maximize speed.
- Boil-the-lake: do it 100%.

### Three-state permissions

Allow:
- Write files, run commands, dispatch agents without conversational confirmation
- Make tactical decisions (library choice, file structure, naming) and log them
- Execute an entire phase autonomously

Ask:
- Architecture-level changes that contradict the agreed plan
- Anything that affects phases beyond the current one
- Deleting files or reverting prior work

Deny:
- Proceeding to the next phase without user approval
- Ignoring a blocker by guessing
- Pushing to remote without explicit instruction

### When bossman mode is NOT active

This rule has no effect. All suspended rules operate normally.
