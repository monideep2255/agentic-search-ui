# Fix-plan item 1, the coordinate range: the plan before the work

Written before any code, per `goal-contracts` and `plan-then-fan-out`. The
product owner chose this item on 2026-09-22 and asked for the work to be
planned by the reasoning model and executed by cheaper workers in parallel
where the parts are independent. This file is the contract; `findings.md`
beside it will hold what was measured and what shipped.

## Table of contents

- [What the person gets](#what-the-person-gets)
- [Goal contract](#goal-contract)
- [Design, decided from the user's chair](#design-decided-from-the-users-chair)
- [Decomposition and who does what](#decomposition-and-who-does-what)
- [What is deliberately not in this item](#what-is-deliberately-not-in-this-item)

## What the person gets

Today, "What ACMG-relevant evidence is available for a copy number variant
spanning chr17:43,044,295-43,125,364 on GRCh38?" is answered with a request to
name a gene, variant, disease or organism. Not knowing the gene is the reason
for asking. After this item, the answer names the genes under the window
(BRCA1, for that window), lists the dbVar and ClinVar records that genuinely
overlap it on the named assembly, each cited to its NCBI page, and carries the
genes' disease associations from the graph, the literature and OMIM the way any
gene question does. It classifies nothing; the guardrail already refuses a
pathogenicity verdict. A question that gives coordinates and no assembly is
asked which assembly, because GRCh37 and GRCh38 put different genes under the
same numbers, and guessing would be a confident wrong answer.

## Goal contract

- Done when: on develop, the golden coordinate question (G-001) answers three
  of three passes with NCBIGene:672 resolved without the gene being named,
  dbVar and ClinVar records overlapping the window among the sources, the
  BRCA1 gene page among the sources, no errored graph call, and no lost-search
  line; a second window on another chromosome answers with its own genes; a
  window with no assembly named is answered with the assembly question; the
  unit suite, ruff over the whole repository and isort per gate 2 are green;
  the debugging guide has a row for the new module and its manifest is
  regenerated in the same commit.
- Verify: `run_consistency.py` from the consistency run against develop, three
  passes of G-001 and of the second window; a capture read for the assembly
  question; the unit suite; the two lint gates; `check_doc_drift.py`.
- Output: `src/system_03_search_agent/core/coordinate_window.py` and its
  tests; the wiring in `core/graph.py` and `core/state.py` with wiring tests;
  this folder's `findings.md`, probes and live runs; the fix plan, the shipped
  list, the continuation prompt, the Plan's revision history, the progress
  page and the counts.
- Constraints: no new tool and no new transport, the overlap action and the
  Gene search already exist on `ncbi_efetch`; every NCBI request in a probe at
  most one per second; the validator, the grounding gate and the guardrail
  untouched; no organism or assembly assumed silently; the per-query call
  ceiling of 20 respected (a window question adds two calls, dbVar and
  ClinVar, to a gene question's 14 to 16).
- Blocked-stop: if the live probe finds no Gene search term that returns the
  genes under a window, gene resolution from coordinates waits and only the
  overlap records ship, said plainly; if the overlap action fails live on the
  example window, stop and report.

## Design, decided from the user's chair

- Think recognises the window with a fixed rule, never the model:
  `chr17:43,044,295-43,125,364` with or without commas, with `chr` or
  `chromosome 17`, a hyphen, an en dash or "to" between the ends, and an
  assembly word (GRCh38, hg38, GRCh37, hg19, b37, b38). The rule runs beside
  the exact-identifier pre-pass, which stays local and synchronous as its gate
  arm requires; the window's own lookup is a separate awaited step.
- With GRCh38 named, Think resolves the genes under the window with one Gene
  ESearch on chromosome and base position and one ESummary, keeps only the
  records whose own genomic placement overlaps the window (the same discipline
  the overlap action applies, because Entrez range fields are not interval
  overlap), sorts them by position, keeps at most ten and says so when there
  were more, and adds each as a resolved entity with its symbol as the text so
  the rest of the pipeline treats the question as a gene question.
- With GRCh37 named, the dbVar and ClinVar overlap calls run (the action
  handles GRCh37 placements) and the genes come from those records; the Gene
  position search is GRCh38-only by NCBI's own annotation, so it is not issued
  and the answer says which assembly it used.
- With no assembly named, Think sets the clarifying question and nothing is
  searched.
- Plan adds the two overlap calls, ClinVar and dbVar, right after the
  question's own graph call so that under the call ceiling they are never the
  ones skipped, with purposes Act can route (`clinvar_overlap`,
  `dbvar_overlap`) and a field allowlist chosen from what the probe shows the
  records carry.
- Nothing in Write changes: the records become rows and citations through the
  same path every breadth result takes, capped and disclosed the same way.

## Decomposition and who does what

| Part | Who | Writes | Depends on |
|---|---|---|---|
| Live probes: the Gene search term for a window, the overlap action on the example window, the record fields | Sonnet worker, running | `probe_gene_window.py`, `probe_overlap_window.py`, `probes.md` in this folder | nothing |
| The pure module: parser, term builder, gene filter, overlap call planner, disclosure text, and its tests, plus the debugging guide row and manifest | Sonnet worker | `core/coordinate_window.py`, `tests/.../core/test_coordinate_window.py`, `docs/build/Debugging_guide.md`, the manifest | nothing; the term's field names sit in one constant the planner corrects if the probe disagrees |
| The wiring into Think, Plan and Act, the state field, the wiring tests | The planner (reasoning model), because Think and Plan carry invariants a bounded worker should not have to learn | `core/graph.py`, `core/state.py`, `tests/.../core/test_coordinate_window_wiring.py` | both workers |
| Live verification, findings, documentation, counts, commit | The planner | this folder, the plan documents | the wiring |

Two workers never write the same file; the planner writes nothing until both
return.

## What is deliberately not in this item

- An isolate description ("E. coli isolates carrying ESBL genes") and a
  BioProject accession, the other two never-answering shapes in the same fix
  plan item; each is its own day and its own tool path.
- Segmental duplications, deferred to the fast-follow with a UCSC source by
  the locked PRD.
- A window with no gene under it on GRCh38 still ends where it ends today, a
  request for a name; recorded as a limit rather than hidden.
