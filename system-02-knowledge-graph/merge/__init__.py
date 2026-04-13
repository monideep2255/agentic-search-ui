"""KGX merge and node normalization.

Combines per-database KGX files, deduplicates nodes by canonical ID,
validates no dangling edges, and produces the merged graph for loading.
"""
