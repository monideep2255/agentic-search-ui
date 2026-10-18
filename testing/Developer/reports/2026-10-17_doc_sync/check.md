# Drift check: dated rows outside the append-only table

## What changed

- `check_append_only_table` in `tracker/check_doc_drift.py` now scans every line of DECISIONS.md and LEARNINGS.md for a dated row (`DATED_ROW_RE`). A row that is not inside the one contiguous table under the header fails, with its line number and the words "renders as loose text".
- Text after the table's last row also fails: the table must be the last thing in the file, so an append lands in it.
- The module docstring now states both rules.

## Tests

- `tests/tracker/test_check_doc_drift.py`: a row after the table in another section, a row before the header, a row glued to a paragraph (the 2026-08-28 shape), text after the table, and the clean case. Both files are covered where the rule is the same.
- Result: 36 passed in that file, 72 passed in `tests/tracker/`.

## Mutations

| Mutation | Result | Restored |
|---|---|---|
| Scan only after the table, not before | 1 test failed (row before header) | Yes |
| Stop scanning at the first heading | 3 tests failed | Yes |
| Allow trailing text after the table | 2 tests failed | Yes |

## Live check

`python3 tracker/check_doc_drift.py --check` reports 0 structural findings on the current DECISIONS.md and LEARNINGS.md.
