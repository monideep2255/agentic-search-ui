"""node_loader.py - Stream merged nodes.tsv into AGE as vertex nodes.

Reads the merged KGX nodes.tsv in streaming chunks (no full file load into
memory) and inserts each row as an AGE vertex via direct SQL INSERT into
AGE's internal vertex tables. Rows are grouped by vertex label (derived from
the category column) so that each INSERT targets a single homogeneous vertex
label table.

Direct INSERT into ag_catalog."{graph}"."{Label}" is used instead of the
cypher() function because AGE's cypher() requires its third argument to be a
PostgreSQL Param node (server-side binding). psycopg2's execute() embeds
parameters as SQL string literals via the simple query protocol, which are
not Param nodes. This causes:
    InvalidParameterValue: third argument of cypher function must be a parameter
Direct INSERT with %s::agtype is a plain SQL operation — no Param node check
applies.

Depends on:
    - psycopg2 (psycopg2.extensions.cursor)
    - stdlib: csv, json, logging, pathlib, collections

Reads:
    - data/kgx/merged/nodes.tsv (115M rows)

Writes:
    - AGE vertices in PostgreSQL via direct INSERT into ag_catalog vertex tables

Depended by:
    - system-02-knowledge-graph/loader/ (main loader orchestration, planned)
"""

import csv
import json
import logging
from collections import defaultdict
from pathlib import Path

import psycopg2
import psycopg2.extensions

logger = logging.getLogger(__name__)

# How many rows to accumulate per category before flushing to AGE.
_DEFAULT_BATCH_SIZE = 500

# Progress log frequency: log every N rows processed.
_PROGRESS_INTERVAL = 1_000_000

# biolink: prefix on the category column values.
_BIOLINK_PREFIX = "biolink:"


def load_nodes(
    cur: psycopg2.extensions.cursor,
    graph_name: str,
    nodes_tsv: Path,
    batch_size: int = _DEFAULT_BATCH_SIZE,
) -> int:
    """Stream nodes.tsv, insert in batches via direct SQL INSERT. Returns node count loaded.

    Processing strategy:
      1. Open nodes.tsv with csv.DictReader (tab delimiter, streaming).
      2. For each row, derive the vertex label by stripping "biolink:" from
         the category field.
      3. Accumulate rows into per-label buffers. When any buffer reaches
         batch_size, flush that buffer via a multi-row INSERT into
         ag_catalog."{graph_name}"."{label}".
      4. After the file is exhausted, flush any remaining partial batches.

    The graph_name and label are interpolated into the SQL template (safe:
    graph_name comes from application config; label comes from the category
    column and is validated against VERTEX_LABELS by the orchestrator).
    All property values are passed as %s::agtype parameters, never
    string-interpolated.

    Args:
        cur: An open psycopg2 cursor on a connection with AGE loaded.
        graph_name: Name of the AGE graph to insert into.
        nodes_tsv: Path to the merged nodes.tsv file.
        batch_size: Number of nodes per INSERT batch (default 500).

    Returns:
        Total number of nodes successfully inserted.

    Raises:
        FileNotFoundError: If nodes_tsv does not exist.
        psycopg2.DatabaseError: On unrecoverable database errors.
    """
    if not nodes_tsv.exists():
        raise FileNotFoundError(f"nodes.tsv not found: {nodes_tsv}")

    # Per-label accumulation buffers: label -> list of property dicts
    buffers: defaultdict[str, list[dict]] = defaultdict(list)
    total_loaded = 0
    total_rows = 0

    logger.info("Loading nodes from %s into graph '%s' (batch_size=%d)", nodes_tsv, graph_name, batch_size)

    with nodes_tsv.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            total_rows += 1

            label = _extract_label(row.get("category", ""))
            if not label:
                logger.warning("Row %d: empty or unrecognised category %r, skipping", total_rows, row.get("category"))
                continue

            node_props = _extract_node_props(row)
            buffers[label].append(node_props)

            if len(buffers[label]) >= batch_size:
                total_loaded += _flush_node_batch(cur, graph_name, label, buffers[label])
                buffers[label] = []

            if total_rows % _PROGRESS_INTERVAL == 0:
                logger.info("Progress: %d rows processed, %d nodes loaded", total_rows, total_loaded)

    # Flush remaining partial batches
    for label, batch in buffers.items():
        if batch:
            total_loaded += _flush_node_batch(cur, graph_name, label, batch)

    logger.info(
        "Node load complete: %d rows processed, %d nodes loaded into graph '%s'",
        total_rows,
        total_loaded,
        graph_name,
    )
    return total_loaded


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_label(category: str) -> str:
    """Strip 'biolink:' prefix and return the vertex label name.

    Returns an empty string if category is blank.
    """
    stripped = category.strip()
    if not stripped:
        return ""
    if stripped.startswith(_BIOLINK_PREFIX):
        return stripped[len(_BIOLINK_PREFIX):]
    # Already stripped (some rows may omit the prefix)
    return stripped


def _extract_node_props(row: dict) -> dict:
    """Extract node property fields from a TSV row dict.

    Reads by column name (not position) so extra pipeline-specific columns
    are ignored gracefully. Returns only the properties that will be written
    into the AGE vertex.
    """
    return {
        "id": row.get("id", ""),
        "name": row.get("name", ""),
        "source": row.get("source", ""),
        "source_url": row.get("source_url", ""),
        "xrefs": row.get("xrefs", ""),
        "knowledge_level": row.get("knowledge_level", ""),
        "agent_type": row.get("agent_type", ""),
    }


def _flush_node_batch(
    cur: psycopg2.extensions.cursor,
    graph_name: str,
    label: str,
    batch: list[dict],
) -> int:
    """Insert a batch of nodes directly into AGE's internal vertex table.

    AGE stores vertices in ag_catalog."{graph_name}"."{label}".
    Direct INSERT bypasses cypher() and its Param-node constraint.
    The %s::agtype cast converts the text parameter to AGE's property format.

    graph_name comes from application config — safe to interpolate.
    label comes from the category column after prefix stripping — validated
    against VERTEX_LABELS by the orchestrator; trusted here.
    All property values flow through %s::agtype parameters, never interpolated.

    Args:
        cur: Active psycopg2 cursor with AGE loaded.
        graph_name: AGE graph name (from config, not user input).
        label: Vertex label name (e.g. "Gene").
        batch: List of node property dicts.

    Returns:
        Number of nodes inserted (len of batch).

    Raises:
        psycopg2.DatabaseError: On INSERT execution failure.
    """
    if not batch:
        return 0

    # Build multi-row INSERT: INSERT INTO ... VALUES (%s::agtype), (%s::agtype), ...
    # Each row's properties dict is serialized to JSON and cast to agtype.
    # AGE stores vertex tables as "{graph_name}"."{Label}" within the ag_catalog
    # schema. The connection search_path already includes ag_catalog, so the
    # table is referenced as "{graph_name}"."{Label}" (schema.table), not as
    # ag_catalog."{graph_name}"."{Label}" (which PostgreSQL parses as a
    # three-part catalog.schema.table reference and rejects as cross-database).
    values_sql = ", ".join(["(%s::agtype)"] * len(batch))
    sql = (
        f'INSERT INTO "{graph_name}"."{label}" (properties) '
        f"VALUES {values_sql}"
    )
    props = [json.dumps(row) for row in batch]
    cur.execute(sql, props)
    logger.debug("Inserted %d %s nodes", len(batch), label)
    return len(batch)
