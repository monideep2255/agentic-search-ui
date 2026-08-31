# Build phase 5.3: golden dataset schema v2, layer-reach constraints

Branch: `phase/5.3-golden-dataset-schema-v2`. Opened 2026-08-31.

Not a Section 25 row. This phase exists because of a product-owner review of build phase 5.1's merged dataset on 2026-08-31, in the same way build phase 5.2 was carved out of 5.1 rather than named by Section 25. Depends on 5.1, merged as PR #85.

## Table of contents

- [What this phase is for](#what-this-phase-is-for)
- [The measurement that opened it](#the-measurement-that-opened-it)
- [Everything measured before any change was made](#everything-measured-before-any-change-was-made)
- [What this phase must not do](#what-this-phase-must-not-do)
- [The independence rule this phase can most easily break](#the-independence-rule-this-phase-can-most-easily-break)
- [Goal contract](#goal-contract)
- [Tickets](#tickets)
- [Coverage: what this phase does not cover](#coverage-what-this-phase-does-not-cover)
- [Findings](#findings)
- [History](#history)

## What this phase is for

Build phase 5.1 shipped 50 questions whose constraints were read from live NCBI lookups. Nothing in those constraints can require that the agent actually called a live API.

This phase makes that requirement expressible. It does not author the questions that would use it, and the distinction is the whole scope boundary: the mechanism is ours, the content is not (see [What this phase must not do](#what-this-phase-must-not-do)).

## The measurement that opened it

Measured across all 50 merged rows on 2026-08-31, before any change:

| Tool | Rows that require it |
|---|---|
| `litvar2_lookup` | 0 |
| `pubtator_annotate` | 0 |
| `clinicaltrials_search` | 2 (G-012, G-030) |
| `pathogen_detection` | 2 |

Read alone, that is thin coverage and more questions would fix it. It is not the defect.

THE DEFECT IS THAT THE SCHEMA CANNOT EXPRESS THE REQUIREMENT AT ALL. The only constraint fields are `must_resolve` and `must_cite`, and `must_cite` pins a URL. A citation to `ncbi.nlm.nih.gov/gene/672` is satisfiable straight from the Layer 1 graph node's own `source_url` with no live call ever made, so the eight rows citing PubMed and the four citing dbSNP can all be passed by an agent that only ever read the graph. Adding twenty Layer 2 and Layer 3 questions would have changed none of that.

The dataset could not distinguish an agent that federated three layers from one that read the graph and stopped.

## Everything measured before any change was made

Measured 2026-08-31 at the branch point, on `develop` at `332da84`.

| Fact | Value | How |
|---|---|---|
| Branch point | `332da84` | `git rev-parse --short HEAD` |
| Doc drift | 0 stale, 0 structural, 10 facts computed | `python tracker/check_doc_drift.py --check` |
| Transports | product-model ok 851ms, harness-model ok 95ms, graph ok 934ms via the HTTPS query service | `python3 tracker/preflight.py` |
| Python tests | 4652 | `check_doc_drift.py` |
| Frontend tests | 235 | `check_doc_drift.py` |
| Golden rows | 50, schema `version: 1` | `eval/golden/golden_dataset.json` |
| Graph snapshot label | `ncbi_kg_v1_2026-04-22` (the `_DEFAULT_GRAPH_SNAPSHOT_VERSION` fallback) | `cypher_query.py:237` |

THE GRAPH IS REACHABLE FROM THIS SESSION. That is what makes ticket T-5.3-03 buildable as a measurement rather than as an inference, and if it stops being true mid-phase that ticket's blocked-stop applies.

## What this phase must not do

It authors NO new questions, and adds NO new rows to the dataset. Product-owner decision, 2026-08-31, logged in `DECISIONS.md`: the 50 questions are a data-derived v1, and the settled set is data plus subject-matter-expert input. Authoring twenty new Layer 2 and Layer 3 questions now would aim precision at the same moving specification that got build phase 5.2 parked, one file over.

The deliverable is therefore a better SPECIFICATION LANGUAGE, not better coverage. Nothing in this phase closes the coverage gap in the table above; it makes the gap sayable so that when SME review lands, the right constraints can be written down. Any report of this phase that claims coverage improved is wrong.

## The independence rule this phase can most easily break

`eval/golden/build_dataset.py` verifies every constraint against live E-utilities over raw HTTP, deliberately touching none of the agent's own tool layer. Its docstring explains why at length. Build phase 5.2 then rebuilt the identical circularity one file over, and it is the root defect that parked that phase: a grounding check compared the agent's prose against the agent's own citation payload, so an answer about a gene that does not exist, citing a record that does not exist, scored 16 of 16.

The general form recorded in `LEARNINGS.md`, 2026-08-30: when you build an independent verification path for one component, write down what made it independent, then check every neighbouring component against that same definition. Knowing the principle did not transfer; only re-applying it deliberately would have.

Re-applying it here, explicitly, because T-5.3-03 is exactly where it would break again:

- The builder may reach the graph query service over RAW HTTPS, the same way it already reaches E-utilities over raw HTTPS.
- The builder may NOT import or call `cypher_query`, `graph_connection.execute_cypher`, or any other module under `src/system_03_search_agent/tools/`. Doing so would make the dataset's own verification depend on the machinery the dataset exists to grade.

A reviewer should treat any import from `system_03_search_agent` inside `eval/golden/` as a finding on sight.

## Goal contract

Done when: a golden row can state, and the loader can enforce, that answering it requires a live Layer 2 or Layer 3 call, by two independent mechanisms, with the second protected against silently becoming false.

- `must_reach`: names the tools a row requires. Grades the retrieval path. Countable per tool.
- `live_only`: names a fact whose value the Layer 1 graph does not contain. Grades the answer. Cannot be satisfied by a graph-only agent.

Verify (immutable for the run; checks may be added, never weakened):

1. A premise gate under `tests/system_03_search_agent/eval/`, every arm paired with a named mutation APPLIED by a harness in the same edit as the arm, not merely named in a comment. Build phase 4.3 shipped five vacuous arms whose mutations were named and never run.
2. The builder REFUSES a `live_only` fact that the live graph already contains, proven by a mutation that plants a graph-satisfiable fact and requires the build to fail.
3. The loader REFUSES a `must_reach` naming a tool outside the seven-tool roster, and refuses a `live_only` block missing any required key.
4. Every one of the 50 existing rows survives the schema change with its meaning unchanged, proven by diffing the v1 and v2 rows field by field, not by the suite staying green.
5. `python tracker/check_doc_drift.py --check` clean, `ruff check` clean over the WHOLE repository (gate 3 takes no path; build phase 4.15 lost five errors to a narrower local command), `isort --check-only` clean (build phase 5.0 lost gate 2 because `/verify` does not run it).

Output: `must_reach` and `live_only` in `eval/golden/question_set.py` specs and `build_dataset.py` rows; validation in `src/system_03_search_agent/eval/dataset.py`; `golden_dataset.json` regenerated at `version: 2`; the premise gate and its mutation harness; this file; the SME content note recorded in the continuation prompt's open items and on the board.

Constraints:

- No new questions, no new rows. See [What this phase must not do](#what-this-phase-must-not-do).
- No import from `system_03_search_agent` inside `eval/golden/`. See the section above.
- No existing validation weakened to accommodate the new fields.
- A row without `must_reach` or `live_only` stays valid. Both fields are optional and additive, so schema v2 is backward compatible and the 50 existing rows need no edit.

Blocked-stop:

- If the graph query service is unreachable, T-5.3-03 cannot be built as a measurement. STOP on that ticket and report; do not substitute date arithmetic against `GRAPH_SNAPSHOT_VERSION` and call it equivalent. The date is a hand-maintained env fallback that nothing re-reads from the graph, so it can be stale in exactly the case the check exists to catch.
- If a `live_only` candidate cannot be shown absent from the graph, the row does not get the field. Do not relax the check to admit it.

## Tickets

| Ticket | What | Acceptance | Status |
|---|---|---|---|
| T-5.3-01 | `must_reach` on specs, carried into rows by the builder | Loader refuses a tool name outside the seven-tool roster; the roster is pinned in ONE place, not copied | todo |
| T-5.3-02 | `live_only` field: the fact, its value, its live source | Builder verifies the value against live E-utilities over raw HTTP, reusing the existing verifier machinery | todo |
| T-5.3-03 | Builder refuses a `live_only` fact the GRAPH already contains | A planted graph-satisfiable fact makes the build FAIL. Raw HTTPS to the graph service only, no agent-tool import | todo |
| T-5.3-04 | Snapshot-date secondary guard, and its limits stated | Parses the date from `GRAPH_SNAPSHOT_VERSION`; the coverage statement says plainly that this is only as current as the env var, and that T-5.3-03 is the real check | todo |
| T-5.3-05 | Schema `version` 1 to 2, loader accepts both | All 50 existing rows load unchanged under v2, proven field by field | todo |
| T-5.3-06 | Premise gate plus applied-mutation harness | One mutation case per arm, added in the same edit as the arm; every arm goes red under its own mutation | todo |
| T-5.3-07 | Record the SME content boundary where a later reader will look | Present in the continuation prompt's open items table and on `tracker/BOARD.md`, with an owner | todo |

## Coverage: what this phase does not cover

Stated here rather than left to be inferred, per `goal-contracts`: a verify surface must state its own coverage or a gap in it is not arguable.

- NOTHING CHECKS `must_reach` AT GRADING TIME. Verifying that `litvar2_lookup` was actually called means reading tool calls out of a trace, which is `replay()`'s job, and `replay()` refuses to run without `acknowledge_parked=True`. This phase makes the constraint expressible and enforces its SHAPE; it does not make it graded. That happens when build phase 5.2 is unparked.
- No row in the shipped dataset uses either new field when this phase closes, because no new questions are authored. The fields are exercised by fixtures in the gate, not by production rows.
- The `live_only` shelf life is bounded by T-5.3-03 at BUILD time only. A System 1/2 re-ingest between two builder runs makes a shipped row graph-satisfiable, and nothing re-checks it until the builder runs again. The refresh trigger is a re-ingest, and this repository does not control or observe one.
- Nothing here improves per-tool coverage. See [What this phase must not do](#what-this-phase-must-not-do).

## Findings

| Finding | Severity | What | Status |
|---|---|---|---|

## History

- 2026-08-31: opened. Branch cut from `develop` at `332da84`. Preflight green on all three transports. Baseline: 4652 Python tests, 235 frontend, 50 golden rows at schema v1, 0 doc drift.
