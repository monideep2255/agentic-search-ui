"""Integration tests for the merge and validation pipeline.

Uses small inline fixtures written to tmp_path. No network access, no FTP.

Depends on:
    - system-01-data-pipelines/shared/merger.py
    - system-01-data-pipelines/shared/merge_report.py
    - system-01-data-pipelines/shared/validator.py
"""

import csv
from pathlib import Path

import pytest

from shared.merger import (
    inject_stubs,
    load_kgx_edges,
    load_kgx_nodes,
    merge_kgx,
    validate_merge,
)
from shared.merge_report import generate_merge_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_nodes(path: Path, rows: list[dict]) -> Path:
    """Write a minimal nodes.tsv to path."""
    if not rows:
        rows = []
    fieldnames = ["id", "category", "name", "source", "source_url"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore", restval="")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_edges(path: Path, rows: list[dict]) -> Path:
    """Write a minimal edges.tsv to path."""
    fieldnames = ["subject", "predicate", "object", "source", "source_url"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore", restval="")
        writer.writeheader()
        writer.writerows(rows)
    return path


# ---------------------------------------------------------------------------
# load_kgx_nodes
# ---------------------------------------------------------------------------

def test_load_kgx_nodes(tmp_path: Path) -> None:
    nodes_path = tmp_path / "nodes.tsv"
    _write_nodes(nodes_path, [
        {"id": "NCBIGene:672", "category": "biolink:Gene", "name": "BRCA1",
         "source": "ncbi_gene", "source_url": "https://www.ncbi.nlm.nih.gov/gene/672"},
    ])

    rows = load_kgx_nodes(nodes_path)

    assert len(rows) == 1
    assert rows[0]["id"] == "NCBIGene:672"
    assert rows[0]["name"] == "BRCA1"
    assert rows[0]["category"] == "biolink:Gene"


# ---------------------------------------------------------------------------
# load_kgx_edges
# ---------------------------------------------------------------------------

def test_load_kgx_edges(tmp_path: Path) -> None:
    edges_path = tmp_path / "edges.tsv"
    _write_edges(edges_path, [
        {"subject": "ClinVar:12345", "predicate": "biolink:is_sequence_variant_of",
         "object": "NCBIGene:672", "source": "ncbi_clinvar",
         "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/12345"},
    ])

    rows = load_kgx_edges(edges_path)

    assert len(rows) == 1
    assert rows[0]["subject"] == "ClinVar:12345"
    assert rows[0]["predicate"] == "biolink:is_sequence_variant_of"
    assert rows[0]["object"] == "NCBIGene:672"


# ---------------------------------------------------------------------------
# merge_kgx - node deduplication
# ---------------------------------------------------------------------------

def test_merge_kgx_dedup_nodes(tmp_path: Path) -> None:
    shared_node = {"id": "NCBIGene:672", "category": "biolink:Gene", "name": "BRCA1",
                   "source": "ncbi_gene", "source_url": "https://www.ncbi.nlm.nih.gov/gene/672"}
    unique_node = {"id": "NCBIGene:7157", "category": "biolink:Gene", "name": "TP53",
                   "source": "ncbi_gene", "source_url": "https://www.ncbi.nlm.nih.gov/gene/7157"}

    file_a = tmp_path / "a_nodes.tsv"
    file_b = tmp_path / "b_nodes.tsv"
    _write_nodes(file_a, [shared_node])
    _write_nodes(file_b, [shared_node, unique_node])

    merged_nodes, merged_edges = merge_kgx([file_a, file_b], [])

    ids = [n["id"] for n in merged_nodes]
    assert len(merged_nodes) == 2, f"Expected 2 unique nodes, got {len(merged_nodes)}"
    assert "NCBIGene:672" in ids
    assert "NCBIGene:7157" in ids


# ---------------------------------------------------------------------------
# merge_kgx - edge deduplication
# ---------------------------------------------------------------------------

def test_merge_kgx_dedup_edges(tmp_path: Path) -> None:
    shared_edge = {"subject": "ClinVar:12345", "predicate": "biolink:is_sequence_variant_of",
                   "object": "NCBIGene:672", "source": "ncbi_clinvar",
                   "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/12345"}
    unique_edge = {"subject": "NCBIGene:672", "predicate": "biolink:gene_associated_with_condition",
                   "object": "MedGen:C0006142", "source": "ncbi_gene",
                   "source_url": "https://www.ncbi.nlm.nih.gov/gene/672"}

    file_a = tmp_path / "a_edges.tsv"
    file_b = tmp_path / "b_edges.tsv"
    _write_edges(file_a, [shared_edge])
    _write_edges(file_b, [shared_edge, unique_edge])

    nodes_file = tmp_path / "nodes.tsv"
    _write_nodes(nodes_file, [])

    _, merged_edges = merge_kgx([], [file_a, file_b])

    triples = [(e["subject"], e["predicate"], e["object"]) for e in merged_edges]
    assert len(merged_edges) == 2, f"Expected 2 unique edges, got {len(merged_edges)}"
    assert ("ClinVar:12345", "biolink:is_sequence_variant_of", "NCBIGene:672") in triples
    assert ("NCBIGene:672", "biolink:gene_associated_with_condition", "MedGen:C0006142") in triples


# ---------------------------------------------------------------------------
# inject_stubs - Gene stub
# ---------------------------------------------------------------------------

def test_inject_stubs_creates_gene_stub() -> None:
    nodes: list[dict] = []  # no nodes at all
    edges = [
        {"subject": "ClinVar:12345", "predicate": "biolink:is_sequence_variant_of",
         "object": "NCBIGene:999", "source": "ncbi_clinvar", "source_url": "x"},
    ]

    stubs = inject_stubs(nodes, edges)

    stub_ids = [s["id"] for s in stubs]
    assert "NCBIGene:999" in stub_ids
    assert "ClinVar:12345" in stub_ids

    gene_stub = next(s for s in stubs if s["id"] == "NCBIGene:999")
    assert gene_stub["category"] == "biolink:Gene"
    assert gene_stub["source"] == "stub"
    assert gene_stub["name"] == "[stub] NCBIGene:999"


# ---------------------------------------------------------------------------
# inject_stubs - Article stub for PMID
# ---------------------------------------------------------------------------

def test_inject_stubs_creates_pmid_stub() -> None:
    nodes: list[dict] = [
        {"id": "NCBIGene:672", "category": "biolink:Gene", "name": "BRCA1",
         "source": "ncbi_gene", "source_url": "https://www.ncbi.nlm.nih.gov/gene/672"},
    ]
    edges = [
        {"subject": "NCBIGene:672", "predicate": "biolink:mentioned_in_publication",
         "object": "PMID:12345678", "source": "ncbi_gene",
         "source_url": "https://www.ncbi.nlm.nih.gov/gene/672"},
    ]

    stubs = inject_stubs(nodes, edges)

    pmid_stub = next((s for s in stubs if s["id"] == "PMID:12345678"), None)
    assert pmid_stub is not None
    assert pmid_stub["category"] == "biolink:Article"
    assert pmid_stub["source"] == "stub"


# ---------------------------------------------------------------------------
# inject_stubs - no stubs needed
# ---------------------------------------------------------------------------

def test_inject_stubs_no_stubs_needed() -> None:
    nodes = [
        {"id": "NCBIGene:672", "category": "biolink:Gene", "name": "BRCA1",
         "source": "ncbi_gene", "source_url": "https://www.ncbi.nlm.nih.gov/gene/672"},
        {"id": "MedGen:C0006142", "category": "biolink:Disease", "name": "Breast cancer",
         "source": "ncbi_medgen", "source_url": "https://www.ncbi.nlm.nih.gov/medgen/C0006142"},
    ]
    edges = [
        {"subject": "NCBIGene:672", "predicate": "biolink:gene_associated_with_condition",
         "object": "MedGen:C0006142", "source": "ncbi_gene",
         "source_url": "https://www.ncbi.nlm.nih.gov/gene/672"},
    ]

    stubs = inject_stubs(nodes, edges)

    assert stubs == []


# ---------------------------------------------------------------------------
# validate_merge - passing
# ---------------------------------------------------------------------------

def test_validate_merge_passed() -> None:
    nodes = [
        {"id": "NCBIGene:672", "category": "biolink:Gene", "name": "BRCA1",
         "source": "ncbi_gene", "source_url": "https://www.ncbi.nlm.nih.gov/gene/672"},
        {"id": "MedGen:C0006142", "category": "biolink:Disease", "name": "Breast cancer",
         "source": "ncbi_medgen", "source_url": "https://www.ncbi.nlm.nih.gov/medgen/C0006142"},
    ]
    edges = [
        {"subject": "NCBIGene:672", "predicate": "biolink:gene_associated_with_condition",
         "object": "MedGen:C0006142", "source": "ncbi_gene",
         "source_url": "https://www.ncbi.nlm.nih.gov/gene/672"},
    ]

    result = validate_merge(nodes, edges)

    assert result["passed"] is True
    assert result["category_counts"]["biolink:Gene"] == 1
    assert result["category_counts"]["biolink:Disease"] == 1
    assert result["predicate_counts"]["biolink:gene_associated_with_condition"] == 1


# ---------------------------------------------------------------------------
# validate_merge - failing (provenance issues introduced by stubs)
# ---------------------------------------------------------------------------

def test_validate_merge_with_issues() -> None:
    # Stubs have empty source_url which triggers missing provenance.
    nodes = [
        {"id": "NCBIGene:672", "category": "biolink:Gene", "name": "BRCA1",
         "source": "stub", "source_url": ""},  # missing provenance
        {"id": "MedGen:C0006142", "category": "biolink:Disease", "name": "Breast cancer",
         "source": "ncbi_medgen", "source_url": "https://www.ncbi.nlm.nih.gov/medgen/C0006142"},
    ]
    edges = [
        {"subject": "NCBIGene:672", "predicate": "biolink:gene_associated_with_condition",
         "object": "MedGen:C0006142", "source": "ncbi_gene",
         "source_url": "https://www.ncbi.nlm.nih.gov/gene/672"},
    ]

    result = validate_merge(nodes, edges)

    assert result["passed"] is False
    assert len(result["missing_provenance_nodes"]) >= 1


# ---------------------------------------------------------------------------
# generate_merge_report smoke test
# ---------------------------------------------------------------------------

def test_generate_merge_report_writes_file(tmp_path: Path) -> None:
    nodes = [
        {"id": "NCBIGene:672", "category": "biolink:Gene", "name": "BRCA1",
         "source": "ncbi_gene", "source_url": "https://www.ncbi.nlm.nih.gov/gene/672"},
        {"id": "ClinVar:12345", "category": "biolink:SequenceVariant", "name": "Variant 12345",
         "source": "ncbi_clinvar", "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/12345"},
        {"id": "MedGen:C0006142", "category": "biolink:Disease", "name": "Breast cancer",
         "source": "ncbi_medgen", "source_url": "https://www.ncbi.nlm.nih.gov/medgen/C0006142"},
    ]
    edges = [
        {"subject": "ClinVar:12345", "predicate": "biolink:is_sequence_variant_of",
         "object": "NCBIGene:672", "source": "ncbi_clinvar",
         "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/12345"},
        {"subject": "ClinVar:12345", "predicate": "biolink:has_phenotype",
         "object": "MedGen:C0006142", "source": "ncbi_clinvar",
         "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/12345"},
    ]
    validation = validate_merge(nodes, edges)
    report_path = tmp_path / "reports" / "merge_report.md"

    result = generate_merge_report(nodes, edges, validation, report_path)

    assert result == report_path
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "Total nodes: 3" in content
    assert "Total edges: 2" in content
    assert "biolink:Gene" in content
    assert "biolink:is_sequence_variant_of" in content
    assert "ClinVar edges referencing Gene nodes" in content
