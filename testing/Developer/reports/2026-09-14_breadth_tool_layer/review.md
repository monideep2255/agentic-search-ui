# Review of the 11.21 tool-layer change, 2026-09-14

This reviews the uncommitted tool-layer half of UI fix Set 11.21, "search broad, cite exact". The change sits in the builder's worktree, `.claude/worktrees/agent-aa07f985dc6ebdaa8`, based on develop `e5947e0`. A fresh-context reviewer with no write access checked it. Its report could not be written from inside that role, so the main agent recorded it here when it arrived.

## Table of contents

- [Verdict](#verdict)
- [Gates](#gates)
- [Findings](#findings)
- [Verified versus read](#verified-versus-read)
- [Fix round 1, by the builder](#fix-round-1-by-the-builder)
- [Round 2 re-review](#round-2-re-review)
- [Decision after round 2](#decision-after-round-2)
- [F-09 follow-up, by the main agent](#f-09-follow-up-by-the-main-agent)

## Verdict

Do not land as is. Land after F-01 and F-02 are fixed, and after F-03's `link()` behaviour is restricted to verified database pairs. The worst defect is new code, not a regression inside an earlier fix.

## Gates

Run by the reviewer inside the worktree:

- pytest on `tools/`, `core/test_breadth_plan.py` and `test_debugging_guide_coverage.py`: 1578 passed, 98 skipped, 0 failed.
- `ruff check src tests`: clean.
- `isort --check-only src tests`: clean.

All three are green while F-01 is live, so the suite does not cover the shape that breaks.

## Findings

| ID | Severity | Where | Defect | Reproduction |
|---|---|---|---|---|
| F-01 | Critical | `tools/cypher_provenance.py`, `_go_attribution_curie` and its call in `to_output_rows` | A GO term is cited to any Gene vertex in the same raw row, whether or not that gene carries the annotation. No caller passes `go_attribution_curie`, so this rule governs every query, including model-generated Cypher | BRCA1 to TP53 to GO row: the GO term is cited to `gene/672` (BRCA1). `RETURN go, tp53, brca1`: cited to 7157, so the choice follows column order |
| F-02 | Major | `cypher_provenance.py`, `_shape_entity` GO branch | Any `GO:` CURIE becomes citeable, with no `GO:\d{7}` shape check and no GO-type label check | Id `GO:anything <script>` beside BRCA1 is cited to `gene/672`; a vertex labelled `Gene` with id `GO:0006281` is cited too |
| F-03 | Major | `tools/ncbi_eutils_actions.py`, `link()` | Preferring the `<dbfrom>_<db>` linkname drops other linksets. The code comment's claim that no caller loses ids is false | Live: `gene` to `pubmed` for 2645 goes from 477 ids to 357, losing all 120 from `gene_pubmed_citedinomim`. `pubmed` to `pubmed` now returns similar articles and hides `citedin` |
| F-04 | Major, not yet wired | `core/breadth_plan.py`, `verify_verbatim_spans` | Any exact substring passes: no minimum length, no word boundary, no sentence boundary | From "GCK is not associated with neonatal diabetes. Prior claims that GCK causes MODY were refuted.", the spans "associated with neonatal diabetes" and "GCK causes MODY" are accepted |
| F-05 | Minor | `breadth_plan.py`, `verify_verbatim_spans` | A bare string is iterated as characters | `verify_verbatim_spans(ab, "BRCA1")` returns five one-character spans |
| F-06 | Minor | `breadth_plan.py`, `select_ids` | `"0"` is accepted as an id | `plan_literature_follow_up(["0"])` plans a fetch for PMID 0 |
| F-07 | Minor | `breadth_plan.py`, `filter_omim_titles` | A one-letter symbol matches unrelated titles | `T` keeps "T-CELL RECEPTOR ALPHA LOCUS; TRA" |
| F-08 | Minor, unsure | `cypher_provenance.py`, `_dedupe_rows_by_record_identity` | One GO vertex in three columns yields three rows; downstream CURIE dedupe is expected to collapse them but was not executed | Three identical GO rows from one raw row |
| F-09 | Unsure | `tools/ncbi_transport.py` | The limiter is per process. At 10 per second, several processes or apps sharing one key can exceed NCBI's 10 per second, and a keyless deployment runs at 10 against a 3 per second limit | Not executed; depends on worker count and key sharing |

## Verified versus read

Executed by the reviewer:

- F-01 to F-07, plus the live ELink linksets behind F-03.
- Planner determinism, under shuffled and duplicated ids.
- Rejection of symbol injection, and stripping of quotes and field tags from disease titles.
- HP and MONDO rows stay uncited.
- The Datasets summary cap.

Read only: downstream dedupe in `cypher_query`, the PMC URL template, the limiter's wait arithmetic, and the deployment topology behind F-09.

## Fix round 1, by the builder

Recorded by the main agent from the builder's report. All eight fixes are pending round 2 re-review.

- Red first: 27 new test arms failed against the unfixed code, exactly the new arms (F-01 5, F-02 11, F-08 1, F-03 2, F-04 2, F-05 1, F-06 1, F-07 4).
- Green after the fixes: 1610 passed, 98 skipped, 0 failed; `ruff` and `isort` clean.

| ID | Fix |
|---|---|
| F-01 | The shared-row gene rule is removed. A GO row is citeable only when the caller passes an explicit `go_attribution_curie`; otherwise it stays uncited and is dropped |
| F-02 | The GO id must match `^GO:\d{7}$` (ASCII), and the label must be BiologicalProcess, MolecularActivity or CellularComponent |
| F-03 | The direct linkname is preferred only for (pubmed, pmc); every other pair keeps all matching linksets |
| F-04 | Only runs of 1 to 3 consecutive whole sentences from one deterministic splitter are accepted; substring matching is gone |
| F-05 | A str or bytes `spans` argument raises TypeError |
| F-06 | Zero ids are rejected |
| F-07 | The OMIM symbol must equal a semicolon-separated symbol field after the title's first segment |
| F-08 | Executed: one GO vertex in three columns did give three rows. Attributed GO rows are now deduped by GO CURIE, and the test runs through `cypher_query`'s own dedupe |

The builder corrected one fixture of its own: `("T", "T; TBXT")` must not match, because an OMIM title's first segment is the name, not a symbol field.

## Round 2 re-review

Verdict: land after two named fixes, N-01 and N-02. The review loop's stop condition fired, because N-01 is a defect inside the F-04 fix, so the decision went to the product owner.

Gates rerun by the reviewer: 1610 passed, 98 skipped, 0 failed; `ruff` and `isort` clean. No test was loosened.

Round 1 status:

- Closed: F-01 (all 11 round 1 rows now uncited, and nothing in `src/` passes `go_attribution_curie`), F-03, F-05, F-06, F-07 and F-08.
- Closed with one gap: F-02, which has N-02.
- Partly closed: F-04, whose fix introduces N-01.

| ID | Severity | Where | Defect | Reproduction |
|---|---|---|---|---|
| N-01 | Major, inside the F-04 fix | `core/breadth_plan.py`, `_SENTENCE_END` | Every `.` followed by whitespace ends a sentence, including inside "et al.", "Fig.", "e.g.", "vs.", "approx." and "p.", so a meaning-reversing fragment passes as a whole sentence. The tests have no abbreviation case | "The variant was pathogenic according to Smith et al." is accepted from a sentence that continues "but not in our cohort"; "90 percent of MODY families." is accepted from "Mutations were not found in approx. 90 percent of MODY families." |
| N-02 | Minor, inside the F-02 fix | `tools/cypher_provenance.py`, `_GO_CURIE_SHAPE` | `$` matches before a trailing newline | `'GO:0006281\n'` is cited to `gene/672`; use `\Z` or `fullmatch` |
| N-03 | Unsure | whole-sentence design | A whole sentence can be quoted while the next sentence refutes it; a sentence rule cannot see that | "Earlier reports claimed GCK causes MODY." is accepted before "We refute this." |
| N-04 | Unsure | `cypher_query._dedupe_by_cited_record` | CURIE-only dedupe could drop a second gene's citation for the same GO term if a multi-gene GO template is ever built | Two calls for `GO:0006281` cite `gene/672` and `gene/7157` |
| N-05 | Minor, unsure | `test_pubmed_to_pmc_keeps_only_the_direct_linkname` | The fixture labelled live-verified did not reproduce live; PMID 31452104 today returns only `pubmed_pmc_refs` | Live ELink call |
| N-06 | Minor, older code | explicit gene CURIE shape check | `NCBIGene:0`, `NCBIGene:00672` and a 20-digit id are accepted | Direct call |

## Decision after round 2

Product owner, 2026-09-14: land the safe parts, and hold the quote check back.

- The builder fixes N-02, removes `verify_verbatim_spans` and its sentence splitter, and corrects N-05's fixture comment. The landing lands after that.
- Abstract sentences do not become findings until a new design exists, which closes N-01 and N-03 by removing the code they live in.
- N-04 stays open. Owner: whoever builds a multi-gene GO template, since no caller runs one today.
- N-06 stays open as minor. Owner: the `source_url_for_curie` shape check, next time that code is touched.

## F-09 follow-up, by the main agent

- `railway.json`'s start command runs `uvicorn` with no `--workers` flag, so each app is one process with one limiter.
- At 10 per second, NCBI's per-key limit can be exceeded only if develop and production share one key and both run at full rate at once, 20 at most.
- Production gets the new default only with a release, so nothing is exposed today.
- Before that release, confirm whether the two apps use separate keys. If they share one, set `NCBI_EUTILS_RPS=5` on each app. This is a product-owner decision under the tool-call-budgets rule, not a code change.
