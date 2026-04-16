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

from .validator import validate_all

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


def load_kgx_nodes(path: Path) -> list[dict]:
    """Read a nodes.tsv file and return a list of row dicts.

    Parameters
    ----------
    path:
        Path to a KGX nodes.tsv file (tab-separated, first row is header).

    Returns
    -------
    List of dicts, one per data row.
    """
    rows: list[dict] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            rows.append(dict(row))
    logger.info("Loaded %d nodes from %s", len(rows), path)
    return rows


def load_kgx_edges(path: Path) -> list[dict]:
    """Read an edges.tsv file and return a list of row dicts.

    Parameters
    ----------
    path:
        Path to a KGX edges.tsv file (tab-separated, first row is header).

    Returns
    -------
    List of dicts, one per data row.
    """
    rows: list[dict] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            rows.append(dict(row))
    logger.info("Loaded %d edges from %s", len(rows), path)
    return rows


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
