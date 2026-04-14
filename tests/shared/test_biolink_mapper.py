"""Tests for shared/biolink_mapper.py - BioLink node/edge mapping and CURIE validation.

Depends on:
    - system-01-data-pipelines/shared/biolink_mapper.py
    - pytest
"""

import pytest

from shared.biolink_mapper import (
    VALID_CATEGORIES,
    VALID_PREDICATES,
    map_edge,
    map_node,
    validate_curie,
)


class TestRegistries:
    def test_valid_categories_has_ten_entries(self):
        """VALID_CATEGORIES contains exactly 10 BioLink category strings."""
        assert len(VALID_CATEGORIES) == 10

    def test_valid_predicates_has_fourteen_entries(self):
        """VALID_PREDICATES contains exactly 14 BioLink predicate strings."""
        assert len(VALID_PREDICATES) == 14

    def test_categories_are_biolink_prefixed(self):
        """All VALID_CATEGORIES entries start with 'biolink:'."""
        for cat in VALID_CATEGORIES:
            assert cat.startswith("biolink:"), f"Expected biolink: prefix on {cat}"

    def test_predicates_are_biolink_prefixed(self):
        """All VALID_PREDICATES entries start with 'biolink:'."""
        for pred in VALID_PREDICATES:
            assert pred.startswith("biolink:"), f"Expected biolink: prefix on {pred}"


class TestMapNode:
    def test_returns_correct_dict_with_required_fields(self):
        """map_node returns a dict containing all five required provenance fields."""
        node = map_node(
            id="NCBIGene:672",
            category="biolink:Gene",
            name="BRCA1",
            source="NCBI Gene",
            source_url="https://www.ncbi.nlm.nih.gov/gene/672",
        )
        assert node["id"] == "NCBIGene:672"
        assert node["category"] == "biolink:Gene"
        assert node["name"] == "BRCA1"
        assert node["source"] == "NCBI Gene"
        assert node["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/672"

    def test_extra_kwargs_included_in_output(self):
        """map_node passes extra keyword arguments through verbatim."""
        node = map_node(
            id="NCBIGene:672",
            category="biolink:Gene",
            name="BRCA1",
            source="NCBI Gene",
            source_url="https://www.ncbi.nlm.nih.gov/gene/672",
            xrefs=["HGNC:1100", "OMIM:113705"],
            description="Breast cancer type 1 susceptibility protein",
        )
        assert node["xrefs"] == ["HGNC:1100", "OMIM:113705"]
        assert node["description"] == "Breast cancer type 1 susceptibility protein"

    def test_raises_on_invalid_category(self):
        """map_node raises ValueError when category is not in VALID_CATEGORIES."""
        with pytest.raises(ValueError, match="invalid category"):
            map_node(
                id="NCBIGene:672",
                category="biolink:Protein",  # not in registry
                name="BRCA1",
                source="NCBI Gene",
                source_url="https://www.ncbi.nlm.nih.gov/gene/672",
            )

    def test_raises_on_empty_source_url(self):
        """map_node raises ValueError when source_url is empty."""
        with pytest.raises(ValueError, match="source_url"):
            map_node(
                id="NCBIGene:672",
                category="biolink:Gene",
                name="BRCA1",
                source="NCBI Gene",
                source_url="",
            )

    def test_raises_on_empty_id(self):
        """map_node raises ValueError when id is empty."""
        with pytest.raises(ValueError, match="'id'"):
            map_node(
                id="",
                category="biolink:Gene",
                name="BRCA1",
                source="NCBI Gene",
                source_url="https://www.ncbi.nlm.nih.gov/gene/672",
            )

    def test_raises_on_empty_name(self):
        """map_node raises ValueError when name is empty."""
        with pytest.raises(ValueError, match="'name'"):
            map_node(
                id="NCBIGene:672",
                category="biolink:Gene",
                name="",
                source="NCBI Gene",
                source_url="https://www.ncbi.nlm.nih.gov/gene/672",
            )


class TestMapEdge:
    def test_returns_correct_dict_with_required_fields(self):
        """map_edge returns a dict containing all five required provenance fields."""
        edge = map_edge(
            subject="ClinVar:VCV000017599",
            predicate="biolink:is_sequence_variant_of",
            object="NCBIGene:672",
            source="ClinVar",
            source_url="https://www.ncbi.nlm.nih.gov/clinvar/variation/17599/",
        )
        assert edge["subject"] == "ClinVar:VCV000017599"
        assert edge["predicate"] == "biolink:is_sequence_variant_of"
        assert edge["object"] == "NCBIGene:672"
        assert edge["source"] == "ClinVar"
        assert edge["source_url"] == "https://www.ncbi.nlm.nih.gov/clinvar/variation/17599/"

    def test_raises_on_invalid_predicate(self):
        """map_edge raises ValueError when predicate is not in VALID_PREDICATES."""
        with pytest.raises(ValueError, match="invalid predicate"):
            map_edge(
                subject="ClinVar:VCV000017599",
                predicate="biolink:causes",  # not in registry
                object="NCBIGene:672",
                source="ClinVar",
                source_url="https://www.ncbi.nlm.nih.gov/clinvar/variation/17599/",
            )

    def test_raises_on_empty_source(self):
        """map_edge raises ValueError when source is empty."""
        with pytest.raises(ValueError, match="'source'"):
            map_edge(
                subject="ClinVar:VCV000017599",
                predicate="biolink:is_sequence_variant_of",
                object="NCBIGene:672",
                source="",
                source_url="https://www.ncbi.nlm.nih.gov/clinvar/variation/17599/",
            )

    def test_extra_kwargs_included_in_output(self):
        """map_edge passes extra keyword arguments through verbatim."""
        edge = map_edge(
            subject="ClinVar:VCV000017599",
            predicate="biolink:is_sequence_variant_of",
            object="NCBIGene:672",
            source="ClinVar",
            source_url="https://www.ncbi.nlm.nih.gov/clinvar/variation/17599/",
            clinical_significance="Pathogenic",
        )
        assert edge["clinical_significance"] == "Pathogenic"


class TestValidateCurie:
    def test_returns_true_for_valid_curie(self):
        """validate_curie returns True for a well-formed CURIE."""
        assert validate_curie("NCBIGene:672") is True

    def test_returns_true_for_biolink_curie(self):
        """validate_curie returns True for a biolink: CURIE."""
        assert validate_curie("biolink:Gene") is True

    def test_returns_false_when_no_colon(self):
        """validate_curie returns False when string contains no colon."""
        assert validate_curie("NCBIGene672") is False

    def test_returns_false_when_empty_prefix(self):
        """validate_curie returns False when the prefix is empty (:localid)."""
        assert validate_curie(":672") is False

    def test_returns_false_when_empty_local_id(self):
        """validate_curie returns False when the local ID is empty (prefix:)."""
        assert validate_curie("NCBIGene:") is False

    def test_returns_false_for_empty_string(self):
        """validate_curie returns False for an empty string."""
        assert validate_curie("") is False

    def test_returns_false_for_multiple_colons(self):
        """validate_curie returns False when there are more than one colon."""
        assert validate_curie("foo:bar:baz") is False

    def test_returns_false_for_non_string(self):
        """validate_curie returns False when input is not a string."""
        assert validate_curie(None) is False
        assert validate_curie(672) is False
