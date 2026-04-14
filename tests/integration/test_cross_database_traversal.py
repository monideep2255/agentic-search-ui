"""Integration tests verifying cross-pipeline edge resolution for the core triangle.

The core triangle: Gene (NCBIGene:672 / BRCA1) + ClinVar (ClinVar:12345) +
MedGen (MedGen:C0006142 / Breast cancer).

Three edges connect the triangle:
  ClinVar:12345 --is_sequence_variant_of--> NCBIGene:672
  ClinVar:12345 --has_phenotype--> MedGen:C0006142
  NCBIGene:672  --gene_associated_with_condition--> MedGen:C0006142

Tests use merger functions directly; no FTP, no network.

Depends on:
    - system-01-data-pipelines/shared/merger.py
    - system-01-data-pipelines/shared/validator.py
"""

import csv
from pathlib import Path

import pytest

from shared.merger import inject_stubs, merge_kgx, validate_merge
from shared.validator import validate_no_dangling


# ---------------------------------------------------------------------------
# Shared fixture data
# ---------------------------------------------------------------------------

_GENE_NODE = {
    "id": "NCBIGene:672",
    "category": "biolink:Gene",
    "name": "BRCA1",
    "source": "ncbi_gene",
    "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
}

_CLINVAR_NODE = {
    "id": "ClinVar:12345",
    "category": "biolink:SequenceVariant",
    "name": "NM_007294.4(BRCA1):c.5266dupC (p.Gln1756ProfsTer74)",
    "source": "ncbi_clinvar",
    "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/12345",
}

_MEDGEN_NODE = {
    "id": "MedGen:C0006142",
    "category": "biolink:Disease",
    "name": "Breast cancer",
    "source": "ncbi_medgen",
    "source_url": "https://www.ncbi.nlm.nih.gov/medgen/C0006142",
}

_EDGE_VARIANT_TO_GENE = {
    "subject": "ClinVar:12345",
    "predicate": "biolink:is_sequence_variant_of",
    "object": "NCBIGene:672",
    "source": "ncbi_clinvar",
    "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/12345",
}

_EDGE_VARIANT_TO_DISEASE = {
    "subject": "ClinVar:12345",
    "predicate": "biolink:has_phenotype",
    "object": "MedGen:C0006142",
    "source": "ncbi_clinvar",
    "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/12345",
}

_EDGE_GENE_TO_DISEASE = {
    "subject": "NCBIGene:672",
    "predicate": "biolink:gene_associated_with_condition",
    "object": "MedGen:C0006142",
    "source": "ncbi_gene",
    "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
}


def _all_triangle_nodes() -> list[dict]:
    return [_GENE_NODE.copy(), _CLINVAR_NODE.copy(), _MEDGEN_NODE.copy()]


def _all_triangle_edges() -> list[dict]:
    return [
        _EDGE_VARIANT_TO_GENE.copy(),
        _EDGE_VARIANT_TO_DISEASE.copy(),
        _EDGE_GENE_TO_DISEASE.copy(),
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_nodes(path: Path, rows: list[dict]) -> Path:
    fieldnames = ["id", "category", "name", "source", "source_url"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t",
                                extrasaction="ignore", restval="")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_edges(path: Path, rows: list[dict]) -> Path:
    fieldnames = ["subject", "predicate", "object", "source", "source_url"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t",
                                extrasaction="ignore", restval="")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _make_triangle_files(tmp_path: Path) -> tuple[list[Path], list[Path]]:
    """Write per-pipeline KGX files for the full core triangle."""
    # Gene pipeline files.
    gene_nodes = tmp_path / "gene_nodes.tsv"
    gene_edges = tmp_path / "gene_edges.tsv"
    _write_nodes(gene_nodes, [_GENE_NODE])
    _write_edges(gene_edges, [_EDGE_GENE_TO_DISEASE])

    # ClinVar pipeline files.
    clinvar_nodes = tmp_path / "clinvar_nodes.tsv"
    clinvar_edges = tmp_path / "clinvar_edges.tsv"
    _write_nodes(clinvar_nodes, [_CLINVAR_NODE])
    _write_edges(clinvar_edges, [_EDGE_VARIANT_TO_GENE, _EDGE_VARIANT_TO_DISEASE])

    # MedGen pipeline files.
    medgen_nodes = tmp_path / "medgen_nodes.tsv"
    medgen_edges = tmp_path / "medgen_edges.tsv"
    _write_nodes(medgen_nodes, [_MEDGEN_NODE])
    _write_edges(medgen_edges, [])

    node_files = [gene_nodes, clinvar_nodes, medgen_nodes]
    edge_files = [gene_edges, clinvar_edges, medgen_edges]
    return node_files, edge_files


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_gene_to_clinvar_path(tmp_path: Path) -> None:
    """The is_sequence_variant_of edge connects variant to gene."""
    node_files, edge_files = _make_triangle_files(tmp_path)
    nodes, edges = merge_kgx(node_files, edge_files)

    variant_to_gene = [
        e for e in edges
        if e["subject"] == "ClinVar:12345"
        and e["predicate"] == "biolink:is_sequence_variant_of"
        and e["object"] == "NCBIGene:672"
    ]
    assert len(variant_to_gene) == 1, "Expected one is_sequence_variant_of edge"


def test_clinvar_to_medgen_path(tmp_path: Path) -> None:
    """The has_phenotype edge connects variant to disease."""
    node_files, edge_files = _make_triangle_files(tmp_path)
    nodes, edges = merge_kgx(node_files, edge_files)

    variant_to_disease = [
        e for e in edges
        if e["subject"] == "ClinVar:12345"
        and e["predicate"] == "biolink:has_phenotype"
        and e["object"] == "MedGen:C0006142"
    ]
    assert len(variant_to_disease) == 1, "Expected one has_phenotype edge"


def test_gene_to_medgen_path(tmp_path: Path) -> None:
    """The gene_associated_with_condition edge connects gene to disease."""
    node_files, edge_files = _make_triangle_files(tmp_path)
    nodes, edges = merge_kgx(node_files, edge_files)

    gene_to_disease = [
        e for e in edges
        if e["subject"] == "NCBIGene:672"
        and e["predicate"] == "biolink:gene_associated_with_condition"
        and e["object"] == "MedGen:C0006142"
    ]
    assert len(gene_to_disease) == 1, "Expected one gene_associated_with_condition edge"


def test_triangle_all_nodes_resolved(tmp_path: Path) -> None:
    """After merging the full triangle, there are zero dangling edges."""
    node_files, edge_files = _make_triangle_files(tmp_path)
    nodes, edges = merge_kgx(node_files, edge_files)

    node_ids = {n["id"] for n in nodes}
    dangling = validate_no_dangling(edges, node_ids, label="triangle")

    assert dangling == [], (
        f"Expected zero dangling edges, got {len(dangling)}: "
        + str([(e["subject"], e["object"]) for e in dangling])
    )


def test_triangle_with_missing_gene(tmp_path: Path) -> None:
    """Removing the Gene node causes dangling edges; inject_stubs resolves them."""
    # ClinVar and MedGen files only - Gene node file is empty.
    clinvar_nodes = tmp_path / "clinvar_nodes.tsv"
    clinvar_edges = tmp_path / "clinvar_edges.tsv"
    medgen_nodes = tmp_path / "medgen_nodes.tsv"
    medgen_edges = tmp_path / "medgen_edges.tsv"
    gene_nodes = tmp_path / "gene_nodes.tsv"   # intentionally empty
    gene_edges = tmp_path / "gene_edges.tsv"

    _write_nodes(clinvar_nodes, [_CLINVAR_NODE])
    _write_edges(clinvar_edges, [_EDGE_VARIANT_TO_GENE, _EDGE_VARIANT_TO_DISEASE])
    _write_nodes(medgen_nodes, [_MEDGEN_NODE])
    _write_edges(medgen_edges, [])
    _write_nodes(gene_nodes, [])   # Gene node absent.
    _write_edges(gene_edges, [_EDGE_GENE_TO_DISEASE])

    nodes, edges = merge_kgx(
        [gene_nodes, clinvar_nodes, medgen_nodes],
        [gene_edges, clinvar_edges, medgen_edges],
    )

    # Before stub injection: dangling edges expected because NCBIGene:672 is absent.
    node_ids_before = {n["id"] for n in nodes}
    dangling_before = validate_no_dangling(edges, node_ids_before, label="pre-stub")
    assert len(dangling_before) > 0, "Expected dangling edges before stub injection"

    # After stub injection: dangling edges must be zero.
    stubs = inject_stubs(nodes, edges)
    assert any(s["id"] == "NCBIGene:672" for s in stubs), "Expected Gene stub for NCBIGene:672"

    gene_stub = next(s for s in stubs if s["id"] == "NCBIGene:672")
    assert gene_stub["category"] == "biolink:Gene"

    all_nodes = nodes + stubs
    node_ids_after = {n["id"] for n in all_nodes}
    dangling_after = validate_no_dangling(edges, node_ids_after, label="post-stub")
    assert dangling_after == [], (
        f"Expected zero dangling edges after stub injection, got {len(dangling_after)}"
    )
