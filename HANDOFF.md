# Handoff

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-18.

## Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

## What is live

- Production: `v0.3.2`, merge `0e277d61`, released 2026-10-18 for the innovation day poster: the day's release plus the disclaimer's phone fix (#282). Healthy; its settings match develop's, and its crowd limits stay at 1000 guest runs and $25 a day (`DECISIONS.md`, 2026-10-18).
- Develop: the same code as production; it leads by documents only, by the owner's call, until the next release. Deployed and healthy. CI is green.
- Each release's changelog reaches production by a changelog-only pull request after its back-merge, until the release job is fixed (`testing/Future.md`, row 64).
- Nothing is being built. Locally only `develop`; on GitHub only `develop` and `production`.
- The poster's QR code is on the owner's machine, not in the repository; it encodes the production web address, so no release changes it.

## What awaits the product owner

- Retests: the rows in `testing/Retest_product_owner.md`, newest first. Row 1 is the disclaimer on a phone; every other row has the lead's browser verdict in `testing/Developer/reports/2026-10-18_browser_retest/report.md`.
- After the poster event: the order of cards 129 to 145; the privacy call on rewriting git history (`DECISIONS.md`, 2026-10-17).
- Designs, after the event: card 56's next slice, card 126 and the other "Design with you first" cards.
- On 23 October, card 84's row: a week of the server's lag lines decides the freeze fix.

## The one next action

The poster event. Afterwards the owner orders cards 129 to 145 and building resumes, starting from the board's To do column.

How to start a session: read this file, then `git status --short` and `git worktree list`, then `testing/Retest_product_owner.md` and the board's To do column. Overnight, follow `.claude/skills/overnight-development/SKILL.md`. At the end, run `/phase-checkpoint`, then `/ship`.

## Where the facts live

- The board: `testing/UI_fix_plan.md`; build order: `testing/Board_plan.md`
- Retests: `testing/Retest_product_owner.md`
- The cutoff and closed items: `testing/UI_fixes_done.md`; older: `testing/UI_fixes_archive.md`
- Queries to type: `testing/Test_queries_and_workflows.md`
- Each card's reviews: `testing/Developer/reports/<date>_card*`; the release day: `testing/Developer/reports/2026-10-18_browser_retest/`, `2026-10-17_poster_release/`
- Releases: `docs/build/Release_flow.md`; the changelog: `CHANGELOG.md`
- Factory's brief: `docs/build/Factory_onboarding.md`; other work: `testing/Future.md`
- Models: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`; the narrative: `requirements/Plan.md`
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`
- The registry and sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`
