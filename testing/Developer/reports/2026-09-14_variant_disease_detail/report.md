# Variant-to-disease detail (2026-09-14)

The product owner compared this system's answers with their other prototype (the NCBI knowledge graph frontend on Railway). For "What diseases are caused by variants in the HNF1A gene?" it shows a summary, a disease list and a variant-to-disease mapping table of 13 rows; for "What genes are associated with MODY?" a gene-to-disease table of 6 rows. Ours showed a list of variant names, because set 9 had recorded that the graph has no variant-to-disease edge. This report records that the claim was false, what the graph actually holds, the templates and layout built on it, the Think changes that came with it (a disease-span resolver, the GCK refusal fix), the product-owner direction on one answer structure for every mode, and the live proof.

Scope added by the coordinator at the start of phase 2, recorded the moment it was taken on: the "Variants in GCK causing MODY" refusal on develop at 2b6d274 is investigated by execution in the same round, since both edit `think_node`. A second direction, received mid-phase and folded in rather than run as a separate pass: records must never render as run-on lines in either mode.

## Table of contents

- [Summary](#summary)
- [The claim was false: evidence](#the-claim-was-false-evidence)
- [What the graph holds beside the edge](#what-the-graph-holds-beside-the-edge)
- [What was built](#what-was-built)
- [The disease-span resolver (D3)](#the-disease-span-resolver-d3)
- [GCK refusal: cause found by execution](#gck-refusal-cause-found-by-execution)
- [What the first live attempt found, and what changed](#what-the-first-live-attempt-found-and-what-changed)
- [One structure in every mode](#one-structure-in-every-mode)
- [Tests and mutation proofs](#tests-and-mutation-proofs)
- [Live proof](#live-proof)
- [Comparison with the reference prototype](#comparison-with-the-reference-prototype)
- [Verification](#verification)
- [Open items and residuals](#open-items-and-residuals)
- [Proposed DECISIONS.md rows](#proposed-decisionsmd-rows)
- [Files](#files)

## Summary

- The graph links a SequenceVariant to a Disease through `has_phenotype` edges whose source is ClinVar and whose `source_url` is the variant's own ClinVar page. HNF1A alone: 2075 links over 1158 variants and 36 diseases, read in 1.5 s. Set 9's F9-05 and F9-16 were wrong; nobody had queried.
- Three fold templates run in code for the variant-to-disease shapes, deterministic and parameterised, each collecting the linked Disease records beside the anchor row. `cypher_query` writes the linked CURIEs onto the anchor row (`clinvar_condition_ids`, `medgen_condition_ids`) and still emits the Disease records as cited rows of their own.
- Answers open on "Found N sequence variant records for HNF1A, ..., linked to M diseases: ..." and render a "Variant-to-disease mapping" table (Variant, Associated disease(s)) after a disease list, one citation per row plus one per named disease. Placeholder conditions ("not provided", "not specified", "see cases") are excluded from cells and counts and the real count of excluded links is disclosed under the table (D2).
- Think live-confirms disease spans against MedGen (D3). "What genes are associated with MODY?" binds the eight MODY subtype records and answers with a Gene-to-disease table of 6 rows; the baseline refused with no source.
- The GCK refusal's cause, found by running Think alone 20 times: on 2 of 20 the model tagged "MODY" as an ORGANISM, the taxon became "MODY", and `GCK[sym] AND MODY[orgn]` found nothing. Fixed by asking NCBI Taxonomy whether an organism span exists before it may change the species, one retry on a non-cacheable miss, and a fallback that also runs when every model span failed. After: 20 of 20 Think runs resolve `NCBIGene:2645`; the live proof's five GCK runs answer 5 of 5 with the mapping table.
- Every depth now lists its records in code under headings, as tables or lists; the run-on findings tail is gone.
- Stable prefix byte-identical (SHA-256 `34a07a1a...`, 28925 bytes, before and after). Ten mutation arms red, every file restored byte-identical. Live proof: 30 runs, 28 answered, one source set per question among answered runs, median elapsed 17.4 s over all runs.

## The claim was false: evidence

Every query ran through `graph_connection.execute_cypher` over `GRAPH_QUERY_URL`, parameterised, with a 30 s timeout. Raw records: `probe_out*.jsonl` beside this report.

| Probe (HNF1A, `NCBIGene:6927`) | Rows | Elapsed |
|---|---|---|
| variants of HNF1A (`is_sequence_variant_of`) | 1212 | 1.1 s |
| `MATCH (v)-[:has_phenotype]->(n)` from those variants | 2075 | 1.5 s |
| label of every target `n` | `Disease`, 2075 of 2075 | 1.4 s |
| distinct variants with a disease / distinct diseases | 1158 / 36 | 1.1 s |
| `close_match`, `exact_match`, `gene_associated_with_condition` from or to a variant | 0 each | under 3 s |

One edge, verbatim from the graph: `{"label": "has_phenotype", "properties": {"source": "ClinVar", "agent_type": "manual_agent", "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/1025247", "knowledge_level": "knowledge_assertion"}}`, from `ClinVar:1025247` to `MedGen:C0342276`.

Why set 9 got it wrong. F9-16 read one variant NODE (`MATCH (v:SequenceVariant) RETURN v LIMIT 1`), found no disease field, and concluded no mapping exists. The mapping is an EDGE. F9-05 relied on `cypher_templates.py`'s own docstring, which relied on the reference doc, which lists `has_phenotype` only as Disease to PhenotypicFeature. The doc, the schema visualization and `graph_schema_constants` now record the second endpoint pair (`ADDITIONAL_EDGE_ENDPOINTS`, kept apart from `EDGE_ENDPOINTS` so the model's schema slice and the stable prefix are untouched).

## What the graph holds beside the edge

- Disease names are not in the graph: a Disease node's `name` holds the source vocabulary ("OMIM", "MeSH", "OMIM included"), the F-2.1-B07 defect, so the reference prototype's name-contains search returns 0 rows here. Names come from the existing Layer 2 path `disease_names.resolve_concept_ids`, verified live for HNF1A's six: C0342276 "Maturity-onset diabetes of the young", C1838100 "... type 3", C3888631 "Monogenic diabetes", C2675866 "Type 1 diabetes mellitus 20", CN074294 "Nonpapillary renal cell carcinoma", C0011860 "Type 2 diabetes mellitus". Exactly the six the reference lists.
- ClinVar's placeholder concepts are the most frequent targets: C3661900 "not provided" (730 of HNF1A's 2075 links), CN169374 "not specified" (193). Real MedGen records; a presentation rule, not a grounding change (D2).
- The general MODY concept C0342276 has ZERO `gene_associated_with_condition` edges; MODY3 (C1838100) has one (HNF1A). Through variants, C0342276 reaches 15 genes (GCK 436 variants, ABCC8 469, HNF1A 380, HNF4A 282, HNF1B 210, KCNJ11 164, PDX1 42, ...) in 1.1 s. That is why the disease-genes template carries the variant path as its fallback.
- The tool emits one output row per record and deduplicates by `source_url`, so `RETURN v, d` alone loses which disease belonged to which variant. The fold carries the pairing.
- `parse_agtype` decoded a list column (`collect(DISTINCT x)`, wire text `[{...}::vertex, {...}::vertex]`) to None, so every collected Disease record was lost until the list branch stripped the per-element suffix. Found live, fixed in `tools/agtype.py`, mutation-proven (M8).

## What was built

Templates (`tools/cypher_templates.py`), all measured at LIMIT 100 through the HTTPS service:

| Template | Shape it answers | Cypher (parameter names elided) | Live |
|---|---|---|---|
| `gene_variant_diseases_one` | one gene, a variants word AND a diseases word ("diseases caused by variants in HNF1A", "what variants cause disease in BRCA1") | `MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(a:Gene {id: $e}) MATCH (v)-[:has_phenotype]->(x:Disease) WITH v, collect(DISTINCT x) AS xs RETURN v, xs ORDER BY v.id` | HNF1A 1.8 s, GCK 1.9 s, BRCA1 3.7 s |
| `gene_variant_disease_link` | one gene and one or more diseases with a variants word ("variants in GCK causing MODY") | the same with `(x:Disease {id: $d})` or `WHERE x.id IN [...]` | GCK plus C0342276: 100 rows, 1.4 s |
| `disease_genes_one` / `_many` | disease(s) with a genes word | `MATCH (x:Gene)-[:gene_associated_with_condition]->(a:Disease ...) WITH x, collect(DISTINCT a) AS xs RETURN x, xs ORDER BY x.id`, with FALLBACK `disease_variant_genes_*` through `is_sequence_variant_of` and `has_phenotype` when the gene edge returns no rows | 0.5 s; fallback 1.1 s |

Decision D1, taken in the plan: a question naming only diseases ("Which diseases are associated with BRCA1?") keeps `gene_diseases_one`, so its source set is unchanged; naming only variants keeps `gene_variants_one`. The five routing rows in `test_cypher_templates.py` this changes are re-pinned, including the flagship "Give me everything NCBI knows about BRCA1 ... associated conditions, clinically significant variants ...", which now takes the fold template.

The fold (`CypherTemplate.fold`, `cypher_query._apply_fold`): template path only, after `to_output_rows` and before the typed boundary; at most `MAX_FOLD_ITEMS` (12) CURIEs; the columns are located from the RETURN text (`_returned_variable_by_column`), never by position. A template without a fold, and the whole model path, are untouched. `CypherTemplate.fallback`: one second template run only when the first returns no rows, through the identical validator and binding gate, inside the same call budget.

The answer (`synthesis/answer_layout.py`, `core/graph.py` write side):

- `TABLE_COLUMNS`: SequenceVariant rows map `clinvar_condition_ids` to "Variant | Associated disease(s)"; Gene rows map `medgen_condition_ids` to "Gene | Associated disease"; Clinical trial rows map `overall_status` to "Trial | Status". Headings "Variant-to-disease mapping" and "Gene-to-disease mapping". The disease group is listed before a mapping table.
- The second cell is the resolved MedGen titles (`readable_disease_name`), joined by "; ". A placeholder or unresolved id is never shown, so no raw code reaches answer words; a row whose links were all placeholders gets an empty cell and stays in the table.
- One more cached `resolve_concept_ids` call over the fold ids (at most 25) so a disease the citation cap left out of the findings is still named in its cell, cited to the ClinVar record whose row it sits in.
- `drop_placeholder_condition_findings`: a Disease finding whose resolved title is a placeholder is dropped, survivors renumbered densely. The note under the table states the real count of excluded links.
- `answer_summary_sentence`: "Found N sequence variant records for X, of T available, linked to M diseases: A [k], B [m] and 4 others." M is the distinct non-placeholder CURIEs across the cited anchors' folds; a disease is named only when it is itself a cited finding, with its marker.
- Each table row's markers: the record's own plus the Disease findings its cell names.
- The partial-answer note names a MedGen id by its resolved title, or by the question's own mention, never by its code (found live: "does not address ... MedGen:C0271653").

The frontend is unchanged: `table_header`, `table_row`, `list_item`, `heading` and `note` tokens with two cells and per-row markers already render; `cells` is contract-bounded at two, so the reference's redundant Gene column is not added. The `kind` contract is unchanged and additive, as asked, for the Opus restyle.

## The disease-span resolver (D3)

`core/graph.py::resolve_disease_mention_to_curies(mention) -> (curies, matched)`. Runs for spans the model tagged `disease` (at most three distinct mentions); for a gene span that NO live gene lookup confirms when nothing else resolved; and for the gene-shaped fallback candidates when nothing at all resolved and no gene span failed. One ESearch on `db=medgen` with one `[title]` clause per content word, ANDed (a hyphenated or stopworded phrase returns nothing as one field-tagged phrase, measured live; "maturity-onset diabetes of the young" returns 3 records as ANDed words), boolean words and brackets stripped, at most 20 hits, then one ESummary for titles. Rules, in order: exact case-folded title; else up to 8 records in two tiers, titles containing the mention as a whole phrase first, then the other name-index hits, each tier in concept-id order; placeholder titles never bound. Never raises; a transport failure binds nothing and is not cached. An unconfirmed span never enters `unresolved_symbols`, so it never refuses; a failed gene span that MedGen does not confirm (BRCA9) stays unresolved and refuses by name as before.

The Think instruction had told the model "Only ever emit entity_type gene or organism", so no disease span could ever arrive: TASK 4, disease extraction, was added and "disease" admitted in the output rule. Measured after (`think_gck_tag.jsonl`): 8 of 8 GCK runs tag MODY as a disease.

Live probes (`disease_resolver_probe.json`):

| Mention | Bound | Matched |
|---|---|---|
| MODY | C0271653, C0342277 (type 2), C1833382 (type 4), C1838100 (type 3), C1852093 (type 1), C4014962, C4225299 (type 14), C4225365 (type 13) | 8 |
| Monogenic diabetes | C3888631 alone (exact title) | 2 |
| maturity-onset diabetes of the young | C0342276 alone (exact title, the umbrella) | 3 |
| breast cancer, cystic fibrosis | 8 of at least 20 each | 20 |
| BRCA9, COMMODITY, GCK | nothing | 0 |
| MODY[all] OR x | nothing (operators stripped) | 0 |

The disclosure: the Think narrative gains "(MODY: 8 MedGen records matched by name)" or "(breast cancer: 8 of at least 20 MedGen records matched by name)", and the bound records reach the answer as cited MedGen findings. The umbrella-versus-cap choice: exact title first, so "maturity-onset diabetes of the young" binds the umbrella; "MODY" has no exact title and binds the capped subtype set with the count disclosed. The `medgen` summary projection carries no synonyms, which is why the umbrella cannot be found through "MODY" itself.

## GCK refusal: cause found by execution

Script: `think_gck.py` runs `think_node` alone with the real Plan-tier model and live lookups, spying the model's spans, every uncached symbol lookup and the cache. Before the fix (`think_gck_20.jsonl`): 18 of 20 resolved. Both failures, runs 9 and 13, had one signature: spans `GCK: gene` plus `MODY: organism`; one lookup `GCK` with `curie: null, cacheable: false`; the warm `GCK:human` cache entry present and not consulted. So the taxon was "MODY" (`_taxon_for_extraction` passes an organism span to NCBI verbatim, by design since F-4.7-A-03), the lookup was keyed `GCK:mody`, `GCK[sym] AND MODY[orgn]` found nothing, and GCK was filed unresolved and refused by name. Neither of the other candidates fired: no run returned no entities, none tagged MODY as a gene in that batch (the gene tag did appear later, once, on the MODY-genes question).

The fix, within the constraints:

- `_organism_is_known(name)`: one ESearch on `db=taxonomy`, `<name>[All Names]`, `retmax=1`. True on a hit, False on a clean empty answer, None on a transport failure. `_confirmed_taxon_for_extraction` drops an organism span Taxonomy rejects before the existing rule runs, keeps one it confirms or could not check (so an outage never turns a mouse question into a human one), at most three checked. Executed live: MODY False, mouse True, Mus musculus True; with `GCK: gene, MODY: organism` the taxon is human and the resolution is `NCBIGene:2645`.
- `resolve_symbol_to_curie`: one retry inside the same call when the uncached lookup reports a non-cacheable miss; a second failure is still never cached.
- The gene-shaped fallback runs whenever no CURIE resolved, whether the model named nothing or every span it named failed live; a confirmed candidate leaves `unresolved_symbols`, any other failed span stays, so BRCA9 alone still refuses by name and memory still cannot supply the entity (`_select_planned_tool_call` unchanged).

After the fix (`think_gck_after.jsonl`): 20 of 20 resolve `NCBIGene:2645`. No run in that batch reproduced the organism tag, so the mechanism is proven by the deterministic arm `test_an_organism_taxonomy_rejects_does_not_change_the_taxon` (mutation M3 red) and by the live execution above, not by the batch alone. Done-when met: 20 of 20 local Think runs, and 5 of 5 GCK runs in the live proof.

## What the first live attempt found, and what changed

The first queue (files under `first_attempt/`) ran on the code as it stood after D2 and D3 and found three things the unit tests could not:

- "Variants in GCK causing MODY" answered 5 of 5 with one source set but showed NO mapping table: it ran `gene_variants_one` ("Found 13 sequence variant records for GCK, of 1333 available"), because no MODY disease span ever reached D3 (the instruction gap above; the 40 recorded Think runs agree: MODY absent on 38, "organism" on 2, never "disease").
- "What genes are associated with MODY?" refused on run 2 of 5 ("I could not identify that gene"): the model tagged MODY as a GENE. Fix, within D3's rule: a failed gene span is tried as a disease mention when nothing else resolved (`test_a_failed_gene_span_that_medgen_confirms_binds_as_a_disease`).
- Run 1 of the same question printed a raw code in its partial-answer note. Fixed as described above.

The second queue then found the last one: three of five Plain language MODY runs rendered "Gene name: ... Disease name: ..." as run-on claims, because the structured fallback (the model's prose grounded nothing) listed in code only in Researcher. Fixed (`_answer_tokens`, one branch), pinned by `test_the_structured_fallback_lists_records_in_every_depth`, mutation M10 red, and the five Plain language MODY runs were redone under the fix (5 of 5, mapping table on every run). Cost of the reruns: 30 runs in the first attempt, 5 redone.

## One structure in every mode

Product-owner direction received during phase 2 (a Plain language BRCA1 answer read as one run-on block) and folded in here: every depth lists the prepared records in code, grouped by type under a code-built heading, as a table when the rows carry a second field (Variant | Associated disease(s); Gene | Associated disease; Trial | Status) and as a list otherwise, one citation per row. `tail_is_listing` is True for every depth, so the run-on findings tail and its note are gone; the structured fallback lists too. Plain language keeps its shorter prose and the medical-advice note, and the Researcher-only restatement drop stays Researcher-only so a Plain language paragraph is never emptied into its own list. Three tests that pinned the tail note for non-Researcher depths were re-pinned to the listing. `frontend/` is untouched.

## Tests and mutation proofs

New: `tests/system_03_search_agent/tools/test_cypher_fold_templates.py` (selection, parameterisation with no quoted literal, the fold and its cap, the list column, the fallback, the model path untouched), `tests/system_03_search_agent/core/test_think_disease_and_organism.py` (both directions of every D3 rule, the refusal preserved, the failed-gene-span path, the organism confirmation, the outage direction, the widened fallback through `think_node`), arms appended to `test_answer_layout.py` (summary clause, placeholder count) and `test_write_answer_structure.py` (the fold table, plain language listing, the fallback listing), the outage test updated for the in-call retry, five routing rows and three tail tests re-pinned.

Mutations, each applied to the source, the named arm run, the file restored and proven byte-identical (`mutations_out.txt`):

| Mutation | Arm | Result |
|---|---|---|
| M1 `_apply_fold` not called | fold test | red |
| M2 placeholder findings kept | write-structure table test | red |
| M3 organism not confirmed live | organism test | red |
| M4 fallback gate restored to "model named no gene" | fallback test | red |
| M5 template fallback never appended | disease-genes fallback test | red |
| M6 summary fold clause removed | summary test | red |
| M7 exact-title rule removed | exact-title test | red |
| M8 list suffix strip removed in `parse_agtype` | fold test | red |
| M9 symbol-lookup retry removed | outage test | red |
| M10 fallback rendered as run-on claims outside Researcher | fallback-listing test | red |

## Live proof

`queue.sh` ran `measure_write2.py` (the speed-fix script, extended to record table rows, list items, notes and the Think narrative) five times per question, sequentially, against the real models, the live graph and NCBI. `analyze.py` renders `live_proof_table.md` from the run files; the per-run table is there in full. Summary:

| Question (depth) | Answered | Distinct source sets among answered runs | Median elapsed s | Mapping rows per run | Distinct diseases per run | Run-on record lines |
|---|---|---|---|---|---|---|
| What diseases are caused by variants in the HNF1A gene? (researcher) | 5 of 5 | 1 (`706176af`) | 37.4 | 5, 5, 5, 5, 5 | 6, 6, 6, 6, 6 | none |
| Variants in GCK causing MODY (researcher) | 5 of 5 | 1 | 19.6 | 12, 12, 12, 12, 12 | 1 (MODY type 2) | none |
| What genes are associated with MODY? (researcher) | 4 of 5 | 1 (`2cdfb738`); run 3 was a Think classification parse error, no tool ran | 14.0 | 6, 6, -, 6, 6 | 7 | none |
| What genes are associated with MODY? (plain_language, redone) | 5 of 5 | 1 | 15.4 | 6, 6, 6, 6, 6 | 7 | none |
| Which diseases are associated with BRCA1? (researcher) | 4 of 5 | 1 (`f5cd2a85`, the same 11 sources as before this work); run 1 was a transient step error at 66 s | 29.0 | no mapping (single-hop template, unchanged), trials table 5 rows | n/a | none |
| Which diseases are associated with BRCA1? (plain_language) | 5 of 5 | 1 (`f5cd2a85`) | 17.4 | no mapping, trials table 5 rows, disease list 4 rows | n/a | none |

Median elapsed over all 30 runs: 17.4 s, within the 16.6 plus 2 s bound. Two question medians are above it: HNF1A at 37.4 s and BRCA1 Researcher at 29.0 s. Both are model latency, not this work: the first attempt's HNF1A runs, on the identical write code, took a median of 15.4 s, and in the slow runs the guard step alone ranged 1.9 to 6.7 s and Think 0.9 to 8.7 s, steps this work does not touch beyond one Taxonomy call; the graph and Layer 2 calls stayed at 1.4 to 4.8 s.

Against the reference: HNF1A shows 5 mapping rows over 6 diseases (the reference 13 rows over the same 6), bounded by the 20-citation cap with Layer 2 and Layer 3 rows admitted first; MODY shows 6 gene rows against the reference's 6 (APPL1 for type 14, GCK type 2, HNF4A types 1 and Fanconi renotubular syndrome 4, PDX1 type 4, KCNJ11 type 13, HNF1A type 3). No raw MedGen code appears in any answer word (`raw_medgen_in_words` false on all 30 runs). Every table row carries at least one marker, and the HNF1A rows carry 2 to 6.

Two unanswered runs, both pre-existing failure classes recorded rather than closed: a Think classification schema parse failure (the coordinator's 2026-09-12 note measured about 1 in 7 before the retry was added; here 1 in 30), and one transient step error.

## Comparison with the reference prototype

Captured this round with Playwright (`scratchpad/ref/`): gck_activities, gck_pathways, most_variants, mody_processes, beside the earlier hnf1a and mody. The reference writes with a different model family (the product owner: GPT 5.4); ours resolves from environment configuration and is not changed here. Element by element, (a) reachable in code from retrieved records, (b) only by relaxing grounding, (c) not from this graph:

| Element in the reference | Status |
|---|---|
| Opening summary that interprets ("primarily to monogenic diabetes...") | (a) in part: the code-built summary states counts and names diseases with markers; a ranking by per-disease link count is expressible in code from the fold; the prose gloss beyond it is (b). |
| Bold key terms | (a) exists. |
| Topic headings | (a) code-built, this round. |
| Disease list | (a) this round. |
| Variant-to-disease table (13 rows) | (a) this round; row count bounded by the 20-citation cap. |
| Gene-to-disease table (6 rows) | (a) this round, 6 rows, through D3. |
| Gene / molecular activity table | (a) in principle with the existing `gene_activities_one` template, but GO nodes carry no citable `source_url` and are dropped by cite-or-refuse; that, not layout, is the constraint. |
| "Summary by functional category" grouping of GO terms | (b) or (c): a category is an ontology fact the graph lacks; a model grouping is uncited. |
| Pathways (Reactome) | (c): no pathway nodes. |
| Ranked "most disease-causing variants" table | (a) in principle as an anchor-free aggregate template; a new shape and a 4.4 M-edge scan, out of this round. |
| "Key takeaways" bullets | (b). |
| Notes ("typically derived from ClinVar") | (a) as a code-built provenance note the code knows (D4 below); the hedged "typically" wording is (b). |
| "Showing 20 of 20" | (a) exists (truncation note). |
| Source chips | (a) exists. |

Nothing in (b) was done. The model: the grounding gate strips every sentence not contained in a finding, so a stronger writer yields at most more surviving prose, never a table, list, heading or count, all built in code here; the model is not the constraint for (a), and (b) is a product decision. A model swap is build phase 7.0's benchmark.

## Verification

- `python -m pytest tests/system_03_search_agent -q -p no:cacheprovider`, one 33-minute run of the whole tree: `7 failed, 4692 passed, 176 skipped, 1 xfailed`. The two failures the capture named are `adapters/web_sse/test_streaming_endpoints.py::TestEventsEndpoint::test_requires_auth` and `::TestConcurrentRunCap::test_a_completed_run_does_not_count_against_the_cap`; that file passes alone (36 of 36), and the other five names were lost to the run's `tail -3` capture. Every directory then ran on its own and was green: `core` 642 passed, `tools` 1501 passed, `synthesis` green within a 352-test batch, `eval` 145 passed, and everything else (`adapters`, `auth`, `contracts`, `guardrail`, `harness`, `observability`, `orchestrator`, `feedback`, `export`, `data`) 2093 passed. The seven are order or concurrency effects of the single long run, not failures of any test in isolation; a second full run was not repeated for time.
- `ruff check .` (whole repository): All checks passed, exit 0, after the report-folder scripts were brought to the repository's rules.
- `isort --check-only src tests`: exit 0.
- `python tests/system_03_search_agent/test_debugging_guide_coverage.py`: exit 0, manifest unchanged.

- Stable prefix: `prefix_sha256.py 2b6d274` reports `34a07a1aab36ecad4491fa2173bc8cb5d14566b3e71d3e4c879e181d9b26603e` (28925 bytes) before and after, BYTE-IDENTICAL. The script swaps only `core/graph.py`; the other changed modules do not feed the prefix (`harness/cache.py` carries its own label tables).
- No file under `src/` added; `test_debugging_guide_coverage.py` run, manifest unchanged; no frontend file changed, so no `npm run build` or vitest run was needed.

## Open items and residuals

- Table row count. With Layer 2 and Layer 3 rows admitted first and 20 citations per answer, an HNF1A Researcher answer shows 5 variant rows and 6 diseases, against the reference's 13 rows. The lever is the admission order within the graph result, or the cap, both product-owner decisions; neither was changed here.
- The partial-answer note on "Variants in GCK causing MODY" now lists the seven MODY subtype titles the answer's rows do not link to. Honest, and long; a shorter form ("7 of the 8 MODY records bound have no GCK variant link") is a wording decision for the product owner.
- A common disease with hundreds of name-index hits ("cystic fibrosis") binds 8 of the first 20 index hits in concept-id order, disclosed as "8 of at least 20"; the umbrella record can fall outside the 20-hit window when no exact title matches.
- `has_phenotype` from a variant is not in `trust.py`'s high-risk relationship set, so Disease rows reached through the fold classify from their bare type. Named, not widened.
- The Think classification schema parse failure and the transient step error each cost one run of 30; both pre-date this work.
- `measure_write2.py` (copied from the speed-fix folder) builds a `Query` with no `owner_id`, so `run._remember_turn` and `_capture_interaction` log a `CallerIdentityRequired` traceback on every run; both are best-effort and the runs complete. The speed-fix queue logs carry the same traceback 90 times. A measurement artefact, not a product path: every surface mints a guest or user owner id.
- D4, the code-built provenance note, is proposed and not shipped.

## Proposed DECISIONS.md rows

| Date | Decision | Alternatives considered | Why |
|------|----------|------------------------|-----|
| 2026-09-14 | The variant-to-disease shapes run as fold templates over the graph's own `has_phenotype` edge from SequenceVariant to Disease, recorded as a second endpoint pair in `graph_schema_constants.ADDITIONAL_EDGE_ENDPOINTS`, with the pairing carried onto the anchor row by `cypher_query._apply_fold` | Widening `EDGE_ENDPOINTS["has_phenotype"]` to mixed (`None`); a Layer 2 ClinVar call per variant for its conditions; returning `RETURN v, d` pairs and reassembling downstream | <details><summary>why</summary>The edge exists, measured live (HNF1A: 2075 links over 1158 variants and 36 diseases in 1.5 s), so a Layer 2 call per variant would be a second source for a fact the graph already asserts, with ClinVar's own page as the edge's source. A separate table keeps `schema_slice` and the stable prefix untouched, which widening the primary pair to mixed would not. `RETURN v, d` loses the pairing at the tool's one-row-per-record output, which is why the fold writes the linked CURIEs onto the anchor row and still emits the Disease records as their own cited rows.</details> |
| 2026-09-14 | ClinVar placeholder conditions ("not provided", "not specified", "see cases") are excluded from mapping cells, disease lists and counts by exact case-folded title, and the real number of excluded links is disclosed under the table (D2) | Showing them verbatim; substring matching; dropping the variant rows that link only to them | <details><summary>why</summary>They are the most frequent targets of the edge (730 of HNF1A's 2075 links to "not provided") and are real MedGen records, so this is a presentation rule and never a grounding change: the variant rows stay and stay cited, only the placeholder cells go, and the count is the real one. Exact match so a real disease whose name contains one of the words is never mistaken for a placeholder.</details> |
| 2026-09-14 | Think live-confirms disease spans against MedGen (D3): exact title first, else up to 8 name-index records in a stable order with the count disclosed; the Think instruction extracts disease spans; a failed gene span that MedGen confirms binds as a disease; an unconfirmed span never refuses; memory still cannot supply the entity | Binding only an umbrella concept found through synonyms; a fuzzy top hit; leaving disease spans unresolved | <details><summary>why</summary>Without it "What genes are associated with MODY?" bound nothing and refused with no source (measured baseline), and the instruction admitted only gene and organism spans so no disease span could ever arrive. The `medgen` summary projection carries no synonyms and the name index ranks by neither title nor relevance this system controls, so the umbrella cannot be found through the acronym; exact title takes it when the mention is the title, and otherwise a capped set in concept-id order is deterministic and disclosed. Every bound CURIE is a real MedGen record confirmed live, the same rule as genes, and BRCA9 still refuses by name because MedGen confirms nothing for it.</details> |
| 2026-09-14 | An organism span changes the taxon only when NCBI Taxonomy confirms the name exists; a rejected span is dropped and a span the check cannot run for is kept | A hand-kept organism list; keeping the verbatim rule; treating a Taxonomy outage as a rejection | <details><summary>why</summary>Found by running Think alone 20 times on "Variants in GCK causing MODY": on 2 of 20 the model tagged MODY as an organism, the taxon became "MODY", `GCK[sym] AND MODY[orgn]` found nothing and the answer refused by name. The verbatim rule was right to pass the span to NCBI rather than a word list; what it lacked was asking NCBI whether the span is an organism before it may change the species. Keeping a span the check cannot run for means a Taxonomy outage never turns a mouse question into a human one, which is F-4.7-A-03 in the other direction.</details> |
| 2026-09-14 | Every audience depth lists the prepared records in code, grouped by type under a heading, as a table when the rows carry a second field and a list otherwise, and the run-on findings tail is retired; Plain language keeps its shorter prose | Keeping the tail for non-Researcher depths; a separate formatting pass; model-written lists | <details><summary>why</summary>Product-owner direction 2026-09-14 after a Plain language BRCA1 answer read as one run-on block: "the beautiful format of the answer should be irrespective of the plain language or researcher mode". The listing already existed for Researcher, built in code with one citation per row, so extending it to every depth changes presentation only; the structured fallback lists too, since 3 of 5 Plain language MODY runs rendered run-on claims through that branch. The restatement drop stays Researcher-only so a short Plain language paragraph is not emptied into its own list.</details> |

D4 for the product owner, not shipped: a code-built provenance note under the mapping table, "Variant-to-disease links are ClinVar assertions, each cited to its variation record. Disease names are MedGen titles read live from NCBI."

## Files

Source: `src/system_03_search_agent/tools/graph_schema_constants.py`, `tools/cypher_templates.py`, `tools/cypher_query.py`, `tools/agtype.py`, `synthesis/disease_names.py`, `synthesis/findings.py`, `synthesis/answer_layout.py`, `core/graph.py`. No file under `src/` added.

Docs: `docs/data-engineering/Knowledge_graph_on_server_reference.md` and `visualizations/Schema_visualization.md` record the second endpoint pair.

Tests: `tests/system_03_search_agent/tools/test_cypher_fold_templates.py` (new), `tests/system_03_search_agent/core/test_think_disease_and_organism.py` (new), `tests/system_03_search_agent/synthesis/test_answer_layout.py`, `tests/system_03_search_agent/core/test_write_answer_structure.py`, `tests/system_03_search_agent/core/test_write_findings_tail.py`, `tests/system_03_search_agent/core/test_write_completeness.py`, `tests/system_03_search_agent/core/test_resolve_symbol_to_curie.py`, `tests/system_03_search_agent/tools/test_cypher_templates.py`.

Beside this report: `measure_write2.py`, `queue.sh`, `analyze.py`, `live_proof_table.md`, the run files (`hnf1a_researcher.jsonl`, `gck_mody_researcher.jsonl`, `mody_genes_researcher.jsonl`, `mody_genes_plain.jsonl`, `brca1_researcher.jsonl`, `brca1_plain.jsonl`), `first_attempt/` (the runs before the Think instruction, refusal-path and fallback-listing fixes), `think_gck.py`, `think_gck_20.jsonl` (before), `think_gck_after.jsonl` (after), `analyze_think.py`, `mutations.py`, `mutation_m10.py`, `mutations_out.txt`, `probe.py` and `probe_out*.jsonl` (the phase 1 graph probes), `disease_resolver_probe.json`, `baseline_mody.jsonl`, `baseline_hnf1a.jsonl`, `plan.md` (the phase 1 plan).
