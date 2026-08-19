"""Build phase 4.4: the KGX export, a batch job over Layer 1.

Reads a scoped subgraph out of the already-built AGE graph and serializes
it as KGX (`nodes.tsv` plus `edges.tsv` plus a manifest). It never writes
to the graph, and it is not an ETL path: see the "Reading KGX out of the
graph is not writing KGX into it" section of `.claude/rules/file-protection.md`.

Depends on:
    - system_03_search_agent.tools.graph_connection (read-only Layer 1)
    - system_03_search_agent.tools.graph_schema_constants
    - system_03_search_agent.tools.cypher_provenance

Writes:
    - The caller-supplied output directory only.
"""
