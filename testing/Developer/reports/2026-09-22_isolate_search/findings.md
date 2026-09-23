# The isolate search: which isolates of an organism carry a resistance gene, with an exact count

Fix-plan "Next, in order" item 1 as it stood at the close of 2026-09-22, the one golden question shape that still never answered. "What Escherichia coli isolates in Pathogen Detection carry extended-spectrum beta-lactamase genes?" (G-035) ended, on every pass of the consistency run, with a request to name a gene or variant, because nothing in the agent loop recognised an organism plus a gene family, and no mode of the pathogen tool searched isolates by a gene. This folder holds the live probe that settled the design, the pinned contract, the live runs after the build, and the two follow-ups the live runs found.

## Table of contents

- [Verdict](#verdict)
- [What the person feels](#what-the-person-feels)
- [Method](#method)
- [What the probe settled](#what-the-probe-settled)
- [What was built](#what-was-built)
- [The live runs](#the-live-runs)
- [What the live runs found](#what-the-live-runs-found)
- [What is left open](#what-is-left-open)
- [Method and evidence](#method-and-evidence)

## Verdict

The isolate shape answers. Five of five live passes of the golden question on develop answered in 19 to 28 seconds with 21 citations each: the first 20 E. coli isolates carrying a blaCTX-M gene, each in a two-column table with its full AMR genotype list beside its name, each cited to its Pathogen Detection isolate page by its BioSample accession, the organism cited to its NCBI Taxonomy record, and under the answer the sentence "Pathogen Detection lists 140,476 Escherichia coli isolates with these genes; the first 20 in the snapshot are shown". The count is exact: the tool reads the whole 521 MB metadata file to the end on every pass.

The seven extra questions behaved as `testing/Product/queries/Isolate_search_queries_and_workflow.md` expects: Salmonella ESBL 20,307 isolates, blaCTX-M-15 alone 2,678 (never a neighbouring allele), Klebsiella carbapenemase genes 88,025, Listeria blaKPC a true zero stated as zero rather than a refusal, an organism the product cannot search asked "which organism" with five it covers named, an organism with no gene asked "which gene", and the shortest phrasing, "ESBL E. coli isolates?", read exactly as the full question.

## What the person feels

Someone typing this is an outbreak or AMR researcher. Before today the product asked them for a gene name, which read as not knowing what an isolate is. Now they get isolates they can open, each with its resistance genes and a link, and an honest statement of how many there are and how many were shown. Where the family name is loose, the answer says which prefixes it searched and which it deliberately did not: for "ESBL", the blaCTX-M family only, because 279,100 of 584,433 E. coli isolates carry a blaTEM allele and nearly all of those are the narrow-spectrum blaTEM-1, which is not an ESBL. A confident wrong record is worse than a missing one.

## Method

The same shape as the coordinate range and the accession: a probe worker measured the FTP tree live before anything was designed, the wire contract was pinned in `contract.md`, a tool worker built the new mode and its tests against it, a document worker wrote the test queries from the user's chair, and the planner wired Think, Plan, Act and Write with its own tests. No two workers wrote the same file.

| Step | Who | Output |
|---|---|---|
| The FTP tree, live: folders, snapshot, file size, columns, gene spelling, scan time | The probe worker | `probes.md`, `probe_ecoli_metadata.py` |
| The contract every worker built against | The planner | `contract.md` |
| A third mode, `isolate_search`, on the pathogen tool, the predicate scan on the transport, 51 new arms and one live premise arm | The tool worker | `tools/pathogen_detection.py`, `pathogen_detection_schemas.py`, `pathogen_ftp_transport.py` and their tests |
| The test queries and the product owner's workflow | The document worker | `testing/Product/queries/Isolate_search_queries_and_workflow.md` |
| The pure module, the wiring, 44 arms, the debugging guide | The planner | `core/isolate_search.py`, `core/graph.py`, `core/state.py`, `test_isolate_search.py`, `test_isolate_search_wiring.py` |
| Live runs on develop, three deploys | The planner | `golden/`, `raw/`, `round2/`, the tables below |

## What the probe settled

- The FTP root lists 107 taxon folders; E. coli lives under `Escherichia_coli_Shigella`, and the complete snapshot (`PDG000000004.6314`) resolved in under two seconds.
- The metadata file is 521 MB, 584,433 rows, 67 columns; the AMR column is `AMR_genotypes`, comma-joined, spelled `blaTEM-1`, `aph(3'')-Ib`, `tet(A)`, with no suffix decorations.
- A full scan with a per-row predicate finished in 17.7 seconds at a 120-second budget and reached the end of the file at every budget tried, so counting every match is affordable and the person gets a true total rather than "more exist".
- The probe's own first ESBL pattern matched 279,100 rows, every early hit through `blaTEM-`. That is the measurement behind the blaCTX-M-only decision.

## What was built

Decided from the user's chair and recorded in `DECISIONS.md` dated 2026-09-22.

- A third mode on the tool, `isolate_search`: taxon folder, one to ten gene prefixes, at most 100 isolates kept. It streams the whole metadata file through a boundary-aware prefix match (`blaCTX-M-15` never matches `blaCTX-M-155`, `blaOXA-48` never `blaOXA-484`, `mcr-1` does match `mcr-1.1`), counts every match, keeps the first `max_isolates`, and reports `total_available`, `rows_scanned` and `scan_complete`. A deadline cut with matches is `ok` and `truncated`, so the answer says "at least".
- A fixed rule in `core/isolate_search.py` recognises the shape: an isolate word, an organism from a table of twenty (each folder read from the FTP root, each taxonomy id verified live), and a gene family word (ESBL, carbapenemase, colistin or mcr, methicillin or MRSA, vancomycin or VRE) or an explicit gene token. A question naming one isolate by a `PDT` or `PDS` identifier stays on the lookup path.
- Think resolves the organism to `NCBITaxon:<id>` with no call and does not confirm the model's spans, so the count is the same on every pass. Plan plans the isolate search then the organism's Taxonomy summary and no graph call, since the graph holds no isolates. Act shapes the kept isolates into rows led by the strain name, capped at 20. Write renders them as an "Isolates and their AMR genes" table, cites each through the tool's own builder, and puts the count sentence under the answer.
- Two additive contract changes beyond the tool: `taxonomy` on `ncbi_efetch`'s summary enum, and the `Pathogen Detection isolate` row type in the answer layout's table columns.

## The live runs

Round 1, the golden question on develop at `24305f0`, one worker, laptop kept awake:

| id | pass | outcome | seconds | trust | citations | count sentence | model summary grounded |
|---|---|---|---|---|---|---|---|
| G-035 | 1 | answered | 26.4 | answer | 21 | 140,476 E. coli isolates; the first 20 shown | yes |
| G-035 | 2 | answered | 19.3 | answer | 21 | 140,476 | yes |
| G-035 | 3 | answered | 27.9 | ask | 21 | 140,476 | no, the code-built listing carried the answer |

Round 1, the seven extra questions on develop at `24305f0`, two passes each (the last three ran after the API had redeployed at `286bb49`, which changed nothing in Think):

| id | question | passes | outcome | seconds | count sentence |
|---|---|---|---|---|---|
| R-SALMONELLA-ESBL | Which Salmonella isolates in Pathogen Detection carry ESBL genes? | 2 | answered, 21 citations each | 29.9, 33.8 | 20,307 Salmonella isolates; the first 20 shown |
| R-CTXM15 | Which Salmonella isolates carry blaCTX-M-15? | 2 | answered, 21 citations each | 31.5, 41.7 | 2,678 |
| R-KLEBSIELLA-CARBAPENEMASE | Which Klebsiella isolates in Pathogen Detection carry carbapenemase genes? | 2 | answered, 21 citations each | 20.9, 20.7 | 88,025 |
| R-LISTERIA-ZERO | Which Listeria isolates in Pathogen Detection carry blaKPC? | 2 | answered, the Taxonomy record cited, trust `ask` | 14.5, 17.5 | "lists 0 Listeria isolates with these genes, all shown" |
| R-NO-ORGANISM | Which tomato isolates in Pathogen Detection carry resistance genes? | 2 | the GENERIC refusal, "name a gene, variant, disease or organism" | 26.8, 6.3 | none; fixed in round 2 |
| R-NO-GENE | Which E. coli isolates are in Pathogen Detection? | 2 | the shape's own question: which resistance gene or family | 6.5, 6.8 | none, by design |
| R-TERSE | ESBL E. coli isolates? | 2 | answered, 21 citations each | 28.0, 38.2 | 140,476 |

Round 2, on develop at `f96c780` after both follow-ups, in `golden/round2/` and `round2/`:

| id | pass | outcome | seconds | what changed |
|---|---|---|---|---|
| G-035 | 1 | answered, 21 citations, trust `answer` | 24.6 | every citation's identity is the BioSample accession |
| G-035 | 2 | answered, 21 citations, trust `ask` | 26.5 | same |
| G-035, token capture | 1 | answered | 30.2 | one `table_header` ["Isolate", "AMR genes"] and 20 `table_row` tokens, the first reading C236-11 with acrF, aph(3'')-Ib, aph(6)-Id, blaCTX-M-15, blaEC, blaTEM-1, dfrA7, gyrA_S83A=POINT, mdtM, sul1, sul2, tet(A) |
| R-NO-ORGANISM | 1, 2 | "Pathogen Detection is searched one organism at a time. Which organism do you mean? For example Escherichia coli, Salmonella, Listeria monocytogenes, Klebsiella pneumoniae or Campylobacter." | 5.4, 11.7 | the shape's own question, not the generic refusal |

## What the live runs found

Three things the offline arms could not, each fixed the same night and re-run above:

- The listing showed each isolate's name alone, so the genes the person asked about were nowhere on screen. The isolate rows now render as a two-column table from the record's own genotype list (`286bb49`). The consistency runner drops token events, so this needed `capture_tokens.py` to see; it is now in the folder for the next shape that renders a table.
- Every citation's identity read "unknown", because the pathogen tool was not among the tools routed through their own citation builders. It is now, and the identity is the BioSample accession (`286bb49`).
- An organism the product cannot search got the generic "name a gene, variant, disease or organism" rather than the shape's "which organism", because "resistance genes" named no gene family. A resistance word with no family behind it now marks the shape (`f96c780`).

One thing the mutation harness found before anything shipped: competency question Q5, "For Salmonella isolate PDT000123456, what SNP cluster is it in, what AMR genes does it carry", was taken by the shape and would have asked which gene. Its P1 arm went vacuous on Q5 because the shape skipped the model's span confirmation, which is exactly the shape of failure that arm exists to catch; a PDT or PDS identifier now keeps a question off this shape.

## What is left open

- The model's written summary fails grounding on most passes of this shape (the ESBL, blaCTX-M-15, Klebsiella, Listeria and terse questions all showed the structured-fallback note), so the code-built table and the count sentence carry the answer and the prose above them is one sentence. Honest, and thin. It is the same grounding property recorded on 2026-09-21: the gate permits quoting and forbids explaining, and a strain name is not something a model can restate.
- The golden row's `must_cite` names `https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=562`; the product cites NCBI's own record page, `https://www.ncbi.nlm.nih.gov/taxonomy/562`, so the instrument reads 1 of 2 must-cite hits on every pass. The organism IS cited; the row's URL form is the older browser address. A golden row edit is the product owner's, per `docs/build/Golden_dataset_method.md`.
- A year filter, or any filter beyond the gene prefix, is not built, and a follow-up does not carry an isolate search forward. `testing/Product/queries/Isolate_search_queries_and_workflow.md` test 9 states the honest current behaviour.
- The stable prompt prefix changed bytes at this deploy, since the tool's input schema gained a branch; one cold cache, no code change, and the cache test suite is green.
- Every Pathogen Detection isolate page is a client-rendered app whose search fragment was not verified to pre-populate, the same scope the tool's build stopped at (F-3.5-04).

## Method and evidence

| File | What it is |
|---|---|
| `probes.md`, `probe_ecoli_metadata.py` | The live measurement of the FTP tree that settled the design |
| `contract.md` | The wire contract the three workers built against |
| `golden/runs.jsonl`, `golden/raw/` | Round 1 of the golden question, three passes |
| `runs.jsonl`, `raw/` | Round 1 of the seven extra questions, two passes each |
| `golden/round2/`, `round2/` | Round 2 after the follow-ups: the golden question twice, the organism question twice, and `tokens_G-035.json`, one run with every token kept |
| `run_isolate_extra.py`, `capture_tokens.py` | The two instruments: the extra questions through the consistency runner's client, and one run with token events kept |
| `src/system_03_search_agent/core/isolate_search.py` | The pure module, no network and no model |
| `tests/system_03_search_agent/core/test_isolate_search.py`, `test_isolate_search_wiring.py` | The 32 module arms and the 13 wiring arms |
| `tests/system_03_search_agent/tools/test_pathogen_detection*.py`, `test_pathogen_ftp_transport.py` | The tool worker's 51 arms and the live premise arm |
