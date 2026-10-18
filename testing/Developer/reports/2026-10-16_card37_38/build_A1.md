# Build report: card 37, slice A1

Branch `fix/card37-rs334-named-by-its-id`, from develop `78c68c1c`.

## What changed in the person's words

- rs334's record is called rs334, never by the significance list.
- In Researcher its row shows four cells: Variant (rs334), Identifier (rs334), Gene (HBB), Clinical significance (the values dbSNP lists).
- In Plain language it reads "Genetic variant (HBB)".
- Every other record type reads as on develop. The writer's input and the trust verdict do not change.

## Diff by file

- `src/system_03_search_agent/synthesis/answer_layout.py`
  - `TABLE_COLUMNS`: one entry, `"Variant record": ("genes", "Variant", "Gene")`.
  - New closed tables keyed by the exact row type: `_ROW_TYPE_COLUMNS`, `_ROW_TYPE_LABEL_FIELDS`, `_ROW_TYPE_PLAIN_SUFFIXES`, and helper `_row_type_label`.
  - `record_label`: reads `rsid` for `Variant record` (after the resolved name check, before the name fields).
  - `record_status_or_year`: `("Variant record", "clinical_significance")` gives the "Clinical significance" column.
  - `plain_record_label`: `Variant record` with an rs id reads "Genetic variant (genes)", or "Genetic variant" with no gene.
  - `core/graph.py`, `findings.py`, `trust.py` untouched; `variant_to_disease_source_note` untouched (it returns None for this type).
- `tests/system_03_search_agent/synthesis/test_variant_record_label.py` (new, 13 tests).
- `testing/Test_queries_and_workflows.md`: the diagnosis's line added to query 23.

## Tests

- Guard: `build_synth_findings` on the rs334 row still yields `clinical_significance` first; `risk_tier_for` high; field order unchanged. Passes on develop too, by design.
- Label, table cells (exactly four), Plain language label, no-rs-id and no-gene fallbacks: fail on develop, pass here.
- PubTator3 `Publication`, Layer 2 `gene` with `organism`, LitVar2 `Literature variant` with `gene`: label, column, plain label unchanged. Pass on develop and here.
- Whole page through `write_node`: Researcher header and row, writer prompt has no HBB, Plain language item, opening sentence pinned as "Found 1 variant record record: rs334 [1]." (the doubled noun is card 121, not fixed).
- On develop's `answer_layout.py`: 7 failed, 6 passed. With the change: 13 passed.

## Commands

- Test files above plus `test_answer_layout.py`, `test_answer_quality.py`, `core/test_write_answer_structure.py`: 216 passed. `core/test_graph.py`: 244 passed.
- `ruff check`: clean. `isort --check-only`: clean.
- `ruff format --check` on `answer_layout.py` reports differences, all on lines I did not touch (develop already fails it); my new test file is formatted.

## Notes

- The opening sentence in the test fixture has no subject, so it reads "Found 1 variant record record: rs334 [1]." Live it reads "... for rs334: rs334 [1]." (redundant, as the diagnosis predicted).
- Plain language also reads "Genetic variant" without a gene, never the rs id.

## Fix round

From `verifier_A1.md`, per the lead's decision of 2026-10-16.

- V-37-01: a dbSNP row whose significance list is withheld shows its `functional_consequence` in a "Consequence" column (read only when the significance is absent). The rs6025 shape: `rs6025, rs6025, F5, coding_sequence_variant, missense_variant`.
- V-37-02: Plain language keeps dbSNP's values after the gene: "Genetic variant (HBB), clinical significance: ...", or "..., consequence: ..." when there is no significance. Clipped to the 500 label limit.
- V-37-03: both are clipped at a term boundary with an ellipsis (`_clip_terms`), never mid-term. The column now allows 500 characters, develop's label limit.
- V-37-04: the guard test builds its row by calling the real `ncbi_dbsnp` branch of `_layer_tool_output_to_structured_fields`.
- V-37-05: a test for the label's URL check.

Mutations, each restored after (`git diff` showed only the intended change):

| Mutation | Result |
|---|---|
| Drop the Consequence column entry | 2 failed |
| Plain details loop emptied | 5 failed |
| `_clip_terms` hard cut | 1 failed |
| Drop the URL check | 1 failed |
| Real builder puts `rsid` first (probe copy of `src`, run with `-o pythonpath`) | guard test failed |

Commands: slice tests, `test_answer_layout.py`, `test_answer_quality.py`, `core/test_write_answer_structure.py`, `core/test_layer_handoff.py`: 250 passed. `ruff check` (no path) clean; `isort --check-only --diff src tests services tracker alembic .claude .github` clean.

Known edge: a table mixing dbSNP rows with and without a significance takes its column heading from the first row, so a consequence in a later row sits under "Clinical significance". Not seen live.

### Fix round, third commit: the mixed table

The edge noted above was worse than a wrong heading: `grouped_listing` in `core/graph.py` took the extra column's heading from the first row, and a later row with a different label got an empty cell, so its value was dropped. The lead widened the fence to that block for `Variant record` groups.

- `answer_layout.name_mixed_variant_extras`: when a group holds both "Clinical significance" and "Consequence" rows, every row goes under "Clinical significance or consequence" and each cell says "significance: ..." or "consequence: ...". Other types and single-kind groups are returned unchanged.
- `core/graph.py`: one call after `extras` is built, plus its import. The first-label rule is untouched.
- Tests: mixed table (heading, both cells, four cells), the two pure tables, a clinical trial group unchanged. Mutation: removing the call in `grouped_listing` turns the mixed test red (1 failed, 22 passed); restored.
- 23 tests in the slice file; the five-file run and lint gates are clean.
