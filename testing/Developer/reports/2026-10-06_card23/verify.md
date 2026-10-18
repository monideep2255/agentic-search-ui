# Card 23 fresh verifier report, after the fix round (parts 1 and 2)

Branch fix/card23-source-note at d0c19f53 against develop d94604fb. Fresh context, written as findings are established.

## Findings

### Probe record 1 (held, not a finding): real backend streams through both real frontends

- Method: my own script drove the real `write_node` (model call and MedGen lookup faked, as the judge and adversary did) for 14 shapes on the branch and on develop, dumped the full event streams as JSON, then rendered each stream through the real `useRunView` and `AnswerScreen` of each tree in vitest, at desktop width and with the phone media query.
- Backend: the only token differences between develop and branch are one `note` (the line) and one `paragraph_break`, in the 8 shapes with a variant-to-disease table at a technical depth. Plain language, diseases only, unfolded variants, isolates, trials and the gene-to-disease table alone are identical.
- Frontend no-regression: develop's streams render byte-identical summaries (blocks, inline notes, Notes list) on the develop and branch frontends (`cmp` equal).
- Placement on the branch, desktop and phone: in all 8 shapes the line is `answer-inline-note-0`, its previous block is the variant table, it is not in the Notes list. Table last (Researcher, Clinical brief, Deep technical, structured fallback, gene-to-disease table first then variant table): line under the variant table, Notes list keeps only the placeholder note and, on the fallback, "Note: no written summary ...". More records after (gene list, gene-to-disease table): line under the variant table, next block the following heading.
### Probe record 2: trying to break the opening-words match (crafted streams through the real hook, branch and develop frontends)

| Case | Branch result | Reachable from today's backend |
|---|---|---|
| Writer sentence (kind `claim`) starting with the line's words, after the table | Prose, not attached | Model sentences are claims, never notes, so yes, and it holds |
| The line after prose, no table | Notes list, as before | No |
| Line, then "Note: no written summary ..." | Line under table, summary note in Notes list | Yes (fallback), holds |
| Line with leading spaces | Attached (trimmed) | Holds |
| Line streamed, run not landed | Attached at once; develop showed it in Notes until a later claim | Holds, an improvement |
| A kind-less truncation note between the last row and the line | Line still attached | Holds |
| A different note that opens with the same words | Attached under the table (F-23-V-01) | No backend note opens that way today |
| Line truncated to 40 characters, curly apostrophe, or an answer-wide note before the line | Falls back to the Notes list | No: the line is one code-built token with a straight apostrophe, emitted directly after the rows (probe 1) |
| Line emitted twice | First under the table, second in Notes | No (one variant-to-disease table per answer) |
| Line followed by more rows of the same table | Table split in two around the line | No (every table opens with a heading and header) |

### F-23-V-01: any note that opens with the line's first 63 characters is pulled under the table, not only the line
- Severity: minor, unsure (not reachable today). Not a regression against develop (develop has no line and no attach).
- File: `frontend/src/hooks/useRunView.ts:101` (the prefix) and `:738` (`note.startsWith(VARIANT_TABLE_SOURCE_NOTE_PREFIX)`).
- What: the screen tells the line apart from answer-wide notes only by its opening words. A crafted note "Each row lists the conditions the variant's ClinVar record names, and also something answer-wide." after a table's last row rendered as an inline note under the table, and the Notes list was empty.
- Reproduction: crafted stream (table header, two `table_row`, `paragraph_break`, that `note`) through the real `useRunView` and `buildAnswerBlocks`: blocks `prose, H[Variant-to-disease mapping], records(2), NOTE[Each row lists the conditions the variant's C]`, systemNotes `[]`.
- Why it matters: the pin test only holds the frontend prefix to the backend line; nothing stops a second backend note from starting with the same words. The DECISIONS row of 2026-10-07 records this as a chosen trade-off against a new token kind. Filed so the risk is on the page; I judge it not blocking.
- NOT FIXED

### F-23-V-02: the concatenation arm for a second note on the same row is dead code
- Severity: minor. Not a regression.
- File: `frontend/src/hooks/useRunView.ts:739` (`openTableRow.noteAfter ? \`${...} ${note}\` : note`) with `:743` (`openTableRow = null` after every note).
- What: after the first note attaches, `openTableRow` is set to null, so a second matching note can never reach the concatenation branch. Probe "line emitted twice": the first attaches, the second goes to the Notes list. Harmless, but the code claims a behaviour it cannot have.
- NOT FIXED

### F-23-V-03: "Each row lists the conditions the variant's ClinVar record names" reads as complete, but the cell silently drops an unresolved condition and clips at 500 characters
- Severity: minor, unsure. Not a regression against develop (the cell behaviour predates card 23; the tightened sentence of part 2, `6ae00d28`, is what now reads as a completeness claim). It sits inside part 2's wording change, so I flag it, though I do not judge it blocking.
- File: `src/system_03_search_agent/synthesis/answer_layout.py:812` (`"; ".join(titles)[:500]`) under the line at `:342` to `:346`.
- Reproduction: `table_second_cell("SequenceVariant", {"clinvar_condition_ids": ["MedGen:C0342276", "MedGen:C9999999", "MedGen:C3661900"]}, {C0342276: "Maturity-onset diabetes of the young", C9999999: None, C3661900: "not provided"})` returned `'Maturity-onset diabetes of the young'`; `placeholder_link_count` returned 1, so the placeholder is disclosed in the Notes list but the unresolved C9999999 is disclosed nowhere. With 40 named conditions the cell is 500 characters ending mid-word: `'Some long hereditary condition name numb'`.
- Why it matters: a reader who opens the cited record and finds a condition the row did not list was told the row lists "the conditions" the record names. Low frequency (unresolved MedGen ids, or a variant with very many conditions; A-23-08 shows a lookup failure blanks every name, which removes the table and so the line too).
- NOT FIXED

### Probe record 3: the judge and adversary findings marked fixed

| Finding | Reproduced as the reviewer did | Result |
|---|---|---|
| J-23-01, A-23-01 | Real `write_node` with `_FOLDED_VARIANT_ROWS` alone (table last), at Researcher, Clinical brief, Deep technical and the structured fallback, then the real hook and screen (not a Python port) | Fixed: line under the table at desktop and phone, not in the Notes list (probe 1). On develop's frontend the same streams put it in the Notes list, so the probe discriminates |
| J-23-02, A-23-02 | Read the shipped constant (`answer_layout.py:342`); grep for "read live" in `frontend/src` and the test-queries document | Fixed: "looked up from NCBI", no "live" in the line |
| J-23-05 | `ruff check` over the whole repository on d0c19f53 | Fixed: "All checks passed!", the adversary probes are committed and clean |
| A-23-05 | Folded variant rows given `clinical_significance` and `ClinicalSignificance` "Likely benign" and a review status, through the real `write_node` at three technical depths | Fixed: the line carries no "assertion" or cause wording, says the classification is not shown, and no token text or cell mentions "benign" outside the line, so "not shown here" is true |

### Probe record 4: mutations of part 2's code changes (my own runner, a separate scratch worktree, each restored with `git checkout --`)

| Mutation | Result | Test that went red |
|---|---|---|
| M1 the `noteAfter` attach branch disabled (`useRunView.ts:738`) | Red | the two table-last arms (desktop, phone) in `answerLayout.test.tsx` |
| M2 the opening-words guard removed | Red | "leaves an answer-wide note after any table in the Notes list" |
| M3 no reset on `heading` (`:721`) | Survived, full frontend suite 517 passed | none (F-23-V-04) |
| M4 no reset on `table_header` (`:731`) | Survived, 517 passed | none (F-23-V-04) |
| M5 no reset after a note (`:743`) | Survived, 517 passed | none (F-23-V-04) |
| M6 any claim kind opens the table (`:853`) | Survived, 517 passed | none (F-23-V-04) |
| M7 `buildAnswerBlocks` ignores `noteAfter` (`AnswerScreen.tsx:388`) | Red | three card 23 arms |
| M8 frontend prefix back to "Each row is a condition" | Red | `test_card23_the_screen_finds_the_line_by_the_words_that_ship` |
| M9 backend line's first sentence back to "is a condition" | Red | `test_the_variant_to_disease_table_names_its_two_sources` |
| M10 helper returns the line for any mapped table | Red | `test_the_variant_to_disease_note_is_silent_off_its_own_table[Gene-True]` |
| M11 `graph.py` stops emitting the line | Red | `test_card23_the_source_note_sits_directly_under_the_variant_table` |
| M12 line emitted without its paragraph break | Red | the same |

### F-23-V-04: four of part 2's seven frontend edits survive mutation; no test holds the `openTableRow` resets
- Severity: minor. Not a regression against develop. Inside part 2's fix (`f5703691`), so flagged prominently, but I judge it not blocking: every survivor is a guard for a stream the backend cannot produce today.
- File: `frontend/src/hooks/useRunView.ts:721`, `:731`, `:743`, `:853`.
- Reproduction: M3 to M6 above, each against `src/answerLayout.test.tsx` and then the whole frontend suite: 15 of 15 and 517 of 517 passed with each mutation in place.
- Reachability, by probe 1 and probe 2: `write_node` emits the line only as `paragraph_break, note` directly after the variant table's last `table_row`, so a heading, a table header, a prose claim or a second matching note never sits between the row and the line. Under M6, though, a line that followed a prose claim would be attached to that claim as `noteAfter`, which `buildAnswerBlocks` renders only for table and list rows, so the line would vanish from the page entirely rather than fall back to the Notes list. Nothing pins that.
- Why it matters: the resets are what keep a future reordering of `_answer_tokens` from moving the line under the wrong table or deleting it, and a refactor could drop any of them with every test green.
- NOT FIXED

### Probe record 5: gates on d0c19f53, exact CI commands, run by me in a scratch worktree

| Gate | Result |
|---|---|
| gate02 `isort --check-only --diff src tests services tracker alembic .claude .github` | exit 0 |
| gate03 `ruff check` (whole repository) | "All checks passed!", exit 0 |
| gate04 `pytest -m "not integration" -q -rs --junitxml=unit-results.xml`, then `assert_no_db_skips.py` | 7093 passed, 143 skipped, 24 deselected, 1 xfailed in 477 s, exit 0; skip assertion exit 0 (load about 20 throughout) |
| gate08 `npm run build && npm test && python3 ../.github/scripts/assert_license_notices.py dist` | build clean, 59 files and 517 tests passed, license check ok, exit 0 |
| `check_public_leaks.py --base origin/develop` | PASS, 16 commits, 0 findings, 4 binary screenshots. I looked at all four: fixture data only, the sign-in email field blanked, and they show the line directly under the table at 1280 and 390, table last and with a gene list after |
| `tracker/check_doc_sync.py` | ok |
| Commit identity and trailers | every commit by the noreply address, no co-author trailer |

### F-23-V-05: the board row for card 23 still says the wiring is not built
- Severity: minor, unsure (the lead may move the card at merge time, as with earlier cards). Not a code regression.
- File: `testing/UI_fix_plan.md:53`, unchanged on the branch against develop.
- What: the row reads "Where we stopped, waiting on the product owner; a helper is on the 8.4 branch, its wiring in `core/graph.py` is not built". After this branch merges, the wiring is built, the owner's wording decision is taken, and the line is placed. `tracker/check_doc_sync.py` passes because it does not compare the row's prose with the code.
- Why it matters: the owner reads the board as the source of truth; a merged card still described as unbuilt sends them to retest nothing.
- NOT FIXED

### Probe record 6: end-to-end in a real browser (ports 5273 and 8931 waited free; another session's run held them first and was not touched)

- `CI=1 npx playwright test e2e/card23-source-note.spec.ts e2e/answer-layout.spec.ts e2e/long-variant-name.spec.ts` on d0c19f53: 17 passed (4 card 23, 9 answer layout, 4 long variant name).
- Discrimination: the same card 23 spec with `useRunView.ts` and `AnswerScreen.tsx` taken from develop: 2 failed (both "the table ends the answer", 1280 and 390), 2 passed (more records follow), so the spec measures the fix and not something both trees share.

## Verdict

PASS against card 23's goal: the line tells the reader the truth about where its rows come from, and sits directly under its own table at 1280 and 390, whether the table ends the answer or more records follow.

- No regression against develop. Develop's streams render identically on develop's and the branch's frontend; the backend's only change is the line and its paragraph break, under the variant-to-disease table only; every gate is green.
- Inside part 2's fix, flagged as the brief asks: F-23-V-04 (four of part 2's frontend guards survive mutation) and F-23-V-03 (the tightened sentence reads as complete while the cell can drop an unresolved condition or clip at 500 characters). Neither is reachable as a wrong placement or a wrong statement in today's streams, so I judge neither blocking. Whether either fires the review loop's stop condition is the lead's call.
- Other findings: F-23-V-01 (any note opening with the same words would attach, not reachable today), F-23-V-02 (a dead concatenation arm), F-23-V-05 (the board row still says unbuilt). All minor.

Verified by my own probes: the backend token streams of 14 shapes at four depths against develop; placement through the real hook and screen at desktop and phone widths for all 8 shapes that have the line, with develop's frontend as the control; 17 crafted streams aimed at the opening-words match; A-23-05 with rows that carry a classification; 12 mutations; the three e2e specs and the card 23 spec's power to tell develop's screen from the branch's; gates 02, 03, 04, 08, the leak scan and the doc sync check; the four committed screenshots, looked at.

Only read, not run: the saved-answer markdown and the command line and MCP surfaces (the adversary ran them; part 2 did not touch them); the DECISIONS rows and query 79's text, beyond what their tests check; no live model, graph or NCBI call was made.
