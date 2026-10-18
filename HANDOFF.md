# Handoff

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-17.

## Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

## What is live

- Develop: `6935a0a3` is the product (card 125, #271); documents since then only. Deployed and healthy. Production: `v0.2.0`, tag `cde4f592`, unchanged. CI is green.
- Merged today, behind CI, a judge and an adversary, then checked on deployed develop at 1280 and 390: card 125, no paper's title or abstract can pose as the answer writer's instructions, and records read exactly as PubMed writes them. Its third attempt; three small items merged open by your call (`testing/Future.md`, row 61).
- Closed today, never pushed, each back in To do as "Design with you first": card 126 (the disagreement line fired where nothing disagreed) and card 56's first slice (a single NCBI fit trusted for an acronym, "HEV" read as a pig virus). Why: `DECISIONS.md`, rows dated 2026-10-17.
- Nothing is parked. Locally only `develop`; on GitHub only `develop` and `production`.

## What awaits the product owner

- Retests: the rows at the top of `testing/Retest_product_owner.md`, card 125 first, then the night of 16 to 17 October; each checked by the team on deployed develop.
- The poster release: four calls for you in the plan above, each asked on its own tomorrow.
- After the event, privacy: whether to rewrite git history to drop two private symlink targets (`DECISIONS.md`, 2026-10-17); the current tree is clean.
- Designs, after the event: card 56's next slice (the design and the first slice's reviews: `testing/Developer/reports/2026-10-17_card56/`), card 126, and the other "Design with you first" cards on the board.
- New cards: 127 (a remembered organism never reaches its sequencing records) and 128 (a CFTR answer with no summary and no note), both buildable.
- On 23 October, card 84's row: a week of the server's lag lines decides the freeze fix.
- Every decision taken today: `DECISIONS.md`, rows dated 2026-10-17. What broke: `LEARNINGS.md`.

## The one next action

Tomorrow, Sunday 18 October, is a freeze-and-release day for the innovation day poster, by your call: no new features; retest the top rows of `testing/Retest_product_owner.md`, answer the four release calls, then release develop to production and verify the demo questions there. The plan, step by step: `testing/Developer/reports/2026-10-17_poster_release/plan.md`.

How to start a session: read this file, then `git status --short` and `git worktree list`, then `testing/Retest_product_owner.md` and the board's To do column. Overnight, follow `.claude/skills/overnight-development/SKILL.md`. At the end, run `/phase-checkpoint`, then `/ship`.

## Where the facts live

- The board: `testing/UI_fix_plan.md`; build order: `testing/Board_plan.md`
- Retests: `testing/Retest_product_owner.md`
- The cutoff and closed items: `testing/UI_fixes_done.md`; older: `testing/UI_fixes_archive.md`
- Queries to type: `testing/Test_queries_and_workflows.md`
- Each card's reviews: `testing/Developer/reports/<date>_card*`; today's: `testing/Developer/reports/2026-10-17_card56/`, `_card125/`, `_card126/`
- Factory's brief: `docs/build/Factory_onboarding.md`; other work: `testing/Future.md`
- Models: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`; the narrative: `requirements/Plan.md`
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`; releases: `docs/build/Release_flow.md`
- The registry and sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`
