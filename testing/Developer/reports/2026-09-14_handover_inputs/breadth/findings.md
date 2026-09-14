# Search breadth audit, 2026-09-14

Audit of develop at commit 2b6d274, by a read-only sub-agent whose own write of a report file was refused; the main agent recorded its findings here. Probe scripts and raw results sit beside this file (`probe_graph.py`, `graph_probe.jsonl`, `probe_apis.py`, `probe_apis_fix.py`, `api_probe.jsonl`, `api_probe_stdout.txt`, `tool_audit_probe.jsonl`).

## Table of contents

- [Diagnosis](#diagnosis)
- [Is the model a cause](#is-the-model-a-cause)
- [Where the code decides what is searched](#where-the-code-decides-what-is-searched)
- [What is reachable and never used](#what-is-reachable-and-never-used)
- [Live measurements](#live-measurements)
- [The plan: search broad, cite exact](#the-plan-search-broad-cite-exact)
- [Ranked recommendations](#ranked-recommendations)
- [Constraints to settle first](#constraints-to-settle-first)

## Diagnosis

- Plan makes no model call and builds a fixed list in code: one graph template chosen by the first shape word in the question, plus exactly four Layer 2 and 3 calls per resolved gene (`core/graph.py:2514` and `:3406`).
- "Which diseases are associated with BRCA1?" runs one hop and returns 4 rows, while the graph holds 54 GO processes, 15,310 variants and 3,447 articles for BRCA1 that are never asked for.
- No planned call touches PubMed, PMC, live ClinVar, OMIM, GTR or LitSense, although `ncbi_efetch` already has working `search`, `fetch` (PubMed abstracts) and `link` actions, and `pubtator_annotate` has a working `annotate_publications` mode.
- Each live record contributes one fact (`_pick_representative_field`), so the Datasets gene record's 1,253-character RefSeq summary and 117 GO terms become one finding: the symbol.
- The graph's GO rows are dropped by cite-or-refuse, because the `GO:` prefix maps to no NCBI URL.
- All eleven decision points are code constants or rules written for consistency (the 2026-09-13 one-source-set rule) or safety. None is a model decision.

## Is the model a cause

No. The configured models (guard, plan and synth tiers) affect entity extraction reliability (the measured GCK refusals, now covered by code fallbacks) and prose quality. They cannot cite a source that was never retrieved, and no model chooses which tools run.

## Where the code decides what is searched

| Decision | File and line | What it decides today |
|---|---|---|
| Which entities exist | `core/graph.py:1875` `think_node`, `:1621`, `:2724`, `:3019`, `:1494` | Model spans, live-confirmed; at most 3 gene and 3 disease lookups; at most 10 target entities |
| Whether a graph call is planned | `core/graph.py:3623` `_select_planned_tool_call` | One `cypher_query`, `row_limit=100` |
| Which Layer 2 call | `core/graph.py:3406` | One Datasets gene report for the first gene only |
| Which Layer 3 calls | `core/graph.py:2514` `_build_layer_tool_calls` | PubTator entity lookup (limit 5), trials on the symbol, dbSNP and LitVar2 only for typed rs ids |
| What a Layer 2 or 3 result contributes | `core/graph.py:2364`, `_LAYER_TOOL_ROW_CAP = 5` | Stable sort, cut to 5 |
| The 20-call ceiling | `core/graph.py:4584`, `harness/call_budget.py:101` | Never binds today (4 to 8 counted calls) |
| Which Cypher runs | `tools/cypher_templates.py:580` `select_template` | One template per question, by first shape word |
| How many findings | `synthesis/findings.py:102` (25), `:107` (12,000 chars), `:91` (2,000 per value); `core/graph.py:4709` (20 citations) | Admission Layer 2, 3, then 1 |
| Which single fact per record | `core/graph.py:4880` `_pick_representative_field` | One finding per row |
| Which rows are citeable | `tools/cypher_provenance.py:280`, `:390`; `tools/graph_schema_constants.py:190` | GO, HP and MONDO prefixes map no URL |
| Untrusted free text | `core/graph.py:4103`, `:4148`; `harness/coordinator_worker.py:217` | Article titles emptied |

## What is reachable and never used

- PubMed search and abstract fetch work (`ncbi_eutils_actions.py:661`, `:1064`, `:965`) and are never planned.
- `pmc` is not in `SearchDb` (`ncbi_efetch_schemas.py:165`); ELink from PubMed to PMC works.
- The Datasets `summary` is dropped by `_GENE_REPORT_FIELDS` (`ncbi_datasets_actions.py:136`).
- PubTator3 `annotate_publications` is implemented (`pubtator_annotate.py:762`) and never planned.
- LitSense has no tool (the roster is seven).
- ClinVar live, OMIM, GTR and MedGen by gene are valid search targets, never planned.
- E-utilities limiter default is 3 per second (`ncbi_transport.py:305`, env `NCBI_EUTILS_RPS`), with a 1.5-second lookup-class queue wait ceiling (`call_budget.py:118`). The API key is configured.
- No Layer 2 or 3 response cache exists in code (Section 4.3 unbuilt).

## Live measurements

Three samples per call, medians.

- Layer 1 on BRCA1: diseases 0.72 s (4 rows); variants 3.32 s (100 of 15,310); variant-to-disease fold 2.69 s (19.7 s cold once); GO processes 0.72 s (54, not citeable today); orthologs 6.19 s; bounded articles 3.51 s (20 of 3,447).
- PubMed ESearch, gene and disease, sort by date: 0.14 s. EFetch 5 abstracts: 0.22 s, 1,000 to 1,300 characters each, all citeable on `pubmed.ncbi.nlm.nih.gov`.
- PubTator3 `annotate_publications` on 5 PMIDs: 0.04 to 0.18 s, 20 annotations and 5 to 10 relations per paper.
- ClinVar ESearch plus ESummary: 0.05 + 0.06 s, 10 of 10 records carry classification, review status and readable condition names ("Maturity-onset diabetes of the young type 2").
- Datasets gene record: 0.09 s, with a 1,253-character summary and 29/51/37 GO terms for BRCA1.
- OMIM ESearch plus ESummary: under 0.1 s; for GCK the first hit was MAP4K2, so titles must contain the symbol.
- LitSense: 1.2 to 1.5 s, sentences with PMID and section; no tool exists.
- PMC: 2 of 5 recent BRCA1 papers have open-access full text.
- ClinicalTrials.gov with the symbol as condition returns the same 383 studies as a free-text search; the off-topic feel is the sort (lowest NCT id), not the search.

## The plan: search broad, cite exact

- Per question shape, a fixed fan-out across all three layers with deterministic inputs, a stable sort and a cap per source. The widest plan is 10 counted Layer 2 and 3 calls, 16 with two typed rs ids, under the 20-call ceiling.
- Act wall time rises from 0.5 to 3.2 s today to about 3 to 4 s, run in parallel.
- Abstracts become findings. The grounding gate accepts a sentence only if its text is contained in a finding, so explanatory sentences taken verbatim from abstracts can be cited without loosening the gate.
- Untrusted abstract text goes through one Guard-tier reader call that returns verbatim spans; code verifies each span is a substring of the original abstract before it becomes a finding.
- Prompt bounds: per-source caps enforced before admission; worst case about 27,400 characters of findings, so the findings block cap would rise from 12,000 to 28,000 characters and the finding count from 25 to 40. All of it sits in the dynamic suffix.
- Cost per query rises from about 0.014 to 0.018 USD, under the 0.10 USD per-query cap.

## Ranked recommendations

| Rank | Build | Latency | Calls | Money | Risk |
|---|---|---|---|---|---|
| 1 | Literature for every resolved gene: PubMed search, 5 abstracts, PubTator3 relations on the same papers, via reader-verified spans | +0.6 s, reader +1 to 2 s in parallel | +3 | +0.003 USD | Top-5 papers move as PubMed indexes; disclose the search date |
| 2 | Keep the whole Layer 2 record: Datasets summary and GO terms as findings, live ClinVar with conditions, OMIM by symbol | +0.2 s | +4 | +0.001 USD | OMIM symbol ambiguity; keep only titles containing the symbol |
| 3 | Make GO rows citeable by attributing each term to the Datasets gene record's GO entry | 0 | 0 | 0 | None |
| 4 | Trials by bound disease title, sorted by last update | 0 | 0 to +1 | 0 | Source set moves when a study updates |
| 5 | One context template per shape, 12 rows | +2 to 3 s | 0 | 0 | One cold 19.7 s sample, bounded at 30 s |
| 6 | Confirm the NCBI key's rate, set `NCBI_EUTILS_RPS=10`, add an in-process response cache | Negative | 0 | 0 | A product-owner decision under the tool-call-budgets rule |
| 7 | Graph article titles via the reader-span route | +3.5 s | 0 | +0.0003 USD | Oldest papers first; pair with rank 1 |
| 8 | PMC open-access availability shown on paper cards | +0.3 s | +2 | 0 | Additive `pmc` enum value |
| 9 | LitSense as an eighth tool | +1.5 s | +1 | 0 | Contract-version event; defer to Phase 7 |

Ranks 1 and 2 together take the BRCA1 diseases answer from 11 sources to about 25 at about 3 seconds more and 0.004 USD more per query.

## Constraints to settle first

- E-utilities pace: at the default 3 per second, nine calls issued at once would exceed the 1.5-second queue wait ceiling and fail fast. Either chain search-then-fetch pairs with at most 4 concurrent, or confirm the key and set 10 per second. The tool-call-budgets rule asks before locking that constant.
- Locked-spec items to reconcile: `pmc` missing from `SearchDb` and `summary` from the Datasets field list (both additive); Section 11.1's wording on raw retrieved text; the Section 4.3 cache.
- Scope: nothing proposed is BLAST, sequence similarity, VCF or non-NCBI federation.
