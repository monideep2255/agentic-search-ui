"""Tests for shared/kgx_exporter.py - KGX TSV export.

Depends on:
    - system-01-data-pipelines/shared/kgx_exporter.py
    - pytest, csv (stdlib)
"""

import csv
from pathlib import Path

import pytest

from shared.kgx_exporter import (
    NODE_REQUIRED_COLUMNS,
    EDGE_REQUIRED_COLUMNS,
    export_edges,
    export_kgx,
    export_nodes,
)


@pytest.fixture()
def gene_node() -> dict:
    return {
        "id": "NCBIGene:672",
        "category": "biolink:Gene",
        "name": "BRCA1",
        "source": "NCBI Gene",
        "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
    }


@pytest.fixture()
def variant_edge() -> dict:
    return {
        "subject": "ClinVar:VCV000017599",
        "predicate": "biolink:is_sequence_variant_of",
        "object": "NCBIGene:672",
        "source": "ClinVar",
        "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/17599/",
    }


def _read_tsv(path: Path) -> tuple[list[str], list[dict]]:
    """Helper: return (header_list, rows_as_dicts) from a TSV file."""
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    return list(fieldnames), rows


class TestExportNodes:
    def test_writes_tsv_with_required_columns(self, tmp_path, gene_node):
        """export_nodes writes a TSV file containing all required node columns."""
        path = export_nodes([gene_node], tmp_path, "gene")
        header, rows = _read_tsv(path)

        for col in NODE_REQUIRED_COLUMNS:
            assert col in header
        assert len(rows) == 1
        assert rows[0]["id"] == "NCBIGene:672"

    def test_required_columns_appear_first(self, tmp_path, gene_node):
        """export_nodes puts required columns before any extra columns."""
        node = {**gene_node, "description": "a gene"}
        path = export_nodes([node], tmp_path, "gene")
        header, _ = _read_tsv(path)

        for i, col in enumerate(NODE_REQUIRED_COLUMNS):
            assert header[i] == col

    def test_creates_subdirectory(self, tmp_path, gene_node):
        """export_nodes creates output_dir/database/ if it does not exist."""
        path = export_nodes([gene_node], tmp_path, "new_db")
        assert (tmp_path / "new_db").is_dir()
        assert path == tmp_path / "new_db" / "nodes.tsv"

    def test_multivalued_fields_are_pipe_joined(self, tmp_path, gene_node):
        """export_nodes joins list values with pipe for known multivalued fields."""
        node = {**gene_node, "xref": ["HGNC:1100", "OMIM:113705"]}
        path = export_nodes([node], tmp_path, "gene")
        _, rows = _read_tsv(path)
        assert rows[0]["xref"] == "HGNC:1100|OMIM:113705"

    def test_missing_optional_fields_are_empty_string(self, tmp_path):
        """export_nodes writes empty string for fields missing in some records."""
        node1 = {
            "id": "NCBIGene:672",
            "category": "biolink:Gene",
            "name": "BRCA1",
            "source": "NCBI Gene",
            "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
            "description": "a gene",
        }
        node2 = {
            "id": "NCBIGene:675",
            "category": "biolink:Gene",
            "name": "BRCA2",
            "source": "NCBI Gene",
            "source_url": "https://www.ncbi.nlm.nih.gov/gene/675",
        }
        path = export_nodes([node1, node2], tmp_path, "gene")
        _, rows = _read_tsv(path)
        assert rows[1]["description"] == ""


class TestExportEdges:
    def test_writes_tsv_with_required_columns(self, tmp_path, variant_edge):
        """export_edges writes a TSV file containing all required edge columns."""
        path = export_edges([variant_edge], tmp_path, "clinvar")
        header, rows = _read_tsv(path)

        for col in EDGE_REQUIRED_COLUMNS:
            assert col in header
        assert len(rows) == 1

    def test_creates_subdirectory(self, tmp_path, variant_edge):
        """export_edges creates output_dir/database/ and returns correct path."""
        path = export_edges([variant_edge], tmp_path, "clinvar")
        assert (tmp_path / "clinvar").is_dir()
        assert path == tmp_path / "clinvar" / "edges.tsv"

    def test_required_columns_appear_first(self, tmp_path, variant_edge):
        """export_edges puts required edge columns before any extra columns."""
        edge = {**variant_edge, "clinical_significance": "Pathogenic"}
        path = export_edges([edge], tmp_path, "clinvar")
        header, _ = _read_tsv(path)

        for i, col in enumerate(EDGE_REQUIRED_COLUMNS):
            assert header[i] == col

    def test_multivalued_supporting_publications_pipe_joined(self, tmp_path, variant_edge):
        """export_edges joins supporting_publications list with pipe."""
        edge = {**variant_edge, "supporting_publications": ["PMID:12345", "PMID:67890"]}
        path = export_edges([edge], tmp_path, "clinvar")
        _, rows = _read_tsv(path)
        assert rows[0]["supporting_publications"] == "PMID:12345|PMID:67890"


class TestExportKgx:
    def test_returns_both_paths(self, tmp_path, gene_node, variant_edge):
        """export_kgx returns a tuple of (nodes_path, edges_path)."""
        nodes_path, edges_path = export_kgx([gene_node], [variant_edge], tmp_path, "gene")
        assert nodes_path.name == "nodes.tsv"
        assert edges_path.name == "edges.tsv"
        assert nodes_path.exists()
        assert edges_path.exists()

    def test_both_files_under_same_database_directory(self, tmp_path, gene_node, variant_edge):
        """export_kgx places both files under output_dir/database/."""
        nodes_path, edges_path = export_kgx([gene_node], [variant_edge], tmp_path, "gene")
        assert nodes_path.parent == tmp_path / "gene"
        assert edges_path.parent == tmp_path / "gene"
