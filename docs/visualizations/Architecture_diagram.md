# Architecture diagram: NCBI knowledge graph V1

System architecture for the V1 knowledge graph: 5 NCBI ETL pipelines feed a streaming merger that writes a single KGX dataset, the loader pushes that dataset into PostgreSQL 15.17 + Apache AGE 1.5.0 on a Hetzner CPX42 VPS, and System 3 (a separate repo) connects as a Cypher client. Live counts: 115,406,761 nodes, 693,295,991 edges, 11 vertex labels, 14 edge labels.

## Table of contents

1. [End-to-end system overview](#1-end-to-end-system-overview)
2. [System 1: data pipelines (5 ETLs)](#2-system-1-data-pipelines-5-etls)
3. [Streaming merge into a single KGX](#3-streaming-merge-into-a-single-kgx)
4. [System 2: AGE loader on the Hetzner CPX42](#4-system-2-age-loader-on-the-hetzner-cpx42)
5. [Query-time data flow (System 3 as client)](#5-query-time-data-flow-system-3-as-client)
6. [Deployment topology](#6-deployment-topology)
7. [Live statistics](#7-live-statistics)

## 1. End-to-end system overview

```mermaid
flowchart LR
    NCBI["NCBI FTP + Entrez<br/>5 databases"]
    S1["System 1: ETL pipelines<br/>parse, map, validate, KGX"]
    Merge["Streaming merger<br/>dedup + stub injection"]
    KGX["Merged KGX<br/>nodes.tsv + edges.tsv<br/>~144 GB"]
    Loader["System 2: age-load<br/>node + edge loaders"]
    AGE["PostgreSQL 15 + AGE 1.5<br/>graph: ncbi_kg<br/>Hetzner CPX42"]
    S3["System 3: search agent<br/>separate repo"]

    NCBI --> S1 --> Merge --> KGX --> Loader --> AGE
    S3 -->|Cypher over psycopg2| AGE
```

The repo at hand owns everything from NCBI to AGE. System 3 is an external Cypher client and is not built here. See [docs/architecture/Three_layer_data_architecture.md](../architecture/Three_layer_data_architecture.md) for the full layer model.

## 2. System 1: data pipelines (5 ETLs)

Each pipeline follows the same 5-step pattern: download, parse, map to BioLink, validate against LinkML, export to KGX. Code lives under [system-01-data-pipelines/](../../system-01-data-pipelines/).

```mermaid
flowchart TD
    subgraph ETLs["5 ETL pipelines"]
        Gene["gene/<br/>67.5M nodes<br/>NCBIGene + orthologs"]
        ClinVar["clinvar/<br/>4.4M variants<br/>ClinVar:"]
        MedGen["medgen/<br/>198K diseases<br/>MedGen:"]
        PubMed["pubmed/<br/>40.4M articles + MeSH<br/>PMID: + MeSH:"]
        Tax["taxonomy/<br/>2.7M taxa<br/>NCBITaxon:"]
    end

    subgraph Steps["Per-pipeline 5-step pattern"]
        D["1. Download<br/>FTP, idempotent cache"]
        P["2. Parse<br/>format-specific parser"]
        M["3. Map<br/>BioLink categories + predicates"]
        V["4. Validate<br/>LinkML schema"]
        E["5. Export<br/>KGX TSV with provenance"]
    end

    Gene --> D
    ClinVar --> D
    MedGen --> D
    PubMed --> D
    Tax --> D
    D --> P --> M --> V --> E
    E --> Out["data/kgx/<db>/<br/>nodes.tsv + edges.tsv"]
```

Shared utilities (downloader, BioLink mapper, LinkML validator, KGX exporter, streaming merger) live in [system-01-data-pipelines/shared/](../../system-01-data-pipelines/shared/). Provenance fields (`source`, `source_url`) are required on every node and edge; this is enforced at the validator boundary.

## 3. Streaming merge into a single KGX

The merger combines 5 per-database KGX directories into one merged KGX. It uses two streaming passes to keep RAM bounded at O(unique node CURIEs) instead of O(total rows). The full algorithm lives in [system-01-data-pipelines/shared/merger.py](../../system-01-data-pipelines/shared/merger.py); see [docs/architecture/Merge_logic_explained.md](../architecture/Merge_logic_explained.md) for the first-principles walkthrough.

```mermaid
flowchart TD
    subgraph In["Input: 5 KGX folders"]
        N1["gene/nodes.tsv"]
        N2["clinvar/nodes.tsv"]
        N3["medgen/nodes.tsv"]
        N4["pubmed/nodes.tsv"]
        N5["taxonomy/nodes.tsv"]
        E1["+ matching edges.tsv files"]
    end

    P1["Pass 1: stream nodes<br/>dedup by CURIE in a set<br/>~116M unique IDs in RAM"]
    P2["Pass 2: stream edges<br/>track dangling endpoints"]
    Stub["Stub injection<br/>~81K NamedThing nodes<br/>category from CURIE prefix"]

    Out["data/kgx/merged/<br/>nodes.tsv + edges.tsv<br/>~144 GB"]

    N1 --> P1
    N2 --> P1
    N3 --> P1
    N4 --> P1
    N5 --> P1
    E1 --> P2
    P1 --> P2 --> Stub --> Out
```

Prefix-to-category map (from [merger.py](../../system-01-data-pipelines/shared/merger.py) lines 39 to 50) drives stub-category inference for any dangling endpoint:

| CURIE prefix | BioLink category |
| --- | --- |
| NCBIGene: | biolink:Gene |
| PMID: | biolink:Article |
| MeSH: | biolink:OntologyClass |
| GO: | biolink:BiologicalProcess |
| MedGen:, MONDO:, UMLS: | biolink:Disease |
| NCBITaxon: | biolink:OrganismTaxon |
| HP: | biolink:PhenotypicFeature |
| ClinVar: | biolink:SequenceVariant |
| (other) | biolink:NamedThing |

## 4. System 2: AGE loader on the Hetzner CPX42

The loader takes the merged KGX and pushes it into a single AGE graph called `ncbi_kg`. Code lives under [system-02-knowledge-graph/loader/](../../system-02-knowledge-graph/loader/). See [docs/architecture/AGE_loader_explained.md](../architecture/AGE_loader_explained.md) for the deep-dive.

```mermaid
flowchart TD
    KGX["Merged KGX<br/>on VPS at /root/data/kgx/merged/"]

    subgraph Loader["age-load pipeline (system-02-knowledge-graph/loader/)"]
        S1["1. connect_age<br/>connection.py"]
        S2["2. create_graph<br/>schema.py"]
        S3["3. create_vertex_labels<br/>11 labels"]
        S4["4. create_edge_labels<br/>14 predicates"]
        S5["5. node_loader<br/>COPY nodes by label"]
        S6["6. curie_to_id dict<br/>~116M entries in RAM"]
        S7["7. edge_loader<br/>COPY edges with resolved IDs"]
        S8["8. index_builder<br/>functional B-tree + GIN + edge B-trees + ANALYZE"]
    end

    PG["PostgreSQL 15.17<br/>schema: ncbi_kg<br/>11 vertex tables<br/>14 edge tables"]

    KGX --> S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7 --> S8 --> PG
```

The `curie_to_id` dict is the memory hot-spot: it maps every CURIE to its AGE-assigned graphid so edge endpoints can be resolved at insert time. It peaks around 12-14 GB on this graph, which is why the box has 16 GB swap (see [docs/learnings.md](../learnings.md) Problem 9).

Step 8 covers three index passes (added during Gate 3 close-out): functional B-tree on `agtype_to_text(properties -> '"id"')`, GIN on `properties` for high-traffic vertex labels, and B-tree on `start_id`/`end_id` for every edge label. ANALYZE then refreshes planner statistics. See [docs/Knowledge_graph_on_server_reference.md](../Knowledge_graph_on_server_reference.md) Section I and Problem 12 in [docs/learnings.md](../learnings.md).

## 5. Query-time data flow (System 3 as client)

System 3 lives in a separate repo and connects to the AGE graph as a read-only Cypher client. Nothing in this repo writes to the graph after the bulk load.

```mermaid
sequenceDiagram
    participant U as User
    participant S3 as System 3 (other repo)
    participant PG as PostgreSQL + AGE
    participant Tables as ncbi_kg schema

    U->>S3: NL query
    S3->>S3: NL to Cypher
    S3->>PG: SELECT cypher('ncbi_kg', $$ MATCH ... $$)
    PG->>Tables: typed edge label scan + GIN lookup
    Tables-->>PG: result rows (agtype)
    PG-->>S3: rows
    S3->>S3: synthesise answer
    S3-->>U: response with citations
```

Performance bands and the three rules of fast Cypher (always specify edge label, match by `id` with the right CURIE prefix, keep regex narrow) live in [docs/Knowledge_graph_on_server_reference.md](../Knowledge_graph_on_server_reference.md) Section H.

## 6. Deployment topology

```mermaid
flowchart LR
    subgraph Dev["Local dev (Windows laptop)"]
        Repo["agentic-search-data-engineering"]
        LocalKGX["data/kgx/merged/<br/>144 GB"]
    end

    subgraph Hetzner["Hetzner Cloud, Nuremberg"]
        VPS["CPX42 VPS<br/>8 vCPU, 16 GB RAM<br/>320 GB NVMe<br/>Ubuntu 22.04"]
        SW["PostgreSQL 15.17<br/>Apache AGE 1.5.0<br/>16 GB swap"]
        Snap["Snapshot ~28 GB<br/>3.5x compression"]
    end

    subgraph S3Repo["System 3 repo"]
        Client["FastAPI + LangGraph + UI<br/>built elsewhere"]
    end

    Repo -->|build pipelines| LocalKGX
    LocalKGX -->|rsync over SSH<br/>~120 sessions, partial+inplace| VPS
    VPS --> SW
    SW -.->|nightly via Hetzner console| Snap
    Client -->|Cypher via psycopg2| SW
```

VPS provisioning detail and the rsync-on-Windows playbook live in [docs/context/setup/setup-04_hetzner_vps.md](../context/setup/setup-04_hetzner_vps.md) and [docs/context/setup/setup-05_rsync_windows.md](../context/setup/setup-05_rsync_windows.md). All-in cost is roughly $28.50/month on CPX42, $22/month on a future CPX32 downsize. See Section P of the server reference.

## 7. Live statistics

Counts below are pulled from [tests/cypher/gate3_results_2026-04-22.txt](../../tests/cypher/gate3_results_2026-04-22.txt), Q6 and Q7 of the smoke suite.

| Metric | Count |
| --- | --- |
| Vertex labels | 11 |
| Edge labels | 14 |
| Total nodes | 115,406,761 |
| Total edges | 693,295,991 |
| Source databases | 5 (Gene, ClinVar, MedGen, PubMed, Taxonomy) |
| BioLink validation errors | 0 (build-time + at-merge) |

Top vertex tables by row count:

| Vertex label | Rows |
| --- | --- |
| Gene | 67,536,325 |
| Article | 40,387,670 |
| SequenceVariant | 4,467,468 |
| OrganismTaxon | 2,736,611 |
| Disease | 200,845 |
| OntologyClass | 30,790 |
| BiologicalProcess | 16,901 |
| NamedThing | 10,580 |
| PhenotypicFeature | 9,881 |
| MolecularActivity | 6,978 |
| CellularComponent | 2,712 |

Top edge tables by row count:

| Edge label | Rows |
| --- | --- |
| has_mesh_annotation | 349,158,787 |
| mentioned_in | 124,032,423 |
| in_taxon | 67,536,046 |
| actively_involved_in | 44,832,765 |
| participates_in | 40,767,507 |
| located_in | 31,889,215 |
| orthologous_to | 17,421,811 |
| has_phenotype | 6,076,764 |
| is_sequence_variant_of | 4,407,168 |
| cited_in | 3,924,820 |
| subclass_of | 2,832,676 |
| close_match | 410,000 |
| gene_associated_with_condition | 7,644 |
| exact_match | 0 |

References:

- [Schema_visualization.md](Schema_visualization.md): vertex labels, edge predicates, sample CURIEs
- [docs/Knowledge_graph_on_server_reference.md](../Knowledge_graph_on_server_reference.md): live server reference
- [docs/architecture/Technical_reference_data_engineering.md](../architecture/Technical_reference_data_engineering.md): full V1 walkthrough
- [docs/architecture/AGE_loader_explained.md](../architecture/AGE_loader_explained.md): loader design
- [docs/architecture/Merge_logic_explained.md](../architecture/Merge_logic_explained.md): merger design

Last updated: 2026-04-22
