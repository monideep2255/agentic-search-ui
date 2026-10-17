# Cards 37 and 38 diagnosis: records carry the field asked for

Read on develop at `78c68c1c`, 2026-10-16, after phase 8.7 (#218, #229) and card 37's first part (#213). Code reading, offline probes of develop's own functions, the saved run files named below, and three free PubMed EFetch calls. No model call and no question sent to the develop or production API.

Read-only graph probes need the graph credential, which this shell does not have. Every graph fact below comes from phase 8.9's recorded probes 1 and 3 (`tracker/phase_8.9.md`, "Premises and probes", run 2026-09-26) and says so.

This replaces `testing/Developer/reports/2026-10-08_overnight/card37_diagnosis.md` and `card38_diagnosis.md`, whose line numbers are stale and whose card 37 step 1 is now live.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The cause](#the-cause)
- [The smallest fix](#the-smallest-fix)
- [Tests](#tests)
- [Overlap with tonight's other cards](#overlap-with-tonights-other-cards)
- [Needs the owner](#needs-the-owner)
- [Test query](#test-query)

## Status today

| Shape | Status on `78c68c1c` | Evidence |
|---|---|---|
| rs334 listed beside rs334348, rs334353, rs334773 | Fixed, live, in the owner's retest (row 18 of `testing/Retest_product_owner.md`) | #213: the exact rs id filter in the `litvar2_lookup` branch, `src/system_03_search_agent/core/graph.py:5053`; product check of 2026-10-09 passed it (`testing/Developer/reports/2026-10-09_product_check_37_36/product_review.md`, results table, item 1) |
| The rs334 record named by its clinical significance list | Still happens | Offline probe of develop's `record_label`, `plain_record_label` and `summary_label` on the probe 3 pseudo-row: all three return "not-provided, protective, likely-benign, pathogenic, other". Seen live 2026-10-09: "Found 1 variant record record for rs334: not-provided, protective, likely-benign, pathogenic, other." (`S1_rs334_log.json`, step "answer texts") |
| The writer never given the gene HBB | Still happens | Probe: `build_synth_findings` on the dbSNP pseudo-row gives one finding, field `clinical_significance`; the row's `genes: HBB` reaches no finding |
| No condition (sickle cell) named | Still happens, outside 8.9's approved words | No ClinVar call is planned for an rs id; phase 8.9 "Out of scope", probe 2 |
| TP53's orthologs carry no species (G-016) | Still happens | Probe: develop's `gene_orthologs_one` is `MATCH (a:Gene {id: $e_0})-[:orthologous_to]->(x:Gene) RETURN x ORDER BY x.id`, fold None. No commit since 2026-09-29 touches the ortholog hop (`git log` on `tools/cypher_templates.py`: only `ac3dded8` and `3603bb49`, other templates) |
| CFTR's graph papers carry no title (G-021) | Still happens | Probe: a quarantined Article row becomes finding `curie = PMID:10075921`, `curie_fallback` true; Researcher label "PMID:10075921", Plain language label "Published paper"; prompt line "Article record PMID:10075921" |
| The ESBL isolates do not say which gene each carries | Fixed on screen by card 94 | Table "Isolates and their AMR genes" (`synthesis/answer_layout.py:307`, `TABLE_COLUMNS`); query 33 passed 2026-10-05 |

What phase 8.7 changed for these cards: it added `_prefetch_answer_names` (`core/graph.py:8738`), which resolves MedGen and MeSH names during Act behind the reader pass. That is the natural home for card 38's title lookup and changes slice C's timing cost (below). Nothing else 8.7 rewrote touches the dbSNP row, the Article quarantine or the ortholog template.

## What a person sees

A researcher typing the question:

- "What is rs334 and what condition is it associated with?": "I asked about the sickle cell variant. The one record is named 'not-provided, protective, likely-benign, pathogenic, other', which reads as if the variant were protective. No gene, no condition." In Researcher the table reads Variant "not-provided, protective, ..." beside Identifier "rs334". In Plain language the one row reads the same list.
- "What are the known orthologs of TP53 in other species?": "I asked which species. I got about forty rows that all say 'tumor protein p53'. I would have to open every gene page to learn the species."
- "Which papers in the graph mention the CFTR gene, and what do they cover?": "I got 54 rows of 'PMID:10075921' and so on in Researcher, and 54 rows that each say only 'Published paper' in Plain language." The same happens on any gene question with the word papers, literature, publications or mentioned in it, because those select the graph's paper template (`tools/cypher_templates.py:217`), and card 105's window question shows the same bare ids.

## The cause

| Link | Cause | Evidence |
|---|---|---|
| rs334 label, 1 | The dbSNP pseudo-row puts `clinical_significance` first, on purpose: the shaping docstring says "a variant's clinical significance ahead of its rs id" | `core/graph.py:4955`, row at `:5027` to `:5050`; probe: field order `clinical_significance, functional_consequence, rsid, genes, chrpos` |
| rs334 label, 2 | `_pick_representative_field` prefers `name`, else the first usable field, so the row's one finding is the significance list | `core/graph.py:9469` |
| rs334 label, 3 | `record_label` reads `name`, `title`, `symbol`, `preferred_name`, then the CURIE (empty for every pseudo-row, `core/graph.py:4896`), then the finding's value. The dbSNP row has none of the first five, so the list shows the significance list. `summary_label` falls through to the same label | `synthesis/answer_layout.py:787`, `:794`, `:1582` |
| rs334 label, 4 | When LitVar2's rs334 match is also kept, it shares the page `snp/rs334`; `one_finding_per_record` keeps the lowest numbered view of one page, and the dbSNP finding is numbered first | `synthesis/findings.py:1154`; live 2026-10-09: "litvar2_lookup, 1 result" yet "1 source cited" |
| Gene never reaches the writer | One finding per row; `_EXPLANATORY_FIELDS` is only `summary`, so `genes` never becomes a second finding | `synthesis/findings.py:128`, `:497` |
| Orthologs | The template returns only the ortholog Gene vertex, whose keys carry no organism; the organism is one `in_taxon` hop away | Template `tools/cypher_templates.py:263`, `:581`. Phase 8.9 probe 1 (recorded, not rerun): "591 of 591 TP53 orthologs have an `in_taxon` edge", Gene keys `agent_type, id, knowledge_level, name, source, source_url, xrefs` |
| Papers | An Article's `name` is the PubMed title, quarantined as untrusted text: `fields` are emptied, so the finding falls back to the PMID | `core/graph.py:7539`, `_sanitized_citeable_row` `:7584`, `_rows_for_citation` `:7608` |

The quarantine is a security control and stays. The titles must come from PubMed's own record, through the `ncbi_efetch` path the product already verifies.

## The smallest fix

Four slices, each its own pull request, ranked by what a person notices first. The expected slices are confirmed with three corrections:

1. Card 37 step 3 must not reorder the dbSNP pseudo-row. That would change the prompt and the trust verdict of every rs id question: `clinical_significance` is a high-risk field token (`synthesis/trust.py:63`; probe: `risk_tier_for("clinical_significance", ...)` is high, `rsid` is low), and `dbsnp` citations take their hedged or asserted label from it (`tools/ncbi_dbsnp.py:1648`). The fix lives in the list only.
2. Labelling the row by its rs id alone would make the answer worse when no written sentence survives (the 2026-10-09 rs334 answer was exactly that fallback): the significance values, including "pathogenic", would vanish from the screen. So slice A1 also shows them in their own labelled column.
3. Card 37 step 2 splits: the gene shown in the list (A1, layout) and the gene given to the writer (A2, runnable behaviour). The list reaches the person every time; a writer sentence reaches them only when it survives the gate.

### Slice table

| Rank | Slice | What changes, in the person's words | File fence | Answer path | Dial | Size | Migration, package, event schema, setting |
|---|---|---|---|---|---|---|---|
| 1 | A1, card 37 step 3 and the gene in the list | "rs334's record is called rs334. Its table row shows the gene HBB and, in its own column, the clinical significance values dbSNP lists. In Plain language it reads 'Genetic variant (HBB)'." | `synthesis/answer_layout.py` only: `TABLE_COLUMNS` gains `"Variant record": ("genes", "Variant", "Gene")`; `record_label` gains a closed label table keyed by row type, `Variant record` reading `rsid`; `record_status_or_year` gains a closed (row type, field) column table with `("Variant record", "clinical_significance")` to "Clinical significance"; `plain_record_label` gains a closed (row type, field) suffix table with `("Variant record", "genes")` | No for the writer; yes for the code-built opening sentence | 1, layout | S | None. Four cells, exactly the `cells` cap (`contracts/events.py:428`) |
| 2 | C, card 38 step 2, papers by title | "Every paper the knowledge graph found is listed by its title, in both depths, and the written answer can name it." | New `synthesis/article_titles.py` (mirrors `synthesis/mesh_terms.py`); `core/graph.py`: the resolution block of `_write_answer` (`:13942` to `:13985`) and `_prefetch_answer_names` (`:8738`) so the lookup hides behind the reader pass; `synthesis/findings.py`: the title line in `build_synth_messages` (`:1981`). `_sanitized_citeable_row`, `_split_rows_by_trust`, `_untrusted_rows_free_text` byte-identical | Yes | 2, with the adversary (untrusted titles enter the writer's prompt) | M | None |
| 3 | B, card 38 step 1, orthologs with species | "TP53's orthologs list their species: an Organism column in Researcher, 'tumor protein p53 (Oryctolagus cuniculus)' in Plain language. The answer still says 591 orthologs." | `tools/cypher_templates.py` (single-gene ortholog template only, plus a value fold and `FOLD_FIELD_ORGANISM`); `tools/cypher_query.py` (`_apply_fold` for strings, and the count gate at `:2099` so a value-fold template keeps its total); `synthesis/answer_layout.py`: one row `("Gene", "organism")` in A1's two closed tables | No for the writer; yes for the graph call's rows | 2 | M | None |
| 4 | A2, card 37 step 2, the gene for the writer | "The written answer can say rs334 is in HBB, cited to its dbSNP record." | `synthesis/findings.py` `build_synth_findings` (one companion, row type `Variant record`, field `genes`, emitted as `gene`); `core/graph.py` `_layer3_base_citation` (`:12405`, map `gene` to `genes`) | Yes | 2 | S | None |

Why this order:

- A1 first: the owner is retesting card 37 now (retest row 18), its label "protective" on the sickle cell variant is the most misleading of the three, and it is the smallest and safest change.
- C before B: C reaches every gene question that asks about papers, the one-paper template's cited and citing papers (card 15, `ac3dded8`), and card 105's window question; B reaches only ortholog questions.
- A2 last and optional: once A1 shows HBB in the list, A2 adds only prose.

The organism half of T-8.9-03 (a companion finding per ortholog) is left out on purpose. The companion passes through the same 100-finding display cap (`_MAX_FINDINGS_FOR_DISPLAY`, `core/graph.py:9192`), so 100 orthologs would take 200 findings and the list would drop to about 50 orthologs. The list (slice B) already answers "which species".

### What each slice could make worse, and the test that catches it

| Slice | Who else is touched | Risk | Caught by |
|---|---|---|---|
| A1 | Every dbSNP record in every list and opening sentence: every rs id question | The writer's input and the trust verdict must not move | A guard test: `build_synth_findings` on the probe 3 row still yields field `clinical_significance` first, and `risk_tier_for` on it stays high |
| A1 | Opening sentence | Reads "Found 1 variant record record for rs334: rs334 [1]", redundant. Pre-existing doubled "record record" (PR-37-02 of the 2026-10-09 check) is not on the board | A test pins the new sentence; the doubled noun is a separate card for the lead to file |
| A1 | Other types without a name field (PubTator3 publications, Layer 2 gene rows with `organism`, LitVar2 `Literature variant` rows with `gene`) | A label or suffix leaking past `Variant record` | Tests: each of those rows keeps today's label, column and plain label exactly |
| A1 | Researcher table width | Four cells is the event cap; a fifth would fail validation | A test builds the rs334 table and asserts four cells |
| C | Every answer with graph Article rows (gene paper questions, card 15's one-paper template, model-written Cypher returning Articles) | Prompt injection through a title; titles joined to the wrong PMID; a paper's citation moves from the knowledge graph to the live APIs in Sources, as MedGen names did in phase 6.2 (`synthesis/findings.py:752`, "Why the layer changes"), so "from 1 layer" could read as if the graph found nothing | Tests from T-8.9-01's acceptance: join by `NcbiEfetchRecord.id` with shuffled order, a hostile title cleaned to one line, every failure class leaves the PMID; the adversary's quote-path hunt; the product reviewer checks the Sources wording on G-021 |
| C | Written prose | `drop_record_restatements` drops a sentence that only restates a listed title, so the written part may shrink to the fallback more often | Live: G-021's fallback note rate before and after (baseline: the note in 2 of 3 passes, phase 8.2 run) |
| C | 20-call ceiling | Two more calls; a question near the ceiling keeps PMIDs | Test: budget at 20, no request, every finding keeps its PMID, nothing raised |
| B | Every single-gene ortholog or homolog question (`gene_orthologs_one`) | The template's RETURN becomes two columns, and develop skips the count query for two columns (`tools/cypher_query.py:2099`; probe: `_return_column_count` is 2), so "100 of 591" would become "100 of unknown" | Test: a stubbed count returns 591 and `total_available` stays 591 |
| B | Same | A taxon becoming a row of its own, or a non-string item rendered with `str()` | Tests: row count unchanged at 100; a dict item in the list column is ignored |
| B | Layer 2 `gene` rows, which carry `organism` | Suffix or column leaking onto every gene answer | Test: the closed table keys on the exact type `Gene`; a Layer 2 `gene` row is unchanged |
| A2 | Every rs id question | One more finding in the prompt; if only the gene sentence survives, the verdict moves from the fallback to an answer (the most restrictive claim still governs, `synthesis/trust.py:477`) | T-8.9-03's replay through the unchanged `run_grounding_pass`; G-024 live before and after |

### Timing cost

| Slice | Cost | Evidence |
|---|---|---|
| A1 | None. No call, no new finding | Code read |
| A2 | None measurable. One more prompt line | Code read |
| B | About 0.2 s on ortholog questions: the main query 5.1 s against 5.01 s, and the count query (which runs after it) 5.44 s against 5.35 s | Phase 8.9 probe 1, recorded 2026-09-26, not rerun tonight |
| C | About 0.5 s per 50 PMIDs; two requests run concurrently for up to 100. Hidden behind the reader pass when it runs in `_prefetch_answer_names`, since a graph Article result is exactly what starts the reader pass | Measured tonight: three EFetch calls for 50 of G-021's PMIDs, `rettype=abstract`, `retmode=xml`, no key: 0.490 s, 0.472 s, 0.490 s (median 0.49 s), 50 of 50 titles, none blank, none with a line break, longest 214 characters. The product's own parser, `_extract_pubmed_articles` (`tools/ncbi_eutils_actions.py:1232`), took 0.016 s on that body |

C's measurement settles T-8.9-01's stop rule: 0.49 s is far under the 3 s median, so EFetch stands and no ESummary allowlist deviation is needed. It was measured from this shell, not through the product's transport and pool, so the builder still pastes the in-product time on G-021.

Both ortholog and paper questions were already over the 20 s goal before phase 8.7: G-016 at 27.2 and 28.1 s, G-021 at 23.7 to 25.0 s (`testing/Developer/reports/2026-09-29_card63_golden/runs.jsonl`). That is why C should run in `_prefetch_answer_names` rather than serially in Write.

## Tests

Each test below fails on develop's code (shown by tonight's offline probe) and passes on the fix.

| Slice | Test file | Test | Fails on develop because |
|---|---|---|---|
| A1 | `tests/system_03_search_agent/synthesis/test_answer_layout.py` | `test_dbsnp_record_is_labelled_by_its_rs_id_not_its_significance_list`: `record_label` and `summary_label` on the probe 3 row return "rs334" | Both return "not-provided, protective, likely-benign, pathogenic, other" |
| A1 | same | `test_dbsnp_record_table_shows_its_gene_and_its_significance`: `table_second_cell("Variant record", ...)` is "HBB" and `record_status_or_year` is `("Clinical significance", "not-provided, protective, likely-benign, pathogenic, other")` | Both return None |
| A1 | same | `test_plain_dbsnp_label_names_the_gene`: `plain_record_label` is "Genetic variant (HBB)" | Returns the significance list |
| B | `tests/system_03_search_agent/tools/test_cypher_templates.py` | `test_single_gene_ortholog_template_reads_each_organism`: the template keeps the name `gene_orthologs_one`, contains `OPTIONAL MATCH (x)-[:in_taxon]->`, passes `validate_cypher`, and declares the organism value fold | No `in_taxon`, fold None |
| B | `tests/system_03_search_agent/tools/test_cypher_fold_templates.py` | `test_value_fold_writes_organism_and_keeps_the_total`: stubbed rows give `fields["organism"] == "Oryctolagus cuniculus"`, 100 rows, `total_available == 591` | No value fold; two columns skip the count |
| B | `tests/system_03_search_agent/synthesis/test_answer_layout.py` | `test_ortholog_row_shows_its_organism`: Organism column and "tumor protein p53 (Oryctolagus cuniculus)" | Probe: column None, plain label "tumor protein p53" |
| C | new `tests/system_03_search_agent/synthesis/test_article_titles.py` | `test_graph_paper_is_named_by_the_title_pubmed_returns`: a `curie_fallback` `PMID:` finding becomes field `title`, `name_resolved`, `layer_2_api`, `ncbi_efetch`, joined by PMID under shuffled order | The module does not exist |
| C | new `tests/system_03_search_agent/core/test_article_title_wiring.py` | `test_write_prompt_reads_article_title_not_bare_pmid` with a stubbed fetch; plus `test_quarantine_still_empties_article_fields` | Prompt reads "Article record PMID:10075921" |
| A2 | new `tests/system_03_search_agent/synthesis/test_companion_findings.py` | `test_dbsnp_row_gives_the_writer_its_gene`: a `gene` finding "HBB" right after the row's own, same page; none for a `Literature variant` row | No such finding |
| A2 | same | `test_gene_companion_is_cited_by_the_dbsnp_builder`: shaped like `core/test_layer_handoff.py:860`, citation `source == "dbsnp"` | `dbsnp_build_citation(raw, "gene")` raises, so the generic fallback cites `source` "ncbi_dbsnp" |

## Overlap with tonight's other cards

| Card | Its likely fence | Overlap with these slices |
|---|---|---|
| 105, a picked window limits graph papers | `core/breadth_plan.py`, `tools/cypher_templates.py`, Plan wiring | Conflicts with C in meaning, not in code: both decide how a gene's graph Article records are shown, and 105's board text names the bare ids C fixes. Card 105's own diagnosis tonight (`testing/Developer/reports/2026-10-16_card105/diagnosis.md`, link 5) finds an Article vertex carries no publication date, so its recommended fix removes graph Article rows on a windowed question. Then C has nothing to resolve there and spends no EFetch call; on every unwindowed question C works as designed. Either can land first. The one real collision is option (a) of that diagnosis, dating graph papers live: it would need the year from the same PubMed fetch C adds (tonight's 50 records all carry `PubDate`, but `_extract_pubmed_articles` keeps only `title` and `abstract`). If the owner picks (a), one resolver must serve both, never two EFetch calls per paper, and C should land first. If 105 edits `_write_answer`, merge the two one after the other |
| 30, BRCA1 pathogenic variants note | `synthesis/answer_layout.py` beside `variant_to_disease_source_note`; `core/graph.py` a Think decision and `_write_answer` | A1 and B edit other functions of `answer_layout.py` (no textual clash expected). C edits `_write_answer`'s resolution block, card 30 edits elsewhere in `_write_answer`: merge one after the other and rerun both suites |
| 18, `_answer_tokens` merge | `core/graph.py` `_answer_tokens` | No slice edits `_answer_tokens`. A1 and B change the cells its merge compares (`merge_into`); A1 makes every finding of the rs334 page carry the same label, which helps that merge. Run card 18's tests after A1 and B |
| 8, the trust line wording | `synthesis/trust.py`, `contracts/events.py` comment | No shared file. C changes which database a paper claim is named under (PubMed, not the knowledge graph); A2 adds a dbSNP claim. Whichever merges second reruns the trust line tests on G-021 and G-024 |
| Within these slices | | A1 and B share `answer_layout.py`'s two closed tables: B adds one row to each, rebased on A1. A2 and C share `synthesis/findings.py` and `core/graph.py`, in different functions. All four can be built in parallel worktrees and merged one at a time |

## Needs the owner

One decision, and it blocks none of the four slices.

1. The condition for an rs id (G-024's second half, card 37's "no condition").
   - Recommended: queue it as the next card after A1, not tonight. Phase 8.9's probe 2 found ClinVar holds "Hb SS disease" for rs334 (record 15333), but 9 of the 10 records a ClinVar search for rs334 returns are compound records or another allele (c.20A>C, "Likely benign"). A correct version needs a new search per rs id, an exact single-variant filter and the placeholder rule: a medium card with its own review. Until then rs334 names its gene and not its condition.
   - Build it now: about one more ClinVar search per rs id question, a few tenths of a second, and a real risk of naming a compound record's condition as rs334's. A confident wrong condition is worse than none.
   - Leave it out entirely: the question's second half stays unanswered, and card 37 cannot close.

Not the owner's, decided from the user's chair and logged by the lead:

- Building 8.9's tickets as standalone pull requests: both cards are already "Team: buildable now" on the board.
- The Plain language label "Genetic variant (HBB)": it keeps rule 12.9's titles only (no identifier) and follows the "(organism)" shape 8.9 already planned.
- Dropping the ortholog organism companion: it would halve the ortholog list.
- Papers moving to the live APIs group in Sources: phase 6.2's MedGen precedent, required by the layer authority gate.

## Test query

Query 23 covers A1 and A2. Proposed lines for its "What you should see", same shape (do not edit the file here):

```markdown
- rs334's record is called rs334, never "not-provided, protective, likely-benign, pathogenic, other". In Researcher its row shows the gene HBB and, in a column of its own headed "Clinical significance", the values dbSNP lists. In Plain language it reads "Genetic variant (HBB)".
```

No query covers B or C. Query numbers up to 114 are taken, and card 105's diagnosis proposes 116, so these use 115 and 117. The numbers are provisional; the lead assigns them when filing.

```markdown
### 115. A gene's orthologs name their species (card 38, G-016)

Queries to try:

- `What are the known orthologs of TP53 in other species?`: ask it once in Plain language and once in Researcher.

What you should see:

- Each ortholog listed with its species, for example "tumor protein p53 (Oryctolagus cuniculus)" in Plain language, and an Organism column in Researcher.
- Never a list of rows that all read "tumor protein p53" with no species.
- The answer still says how many orthologs the knowledge graph holds, 591 for TP53, against how many are shown.
- Why it matters: the person asked which species carry the gene; a list of identical names answers nothing.

### 117. Papers in the graph are named by their titles (card 38, G-021)

Queries to try:

- `Which papers in the graph mention the CFTR gene, and what do they cover?`
- `What is the latest literature on BRCA1?`

What you should see:

- Each paper listed by its title, linked to its PubMed page, in both Plain language and Researcher.
- Never a list of bare "PMID:..." rows, and never a Plain language list where every row reads "Published paper".
- Plain language and Researcher list the same papers.
- Why it matters: a paper's number tells a person nothing about what it covers; they would have to open every link to learn what the answer found.
```
