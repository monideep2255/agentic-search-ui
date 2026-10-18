# Card 23 fix round, part 1

One fix-and-verify round on branch `fix/card23-source-note`, after the judge (`judge.md`) and adversary (`adversary.md`) rounds. The owner was asleep and had approved going with the lead's recommendations; this round carries them out. Nothing under `frontend/` was touched: card 22 edits the same screen files in another worktree, so the placement fix waits for part 2.

## Table of contents

- [In the user's words](#in-the-users-words)
- [The classification question](#the-classification-question)
- [Commits](#commits)
- [Every finding](#every-finding)
- [Tests and mutations](#tests-and-mutations)
- [Gates](#gates)
- [For the lead](#for-the-lead)
- [Part 2](#part-2)

## In the user's words

A person who asks "What diseases are caused by variants in the HNF1A gene?" at Researcher depth now reads, with the "Variant-to-disease mapping" table:

> Each row is a condition the variant's ClinVar record names; the record's classification (for example pathogenic, benign or uncertain) is not shown here. Disease names are MedGen titles looked up from NCBI.

Before, the line called every row a "ClinVar assertion". Beside a likely benign variant shown with "Maturity-onset diabetes of the young", that read as "ClinVar says this variant causes this disease". The new line tells the reader the table does not say which way ClinVar classified the variant, so they know to open the record before drawing that conclusion.

## The classification question

The lead's first choice was to show each row's ClinVar classification as its own column. That needs the graph to hold it. It does not.

| Check | Result |
|---|---|
| System 1's ClinVar parser (`parse_variant_summary.py`, reference repository, read only) | Reads `ClinicalSignificance` and `ReviewStatus` and passes them to `map_node` as `clinical_significance` and `review_status` |
| The live graph, five HNF1A variants from the adversary's evidence (ClinVar 1134661, 1036297, 1043641, 1025247, 1173962), one read-only query each | Every vertex carries only `agent_type, id, knowledge_level, name, source, source_url, xrefs`. No `clinical_significance`, no `review_status` |
| All HNF1A variants with a disease link, `v.clinical_significance` | 500 of 500 empty |
| The `has_phenotype` edges out of 1134661 and 1173962 | Only `source, agent_type, source_url, knowledge_level` |
| System 3's own code | No graph-path reader of a classification; `answer_layout._STATUS_FIELDS` has none |

So the classification was dropped somewhere between the parser and the load, and the template returns the whole vertex, so nothing in System 3 could recover it. Showing it would need either a graph reload (System 1, outside this repository) or a new live ClinVar call per row (a new Layer 2 lookup, a design change with its own cost and speed budget). Neither is safe tonight, so I took the second path: reword the line so it implies no cause.

The probes were two throwaway scripts in the session scratchpad, read only through `graph_connection.execute_cypher` with every value a parameter, the way `testing/Developer/reports/2026-09-23_overnight/probe_disease_names.py` reads the graph. They are not committed.

## Commits

| Commit | What |
|---|---|
| `3b1d89da` docs(card23): Add the judge and adversary reports | The two reports and the adversary's four probe scripts, with lint-only fixes (unused `noqa` markers removed, imports sorted) so gate03 passes (J-23-05) |
| `6a229f57` fix(write): The variant-to-disease line no longer implies the variant causes the disease | The new first sentence, the reason in a source comment, the pinned-text test updated, one new test (A-23-05) |
| `9b8a064a` fix(write): Say disease names are looked up from NCBI, not read live | "looked up from NCBI" in the line and in the table comment, one new test (J-23-02, A-23-02, the owner's wording decision of 2026-10-06) |
| `f3247caf` docs(test-queries): Quote the shipped line under query 79 and drop the placement promise | Query 79 quotes the shipped line word for word and says where it shows today, with no "directly under that table" promise; one new test |

## Every finding

| Finding | Outcome | Why |
|---|---|---|
| J-23-01, the line leaves the table when the table ends the answer | Deferred to part 2 | The fix is in `frontend/src/hooks/useRunView.ts` and `AnswerScreen.tsx`, which card 22 is editing. Query 79 now says where the line shows until then |
| J-23-02, "read live" overstates a week-long title cache | Fixed, `9b8a064a` | The owner's wording, "looked up from NCBI" |
| J-23-03, titles shown in reading order | Not in scope | Same as A-23-03 below |
| J-23-04, the cherry-picked commit's subject is not in sentence case | Not in scope | Behaviour is unaffected, and rewording `2f7850bd` means rewriting the branch's history under three later commits. The judge suggested no fix |
| J-23-05, the adversary's probes fail gate03 | Fixed, `3b1d89da` | Lint-only fixes; gate03 passes over the whole repository |
| A-23-01, same as J-23-01 | Deferred to part 2 | As J-23-01 |
| A-23-02, same as J-23-02 | Fixed, `9b8a064a` | As J-23-02 |
| A-23-03, "Familial breast-ovarian cancer susceptibility 1" for MedGen's "Breast-ovarian cancer, familial, susceptibility to, 1" | Not in scope | Every word comes from the MedGen title by a closed rule, the source claim stays true, and both reviewers judged it not misleading |
| A-23-04, the command line and MCP answers show the line without the disease column | Not in scope | The command line already drops a table row's cells; the real fix is rendering cells there, a separate card |
| A-23-05, "ClinVar assertions" beside likely benign and uncertain rows | Fixed, `6a229f57` | Reworded; the classification is not in the graph (above) |
| A-23-06, one link no longer in today's ClinVar record | Not in scope | Graph snapshot drift, not this card's code. A dated snapshot claim belongs with how the graph's age is shown answer-wide |
| A-23-07, build.md's live metric is misnamed | Not in scope, not in the brief | The adversary checked the six names against live MedGen titles itself: all six match exactly, so the claim held. `build.md` stays as the builder's record |
| A-23-08, 22 or more uncached MedGen ids fail the lookup, and a failure is cached for a week | Not in scope | Pre-existing in `synthesis/disease_names.py`, and the line fails closed (no table, no line). It needs its own card |

## Tests and mutations

Three new tests in `tests/system_03_search_agent/synthesis/test_answer_layout.py`, plus the pinned-text test and the wording arm in `test_write_answer_structure.py` moved to the new text ("ClinVar record" in place of "variation record"). Each mutation was applied, the test run, and the file restored from a copy.

| Test | Mutation | Turns red |
|---|---|---|
| `test_card23_the_note_never_implies_the_variant_causes_the_disease` | The line put back to "Variant-to-disease links are ClinVar assertions" | Yes |
| The same | `clinical_significance` added to `_STATUS_FIELDS`, so a variant row shows "Status: Likely benign" while the line says the classification is not shown | Yes |
| The same | "is not shown here" replaced by "is in the record" | Yes |
| `test_card23_the_note_makes_no_freshness_claim_about_disease_names` | "read live from NCBI" put back | Yes |
| `test_card23_query_79_quotes_the_line_that_ships` | Query 79 quoting "read live from NCBI" | Yes |
| The same | Query 79 saying "Directly under that table" again | Yes |

Results: card 23's five arms in `test_write_answer_structure.py` pass; `tests/system_03_search_agent/synthesis/` 611 passed, 10 skipped, 1 xfailed.

No live answer was run: no column was added, and the line's text is code-built, so the tests above cover it.

## Gates

| Gate | Result |
|---|---|
| gate02, import order | Pass |
| gate03, lint over the whole repository | Pass |
| gate04, the whole unit suite | Pass on the second run: 7038 passed, 143 skipped, 1 xfailed, started at load under 8. The first run started at load 7.9, but the machine climbed to about 50 during it, and one test failed: `tests/ci/test_gate_scripts.py::TestGate6PythonAudit::test_it_passes_on_this_project_s_requirements`. Its subprocess ran past its 120 second limit under that load, and no code this round touched is involved |
| `check_public_leaks.py --base origin/develop` | Pass, 8 commits, 0 findings |
| `tracker/check_doc_sync.py` | Pass |

## For the lead

- A `DECISIONS.md` row is due for the reworded line. `DECISIONS.md:693` still quotes the 2026-09-25 wording, and the file is append-only, so a new row supersedes it. I did not write it.
- One wording nuance in the lead's text: "Each row is a condition" while a row can name two (live r1, c.737T>G: "Maturity-onset diabetes of the young type 3; Monogenic diabetes"). I kept the approved text verbatim. If the owner wants it exact, "Each row's conditions are those the variant's ClinVar record names" fixes it with the same meaning.
- The graph lost ClinVar's classification and review status on load. Restoring them is System 1 work in the data-engineering repository; once they are back, the table can show a classification column and this line can drop its "not shown" clause. The new test goes red the day the table shows one, which forces the line to be revisited.
- Part 2: the J-23-01 placement fix in the frontend after card 22 merges, then "directly under that table" back into query 79 and into its test.

## Part 2

Branch `fix/card23-source-note`, 2026-10-07, after card 22 merged into `develop`. The placement fix part 1 deferred, the tightened first sentence, and query 79's placement promise put back.

### In the user's words, part 2

A person who asks "What diseases are caused by variants in the HNF1A gene?" at Researcher depth now reads this line directly under the "Variant-to-disease mapping" table, at 1280 and 390, whether more records follow the table or the table ends the answer:

> Each row lists the conditions the variant's ClinVar record names; the record's classification (for example pathogenic, benign or uncertain) is not shown here. Disease names are MedGen titles looked up from NCBI.

Before, when the table ended the answer, the line showed first in the Notes list after the answer, away from the table it describes. "Lists the conditions" replaces "is a condition" because one row can name two (live c.737T>G: "Maturity-onset diabetes of the young type 3; Monogenic diabetes").

### Commits, part 2

| Commit | What |
|---|---|
| `1608817f` Merge origin/develop | Card 22's merge brought in. One conflict, `DECISIONS.md`, where both sides only appended rows: develop's nine rows kept first, then this branch's card 23 row. `graph.py`, `answer_layout.py`, `test_answer_layout.py` and the test-queries document merged on their own |
| `6ae00d28` fix(write): Say each variant row lists the conditions its ClinVar record names | The backend constant, its pinned test and query 79's quote |
| `f5703691` fix(web-ui): Keep the variant-to-disease source line directly under its table | `useRunView.ts` attaches the line to the table's last row when it arrives straight after it (`noteAfter`); `AnswerScreen.tsx` renders it right after that table; four vitest arms, a backend pin test, and `e2e/card23-source-note.spec.ts` |
| `3f2dd25d` docs(test-queries): Promise the source line directly under its table again | Query 79 says "Directly under that table, at 1280 and 390, whether more records follow it or the table ends the answer; never in the Notes list"; its test requires that |
| `a8b7f844` docs(decisions): Record card 23's tightened first sentence and how the line stays under its table | Two appended rows: the sentence, and the placement mechanism with the alternatives |

### Every finding, part 2

| Finding | Outcome | Why |
|---|---|---|
| J-23-01, the line leaves the table when the table ends the answer | Fixed, `f5703691` | The line attaches under its own table in the hook, so it no longer waits for a later sentence that never comes |
| A-23-01, same as J-23-01 | Fixed, `f5703691` | As J-23-01 |
| The fix round's wording nuance, "Each row is a condition" | Fixed, `6ae00d28` | "Each row lists the conditions", the lead's text |

How the screen recognises the line: by its opening words, `VARIANT_TABLE_SOURCE_NOTE_PREFIX`. Nothing else on the wire tells it apart from an answer-wide note that also follows a table, and attaching every such note would move "no written summary", the findings-tail note and the placeholder note under whatever table came last. A new token kind would change the event contract for one line. `test_card23_the_screen_finds_the_line_by_the_words_that_ship` holds the prefix to the backend constant.

### Tests and mutations, part 2

| Test | Mutation | Turns red |
|---|---|---|
| `answerLayout.test.tsx`, card 23 block (4 arms) | Both source files back to the pre-fix code | Yes, the two table-last arms (1280 shape and phone) |
| The same | The `noteAfter` attach disabled in `useRunView` | Yes, the two table-last arms |
| The same | The prefix guard removed, so any note after a table attaches | Yes, "leaves an answer-wide note after any table in the Notes list" |
| The same | `buildAnswerBlocks` ignores `noteAfter` | Yes, three arms |
| `test_card23_the_screen_finds_the_line_by_the_words_that_ship` | The frontend prefix put back to "Each row is a condition" | Yes |
| `test_card23_query_79_quotes_the_line_that_ships` | Query 79 without "Directly under that table" | Yes |
| `e2e/card23-source-note.spec.ts`, 4 tests | Both source files back to the pre-fix code | Yes, both table-last tests (1280 and 390); the more-records tests stayed green, as expected |

Each mutation was restored from a copy; `git status` showed no tracked change afterwards.

### On screen, part 2

`CI=1 CARD23_SHOTS=1 npx playwright test e2e/card23-source-note.spec.ts`, ports 5273 and 8931 free first: 4 passed. Each test checks the element right after the table's block is the line, the line starts within 48 pixels below the table, the Notes list holds the placeholder note and not the line, and there is no sideways scroll. Screenshots: `part2_table_last_1280.png`, `part2_table_last_390.png`, `part2_more_after_1280.png`, `part2_more_after_390.png`. In the full-page shots the app's fixed footer is painted across the middle of the page; that is the screenshot method, not the layout. `e2e/answer-layout.spec.ts` and `e2e/long-variant-name.spec.ts` also pass (13 tests); the answer-layout run rewrote its 2026-09-14 screenshots, which were restored with `git checkout`.

### Gates, part 2

| Gate | Result |
|---|---|
| gate02, import order | Pass, exit 0 |
| gate03, lint over the whole repository | Pass, "All checks passed!" |
| gate04, the whole unit suite | Pass: 7093 passed, 143 skipped, 24 deselected, 1 xfailed |
| gate08, frontend build, tests and license notices | Pass: build clean, 59 files and 517 tests passed, license check ok |
| `check_public_leaks.py --base origin/develop` | Pass: 16 commits, 0 findings; the four part 2 screenshots are binary, so I looked at each: fixture data only, the sign-in email masked |
| `tracker/check_doc_sync.py` | Pass: "the board, the done file, the test queries, the board plan, the Factory brief, the handoff and the registry agree" |

The worktree had no `node_modules`; the main checkout's, from the identical `package-lock.json`, was linked in for the run and unlinked afterwards. Nothing was installed.
