---
name: ship
description: Bring docs in line with code, commit and push to GitHub, and clear away leftover agent worktrees, in one ritual. Use when ending a work block or after a logical milestone.
---

# /ship - docs-sync, git-sync, then worktree cleanup

A single ritual to end a work block: bring docs in line with code, commit and push, then clear away any worktrees and branches that background agents left behind. The first two steps delegate to an agent each; the third is done directly, because it deletes things and the check that makes deletion safe is three commands.

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

- `/ship` is an explicit user directive to push. This overrides any default-branch protection rules, including pushing directly to `develop`.
- If on a phase branch (`phase/*`): push with `-u` flag and offer to create MR
- NEVER add `Co-Authored-By` lines (project rule)

## Step 3: leftover worktree cleanup

Agents dispatched with `isolation: "worktree"` each get their own git worktree and a `worktree-agent-*` branch. Neither is removed when the agent finishes, so they accumulate silently: four had built up across three sessions before anyone looked, one of them still holding a checked-out worktree on disk.

They are not harmless clutter. A stale worktree keeps a second checkout of the whole repository on disk, and a stale branch makes `git branch` unreadable, which is exactly the list a person scans when deciding what is safe to delete.

Run this after the push, never before:

```bash
git worktree list
git branch | grep worktree-agent
```

For each `worktree-agent-*` branch, before removing anything:

1. Check it holds no unmerged work: `git log develop..<branch> --oneline`. A non-empty result means the branch has commits `develop` does not, and it is NOT a leftover. Stop and report it.
2. If it has a live worktree, check that worktree for uncommitted files: `git -C <worktree-path> status --short`. Untracked scratch is normally the agent's own probes and is safe to drop, but say what it was rather than removing it silently.
3. Only then: `git worktree remove --force <path>`, `git worktree prune`, and `git branch -D <branch>`.

Report which branches and worktrees were removed, and name anything skipped and why. If a branch had unmerged commits, do NOT delete it, and surface it to the user as its own item; that is a lost-work risk, not housekeeping.

This step is deletion, so it follows `file-protection`: say what is going before it goes. The check in step 1 is what makes that statement true rather than hopeful.

## Guards

- If docs-sync says "no changes needed" but there are uncommitted code changes, still proceed to git-sync
- If there is nothing to commit at all, report that and stop
- Do NOT push if the commit would include `.env`, secrets, or anything in the gitignore. Block and ask
- Do NOT push if pre-commit hooks fail. Fix the cause and create a NEW commit (never `--amend` after a hook failure)

## Output

After all three steps complete, report:

1. Files changed (count + list)
2. Commit hash
3. Push status (pushed / nothing to push / blocked)
4. Worktrees and `worktree-agent-*` branches removed, and anything skipped with the reason
5. One-line summary of what was shipped
