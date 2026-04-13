"""System 1: data pipelines.

Extracts data from 6 NCBI databases, transforms to BioLink-compliant KGX files,
and prepares for loading into the knowledge graph (System 2).

Input:  NCBI FTP bulk files + mapping files
Output: Per-database KGX files (nodes.tsv + edges.tsv) with provenance on every row
"""
