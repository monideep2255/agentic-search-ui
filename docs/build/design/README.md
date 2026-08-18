# Design

Everything build phase 4.8 is built against. This folder answers "what should it look like, and how does that become React code". For how a build phase runs at all, read `../Build_workflow_cadence.md` one level up.

Split out of `docs/build/` on 2026-08-12, when that folder hit its own nine-file revisit trigger. The cadence documents stayed put because they are referenced from 27 and 7 places respectively, including premise-gate tests and a publish script. Everything here was referenced from 2 to 6 places, all documentation, so it moved cheaply.

## Table of contents

- [Open this first](#open-this-first)
- [Reconciliation, closed 2026-08-18](#reconciliation-closed-2026-08-18)
- [The files](#the-files)
- [Which file answers which question](#which-file-answers-which-question)
- [The one thing not allowed to go stale](#the-one-thing-not-allowed-to-go-stale)

## Open this first

`design-system/prototype/app.html` is the whole product, clickable, in one file: disclaimer gate, landing, a question running through the five-step pipeline with tool chips landing live, the answer typing in with its provenance spine, source cards, feedback, the guest allowance, the login wall, and the Integrations and About pages. Four questions are canned end to end with different data-layer mixes.

It is also in the Claude Design project "NCBI Agentic Search" under the group `Prototype`, at `claude.ai/design`. That is where design changes originate. Everything in this folder is downstream of it.

## Reconciliation, closed 2026-08-18

Closed. Build phases 4.8, 4.9 and 4.10 have all merged, so the gate this section once held ("build phase 4.8 must not open until this is closed") no longer applies and has been removed rather than left standing, since a satisfied blocker that still reads as blocking is worse than no note.

What follows is the record of what the reconciliation covered, kept because the five uncarded surfaces below are the ones 4.9's fidelity pass worked from, and because the tool-name correction at the end has to be reapplied after every pull from Claude Design.

Five things existed in the prototype with no card at all:

| Needs a card | What it is |
|--------------|-----------|
| Reasoning trace | A collapsible, timestamped, per-step log of the agent's own reasoning, with the phase label coloured by data layer. Sits under the pipeline stepper during a run and folds into the completed answer's work panel |
| Result table | A bordered table rendered inside an answer, for structured results such as a genotype-to-phenotype mapping, with linked source cells |
| Conflict callout | An amber block reporting that two layers describe different things, distinct from the risk red |
| Answer sub-headings | Uppercase section labels that break a long answer into parts |
| Collapsed sources | The source list folded behind a summary carrying a count, rather than always expanded |

Three existing cards are behind the prototype: `components/source-card.html` (sources now collapse and their record rows are linked), `components/pipeline-stepper.html` (no reasoning panel), and `screens/answer.html` (no trace, no tables, sources not collapsed).

One correction is applied locally but not yet pushed to Claude Design, deliberately, because edits are in progress there and a write would clobber them. Three tool names shown in the prototype were not in the seven-tool roster and have been renamed to the tools that would genuinely make those calls: `medgen_lookup` and `pubmed_search` to `ncbi_efetch`, and `alfa_frequency` to `ncbi_dbsnp`, which already returns population frequencies. The rename is three deterministic string swaps and gets reapplied after the next pull.

## The files

| Path | What it is |
|------|-----------|
| `design-system/` | The fixture. 20 isolated component cards plus the prototype card, 21 files in all, mirrored to Claude Design |
| `Design_to_build_workflow.md` | How a design change travels from Claude Design into React code, and what it costs before versus after the phase opens. Read before touching anything else here |
| `Phase_4.8_visual_design.html` | The argument. Why the layer system is the identity, why flat, why one saturated surface, why monospace narrowed. Holds no component reproductions, so it cannot drift |
| `Phase_4.8_prototype.html` | Generated, do not hand-edit. The publishable form of the prototype |
| `make_prototype_artifact.py` | The generator behind the file above. Run it after every pull from Claude Design |

## Which file answers which question

| Question | File |
|----------|------|
| Does the whole thing feel right? | `design-system/prototype/app.html` |
| What exactly should this one component look like? | The matching card under `design-system/` |
| Why does it look like this? | `Phase_4.8_visual_design.html` |
| How does a design change reach the code? | `Design_to_build_workflow.md` |
| What does a builder build against? | `design-system/`, never the prototype |

That last row is the one people get wrong. A builder implementing the citation chip reads `design-system/identity/citation-chip.html`, because an isolated card is an unambiguous statement about one component in a way a running app never is. The prototype is where you decide whether the design is right, not where you read what it is.

## The one thing not allowed to go stale

`design-system/` is a fixture, not documentation. The build phase 4.8 premise gate asserts against it: token conformance against `foundations/colors.html`, structural checks that a citation chip carries a layer class and a source card renders all six provenance fields, WCAG 2.1 AA contrast on every token pair used, and an assembly check that every screen is reachable and renders from the real event stream. It does NOT do visual regression: a screenshot test was planned and deliberately never built, and pixel fidelity is the judge and adversary rounds' job. This line claimed the visual-regression gate until 2026-08-18, which advertised a gate nothing performed, the exact failure `Design_to_build_workflow.md` line 70 records deciding against.

Treat it the way you would treat a test's golden files. The prototype and the argument page are both allowed to lag, because nothing is checked against them. The cards are not.

Each card is standalone HTML carrying its own copy of the token block, so it renders correctly in isolation in the Claude Design pane, and its first line is a `@dsCard` marker naming its group. The token duplication across files is deliberate: a shared stylesheet would not survive isolated-card rendering.

Last updated: 2026-08-18
