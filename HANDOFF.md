# Handoff

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-16.

## Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

## What is live

- Develop: `de53c6aa`, deployed, `/health` reads develop. Production: `v0.2.0`, tag `cde4f592`, unchanged. CI is green.
- Merged overnight, each behind CI, a judge, an adversary and a fresh verifier: card 115 (#240), card 17 (#241), card 94's timeout fix (#246) and card 24 (#245). All four passed the product check on deployed develop at 1280 and 390 (`testing/Developer/reports/2026-10-16_product_check/` and `2026-10-16_product_check_card24/`).
- Closed overnight by your rule, each back in To do with its reviews and final diff on develop: cards 48, 75, 29, 94's lookup, 110, 101, 20 and 15. Why, one row each: `DECISIONS.md`, 2026-10-16.
- Nothing is parked. Locally only `develop`; on GitHub only `develop` and `production`; no parked tag, no leftover worktree.
- Develop's API sets `SYNTH_MODEL=z-ai/glm-5.2`, `GUARD_MODEL` and `PLAN_MODEL=deepseek/deepseek-v4-flash`, `CLASSIFIER_PROVIDER=jev` and `PER_QUERY_COST_CAP_USD=0.25`. Factory is paused; its brief lists cards 75 and 100.

## What awaits the product owner

- Retests: `testing/Retest_product_owner.md`, newest first, the night's cards 24, 94's timeout fix, 17 and 115 on top. The team checked all four on deployed develop.
- Two rules only you can set: whether a question after a long server pause is checked like any other (cards 84 and 72, step 3b, `testing/Developer/reports/2026-10-15_card84_72/design.md`), and what a failed sign-in renewal does (card 75).
- The product check's "needs your eye" findings, PR-1016-01 to 05 (`testing/Developer/reports/2026-10-16_product_check/report.md`).
- Still open from before: whether develop's writer becomes Opus 5.5 (card 5), card 40's 27 items. Every decision taken for you overnight: `DECISIONS.md`, rows dated 2026-10-15 and 16; what broke: `LEARNINGS.md`.

## The one next action

Retest the night's four cards from `testing/Retest_product_owner.md`, then answer the two rules above. After that, the board's To do column top down: each closed card needs a design agreed with you before it is built again, starting with card 101, where a quoted record sentence ends.

How to start a session: read this file, then `git status --short` and `git worktree list`, then `testing/Retest_product_owner.md` and the board's To do column. Overnight, follow `.claude/skills/overnight-development/SKILL.md`. At the end, run `/phase-checkpoint`, then `/ship`.

## Where the facts live

- The board: `testing/UI_fix_plan.md`; build order: `testing/Board_plan.md`
- Retests: `testing/Retest_product_owner.md`
- The cutoff and closed items: `testing/UI_fixes_done.md`; older: `testing/UI_fixes_archive.md`
- Queries to type: `testing/Test_queries_and_workflows.md`
- Each card's reviews: `testing/Developer/reports/<date>_card*`; the night's plan and ledger: `2026-10-15_overnight/`
- Factory's brief: `docs/build/Factory_onboarding.md`; other work: `testing/Future.md`
- Models: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`; the narrative: `requirements/Plan.md`
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`; releases: `docs/build/Release_flow.md`
- The registry and sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`
