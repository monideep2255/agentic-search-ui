# Judge, cards 133 and 137 part 1, one round

Branch `fix/card133-one-record-one-row`, commit fa3433c3, worktree `s3-worktrees/card133`. Findings are appended as they are established.

## Findings

### J-133-01: The "own identifier" test only knows the two graph borrow flags, so a Layer 2 row whose identifier is borrowed still merges on a different name
- Severity: minor (unsure on reachability; no live path found that puts two such rows on one page today)
- What: `own_record_kind` (`src/system_03_search_agent/core/graph.py:13385-13396`) treats every non-blank identifier as the record's own unless the row carries `_cited_via_endpoint_curie` or `_cited_via_gene_curie`. But `record_identifier` (`src/system_03_search_agent/synthesis/answer_layout.py:558-600`) can return a value that is not the record's own: `taxid` from `_IDENTIFIER_FIELDS` (the organism's id, `NCBITaxon:N`, on any non-taxon row that carries a `taxid` field and none of the earlier fields), and the citation's `source_id` fallback. Neither is checked. Grep confirms the only `_cited_via_*` flags in `src` are those two (`cypher_provenance.py:221`, `:747`, `:774`), so the helper is complete for flags but not for the other borrow routes the identifier reader has.
- Reproduction: scratchpad probe `probe_cases.py` (helpers in `probe_lib.py`, calling `graph._answer_tokens` directly). Two live `gene` rows on one page `.../gene/7157/`, fields `{"symbol": "Trp53", "taxid": 10090}` and `{"symbol": "Trp53bp1", "taxid": 10090}`, citation `source_id` 22059 and 27223. Output, both depths: one row `['Trp53 (Trp53bp1)', 'NCBITaxon:10090'] ['o1', 'o2']`. Two different genes, one row, identifier cell the mouse taxon. The same with two `nuccore` rows sharing a citation `source_id`: `['isoform X1 mRNA (isoform X2 mRNA)', 'nuccore 568815597'] ['n1', 'n2']`. On develop the name check kept both apart.
- Why it matters: the decision says "a borrowed ... identifier never merges". The code enforces that for two named graph borrow routes only. Reachability today needs two such rows on one page key, which no breadth purpose I traced produces (the gene report uses `tax_id`, not `taxid`, and builds the page from `gene_id`), so this is a latent hole, not an observed wrong answer. A wrong merge hides a record: worse than develop if it ever fires.
- NOT FIXED

### J-133-02: An edge row that carries its own `id` is not treated as borrowed, so two condition edges on one ClinVar page merge
- Severity: unsure (the server reference says live edges carry no CURIE, so likely unreachable)
- What: `own_record_kind` excludes `derived` and the two flags, never edges as such. `cypher_provenance._shape_entity` sets `_cited_via_endpoint_curie` only when an edge has no `id` property (`cypher_provenance.py:743-747`).
- Reproduction: `probe_cases.py`, two `has_phenotype` rows, curie `ClinVar:17661`, page `.../clinvar/variation/17661/`, names "Breast-ovarian cancer, familial 1" and "Hereditary cancer-predisposing syndrome", no flag. Output, both depths: one row `['Breast-ovarian cancer, familial 1 (Hereditary cancer-predisposing syndrome)', 'ClinVar:17661'] ['e1', 'e2']`. With the flag set (the shape live edges get) they stay two rows, as expected.
- Why it matters: two different conditions would read as two names of one record. Only reachable if a future graph load gives edges an `id`; filed so the assumption is written down.
- NOT FIXED

### J-133-03: The merged name cell is capped at 1000 characters but a cell may hold 500, so a long two-name merge crashes the answer on the web path
- Severity: major (inside this phase's fix; the trigger needs two names of one record over about 497 characters together, which I did not find in live data, but when it fires the answer is lost, worse than develop's two rows)
- What: `merge_into` guards the merged name with `len(merged[0]) > 1000` (`src/system_03_search_agent/core/graph.py:13480`). `TokenPayload.cells` items are `Field(max_length=500)` (`src/system_03_search_agent/contracts/events.py:428`). The token is mutated in place with no validation, then `_with_placement` rebuilds it through the model (`graph.py:10470`) when the request reads placement, which the web app's request does, and that raises. The CLI (`adapters/cli/render.py:877`, `:1368`), the MCP server (`adapters/mcp/server.py:1173`) and the saved-answer capture (`feedback/capture.py:184`) also re-validate every token. Each label alone is capped at 500 (`answer_layout.py:891`, `:973`), so two legal labels make an illegal cell.
- Reproduction: scratchpad `test_probe_e2e.py::test_long_names_end_to_end`, run with `pytest -p tests.conftest --rootdir <worktree> -c pyproject.toml`. Two graph Gene rows, pages `.../gene/672` and `.../gene/672/`, names "alpha gene name " plus 60 "word " and "beta gene name " plus 60 "term ". `write_node` raises: `pydantic_core._pydantic_core.ValidationError: 1 validation error for TokenPayload cells.0 String should have at most 500 characters [type=string_too_long ...]` at `graph.py:10470 in _with_placement`, both depths. Direct `_answer_tokens` probe (`probe_long.py`): merged cell length 609, `TokenPayload.model_validate` fails the same way.
- Why it matters: a reader asking about such a record gets an error in place of an answer. The guard exists, it is set to the text limit rather than the cell limit. A test of a long merge would have caught it; none exists.
- NOT FIXED

Develop comparison for J-133-01 to J-133-03, the same probes run against `git archive origin/develop`: every case is two rows, and the long-name case gives two cells of 316 and 290 characters that validate. Each of the three is therefore a regression against develop when it fires, all three inside this phase's fix.

### J-133-04: Two of the fix's new limits are pinned by no test: the four-name cap and the merged-name length guard
- Severity: minor
- What: `merged_cells` refuses a fifth name (`if len(names) >= 4: return None`, `graph.py:13423-13424`) and `merge_into` refuses a merged name over 1000 characters (`graph.py:13480`). Deleting either leaves every named suite green. The length guard is also set at the wrong limit (J-133-03), which a test would have shown.
- Reproduction: scratch copies of HEAD from `git archive HEAD src tests pyproject.toml frontend/e2e/fixtures` (worktree untouched). Each mutation removes exactly the two named lines (diff shows 2 changed lines). Suites: `test_write_answer_structure.py test_write_answer_quality.py synthesis/ test_write_answers_sooner.py`. Results: cap removed, `2 failed, 1459 passed, 10 skipped, 1 xfailed`; length guard removed, `2 failed, 1459 passed, 10 skipped, 1 xfailed`. The 2 failures are `test_card23_query_79_quotes_the_line_that_ships` and `test_card23_the_screen_finds_the_line_by_the_words_that_ship`, which fail identically on an unmutated copy because the copy lacks `testing/Test_queries_and_workflows.md` and `frontend/src/hooks/useRunView.ts` (environment, not the mutation).
- Why it matters: a later edit can remove or loosen either limit silently. The length guard is the line between a merged row and a crashed answer.
- NOT FIXED

## Break it

Scratch copies of HEAD in the session scratchpad, never the worktree. `git -C <worktree> diff HEAD` empty before and after; `git status --short` shows only `?? frontend/node_modules`.

| Mutation | Red tests (excluding the 2 environment card23 failures) |
|---|---|
| Drop the same-kind check (`row.same_record_kind != later_kind`) | `test_two_kinds_of_record_on_one_page_never_merge`: `AssertionError: [['BRCA1 (breast cancer 1, BRCA1 protein)']]` |
| Drop the borrowed check (`_cited_via_*` line made `if False:`) | 4: `test_rows_on_a_borrowed_identifier_never_merge`, all four parameters |
| Drop the blank-identifier return | 4: `test_two_records_with_no_identifier_merge_only_on_the_same_name` x2, `test_two_gene_rows_with_a_blank_identifier_never_merge_on_different_names` x2 |
| Drop `derived` from the excluded kinds | 1: `test_a_derived_row_and_its_twin_never_merge_on_different_names` |
| Drop the no-fields return | 1: `test_one_record_cited_by_two_claims_is_one_row`, by `AttributeError: 'NoneType' object has no attribute 'get'`, a crash rather than an assertion |
| Drop the four-name cap | none (J-133-04) |
| Drop the merged-name length guard | none (J-133-04) |

### J-133-05: Card 133 as filed is not fully closed: query 116's "Found 40" over 41 rows remains, and queries 25 and 29 were not rerun
- Severity: minor (scope, stated openly by the builder in `after.md`)
- What: the card lists four answers. `after.md` reruns query 24 and `What does BRCA1 do?`, and finds query 116's mismatch has a different cause (the Found line leaves out the live TP53 context record) that this change does not touch. Queries 25 (TP53 GEO datasets) and 29 (CFTR) were not run after the fix.
- Reproduction: read only, `testing/Developer/reports/2026-10-22_card133_137/after.md` (worktree), sections "Results" and "Query 116 is a different count": "Found 40 gene records for TP53, of 715 available ... over 41 gene rows, on develop and on the fix".
- Why it matters: if card 133 is moved to Retest as fixed, the owner will still see "Found 40" over 41 rows on query 116. The DECISIONS.md rule this round was judged against is met; the card's own symptom list is not.
- NOT FIXED

## Checks with evidence

| Check | Result | Evidence |
|---|---|---|
| Graph gene row plus live gene row, through `write_node` with the real Layer 2 citation path (`layer2_raw_outputs` supplied) | One row, both numbers, both open the gene page | Researcher `['BRCA1 DNA repair associated (BRCA1)', 'NCBIGene:672'] ['cq-structure-1', 'ne-gene-2']`; Plain `['BRCA1 DNA repair associated (BRCA1)']`, same markers. Citations `('cq-structure-1', 1, 'NCBIGene', 'NCBIGene:672', '.../gene/672')`, `('ne-gene-2', 2, 'gene', '672', '.../gene/672/')` |
| Count line, Based on line, Sources pages agree | Yes | "Found 1 gene record for BRCA1 ...", "Based on 1 source cited, from NCBI Gene", distinct pages 1, rows 1 |
| Saved answer (`feedback.capture.answer_markdown_from`) | Agrees | `\| BRCA1 DNA repair associated (BRCA1) [1][2] \| NCBIGene:672 \|`; Plain `- BRCA1 DNA repair associated (BRCA1)[1][2]` |
| Command line (`adapters/cli/render.Renderer`) | Agrees, prints both numbers | `Gene NCBIGene:672, name: BRCA1 DNA repair associated [1]. Gene symbol: BRCA1 [2].` |
| GraphQL | Read only: `adapters/graphql/fold.py` joins token text (`joined_text`), which carries both sentences and both markers. Not run | |
| Without `layer2_raw_outputs` the live citation is `source='ncbi_efetch', source_id='unknown'`, identifier blank, so two rows stay, as on develop | No worse than develop | first e2e probe, `ROWS [(['BRCA1 DNA repair associated', 'NCBIGene:672'], ...), (['BRCA1', ''], ...)]` |
| Different records on one page stay apart | Yes for every realistic shape probed | ClinVar page with two flagged condition edges: 2 rows; variant vertex plus edge: 2 rows; gene plus PubTator entity on the gene page: 2 rows (`@GENE_BRCA1`); three diseases sharing one page in one call (J4-03 shape): 3 rows; assembly plus sequence on one page: 2 rows; two isoforms with own accessions: 2 rows; two ortholog vertices with own CURIEs on one page: 2 rows; gene plus two GO terms cited via the gene: 3 rows. Exceptions only on constructed shapes: J-133-01, J-133-02 |
| `_cited_via_*` flags complete | Yes for flags: grep finds only `_cited_via_endpoint_curie` and `_cited_via_gene_curie` in `src` (5 and 3 hits). Other borrow routes: J-133-01 | |
| Speed: no new call | Confirmed by diff: added lines contain no `await`, `async`, `httpx`, `acompletion`, tool call. Adds one in-memory `_row_fields_for` scan per listed row | grep exit 1 |
| Suites | `test_write_answer_structure.py test_write_answer_quality.py synthesis/`: `1411 passed, 10 skipped, 1 xfailed in 10.48s`; `test_write_answers_sooner.py` (the other file naming card 104): `50 passed in 5.46s` | |
| Gate 2 and 3 | `isort --check-only --diff src tests services tracker alembic .claude .github`: exit 0, "Skipped 2 files"; `ruff check .`: "All checks passed!", exit 0 | |

## Verdict

FAIL, on one finding inside this phase's fix: J-133-03, a merged name over 500 characters raises `ValidationError` in `write_node` on the web path, where develop shows two rows. That is new code from this phase, which per the review loop's stop condition escalates rather than starting another round. J-133-01 and J-133-02 are latent wrong merges in the new rule, reachable only by shapes I could not find in today's data; also inside the fix.

The acceptance sentence itself is met on every realistic shape: same page and own identifier merge showing both names with every number; borrowed (flagged), blank, and different-kind rows stay apart. Nothing is worse than develop on any realistic input I probed.

Verified by my own probes: every row of the table above except GraphQL; all seven break-it mutations; the develop comparison. Read only, not run: GraphQL folding, the live runs and timings in `after.md`, the reachability argument behind J-133-01 and J-133-02 (traced through `_BREADTH_FIELDS_BY_PURPOSE`, the Datasets gene report fields and `cypher_provenance._shape_entity`), and the claim that live edges never carry an `id`.

Probe files (session scratchpad, not committed): `probe_lib.py`, `probe_cases.py`, `probe_long.py`, `test_probe_e2e.py`.
