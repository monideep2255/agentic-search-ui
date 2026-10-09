# Card 53 builder report

Branch `fix/card53-stale-facts`, finished on 2026-09-29 after the builder was stopped on 2026-09-27. `origin/develop` was merged in with no conflicts (merge commit `383b53bf`). Nothing was pushed.

## Table of contents

- [Fact table](#fact-table)
- [Fixes made in this session](#fixes-made-in-this-session)
- [Gate results](#gate-results)
- [Not done](#not-done)

## Fact table

Every correction was read against the code it describes. The last column names the registry fact in `.claude/skills/verify/scripts/facts_registry.py` that guards it, or says so when nothing does.

| Stale fact | Corrected at | Commit | Checked against the code | Guard |
|------------|--------------|--------|--------------------------|-------|
| CLAUDE.md and AGENTS.md name LitSense and omit PubChem, Datasets and Pathogen Detection from layer 2 | `CLAUDE.md:45-46`, `AGENTS.md:45-46` | `74bfed6f` | `tools/ncbi_transport.py` `_LAYER_BY_FAMILY`: eutils, datasets, pubchem, variation are layer 2; pubtator, litvar2, clinicaltrials are layer 3. Pathogen Detection declares layer 2 in its own module. Nothing in `src/` calls LitSense | `layers.l2_apis`, `layers.l3_apis` (instruction files) |
| README layer table names LitSense and omits the same layer 2 sources | `README.md:120-121` | `509d7792` | same as above | `layers.l2_apis`, `layers.l3_apis` (README rows) |
| KGX manifest layer note carried the old lists | `src/system_03_search_agent/export/manifest.py:70` | `01ac62ed` | same as above | `layers.l2_apis`, `layers.l3_apis` (manifest downstream) |
| A code docstring still counted four layer 3 APIs including LitSense | `src/system_03_search_agent/tools/pathogen_detection.py:1483` | `9a53a903` (this session) | CLAUDE.md now names three | none (a comment) |
| Architecture diagram and deep dive said Plan and Act make no model call | `visualizations/Architecture_diagram.md:83-84,108-109`, `visualizations/System_3_deep_dive.md:73-74,472` | `2310b925`, `7b26c987` | `core/graph.py`: Act reaches the plan and guard tiers (Cypher writing, article titles). Plan calls no tier of its own but reads `_literature_choice` (`graph.py:1301`, called at `graph.py:6283` only when no gene resolved, with `ask_if_missing=True`) | `loop.plan_on_plan_tier`, `loop.act_on_plan_tier`, `loop.act_on_guard_tier`, `loop.plan_asks_no_model` |
| README, CLAUDE.md and AGENTS.md said what the plan tier does | `README.md:144`, `CLAUDE.md:53`, `AGENTS.md:53` | `509d7792`, `74bfed6f` | as above | `loop.plan_on_plan_tier` |
| Architecture diagram and deep dive said the graph budget is 90 s | `visualizations/Architecture_diagram.md:131,165`, `visualizations/System_3_deep_dive.md:363` | `2310b925` | `tools/graph_schema_constants.py:208`, `CYPHER_QUERY_TIMEOUT_SECONDS = 30.0` | `budget.graph_query_s` |
| `tools/catalogue.py` said 30 s for the graph | `src/system_03_search_agent/tools/catalogue.py:123` | already 30.0 on develop | matches the constant above | `budget.graph_query_s` (catalogue downstream) |
| `tools/catalogue.py` said 60 s for Pathogen Detection where the code enforces 120 s | `src/system_03_search_agent/tools/catalogue.py:141` and the test at `tests/system_03_search_agent/tools/test_catalogue.py:90` | `0eb3ca83` (this session) | `tools/pathogen_detection.py:284`, `_TOTAL_BUDGET_S = 120.0`. Diagnosis: `.claude/rules/tool-call-budgets.md` says "60 seconds or more", a floor. The catalogue copied the floor | `budget.pathogen_s` (catalogue downstream) |
| Catalogue live-tool budgets | `catalogue.py` | unchanged, already right | `ncbi_transport.py:338`, `DEFAULT_TIMEOUT_S = 15.0` | `budget.live_call_s` |
| About walk said a question "starts here" at layer 1 | `frontend/src/components/screens/InfoScreens.tsx:933` | `aa7cc3a1` | `core/graph.py:7859`, `_gather_planned_calls` awaits every planned call with `asyncio.gather` | `loop.layer_one_read_first` (four page rows) |
| Layer 3 called "never by default" and "when the question asks for it" | `InfoScreens.tsx:950,1201`, `ArchitectureScreen.tsx`, `architectureFacts.ts` | `aa7cc3a1` | `core/graph.py:4551`, `_build_layer_tool_calls`: PubTator3 and ClinicalTrials.gov on the gene symbol, or on the disease's MedGen name when no gene resolved, and LitVar2 per rs id (at most two). No decision or request gates them | `layers.l3_in_code` |
| Eight page claims were unchecked because the patterns looked for sentences phase 8.10 replaced | `.claude/skills/verify/scripts/facts_registry.py`, `check_facts.py` | `a470c82e` | The registry now matches the new sentences. New or rewritten facts: `layers.l3_in_code`, `events.client_types`, `loop.act_on_plan_tier`, `loop.act_on_guard_tier`, `seeds.count`. `check_facts.py` counts `call_jev_batch` as a classifier call | the checker itself; `--self-test` proves each check can fail |
| Client's known event list left out `step` without saying why | `frontend/src/lib/events.ts`, comment in `InfoScreens.tsx` | `355b410e` | `contracts/events.py:670` includes `step` | `events.client_types` |
| README "node 18+" | `README.md:72` reads "node 22+" | `6e8d0300` (on develop, 2026-09-26) | `frontend/package.json` engines `"node": ">=22"` | none |
| README "no release has been cut yet" | removed; the release section names the changelog and releases | `6e8d0300` (develop) | `gh release list` shows v0.2.0 latest, v0.1.2, v0.1.1 | none |
| README "CI is advisory" now that rulesets protect develop | `README.md:62-63` | `6e8d0300`, `465c5a6b` (develop) | The two active rulesets carry `update`, `pull_request`, `deletion`, `non_fast_forward` and no required status check, so "still advisory" is true | none |

Also on the branch, no fact: `b27afce1` moves the architecture diagram's last-updated line, `fbaee957` indexes the doc readability runs log.

Facts corrected: 17 of 17 rows above that name a stale fact, and every one now matches its code. Three of them (README node engine, release, advisory CI) landed on develop before this branch and have no checker line.

## Fixes made in this session

- `0eb3ca83`: `catalogue.py` now says 120.0 for Pathogen Detection with a comment giving the reason, and the catalogue test asserts 120.0. Before it, the facts checker exited 1 with `FAIL | budget.pathogen_s | code copy | says "_PATHOGEN_DETECTION_BUDGET = ( 60.0" | true: 120`.
- `9a53a903`: the docstring in `pathogen_detection.py` names three layer 3 APIs.

## Gate results

| Gate | Command | Result |
|------|---------|--------|
| Facts checker | `check_facts.py` with the repository venv, against the local files | `facts: 67 | stale 0 | not fully checked 0 | places: PASS 202, FAIL 0, GAP 0, ERROR 0 | PASS`, exit 0 |
| Facts checker self-test | `check_facts.py --self-test` | `202 of 202 comparisons proven to pass and to fail; 67 of 67 readers proven to follow a changed source; 10 parser cases; 0 failures` |
| Frontend tests for touched files | `npx vitest run` on the Architecture, About, Integrations, events and events.persona tests | `Test Files  5 passed (5)`, `Tests  63 passed (63)` |
| Frontend build | `npm run build` | exit 0 (`built in 178ms`, one chunk size warning, not new) |
| Unit suite | `.github/gates/gate04_unit_suite.sh` | `6501 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 281.20s`, exit 0 |
| Lint | `ruff check .` | `All checks passed!` |
| Import order | `.github/gates/gate02_import_order.sh` | exit 0 |
| Doc drift | `python3 tracker/check_doc_drift.py --check` | `ok: 2 facts computed | 0 could not be computed | 0 stale | 0 structural`, exit 0 |

The frontend tests ran only for the four files the branch touched, as asked, not the whole vitest suite. No request was made to the deployed apps.

## Not done

- The README node engine, release and advisory-CI corrections have no line in the facts registry, so a later drift would not be caught. Adding one is a design choice, since the source for "a release exists" is GitHub, which the checker does not call.
- `docs/architecture/Three_layer_data_architecture.md:127` still lists LitSense as a layer 3 API. It is a design document and LitSense is a planned source (card 44, DECISIONS.md 2026-09-25), so it was left alone.
- `testing/UI_fix_plan.md` was not touched: closing card 53 and the pull request are the lead's.
