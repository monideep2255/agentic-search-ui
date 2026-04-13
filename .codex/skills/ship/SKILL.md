---
name: ship
description: Sync docs then commit and push to GitHub. Two-step shortcut - runs the docs-sync agent first, then commits and pushes. Use when ending a work block or after a logical milestone.
---

# /ship - sync docs + commit + push

A single ritual to end a work block: bring docs in line with code, commit, push.

## Step 1: docs sync

Use the `docs-sync` sub-agent (`.codex/agents/docs-sync.md`).

Key behaviors:

1. Run `git status --short` to see what changed
2. Use the routing in `docs-sync.md` to identify which docs may need updating
3. Read only affected docs
4. Make surgical edits, not rewrites
5. Report what changed (or "no changes needed")

## Step 2: commit and push

After docs-sync completes:

1. Run `git status` and `git diff --stat` to confirm what's staged
2. Show the user the file list before committing
3. Use a clear, descriptive commit message that explains the why, not just the what
4. NEVER add `Co-Authored-By` lines (project rule, see `.codex/rules/git-workflow.md`)
5. Check current branch:
   - If on a phase branch (`phase/*`): `git push -u origin <branch>` and offer to create MR
   - If on `main`: `git push origin main` (only for merge commits or non-phase work)
6. Report commit hash and push status

## Important

- Always run docs-sync before committing — docs changes may add files to the commit
- If docs-sync says "no changes needed" but there are uncommitted code changes, still proceed
- If there is nothing to commit at all, report that and stop
- Do NOT push if the commit would include `.env`, secrets, or anything in the gitignore — block and ask
- Do NOT push if pre-commit hooks fail — fix the cause and create a NEW commit (never `--amend` after a hook failure)

## Output

After completing both steps, report:

1. Files changed (count + list)
2. Commit hash
3. Push status (pushed / nothing to push / blocked)
4. One-line summary of what was shipped
