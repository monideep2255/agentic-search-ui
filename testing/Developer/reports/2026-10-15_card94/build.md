# Card 94 build: one named isolate lookup, 2026-10-15

Base: `7626fe85`, branch `fix/card94-isolate-lookup`, from develop.

## Table of contents

- [What changed](#what-changed)
- [Time bound](#time-bound)
- [Live proof](#live-proof)
- [Mutations](#mutations)
- [Gates](#gates)
- [Not covered](#not-covered)
- [Learnings](#learnings)

## What changed

| Step | Change |
|---|---|
| 1 | The parked lookup is back, adapted. The organism is unknown at Plan, so Plan declares a `_PlannedFollowUpCall` (purpose `isolate_lookup`, source `biosample_summary`) first in the list, only for a BioSample accession plus an isolate word. Act builds the tool input after the BioSample summary returns. Query 42's text is updated. |
| 2 | `PathogenIsolateLookupInput.skip_snp_distance` (default false). The app's lookup sets it, so `_isolate_lookup` never reads the SNP-distances file. F-3.5-A-05's behaviour is unchanged when the flag is false and in every other mode. |
| 3 | The tool's `timeout` status is shaped as `error` in `_layer_tool_output_to_structured_fields`, with failure kind `timed_out`. Act no longer raises. |
| 4 | The organism is read from the BioSample record's `organism` field (the record whose own accession is the asked one), matched to the covered organisms by `isolate_search.organism_of_record`. No organism, or an uncovered one, means no lookup. |
| 5 | One note beside the BioSample record, `_isolate_lookup_note`, in the notes list after the isolate disclosure. Four fixed lines in `isolate_search`: not found ("<acc> was not found in NCBI Pathogen Detection's <organism> data, so only its BioSample record is shown."), took too long ("The Pathogen Detection lookup took too long and was stopped, so only the BioSample record of <acc> is shown."), did not complete (other errors), and no organism. A lookup that shows no isolate adds no evidence pair and no `failed_searches` entry. |
| 6 | `_ISOLATE_LOOKUP_ACT_TIMEOUT_SECONDS = 8.0`, used only for `isolate_lookup`. The other isolate modes keep 150 s. |

Design coverage (docs/build/design/README.md): answer notes are plain note tokens and no coverage-table row names them. This is a gap named, not a new design: the line follows the existing note pattern (isolate disclosure, paper-link notes).

## Time bound

Measured live with the SNP scan skipped (tool called directly):

| Lookup | Seconds |
|---|---|
| SAMN02147118 in Salmonella (row 1 of the file) | 3.2 |
| A Salmonella BioSample the file does not hold | 31.8, then 31.4 |
| The same isolate in the E. coli folder | 28.4 |

A not-found lookup reads the file to the end, about 30 s. Through the app, guard plus think took 3.7 to 8 s before Plan and write took 1.5 to 3.6 s after. So the lookup gets 8 s: worst case about 8 + 8 + 4, about 20 s. Cost of the choice: an isolate more than roughly a quarter of the way into the file is not reached and the person sees the "took too long" line (it appeared once in 6 runs of query 42, network variance). A not-in-file BioSample in a large organism always reads "took too long", because the scan cannot finish in time; "not found" shows only when the file is read inside the bound.

## Live proof

`run_streaming`, `reads_placement=True`, develop's settings. Quoted fields only: strain, accession, genes, place and year, the line, times, cost. No submitter fields were read or kept. Raw run output stays in the scratchpad, not the repository.

| Query | Runs | Seconds | Answer shows | Line | Cost per run |
|---|---|---|---|---|---|
| 42, SAMN02147118 | 6 | 8.2, 9.5, 11.2, 15.9, 17.6, 18.1 | 5 of 6: SQ0227, USA: Western Region, 2013, genes, cited to Pathogen Detection and BioSample. 1 of 6: BioSample only | 1 of 6: "took too long" | 0.0014 to 0.0037 |
| SAMN64233002 (Salmonella, not in the file) | 6 | 15.3, 15.9, 16.6, 18.4, 18.5, 19.7 | BioSample record, cited | 6 of 6: "took too long" | 0.0022 to 0.0040 |
| E. coli named, SAMN02147118 (Salmonella) | 6 | 10.5, 10.6, 10.7, 10.9, 13.4, 14.8 | 6 of 6: the Salmonella isolate, found in the Salmonella data | none | 0.0019 to 0.0050 |
| Controls 33 to 37 | 5 each | 21 to 130 (develop: 19 to 133) | 21 rows each, same as develop | none, same as develop | 0.027 to 0.032 per five (develop 0.031 to 0.035) |

Total spend about $0.35. The controls' long times are the isolate search's own scan, identical on develop.

Trust badge: the notin question reads "ask" (answer 1 of 12 across two runs of six) with the code-built list note "no written summary could be checked". Develop on the same question without the lookup read "ask" 4 of 6 and 1 of 3 in two runs. So the fallback pre-exists on this question shape, with the lookup the rate looked higher (about 11 of 12 against 5 of 9). Not proven to be the lookup; see Not covered.

## Mutations

Each broke one property, ran the arm, and was restored from a copy.

| Step | Mutation | Result |
|---|---|---|
| 2 | Plan asks `skip_snp_distance` false | 1 failed, 38 passed |
| 2 | Tool ignores the flag | 1 failed, 46 passed |
| 3 | Timeout status not shaped as error | 1 failed, 38 passed |
| 4 | Organism fixed to the first table entry | 2 failed, 37 passed |
| 5 | Note never added | 1 failed, 38 passed |
| 5 | Not-found read as timed out | 2 failed, 37 passed |
| 6 | Bound 150 s | 1 failed, 38 passed |

Two later changes (8 s bound, dropping the failed lookup's evidence pair) were made after the mutation run; the pair change has its own assertion in two tests, the bound is held by the `<= 12` assertion and the 0.2 s cut test, which passed on the final code.

## Gates

| Gate | Result |
|---|---|
| `ruff check` | All checks passed! |
| `isort --check-only src tests services tracker alembic .claude .github` | Skipped 2 files, exit 0 |
| `pytest tests/system_03_search_agent -m "not integration" -q` | 6959 passed, 143 skipped, 24 deselected, 1 xfailed |

## Not covered

- The deployed app and the "ask" trust rate above.
- The cluster-list read (about 1.7 s for a first-row isolate) still runs; the owner's decision named only the SNP-distance scan.
- A multi-accession question looks up only the first accession, as before.
- A BioSample organism name not in the table (a species outside the 20 covered) gets the "no organism" line.

## Learnings

- A shared scratchpad holds other agents' files with generic names (`mut.sh`, `graph.orig`). Two were overwritten or moved by this run; this run's work moved to a `b94` subfolder. Use a private subfolder from the start.
- A failed lookup left in the writer's evidence is not proven to cause the code-built list fallback; dropping it did not change the badge (develop shows it too).
