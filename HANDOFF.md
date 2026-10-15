# Handoff

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-09.

## Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

## What is live

- Develop: `a2bb7732`. Production: `v0.2.0`, tag `cde4f592`.
- Merged 2026-10-09, each behind green CI, a judge, an adversary, one fix round and a fresh verifier, then checked on deployed develop at 1280 and 390: phase 8.7 (#218) and its follow-ups (#229), the guardrail's safe part (#227), cards 19 (#224), 109 (#225), 94 part (#226) and 112 (#231). The checks: `testing/Developer/reports/2026-10-09_product_check_*`.
- Develop's API has `PER_QUERY_COST_CAP_USD=0.25`. OpenRouter: $31.36 left; tonight spent $0.41.
- A command line installed from develop since the evening of 2026-10-08 prints a "redefined" warning per cited record until reinstalled; production's is unaffected.
- GitHub also holds open pull requests #223 (overnight skill lessons), #228 (card 35) and #230 (card 48), and the parked branch `fix/card20-isolate-year-place`.
- Locally, besides `develop`: worktrees `~/asu-wt/card35`, `card48` and `skill` for those pull requests; on the Desktop `asu-card22` (raw review files), `asu-card56` (5 unmerged commits), and `asu-factory-43`, `-43b`, `-44`, `-47` (uncommitted changes from a damaged index, `-43` still partly evicted), none removable by the clean-up checks; local branch `fix/card20-isolate-year-place`.

## What awaits the product owner

- Card 35, #228: merge as it is, or a one-line change and a fresh verifier (V-35-03).
- Card 48, #230: redesign so the classifier judges whether a message names a record (the lead's recommendation), or merge as it is (V-48-04).
- Card 20: a separate extraction call on isolate questions (recommended), or Think extracting with the listed fixes.
- Card 94's single-isolate lookup: keep or trim the 19 s SNP scan (F-3.5-A-05). Card 17: accept two dropped sentences, or another option.
- The guardrail's step 3b; whether develop's writer becomes Opus 5.5 (card 5); card 40's 27 items; pull request #223.
- Retests: "Waiting for your retest" in `testing/UI_fixes_done.md`. Every decision taken for you tonight: `DECISIONS.md`, rows dated 2026-10-09; what broke: `LEARNINGS.md`.

## The one next action

Decide #228 and #230, then build cards 110 and 111, the first-sentence pick and the sentence made only of record titles, from `testing/Developer/reports/2026-10-09_product_check_8.7/diagnosis.md`.

How to start a session: read this file, then `git status --short` and `git worktree list`, then "Waiting for your retest" and the board's To do column. Overnight, follow `.claude/skills/overnight-development/SKILL.md`. At the end, run `/phase-checkpoint`, then `/ship`.

## Where the facts live

- The board: `testing/UI_fix_plan.md`; build order: `testing/Board_plan.md`
- Retests, the cutoff, closed items: `testing/UI_fixes_done.md`; older: `testing/UI_fixes_archive.md`
- Queries to type: `testing/Test_queries_and_workflows.md`
- Phase 8.7: `tracker/phase_8.7.md`; each card's reviews: `testing/Developer/reports/2026-10-09_card*`
- Factory's brief: `docs/build/Factory_onboarding.md`; other work: `testing/Future.md`
- Models: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`; the narrative: `requirements/Plan.md`
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`; releases: `docs/build/Release_flow.md`
- The registry and sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`
