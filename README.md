# NCBI data engineering

ETL pipelines and knowledge graph for 6 NCBI databases.

Downloads bulk data from NCBI FTP, parses it, maps it to the BioLink model, validates with LinkML, and loads it into PostgreSQL + Apache AGE. The result is a BioLink-compliant knowledge graph queryable via openCypher.

6 databases. ~1.4B nodes. ~1.5B edges. Every node and edge traced back to its NCBI source record.

---

## Status

Phase 2 code complete: PubMed ETL, Taxonomy ETL, and 5-database merge pipeline all merged. Gate 2 next: run all three on real data and validate KGX output.

| System | Status |
|--------|--------|
| System 1: data pipelines | Phase 2 code done (PubMed + Taxonomy + 5-db merge). Gate 2 next (real data run). |
| System 2: knowledge graph | Not started |
| System 3: search agent | Not started |

---

## Architecture

This repo builds Layer 1 of a three-layer data architecture:

| Layer | What | Where | Latency |
|-------|------|-------|---------|
| Layer 1: knowledge graph | 6 NCBI databases fully ingested into PostgreSQL + AGE | This repo (System 1 + 2) | <10ms per Cypher query |
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
| SNP (full dbSNP) | 1.2B | `biolink:SequenceVariant` | ftp.ncbi.nlm.nih.gov/snp/ |

---

## Documentation

| Doc | What it covers |
|-----|---------------|
| [Execution plan](docs/bossman_execution_plan.md) | Phase-by-phase build plan with status, gates, validation checklist, disk budget |
| [Three-layer architecture](docs/architecture/Three_layer_data_architecture.md) | Layer 1 (graph), Layer 2 (on-demand API), Layer 3 (enrichment), cost breakdown |
| [System 1 data engineering plan](docs/System_1_data_engineering_plan.md) | Detailed design for all 6 ETL pipelines |
| [Data inventory](docs/data_inventory.md) | What data was downloaded, FTP URLs, file sizes, row counts, validation results |
| [Learnings](docs/learnings.md) | Problems encountered and solutions, updated after every pipeline run |
| [BioLink schema](schema/biolink_ncbi.yaml) | LinkML schema with 10 node types, 14 predicates |
| [Decisions](DECISIONS.md) | Architecture and implementation decisions with rationale |
| [Local setup](docs/context/setup/setup-03_windows_laptop.md) | One-time migration guide for Windows laptop (repo clone, symlinks, venv, data rsync, verification) |

---

## License

Apache 2.0. See [LICENSE](LICENSE).
