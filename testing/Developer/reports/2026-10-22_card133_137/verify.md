# Card 133 and 137 part 1: fresh verifier, after the fix round

Pull request #300, branch fix/card133-one-record-one-row, fix round 5a23706c. Findings are appended below as they are established.

## Findings

Verifier header, 2026-10-23. Trees compared, each exported with `git archive` into the session scratchpad `ver133/`: develop as merged into the branch (5b9b5125), round 1 merged with that develop (052a7bd4), fix round (5a23706c, HEAD). Shape probe `ver133/probe/shapes.py` calls `_answer_tokens` directly through the judge's `probe_lib.py`; module paths printed to confirm each tree loads its own `graph.py`.

### V-133-01: The fix round's live-row database check is pinned by no test
- Severity: minor
- What: in `own_record_kind` (`src/system_03_search_agent/core/graph.py:13452-13456`) the clause `source.lower() != kind` can be removed and every test in `test_write_answer_structure.py` stays green. The other six new guards each turn a named test red.
- Reproduction: scratch copy of HEAD at `ver133/m_kindsrc`, the clause replaced with `False` (2 changed lines): `78 passed in 3.03s`. Control copy, unmutated: `78 passed in 3.31s`. Same method, each other guard: own-id clause 2 red (`test_two_genes_sharing_a_page_and_a_taxid_stay_two_rows`), CURIE equality 2 red (same test), prefix-map regex 2 red (`test_two_live_rows_on_a_shared_citation_id_stay_two_rows`), edge ends 2 red and edge detection 2 red (`test_two_condition_edges_on_one_clinvar_page_stay_two_rows`), four-name cap 2 red (`test_one_row_shows_at_most_four_names`), two-bracketed-names refusal 1 red (`test_two_names_that_both_carry_brackets_stay_two_rows`).
- Why it matters: low today. A live row's type is its `record.db` and its citation's `source` is the same `record.db` (`graph.py:8276`, `tools/ncbi_efetch.py:194`), so the clause rarely decides anything the prefix-map regex has not already decided. A later edit can still drop it without notice. Inside the fix round's code; not a regression, a gap in its tests.
- NOT FIXED

### V-133-02: A-133-01 no longer nests brackets, but a Plain language gene row still carries two brackets that mean two things
- Severity: minor (cosmetic, the same text round 1 gave in the graph-first order; never a wrong record)
- What: the fix round puts a bracketed name first (`shown_name`, `src/system_03_search_agent/core/graph.py:13480-13490`), so no bracket sits inside another. The organism bracket and the also-called bracket still sit side by side, and in the live-first order the Researcher row and the Plain language row now lead with different names.
- Reproduction: the adversary's `adv/test_adv133.py::test_organism_brackets`, run on the HEAD export. Plain language, either order: `list_item ['tumor protein p53 (Homo sapiens) (TP53)']`. Researcher, live first: `table_row ['TP53 (tumor protein p53)', 'NCBIGene:7157']`. Round 1, Plain language, live first: `['TP53 (tumor protein p53 (Homo sapiens))']`. Develop: two rows, `['TP53']` and `['tumor protein p53 (Homo sapiens)']`.
- Why it matters: a Plain language reader cannot tell "(Homo sapiens)" (the organism) from "(TP53)" (another name). Not worse than develop on what the reader is told, one record, both names, both citations; the brief's closing condition for A-133-01 (no nested brackets) is met.
- NOT FIXED

### V-133-03: Regression of: round 1's merge (the J-133-01 and A-133-01 fixes). The fix round now keeps two rows for some single records that round 1 joined; develop shows the same two rows
- Severity: minor (unsure on reachability; no worse than develop, so it does not touch the merge condition)
- What: a live row now vouches for its identifier only when its database is in `_LAYER2_CURIE_PREFIXES`, which is gene, PubMed and Taxonomy only (`src/system_03_search_agent/core/graph.py:13449-13458`, `synthesis/answer_layout.py:551-555`). Two live ClinVar rows of one variant with the record's own accession, on one page, named differently, now stay two rows. Two names that both carry brackets also never merge now (`graph.py:13485-13486`), so one HGVS-named variant seen twice stays two rows.
- Reproduction: `ver133/probe/shapes.py`, on the three trees. Two live `clinvar` rows, page `.../clinvar/variation/17661/`, both `accession` `VCV000017661`, titles "NM_007294.4(BRCA1):c.68_69del (p.Glu23fs)" and "BRCA1 c.68_69del", calls `a` and `b`. Develop: 2 rows. Round 1: 1 row, `['NM_007294.4(BRCA1):c.68_69del (p.Glu23fs) (BRCA1 c.68_69del)', 'VCV000017661']`, both citations. Fix round: 2 rows, as develop. Two graph `SequenceVariant` rows, CURIE `ClinVar:17661`, names "NM_007294.4(BRCA1):c.68_69del" and "NM_007294.4(BRCA1):c.68_69del (p.Glu23fs)": develop 2 rows, round 1 1 row with nested brackets, fix round 2 rows.
- Why it matters: the DECISIONS.md rule says a record's own identifier on one page merges. For ClinVar, dbVar, OMIM and other databases outside the prefix map, the fix round falls back to develop's two rows. The owner rule ("a confident wrong record is worse than a missing one") favours this side of the line, and I found no question that puts two live ClinVar rows of one variant on one page today. Filed under Rule 4 because it is inside the fix round's code; it is a narrowing against round 1, not a regression against develop.
- NOT FIXED

### V-133-04: The cell-limit test does not pin the limit itself
- Severity: minor
- What: `test_a_merged_name_a_cell_cannot_hold_keeps_two_rows` (`tests/system_03_search_agent/core/test_write_answer_structure.py:2135`) uses two names of 315 and 314 characters, a merged name of 632. A guard set anywhere from 500 to 631 passes it, and every value from 501 up to that guard would still crash the answer.
- Reproduction: my own boundary probe `ver133/probe/test_ver_edge.py` through `write_node` with the live citation path, every token validated: merged length 499 and 500 give one row of 499 and 500 characters with both citations; 501 gives two rows (250 and 248 characters). So the code is right at the boundary today; only the test is loose.
- Why it matters: a later edit to `merged_name_limit` (`graph.py:13474`) could reopen J-133-03 for names between 501 and 631 characters with the suite green.
- NOT FIXED

## Checks with evidence

| Check | Result | Evidence |
|---|---|---|
| Card's own case, BRCA1, graph Gene plus live gene report row, through `write_node` with `layer2_raw_outputs` | One row, both citations, one page, tokens validate | Researcher `['BRCA1 DNA repair associated (BRCA1)', 'NCBIGene:672'] ['cq-structure-1', 'ne-gene-2']`; Plain `['BRCA1 DNA repair associated (BRCA1)']`, same markers; citations `('ne-gene-2', 'gene', '672', '.../gene/672/')`; PAGES 1; count line "Found 1 gene record" |
| Query 24 shape, MLH1 | One row, both citations | Researcher `['mutL homolog 1 (MLH1)', 'NCBIGene:4292'] ['cq-structure-1', 'ne-gene-2']`; Plain the same name. Also with an ESummary-shaped live row (`name`, `organism`): one row |
| J-133-01 closed | Both shapes back to develop's two rows | Two live genes on a shared taxid: round 1 `['Trp53 (Trp53bp1)', 'NCBITaxon:10090']`, fix round two rows. Two `nuccore` rows on a shared citation id: round 1 one row, fix round two rows. A live gene with a different id on the BRCA1 page, and a graph CURIE against a different live id: two rows on all three trees |
| J-133-02 closed | Edges merge only with both ends equal | Unflagged edges with no ends: round 1 one row, fix round two. Same CURIE, ends (1,2) and (1,3): round 1 `['Breast cancer (Ovarian cancer)']`, fix round two rows. Same edge id and same ends: one row. Upper-case edge label with no ends: two rows |
| J-133-03 closed | No crash, rows stay apart | Long-name probe through `write_node`: round 1 export raises `ValidationError for TokenPayload` at `graph.py:10495`; fix round two rows of 315 and 314 characters, tokens validate. Boundary 499, 500 merge; 501 splits (V-133-04) |
| J-133-04 closed | Both limits now turn a test red | Cap removed: 2 red `test_one_row_shows_at_most_four_names`. Cell limit removed: 2 red, see Break it |
| A-133-01 closed as briefed | No nested brackets | Plain `['tumor protein p53 (Homo sapiens) (TP53)']` in both orders; residual in V-133-02 |
| A-133-02 open | Better than develop | `test_three_way` on the exports: develop Plain 3 rows (`BRCA1 DNA repair associated`, `BRCA1`, `BRCA1`), fix round 2 (`BRCA1 DNA repair associated (BRCA1)`, `BRCA1` for `@GENE_BRCA1`), Sources 1 page on both |
| A-133-03 open | Same as develop | `adv/p_rs.py`: dbSNP row and LitVar2 row on `.../snp/rs80357906`, two rows on develop and on the fix round, identical cells |
| J-133-05 open | Same as develop, read only | `after.md`: query 116's "Found 40" over 41 rows is reported on develop and on the fix; not rerun live by me |
| New rule never merges what develop kept apart wrongly | Held on every shape | 22 shapes, two depths, three trees (`ver133/out_{dev,r1,head}.json`): every fix-round merge joins one record on its own identifier and one kind; every fix-round two-row result equals develop's |
| Would-be merge with today's develop (dfd5e4ff, card 134) | Green, same behaviour | `git merge-tree --write-tree origin/develop HEAD` clean; that tree's suites `1473 passed, 10 skipped, 1 xfailed`; shape outputs identical to HEAD's |
| Suites on the worktree | Green | structure, quality, `synthesis/`: `1423 passed, 10 skipped, 1 xfailed in 9.60s`; `test_write_answers_sooner.py`: `50 passed in 5.51s` |
| Gate 2 | Pass | `venv/bin/isort --check-only --diff src tests services tracker alembic .claude .github`: "Skipped 2 files", exit 0 |
| Gate 3 | Pass | `venv/bin/ruff check .`: "All checks passed!", exit 0 |
| CI on 5a23706c | Green | `gh pr checks 300`: Accessibility, Frontend gates, Integration suite, Python gates all pass; MERGEABLE |
| Speed | No new call | Fix-round added lines contain no `await`, `async`, `httpx` or model call |

## Break it

In the worktree, a backup copy taken first: the line `return text if len(text) <= merged_name_limit else None` (`graph.py:13490`) made `return text`, one changed line. `test_write_answer_structure.py`: `2 failed, 76 passed`, both `test_a_merged_name_a_cell_cannot_hold_keeps_two_rows[researcher]` and `[plain_language]`. Restored from the backup: `git diff HEAD` empty, `git status --short` shows only `?? frontend/node_modules`. No `git stash`. The other seven new guards were mutated in scratch copies only; results in V-133-01.

## Verdict

PASS: nothing worse than develop. Every fix-round result is either develop's own output or one record joined on its own identifier with every name and every citation kept. The four new findings are minor: two test gaps (V-133-01, V-133-04), one cosmetic label (V-133-02) and one narrowing against round 1 that equals develop (V-133-03, filed under Rule 4 because it sits in the fix round's code).

Verified by my own probes: every row of the table above except J-133-05; the break-it run; the seven scratch mutations; the would-be merge with today's develop; CI status read from GitHub. Read only, not run: J-133-05's live query 116 count, and the live runs and timings in `after.md`. Reachability of V-133-03 was argued from the code, not run live. No model calls and no NCBI calls were made.

Probe files (session scratchpad `ver133/`, not committed): `probe/shapes.py`, `probe/test_ver_e2e.py`, `probe/test_ver_edge.py`, `probe/test_ver_count.py`, `mut.py`, the `m_*` mutant copies and the `dev`, `r1`, `head` and `merged` exports.
