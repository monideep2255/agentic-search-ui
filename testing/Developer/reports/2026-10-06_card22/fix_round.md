# Card 22 fix round

The one fix round for card 22, 2026-10-06, on `fix/card22-name-every-total` from f82c1230. It answers the judge's findings J-22-01 to J-22-09 and the adversary's A-22-01 to A-22-10 (`judge.md`, `adversary.md` in this folder), and carries out the owner's decision of the same evening on a page cited from two layers.

## Table of contents

- [What a person sees now](#what-a-person-sees-now)
- [Findings](#findings)
- [Choices and their alternatives](#choices-and-their-alternatives)
- [Mutations](#mutations)
- [Gates](#gates)
- [Not fixed and left for a card](#not-fixed-and-left-for-a-card)

## What a person sees now

| Where | Before this round | After |
|---|---|---|
| One gene page cited from the graph and from a live lookup | One card labelled "L1 · graph"; the Live NCBI APIs group gone; "1 source cited from 1 layer" | One card labelled "L1 · graph, L2 · live" under Knowledge graph; Live NCBI APIs still shows and names the page and where its card is; "1 source cited from 2 layers" |
| A reopened saved answer, BRCA1 evidence | "Based on 16 sources cited" above 18 rows, the gene page three times | 16 rows, the gene page once as "1, 6, 9." |
| YOUR SEARCHES after a reload | "18 sources · Oct 6" | "16 sources cited · Oct 6", the live item's number and words |
| "Confirmed by N independent databases" | N counted every claim's database, and a live record by its tool name | N counts the databases whose records state the confirmed fact, read off the record page; with fewer than two, the line says "not yet confirmed" |
| The trust line's info card | "Not yet confirmed" explained only as a missing second database | Names both causes: a fact not yet found in a second database, or an answer that may be incomplete |
| Opening line, graph and live link to one gene | "Found 2 gene records for BRCA1: BRCA1 [1] and BRCA1 [2]" | One record, one marker |
| Truncation note and "more to show" count | Counted numbered citations and called them records | Count record pages |
| Command line | "Based on 16 sources cited" above 18 numbered references | 16 reference lines; "[1][6][9] NCBIGene - ..." on one line |

## Findings

Line numbers are on this branch after the round.

| Finding | Status | What changed | Test that holds it |
|---|---|---|---|
| J-22-02, A-22-09 | Fixed | `groupSourcesByLayer` (`frontend/src/components/screens/AnswerScreen.tsx:607`) keeps one card per page, records every layer (`MergedSource.layers`, `nsByLayer`) and fills `SourceGroup.alsoCited`; the card names every layer (`:2103`, `sourceLayerLabel` at `:526`); a group with only a shared page still renders a line naming it (`:2013`); `citedSourceCounts` (`:558`) counts every layer any cited page came from. The author's unit test that pinned "1 layer" now pins "2 layers". | `AnswerScreen.card22.test.tsx`: "counts every layer a cited page came from ...", "shows one card naming both layers, keeps the live group ..."; e2e `card22-name-every-total.spec.ts`, the new cross-layer test at 1280 and 390 |
| J-22-07 | Fixed | The rule, written in the docstring at `AnswerScreen.tsx:607`: the card sits under the group of the lowest-numbered layer it was cited from, whichever citation came first. | "files a page cited from two layers under the lowest-numbered layer, whichever was cited first", which runs both orders |
| J-22-04, A-22-05 | Fixed | `savedSourceRows` (`frontend/src/components/screens/SavedAnswerScreen.tsx:106`) keys rows by `sourcePageKey`, carrying every citation number and layer; the list renders rows (`:340`). | "lists one row per page, so its rows agree with its stored trust line" (16 rows, one gene row, "1, 6, 9."), "names every layer a merged row was cited from ..." |
| J-22-05, A-22-06 | Fixed, no migration | `_citation_count` (`src/system_03_search_agent/feedback/history.py:149`, helper `_stored_page_key` at `:235`) counts the distinct pages of the stored citation payloads, from the `source_url` each one already carries; the rail labels it "sources cited" (`frontend/src/App.tsx:272`). The wire field keeps its name, `citation_count`. | `test_the_history_rail_count_after_a_reload_counts_pages`, `..._never_merges_what_it_cannot_read`, `..._agrees_with_the_trust_line_on_the_evidence`; the database round trip in `feedback/test_history.py` now seeds a slash pair and reads 2; `App.test.tsx` pins "3 sources cited" |
| A-22-01, A-22-02, J-22-03 | Fixed within the line | `record_database` (`src/system_03_search_agent/synthesis/trust.py:537`) reads the database off the record page (NCBI path, subdomain or research resource; other hosts by name), then the CURIE prefix, never the tool. `_databases_backing` (`:586`) counts the databases whose records state the same bucketed value for the same field. `answer_trust_line` (`:605`) takes `all_findings`, and N is the smallest count over the confirmed facts (`:713`); under two, the line says "not yet confirmed". `core/graph.py:13872` passes the pool. | `test_confirmed_counts_only_the_databases_that_state_the_fact` (2, not 5), `test_a_graph_row_and_a_live_fetch_of_one_record_confirm_nothing`, `test_the_graph_gene_page_and_the_live_gene_page_are_one_database`, `test_agreement_is_read_from_the_whole_findings_pool`, `test_a_record_stating_a_different_value_does_not_count_as_agreeing`, `test_with_several_confirmed_facts_n_is_what_every_one_of_them_has`, the 13 `test_a_record_counts_by_its_database_not_its_tool` cases; two older tests in `test_answer_layout.py` rebuilt with records that actually agree |
| J-22-08 | Fixed | `TRUST_LINE_EXPLAINER` (`AnswerScreen.tsx:103`) now reads "... or this answer may be incomplete, for example because a search did not finish or more records were found than it lists." | "explains a not-yet-confirmed answer that is incomplete ..." |
| A-22-03 | Fixed | The opening line's `by_page` (`src/system_03_search_agent/synthesis/answer_layout.py:1027`) and the restatement gate's `shown_by_url` (`:866`) key by `source_page_key`; the stale "exact `source_url`" comment is rewritten. | `test_the_opening_line_counts_one_record_per_page` |
| A-22-04 | Fixed | `_cited_page_count` (`src/system_03_search_agent/core/graph.py:10270`) feeds the truncation note's `shown` (`:13568`) and the remaining count (`:13848`). | `core/test_graph.py::test_truncation_note_and_more_to_show_count_record_pages_not_citations` (150 rows through `write_node`, one page cited through both spellings), `test_the_truncation_count_counts_pages` |
| J-22-06, A-22-08 | Fixed | The references block (`src/system_03_search_agent/adapters/cli/render.py:1102`) prints one line per page with every marker on it, in first-cited order. | `test_the_command_line_lists_one_reference_per_page` (16 lines, "[1][6][9] NCBIGene - ...", every marker still listed) |
| J-22-09, A-22-10, A-22-11 | Fixed | `useRunView.ts:1171` says 16 and states the layer rule; the `answer_trust_line` docstring says the count is keyed by `source_page_key` and the "source(s))" typo is gone. | Comments only |
| J-22-01, A-22-07 | Not fixed, as briefed | None. | None |

Where the page key lives now: `source_page_key` moved from `synthesis/trust.py` to `contracts/events.py:190`, beside `NCBI_SOURCE_URL_PATTERN`, and `trust.py` re-exports it. The command line imports only the contracts module, and importing `synthesis.trust` costs about two seconds (it pulls in the model harness), which the command line should not pay to print references.

J-22-01 and A-22-07, not fixed: Python's `strip()` and JavaScript's `trim()` disagree only on a leading U+FEFF and on trailing U+001C to U+001F and U+0085. `NCBI_SOURCE_URL_PATTERN` rejects every one of those characters, so no citation a person sees can carry one, and no total on the screen can differ because of it.

## Choices and their alternatives

| Choice | Alternatives considered | Why |
|---|---|---|
| A page cited from two layers sits under its lowest-numbered layer | The layer cited first; the layer cited last | It is the first group in the list that holds the page, and it does not move when the citation order changes. |
| The other layer's group shows a line, "[2] NCBIGene 672: one card for this page, listed under Knowledge graph" | A second card; an empty group | The owner said one card. A line keeps the group and the live lookup visible without a second card. |
| A group's badge counts pages cited from that layer, its own cards plus shared pages | Its own cards only | A badge of 0 on a group that holds a cited page reads as broken. The SOURCES heading still counts distinct pages, so in the two-layer case the badges add to one more than the heading, and the line under the group says why. |
| The merged card's tool line names every tool that cited the page | The first citation's tool only | Same reason as the layer label: no citation points at a card that names a different tool. |
| N is the smallest agreeing-database count over the confirmed facts | The union over all confirmed facts; the largest count | "Confirmed by N" must hold for every confirmed fact. The union could count databases that agree on different facts. |
| Under two agreeing databases, the line says "not yet confirmed" | Fall back to "Based on S sources cited" with no qualifier | The fact is high stakes and has one database behind it, which is what "not yet confirmed" tells the reader. |
| A record with neither a page nor a CURIE names no database | Fall back to the tool name | A tool is not a database; uncounted is honest, counted by tool overstates. |
| The rail's wire field keeps the name `citation_count` | Rename it, or add a field | A rename breaks the v1 history contract and the MCP `past_searches` output. The docstring says what it counts. |
| Saved-answer rows read "1, 6, 9. BRCA1" | "[1][6][9] BRCA1" as on the live card | A single row keeps its existing "1. BRCA1" form, so its tests and its look stay as they were. |

## Mutations

Each mutation was applied alone, the named tests run, and the file restored from a copy; `git status` showed only this round's changes afterwards.

| Mutation | Result |
|---|---|
| M-B1 `record_database` keys by tool | Caught, 16 failed |
| M-B2 confirmed line counts every claim's database again | Caught, 3 failed |
| M-B3 agreement ignores `all_findings` | Caught, 2 failed |
| M-B4 largest count instead of smallest | Caught, 1 failed |
| M-B5 agreement ignores the value | Caught, 1 failed |
| M-B6 rail count back to `len(stored)` | Caught, 2 failed |
| M-B7 opening line keyed by exact URL | Caught, 1 failed |
| M-B8 command line one line per citation | Caught, 1 failed |
| M-B9 page count helper counts citations | Caught, 1 failed |
| M-B10 truncation note `shown=len(citations)` | Caught, 1 failed (`core/test_graph.py`) |
| M-B11 remaining count `known_total - len(citations)` | Caught, 1 failed (`core/test_graph.py`) |
| F-M1 card sits under the first-cited layer | Caught, 1 failed |
| F-M2 card sits under the last-cited layer (the judge's M2) | Caught, 2 failed |
| F-M3 card names only its group's layer | Caught, 1 failed |
| F-M4 a group with only a shared page vanishes | Caught, 3 failed |
| F-M5 the shared-page line is not rendered | Caught, 1 failed |
| F-M6 saved rows one per citation | Caught, 2 failed |
| F-M7 info card back to one cause | Caught, 1 failed |
| F-M8 rail label without "cited" | Caught, 1 failed |
| F-M9 group badge counts its own cards only | Caught, 1 failed |

## Gates

Run with the main checkout's virtual environment first on PATH, load average about 18 from other work.

| Gate | Result |
|---|---|
| gate02, import order | Pass, "Skipped 2 files", exit 0 |
| gate03, lint, `ruff check` with no path | Fails only on the reviewers' untracked probes under `raw/adversary/` (10 findings: I001 and SIM115 in `probe_cli.py`, `probe_confirmed.py`, `probe_parity.py`, `probe_summary.py`). With that folder excluded: "All checks passed!". Every intermediate commit's changed Python files also lint clean. |
| gate04, whole unit suite | Pass: "7068 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 497.84s". The local user database was reachable, so `feedback/test_history.py` ran: 16 passed. |
| `npm run build` | Pass |
| `npm test` | Pass: "Test Files 59 passed (59), Tests 513 passed (513)" |
| `CI=1 npx playwright test e2e/card22-name-every-total.spec.ts` | Pass: "4 passed (22.5s)", the BRCA1 evidence and the new two-layer test, each at 1280 and 390 |
| `check_public_leaks.py --base origin/develop` | PASS, 0 findings over 11 commits; 12 binary files listed for a person to look at, all untracked and none committed by this round |

## Not fixed and left for a card

- The per-claim check still compares tools. `triangulate` keys origin by `_origin_of`, the tool name unless the field is a CURIE, so a graph ClinVar row and a live fetch of the same record are still "concordant" per claim. The line no longer repeats that as confirmation, but the claim's own `trust_signal` still reports `triangulated: true` and the answer's outcome stays `answer`. Moving `triangulate` onto `record_database` changes trust outcomes, so it is a card of its own.
- Agreement is compared by field and value, not by subject: two records stating "Pathogenic" for different variants agree under both `triangulate` and the new count. Inherited from `triangulate`.
- The MCP `ask` output still returns the trust line beside the full per-citation list (J-22-06's second surface); a client that prints the list one line per citation shows more lines than sources.
- J-22-01 and A-22-07, above.
