# Card 111 alone: build report

Re-split ordered by the product owner: card 111 ships alone, card 110 is reverted. History: [2026-10-15_cards110_111](../2026-10-15_cards110_111/) (build, fix round, judge, adversary, verifier).

## Table of contents

- [Base](#base)
- [What came over](#what-came-over)
- [What was left out](#what-was-left-out)
- [Proof](#proof)
- [Verifier card 111 cases](#verifier-card-111-cases)
- [Gates](#gates)
- [Learnings](#learnings)

## Base

Worktree `<repo-root>`-relative `asu-wt/card111`, branch `fix/card111-repeated-title`, HEAD `cffdb8fd2d96968a62518d5eded1ecbefed34a15`. Source of the logic: 3cef7ae6.

## What came over

| File | Change |
|---|---|
| core/graph.py | `_is_label_only_sentence`, `_label_only_positions`, the echo drop and keep-all guard in `_answer_parts`, `listing_sentences` argument, `skip` argument on `_lead_candidates` and `_lead_sentence_choice` (a left-out sentence is never offered), `LABEL_FIELDS` and `_clean_claim` imports, call-site wiring in `_write_answer` |
| synthesis/answer_layout.py | public `LABEL_FIELDS` |
| synthesis/findings.py | features directive: one list, "and" only before the last name |
| tests/.../core/test_summary_label_only_sentence.py | card 111 tests as at 3cef7ae6; one test adapted (see below) |
| tests/.../synthesis/test_listing_one_row_per_record.py | features directive test, as at 3cef7ae6 |

The one adapted test, `test_a_sentence_the_prose_leaves_out_is_never_a_lead_candidate`, imported `_picks` from card 110's helper set in `test_write_answers_sooner.py`. `_picks` only filtered out card 110's standalone requests, so the test now reads `asked[0]` directly. Its assertions are unchanged.

## What was left out

- `harness/decide.py`: `git diff cffdb8fd -- src/system_03_search_agent/harness/decide.py` is empty (0 lines).
- `test_decide.py` and `test_write_answers_sooner.py`: diff against cffdb8fd is empty (0 lines).
- The lead pick is develop's: two candidates, one decision, no standalone check, no timing code. Only the `skip` filter is new.
- Grep over `src` for `stands_alone`, `LEAD_STANDALONE`, `LEAD_STANDS`, `LEAD_NEEDS`, `_shared_room`: no match. The word "standalone" appears only in older, unrelated comments. Added lines containing third, fourth, four, standalone: none.

## Proof

- (a) Tests on cffdb8fd's src (graph.py, findings.py, answer_layout.py restored from cffdb8fd, tests kept): `23 failed, 32 passed`. On this branch: `55 passed in 2.39s`.
- (b) Mutations, each restored afterwards:
  - Allow distinct names (drop the label mismatch checks): `6 failed, 19 passed`, including `test_a_cited_list_of_distinct_names_is_kept`.
  - Ignore the listing (`if False:` for the all-markers-listed check): `3 failed, 22 passed`, including `test_with_no_listing_the_repeated_title_stays`.
  - Pass no `skip` to the lead candidates: `1 failed, 24 passed` (`test_a_sentence_the_prose_leaves_out_is_never_a_lead_candidate`).
  - After restore: `55 passed`.
- (c) Diff summary against cffdb8fd: 5 files changed, 414 insertions, 5 deletions (graph.py, answer_layout.py, findings.py, two test files).

## Verifier card 111 cases

The verifier's end-to-end probe (21 cases, c01 to c21) was run on this branch through `write_node`. Results match the verifier's "Branch" column in every case:

- Left out: c01, c02, c03, c04, c05, c13, c16, c18, c20.
- Kept: c06, c07, c08, c21 (distinct names), c17 and c19 (no listing).
- Stripped by the grounding pass, so no echo remains: c09, c10, c11, c12, c14, c15.

Unit cases u1 to u10: u1 to u5, u7, u8, u9 are the parametrized cases in `test_label_only_is_decided_from_structure` (all pass). u6 (the second marker cites a non-label field): False, kept. u10 (listing line markers [1][2]): True, dropped, as recorded.

## Gates

- `ruff check` (no path): `All checks passed!`
- `isort --check-only` on the five touched files: only `core/graph.py` fails. cffdb8fd's `core/graph.py` fails the same way: the diff on both is the identical `contracts.events` `EventResolvedEntity` reordering.
- `pytest tests/system_03_search_agent/harness tests/system_03_search_agent/core tests/system_03_search_agent/synthesis -m "not integration" -q`: `2 failed, 2846 passed, 66 skipped, 1 deselected, 1 xfailed, 2 warnings in 98.97s`. The two failures are the known glm price tests in `test_opus_writer.py`.

## Learnings

- Nothing over five minutes. Small: zsh does not split an unquoted variable of paths, and a `sed` expression containing `/` paths needs another delimiter, so edits went through a small Python helper.
