# Learnings

Problems encountered and solutions implemented during development. Each entry captures what went wrong, why, and how it was fixed so the same mistake is not repeated.

## Gate 1: MedGen pipeline on real data (2026-04-14)

### Problem: parse_pubmed_links and parse_hpo_omim returned 0 edges

Root cause: both parsers split lines on tab (`\t`), but the real MedGen FTP files are pipe-delimited (`|`). The test fixtures also used tabs, so unit tests passed while real data produced zero results.

Why it happened: the builder agent assumed tab-separated based on the `.txt.gz` extension and the prompt saying "tab-separated." The actual files use pipe delimiters like all other MedGen RRF-format files.

Fix: changed `line.split("\t")` to `line.split("|")` in both parsers. Updated test fixtures to use pipe-delimited format matching real files.

Lesson: always check a sample of the real FTP file format before writing a parser. The file extension and documentation may not match the actual delimiter. A 5-second `zcat file.gz | head -3` would have caught this before writing any code.

### Problem: parse_pubmed_links used wrong column index for PMID

Root cause: the parser assumed columns were `UID\tPMID` (two columns), but the real format is `#UID|CUI|NAME|PMID|` (four columns). PMID is at index 3, not index 1.

Fix: updated column indices and used CUI (column 1) as the subject identifier instead of UID, since CUI is the standard MedGen concept identifier.

Lesson: same root cause as above. Read the actual file header before hardcoding column positions.

### Problem: parse_hpo_omim used wrong column indices

Root cause: assumed `CUI|MedGenName|HPO_ID|OMIM_ID|...` but real format is `#OMIM_CUI|MIM_number|OMIM_name|relationship|HPO_CUI|HPO_ID|...`. HPO_ID is at index 5, OMIM (MIM_number) is at index 1.

Fix: updated column indices to match real file header.

### Problem: pyproject.toml build-backend was invalid

Root cause: `build-backend = "setuptools.backends._legacy:_Backend"` does not exist. Should be `"setuptools.build_meta"`.

Fix: corrected the build-backend string. Editable install now works, though CLI entry points still need `PYTHONPATH` due to the hyphenated directory name mapping issue with setuptools editable mode.

Lesson: test `pip install -e .` early, not after all code is written.

## Gate 1: Gene pipeline on real data (2026-04-14)

### Problem: gene_refseq_uniprotkb_collab.gz has no GeneID column

Root cause: the parser expected a `GeneID` column in `gene_refseq_uniprotkb_collab.gz`, but the real file has columns `#NCBI_protein_accession|UniProtKB_protein_accession|NCBI_tax_id|UniProtKB_tax_id|method`. It maps RefSeq protein accessions to UniProt accessions, not gene IDs to UniProt.

Impact: non-blocking. UniProt xrefs on gene nodes are a nice-to-have, not required. The pipeline completed with 0 UniProt enrichments but all other data is correct.

Fix needed: to use this file, we would need a second lookup (RefSeq protein accession to GeneID via gene2refseq). Alternatively, skip this file and get UniProt xrefs from the dbXrefs column in gene_info (which already provides some). Low priority.

Lesson: verify the actual column names of every FTP file, not just the delimiter. The file name suggests gene-to-UniProt mapping but the actual content is protein-to-protein.

## Gate 1: ClinVar pipeline on real data (2026-04-14)

### Observation: 2,337 duplicate variant nodes

Not a bug. ClinVar variant_summary has some VariationIDs that appear in multiple rows even after filtering to GRCh38. The dedup keeps the first occurrence. Low enough count (0.05% of 4.4M) to be acceptable.

### Problem: Gene pipeline ran with --tax-id 9606 (human only) instead of all organisms

Root cause: the Gate 1 test run used `gene-etl --tax-id 9606` for speed, but the plan requires all data from all organisms. This produced 193K human genes instead of the full ~67.5M.

Fix: rerun `gene-etl --skip-download` without the `--tax-id` flag to parse all organisms from the already-cached FTP files.

Lesson: "test run" and "production run" are different. Gate 1 should validate the full dataset, not a filtered subset. The --tax-id flag is useful for development testing, but the gate should run the real thing.

### Problem: Gene pipeline killed during export of 278M edges (OOM)

Root cause: the pipeline collects all 278M edge dicts in a Python list before passing them to `export_kgx()`, which then iterates the full list to write TSV. At ~500 bytes per dict, 278M edges is ~130GB of memory. The process was killed by the OS OOM killer.

The nodes (67M) also hit this but survived at ~30GB because the nodes are smaller dicts. The edges are 4x more numerous and couldn't fit.

Fix needed: refactor the Gene pipeline to write edges to disk incrementally per parser instead of accumulating all edges in memory. Each parser (gene2go: 117M, gene2pubmed: 76M, orthologs: 17M, taxon: 67M) should write directly to the edges.tsv file in append mode, or the pipeline should stream edges through a generator instead of materializing the full list.

Lesson: 278M dicts in memory is not feasible. Any pipeline producing more than ~10M edges should stream to disk. The architecture assumption of "collect all, then export" works for MedGen (48M edges, smaller dicts) but fails at Gene scale. This was predictable from the execution plan's graph scale table (134M Gene edges estimated).

## Architecture discussions (2026-04-14)

### Observation: Gene count is 67.5M, not 94M as estimated

The execution plan estimated ~94M genes based on early planning docs. The actual gene_info.gz file has 67,536,236 data rows. Verified against NCBI Gene Entrez search (`all[filter]`), which reports 67,736,810 records. The ~200K difference is likely records added after the FTP snapshot date. The 94M figure was never accurate.

All rows parsed, 0 skipped. We have all the data.

Lesson: verify estimated counts against the live NCBI database (`all[filter]` search on the database homepage) before and after each gate run.

### Understanding: what is Apache AGE and why we use it

AGE (A Graph Extension) is a free extension for PostgreSQL that adds graph query support. It lets you store nodes and edges and query them with Cypher (the same language Neo4j uses), but the data lives on disk using PostgreSQL's storage engine instead of requiring everything in RAM.

Why it matters for this project: our graph has 1.4 billion nodes (mostly dbSNP variants). Neo4j would need 256GB+ RAM for that ($500+/month in cloud). AGE handles it with 16GB RAM + 500GB disk because PostgreSQL is disk-based. Cost drops to ~$25-30/month on a Hetzner VPS.

AGE is not a separate database. It is PostgreSQL with a graph layer added. Same connection, same drivers (psycopg2), same backup tools (pg_dump). You just wrap Cypher in a SQL function call.

### Understanding: ClinVar and dbSNP use different ID spaces, no schema conflict

ClinVar nodes use `ClinVar:{VariationID}` (one per clinical submission). dbSNP nodes use `dbSNP:rs{RSID}` (one per genomic position). Both are `biolink:SequenceVariant` in the schema, but they are separate nodes with different IDs. No conflict.

The merge step (Phase 3.1) connects them via the RS# column in ClinVar's variant_summary. When a ClinVar variant has an RS number, an `exact_match` edge links it to the corresponding dbSNP node. This lets you traverse from clinical significance (ClinVar) to population frequency (dbSNP) through the same variant.

### Decision: reorder phases to solve the dbSNP disk problem

Problem: dbSNP KGX output is 200-400GB. With the other 5 databases' KGX files on disk (~80-120GB), total exceeds the 434GB available on /export.

Solution: load the first 5 databases into AGE before building the dbSNP pipeline. Once loaded, delete the KGX intermediates (~80-120GB freed). Then process dbSNP incrementally per chromosome, loading directly into AGE. The full dbSNP KGX never exists on disk at once.

This changed the phase order from 1-2-3-4 to 1-2-4-3.

### Decision: KGX files are intermediates, graph database is the end target

Raw KGX files (nodes.tsv + edges.tsv) are intermediate artifacts. They exist only to transport data from the ETL pipelines into PostgreSQL + AGE. Once loaded, they can be deleted. If ever needed again, they can be regenerated from the FTP cache.

This means no cloud backup of KGX files is needed. The graph database is the authoritative copy.

### Understanding: deployment cost for the full system

Layer 1 (knowledge graph) is the only component that needs hosting. Layers 2 and 3 call free external APIs (NCBI ELink/EFetch, PubTator3, LitVar2, ClinicalTrials.gov) at query time. System 3 (search agent, UI) lives in a separate repo with its own hosting.

Estimated cost for the full system:
- Layer 1 AGE database (Hetzner CX41 + volume): ~$25-30/month
- System 3 search agent + API: ~$10-20/month (separate VPS or Railway)
- System 3 UI: ~$0-10/month (Vercel/Netlify)
- Layers 2 + 3 API calls: $0 (NCBI APIs are free with API key)
- Total: ~$35-60/month for a 1.4B node knowledge graph with search agent
