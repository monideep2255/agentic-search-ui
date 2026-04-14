"""validator.py - KGX output quality validation functions.

All functions return data for the caller to act on. None raise on validation
failure - the caller decides what to do with bad records. Use validate_all()
as the single entry point for a full pipeline quality check.

No pandas dependency; uses stdlib only.

Depends on:
    - stdlib: logging

Depended by:
    - system-01-data-pipelines/gene/pipeline.py (planned)
    - system-01-data-pipelines/clinvar/pipeline.py (planned)
    - system-01-data-pipelines/medgen/pipeline.py (planned)
"""

import logging

logger = logging.getLogger(__name__)


def validate_no_dangling(
    edges: list[dict],
    node_ids: set[str],
    label: str = "edges",
) -> list[dict]:
    """Find edges whose subject or object is not in node_ids.

    Does not raise. Returns the dangling edges so the caller can decide
    whether to drop them, log them, or fail the pipeline.

    Parameters
    ----------
    edges:
        List of edge dicts. Each must have "subject" and "object" keys.
    node_ids:
        Set of known node id strings.
    label:
        Human-readable label used in log messages.

    Returns
    -------
    List of edge dicts that have a dangling subject or object. Empty list
    means no dangling edges.
    """
    dangling: list[dict] = []
    n_subj = 0
    n_obj = 0

    for edge in edges:
        subject_missing = edge.get("subject", "") not in node_ids
        object_missing = edge.get("object", "") not in node_ids
        if subject_missing:
            n_subj += 1
        if object_missing:
            n_obj += 1
        if subject_missing or object_missing:
            dangling.append(edge)

    if dangling:
        logger.warning(
            "%s: %d dangling subjects, %d dangling objects (%d total bad edges)",
            label,
            n_subj,
            n_obj,
            len(dangling),
        )
    else:
        logger.info("%s: 0 dangling edges", label)

    return dangling


def validate_no_duplicates(
    nodes: list[dict],
    key: str = "id",
) -> list[str]:
    """Find duplicate values for the given key across nodes.

    Does not raise. Returns the duplicate key values so the caller can
    inspect or drop them.

    Parameters
    ----------
    nodes:
        List of node dicts.
    key:
        Dict key to check for duplicates. Defaults to "id".

    Returns
    -------
    List of key values that appear more than once. Empty list means no
    duplicates.
    """
    seen: dict[str, int] = {}
    for node in nodes:
        val = node.get(key, "")
        seen[val] = seen.get(val, 0) + 1

    duplicates = [val for val, count in seen.items() if count > 1]

    if duplicates:
        logger.warning(
            "validate_no_duplicates: %d duplicate values for key '%s'",
            len(duplicates),
            key,
        )
    else:
        logger.info("validate_no_duplicates: 0 duplicates on key '%s'", key)

    return duplicates


def validate_provenance(
    records: list[dict],
    label: str = "records",
) -> list[dict]:
    """Find records missing non-empty source or source_url.

    Does not raise. Returns failing records so the caller can drop or
    report them.

    Parameters
    ----------
    records:
        List of node or edge dicts to check.
    label:
        Human-readable label used in log messages.

    Returns
    -------
    List of records where source or source_url is absent or empty. Empty
    list means full provenance coverage.
    """
    failing: list[dict] = []

    for rec in records:
        source = rec.get("source", "")
        source_url = rec.get("source_url", "")
        if not source or not source_url:
            failing.append(rec)

    if failing:
        logger.warning(
            "%s: %d records missing provenance (source or source_url)",
            label,
            len(failing),
        )
    else:
        logger.info("%s: provenance complete on all %d records", label, len(records))

    return failing


def validate_all(
    nodes: list[dict],
    edges: list[dict],
    label: str = "pipeline",
) -> dict:
    """Run all three validations and return a summary dict.

    Runs:
    - validate_no_dangling on edges vs node id set
    - validate_no_duplicates on nodes by id
    - validate_provenance on nodes and edges separately

    Does not raise on failure. The "passed" key in the result is True only
    if all four result lists are empty.

    Parameters
    ----------
    nodes:
        List of node dicts with at minimum id, source, source_url.
    edges:
        List of edge dicts with at minimum subject, object, source, source_url.
    label:
        Human-readable label for log messages.

    Returns
    -------
    Dict with keys:
        dangling_edges: list[dict] - edges with missing subject/object nodes
        duplicate_nodes: list[str] - id values that appear more than once
        missing_provenance_nodes: list[dict] - nodes with empty source/source_url
        missing_provenance_edges: list[dict] - edges with empty source/source_url
        passed: bool - True if all lists are empty
    """
    node_ids: set[str] = {n.get("id", "") for n in nodes}

    dangling_edges = validate_no_dangling(edges, node_ids, label=f"{label}:edges")
    duplicate_nodes = validate_no_duplicates(nodes, key="id")
    missing_provenance_nodes = validate_provenance(nodes, label=f"{label}:nodes")
    missing_provenance_edges = validate_provenance(edges, label=f"{label}:edges")

    passed = not any(
        [dangling_edges, duplicate_nodes, missing_provenance_nodes, missing_provenance_edges]
    )

    if passed:
        logger.info("%s: all validation checks passed", label)
    else:
        logger.warning(
            "%s: validation FAILED - dangling=%d duplicates=%d provenance_nodes=%d provenance_edges=%d",
            label,
            len(dangling_edges),
            len(duplicate_nodes),
            len(missing_provenance_nodes),
            len(missing_provenance_edges),
        )

    return {
        "dangling_edges": dangling_edges,
        "duplicate_nodes": duplicate_nodes,
        "missing_provenance_nodes": missing_provenance_nodes,
        "missing_provenance_edges": missing_provenance_edges,
        "passed": passed,
    }
