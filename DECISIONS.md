# Decisions

Architecture and implementation decisions made during this project.

| Date | Decision | Alternatives considered | Why |
|------|----------|------------------------|-----|
| 2026-04-06 | Neo4j Community Edition for local dev | AuraDB (cloud), PostgreSQL + AGE | Free, local, full Cypher support. Switch to AuraDB or self-hosted for production. PostgreSQL + AGE is the budget option if Neo4j costs are prohibitive. |
| 2026-04-06 | Start with 1-month scope: Gene + ClinVar + MedGen only | Full 6-database scope from week 1 | Ship something real in 4 weeks. PubMed download alone takes 4-8 hours. Add remaining databases in month 2. |
| 2026-04-06 | KGX format for pipeline output (nodes.tsv + edges.tsv) | Direct Neo4j Cypher INSERT, JSON-LD | KGX is the standard for BioLink-compliant graph exchange. System 1 and System 2 stay decoupled. |
| 2026-04-06 | LinkML for schema definition | Raw BioLink YAML, Pydantic models | LinkML generates validators automatically. BioLink uses LinkML natively. Schema-as-code. |
| 2026-04-06 | SNP: clinical subset only (~500K) via ClinVar cross-references | Full dbSNP (1.2B records) | 1.2B records are too large for a 2-month alpha. Clinical subset covers the queries that matter. Expand later. |
| 2026-04-06 | PubMed: 2024-2026 subset first | Full 40M article baseline | Full baseline download is 30GB compressed, 4-8 hours. Start small, prove the pipeline, then expand. |
| 2026-04-06 | Apache 2.0 license | MIT, GPL | Permissive (commercial use allowed), has patent protection, NCBI can adopt without legal friction. |
