# Handoff

What a fresh session needs, and nothing else. Rewritten in place at every `/phase-checkpoint`, never appended to. It states no fact another file owns beyond the pointers in the last section; history goes to `requirements/Plan.md`'s Revision history and `testing/UI_fixes_done.md`, never here.

Last updated: 2026-09-25.

## Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

## What is live

- Develop: the overnight build of 2026-09-25, merged as pull requests #105 (phase 8.1), #107 (phase 8.5) and #106 (phase 8.2, product code through `06f4587`); later commits are documents and evidence. Develop's API carries `CLASSIFIER_PROVIDER=jev`. Both Railway services redeploy on every push to `develop`.
- The rollback point: the tag `pre-overnight-2026-09-25`. `testing/Developer/scripts/bin_overnight.py --all --yes` restores develop's product code to it and takes back the logged Railway setting; `--phase 8.N --yes` bins one phase; `--list` shows what would change.
- Phase 8.4 is built on the branch `phase/8.4-answers-worth-reading`, not merged, with no pull request yet.
- Production: `v0.2.0`, tag `cde4f59`, released 2026-09-20. Nothing since is on it. Settle any doubt with `git tag --sort=-creatordate | head -1` and `git log origin/production -1`.
- Nothing is being built between sessions. CI passed on each of the three pull requests before merge; check `gh run list --branch develop --limit 3` before trusting this line.

## What awaits the product owner

- The morning report of the overnight build, and its first question: keep the night, bin a phase, or bin it all.
- Retests: the Retest column of `testing/UI_fix_plan.md`, newest first. Read the product review of phase 8.1 before retesting: `testing/Developer/reports/2026-09-25_product_review_8.1/report.md`.
- Decisions: every To do card whose "Waiting on" reads "Your decision", including the writing model from the bench and the code-built opening line every answer starts with.

## The one next action

After the product owner's verdict on the night: To do item 1 in `testing/UI_fix_plan.md`, the stray "MedGen lists no clinical features" sentence in unrelated answers.

- Its reasons and the order after it: "Next, in order" in `testing/UI_fixes_done.md`.
- Read before picking anything up: "What is parked, and why", in the same file.

## Where the facts live

| Question | Owner |
|---|---|
| What is not started, being built, or live awaiting retest | `testing/UI_fix_plan.md`, the board |
| The cutoff, the ordered next actions, what is parked and why, every closed item | `testing/UI_fixes_done.md`, starting at "Where we stopped" |
| The exact queries to type and what a person should see | `testing/Test_queries_and_workflows.md` |
| The overnight build's plan, the product owner's answers and the night's log | `testing/Overnight_build_plan_2026-09-25.md` |
| Each overnight phase's tickets, findings and reverts | `tracker/phase_8.1.md`, `tracker/phase_8.2.md`, `tracker/phase_8.5.md` |
| Which model does what, and how the calls hand off | `docs/architecture/Model_architecture.md` |
| The remaining work outside the UI fix loop | `testing/Future.md` |
| Which documents the session-closing skills keep current | `tracker/Living_documents.md` |
| Why something was decided | `DECISIONS.md`, newest rows last |
| What broke and what fixed it | `LEARNINGS.md` |
| Build phase status and open flags | `tracker/BOARD.md` and `tracker/phase_N.M.md` |
| The dated narrative of every phase and session | `requirements/Plan.md`, Revision history |
| The plain-language state, for someone outside the build | `PROGRESS.md` |
| How the UI fix loop and a build phase run | `.claude/skills/bossman-mode/SKILL.md` and its `reference/` files |
| How a release is cut | `docs/build/Release_flow.md` |

How to start: read this file, then `git status --short` and `git worktree list` (local should carry only `develop`, plus `phase/8.4-answers-worth-reading` until it is merged or closed), then the board's Retest and To do columns, then "Where we stopped". Run `/phase-checkpoint` then `/ship` at the session's end.
