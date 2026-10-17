# Card 105 build report: a picked window leaves undated graph papers out

Branch `fix/card105-window-leaves-undated-papers-out`, from develop `78c68c1c`. Built from `diagnosis.md` in this folder, parts 1 and 2. Part 3 is built in a second commit.

## Table of contents

- [What changed, in the person's words](#what-changed-in-the-persons-words)
- [Diff summary](#diff-summary)
- [Tests](#tests)
- [Mutation checks](#mutation-checks)
- [Commands run](#commands-run)
- [Part 3](#part-3)
- [Unsure about, and seen outside the ticket](#unsure-about-and-seen-outside-the-ticket)
- [Fix round](#fix-round)

## What changed, in the person's words

- When I pick a "How far back" window on a gene question, the papers I am shown are only from that window. The knowledge graph's paper links (no publication date) are left out.
- The recent papers lead the answer and the count line counts them ("Found 1 pubmed record and 1 gene record for BRCA1"), with no "of 3487 available" note.
- A question with no picked window, including the same words typed, runs the code it ran before.
- The paper cap of 5 is unchanged.

## Diff summary

All in `src/system_03_search_agent/core/graph.py`:

| Where | Change |
|---|---|
| `_PlannedToolCall` | New field `undated_papers_left_out: bool = False` |
| `plan_node`, gene path | `dataclasses.replace(planned, undated_papers_left_out=True)` on the question's own graph call, only when `publication_window is not None` (the value of `_picked_publication_window(query)`) |
| New `_without_article_rows` | Removes `Article` rows; recomputes `row_count` and `total_available` from the rows kept; `truncated=False`; a result that was only Article rows becomes `empty` instead of `ok` with no rows |
| `_execute_planned_call`, cypher branch | When the flag is set, calls `_without_article_rows(output)` before `_split_rows_by_trust`, so both the structured pair and the quarantine pair see the kept rows |
| `_answer_call_ids` | When any planned graph call carries the flag, the `pubmed_abstracts` follow-up whose source is `pubmed_search` also answers |

Not touched: `_sanitized_citeable_row`, `_rows_for_citation`, `_UNTRUSTED_FREE_TEXT_NODE_TYPES`, the paper cap, any file outside the fence.

## Tests

| Test | File | Proves | Fails on develop |
|---|---|---|---|
| `test_a_picked_window_leaves_the_graph_s_undated_papers_out` | `test_bare_topic_clarification.py` | Real graph, picked window: no 1999 PMID in citations or tokens, the 2024 paper is cited, no "of 3487", count line counts the PubMed record, trust outcome is not refuse | Yes (see mutation 1) |
| `test_an_unpicked_window_keeps_the_graph_s_papers` | same | Control: same words typed with no offer keep the graph papers | Passes on develop too (byte identity guard) |
| `test_a_picked_window_with_no_papers_in_it_lists_no_older_papers` | same | Window finds nothing: no older paper listed, answer still ships on the gene record | Yes |
| `test_undated_papers_left_out_drops_only_article_rows` | `test_window_graph_papers.py` | Flag on: only the Gene row kept, counts equal 1, no quarantine pair; flag off: identical to today | Yes (field missing) |
| `test_a_result_of_only_articles_becomes_empty_not_ok` | same | All-Article result becomes `empty` | Yes |
| `test_the_flag_defaults_to_false` | same | Default is False | Yes |
| `test_the_windowed_abstracts_call_answers_only_when_the_flag_is_set` | same | `_answer_call_ids` adds the abstracts call only with the flag | Yes |

## Mutation checks

| Mutation | Result |
|---|---|
| Drop the flag check in Act (`if False:`) | 4 tests red, including `test_a_picked_window_leaves_the_graph_s_undated_papers_out` and `test_undated_papers_left_out_drops_only_article_rows`; restored |
| Set the flag unconditionally in Plan (`if True:`) | `test_an_unpicked_window_keeps_the_graph_s_papers` red; restored |

## Commands run

- Targeted run of the two test files plus the 13 neighbouring files under `tests/system_03_search_agent/core/` that reference the four names: see the result line in the hand-back.
- `ruff check` and `isort --check-only` run as CI runs them: clean (see Part 3).
- `ruff format` on the new test file: applied. `ruff format --check` and `isort --check-only` on `core/graph.py` and on `test_bare_topic_clarification.py` fail the same way on develop `78c68c1c` (checked against the committed copies), so I did not reformat those two files.

## Part 3

Built in a second commit after the lead widened the fence to the write path's existing note mechanism, inside `core/graph.py` only.

- New `_window_no_papers_note(state, query)`, added to the `notes` tuple in `write_node` beside the other notes (so it rides the existing trailing `note` token). `_answer_parts` and `contracts/events.py` are untouched.
- It speaks only when a planned graph call carries the flag, a window was picked, and every windowed `pubmed_search` ended without error and with no ids.
- Words: "No PubMed papers from the last 5 years were found for BRCA1. Papers in the knowledge graph carry no publication date, so they are not listed here." The window's own label and the follow-up's gene symbol are used; the symbol is dropped if none is known.
- Tests: `test_a_picked_window_with_no_papers_in_it_says_so` (line present, under 200 characters, no graph paper cited), `test_a_picked_window_with_papers_in_it_carries_no_such_line`, and the unpicked control now also asserts no such line.
- Mutation: removing the "search returned ids" condition turns the with-papers control red; restored.
- Gates run exactly as CI does, from the worktree root: `ruff check` (all passed) and `isort --check-only --diff src tests services tracker alembic .claude .github` (clean).
- Neighbour run after the change: 587 passed.

## Unsure about, and seen outside the ticket

- A windowed gene question whose graph answer was only Article rows now has an `empty` graph call. With PubMed papers present the answer still ships (tested); with none it ships on the Gene row (tested).
- The Gene row still counts in the count line next to the PubMed record ("Found 1 pubmed record and 1 gene record"). That is existing behaviour for non-paper graph rows.
- The test stubs the code-chosen GO context call (`template` keyword) as empty so only the question's own call returns Article rows.

## Fix round

Third commit, from `adversary.md` (FIX FIRST) and `judge.md` (PASS). Fence kept: `core/graph.py` and the card's two test files.

| Finding | Fix | Test | Mutation that turns it red |
|---|---|---|---|
| A-105-01 | The flag is set after the plan is built, only when it holds a windowed `pubmed_search`. A gene typed as a CURIE plans no search, so its graph call runs as on develop | `test_a_picked_window_on_a_gene_typed_as_a_curie_keeps_the_graph_papers` | Set the flag whenever a window is picked |
| A-105-02 | The refusal's existing `none_linked` text slot now takes the empty-window line plus "Pick a longer window, or ask without one." (`_window_no_papers_refusal`). A failed search still outranks it. No new event field | `test_a_refusal_the_left_out_papers_caused_says_what_happened_and_what_to_type`, graph stub returns Article rows only, as the real template does | Drop the refusal slot argument |
| A-105-03 | The line takes the gene's text from Think's resolved entity for the graph call's CURIE, the form the count line uses, and falls back to the search symbol | `test_the_line_writes_the_symbol_as_the_count_line_does`, `test_the_line_falls_back_to_the_search_symbol_when_nothing_resolved` | Skip the resolved-entity lookup |
| A-105-04, J-105-02 | Test only | `test_a_failed_windowed_search_never_says_no_papers_were_found` | Remove the `status == "error"` guard |
| J-105-03 | Test only | `test_the_line_needs_the_flag` | Replace the flag lookup with any graph call |

Each mutation was applied alone, turned exactly the named test red, and was restored.

Runs: the two card files plus the 13 neighbouring files, 593 passed. `ruff check` (no path) and `isort --check-only --diff src tests services tracker alembic .claude .github`: clean.
