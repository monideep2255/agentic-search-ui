"""index_builder.py - Create the four index passes AGE needs after a bulk load.

AGE label tables inherit from `_ag_label_vertex` / `_ag_label_edge`. PostgreSQL
inheritance does NOT propagate primary keys, unique constraints, or indexes from
parent to child, so each label table starts as a bare heap with zero indexes.
This module creates the four index types Cypher needs to run at indexed speed.
Without all four passes, queries fall back to seq scans on millions of rows.

Background: see Phase 4 Problem 12 + Problem 13 in docs/learnings.md, and
DECISIONS.md rows 76 to 79.

The four passes (run in order, all idempotent via CREATE INDEX IF NOT EXISTS):

1. Functional B-tree on agtype_to_text(properties -> '"id"') for every vertex
   label. Used by the loader's edge-resolution dict-build (raw SQL path).
2. Unique B-tree on the `id` graphid column for every vertex label. Used by
   any join that lands on a vertex by graphid; without this, even a 1-row
   lookup forces a seq scan because AGE inheritance strips the parent PK.
3. GIN on the `properties` column for every vertex label. The Cypher engine
   compiles MATCH (n:Label {id:'X'}) into WHERE properties @> '{"id":"X"}'::agtype
   (containment), which only GIN can serve.
4. B-tree on (start_id) and (end_id) for every edge label table. Required for
   any traversal; without these, every relationship hop is a seq scan over the
   full edge table.

Depends on:
    - psycopg2 (psycopg2.extensions.cursor)
    - stdlib: logging, re

Reads:
    - Nothing (index DDL only)

Writes:
    - PostgreSQL B-tree and GIN indexes on "{GraphName}"."{LabelName}" tables
    - PostgreSQL B-tree indexes on "{GraphName}"."{EdgeLabel}" tables
    - Refreshed pg_statistic via ANALYZE (caller's responsibility, but recommended
      immediately after this module runs; see analyze_tables() helper)

Depended by:
    - system-02-knowledge-graph/loader/pipeline.py (Step 8: index build)
"""

import logging
import re

import psycopg2
import psycopg2.extensions

logger = logging.getLogger(__name__)


def discover_edge_labels(
    cur: psycopg2.extensions.cursor,
    graph_name: str,
) -> list[str]:
    """Return the list of edge-label table names AGE created for `graph_name`.

    AGE writes one row per label into `ag_catalog.ag_label`, with `kind = 'e'`
    for edges and `'v'` for vertices. Discovering edge labels at index-build
    time avoids a parallel hand-maintained constant for the dozen+ edge
    predicates in the BioLink schema.
    """
    cur.execute(
        "SELECT name FROM ag_catalog.ag_label "
        "WHERE graph = (SELECT graphid FROM ag_catalog.ag_graph WHERE name = %s) "
        "AND kind = 'e' AND name NOT LIKE '\\_ag\\_%%' ORDER BY name;",
        (graph_name,),
    )
    return [r[0] for r in cur.fetchall()]


def create_indexes(
    cur: psycopg2.extensions.cursor,
    graph_name: str,
    vertex_labels: list[str],
    edge_labels: list[str] | None = None,
) -> None:
    """Run all four index passes for an AGE graph after a bulk load.

    Idempotent. Safe to re-run after a partial crash.

    Args:
        cur: psycopg2 cursor on a connection with AGE loaded and autocommit on.
        graph_name: AGE graph name (e.g. 'ncbi_kg').
        vertex_labels: Vertex label names (typically VERTEX_LABELS from schema.py).
        edge_labels: Edge label names. If None, callers must build edge indexes
                     separately. The 4th pass (start_id/end_id B-tree) is skipped
                     when edge_labels is None.

    Raises:
        psycopg2.DatabaseError: If any index creation fails unexpectedly.
    """
    logger.info(
        "Index build for graph '%s': %d vertex labels, %s edge labels",
        graph_name,
        len(vertex_labels),
        len(edge_labels) if edge_labels else "skipped",
    )

    for label in vertex_labels:
        _create_vertex_id_functional_index(cur, graph_name, label)
        _create_vertex_graphid_index(cur, graph_name, label)
        _create_vertex_props_gin_index(cur, graph_name, label)

    if edge_labels:
        for edge_label in edge_labels:
            _create_edge_endpoint_indexes(cur, graph_name, edge_label)

    logger.info("Index build complete for graph '%s'", graph_name)


def analyze_tables(
    cur: psycopg2.extensions.cursor,
    graph_name: str,
    vertex_labels: list[str],
    edge_labels: list[str] | None = None,
) -> None:
    """Run ANALYZE on every vertex and edge table.

    Postgres autovacuum is idle on freshly-loaded tables (no DML happened, so it
    never schedules an ANALYZE), which leaves planner statistics stale. Without
    fresh stats, the planner falls back to defaults and picks bad plans even
    when correct indexes exist. Always run this after a bulk load and after
    create_indexes().

    Args:
        cur: psycopg2 cursor.
        graph_name: AGE graph name.
        vertex_labels: Vertex labels to analyze.
        edge_labels: Edge labels to analyze (skipped if None).
    """
    logger.info("Running ANALYZE on all label tables for graph '%s'", graph_name)
    for label in vertex_labels:
        cur.execute(f'ANALYZE "{graph_name}"."{label}";')
        logger.debug("ANALYZE done: %s.%s", graph_name, label)
    if edge_labels:
        for edge_label in edge_labels:
            cur.execute(f'ANALYZE "{graph_name}"."{edge_label}";')
            logger.debug("ANALYZE done: %s.%s", graph_name, edge_label)
    logger.info("ANALYZE complete for graph '%s'", graph_name)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sanitize_identifier_part(value: str) -> str:
    return re.sub(r"[^\w]", "_", value).lower()


def _create_vertex_id_functional_index(
    cur: psycopg2.extensions.cursor,
    graph_name: str,
    label: str,
) -> None:
    """Pass 1: B-tree on agtype_to_text(properties -> '"id"').

    Used by the loader's edge-resolution code (raw SQL WHERE agtype_to_text(...) = 'X').
    Does NOT serve Cypher MATCH-by-property — see GIN pass for that.
    """
    safe_graph = _sanitize_identifier_part(graph_name)
    safe_label = _sanitize_identifier_part(label)
    index_name = f"idx_{safe_graph}_{safe_label}_id"
    sql = (
        f"CREATE INDEX IF NOT EXISTS {index_name} "
        f'ON "{graph_name}"."{label}" '
        f"(agtype_to_text(properties -> '\"id\"'));"
    )
    cur.execute(sql)
    logger.info("Pass 1 (functional B-tree) ready: %s", index_name)


def _create_vertex_graphid_index(
    cur: psycopg2.extensions.cursor,
    graph_name: str,
    label: str,
) -> None:
    """Pass 2: unique B-tree on the `id` (graphid) column.

    Without this, joins that look up a vertex by graphid PK force a seq scan
    because AGE inheritance does not propagate the parent _ag_label_vertex_pkey
    to child label tables.
    """
    safe_graph = _sanitize_identifier_part(graph_name)
    safe_label = _sanitize_identifier_part(label)
    index_name = f"idx_{safe_graph}_{safe_label}_pk"
    sql = (
        f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} "
        f'ON "{graph_name}"."{label}" (id);'
    )
    cur.execute(sql)
    logger.info("Pass 2 (graphid PK) ready: %s", index_name)


def _create_vertex_props_gin_index(
    cur: psycopg2.extensions.cursor,
    graph_name: str,
    label: str,
) -> None:
    """Pass 3: GIN on the `properties` column.

    Required for Cypher MATCH-by-property. AGE compiles MATCH (n:Label {id:'X'})
    into WHERE properties @> '{"id":"X"}'::agtype (JSONB-style containment),
    which only GIN can serve. Without GIN, every property MATCH falls back to
    a parallel seq scan over the entire label table.
    """
    safe_graph = _sanitize_identifier_part(graph_name)
    safe_label = _sanitize_identifier_part(label)
    index_name = f"idx_{safe_graph}_{safe_label}_props_gin"
    sql = (
        f"CREATE INDEX IF NOT EXISTS {index_name} "
        f'ON "{graph_name}"."{label}" USING gin (properties);'
    )
    cur.execute(sql)
    logger.info("Pass 3 (GIN on properties) ready: %s", index_name)


def _create_edge_endpoint_indexes(
    cur: psycopg2.extensions.cursor,
    graph_name: str,
    edge_label: str,
) -> None:
    """Pass 4: B-tree on (start_id) and (end_id) per edge table.

    Required for any relationship traversal. Without these, every Cypher edge
    hop forces a seq scan over the full edge table (which can be hundreds of
    millions of rows for has_mesh_annotation, mentioned_in, etc.).
    """
    safe_graph = _sanitize_identifier_part(graph_name)
    safe_label = _sanitize_identifier_part(edge_label)
    for col in ("start_id", "end_id"):
        index_name = f"idx_{safe_graph}_{safe_label}_{col}"
        sql = (
            f"CREATE INDEX IF NOT EXISTS {index_name} "
            f'ON "{graph_name}"."{edge_label}" ({col});'
        )
        cur.execute(sql)
        logger.info("Pass 4 (edge %s) ready: %s", col, index_name)
