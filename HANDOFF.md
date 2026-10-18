# Handoff

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-18.

## Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

## What is live

- Production: `v0.3.0`, merge `59aba7d8`, released 2026-10-18 for the innovation day poster. Deployed by hand from source because the merge triggered no Railway deploy (`LEARNINGS.md`, 2026-10-18); migrations at 0011; healthy.
- Production's settings match develop's, and its crowd limits are raised for the event: 1000 guest runs and $25 a day (`DECISIONS.md`, 2026-10-18).
- Develop: the same code as production, plus documents only; the changelog's v0.3.0 section arrived by back-merge #277. Deployed and healthy. CI is green.
- Nothing is being built. Locally only `develop`; on GitHub only `develop` and `production`.

## What awaits the product owner

- Retests: the rows in `testing/Retest_product_owner.md`. Every row was driven by hand in a browser on develop on 2026-10-18, with a verdict and a take each: `testing/Developer/reports/2026-10-18_browser_retest/report.md` (its recordings are local only, in that folder).
- After the event: set production's crowd limits back to 200 guest runs and $10 a day; the privacy call on rewriting git history (`DECISIONS.md`, 2026-10-17).
- The findings of that retest and of the production check, filed as board cards 129 to 145, to order with the owner after the event.
- Designs, after the event: card 56's next slice, card 126 and the other "Design with you first" cards.
- On 23 October, card 84's row: a week of the server's lag lines decides the freeze fix.

## The one next action

The poster event: the QR code opens `https://search-agent-web-production.up.railway.app`, and the owner checks it from a phone. Demo questions checked on production, five runs each, are in the report's "Production check"; keep the bronchiolitis question and the breast cancer gene count off the poster. After the event, the owner orders cards 129 to 145, then building resumes.

How to start a session: read this file, then `git status --short` and `git worktree list`, then `testing/Retest_product_owner.md` and the board's To do column. Overnight, follow `.claude/skills/overnight-development/SKILL.md`. At the end, run `/phase-checkpoint`, then `/ship`.

## Where the facts live

- The board: `testing/UI_fix_plan.md`; build order: `testing/Board_plan.md`
- Retests: `testing/Retest_product_owner.md`
- The cutoff and closed items: `testing/UI_fixes_done.md`; older: `testing/UI_fixes_archive.md`
- Queries to type: `testing/Test_queries_and_workflows.md`
- Each card's reviews: `testing/Developer/reports/<date>_card*`; today's retest and release: `testing/Developer/reports/2026-10-18_browser_retest/`, `2026-10-17_poster_release/`
- Releases: `docs/build/Release_flow.md`; the changelog: `CHANGELOG.md`
- Factory's brief: `docs/build/Factory_onboarding.md`; other work: `testing/Future.md`
- Models: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`; the narrative: `requirements/Plan.md`
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`
- The registry and sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`
