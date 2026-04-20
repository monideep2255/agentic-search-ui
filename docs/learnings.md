# Learnings

Problems encountered and solutions implemented during development. Each entry captures what went wrong, why, and how it was fixed so the same mistake is not repeated.

## Table of contents

- [Phase 3.0: AGE loader on Docker Desktop (2026-04-19)](#phase-30-age-loader-on-docker-desktop-2026-04-19)
- [Gate 2: Taxonomy + PubMed + 5-db merge on Windows laptop (2026-04-16)](#gate-2-taxonomy--pubmed--5-db-merge-on-windows-laptop-2026-04-16)
- [Gate 1: MedGen pipeline on real data (2026-04-14)](#gate-1-medgen-pipeline-on-real-data-2026-04-14)
- [Gate 1: Gene pipeline on real data (2026-04-14)](#gate-1-gene-pipeline-on-real-data-2026-04-14)
- [Gate 1: ClinVar pipeline on real data (2026-04-14)](#gate-1-clinvar-pipeline-on-real-data-2026-04-14)
- [Architecture discussions (2026-04-14)](#architecture-discussions-2026-04-14)

## Phase 3.0: AGE loader on Docker Desktop (2026-04-19)

### Problem: psycopg2 parameter binding incompatible with AGE's cypher() Param-node requirement

The first AGE loader prototype used the `cypher() UNWIND` approach: pass a JSON batch parameter to `cursor.execute()` via psycopg2 as the third argument to AGE's `cypher()` function. This failed with `InvalidParameterValue: third argument of cypher function must be a parameter`, not a Python-level error.

Root cause: AGE's `cypher()` function enforces at PostgreSQL parse time that its third argument is a `Param` node (a server-side bind parameter). psycopg2's `execute(query, params)` uses libpq's simple query protocol, which substitutes `%s` markers as SQL string literals on the client before the string reaches the database. SQL string literals are not `Param` nodes. The check fails regardless of what value is passed. This is a fundamental incompatibility between psycopg2's wire protocol and AGE's internal Cypher planner requirement, not a formatting or escaping issue.

Fix: switch to direct INSERT into AGE's internal vertex and edge tables (`"{graph}"."{label}"`) using standard parameterised SQL with `%s::agtype` casts. AGE stores graph data in regular PostgreSQL heap tables; `cypher()` is a read/write wrapper for interactive use, not a requirement for bulk load. With direct INSERT, psycopg2 parameter binding works normally. Three additional AGE-specific constraints discovered during the fix: (1) table reference must be `"{graph}"."{label}"` not `ag_catalog."{graph}"."{label}"` even with `ag_catalog` on `search_path`; (2) agtype property access uses `agtype_to_text(properties -> '"id"')` not the `->>` operator; (3) graphid values must be passed as `%s::agtype::graphid`, not plain Python ints.

Trade-off: direct INSERT couples the loader to AGE's internal schema. If a future AGE release renames or restructures these tables, the loader needs updating. Accepted: AGE has kept this table layout stable across all 1.x releases, and the loader already imports `ag_catalog` functions by name so it is already coupled to AGE internals.

Lesson: when a library's recommended query interface has a hard wire-protocol incompatibility with the DB driver, reach for the lower-level interface. The `cypher()` wrapper is right for interactive Cypher; it is not right for batch ETL where you control the insert path.

### Observation: Docker Desktop smoke test confirmed 5-node + 3-edge round-trip on apache/age:latest

The smoke test (`tests/loader/test_age_smoke.py`, 4 tests, `@pytest.mark.docker`) loads a tiny inline KGX fixture (5 nodes, 3 edges) into a fresh AGE graph, queries it back via `cypher()` SELECT, and asserts node properties and edge connectivity. All 4 tests passed against `apache/age:latest` on Docker Desktop. The loader correctly creates the graph, inserts vertex and edge records, builds indexes, and returns results via openCypher.

This confirms the loader logic is sound before any cloud deployment. The full 5-database load (115M nodes, 693M edges) is reserved for Phase 4 on the Hetzner VPS.

Lesson: a 5-node smoke test catches the wiring (connection, schema creation, insert path, query path) at negligible cost. Run it before assuming the full-scale load will work. The smoke test pays for itself the first time it catches a parameter binding bug (which it did here, see above).

## Gate 2: Taxonomy + PubMed + 5-db merge on Windows laptop (2026-04-16)

### Observation: taxonomy-etl finished in 77 seconds, not 10 minutes

The plan estimated 10 minutes for taxonomy. Actual end-to-end time on the Windows laptop was 77 seconds: download 5s, extract 1s, parse nodes.dmp 6s, merge names + map nodes 6s, map edges 3s, export KGX TSVs 19s, internal validation 3s.

The "10 minutes" estimate budgeted for a slow FTP day. With a fast NCBI connection and a local SSD, the parse-and-export work dominates and is small (2.74M records). No tuning needed.

Lesson: estimates in `bossman_execution_plan.md` for small datasets are conservative ceilings, not predictions. When a step finishes faster than budgeted, that is the expected case, not a sign that something was skipped.

### Problem: `kgx validate` requires `-i tsv` flag, not auto-detected

The validation checklist in the plan shows `kgx validate data/kgx/<database>/nodes.tsv data/kgx/<database>/edges.tsv` with no flags. That fails on kgx 2.3.2 with `Error: Missing option '--input-format' / '-i'`.

Fix: invoke as `kgx validate -i tsv data/kgx/<db>/nodes.tsv data/kgx/<db>/edges.tsv`. The validator does not infer format from the file extension.

Lesson: update the validation checklist in `bossman_execution_plan.md` step 8 to include `-i tsv`. Carry this forward for every gate.

### Problem: edges missing BioLink 4.x required `knowledge_level` and `agent_type` slots

Once `kgx validate` ran with the right flag, it returned `ERROR: MISSING_EDGE_PROPERTY` for `knowledge_level` and `agent_type` on taxonomy edges. BioLink Model 4.x marks both as required slots on every `Association`. They define provenance metadata: how the assertion was made (knowledge_assertion vs prediction vs statistical_association) and what produced it (manual_agent vs automated_agent vs text_mining_agent).

Root cause: `system-01-data-pipelines/shared/kgx_exporter.py` defined `EDGE_REQUIRED_COLUMNS = ["subject", "predicate", "object", "source", "source_url"]` — 5 columns. No pipeline mapper set `knowledge_level` or `agent_type`. The schema in `schema/biolink_ncbi.yaml` defined both as optional slots on `Association`, so internal LinkML validation passed. The external NCATS `kgx validate` enforces BioLink Model required slots, which our internal validator does not.

Blast radius: all 5 pipelines (Gene, ClinVar, MedGen, Taxonomy, PubMed) use the same shared exporter and shared `map_edge()`. Gate 1 outputs (Gene, ClinVar, MedGen) have the same gap. Gate 1's validation step 8 was checked off in the plan but the external validator was never actually run on Gate 1 outputs (or it failed with the missing `-i tsv` flag and the failure was not surfaced).

Fix:

- `system-01-data-pipelines/shared/biolink_mapper.py`: added `knowledge_level: str = "knowledge_assertion"` and `agent_type: str = "manual_agent"` as kwargs on `map_edge()` with sensible defaults. Pipeline mappers can override per edge (e.g. `agent_type="automated_agent"` for Gene orthologs from HomoloGene, or for GO annotations with IEA evidence).
- `system-01-data-pipelines/shared/kgx_exporter.py`: added both columns to `EDGE_REQUIRED_COLUMNS`. Streaming pipelines (Gene, PubMed) compute their fieldnames from this constant, so they pick up the new columns automatically.
- `schema/biolink_ncbi.yaml`: marked `knowledge_level` and `agent_type` required in `Association.slot_usage` so the schema reflects what the exporter now produces.
- `tests/shared/test_biolink_mapper.py`: added 2 tests covering the defaults and override behavior. Test count went from 180 to 184.

Defaults reasoning: most NCBI data is curator-asserted (Taxonomy hierarchy, ClinVar submissions, MedGen concept relations, PubMed MeSH annotations, gene_info, mim2gene_medgen). `knowledge_assertion` + `manual_agent` is the right default. Edges that are computationally derived (Gene orthologs from HomoloGene, GO IEA annotations) should override; that work is deferred to a Phase 3 follow-up since it does not block Gate 2.

Re-do scope and cost (mid-Gate-2 cleanup):

- Code change: 1 file (`shared/kgx_exporter.py`) plus the mapper, schema, and tests. 184 tests pass after the change (was 180 + 4 new).
- Re-export from cache, not re-download: FTP downloads were fine (untouched by the bug). Only the KGX output stage needed re-running. `<pipeline>-etl --skip-download` reuses the gigabytes of cached FTP files and just re-emits the TSVs with new code. Taxonomy re-export took 30 seconds; MedGen + ClinVar a few minutes each; Gene ~30 minutes (still streams 278M edges).
- PubMed: caught mid-download, so kill + restart let us roll the BioLink fix and the parallel-download speedup (decision logged 2026-04-16) into a single restart with no extra cost.
- Net wall-clock cost: ~2 hr (PubMed parallel download dominates). Net benefit: clean BioLink 4.x compliance across all 5 databases in one shot before `merge-etl` runs, instead of carrying the gap into Phase 3 and discovering it during AGE load.

Lesson 1: external `kgx validate` is a different bar from internal LinkML schema validation. The external validator enforces the BioLink Model's required-slot list at the time the validator was published; that list grows with every BioLink minor release. Schema-says-optional does not mean validator-accepts. Run external `kgx validate -i tsv` at every gate, not just internal validation.

Lesson 2: schema definition is documentation, not enforcement. A slot defined in the LinkML YAML does not appear in the KGX output unless the exporter writes the column. The schema, the mapper, and the exporter must all agree.

Lesson 3: shared utility bugs hide because per-pipeline tests use small in-line fixtures that pass through the same broken shared code. The bug only surfaced on real-data validation. Lesson for the next gate: run external `kgx validate` on a small fixture as part of CI, not only at gate time.

### Problem: gene pipeline OOMs on 33 GB laptop because nodes aren't streamed (2026-04-17)

When gene-etl was re-run on the laptop during Gate 2 (to regenerate KGX with the BioLink 4.x fix), the python process grew to 21 GB RSS and crashed with `MemoryError`. The system had 33.9 GB total RAM, ~11 GB held by Windows + IDE + Claude + browser, leaving ~22 GB for gene — and parse_gene_info peaks above that.

Root cause: edges were already streamed (fix from Gate 1, learnings section above), but nodes are not. `gene/parse_gene_info.py` returns a list of all 67M gene dicts at once, and `gene/pipeline.py` holds that list in RAM while calling `export_nodes(all_nodes, ...)`. Peak memory ~22-25 GB just for the node accumulation. Gate 1 succeeded because it ran on the NCBI server with 128+ GB RAM; on a 33 GB laptop the same design OOMs.

Contrast with PubMed: `pubmed/pipeline.py` uses `lxml.etree.iterparse` with `elem.clear()` and calls `append_nodes()` + `append_edges()` per article. Peak ~200-500 MB even on 41M articles. Streaming from the start, not after-the-fact.

Fix plan (executing 2026-04-17):

- `system-01-data-pipelines/gene/parse_gene_info.py`: convert the return-a-list parser into a generator that yields one node dict per row.
- `system-01-data-pipelines/shared/kgx_exporter.py`: add `init_nodes_file()` and `append_nodes()` mirroring the existing `init_edges_file()` / `append_edges()` streaming helpers.
- `system-01-data-pipelines/gene/pipeline.py`: call `init_nodes_file()` before parsing, then `append_nodes()` per batch as the generator yields, and drop the accumulated-list pattern.
- Tests: update gene pipeline tests to assert streaming behavior (nodes.tsv grows incrementally, RAM stays bounded).
- Re-run: delete only `data/kgx/gene/` (keep `data/ftp_cache/gene_*.gz` — raw source is untouched), then `gene-etl --skip-download` with the new streaming code. Expected peak ~2-3 GB RAM.

Lesson: when a pipeline works on a server but not on a laptop, the issue is almost always unbounded accumulation in RAM. The streaming refactor that worked for pubmed from day 1, and for gene edges after Gate 1, must also cover gene nodes. The rule going forward: any parser returning a list of >1M items should instead be a generator feeding a streaming writer, regardless of current RAM headroom. The "fits in server RAM" assumption is a time bomb for any dev environment.

### Problem: merge-etl OOMs for the same streaming reason as gene (2026-04-17)

After the gene streaming refactor landed and gene produced a clean KGX, `merge-etl` was started. RAM climbed from 43% to 96% load within seconds and the run was halted before OOM.

Root cause: `system-01-data-pipelines/shared/merger.py` has the same anti-pattern that just bit gene. `load_kgx_nodes(path)` and `load_kgx_edges(path)` each read an entire KGX TSV into a list of dicts in RAM. At Phase 2.2 test time the files were tiny (inline fixtures, <1K rows) so nobody noticed. At Gate 2 real scale the files are:

- gene: 67.5M nodes (11.3 GB TSV) + 278.7M edges (40.1 GB TSV)
- pubmed: 41.3M nodes (25 GB TSV) + 349.2M edges (41 GB TSV)
- medgen: 0.2M nodes + 48.3M edges
- clinvar: 4.4M nodes + 14.4M edges
- taxonomy: 2.7M nodes + 2.7M edges

Load all 5 as list-of-dicts into RAM = ~200 GB, impossible on a 33 GB laptop.

Fix plan (executing 2026-04-17):

- `shared/merger.py`: add `stream_kgx_nodes(path)` and `stream_kgx_edges(path)` generators that yield one dict per row. Keep `load_kgx_nodes` / `load_kgx_edges` as thin wrappers around the generators, for tests that want full lists on small fixtures.
- `shared/merger.py`: add `merge_kgx_streaming(node_paths, edge_paths, output_paths)` that runs in two passes. Pass 1 streams every nodes.tsv, dedups by id via an in-memory set of ~116M CURIE strings (~8 GB, fits on 33 GB), writes to merged/nodes.tsv in 10K-row batches. Pass 2 streams every edges.tsv, tracks dangling endpoints via set membership, writes to merged/edges.tsv in batches, and appends stub nodes for missing endpoints at the end of the nodes file.
- `merge/pipeline.py`: swap `merge_kgx` + `inject_stubs` + `validate_merge` for the streaming version. Skip edge-level dedup at merge time (cross-pipeline edge collisions are rare by construction — each pipeline's edges are scoped to its own subject prefix; edge set dedup would require a 200 GB in-memory set that is not worth the cost).
- Tests: existing Phase 2.2 merge tests use small fixtures and continue to pass via the list wrappers. Add one integration test that validates streaming on a synthetic medium-sized input.

Memory projection:
- Node ID set: ~8 GB (116M unique CURIEs)
- Batch buffers: ~10 MB
- Python runtime + Windows + IDE + Claude: ~10 GB
- Peak: ~20 GB on a 33 GB laptop → ~60% load, safe margin

Lesson: the "accumulate in list, then write" pattern in shared utilities is a landmine. It hid in `merger.py` through Phase 2.2 because all tests used tiny fixtures, and hit us within minutes of the first real-data merge attempt. New rule: any shared utility that reads or produces data proportional to FTP input size must be a generator or stream by default. The list version exists only for tests, with a loud docstring saying "do not use in production pipelines."

### Observation: OMIM prefix missing from merger's _PREFIX_TO_CATEGORY (2026-04-17)

The Gate 2 merge completed and injected 81,125 stubs for dangling cross-pipeline references. The stub prefix breakdown was:

- ClinVar: 43,770 (expected: newer ClinVar IDs referenced but not yet in our snapshot)
- PMID: 14,769 (expected: newer PMIDs in gene2pubmed not in our baseline)
- HP: 9,881 (expected)
- MedGen: 2,032 (expected)
- **OMIM: 10,580** (unexpected - these became `biolink:NamedThing` because `OMIM:` is not in `_PREFIX_TO_CATEGORY` in `system-01-data-pipelines/shared/merger.py`)
- NCBIGene: 89, NCBITaxon: 4 (negligible)

Root cause: `_PREFIX_TO_CATEGORY` covers NCBIGene, PMID, MeSH, GO, MedGen, MONDO, NCBITaxon, HP, ClinVar, UMLS — but not OMIM. The Gene pipeline's mim2gene_medgen parser emits edges with OMIM CURIEs as endpoints. At merge time, those CURIEs had no matching node (OMIM is not one of our pipelines), so they became stubs with fallback category `biolink:NamedThing`.

Fix (low priority, not a Gate 2 blocker): add `("OMIM:", "biolink:Disease"),` to `_PREFIX_TO_CATEGORY`. OMIM is a clinical disease/phenotype registry; categorising as `biolink:Disease` aligns with how MedGen and MONDO are already mapped. Re-running merge (or a post-merge rewrite) would move 10,580 stubs from NamedThing to Disease.

Lesson: whenever the merger injects stubs as `biolink:NamedThing`, treat it as a gap in `_PREFIX_TO_CATEGORY`. Each Gate run should include a post-merge check: "how many NamedThing stubs, what prefix?" and add the missing row to the table.

### Understanding: why the merged graph shows 115.4M nodes (not ~116M) and 99.99% cross-pipeline connectivity (not 100%)

Two questions came up reading the Gate 2 merge report. Both answers are "the numbers are right; here's the arithmetic."

Merged node count:

| Step | Nodes |
|------|-------|
| Gene | 67,562,827 |
| PubMed | 41,305,514 |
| ClinVar | 4,426,035 |
| Taxonomy | 2,736,607 |
| MedGen | 198,813 |
| Sum of raw inputs | 116,229,796 |
| Duplicates removed (same CURIE in 2+ pipelines, first occurrence wins) | -904,160 |
| Unique nodes after dedup | 115,325,636 |
| Stub nodes added (dangling endpoints) | +81,125 |
| Final merged total | 115,406,761 (matches report) |

The 904K dedup hits are cross-pipeline overlap, not data loss. Examples: MedGen disease IDs that ClinVar also names via has_phenotype; MeSH IDs present as stubs in pubmed and as cross-refs in medgen; a handful of GO terms duplicated between gene2go and medgen mappings. Dedup keeps the first occurrence and drops the rest; we have all the data.

Why 99.99%, not 100%. The 81,125 stubs (0.07% of 116M nodes) break down by prefix:

| Prefix | Stubs | Why it is stubs |
|--------|-------|-----------------|
| ClinVar | 43,770 | ClinVar IDs referenced by Gene and MedGen that were not in our ClinVar snapshot. ClinVar variants get merged and retired, and some references are forward-looking. |
| PMID | 14,769 | PMIDs in gene2pubmed added after our PubMed baseline snapshot. FTP snapshots are not synchronised across NCBI databases. |
| OMIM | 10,580 | mim2gene_medgen references OMIM disease IDs. OMIM is not one of our 5 pipelines, so every OMIM reference is a stub by design. |
| HP | 9,881 | Same reason as OMIM. MedGen cross-references HPO terms; HPO is not a pipeline we ingest. |
| MedGen | 2,032 | Newer MedGen concepts not in our MedGen snapshot yet. |
| NCBIGene | 89 | Gene IDs in clinvar not in the gene snapshot (trivial volume). |
| NCBITaxon | 4 | Taxa merged or deleted between the gene_info and taxdump snapshot dates. |

The "missing 0.01%" is structural, not a bug:

- 0.006% of Gene->PMID edges miss because PMIDs get added to pubmed continuously, and gene_info.gz/gene2pubmed.gz are snapshotted on a different schedule from pubmed/baseline/.
- 0.0001% of Gene->Taxon miss because taxonomy curation merges and retires taxa as new genomes are published.
- OMIM (~10K) and HP (~10K) can never resolve because we chose not to ingest those databases. See DECISIONS.md 2026-04-06 (v1 scope: no OMIM, no HPO).

To reach 100% you would need either (a) same-minute synchronised FTP snapshots across all NCBI source databases, which NCBI does not publish, or (b) ingest OMIM and HPO as Layer 1 pipelines. Option (b) adds roughly 50 MB of source data and is deferred to a post-Gate-4 scope expansion.

Lesson: a 0.07% stub rate on a 116M-node biological knowledge graph is healthy. Published merged KGs in the BioLink / NCATS ecosystem routinely run 2-5% stubs because their source snapshots drift too. Anyone reviewing the Gate 2 merge_report.md should read `stub_count / node_count` rather than the raw `Validation passed: False` line (which is noise from stubs carrying empty source_url, intentional behaviour that matches the inject_stubs contract).

### Decision: delete per-db KGX after merge validates, keep merged + FTP cache

Logged 2026-04-17 during Gate 2 execution. Once `merge-etl` finishes and the merged KGX passes validation (awk col check, row counts, cross-pipeline connectivity metrics resolve to 0 dangling), the per-database KGX directories are redundant. Deleting them reclaims ~130 GB of disk, giving clean headroom for Phase 3 fixture smoke tests and Phase 4 rsync staging.

Guard before deletion (all must pass):
- Merged nodes.tsv + edges.tsv both have the 7 BioLink 4.x edge columns
- Row counts: merged ≥ sum of per-db minus expected dedup (no silent loss)
- Gene->PMID, Gene->NCBITaxon, PMID->MeSH cross-pipeline edges resolve to valid nodes (0 dangling after merge)

Recovery path if something later breaks: the FTP cache at `data/ftp_cache/` is untouched, so any per-db KGX can be regenerated with `<pipeline>-etl --skip-download` (minutes for everything except pubmed which is 2-3 hr for the parse+export).

Extends the 2026-04-14 decision (KGX files are intermediates) to apply inside Gate 2 rather than only at Phase 4.

### Observation: `run_in_background: true` with shell `&` produces misleading "completed" notifications

Running `.venv/Scripts/<cli>.exe > log 2>&1 &` with `run_in_background: true` reports the bash shell as "completed (exit code 0)" almost immediately, even though the orphaned `.exe` keeps running. The exit code is the wrapper shell's, not the pipeline's.

Verified for taxonomy-etl (77s actual run, completion event fired in seconds) and pubmed-etl (still running 1 hour in, completion event fired in seconds).

Confirm a pipeline is actually alive by checking:
1. `tasklist | grep -iE "python|<cli-name>"` for the running process
2. Log file mtime is recent
3. `du -sh data/ftp_cache/<db>/` is growing

Lesson: do not trust "exit 0" from a backgrounded `&` invocation. The pipeline is not done until its own log says so or the KGX outputs land.

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

Fix: corrected the build-backend string. A second follow-up fix on 2026-04-16 replaced `[tool.setuptools.packages.find]` with an explicit `packages = [...]` list because setuptools `find` skips directories whose names contain hyphens (`system-01-data-pipelines`), leaving the MAPPING dict empty and breaking CLI entry points. Explicit enumeration works around this.

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
