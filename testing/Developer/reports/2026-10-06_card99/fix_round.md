# Card 99 fix round

One fix-and-verify round on branch `fix/card99-pair-check`, 2026-10-06, after the judge and adversary reports. Every fix is one commit with a test that goes red when its one property is mutated. Nothing is pushed.

## Table of contents

- [Commits](#commits)
- [Findings fixed](#findings-fixed)
- [Gates and tests](#gates-and-tests)
- [Offline table](#offline-table)
- [Spend](#spend)
- [Not in scope](#not-in-scope)

## Commits

| Commit | Finding |
|---|---|
| 76059f23 | Reviewer reports and raw probes added; J-99-01 lint fix |
| bd5f0da0 | A-99-01, blocking |
| 2c525acc | J-99-04 |
| feb941ef | A-99-05 and J-99-07 |
| 2fd32b3a | A-99-07 |
| ef9cfaeb | A-99-03 |
| dcb3da64 | J-99-05, the sixth fix |

## Findings fixed

### J-99-01: lint in the reviewers' scripts

- Gate03 failed on more than the one script by the time I ran it: 20 errors across the adversary's probes. I applied ruff's own fixes to the whole folder and put a line-level noqa on the 3 blind-exception and blocking-open lines. Behaviour is unchanged; every script still compiles. The brief named only `replay_live_pairs.py`, so this is wider than asked, and it is lint only.
- The reports `judge.md` and `adversary.md` are unchanged.

### A-99-01: a repeated limit phrase asked against the first quote only

- Change: `_proposed_pairs` dedups on (phrase, quote) instead of phrase. A phrase found in two different quotes is now asked once against each. The same phrase twice in one quote, or in two equal quotes, is still one pair.
- Choice, with the alternative: "ask against the quote the sentence actually rewords" needs code to decide which quote that is, which is a model's call and would add a word or overlap rule. Asking against every quote that holds the phrase needs no decision, and a pair can only veto, so the extra pair can only hold a sentence back. Cost: a few more pair questions when quotes repeat a phrase (4 of 304 live items had the shape).
- In the person's words: a sentence that turns the paper's "young children" into "children" is shown to the checker against the quote that says it, even when an earlier quote of the same record also says "young children".
- Reproduced first, offline (the adversary's case): every proposed pair carried the decoy quote, and the source quote appeared in none.
- Fixed, offline: the pairs "in young" and "young children" now each appear against both quotes.
- Fixed, live (`raw/fix_round/live_decoy.py`, 2 billed calls, about $0.0002): the decoy case through `check_reworded_sentences` was not approved. The two pairs shown with the source quote answered "yes" at 0.70 and held the sentence back, while the pairs shown with the decoy quote still answered "no" at 0.68 to 0.95. Before the fix the adversary saw approval in 3 of 3 runs. One run, so it shows the mechanism, not a rate.
- Tests: `test_a_phrase_in_two_quotes_is_asked_against_each_quote`, `test_the_same_phrase_twice_in_one_quote_or_in_two_equal_quotes_is_one_pair`, `test_a_dropped_young_is_held_back_when_only_the_second_quote_makes_it_a_yes`.
- Mutation: the dedup test went back to phrase-only. Two tests went red (the first and the third); restored, green.

### J-99-04: which sentence a pair veto lands on

- Test only: `test_a_pair_veto_lands_on_the_sentence_the_pair_belongs_to`. The sentence with pairs is item 2, a pair "yes" must hold back item 2 and leave item 1 shown, and every pair key must map to item 2.
- Mutation: `items[key] = item` changed to `items[key] = 1`. The test went red, restored, green. The old suite passed this mutation.

### A-99-05 and J-99-07: the cap reserves what a call can be charged

- Change: one cap check before any call is sent, reserving the calls times `MAX_JEV_COST_USD` read from the client (imported, not copied). `check_per_query_cap` adds the guard estimate itself, so the cap handed to it is lowered by (calls times ceiling) minus that estimate; the check passes exactly when spent plus calls times ceiling fits the cap. This replaces the loop that reserved the $0.003 estimate a call.
- The arithmetic, as the test shows it at a $0.10 cap: a check of 2 calls is sent when $0.079 is spent (worst case ends at $0.099) and refused at $0.081; a check of 3 calls is sent at $0.069 and refused at $0.071. A query that cannot be taken past its cap by a check that is sent.
- Cost to the person: a check now needs up to $0.05 of headroom with 5 calls ($0.01 a call) where it needed $0.015. Live answers cost $0.008 to $0.019 against the $0.10 starter cap, so a query loses its approvals to this only when it is already past about $0.05 to $0.09 (depending on its calls). A check with no pair also needs $0.01 now, where it needed $0.003. I did not read the deployed cap value.
- Tests: `test_a_check_that_is_sent_can_never_take_the_query_past_its_cap` (two cases), and the two older cap tests now use the ceiling.
- Mutation: reserving the guard estimate per call again. Three tests went red (the new two cases and the older refusal test); restored, green.

### A-99-07: the log counts what the pair check cost

- Change: "held back by a pair" is the number of sentences the item question approved and a pair then vetoed. The line is `... N approved sentences held back by a pair, M sentences not asked for want of room`.
- Test: `test_the_log_counts_only_sentences_the_item_question_approved_and_a_pair_held_back`: two sentences, every pair "yes", the item question rejects the first and approves the second: the line says 1, not 2.
- Mutation: count every vetoed sentence. Red; restored, green.

### A-99-03: sentences the call cap left unasked

- The line already carried a not-asked count after the build, so the code change is the wording ("not asked for want of room") and the separation from the held-back count. The count covers every sentence the cap left without its pairs, whether the item question approved it or not. One line, counts only, no text. The cap is unchanged (`MAX_PAIR_CALLS` is 4).
- Test: `test_the_log_counts_the_sentences_the_call_cap_left_unasked_and_no_text`, with the cap set to 0 calls: the line says 1 not asked and names no sentence word.
- Mutation: the logged not-asked count forced to 0. Red; restored, green.
- The A-99-07 and A-99-03 source change is one hunk, so it sits in the A-99-07 commit; the A-99-03 commit carries its test.

### J-99-05: U+2028, checked and fixed

- Check: yes, it can forge. `json.dumps(text, ensure_ascii=False)` leaves U+2028 as is, and the output split by `splitlines()` gave 3 lines for one string carrying 2 separators, so a sentence could lay out a fake `PAIR 9` line for a reader that splits that way. U+2029 and U+0085 split the same way.
- Change: a helper `_json_text` writes those three characters as JSON escapes, used by both the item block and the pair block. Still valid JSON, same text.
- Test: `test_a_unicode_line_break_in_a_sentence_or_quote_cannot_lay_out_a_fake_block`, for each of the three characters, in both blocks: the character is absent, `splitlines()` equals a split on the code's own newline, and exactly one block header appears.
- Mutation: the escaping loop removed. All three cases red; restored, green.
- Not tested: whether Jev reads these characters as a line break. The fix removes the question.

## Gates and tests

| Run | Result |
|---|---|
| `tests/system_03_search_agent/synthesis/` and `harness/test_jev_followup_costs.py` | 614 passed, 10 skipped, 1 xfailed |
| Gate02, import order | passed |
| Gate03, lint (whole repository) | passed |
| Gate04, whole unit suite (load was 16; it ran 5 min 47 s) | 6974 passed, 143 skipped, 24 deselected, 1 xfailed |

I did not run `ruff format` over the files, because it reformats code this card did not touch.

## Offline table

Rerun of `raw/offline_shipped_path.py` once, through the shipped code after all fixes: 26 checks, 81 calls, no check failed, nothing left unasked, 265 to 1,093 ms a check, median added time 82 ms. The first run's output is kept as `raw/offline_shipped_path_build.jsonl`, the rerun as `raw/offline_shipped_path.jsonl`.

| Label | Items | Item question alone approves | Shipped check approves, before | Shipped check approves, now |
|---|---|---|---|---|
| A, says more than its record | 18 | 8 | 0 | 0 |
| A, dropped qualifier | 9 | 7 | 0 | 0 |
| A, dropped hedge | 3 | 1 | 0 | 0 |
| F, faithful rewording | 144 | 128 | 121 | 121 |
| R, beyond the widened quote | 20 | 2 | 1 | 1 |
| B, borderline | 23 | 15 before, 16 now | 10 | 11 |

The labelled set has one item of the repeated-phrase shape, so this table cannot show A-99-01; the offline and live cases above do. The B row moves by one because the item question's own answer moved by one between runs.

## Spend

- Live decoy check: 2 billed calls, about $0.0002.
- Offline driver rerun: 81 billed calls, $0.0289.
- Total about $0.029, under the $0.06 allowed.

## Not in scope

| Finding | Why |
|---|---|
| A-99-02, hedge words under 4 letters | The item question catches them today (the adversary's live check of "may", "a few", "In men", "Up to"); lowering the knob needs a new measurement of faithful loss |
| A-99-04, a partial-list sentence held back | The intended conservative behaviour: a sentence lost, never a wider claim |
| A-99-06, a late call empties the check | The fail-closed rule the owner set |
| J-99-02 | The same coverage limit as A-99-02 |
| J-99-03 | Rule text in `.claude/rules/production-standards.md` and the `core/graph.py` docstring, the lead's, outside this fence |
| J-99-06 | Fail closed by the owner's rule; the lead's live runs should count checks that approved nothing because of a pair-call failure |
