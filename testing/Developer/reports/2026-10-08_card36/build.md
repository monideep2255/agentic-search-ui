# Card 36 build: a lost "How far back" window is named in the plan

## Base

- c916cfa30f59802dfd85c81ef7ba39bdcfc2b263 (origin/develop), branch fix/card36-window-not-applied.

## What changed

- `src/system_03_search_agent/core/clarify.py`: new `is_recent_window_option(text)`. True only when the text is some ask, then " from ", then one of the fixed `RECENT_WINDOW_PHRASES`, then "?". It reads no free text and never yields a window.
- `src/system_03_search_agent/core/graph.py`, `plan_node` only: `window_lost` is true when no window was picked and the question has the fixed option shape. Both narrative sites (the literature path and the gene or disease path) then add "the date range you chose could not be applied, so papers from any year were searched". The window is not re-applied.
- Tests: one unit test in `test_clarify.py`; three in `test_bare_topic_clarification.py` (lost offer on a topic and on a gene, parametrized; an applied window carries no note).
- `testing/Test_queries_and_workflows.md`: new query 108, after query 84.

## Tests

- `test_clarify.py` and `test_bare_topic_clarification.py`: 85 passed.
- `tests/system_03_search_agent/core`: 1389 passed, 56 skipped.
- ruff check: all checks passed. isort --check-only: clean on the three other files; `core/graph.py` is reported unsorted, and it is also reported on the base file (pre-existing, not changed).

## Mutation check

- Site 2 disabled (`elif False and ...`): 1 failed (the BRCA1 case). Restored.
- Site 1 disabled (`if False:`): 1 failed (the statins case). Restored; 85 passed.

## Deviations

- The same exact words typed with no offer at all (never clicked) also get the note, since the helper verifies the fixed shape, not that an offer existed. The search is unchanged and the note is true there too (no range was applied).
- Query number 108 taken.

## Learnings

- None.
