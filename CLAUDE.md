# CLAUDE.md

Claude Code instructions for `agentic-search-data-engineering`. This IS a software project.

Stack: Python 3.11+, FastAPI, LangGraph, Neo4j, React, LinkML, KGX.

---

## Current focus

| Priority | System | Status |
|----------|--------|--------|
| 1 | **System 1: data pipelines** | Building now. Phase 1: Gene + ClinVar + MedGen (core triangle). |
| 2 | **Knowledge graph** | Schema defined alongside pipelines. Neo4j load after Phase 1. |
| 3 | **Search agent** | Weeks 5-6. Do not start until 6-database graph is loaded. |

---

## Architecture

Three systems. Build in order. Do not jump ahead.

```
System 1: data engineering
  Input:  NCBI FTP bulk files
  Output: BioLink-compliant KGX files (nodes.tsv + edges.tsv per database)

System 2: knowledge graph
  Input:  KGX files from System 1
  Output: Merged graph in Neo4j, queryable via Cypher

System 3: search agent
  Input:  User query
  Output: Cited multi-database answer from Neo4j + on-demand ELink/EFetch
```

---

## Reference docs (in docs/)

| Doc | What it is | Read when |
|-----|-----------|-----------|
| `System_1_data_engineering_plan.md` | Detailed build plan for all 6 ETL pipelines | Before writing any pipeline code |
| `NCBI_databases_and_APIs_reference.md` | Raw data on all 39 NCBI databases, FTP paths, record counts | Checking FTP URLs and file formats |
| `planning/Personal_build_plan.md` | 8-week execution plan, repo structure, cost model | Session planning |
| `planning/Two_track_plan.md` | Two-track execution strategy | Planning sessions |
| `architecture/Agentic_search_architecture_QA.md` | Full architecture Q&A and decisions | Architecture decisions |
| `architecture/Biolink_repos_explained.md` | BioLink/LinkML reference | Schema design |
| `context/KG_prototype_feedback.md` | SME feedback and query patterns that define quality bar | Designing CQ tests |
| `context/Decision_log_agentic_search.md` | Architecture decisions already made | Before re-deciding something |
| `context/Innovation_proposal_2026.md` | Full system proposal | Context and framing |
| `context/Vision_of_success.md` | Vision and success criteria | Context and framing |

Reference symlinks: `reference/ncbi_ai_agents/` (prior work), `reference/personal-os-work/`

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

Shared utilities live in `data-pipelines/shared/`. Never duplicate across pipelines.

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

| Skill | Invocation |
|-------|-----------|
| bossman-mode | `/bossman` - autonomous execution after plan is agreed |
| first-principles | Explains BioLink, LangGraph, Neo4j, LinkML concepts |
| objective-review | `/objective-review` - critical feedback |
| socratic-questioning | Clarifying questions before big decisions |

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

Work on `main`. Clear descriptive commits. No Co-Authored-By lines ever.

Gitignored: `data/raw/`, `data/ftp_cache/`, `.env`, `*.gz`, `*.xml.gz`, `node_modules/`, `__pycache__/`

---

## Cost targets (from Personal_build_plan.md)

- Claude Code Max: $100/month (already paying)
- LLM API: $50-150/month (Sonnet for search, Haiku for eval)
- VPS: $25-50/month (Hetzner CX31 or DigitalOcean)
- Total 2-month budget: $300-500 cash

Frugal principle: lead with free/cheapest tier. Neo4j Community (free), LangSmith free tier (5K traces/month), PostHog free tier (1M events/month).

---

*Created: 2026-04-06*
