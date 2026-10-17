# Overnight plan, 2026-10-16 to 17

The lead's plan for the night, written before the owner sleeps under `.claude/rules/plan-then-fan-out.md` and `.claude/skills/overnight-development/SKILL.md`. The owner's approvals for the night are the `DECISIONS.md` rows dated 2026-10-16 that begin "Overnight of 2026-10-16 to 17", and the card rows for 18, 30 and 8 of the same date.

## Table of contents

- [The goal by morning](#the-goal-by-morning)
- [The owner's rules for the night](#the-owners-rules-for-the-night)
- [Why these cards](#why-these-cards)
- [The cards, in order](#the-cards-in-order)
- [Who works on what, by model](#who-works-on-what-by-model)
- [Waves and what runs in parallel](#waves-and-what-runs-in-parallel)
- [Not tonight](#not-tonight)
- [The morning close](#the-morning-close)

## The goal by morning

- Every card below merged on develop, or closed and back in To do with its findings.
- Each merged card checked on deployed develop at 1280 and 390, with its row in `testing/Retest_product_owner.md`.
- `/phase-checkpoint` and `/ship` run, `HANDOFF.md` rewritten for the owner.
- Locally only `develop`; on GitHub only `develop` and `production`, or every exception named in `HANDOFF.md` with its reason.

## The owner's rules for the night

| Rule | Source |
|---|---|
| Any card in this plan, and the night's docs pull request, merges when CI is green and a fresh verifier finds nothing worse than develop | Owner, before sleep |
| A reviewer that finds something worse: close the pull request, card back to To do with its findings | Owner, before sleep |
| Live checks spend $8, up to $12 only when a card's verification needs it; balance at the start $23.86 of $125 | Owner, before sleep |
| Every owner choice the diagnoses name is asked before sleep; a later one takes the smallest option that changes nothing else, logged | Owner, before sleep |
| No golden run; the test queries document is the gate, with five or more repeated live runs of each answer-path card's own questions before merge | Owner, before sleep |
| The close starts at 07:00; any card not merged by then is closed, back in To do, its branch deleted | Owner, before sleep |
| Factory's lane (cards 100, 106, 113, 117) is not touched | Owner, 2026-10-16 |
| No security-layer change, production deploy, migration or graph write | `CLAUDE.md`, overnight skill Step 4 |

## Why these cards

The night before, six of ten cards were closed by their reviewers, and each of the six was built from a new design. Tonight takes the board's "Team: buildable now" cards instead: each has a written diagnosis, a narrow fix, and stops something a person sees. The design cards (56, 101, 94, 15, 20, 29, 36, 48, 107, 110, 116) wait for a design with the owner. Cards 52 and 108 change the event schema, so they wait for a pull request the owner merges.

## The cards, in order

Ordered by what a person feels first: a confident wrong record before a confusing one, before wording.

| # | Card | What a person gets | Dial | Diagnosis |
|---|---|---|---|---|
| 1 | 30, step 1 | A list of BRCA1's ClinVar variants says plainly it is not a list of pathogenic variants, and the trust line reads "ask" | 2 | `2026-10-16_card30/diagnosis.md` |
| 2 | 37 and 38, in slices | rs334 is named by its id and gene; TP53's orthologs show their species; a gene's graph papers show their titles | 2 | `2026-10-16_card37_38/diagnosis.md` |
| 3 | 105 | A picked "How far back" window no longer shows 1999 graph papers under a heading that claims the window | 2 | `2026-10-16_card105/diagnosis.md` |
| 4 | 18 | One paper never shows on two rows | 2 | `2026-10-16_card18/diagnosis.md` |
| 5 | 8 | The line under an answer names the databases it rests on, never "not yet confirmed" | 1 | `2026-10-16_card8/diagnosis.md` |

## Who works on what, by model

| Role | Model | Why |
|---|---|---|
| Lead: split, briefs, integration, merges, board, handoff | Opus, this session | A bad split cascades into every worker |
| Diagnoses of 30, 105, 37 and 38 | Opus | A diagnosis decides what every later step builds |
| Diagnoses of 18 and 8 | Sonnet | Bounded re-checks of earlier diagnoses |
| Builders and fix agents | Sonnet | Bounded work with clear acceptance |
| Judges, adversaries and fresh verifiers | Opus | Trust-critical multi-file judgement |
| Product checks on deployed develop | Opus (product-reviewer) | It reads answers as a person would |

Workers never dispatch. Each brief names its file fence, its report path and its probe folder. Reviewers write their reports under `testing/Developer/reports/2026-10-16_card<N>/` in the docs worktree, named by card and role, never inside their own worktree.

## Waves and what runs in parallel

At most about six agents at once, since two usage limits stopped the team the night before. One full unit suite at a time; builders run their own files' tests and CI runs the rest.

| Wave | Runs together | Starts when |
|---|---|---|
| A | Five diagnoses; builders of 18 and 8 | Now |
| B | Builders of 30, the first 37 and 38 slice, 105; judge and adversary of 18; fresh verifier of 8 | Each diagnosis read and its owner choices answered |
| C | Each card's judge, adversary, one fix round, fresh verifier, merge, product check | As each builder reports |
| Close | `/phase-checkpoint`, `/ship`, clean-up | 07:00, or earlier when every card has merged or been closed |

Cards that write the same function run one after the other. `core/graph.py` is shared by 18, 30, 37 and 38 in different functions; a branch takes develop by a merge commit before its review if another card merged first.

## Not tonight

| Card | Why it waits |
|---|---|
| 30, step 2 | The owner chose the honest line only; showing each classification waits for a design |
| 52, 108 | Event-schema changes, dial 3: a pull request the owner merges |
| 100, 106, 113, 117 | Factory's lane |
| The design cards | Each needs a design with the owner first |

## The morning close

1. `/phase-checkpoint` in UI-fix-loop mode: board, retest file, done file, `PROGRESS.md`, Plan.md, `HANDOFF.md`.
2. `/ship` with the night's docs branch, `chore/overnight-2026-10-16`.
3. Local and GitHub brought to their steady state; anything left named in `HANDOFF.md`.
