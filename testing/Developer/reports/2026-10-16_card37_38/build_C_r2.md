# Card 38 slice C build report, round 2: angle brackets in paper titles

Branch `fix/card38-paper-titles-r2`. Fixes V-38C-01.

## What changed, in the person's words

- A paper title that names a variant ("c.3140-26A>G", "3849+10kbC->T") or a bound ("<5 years") now shows exactly as PubMed wrote it.
- Only text shaped like a markup tag (`</question>`, `<question>`, `<b>`, `<script src=x>`) is neutralised: its brackets and slash go, its words stay.

## Diff

- `src/system_03_search_agent/synthesis/article_titles.py`: new `_MARKUP_TAG` (`</?[A-Za-z][^<>]*>`); `clean_article_title` replaces each match with its inner words (leading slash dropped) and keeps every other `<` and `>`.
- `tests/system_03_search_agent/synthesis/test_article_titles.py`: three tests.

## Tests

- `test_variant_notation_and_bounds_are_kept_byte_for_byte`: four titles including the three notations, returned unchanged.
- `test_each_tag_form_is_neutralised`: four tag forms leave no `<` or `>`, words stay.
- `test_a_title_mixing_tags_and_notation_loses_only_the_tags`: "<b>CFTR c.1585-1G>A</b> in children <5 years" gives "b CFTR c.1585-1G>A b in children <5 years".
- The existing hostile-title test (words stay) passes unchanged.

Mutation: restoring the old rule (every `<` and `>` to a space) turns 5 tests red (four notation cases and the mixed title). Restored.

## Commands

- Slice files: 61 passed.
- `synthesis/` plus the 12 core files naming the build_C neighbour functions: 1419 passed, 20 skipped, 1 xfailed.
- `ruff check` (whole repository): passed. `isort --check-only` per gate02: passed. `ruff format --check` on both files: passed.

## Unsure about

- A tag is replaced by its inner words, so "<b>x</b>" reads "b x b". Chosen to keep the existing test (the words stay). A title with a literal "a <b and c> d" would be read as a tag.
