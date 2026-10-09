# Card 15 diagnosis: the remaining paths where the system writes its own graph search

Diagnosis only, 2026-10-08 overnight, read against `develop` at `c916cfa3`. Paths are relative to `<repo-root>`. No code was changed, no model was called and the graph was not queried.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The cause](#the-cause)
- [Every path that still reaches a model-written search](#every-path-that-still-reaches-a-model-written-search)
- [The smallest fix](#the-smallest-fix)
- [Overlap with phase 8.7 and the guardrail](#overlap-with-phase-87-and-the-guardrail)
- [Needs the owner](#needs-the-owner)
- [Proposed test query](#proposed-test-query)

## Status today

Part fixed. Step 1 is live (`ac3dded8`, merged as #171 on 2026-10-05): one paper with no shape word, on a hop class or a no-count aggregate, takes the checked template `article_links_one`. Nothing has changed in `tools/cypher_templates.py` or the model path since. Every other case below still writes its own graph search.

Decision D5 (`testing/Board_plan.md`, line 206, answered yes): no model-written graph search except true count questions.

## What a person sees

When no checked search fits, a model writes the graph query. Measured before: the written query is rejected by the validator, or runs into the graph's 30-second limit, and the person is told a search did not finish (G-037, G-039, G-033); or it returns rows that answer a different question (G-014). Either way the same question can give different sources on different runs.

## The cause

| Where | What it does |
|---|---|
| `src/system_03_search_agent/tools/cypher_templates.py:760`, `select_template` | Returns a checked template or None. None means "run the model path". |
| `tools/cypher_query.py:1930` to `1975` | When the template is None, `_generate_and_validate` asks the plan tier to write the query (`generate_cypher`), with one repair retry. |
| `cypher_templates.py:172` to `177`, `_LABEL_BY_PREFIX` | Only Gene, Disease and Article CURIEs can anchor a template. A ClinVar variant, an organism (`NCBITaxon`), a MeSH term, a GO term or a phenotype anchor always gets None (`anchor_label_for`, line 181). |

A question that binds no CURIE at all does not reach the model; it returns "no entity could be identified" (`cypher_query.py:1904`).

## Every path that still reaches a model-written search

Read from `select_template` and `_mixed_gene_disease_template` (lines 399 to 470). "True count" means `_wants_count` is true: "how many" on any class, or "count" or "number of" on an aggregate question (line 238).

| Path to None | Example shape | A true count? | Allowed by D5? |
|---|---|---|---|
| Anchor is a ClinVar variant, an organism, a MeSH, GO or phenotype term | "Which conditions is this ClinVar variant linked to?" | No | No |
| Labels mixed other than Gene with Disease (Gene with Article, Disease with Article, any with a variant) | "Does PMID 123 discuss BRCA1?" | No | No |
| One or more Diseases, no shape word, `single_hop` or `multi_hop` (lines 836 to 839, the G-014 reason) | "What is linked to Marfan syndrome?" | No | No |
| One or more Diseases, no shape word, `aggregate`, no count | "Summarise what the graph holds on Marfan syndrome" when classed aggregate | No | No |
| Several Articles, no shape word, not a lookup | "Compare PMID 1 and PMID 2" | No | No |
| Gene with Disease: the variants shape with several genes, or a shape other than diseases or variants (lines 452 to 466) | "Variants in MLH1 and MSH2 causing Lynch syndrome" | No | No |
| Two shapes matched with several anchors, outside lookup, single-hop and aggregate (`_resolve_shape`, line 364) | "Genes and variants for BRCA1 and BRCA2" on `multi_hop` | No | No |
| A count over several anchors (line 873; `_mixed_gene_disease_template` line 460) | "How many variants do BRCA1 and BRCA2 have?" | Yes | Yes |
| An aggregate count on a Disease or Article with no shape | "How many records mention Marfan syndrome?" | Yes | Yes |

How often each happens is not measured. Cheapest check: the cypher tool already returns the template name, None on the model path (`cypher_query.py:32`); run the test queries document's graph questions locally and count the None results by path. That costs Think and Plan calls for each question and no model-written query needs to run.

## The smallest fix

Close the model path for everything D5 does not allow, and give each closed case a checked answer or an honest one.

| Field | Value |
|---|---|
| Change | In `select_template`, a None that is not a true count becomes a checked fallback: the anchor's own record (`_record_template`) for one anchor of any label the graph holds, extended to ClinVar variants and organisms. Where no record template fits (mixed labels, several anchors of a label with no hop), `cypher_query.execute` returns "no checked graph search fits this question" and the answer rests on Layers 2 and 3, as it does when a search fails today, without the model attempt. `generate_cypher` is then reached only from a true count. |
| Files and functions | `src/system_03_search_agent/tools/cypher_templates.py`: `_LABEL_BY_PREFIX`, `anchor_label_for`, `select_template`, `_record_template`; `tools/cypher_query.py`: the model-path branch of `execute` (lines 1930 to 1975); tests in `tests/system_03_search_agent/tools/test_cypher_templates.py` |
| Answer path | Yes |
| Dial position | 2, runnable behaviour |
| Size | M. S for closing the path alone; the record templates for new labels need a live read-only check against the graph that each label has the properties the record template returns. |
| Migration, package, event schema | None |

The G-014 risk stays the reason a Disease hop question with no shape does not get a record: Think can resolve a common noun ("diseases") to a list of concepts, and their records would be a page of unrelated diseases. For several Diseases with no shape, return the honest "no checked search fits" rather than records. For one Disease, its record is safe: it is the disease the person named.

Cards 4 and 32 close with this one (`testing/Board_plan.md`, lines 63 and 64).

## Overlap with phase 8.7 and the guardrail

| Fence | Phase 8.7 | Guardrail |
|---|---|---|
| `tools/cypher_templates.py`, `tools/cypher_query.py` | None | None |
| `core/graph.py` | Not touched | Not touched |

Can be built tonight.

## Needs the owner

No. D5 is the owner's decision and this applies it. The choice inside it, one Disease's record against an honest "no checked search fits" for several, follows the G-014 measurement already on record.

## Proposed test query

Existing query 104 ("The data records linked to one paper", card 74, G-006) covers step 1. Proposed entry 110 for section 3 of `testing/Test_queries_and_workflows.md`:

```markdown
### 110. A graph question with no checked search gives the same answer every time (card 15, D5)

Queries to try:

- `What conditions is ClinVar variant 12345 linked to?`, three times
- `What is linked to Marfan syndrome?`, three times
- `How many variants do BRCA1 and BRCA2 have?`

What you should see:

- The first two give the same sources on every run, and never say a search did not finish because of a query the system wrote.
- Where the graph has nothing for the question, the answer says so plainly and shows what the live sources found.
- The count question still answers with a count.
- Why it matters: a person who asks twice and gets two different answers stops trusting both.
```
