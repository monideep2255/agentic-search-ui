"""merger.py - Merge KGX files from multiple pipelines into a single combined output.

Loads nodes.tsv and edges.tsv from each pipeline, deduplicates, injects stubs
for dangling references, and runs full validation on the merged graph.

No pandas dependency; uses stdlib only (csv, pathlib, collections, logging).

Depends on:
    - stdlib: csv, collections, logging, pathlib
    - system-01-data-pipelines/shared/validator.py (validate_all)

Depended by:
    - tests/integration/test_merge.py
    - tests/integration/test_cross_database_traversal.py

Reads:
    - data/kgx/<database>/nodes.tsv
    - data/kgx/<database>/edges.tsv

Writes:
    - data/kgx/merged/nodes.tsv
    - data/kgx/merged/edges.tsv
"""

import csv
import logging
from collections import Counter
from pathlib import Path
from typing import Iterator

from .kgx_exporter import append_edges, append_nodes
from .validator import validate_all

BATCH_SIZE = 10_000

logger = logging.getLogger(__name__)

# CURIE prefix -> BioLink category. Checked in order; first match wins.
_PREFIX_TO_CATEGORY: list[tuple[str, str]] = [
    ("NCBIGene:", "biolink:Gene"),
    ("PMID:", "biolink:Article"),
    ("MeSH:", "biolink:OntologyClass"),
    ("GO:", "biolink:BiologicalProcess"),
    ("MedGen:", "biolink:Disease"),
    ("MONDO:", "biolink:Disease"),
    ("NCBITaxon:", "biolink:OrganismTaxon"),
    ("HP:", "biolink:PhenotypicFeature"),
    ("ClinVar:", "biolink:SequenceVariant"),
    ("UMLS:", "biolink:Disease"),
]


def _infer_category(curie: str) -> str:
    """Return the BioLink category for a CURIE, or biolink:NamedThing if unknown."""
    for prefix, category in _PREFIX_TO_CATEGORY:
        if curie.startswith(prefix):
            return category
    return "biolink:NamedThing"


def stream_kgx_nodes(path: Path) -> Iterator[dict]:
    """Generator: yield one node dict per row in a nodes.tsv file.

    Use this for production pipelines where the node list is too big for RAM.
    Memory is O(1) per row instead of O(n).

    Args:
        path: Path to a KGX nodes.tsv file (tab-separated, first row is header).

    Yields:
        One row dict per data line.
    """
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            yield dict(row)


def stream_kgx_edges(path: Path) -> Iterator[dict]:
    """Generator: yield one edge dict per row in an edges.tsv file.

    Use this for production pipelines where the edge list is too big for RAM.

    Args:
        path: Path to a KGX edges.tsv file (tab-separated, first row is header).

    Yields:
        One row dict per data line.
    """
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            yield dict(row)


def load_kgx_nodes(path: Path) -> list[dict]:
    """List-returning wrapper around stream_kgx_nodes. Use for tests only.

    Do NOT use in production pipelines — a full nodes.tsv list holds every
    node dict in RAM at once and OOMs on Gate-2-scale data (gene alone is
    67M nodes, ~25 GB as Python dicts).

    Args:
        path: Path to a KGX nodes.tsv file.

    Returns:
        List of row dicts.
    """
    rows = list(stream_kgx_nodes(path))
    logger.info("Loaded %d nodes from %s", len(rows), path)
    return rows


def load_kgx_edges(path: Path) -> list[dict]:
    """List-returning wrapper around stream_kgx_edges. Use for tests only.

    Do NOT use in production pipelines — a full edges.tsv list OOMs on
    Gate-2-scale data (pubmed alone is 349M edges).

    Args:
        path: Path to a KGX edges.tsv file.

    Returns:
        List of row dicts.
    """
    rows = list(stream_kgx_edges(path))
    logger.info("Loaded %d edges from %s", len(rows), path)
    return rows


def _peek_fieldnames(paths: list[Path], required: list[str]) -> list[str]:
    """Read the header of each TSV and return a union with required columns first.

    Args:
        paths: List of TSV files to peek.
        required: Required columns that always come first, in order.

    Returns:
        List of column names: required columns in order, then extras sorted.
    """
    extras: set[str] = set()
    for path in paths:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh, delimiter="\t")
            try:
                header = next(reader)
            except StopIteration:
                continue
            for col in header:
                if col and col not in required:
                    extras.add(col)
    return list(required) + sorted(extras)


def merge_kgx_streaming(
    node_files: list[Path],
    edge_files: list[Path],
    output_nodes_path: Path,
    output_edges_path: Path,
    node_fieldnames: list[str],
    edge_fieldnames: list[str],
) -> dict:
    """Stream-merge KGX files into one pair of TSVs with stub injection.

    Two-pass design for O(unique_node_ids) memory instead of O(total_rows):

    Pass 1: stream every nodes.tsv file; dedup by id via an in-memory set of
    CURIE strings; write unique nodes to output_nodes_path in 10K batches.
    At Gate 2 scale the set holds ~116M CURIEs (~8 GB RAM).

    Pass 2: stream every edges.tsv file; track dangling endpoints against the
    pass-1 node-id set; write edges to output_edges_path in 10K batches.
    Edge-level dedup is NOT performed (cross-pipeline edge collisions are
    rare by construction and a full edge-triple set would need ~100 GB RAM
    on Gate-2-scale data).

    After pass 2, synthesise a stub node (source="stub") for every dangling
    endpoint using _infer_category on the CURIE prefix, and append stubs
    to the nodes file.

    Args:
        node_files: List of per-db nodes.tsv paths.
        edge_files: List of per-db edges.tsv paths.
        output_nodes_path: Path to the merged nodes.tsv (already initialised
                           with header by the caller).
        output_edges_path: Path to the merged edges.tsv (already initialised).
        node_fieldnames: Column order for the merged nodes file.
        edge_fieldnames: Column order for the merged edges file.

    Returns:
        Dict with keys node_count, edge_count, stub_count, duplicate_nodes_dropped,
        dangling_endpoints, validation (dict with passed, missing_prov_*, counts).
    """
    seen_node_ids: set[str] = set()
    node_batch: list[dict] = []
    node_count = 0
    duplicate_nodes: list[str] = []
    missing_prov_nodes: list[str] = []
    category_counts: Counter[str] = Counter()

    # Pass 1: nodes
    for path in node_files:
        logger.info("Pass 1 streaming nodes from %s", path)
        for row in stream_kgx_nodes(path):
            node_id = row.get("id", "")
            if not node_id:
                continue
            if node_id in seen_node_ids:
                duplicate_nodes.append(node_id)
                continue
            seen_node_ids.add(node_id)
            category_counts[row.get("category", "(unknown)")] += 1
            if not row.get("source") or not row.get("source_url"):
                missing_prov_nodes.append(node_id)
            node_batch.append(row)
            if len(node_batch) >= BATCH_SIZE:
                append_nodes(node_batch, output_nodes_path, fieldnames=node_fieldnames)
                node_count += len(node_batch)
                node_batch.clear()
                if node_count % 1_000_000 == 0:
                    logger.info("  merged %d unique nodes so far", node_count)
    if node_batch:
        append_nodes(node_batch, output_nodes_path, fieldnames=node_fieldnames)
        node_count += len(node_batch)
        node_batch.clear()

    logger.info(
        "Pass 1 complete: %d unique nodes written, %d duplicates dropped",
        node_count,
        duplicate_nodes,
    )

    # Pass 2: edges
    edge_batch: list[dict] = []
    edge_count = 0
    missing_prov_edges: list[tuple[str, str, str]] = []
    predicate_counts: Counter[str] = Counter()
    dangling_endpoints: set[str] = set()
    connectivity: dict[str, int] = {
        "gene_pmid_resolved": 0,
        "gene_taxon_resolved": 0,
        "pmid_mesh_resolved": 0,
        "taxon_subclass_resolved": 0,
    }

    for path in edge_files:
        logger.info("Pass 2 streaming edges from %s", path)
        for row in stream_kgx_edges(path):
            subj = row.get("subject", "")
            pred = row.get("predicate", "")
            obj = row.get("object", "")
            if not subj or not pred or not obj:
                continue
            predicate_counts[pred] += 1
            if not row.get("source") or not row.get("source_url"):
                missing_prov_edges.append((subj, pred, obj))
            # Cross-pipeline connectivity counters (both endpoints must resolve to real nodes)
            if subj in seen_node_ids and obj in seen_node_ids:
                if pred == "biolink:mentioned_in" and subj.startswith("NCBIGene:") and obj.startswith("PMID:"):
                    connectivity["gene_pmid_resolved"] += 1
                elif pred == "biolink:in_taxon" and subj.startswith("NCBIGene:") and obj.startswith("NCBITaxon:"):
                    connectivity["gene_taxon_resolved"] += 1
                elif pred == "biolink:has_mesh_annotation" and subj.startswith("PMID:") and obj.startswith("MeSH:"):
                    connectivity["pmid_mesh_resolved"] += 1
                elif pred == "biolink:subclass_of" and subj.startswith("NCBITaxon:") and obj.startswith("NCBITaxon:"):
                    connectivity["taxon_subclass_resolved"] += 1
            if subj not in seen_node_ids:
                dangling_endpoints.add(subj)
            if obj not in seen_node_ids:
                dangling_endpoints.add(obj)
            edge_batch.append(row)
            if len(edge_batch) >= BATCH_SIZE:
                append_edges(edge_batch, output_edges_path, fieldnames=edge_fieldnames)
                edge_count += len(edge_batch)
                edge_batch.clear()
                if edge_count % 10_000_000 == 0:
                    logger.info("  merged %d edges so far", edge_count)
    if edge_batch:
        append_edges(edge_batch, output_edges_path, fieldnames=edge_fieldnames)
        edge_count += len(edge_batch)
        edge_batch.clear()

    logger.info(
        "Pass 2 complete: %d edges written, %d dangling endpoints",
        edge_count,
        len(dangling_endpoints),
    )

    # Inject stubs for dangling endpoints (single batch; typically small)
    stubs: list[dict] = []
    stub_prefix_counts: Counter[str] = Counter()
    for curie in sorted(dangling_endpoints):
        category = _infer_category(curie)
        prefix = curie.split(":")[0] + ":" if ":" in curie else curie
        stub_prefix_counts[prefix] += 1
        stubs.append({
            "id": curie,
            "category": category,
            "name": f"[stub] {curie}",
            "source": "stub",
            "source_url": "",
        })
        seen_node_ids.add(curie)
        category_counts[category] += 1

    if stubs:
        append_nodes(stubs, output_nodes_path, fieldnames=node_fieldnames)
        node_count += len(stubs)
        # Stubs carry empty source_url; record them as missing_provenance_nodes
        # (matches existing inject_stubs+validate_merge behavior).
        for stub in stubs:
            missing_prov_nodes.append(stub["id"])
        logger.info(
            "Stub injection: %d stubs; prefixes=%s",
            len(stubs),
            dict(stub_prefix_counts),
        )
    else:
        logger.info("Stub injection: no dangling endpoints, no stubs needed")

    validation = {
        "passed": len(missing_prov_nodes) == 0 and len(missing_prov_edges) == 0,
        "dangling_edges": [],  # empty list by construction (stubs cover every endpoint)
        "duplicate_nodes": duplicate_nodes,  # list of duplicate CURIEs seen across pipelines
        "missing_provenance_nodes": missing_prov_nodes,
        "missing_provenance_edges": missing_prov_edges,
        "category_counts": dict(category_counts),
        "predicate_counts": dict(predicate_counts),
    }

    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "stub_count": len(stubs),
        "duplicate_nodes_dropped": len(duplicate_nodes),
        "dangling_endpoints": len(dangling_endpoints),
        "connectivity": connectivity,
        "validation": validation,
    }


def merge_kgx(
    node_files: list[Path],
    edge_files: list[Path],
) -> tuple[list[dict], list[dict]]:
    """Load, concatenate, and deduplicate KGX node and edge files.

    Nodes are deduplicated by the "id" field (first occurrence kept).
    Edges are deduplicated by the (subject, predicate, object) tuple
    (first occurrence kept). Counts before and after dedup are logged.

    Parameters
    ----------
    node_files:
        Paths to all nodes.tsv files to merge.
    edge_files:
        Paths to all edges.tsv files to merge.

    Returns
    -------
    Tuple of (merged_nodes, merged_edges) after deduplication.
    """
    # Load all nodes.
    all_nodes: list[dict] = []
    for path in node_files:
        all_nodes.extend(load_kgx_nodes(path))

    # Load all edges.
    all_edges: list[dict] = []
    for path in edge_files:
        all_edges.extend(load_kgx_edges(path))

    nodes_before = len(all_nodes)
    edges_before = len(all_edges)

    # Deduplicate nodes by id (keep first).
    seen_ids: set[str] = set()
    merged_nodes: list[dict] = []
    for node in all_nodes:
        node_id = node.get("id", "")
        if node_id not in seen_ids:
            seen_ids.add(node_id)
            merged_nodes.append(node)

    # Deduplicate edges by (subject, predicate, object) tuple (keep first).
    seen_triples: set[tuple[str, str, str]] = set()
    merged_edges: list[dict] = []
    for edge in all_edges:
        triple = (
            edge.get("subject", ""),
            edge.get("predicate", ""),
            edge.get("object", ""),
        )
        if triple not in seen_triples:
            seen_triples.add(triple)
            merged_edges.append(edge)

    logger.info(
        "Nodes: %d -> %d after dedup (removed %d)",
        nodes_before,
        len(merged_nodes),
        nodes_before - len(merged_nodes),
    )
    logger.info(
        "Edges: %d -> %d after dedup (removed %d)",
        edges_before,
        len(merged_edges),
        edges_before - len(merged_edges),
    )

    return merged_nodes, merged_edges


def inject_stubs(
    nodes: list[dict],
    edges: list[dict],
) -> list[dict]:
    """Create stub nodes for edge endpoints not present in the node set.

    For each subject or object CURIE in edges that has no matching node,
    a minimal stub node is created. Stub nodes carry no provenance (source
    and source_url are empty strings) and are marked source="stub".

    Category is inferred from the CURIE prefix using the mapping:
        NCBIGene: -> biolink:Gene
        PMID:     -> biolink:Article
        GO:       -> biolink:BiologicalProcess
        MedGen:   -> biolink:Disease
        MONDO:    -> biolink:Disease
        NCBITaxon:-> biolink:OrganismTaxon
        HP:       -> biolink:PhenotypicFeature
        (other)   -> biolink:NamedThing

    Parameters
    ----------
    nodes:
        Current node list.
    edges:
        Edge list to check for dangling references.

    Returns
    -------
    List of stub node dicts. Caller is responsible for appending these to
    the merged node list.
    """
    node_ids: set[str] = {n.get("id", "") for n in nodes}

    dangling: set[str] = set()
    for edge in edges:
        subject = edge.get("subject", "")
        obj = edge.get("object", "")
        if subject and subject not in node_ids:
            dangling.add(subject)
        if obj and obj not in node_ids:
            dangling.add(obj)

    stubs: list[dict] = []
    prefix_counter: Counter[str] = Counter()

    for curie in sorted(dangling):
        category = _infer_category(curie)
        prefix = curie.split(":")[0] + ":" if ":" in curie else curie
        prefix_counter[prefix] += 1
        stub: dict = {
            "id": curie,
            "category": category,
            "name": f"[stub] {curie}",
            "source": "stub",
            "source_url": "",
        }
        stubs.append(stub)

    if stubs:
        logger.info(
            "inject_stubs: created %d stub nodes; prefix breakdown: %s",
            len(stubs),
            dict(prefix_counter),
        )
    else:
        logger.info("inject_stubs: no dangling references found, no stubs needed")

    return stubs


def validate_merge(
    nodes: list[dict],
    edges: list[dict],
) -> dict:
    """Run full validation on a merged graph and return an enriched summary.

    Runs validate_all from shared.validator, then adds per-category and
    per-predicate counts for reporting.

    Parameters
    ----------
    nodes:
        Merged node list (including any injected stubs).
    edges:
        Merged edge list.

    Returns
    -------
    Dict with keys from validate_all (dangling_edges, duplicate_nodes,
    missing_provenance_nodes, missing_provenance_edges, passed) plus:
        category_counts: dict[str, int] - node count per BioLink category
        predicate_counts: dict[str, int] - edge count per predicate
    """
    result = validate_all(nodes, edges, label="merged")

    category_counts: Counter[str] = Counter()
    for node in nodes:
        category_counts[node.get("category", "(unknown)")] += 1

    predicate_counts: Counter[str] = Counter()
    for edge in edges:
        predicate_counts[edge.get("predicate", "(unknown)")] += 1

    result["category_counts"] = dict(category_counts)
    result["predicate_counts"] = dict(predicate_counts)

    return result
