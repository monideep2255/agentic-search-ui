# Handoff

The current state a fresh session needs, and nothing else. `/phase-checkpoint` rewrites it in place at every session end and keeps it to about 4 KB. Earlier versions, and the setup steps for a new laptop, are in `docs/build/Handoff_history.md`.

Last updated: 2026-10-07.

## Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

## What is live

- Develop: `fde37ddf`, the merge of #199. Both Railway services redeploy on every push to `develop`; check `gh run list --branch develop --limit 3` before trusting CI.
- Production: `v0.2.0`, tag `cde4f592`, released 2026-09-20. Nothing since is on it. The changelog fix, `testing/Future.md` row 53, lands before the next release.
- The overnight run of 2026-10-06 to 07 merged the readability pass (#196) and cards 22, 23 and 102 (#197 to #199), each behind CI and a fresh verifier. What it did and why: the done file's session table and `DECISIONS.md` rows dated 2026-10-06 and 2026-10-07.
- Factory works every day from `docs/build/Factory_onboarding.md`; its next cards are 75, then 24, then 100. Paste-in prompt: "Read docs/build/Factory_onboarding.md in full, then build card 75, one pull request; then card 24, then card 100." The lead verifies each pull request before merging.
- Kept on GitHub: `fix/card101-copied-cuts` (card 101, parked); `feat/8.7-s1` to `s3` and `phase/8.7-answers-sooner` (phase 8.7); `fix/card72-r10-guardrail` and `fix/card84-r10-sound-parts` (guardrail reference).
- Local worktrees left for the morning clean-up, all merged or pushed: `asu-card22`, `asu-card23`, `asu-card101c`, `asu-card102`, `asu-readability`, `asu-checkpoint`. Remove only after `git merge-base --is-ancestor` or a pushed branch confirms nothing is lost.

## What awaits the product owner

- Retests: "Waiting for your retest" in `testing/UI_fixes_done.md`, newest first, cards 102, 23 and 22 on top.
- Card 101: whether to try dropping the whole sentence whenever a copied cut is held back, on its parked branch (`DECISIONS.md`, 2026-10-07).
- The decisions the lead took on your behalf overnight, each a `DECISIONS.md` row: the readability merge bar, the withdrawn board-cell move, the last rounds of cards 22 and 101, and card 102.
- Card 40: the itemized list of hook and always-loaded rule changes, each for your yes or no. Nothing in the security layer changed overnight.
- From before: decisions D5 to D21 in `testing/Board_plan.md` (taken as recommended unless you object), the OpenRouter top-up phase 8.7 waits on, the MedGen encoding note to NCBI, and the privacy hooks and `railway link` on the second laptop.

## The one next action

Ask the owner card 101's question, then build from the board's To do column top down: card 56's remaining cases with a design agreed first, per `testing/UI_fixes_done.md`, "Next, in order". Review Factory's pull requests as they arrive.

How to start a session: read this file, then `git status --short` and `git worktree list`, then "Waiting for your retest" and the board's To do column. At the end, run `/phase-checkpoint`, then `/ship`.

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
