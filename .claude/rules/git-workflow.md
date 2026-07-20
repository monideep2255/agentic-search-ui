---
description: "Git workflow: phase branches, MRs for review, clean commits, gitignored paths"
scope: portable
alwaysApply: true
---

## Git workflow

### Branch model

Work on phase branches, not directly on `main`. One branch per bossman phase.

Branch naming: `phase/N.M-short-description`

- `phase/1.0-fastapi-skeleton`
- `phase/1.1-auth-service`
- `phase/2.0-langgraph-agent-loop`
- `phase/2.1-cypher-tool`
- `phase/3.0-guardrail-node`

Non-phase work uses a type prefix and short description, e.g. `chore/short-description`, `fix/short-description`.

Create the branch at phase start: `git checkout -b phase/N.M-description`

### Merge requests

One MR per phase. Create the MR when the phase is complete and release-workflow passes.

MR flow:
1. Push the phase branch: `git push -u origin phase/N.M-description`
2. Create PR/MR with deliverables checklist from `requirements/Plan.md`
3. User reviews and approves
4. Merge into `main` (no squash, preserve commit history)
5. Delete the phase branch after merge

Do not start the next phase branch until the current MR is merged or the user says to proceed.

### Commit hygiene

Clear, descriptive commit messages in sentence case. No emoji. One logical change per commit.

NEVER add Co-Authored-By lines to commit messages. No co-author trailers of any kind.

Never `git push --force`. Never amend a published commit. Never `git add -A` blindly. Stage specific files.

### Gitignored paths

`node_modules/`, `__pycache__/`, `venv/`, `.env`, `.pytest_cache/`, `frontend/build/` or `frontend/dist/`
