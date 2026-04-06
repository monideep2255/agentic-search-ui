# NCBI agentic search - innovation project proposal

## Executive summary

We propose building an alpha version of agentic search for NCBI: a system where a biomedical researcher asks a plain English question and gets a single, cited answer sourced from across all NCBI databases (except SRA and dbGaP). Every fact traces to a specific record in a specific database. The system is built on a BioLink-compliant knowledge graph (KG) that maps the connections NCBI already maintains into a unified, queryable structure.

The alpha is a 6-month effort in two phases. Phase 1 (months 1-3) builds the KG and data pipelines, deploys on NCBI infrastructure, and onboards internal subject matter experts (SMEs). Phase 2 (months 4-6) adds automated quality monitoring, an evaluation pipeline, and prepares for limited external testing. A key goal of the alpha is testing whether search performs efficiently over a large-scale KG within a realistic compute budget.

The project requires a core team of 2 (existing), 1 additional developer, and part-time access to NCBI data-type experts as databases are integrated. Infrastructure needs include Neo4j instances (~$1,000-2,000/month), enterprise large language model (LLM) API access (~$1,000-3,000/month), and an observability platform (~$500-1,500/month). The system will be built on Python/Django, React, and GraphQL, aligned with NCBI's standard technology stack.

This work is aligned with three strategic directives: NCBI's FY26 guiding principles (simplify discovery, optimize for AI consumption), NIH's Gold Standard Science plan (reproducibility, transparency), and America's AI Action Plan (AI-ready scientific datasets, National Science and Technology Council (NSTC) data quality standards). Two prior experiments (Model Context Protocol (MCP) orchestration and in-memory KG), along with the NLM/NCBI KG proof of concept (PoC), validated the approach and informed the architecture described in this proposal.

## Vision

A biomedical researcher asks 1 question and gets 1 answer, sourced from every relevant NCBI database, with every fact cited and every connection visible. No more navigating 30+ databases separately. No more being the integration layer. NCBI becomes a single, intelligent knowledge source.

## The problem and why now

Three strategic directives converge on the same need. NCBI's FY26 guiding principles call for simplifying content discovery, eliminating the need for users to understand NCBI's internal architecture, and optimizing content and metadata for AI and machine consumption. NIH's Gold Standard Science implementation plan (August 2025) requires that NIH-supported science be reproducible, transparent, and communicative of error and uncertainty. At the federal level, America's AI Action Plan (July 2025) directs agencies to build "the world's largest and highest quality AI-ready scientific datasets" and calls on the NSTC to set minimum data quality standards for biological data used in AI model training. Together, these directives point to the same gap: NCBI has the data and the knowledge of how entities connect across databases, but this knowledge is not yet mapped into a unified, queryable structure that meets these goals.

NCBI maintains over 30 specialized databases, each serving a distinct function in biomedical research. These databases operate independently, requiring biomedical researchers to navigate multiple interfaces and manually synthesize results across systems. The core bottleneck is not finding information within 1 database. It is connecting findings between them.

A typical multi-database investigation looks like this: a biomedical researcher finds a variant mentioned in a PubMed Central (PMC) paper, follows a link to its classification in ClinVar, then navigates to Datasets for the gene's reference sequence. Some cross-links exist, but the researcher still drives the process, deciding what to look up next and tracking the connections manually. The researcher is the integration layer. This process consumes significant expert time per investigation, and the deeper risk is that connections get missed because no human can hold all the relationships in their head across 30+ databases.

The tools to close this gap now exist. The BioLink standard gives us a shared vocabulary across databases. Domain ontologies such as Gene Ontology (GO), Monarch Disease Ontology (MONDO), etc. give us the relationship structures. And the KG approach gives us a way to connect entities across databases so the system can trace paths that no single database exposes on its own. A standards-compliant KG that unifies NCBI data would directly address the FY26 guiding principles, align with the AI Action Plan's mandate for AI-ready scientific datasets, and position NCBI to meet upcoming NSTC data quality requirements.

The question is not whether this should be built, but who should build it. NCBI has advantages that cannot be replicated:

- We own the data: NCBI serves structured, curated data directly from the source. External tools scrape or index with inherent lag.
- We have the SMEs: NCBI data-type experts can validate outputs, creating a feedback loop that improves quality over time. This cannot be replicated with more compute.
- We see the connections: A KG that links genes to diseases through variants through pathways answers questions that no single database or literature search can answer.

## What we are proposing

We propose building an alpha version of agentic search for NCBI, applying the lessons from our experiments and the NLM/NCBI KG project to create a new KG purpose-built for cross-database search, deploying on NCBI infrastructure, and establishing an SME feedback loop to build trust and measure quality.

### How it works

The system has 2 sides connected by a shared KG:

![System architecture](diagrams/architecture.png)

Data engineering: Gets NCBI data into the graph. Each data source has its own pipeline. It pulls raw data, maps it to the BioLink standard, validates, and loads it. This runs on a schedule (some databases update daily, others weekly).

AI search: Gets answers out of the graph. The agent follows a structured loop (think, plan, act, write) with guardrails at the entry point:

![Agent loop](diagrams/agent-loop.png)

The agent does not jump straight to action. It first checks guardrails (is this a valid biomedical question? is the query safe?), then thinks (what is the user really asking? what context and constraints matter?), then plans (which data sources are relevant? what sequence of retrieval steps will produce the best answer?), then acts (queries the KG, fetches related entities and relationships), and finally writes (synthesizes the data into a readable, cited answer and records context, decisions, and outcomes so the system stays consistent and improves over time). Every assertion links back to its source record.

The KG: Sits between them as the single source of truth. Data engineering writes to it. AI search reads from it. This separation keeps the data layer stable while the search layer improves continuously. But architecture alone does not earn biomedical researcher adoption. Trust does.

### Trust at the center

Trust is the foundation this system is built on. Biomedical researchers will not adopt a tool they cannot verify. Every design decision serves trust:

- Full provenance: Every fact in every answer links to a specific record in a specific NCBI database. Nothing is generated from training data alone.
- Evaluation feedback loop: The system improves through 3 layers of evaluation, all feeding back into the search and orchestration layer (not the data itself), keeping the KG stable while the agent continuously improves.
  - Golden datasets: SMEs help build curated question-answer pairs that define what a correct answer looks like. The system scores itself against these.
  - LLM-as-judge: An independent review layer checks each answer for citation accuracy, completeness, and grounding in the data.
  - User feedback: direct signals (thumbs up/down) and behavioral signals (abandoned queries, repeat searches, session depth) track real-world quality.
- Subject matter expert validation: NCBI data experts for each type of data review outputs, help build golden datasets, and define what good answers look like. Their expertise feeds directly into the evaluation loop.
- What this is not: This is not a chatbot, a literature summarizer, or a general-purpose AI assistant. It is a structured data retrieval system where every answer can be verified against its source.

### Delivery formats

The system serves answers through multiple channels.

- Web interface: for interactive research queries
- REST (Representational State Transfer) API: for programmatic access and integration with existing tools
- MCP server: a standard interface for AI agents so external research pipelines can query NCBI data directly
- KGX (Knowledge Graph Exchange) export: for bulk download in a standardized graph exchange format
- CLI (Command-line interface) agent: for terminal-based querying and scripting into research workflows

### Alpha scope

The alpha is not limited to a subset of NCBI data. The goal is to build a new KG for agentic search that integrates all NCBI databases following the BioLink standard and relevant ontologies. The two exceptions are SRA and dbGaP. SRA contains raw sequencing reads (petabytes of FASTQ files) that are consumed by analysis pipelines, not search queries. dbGaP is controlled-access data that requires individual Data Access Requests with IRB approval, making it a separate compliance effort. The system should be able to answer questions across any area that the underlying data covers.

For literature, the system uses PubMed, which provides the full-text open access subset available in PMC, enriched via PubTator for structured entity extraction. Existing work on PubMed/PMC by other groups in the Division of Intramural Research (DIR) will be leveraged where possible. Datasets is a delivery service (not a database) that currently covers Genome, Virus, Gene, and a subset of Protein and Nuccore, giving the KG access to multiple underlying data types through a single integration point.

| Dimension | Alpha |
|-----------|-------|
| Data sources | All NCBI databases (except SRA and dbGaP), including PubMed/PMC, ClinVar, Datasets, MedGen, integrated into a BioLink-compliant KG with relevant ontologies |
| Search scope | Any query the integrated data sources can answer, not domain-restricted |
| Graph | Target: all entities and relationships across integrated databases |
| Users | Internal SMEs and select biomedical researchers (invite-only) |
| Deployment | NCBI-managed infrastructure |

## What's needed

### Personnel

Alpha (0-to-1): The core team of 2 (existing) owns everything end to end, including architecture, data engineering, search agent, product direction, evaluation pipeline, and dogfooding. SMEs are stakeholders who validate outputs and help build golden datasets, not dedicated team members.

| Role | Need |
|------|------|
| Core team | 2 (existing). End-to-end: engineering, product, evaluation, dogfooding. |
| Developer | 1 (new). Support data pipeline development and search agent engineering. |
| SME stakeholders | NCBI data-type experts, part-time as needed per integrated database. Validate outputs, help build golden datasets, test the system. |

### Technology stack

The system will be built on Python/Django (backend and data pipelines), React (frontend), and GraphQL (API layer). This ensures future migration into NCBI's standard infrastructure is straightforward. All code will be hosted on GitLab.

### Infrastructure and tools

| Area | What's needed | Estimated cost |
|------|---------------|----------------|
| Data engineering | NCBI API access for bulk data ingestion across all databases (except SRA and dbGaP). PubTator for structured entity extraction from literature. | Existing NCBI infrastructure |
| Graph database | Neo4j Enterprise or Professional instance (managed or self-hosted on NCBI servers) | ~$1,000-2,000/month |
| LLM API access | Enterprise-tier access for query translation, answer synthesis, and evaluation. Estimated volume: hundreds to low thousands of queries/month during alpha. | ~$1,000-3,000/month |
| Development | GitLab repository (existing). VS Code with LLM-assisted development tooling. | Existing |
| Observability | LangSmith or Arize AI for tracing agent behavior, latency, and LLM call quality. NCBI/NLM-managed instance. | ~$500-1,500/month |
| Analytics | NCBI Applog (existing) + Google Analytics for user behavior tracking, session analysis, and evaluation metrics. PostHog as alternative if additional event tracking is needed. | Minimal (existing infrastructure) |

### Post-alpha (scaling)

Once the alpha proves the system works, it generates the evaluation data, SME feedback, and performance benchmarks needed to justify scaling. A successful alpha means the system has proven it can answer cross-database questions accurately at scale, creating the foundation for broader external access, deeper answer quality improvements, and a path toward a more unified research experience across NCBI.

Expanding to that next stage requires a dedicated team:

| Role | Need |
|------|------|
| Data engineering | Dedicated support for maintaining database ingestion pipelines |
| Software engineering | Scale the search agent, API, and infrastructure |
| Cybersecurity | Security review, access controls, threat modeling for production deployment |
| Subject matter experts | Expanded SME coverage for deeper validation and answer quality |
| Project management | Coordinate cross-team delivery as scope and stakeholders expand |

## Timeline

With the resources above in place, the following timeline applies. The proof of concept has validated the core approach at small scale. What remains is testing whether the system can search efficiently over a large-scale KG within a realistic compute budget, expanding database coverage, and hardening for production use.

### Phase 1: alpha foundation (months 1-3)

Goal: Expand database coverage, leveraging existing NCBI data infrastructure and standards where available. Deploy on NCBI infrastructure. Get SMEs using it.

| Month | What happens | Deliverables | How we know it's done |
|-------|-------------|-------------|----------------------|
| 1 | Build data pipelines across NCBI data sources (except SRA and dbGaP). Each pipeline: pull data, map to BioLink, validate, load. Leverage existing DIR work on PMC/PubMed. | BioLink schema definition. Per-source extract-transform-load (ETL) pipelines. Validation reports for each data source. | Each pipeline passes BioLink validation. Data loads into Neo4j without errors. Schema is reviewable. |
| 2 | Load data into the graph. Extend the search agent to handle new entity types and relationships. | Populated KG across integrated databases. Search agent returning cross-database answers. | Cross-database Cypher queries return connected results. Agent answers sample questions with citations. |
| 3 | Deploy on NCBI servers. Onboard internal SMEs. Build initial evaluation dataset (50-500 ground-truth question-answer pairs). | Live system on NCBI infrastructure. Golden dataset. First evaluation scores. | SMEs can query the system and get cited answers. Relevance score baseline established. |

Exit criteria: SMEs can ask questions across integrated databases and get accurate, cited answers. Relevance score baseline established through SME evaluation.

### Phase 2: alpha hardening (months 4-6)

Goal: Measure quality systematically. Build automated checks. Prepare for limited beta.

| Month | What happens | Deliverables | How we know it's done |
|-------|-------------|-------------|----------------------|
| 4 | Build automated answer review system. Checks: Is every claim backed by data? Are citations correct? Did the agent miss a source? | LLM-as-judge pipeline. Automated quality gate. | Bad answers flagged before reaching users. Quality gate rejects ungrounded responses. |
| 5 | Build full evaluation pipeline. User feedback collection, scoring against ground truth, session tracking. | Quality dashboard. Feedback collection interface. Scoring pipeline. | Dashboard shows accuracy trends. Feedback loop is active and feeding into agent improvements. |
| 6 | Test graph traversal performance at scale (query speed depends primarily on edge count and traversal depth, not node count). Prepare for limited external testing. | Performance benchmarks across query types. Beta access plan for a limited set of external users. | Cross-database queries return results within acceptable latency at full graph scale. Ready to onboard initial external testers. |

Exit criteria: Automated quality monitoring in place. Repeat engagement (users returning to the system for new investigations) as the primary adoption signal. Ready to test with a limited set of external users.

Total: 6 months. The concept has been validated at small scale. The alpha tests whether it holds at production scale.

Publication plan: after Phase 2, once accuracy metrics and usage data from production use provide publishable evidence.

## Prior work

Over the last 6 months, we ran 2 experiments and contributed to the NLM/NCBI KG PoC. Together, these efforts validated the approach and directly informed the architecture proposed above. Each one solved a problem and revealed the next one.

### Experiment 1: MCP orchestration

We built an MCP orchestrator, a single agent that analyzed each query, planned which databases to call, then executed 4 MCP servers (PMC, ClinVar, Datasets, MedlinePlus) in parallel and synthesized the results into one answer. Each MCP server wrapped 1 NCBI application programming interface (API) with a clean, standardized interface.

What worked: 1 question, data from 4 databases. The orchestrator intelligently selected which databases to query based on the question, called them in parallel, and returned a readable summary. The MCP server pattern proved that individual NCBI APIs can be wrapped cleanly.

What didn't: Answers were fragmented because each MCP server returned flat results without leveraging the cross-database links (like E-Link) that already exist within NCBI. Additionally, the pipeline was slow (60-90 seconds, 8 LLM calls per query) and fragile (1 slow API delayed the entire answer).

Lesson: Getting the data is not the hard part. NCBI already knows how entities connect across databases. MCP works well for wrapping individual databases, but what's missing is a unified layer that makes those relationships queryable.

> [Recording](https://share.descript.com/view/uXjS7imhDar) | [Repository (main branch)](https://gitlab.be-md.ncbi.nlm.nih.gov/chakrabortim2/ncbi_ai_agents/-/tree/main?ref_type=heads)

### Experiment 2: in-memory KG

We built a KG using NetworkX with 391 nodes (59 genes, 168 variants, 18 diseases, 146 papers) and explicit relationships between them.

What worked: Answer quality improved immediately. The graph enabled zero-cost query expansion by traversing relationships to find related entities without additional LLM calls. Response time dropped to 2-3 seconds. Answer depth roughly doubled.

What didn't: The graph was small and the connections were inferred from search results rather than built from authoritative data. No recognized biomedical standard, no interoperability, no path to scale.

Lesson: Relationships are the key to better answers. But they need to be built on real standards, not inferred.

> [Recording](https://share.descript.com/view/yIjSzZEV9lK) | [Repository (knowledge-graphs branch)](https://gitlab.be-md.ncbi.nlm.nih.gov/chakrabortim2/ncbi_ai_agents/-/tree/knowledge-graphs?ref_type=heads)

### Lessons from the NLM/NCBI KG PoC

In parallel, we built a PoC for the NLM initiative as part of the NLM/NCBI KG team using Neo4j and BioLink. This PoC validated the approach and taught us what a properly engineered KG requires:

- A standard schema: BioLink so different databases can be represented consistently
- Domain ontologies: GO, MONDO, etc. to provide the relationship structures that make cross-database queries possible
- Proper data engineering: NCBI already has the data and the knowledge of how entities are connected across databases. What has changed is that AI-assisted tooling now makes the cleaning, mapping, and validation work dramatically faster than the manual processes of the past. The graph quality still determines the answer quality, but the cost of building a high-quality graph has dropped significantly.

These are the engineering foundations we will apply to the agentic search system.

> [Repository (ncbi-kg branch)](https://gitlab.be-md.ncbi.nlm.nih.gov/chakrabortim2/ncbi_ai_agents/-/tree/ncbi-kg?ref_type=heads) | [Live application](https://ncbi-kg-frontend-production.up.railway.app/)

### Already validated (from the NLM/NCBI KG PoC)

These patterns and tools have been proven in the parallel NLM/NCBI KG project and can be applied directly to the agentic search alpha:
- BioLink validator for automated data quality checks
- MCP server architecture (published and installable)
- Data ingestion pipeline patterns (per-database, BioLink-mapped, validated)
- Safety guardrail design patterns

## Risks and mitigations

| Risk | Mitigation |
|------|-----------|
| AI generates answers not grounded in the data | Every assertion must trace to a specific graph record. The guardrail layer validates queries before they reach the graph. The LLM-as-judge layer independently reviews answers for accuracy. Automated answer review flags bad answers before they reach users. |
| System doesn't scale to all NCBI databases | BioLink schema is database-count agnostic. Each data source is added as an independent ingestion job. The alpha targets all databases (except SRA and dbGaP) from the start. |
| SMEs don't engage with feedback | Early onboarding (month 3). Lightweight feedback interface. Visible impact so their feedback directly changes system behavior. |
| Same term means different things across databases | BioLink standard + domain ontologies (GO, MONDO) handle entity alignment. Unmappable entities escalate to human experts. |
| Security: prompt injection or adversarial input | The agent's guardrail layer rejects non-biomedical, malicious, and out-of-scope queries before they reach the graph. Read-only enforcement blocks any attempt to modify data. |
| Security: data pipeline integrity | Each data ingestion pipeline validates against the BioLink schema before anything enters the graph. Malformed or suspicious records are rejected automatically. The 2-repository architecture enforces a strict security boundary where the AI search side has no write access to the KG. |

## Attachments and evidence

| Item | Link |
|------|------|
| Experiment 1: MCP orchestrator recording | [Recording](https://share.descript.com/view/uXjS7imhDar) |
| Experiment 1: repository (main branch) | [GitLab](https://gitlab.be-md.ncbi.nlm.nih.gov/chakrabortim2/ncbi_ai_agents/-/tree/main?ref_type=heads) |
| Experiment 2: in-memory KG recording | [Recording](https://share.descript.com/view/yIjSzZEV9lK) |
| Experiment 2: repository (knowledge-graphs branch) | [GitLab](https://gitlab.be-md.ncbi.nlm.nih.gov/chakrabortim2/ncbi_ai_agents/-/tree/knowledge-graphs?ref_type=heads) |
| NLM/NCBI KG PoC: repository (ncbi-kg branch) | [GitLab](https://gitlab.be-md.ncbi.nlm.nih.gov/chakrabortim2/ncbi_ai_agents/-/tree/ncbi-kg?ref_type=heads) |
| NLM/NCBI KG PoC: live application | [Live app](https://ncbi-kg-frontend-production.up.railway.app/) |
| NLM/NCBI KG PoC: integrations | [Integrations](https://ncbi-kg-frontend-production.up.railway.app/integrations) |
