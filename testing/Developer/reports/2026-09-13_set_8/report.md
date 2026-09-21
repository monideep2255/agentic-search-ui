# Set 8 report: search every layer, with the scientists

Builder: the set 8 sub-agent, 2026-09-13. Branch `develop`, working tree shared with the set 9 builder. Nothing here is committed; the main agent gates, commits and pushes.

Findings are appended the moment they are established, so the sections below grow in the order the work happened.

## Table of contents

- [Coordinator constraint received mid-task](#coordinator-constraint-received-mid-task)
- [Design decisions taken before coding](#design-decisions-taken-before-coding)
- [Files changed](#files-changed)
- [Verify commands](#verify-commands)
- [Live-run table](#live-run-table)
- [Design gap and token derivation](#design-gap-and-token-derivation)
- [Write-side needs for Layer 3 citations](#write-side-needs-for-layer-3-citations)
- [Proposed DECISIONS.md rows](#proposed-decisionsmd-rows)
- [Proposed hand-test changes](#proposed-hand-test-changes)
- [Tests whose requirement changed](#tests-whose-requirement-changed)
- [Left open](#left-open)
- [Layer 3 citation branch](#layer-3-citation-branch)

## Coordinator constraint received mid-task

Adding Layers 2 and 3 must not break item 10.1's rule of one citation source set per flagship question over five runs. So every Layer 2 and 3 call gets a deterministic input, every tool's rows are sorted by a stable key before a fixed cap, and the live-run table counts distinct source sets per question. Where a live API genuinely returns different records call to call, that is measured and reported, not hidden. The write side is not changed to filter citations.

Also asked and answered: the Agent tool is available to this builder; none was spawned.

## Design decisions taken before coding

Established from reading the code, before the first edit.

- Layer 3 rows are citeable through the EXISTING write-side builders without any write-side edit. `_citations_from_grounded_claims` has one special branch (`tool == "ncbi_efetch"`) and a generic branch for everything else that reads `synth_finding.source_url`, `layer` and `field` off the finding and builds a `CitationPayload`. `CitationPayload.source_url` is validated by `NCBI_SOURCE_URL_PATTERN`, which already admits `*.ncbi.nlm.nih.gov/...` (PubTator entity pages, PubMed pages, dbSNP pages) and `clinicaltrials.gov/study/...`. So a Layer 3 result shaped like the `ncbi_efetch` pseudo-row (`curie=""`, `node_or_edge_type`, `fields`, `source_url`) flows through `build_synth_findings` (which already skips the Layer 1 vocabulary-artifact check for non-Layer-1 rows) and is cited by the generic branch. What that branch produces for such a row: `source` = the tool name, `source_id` = `"unknown"` (empty CURIE), `evidence_kind="primary_assertion"`, `license="public_domain_us_gov"`. The last two are wrong for a ClinicalTrials.gov study (`provenance_defaults.defaults_for_tool("clinicaltrials_search")` carries the right values) and `source_id="unknown"` is poorer than the NCT id. That is a write-side improvement, recorded under "Write-side needs", not a blocker.
- The PubTator3 literature call is `entity_lookup` (the gene symbol, fixed `limit`), not `annotate_publications`. The tool has only those two modes; `annotate_publications` needs PMIDs, and the only in-repo source of PMIDs is the graph's Article rows, which the flagship disease question does not return and which would chain Layer 3 behind Layer 1. `entity_lookup` returns PubTator3's literature-derived entity record (gene page URL, name, description, biotype), deterministic for a fixed symbol. Stated plainly: this is the literature index entry for the gene, not a list of papers.
- ClinicalTrials.gov input is `query_cond` = the gene symbol uppercased, `page_size` fixed, and `overall_status = "RECRUITING"` only when the question text contains "recruit" (deterministic on the text). A model-extracted disease span is NOT used as the condition, because the span text varies between runs of the same question and that would change the source set. The tool requests `sort=@relevance`, which is not stable across runs, so rows are re-sorted by `nct_id` before the cap.
- `ncbi_dbsnp` and `litvar2_lookup` are planned only when an rs id is written in the question (`_RSID_PATTERN`), the one variant shape the pre-pass already resolves. "Clinically significant variants in CFTR" names no variant, so those two do not run for it, and the variant evidence comes from Layer 1's ClinVar rows.
- A disease resolved only as a typed `MedGen:` CURIE gets no Layer 2 or 3 call: no name is available without a lookup and the PubTator and trials inputs take text. `test_plan_selects_only_cypher_query_for_a_disease_anchored_query` keeps its meaning.
- The four Layer 2/3 tools are called through module-level names in `core/graph.py` (`ncbi_dbsnp`, `pubtator_annotate`, `litvar2_lookup`, `clinicaltrials_search`) looked up at call time, the same seam `ncbi_efetch` and `cypher_query` already use, so tests fake them with `monkeypatch.setattr(graph_module, ...)`.
- Helper persona names ride on `ToolCall` (plan event) and on `ToolStartPayload` (so also on `tool_result`), all optional with default `None`, additive within v1. They are never copied onto a `Finding` and so cannot reach the synthesis prompt; a test asserts it.
- The GCK fallback candidate rule, since no stopword list exists in `src/` and build phase 4.7 retired hand-maintained token lists from this path on purpose: a word-bounded token of 2 to 8 letters and digits qualifies only if it contains a digit (`brca1`, `tp53`, `c9orf72`) or is entirely upper-case letters (`GCK`, `CFTR`, `MODY`). An all-lowercase all-letter token (`gck`, `in`, `causing`) and a Title-case or mixed-case token without a digit (`Variants`, `Which`) are never tried. Tokens inside an exact-identifier span (`NCBIGene:672`, `rs334`, `PMID 123`) are excluded. At most three candidates, in question order. Residual, stated: `variants in gck causing mody` in all lowercase still resolves nothing.

## Files changed

- `src/system_03_search_agent/contracts/events.py`: `ToolCall` and `ToolStartPayload` (so also `ToolResultPayload`) gain optional `persona`, `persona_about`, `persona_wikipedia`, default None, additive within v1.
- `src/system_03_search_agent/core/persona.py`: `draw_helpers(lead_name, count=3, rng=None)`, three distinct helpers excluding the lead, `random.SystemRandom` by default, seedable for tests; `HELPER_COUNT`.
- `src/system_03_search_agent/core/graph.py`: `_PlannedLayerToolCall` plus per-tool Act timeouts and the fixed row cap; `_layer_tool_executor` (call-time lookup, fakeable); `_layer_tool_output_to_structured_fields` (source-url-only rows, stable sort, fixed cap, ok-to-empty downgrade); `_build_layer_tool_calls` and `_rsids_in_text` (deterministic inputs); `_assign_helpers`; `plan_node` plans Layers 2 and 3 for a resolved gene and an rs id, stamps helpers, names layers and tools in the narrative; `act_node` rewritten around `_execute_planned_call`, `_CallOutcome` and the `_gather_planned_calls` seam: admission in plan order, every `tool_start` before dispatch, concurrent execution, each `tool_result` closed as it lands, lists reassembled in plan order; the GCK fallback (`_gene_shaped_fallback_candidates`, `_confirm_fallback_candidates`) in `think_node`.
- `tests/system_03_search_agent/core/test_layer_handoff.py`: new, 20 arms including three mutation arms (sequential dispatch, emptied extractor, a draw that includes the lead).
- `tests/system_03_search_agent/core/test_graph.py`, `tests/system_03_search_agent/core/test_run.py`: seven assertions updated from two planned calls to four; autouse `_stub_layer3_dispatch` fixture.
- `frontend/src/lib/events.ts`: optional persona fields on `ToolCall` and `ToolStartPayload`, guarded by `hasOptionalPersonaFields`.
- `frontend/src/hooks/useRunView.ts` (set 9's file, one localized edit in the tool-chip loop, re-read first): the chip list is an upsert keyed on `call_id` carrying `status` and the persona trio; before, the first frame won and a chip read "running" for the life of the run.
- `frontend/src/components/screens/RunProgress.tsx`: `ToolCall` grows optional `status` and persona fields; `deriveHandoff`, `handoffSentence`, `HANDOFF_NARRATIVE`; the lead's Act caption reads the handoff sentence; the handoff block with per-layer badge and `PersonaInfo`.
- `frontend/src/components/shell/PersonaChip.tsx`: `PersonaCaption` takes an optional `narrative` override.
- `frontend/src/components/screens/RunProgress.handoff.test.tsx`, `frontend/src/lib/events.persona.test.ts`, `frontend/src/hooks/useRunView.handoff.test.ts`: new.
- `testing/Developer/scripts/local_loop_run.py`: additive flags `--no-memory` and `--summary` (see the live-run section); its four pre-existing ruff errors (three import blocks, one blind except) fixed on the coordinator's instruction, so `ruff check .` is clean for the whole repository.
- `src/system_03_search_agent/core/state.py`: additive `layer3_raw_outputs` key on `GraphState`, set by `act`, the typed output of each Layer 3 (and dbSNP) call by call_id, for the approved write-side citation branch.
- `tests/system_03_search_agent/core/test_cq_routing_mutation.py`: the P2 "resolves nothing" mutation now empties both the model's spans and the lookup (the fallback confirms BRCA1 otherwise), and a new arm pins that the fallback is what keeps P2 green under an empty extraction.

## Verify commands

Each run on its own exit code, never piped into another command. Results as of the final state of the tree at the time of running; set 9 was editing the same tree throughout, and where a failure is theirs it is named as such rather than counted against this set.

| Command | Result | Notes |
|---|---|---|
| `python -m pytest tests/system_03_search_agent -q -p no:cacheprovider` (first full run, with `-p no:logging` added) | 6 failed, 4589 passed, 176 skipped, 1 xfailed, 10 errors, 18m17s | The 10 errors are `caplog` fixtures broken by my `-p no:logging` flag, not defects; the run is repeated without the flag below. Of the failures: `test_cq_routing_mutation::test_p2_goes_red_when_the_flagship_resolves_nothing` was mine (the mutation no longer breaks resolution because the fallback confirms BRCA1; the arm now empties both halves, and a second arm pins the fallback), fixed; `test_debugging_guide_coverage` (2) is set 9's new `synthesis/answer_layout.py` with no guide row; `adapters/mcp/test_phase_4_1_premise::test_an_operator_allowlisted_caller_still_gets_no_cost_field` is set 9's new `summary` key on the trust signal reaching the MCP response allowlist. |
| `python -m pytest tests/system_03_search_agent -q -p no:cacheprovider` (final, no extra flags) | 1 failed, 4607 passed, 176 skipped, 1 xfailed, 10m10s | The one failure is `adapters/graphql/test_types.py::TestAskInputAndAudienceDepth::test_audience_depth_has_exactly_querys_three_values`: set 9's new `plain_language` value on `Query.audience_depth`, their file and their test to update. Every arm of this set (`test_layer_handoff.py`, 22; the two P2 mutation arms; the updated `test_graph.py` and `test_run.py` assertions) passes. |
| `ruff check .` | exit 0 (final) | Four pre-existing errors in `testing/Developer/scripts/local_loop_run.py` (3 x I001, 1 x BLE001, all present on the HEAD copy) were fixed on the coordinator's instruction since this set had edited the script. |
| `isort --check-only src tests` | exit 0 | |
| `python3 tracker/check_doc_drift.py --check` | exit 1: 2 stale, 0 structural (final) | `AGENTS.md:32` and `CLAUDE.md:32` carried a Python test count of 4919 at the time, against 4991 computed. Not edited (the main agent's files); the count includes set 9's new tests as well as this set's 22 plus one. |
| `frontend`: `npm run build` | exit 0 | one pre-existing chunk-size warning |
| `frontend`: `npx vitest run` | first run under load: 64 failed in 8 files, all 15-second timeouts. Final run on an idle machine: 4 failed, 406 passed in 41 files; three of the four were 15-second load timeouts, and each of those three files passes alone (`App.test.tsx` 37 of 38, `phase49Premise.test.tsx` 21 of 21, `railCollapsePremise.test.tsx` 20 of 20) | The one genuine failure, `App.test.tsx > the tour's 'Run it for me' sends the BRCA1 question through the real ask`, asserts `createRun` is called with `audience_depth: "researcher"`; set 9's `App.tsx` now defaults the mode to Plain language, so it is their test to update. Every set 8 file passes: `RunProgress.handoff.test.tsx` (12), `events.persona.test.ts` (3), `useRunView.handoff.test.ts` (3), plus the neighbouring `RunScreen.*`, `events.test.ts`. |
| `frontend`: `npx playwright test e2e/query-stream-and-stop.spec.ts e2e/second-turn.spec.ts e2e/accessibility.spec.ts --workers=1` | exit 0, 24 passed in 4.2m | includes `second-turn.spec.ts`'s 390px arm ("the thread and the inline run fit the page at 390px") and the accessibility spec's no-horizontal-scroll checks, so the handoff block was on screen for those |

## Live-run table

All runs through `testing/Developer/scripts/local_loop_run.py <question> --plain --no-memory --summary`, real models and graph from `.env`, driven by a scratchpad runner (14 runs, about 0.42 USD). `--no-memory` matters: the script otherwise injects a BRCA1 memory, and a gene that failed to resolve would silently bind to that antecedent and hide the failure. Layers are the tool layers that ran; "cited" is the layer set of the citation events; the source set is the set of citation `source_url`s.

### Batch 1 (page size 10 for trials, plan-order findings)

| Question | Run | Elapsed | Resolved | Tools (status/rows) | Layers ran | Layers cited | Sources | Trust |
|---|---|---|---|---|---|---|---|---|
| Which diseases are associated with BRCA1? | 1 | 37.0s | NCBIGene:672 | cypher ok/4, efetch ok/1, pubtator ok/1, trials ok/5 | 1, 2, 3 | 2, 3 | 10 | ask |
| same | 2 | 20.2s | NCBIGene:672 | same, all ok | 1, 2, 3 | 2, 3 | 11 | ask |
| same | 3 | 60.7s | NCBIGene:672 | same, all ok | 1, 2, 3 | 2, 3 | 10 | ask |
| Variants in GCK causing MODY | 1 | 34.7s | NCBIGene:2645 | cypher ok/100, efetch ok/1, pubtator ok/1, trials ok/5 | 1, 2, 3 | 1 | 20 | answer |
| same | 2 | 27.2s | NCBIGene:2645 | same, all ok | 1, 2, 3 | 1 | 20 | answer |
| same | 3 | 31.1s | NCBIGene:2645 | same, all ok | 1, 2, 3 | 1 | 20 | answer |
| same | 4 | 9.6s | NCBIGene:2645 | same, all ok | 1, 2, 3 | none | 0 | refuse ("I could not identify that gene") |
| same | 5 | 15.2s | none | none ran | none | none | 0 | refuse |
| Which clinically significant variants have been reported in CFTR? | 1 | 28.3s | NCBIGene:1080 | cypher ok/100, efetch ok/1, pubtator ok/1, trials ok/5 | 1, 2, 3 | 1 | 20 | answer |
| same | 2 | 33.0s | NCBIGene:1080 | same, all ok | 1, 2, 3 | 1 | 20 | answer |
| same | 3 | 34.5s | NCBIGene:1080 | same, all ok | 1, 2, 3 | 1 | 20 | ask |
| What is known about EGFR mutations in NSCLC, and what trials are recruiting? | 1 | 22.7s | NCBIGene:1956 | cypher ok/100, efetch ok/1, pubtator ok/1, trials (RECRUITING) ok/5 | 1, 2, 3 | 1 | 20 | ask |
| same | 2 | 28.9s | NCBIGene:1956 | same, all ok | 1, 2, 3 | 1 | 20 | ask |
| same | 3 | 42.8s | NCBIGene:1956 | same, all ok | 1, 2, 3 | 1 | 20 | ask |

Distinct citation source sets per question, batch 1: BRCA1 2 of 3 runs (one run also cited `NCT03286842`); GCK 1 among the three answering runs (the refusals cite nothing); CFTR 1 of 3; EGFR 1 of 3.

What batch 1 established, each of which changed the code before batch 2:

- The BRCA1 disease question shows no Layer 1 citation because build phase 6.2 attributes a resolved MedGen disease name to the Layer 2 record it came from (`_RESOLVED_NAME_LAYER` in `synthesis/findings.py`); the four disease sources are the same four URLs as before this set. Not a set 8 effect.
- On GCK, CFTR and EGFR every tool ran `ok` and every citation was Layer 1: the graph returns 100 rows, the write side offers Synth at most `MAX_FINDINGS_PER_PROMPT` findings and cites at most 20, walking `findings` in order, and the cypher finding came first, so the seven small Layer 2/3 findings never reached the prompt. Fixed inside `act_node`, not on the write side: the pairs handed to the coordinator are ordered Layer 2, Layer 3, Layer 1 (each in plan order within the layer), so the fixed-cap layers take at most seven slots and the graph the rest. Every pairing is intact and `state["tool_calls"][0]` is still the cypher call. It changes which 13 of 100 ClinVar rows a variants question cites (still the template's stable order), which is why it is flagged for the main agent as a decision rather than taken quietly.
- BRCA1's second source set came from ClinicalTrials.gov's `sort=@relevance` page of 10 admitting a different study at the boundary once. `_CLINICALTRIALS_PAGE_SIZE` is now the tool's maximum, 50, before the `nct_id` sort and the cap of 5.
- GCK run 4 refused after four `ok` tools with GCK resolved: the model tagged MODY as a gene span, the live lookup rejected it, `think_node` set `unresolved_entity_symbols` on that alone, and `write_node`'s early exit refuses on the key regardless of what else resolved, although its own comment says the key means "this query's ONLY candidate entity does not resolve" and `_select_planned_tool_call`'s rule 1 already refuses only when nothing resolved. `think_node` now sets the key only when nothing resolved, and names the rejected span in the think narrative ("not recognised as a gene symbol: MODY"). A lone mistyped symbol still refuses, unchanged, and `test_an_unconfirmed_model_span_still_refuses` pins it.
- GCK run 5 resolved nothing and ran no tool; its raw log was not kept by the batch 1 runner. Batch 2 keeps every log.
- The `ask` outcomes carry answer-scope trust text "Based on N sources, not yet confirmed" with `grounded: true`: the existing Section 8.3 aggregate (not triangulated) as rendered by set 9's trust line, not a set 8 effect. Recorded because a product owner will see "not yet confirmed" over a fully cited answer.
- Elapsed: 9.6s to 60.7s, all under 90s, measured while the full Python suite ran on the same machine.

### Batch 2 (page size 50, Layer 2-3-1 findings order, Think key only when nothing resolved; raw log per run kept in the scratchpad as `run2_q*_*.log`)

| Question | Run | Elapsed | Resolved | Tools | Layers cited | Sources | Trust |
|---|---|---|---|---|---|---|---|
| Which diseases are associated with BRCA1? | 1 | 20.6s | NCBIGene:672 | all four ok (4, 1, 1, 5 rows) | 2, 3 | 11 | ask ("Based on 4 sources, not yet confirmed") |
| same | 2 | 31.3s | NCBIGene:672 | all four ok | 2, 3 | 11 | ask |
| same | 3 | 19.6s | NCBIGene:672 | all four ok | 2, 3 | 11 | ask |
| same | 4 | 19.0s | NCBIGene:672 | all four ok | 2, 3 | 11 | ask |
| same | 5 | 24.9s | NCBIGene:672 | all four ok | 2, 3 | 11 | ask |
| Variants in GCK causing MODY | 1 | 40.8s | NCBIGene:2645 | all four ok (100, 1, 1, 5 rows) | 1, 2, 3 | 20 | ask |
| same | 2 | 42.9s | NCBIGene:2645 | all four ok | 1, 2, 3 | 20 | ask |
| same | 3 | 39.9s | NCBIGene:2645 | all four ok | 1, 2, 3 | 20 | answer |
| same | 4 | 38.6s | NCBIGene:2645 | all four ok | 1, 2, 3 | 20 | ask |
| same | 5 | 43.6s | NCBIGene:2645 | all four ok | 1, 2, 3 | 20 | ask |

Distinct citation source sets, batch 2: BRCA1 1 of 5; GCK 1 of 5. GCK resolved five of five and answered five of five; every run cited all three layers. In all five GCK runs the Think model itself extracted GCK, and none tagged MODY as a gene (no "not recognised as a gene symbol" note in any think narrative), so neither the fallback nor the narrowed refusal key fired in this batch; both are pinned by unit arms rather than by this batch. Elapsed 19.0s to 43.6s, under 90s.

BRCA9 proof (decision 3): `Which diseases are associated with BRCA9?` with `--no-memory`: think resolved nothing, plan reads "no tool selected; unresolved gene symbol candidate(s): BRCA9", no tool ran, the answer is the refusal naming BRCA9 with the NCBI search link, `trust_outcome: refuse`. Memory-with-BRCA1 cannot supply an entity in its place: `_select_planned_tool_call`'s rule 1 is unchanged and `test_an_unconfirmed_model_span_still_refuses` covers the model path; the plan-memory-binding suite is unchanged and green.

### Batch 3 (CFTR and EGFR, three runs each, after the same changes; logs kept as `run3_q*_*.log`)

| Question | Run | Elapsed | Resolved | Tools | Layers cited | Sources (of which Layer 3) | Trust |
|---|---|---|---|---|---|---|---|
| Which clinically significant variants have been reported in CFTR? | 1 | 38.6s | NCBIGene:1080 | all four ok (100, 1, 1, 5 rows) | 1, 2, 3 | 20 (6) | answer |
| same | 2 | 28.2s | NCBIGene:1080 | all four ok | 1, 2, 3 | 20 (6) | ask |
| same | 3 | 30.8s | NCBIGene:1080 | all four ok | 1, 2, 3 | 20 (6) | ask |
| What is known about EGFR mutations in NSCLC, and what trials are recruiting? | 1 | 49.3s | NCBIGene:1956 | all four ok, trials filtered to RECRUITING | 1, 2, 3 | 20 (6) | answer |
| same | 2 | 32.0s | NCBIGene:1956 | all four ok | 1, 2, 3 | 20 (6) | answer |
| same | 3 | 55.0s | NCBIGene:1956 | all four ok | 1, 2, 3 | 20 (6) | answer |

Distinct citation source sets, batch 3: CFTR 1 of 3; EGFR 1 of 3.

### Done-when 6, taken together

Every run in batches 2 and 3 (16 runs) resolved its gene, ran all four tools `ok`, cited at least two layers (BRCA1: Layers 2 and 3, the four disease names being Layer 2 attributed; GCK, CFTR, EGFR: all three), the trials question cited Layer 3 (five recruiting trials plus the literature entity), every run finished under 90 seconds (19.0s to 55.0s, on a machine also running the Python suite), GCK resolved five of five, and every question had exactly one distinct citation source set across its runs. Batch 1's variance (two BRCA1 sets, two GCK refusals) is recorded above with the change that answered each.

## Design gap and token derivation

No handoff design exists. Checked `docs/build/design/README.md`'s coverage table, `components/persona.html` (the chip and the per-step caption only) and `prototype/app.html` (one `.pcap` caption per step, `NARRATIVE[step]`, no helpers, no per-layer line). Built from the two nearest designed neighbours, named here rather than invented:

- The persona caption (`.pcap` in `prototype/app.html` line 315, `PersonaCaption` in code): 13.5px muted text (`designTokens.inkMuted`, MUI `body2`), the name in bold ink (`designTokens.ink`), 22px minimum line height, the same `PersonaInfo` control the lead's chip carries. Each handoff line is that caption with a layer badge in front.
- The layer badge (`identity/layer-badges.html`): `.dot` is a 12px square with a 3px radius filled with the layer colour; `.n` is mono 11px, 0.06em tracking, bold, in the layer colour. Both copied as written. Colour: `layerColour(n).main` from `theme.ts` (`layer1`, `layer2`, `layer3`).
- Working versus done: the dot is outlined (2px border in the layer colour, `designTokens.surface` fill) while working and filled once the layer's results land; a layer whose every call errored gets a `designTokens.line` border and the words "did not answer". No new colour, radius or type size; the working outline reuses the 2px border weight the stepper's own dots carry.
- 390px: every handoff line is `flexWrap: wrap`, so the sentence drops under the badge rather than pushing the card sideways; the info card already caps at `calc(100vw - 32px)`. Verified in the browser suite's accessibility run (see Verify commands).
- The lead's sentence during Act, "{Lead} is handing off to {A}, {B} and {C}", replaces `STEP_NARRATIVE.Act` for that step only, through an optional `narrative` prop on `PersonaCaption`; on Write the caption returns to "is writing the answer, citing as it goes", which is the coordinator writing underneath.

## Write-side needs for Layer 3 citations

Confirmed by the live runs: a Layer 3 row is cited today through `_citations_from_grounded_claims`'s generic branch with no write-side change. What that branch gets wrong for these rows, and what the write side would need to fix it (the main agent decides; nothing here was edited):

- `evidence_kind` and `license`: the generic branch writes `primary_assertion` and `public_domain_us_gov`. For `clinicaltrials_search` the right values are in `synthesis/provenance_defaults.defaults_for_tool("clinicaltrials_search")`, and each tool ships its own `build_citation` (`tools/clinicaltrials_search.build_citation(study, display_index)`, `tools/pubtator_annotate.build_citation(...)`, `tools/ncbi_dbsnp.build_citation(result, field, display_index)`). The need: a branch per tool in `_citations_from_grounded_claims`, shaped like `_layer2_citation_for_synth_finding`, looked up by `source_url` identity against a `layer3_raw_outputs` map that `act_node` would stash exactly as it stashes `layer2_raw_outputs` (the `_CallOutcome.raw_output` slot already exists; today it is filled only for `ncbi_efetch`).
- `source_id` reads `"unknown"` because the pseudo-row's `curie` is empty. The row carries the identity in `fields` (`nct_id`, `pubtator_id`, `rsid`), so a per-tool branch can set `source_id` to it.
- `source` reads the tool name (`clinicaltrials_search`), which the source card shows as-is. The per-tool builders write `clinicaltrials.gov`, `PubTator3`, `dbSNP`.
- Host patterns: every Layer 3 `source_url` already passes `NCBI_SOURCE_URL_PATTERN` (`*.ncbi.nlm.nih.gov/...` and `clinicaltrials.gov/study/...`), so no pattern change is needed. LitVar2 rows use `source_url` from the tool, which the tool already host-pins.

## Proposed DECISIONS.md rows

In the existing table shape; the main agent appends them.

| Date | Decision | Alternatives considered | Why |
|------|----------|------------------------|-----|
| 2026-09-13 | Every question that resolves a gene plans all three layers: `cypher_query`, `ncbi_efetch`, `pubtator_annotate` (entity lookup on the symbol) and `clinicaltrials_search` (condition = the symbol), plus `ncbi_dbsnp` and `litvar2_lookup` per rs id written in the question; the four new calls run concurrently with the graph call under per-tool timeouts and degrade one at a time | Chain Layer 3 behind Layer 1 (PubTator `annotate_publications` on the graph's Article PMIDs); use a model-extracted disease span as the trials condition; run the layers one after another | <details><summary>why</summary>The product owner asked for all three layers on every question (R29). Chaining would make the literature call wait for the graph and would run only when the graph returns Article rows, which the flagship disease question does not. A model-extracted span varies in wording between runs of one question, and item 10.1 requires one citation source set per question, so every Layer 2 and 3 input is a pure function of the question text and the live-confirmed symbol. Sequential dispatch measured as the sum of four calls; concurrent dispatch is about the slowest one, and a layer that fails lands as a disclosed error result rather than a blank run.</details> |
| 2026-09-13 | Layer 2 and 3 tool rows are sorted by a record property (NCT id, rs id, record URL) and cut to a fixed five before synthesis; ClinicalTrials.gov is asked for its maximum page of 50 first | Keep the API's relevance order and take the first page; no cap | <details><summary>why</summary>The coordinator's instruction of 2026-09-13: adding layers must not break item 10.1's one-source-set rule. ClinicalTrials.gov's `sort=@relevance` order is not stable run to run, measured as two distinct BRCA1 source sets in three runs with a page of 10, one study at the page boundary. Sorting a superset by NCT id and cutting to five makes the kept set a property of membership, not order; the page of 50 makes boundary churn reach the kept five far less often. Consistency over relevance, stated as such.</details> |
| 2026-09-13 | The pairs `act_node` hands to the coordinator are ordered Layer 2, Layer 3, Layer 1, so the small fixed-cap findings reach the synthesis prompt ahead of a graph result that can fill every slot | Leave plan order; raise the write side's finding or citation caps; filter Layer 1 rows | <details><summary>why</summary>Measured live on CFTR and EGFR: all four tools ok, every citation Layer 1, because the graph returned 100 rows and the write side walks `findings` in order to its caps. The write side is set 9's and the main agent's to change, and raising caps changes answer length; ordering inside Act keeps every pairing and `state["tool_calls"][0]` intact and is deterministic, so a question still has one source set. It changes which 13 of 100 ClinVar rows a variants question cites, from the first 20 to the first 13, in the template's stable order.</details> |
| 2026-09-13 | Three helper scientists per run, one per layer, drawn with `random.SystemRandom` from the curated list excluding the session's lead, carried additively on `ToolCall` and the tool frames, never onto a `Finding` | Derive helpers deterministically from the session like the lead; draw on the client; put the names on the `plan` event only | <details><summary>why</summary>Decision U5 (2026-09-12): random every visit, helpers included. A per-session draw would repeat across a session, which reads as a bug once a second question runs; a client draw could not match the CLI and GraphQL surfaces. The frames carry the names because the web UI builds its chips from `tool_start` and `tool_result` alone. The coordinator copies only `call_id`, `tool` and `layer` onto a `Finding`, which is what keeps the names out of every synthesis prompt; a test asserts it.</details> |
| 2026-09-13 | `think_node` sets `unresolved_entity_symbols` only when nothing resolved; a span the model tagged as a gene that the live lookup rejected, beside one that resolved, is named in the think narrative and does not refuse | Keep refusing on any rejected span; drop the rejected span silently | <details><summary>why</summary>`_select_planned_tool_call`'s rule 1 and `write_node`'s early-exit comment both state the refusal is for a question whose ONLY candidate does not resolve, but the key was set on any rejected span and `write_node` refuses on the key alone. Live: "Variants in GCK causing MODY" resolved GCK, ran four tools ok, then refused because the model had tagged MODY as a gene. The lone mistyped symbol ("BRCA9") still refuses by name, unchanged and pinned by a test; the rejected span is disclosed in the narrative rather than dropped.</details> |
| 2026-09-13 | The GCK fallback: when the model extracts no gene span, tokens of 2 to 8 letters and digits that carry a digit or are entirely upper case are live-confirmed, at most three, and unconfirmed ones are dropped silently | Resurrect build phase 4.7's capitalised-token guess; add a stopword list; try every token | <details><summary>why</summary>The 2026-08-23 decision retired the unconfirmed guess and hand-kept token lists from this path, and this does not resurrect either: it runs only when the model found nothing, and a token contributes nothing unless NCBI confirms it. The digit-or-upper-case shape is the bound in place of a stopword list; an all-lowercase symbol without a digit (`gck`) is the stated residual. Unconfirmed candidates never become unresolved symbols, so the fallback can never turn a question the model failed to read into a refusal naming an English word.</details> |

## Proposed hand-test changes

For `testing/Product/Product_workflows.md`, tests 1, 7 and 12 (the main agent edits the file):

- Test 1 (a first question, the progress screen): after "Plan", expect the lead's line to read "{Lead} is handing off to {A}, {B} and {C}", then three lines under it, "{A} is searching the knowledge graph", "{B} is checking live NCBI records", "{C} is reading the literature and trials", each with an L1, L2 or L3 badge that starts outlined and fills as that layer's results land; each helper name has the same circled "i" as the lead's chip, opening a card with a sentence and a Wikipedia link. On "Write" the lead's line reads "is writing the answer, citing as it goes" and the three lines stay. Expected time to the answer: under 90 seconds; typically 20 to 40.
- Test 7 (a follow-up on the same screen): the same handoff renders inline under the new question; the helpers may differ from the first question's (they are drawn per run) while the lead stays the same.
- Test 12 (sources from more than one layer): expect the source list to show L2 and L3 sources as well as L1: a gene record (`gene/<id>`), a literature entity (`gene/<id>` from PubTator3), and up to five trials (`clinicaltrials.gov/study/NCT...`). For a variants question (GCK, CFTR) the first seven sources are the Layer 2 and 3 records and the rest are ClinVar variation records. For "what trials are recruiting", the trials shown are recruiting ones. Also expected, and to be read as normal: the trial and literature citations name the tool (`clinicaltrials_search`, `pubtator_annotate`) as their source until the write side gains per-tool citation builders (see "Write-side needs").
- Test 14, if it lists the scientists: two visits can show different helpers and the same answer; the lead's name is per session (or per account).

## Tests whose requirement changed

Seven assertions said a gene question plans exactly two tool calls (cypher_query and ncbi_efetch). The requirement is now four (plus pubtator_annotate and clinicaltrials_search on Layer 3), so each was updated to 4 with its comment saying why, and nothing else in those tests changed:

- `tests/system_03_search_agent/core/test_graph.py`: `test_done_event_trust_outcome_is_refuse_when_the_tool_call_errors` (total_tool_calls), `test_done_event_trust_outcome_is_answer_with_a_real_citation_when_the_tool_call_succeeds` (total_tool_calls), `test_plan_selects_cypher_query_for_a_graph_answerable_query`, `test_act_executes_the_selected_cypher_query_call` (paired lists), `test_plan_also_selects_ncbi_efetch_for_a_gene_anchored_query`.
- `tests/system_03_search_agent/core/test_run.py`: `test_run_dispatches_the_selected_tool_call_for_a_graph_answerable_query`, `test_run_streaming_dispatches_the_selected_tool_call_for_a_graph_answerable_query`.

Both files also gained an autouse fixture, `_stub_layer3_dispatch`, stubbing the two Layer 3 tools to genuine "empty" outputs, the same discipline as the existing `_stub_ncbi_efetch_dispatch`, so no unit test reaches the network blocker and no assertion about citations or trust changes (an empty finding contributes nothing). Before the fixture the suites still passed, because every tool catches its own transport failure and returns an error output, but each gene-question test then logged a blocked-network warning per Layer 3 call.

Observed while running: a mid-edit state of set 9's write-side code made 44 of these tests fail for a few minutes (unused imports from `synthesis/answer_layout`, then a refusal on every path); rerun a few minutes later, only the seven above failed, all `assert 4 == 2`. Recorded because the brief says to wait and rerun rather than touch their file, and that is what happened.

## Left open

- Set 9 reported `test_two_slow_layer_calls_finish_in_about_one_delay` red in their full-suite run under shared load: it compared wall time against a fixed 0.85s. Rewritten (2026-09-14) to compare the concurrent run against a sequential baseline measured in the same process (ratio under 0.75, baseline populate-checked at 0.8s or more), which a loaded machine slows alike; the mutation arm was rewritten to the same shape. 22 of 22 green after the change.
- Set 9 says they have finished and that `_citations_from_grounded_claims` is mine; per the coordinator's sequencing I have NOT taken it over, since that go-ahead must come from the coordinator. The draft and its test list are in the scratchpad, ready.

- The write-side Layer 3 citation branch (approved, sequenced behind set 9). Drafted in the scratchpad as `layer3_citation_branch_draft.py` with its tests listed; not applied. Until it lands, a trial or literature citation names the tool as its `source`, reads `source_id: unknown`, and carries the Layer 1 `evidence_kind` and `license` literals. `act_node` already stashes `GraphState.layer3_raw_outputs` for it.
- `frontend/src/App.test.tsx`: 4 of 38 failed when rerun alone while batch 2 shared the machine, two of them on the 15-second load timeout and two in the R46 reload group; `App.tsx` is set 9's file in this pass. To be rerun on an idle machine by the main agent; not attributable either way from here.
- The `ask` outcome on fully cited answers ("Based on N sources, not yet confirmed"): the answer-level aggregate as set 9's trust line renders it. A product owner will read "not yet confirmed" over a correct, cited answer. Not a set 8 change; named for the main agent.
- The GCK fallback's stated residual: an all-lowercase symbol with no digit (`gck`) is never a candidate, by the rule that admits only tokens with a digit or entirely upper-case letters, in place of a word list.
- A disease named only as a typed `MedGen:` CURIE, and a memory-bound follow-up whose remembered mention is itself a CURIE, plan no Layer 2 or 3 call: those inputs take text and no name is available without a lookup.
- `ncbi_dbsnp` and `litvar2_lookup` run only for an rs id written in the question. HGVS and SPDI strings are not recognised as variant mentions here; the variant evidence for "clinically significant variants in CFTR" is Layer 1's ClinVar rows.
- Doc drift: `AGENTS.md:32` and `CLAUDE.md:32` still carried a Python test count of 4919 when this was written (4988 computed, before this set's last arms and set 9's). The main agent owns those lines.
- No `DECISIONS.md`, `CLAUDE.md`, `AGENTS.md`, `Plan.md`, fix-plan or hand-test file was edited; the proposed rows and hand-test wording are above.
- The scratchpad runner scripts (`live_runs.py`, `live_runs2.py`, `live_runs3.py`) and the raw per-run logs live in the session scratchpad, not in the repository.

## Layer 3 citation branch

Applied on the coordinator's go-ahead of 2026-09-14, after set 9 reported finished. Scope taken over: `_citations_from_grounded_claims`, the new branch and its helpers, the `layer3_raw_outputs` wiring; nothing else in `write_node` except the `record_label` call the coordinator asked for separately (below).

What changed in `core/graph.py`:

- `_LAYER3_CITATION_TOOLS`, `_layer3_row_for_synth_finding`, `_layer3_base_citation`, `_layer3_citation_for_synth_finding`, placed beside `_layer2_citation_for_synth_finding` and shaped like it. A grounded claim from `clinicaltrials_search`, `pubtator_annotate`, `litvar2_lookup` or `ncbi_dbsnp` is cited through the tool's own `build_citation` (imported under aliases), so `source`, `evidence_kind` and `license` come from the builder and `provenance_defaults.defaults_for_tool`; `source_id` is the record's own identity read off the pseudo-row (`nct_id`, `pubtator_id`, `rsid`, else the CURIE); `source_url` is the claim's own record, so a builder that cites its output's first entity is re-targeted, and it stays host-pinned by `CitationPayload`'s pattern. Falls back to the generic construction with the tool's registered defaults when the typed output is missing or the builder refuses; returns None, never raises, when that fails too (F-3.4-T05-04's rule).
- `_citations_from_grounded_claims` gains the optional `layer3_raw_outputs` kwarg and the branch right after the `ncbi_efetch` one; `write_node` reads `state.get("layer3_raw_outputs", {})` beside the Layer 2 stash and passes it at the one call site.
- One fact the registry settled against the brief's premise: `defaults_for_tool("clinicaltrials_search")["license"]` IS `public_domain_us_gov`, the same word as the Layer 1 literal. What the branch changes for a trial is therefore `source` (`clinicaltrials.gov`, was the tool name), `source_id` (the NCT id, was `unknown`) and `evidence_kind` (`external_annotation`, was `primary_assertion`); PubTator3 changes all four (`ncbi_gene`, `@GENE_<symbol>`, `publisher_copyright_abstract_only`, `literature_mention`). The tests and the mutation arm key on `source` and `source_id` for that reason.

Tests added to `tests/system_03_search_agent/core/test_layer_handoff.py` (now 28 arms, all populate-checked): a trial citation carries `clinicaltrials.gov`, its NCT id and the registry's evidence kind and license; a PubTator3 citation carries `@GENE_BRCA1` and its registry provenance on the claim's own gene page; every citation on a three-layer run matches `NCBI_SOURCE_URL_PATTERN`; the dbSNP path through `ncbi_dbsnp.build_citation` yields `dbsnp` and `rs334`; a missing stash falls back to the tool's defaults with `source_id: unknown` rather than raising; and the mutation arm empties `_LAYER3_CITATION_TOOLS` and asserts the trial citation reverts to the tool name and `unknown`, which is exactly what the first arm refuses.

### Live proof (batch 4: EGFR three runs, BRCA1 two runs, `--plain --no-memory --summary`; logs `run4_q*_*.log`)

Every Layer 2 and 3 citation, per run (the Layer 1 ClinVar citations are omitted from the listing; they are unchanged):

| Question | Run | Elapsed | Layer 3 citations: source / source_id / license / evidence_kind | Source set |
|---|---|---|---|---|
| EGFR mutations in NSCLC, recruiting trials | 1 | 35.5s | `ncbi_gene` / `@GENE_EGFR` / `publisher_copyright_abstract_only` / `literature_mention` (gene/1956); `clinicaltrials.gov` / `NCT01994057`, `NCT04324164`, `NCT05037331`, `NCT05257967`, `NCT05341492` / `public_domain_us_gov` / `external_annotation`; Layer 2 `gene` / `1956` | 20 URLs |
| same | 2 | 30.2s | identical | identical |
| same | 3 | 47.4s | identical | identical |
| Which diseases are associated with BRCA1? | 1 | 23.0s | `ncbi_gene` / `@GENE_BRCA1` / `publisher_copyright_abstract_only` / `literature_mention` (gene/672); `clinicaltrials.gov` / `NCT00590109`, `NCT00597987`, `NCT00617656`, `NCT00673335`, `NCT00700778` / `public_domain_us_gov` / `external_annotation`; Layer 2 `ncbi_efetch` / the four MedGen ids and `gene` / `672` | 11 URLs |
| same | 2 | 20.9s | identical | identical |

Distinct source sets: EGFR 1 of 3, BRCA1 1 of 2, and both sets are the same URLs as batches 2 and 3 (checked by set equality against those runs' JSON). Every `source_url` is on `*.ncbi.nlm.nih.gov` or `clinicaltrials.gov/study/`.

### `record_label` in the list and table cells

Verified first: `record_label(finding, row_fields)` exists in `synthesis/answer_layout.py` and `_row_fields_for(finding, findings)` exists in `core/graph.py`, already used for the table's second cell. In `_answer_tokens` the `table_row` first cell and the `list_item` cell now read `record_label(finding, _row_fields_for(finding, findings))` instead of `finding.field_value[:500]`; `record_label` added to the existing `answer_layout` import. `_pick_representative_field` and `_is_vocabulary_token_artifact` untouched. New arm in `tests/system_03_search_agent/core/test_write_answer_structure.py`: a real ClinVar row whose `name` is `NM_000162.5(GCK):c.363+318G>A`, with `id`, `source` and `source_url` fields, populate-checked to have `source_url` as the upstream pick, renders a list cell reading the variant name and never a URL. `tests/system_03_search_agent/synthesis/test_answer_layout.py` plus `core/test_write_answer_structure.py`: 44 passed.

### The concurrency arm

`test_two_slow_layer_calls_finish_in_about_one_delay` compared wall time against a fixed 0.85 seconds, which a loaded machine breached in set 9's full run. Changed exactly this: the arm now measures a sequential baseline in the same process (the module's own `_gather_planned_calls` swapped for a sequential runner, then restored) and asserts the concurrent run takes under 0.75 of it, with the baseline populate-checked at 0.8 seconds or more for two 0.4-second fakes; the mutation arm asserts the same ratio does not hold under the sequential runner. The claim pinned is unchanged: concurrent finishes well under the sum. Not deleted, not skipped. Rerun alone five times: 2 passed each time (7.4s to 9.7s per pair).

### Live Researcher run of the CFTR question

`python testing/Developer/scripts/local_loop_run_depth.py --depth researcher --print "Which clinically significant variants have been reported in CFTR?"` (log `cftr_researcher.log`): outcome `answer`, 5 headings, 20 list items, 0 unmarked claims. Every list row reads a record name and none reads a URL: the gene record and literature entity rows read `CFTR`, the five trial rows read their titles, the thirteen ClinVar rows read their HGVS names, including the two intronic ones (`NM_000492.4(CFTR):c.744-9G>T`, `NM_000492.4(CFTR):c.744-7_744-4del`) whose upstream pick is the URL. Source set: 20 records, identical to batch 3's CFTR runs (checked by set equality after mapping the printed ids back to URLs).

### Verify (this round, each on its own exit code)

| Command | Result | Notes |
|---|---|---|
| `python -m pytest tests/system_03_search_agent -q -p no:cacheprovider` (final, over the finished tree) | 4619 passed, 176 skipped, 1 xfailed, 0 failed, 3m41s | An earlier run of this round, started before the last two arm corrections, showed two failures, `test_rate_limit_concurrency_premise::test_a8_...` and `test_think_retry::test_the_logged_excerpt_is_bounded_and_escaped`; each passes alone and both pass in the final run, so they were order- or load-dependent in that one run. Set 9 updated the GraphQL depth-values test, so it no longer fails. |
| `ruff check .` | exit 0 | |
| `isort --check-only src tests` | exit 0 | |
| `frontend`: `npx vitest run src/components/screens` | 10 files, 68 passed, exit 0 | |
| `tests/.../synthesis/test_answer_layout.py` plus `core/test_write_answer_structure.py` | 44 passed | includes the new intronic-name arm |
| `test_layer_handoff.py` concurrency pair, alone, five times | 2 passed each time | |
