# Three-layer data architecture

How data flows from NCBI sources to user answers. Three layers, each with a different purpose, latency, and ownership.

---

## Layer 1: knowledge graph (this repo, fully ingested)

6 NCBI databases downloaded from FTP, parsed, mapped to BioLink, and loaded into PostgreSQL + Apache AGE. The search agent queries these via openCypher in milliseconds.

| Database | Records | BioLink category | Why Layer 1 |
|----------|---------|-----------------|-------------|
| Gene | 94M (all organisms) | biolink:Gene | Biology hub. 33 outbound link types. Connects to everything. |
| PubMed | 40M articles | biolink:Article | Universal connector. 47 link types. Literature is the glue. |
| ClinVar | 4.5M variants | biolink:SequenceVariant | Variant-disease associations. |
| MedGen | 233K concepts | biolink:Disease | Disease concept hub. Maps MONDO, OMIM, MeSH, SNOMED, HPO. |
| Taxonomy | 2.9M organisms | biolink:OrganismTaxon | Scopes results to human (or any organism). |
| SNP | 1.2B variants | biolink:SequenceVariant | Full dbSNP. Population frequencies, functional annotations. |

Built by: System 1 (ETL pipelines) + System 2 (AGE loader) in this repo.
Latency: <10ms per Cypher query.
Total: ~1.4B nodes, ~1.5B edges.

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

```
User query
    |
    v
System 3: search agent (separate repo)
    |
    +-- Layer 1: Cypher query against AGE graph ------> This repo (System 1 + 2)
    |   (Gene, ClinVar, MedGen, PubMed, Taxonomy, SNP)
    |   Latency: <10ms
    |
    +-- Layer 2: ELink/EFetch to NCBI APIs ------------> NCBI live servers
    |   (Protein, PMC, Structure, OMIM, GTR, etc.)
    |   Latency: 200-500ms per call
    |
    +-- Layer 3: enrichment APIs -----------------------> PubTator3, LitVar2, etc.
    |   Latency: 500ms-2s per call
    |
    v
Cited multi-database answer
```

---

## What this repo does and does not do

Does:
- Download and ingest 6 Layer 1 databases (System 1: ETL pipelines)
- Load them into PostgreSQL + AGE (System 2: knowledge graph)
- Make them queryable via openCypher

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
