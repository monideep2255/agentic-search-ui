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

## Fix round

Base: a6d67d3cd66961fb2ad4c6839417d00ed7a0d54a.

- J-36-01, A-36-01, A-36-02 (owner decision, DECISIONS.md 2026-10-08): the note now reads "the date range in your question could not be applied, so papers from any year were searched" and also shows for typed text that ends like one of the product's own options. `is_recent_window_option` is unchanged and still matches only the fixed option strings. Tests: the existing lost-offer test and `test_typed_text_ending_like_an_option_gets_the_same_note` (a topic question and a gene question). Mutation (old wording): 4 failed, 84 passed. Restored. Test queries document, query 108, wording updated.
- J-36-02: both narrative sites add the note only when a planned call has the `pubmed_search` purpose. Test: `test_no_note_when_no_paper_search_was_planned` (a CURIE in the question, no PubMed search planned). Mutation (gene path gate removed): 1 failed, 87 passed. Restored. The topic path gate cannot be shown red: a topic plan always contains a `pubmed_search` call, so that gate is an equivalent mutant (88 passed); it is kept as a guard.
- The applied-window sentence on the gene path keeps its old condition (not in this round's scope).
- Tests: `test_bare_topic_clarification.py` and `test_clarify.py` 88 passed; `tests/system_03_search_agent/core` 1392 passed, 56 skipped. ruff and isort clean on changed files.

Stays open: A-36-03 (the note is in the plan line only, not in the answer or the writing model's input; major, unsure). Also A-36-04 (a second offer in a session drops the first offer's windows) and A-36-05 (organism and fallback plan paths carry no note) are not fixed.
