# Project setup and onboarding

Everything needed to go from zero to writing the first ETL pipeline. Do these in order.

This repository covers System 1 (data pipelines) and System 2 (knowledge graph) only. System 3 (search agent, FastAPI, LangGraph, UI, delivery channels) lives in a separate repository. Do not add System 3 dependencies or code here.

## Table of contents

- [Phase 0: scope cleanup (do this first)](#phase-0-scope-cleanup-do-this-first)
- [Phase 1: context (understand before building)](#phase-1-context-understand-before-building)
- [Phase 2: environment setup (prerequisites before first pipeline run)](#phase-2-environment-setup-prerequisites-before-first-pipeline-run)
- [Phase 3: first code orientation](#phase-3-first-code-orientation)
- [What done looks like (System 1 exit criteria)](#what-done-looks-like-system-1-exit-criteria)

---

## Phase 0: scope cleanup (do this first)

The initial scaffold created folders for all three systems. Before starting Phase 1, delete the System 3 folders:

```bash
rm -rf api cli eval mcp-server search-agent web-ui
```

Keep only: `data-pipelines/`, `knowledge-graph/`, `docs/`, `reference-repos/`. Everything System 3 belongs in the separate repo.

---

## Phase 1: context (understand before building)

Do these before writing any code. Each step answers a specific question.

### Step 1: review the ncbi-kg repository inside out

What: deep dive the existing NCBI knowledge graph repo (the NLM/NCBI KG proof-of-concept), specifically the KG folder structure and pipeline code.

Why: it already has working BioLink pipelines, a validated schema, and lessons from production data. Do not reinvent what already works.

What to extract:
- Which pipeline patterns are reusable (FTP download, BioLink mapping, validation approach)
- What schema decisions were made and why
- What broke or was left unfinished
- MCP server architecture (already published and installable)

Source: `reference-repos/ncbi_ai_agents/` (symlink, ncbi-kg branch)

Action: read the repo end to end, focusing on `KG/pipeline/src/glucose_metabolism_kg/`. Look for pipeline scripts, schema definitions, BioLink mapping code, and any validation logic. The reference symlinks are your "Confluence documentation" — read for context, do not bulk-vendor files.

### Step 2: review the proposal and architecture docs

What: read the innovation proposal and architecture Q&A.

Why: the proposal defines what we are building. The architecture Q&A records every decision made during the April 2 and April 5 brainstorming sessions.

Files (in order):
1. `docs/System_1_data_engineering_plan.md` — what we're building and why (read first)
2. `docs/architecture/Agentic_search_architecture_QA.md` — every architecture decision, with evidence
3. `docs/context/Innovation_proposal_2026.md` — the full proposal (context and framing)
4. `docs/planning/Two_track_plan.md` — personal build vs NCBI proposal (parallel tracks)
5. `docs/planning/Personal_build_plan.md` — 8-week execution plan, cost model

Action: read all five. Note any open questions in DECISIONS.md.

### Step 3: review Anne's data pipeline (ncbi-kg reference)

What: review the data engineering approach from the NLM/NCBI KG pipeline built by Anne's team.

Why: this is the closest existing implementation to what we're building. Avoids repeating their mistakes and lets us reuse validated patterns directly.

Where: `reference-repos/ncbi_ai_agents/KG/pipeline/src/glucose_metabolism_kg/` (canonical, this is where the working code now lives) — also mirrored at `reference-repos/personal-os/NIH/KG/Use-case-WG/PoC/Pipeline/glucose_metabolism_kg_package/`

Files:
- `README.md` — pipeline overview
- `documentation_data_selection.md` — data selection rationale
- `glucose_metabolism_kg_package/glucose_metabolism_kg/` — working pipeline code

What to extract:
- FTP download patterns (idempotent downloads, checksum verification)
- BioLink mapping approach (how they handled entity ID normalization)
- Validation pipeline (what the BioLink validator catches vs. what it misses)
- Merge strategy (how they deduplicated nodes across databases)
- What they got right, what they left unfinished

Action: add any reusable patterns to `docs/` as a reference doc. Flag anything that conflicts with our DECISIONS.md.

### Step 4: review ncbi_ai_agents .claude config for reusable patterns

What: review the `.claude/` config from the ncbi_ai_agents repo to identify skills and agents worth porting.

Why: that repo was built for a similar domain (NCBI + knowledge graphs). Its skills encode patterns for BioLink, Cypher, Python data pipelines, and testing that we should reuse rather than reinvent.

Where: `reference-repos/ncbi_ai_agents/.claude/` and `reference-repos/personal-os/.claude/`

Review:

- `ncbi_ai_agents-ncbi-kg/.claude/agents/` — 4 agents: `biomedical-expert.md`, `doc-sync.md`, `first-principles.md`, `git-sync.md`
- `ncbi_ai_agents-ncbi-kg/.claude/skills/` — 15 skills including: `architecture-patterns`, `best-practices`, `python-code-standards`, `testing-standards`, `documentation-standards`
- `personal-os-work/.claude/skills/` — `repo-dive`, `eval-harness`, `ship`, `objective-review`, `first-principles`
- `personal-os-work/.claude/hooks/` — `scan-secrets.sh`, `session-start.sh`, `log-git-commands.sh`
- `personal-os-work/.claude/rules/` — `system-design-patterns.md`, `dependency-tracking.md`

Caveat: the working directory contains a space (`Tech Skills/`), which confuses the Explore subagent. Review these files manually with `Read` and `Glob` rather than dispatching a subagent.

Action: for each component, decide: port as-is, adapt for ETL, or skip. Skip anything tied to deploy pipelines (`qa-gate`, `release-workflow`, `phase-complete`, `self-healing-deploy`, `nl-cypher-loop`, `visualization-standards`) — those are System 3 / Railway-specific. Log any behavioral changes in DECISIONS.md.

### Step 5: deep dive this repo + update CLAUDE.md

What: after steps 1-4, walk through the current `CLAUDE.md` and `AGENTS.md` and update anything that changed.

Specifically:
- Update the "current focus" table to reflect what Phase 1 actually starts with
- Update the "reference docs" table if paths changed
- Add any new decisions to `DECISIONS.md` that came out of the context review
- Flag any architecture conflicts between the ncbi-kg repo review and our plan

Decision logging: this repo maintains `DECISIONS.md` as a running log of every architecture and implementation choice, modeled on `personal-os-work/NIH/Agentic-Search/Data/reference/Decision_log_agentic_search.md`. Every time a non-trivial choice is made (database, library, pipeline pattern, schema approach), log it with: decision, what was said, what it changed, alternatives considered. Do not re-debate logged decisions without updating the log.

### Step 6: ask Monideep clarification questions

After completing steps 1-5, stop and ask Monideep the following before writing any code:

1. Which docs/ paths are final? (The CLAUDE.md references subdirs planning/, architecture/, context/ — confirm these match the actual folder structure.)
2. Are there any pipeline patterns from Anne's code (Step 3) or the ncbi-kg repo (Step 1) that should be copied directly into `data-pipelines/shared/`?
3. Any additional skills or agents from the ncbi_ai_agents `.claude/` (Step 4) that should be ported before starting Phase 1?
4. Any decisions made since April 6 that need to be added to DECISIONS.md before writing the first pipeline?
5. Any other context — people, constraints, or access issues — that would change how Phase 1 is executed?

Do not start Phase 2 or write any pipeline code until Monideep has answered these.

---

## Phase 2: environment setup (prerequisites before first pipeline run)

### 2a. Python environment

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

Requirements to install (add to `requirements.txt` as you go):

```
# BioLink / schema
linkml>=1.7
biolink-model>=4.0
kgx>=2.3

# Data processing
lxml>=5.0          # XML parsing (ClinVar, PubMed)
pandas>=2.0
pyarrow>=15.0

# Knowledge graph (System 2: PostgreSQL + Apache AGE)
# Apache AGE is a PostgreSQL extension - no separate Python driver exists.
# Communicate with it via psycopg2 + raw SQL calling the cypher() function.
psycopg2-binary>=2.9

# Utilities
requests>=2.31
tqdm>=4.66
python-dotenv>=1.0
pyyaml>=6.0

# Testing
pytest>=8.0
pytest-cov>=5.0
```

Note: System 3 dependencies (LangGraph, FastAPI, Redis, LangSmith, React) go in a separate repository.

### 2b. Environment variables

```bash
cp env.example .env
# Fill in:
# NCBI_API_KEY=    <- get from https://www.ncbi.nlm.nih.gov/account/
# PG_HOST=localhost
# PG_PORT=5432
# PG_USER=postgres
# PG_PASSWORD=     <- set when installing PostgreSQL
# PG_DBNAME=ncbi_kg
```

### 2c. PostgreSQL + Apache AGE install

Apache AGE is a PostgreSQL extension written in C. There is no PyPI package. From Python you reach it through `psycopg2` + raw SQL that wraps Cypher in a `cypher('graph_name', $$ ... $$)` call.

```bash
# macOS (Homebrew) — Postgres
brew install postgresql@15
brew services start postgresql@15

# Build Apache AGE against this Postgres install
# Download a release that matches PG 15 from https://github.com/apache/age/releases
cd ~/src && curl -LO https://github.com/apache/age/releases/download/PG15%2Fv1.5.0-rc0/apache-age-1.5.0-src.tar.gz
tar xzf apache-age-1.5.0-src.tar.gz && cd apache-age-1.5.0
make PG_CONFIG=$(brew --prefix postgresql@15)/bin/pg_config install

# Create the database and enable AGE
psql postgres -c "CREATE DATABASE ncbi_kg;"
psql -d ncbi_kg -c "CREATE EXTENSION age;"
psql -d ncbi_kg -c "LOAD 'age';"
psql -d ncbi_kg -c "SET search_path = ag_catalog, \"\$user\", public;"
psql -d ncbi_kg -c "SELECT * FROM ag_catalog.create_graph('ncbi_kg');"
```

Note on Homebrew Postgres: the default superuser is your macOS username (no password), not `postgres`. Adjust `PG_USER` in `.env` accordingly, or create a `postgres` role explicitly.

Decision: PostgreSQL + AGE over Neo4j. Neo4j Community requires 64GB+ RAM for large graphs; PostgreSQL + AGE is disk-based and handles 150M nodes on 8GB RAM. Saves $100-200/month. See DECISIONS.md entry #28.

### 2d. Verify everything connects

```python
# Test NCBI API key
import os, requests
r = requests.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi",
                 params={"api_key": os.environ["NCBI_API_KEY"], "retmode": "json"})
print(r.json()["einforesult"]["dblist"][:5])
# Expected: ['pubmed', 'protein', 'nuccore', 'ipg', 'nucleotide']
```

```python
# Test PostgreSQL + AGE connection
import os, psycopg2
conn = psycopg2.connect(
    host=os.environ["PG_HOST"],
    dbname=os.environ["PG_DBNAME"],
    user=os.environ["PG_USER"],
    password=os.environ.get("PG_PASSWORD", ""),
)
conn.set_session(autocommit=True)
cur = conn.cursor()
cur.execute("LOAD 'age';")
cur.execute('SET search_path = ag_catalog, "$user", public;')
cur.execute("SELECT * FROM ag_catalog.create_graph('test_graph');")
cur.execute("SELECT * FROM ag_catalog.drop_graph('test_graph', true);")
print("PostgreSQL + AGE connected")
# Expected: prints "PostgreSQL + AGE connected" with no exceptions
conn.close()
```

Both must pass before starting any pipeline.

---

## Phase 3: first code orientation

After setup, review these before writing the first pipeline:

1. `DECISIONS.md` — architecture decisions already made. Do not re-debate these without updating the log.
2. `docs/System_1_data_engineering_plan.md` section "Pipeline architecture" — the 5-step pattern every ETL must follow.
3. `docs/System_1_data_engineering_plan.md` section "Build order" — Phase 1 first (Gene + ClinVar + MedGen), not any other order.
4. `docs/NCBI_databases_and_APIs_reference.md` — exact FTP paths and file sizes before downloading anything.

---

## What done looks like (System 1 exit criteria)

From `docs/System_1_data_engineering_plan.md`:

- [ ] 6 ETL pipelines producing valid KGX files
- [ ] Every node has a `source_url` (clickable NCBI link)
- [ ] Every edge has `source` and provenance properties
- [ ] SSSOM mapping files for all cross-database identifier resolutions
- [ ] BioLink validator passes on all KGX files
- [ ] Merge report showing deduplication stats (nodes before/after)
- [ ] KGX files loaded into PostgreSQL + AGE graph (System 2 ready)

---

*Created: 2026-04-06*
