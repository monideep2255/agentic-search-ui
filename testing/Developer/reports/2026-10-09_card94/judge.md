# Card 94 judge report, 2026-10-09

Branch fix/card94-isolate-place-lookup at 3174a51d, base develop b01dee92. Fresh-context judge. Findings are appended as they are established.

## Findings

### J-94-01: Placeholder words in a record's place field are shown as if they were a place
- Severity: minor
- What: `isolate_place` returns `geo_loc_name` verbatim, so a submitter's placeholder ("missing", "not collected", "Not applicable", and a graph row's literal "NULL") becomes the place half of the "Collected" cell. The tool's own `_cap_or_withhold` strips only "NULL" and blanks, not the other placeholders. BioSample records in this repository's own raw evidence hold `geo_loc_name` "missing" (testing/Developer/reports/2026-10-05_card94/raw/biosample_SAMN00715300_SAMN00778958.xml).
- Reproduction: judge's differential probe (write_node with the test module's `_state` and `_no_prose`, base b01dee92 versus branch 3174a51d, both depths). Isolate rows with fields {geo_loc_name: "missing", collection_date: "2013"}, {"not collected", "missing"}, {"NULL", "NULL"}, {"Not applicable", none}. Base cells: "2013", "", "", "Not recorded". Branch cells: "2013, missing", "not collected, date not recorded", "NULL, date not recorded", "Not applicable, date not recorded".
- Why it matters: the card's own promise is "missing halves named honestly". A reader sees "missing" or "NULL" in the place position, and a placeholder word is treated as a place while a placeholder date is treated as absent, so the two halves of one cell follow different rules. Not a wrong record, but it reads as data. Unsure how often Pathogen Detection metadata carries these words; the graph and BioSample records do.
- NOT FIXED

### J-94-02: A long place is clipped silently at 128 characters
- Severity: minor
- What: `isolate_place` cuts the place to `MAX_IDENTIFIER_CHARS` (128) with no ellipsis or note, while the tool accepts places up to 150 characters (`_MAX_GEO_CHARS`). A clipped place can end mid-word and read as a different, shorter place.
- Reproduction: probe isolate row {geo_loc_name: "X" * 140, collection_date: "2013"}: branch cell "2013, " followed by exactly 128 X characters; base cell "2013". The cell bound in `TokenPayload.cells` is 500, so the clip is not needed for validation.
- Why it matters: "read verbatim from the isolate's own record" is not true for 129 to 150 character places. Low frequency.
- NOT FIXED

### J-94-03: A lookup that runs out of its 120-second budget crashes the whole answer, losing the BioSample record develop showed
- Severity: major
- What: `pathogen_detection` returns `status: "timeout"` when its shared 120-second budget runs out during the mandatory metadata read (`_deadline_exceeded_output`). `_layer_tool_output_to_structured_fields` passes that status through unchanged, and `act_node` builds `ToolResultPayload(status="timeout")`, whose field is `Literal["ok", "empty", "error"]`. Act raises a pydantic ValidationError instead of degrading the one call. The pass-through is pre-existing (the isolate search has the same path), but this branch makes it reachable from every BioSample question that names an organism and an isolate word, query 42 among them, which on develop planned only the two NCBI summaries and could not hit it.
- Reproduction: judge's offline end-to-end probe (real `plan_node`, `act_node`, `write_node`; `graph_module.pathogen_detection` and `graph_module.ncbi_efetch` replaced by fakes; no network). Question "What is known about Salmonella isolate SAMN02147118 in Pathogen Detection?", fake lookup returns `PathogenDetectionOutput(status="timeout", mode="isolate_lookup", ...)`. Branch: `pydantic_core._pydantic_core.ValidationError: 1 validation error for ToolResultPayload status Input should be 'ok', 'empty' or 'error' [type=literal_error, input_value='timeout']` raised at `src/system_03_search_agent/core/graph.py:8816`. Base on the same question: no lookup planned, answer lists the BioSample and SRA records.
- Why it matters: on a slow FTP day (the metadata read is a full-file scan when the accession is not in the named organism's folder, J-94-05) the person loses the answer they got on develop. A degradation on the query this card is meant to improve. The 150-second Act ceiling does not help, since the tool's own 120-second budget fires first and returns normally.
- NOT FIXED

### J-94-04: The lookup's organism is the first organism in a fixed table that appears anywhere in the question, not the organism the accession belongs to
- Severity: minor
- What: `parse_isolate_question(...).organism` walks `ORGANISMS` in table order, so a question naming two organisms picks whichever comes first in the table, regardless of which one the sentence ties to the accession. The lookup then reads the wrong folder and finds nothing.
- Reproduction: judge's plan probe (real `plan_node`, accession plan for SAMN02147118). "Is Salmonella isolate SAMN02147118 related to E. coli isolates?" plans `isolate_lookup` with taxon `Escherichia_coli_Shigella`. "What is known about the human sample SAMN02147118? I study Salmonella, not isolates." plans a Salmonella lookup. "Pathogen Detection record for SAMN02147118 (Shigella)" plans the E. coli and Shigella folder (correct by shared folder).
- Why it matters: no wrong isolate can attach (the tool matches `biosample_acc` exactly, and the row carries the accession), so this is not a confident wrong record. The cost is a wasted full-folder scan and a silent miss (J-94-05). The diagnosis's alternative, reading the organism from the BioSample summary, would not have this failure.
- NOT FIXED

### J-94-05: A lookup that finds nothing is silent, and the person still waits for a full scan of the organism's metadata file
- Severity: minor
- What: when the BioSample is not in the named organism's Pathogen Detection folder (an organism mismatch, a non-isolate BioSample, or a BioSample NCBI has but Pathogen Detection does not), the lookup returns `status: "empty"` and the answer is word for word develop's answer: no line says Pathogen Detection was searched for this accession and held no isolate, or which organism was searched. `stream_filtered_tsv_rows` has no early exit for a key that is absent, so this "empty" costs a scan to the end of the metadata file (the graph's own comment measures 18 s for the 521 MB E. coli file).
- Reproduction: offline end-to-end probe as in J-94-03, fake lookup returns `status="empty"`. Branch answer text and rows equal base's for both "What is known about Salmonella isolate SAMN02147118 in Pathogen Detection?" and "Is Salmonella isolate SAMN02147118 related to E. coli isolates?"; `failed_searches` is empty. The full-scan cost is read from `pathogen_ftp_transport.stream_filtered_tsv_rows` (breaks only on match, `max_matches` or deadline) and measured live in J-94-06.
- Why it matters: the person asked "in Pathogen Detection" and is told nothing about Pathogen Detection, after a wait that develop did not impose. "A refusal says what to type next."
- NOT FIXED

### J-94-06: The lookup adds 20 s to query 42 at best and 45 s to a BioSample that is not in the named organism's folder, all of it before the records list can show
- Severity: major
- What: Act runs its calls concurrently and waits for the slowest (`_gather_planned_calls`), and the record listing is sent when Act ends, so the BioSample and SRA rows develop showed after the two NCBI summaries now wait for the lookup. The lookup's bounds are the tool's 120-second shared budget, a 20-second sub-budget for the cluster and SNP-distance enrichment, and the 150-second Act ceiling (`_LAYER_TOOL_ACT_TIMEOUT_SECONDS["pathogen_detection"]`). Nothing bounds it near 20 s. The SNP-distance enrichment spends its whole 20-second sub-budget and returns nothing, and neither `pds_cluster` nor `snp_distance` is shaped into the answer's row (`_layer_tool_output_to_structured_fields` keeps name, accession, genes, serovar, place and date only), so that time buys the reader nothing on this path.
- Reproduction: two live, read-only `pathogen_detection` calls run by the judge from `src` at 3174a51d, each wrapped in `asyncio.wait_for(..., 150)`, per-read times from a wrapper around `stream_filtered_tsv_rows`, no model call.
  - Query 42's lookup, taxon Salmonella, SAMN02147118: TOTAL 20.2 s, status ok. Metadata 0.0 s (the accession is row 1 of 896,782, the best case possible), cluster list 1.2 s, SNP distances 18.8 s, 2,348,231 rows scanned, cut by the sub-budget, 0 rows. Strain SQ0227, place "USA: Western Region", 2013, cluster PDS000032687.5, SNP distance None. Matches the builder's 20.3 s.
  - The same lookup for a BioSample not in Salmonella (SAMN00778958, an E. coli O104:H4 sample from this repository's own evidence): TOTAL 45.2 s, status empty, 896,782 rows scanned to end of file, nothing shown to the reader (J-94-05).
- What a person waits for query 42: on develop the Act step is the two NCBI summary calls (about a second; not measured live here, no model calls allowed), so the records list shows about a second after planning. On this branch Act cannot finish in under about 20 s for this best-case accession; any other isolate adds its row position's share of a 45-second metadata scan, up to about 65 s. Then the writing model runs on top. Query 42 cannot meet the owner's 20-second rule on this branch, and any BioSample question that names an organism and says "isolate" or "Pathogen Detection" gains up to 45 s even when the lookup finds nothing.
- Why it matters: the owner's rule is every answer within about 20 s and no degradation on any surface. The builder disclosed the query 42 overrun; the 45-second empty case and the "lookup runs on questions where it finds nothing" case were not in the build report.
- NOT FIXED

### J-94-07: The tests do not pin the organism, the accession-kind guard, or what an empty or timed-out lookup does
- Severity: minor
- What: two mutations to the new plan code leave every test green, and no test drives a lookup that returns `empty` or `timeout` through Act.
- Reproduction: judge's mutations, each restored with `git checkout`, run over `test_isolate_search_wiring.py`, `test_write_answer_structure.py` and `test_accession_wiring.py` (all under tests/system_03_search_agent/core).
  - Taxon hard-coded to "Salmonella" in `plan_node`: 83 passed. The one positive test asks only about Salmonella.
  - The `accession_plan.record.kind == "biosample"` guard replaced by `True`: 83 passed. With it gone, an SRA run accession beside an organism and "isolate" would be sent as `biosample_acc`, a guaranteed full-file scan.
  - The builder's own "lookup never planned" mutation: 1 failed (`test_naming_one_isolate_plans_the_tools_lookup_of_that_isolate_first`), 82 passed. Confirmed.
  - `test_one_isolates_answer_shows_its_details_with_no_sample_note` feeds a hand-built lookup output straight to `write_node`, so it does not show the lookup's output passing through Act; J-94-03 lives in exactly that gap.
- Why it matters: the parts of the change that decide which folder is read and which accessions are sent are unguarded, and the failure path that crashes (J-94-03) has no test.
- NOT FIXED

### J-94-08: Note, the import-order gate passes; the isort failure the builder reports appears only when graph.py is named directly
- Severity: minor (report accuracy, not a code defect)
- What: `isort --check-only --diff src tests services tracker alembic .claude .github` (gate02's command) passes on the branch, "Skipped 2 files", because `pyproject.toml` lists `core/graph.py` in `extend_skip`. Run on graph.py by name, isort reports the `contracts.events` import block, and the same report appears on develop's graph.py at b01dee92. The builder's statement is correct for that direct run; the gate itself is green.
- Reproduction: gate command exit clean; `isort --check-only --diff src/system_03_search_agent/core/graph.py` shows the `ResolvedEntity as EventResolvedEntity` move; the same command on `git show b01dee92:src/system_03_search_agent/core/graph.py` with `--settings-path pyproject.toml` shows the identical hunk.
- NOT FIXED (nothing to fix in this card)

## Verdict

FIX FIRST.

The place half meets the card: each isolate's "Collected" cell reads its own record's place and date, names a missing half, and no other table changes. The single-isolate half shows the right isolate with its Pathogen Detection link, but it makes query 42 wait at least 20 s for Act alone (J-94-06), adds up to 45 s to BioSample questions where it finds nothing and says nothing about it (J-94-05, J-94-06), and turns a slow-FTP timeout into a crashed answer where develop answered (J-94-03). That breaks the owner's "every answer within about 20 s, no degradation on any surface". Whether to cut the SNP-distance enrichment in lookup mode (it reverses F-3.5-A-05) is the owner's call, as the builder said. Mapping the tool's `timeout` status to an error result is not.

No finding sits inside a fix made during an earlier review round of this card; this is the first judge round. J-94-03 and J-94-06 sit in the card's new lookup planning code.

## Verified by my own probes versus only read

| Claim | How |
|---|---|
| Place read verbatim from the row's own fields; missing halves named | Probed: differential write_node run, base versus branch, both depths (J-94-01, J-94-02 found there) |
| Every other table unchanged | Probed: 10 table shapes (default disease, variant, folded, intronic, trial status, BioSample with a place field, assembly with a place field, gene with a place field, isolates, isolates with organism) by 2 depths, token-for-token equal to base; only isolate tables differ |
| When the lookup is planned, and that a plain BioSample, SRA, or PDT question gets none | Probed: plan_node on 14 questions, base versus branch |
| The lookup cannot attach a different accession's isolate | Read: exact `biosample_acc` key match in `stream_filtered_tsv_rows`; probed only that a wrong-folder question plans the wrong folder (J-94-04) |
| Empty and timeout lookups through Act and Write | Probed: offline end-to-end with fake tools (J-94-03, J-94-05) |
| Query 42 lookup 20.2 s; empty lookup 45.2 s; tool budgets 120 s, 20 s, Act 150 s | Probed live, two calls, no model call; budgets read from code |
| Develop's query 42 Act time of about one second | Read and inferred only, not measured |
| Citations: the isolate row cites its Pathogen Detection page, BioSample and SRA rows their NCBI pages | Probed in the offline end-to-end run |
| 8 tests fail on develop's code | Probed: branch test files against base source, 8 failed, 63 passed |
| Builder's "lookup never planned" mutation goes red | Probed: 1 failed; two further mutations stay green (J-94-07) |
| pytest on the two named files and the other answer_layout test files | Run: 71 passed; 590 passed |
| ruff check, isort gate | Run: both pass (J-94-08) |

Note: the brief named `tests/system_03_search_agent/synthesis/test_write_answer_structure.py`; that path does not exist, and the file is `tests/system_03_search_agent/core/test_write_answer_structure.py`, which was run.
