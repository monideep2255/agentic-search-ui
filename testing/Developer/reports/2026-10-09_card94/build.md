# Card 94 build: each isolate's place, and one isolate's details

Build report, 2026-10-09, branch `fix/card94-isolate-place-lookup`, cut from `develop` at `b01dee92`. Paths are relative to `<repo-root>`. Diagnosis: `testing/Developer/reports/2026-10-08_overnight/card94_diagnosis.md`.

In the user's words: "An isolate answer shows each isolate's place, and naming one isolate gets that isolate's details."

Kept. The "from 2023" follow-up is card 20's and is not touched here.

After review, the card was split (lead, 2026-10-09): the place half ships, and the lookup of one named isolate was taken out and parked for the owner. The sections below "Fix round" record the build round as it was built; "Fix round" and "Parked" say what changed after it.

## Table of contents

- [What changed](#what-changed)
- [One departure from the diagnosis](#one-departure-from-the-diagnosis)
- [What a person sees](#what-a-person-sees)
- [Tests](#tests)
- [Live probe of the lookup](#live-probe-of-the-lookup)
- [Gates](#gates)
- [Not covered and left open](#not-covered-and-left-open)
- [Fix round](#fix-round)
- [Parked](#parked)

## What changed

| Slice | Where | Change |
|---|---|---|
| Place | `synthesis/answer_layout.py`, `isolate_place` and `collected_with_place` | An isolate row's place is read verbatim from its own `geo_loc_name`. Its "Collected" cell reads when, then where: "2013, USA: Minnesota". A half the record does not hold is named: "2013, place not recorded", "USA: Minnesota, date not recorded", or "Not recorded" for neither. |
| Place | `core/graph.py`, the inner `grouped_listing` of the answer listing | The cell is built there for isolate rows only. An isolate table shows the "Collected" column even when no isolate holds a date, so the place is never dropped with it. Every other table is unchanged. |
| Single isolate | `core/graph.py`, `plan_node`'s accession branch | A BioSample asked about as a Pathogen Detection isolate of a named organism also plans `pathogen_detection` in `isolate_lookup` mode, first, beside the BioSample summaries it planned before. The organism is the one the existing isolate shape (`isolate_search.parse_isolate_question`) reads from the question; with none named there is no taxon folder to read, and the plan is unchanged. |
| Accession column | none | Already shown under "Identifier", as the lead noted; left as it is. |
| Tool | none | `tools/pathogen_detection.py`'s lookup mode already returns strain, place, date, genes and the isolate's page; it needed no change. |

The lookup row reaches the answer through the same shaping as an isolate search (`_layer_tool_output_to_structured_fields`): one row, `truncated` false, and no count line, since the count line belongs to an isolate search only.

## One departure from the diagnosis

The diagnosis proposed a separate "Place" column. A table row carries at most four cells (`contracts/events.py`, `TokenPayload.cells`, `max_length=4`), and the isolate table already uses four: Isolate, Identifier, AMR genes, Collected. A fifth column failed validation in the first test run. Widening the bound is an event contract change outside this card's fence, so the place shares the "Collected" cell instead.

If the owner prefers a column of its own, the change is one line, `max_length=5` on `cells`, additive as item 12.9's widening from two to four was, plus moving the place out of `collected_with_place` into its own cell.

## What a person sees

| Question | Before | After |
|---|---|---|
| Query 33, `What Escherichia coli isolates in Pathogen Detection carry extended-spectrum beta-lactamase genes?` | "Collected" shows the year only | "Collected" shows "2013, USA: Minnesota", or says which half is not recorded |
| Query 42, `What is known about Salmonella isolate SAMN02147118 in Pathogen Detection?` | The BioSample summary only: no strain, place, date, genes or Pathogen Detection link | One isolate row: strain, BioSample accession, genes, "Collected" with year and place, linked to its Pathogen Detection page; the BioSample record and its runs beside it; no "first 20" line |
| `What is BioSample SAMN02147118?` | BioSample summary | Unchanged |

`testing/Test_queries_and_workflows.md` queries 33 and 42 now say this.

## Tests

New or changed arms, in `tests/system_03_search_agent/core/test_isolate_search_wiring.py` unless named:

| Test | Proves |
|---|---|
| `test_an_isolate_row_shows_its_place_or_says_none_was_recorded` | The place is read verbatim; other record types get none; each missing half is named |
| `test_the_isolate_table_shows_each_isolates_place_beside_when`, Researcher and Plain language | Through `write_node`: "2013, USA:AZ", "2013, place not recorded", "Mexico, date not recorded" |
| `test_an_isolate_table_with_no_dates_still_shows_each_place` | With no dates at all the column still shows each place |
| `test_naming_one_isolate_plans_the_tools_lookup_of_that_isolate_first` | The lookup is planned first, taxon `Salmonella`, accession `SAMN02147118`, then the BioSample and SRA summaries, no graph call |
| `test_a_biosample_question_naming_no_isolate_organism_plans_no_lookup` | Populate check: no organism named, no lookup |
| `test_one_isolates_answer_shows_its_details_with_no_sample_note` | The lookup's one isolate becomes one full row, cited to its Pathogen Detection page, with no count line |
| `test_write_puts_the_count_under_an_isolate_answer` (changed) | Its pinned row now ends "2013, USA:AZ" |
| `test_write_answer_structure.py::test_card94_plain_language_isolates_show_the_genes_table` (changed) | Its fixture rows hold no place, so the cell reads "2023, place not recorded" |

Red on the old code: the new and changed tests run against `develop`'s `graph.py` and `answer_layout.py`, 8 failed and 63 passed. The populate check passes on both, as it should.

One property broken at a time, then restored:

| Mutation | Result |
|---|---|
| `isolate_place` never reads the place | 6 failed, 14 passed |
| The lookup is never planned | 1 failed, 19 passed |
| The isolate table no longer forces the "Collected" column | 1 failed, 19 passed |
| Restored | 20 passed |

## Live probe of the lookup

One live, read-only call of the tool, no model call: `isolate_lookup`, taxon Salmonella, SAMN02147118.

| Field | Value |
|---|---|
| Strain | SQ0227 |
| Place | USA: Western Region |
| Collected | 2013 |
| Genes | ant(2'')-Ia, aph(3')-Ia, blaTEM-1, catA1, dfrA10, mdsA, mdsB, sul1 |
| Cluster | PDS000032687.5 |
| SNP distance | none |
| Total time | 20.8 s, then 20.3 s on a second run |

Where the second run's time went:

| Read | Seconds | Rows |
|---|---|---|
| Snapshot | 0.2 | |
| Metadata | 0.0 | 1 |
| Cluster list | 1.7 | 1 |
| SNP distances | 18.3 | 0, cut by its 20-second sub-budget |

So 18.3 of the 20.3 seconds are spent on the SNP-distance enrichment, which found nothing and whose value the answer does not show. An answer to query 42 will take longer than 20 seconds. Skipping or shrinking that scan in lookup mode is inside this card's fence, but it reverses adversary finding F-3.5-A-05, which made the partial scan count, so it is left for the owner to decide.

## Gates

| Gate | Result |
|---|---|
| `tests/system_03_search_agent/synthesis`, not integration | 753 passed, 10 skipped, 1 xfailed |
| `tests/system_03_search_agent/core`, not integration | 1485 passed, 56 skipped, 1 deselected |
| `ruff check` on the four touched Python files | pass |
| `isort --check-only` | pass on `answer_layout.py` and both test files. `core/graph.py` fails with the same report on `develop` at `b01dee92` (the `contracts.events` import block); this change adds nothing to it. |

## Not covered and left open

- A BioSample isolate question that names no organism. The diagnosis's second-round call (read the organism from the BioSample summary, then look up) was outside the fence.
- The deployed app and the 20-second ceiling for query 42, above.
- Card 20's "from 2023" follow-up.

## Fix round

Review: `judge.md` (verdict FIX FIRST) and `adversary.md` (verdict FAIL), both in this folder.

| Finding | What changed |
|---|---|
| J-94-03, J-94-04, J-94-05, J-94-06, J-94-07, A-94-01, A-94-02, A-94-03, A-94-04, A-94-08, A-94-09 | The lookup of one named isolate is taken out. `plan_node`'s accession branch in `core/graph.py` is again exactly develop's, so a BioSample question plans the two NCBI summaries and nothing else. The three tests that pinned the lookup are removed, and query 42 in `testing/Test_queries_and_workflows.md` is back to develop's text. Each of these findings lives in the lookup's planning or its Act path, so none is reachable from this branch now. See "Parked". |
| J-94-01, A-94-05 | A missing value word in the place field is not a place. `isolate_place` in `synthesis/answer_layout.py` treats "missing", "not applicable", "not collected", "not provided", "restricted access", any "missing: reason" form, "NULL", "unknown", "N/A" and "NA", in any case, and a blank as no place, so the cell reads "2013, place not recorded". The words sit in one named constant, `PLACE_PLACEHOLDERS`, whose comment cites the INSDC missing value reporting list; the codebase had no such list before. A real place that only contains such a word ("USA: Unknown County") is still shown. |
| J-94-01, the date half | Checked, no change. The date half reads only a four-digit year from `collection_date`, so a placeholder date gives no year and the isolate cell already says "date not recorded". Probe: date "missing", place "USA" reads "USA, date not recorded"; both placeholders read "Not recorded". Outside isolate tables a placeholder date still leaves the "Collected" cell blank, as on develop; this card does not touch those tables. |
| J-94-02, A-94-06 | A place longer than 128 characters is cut to fit and ends with "…", the mark the module already uses for a cut sentence, so a cut place never reads as the whole place. A place that fits is shown whole, with no mark. |
| A-94-07 | Confirmed, no change. Both surfaces render the cell as text. The live answer (`AnswerScreen.tsx`) puts each cell in a React text child, and the saved answer (`savedAnswerMarkdown.tsx`) parses `feedback/capture.py::_cell`'s escaped markdown into typed nodes, with no `dangerouslySetInnerHTML` in either. One jsdom render (a scratch vitest file, not kept) of a place holding two pipes, an `img` tag with an `onerror` handler, a markdown link and markdown bold (the adversary's own value), live from token events and saved from `_cell`'s real output: no `img`, no link, no bold element, the row stays four cells, and the cell text is the value verbatim. 2 passed. |
| J-94-08 | Nothing to fix. The gate command `isort --check-only --diff src tests services tracker alembic .claude .github` passes; `core/graph.py` is skipped by `pyproject.toml`. The "Gates" table above reports a direct run on `graph.py`, not the gate. |

New tests, in `tests/system_03_search_agent/core/test_isolate_search_wiring.py`:

| Test | Proves |
|---|---|
| `test_a_missing_value_word_in_the_place_field_is_not_a_place`, 12 cases | Each placeholder, in mixed case, and a blank read as no place, so the cell says "2013, place not recorded"; "USA: Unknown County" is still a place |
| `test_a_place_too_long_for_the_cell_ends_with_a_mark_that_it_was_cut` | A 144-character place ends with "…", fits in 128 characters and is the start of the real place; a place of exactly 128 characters is shown whole |

Red on the old code: run against 3174a51d's `answer_layout.py`, 11 failed and 2 passed (the two blank cases, which 3174a51d already handled).

One property broken at a time, then restored:

| Mutation | Result |
|---|---|
| The placeholder check is switched off | 10 failed, 3 passed |
| The cut mark is dropped, so the cut is silent again | 1 failed, 12 passed |
| Restored | 13 passed |

Gates for this round:

| Gate | Result |
|---|---|
| `test_isolate_search_wiring.py` and `test_write_answer_structure.py`, not integration | 81 passed |
| The seven synthesis test files that touch `answer_layout`, not integration | 301 passed |
| `test_accession_wiring.py`, the plan code put back to develop's | 12 passed |
| `ruff check`, no path | pass |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | pass, 2 files skipped by config |

## Parked

The lookup of one named isolate ("What is known about Salmonella isolate SAMN02147118 in Pathogen Detection?" showing that isolate's strain, place, date and genes) is parked for the owner, not dropped. The diff that restores it, on top of this fix round, is `raw/lookup_parked.patch`: the plan change in `core/graph.py`, its three tests, and query 42's text. It applies cleanly with `git apply`.

Why it was taken out:

| Measured | Time | Source |
|---|---|---|
| Query 42's lookup, an isolate in the first row of the Salmonella file | 20.2 s, 18.8 s of it the SNP-distance scan, which found nothing the answer shows | J-94-06, live |
| The same lookup for a BioSample not in the Salmonella folder | 45.2 s, then nothing shown | J-94-06, live |
| A Salmonella isolate looked up in the E. coli folder | 34.6 s, empty | A-94-08, live |
| A human BioSample looked up in the Salmonella folder | 55.3 s, empty | A-94-08, live |
| Develop's query 42, the two NCBI summaries | about 1 s for Act, read and inferred, not measured | J-94-06 |

- Every answer must arrive within about 20 s and no surface may get worse. With the lookup, query 42 was slower than on develop, and a BioSample question naming an organism and an isolate word could wait 45 to 55 s for nothing.
- When the lookup ran out of the tool's own 120-second budget, its "timeout" status crashed Act and the person lost the whole answer, the BioSample record develop showed included (J-94-03, A-94-03).
- An empty lookup said nothing about Pathogen Detection (J-94-05, A-94-04), and the organism was read from the first match in a fixed table, not from the isolate (J-94-04, A-94-01).

What the owner decides before it comes back: whether to skip or shrink the SNP-distance scan in lookup mode (it reverses F-3.5-A-05); how an empty or timed-out lookup is said to the reader; and whether to read the organism from the BioSample summary instead of the question. Mapping the tool's "timeout" status to an error result is a code fix, not a choice, and must land before the lookup does.
