# Phase 1 session: May 7, 2026

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

## What's next

Steps 1.1 and 1.2 complete. Move to Step 1.3 (reference implementations, 2 sources):
1. NCBI KG repo, ncbi-kg branch (`reference/ncbi_ai_agents-ncbi-kg/`)
2. Contractor 8-layer architecture (`reference/personal-os-work/NIH/KG/Contractor/`)
