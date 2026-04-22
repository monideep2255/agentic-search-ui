"""pipeline.py - Orchestrator: load merged KGX files into PostgreSQL + AGE.

Calls all core loader functions in order:
  1. connect_age          — open connection with AGE loaded
  [conditional] drop_graph — drop+recreate if drop_existing=True (not numbered)
  2. create_graph         — idempotent graph creation
  3. create_vertex_labels — idempotent vlabel creation for all 10 BioLink types
  4. create_edge_label    — idempotent elabel creation for all 14 predicates
  5. load_nodes           — stream nodes.tsv into AGE vertex tables (direct INSERT)
  [between 5 and 6]       — build curie->graphid map from vertex tables
  6. load_edges           — stream edges.tsv into AGE edge tables (direct INSERT)
  7. create_indexes       — btree index on id for every vertex label

Node and edge loads use direct INSERT into ag_catalog."{graph}"."{label}"
instead of cypher() UNWIND, because psycopg2's execute() embeds parameters
as SQL string literals (not PostgreSQL Param nodes), which AGE's cypher()
rejects with InvalidParameterValue.

Each step is timed with time.monotonic() and logged at INFO level.

Depends on:
    - system-02-knowledge-graph/loader/connection.py
    - system-02-knowledge-graph/loader/schema.py
    - system-02-knowledge-graph/loader/node_loader.py
    - system-02-knowledge-graph/loader/edge_loader.py
    - system-02-knowledge-graph/loader/index_builder.py
    - psycopg2
    - stdlib: logging, pathlib, time

Reads:
    - {kgx_dir}/nodes.tsv
    - {kgx_dir}/edges.tsv

Writes:
    - AGE graph, vertices, edges, and indexes in PostgreSQL

Depended by:
    - system-02-knowledge-graph/loader/cli.py
    - tests/loader/test_age_loader.py
    - tests/loader/test_age_smoke.py
"""

import logging
import time
from pathlib import Path

import psycopg2

from .connection import connect_age
from .edge_loader import _build_curie_id_map, load_edges
from .index_builder import analyze_tables, create_indexes, discover_edge_labels
from .node_loader import load_nodes
from .schema import EDGE_LABELS, VERTEX_LABELS, create_edge_label, create_graph, create_vertex_labels

logger = logging.getLogger(__name__)


def run_age_load(
    kgx_dir: Path,
    graph_name: str,
    dsn: str,
    drop_existing: bool = False,
    batch_size: int = 500,
) -> dict[str, int]:
    """Load merged KGX files into PostgreSQL + AGE.

    Args:
        kgx_dir: Directory containing merged nodes.tsv and edges.tsv.
        graph_name: AGE graph name (e.g. 'ncbi_kg').
        dsn: psycopg2 DSN string, e.g.
             "host=localhost port=5432 dbname=kg user=postgres password=secret"
        drop_existing: If True, drop and recreate the graph before loading.
                       Use for a clean reload from scratch.
        batch_size: UNWIND batch size passed to load_nodes and load_edges
                    (default 500).

    Returns:
        {"nodes": int, "edges": int} — counts of loaded nodes and edges.

    Raises:
        FileNotFoundError: If nodes.tsv or edges.tsv are missing from kgx_dir.
        psycopg2.DatabaseError: On unrecoverable database errors.
    """
    kgx_dir = Path(kgx_dir)
    nodes_tsv = kgx_dir / "nodes.tsv"
    edges_tsv = kgx_dir / "edges.tsv"

    logger.info(
        "Starting AGE load: graph='%s' kgx_dir=%s drop_existing=%s batch_size=%d",
        graph_name,
        kgx_dir,
        drop_existing,
        batch_size,
    )
    pipeline_start = time.monotonic()

    # Step 1: connect
    t0 = time.monotonic()
    conn = connect_age(dsn)
    cur = conn.cursor()
    logger.info("Step 1 connect_age: %.2fs", time.monotonic() - t0)

    # Conditional (not numbered): drop existing graph when requested
    if drop_existing:
        t0 = time.monotonic()
        # AGE provides drop_graph(name, cascade) as a SQL function.
        # DROP GRAPH is not valid PostgreSQL syntax — use the AGE function instead.
        # AGE has no "IF EXISTS" variant for drop_graph; catch InvalidSchemaName
        # when the graph doesn't exist yet (first clean run).
        try:
            cur.execute("SELECT drop_graph(%s, true);", (graph_name,))
        except psycopg2.errors.InvalidSchemaName:
            logger.debug("Graph '%s' does not exist yet; nothing to drop.", graph_name)
        logger.info(
            "Dropping existing graph (drop_existing=True) '%s': %.2fs",
            graph_name,
            time.monotonic() - t0,
        )

    # Step 2: create graph (idempotent)
    t0 = time.monotonic()
    create_graph(cur, graph_name)
    logger.info("Step 2 create_graph: %.2fs", time.monotonic() - t0)

    # Step 3: create vertex labels (idempotent)
    t0 = time.monotonic()
    create_vertex_labels(cur, graph_name, VERTEX_LABELS)
    logger.info(
        "Step 3 create_vertex_labels (%d labels): %.2fs",
        len(VERTEX_LABELS),
        time.monotonic() - t0,
    )

    # Step 4: create edge labels (idempotent)
    t0 = time.monotonic()
    for label in EDGE_LABELS:
        create_edge_label(cur, graph_name, label)
    logger.info(
        "Step 4 create_edge_labels (%d labels): %.2fs",
        len(EDGE_LABELS),
        time.monotonic() - t0,
    )

    # Step 5: load nodes
    t0 = time.monotonic()
    node_count = load_nodes(cur, graph_name, nodes_tsv, batch_size)
    logger.info(
        "Step 5 load_nodes: %d nodes in %.2fs", node_count, time.monotonic() - t0
    )

    # Build curie->graphid map for edge endpoint resolution.
    # Must run after load_nodes so all vertex tables are populated.
    t0 = time.monotonic()
    curie_to_id = _build_curie_id_map(cur, graph_name, VERTEX_LABELS)
    logger.info(
        "curie_to_id map: %d entries in %.2fs", len(curie_to_id), time.monotonic() - t0
    )

    # Step 6: load edges
    t0 = time.monotonic()
    edge_count = load_edges(cur, graph_name, edges_tsv, batch_size, curie_to_id=curie_to_id)
    logger.info(
        "Step 6 load_edges: %d edges in %.2fs", edge_count, time.monotonic() - t0
    )

    # Step 7: create indexes (4 passes: functional B-tree, graphid PK, GIN, edge endpoints)
    t0 = time.monotonic()
    edge_labels = discover_edge_labels(cur, graph_name)
    create_indexes(cur, graph_name, VERTEX_LABELS, edge_labels=edge_labels)
    logger.info(
        "Step 7 create_indexes: %d edge labels indexed in %.2fs",
        len(edge_labels), time.monotonic() - t0,
    )

    # Step 8: ANALYZE so the planner has fresh stats before any query lands
    t0 = time.monotonic()
    analyze_tables(cur, graph_name, VERTEX_LABELS, edge_labels=edge_labels)
    logger.info("Step 8 analyze_tables: %.2fs", time.monotonic() - t0)

    cur.close()
    conn.close()

    total_elapsed = time.monotonic() - pipeline_start
    logger.info(
        "AGE load complete: %d nodes, %d edges, graph='%s', total=%.2fs",
        node_count,
        edge_count,
        graph_name,
        total_elapsed,
    )

    return {"nodes": node_count, "edges": edge_count}
