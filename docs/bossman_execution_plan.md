# Bossman execution plan: System 1 data pipelines

Phase-by-phase implementation plan for the 6 NCBI ETL pipelines. Each phase is one bossman session with integrated skill chain and branch+MR workflow. Use `/bossman-mode --phase N` to execute.

Created: 2026-04-13. Last updated: 2026-04-16 (Phase 2.2 complete; architecture revised: skip local AGE load, load once on cloud; local development moved from shared NCBI `/export` to personal Windows laptop).

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

    subgraph "Phase 3: AGE loader code"
        P30[3.0 AGE loader + fixture smoke test]
        G2V --> P30
    end

    subgraph "Phase 4: cloud provision + load"
        P40[4.0 Provision Hetzner VPS]
        P40R[rsync KGX to VPS]
        P40L[Load 5 databases into AGE on cloud]
        P40Q[Cypher query validation on cloud]
        P30 --> P40 --> P40R --> P40L --> P40Q
    end

    subgraph "Gate 3: cloud graph validated"
        G3D[Delete local KGX files]
        P40Q --> G3D
    end

    subgraph "Phase 5: dbSNP on cloud"
        P50[5.0 SNP ETL code]
        P51[5.1 Run SNP pipeline on cloud]
        P52[5.2 SNP-ClinVar merge on cloud]
        G3D --> P50 --> P51 --> P52
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
| PubMed | ~40M | ~40M+ | ~30-50GB (KGX TSV output; FTP download is ~54GB compressed) |
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
| Gate 1 | Phase 1.5 | Run medgen/gene/clinvar-etl, validate KGX | NCBI server `/export` (data migrated to laptop 2026-04-16) | DONE (2026-04-16) |
| Gate 2 | Phase 2.2 | Run pubmed/taxonomy-etl + merge-etl, validate KGX | Windows laptop C: drive | DONE (2026-04-17) |
| Gate 3 | Phase 4.0 | Load 5-db into AGE on cloud, Cypher queries pass, delete local KGX | Hetzner VPS | Pending |
| Gate 4 | Phase 5.2 | Full 6-db graph on cloud, all queries pass | Hetzner VPS | Pending |

### Coding time (bossman sessions)

| Phase | Session | What | Status |
|-------|---------|------|--------|
| 1.0 | 1 | Schema + scaffolding | DONE (2026-04-13) |
| 1.1 | 2 | Shared utilities (6 modules) | DONE (2026-04-14) |
| 1.2-1.4 | 3 | Gene + ClinVar + MedGen ETL | DONE (2026-04-14) |
| 1.5 | 4 | Merge + validation | DONE (2026-04-14) |
| Gate 1 | - | Run 3 pipelines on NCBI server, validate (data migrated to laptop 2026-04-16) | DONE (2026-04-16) |
| 2.0 | 5 | PubMed ETL | DONE (2026-04-16) |
| 2.1 | 6 | Taxonomy ETL | DONE (2026-04-16) |
| 2.2 | 7 | 5-database merge | DONE (2026-04-16) |
| Gate 2 | - | Run PubMed + Taxonomy + Gene (re-export) + merge-etl on laptop, validate | DONE (2026-04-17): 115M nodes + 693M edges, 99.99% cross-pipeline connectivity, streaming refactors required mid-gate (gene + merge both hit list-accumulate OOM on laptop-scale data) |
| 3.0 | 8 | AGE loader code + fixture smoke test (no bulk local load) | Pending |
| 4.0 | 9 | Provision Hetzner VPS, rsync KGX, load 5-db on cloud | Pending |
| Gate 3 | - | Validate cloud graph, delete local KGX files | Pending |
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
| PubMed baseline + updatefiles download (~54GB compressed, 1334 + 81 files) | 4-8 hours serial, 1-2 hours if parallelized | Gate 2 (laptop, overnight) |
| Taxonomy download (500MB) | 10 min | Gate 2 (laptop) |
| rsync KGX to Hetzner VPS (~140GB) | 6-16 hours at home Wi-Fi upload (typical 20-50 Mbps up) | Phase 4.0 |
| AGE load 5 databases (~140M nodes) on cloud | 2-6 hours | Phase 4.0 (cloud) |
| dbSNP download (100GB) | 8-16 hours | Phase 5.1 (cloud, overnight) |
| dbSNP VCF parsing (1.2B records) | 4-12 hours | Phase 5.1 (cloud) |
| dbSNP load into AGE (incremental) | 6-24 hours | Phase 5.2 (cloud) |

### Realistic calendar

| Week | What | Where | Status |
|------|------|-------|--------|
| Week 1 | Phase 1 code + Gate 1 | NCBI server `/export` | DONE (2026-04-14 to 2026-04-16). Data migrated to Windows laptop on 2026-04-16 (see `docs/context/setup/setup-03_windows_laptop.md`). |
| Week 2 | Phase 2 code + Gate 2 | Windows laptop C: drive | 2.0 + 2.1 + 2.2 code DONE (2026-04-16). Gate 2 NEXT (pubmed/taxonomy run + 5-db merge validation), runs on laptop. |
| Week 3 | Phase 3 (loader code) + Phase 4 (provision VPS, rsync from laptop, cloud load) + Gate 3 | Laptop then cloud | Pending |
| Week 4 | Phase 5 (dbSNP on cloud) + Gate 4 | Cloud | Pending |

### Why this order

1. Phases 1-2 (code + Gates 1-2): build and test all non-dbSNP pipelines on the Windows laptop. Free, fast iteration, exclusive 355GB C: drive.
2. Phase 3 (AGE loader code only): build the AGE loader module. Validate loader logic against a tiny KGX fixture locally on the laptop using Docker Desktop + a Linux PostgreSQL + AGE container (AGE round-trip smoke test). No full 5-database load locally. Rationale: a local full load + pg_dump peak (~300 GB) would exceed comfortable laptop headroom and is wasted work when the graph's final home is the cloud VPS.
3. Phase 4 (provision VPS + rsync + cloud load): provision Hetzner CX41 + 500GB volume, install PostgreSQL + AGE, rsync KGX files from the laptop to the VPS (6-16 hrs over home Wi-Fi upload), run the AGE loader on the cloud instance, validate with Cypher queries. Gate 3 passes when cloud queries return expected results. Delete laptop KGX after cloud validation passes. Single load (not laptop then cloud) avoids duplicate 2-6 hour work and the ~150GB temporary pg_dump overhead.
4. Phase 5 (dbSNP on cloud): build the SNP ETL code on the laptop, run the pipeline directly on the Hetzner VPS. dbSNP downloads and loads on the cloud instance where there's 500GB dedicated disk. No laptop storage pressure.

Schema impact: none. The schema already defines `biolink:SequenceVariant` for both ClinVar (`ClinVar:{id}`) and dbSNP (`dbSNP:rs{id}`). They are different nodes in the graph, connected by an `exact_match` edge via the RS# field in ClinVar's variant_summary. No schema changes needed at any step.

### Disk budget

Local disk (Windows laptop C: drive): 355GB free as of 2026-04-16 (exclusive, not shared). Gate 1 data migrated from NCBI server `/export` on 2026-04-16 (see `docs/context/setup/setup-03_windows_laptop.md`).

Project footprint after Gate 1 migration: Gene KGX 39GB + ClinVar KGX 2.6GB + MedGen KGX 4.7GB + FTP cache ~5GB = ~51GB.

| After step | Project footprint | Laptop C: free space |
|------------|-------------------|----------------------|
| Gate 1 (migrated, KGX for 3 databases) | ~51GB | ~304GB |
| Gate 2 (add PubMed KGX 30-50GB + PubMed FTP cache ~54GB + Taxonomy ~1-2GB) | ~136-157GB | ~198-219GB |
| Phase 3.0 (loader code + fixture smoke test only via Docker Desktop, no bulk local load) | ~136-157GB | ~198-219GB |
| Phase 4.0 (rsync KGX from laptop to VPS, delete laptop KGX after cloud validation passes) | ~60GB (FTP cache only) | ~295GB |

No local peak above 160GB. The original plan's ~280GB Phase 3 peak + ~300GB pg_dump peak have been eliminated by moving the full load to the cloud. Exclusive laptop storage eliminates the shared-volume risk of the NCBI `/export` setup.

Cloud disk (Hetzner CX41 + 500GB volume): dedicated to this project.

| After step | Cloud disk used | Cloud headroom |
|------------|----------------|----------------|
| Phase 4.0 (KGX uploaded + 5-db graph loaded; delete KGX after validation) | ~100-150GB | ~350GB |
| Phase 5 (add dbSNP) | ~250-350GB | ~150GB |

No storage problems at any step.

### Data storage

Local (current, post 2026-04-16 migration): all data on the Windows laptop C: drive under the repo-local path `C:/Users/<you>/agentic-search-data-engineering/data/`. Paths are configured in `.env` (see `docs/context/setup/setup-03_windows_laptop.md` for the full setup). FTP cache is kept for re-runs, and KGX files are deleted after rsync to the Hetzner VPS and cloud validation passes.

Prior arrangement (retired 2026-04-16): data was symlinked from the repo to `/export/home/chakrabortim2/data/` on the NCBI server. `/export` is a 4.3TB LVM volume shared across ~925 machine users with no quota protection, which made the 51GB footprint a good-citizen concern and exposed the pipeline to silent disk contention. Migrated to laptop to eliminate both risks.

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
| 2.2 | `phase/2.2-literature-taxonomy-merge` | Merged, deleted |

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
--- GATE 2: run PubMed + Taxonomy + merge-etl on Windows laptop --- NEXT
    |  pubmed-etl (overnight), taxonomy-etl
    |  kgx validate on each output
    v
Session 8: Phase 3.0  AGE loader code + fixture smoke test
    |  build AGE loader module (schema, batch insert, indexes)
    |  round-trip a tiny KGX fixture through Docker Desktop PG+AGE container
    |  NO bulk local load (reserved for cloud)
    v
Session 9: Phase 4.0  provision VPS + rsync KGX + cloud load
    |  provision Hetzner CX41 + 500GB volume
    |  install PostgreSQL + AGE on VPS
    |  rsync KGX (~140GB) from laptop to VPS (~6-16 hrs over home Wi-Fi)
    |  run AGE loader on VPS for 5 databases
    |  run Cypher test queries on cloud
    v
--- GATE 3: cloud graph validated ---
    |  delete laptop KGX intermediates
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

## Phase 2: literature + taxonomy [CODE DONE, Gate 2 NEXT]

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

Branch: `phase/2.2-literature-taxonomy-merge` (merged PR #6, deleted)

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

## Phase 3: AGE loader code (no bulk local load)

### Phase 3.0: PostgreSQL + AGE loader

Branch: `phase/3.0-age-loader`

Build the AGE loader code. Create graph schema, batch node/edge INSERT, create indexes. Round-trip a tiny KGX fixture through a local PostgreSQL + AGE instance to prove loader logic before shipping to cloud. Do NOT do the full 5-database local load (disk budget).

Deliverables:
- AGE loader module (schema creation, batched node insert, batched edge insert, index creation)
- Fixture tests using small inline KGX to assert load + Cypher round-trip
- Smoke-test script: loads fixture into local AGE, runs a handful of Cypher queries, tears down

Rationale: laptop C: drive has 355GB free, but holding the 5-database KGX (~140GB) plus a full AGE database (~80-130GB) plus a pg_dump peak would squeeze a development workstation. Loading once on the cloud avoids duplicate work. The fixture smoke test runs via Docker Desktop with a Linux PostgreSQL + AGE container; do not install AGE natively on Windows.

---

## Phase 4: provision VPS + rsync KGX + cloud load

### Phase 4.0: provision Hetzner VPS and load 5 databases on cloud

Branch: `phase/4.0-cloud-deploy`

Provision Hetzner CX41 + 500GB volume (~$25-30/month). Install PostgreSQL + AGE. rsync KGX files from the Windows laptop C: drive to the VPS (6-16 hours over home Wi-Fi upload for ~140GB). Run the AGE loader from Phase 3.0 on the VPS to load all 5 databases. Verify Cypher queries work remotely. After cloud validation passes, delete laptop KGX intermediates.

Test queries (run on cloud; same as original Phase 3 test queries):
- Gene to variant traversal (BRCA1)
- Disease to gene traversal (phenylketonuria -> PAH)
- Gene to biological process (glucose metabolism genes)

Gate 3 passes when cloud Cypher queries return the expected results.

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
  pubmed/
    test_pubmed_pipeline.py            xml streaming + mesh stubs + end-to-end (12 tests)
  taxonomy/
    test_taxonomy_pipeline.py          nodes.dmp, names.dmp, end-to-end (11 tests)
  integration/
    conftest.py                        sys.path setup
    test_merge.py                      merge dedup, stubs, validation (9 tests)
    test_cross_database_traversal.py   Gene -> ClinVar -> MedGen triangle (5 tests)
  merge/
    conftest.py                        sys.path setup
    test_five_database_merge.py        5-db orchestrator + cross-pipeline connectivity (11 tests)
```

All tests use inline fixtures (no separate fixture files). Total: 180 tests, all passing.

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
13. AGE loader (Phase 3) builds loader code only; full load moved to Phase 4 on the cloud VPS (see decision 18).
14. dbSNP runs on cloud VPS, not locally. Avoids local storage pressure.
15. Cloud deploy (Hetzner CX41 + 500GB volume, ~$25-30/month) for team access and System 3 integration.
16. Gene pipeline streams edges to disk per parser batch (append_edges) to avoid OOM on 278M edges.
17. ClinVar and dbSNP use different ID spaces (ClinVar:{id} vs dbSNP:rs{id}), no schema conflict. Connected via exact_match edges at Phase 5.2.
18. Skip the local AGE load. Phase 3.0 builds the loader + a fixture smoke test; Phase 4.0 provisions the VPS, rsyncs KGX, and loads once on the cloud. Rationale: actual `/export` free space is 284GB (not 403GB as originally budgeted), and a local full load + pg_dump peak would overflow. A single cloud load avoids ~2-6 hours of duplicate load work and eliminates the ~150GB temporary pg_dump overhead. Trade-off: lose the ability to run full-scale Cypher validation locally; mitigated by the Phase 3.0 fixture smoke test proving loader logic before rsync. Earlier Hetzner billing starts ~2 weeks sooner (~$15).
19. PubMed download is serial today ([download.py:97-104](../system-01-data-pipelines/pubmed/download.py#L97-L104)). Gate 2 runs overnight, so serial is acceptable. If Gate 2 retries become needed, switch to `ThreadPoolExecutor(max_workers=8)` to cut 4-8 hours to ~1-2 hours.
20. Local development and all bulk data live on the user's Windows laptop C: drive (355GB exclusive), not the NCBI shared server `/export`. Gate 1 data was migrated on 2026-04-16 after the `/export` free-space audit revealed 284GB shared with ~925 users and no quota protection. Setup steps captured in `docs/context/setup/setup-03_windows_laptop.md`. Phase 3.0 fixture smoke test uses Docker Desktop + a Linux PostgreSQL + AGE container. Phase 4 rsync to Hetzner runs over home Wi-Fi upload (6-16 hrs for ~140GB). No NIH funding or policy ties the pipeline to NCBI infrastructure; all NCBI data is public FTP.

---

## Reference files

| File | Read when |
|------|-----------|
| `docs/context/setup/setup-03_windows_laptop.md` | First time setting up the repo on a laptop; migrating from `/export`; verifying `.env` paths |
| `docs/System_1_data_engineering_plan.md` | Before any pipeline work |
| `docs/learnings.md` | After any pipeline run (add problems and solutions) |
| `docs/data_inventory.md` | After any pipeline run (add download and output details) |
| `reference-repos/ncbi_ai_agents/KG/pipeline/src/glucose_metabolism_kg/` | Building shared utilities, merger, exporter |
