# Card 37 build: rs334 lists only its own records

## Base

- c916cfa30f59802dfd85c81ef7ba39bdcfc2b263 (origin/develop), branch fix/card37-rs-id-exact.

## What changed

- `src/system_03_search_agent/core/graph.py`: the `litvar2_lookup` branch of `_layer_tool_output_to_structured_fields` only. When the call's query is a bare rs id, a match is kept only when its rsid equals the query, compared case-insensitively. Any other query (HGVS, a name) is unfiltered. If no match is exact, `_shaped` gives status `empty`, not `error`.
- New `tests/system_03_search_agent/core/test_litvar2_exact_rsid.py`, five tests.
- `testing/Test_queries_and_workflows.md`: one line added to query 23, "What you should see". No new query number taken.

## Tests

- New file: 5 passed.
- `test_graph.py` and `test_layer_handoff.py`: 266 passed.
- `tests/system_03_search_agent/core`: 1390 passed, 56 skipped.

## Mutation check

- Replaced the exact comparison with a prefix comparison (the old behaviour): 3 failed, 2 passed. Restored; 5 passed.

## Deviations

- Only step 1 of the diagnosis (T-8.9-04) built. Steps 2 and 3 are not part of this card.

## Learnings

- None.
