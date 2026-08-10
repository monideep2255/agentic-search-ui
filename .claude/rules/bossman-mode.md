---
description: "Autonomous execution mode - suspends deliberation rules, uses agent teams for builders, skill chain at phase end"
---

## Bossman mode rule

When bossman mode is active (user has invoked `/bossman` and activation checklist passed):

### Suspended behaviors

- **Do not pause to check if clarification is needed** (overrides the pause-before-acting check in anti-rationalization, step 2). Rules still apply, but you do not stop to ask.
- **Do not ask what the user thinks before acting** (overrides preserve-your-thinking). Decisions were made during planning. Execute.
- **Do not run Socratic clarification before drafting** (overrides the clarify-before-drafting section of preserve-your-thinking). Scope is defined.
- **Do not ask "should I do X or Y?"** - pick the better path, note the choice, keep moving.

### Preserved behaviors

- File protection: never delete without informing.
- Dependency tracking: track what you build.
- Writing style: output quality stays high.
- Git workflow: phase branches, MRs, clean commits, no co-author lines.
- Parallel-first (in plan-then-fan-out): maximize speed via agent teams for builders.
- Boil-the-lake (in goal-contracts): do it 100%.
- Skill chain at phase end: a judge round, an adversary round, the gates named in `docs/build/Build_workflow_cadence.md` stage 10 (`verify`, `dev-standards` where warranted, `eval-harness` when an answer-generation feature shipped) -> `ship`. Rewritten at Step 6.2, 2026-08-10, to match measured practice: `release-workflow` as a single mandatory phase-end dispatch had a 0-of-6 real dispatch rate through build phase 3.4, while the judge, adversary, and gate sequence above ran, and caught real defects, every phase. Per this repo's own `attack-the-constraint` standard, an unenforced mandate is an ownerless requirement; `release-workflow` stays available to invoke directly whenever its end-to-end local-verify-then-ship ritual is wanted, it is just no longer the assumed default.

### Dispatch model

- 2+ parallel builder tasks: use agent teams (teammates in tmux panes)
- Single-task roles (researcher, judge, test writer): use sub-agents
- See `.claude/skills/bossman-mode/SKILL.md` for full team composition

### Three-state permissions

Allow:
- Write files, run commands, dispatch agents and teammates without conversational confirmation
- Create agent teams for parallel builder tasks
- Make tactical decisions (library choice, file structure, naming) and log them
- Execute an entire phase autonomously on a phase branch
- Run the judge round, adversary round, and stage-10 gates, then ship, at phase end

Ask:
- Architecture-level changes that contradict the agreed plan
- Anything that affects phases beyond the current one
- Deleting files or reverting prior work
- External data downloads: present exact URLs and file names for user verification before downloading

Deny:
- Proceeding to the next phase without user MR approval
- Ignoring a blocker by guessing
- Pushing to develop directly (push to phase branch only, merge via MR), except through the sanctioned /ship release chain at phase end, where ship/SKILL.md's explicit user directive overrides this and permits pushing directly to develop

### When bossman mode is NOT active

This rule has no effect. All suspended rules operate normally.
