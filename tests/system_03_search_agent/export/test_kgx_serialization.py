"""Unit tests for the KGX TSV serialization in kgx.py (T-4.4-03).

These cover the shapes the premise gate deliberately does not exercise
(`tests/system_03_search_agent/export/test_kgx_export_premise.py`'s own
module docstring): a property value carrying a tab, a newline, or a
double quote, a list-valued property, a zero-row export, extra columns
sorted after the required ones, and a row missing a column. None of these
need the live graph: they exercise `kgx.py`'s pure TSV-writing functions
directly against hand-built row dicts.
"""

from __future__ import annotations

import csv
from pathlib import Path

from system_03_search_agent.export import kgx


def _read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = list(reader.fieldnames or [])
        return fieldnames, list(reader)


class TestSerializeValue:
    def test_list_is_pipe_joined(self) -> None:
        assert kgx.serialize_value(["HGNC:1100", "OMIM:113705"]) == "HGNC:1100|OMIM:113705"

    def test_tuple_is_pipe_joined(self) -> None:
        assert kgx.serialize_value(("a", "b", "c")) == "a|b|c"

    def test_none_becomes_empty_string(self) -> None:
        assert kgx.serialize_value(None) == ""

    def test_plain_scalar_is_stringified(self) -> None:
        assert kgx.serialize_value(672) == "672"
        assert kgx.serialize_value("NCBIGene:672") == "NCBIGene:672"

    def test_empty_list_becomes_empty_string(self) -> None:
        assert kgx.serialize_value([]) == ""


class TestFieldnameOrdering:
    def test_extra_columns_sorted_alphabetically_after_required(self) -> None:
        records = [
            {"id": "a", "xrefs": "x", "knowledge_level": "y", "agent_type": "z"},
            {"id": "b", "zzz_custom": "w"},
        ]
        fieldnames = kgx._build_fieldnames(records, kgx.NODE_REQUIRED_COLUMNS)
        assert fieldnames[: len(kgx.NODE_REQUIRED_COLUMNS)] == kgx.NODE_REQUIRED_COLUMNS
        extra = fieldnames[len(kgx.NODE_REQUIRED_COLUMNS) :]
        assert extra == sorted(extra)
        assert set(extra) == {"agent_type", "knowledge_level", "xrefs", "zzz_custom"}

    def test_no_extra_columns_when_records_carry_only_required_keys(self) -> None:
        records = [{"id": "a", "category": "biolink:Gene", "name": "", "source": "", "source_url": ""}]
        fieldnames = kgx._build_fieldnames(records, kgx.NODE_REQUIRED_COLUMNS)
        assert fieldnames == kgx.NODE_REQUIRED_COLUMNS


class TestWriteTsv:
    def test_zero_row_export_still_writes_header(self, tmp_path: Path) -> None:
        path = kgx._write_tsv([], tmp_path / "nodes.tsv", kgx.NODE_REQUIRED_COLUMNS)
        fieldnames, rows = _read_tsv(path)
        assert fieldnames == kgx.NODE_REQUIRED_COLUMNS
        assert rows == []

    def test_zero_row_edges_export_still_writes_header(self, tmp_path: Path) -> None:
        path = kgx._write_tsv([], tmp_path / "edges.tsv", kgx.EDGE_REQUIRED_COLUMNS)
        fieldnames, rows = _read_tsv(path)
        assert fieldnames == kgx.EDGE_REQUIRED_COLUMNS
        assert rows == []

    def test_a_row_missing_a_column_is_written_empty_not_shifted(self, tmp_path: Path) -> None:
        # The second record has no "name" key at all, unlike the first,
        # which is exactly the "a row missing a column" case: the missing
        # field must land as an empty string in the "name" column, never
        # shift every later column left by one.
        records = [
            {"id": "NCBIGene:1", "category": "biolink:Gene", "name": "GENE1",
             "source": "NCBI Gene", "source_url": "https://www.ncbi.nlm.nih.gov/gene/1"},
            {"id": "NCBIGene:2", "category": "biolink:Gene",
             "source": "NCBI Gene", "source_url": "https://www.ncbi.nlm.nih.gov/gene/2"},
        ]
        path = kgx._write_tsv(records, tmp_path / "nodes.tsv", kgx.NODE_REQUIRED_COLUMNS)
        fieldnames, rows = _read_tsv(path)
        assert fieldnames == kgx.NODE_REQUIRED_COLUMNS
        second = next(r for r in rows if r["id"] == "NCBIGene:2")
        assert second["name"] == ""
        assert second["source"] == "NCBI Gene"
        assert second["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/2"

    def test_tab_newline_and_quote_round_trip_without_shifting_a_row(self, tmp_path: Path) -> None:
        hostile_name = 'a name with a "quote", a\ttab, and a\nnewline'
        records = [
            {"id": "NCBIGene:9", "category": "biolink:Gene", "name": hostile_name,
             "source": "NCBI Gene", "source_url": "https://www.ncbi.nlm.nih.gov/gene/9"},
            {"id": "NCBIGene:10", "category": "biolink:Gene", "name": "ordinary",
             "source": "NCBI Gene", "source_url": "https://www.ncbi.nlm.nih.gov/gene/10"},
        ]
        path = kgx._write_tsv(records, tmp_path / "nodes.tsv", kgx.NODE_REQUIRED_COLUMNS)
        fieldnames, rows = _read_tsv(path)

        assert fieldnames == kgx.NODE_REQUIRED_COLUMNS
        assert len(rows) == 2
        hostile_row = next(r for r in rows if r["id"] == "NCBIGene:9")
        ordinary_row = next(r for r in rows if r["id"] == "NCBIGene:10")

        # The row was not split or shifted: every column still holds
        # exactly what it should, including the hostile one round-tripping
        # byte for byte.
        assert hostile_row["name"] == hostile_name
        assert hostile_row["source"] == "NCBI Gene"
        assert hostile_row["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/9"
        assert ordinary_row["name"] == "ordinary"
        assert ordinary_row["id"] == "NCBIGene:10"

    def test_list_valued_property_is_pipe_joined_on_disk(self, tmp_path: Path) -> None:
        records = [
            {"id": "NCBIGene:1", "category": "biolink:Gene", "name": "G1",
             "source": "NCBI Gene", "source_url": "https://www.ncbi.nlm.nih.gov/gene/1",
             "xrefs": ["HGNC:1", "OMIM:2"]},
        ]
        path = kgx._write_tsv(records, tmp_path / "nodes.tsv", kgx.NODE_REQUIRED_COLUMNS)
        _, rows = _read_tsv(path)
        assert rows[0]["xrefs"] == "HGNC:1|OMIM:2"


class TestResolveSourceUrl:
    def test_keeps_a_valid_host_pinned_stored_url(self) -> None:
        stored = "https://www.ncbi.nlm.nih.gov/gene/672"
        assert kgx._resolve_source_url("NCBIGene:672", stored) == stored

    def test_discards_a_stored_url_on_a_foreign_host_and_derives_instead(self) -> None:
        stored = "https://evil.example/gene/672"
        resolved = kgx._resolve_source_url("NCBIGene:672", stored)
        assert resolved == "https://www.ncbi.nlm.nih.gov/gene/672"

    def test_returns_none_for_an_unmapped_prefix_with_no_stored_url(self) -> None:
        assert kgx._resolve_source_url("GO:0008150", None) is None

    def test_returns_none_when_curie_is_empty(self) -> None:
        assert kgx._resolve_source_url("", None) is None
        assert kgx._resolve_source_url(None, None) is None


class TestNodeAndEdgeRowShaping:
    def test_node_row_maps_label_to_biolink_category_and_carries_extras(self) -> None:
        entity = {
            "id": 12345,
            "label": "Gene",
            "properties": {
                "id": "NCBIGene:7157",
                "name": "TP53",
                "source": "NCBI Gene",
                "source_url": "https://www.ncbi.nlm.nih.gov/gene/7157",
                "xrefs": "HGNC:11998",
                "agent_type": "",
                "knowledge_level": "",
            },
        }
        row, is_empty = kgx._node_row("NCBIGene:7157", entity)
        assert row["id"] == "NCBIGene:7157"
        assert row["category"] == "biolink:Gene"
        assert row["name"] == "TP53"
        assert row["source"] == "NCBI Gene"
        assert row["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/7157"
        assert row["xrefs"] == "HGNC:11998"
        assert is_empty is False

    def test_node_row_reports_empty_source_url_for_an_unmapped_prefix(self) -> None:
        entity = {
            "id": 1,
            "label": "OntologyClass",
            "properties": {"id": "GO:0008150", "name": "biological_process", "source": "GO"},
        }
        row, is_empty = kgx._node_row("GO:0008150", entity)
        assert row["source_url"] == ""
        assert is_empty is True

    def test_edge_row_maps_label_to_biolink_predicate_and_uses_attached_curies(self) -> None:
        edge_entity = {
            "id": 999,
            "label": "gene_associated_with_condition",
            "start_id": 1,
            "end_id": 2,
            "subject_curie": "NCBIGene:7157",
            "object_curie": "MedGen:C0205770",
            "properties": {
                "source": "NCBI MIM2Gene",
                "source_url": "https://www.ncbi.nlm.nih.gov/gene/7157",
                "agent_type": "manual_agent",
                "knowledge_level": "knowledge_assertion",
            },
        }
        row, is_empty = kgx._edge_row(edge_entity)
        assert row["subject"] == "NCBIGene:7157"
        assert row["predicate"] == "biolink:gene_associated_with_condition"
        assert row["object"] == "MedGen:C0205770"
        assert row["knowledge_level"] == "knowledge_assertion"
        assert row["agent_type"] == "manual_agent"
        assert is_empty is False

    def test_edge_row_with_no_stored_or_derivable_url_is_counted_empty(self) -> None:
        edge_entity = {
            "id": 1000,
            "label": "close_match",
            "start_id": 1,
            "end_id": 2,
            "subject_curie": "GO:0008150",
            "object_curie": "GO:0008151",
            "properties": {"source": "GO", "source_url": ""},
        }
        row, is_empty = kgx._edge_row(edge_entity)
        assert row["source_url"] == ""
        assert is_empty is True


class TestRowsFromTraversal:
    def test_empty_traversal_result_produces_empty_row_lists(self) -> None:
        from system_03_search_agent.export.traversal import TraversalResult

        result = TraversalResult(
            nodes={},
            edges=[],
            seeds_requested=["NCBIGene:99999999"],
            seeds_resolved=[],
            hops=1,
            max_nodes=500,
            max_edges=1000,
            time_budget_s=60.0,
            elapsed_s=0.01,
            truncated=False,
            truncation=[],
            empty_reason="0 of 1 requested seed CURIE(s) resolved",
        )
        node_rows, edge_rows, empty_count = kgx.rows_from_traversal(result)
        assert node_rows == []
        assert edge_rows == []
        assert empty_count == 0
