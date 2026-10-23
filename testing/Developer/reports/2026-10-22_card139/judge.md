# Card 139 judge, one round

Branch fix/card139-notes-say-what-is-true, worktree card139, diff `origin/develop...HEAD` at 59965172. Read and run only. Findings are appended as they are established.

## Findings

### J-139-01: The repair-cap note's "the omission described above" points on screen at a note the web UI hides
- Severity: minor (rare path: cost cap hit during repair AND an omission remains; not introduced by this PR, but the diagnosis certifies it true)
- What: `core/graph.py:10676` keeps "so the omission described above was not repaired". The omission is described by `_build_incomplete_answer_note` ("Note: N further ... records were found ... not covered in the summary above"), and the web UI hides exactly that note (`frontend/src/components/screens/AnswerScreen.tsx:645`, `HIDDEN_NOTE_PATTERNS = [/^Note: (?:one|\d+) further /]`, filtered at AnswerScreen.tsx:1888). The diagnosis ("Checked and left as they are") says the clause is true because the incomplete note "comes before it in the same notes list"; that holds on the command line and in the token list, not on the screen.
- Reproduction: `node -e` with the hide pattern: `true | Note: 3 further pubmed records were found for this question and are not covered in the summary above`; `false | Note: this answer's completeness check could not run ... so the omission described above was not repaired`. Both fire together whenever `repair_cap_exceeded` and `omitted_findings` are non-empty (graph.py:15161 and 15200 to 15201), so on screen the person reads "the omission described above" with nothing above describing one.
- Why it matters: acceptance (1) asks that no note say "above" unless that is where it renders on every surface. This one does not on the web UI.
- NOT FIXED

### J-139-02: A kind NCBI links but the answer shows none of now reads "this answer shows 0", a case the diagnosis planned to suppress and the build does not mention
- Severity: unsure (inside this PR's fix; the sentence is true, the open question is whether it is the sentence the owner wants)
- What: `core/paper_links.py:158` `count_note` returns None only when `total <= shown`. The diagnosis's own "Smallest true fix" step 2 said "return None when `shown == 0` or `total <= shown`"; the built version dropped the `shown == 0` arm and the "Built" list does not say so or why. On develop the 6 to 10 case was silent (old default 10); now it prints a zero count.
- Reproduction: my own probe (scratchpad `test_probe139.py`, the whole Plan, Act and Write path with the test file's stubs, NCBI linking nuccore 20 of 1533, sra 3, assembly 8). The answer's rows are five nuccore records only; the notes read, in the saved-answer markdown (`answer_markdown_from`): "NCBI lists 1533 sequence records linked to PMID 11237011; this answer shows 5." / "NCBI lists 3 SRA run records linked to PMID 11237011; this answer shows 0." / "NCBI lists 8 genome assemblies linked to PMID 11237011; this answer shows 0." On develop the last two lines would not appear at all. Why sra and assembly rows are absent in this stubbed run I did not establish.
- Why it matters: honest and true, which the owner's rule favours, but it states a gap with no reason and nothing to type next ("A refusal says what to type next"). The owner may want this wording, a different one, or the suppression the diagnosis proposed; the PR should say which it chose.
- NOT FIXED

### J-139-03: No test cites two linked kinds at once, so counting across kinds is caught by one arm only
- Severity: minor (test gap, inside this PR's fix)
- What: every new test in `tests/system_03_search_agent/core/test_paper_links_wiring.py` (lines 302 to 399) cites records of a single kind. A mutation that counts every cited page of any kind is caught only by the one arm that adds a gene URL (`other`, about line 341). A sequences question, the real query 104 shape, cites nuccore and assembly together; no test checks that one kind's citations never raise the other kind's number.
- Reproduction: scratch edit of `core/graph.py` `_paper_link_shown` return to `len({source_page_key(c.source_url) for c in citations})`: `1 failed, 11 passed` (only `test_more_linked_records_than_are_shown_says_how_many_NCBI_lists`). Restored; `git diff HEAD` empty.
- Why it matters: if that one arm is ever edited, cross-kind overcounting ("shows 10" over five rows, the card's own defect) returns with every test green.
- NOT FIXED

## Checks that found nothing, with evidence

- Note 1 placement, my own probe: event order on the paper-link path is listing rows, then summary claim, then every note last (`NOTE: listing ...` tokens follow the five `table_row` tokens). The saved answer (`feedback/capture.py answer_markdown_from`) puts the notes after the last row: `note after last row in saved answer: True`. The command line holds listing tokens after the summary (`adapters/cli/render.py:892`), with notes in the listing region at its end. GraphQL `fold.py` keeps arrival order, and notes still arrive last (graph.py:15563 to 15566). On screen, `useRunView.ts:925` sends trailing notes to `systemNotes`, which `AnswerScreen.tsx:2126` renders after `listingBlocks` (AnswerScreen.tsx:2101). The listing-first path: same, `AnswerScreen.listingFirst.test.tsx` green with the note sent with no kind.
- Remaining "below" and "above" in user-visible notes: `_FINDINGS_TAIL_NOTE` "the records below" (graph.py:11089) attaches as `noteBefore` to the first tail row (useRunView.ts:870 to 873) and precedes the tail on the command line, so true. `_build_incomplete_answer_note` "summary above" and "list above" (graph.py:10942 to 10944) are true where shown and hidden on screen. "the omission described above" is J-139-01. `synthesis/findings.py` and `core/clarify.py` hits are model prompts. The adapters' "the answer above" warnings (graphql/fold.py, mcp/server.py, cli) are outside this card.
- Consumers of the old wording: no live consumer matches it. `useRunView.ts:82` matches the unchanged prefix. The coverage grader and eval gate split on "Note:" and periods; the new texts have no interior period. `testing/Test_queries_and_workflows.md` holds no quote of "listed below with their sources", "listed below as found" or "shows 10" (grep of the whole repository, reports excluded: only test and docstring history, `test_write_completeness.py:1046` a dated quote in a docstring). There are no stale quotes to list.
- Card 128 (PR #291, `origin/fix/card128-note-when-summary-repeated`): its new note "only repeated the records listed above" goes in the `structured_fallback_note` slot, so it renders after the listing like this card's notes; "above" is true on every surface above, and consistent with this card's finding. `git merge-tree --write-tree HEAD origin/fix/card128...`: clean.
- Purpose collision: `{db}_summary` purposes are shared with breadth and accession plans, but the paper-link plan is an exclusive `elif` branch (graph.py:7162), so no other call of the same purpose runs on a paper-link question.
- Break it (scratch edits, restored by copy, `git diff HEAD --stat` empty, `git status --short` shows only `?? frontend/node_modules`):
  - Old default `shown: int = MAX_LINKED_PER_DB` with the caller not passing it: `3 failed, 9 passed`, the query 104 test `test_the_written_answer_counts_the_records_it_shows` among them.
  - `_paper_link_shown` returns the summarised count: `3 failed, 9 passed`.
  - Exact URL match without `source_page_key`: `2 failed, 10 passed`.
  - Any-kind count: `1 failed, 11 passed` (J-139-03).
- Runs:
  - `pytest test_paper_links_wiring.py test_write_completeness.py eval/test_write_step_eval_gate.py test_write_answer_structure.py test_write_answer_quality.py`: `122 passed, 1 skipped in 9.94s`
  - `npx vitest run` (answerNotesHidden, answerBold, App, answerPagination, answerLayout, set9AnswerStructure, previousTurnBody, listingFirst, useRunView.refusal, useAnswerReveal, savedAnswerMarkdown): `Test Files 11 passed (11)`, `Tests 117 passed (117)`
  - `venv/bin/isort --check-only --diff src tests services tracker alembic .claude .github`: exit 0, "Skipped 2 files"
  - `venv/bin/ruff check .`: "All checks passed!", exit 0

## Verdict

Acceptance (2) met; acceptance (1) met for the two notes this card changed, but not in full: one remaining "above" (J-139-01, untouched code) is false on the web screen. Nothing measured is worse than develop. J-139-02 is new user-visible text in a case that used to be silent, so that is a wording call, not a regression. J-139-02 and J-139-03 sit inside this phase's fix.

Verified by my own probes: note order in the event stream and the saved answer; the count equals the cited pages per kind; the three-kind zero-count sentence; the hide pattern on J-139-01's pair; four mutations; merge with card 128. Read only: command line and GraphQL ordering (from code), the screen's render order (AnswerScreen.tsx), and the coverage grader's split rule.
