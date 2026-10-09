# Card 92 diagnosis: no dbVar records among the sources for a chromosome window

Read-only diagnosis, 2026-10-05, develop environment, guest sessions only. Raw evidence is in `raw/`; scripts are `ask.py`, `tool_direct.py` and `repro_drop.py` in this folder. Source paths below are relative to `<repo-root>/src/system_03_search_agent/`.

## Table of contents

- [What the person sees](#what-the-person-sees)
- [Reproduction](#reproduction)
- [Root cause](#root-cause)
- [Does dbVar hold records there](#does-dbvar-hold-records-there)
- [Fix options](#fix-options)
- [Recommendation](#recommendation)
- [Confidence](#confidence)
- [Not covered](#not-covered)

## What the person sees

- A chromosome window question returns the right genes (BRCA1, CFTR) and ClinVar records with links.
- No dbVar record (an `nsv` accession, a copy number variant) appears among the sources or in the answer, although test queries 27 and 29 expect them.
- Nothing tells the person a dbVar search ran. There is no error and no note. The search ran, found records, and the records were dropped silently.

## Reproduction

Four live guest runs (2 per query), 4 of the 10 question budget used. Both queries are the exact texts from the test document. Note that query 29's text names only "genes and ClinVar records", so it never asks for dbVar by name; the document's expectation for 29 asks more than the question does (see Fix options, last point).

| Query | Run | Seconds | Plan holds dbVar overlap call | dbVar call result | dbVar citations | ClinVar overlap citations |
|---|---|---|---|---|---|---|
| 27 | 1 | 18.9 | yes (2 coordinate_overlap calls) | ok, 5 records, truncated | 0 | 5 (VCV4935316, 18, 21, 22, 23) |
| 27 | 2 | 13.7 | yes | ok, 5 records, truncated | 0 | 5 |
| 29 | 1 | 17.5 | yes | ok, 5 records, truncated | 0 | 5 |
| 29 | 2 | 18.1 | yes | ok, 5 records, truncated | 0 | 5 |

Every run: 15 tool calls planned and 15 returned status ok, no error events, 60 to 72 citations, none with a dbVar source URL. The citation sets were identical across the two runs of each query (stable, not flaky).

## Root cause

A dbVar search is planned, runs, and returns records. The write step then discards every dbVar row because the first field of the row is a list.

Chain, with file and line:

- Planned: `core/coordinate_window.py:419-445` (`plan_overlap_calls`) always plans a ClinVar then a dbVar `coordinate_overlap` call when the assembly is named. The live plan shows both calls (raw `q27_run1.json`, two `ncbi_efetch` calls whose summary is "coordinate_overlap: 5 record(s)").
- Returns records: `tools/ncbi_coordinate_overlap.py` returns 20 dbVar records for window 27 and 17 for window 29 when called directly (`raw/tool_direct_output.txt`). The write step keeps 5 per call (`core/graph.py:4272`, `_LAYER_TOOL_ROW_CAP = 5`), so the live "5 record(s)" is correct.
- Row fields: `core/graph.py:6906` allows `("variant_type", "gene_name", "chr_start", "chr_end", "assembly")` for `dbvar_overlap`. The tool stores `variant_type` and `gene_name` as lists (`tools/ncbi_coordinate_overlap.py:465-466`), for example `["copy number variation"]`. ClinVar's first field is `title`, a string.
- Field pick: `core/graph.py:8550` (`_pick_representative_field`) returns the first non-blank field in order, so for dbVar it picks `variant_type`, a list.
- The drop: `synthesis/findings.py:352` marks any list value as `is_container`, which makes the pick degenerate. With no CURIE on an `ncbi_efetch` row (`core/graph.py` row builder sets `curie` to the empty string) the function returns `"", ""` at `synthesis/findings.py:449`, and `build_synth_findings` skips the row at `synthesis/findings.py:604`. It never tries the next field (`chr_start` is a plain number and would pass).
- Result: no finding, so no citation, so no dbVar source in the answer.

Proof by replay (`raw/repro_drop_output.txt`, live NCBI, the write step's own functions): the 5 ClinVar rows each yield a citable field `title`; the 5 dbVar rows each yield `''` and are dropped. The 5 ClinVar ids replayed match the 5 cited live (VCV004935316, 318, 321, 322, 323).

This is a code defect, not planning, not an NCBI outage, not a transport error.

## Does dbVar hold records there

Yes. NCBI E-utilities directly (esearch db=dbvar, `17[CH] AND 43044295:43125364[BASE] AND GRCh38[ASSM]`) returns 2884 candidates for window 27; the CFTR window `7[CH] AND 117480025:117668665[BASE] AND GRCh38[ASSM]` returns 1517 (`raw/ncbi_dbvar_q27.json`, `raw/ncbi_dbvar_q29.json`). After the overlap check the tool confirms real overlaps, for example nsv7906333 (BRCA1 and NBR2 copy number variation, chr17:43115725-43125364) and nsv7908076 (CFTR and CFTR-AS1, copy number variation). The test document's expectation is correct; the product is wrong.

## Fix options

All three are plain code changes with no hardcoded questions and no word lists; no classifier decision is involved, because this is verification of fields, not a judgment about the question.

| Option | What changes | Risk | Answer path |
|---|---|---|---|
| A. Flatten list fields in the tool | In `tools/ncbi_coordinate_overlap.py` `_build_record`, or when shaping breadth rows at `core/graph.py` `_ncbi_efetch_output_to_structured_fields`, join a list of strings into one string ("copy number variation", "BRCA1, NBR2") for the dbVar and ClinVar `gene_symbol` fields. The first field then passes the container check. | Low. Touches two fields on two row types. Needs unit tests for list values and an eye on tests asserting list-valued fields. | Yes, it changes which sources and rows reach the answer |
| B. Build a code label for dbVar rows | Give each dbVar row a leading string field, for example a `title` assembled in code from variant type, gene names and position ("copy number variation overlapping BRCA1, NBR2, chr17:43115725-43125364"), and put it first in the `dbvar_overlap` allow-list. Mirrors ClinVar's `title`. | Low to medium. The label becomes the cited claim, so the sentence must be built only from record fields (it is). Reads best for the person. | Yes |
| C. Make the picker skip containers | In `core/graph.py:8550` (`_pick_representative_field`) or `synthesis/findings.py:279`, move on to the next usable field when the first is a list. | Higher blast radius: it changes every tool's row handling, and the next dbVar field would be `chr_start`, giving a weak claim like "chr_start 43094142". Not recommended alone. | Yes, across all layers |

Every option is answer path, so the golden run must hold at least 101 of 150 before it counts as done, and the five or more repeated live runs of queries 27 and 29 should be shown after the fix.

Related but separate: query 29's text asks for "genes and ClinVar records" only. The test document's expected line "ClinVar and dbVar records for that stretch are among the sources" goes beyond what the question asks. The plan includes dbVar anyway because a window always plans both calls, so the fix should satisfy it, but the question text could also gain "and dbVar records" for a cleaner test. That is the owner's call on the test document.

## Recommendation

Option B, with the list-to-string join from option A applied to the fields it uses (gene names), so the dbVar label reads in plain words and the record can be cited like a ClinVar record. It is the smallest change that gives the person a readable, checkable dbVar line and keeps one source set per question. Add a unit test that feeds a list-valued first field through `_citable_value_for_row` and asserts a dbVar row yields a finding. Also consider a guard so a planned call whose rows all vanish at the write step is disclosed in Notes rather than silent (honesty rule), as a follow-up.

## Confidence

High, about 90 percent. The failing row handling was reproduced offline with the same functions on live NCBI data and it matches the live runs exactly (5 of 5 dbVar rows dropped, 5 of 5 ClinVar rows kept, same ClinVar ids cited). The remaining uncertainty is that I did not read the raw dbVar rows as the deployed develop build saw them (the stream carries counts, not rows), so a deployed-build difference from this working tree is possible but unlikely given the identical ClinVar ids.

## Not covered

- No fix was applied and no tests were run; the golden run was not executed.
- No other chromosome windows, GRCh37 windows or windows with a different assembly string were run (query 28 and 26 not run).
- The disclosure "does not address the following entities named in the question" with gene symbols the person never named (seen in the retest report notes for queries 27 and 29) was seen as a side effect (the opening sentence lists RPL21P4, LOC genes) but not diagnosed here.
- The ESearch prefilter reads only 20 candidates of 2884 and 1517, so even after the fix the dbVar sample is 5 rows shown from a larger set; the truncation disclosure exists but its wording for dbVar was not checked.
- Other tools or purposes whose first allowed field is a list (an audit of `_BREADTH_FIELDS_BY_PURPOSE` entries) were not checked.
