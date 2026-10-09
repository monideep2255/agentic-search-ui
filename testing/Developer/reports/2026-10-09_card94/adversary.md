# Card 94 adversary

Adversary report, 2026-10-09, fresh context, checkout detached at `3174a51d` (`fix/card94-isolate-place-lookup`), base `develop` `b01dee92`. Paths are relative to `<repo-root>`.

## Findings

### A-94-01: the lookup reads the folder of whichever organism comes first in the module's table, not the organism the isolate is named as

- Severity: major
- What: `plan_node` takes the taxon from `isolate_search.parse_isolate_question(query.text).organism`, and `_find_organism` returns the first entry of `ORGANISMS` (table order: E. coli, Shigella, Salmonella, Listeria, ...) whose spelling appears anywhere in the text. A question that names the isolate's own organism and also mentions a second organism looks the isolate up in the wrong folder.
- Reproduction: offline probe calling `plan_node` with an `_AccessionPlan` for the parsed accession (scratch probe, no model call). `Is Salmonella isolate SAMN02147118 related to E. coli isolates?` planned `('pathogen_detection', 'isolate_lookup', taxon 'Escherichia_coli_Shigella', 'SAMN02147118')`. `Which E. coli isolates are similar to Salmonella isolate SAMN02147118?` planned the same E. coli folder. The isolate is a Salmonella isolate (the builder's own live probe found it in the Salmonella folder).
- What a person sees: no wrong record (a BioSample accession is unique, so the E. coli folder simply has no such row), but the lookup scans the E. coli metadata file to its end for a row that cannot be there, and the answer gets no isolate row. See A-94-04 for the time and A-94-05 for what an empty lookup shows.
- NOT FIXED

### A-94-02: a negated or contrasting organism still fires the lookup, and a second named isolate is silently dropped

- Severity: minor
- What: the trigger is "an isolate word or Pathogen Detection" plus "an organism spelling anywhere in the text". There is no reading of negation, and only the first accession in the text is looked up.
- Reproduction: same offline probe. `Does BioSample SAMN02147118 contain human tissue isolates? Not Salmonella.` planned `isolate_lookup` in the `Salmonella` folder. `Human isolate SAMN00000001 sequenced for MRSA screening, what is it?` planned `isolate_lookup` in `Staphylococcus_aureus`. `Compare Salmonella isolates SAMN02147118 and SAMN02147119 in Pathogen Detection` planned one `isolate_lookup`, for SAMN02147118 only; nothing in the plan narrative says SAMN02147119 was not looked up.
- What a person sees: a comparison of two isolates comes back as a one-row isolate table about the first. The single-accession limit is older than this card (`accession.parse_accession`), but the new isolate table makes the missing second isolate look like a complete answer. Unsure whether the owner counts this inside card 94.
- NOT FIXED

### A-94-03: when the lookup runs out of its own 120-second budget, Act crashes instead of answering

- Severity: major
- What: every deadline path in `_isolate_lookup` returns `_deadline_exceeded_output`, whose `status` is `"timeout"`. `_layer_tool_output_to_structured_fields` passes `isolates.status` through unchanged, and `act_node`'s `_close_tool_call` builds `ToolResultPayload(status=outcome.status)`, whose field is `Literal["ok", "empty", "error"]`. A `"timeout"` status raises a pydantic `ValidationError` out of `act_node`. It is not an `"error"` either, so it would never reach `failed_searches` and the honest unfinished-search note even if it did not raise.
- Reproduction: offline probe driving the real `plan_node` then `act_node` for `What is known about Salmonella isolate SAMN02147118 in Pathogen Detection?`, with `ncbi_efetch` faked to return the BioSample and SRA summaries and `pathogen_detection` faked to return `PathogenDetectionOutput(status="timeout", mode="isolate_lookup", isolate_count=0, total_available=0, truncated=False, error="...budget was exceeded during isolate_lookup metadata read")`, exactly the shape the tool's own `_deadline_exceeded_output` builds. Output, both reading depths: `pydantic_core._pydantic_core.ValidationError: 1 validation error for ToolResultPayload ... Input should be 'ok', 'empty' or 'error' [type=literal_error, input_value='timeout', input_type=str]` at `core/graph.py:8816`.
- What a person sees: no answer at all for the question, not even the BioSample record that was found beside it, instead of an answer with a note that the Pathogen Detection lookup did not finish. The isolate search shares the same pass-through, so this may be older than the card for an isolate search that times out with no match; card 94 adds a new, common way to reach it, since the lookup's metadata read is a scan of a whole organism file (A-94-04) against the same 120-second budget.
- NOT FIXED

### A-94-04: when the lookup finds no isolate, the answer says nothing about Pathogen Detection

- Severity: major
- What: an `isolate_lookup` that returns `status="empty"` (the BioSample is not in that organism's Pathogen Detection folder) contributes no row, no `failed_searches` entry and no sentence. The answer is the BioSample and SRA records only, exactly as on `develop`, with nothing saying that the Pathogen Detection lookup the question asked for found no isolate.
- Reproduction: the offline plan, act and write probe from A-94-03 with `pathogen_detection` faked to return `PathogenDetectionOutput(status="empty", mode="isolate_lookup", isolate_count=0, total_available=0, truncated=False)`. Researcher text: `Found 1 biosample record and 1 sra record: Salmonella enterica isolate SQ0227 [1] and SRR111 [2].` then the two record tables and the standard "no written summary could be checked" note. Plain language: `I found 1 biological sample and 1 sequencing dataset on this topic [1][2].` No mention of Pathogen Detection or of an isolate in either. For contrast, the same probe with a tool `status="error"` or a raised exception does add `The background search of Pathogen Detection did not finish, so this answer may be missing sources from it. Ask again to retry.`
- What a person sees: they asked what Pathogen Detection holds about a Salmonella isolate and get an answer that does not say whether Pathogen Detection holds it. Combined with A-94-01, a real Salmonella isolate looked up in the E. coli folder is silently absent. A refusal or a gap should say what to type next ("Pathogen Detection lists no Salmonella isolate under SAMN..., name the organism it belongs to").
- NOT FIXED

### A-94-05: an INSDC missing-value term in geo_loc_name is shown as if it were a place

- Severity: minor
- What: `isolate_place` returns any non-blank `geo_loc_name` verbatim. BioSample and Pathogen Detection metadata use the INSDC missing-value terms ("missing", "not collected", "not provided", "not applicable", "restricted access") in this field, and the cell joins them after the year as a place.
- Reproduction: `collected_with_place("2013", isolate_place("Pathogen Detection isolate", {"geo_loc_name": v}))` for each term returned `'2013, missing'`, `'2013, not collected'`, `'2013, not provided'`, `'2013, not applicable'`, `'2013, restricted access'`; with no date, `'missing, date not recorded'`. The same row through the full plan, act and write probe rendered the cell `missing, date not recorded`.
- What a person sees: "2013, not collected" reads as "this isolate was not collected in 2013", the opposite of what the record says, and "missing, date not recorded" names "missing" as the place. The card's own wording for this case is "place not recorded". Unsure how often the live metadata carries these terms; I did not spend a live call to count them.
- NOT FIXED

### A-94-06: a long place is cut at 128 characters with no mark that it was cut

- Severity: minor
- What: `isolate_place` returns `value.strip()[:MAX_IDENTIFIER_CHARS]` (128). The tool already allows up to 150 characters for `geo_loc_name`, so a place between 129 and 150 characters is cut mid-word and shown as the whole place, with no ellipsis.
- Reproduction: a 144-character `geo_loc_name` ending `... downstream of the lock and dam` rendered `'2013, USA: Minnesota, Hennepin County, Minneapolis, Mississippi River sampling site number 4 near the Stone Arch Bridge downstream of '`, ending on "downstream of " with a trailing space.
- What a person sees: a place that stops mid-phrase and reads as verbatim. Small, but the card's promise is "read verbatim from its own geo_loc_name"; the cell has room (500 characters) for the full 150.
- NOT FIXED

### A-94-07: geo_loc_name markup reaches the cell unescaped; the surfaces I checked neutralise it

- Severity: unsure
- What: a `geo_loc_name` holding `|`, HTML, a markdown link, `**` or newlines passes byte for byte into the "Collected" cell token.
- Reproduction: the full probe with `geo_loc_name="USA | <img src=x onerror=alert(1)> | [click](https://evil.example) **bold**"` produced the cell `'2013, USA | <img src=x onerror=alert(1)> | [click](https://evil.example) **bold**'`; with `"USA\n\n# Heading\n| a | b |"` it produced `'2013, USA\n\n# Heading\n| a | b |'`. The row stayed four cells in both cases, so the four-cell limit holds.
- What a person sees: probably nothing harmful. The saved-answer markdown escapes `|` and flattens newlines (`feedback/capture.py::_cell`), and `savedAnswerMarkdown.tsx` renders typed React nodes with no `dangerouslySetInnerHTML`. I read these and did not render a hostile cell in the live screen. The strain cell has carried the same lab-submitted free text since the isolate search, so this is not new exposure, only a new field on it. Filed so the judge can confirm the live screen.
- NOT FIXED

### A-94-08: the lookup reads a whole organism file when the BioSample is not in it, 35 to 55 seconds, and the answer waits for it

- Severity: major
- What: the lookup's metadata read is a streamed scan of the organism's whole Pathogen Detection metadata file until the BioSample's row is found (`stream_filtered_tsv_rows(..., max_matches=1)` against the 120-second shared budget). The builder's 20.3 s was for an isolate whose row sits early in the file (metadata 0.0 s). When the row is late in the file, or absent (a non-isolate BioSample, or the wrong organism per A-94-01), the scan runs to the end, then returns `empty`. The only bound is the tool's 120 s budget and Act's 150 s ceiling for `pathogen_detection` (`_LAYER_TOOL_ACT_TIMEOUT_SECONDS`); nothing is sized to the 20-second answer goal. On `develop` these questions planned only the BioSample and SRA summaries.
- Reproduction: two live, read-only tool calls, no model call, `pathogen_detection(PathogenDetectionInput(mode="isolate_lookup", ...))`:
  - `taxon=Escherichia_coli_Shigella, biosample_acc=SAMN02147118` (the plan for `Is Salmonella isolate SAMN02147118 related to E. coli isolates?`): `secs=34.6 status=empty count=0 snapshot=PDG000000004.6350`.
  - `taxon=Salmonella, biosample_acc=SAMN12121739` (a human reference BioSample; the plan for a question like `Is SAMN12121739 a Salmonella isolate?`): `secs=55.3 status=empty count=0 snapshot=PDG000000002.4254`.
- What a person sees: 35 to 55 seconds of waiting, then an answer that is the BioSample record alone with no word about Pathogen Detection (A-94-04). A real isolate whose row is near the end of the Salmonella file would pay the same scan plus up to 20 s of SNP enrichment, about 75 s. On a slow FTP day the same scan crosses the 120 s budget and hits A-94-03, which loses the whole answer. Every one of these questions answered from the BioSample summaries alone on `develop`.
- NOT FIXED

### A-94-09: even the found-isolate path, query 42, is over 20 seconds by design of the SNP sub-budget

- Severity: minor
- What: for an isolate in a SNP cluster the lookup always spends up to `_ISOLATE_LOOKUP_ENRICHMENT_BUDGET_S` (20 s) on the cluster and SNP-distance reads, whose result (`snp_distance`) the answer does not show. The build report measured 20.3 s with 18.3 s in that scan and names it as the owner's call. I did not re-measure it; read only.
- Reproduction: build report, "Live probe of the lookup"; the bound is `enrichment_deadline = min(deadline, time.monotonic() + 20.0)` in `_isolate_lookup`.
- What a person sees: query 42, which answered under 20 s on `develop` from the BioSample summary, now takes over 20 s on every run. Recorded so the owner's decision has a finding behind it, not as a new discovery.
- NOT FIXED

## What I checked and found holding

- Place from a different record: none. The place is read from each row's own fields, rows are zipped `strict=True`, and the lookup matches the BioSample by exact key. Probed through plan, act and write.
- Four-cell row limit: holds with hostile places (A-94-07); the cell is at most 4 + 2 + 128 characters.
- Non-isolate tables: the BioSample and SRA tables in the same answer kept their "Published" and "Created" columns; `isolate_place` returns None for every other type.
- Lookup not planned for: `What is BioSample SAMN02147118?`, `What is the Salmonella BioSample SAMN02147118?` (no isolate word), SRA runs (`SRR1234567` with a Salmonella isolate named), a BioProject, an assembly. Planned in Plain language exactly as in Researcher.
- Lookup error, raise and Act timeout: the answer still comes, with the BioSample records and the note "The background search of Pathogen Detection did not finish ... Ask again to retry." Only the tool's own `"timeout"` status breaks (A-94-03).
- Follow-up turns: the accession is read from the current turn's text only, so a follow-up naming no accession plans no lookup (read, not probed).

## Verdict

FAIL. A-94-03 loses the whole answer when the lookup's own budget runs out, A-94-08 measured 35 s and 55 s waits on questions that answered from the BioSample summary on `develop`, and A-94-04 gives no word about Pathogen Detection when the lookup finds nothing, which A-94-01 makes reachable for a real isolate.

Verified with my own probes: A-94-01 and A-94-02 (offline `plan_node` over 16 questions), A-94-03, A-94-04, A-94-05 and A-94-07 (offline `plan_node`, `act_node`, `write_node` with only the tools and model faked, both reading depths), A-94-06 (direct call), A-94-08 (two live tool calls, no model call). Read only: A-94-09, the surface escaping in A-94-07, the follow-up behaviour.

None of these sits inside an earlier fix made during this card; A-94-03's pass-through is older than the card, and the card adds the new way to reach it.
