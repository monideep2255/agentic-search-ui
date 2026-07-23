# Phase 1 session: May 7, 2026

## Table of contents

- [Steps covered](#steps-covered)
- [Sources reviewed](#sources-reviewed)
- [Decisions made](#decisions-made-all-logged-to-decisionsmd)
- [Discussion record](#discussion-record)
- [Step 1.2: architecture design review](#step-12-architecture-design-review)
- [Open questions remaining](#open-questions-remaining)
- [Step 1.3: reference implementations](#step-13-reference-implementations-2-sources)
- [Step 1.4: data handoff](#step-14-data-handoff-2-sources)
- [Step 1.5: agent and harness research](#step-15-agent-and-harness-research-22-sources)
- [Objective review of Steps 1.1-1.5](#objective-review-of-steps-11-15)
- [What's next](#whats-next)

## Steps covered

- Step 1.1: strategic foundation review (3 sources) - COMPLETE
- Step 1.2: architecture design review (4 sources) - COMPLETE

## Sources reviewed

### Step 1.1

1. Innovation proposal (`Proposals/Innovation_proposal_2026.md`)
2. NCBI strategic alignment (`NCBI strategy/` - 5 documents: FY26 guiding principles, Gold Standard Science, AI Action Plan, Kim Pruitt email, first-principles breakdown)
3. Two-track plan (`Plan/Two_track_plan.md`)

---

## Decisions made (all logged to DECISIONS.md)

1. Innovation proposal is the starting ground for V1: all scope elements and requirements apply
2. All 5 delivery formats in scope for V1 (web UI, GraphQL API, MCP server, KGX export for System 1/2 graph, CLI agent)
3. FastAPI over Django for V1 backend
4. Hybrid API surface: REST + SSE for chat streaming, GraphQL (Strawberry) for structured programmatic access
5. NCBI strategic directives are real requirements, not aspirational alignment
6. Open-source LLMs preferred for the running system; commercial models for debugging only
7. OpenRouter as inference provider, accessed via LiteLLM in application code
8. V1 budget target: ~$100 total for 2-month build (excluding Claude Code Max subscription)
9. Agent architecture (single vs multi-agent): deferred to Step 1.2

---

## Discussion record

### Admin: how we track Phase 1 work

Agreed on a three-document structure for Phase 1 output:

1. Session notes (this file and any future session files): what we discussed, chronological record
2. DECISIONS.md: every confirmed choice, append-only table with rationale
3. Phase 1 synthesis document (written after Phase 1 completes): organizes all decisions by topic into a single narrative that feeds Phase 2 and Phase 3

The synthesis document fills the gap between chronological session notes and a flat decision table. It becomes the single input for downstream phases.

Created `requirements/phase_1/` folder to hold session notes and any Phase 1 reference files.

### Django vs FastAPI trade-off

The innovation proposal specifies Python/Django, React, GraphQL (NCBI standard stack). CLAUDE.md already had FastAPI. The divergence was explicit.

Arguments for FastAPI:
- Agent loop requires native async for concurrent API calls, LLM streaming, LangGraph integration
- Django ORM adds no value (we use raw Cypher queries against AGE, not SQL models via an ORM)
- Django added async support in 3.1+, but it's bolted on, not the foundation. Streaming requires Django Channels (significantly more wiring than sse-starlette)
- LangGraph is async-native, integrates directly with FastAPI

Portability assessment:
- Core agent code (LangGraph, tools, harness, guardrails) is pure Python, framework-agnostic: 90% of the codebase
- Porting to Django for NCBI Track 2 means rewriting the HTTP layer only (~10-15 files, mechanical translation)
- Django's built-in auth is actually easier than rolling it in FastAPI (a minor advantage for the port)

Decision: FastAPI for V1. Porting cost to Django is bounded and doesn't touch the valuable code.

### Hybrid API surface: REST + SSE and GraphQL

Two distinct consumer patterns exist that map to different protocols:

Chat consumers (web UI, CLI agent):
- Conversational, stateful, streaming
- POST a question, stream back tokens with inline citations
- REST + SSE is the natural fit (simpler than GraphQL subscriptions for this pattern)

Programmatic consumers (developers, external tools, MCP):
- Structured queries against nested biomedical data
- A query like "gene TP53, its variants, their disease associations, and citing papers" requires 4 REST endpoints and client-side joining, or 1 GraphQL query
- GraphQL is genuinely superior for nested biomedical data (the contractor also recommended this)

Architecture:
- FastAPI serves both from the same app: `/api/chat` (REST+SSE), `/graphql` (Strawberry)
- Same auth middleware, same underlying tools, no business logic duplication
- MCP server wraps internal Python functions directly (no HTTP round-trip), can expose either interface to external clients

### NCBI strategic alignment as hard requirements

Three directives treated as requirements that constrain system behavior, not aspirational positioning:

FY26 guiding principles (Kim Pruitt, Acting Director):
- Simplify content discovery for users
- Eliminate the need for users to understand NCBI's internal architecture
- Optimize content and metadata for AI and machine consumption
- Four primary use cases: archiving/publishing, reference collection, discovery (exploration), data reuse (analysis)

Gold Standard Science (NIH, August 2025):
- Reproducible: every answer traceable to specific database records (our provenance model)
- Transparent: full citation chains, visible reasoning, open evaluation metrics
- Communicative of error and uncertainty: evaluation pipeline explicitly measures and reports quality

AI Action Plan (White House, July 2025):
- Build "the world's largest and highest-quality AI-ready scientific datasets"
- NSTC to set minimum data quality standards for biological data
- The KG is exactly the AI-ready scientific data this policy demands
- Not a funding guarantee, but a strong tailwind and institutional cover

### Cost model discussion

Original estimate was $300-500 for 2 months. Revised downward after discussion.

Actual cost breakdown:
- Hetzner CPX42 (graph host): ~$30/month, ~$60 for 2 months (already running)
- Railway: $0 (free year)
- LangSmith: $0 (free tier sufficient for V1 volume)
- LLM inference for running system: single digits per month via OpenRouter on open-source models
- Claude Code Max: $100/month, not counted as project cost (personal development tool)

Total: ~$100 or less for the full 2-month build.

### Harness engineering and open-source LLMs

Core insight discussed: if the harness does the structural work well, each LLM tier's job becomes simpler, and cheaper models suffice.

How the three tiers map to open-source models:
- Guard tier (input validation, prompt injection detection): classification task. Gemma 4 or smaller handles this. Cost: effectively zero.
- Plan tier (query decomposition, tool selection): structured output following a schema. Open-source models handle this well when the harness constrains output format (JSON schema, few-shot examples, CQ templates).
- Synth tier (final answer with citations): by this point, tools have returned structured data with provenance. The model assembles facts from pre-fetched cited data, not open-ended reasoning. Template filling with natural language, not frontier reasoning.

Debugging caveat: during early development, temporarily swapping in a stronger commercial model to isolate "harness bug vs model capability bug" is worth keeping open. LiteLLM makes this a config change.

### OpenRouter vs Groq vs direct provider keys

Initial suggestion was Groq free tier (fastest inference, LPU hardware). Monideep raised OpenRouter as an alternative.

Why OpenRouter fits better:
- Unified API gateway to 100+ models (Gemma, Llama, Mistral, DeepSeek, Qwen, commercial if needed)
- One API key, one billing relationship
- Supports the multi-model, multi-agent vision: different models for different tiers/agents via model name change
- Built-in fallback chains (if one provider is down, routes to another)
- Pricing for open-source models is comparable to direct access

Architecture: LiteLLM (in-code SDK abstraction) points to OpenRouter (provider mesh). LiteLLM handles typed calls, cost tracking, retry logic, LangGraph integration. OpenRouter handles provider routing and fallbacks. Each layer does what it's good at.

### Multi-model, multi-agent vision (seed planted for 1.2)

Monideep raised the idea of multiple agents using different models working in sync. This connects to the agent architecture question (single vs orchestrator + workers vs multi-agent) deferred to Step 1.2.

The OpenRouter + LiteLLM decision enables this: each agent or tier can use a different model via a config change. The infrastructure supports the multi-model multi-agent pattern regardless of which agent architecture we pick in 1.2.

---

---

## Step 1.2: architecture design review

### Sources reviewed

1. System 3 architecture brainstorming (`docs/System_3_architecture_brainstorming.md`) - 544 lines, first-principles design from April 20
2. Three-layer data architecture (`docs/architecture/Three_layer_data_architecture.md`) - layer boundaries, costs, connection patterns
3. Architecture QA (`reference/personal-os-work/NIH/Agentic-Search/Data/Agentic_search_architecture_QA.md`) - 10 Q&As: database selection, BioLink, ontology, build order
4. CQ planning (`reference/personal-os-work/NIH/Agentic-Search/Reference/system-3-brainstorming/00_Plan_and_discussion.md`) - competency question framework, persona mapping

### Decisions made (all logged to DECISIONS.md)

10. Single orchestrator with 3-tier model routing; sub-query decomposition as upgrade path
11. Model selection deferred to Phase 6; harness pattern locked, models benchmarked via golden dataset
12. Streaming with typed SSE events and hard latency budgets per query class
13. Three-layer data architecture confirmed (graph + NCBI APIs + enrichment)
14. Parallel tool execution via asyncio.gather
15. Result compression in harness before re-injecting into agent context
16. NCBI API rate limit upgraded from 10 to 100 req/sec; architecture unchanged, headroom relaxed
17. Two-API strategy for Layer 2: E-utilities + Datasets API v2 + Variation Services
18. PubTator3 REST API replaces all local NER/normalization

### Agent architecture discussion

Architecture brainstorming doc recommendation: "Single orchestrator is the right default."

Monideep's devil's advocate question: what about 10+ tool calls?

Two types of 10+ calls:
- Fan-out (parallel): 5 genes x 2 calls = 10 calls. asyncio.gather handles this. No additional reasoning between calls.
- Sequential chains: each step depends on previous. Context grows, errors compound.

Three harness mechanisms for sequential chains (no second agent needed):
1. Result compression: summarize tool results before re-injecting into context
2. Planner budget enforcement: max tool calls, cost ceiling, timeout
3. Sub-query decomposition (upgrade path): break complex query into independent mini-loops (LangGraph subgraph), each with fresh context

Key distinction established: multi-model (different model per step) is not multi-agent (independent reasoners). V1 is multi-model, single-agent.

Contractor 8-layer architecture maps to our 5-step loop + infrastructure. Same concepts, simpler packaging for our team size.

### Open-source models confirmed

Best open-source models via OpenRouter. Strong candidates:
- Guard: Gemma 3 4B, Qwen3 0.6B
- Plan: DeepSeek R1, Kimi K2, Qwen3 32B
- Synth: Llama 4 Maverick, DeepSeek V3, Kimi K2

Not locked. Golden dataset ablation during build determines final selection.

### Streaming UX and latency

Five SSE event types: status, tool_result, token, citation, done.

Hard latency budgets: lookup 5s, single-hop 10s, multi-hop 30s, deep research 2min. If exceeded: synthesize with partial results, explain what timed out.

Typical multi-hop query timeline: guard 0.1s, plan 0.8s, tools 1-2s (parallel), synth first token at ~3s, full answer by 6-8s. User sees progress from T+0.1s.

### Three-layer data confirmed

No changes needed from what's built:
- Layer 1: 5 databases in AGE (115M nodes, 693M edges, <10ms)
- Layer 2: 10 NCBI databases via E-utilities (free, 100-500ms)
- Layer 3: 6 enrichment APIs (free, 200ms-2s)

### Architecture QA key confirmations

- 5 databases is the right Layer 1 scope (hub connectivity analysis)
- Modular KG pattern (Monarch Initiative) already implemented in System 1/2
- 3-layer ontology stack: BioLink schema, domain ontologies (GO, MONDO, MeSH, SO, HPO), CURIE normalization

### NCBI API rate limit upgrade: 10 to 100 req/sec

Monideep updated the NCBI API key rate limit from 10 req/sec to 100 req/sec (admin access). Impact on architecture:

| At 10 req/sec (old) | At 100 req/sec (new) |
|---------------------|----------------------|
| Max 20 API calls per query, must budget carefully | Can afford 50+ calls per query without throttling |
| Concurrent users compete for rate limit (3 users = ~3 calls/sec each) | 10 concurrent users still get 10 calls/sec each |
| Redis caching is survival-critical to stay under limit | Caching is still smart but no longer survival-critical |
| Sequential fan-out queries hit the ceiling fast | Fan-out across 5 databases in parallel is comfortable |

This relaxes the tightest constraint in the architecture. The planner's budget enforcement still matters for cost and latency control, but we're no longer one busy session away from throttling. Architecture stays the same, just more headroom.

Note: Variation Services API (`api.ncbi.nlm.nih.gov/variation/v0/`) has its own separate rate limit of 1 req/sec (IP-based, no auth). This is independent of the E-utilities limit.

### Additional sources reviewed for API and tool mapping

5. NCBI databases and APIs reference (`docs/NCBI_databases_and_APIs_reference.md`) - all 39 Entrez databases, API endpoints, searchable fields, cross-database link map, rate limits, research APIs
6. NCBI repos deep dive (`docs/NCBI_repos_deep_dive.md`) - 13 NCBI GitHub repos analyzed for code reuse, architecture decisions, patterns to adopt, what NOT to build

### How every API fits into the three-layer architecture

The knowledge graph is the skeleton. The NCBI APIs extend it with live data. The enrichment APIs augment answers with evidence. The layers are additive, not alternatives.

Concrete query walkthrough for "What genes cause MODY, what pathogenic variants exist, what are the allele frequencies, and what recent papers describe novel variants?":

```
Step 1: KNOWLEDGE GRAPH (Layer 1, <10ms)
   cypher_query → "MATCH genes linked to MODY, their pathogenic variants"
   Returns: 14 genes, 47 variants, with CURIEs (NCBIGene:6927, ClinVar:12345)
   This is the SKELETON. Fast. Pre-computed relationships.

Step 2: NCBI APIs (Layer 2, 100-500ms each, parallel)
   ncbi_efetch → fetch latest Gene record for HNF1A (live, current)
   ncbi_dbsnp  → fetch allele frequencies for rs121908261 (Variation Services API)
   datasets_api → fetch gene summary with GO terms, transcripts (richer than graph)
   These EXTEND the skeleton with live, detailed data.

Step 3: ENRICHMENT APIs (Layer 3, 200ms-2s each, parallel)
   pubtator_annotate → "which entities are mentioned in PMID:32942285?"
   litvar2_lookup    → "what papers discuss rs121908261 specifically?"
   litsense          → "find sentences mentioning HNF1A + MODY in full text"
   clinicaltrials    → "any active trials for MODY?"
   These AUGMENT the answer with evidence the graph doesn't contain.

Step 4: SYNTHESIS
   All results assembled into one cited answer with inline citations.
```

### Two-API strategy for Layer 2

The NCBI repos deep dive identified that Layer 2 needs two separate APIs, not one. E-utilities and the Datasets API cover complementary domains:

| Data need | Use Datasets API | Use E-utilities |
|-----------|-----------------|-----------------|
| Gene records | Yes (primary, richer) | Fallback |
| Genome metadata | Yes | No |
| Orthologs | Yes (native endpoint) | No (manual via ELink) |
| Taxonomy | Yes | No |
| ClinVar variants | No (not in Datasets) | Yes (primary) |
| dbSNP variants | No (not in Datasets) | Yes + Variation Services API |
| PubMed literature | No (not in Datasets) | Yes (primary) |
| OMIM disease records | No (not in Datasets) | Yes (primary) |

### V1 tool-to-API mapping

| Tool | Layer | Primary API | What it does | Rate limit |
|------|-------|------------|--------------|------------|
| `cypher_query` | 1 | psycopg2 to AGE on Hetzner | Graph traversals across 115M nodes, 693M edges | No API limit (direct DB) |
| `ncbi_efetch` | 2 | E-utilities (ESearch, EFetch, ELink) | ClinVar, PubMed, OMIM, Protein, Nucleotide records | 100 rps (upgraded) |
| `ncbi_dbsnp` | 2 | Variation Services API | Individual variant lookups by rsID (allele frequencies, functional annotations) | 1 rps (separate limit) |
| `pubtator_annotate` | 3 | PubTator3 REST API | Entity recognition from text/PMIDs (genes, diseases, variants, chemicals, species) | Free, no auth |
| `litvar2_lookup` | 3 | LitVar2 REST API | Variant-specific literature links | Free, no auth |

Additional Layer 2/3 APIs available but not separate tools (called within existing tools or added later):

| API | Layer | When called | Notes |
|-----|-------|-------------|-------|
| Datasets API v2 | 2 | Gene/genome lookups needing richer data than graph | 10 rps with key. Complements E-utilities. |
| LitSense | 3 | When user needs sentence-level evidence from full text | Called after key publications identified |
| ClinicalTrials.gov v2 | 3 | When query has a clinical dimension | 581K+ studies. Clean REST API. |
| ESummary | 3 | Fallback for any ELink result not covered above | Summary records for any NCBI database |

### Code reuse from NCBI repos (deep dive findings)

Direct code to reuse in V1:

1. dbSNP `navs.py` wrapper (`lib/python/navs.py` from ncbi/dbsnp repo): auto-detects variant input type (rsID, SPDI, HGVS, VCF), returns structured data. Copy the `Variation` class and conversion methods into our `ncbi_dbsnp` tool. Add: provenance fields, rate limiting, error handling, clinical significance extraction.

2. NCBI Datasets API endpoints: 107+ REST endpoints at `api.ncbi.nlm.nih.gov/datasets/v2`. No official Python SDK, but clean REST with OpenAPI spec. Key endpoints: gene by ID, gene by symbol, orthologs, taxonomy.

Patterns to adopt:

1. Demonstrations over documentation (from GeneGPT): showing the LLM concrete API call examples with real results produces better tool use than API docs. Our system prompt should include worked examples of each tool call, not just schemas.

2. Iterative context building with execution trace (from GeneGPT): agent state should include full tool call history (tool name, parameters, truncated result) so synthesis can reference what was queried and found.

3. Conservative multiplicative fusion for citations (from BmCS): multiply independent signals rather than averaging. `citation_confidence = graph_provenance_score x api_freshness_score x source_authority_score`.

### What NOT to build locally (deep dive findings)

| Capability | Why not build | What to use instead |
|-----------|---------------|-------------------|
| Gene normalization (GNorm2) | 60GB JVM heap, Java + Python hybrid | PubTator3 REST API |
| Variant normalization (tmVar3) | 5GB JVM, pure Java, CRF++ dependency | PubTator3 REST API |
| Full NER pipeline (AIONER + GNorm2 + tmVar3 + BioREx) | 4 tools, mixed languages, 65GB+ memory | PubTator3 REST API (wraps all four) |
| PubMed semantic search (MedCPT) | 37GB pre-computed embeddings | Not needed until Phase 4+ |
| Query expansion (BioConceptVec) | 800MB-2.4GB embeddings | Not needed until recall is a bottleneck |
| KG edge validation (BioREx) | Custom BioLink mapping needed | Not needed until post-V1 quality hardening |

PubTator3 REST API is the single endpoint that replaces local NER/normalization infrastructure. Accepts raw text, returns normalized entities with database IDs (Gene IDs, MeSH IDs, rsIDs). Free, no auth required.

### ClinVar classification systems (important for tool design)

As of May 2024, ClinVar serves three distinct classification types:
1. Germline (traditional): Pathogenic, Likely pathogenic, VUS, Likely benign, Benign
2. Somatic clinical impact (new): Tier I-IV
3. Oncogenicity (new): Oncogenic, Likely oncogenic, Uncertain, Likely benign, Benign

A variant can have all three classifications simultaneously. Our agent must surface which classification system applies. The 4-star review status indicates consensus level and feeds into citation confidence scoring.

### Layer 3 enrichment APIs: when each is called

Not every query hits every API. The planner decides based on query shape:

| API | Called when | Example |
|-----|-----------|---------|
| PubTator3 | Entity recognition needed from text or PMIDs | "What genes are mentioned in this paper?" |
| LitVar2 | Variant-specific literature links needed | "What papers discuss rs121908261?" |
| LitSense | Sentence-level evidence from full text needed | "Show me the evidence for BRCA1-breast cancer link" |
| ClinicalTrials.gov | Query has a clinical/translational dimension | "Are there any active trials for MODY?" |
| Datasets API v2 | Richer gene/genome records needed than graph provides | "What are the GO annotations for HNF1A?" |

### Architecture diagram: all APIs placed

```
                        ┌─────────────────────────────────┐
                        │         Agent Orchestrator       │
                        │    (LangGraph, single loop)      │
                        │                                  │
                        │  Guard → Think → Plan → Act → Write │
                        └───────┬──────────┬──────────┬────┘
                                │          │          │
                    ┌───────────┘   ┌──────┘   ┌──────┘
                    ▼               ▼           ▼
            ┌──────────────┐ ┌──────────┐ ┌──────────────┐
            │   Layer 1    │ │ Layer 2  │ │   Layer 3    │
            │   (Graph)    │ │ (APIs)   │ │ (Enrichment) │
            ├──────────────┤ ├──────────┤ ├──────────────┤
            │ cypher_query │ │ E-utils  │ │ PubTator3    │
            │ psycopg2→AGE │ │ 100rps   │ │ LitVar2      │
            │              │ │          │ │ LitSense     │
            │ 115M nodes   │ │ Datasets │ │ ClinTrials   │
            │ 693M edges   │ │ API v2   │ │              │
            │              │ │ 10rps    │ │ Free, no     │
            │ <10ms        │ │          │ │ auth needed  │
            │              │ │ Var.Svcs │ │              │
            │              │ │ 1rps     │ │ 200ms-2s     │
            └──────────────┘ └──────────┘ └──────────────┘

Layer 1: SKELETON (what's connected, pre-computed)
  Gene (67.5M) + PubMed (40M) + ClinVar (4.5M) + Taxonomy (2.9M) + MedGen (198K)
  Queried via openCypher through psycopg2

Layer 2: EXTENSION (live details, current data)
  E-utilities: ClinVar, PubMed, OMIM, Protein, Nucleotide, GEO, GTR, dbVar, Assembly
  Datasets API v2: Gene (richer), Genome, Orthologs, Taxonomy
  Variation Services: dbSNP individual variant lookups

Layer 3: AUGMENTATION (evidence, context, enrichment)
  PubTator3: entity extraction from publications
  LitVar2: variant-specific literature links
  LitSense: sentence-level evidence from full text
  ClinicalTrials.gov: active clinical trials
  ESummary: fallback for any ELink result
```

---

## Open questions remaining

- Auth provider for day one (deferred to Step 1.8)
- Fork reference repo or cherry-pick (deferred to Phase 5/6)

---

## Step 1.3: reference implementations (2 sources)

### Source 1: NCBI KG repo (ncbi-kg branch)

The reference repo (`reference/ncbi_ai_agents-ncbi-kg/`) was built as a 2-day prototype. It contains a 7-stage NL-to-Cypher pipeline, React frontend, LangSmith tracing, 4-layer guardrails, and 234 tests. The pipeline architecture itself is not worth copying (monolithic, tightly coupled), but the surrounding infrastructure is a strong starting template.

Decision: use the repo as an infrastructure template, not an architecture blueprint.

**Patterns to adopt directly:**

1. React component structure: ChatMode with AbortController for cancellation, 10-entry message history, react-markdown + GFM table rendering. Solid chat shell boilerplate.
2. Feedback buttons: thumbs up/down linked to LangSmith run_id. Simple and already wired to observability.
3. QueryPipeline timing visualization: shows the user how long each pipeline stage took. Transparency UX pattern.
4. Guardrail disclaimers: "This is a testing website" banner, relevance pre-filter before any LLM call. Cheap first layer of safety.
5. LangSmith tracing wiring: traces tied to run_ids, feedback loops back to traces. Adopt the integration pattern.
6. MCP server with 5 tools: query, cypher, get_stats, get_schema, get_neighbors. Subset may apply to our MCP delivery format.
7. Test organization: tests organized by domain (admin, API, MCP, NL-to-Cypher, observability). Good structural pattern for our test suite.

**Patterns to skip or adapt:**

- NL-to-Cypher pipeline: 7-stage monolithic pipeline is not our architecture. Our 5-step agent loop (Guard, Think, Plan, Act, Write) distributes this work across typed LangGraph nodes and self-contained tools.
- Hardcoded few-shot examples (20 examples in the pipeline): we will use competency question-based routing instead, selected via the Plan step.
- 3-tier LLM fallback in Cypher generation: our multi-model harness handles tier routing at the orchestrator level, not inside individual tools.
- Neo4j-specific schema introspection: we use AGE via psycopg2, so schema context will be hand-authored or queried differently.

**Combining with NCBI screenshots:**

The UI will be grounded in two inputs: (1) the reference repo's React component patterns as code boilerplate, and (2) NCBI interface screenshots (to be provided) for visual design conventions. This gives us both a working codebase to start from and real NCBI design language to match.

### Source 2: contractor 8-layer architecture

The contractor's architecture (`reference/personal-os-work/NIH/KG/Contractor/`) defines an 8-layer system: Entry, Guarded Planning, Context Retrieval, Public Surface (GraphQL), Backend Compilation, Knowledge Modules, Provenance Response, Governance. This was assessed as too intense for V1. Instead of adopting the architecture, we extracted individual ideas worth using.

**Ideas extracted and adopted (simplified):**

1. Query classification before execution: their `cqClass` concept (lookup, single-hop, multi-hop, aggregate, exploratory) maps to our model tier routing and latency budgets. We adopt this as a lightweight output from the Plan step: query class + target entities + tool list. Not a full typed IR with joins, constraints, and resultShape.

2. Schema slicing: the context-pack builder sends only the relevant portion of the graph schema to the LLM, not the entire schema. With 14 edge types and many node properties in our AGE graph, this matters for prompt efficiency. Adopted as a lightweight function, not the full context-pack builder.

3. Provenance as first-class type: every result carries source, source_id, source_url, layer. Already decided in our system design patterns. The contractor formalized it with `provenanceRequired: true` on query plans, which confirms our direction.

4. NFR baseline cherry-picking: their 39 non-functional requirements across 10 categories, 23 tagged for POC. We will review and cherry-pick the ones applicable to our V1 (latency targets, audit logging, rate limiting) in Step 1.7 when we review contractor documents in detail.

**Ideas explicitly skipped:**

- Full typed query-plan IR (JSON schema with cqClass, focusEntities, joins, constraints, modules, resultShape, provenanceRequired): too heavy for V1. Our Plan step produces a simpler structured output.
- GraphQL as the only public surface: already decided hybrid REST+SSE for chat + GraphQL for programmatic access.
- 8-layer separation: our 5-step agent loop covers equivalent functionality with less ceremony.
- Federation scope: not V1.
- Full context-pack builder: hand-author schema context for V1, formalize into a builder when query complexity demands it.

**Key learning from contractor: separation principle.**

The contractor's architecture enforces that natural language never directly generates Cypher. There is always an intermediate representation between the user's question and the database query. In our architecture, this maps to the Plan step producing a structured output (query class, target entities, tool calls) that the cypher_query tool then compiles into actual Cypher. The LLM in the Plan step reasons about what to query; the tool handles how to query it.

### Step 1.3 decisions logged

5 decisions logged to DECISIONS.md from Step 1.3 (see table).

---

## Step 1.4: data handoff (2 sources)

### Source 1: System 1+2 data engineering repo (verified)

Verified the data handoff contract across three files: LinkML schema (`biolink_ncbi.yaml`, 513 lines), Knowledge graph server reference (`Knowledge_graph_on_server_reference.md`), and Background_requirements.md Section 6. All three agree. No conflicts.

What System 3 inherits:

- 10 node types: Gene (67.5M), Article (40M), SequenceVariant (4.5M), OrganismTaxon (2.7M), Disease (200K), BiologicalProcess, MolecularActivity, CellularComponent, OntologyClass, PhenotypicFeature
- Plus ~81K NamedThing stubs (dangling endpoint fill from merger, 0.07% of total nodes)
- 14 edge predicates: gene_associated_with_condition, is_sequence_variant_of, has_phenotype, participates_in, actively_involved_in, located_in, mentioned_in, has_mesh_annotation, in_taxon, subclass_of, close_match, exact_match, orthologous_to, cited_in
- 9 CURIE prefixes: NCBIGene, ClinVar, MedGen, PMID, NCBITaxon, GO, MeSH, HP, MONDO (most diseases use MedGen prefix, not MONDO)
- Connection: `postgresql://kg_reader@46.225.128.133:5432/ncbi_kg` with AGE prelude (`LOAD 'age'; SET search_path = ag_catalog, "$user", public;`)
- Provenance: every node/edge has `source` + `source_url` (required in schema). BioLink 4.x compliant with knowledge_level and agent_type on edges.
- Indexes: GIN on 4 largest vertex labels (Gene, Disease, BiologicalProcess, SequenceVariant); B-tree on start_id/end_id for all 14 edge tables
- Three Cypher performance rules: always specify edge labels (never untyped `[r]`), match by `id` property, keep regex narrow on large labels

Known data quality issues on current graph:

1. MedGen Disease nodes have corrupted `name` field (shows vocabulary codes like "SNOMEDCT_US" instead of actual disease names). IDs and edges are correct.
2. ~81K NamedThing stubs from merger dangling endpoints. IDs are correct, category is wrong.

### Source 2: V1 shoring-up recommendations

Reviewed `V1_shoring_up_recommendations.md` (6 items across 3 priority tiers).

Key finding: none of the 6 items are System 3 blockers. All are data pipeline fixes (merger, loader, health check) that affect the next graph reload, not the current query path. The graph is already loaded and running. System 3 connects read-only and queries the graph as-is.

The 6 items:

Tier 1 (fix before next graph reload):

1. Extend PREFIX_TO_CATEGORY map (10 entries, missing prefixes default to NamedThing). Small effort.
2. Add connection recovery to loader (no retry during 2-4 hour loads). Medium effort.
3. Automated graph health check (7 smoke queries post-reload). Small effort.

Tier 2 (fix before portfolio):

- Parser unit tests (15+ parsers have no tests). Medium effort.
- End-to-end smoke test (nothing tests the whole pipeline chain). Medium effort.
- SQL identifier validation (code smell in loader, not a vulnerability). Trivial effort.

### Resilience principle (emerged from discussion)

The discussion surfaced a key architectural principle: the three-layer architecture is not just a data access pattern, it's a resilience strategy.

- Layer 1 (graph) is a periodic snapshot. Snapshots can have stale data, corrupted fields, wrong categories, missing nodes.
- Layer 2 (live NCBI APIs) is always current and always authoritative.
- Layer 3 (enrichment) adds context on top of whatever the other two produced.

Principle: Layer 1 for speed, Layer 2 for correction, Layer 3 for enrichment.

How System 3 handles each known issue:

1. NamedThing stubs: cypher_query tool infers real type from CURIE prefix, or filters stub from results.
2. MedGen name corruption: agent detects vocabulary code in name field, fetches actual display name from MedGen API (Layer 2).
3. Connection handling: System 3 has its own connection pooling with retry logic (separate from loader).
4. Graph health on startup: lightweight check (verify expected vertex labels exist and have non-zero counts).

UX requirement: the user must never see nothing. If Layer 1 has bad data, fall back to Layer 2/3. If an API fails, synthesize from whatever did respond. A degraded answer with an explanation is always better than a blank screen.

### Step 1.4 decisions logged

3 decisions logged to DECISIONS.md from Step 1.4 (see table).

---

## Step 1.5: agent and harness research (22 sources)

### Overview

Reviewed all 22 research documents in `reference/personal-os-work/NIH/Agentic-Search/Reference/system/`. Two passes: first pass extracted surface-level ideas, second deep dive focused on harness engineering architecture (tools, memory/SOUL, MCPs, API patterns, middleware) after Monideep pushed for deeper introspection.

### Core philosophy (from discussion)

Monideep's framing: "LLMs are just a brain. The harness makes it deterministic and financially viable."

Three principles that drive the architecture:

1. Harness is the product. The LLM is just a brain. The harness (tools, memory, orchestration, verification, safety) is what makes the system work.
2. Deterministic as possible. The more logic lives in code (not LLM judgment), the more reliable and cheaper the system is. But not so deterministic it gives wrong answers. Balance: LLM has narrative flexibility, harness handles everything else.
3. Citations and provenance must be perfect. Not "usually right." Always right. This is the trust moat.

### The 11 harness components (from Agent_harness_engineering.md)

The primary harness engineering doc defines 11 components of a production harness. Mapped against our architecture:

| # | Component | Our mapping | V1 status |
|---|-----------|-------------|-----------|
| 1 | Orchestration loop | LangGraph 5-step loop (Guard, Think, Plan, Act, Write) | Covered |
| 2 | Tools | cypher_query, ncbi_efetch, ncbi_dbsnp, pubtator_annotate, litvar2_lookup | Covered |
| 3 | Memory (short + long-term) | SOUL.md behavioral directives + session context | New for V1 |
| 4 | Context management | Result compression + schema slicing | Covered |
| 5 | Prompt construction | Hierarchical: system + tools + schema slice + history + query | Needs design |
| 6 | Output parsing | Structured JSON from Write step | New for V1 |
| 7 | State management | LangGraph typed state + checkpointing | Covered |
| 8 | Error handling | Graceful degradation + error classification | Partial |
| 9 | Guardrails and safety | Guard step + security (Step 1.10) | Planned |
| 10 | Verification loops | Rules-based checks on output before user sees it | New for V1 |
| 11 | Subagent orchestration | Not needed for V1 (single orchestrator) | Deferred |

### LLM as narrative controller (key architectural decision)

The LLM's job is single-responsibility: write the narrative text that explains the data to the user. It receives pre-assembled, cited data from the harness and writes a natural language summary with placeholder markers ([1], [2]).

The harness (deterministic code) handles everything else:

- Tool execution and result collection
- Citation assembly from structured tool outputs (source_url from graph nodes, API record URLs, PubTator section references)
- Provenance formatting and validation (every CURIE resolves, every URL is real)
- Mapping narrative markers to verified sources
- Stripping any marker that doesn't match a real tool result
- Cost control and latency budgets
- Error handling and graceful degradation

Why this split matters for cost: if the synth tier only writes narrative from pre-assembled data, it doesn't need frontier-level reasoning. A mid-range open-source model handles this job. The harness absorbs the complexity so the model can be cheaper. Determinism = financial viability.

### Tool design philosophy

From the research (Harness_engineering_CLI_source_analysis.md, Agent_harness_engineering.md):

Tools must be narrow, strongly typed, CLI-style contract surfaces. Not raw API access. The agent proposes a tool call with validated arguments, the harness executes in a controlled environment, and returns formatted results. The model never sees raw API responses.

Design principles:

- Each tool has a JSON schema (name, description, parameters)
- Harness validates arguments before execution
- Parallel reads, serial writes for safety
- Deterministic tool ordering (alphabetical) for stable KV cache hits
- Fewer tools per step improves LLM performance (tool scoping)

Decision: tools are direct Python functions inside the FastAPI app for V1. The MCP delivery format (one of our 5 formats) wraps the same functions behind MCP protocol as a separate layer. This avoids inter-process communication overhead while keeping the same tool code for both the web UI agent and programmatic MCP access.

### Memory and SOUL.md pattern

From the research (OpenClaw_adapter_plugin_and_agent_memory_patterns.md), expanded with Monideep's personalization vision:

The SOUL.md pattern defines behavioral directives that constrain how the LLM operates. For our search agent:

- SOUL.md: domain rules ("prioritize peer-reviewed sources," "always include clinical significance," "never state causation without evidence type," "cite every claim"). Loaded into the prompt every session.

MEMORY.md and user personalization (Monideep's vision for the full system):

The system should feel like a personalized research companion, not a chatbot. The flow:

1. User logs in (ideally through NCBI network, but any auth for V1). Provides name, profession, research focus.
2. This profile gets fed into every query as context. The agent knows who it's talking to.
3. As the user runs queries, the system tracks query types, themes, and research patterns.
4. On return visits: "Hi Monideep, welcome back. Want to continue your research on [topic]?" Feels personal.
5. Each answer leads to the next question — the system maintains state and suggests follow-up directions, like a research conversation that builds on itself.

Why this matters (connects to hook model, Step 1.6): when someone invests time into building something (IKEA effect), they're much more willing to keep using it. The memory creates investment. The personalization creates the internal trigger ("I have a question, let me ask my system"). The follow-up suggestions create variable reward ("what will it find next?").

SOUL.md = behavioral directives (domain rules, loaded every session, same for all users).
MEMORY.md = per-user learned context (query history, research themes, preferences, built over time).
USER.md = user profile (name, profession, research focus, set at login).

For V1: SOUL.md (behavioral directives) is required. USER.md (basic profile from login) is required if auth is in V1 (deferred to Step 1.8). MEMORY.md (learned patterns over time) is V1.1 — it needs enough query volume to be meaningful.

### Verification loops

From the research (Agent_harness_engineering.md):

After the Write step produces output but before the user sees it, a verification pass runs:

1. Rules-based checks (cheap, deterministic): every citation marker maps to a real tool result, CURIEs resolve, source_urls are valid
2. Structural checks: answer addresses the original query intent, required fields present in structured output
3. LLM-as-judge (expensive, edge cases only): check if the narrative actually reflects the data it claims to cite

Rules-based checks run on every response. LLM-as-judge is reserved for the eval harness (Phase 4), not the live query path.

### Actionable ideas extracted (beyond what's already decided)

From the 22 documents, after filtering out ideas that confirm existing decisions:

1. Structured JSON output from Write step: summary, genes[], citations[{pmid, source_url}], confidence. Enables machine verification. (Small effort)
2. Six-metric agent evaluation (DeepEval): PlanQuality, PlanAdherence, TaskCompletion, StepEfficiency, ToolCorrectness, ArgumentCorrectness. Feeds Phase 4 eval harness. (Small effort)
3. Encode quality as tests, not prompts: "every citation must include PMID or DOI," "results should cluster by mechanism." Run after Write step. (Small effort)
4. Deterministic tool ordering: alphabetical presentation to LLM for KV cache stability. (Trivial effort)
5. Prompt caching: system prompt + schema context reused across session. Meaningful cost reduction. (Small effort)
6. Spec-driven harness: agent behavior as versioned specs in git, not monolithic prompts. (Medium effort)
7. Session memory (V1.1): track query history, domain focus, preferred sources. (Medium effort, deferred)

### Ideas confirmed (already decided, research validates)

- Data source adapter pattern (Decision #5)
- Single orchestrator, not multi-agent (Decision #26)
- Model selection deferred to Phase 6 ablation (Decision #27)
- Open-source LLMs preferred (Decision #23)
- Result compression before context injection (Decision #31)

### Step 1.5 decisions logged

4 decisions logged to DECISIONS.md from Step 1.5 (see table).

---

## Objective review of Steps 1.1-1.5

After completing Steps 1.1-1.5, an objective review of all accumulated decisions was conducted to identify gaps, feasibility concerns, and areas where pushback was warranted.

### Concerns raised and resolutions

1. Cypher generation gap (critical): the NL-to-Cypher separation was decided but HOW Cypher gets generated wasn't. Resolved: the cypher_query tool makes its own LLM call (plan-tier model, cheap) to generate Cypher from structured intent, constrained by schema slice + few-shot examples + edge label rules. Generated Cypher is validated before execution (syntax, forbidden keywords, edge labels, row limit). One retry on validation failure, then fail gracefully. The main agent never sees or generates Cypher.

2. Five delivery formats: initially flagged as too much scope. Resolved: the reference repo already has working examples of most formats (MCP, API, KGX), built in 2 days. The boilerplate exists. Scope is manageable.

3. Budget: clarified as ~$100/month (relative marker, not hard cap), not $100 total. This is comfortable for development and testing.

4. User data storage: needs a separate database for user profiles, query history, session state. Options: Neo4j, Railway-hosted PostgreSQL, SQLite. Decision deferred to Step 1.8 (tools and infrastructure).

5. Concurrent users: not an immediate concern at V1 launch volume. Design for it (connection pooling, session isolation) but don't over-engineer.

6. Verification loop: confirmed as in-memory checks only. No HTTP calls for URL validation on the live path. Format validation, marker-to-result matching, CURIE format checks. Fast and deterministic.

Monideep's philosophy on feasibility: "Once we have the PRD and everything set up, it should take us at most two to three weeks to build. That is why I'm putting in so much effort up front so that our building effort becomes easier."

### Decisions logged from objective review

2 decisions logged to DECISIONS.md (Cypher generation strategy, budget clarification).

## What's next

Steps 1.1 through 1.5 complete. Resume with Step 1.6 (user psychology and product design, 4 sources).
