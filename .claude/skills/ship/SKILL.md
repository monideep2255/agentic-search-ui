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

## Step 1b: stray file sweep

Run `git status --porcelain` and account for EVERY untracked path before anything is staged. Each one is either work that belongs in the commit, work that belongs in `.gitignore`, or a leftover to remove. There is no fourth category, and "I did not look" is not one of them.

Where scratch actually lives, because this is the part that gets assumed wrongly in both directions:

- The session scratchpad is OUTSIDE the repository, under the harness's own temp directory. Nothing in it is tracked, nothing in it can be committed, and committing does not touch it. There is no cleanup to do there and no risk to guard against.
- The risk is a file written INSIDE the repository by mistake: a probe script, a measurement dump, a log, an `out.txt`, a half-written report. That one is invisible to the reasoning above and is exactly what this sweep is for.

For each untracked path, say which it is and why, in one clause:

| What it is | What to do |
|---|---|
| Work that belongs in this commit | Stage it by name |
| Output worth keeping but not committing (a large dump, a local measurement) | Add it to `.gitignore`, or move it under a path already ignored |
| A leftover probe, log or temp file | Remove it, and SAY SO in the report rather than removing it silently |
| Something you did not create and cannot classify | Leave it, name it in the report, and ask. Never remove a file whose purpose you do not know |

Removing a leftover follows `file-protection`: inform first, and prefer moving to the Trash over `rm`, so a wrong call is recoverable.

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
- Do NOT push with an unexplained untracked file in the tree. Every path from `git status --porcelain` is classified at Step 1b, or the push waits.
- Do NOT push if pre-commit hooks fail. Fix the cause and create a NEW commit (never `--amend` after a hook failure)

## Output

After all three steps complete, report:

1. Files changed (count + list)
2. Commit hash
3. Push status (pushed / nothing to push / blocked)
4. Every untracked path that was found, and what happened to each: staged, ignored, removed, or left with a question
5. Worktrees and `worktree-agent-*` branches removed, and anything skipped with the reason
6. One-line summary of what was shipped
