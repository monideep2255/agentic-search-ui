# Build phase 8.2: one place where every choice is made

Branch: `phase/8.2-classifier-seam`. Opened 2026-09-25 05:05 UTC, alongside phase 8.1, on files phase 8.1 did not touch; its second wave started once phase 8.1's builders released `core/graph.py`.

The second phase of the overnight plan, `testing/Overnight_build_plan_2026-09-25.md`. It builds the product owner's architecture direction of 2026-09-23: Jev, TypeSafe's decision model, makes the search loop's small choices through one classifier seam, with the guard-tier model deciding the same inputs beside it only for a comparison table (DECISIONS.md, 2026-09-25, cards 8, 9, 10 and 13).

## Table of contents

- [Goal contract](#goal-contract)
- [Budget](#budget)
- [Tickets](#tickets)
- [Coverage: what this phase does not cover](#coverage-what-this-phase-does-not-cover)
- [History](#history)
- [Findings](#findings)

## Goal contract

- Done when: every ticket meets its acceptance, the pull request's CI is green, one judge round and one adversary round leave no blocking finding after one fix-and-verify, and the golden run on develop after merge answers at least the floor.
- Verify: each ticket's tests and live runs; the golden consistency run with `CLASSIFIER_PROVIDER=jev` set on develop.
- Output: one pull request; this file; test-query entries and Retest cards.
- Constraints: every rule under `.claude/rules/`; `CLASSIFIER_PROVIDER=guard` is the code default, so production is unchanged until a release; the cite-or-refuse gate and every safety check are untouched; no database migration; the Think, Plan and Write stable prompt prefixes stay byte-identical.
- Blocked-stop: as phase 8.1.

## Budget

- Wall clock: 8 hours from 05:05 UTC.
- Dispatches: 8. Used before review: builder D (the seam) and builder J (the wiring).
- Golden floor: phase 8.1's accepted result, or 86 of 150 if phase 8.1's run is not accepted.
- Answer path: yes.

## Tickets

### T-8.2-01: One classifier seam, with Jev deciding and the guard tier recorded beside it

Status: in-review, builder D, `b352516`; `52b6890` (builder J) sends each decision's meaning to both models
Cards: 8, 13

Acceptance: `decide()` in `harness/decide.py` calls Jev and the guard tier concurrently when `CLASSIFIER_PROVIDER=jev`, uses Jev's choice when it answers in time with an offered option, and otherwise the guard tier's with the reason recorded; with the default `guard`, Jev is never called. Live: Jev answered in 218 to 401 milliseconds with valid options; after `52b6890`, 21 of 21 probes right.

### T-8.2-02: The function catalogue and the task-to-tier table

Status: in-review, builder D, `b352516`
Cards: 9, 10 (the table)

Acceptance: `tools/catalogue.py` lists 17 actions of the seven tools with input schemas generated from their Pydantic models, in a fixed order; `harness/task_tiers.py` names the tier or provider of every model call and decision point. Nothing else changes.

### T-8.2-03: A question the word list does not recognise is judged by the classifier, not refused

Status: in-review, builder J, `872cac7`
Card: 8 (relevancy), card 5 (G-038)

Acceptance: the biomedical allowlist may only admit; an unrecognised question goes to `decide("guardrail.relevancy")`. Live: `Tell me about the tree of life` admitted and answered; `what is the best pizza in Chicago` refused 3 of 3 with today's wording.

### T-8.2-04: The one-to-three-word ask-back goes through the seam

Status: in-review, builder J, `9f079ce`
Card: 8 (item 12.3)

Acceptance: `reflux disease` asked back; `What is GERD?`, `Any trials for GERD?` and a short follow-up answered.

### T-8.2-05: "Recent papers" asks which years

Status: in-review, builder J, `44f97dc`
Card: 4 (item 12.15)

Acceptance: `recent papers on statins` asks "How far back should I search?" with 12 months, 5 years and 10 years; choosing 5 years returned only papers dated 2022 to 2024; `papers on statins since 2022` is not asked back.

### T-8.2-06: Whether a question asks for papers is a classifier's choice, not a word list

Status: in-review, builder J, `4b32994`
Card: 3 (item 12.16 part 3)

Acceptance: `_LITERATURE_WORDS` no longer decides; `papers on caffeine` and the MTHFR literature question route to papers; `What is GERD?` does not.

### T-8.2-07: Every answer carries the choices its run made

Status: in-review, builder J, `abead5a`
Card: 13

Acceptance: the done event's optional `decisions` field carries every DecisionRecord; decisions at one step run concurrently; median time to the plan event changed by minus 0.02 seconds.

### T-8.2-08: Golden row G-035 accepts the Taxonomy link the product cites

Status: in-review, builder J, `364e2b9`
Card: 5

Acceptance: both links resolve to taxonomy 562 live; only G-035's must-cite changed.

## Coverage: what this phase does not cover

- `plan.resource`: the plan makes no runtime choice between tools today, so nothing was wired; builder J's report says where it would go.
- Moving the reworded-sentence model check to Jev: excluded by the product owner's decision of 2026-09-23, which names that exception and forbids widening it without sign-off.
- The writer bench (card 10's measurement): run separately, costed against the night's spend.

## History

- 2026-09-25 05:05 UTC: builder D dispatched for the seam, in parallel with phase 8.1.
- 2026-09-25 about 06:45 UTC: builder J dispatched for the wiring on a base carrying phase 8.1's work.
- 2026-09-25 about 08:30 UTC: builder J done; the fence crossing into `harness/jev_client.py` (`52b6890`) accepted by the lead: the models were never told what each decision meant, which is why pizza was first admitted.

## Findings

Written the moment a finding is established.
