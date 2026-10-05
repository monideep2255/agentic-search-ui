# Handoff

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-05.

## Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

## What is live

- Develop: `042985a3`, the merge of #175. Both Railway services redeploy on every push to `develop`. Nothing is built between sessions; check `gh run list --branch develop --limit 3` before trusting CI.
- Production: `v0.2.0`, tag `cde4f592`, released 2026-09-20. Nothing since is on it. The changelog fix, `testing/Future.md` row 53, lands before the next release.
- The gate for a change is the test queries document, run by agent runners on develop; the golden run is an alarm only (`DECISIONS.md`, 2026-10-05).
- The build order is `testing/Board_plan.md`: root causes, waves, the owner's decisions. Its Progress list says where the waves stand.
- Two development agents: this lead (answer path, the board, the plan, the one merge queue) and Factory (screens and wording, cards 43, 44, 18, 23, 24, 25, 47 and the rest of 61, on `factory/` branches). Merge one pull request at a time; several at once starve CI of runners (`LEARNINGS.md`, 2026-10-05).
- Parked on GitHub: `feat/8.7-s1` to `s3` and `phase/8.7-answers-sooner` (phase 8.7, resume plan in `testing/Developer/reports/2026-10-05_phase_8.7_resume/plan.md`); `fix/card72-r10-guardrail` and `fix/card84-r10-sound-parts` (guardrail, returns as an agreed design).

## What awaits the product owner

- Retests: the board's Retest column, newest first, each card naming its test query.
- A top-up of the OpenRouter account before phase 8.7 (about $38.50 left against its approved $60; develop's live answers draw on it too).
- Decisions D5 to D21 in `testing/Board_plan.md` are taken as recommended unless the owner objects.
- A note to NCBI about the broken encoding in MedGen's Muir-Torré syndrome record, drafted by the lead for the owner to send.
- Unchanged from earlier: the privacy hooks and `railway link` on the second laptop.

## The one next action

Diagnose why the SARS-CoV-2 question still answers about the disease SARS on develop though card 56's fix passed locally (card 56 at the top of To do; evidence `testing/Developer/reports/2026-10-05_final_test_queries/results.md`). Then card 99's measurement, then phase 8.7 once the account is topped up.

How to start a session: read this file, then `git status --short` and `git worktree list` (expect the main checkout on `develop`, plus any Factory worktrees, which are not ours to touch), then `git ls-remote --heads origin 'factory/*'` and `gh pr list` for Factory's work (move its cards on the board as they start and land), then the board's Retest and To do columns. At the end, run `/phase-checkpoint`, then `/ship`.

## Where the facts live

- The board, every card: `testing/UI_fix_plan.md`
- The build order and progress: `testing/Board_plan.md`
- The cutoff and every closed item: `testing/UI_fixes_done.md`, from "Where we stopped"
- Queries to type and what a person sees: `testing/Test_queries_and_workflows.md`
- Work outside the board: `testing/Future.md`
- A numbered phase's tickets and findings: `tracker/phase_N.M.md`
- Models and how calls hand off: `docs/architecture/Model_architecture.md`
- Why, and what broke: `DECISIONS.md`, `LEARNINGS.md`
- The dated narrative: `requirements/Plan.md`, Revision history
- How a card or phase runs: `.claude/skills/bossman-mode/SKILL.md`
- Releases: `docs/build/Release_flow.md`
- The living-documents registry: `tracker/Living_documents.md`
