# Card 30 step 1 build: unclassified variants say so

Branch `fix/card30-unclassified-variants-say-so`, from develop `78c68c1c`. Step 2 is not built.

## Table of contents

- [What changed for the person](#what-changed-for-the-person)
- [Diff summary](#diff-summary)
- [Tests](#tests)
- [Commands run](#commands-run)
- [Unsure or outside the ticket](#unsure-or-outside-the-ticket)
- [Fix round](#fix-round)

## What changed for the person

- Under a list of a gene's variants from the knowledge graph, the Notes list carries one line: "ClinVar's classification of these variants (for example pathogenic, benign or uncertain) was not retrieved, so this list does not say which are pathogenic. Each variant's ClinVar record shows its classification."
- When the classifier reads the question as asking about classification (pathogenic, benign, clinically significant), the answer's verdict is "ask", never "answer".
- Beside the variant to disease table (card 23) only card 23's line shows. An answer that cites a classification field (rs334, dbSNP) gets neither line nor floor. Nothing else changes.

## Diff summary

| File | Change |
|---|---|
| `src/system_03_search_agent/synthesis/answer_layout.py` | `VARIANT_CLASSIFICATION_NOTE`, `_CLASSIFICATION_FIELDS`, `variant_classification_note(findings)`: a graph `SequenceVariant` finding present and no finding on `clinical_significance` or `germline_classification`. Record type and field only |
| `src/system_03_search_agent/core/graph.py` | `_ASKS_CLASSIFICATION` spec (instructions and criteria written as rules, no question lifted); `_RunDecisions.classification_task`; `_classification_asked` and `_drop_classification_decision`; started and cancelled in `think_node` beside features; dropped in `write_node`'s `finally`; read once in `_write_answer`; floor `aggregate([trust_outcome, "ask"])` on the answer outcome only; `_answer_parts` gains `classification_note`, emitted first in the notes part, skipped when card 23's line is in the tokens it built or in `listing_tokens` |
| `testing/Test_queries_and_workflows.md` | Query 22 expected text updated; new query 115 (114 was the highest); provenance and feature table rows |

`merge_into` in `_answer_parts` is untouched.

## Tests

Nine of ten new tests fail on develop's code and all pass here (checked by reverting `src` only). The tenth, the decision still running past the grace, passes on develop too: it pins that a slow decision is never a floor.

| Test | Proves |
|---|---|
| `test_card30_a_graph_variant_list_says_classification_was_not_retrieved` (answer_layout) | selector returns the pinned line |
| `test_card30_no_line_when_a_shown_record_gives_a_classification` | rs334 shape, a classified list and an empty list return None |
| `test_card30_the_line_shows_in_both_depths_once_after_the_list` (two depths) | exactly one line, after the last row |
| `test_card30_beside_the_variant_table_only_card_23s_line_shows` | one line, card 23's |
| `test_card30_a_classification_question_over_unclassified_variants_is_ask` | verdict goes answer to ask, claim outcomes unchanged |
| `test_card30_no_floor_without_the_decision` (not applicable, failed, none) | verdict stays answer, line still shows |
| `test_card30_a_decision_still_running_past_the_grace_is_not_a_floor` | late decision is no floor |
| `test_card30_a_write_that_ends_early_stops_the_classification_decision` | task cancelled |
| `test_card30_a_searched_question_asks_about_classification_and_carries_it_on_done`, `..._small_talk_is_never_asked...` (test_bare_topic_clarification) | asked at Think, record on done, not asked for small talk |

I also added `think.asks_classification` to `_SAFE_PICKS` in `test_bare_topic_clarification.py`; without it the existing "every decision is jev" test failed.

## Commands run

- Three named files plus `test_bare_topic_clarification`, `test_write_answers_sooner`, `test_run_registry_stop_mid_write`, `test_first_sentence_gap`: 551 passed. `tests/system_03_search_agent/harness` plus `test_bare_topic_clarification`: 625 passed.
- `ruff check` on the six changed Python files: clean. `ruff format --check` and `isort --check-only` fail on `graph.py` and some others for reasons already on develop; the new lines add no format difference. I did not run the fixers, because they rewrote hundreds of unrelated lines.

## Unsure or outside the ticket

- The floor applies even where card 23's line shows (a variant table at Researcher with a classification question). The diagnosis only says the note is skipped there.
- `harness/task_tiers.py` lists decision points but nothing reads it at runtime, and `write.lead_sentence` is absent too, so I did not add a row (outside the fence).
- Query number 115 may collide with another card's entry tonight.
- The judge of "which questions ask about classification" is the classifier alone; live wording quality is unmeasured (no model calls allowed).

## Fix round

Second commit on the same branch, after the judge and adversary reviews (both PASS).

| Finding | Change |
|---|---|
| J-30-01, A-30-01 | Write now reads the features and classification decisions with one `asyncio.gather`, so both share one `_LATE_DECISION_GRACE_S`. Worst case is 1 s, as on develop. Test `test_card30_two_late_decisions_share_one_grace` hands both decisions a 30 s sleep and checks Write's added wait is between 0.3 s and 0.8 s with the grace set to 0.5 s |
| J-30-03 M1 | `test_card30_no_floor_when_the_answer_shows_a_classification`. A classified claim is already "ask" by its own trust, so the test counts the floors applied through `aggregate` instead of reading the outcome |
| J-30-03 M5, A-30-02 | `test_card30_answer_parts_skips_its_line_beside_card_23s_table`: on a request that does not read `placement`, the final `_answer_parts` call is handed the card 30 line and must leave it out beside card 23's line |
| J-30-03 M8 | `test_card30_think_ending_the_search_stops_the_classification_decision` (three early ends), calling `think_node` alone so Write's own drop cannot mask it |
| J-30-04 | Query 79's entry now says Plain language carries card 30's line in its Notes. `docs/architecture/Model_architecture.md` has a `think.asks_classification` bullet beside `think.asks_features`. `task_tiers.py` has a `think.asks_classification` row beside `think.asks_features`; `write.lead_sentence` is also missing there and nothing reads the table at runtime, so only the card 30 row was added, and `test_task_tiers.py` now expects 16 rows |

Mutation reds (each applied alone to `core/graph.py`, then restored; the tree has no stray edit):

| Mutation | Result |
|---|---|
| Sequential reads in place of the gather | the shared grace test fails |
| Floor without the `classification_note is not None` check | the no floor with a classification test fails |
| `_answer_parts` card 23 skip removed | the `_answer_parts` test fails |
| Think no longer cancels `classification_task` | the Think early end test fails |

Not changed: the note's condition, the floor's rule, the decision's description.
