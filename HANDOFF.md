# Handoff

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-15.

## Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

## What is live

- Develop: `f3950564`, deployed and checked at 1280 and 390 (`testing/Developer/reports/2026-10-15_product_check/`). Production: `v0.2.0`, tag `cde4f592`. CI is green on develop again.
- Merged 2026-10-15: card 114 (#233, develop's writer priced again, strawberry-graphql 0.327.7), card 35 (#228, merged with V2-35-02 open as card 115) and card 111 (#234, re-split alone).
- Develop's API sets `SYNTH_MODEL=z-ai/glm-5.2`, `GUARD_MODEL` and `PLAN_MODEL=deepseek/deepseek-v4-flash`, `CLASSIFIER_PROVIDER=jev` and `PER_QUERY_COST_CAP_USD=0.25`. litellm's downloaded price map lacks OpenRouter entries today, so prices come from `harness/tiers.py`'s table.
- GitHub also holds open pull requests #230 (card 48, waiting for its redesign) and #223 (skill lessons), and two parked branches: `fix/cards110-111-summary-opening` (card 110) and `fix/card20-isolate-year-place`.
- Locally, besides `develop`: worktrees `~/asu-wt/card48` and `skill` for those pull requests; on the Desktop `asu-card22`, `asu-card56` and `asu-factory-43`, `-43b`, `-44`, `-47`, none removable by the clean-up checks; local branch `fix/card20-isolate-year-place`.

## What awaits the product owner

- Retests: `testing/Retest_product_owner.md`, newest first, today's cards 114, 35 and 111 on top.
- The product check's findings marked "needs your eye": `testing/Developer/reports/2026-10-15_product_check/product_review.md`.
- Still open from before: the guardrail's step 3b, whether develop's writer becomes Opus 5.5 (card 5), card 40's 27 items, pull request #223. Every decision of today: `DECISIONS.md`, rows dated 2026-10-15; what broke: `LEARNINGS.md`.

## The one next action

Build card 94's single-isolate lookup with the SNP-distance scan skipped, your call of 2026-10-15: it is the first card in the board's To do that waits on no design. Its timeout crash and empty-result wording come first (`testing/Developer/reports/2026-10-09_card94/build.md`, "Parked"). Your other calls of today, cards 48, 20, 17 and 115, follow in the board's order.

How to start a session: read this file, then `git status --short` and `git worktree list`, then `testing/Retest_product_owner.md` and the board's To do column. Overnight, follow `.claude/skills/overnight-development/SKILL.md`. At the end, run `/phase-checkpoint`, then `/ship`.

## Where the facts live

- The board: `testing/UI_fix_plan.md`; build order: `testing/Board_plan.md`
- Retests: `testing/Retest_product_owner.md`
- The cutoff and closed items: `testing/UI_fixes_done.md`; older: `testing/UI_fixes_archive.md`
- Queries to type: `testing/Test_queries_and_workflows.md`
- Each card's reviews: `testing/Developer/reports/<date>_card*`; today's: `2026-10-15_*`
- Factory's brief: `docs/build/Factory_onboarding.md`; other work: `testing/Future.md`
- Models: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`; the narrative: `requirements/Plan.md`
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`; releases: `docs/build/Release_flow.md`
- The registry and sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`
