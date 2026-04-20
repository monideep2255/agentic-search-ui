"""conftest.py - Inline KGX fixtures for AGE loader unit tests.

No network access. No Docker. All data is written to tmp_path.
Covers 5 nodes across 4 vertex labels and 3 edges across 3 predicates.

Depends on:
    - pytest
    - stdlib: csv, pathlib
"""
# SAMPLE_CURIE_TO_ID maps every CURIE in SAMPLE_NODES to a fake AGE graphid.
# Used by edge loader tests so that _flush_edge_batch() can resolve endpoints.
SAMPLE_CURIE_TO_ID = {
    "NCBIGene:672": "1001",
    "NCBIGene:675": "1002",
    "ClinVar:12345": "1003",
    "MONDO:0007254": "1004",
    "NCBITaxon:9606": "1005",
}

import csv

import pytest
from pathlib import Path


SAMPLE_NODES = [
    {
        "id": "NCBIGene:672",
        "category": "biolink:Gene",
        "name": "BRCA1",
        "source": "NCBI Gene",
        "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
        "xrefs": "HGNC:1100",
        "knowledge_level": "knowledge_assertion",
        "agent_type": "manual_agent",
    },
    {
        "id": "NCBIGene:675",
        "category": "biolink:Gene",
        "name": "BRCA2",
        "source": "NCBI Gene",
        "source_url": "https://www.ncbi.nlm.nih.gov/gene/675",
        "xrefs": "",
        "knowledge_level": "knowledge_assertion",
        "agent_type": "manual_agent",
    },
    {
        "id": "ClinVar:12345",
        "category": "biolink:SequenceVariant",
        "name": "NM_007294.4:c.1A>G",
        "source": "ClinVar",
        "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/12345",
        "xrefs": "",
        "knowledge_level": "knowledge_assertion",
        "agent_type": "manual_agent",
    },
    {
        "id": "MONDO:0007254",
        "category": "biolink:Disease",
        "name": "breast cancer",
        "source": "MedGen",
        "source_url": "https://www.ncbi.nlm.nih.gov/medgen/336867",
        "xrefs": "UMLS:C0006142",
        "knowledge_level": "knowledge_assertion",
        "agent_type": "manual_agent",
    },
    {
        "id": "NCBITaxon:9606",
        "category": "biolink:OrganismTaxon",
        "name": "Homo sapiens",
        "source": "NCBI Taxonomy",
        "source_url": "https://www.ncbi.nlm.nih.gov/taxonomy/9606",
        "xrefs": "",
        "knowledge_level": "knowledge_assertion",
        "agent_type": "manual_agent",
    },
]

SAMPLE_EDGES = [
    {
        "subject": "NCBIGene:672",
        "predicate": "biolink:gene_associated_with_condition",
        "object": "MONDO:0007254",
        "source": "ClinVar",
        "source_url": "https://www.ncbi.nlm.nih.gov/clinvar",
        "knowledge_level": "knowledge_assertion",
        "agent_type": "manual_agent",
    },
    {
        "subject": "ClinVar:12345",
        "predicate": "biolink:is_sequence_variant_of",
        "object": "NCBIGene:672",
        "source": "ClinVar",
        "source_url": "https://www.ncbi.nlm.nih.gov/clinvar",
        "knowledge_level": "knowledge_assertion",
        "agent_type": "manual_agent",
    },
    {
        "subject": "NCBIGene:672",
        "predicate": "biolink:in_taxon",
        "object": "NCBITaxon:9606",
        "source": "NCBI Gene",
        "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
        "knowledge_level": "knowledge_assertion",
        "agent_type": "manual_agent",
    },
]


@pytest.fixture
def sample_nodes() -> list[dict]:
    """Return SAMPLE_NODES as a plain list of dicts."""
    return SAMPLE_NODES


@pytest.fixture
def sample_edges() -> list[dict]:
    """Return SAMPLE_EDGES as a plain list of dicts."""
    return SAMPLE_EDGES


@pytest.fixture
def sample_curie_to_id() -> dict:
    """Return SAMPLE_CURIE_TO_ID as a plain dict.

    Maps every CURIE in SAMPLE_NODES to a fake AGE graphid integer.
    Pass to load_edges() or _flush_edge_batch() in unit tests that
    need endpoint resolution without a live database.
    """
    return dict(SAMPLE_CURIE_TO_ID)


@pytest.fixture(scope="module")
def kgx_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Write both TSVs into a single temp directory and return the path.

    Module-scoped so module-scoped fixtures in test_age_smoke.py
    (age_container, loaded_graph) can depend on it without ScopeMismatch.

    Both nodes.tsv and edges.tsv are written into the same directory so that
    run_age_load(kgx_dir, ...) finds both files under the same parent path.
    Previously the two fixtures used separate mktemp() calls, which produced
    kgx0/nodes.tsv and kgx1/edges.tsv — a different parent for each file —
    causing FileNotFoundError when pipeline.py looked for edges.tsv under
    nodes_tsv.parent.
    """
    d = tmp_path_factory.mktemp("kgx")

    nodes_path = d / "nodes.tsv"
    with open(nodes_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=list(SAMPLE_NODES[0].keys()), delimiter="\t"
        )
        writer.writeheader()
        writer.writerows(SAMPLE_NODES)

    edges_path = d / "edges.tsv"
    with open(edges_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=list(SAMPLE_EDGES[0].keys()), delimiter="\t"
        )
        writer.writeheader()
        writer.writerows(SAMPLE_EDGES)

    return d


@pytest.fixture(scope="module")
def nodes_tsv(kgx_dir: Path) -> Path:
    """Return the path to nodes.tsv inside kgx_dir."""
    return kgx_dir / "nodes.tsv"


@pytest.fixture(scope="module")
def edges_tsv(kgx_dir: Path) -> Path:
    """Return the path to edges.tsv inside kgx_dir."""
    return kgx_dir / "edges.tsv"
