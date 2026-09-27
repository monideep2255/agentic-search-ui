# Handoff

What a fresh session needs, and nothing else. Rewritten in place at every `/phase-checkpoint`, never appended to. It states no fact another file owns beyond the pointers in the last section; history goes to `requirements/Plan.md`'s Revision history and `testing/UI_fixes_done.md`, never here.

Last updated: 2026-09-27.

## Table of contents

- [What is live](#what-is-live)
- [What awaits the product owner](#what-awaits-the-product-owner)
- [The one next action](#the-one-next-action)
- [Where the facts live](#where-the-facts-live)

## What is live

- Develop's product code is card 58's merge, e116b9d9: Stop works until the answer appears. Everything after it on develop is documents. `git log --merges --first-parent develop` lists what came before.
- Develop's API carries `CLASSIFIER_PROVIDER=jev` and `SYSTEM_DAILY_CAP_USD=25`, raised from $10 on 2026-09-27. Both Railway services redeploy on every push to `develop`.
- Production: `v0.2.0`, tag `cde4f59`, released 2026-09-20. Nothing since is on it.
- Parked tags: `parked/phase-8.4-2026-09-25`, `parked/phase-8.8-snippets-2026-09-25` and `parked/verify-facts-118-2026-09-27`.
- Nothing is being built between sessions. The machine restarted at 06:45 UTC on 2026-09-27 with seven agents running, and the owner parked everything except the release job (`DECISIONS.md`, the same day).
- PubMed answers again, since 06:26 UTC on 2026-09-27. Check `gh run list --branch develop --limit 3` before trusting that CI is green.

### Parked work, to pick up later

Nothing below is pushed unless it says so. Each worktree is under `.claude/worktrees/`.

| Work | Done | Where | Not done |
|---|---|---|---|
| Release job, both repositories | Built and fixed after one review round; System 3's CI passed | #125 (`chore/release-without-production-push`), data engineering #9 (`chore/release-cadence`) | In progress today: the fresh reviewer's verdict, the merges, the README line, data engineering's v1.0.0 and `production` in both repositories' owner-only rule |
| Phase 8.7 builder A: the first sentence answers the question | Built, not reviewed; its unit suite never finished | `feat/8.7-s1` at 32e5945e, worktree `p87s1` | Review its own diff, run the suite, commit it properly |
| Phase 8.7 builder B: records on screen while the summary is written | The `placement` field (1e030148); the screen work, not reviewed | `feat/8.7-s2` at cb407508, worktree `p87s2` | The screen and App-level Stop tests (one new test file's write was refused), reshaping `App.stopUntilAnswer.test.tsx`, the mutation reds, the gates |
| Phase 8.7 builder C: shorter waits, the Opus writer | Six commits, every mutation red | `feat/8.7-s3` at da2c04f6, worktree `p87s3` | Its final gates |
| Phase 8.7 as a whole | Tickets, findings and every decision | `tracker/phase_8.7.md`, branch `phase/8.7-answers-sooner` | Merge the three builders into the phase branch, then the judge, the adversary and one fix-and-verify; then the golden run at 101 or more plus test queries 1, 2, 17, 72 and 98, reverting on failure; then the product review. At merge, set `PER_QUERY_COST_CAP_USD=0.25` on develop. Up to 12 dispatches |
| Card 63: every "not yet confirmed" answer saved, and an NCBI outage said so | Built and tested; the adversary passed it | `fix/card63-tested` at 1c1558a4, worktree `card63` | The judge's round (cut part-way), a fix round if it finds anything, a fresh verifier, the merge, then the golden run at 101 or more plus its test queries, reverting on failure |
| Card 53: stale facts on the pages and in the documents | Eight commits | `fix/card53-stale-facts` at a470c82e, worktree `card53` | The builder's report, the review, the gates, the merge |
| Card 62: install and connect from the Integrations page on the first try | Five commits | `fix/card62-install-first-try` at 4f749a7f, worktree `card62` | Its test run, its report, the judge and the adversary, the merge |
| Card 58: Stop works until the answer appears | Live on develop | The board's Retest column | The product review of develop, then your retest with query 98 |

The reviewers' probes lived in the temporary folder the restart cleared, so any resumed reviewer reruns its probes.

## What awaits the product owner

- Retests: the Retest column of `testing/UI_fix_plan.md`, newest first. Card 58 is at the top, query 98.
- When to resume the parked work above.

## The one next action

Resume the parked work two agents at a time, card 63's judge first, since card 63 is closest to landing. Run one unit suite at a time: several at once took the machine down on 2026-09-27.

## Where the facts live

| Question | Owner |
|---|---|
| What is not started, being built, or live awaiting retest | `testing/UI_fix_plan.md`, the board |
| The cutoff, the ordered next actions, what is parked and why, every closed item | `testing/UI_fixes_done.md`, starting at "Where we stopped" |
| The exact queries to type and what a person should see | `testing/Test_queries_and_workflows.md` |
| Phase 8.7's tickets, findings, decisions and where each builder stopped | `tracker/phase_8.7.md` |
| Phases 8.6 and 8.10, and earlier numbered phases | `tracker/phase_N.M.md`; `tracker/BOARD.md` is frozen at 6.2 |
| Phase 8.9's plan, not yet opened | `tracker/phase_8.9.md` |
| Card 58's reviews | `testing/Developer/reports/2026-09-27_card58_stop/review.md` |
| Which model does what, and how the calls hand off | `docs/architecture/Model_architecture.md` |
| The golden run and its floor | `.claude/skills/bossman-mode/reference/Product_review.md`, Step 2; the owner set 101 for card 63 and phase 8.7 (`DECISIONS.md`, 2026-09-27) |
| The remaining work outside the board | `testing/Future.md` |
| Which documents the session-closing skills keep current | `tracker/Living_documents.md` |
| Why something was decided | `DECISIONS.md`, newest rows last |
| What broke and what fixed it | `LEARNINGS.md` |
| The dated narrative of every phase and session | `requirements/Plan.md`, Revision history |
| The plain-language state, for someone outside the build | `PROGRESS.md` |
| How a phase or a card runs | `.claude/skills/bossman-mode/SKILL.md` and its `reference/` files |
| How a release is cut | `docs/build/Release_flow.md` |

How to start: read this file, then `git status --short` and `git worktree list`. Locally, expect `develop` plus the parked branches above. Then read the board's Retest and To do columns. Run `/phase-checkpoint` then `/ship` at the session's end.
