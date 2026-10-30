# Card 149 build: cite only the resolved gene's own PubTator3 record

Builder report, 2026-10-30, branch `fix/card149-human-gene-record-only`. Built from `testing/Developer/reports/2026-10-30_card149/diagnosis.md`. No model call and no network call.

## Table of contents

- [What changed](#what-changed)
- [Tests and results](#tests-and-results)
- [Notes](#notes)

## What changed

All source changes are in `src/system_03_search_agent/core/graph.py`.

| Part | Change |
|---|---|
| Plan | `_PlannedLayerToolCall` gains `expected_gene_id` (default empty). `_layer_call` and `_build_layer_tool_calls` take it; it is set on the `pubtator_annotate` call only when the call is searched by the gene symbol. |
| Call site | Think's resolved `NCBIGene:<n>` gives the numeric id, passed to the planner. A non-numeric id gives an empty value. |
| Shaping | `_layer_tool_output_to_structured_fields` takes `expected_gene_id`. When set, only `db == "ncbi_gene"` entities whose `db_id` equals it are kept. When empty, the old name rule runs unchanged. |
| Act | The Act call site passes `planned.expected_gene_id` to the shaper. |

In the person's words: a question about a human gene no longer cites a rat, mouse or dog gene record, or a different gene's record, as the gene they asked about. The human record stays cited, and disease questions and unresolved-gene questions behave as before. No list of symbols or species is used.

## Tests and results

New tests in `tests/system_03_search_agent/core/test_layer_handoff.py`:

- Rat `Gck` (24385) is dropped for resolved GCK (2645), status `empty`; with no resolved gene it is kept as before.
- Human `TP53` (7157) is kept for 7157; GCKR (2646) is dropped for GCK; a MeSH entity with the same id is dropped.
- The plan sets `expected_gene_id` "2645" on the gene call, and nothing on a disease call or when no symbol is used.

Results:

| Check | Result |
|---|---|
| `test_layer_handoff.py` | 31 passed |
| Mutation (id comparison replaced by `True`) | 2 new tests red, 29 passed, then restored and 31 passed |
| `test_layer_handoff.py`, `test_pubtator_act_cap.py`, `test_graph.py` | 287 passed |
| `ruff check .` | All checks passed |
| isort per gate02 | clean |

## Notes

- When a gene was resolved and PubTator3 holds no entity with that id, the call reports `empty`, the same state as an unknown symbol.
- The existing frog test (no expected id) passes unchanged.
