# Card 131 part 1 judge, one round

Pull request #292, branch fix/card131-count-line-titles, worktree s3-worktrees/card131. Findings are appended as they are established.

## Findings

### J-131-01: the new full-stop strip removes abbreviation dots and ellipses from non-paper names, and blanks a name made only of dots
- Severity: minor
- What: `answer_layout.py:1969` uses `.rstrip('.')`, which removes every trailing full stop, not one. A stored name ending in an abbreviation or an ellipsis is changed, and a name of only dots becomes empty, leaving a bare marker after a double space.
- Reproduction: scratch probe calling `answer_summary_sentence` with two `OrganismTaxon` findings, branch versus origin/develop (copied by `git archive`):
  - "Streptomyces sp." gives branch `Found 2 organism taxon records for x: Streptomyces sp [1] and Other [2].`, develop `... Streptomyces sp. [1] ...`
  - "Acme Inc." gives `Acme Inc [1]`; "Smith et al." gives `Smith et al [1]`; "And so..." gives `And so [1]`
  - "." and "..." give `Found 2 organism taxon records for x:  [1] and Other [2].` (develop: `. [1]` and `... [1]`)
- Why it matters: NCBI Taxonomy holds many names ending "sp." and strain names ending "str."; the line now misquotes the stored record name, which is the thing the line claims to cite. `lead_in_title` at `answer_layout.py:1391` already removes exactly one stop with `removesuffix(".")`, which would keep "...", but would still cut "sp.". Code cannot tell an abbreviation from a sentence end, so any strip is a trade; this one is the widest.
- NOT FIXED

### J-131-02: the branch fails a test in the synthesis suite that pins the old "variant record record" line
- Severity: major
- What: `tests/system_03_search_agent/synthesis/test_variant_record_label.py:346` asserts `first.strip() == "Found 1 variant record record: rs334 [1]."`. The branch changes that line, does not update this test, and the test fails. The pull request touched four test files but missed this fifth one. On GitHub, PR #292's "Python gates (1, 2, 3, 4, 6, 9)" and "Frontend gates (7, 8)" checks both report fail.
- Reproduction: from the worktree root, `venv/bin/python -m pytest -q -p no:cacheprovider tests/system_03_search_agent/synthesis/ tests/system_03_search_agent/core/test_write_answer_structure.py tests/system_03_search_agent/core/test_bare_topic_clarification.py` gives `1 failed, 1434 passed, 10 skipped, 1 xfailed`, with the failure `- Found 1 variant record record: rs334 [1].` / `+ Found 1 variant record: rs334 [1].` at test_variant_record_label.py:346. `gh pr checks 292` gives `Python gates (1, 2, 3, 4, 6, 9) fail` and `Frontend gates (7, 8) fail`.
- Why it matters: the pull request cannot merge green as it stands. The new line is the one the card asks for, so this test's expectation needs updating (its docstring names card 121 as the later fix), but the suite was evidently not run whole before push.
- NOT FIXED

### J-131-03: when papers sit beside other records, the line stops naming the other records too, and a CI control test goes red
- Severity: major
- What: `answer_layout.py:1967` adds `and not papers` to the naming condition, so one paper in the answer suppresses the names of every gene, disease and variant record counted with it, not only the paper titles. The card asked for no paper titles inline. It did not ask to drop gene or disease names.
- Reproduction: scratch probe, branch versus origin/develop:
  - [Article "T1.", Gene "BRCA1", Disease "Breast cancer"] gives branch `Found 1 paper, 1 gene record and 1 disease record for BRCA1 [1][2][3].`, develop `Found 1 article record, 1 gene record and 1 disease record for BRCA1: T1. [1], BRCA1 [2] and Breast cancer [3].`
  - CI on PR #292, Gate 4: `tests/system_03_search_agent/core/test_reader_pass_reach_probe.py:297: AssertionError: assert 'CANARYGENENAMEGAMMA' in 'Found 1 paper and 1 gene record [1][2].  \n\n Gene records found\n\n  Gene record NCBIGene:672 [1].  \n\n Article records found\n\n  Article record PMID:1 [2]. '`. That test is the control arm proving the leak detector is not blind; the gene's name now appears nowhere in the answer, because in that shape the listing shows only "Gene record NCBIGene:672".
- Why it matters: a researcher who asks about a gene and gets one paper alongside it no longer sees the gene's name in the opening line, and in at least this fixture shape nowhere else in the answer either. The CI gate fails (Gate 4: `3 failed, 8478 passed`), and the failing test was not among the four the pull request edited. Narrower alternative to weigh: name the non-paper records and count the papers, for example "Found 1 paper and 1 gene record for BRCA1: BRCA1 [2], and 1 paper [1]". The wording is the owner's call.
- NOT FIXED

- Addendum to J-131-03, local confirmation: on the branch, `pytest tests/system_03_search_agent/core/test_reader_pass_reach_probe.py` gives `1 failed, 3 passed` (`test_the_probe_sees_a_canary_that_does_reach_the_answer`). On origin/develop's src and tests (unpacked to scratch by `git archive`), the same file plus test_variant_record_label.py gives `27 passed`.

### J-131-04: the third CI failure, gate 6 on graphql-core, is not this pull request's
- Severity: unsure
- What: the third Gate 4 failure is `tests/ci/test_gate_scripts.py:158`, a pip audit reporting `graphql-core 3.2.11 CVE-2026-75507` and `CVE-2026-75508`. The diff touches no requirement file, so the cause is a newly published advisory. Frontend gates (7, 8) fail at "Gate 7: Frontend dependency audit", probably for the same reason. Not checked: whether develop now fails the same way, since its last CI run on GitHub is from 2026-10-18.
- Reproduction: `gh run view 39883097071 --log-failed`, lines quoted above; `git diff origin/develop...HEAD --stat` lists only answer_layout.py and four test files.
- Why it matters: PR #292 stays red even after J-131-02 and J-131-03 are fixed. Whoever merges must not take the red checks for this card's fault alone, or this card's two failures for audit noise.
- NOT FIXED

### J-131-05: two of the four edited tests stay green when paper titles are pasted inline again
- Severity: minor
- What: put titles back (scratch edit removing `and not papers` from `answer_layout.py:1967`, everything else unchanged) and `test_sentence_check.py::test_the_opening_sentence_counts_a_paper_cited_twice_once` and `test_bare_topic_clarification.py::test_a_picked_window_leaves_the_graph_s_undated_papers_out` still pass.
  - test_sentence_check.py:531 asserts `"PPIs and bone health." not in text`, with the full stop included. The same pull request strips that full stop from every inline name (line 1969), so the title can come back as `PPIs and bone health [2]` and the check still passes. It cannot fail on the defect it names.
  - test_bare_topic_clarification.py:914 asserts the substring `"Found 1 paper and 1 gene record"`, which "Found 1 paper and 1 gene record: <title> [1] and ..." also contains. Line 913's `"Found 2 article records" not in text` can no longer fail at all, since no paper is called an "article record" now.
  - Before and after: test_sentence_check.py had `startswith("Found 2 publication records")` and `"PPIs and bone health." in text` ("the paper is named by its title, not its abstract"); it now has `startswith("Found 2 papers")` and the `not in` check. The old second assertion also pinned which of the two same-page findings is kept, and nothing pins that now. A probe shows the kept marker is unchanged, `Found 2 papers [2][3].` against develop's `... PPIs and bone health. [2] and MEFV in Turkey. [3].`, but no test asserts `[2][3]`.
- Reproduction: M1 scratch edit, then pytest on the four edited files: `3 failed, 341 passed`. The failures are test_answer_layout.py `test_12_9_a_plain_opening_with_no_subject_says_on_this_topic` and `test_card_131_count_line_never_pastes_titles_or_doubles_full_stops`, and test_write_answer_structure.py `test_12_9_a_papers_question_gives_plain_titles_and_a_researcher_pmids`. Neither test_sentence_check nor test_bare_topic_clarification fails. Restored by copying the saved file back; `git diff HEAD --stat` printed nothing.
- Why it matters: the defect is still caught by two other tests, so this is coverage quality, not a live bug. But two of the four rewritten expectations look checked without checking the property they state. Exact expectations such as `text == "Found 2 papers [2][3]."` and `"Found 1 paper and 1 gene record [1][2]."` would close it.
- NOT FIXED

### J-131-06: the fold clause still pastes a disease name with its stored full stop
- Severity: unsure (read, not run; I did not build a fold fixture)
- What: the linked-disease clause at `answer_layout.py:1984` builds `f"{clip_to_word(f.field_value, 200)} [{slot}]"` with no strip, so a cited linked disease whose stored name ends in "." would still read "Name. [14]." That is the doubled-stop shape the card fixes on line 1969.
- Reproduction: none run. Quoted from the code: line 1984 `f"{clip_to_word(f.field_value, 200)} [{display_slots[f.citation_id]}]"`. MedGen names rarely end in a full stop, which is why this is unsure.
- Why it matters: if such a name exists, the card's "no doubled punctuation" holds for the main list but not for the clause after it.
- NOT FIXED

### J-131-07: database codes still serve as nouns in the Researcher line
- Severity: minor (arguably outside the card, which names only "pubmed records")
- What: live efetch rows take `node_or_edge_type = record.db` (`core/graph.py:8276`), so other databases still read as codes, and the efetch fallback reads as a tool name.
- Reproduction: probe, branch: `Found 1 clinvar record, 1 snp record, 1 medgen record and 1 ncbi_efetch record for x: v1 [1], rs2 [2], d [3] and z [4].` (identical on develop). Types the paper map at `answer_layout.py:1338` does not hold, such as "ScholarlyArticle" and "PubmedArticle", still name their titles inline (`Found 1 pubmed article record for x: T [1].`), but no source code I found emits them.
- Why it matters: the commit subject says "use reader nouns", and "snp record" and "ncbi_efetch record" are the same kind of wording as the "pubmed records" the card removes.
- NOT FIXED

### J-131-08: the module docstring still describes the old Researcher form
- Severity: minor
- What: `answer_layout.py:37-38` still reads `every other depth keeps the technical "Found 5 pubmed records: <titles>" form`, which is the form this pull request removes.
- Reproduction: `sed -n 35,38p src/system_03_search_agent/synthesis/answer_layout.py` on the branch.
- Why it matters: the next reader is told titles are the intended Researcher form, which invites the regression back.
- NOT FIXED

## Checks that held, with evidence
- Full revert (M2, develop's answer_layout.py written over the branch's in scratch): `6 failed, 338 passed`, covering all six changed or new tests. Restored by copying the saved file back; `git diff HEAD` printed nothing and `git status --short` shows only `?? frontend/node_modules`.
- CFTR shape, 54 papers of 1962: branch `Found 54 papers for CFTR, of 1962 available [1]...[20].`, develop `Found 54 article records for CFTR, of 1962 available [1]...[20].`. The cap is the existing `MAX_SUMMARY_MARKERS = 20` (`answer_layout.py:1620`, applied at 1905), the same in both, so the line is not worse.
- Single paper: `Found 1 paper for BRCA1 [1].` Seven papers with a total: `Found 7 papers for TP53, of 500 available [1]...[7].`, the same markers as develop.
- Labels ending in "?" and "!" are kept (`Why? [1]`, `Wow! [1]`). Labels with an internal full stop are kept (`a.b.c [1]`). Bracketed non-English titles and accented text keep everything except the final stop.
- Markers: every probe gives the same marker set and order as develop, including the same-page dedup (`[2][3]` on both).
- Counts: every probe gives the same totals. Mixed types only regroup: "1 pubmed record and 1 article record" becomes "2 papers", and "1 variant record and 1 variant record record" becomes "2 variant records".
- Plain language, run on both trees: `I found 54 published papers related to CFTR, out of 1962 available [1]...[20].` and `I found 1 gene and 2 published papers related to BRCA1, out of 9 available [1][2][3].` are identical. The plain branch (lines 1907 to 1936) sits above the diff's first hunk.
- Text parsers: `grep -rnE "Found |pubmed record|article record|record records"` over src/, frontend/src, clients, services and eval finds no production code that parses the count line, only docstrings, comments and frontend test fixtures. `sentence_token` (`core/graph.py:13318`) reads only `[N]` markers from it.

## Verdict
- FAIL against the acceptance as a mergeable change. The text goals hold in my probes: no paper titles, no "pubmed records", no "record records", counts and markers unchanged, Plain unchanged. But the change also drops non-paper names whenever a paper is present (J-131-03), which breaks a CI control test, and it leaves a stale pinned test (J-131-02). PR #292's Gate 4 is red for both reasons.
- Verified by my own probes: J-131-01, 02, 03, 05, 07 and 08, the CFTR, single-paper, mixed, punctuation, dedup, count and Plain cases, and the break-it runs.
- Read only: J-131-06 (fold clause). J-131-04 is from the CI log only; I did not run gate 6 myself.
