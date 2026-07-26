# Build workflow cadence

The loop one build phase runs, who does each step, and which model runs it. This is the quick reference. The visual version is `docs/Phase_6_execution_flow.html`, and the full detail lives in `.claude/skills/bossman-mode/SKILL.md`.

The loop repeats 26 times, once per build phase in `requirements/Technical_specification.md` section 25.

Last updated: 2026-07-26.

## Table of contents

- [The one-paragraph version](#the-one-paragraph-version)
- [The eleven stages](#the-eleven-stages)
- [Model assignment](#model-assignment)
- [Where everything is written](#where-everything-is-written)
- [The two verification halves](#the-two-verification-halves)
- [Known weak points](#known-weak-points)

## The one-paragraph version

It runs like a normal engineering team. Tickets get read, picked up, worked, and moved across a board as they progress. Agents verify the engineering: does it work, is it correct, is it safe to ship. The product owner verifies the product: is this the right thing, and does it meet the user need. Nothing merges without that second check.

## The eleven stages

| # | Stage | Who | Model | Effort |
|---|-------|-----|-------|--------|
| 1 | Open the phase: read section 25, verify dependencies merged | Lead | Opus 5 | high |
| 2 | Read `LEARNINGS.md` filtered to this phase | Lead | Opus 5 | low |
| 3 | Decompose into tickets with acceptance criteria and file scopes | Lead | Opus 5 | high |
| 4 | Cut the branch, dispatch researchers | Lead, researchers | Opus 5 lead, Haiku 4.5 research | low |
| 5 | Builders work tickets in parallel | Builders | Sonnet 5 | medium |
| 6 | Record what broke, at the moment it breaks | Whoever hit it | inherits its own | n/a |
| 7 | Judge grades with cited evidence, closes tickets | Judge | Opus 5 | high |
| 8 | Adversary attacks what the judge certified | Adversary | Opus 5 | high |
| 9 | Gates: verify, eval-harness, dev-standards, release-workflow | Lead, test writer | Opus 5 lead, Sonnet 5 tests | medium |
| 10 | Close the board, render, republish, open the pull request | Lead | Opus 5 | low |
| 11 | Review and merge | Product owner | human | n/a |

## Model assignment

The rule: spend reasoning where a mistake is expensive and cascades, spend cheaply where the task is bounded and the instructions are clear.

| Role | Model | Effort | Why this tier |
|------|-------|--------|---------------|
| Lead, planning and decomposition | Opus 5 | high | A bad split cascades into every builder downstream. This is the most expensive place to be wrong |
| Lead, mechanical steps | Opus 5 | low | Same session, but branch cutting and board closing need no reasoning. Keep the lead thin |
| Researcher, bulk reading | Haiku 4.5 | low | The cost is input tokens, not reasoning. Reading an API doc does not need a frontier model |
| Researcher, analysis | Sonnet 5 | medium | When the research needs a judgment, not just a summary |
| Builder | Sonnet 5 | medium | Well-scoped construction against clear acceptance criteria. Reserve high effort for genuinely hard builds |
| Sub-planner | Opus 5 | high | Same cascade risk as the lead's own decomposition |
| Judge | Opus 5 | high or xhigh | A missed defect here is the most expensive thing in the loop, because it ships |
| Adversary | Opus 5 | high | Finding a fluent, plausible, wrong answer needs real adversarial reasoning. A cheap model will not find what the judge missed |
| Test writer | Sonnet 5 | medium | Bounded work against a finished artifact |
| Integrator | Sonnet 5 | medium | Wiring, only dispatched when builders produced isolated pieces |

Two notes on this table:

- These are build-time models, the agents that write System 3. They are a separate concern from the product's own guard, plan, and synth runtime tiers, which route models per user query at serve time and are chosen by model-bench at build phase 7.0. Do not conflate the two.
- Delegation has a fixed setup cost, so do not shard a phase into many tiny tasks just to parallelize. Each dispatched agent should carry a task worth its overhead.

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
- Playwright is not installed, so the UI gate on build phases 1.2 and 4.5 has nothing behind it yet.
