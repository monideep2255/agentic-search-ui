# Card 94 build: each isolate's place, and one isolate's details

Build report, 2026-10-09, branch `fix/card94-isolate-place-lookup`, cut from `develop` at `b01dee92`. Paths are relative to `<repo-root>`. Diagnosis: `testing/Developer/reports/2026-10-08_overnight/card94_diagnosis.md`.

In the user's words: "An isolate answer shows each isolate's place, and naming one isolate gets that isolate's details."

Kept. The "from 2023" follow-up is card 20's and is not touched here.

## Table of contents

- [What changed](#what-changed)
- [One departure from the diagnosis](#one-departure-from-the-diagnosis)
- [What a person sees](#what-a-person-sees)
- [Tests](#tests)
- [Live probe of the lookup](#live-probe-of-the-lookup)
- [Gates](#gates)
- [Not covered and left open](#not-covered-and-left-open)

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
