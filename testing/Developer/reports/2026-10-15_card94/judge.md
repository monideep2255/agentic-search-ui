# Card 94 judge, round 2 (dial position 2), 2026-10-16

Subject: pull request #244, `git diff 7626fe85...2aceb25e`. Judge worktrees: `<scratchpad>/judge94/j94` at 2aceb25e and `<scratchpad>/judge94/j94dev` at 7626fe85.

## Findings

### J2-94-01: Under the 8 s bound only the oldest tenth to fifth of Salmonella isolates can be shown; most named isolates get "took too long"
- Severity: major (unsure whether the owner knew the size of this cost when the 8 s row was taken on their behalf)
- What: the Salmonella metadata file (snapshot PDG000000002.4262) has 898,837 rows, about 870 MB, ordered roughly by accession age. The lookup reads it from the top, so the time to find an isolate grows with its row. Under the 8 s Act bound an isolate past roughly row 100,000 to 160,000 (11 to 18 percent of the file, accessions up to about SAMN08 to SAMN10, i.e. older submissions) is cut and the person sees "took too long" instead of the strain, place, date and genes. The build report and the 8 s decision row say "roughly a quarter of the way into the file"; measured here it is less, and network variance moves it.
- Reproduction: judge probe streaming the metadata file: row 50,000 SAMN06033867 at 2.1 s, row 100,000 SAMN08362344 at 4.2 s, row 150,000 SAMN10138914 at 6.1 s, row 200,000 SAMN12036166 at 7.9 s, total 898,837 rows in 38.1 s. Tool called directly (`isolate_lookup`, `skip_snp_distance=True`), total seconds: SAMN02147118 1.8; SAMN08362344 (row 100k) 7.0; SAMN12036166 (row 200k) 8.3; SAMN16248642 (row 300k) 10.6; SAMN10138914 (row 150k) 15.6 on a slow read. Three of four rows from 11 percent on exceed 8.0 s.
- Why it matters: the user's words promise the isolate's details "within about 20 seconds" for "one named isolate". For a recent isolate, which is what a researcher is most likely to ask about, the answer is the BioSample record plus "took too long" every time. Honest, but the card's headline outcome holds for a minority of isolates. The owner should see this number before merge, not "about a quarter".
- NOT FIXED

### J2-94-02: The lookup still scans the cluster list for a cluster id the answer never shows, spending part of the 8 s bound
- Severity: minor
- What: with `skip_snp_distance=True` `_isolate_lookup` still streams `reference_target.cluster_list.tsv` (47 MB, 820,394 rows for Salmonella) to fill `pds_cluster`. No code in `core/` reads `pds_cluster` or `snp_distance` (grep of `src/system_03_search_agent/core` finds only the `skip_snp_distance` key), so the answer never shows it.
- Reproduction: stage timings from the judge probe: cluster-list stage 1.4 s (SAMN02147118), 1.3 s, 1.5 s, 0.4 s, 1.2 s, 1.8 s, 0.8 s. SAMN12036166: metadata found at 6.3 s, cluster list 1.8 s, total 8.3 s, so under the app's bound this isolate is cut only because of the unseen cluster read.
- Why it matters: up to about 2 s of an 8 s bound goes to data nobody sees, moving isolates from "shown" to "took too long". The build report names the scan under Not covered but not its effect on the bound.
- NOT FIXED

### J2-94-03: A lookup that raises, or is refused by the call ceiling, shows no line and its failed result goes into the writer's evidence
- Severity: minor
- What: the card 94 handling (line, empty pairs) covers only the harness timeout and a returned tool status. `_execute_planned_call`'s other exits for the lookup, "call failed unexpectedly" (any exception) and `CallBudgetExceededError`, return `_error_outcome` unchanged: no `layer_raw_output`, so `_isolate_lookup_note` finds no lookup and returns None, and the error pair stays in `findings`. The build's own reasoning is that a failed lookup in the evidence sends the answer to the code-built list.
- Reproduction: judge offline probe (plan_node, act_node, write_node with tools and model faked) on the PR tree, question "What is known about Salmonella isolate SAMN64233002 in Pathogen Detection?", lookup executor raising RuntimeError: `ACT findings [('pathogen_detection', 'error', None), ('ncbi_efetch', 'ok', 1), ('ncbi_efetch', 'ok', 1)]`, `failed_searches []`, tokens carry no Pathogen Detection line at all. Same probe with the tool returning status "error": line "The Pathogen Detection lookup of SAMN64233002 did not complete, so only its BioSample record is shown." and no pathogen finding.
- Why it matters: the user's words promise "one plain line saying so" whenever the details are not shown. On these two paths the person sees silence, and the failed pair is excluded from `failed_searches` too, so nothing at all says Pathogen Detection was tried. Rare (the tool contract says it never raises), hence minor.
- NOT FIXED

### J2-94-04: The new field's description, card number and owner date included, enters every question's model prompt
- Severity: minor
- What: `skip_snp_distance`'s `Field(description=...)` ("Card 94 (owner, 2026-10-15): when true the lookup does not scan ... which took about 18 of the 20 seconds and which the answer does not show ...") is serialised into the pathogen_detection tool schema in the system prompt the model receives. It is the only difference between the two trees' prompts.
- Reproduction: judge offline probe, same question and fakes on both trees, every model prompt captured and diffed: 2 prompts each; prompt 0 is 38,977 characters on the PR tree against 38,597 on develop, prompt 1 39,607 against 39,227; `difflib` shows one changed line in each, line 9, the pathogen_detection schema. The user-side evidence block is byte-identical.
- Why it matters: about 380 characters of build-history prose are sent to the model on every question, not only isolate ones, and the text tells the model about a flag only code sets. Small cost and noise, no answer change measured.
- NOT FIXED

### J2-94-05: The higher "ask" rate on the not-found question is not caused by the lookup: the writer's evidence is identical on both trees
- Severity: unsure (informational; the cause found is sampling noise on a pre-existing fallback, not a card 94 defect)
- What: on the not-found and timed-out paths, every input that can floor trust at "ask" is the same on both trees. `failed_searches` is `[]` on both (the lookup is excluded), the lookup's pair is dropped so `findings` is the same two ncbi_efetch rows, and the model's evidence block is byte-identical; the only prompt difference is the schema line in J2-94-04. "ask" on this shape comes from `structured_fallback_used` (the model's summary failed grounding), which is a draw from the same prompt on both trees. 11 of 12 against 5 of 9 is Fisher exact p = 0.08 one-sided, 0.12 two-sided.
- Reproduction: judge offline probe, "What is known about Salmonella isolate SAMN64233002 in Pathogen Detection?", lookup faked as empty, tool "timeout", tool "error", and a 30 s sleep cut by the real 8 s bound: each run on the PR tree prints `ACT findings [('ncbi_efetch', 'ok', 1), ('ncbi_efetch', 'ok', 1)]` and `ACT failed_searches []`, identical to develop's run of the same question. Write does not read Act's events. The live paired runs are in J2-94-06 below if made.
- Why it matters: the lookup does not lower trust; develop already sends this question shape to the code-built list about half the time or more, which is a separate, pre-existing problem a person sees as "no written summary could be checked".
- NOT FIXED

### J2-94-06: No test holds "the organism is read only from the record whose accession is the asked one"; a mutation removing the match stays green
- Severity: minor
- What: `_biosample_record_fields` returns a record only when its `accession` field equals the asked accession. Replacing that condition with `if True:` (any record of the output counts) leaves every test green. The card's checklist names this property ("organism read only from the matching BioSample record") and the docstring claims it, but the fakes only ever return one record per output, so the condition is never exercised.
- Reproduction: in the judge worktree at 2aceb25e, `sed` replaced `if str(fields.get("accession", "")).upper() == accession.upper():` with `if True:` in `core/graph.py` (1 match, line 8763), then `pytest tests/system_03_search_agent/core/test_isolate_search_wiring.py tests/system_03_search_agent/tools/test_pathogen_detection.py tests/system_03_search_agent/core/test_accession_wiring.py -q`: `98 passed in 2.72s`. File restored from a copy; `git status --short` empty afterwards.
- Why it matters: if a summary output ever carries a second record (a linked record, a merged accession), the organism could come from it and send the lookup to the wrong organism's data, the exact failure card 94's organism decision was made to prevent, with nothing to catch a regression.
- NOT FIXED

### J2-94-07: Live trust tally and live prompt capture for the not-found question (completes J2-94-05; its "J2-94-06 below" reference means this entry)
- Severity: unsure
- What: live, the PR tree still reads "ask" more often than develop on "What is known about Salmonella isolate SAMN64233002 in Pathogen Detection?", but the model's live prompts on both trees differ only in the pathogen_detection schema line (J2-94-04), so the lookup's result, error and line do not reach the writer. The remaining candidate causes are that schema text and chance; the data does not separate them.
- Reproduction: judge live runs, develop's settings. Develop: 4 of 5 "ask" (batch, CONC=2) plus 1 of 1 (logged) = 5 of 6. PR tree: 5 of 5 (batch) plus 0 of 1 (logged, shipped "answer") plus 4 of 4 (logged) = 9 of 10. Pooled with the builder's runs: develop 10 of 15, PR 20 of 22, Fisher exact p = 0.079 one-sided, 0.095 two-sided. Logged run, every model call captured on both trees: guard and think prompts identical apart from the random query fence; both synth prompts 38,643 against 39,023 and 39,257 against 39,637 characters, one differing line each, the schema. The model's raw reply on BOTH trees opens "The Pathogen Detection system holds a record for BioSample accession SAMN64233002", a false statement the grounding gate removed in every shipped answer I captured.
- Why it matters: the card does not lower trust through its evidence. If the owner wants the rate difference settled, the next probe is to drop the field description from the prompt schema and rerun about 20 per tree; I did not, to stay inside the spend.
- NOT FIXED

### J2-94-08: Query 42 itself, the card's flagship, reads "took too long" under light load, and the unseen cluster-list read is most of its lookup time
- Severity: major
- What: SAMN02147118 is row 1 of the Salmonella metadata file, yet its lookup sits close to the 8 s bound once three lookups run at once, and the cluster-list read (J2-94-02) is 1.3 to 2.0 s of its 1.5 to 2.2 s when alone. Live through the app, query 42 showed "The Pathogen Detection lookup took too long and was stopped, so only the BioSample record of SAMN02147118 is shown." in 1 of 5 judge runs (the builder saw 1 of 6), and one run that did find it took 27.3 s end to end.
- Reproduction: direct tool calls, `skip_snp_distance=True`: alone 1.5, 1.6, 2.2 s (stages: metadata 0.0 s, cluster list 1.3 to 2.0 s) and 4.9 s in a later single call; three at once [7.2, 7.6, 7.7] s and [6.6, 5.9, 7.7] s, all status ok. Live app batch (CONC=3, two query 42 runs beside two SAMN12036166 runs and three BioSample questions): run 1 14.3 s, pathogen_detection "error", line "took too long"; run 2 27.3 s, isolate shown. Serial runs: 16.7 s and 10.6 s, lookup closed at 6.4 s and 6.8 s from the start, about 2 s after it began.
- Why it matters: the person asking the very question the card was built for will, on a busy deployment, sometimes see the BioSample record and "took too long" for an isolate Pathogen Detection holds at row 1. Skipping the cluster read (the answer never shows it) would take about 2 s off every lookup; that is the owner's or lead's call, since the decision named only the SNP scan.
- NOT FIXED

### J2-94-09: A genus match sends a Pathogen Detection isolate to the wrong organism folder, and the answer then says it "was not found" there
- Severity: major
- What: `organism_of_record` matches the record's organism name against the 20-entry table, species before genus, so any Klebsiella that is not K. pneumoniae maps to the `Klebsiella` folder and any Listeria that is not L. monocytogenes to the `Listeria` folder. Pathogen Detection keeps separate folders for these (`Klebsiella_oxytoca`, `Listeria_innocua`; the FTP root lists 108 folders). The lookup scans the wrong file, finds nothing inside the 8 s bound, and the line reads "<acc> was not found in NCBI Pathogen Detection's Klebsiella data", while Pathogen Detection holds the isolate. This is the failure the owner's "organism from the BioSample record" decision was made to prevent (a lookup sent to the wrong data and back empty), now through the record's own organism.
- Reproduction: judge probe. `organism_of_record("Klebsiella oxytoca")` -> Klebsiella, `("Klebsiella michiganensis")` -> Klebsiella, `("Listeria innocua")` -> Listeria. Row 1 of `Klebsiella_oxytoca`'s metadata is SAMN02603580 (Klebsiella michiganensis KCTC 1686): tool in `Klebsiella` (what the app asks) -> `empty` in 4.9 s; the same accession in `Klebsiella_oxytoca` -> `ok` in 0.4 s. Row 1 of `Listeria_innocua` is SAMEA3138320 (Listeria innocua Clip11262): in `Listeria` -> `empty` in 2.3 s; in `Listeria_innocua` -> `ok` in 0.3 s. Both empties land inside the 8 s bound, so the person gets the "not found" line, not "took too long".
- Why it matters: a confident wrong statement about a record, which the user's-chair rule ranks worse than a missing one. A researcher asking about a K. oxytoca or L. innocua isolate is told Pathogen Detection does not hold it.
- NOT FIXED

### J2-94-10: The "no organism" line tells the person Pathogen Detection does not cover organisms it does cover
- Severity: minor
- What: for a record whose organism is outside the 20-entry table the line reads "Pathogen Detection was not looked up for <acc>: its BioSample record names no organism that Pathogen Detection covers here". Pathogen Detection has 108 organism folders, including Enterobacter_hormaechei, Vibrio_parahaemolyticus, Neisseria_meningitidis, Serratia, Citrobacter_freundii, Streptococcus_pyogenes.
- Reproduction: `organism_of_record` returns None for "Enterobacter hormaechei", "Vibrio parahaemolyticus", "Neisseria meningitidis", "Escherichia albertii"; FTP root listing at `pathogen/Results` returns 108 folder names containing each of the first three.
- Why it matters: "here" is the only hedge; a reader takes it as "Pathogen Detection does not cover this organism", which is false for about 80 organisms. The build report names the limit under Not covered, but not that the line overstates it.
- NOT FIXED

### J2-94-11: Live confirmation of J2-94-09 through the app
- Severity: major (same defect as J2-94-09, confirmed end to end)
- What: through `run_streaming` on the PR tree with develop's settings, a Listeria innocua isolate Pathogen Detection holds is reported as not found.
- Reproduction: "What is known about Listeria isolate SAMEA3138320 in Pathogen Detection?": 16.2 s, pathogen_detection `empty`, answer line "SAMEA3138320 was not found in NCBI Pathogen Detection's Listeria data, so only its BioSample record is shown." The tool asked for the same accession in `Listeria_innocua` returns `ok` (J2-94-09). "What is known about Klebsiella isolate SAMN02603580 in Pathogen Detection?": 16.0 s, pathogen_detection `error`, "took too long" (concurrency pushed the 4.9 s wrong-folder scan past 8 s this time); the isolate is in `Klebsiella_oxytoca`.
- Why it matters: as J2-94-09.
- NOT FIXED

### J2-94-12: The bound's test accepts any value up to 12 s, so a bound that breaks the 20 s answer would stay green
- Severity: minor
- What: `test_a_lookup_that_outruns_its_bound_is_stopped_and_says_so` asserts `_ISOLATE_LOOKUP_ACT_TIMEOUT_SECONDS <= 12`. The decision row is 8 s, chosen so that 8 + 8 + 4 is about 20 s; at 12 s the measured worst case is about 24 s.
- Reproduction: read only; not mutated (one mutation per round, J2-94-06).
- Why it matters: drift in the one number that holds the 20 s promise is not caught.
- NOT FIXED

### J2-94-13: Probe note, a session-memory traceback appears on both trees in judge live runs
- Severity: unsure (judge harness artefact, not attributed to card 94)
- What: `CallerIdentityRequired: session memory requires the caller's namespaced identity ... got None` is logged in judge live runs on BOTH trees, because the judge script builds `RequestContext` with no caller. One query 42 run on the PR tree ended `refuse` with cost None in 14.5 s with this traceback; it is excluded from every count above.
- Reproduction: `probes/live_judge.py` runs on `j94dev` and `j94`; the traceback prints in each batch.
- Why it matters: only that the excluded run is disclosed.
- NOT FIXED

## Verdict

FIX FIRST.

J2-94-09 and J2-94-11 sit inside a fix made in this phase (the organism-from-record change that answered J-94-04 and A-94-01 of the 2026-10-09 round): the review loop's stop condition fires, and this goes to the product owner rather than another round. J2-94-01 and J2-94-08 are the owner's to weigh: with the 8 s bound the card's headline promise holds for about the oldest tenth to fifth of Salmonella isolates, and even query 42 reads "took too long" under light load.

Spend: about $0.11 of $0.30, 25 counted live runs plus 1 excluded, no Opus.

## Verified by my own probes versus only read

| Claim | How |
|---|---|
| Lookup planned only for a BioSample accession plus an isolate word | Probe: offline plan on both trees (lookup first, then biosample and sra summaries on PR; none on develop); live, three BioSample questions with no isolate word made no pathogen_detection call on PR |
| Skip flag set by the app; other modes unchanged | Probe: offline Act recorded `skip_snp_distance=True`; queries 33 to 37 plan identically on both trees (offline); F-3.5-A-05 path read only |
| Timeout shaped as error, no crash | Probe: develop's Act raises `ValidationError ... input_value='timeout'` on all five isolate search queries with the tool's timeout; PR returns `error` with failure kind `timed_out` |
| Organism from the matching record only | Probe: live record fields for 5 accessions; mutation survives (J2-94-06); wrong-folder mapping (J2-94-09) |
| Four lines | Probe: offline empty, timeout, error, 8 s cut, raise (no line, J2-94-03); live "not found", "took too long" |
| 8 s for the lookup only, 150 s elsewhere | Probe: 30 s fake cut at 8 s; 9 s isolate_search fake not cut |
| Nothing cited that was not shown | Probe: 25 live runs, Pathogen Detection cited only where an isolate row was shown |
| Trust | Probe: offline and live prompt capture, J2-94-05 and J2-94-07 |
| Privacy | Probe: diff scan for submitter, organisation, local path patterns, nothing found; answers show strain, accession, genes, place, year only |
| Gates | Run: `ruff check` All checks passed!; gate 2 isort exit 0 (Skipped 2 files); unit suite 6959 passed, 143 skipped, 24 deselected, 1 xfailed in 277.87 s |
| Build report's controls 33 to 37 live timings | Read only |
