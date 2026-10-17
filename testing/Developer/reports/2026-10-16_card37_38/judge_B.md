# Judge report: card 38 slice B, orthologs with species

Pull request #265, branch `fix/card38-orthologs-with-species`, one commit `dfdc27c0` on develop `655e9dfe`. Judge worktree `<worktrees>/card38b-judge` (detached at the head), develop comparison worktree `<worktrees>/card38b-judge-dev` (detached at `655e9dfe`). Probes in `<scratchpad>/card38b_judge/`. Read-only graph calls through the product's own `cypher_query` tool, no model call, no write.

The lead's decision: "B (TP53's orthologs carry their species through an `in_taxon` fold, keeping the 591 total)."

## Table of contents

- [Findings](#findings)
- [Live graph, branch against develop](#live-graph-branch-against-develop)
- [Every other template is unchanged](#every-other-template-is-unchanged)
- [Production standards gates](#production-standards-gates)
- [The value fold for strings](#the-value-fold-for-strings)
- [The count gate](#the-count-gate)
- [The closed tables and the Layer 2 gene row](#the-closed-tables-and-the-layer-2-gene-row)
- [Break it, does a test go red](#break-it-does-a-test-go-red)
- [Tests and lint gates](#tests-and-lint-gates)
- [Verdict](#verdict)

## Findings

None filed. Each check below carries its evidence.

## Live graph, branch against develop

Probe `<scratchpad>/card38b_judge/live_orthologs.py`, run once from each worktree, the same `.env`, the audit sink off. Three questions through `cypher_query` with a harness that raises if the plan tier is called (so only the template path runs).

Branch:

```
branch | What are the known orthologs of TP53 in other species?
  status ok template gene_orthologs_one rows 100 total_available 591 truncated True distinct 100 seconds 8.98
  query 4.05 s raw_rows 100 | MATCH (a:Gene {id: $e_NCBIGene_7157})-[:orthologous_to]->(x:Gene) OPTIONAL MATCH (x)-[:in_taxon]->(t:OrganismTaxon) WITH x, collect(DISTINCT t.name) AS xs RETURN x, xs ORDER BY x.id LIMIT 100
  query 4.92 s raw_rows 1 | MATCH (a:Gene {id: $e_NCBIGene_7157})-[:orthologous_to]->(x:Gene) OPTIONAL MATCH (x)-[:in_taxon]->(t:OrganismTaxon) WITH x, collect(DISTINCT t.name) AS xs RETURN count(*) AS total_count LIMIT 1
  curie digest 0d12e9b1eb6bb0f5
branch | What diseases is TP53 associated with?
  status ok template gene_diseases_one rows 12 total_available 12 truncated False distinct 12 seconds 0.65
  curie digest 5c335e1377389a26 rows digest fa729ea7e54adb8d
branch | What are the known orthologs of BRCA1 in other species?
  status ok template gene_orthologs_one rows 100 total_available 514 truncated True distinct 100 seconds 10.09
  query 5.12 s raw_rows 100 | ... OPTIONAL MATCH (x)-[:in_taxon]->(t:OrganismTaxon) WITH x, collect(DISTINCT t.name) AS xs RETURN x, xs ORDER BY x.id LIMIT 100
  query 4.93 s raw_rows 1 | ... WITH x, collect(DISTINCT t.name) AS xs RETURN count(*) AS total_count LIMIT 1
  curie digest 4fccd47be5f0d3a7
```

Develop:

```
develop | What are the known orthologs of TP53 in other species?
  status ok template gene_orthologs_one rows 100 total_available 591 truncated True distinct 100 seconds 10.05
  query 5.06 s raw_rows 100 | MATCH (a:Gene {id: $e_NCBIGene_7157})-[:orthologous_to]->(x:Gene) RETURN x ORDER BY x.id LIMIT 100
  query 4.98 s raw_rows 1 | MATCH (a:Gene {id: $e_NCBIGene_7157})-[:orthologous_to]->(x:Gene) RETURN count(*) AS total_count LIMIT 1
  curie digest 0d12e9b1eb6bb0f5
develop | What diseases is TP53 associated with?
  status ok template gene_diseases_one rows 12 total_available 12 truncated False distinct 12 seconds 0.52
  curie digest 5c335e1377389a26 rows digest fa729ea7e54adb8d
develop | What are the known orthologs of BRCA1 in other species?
  status ok template gene_orthologs_one rows 100 total_available 514 truncated True distinct 100 seconds 10.97
  curie digest 4fccd47be5f0d3a7
```

Row by row comparison of the saved outputs (`live_branch.json` against `live_dev.json`):

```
What are the known orthologs of TP53 in other species?
  rows identical to develop apart from organism: True | rows with organism: 100 of 100 | multi-taxon: 0 | develop rows with organism: 0
  samples: [('NCBIGene:100009292', 'tumor protein p53', 'Oryctolagus cuniculus'), ('NCBIGene:100049321', 'tumor protein p53', 'Oryzias latipes'), ('NCBIGene:100062044', 'tumor protein p53', 'Equus caballus')]
  distinct organisms: 100 max length 30
What diseases is TP53 associated with?
  rows identical to develop apart from organism: True | rows with organism: 0 of 12 | multi-taxon: 0 | develop rows with organism: 0
What are the known orthologs of BRCA1 in other species?
  rows identical to develop apart from organism: True | rows with organism: 100 of 100 | multi-taxon: 0 | develop rows with organism: 0
  samples: [('NCBIGene:100049662', 'BRCA1 DNA repair associated', 'Sus scrofa'), ('NCBIGene:100051990', 'BRCA1 DNA repair associated', 'Equus caballus'), ('NCBIGene:100224649', 'BRCA1 DNA repair associated', 'Taeniopygia guttata')]
  distinct organisms: 100 max length 30
```

What this shows:

- The live graph accepts the new template and its count query (no edge alternation, `OPTIONAL MATCH ... WITH ... collect(DISTINCT ...)` runs).
- Row count 100, `total_available` 591 for TP53 (514 for BRCA1), the same as develop. The same 100 CURIEs in the same order (identical digest), the same type `Gene`, the same edge type `orthologous_to`, the same source URLs and the same fields; the only addition is `organism`, on 100 of 100 rows.
- Time: branch 8.98 s against develop 10.05 s for TP53, 10.09 s against 10.97 s for BRCA1, one run each. The new main query is 4.05 s against 5.06 s and the count 4.92 s against 4.98 s. Not slower within one run's noise; the extra hop costs nothing measurable.
- `count(*)` after `WITH x` counts one row per distinct ortholog, and it equals develop's path count (591 both), so there is no duplicate `orthologous_to` edge for TP53 that would make the two counts disagree.

## Every other template is unchanged

Probe `<scratchpad>/card38b_judge/dump_templates.py`, run against each tree. For every template in `all_template_examples()` it records the Cypher, the validator result, the fold, `value_fold`, the RETURN column count, the count query `_build_count_cypher` builds, and the two edge maps `_run_pipeline` computes (`_traversed_edge_type_by_column` and `_ambiguous_high_risk_edge_touch_by_column`), on the text the branch actually reads (`edge_text`, `cypher_query.py:2188`).

```
46 templates   (branch)
46 templates   (develop)
identical in every field (cypher, edge map used, ambiguous map used, count cypher, columns): 45
differ: ['gene_orthologs_one']
value_fold True: ['gene_orthologs_one']
edge text differs: ['gene_orthologs_one']
```

For the one that differs:

```
edge_full    dev {'c0': 'orthologous_to'}   branch {}
edge_used    dev {'c0': 'orthologous_to'}   branch {'c0': 'orthologous_to'}
amb_full     dev []                         branch []
amb_used     dev []                         branch []
```

The builder's edge type change, answered:

- It runs only when `value_fold` is true (`cypher_query.py:2188` to `:2192`). `value_fold` is read from the active template (`:2076`) and is False when no template is active, so model written Cypher always reads the full query, exactly as develop.
- Of the 46 templates only `gene_orthologs_one` has `value_fold`, so for the other 45 `edge_text` is the normalized query byte for byte and both edge maps are equal to develop's (above).
- On the ortholog template it restores develop's `{'c0': 'orthologous_to'}`; without it the branch would give `{}`. Live, every ortholog row carries `traversed_edge_type` `orthologous_to` on both trees.
- The ambiguous high risk map is `[]` on both trees for the ortholog template with or without the strip, so the strip changes no risk tier.
- Live, the TP53 diseases template (`gene_diseases_one`) gives the same 12 rows with an identical rows digest on both trees (`fa729ea7e54adb8d`), including the edge type field.

## Production standards gates

- Parameterized: the live query binds `$e_NCBIGene_7157`; the template text has no literal identifier and no quote (the builder's shape test asserts both, and it went red under mutation M8 below). The new names `t`, `OrganismTaxon`, `in_taxon` and `xs` are code constants, never caller text (`cypher_templates.py:629` to `:637`).
- Read-only: the template and its count both pass `validate_cypher` (live, both executed after validation; `test_the_count_query_counts_one_row_per_ortholog` asserts `validate_cypher(count, row_limit=1).ok`). `in_taxon` is a documented edge (`graph_schema_constants.py:62` and `:82`).
- Timeout: unchanged. The count query runs inside the same recomputed budget (`cypher_query.py:2158` to `:2160`, `count_budget = max(1.0, CYPHER_QUERY_TIMEOUT_SECONDS - elapsed_before_count)`) and the whole call is under `asyncio.wait_for(..., timeout=CYPHER_QUERY_TIMEOUT_SECONDS)` (`:2425` to `:2428`). Live total 8.98 s.
- No secret, no path, no personal data in the diff.

## The value fold for strings

`_fold_value_names` (`cypher_query.py:1843` to `:1879`):

- Strings only: a non-string item is skipped (`if not isinstance(item, str): continue`), never `str()` rendered. Mutation M3 turned it into `str(item)` and a test went red.
- One printable line: non-printable characters become spaces, whitespace collapses. Blanks drop, duplicates collapse through a set, then `sorted(...)[:MAX_FOLD_ITEMS]` and `", ".join`. M4, M5 and M6 each went red.
- An empty or non-list column writes nothing (`_apply_fold`, `if anchor_curie is None or not written: return`). M7 went red.
- No taxon becomes a row: live, 100 raw rows gave 100 output rows with 100 distinct CURIEs, all type `Gene`.
- `_fold_curies` and its callers are untouched: the CURIE branch of `_apply_fold` is the same call with the same arguments, and the fold templates' arms in `test_cypher_fold_templates.py` pass.

## The count gate

- Develop runs the count only for one RETURN column. The branch adds `or value_fold` (`cypher_query.py:2150`). No other template has `value_fold`, so no other template's count path moves (and the 45 count queries are byte identical, above).
- The count query keeps the `WITH x, collect(...)` prefix, so `count(*)` counts one row per ortholog. Live: 591 for TP53, equal to develop's 591; 514 for BRCA1, equal to develop's 514.
- M1 (drop `or value_fold`) went red on `test_the_list_carries_species_and_the_total_stays_591`.

## The closed tables and the Layer 2 gene row

- `("Gene", "organism")` sits last in `_ROW_TYPE_COLUMNS` (`answer_layout.py:629`) and in `_ROW_TYPE_PLAIN_SUFFIXES` (`:644`). The `Variant record` entries keep their order, so A1's first match rule for variants is unchanged.
- Exact type only: Layer 2 rows are typed by their database, lowercase (`core/graph.py:8227`, `"node_or_edge_type": record.db or "ncbi_efetch"`), and Layer 3 pseudo rows use other names ("Clinical trial", "Publication", "Variant record" and so on, `core/graph.py:5026` to `:5166`). Only a graph row is typed `Gene`, and only the fold writes `organism` onto one: a live graph Gene row's fields are `id, name, xrefs, source, agent_type, source_url, knowledge_level` on develop.
- The plain label loop in the variant branch (`answer_layout.py:1006`) iterates the new entry too, but checks `row_type == finding.entity_type`, so a `Variant record` row never takes it. The new loop (`:1027` to `:1035`) acts only when `base` is empty, which only the Gene entry has.
- Applied to the live rows (`<scratchpad>/card38b_judge/labels.py`):

```
branch  | TP53 orthologs  | distinct plain labels 100 | ['tumor protein p53 (Oryctolagus cuniculus)', 'tumor protein p53 (Oryzias latipes)'] | columns ['Organism']
branch  | TP53 diseases   | distinct plain labels 6   | ['MedGen', 'MeSH'] | columns []
develop | TP53 orthologs  | distinct plain labels 1   | ['tumor protein p53', 'tumor protein p53'] | columns []
develop | TP53 diseases   | distinct plain labels 6   | ['MedGen', 'MeSH'] | columns []
```

  The diseases labels "MedGen" and "MeSH" are a develop defect the branch does not touch (the graph's vocabulary artifact), recorded as evidence only.
- The ortholog row's citation field is still `name` (`_pick_representative_field` prefers `name`, `core/graph.py:9610`), and `organism` is not an explanatory field (`findings.py:128`, `("summary",)`), so the finding count, and with it the 100 shown and "of 591", is unchanged.

Observations, not findings:

- The Plain language suffix cuts at 100 characters (`organism.strip()[:100]`), not at a term boundary as the Researcher cell does. Live, every ortholog has one taxon and the longest name is 30 characters, so no one sees a cut today.
- On a `Gene` row the Organism column now takes the extra column slot ahead of a status or year; graph Gene rows carry neither.

## Break it, does a test go red

Probe `<scratchpad>/card38b_judge/mutate.py`: one property at a time, the five touched test files, then the file restored from memory.

```
M1 count gate ignores the value fold: RED | test_the_list_carries_species_and_the_total_stays_591
M2 edge type read from the full query: RED | test_the_list_carries_species_and_the_total_stays_591
M3 non-string item rendered with str(): RED | test_a_taxon_never_becomes_a_row_and_odd_values_never_leak
M4 names not sorted before the cap: RED | test_the_list_carries_species_and_the_total_stays_591
M5 no whitespace cleaning: RED | test_the_list_carries_species_and_the_total_stays_591
M6 no cap: RED | test_a_taxon_never_becomes_a_row_and_odd_values_never_leak
M7 empty fold still writes the field: RED | test_a_taxon_never_becomes_a_row_and_odd_values_never_leak
M8 OPTIONAL MATCH becomes MATCH: RED | test_the_ortholog_template_reads_each_organism_and_stays_read_only
M9 template drops value_fold: RED | test_the_ortholog_template_reads_each_organism_and_stays_read_only
M10 Researcher column keyed on lowercase gene: RED | test_ortholog_row_shows_its_organism
M11 plain label ignores the row type: RED | test_gene_rows_without_an_organism_and_other_row_types_are_unchanged
M12 plain label drops the string check: RED | test_gene_rows_without_an_organism_and_other_row_types_are_unchanged
M13 optional pattern never strips: RED | test_the_list_carries_species_and_the_total_stays_591
M14 plain suffix table drops the Gene row: RED | test_ortholog_row_shows_its_organism
```

14 of 14 red. M4's red on the first arm depends on set order for two names; the odd values arm checks sorting over 32 names, so the property stays pinned.

## Tests and lint gates

New file, neighbours, layout and variant label:

```
PYTHONPATH=src venv/bin/python -m pytest -q test_cypher_ortholog_organism.py test_cypher_fold_templates.py test_cypher_templates.py test_cypher_query.py test_cypher_query_templates.py test_cypher_query_budget.py test_cypher_query_e2e.py test_cypher_query_premise.py test_cypher_provenance.py test_cypher_validator.py test_cypher_generation.py test_cypher_schemas.py synthesis/test_answer_layout.py synthesis/test_variant_record_label.py
579 passed, 32 skipped in 15.72s
```

CI's gates as `.github/gates/` runs them:

```
gate01: python -m compileall -q src services tests alembic -> exit 0; the three module import -> import ok
gate02: isort --check-only --diff src tests services tracker alembic .claude .github -> Skipped 2 files, exit 0
gate03: ruff check -> All checks passed!, exit 0
```

`git status --short` in the judge worktree after every probe: empty.

## Verdict

Nothing on this branch shows any person anything worse than develop:

- TP53's orthologs: the same 100 records, the same order, the same 591 total, the same edge type, now each with its species; no slower (8.98 s against 10.05 s, one run each).
- Every other question: 45 of 46 templates, their count queries and their edge maps are byte identical to develop, the model path is untouched, and the layout change keys on a type and field only the ortholog fold produces.

No findings filed.

VERDICT: PASS
