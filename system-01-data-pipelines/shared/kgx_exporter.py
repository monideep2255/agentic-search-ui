"""kgx_exporter.py - Write KGX-format TSV files (nodes.tsv + edges.tsv).

Produces tab-separated files with provenance on every row. No pandas dependency;
uses stdlib csv only so this module stays importable in minimal environments.

Depends on:
    - stdlib: csv, logging, pathlib

Writes:
    - data/kgx/<database>/nodes.tsv
    - data/kgx/<database>/edges.tsv

Depended by:
    - system-01-data-pipelines/gene/pipeline.py (planned)
    - system-01-data-pipelines/clinvar/pipeline.py (planned)
    - system-01-data-pipelines/medgen/pipeline.py (planned)
"""

import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Required columns define provenance and identity - non-negotiable on every row.
NODE_REQUIRED_COLUMNS: list[str] = ["id", "category", "name", "source", "source_url"]
EDGE_REQUIRED_COLUMNS: list[str] = ["subject", "predicate", "object", "source", "source_url"]

def serialize_value(value: object) -> str:
    """Serialize a value for TSV output. Pipe-join list/tuple values."""
    if isinstance(value, (list, tuple)):
        return "|".join(str(v) for v in value)
    if value is None:
        return ""
    return str(value)


def _build_fieldnames(
    records: list[dict],
    required: list[str],
) -> list[str]:
    """Derive ordered column list: required first, then extras sorted."""
    extra: set[str] = set()
    for rec in records:
        extra.update(rec.keys())
    extra -= set(required)
    return required + sorted(extra)


def _write_tsv(
    records: list[dict],
    path: Path,
    required_columns: list[str],
) -> Path:
    """Write records to a tab-separated file at path.

    Column order: required columns first, then any additional columns found
    in the data sorted alphabetically. Missing keys are written as empty string.
    List/tuple values are pipe-joined automatically.

    Parameters
    ----------
    records:
        List of dicts, one per row.
    path:
        Destination file path. Parent directory must exist.
    required_columns:
        Columns that appear first in the output, in order.

    Returns
    -------
    Path to the written file.
    """
    fieldnames = _build_fieldnames(records, required_columns)

    missing_provenance = sum(
        1 for r in records if not r.get("source") or not r.get("source_url")
    )
    if missing_provenance:
        logger.warning(
            "%d of %d records missing source or source_url in %s",
            missing_provenance,
            len(records),
            path.name,
        )

    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=fieldnames,
            delimiter="\t",
            extrasaction="ignore",
            restval="",
        )
        writer.writeheader()
        for rec in records:
            row: dict[str, str] = {}
            for field in fieldnames:
                raw = rec.get(field, "")
                row[field] = serialize_value(raw)
            writer.writerow(row)

    return path


def export_nodes(
    nodes: list[dict],
    output_dir: Path,
    database: str,
) -> Path:
    """Write nodes to output_dir/database/nodes.tsv.

    Creates the output directory if it does not exist. Column order is
    required columns first (id, category, name, source, source_url), then
    any additional columns found in the data sorted alphabetically. Missing
    keys are written as empty string. Multi-valued fields (xref, omim_ids,
    ensembl_ids) are joined with pipe.

    Parameters
    ----------
    nodes:
        List of node dicts. Each must contain at minimum: id, category,
        name, source, source_url.
    output_dir:
        Root KGX output directory (e.g. data/kgx/).
    database:
        Database name used as subdirectory (e.g. "gene", "clinvar").

    Returns
    -------
    Path to the written nodes.tsv file.
    """
    dest_dir = output_dir / database
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / "nodes.tsv"
    _write_tsv(nodes, path, NODE_REQUIRED_COLUMNS)
    logger.info("Wrote %d nodes to %s", len(nodes), path)
    return path


def export_edges(
    edges: list[dict],
    output_dir: Path,
    database: str,
) -> Path:
    """Write edges to output_dir/database/edges.tsv.

    Creates the output directory if it does not exist. Column order is
    required columns first (subject, predicate, object, source, source_url),
    then any additional columns found in the data sorted alphabetically.
    Missing keys are written as empty string. Multi-valued fields
    (supporting_publications) are joined with pipe.

    Parameters
    ----------
    edges:
        List of edge dicts. Each must contain at minimum: subject, predicate,
        object, source, source_url.
    output_dir:
        Root KGX output directory (e.g. data/kgx/).
    database:
        Database name used as subdirectory (e.g. "gene", "clinvar").

    Returns
    -------
    Path to the written edges.tsv file.
    """
    dest_dir = output_dir / database
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / "edges.tsv"
    _write_tsv(edges, path, EDGE_REQUIRED_COLUMNS)
    logger.info("Wrote %d edges to %s", len(edges), path)
    return path


def init_edges_file(
    output_dir: Path,
    database: str,
    fieldnames: list[str] | None = None,
) -> Path:
    """Create edges.tsv with header row only. Used for streaming writes.

    Args:
        output_dir: Root KGX output directory.
        database: Database name used as subdirectory.
        fieldnames: Column names. Defaults to EDGE_REQUIRED_COLUMNS if None.

    Returns:
        Path to the initialized edges.tsv file.
    """
    dest_dir = output_dir / database
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / "edges.tsv"
    cols = fieldnames or EDGE_REQUIRED_COLUMNS
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, delimiter="\t")
        writer.writeheader()
    logger.info("Initialized edges file with %d columns at %s", len(cols), path)
    return path


def append_edges(
    edges: list[dict],
    edges_path: Path,
    fieldnames: list[str] | None = None,
) -> int:
    """Append edges to an existing edges.tsv file. Frees memory after writing.

    Designed for large pipelines that cannot hold all edges in memory at once.
    Call init_edges_file first to create the header, then call this repeatedly
    for each batch of edges.

    Args:
        edges: List of edge dicts to append.
        edges_path: Path to the edges.tsv file (must already exist with header).
        fieldnames: Column names matching the header. Defaults to EDGE_REQUIRED_COLUMNS.

    Returns:
        Number of edges written.
    """
    cols = fieldnames or EDGE_REQUIRED_COLUMNS
    with open(edges_path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=cols,
            delimiter="\t",
            extrasaction="ignore",
            restval="",
        )
        for rec in edges:
            row = {field: serialize_value(rec.get(field, "")) for field in cols}
            writer.writerow(row)
    logger.info("Appended %d edges to %s", len(edges), edges_path)
    return len(edges)


def export_kgx(
    nodes: list[dict],
    edges: list[dict],
    output_dir: Path,
    database: str,
) -> tuple[Path, Path]:
    """Write both nodes.tsv and edges.tsv for a database.

    Convenience wrapper that calls export_nodes and export_edges in sequence.

    Parameters
    ----------
    nodes:
        List of node dicts with required provenance fields.
    edges:
        List of edge dicts with required provenance fields.
    output_dir:
        Root KGX output directory (e.g. data/kgx/).
    database:
        Database name used as subdirectory (e.g. "gene", "clinvar").

    Returns
    -------
    Tuple of (nodes_path, edges_path).
    """
    nodes_path = export_nodes(nodes, output_dir, database)
    edges_path = export_edges(edges, output_dir, database)
    return nodes_path, edges_path
