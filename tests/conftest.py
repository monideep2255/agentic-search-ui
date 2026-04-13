"""Shared fixtures for the agentic-search-data-engineering test suite.

Depends on:
    - schema/biolink_ncbi.yaml (schema fixture points here)
    - pytest (test runner)
"""

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def sample_node_dict() -> dict[str, str | list[str]]:
    """Return a valid BioLink Gene node with all required fields."""
    return {
        "id": "NCBIGene:672",
        "category": "biolink:Gene",
        "name": "BRCA1",
        "source": "NCBI Gene",
        "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
        "xrefs": ["HGNC:1100", "OMIM:113705"],
    }


@pytest.fixture()
def sample_edge_dict() -> dict[str, str]:
    """Return a valid BioLink edge with all required fields."""
    return {
        "subject": "ClinVar:VCV000017599",
        "predicate": "biolink:is_sequence_variant_of",
        "object": "NCBIGene:672",
        "source": "ClinVar",
        "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/17599/",
    }


@pytest.fixture()
def tmp_output_dir(tmp_path: Path) -> Path:
    """Return a temporary directory for KGX output."""
    output = tmp_path / "kgx_output"
    output.mkdir()
    return output


@pytest.fixture()
def schema_path() -> Path:
    """Return the path to schema/biolink_ncbi.yaml."""
    return REPO_ROOT / "schema" / "biolink_ncbi.yaml"
