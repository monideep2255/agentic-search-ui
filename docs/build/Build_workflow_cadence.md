# Build workflow cadence

Since 2026-09-25 the build loop is described in one home: `.claude/skills/bossman-mode/SKILL.md` and its four reference files. This document keeps the one table nothing else holds (the provider mapping) and points at where everything else went. From 2026-07-26 to 2026-09-25 it was the stage-by-stage quick reference; the build harness review of 2026-09-25 (D5) found the one loop described in seven files, 1,268 live lines, with one change to the premise-gate stage made in four of them.

Last updated: 2026-09-25.

## Where the cadence lives now

| What you are looking for | Read |
| --- | --- |
| The dial, the team and its tiers with the measurements behind them, the flow, the eleven stages with tier and effort, the budgets with their basis, where everything is written, the known weak points | `.claude/skills/bossman-mode/SKILL.md` |
| Opening, splitting and dispatching a numbered phase, the transport preflight table, the phase ledger and its dispatch table, the worker brief, the gates, the checkpoint | `.claude/skills/bossman-mode/reference/Phase_execution.md` |
| The judge, the adversary, the fix-and-verify round and the four review-loop rules | `.claude/skills/bossman-mode/reference/Review_rounds.md` |
| The product review, the golden consistency run with answered and answered well, and the answer-path premise check with its four properties | `.claude/skills/bossman-mode/reference/Product_review.md` |
| A card alone on develop, what the lead decides, how questions reach the owner | `.claude/skills/bossman-mode/reference/UI_fix_loop.md` |
| The loop as it stood on 2026-09-24, as a page, with a note at its top saying so | `docs/build/Phase_6_execution_flow.html` |
| Why the loop was redesigned on 2026-09-24 | `docs/build/Bossman_mode_redesign.md` |

## Provider mapping

What this section covers:

- Three providers
- Three capability bands each
- An identical five-rung effort ladder

This table is the only place a provider name appears in the cadence. Every tier reference in the skill and its reference files points back to a row here.

| Tier | What it is for | Claude | Codex | Alternate backend |
| --- | --- | --- | --- | --- |
| Depth | Architecture, hard debugging, long messy agentic work with many tradeoffs | Opus | Sol | See the local note |
| Balance | Normal development work, bounded construction, careful checking | Sonnet | Terra | See the local note |
| Speed | Quick lookups, extraction, classification, repetitive work | Haiku | Luna | See the local note |

Effort ladder, identical on all three providers:

- The five rungs: low, medium, high, extra high, max
- Raise the rung as the task gets harder
- `low` for quick and bounded work
- `max` for the one hardest problem where maximum depth matters most

The alternate backend is the metered fallback used when the primary provider's weekly budget is exhausted. Its model identifiers, prices and launch profiles are deliberately not written here, for two reasons:

- They name specific products and change monthly, which `writing-style` keeps out of tracked documentation
- Writing them here would make this table stale by design

They live in a local, uncommitted note instead, `docs/build/multi-model-harness/Multi_model_harness_plan.md`.

One constraint from that arrangement does belong here, because it governs the cadence itself rather than the configuration: the fallback is scoped by role, not applied to a whole phase.

- Stages assigned Depth for their judgement do not fail over: the lead's split, the judge, the adversary, the verifier and the product reviewer's judgement.
- A review run on the fallback records findings and closes nothing.
- The phase does not reach its merge until those stages have run on the primary provider, and the re-run counts against the 8 dispatches.

Switching the harness to a different provider means editing this one table and nothing else. Nothing in these three places names a product directly:

- The stage table, in `SKILL.md` under "The stages"
- The team table, in `SKILL.md` under "The team"
- `Phase_6_execution_flow.html`
