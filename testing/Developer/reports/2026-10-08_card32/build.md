# Card 32 build: a graph column named clinical_features is not MedGen's

## Base

- c916cfa30f59802dfd85c81ef7ba39bdcfc2b263 (origin/develop), branch fix/card32-reserved-feature-names.

## What changed

- `src/system_03_search_agent/tools/cypher_provenance.py`: a reserved set (`clinical_features`, `clinical_features_total`, `hpo_id`, `disease_title`) and a small helper `_graph_field_name`. `_shape_derived_value` renames a Layer 1 field whose name is in the set to `graph_<name>`. A name check on our own strings, no reading of text. No consumer changed.
- `tests/system_03_search_agent/tools/test_cypher_provenance.py`: two tests (one parametrized over the four names, one showing an ordinary alias is untouched).

## Tests

- `test_cypher_provenance.py`: 110 passed.
- `tests/system_03_search_agent/tools`: 1664 passed, 99 skipped.
- ruff check: all checks passed. isort --check-only: clean.

## Mutation check

- Narrowed the reserved set to `hpo_id` and `disease_title` only: 2 failed (the `clinical_features` and `clinical_features_total` cases), 108 passed. Restored; 110 passed.

## Deviations

- No test query entry added: the diagnosis names none (no live query can trigger this; it proposes a unit test, with queries 87 and the Marfan query as existing regressions). Nothing in `testing/Test_queries_and_workflows.md` changed.

## Learnings

- None.

## Fix round

Base: ee09aff5a10c56618cb5ebebb7426c09fc2c5572.

- A-32-01 and J-32-01: `_graph_field_name` is replaced by `_graph_field_names`, which takes all of a row's labels at once. A reserved label gets the `graph_` prefix, repeated while the result is already a name in the row, so a column really aliased `graph_clinical_features` keeps its own name and value. Test: `test_renamed_column_never_collides_with_a_real_alias` (four reserved names). Mutation (collision loop disabled): 8 failed, 110 passed. Restored.
- A-32-02 and J-32-02: `_shape_entity` now shapes a vertex or edge property key through the same helper. It is a different function from `_shape_derived_value` but the same job (where a Layer 1 field name is born), so one helper serves both. Test: `test_vertex_property_with_a_reserved_name_is_renamed_and_keeps_its_value` (four names, with a colliding `graph_` property). Mutation (properties copied as before): 4 failed, 114 passed. Restored.
- Tests: `test_cypher_provenance.py` 118 passed; `tests/system_03_search_agent/tools` 1672 passed, 99 skipped. ruff and isort clean on changed files.

Stays open: A-32-03 (the renamed field still contains the words "clinical features" and the Synth model could describe it as MedGen's list; model behaviour, not probed, no live calls).
