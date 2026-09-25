# LitSense live probe, card 44 (item 13.1)

A bounded live probe run on 2026-09-25 against the real LitSense API, ten questions from the golden dataset. No product code touched. The probe script and its raw output sit beside this file (`probe.py`, `raw_results.json`). Written up by researcher I; saved by the lead, since the researcher's own write was blocked.

## Table of contents

- [Verdict](#verdict)
- [The endpoint](#the-endpoint)
- [Questions chosen](#questions-chosen)
- [Per-question results](#per-question-results)
- [Numbers](#numbers)
- [PMID restriction](#pmid-restriction)
- [Failure cases and misleading snippets](#failure-cases-and-misleading-snippets)
- [Recommendation](#recommendation)
- [The narrow version, smoke-tested the same night](#the-narrow-version-smoke-tested-the-same-night)

## Verdict

Do not build the decision as written.

- LitSense gives a useful, on-topic snippet for a general "what is the evidence for X" question about four or five times in ten.
- It cannot give a snippet for one named paper, because the API has no way to point it at a paper. It is free-text search over the whole corpus, not a lookup keyed by PMID or PMCID.
- For both questions anchored to one PMID (G-006, G-019), the paper asked about never appeared in the top ten.

The decision asks for a sentence "under each cited paper", which assumes LitSense can be told which paper to read. It cannot.

## The endpoint

Confirmed live, no key needed: `GET https://www.ncbi.nlm.nih.gov/research/litsense-api/api/?query=<text>&rerank=true&limit=<n>`.

- `query`: free text, required.
- `rerank`: semantic reranking on top of a term-overlap first pass.
- `limit`: result count; tested up to 10.
- `min_score`: not exercised.

The response is a JSON array. Each item carries `pmid`, `pmcid`, `section` (abstract, INTRO, METHODS, RESULTS, DISCUSS, SUPPL or null), `score`, `text` and an `annotations` array. No published rate limit; the probe kept to one request per second.

## Questions chosen

Ten from `eval/golden/golden_dataset.json`, all gene, variant and literature questions whose must-cite list names PubMed or which an abstract would plausibly answer:

- G-002: BRCA1 overview including literature evidence
- G-006: for PMID 11237011, what sequence data and BioProjects link to it
- G-019: MeSH terms for PMID 11237011
- G-021: which papers mention CFTR and what they cover
- G-023: clinically significant CFTR variants
- G-024: rs334 and its associated condition
- G-025: MTHFR C677T evidence quality
- G-028: APOE and late-onset Alzheimer disease evidence
- G-030: EGFR mutations in NSCLC and recruiting trials
- G-033: MLH1 against MSH2 in colorectal cancer risk

G-006 and G-019 were chosen deliberately: they are the only golden questions anchored to one named PMID, the shape "a sentence under each cited paper" needs.

## Per-question results

Top result only; the top three are judged in the raw data.

| Id | Latency (s) | Top PMID | Verdict | Reason |
|----|------|------|------|--------|
| G-002 | 1.49 | 41619087 | partly | On topic, but refers to "other studies" with no antecedent |
| G-006 | 1.12 | 41160891 | no | Describes a different paper; PMID 11237011 is not in the top ten |
| G-019 | 0.67 | 34629973 | no | About MEDLINE indexing in general; PMID 11237011 is not in the top ten |
| G-021 | 0.96 | 28845852 | partly | Uses CFTR as an analogy in a paper about a different disease |
| G-023 | 1.80 | 32512765 | yes | States the CFTR variant classification scheme |
| G-024 | 2.45 | 26445879 | partly | On topic, but a stray results-table caption fragment |
| G-025 | 1.12 | 10794488 | yes | States a clear MTHFR C677T conclusion |
| G-028 | 1.56 | 23119149 | yes | States the APOE and late-onset Alzheimer disease link |
| G-030 | 2.10 | 25806291 | partly | Answers the EGFR half and ignores the trials half |
| G-033 | 1.31 | 40073395 | yes | States that MLH1 and MSH2 both cause Lynch syndrome |

## Numbers

- Top result judged yes: 4 of 10. Partly: 4 of 10. No: 2 of 10.
- Latency: median 1.40 seconds, worst 2.45 seconds.
- Failures: none of ten queries.
- Duplicates: the same PMID and text twice in G-021's top three, and one PMID at ranks 5 and 6 for G-019. The API's own de-duplication is incomplete.

## PMID restriction

Four guessed parameter names (`pmids`, `pmid`, `pmid_list`, `restrict_pmid`) each carried PMID 11237011. All four returned normal responses without that PMID, and the four result sets differed from each other and from the baseline: the parameters are ignored, not applied or rejected. The unofficial wrapper's documented parameters (query, rerank, limit, min_score) confirm there is no restriction by paper.

## Failure cases and misleading snippets

- G-006 and G-019: the named paper never appears. A reader seeing PMID 11237011 in the sources with an unrelated sentence under it would believe the sentence describes that paper.
- G-021: CFTR appears only as an aside in a paper about another disease; shown under a CFTR citation it reads as CFTR-specific.
- G-024: a grammatically incomplete caption fragment.
- G-030: fluent and on topic but covers one half of a two-part question.

## Recommendation

Do not build as decided: a wrong-paper snippet under a real citation is worse than none, because the point of a snippet is that a reader trusts it without checking.

A narrower version is possible and needs its own smoke test first:

- Query LitSense with the cited paper's own title, then keep only results whose `pmid` matches that paper.
- Show a snippet only when a match survives; otherwise show nothing.
- Prefer abstract, RESULTS or DISCUSS sections over METHODS, SUPPL or null, and skip fragments with no verb or under about eight words.
- Treat 4 in 10 as an upper bound for general questions only.

## The narrow version, smoke-tested the same night

The recommendation above asked for its own test first. Run on 2026-09-25 by researcher I: 20 real PubMed papers the product cites, each title sent to LitSense, keeping only results from the same PMID. Script and raw output: `title_smoke_test.py`, `raw_title_probe.json`.

- Same PMID returned: 19 of 20 titles (none for PMID 11237011).
- A real content sentence, not the title echoed back: 6 of 20. The other 13 matches were the paper's own title returned as its best sentence, which repeats what the citation already shows.
- Useful as a snippet: 4 of 20 yes, 2 of 20 partly, 14 of 20 no.
- Latency: median 1.28 seconds, worst 2.30 seconds, no failures.
- Papers with PMC full text matched real content more often: 3 of 5, against 3 of 15 without.

Verdict: do not build the narrow version either. The PMID filter removes the wrong-paper risk, but one reader in five getting a useful sentence is too low for a feature shown under every citation. Card 44 stays in To do with these measurements for the product owner.
