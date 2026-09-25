# Handoff

What a fresh session needs, and nothing else. Rewritten in place at every `/phase-checkpoint`, never appended to. It states no fact another file owns beyond the pointers in the last section; history goes to `requirements/Plan.md`'s Revision history and `testing/UI_fixes_done.md`, never here.

Last updated: 2026-09-24.

## Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

## What is live

- Develop: product code through `9b9ff2b`, plus the SQLAlchemy pin at `cfff699`. Every later commit is documents, rules, skills and tests; the newest is `f21f439`, pull request #104, deployed with SUCCESS on both services. Both Railway services redeploy on every push to `develop`.
- Production: `v0.2.0`, tag `cde4f59`, released 2026-09-20. Nothing from 2026-09-21 onward is on it. Settle any doubt with `git tag --sort=-creatordate | head -1` and `git log origin/production -1`.
- Nothing is being built between sessions. The board's "Build in progress" column is the check.
- CI on GitHub runs: all four jobs passed on pull request #104. One test inside the unit gate calls NCBI live, so an NCBI outage can turn it red; read `unit-results.xml` before blaming the code. Check `gh run list --branch develop --limit 3` before trusting this line.

## What awaits the product owner

- Retests: every card in the Retest column of `testing/UI_fix_plan.md`, newest first. Each card names its query numbers in `testing/Test_queries_and_workflows.md`.
- Decisions: every To do card whose "Waiting on" reads "Your decision", and the seven test files set aside in `docs/build/Bossman_redesign_deletion_inventory.md`.

## The one next action

After the retests: To do item 1 in `testing/UI_fix_plan.md`, currently 12.14.

- Its reasons and bounds: item 1 of "Next, in order" in `testing/UI_fixes_done.md`.
- Read before picking anything up: "What is parked, and why", in the same file.

## Where the facts live

| Question | Owner |
|---|---|
| What is not started, being built, or live awaiting retest | `testing/UI_fix_plan.md`, the board |
| The cutoff, the ordered next actions, what is parked and why, every closed item | `testing/UI_fixes_done.md`, starting at "Where we stopped" |
| The exact queries to type and what a person should see | `testing/Test_queries_and_workflows.md` |
| Which documents the session-closing skills keep current, and their current shape | `tracker/Living_documents.md` |
| Why something was decided | `DECISIONS.md`, newest rows last |
| What broke and what fixed it | `LEARNINGS.md` |
| Build phase status and open flags | `tracker/BOARD.md` and `tracker/phase_N.M.md` |
| The dated narrative of every phase and session | `requirements/Plan.md`, Revision history |
| The plain-language state, for someone outside the build | `PROGRESS.md` |
| How the UI fix loop runs | `.claude/skills/bossman-mode/reference/UI_fix_loop.md` |
| How a build phase runs, its team, budget and product review | `.claude/skills/bossman-mode/SKILL.md` and `docs/build/Build_workflow_cadence.md` |
| How a release is cut | `docs/build/Release_flow.md` |
| The Phase 6 continuation prompt this file replaced, kept as a record | `requirements/phase_6/Continuation_prompt-archive.md` |

How to start: read this file, then `git status --short` and `git worktree list` (both clean, local carrying only `develop`), then the board's Retest and To do columns, then "Where we stopped". Run `/phase-checkpoint` then `/ship` at the session's end.
