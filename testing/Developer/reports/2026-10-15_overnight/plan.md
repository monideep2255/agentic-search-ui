# Overnight plan, 2026-10-15 to 16

The lead's plan for the night, written before the owner sleeps under `.claude/rules/plan-then-fan-out.md` and `.claude/skills/overnight-development/SKILL.md`. The owner's approvals for the night are the `DECISIONS.md` rows dated 2026-10-15 that begin "Overnight of 2026-10-15 to 16".

## Table of contents

- [The goal by morning](#the-goal-by-morning)
- [The owner's rules for the night](#the-owners-rules-for-the-night)
- [The cards, in order](#the-cards-in-order)
- [Who works on what, by model](#who-works-on-what-by-model)
- [Waves and what runs in parallel](#waves-and-what-runs-in-parallel)
- [Not tonight](#not-tonight)
- [The morning close](#the-morning-close)

## The goal by morning

- Every card below merged on develop, or reverted and back in To do with its findings.
- Each merged card checked on deployed develop at 1280 and 390, with its row in `testing/Retest_product_owner.md`.
- `/phase-checkpoint` and `/ship` run, `HANDOFF.md` rewritten for the owner.
- Locally only `develop`; on GitHub only `develop` and `production`, except the parked branch and tags a card still needs, each named in `HANDOFF.md` with its reason.

## The owner's rules for the night

| Rule | Source |
|---|---|
| Any card in this plan merges when CI is green and a fresh verifier finds nothing worse than develop | Owner, before sleep |
| A verifier that finds something worse: close the pull request, card back to To do with its findings | Owner, before sleep |
| Live checks spend $8, up to $12 if needed to verify every card; balance at the start was $30.69 of $125 | Owner, before sleep; OpenRouter credits read at 23:30 |
| A design that names an owner's choice: take the designer's recommendation, log it, build it | Owner, before sleep |
| The close starts at 07:00; any card not merged by then is closed, back in To do, its branch deleted | Owner, before sleep |
| Factory is not working: its cards are the lead's | Owner, 2026-10-15 |
| No security-layer change, production deploy, migration or graph write | `CLAUDE.md`, overnight skill Step 4 |
| No golden run; the test queries document is the gate | Overnight skill Step 6 |

## The cards, in order

| # | Card | What a person gets | Depends on | State at 23:30 |
|---|---|---|---|---|
| 1 | 29 | One sentence of each of the first five papers' own abstracts, never from a retracted paper or cut short | none | Fix round running |
| 2 | Retest rule (#238) | `/ship` stops a push when a live card has no row in the retest file | none | Verifier running |
| 3 | 115 | A graph-change follow-up always gets the read-only reply | none | Builder running |
| 4 | 94 | One named isolate looked up in about 2 s, with a plain line when it is not found | none | Builder running |
| 5 | 24 | The Plain language and Researcher switch beside an answer, its cost shown first | 29 merged (same answer screen file) | Waits |
| 6 | 20 | Isolate searches narrowed by year and place, read by a separate small call | 94 merged (same isolate files) | Waits |
| 7 | 15 | One checked graph search per question shape, starting with the five the build note names | none | Design first |
| 8 | 17 | A reworded sentence that moves to another paper names that paper (option E) | none | Design first |
| 10 | 110 | The answer opens on the sentence that answers, never on a paper title or a sentence leaning on another | Design first (Fable) | Design starting |
| 11 | 101 | A record's sentence ends where the record's sentence ends, so a quote never loses its negation | Design first (Fable) | Design starting |
| 12 | 84 and 72, step 3b | A question after a long server pause is checked the same as any other | Design first (Fable) | Design starting |
| 9 | 75 | A sign-in renewal reply that cannot be read no longer signs the person out | none; approved by the owner at 23:35 | Builder starting |

## Who works on what, by model

The tier follows the cost of a mistake, per the owner's standing rule on sub-agent tiers.

| Role | Model | Why |
|---|---|---|
| Lead: split, briefs, integration, merges, board, handoff | Opus, this session | A bad split cascades into every worker |
| Designs for cards 15, 17, 110, 101 and 84 and 72 | Fable | The hardest reasoning: a design decides what every later step builds |
| Adversaries on answer-path cards (29's verifier included) | Fable for 29 and 17; Opus for the others | Hunting a confident wrong answer is where review misses cost most |
| Judges and fresh verifiers | Opus | Trust-critical multi-file judgement |
| Builders and fix agents | Sonnet | Bounded work with clear acceptance |
| Product checks on deployed develop | Opus (product-reviewer) | It reads answers as a person would |
| Doc audits of the handoff and the night's docs | Sonnet (doc-auditor) | A checklist grade |
| Mechanical edits: query numbering, report path scans, leak triage | Haiku | Copying fields, no judgement |

Workers never dispatch. Each brief names its file fence, its report path and its budget.

## Waves and what runs in parallel

No two workers write the same file. One full unit suite runs at a time; builders run their own files' tests and CI runs the rest. At most about eight agents at once.

| Wave | Runs together | Starts when |
|---|---|---|
| A, running | Card 29 fix round, card 94 builder, card 115 builder, retest rule verifier | Now |
| B | Card 29 verifier (Fable); card 94 judge and adversary; card 115 judge and adversary; card 15 design (Fable); card 17 design (Fable) | As each of wave A reports |
| C | Card 24 builder; card 20 builder; card 15 builder; card 17 builder; card 75 builder | 29 merged for 24; 94 merged for 20; the design read for 15 and 17 |
| D | Each card's judge, adversary, one fix round, fresh verifier, merge, product check | As each builder reports |
| Close | `/phase-checkpoint`, handoff audit, `/ship`, clean-up | 07:00, or earlier when every card has merged or been reverted |

## Not tonight

| Card | Why it waits |
|---|---|
| 48, 116 and card 56's open cases | No branch or tag holds their work; each needs a design with the owner and stays in To do |
| 100 | A low-priority screen card from Factory's old list; next after this plan |

## The morning close

1. `/phase-checkpoint` in UI-fix-loop mode: board, retest file, done file, `PROGRESS.md`, Plan.md, `HANDOFF.md`.
2. A fresh doc audit of `HANDOFF.md` before it ships.
3. `/ship` with the night's docs branch, `chore/overnight-2026-10-15`.
4. Local and GitHub brought to their steady state; anything left named in `HANDOFF.md`.
