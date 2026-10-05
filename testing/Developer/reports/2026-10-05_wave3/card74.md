# Card 74: a paper's linked data records

## The change

- Before: "sequence data for PMID 11237011" (G-006) reached a model-written graph search that found nothing. The graph has no edge from a paper to sequence data, BioProjects, GEO series or assemblies (card 15's finding).
- After: Plan asks one classifier decision, `plan.paper_links`, only when the question resolved exactly one PubMed paper and no gene. Its pick (sequences, projects, samples, reads, expression, assemblies, all_data, or not_linked_data) maps in `core/paper_links.py` to explicit ELink target databases. Plan then plans one ELink from `pubmed` per target through the existing `link` action, and one ESummary follow-up per target, so each linked record is cited to its own NCBI page. No graph call is planned for that question. At most 12 calls (all_data), under the ceiling of 20.
- No usable pick or "not_linked_data" keeps the plan the question had before.
- Write: every link empty gives "NCBI lists no linked <kind> for PMID n." (a refusal-path message, outranked by a failed search). One kind empty beside a kind that answered gives a note. More records than the 10 cited gives "NCBI lists N ... linked to PMID n; this answer shows 10."
- No new tool. Additive: `nuccore` joins `SummaryDb`, the record URL table and the summary field table (live-verified, see below), because sequence records had no citable page before.

## Tests (`tests/system_03_search_agent/core/test_paper_links_wiring.py`, 10)

- Plans ELink with explicit targets, three follow-ups, no graph call: failed on the old code.
- all_data plans 12 calls: failed on the old code.
- Links feed summaries, empty kind costs no summary, rows cite the linked records' own pages: failed on the old code.
- Every link empty gives the plain sentence and a refusal outcome: failed on the old code.
- Failed link search makes no "none listed" claim; count note: failed on the old code.
- Guards that pass on old and new code: classifier says not_linked_data or gives no pick (graph call first), a gene question (classifier never asked), two papers.
- Old-code proof: `git archive origin/develop src` into a scratch directory plus the new pure module, tests run against it: 6 failed, 4 passed. No stash.
- Changed: `test_breadth_wiring.py` gains a `nuccore_summary` realistic record (its test requires one per breadth purpose). Debugging guide row and manifest added for the new module.

## Gates

- Gate 2 and gate 3 green.
- Gate 4 first run: 8 failed, 6541 passed. Two were mine (debugging guide row missing), fixed and re-run green. Six are connection refused to local PostgreSQL (port 5432), the same six card 15 reported, none touch this change. Gate 4 was not re-run in full after the guide fix.

## Live run (read-only, through the repository's own `link` and `summary`, 0.5 s apart)

PMID 11237011, ELink from pubmed:

| Target | Result |
|---|---|
| nuccore | 1587 linked records (union of pubmed_nuccore and pubmed_nuccore_refseq), the tool returns the first 100; ESummary of 10 returns titles and accession versions with `/nuccore/<id>` pages |
| bioproject | 2: PRJNA31257 (Human Genome Project, GRC) and PRJNA168 (RefSeq annotation of the human reference assembly) |
| biosample | none |
| sra | 1 (uid 8317276, a trace experiment from center WUGSC, 1 run) |
| gds | none |
| assembly | 29, led by GCF_000001405.40 (GRCh38.p14) |

An earlier probe the same day showed 1533 nuccore links (the count moves as NCBI updates). So "sequence data" for this paper is large and mostly RefSeq and GenBank human genome records.

## Not covered

- No end-to-end answer run through the live model: how Synth words the rows is the lead's test-query check on develop.
- The classifier's real picks were stubbed; its criteria are untested against the live guard model.
- The `sequences` pick means GenBank and RefSeq records, SRA runs and assemblies together. Protein records (pubmed_protein, 5 for this paper) are not linked.
- On a question that wants the paper's linked data plus something else (its genes, say), the graph is not searched at all.
- Branch is cut from develop without card 15, so the article-anchor template is not in this change. The two touch Plan differently and should merge without conflict, but that was not tried.
