# Card 110: fix round (the one round)

Fix agent, dial position 2. Base c2395ca7, branch `fix/card110-first-sentence-redesign`, pull request 242, worktree clean at start. Nothing committed. Design lines come from DECISIONS.md 2026-10-16. Scratch files are under `<scratchpad>/fix110/`.

## Table of contents

- [Findings](#findings)
- [What changed](#what-changed)
- [Mutations](#mutations)
- [Label map fuzz](#label-map-fuzz)
- [Replay bar](#replay-bar)
- [Feature round](#feature-round-lead-decision-on-clinical_features)
- [Gates](#gates)
- [Open](#open)

## Findings

| Finding | State | Test |
|---|---|---|
| J2-110-06, A2-110-02 (curly quotes, en dash) | closed | test_a_title_in_quotes_or_with_other_dashes_is_still_a_record_title (6 shapes: the reviewers' curly sentence, straight quotes, en dash, doubled space, no-break hyphen, single curly quotes), test_a_label_in_a_label_map_with_an_en_dash_matches_a_sentence_with_a_hyphen |
| J2-110-07, A2-110-03 (label-only candidate) | closed, including the live shape: a listed `clinical_features` value counts as a label for the later path (lead decision, 2026-10-16) | test_a_sentence_made_only_of_record_names_or_titles_is_never_a_later_candidate (9 shapes: joined by "and", comma, "or", nothing, three-item, "Ectopia lentis [14] and glaucoma [10]." and variants), test_a_sentence_with_any_other_word_is_still_a_later_candidate (6 shapes), test_the_label_filter_reads_only_the_label_map_no_word_list, test_a_fragment_of_listed_clinical_features_is_never_a_later_candidate (the d66_2 record shape; fails before the change), test_a_sentence_that_says_what_the_features_are_is_still_a_later_candidate |
| A2-110-01, J2-110-04 (later pick instructions) | closed | test_the_later_pick_is_asked_with_its_own_instructions, test_the_later_pick_has_its_own_instructions_that_say_it_reads_later_sentences (357 characters, under 1,000; no test-question words) |
| J2-110-03, A2-110-05 (trace) | closed | test_a_later_pick_and_checks_that_did_not_decide_the_opening_are_marked, test_a_late_first_pick_marks_the_finished_later_records_unused, test_the_later_records_that_decided_the_opening_keep_their_names |
| J2-110-01 (duplicate display number) | closed | test_the_label_map_keeps_the_last_citation_per_display_number_as_develop_did, plus the fuzz below |
| J2-110-02, J2-110-05, A2-110-04 | not in this round (declared departure; latency) | none |
| J2-110-08 | open | none |

## What changed

| File | Change |
|---|---|
| `src/system_03_search_agent/core/graph.py` | New `_is_only_record_labels` and `_label_form`; `_later_lead_candidates` uses it. The sentence splits at its markers and every piece must equal the label of the record its marker cites (labels may differ), joined by the grounding pass's own glue (`_clean_claim`: comma, "and", "or") or by nothing, nothing after the last marker. `_label_form` folds compatibility forms, makes every dash a hyphen, drops quotation marks and apostrophes, collapses spaces, folds case. No word list of its own. Card 111's `_repeats_one_label` and `_is_label_only_sentence` are untouched, so the prose is unchanged. |
| same | `_lead_label_map` takes a `fields` argument. The later path's call site passes `_LATER_LABEL_FIELDS` (the label fields plus `clinical_features`); card 111's prose rule still reads `LABEL_FIELDS` alone. |
| same | `_lead_label_map` keeps the last citation per display number, as develop did. |
| same | After the choice, a later pick or check that finished but did not decide the opening is renamed in the run's decisions with the suffix `.unused` (for example `write.lead_stands_alone.unused`). A task counts as read when the result waited on it. |
| `src/system_03_search_agent/harness/decide.py` | `LEAD_LATER_INSTRUCTIONS`: says the sentences come from later in the answer and the earlier ones are not shown. Develop's `LEAD_SENTENCE_INSTRUCTIONS` and tier A are untouched. |
| tests | The existing list-of-names test now asserts the new rule (a list of record names is never offered); 34 new test cases in `test_write_answers_sooner.py`, 1 in `test_decide.py`. |

## Mutations

Each: one property changed, the named test red, file restored (script `<scratchpad>/fix110/mutate.py`).

| Mutation | Red |
|---|---|
| drop the quote translation in `_label_form` | the curly-quote case of test_a_title_in_quotes_or_with_other_dashes_is_still_a_record_title |
| drop the dash translation | the en dash case of the same test |
| tier B filter back to `_repeats_one_label` (one label) | 9 of 9 cases of test_a_sentence_made_only_of_record_names_or_titles_is_never_a_later_candidate |
| drop `clinical_features` from `_LATER_LABEL_FIELDS` | test_a_fragment_of_listed_clinical_features_is_never_a_later_candidate |
| any sentence citing only labelled records counts as label-only | test_a_sentence_that_says_what_the_features_are_is_still_a_later_candidate and 3 cases of test_a_sentence_with_any_other_word_is_still_a_later_candidate |
| tier B handed `LEAD_SENTENCE_INSTRUCTIONS` | test_the_later_pick_is_asked_with_its_own_instructions |
| `_mark_unused_decisions` does nothing | test_a_later_pick_and_checks_that_did_not_decide_the_opening_are_marked |
| mark read tasks too | test_a_later_pick_and_checks_that_did_not_decide_the_opening_are_marked and test_the_later_records_that_decided_the_opening_keep_their_names |
| label map iterates `citations` directly | test_the_label_map_keeps_the_last_citation_per_display_number_as_develop_did |

## Label map fuzz

The judge's `diff111.py`, 10,000 cases (seed 110), run on develop 7626fe85 (from `git archive`), on the committed branch head c2395ca7 and on this tree.

| Tree | `_is_label_only_sentence` differences against develop | `_label_only_positions` differences against develop |
|---|---|---|
| c2395ca7 (before) | 0 | 11 |
| this tree | 0 | 0 (25 cases with a non-empty left-out set) |

## Replay bar

69 groundings (the 63 saved ones that carry sentences, plus 6 hand cases), 5 replays each, both trees, live Jev, develop's settings, 345 replays per tree. Raw rows: `bench_dev.jsonl`, `bench_new.jsonl`; analysis `analysis.txt`.

| Bar item | Result |
|---|---|
| 1 No lost win | Replays where tier A picked and the answer did not open on the pick: 0. Features second (ver d66_2, adv d66_3, adv d66_4): 5 of 5, 5 of 5, 5 of 5 on this tree; develop 5, 4, 5. Groundings below develop: adv dtrial_1 (develop 3, this 0; replayed 20 each: develop 3 of 20, this 1 of 20; tier A is the same call and says "neither" at confidence 0.04, A-110-06, older than this card), adv bgene_1 (5 and 4) and ver d66_1x#3 (5 and 4), the last two each a 1 s bound. |
| 2 No forbidden opening | 0 openings on A110_02, A110_01, A110_04a, A110_04b, bbrca_2, dbrca_1, dbrca_4, fbrca_4 sentences, and 0 on the hand cases curly title, en dash title, two titles joined by "and", the named Ectopia fragment and the plain title. 0 openings beyond tier A whose check said needs_earlier. The Ectopia fragment with the real d66_2 label map is covered by the feature round below. |
| 3 The gain | adv d66_5 5 of 5, case V_good3 5 of 5, fix f66_2 5 of 5, ver d66_1 4 of 5 (one count line), against develop 0 of 5 each. Also adv b66_4 4 of 5 against 0. |
| 4 Latency | Median 216 ms develop, 250 ms this tree; p95 363 and 436; max 1010 and 1004. Replays at or above 1,000 ms: 5 and 6 of 345, each the 1 s bound firing. |

Gain cases given up by the label-only rule: none. Among the 69 groundings, the label-only filter removes a later sentence only in case A110_02 and in the five hand cases (all paper titles or names, never an answer); no saved gain opened on a label-only sentence, and the count of later openings against the earlier bench of c2395ca7 is unchanged except Jev noise (b66_4 5 to 4, f66_2 4 to 5, ver d66_1 5 to 4).

Reviewers' hand cases, 5 replays each, develop and this tree: curly-quoted title, en dash title, two titles joined by "and", plain title, Ectopia fragment with name labels: count line 5 of 5 on both.

Live spend: about 1,900 Jev decisions at roughly $0.00002, about $0.04, under the $0.30 budget.

## Gates

| Gate | Result |
|---|---|
| `ruff check` (no path) | All checks passed |
| isort gate 2 (`isort --check-only --diff src tests services tracker alembic .claude .github`, version 9.0.0) | exit 0 |
| `pytest tests/system_03_search_agent/harness tests/system_03_search_agent/core tests/system_03_search_agent/synthesis -m "not integration" -q` | 2901 passed, 66 skipped, 1 deselected, 1 xfailed |

## Feature round (lead decision on clinical_features)

Groundings that carry features (adv b66 and d66 families, fix f66 family, ver d66_1#2) plus the hand cases, 5 replays each, both trees, live Jev: 100 replays per tree. The adv groundings use their saved label maps (now including `clinical_features`); the fix and ver groundings have no saved pickle, so their label map is empty and the change cannot touch them. Raw rows `f_dev.jsonl`, `f_new.jsonl`.

| Case | Develop | This tree |
|---|---|---|
| hand:ectopia_d66_2map ("Ectopia lentis [6] and glaucoma [10]." with the real d66_2 label map) | count line 5 of 5 | count line 5 of 5 |
| hand:features_full_d66_2map ("MedGen lists these clinical features: ...", real map) | count line 5 of 5 | opens on it 5 of 5 (still offered) |
| hand:ectopia_realmap (empty map, artefact: markers 19 and 27 are not in the real map) | count line | opens 5 of 5; not a real shape, kept for the record |
| gain cases adv b66_4, adv d66_5, fix f66_2, ver d66_1#2 | count line 5 of 5 each | 4 of 5, 5 of 5, 5 of 5, 5 of 5 |
| features first or second (b66_1, b66_2, d66_3, d66_4) and the rest | same as this tree | same as develop, 5 of 5 each |

Gain cases given up: none. Latency over the 100 replays: median 221 ms develop, 224 ms here; max 1,002 and 987.

## Open

- J2-110-08 (a sentence that continues a lifted later sentence stays in the prose): open, unchanged.
- J2-110-02 (declared departure) and J2-110-05, A2-110-04 (latency, minor): not in this round.
- The trace suffix is a rename of the decision's `name`, because the record schema forbids extra fields. A reader or test that matches `write.lead_*` names exactly now also sees `.unused` forms.
