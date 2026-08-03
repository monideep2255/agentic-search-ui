# Build workflow cadence

The loop one build phase runs, who does each step, and which model runs it. This is the quick reference. The visual version is `docs/build/Phase_6_execution_flow.html`, and the full detail lives in `.claude/skills/bossman-mode/SKILL.md`.

The loop repeats 26 times, once per build phase in `requirements/Technical_specification.md` section 25.

Last updated: 2026-08-02.

## Table of contents

- [The one-paragraph version](#the-one-paragraph-version)
- [The twelve stages](#the-twelve-stages)
- [Stage 5, the premise gate, and why it blocks](#stage-5-the-premise-gate-and-why-it-blocks)
- [Model assignment](#model-assignment)
- [Effort and tier basis, measured 2026-08-02](#effort-and-tier-basis-measured-2026-08-02)
- [Provider mapping](#provider-mapping)
- [Where everything is written](#where-everything-is-written)
- [The two verification halves](#the-two-verification-halves)
- [Known weak points](#known-weak-points)

## The one-paragraph version

It runs like a normal engineering team. Tickets get read, picked up, worked, and moved across a board as they progress. Agents verify the engineering: does it work, is it correct, is it safe to ship. The product owner verifies the product: is this the right thing, and does it meet the user need. Nothing merges without that second check.

## The twelve stages

| # | Stage | Who | Tier | Effort |
|---|-------|-----|------|--------|
| 1 | Open the phase: read section 25, verify dependencies merged | Lead | balance | medium |
| 2 | Read `LEARNINGS.md` filtered to this phase | Lead | balance | low |
| 3 | Decompose into tickets with acceptance criteria and file scopes | Lead | depth | high |
| 4 | Cut the branch, dispatch researchers | Lead, researchers | balance lead, speed research | low |
| 5 | Write the premise gate and WATCH IT FAIL. Blocks stage 6 | Lead | depth | high |
| 6 | Builders work tickets in parallel | Builders | balance | medium |
| 7 | Record what broke, at the moment it breaks | Whoever hit it | inherits its own | n/a |
| 8 | Judge grades with cited evidence, closes tickets | Judge | depth | high or extra high |
| 9 | Adversary attacks what the judge certified | Adversary | depth | high |
| 10 | Gates: see the breakdown below the table, they are not all run on the same schedule | Lead, test writer | balance | medium |
| 11 | Close the board, render, republish, open the pull request | Lead | balance | low |
| 12 | Review and merge | Product owner | human | n/a |

Five of these ten model-driven stages ran at `high` or `extra high` effort and seven ran on the `depth` tier before 2026-08-02. Both numbers dropped. See "Effort and tier basis" below the model assignment table for the measured reason and per-stage reasoning.

Stage 10 names four gate skills, and they are not interchangeable items on one checklist. Measured against `tracker/phase_*.md` across the five build phases completed so far (1.0, 1.1, 2.0, 1.2, 2.1):

- `release-workflow` is mandatory at every phase end per the bossman-mode rule's "Skill chain at phase end: release-workflow -> ship (mandatory, no skips)". Measured dispatch count: 0 of 5 phases. This is a real gap between what the rule requires and what has actually run, not a gate this document is dropping. Not-yet-exercised, and the gap is stated here so it stays visible.
- `verify` is the pre-commit check (Python compile, tests, lint, git status) that `release-workflow` calls as part of its own local-verify step. Measured dispatch count: 1 of 5 phases (build phase 2.0). Runs whenever `release-workflow` runs, so its own gap tracks the release-workflow gap above.
- `dev-standards` is the six-lens production readiness review, invoked for a full readiness check rather than on every phase automatically. Measured dispatch count: 1 of 5 phases (build phase 1.2).
- `eval-harness` is required before shipping any answer-generation feature, per the AI answer grounding gate in `production-standards.md`. Measured dispatch count: 0 of 5 phases, which is expected rather than a gap: none of the five completed phases shipped answer generation. The trigger is build phase 2.2, deterministic cite-or-refuse, the next phase in the sequence.

## Stage 5, the premise gate, and why it blocks

Added 2026-08-01 after build phase 2.1 failed four consecutive reviews with
a green suite. This stage is mandatory and blocking for any phase whose
deliverable is model-generated output. That property currently names build
phase 2.2 (deterministic cite-or-refuse over model-generated synthesis) and
every remaining tool phase, 3.1 to 3.5. No tool code is written until the
gate exists and has been seen failing.

What phase 2.1 cost, stated plainly because it is the argument for the
stage: a fully green suite, and 3 of 8 real questions answered correctly.
The worst case returned twenty-five non-human orthologs for "which diseases
are associated with BRCA1?", `status="ok"`, every row carrying a real and
resolving NCBI citation. Five review rounds found roughly 25 real defects,
none of them the cause. The cause was a schema slice that handed the
generator no Disease label at all, and it was visible from day one to
anyone who printed what the model was actually given.

A premise gate has four properties. Each one is there because its absence
was a measured failure in 2.1:

- It does NOT mock the model. Every other test in the suite does, which
  means every one of those tests supplied a query someone already knew was
  correct, and none of them could see a generation defect. The premise
  evidence lives in `tests/system_03_search_agent/tools/test_cypher_query_premise.py`,
  the one test file that calls the real model against pinned live ground
  truth rather than a mock.
- It asserts on the MEANING of the answer, not its shape. "Rows came back"
  and "every row is cited" both passed on the ortholog answer.
- Its ground truth is read from the live source and pinned, so "correct" is
  checkable rather than plausible.
- It runs the way PRODUCTION runs. A first draft of 2.1's gate hand-picked a
  `query_class` per question and scored 8 of 9, where sending the stub value
  production actually emits scored 3 of 9. A gate handed a better input than
  production sends is a fixture, not a gate.

It must also state its own coverage: which shapes of question it exercises
and which it omits. 2.1's gate could not see finding F-2.1-A5-03 because all
nine of its questions were one hop from a single anchor type, so a defect
making every two-hop question unanswerable was invisible to the gate built
to catch exactly that class. A gate with an unstated blind spot inherits the
blind spot of the code it grades.

Cost, measured on 2.1: about 40 minutes to write, and $0.013 per run for
eight real generations. Against ten review passes at 20 to 30 minutes each,
it pays for itself the first time it fires. It already has: two regressions
introduced by 2.1's own late fixes were caught by the gate rather than by a
sixth review round.

The reason it blocks rather than merely being required: a gate written after
the code it grades is written against behavior that already exists, and will
tend to encode that behavior as correct. Watching it fail first is what
proves it can fail at all.

## Model assignment

The rule: spend reasoning where a mistake is expensive and cascades, spend cheaply where the task is bounded and the instructions are clear.

| Role | Tier | Effort | Why this tier |
|------|------|--------|---------------|
| Lead, planning and decomposition (stage 3) | depth | high | A bad split cascades into every builder downstream. This is the most expensive place to be wrong |
| Lead, premise gate design (stage 5) | depth | high | The same cascading logic as decomposition, not a blanket carry-over: a weak premise gate reproduces the exact cost stage 5 exists to prevent, and its own coverage gaps are invisible to every test it grades. Build phase 2.1 shipped four consecutive failed reviews behind a green suite before this was found |
| Lead, phase-open verification (stage 1) | balance | medium | Bounded checking against a fixed document, does section 25 name this phase, did the dependency actually merge. A miss here surfaces fast, at build start, rather than compounding silently the way a bad decomposition does |
| Lead, routine steps (stages 2, 4, 11) | balance | low | Reading a filtered log, cutting a branch, closing a board. No reasoning, bounded, instructions already clear |
| Lead, gate execution and readiness call (stage 10) | balance | medium | Running a finished gate skill and reading its pass or fail output is checklist work against a defined bar, not open architectural judgment |
| Researcher, bulk reading | speed | low | The cost is input tokens, not reasoning. Reading an API doc does not need a frontier model |
| Researcher, analysis | balance | medium | When the research needs a judgment, not just a summary |
| Builder | balance | medium | Well-scoped construction against clear acceptance criteria. Reserve high effort for genuinely hard builds |
| Judge | depth | high or extra high | A missed defect here is the most expensive thing in the loop, because it ships. Measured on this repo: build phase 2.1 failed four consecutive judge and adversary reviews with a green suite before the real defect surfaced |
| Adversary | depth | high | Finding a fluent, plausible, wrong answer needs real adversarial reasoning. A cheap tier will not find what the judge missed |
| Test writer | balance | medium | Bounded work against a finished artifact |

The role list above once also carried a Sub-planner row and an Integrator row. Both are removed: across the five build phases completed so far (1.0, 1.1, 2.0, 1.2, 2.1), `tracker/phase_*.md` shows zero dispatches of either role. If either role is genuinely needed on a future phase, add it back with its first real dispatch as evidence.

Two notes on this table:

- These are build-time capability tiers, assigned to the agents that write System 3 itself. They are a separate concept from the product's own guard, plan, and synth runtime tiers, which route models per user query at serve time and are chosen by model-bench at build phase 7.0. Both are called tiers, but they name different things: one sizes the agent doing the building, the other picks the model that answers a live query. Do not conflate the two.
- Delegation has a fixed setup cost, so do not shard a phase into many tiny tasks just to parallelize. Each dispatched agent should carry a task worth its overhead.

## Effort and tier basis, measured 2026-08-02

Both tables above were re-tiered on this date from a prior default of `depth` and `high` on most roles. This section states the measurement behind that change and what would justify raising a rung back, so the next reader does not mistake a guess for a finding.

External evidence, on reasoning effort specifically:

- Dropping reasoning effort from high to medium gave 76 percent fewer output tokens at the same task-completion rate.
- Each effort rung costs roughly twice the rung below it.
- Thinking tokens reach up to 40 percent of total output spend, and they are replayed as input on every later turn in a session, so an unnecessarily high rung compounds across a whole phase, not just one call.

External evidence, on capability tier:

- A mid-tier model costs about 0.6 times a top-tier model and performs comparably on most development work.

Internal evidence, from this repo's own build. `LEARNINGS.md`'s 2026-07-31 entry on `harness/harness.py` tier configuration records that the plan tier, configured `effort: high`, spent 970 of 1014 output tokens on a single Cypher generation on reasoning rather than content. Measured over five failing query shapes, two runs each: `high` totalled 163.0 seconds with a worst case of 84.3 seconds on a multi-hop query, and dropping the same calls to `effort: none`, a rung below this ladder's own `low`, totalled 6.1 seconds with a worst case of 2.2. All five runs were correct at both settings, with neither setting ever writing an entity id as a literal. The entry calls this "a 27x latency multiple for no measurable quality" and states the general lesson directly: reasoning effort is a latency setting, not just a quality setting, and its cost is invisible in the response because reasoning tokens do not appear in the content.

That internal data point is narrower than the change made here: it proves `none` was safe for one bounded, fixed-schema Cypher generation, not that `medium` is safe for every role in this cadence. The external 76 percent figure is the direct evidence for the specific high-to-medium move applied to most roles below. Reading both together: the internal result is a strict superset of the claim actually needed, so it supports the change without overstating what was measured.

Per-role reasoning is recorded inline in the "Why this tier" column above rather than repeated here. The two roles that did not move, judge and adversary, share one justification: this repo has direct evidence that a weaker review costs entire rounds, not just latency. Build phase 2.1 failed four consecutive judge and adversary reviews behind a fully green test suite before the real defect was found, and the fifth pass found a defect class (every two-hop question unanswerable) that the phase's own premise gate could not see. Reasoning effort measurably changed neither the pass rate nor the citations on a bounded lookup task; it has not been measured against a review role's job, which is finding what a prior pass missed. The premise gate design step (stage 5) is treated the same way as decomposition for a stated reason, not by default: its own section above states that a first draft of a premise gate scored 8 of 9 against a hand-picked input and 3 of 9 against what production actually sends, and that its coverage gaps are invisible to the very tests it grades. That is the same cascading-cost shape as a bad decomposition, so it stays on `depth` and `high`.

What would justify raising a tier or a rung back: a specific, cited miss. A defect that a lower effort or tier demonstrably let through, recorded as a finding in a `tracker/phase_N.M.md` file or as a `LEARNINGS.md` entry naming the tier or effort setting as a contributing cause, the same evidentiary bar this section itself used to justify the cut. A feeling that a role "seems important" is not that bar. Per `goal-contracts`, this section is a verify surface for the tables above: weakening it back to a guess, rather than a fresh measurement, does not meet the bar it sets.

## Provider mapping

Two providers, three capability bands each, and an identical five-rung effort ladder. This table is the only place a provider name appears in this document. Every tier reference elsewhere, in the stage table and in the model assignment table above, points back to a row here.

| Tier | What it is for | Claude | Codex |
|------|-----------------|--------|-------|
| Depth | Architecture, hard debugging, long messy agentic work with many tradeoffs | Opus | Sol |
| Balance | Normal development work, bounded construction, careful checking | Sonnet | Terra |
| Speed | Quick lookups, extraction, classification, repetitive work | Haiku | Luna |

Effort ladder, identical on both providers: low, medium, high, extra high, max. Raise the rung as the task gets harder, low for quick and bounded work, max for the one hardest problem where maximum depth matters most.

Switching the harness to a different provider means editing this one table and nothing else. Nothing in the stage table, the model assignment table, or `Phase_6_execution_flow.html` names a product directly, so a provider swap is a single edit here, not a search-and-replace across every planning document. That indirection is the property that makes the harness portable.

## Where everything is written

| File | Holds | Written by | When |
|------|-------|-----------|------|
| `tracker/BOARD.md` | Phase index and status | Lead | Phase open and close |
| `tracker/phase_N.M.md` | Tickets and adversary findings | Lead, builders, judge, each on its own states | Continuously |
| `tracker/board.html` | The page the product owner reads | `tracker/render_board.py`, via hook | Automatically, on every board edit |
| `LEARNINGS.md` | What broke, what was tried, what fixed it | Whoever hit the problem | At the moment of failure |
| `DECISIONS.md` | Choices between alternatives | Lead | When a choice is made |
| Source and tests | The product | Builders | During the phase |
| PRD, tech spec, memo | The locked contract | Nobody | Frozen until step 6.2 |

## The two verification halves

The split that matters, and the reason both halves exist:

- Agents verify the engineering. The judge asks whether it works, whether it is correct, and whether it is safe to ship, and must produce cited evidence for every claim. The adversary asks whether it can be made to fail in a way nobody wrote a check for.
- The product owner verifies the product. Is this the right thing to have built, does it meet the user need, and on interface phases, does it actually feel right. No agent can answer that last one.

One nuance worth keeping straight: the adversary sits on the boundary. It hunts the confident wrong answer, which is an engineering failure in mechanism and a product failure in consequence. It belongs to the agent half because finding it is mechanical, but what it protects is the trust moat, which is a product concern.

## Known weak points

Stated rather than hidden, because each one is a place the cadence can quietly fail:

- A board edit made through a shell command instead of the Edit tool bypasses the sync hook and leaves the rendered page stale. Mitigated by re-rendering at phase close, not eliminated.
- The golden fixtures at build phase 5.1 have no named domain sign-off owner. If an expected answer is wrong, a wrong agent passes the gate, which is the exact failure the gate exists to catch.
- Playwright 1.62.0 shipped in build phase 1.2, with three passing end-to-end tests in `frontend/e2e/query-stream-and-stop.spec.ts`. The UI gate has something behind it as of that phase. Build phase 4.5 has not opened yet, so its own UI gate has nothing behind it until that phase runs.
- The premise gate at stage 5 is only as good as its question set, and nothing mechanically checks that the set covers the shapes a phase will actually be asked. Build phase 2.1's gate omitted every two-hop question and the omission was found by an adversary, not by the gate. Stating coverage is required; verifying that the stated coverage is complete is still a human judgment.
