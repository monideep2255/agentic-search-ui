# Decisions

Architecture and implementation decisions made during this project.

| Date | Decision | Alternatives considered | Why |
|------|----------|------------------------|-----|
| 2026-04-06 | PostgreSQL + Apache AGE for graph storage (supersedes Neo4j decision below) | Neo4j Community, Neo4j AuraDB | Neo4j Community needs 64GB+ RAM for large graphs. PostgreSQL + AGE is disk-based and handles 150M nodes on 8GB RAM. Saves $100-200/month on hosting. Cypher syntax still supported via openCypher in AGE. |
| 2026-04-06 | Neo4j Community Edition for local dev (SUPERSEDED 2026-04-06 by PG+AGE above) | AuraDB (cloud), PostgreSQL + AGE | Free, local, full Cypher support. Switch to AuraDB or self-hosted for production. PostgreSQL + AGE is the budget option if Neo4j costs are prohibitive. |
| 2026-04-06 | Start with 1-month scope: Gene + ClinVar + MedGen only | Full 6-database scope from week 1 | Ship something real in 4 weeks. PubMed download alone takes 4-8 hours. Add remaining databases in month 2. |
| 2026-04-06 | KGX format for pipeline output (nodes.tsv + edges.tsv) | Direct Neo4j Cypher INSERT, JSON-LD | KGX is the standard for BioLink-compliant graph exchange. System 1 and System 2 stay decoupled. |
| 2026-04-06 | LinkML for schema definition | Raw BioLink YAML, Pydantic models | LinkML generates validators automatically. BioLink uses LinkML natively. Schema-as-code. |
| 2026-04-06 | SNP: clinical subset only (~500K) via ClinVar cross-references | Full dbSNP (1.2B records) | 1.2B records are too large for a 2-month alpha. Clinical subset covers the queries that matter. Expand later. |
| 2026-04-06 | PubMed: 2024-2026 subset first | Full 40M article baseline | Full baseline download is 30GB compressed, 4-8 hours. Start small, prove the pipeline, then expand. |
| 2026-04-06 | Apache 2.0 license | MIT, GPL | Permissive (commercial use allowed), has patent protection, NCBI can adopt without legal friction. |
| 2026-04-06 | This repo holds System 1 + System 2 only; System 3 in a separate repo | Single monorepo for all three systems | System 3 (search agent, FastAPI, LangGraph, UI) has different deployment cadence and dependencies. Decoupling lets data pipelines and graph load run independently of agent layer. |
| 2026-04-06 | Adopt 9-step pipeline pattern from canonical reference (`reference/ncbi_ai_agents-ncbi-kg/KG/pipeline/`) over reinventing | Custom 5-step pattern from scratch | Reference pipeline already produces a BioLink 4.x compliant KG with 82K nodes / 263K edges. Idempotent download, dedup, dangling-edge validation, MONDO stub injection, KGX export are all working. Copy patterns directly. |
| 2026-04-06 | BioLink 4.x: 8 node categories, 15 edge predicates (verbatim from reference) | Define our own subset, use BioLink 5.x | Reference pipeline schema is validated against real glucose metabolism KG. Categories: Gene, Protein, SequenceVariant, Disease, BiologicalProcess, MolecularActivity, CellularComponent, Pathway. We extend rather than replace. |
| 2026-04-06 | DataFrame-based assembly with pandas (per reference pipeline) | Direct streaming to graph, dict-of-dicts | Reference uses pandas DataFrames for nodes/edges, dedups by id and (subject, predicate, object), validates dangling edges. Mature, tested, debuggable. |
| 2026-04-06 | Canonical CURIE prefixes: NCBIGene, NCBIProtein, ClinVar, MONDO, UMLS, GO, Reactome, MeSH | Custom internal IDs | Match reference pipeline conventions so KGX files merge cleanly with the existing graph and downstream consumers. |
