# Handoff

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-25.

## Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

## What is live

- Production: release `v0.3.2`'s code (merge `0e277d61`) on the keys rotated on 2026-10-21. By the owner's call of 2026-10-25 there is no release of the overnight work: it stays on develop only.
- Develop: the overnight merges of 2026-10-22 (#287 to #300) and the documents since. Deployed and healthy. Develop has no tracing, by design.
- CI: the frontend and Python audit gates are red on every pull request, from new advisories for `fast-uri`, `undici` and `filelock`. The owner approved one dependency pull request on 2026-10-25 (fast-uri 3.1.9 and undici 7.30.1 in the frontend lockfile, filelock 4.2.1 pinned after a check that huggingface_hub accepts it); it is not built yet.
- Pull requests: card 139's note 3 (#301, draft) stays open for rework. The five other overnight drafts were closed on 2026-10-25 and their branches removed; each is restorable from its closed pull request.
- Locally only `develop` and #301's branch, with its worktree in `~/s3-worktrees/card139b`. On GitHub `develop`, `production` and #301's branch.
- Nothing is being built.

## What awaits the product owner

- Retests: the newest rows of `testing/Retest_product_owner.md`, one per card merged on 2026-10-22.
- Nothing else is waiting on a decision: the owner's calls of 2026-10-25 are rows in `DECISIONS.md`, and the board's To do column carries each card's next move.

## The one next action

Build the approved dependency pull request first, since CI stays red until it lands. Then diagnose card 147 (summaries that open mid-thought) and read card 84's guard lag lines, both by the owner's calls of 2026-10-25, then the board's To do column in order.

How to start a session: read this file, then `git status --short` and `git worktree list`, then `testing/Retest_product_owner.md` and the board's To do column. Overnight, follow `.claude/skills/overnight-development/SKILL.md`. At the end, run `/phase-checkpoint`, then `/ship`.

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
