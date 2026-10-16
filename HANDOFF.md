# Handoff

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-16.

## Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

## What is live

- Develop: `b15038e3`, deployed and healthy. Production: `v0.2.0`, tag `cde4f592`, unchanged. CI is green.
- Merged 2026-10-16, each behind CI and three independent reviews (one checks the code, one hunts for a wrong answer, a third re-checks with fresh eyes):
  - Overnight: cards 115, 17, 94's timeout fix and 24, each checked on deployed develop at desktop and phone width.
  - Today, cards 75 (#252) and 118 (#253): when the command line cannot tell whether its sign-in was renewed, it asks for `s3 login` once, so nobody is signed out of the web app by surprise.
  - Today, the freeze count (#251, cards 84 and 72): the server logs each moment it falls behind.
- Closed overnight by your rule, each back in To do with its reviews on develop: cards 48, 29, 94's lookup, 110, 101, 20 and 15. Why: `DECISIONS.md`, rows dated 2026-10-15 and 16.
- Nothing is parked. Locally only `develop`; on GitHub only `develop` and `production`.
- Factory is paused; its brief lists card 100. Develop's model settings: `docs/architecture/Model_architecture.md`.

## What awaits the product owner

- Retests: `testing/Retest_product_owner.md`, newest first. The team checked the overnight four on deployed develop; cards 75 and 118 show only when a sign-in renewal fails, so there is nothing to type.
- On 23 October, decide whether the safety check's freeze fix is worth building (card 84's row):
  - Read a week of `event loop lag` lines from develop's log.
  - Each line is a moment the server fell behind: a freeze, a busy server or a host pause, not freezes alone.
- Findings the product check flagged for you to look at: `testing/Developer/reports/2026-10-16_product_check/report.md`.
- Still open from before: a stronger writer model for develop (card 5), and card 40's hook and rule changes.
- Every decision taken for you: `DECISIONS.md`, rows dated 2026-10-15 and 16. What broke: `LEARNINGS.md`.

## The one next action

Retest the night's cards from `testing/Retest_product_owner.md`. After that, the board's To do column top down: each closed card needs a design agreed with you before it is built again, starting with card 101, where a quoted record sentence ends.

How to start a session: read this file, then `git status --short` and `git worktree list`, then `testing/Retest_product_owner.md` and the board's To do column. Overnight, follow `.claude/skills/overnight-development/SKILL.md`. At the end, run `/phase-checkpoint`, then `/ship`.

## Where the facts live

- The board: `testing/UI_fix_plan.md`; build order: `testing/Board_plan.md`
- Retests: `testing/Retest_product_owner.md`
- The cutoff and closed items: `testing/UI_fixes_done.md`; older: `testing/UI_fixes_archive.md`
- Queries to type: `testing/Test_queries_and_workflows.md`
- Each card's reviews: `testing/Developer/reports/<date>_card*`; the night's plan and ledger: `testing/Developer/reports/2026-10-15_overnight/`
- Factory's brief: `docs/build/Factory_onboarding.md`; other work: `testing/Future.md`
- Models: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`; the narrative: `requirements/Plan.md`
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`; releases: `docs/build/Release_flow.md`
- The registry and sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`
