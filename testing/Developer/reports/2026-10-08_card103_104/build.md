# Cards 103 and 104: build

Branch `fix/card103-104-answer-tables`, on develop `2182aff3`. The diagnosis in `diagnosis.md` names the causes; this note says what changed.

## Table of contents

- [The change in the reader's words](#the-change-in-the-readers-words)
- [Exact cell wordings](#exact-cell-wordings)
- [Choices and rejected alternatives](#choices-and-rejected-alternatives)
- [Tests](#tests)
- [Not changed](#not-changed)

## The change in the reader's words

- Card 103: under the variant-to-disease table, no disease cell is blank. A row whose only condition is a ClinVar placeholder says so in the record's own words. A row whose condition name could not be looked up says that.
- Card 104: an answer lists a record once. Two rows for the same page and the same identifier become one row that keeps both citation numbers, so "BRCA1 NCBIGene:672" no longer appears twice while Sources shows the page once.

## Exact cell wordings

| Situation | Cell |
|---|---|
| Only "not provided" linked | None named: the ClinVar record says not provided |
| Only "not specified" linked | None named: the ClinVar record says not specified |
| Both linked | None named: the ClinVar record says not provided and not specified |
| Name lookup failed | Name could not be looked up |
| Placeholder and a failed lookup | None named: the ClinVar record says not provided; Name could not be looked up |
| A real name present | The names, as before |
| No condition linked at all | Empty, as before (nothing was linked) |

A row's merged citations read in order, for example "BRCA1 [8][12]". The first row's name stays.

## Choices and rejected alternatives

| Choice | Rejected | Why |
|---|---|---|
| Say why in the cell, from `empty_cell_reason` in `answer_layout.py`, called where `core/graph.py` writes the cell | Drop placeholder-only rows; reword the line under the table | Dropping hides cited records and breaks "Found N". A reworded line leaves a blank that still looks broken and would call a failed lookup "names none". |
| The mapping column still appears only when a row has a real name (`mapped` is unchanged) | Show the column when any cell has a reason | The explanation alone must never create a table. |
| Merge key is `source_page_key` of the link plus the identifier cell | Raw link plus cells (the old key); page alone | The old key kept the slash and name duplicates. The page alone would merge a gene's different records that share a page. |
| A row with no identifier also needs the same name to merge | Merge on page alone when identifiers are all empty | Two different records on one page must not merge on a blank. |
| Merge adds citation ids to the first row's `marker_ids`, as linked diseases already do | Rewrite the row text | The row text keeps the first sentence; no surface changes. |
| The Notes line and the line under the table are unchanged | Count failed lookups in the Notes line | Out of the stated scope; no test showed a contradiction with the cells. |

## Tests

All in `tests/system_03_search_agent/core/test_write_answer_structure.py`. Seen red on develop's source, green after.

- Updated on purpose: `test_variant_records_become_a_variant_to_disease_table` pinned the blank cell (`""`); it now expects "None named: the ClinVar record says not provided".
- `test_no_disease_cell_is_blank_without_a_reason`: five HNF1A placeholder rows (four "not provided", one "not specified"), one real name, one failed lookup, no blank cell.
- `test_empty_cell_reason_names_both_placeholders_and_a_failed_lookup`: the wordings above, including both placeholders and the mixed case.
- `test_one_gene_page_is_one_row_with_every_citation`: BRCA1 with and without a trailing slash is one row carrying both citation ids; the opening "Found 1 gene record" line, the trust line and the Sources page count equal those of the single-row answer.
- `test_one_page_with_two_names_keeps_the_first_name`: the saved-answer case, one exact link and two names.
- `test_same_page_different_identifier_stays_two_rows`: green before and after, a guard against over-merging.
- `test_the_plain_language_list_does_not_repeat_a_record`: the Plain language list merges the same way.

## Not changed

- The frontend, `disease_names.py`, claims, citations and counts.
- Answers already saved keep their old rows, since a saved answer replays stored tokens.
- The 25-condition lookup cap and the 500-character cut in the diagnosis stay as findings; neither was seen live.
