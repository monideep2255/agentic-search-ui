"""test_age_loader.py - Unit tests for the AGE loader modules.

All tests use mocked psycopg2. No live database required. No Docker.

Test coverage:
    connect_age:
        - sets autocommit=True on the connection
        - executes LOAD 'age'
        - executes SET search_path

    schema:
        - create_graph calls SELECT create_graph(...) with the graph name
        - create_graph is idempotent (DuplicateTable does not propagate)
        - create_vertex_labels calls create_vlabel for each label
        - create_edge_label calls create_elabel with graph name and label

    node_loader:
        - load_nodes reads nodes_tsv and executes direct INSERT SQL
        - load_nodes returns the correct count
        - load_nodes handles an empty TSV without error
        - _flush_node_batch SQL contains INSERT INTO with graph and label names

    edge_loader:
        - load_edges reads edges_tsv and executes direct INSERT SQL
        - load_edges returns the correct count
        - _build_curie_id_map builds CURIE->graphid dict from vertex tables
        - edges with missing endpoints are skipped (logged warning)

    index_builder:
        - create_indexes calls CREATE INDEX for each vertex label

    pipeline:
        - run_age_load calls all five steps in order
        - run_age_load returns {"nodes": N, "edges": M} with correct counts
        - run_age_load passes curie_to_id kwarg to load_edges

Depends on:
    - system-02-knowledge-graph/loader/connection.py
    - system-02-knowledge-graph/loader/schema.py
    - system-02-knowledge-graph/loader/node_loader.py
    - system-02-knowledge-graph/loader/edge_loader.py
    - system-02-knowledge-graph/loader/index_builder.py
    - system-02-knowledge-graph/loader/pipeline.py
    - tests/loader/conftest.py
    - stdlib: unittest.mock
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import psycopg2.errors
import pytest

# Make the loader package importable from test context (mirrors the sys.path
# approach used in tests/gene/test_gene_pipeline.py).
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "system-02-knowledge-graph"))

from loader.connection import connect_age
from loader.edge_loader import _build_curie_id_map, load_edges
from loader.index_builder import create_indexes
from loader.node_loader import load_nodes
from loader.pipeline import run_age_load
from loader.schema import (
    EDGE_LABELS,
    VERTEX_LABELS,
    create_edge_label,
    create_graph,
    create_vertex_labels,
)
from tests.loader.conftest import SAMPLE_CURIE_TO_ID


# ---------------------------------------------------------------------------
# connect_age
# ---------------------------------------------------------------------------


class TestConnectAge:
    """Tests for connect_age in connection.py."""

    def _make_mock_conn(self) -> MagicMock:
        """Return a mock psycopg2 connection with a cursor context manager."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return mock_conn

    def test_autocommit_set_to_true(self) -> None:
        """connect_age sets connection.autocommit = True."""
        mock_conn = self._make_mock_conn()
        with patch("psycopg2.connect", return_value=mock_conn):
            connect_age("host=localhost dbname=test")
        assert mock_conn.autocommit is True

    def test_autocommit_false_when_requested(self) -> None:
        """connect_age respects autocommit=False."""
        mock_conn = self._make_mock_conn()
        with patch("psycopg2.connect", return_value=mock_conn):
            connect_age("host=localhost dbname=test", autocommit=False)
        assert mock_conn.autocommit is False

    def test_load_age_executed(self) -> None:
        """connect_age executes LOAD 'age'."""
        mock_conn = self._make_mock_conn()
        mock_cur = mock_conn.cursor.return_value.__enter__.return_value
        with patch("psycopg2.connect", return_value=mock_conn):
            connect_age("host=localhost dbname=test")
        executed_stmts = [c.args[0] for c in mock_cur.execute.call_args_list]
        assert any("LOAD" in s and "age" in s for s in executed_stmts)

    def test_set_search_path_executed(self) -> None:
        """connect_age executes SET search_path including ag_catalog."""
        mock_conn = self._make_mock_conn()
        mock_cur = mock_conn.cursor.return_value.__enter__.return_value
        with patch("psycopg2.connect", return_value=mock_conn):
            connect_age("host=localhost dbname=test")
        executed_stmts = [c.args[0] for c in mock_cur.execute.call_args_list]
        assert any("search_path" in s and "ag_catalog" in s for s in executed_stmts)

    def test_returns_connection(self) -> None:
        """connect_age returns the connection object."""
        mock_conn = self._make_mock_conn()
        with patch("psycopg2.connect", return_value=mock_conn):
            result = connect_age("host=localhost dbname=test")
        assert result is mock_conn


# ---------------------------------------------------------------------------
# schema — create_graph
# ---------------------------------------------------------------------------


class TestCreateGraph:
    """Tests for create_graph in schema.py."""

    def test_calls_create_graph_with_name(self) -> None:
        """create_graph calls SELECT create_graph(%s) with the graph name."""
        mock_cur = MagicMock()
        create_graph(mock_cur, "test_graph")
        mock_cur.execute.assert_called_once_with(
            "SELECT create_graph(%s);", ("test_graph",)
        )

    def test_idempotent_duplicate_table(self) -> None:
        """create_graph does not raise when AGE raises DuplicateTable."""
        mock_cur = MagicMock()
        mock_cur.execute.side_effect = psycopg2.errors.DuplicateTable("already exists")
        # Should not raise
        create_graph(mock_cur, "test_graph")
        mock_cur.connection.rollback.assert_called_once()

    def test_idempotent_generic_already_exists(self) -> None:
        """create_graph does not raise on generic DatabaseError with 'already exists'."""
        mock_cur = MagicMock()
        mock_cur.execute.side_effect = psycopg2.DatabaseError("already exists")
        # Should not raise
        create_graph(mock_cur, "test_graph")
        mock_cur.connection.rollback.assert_called_once()

    def test_propagates_unexpected_db_error(self) -> None:
        """create_graph re-raises unexpected DatabaseError."""
        mock_cur = MagicMock()
        mock_cur.execute.side_effect = psycopg2.DatabaseError("disk full")
        with pytest.raises(psycopg2.DatabaseError, match="disk full"):
            create_graph(mock_cur, "test_graph")


# ---------------------------------------------------------------------------
# schema — create_vertex_labels
# ---------------------------------------------------------------------------


class TestCreateVertexLabels:
    """Tests for create_vertex_labels in schema.py."""

    def test_calls_create_vlabel_for_each_label(self) -> None:
        """create_vertex_labels calls create_vlabel for every label supplied."""
        mock_cur = MagicMock()
        labels = ["Gene", "Disease", "SequenceVariant"]
        create_vertex_labels(mock_cur, "test_graph", labels)
        executed = [c.args[0] for c in mock_cur.execute.call_args_list]
        # Each call should reference create_vlabel
        assert all("create_vlabel" in s for s in executed)
        assert len(executed) == len(labels)

    def test_all_vertex_labels_constant_covered(self) -> None:
        """VERTEX_LABELS has exactly 11 entries (10 BioLink categories plus NamedThing for stub endpoints)."""
        assert len(VERTEX_LABELS) == 11

    def test_vertex_labels_are_strings(self) -> None:
        """Every entry in VERTEX_LABELS is a non-empty string."""
        assert all(isinstance(lbl, str) and lbl for lbl in VERTEX_LABELS)


# ---------------------------------------------------------------------------
# schema — create_edge_label
# ---------------------------------------------------------------------------


class TestCreateEdgeLabel:
    """Tests for create_edge_label in schema.py."""

    def test_calls_create_elabel_with_graph_and_label(self) -> None:
        """create_edge_label calls SELECT create_elabel(graph_name, label)."""
        mock_cur = MagicMock()
        create_edge_label(mock_cur, "test_graph", "in_taxon")
        mock_cur.execute.assert_called_once_with(
            "SELECT create_elabel(%s, %s);", ("test_graph", "in_taxon")
        )

    def test_idempotent_duplicate_table(self) -> None:
        """create_edge_label does not raise when label already exists."""
        mock_cur = MagicMock()
        mock_cur.execute.side_effect = psycopg2.errors.DuplicateTable("already exists")
        # Should not raise
        create_edge_label(mock_cur, "test_graph", "in_taxon")
        mock_cur.connection.rollback.assert_called_once()

    def test_all_edge_labels_constant_covered(self) -> None:
        """EDGE_LABELS has exactly 14 entries."""
        assert len(EDGE_LABELS) == 14


# ---------------------------------------------------------------------------
# node_loader
# ---------------------------------------------------------------------------


class TestLoadNodes:
    """Tests for load_nodes in node_loader.py."""

    def test_returns_correct_count(self, nodes_tsv: Path) -> None:
        """load_nodes returns the number of rows in nodes.tsv."""
        mock_cur = MagicMock()
        count = load_nodes(mock_cur, "test_graph", nodes_tsv, batch_size=500)
        assert count == 5

    def test_executes_insert_sql(self, nodes_tsv: Path) -> None:
        """load_nodes calls cur.execute with direct INSERT SQL."""
        mock_cur = MagicMock()
        load_nodes(mock_cur, "test_graph", nodes_tsv, batch_size=500)
        assert mock_cur.execute.call_count >= 1
        # Every execute call must use direct INSERT, not cypher()
        for c in mock_cur.execute.call_args_list:
            sql = c.args[0]
            assert "INSERT INTO" in sql
            assert "cypher" not in sql.lower()

    def test_insert_sql_includes_graph_and_label(self, nodes_tsv: Path) -> None:
        """load_nodes INSERT SQL contains both the graph name and vertex label."""
        mock_cur = MagicMock()
        load_nodes(mock_cur, "test_graph", nodes_tsv, batch_size=500)
        sqls = [c.args[0] for c in mock_cur.execute.call_args_list]
        # Gene label must appear (2 gene nodes in fixture)
        assert any('"Gene"' in sql for sql in sqls)
        assert any('"test_graph"' in sql for sql in sqls)

    def test_batch_flushing(self, nodes_tsv: Path) -> None:
        """load_nodes flushes multiple batches when batch_size < row count."""
        mock_cur = MagicMock()
        # batch_size=2 with 5 rows across 4 labels forces multiple flushes
        count = load_nodes(mock_cur, "test_graph", nodes_tsv, batch_size=2)
        assert count == 5
        # At least 3 execute calls expected (5 rows / 2 per batch, rounded up)
        assert mock_cur.execute.call_count >= 3
        # All execute calls must use direct INSERT
        for c in mock_cur.execute.call_args_list:
            sql = c.args[0]
            assert "INSERT INTO" in sql

    def test_empty_tsv_returns_zero(self, tmp_path: Path) -> None:
        """load_nodes returns 0 and does not error on an empty TSV."""
        import csv as csv_mod

        empty_tsv = tmp_path / "nodes.tsv"
        fieldnames = ["id", "category", "name", "source", "source_url", "xrefs",
                      "knowledge_level", "agent_type"]
        with open(empty_tsv, "w", newline="") as f:
            writer = csv_mod.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
            writer.writeheader()
            # No data rows

        mock_cur = MagicMock()
        count = load_nodes(mock_cur, "test_graph", empty_tsv)
        assert count == 0
        mock_cur.execute.assert_not_called()

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        """load_nodes raises FileNotFoundError when nodes.tsv does not exist."""
        mock_cur = MagicMock()
        missing = tmp_path / "missing_nodes.tsv"
        with pytest.raises(FileNotFoundError):
            load_nodes(mock_cur, "test_graph", missing)


# ---------------------------------------------------------------------------
# edge_loader
# ---------------------------------------------------------------------------


class TestLoadEdges:
    """Tests for load_edges in edge_loader.py."""

    def test_returns_correct_count(self, edges_tsv: Path) -> None:
        """load_edges returns the number of edges actually inserted (all 3 in fixture)."""
        mock_cur = MagicMock()
        count = load_edges(
            mock_cur,
            "test_graph",
            edges_tsv,
            batch_size=500,
            curie_to_id=dict(SAMPLE_CURIE_TO_ID),
        )
        assert count == 3

    def test_executes_insert_sql(self, edges_tsv: Path) -> None:
        """load_edges calls cur.execute with direct INSERT SQL."""
        mock_cur = MagicMock()
        load_edges(
            mock_cur,
            "test_graph",
            edges_tsv,
            batch_size=500,
            curie_to_id=dict(SAMPLE_CURIE_TO_ID),
        )
        assert mock_cur.execute.call_count >= 1
        for c in mock_cur.execute.call_args_list:
            sql = c.args[0]
            assert "INSERT INTO" in sql
            assert "cypher" not in sql.lower()

    def test_missing_endpoint_skips_edge(self, edges_tsv: Path) -> None:
        """load_edges skips edges whose endpoints are not in curie_to_id."""
        mock_cur = MagicMock()
        # Provide a map that omits MONDO:0007254 (the object of edge 1)
        partial_map = {k: v for k, v in SAMPLE_CURIE_TO_ID.items() if k != "MONDO:0007254"}
        count = load_edges(
            mock_cur,
            "test_graph",
            edges_tsv,
            batch_size=500,
            curie_to_id=partial_map,
        )
        # Edge 1 (NCBIGene:672 -> MONDO:0007254) should be skipped; 2 inserted
        assert count == 2

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        """load_edges raises FileNotFoundError when edges.tsv does not exist."""
        mock_cur = MagicMock()
        missing = tmp_path / "missing_edges.tsv"
        with pytest.raises(FileNotFoundError):
            load_edges(mock_cur, "test_graph", missing, curie_to_id=dict(SAMPLE_CURIE_TO_ID))

    def test_empty_tsv_returns_zero(self, tmp_path: Path) -> None:
        """load_edges returns 0 and does not error on an empty TSV."""
        import csv as csv_mod

        empty_tsv = tmp_path / "edges.tsv"
        fieldnames = ["subject", "predicate", "object", "source", "source_url",
                      "knowledge_level", "agent_type"]
        with open(empty_tsv, "w", newline="") as f:
            writer = csv_mod.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
            writer.writeheader()

        mock_cur = MagicMock()
        count = load_edges(
            mock_cur,
            "test_graph",
            empty_tsv,
            curie_to_id=dict(SAMPLE_CURIE_TO_ID),
        )
        assert count == 0
        mock_cur.execute.assert_not_called()


class TestBuildCurieIdMap:
    """Tests for _build_curie_id_map in edge_loader.py."""

    def test_builds_correct_map(self) -> None:
        """_build_curie_id_map returns a dict mapping CURIE strings to graphid strings."""
        mock_cur = MagicMock()
        # Simulate two vertex label tables: Gene and Disease.
        # fetchall returns [(graphid, curie_str), ...] where graphid is the raw
        # AGE graphid value (Python represents it as int from psycopg2).
        mock_cur.fetchall.side_effect = [
            [(1001, "NCBIGene:672"), (1002, "NCBIGene:675")],
            [(1004, "MONDO:0007254")],
        ]
        result = _build_curie_id_map(mock_cur, "test_graph", ["Gene", "Disease"])
        # Values are stored as strings for use in %s::agtype::graphid INSERT params.
        assert result == {
            "NCBIGene:672": "1001",
            "NCBIGene:675": "1002",
            "MONDO:0007254": "1004",
        }

    def test_queries_each_label_table(self) -> None:
        """_build_curie_id_map executes one SELECT per vertex label."""
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = []
        labels = ["Gene", "Disease", "SequenceVariant"]
        _build_curie_id_map(mock_cur, "test_graph", labels)
        assert mock_cur.execute.call_count == len(labels)
        # Each SQL must reference the graph name (schema) and the label (table)
        for i, c in enumerate(mock_cur.execute.call_args_list):
            sql = c.args[0]
            assert '"test_graph"' in sql
            assert f'"{labels[i]}"' in sql

    def test_skips_rows_with_null_curie(self) -> None:
        """_build_curie_id_map skips rows where the CURIE is None or empty."""
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [
            (1001, "NCBIGene:672"),
            (1002, None),
            (1003, ""),
        ]
        result = _build_curie_id_map(mock_cur, "test_graph", ["Gene"])
        # Only the row with a non-empty CURIE should be included; value is a string.
        assert result == {"NCBIGene:672": "1001"}

    def test_returns_empty_dict_for_empty_labels(self) -> None:
        """_build_curie_id_map returns {} when vertex_labels is empty."""
        mock_cur = MagicMock()
        result = _build_curie_id_map(mock_cur, "test_graph", [])
        assert result == {}
        mock_cur.execute.assert_not_called()


# ---------------------------------------------------------------------------
# index_builder
# ---------------------------------------------------------------------------


class TestCreateIndexes:
    """Tests for create_indexes in index_builder.py."""

    def test_calls_create_index_for_each_label(self) -> None:
        """create_indexes calls cur.execute once per vertex label."""
        mock_cur = MagicMock()
        labels = ["Gene", "Disease"]
        create_indexes(mock_cur, "test_graph", labels)
        assert mock_cur.execute.call_count == len(labels)

    def test_sql_contains_create_index_if_not_exists(self) -> None:
        """Each create_indexes call uses CREATE INDEX IF NOT EXISTS."""
        mock_cur = MagicMock()
        create_indexes(mock_cur, "test_graph", ["Gene"])
        sql = mock_cur.execute.call_args[0][0]
        assert "CREATE INDEX IF NOT EXISTS" in sql

    def test_sql_references_vertex_label_table(self) -> None:
        """The index DDL targets the correct per-label table."""
        mock_cur = MagicMock()
        create_indexes(mock_cur, "test_graph", ["Gene"])
        sql = mock_cur.execute.call_args[0][0]
        assert '"test_graph"' in sql
        assert '"Gene"' in sql

    def test_index_name_includes_graph_and_label(self) -> None:
        """Index name contains both sanitized graph name and label."""
        mock_cur = MagicMock()
        create_indexes(mock_cur, "my_graph", ["MyLabel"])
        sql = mock_cur.execute.call_args[0][0]
        # Index name should contain 'my_graph' and 'mylabel' (lowercased)
        assert "my_graph" in sql.lower()
        assert "mylabel" in sql.lower()


# ---------------------------------------------------------------------------
# pipeline — run_age_load
# ---------------------------------------------------------------------------


class TestRunAgeLoad:
    """Tests for run_age_load in pipeline.py."""

    def _patch_all(self, mock_conn: MagicMock, node_count: int = 5, edge_count: int = 3):
        """Return a dict of patches covering all pipeline dependencies."""
        return {
            "connect_age": patch(
                "loader.pipeline.connect_age",
                return_value=mock_conn,
            ),
            "create_graph": patch(
                "loader.pipeline.create_graph"
            ),
            "create_vertex_labels": patch(
                "loader.pipeline.create_vertex_labels"
            ),
            "create_edge_label": patch(
                "loader.pipeline.create_edge_label"
            ),
            "load_nodes": patch(
                "loader.pipeline.load_nodes",
                return_value=node_count,
            ),
            "_build_curie_id_map": patch(
                "loader.pipeline._build_curie_id_map",
                return_value=dict(SAMPLE_CURIE_TO_ID),
            ),
            "load_edges": patch(
                "loader.pipeline.load_edges",
                return_value=edge_count,
            ),
            "create_indexes": patch(
                "loader.pipeline.create_indexes"
            ),
        }

    def test_returns_correct_node_and_edge_counts(self, kgx_dir: Path) -> None:
        """run_age_load returns {'nodes': N, 'edges': M} with correct counts."""
        mock_conn = MagicMock()
        patches = self._patch_all(mock_conn, node_count=5, edge_count=3)
        with (
            patches["connect_age"],
            patches["create_graph"],
            patches["create_vertex_labels"],
            patches["create_edge_label"],
            patches["load_nodes"],
            patches["_build_curie_id_map"],
            patches["load_edges"],
            patches["create_indexes"],
        ):
            result = run_age_load(kgx_dir, "test_graph", "host=localhost")
        assert result == {"nodes": 5, "edges": 3}

    def test_connect_age_called_with_dsn(self, kgx_dir: Path) -> None:
        """run_age_load passes the DSN to connect_age."""
        mock_conn = MagicMock()
        patches = self._patch_all(mock_conn)
        with (
            patches["connect_age"] as mock_connect,
            patches["create_graph"],
            patches["create_vertex_labels"],
            patches["create_edge_label"],
            patches["load_nodes"],
            patches["_build_curie_id_map"],
            patches["load_edges"],
            patches["create_indexes"],
        ):
            run_age_load(kgx_dir, "test_graph", "host=myhost dbname=mydb")
        mock_connect.assert_called_once_with("host=myhost dbname=mydb")

    def test_create_graph_called(self, kgx_dir: Path) -> None:
        """run_age_load calls create_graph with the graph name."""
        mock_conn = MagicMock()
        patches = self._patch_all(mock_conn)
        with (
            patches["connect_age"],
            patches["create_graph"] as mock_cg,
            patches["create_vertex_labels"],
            patches["create_edge_label"],
            patches["load_nodes"],
            patches["_build_curie_id_map"],
            patches["load_edges"],
            patches["create_indexes"],
        ):
            run_age_load(kgx_dir, "test_graph", "host=localhost")
        mock_cg.assert_called_once()
        assert mock_cg.call_args[0][1] == "test_graph"

    def test_load_nodes_called_with_nodes_tsv(self, kgx_dir: Path) -> None:
        """run_age_load passes {kgx_dir}/nodes.tsv to load_nodes."""
        mock_conn = MagicMock()
        patches = self._patch_all(mock_conn)
        with (
            patches["connect_age"],
            patches["create_graph"],
            patches["create_vertex_labels"],
            patches["create_edge_label"],
            patches["load_nodes"] as mock_ln,
            patches["_build_curie_id_map"],
            patches["load_edges"],
            patches["create_indexes"],
        ):
            run_age_load(kgx_dir, "test_graph", "host=localhost")
        assert mock_ln.call_args[0][2] == kgx_dir / "nodes.tsv"

    def test_load_edges_called_with_edges_tsv(self, kgx_dir: Path) -> None:
        """run_age_load passes {kgx_dir}/edges.tsv to load_edges."""
        mock_conn = MagicMock()
        patches = self._patch_all(mock_conn)
        with (
            patches["connect_age"],
            patches["create_graph"],
            patches["create_vertex_labels"],
            patches["create_edge_label"],
            patches["load_nodes"],
            patches["_build_curie_id_map"],
            patches["load_edges"] as mock_le,
            patches["create_indexes"],
        ):
            run_age_load(kgx_dir, "test_graph", "host=localhost")
        assert mock_le.call_args[0][2] == kgx_dir / "edges.tsv"

    def test_load_edges_receives_curie_to_id_kwarg(self, kgx_dir: Path) -> None:
        """run_age_load passes the curie_to_id kwarg to load_edges."""
        mock_conn = MagicMock()
        patches = self._patch_all(mock_conn)
        with (
            patches["connect_age"],
            patches["create_graph"],
            patches["create_vertex_labels"],
            patches["create_edge_label"],
            patches["load_nodes"],
            patches["_build_curie_id_map"],
            patches["load_edges"] as mock_le,
            patches["create_indexes"],
        ):
            run_age_load(kgx_dir, "test_graph", "host=localhost")
        # curie_to_id must be passed as a keyword argument
        assert "curie_to_id" in mock_le.call_args.kwargs
        assert mock_le.call_args.kwargs["curie_to_id"] == SAMPLE_CURIE_TO_ID

    def test_drop_existing_executes_drop_graph(self, kgx_dir: Path) -> None:
        """run_age_load calls SELECT drop_graph() when drop_existing=True.

        AGE uses drop_graph(name, cascade) as a SQL function, not a DDL statement.
        The pipeline executes: SELECT drop_graph(%s, true);
        """
        mock_conn = MagicMock()
        mock_cur = mock_conn.cursor.return_value
        patches = self._patch_all(mock_conn)
        with (
            patches["connect_age"],
            patches["create_graph"],
            patches["create_vertex_labels"],
            patches["create_edge_label"],
            patches["load_nodes"],
            patches["_build_curie_id_map"],
            patches["load_edges"],
            patches["create_indexes"],
        ):
            run_age_load(kgx_dir, "test_graph", "host=localhost", drop_existing=True)
        executed = [str(c.args[0]) for c in mock_cur.execute.call_args_list]
        assert any("drop_graph" in s for s in executed)

    def test_no_drop_when_drop_existing_false(self, kgx_dir: Path) -> None:
        """run_age_load does NOT call drop_graph() when drop_existing=False."""
        mock_conn = MagicMock()
        mock_cur = mock_conn.cursor.return_value
        patches = self._patch_all(mock_conn)
        with (
            patches["connect_age"],
            patches["create_graph"],
            patches["create_vertex_labels"],
            patches["create_edge_label"],
            patches["load_nodes"],
            patches["_build_curie_id_map"],
            patches["load_edges"],
            patches["create_indexes"],
        ):
            run_age_load(kgx_dir, "test_graph", "host=localhost", drop_existing=False)
        executed = [str(c.args[0]) for c in mock_cur.execute.call_args_list]
        assert not any("drop_graph" in s for s in executed)

    def test_batch_size_forwarded_to_loaders(self, kgx_dir: Path) -> None:
        """run_age_load forwards batch_size to load_nodes and load_edges."""
        mock_conn = MagicMock()
        patches = self._patch_all(mock_conn)
        with (
            patches["connect_age"],
            patches["create_graph"],
            patches["create_vertex_labels"],
            patches["create_edge_label"],
            patches["load_nodes"] as mock_ln,
            patches["_build_curie_id_map"],
            patches["load_edges"] as mock_le,
            patches["create_indexes"],
        ):
            run_age_load(kgx_dir, "test_graph", "host=localhost", batch_size=250)
        # batch_size is passed positionally (index 3) by pipeline.py
        assert mock_ln.call_args[0][3] == 250
        assert mock_le.call_args[0][3] == 250

    def test_create_indexes_called_after_load(self, kgx_dir: Path) -> None:
        """run_age_load calls create_indexes after loading nodes and edges."""
        call_order: list[str] = []
        mock_conn = MagicMock()

        def record(name: str):
            def fn(*args, **kwargs):
                call_order.append(name)
                if name in ("load_nodes", "load_edges"):
                    return 0
                if name == "_build_curie_id_map":
                    return {}
            return fn

        with (
            patch("loader.pipeline.connect_age", return_value=mock_conn),
            patch("loader.pipeline.create_graph", side_effect=record("create_graph")),
            patch("loader.pipeline.create_vertex_labels", side_effect=record("create_vertex_labels")),
            patch("loader.pipeline.create_edge_label", side_effect=record("create_edge_label")),
            patch("loader.pipeline.load_nodes", side_effect=record("load_nodes")),
            patch("loader.pipeline._build_curie_id_map", side_effect=record("_build_curie_id_map")),
            patch("loader.pipeline.load_edges", side_effect=record("load_edges")),
            patch("loader.pipeline.create_indexes", side_effect=record("create_indexes")),
        ):
            run_age_load(kgx_dir, "test_graph", "host=localhost")

        assert call_order.index("load_nodes") < call_order.index("create_indexes")
        assert call_order.index("load_edges") < call_order.index("create_indexes")
        # curie_to_id map must be built between node load and edge load
        assert call_order.index("load_nodes") < call_order.index("_build_curie_id_map")
        assert call_order.index("_build_curie_id_map") < call_order.index("load_edges")
