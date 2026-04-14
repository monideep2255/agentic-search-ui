"""Tests for shared/validator.py - KGX output quality validation.

Depends on:
    - system-01-data-pipelines/shared/validator.py
    - pytest
"""

import pytest

from shared.validator import (
    validate_all,
    validate_no_dangling,
    validate_no_duplicates,
    validate_provenance,
)


@pytest.fixture()
def clean_node() -> dict:
    return {
        "id": "NCBIGene:672",
        "category": "biolink:Gene",
        "name": "BRCA1",
        "source": "NCBI Gene",
        "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
    }


@pytest.fixture()
def clean_edge() -> dict:
    return {
        "subject": "ClinVar:VCV000017599",
        "predicate": "biolink:is_sequence_variant_of",
        "object": "NCBIGene:672",
        "source": "ClinVar",
        "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/17599/",
    }


class TestValidateNoDangling:
    def test_returns_empty_list_when_no_dangling(self, clean_edge):
        """validate_no_dangling returns [] when all edge endpoints are in node_ids."""
        node_ids = {"ClinVar:VCV000017599", "NCBIGene:672"}
        result = validate_no_dangling([clean_edge], node_ids)
        assert result == []

    def test_finds_dangling_subject(self, clean_edge):
        """validate_no_dangling includes edge when subject is missing from node_ids."""
        node_ids = {"NCBIGene:672"}  # subject is missing
        result = validate_no_dangling([clean_edge], node_ids)
        assert len(result) == 1
        assert result[0] == clean_edge

    def test_finds_dangling_object(self, clean_edge):
        """validate_no_dangling includes edge when object is missing from node_ids."""
        node_ids = {"ClinVar:VCV000017599"}  # object is missing
        result = validate_no_dangling([clean_edge], node_ids)
        assert len(result) == 1
        assert result[0] == clean_edge

    def test_returns_empty_list_for_no_edges(self):
        """validate_no_dangling returns [] when edges list is empty."""
        result = validate_no_dangling([], node_ids={"NCBIGene:672"})
        assert result == []

    def test_multiple_dangling_edges(self):
        """validate_no_dangling returns all edges with missing endpoints."""
        edges = [
            {"subject": "A:1", "predicate": "biolink:subclass_of", "object": "B:1"},
            {"subject": "A:2", "predicate": "biolink:subclass_of", "object": "B:2"},
        ]
        node_ids = {"A:1"}  # B:1 missing, and all of A:2 / B:2 missing
        result = validate_no_dangling(edges, node_ids)
        assert len(result) == 2


class TestValidateNoDuplicates:
    def test_returns_empty_list_when_no_duplicates(self, clean_node):
        """validate_no_duplicates returns [] when all node ids are unique."""
        nodes = [clean_node, {**clean_node, "id": "NCBIGene:675"}]
        result = validate_no_duplicates(nodes)
        assert result == []

    def test_finds_duplicate_ids(self):
        """validate_no_duplicates returns the duplicated id value."""
        nodes = [
            {"id": "NCBIGene:672", "name": "BRCA1"},
            {"id": "NCBIGene:672", "name": "BRCA1 duplicate"},
        ]
        result = validate_no_duplicates(nodes)
        assert result == ["NCBIGene:672"]

    def test_returns_empty_list_for_empty_input(self):
        """validate_no_duplicates returns [] when nodes list is empty."""
        result = validate_no_duplicates([])
        assert result == []

    def test_checks_custom_key(self):
        """validate_no_duplicates respects a custom key argument."""
        nodes = [
            {"id": "NCBIGene:672", "name": "BRCA1"},
            {"id": "NCBIGene:675", "name": "BRCA1"},
        ]
        result = validate_no_duplicates(nodes, key="name")
        assert result == ["BRCA1"]


class TestValidateProvenance:
    def test_returns_empty_list_when_all_have_provenance(self, clean_node):
        """validate_provenance returns [] when all records have source and source_url."""
        result = validate_provenance([clean_node])
        assert result == []

    def test_catches_missing_source(self):
        """validate_provenance flags records with missing source."""
        record = {"id": "NCBIGene:672", "source": "", "source_url": "https://example.com"}
        result = validate_provenance([record])
        assert len(result) == 1
        assert result[0] == record

    def test_catches_missing_source_url(self):
        """validate_provenance flags records with missing source_url."""
        record = {"id": "NCBIGene:672", "source": "NCBI Gene", "source_url": ""}
        result = validate_provenance([record])
        assert len(result) == 1
        assert result[0] == record

    def test_catches_absent_keys(self):
        """validate_provenance flags records where source/source_url keys are absent."""
        record = {"id": "NCBIGene:672"}
        result = validate_provenance([record])
        assert len(result) == 1

    def test_returns_empty_list_for_empty_input(self):
        """validate_provenance returns [] when records list is empty."""
        result = validate_provenance([])
        assert result == []


class TestValidateAll:
    def _make_node(self, node_id: str) -> dict:
        return {
            "id": node_id,
            "category": "biolink:Gene",
            "name": "Gene",
            "source": "NCBI Gene",
            "source_url": f"https://www.ncbi.nlm.nih.gov/gene/{node_id.split(':')[1]}",
        }

    def _make_edge(self, subject: str, obj: str) -> dict:
        return {
            "subject": subject,
            "predicate": "biolink:is_sequence_variant_of",
            "object": obj,
            "source": "ClinVar",
            "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/1/",
        }

    def test_passed_true_when_everything_is_clean(self):
        """validate_all returns passed=True when all validation checks pass."""
        nodes = [self._make_node("NCBIGene:672"), self._make_node("NCBIGene:675")]
        edges = [self._make_edge("NCBIGene:672", "NCBIGene:675")]
        result = validate_all(nodes, edges)

        assert result["passed"] is True
        assert result["dangling_edges"] == []
        assert result["duplicate_nodes"] == []
        assert result["missing_provenance_nodes"] == []
        assert result["missing_provenance_edges"] == []

    def test_passed_false_when_dangling_edge_exists(self):
        """validate_all returns passed=False when there is a dangling edge."""
        nodes = [self._make_node("NCBIGene:672")]
        edges = [self._make_edge("NCBIGene:672", "NCBIGene:MISSING")]
        result = validate_all(nodes, edges)

        assert result["passed"] is False
        assert len(result["dangling_edges"]) == 1

    def test_passed_false_when_duplicate_node_exists(self):
        """validate_all returns passed=False when duplicate node ids exist."""
        nodes = [self._make_node("NCBIGene:672"), self._make_node("NCBIGene:672")]
        edges = []
        result = validate_all(nodes, edges)

        assert result["passed"] is False
        assert "NCBIGene:672" in result["duplicate_nodes"]

    def test_passed_false_when_provenance_missing_on_node(self):
        """validate_all returns passed=False when a node is missing provenance."""
        node_bad = {"id": "NCBIGene:672", "category": "biolink:Gene", "name": "BRCA1", "source": "", "source_url": ""}
        result = validate_all([node_bad], [])

        assert result["passed"] is False
        assert len(result["missing_provenance_nodes"]) == 1

    def test_result_dict_has_all_expected_keys(self):
        """validate_all always returns a dict with all five expected keys."""
        result = validate_all([], [])
        expected_keys = {
            "dangling_edges",
            "duplicate_nodes",
            "missing_provenance_nodes",
            "missing_provenance_edges",
            "passed",
        }
        assert set(result.keys()) == expected_keys
