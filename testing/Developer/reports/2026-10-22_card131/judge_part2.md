# Card 131 part 2 judge, one round

Branch fix/card131-skip-repeated-count-line (commit 0ce8b7ab), worktree s3-worktrees/card131b. Diff: `src/system_03_search_agent/core/graph.py` (+25/-1) and one new test file. Findings are appended as they are established.

## Findings

### J-131b-01: the "linked to N conditions" fold clause is not counted as an extra clause, so the linked-disease count vanishes when the lead cites the anchor records
- Severity: major
- What: the call site's flag at `src/system_03_search_agent/core/graph.py:15521-15526` is True only for a known graph total or an asked field. It ignores the fold clause that `answer_summary_sentence` appends (`answer_layout.py`, ", linked to {len(titles)} conditions" / "diseases"). The fold's count includes linked conditions that are not cited records, so it carries a fact the lead does not, yet the subset test at `graph.py:13830-13836` drops the whole line. When no linked disease is itself a cited finding, the fold adds no markers, so the line's markers are only the anchors' and any lead citing the anchors is a superset.
- Reproduction: scratch probe (`scratchpad/probe1.py`) building the count line with the real `answer_summary_sentence` for 3 `SequenceVariant` findings whose rows carry `clinvar_condition_ids` over 6 resolved MedGen CURIEs, then calling `_answer_parts` with lead "Three variants of HNF1A are reported as pathogenic [1][2][3]." and `summary_has_extra_clause=False` (what the call site computes: no truncation, no asked field).
  - Branch, Plain: summary `'Three variants of HNF1A are reported as pathogenic [1][2][3].  \n\n'`; the count line `I found 3 genetic variants related to HNF1A [1][2][3], linked to 6 conditions.` is gone.
  - Branch, Researcher: summary `'Three variants ... [1][2][3].  \n\n'`; `Found 3 sequence variant records for HNF1A: rs100 [1], rs200 [2] and rs300 [3], linked to 6 diseases.` is gone.
  - origin/develop, same inputs: both depths keep the count line after the lead.
- Why it matters: worse than develop. "Linked to 6 conditions" is the only place the answer states how many distinct conditions the variants link to. Plain language lists titles only, with no mapping column, so the number appears nowhere else. Researcher shows per-row disease cells, which the reader would have to de-duplicate and count by hand. The brief named this case; the flag does not cover it. The new test file has no fold case.
- NOT FIXED

### J-131b-02: past 20 records the count line counts more records than it cites, so a lead citing the first 20 drops a count of records the lead never cites
- Severity: minor (unsure how often a lead carries 20 markers)
- What: `answer_summary_sentence` caps the line's markers at `MAX_SUMMARY_MARKERS = 20` (`answer_layout.py:1622`) while its number counts every record, and `marker_ids` in `_answer_parts` also caps at 20 (`graph.py:13304-13309`). The subset test at `graph.py:13830-13836` compares the capped markers, so "same records" is judged on 20 of 25.
- Reproduction: scratch probe (`scratchpad/probe2.py`), 25 `Gene` findings, real `answer_summary_sentence`, lead "These genes are in the pathway [1]...[20].", flag False.
  - Branch, Researcher: count line `Found 25 gene records for X [1]...[20].`; summary `'These genes are in the pathway [1]...[20].  \n\n'`, count line dropped.
  - Branch, Plain: count line `I found 25 genes related to X [1]...[20].`, dropped the same way.
  - origin/develop: the count line follows the lead.
- Why it matters: the line that says 25 is removed because a sentence cites 20, which is not the owner's "cites the same records". The 25 rows are still in the list, so the reader can count them; the harm is small, but the rule fires outside its own definition.
- NOT FIXED

### J-131b-03: the subset test compares citation ids, not records, so on the real paper path a lead that cites the same two papers keeps the repeated count line
- Severity: major
- What: `graph.py:13830-13834` compares `marker_ids`, which are citation ids, one per cited FIELD. The count line keeps one finding per page, preferring the title (`answer_layout.py`, the `by_page` fold keyed on `source_page_key`), while a written sentence cites the abstract finding of the same paper, which is a different citation id with a different marker. The owner's rule is "cites the same records"; the code tests "cites the same markers", which never holds when the lead quotes a paper's abstract. `_label_only_positions` also keeps title-only sentences from being picked as the lead, so on paper questions a lead citing the title findings is the rare case.
- Reproduction: scratch end-to-end probe (`scratchpad/e2e/probe_e2e.py`) driving the real `write_node` with the card 17 test's fixture (two PubMed records, title and abstract each), the Synth reply `Lakes are fed by glacier melt [a: "Glacier melt feeds the high lakes each summer"] and valleys hold fine silt [b: "Cores show valleys filled with fine silt"].`, and `_lead_sentence_choice` monkeypatched to pick sentence 0. The call site passed `summary_has_extra_clause=False`. Tokens emitted, Researcher:
  - `claim 'Lakes are fed by glacier melt [3] and valleys hold fine silt [4]. '`
  - `claim 'Found 2 papers [1][2]. '`
  - then the two table rows `[1]` and `[2]`, the same two papers.
  - Plain: `'Lakes are fed by glacier melt [3] and valleys hold fine silt [4]. '` then `'I found 2 published papers on this topic [1][2]. '`.
- Why it matters: the card's goal is not met on the paper path. The lead and the count line cite the same two papers and both still print, the "says one thing twice" the owner asked to remove. Not worse than develop, since this is develop's behaviour. The new tests miss it because they build the count line by hand and give the lead the very same markers, `_LEAD` and `_COUNT` both `[1][2][3][4]` (`test_card_131_skip_repeated_count_line.py:19-20`); no test runs `write_node` or `answer_summary_sentence`. Comparing `source_page_key` of each marker's citation, the key the count line already folds on, would match records rather than fields. Unverified for graph disease records, the owner's own example, where the lead may cite the same name findings the count line keeps.
- NOT FIXED

- J-131b-03 addendum, confirmed from the same run's citation events: `[1] pubmed/11111111 title`, `[2] pubmed/22222222 title`, `[3] pubmed/11111111 abstract`, `[4] pubmed/22222222 abstract`. The lead's [3][4] and the count line's [1][2] are the same two pages.

### Evidence: paths that behave as the acceptance says (own probes)
- Owner's example shape, graph Disease records, real `write_node`, lead picked by monkeypatched `_lead_sentence_choice` (`scratchpad/e2e/probe_disease.py`, fixture from `test_write_completeness`): writer "NCBIGene:672 is associated with four diseases: disease name number 1 [1], ... and disease name number 4 [4]."
  - Researcher, not truncated: call site flag `False`; tokens are the lead, `\n\n`, `Disease records found`, four table rows. The count line `Found 4 disease records: ...` is skipped. The four rows remain.
  - Plain, not truncated: lead, then `Where this answer comes from` and four list items; `I found 4 conditions on this topic [1][2][3][4].` skipped.
  - Researcher, truncated with total 90: flag `True`; `Found 4 disease records, of 90 available: ...` kept after the lead, and the note `Note: this answer was truncated because only 4 of the 90 records ...` still follows the list.
  - Plain, truncated with total 90: flag `True`; `I found 4 conditions on this topic, out of 90 available [1][2][3][4].` kept.
- Listing-first client path (`_request_reads_placement` forced True, `scratchpad/e2e/probe_disease_placement.py`): listing tokens placed `listing` go first, then one `summary` claim, the lead; no count line. Same outcome as the reading-order path.
- No lead picked (`_summary_text(lead=None)` path and the new test): the count line opens the answer as on develop.
- Read only, not probed: the command line (`adapters/cli/render.py` holds listing tokens until the summary and reads no count line), GraphQL, MCP and the saved-answer reopen all replay the tokens `_write_answer` emits; `answer_summary_sentence` has one caller (`graph.py:15444`) and `_answer_parts` three (`graph.py:13068` via `_answer_tokens`, `graph.py:14402` the listing build with no `model_grounding`, `graph.py:15496`); only the last passes the new kwarg, the others take the default True, which keeps the count line. A follow-up turn uses the same `_write_answer`. No sentence check runs after `_answer_parts` that could remove the lead: `name_switched_records` runs before it and skips the lead, card 111's echo removal excludes `lead_index` (`graph.py:13861-13864`), and the lead token is emitted unconditionally once picked (`graph.py:13821`). So the lead cannot vanish after the count line was dropped, as far as the code shows.
- Honest totals: with the count line gone, no list heading states a count ("Disease records found", "Where this answer comes from"); the reader counts the rows. A known graph total keeps the line (flag True). A display-only cut never put a total in the line (D-2) and its truncation note still states "N of M". The trust line's "Based on N sources cited" and the incomplete-answer note's "not covered in the summary above" do not refer to the count line, and a summary (the lead) still exists.

### J-131b-04: the `_answer_parts` docstring still says the count line always follows the lead, and the new kwarg is not documented there
- Severity: minor
- What: `graph.py:13248-13252` reads "it opens the answer, the code-built count line follows it in the same paragraph", and the structure list at `graph.py:13258-13261` describes the summary sentence as always first or second. Neither mentions `summary_has_extra_clause` or the skip; the only description is the inline comment at `graph.py:13823-13829`. (The brief calls the kwarg a parameter of `answer_summary_sentence`; it is a parameter of `_answer_parts`, `graph.py:13236`.)
- Reproduction: `sed -n 13248,13261p src/system_03_search_agent/core/graph.py` on the branch.
- Why it matters: the next builder reads the docstring as the contract. Card 2's statement is now false for the skip case.
- NOT FIXED

### J-131b-05: no test covers the call site's flag; forcing it to False leaves every core and synthesis test green
- Severity: major (test gap on the guard that keeps a stated total; the behaviour itself was correct in my probe)
- What: the only thing that keeps "of 90 available" / "out of 90 available" and the honest-gap clause on screen when the lead cites every record is the expression at `graph.py:15521-15526`. The new tests pass the flag by hand to `_answer_parts`; nothing drives `_write_answer` with a picked lead and a truncated total or an asked field.
- Reproduction: in a scratch copy of HEAD (`git archive HEAD`, never the worktree), replace the six-line expression with `summary_has_extra_clause=False,` and run `pytest -q -m "not integration" tests/system_03_search_agent/core tests/system_03_search_agent/synthesis`: `2 failed, 2912 passed, 66 skipped, 1 deselected, 1 xfailed`. The 2 failures are `test_card23_query_79_quotes_the_line_that_ships` and `test_card23_the_screen_finds_the_line_by_the_words_that_ship`, which fail identically on the unmutated copy (they read files outside the archived paths), so the mutation turns nothing red. My own end-to-end probe shows the real effect of such a regression: the truncated disease answer would lose `Found 4 disease records, of 90 available: ...`, leaving the 90 only in the truncation note.
- Why it matters: a later refactor of the call site could silently drop the graph total from the opening paragraph on every answer that has a lead, and CI would stay green.
- NOT FIXED

### Break it, results
- M1, invert the subset test (`and not set(summary_ids) <= set(marker_ids(lead_text))`, `graph.py:13834`), scratch copy: 4 new failures, all in the new file: `test_count_line_is_skipped_when_the_lead_cites_every_record[plain_language]`, `[researcher]`, `test_count_line_stays_when_the_lead_cites_only_some_records[plain_language]`, `[researcher]`. Red, as it should be.
- M2, delete `and not summary_has_extra_clause` (`graph.py:13833`), scratch copy: 1 new failure, `test_count_line_stays_when_it_has_an_extra_clause`. Red.
- M3, call-site flag forced False: no new failure (J-131b-05). Green, a finding.
- Each mutation was made in the scratch copy and restored with `cp`; `diff graph.py.orig graph.py` empty after each. The worktree was never edited: `git diff HEAD --stat` empty, `git status --short` shows only `?? frontend/node_modules`.

### Runs on the worktree, unmutated
- Named suites: `pytest -q -p no:cacheprovider tests/system_03_search_agent/core/test_card_131_skip_repeated_count_line.py tests/system_03_search_agent/core/test_write_answer_structure.py tests/system_03_search_agent/core/test_write_answer_quality.py tests/system_03_search_agent/synthesis/` gives `1398 passed, 10 skipped, 1 xfailed in 14.85s`.
- Gate 4 command (`pytest -m "not integration" -q`): `8488 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 486.57s`.
- Gate 2: `venv/bin/isort --check-only --diff src tests services tracker alembic .claude .github` prints `Skipped 2 files`, exit 0.
- Gate 3: `venv/bin/ruff check .` prints `All checks passed!`.

## Verdict

FAIL against the acceptance sentence and the owner's bar of nothing worse than develop.

- Met, verified by my own end-to-end probes: on graph Disease records, the owner's own example shape, the count line is skipped after a lead that cites every record, in Plain and Researcher, in reading order and on the listing-first path; it is kept when a graph total is known; it opens the answer as before with no lead.
- Not met, verified by probe: on paper questions a lead citing the papers' abstracts keeps the repeated count line, because the test compares citation ids, not records (J-131b-03). Not worse than develop.
- Worse than develop, verified by probe: the "linked to N conditions" count is dropped with the line (J-131b-01, major), and past 20 records a count larger than the lead's citations is dropped (J-131b-02, minor).
- Test gap, verified by mutation: the call site's flag has no test (J-131b-05).
- Read only, not probed: the command line, GraphQL, MCP and saved-answer reopen surfaces (they replay the same tokens), the follow-up turn (same `_write_answer`), and the claim that no later step removes the lead.
- This change is card 131 part 2's first build, not a fix round, so no finding sits inside a fix made during this phase.

