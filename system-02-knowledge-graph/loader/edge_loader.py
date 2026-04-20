"""edge_loader.py - Stream merged edges.tsv into AGE as graph edges.

Reads the merged KGX edges.tsv in streaming chunks (no full file load into
memory) and inserts each row as an AGE edge via direct SQL INSERT into AGE's
internal edge tables. Rows are grouped by edge label (the predicate column)
so each INSERT targets a single edge label table.

Direct INSERT into ag_catalog."{graph}"."{label}" is used instead of the
cypher() function because AGE's cypher() requires its third argument to be a
PostgreSQL Param node (server-side binding). psycopg2's execute() embeds
parameters as SQL string literals via the simple query protocol, which are
not Param nodes. This causes:
    InvalidParameterValue: third argument of cypher function must be a parameter
Direct INSERT with %s, %s, %s::agtype is a plain SQL operation — no Param
node check applies.

Edge endpoints are resolved from CURIE strings to AGE graphid integers using
a curie_to_id map that must be built after load_nodes() completes. Use
_build_curie_id_map() or pass a pre-built dict to load_edges().

Depends on:
    - psycopg2 (psycopg2.extensions.cursor)
    - stdlib: csv, json, logging, pathlib, collections

Reads:
    - data/kgx/merged/edges.tsv (693M rows)

Writes:
    - AGE edges in PostgreSQL via direct INSERT into ag_catalog edge tables

Depended by:
    - system-02-knowledge-graph/loader/ (main loader orchestration, planned)
    - system-02-knowledge-graph/loader/pipeline.py
"""

import csv
import json
import logging
from collections import defaultdict
from pathlib import Path

import psycopg2
import psycopg2.extensions

from .schema import VERTEX_LABELS

logger = logging.getLogger(__name__)


def _build_curie_id_map(
    cur: psycopg2.extensions.cursor,
    graph_name: str,
    vertex_labels: list[str],
) -> dict[str, str]:
    """Query all vertex label tables to build a CURIE -> AGE graphid mapping.

    Used by load_edges() to resolve edge endpoint CURIEs to AGE internal IDs.
    Must be called AFTER load_nodes() completes.

    Graphids are stored as strings because AGE's graphid type cannot be cast
    from Python int directly in psycopg2 INSERT statements. The edge INSERT
    uses %s::agtype::graphid, which requires a string representation of the
    integer (agtype accepts numeric literals as strings).

    Property access uses (properties -> '"id"')::text — AGE's agtype accessor
    requires the key to be an agtype string literal (double-quoted inside the
    single-quoted argument). The ->> operator is not registered for agtype.

    Args:
        cur: Active psycopg2 cursor with AGE loaded.
        graph_name: AGE graph name.
        vertex_labels: List of vertex label names to query (e.g. VERTEX_LABELS).

    Returns:
        Dict mapping CURIE string -> AGE graphid as string.
    """
    curie_to_id: dict[str, str] = {}
    for label in vertex_labels:
        # Use "{graph_name}"."{label}" (schema.table) — PostgreSQL rejects
        # three-part catalog.schema.table as a cross-database reference.
        # agtype_to_text strips the surrounding double-quotes from the agtype
        # string value. The -> key must be an agtype string literal: '"id"'.
        # The ->> operator is not registered for agtype in this AGE version.
        cur.execute(
            f"SELECT id, agtype_to_text(properties -> '\"id\"') "
            f'FROM "{graph_name}"."{label}"'
        )
        for row in cur.fetchall():
            graphid, curie = row
            if curie:
                curie_to_id[curie] = str(graphid)
    logger.info("Built curie->id map: %d entries", len(curie_to_id))
    return curie_to_id


# How many rows to accumulate per predicate before flushing to AGE.
_DEFAULT_BATCH_SIZE = 500

# Progress log frequency: log every N rows processed.
_PROGRESS_INTERVAL = 1_000_000

# biolink: prefix on the predicate column values.
_BIOLINK_PREFIX = "biolink:"


def load_edges(
    cur: psycopg2.extensions.cursor,
    graph_name: str,
    edges_tsv: Path,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    curie_to_id: dict[str, str] | None = None,
) -> int:
    """Stream edges.tsv, insert in batches via direct SQL INSERT. Returns edge count loaded.

    Processing strategy:
      1. If curie_to_id is None, build it by querying all vertex label tables.
      2. Open edges.tsv with csv.DictReader (tab delimiter, streaming).
      3. For each row, use the predicate column (with biolink: prefix stripped)
         as the edge label.
      4. Accumulate rows into per-label buffers. When any buffer reaches
         batch_size, flush that buffer via a multi-row INSERT into
         ag_catalog."{graph_name}"."{label}".
      5. After the file is exhausted, flush any remaining partial batches.

    Edges whose subject or object CURIE is not in curie_to_id are skipped
    with a warning. This should not happen in production (dangling edges are
    validated at merge time), but is handled defensively.

    The graph_name and label are interpolated into the SQL template (safe:
    graph_name from config; label validated against EDGE_LABELS by orchestrator).
    All property values are passed as %s parameters, never string-interpolated.

    Args:
        cur: An open psycopg2 cursor on a connection with AGE loaded.
        graph_name: Name of the AGE graph to insert edges into.
        edges_tsv: Path to the merged edges.tsv file.
        batch_size: Number of edges per INSERT batch (default 500).
        curie_to_id: Optional pre-built CURIE -> AGE graphid map. If None,
                     built automatically from all VERTEX_LABELS tables.

    Returns:
        Total number of edges successfully inserted.

    Raises:
        FileNotFoundError: If edges_tsv does not exist.
        psycopg2.DatabaseError: On unrecoverable database errors.
    """
    if not edges_tsv.exists():
        raise FileNotFoundError(f"edges.tsv not found: {edges_tsv}")

    # Build curie->graphid map if not supplied by caller.
    if curie_to_id is None:
        curie_to_id = _build_curie_id_map(cur, graph_name, VERTEX_LABELS)

    # Per-label accumulation buffers: label -> list of property dicts
    buffers: defaultdict[str, list[dict]] = defaultdict(list)
    total_loaded = 0
    total_rows = 0

    logger.info(
        "Loading edges from %s into graph '%s' (batch_size=%d)",
        edges_tsv,
        graph_name,
        batch_size,
    )

    with edges_tsv.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            total_rows += 1

            label = _extract_label(row.get("predicate", ""))
            if not label:
                logger.warning("Row %d: empty predicate, skipping", total_rows)
                continue

            edge_props = _extract_edge_props(row)
            buffers[label].append(edge_props)

            if len(buffers[label]) >= batch_size:
                total_loaded += _flush_edge_batch(
                    cur, graph_name, label, buffers[label], curie_to_id
                )
                buffers[label] = []

            if total_rows % _PROGRESS_INTERVAL == 0:
                logger.info(
                    "Progress: %d rows processed, %d edges loaded",
                    total_rows,
                    total_loaded,
                )

    # Flush remaining partial batches
    for label, batch in buffers.items():
        if batch:
            total_loaded += _flush_edge_batch(cur, graph_name, label, batch, curie_to_id)

    logger.info(
        "Edge load complete: %d rows processed, %d edges loaded into graph '%s'",
        total_rows,
        total_loaded,
        graph_name,
    )
    return total_loaded


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_label(predicate: str) -> str:
    """Strip 'biolink:' prefix and return the edge label name.

    Returns an empty string if predicate is blank. Matches the same logic
    used by node_loader._extract_label for the category column.
    """
    stripped = predicate.strip()
    if not stripped:
        return ""
    if stripped.startswith(_BIOLINK_PREFIX):
        return stripped[len(_BIOLINK_PREFIX):]
    # Already stripped (some rows may omit the prefix)
    return stripped


def _extract_edge_props(row: dict) -> dict:
    """Extract edge property fields from a TSV row dict.

    Reads by column name (not position) so extra pipeline-specific columns
    are ignored gracefully. Returns only the properties relevant to the AGE
    edge relationship plus the subject/object identifiers for MATCH.
    """
    return {
        "subject": row.get("subject", ""),
        "object": row.get("object", ""),
        "source": row.get("source", ""),
        "source_url": row.get("source_url", ""),
        "knowledge_level": row.get("knowledge_level", ""),
        "agent_type": row.get("agent_type", ""),
    }


def _flush_edge_batch(
    cur: psycopg2.extensions.cursor,
    graph_name: str,
    label: str,
    batch: list[dict],
    curie_to_id: dict[str, str],
) -> int:
    """Insert a batch of edges directly into AGE's internal edge table.

    Resolves subject/object CURIEs to AGE graphids using curie_to_id map.
    Skips edges where either endpoint is missing from the map (logs warning).

    AGE stores edges in ag_catalog."{graph_name}"."{label}" with columns:
        id graphid (auto-generated), start_id graphid, end_id graphid,
        properties agtype.

    graph_name comes from application config — safe to interpolate.
    label comes from the predicate column — validated against EDGE_LABELS by
    the orchestrator; trusted here.
    All property values flow through %s::agtype parameters, never interpolated.

    Args:
        cur: Active psycopg2 cursor with AGE loaded.
        graph_name: AGE graph name (from config, not user input).
        label: Edge label name / predicate (e.g. "gene_associated_with_condition").
        batch: List of edge property dicts with subject, object, and properties.
        curie_to_id: CURIE -> AGE graphid map (built from vertex tables).

    Returns:
        Number of edges actually inserted (skipped edges not counted).

    Raises:
        psycopg2.DatabaseError: On INSERT execution failure.
    """
    if not batch:
        return 0

    rows = []
    skipped = 0
    for edge in batch:
        start_id = curie_to_id.get(edge.get("subject", ""))
        end_id = curie_to_id.get(edge.get("object", ""))
        if start_id is None or end_id is None:
            logger.warning(
                "Skipping edge: endpoint not found in graph (subject=%s object=%s)",
                edge.get("subject"),
                edge.get("object"),
            )
            skipped += 1
            continue
        props = {k: v for k, v in edge.items() if k not in ("subject", "predicate", "object")}
        rows.append((start_id, end_id, json.dumps(props)))

    if not rows:
        return 0

    # start_id and end_id are graphid strings. AGE's graphid type has no direct
    # cast from bigint in psycopg2; the only registered source cast is from
    # agtype. Cast path: %s (text param) -> ::agtype -> ::graphid.
    # Use "{graph_name}"."{label}" (schema.table) — three-part
    # ag_catalog."g"."l" is rejected by PostgreSQL as a cross-database ref.
    values_sql = ", ".join(
        ["(%s::agtype::graphid, %s::agtype::graphid, %s::agtype)"] * len(rows)
    )
    sql = (
        f'INSERT INTO "{graph_name}"."{label}" '
        f"(start_id, end_id, properties) VALUES {values_sql}"
    )
    # Flatten: [(s1, e1, p1), (s2, e2, p2)] -> [s1, e1, p1, s2, e2, p2]
    params = [val for row in rows for val in row]
    cur.execute(sql, params)

    if skipped:
        logger.warning("Batch: %d edges skipped (missing endpoints)", skipped)
    logger.debug("Inserted %d %s edges (%d skipped)", len(rows), label, skipped)
    return len(rows)
