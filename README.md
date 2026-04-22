# NCBI data engineering

ETL pipelines and knowledge graph for 5 NCBI databases.

Downloads bulk data from NCBI FTP, parses it, maps it to the BioLink model, validates with LinkML, and loads it into PostgreSQL + Apache AGE. The result is a BioLink-compliant knowledge graph queryable via openCypher.

5 databases. ~115M nodes. ~693M edges. Every node and edge traced back to its NCBI source record.

---

## Status

V1 COMPLETE (2026-04-22). Phase 4.0 + Gate 3 PASSED. The 5-database AGE graph is live on Hetzner CPX42 (46.225.128.133), holding 115,406,761 nodes + 693,295,991 edges. All 7 Cypher smoke queries return correct results in milliseconds to seconds. See `docs/Knowledge_graph_on_server_reference.md` for the live-graph A-Z reference.

| System | Status |
|--------|--------|
| System 1: data pipelines | V1 complete (2026-04-22). All 5 ETL pipelines built, validated against real NCBI data, and merged into a single BioLink-compliant KGX. |
| System 2: knowledge graph | Live on cloud VPS. 115.4M nodes + 693.3M edges loaded into PostgreSQL 15 + Apache AGE 1.5.0. Queryable via openCypher. |
| System 3: search agent | Lives in a separate repository. Connects to this graph as a client. |

---

## Architecture

This repo builds Layer 1 of a three-layer data architecture:

| Layer | What | Where | Latency |
|-------|------|-------|---------|
| Layer 1: knowledge graph | 5 NCBI databases fully ingested into PostgreSQL + AGE | This repo (System 1 + 2) | <10ms per Cypher query |
| Layer 2: on-demand API | 30+ NCBI databases reached at query time via ELink/EFetch | Separate repo (System 3) | 200-500ms per call |
| Layer 3: enrichment APIs | PubTator3, LitVar2, LitSense, ClinicalTrials.gov | Separate repo (System 3) | 500ms-2s per call |

This repo handles Layer 1 only: download, parse, map, validate, load. Layers 2 and 3 are query-time concerns handled by the search agent in a separate repository.

```
System 1: data pipelines (this repo)
  NCBI FTP -> parse -> BioLink map -> LinkML validate -> KGX files (nodes.tsv + edges.tsv)

System 2: knowledge graph (this repo)
  KGX files -> normalize -> merge -> PostgreSQL + AGE -> queryable via openCypher
```

- See [docs/architecture/Three_layer_data_architecture.md](docs/architecture/Three_layer_data_architecture.md) for the full three-layer design.
- See [docs/System_1_data_engineering_plan.md](docs/System_1_data_engineering_plan.md) for the detailed build plan.
- See [docs/bossman_execution_plan.md](docs/bossman_execution_plan.md) for phase-by-phase execution status.

---

## Quick start

```bash
# Prerequisites
python 3.11+
postgresql 15 + apache age (for System 2)

# Setup
git clone <repo-url>
cd agentic-search-data-engineering
copy env.example .env  # or: cp env.example .env
pip install -r requirements.txt

# Run tests
pytest tests/

# Run Gene ETL
python system-01-data-pipelines/gene/pipeline.py
```

---

## Data sources (System 1)

| Database | Records | BioLink category | FTP source |
|----------|---------|-----------------|-----------|
| Gene | 67.5M | `biolink:Gene` | ftp.ncbi.nlm.nih.gov/gene/DATA/ |
| ClinVar | 4.4M | `biolink:SequenceVariant` | ftp.ncbi.nlm.nih.gov/pub/clinvar/ |
| MedGen | 198K | `biolink:Disease` | ftp.ncbi.nlm.nih.gov/pub/medgen/ |
| PubMed | 40M | `biolink:Article` | ftp.ncbi.nlm.nih.gov/pubmed/baseline/ |
| Taxonomy | 2.9M | `biolink:OrganismTaxon` | ftp.ncbi.nlm.nih.gov/pub/taxonomy/ |

---

## Documentation

| Doc | What it covers |
|-----|---------------|
| [Execution plan](docs/bossman_execution_plan.md) | Phase-by-phase build plan with status, gates, validation checklist, disk budget |
| [Three-layer architecture](docs/architecture/Three_layer_data_architecture.md) | Layer 1 (graph), Layer 2 (on-demand API), Layer 3 (enrichment), cost breakdown |
| [Merge logic explained](docs/architecture/Merge_logic_explained.md) | First-principles walkthrough of the 5-database streaming merge, dedup strategy, stub injection |
| [System 1 data engineering plan](docs/System_1_data_engineering_plan.md) | Detailed design for all 5 ETL pipelines |
| [Data inventory](docs/data_inventory.md) | What data was downloaded, FTP URLs, file sizes, row counts, validation results |
| [Learnings](docs/learnings.md) | Problems encountered and solutions, updated after every pipeline run |
| [BioLink schema](schema/biolink_ncbi.yaml) | LinkML schema with 10 node types, 14 predicates |
| [Decisions](DECISIONS.md) | Architecture and implementation decisions with rationale |
| [Local setup](docs/context/setup/setup-03_windows_laptop.md) | One-time migration guide for Windows laptop (repo clone, symlinks, venv, data rsync, verification) |

---

## License

Apache 2.0. See [LICENSE](LICENSE).
