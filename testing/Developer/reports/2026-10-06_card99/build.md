# Card 99 build: the pair check

Builder report, 2026-10-06, branch `fix/card99-pair-check`. The owner chose option 4 of `testing/Developer/reports/2026-10-05_qualifier_check/design.md` on 2026-10-06, after the measurement in `measurement.md` beside this file. Option 5, the writer's prompt line in `synthesis/findings.py`, was not chosen and is not built. Everything changed is inside `src/system_03_search_agent/synthesis/sentence_check.py` and runs only in Jev mode.

## Table of contents

- [What changed for the person reading](#what-changed-for-the-person-reading)
- [How it works](#how-it-works)
- [Choices made, with the alternatives](#choices-made-with-the-alternatives)
- [Tests](#tests)
- [Offline result through the shipped code](#offline-result-through-the-shipped-code)
- [Added time and spend](#added-time-and-spend)
- [Gates](#gates)
- [What is not covered](#what-is-not-covered)

## What changed for the person reading

| Before | After |
|---|---|
| A plain-language answer could say "In children, GERD symptoms can be varied and nonspecific" where the paper says young children | That sentence is not shown. In the offline run, none of the 9 "young children" sentences and none of the 3 dropped "potentially" sentences was approved |
| A faithful sentence the check approved was shown | It is still shown unless one of its quote phrases is judged a dropped limit. A sentence can only lose approval, never gain it |
| A sentence that leaves out a setting or a modifier from its record, such as "outpatient" or "abnormal transient", was shown | It may be held back: 7 of 144 faithful rewordings in the offline run, each one sentence fewer, never a wider claim |

In the person's words: a sentence about young children is never shown as a sentence about all children, and a symptom the paper only suspects is never shown as one the paper confirms.

## How it works

- `check_phrases(sentence, quotes)`, ported from the design's script: every two-word quote phrase in which one word is in the sentence and the other is not, the missing word four characters or longer (`PAIR_MISSING_WORD_MIN_CHARS`, the one knob, no word list). Pure; it reads at most `MAX_SENTENCE_CHARS` of the sentence and `MAX_QUOTE_CHARS` of each quote, the text Jev is shown.
- `build_pair_calls(sent)` packs the proposed pairs of the sentences the item call carries into PAIR blocks (phrase, quote, sentence, each a JSON string), numbered from 1 in each call, questions keyed `pair_<item>_<k>`. At most 30 questions (`MAX_BATCH_QUESTIONS`) and 30,000 characters (`JEV_STATE_MAX_CHARS`) a call, at most 4 calls (`MAX_PAIR_CALLS`).
- The question text is `PERPAIR_INSTRUCTIONS` and `PERPAIR_CRITERIA`, copied verbatim from the script the measurement ran, each under the client's 1,000-character cap.
- `_ask_jev` sends the item call, unchanged, and the pair calls in one `asyncio.gather`. A sentence is approved only when its item answer approves it and every one of its pair answers is a "no" that `_jev_approves` (Jev's own probability for "no" strictly above "yes"). A sentence with no proposed pair needs only its item answer, in exactly one call as before.
- Any failed, late, malformed or cost-capped call, item or pair, approves nothing in that check, and the guard tier is never asked. A reply with a pair key missing, an extra key or an answer outside yes and no is unreadable (`items_vetoed_by_pairs`, as strict as `approved_keys_from_jev`).
- An info log line per check states the pair questions, the calls, how many sentences a pair held back and how many were not asked. It carries counts only, never sentence text.
- The guard path, the three exact checks, the cite-or-refuse gate and `core/graph.py` are untouched.

## Choices made, with the alternatives

| Choice | Alternatives considered | Why |
|---|---|---|
| At most 4 pair calls a check (120 pairs, about 20 sentences at the measured 5.8 pairs a sentence) | No cap, which could reach 25 calls for 30 long sentences; 2 or 3 calls | Live checks carry 4 to 8 sentences: the offline run at 8 sentences a check needed 23 to 75 pairs, 1 to 3 calls, and never reached the cap. Four keeps the worst check at five concurrent calls and about $0.003 |
| A sentence whose pairs do not all fit is not asked and not approved; the next sentence that fits is still asked | Stop at the first sentence that does not fit, as `build_jev_state` does; ask part of a sentence's pairs | Half a sentence's pairs cannot approve it, so asking them spends money for nothing. Skipping rather than stopping shows the reader more sentences at no extra cost |
| Every call is cap-checked before any is sent, each counting the estimates of the calls checked before it | Check each call against the cap alone, as if the others were not in flight | None of the concurrent calls is charged until it returns, so checking each alone would let a check pass the per-query cap. Cost: a query within about $0.006 to $0.015 of its cap now approves nothing where before it needed only $0.003 of room |
| `asyncio.gather(..., return_exceptions=True)`, then the first failure raised, item call first | Plain `gather`, which raises at the first failure | Plain `gather` leaves the other calls running unawaited, so a call that came back after the failure would never be charged. The wait is bounded by the same 3-second Jev limit either way |
| The QUOTE in a PAIR block is the quote the phrase was first found in | The script's `quote_of`, a substring search over every quote with the first quote as fallback | The same quote in every case of the labelled set, without a fallback that could show the wrong quote |
| The item call's state, questions and parser are unchanged | Put the pair questions in the item call | The measurement asked them in separate calls; mixing questions in one call is known to move Jev's verdicts |

## Tests

New file `tests/system_03_search_agent/synthesis/test_sentence_pair_check.py` (36 tests). Each was turned red by mutating one property of the code and restored; the mutation runner was a scratch script, not committed.

| Test | What it proves | Mutation that turned it red |
|---|---|---|
| `test_every_young_children_sentence_gets_its_young_children_pair` (9 cases) | All 9 "young children" sentences of the labelled set get the pair | Propose only a missing word after a shared one (9 red); raise the knob from 4 to 6 (9 red) |
| `test_every_dropped_hedge_sentence_gets_its_symptoms_potentially_pair` (3 cases) | All 3 dropped-hedge sentences get the pair | Propose only a missing word before a shared one (3 red) |
| `test_a_sentence_sharing_no_word_with_its_quotes_gets_no_pair` | No shared word, no pair | Propose phrases where neither word is shared |
| `test_check_phrases_reads_only_the_bounded_text` | Text past `MAX_QUOTE_CHARS` proposes nothing | Drop the quote bound |
| `test_a_pair_yes_holds_back_a_sentence_the_item_question_approved` | A pair "yes" rejects an item-approved sentence; a sentence with no pair beside it stays approved | Ignore the pair verdicts |
| `test_every_pair_no_keeps_the_item_approval` | Populate check for the test above | (control) |
| `test_a_pair_no_at_even_odds_holds_the_sentence_back_too` | Through the real client, a pair "no" at 0.5 against 0.5 vetoes | Read only the pick, not the probabilities; ignore the pair verdicts |
| `test_an_item_rejection_is_never_overturned_by_its_pairs` | Item "yes", every pair "no": not approved | Let a sentence's pairs approve it |
| `test_a_sentence_with_no_pair_is_decided_by_its_item_answer_in_one_call` (2 cases) | No pair: one call, today's state, the item answer decides | Treat a sentence with no pair as not asked; give it a pair call anyway |
| `test_a_failed_pair_call_approves_nothing` (4 cases) | Timeout, HTTP error, malformed reply or a bug in a pair call approves nothing, the guard is not asked | Skip a failed pair call instead of failing the check (4 red) |
| `test_a_late_pair_reply_approves_nothing` | Through the real client, an on-time item reply and a late pair reply approve nothing | The same mutation |
| `test_an_unreadable_pair_verdict_raises` (3 cases) | A missing pair key, an extra key, an answer outside yes and no | (parser strictness, as for the item call) |
| `test_a_query_too_close_to_its_cap_for_every_call_approves_nothing` | Room for the item call alone is not enough; nothing is sent | Cap-check each call alone |
| `test_room_for_every_call_sends_them_all` | Populate check for the test above | (control) |
| `test_the_pair_calls_run_at_the_same_time_as_the_item_call` | One wait, not two in a row | Await the calls one after another |
| `test_every_call_that_came_back_is_charged_even_when_another_failed` | A failed pair call is charged its billed cost and the slower item call is still charged | Plain `gather` |
| `test_the_pair_questions_are_the_measured_ones_and_fit_the_endpoints_bounds` | Keys, verbatim text, per-call numbering, the client's own bounds, a second call past 30 pairs | (bounds) |
| `test_a_sentence_whose_pairs_do_not_fit_is_not_asked_and_the_next_one_is` | Whole sentences only, at most `MAX_PAIR_CALLS` calls | Remove the undo, so a sentence is half asked |
| `test_a_sentence_whose_pairs_were_not_asked_is_not_approved` | With no room for pairs, the sentence with pairs is not shown | Approve sentences that were not asked |
| `test_the_pair_data_travels_only_in_the_state` | Sentence and quote text never enter the question text | (data as data) |

Existing tests changed, because every Jev-mode check with a pair now makes a second call:

- `test_sentence_check.py`: the `_FakeJev` and HTTP fakes answer pair calls "no" by default; five assertions now count the item call alone or add the pair call's charge. No assertion was weakened: each still checks what it checked, plus the pair call.
- `tests/system_03_search_agent/harness/test_jev_followup_costs.py`, `test_the_sentence_check_charges_the_ceiling`: its placeholder items carry no sentence, so it now also stubs `build_pair_calls` to no calls. It tests the item call's charge, as before.

## Offline result through the shipped code

Driver: `raw/offline_shipped_path.py`, output `raw/offline_shipped_path.jsonl`. It calls `check_reworded_sentences` in Jev mode on `2026-10-05_qualifier_check/raw/eval_set.jsonl`, with only `call_jev_batch` wrapped to record each call. One run.

How it differs from the measurement's script: checks of 8 sentences (the top of the live 4 to 8) in file order, each with its own item call and pair calls, instead of 30 pairs a call on their own and item verdicts taken from an earlier run of 15 items a call. So 26 checks and 81 calls (26 item, 55 pair), not about 40; the same 1,194 pairs were proposed. The "item question alone" column is this run's own item answers.

| Label | Items | Item question alone approves | Shipped check approves | Target |
|---|---|---|---|---|
| A, says more than its record | 18 | 8 | 0 | 0 |
| A, dropped qualifier ("young children") | 9 | 7 | 0 | 0 |
| A, dropped hedge ("potentially") | 3 | 1 | 0 | 0 |
| F, faithful rewording | 144 | 128 | 121 | as many as possible |
| R, beyond the widened quote | 20 | 2 | 1 | 0 |
| B, borderline | 23 | 15 | 10 | reported only |

- Dropped qualifier and dropped hedge items approved: 0 of 12. The "young children" pair came back 0.04 to 0.41 for "no", the "symptoms potentially" pair 0.06 to 0.19.
- The faithful hedged rewordings that keep the hedge ("may be related to GERD") passed the same pair, 0.53 to 0.81.
- The added population item (`d-gerd1-c1-i2`, "in adults") was rejected by the item question in this run, not by a pair; the pair check cannot see an added word, as the measurement says.
- The one R approved, `d-gerd2-c2-i4`, was approved by the item question too; its extra words are a setting and "management approaches" from the record outside the quote, which no pair covers.
- B by sub-label: stronger_degree 6 of 10, weaker_degree 2 of 2, added_gloss 1 of 3, relabelled 1 of 5, narrowed 0 of 2, reframed 0 of 1.

The 7 faithful rewordings the pair check held back, each approved by the item question:

| Item | Pair flagged, probability of "no" | What the sentence leaves out |
|---|---|---|
| `w-gp3-c1-i6` | "the outpatient" 0.48 | the outpatient setting |
| `w-cp2-c2-i4` | "the outpatient" 0.33 | the outpatient setting |
| `w-gp5-c1-i5` | "from abnormal" 0.34, "abnormal transient" 0.16, "transient relaxations" 0.15 | "abnormal transient" relaxations |
| `d-gerd3-c1-i5` | "from abnormal" 0.50 | "abnormal", at even odds |
| `w-gr4-c1-i3` | "from abnormal" 0.45 | "abnormal" |
| `w-md2-c2-i3` | "contributes to" 0.47, "to certain" 0.10, "certain clinical" 0.10 | "certain" clinical features |
| `w-gp4-c1-i3` | "affects quality" 0.47 | an "affects quality" phrase |

Four of these were not held back in either measurement run (`w-cp2-c2-i4`, `d-gerd3-c1-i5`, `w-gr4-c1-i3`, `w-gp4-c1-i3`), and four the measurement held back passed here (`w-cp3-c2-i4`, `d-med2-c2-i4`, `w-gp1-c1-i5`, `w-cr4-c2-i5`, each approved by its item question and every pair). Most flagged pairs sit at 0.33 to 0.50, so which faithful sentences fall is close to a coin flip, as the measurement found; the count, 6 or 7 of 144, held.

## Added time and spend

- A check's wall time was 303 to 663 ms; its item call alone took 230 to 662 ms. The pair calls added 1 to 302 ms a check, median 104 ms, because they run at the same time as the item call.
- Pair call latency: 241 to 629 ms each, 1 to 30 pairs a call. The measurement saw 293 to 1,293 ms a 30-pair call.
- An answer has at most two checks (first draft and repair), so the added time is at most about 0.6 seconds an answer at the slowest seen, within the 20-second line.
- Each check now makes 1 to 5 calls instead of 1. A transport failure on any of them approves nothing in that check, so such a failure becomes 2 to 3 times as likely for a typical answer. None failed in this run.
- Spend: $0.0289 for the one run (item calls $0.0033, pair calls $0.0256), about $0.0011 a check. No other model call was made. Total for this card: $0.029 of the $0.10 allowed.

## Gates

Run from the worktree with the main checkout's virtual environment first on PATH, exactly as CI runs them.

| Gate | Result |
|---|---|
| `gate02_import_order.sh` (isort) | Pass |
| `gate03_lint.sh` (ruff, whole repository) | Pass, "All checks passed!" |
| `gate04_unit_suite.sh` (whole suite) | Pass: 6,963 passed, 143 skipped, 24 deselected, 1 xfailed, 0 failed. The 6 Postgres tests passed on this run. Load average was 5.5 at the start and 3.1 at the end |

## What is not covered

- No live answer was run. The lead runs five or more live runs a question after review, counting sentences shown, "young children" shown as "children" (must be 0) and the hedged primary-care sentence shown.
- One offline run, not two, at 8 sentences a check. The 4-sentence end of the live range was not run.
- The pair check cannot catch an added word ("in adults") or a replaced one ("occasionally" for "in rare instances"); those remain the item question's job, as the measurement says.
- The rule text in `.claude/rules/production-standards.md`, "all sentences of one answer in one call", still holds for the item call, but a check now also makes up to four pair calls. The rule is outside this card's fence; the lead may want to add a line.
- A query near its per-query cost cap now needs room for every call of the check, not one; how often live queries come that close was not measured.
