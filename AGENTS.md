# AGENTS.md

Instructions for `agentic-search-data-engineering`. For all AI agents (Gemini, Copilot, Codex, GPT, etc.). Exact same content as CLAUDE.md.

This repo covers System 1 (data pipelines) and System 2 (knowledge graph) only. System 3 (search agent, FastAPI, LangGraph, UI, delivery channels) lives in a separate repository. Do not add System 3 dependencies or code here.

Stack: Python 3.11+, LinkML, BioLink 4.x, KGX, PostgreSQL 15 + Apache AGE.

---

## Current focus

| Priority | System | Status |
|----------|--------|--------|
| 1 | System 1: data pipelines | Phase 1 and Gate 1 complete (67.5M Gene, 4.4M ClinVar, 198K MedGen nodes produced on real data). Phase 2 complete: Gate 2 done (2026-04-17), 5-database merge validated on real data. Phase 3 complete: AGE loader done (2026-04-19), 5-node + 3-edge round-trip smoke test passed via Docker Desktop. Phase 4 next: provision Hetzner VPS, rsync KGX, cloud load. |
| 2 | System 2: knowledge graph | AGE loader module built (system-02-knowledge-graph/loader/). Full load deferred to Phase 4 on cloud VPS. |
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
Phase 4 (week 7):     Cloud deploy: provision Hetzner VPS -> rsync KGX from laptop -> load into AGE on cloud -> Gate 3 = V1 complete
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

Last updated: 2026-04-19
