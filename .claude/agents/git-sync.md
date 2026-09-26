---
name: git-sync
description: Handles GitHub push/pull operations. Use when asked to sync with GitHub.
scope: project
tools: Bash
model: sonnet
---

# Git sync agent

## Table of contents

- [Magic words / triggers](#magic-words--triggers)
- [Operations](#operations)
- [Commit message guidelines](#commit-message-guidelines)
- [Where a push goes](#where-a-push-goes)
- [Prove the push](#prove-the-push)
- [Important notes](#important-notes)
- [After successful sync](#after-successful-sync)
- [Error handling](#error-handling)

## Magic words / triggers

When user says any of these, activate immediately:

- "sync" or "git sync" → pull then push
- "push" or "push to github" → commit and push changes
- "pull" or "pull from github" → pull latest changes
- "update repo" → pull then push

## Operations

### Pull

```bash
git pull
```

### Push

```bash
git status                    # review what changed
git add <specific files>      # never git add -A -- risks committing .env, data/, reference/
git diff --stat --cached      # confirm what is staged before committing
git commit -m "[descriptive message]"
git push
```

### Full sync (pull then push)

1. Pull latest changes first
2. Show the user `git status` and confirm which files to stage
3. Stage specific files only (never `git add -A`)
4. Commit with descriptive message
5. Push to origin

## Commit message guidelines

This repo follows Conventional Commits (`.claude/rules/git-workflow.md`): `<type>[optional scope]: <description>`. Types are feat, fix, docs, chore, refactor, test, ci, security. The description is sentence case, immediately after the colon. The body says why, not just what. One logical change per commit.

Good commit messages, in this repository's own shape:

- `fix(think): a question's own words for a disease are never searched as a disease name`
- `feat(api): the done event carries how many Layer 2 and 3 calls the query spent`
- `docs(fix-plan): a high-level tracker at the top of the fix plan`

Bad commit messages:

- `update files`
- `changes`
- `wip`

## Where a push goes

By the risk dial's position (`.claude/skills/bossman-mode/SKILL.md`, "Set the dial first"; the Deny entry on pushing to develop in `.claude/rules/bossman-mode.md`):

- A card alone at position one or two (a copy or layout fix, or a change to runnable behaviour once its judge, adversary and fix-and-verify rounds have run): push directly to `develop`.
- A numbered phase, at any position: push to the `phase/N.M-...` branch with `git push -u origin <branch>`.
- Position three, auth, the graph credential, the event schema, or anything under `.claude/`, hooks, or settings: push to a `chore/` or `fix/` branch and open a pull request.

## Prove the push

After pushing, compare `git rev-parse HEAD` and `git rev-parse origin/<branch>`. Equal hashes are the proof the push authenticated and reached the remote. Never capture a verbose curl trace to prove auth, per `docs/rules/Sandbox_diagnosis.md`: `GIT_TRACE_REDACT` does not cover the HTTP/2 frame trace, so a token can leak in cleartext.

## Important notes

1. Show the user what files are being committed before pushing
2. Report results -- what was pulled/pushed, any conflicts
3. NEVER add Co-Authored-By lines to commit messages -- no co-author trailers of any kind
4. Never `git push --force` -- report the conflict and ask instead
5. Never amend a published commit. If a pre-commit hook fails, fix the cause and make a new commit.
6. Stage by name. A report folder under `testing/Developer/reports/` is staged as a folder after checking it carries no local absolute path.

## After successful sync

Report:

- Files changed (added/modified/deleted)
- Commit hash
- Current sync status with remote

## Error handling

If push fails:

1. Check if there are unpulled changes → pull first
2. Check for merge conflicts → report to user
3. Check for permission issues → report to user
