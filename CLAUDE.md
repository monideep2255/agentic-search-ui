# CLAUDE.md

Claude Code instructions for `agentic-search-ui`. This IS a software project.

This repository covers System 3 (search agent, API, UI). System 1 (data pipelines) and System 2 (knowledge graph) live in a separate repository symlinked at `reference/agentic-search-data-engineering`.

Stack: Python 3.11+, FastAPI, LangGraph, React, PostgreSQL (user data), psycopg2 (AGE graph read-only), LiteLLM/multi-model harness.


## Table of contents

- [Current focus](#current-focus)
- [Working agreements](#working-agreements)
- [Architecture](#architecture)
- [Agent loop pattern (every query follows this)](#agent-loop-pattern-every-query-follows-this)
- [Citations: non-negotiable](#citations-non-negotiable)
- [Data source adapter pattern](#data-source-adapter-pattern)
- [Sub-agents](#sub-agents)
- [Skills](#skills)

## Current focus

| Priority | System | Status |
|----------|--------|--------|
| 1 | System 3: planning | COMPLETE, all 5 phases (2026-07-21 to 2026-07-26). Narrative: `requirements/Plan.md`'s Revision history and the `requirements/phase_N/` synthesis docs. |
| 2 | System 3: build (Phase 6) | IN PROGRESS. Steps 6.1 (prototype) and 6.2 (reconciliation) COMPLETE, step 6.3 (v1) underway. `HANDOFF.md` says what is live, what awaits the product owner and the one next action; the board is `testing/UI_fix_plan.md`; a numbered phase's ledger is `tracker/phase_N.M.md`. Counts: `python3 tracker/check_doc_drift.py --counts`. |
| 3 | System 3: tool integration | PLANNED, seven tools: cypher_query, ncbi_efetch, ncbi_dbsnp, pubtator_annotate, litvar2_lookup, pathogen_detection, clinicaltrials_search. Build phases 2.1 and 3.1 to 3.5. |
| 4 | System 3: eval and tracing | Build phases 5.0 to 5.3 merged. The evaluation track is CLOSED (owner, 2026-08-31; the rest is Phase 7 in `requirements/Plan.md`). UI fixes and build phases run as one cadence with a risk dial (`.claude/skills/bossman-mode/SKILL.md`). |

## Working agreements

Short forms of rules that load only with the files they govern, so they also hold from the first turn:

- Judgment calls are the owner's: ask what they think first, stress-test it, then let them decide. Before a substantial document, clarify its story first. Full rule: `.claude/rules/preserve-your-thinking.md`.
- Log every non-trivial choice between alternatives as an append-only `DECISIONS.md` row (Date, Decision, Alternatives considered, Why in a `<details>` dropdown). Full rule: `.claude/rules/decision-logging.md`.
- Before `npm install`, `pip install`, a version bump, or adding an MCP server or tool integration, read `.claude/rules/supply-chain-security.md` and `.claude/rules/ai-security-standards.md`. A path cannot trigger them for a shell command.
- Before writing or reviewing code, the production, AI security and design rules load with the file. A shell-only change to code still follows them.
- Rules, their loading map and full texts: `.claude/README.md`, "Rules", and `.claude/rules-reference/`. Another agent reads every rule in `.claude/rules/`, `.claude/rules-reference/` and `docs/rules/` explicitly, and `.claude/README.md`, "Running this project with a different agent".

## Architecture

```
Agent loop (every query):
  Guardrail -> Think -> Plan -> Act -> Write

Three-layer data access:
  Layer 1: Knowledge graph (Cypher via psycopg2 to AGE on Hetzner VPS, read-only)
  Layer 2: NCBI APIs live (E-utilities, Datasets, PubChem, dbSNP, Pathogen Detection, called at query time)
  Layer 3: Enrichment APIs (PubTator3, LitVar2, ClinicalTrials.gov)
```

The agent orchestrates across all three layers. Layer 1 provides the pre-ingested graph (115M nodes, 693M edges from 5 NCBI databases), hosted on Hetzner CPX42 (`<server-ip>`) and queryable via openCypher over psycopg2. Layers 2 and 3 reach live APIs for data not in the graph or for real-time enrichment.

Multi-model harness with three tiers:
- Guard tier: fast, cheap model for input validation and guardrails
- Plan tier: mid-range model for Think's question analysis, and for writing a graph query in Act when no template fits. The Plan step picks its tools in code
- Synth tier: strongest model for final answer synthesis and citation assembly

Reference documents under `docs/`, with when to read each: `.claude/README.md`, "Reference docs". The build order is `requirements/Technical_specification.md` Section 25.

## Agent loop pattern (every query follows this)

```
Step 1: Guardrail  - validate input, reject prompt injection, check rate limits
Step 2: Think      - classify query intent, identify required data layers
Step 3: Plan       - decompose into tool calls, select model tier per step
Step 4: Act        - execute tool calls (Cypher, NCBI APIs, enrichment APIs)
Step 5: Write      - synthesize answer with inline citations, format for UI
```

Tools live in `system_03_search_agent/tools/`. Each tool is a self-contained module with:

- A schema
- An execute function
- A test fixture

## Citations: non-negotiable

Every fact in a response must link back to its source:
- Graph results: link to the NCBI source record via `source_url` stored on each node/edge
- Layer 2 API results: link to the NCBI record page (e.g., `https://www.ncbi.nlm.nih.gov/gene/7157`)
- Layer 3 enrichment: link to the enrichment source (PubTator annotation, LitVar2 page, clinical trial)

Every claim must be verifiable. This is the trust moat.

## Data source adapter pattern

Each NCBI data source implements only the adapters that apply to its capabilities. No monolithic interface.

Adapter types:
- `QueryAdapter` (required): accepts a structured query, returns results
- `FacetAdapter` (optional): supports faceted search (PubMed has this; Gene does not)
- `CitationAdapter` (optional): returns structured citation metadata (PubMed, ClinVar)
- `RelationshipAdapter` (optional): can traverse entity relationships (Gene, MedGen)
- `StreamingAdapter` (optional): supports streaming large result sets (dbSNP)

The agent checks adapter availability before attempting operations. If a source lacks `FacetAdapter`, the agent skips faceted refinement for that source. No "not implemented" exceptions, no silent no-ops.

## Sub-agents

The table of sub-agents and their trigger words is in `.claude/README.md`, "Sub-agents". Claude Code also lists each by its own description.

## Skills

The table of skills is in `.claude/README.md`, "Skills". The invocation is always the skill's exact name; a shortened alias does not resolve.

Last updated: 2026-10-04
