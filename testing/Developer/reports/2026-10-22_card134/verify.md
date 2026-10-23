# Card 134: fresh verifier, after the fix round

Pull request #299, branch `fix/card134-papers-keep-their-titles`, fix round 7b0d4e01 after the develop merge a639fdfc. Written by a fresh verifier with no prior context, 2026-10-22. Findings are appended as they are established; the verdict is at the end.

## Table of contents

- [Findings](#findings)
- [Runs](#runs)
- [Verdict](#verdict)

## Findings

### V-134-01: Regression of: J-134-04. The new rank demotes a PubTator3 paper's view even when its row holds the title, so any other one-sentence view of the same page names the paper
- Severity: minor (not worse than develop in the realistic cases; worse than the pre-fix round in two constructed ones)
- What: `_number_only_paper_view` (`src/system_03_search_agent/synthesis/findings.py:1436-1446`) returns 1 for every `Publication`/`pmid` finding. Its docstring says that view "names nothing", but after this card the row's `title` names it (`answer_layout.record_label` reads the row). So in the per-page fold a titled PubTator3 view loses to whatever other one-sentence view shares the page, whether or not that view names the paper.
- Reproduction: own probe through `graph.write_node`, writer faked, Researcher depth, run on develop `5b9b5125`, the pre-fix-round branch `a639fdfc` and HEAD `7b0d4e01`:
  - PubTator3 row for 20000002 titled "PT B title.", then a PubMed EFetch record for 20000002 with no title and a one-sentence abstract "Only one sentence abstract". Develop `['20000002', 'PMID:20000002']`; pre-fix `['PT B title.', 'PMID:20000002']`; HEAD `['Only one sentence abstract', 'PMID:20000002']`. The paper is named by its abstract text. Plain: develop `Published paper`, HEAD `Only one sentence abstract`.
  - PubTator3 rows for 11111111 ("PT version") and 22222222 ("PT title for placeholder paper"), then graph `Article` rows on the same pages with titles "A graph paper title." and "[Not Available]." (raw rows, not passed through card 38's cleaning). Develop `['11111111', ...], ['22222222', ...]`; pre-fix shows both PubTator3 titles; HEAD shows the graph's `'[Not Available].'`. In production the graph's placeholder title would be cleaned upstream, so this second case is a fixture artifact in part; I did not trace that path.
  - With a bare graph `Article` row (no title) after the PubTator3 row, HEAD shows the graph paper's live PubMed title, which is fine.
- Why it matters: rare (a PubMed record with no title, or a graph paper whose title is a placeholder, sharing the page with a titled PubTator3 row that came first). In the first case a reader sees an abstract sentence where a title belongs. The rank should arguably fire only when the row holds no usable title, as `answer_layout._is_untitled_paper_row` already decides. This sits inside the fix round's code.
- NOT FIXED

### V-134-02: Regression of: J-134-04. With the PubTator3 finding first, papers now split into two sections and move down the page
- Severity: minor (order and grouping change; row count unchanged; titles better than develop)
- What: the fold keeps a paper's PubMed view instead of its PubTator3 view, and the kept finding keeps its own position and its own type, `pubmed`. So the paper leaves "Publication records found" for a separate "Pubmed records found" section, placed where the PubMed finding sat.
- Reproduction: same probe. PubTator3 rows for 20000001, 20000002, 20000003 (all titled) first, then PubMed EFetch titles for 20000002 and 20000003:
  - Develop: one heading `Publication records found`, rows `20000001`, `20000002`, `20000003` (numbers).
  - HEAD: `Publication records found` with `['PT A title.', 'PMID:20000001']`, then a second heading `Pubmed records found` with `PubMed B title.` and `PubMed C title.`.
  - Mixed answer (genes, a variant, graph articles, PubTator3 papers, dbSNP, trials, PubMed): develop puts `Publication records found` before `Clinical trial records found`; HEAD drops that section and adds `Pubmed records found` after the trials, last on the page. The summary sentence follows the new order: in the set with graph genes and a variant it changed from `Found 2 papers, 2 gene records ... [1][2]` to `Found 2 gene records, 1 sequence variant record and 2 papers [4][5]`.
  - The same two-section split already happens on develop when the PubMed finding comes first, so the shape is not new; the fix round makes it happen in both orders.
- Why it matters: one set of papers in two tables, one titled with a raw database name, "Pubmed". The listing's length is unchanged; only grouping and order move. For genes, variants and trials alone, nothing moves (see the evidence entry below).
- NOT FIXED

### V-134-03: "PMID:42477928 | PMID:42477928" is the same doubled number, and the test that guards it cannot see that form
- Severity: minor (not worse than develop; the false sentence is gone)
- What: for a PubTator3 paper with no usable title, the Paper cell and the Identifier cell now both read `PMID:42477928`. Develop read `42477928 | PMID:42477928`; the pre-fix round read `Title not retrieved | PMID:42477928`. The reader still sees the paper's number twice and nothing else, which is the card's original complaint in a new form. The test helper `_no_doubled_number` (`tests/system_03_search_agent/core/test_enrichment_paper_titles.py`) checks only `cells[:2] != [pmid, f"PMID:{pmid}"]` and `cells[:1] != [pmid]`, so it passes on `['PMID:42477928', 'PMID:42477928']`, while its name says no number is doubled; `test_with_no_usable_title_the_row_is_named_by_its_pmid` pins the doubled form as the expected output.
- Reproduction: own probe, Researcher: develop `[['42477928', 'PMID:42477928']]`, pre-fix `[['Title not retrieved', 'PMID:42477928']]`, HEAD `[['PMID:42477928', 'PMID:42477928']]`. Same for a bracketed translated title `[Clinical study of ovarian cancer].`, whose English title the run holds and the row does not show (A-134-01's residue). Plain on all three trees: `Published paper`.
- Why it matters: better than develop only in that the system name is shown, and better than the pre-fix round in that nothing false is said. It matches how card 38 slice C names a graph paper (`answer_layout.py:940-944` says so; I did not probe card 38's graph form). Whether "the same number twice" is acceptable is a product call, not a defect I can prove.
- NOT FIXED

### V-134-04 (evidence, no defect): for genes, variants, trials and graph papers the new rank changes nothing
- Severity: none, evidence only
- Unit fuzz, own script: 3,000 random groups of 1 to 8 `SynthFinding`s over shared and blank pages, fields `name, title, symbol, pmid, abstract, nct_id, rsid, clinical_significance, summary, overall_status, annotation_count`, one- and two-sentence values. `one_finding_per_record` and `_listing_order` outputs hashed per tree:
  - Types `Gene, SequenceVariant, Variant record, Clinical trial, Article, pubmed, Literature entity, Disease` (no `Publication`): develop, pre-fix and HEAD all `a2cf9dc994c0e7618f20667954b43d3b`, identical.
  - With `Publication` added: develop and pre-fix `7880f745...`, HEAD `9fbf8030...`. 23 of 3,000 groups differ, all in which view is kept, none in the number of entries (0 length differences).
- End to end, own `write_node` probe, graph genes (one with a two-sentence summary), a graph variant, graph articles, a dbSNP record and two trials, no PubTator3 rows: rows identical across develop, pre-fix and HEAD, Researcher and Plain.
- `"Publication"` is produced only by `graph.py:5089` (the PubTator3 builder); the graph's vertex labels (`tools/graph_schema_constants.py:44-56`) have no `Publication`, so no graph row can trip the rank.

### V-134-05 (evidence): the closed items, re-derived
- A-134-01, A-134-04, A-134-09: `grep -rn "Title not retrieved\|UNTITLED_PAPER_LABEL" src frontend/src` returns nothing; the only hit is the test's negative assertion. Probe: no row in any of 10 scenarios on HEAD carries that text. Closed, with V-134-03's residue.
- J-134-04: PubTator3 first, PubMed EFetch titles for two of three papers: HEAD shows `PubMed B title.` and `PubMed C title.`, not the PubTator3 text; PubMed first gives the same. Closed, with V-134-01 and V-134-02 as side effects.
- A-134-06: the `summary_label` branch is gone (`answer_layout.py:1792-1799` now ends in `record_label`). Closed.
- J-134-07: see the break-it entry.

### V-134-06: A-134-02 (retractions) is still open, and in the PubTator3-only case it is a new surface rather than an old one
- Severity: unsure (whether this counts as "worse than develop" is the owner's call; I am filing it so it is not read as settled)
- What: `grep -rni retract src` finds no code that reads or marks a retraction. When the PubMed search finishes, develop already lists a retracted paper under its PubMed title with no mark (the EFetch title row), and the fix round makes PubMed's title win in both orders, so that path is unchanged in kind. When only PubTator3 holds the paper, develop showed `9500320 | PMID:9500320` and HEAD shows the paper's full title. I did not re-fetch 9500320 live; this rests on the adversary's live reading (A-134-02, A-134-04) and on my reading of the unchanged label path.
- Why it matters: "A confident wrong record is worse than a missing one." A retracted paper named in plain words looks like support; a number did not. It is the same class develop already shows on its PubMed path.
- NOT FIXED

### V-134-07 (evidence): the other open items are unchanged by the fix round and none is worse than develop
- A-134-07 (`<sup>` fusion): offline probe `'Mutation rate of 10<sup>-9</sup> per site'` gives `'Mutation rate of 10-9 per site'`. Still open, in PubTator3-only rows only; develop showed the number.
- J-134-02 (entities): `'A &amp; B'` stays `'A &amp; B'`. J-134-03 (attributed tags): `'<i class="x">BRCA1</i>'` gives `'<i class="x">BRCA1'`. Neither observed live by either reviewer.
- A-134-08: `'[Clinical study of BRCA1 [ER+] tumours].'` is kept, the live 42477928 form is withheld and now reads `PMID:42477928` (V-134-03).
- J-134-01, A-134-03, A-134-05 (PubTator3's text differs from PubMed's by a full stop, a mark or a transliteration): now visible only when PubMed's own title is not on the page, because PubMed's view wins whenever it is (V-134-05). Narrower than before the fix round.
- J-134-06 (CLI and GraphQL still show the number): not re-probed; the fix round touched no render path for those surfaces (the diff is `findings.py` and `answer_layout.py` label code only).

### V-134-08: Break it, both mutations go red
- Severity: none, evidence only
- `_listing_rank` reverted in a scratch edit of the worktree to `return (multi_sentence, finding.ref_index)`: the new test file, `synthesis/`, `test_graph.py` and `test_pubtator_annotate.py` give `2 failed, 1629 passed, 10 skipped, 1 xfailed`. Red: `test_when_the_background_search_holds_the_title_pubmeds_row_names_the_paper[28340353-...-None-False]` and `[42477928-...-False]`. The parametrisation where both sources give the same title (`[28340353-CFTR-CFTR-False]`) stays green under the mutant, so it cannot tell which view won; harmless, as the other two cover it. Restored with `git checkout -- <file>`; `git diff HEAD` empty.
- J-134-07's mutant, `_FORMATTING_TAG` replaced by `r"<[^>]*>"`: the new test file and `test_pubtator_annotate.py` give `3 failed, 58 passed`. Closed. Restored; `git diff HEAD` empty, `git status --short` shows only `?? frontend/node_modules`.

## Runs

From the worktree root on HEAD `7b0d4e01`:

- `tests/system_03_search_agent/core/test_enrichment_paper_titles.py`: `21 passed in 2.59s`
- PubTator3 tool tests (`test_pubtator_annotate.py`, `_premise.py`, `_schemas.py`): `120 passed, 6 skipped in 0.25s`
- `tests/system_03_search_agent/synthesis/`: `1319 passed, 10 skipped, 1 xfailed in 8.67s`
- `tests/system_03_search_agent/core/test_graph.py`: `251 passed in 6.21s`
- Gate 2, `venv/bin/isort --check-only --diff src tests services tracker alembic .claude .github`: `Skipped 2 files`, exit 0
- Gate 3, `venv/bin/ruff check .`: `All checks passed!`, exit 0
- Develop `5b9b5125` (the merge base, equal to `origin/develop`) and the pre-fix branch `a639fdfc` were probed as `git archive` copies in the session scratchpad. No stash, no commit, no push.
- Network: no PubTator3 calls and no model calls. Over the brief's budget, unintentionally: two of my `write_node` scenarios held a graph `Article` row with no title, and `write_node` resolved it live through `resolve_article_titles` (PubMed, read only). Instrumented afterwards: 2 resolutions per process, 6 processes, so between 6 and 12 read-only PubMed calls depending on the in-process cache. Every other scenario made no resolution call (instrumented on HEAD: `{"calls": []}`).

## Verdict

PASS: nothing I found is worse than develop for the person reading the answer. Two minor findings sit inside the fix round's own code (V-134-01, V-134-02, both "Regression of: J-134-04"), so Rule 4's stop condition is met and goes to the lead and owner. Neither puts a false statement on screen in the realistic cases, and neither changes the number of rows.

| Claim | How checked |
|---|---|
| No "Title not retrieved" anywhere | Own grep, own probes in 10 scenarios |
| PubMed's title wins in both orders | Own `write_node` probe, three trees |
| Rank changes nothing for genes, variants, trials, graph papers | Own fuzz (3,000 groups, three trees) and own end-to-end probe |
| Rank changes grouping and order when PubTator3 comes first | Own probe (V-134-02) |
| Rank can pick a worse view than the pre-fix round | Own probe, two constructed cases (V-134-01) |
| Untitled row reads `PMID:n PMID:n` | Own probe (V-134-03) |
| Tag-rule tests now catch the broad regex | Own mutation (V-134-08) |
| `_listing_rank` is guarded by a test | Own mutation (V-134-08) |
| Retraction, transliteration, CLI and GraphQL | Read only, resting on the judge's and adversary's live readings |
| Production finding order, frontend rendering of `cells`, card 38's graph placeholder path | Not probed |
