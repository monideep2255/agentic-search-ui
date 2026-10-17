# Card 18 build: one row per record

## What changed, in the person's words

A paper with a long abstract is listed once in an answer's records list, not two or three times. The row keeps its first sentences, its cells and its citation number. The command line prints only those first sentences for such a paper (owner decision of 2026-10-16); the web and saved answers lose nothing.

## Diff summary

- `src/system_03_search_agent/core/graph.py`, inner `merge_into` of `_answer_parts`: the `len(ids) > 20` skip stays. When the joined text would pass 1000 characters, a repeat that adds no marker folds into the first row and its sentence is not appended; a repeat that adds a marker still skips and stays its own row. The 1000 cap, `contracts/events.py` and the mapping cell check are untouched.
- `tests/system_03_search_agent/core/test_write_answer_structure.py`: three tests and a helper after the existing tests.

## Tests

| Test | Proves | Fails on develop |
|---|---|---|
| `test_long_abstract_sentences_of_one_record_are_one_row` | Three sentences of about 436 characters on one PubMed record give one row at Researcher and Plain language: text at most 1000, first sentences kept, marker `pm-1`, cells present | Yes (two rows, lengths 872 and 436) |
| `test_short_repeat_of_one_record_still_appends_its_sentence` | A repeat under 1000 appends exactly as today | No, passes on both |
| `test_long_repeat_with_a_new_citation_stays_its_own_row` | A long repeat citing `pm-2` keeps both markers on rows, text at most 1000 | No, passes on both |

## Commands

- `pytest -q tests/system_03_search_agent/core/test_write_answer_structure.py`: 54 passed. This is the only file that references `_answer_parts` or `_answer_tokens`.
- `ruff check` clean on both files. `ruff format --check` and `isort --check-only` already report drift on develop in both files (outside my lines; I did not reformat them).

## Unsure

- The third test cites a second record, so the two rows come from different pages. A same page repeat that adds a marker cannot be built from the fallback sentences alone; the `len(ids) > len(first marker_ids)` guard is the code that covers it and is not exercised on its own.
- The `ids` limit of 20 has no new test; its line is unchanged.
