"""index_builder.py - Create btree indexes on AGE vertex and edge tables.

AGE stores vertex data in per-label tables under the ag_catalog schema with
the naming convention "{GraphName}"."{LabelName}" (referenced as schema.table
with ag_catalog in the search_path). This module creates a btree index on the
agtype 'id' property for every vertex label, enabling fast CURIE lookups.

Idempotent: uses CREATE INDEX IF NOT EXISTS so it is safe to re-run.

Depends on:
    - psycopg2 (psycopg2.extensions.cursor)
    - stdlib: logging

Reads:
    - Nothing (index DDL only)

Writes:
    - PostgreSQL btree indexes on "{GraphName}"."{LabelName}" tables

Depended by:
    - system-02-knowledge-graph/loader/ (main loader orchestration, planned)
"""

import logging
import re

import psycopg2
import psycopg2.extensions

logger = logging.getLogger(__name__)


def create_indexes(
    cur: psycopg2.extensions.cursor,
    graph_name: str,
    vertex_labels: list[str],
) -> None:
    """Create btree index on id for every vertex label. Idempotent (IF NOT EXISTS).

    AGE vertices store their properties in an agtype column named 'properties'
    on the per-label table "{GraphName}"."{LabelName}" (with ag_catalog in the
    search_path). This function creates a functional btree index on the text
    value of the id property for each label, enabling fast CURIE lookups.

    Index naming convention: idx_{graph_name}_{label}_id
    (lowercase, underscores — avoids quoting issues with the index name itself)

    The CREATE INDEX IF NOT EXISTS pattern makes this idempotent: re-running
    after a partial load or crash will skip already-created indexes without
    error.

    Args:
        cur: An open psycopg2 cursor on a connection with AGE loaded.
             autocommit must be True, or the caller must manage the transaction.
        graph_name: Name of the AGE graph (e.g. "biolink_kg").
        vertex_labels: List of vertex label names to index.
                       Typically VERTEX_LABELS from schema.py.

    Raises:
        psycopg2.DatabaseError: If index creation fails unexpectedly.
    """
    logger.info(
        "Creating id indexes on %d vertex labels for graph '%s'",
        len(vertex_labels),
        graph_name,
    )

    for label in vertex_labels:
        _create_vertex_id_index(cur, graph_name, label)

    logger.info(
        "Index creation complete for graph '%s' (%d labels)",
        graph_name,
        len(vertex_labels),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sanitize_identifier_part(value: str) -> str:
    """Return a safe lowercase identifier fragment for use in index names.

    Replaces characters that are not alphanumeric or underscores with
    underscores. Used only for the index name (not for table/schema names
    which are always quoted).

    Args:
        value: Raw label or graph name string.

    Returns:
        Lowercase string with non-word characters replaced by underscores.
    """
    return re.sub(r"[^\w]", "_", value).lower()


def _create_vertex_id_index(
    cur: psycopg2.extensions.cursor,
    graph_name: str,
    label: str,
) -> None:
    """Create a single btree index on the id property for one vertex label.

    Table name uses the two-part "{graph_name}"."{label}" form (schema.table).
    Three-part ag_catalog."g"."l" is rejected by PostgreSQL as a cross-database
    reference. ag_catalog is already in the search_path set by connect_age().

    Property access uses (properties -> '"id"')::text — AGE's agtype type does
    not support the ->> operator. The key must be an agtype string literal
    (double-quoted inside single quotes); the outer cast strips agtype quoting.

    The index name is constructed from sanitized lowercase fragments and does
    NOT need quoting.

    Args:
        cur: Active psycopg2 cursor.
        graph_name: AGE graph name.
        label: Vertex label name.

    Raises:
        psycopg2.DatabaseError: On unexpected index creation failure.
    """
    # Index name uses sanitized lowercase parts — safe to interpolate.
    # Table identifier uses quoted two-part form — values from application
    # config and the fixed VERTEX_LABELS constant; trusted.
    # psycopg2 %s parameterization cannot be used for identifier names in DDL.
    safe_graph = _sanitize_identifier_part(graph_name)
    safe_label = _sanitize_identifier_part(label)
    index_name = f"idx_{safe_graph}_{safe_label}_id"

    # Double-quoted identifiers preserve the exact case AGE uses.
    # agtype_to_text strips the surrounding double-quotes from the agtype
    # string value returned by (properties -> '"id"'). The -> key must be an
    # agtype string literal: '"id"' (double-quoted inside single-quoted).
    # The ->> operator and ::text cast are not valid on agtype in this AGE version.
    sql = (
        f"CREATE INDEX IF NOT EXISTS {index_name} "
        f"ON \"{graph_name}\".\"{label}\" "
        f"(agtype_to_text(properties -> '\"id\"'));"
    )

    logger.debug("Creating index: %s", index_name)
    cur.execute(sql)
    logger.info("Index ready: %s", index_name)
