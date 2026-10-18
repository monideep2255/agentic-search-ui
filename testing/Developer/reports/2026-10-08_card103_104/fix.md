# Cards 103 and 104: fix round

One fix round on branch `fix/card103-104-answer-tables`, pull request 205, for the findings in `judge.md` and `adversary.md`. Each finding below says what the reader now sees, what changed and which test proves it.

## Table of contents

- [In the reader's words](#in-the-readers-words)
- [Final cell wordings](#final-cell-wordings)
- [Per finding](#per-finding)
- [Tests seen red, then green](#tests-seen-red-then-green)
- [Gates](#gates)
- [Not changed](#not-changed)

## In the reader's words

- A disease cell never says "None named" when the record links a condition we could not name. It says only "Name could not be looked up".
- Only a ClinVar variant row ever says "the ClinVar record says". A gene row is never told about a ClinVar record its own link does not open.
- "See cases" is never quoted bare, so it cannot read as an instruction.
- The Notes line now agrees with the cells: placeholder links "are not listed as diseases".
- Two rows for one record become one row only when they show the same thing. The merged row keeps every citation number, in order, and nothing either row showed disappears. When that cannot hold, both rows stay, as on develop.
- The command line prints every citation number of a merged row.

## Final cell wordings

| Situation | Cell |
|---|---|
| ClinVar variant row, only "not provided" linked | None named: the ClinVar record says not provided |
| ClinVar variant row, only "not specified" linked | None named: the ClinVar record says not specified |
| ClinVar variant row, both linked | None named: the ClinVar record says not provided and not specified |
| ClinVar variant row, any other placeholder ("see cases"), alone or with the two above | None named: the ClinVar record gives only a placeholder |
| Any row with a condition whose name lookup failed, with or without a placeholder | Name could not be looked up |
| Gene or other row whose links are all placeholders | Empty, as on develop |
| A real name present | The names, as before |
| No condition linked at all | Empty, as before |

Notes line: "N variant links to ClinVar placeholder conditions ('not provided', 'not specified' or 'see cases') are not listed as diseases." The count is unchanged.

## Per finding

| Finding | What changed | Test |
|---|---|---|
| J-103-01 | `empty_cell_reason` returns "Name could not be looked up" alone whenever any linked condition did not resolve | `test_a_failed_lookup_beside_a_placeholder_never_says_none_named` |
| J-103-02, A-103-01 | `empty_cell_reason` takes the row's `source_url`; the ClinVar wording needs a `SequenceVariant` row whose page is a ClinVar variation page | `test_only_a_clinvar_variant_row_is_told_the_clinvar_record_says`, `test_a_gene_row_in_the_table_is_not_told_the_clinvar_record_says` (real `write_node`) |
| J-103-09, A-103-05 | Only "not provided" and "not specified" are quoted; any other placeholder gives the generic wording | `test_only_not_provided_and_not_specified_are_quoted` |
| A-103-04, J-103-07 | `placeholder_links_note` ends "are not listed as diseases" | `test_the_notes_line_agrees_with_the_cells`, and the pin in `synthesis/test_answer_layout.py` |
| J-103-03 | A merge that would need more than 20 citation numbers does not happen; the repeat stays its own row, as on develop | `test_a_full_row_never_swallows_a_later_citation` |
| J-103-04 | A merged row's citation numbers are sorted ascending | `test_a_merged_row_reads_its_citations_in_ascending_order` |
| A-103-02 | Rows merge only when every cell agrees, so a placeholder row and a named row of one page stay two rows, each cell beside its own chips | `test_a_merged_disease_cell_never_contradicts_its_chips` |
| A-103-06 | A blank cell on one row takes the other row's value; two different values keep two rows | `test_a_merge_keeps_a_value_only_the_later_row_carried`, `test_two_different_values_keep_two_rows` |
| J-103-05 | Two names for one page are different cells, so case B now stays two rows; edge rows with identical cells still merge, each sentence kept in the row's text | `test_one_page_with_two_names_stays_two_rows` (replaces the test that pinned one row) |
| Disease cell on a merge | The merged row's disease cell is recomputed from both rows' linked conditions together, must read what the rows showed, and its chips come from the same set | `test_a_merged_row_takes_the_disease_chip_of_the_row_that_named_it` |
| A-103-03 | A merged row's `text` carries both grounded sentences, each with its own number. The command line prints `text` before any citation arrives, so the number has to be in the text; the renderer itself is unchanged | `test_the_command_line_prints_every_citation_of_a_merged_row` (drives the real `Renderer`) |
| J-103-06 (M6), A-103-09 | The name guard now lives in the cell check: the key is page plus identifier, and the name must match exactly, never taken from the other row | `test_two_records_with_no_identifier_merge_only_on_the_same_name` (both depths) |
| J-103-06 (M10) | The Researcher list path merges through the same check | Same test, Researcher arm |
| J-103-06 (M14) | No change; now pinned | `test_a_group_of_only_placeholder_rows_gets_no_disease_column` |
| J-103-06 (M16) | Placeholder words are a set, said once in a fixed order | `test_only_not_provided_and_not_specified_are_quoted` ("not provided" twice) |
| A-103-10 | Pinned by the disease-chip test above | As above |

Numbers: `test_the_stated_numbers_stay_as_on_develop` pins the opening "Found N" line, the trust line and the Sources page count for the diagnosis's cases (the HNF1A placeholder table, case A and case B, in both depths) to what develop `2182aff3` states for the same input, read by running that input against develop's source.

## Tests seen red, then green

Run against the branch head before this round (`655dc046`), 14 tests failed. Against this round, all 51 in `test_write_answer_structure.py` pass.

- Red before, green after: the 13 new or rewritten tests named in the table above, plus `test_empty_cell_reason_names_both_placeholders_and_a_failed_lookup`, updated for the new `source_url` argument.
- Green before and after, as guards: the no-identifier name test, the no-column test and the numbers test.

Mutation check on a scratch copy, the test file run after each:

| Mutation | Result |
|---|---|
| Name not compared (the no-identifier guard removed) | 3 red |
| Disease-chip merge removed | 1 red |
| 20-number check removed | 1 red |
| Ascending order removed | 1 red |
| Merged text keeps the first sentence only | 1 red |
| A blank cell does not take the filled value | 2 red |
| Reasons alone create the disease column | 1 red |

## Gates

Each run on its own, its exit code read directly.

| Gate | Exit code |
|---|---|
| `ruff check` | 0 |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | 0 |
| Core answer tests (`test_write_answer_structure.py` and ten sibling files) | 0, 171 passed |
| `tests/system_03_search_agent/synthesis` | 0, 664 passed |
| `adapters/cli/test_render.py`, `test_s3_as_printed.py` | 0, 138 passed |
| `tests/system_03_search_agent/core -k "listing or plain or table or record or answer"` | 0, 296 passed |
| `python3 tracker/check_doc_drift.py --check` | 0, nothing stale |

## Not changed

- The frontend. It draws table rows from `cells` and chips from `marker_ids`; a merged row's longer `text` shows only where a row has no cells.
- J-103-08, A-103-07, A-103-08: a failed lookup beside a real name, the 500-character cut and the three kinds of failed lookup, all as on develop and outside this round.
- J-103-10: the wording choices are recorded here and in `build.md`; a `DECISIONS.md` row is the lead's call.
