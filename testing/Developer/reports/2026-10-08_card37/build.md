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

## Fix round

Base: bcdfee5ea3ca97c418fd6c4f1e34ed44b94b7e6d.

- A-37-01 and J-37-01: `_layer3_base_citation` now narrows the raw LitVar2 output to the match whose `source_url` is the cited finding's, so the hedged or asserted label comes from the cited record. Test: `test_citation_label_comes_from_the_cited_record_not_the_first_match` (both orders). Mutation (narrowing disabled): 1 failed, 8 passed. Restored.
- A-37-02: `_RSID_PATTERN` is now case-insensitive; the dbSNP CURIE built from it is lowercased. Test: `test_rsid_in_capitals_is_found_in_the_question`. Mutation (IGNORECASE removed): 1 failed, 8 passed. Restored.
- J-37-02: M6 (re.match for fullmatch) is now red through `test_query_that_starts_with_an_rsid_but_is_not_a_bare_one_is_not_filtered` (1 failed, 8 passed). M5 (match side not casefolded) is now red through `test_uppercase_rsid_in_a_match_is_kept_for_a_lowercase_query`, which builds the match with its own `source_url` (1 failed, 8 passed).
- Tests: new file 9 passed; `tests/system_03_search_agent/core` 1394 passed, 56 skipped. ruff and isort clean on changed files.

Stays open: A-37-03 (leading zero or merged rs id compared as strings) and A-37-04 (filter runs after the tool's 10-match cap), both unsure and needing live LitVar2 behaviour.
