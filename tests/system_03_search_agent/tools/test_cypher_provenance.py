"""Tests for Layer 1 provenance and source URL mapping (T-2.1-05).

Depends on:
    - system_03_search_agent.tools.cypher_provenance
      (source_url_for_curie, to_output_row)
    - system_03_search_agent.tools.graph_schema_constants
      (CURIE_PREFIXES, used only to assert every documented prefix in the
      graph is covered by a test, never to duplicate the mapping logic
      under test)
"""

from __future__ import annotations

import pytest

from system_03_search_agent.tools.cypher_provenance import (
    source_url_for_curie,
    to_output_row,
)
from system_03_search_agent.tools.graph_schema_constants import CURIE_PREFIXES

# ---------------------------------------------------------------------------
# The five prefixes with a documented NCBI record page.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("curie", "expected_url"),
    [
        ("NCBIGene:672", "https://www.ncbi.nlm.nih.gov/gene/672"),
        ("ClinVar:17660", "https://www.ncbi.nlm.nih.gov/clinvar/variation/17660/"),
        ("MedGen:C0031485", "https://www.ncbi.nlm.nih.gov/medgen/C0031485"),
        ("PMID:34567890", "https://pubmed.ncbi.nlm.nih.gov/34567890/"),
        (
            "NCBITaxon:9606",
            "https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=9606",
        ),
    ],
)
def test_documented_prefix_maps_to_expected_ncbi_record_url(
    curie: str, expected_url: str
) -> None:
    assert source_url_for_curie(curie) == expected_url


# ---------------------------------------------------------------------------
# The four prefixes with no NCBI-hosted record page: GO, MeSH, HP, MONDO.
# Returning None here is the correct, documented behavior, not a gap: none
# of the four is an NCBI database, so no host-pinned URL can be built
# without fabricating one.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("curie", ["GO:0006096", "MeSH:D012345", "HP:0001250", "MONDO:0009861"])
def test_non_ncbi_ontology_prefix_returns_none(curie: str) -> None:
    assert source_url_for_curie(curie) is None


def test_every_curie_prefix_in_the_graph_schema_is_covered_by_a_test() -> None:
    # Guards against a tenth prefix being added to CURIE_PREFIXES with no
    # corresponding test above, either in the documented-mapping test or
    # the non-NCBI-ontology test.
    documented = {"NCBIGene", "ClinVar", "MedGen", "PMID", "NCBITaxon"}
    non_ncbi = {"GO", "MeSH", "HP", "MONDO"}

    assert documented | non_ncbi == set(CURIE_PREFIXES)
    assert len(CURIE_PREFIXES) == 9


# ---------------------------------------------------------------------------
# An unrecognized prefix, outside the graph's nine entirely.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "curie",
    ["UNKNOWNPREFIX:123", "OMIM:600123", "", "NoColonAtAll", ":123", "NCBIGene:"],
)
def test_unrecognized_or_malformed_curie_returns_none(curie: str) -> None:
    assert source_url_for_curie(curie) is None


def test_url_encodes_the_local_id() -> None:
    # A local id with a character that needs encoding must not break the
    # constructed URL's path structure.
    url = source_url_for_curie("NCBIGene:67 2")
    assert url == "https://www.ncbi.nlm.nih.gov/gene/67%202"


def test_local_id_cannot_escape_the_pinned_host_via_path_traversal() -> None:
    url = source_url_for_curie("NCBIGene:../../evil.example")
    assert url is not None
    assert url.startswith("https://www.ncbi.nlm.nih.gov/gene/")
    assert "evil.example" not in url or "%2F" in url


# ---------------------------------------------------------------------------
# to_output_row: stored-URL passthrough and foreign-host discard.
# ---------------------------------------------------------------------------


def test_to_output_row_keeps_a_valid_stored_source_url() -> None:
    raw_row = {
        "label": "Gene",
        "id": "NCBIGene:672",
        "properties": {"symbol": "BRCA1"},
        "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
    }

    row = to_output_row(raw_row, snapshot_version="2026-07-01")

    assert row["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/672"
    assert row["node_or_edge_type"] == "Gene"
    assert row["curie"] == "NCBIGene:672"
    assert row["fields"] == {"symbol": "BRCA1"}
    assert row["graph_snapshot_version"] == "2026-07-01"


def test_to_output_row_discards_a_stored_source_url_on_a_foreign_host() -> None:
    raw_row = {
        "label": "Gene",
        "id": "NCBIGene:672",
        "properties": {"symbol": "BRCA1"},
        "source_url": "https://evil.example/gene/672",
    }

    row = to_output_row(raw_row, snapshot_version="2026-07-01")

    # The foreign-host URL is discarded, never passed through, and the
    # module falls back to deriving a fresh URL from the CURIE.
    assert row["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/672"


def test_to_output_row_falls_back_to_none_when_no_valid_url_can_be_derived() -> None:
    raw_row = {
        "label": "OntologyClass",
        "id": "GO:0006096",
        "properties": {"name": "glycolytic process"},
        "source_url": "https://evil.example/go/0006096",
    }

    row = to_output_row(raw_row, snapshot_version="2026-07-01")

    # No documented NCBI mapping for GO, and the stored URL is a foreign
    # host, so the row correctly carries no fabricated source_url.
    assert row["source_url"] is None
    assert row["curie"] == "GO:0006096"


def test_to_output_row_derives_url_when_no_stored_url_present() -> None:
    raw_row = {
        "label": "SequenceVariant",
        "id": "ClinVar:17660",
        "properties": {},
    }

    row = to_output_row(raw_row, snapshot_version="2026-07-01")

    assert row["source_url"] == "https://www.ncbi.nlm.nih.gov/clinvar/variation/17660/"


def test_to_output_row_accepts_node_or_edge_type_and_curie_keys_directly() -> None:
    raw_row = {
        "node_or_edge_type": "Gene",
        "curie": "NCBIGene:672",
        "fields": {"symbol": "BRCA1"},
    }

    row = to_output_row(raw_row, snapshot_version="2026-07-01")

    assert row["node_or_edge_type"] == "Gene"
    assert row["curie"] == "NCBIGene:672"
    assert row["fields"] == {"symbol": "BRCA1"}


def test_to_output_row_always_returns_exactly_the_five_expected_keys() -> None:
    raw_row = {"label": "Gene", "id": "NCBIGene:672", "properties": {}}

    row = to_output_row(raw_row, snapshot_version="2026-07-01")

    assert set(row.keys()) == {
        "node_or_edge_type",
        "curie",
        "fields",
        "source_url",
        "graph_snapshot_version",
    }
