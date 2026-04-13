"""System 2: knowledge graph.

Takes KGX files from System 1 data pipelines, normalizes identifiers,
merges across databases, and loads into PostgreSQL + Apache AGE.

Input:  KGX files from data-pipelines (nodes.tsv + edges.tsv per database)
Output: Merged graph in PostgreSQL + Apache AGE, queryable via openCypher
"""
