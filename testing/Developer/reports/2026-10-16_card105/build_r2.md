# Card 105 re-attempt build report

Branch `fix/card105-window-r2` in `<worktrees>/card105r`, develop `655e9dfe` plus the closed branch merged (`4e073a38`). One commit on top.

## What changed for the person

- A window that finds no papers now names the gene that was searched. "Recent papers on rs80357906 in BRCA1" says "for BRCA1", and a typed PMID no longer becomes the subject (V-105-01).
- The sentence "Papers in the knowledge graph carry no publication date, so they are not listed here." shows only when graph paper rows were actually removed from that answer (V-105-02).

## Diff by file

- `core/graph.py`: `_window_no_papers_line` takes the gene CURIE from `_first_gene_curie` over the graph call's targets, matches Think's resolved text for that CURIE, falls back to the follow-up's symbol. `_CallOutcome` gains `undated_articles_dropped`, set in `_execute_planned_call` when `_without_article_rows` really removed a row. Act records it in `layer3_raw_outputs` under the key `<call_id>:undated-articles-dropped` (state.py is outside the fence; no citation lookup uses that key, and the only iteration over the dict checks the type first). The line adds the second sentence only when that key is set.
- `test_window_graph_papers.py`: `_line_state` takes targets, entities and a dropped switch; five new tests.

## Tests and red under mutation

| Test | Mutation | Result |
|---|---|---|
| rs id typed before the gene | lookup back to any resolved target | red |
| PMID typed before the gene | same | red |
| plain gene case | guards the common path; passes before and after | green both |
| second sentence both ways | sentence always added | red |
| Act records only when rows removed | flag always true | red |

Each file was restored after its mutation (diff checked).

## Commands

- Before and after: the card's two files plus the 16 other files under `tests/system_03_search_agent/core/` naming the listed symbols (18 files with the two): 681 passed before, 686 passed after.
- `ruff check` (no path): all checks passed. `isort --check-only --diff src tests services tracker alembic .claude .github`: exit 0.
- `ruff format --check` on graph.py already reports pre-existing differences on develop; not part of CI, not touched.

## Unsure or noticed

- V-105-03 (disease-anchored questions reach the flag) is untouched by design.
- The end-to-end tests in `test_bare_topic_clarification.py` pass unchanged; no new end-to-end test was added, the new cases are unit level.
