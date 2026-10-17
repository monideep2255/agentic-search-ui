# Handoff

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-17.

## Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

## What is live

- Develop: `cf9be15d` is the product; documents since then only. Deployed and healthy. Production: `v0.2.0`, tag `cde4f592`, unchanged. CI is green.
- Merged overnight 2026-10-16 to 17, each behind CI, its reviews and a fresh verifier, then checked on deployed develop at desktop and phone width:
  - Card 30, step 1 (#261): a gene's variant list says it is not a list of pathogenic variants.
  - Card 37, slice A1 (#262): rs334 is named by its id, with its gene and significance.
  - Card 8 (#266): the line under an answer names the databases it rests on.
  - Card 38, slices B (#265) and C (#267): orthologs show their species; graph papers show their titles.
  - Card 105 (#268): a picked "How far back" window leaves out the graph's undated papers.
- Closed by your rule, back in To do with their reviews: card 18, card 37's slice A2 and card 30's step 2b. Three more (8, 105, 38 C) closed once and were rebuilt and merged. Why: `DECISIONS.md`, rows dated 2026-10-16 and 17.
- A usage limit stopped the session from 01:40 to 11:32, so the 07:00 close ran late (`LEARNINGS.md`, 2026-10-17).
- Nothing is parked. Locally only `develop`; on GitHub only `develop` and `production`.

## What awaits the product owner

- Retests: the night's rows at the top of `testing/Retest_product_owner.md`, each checked by the team on deployed develop.
- Two calls on card 8's row: MedGen counted under "other databases" when databases tie, and the rare case where two databases disagree.
- One security call on card 38 slice C's row: whether every paper title path, live ones included, gets a stricter cleaning.
- Designs: cards 18 and 37 (slice A2) now say "Design with you first"; card 30's step 2b says what its next attempt needs.
- New cards from the night's checks, 119 to 124, at the bottom of To do.
- On 23 October, card 84's row: the night's checks saw two more safety-check timeouts on develop.
- Every decision taken for you: `DECISIONS.md`, rows dated 2026-10-16 and 17. What broke: `LEARNINGS.md`.

## The one next action

Retest the night's cards from the top of `testing/Retest_product_owner.md`, then choose the first "Design with you first" card on the board to design together.

How to start a session: read this file, then `git status --short` and `git worktree list`, then `testing/Retest_product_owner.md` and the board's To do column. Overnight, follow `.claude/skills/overnight-development/SKILL.md`. At the end, run `/phase-checkpoint`, then `/ship`.

## Where the facts live

- The board: `testing/UI_fix_plan.md`; build order: `testing/Board_plan.md`
- Retests: `testing/Retest_product_owner.md`
- The cutoff and closed items: `testing/UI_fixes_done.md`; older: `testing/UI_fixes_archive.md`
- Queries to type: `testing/Test_queries_and_workflows.md`
- Each card's reviews: `testing/Developer/reports/<date>_card*`; the night's plan and ledger: `testing/Developer/reports/2026-10-16_overnight/`
- Factory's brief: `docs/build/Factory_onboarding.md`; other work: `testing/Future.md`
- Models: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`; the narrative: `requirements/Plan.md`
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`; releases: `docs/build/Release_flow.md`
- The registry and sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`
