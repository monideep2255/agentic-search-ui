# Card 101 build round 5: a held copy takes its whole sentence

Builder, 2026-10-07, branch `fix/card101-copied-cuts` at bde1b65d (merged with develop 2182aff3). The final round, on the owner's decision of 2026-10-07: "Try dropping the whole sentence whenever a copied cut is held back." It fixes A4-101-03 to 07, J4-101-01, J4-101-02 and J4-101-08 from `judge_r4.md` and `adversary_r4.md`, and nothing else.

## Table of contents

- [Verdict](#verdict)
- [The change in the reader's words](#the-change-in-the-readers-words)
- [What changed](#what-changed)
- [Tests, red then green](#tests-red-then-green)
- [Mutations](#mutations)
- [Replay of the recorded drafts](#replay-of-the-recorded-drafts)
- [Live check](#live-check)
- [Choices for the lead to log](#choices-for-the-lead-to-log)
- [Gates](#gates)
- [Spend](#spend)
- [Still open](#still-open)

## Verdict

| Item | Findings | Status |
|---|---|---|
| A | A4-101-03, J4-101-01, J4-101-02: a held copy left part of its sentence on screen | Fixed: no part of the sentence shows |
| B | A4-101-04: the check approved text past 600 characters it never read | Fixed: such an item is not sent and counts as held |
| B | A4-101-07: a cut with no record sentences to show was sent with itself as its quote | Fixed: held, never sent |
| C | A4-101-05: the listing lost a row opening on ",", ";" or ":" | Fixed: shown exactly as develop |
| D | J4-101-08: an unexpected guard-tier failure escaped the check | Fixed: approves nothing |
| Replay | 168 recorded drafts, no, all and partial approvals | 0 sentences develop does not show; 0 drafts emptied |
| Live | 4 cases, 5 runs each, Jev mode and guard tier | Every run met its property; $0.0023 in all |

## The change in the reader's words

- When the check holds back any copied piece of a sentence, for any reason, you see none of that sentence. You never see "Ribavirin [1]." on its own, "In babies, ribavirin [1].", or "Azithromycin shortens the course of bronchiolitis in infants [1]." without the "only when a bacterial co-infection is confirmed by culture" the writer put after it.
- The check is never counted as approving words it was not shown. A sentence too long for the check to read whole, or a copied piece whose surrounding record sentences are too long to show it, is not shown.
- The record list shown when the writer's answer fails keeps every row it showed on develop, including one that opens on a comma or colon.
- If the checking model's call breaks in an unexpected way, you get the sentences code can vouch for on its own, never a failed answer.
- A sentence with no copied piece held back behaves exactly as on develop.

## What changed

| File | Change |
|---|---|
| `src/system_03_search_agent/synthesis/grounding.py` | A: in `run_grounding_pass`, any held copied clause (`held_for_check`) drops the whole sentence; round 4's extra middle-strip term is gone, since the new rule covers it. B: `record_sentence_run` returns the run of record sentences or None; `widen_to_record_sentences` keeps its fallback through it; `_copied_record_span` and `_copied_clause_candidate` return None for a cut with no run, and the caller holds that clause without sending an item. C: `_is_code_built_row` compares each piece with its leading separators removed, as it already did the segment |
| `src/system_03_search_agent/synthesis/sentence_check.py` | B: `_read_whole`; `check_reworded_sentences` sends only items whose sentence is within `MAX_SENTENCE_CHARS` and every quote within `MAX_QUOTE_CHARS`, in both modes, and asks no model when none is left. Counts are logged, never text |
| `src/system_03_search_agent/core/graph.py` | D: inside `_ground_with_sentence_check`, the guard-tier call (`_ask_guard_tier`) turns any exception other than the cost cap and `HarnessCallError` into `SentenceCheckUnreadable`, which the caller already catches. Cancellation still propagates |
| `tests/system_03_search_agent/synthesis/test_copied_cuts.py` | 9 new test functions, 23 new cases; `test_only_what_the_check_read_is_shown` now expects nothing when only the cut is approved; two docstrings updated |
| `tests/system_03_search_agent/synthesis/test_sentence_check.py` | 2 new test functions, 3 cases |
| `raw/build_r5/` | Red list, mutation script and output, replay script and counts, live script and rows |

## Tests, red then green

Each test was written first and run on the unchanged branch (bde1b65d): 23 cases failed, listed in `raw/build_r5/red_before.txt`. After the change all 202 cases of the four card 101 synthesis files pass. Reproductions are the reviewers' own where they gave one.

| Item | Test | Red before | Green after |
|---|---|---|---|
| A | `test_a_held_cut_shows_no_part_of_its_sentence` (A4-101-03 "Ribavirin [1]." and "In babies, ribavirin [1].") | 2 of 2 | Yes |
| A | `test_a_held_limit_never_leaves_the_sentence_without_it` (A4-101-03 azithromycin through `_ground_with_sentence_check`: holds it, unreadable, call failed, cost cap, budget 3.9 s) | 5 of 5 | Yes |
| A | `test_a_partial_verdict_shows_the_whole_sentence_or_nothing` (J4-101-01 BRCA1, J4-101-02 ribavirin and palivizumab; 4 partial verdicts, 2 approve-all) | 4 partial of 4 | Yes |
| A | `test_only_what_the_check_read_is_shown`, "the cut alone approved" | 1 | Yes |
| A, pins | `test_an_approved_limit_shows_the_whole_sentence`; `test_a_sentence_with_no_copied_cut_keeps_developments_end_strip` | Pass before and after, by design | Yes |
| B | `test_an_item_longer_than_the_check_reads_is_never_sent_or_approved` (guard and Jev; 601-character sentence, 601-character quote, items at exactly 600 still sent) | 2 of 2 | Yes |
| B | `test_a_check_with_only_oversized_items_asks_no_model` | 1 | Yes |
| B | `test_a_joined_item_longer_than_the_check_reads_is_held` (A4-101-04 shape: a cut, then five whole titles, over 700 characters; the guard approves every item it is sent) | 1 | Yes |
| B | `test_a_cut_the_widener_cannot_place_is_held_not_sent_as_its_own_quote` (A4-101-07 "There was no evidence that" long run; one long sentence with "but only in the small subgroup") | 2 of 2 | Yes |
| C | `test_the_listing_keeps_a_row_opening_on_a_separator` (A4-101-05, both reproductions, develop's exact output) | 2 of 2 | Yes |
| D | `test_an_unexpected_failure_of_the_guard_call_approves_nothing` (J4-101-08: `RuntimeError`, bare `TimeoutError`, `KeyError`) | 3 of 3 | Yes |

Each commit was also checked on its own: the four card 101 synthesis files pass at every step (191, 195, 197, 199, 202 cases).

## Mutations

`raw/build_r5/mutate_r5.py`, applied to a scratch copy of the tree, never a worktree, each file restored and compared byte for byte. Output in `raw/build_r5/mutations.txt`; baseline 0 failed.

| Mutation | Red |
|---|---|
| R1 no whole-sentence drop for a held copy | 15 (every A case, round 4's fragment test, and the long joined item) |
| R2 no length filter, every item sent | 4 |
| R3 a cut with no run falls back to the cut as its quote | 2 |
| R4 listing pieces compared with their separators kept | 2 |
| R5 no catch around the guard-tier call | 3 |
| R6 the length filter reads only the sentence's length when either cap fails | 4 |

## Replay of the recorded drafts

`raw/build_r5/replay_r5.py`, built on round 4's `replay_r4.py`: the same 168 distinct recorded first drafts, findings and draft selection, no model call. Writer quotes are not recorded beside the drafts, so reworded sentences are stripped alike on every tree; copied clauses behave as live. Develop is 2182aff3, round 4 is bde1b65d, round 5 is this working tree. Partial approvals use the judge's scheme: every subset of a draft's items for 8 or fewer, else 200 random subsets (seed 7). On round 5 an approval set holds only items `check_reworded_sentences` would send. Sentences are compared with their citation markers removed. Counts in `raw/build_r5/replay_r5.txt`.

| Tree and mode | Runs | Shown that develop does not show | Drafts emptied of all prose | Develop sentences dropped |
|---|---|---|---|---|
| Round 4, approves nothing | 168 | 0 | 0 | 7 |
| Round 4, approves all | 168 | 0 | 0 | 0 |
| Round 4, partial approvals | 252 | 0 | 0 | 33 (7 distinct) |
| Round 5, approves nothing | 168 | 0 | 0 | 7 |
| Round 5, approves all | 168 | 0 | 0 | 0 |
| Round 5, partial approvals | 252 | 0 | 0 | 33 (7 distinct) |

- Round 5 shows exactly what round 4 shows on every recorded draft, in every mode: no recorded draft has a held copy after a kept clause, so the new rule changes no recorded answer. Its effect is on the constructed shapes the reviewers found.
- The 7 dropped sentences are the cuts themselves, the same 7 as round 4. Three of them, as develop showed them: "GERD affects quality of life." (`develop_control/cr1`), "The goal of therapy is to maintain adequate oxygenation and hydration." (`live/br2`), "A high-flow nasal cannula is becoming common for children with severe bronchiolitis." (`live/br3`).
- 34 items in 18 drafts, the same as round 4; none longer than the check reads, and no recorded cut lost its record sentences to the 600-character cap.

## Live check

`raw/build_r5/live_r5.py`: each case through the real `core.graph._ground_with_sentence_check` with a real harness and the shipped `check_reworded_sentences`, in Jev mode (develop's configured mode) and with the guard tier (production's code default), 5 runs each. The check's verdicts are recorded by wrapping the function `core.graph` calls. All text is synthetic. Rows in `raw/build_r5/live_r5.jsonl`. No sign-in to the deployed app, no call to production.

| Case | Mode | What the check said | Shown, 5 of 5 runs unless stated |
|---|---|---|---|
| Azithromycin limit (title, then the cut "only when ... confirmed by culture") | Jev | Approved the joined item 5 of 5 | The whole sentence with its limit, and the next sentence |
| | Guard | Approved 5 of 5 | The same |
| "There was no evidence that" long run (618 characters, sentences opening on digits and "p") | Jev | Never asked about the cut: no item built | Only the other two sentences; the reversed claim never |
| | Guard | Never asked | The same |
| Partial verdict: "Ribavirin [4] and palivizumab [5] are used to treat bronchiolitis [6]." | Jev | "Ribavirin" approved 5 of 5; both joined items held 5 of 5 | Nothing from the sentence. Round 4 showed "Ribavirin [1]." on these verdicts |
| | Guard | Held at least one item 3 of 5; approved all 2 of 5 | Nothing 3 of 5; the whole sentence 2 of 5, as develop shows it unchecked |
| Faithful whole copy, beside a faithful "Results:" copy | Jev | The "Results:" copy approved 5 of 5; the whole copy needs no check | Both sentences |
| | Guard | Approved 5 of 5 | Both sentences |

Every run showed either the whole writer sentence or none of it, and the whole record sentence showed in all 10 runs of its case and in every other case that carried it.

## Choices for the lead to log

| Choice | Taken | Alternative rejected | Why |
|---|---|---|---|
| What counts as held | Every copied clause the check did not approve, including a cut code holds for a bare verdict opener and a clause with no record text to send | Only clauses the check itself answered "no" | The owner's words are "for any reason"; a code hold or an unsendable item leaves the same leftover piece |
| Scope of the drop | Sentences with a held copied clause only | Every sentence with any held clause, reworded ones included | The brief keeps develop's end strip for sentences with no copied-cut item; a held reworded tail after an approved cut still end-strips, as on develop |
| Where the length rule lives | In `check_reworded_sentences`, for every item in both modes | At the point copied items are built | One place guarantees the check never approves unread text, for reworded items too; building-site checks would miss reworded items with long quotes |
| A reworded item past the cap | Not sent, not approved | Sent cut short, as before | Same rule as copied items; none of the recorded items is past the cap, so it costs nothing measured |
| A cut whose record sentences cannot be shown | Held, no item | The record text around the cut trimmed to 600 characters | A trimmed quote can cut off the very clause that reverses the cut; holding is the fail-closed reading of the brief |
| Round 4's middle-strip term | Removed | Kept beside the new rule | The new rule drops every sentence the term dropped and more; keeping both would leave dead code |
| The guard-tier catch | Inside `_ask_guard_tier`, converting to `SentenceCheckUnreadable` | A broad `except Exception` at the caller's `try` | Narrow: only the model call is covered, the cost cap and harness errors keep their own paths, and a bug elsewhere in grounding still surfaces |

## Gates

Run in this worktree with the main checkout's virtual environment first on PATH, each on its own exit code.

| Gate | Result |
|---|---|
| `ruff check` (no path) | All checks passed, exit 0 |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | Exit 0 |
| `bash .github/gates/gate04_unit_suite.sh` | Exit 1: 7,166 passed, 143 skipped, 24 deselected, 1 xfailed, 1 failed, in 1,656 s with the machine's load average above 100. The one failure is `tests/ci/test_gate_scripts.py::TestGate6PythonAudit::test_it_passes_on_this_project_s_requirements`: the dependency audit script it runs timed out at its 120-second limit. It touches no file this round changed; rerun alone it passed (2 passed, exit 0, in 123 s, load average 164). Every card 101 test passed in the full run |
| `python3 tracker/check_doc_drift.py --check` | 2 facts computed, 0 stale, exit 0 |

## Spend

| Item | Calls | Cost |
|---|---|---|
| Live, Jev mode, 5 runs of 4 cases | 20 checks, item and pair calls | $0.00167 |
| Live, guard tier, 5 runs of 4 cases | 20 checks | $0.00039 |
| Two trial runs of 3 cases before the log was reset | 6 checks | $0.00021 |
| Replay, probes, mutations, tests | 0 | $0 |
| Total | | $0.0023 |

## Still open

Not fixed in this round, by the brief; each is shared with develop.

- A4-101-01: an abbreviation followed by a capital (S. Typhimurium, U.S. FDA, vs. PCI, e.g. RSV) still breaks a record sentence, so a faithful copy can show its tail as the record's claim.
- A4-101-02: a sentence in the middle of a multi-sentence quotation or bracket carries no marks of its own and counts as whole.
- A4-101-06: a marked segment of connective words only ("and with") is read by the check but not shown.
- J4-101-03: a faithful whole copy goes to the check when it, or the sentence after it, opens on a lowercase letter, a digit or a Greek letter.
- J4-101-04: any acronym, gene symbol or capitalised drug after "e.g.", "i.e." or "vs." still makes a cut whole.
- J4-101-05 and J4-101-07 (test gaps for round 4's middle-strip term and two listing callers): the term is gone; the two listing callers' flag is still pinned at one caller only.
- Wrapped record names keep today's path by the logged decision of 2026-10-06.
