# Card 129 judge round

Judge for branch fix/card129-bind-disease-records-first (commits 2b2313b1, 404f78b3), 2026-10-22. Findings are appended as they are established.

## Findings

### Method for Fix C probes

- One live MedGen ESearch plus ESummary per mention through the repository's own `ncbi_eutils_actions.search` and `summary` (22 read-only calls, 11 mentions), recorded to a scratch file. Then the branch's own `resolve_disease_mention_to_curies` (graph.py:3308) was run twice on the same recorded data: as is (branch), and with `_is_medgen_disease_record` forced to False, which empties `disease_typed` and is exactly develop's code path, since the filter at graph.py:3455 to 3456 is the diff's only change to the function.
- Unchanged by the branch (develop and branch bind the same records): seizure (exact title "Seizure", Sign or Symptom, binds through the exact rule), seizures (8 epilepsy syndromes either way), tall stature (exact, Finding), hearing loss (exact, Finding), intellectual disability (exact), arachnodactyly (exact, Finding), hypotonia (exact, Finding), scoliosis (exact).
- So the exact rule (graph.py:3437 to 3438) protects every phenotype whose MedGen title equals the words typed. The loss sits where no exact title is in the first 20 hits.

### J-129-01: "short stature" loses every record named for short stature and binds five syndromes matched only through synonyms
- Severity: major
- What: for the mention "short stature" MedGen returns 20 hits, 7 disease-typed, and no title equals the mention. The filter at graph.py:3455 to 3456 drops the 13 Findings before the phrase tier is built, so the synonym-only tier (graph.py:3458) fills the cap with records whose titles do not name short stature.
- Reproduction: develop binds C0878659 "Disproportionate short stature" [Finding], C1740819 "idiopathic short stature" [Finding], C1845118 "SHOX-related short stature" [Congenital Abnormality], C1846435 "Disproportionate short-trunk short stature" [Finding], C1849937 "Disproportionate short-limb short stature" [Finding], C2678408 "Short stature-pituitary and cerebellar defects-small sella turcica syndrome" [Disease or Syndrome], C3150077 "Mild short stature" [Finding], C4020838 "Short stature, relative" [Finding]. The branch binds C1845118, C2678408, then C0729582 "Floating-Harbor syndrome", C0796081 "Myhre syndrome", C0878684 "SHORT syndrome", C1845862 "Creatine transporter deficiency", CN034159 "Larsen-like syndrome, B3GAT3 type", all [Disease or Syndrome], none with the phrase in its title.
- Why it matters: "What genes are associated with short stature?" now answers about five named syndromes the person did not ask about, cited to those records. The `[title]` search ANDs single words (graph.py:3388 to 3389), so a synonym-only hit need not carry the phrase at all; develop kept such hits behind every phrase-in-title record, the branch puts them ahead of every Finding. This is the diagnosis's stated risk ("Ranking, not excluding"), realised: the build excludes rather than ranks. Worse than develop for this question shape, in my reading; whether a syndrome with short stature as a feature is a wrong record or a broader one is the owner's call, hence major not critical.
- NOT FIXED

### J-129-02: "developmental delay" loses seven phrase-in-title records and binds three synonym-only syndromes
- Severity: major
- What: the same mechanism as J-129-01. 20 hits, 4 disease-typed, no exact title.
- Reproduction: develop binds C0557874 "Global developmental delay" [Mental or Behavioral Dysfunction] and seven Findings: "Motor developmental delay, severe", "Mild developmental delay", "Developmental delay, profound", "Severe developmental delay in survivors", "Developmental delay if undiagnosed or untreated", "Developmental delay, variable", "Developmental delay, progressive". The branch binds C0557874, then C0268355 "Cutis laxa with osteodystrophy", C4751114 "Huppke-Brendel syndrome", C5231391 "Isolated cerebellar hypoplasia/agenesis", the last three synonym-only.
- Why it matters: a question about genes and developmental delay answers with three specific syndromes the person never named. Some of develop's seven are poor records too ("Severe developmental delay in survivors"), so this is a trade, not a clean loss; recorded because the branch's rule makes a title-blind synonym hit outrank a title that names the phrase, on every mention where any disease-typed record matched.
- NOT FIXED

### J-129-03: Fix D's route keys on the question's words through the existing keyword tests, not only on what Think resolved
- Severity: minor (unsure whether the owner counts this against "decisions go to a classifier model, code only verifies")
- What: the new condition at src/system_03_search_agent/tools/cypher_templates.py:920 to 924 is `anchor_label == "Disease" and shape == "genes" and (not wants_count or len(param_names) > 1)`. `len(param_names)` and `anchor_label` come from Think's bound CURIEs, but `shape` comes from `matched_shapes(tool_input.query_intent, ...)` (cypher_templates.py:349 to 360, a regex per shape) and `wants_count` from `_HOW_MANY_PATTERN = re.compile(r"\bhow\s+many\b", re.IGNORECASE)` (cypher_templates.py:242). `query_intent` is the raw question: `query_intent=query_text[:_PLAN_TOOL_CALL_MAX_INTENT_CHARS]` (src/system_03_search_agent/core/graph.py:6831).
- Reproduction: read, plus the routing probes below (the route flips on the words "how many" alone).
- Why it matters: the diagnosis (card 145 diagnosis.md, "Fix D is a template route keyed on what Think already resolved") and the brief describe the route as keyed only on Think's output. It adds no new word list, so it is no worse than develop's existing route, but the claim as stated is not true. Recorded so the description is corrected, not as a regression.
- NOT FIXED

### J-129-04: the branch's breast cancer gene list drops CHEK2, PALB2, PTEN, STK11, NBN, RAD50 and RAD51D, which develop's binding returned
- Severity: major
- What: the Finding C3469522 "Breast cancer, susceptibility to" is one of the records Fix C now drops (graph.py:3455 to 3456). It carries no `gene_associated_with_condition` edge but 18 genes through the variant path, which `_disease_genes_template`'s fallback (src/system_03_search_agent/tools/cypher_templates.py:559 to 579) reads when the gene edge has no rows. The branch's six records do have gene-edge rows, so the fallback never runs, and those genes leave the answer.
- Reproduction: through the code's own read path, `cypher_query(None, CypherQueryInput(query_intent=..., query_class="aggregate", target_entities=<set>, row_limit=100))`, read-only:
  - develop's 8 bound records, "What genes are associated with breast cancer?": `row_count 20 total_available 20 truncated False`, 18 distinct genes, cypher `MATCH (x:Gene)<-[:is_sequence_variant_of]-(v:SequenceVariant)-[:has_phenotype]->(a:Disease) WHERE a.id IN [...8...] ... LIMIT 100`. Genes: RAD50 (10111), CHEK2 (11200), CYP17A1 (1586), HMMR (3161), APC (324), AR (367), NBN (4683), ATM (472), PHB1 (5245), PTEN (5728), BARD1 (580), RAD51D (5892), BRCA1 (672), BRCA2 (675), STK11 (6794), XRCC3 (7517), PALB2 (79728), CDH1 (999).
  - the branch's 6 records, "How many genes are associated with breast cancer?": `row_count 25 total_available 25 truncated False`, 22 distinct genes, none of 11200, 79728, 5728, 6794, 4683, 10111, 5892, 324, 1586.
- Why it matters: for the list question ("What genes are associated with breast cancer?"), which takes `disease_genes_many` on develop and on the branch alike (routing probe below), develop answered 18 genes cited to "Breast cancer, susceptibility to"; the branch answers 22 genes without CHEK2 and PALB2, two of the best-known breast cancer genes. For the count question, "22" is presented as the answer while the graph links at least 29 distinct genes to the 14 records together. The report's statement "The 8 Findings develop bound, together: 0" (testing/Developer/reports/2026-10-22_card129/after.md, "What the graph holds") counted the gene edge only and is false for the template the answer actually runs; so is "the 22 is the graph's whole answer for these records" if read as "for breast cancer". A Finding record here is not a nurse visit: it is the OMIM susceptibility record a person asking this question wants. This is the diagnosis's ranking-versus-excluding risk at its sharpest, and it sits inside this phase's Fix C.
- NOT FIXED

### J-129-05: "What genes are associated with developmental delay?" goes from Global developmental delay's genes to three genes of three synonym-only syndromes
- Severity: critical (sits inside this phase's Fix C; a confident answer about records the person did not ask about, replacing an answer about the record they did)
- What: Fix C's binding (J-129-02) adds three synonym-only syndromes beside C0557874 "Global developmental delay". C0557874 has no `gene_associated_with_condition` edge but 298 genes through the variant path. `_disease_genes_template` runs the variant path only when the gene edge returns nothing for the whole set (cypher_templates.py:551 to 579). On develop the set's gene edge is empty, so the fallback answers with Global developmental delay's genes; on the branch the three syndromes each have one gene-edge gene, so the primary wins and Global developmental delay contributes nothing.
- Reproduction: read-only, `execute_cypher` (graph_connection.py:678), per-anchor counts:
  - develop's 8: `genes_per_anchor []`, `variant_genes_per_anchor [{'aid': '"MedGen:C0557874"', 'n': '298'}]`, and through `cypher_query` the list template returns `row_count 100 total_available None truncated True`, 99 genes, every one linked to MedGen:C0557874.
  - the branch's 4 (C0557874, C0268355, C4751114, C5231391): `genes_per_anchor [{'aid': '"MedGen:C0268355"', 'n': '1'}, {'aid': '"MedGen:C4751114"', 'n': '1'}, {'aid': '"MedGen:C5231391"', 'n': '1'}]`, and through `cypher_query`: `row_count 6 total_available 6 truncated False`, 3 genes: ATP6V0A2 (Cutis laxa with osteodystrophy), SLC33A1 (Huppke-Brendel syndrome), OXR1 (Isolated cerebellar hypoplasia/agenesis).
- Why it matters: a person asking about developmental delay is told of three genes for three syndromes they never named, each honestly cited to its own record, while the one record named for their phrase is then listed in the "entities named in the question" note as not addressed. The count form ("How many genes are associated with developmental delay?", now `disease_genes_many` by Fix D) would say "Found 3 gene records". Worse than develop for this person. The template's all-or-nothing fallback is develop's design, but Fix C is what now trips it.
- NOT FIXED

### J-129-06: correction to J-129-04's union figure
- Severity: minor
- What: J-129-04 says "at least 29 distinct genes". Counting the two printed lists, develop's 18 and the branch's 22 share 9 genes (HMMR, AR, ATM, PHB1, BARD1, BRCA1, BRCA2, XRCC3, CDH1), so the union is 31. Also measured: the branch's six records carry at least 99 further genes on the variant path (`disease_variant_genes_many ok rows 100 total None trunc True genes 99`), mostly LOC records, which the primary template never reaches; that part is develop's template design, not a regression.
- NOT FIXED

### J-129-07: addendum to J-129-01, what the short stature genes become
- Severity: minor
- What: through `cypher_query`, develop's 8 short stature records return `row_count 4`, 2 genes: SHOX (C1845118) and LHX4 (C2678408). The branch's 7 return `row_count 12`, 6 genes: the same two plus SRCAP (Floating-Harbor syndrome), SMAD4 (Myhre syndrome), PIK3R1 (SHORT syndrome) and SLC6A8 (Creatine transporter deficiency). No gene is lost; four are added, each beside a syndrome the person did not name. Less severe than J-129-05 for that reason.
- NOT FIXED

## Break it and test runs

- Fix C: `if disease_typed:` at graph.py:3455 replaced by `if False:` (sed, scratch). `tests/system_03_search_agent/core/test_think_disease_and_organism.py`: `FAILED ...::test_breast_cancer_binds_disease_records_and_never_the_nurse_visit`, `1 failed, 21 passed in 2.74s`. Restored with `git checkout -- <file>`; `git diff HEAD --stat` empty.
- Fix D, arm removed: `and (not wants_count or len(param_names) > 1)` at cypher_templates.py:923 replaced by `and (not wants_count)`. `test_cypher_templates.py`: 3 failed (`test_a_genes_count_over_several_disease_records_takes_the_gene_list[aggregate|single_hop|lookup]`), `3 failed, 69 passed in 3.32s`.
- Fix D, over-broadened (every genes count to the list): `2 failed, 70 passed in 2.50s` (`test_known_shapes_select_the_named_template[How many genes in the graph are associated with breast cancer?-...-disease_genes_one_count-...]`, `test_a_genes_count_over_one_disease_record_keeps_the_cited_count`). Restored; `git status --short` shows only `?? frontend/node_modules`.
- New tests' files: `94 passed in 3.31s` (test_think_disease_and_organism.py plus test_cypher_templates.py).
- `tests/system_03_search_agent/tools/`: `1682 passed, 99 skipped, 3 warnings in 28.21s`.
- Other files naming `_MEDGEN_DISEASE_SEMANTIC_TYPES`, `select_template` or `resolve_disease_mention_to_curies` (test_disease_breadth.py, test_graph.py, test_topic_search.py): `355 passed in 9.25s`.
- `ruff check` (no path, whole repository): `All checks passed!`. Gate02's exact isort command: exit 0. (`ruff format --check` on the four files reports "4 files would be reformatted", the same on develop's copies, so not this branch.)
- Not mutated, read only: the claim that the exact rule runs before the type narrowing is pinned by `test_an_exact_finding_title_still_binds_over_a_disease_containing_it`.

### J-129-08: every new Fix C test runs on recorded shapes where Findings never carry the answer; nothing pins J-129-04 or J-129-05
- Severity: minor
- What: the five new binding tests (test_think_disease_and_organism.py, added at line 374 onward) assert which CURIEs bind, never what the bound set returns from the graph. The fixture `BREAST_CANCER_RECORDS` contains C3469522 "Breast cancer, susceptibility to", the record whose loss drops CHEK2 and PALB2 (J-129-04), and the test asserts its absence as a success: `assert not findings & set(curies)`.
- Why it matters: the test suite reads the regression in J-129-04 as the fix working. A check pointed at the branch and at a binding that kept the susceptibility record would disagree only in the branch's favour.
- NOT FIXED

## Fix D checks

- Routing, branch versus develop, offline through `select_template` (develop's copy from `git show origin/develop:...cypher_templates.py`):

| Question, anchors, class | Develop | Branch |
|---|---|---|
| "How many genes are associated with breast cancer?", 6 Disease, aggregate | None | disease_genes_many |
| the same, 1 Disease, aggregate | disease_genes_one_count | disease_genes_one_count |
| "What genes are associated with breast cancer?", 6, single_hop | disease_genes_many | disease_genes_many |
| "What is the number of genes ...", 6, aggregate | None | disease_genes_many |
| "How many variants are linked to breast cancer?", 6, aggregate | None | None |
| "How many genes and variants are linked to breast cancer?", 6, aggregate | None | disease_genes_many |
| "How many genes ... breast cancer and BRCA1?", 6 Disease plus 1 Gene | None | None |

- Single anchor unchanged: verified, row 2.
- "Found 22 gene records for breast cancer, linked to 3 diseases": true against the cited records. Through `cypher_query` on the six records: `row_count 25 total_available 25 truncated False`, 22 distinct NCBIGene CURIEs, 3 distinct linked MedGen ids (C0346153, C0268301, C1708349), each gene row's `source_url` its own `https://www.ncbi.nlm.nih.gov/gene/<id>`. Not a capped list.
- Risk tier: the 22 gene rows carry `traversed_edge_type gene_associated_with_condition` and `risk_tier_for` returns `high` for each; the 3 Disease rows `low` (`{('Gene', 'gene_associated_with_condition', 'high'): 22, ('Disease', None, 'low'): 3}`).
- I could not verify the rendered trust line text against that tier: no full run without a live model call. Per the house rule this check is a fail, not a pass.
- Speed: not measured by me; the builder's after.md reports 5.6 to 11.4 s. Read only.

### J-129-09: a capped multi-record genes count reads as the total; the code comment says the true total is given
- Severity: minor (no question I measured reaches it on the branch's own bindings)
- What: cypher_templates.py:917 to 918 says the count line states "the true total when the row cap cut the list". For the fold template the total is not fetched: `if column_count == 1 or value_fold:` (src/system_03_search_agent/tools/cypher_query.py:2147) is false for `RETURN x, xs`, so `total_available` is None.
- Reproduction: `cypher_query` on develop's 8 developmental delay records, "What genes are associated with it?": `row_count 100 total_available None truncated True`, 99 genes. With Fix D's route a count question over such a set opens "Found 99 gene records for ..." (answer_layout.py:1945 to 1949 add ", of N available" only when a total is known). The diagnosis asked for "at least" here; the builder's after.md says it was not built.
- Why it matters: a person asking "how many" reads 99 as the answer. The truncation note elsewhere says the exact total is unavailable, so it is disclosed, but not in the line that answers the question. The comment is false and should not stay.
- NOT FIXED

### J-129-10: the note now tells a breast cancer asker the answer does not address "Malignant tumor of breast"
- Severity: minor (the note wording is the open item; this records how its content changed)
- What: `_build_partial_answer_note` (graph.py:10239 to 10249) names every bound target with no surviving citation. Three of the six records Fix C binds have no gene row (C0006142, C4016951, C0677776; measured above, the 22 genes link only to C0346153, C0268301, C1708349).
- Reproduction: after.md's live runs quote the note as "this answer does not address the following entities named in the question: Early-onset breast cancer, Malignant tumor of breast, Hereditary breast ovarian cancer syndrome". Not rerun by me.
- Why it matters: shorter than develop's 7 to 8 Finding titles, so not worse by count, but it now names the breast cancer record itself as unaddressed, which reads as "this answer is not about breast cancer". Ties to J-129-04: C0006142 does have 60 genes through the variant path together with C4016951 (`row_count 62 ... 60` genes, measured), which the primary-first template never reads.
- NOT FIXED

### J-129-11: "How many variants are linked to breast cancer?" keeps develop's failing model path
- Severity: minor (scope, not regression)
- What: Fix D covers the genes shape only (cypher_templates.py:920 to 925); the variants count over the same six records still returns None (routing table above), the path that produced the "1 record" answer this card was filed for.
- NOT FIXED

### J-129-12: "How many genes and variants ..." over several disease records now answers genes only, silently
- Severity: minor (unsure; the first-named-shape rule already does this for the list form on develop)
- What: with two shapes and an aggregate class, `_resolve_shape` picks the first (cypher_templates.py:398 to 399), and Fix D's arm then sends it to the gene list.
- Reproduction: "How many genes and variants are linked to breast cancer?", 6 Disease anchors, aggregate: develop None, branch `disease_genes_many` (routing table above).
- Why it matters: the variants half of the question gets no answer and nothing in the template path says so.
- NOT FIXED

## Controls

- bronchiolitis, live MedGen recorded by me: 20 hits, 17 disease-typed; develop and branch bind the same 8 records in the same order (C0001311, C0006271, C0006274, C0264366, C0264369, C0276154, C0276340, C0340047).
- MODY: not checked live by me (MedGen call budget spent: 24 of 25). Only the builder's fixture test `test_mody_binds_the_same_eight_records` and after.md speak for it; per the house rule, I could not verify it.

## Verdict

FAIL against the card's acceptance as a whole, though its first clause holds.

- Met, verified by my own probes: no breast cancer binding includes a Finding when a disease record matched (live MedGen data, branch function); the breast cancer count routes to the gene list; 22 genes, 3 linked diseases, each gene cited to its own Gene record; single anchor unchanged; bronchiolitis unchanged; both mutations go red; tests and ruff green.
- Not met or not verified: MODY live (not run); the trust line text (not run end to end); speed (read only).
- Worse than develop for a person, inside this phase's Fix C, so this fires the stop condition and goes to the owner: J-129-05 (developmental delay: 99 Global developmental delay genes become 3 genes of three synonym-only syndromes), J-129-04 (breast cancer list loses CHEK2, PALB2, PTEN, STK11, NBN, RAD50, RAD51D), and J-129-01 and 02 (synonym-only syndromes replace records named for the phrase). The cause in each is excluding, not ranking, the Findings, as the diagnosis warned.
- Read only, not probed: the exact-before-narrowing ordering beyond the builder's test; that the count line renders as after.md quotes.
