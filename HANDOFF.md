# Handoff

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-29.

## Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

## What is live

- Production: release `v0.3.2`'s code (merge `0e277d61`). By the owner's call of 2026-10-25 there's no release of the overnight work of 2026-10-22: it stays on develop only.
- Develop: merge `049240d0` (#307) and the documents since. Develop has no tracing, by design.
- CI: every gate passes again since #308:
  - fast-uri 3.1.9 and undici 7.30.1 are in the frontend lockfile.
  - Gate 6 accepts the 13 filelock advisories by ID, by the owner's yes of 2026-10-29, until litellm accepts filelock 4. That day filelock is pinned and the list deleted (`.github/gates/gate06_python_audit.sh`).
- Vespa isn't pursued (owner, 2026-10-29). Card 148 closed unbuilt. Its notes and the parked plan stay local in `docs/retrieval-engine-discussion/`, which is gitignored.
- Pull requests: only #301, card 139's note 3, a draft kept for rework.
- Branches:
  - Locally: `develop` and #301's branch, with its worktree in `~/s3-worktrees/card139b`.
  - On GitHub: `develop`, `production` and #301's branch.
- Nothing is being built.

## What awaits the product owner

- Retests: the newest rows of `testing/Retest_product_owner.md`, one per card merged on 2026-10-22.
- No decision is waiting: the owner's calls are rows in `DECISIONS.md`, and the board's To do column carries each card's next move.

## The one next action

Diagnose card 147 (summaries that open mid-thought), then read card 84's guard lag lines. Both are the owner's calls of 2026-10-25. Then work the board's To do column in order. Card 84 needs Railway logs: the Railway connector needs the owner to sign in, or use the `railway` command-line tool.

How to start a session:

1. Read this file.
2. Run `git status --short` and `git worktree list`.
3. Read `testing/Retest_product_owner.md` and the board's To do column.

Overnight, follow `.claude/skills/overnight-development/SKILL.md`. At the end, run `/phase-checkpoint`, then `/ship`.

## Where the facts live

- The board: `testing/UI_fix_plan.md`; build order: `testing/Board_plan.md`
- Retests: `testing/Retest_product_owner.md`
- The cutoff and closed items: `testing/UI_fixes_done.md`; older: `testing/UI_fixes_archive.md`
- Queries to type: `testing/Test_queries_and_workflows.md`
- The overnight run's reviews and product checks: `testing/Developer/reports/2026-10-22_*`
- Releases: `docs/build/Release_flow.md`; the changelog: `CHANGELOG.md`
- Factory's brief: `docs/build/Factory_onboarding.md`; other work: `testing/Future.md`
- Models: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`; the narrative: `requirements/Plan.md`
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`
- The registry and sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`
