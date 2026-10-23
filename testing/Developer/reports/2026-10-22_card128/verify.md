# Card 128 fresh verification, after the fix round

Verifier: fresh agent, no prior context. Branch fix/card128-note-when-summary-repeated, fix round commit 91b01f20.

## Findings

### V-128-01: no test pins the incomplete-answer note's new wording beside the card 128 note

- Severity: minor (test gap inside the fix round's own code, `graph.py:15166` to `:15172`; behaviour is correct today)
- Located in: the fix round's A-128-02 change (`summary_exists=... and not restatements_only_note_shown`). Not a behaviour regression, so not filed as "Regression of:".
- What: reverting that one expression to `summary_exists=not structured_fallback_used` leaves every named suite green, and the answer then shows the exact contradiction A-128-02 named.
- Reproduction: scratch edit of that one line, then `pytest test_write_answer_quality.py test_write_step_eval_gate.py test_graph.py test_write_completeness.py` printed `314 passed, 1 skipped`. Probe (real `write_node`, restating reply that skips record 3, listing built without `cq-aq-3`) under the mutant, Researcher notes: `'Note: no written summary is shown, because the sentences written only repeated the records listed above'`, `'Note: one further disease record was found for this question and is not covered in the summary above'`. Unmutated HEAD ends instead `... is not included in the list above`. File restored, `cmp` against a backup identical.
- Why it matters: `test_no_note_when_a_dropped_record_is_not_in_the_listing` covers only the case where the writer cited record 3, where the card note is suppressed. The case where the card note shows beside the incomplete-answer note has no test, so the fix for the second half of A-128-02 could be undone silently.
- NOT FIXED

### V-128-02: on the mixed reply shape the diagnosis saw for CFTR, the note never fires, so the reader still gets no summary and no reason

- Severity: unsure (owner scope, not a defect against the owner's words; identical to develop)
- Located in: the fix round's A-128-01 change, `prose_before_drop.stripped_count == 0` at `graph.py:14929`.
- What: any one stripped sentence blocks the note. The card 130 diagnosis (`testing/Developer/reports/2026-10-22_card130/diagnosis.md`, lines 63 to 73) shows the CFTR papers shape is mixed: copied titles ground and are dropped as restatements, while summary sentences ("The papers cover CFTR folding and splicing [1][2].") are stripped. That shape now gets the count line, the list, no note and trust `answer`, which is card 128's reported symptom.
- Reproduction: probe, both depths, HEAD against develop. `restate_plus_stripped`, `restate_plus_unmarked`, `framing_plus_restate` ("The following was found." counted as stripped, `stripped=1`), `cftr_like` (restatements plus "The records cover inherited cancer syndromes and their trials [1][4]."), `two_record_sentence`: spy `stripped=1, dropped=4 or 6, left=0`, notes `[]`, trust `answer`, every token byte-identical to develop. Only the pure restating reply (`stripped=0, dropped=6, left=0`) gets the note.
- Why it matters: the note does fire on the card's pure shape, so it is not "never", but whether a real CFTR Researcher reply is ever pure is not established offline. A person reading the mixed case sees a list with no word about why there is no summary. The owner's decision covers only "every sentence only repeated", so what the mixed case should say is the owner's call. Nothing here is worse than develop.
- NOT FIXED

### V-128-03: the new frontend test does not exercise the kind-less path its title claims

- Severity: minor (test gap; behaviour verified correct by my own probe)
- What: `frontend/src/answerNotesHidden.test.tsx:81` to `:94`, "renders as a note, opening Note: so a kind-less token is a system note too", passes the note straight in as `systemNotes` to `AnswerScreen`. It never sends a token through `useRunView`, so it would pass if `useRunView` classified a kind-less copy of the note as a claim.
- Reproduction: own scratchpad vitest probe feeding token events to `useRunView` then `AnswerScreen`: `kind=note systemNotes=["Note: no written summary is shown, ..."] claims=["Found 1 disease record.","Disease MedGen:C1, name: x."] onscreen=1` and `kind=null` printed the same. So J-128-03 is closed in behaviour; only the test is weaker than its name.
- NOT FIXED

### V-128-04: CI gate 2 (import order) is red on the pull request, from the fix round's new test import

- Severity: major (the merge condition "once CI is green" cannot be met)
- Regression of: J-128-01 and J-128-06. The fix round added `from system_03_search_agent.synthesis.grounding import GroundingResult` at `tests/system_03_search_agent/core/test_write_answer_quality.py:43` for the restore-path test, out of isort order.
- What: `gh pr checks 291` at head 91b01f20 shows `Python gates (1, 2, 3, 4, 6, 9) fail`. The failed log is gate 2: `ERROR: .../tests/system_03_search_agent/core/test_write_answer_quality.py Imports are incorrectly sorted and/or formatted.`, the diff moving the `grounding` import below `synthesis.findings`.
- Reproduction: `gh run view 39885948194 --log-failed`, quoted above. Accessibility, Frontend gates and Integration suite pass.
- Why it matters: the pull request cannot merge under the owner's condition, and gate 2 failing means CI never reached gate 4, the unit suite, which holds V-128-05.
- NOT FIXED

### V-128-05: the unit suite has a test that fails on this branch and passes on develop

- Severity: major (gate 4 will fail once gate 2 is fixed; a card 105 property no longer holds)
- Located in: the card's first commit c2232ae7, not the fix round. It reproduces with c2232ae7's source too (there the note is the old wording). The fix round's narrowed condition does not exclude this case.
- What: `tests/system_03_search_agent/core/test_bare_topic_clarification.py::test_a_picked_window_with_no_papers_in_it_says_so` (`:927` to `:941`) asserts card 105's "one plain line" for a picked five-year window with no PubMed papers, `len(notes) < 200`. On HEAD the card 128 note fires too and the notes come to 250 characters.
- Reproduction: `pytest tests/system_03_search_agent/core/ tests/system_03_search_agent/eval/ tests/system_03_search_agent/synthesis/` printed `1 failed, 2961 passed, 67 skipped, 1 xfailed`. The single test on HEAD: `AssertionError: No PubMed papers from the last 5 years were found for BRCA1. Papers in the knowledge graph carry no publication date, so they are not listed here.\nNote: no written summary is shown, because the sentences written only repeated the records listed above`, `250 < 200` false. The same test run against develop's `src` (git archive of origin/develop into the scratchpad, `-o pythonpath`): `1 passed`. The answer tokens on HEAD: claim `Found 1 gene record for BRCA1: BRCA1 DNA repair associated [1].`, one gene table row, the no-papers note, then the card 128 note, trust `answer`.
- Why it matters: the note's words are true here, since the gene record is listed above. But a person who asked for recent BRCA1 papers now reads two notes, and the second is about a gene summary they did not ask for. Whether card 105's one-line rule or card 128's note wins is the owner's call, or the test changes with a stated reason. Either way the branch is red today.
- NOT FIXED

- Addendum to V-128-04, own run of the gates' exact commands in the worktree: gate 2 `isort --check-only src tests services tracker alembic .claude .github` printed the same `Imports are incorrectly sorted` error; gate 3 `ruff check` printed `I001 [*] Import block is un-sorted or un-formatted` at `test_write_answer_quality.py:31`, `Found 1 error.`, so gate 3 is red for the same line; gate 4 `pytest -m "not integration" -q` printed `1 failed, 8486 passed, 143 skipped, 24 deselected, 1 xfailed`, the one failure being V-128-05.

## Closure of the judge and adversary findings

Each re-derived by my own probe (`<scratchpad>/probe128.py`, real `write_node`, the fixtures of `test_write_answer_quality.py`, stubbed writer replies, no live model call), run against HEAD, against develop's `src` and against c2232ae7's `src`, 11 reply shapes at both depths.

| Finding | Verdict | Evidence |
|---|---|---|
| J-128-01 restore path | Closed | `listing_empty_restore`, both depths: restored sentences on screen, notes `[]`, trust `answer`, identical to develop. The `and restatements_dropped` guard at the `elif` is redundant (removing it leaves 314 passed), because the flag already needs listing claims and the restore needs none; not a defect |
| J-128-02 grader | Closed | `_citation_coverage(base + note)` printed `1.0`, `_looks_like_framing` True; the old wording printed `0.667`, False |
| J-128-05 wording | Closed | Shipped text equals DECISIONS.md 2026-10-22 exactly, no trailing period in either |
| J-128-03 kind-less token | Closed in behaviour | Own vitest probe through `useRunView`: `kind=null` puts the note in `systemNotes`, not claims. The committed test does not prove it (V-128-03) |
| J-128-04 "above" | Closed | Researcher and Plain language: the note is the last token after every table row and list item; saved markdown and `joined_text` end with it after the rows; with `reads_placement=True` it carries `placement='listing'` after the listing; on screen it renders after the row (`compareDocumentPosition` FOLLOWING) |
| J-128-06 restore test | Closed | `test_no_note_when_the_restatements_are_put_back` exists; the J-128-01 mutant is no longer distinguishable because the guard is redundant, see above |
| J-128-07 populate-check | Closed | `_written_sentences` now matches "NCBIGene:672 is associated with", not the count line |
| A-128-04 boundary tests | Closed | `test_one_surviving_sentence_blocks_the_note` and `test_note_shows_when_only_two_sentences_were_written_and_both_repeated` cover the two mutants named |
| A-128-01 stripped sentences | Closed | `restate_plus_stripped`, `restate_plus_unmarked`, `cftr_like`: no note on HEAD (the first commit showed it on every one). Mutant without `stripped_count == 0` turns `test_no_note_when_some_sentences_were_stripped_not_repeated` red. Scope consequence: V-128-02 |
| A-128-02 unlisted record | Closed in behaviour | Writer cites record 3, listing omits it: no card note, identical to develop. Writer skips record 3: card note plus "is not included in the list above", both true. Second half unpinned: V-128-01 |
| A-128-03 | Left on purpose | Plain language still ends with the card note then "This is a research summary, not medical advice." |

## Trust outcome and the rest of the answer

- Every case, HEAD against develop: `trust_outcome` and `trust_line` identical in all 22 runs.
- With the card note removed from HEAD's output, tokens and notes are identical to develop in 20 of 22 runs. The two others are `listing_omits3_writer_skips3`, where the incomplete-answer note changes on purpose from "not covered in the summary above" to "is not included in the list above".
- `summary_exists=False` is reached only when the card note is shown, which needs listing claims, so "the list above" always has a list above it. Its words were true in the one case that reaches it.
- Pre-existing on develop and unchanged here, not filed against this card: with record 3 unlisted and every written sentence dropped, develop and HEAD both say "not covered in the summary above" where only the count line remains.

## Break it

- Listing-subset check removed alone (`graph.py:14932` to `:14933`): `FAILED tests/system_03_search_agent/core/test_write_answer_quality.py::test_no_note_when_a_dropped_record_is_not_in_the_listing`, `1 failed, 313 passed, 1 skipped`.
- `stripped_count == 0` removed alone: `test_no_note_when_some_sentences_were_stripped_not_repeated` red.
- `and restatements_dropped` removed from the `elif`: 314 passed (redundant guard, see J-128-01).
- `summary_exists` reverted: 314 passed (V-128-01).
- Each restored with `git checkout -- graph.py`; `cmp` against a scratchpad backup identical; `git diff HEAD` empty; `git status --short` shows only `?? frontend/node_modules`. No git stash.

## Suites run

- `test_write_answer_quality.py`, `test_write_step_eval_gate.py`, `test_graph.py`, `test_write_completeness.py` (the two that mention `structured_fallback_note`): `314 passed, 1 skipped in 9.40s`. The skip is the eval gate itself, which needs the live graph and a model key.
- `frontend/src/answerNotesHidden.test.tsx`: `Test Files 1 passed (1)`, `Tests 6 passed (6)`.
- Full unit suite as gate 4 runs it: `1 failed, 8486 passed` (V-128-05).

## Verified by my own probes and only read

- Probed: every closure row above, trust unchanged, placement, saved answer, CLI text, screen order, the kind-less path, the grader, the four mutants, the gates' exact commands, the V-128-05 failure on HEAD, develop and c2232ae7.
- Read only: the refusal case (the `elif` does not check `trust_outcome != "refuse"`; by the code's own comment a grounded listing cannot refuse, not probed); the completeness repair replacing a first draft (not reached with these fixtures); GraphQL and MCP end to end beyond `joined_text`; whether a real CFTR Researcher reply is ever the pure shape (needs a live run).

## Verdict

HOLD. The fix round closes every judge and adversary finding it claims, and the trust outcome is unchanged on every path probed. But the branch is red: gates 2 and 3 fail on the fix round's own test import (V-128-04, Regression of J-128-01 and J-128-06, inside this phase's fix), and the unit suite has one test that passes on develop and fails here (V-128-05, from the first commit). The owner's merge condition, CI green, is not met. V-128-04 sits inside a fix made in this phase, which under Rule 4 escalates to the owner.

## Round 3, fresh verifier

Started 2026-10-22 against cd47ab23. Findings appended as established.

### V-128-06: the window check is read twice, and the second read can disagree with the first

- Severity: minor (unsure it is ever reached; not worse than develop)
- Regression of: round 3, cd47ab23, inside this phase's fix.
- What: `_window_no_papers_note(state, query)` is called at `src/system_03_search_agent/core/graph.py:15093` to suppress card 128's note and again at `:15421` to show card 105's note. It is not pure: through `_picked_publication_window` it calls `clarify.picked_recent_window` (`core/clarify.py:365` to `:372`), which pops the session's offer when it has expired and reads a module-level `_OFFERED` dict that another request in the same session can replace (`offer_recent_windows`, `:346`). An `await resolve_concept_ids(...)` sits between the two calls (`graph.py:15133`). If the offer expires (1 hour TTL) or is replaced in that gap, the first call returns the line, the second returns None, and the answer shows neither note.
- Reproduction: read only, not driven. The race needs the TTL to lapse inside one Write step.
- Why it matters: the person would see a list with no explanation of the missing summary, which is exactly develop's behaviour, so nothing is worse than develop. Computing the line once and reusing it removes the gap. Cheap otherwise: both calls are dict lookups and list scans, no I/O.
- NOT FIXED

### V-128-07: round 3 covers only card 105; other notes that explain a thin answer still stack with card 128's

- Severity: unsure (a scope question for the owner, not a wrong word)
- Located in: round 3, cd47ab23, by what it leaves out.
- What: the owner's words are "when another note already explains the missing summary, such as card 105's". The clause checks card 105 only. In the note list at `graph.py:15415` to `:15428`, notes that can co-occur with card 128's (none of them is gated on it): `truncation_note`, `_isolate_count_note`, `_paper_link_notes` (card 74's `empty_target_note` "NCBI lists no linked genes for PMID X.", the closest analogue of card 105's line), `_isolate_disclosure_note`, `_disease_lookup_failed_note` ("literature and trials were not searched"), `partial_answer_note`, `incomplete_answer_note` (rewords to "not included in the list above", by design), `failed_search_note` (`_build_failed_search_note` / `_build_unfinished_search_note`, "this answer may be missing sources"), `repair_cap_note`, the placeholder note and the medical-advice note. Cannot co-occur, same variable and the `elif`: `_build_cap_list_note`, `_build_writer_failed_note`, `_build_structured_fallback_note`. Refusal-only, never stacks: `_paper_link_none_message`, `_window_no_papers_refusal`.
- Reproduction: read only, plus the probe below for the failed-search case.
- Why it matters: none of the stacking notes says why there is no written summary in the way the three `elif` notes do, so card 128's words stay true beside them. Whether card 74's empty-target line or card 77's disease-lookup line "already explains" it, as card 105's was judged to, is the owner's call.
- NOT FIXED

### Closure of V-128-04 and V-128-05

| Finding | Verdict | Evidence, own run in the worktree at cd47ab23 |
|---|---|---|
| V-128-04 import order | Closed | Gate 2 `isort --check-only --diff src tests services tracker alembic .claude .github`: `Skipped 2 files`, exit 0, no diff. Gate 3 `ruff check .`: `All checks passed!` |
| V-128-05 card 105's one line | Closed | Gate 4 as `.github/gates/gate04_unit_suite.sh` runs it (`pytest -m "not integration" -q -rs`, junit file sent to the scratchpad so nothing lands in the worktree): `8488 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 508.23s`, exit 0. The last round's `1 failed, 8486 passed` plus the one new test |

- CI at cd47ab23 when read: Accessibility, Frontend gates and Integration suite pass; Python gates pending.
- `git merge-tree --write-tree HEAD origin/develop` merges cleanly (develop has moved by cards 131 and 138). On that merged tree, `test_bare_topic_clarification.py` and `test_write_answer_quality.py`: `87 passed`.

### Round 3's condition

- Scope: `git diff 91b01f20..HEAD -- src` is one hunk, the new `and _window_no_papers_note(state, query) is None` clause at `graph.py:15093`. The rest of the earlier verified behaviour is unchanged in source. 6751f0f7 only moves one import line.
- Cost: two dict lookups and a scan of the planned calls, no I/O, no model call. Side effects: one, an expired offer is popped (V-128-06).
- Same answer twice: a spy around the real helper, in five `_ask_brca1` cases, returned the same value on both calls every time.
- Exactly card 105's case: the note list at `:15421` shows the line whenever the helper is non-None, on every non-refusal. A refusal takes the other branch and shows the line inside the refusal, where card 128's note never appears. So the clause suppresses card 128's note exactly when card 105's line shows, apart from the expiry gap in V-128-06.

| Case (own probe, real `write_node`, stubbed tools and models) | develop | HEAD | merged with develop |
|---|---|---|---|
| Picked window, no papers | 105 line only, 146 chars, answer | Same, 146 chars, answer | Same |
| Picked window, PubMed search fails | Failed-search note, ask | Card 128 note plus failed-search note, ask | Same as HEAD |
| Picked window, papers found | No notes, answer | Same | Same |
| No window, graph papers | Truncation note, answer | Truncation note plus card 128 note, answer | Same as HEAD |
| Picked window, papers only, none in window | Refusal with the 105 line | Same, helper not reached | Same |

- Trust outcome identical to develop in every case.
- The failed-search row is the stacking V-128-07 names. Card 128's words are true there.

### Break it

- Clause replaced by `and True`: `FAILED test_write_answer_quality.py::test_no_note_when_card_105s_window_note_already_explains` (`:356`, the card 128 note present) and `FAILED test_bare_topic_clarification.py::test_a_picked_window_with_no_papers_in_it_says_so` (`:939`, the 250 character notes), `2 failed`.
- Clause inverted to `is not None`: 4 failed, those two plus `test_researcher_drops_restatements_the_list_carries_and_keeps_a_cited_summary` and `test_note_shows_when_only_two_sentences_were_written_and_both_repeated`.
- The new unit test monkeypatches the helper to a constant, so on its own it does not prove the helper's real value. Card 105's end-to-end test at `:927` does, and it goes red as well.
- Restored with `git checkout -- graph.py`; `cmp` against the scratchpad backup identical; `git diff HEAD` empty; `git status --short` shows only `?? frontend/node_modules`. No git stash.

### Verified by my own probes and only read

- Probed: gates 2, 3 and 4 by their exact commands, the clean merge with develop and its two test files, the helper's repeat value, the five-case table against develop, HEAD and the merged tree, both mutants, the restore.
- Read only: the V-128-06 expiry gap (not driven), what each note builder in V-128-07 says, the Plain language depth (the clause does not read the depth), CI's Python gates (pending when read).

### Verdict, round 3

PASS, nothing worse than develop. V-128-04 and V-128-05 are closed, round 3 does what the owner asked for card 105, and nothing else in `src` changed. Two findings sit inside round 3 and neither is worse than develop: V-128-06 (minor, the second read of the window check can disagree with the first, read only) and V-128-07 (unsure, a scope question: other notes that explain a thin answer still stack). Both are filed as "Regression of" or "Located in" round 3, so under Rule 4 they go to the owner, not to a fourth round. The merge condition still needs the pending Python gates to finish green.
