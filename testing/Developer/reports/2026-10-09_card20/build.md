# Card 20 build: an isolate search narrowed by year and place

Base: develop at b01dee92. Branch `fix/card20-isolate-year-place`. Diagnosis: `testing/Developer/reports/2026-10-08_overnight/card20_diagnosis.md`. The owner's choice: "Think extracts the year and place from the question in the call it already makes; the answer says when a filter could not be applied."

## Table of contents

- [What the person sees now](#what-the-person-sees-now)
- [What changed](#what-changed)
- [Tests](#tests)
- [Checks](#checks)
- [Left for review](#left-for-review)

## What the person sees now

| Question | Before | After |
|---|---|---|
| `Which E. coli isolates carry blaKPC genes in the USA since 2020?` | Every blaKPC isolate, year and place dropped in silence | Only isolates from the USA collected since 2020; the note says "collected in USA since 2020" |
| `E. coli isolates with blaKPC from Atlantis` | Every blaKPC isolate, place dropped in silence | Every blaKPC isolate, and the note says the place is not a country name Pathogen Detection uses, so isolates from every place are counted |
| A question with no year or place | Unchanged | Unchanged: the same call and the same note, word for word |

## What changed

| File | Change |
|---|---|
| `tools/pathogen_detection_schemas.py` | From parked commit 94b0ba41, unchanged except one docstring sentence: optional `location`, `collection_year_min`, `collection_year_max` on `PathogenIsolateSearchInput`, bounds 1900 to 2100, a min-above-max validator, and `PATHOGEN_LOCATION_PATTERN`. |
| `tools/pathogen_detection.py` | From 94b0ba41, unchanged: the scan's predicate ANDs the gene test with a boundary-aware place prefix on `geo_loc_name` and a year range on `collection_date`; a missing or unreadable date never matches a year filter. |
| `core/isolate_search.py` | Not from 94b0ba41: none of its five year regexes. New `apply_filters` verifies what the model named; `GEO_LOC_COUNTRIES` is the INSDC geographic location vocabulary, read from insdc.org on 2026-10-09; `plan_calls` passes verified filters only; `disclosure` names them and each filter that could not be applied. |
| `core/graph.py` | `_ThinkClassification` gains `collection_year_min`, `collection_year_max` and `location`, all defaulted to None. `_THINK_SYSTEM_INSTRUCTION` gains TASK 6 and the three keys in its reply shape. `_think` calls `apply_filters` on an isolate question, before its disclosure is built. |

What code verifies, and nothing more:

- A year range is kept when every bound is a whole year in 1900 to 2100 within one of a four-digit number written in the question, and the lower bound is not above the upper. One either side lets an exclusive bound, the year before a named year, stay anchored. Any bound failing drops the whole range.
- A place is kept when it fits the tool's location shape and is a name in the INSDC vocabulary, in that vocabulary's own spelling. A place with an unsafe shape is never named back to the person.

The prefix-hash check: Think's call sends no stable prefix (`cache_prefix=None`), so `build_stable_prefix` is unchanged; `test_prompt_cache_prefix.py` passes. TASK 6 is fixed text, and a new test proves Think's system message hashes the same (SHA-256) for two different questions and memory suffixes.

## Tests

| File | Added |
|---|---|
| `tests/system_03_search_agent/tools/test_pathogen_detection.py` | 94b0ba41's tool tests, applied cleanly |
| `tests/system_03_search_agent/core/test_isolate_search.py` | 22 cases: no year or place read from the words, anchored years kept, six unverifiable years dropped and said, vocabulary spellings kept, four unknown or unsafe places dropped and said, an empty place, the planned call, the disclosure, the unchanged call with no filter |
| `tests/system_03_search_agent/core/test_isolate_search_wiring.py` | Through the real `think_node` and `plan_node`: the model's year and place narrow the planned search; an unknown place and an unwritten year are each dropped and said; no filter keeps the old disclosure word for word; a reply without the new keys parses; the system message hash |
| `tests/system_03_search_agent/core/test_think_sra_disease_fallback.py` | Its pin of `_ThinkClassification`'s field set now lists the three new fields |

Mutation: replacing `isolate_question = isolate_search.apply_filters(` with an unused assignment in `_think` turned 3 wiring tests red ("3 failed, 16 passed"); restored, "19 passed".

| Run | Result |
|---|---|
| `test_isolate_search.py` | 61 passed |
| `test_isolate_search_wiring.py` with `test_prompt_cache_prefix.py` | 24 passed |
| `test_think_sra_disease_fallback.py` | 12 passed |
| `tests/system_03_search_agent/core` | 1 failed (the field-set pin above, then fixed), 1506 passed, 56 skipped |
| `tests/system_03_search_agent/tools` | 1684 passed, 99 skipped |

No live model or network calls.

## Checks

| Check | Result |
|---|---|
| ruff on the eight touched files | All checks passed |
| isort `--check-only` on the touched files other than `core/graph.py` | Passed |
| isort on `core/graph.py` | Fails identically on develop at b01dee92 (the `contracts.events` import block, untouched here). Pre-existing. |
| `tracker/check_doc_sync.py` | ok |

## Left for review

- Live proof is not run here: no model call was made, and the tool's live scan was last measured by 94b0ba41 (E. coli, blaKPC, USA, since 2020: 580 of 584,992 rows, 21.26 s).
- A follow-up such as query 41's `Show me the ones from 2023` still cannot use the filter: a follow-up does not carry an isolate search forward. That is outside this card's fence.
- A place the vocabulary holds but the file has no isolates for returns a true zero; the note names the place, so it reads as "none from there", not as a filter that failed.
- `Falkland Islands (Islas Malvinas)` is in the vocabulary but its brackets fail the tool's location shape, so that one place is always reported as not applied.
- The count sentence (`count_sentence`) is unchanged, as the diagnosis advised; the filters are named in the note beside it.
