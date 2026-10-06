# Card 99 fresh verifier report

Fresh-context verification of card 99's fix round on branch `fix/card99-pair-check`, fix commits bd5f0da0, 2c525acc, feb941ef, 2fd32b3a, ef9cfaeb, dcb3da64. Written as I go; findings are appended the moment they are established.

## Table of contents

- [Findings log](#findings-log)
- [Gates and tests](#gates-and-tests)
- [Verdict](#verdict)
- [What I did not cover](#what-i-did-not-cover)

## Findings log

### V-99-01: feb941ef's headroom costs no live answer its sentences at the documented caps, but would at a cap under about $0.056, and the deployed cap is not visible to me
- Severity: non-blocking, unsure (conditional on a value I cannot read)
- Regression of: A-99-05 and J-99-07's fix (feb941ef), only if the deployed cap is below about $0.056
- What: `_ask_jev` (`src/system_03_search_agent/synthesis/sentence_check.py:640-647`) now refuses the whole check unless spent + calls x $0.01 fits `PER_QUERY_COST_CAP_USD`. The cap has no code default: `cost_control.per_query_cost_cap_usd()` (`harness/cost_control.py:231-233`) raises when the variable is unset, `env.example:151` ships it empty, the spec's starter value is $0.10 (`requirements/Technical_specification.md:1913,2817,3146`), `tracker/phase_4.12.md:135` records $0.10 as provisioned, and `docs/build/Handoff_history.md:242` planned $0.25 on develop at phase 8.7's merge (I found no record that it was set). CI runs with $1.00 (`.github/workflows/ci.yml:126,277`). The Railway value itself I did not and cannot read.
- Reproduction: scratch probe `p2_headroom.py` (outside the repository) replays all 56 CHECK_IN records of `2026-10-05_wave3/sentence_check_raw/` (gp, md plain language; gr, cr Researcher; cm, cp plain) through the fixed `build_jev_state` and `build_pair_calls`, takes the run's whole `total_cost_usd` as an upper bound on spend at the check, and asks the lowest cap that still sends it. Output: calls a check 2 (28 checks), 3 (27), 4 (1, gp4); highest needed cap after the fix $0.0555 (gp4, plain), highest Researcher $0.0473 (gr4). Refused checks out of 56, after vs before: cap $0.02 56 vs 47; $0.03 54 vs 0; $0.05 1 vs 0; $0.06 0 vs 0; $0.10 0 vs 0; $0.25 0 vs 0.
- Wider: the highest per-query `total_cost_usd` in any report under `testing/` outside the writer bench is $0.0274 (`2026-09-14_answer_quality/before_gck_researcher.json`, Researcher); even with 5 calls ($0.05) that needs $0.077, under $0.10.
- Plain answer: at $0.10 or $0.25, no answer on develop today loses its written sentences to this, at Researcher depth or plain language. At a deployed cap of $0.05 or less it would, mostly plain language checks with 3 to 4 calls. Not blocking on the evidence I have; the lead should confirm the Railway value is at least $0.06 before merging.
- Also: the fix round's offline rerun pins `PER_QUERY_COST_CAP_USD=1.0` (`raw/offline_shipped_path.py:47`), so its "no check failed" cannot speak to this.
- NOT FIXED

### Check 3 result: A-99-01's extra pairs leave sentences unasked no more often (no finding)
- Probe `p3_packing.py` (scratch), the module's own `build_jev_state` and `build_pair_calls`, with `_proposed_pairs` swapped for a phrase-only copy for "before".
- Wave 3 live, 56 checks, 304 candidates as recorded: 3 checks change (cm4, cp3, md2), each by one pair; pairs 1,750 to 1,753; calls a check unchanged (max 3 pair calls); not asked 0 before and after.
- The same 304 candidates cut into checks of 8, 10, 12, 15, 20, 30: not asked before vs after 0/0, 0/0, 0/0, 3/3, 24/24, 74/74. Identical at every size.
- Labelled set, 205 items: one item changes pairs (`w-cp3-c2-i5`, +1 pair); calls and not asked identical in checks of 8, 12 and 30.
- So the A-99-01 fix does not push checks past `MAX_PAIR_CALLS` on realistic answers. A-99-03's cap loss above 12 sentences a check is unchanged and pre-existing.

### A-99-01: verified fixed
- Code: `_proposed_pairs` dedups on `(phrase, bounded quote)` (`sentence_check.py:466-477`).
- Probe `p1_decoy.py` (scratch, no network): the adversary's Q1 decoy, Q2 source and sentence through `check_reworded_sentences` in Jev mode, `call_jev_batch` replaced by a mock that answers the item "no" at 0.67 and each pair by the quote its PAIR block actually shows, using the live run's numbers (Q1: "in young" p_no 0.62, "young children" 0.54; Q2: 0.28, 0.31; other pairs 0.9).
  - Fixed code: decoy first (Q1, Q2) approved=False; the pairs asked include `pair_1_7 in young Q2 0.28` and `pair_1_8 young children Q2 0.31`. Source only: False. Source first: False.
  - Control, mock answers every pair "no" at 0.9: all three approved=True, so the probe is not vacuous.
  - Mutation, dedup back to phrase only (`sed` on line 475): decoy first approved=True with the same mock, the adversary's live result; two tests red (`test_a_phrase_in_two_quotes_is_asked_against_each_quote`, `test_a_dropped_young_is_held_back_when_only_the_second_quote_makes_it_a_yes`). Restored with `git checkout --`, `git status --short` shows only this report.

### J-99-04: verified fixed (test gap closed)
- Test: `test_a_pair_veto_lands_on_the_sentence_the_pair_belongs_to` (`tests/system_03_search_agent/synthesis/test_sentence_pair_check.py`, end of the J-99-04 section): sentence with pairs at item 2, a pair "yes", asserts approved is exactly item 1's key and every pair key maps to item 2.
- Mutation 1, the judge's: `items[key] = item` to `items[key] = 1` (`sentence_check.py:573`). Red: this test and the A-99-07 log test (2 failed, 588 passed). Restored, clean.
- Mutation 2, mine: a veto lands on the lowest item of the same call (`vetoed.add(item)` at `:600` replaced). The J-99-04 test stays green, because its call carries only item 2's pairs; the A-99-07 log test goes red (its call carries two sentences' pairs and it asserts the approved set). So a cross-sentence mis-mapping inside one call is caught, but by a test written for another property. Not filed as a finding. Restored, clean.

### A-99-05 and J-99-07: verified fixed (with V-99-01's condition on the deployed cap)
- Code: one `check_per_query_cap` call with the cap lowered by `calls * MAX_JEV_COST_USD - estimate` (`sentence_check.py:640-647`); `check_per_query_cap` adds the estimate back (`harness/cost_control.py:412-416`), so it refuses exactly when spent + calls x $0.01 > cap. `MAX_JEV_COST_USD` is imported from the client (`:95`), and both a successful reply's cost (`jev_client.py:566`, `le=MAX_JEV_COST_USD`) and an unusable reply's billed cost are bounded by it.
- Probe `p4_cap.py` (scratch): every call raises `JevCallError(malformed_reply, billed_cost_usd=0.01)`, cap $0.10, spend before the check swept $0.000 to $0.100 in $0.001 steps for checks of 1, 2, 3 and 5 calls (606 runs). Worst overshoot of the cap: 0. Runs where "sent" disagreed with spent + calls x $0.01 <= cap: 0. Highest spend still sent: $0.09 (1 call), $0.08 (2), $0.07 (3), $0.05 (5). The adversary's $0.085 + 5 calls now refuses; before the fix it ended at $0.135.
- Mutation, the old loop reserving the $0.003 estimate a call: 3 tests red (`test_a_query_too_close_to_its_cap_for_every_call_approves_nothing` and both cases of `test_a_check_that_is_sent_can_never_take_the_query_past_its_cap`). Restored, clean.
- The cost of the fix to a reader: see V-99-01.

### A-99-07: verified fixed
- Code: the held-back count is `len(approved & {keys of vetoed items})` (`sentence_check.py:698`); what is returned is unchanged in substance (`held_keys = vetoed | not_asked`, the same set as the old `held_back`).
- Probe `p5_log.py` (scratch): 300 random checks of 1 to 30 live wave 3 sentences, random item and pair verdicts, mocked Jev; an independent oracle computes the approved set and both counts. 0 mismatches on the fixed code. With the log count mutated to `len(vetoed)`: 191 of 300 mismatch, so the probe sees it.
- Mutation in the suite, the same `len(vetoed)`: `test_the_log_counts_only_sentences_the_item_question_approved_and_a_pair_held_back` red (1 failed). Restored, clean.

### A-99-03: verified as the fix round scoped it (log visibility only; the cap is unchanged)
- Code: the line now reads "N approved sentences held back by a pair, M sentences not asked for want of room" (`sentence_check.py:690-700`); M is `len(not_asked)`, counts only, no text.
- Probe `p5_log.py`: the not-asked count matched `build_pair_calls`' own not-asked set on all 300 random checks; with M forced to 0, 126 of 300 mismatch.
- Mutation in the suite, M forced to 0: `test_the_log_counts_the_sentences_the_call_cap_left_unasked_and_no_text` red. Restored, clean.
- What this does not do: a sentence past the call cap is still unshown with no note to the reader; the fix makes it visible to the operator only. Unchanged by A-99-01 (check 3 above).

### J-99-05: verified fixed, both builders, no change for normal text
- Code: `_json_text` (`sentence_check.py:168-180`) escapes U+2028, U+2029 and U+0085 after `json.dumps(..., ensure_ascii=False)`; used for SENTENCE and every QUOTE in `_item_block` (`:183-193`) and for PHRASE, QUOTE and SENTENCE in `_pair_block` (`:506-513`). The only `json.dumps` left in the module is inside `_json_text` itself (and a comment). `build_sentence_check_messages` (guard mode) reads `_item_block`, so it is covered too.
- Probe `p6_escape.py` (scratch):
  - Every code point `str.splitlines()` treats as a line end: 0x0a, 0x0b, 0x0c, 0x0d, 0x1c, 0x1d, 0x1e, 0x85, 0x2028, 0x2029. Those `json.dumps(ensure_ascii=False)` leaves raw: exactly 0x85, 0x2028, 0x2029, the three `_LINE_BREAKS` escapes. The set is complete.
  - 6,132 texts (every wave 3 live sentence and quote, the labelled set, and 5,000 random strings mixing the breaks, quotes, backslashes and control characters): normal text changed 0, `json.loads` round trip failures 0, line breaks left 0.
  - All 56 wave 3 live item states are byte-identical to the pre-fix construction, so Jev reads exactly what it read before on real answers.
  - A forged sentence and quote carrying all three characters: no raw break in the item state, the pair state or the guard-mode messages.
- Mutations: the escaping loop removed: 3 tests red (all three characters). Only the pair QUOTE field reverted to `json.dumps`: the same 3 red. Restored, clean.
- Not tested, as the fix round says: whether Jev itself treats these characters as a line break; the fix removes the question.

### Check 5: the lint edits to the adversary's raw scripts changed no behaviour a report relies on
- The pre-lint scripts were never committed (untracked when the judge saw them, linted before 76059f23), and the `__pycache__` files carry the post-lint source stamps, so a text diff is impossible. I compared behaviour instead.
- Method: `git archive 76059f23 src` into the scratch folder (the code the adversary probed, before the fix commits), then ran each offline script from the worktree root with that `src` first on `PYTHONPATH`, and compared stdout with the `.txt` the adversary recorded before the lint.
- Result: `fuzz_packing`, `probe_blast_radius`, `probe_cap_overrun`, `probe_cap_packing`, `probe_check_phrases`, `probe_dedup_context`, `replay_live_pairs`, `scan_short_limits`: byte-identical. `probe_log_count`: identical once stderr is merged (its one log line goes to stderr; the adversary captured both streams).
- `probe_cap_overrun` reproducing "$0.080 ... spent after $0.130" confirms the run really used the pre-fix code.
- Not covered: `live_attacks.py` makes live calls, so it was not run; it compiles, and its only visible lint marker is `# noqa: ASYNC230` on an output `open`.

### V-99-02: the `MAX_PAIR_CALLS` comment still claims "about 20 sentences", which the live data contradicts
- Severity: non-blocking, minor (a comment, not behaviour; not inside a fix commit, left untouched by the A-99-03 fix)
- What: `sentence_check.py:409-410` says "Four calls carry 120 pairs, about 20 sentences at the measured mean". Review_rounds.md treats a comment that claims a property as a claim to be tested.
- Reproduction: `p3_packing.py`, the 304 wave 3 live candidates cut into checks of 15: 3 sentences not asked in 3 checks; of 20: 24 not asked, 7 of 16 checks lose at least one (worst 7). The adversary's A-99-03 numbers agree.
- Why it matters: the next person sizing `MAX_PAIR_CALLS` for Researcher depth reads 20 where the live figure is about 12.
- NOT FIXED

- Correction to V-99-02's location: the comment is at `sentence_check.py:407-408`, not 409-410.

## Gates and tests

| Run | Result |
|---|---|
| `pytest tests/system_03_search_agent/synthesis/ tests/system_03_search_agent/harness/test_jev_followup_costs.py` | 614 passed, 10 skipped, 1 xfailed |
| `bash .github/gates/gate03_lint.sh` with the venv first on `PATH` | All checks passed |
| `git status --short` after every mutation and probe | only this report, untracked |

Mutations run, each one property, each restored with `git checkout --`:

| Mutation | Tests red |
|---|---|
| A-99-01 dedup on phrase only | 2 |
| J-99-04 `items[key] = 1` | 2 |
| Veto lands on the lowest item of its call (mine) | 1, the A-99-07 test only |
| A-99-05 reserve the $0.003 estimate a call | 3 |
| A-99-07 count every vetoed sentence | 1 |
| A-99-03 not-asked count forced to 0 | 1 |
| J-99-05 escaping loop removed | 3 |
| J-99-05 pair QUOTE back to plain `json.dumps` (mine) | 3 |

## Verdict

PASS against card 99's goal contract. No blocking finding, and no finding inside a fix commit of this round unless the deployed cap is below about $0.056 (V-99-01).

| Finding | Verdict |
|---|---|
| A-99-01 | Fixed. Offline decoy with Jev mocked to the live answers: held back; with the fix mutated away: approved, as live |
| J-99-04 | Fixed (test added, goes red on the judge's mutation) |
| A-99-05 and J-99-07 | Fixed. The total never passes the cap across a 606-run sweep; cost to readers in V-99-01 |
| A-99-07 | Fixed. 300-check fuzz against an independent oracle, 0 mismatches |
| A-99-03 | Fixed as scoped: the operator can now see unasked sentences; the reader still cannot |
| J-99-05 | Fixed in both builders; normal text byte-identical on all 56 live states |

Question 2, plainly: at the $0.10 starter cap, or the $0.25 planned for develop, no answer that shows written sentences on develop today would lose them to the new headroom, at Researcher depth or plain language. The highest headroom any of the 56 live checks needs is $0.0555 (plain language), $0.0473 at Researcher depth. Below a deployed cap of about $0.056 the fix would cost answers their sentences, which is why V-99-01 asks the lead to confirm the Railway value.

Verified with my own probes: the A-99-01 decoy (fixed, control, mutated), the cap arithmetic and its no-overshoot guarantee, the headroom against live costs, the A-99-01 packing effect on live and labelled data, the log counts, the escaping set and its no-change on normal text, the lint edits' behaviour via pre-fix reruns, and every mutation above.

Only read, not probed: the deployed `PER_QUERY_COST_CAP_USD` (not visible to me; documented values only), whether the phase 8.7 plan to set $0.25 was carried out, the 0 of 12 and 7 of 144 offline rates, and the fix round's single live decoy run (I read its record: the two source-quote pairs answered "yes" at 0.70, consistent with the report).

## What I did not cover

- No live model call, as briefed.
- The Railway value of `PER_QUERY_COST_CAP_USD`.
- Spend at the moment of each check is bounded above by the run's total, not measured; costs of question classes other than the GERD, Mediterranean, BRCA1 and GCK runs on record.
- `live_attacks.py` behaviour after the lint pass.
- Gate02, gate04 and the whole unit suite (not briefed).
- Whether anything else in the Write step spends concurrently with the sentence check, which the single pre-check could not see.
  - Partly checked since: both call sites are awaited directly in Write (`core/graph.py:12912` and `:13057`), not gathered with other model calls. I did not trace whether a background decision task started in an earlier step (`create_task` at `core/graph.py:1374`, `:3912` to `:3925`, `:6516`) can still be charging while the check runs.
