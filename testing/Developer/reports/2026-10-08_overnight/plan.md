# Overnight plan, 2026-10-08 to 09

This is the lead's plan for the night, written before the first merge. The owner's instruction and answers are the `DECISIONS.md` rows of 2026-10-08, starting with "The overnight run of 2026-10-08 to 09".

## Table of contents

- [Goal contract](#goal-contract)
- [Work in order](#work-in-order)
- [Spend](#spend)
- [Skipped and why](#skipped-and-why)

## Goal contract

- Done when: every card on the owner's list ends merged on develop and checked on deployed develop at 1280 and 390, or parked with its reason and the one event that ends the park named in `HANDOFF.md`. Locally only `develop` is left, and GitHub holds `develop`, `production` and release tags, or each exception is named.
- Verify: CI green on each pull request; a fresh verifier finding nothing worse than develop; the card's entries in `testing/Test_queries_and_workflows.md` run on deployed develop after the Railway deploy carries the merge commit. Not covered: the golden run, which the owner did not ask for.
- Output: merged pull requests, report folders under `testing/Developer/reports/`, `DECISIONS.md` rows as decisions are taken, and `HANDOFF.md` rewritten at the close.
- Constraints: no security-layer change, no production deploy, no migration other than card 71's, no graph write, Factory assigned nothing, at most two full test suites at once.
- Blocked-stop: a refused merge is named for the owner, never routed around; a regression inside a fix round is reverted or parked, never given a third round; a spend ceiling reached stops that work's live checks.

## Work in order

| Order | Work | Branch | State at start |
|---|---|---|---|
| 1 | Phase 8.7, steps 0 to 9 of `testing/Developer/reports/2026-10-05_phase_8.7_resume/plan.md` | `phase/8.7-answers-sooner` | Steps 0, 1 and 3 on the branch; builders on steps 2, 4, 5, 6 and 7 |
| 2 | Guardrail, cards 84 and 72: steps 1 and 3 of the design; step 2 parked | `fix/card84-72-guardrail` | Builder dispatched |
| 3 | Card 71, the "High-risk claim" tag with its one migration | `fix/card71-high-risk-tag` | Builder dispatched |
| 4 | Buildable To do cards and the partly live cards' last slices | one `fix/cardN-...` branch each | Diagnoses written in this folder |
| 5 | Card 40's itemized list, written only | this docs branch | Writer dispatched |
| 6 | Cards 11 and 12 proposed for closing | `HANDOFF.md` | At the close |

## Spend

OpenRouter read at 2026-10-09T00:11Z: $36.11 left.

- Phase 8.7: at most $20, read from the credits endpoint before and after each run.
- Every other card's test queries: at most $6 together.
- At least $10 stays for the owner's retests.

## Skipped and why

| Card | Why |
|---|---|
| 56 | Its remaining cases need a design with the owner first |
| 75, 24, 100 | Factory's lane; Factory does no work tonight |
| 25 | A new package needs the owner's approval and a supply-chain review |
| 42, 52, 55 | Waiting on the owner's yes |
| 4, 6, 7, 8, 9 | The owner's architecture cards |
