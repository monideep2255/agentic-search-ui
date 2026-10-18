# Verifier report: cards 103 and 104 fix round

Fresh verifier of branch `fix/card103-104-answer-tables` at 65e8cf18 (pull request #205) against `origin/develop`. Findings are appended as they are established.

## Table of contents

- [Findings](#findings)
- [Method](#method)
- [Fix claims re-derived](#fix-claims-re-derived)
- [Numbers against develop](#numbers-against-develop)
- [Command line](#command-line)
- [Tests run](#tests-run)
- [Verified by probe versus only read](#verified-by-probe-versus-only-read)
- [Verdict](#verdict)

## Findings

### VF-103-01: one variant shown twice, one row saying "None named" and the other naming a disease

- Severity: minor (reachability on live data not shown, as for A-103-02)
- Regression: yes, against develop; inside this fix round's A-103-02 fix
- What: when one ClinVar page reaches the table twice, once folding only "not provided" and once folding a named condition, the fix round keeps both rows (`merged_cells` in `core/graph.py`, the merge refuses two different non-empty cells). The first row now reads "None named: the ClinVar record says not provided" while the row under it, for the same record and the same page, names "Maturity-onset diabetes of the young". The fix round's own test `test_a_merged_disease_cell_never_contradicts_its_chips` pins exactly this pair. Develop shows the first row blank, which asserts nothing.
- Reproduction: verifier probe `own_variant`, real `write_node`, Researcher. `ClinVar:10` cited at 4 (folds `MedGen:C3661900`, "not provided") and at 8 (same page without the trailing slash, folds `MedGen:C0342276`). Branch rows: `['variant ClinVar:10', 'ClinVar:10', 'None named: the ClinVar record says not provided'] [4]` and `['variant ClinVar:10', 'ClinVar:10', 'Maturity-onset diabetes of the young'] [8, 6]`. Develop rows: `[..., ''] [4]` and `[..., 'Maturity-onset diabetes of the young'] [8, 6]`.
- Why it matters: "None named" is a statement about the ClinVar record, and the same table contradicts it one row later. A confident wrong statement is worse than a blank. The contradiction moved from cell-versus-chip (A-103-02) to row-versus-row; it did not go away.

### VF-103-02: the two depths now show different row counts for one answer

- Severity: minor
- Regression: yes, against develop (develop shows the same rows at both depths in every probe); inside this fix round
- What: the Plain language list merges on the name cell alone (`merge_into(listed_records, record_key, sentence, [label])` in the Plain path), while the Researcher table also compares the identifier, disease, status and year cells. Where the Researcher cells differ, Plain shows one item and Researcher two rows for the same record.
- Reproduction: verifier probe `own_variant`. Researcher: 7 rows (two `ClinVar:10` rows, markers `[4]` and `[8, 6]`). Plain language: 6 items (one `variant ClinVar:10` item, markers `[4, 8]`). Develop: 10 and 10.
- Why it matters: the item 12.9 firewall rule says both depths list the same cited records. A reader who switches depth sees a different count of records for the same question. Unsure whether the owner treats this as a defect; filed so it is decided, not discovered.

### VF-103-03: a second sentence for the same citation is now appended to the row's text, so the command line prints it twice

- Severity: minor
- Regression: yes, against develop; inside this fix round's A-103-03 fix (`merge_into` appends every merged sentence to `first.token.text`)
- What: `merge_into` appends the later sentence to the row's text even when that sentence brings no new citation number. Develop dropped an exact repeat (key `(source_url, cells)`, `continue`). The command line, the MCP answer and the GraphQL answer all join `token.text` (`adapters/cli/render.py` writes `payload.text`; `adapters/mcp/server.py` and `adapters/graphql/fold.py` append it), so they now print a repeat develop removed. The web screen and the saved answer read `cells` and `marker_ids` and are unaffected.
- Reproduction: verifier probe `dup.py`, the real `_answer_tokens`, one gene record cited once (`cq-1`, display 1) with two sentences `"BRCA1 [1]."` and `"BRCA1 [1]."`. Branch, both depths: one row, `marker_ids ['cq-1']`, text `'BRCA1 [1]. BRCA1 [1]. '`. Develop: one row, text `'BRCA1 [1]. '`. With `"Gene name: BRCA1 [1]."` and `"Gene symbol: BRCA1 [1]."` the branch text carries both sentences, develop only the first.
- Why it matters: a command-line reader sees the same sentence twice under one row. Reach: through the real `write_node` the code-built listing gives one sentence per citation, so I did not reproduce it end to end; it needs a path that feeds several grounded sentences of one citation to the listing (the structured fallback or a tail listing). A one-line fix would append only when the sentence adds a marker the row lacks.

### VF-103-04: four guards in the new merge code survive a one-line mutation

- Severity: minor (test gap; the code is right today)
- Regression: no behaviour regression
- What: 24 one-line mutations of the fix round's code were run against `test_write_answer_structure.py` and `synthesis/test_answer_layout.py` on a scratch copy (one test that needs `testing/Test_queries_and_workflows.md` deselected). 19 went red. Five stayed green, 126 passed:
  - the disease-cell recompute check in `merge_into` (`if mapping_cell(entity_type, fields, url) != merged[at]: continue`) removed. It is what refuses a merge when two different MedGen ids share one title, or when the joined titles would differ from the cell either row showed. No test reaches a case where it decides.
  - the 1000-character text check removed (`len(text) > 1000`). `TokenPayload` has no `validate_assignment`, so without it an over-long text would leave the node silently and fail only where a consumer re-validates (`adapters/mcp/server.py` builds `TokenPayload(**event.payload)`).
  - the identifier dropped from `record_merge_key` (`return (page, "")`). The Researcher table still compares the identifier cell, but the Plain language list compares only the name, so two records on one page with one name and two identifiers would merge in Plain language with no test going red. `test_same_page_different_identifier_stays_two_rows` runs Researcher only.
  - the `SequenceVariant` type check in `empty_cell_reason` removed (the URL check alone still holds the gene case in the tests).
  - the `shown[0] != later[0]` name check removed. This one is an equivalent mutant: the cell loop already refuses two different non-empty names. Listed for completeness, not as a gap.
- Reproduction: verifier `mutate.py`; survivors printed `GREEN merge: mapping recompute check removed: ['126 passed, 1 deselected']`, `GREEN merge: 1000 text check removed`, `GREEN merge: key drops identifier`, `GREEN wording: type check removed`, `GREEN merge: name not compared`. The scratch copy was compared with its original after the run: no difference.
- Why it matters: the identifier in the key is the guard against two different records sharing one Plain language item, the exact card 104 failure. The next edit can drop it and stay green.

## Method

- Compared against `origin/develop` at 7309b55f (a detached worktree, removed afterwards), and against a scratch tree of the merge develop plus this branch would make (`git merge-tree`, clean, no conflicts). Develop's commits since the merge base do not touch `_answer_tokens`; the branch and the merge tree give identical probe output on every case.
- Probes call the real `core.graph.write_node`, with only the Synth model call faked to restate each finding line and the MedGen title lookup faked from a fixed table, and the real `_answer_tokens` for the repeated-sentence case. Each case ran at Researcher and Plain language depth on the branch and on develop, and every token, cell, marker, citation, trust signal, note, opening line and trust line was compared field by field.
- Cases: the diagnosis's HNF1A placeholder table, case A (one gene page with and without a trailing slash) and case B (one page, two names); my own gene answer (BRCA1, BRCA2, TP53 with folds, repeats, placeholder-only and failed lookup), variant answer (repeats with the same fold, a differing fold, "see cases", an empty fold) and isolate answer (a repeat by slash, one strain name on two BioSamples, a repeat with AMR genes only on the later row); plus the judge's 22-disease cap case, the paper year case in both orders, edge rows, identifier-less records on one page, mixed placeholder and failed-lookup rows and a variant row on a dbSNP page.
- Mutations: 24 one-line mutations on a scratch copy, as in VF-103-04.

## Fix claims re-derived

| Finding | Status | Evidence |
|---|---|---|
| J-103-01 | Fixed | `answer_layout.py` `empty_cell_reason` returns `EMPTY_CELL_LOOKUP_FAILED` before any placeholder wording. Probe: TP53 folding a failed lookup and "not provided" reads "Name could not be looked up"; `ClinVar:20` the same. Mutation (lookup not returned first; "None named" prefixed) goes red. |
| J-103-02, A-103-01 | Fixed | The ClinVar wording needs `SequenceVariant` and a ClinVar variation page. Probe: BRCA2 with only "not provided" stays blank, as on develop; `ClinVar:23` on a dbSNP page stays blank. Mutations removing the scope or URL check go red; the type check alone survives (VF-103-04). |
| J-103-09, A-103-05 | Fixed | Probe: `ClinVar:9` with "See cases" reads "None named: the ClinVar record gives only a placeholder"; "see cases" beside "not provided" reads the same. Mutations go red. |
| A-103-04, J-103-07 | Fixed | Notes line ends "are not listed as diseases"; the count is unchanged in every case. Mutation goes red. |
| J-103-03 | Fixed | Cap case: two `ClinVar:9` rows, markers `[1..20]` and `[24, 2..20]`, identical to develop; citation 24 reached. Mutation removing the 20 check goes red. |
| J-103-04 | Fixed | `ClinVar:7` merged row markers `[1, 6, 7]`. Mutation goes red. |
| A-103-02 | Fixed as cell versus chip | Two rows, each cell beside its own chips. The contradiction moves between rows: VF-103-01. |
| A-103-06 | Fixed | Paper case: one row `['A paper', 'PMID:123', '2019']` markers `[1, 2]` in both orders; develop showed a blank row and a 2019 row. Different years keep two rows. Mutations go red. |
| J-103-05 | Accepted, not worse | Case B stays two rows at both depths, as on develop. Edge rows with their own names stay one row each. |
| J-103-06 | Fixed, with residual gaps | M6, M10, M14 and M16 are each now red under mutation. Four other guards survive: VF-103-04. |
| A-103-09, A-103-10 | Fixed | Identifier-less records on one page with different names stay two rows at both depths; the disease-chip merge mutation goes red. |
| A-103-03 | Fixed | The real command-line `Renderer` prints every cited number on case A, the gene case and the variant case, on branch and develop alike. The text change behind it causes VF-103-03. |

## Numbers against develop

On all 26 case and depth runs, the opening "Found N" line, the trust line, the trust signals, the citation list and the distinct Sources page count are identical to develop. The meta line reads the same citations, so it cannot differ. No marker points at a citation that does not exist, no `[n]` in any text is uncited, and no citation is left unreached on the branch in any run.

The table's "Showing" bar counts the rows a table receives (`AnswerScreen.tsx`, `totalRows`), so it falls exactly where rows merge, by the card's design: case A goes from 2 rows to 1, matching its opening "Found 1 gene record". It equals develop wherever nothing merges.

## Command line

Every citation number of a merged row is printed: case A prints "Gene record NCBIGene:672 [1]. Gene record NCBIGene:672 [2].", and the gene and variant cases print every cited number, checked through the real `Renderer`. The command line prints no cells, so card 103's wording never reaches it.

## Tests run

- `tests/system_03_search_agent/core/test_write_answer_structure.py` with `tests/system_03_search_agent/synthesis/test_answer_layout.py`, in the branch worktree: 127 passed.
- `tests/system_03_search_agent/synthesis`, branch worktree: 664 passed, 10 skipped, 1 xfailed.
- `tests/system_03_search_agent/adapters/cli/test_render.py`, branch worktree: 60 passed.
- Merge tree (develop plus branch): the touched core file, `synthesis` and `cli/test_render.py`: 849 passed, 10 skipped, 1 xfailed.
- The branch's tests are counted as a gate here, not as verification.

## Verified by probe versus only read

- Verified with my own probes: every row of "Fix claims re-derived"; every number in "Numbers against develop"; the command-line output; VF-103-01 to VF-103-04; that the merge tree behaves as the branch.
- Only read: that the web draws chips from `marker_ids` and table cells from `cells` (`useRunView.ts`, `AnswerScreen.tsx`); that the saved answer reads `cells` and `marker_ids`, not `text` (`feedback/capture.py`); that MCP and GraphQL join `token.text`; that `TokenPayload` does not validate on assignment.
- Not probed: the live graph, the live model, deployed develop, and whether one ClinVar page ever reaches an answer under two finding identities with different folds (the precondition of VF-103-01 and VF-103-02).

All four findings sit inside this fix round's own changes. That is the review loop's stop condition: the decision goes to the product owner rather than into another round.

## Verdict

MERGE WITH NAMED ITEMS. On every end-to-end case, the branch is equal to or better than develop: no row, citation or Notes fact is lost, every stated number is unchanged, and both cards do what they promise. Named items for the owner: VF-103-01 (one record shown as "None named" in one row and with a disease in the next) and VF-103-03 (a repeated sentence printed twice on the command line), both inside this round's fixes and both on inputs not reproduced end to end. VF-103-02 shares VF-103-01's trigger. VF-103-04 is a test gap.

Worse than develop: yes (narrowly: VF-103-01 is wording that says more than the record on a constructed input, and VF-103-02 and VF-103-03 change develop's output for the worse on the same kind of input; none appears on the diagnosis's cases or my own)
