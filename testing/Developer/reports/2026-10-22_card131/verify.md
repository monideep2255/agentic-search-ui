# Card 131 part 1: fresh verifier report

Verifier for pull request #292 after its fix round (commit dc3e0bd1). Findings are appended as they are established.

## Findings

### V-131-01: the derived-row rule makes Researcher and Plain state different paper counts for the same answer
- Regression of: A-131-03 (the fix round's `_is_paper_finding`, `src/system_03_search_agent/synthesis/answer_layout.py:1756-1764`)
- Severity: minor
- What: a "derived" row cited to a PubMed or PMC page now counts as a paper in the Researcher line, but `plain_noun` still calls it a "record" in the Plain line. Both depths are built from the one `counted` list, and the item 12.9 docstring says they carry exactly the same records and counts. The totals still agree; the per-noun counts do not.
- Reproduction: scratch probe calling `answer_summary_sentence` on develop's and the branch's `answer_layout.py` (both unpacked by `git archive`), findings [derived "Proj title." field title, url `https://pubmed.ncbi.nlm.nih.gov/1/`; Gene "BRCA1"; Article "Real title." url `.../3/`], subject BRCA1:
  - branch Researcher: `Found 2 papers and 1 gene record for BRCA1 [1][3]: BRCA1 [2].`
  - branch Plain: `I found 1 record, 1 gene and 1 published paper related to BRCA1 [1][2][3].`
  - develop Researcher: `Found 1 derived record, 1 gene record and 1 article record for BRCA1: Proj title. [1], BRCA1 [2] and Real title. [3].` (three groups, matching Plain's three)
  - Two derived PubMed rows alone: branch Researcher `Found 2 papers for BRCA1 [1][2].`, Plain `I found 2 records related to BRCA1 [1][2].`
- Why it matters: a reader who switches between Plain and Researcher on one answer sees "2 papers" in one and "1 published paper" in the other. Only reachable when a model-written query projects paper columns as scalars (A-131-03 notes this has reached the line live before). Develop's line used the code word "derived" but the two depths grouped the records the same way.
- NOT FIXED

### V-131-02: the derived-row rule counts any projected value cited to a PubMed page as a paper and drops its name
- Regression of: A-131-03 (`answer_layout.py:1760-1764`)
- Severity: minor (unsure how often a live plan projects a non-paper column before a PMID)
- What: a derived row's `source_url` is the first resolvable CURIE in the RETURN columns (`tools/cypher_provenance.py:827-850`, 925-927). A query such as `RETURN a.pmid, g.symbol` makes the gene symbol finding a derived row cited to PubMed. The branch calls it a paper and removes its value from the line. A Gene-typed record whose URL points at PubMed is not affected (only the type "derived" is tested).
- Reproduction: same scratch probe, findings [derived "BRCA1" field symbol, url `https://pubmed.ncbi.nlm.nih.gov/111/`; Gene "TP53"], subject BRCA1:
  - branch: `Found 1 paper and 1 gene record for BRCA1 [1]: TP53 [2].`
  - develop: `Found 1 derived record and 1 gene record for BRCA1: BRCA1 [1] and TP53 [2].`
  - Gene-typed "BRCA1" with a PubMed url: `Found 1 gene record for BRCA1: BRCA1 [1].` on both.
- Why it matters: the value is a gene symbol, not a paper title, so the line now hides a name the card did not ask to hide. The noun "paper" is defensible because the cited page is a paper.
- NOT FIXED

### V-131-03: the PubMed test is a substring match on the whole URL
- Severity: unsure (not reachable today as far as I found: derived URLs are built by `source_url_for_curie` from fixed templates, not taken from data)
- What: `"pubmed.ncbi.nlm.nih.gov" in url` matches anywhere in the URL, including a query string or path, rather than the host.
- Reproduction: derived finding with url `https://example.org/?r=pubmed.ncbi.nlm.nih.gov`, value "Value X": branch `Found 1 paper for BRCA1 [1].`, develop `Found 1 derived record for BRCA1: Value X [1].`
- Why it matters: only if a derived row's URL ever comes from data rather than a template. A host check would close it.
- NOT FIXED

### V-131-04: in a mixed answer the paper markers sit after the subject or the total, so they read as that phrase's citation
- Regression of: J-131-03 and A-131-02 (the fix round's `paper_markers` placement, `answer_layout.py:1984-1986`)
- Severity: minor (a reading problem, not a wrong fact: every marker still opens its own record, and the marker set equals develop's)
- What: the paper markers are appended to `head`, which ends with the subject phrase or ", of N available", and the named non-paper records follow after a colon. In the shape the brief names, the subject reads as carrying two different markers.
- Reproduction: scratch probe, branch:
  - [Gene "BRCA1", Article, Disease "Breast cancer"]: `Found 1 gene record, 1 paper and 1 disease record for BRCA1 [2]: BRCA1 [1] and Breast cancer [3].` BRCA1 is followed by [2] and then by [1].
  - [Gene "BRCA1", pubmed paper], total 9: `Found 1 gene record and 1 paper for BRCA1, of 9 available [2]: BRCA1 [1].` [2] reads as the source of "9 available", which is the graph total, not the paper.
  - [Gene, Article, ClinicalTrial "T1", Article]: `Found 1 gene record, 2 papers and 1 clinical trial record for BRCA1 [2][4]: BRCA1 [1] and T1 [3].`
  - develop, same three: every marker attached to a name (`... for BRCA1: BRCA1 [1], A paper title. [2] and Breast cancer [3].`, `... of 9 available: BRCA1 [1] and T. [2].`).
- Against develop: worse in one property (a reader can no longer tell from the line which record [2] is) and better in the card's (no pasted title, no doubled stop). Develop already printed bare markers after "of N available" for more than six records, so the bare-marker shape itself is not new; mixing bare and named markers in one line is. A form such as "...: BRCA1 [1], Breast cancer [3] and 1 paper [2]." would keep each marker beside its noun. Wording is the owner's call.
- NOT FIXED

### V-131-05: CI is red on the pull request head: the fix round's new import breaks gate 2, so gates 3, 4, 6 and 9 never ran
- Regression of: J-131-02 (the fix round was to make the pull request merge green; the import was added in dc3e0bd1)
- Severity: major for tonight's merge condition ("once CI is green"), trivial to fix
- What: dc3e0bd1 added `from dataclasses import replace` above `import re` in `tests/system_03_search_agent/synthesis/test_answer_layout.py:11-12`. isort wants `import re` first. Gate 2 fails, and the job skips Gate 3 (lint), Gate 4 (unit suite), Gate 6 (Python audit) and Gate 9 (required paths), so CI has not yet run the unit suite on this head at all.
- Reproduction: `gh pr checks 292` on head b247de02: `Python gates (1, 2, 3, 4, 6, 9)	fail`, the other three pass. `gh run view 39885418121 --log-failed`: `ERROR: .../tests/system_03_search_agent/synthesis/test_answer_layout.py Imports are incorrectly sorted and/or formatted.` with the diff `+import re` / ` from dataclasses import replace` / `-import re`. Job steps: `Gate 2: Import order: failure`, `Gate 3: Lint: skipped`, `Gate 4: Unit test suite: skipped`, `Gate 6: Python dependency audit: skipped`, `Gate 9 ...: skipped`.
- Why it matters: the owner's merge condition is not met, and the green suite is only my local run on the named files, not CI's full gate 4. J-131-04 (gate 6 on graphql-core) cannot be confirmed closed by the develop merge until gate 6 actually runs.
- NOT FIXED
- Addendum to V-131-05: run locally from the worktree root, `venv/bin/isort --check-only src tests services tracker alembic .claude .github` prints the same `ERROR: .../test_answer_layout.py Imports are incorrectly sorted`, and `venv/bin/ruff check` (gate 3) gives `I001 [*] Import block is un-sorted or un-formatted --> tests/system_03_search_agent/synthesis/test_answer_layout.py:9:1`, `Found 1 error.` So gate 3 fails too once gate 2 is fixed by hand only if the fix is not the isort order; one reorder fixes both.
- Correction to the addendum's last sentence: gate 3 (`ruff check`, rule I001) fails on the same import block today, independently of gate 2. Putting `import re` above `from dataclasses import replace` fixes both.
- Local gate 4 on head b247de02, run as the gate script runs it (`PYTHONPATH=src pytest -m "not integration" -q`, junit file sent to scratch): `8482 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 479.13s`. No failure, so once the import order is fixed the unit suite is expected green; CI has not confirmed that.

## Fix round claims, checked by my own probes

Probes ran on develop's and the branch's `src` unpacked to the scratchpad by `git archive` (origin/develop 78c307fa, branch head b247de02), never by editing the worktree.

- J-131-01, fixed. No strip remains (`summary_label` is byte-identical to develop). "Streptomyces sp." gives `Found 2 organism taxon records for x: Streptomyces sp. [1] and Other [2].` and "..." gives `... [1]`, both equal to develop.
- J-131-02, fixed. `test_variant_record_label.py::test_opening_sentence_is_pinned_as_it_reads_now` now pins `Found 1 variant record: rs334 [1].` and passes; the M4 mutation below turns it red.
- J-131-03, fixed. Non-paper names are kept beside papers: `Found 1 gene record, 1 paper and 1 disease record for BRCA1 [2]: BRCA1 [1] and Breast cancer [3].` `test_reader_pass_reach_probe.py` passes, and the M5 mutation (names hidden when a paper is present) turns its control arm red. New shape filed as V-131-04.
- J-131-05, fixed. With titles back inline (M1), `test_sentence_check.py::test_the_opening_sentence_counts_a_paper_cited_twice_once` and `test_bare_topic_clarification.py::test_a_picked_window_leaves_the_graph_s_undated_papers_out` both go red now. The first pins `Found 2 papers [2][3].` exactly.
- J-131-08, fixed (read): `answer_layout.py:37-40` now describes the count form.
- A-131-02, fixed. Nouns follow first appearance at both depths. Probe [Gene, Article, ClinicalTrial, Article]: Researcher `Found 1 gene record, 2 papers and 1 clinical trial record ...`, Plain `I found 1 gene, 2 published papers and 1 clinical trial ...`. End to end through `write_node` with the test module's stubbed model, `_mixed_state` gives branch `Found 3 disease records, 2 clinical trial records and 2 papers for BRCA1 [1][2][3][4][5][6][7].`, the same noun order as develop's `... and 2 pubmed records ...` and as Plain.
- A-131-03, fixed for the reported shape: two derived title rows cited to PubMed give `Found 2 papers for BRCA1 [1][2].` (develop: `Found 2 derived records for BRCA1: BRCA1 and breast cancer. [1] and A second paper. [2].`). The rule's side effects are filed as V-131-01, V-131-02 and V-131-03.

## Left open on purpose: not worse than develop

- A-131-01 and A-131-04: `diff -rq -x __pycache__` of the two `src` trees lists only `answer_layout.py`, so the offer, the note and the heading in `core/graph.py` are byte-identical to develop. On develop the count line and the heading both said "record records" and "pubmed records"; on the branch only the heading and offer still do. Not worse; the two now disagree on one screen, as the adversary filed.
- A-131-05: `Found 2 papers for BRCA1 [1][2].` over off-topic titles, as filed. This is the card's intended removal of titles; unchanged by the fix round.
- A-131-07: PubMed plus PMC copy of one paper gives `Found 2 papers [1][2].`, develop `Found 1 pubmed record and 1 pmc record: ...`. Same count and markers; unchanged by the fix round.
- J-131-07: `Found 1 clinvar record, 1 snp record, 1 medgen record and 1 ncbi_efetch record ...` identical on both.

## Counts, totals and markers against develop

- 30 fixtures (papers only, mixed in several orders, with and without a total and a subject, six and seven records, derived rows, variant records, PubMed plus PMC, unkeyed paper, unknown type, abbreviation and dot names, efetch codes), each run at both depths on both trees.
- A script compared, per fixture, the sorted marker set, the summed noun counts, the "of N available" total and the full Plain sentence: `30 fixtures, 0 differ in markers/total/available/plain`. The comparator was checked on three known lines (parsed 4, 7 and 2).
- The marker order differs by design in mixed answers (paper markers first, then named ones); see V-131-04.
- End to end, `_mixed_state`, `_papers_state` and `_state` give the same citation ids at both depths on both trees.

## Test runs

- `pytest tests/system_03_search_agent/synthesis/ tests/system_03_search_agent/core/test_write_answer_structure.py tests/system_03_search_agent/core/test_bare_topic_clarification.py tests/system_03_search_agent/synthesis/test_sentence_check.py tests/system_03_search_agent/core/test_reader_pass_reach_probe.py`: `1440 passed, 10 skipped, 1 xfailed in 18.57s`.
- Full local gate 4: `8482 passed, 143 skipped, 24 deselected, 1 xfailed`.
- Local gate 2 and gate 3: both fail on `test_answer_layout.py`'s import order (V-131-05).

## Break it

The worktree's `answer_layout.py` was copied to the scratchpad (sha 7f58235f), mutated by a script one property at a time, and the same test set run each time:

- M1, develop's title naming restored (papers named inline, no separate paper markers): `6 failed`, including test_sentence_check, test_bare_topic_clarification and test_write_answer_structure.
- M2, paper noun forced first (A-131-02's shape): `1 failed` (`test_card_131_count_line_counts_papers_and_keeps_other_names`).
- M3, derived rule off: `1 failed`. No test checks that Plain and Researcher agree on derived rows (V-131-01).
- M4, "record record" strip off: `2 failed`.
- M5, names hidden when a paper is present (J-131-03's shape): `4 failed`, including the reach probe's control arm.
- M6, paper markers dropped from the line: `5 failed`.
- Restored by copying the saved file back: sha 7f58235f again, `git diff HEAD --stat` empty, `git status --short` shows only `?? frontend/node_modules`.

## Verdict

- HOLD. The behaviour the fix round claims is there, and counts, totals, markers and Plain equal develop's on every fixture. But the owner's merge condition is not met: CI is red on the head (V-131-05, gate 2 import order, which also skipped gates 3, 4, 6 and 9 on CI).
- Rule 4: four findings sit inside the fix round's own code (dc3e0bd1) and are filed with "Regression of:". V-131-05 (major for tonight's merge, a one-line import reorder), V-131-01 (Plain and Researcher give different paper counts for derived rows), V-131-04 (paper markers read as the subject's or the total's citation in mixed answers) and V-131-02 (a projected gene symbol cited to PubMed is counted as a paper and unnamed). V-131-03 is unsure. None states a wrong fact or a wrong marker; V-131-01 and V-131-04 are the two ways the branch reads worse than develop.
- Verified by my own probes: every fixed claim above, the four left-open items' state against develop, counts and markers on 30 fixtures, the end-to-end `write_node` openings, the named test files, the full local gate 4, local gates 2 and 3, CI's status and log, and six mutations.
- Only read: J-131-08's docstring text, and how derived rows get their URL (`tools/cypher_provenance.py:827-850, 925-927`), which V-131-02 and V-131-03 rely on.
