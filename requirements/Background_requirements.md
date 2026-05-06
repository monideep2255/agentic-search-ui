# Background requirements for System 3 PRD and technical specification

All source material, reference implementations, personal notes, and strategic context needed to write the PRD and technical specification for System 3 (agentic search agent + UI).

This document is a reference index. Each section links to source files and summarizes what they contribute. Read the linked documents for full detail.

Last updated: 2026-05-06

## Table of contents

- [1. Strategic foundation](#1-strategic-foundation)
- [2. Architecture design](#2-architecture-design)
- [3. Competency questions and evaluation](#3-competency-questions-and-evaluation)
- [4. Reference implementation: NCBI KG repo](#4-reference-implementation-ncbi-kg-repo)
- [5. Contractor architecture: NLQ and NFR baseline](#5-contractor-architecture-nlq-and-nfr-baseline)
- [6. System 1 and 2 data handoff](#6-system-1-and-2-data-handoff)
- [7. Agent and harness engineering research](#7-agent-and-harness-engineering-research)
- [8. Security and red-teaming research](#8-security-and-red-teaming-research)
- [9. User psychology and product design](#9-user-psychology-and-product-design)
- [10. Existing project documentation](#10-existing-project-documentation)
- [11. Tools and infrastructure](#11-tools-and-infrastructure)
- [12. Build philosophy and personal notes](#12-build-philosophy-and-personal-notes)
- [13. Open questions for PRD and tech spec](#13-open-questions-for-prd-and-tech-spec)

---

## 1. Strategic foundation

### Innovation proposal (starting ground)

Source: `reference/personal-os-work/NIH/Agentic-Search/Proposals/Innovation_proposal_2026.md`

A 6-month alpha proposal for agentic search at NCBI. Biomedical researchers ask plain English questions, receive cited answers from all NCBI databases unified through a BioLink-compliant knowledge graph. Every fact traces to a source record.

Key points for PRD:
- Two-phase delivery (months 1-3: KG + pipelines, months 4-6: quality monitoring + evaluation)
- Trust-first design: full provenance, SME validation loops, golden datasets, LLM-as-judge
- Five delivery formats: web UI, GraphQL API, MCP server, KGX export, CLI agent
- Cost model: ~$100-150K for 6 months ($2K/mo Neo4j, $2K/mo LLM API, $1K/mo observability)
- Success metrics: accuracy/validation, cross-database coverage, latency at scale, cost control

### NCBI strategic alignment

Source: `reference/personal-os-work/NIH/Agentic-Search/NCBI strategy/`

Three directives the system must align with:
- NCBI FY26 guiding principles: simplify discovery, optimize for AI consumption
- NIH Gold Standard Science (August 2025): reproducibility, transparency, error/uncertainty communication
- America's AI Action Plan (July 2025): build highest-quality AI-ready scientific datasets

### Two-track plan

Source: `reference/personal-os-work/NIH/Agentic-Search/Plan/Two_track_plan.md`

Track 1 (personal portfolio project): open source, 2 months, ~$300-500 total cost
Track 2 (NCBI innovation proposal): official 6-month alpha, $100-150K budget, SME validation

Source: `reference/personal-os-work/NIH/Agentic-Search/Data/Personal_build_plan.md`

Week-by-week execution plan for the personal build track.

---

## 2. Architecture design

### System 3 architecture brainstorming (primary)

Source: `docs/System_3_architecture_brainstorming.md`

First-principles walkthrough from 2026-04-20. Covers:
- Agent loop: 5 steps (guardrail, think, plan, act, write)
- Multi-tier LLM routing: guard tier (fast/cheap), plan tier (mid-range), synth tier (strongest)
- Query classification by complexity
- Auth and user data storage
- Streaming UI with inline citations
- Deployment modes (web UI, CLI, MCP server, REST API, KGX export)
- Cost modeling: $15-60/month LLM at 250 queries/day with smart routing
- End-to-end query trace example

### Three-layer data architecture

Source: `docs/architecture/Three_layer_data_architecture.md`

- Layer 1: pre-ingested knowledge graph (115M nodes, 693M edges, <10ms latency, psycopg2 to AGE)
- Layer 2: NCBI on-demand APIs (dbSNP, Protein, PMC, OMIM, GTR, GEO, dbVar, Assembly)
- Layer 3: enrichment APIs (PubTator3, LitVar2, LitSense, ClinicalTrials.gov)
- Cost: ~$30/month Layer 1 host, $0 Layer 2/3 APIs, $10-60 LLM

### Initial brainstorming (earlier iteration)

Source: `reference/personal-os-work/NIH/Agentic-Search/Reference/system-3-brainstorming/`

Files:
- `00_Plan_and_discussion.md`: framework for deriving competency questions from user research
- `01_Consolidated_findings.md`: complete tiered CQ set (65 questions across 11 personas)
- `02_Tier1_eval_spec.md`: operational eval rubric for must-pass wedge questions
- `findings/`: supporting research data

### Architecture QA

Source: `reference/personal-os-work/NIH/Agentic-Search/Data/Agentic_search_architecture_QA.md`

Question-and-answer format covering architecture decisions and trade-offs.

---

## 3. Competency questions and evaluation

### Competency question framework

Source: `reference/personal-os-work/NIH/Agentic-Search/Reference/system-3-brainstorming/01_Consolidated_findings.md`

65 questions across 11 personas, organized into three tiers:

Tier 1 (must answer, 10 questions): cross-database wedges that prove value
- Human variation journeys (CNV, ClinVar, dbVar, clinical interpretation)
- Pathogen surveillance (Salmonella, SNP cluster, AMR, BioSample)
- Paper-to-data links (PMID, SRA/BioProject/assembly)
- BLAST/sequence searches with literature linkage

Tier 2 (should answer, 28 questions): single-persona competence (literature, sequences, variants, bioinformatics)

Tier 3 (stretch, 27 questions): edge personas, submission flows, clinical triage, education

### Evaluation rubric

Source: `reference/personal-os-work/NIH/Agentic-Search/Reference/system-3-brainstorming/02_Tier1_eval_spec.md`

8-point scoring system: intent recognition, entity normalization, database routing, evidence quality, synthesis, freshness, safety, output usability. Minimum pass: 13/16.

Key insight from this work: "The strongest story is not NCBI search for everything. The strongest story is: System 3 proves value when it crosses databases cleanly, with provenance."

### Routing optimization (discussed 2026-05-06)

Competency questions serve a dual purpose:
1. Evaluation: prove the system works
2. Routing: teach the orchestrator which layers to hit for which query shapes

Start with few-shot examples in the planner prompt. Collect real query data. Upgrade to a classification layer only when data justifies it.

---

## 4. Reference implementation: NCBI KG repo

Source: `reference/ncbi_ai_agents-ncbi-kg/` (ncbi-kg branch)

A fully-implemented, production-deployed knowledge graph system. Canonical reference for search agent + UI architecture.

### Backend patterns to adopt

- Async FastAPI with CORS, middleware, startup/shutdown events
- 7-step NL-to-Cypher pipeline: relevance filter, schema context, few-shot selection, LLM call, read-only validation, execution, synthesis
- 4-layer guardrails: UI disclaimer, semantic relevance filter, read-only adapter, execution limits (30s timeout, 1000 row cap)
- LangSmith tracing (7 pipeline steps logged)
- PostHog analytics (7 custom product events)
- Keep-alive background task pinging the database every 5 minutes
- MCP server wrapper (5 tools: query, cypher, get_stats, get_schema, get_neighbors)

### Frontend patterns to adopt

22 React TypeScript components:
- `App.tsx`: NCBI visual styling (Public Sans font, #205493), routing, tabs
- `ChatMode.tsx`: NL chat interface, react-force-graph-2d visualization, pipeline display, feedback
- `AboutPage.tsx`: live stats, interactive schema graph, data sources
- `CypherEditor.tsx`: read-only Cypher with syntax highlighting
- `IntegrationHub.tsx`: REST API curl examples, KGX export, MCP config
- `ResultsTable.tsx`, `ResultsPanel.tsx`, `FeedbackButtons.tsx`, `QueryHistory.tsx`
- Admin portal: Firebase auth, file upload, pipeline viz

### Testing patterns

234 passing tests across: admin (31), API integration (24), MCP (9), NL-to-Cypher (40), observability (30), KGX validation (26)

### Deployment stack

- Backend: FastAPI on Railway (auto-deploys from ncbi-kg branch)
- Frontend: React + Vite on Railway
- Database: Neo4j Aura Free (200K/400K node/edge limit)
- MCP server: published to PyPI as `ncbi-kg-mcp`

Key files to reference:
- `src/knowledge_graph/nl_to_cypher.py`: core query generation pipeline
- `api/main_api.py`: FastAPI route patterns
- `frontend/src/components/ChatMode.tsx`: chat UI architecture
- `KG/PoC/documents/GUARDRAILS.md`: guardrail design patterns

---

## 5. Contractor architecture: NLQ and NFR baseline

Source: `reference/personal-os-work/NIH/KG/Contractor/`

Strategic design documents defining vision, constraints, and approved architecture for NLQ systems at NLM scale.

### April 21 deliverables (current baseline)

NLQ approach (ranked): `Contractor/April 21/NLQ_approach_draft.md`
- Rank 1 (best overall): guarded NLQ, typed query-plan IR, compiler/adapters
- Rank 2 (best POC trade-off): controlled NLQ, CQ templates + slot filling
- Rank 3 (fast delivery): direct LLM text-to-query with retrieval + verifier
- Recommendation: build toward rank 1 while operating like rank 2

8-layer architecture: `Contractor/April 21/NLQ_solution_overview_explained.md`
- Layer 0: entry channels (NLQ chat UI, direct GraphQL UI)
- Layer 1: guarded NLQ planning (identity, planner, CQ classifier, context builder)
- Layer 2: context retrieval (CQ library, schema slice, ontology, examples, entity grounding)
- Layer 3: public query surface (GraphQL)
- Layer 4: backend compilation (SPARQL/Cypher compiler, validator + repair loop)
- Layer 5: knowledge modules (genomics, cells, RWD, physiology, external KGs)
- Layer 6: provenance response (bindings, provenance assembler, response surfaces)
- Layer 7: governance (audit logs, versioned schema/config, CQ replay suite)

Three core axioms:
1. LLM cannot be trusted for biomedical queries: deterministic validator between model and execution
2. Public contract is GraphQL; SPARQL/Cypher are backend details
3. Provenance is mandatory first-class, not formatting

Non-functional requirements: `Contractor/April 21/NLM_KG_NFR_Baseline.md`
- 10 categories: ARCH, AUD, SEC, DATA, OPS, PERF, IAM, UX, REP, REL
- Each tagged POC vs. MVP
- Every requirement traceable to SoW deliverables (D1-D12)

Meeting decisions: `Contractor/April 21/2026-04-21-Meeting_Notes.md`
- Infrastructure planning is an early workstream, not deferred
- Federation is in-scope from day 1
- 6-month POC horizon confirmed
- Template-based interface acceptable for POC only; NL is the long-term goal

First-principles breakdown: `Contractor/April 21/NLM_KG_NFR_and_NLQ_first_principles_breakdown.md`

### April 14 deliverables (earlier baseline)

- `Contractor/April 14/Proposal_NLM_knowledgebases_v17.md`: original project charter
- `Contractor/April 14/Updated_proposal_issue_review.md`: contractor feedback on proposal
- `Contractor/April 14/2026-04-14-KG-Tech-Meeting_Notes.md`: earlier tech alignment

### Key contractor insights for System 3

| Insight | How it applies |
| --- | --- |
| Typed query-plan IR as canonical contract | Don't emit Cypher directly from LLM; freeze semantics in structured JSON first |
| Context-pack builder restricts prompt scope | Send question-specific schema slice, not full schema (reduces hallucination 6x) |
| Validator + repair loop, not unbounded agent | Deterministic validation before execution; bounded repair, not agentic loops |
| CQ library as the strongest guardrail | Constrain interpretation to approved question classes |
| Provenance-first, not answer-first | Every answer = bindings + sources + evidence + confidence + version |

### NLM KG lessons synthesized for System 3

Source: `reference/personal-os-work/NIH/Agentic-Search/Reference/user-side/Lessons_from_NLM_KG_contractor_for_System_3.md`

Prioritized recommendations:
1. Entity grounding tool (high impact, low cost): pre-resolve entity mentions to canonical IDs before Cypher
2. Schema pruning (high impact, low cost): send only relevant schema slice to reduce hallucinations
3. Structured query intent logging (medium impact): log focus_entities, relationships, constraints for replay/audit
4. Validation gate (medium impact, low cost): syntax check, row limits, provenance requirements before execution
5. Few-shot examples from golden dataset (medium impact, low cost): use tier 1 CQs in system prompt

---

## 6. System 1 and 2 data handoff

Source: `reference/agentic-search-data-engineering/`

### What System 3 inherits

Graph: 115.4M nodes, 693.3M edges on PostgreSQL + Apache AGE (Hetzner CPX42, 46.225.128.133)

Node types (10 categories):
- biolink:Gene (67.5M from NCBI Gene)
- biolink:Article (40M from PubMed)
- biolink:SequenceVariant (4.4M from ClinVar)
- biolink:OrganismTaxon (2.9M from Taxonomy)
- biolink:Disease (198K from MedGen)
- biolink:BiologicalProcess, MolecularActivity, CellularComponent (GO terms)
- biolink:PhenotypicFeature (HP from MedGen)
- biolink:OntologyClass (MeSH descriptors)

Edge predicates (14 relationships):
- gene_associated_with_condition, is_sequence_variant_of, has_phenotype
- participates_in, actively_involved_in, located_in
- mentioned_in, has_mesh_annotation, in_taxon
- subclass_of, close_match, exact_match, orthologous_to, cited_in

CURIE convention: `NCBIGene:7157`, `ClinVar:123456`, `PMID:12345678`, `MONDO:0005148`, `NCBITaxon:9606`

### Connection pattern

- Protocol: openCypher via psycopg2 (not Neo4j driver)
- Connection: `postgresql://kg_reader@46.225.128.133:5432/ncbi_kg` (read-only)
- Latency: <10ms for match-by-id, 1-10s for traversals
- Required prelude: `LOAD 'age'; SET search_path = ag_catalog, "$user", public;`

### Provenance guarantees

- Every node/edge has `source` and `source_url` fields
- No dangling edges (merge validates this)
- BioLink 4.x compliant (categories, predicates, knowledge_level, agent_type)
- CURIEs resolve to clickable NCBI URLs

### Data engineering fixes needed

Source: `reference/personal-os-work/NIH/Agentic-Search/Reference/system-3-must-update/V1_shoring_up_recommendations.md`

- Extend PREFIX_TO_CATEGORY map (missing prefixes default to NamedThing)
- Add connection recovery with exponential backoff
- Automated graph health check script (7 smoke queries post-reload)
- Parser unit tests for 15+ parsers

### Key reference files

- `reference/agentic-search-data-engineering/schema/biolink_ncbi.yaml`: LinkML schema (514 lines)
- `reference/agentic-search-data-engineering/docs/Knowledge_graph_on_server_reference.md`: operations manual
- `reference/agentic-search-data-engineering/system-02-knowledge-graph/loader/schema.py`: AGE DDL

---

## 7. Agent and harness engineering research

Source: `reference/personal-os-work/NIH/Agentic-Search/Reference/system/`

22 research documents on agent architecture, memory, evaluation, and LLM optimization. Key ones for System 3:

### Architecture and design

| Document | Key idea for System 3 |
| --- | --- |
| `Agent_harness_engineering.md` | 11 harness components; the harness (not the model) is what makes an agent useful |
| `Agent_memory_and_harness_design_from_first_principles.md` | Memory layers: sensory, working, long-term; chat context alone causes amnesia |
| `Context_graphs_as_agent_memory.md` | Use the knowledge graph itself as agent memory |
| `Spec_driven_AI_engineering_dark_factory.md` | Spec-driven development, ghost libraries, PR lifecycle delegation |
| `Choosing_multi_agent_vs_single_agent.md` | Decision framework for agent count |
| `Agent_teams_parallel_reasoning_and_managed_infra.md` | Multi-agent orchestration patterns |
| `OpenClaw_adapter_plugin_and_agent_memory_patterns.md` | Adapter and plugin architecture for agents |

### Evaluation and optimization

| Document | Key idea for System 3 |
| --- | --- |
| `Six_metrics_for_AI_agent_evaluation.md` | DeepEval: PlanQuality, PlanAdherence, TaskCompletion, StepEfficiency, ToolCorrectness, ArgumentCorrectness |
| `Nine_layers_of_LLM_production_optimization.md` | Full optimization stack for production LLM systems |
| `Inference_is_everything.md` | Inference-first approach to system design |
| `GraphRAG_multi_layer_semantic_indexing.md` | Multi-layer semantic indexing patterns |

### Memory and performance

| Document | Key idea for System 3 |
| --- | --- |
| `LLM_memory_bottlenecks_and_sparse_attention.md` | KV cache management, attention optimization, decision matrices |
| `Delta_state_pattern_for_concurrent_graph_access.md` | Concurrent graph access without conflicts |

### Harness engineering deep dives

| Document | Key idea for System 3 |
| --- | --- |
| `Harness_engineering_CLI_source_analysis.md` | CLI-first agent contract surface |
| `Harness_engineering_humans_steer_agents_work.md` | Human-in-the-loop orchestration |
| `Hermes_agent_and_new_stack_for_coding_agents.md` | New agent stacks and patterns |

### Local/edge models (future reference)

| Document | Key idea |
| --- | --- |
| `Gemma_4_local_AI_powerhouse.md` | Local model options for cost reduction |
| `Gemma_4_multi_token_prediction.md` | Multi-token prediction for speed |
| `Small_frontier_models_for_edge.md` | Small models for guard tier |
| `Training_RL_agents_with_RULER.md` | RL training for agent improvement |

---

## 8. Security and red-teaming research

### Agents of Chaos: red-teaming autonomous AI agents

Source: `reference/personal-os-work/NIH/Agentic-Search/Reference/security/Red_teaming_agents_of_chaos.md`

Original paper: arXiv:2602.20021. A red-teaming study of autonomous AI agents that documents eleven case studies of how agents fail in realistic setups, even when built with current best practices.

Six failure categories directly relevant to our System 3 security discussion (Plan.md Step 1.10):

1. Unauthorized compliance: agents obey the wrong person when identity is prompt-based, not cryptographic
2. Sensitive information disclosure: agents leak data they were told to protect via indirect questions or tool chaining
3. Destructive system-level actions: agents delete files or shut down services as side effects of literal goal interpretation
4. Denial-of-service and resource exhaustion: agents enter loops that consume all available compute or API quota
5. Identity spoofing and cross-agent contamination: agents impersonate other actors; unsafe strategies propagate via shared artifacts
6. Misreporting and false task completion: agents claim success when the system state shows failure

Key design principle from the paper: soft constraints (prompt instructions like "never harm the system") are not sufficient. Hard guardrails require technical enforcement outside the model: sandboxing, access control, rate limits, independent verification, and human-in-the-loop for destructive actions.

Feeds into: security and threat model (Plan Step 1.10), guardrail implementation (PRD and tech spec), tool boundary design.

---

## 9. User psychology and product design

### Hook model for adoption

Source: `reference/personal-os-work/NIH/Agentic-Search/Reference/user-side/Hook_model_and_belief_design_Nir_Eyal.md`

- Trigger (internal): researcher has a question, needs evidence synthesis
- Action: ask plain language question, get cited answer
- Variable reward: unpredictable depth of cross-database connections (what will it find?)
- Investment: saved queries, feedback loops, personalization improve the system

Goal: researcher with a genomics question automatically thinks "ask the system first" before going to individual NCBI databases.

### AI adoption gap

Source: `reference/personal-os-work/NIH/Agentic-Search/Reference/user-side/Bridging_the_AI_adoption_gap_enterprise.md`

How to bridge the gap between AI capability and actual user adoption in enterprise/research settings.

### Build to learn vs. build to earn

Source: `reference/personal-os-work/NIH/Agentic-Search/Reference/user-side/Build_to_learn_vs_build_to_earn.md`

Framework for deciding when a build is for learning vs. production.

### Board session notes

Source: `reference/personal-os-work/NIH/Agentic-Search/Reference/thoughts/`

- `Board_session_collaboration_April_23.md`: collaboration patterns
- `Board_session_Rana_emotional_clarity_April_25.md`: emotional clarity in decision-making

### Meeting notes

Source: `reference/personal-os-work/NIH/Agentic-Search/Meetings/Victor Cid/1_April_30.md`

Coordination meeting with Victor Cid.

---

## 10. Existing project documentation

### In this repo (docs/)

| Document | What it covers | PRD/tech spec section |
| --- | --- | --- |
| `docs/System_3_architecture_brainstorming.md` | Agent loop, multi-tier LLM, cost model, UI, deployment | Agent architecture, cost model |
| `docs/NCBI_repos_deep_dive.md` | 13 NCBI repos analyzed; code to reuse, what not to build | Tool design, entity resolution |
| `docs/NCBI_databases_and_APIs_reference.md` | All 39 NCBI databases, APIs, rate limits | Layer 2 tool specifications |
| `docs/architecture/Three_layer_data_architecture.md` | Three-layer query strategy, costs, connection code | Data architecture blueprint |
| `docs/architecture/Biolink_repos_explained.md` | BioLink categories, predicates, CURIEs | Graph schema, Cypher patterns |
| `docs/data-engineering/Knowledge_graph_on_server_reference.md` | Live graph operations: SSH, Cypher, indexes, performance | Database connection, query optimization |
| `docs/data-engineering/Project_overview_A_to_Z.md` | Navigation hub for System 1+2 | Upstream context |
| `DECISIONS.md` | 18 architecture decisions with rationale | Technical stack decisions |
| `AGENTS.md` | Instructions for all AI agents | Development workflow |

### Spec templates

Source: `reference/personal-os-work/NIH/Agentic-Search/Specs/`

Templates for PRD and technical specification documents. Use these as the starting structure.

---

## 11. Tools and infrastructure

### Development and deployment

| Tool | Purpose | Notes |
| --- | --- | --- |
| LLM API keys (Anthropic, OpenAI) | Multi-model harness | Three-tier routing: guard/plan/synth |
| Railway | Backend + frontend hosting | Already used for NCBI KG reference project |
| PostgreSQL + Apache AGE | Knowledge graph (Layer 1) | Live on Hetzner CPX42, read-only |
| Redis | Cache and session store | Local for dev, hosted for prod |

### Observability and analytics

| Tool | Purpose | Notes |
| --- | --- | --- |
| PostHog | Product analytics | User behavior, feature adoption |
| Arize AI or LangSmith | LLM tracing and evaluation | Evaluate: trace quality, cost, latency per query |
| Linear | Issue tracking | Track tasks, bugs, feature requests |

### Evaluation

| Tool | Purpose | Notes |
| --- | --- | --- |
| Golden dataset (50 CQs) | Regression testing | Gate on every PR |
| LLM-as-judge | Automated quality scoring | 8-point rubric from eval spec |
| DeepEval metrics | Agent behavior evaluation | 6 metrics: plan quality, tool correctness, etc. |

### Open question: GraphQL vs REST API

Evaluate GraphQL as the public API surface (contractor recommends it). REST is simpler but GraphQL allows clients to request exactly what they need, reduces over-fetching for complex nested biomedical data.

---

## 12. Build philosophy and personal notes

### Team model: agent army

Not getting a human team anytime soon. Build my own. Agent army. Map out the whole job of the product and engineering team, user research, develop workflows for each. Me as the orchestrator.

This means:
- Every role (researcher, developer, tester, reviewer) has an agent workflow
- The bossman-mode skill (`.claude/skills/bossman-mode/SKILL.md`) is the execution framework
- Agent teams dispatch parallel builders in tmux panes
- Update bossman-mode as we learn what works

### Council of models

Each AI model has a niche:
- Claude: matching your level, visual artifacts, main coding partner
- ChatGPT: strong all-rounder
- Gemini: search and YouTube advantage (Google's data/crawl)
- Grok: technical/scientific questions, X access, less filtered answers
- Wire into GitHub so pushing code triggers the right model

### Harness engineering is the real work

The interesting work is shifting from better base models to better harnesses. A harness includes:
- Middleware for routing and modifying requests/responses
- Memory (short-term and long-term)
- Tool/CLI integrations
- Orchestration (multi-step workflows, multi-agent flows)
- Safety rules and evaluation

Design for CLIs and tools first. Give agents a small, robust vocabulary of CLI-like tools for critical paths. Wrap messy external APIs behind local CLIs. The CLI is the "agent contract surface."

### What makes AI features magical

Subtlety, not technical sophistication. The features that feel magical are the ones that work without the user noticing the complexity.

### Industry trends

Parallel trends across NVIDIA, Perplexity, Anthropic, LangChain: fast open models, persistent agents, orchestration/harnesses, AI-assisted research, multimodal/physical AI. Not just "better chatbots."

### Workflow design principle

For any workflow ("help a scientist explore a dataset," "generate a protocol," "summarize literature"), ask: can the system go from high-level goal to multi-step plan to artifacts (code, diagrams, UIs) to refinement?

### Single vs. multiple agents

Decision pending. If multiple, name agents to scientific names (Einstein, etc.). Consider: one orchestrator with specialized tools vs. multiple agents with handoffs.

### Competency question strategy

- Competency questions + user stories: work backwards from one-shot answer capability
- Deep dive on Confluence, Jira, app logs to understand what people actually search for (people may lie, data never lies)
- Reverse engineer competency questions from user profiles and jobs to be done
- Search must match current keyword matching AND add dialogue/conversation capability

### Context graph and model distillation

- Use the knowledge graph as a context graph for the agent
- Use the best models to establish what a good answer looks like, then adapt a lower model to that performance level
- Comparison and benchmarking is a must: run experiments

### Future UI capabilities

- Login for collecting information to memory (harness engineering)
- Charts, graphs, download data in the UI
- Feedback mechanisms that feed back into the system

### Build purpose and learning goals

Use Elon's 5-step algorithm (question requirements, delete, simplify, accelerate, automate).

Next 2 months goal: build something end to end using tools (coding agents + Linear + evals). Whole system with AI tools as teammate.

NCBI search project as playground with latest tools (Codex, Cursor, Droid, Claude Code + KG work). Learn new tools + learn domain knowledge. Apply OpenClaw architecture patterns. Cover the full stack: get data, create agents, security, cloud, load testing, best practices.

Where does AI fit in end-to-end product development (discovery to execution)? Apply auto-research (Karpathy) to work. Add context tracing for agents when building. Can a self-improving loop be created?

### Discussion with Carl

Search must match current GQuery (keyword matching) + add dialogue/conversation. Harness engineering is the differentiator.

---

## 13. Open questions for PRD and tech spec

These need resolution before or during PRD/tech spec writing:

1. GraphQL vs REST API: contractor recommends GraphQL as public surface. What is best for our scale and use case?
2. Single agent vs multi-agent: one orchestrator with tools, or multiple specialized agents with handoffs?
3. Competency question routing: start with few-shot in planner prompt. When do we upgrade?
4. Model distillation: when do we benchmark frontier models and adapt cheaper models to match performance?
5. Federation: contractor says in-scope from day 1. How much federation do we need for the POC?
6. Login and user data: what do we collect from day 1 vs. add later?
7. Agent naming convention: scientific names or functional names?
8. Bossman-mode updates: what needs to change in the skill as we learn from execution?
9. Cost caps: what are the per-query, per-user, and system-wide daily limits?
10. Deployment: Railway confirmed, or evaluate alternatives?
