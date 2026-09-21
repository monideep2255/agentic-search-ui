# Variant-to-disease detail: phase 1 findings and phase 2 plan

Written 2026-09-14 by the `detail` agent. Phase 1 was read-only in the repository. Every graph query below ran through `graph_connection.execute_cypher` over `GRAPH_QUERY_URL`, parameterised, with a 30 second timeout and a small LIMIT. Raw records: `probe_out*.jsonl` beside this file. Reference captures: `scratchpad/ref/`.

## Table of contents

- [1. The claim was false: the graph links variants to diseases](#1-the-claim-was-false-the-graph-links-variants-to-diseases)
- [2. Three more facts that shape the design](#2-three-more-facts-that-shape-the-design)
- [3. The templates, measured live](#3-the-templates-measured-live)
- [4. How rows become findings, citations and the table](#4-how-rows-become-findings-citations-and-the-table)
- [5. The disease-anchored question needs a Think change](#5-the-disease-anchored-question-needs-a-think-change)
- [6. Reference prototype, element by element](#6-reference-prototype-element-by-element)
- [7. The model](#7-the-model)
- [8. Phase 2 work list, files, tests](#8-phase-2-work-list-files-tests)
- [9. Decisions for main or the product owner](#9-decisions-for-main-or-the-product-owner)
- [10. Risks and blocked-stops](#10-risks-and-blocked-stops)
- [11. Addendum: decisions received from main (2026-09-14)](#11-addendum-decisions-received-from-main-2026-09-14)

## 1. The claim was false: the graph links variants to diseases

Path: `(v:SequenceVariant)-[:has_phenotype]->(d:Disease)`. The edge carries `source: "ClinVar"`, `agent_type: "manual_agent"`, `knowledge_level: "knowledge_assertion"`, and `source_url` = the variant's own ClinVar variation page. So the association is a ClinVar assertion, cited to the ClinVar record that makes it.

HNF1A (`NCBIGene:6927`), every query parameterised:

| Probe | Rows | Elapsed |
|---|---|---|
| variants of HNF1A (`is_sequence_variant_of`) | 1212 | 1.1 s |
| variant-to-disease pairs via `has_phenotype` | 2075 | 1.5 s |
| every target of those edges is labelled `Disease` | yes (2075 of 2075) | 1.4 s |
| distinct variants with a disease / distinct diseases | 1158 / 36 | 1.1 s |
| `close_match`, `exact_match`, `gene_associated_with_condition` from or to a variant | 0 each | under 3 s |

Why set 9 got it wrong. F9-16 read one variant NODE (`MATCH (v:SequenceVariant) RETURN v LIMIT 1`), found no disease field, and concluded no mapping exists. The mapping is an EDGE. F9-05 relied on `cypher_templates.py`'s own docstring, which says the graph has no variant-to-disease edge; the docstring relied on the reference doc, which lists `has_phenotype` only as `Disease to PhenotypicFeature`. Nobody queried. `graph_schema_constants.EDGE_ENDPOINTS["has_phenotype"] = ("Disease", "PhenotypicFeature")` is therefore incomplete: the live graph carries `SequenceVariant to Disease` rows under the same label.

## 2. Three more facts that shape the design

Disease names are not in the graph. A Disease node's `name` holds the source vocabulary ("OMIM", "MeSH", "MedGen", "OMIM included"), the F-2.1-B07 defect. So a name-contains search, which is how the reference prototype finds its MODY subtypes, returns 0 rows here (probed: `d.name =~ '(?i).*maturity-onset diabetes.*'`, 0 rows). Names come from the existing Layer 2 path `synthesis/disease_names.resolve_concept_ids` (one ESearch on `[ConceptId]` plus one ESummary, cap 25 ids per call, cached). Verified live: C0342276 "Maturity-onset diabetes of the young", C1838100 "Maturity-onset diabetes of the young type 3", C3888631 "Monogenic diabetes", C2675866 "Type 1 diabetes mellitus 20", CN074294 "Nonpapillary renal cell carcinoma", C0011860 "Type 2 diabetes mellitus". These are exactly the six the reference lists for HNF1A.

Two MedGen concepts are ClinVar placeholders, and they are the most frequent targets: C3661900 "not provided" (730 of HNF1A's 2075 pairs) and CN169374 "not specified" (193). The reference prototype's graph does not carry them. Shown verbatim they would put "not provided" in a disease cell. Proposed: a closed, documented set of placeholder concept ids excluded from the second cell and the disease list, the same shape as `findings._STRING_SENTINELS`. This is decision D2 below.

The general MODY concept has no gene edges. `gene_associated_with_condition` into C0342276 returns 0 genes; into C1838100 (MODY3) returns HNF1A; into CN074294 returns 7 genes. The reference gets its six-row Gene / Associated disease table by matching six MODY subtype concepts by name. Our honest equivalents are in section 5.

Tool row model. `cypher_provenance.to_output_rows` emits one output row per entity per RETURN column, then `_dedupe_by_cited_record` collapses by `source_url`, so `RETURN v, d` loses which disease belonged to which variant. A list column of vertices (`collect(DISTINCT x)`) IS decoded (`_iter_entities` walks lists), so a disease list per variant row reaches the tool as citable Disease rows. The pairing has to be carried explicitly; section 4 says how.

## 3. The templates, measured live

All four pass `validate_cypher` and `_check_entity_binding` offline (the validator injects `LIMIT 100` after the ORDER BY, the AS clause is derived from the column count). Timings at LIMIT 100 through the HTTPS service:

T1, gene variants with their diseases ("diseases caused by variants in X", "variants in X"):

```
MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(a:Gene {id: $e_one})
MATCH (v)-[:has_phenotype]->(x:Disease)
WITH v, collect(DISTINCT x) AS xs
RETURN v, xs ORDER BY v.id
```

HNF1A 1.8 s, GCK 1.9 s, BRCA1 3.7 s. Stable order by variant id. The `xs` column decodes to Disease vertices with MedGen `source_url`s.

T2, variants in X causing Y (gene and disease both bound):

```
MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(a:Gene {id: $e_one})
MATCH (v)-[:has_phenotype]->(x:Disease {id: $e_two})
RETURN v, x ORDER BY v.id
```

GCK plus C0342276: 100 rows in 1.4 s. `_traversed_edge_type_by_column` pins column `x` to `has_phenotype`.

T3, genes for a disease through the gene edge (exists today as `disease_genes_one` and `_many`): 0.5 s. Per-concept results above.

T5, genes for a disease through its variants, with a per-gene variant count:

```
MATCH (x:Gene)<-[:is_sequence_variant_of]-(v:SequenceVariant)-[:has_phenotype]->(a:Disease {id: $e_one})
WITH x, count(DISTINCT v) AS variant_count
RETURN x, variant_count ORDER BY x.id
```

C0342276: 15 genes in 1.1 s (GCK 436 variants, ABCC8 469, HNF1A 380, HNF4A 282, HNF1B 210, KCNJ11 164, PDX1 42, PAX4 3, CEL 2, and six with 1). This is the graph's own answer to "genes associated with MODY", and its counts are the reference's "most disease-causing variants" column.

Nothing here approaches the 30 second budget; the worst was BRCA1 at 3.7 s.

## 4. How rows become findings, citations and the table

The fold. A `CypherTemplate` gains one optional field, `fold: tuple[str, str, str] | None` = (anchor column variable, list column alias, field name), for example `("v", "xs", "clinvar_condition_ids")`. On the template path only, `_run_pipeline` parses the two named columns of each raw row (`parse_agtype`, already imported) and, on the anchor's shaped output row, sets `fields[field_name]` to the list of the list column's vertex CURIEs, capped at 12 entries, in the graph's order. The Disease rows are still shaped and cited as their own records, exactly as today. Nothing changes on the model path, and a template without `fold` behaves as before. The value is retrieved data: the CURIEs of the Disease nodes this ClinVar record's `has_phenotype` edges point at, and the row cites that record. `_pick_representative_field` prefers `name` and treats a list as a container, so the variant's citable value is unchanged (the HGVS name, or the CURIE fallback for intronic names).

Findings. The variant rows (ClinVar) and the disease rows (MedGen, `curie_fallback`, resolved to titles by the existing `apply_resolved_disease_names`) enter `build_synth_findings` in tool order: v1, its diseases, v2, its diseases. Admission is unchanged: Layer 2, then Layer 3, then Layer 1, capped at `MAX_FINDINGS_PER_PROMPT` 25 and `_MAX_CITATIONS_PER_ANSWER` 20. So an HNF1A answer cites roughly 13 to 16 graph records: some variants, some diseases, plus the gene and the trials. Names for the second cell are resolved separately from the fold ids of the CITED variant rows (one extra `resolve_concept_ids` call, cached, at most 25 ids), so a disease that was capped out of the findings list can still be named in a cell, cited to the ClinVar record whose row it sits in.

The table. `answer_layout.TABLE_COLUMNS["SequenceVariant"]` becomes `("clinvar_condition_ids", "Variant", "Associated disease(s)")`, and `table_second_cell` takes a `condition_name_by_curie` map: it maps the row's ids to titles through `readable_disease_name`, drops placeholder ids (D2) and unresolved ids (so no raw MedGen code ever reaches answer words), and joins with "; ". `_answer_tokens.listing` renders the group as a table when at least one row has a non-empty cell; a row whose conditions were all placeholders gets an empty cell rather than a phrase (an empty cell asserts nothing). Each row's marker set is the variant's own marker plus the markers of any Disease finding in the answer that the cell names, so every name in a cell is cited either to its MedGen record or, when that disease was not admitted as a finding, to the ClinVar record the row already cites. The frontend already renders `table_header` and `table_row` with two `cells` and chips per row (`AnswerScreen.tsx` lines 813 to 874); `cells` is contract-bounded at 2, so the reference's redundant Gene column is not added.

The disease list. A code-built "Diseases linked to HNF1A variants" heading over the admitted Disease findings, each a `list_item` with its resolved title and MedGen marker, placed before the variant table. Both headings are code-built, like the existing "records found" headings.

The summary sentence. `answer_summary_sentence` gains the fold count: "Found 13 sequence variant records for HNF1A, of 1212 available, linked to 6 diseases: Maturity-onset diabetes of the young [3], ... [n]." The variant count is the number of cited variant findings, the disease count is the distinct non-placeholder ids across their folds, and each named disease carries its Disease finding's marker; a disease with no admitted finding is counted, not named. Every number is retrieval bookkeeping, as today.

Plain language keeps its three paragraphs; the disease titles reach the model as findings (already the case for `curie_fallback` rows), so the paragraphs can name them.

Trust tier. The Disease rows from `xs` arrive with no `traversed_edge_type` (the column is an alias, not a variable) and classify from the bare `Disease` type. On T2 the `x` column pins `has_phenotype`. To be checked in phase 2 against `trust.py`'s high-risk table; if `has_phenotype` is not listed there, the rows classify as they would for a bare lookup, which understates the risk of a variant-to-disease mapping and should be raised as a finding rather than patched by widening the table (F-2.2-A-05's reasoning).

## 5. The disease-anchored question needs a Think change

`_confirm_extracted_entities` live-confirms GENE spans only; a span typed `disease` is schema-valid and contributes nothing (its own docstring records the gap). `resolve_symbol_to_curie("MODY")` returns None, so the gene-shaped fallback does not misbind it either. Today "What genes are associated with MODY?" therefore binds no entity, and `cypher_query` returns its "no entity could be identified" error. The baseline will be measured before the change in phase 2.

So the "genes associated with" shape cannot route without a live disease confirmation primitive. Proposed, bounded and deterministic:

- `resolve_disease_mention_to_curies(mention)` in `core/graph.py` beside `resolve_symbol_to_curie`: ESearch `db=medgen`, term `<mention>[title]`, `retmax` 8; ESummary; keep a record only when its title contains the mention as a whole word (case-insensitive) or, for a multi-word mention, every content word; return the kept concept ids as `MedGen:` CURIEs, sorted, at most 8. Nothing unconfirmed is bound.
- Measured live: `MODY[title]` returns 8 concepts, all MODY subtypes or MODY-named (types 1, 2, 3, 4, 13, 14, the Fanconi renotubular syndrome 4 with MODY, and "Impaired glucose tolerance in MODY"). The general concept C0342276 is NOT in that set, since "MODY" is a synonym there, not in the title.
- Think binds these as several Disease CURIEs; `select_template` already handles several anchors of one label (`disease_genes_many`, `RETURN a, x ORDER BY a.id, x.id`). With a fold `("x", "as", "medgen_condition_ids")` over `collect(DISTINCT a)` the gene rows carry which subtype each gene is linked to, which is the reference's Gene / Associated disease table (`TABLE_COLUMNS["Gene"]`). Expected rows: HNF1A for MODY3 (probed), and the others to be measured in phase 2.
- The variant path (T5) is the alternative when the gene edge has no rows for the bound concepts: the same fold shape, second column the variant count. Whether to run T5 as a fallback inside the tool, or as a second template shape ("genes with variants causing Y"), is decision D3.

Risk named: a disease mention can be ambiguous ("diabetes"). The title-containment rule plus the cap of 8 bounds the blast radius, every bound CURIE is a real MedGen record, and the summary names the resolved titles so the reader sees what was bound. This is the same live-confirm-or-nothing rule as genes.

## 6. Reference prototype, element by element

Captured: hnf1a, mody (earlier), gck_activities, gck_pathways, most_variants, mody_processes (this phase). Their model is a different family (product owner: GPT 5.4); ours resolves from environment and is not changed.

| Element in the reference | Reachable how |
|---|---|
| Opening summary that interprets ("primarily to monogenic diabetes and MODY, with one variant also associated with...") | (a) partly: the code-built summary sentence can state the counts and name the diseases with markers. The interpretive ranking ("primarily") needs the per-disease pair counts, which the fold carries, so "most often linked to X (n variants)" is expressible in code. The prose gloss beyond that is (b). |
| Bold key terms | (a) exists: `emphasis` on Researcher prose. |
| Topic heading ("Diseases linked to HNF1A variants", "Variant-to-disease mapping") | (a) code-built headings, this work. |
| Disease list | (a) admitted Disease findings with resolved titles. |
| Variant / disease mapping table, 13 rows | (a) this work; row count bounded by the citation cap (about 13 to 16 graph records per answer), which matches the reference's 13. |
| Gene / Associated disease table (MODY) | (a) with the Think change in section 5; without it, (c). |
| Gene / Molecular activity table (GCK activities) | (a) the existing `gene_activities_one` template as a table, second cell the GO term name, if the GO node's `name` is populated (to be probed; GO nodes have no citable `source_url`, so today they are DROPPED by cite-or-refuse, which is why activities answers are thin: that is the constraint, not the layout). |
| "Summary by functional category" grouping of GO terms | (b) or (c): a category is an ontology fact the graph does not carry; a model grouping is uncited. |
| Pathways (Reactome R-HSA) | (c) no pathway nodes in this graph. |
| Ranked "most disease-causing variants" table with counts | (a) in principle as an aggregate template over `is_sequence_variant_of` and `has_phenotype`, but the question binds no entity and `select_template` requires one; an anchor-free template is a new shape and a new cost profile (a scan over 4.4 M edges). Out of this task; recorded. |
| "Key takeaways" bullets | (b): interpretation, uncited. |
| Notes ("typically derived from ClinVar and MedGen") | (a) as a code-built provenance note the code KNOWS: "Disease names are MedGen titles read live; each variant-to-disease link is a ClinVar assertion cited to its variation record." Never a model note. The reference's hedged "typically" wording is (b). |
| "Showing 20 of 20 total results" | (a) exists: the truncation note and `total_available`. |
| Source chips | (a) exists. |

Nothing in (b) is done in phase 2. Items in (b) are the product owner's decision.

## 7. The model

Our Synth model identity comes from environment configuration (`system-design-patterns` pattern 11) and is not touched. Could it be part of the gap? Only for prose: the grounding gate strips every sentence not contained in a finding, so a stronger writer produces at most more surviving sentences, never a table, a list, a heading or a count, all of which are built in code here. For the elements in (a) the constraint is retrieval and layout, not the model; for (b) any model's output would be stripped by the gate as it stands. A model swap is build phase 7.0's benchmark.

## 8. Phase 2 work list, files, tests

Backend:
- `tools/graph_schema_constants.py`: add `ADDITIONAL_EDGE_ENDPOINTS = {"has_phenotype": (("SequenceVariant", "Disease"),)}` with the measurement recorded; `EDGE_ENDPOINTS` unchanged so `schema_slice` and the stable prefix are untouched (prefix SHA checked before and after with `speed_fix/prefix_sha256.py`).
- `tools/cypher_templates.py`: `fold` on `CypherTemplate`; the guard accepts a hop whose endpoints are in either table; new shapes: `gene_variant_diseases_one` (T1, chosen for "diseases" or "variants" with the gene bound, replacing `gene_variants_one` and the `("Gene","diseases")` hop? No: see D1), `gene_variant_disease_link` (T2, the mixed form), `disease_genes_many` with fold, `disease_variant_genes_one` (T5). Docstring rewritten: the "no variant-to-disease edge" sentence goes.
- `tools/cypher_query.py`: the fold, template path only, after `to_output_rows`, before `_cap_shaped_row`.
- `synthesis/answer_layout.py`: `TABLE_COLUMNS` for SequenceVariant and Gene, `table_second_cell` with the name map and placeholder set, summary sentence with the fold counts.
- `synthesis/disease_names.py`: `PLACEHOLDER_CONCEPT_IDS`.
- `core/graph.py`: the second `resolve_concept_ids` call over fold ids; the disease-list heading; `listing` passing the map and per-row markers; `resolve_disease_mention_to_curies` and its use in `_confirm_extracted_entities` for `disease` spans (section 5).
- `docs/build/Debugging_guide.md` only if a file under `src/` is added; none planned. `docs/data-engineering/Knowledge_graph_on_server_reference.md` and `visualizations/Schema_visualization.md` gain the measured endpoint pair (docs, not locked).

Tests, each populate-checked and mutation-proven:
- template selection: the four new shapes and the unchanged fallbacks; `all_template_examples` still validates; the guard rejects an endpoint pair in neither table.
- parameterisation: every new template's Cypher contains no quoted literal and references only `$e_` names; `_build_params` binds exactly the referenced names.
- the fold: a fixture raw row with a variant and a two-disease list produces one variant row with `clinvar_condition_ids` of length 2 and two Disease rows; the cap of 12; no fold on the model path; a mutation that drops the fold turns the table test red.
- table rows: a fixture answer renders `table_header` plus one `table_row` per variant, cells `[HGVS, "A; B"]`, placeholder ids omitted, unresolved ids omitted, marker ids per row include the variant and the named diseases' findings.
- summary counts: "13 ... 6 diseases" from a fixture; placeholders not counted.
- the frontend unchanged unless the disease-list heading needs a style; existing `.rtab` tests cover the table.

Live proof, 5 runs each with `speed_fix`'s scripts: HNF1A diseases (researcher), GCK MODY variants (researcher), MODY genes (researcher and plain_language), BRCA1 diseases (researcher); rows, distinct diseases, source-set hash per run, elapsed, first sentence; compared with the reference's 13 HNF1A rows and 6 MODY rows.

## 9. Decisions for main or the product owner

D1, which template answers "diseases caused by variants in X". Two readings: the gene's own disease edges (`gene_associated_with_condition`, 6 rows for HNF1A, today's template) or the variants' diseases (T1, the reference's reading). Proposed: the "variants" wording routes T1 ("diseases caused by variants in X", "variants in X", "mutations in X"), and a plain "diseases associated with X" keeps `gene_diseases_one`. Deterministic on the keyword order already in `_SHAPE_KEYWORDS`: when both "variant" and "disease" words appear with one gene bound, T1. "Which diseases are associated with BRCA1?" is unchanged (the unchanged-source-set requirement).

D2, placeholder concepts. Exclude C3661900 "not provided", CN169374 "not specified" and CN517202 "See cases" from cells, lists and counts, as a documented closed set. They are real MedGen records, so this is a presentation rule, not a grounding change. Default if unanswered: exclude, and say so in the code-built provenance note.

D3, the MODY genes path. (i) Think confirms disease spans by MedGen title containment (section 5) and the gene-edge template runs over the bound subtypes; (ii) the variant path T5 as the template for "genes associated with Y" when Y is a single concept, second column the variant count; (iii) both, gene edge first, T5 when it returns nothing. Proposed: (iii). Either way this is a Think change; confirm it is in this task's scope.

D4, the code-built provenance note (section 6, Notes row). Proposed wording, product owner to approve: "Variant-to-disease links are ClinVar assertions, each cited to its variation record. Disease names are MedGen titles read live from NCBI."

## 10. Risks and blocked-stops

- None of the blocked-stop conditions fired: a path exists, no template exceeds 30 s (worst 3.7 s), no row is model-written, no gate, cap or timeout changes.
- Row admission: with variants and diseases interleaved, the 20-citation cap may admit fewer variant rows than the reference's 13 on a gene with many diseases per variant. Measured, not guessed, in phase 2; if it lands short the fix is ordering within the graph call's rows, not a cap change.
- The 37-id resolution in phase 1 failed with a ValidationError (the ESearch term over 37 `[ConceptId]` clauses); production never sends more than 25 and the eight-id call succeeded. Not a defect on the shipped path; noted.
- A phase-1 live run of the full loop was not done because it writes the audit log and interactions table; the MODY baseline is measured first thing in phase 2.

## 11. Addendum: decisions received from main (2026-09-14)

Baseline measured once each in phase 1 with `measure_write2.py` (audit log and tracing off, output in this folder): "What genes are associated with MODY?" refuses in 9.3 s with no source; "What diseases are caused by variants in the HNF1A gene?" answers with the gene's own 6 disease records (gene edge) in 16.8 s, 13 sources.

D2 approved with conditions: a closed, exact-match set on the record's own case-folded title, "not provided", "not specified", "see cases"; never substring; a note under the table disclosing the real count of excluded links; a variant with a real disease is kept and only its placeholder cells dropped; shown variant rows stay cited.

D3 approved with conditions: the resolver runs only for spans the model tagged `disease`, or for disease-shaped tokens when nothing else resolved, at most three candidates; every span confirmed by a live MedGen lookup; exact title or synonym match preferred; when containment matches several records, EITHER bind the umbrella concept whose title matches the span's expansion OR cap the set in a stable order with a disclosed count, one choice, justified; an unconfirmed disease span never refuses on its own and the BRCA9 gene refusal is unchanged; the answer names the disease record used, cited to MedGen; memory cannot supply the entity; tests in both directions plus a mutation arm; the MODY question joins the live proof at 5 runs, one source set.

Choice for D3, justified: bind the UMBRELLA concept when one exists. MedGen ESummary carries a synonym list for a concept (to be confirmed on the `medgen` summary fields in phase 2; `ncbi_eutils_actions` currently projects `conceptid, title, definition, semantictype`); "MODY" is a synonym of C0342276 "Maturity-onset diabetes of the young", which is the one record whose title is the span's expansion. The gene-edge path has no rows for C0342276, so for the umbrella the variant path (T5, 15 genes with counts, 1.1 s) is the graph's answer. If no umbrella resolves (no exact title or synonym), fall back to the capped subtype set in concept-id order, at most 8, with the count disclosed. Exact-match first, containment second, both deterministic.
