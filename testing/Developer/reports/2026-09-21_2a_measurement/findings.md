# Item 2a is mostly already built, and its residual gap is item 11.34

Measured 2026-09-21, before writing any code for 2a, on the principle that a
component fed by an assembly step is not the constraint until the assembly
step has been checked. Build phase 6.0 found five of Section 21's eight
requirements already built the same way.

## What 2a asks for

"Cite every retrieved finding, so a question's source set is identical run to
run" (DECISIONS.md, 2026-09-20). The stated problem was that a citation exists
only where the model grounded a claim, and that choice varied once in 21
measured runs.

## Why the obvious implementation would be a regression

Emitting a citation per retrieved row is not a new idea here. It is what build
phase 2.1 did, and `_citations_from_grounded_claims`' own docstring records
why it was replaced:

> 2.1 emitted a citation for every row that carried a `source_url`, whether or
> not the answer said anything about it. That is how the flagship question
> shipped twenty-five chips over an answer to a different question, each one
> resolving perfectly.

So "cite every row" is a recorded defect, not an unbuilt feature.

## What is already built

`tail_is_listing` is unconditionally `True` (`core/graph.py`), so on every
answer and at every depth the findings tail runs
`build_structured_fallback_narrative` over ALL admitted findings, grounds the
result, and MERGES those claims into the answer's claim set. Every finding
that grounds therefore earns a citation, whether or not the model's own prose
mentioned it.

That is 2a's requirement, already in place, reached through claims rather than
by bypassing them.

## The residual gap, measured

Five admitted findings through the real tail path, offline:

| Finding | Value shape | Cited by the tail |
|---|---|---|
| `name` = "Familial cancer of breast" | one sentence | yes |
| `abstract` = "BRCA1 functions as a tumour suppressor. It participates in DNA repair." | TWO sentences | NO |
| `symbol` = "BRCA1" | one sentence | yes |
| `summary` = "This gene encodes a nuclear phosphoprotein. It acts as a tumor suppressor." | TWO sentences | NO |
| `title` = "A trial of olaparib" | one sentence | yes |

`admitted findings: 5, cited by the tail: 3, stripped: 4`

Both uncited findings are multi-sentence values and nothing else distinguishes
them. `build_structured_fallback_narrative` puts one marker at the END of a
finding's body while `run_grounding_pass` splits on sentence boundaries, so
every sentence but the last is unmarked and stripped as an uncited claim.

That is item 11.34 exactly.

## What follows

- 2a needs NO new citation mechanism. Fixing 11.34 closes its gap.
- The two finding types that carry multi-sentence values are the two that
  matter most for an answer a person can read: PubMed abstracts, citeable
  since `9cf8572`, and NCBI gene summaries, retrieved since 2026-09-21. Both
  are currently retrieved and then silently dropped.
- After 11.34 lands, re-run this measurement. If every admitted finding is
  then cited, 2a is done and should be closed with this evidence rather than
  built.

## How to re-run it

The script is `measure.py` beside this file. It builds five findings with the
value shapes above, runs the real tail path, and prints which earned a
citation.
