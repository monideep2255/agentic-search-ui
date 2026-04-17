"""pipeline.py - Orchestrate the 5-database KGX merge (streaming).

Loads per-database KGX outputs (gene, clinvar, medgen, pubmed, taxonomy),
streams them through shared.merger.merge_kgx_streaming to a merged pair of
TSVs with stub injection for dangling cross-pipeline references, then emits
a markdown report summarising category and predicate counts and cross-
pipeline connectivity.

Memory profile: streams every input file one row at a time. Peak RAM is the
seen-node-id set (~8 GB at Gate-2 scale, ~116M CURIEs). Runs on a 33 GB
laptop without hitting OOM. See DECISIONS.md (2026-04-17) and
docs/learnings.md for the streaming refactor history.

Depends on:
    - system-01-data-pipelines/shared/config.PipelineConfig
    - system-01-data-pipelines/shared/merger.merge_kgx_streaming
    - system-01-data-pipelines/shared/merger._peek_fieldnames
    - system-01-data-pipelines/shared/kgx_exporter.init_nodes_file
    - system-01-data-pipelines/shared/kgx_exporter.init_edges_file
    - system-01-data-pipelines/shared/merge_report.generate_merge_report

Reads:
    - config.kgx_output_dir/<database>/nodes.tsv
    - config.kgx_output_dir/<database>/edges.tsv

Writes:
    - config.kgx_output_dir/merged/nodes.tsv
    - config.kgx_output_dir/merged/edges.tsv
    - config.kgx_output_dir/merged/merge_report.md
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import PipelineConfig
from shared.kgx_exporter import (
    EDGE_REQUIRED_COLUMNS,
    NODE_REQUIRED_COLUMNS,
    init_edges_file,
    init_nodes_file,
)
from shared.merge_report import generate_merge_report
from shared.merger import _peek_fieldnames, merge_kgx_streaming, stream_kgx_nodes, stream_kgx_edges

logger = logging.getLogger(__name__)

DEFAULT_DATABASES: tuple[str, ...] = ("gene", "clinvar", "medgen", "pubmed", "taxonomy")


def _collect_input_paths(
    kgx_output_dir: Path,
    databases: tuple[str, ...],
) -> tuple[list[Path], list[Path], list[str]]:
    """Collect nodes.tsv and edges.tsv paths for the requested databases.

    Databases missing either nodes.tsv or edges.tsv are skipped with a warning.

    Args:
        kgx_output_dir: Root KGX output directory.
        databases: Tuple of database names to include.

    Returns:
        (node_paths, edge_paths, found_databases).
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


def run_five_database_merge(
    config: PipelineConfig,
    databases: tuple[str, ...] = DEFAULT_DATABASES,
    output_subdir: str = "merged",
) -> dict:
    """Merge per-database KGX outputs into a single 5-database graph via streaming.

    Steps:
        1. Collect input paths for each requested database.
        2. Peek headers to compute union fieldnames for the merged output.
        3. Initialise merged/nodes.tsv and merged/edges.tsv with headers.
        4. merge_kgx_streaming -> two-pass streaming merge with inline stub injection.
        5. generate_merge_report -> markdown summary with cross-pipeline connectivity.

    Args:
        config: Pipeline configuration providing kgx_output_dir.
        databases: Tuple of database names to include. Defaults to the 5-db set.
        output_subdir: Subdirectory name under kgx_output_dir. Defaults to "merged".

    Returns:
        Dict with:
            databases_found: list[str]
            databases_requested: list[str]
            nodes_path: Path
            edges_path: Path
            report_path: Path
            stub_count: int
            validation: dict (passed, missing_provenance_*, category_counts, predicate_counts)
            node_count: int
            edge_count: int
    """
    logger.info(
        "Starting 5-database merge (streaming): kgx_output_dir=%s databases=%s",
        config.kgx_output_dir,
        list(databases),
    )

    # Step 1: collect
    node_paths, edge_paths, found = _collect_input_paths(
        config.kgx_output_dir, databases
    )
    if not node_paths:
        raise FileNotFoundError(
            f"No KGX inputs found under {config.kgx_output_dir}. "
            f"Looked for databases: {list(databases)}."
        )
    logger.info("Merging %d databases: %s", len(found), found)

    # Step 2: peek headers to compute union fieldnames
    node_fieldnames = _peek_fieldnames(node_paths, NODE_REQUIRED_COLUMNS)
    edge_fieldnames = _peek_fieldnames(edge_paths, EDGE_REQUIRED_COLUMNS)
    logger.info(
        "Union fieldnames: nodes=%d cols %s, edges=%d cols %s",
        len(node_fieldnames),
        node_fieldnames,
        len(edge_fieldnames),
        edge_fieldnames,
    )

    # Step 3: init merged output files
    output_dir = config.kgx_output_dir / output_subdir
    output_dir.mkdir(parents=True, exist_ok=True)
    nodes_path = init_nodes_file(
        config.kgx_output_dir, output_subdir, fieldnames=node_fieldnames
    )
    edges_path = init_edges_file(
        config.kgx_output_dir, output_subdir, fieldnames=edge_fieldnames
    )

    # Step 4: streaming merge + stub injection
    result = merge_kgx_streaming(
        node_files=node_paths,
        edge_files=edge_paths,
        output_nodes_path=nodes_path,
        output_edges_path=edges_path,
        node_fieldnames=node_fieldnames,
        edge_fieldnames=edge_fieldnames,
    )

    # Step 5: report
    # generate_merge_report expects merged_nodes + merged_edges lists in the
    # old API; pass the summary counts instead via a lightweight adapter.
    report_path = _write_streaming_merge_report(
        result=result,
        found_databases=found,
        report_path=output_dir / "merge_report.md",
    )

    logger.info(
        "5-database merge complete: nodes=%d edges=%d stubs=%d validation_passed=%s "
        "nodes_path=%s edges_path=%s report_path=%s",
        result["node_count"],
        result["edge_count"],
        result["stub_count"],
        result["validation"].get("passed"),
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
        "stub_count": result["stub_count"],
        "validation": result["validation"],
        "node_count": result["node_count"],
        "edge_count": result["edge_count"],
        "duplicate_nodes_dropped": result["duplicate_nodes_dropped"],
        "dangling_endpoints": result["dangling_endpoints"],
    }


def _write_streaming_merge_report(
    result: dict,
    found_databases: list[str],
    report_path: Path,
) -> Path:
    """Write a markdown merge report from streaming merge counts.

    The old generate_merge_report() walked the in-memory merged lists to
    compute cross-pipeline connectivity. Under streaming we write a lighter
    report with category / predicate distributions and merge summary. Detailed
    connectivity can be recomputed later via an awk pass on the merged files
    if needed.
    """
    validation = result["validation"]
    lines: list[str] = []
    lines.append("# 5-database merge report\n")
    lines.append(f"**Databases merged:** {', '.join(found_databases)}\n")
    lines.append("")
    lines.append("## Summary\n")
    lines.append(f"- Total nodes: {result['node_count']:,}")
    lines.append(f"- Total edges: {result['edge_count']:,}")
    lines.append(f"- Stubs injected: {result['stub_count']:,}")
    lines.append(f"- Duplicate nodes dropped: {result['duplicate_nodes_dropped']:,}")
    lines.append(f"- Dangling endpoints (resolved via stubs): {result['dangling_endpoints']:,}")
    lines.append(f"- Validation passed: {validation.get('passed')}")
    lines.append(f"- Missing provenance on nodes: {len(validation.get('missing_provenance_nodes', [])):,} (stubs count here)")
    lines.append(f"- Missing provenance on edges: {len(validation.get('missing_provenance_edges', [])):,}")
    lines.append("")
    lines.append("## Node categories\n")
    cc = validation.get("category_counts", {})
    for cat, n in sorted(cc.items(), key=lambda x: -x[1]):
        lines.append(f"- {cat}: {n:,}")
    lines.append("")
    lines.append("## Edge predicates\n")
    pc = validation.get("predicate_counts", {})
    for pred, n in sorted(pc.items(), key=lambda x: -x[1]):
        lines.append(f"- {pred}: {n:,}")
    lines.append("")
    lines.append("## Cross-pipeline connectivity\n")
    conn = result.get("connectivity", {})
    lines.append(f"- Gene mentioned_in PubMed Article edges resolved: {conn.get('gene_pmid_resolved', 0)}")
    lines.append(f"- Gene in_taxon NCBITaxon edges resolved: {conn.get('gene_taxon_resolved', 0)}")
    lines.append(f"- PubMed Article has_mesh_annotation MeSH edges resolved: {conn.get('pmid_mesh_resolved', 0)}")
    lines.append(f"- NCBITaxon subclass_of NCBITaxon edges resolved: {conn.get('taxon_subclass_resolved', 0)}")
    lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote merge report to %s", report_path)
    return report_path
