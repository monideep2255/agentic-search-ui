# NCBI agentic search: personal build plan

Open source portfolio project. 2-month build with Claude Code Max ($100/month plan, unlimited usage). Built on the architecture designed in Agentic_search_architecture_QA.md and the live NCBI API data in NCBI_databases_and_APIs_reference.md.

---

## Why build this independently

NCBI may or may not fund the innovation project. But the data is public (NCBI FTP + free APIs), the tools are available (Neo4j Community, LangGraph, FastAPI), and the architecture is designed. The only cost is time and ~$200-500 in hosting over 2 months.

What this becomes:
- Open source project that nobody else has built (agentic search across all NCBI databases)
- Portfolio piece demonstrating: data engineering, knowledge graphs, AI agents, full-stack, API design, BioLink compliance
- Publishable (Bioinformatics, NAR Database Issue, or JAMIA)
- Adoptable by NCBI if they want it later (Apache 2.0 license)
- Community magnet for bioinformaticians who use Claude/GPT for research

---

## Total cost

### Monthly costs

| Item | Cost | Notes |
|---|---|---|
| Claude Code Max | $100/month | Already paying. Unlimited usage. No overage. |
| LLM API for agent layer (production queries) | $50-150/month | Sonnet for search queries. Haiku for evaluation. Low volume during alpha. |
| VPS (Neo4j + FastAPI + Redis) | $25-50/month | Hetzner CX31 (8GB RAM, 4 vCPU, 80GB SSD) at ~$8-15/month, or DigitalOcean droplet at $24-48/month. Neo4j Community Edition is free. |
| Object storage (FTP dumps) | $1-5/month | S3 or local disk. ~50GB total for all FTP dumps. |
| Domain name | $1/month | Optional. ~$12/year. |
| NCBI APIs | Free | Already have API key. 10 req/sec. |
| Research APIs (PubTator3, LitVar2, LitSense, ClinicalTrials.gov) | Free | No API keys needed. |
| LangSmith (observability) | Free | Free tier: 5K traces/month. Enough for alpha. |
| PostHog (analytics) | Free | Free tier: 1M events/month. Enough for alpha. |

### 2-month total

| Scenario | Monthly | 2-month total |
|---|---|---|
| Minimum (free tiers, cheapest VPS) | $130-170 | $260-340 |
| Comfortable (decent VPS, Sonnet API) | $175-300 | $350-600 |

Honest number: **$300-500 total cash out of pocket for a 2-month alpha.**

For context: BCC is charging $2.6-3.3M for a narrower scope. You're building broader coverage for under $500.

### Why the data is already curated (no SME cost needed)

You don't need a curation UI or dedicated SME time for the data layer. NCBI databases are curated at the source:

| Database | Professional curators | What they curate |
|---|---|---|
| ClinVar | Clinical labs, expert panels, practice guidelines committees | Every variant-disease assertion has a review status |
| Gene | NCBI RefSeq curators | Gene records, RefSeq sequences, gene2go annotations |
| PubMed | NLM indexers | MeSH terms assigned by trained librarians to 40M articles |
| MedGen | NLM terminology experts | Disease concepts mapped to OMIM, MONDO, SNOMED, MeSH, HPO |
| Taxonomy | NCBI taxonomy curators | 2.9M organisms with validated lineage |
| PubChem | PubChem standardization pipeline | Chemical structures validated and cross-referenced |

The knowledge graph inherits this curation. You validate the search and synthesis layer, not the underlying data.

---

## 2-month build plan

### Prerequisites (before week 1)

- [ ] NCBI API key in .env (have it)
- [ ] Neo4j Community Edition installed locally (for dev)
- [ ] Python 3.11+ environment
- [ ] Node.js 18+ (for web UI)
- [ ] Clone/init the repo structure

### Week 1-2: schema + first pipelines + graph loader

Goal: Gene and ClinVar data flowing into Neo4j with BioLink compliance.

| Day | Task | Output |
|---|---|---|
| 1 | Define LinkML schema for core node types (Gene, Disease, SequenceVariant, Publication, OrganismTaxon) and core edge predicates | `schema/biolink_ncbi.yaml` |
| 2 | Write Gene ETL pipeline: download gene_info.gz, gene2go.gz, gene2pubmed.gz from FTP. Parse, map to BioLink, validate against LinkML, export KGX. | `data-pipelines/gene/` |
| 3 | Write ClinVar ETL pipeline: download ClinVarFullRelease.xml.gz. Parse VCV records, extract variant-gene-disease edges with edge-level provenance. Export KGX. | `data-pipelines/clinvar/` |
| 4 | Build Neo4j loader: read KGX nodes.tsv + edges.tsv, create nodes with properties, create relationships with provenance properties. | `knowledge-graph/loader/` |
| 5 | Load Gene + ClinVar subgraphs. Write first 5 CQ test skeletons (Cypher). Run them. Fix schema issues. | First graph: ~100M nodes (Gene) + ~4.5M (ClinVar) |
| 6-7 | Write SSSOM mapping files for Gene-to-HGNC, ClinVar-to-MONDO (via MedGen CUI), Gene-to-GO. Record every mapping decision. | `knowledge-graph/mappings/*.sssom.tsv` |
| 8-10 | Write node normalization: resolve NCBIGene, MONDO, PMID, dbSNP prefixes. Deduplicate cross-database entities. Build merge script. | `knowledge-graph/merge/` |

Milestone: Gene + ClinVar in Neo4j. CQ test skeletons passing. Edge-level provenance on every relationship.

### Week 3-4: remaining pipelines + PubMed + merge

Goal: 5-6 databases in the graph, all linked, all CQ tests passing.

| Day | Task | Output |
|---|---|---|
| 11-12 | MedGen ETL: download MedGenIDMappings.txt, MGREL. Parse disease-to-ontology mappings (MONDO, OMIM, MeSH, SNOMED, HPO). Export KGX. | `data-pipelines/medgen/` |
| 13-14 | PubMed ETL: download baseline XML (start with 2024-2026 subset, ~5M articles). Parse, extract MeSH annotations, link via gene2pubmed. Export KGX. | `data-pipelines/pubmed/` |
| 15-16 | Taxonomy ETL: download taxdump.tar.gz. Parse names.dmp + nodes.dmp. Build full lineage tree. Export KGX. | `data-pipelines/taxonomy/` |
| 17-18 | SNP ETL (clinical subset only): download ClinVar cross-references to dbSNP. Parse clinically annotated variants only. Export KGX. | `data-pipelines/snp/` |
| 19-20 | Full merge: run all 6 subgraphs through node normalization + Cat-Merge + Neo4j load. Write 15 more CQ test skeletons (total: 20). Run all. | Merged graph: ~150M nodes |

Milestone: 6-database graph. 20 CQ tests passing. Cross-database traversal working (Gene -> ClinVar -> MedGen -> PubMed).

### Week 5-6: search agent + API + MCP

Goal: all 8 agents working, FastAPI backend serving queries, MCP server exposable.

| Day | Task | Output |
|---|---|---|
| 21-22 | Agent 1 (Orchestrator) + Agent 2 (Query Understanding): LangGraph graph with entity extraction, intent classification. | `search-agent/orchestrator/`, `search-agent/query_understanding/` |
| 23-24 | Agent 3 (Retrieval Planner): decides which databases, plans Cypher queries, sets API budget. | `search-agent/retrieval_planner/` |
| 25-26 | Agent 4 (Graph Searcher): generates parameterized Cypher from plan, executes against Neo4j, returns subgraph. | `search-agent/graph_searcher/` |
| 27-28 | Agent 5 (API Caller): ELink/EFetch for on-demand databases, PubTator3 for entity extraction, LitVar2 for variant evidence, LitSense for sentences, ClinicalTrials.gov. Redis caching. | `search-agent/api_caller/` |
| 29-30 | Agent 6 (Synthesizer): merges graph + API results, writes cited markdown answer, generates graph viz data. | `search-agent/synthesizer/` |
| 31-32 | Agent 7 (Evaluator): LLM-as-judge for citation accuracy, completeness, grounding. Async, non-blocking. | `search-agent/evaluator/` |
| 33-34 | FastAPI backend: `/search`, `/entity`, `/traverse`, `/graph/cypher`, `/status` endpoints. Auth middleware (API key). Rate limiting. | `api/` |
| 35-36 | MCP server: `ncbi_search`, `ncbi_entity_lookup`, `ncbi_graph_traverse`, `ncbi_literature_evidence` tool definitions. | `mcp-server/` |

Milestone: ask a question via API, get a cited multi-database answer. MCP server callable by Claude/GPT.

### Week 7-8: UI + CLI + eval + deploy + docs

Goal: all 5 access channels working, evaluation pipeline running, deployed and documented.

| Day | Task | Output |
|---|---|---|
| 37-38 | Web UI: React + Cytoscape.js. Search box, streaming answer display, interactive graph visualization, source links, entity cards. | `web-ui/` |
| 39-40 | CLI agent: `ncbi-search` command. NL search, entity lookup, graph traversal, batch queries. Pipe-friendly JSON/TSV output. | `cli/` |
| 41-42 | KGX export endpoint: monthly snapshot generation, subset export (gene-disease, clinvar-only, etc.). | `api/export/` |
| 43-44 | Evaluation pipeline: 20-30 golden QA pairs, CQ test suite (automated), LLM-as-judge scoring, quality dashboard. | `eval/` |
| 45-46 | Agent 8 (Graph Monitor): post-pipeline quality checks. Orphan nodes, edge count drift, schema violations. | `search-agent/graph_monitor/` |
| 47-48 | Deploy: containerize everything (Docker Compose). Deploy to VPS. SSL. Monitoring. Write README, architecture docs, contributing guide. | Production deployment |

Milestone: all 5 channels live. Evaluation pipeline running. Open source repo published.

---

## Repository structure

```
ncbi-agentic-search/
  README.md                     # Project overview, quick start, architecture summary
  LICENSE                       # Apache 2.0
  docker-compose.yml            # One-command deployment
  .env.example                  # Required environment variables

  data-pipelines/               # System 1: ETL for each database
    gene/
      pipeline.py               # FTP download, parse, BioLink map, validate, KGX export
      config.yaml               # FTP URLs, update schedule, field mappings
    clinvar/
    pubmed/
    medgen/
    taxonomy/
    snp/
    shared/
      ftp_client.py             # Shared FTP download utilities
      biolink_mapper.py         # Shared BioLink mapping functions
      kgx_exporter.py           # Shared KGX export functions

  knowledge-graph/              # System 2: schema, merge, load
    schema/
      biolink_ncbi.yaml         # LinkML schema definition
    mappings/
      gene_hgnc.sssom.tsv       # SSSOM mapping files
      clinvar_mondo.sssom.tsv
      medgen_ontologies.sssom.tsv
    merge/
      node_normalizer.py        # Canonical ID resolution
      cat_merge.py              # Deduplicate nodes, concatenate edges
    loader/
      neo4j_loader.py           # KGX to Neo4j
    tests/
      cq_test_suite.py          # 20-30 Cypher CQ skeletons
      test_cqs.py               # Pytest runner for CQ validation

  search-agent/                 # System 3: 8 agents
    orchestrator/
      agent.py                  # LangGraph orchestrator
    query_understanding/
      agent.py                  # Entity extraction, intent classification
    retrieval_planner/
      agent.py                  # Database selection, traversal planning
    graph_searcher/
      agent.py                  # Cypher generation + Neo4j execution
    api_caller/
      agent.py                  # ELink, EFetch, PubTator3, LitVar2, LitSense, ClinicalTrials.gov
      cache.py                  # Redis caching layer
    synthesizer/
      agent.py                  # Result merging, citation, graph viz data
    evaluator/
      agent.py                  # LLM-as-judge (async)
    graph_monitor/
      agent.py                  # Post-pipeline quality checks

  api/                          # FastAPI backend
    main.py                     # App + routes
    auth.py                     # API key authentication
    routes/
      search.py                 # POST /api/v1/search
      entity.py                 # GET /api/v1/entity/{type}/{id}
      traverse.py               # POST /api/v1/traverse
      graph.py                  # GET /api/v1/graph/cypher (read-only)
      export.py                 # GET /api/v1/export/{subgraph}
      status.py                 # GET /api/v1/status

  mcp-server/                   # MCP tool definitions
    server.py                   # MCP server implementation
    tools/
      ncbi_search.py
      ncbi_entity_lookup.py
      ncbi_graph_traverse.py
      ncbi_literature_evidence.py

  cli/                          # CLI agent
    ncbi_search/
      __main__.py               # Entry point
      commands/
        search.py               # ncbi-search "query"
        entity.py               # ncbi-search entity gene BRCA1
        traverse.py             # ncbi-search traverse --from gene:672
        batch.py                # ncbi-search batch queries.txt

  web-ui/                       # React frontend
    src/
      components/
        SearchBox.tsx
        StreamingAnswer.tsx
        GraphVisualization.tsx   # Cytoscape.js
        EntityCard.tsx
        SourceLink.tsx

  eval/                         # Evaluation pipeline
    golden_datasets/            # SME-curated QA pairs
    cq_tests/                   # Automated CQ Cypher tests
    llm_judge/                  # LLM-as-judge scoring
    dashboard/                  # Quality metrics dashboard

  docs/                         # Architecture documentation
    architecture.md             # From the Q&A doc
    ncbi_databases_reference.md # From the reference doc
    contributing.md
    api_reference.md
```

---

## Open source strategy

### License

Apache 2.0. Permissive, allows commercial use, has patent protection (matters for government adoption). NCBI can adopt it internally without legal friction.

### README pitch

```
# NCBI Agentic Search

Ask a question in English. Get a cited, multi-database answer in seconds.

Connects 6 NCBI databases (Gene, PubMed, ClinVar, MedGen, Taxonomy, SNP)
into a BioLink-compliant knowledge graph. An 8-agent AI system understands
your question, plans retrieval across databases, and synthesizes cited answers.

5 ways to access:
- Web UI: interactive search with graph visualization
- MCP server: for AI agents (Claude, GPT, Gemini)
- REST API: for programmatic access (OpenAPI spec)
- CLI: ncbi-search "pathogenic BRCA1 variants in breast cancer"
- KGX export: bulk graph download for data scientists

150M+ nodes. 6 databases. 30+ more on-demand via ELink.
Every fact cited. Every connection visible.
```

### Publication target

After the 2-month alpha, the system has publishable evidence:
- Graph statistics (node/edge counts, database coverage)
- CQ test suite results (what the graph can answer)
- Evaluation metrics (accuracy, completeness, grounding scores)
- Latency benchmarks (end-to-end query time)
- Architecture description (3 systems, 8 agents, 5 channels)

Target journals:
1. Bioinformatics (application note): short format, fast review
2. NAR Database Issue (annual, deadline usually June): fits the "database resource" category
3. JAMIA: if the clinical angle is strong (ClinVar + MedGen + variant-disease queries)

### Community growth

- GitHub Discussions for feature requests and Q&A
- PyPI package for CLI (`pip install ncbi-search`)
- NPM package for MCP server (`npx ncbi-search-mcp`)
- Docker image for one-command deployment (`docker compose up`)
- Example notebooks (Jupyter) showing API usage for common research workflows

---

## Risk signals to watch during build

| Risk | Signal | Response |
|---|---|---|
| PubMed baseline too large for VPS | Download exceeds available disk or load takes > 24 hours | Start with 2024-2026 subset (~5M articles), not full baseline |
| Neo4j Community can't handle 150M nodes on 8GB RAM | Cypher queries timeout or OOM | Reduce to Gene (human only, ~60K genes) + ClinVar + MedGen + Taxonomy. Still valuable, much smaller. |
| Agent quality too low | Evaluator flags > 30% of answers as ungrounded | Simplify: reduce to 3 agents (understand, retrieve, synthesize) instead of 8. Add complexity later. |
| 2 months not enough | Week 4 and only 2 pipelines done | Cut scope: ship with Gene + ClinVar + MedGen only (the core triangle). Add others post-launch. |
| LLM API costs higher than expected | Monthly bill exceeds $200 | Switch search queries to Haiku (cheaper). Use Sonnet only for synthesis. |

---

## What "done" looks like at week 8

- [ ] 6-database BioLink-compliant knowledge graph in Neo4j (150M+ nodes)
- [ ] 20+ CQ test skeletons passing
- [ ] 8-agent search system returning cited answers
- [ ] 5 access channels working (Web UI, MCP, API, CLI, KGX export)
- [ ] Evaluation pipeline with golden datasets + LLM-as-judge
- [ ] Deployed on VPS with Docker Compose
- [ ] Open source repo on GitHub with README, docs, contributing guide
- [ ] Apache 2.0 license

---

---

## 1-month vs 2-month timeline

### 1-month plan (aggressive, ship fast)

| Week | What ships | What's cut |
|---|---|---|
| 1 | Gene + ClinVar + MedGen pipelines, Neo4j loaded, 10 CQ tests | No PubMed (too large), no Taxonomy, no SNP |
| 2 | 5 agents (orchestrator, understanding, planner, graph searcher, synthesizer), FastAPI backend | Cut API caller agent (no live API augmentation). Cut evaluator. Cut graph monitor. 5 agents not 8. |
| 3 | MCP server + CLI + basic React UI (search box + streaming text, no graph viz) | No Cytoscape.js visualization. No KGX export. No entity cards. |
| 4 | Deploy, README, 15 golden QA pairs, open source | No evaluation dashboard. No graph monitor. |

Ships in 1 month: 3 databases, 5 agents, 3 access channels (API, MCP, CLI), basic web UI, deployed and open sourced.

Does NOT ship: PubMed (40M nodes), graph visualization, KGX export, evaluation pipeline, live API augmentation (PubTator3/LitVar2/LitSense). Add in month 2.

### 2-month plan (comfortable, full scope)

Everything in the week-by-week plan above. All 6 databases, 8 agents, 5 channels, graph viz, evaluation pipeline.

### Recommendation

Start with the 1-month plan. Ship something real in 4 weeks. Spend month 2 adding PubMed, graph visualization, the remaining 3 agents, and the evaluation pipeline. Shipping early creates momentum and feedback. Waiting for perfection creates nothing.

### What takes real wall-clock time regardless of coding speed

- PubMed FTP baseline download: 30GB compressed, 4-8 hours
- Neo4j loading 150M nodes: 2-6 hours per full load
- Agent tuning: prompt iteration takes human judgment loops, not just coding
- Testing: you find bugs by using it, which takes days not hours

---

## What is this worth? Equivalent contractor value

### What BCC's $3M pays for that we skip entirely

| BCC work | Cost portion | Why we skip it |
|---|---|---|
| Custom NLP from medical textbooks (HuPhysKN) | ~$327K | We use pre-built APIs (PubTator3) |
| Dedicated ontology engineer (9 months) | ~$274K | We write LinkML schema but lighter-weight |
| Human curation workflow + curation UI | ~$460K | Our data is pre-curated at source by NCBI teams |
| Formal SME review cycles, governance, PM | ~$475K | Solo project, zero coordination overhead |
| 9.75 FTE coordination overhead | ~$300-500K | One person, no meetings |

Skipped: ~$1.5-1.7M of BCC's budget. Not needed because NCBI data is pre-curated and there's no team coordination cost.

### What we ARE building (maps to BCC scope)

| Our work | BCC equivalent | Contractor cost |
|---|---|---|
| 6 database ETL pipelines | ETL engineer (1.0 FTE, 9 months) | ~$311K |
| Knowledge graph (schema, merge, Neo4j) | KG architect + graph DB engineer | ~$584K |
| FastAPI backend + API design | Part of full-stack dev work | ~$100K |
| Subtotal | | ~$800K - $1M |

### What we're building that BCC is NOT building

| Our work | If contracted | Estimated cost |
|---|---|---|
| 8-agent AI search system | AI/ML engineers (2 FTE, 3-4 months) | ~$300-500K |
| MCP server for agent-to-agent | Backend engineer (0.5 FTE, 2 months) | ~$50-80K |
| CLI agent | Backend engineer (0.25 FTE, 1 month) | ~$20-30K |
| 5 access channels (vs their 1) | Full-stack + backend (1 FTE, 3 months) | ~$150-200K |
| KGX bulk export | Data engineer (0.25 FTE, 1 month) | ~$20-30K |
| Subtotal | | ~$500K - $800K |

### Total equivalent value

| Category | Contractor value |
|---|---|
| Data engineering + KG (overlaps with BCC) | $800K - $1M |
| AI agent layer + access channels (BCC doesn't do this) | $500K - $800K |
| Total equivalent | $1.3M - $1.8M |
| Our actual cost | $300 - $500 |
| Leverage ratio | ~3,000x |

### Where the leverage comes from

1. Claude Code Max writes 80% of the boilerplate (ETL parsers, FastAPI routes, React components, Cypher generators)
2. NCBI data is pre-curated by professional teams (no NLP engineer, no curation UI, no SME review cycles needed)
3. Zero coordination overhead (no PM, no meetings, no change control for a team of 1)
4. Public FTP data (no licensing costs, no access negotiations)
5. Free tools (Neo4j Community, LangSmith free tier, PostHog free tier)

### Portfolio framing

"Built a system equivalent to $1.3-1.8M of contractor work, solo, in 2 months, for under $500, by leveraging AI-assisted development and pre-curated public data. 6 databases, 150M+ nodes, 8 AI agents, 5 access channels, open sourced under Apache 2.0."

---

---

## Legal: can NCBI sue if I open source this and leave?

Short answer: not if you build it right.

### What's safe

| Factor | Status | Why |
|---|---|---|
| NCBI data | Safe | US government work, public domain, no copyright. FTP dumps freely downloadable by anyone. |
| NCBI API | Safe | Public API. Free API key to anyone who registers. |
| Code written on personal time, personal machine | Safe | You own it. |
| Architecture and ideas | Safe | Ideas are not copyrightable. Architecture designs are not patentable by your employer unless assigned. |

### What's risky

| Factor | Status | Why |
|---|---|---|
| Code written during work hours or on government equipment | Risky | Government or employer may claim ownership under employment agreement. |
| If NCBI funds the innovation project and you reproduce the exact system externally | Risky | Even with different code, reproducing a funded project's deliverables is a problem. |
| Using NCBI internal systems, VPN, or non-public data | Risky | Creates a nexus to your employment. |

### The key distinction

If NCBI does NOT fund the innovation project: you proposed it, they said no, you built it yourself with public data and open tools on your own time. This is clean.

If NCBI DOES fund it: the code belongs to the government (or your employer). You cannot take that code and open source it. But you CAN build a separate, clean-room implementation on personal time using the same public data.

### Protections to follow

1. Build on personal machine, personal GitHub account, personal time (evenings/weekends)
2. Never use NCBI internal systems, VPN, or non-public data
3. Never copy code from any NCBI GitLab repository
4. Use only public NCBI data (FTP, public APIs) that anyone in the world can access
5. If the innovation project gets funded, keep the open source project architecturally distinct
6. Public GitHub repo from day one, public commits, clearly timestamped outside work hours
7. Check employment agreement for IP assignment clauses (contractor IP terms vary)

### Recommended

Spend $200 on a 30-minute consultation with an IP attorney who handles government contractor issues. That's cheaper than any legal problem. Do this before the first commit.

---

## Patent vs open source

### Should you patent this?

No. Here's why.

**What's patentable in theory:** the multi-agent architecture (8 agents with specific roles), the hybrid graph + on-demand API traversal pattern, the MCP tool definitions for biomedical knowledge. These are novel system designs.

**Why patenting doesn't make sense for you:**

| Reason | Details |
|---|---|
| Cost | A US patent costs $10K-15K (filing + attorney + prosecution). International patents: $50K+. For a personal project, this is prohibitive. |
| Time | Patents take 2-4 years to grant. The AI landscape will be unrecognizable by then. Anything you patent today will be obsolete before it's granted. |
| Enforcement | A patent is only useful if you can afford to enforce it. Patent litigation starts at $500K. Against whom would you enforce it? NCBI? Google? |
| Conflicts with open source | A patent on the architecture contradicts Apache 2.0 open source. Apache 2.0 includes an explicit patent grant to all users. You'd be granting the patent rights away to everyone who uses the repo. |
| Your goal is impact, not rent-seeking | You want this to be used, forked, adopted, cited. Patents restrict use. Open source maximizes it. |

**What protects you without a patent:**

| Protection | How it works |
|---|---|
| Apache 2.0 license | Requires attribution. Anyone who uses your code must credit you. Your name stays attached to the project permanently. |
| Git history | Every commit is timestamped and signed. You can prove you built it and when. Prior art is established automatically. |
| Publication | A published paper (Bioinformatics, NAR) is prior art that prevents anyone ELSE from patenting the same approach. Publishing is a defensive move. |
| First-mover brand | "The person who built open-source agentic search for NCBI" is a reputation asset no patent can buy. |
| Community | Contributors, stars, forks, citations. These create a network effect that compounds over time. |

### The right strategy

1. Open source under Apache 2.0 (requires attribution, includes patent grant)
2. Publish a paper (establishes prior art, prevents others from patenting your approach)
3. Build in public (GitHub commits prove authorship and timeline)
4. Let the project's reputation be the asset, not a legal monopoly

This is the same strategy used by every successful open source project in bioinformatics: Biopython, Nextflow, nf-core, Snakemake, Cytoscape. None are patented. All are career-defining for their creators.

### One-sentence decision

You want to build great things and open source everything. A patent is a wall around an idea. Open source is a door. Build the door.

---

---

## Publication and conference plan

The pipeline: build it -> paper -> poster -> talk. Each one feeds the next.

The paper gets you into the conference. The poster gets you conversations with people who care about the same problem. Those conversations lead to collaborators, job offers, and adoption.

### Paper targets

| Journal | Format | Why | Deadline |
|---|---|---|---|
| Bioinformatics | Application note (2-4 pages) | Short format, fast review. "Software/tools" category. | Rolling submissions |
| NAR Database Issue | Database resource article | Annual special issue for database tools. High visibility in the NCBI/bioinformatics community. | Usually June submission deadline |
| JAMIA | Research article | If the clinical angle is strong (ClinVar + MedGen + variant-disease queries). | Rolling submissions |

### Conference targets

| Conference | When | Format | Why |
|---|---|---|---|
| ISMB (Intelligent Systems for Molecular Biology) | July annually | Poster + talk track | The main bioinformatics conference. "Bio-Ontologies" and "Knowledge Graphs" are recurring tracks. |
| Bio-IT World | May annually | Poster + presentation | Industry + government audience. NCBI people attend. |
| AMIA (American Medical Informatics Association) | November annually | Poster + podium | Clinical informatics focus. ClinVar/MedGen angle plays well here. |
| BOSC (Bioinformatics Open Source Conference) | Co-located with ISMB | Lightning talks + poster | Literally built for open source bioinformatics tools. Perfect fit. |
| KGC (Knowledge Graph Conference) | May annually | Talk + poster | KG-specific audience. BioLink, Monarch, Translator people attend. |

A poster is cheap ($50-100 for printing) and reusable across multiple conferences.

### Paper content (what the build produces)

By the end of month 2, you have publishable evidence:

| Section | Content |
|---|---|
| Introduction | The problem (30+ NCBI databases, researcher is the integration layer) |
| Methods | 3-system architecture, 8 agents, BioLink compliance, hybrid graph + on-demand design |
| Results | Graph statistics (150M+ nodes, 6 databases), CQ test suite results (20+ passing), evaluation metrics (accuracy, completeness, grounding), latency benchmarks (< 10s end-to-end) |
| Discussion | Comparison to existing tools (Monarch, RTX-KG2, BioThings Explorer), MCP as the agent-to-agent future, limitations |
| Availability | Open source repo (GitHub), Apache 2.0, Docker one-command deploy, pip installable CLI |

---

## 6-month exit plan

| Month | Build | Publish | Network |
|---|---|---|---|
| 1 | Ship alpha (3 databases, 5 agents, 3 channels) | Start paper draft | First LinkedIn post about the project |
| 2 | Full build (6 databases, 8 agents, 5 channels) | Finish paper, submit to Bioinformatics or NAR | Share on bioinformatics Twitter/Mastodon, Reddit r/bioinformatics |
| 3 | Post-launch iteration (add OMIM, PubChem, improve based on feedback) | Paper under review. Submit conference abstracts (BOSC, KGC, AMIA). | Start conversations with target companies |
| 4 | Community building (accept PRs, write tutorials, example notebooks) | Present poster at BOSC or KGC | Interview cycle begins. GitHub repo + paper + talk are the portfolio. |
| 5 | Maintenance + community growth | Paper accepted (ideally). Poster at second conference. | Active interviews. The project sells itself. |
| 6 | Hand off or continue maintaining | First citations from researchers who used the tool | Leave |

### What makes you uniquely hireable

Your portfolio by month 6:

| Asset | What it proves |
|---|---|
| Open source NCBI agentic search (GitHub) | Can architect and ship a complex system end-to-end, solo |
| Paper in Bioinformatics or NAR | Can communicate technical work to a scientific audience |
| Conference poster/talk | Has presence in the community |
| NCBI domain expertise (3+ years) | Understands biomedical data at a depth most PMs never will |
| $1.3-1.8M equivalent system for $500 | Understands AI leverage, can do more with less |
| 5 access channels including MCP | Understands the agent-to-agent future before most companies do |

### Why this profile is rare

Biomedical domain expertise + knowledge graph architecture + AI agent systems + product management. Most candidates have one, maybe two of these. You have all four. Here's where that combination is most valuable.

### Tier 1: your skills are a direct match

| Company | Why you fit | Role to target | What they'd pay |
|---|---|---|---|
| Tempus | Genomics + AI platform. They integrate clinical and molecular data (exactly what you're building). Use knowledge graphs internally. | Senior PM, AI/Data Products or Technical PM, Genomics Platform | $180-250K total comp |
| Color Health | Population genomics, variant interpretation, ClinVar-heavy. Your NCBI domain knowledge is directly applicable. | PM, Genomics Platform or PM, AI Features | $170-230K |
| Invitae / Natera | Genetic testing companies that consume ClinVar, Gene, MedGen daily. Your system is literally their workflow automated. | Senior PM, Data/AI or PM, Variant Interpretation Platform | $170-240K |
| Flatiron Health (Roche) | Oncology data platform. KG approach to clinical + molecular data integration. NYC-based. | Senior PM, Data Products | $180-250K |
| Recursion Pharmaceuticals | AI drug discovery. Knowledge graphs linking genes, compounds, diseases, pathways. Your PubChem + Gene + MedGen work maps directly. | PM, Knowledge Platform or PM, Data Infrastructure | $180-260K |

### Tier 2: AI-native companies that need biomedical depth

| Company | Why you fit | Role to target | What they'd pay |
|---|---|---|---|
| Anthropic | You've built production systems with Claude Code, understand multi-agent architecture deeply, and have a domain specialization (bio/health) they're expanding into. Not a joke, actually plausible. | PM, Applied AI or PM, Claude for Enterprise (health vertical) | $250-400K total comp |
| Elicit | AI research assistant. They do exactly what your agentic search does but for general research. Your biomedical specialization + agent architecture experience is differentiated. | PM, Search/Retrieval or PM, Domain Expansion | $180-280K |
| Consensus | AI search engine for scientific research. PubMed is their primary data source. You literally built the next-gen version of their product. | Senior PM or founding PM for a vertical | $170-250K |
| Semantic Scholar (Allen AI) | Non-profit AI research lab. Biomedical literature search. Your PubMed + PubTator3 + knowledge graph work is their exact problem space. | PM, Search or Research Engineer (PM-adjacent) | $160-220K |

### Tier 3: big tech health AI divisions

| Company | Why you fit | Role to target | What they'd pay |
|---|---|---|---|
| Google DeepMind Health | AlphaFold, Med-PaLM, health AI research. Your KG + agent architecture experience applies to their health product buildout. | PM, Health AI Products | $280-400K total comp |
| Microsoft Health AI | Nuance (clinical), health data platform, Copilot for healthcare. | Senior PM, Health AI | $250-350K |
| Amazon (One Medical / Health AI) | Building health data infrastructure. Your data engineering + KG architecture skills apply. | Senior PM, Health Data Platform | $250-380K |
| Apple Health | Health records, clinical data, on-device health AI. Secretive but hiring aggressively. | PM, Health Platform | $270-380K |

### The Anthropic angle (honest take)

Not a joke. Your profile actually fits. Anthropic is expanding into enterprise verticals (health, legal, finance). They need people who understand both the AI capabilities AND the domain. Most Anthropic PMs understand AI but not biomedical data. Most biomedical PMs understand the domain but not multi-agent systems. You understand both.

The open source project is your application. If you build ncbi-agentic-search using Claude Code, publish it, and it gets adoption in the bioinformatics community, that's a stronger signal than any resume.

---

*Created: April 2, 2026. Personal build plan for NCBI agentic search as an open source portfolio project.*
