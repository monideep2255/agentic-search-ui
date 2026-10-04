# Handoff

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-04.

## Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

## What is live

- Develop's product code: card 73's merge, #139 at ca85a03d. `git log --merges --first-parent develop` lists what came before.
- Golden run floor for the next answer-path change: 101 of 150 (`DECISIONS.md`, 2026-09-29). Card 63's accepted run answered 98.
- Develop's API carries `CLASSIFIER_PROVIDER=jev` and `SYSTEM_DAILY_CAP_USD=25`. Both Railway services redeploy on every push to `develop`.
- Production: `v0.2.0`, tag `cde4f59`, released 2026-09-20. Nothing since is on it. Card 65 fixes the release fix's open findings first.
- `/ship` runs the public-repository leak scan before every push. Open items: `testing/Developer/reports/2026-09-29_ship_leak_scan/verifier.md`.
- The lead merges into develop with `gh pr merge --merge --admin --delete-branch` once checks pass (`DECISIONS.md`, 2026-09-29).
- Test sign-ins are fresh accounts made on develop, kept only in the lead's scratch folder (`LEARNINGS.md`, 2026-09-29).
- Nothing is built between sessions. Check `gh run list --branch develop --limit 3` before trusting CI.

Parked branches, all on GitHub. Pick one up with `git worktree add .claude/worktrees/<name> <branch>`; the full table is in the history file, 2026-09-30.

- `fix/card72-r10-guardrail` and `fix/card84-r10-sound-parts`: stopped by the owner; return only as an agreed design.
- `feat/8.7-s1`, `feat/8.7-s2`, `feat/8.7-s3`: phase 8.7's three builders, unmerged. Plan in `tracker/phase_8.7.md`.

## What awaits the product owner

- Approve, through the permission system, making the leak scan's email findings warnings rather than blocks (`DECISIONS.md`, 2026-09-30).
- The privacy pre-commit and commit-msg hooks on the second laptop. Until then, check every commit there by hand.
- `railway link` on the second laptop, choosing `system3-search-agent-develop`.
- Three cards in the Retest column after the 2026-09-29 batch retest (`testing/Developer/reports/2026-09-29_retest/`).

## The one next action

The owner picks the next piece from the top of To do: cards 86 to 94, each needing a diagnosis first. Phase 8.7 stays parked. One piece at a time, carried to done (`DECISIONS.md`, 2026-09-29).

How to start a session: read this file, then `git status --short` and `git worktree list` (expect `develop` alone locally), then the board's Retest and To do columns. At the end, run `/phase-checkpoint`, then `/ship`. A new laptop starts with the setup steps in `docs/build/Handoff_history.md`.

## Where the facts live

- The board, every card: `testing/UI_fix_plan.md`
- The cutoff and every closed item: `testing/UI_fixes_done.md`, from "Where we stopped"
- Queries to type and what a person sees: `testing/Test_queries_and_workflows.md`
- A numbered phase's tickets and findings: `tracker/phase_N.M.md`
- Work outside the board: `testing/Future.md`
- Models and how calls hand off: `docs/architecture/Model_architecture.md`
- The golden run: `.claude/skills/bossman-mode/reference/Product_review.md`, Step 2
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`
- The dated narrative: `requirements/Plan.md`, Revision history
- How a phase or card runs: `.claude/skills/bossman-mode/SKILL.md`
- Releases: `docs/build/Release_flow.md`
- The living-documents registry: `tracker/Living_documents.md`
