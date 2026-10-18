# Card 91: aggregate class with a Gene anchor and no count request

## The change

- A question Think classes `aggregate` about a Gene, with no shape matched and no count request (`_wants_count`, the existing "how many" and "count or number of" patterns), now takes the checked Gene record template in `select_template` (`src/system_03_search_agent/tools/cypher_templates.py`). Before, it returned None, the model wrote Cypher, the validator rejected it twice and no graph search ran.
- No new word list. A count request, a Disease or Article anchor, and every shape-matched question keep their paths.
- G-034 is a Disease anchor with the genes shape ("how many genes"): not touched by this branch. Its path is unchanged.
- The failure note wording is unchanged (wave 2).

## Tests

- New case in `test_known_shapes_select_the_named_template`: the TP53 dataset question on `aggregate` selects `gene_record_one`. It failed on the old code (stash of `src`), passes now.
- The fallback case "Tell me about BRCA1" on `aggregate` moved out of the model-path list, replaced by two count requests ("How many records does BRCA1 have?", "Count the records for BRCA1") that still return None.
- `test_cypher_templates.py`: 60 passed with the change, 1 failed on the old code.

## Local runs

`select_template` called for the TP53 question with each class Think produced in the diagnosis runs (aggregate, exploratory, single_hop, single_hop, multi_hop, exploratory, aggregate): `gene_record_one` in 7 of 7.

## Gates

- gate02 import order: pass. gate03 lint: pass.
- gate04 unit suite: the first run was killed by the harness (exit 143, machine loaded). The same command run in full: 6800 passed, 4 failed. The 4 were tests that used a no-count Gene question on `aggregate` as their model-path example (3 in `test_graph.py`, 1 in `test_cypher_query_templates.py`). They now use a count request ("How many records does BRCA1 have?"), the case that still takes the model path. Those tests and the template tests pass after the edit. The full suite was not re-run end to end after the edit.

## Not covered

- No live API run: Think's class and the full answer were not driven. The lead's test query run on develop is the gate.
- The golden run was not made. Rate-limit failures (diagnosis cause B) are untouched.
