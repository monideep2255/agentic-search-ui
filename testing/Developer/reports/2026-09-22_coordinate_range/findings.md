# The coordinate range: what a person asking "what is under this window" gets now

Fix-plan item 1 as it stood on the evening of 2026-09-22: four golden questions never answered because Think resolved no entity for them, and the first of those shapes, a chromosome window such as chr17:43,044,295-43,125,364 on GRCh38, is the everyday question of clinical genetics. The person asking has a copy number variant call and wants to know what is under it; not knowing the gene is the reason for asking, and the product answered with a request to name a gene. This folder holds the plan written before the work (`plan.md`), the live probes that fixed the design (`probes.md`), and what shipped and how it was verified.

## Table of contents

- [Verdict](#verdict)
- [What the person sees](#what-the-person-sees)
- [What the probes settled](#what-the-probes-settled)
- [The design, and the decisions taken from the user's chair](#the-design-and-the-decisions-taken-from-the-users-chair)
- [What changed in the code](#what-changed-in-the-code)
- [Live verification on develop](#live-verification-on-develop)
- [Limits, said plainly](#limits-said-plainly)
- [Method and evidence](#method-and-evidence)

## Verdict

| Question | Before | After |
|---|---|---|
| What ACMG-relevant evidence is available for a copy number variant spanning chr17:43,044,295-43,125,364 on GRCh38? (golden G-001) | Think bound nothing, the graph search was dispatched with nothing to look up, and the answer asked the person to name a gene | Think resolves the genes under the window from NCBI Gene (BRCA1 first, seven smaller annotated features beside it), the question proceeds as a gene question, and the answer carries the ClinVar and dbVar records that genuinely overlap the window on GRCh38, each cited to its NCBI page |
| A window with no assembly named | The same request to name a gene | The assembly question: GRCh38 and GRCh37 put different genes under the same numbers, so the product asks rather than guesses |
| A window on GRCh37 | The same request to name a gene | The dbVar and ClinVar overlap records for GRCh37 placements; genes are not resolved from coordinates, since Entrez Gene's positions are on the current assembly only, and the answer says which assembly it used |

## What the person sees

Decided from the user's chair, the standing rule since the morning of 2026-09-22.

- A clinician or researcher who types a window gets the genes under it named, without naming any themselves, and the structural variants and clinical variants NCBI holds for that exact stretch, on the assembly they said. The evidence is listed; it is not classified. The guardrail already refuses a pathogenicity verdict, and the ClinVar classification shown is NCBI's own statement on each record.
- A person who forgets the assembly is asked one question and told why it matters, instead of being handed an answer about the wrong stretch of chromosome. That costs one round trip and prevents a confident wrong answer, which the user's chair ranks above speed.
- Honesty is preserved by construction: the gene list is filtered by each record's own genomic placement, because NCBI's range fields are not interval overlap (measured on this same window in build phase 3.1 for dbVar, and the same care applies to Gene); a window with more than ten genes says so and searches the ten nearest its start; the overlap calls report their totals (15,506 ClinVar records and 2,884 dbVar records overlap the BRCA1 window) so a capped list is never presented as the whole.

## What the probes settled

Measured live on 2026-09-22 before any code was written (`probes.md`, twelve NCBI requests in total, one per second):

| Fact | Result |
|---|---|
| Which Gene search term finds the genes under a window | Three candidate terms are equivalent; NCBI translates each to the same CHRPOS range and returns the same eight ids, BRCA1 (672) first. The plan uses the shortest, `17[CHR] AND 43044295:43125364[CPOS] AND human[ORGN]` |
| Whether the range search returns genes that do not overlap | Not on this window: all eight records genuinely overlap by their own placement. The filter stays, because the dbVar trap this repository recorded is the same class |
| How Gene reports a placement | In transcription order: BRCA1 is on the minus strand and comes back with start greater than stop. The module takes the smaller bound as the start before comparing, so no minus-strand gene is dropped |
| What the overlap action returns for the window | ClinVar: 20 of 15,506 overlapping records in 0.39 s. dbVar: 20 of 2,884 in 1.36 s. Every candidate the action placement-checked survived |
| A boundary worth knowing | NCBI's live Gene record for BRCA1 now ends at 43,170,326, about 45,000 bases past the window's end; the window still overlaps the gene, and the discrepancy is recorded rather than resolved |

## The design, and the decisions taken from the user's chair

- The window is recognised by a fixed rule, never the model, beside the exact-identifier pre-pass, which stays local and synchronous as its gate arm requires: `chr17:43,044,295-43,125,364`, with or without commas, with `chr` or `chromosome 17`, a hyphen, an en dash or "to" between the ends, and an assembly word anywhere in the question (GRCh38, hg38, b38; GRCh37, hg19, b37). Windows over 50 million bases are not treated as a locus question. Only the first window in a question counts.
- With GRCh38 named, Think resolves the genes under the window with one Gene ESearch and one ESummary, filters by placement, orders named genes before unnamed loci and each group by position (the first resolved gene is the one the fan-out follows), keeps at most ten and says so when there were more, and adds each as a resolved entity with its symbol as the text. The model's own gene-shaped spans are not confirmed live on a window question, so its Layer 2 and 3 call count is fifteen on every pass. From there the question is a gene question: the graph, the live gene record, the literature, ClinVar, OMIM, the gene's own summary.
- Plan adds the ClinVar and dbVar overlap calls right after the question's own graph call, so that under the twenty-call ceiling they are never the ones skipped: for a window question they are the answer. Two calls, only on a window question.
- Act shapes each overlap record with the fields a person choosing a record reads: the ClinVar variant's title, NCBI's germline classification, the genes it names, and its placement on the assembly asked about; the dbVar record's variant type, genes and placement. The requested assembly is withheld from the rows because it repeats the question.
- The alternatives weighed and not taken: guessing GRCh38 when no assembly is named (a confident wrong answer for anyone working on GRCh37); resolving the genes from the ClinVar records' own gene lists instead of Gene (biased to variant-rich genes and empty for a window with no clinical variants); letting the model recognise the window (a fixed rule is the same every pass, which item 11.21 requires of sources).

## What changed in the code

- `core/coordinate_window.py`, new and pure: the parser, the Gene search term, the placement filter with its cap, the two overlap calls as breadth-plan calls, the assembly question and the disclosure sentence. Sixty-six unit tests of its own, a row in the debugging guide, the manifest regenerated.
- `core/graph.py`: `resolve_window_genes` (the live lookup, empty on any failure rather than a crashed turn), the window parse in Think beside the exact-identifier pre-pass, the resolved genes merged ahead of the model's spans so the fallbacks do not fire on a resolved question, the assembly question as Think's clarification, the window on the state, the two overlap calls in Plan, and the two row-field allowlists in Act.
- `core/state.py`: the `coordinate_window` field, with its docstring.
- `tests/.../core/test_coordinate_window_wiring.py`: Think with GRCh38, with no assembly, with GRCh37 and with a failing transport; Plan with and without a window; the row shaping for both overlap purposes; each with a populate check.
- Two follow-up commits from the live runs: `e477077`, named genes before unnamed loci in the module, with its test; `c72b8a7` (and `d21193a` for its test arm), a window question's entities are the window's genes, so the model's spans are not confirmed and the call count is fixed.

## Live verification on develop

Twenty signed-in runs on a fresh test account, one at a time, the laptop held awake, through the consistency run's own client (`run_consistency.py` for the golden row, `run_windows.py` for the two questions that are not golden rows). The runs span three deploys, because the live runs found two things worth fixing the same night and each fix was verified on its own passes:

| Deploy | What it carried | Passes |
|---|---|---|
| `66b3811` | The feature as built | G-001 passes 1 to 5, CFTR passes 1 to 3, no-assembly passes 1 to 3 |
| `e477077` | Named genes before unnamed loci | CFTR passes 4 to 6, no-assembly passes 4 to 6 |
| `c72b8a7` and `d21193a` | A window question's call count fixed at fifteen | G-001 passes 6 to 8 |

| id | pass | outcome | seconds | resolved | asked | ClinVar overlap | dbVar overlap | own graph call | trust | sources by layer |
|---|---|---|---|---|---|---|---|---|---|---|
| G-001 | 1 | no done event | 23.1 | BRCA1, LOC127886930, LOC129664047, RPL21P4, LOC126862571, LOC110485084 ... | - | ok 5 | ok 5 | ok 100 rows | - | - |
| G-001 | 2 | answered | 19.7 | BRCA1, LOC127886930, LOC129664047, RPL21P4, LOC126862571, LOC110485084 ... | - | ok 5 | ok 5 | ok 100 rows | ask | L1 66, L2 24, L3 10 |
| G-001 | 3 | answered | 19.5 | BRCA1, LOC127886930, LOC129664047, RPL21P4, LOC126862571, LOC110485084 ... | - | ok 5 | ok 5 | ok 100 rows | ask | L1 66, L2 24, L3 10 |
| G-001 | 4 | answered | 19.1 | BRCA1, LOC127886930, LOC129664047, RPL21P4, LOC126862571, LOC110485084 ... | - | ok 5 | ok 5 | ok 100 rows | ask | L1 66, L2 24, L3 10 |
| G-001 | 5 | refused, the call ceiling | 10.6 | BRCA1, RPL21P4, LOC127886930, LOC129664047, LOC126862571, LOC110485084 ... | - | error 0 | error 0 | ok 100 rows | flag | none |
| G-001 | 6 | answered | 22.4 | BRCA1, RPL21P4, LOC127886930, LOC129664047, LOC126862571, LOC110485084 ... | - | ok 5 | ok 5 | ok 100 rows | ask | L1 66, L2 24, L3 10 |
| G-001 | 7 | answered | 20.8 | BRCA1, RPL21P4, LOC127886930, LOC129664047, LOC126862571, LOC110485084 ... | - | ok 5 | ok 5 | ok 100 rows | ask | L1 66, L2 24, L3 10 |
| G-001 | 8 | answered | 22.6 | BRCA1, RPL21P4, LOC127886930, LOC129664047, LOC126862571, LOC110485084 ... | - | ok 5 | ok 5 | ok 100 rows | ask | L1 66, L2 24, L3 10 |
| W-CFTR | 1 | answered | 18.2 | LOC111674463, CFTR, LOC111674464, LOC113664106, LOC113664107, LOC113219471 ... | - | ok 5 | ok 5 | ok 100 rows | ask | L1 87, L2 13 |
| W-CFTR | 2 | answered | 14.1 | LOC111674463, CFTR, LOC111674464, LOC113664106, LOC113664107, LOC113219471 ... | - | ok 5 | ok 5 | ok 100 rows | ask | L1 87, L2 13 |
| W-CFTR | 3 | answered | 14.5 | LOC111674463, CFTR, LOC111674464, LOC113664106, LOC113664107, LOC113219471 ... | - | ok 5 | ok 5 | ok 100 rows | ask | L1 87, L2 13 |
| W-CFTR | 4 | answered | 15.2 | CFTR, CFTR-AS1, CFTR-AS2, LOC111674463, LOC111674464, LOC113664106 ... | - | ok 5 | ok 5 | ok 100 rows | ask | L1 66, L2 24, L3 10 |
| W-CFTR | 5 | answered | 14.3 | CFTR, CFTR-AS1, CFTR-AS2, LOC111674463, LOC111674464, LOC113664106 ... | - | ok 5 | ok 5 | ok 100 rows | ask | L1 66, L2 24, L3 10 |
| W-CFTR | 6 | answered | 20.4 | CFTR, CFTR-AS1, CFTR-AS2, LOC111674463, LOC111674464, LOC113664106 ... | - | ok 5 | ok 5 | ok 100 rows | ask | L1 66, L2 24, L3 10 |
| W-NOASM | 1 | the assembly question | 3.5 | none | yes | - | - | - | refuse | none |
| W-NOASM | 2 | the assembly question | 3.0 | none | yes | - | - | - | refuse | none |
| W-NOASM | 3 | the assembly question | 5.1 | none | yes | - | - | - | refuse | none |
| W-NOASM | 4 | the assembly question | 6.3 | none | yes | - | - | - | refuse | none |
| W-NOASM | 5 | the assembly question | 2.8 | none | yes | - | - | - | refuse | none |
| W-NOASM | 6 | the assembly question | 2.8 | none | yes | - | - | - | refuse | none |

Read against the verdict:

- The golden coordinate question resolves BRCA1 from the coordinates alone on every one of eight passes, with the seven smaller annotated features NCBI lists under the window beside it, and answers on six of the eight: the ClinVar and dbVar overlap calls return five rows each (the cap, with 15,506 and 2,884 as their totals), the question's own graph call returns the genes' ClinVar variants (100 rows, the cap), and the sources come from all three layers, the same set on every answering pass. 19 to 23 seconds. The two misses are each read:
  - Pass 1, the very first request after the deploy, delivered every tool result and then the stream ended with no done event and no error, at 23 seconds; the laptop was held awake by `caffeinate` and the next seven requests did not repeat it. Recorded as an unexplained single occurrence rather than rounded away.
  - Pass 5 refused with "reached its resource limit" and no citations: every overlap call and four fan-out calls were refused by the per-query ceiling of twenty Layer 2 and 3 calls. The window question's fixed cost is fifteen calls (two to resolve the window, two for the overlap records, eleven for a gene question's fan-out), and on that pass the model's gene-shaped spans ("ACMG", "dbVar", "ClinVar", "copy number variant") each cost a live confirmation call on top. Fixed in `c72b8a7`: a window question's entities are the window's genes, so the model's spans are not confirmed and the count is the same fifteen on every pass. Passes 6 to 8, on that fix: three of three, no refused call.
- The CFTR window answered six of six, 14 to 20 seconds, and the live runs found the ordering defect: on passes 1 to 3 the first resolved gene was LOC111674463, a regulatory locus that starts before CFTR, so the literature, OMIM and gene summary followed the locus and the answer had no literature sources at all (L3 0). Fixed in `e477077`: named genes lead. Passes 4 to 6 resolve CFTR first, with CFTR-AS1 and CFTR-AS2 beside it, and the sources come from all three layers.
- The window with no assembly named was answered with the assembly question on six of six passes, in 3 to 6 seconds, with no search issued: "These coordinates could be on GRCh38 or GRCh37, and the two put different genes under the same numbers. Add the assembly to the question, for example "on GRCh38", and I will search." The run client files it as a refusal because the clarification path uses the refuse outcome, as item 7.5's clarifying question does; the answer text is the question.
- Zero rate-limit signals across the twenty runs.

What the live runs changed, in the terms of the person asking: a window over CFTR now gives them CFTR's literature rather than a regulatory fragment's, and a window question no longer turns into a citation-less refusal on the pass where the model guesses more.

CI did not run on any of tonight's pushes, for the billing reason recorded in the plan; the four gates were run locally with CI's own commands before each push (`ruff check` over the whole repository, `isort` per gate 2, the full unit suite), and one process slip is recorded in `LEARNINGS.md`: a commit went out with a new test arm red because the shell chain gated on a pipe's exit code, caught within the minute and fixed as its own commit.

## Limits, said plainly

- Gene resolution from coordinates is GRCh38-only, because Entrez Gene's positions are on the current annotation. A GRCh37 window gets the overlap records, which are placement-checked on GRCh37, and the genes those records name in their own fields; it does not get a graph search of its own.
- A GRCh38 window with no gene under it still ends where it ended before: Think binds nothing and the answer asks for a name. Rare, and recorded rather than hidden.
- The overlap lists are capped at five rows per call in the answer, as every breadth result is, with the totals disclosed. A window over BRCA1 has thousands of overlapping records and no answer can list them; what the person gets is the count and the first records, each linked.
- The other two never-answering shapes in the same fix-plan item, an isolate description and a BioProject accession, are not touched here.

## Method and evidence

| File | What it is |
|---|---|
| `plan.md` | The contract and the decomposition, written before the work |
| `probes.md`, `probe_gene_window.py`, `probe_overlap_window.py` | The live NCBI probes, re-runnable from the repository root |
| `run_windows.py` | The live runs of the two questions that are not golden rows, through the consistency run's own client |
| `runs.jsonl`, `raw/` | The twenty live verification runs, written first as they end, and every event but tokens of each |
| `summarize_windows.py` | The table above, computed from the two files |
