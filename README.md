# Agentic search UI

Agentic search agent for querying NCBI biomedical data across a 115M-node knowledge graph and 30+ live APIs.

Takes natural language questions about genes, diseases, variants, publications, and taxonomy. Returns cited answers with links back to NCBI source records. Built with FastAPI, LangGraph, and React.

---

## Architecture

This is System 3 of a three-system project. System 1 (ETL pipelines) and System 2 (knowledge graph) built the graph. System 3 queries it.

| Layer | What | Access method | Latency |
|-------|------|---------------|---------|
| Layer 1: knowledge graph | 5 NCBI databases (Gene, ClinVar, MedGen, PubMed, Taxonomy) pre-ingested into PostgreSQL + AGE | Cypher queries via psycopg2 (read-only) | <10ms per query |
| Layer 2: on-demand NCBI APIs | 30+ databases reached at query time via EFetch, ELink, dbSNP REST | httpx async calls | 200-500ms per call |
| Layer 3: enrichment APIs | PubTator3, LitVar2, LitSense, ClinicalTrials.gov | httpx async calls | 500ms-2s per call |

Agent loop for every query:

```
Guardrail -> Think -> Plan -> Act -> Write
```

Multi-model harness routes each step to the appropriate model tier (guard, plan, or synth) based on cost and capability.

---

## Tech stack

| Component | Technology |
|-----------|-----------|
| Backend API | FastAPI + Uvicorn |
| Agent orchestration | LangGraph |
| LLM access | LiteLLM (multi-provider: Anthropic, OpenAI) |
| Knowledge graph | PostgreSQL 15 + Apache AGE on Hetzner CPX42 |
| User data | PostgreSQL (separate instance) |
| Caching | Redis |
| Frontend | React |
| Auth | python-jose (JWT) |
| Observability | LangSmith |

---

## Status

IN PROGRESS: baseline setup (Phase 1).

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 1 | FastAPI skeleton + auth + empty chat + React shell + SSE streaming | In progress |
| Phase 2 | cypher_query tool + LangGraph agent loop + first end-to-end query | Planned |
| Phase 3 | Additional tools + guardrail + citation formatting | Planned |
| Phase 4 | LangSmith tracing + golden dataset + eval harness | Planned |

---

## Quick start

```bash
# Prerequisites
python 3.11+
node 18+ (for React frontend)
redis (for caching)
# No local PostgreSQL+AGE needed - connects to remote Hetzner VPS

# Backend setup
git clone <repo-url>
cd agentic-search-ui
cp env.example .env   # fill in API keys and credentials
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run backend
uvicorn system_03_search_agent.api.main:app --reload

# Frontend setup (separate terminal)
cd frontend
npm install
npm run dev

# Run tests
pytest tests/
```

---

## Directory structure

```
agentic-search-ui/
  system_03_search_agent/       # Python backend
    api/                        # FastAPI routes, middleware, SSE
    agent/                      # LangGraph graph definition, nodes, edges
    tools/                      # cypher_query, ncbi_efetch, ncbi_dbsnp, pubtator, litvar2
    models/                     # Multi-model harness, tier routing
    auth/                       # JWT auth service
    config/                     # Settings, environment loading
    cli.py                      # CLI entry point
  frontend/                     # React UI
    src/
    public/
    package.json
  tests/                        # pytest test suite
  docs/                         # Architecture docs, reference material
  reference/                    # Symlink to agentic-search-data-engineering (System 1+2)
  .claude/                      # Claude Code rules, skills, agents (gitignored)
  CLAUDE.md                     # Claude Code instructions
  AGENTS.md                     # Instructions for other AI agents
  DECISIONS.md                  # Architecture decision log
  pyproject.toml
  requirements.txt
  env.example
```

---

## Documentation

| Doc | What it covers |
|-----|---------------|
| [System 3 architecture brainstorming](docs/System_3_architecture_brainstorming.md) | Agent loop, tools, multi-model harness, cost model, deployment plan |
| [Three-layer data architecture](docs/architecture/Three_layer_data_architecture.md) | How System 3 accesses Layer 1 (graph), Layer 2 (NCBI APIs), Layer 3 (enrichment) |
| [Knowledge graph reference](docs/Knowledge_graph_on_server_reference.md) | Live graph operations: SSH, Cypher examples, indexes, node/edge counts, cost |
| [NCBI databases and APIs](docs/NCBI_databases_and_APIs_reference.md) | All 39 NCBI databases, endpoints, rate limits, record counts |
| [NCBI repos deep dive](docs/NCBI_repos_deep_dive.md) | Analysis of 13 NCBI GitHub repos: code to reuse, patterns to adopt, what not to build locally |
| [BioLink repos explained](docs/architecture/Biolink_repos_explained.md) | BioLink model categories, predicates, CURIEs used in the graph |
| [Project overview](docs/Project_overview_A_to_Z.md) | Navigation hub for the full project |
| [Decisions](DECISIONS.md) | Architecture and implementation decisions with rationale |

---

## Cost model

Estimated monthly cost for the full System 3 deployment:

| Item | Estimated cost |
|------|---------------|
| Knowledge graph hosting (Hetzner CPX42, 8 vCPU, 16 GB, 320 GB NVMe) | ~$28/month |
| LLM API costs (Anthropic + OpenAI, depending on query volume) | ~$10-50/month |
| User database (serverless PostgreSQL) | ~$5/month |
| Redis (managed or self-hosted) | ~$0-5/month |
| Domain + TLS | ~$1/month |
| Total | ~$44-89/month |

Cost caps enforced per-query via the multi-model harness. Guard tier uses the cheapest model, synth tier uses the strongest only when needed.

---

## Connection to System 1 and System 2

The knowledge graph that System 3 queries was built by the data engineering repo (System 1 + System 2). That repo is symlinked at `reference/agentic-search-data-engineering` for documentation access. System 3 connects to the graph as a read-only client via psycopg2.

Do not add ETL pipeline code, graph loading code, or data ingestion logic to this repo. That belongs in the data engineering repo.

---

## License

Apache 2.0. See [LICENSE](LICENSE).

---

Last updated: 2026-05-05
