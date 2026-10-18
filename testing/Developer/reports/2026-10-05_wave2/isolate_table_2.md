# Card 94 follow-up: isolate table beside an organism record (isolate-table-2)

## Change

- #165 showed the Plain language isolate table only when every listed record was an isolate. Query 33 lists 20 isolates and 1 organism (Taxonomy) record, so it fell back to names only.
- Now `listing` in Plain language splits the records by their own type (`ISOLATE_ENTITY_TYPE`, never the question): isolates take the "Isolates and their AMR genes" table, every other record keeps the titles-only Plain list in its own group after the table. Answers with no isolates are unchanged. Researcher mode is unchanged.
- File: `src/system_03_search_agent/core/graph.py` (`listing`, split into `listing` and `grouped_listing`). `answer_layout.py` needed no change.

## Tests (`tests/system_03_search_agent/core/test_write_answer_structure.py`)

- `test_card94_plain_language_isolates_with_an_organism_keep_the_table`: two isolates plus one organism record gives the table with genes and one separate titles-only organism item with its citation. Failed on develop's code (ran with the old `graph.py` restored), passes now.
- The existing non-isolate Plain test still passes, unchanged.

## Gates

- Gate 2 and gate 3 green. Gate 4: 6540 passed, 6 failed, all on a refused connection to the local Postgres (port 5432), an environment gap that fails on any branch.

## Not covered

- No live run. The lead's query 33 run on develop is the gate. Ordering inside a mixed answer: the table first, then the organism group.
