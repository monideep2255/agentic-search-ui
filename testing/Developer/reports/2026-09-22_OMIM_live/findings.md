# OMIM dispatch, live proof (item 2b, 2026-09-22)

What a person asking a question now gets: a question about a gene shows OMIM's
entry for that gene, cited to `omim.org`, and never an entry for a different
gene. This file is the measurement behind that sentence.

## Table of contents

- [What was measured](#what-was-measured)
- [The ten runs](#the-ten-runs)
- [What the filter actually dropped](#what-the-filter-actually-dropped)
- [Calls against the 20-call ceiling](#calls-against-the-20-call-ceiling)
- [What this does not measure](#what-this-does-not-measure)
- [One defect in the instrument, not the product](#one-defect-in-the-instrument-not-the-product)

## What was measured

Setup: the API run locally from this worktree on port 8011, one account created
through `/auth/signup` and `/auth/login`, ten runs in all, five each of "Which
diseases are associated with GCK?" and "Which diseases are associated with
BRCA1?". Every citation event was captured per run.

GCK is the case that matters. OMIM's own search ranks `MAP4K2` first for that
symbol, which is the wrong-gene failure `breadth_plan.filter_omim_titles` was
written to prevent and which nothing called until today.

Every cited OMIM entry was then checked against NCBI ESummary directly, by
plain `urllib` on a path that touches none of the agent's own machinery, and
its title's semicolon-separated symbol fields compared with the asked symbol.

Evidence: one JSON file per run under `runs/`, the per-run verification in
`runs/verification.json`, and the cold-cache pair under `cold_cache/`.

## The ten runs

| Gene | Runs | Citations per run | OMIM citations per run | OMIM entry cited | Title, read back from NCBI | Wrong-gene hits |
|---|---|---|---|---|---|---|
| GCK | 5 | 54 | 1 | `omim.org/entry/138079` | GLUCOKINASE; GCK | 0 |
| BRCA1 | 5 | 73 | 1 | `omim.org/entry/113705` | BRCA1 DNA REPAIR-ASSOCIATED PROTEIN; BRCA1 | 0 |

- Ten of ten runs carry exactly one OMIM citation.
- Ten of ten cite the entry whose title names the asked symbol in a symbol
  field, confirmed against NCBI on an independent path.
- `MAP4K2` appears in zero of the five GCK runs, in any citation and in any
  tool result.
- Every run returned the same citation count for the same question, so the
  source set is still one set per question (item 11.21's own rule).
- Latency, end to end: GCK 19.5 to 33.6 seconds, BRCA1 11.7 to 20.2 seconds.
  Unchanged in shape from before this item, since the OMIM pair runs inside the
  two concurrent stages that already existed.

## What the filter actually dropped

Measured on the cold-cache GCK run: the OMIM ESearch returned 10 ids, the OMIM
ESummary was issued on all 10, and 1 record survived into rows. Nine records
were dropped for naming a gene other than the one asked about, `MAP4K2` among
them.

So the control is not decorative on this question. Without it, nine wrong-gene
records would have been offered to synthesis, each one fully and correctly
citeable.

## Calls against the 20-call ceiling

`harness/call_budget.py` sets `MAX_LAYER_2_3_CALLS_PER_QUERY` to 20 and charges
at `ncbi_transport.execute_get`, the same line that writes the audit entry, so
counting audit lines whose tool starts with `ncbi_transport:` counts charged
calls exactly.

| Question | Redis response cache | Charged Layer 2 and 3 calls | Ceiling | Headroom |
|---|---|---|---|---|
| GCK | cold, empty cache | 16 | 20 | 4 |
| BRCA1 | cold, empty cache | 14 | 20 | 6 |
| GCK | warm | 11 | 20 | 9 |
| BRCA1 | warm | 11 | 20 | 9 |

The cold figure is the one that binds. The cold run was taken by pointing
`REDIS_URL` at an unused database index, so the cache started empty and nothing
was deleted to get there.

OMIM's own share is 2 of those calls, one ESearch and one ESummary. The cold
GCK run's 16 calls break down as the symbol resolution at Think (3), the gene
report (1), PubTator3 twice (2), ClinicalTrials.gov once (1), the three breadth
searches (3), the four follow-up fetches (4), and the MedGen disease-name
resolution at Write (2).

UNDER THE CEILING, AND WORTH WATCHING. 16 of 20 on a plain gene question is the
tightest figure this budget has carried, and it is 2 tighter than it was
yesterday. A question that also names rs ids plans `ncbi_dbsnp` and
`litvar2_lookup` per id, and `ncbi_dbsnp` makes two sequential requests, so that
shape has room to reach the ceiling. That is not measured here and is not new
with this item, but it is 2 closer than it was. The ceiling was not raised.

## What this does not measure

Stated so the gap is arguable rather than implied:

- Two genes. Whether OMIM's titles take the `NAME; SYMBOL` shape for every
  symbol is not established. A symbol whose OMIM entry does not name it in a
  symbol field gets no OMIM row at all, which is the filter refusing rather
  than failing, but it does mean coverage varies by gene.
- Phenotype entries. The filter keeps entries whose SYMBOL field matches, so a
  disease entry naming no gene symbol is dropped. For GCK that is why 1 of 10
  survived rather than 3 or 4. Whether a gene question should also show OMIM's
  phenotype entries is a product question, not a defect, and is not decided
  here.
- The screen. These runs read the event stream, not the rendered page.
- Concurrency and load. One caller at a time, locally.

## One defect in the instrument, not the product

The first version of the verifier counted one `MAP4K2` mention in every single
run, including the BRCA1 runs, which would have read as the defect being live.
It was not. The verifier scanned the whole saved record, and the record carries
a field literally named `mentions_map4k2`, so the instrument was matching the
name of the thing it was looking for. Fixed by scanning only the run's own
citations and tool results, after which the count is 0 everywhere. Recorded
rather than tidied away, because it is the same family as build phase 6.2's
four instrument defects: a harness reporting a plausible value for something
that was not there.
