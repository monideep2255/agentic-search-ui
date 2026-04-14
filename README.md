# NCBI agentic search

Ask a question in English. Get a cited, multi-database answer in seconds.

Connects 6 NCBI databases (Gene, PubMed, ClinVar, MedGen, Taxonomy, SNP) into a BioLink-compliant knowledge graph. An 8-agent AI system understands your question, plans retrieval across databases, and synthesizes cited answers.

5 ways to access:
- Web UI: interactive search with graph visualization
- MCP server: for AI agents (Claude, GPT, Gemini)
- REST API: for programmatic access (OpenAPI spec)
- CLI: `ncbi-search "pathogenic BRCA1 variants in breast cancer"`
- KGX export: bulk graph download for data scientists

150M+ nodes. 6 databases. 30+ more on-demand via ELink. Every fact cited. Every connection visible.

---

## Status

Phase 1 complete: Gene + ClinVar + MedGen ETL pipelines, 6 shared modules, merge infrastructure, 146 tests. Gate 1 next: run pipelines on real data.

| System | Status |
|--------|--------|
| System 1: data pipelines | Phase 1 done. Gate 1 (real data validation) next. |
| System 2: knowledge graph | Not started |
| System 3: search agent | Not started |

---

## Architecture

```
System 1: data engineering
  NCBI FTP -> parse -> BioLink map -> validate -> KGX files

System 2: knowledge graph
  KGX files -> normalize -> merge -> PostgreSQL + AGE

System 3: search agent (8 agents)
  Query -> understand -> plan -> retrieve -> synthesize -> cite
```

See `docs/System_1_data_engineering_plan.md` for detailed build plan.
See `docs/bossman_execution_plan.md` for phase-by-phase execution status.

---

## Quick start

```bash
# Prerequisites
python 3.11+
postgresql 15 + apache age (for System 2)

# Setup
git clone https://github.com/[you]/agentic-search-data-engineering
cd agentic-search-data-engineering
cp .env.example .env  # add your NCBI API key
pip install -r requirements.txt

# Run Gene ETL (Phase 1, Step 1)
python system-01-data-pipelines/gene/pipeline.py
```

---

## Data sources (System 1)

| Database | Records | BioLink category | FTP source |
|----------|---------|-----------------|-----------|
| Gene | 94M | `biolink:Gene` | ftp.ncbi.nlm.nih.gov/gene/DATA/ |
| ClinVar | 4.5M | `biolink:SequenceVariant` | ftp.ncbi.nlm.nih.gov/pub/clinvar/ |
| MedGen | 233K | `biolink:Disease` | ftp.ncbi.nlm.nih.gov/pub/medgen/ |
| PubMed | 40M | `biolink:Article` | ftp.ncbi.nlm.nih.gov/pubmed/baseline/ |
| Taxonomy | 2.9M | `biolink:OrganismTaxon` | ftp.ncbi.nlm.nih.gov/pub/taxonomy/ |
| SNP (full dbSNP) | 1.2B | `biolink:SequenceVariant` | ftp.ncbi.nlm.nih.gov/snp/ |

---

## License

Apache 2.0. See LICENSE.
