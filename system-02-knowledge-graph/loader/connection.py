"""connection.py - PostgreSQL + Apache AGE connection helper.

Every connection to the AGE-enabled database must load the AGE shared library
and set the search_path so that AGE catalog functions are accessible without
schema-qualification. This module provides a single entry point for that setup.

Depends on:
    - psycopg2 (pip install psycopg2-binary)

Reads:
    - DSN string supplied by caller (from environment or PipelineConfig)

Writes:
    - Nothing (connection setup only)

Depended by:
    - system-02-knowledge-graph/loader/schema.py
    - system-02-knowledge-graph/loader/node_loader.py
    - system-02-knowledge-graph/loader/edge_loader.py
    - system-02-knowledge-graph/loader/index_builder.py
"""

import logging

import psycopg2
import psycopg2.extensions

logger = logging.getLogger(__name__)

# AGE setup statements executed on every new connection.
_AGE_SETUP_SQL = [
    "LOAD 'age';",
    "SET search_path = ag_catalog, \"$user\", public;",
]


def connect_age(
    dsn: str,
    autocommit: bool = True,
) -> psycopg2.extensions.connection:
    """Connect to PostgreSQL, load AGE extension, set search_path.

    Opens a new psycopg2 connection using the supplied DSN, then issues the
    two AGE setup statements required before any Cypher queries can run:
      1. LOAD 'age'  - loads the AGE shared library into the session
      2. SET search_path = ag_catalog, "$user", public  - makes AGE catalog
         functions available without schema-qualification

    autocommit defaults to True because AGE DDL (create_graph, create_vlabel,
    CREATE INDEX) must not run inside a transaction block on some AGE versions.
    Set autocommit=False when you need explicit transaction control (e.g. bulk
    inserts where you want to rollback on error).

    Args:
        dsn: PostgreSQL connection string, e.g.
             "host=localhost port=5432 dbname=kg user=postgres password=secret"
             or a libpq URI: "postgresql://user:pass@host:5432/dbname"
        autocommit: Whether to set connection.autocommit = True after setup.
                    Defaults to True.

    Returns:
        An open psycopg2 connection with AGE loaded and search_path set.

    Raises:
        psycopg2.OperationalError: If the connection cannot be established.
        psycopg2.DatabaseError: If LOAD 'age' fails (AGE not installed).
    """
    logger.debug("Connecting to PostgreSQL via DSN (autocommit=%s)", autocommit)
    conn = psycopg2.connect(dsn)
    conn.autocommit = autocommit

    with conn.cursor() as cur:
        for stmt in _AGE_SETUP_SQL:
            logger.debug("Executing AGE setup: %s", stmt.strip())
            cur.execute(stmt)

    logger.info("AGE connection ready (autocommit=%s)", autocommit)
    return conn
