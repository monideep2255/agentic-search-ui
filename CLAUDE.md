# CLAUDE.md

Claude Code instructions for `agentic-search-ui`. This IS a software project.

This repo covers System 3 (search agent, API, UI). System 1 (data pipelines) and System 2 (knowledge graph) live in a separate repository symlinked at `reference/agentic-search-data-engineering`.

Stack: Python 3.11+, FastAPI, LangGraph, React, PostgreSQL (user data), psycopg2 (AGE graph read-only), LiteLLM/multi-model harness.

---

## Current focus

| Priority | System | Status |
|----------|--------|--------|
| 1 | System 3: planning (Phase 5) | PHASE 1 COMPLETE (all 13 steps, synthesis in requirements/phase_1/Phase_1_synthesis.md). PHASE 2 COMPLETE per requirements/Plan.md: competency questions and the evaluation playbook, deliverable requirements/Evaluation_playbook.md. PHASE 3 COMPLETE: PRD drafted, graded, and locked, deliverable requirements/PRD.md (locked 2026-07-22). PHASE 4 COMPLETE (opened 2026-07-24, closed 2026-07-25): the verified API capability sheet (requirements/phase_4/API_capability_sheet.md), the locked technical specification (requirements/Technical_specification.md, 25 sections, seven tools, six delivery surfaces), and the strategic memo (requirements/Strategic_memo.md). These three deliverables serve as the phase synthesis. requirements/System_3_overview.html combines the four Phase 4 planning docs (Strategic_memo.md, PRD.md, Technical_specification.md, Evaluation_playbook.md) into one navigable overview, also published as a Claude artifact. PHASE 5 COMPLETE (opened and closed 2026-07-26, all steps 5.1 to 5.4, branch phase/5.0-system-tooling-updates). Scope was set by a coverage map of 303 obligations extracted from the three locked docs, of which 57 had no owner; deliverables are requirements/phase_5/Coverage_map.md and requirements/phase_5/Phase_5_synthesis.md. Delivered: the bossman-mode overhaul (phase branches, tech spec Section 25 as the phase source of truth, worktree isolation by default, the full gate chain), two new skills (task-tracker, learnings), four new or adopted rules (tool-call-budgets, v1-scope-boundary, prompt-cache-discipline, plus extensions to production-standards and system-design-patterns), dependency-tracking narrowed to hooks, and docs/ncbi/Tool_implementation_mechanics.md. 121 decisions in DECISIONS.md. No application code yet; build execution begins at Plan.md Phase 6. Knowledge graph available on Hetzner CPX42 (46.225.128.133): 115M nodes + 693M edges queryable via openCypher over psycopg2. |
| 2 | System 3: tool integration | PLANNED, seven tools. cypher_query, ncbi_efetch, ncbi_dbsnp, pubtator_annotate, litvar2_lookup, pathogen_detection, clinicaltrials_search. Build phases 2.1 and 3.1 to 3.5. |
| 3 | System 3: eval and tracing | PLANNED. LangSmith tracing, PostHog, the 50-query golden dataset, the eval harness against the playbook. Build phases 5.0 and 5.1. |

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
| `data-engineering/Knowledge_graph_on_server_reference.md` | A-Z operations reference for the live graph on Hetzner CPX42: SSH access, Cypher query examples, index listing, node/edge counts, cost breakdown | Before writing cypher_query tool or debugging graph access |
| `NCBI_databases_and_APIs_reference.md` | All 39 NCBI databases, API endpoints, rate limits, record counts | Before implementing Layer 2 tools (ncbi_efetch, ncbi_dbsnp) |
| `NCBI_repos_deep_dive.md` | Analysis of 13 NCBI GitHub repos: code to reuse, architecture decisions informed, patterns to adopt, what not to build locally | Before implementing any Layer 2 or Layer 3 tool; before making architecture decisions about entity resolution or data access |
| `data-engineering/Project_overview_A_to_Z.md` | Navigation hub with pointers into every doc in the project | First doc to read for project orientation |
| `Agent_teams_tmux_quickstart.md` | tmux launch guide so bossman-mode parallel builders show in live panes | Before running `/bossman-mode` with 2 or more builder tasks |
| `Claude_security_plugin_usage.md` | Reference for the on-demand `claude-security` scan plugin: how to run a scan, apply patches, and how it complements the always-on `security-guidance` plugin | Before the release-workflow Step 3 security scan gate, or before opening a pull request |
| `Tool_implementation_mechanics.md` | Per-tool API traps taken from tech spec Section 6: edge-label enforcement, ELink target db, the `global_mafs` array, sequential dbSNP calls, snapshot pinning | Before wiring any of the seven tools. Facts, not policy; the policy lives in the rules |
| `Build_workflow_cadence.md` | The quick reference for how a build phase runs: the eleven stages, who acts at each, the model and effort per stage, where every file gets written | Before opening any build phase, and any time the model tiering is in question |
| `Phase_6_execution_flow.html` | The same cadence as a visual page, openable in a browser. Also published as a Claude artifact | When explaining the build loop to someone, or checking the flow at a glance |

---

## Build order (System 3)

The authoritative build order is `requirements/Technical_specification.md` Section 25: 26 numbered build phases from 1.0 to 7.1, each with its branch name, what it delivers, what it depends on, and a dependency graph. Read that section, not a summary. The four-week table that used to live here is superseded.

Shape of the sequence:

| Group | Delivers | Maps to Plan.md |
|-------|----------|-----------------|
| 1.0 to 1.2 | FastAPI skeleton with the typed event contract, auth and the user-data schema, React shell with SSE | Step 6.1, the prototype |
| 2.0 to 2.2 | LangGraph loop and the three-tier harness, `cypher_query` over Layer 1, deterministic cite-or-refuse | Step 6.1, the prototype |
| 3.0 to 3.5 | Full guardrail, the six remaining tools, provenance and the two-tier trust gate | Step 6.3, v1 |
| 4.0 to 4.7 | The six delivery surfaces, personalization and memory, feedback capture, competency-question routing | Step 6.3, v1 |
| 5.0 to 5.1 | LangSmith tracing, PostHog, the 50-query golden dataset and eval harness | Step 6.3, v1 |
| 6.0 to 6.1 | Rate limiting and concurrency, the full `dev-standards` pass and release hardening | Step 6.3, v1 |
| 7.0 to 7.1 | model-bench per tier, the A/B routing mechanism | Step 6.3, v1 |

Step 6.2, the one reconciliation pause, sits between the prototype and v1.

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

The invocation is always the skill's exact name. A shortened alias does not resolve.

| Skill | Purpose | Invocation |
|-------|---------|-----------|
| bossman-mode | Autonomous execution with agent teams | `/bossman-mode` |
| task-tracker | The in-repo build board: tickets, acceptance criteria, status, evidence, append-only history | `/task-tracker` |
| learnings | Capture what broke and what fixed it in LEARNINGS.md, and recall it before a phase | `/learnings` |
| dev-standards | Production readiness review (6 lenses) | `/dev-standards` |
| objective-review | Critical feedback, not agreement | `/objective-review` |
| repo-dive | First-principles analysis of a reference repo | `/repo-dive <path>` |
| skill-adapt-verify | Verify adapted skill for stale paths and style violations | `/skill-adapt-verify <path>` |
| ship | Sync docs, commit, push phase branch | `/ship` |
| first-principles | Explain concepts from fundamentals | `/first-principles` |
| socratic-questioning | Clarifying questions before advice | `/socratic-questioning` |
| release-workflow | End-to-end release verification and ship | `/release-workflow` |
| eval-harness | The offline evaluation gate, operationalizing the evaluation playbook: 8-point rubric, hard-fails, coverage metric, must-pass set | `/eval-harness` |
| verify | Pre-commit checks: Python compile, tests, lint, git status | `/verify` |
| phase-checkpoint | Sync planning docs at a phase or sub-phase boundary (decisions, session doc, meeting note, continuation prompt, and at phase end the synthesis and Plan status). Runs before `/ship`, never touches git | `/phase-checkpoint` |

Auto-read skills (loaded by other skills or before specific tasks): best-practices, release-workflow, dev-standards.

All rules are in `.claude/rules/` and loaded automatically. No need to duplicate here.

Security hooks in `.claude/hooks/` (wired in `.claude/settings.json`) run on PreToolUse (secret scan on Bash commands, secret scan on config writes, deletion block) and SessionStart (context-injection scan, session context).

---

Last updated: 2026-07-26
