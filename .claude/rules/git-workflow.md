---
description: "Git workflow: phase branches, MRs for review, clean commits, gitignored paths"
scope: portable
alwaysApply: true
---

## Git workflow

The core. Full text, with the reasons, the merge-request flow, examples and the scope list: `.claude/rules-reference/git-workflow.md`. Read it before opening or merging a branch.

Branch and pull request:

- Required: build phases (Plan.md Phase 6 onward), anything touching `.claude/`, hooks or settings, and any change the owner asks to see first.
- Not required: planning phases 1 to 5, which may go straight to `develop`.
- Names: `phase/N.M-short-description` for a phase, one branch per bossman phase; a type prefix otherwise, such as `fix/short-description` or `chore/short-description`.
- Merge into `develop` with no squash. Do not start the next phase branch until the current one merges or the user says to proceed.

Steady state, confirmed by the owner on 2026-08-30: locally `develop` and nothing else; on the remote `develop` and `production` and nothing else. After a merge:

1. Merge with branch deletion on. Never pass `--delete-branch=false`.
2. Switch to `develop` and fast-forward.
3. Confirm with `git merge-base --is-ancestor <branch> origin/develop`.
4. Delete with `git branch -d`, never `-D`, and `git push origin --delete <branch>`.

Keeping a branch after merge needs a reason stated at merge time.

Commits:

- Conventional Commits subject: `<type>[optional scope]: <description>`, the description in sentence case. Types: feat, fix, docs, chore, refactor, test, ci, security. A breaking change takes `!` before the colon or a `BREAKING CHANGE:` footer.
- One logical change per commit, no emoji.
- NEVER add Co-Authored-By lines to commit messages. No co-author trailers of any kind. One exception, the owner's of 2026-10-06: commits Factory authors may carry its own `Co-authored-by: factory-droid[bot]` trailer. Every other commit carries none.
- Never `git push --force`. Never amend a published commit. Never `git add -A` blindly. Stage specific files.

Gitignored paths: `node_modules/`, `__pycache__/`, `venv/`, `.env`, `.pytest_cache/`, `frontend/build/` or `frontend/dist/`
