# Card 94t build: a timed-out Pathogen Detection search no longer loses the answer

Base: bce08af9, branch fix/card94-timeout-no-crash.

## Change (src/system_03_search_agent/core/graph.py only)

Taken from the closed branch's step 3 only:

- `_layer_tool_output_to_structured_fields`: the tool's status "timeout" is shaped as "error".
- `_execute_planned_call`: that outcome carries failure kind `timed_out`.

No lookup, no organism mapping, no bound change, no schema field. No new wording: the existing failed-search path (`failed_searches`, Write's unfinished-search note, "timed out" from `_FAILURE_KIND_WORDS`) shows the person the note.

## Test

tests/system_03_search_agent/core/test_pathogen_timeout_no_crash.py: for each mode (isolate_search, isolate_lookup, cluster_snp_neighbors) the tool returns "timeout" beside a good graph result. Act completes, the graph finding stands, and `failed_searches` is exactly pathogen_detection with kind `timed_out`.

Mutation (one property): the `timeout` to `error` mapping disabled. Red: 3 failed (pydantic literal_error ValidationError at graph.py, the develop crash). Restored: 3 passed.

## Live (core/run.py run_streaming, reads_placement=True, deepseek/deepseek-v4-flash for guard and plan, z-ai/glm-5.2 for synth, cap 0.25)

| Query | Elapsed | Citations | Outcome | Errors |
|---|---|---|---|---|
| 33 (E. coli ESBL) | 18.9 s | 41 | answer, 20 isolates, count line and blaCTX-M note shown | none |
| 42 (SAMN02147118) | 6.9 s | 3 | answer | none |

Query 33 and 42 each ran twice (one extra run to read the output); the second query 33 run was not printed in full. Session memory and capture log errors in the script are from the script passing no caller identity, not from this change.

## Gates

- ruff check: all checks passed.
- isort gate 2: clean.
- pytest core and tools, not integration: 3204 passed, 132 skipped, 24 deselected.
