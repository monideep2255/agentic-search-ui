# Card 94 group A: Plain language isolate table (w2-isolate-table)

## Change

- Owner decision D11 (2026-10-05): when every listed record is a Pathogen Detection isolate, Plain language now shows the same "Isolates and their AMR genes" table as Researcher. Every other record type keeps the titles-only Plain listing (rule 12.9).
- Keyed on the records' own type (`ISOLATE_ENTITY_TYPE`, now a named constant in `answer_layout.py`), never on the question.
- A Collected cell for an isolate with no collection date now reads "Not recorded". The column is still left out when no row has a date (existing behaviour). Query 33 expects a "where and when it was collected" column, so the table shape stays.
- Files: `src/system_03_search_agent/core/graph.py` (`listing`), `src/system_03_search_agent/synthesis/answer_layout.py`.

## Tests (`tests/system_03_search_agent/core/test_write_answer_structure.py`)

- `test_card94_plain_language_isolates_show_the_genes_table`: fails on the old code (no table), passes now.
- `test_card94_plain_language_other_records_stay_titles_only`: guards the unchanged path; passes on both, as intended.

## Gates

- Gate 2 and gate 3 green. Gate 4: 6530 passed, 6 failed. All 6 fail on a refused connection to a local Postgres on port 5432 (3 in adapters/graphql/test_no_cost_channel, 3 in core/test_think_retry), an environment gap outside this change.

## Not covered

- No live run, no frontend change or test (tokens already carry `table_row`; the Researcher screen renders them). Place column (A2) and accession beside strain (A3) not built; only D11 and the blank date.
