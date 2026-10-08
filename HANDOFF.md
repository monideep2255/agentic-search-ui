# Handoff

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-08.

## Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

## What is live

- Develop: `29d8d8a0`, the merge of #208. Both Railway services redeploy on every push to `develop`; check `gh run list --branch develop --limit 3` before trusting CI.
- Production: `v0.2.0`, tag `cde4f592`. The changelog fix, `testing/Future.md` row 53, lands before the next release.
- Merged on the night of 2026-10-07 to 08, each behind CI and a fresh verifier finding nothing worse than develop, then its test queries on develop at 1280 and 390: cards 71 part (#203), 54 (#202), 101 part (#204), 103 and 104 (#205), 67 (#207, no live check possible), 59 (#208), and the overnight-development skill (#206). How each was reviewed: the done file's session table.
- Not done that night: card 54's warning line for older answers, reverted for false alarms; card 67's dated first version, redone; the golden run, at the owner's choice.
- The data engineering repository is released as `v1.1.0` (#19 to #21); its production merges used the owner's admin bypass, approved in the chat.
- GitHub holds `develop`, `production` and phase 8.7's four branches (`feat/8.7-s1` to `s3`, `phase/8.7-answers-sooner`), which wait on the OpenRouter top-up.
- Locally, besides `develop`: nine old worktrees on merged branches that could not be checked for untracked work, because iCloud evicted their files (`LEARNINGS.md`, 2026-10-08): `asu-audit`, `asu-card22`, `asu-card56`, `asu-card56-r3`, `asu-card99`, `asu-factory-43`, `asu-factory-43b`, `asu-factory-44`, `asu-factory-47`. Their local branches go with them.
- Factory did no work on 2026-10-08; its next cards stay 75, 24 and 100 (`docs/build/Factory_onboarding.md`).

## What awaits the product owner

- Retests: "Waiting for your retest" in `testing/UI_fixes_done.md`, newest first, cards 59, 67, 103 and 104, 101 part, 54 and 71 part on top.
- The guardrail design's seven yes or no questions: `testing/Developer/reports/2026-10-08_guardrail_design/design.md`.
- The "High-risk claim" tag on a reopened answer (card 71): approved, a migration built in a daytime session with you present.
- Card 40: the itemized hook and always-loaded rule changes, now with one git-workflow line (tags count, every session end, both repositories).
- The decisions taken for you overnight: `DECISIONS.md`, rows dated 2026-10-08.
- The nine evicted worktrees above: once iCloud restores them, the lead checks each and removes what clears all three checks.
- From before: decisions D5 to D21 in `testing/Board_plan.md`, the OpenRouter top-up, the privacy hooks and `railway link` on the second laptop.

## The one next action

Read the night's loose ends in `testing/UI_fixes_done.md` ("Where we stopped"), then build from the board's To do column top down: card 94's remaining isolate work next, since card 56 waits on a design with you.

How to start a session: read this file, then `git status --short` and `git worktree list`, then "Waiting for your retest" and the board's To do column. Overnight, follow `.claude/skills/overnight-development/SKILL.md`. At the end, run `/phase-checkpoint`, then `/ship`.

## Where the facts live

- The board, every card: `testing/UI_fix_plan.md`
- The build order and progress: `testing/Board_plan.md`
- Retests, the cutoff and every closed item: `testing/UI_fixes_done.md`; older history in `testing/UI_fixes_archive.md`
- Queries to type and what a person sees: `testing/Test_queries_and_workflows.md`
- Factory's brief: `docs/build/Factory_onboarding.md`
- Work outside the board: `testing/Future.md`
- A numbered phase's tickets and findings: `tracker/phase_N.M.md`
- Models and how calls hand off: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`
- The dated narrative: `requirements/Plan.md`, Revision history
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`
- Releases: `docs/build/Release_flow.md`
- The living-documents registry and the sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`
