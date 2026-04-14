# Three-layer data architecture

How data flows from NCBI sources to user answers. Three layers, each with a different purpose, latency, and ownership.

## Table of contents

- [Layer 1: knowledge graph](#layer-1-knowledge-graph-this-repo-fully-ingested)
- [Why PostgreSQL + Apache AGE](#why-postgresql--apache-age)
- [Layer 2: on-demand API](#layer-2-on-demand-api-system-3-repo-not-ingested)
- [Layer 3: research APIs](#layer-3-research-apis-system-3-repo-answer-enrichment)
- [How they connect](#how-they-connect)
- [Estimated monthly cost](#estimated-monthly-cost-for-the-full-system)
- [What this repo does and does not do](#what-this-repo-does-and-does-not-do)
- [Handoff point](#handoff-point)
- [Will Layer 2/3 API calls work?](#will-layer-23-api-calls-work)
- [Why these 6 databases for Layer 1?](#why-these-6-databases-for-layer-1)

---

## Layer 1: knowledge graph (this repo, fully ingested)

6 NCBI databases downloaded from FTP, parsed, mapped to BioLink, and loaded into PostgreSQL + Apache AGE. The search agent queries these via openCypher in milliseconds.

| Database | Records | BioLink category | Why Layer 1 |
|----------|---------|-----------------|-------------|
| Gene | 67.5M (all organisms) | biolink:Gene | Biology hub. 33 outbound link types. Connects to everything. |
| PubMed | 40M articles | biolink:Article | Universal connector. 47 link types. Literature is the glue. |
| ClinVar | 4.5M variants | biolink:SequenceVariant | Variant-disease associations. |
| MedGen | 233K concepts | biolink:Disease | Disease concept hub. Maps MONDO, OMIM, MeSH, SNOMED, HPO. |
| Taxonomy | 2.9M organisms | biolink:OrganismTaxon | Scopes results to human (or any organism). |
| SNP | 1.2B variants | biolink:SequenceVariant | Full dbSNP. Population frequencies, functional annotations. |

Built by: System 1 (ETL pipelines) + System 2 (AGE loader) in this repo.
Latency: <10ms per Cypher query.
Total: ~1.4B nodes, ~1.5B edges.

### Why PostgreSQL + Apache AGE

PostgreSQL + AGE stores data on disk at `/export` (local LVM volume). We chose it over Neo4j because:

- Neo4j needs all data in RAM. At 1.4B nodes, that requires 256GB+ RAM ($500+/month for a cloud instance). We have 8-16GB.
- AGE is disk-based. It handles 1.4B nodes on 8-16GB RAM because it uses PostgreSQL's disk-backed storage engine.
- AGE supports openCypher, so the query language is the same as Neo4j.
- Cost: $0 (PostgreSQL is already installed locally).

---

## Layer 2: on-demand API (System 3 repo, not ingested)

Reached at query time via ELink/EFetch. The search agent follows connections from Layer 1 nodes into these databases via live NCBI API calls. Nothing is pre-downloaded.

Examples: PMC (12M full-text articles), Protein (1.57B records), Nucleotide (712M), Structure, OMIM, GTR, GEO, dbVar, Assembly.

Excluded from all layers: SRA (raw sequencing reads), dbGaP (controlled-access, requires IRB), PubChem (community-submitted, varying curation).

Latency: 200-500ms per API call. Budget: max 20 calls per user query. Cached in Redis.

Built by: System 3 (search agent) in a separate repo.

---

## Layer 3: research APIs (System 3 repo, answer enrichment)

Not databases. Specialized APIs that augment answers with deeper evidence. Called after initial results are found from Layer 1 and Layer 2.

| API | What it adds | When called |
|-----|-------------|-------------|
| PubTator3 | Entity annotations on publications (genes, diseases, chemicals, mutations, species) | After PubMed results found |
| LitVar2 | Variant-specific literature links | After variants identified |
| LitSense | Sentence-level evidence from full text | After key publications identified |
| ClinicalTrials.gov | Active clinical trials for diseases/genes | After diseases identified |

Latency: 500ms-2s per call. Called selectively, not on every query.

Built by: System 3 (search agent) in a separate repo.

---

## How they connect

System 3 queries all three layers independently at query time and combines the results into one cited answer. Layer 1 is a database query against our hosted graph. Layers 2 and 3 are live API calls to external NCBI services. All three happen in parallel, orchestrated by the search agent.

```
User query
    |
    v
System 3: search agent (separate repo)
    |
    +-- Layer 1: Cypher query against AGE graph ------> Hetzner VPS (~$25-30/month)
    |   (Gene, ClinVar, MedGen, PubMed, Taxonomy, SNP)
    |   Source: PostgreSQL + AGE database built by this repo
    |   Latency: <10ms
    |   Cost: hosting only, data is pre-loaded
    |
    +-- Layer 2: ELink/EFetch to NCBI APIs ------------> NCBI live servers (free)
    |   (Protein, PMC, Structure, OMIM, GTR, etc.)
    |   Source: NCBI public APIs, called at query time
    |   Latency: 200-500ms per call
    |   Cost: $0 (free with API key, 10 req/sec)
    |
    +-- Layer 3: enrichment APIs -----------------------> PubTator3, LitVar2, etc. (free)
    |   Source: NCBI and NIH enrichment services
    |   Latency: 500ms-2s per call
    |   Cost: $0 (free public APIs)
    |
    v
Cited multi-database answer
```

System 3 fetches data from Layer 1 (our database) and separately from Layers 2 and 3 (external APIs). These are independent data sources combined at answer time. Layer 1 provides the pre-built graph connections. Layers 2 and 3 add on-demand detail that would be too large or too dynamic to pre-ingest.

### Estimated monthly cost for the full system

| Component | What it does | Monthly cost |
|-----------|-------------|-------------|
| Layer 1: AGE database | Hosts the 1.4B node knowledge graph | ~$25-30 (Hetzner VPS) |
| Layers 2 + 3: NCBI APIs | Live queries to NCBI servers | $0 (free) |
| System 3: search agent + API | Orchestrates queries, serves results | ~$10-20 (separate VPS or Railway) |
| System 3: UI | Web interface for users | ~$0-10 (Vercel/Netlify) |
| Total | | ~$35-60/month |

---

## What this repo does and does not do

Does:
- Download and ingest 6 Layer 1 databases (System 1: ETL pipelines)
- Load them into PostgreSQL + AGE locally (System 2: knowledge graph)
- Validate the graph with Cypher queries
- Deploy the graph to a cloud VPS for production use

Does not:
- Call Layer 2 or Layer 3 APIs (that's System 3, query-time)
- Build the search agent (that's System 3, separate repo)
- Serve a UI or API endpoint (that's System 3)

---

## Handoff point

Phase 4.1 (Cypher query validation) in the bossman execution plan is the handoff. Once Gene -> ClinVar -> MedGen traversals return correct results from the AGE graph, System 3 can connect and start building the agent layer on top.

System 3 needs:
- PostgreSQL + AGE running with the `ncbi_kg` database loaded
- The BioLink schema (schema/biolink_ncbi.yaml) to know what node types and predicates exist
- The CURIE prefix conventions (NCBIGene:, MONDO:, PMID:, etc.) to construct queries

System 3 does not need:
- The KGX files (those are intermediate, deleted after AGE load)
- The ETL pipeline code (System 3 talks to the database, not the pipelines)
- This repo checked out (just the running database)

---

## Will Layer 2/3 API calls work?

Yes, with constraints.

### Why it works

- NCBI E-utilities (ELink, EFetch, ESummary) are stable public APIs that have been running for 20+ years. They are the official programmatic interface to all 39 databases.
- The latency budget (200-500ms per call, max 20 calls per query) is realistic. NCBI responses are typically 100-300ms for EFetch on small record sets.
- Layer 2 databases (Protein at 1.57B records, PMC at 12M, Structure at 251K) are too large or too dynamic to pre-ingest. Protein alone is bigger than the entire Layer 1 graph. Pre-ingesting it would require terabytes of storage and weekly re-downloads.

### Where the risk is

- Rate limiting: 10 req/sec with an API key. If System 3 has multiple concurrent users, cache misses under load could bottleneck.
- NCBI occasionally throttles or blocks IPs that exceed limits, even with a key. The agent needs proper backoff.
- Some EFetch responses are large (a full protein record, a PMC full-text XML). Parsing these at query time adds latency.
- NCBI has occasional maintenance windows where APIs return errors for hours.

None of these are dealbreakers. They are engineering problems with known solutions (caching, retry logic, timeouts, fallback messages).

---

## Why these 6 databases for Layer 1?

The selection criteria were density of connections and role as a hub in the cross-database link graph. Three criteria drove the split.

### Criterion 1: hub connectivity

The cross-database link map (Part 6 of `NCBI_databases_and_APIs_reference.md`) shows which databases are universal connectors, appearing as link targets from almost every other database:

- PubMed: 47 link types to 25+ databases
- Gene: 33 link types
- Taxonomy: organism classification links from all sequence databases

These three are the backbone. ClinVar, MedGen, and SNP complete the clinical genetics triangle. Together they form the traversal paths that matter most: disease -> gene -> variant -> literature.

### Criterion 2: what can't be served by API at query time

The 6 Layer 1 databases need to be pre-ingested because:

- Graph traversals require joins across multiple entity types. You cannot do "find all genes linked to this disease, then find all variants of those genes, then find literature for those variants" in a sequence of API calls without unacceptable latency (potentially dozens of round-trips).
- Gene (67.5M records), SNP (1.2B records), PubMed (40M records) are too large to search via API for graph-style queries. ESearch returns ranked results, not graph neighborhoods.

### Criterion 3: what's too large or wrong for Layer 1

The databases left for Layer 2:

| Database | Records | Why Layer 2 |
|----------|---------|-------------|
| Protein | 1.57B | Sequence database. Enormous, but most queries only need a handful of records. On-demand EFetch. |
| Nucleotide | 712M | Same pattern as Protein. |
| PMC | 12M | Full text only needed after you know which articles matter. Too large to store locally. |
| OMIM | 29K | Small but specialized. Only needed for specific query types. |
| GTR | 64K | Genetic testing registry. Niche queries only. |
| Structure | 251K | 3D structures. Needed only when following protein links. |
| GEO | 8.7M | Expression data. Specialized research queries. |

Excluded entirely: SRA (raw sequencing reads), dbGaP (controlled-access, requires IRB), PubChem (community-submitted, varying curation).

### The key insight

Layer 1 holds the databases that form the graph skeleton. The connections between genes, diseases, variants, organisms, and literature are what make a knowledge graph useful. Layer 2 databases are leaf nodes: you reach them by following a link from a Layer 1 entity, grab the specific record you need, and return. That pattern works fine with an API call.
