# Cards 110 and 111: build report

Base commit: cffdb8fd2d96968a62518d5eded1ecbefed34a15 (develop, branch fix/cards110-111-summary-opening).

## Table of contents

- [Files per card](#files-per-card)
- [Card 110: what changed](#card-110-what-changed)
- [Card 111: what changed](#card-111-what-changed)
- [Mutation proofs](#mutation-proofs)
- [Gates](#gates)
- [Live runs](#live-runs)
- [Not covered](#not-covered)
- [Learnings](#learnings)

## Files per card

| Card | Files |
|---|---|
| 110 | `src/system_03_search_agent/harness/decide.py`, `tests/system_03_search_agent/harness/test_decide.py`, `tests/system_03_search_agent/core/test_write_answers_sooner.py` |
| 111 | `src/system_03_search_agent/core/graph.py`, `src/system_03_search_agent/synthesis/findings.py`, `tests/system_03_search_agent/core/test_summary_label_only_sentence.py` (new), `tests/system_03_search_agent/synthesis/test_listing_one_row_per_record.py` |

`_lead_candidates` in `core/graph.py` needed no change: it slices to `MAX_LEAD_CANDIDATES`, which now is four.

## Card 110: what changed

- `LEAD_SENTENCE_PICKS` is now first, second, third, fourth, so `MAX_LEAD_CANDIDATES` is four.
- Four, not three: the sentence that answers can sit behind two abstract sentences (the Marfan case), and a fourth costs about 700 more input characters, small beside the 1 s wait the caller already bounds.
- `third` and `fourth` each have a criterion ("Sentences 1 and 2 do not, and sentence 3 ... states a fact that answers what the question asks").
- `_LEAD_CANDIDATE_MAX_CHARS` is 700 (was 1200). Worst case: 1000 + 10 + 4 x (700 + 12) + 3 x 2 = 3864, under `_STATE_MAX_CHARS` 4000.
- The instruction text says "the first few sentences". The pick stays the classifier's; no word of any question is in code or prompt.
- Latency of the pick (live Jev, same Marfan question, six calls each, the dedicated measure, `decide()` directly): 2 candidates 227, 148, 192, 195, 195, 187 ms (median 193.5); 4 candidates 195, 235, 163, 189, 210, 212 ms (median 202.5). No visible change; far under the 1 s bound (F-8.7-A07). The "2 candidates" arm uses today's criteria and state shape with two sentences, not develop's exact old text.
- Same probe, sentences ordered abstract, abstract, features, publication: with 2 candidates the pick was "neither" 6 of 6 (the features sentence was not offered); with 4 candidates it was "third" 6 of 6.

## Card 111: what changed

- `_is_label_only_sentence` (beside `_answer_parts`): splits a grounded sentence at its markers. Each piece, after the grounding pass's own glue rule (`_clean_claim`: leading comma, "and") and end punctuation, must equal the whole title or name (finding fields name, title, symbol, preferred_name) of the record its marker cites. Any other word, text after the last marker, a marker citing no labelled record, or no marker: not matched. No word list of its own, no word of the question.
- The prose loop of `_answer_parts` skips such sentences. If that would leave no model sentence at all (every model sentence is label-only and none leads), nothing is skipped: develop's behaviour. A lead sentence always counts as a model sentence kept.
- `build_clinical_features_directive` (dynamic suffix only): adds "Write every feature in that one sentence as a single list: commas between the names, and the word "and" only before the last name, never between two names in the middle of the list." It constrains the list shape only, never which names may appear; the stable prefix is untouched.
- Dropped sentences' records still appear in the listing, because the listing is built from all records.

## Mutation proofs

| Mutation (one property) | Test that went red | Output line |
|---|---|---|
| Card 111: prose loop never skips (`if position in echo_positions:` to `if False:`) | `test_summary_label_only_sentence.py::test_a_summary_does_not_end_on_a_sentence_of_record_names` | `1 failed, 11 passed` |
| Card 111: directive says "somewhere in the list" instead of "only before the last name" | `test_listing_one_row_per_record.py::test_the_features_directive_asks_for_one_list_with_and_only_before_the_last_name` | `1 failed, 29 passed` |
| Card 110: `LEAD_SENTENCE_PICKS` back to two names | `test_write_answers_sooner.py::test_the_lead_options_are_closed_and_end_on_neither` and `::test_the_third_cited_sentence_can_lead_the_answer` | `2 failed, 49 passed` |
| Card 110: `_LEAD_CANDIDATE_MAX_CHARS` back to 1200 | `test_decide.py::test_the_lead_state_holds_the_question_and_four_longest_candidates_whole` | `1 failed, 72 passed` |

Each was restored after its run. The tests also fail on develop's code (develop has two picks, a 1200 cap, no label check and no list sentence).

## Gates

- `ruff check` (no path, worktree root): `All checks passed!`
- `isort --check-only` on `decide.py`, `findings.py` and the four test files: clean. On `core/graph.py` it reports an import-order complaint on the `ResolvedEntity as EventResolvedEntity` import block; develop's own copy of `graph.py` reports the same, and my only import change (`_clean_claim` added in the grounding import) is not in the diff isort proposes.
- `pytest tests/system_03_search_agent/harness tests/system_03_search_agent/core tests/system_03_search_agent/synthesis -m "not integration" -q`: `2 failed, 2836 passed, 66 skipped, 1 deselected, 1 xfailed`. The two failures are `test_opus_writer.py::test_the_rollback_writer_glm_5_2_is_still_priced_by_the_installed_map` and `::test_the_old_writer_is_never_priced_below_the_static_estimate`: litellm's installed price map has no entry for `z-ai/glm-5.2` (`no OpenRouter price found`). They touch nothing I changed.

## Live runs

Path: `core/run.py` `run_streaming`, `reads_placement=True`, `CLASSIFIER_PROVIDER=jev`, `PER_QUERY_COST_CAP_USD=0.25`, `SYNTH_MODEL=anthropic/claude-opus-5.5` (the code default; the local `.env` names `z-ai/glm-5.2`, which has no price and made the writer fail on the first attempt, discarded).

Plain language, "What phenotypic features are associated with Marfan syndrome?":

| Run | Opens on | Label-only sentence | Lead pick (options offered) | Jev latency | Cost |
|---|---|---|---|---|---|
| 1 | features sentence | none | first (2) | 197 ms | 0.00235 |
| 2 | features sentence | none | first (4) | 229 ms | 0.00219 |
| 3 | features sentence | none | first (4) | 180 ms | 0.00327 |
| 4 | features sentence | none | first (4) | 209 ms | 0.00339 |
| 5 | features sentence | none | first (4) | 234 ms | 0.00324 |

The features sentence in every run read as one list with "and" only before the last name, for example "MedGen lists these clinical features: Aortic regurgitation [3], Arachnodactyly [4], ..., Hypertropia [12] and Micrognathia [13]."

Researcher, "What is known about EGFR mutations in non-small cell lung cancer, and what trials are recruiting?":

| Run | Opens on | Label-only sentence | Lead pick | Cost |
|---|---|---|---|---|
| 1 to 5 | the count line ("Found 5 clinical trial records and 38 sequence variant records for EGFR, of 4002 available") | none | none asked | 0.00126, 0.00121, 0.00120, 0.00117, 0.00119 |

Total reported spend about $0.03, under the $0.60 cap.

What the live runs do and do not show:

- The label-only sentence did not occur in any of the 5 Marfan runs (the writer cited the papers as "Another is PMID ..."), so the live runs do not exercise the card 111 drop. The structural check is proved by the offline tests and mutation only.
- The features sentence came first in all 5 Marfan runs, so the third-position case of card 110 did not occur live. The probe above (abstract, abstract, features, publication, 6 of 6 "third") is the proof that it now can lead.
- EGFR: the answer had no model-written sentence in 5 of 5 runs (reported cost is only the classifier calls, so the writer appears not to have produced prose), so there was nothing for the lead pick to choose and it opened on the count line. That is a different cause from card 110 and my change cannot affect it.

## Not covered

- "BRCA1, and its gene symbol is BRCA1.": not covered. The piece "and its gene symbol is" carries words beyond a label, and the structural check, by design, never drops a sentence that says something beyond labels. Covering it would need a judgement of meaning, which LEARNINGS.md (2026-09-24, grounding.py) rules out for code.
- A sentence of cited labels joined by a verb ("A [1] causes B [2]") is kept, by the same rule.
- EGFR Researcher opening on the count line: see above; a separate cause, not diagnosed here.
- A label-only sentence still leaves its records in the listing, and its citation chips still exist; only the prose sentence is dropped.

## Learnings

- The local `.env` sets `SYNTH_MODEL=z-ai/glm-5.2`, which litellm cannot price, so any live run from this machine's `.env` loses the writer ("writer call failed after the listing was sent") and shows only the count line. Cost me one discarded run. Run live checks with `SYNTH_MODEL=anthropic/claude-opus-5.5`. The same missing price fails two tests in `test_opus_writer.py` on develop.
