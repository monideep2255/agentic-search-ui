"""Layer 1 graph connection and Cypher execution over psycopg2 and AGE.

This module is the I/O boundary for `cypher_query` (Technical_specification.md
Section 6.1). It owns exactly one job: open a connection to the AGE-enabled
Postgres instance as the read-only `kg_reader` role, wrap an already-validated
Cypher body in the AGE SQL call, execute it under a bounded timeout, and
return rows plus a total-available count. It does not generate Cypher and it
does not validate Cypher structure; those are `cypher_generation` and
`cypher_validator`'s jobs. This module trusts that the `cypher` argument it
receives is a Cypher template that uses named parameters ($paramName) for
every caller-supplied value, never a literal value concatenated in by an
upstream step.

Adapted from the AGE connection pattern in
`reference/agentic-search-data-engineering/system-02-knowledge-graph/loader/connection.py`,
with one deliberate divergence: that pattern issues `LOAD 'age';` because it
runs as a superuser during bulk loading. The `kg_reader` role used here is a
non-superuser with `session_preload_libraries = age` set at the role level,
so `LOAD 'age'` is neither necessary nor permitted (a non-superuser raises
`InsufficientPrivilege` on that statement). Only `search_path` is set here.

Depends on:
    - psycopg2 (the Layer 1 database driver)
    - system_03_search_agent.tools.graph_schema_constants (GRAPH_NAME,
      DEFAULT_ROW_LIMIT, MAX_ROW_LIMIT, CYPHER_QUERY_TIMEOUT_SECONDS)

Reads:
    - Environment variables: GRAPH_PG_HOST, GRAPH_PG_PORT, GRAPH_PG_USER,
      GRAPH_PG_PASSWORD, GRAPH_PG_DBNAME (read-only `kg_reader` role on the
      Hetzner AGE graph, reached through the SSH local port-forward recorded
      in tracker/phase_2.1.md).

Writes:
    - Nothing. The connection is read-only by credential: `kg_reader` carries
      `default_transaction_read_only = on`. This module adds no additional
      write path.

Depended by:
    - system_03_search_agent.tools.cypher_query (T-2.1-07, the pipeline that
      assembles schema slicing, generation, validation, and this execution
      step into the tool the Act step calls)
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from typing import Any

import psycopg2
import psycopg2.errors
import psycopg2.extensions

from system_03_search_agent.tools.graph_schema_constants import (
    CYPHER_QUERY_TIMEOUT_SECONDS,
    DEFAULT_ROW_LIMIT,
    GRAPH_NAME,
    MAX_ROW_LIMIT,
)

ConnectionFactory = Callable[[], "psycopg2.extensions.connection"]

# Session setup issued on every new connection, in place of the reference
# pattern's `LOAD 'age';`. The kg_reader role preloads AGE at the role level
# (session_preload_libraries = age), and a non-superuser cannot run LOAD.
_SEARCH_PATH_SQL = 'SET search_path = ag_catalog, "$user", public;'

# The default AGE output column. A row's Cypher RETURN clause is expected to
# collapse to one expression per row; a caller with a different shape can
# override as_clause, since cursor.description drives the returned dict keys
# either way.
_DEFAULT_AS_CLAUSE = "(result agtype)"

# A safe-shape guard on as_clause. It is an internal, code-controlled
# parameter (never raw end-user input), but this keeps the wrapper honest
# about what it will concatenate into SQL text.
_AS_CLAUSE_PATTERN = re.compile(r"^\([A-Za-z_][A-Za-z0-9_ ,]*\)$")

# Environment variable names read for the default connection. Only the
# names are ever logged or mentioned in an error message, never the values.
_ENV_HOST = "GRAPH_PG_HOST"
_ENV_PORT = "GRAPH_PG_PORT"
_ENV_USER = "GRAPH_PG_USER"
_ENV_PASSWORD = "GRAPH_PG_PASSWORD"
_ENV_DBNAME = "GRAPH_PG_DBNAME"

_AUTH_SQLSTATES = {"28000", "28P01"}
_AUTH_MESSAGE_MARKERS = ("password authentication failed", "authentication failed")


class GraphError(Exception):
    """Base exception for every Layer 1 graph connection or execution failure."""


class GraphConnectionError(GraphError):
    """The graph connection could not be established, or was lost mid-query.

    Covers connection refused, host unreachable, and any other transport
    failure that is not specifically a timeout or an authentication failure.
    """


class GraphTimeoutError(GraphError):
    """The query exceeded its per-call timeout budget (30 seconds by default)."""


class GraphAuthError(GraphError):
    """The kg_reader role failed authentication against the graph host."""


def _redact(message: str, secret: str | None) -> str:
    """Remove a credential value from a message before it is raised or logged.

    This never adds the secret to a message. It only ever strips an
    occurrence of it out, as a belt-and-suspenders check against a driver
    or dependency echoing a connection parameter back in an error string.
    """
    if secret:
        message = message.replace(secret, "[REDACTED]")
    return message


def _classify_connect_error(exc: psycopg2.OperationalError, password: str | None) -> GraphError:
    """Turn a connect-time psycopg2.OperationalError into a typed GraphError.

    Classification never inspects the password value; it only inspects the
    SQLSTATE code and message text psycopg2 itself surfaces, which for a
    connect-time authentication failure names the role, not the password.
    """
    pgcode = getattr(exc, "pgcode", None)
    lowered = str(exc).lower()
    is_auth_failure = pgcode in _AUTH_SQLSTATES or any(
        marker in lowered for marker in _AUTH_MESSAGE_MARKERS
    )
    if is_auth_failure:
        return GraphAuthError(
            _redact(
                "graph authentication failed for the kg_reader role, verify "
                "GRAPH_PG_USER and GRAPH_PG_PASSWORD are set correctly and retry",
                password,
            )
        )
    return GraphConnectionError(
        _redact(
            "graph connection refused or unreachable, verify GRAPH_PG_HOST and "
            "GRAPH_PG_PORT and that the SSH tunnel to the graph host is open, "
            "then retry",
            password,
        )
    )


def _default_connection_factory() -> psycopg2.extensions.connection:
    """Open a connection to the Layer 1 graph using environment credentials.

    Reads GRAPH_PG_HOST, GRAPH_PG_PORT, GRAPH_PG_USER, GRAPH_PG_PASSWORD, and
    GRAPH_PG_DBNAME. Raises GraphConnectionError if any required variable is
    unset, so a missing tunnel or missing .env fails fast with a named cause
    rather than a bare psycopg2 error deeper in the stack.
    """
    host = os.environ.get(_ENV_HOST)
    port = os.environ.get(_ENV_PORT, "5432")
    user = os.environ.get(_ENV_USER)
    password = os.environ.get(_ENV_PASSWORD)
    dbname = os.environ.get(_ENV_DBNAME)

    missing = [
        name
        for name, value in (
            (_ENV_HOST, host),
            (_ENV_USER, user),
            (_ENV_PASSWORD, password),
            (_ENV_DBNAME, dbname),
        )
        if not value
    ]
    if missing:
        raise GraphConnectionError(
            "graph connection environment variables are not fully set: "
            + ", ".join(missing)
            + " must all be set, then retry"
        )

    # Connect-time exceptions are intentionally left unclassified here and
    # propagate to execute_cypher's own try/except, which classifies both
    # this default factory and any test-injected factory the same way. That
    # keeps classification in one place instead of duplicating it per
    # factory implementation.
    conn = psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=dbname,
        connect_timeout=10,
    )
    conn.autocommit = True
    return conn


def _wrap_cypher(cypher: str, as_clause: str) -> str:
    """Build the AGE SQL wrapper around an already-validated Cypher body.

    The wrapper is built with plain string concatenation, never an f-string
    or `.format()` call, per the production-standards query-safety gate.
    GRAPH_NAME is a fixed system constant, not caller-supplied. `cypher` must
    already be validated Cypher that uses named parameters ($paramName) for
    every data value; this function performs no validation of its own, that
    is cypher_validator's job upstream. The only value that ever passes
    through the psycopg2 %s placeholder is the params JSON object, appended
    by the caller of this function, never a value spliced into the Cypher
    text itself.
    """
    if "$$" in cypher:
        raise GraphConnectionError(
            "generated Cypher contains a literal '$$', which would break out "
            "of the dollar-quoted query body, rejecting before execution"
        )
    if not _AS_CLAUSE_PATTERN.match(as_clause):
        raise GraphConnectionError(
            "as_clause did not match the expected '(name type, ...)' shape, "
            "rejecting before execution"
        )
    return (
        "SELECT * FROM cypher('"
        + GRAPH_NAME
        + "', $$ "
        + cypher
        + " $$, %s) AS "
        + as_clause
    )


def execute_cypher(
    cypher: str,
    params: dict[str, Any] | None = None,
    row_limit: int = DEFAULT_ROW_LIMIT,
    timeout_s: float = CYPHER_QUERY_TIMEOUT_SECONDS,
    connection_factory: ConnectionFactory | None = None,
    as_clause: str = _DEFAULT_AS_CLAUSE,
) -> tuple[list[dict[str, Any]], int]:
    """Execute an already-validated Cypher query against the Layer 1 graph.

    Wraps `cypher` as `SELECT * FROM cypher('ncbi_kg', $$ ... $$, %s) AS
    (...)`. `params` passes through the psycopg2 %s placeholder as a JSON
    object; it is never string-interpolated into the Cypher text.

    Args:
        cypher: An already-validated Cypher body using named parameters
            ($paramName) for every caller-supplied value. Never a raw or
            unvalidated string; validation is cypher_validator's job.
        params: The values referenced by the Cypher's named parameters,
            passed to AGE as a JSON object through the psycopg2 %s
            placeholder.
        row_limit: The maximum number of rows to return to the caller. Rows
            beyond this count are truncated, with total_available reporting
            how many the query actually returned and truncated set True.
        timeout_s: The per-call budget in seconds. Enforced with a session
            level `SET statement_timeout` on the connection this call opens.
        connection_factory: A zero-argument callable returning an open
            psycopg2 connection. Defaults to the real environment-backed
            connection. Tests inject a fake factory here.
        as_clause: The AGE output column declaration, for example
            "(result agtype)". Defaults to a single generic output column.
            This is an internal, code-controlled parameter, never raw
            end-user input.

    Returns:
        A tuple of (rows, total_available). Each row is a dict keyed by the
        AGE output column name(s) declared in as_clause.

    Raises:
        GraphConnectionError: The connection could not be established or
            was lost during execution.
        GraphAuthError: The kg_reader role failed authentication.
        GraphTimeoutError: The query exceeded timeout_s.
    """
    factory = connection_factory or _default_connection_factory
    bound_params = params or {}
    effective_row_limit = min(row_limit, MAX_ROW_LIMIT) if row_limit >= 1 else DEFAULT_ROW_LIMIT

    # Classification happens here, in one place, so a connect-time failure
    # from the default factory and from a test-injected factory are both
    # turned into the same typed GraphError family.
    password = os.environ.get(_ENV_PASSWORD)
    try:
        conn = factory()
    except GraphError:
        raise
    except psycopg2.OperationalError as exc:
        raise _classify_connect_error(exc, password) from None
    except Exception as exc:  # noqa: BLE001 - last-resort classification, see below
        # A connection_factory (default or test-injected) can in principle
        # raise something other than psycopg2.OperationalError. This is the
        # deliberate catch-all that still turns it into a typed GraphError
        # instead of letting an unclassified exception escape this module,
        # per the production-standards retry-safety gate: the Act step
        # reads the error type to decide its next move, so it must always
        # get one of the four GraphError types, never a bare exception.
        raise GraphConnectionError(
            _redact(
                "graph connection failed: " + type(exc).__name__ + ", verify "
                "network access to the graph host and retry",
                password,
            )
        ) from None

    try:
        try:
            with conn.cursor() as cur:
                cur.execute(_SEARCH_PATH_SQL)
                cur.execute(
                    "SET statement_timeout = %s;",
                    (int(timeout_s * 1000),),
                )
                wrapped_sql = _wrap_cypher(cypher, as_clause)
                cur.execute(wrapped_sql, (json.dumps(bound_params),))
                fetched = cur.fetchall()
                columns = [desc[0] for desc in cur.description] if cur.description else []
        except psycopg2.errors.QueryCanceled:
            timeout_display = f"{timeout_s:g}"
            raise GraphTimeoutError(
                "graph query exceeded " + timeout_display + "s, retry with a "
                "narrower query_intent or a smaller query_class"
            ) from None
        except psycopg2.OperationalError:
            raise GraphConnectionError(
                "graph connection was lost during query execution, retry"
            ) from None
        except GraphError:
            raise
        except psycopg2.Error as exc:
            raise GraphConnectionError(
                "graph query failed: " + type(exc).__name__ + ", verify the "
                "generated Cypher and retry"
            ) from None
    finally:
        conn.close()

    rows = [dict(zip(columns, row)) for row in fetched]
    total_available = len(rows)
    truncated = total_available > effective_row_limit
    if truncated:
        rows = rows[:effective_row_limit]

    return rows, total_available
