# Wiring 11.21 into the answer path, 2026-09-19 overnight run

Unattended build in worktree `.claude/worktrees/breadth-wiring` (branch `worktree-breadth-wiring`, cut from develop `6e4aae1`). Contract: `testing/UI_fix_plan.md`, "Next, in order", item 2. Binding review: `testing/Developer/reports/2026-09-14_breadth_tool_layer/review.md`. This file is appended to as findings are established, so the sections below grow in the order the work happened.

## Table of contents

- [Status](#status)
- [What was read first](#what-was-read-first)
- [Findings log](#findings-log)
- [What was wired, file by file](#what-was-wired-file-by-file)
- [The GO template](#the-go-template)
- [Call counts per question shape](#call-counts-per-question-shape)
- [Latency](#latency)
- [Determinism evidence](#determinism-evidence)
- [Verify surface](#verify-surface)
- [Not done, with reasons](#not-done-with-reasons)
- [Merge judgement](#merge-judgement)

## Status

Done, 2026-09-20 03:00. The wiring is built in the worktree, every verify-surface item is quoted below, and the judgement is at the end. Two items the run could not close are recorded as the product owner's (the cited-set half of determinism, and the answer's composition inside the 20 cap); two tool-layer items and one coordinator item are under "Not done".

## What was read first

| File | What it settled |
|---|---|
| `src/system_03_search_agent/core/breadth_plan.py` | Real signatures: `plan_first_stage(gene_symbol, disease_title) -> tuple[PlannedCall, ...]` (PubMed search, then for a symbol ClinVar search and OMIM search); `plan_literature_follow_up(pmids)` (abstract fetch plus PubTator3 `annotate_publications` on the same sorted, capped PMIDs); `plan_clinvar_follow_up(ids)` and `plan_omim_follow_up(ids)` (one ESummary each); `select_ids` sorts numerically highest first, drops non-uids and zero, caps; `filter_omim_titles` is field-exact on the semicolon-separated symbol fields. Caps: PubMed 5, ClinVar 10, OMIM 10. `PlannedCall` carries `tool`, `layer`, `prefix`, `purpose`, `tool_input` |
| `testing/Developer/reports/2026-09-14_breadth_tool_layer/review.md` | F-01 closed: GO rows citeable only with an explicit `go_attribution_curie`, nothing in `src/` passes it today. N-04 open: `_dedupe_by_cited_record` dedupes by CURIE only; a multi-gene GO template would make it live. Abstract quoting removed by product-owner decision; 11.22 reserved |
| `src/system_03_search_agent/harness/call_budget.py` | `MAX_LAYER_2_3_CALLS_PER_QUERY = 20`, charged at the two Layer 2/3 transports, read by `act_node`. `calls_made()` exposes the counter |
| `src/system_03_search_agent/core/graph.py` (definitions list) | `plan_node` at line 3747, `_build_layer_tool_calls` at 2522, `_layer_call` at 2515, `_build_planned_ncbi_efetch_call` at 3414, `act_node` at 4525, `_execute_planned_call` at 4309, `_MAX_CITATIONS_PER_ANSWER = 20` at 4717 (reserved for the product owner, not touched) |

## Findings log

Appended the moment each is established.

- 2026-09-19: tooling. The worktree has no `venv/`; the main repository's `venv/bin/python`, `ruff` and `isort` are used, and `pyproject.toml`'s `pythonpath = ["src", "."]` makes pytest import the WORKTREE's `src` (the package is not pip-installed, verified by `ModuleNotFoundError` outside pytest).
- 2026-09-19: OMIM cannot be cited on an answer today. `ncbi_eutils_actions._RECORD_URL_TEMPLATES["omim"]` is `https://omim.org/entry/{id}` (Section 6.2, "design decision 3"), and `contracts/events.py` `NCBI_SOURCE_URL_PATTERN` admits only `ncbi.nlm.nih.gov` and `clinicaltrials.gov/study/`. `_layer2_citation_for_synth_finding`'s own docstring records that an OMIM record fails `CitationPayload` construction (F-3.4-T05-04) and the claim goes uncited. Decision: the OMIM search and summary from `plan_first_stage` and `plan_omim_follow_up` are NOT dispatched by this wiring, because two Layer 2 calls whose records can never be cited would feed uncited claims into the grounding pass. Lifting this needs the locked URL template or the locked citation pattern widened, a product-owner item, recorded under "Not done".
- 2026-09-19: the per-query call ceiling counts Think's live lookups. `core/run.py:581` enters `query_budget_scope("lookup")` around the whole run and `ncbi_transport.execute_get` charges once per attempt, so symbol resolution (Datasets, ESearch, ESummary: up to three per symbol) and disease-mention resolution (up to three mentions) are already spent before Act. The worst-case count must therefore be measured on a run, not summed from the plan.
- 2026-09-19: the findings cap crowds out the graph unless admission changes. `write_node` hands Synth at most `_MAX_CITATIONS_PER_ANSWER` (20) findings, admitted in the Layer 2, 3, 1 handoff order `act_node` reassembles. Develop's context rows today: one gene record plus up to five literature entities plus up to five trials, 11, leaving nine slots for the graph answer. Adding ClinVar (10), PubMed (5) and PubTator publications (5) rows in front would leave zero. So the wiring needs a fixed, deterministic allotment between answer-shape findings and context findings; this is an admission-order decision inside the 20 cap and does not touch the cap value, which is reserved for the product owner.
- 2026-09-19: an ESearch result is one aggregate record carrying `idlist`; it is an id source, not a finding, so search outcomes contribute no rows to synthesis.
- 2026-09-20 00:40: the coordinator's L-01 (`../2026-09-19_live_measure/findings.md`) read in full. Shape 2 (a DIFFERENT six MedGen concepts on run 1) has an established mechanism in the code: `gene_variant_diseases_one` returns `RETURN v, xs ORDER BY v.id` where `xs` is `collect(DISTINCT x)`; neither AGE nor Postgres orders the elements of a collected list, `cypher_provenance._iter_entities` emits a list column's vertices in list order, `cypher_query._fold_curies` reads the same list in the same order, `_dedupe_by_cited_record` keeps the FIRST row per CURIE, and `mapped_rows[: row_limit]` (100) then cuts 100 variants plus 36 diseases to 100 in that emission order. Which diseases survive the cut therefore follows the aggregate's internal order, which is not stable between executions. Fix in scope for this run: sort a list column's vertices by CURIE before emission (`_iter_entities`) and in `_fold_curies`, leaving path columns (which carry edges) untouched. Shape 1 (all five ClinVar rows absent on runs 1 and 4, 13 and 8 sources) is UNESTABLISHED: `baseline_6e4aae1.json` records only the step sequence, not `tool_result` payloads or the answer text, and on both runs all four `tool_result` events were emitted and no `error` event fired, so a timed-out or errored graph call is not shown by the data and is not asserted here. What would settle it: the measurement script capturing each `tool_result` payload (`status`, `summary`, `result_count`) and the citation count against the findings count per run. Left to the coordinator, scoped in "Not done".
- 2026-09-20 00:40: `_layer2_citation_for_synth_finding` hands `build_layer2_citation` the WHOLE `NcbiEfetchOutput` and that builder cites the FIRST record carrying a `source_url`, so on a multi-record output every claim would cite record one's URL and id. Latent today because `dataset_report` returns one record; it becomes live the moment a ClinVar ESummary (up to 10 records) or a PubMed fetch (up to 5) reaches the write side. Fixed in this run by narrowing the output to the matched record before the builder runs, with a red-first test.
- 2026-09-20 01:05: first live run of the wiring (local, in-process, main `.env`, BRCA1 disease question, researcher): 16.4s, 15 cited sources, 11 Layer 2/3 transport charges, ten planned calls. Two `error` results. (1) The GO graph call: the live graph rejects `-[:participates_in|actively_involved_in|located_in]->` with `SyntaxError` (transport message: "graph query failed: SyntaxError, verify the generated Cypher"), although `cypher_validator.validate_cypher` accepts it, so the offline test that proved the template is unit-correct did not prove AGE runs it. Fix in progress below. (2) The PubTator3 publications call errored in the run but answered `ok` with two publications when probed directly a minute later on two other PMIDs, so its cause is not the input shape; watched across the full measurement.
- 2026-09-20 01:05: the cited set is narrower than the admitted set. Five PubMed records were fetched and admitted to the prompt, and no PubMed citation was emitted: a citation exists only where the model's prose grounded a claim on that finding (`_citations_from_grounded_claims`, build phase 2.2), so which CONTEXT findings become sources is the model's choice. The admitted findings set is now recorded separately from the cited set on every measured run, so the determinism evidence can say which of the two varies.
- 2026-09-20 01:15: probed four Cypher forms against the live graph through `cypher_query` with a forced template. Both alternation forms (`[:a|b|c]` and `[:a|:b|:c]`) fail with `SyntaxError`; each single-edge hop succeeds with attribution: `participates_in` 40 BiologicalProcess rows, `actively_involved_in` 19 MolecularActivity rows, `located_in` 16 CellularComponent rows, every row cited to `https://www.ncbi.nlm.nih.gov/gene/672` with `_cited_via_gene_curie=NCBIGene:672`. Decision: the template traverses `participates_in` alone and is named `gene_go_processes_one`; the other two edges would be two more graph calls (two more chips, two more context queues in the allotment) and are recorded as not done. The GO template test was corrected to pin the single edge, before its green run.
- 2026-09-20 01:25: `tracker/check_doc_drift.py --check` in the worktree reports `6 facts computed (4 skipped) | 0 stale | 1 structural`; the structural item is `testing/Developer/reports/2026-09-19_verification/live_check.md`, whose ToC lacks its last heading (`correction-by-the-main-agent-2026-09-19`). Not mine and not touched; the coordinator's file.
- 2026-09-20 01:35: the PubTator3 publications follow-up fails on every BRCA1 run and on no HNF1A run. Reproduced outside the loop: `breadth_plan` selects the FIVE HIGHEST PMIDs the PubMed search returned (its documented determinism rule), which for BRCA1 are the five newest papers (`42762135`, `42760358`, `42760352`, `42758366`, `42757486`), and PubTator3 answers "Could not retrieve publications" for them; HNF1A's five (`42733542` down) are a little older and annotate `ok`. So the failure is the planner's newest-first choice meeting PubTator3's indexing lag on a heavily published gene, and it degrades as designed (an `error` result, the run answers, the abstract fetch on the same PMIDs succeeds). Owner: the tool layer (`breadth_plan` or `pubtator_annotate`), not the wiring; a candidate fix is recorded under "Not done" once the batch probe below says whether one unindexed PMID sinks the batch.
- 2026-09-20 01:40: batch probe: each of the five BRCA1 PMIDs fails PubTator3 on its own, and the four without the newest fail as a batch too, so it is not one bad id sinking a batch; all five are newer than PubTator3's index. A wiring-side retry cannot help; the fix is in the planner (search wider than five, keep the five highest PubTator3 can annotate, or prefer ids below a recency margin), which changes `breadth_plan`'s documented selection rule and is a tool-layer decision.
- 2026-09-20 02:10: the first full-suite run (started before the GO rename and the two boundaries) returned `43 failed, 4980 passed`. Causes, each established. Forty were one defect of mine: `act_node` passed `template=None` to EVERY `cypher_query` call, so every existing two-argument stand-in raised `TypeError`, and with no last-resort boundary on the Layer 1 branch that exception discarded the run's accumulated events (hence "no `think` event" and "never emitted a `guard` event" across the mutation and clarification files). Fixed by passing the keyword only when a template is set and by giving the Layer 1 branch the boundary the other branches have. Nine were count assertions in `test_run.py` and `test_graph.py` pinning set 8's plan size (4 planned, 4 dispatched); each now pins the new exact value (10 planned, 5 dispatched pairs) or the exact new tail list of tools and layers, with a comment naming this wiring; none was loosened to a range, a subset or removed. One (`test_debugging_guide_coverage`, `contracts/events.py`'s summary line) is pre-existing at `6e4aae1` and passes on the main tree, where the other agent's uncommitted manifest fix lives. One (`test_phase_4_1_production_mount`, "StreamableHTTPSessionManager .run() can only be called once per instance") is order-dependent in a full run and passes alone in both trees.
- 2026-09-20 02:20: two citation identity defects found in the live citation dump, both mine, both fixed red first (`test_a_go_citation_carries_the_go_curie_even_when_a_layer3_row_shares_its_url` and `test_a_pubtator_publication_citation_carries_its_pmid_as_source_id`, red `'' == 'GO:0006281'` and `'unknown' == '42639261'`, then green). (1) Three GO rows in the BRCA1 answer shipped as `source_id` `unknown` under `source` `cypher_query`: `_curie_for_citation`, `_graph_snapshot_version_for_citation` and `_entity_name_for_citation` each recovered a row by `source_url` alone across every finding, and the PubTator3 entity row (Layer 3, empty CURIE, the same gene page URL) comes first in the handoff order. A shared `_row_behind_synth_finding` now prefers the finding's own call and, within it, the row carrying the finding's own CURIE (several GO rows share one URL), before the old global scan, so no caller that never hit the collision changes. (2) A PubTator3 publication row shipped as `source_id` `unknown`: the Layer 3 identity chain knew `nct_id`, `pubtator_id` and `rsid` but not `pmid`; added. Verified live after the fix, one BRCA1 run: 0 `unknown`, GO citations `GO:0000724`, `GO:0006281`, `GO:0006282` each to `https://www.ncbi.nlm.nih.gov/gene/672`, 16 sources, 14.3s.
- 2026-09-20 03:15: the copy experiment did NOT confirm the inference. With develop's `tests/conftest.py` and manifest copied into the worktree, the full suite returned `3 failed, 5022 passed`: the MCP production-mount test still fails in the worktree's full run, and the copied manifest, paired with the branch's older `docs/build/Debugging_guide.md`, fails two coverage arms of its own. So whether a merge onto current develop clears the MCP failure is UNESTABLISHED; what is established is that it passes alone, passes with its whole directory (82 passed), fails only inside this worktree's full run, and does not fail in the main tree's full run at `079fe42`. The lead's table above attributes it to `a90ef25`; this run could not reproduce that attribution and does not assert it. The two copied files were restored to the branch's own content from `6e4aae1` by file write. The next session should merge develop into the branch and run the suite once; that run, not this reasoning, decides item 2.
- 2026-09-19: the stable-prefix byte-equality checks are `tests/system_03_search_agent/harness/test_cache.py::test_prefix_byte_identical_across_differing_dynamic_suffixes`, `tests/system_03_search_agent/synthesis/test_prompt_cache_prefix.py::test_the_stable_prefix_is_byte_identical_across_assemblies`, and the graph-level `test_graph.py::test_every_model_call_carries_the_stable_prefix_as_its_leading_message*`. These are the named check for verify item 5.

## What was wired, file by file

Design decisions, recorded before the code was written (2026-09-20 00:45):

| Decision | Choice | Why |
|---|---|---|
| Disease title for the PubMed term | Never passed; the term is the gene symbol alone | The only disease text available at Plan is the model-extracted mention span, whose boundaries vary between runs of one question (the reason set 8 already keeps trials on the symbol). A MedGen title would need another call. Determinism wins |
| OMIM | Not dispatched | Its record URL is `omim.org`, which the citation contract rejects; see the findings log |
| Follow-up calls in the `plan` event | Declared at Plan time with their `call_id`, inputs filled at Act once the search ids exist | Keeps the plan event's tool list fixed per question shape, keeps the premise gate A1 (one `tool_start` per planned call) and A2 (every start closed) exact. A follow-up whose search returned no ids is closed as `empty` with a summary saying so, with no request made |
| Search results | Contribute no rows to synthesis | An ESearch result is one aggregate record of ids, not a fact |
| PubMed abstracts | `abstract` stripped at shaping; `title` kept, capped by the tool | 11.22 reserved; a title is what a literature citation needs |
| ClinVar summary rows | `title`, `germline_classification`, `accession`, `genes` in that order; `variation_set` dropped | The first field is the cited claim; a nested variation set is not a claim |
| GO template | `gene_go_processes_one` (first written as `gene_go_terms_one` over three edges, narrowed after the live probe), single gene, forced from Plan as a second Layer 1 call flagged `context_only` | See "The GO template" |
| Findings allotment | Lead calls (answer shape) admitted first up to a quota of 10, then one row per call round-robin in handoff order until the 20 cap | Without it the new rows fill every slot ahead of the graph answer. The 20 cap value is untouched |
| Existing Layer 1 order (L-01 shape 2) | List columns sorted by CURIE before emission and in the fold | In scope by the coordinator's message; a two-line, deterministic fix |

| File | Change |
|---|---|
| `src/system_03_search_agent/core/graph.py` | Imports `breadth_plan`, `entity_param_bindings`, `CypherTemplate`, `gene_go_terms_template`, `matched_shapes`. `_PlannedToolCall` gains `template` and `context_only`; `_PlannedNcbiEfetchToolCall` and `_PlannedLayerToolCall` gain `purpose`; new `_PlannedFollowUpCall(tool_call, purpose, source_purpose)`. New `_BREADTH_FOLLOW_UPS`, `_BREADTH_SEARCH_PURPOSES`, `_BREADTH_DROPPED_PURPOSES` (OMIM), `_BREADTH_ROW_CAP` (5), `_LEAD_FINDINGS_QUOTA` (10), `_GO_SHAPES`, `_BREADTH_FIELDS_BY_PURPOSE`. New `_planned_from_breadth`, `_build_breadth_calls(gene_symbol)`, `_build_planned_go_terms_call(gene_curie, query_class)`, `_search_ids`, `_follow_up_planned_call`, `_empty_follow_up_outcome`. `plan_node` appends the breadth calls after set 8's calls and the GO call unless the question's own shape is a GO shape. `_execute_planned_call`'s `ncbi_efetch` branch: search purposes contribute no rows, breadth purposes are shaped by `_ncbi_efetch_output_to_structured_fields(output, purpose)`, and a last-resort `except Exception` boundary matching the four other tools. `act_node` runs two stages and re-reads the ceiling before each follow-up. `_answer_call_ids` skips `context_only`. `_layer2_citation_for_synth_finding` narrows the raw output to the matched record. `write_node` passes `lead_quota=_LEAD_FINDINGS_QUOTA`. The Layer 1 dispatch passes `template=` only when one is set and carries the same last-resort boundary as the other branches. New `_row_behind_synth_finding`, used by `_curie_for_citation`, `_graph_snapshot_version_for_citation` and `_entity_name_for_citation`; `pmid` added to the Layer 3 citation identity chain |
| `src/system_03_search_agent/synthesis/findings.py` | `build_synth_findings(..., lead_quota=None)` and `_allot_with_lead_quota`: lead rows first up to the quota, then one row per call per round in arrival order with the lead leftover as the last queue. Every caller without `lead_quota` is unchanged |
| `src/system_03_search_agent/tools/cypher_templates.py` | `CypherTemplate.go_attribution_param`; `_GENE_GO_EDGES` asserted documented at import; `gene_go_terms_template(gene_param)` producing `gene_go_processes_one`; added to `all_template_examples()` so the validator and ORDER BY arms cover it |
| `src/system_03_search_agent/tools/cypher_query.py` | `cypher_query(harness, tool_input, *, template=None)` and `_run_pipeline(..., forced_template)`; the attribution CURIE read from `entity_bindings[template.go_attribution_param]` and passed to `to_output_rows`; `_fold_curies` sorted by CURIE (L-01 shape 2) |
| `src/system_03_search_agent/tools/cypher_provenance.py` | `_iter_entities` sorts a vertex-only list column by `(CURIE, internal id)`; a path (carries edges) keeps its order (L-01 shape 2) |
| `tests/system_03_search_agent/core/test_breadth_wiring.py` | New, 18 tests, see the verify surface |
| `tests/system_03_search_agent/core/test_run.py`, `tests/system_03_search_agent/core/test_graph.py` | Nine count assertions that pinned set 8's plan size now pin the new exact values (10 planned, 5 dispatched pairs, the exact tail of tools and layers); see the findings log entry of 02:10 |

Not touched: `breadth_plan.py`, every tool schema, `call_budget.py`, `_MAX_CITATIONS_PER_ANSWER`, the E-utilities rate, `.claude/`, `CLAUDE.md`, `DECISIONS.md`.


## The GO template

`cypher_templates.gene_go_terms_template(gene_param)`, name `gene_go_processes_one`:

```
MATCH (a:Gene {id: $e_NCBIGene_672})-[:participates_in]->(x:BiologicalProcess) RETURN x ORDER BY x.id LIMIT 100
```

How it establishes which gene carries the annotation: the template binds exactly one parameter, the anchor gene, and traverses that gene's own `participates_in` edge for one hop. Every `x` it returns is therefore reached through an edge whose source is the bound gene, by the shape of the query, and cannot be another gene's term. `CypherTemplate.go_attribution_param` names that parameter; `cypher_query._run_pipeline` reads the bound CURIE from `entity_bindings[go_attribution_param]`, the one mapping from parameter name to CURIE, and hands it to `to_output_rows(go_attribution_curie=...)`. Nothing reads a column position, and the model path and every other template pass `None`, so review F-01's rule holds: a GO vertex is cited only on this explicit say-so.

N-04 stays dormant: `_build_planned_go_terms_call` binds `[gene_curie]` alone, the first Gene CURIE the question resolved, and the template's own test pins that two bound genes never produce it.

Live evidence, 2026-09-20 01:15, BRCA1: 40 rows, the first two `GO:0000724` "double-strand break repair via homologous recombination" and `GO:0006281` "DNA repair", each `source_url` `https://www.ncbi.nlm.nih.gov/gene/672` with `_cited_via_gene_curie` `NCBIGene:672`. The control in the same test file runs the same vertex through the model path with no template and shows it stays uncited (`status` `empty`).

Why one edge: see the findings log entry of 01:15. AGE rejects a relationship-type alternation, so the molecular activities (`actively_involved_in`, 19 rows live) and cellular components (`located_in`, 16 rows live) are not traversed; each would be a further single-edge call.

## Call counts per question shape

Measured, not summed: `call_budget.charge_one_call` was wrapped in the live runs, so the figure is the ceiling's own count, including Think's live resolution and Write's disease-name resolution, which the ceiling also counts. Cold means the in-process symbol and disease caches were empty (the first run of a question in a process); warm means an earlier run had filled them.

| Question shape | Example | Planned calls | Layer 2 and 3 charges, cold | Warm | Ceiling |
|---|---|---|---|---|---|
| Gene, disease shape | Which diseases are associated with BRCA1? | 10 | 11 | 8 | 20 |
| Gene, variants-to-diseases shape | What diseases are caused by variants in the HNF1A gene? | 10 | 11 | 8 | 20 |
| Gene plus a disease mention | Variants in GCK causing MODY | 10 | 17 | 8 (6 when the PubMed search failed) | 20 |
| Disease only | What genes are associated with MODY? | 1 | 0 | 0 | 20 |
| Gene plus one rs id | Show the dbSNP record for rs28934578 in TP53 | 12 | 12 | 11 | 20 |

By family on the worst run (GCK plus MODY, cold, 17): E-utilities 12, Datasets 2, PubTator3 2, ClinicalTrials.gov 1. The wiring's own share is fixed at five per gene question (two searches, an abstract fetch, a PubTator3 publications call, a ClinVar summary); the rest is set 8's calls and resolution.

Not measured, stated by arithmetic: a gene plus a disease mention plus two rs ids, cold, would be about 17 plus 6 (two dbSNP pairs, two LitVar2), which crosses 20. The ceiling then degrades in PLAN order, and the breadth calls are planned last so they are refused first; the plan is the same on every run, but Think's charge count is not (17 cold against 8 warm), so on that one shape a cold run and a warm run could admit different tails. No measured question reached the ceiling.

## Latency

Two wired measurements exist and only the second is usable. The first (18 runs) overlapped the full test suite on the same machine, and the question that plans NO new call ("What genes are associated with MODY?", one graph call on both trees) ran 14.9s median against 8.8s on the baseline, which shows the confound. It was re-run with nothing else on the machine.

Local, in-process, real services and real model tiers, three runs per question, medians with the three sorted values, in seconds:

| Question | Depth | Wired, clean | Baseline `6e4aae1` |
|---|---|---|---|
| Which diseases are associated with BRCA1? | researcher | 16.6 (13.8, 16.6, 23.6) | 6.2 (5.7, 6.2, 11.3) |
| What diseases are caused by variants in the HNF1A gene? | researcher | 15.9 (11.8, 15.9, 21.4) | 14.9 (7.3, 14.9, 19.4) |
| Variants in GCK causing MODY | researcher | 13.9 (12.0, 13.9, 20.7) | 14.5 (13.4, 14.5, 15.9) |
| What genes are associated with MODY? | researcher | 15.3 (10.4, 15.3, 19.0) | 8.8 (6.6, 8.8, 9.8) |
| Which diseases are associated with BRCA1? | plain_language | 8.4 (8.1, 8.4, 10.3) | 7.4 (5.7, 7.4, 8.1) |
| Show the dbSNP record for rs28934578 in TP53 | researcher | 12.3 (7.5, 12.3, 21.7) | not measured |

Reading it honestly: the MODY-genes question plans the identical single graph call on both trees and still differs by 6.5s in median, so run-to-run variance in the synthesis model is of the same order as any cost the wiring adds, and three runs per question cannot separate the two. What the wiring adds by construction is one extra round trip (the second stage, about a second of NCBI and PubTator3 time) and a longer synthesis prompt (17 to 19 admitted findings against 11 to 20 before). The slowest wired run was 23.6s against the plan's stated 53s and the coordinator's 30.3s; the wired medians (8.4 to 16.6) sit inside the coordinator's develop range of 7.8 to 16.1. Nothing here is a regression a reader would notice against the 2026-09-14 figures, and nothing here is proof the wiring is free.

## Determinism evidence

Two sets are recorded per run: the ADMITTED findings (what reached the synthesis prompt after the allotment, recorded by wrapping `build_synth_findings`) and the CITED sources (the `citation` events, which exist only where the model's prose grounded a claim on a finding). Retrieval determinism is the first; the second also depends on the model's choice of which context findings to cite.

Offline (`test_three_runs_with_shuffled_ids_produce_one_plan_and_one_source_set`): three runs with the fakes returning the PubMed and ClinVar ids in a different shuffled order each time produce one plan, one cited source set, and identical follow-up inputs (`["30000006", "30000005", "30000004", "30000003", "30000002"]` and `["12", "11", "10", "9", "8", "7", "6", "5", "4", "3"]`).

Live, clean measurement, three runs each, source ids as the citation events carry them (measured before the identity fix, so `unknown` still appears where a GO row or a publication row was cited):

| Question | Admitted sets seen | Cited sets seen | The cited set |
|---|---|---|---|
| Which diseases are associated with BRCA1? (researcher) | 1 of 3 (17 rows) | 1 of 3 (14) | 4880487, 4880627, 4882953, 4883311, 672, @GENE_BRCA1, MedGen:C0346153, MedGen:C2676676, MedGen:C3280442, MedGen:C4554406, NCT00590109, NCT00597987, NCT00617656, unknown |
| What diseases are caused by variants in the HNF1A gene? | 1 of 3 (18) | 1 of 3 (15) | 4856659, 4856802, 6927, @GENE_HNF1A, ClinVar:1025247, ClinVar:1026109, ClinVar:1033090, MedGen:C0011854, MedGen:C0011860, MedGen:C0342276, MedGen:C1838100, MedGen:C2675866, MedGen:C3888631, NCT00760331, unknown |
| Variants in GCK causing MODY | 2 of 3 | 2 of 3 (18, 19) | Runs 1 and 3: 2645, 4881257, 4881317, @GENE_GCK, ClinVar:1028584, ClinVar:1098819, ClinVar:1172896, ClinVar:1188508, ClinVar:1210150, ClinVar:129144, ClinVar:129147, ClinVar:1299600, ClinVar:1301411, ClinVar:1303095, GO:0001678, MedGen:C0342277, NCT01029795, unknown. Run 2: the PubMed ESearch itself returned `error` (`search: 0 id(s)`), both PubMed follow-ups closed `no ids to fetch: the pubmed_search search did not complete`, and the two freed slots went to ClinVar:1338576 and NCT01238380 |
| What genes are associated with MODY? | 1 of 3 (13) | 1 of 3 (13) | MedGen:C0342277, MedGen:C1833382, MedGen:C1838100, MedGen:C1852093, MedGen:C4014962, MedGen:C4225299, MedGen:C4225365, NCBIGene:26060, NCBIGene:2645, NCBIGene:3172, NCBIGene:3651, NCBIGene:3767, NCBIGene:6927 |
| Which diseases are associated with BRCA1? (plain language) | 1 of 3 (17) | 1 of 3 (14) | the same set as the researcher row |
| Show the dbSNP record for rs28934578 in TP53 | 1 of 3 (15) | 1 of 3 (12) | 4865882, 4865883, 4865884, 4880485, 7157, @GENE_TP53, NCT02289326, NCT02612285, NCT03149679, NCT03466034, rs28934578, unknown |

The first (contended) wired measurement agreed on every admitted set, and its one cited-set difference was run 3 of the GCK question citing two more of the admitted PubMed papers (42684983, 42731429): the model's choice among identical findings.

Baseline `6e4aae1`, same script, three runs each: one admitted set and one cited set per question, HNF1A at 18 sources on all three runs. L-01's variance did not reproduce in three local runs; the shape 2 mechanism is fixed regardless, by the sort, and shape 1 stays unestablished.

What this establishes: the retrieval half of the requirement holds. The same question admits the same findings on every run, and the one measured exception was a live NCBI search failure that the answer degraded from and the tool result disclosed. What it does not establish: that the CITED set is identical on every run, because a citation exists only where the model grounded a claim, and that choice varied once in 21 wired runs. Closing that gap is a Write-side decision (cite every admitted finding deterministically, or keep prose-grounded citations) and belongs to the product owner.

## Verify surface

### Item 1: new tests, red first

File: `tests/system_03_search_agent/core/test_breadth_wiring.py`, 16 tests. Run against the unwired code at `6e4aae1` plus only the test file, 2026-09-20 00:55:

```
16 failed in 27.01s
```

Every one of the 16 failed (names in the run's short summary: the plan, the OMIM exclusion, the context-only GO call, the follow-up ids, the failed search, the raising follow-up, the abstract, the three-run determinism, the GO template, the forced-template citation, the two-gene guard, the two L-01 list-order arms, the multi-record Layer 2 citation, and the two allotment arms). Two fixture errors in the first red run (the `Finding` constructor's three required fields) were corrected before the green run. Three of my own assertions were also corrected before the green run and are recorded rather than hidden: the planned-call count is 10, not 11 (one primary graph call, five `ncbi_efetch`, two `pubtator_annotate`, one trials, one GO graph call; my arithmetic was wrong in three places), the allotment test's context slice starts after the eleven lead rows the presentation sort places first, and two fixtures (a PubTator publication URL that the schema pins to the PubMed record page, and a fake harness that needed `call_tier`). No assertion was weakened; the count corrections tightened what the arms pin.

Green, same file, after the wiring, 2026-09-20 00:50:

```
16 passed in 2.86s
```

Two more arms were added later in the run for the two citation identity defects the live dump exposed (findings log, 02:20), each run red before its fix and green after, taking the file to 18 tests. Final run of the file with the two answer-quality files that share `build_synth_findings` and `_answer_call_ids`, 2026-09-20 02:25:

```
60 passed in 3.90s
```

### Item 3: ruff over the whole repository

`venv/bin/ruff check` with no path argument, from the worktree root, after the last edit:

```
All checks passed!
```

### Item 4: isort

`venv/bin/isort --check-only src tests`, after the last edit:

```
Skipped 2 files
```

(exit 0; the two skipped files are isort's own skip list, unchanged.)

### Items 6 and 7: determinism and the call ceiling

See "Determinism evidence" and "Call counts per question shape" above.

### Item 5: the stable prefix stays byte-identical

The named checks are the byte-equality arms that hash or compare the assembled prefix across two requests whose dynamic suffix differs: `harness/test_cache.py::test_prefix_byte_identical_across_differing_dynamic_suffixes` and `::test_none_and_empty_list_produce_byte_identical_prefixes`, `synthesis/test_prompt_cache_prefix.py::test_the_stable_prefix_is_byte_identical_across_assemblies`, `core/test_personalization_premise.py::test_p7_the_stable_prefix_is_byte_identical_as_depth_varies` and `::test_p7b_...as_session_memory_varies`, `core/test_cq_routing_premise.py::test_p10_the_few_shot_block_does_not_move_the_stable_prefix`, and the three `core/test_graph.py::test_every_model_call_carries_the_stable_prefix_as_its_leading_message*` and `::test_stable_prefix_still_reaches_every_graph_node_call_when_a_tool_runs` arms. Run together on the wired code, 2026-09-20 01:20:

```
9 passed in 6.96s
```

Why nothing could have moved it: the wiring adds no system instruction, no tool schema and no static schema text. `cypher_query`'s new `template` argument is keyword-only on the Python function and is not on `CypherQueryInput`, so `REGISTERED_TOOL_SCHEMAS` is byte-identical; every new retrieved row enters through `findings`, which is the dynamic suffix.

One product change came out of the red run rather than out of the design: the raising-follow-up arm showed the `ncbi_efetch` branch of `_execute_planned_call` had no last-resort catch (the four other Layer 2/3 tools had one), so a fault below the tool's never-raises boundary escaped `act_node` instead of degrading one call. It now has the same boundary as the others.

### Item 2: the full Python suite, run by the lead

Run by the lead in this worktree at 2026-09-20 01:15, because the worker had not reached
this item and it is the gate that decides whether the change merges.

```
venv/bin/python -m pytest tests -q -p no:cacheprovider
2 failed, 5023 passed, 176 skipped, 1 xfailed, 8 warnings in 214.77s (0:03:34)
```

CORRECTED after the worker ran its own suite. The lead first wrote that both failures
were two of the three CI causes this branch predates, and called that "checked rather
than assumed". Only ONE of them is established as such.

What the lead actually checked was that develop's guard is ABSENT here:
`grep -c "_user_db_engine_matches_the_ambient_url" tests/conftest.py` returns 0. That
shows the guard is absent and nothing more. Reading it as "therefore both failures are
the known ones" is inferring a cause from an absence, which is the same shape as the
confident-sentence defects this repository has recorded before.

The worker then tested the inference directly: it copied develop's `conftest.py` and
manifest into this worktree and the MCP failure DID NOT clear. So:

| Failure | Status |
|---|---|
| `test_debugging_guide_coverage.py::test_no_repurposed_file_keeps_a_stale_row` | Explained. The stale `contracts/events.py` guide row from UI fix 11.16, regenerated on develop in `a90ef25`, and this branch predates it |
| `test_phase_4_1_production_mount.py::TestProductionMount::test_the_real_shipped_app_answers_a_real_mcp_call_end_to_end` | UNEXPLAINED. Develop's fix does not clear it here. It passes alone, and passes with its own directory (82 passed), inside this worktree; the main tree's full run at `079fe42` is clean. So it is an interaction visible only in this branch's full run, and its cause is unknown |

Item 2 of the verify surface is therefore NOT MET on this branch as it stands. It needs a
full-suite run after develop is merged in, and if the MCP failure survives that merge, its
cause must be established before anything is merged the other way.

5023 passed against the 5007 on develop is the new tests in `test_breadth_wiring.py`.
That the wiring introduces no failure of its own is NOT established while the MCP
interaction is unexplained.

### Merge judgement, by the lead

HOLD. Do not merge unattended. The reasons are about confidence and timing, not about
anything found wrong.

- The worker's own merge judgement is still "Pending". The author of a 726-line change to
  the hot path of every query has not signed it off, and the lead will not sign off on
  the author's behalf.
- The worker found two citation identity defects late in the run and added arms for them.
  That is a change still being iterated, not a settled one.
- Merging deploys to the develop app the product owner tests in the morning, and it
  changes what every query retrieves. No live browser check is possible unattended.
- One merge was already reverted tonight for shipping ahead of complete verification. The
  same mistake on a larger change is not worth the hours saved.

What the next session should do: merge develop into this branch and re-run the full
suite. Expect the manifest failure to clear; do NOT expect the MCP one to, because
that was tested and it did not. If it survives, establish why it appears only in this
branch's full run before merging.

## Not done, with reasons

| Item | Reason | Owner |
|---|---|---|
| OMIM search and summary | Never dispatched: an OMIM record's URL is `omim.org`, which the citation contract rejects, so its rows could only feed uncited claims. Needs the locked Section 6.2 URL template or the locked citation pattern widened | Product owner (locked documents) |
| GO molecular activities and cellular components | AGE rejects the edge alternation, so the GO template traverses `participates_in` alone; the other two edges are two further single-edge graph calls, each another chip and another context queue in the allotment | Whoever next touches `cypher_templates` |
| PubTator3 publications on a heavily published gene | The planner's five highest PMIDs are newer than PubTator3's index for BRCA1, so that follow-up errors and degrades; the fix changes `breadth_plan`'s selection rule | Tool layer (`breadth_plan`) |
| Disease title in the PubMed term | Left off for determinism (the model-extracted mention varies); a MedGen title would cost another call | Product owner, if a disease-scoped literature search is wanted |
| Abstract sentences as evidence (11.22) | Reserved by product-owner decision of 2026-09-14; `abstract` is stripped before synthesis and no quote check was re-added | Product owner |
| L-01 shape 1 (a whole graph result missing on 2 of 6 live runs) | Unestablished from the recorded data; the measurement script needs to capture `tool_result` payloads and the answer text. The wiring's own live runs record both and show no such run in 18 wired runs, which bounds it loosely, not to zero | Coordinator |
| The 20-citation cap, the provenance note, the trust-line wording, any release | Reserved for the product owner by the brief | Product owner |
| Any change to `CLAUDE.md` test counts, `DECISIONS.md`, the board or the plan | Outside the worktree; the new test count is 16 more than the 5184 the docs state | Coordinator at checkpoint |

## Merge judgement

Written by the worker at 2026-09-20 03:05, after the lead's HOLD above, which stands as the lead's decision; this is the author's sign-off the lead asked for. The two late citation identity arms are settled: both were red, both are green, and the fix was verified live (findings log, 02:20).

The worker's own full-suite run on the final code, 02:45: `2 failed, 5023 passed, 176 skipped, 1 xfailed, 8 warnings in 259.70s`, the same two failures the lead names, and the main tree at `079fe42` runs `5007 passed, 176 skipped, 1 xfailed`, no failures, so both are develop's `a90ef25` fixes absent from this base. To prove that a merge clears them rather than infer it, develop's `tests/conftest.py` and the manifest, the only two files a merge would add under `tests/`, were copied into the worktree and the suite rerun; it returned `3 failed, 5022 passed` (findings log, 03:15), so that inference is unestablished and item 2 is NOT met on this branch as it stands: 5023 of 5025 collected pass, and the two failures are not in code this change touches, but the run that decides item 2 is the suite on this branch after develop is merged in, which this session could not do without a git state change.

Judgement: safe to merge into `develop` once that merged-branch suite run is clean, and the lead's HOLD is right about the timing. Three things said plainly.

- Retrieval is deterministic and broad, measured: one admitted findings set per question across every clean live run, ClinVar, PubMed and the gene's GO processes beside the graph, trials and the gene record, every new fact cited to a host-pinned NCBI page. The 20 cap, cite-or-refuse, the grounding gate and the stable prefix (nine byte-equality arms) are untouched.
- Not proven: that the CITED set is identical on every run. A citation exists only where the model grounded a claim, and that choice varied once in 21 wired runs among identical findings. A Write-side product decision, not a retrieval defect, and the likeliest mechanism behind L-01 shape 1, which stays unestablished.
- Two degradations ship disclosed: PubTator3 cannot annotate BRCA1's five newest PMIDs, so that one follow-up closes as an error, and OMIM is not searched. Both are recorded with owners under "Not done".

Not for a live deployment tonight without the product owner seeing one answer first: the answer's composition changed (ten lead rows, then one row per source per round), the one decision this run took inside the reserved cap, and this report is the only review it has had. Merge develop into the branch, confirm the suite is clean, merge to develop, and let the product owner test on develop per the UI fix loop.
