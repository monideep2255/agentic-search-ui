# Card 32 fresh verifier report

Verifier checkout: <repo-root>, HEAD a25eb563 (git rev-parse HEAD matched the expected tip). Base: origin/develop. No live model calls; probes are local Python and targeted pytest runs.

## Findings

### V-32-01: a map value's inner keys are not renamed

- Severity: minor (unsure; no consumer I found reads a nested key, and develop behaves identically)
- What: `_graph_field_names` renames top-level field names only. A column returning a Cypher map keeps a reserved key inside the value.
- Reproduction: p32_map.py at HEAD a25eb563, `to_output_rows({"c0": '{"clinical_features": ["Arachnodactyly"], "name": "x"}'}, snapshot_version="v", derived_source_curie="MedGen:C0024796")` gave `'fields': {'c0': {'clinical_features': ['Arachnodactyly'], 'name': 'x'}}`.
- Why it matters: only if a consumer or the writing model reads the nested key as MedGen's list. Every code consumer I read keys on the top-level field name, so this is filed for the record, not as a blocker. Not worse than develop.
- NOT FIXED

## Fix-round findings, re-derived

- A-32-01 and J-32-01 (rename collides with a real `graph_` alias and drops a value): FIXED.
  - Fuzz p32_fuzz.py: 24000 random label lists of 1 to 6 distinct labels drawn from the four reserved names, their `graph_` and `graph_graph_` forms, and ordinary names. Checked: output names all distinct, none reserved, every ordinary label unchanged. Output `cases 24000 bad 0`.
  - End to end, three columns aliased `clinical_features`, `graph_clinical_features`, `graph_graph_clinical_features`: `{'graph_graph_graph_clinical_features': 3, 'graph_clinical_features': 7, 'graph_graph_clinical_features': 9}`. All three values kept.
  - Mutation `while label in taken:` to `while False:`: "8 failed, 110 passed". Mutation `taken = set()`: "8 failed, 110 passed". Both restored.
- A-32-02 and J-32-02 (vertex or edge property not renamed): FIXED. A Disease vertex with `hpo_id` and `graph_hpo_id` properties shaped to `{'id': 'MedGen:C0024796', 'name': 'Marfan', 'source_url': ..., 'graph_graph_hpo_id': 'HP:1', 'graph_hpo_id': 'g'}`, `source_url` and `curie` unchanged. Mutation back to `fields = dict(properties)`: "4 failed, 114 passed". Restored.

## Worse than develop

- Ordinary graph rows unchanged: p32_dev.py printed a derived row (`variant_count`, `name`), a Gene vertex and an edge with `_edge_start_id`, `_edge_end_id` and `_cited_via_endpoint_curie`. Output byte-identical at HEAD and develop, md5 `1c82964c59d6f9d16efa928e4c407e55` on both.
- Real MedGen clinical features: the reserved set equals the consumers' constants (`synthesis/findings.py:167` "clinical_features"; `core/graph.py:7692` to `:7694`). The feature rows are built in `core/graph.py` from the MedGen record and never pass through `cypher_provenance` (`_graph_field_names` is referenced only in `tools/cypher_provenance.py`). Tests: `core/test_disease_breadth.py` "49 passed in 2.61s", `synthesis/test_listing_one_row_per_record.py` "29 passed in 1.78s", `core/test_graph.py -k "clinical_feature or medgen"` "6 passed, 232 deselected in 2.21s".
- No System 1 parser writes these property names into the graph: a search of the reference data repository found `hpo_id` only as a local variable in `system-01-data-pipelines/medgen/parse_hpo_omim.py:76` to `:99`, never a node property. So no real graph row is renamed today.
- Nothing worse found.

## Items left open

- A-32-03 (the renamed field still contains the words "clinical features" for the writing model): on develop the same column reached the model as `clinical_features` and also reached the MedGen panel code by name. HEAD removes the code path and leaves only the word. No worse than develop. Not probed live.

## Tests run

- `tools/test_cypher_provenance.py`: "118 passed in 1.65s".
- `tests/system_03_search_agent/tools`: "1672 passed, 99 skipped, 3 warnings in 26.71s".

## Verified by own probe versus read

- Own probe: A-32-01 and A-32-02 fixes (fuzz, end to end, three mutations), ordinary-row equality with develop, the regression tests above.
- Read only: that every downstream consumer keys on the top-level name, A-32-03.

Verdict: MERGE. Both fixed findings hold under my own probes and mutations, ordinary graph rows are byte-identical to develop, and V-32-01 is no worse than develop.
