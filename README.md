# Agentic search UI

Agentic search agent for querying NCBI biomedical data across a 115M-node knowledge graph and 30+ live APIs.

Takes natural language questions about genes, diseases, variants, publications, and taxonomy. Returns cited answers with links back to NCBI source records. Built with FastAPI, LangGraph, and React.

For a plain-language, no-jargon project update, see [PROGRESS.md](PROGRESS.md).

## Table of contents

- [Live demo](#live-demo)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Status](#status)
- [Quick start](#quick-start)
- [Directory structure](#directory-structure)
- [Planning documents](#planning-documents)
- [Documentation](#documentation)
- [Cost model](#cost-model)
- [Connection to System 1 and System 2](#connection-to-system-1-and-system-2)
- [License](#license)

## Live demo

Deployed on Railway, 2026-08-24. Both services auto-deploy on merge to `develop`.

| Surface | URL |
|---------|-----|
| Web UI | https://search-agent-web-production.up.railway.app |
| API | https://search-agent-api-production.up.railway.app |

Measured on the deployed API rather than asserted: "Which diseases are associated with BRCA1?" returns a grounded answer with five citations in about 16 seconds, across a Layer 1 graph query and a Layer 2 NCBI confirmation.

It is a PROTOTYPE and is honest about what does not work yet. Known open defects, all recorded in `tracker/phase_4.12.md`: streaming does not render incrementally, a second conversational turn is not possible, answer presentation does not match the approved design, the integrations page does not present the KGX, REST, CLI and MCP surfaces properly, there is no client-side routing so every page serves at `/`, and one alias-ambiguous gene symbol is refused in production while resolving locally.

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
| Auth | PyJWT (HS256 access tokens), argon2-cffi (argon2id password hashing) |
| Observability | LangSmith |

---

## Status

| Track | Status |
|-------|--------|
| Planning (Phases 1-4) | Complete: problem definition, evaluation playbook, PRD (locked), technical specification (locked) plus strategic memo |
| Planning (Phase 5) | Complete (opened and closed 2026-07-26): system and tooling updates |
| Build (Phases 6-7) | In progress. Step 6.1, the prototype, is complete. Step 6.3, build v1, has merged build phases 3.0 through 3.5 and 4.0 through 4.12. THE PRODUCT IS DEPLOYED AND ANSWERING (see Live demo above), with CD watching `develop`. Next: the UI defects the live demo surfaced, then CI (build phase 4.14), then 5.0 and 5.1 for tracing and the eval harness. See `tracker/BOARD.md` for per-phase status and `requirements/Plan.md` for the full narrative |

### Build phase detail

| Phase | Delivers | Status |
|-------|----------|--------|
| 1.0 | FastAPI app skeleton, health endpoint, the Pydantic event contract, a typed run() stub wired to the query endpoint | Merged into develop, PR #5, 2026-07-27 |
| 1.1 | Minimal v1 auth and the PostgreSQL user-data schema (six tables) | Merged into develop, PR #6 |
| 2.0 | The real five-node LangGraph Guardrail, Think, Plan, Act, Write loop and the three-tier harness, replacing the phase 1.0 stub | Merged into develop, PR #9 |
| 1.2 | SSE streaming endpoints (POST /v1/query, GET /v1/query/{run_id}/events, POST /v1/query/{run_id}/stop) and the frontend/ React shell wired end to end against the real backend | Merged into develop, PR #12 |
| 2.1 | cypher_query over Layer 1, the first live graph access | Merged into develop, PR #15, 2026-08-01 |
| 2.2 | Deterministic cite-or-refuse, Layer 1 provenance on every citation, the first trust signal | Merged into develop, PR #18, 2026-08-03 |
| 3.0 | The full Section 10 guardrail: non-LLM pre-filter, boundary validation, Guard-tier injection and off-topic classification, forbidden query types | Merged into develop, PR #19, 2026-08-04 |
| 3.1 | ncbi_efetch, the first Layer 2 tool: live NCBI record access across E-utilities, Datasets v2, and PubChem, with gene-symbol resolution | Merged into develop, PR #22, 2026-08-05; re-review debt closed via PR #23, 2026-08-07 |
| 3.2 | ncbi_dbsnp, the second Layer 2 tool: variant normalization and dbSNP record retrieval over Variation Services and dbSNP ESummary | Merged into develop, PR #25, 2026-08-08, after six review passes |
| 3.3 | pubtator_annotate and litvar2_lookup, the two Layer 3 enrichment tools: entity normalization and publication annotation via PubTator3, variant-to-literature evidence via LitVar2 | Merged into develop, PR #26, 2026-08-08, after ten review passes |
| 3.5 | pathogen_detection (bulk access to the NCBI Pathogen Detection FTP snapshot tree) and clinicaltrials_search (ClinicalTrials.gov API v2), completing the seven-tool roster | Merged into develop, PR #27, 2026-08-08, after a judge round, an adversary round, and two fix rounds |
| 3.4 | Provenance extended to Layers 2 and 3, the two-tier risk gate, freshness and conflict resolution, T-3.1-28 (dual-layer Act-step dispatch) folded in | Merged into develop, PR #28, 2026-08-10, after two judge rounds, an adversary round, and two fix rounds |
| 4.0 | The REST plus SSE adapter finalized as the public API surface: resumable multi-consumer SSE, bounded registry eviction, grace-period abandonment cancellation, GET /citations, operator-scoped cost visibility, legacy POST /query removed | Merged into develop, PR #39, 2026-08-11, after four judge rounds and an adversary round (14 findings, 4 carried open to build phase 6.0 and later) |
| 4.1 | The outbound-only MCP server wrapping the same tool functions: a single advertised tool, ask_biomedical_question, folding the REST/SSE core's event stream into one JSON result, hard-pinned no-cost surface, bearer-JWT auth reusing the existing decode path | Closed 2026-08-11 on `phase/4.1-mcp-server`, ready to ship, after three judge rounds and an adversary round (16 findings, 2 carried open with named owners) |
| 4.2 | Thin CLI client over the REST API: `system3-cli`, command `s3` | Merged into develop, PR #47, 2026-08-16 |
| 4.3 | GraphQL surface via Strawberry, sharing auth and tools with REST | Merged into develop, PR #48, 2026-08-17, after six independent review rounds |
| 4.4 | KGX export: a query-scoped subgraph, seed CURIEs and bounded hops, writing nodes.tsv, edges.tsv and a manifest | Merged into develop, PR #51, 2026-08-19 |
| 4.5 | Bounded session memory, audience-depth control, the named scientist persona. Never touches grounding | Merged into develop, PR #52, then PR #53 on 2026-08-21 |
| 4.6 | Interaction capture, the weekly review ritual, hand-promotion into few-shot examples | Merged into develop, PR #54, 2026-08-21 |
| 4.7 | Competency-question routing: real query-shape classification and entity resolution in Think, closing a finding that survived twelve phases | Merged into develop, PR #56, 2026-08-23 |
| 4.8 | Web UI visual design: MUI adoption, a real theme, restyling every screen | Merged into develop |
| 4.9 | Nine answer-screen and chrome fidelity gaps against the approved design | Merged into develop |
| 4.10 | The anonymous run path and the server-side guest allowance, with history migration on signup | Merged into develop |
| 4.11 | The read-only HTTPS graph query service on the Hetzner box, retiring the hand-opened SSH tunnel | Merged into develop, PR #55, 2026-08-22 |
| 4.12 | The demo deployment on Railway: two services, Postgres and Redis, the Layer 1 cutover, and CD watching develop | Merged into develop, PR #61, 2026-08-24. THE PRODUCT IS LIVE |
| 4.13 | Durable cross-reload search history over the interactions rows 4.6 writes | Not started |
| 4.14 | CI: the ten merge-blocking gates from Section 24 | Not started, pulled forward from 6.1 by product-owner decision 2026-08-24 |
| 4.15 | Two Railway environments and a release-branch flow, so develop and production deploy separately | Not started, inserted by product-owner decision 2026-08-24 |

Per-phase narrative, including what each review round found and what it cost, is `requirements/Plan.md`'s Revision history. Per-phase tickets and evidence are `tracker/phase_N.M.md`.

---

## Quick start

```bash
# Prerequisites
python 3.11+
node 18+ (for React frontend)
redis (for caching)
postgresql 15+ (local, for the user-data database: auth, sessions, interactions)
# No local AGE knowledge graph needed - Layer 1 connects to the remote Hetzner VPS

# Backend setup
git clone <repo-url>
cd agentic-search-ui
cp env.example .env   # fill in API keys and credentials
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# User-data database (auth, sessions, interactions). Create it once, then migrate.
# USER_DB_URL in .env names the target; the default is the local database below.
createdb search_agent_users
alembic upgrade head

# Run backend
uvicorn system_03_search_agent.adapters.web_sse.app:app --reload

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
  src/
    system_03_search_agent/     # Python backend (build phase 1.0: core, contracts, adapters/web_sse; build phase 1.1: auth, data; build phase 1.2: SSE streaming endpoints live)
      core/                     # LangGraph graph: the 5-step loop, run() and run_streaming() entrypoints, run_registry.py (in-process run tracking)
      contracts/                # Pydantic event models and JSONSchemas
      harness/                  # Tiers, cost caps, timeouts, coordinator-worker, cache hooks
      tools/                    # cypher_query, ncbi_efetch, ncbi_dbsnp, pubtator_annotate, litvar2_lookup, pathogen_detection, clinicaltrials_search
      adapters/
        web_sse/                # FastAPI + SSE
        graphql/                # Strawberry schema over the same tools
        mcp/                    # MCP server, outbound-only
        cli/                    # Thin REST client
      auth/                     # Signup, login, refresh, logout, me endpoints (build phase 1.1)
      data/                     # Postgres models: auth, interactions, cq_candidates
  frontend/                     # React UI (build phase 1.2: Vite, React 19, TypeScript; chat UI wired to SSE)
    src/
      components/
        auth/                   # AuthGate (build phase 1.2, T-1.2-08)
        chat/                   # QueryPipelineStepper, AnswerStream, GuardrailBanner, CapMessage, LoadingSkeleton, StopButton, QueryInput, EmptyState
      hooks/                    # useAgentRun (SSE consumption via fetch() + ReadableStream)
      lib/                      # events.ts (typed AgentEvent union), api.ts (typed fetch wrappers)
      pages/                    # HomePage, ChatPage
    public/
    package.json
  tests/                        # pytest test suite
  docs/                         # Architecture docs, reference material
  reference/                    # Symlink to agentic-search-data-engineering (System 1+2)
  requirements/                 # Planning docs: Plan.md, PRD.md, Technical_specification.md, Strategic_memo.md, Evaluation_playbook.md
  tracker/                      # In-repo build board: BOARD.md, phase tickets, render_board.py, board.html
  .claude/                      # Claude Code rules, skills, agents, hooks (tracked in git for v1 development)
  alembic/                      # Alembic migrations for the user-data schema (build phase 1.1)
  CLAUDE.md                     # Claude Code instructions
  AGENTS.md                     # Instructions for other AI agents
  DECISIONS.md                  # Architecture decision log
  LEARNINGS.md                  # What broke during the build and what fixed it
  pyproject.toml
  requirements.txt
  env.example
```

---

## Planning documents

| Doc | Status |
|-----|--------|
| [Plan](requirements/Plan.md) | Master phase tracker. Its Revision history section is the project's change record, since no release has been cut yet |
| [PRD](requirements/PRD.md) | Locked 2026-07-22 |
| [Technical specification](requirements/Technical_specification.md) | Locked. 25 sections, seven tools, six delivery surfaces (web UI, REST plus SSE API, GraphQL API, MCP server, KGX export, CLI), Section 25 build order |
| [Strategic memo](requirements/Strategic_memo.md) | Phase 4 deliverable |
| [Evaluation playbook](requirements/Evaluation_playbook.md) | Living |
| [Evaluation boundary](requirements/Evaluation_boundary.md) | Living. What the eval set does NOT measure. Read beside the playbook, never instead of it: a coverage figure quoted without it is read as a completeness figure |

---

## Documentation

| Doc | What it covers |
|-----|---------------|
| [System 3 architecture brainstorming](docs/architecture/System_3_architecture_brainstorming.md) | Agent loop, tools, multi-model harness, cost model, deployment plan |
| [Three-layer data architecture](docs/architecture/Three_layer_data_architecture.md) | How System 3 accesses Layer 1 (graph), Layer 2 (NCBI APIs), Layer 3 (enrichment) |
| [Knowledge graph reference](docs/data-engineering/Knowledge_graph_on_server_reference.md) | Live graph operations: SSH, Cypher examples, indexes, node/edge counts, cost |
| [NCBI databases and APIs](docs/ncbi/NCBI_databases_and_APIs_reference.md) | All 39 NCBI databases, endpoints, rate limits, record counts |
| [NCBI repos deep dive](docs/ncbi/NCBI_repos_deep_dive.md) | Analysis of 13 NCBI GitHub repos: code to reuse, patterns to adopt, what not to build locally |
| [BioLink repos explained](docs/architecture/Biolink_repos_explained.md) | BioLink model categories, predicates, CURIEs used in the graph |
| [Multi-agent system design explained](docs/architecture/Multi_agent_system_design_explained.md) | Converted external reading on how groups of AI agents fail in a shared environment, and the bounded-swarm architecture that prevents it |
| [Project overview](docs/data-engineering/Project_overview_A_to_Z.md) | Navigation hub for the full project |
| [Agent teams tmux quickstart](docs/build/Agent_teams_tmux_quickstart.md) | tmux launch guide for bossman-mode parallel builders |
| [Claude security plugin usage](docs/Claude_security_plugin_usage.md) | How to run the on-demand `claude-security` scan, apply patches, and how it complements the always-on `security-guidance` plugin |
| [Tool implementation mechanics](docs/ncbi/Tool_implementation_mechanics.md) | Per-tool API traps from tech spec section 6: edge-label enforcement, ELink target db, the `global_mafs` array, sequential dbSNP calls, snapshot pinning |
| [Build workflow cadence](docs/build/Build_workflow_cadence.md) | The quick reference for how a build phase runs: the twelve stages, who acts at each, the model and effort per stage. Stage 5, the premise gate, is mandatory and blocking for a model-generating phase |
| [Phase 6 execution flow](docs/build/Phase_6_execution_flow.html) | The build cadence as a visual page, also published as a Claude artifact |
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

Last updated: 2026-08-24
