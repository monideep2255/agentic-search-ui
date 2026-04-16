# Bossman execution plan: System 1 data pipelines

Phase-by-phase implementation plan for the 6 NCBI ETL pipelines. Each phase is one bossman session with integrated skill chain and branch+MR workflow. Use `/bossman-mode --phase N` to execute.

Created: 2026-04-13. Last updated: 2026-04-16 (Phase 2.2 complete).

---

## Plan overview

```mermaid
graph TD
    subgraph "Phase 1: core triangle [DONE]"
        P10[1.0 Schema + scaffolding]
        P11[1.1 Shared utilities]
        P12[1.2-1.4 Gene+ClinVar+MedGen ETL]
        P15[1.5 Merge + validation]
        P10 --> P11 --> P12 --> P15
    end

    subgraph "Gate 1: run locally [DONE]"
        G1R[Run medgen/gene/clinvar-etl]
        G1V[KGX BioLink validation]
        P15 --> G1R --> G1V
    end

    subgraph "Phase 2: literature + taxonomy [DONE]"
        P20[2.0 PubMed ETL code DONE]
        P21[2.1 Taxonomy ETL code DONE]
        P22[2.2 Five-database merge code DONE]
        G1V --> P20 & P21
        P20 & P21 --> P22
    end

    subgraph "Gate 2: run locally NEXT"
        G2R[Run pubmed/taxonomy-etl + merge-etl]
        G2V[KGX BioLink validation]
        P22 --> G2R --> G2V
    end

    subgraph "Phase 3: AGE loader + local graph"
        P30[3.0 AGE loader code]
        P30L[Load 5 databases into AGE]
        P30Q[Cypher query validation]
        G2V --> P30 --> P30L --> P30Q
    end

    subgraph "Gate 3: local graph validated"
        G3D[Delete local KGX files]
        P30Q --> G3D
    end

    subgraph "Phase 4: cloud deploy"
        P40[4.0 Deploy 5-db to Hetzner VPS]
        P40V[Verify remote queries]
        G3D --> P40 --> P40V
    end

    subgraph "Phase 5: dbSNP on cloud"
        P50[5.0 SNP ETL code]
        P51[5.1 Run SNP pipeline on cloud]
        P52[5.2 SNP-ClinVar merge on cloud]
        P40V --> P50 --> P51 --> P52
    end

    subgraph "Gate 4: complete"
        G4V[Full 6-db graph validation]
        P52 --> G4V
    end

    style P10 fill:#2d6a2d,color:#fff
    style P11 fill:#2d6a2d,color:#fff
    style P12 fill:#2d6a2d,color:#fff
    style P15 fill:#2d6a2d,color:#fff
    style G1R fill:#2d6a2d,color:#fff
    style G1V fill:#2d6a2d,color:#fff
    style P20 fill:#2d6a2d,color:#fff
    style P21 fill:#2d6a2d,color:#fff
    style P22 fill:#2d6a2d,color:#fff
    style G2R fill:#c9a227,color:#000
```

Legend: green = done, yellow = in progress, default = pending.

Each phase produces code only (parsers, pipeline orchestrators, tests). Each gate runs the pipelines on real NCBI FTP data and validates BioLink compliance via the NCATS KGX validator. KGX files are intermediates deleted after AGE load. The graph database is the end target, deployed to a cloud VPS for team access.

---

## End product

When all phases are complete, this repo produces:

1. 6 ETL pipelines that download NCBI bulk data and output BioLink-compliant KGX files (nodes.tsv + edges.tsv per database)
2. A merged knowledge graph in PostgreSQL + Apache AGE, deployed on a Hetzner VPS, queryable via openCypher
3. Every node and edge traceable back to its NCBI source record (provenance on 100%)

### Graph scale

| Pipeline | Nodes | Edges | KGX size |
|----------|-------|-------|----------|
| Gene (all organisms) | ~67.5M | ~278M | ~39GB |
| ClinVar | ~4.5M | ~9M | ~3-5GB |
| MedGen | ~233K | ~500K | ~200MB |
| PubMed | ~40M | ~40M+ | ~30-50GB |
| Taxonomy | ~2.9M | ~2.9M | ~1-2GB |
| SNP (full dbSNP) | ~1.2B | ~1.2B+ | ~200-400GB |
| Total | ~1.3B | ~1.5B+ | ~300-500GB |

### What you can query after Gate 4

- "Find all pathogenic variants in BRCA1" (Gene -> ClinVar)
- "What diseases are associated with HNF1A?" (Gene -> ClinVar -> MedGen)
- "What publications mention BRCA1 and breast cancer?" (Gene -> PubMed, MeSH filter)
- "What human genes are involved in glucose metabolism?" (Taxonomy + Gene -> GO)
- "What is the European allele frequency of rs328?" (dbSNP population frequencies)
- "What is the mutation spectrum for HNF1A?" (full dbSNP aggregate variant stats)

This is System 1 + System 2. System 3 (search agent, FastAPI, LangGraph, UI) lives in a separate repo and consumes this graph.

---

## Timeline estimate

### What the phases produce (code vs data)

Each bossman phase produces code only: parsers, pipeline orchestrators, shared utilities, and tests. Tests use small inline fixtures, not real NCBI data. No data is downloaded during bossman sessions.

The actual FTP downloads happen when you run the pipelines at each gate. Running the pipelines is a separate step from building them.

### Data validation gates (run after each phase group)

After each group of pipeline phases is built and merged, run the pipelines on real data before building the next group. This catches data format surprises early.

Every gate runs the same validation checklist on each pipeline's KGX output before proceeding.

### Validation checklist (run at every gate, for every database)

1. Pipeline runs without errors (no crashes, no uncaught exceptions)
2. KGX files exist at `data/kgx/<database>/nodes.tsv` and `edges.tsv`
3. Row counts match expected order of magnitude (see graph scale table above)
4. All data downloaded, no organism filters, no subset sampling
5. 0 duplicate node IDs
6. 100% provenance coverage (every node and edge has source + source_url)
7. Dangling edges logged and explained (cross-pipeline refs are expected, unexplained dangles are not)
8. KGX BioLink validation via NCATS validator passes:
   ```
   pip install kgx
   kgx validate data/kgx/<database>/nodes.tsv data/kgx/<database>/edges.tsv
   ```
   Checks: categories and predicates exist in official BioLink model, ID prefixes registered in BioLink prefix map, required KGX columns present, edge subjects/objects reference valid node IDs
9. Validation report saved, any failures fixed before proceeding
10. docs/data_inventory.md updated with download sizes, row counts, and validation results
11. docs/learnings.md updated with any problems encountered and fixes applied

### Gate status

| Gate | Run after | What | Where | Status |
|------|-----------|------|-------|--------|
| Gate 1 | Phase 1.5 | Run medgen/gene/clinvar-etl, validate KGX | Local | DONE (2026-04-16) |
| Gate 2 | Phase 2.2 | Run pubmed/taxonomy-etl + merge-etl, validate KGX | Local | Pending (NEXT) |
| Gate 3 | Phase 3.0 | Load 5-db into AGE, Cypher queries, delete KGX | Local | Pending |
| Gate 4 | Phase 5.2 | Full 6-db graph on cloud, all queries pass | Hetzner VPS | Pending |

### Coding time (bossman sessions)

| Phase | Session | What | Status |
|-------|---------|------|--------|
| 1.0 | 1 | Schema + scaffolding | DONE (2026-04-13) |
| 1.1 | 2 | Shared utilities (6 modules) | DONE (2026-04-14) |
| 1.2-1.4 | 3 | Gene + ClinVar + MedGen ETL | DONE (2026-04-14) |
| 1.5 | 4 | Merge + validation | DONE (2026-04-14) |
| Gate 1 | - | Run 3 pipelines locally, validate | DONE (2026-04-16) |
| 2.0 | 5 | PubMed ETL | DONE (2026-04-16) |
| 2.1 | 6 | Taxonomy ETL | DONE (2026-04-16) |
| 2.2 | 7 | 5-database merge | DONE (2026-04-16) |
| Gate 2 | - | Run PubMed + Taxonomy + merge-etl locally, validate | NEXT |
| 3.0 | 8 | AGE loader code + load 5-db locally | Pending |
| Gate 3 | - | Validate local graph, delete KGX files | Pending |
| 4.0 | 9 | Deploy 5-db graph to Hetzner VPS | Pending |
| 5.0 | 10 | SNP ETL code | Pending |
| 5.1 | 11 | Run SNP pipeline on cloud VPS | Pending |
| 5.2 | 12 | SNP-ClinVar merge on cloud | Pending |
| Gate 4 | - | Full 6-db graph validated on cloud | Pending |

### Wall-clock time (downloads and processing)

| Task | Wall-clock | When |
|------|-----------|------|
| MedGen download (115MB) | 5 min | Gate 1 (local) |
| Gene FTP download (3GB) | 30-60 min | Gate 1 (local) |
| ClinVar download (500MB) | 20-30 min | Gate 1 (local) |
| PubMed baseline download (30GB) | 4-8 hours | Gate 2 (local, overnight) |
| Taxonomy download (500MB) | 10 min | Gate 2 (local) |
| AGE load 5 databases (~140M nodes) | 2-6 hours | Phase 3.0 (local) |
| pg_dump + transfer to Hetzner | 1-3 hours | Phase 4.0 |
| dbSNP download (100GB) | 8-16 hours | Phase 5.1 (cloud, overnight) |
| dbSNP VCF parsing (1.2B records) | 4-12 hours | Phase 5.1 (cloud) |
| dbSNP load into AGE (incremental) | 6-24 hours | Phase 5.2 (cloud) |

### Realistic calendar

| Week | What | Where | Status |
|------|------|-------|--------|
| Week 1 | Phase 1 code + Gate 1 | Local | DONE (2026-04-14 to 2026-04-16) |
| Week 2 | Phase 2 code + Gate 2 | Local | 2.0 + 2.1 + 2.2 code DONE (2026-04-16). Gate 2 NEXT (pubmed/taxonomy run + 5-db merge validation). |
| Week 3 | Phase 3 (AGE load) + Gate 3 + Phase 4 (deploy) | Local then cloud | Pending |
| Week 4 | Phase 5 (dbSNP on cloud) + Gate 4 | Cloud | Pending |

### Why this order

1. Phases 1-2 (code + Gates 1-2): build and test all non-dbSNP pipelines locally. Free, fast iteration.
2. Phase 3 (AGE load locally): load 5-database graph into PostgreSQL + AGE on your machine. Validate with Cypher queries. Delete KGX intermediates.
3. Phase 4 (deploy to cloud): `pg_dump` the validated local database, set up Hetzner VPS, `pg_restore` on cloud. Teammates and System 3 can now access the graph.
4. Phase 5 (dbSNP on cloud): build the SNP ETL code locally, run the pipeline directly on the Hetzner VPS. dbSNP downloads and loads on the cloud instance where there's 500GB dedicated disk. No local storage pressure.

Schema impact: none. The schema already defines `biolink:SequenceVariant` for both ClinVar (`ClinVar:{id}`) and dbSNP (`dbSNP:rs{id}`). They are different nodes in the graph, connected by an `exact_match` edge via the RS# field in ClinVar's variant_summary. No schema changes needed at any step.

### Disk budget

Local disk (`/export`): 4.3TB total, ~403GB free as of 2026-04-14.

| After step | Local disk used | Local headroom |
|------------|----------------|----------------|
| Gate 1 (KGX for 3 databases) | ~50-60GB | ~345GB |
| Gate 2 (add PubMed + Taxonomy KGX) | ~100-130GB | ~275GB |
| Phase 3 (AGE load + KGX on disk) | ~200-280GB | ~125GB |
| Gate 3 (delete KGX, keep AGE) | ~100-150GB | ~255GB |
| Phase 4 (pg_dump for transfer) | ~200-300GB temporarily | ~100GB |
| After deploy (delete local AGE) | ~5GB (FTP cache only) | ~400GB |

Cloud disk (Hetzner CX41 + 500GB volume): dedicated to this project.

| After step | Cloud disk used | Cloud headroom |
|------------|----------------|----------------|
| Phase 4 (5-db graph restored) | ~100-150GB | ~350GB |
| Phase 5 (add dbSNP) | ~250-350GB | ~150GB |

No storage problems at any step.

### Data storage

Local: all data on `/export` (local LVM volume, not NFS home). Paths configured in `.env`. Symlinked to `data/` in the repo (gitignored). FTP cache kept for re-runs, KGX files deleted after AGE load.

Cloud: PostgreSQL + AGE database on Hetzner VPS. This is the production instance that System 3 connects to. Estimated cost: ~$25-30/month for 8 vCPU, 16GB RAM, 500GB disk.

---

## Skill chain (every phase follows this)

Each bossman phase integrates multiple skills in a fixed order. This is not optional.

```
PHASE START
  |
  +-- best-practices         session checklist (venv, postgres, CLAUDE.md, git status)
  +-- architecture-patterns   read before designing new modules
  +-- git branch              create phase/N.M-description from main
  |
DEVELOPMENT (bossman autonomous execution)
  |
  +-- python-code-standards   inline during code writing (type hints, docstrings, logging)
  +-- testing-standards       write tests alongside code (fixtures, no network, one assert per concept)
  +-- documentation-standards sentence case, no bold, no em dashes
  +-- decision-logging        log choices to DECISIONS.md as they happen
  +-- parallel-first          check independence, dispatch parallel builders
  +-- boil-the-lake           complete 100%, no shortcuts
  +-- attack-the-constraint   focus on what actually blocks progress
  |
PHASE END
  |
  +-- qa-gate                 6-phase quality gate (mandatory, no skips)
  |   +-- Phase 1: pytest -q
  |   +-- Phase 2: python-code-standards + testing-standards
  |   +-- Phase 3: eval-harness (BioLink, KGX, dangling edges, provenance)
  |   +-- Phase 4: schema + dependency-tracking
  |   +-- Phase 5: documentation-standards + docs-sync agent
  |   +-- Phase 6: verdict checklist
  |
  +-- release-workflow        chains qa-gate then ship
  +-- ship                    docs-sync agent -> commit -> push branch -> create MR
  |
MR REVIEW
  |
  +-- user reviews and approves MR
  +-- merge into main
  +-- delete phase branch
  +-- proceed to next phase
```

### Skills by role

| When | Skills active | Rules active | Agents |
|------|--------------|-------------|--------|
| Phase start | best-practices, architecture-patterns | file-protection, dependency-tracking | none |
| Development | python-code-standards, testing-standards, documentation-standards | parallel-first, boil-the-lake, attack-the-constraint, writing-style, decision-logging | sub-agents (builders, judge, test writer) |
| Phase end | qa-gate (chains eval-harness), release-workflow, ship | git-workflow, file-protection | docs-sync, git-sync |
| Review | objective-review (optional, if user asks) | none | none |

### Skills suspended during bossman execution

| Skill | Why suspended |
|-------|--------------|
| socratic-questioning | Scope is defined. No Socratic questioning mid-build. |
| first-principles | Used during planning, not execution. |
| pause-before-acting | Plan is agreed. No need to pause and re-check. |
| preserve-your-thinking | Decisions were made during planning. Execute. |
| clarify-before-drafting | Scope is defined. |

---

## Branch + MR workflow

### Branch naming

`phase/N.M-short-description` where N.M matches the phase number.

| Phase | Branch name | Status |
|-------|------------|--------|
| 1.0 | `phase/1.0-schema-scaffolding` | Merged, deleted |
| 1.1 | `phase/1.1-shared-utilities` | Merged, deleted |
| 1.2-1.4 | `phase/1.2-1.4-core-triangle-etl` | Merged, deleted (combined) |
| 1.5 | `phase/1.5-merge-validation` | Merged, deleted |
| 2.0 | `phase/2.0-pubmed-etl` | Merged, deleted |
| 2.1 | `phase/2.1-taxonomy-etl` | Merged, deleted |
| 2.2 | `phase/2.2-literature-taxonomy-merge` | Open |

### Per-phase git flow

```
1. git checkout main && git pull origin main
2. git checkout -b phase/N.M-description
3. [bossman builds, commits within branch]
4. qa-gate passes
5. git push -u origin phase/N.M-description
6. gh pr create
7. user reviews MR
8. merge into main, delete branch
9. start next phase from updated main
```

### Parallel phases (1.2 + 1.3 + 1.4)

The original plan called for three separate branches, but in practice these were combined into a single branch (`phase/1.2-1.4-core-triangle-etl`) since all three pipelines touch different directories with no conflicts. One PR, one merge. Faster to review and ship.

---

## Execution map

```
Session 1: Phase 1.0  schema + project scaffolding        DONE (2026-04-13)
    v
Session 2: Phase 1.1  shared utilities (6 modules)        DONE (2026-04-14)
    v
Session 3: Phase 1.2-1.4  Gene+ClinVar+MedGen ETL         DONE (2026-04-14)
    v
Session 4: Phase 1.5  merge + validation                  DONE (2026-04-14)
    v
--- GATE 1: run 3 pipelines locally (all data) ---        DONE (2026-04-16)
    |  medgen-etl (198K nodes, 48M edges)
    |  gene-etl (67.5M nodes, 278M edges)
    |  clinvar-etl (4.4M nodes, 14M edges)
    v
Session 5: Phase 2.0  PubMed ETL code                     DONE (2026-04-16)
    v
Session 6: Phase 2.1  Taxonomy ETL code                   DONE (2026-04-16)
    v
Session 7: Phase 2.2  5-database merge code               DONE (2026-04-16)
    v
--- GATE 2: run PubMed + Taxonomy + merge-etl locally --- NEXT
    |  pubmed-etl (overnight), taxonomy-etl
    |  kgx validate on each output
    v
Session 8: Phase 3.0  AGE loader code + load 5-db locally
    |  load Gene+ClinVar+MedGen+PubMed+Taxonomy into AGE
    |  run Cypher test queries
    v
--- GATE 3: local graph validated ---
    |  delete KGX intermediates
    v
Session 9: Phase 4.0  deploy to Hetzner VPS
    |  pg_dump local, pg_restore on cloud
    |  verify Cypher queries work remotely
    v
Session 10: Phase 5.0  SNP ETL code (built locally)
    v
Session 11: Phase 5.1  run SNP pipeline on cloud VPS
    |  download dbSNP directly to cloud (100GB)
    |  parse per chromosome, load into AGE incrementally
    v
Session 12: Phase 5.2  SNP-ClinVar merge on cloud
    |  link ClinVar variants to dbSNP via RS# field
    v
--- GATE 4: full 6-database graph on cloud ---
    |  run all test queries
    |  handoff to System 3
    |  system complete
```

---

## Phase 1: core triangle (Gene + ClinVar + MedGen) [DONE]

### Phase 1.0: schema + project scaffolding (DONE 2026-04-13)

Branch: `phase/1.0-schema-scaffolding` (merged, deleted)

Deliverables (all complete):
- `schema/biolink_ncbi.yaml`: LinkML schema with 10 node types, 14 predicates, provenance fields required
- `pyproject.toml`: project metadata, pytest config, Click entry points, package-dir mapping
- `tests/conftest.py`: 4 shared fixtures
- `tests/test_schema.py`: 5 tests validating schema structure

Pass criteria (all passed):
- [x] `linkml validate schema/biolink_ncbi.yaml` exits 0
- [x] All 10 node categories present
- [x] 14 predicates present (added orthologous_to and cited_in)
- [x] Every node class requires: id, category, name, source, source_url
- [x] `pytest tests/test_schema.py` passes (5/5)

### Phase 1.1: shared utilities (DONE 2026-04-14)

Branch: `phase/1.1-shared-utilities` (merged, deleted)

Deliverables (all in `system-01-data-pipelines/shared/`):

| Module | Purpose |
|--------|---------|
| `config.py` | PipelineConfig dataclass, loads .env, creates dirs |
| `ftp_client.py` | Idempotent FTP download with cache-hit check |
| `entrez_client.py` | Entrez API with retry/backoff |
| `biolink_mapper.py` | map_node/map_edge with category/predicate validation |
| `kgx_exporter.py` | KGX TSV export with streaming append for large datasets |
| `validator.py` | Dangling edge, duplicate, and provenance validation |

Pass criteria (all passed):
- [x] 82 tests across 6 modules, all passing
- [x] All 6 modules importable
- [x] Provenance enforced at function signature level
- [x] ftp_client skips download on cache hit

### Phase 1.2: Gene ETL pipeline (DONE 2026-04-14)

Branch: `phase/1.2-1.4-core-triangle-etl` (combined, merged, deleted)

FTP source: `ftp.ncbi.nlm.nih.gov/gene/DATA/` (6 files: gene_info, gene2go, gene2pubmed, mim2gene_medgen, gene_refseq_uniprotkb_collab, gene_orthologs)

9 modules created. Uses streaming edge export (append_edges) to handle 278M edges without OOM.

Pass criteria (all passed):
- [x] 10 tests passing
- [x] Correct CURIE format, GO predicate mapping, provenance
- [x] Streaming edges to avoid OOM at full scale

### Phase 1.3: ClinVar ETL pipeline (DONE 2026-04-14)

Branch: `phase/1.2-1.4-core-triangle-etl` (combined, merged, deleted)

FTP source: `ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/` (variant_summary.txt.gz + var_citations.txt)

5 modules created. Uses variant_summary.txt.gz (tabular) not XML. Assembly filter (GRCh38) deduplicates, does not exclude data.

Pass criteria (all passed):
- [x] 16 tests passing
- [x] Header-based column lookup (robust to column order changes)
- [x] Streaming line-by-line parser

### Phase 1.4: MedGen ETL pipeline (DONE 2026-04-14)

Branch: `phase/1.2-1.4-core-triangle-etl` (combined, merged, deleted)

FTP source: `ftp.ncbi.nlm.nih.gov/pub/medgen/` (5 files, all pipe-delimited)

8 modules created. MONDO promotion with CUI-to-canonical-id rewriting in edges.

Pass criteria (all passed):
- [x] 18 tests passing
- [x] MONDO canonical where available, MedGen CUI fallback
- [x] Edge CUI references rewritten to canonical IDs

### Phase 1.5: merge + cross-pipeline validation (DONE 2026-04-14)

Branch: `phase/1.5-merge-validation` (merged, deleted)

Deliverables: merger.py, merge_report.py, 3 SSSOM mapping templates, 14 integration tests.

Pass criteria (all passed):
- [x] 14 integration tests passing
- [x] Stub injection for dangling cross-pipeline refs
- [x] Cross-database traversal tests (Gene -> ClinVar -> MedGen)

---

## Phase 2: literature + taxonomy

### Phase 2.0: PubMed ETL (DONE 2026-04-16)

Branch: `phase/2.0-pubmed-etl` (merged, deleted)

FTP: `ftp.ncbi.nlm.nih.gov/pubmed/baseline/` (1334 files, ~54GB compressed) + `updatefiles/` (81 files, current data through 2026-01-30)

5 modules created: download, parse_pubmed_xml (lxml streaming), parse_mesh_nodes, pipeline (single-open-handle streaming for ~40M articles + ~300M MeSH edges), cli.

Pass criteria (all passed):
- [x] 12 PubMed tests passing
- [x] lxml.etree.iterparse with proper element + ancestor clearing
- [x] One open() per file kind across whole loop (avoids 80M+ syscalls)
- [x] include_updates default True
- [x] BioLink: biolink:Article, biolink:OntologyClass, biolink:has_mesh_annotation

Decision: serialize_value made public in kgx_exporter for cross-module use.

### Phase 2.1: Taxonomy ETL (DONE 2026-04-16)

Branch: `phase/2.1-taxonomy-etl` (merged, deleted)

FTP: `ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz` (~70MB compressed, ~498MB extracted)

5 modules created: download (with path traversal guard on tarball extraction), parse_nodes, parse_names, pipeline, cli.

Format detail: NCBI taxdump uses `\t|\t` field delimiter and `\t|\n` row terminator (NOT standard tab).

Pass criteria (all passed):
- [x] 11 Taxonomy tests passing
- [x] Tab-pipe-tab delimiter handled correctly
- [x] Scientific name filter (name_class == "scientific name", with space)
- [x] Root self-loop excluded (tax_id=1 doesn't subclass_of itself)
- [x] BioLink: biolink:OrganismTaxon, biolink:subclass_of

Decision: in-memory list approach (2.7M nodes is small enough, no streaming needed).

### Phase 2.2: 5-database merge (DONE 2026-04-16)

Branch: `phase/2.2-literature-taxonomy-merge`

Deliverables (all complete):

- `system-01-data-pipelines/merge/pipeline.py`: `run_five_database_merge` orchestrator (collect inputs, merge_kgx, inject_stubs, validate_merge, write merged TSVs, generate report)
- `system-01-data-pipelines/merge/cli.py`: `merge-etl` command, registered in pyproject.toml
- `shared/merger.py`: prefix map extended with MeSH (biolink:OntologyClass), ClinVar (biolink:SequenceVariant), UMLS (biolink:Disease) so stubs for dangling cross-pipeline refs get the correct category
- `shared/merge_report.py`: connectivity metrics added for Gene->PMID, Gene->NCBITaxon, PMID->MeSH, NCBITaxon->NCBITaxon
- `tests/merge/test_five_database_merge.py`: 11 integration tests covering the full 5-database fixture, gene2pubmed resolution, in_taxon resolution, MeSH edge resolution, partial-dataset stub injection, and missing-database graceful skip
- `pyproject.toml`: `merge-etl`, `pubmed-etl`, `taxonomy-etl` scripts registered

Pass criteria (all passed):

- [x] 180 tests passing (146 Phase 1 + 23 Phase 2.0/2.1 + 11 merge)
- [x] merge-etl runs against a 5-database fixture and produces merged nodes.tsv, edges.tsv, and merge_report.md
- [x] Gene in_taxon edges resolve to NCBITaxon nodes (0 dangling)
- [x] Gene mentioned_in edges resolve to PubMed Article nodes (0 dangling)
- [x] PubMed has_mesh_annotation edges resolve to MeSH OntologyClass nodes (0 dangling)
- [x] Omitting a database injects correctly-typed stubs rather than dropping edges

---

## Phase 3: AGE loader (runs before dbSNP to free local disk)

### Phase 3.0: PostgreSQL + AGE loader

Branch: `phase/3.0-age-loader`
Build the AGE loader code, then load the 5-database KGX files into PostgreSQL + AGE locally. Create graph schema, load nodes/edges in batches, create indexes. Run Cypher test queries to validate. Delete KGX intermediates after validation passes.

Test queries:
- Gene to variant traversal (BRCA1)
- Disease to gene traversal (phenylketonuria -> PAH)
- Gene to biological process (glucose metabolism genes)

---

## Phase 4: cloud deployment

### Phase 4.0: deploy to Hetzner VPS

Branch: `phase/4.0-cloud-deploy`
Set up Hetzner CX41 + 500GB volume (~$25-30/month). Install PostgreSQL + AGE. `pg_dump` the local database, transfer to the VPS, `pg_restore`. Verify Cypher queries work remotely. This makes the graph accessible to teammates and System 3.

---

## Phase 5: dbSNP (runs on cloud VPS, not locally)

### Phase 5.0: SNP ETL code

Branch: `phase/5.0-snp-etl`
Build the SNP ETL pipeline code locally. Per-chromosome VCF parsing, streaming. Tests with small fixtures.

### Phase 5.1: run SNP pipeline on cloud

Run the SNP pipeline directly on the Hetzner VPS. Download dbSNP (~100GB compressed) to the cloud instance. Parse per chromosome, load each chromosome into AGE incrementally. Never have the full KGX on disk at once.

### Phase 5.2: SNP-ClinVar merge on cloud

Link ClinVar variants to dbSNP variants via the RS# field. Create `exact_match` edges between `ClinVar:{id}` and `dbSNP:rs{id}` for matched variants. All 6 databases in one graph.

---

## Testing strategy

Testing is integrated at every phase, not an afterthought.

### Test file structure

```
tests/
  conftest.py                          shared fixtures (4 fixtures)
  test_schema.py                       schema validation (5 tests)
  shared/
    conftest.py                        sys.path setup for shared imports
    test_config.py                     config loading (8 tests)
    test_ftp_client.py                 mocked FTP, cache-hit (8 tests)
    test_entrez_client.py              mocked Entrez, retry/backoff (14 tests)
    test_biolink_mapper.py             node/edge mapping, provenance (22 tests)
    test_kgx_exporter.py              TSV output, column order (10 tests)
    test_validator.py                  dangling edges, duplicates (20 tests)
  gene/
    test_gene_pipeline.py              all parsers + end-to-end (10 tests)
  clinvar/
    test_clinvar_pipeline.py           variant_summary, citations, end-to-end (16 tests)
  medgen/
    test_medgen_pipeline.py            id_mappings, names, mgrel, end-to-end (18 tests)
  integration/
    conftest.py                        sys.path setup
    test_merge.py                      merge dedup, stubs, validation (9 tests)
    test_cross_database_traversal.py   Gene -> ClinVar -> MedGen triangle (5 tests)
```

All tests use inline fixtures (no separate fixture files). Total: 146 tests, all passing.

### Testing rules

- Tests do not hit the network unless marked `@pytest.mark.integration`
- One assertion per test concept
- Fixtures for shared setup, never copy-paste
- For new code: there must be a test next to it
- Coverage target: 70%+ on shared utilities, parsers, and mappers

---

## Key decisions

1. Parsers are separate files per FTP source, not monoliths. Enables parallel builders.
2. Cross-database edges dangle within single-pipeline KGX. Merge phase injects stubs to resolve them.
3. ClinVar uses variant_summary.txt.gz (tabular, streaming line-by-line), not XML. Simpler and sufficient.
4. MONDO is canonical disease ID, MedGen CUI fallback. CUI-to-canonical-id rewriting in MedGen pipeline.
5. No Entrez API in Phase 1. All data from FTP bulk files.
6. Combined branch for parallel phases (1.2-1.4) when they touch different directories.
7. Skill chain is fixed: best-practices -> architecture-patterns -> [dev with standards] -> qa-gate -> release-workflow -> ship.
8. Sub-agents used for parallel builders. Simpler than full agent teams, sufficient for the task.
9. Testing integrated at every phase via testing-standards + qa-gate + eval-harness.
10. 180 tests across Phase 1 and Phase 2 (5 schema + 82 shared + 10 gene + 16 clinvar + 18 medgen + 14 integration + 12 pubmed + 11 taxonomy + 11 five-database merge).
11. Data validation gates between phase groups. Run pipelines on real data before building next group.
12. KGX files are intermediates. Graph database is the end target. Delete KGX after AGE load.
13. AGE loader (Phase 3) runs before dbSNP (Phase 5) to free local disk.
14. dbSNP runs on cloud VPS, not locally. Avoids local storage pressure.
15. Cloud deploy (Hetzner CX41 + 500GB volume, ~$25-30/month) for team access and System 3 integration.
16. Gene pipeline streams edges to disk per parser batch (append_edges) to avoid OOM on 278M edges.
17. ClinVar and dbSNP use different ID spaces (ClinVar:{id} vs dbSNP:rs{id}), no schema conflict. Connected via exact_match edges at Phase 5.2.

---

## Reference files

| File | Read when |
|------|-----------|
| `docs/System_1_data_engineering_plan.md` | Before any pipeline work |
| `docs/learnings.md` | After any pipeline run (add problems and solutions) |
| `docs/data_inventory.md` | After any pipeline run (add download and output details) |
| `reference/ncbi_ai_agents-ncbi-kg/KG/pipeline/src/glucose_metabolism_kg/` | Building shared utilities, merger, exporter |
