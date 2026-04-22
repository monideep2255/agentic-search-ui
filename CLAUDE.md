# CLAUDE.md

Claude Code instructions for `agentic-search-data-engineering`. This IS a software project.

This repo covers System 1 (data pipelines) and System 2 (knowledge graph) only. System 3 (search agent, FastAPI, LangGraph, UI, delivery channels) lives in a separate repository. Do not add System 3 dependencies or code here.

Stack: Python 3.11+, LinkML, BioLink 4.x, KGX, PostgreSQL 15 + Apache AGE.

---

## Current focus

| Priority | System | Status |
|----------|--------|--------|
| 1 | System 1: data pipelines | V1 COMPLETE (2026-04-22). Phase 4.0 + Gate 3 PASSED. 5-database AGE graph live on Hetzner CPX42 (46.225.128.133): 115,406,761 nodes + 693,295,991 edges across 11 vertex labels and 14 edge labels. All 7 Cypher smoke queries pass (Q1 BRCA1 224ms, Q2 PKU 6ms, Q3 glucose 28ms, Q4 TP53 26s most-cited gene, Q5 taxon 14ms, Q6 16s full count, Q7 24ms). Loader's `index_builder.py` updated to do all four index passes (functional B-tree + graphid PK + GIN + edge-endpoint B-tree) plus ANALYZE automatically as Steps 7-8. Postgres tuned for 16 GB box. See `docs/Knowledge_graph_on_server_reference.md` for the live-graph A-Z reference. |
| 2 | System 2: knowledge graph | AGE graph live on cloud VPS, 115.4M nodes + 693.3M edges loaded 2026-04-22, queryable via openCypher. See `docs/Knowledge_graph_on_server_reference.md`. |
| 3 | System 3: search agent | Lives in a separate repository. Do not build here. |

---

## Architecture

```
System 1: data pipelines (this repo)
  NCBI FTP -> parse -> BioLink map -> LinkML validate -> KGX files

System 2: knowledge graph (this repo)
  KGX files -> normalize -> merge -> PostgreSQL + AGE -> openCypher
```

This repo builds Layer 1 (fully ingested knowledge graph) of a three-layer data architecture. Layers 2 and 3 (on-demand API, enrichment) are query-time concerns in a separate repo. See `docs/architecture/Three_layer_data_architecture.md`.

---

## Reference docs (in docs/)

| Doc | What it is | Read when |
|-----|-----------|-----------|
| `System_1_data_engineering_plan.md` | Detailed build plan for all 5 ETL pipelines | Before writing any pipeline code |
| `NCBI_databases_and_APIs_reference.md` | Raw data on all 39 NCBI databases, FTP paths, record counts | Checking FTP URLs and file formats |
| `architecture/Biolink_repos_explained.md` | BioLink/LinkML reference | Schema design |
| `architecture/Three_layer_data_architecture.md` | Layer 1 (graph), Layer 2 (on-demand API), Layer 3 (enrichment). What this repo does vs System 3. | Understanding system boundaries |
| `architecture/Merge_logic_explained.md` | First-principles walkthrough of the 5-database merge: streaming passes, dedup strategy, stub injection, dangling-edge detection | Before modifying merger.py or writing Phase 3 loader code |
| `architecture/AGE_loader_explained.md` | First-principles walkthrough of the Phase 3 AGE loader: KG structure, why AGE over Neo4j, performance expectations, hosting comparison (Hetzner vs Netcup vs Contabo, US vs EU) | Before writing any Phase 3 loader or Phase 4 cloud-deploy code |
| `context/Innovation_proposal_2026.md` | Full system proposal | Context and framing |
| `bossman_execution_plan.md` | Phase-by-phase execution plan for System 1 pipelines (bossman mode reference) | Before starting any bossman phase |
| `context/setup/setup-03_windows_laptop.md` | One-time setup guide for Windows laptop (repo clone, symlinks, venv, data rsync) | When setting up a new local dev environment |
| `context/setup/setup-04_hetzner_vps.md` | End-to-end Hetzner CPX42 provisioning: SSH keys from personal computer and work laptop, rsync install, PostgreSQL + AGE install, pre-Phase-4.0 verification | Before Phase 4.0 cloud deploy work |
| `context/setup/setup-05_rsync_windows.md` | First-principles rsync on a locked-down Windows laptop: Scoop + cwRsync install, cygdrive path format, cwRsync vs Windows OpenSSH pipe incompatibility, HOME env var fix, exact working command, transfer time estimate | Before running Phase 4.0 rsync from the work laptop |
| `Knowledge_graph_on_server_reference.md` | A-Z operations reference for the live V1 graph on Hetzner CPX42: SSH access, Cypher query examples, index listing, node/edge counts, cost breakdown, snapshot procedure | Before querying or maintaining the live graph |
| `Project_overview_A_to_Z.md` | Single-source-of-truth navigation hub with pointers into every other doc | First doc to read for project orientation |
| `architecture/Data_mapping_and_ontology_explained.md` | A-Z walkthrough of how raw NCBI data becomes a BioLink graph: CURIEs, per-pipeline mapping rules, merge logic, BioLink 4.x compliance | Before writing any new pipeline or auditing existing mapping |
| `architecture/Technical_reference_data_engineering.md` | End-to-end technical walkthrough of the V1 system: architecture, schema, indexing, Cypher patterns, performance baselines, lessons | Engineering deep-dive on what was built and why |
| `visualizations/Architecture_diagram.md` + `visualizations/Schema_visualization.md` | Mermaid diagrams of system architecture, ETL flow, deployment, and BioLink schema with sample CURIEs | When orienting visually, in slides, or onboarding others |

## Canonical reference pipeline

The most valuable reference is an existing 9-step BioLink pipeline at:

`reference-repos/ncbi_ai_agents/KG/pipeline/src/glucose_metabolism_kg/`

Patterns to copy directly:

- `utils.py:91-104` - idempotent FTP download with cache
- `utils.py:35-86` - NCBI Entrez retry with exponential backoff and rate limiting
- `assembly.py` - dedup, dangling-edge validation, MONDO stub injection
- `export.py` - KGX TSV + JSON-LD + Neo4j CSV export (Neo4j CSV part needs adapting for AGE)
- `config.py` - dataclass-based configuration with `__post_init__` directory creation
- `variants.py` - chunked DataFrame processing for large gzipped files

Reference BioLink schema (8 categories, 15 predicates) is encoded in `assembly.py` and `export.py`. Copy categories and predicates verbatim where they apply.

Reference repo's own CLAUDE.md (full architecture and file map) is at `reference-repos/ncbi_ai_agents/CLAUDE.md`. Skim it before designing new pipelines.

---

## Build order (System 1)

Phase 1 first: Gene + ClinVar + MedGen. These three form the core triangle and share cross-references (`mim2gene_medgen` maps all three). Build them together before adding PubMed or Taxonomy.

```
Phase 1 (weeks 1-2):  Gene ETL -> ClinVar ETL -> MedGen ETL -> first merge test  [DONE 2026-04-14]
Phase 2 (weeks 3-4):  PubMed ETL -> Taxonomy ETL -> five-database merge  [DONE 2026-04-17]
Phase 3 (weeks 5-6):  AGE loader code -> Cypher validation (loader code only; no local load)  [DONE 2026-04-19]
Phase 4 (week 7):     Cloud deploy: provision Hetzner VPS -> rsync KGX from laptop -> load into AGE on cloud -> Gate 3 = V1 complete  [DONE 2026-04-22: V1 complete, 7 Cypher smoke queries passed, post-load tuning (GIN + edge B-tree + ANALYZE + postgres.conf) folded back into loader's index_builder.py]
```

System 3 (search agent, FastAPI, LangGraph, UI) is tracked in the separate repository. Do not build here.

---

## Pipeline pattern (every ETL follows this)

```
Step 1: Download  - FTP bulk download, idempotent (skip if unchanged)
Step 2: Parse     - database-specific parser, output Python objects
Step 3: Map       - BioLink mapper: assign categories, predicates, canonical IDs
Step 4: Validate  - LinkML validator, reject with reason (never silent discard)
Step 5: Export    - KGX format: nodes.tsv + edges.tsv with provenance on every row
```

Shared utilities live in `system-01-data-pipelines/shared/`. Never duplicate across pipelines.

---

## Provenance: non-negotiable

Every node: `id`, `category`, `name`, `source`, `source_url`, `xrefs`
Every edge: `subject`, `predicate`, `object`, `source`, `source_url` + evidence fields

Every fact must be clickable back to its NCBI source record. This is the trust moat.

---

## Data source adapter pattern

When adding new NCBI data sources, use optional adapters instead of a monolithic interface. Each data source implements only the adapters that apply to its capabilities. Derived from OpenClaw's channel plugin architecture (see `reference-repos/personal-os/Reference-repos/openclaw-Deep-Dive/`).

Adapter types:
- `QueryAdapter` (required): accepts a structured query, returns results
- `FacetAdapter` (optional): supports faceted search (PubMed has this; Gene does not)
- `CitationAdapter` (optional): returns structured citation metadata (PubMed, ClinVar)
- `RelationshipAdapter` (optional): can traverse entity relationships (Gene, MedGen)
- `StreamingAdapter` (optional): supports streaming large result sets (dbSNP)

Apply when: designing the System 3 data source abstraction or adding a new NCBI database to the pipeline. The ETL pipelines (System 1) follow the 5-step pattern above. The adapter pattern applies to query-time interfaces in System 3.

The core query pipeline checks adapter availability before attempting operations. If a source lacks `FacetAdapter`, the search agent skips faceted refinement for that source. No "not implemented" exceptions, no silent no-ops.

---

## Sub-agents

| Agent | Magic words | Purpose |
|-------|-------------|---------|
| first-principles | `what is`, `explain`, `how does X work` | Explain technical concepts |
| socratic | `should I`, `help me decide`, `I'm stuck` | Clarifying questions before advice |
| objective-review | `review this`, `is this good`, `am I missing` | Critical feedback |
| action-planner | `plan`, `action items`, `todos` | Break work into tasks |
| git-sync | `sync`, `push`, `pull` | GitHub operations |
| docs-sync | `update docs`, `sync docs` | Update documentation |

---

## Skills

User-invocable skills (slash commands):

| Skill | Purpose | Invocation |
|-------|---------|-----------|
| bossman-mode | Autonomous execution with agent teams | `/bossman` |
| objective-review | Critical feedback, not agreement | `/objective-review` |
| repo-dive | First-principles analysis of a reference-repos/ repo | `/repo-dive <path>` |
| skill-adapt-verify | Verify adapted skill for stale paths and style violations | `/skill-adapt-verify <path>` |
| ship | Sync docs, commit, push phase branch | `/ship` |

Auto-read skills (loaded by other skills or before specific tasks): best-practices, qa-gate, release-workflow, visualization-standards, architecture-patterns, documentation-standards, python-code-standards, testing-standards, eval-harness.

All rules are in `.claude/rules/` and loaded automatically. No need to duplicate here.

---

Last updated: 2026-04-22
