# Handoff

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-09.

## Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

## What is live

- Develop: `599c6e67`. Production: `v0.2.0`, tag `cde4f592`.
- Merged overnight 2026-10-08 to 09, each behind green CI, a judge, an adversary, one fix round and a fresh verifier, then checked on deployed develop at 1280 and 390: cards 71 (#212, with migration 0011), 32 (#214), 36 (#215), 37 (#213, its fix round's case change reverted), 85 (#220) and 51 (#219, its fix round's rewording reverted). The checks: `testing/Developer/reports/2026-10-09_product_check_*`.
- Parked, code under local `parked/` tags, reports kept: the guardrail (84 and 72), card 15's next step, card 101's last slices. Why: the `DECISIONS.md` rows of 2026-10-08.
- OpenRouter: $31.77 left of $36.11; phase 8.7 spent $3.67 of its $20, everything else about $0.66.
- GitHub also holds `phase/8.7-answers-sooner` (open pull request #218) and `feat/8.7-s1` to `s3`, whose work it carries.
- Locally, besides `develop`: worktrees `asu-card22` (raw review files not on develop) and `asu-card56`, `asu-factory-43`, `-43b`, `-44`, `-47` (still downloading from iCloud, unchecked). `asu-audit` and `asu-card99` were checked and removed.

## What awaits the product owner

- Phase 8.7, pull request #218: merge now with A04 and A07 as follow-up cards (the lead's recommendation), or fix them first. With any merge, set `PER_QUERY_COST_CAP_USD=0.25` on develop's API; the permission layer refused the lead's attempt. Whether develop's writer becomes Opus 5.5 is a separate choice: at a true 25-cent bound its repairs are refused on 3 to 19 of 24 bench questions.
- The guardrail's re-split, proposed in its `DECISIONS.md` row.
- Card 40: 27 items, each a yes or no, in `testing/Developer/reports/2026-10-08_card40/itemized_list.md`.
- Closing cards 11 and 12, proposed: neither reproduced since 2026-09-25 and both fixes were reverted; reopen on a failing test query.
- Cards needing a design or decision, from tonight's diagnoses: 17, 20, 29, 33 (D19), 48, 16 (fold into 56), and the `.claude/` and A07 parts of 51 and 85. New cards found: `testing/Developer/reports/2026-10-08_overnight/new_cards.md`.
- After the 8.7 merge: delete `feat/8.7-s1` to `s3` (the lead's tag-and-delete was refused).
- Retests: "Waiting for your retest" in `testing/UI_fixes_done.md`. The night's decisions: `DECISIONS.md`, rows dated 2026-10-08.

## The one next action

Decide pull request #218, then build cards 18, 19, 30, 38 and 94 from their diagnoses in `testing/Developer/reports/2026-10-08_overnight/`, which wait on it.

How to start a session: read this file, then `git status --short` and `git worktree list`, then "Waiting for your retest" and the board's To do column. Overnight, follow `.claude/skills/overnight-development/SKILL.md`. At the end, run `/phase-checkpoint`, then `/ship`.

## Where the facts live

- The board: `testing/UI_fix_plan.md`; build order: `testing/Board_plan.md`
- Retests, the cutoff, closed items: `testing/UI_fixes_done.md`; older: `testing/UI_fixes_archive.md`
- Queries to type: `testing/Test_queries_and_workflows.md`
- Phase 8.7: `tracker/phase_8.7.md` on its branch; the night's plan: `testing/Developer/reports/2026-10-08_overnight/plan.md`
- Factory's brief: `docs/build/Factory_onboarding.md`; other work: `testing/Future.md`
- Models: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`; the narrative: `requirements/Plan.md`
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`; releases: `docs/build/Release_flow.md`
- The registry and sync check: `tracker/Living_documents.md`, `tracker/check_doc_sync.py`
