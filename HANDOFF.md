# Handoff

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-23.

## Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

## What is live

- Production: release `v0.3.2`'s code (merge `0e277d61`), redeployed from source on 2026-10-22 at the owner's request so it runs on the keys rotated on 2026-10-21; a guest question answered with citations. Nothing else reached production overnight.
- Develop: the overnight run of 2026-10-22 merged the dependency bumps (#290) and cards 141, 143, 138, 131 part 1, 128, 139 notes 1 and 2, 134, and 133 with 137 part 1 (#287 to #300). Deployed, healthy, CI green. Develop now leads production by code, not only by documents.
- Parked as draft pull requests, each with its findings and options written on it: 145 (#293), 130 (#294), 129 (#295), 131 part 2 (#296), 142 (#298), 139 note 3 (#301). Their branches stay on GitHub and locally, with worktrees under `~/s3-worktrees`, until the owner decides.
- No card is being built; the board's one Build in progress row is the owner's harness reviews of 2026-09-25. Overnight spend was about $1.20 of the owner's $8.

## What awaits the product owner

- Retests: the newest rows of `testing/Retest_product_owner.md`, one per card merged overnight, each saying what the team saw on deployed develop.
- The six parked pull requests above: a choice on each, from the options on the pull request.
- Calls named in `DECISIONS.md` rows of 2026-10-22: card 137 part 2 (it changes the accepted rule that keeps a sentence whose uncited ending was stripped), card 128's stacked notes (V-128-07), card 139's silent zero count (V-139-01), and new cards 146 (a mark for retracted papers) and 147 (summaries that open mid-thought).
- A release to production, when wanted, to carry the overnight merges.
- Develop's API has tracing switched on but no tracing key; production has both. Intended or a gap?
- Today, 23 October: card 84's row, a week of the server's lag lines decides the freeze fix.
- Still open from before: the order of the remaining cards; the privacy call on rewriting git history (`DECISIONS.md`, 2026-10-17).

## The one next action

Retest the overnight rows and decide the six parked pull requests, starting with 145 and 129, which belong with card 56's redesign.

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
