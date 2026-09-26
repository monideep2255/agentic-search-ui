# Handoff

What a fresh session needs, and nothing else. Rewritten in place at every `/phase-checkpoint`, never appended to. It states no fact another file owns beyond the pointers in the last section; history goes to `requirements/Plan.md`'s Revision history and `testing/UI_fixes_done.md`, never here.

Last updated: 2026-09-26.

## Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

## What is live

- Develop's product code is the overnight build of 2026-09-25 (phases 8.1, 8.5 and 8.2), unchanged since 654f2d2.
  - Phase 8.6 merged as #108, then its product code came off develop through #111, because its golden run answered 99 of 150 against the floor of 102. Its ledger, decision rows and the server-address redaction stay.
  - Merged the same day, with no product code: the build-harness fixes (#110), the four hook gaps (#112), and card 42's proposal (#113).
  - Develop's API carries `CLASSIFIER_PROVIDER=jev`. Both Railway services redeploy on every push to `develop`.
- Parked, not merged: phase 8.4 at the tag `parked/phase-8.4-2026-09-25`, and the paper-sentence work at `parked/phase-8.8-snippets-2026-09-25`.
- Production: `v0.2.0`, tag `cde4f59`, released 2026-09-20. Nothing since is on it.
- Rolling back: the tag `pre-overnight-2026-09-25` with `testing/Developer/scripts/bin_overnight.py --all`. Do not use its `--phase` mode on a merge that carries documents; restore the product paths instead (`LEARNINGS.md`, 2026-09-26).
- Nothing is being built between sessions. Check `gh run list --branch develop --limit 3` before trusting that CI is green.

## What awaits the product owner

Six decisions, each a yes, no or pick-one with a recommendation, asked on 2026-09-26:

- Phase 8.6: accept its golden drop and re-land it, or keep it off until three problems are fixed. The drop and the problems are in `tracker/phase_8.6.md`, History and finding F-8.6-G01. Phase 8.9 waits on this.
- The verify loop, card 42: `docs/build/Verify_loop_proposal.md`, its build order, and whether a `/verify` pass may close a wording or layout card on the seven-day clock.
- Password login off on the graph server (`testing/Overnight_build_plan_2026-09-25.md`, "Waiting for the product owner").
- Security-layer items named open:
  - the secret scan's slowdown on a very long command, F02 on pull request #110;
  - the hook shapes left open on #112: the secret check on file writes, and upper-case wrappers.
- Retests: the Retest column of `testing/UI_fix_plan.md`, newest first.

## The one next action

The owner's answer on phase 8.6 decides it.

- Keep it off: fix the three problems as a re-split of 8.6 with its own review, rerun the golden run, then open phase 8.9 from `tracker/phase_8.9.md`.
- Accept: revert #111's commit to bring the code back, then open phase 8.9.
- Either way, card 39 (the visualization deep dive) goes out after that answer, since what it describes depends on it.

## Where the facts live

| Question | Owner |
|---|---|
| What is not started, being built, or live awaiting retest | `testing/UI_fix_plan.md`, the board |
| The cutoff, the ordered next actions, what is parked and why, every closed item | `testing/UI_fixes_done.md`, starting at "Where we stopped" |
| The exact queries to type and what a person should see | `testing/Test_queries_and_workflows.md` |
| Phase 8.6's tickets, findings, triage, golden result and rollback | `tracker/phase_8.6.md` |
| Phase 8.9's plan, tickets and dispatch plan, not yet opened | `tracker/phase_8.9.md` |
| Earlier numbered phases | `tracker/phase_N.M.md`; `tracker/BOARD.md` is frozen at 6.2 |
| The overnight build's plan, the owner's answers and the nights' log | `testing/Overnight_build_plan_2026-09-25.md` |
| Which model does what, and how the calls hand off | `docs/architecture/Model_architecture.md` |
| The golden runs and their floor | `testing/Developer/reports/<date>_phase_N.M_golden/summary.md`; the floor is phase 8.2's run |
| The remaining work outside the UI fix loop | `testing/Future.md` |
| Which documents the session-closing skills keep current | `tracker/Living_documents.md` |
| Why something was decided | `DECISIONS.md`, newest rows last |
| What broke and what fixed it | `LEARNINGS.md` |
| The dated narrative of every phase and session | `requirements/Plan.md`, Revision history |
| The plain-language state, for someone outside the build | `PROGRESS.md` |
| How a phase or a card runs | `.claude/skills/bossman-mode/SKILL.md` and its `reference/` files |
| How a release is cut | `docs/build/Release_flow.md` |

How to start: read this file, then `git status --short` and `git worktree list` (local should carry only `develop`), then the board's Retest and To do columns, then "Where we stopped". Run `/phase-checkpoint` then `/ship` at the session's end.
