# Card 94 diagnosis: place and accession columns, a "from 2023" follow-up, one isolate

Diagnosis only, 2026-10-08 overnight, read against `develop` at `c916cfa3`. Paths are relative to `<repo-root>`. No code was changed and no model was called. One local probe ran the real `write_node` with the card 94 test's own fixture and its model stubs; its script is not committed. The trial merge used `git merge-tree`, which touches no working tree.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The causes](#the-causes)
- [The smallest fixes](#the-smallest-fixes)
- [Overlap with phase 8.7 and the guardrail](#overlap-with-phase-87-and-the-guardrail)
- [Needs the owner](#needs-the-owner)
- [Proposed test query](#proposed-test-query)

## Status today

| Slice | Status on develop | Evidence |
|---|---|---|
| Accession column | Already shown, under the heading "Identifier" | Probe below |
| Place column | Still missing | Probe below |
| A follow-up such as "Show me the ones from 2023" | Still happens: not carried forward, no year filter exists | Retest of 2026-09-29, `testing/Developer/reports/2026-09-29_retest/runner_A/results.md`, isolate 9; code below |
| A single-isolate lookup | Still happens: the tool's lookup mode is never called | Same report, isolate 10; code below |

The probe: the card 94 test fixture (`_ISOLATE_ROWS` in `tests/system_03_search_agent/core/test_write_answer_structure.py`) with `biosample_acc` and `geo_loc_name` added to each row, as `core/graph.py:4931` to `4938` builds them, through `write_node`:

| Depth | Table header | First row |
|---|---|---|
| Researcher | Isolate, Identifier, AMR genes, Collected | strain-1, SAMN00000001, blaCTX-M-15 acrF1, 2023 |
| Plain language | Isolate, Identifier, AMR genes, Collected | the same |

The place is in each row's fields and never reaches a cell. The accession is there, named "Identifier".

## What a person sees

- The isolate table says when each isolate was collected but not where, so "isolates from the United States" cannot be read off it. The accession column is headed "Identifier", where the isolate workflow promises a BioSample accession.
- After an isolate answer, "Show me the ones from 2023" ended in "This run could not be completed", and on a retry "This looks outside biomedical research".
- "What is known about Salmonella isolate SAMN02147118 in Pathogen Detection?" answers "The isolate SAMN02147118 is a pathogen sample from Salmonella enterica" with a sequencing run as its source: no strain, place, date, resistance genes or Pathogen Detection link.

## The causes

| Slice | Where | Cause |
|---|---|---|
| Place | `src/system_03_search_agent/synthesis/answer_layout.py:297` to `307`, `TABLE_COLUMNS`; `record_status_or_year` (line 570) | The isolate table's columns are the name, the identifier, `amr_genotypes` and one status-or-year column. No column reads `geo_loc_name`. |
| Accession heading | `answer_layout.py:390`, `IDENTIFIER_COLUMN_LABEL = "Identifier"`; `_IDENTIFIER_FIELDS` line 491 | One generic heading for every record type. |
| Follow-up | `src/system_03_search_agent/core/isolate_search.py:325`, `parse_isolate_question`; called at `core/graph.py:4126` in `_think` | An isolate question is recognised only when the turn's own text has an isolate word. "the ones from 2023" has none, and nothing in session memory (`contracts/query.py:144`, `SessionMemorySummary`) records the last isolate search's organism and gene families. |
| Year and place filter | `tools/pathogen_detection_schemas.py:228`, `PathogenIsolateSearchInput` | The search takes a taxon, gene prefixes and a row cap only. |
| Single isolate | `tools/pathogen_detection_schemas.py:179`, `PathogenIsolateLookupInput` (`mode="isolate_lookup"`) | The mode exists in the tool and nothing in `core/` plans it. A SAMN accession takes the accession path (`resolve_accession`, `core/graph.py:4116`), which reads the BioSample summary. Isolate parsing runs only when no accession was found (`core/graph.py:4125`), so the accession path wins. |

The parked work: `94b0ba41` on `parked/phase-8.4-2026-09-25` adds `location` and `collection_year_min` and `collection_year_max` to the isolate search and its filtering in `tools/pathogen_detection.py`, plus a fixed-pattern year parser in `isolate_search.py`. Decision D12 (`testing/Board_plan.md`, line 216) drops that parser: the year and place are read by a classifier decision. Trial merge against develop: `pathogen_detection.py`, `pathogen_detection_schemas.py` and `isolate_search.py` auto-merge; `tests/system_03_search_agent/core/test_isolate_search.py` conflicts.

## The smallest fixes

| Field | Place and accession columns | Single-isolate lookup | "From 2023" follow-up |
|---|---|---|---|
| Change | A "Place" column read from `geo_loc_name` for isolate rows, "Not recorded" where blank, as "Collected" already does; the identifier column headed "BioSample" on the isolate table | A SAMN accession plans `pathogen_detection` `isolate_lookup`. Its taxon comes from the organism the question names, or from the BioSample summary's organism as a second-round call. The answer shows the one isolate's row: strain, BioSample, place, date, genes, link. | Lift the tool half of `94b0ba41` (the two filters in the tool and its schema). A classifier decision reads the year and place (D12). A follow-up with no isolate word reuses the last isolate search's organism and gene families, kept in session memory. |
| Files and functions | `synthesis/answer_layout.py` (`TABLE_COLUMNS` or a sibling for isolates, `collected_placeholder`); `core/graph.py` `_answer_tokens` inner `grouped_listing` (the extras columns) | `core/graph.py` `_think` and `plan_node` (the accession branch), `_follow_up_planned_call` for the second-round call; `core/isolate_search.py` | `tools/pathogen_detection.py`, `pathogen_detection_schemas.py`; `core/isolate_search.py`; `core/graph.py` `_think`; `harness/decide.py` (a new decision point); `contracts/query.py` `SessionMemorySummary`; `core/session_memory.py` |
| Answer path | Yes, layout | Yes | Yes |
| Dial position | 2 | 2 | 2 |
| Size | S | M | L |
| Migration, package, event schema | None | None | No migration: session memory is a JSONB column (`alembic/versions/0007_session_memory.py`), so an optional field needs none. No event schema change. One new classifier decision on every isolate question. |

Build order: the columns, then the single isolate, then the follow-up.

## Overlap with phase 8.7 and the guardrail

| Fence | Phase 8.7 | Guardrail |
|---|---|---|
| `synthesis/answer_layout.py`, `core/graph.py` `_answer_tokens` (columns) | Yes, both on tonight's list | None |
| `core/graph.py` `_think`, `plan_node` (single isolate) | No | No |
| `_follow_up_planned_call`, run from `act_node`'s second stage | Next to `act_node`, which 8.7 rewrites | None |
| `harness/decide.py` (the year and place decision) | Yes | None |
| `tools/pathogen_detection*.py`, `core/isolate_search.py`, session memory | None | None |

Only the tool half of the follow-up is clear of tonight's work. Everything else waits for 8.7.

## Needs the owner

- The columns and the single isolate: no.
- The follow-up: one cost choice, since the year and place decision adds a classifier call to every isolate question. D12 already chose a classifier over a fixed parser, so this is covered unless the owner wants it asked only when the turn carries a year or place.

## Proposed test query

Existing queries 33 to 40 and the isolate workflow (`testing/Product/queries/Isolate_search_queries_and_workflow.md`, queries 9 and 10) cover these. Proposed lines for query 33:

```markdown
- Each isolate row shows its BioSample accession and where it was collected, beside when; a missing place reads "Not recorded".
- Then type `Show me the ones from 2023`: the answer lists only isolates collected in 2023, for the same organism and genes, with a new count, or says plainly it cannot filter by year. It never repeats the full list as if filtered.
```

And for workflow query 10: `What is known about Salmonella isolate SAMN02147118 in Pathogen Detection?` shows that one isolate's strain, BioSample, place, date, resistance genes and its Pathogen Detection link, with no "first 20" note.
