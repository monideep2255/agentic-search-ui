"""schema.py - AGE graph schema: constants, graph creation, label creation.

Defines the BioLink vertex labels and edge predicates present in the merged
knowledge graph, and provides idempotent DDL helpers to create the AGE graph
and its vertex/edge labels.

Depends on:
    - psycopg2 (psycopg2.extensions.cursor)
    - system-02-knowledge-graph/loader/connection.py (connect_age, for callers)

Reads:
    - Nothing (constants only; no file I/O)

Writes:
    - AGE graph schema in PostgreSQL (DDL via psycopg2 cursor)

Depended by:
    - system-02-knowledge-graph/loader/node_loader.py
    - system-02-knowledge-graph/loader/edge_loader.py
    - system-02-knowledge-graph/loader/index_builder.py
"""

import logging

import psycopg2
import psycopg2.extensions
import psycopg2.errors

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BioLink constants
# Strip "biolink:" prefix from category column values to get the vertex label.
# These labels must match the category values in the merged nodes.tsv exactly
# (after prefix stripping).
# ---------------------------------------------------------------------------

VERTEX_LABELS: list[str] = [
    "Gene",
    "SequenceVariant",
    "Disease",
    "PhenotypicFeature",
    "Article",
    "OntologyClass",
    "OrganismTaxon",
    "BiologicalProcess",
    "MolecularActivity",
    "CellularComponent",
    "NamedThing",
]

EDGE_LABELS: list[str] = [
    "gene_associated_with_condition",
    "is_sequence_variant_of",
    "has_phenotype",
    "participates_in",
    "actively_involved_in",
    "located_in",
    "mentioned_in",
    "has_mesh_annotation",
    "cited_in",
    "in_taxon",
    "subclass_of",
    "orthologous_to",
    "exact_match",
    "close_match",
]


def create_graph(
    cur: psycopg2.extensions.cursor,
    graph_name: str,
) -> None:
    """Create AGE graph if not exists. Idempotent.

    AGE does not have a CREATE GRAPH IF NOT EXISTS syntax. Instead we attempt
    the creation and catch the duplicate object error (PostgreSQL error code
    42P07, or a message containing "already exists").

    Args:
        cur: An open psycopg2 cursor on a connection with AGE loaded.
        graph_name: Name for the AGE graph (e.g. "biolink_kg").

    Raises:
        psycopg2.DatabaseError: On unexpected database errors (not duplicate).
    """
    try:
        cur.execute("SELECT create_graph(%s);", (graph_name,))
        logger.info("Created AGE graph: %s", graph_name)
    except psycopg2.errors.DuplicateTable as exc:
        # AGE raises DuplicateTable when the graph already exists.
        logger.info("Graph already exists, skipping creation: %s (%s)", graph_name, exc)
        cur.connection.rollback()
    except psycopg2.DatabaseError as exc:
        # Some AGE versions raise a generic DatabaseError with "already exists"
        # in the message rather than a typed DuplicateTable exception.
        if "already exists" in str(exc).lower():
            logger.info(
                "Graph already exists (generic error), skipping: %s (%s)",
                graph_name,
                exc,
            )
            cur.connection.rollback()
        else:
            raise


def create_vertex_labels(
    cur: psycopg2.extensions.cursor,
    graph_name: str,
    labels: list[str],
) -> None:
    """Create AGE vertex labels. Idempotent (skip existing).

    Iterates over the supplied labels and calls create_vlabel for each. Labels
    that already exist are silently skipped. The connection is rolled back to a
    clean state after each duplicate before continuing.

    Args:
        cur: An open psycopg2 cursor on a connection with AGE loaded.
        graph_name: Name of the AGE graph to add labels to.
        labels: List of vertex label names to create.

    Raises:
        psycopg2.DatabaseError: On unexpected database errors.
    """
    for label in labels:
        _create_vlabel_idempotent(cur, graph_name, label)


def create_edge_label(
    cur: psycopg2.extensions.cursor,
    graph_name: str,
    label: str,
) -> None:
    """Create one AGE edge label. Idempotent.

    Args:
        cur: An open psycopg2 cursor on a connection with AGE loaded.
        graph_name: Name of the AGE graph to add the label to.
        label: Edge label name (predicate) to create.

    Raises:
        psycopg2.DatabaseError: On unexpected database errors.
    """
    try:
        cur.execute("SELECT create_elabel(%s, %s);", (graph_name, label))
        logger.info("Created AGE edge label: %s.%s", graph_name, label)
    except psycopg2.errors.DuplicateTable as exc:
        logger.info(
            "Edge label already exists, skipping: %s.%s (%s)", graph_name, label, exc
        )
        cur.connection.rollback()
    except psycopg2.DatabaseError as exc:
        if "already exists" in str(exc).lower():
            logger.info(
                "Edge label already exists (generic), skipping: %s.%s (%s)",
                graph_name,
                label,
                exc,
            )
            cur.connection.rollback()
        else:
            raise


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _create_vlabel_idempotent(
    cur: psycopg2.extensions.cursor,
    graph_name: str,
    label: str,
) -> None:
    """Create a single vertex label, swallowing duplicate errors."""
    try:
        cur.execute("SELECT create_vlabel(%s, %s);", (graph_name, label))
        logger.info("Created AGE vertex label: %s.%s", graph_name, label)
    except psycopg2.errors.DuplicateTable as exc:
        logger.info(
            "Vertex label already exists, skipping: %s.%s (%s)", graph_name, label, exc
        )
        cur.connection.rollback()
    except psycopg2.DatabaseError as exc:
        if "already exists" in str(exc).lower():
            logger.info(
                "Vertex label already exists (generic), skipping: %s.%s (%s)",
                graph_name,
                label,
                exc,
            )
            cur.connection.rollback()
        else:
            raise
