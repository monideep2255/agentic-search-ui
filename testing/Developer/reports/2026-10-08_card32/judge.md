# Card 32 judge report, round 1

Judge base: HEAD ee09aff5a10c56618cb5ebebb7426c09fc2c5572, compared with origin/develop. Findings are written as they are established.

## Findings

### J-32-01: the rename can collapse two graph columns onto one key and silently drop a value (inside this card's fix)

- Severity: minor (latent: the model must choose both aliases), but it sits inside the fix and undoes an invariant the alias parser already guards
- Evidence: `cypher_query.column_labels_for` refuses duplicate aliases for exactly this reason: "A duplicate alias would collapse two columns onto one key and silently drop a value. Keep both positional instead." (`tools/cypher_query.py:511` to `:515`). The new `_graph_field_name` (`tools/cypher_provenance.py:857` to `:861`) maps `clinical_features` to `graph_clinical_features` after that check, so a second column already aliased `graph_clinical_features` collides in the dict comprehension (`tools/cypher_provenance.py:904` to `:906`). Probe through the real alias parser:

  ```
  labels: {'c0': 'clinical_features', 'c1': 'graph_clinical_features'}
  [{'node_or_edge_type': 'derived', 'curie': 'NCBIGene:2200', 'fields': {'graph_clinical_features': 7}, ...}]
  ```

  "Arachnodactyly" (column c0) is gone with no signal. On origin/develop both columns survived under their own names.
- Smallest fix: in `_shape_derived_value`, when the renamed name is already one of this row's labels, keep the positional column name (`c0`) instead, the same rule `column_labels_for` uses; add a test with the two aliases above.

### J-32-02: a vertex or edge property with a reserved name is not renamed

- Severity: minor, unsure (no graph property carries these names today)
- Evidence: the rename sits only in `_shape_derived_value`; `_shape_entity` still copies a vertex's properties as they are (`fields = dict(properties)`, `tools/cypher_provenance.py:731`). Probe:

  ```
  [{'id': 'NCBIGene:2200', 'name': 'FBN1', 'clinical_features': 'Arachnodactyly'}]
  ```

  A search of `docs/`, `requirements/` and the tool schemas for `clinical_features`, `hpo_id` or `disease_title` finds nothing outside this fix, and `_pick_representative_field` prefers `name`, so this is not reachable on today's graph. Filed so the fence is written down: the fix closes model-chosen aliases, not graph property names.
- Smallest fix: none needed for this card. If the graph ever gains such a property, apply `_graph_field_name` to property keys in `_shape_entity` too.

## Checks with evidence

- Correctness: every consumer of the reserved names keys on the field name alone (`synthesis/findings.py:1875`, `:1235`, `:1247`, `:1268`; `core/graph.py:8871` area, `:12362`; the three row extras at `core/graph.py:7692` to `:7694` are read only from rows behind a `clinical_features` finding). Probe of a graph column aliased `clinical_features` through `to_output_rows`, `build_synth_findings` with the production `_pick_representative_field`, and `build_clinical_features_directive`:

  ```
  rows: [{'graph_clinical_features': 'Arachnodactyly'}]
  synth fields: [('graph_clinical_features', 'Arachnodactyly')]
  directive non-empty: False
  ```

- No template in `src/` aliases a reserved name (search for `AS clinical_features|clinical_features_total|hpo_id|disease_title`: no hits), so no code-chosen graph query is renamed.
- Real MedGen feature path: built in `core/graph.py` `_with_medgen_clinical_feature_rows` from the `ncbi_efetch` record, never through `cypher_provenance`. Tests: `test_disease_breadth.py` "49 passed in 3.64s", `test_listing_one_row_per_record.py` "29 passed in 2.50s", `test_graph.py -k "clinical_feature or medgen"` "6 passed, 232 deselected".
- Security: a set-membership check on the alias the existing parser already restricted to `[A-Za-z_][A-Za-z0-9_]*` (`tools/cypher_query.py:440`); no free-text reading, no query or log change. `ruff check` on both changed files: "All checks passed!".
- Tests: `test_cypher_provenance.py` "110 passed in 1.89s"; `tests/system_03_search_agent/tools` "1664 passed, 99 skipped, 3 warnings in 25.97s".
- Mutations, each restored with `git checkout`: rename disabled "4 failed, 106 passed"; `clinical_features` removed from the set "1 failed, 109 passed"; every label prefixed "5 failed, 105 passed"; helper not called "4 failed, 106 passed". All red. `git diff --stat HEAD` empty afterwards.

## Verdict

FIX FIRST: J-32-01. It is minor and latent, but it sits inside this card's own fix and reintroduces the silent column collapse `column_labels_for` was written to prevent; the fix is a few lines. J-32-02 needs no action.
