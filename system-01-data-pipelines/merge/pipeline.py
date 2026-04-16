"""pipeline.py - Orchestrate the 5-database KGX merge.

Loads per-database KGX outputs (gene, clinvar, medgen, pubmed, taxonomy),
deduplicates, injects stubs for dangling cross-pipeline references, writes
a single merged pair of TSVs, validates the result, and emits a markdown
report summarising category and predicate counts and cross-pipeline
connectivity.

Pipelines included by default:
    - gene
    - clinvar
    - medgen
    - pubmed
    - taxonomy

Depends on:
    - system-01-data-pipelines/shared/config.PipelineConfig
    - system-01-data-pipelines/shared/merger.merge_kgx
    - system-01-data-pipelines/shared/merger.inject_stubs
    - system-01-data-pipelines/shared/merger.validate_merge
    - system-01-data-pipelines/shared/merge_report.generate_merge_report

Reads:
    - config.kgx_output_dir/<database>/nodes.tsv
    - config.kgx_output_dir/<database>/edges.tsv

Writes:
    - config.kgx_output_dir/merged/nodes.tsv
    - config.kgx_output_dir/merged/edges.tsv
    - config.kgx_output_dir/merged/merge_report.md
"""

import csv
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import PipelineConfig
from shared.merge_report import generate_merge_report
from shared.merger import (
    inject_stubs,
    merge_kgx,
    validate_merge,
)

logger = logging.getLogger(__name__)

DEFAULT_DATABASES: tuple[str, ...] = ("gene", "clinvar", "medgen", "pubmed", "taxonomy")

NODE_FIELDNAMES: tuple[str, ...] = (
    "id",
    "category",
    "name",
    "source",
    "source_url",
    "xrefs",
    "description",
)

EDGE_FIELDNAMES: tuple[str, ...] = (
    "subject",
    "predicate",
    "object",
    "source",
    "source_url",
    "evidence",
)


def _collect_input_paths(
    kgx_output_dir: Path,
    databases: tuple[str, ...],
) -> tuple[list[Path], list[Path], list[str]]:
    """Collect nodes.tsv and edges.tsv paths for the requested databases.

    Databases missing a nodes.tsv file are skipped with a warning, not raised.
    Databases missing only an edges.tsv file are also skipped (an empty edges
    file would silently remove edges that belonged to that pipeline).

    Args:
        kgx_output_dir: Root KGX output directory containing per-database subdirs.
        databases: Tuple of database names to include.

    Returns:
        Tuple of (node_paths, edge_paths, found_databases) where found_databases
        lists the databases whose files were located.
    """
    node_paths: list[Path] = []
    edge_paths: list[Path] = []
    found: list[str] = []

    for db in databases:
        nodes_path = kgx_output_dir / db / "nodes.tsv"
        edges_path = kgx_output_dir / db / "edges.tsv"
        if not nodes_path.exists() or not edges_path.exists():
            logger.warning(
                "Skipping database '%s': missing nodes.tsv or edges.tsv in %s",
                db,
                kgx_output_dir / db,
            )
            continue
        node_paths.append(nodes_path)
        edge_paths.append(edges_path)
        found.append(db)

    return node_paths, edge_paths, found


def _union_fieldnames(rows: list[dict], required: tuple[str, ...]) -> list[str]:
    """Return a stable, ordered union of required columns plus any extras seen in rows.

    Required columns always come first, in their declared order. Additional
    keys encountered in rows are appended in sorted order for reproducibility.

    Args:
        rows: List of row dicts.
        required: Required column names, in output order.

    Returns:
        List of column names to use as the TSV header.
    """
    extras: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in required:
                extras.add(key)
    return list(required) + sorted(extras)


def _write_tsv(path: Path, rows: list[dict], fieldnames: list[str]) -> Path:
    """Write a list of row dicts to a TSV file with the given header.

    Missing fields are written as empty strings. Extra fields in a row that
    are not in fieldnames are dropped (extrasaction="ignore").

    Args:
        path: Destination TSV path. Parent dirs are created if needed.
        rows: Rows to write.
        fieldnames: TSV header columns, in output order.

    Returns:
        Path to the written file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=fieldnames,
            delimiter="\t",
            extrasaction="ignore",
            restval="",
        )
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Wrote %d rows to %s", len(rows), path)
    return path


def run_five_database_merge(
    config: PipelineConfig,
    databases: tuple[str, ...] = DEFAULT_DATABASES,
    output_subdir: str = "merged",
) -> dict:
    """Merge per-database KGX outputs into a single 5-database graph.

    Steps:
        1. Collect nodes.tsv and edges.tsv paths for each requested database.
        2. merge_kgx -> deduplicated merged node and edge lists.
        3. inject_stubs -> stub nodes for dangling cross-pipeline references.
        4. Write merged/nodes.tsv and merged/edges.tsv.
        5. validate_merge -> dangling, duplicate, and provenance checks.
        6. generate_merge_report -> markdown summary with cross-pipeline
           connectivity counts.

    Args:
        config: Pipeline configuration providing kgx_output_dir.
        databases: Tuple of database names to include. Defaults to the full
                   5-database set (gene, clinvar, medgen, pubmed, taxonomy).
        output_subdir: Subdirectory name under kgx_output_dir for the merged
                       outputs. Defaults to "merged".

    Returns:
        Dict with keys:
            databases_found: list[str] - databases whose files were located
            databases_requested: list[str] - databases requested via argument
            nodes_path: Path to merged nodes.tsv
            edges_path: Path to merged edges.tsv
            report_path: Path to merge_report.md
            stub_count: int - number of stub nodes injected
            validation: dict - output of validate_merge
            node_count: int - total merged nodes including stubs
            edge_count: int - total merged edges after dedup
    """
    logger.info(
        "Starting 5-database merge: kgx_output_dir=%s databases=%s",
        config.kgx_output_dir,
        list(databases),
    )

    # Step 1: collect input paths
    node_paths, edge_paths, found = _collect_input_paths(
        config.kgx_output_dir, databases
    )
    if not node_paths:
        raise FileNotFoundError(
            f"No KGX inputs found under {config.kgx_output_dir}. "
            f"Looked for databases: {list(databases)}."
        )
    logger.info("Merging %d databases: %s", len(found), found)

    # Step 2: merge + dedup
    merged_nodes, merged_edges = merge_kgx(node_paths, edge_paths)

    # Step 3: inject stubs for dangling edge endpoints
    stubs = inject_stubs(merged_nodes, merged_edges)
    if stubs:
        merged_nodes.extend(stubs)
        logger.info("Extended merged nodes with %d stubs", len(stubs))

    # Step 4: write merged KGX
    output_dir = config.kgx_output_dir / output_subdir
    node_fieldnames = _union_fieldnames(merged_nodes, NODE_FIELDNAMES)
    edge_fieldnames = _union_fieldnames(merged_edges, EDGE_FIELDNAMES)
    nodes_path = _write_tsv(output_dir / "nodes.tsv", merged_nodes, node_fieldnames)
    edges_path = _write_tsv(output_dir / "edges.tsv", merged_edges, edge_fieldnames)

    # Step 5: validate
    validation = validate_merge(merged_nodes, merged_edges)

    # Step 6: report
    report_path = generate_merge_report(
        merged_nodes, merged_edges, validation, output_dir / "merge_report.md"
    )

    logger.info(
        "5-database merge complete: nodes=%d edges=%d stubs=%d validation_passed=%s "
        "nodes_path=%s edges_path=%s report_path=%s",
        len(merged_nodes),
        len(merged_edges),
        len(stubs),
        validation.get("passed"),
        nodes_path,
        edges_path,
        report_path,
    )

    return {
        "databases_found": found,
        "databases_requested": list(databases),
        "nodes_path": nodes_path,
        "edges_path": edges_path,
        "report_path": report_path,
        "stub_count": len(stubs),
        "validation": validation,
        "node_count": len(merged_nodes),
        "edge_count": len(merged_edges),
    }
