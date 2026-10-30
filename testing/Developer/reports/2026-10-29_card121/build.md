# Card 121 build: a variant record named once

## Table of contents

- [Cause](#cause)
- [Fix](#fix)
- [Tests](#tests)

## Cause

- Count line: already fixed on develop. `answer_summary_sentence` in `synthesis/answer_layout.py` strips a trailing " record" from the kind noun before it adds "record"/"records" (build step "Count papers in the count line and use reader nouns"). A Researcher rs id answer now opens "Found 1 variant record for ...".
- Table heading: still doubled. `grouped_listing` in `core/graph.py` builds `f"{Noun} records found"` from `entity_type_noun(raw_type)`. The dbSNP row type is "Variant record", so the noun is "variant record" and the heading read "Variant record records found".
- Other kinds: the only kind whose type name ends in "record" in the graph and Layer 2 row types is "Variant record". The fix is general, so any such kind is covered.
- Plain language: its opening sentence uses everyday nouns ("I found 1 genetic variant ..."), not "variant record", so it was never doubled. It is unchanged by design.

## Fix

- `core/graph.py`, `grouped_listing`: drop a trailing " record" from the noun before building the heading. A noun that is just "record" gives "Records found". Same idiom as the count line.

## Tests

- `tests/system_03_search_agent/core/test_write_answer_structure.py`: card 121 tests for 1 and 2 variant records in both depths (no "record record" in any heading or opening; Researcher heading "Variant records found", opening "Found N variant record(s)"), and a Disease answer whose heading "Disease records found" and opening "Found 3 disease records" are unchanged.
- Red before the fix (2 Researcher cases fail on the doubled heading), green after. Whole file: 83 passed.
