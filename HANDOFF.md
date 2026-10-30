# Handoff

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-30.

## Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

## What is live

- Production: release `v0.3.2`'s code (merge `0e277d61`). No release since; the overnight work of 2026-10-22 and 2026-10-29 to 30 is on develop only.
- Develop: merge `abea730d` (#320) and the documents since. Develop has no tracing, by design.
- Overnight 2026-10-29 to 30, nine pull requests merged under the owner's approval before sleep (`DECISIONS.md`, 2026-10-29), each checked on deployed develop: #310 to #317 and #320.
- CI passes every gate. Gate 6 still accepts the 13 filelock advisories until litellm accepts filelock 4.
- Pull requests open, all drafts: #301 (card 139's note 3, to rework), #318 (card 146, parked for two owner calls), #319 (card 152, parked for a search design).
- Branches: locally `develop` and those three; on GitHub `develop`, `production` and those three.
- Nothing is being built.

## What awaits the product owner

- Retests: rows 1 to 9 of `testing/Retest_product_owner.md`, the overnight merges, each with the team's check on develop.
- Calls, each with the lead's recommendation in the board row and report it names:
  - Card 147, summaries that open mid-thought: build the classifier veto, or a cheaper option.
  - Card 84, step 3b: recommended not to build it (the longest lag in a week was 0.40 s).
  - Card 122, which papers a gene answer lists.
  - Card 124, the GeneReviews chapter under a window.
  - Card 136 part 2, guest searches after sign-in.
  - Card 146 (#318): the text prefix against rule 5, and code enforcement.
  - Card 152 (#319): the search design trade-off.

## The one next action

The owner's retests and the calls above. Then the board's To do column in order, starting with the cards the team can build (`testing/UI_fix_plan.md`).

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
- The overnight run's reviews and product checks: `testing/Developer/reports/2026-10-29_*` and `2026-10-30_*`
- Releases: `docs/build/Release_flow.md`; the changelog: `CHANGELOG.md`
- Factory's brief: `docs/build/Factory_onboarding.md`; other work: `testing/Future.md`
- Models: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`; the narrative: `requirements/Plan.md`
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`
- The registry and sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`
