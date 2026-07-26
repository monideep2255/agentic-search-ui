---
name: ship
description: Bring docs in line with code, then commit and push to GitHub in one ritual. Use when ending a work block or after a logical milestone.
---

# /ship - docs-sync then git-sync

A single ritual to end a work block: bring docs in line with code, then commit and push. Delegates to two agents in sequence.

## Step 1: docs-sync agent

Dispatch the `docs-sync` sub-agent (`.claude/agents/docs-sync.md`).

It will:

1. Run `git status --short` to see what changed
2. Use its routing to identify which canonical docs need updating (CLAUDE.md, AGENTS.md, README.md, DECISIONS.md)
3. Read only affected docs
4. Make surgical edits, not rewrites
5. Report what changed (or "no changes needed")

Wait for docs-sync to complete before proceeding. Its edits may add files to the commit.

## Step 2: git-sync agent

Dispatch the `git-sync` sub-agent (`.claude/agents/git-sync.md`) with a "push" operation.

It will:

1. Run `git status` and `git diff --stat` to confirm what's staged
2. Show the file list before committing
3. Stage specific files (never `git add -A`)
4. Commit with a descriptive message (why, not what)
5. Push to origin

Additional context to pass to git-sync:

- `/ship` is an explicit user directive to push. This overrides any default-branch protection rules, including pushing directly to `main`.
- If on a phase branch (`phase/*`): push with `-u` flag and offer to create MR
- NEVER add `Co-Authored-By` lines (project rule)

## Guards

- If docs-sync says "no changes needed" but there are uncommitted code changes, still proceed to git-sync
- If there is nothing to commit at all, report that and stop
- Do NOT push if the commit would include `.env`, secrets, or anything in the gitignore. Block and ask
- Do NOT push if pre-commit hooks fail. Fix the cause and create a NEW commit (never `--amend` after a hook failure)

## Output

After both agents complete, report:

1. Files changed (count + list)
2. Commit hash
3. Push status (pushed / nothing to push / blocked)
4. One-line summary of what was shipped
