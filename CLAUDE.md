# CLAUDE.md

Claude Code instructions for `agentic-search-data-engineering`. This IS a software project.

This repo covers System 1 (data pipelines) and System 2 (knowledge graph) only. System 3 (search agent, FastAPI, LangGraph, UI, delivery channels) lives in a separate repository. Do not add System 3 dependencies or code here.

Stack: Python 3.11+, LinkML, BioLink 4.x, KGX, PostgreSQL 15 + Apache AGE.

---

## Current focus

| Priority | System | Status |
|----------|--------|--------|
| 1 | System 1: data pipelines | Building now. Phase 1: Gene + ClinVar + MedGen (core triangle). |
| 2 | System 2: knowledge graph | Schema defined alongside pipelines. PostgreSQL + AGE load after Phase 1. |
| 3 | System 3: search agent | Lives in a separate repository. Do not build here. |

---

## Architecture

Three systems. This repo holds System 1 and System 2 only. System 3 lives in a separate repository.

```
System 1: data engineering (this repo)
  Input:  NCBI FTP bulk files
  Output: BioLink-compliant KGX files (nodes.tsv + edges.tsv per database)

System 2: knowledge graph (this repo)
  Input:  KGX files from System 1
  Output: Merged graph in PostgreSQL + Apache AGE, queryable via openCypher

System 3: search agent (separate repo, do not build here)
  Input:  User query
  Output: Cited multi-database answer from graph + on-demand ELink/EFetch
```

---

## Reference docs (in docs/)

| Doc | What it is | Read when |
|-----|-----------|-----------|
| `System_1_data_engineering_plan.md` | Detailed build plan for all 6 ETL pipelines | Before writing any pipeline code |
| `NCBI_databases_and_APIs_reference.md` | Raw data on all 39 NCBI databases, FTP paths, record counts | Checking FTP URLs and file formats |
| `architecture/Biolink_repos_explained.md` | BioLink/LinkML reference | Schema design |
| `architecture/Three_layer_data_architecture.md` | Layer 1 (graph), Layer 2 (on-demand API), Layer 3 (enrichment). What this repo does vs System 3. | Understanding system boundaries |
| `context/Innovation_proposal_2026.md` | Full system proposal | Context and framing |
| `bossman_execution_plan.md` | Phase-by-phase execution plan for System 1 pipelines (bossman mode reference) | Before starting any bossman phase |

## Canonical reference pipeline

The most valuable reference is an existing 9-step BioLink pipeline at:

`reference/ncbi_ai_agents-ncbi-kg/KG/pipeline/src/glucose_metabolism_kg/`

Patterns to copy directly:

- `utils.py:91-104` - idempotent FTP download with cache
- `utils.py:35-86` - NCBI Entrez retry with exponential backoff and rate limiting
- `assembly.py` - dedup, dangling-edge validation, MONDO stub injection
- `export.py` - KGX TSV + JSON-LD + Neo4j CSV export (Neo4j CSV part needs adapting for AGE)
- `config.py` - dataclass-based configuration with `__post_init__` directory creation
- `variants.py` - chunked DataFrame processing for large gzipped files

Reference BioLink schema (8 categories, 15 predicates) is encoded in `assembly.py` and `export.py`. Copy categories and predicates verbatim where they apply.

Reference repo's own CLAUDE.md (full architecture and file map) is at `reference/ncbi_ai_agents-ncbi-kg/CLAUDE.md`. Skim it before designing new pipelines.

---

## Build order (System 1)

Phase 1 first: Gene + ClinVar + MedGen. These three form the core triangle and share cross-references (`mim2gene_medgen` maps all three). Build them together before adding PubMed or Taxonomy.

```
Phase 1 (weeks 1-2):  Gene ETL -> ClinVar ETL -> MedGen ETL -> first merge test
Phase 2 (weeks 3-4):  PubMed ETL -> Taxonomy ETL -> SNP ETL -> full merge
Phase 3 (weeks 5-6):  Search agent (LangGraph, 8 agents, FastAPI)
Phase 4 (weeks 7-8):  Web UI, CLI, eval pipeline, deploy
```

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

| Skill | Purpose | Invocation |
|-------|---------|-----------|
| bossman-mode | Autonomous execution with agent teams: parallel builders, judge, skill chain per phase | `/bossman` |
| first-principles | Explains BioLink, LangGraph, AGE, LinkML concepts | `what is`, `explain` |
| objective-review | Critical feedback, not agreement | `/objective-review` |
| socratic-questioning | Clarifying questions before big decisions | `should I`, `help me decide` |
| best-practices | Session-start checklist, change safety, commit hygiene | Read at session start |
| qa-gate | Post-task quality gate before any pipeline commit | Read before commit |
| release-workflow | End-to-end release: chains qa-gate then ship | Read before release |
| visualization-standards | Mermaid and schema diagram standards for pipelines and KGX flows | Read when diagramming |
| architecture-patterns | ETL + KG architectural patterns adapted from ncbi_ai_agents reference | Read before new pipeline |
| documentation-standards | Doc style rules for all .md and docstrings in this repo | Read before writing docs |
| python-code-standards | Python coding standards for ETL pipelines and graph loaders | Read before writing Python |
| testing-standards | Testing standards for ETL, BioLink validation, KGX export | Read before writing tests |
| eval-harness | Pipeline and KG quality gates (BioLink, dangling-edge, provenance) | Read before pipeline run |
| repo-dive | First-principles analysis of a reference/ symlinked repo | `/repo-dive <path>` |
| skill-adapt-verify | Verify a copied/adapted skill for stale paths, wrong-repo terms, style violations | `/skill-adapt-verify <path>` |
| ship | Sync docs then commit and push phase branch | `/ship` |

---

## Key rules

- `parallel-first`: all ETL steps that are independent run in parallel
- `attack-the-constraint`: don't optimize non-bottlenecks. FTP download is the bottleneck in week 1, not parsing.
- `bossman-mode`: once plan is agreed, execute autonomously per phase
- `decision-logging`: log DECISIONS.md when choosing between alternatives (e.g. Neo4j Community vs AuraDB, LinkML vs raw YAML)
- `boil-the-lake`: if the full pipeline is cheap to build, build the full version
- `preserve-your-thinking`: on architecture judgment calls, ask first
- `writing-style`: no em dashes, sentence case, no bold

---

## Git workflow

Work on phase branches, not directly on `main`. Branch naming: `phase/N.M-short-description`. One MR per phase; merge into `main` after user review. No Co-Authored-By lines ever.

Gitignored: `data/raw/`, `data/ftp_cache/`, `.env`, `*.gz`, `*.xml.gz`, `node_modules/`, `__pycache__/`, `venv/`

---

Last updated: 2026-04-13
