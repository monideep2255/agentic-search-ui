# AGENTS.md

Instructions for `agentic-search-ui`. For all AI agents (Gemini, Copilot, Codex, GPT, etc.). Exact same content as CLAUDE.md.

This repo covers System 3 (search agent, API, UI). System 1 (data pipelines) and System 2 (knowledge graph) live in a separate repository symlinked at `reference/agentic-search-data-engineering`.

Stack: Python 3.11+, FastAPI, LangGraph, React, PostgreSQL (user data), psycopg2 (AGE graph read-only), LiteLLM/multi-model harness.

---

## Current focus

| Priority | System | Status |
|----------|--------|--------|
| 1 | System 3: search agent baseline | IN PROGRESS. Infrastructure setup, auth, empty chat shell, first tool integration. Knowledge graph available on Hetzner CPX42 (46.225.128.133): 115M nodes + 693M edges queryable via openCypher over psycopg2. |
| 2 | System 3: tool integration | PLANNED. cypher_query, ncbi_efetch, ncbi_dbsnp, pubtator_annotate, litvar2_lookup. |
| 3 | System 3: eval and tracing | PLANNED. LangSmith tracing, golden dataset, automated eval harness. |

---

## Architecture

```
Agent loop (every query):
  Guardrail -> Think -> Plan -> Act -> Write

Three-layer data access:
  Layer 1: Knowledge graph (Cypher via psycopg2 to AGE on Hetzner VPS, read-only)
  Layer 2: NCBI APIs live (EFetch, ELink, dbSNP REST, called at query time)
  Layer 3: Enrichment APIs (PubTator3, LitVar2, LitSense, ClinicalTrials.gov)
```

The agent orchestrates across all three layers. Layer 1 provides the pre-ingested graph (115M nodes, 693M edges from 5 NCBI databases). Layers 2 and 3 reach live APIs for data not in the graph or for real-time enrichment.

Multi-model harness with three tiers:
- Guard tier: fast, cheap model for input validation and guardrails
- Plan tier: mid-range model for query decomposition and tool selection
- Synth tier: strongest model for final answer synthesis and citation assembly

---

## Reference docs (in docs/)

| Doc | What it is | Read when |
|-----|-----------|-----------|
| `System_3_architecture_brainstorming.md` | Architecture design for the search agent: agent loop, tools, multi-model harness, cost model, deployment | Before writing any System 3 code |
| `architecture/Three_layer_data_architecture.md` | Layer 1 (graph), Layer 2 (on-demand API), Layer 3 (enrichment). How System 3 accesses each layer. | Understanding data access patterns |
| `architecture/Biolink_repos_explained.md` | BioLink model reference: categories, predicates, CURIEs | Understanding the graph schema when writing Cypher |
| `Knowledge_graph_on_server_reference.md` | A-Z operations reference for the live graph on Hetzner CPX42: SSH access, Cypher query examples, index listing, node/edge counts, cost breakdown | Before writing cypher_query tool or debugging graph access |
| `NCBI_databases_and_APIs_reference.md` | All 39 NCBI databases, API endpoints, rate limits, record counts | Before implementing Layer 2 tools (ncbi_efetch, ncbi_dbsnp) |
| `Project_overview_A_to_Z.md` | Navigation hub with pointers into every doc in the project | First doc to read for project orientation |

---

## Build order (System 3)

```
Phase 1 (week 1):   FastAPI skeleton + auth service + empty chat endpoint + React shell + streaming SSE
Phase 2 (week 2):   cypher_query tool + LangGraph agent loop + first end-to-end query
Phase 3 (week 3):   ncbi_efetch + ncbi_dbsnp + pubtator_annotate + litvar2_lookup + guardrail node + citation formatting
Phase 4 (week 4):   LangSmith tracing + golden dataset (50 queries) + eval harness + cost tracking
```

---

## Agent loop pattern (every query follows this)

```
Step 1: Guardrail  - validate input, reject prompt injection, check rate limits
Step 2: Think      - classify query intent, identify required data layers
Step 3: Plan       - decompose into tool calls, select model tier per step
Step 4: Act        - execute tool calls (Cypher, NCBI APIs, enrichment APIs)
Step 5: Write      - synthesize answer with inline citations, format for UI
```

Tools live in `system_03_search_agent/tools/`. Each tool is a self-contained module with a schema, execute function, and test fixture.

---

## Citations: non-negotiable

Every fact in a response must link back to its source:
- Graph results: link to the NCBI source record via `source_url` stored on each node/edge
- Layer 2 API results: link to the NCBI record page (e.g., `https://www.ncbi.nlm.nih.gov/gene/7157`)
- Layer 3 enrichment: link to the enrichment source (PubTator annotation, LitVar2 page, clinical trial)

Every claim must be verifiable. This is the trust moat.

---

## Data source adapter pattern

Each NCBI data source implements only the adapters that apply to its capabilities. No monolithic interface.

Adapter types:
- `QueryAdapter` (required): accepts a structured query, returns results
- `FacetAdapter` (optional): supports faceted search (PubMed has this; Gene does not)
- `CitationAdapter` (optional): returns structured citation metadata (PubMed, ClinVar)
- `RelationshipAdapter` (optional): can traverse entity relationships (Gene, MedGen)
- `StreamingAdapter` (optional): supports streaming large result sets (dbSNP)

The agent checks adapter availability before attempting operations. If a source lacks `FacetAdapter`, the agent skips faceted refinement for that source. No "not implemented" exceptions, no silent no-ops.

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
| repo-dive | First-principles analysis of a reference repo | `/repo-dive <path>` |
| skill-adapt-verify | Verify adapted skill for stale paths and style violations | `/skill-adapt-verify <path>` |
| ship | Sync docs, commit, push phase branch | `/ship` |
| first-principles | Explain concepts from fundamentals | `/first-principles` |
| socratic-questioning | Clarifying questions before advice | `/socratic` |
| release-workflow | End-to-end release verification and ship | `/release` |

Auto-read skills (loaded by other skills or before specific tasks): best-practices, qa-gate, release-workflow, architecture-patterns, documentation-standards, python-code-standards, testing-standards.

All rules are in `.claude/rules/` and loaded automatically. No need to duplicate here.

---

Last updated: 2026-05-05
