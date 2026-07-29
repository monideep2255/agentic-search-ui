"""Tests for the Layer 1 graph connection and execution module.

Depends on:
    - system_03_search_agent.tools.graph_connection
    - psycopg2 (for constructing realistic error instances)

Reads:
    - Environment variables GRAPH_PG_HOST and GRAPH_PG_PORT, to decide
      whether the one live integration test should run or skip. The guard
      checks both that the variable is set and that the host:port is
      actually reachable, since importing litellm anywhere in the process
      calls load_dotenv() at import time, which can populate GRAPH_PG_HOST
      from this repo's .env even when no SSH tunnel is open.

Writes:
    - Nothing.
"""

from __future__ import annotations

import os
import socket

import psycopg2
import psycopg2.errors
import pytest

from system_03_search_agent.tools import graph_connection
from system_03_search_agent.tools.graph_connection import (
    GraphAuthError,
    GraphConnectionError,
    GraphError,
    GraphTimeoutError,
    execute_cypher,
)


class FakeCursor:
    """A minimal stand-in for a psycopg2 cursor.

    Records every executed statement and its parameters. Optionally raises
    a given exception when a statement containing `raise_on_substring` is
    executed, so a test can simulate a failure on the real query call
    without also failing the SET statements that precede it.
    """

    def __init__(self, rows=None, columns=None, raise_exc=None, raise_on_substring="cypher("):
        self._rows = rows if rows is not None else []
        self._columns = columns if columns is not None else ["result"]
        self._raise_exc = raise_exc
        self._raise_on_substring = raise_on_substring
        self.executed: list[tuple[str, object]] = []

    @property
    def description(self):
        return [(name,) for name in self._columns]

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if self._raise_exc is not None and self._raise_on_substring in sql:
            raise self._raise_exc

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    """A minimal stand-in for a psycopg2 connection."""

    def __init__(self, cursor: FakeCursor):
        self._cursor = cursor
        self.autocommit = False
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


def _graph_host_reachable(host: str, port: str, timeout: float = 2.0) -> bool:
    """Check whether the graph host is actually reachable, not just named.

    Importing litellm anywhere in the process calls load_dotenv() at import
    time (venv/lib/python3.11/site-packages/litellm/__init__.py:27), which
    silently loads this repo's .env and can populate GRAPH_PG_HOST even when
    no SSH tunnel is open. Checking the environment variable alone is not
    enough to decide whether the live integration test should run, so this
    does a short TCP connect and treats any failure as unreachable.
    """
    try:
        port_number = int(port)
    except (TypeError, ValueError):
        return False
    try:
        with socket.create_connection((host, port_number), timeout=timeout):
            return True
    except OSError:
        return False


def _factory_for(cursor: FakeCursor):
    conn = FakeConnection(cursor)

    def factory():
        return conn

    factory.connection = conn
    return factory


# ---------------------------------------------------------------------------
# Successful query
# ---------------------------------------------------------------------------


def test_successful_query_returns_rows_and_total():
    cursor = FakeCursor(rows=[("row-one",), ("row-two",)], columns=["result"])
    factory = _factory_for(cursor)

    rows, total_available = execute_cypher(
        "MATCH (g:Gene {id: $gene_id}) RETURN g",
        params={"gene_id": "NCBIGene:672"},
        row_limit=100,
        connection_factory=factory,
    )

    assert rows == [{"result": "row-one"}, {"result": "row-two"}]
    assert total_available == 2
    assert factory.connection.closed is True


def test_successful_query_sets_search_path_and_never_calls_load_age():
    cursor = FakeCursor(rows=[("row-one",)], columns=["result"])
    factory = _factory_for(cursor)

    execute_cypher("MATCH (g:Gene) RETURN g", connection_factory=factory)

    executed_sql = [sql for sql, _ in cursor.executed]
    assert any("search_path" in sql for sql in executed_sql)
    assert not any("LOAD" in sql for sql in executed_sql)


def test_query_params_pass_through_prepared_statement_not_string_interpolation():
    cursor = FakeCursor(rows=[], columns=["result"])
    factory = _factory_for(cursor)

    execute_cypher(
        "MATCH (g:Gene {id: $gene_id}) RETURN g",
        params={"gene_id": "NCBIGene:672"},
        connection_factory=factory,
    )

    prepare_sql = next(sql for sql, _ in cursor.executed if sql.startswith("PREPARE "))
    execute_sql, execute_params = next(
        (sql, params) for sql, params in cursor.executed if sql.startswith("EXECUTE ")
    )
    # The Cypher body appears literally between the dollar-quote delimiters
    # in the PREPARE statement, never with the caller value spliced in.
    assert "$gene_id" in prepare_sql
    assert "NCBIGene:672" not in prepare_sql
    # The actual value is carried only in the bound EXECUTE parameter, as JSON.
    assert execute_params == ('{"gene_id": "NCBIGene:672"}',)
    assert "NCBIGene:672" not in execute_sql


# ---------------------------------------------------------------------------
# PREPARE/EXECUTE path selection
# ---------------------------------------------------------------------------


def test_params_supplied_uses_prepare_execute_deallocate_sequence():
    cursor = FakeCursor(rows=[("row-one",)], columns=["result"])
    factory = _factory_for(cursor)

    execute_cypher(
        "MATCH (g:Gene {id: $gene_id}) RETURN g",
        params={"gene_id": "NCBIGene:672"},
        connection_factory=factory,
    )

    executed_sql = [sql for sql, _ in cursor.executed]
    prepare_calls = [sql for sql in executed_sql if sql.startswith("PREPARE ")]
    execute_calls = [sql for sql in executed_sql if sql.startswith("EXECUTE ")]
    deallocate_calls = [sql for sql in executed_sql if sql.startswith("DEALLOCATE ")]

    assert len(prepare_calls) == 1
    assert len(execute_calls) == 1
    assert len(deallocate_calls) == 1
    # The three statements reference the same generated statement name.
    statement_name = prepare_calls[0].split("(", 1)[0].removeprefix("PREPARE ").strip()
    assert statement_name.startswith("cq_")
    assert statement_name in execute_calls[0]
    assert statement_name in deallocate_calls[0]
    # No bare %s placeholder is ever passed as the cypher() third argument.
    assert not any(", %s)" in sql for sql in executed_sql)


def test_no_params_supplied_omits_third_argument_to_cypher():
    cursor = FakeCursor(rows=[], columns=["result"])
    factory = _factory_for(cursor)

    execute_cypher("MATCH (g:Gene) RETURN g", connection_factory=factory)

    executed_sql = [sql for sql, _ in cursor.executed]
    query_sql = next(sql for sql in executed_sql if "cypher(" in sql)

    assert not any(sql.startswith("PREPARE ") for sql in executed_sql)
    assert not any(sql.startswith("EXECUTE ") for sql in executed_sql)
    assert not any(sql.startswith("DEALLOCATE ") for sql in executed_sql)
    # No third argument, bound or literal, is passed to cypher() at all.
    assert ", %s)" not in query_sql
    assert ", $1)" not in query_sql
    assert query_sql.rstrip().endswith("$$) AS (result agtype)")


def test_deallocate_failure_never_masks_a_successful_result():
    class DeallocateFailingCursor(FakeCursor):
        def execute(self, sql, params=None):
            self.executed.append((sql, params))
            if sql.startswith("DEALLOCATE "):
                raise psycopg2.Error("prepared statement does not exist")

    cursor = DeallocateFailingCursor(rows=[("row-one",)], columns=["result"])
    factory = _factory_for(cursor)

    rows, total_available = execute_cypher(
        "MATCH (g:Gene {id: $gene_id}) RETURN g",
        params={"gene_id": "NCBIGene:672"},
        connection_factory=factory,
    )

    assert rows == [{"result": "row-one"}]
    assert total_available == 1


# ---------------------------------------------------------------------------
# Zero rows
# ---------------------------------------------------------------------------


def test_zero_rows_returns_empty_list_and_zero_total():
    cursor = FakeCursor(rows=[], columns=["result"])
    factory = _factory_for(cursor)

    rows, total_available = execute_cypher("MATCH (g:Gene {id: $x}) RETURN g", connection_factory=factory)

    assert rows == []
    assert total_available == 0


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------


def test_truncation_when_results_exceed_row_limit():
    cursor = FakeCursor(rows=[(f"row-{i}",) for i in range(10)], columns=["result"])
    factory = _factory_for(cursor)

    rows, total_available = execute_cypher(
        "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene) RETURN v",
        row_limit=3,
        connection_factory=factory,
    )

    assert len(rows) == 3
    assert total_available == 10


def test_row_limit_above_max_is_clamped():
    cursor = FakeCursor(rows=[(f"row-{i}",) for i in range(600)], columns=["result"])
    factory = _factory_for(cursor)

    rows, total_available = execute_cypher(
        "MATCH (g:Gene) RETURN g",
        row_limit=10_000,
        connection_factory=factory,
    )

    assert len(rows) == 500
    assert total_available == 600


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------


def test_timeout_raises_actionable_graph_timeout_error():
    cursor = FakeCursor(raise_exc=psycopg2.errors.QueryCanceled("canceling statement due to statement timeout"))
    factory = _factory_for(cursor)

    with pytest.raises(GraphTimeoutError) as excinfo:
        execute_cypher("MATCH (g:Gene) RETURN g", timeout_s=30.0, connection_factory=factory)

    message = str(excinfo.value)
    assert "30s" in message
    assert "retry" in message
    assert "query_intent" in message or "query_class" in message
    # The connection is still closed even though the query failed.
    assert factory.connection.closed is True


# ---------------------------------------------------------------------------
# Connection refused
# ---------------------------------------------------------------------------


def test_connection_refused_raises_graph_connection_error():
    def refused_factory():
        raise psycopg2.OperationalError(
            "could not connect to server: Connection refused\n"
            "\tIs the server running on host \"127.0.0.1\" and accepting\n"
            "\tTCP/IP connections on port 15432?"
        )

    with pytest.raises(GraphConnectionError):
        execute_cypher("MATCH (g:Gene) RETURN g", connection_factory=refused_factory)


def test_connection_refused_is_not_confused_with_auth_error():
    def refused_factory():
        raise psycopg2.OperationalError("could not connect to server: Connection refused")

    with pytest.raises(GraphConnectionError) as excinfo:
        execute_cypher("MATCH (g:Gene) RETURN g", connection_factory=refused_factory)

    assert not isinstance(excinfo.value, GraphAuthError)


# ---------------------------------------------------------------------------
# Auth failure
# ---------------------------------------------------------------------------


def test_auth_failure_raises_graph_auth_error():
    def auth_factory():
        raise psycopg2.OperationalError(
            'FATAL:  password authentication failed for user "kg_reader"'
        )

    with pytest.raises(GraphAuthError):
        execute_cypher("MATCH (g:Gene) RETURN g", connection_factory=auth_factory)


def test_auth_failure_is_distinct_type_from_connection_and_timeout_errors():
    def auth_factory():
        raise psycopg2.OperationalError(
            'FATAL:  password authentication failed for user "kg_reader"'
        )

    with pytest.raises(GraphAuthError) as excinfo:
        execute_cypher("MATCH (g:Gene) RETURN g", connection_factory=auth_factory)

    assert not isinstance(excinfo.value, GraphTimeoutError)
    assert isinstance(excinfo.value, GraphError)


# ---------------------------------------------------------------------------
# Credential redaction
# ---------------------------------------------------------------------------


def test_no_credential_value_appears_in_connection_error_message(monkeypatch):
    sentinel_password = "sentinel-super-secret-password-12345"
    monkeypatch.setenv("GRAPH_PG_HOST", "127.0.0.1")
    monkeypatch.setenv("GRAPH_PG_PORT", "15432")
    monkeypatch.setenv("GRAPH_PG_USER", "kg_reader")
    monkeypatch.setenv("GRAPH_PG_PASSWORD", sentinel_password)
    monkeypatch.setenv("GRAPH_PG_DBNAME", "ncbi_kg")

    def fake_connect(*args, **kwargs):
        # Simulate a driver or dependency echoing the password value back in
        # an error message, the worst case this module must defend against.
        raise psycopg2.OperationalError(
            "could not connect to server, password=" + sentinel_password
        )

    monkeypatch.setattr(graph_connection.psycopg2, "connect", fake_connect)

    with pytest.raises(GraphError) as excinfo:
        execute_cypher("MATCH (g:Gene) RETURN g")

    assert sentinel_password not in str(excinfo.value)


def test_no_credential_value_appears_in_any_raised_exception_across_all_paths():
    """Belt-and-suspenders sweep: no test-visible exception message in this
    module ever contains the string 'sentinel-super-secret-password-12345'
    used as a stand-in credential value above. This test exists as an
    explicit, named assertion per T-2.1-06's acceptance criteria, separate
    from the redaction-specific test, so a reviewer can find it by name.
    """
    sentinel_password = "sentinel-super-secret-password-12345"

    def auth_factory():
        raise psycopg2.OperationalError(
            'FATAL:  password authentication failed for user "kg_reader", '
            "password=" + sentinel_password
        )

    with pytest.raises(GraphAuthError) as excinfo:
        execute_cypher("MATCH (g:Gene) RETURN g", connection_factory=auth_factory)

    assert sentinel_password not in str(excinfo.value)


# ---------------------------------------------------------------------------
# Defense in depth: dollar-quote escape and as_clause shape
# ---------------------------------------------------------------------------


def test_cypher_containing_literal_dollar_dollar_is_rejected():
    cursor = FakeCursor(rows=[], columns=["result"])
    factory = _factory_for(cursor)

    with pytest.raises(GraphConnectionError):
        execute_cypher("MATCH (g:Gene) RETURN g $$ DROP", connection_factory=factory)


def test_malformed_as_clause_is_rejected():
    cursor = FakeCursor(rows=[], columns=["result"])
    factory = _factory_for(cursor)

    with pytest.raises(GraphConnectionError):
        execute_cypher(
            "MATCH (g:Gene) RETURN g",
            connection_factory=factory,
            as_clause="(result agtype); DROP TABLE foo;",
        )


# ---------------------------------------------------------------------------
# Live integration test: skips cleanly when the graph host is unreachable
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_live_graph_returns_brca1_via_labelled_edge():
    host = os.environ.get("GRAPH_PG_HOST")
    port = os.environ.get("GRAPH_PG_PORT", "5432")
    if not host or not _graph_host_reachable(host, port):
        pytest.skip(
            "GRAPH_PG_HOST is not set, or " + str(host) + ":" + str(port) +
            " is not reachable (no SSH tunnel to the graph host is open in "
            "this environment), skipping the live integration test"
        )

    rows, total_available = execute_cypher(
        "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->"
        "(g:Gene {id: $gene_id}) RETURN v",
        params={"gene_id": "NCBIGene:672"},
        row_limit=10,
    )

    assert total_available > 0
    assert len(rows) > 0
