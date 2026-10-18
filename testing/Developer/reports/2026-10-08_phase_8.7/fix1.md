# Phase 8.7 fix round, fix agent 1: the gap clause

Base: 47ab8725245a8e0e4c7155ae3a61ed0c76c56a98 (branch feat/8.7-fix1, cut from phase/8.7-answers-sooner). One fix round; there is no second.

Findings owned here: F-8.7-J01, F-8.7-J02, F-8.7-A02, F-8.7-A03, F-8.7-A13, all about the gap clause of the opening line (`synthesis/answer_layout.py`: `AskedField`, `records_lack_field`, `_gap_clause`, the `finish` wrapper; `core/graph.py`: `_asked_field` and the one line that passes it into the summary).

## Table of contents

- [The rule and the result](#the-rule-and-the-result)
- [What changed](#what-changed)
- [Each finding](#each-finding)
- [Mutation results](#mutation-results)
- [Test runs](#test-runs)
- [What stays open](#what-stays-open)

## The rule and the result

From the user's chair: a confident wrong absence is worse than saying nothing. The clause may say a record does not give a field only when the product positively knows it. The clause stays, rebuilt so it holds by construction, from the state of the field's source and never from wording. It is said only when all four hold:

| Condition | How code knows it |
|---|---|
| Every search of the question finished | `AskedField.every_search_finished`, set by the loop from `failed_searches` being empty |
| The field's source read every counted record and found none | Each counted record has its own code-built "MedGen lists no clinical features for ..." statement on the same record page (`source_page_key`); only `_with_medgen_clinical_feature_rows` writes it, and only for a record fetched and read |
| No finding shown in the answer carries anything that might state the field | Every finding's field is an identity field (name, title, symbol, preferred name, CURIE, semantic type), one of the source's quiet fields, or the "lists none" statement itself |
| No shown record's row carries anything that might state it | The same test over every field of every shown finding's row, which the listing can show |

Anything short of that gives no clause, and the count line is exactly what develop's would be. A definition, summary, abstract, description or list of linked conditions holds the clause back, because code cannot read prose for a feature.

`AskedField` has no defaults, so a caller cannot leave the source state unsaid and get the clause by accident.

A consequence the lead should know: a MedGen record that carries a definition never gets the clause, since its definition may describe the features. The clause therefore fires only for MedGen disease records read with no features and no definition, alone or beside other records that carry only identity fields.

## What changed

- `src/system_03_search_agent/synthesis/answer_layout.py`:
  - `AskedField` gains `source`, `lists_none_prefix`, `quiet_fields` and `every_search_finished`, none with a default.
  - New `_IDENTITY_FIELDS`, the closed set of fields that name or classify a record.
  - `records_lack_field` is rewritten to the four conditions above.
  - `_gap_clause` is reworded to name the source's record (F-8.7-A13).
  - The `answer_summary_sentence` docstring and the `finish` comment now say the clause needs known absence.
  - The now unused `is_no_clinical_features_finding` import is removed.
- `src/system_03_search_agent/core/graph.py`:
  - `_asked_field(clinical_features_asked, failed_searches)` builds the full `AskedField`: source "MedGen", the "lists none" prefix, the feature rows' quiet fields (total, disease title, HPO id) and `every_search_finished=not failed_searches`.
  - The one call line now passes `state.get("failed_searches", [])`. No other function in the file was touched.
- `tests/system_03_search_agent/synthesis/test_first_sentence_gap.py` is rewritten: 15 arms.
- `tests/system_03_search_agent/core/test_write_answers_sooner.py`, the gap arms only:
  - The arm that expected ", none of which gives clinical features." on five graph rows never read for features now expects the line unchanged (F-8.7-J02).
  - Three arms are new, each over a MedGen record built by the real row builder (`_ncbi_efetch_output_to_structured_fields`) and run through `write_node`: the positive case at both depths, a timed-out MedGen search, and a definition on the record.
- `testing/Test_queries_and_workflows.md` is unchanged. Neither query 2 nor query 72 describes the clause, and neither question can now get it: query 2 is not a features question, and Marfan syndrome's MedGen record lists features. The lead-sentence amendment the plan's owner decision 2 asks for is not this round's.

## Each finding

Every new arm below was checked against the base commit's `answer_layout.py`, extracted with `git show` to a scratch path and run on the same inputs. Base output for each, pasted:

- J01 row: `Found 1 disease record for Marfan syndrome: Marfan syndrome [1], which does not give clinical features.`
- J02 never read: `Found 1 disease record for Marfan syndrome: Marfan syndrome [1], which does not give clinical features.`
- A03 counted gene: `Found 1 disease record and 1 gene record for Marfan syndrome: Marfan syndrome [1] and NCBIGene:2200 [5], none of which gives clinical features.`
- A13 plain: `I found 1 genetic variant on this topic [1], linked to 3 conditions, which does not give clinical features.`

So each arm fails on the old code.

| Finding | What changed | Its tests | Status |
|---|---|---|---|
| F-8.7-J01, a definition describes the features | Any non-identity field with a value, on any shown finding or row, holds the clause back | `test_j01_a_definition_on_the_record_row_keeps_the_clause_unsaid`, `test_j01_a_definition_finding_keeps_the_clause_unsaid`, `test_j01_an_abstract_shown_beside_the_record_keeps_the_clause_unsaid`; loop level `test_a_definition_on_the_record_keeps_the_count_line_unchanged` | Fixed |
| F-8.7-J02, features never read | Each counted record needs its own "lists none" statement, the only proof the source read it | `test_j02_a_record_whose_features_were_never_read_gets_no_clause`, `test_j02_every_counted_record_needs_its_own_lists_none_statement`; loop level `test_records_whose_features_were_never_read_leave_the_count_line_unchanged` | Fixed |
| F-8.7-A02, the MedGen search did not finish | `every_search_finished` from `failed_searches`, passed by the loop | `test_a02_a_search_that_did_not_finish_means_no_clause`, `test_the_loop_says_every_search_finished_only_when_none_failed`; loop level `test_a_search_that_did_not_finish_keeps_the_count_line_unchanged` | Fixed |
| F-8.7-A03, a record row beside it gives the features | The row test covers every shown record, counted or not; a counted gene also has no "lists none" statement | `test_a03_a_counted_gene_row_whose_description_gives_them_keeps_the_clause_unsaid`, `test_a03_a_shown_record_that_is_not_counted_still_counts` | Fixed |
| F-8.7-A13, Plain language reads as "these conditions have no symptoms" | Two parts, below | `test_a13_a_variant_linked_to_conditions_gets_no_clause_in_either_depth`, `test_a13_the_plain_language_clause_says_it_is_the_record_that_lists_none`; loop level `test_a_record_read_and_listing_none_is_said_to_in_both_depths` | Fixed |

F-8.7-A13 is fixed in two parts:

- By construction, the clause can no longer follow "linked to N conditions". A record carrying a fold has a linked-conditions field, which is not an identity field, and it has no MedGen "lists none" statement of its own.
- The wording names the record in both depths, so the clause stays in Plain language:
  - One record: ", and its MedGen record lists no clinical features".
  - Several: ", and none of their MedGen records lists clinical features".

The words "which does not give" and "none of which gives" are gone.

The new lines, from the loop-level arm:

- Researcher: `Found 1 medgen record: Malignant tumor of breast [1], and its MedGen record lists no clinical features.`
- Plain language: `I found 1 condition on this topic [1], and its MedGen record lists no clinical features.`

## Mutation results

Each property was broken alone, the two touched test files run, and the source restored and confirmed byte for byte with `cmp` against a saved copy.

| Mutation | Result |
|---|---|
| M1: `every_search_finished=True` in `_asked_field` | 2 failed, 49 passed (`test_a02_...`, `test_a_search_that_did_not_finish_...`) |
| M2: the per-record "lists none" requirement removed | 3 failed, 48 passed (both `test_j02_...` arms, `test_records_whose_features_were_never_read_...`) |
| M3: every field treated as quiet | 5 failed, 46 passed (three `test_j01_...` arms, `test_a03_a_shown_record_that_is_not_counted_still_counts`, `test_a_definition_on_the_record_...`) |
| M4: the old wording restored in `_gap_clause` | 5 failed, 46 passed (both positive unit arms, `test_a13_the_plain_language_clause_...`, both depths of the loop-level positive arm) |
| M5: M2 and M3 together | 10 failed, 41 passed, adding `test_a03_a_counted_gene_row_...` and `test_a13_a_variant_linked_...` |

Under M2 or M3 alone, the counted-gene A03 arm and the A13 variant arm stay green. Each rests on both protections (the record has no "lists none" statement, and its row carries a non-identity field), so only breaking both turns them red. That is two protections, not an unpinned one.

## Test runs

| Run | Result |
|---|---|
| Touched files (`test_first_sentence_gap.py`, `test_write_answers_sooner.py`) | 51 passed in 3.22s |
| `tests/system_03_search_agent/synthesis` | 753 passed, 10 skipped, 1 xfailed in 4.81s |
| `tests/system_03_search_agent/core` | 1442 passed, 56 skipped, 2 warnings in 71.81s |
| `ruff check` (whole repository) | 4 errors, all in `testing/Developer/reports/2026-10-08_phase_8.7/live/runner.py` (3 RUF100, 1 BLE001), a file tracked at the base and outside this round's fence; none in files touched here |
| `isort --check-only src tests` | Clean |

No live model calls were made.

## What stays open

- The four ruff errors in `live/runner.py` are pre-existing at the base. Whoever owns that file fixes them before the phase's push, or the CI ruff gate fails.
- The clause is now narrow: it never fires on a MedGen record that carries a definition. Saying more would mean reading prose for features, which is a model decision, not a code check. That trade is the lead's to state to the owner.
- `DECISIONS.md` is outside this round's fence. The choice of known absence by source state over removing the clause needs its row, written by the lead.
- Not covered here: F-8.7-J03 to J09 and F-8.7-A01, A04 to A12, A14, A15 belong to other agents or to the owner.
