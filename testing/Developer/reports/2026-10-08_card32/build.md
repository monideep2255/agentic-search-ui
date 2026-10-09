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
