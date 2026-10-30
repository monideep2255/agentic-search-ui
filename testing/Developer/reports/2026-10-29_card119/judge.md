# Card 119 judge, one round (2026-10-29)

Branch fix/card119-ten-papers-in-a-window, commit e2244a2c, draft PR #312. Findings appended as established.

## Findings

Method: develop (b5690f98) and the branch HEAD (e2244a2c) were exported with `git archive` to a scratch folder, and one probe test was dropped into each copy. The probe drives the real compiled graph (`compiled_graph.ainvoke`, real planner, real Act row shaping, real `build_synth_findings`, real writer prompt assembly) with tools and models stubbed through the same seams `test_bare_topic_clarification.py` uses (`_install_tools`, `_install_models`, `_install_decide`). The ESearch stub answers as many ids as the call's own `retmax` asks for, out of a pool of 12 PMIDs of mixed length; the fetch stub answers one record per requested id. The writer prompt is captured at `litellm.acompletion`.

### J-119-E1 (evidence, not a defect): a question with no window is unchanged end to end
Develop and branch, "recent papers on BRCA1 from the last 5 years?" typed with no click, PubMed pool of 10 and of 3. A unified diff of every event payload, the planned call list and both writer prompts, after masking random call ids and timings, differs only in `call_elapsed_s` and `pa-` call ids (16 lines each side, 0 content lines):
```
out_dev_u10.json | search retmax [5] | fetch [5] | quota 10 | writer titles 5 abstracts ['37000005','38000001','38000002','39000010','9000001']
out_br_u10.json  | search retmax [5] | fetch [5] | quota 10 | writer titles 5 abstracts ['37000005','38000001','38000002','39000010','9000001']
```
Same for the pool of 3 (3 titles, 3 abstracts both sides).

### J-119-E2 (evidence): a windowed gene question lists up to ten titled papers and the writer reads at most five abstracts
Branch, clicked "last 5 years" option, BRCA1:
```
w3  | search retmax [10] | fetch [3]  | quota 15 | claim 'Found 3 papers and 1 gene record for BRCA1 [1][2][3]: BRCA1 DNA repair associated [4]. ' | listed 3 | writer titles 3 abstracts 3
w7  | search retmax [10] | fetch [7]  | quota 15 | claim 'Found 7 papers and 1 gene record for BRCA1 [1][2][3][4][5][6][7][8]. ' | listed 7 | writer titles 7 abstracts 5
w10 | search retmax [10] | fetch [10] | quota 15 | claim 'Found 10 papers and 1 gene record for BRCA1 [1]...[11]. ' | listed 10 | writer titles 10 abstracts 5 (38000001, 38000002, 38500000, 39000010, 39100000)
w12 | search retmax [10] | fetch [10] | quota 15 | same as w10
dev w10 | search retmax [5] | fetch [5] | 'Found 5 papers and 1 gene record ...' | listed 5
```
"Found N papers" equals the rows listed in every case. The five abstracts are the five numerically highest PMIDs; 9000001 (lowest number, sorts last by URL) is correctly excluded.

## Defects

### J-119-01: the five abstracts are picked by PMID before checking that a paper has an abstract, so the writer can read none while five listed papers have one
- Severity: major
- Where: `src/system_03_search_agent/core/graph.py:7992-8003` (`_pubmed_abstract_rows`): `newest = sorted(...title_rows..., key=_pmid, reverse=True); abstract_urls = set(newest[:limit])` is computed over all title rows; the `abstract` presence check happens later inside the loop, so a newest paper with no abstract still uses up one of the five slots.
- Reproduction: branch probe, windowed BRCA1, ten papers, the five highest PMIDs (39100000, 39000010, 38500000, 38000002, 38000001) fetched with a title and no abstract, the other five with an abstract:
```
out_br_w10noabs.json | search retmax [10] | fetch [10] | quota 15
  claim: ['Found 10 papers and 1 gene record for BRCA1 [1]...[11]. ']
  listed pubmed rows: 10
  writer titles 10 abstracts []
```
  Develop, the same window, would have read every abstract the five listed papers carry. The newest PubMed records are exactly the ones most likely to have no abstract yet (in-process records, letters, comments, editorials), so this is not an exotic case.
- What a person sees: ten paper titles and a summary that says nothing from any of them ("From the paper" sentences vanish) even though half the listed papers have abstracts.
- NOT FIXED

### J-119-02: the one argument that makes a windowed answer list ten papers can be deleted and every test stays green
- Severity: blocking
- Where: `src/system_03_search_agent/core/graph.py:8597-8598`, Act's `_ncbi_efetch_output_to_structured_fields(ncbi_efetch_output, purpose, planned.gene_symbol, planned.row_cap)`. No test drives `_execute_planned_call` (or the graph) with a windowed abstracts follow-up; every new test calls the shaping function directly with a hand-passed `row_cap`.
- Reproduction (mutation M4e): replace that call's arguments with `ncbi_efetch_output, purpose, planned.gene_symbol` (drop `planned.row_cap`), then run the new file plus the seven related files the builder named:
```
== M4e Act ignores planned.row_cap
328 passed in 10.13s
```
  The same mutation in a scratch copy, driven end to end by the judge's probe (windowed BRCA1, ten papers found):
```
out_m4e_w10.json | search retmax [10] | fetch [10] | quota 15
  claim: ['Found 5 papers and 1 gene record for BRCA1 [1][2][3][4][5]: BRCA1 DNA repair associated [6]. ']
  listed pubmed rows: 5
  writer titles 5 abstracts ['34000000', '35000000', '36000003', '37000005', '38000001']
```
  So the card's whole visible effect reverts (five papers listed, and ten papers fetched for nothing), while the suite reports green. Restored with `git checkout -- src/system_03_search_agent/core/graph.py`.
- What a person sees if this regresses: five papers after picking a window again, the card silently undone, with no test to say so.
- NOT FIXED

### J-119-03: the raised lead quota (15) changes nothing a person or the writer sees in any case the judge built, and its two call sites are unguarded
- Severity: minor
- Where: `src/system_03_search_agent/core/graph.py:5578-5592` (`_lead_findings_quota`) and its call sites `graph.py:8992` and `graph.py:14372`.
- Reproduction: (a) mutation M7b, both call sites set back to `lead_quota=_LEAD_FINDINGS_QUOTA`: `328 passed in 9.48s`. Mutation M7a (the function returns 10) turns only the pinned-value test red: `FAILED ...::test_the_lead_quota_is_fifteen_when_windowed_and_ten_otherwise / 1 failed, 327 passed`; the writer-slice test `test_the_writer_s_first_thirty_findings_hold_exactly_five_abstracts_when_windowed` stays green at quota 10. (b) The M7b copy driven end to end against the branch, windowed BRCA1 with ten papers, with 1, 25 and 99 extra graph Disease rows (the last saturates the 100-row display cap): every event payload and both writer prompts identical apart from `call_elapsed_s`; at 99 rows both give `writer findings 30 abstracts 5 titles 10 | citations 90 | listed pubmed 10`.
- Why it matters: the build report's account ("so the five abstracts stay inside the model's 30-finding slice instead of queueing behind the context rows") is not demonstrated; the abstract limit alone does that. Either the quota guards a case nobody has built, or it is dead weight that reads as a safety control. Unsure which; filed so the lead decides.
- What a person sees: nothing today.
- NOT FIXED

### J-119-04: "the five newest" is unpinned: sorting PMIDs as text instead of numbers stays green
- Severity: minor
- Where: `graph.py:7995-8003`; the test pool `_PMIDS = [str(30000 + n) ...]` in `tests/system_03_search_agent/core/test_window_paper_cap.py:21` is all five-digit, so text order equals number order.
- Reproduction: mutation M6c, `sorted(..., key=_pmid, reverse=True)` -> `sorted(..., reverse=True)` (URL text order): `328 passed in 9.26s`. With mixed-length PMIDs (the judge's probe pool includes 9000001) text order ranks 9000001 (a 2000s paper) above 39100000.
- What a person sees if this regresses: on a long window ("last 30 years") the writer reads abstracts of old papers while the newest go unread. Today's code is right; the test would not notice it going wrong.
- NOT FIXED

### J-119-05: PubTator3 now annotates ten papers but keeps five rows, and they are mostly the papers whose abstracts the writer did not read
- Severity: minor
- Where: `breadth_plan.py:878-886` (the annotate call carries the same ten ids as the fetch) and `graph.py:5115-5116` (PubTator rows sorted by URL text then cut to `_LAYER_TOOL_ROW_CAP` = 5, untouched).
- Reproduction: branch probe, windowed BRCA1, ten papers, PubTator stub returning one Publication per requested PMID. PubTator call input: `{'mode': 'annotate_publications', 'pmids': [ten ids]}`. Kept Publication rows: `34000000, 35000000, 36000003, 37000005, 38000001`. Abstracts the writer read: `38000001, 38000002, 38500000, 39000010, 39100000`. Overlap: one paper. On develop (same scenario) the five PubTator rows and the five abstracts are the same five papers.
- Why it matters: the PubTator3 call is twice the size for five rows, and the enrichment facts the writer sees sit on papers it has only a title for, while the papers it read have none. Nothing is mis-cited (all ten are listed), so minor.
- What a person sees: PubTator3 annotation facts tied to older listed papers, none to the newest five the summary is written from.
- NOT FIXED

### J-119-06: with six or more papers the count line stops naming the gene record
- Severity: minor (unsure it is unwanted)
- Where: `src/system_03_search_agent/synthesis/answer_layout.py:2007-2019`, the `len(counted) <= MAX_SUMMARY_NAMES` (6) branch; card 119 is what pushes a windowed answer past it.
- Reproduction: develop, windowed, ten papers available: `'Found 5 papers and 1 gene record for BRCA1 [1][2][3][4][5]: BRCA1 DNA repair associated [6]. '`. Branch, same: `'Found 10 papers and 1 gene record for BRCA1 [1][2][3][4][5][6][7][8][9][10][11]. '`. Branch with seven papers: `'Found 7 papers and 1 gene record for BRCA1 [1]...[8]. '`.
- What a person sees: the opening sentence becomes a run of eleven bare markers with no name in it. Pre-existing rule, newly reached.
- NOT FIXED

### J-119-07: the carried cap is not clamped to what PubTator3's schema accepts
- Severity: minor (latent)
- Where: `graph.py:5563-5573` returns any positive `retmax` from the planned search; `breadth_plan.py:858-886` passes it to `select_ids` and then `PubtatorAnnotateInput.model_validate({"pmids": selected})`, whose `pmids` is `max_length=20` (`pubtator_annotate_schemas.py`, design decision 5 text at lines 99-120); ESearch `retmax` allows up to 500 (`ncbi_efetch_schemas.py:256`).
- Reproduction: read only, not run. Raising `PUBMED_WINDOW_RESULT_CAP` above 20 would make the PubTator follow-up raise a validation error at planning rather than be capped.
- What a person sees: nothing today (the value is 10).
- NOT FIXED
- Addendum to J-119-07, now run: the schema field is `pubtator_annotate_schemas.py:385-388` (`max_length=_MAX_PMIDS`). `bp.plan_literature_follow_up([30 ids], 25)` -> `ValidationError ... annotate_publications.pmids List should have at most 20 items after validation, not 25`. So the bound holds (fails closed), it just fails loudly instead of capping.

### J-119-08: every first-stage ncbi_efetch call's row cut now comes from the PubMed constant, not the breadth row cap
- Severity: minor (latent, same value today)
- Where: `graph.py:4829` `row_cap: int = breadth_plan.PUBMED_RESULT_CAP` on `_PlannedNcbiEfetchToolCall`; Act now always passes `planned.row_cap` (`graph.py:8597-8598`), so the shaping function's own default `row_cap: int = _BREADTH_ROW_CAP` (`graph.py:8302`) is never used from Act. First-stage calls built by `_planned_from_breadth` (`graph.py:5433-5436`) and the gene dataset report (`graph.py:6498`) take the dataclass default. The judge's probe state shows it: `gene_summary row_cap 5`, `clinvar_search row_cap 5`, `omim_search row_cap 5`, `pubmed_search row_cap 5`.
- Why it matters: both constants are 5 today (`graph.py:4933`, `breadth_plan.py:121`), so nothing changes now. The day someone moves `PUBMED_RESULT_CAP` (the unwindowed paper count), every accession summary, organism record list and gene summary row cut moves with it, which nobody editing that constant would expect.
- What a person sees: nothing today.
- NOT FIXED

### J-119-E3 (evidence): the remaining controls each turn a test red
Mutations run on the worktree, each restored with `git checkout -- <file>` and `git status --short` confirmed:
```
M1 gene window retmax -> 5                     2 failed, 326 passed
M2 topic window retmax -> 5                    2 failed, 326 passed
M3 follow-up select_ids cap -> 5               2 failed, 326 passed
M4a carried cap dropped in _follow_up_calls_for 2 failed, 326 passed   (red, not an error: the builder's "errored" note does not reproduce)
M4b _pubmed_search_retmax always 5             2 failed, 326 passed
M4c follow-up planner not given the cap        1 failed, 327 passed
M4d concrete row_cap not carried               1 failed, 327 passed
M4e Act drops planned.row_cap                  328 passed   (J-119-02)
M5 row cut back to _BREADTH_ROW_CAP            3 failed, 325 passed
M6a abstract limit never applied               3 failed, 325 passed
M6b oldest five instead of newest              1 failed, 327 passed
M6c text order instead of number order         328 passed   (J-119-04)
M6d limit + 1                                  3 failed, 325 passed
M7a quota function returns 10                  1 failed, 327 passed
M7b quota call sites flat 10                   328 passed   (J-119-03)
```
Baseline, the same eight files: `328 passed in 11.19s`.

### J-119-E4 (evidence): CI's own gates, from the worktree root
```
$ ruff check .            (ruff 0.16.0, venv)
All checks passed!
$ isort --check-only --diff src tests services tracker alembic .claude .github   (gate02's command)
isort exit=0
```
The build report's note that isort flags `graph.py` does not reproduce with gate02's exact command.

### J-119-E5 (evidence): security and production-standards gates for the diff
- Timeouts: `git diff origin/develop...HEAD | grep -i timeout` returns nothing; `_LAYER_TOOL_ACT_TIMEOUT_SECONDS` and the efetch timeout are untouched.
- Bounds: the windowed ESearch is `retmax` 10 (`breadth_plan.py:128`), validated by `NcbiEfetchInput` (`retmax` `ge=1, le=500`, `ncbi_efetch_schemas.py:256`); fetch `ids` `max_length=50` (`:271-273`); PubTator `pmids` `max_length=20` (`pubtator_annotate_schemas.py:385-388`, fails closed, J-119-07). No new collection outlives a request.
- Schema validation at the hop: the follow-up inputs are still built through `NcbiEfetchInput.model_validate` and `PubtatorAnnotateInput.model_validate` (`breadth_plan.py:868-885`).
- Not verified by the judge: the windowed answer's time and the joined answer length against the 8000-character cut on MCP (`adapters/mcp/server.py:202, 1295-1298`) and GraphQL (`adapters/graphql/fold.py:1112-1116`). Both surfaces truncate on a word boundary and add a note rather than fail. Five more title rows add roughly 0.7k to 1.5k characters of list text. The lead's paid live check owns this; until it reports, this check is open, not passed.

### J-119-E6 (evidence): unwindowed topic question and unwindowed gene question with PubTator rows are unchanged
Develop against branch, full masked diff of events, planned calls and writer prompts: "recent papers on statins from the last 5 years?" typed, and BRCA1 typed with PubTator returning publications: 8 changed lines each, all `call_elapsed_s`.

## Verdict

FAIL, blocking: J-119-02. Also open: J-119-01 (major), J-119-03 to J-119-08 (minor).

Verified with the judge's own probes (end to end through the real graph, or by mutation): unwindowed gene and topic paths identical to develop; windowed gene and topic paths search 10, fetch up to 10, list up to 10 titled papers, writer reads at most 5 abstracts; "Found N papers" equals the rows listed at 3, 7, 10 and 12 papers available; failed abstracts fetch behaves as develop; the 30-finding slice keeps the 5 abstracts with 25 and 99 graph rows; PubTator row mismatch; every mutation listed in E3; ruff and gate02 isort.
Read only, not run: J-119-08's latent coupling (values printed from the probe state, consequence argued); the disease-anchored windowed path (same `plan_first_stage` code, not driven); answer length on MCP and GraphQL and the windowed answer's time (the lead's live check).
Not a fix made during this phase's earlier rounds: this is round one, so no finding sits inside a previous round's fix.
