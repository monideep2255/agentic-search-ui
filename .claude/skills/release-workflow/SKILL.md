---
name: release-workflow
description: End-to-end release workflow for a pipeline change. Chains qa-gate then ship. No Railway, no deploy step - this repo lands files on disk.
depends_on:
  - .claude/skills/qa-gate/SKILL.md
  - .claude/skills/ship/SKILL.md
  - .claude/skills/best-practices/SKILL.md
  - .claude/rules/git-workflow.md
depended_by:
  - CLAUDE.md
---

# Release workflow

What "release" means in this repo:

- A pipeline change has been written, tested, and is ready to land on `main`.
- KGX output (if any) has been regenerated and validated locally.
- Docs and `DECISIONS.md` are in sync.

There is no remote deploy. Postgres + AGE is local. The "release" is a clean commit on `main` and (optionally) a push to GitHub.

Adapted from the reference NCBI KG `release-workflow` by stripping Railway, `phase-complete`, and the deployed-feature-branch model.

## Pre-flight

1. `git status` is clean except for the change you intend to ship. If there is unrelated drift, stash or commit it separately first.
2. The venv is active (`which python`).
3. Postgres is running, `ncbi_kg` exists, and `CREATE EXTENSION age` is in effect.

## Step 1: local verification

Re-run the affected pipeline end to end on a small slice. For Phase 1 work this means: download a tiny subset (one chromosome of `gene_info`, a hundred ClinVar records, a slice of MedGen), run all 5 ETL steps, check the row counts in the output KGX files.

The point is not to re-run the full bulk job. The point is to prove the code path works on real data, not just unit tests.

If you cannot run a small slice locally without errors, you have not finished the work.

## Step 2: QA gate

Invoke `.claude/skills/qa-gate/SKILL.md` end to end. All six phases. Stop at the first failure.

## Step 3: ship

Invoke `.claude/skills/ship/SKILL.md`:

1. Run `docs-sync` if any docstring, schema, or pipeline shape changed.
2. `git add` only the files you intend to ship (no `git add -A`).
3. `git commit` with a short, sentence-case message describing the why, not the what. **Never** add `Co-Authored-By` lines.
4. Optionally `git push origin main`. Push only when the user has asked for it.

## Step 4: post-release sanity

After the commit:

1. `git log -1 --stat` and confirm only the intended files are in the commit.
2. If you ran a slice job in step 1, the output files in `data/kgx/<database>/` are still there. They are gitignored. Note the row counts in your chat reply so the user can spot regressions session-over-session.
3. If a `DECISIONS.md` row was added, mention it in the chat reply too.

## What this skill does NOT do

- Does not push to a remote unless explicitly told. Local commit is the default.
- Does not tag releases. There are no semver releases in this repo.
- Does not bump versions. There is no published package.
- Does not run a smoke deploy. There is nothing deployed.
- Does not chain into a "phase complete" workflow. Phase tracking lives in `CLAUDE.md` and is updated by hand.
