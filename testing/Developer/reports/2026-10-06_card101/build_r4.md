# Card 101 build round 4: the last fix round for copied cuts

Builder, 2026-10-06, branch `fix/card101-copied-cuts` from round 3's 809c8574. The owner approved this one round after round 3 failed review; it fixes exactly the nine items the lead listed from `judge_r3.md` and `adversary_r3.md`, and nothing else.

Card 101's goal: a sentence the app shows as copied from a record is either a whole record sentence, which may skip the sentence check, or it goes to the sentence check, which fails closed. Wrapped record names stay on today's path (logged decision, not in scope).

## Table of contents

- [Verdict](#verdict)
- [The change in the user's words](#the-change-in-the-users-words)
- [What changed](#what-changed)
- [Each finding, its fix, test and mutation](#each-finding-its-fix-test-and-mutation)
- [Mutations](#mutations)
- [Offline replay of the recorded drafts](#offline-replay-of-the-recorded-drafts)
- [The reviewers' attacks, offline](#the-reviewers-attacks-offline)
- [Faithful colon-label copies and the live check](#faithful-colon-label-copies-and-the-live-check)
- [Choices for the lead to log](#choices-for-the-lead-to-log)
- [Gates](#gates)
- [Spend](#spend)
- [Left for card 101's next step](#left-for-card-101s-next-step)

## Verdict

| Item | Finding | Status |
|---|---|---|
| 1 | J3-101-01, A3-101-01: a colon is not a sentence start | Fixed |
| 2 | J3-101-02, A3-101-06: a semicolon is not a sentence end; the listing keeps its rows by its own path | Fixed |
| 3 | J3-101-03, A3-101-03: an abbreviation's full stop is not a boundary | Fixed, with the residual the widener shares ("Dr. Smith") |
| 4 | A3-101-07: never a leftover fragment | Fixed: hb4 shows what develop shows; "Ribavirin [1]." no longer shown |
| 5 | J3-101-04: the listing keeps "But", "And", "Then", "Or" sentences | Fixed, exactly as develop shows them |
| 6 | J3-101-05: the check reads the whole shown sentence after a cut | Fixed for copied clauses (whole or wrapped) |
| 7 | A3-101-02, A3-101-04: a record question shown as a statement, and stripped quote marks or brackets, go to the check | Fixed (routing); the check itself approved the quoted claim live in round 3, see below |
| 8 | J3-101-06: three missing tests | Added, each mutation-proven |
| 9 | J3-101-08: stale sentence-check comments in `core/graph.py` | Updated |
| Replay | 265 whole copies in 168 recorded drafts | 0 moved to the check; no draft loses all its prose; no sentence shown that develop does not show |
| Gates | 02, 03, 04, leak scan | See [Gates](#gates) |
| Spend | | $0, no model call |

## The change in the user's words

- A sentence the app copies from a paper shows at once only when it is one of the paper's sentences in full, word for word, with the paper's own quote marks and brackets and, for a question, its question mark.
- A label before a colon is part of the sentence. "Drug X cures cancer in mice" copied from "RETRACTED: Drug X cures cancer in mice." is read by the sentence check against the whole title first, as are copies that drop "Myth:", "Hypothesis:" or "Do not:".
- Words before a semicolon, or before an abbreviation such as "e.g." or "U.S.", are not a whole sentence. "Drug X is safe in children" copied from "...; however, it caused deaths in infants" is checked first.
- When a sentence joins a copied piece onto a partial copy, the check reads the sentence as it would appear on screen, all of it.
- When the check holds something back or cannot run, a sentence is either shown as develop showed it or not at all; never a leftover piece such as "Ribavirin [1]."
- The record list shown when the writer's answer fails keeps every sentence it kept before, including one that opens on "But".

## What changed

| File | Lines | Change |
|---|---|---|
| `src/system_03_search_agent/synthesis/grounding.py` | 920 to 1037 | The whole-sentence test: record sentences split by `_RECORD_SENTENCE_BOUNDARY` (`_record_sentences`, 945), the question rule (`_ends_as_question`, 959), the clause tested with its connective kept (`_without_glue`, 965), `is_whole_record_sentence` (983), the listing's own path (`_is_code_built_row`, 1021). Round 3's `_WHOLE_SENTENCE_START`, `_WHOLE_SENTENCE_ENDS` and mark-skipping are gone |
| same | 1060 to 1110 | `_copied_clause_candidate`: docstring; the prefix read without a space before a comma |
| same | 1399 | `run_grounding_pass(..., code_built_listing=False)` |
| same | 1500 to 1515 | Per sentence: `held_for_check`, `cut_in_sentence` |
| same | 1662 to 1702 | Routing: a cut, and every copied clause after a cut, become check items; held clauses recorded |
| same | 1760 to 1778 | Middle-strip rule: a held clause counts as surviving after a clause code stripped |
| `src/system_03_search_agent/core/graph.py` | 9821, 13223, 13328 | The repair probe, the structured fallback and the findings tail pass `code_built_listing=True` |
| same | 9670 to 9712 | Sentence-check comments and docstring name copied cuts as items (item 9) |
| `tests/system_03_search_agent/synthesis/test_copied_cuts.py` | 170 to 525 | Listing test now passes the flag; 13 new test functions, 32 new cases (16 cases before, 48 now) |
| `tests/system_03_search_agent/synthesis/test_pubmed_abstract_grounding.py` | 139 | The "Results:" excerpt is now a check item, shown once approved |
| `tests/system_03_search_agent/synthesis/test_quote_anchored_synthesis.py` | 221 | A copy without its record's closing quote mark is now a check item |
| `testing/Developer/reports/2026-10-06_card101/raw/build_r4/` | | Replay, probe and mutation scripts; counts-only outputs |

## Each finding, its fix, test and mutation

| Item | Fix | Test (`test_copied_cuts.py` unless named) | Mutation that turns it red |
|---|---|---|---|
| 1 Colon | A record sentence starts only at the value's start or after `_RECORD_SENTENCE_BOUNDARY` (a full stop, question or exclamation mark, whitespace, then a capital, quote mark or bracket). A colon never starts one | `test_a_copy_after_a_colon_label_goes_to_the_check` (retracted, myth, hypothesis, do not, faithful "Results:"); `test_pubmed_abstract_grounding.py::test_a_verbatim_abstract_excerpt_grounds_and_cites_its_own_paper` changed: the "Results:" copy is a check item reading the labelled sentence, shown once approved | M1: 5 red ("do not" is held by the semicolon rule too) |
| 2 Semicolon | A semicolon never ends a writer's whole sentence. The listing's rows are matched exactly against the pieces code cut (`_is_code_built_row`), only when the caller passes `code_built_listing=True` | `test_a_copy_up_to_a_semicolon_goes_to_the_check` (however, aspirin, "GLUCOKINASE" copied by the writer); `test_the_code_built_listing_still_grounds_whole` | M2: 3 red; M6 (flag ignored): the listing test red |
| 3 Abbreviation | The same boundary as the widener: no capital after the stop, no break | `test_a_cut_at_an_abbreviation_goes_to_the_check` (e.g., U.S., yrs., vs., approx.) | M3: 5 red |
| 4 Fragment | The middle-strip rule counts a held copied clause as surviving after a clause code stripped, which is exactly develop's drop. A held clause itself stays an end strip | `test_a_held_cut_never_leaves_a_fragment_develop_dropped` (the synthetic "Ribavirin [1]." case, check holds and approves); hb4 by replay, below | M10: 2 red |
| 5 Connective | The whole-sentence test and the listing row read the clause with its connective (`_without_glue`), as well as without it | `test_the_listing_keeps_a_record_sentence_opening_on_a_connective` (But, And, Then, Or; exact develop output); `test_a_writers_copy_of_a_sentence_opening_on_but_is_whole` | M7c: 5 red; M7 alone: the writer case red |
| 6 Joined | Once a sentence holds a cut, every later copied clause, whole or wrapped, is a check item read as the sentence up to it | `test_a_copied_clause_after_a_cut_is_read_joined_from_every_record`; `test_only_what_the_check_read_is_shown` (none, cut alone, both approved); `test_a_whole_record_sentence_after_a_cut_is_read_joined` | M8: 4 red |
| 7 Question, marks | A record sentence ending in "?" is whole only for a copy that keeps the "?". Record sentences are compared with their quote marks and brackets; no mark is skipped | `test_a_record_question_copied_as_a_statement_goes_to_the_check`; `test_a_copy_with_its_quote_marks_or_brackets_left_off_goes_to_the_check`; `test_quote_anchored_synthesis.py::test_an_unpaired_quote_mark_alone_drops_the_sentence` changed | M4: 2 red; M5 (round 3's mark rule): 2 red, the third case held by the colon rule |
| 8 Missing tests | Joined quotes from every record; a "Yes," cut held by code; case-sensitive match | `test_a_copied_clause_after_a_cut_is_read_joined_from_every_record`; `test_a_cut_opening_on_a_bare_verdict_is_held_by_code`; `test_the_whole_sentence_match_is_case_sensitive` | M9, M11, M12: 1 red each |
| 9 Comments | `_SENTENCE_CHECK_MIN_BUDGET_S` comment and `_ground_with_sentence_check` docstring | Comments only | None |

## Mutations

Applied by `raw/build_r4/mutate_r4.py` to a scratch copy of the tree, never this worktree, each restored and checked byte for byte. Output in `raw/build_r4/mutations.txt`. The tests run: `test_copied_cuts.py`, `test_pubmed_abstract_grounding.py`, `test_quote_anchored_synthesis.py`, 80 cases.

| Mutation | Red |
|---|---|
| M1 a colon starts a record sentence | 5 |
| M2 a semicolon ends a record sentence | 3 |
| M3 no capital needed after a full stop | 5 |
| M4 a record question counts as a statement | 2 |
| M5 round 3's rule: a break after a closing mark, marks stripped | 2 |
| M6 the listing flag ignored | 1 |
| M7 only the claim after its connective tested (writer path) | 1 |
| M7b only the listing row after its connective tested | 0, the writer-path form still keeps it |
| M7c both tested after the connective | 5 |
| M8 clauses after a cut not read joined | 4 |
| M9 the joined item keeps only the last record's text | 1 |
| M10 held clauses not counted by the middle-strip rule | 2 |
| M11 a verdict-opening cut not held by code | 1 |
| M12 the whole-sentence match ignores case | 1 |

## Offline replay of the recorded drafts

The adversary's `replay_traces.py` reads round 3's constants, which round 4 removes, so it is adapted as `raw/build_r4/replay_r4.py`: the same 168 distinct recorded first drafts, the same findings rebuilt from each trace, the same draft selection, no model call. Writer quotes are not recorded beside the drafts, so reworded sentences are stripped alike on every tree; copied clauses behave as live. Develop is d8179c4e, round 3 is 809c8574, round 4 is this branch's working tree, each exported to the session scratchpad. Counts in `raw/build_r4/replay_counts.txt`.

| Tree | Shown, check approves nothing | Shown, check approves every item | Check items |
|---|---|---|---|
| Develop | 59 | 59 | 0 |
| Round 3 | 53 | 59 | 31 |
| Round 4 | 52 | 59 | 34 |

- Whole copies: round 3 counts 265 clauses whole; round 4 counts the same 265 whole. 0 moved to the check, 0 newly whole.
- No draft where develop shows prose shows none on round 4, under either check outcome.
- No sentence shown on round 4, under either outcome, that develop does not show.
- hb4: develop shows 2 sentences, round 3 with no approvals 3 (the third was "The name Adenoviral bronchiolitis [2]."), round 4 the same 2 as develop, under both outcomes.
- The 3 extra items are item 6's joined reads, in 3 drafts (`live/gp1`, `live/br3`, `live/br1` in the counts file); none changes what those drafts show.

## The reviewers' attacks, offline

Each run through the real `run_grounding_pass` on develop, round 3 and round 4: shown with no approvals, what the check was asked, shown with every item approved. Scripts: `raw/build_r4/probe_judge.py` (judge_r3's probes) and the adversary's `probe_whole.py`, `probe_fragment.py`, `probe_connective.py`, copied unchanged to the scratchpad.

| Attack | Develop and round 3 | Round 4 |
|---|---|---|
| J3-101-01: hypothesis, myth, misconception, "Not recommended:" | Shown, no check | Check items, nothing shown without approval |
| J3-101-02: "; however", contraindications list | Shown, no check | Check items |
| J3-101-03: e.g., U.S. (both writer forms), yrs. | Shown, no check | Check items |
| J3-101-04: the listing with But, And, Then, Or | Develop shows both rows; round 3 one | Both rows, as develop |
| J3-101-05: "in children", "in bronchiolitis in infants", a whole sentence after a cut | Round 3 read the cut alone | The check reads the cut and the whole shown sentence |
| A3-101-01: retracted title, myth, hypothesis, "Do not:", "the claim:" | Shown, no check | Check items |
| A3-101-02: question title and question sentences as statements | Shown, no check | Check items |
| A3-101-03: vs., et al., e.g., approx. (2 cases) | Shown, no check | Check items |
| A3-101-03: "Dr. Smith's regimen ..." | Shown, no check | Still shown, no check: a capital after the abbreviation is a boundary for the widener too. Residual named by both reviewers |
| A3-101-04: quoted claim after a colon, quoted sentence, bracketed sentence | Shown, no check | Check items |
| A3-101-06: two semicolon cases | Shown, no check | Check items |
| A3-101-07: hb4 and "Ribavirin [1] is first-line care, ..." | Round 3 shows the fragment | Nothing from the sentence, as develop |
| A3-101-07 (connective): writer copies of "But", "And", "Then" sentences, and the listing | Round 3 lost them | Shown as develop |
| A3-101-05: two whole sentences from different records, "It" changing subject (4 cases) | Shown, no check | Unchanged, out of scope |

## Faithful colon-label copies and the live check

No live call was made. The adversary's round 3 live run (`raw/adversary_r3/live_r3.py`, `live_r3.jsonl`) sent the shipped check five synthetic items built by a scratch tree with the colon start removed, a capital required and the question rule added: the check held the retracted, "the claim:" and question-title copies 9 of 9 and approved the faithful "Results:" and "Conclusions:" copies 6 of 6. Built by round 4 (`raw/build_r4/items_dry.py`), those five items are identical, sentence and quotes, so that live result is the result for this branch. hb4's three items differ only by the space before each comma, and hb4's sentence is dropped whatever the check says.

The adversary's live run also showed the check approve the quoted claim ('Advertisements stated: "Drug X cures cancer." ...' copied as "Drug X cures cancer") 3 of 3. Round 4 routes that copy to the check, as item 7 asks; the check's own verdict on it is not changed here.

## Choices for the lead to log

| Choice | Taken | Alternatives considered | Why |
|---|---|---|---|
| How the listing keeps semicolon rows | An explicit `code_built_listing` flag from the three code-built callers; rows matched exactly against the pieces code cut | Accept any piece of `split_into_sentences(value)` for every caller | The second accepts the writer's cut at a semicolon or an abbreviation again, the hole item 2 closes |
| What a record sentence is | `_RECORD_SENTENCE_BOUNDARY`, the widener's rule, unchanged | A list of abbreviations | The brief and the no-hardcoded-decisions rule; "Dr. Smith" stays a residual, the check is the safety |
| Record questions | Whole only when the copy keeps the "?" | Never whole | Same outcome in practice (the narrative splitter ends a sentence at "? "), simpler to state |
| What the check reads after a cut | One item per later copied clause, each the sentence up to it | One item for the cut reading the whole sentence | The second approves a longer sentence and can then show a shorter prefix that drops the limit ("Antibiotics are effective" approved as part of "... only when ..."). Per-clause items make every shown prefix an approved item |
| The fragment rule | Add back exactly develop's middle-strip drops | Drop the whole sentence whenever a cut is held | The second also drops a whole sentence develop showed, when the check holds only its last clause |
| The writer's copy of a "But" sentence | Whole, as on develop | Only the listing | One rule for both paths; develop showed it, and the adversary measured the check approves it |
| The check item's text | No space before a comma where a marker stood | As round 3 | What a reader sees; changes no outcome |

## Gates

Run from this worktree with the main checkout's virtual environment first on PATH, on the tree as committed in 50866eda and 35e045da.

| Gate | Result |
|---|---|
| `gate02_import_order.sh` | Pass, exit 0 |
| `gate03_lint.sh` (ruff, whole repository, no path) | Fails, exit 1, "Found 20 errors": all 20 in the reviewers' untracked scripts under `raw/adversary_r3/` (10 files). With that folder excluded, "All checks passed!". This round's committed files, `raw/build_r4/` included, are clean |
| `gate04_unit_suite.sh` | Pass: 7,072 passed, 143 skipped, 24 deselected, 1 xfailed, 0 failed, in 394 s, load average 15 at the start |
| `check_public_leaks.py --base origin/develop` | Pass, 0 findings, run after the report's commit |

## Spend

| Item | Calls | Cost |
|---|---|---|
| Live model calls | 0 | $0 |
| Replay, probes, mutations, tests | 0 | $0 |

## Left for card 101's next step

- A3-101-05: two whole record sentences from different records joined, so "It reduced hospitalization by 55%" takes the other record's subject. Unchanged, shown with no check on every tree.
- Wrapped record names: unchanged by the logged decision ("Ribavirin can cure bronchiolitis in babies" still shows unchecked), pinned by `test_a_wrapped_record_value_keeps_todays_path_for_now`.
- A capital after an abbreviation ("Dr. Smith") still breaks a record sentence; the widener has the same rule.
- The check approved a quoted claim copied without its quote marks (adversary, 3 of 3); routing alone does not close A3-101-04.
- A reworded clause after a cut is read as its own item, not joined to the cut; item 6 covers copied clauses only.
- Check items in sentences that can no longer show (A3-101-08, A3-101-09) are still collected; round 4 adds 3 such reads in the replay.
- Researcher depth, gene questions and the guard-tier mode of the check: not run live in this round.
