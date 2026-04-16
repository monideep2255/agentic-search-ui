"""merge_report.py - Generate a human-readable merge report for the combined KGX graph.

Writes a markdown file summarising node and edge counts, category and predicate
breakdowns, stub counts, validation results, and cross-pipeline connectivity.

No pandas dependency; uses stdlib only (pathlib, logging).

Depends on:
    - stdlib: logging, pathlib

Depended by:
    - tests/integration/test_merge.py
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _make_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a simple markdown table.

    Parameters
    ----------
    headers:
        Column header strings.
    rows:
        Data rows, each a list of strings the same length as headers.

    Returns
    -------
    Markdown table as a string (no trailing newline).
    """
    separator = "| " + " | ".join("---" for _ in headers) + " |"
    header_row = "| " + " | ".join(headers) + " |"
    data_rows = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header_row, separator] + data_rows)


def generate_merge_report(
    nodes: list[dict],
    edges: list[dict],
    validation: dict,
    output_path: Path,
) -> Path:
    """Write a markdown merge report to output_path.

    Sections:
    - Summary: total node and edge counts
    - Nodes by category (table)
    - Edges by predicate (table)
    - Stub nodes count
    - Validation result (passed/failed, per-issue counts)
    - Cross-pipeline connectivity: ClinVar <-> Gene, ClinVar <-> MedGen,
      Gene mentioned_in PubMed Article, Gene in_taxon NCBITaxon,
      PubMed Article has_mesh_annotation MeSH, NCBITaxon subclass_of NCBITaxon

    Parameters
    ----------
    nodes:
        Merged node list (including stubs).
    edges:
        Merged edge list.
    validation:
        Dict returned by merger.validate_merge, containing validate_all keys
        plus category_counts and predicate_counts.
    output_path:
        Destination path for the markdown file. Parent must exist.

    Returns
    -------
    Path to the written report file.
    """
    total_nodes = len(nodes)
    total_edges = len(edges)
    stub_count = sum(1 for n in nodes if n.get("source") == "stub")

    # Category table.
    category_counts: dict[str, int] = validation.get("category_counts", {})
    category_rows = [
        [cat, str(count)]
        for cat, count in sorted(category_counts.items(), key=lambda x: -x[1])
    ]
    if not category_rows:
        category_rows = [["(none)", "0"]]
    category_table = _make_table(["Category", "Count"], category_rows)

    # Predicate table.
    predicate_counts: dict[str, int] = validation.get("predicate_counts", {})
    predicate_rows = [
        [pred, str(count)]
        for pred, count in sorted(predicate_counts.items(), key=lambda x: -x[1])
    ]
    if not predicate_rows:
        predicate_rows = [["(none)", "0"]]
    predicate_table = _make_table(["Predicate", "Count"], predicate_rows)

    # Validation section.
    passed = validation.get("passed", False)
    validation_status = "passed" if passed else "FAILED"
    dangling_count = len(validation.get("dangling_edges", []))
    duplicate_count = len(validation.get("duplicate_nodes", []))
    prov_node_count = len(validation.get("missing_provenance_nodes", []))
    prov_edge_count = len(validation.get("missing_provenance_edges", []))

    # Cross-pipeline connectivity.
    # Node ID sets by CURIE prefix for lookup.
    gene_ids: set[str] = {n["id"] for n in nodes if n.get("id", "").startswith("NCBIGene:")}
    medgen_ids: set[str] = {n["id"] for n in nodes if n.get("id", "").startswith("MedGen:")}
    pmid_ids: set[str] = {n["id"] for n in nodes if n.get("id", "").startswith("PMID:")}
    mesh_ids: set[str] = {n["id"] for n in nodes if n.get("id", "").startswith("MeSH:")}
    taxon_ids: set[str] = {n["id"] for n in nodes if n.get("id", "").startswith("NCBITaxon:")}

    clinvar_to_gene = 0
    clinvar_to_medgen = 0
    gene_to_pmid = 0
    gene_to_taxon = 0
    pmid_to_mesh = 0
    taxon_to_taxon = 0
    for edge in edges:
        subject = edge.get("subject", "")
        obj = edge.get("object", "")
        predicate = edge.get("predicate", "")

        if subject.startswith("ClinVar:") or obj.startswith("ClinVar:"):
            if subject in gene_ids or obj in gene_ids:
                clinvar_to_gene += 1
            if subject in medgen_ids or obj in medgen_ids:
                clinvar_to_medgen += 1

        if predicate == "biolink:mentioned_in" and subject in gene_ids and obj in pmid_ids:
            gene_to_pmid += 1
        if predicate == "biolink:in_taxon" and subject in gene_ids and obj in taxon_ids:
            gene_to_taxon += 1
        if predicate == "biolink:has_mesh_annotation" and subject in pmid_ids and obj in mesh_ids:
            pmid_to_mesh += 1
        if predicate == "biolink:subclass_of" and subject in taxon_ids and obj in taxon_ids:
            taxon_to_taxon += 1

    lines: list[str] = [
        "# Merge report",
        "",
        "## Summary",
        "",
        f"Total nodes: {total_nodes}",
        f"Total edges: {total_edges}",
        f"Stub nodes: {stub_count}",
        "",
        "## Nodes by category",
        "",
        category_table,
        "",
        "## Edges by predicate",
        "",
        predicate_table,
        "",
        "## Stub nodes",
        "",
        f"{stub_count} stub node(s) injected for dangling edge references.",
        "",
        "## Validation",
        "",
        f"Status: {validation_status}",
        "",
        f"- Dangling edges: {dangling_count}",
        f"- Duplicate nodes: {duplicate_count}",
        f"- Nodes missing provenance: {prov_node_count}",
        f"- Edges missing provenance: {prov_edge_count}",
        "",
        "## Cross-pipeline connectivity",
        "",
        f"ClinVar edges referencing Gene nodes: {clinvar_to_gene}",
        f"ClinVar edges referencing MedGen nodes: {clinvar_to_medgen}",
        f"Gene mentioned_in PubMed Article edges resolved: {gene_to_pmid}",
        f"Gene in_taxon NCBITaxon edges resolved: {gene_to_taxon}",
        f"PubMed Article has_mesh_annotation MeSH edges resolved: {pmid_to_mesh}",
        f"NCBITaxon subclass_of NCBITaxon edges resolved: {taxon_to_taxon}",
        "",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote merge report to %s", output_path)
    return output_path
