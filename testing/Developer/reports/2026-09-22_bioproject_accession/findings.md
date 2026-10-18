# The BioProject accession: a project's samples, runs and assemblies from the accession alone

Fix-plan item 2 as it stood on the night of 2026-09-22, the second of the two question shapes that never answered. "For BioProject PRJNA31257, list the BioSamples, the SRA runs and any genome assemblies, and tell me how to retrieve each" (G-007) ended, on every pass of the consistency run, with a request to name a gene or variant, because the graph holds no projects, samples, runs or assemblies and nothing recognised the accession. This folder holds the live probes that settled the design, the plan and the module worker's contract, and the live runs after the build.

## Table of contents

- [Verdict](#verdict)
- [What the person feels](#what-the-person-feels)
- [Method](#method)
- [What the probes settled](#what-the-probes-settled)
- [What was built](#what-was-built)
- [The live runs](#the-live-runs)
- [Method and evidence](#method-and-evidence)

## Verdict

The accession shape answers. Three of three live runs of the golden question answered with the project record (the Human Genome Project), its BioSample, its SRA run and its GRCh38.p14 assembly, four sources each cited to the NCBI page the record can be fetched from, a fixed eight Layer 2 calls on every pass (one search, three links, four summaries), in 15 to 27 seconds. An accession NCBI does not have was told so on both runs: "BioProject PRJNA999999999 was not found in NCBI. Check the accession and ask again", one call, no request for a gene.

The live runs found two things the offline arms could not, both fixed the same night and re-run below:

- The SRA run was shown as NCBI's own markup, `<Run acc="SRR9496657" total_spots="118" .../>`, where a person wants SRR9496657 (`d882856`).
- The BioSample question resolved its record and its 100 SRA runs and then answered "which gene, variant or condition do you mean?", because "come from it" tripped the follow-up clarification, which knew resolved genes and remembered entities as subjects but not a resolved accession (`649750c`).
After both fixes, the BioSample question answered 2 of 2 with its record and five of its runs as accessions, five calls, 9 to 21 seconds, and the golden question answered again with the run shown as SRR9496657.

## What the person feels

Someone who types a project accession has already done the hard part: they know exactly which record they mean. Being told to "name the gene or variant you mean" reads as the product not knowing what a BioProject is. What they want is the record, the samples, runs and assemblies under it, and a link to each so they can fetch it themselves. And when they mistype the accession, they want to be told it was not found, not asked for a gene.

## Method

The same shape as the coordinate range the night before: the reasoning model wrote the plan and each worker's contract, a probe worker measured NCBI live before anything was designed, a module worker built the pure module and its tests, and the planner wrote the wiring into Think, Plan, Write and Act with its own tests. Two workers never wrote the same file, and nothing was assembled until the module worker returned.

| Step | Who | Output |
|---|---|---|
| Nine live NCBI requests on PRJNA31257 | The probe worker, earlier in the evening | `probes.md`, `probe_bioproject.py` |
| The pure module: recognise an accession, build the search and link inputs, plan the summaries, word the disclosure | The module worker | `src/system_03_search_agent/core/accession.py`, 59 arms in `tests/system_03_search_agent/core/test_accession.py`, a debugging-guide row |
| The wiring: resolve in Think, plan in Plan, the refusal branch in Write, the row shaping in Act | The planner | `core/graph.py`, `core/state.py`, 10 arms in `tests/system_03_search_agent/core/test_accession_wiring.py` |
| Live runs on develop | The planner, after the deploy | `runs.jsonl`, `raw/`, the tables below |

## What the probes settled

Nine requests, all HTTP 200, none typed from memory. The full record is `probes.md`.

- ESearch on `db=bioproject` with the plain accession as the whole term finds the record (uid 31257) in 0.2 seconds. The documented accession field returns nothing: `PRJNA31257[ACCN]` is a valid empty search, count 0, for a record that exists. The module sends the plain term, and a lookup that read an `[ACCN]` empty as "not found" would have been wrong.
- ESummary on the record carries the fields a person recognises it by: `project_acc`, `project_title` ("The Human Genome Project, currently maintained by the Genome Reference Consortium"), `project_type`, `project_data_type`, `organism_name`, `registration_date`.
- ELink from bioproject to biosample, sra and assembly returns one id each for this project, under the link names `bioproject_biosample`, `bioproject_sra` and `bioproject_assembly` beside their `_all` and `_sp` variants, so the same id arrives under more than one link name and must be de-duplicated.
- ESummary on each linked id returns the fields the answer leads with: a BioSample's `accession` and `title`, an SRA record's `runs` string (which carries the run accession) and `createdate`, an assembly's `assemblyname` and `assemblyaccession`.
- The product's own `ncbi_efetch` tool can make every one of these calls today, with its search, summary and link actions and its record pages `bioproject/{id}`, `biosample/{id}`, `sra/{id}` and `assembly/{id}`; no new tool and no new transport.

## What was built

Decided from the user's chair, and recorded in `DECISIONS.md` dated 2026-09-22.

- An accession is recognised by a fixed rule: BioProject (`PRJNA`, `PRJEB`, `PRJDB`), BioSample (`SAMN`, `SAME`, `SAMD`), the SRA run, experiment, sample and study prefixes, and assembly (`GCF_`, `GCA_`). The leftmost one in the question wins.
- Think resolves it live: one ESearch on the record's own database, then one ELink per linked database. A failure anywhere leaves what was resolved so far, never a crashed turn. The model's own spans are not confirmed on such a question, so its call count is fixed, the rule the coordinate window took the night before.
- Plan plans the record's summary and then the summaries of what it links to, at most ten ids per database, and no graph call, since the graph holds no such records. Every summary is an ordinary NCBI call on the existing tool, cited to the record's own NCBI page.
- Write's refusal branch used to assume the plan's first call was a graph call; it now checks.
- An accession NCBI does not have is answered as its own clarification: "PRJNA999999999 was not found in NCBI. Check the accession and ask again."
- The Think narrative discloses what was found: "PRJNA31257 links to 1 BioSample, 1 SRA record and 1 assembly".

## The live runs

Round 1, on develop at `693c020`, one worker, laptop kept awake, read by `summarize_accession.py`:

| id | pass | outcome | seconds | trust | calls | sources by database | records named | not found? | entities note? |
|---|---|---|---|---|---|---|---|---|---|
| G-007 | 1 | answered | 26.6 | ask | 8 | assembly 1, bioproject 1, biosample 1, sra 1 | an SRR run, Human Genome Project | no | no |
| G-007 | 2 | answered | 15.1 | ask | 8 | assembly 1, bioproject 1, biosample 1, sra 1 | an SRR run, Human Genome Project | no | no |
| G-007 | 3 | answered | 14.9 | ask | 8 | assembly 1, bioproject 1, biosample 1, sra 1 | an SRR run, Human Genome Project | no | no |
| R-BIOSAMPLE | 1 | refused_no_evidence | 4.5 | refuse | 3 | - | - | no | no |
| R-BIOSAMPLE | 2 | refused_no_evidence | 5.6 | refuse | 3 | - | - | no | no |
| R-UNKNOWN-ACCESSION | 1 | refused_no_evidence | 11.8 | refuse | 1 | - | - | yes | no |
| R-UNKNOWN-ACCESSION | 2 | refused_no_evidence | 3.3 | refuse | 1 | - | - | yes | no |

The questions: G-007 is the golden row; R-UNKNOWN-ACCESSION is "What is in BioProject PRJNA999999999?", whose right answer is the not-found line the "not found?" column reads; R-BIOSAMPLE is "What is BioSample SAMN12121739 and which SRA runs and assemblies come from it?". The BioSample refusals were the clarification fixed in `649750c`, and its two Think narratives both carried the disclosure "BioSample SAMN12121739 links to 100 SRA runs and no assemblies", so the record and its links had resolved before the ask.

Round 2, on develop at `649750c` after both fixes, in `round2/`:

| id | pass | outcome | seconds | trust | calls | sources by database | records named | not found? | entities note? |
|---|---|---|---|---|---|---|---|---|---|
| G-007 | 1 | answered | 13.4 | ask | 8 | assembly 1, bioproject 1, biosample 1, sra 1 | an SRR run, Human Genome Project | no | no |
| R-BIOSAMPLE | 1 | answered | 20.6 | answer | 5 | biosample 1, sra 5 | SAMN12121739, an SRR run | no | no |
| R-BIOSAMPLE | 2 | answered | 8.8 | answer | 5 | biosample 1, sra 5 | SAMN12121739, an SRR run | no | no |

The BioSample answer reads "BioSample SAMN12121739 is a sample record titled 'Sample from Homo sapiens'" and lists SRR9504670 to SRR9504674, each cited to its SRA page; the golden question's run now reads "sra runs: SRR9496657". One residual, named rather than hidden: the sample links to 100 runs, the plan summarises ten and the answer lists five, and the answer does not yet say there are 100, though the Think narrative on the stream does ("links to 100 SRA runs and no assemblies").

The guard retest that ran in the same chain (the rs334 and GEO questions, twice each) is in `../2026-09-22_call_ceiling/guard_retest/`: four answers, none carrying the "does not address the following entities" note.

## Method and evidence

| File | What it is |
|---|---|
| `probes.md`, `probe_bioproject.py` | The nine live requests and what each returned |
| `runs.jsonl`, `raw/` | The live runs on develop, written as they end, every event but tokens |
| `run_accession_extra.py`, `summarize_accession.py` | The two questions the golden set does not carry, and the tables above |
| `src/system_03_search_agent/core/accession.py` | The pure module, no network and no model |
| `tests/system_03_search_agent/core/test_accession.py`, `test_accession_wiring.py` | The 59 module arms and the 10 wiring arms |
