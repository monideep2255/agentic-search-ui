"""pipeline.py - Orchestrate the full PubMed ETL pipeline.

Coordinates download, streaming XML parse, streaming KGX export, MeSH stub
node generation, and validation for the PubMed database.

At 40M articles and up to 300M MeSH edges, this pipeline cannot hold all data
in memory. Every write is streamed:
- Article nodes are written row-by-row to nodes.tsv as they are parsed.
- MeSH edges are appended to edges.tsv one-article-at-a-time via append_edges.
- MeSH node stubs are accumulated as a set of UIs (not full dicts) then written
  after all files are processed.

Steps:
    1. Download all PubMed baseline + update XML files (optional skip)
    2. Initialize KGX edges file (streaming header only)
    3. Initialize KGX nodes file (streaming header only)
    4. For each XML file: parse articles, stream nodes and edges to disk
    5. Write MeSH stub nodes (appended to nodes.tsv)
    6. Validate: provenance spot-check on a sample of node IDs seen
    7. Log final counts and return (nodes_path, edges_path)

Depends on:
    - system-01-data-pipelines/pubmed/download.py
    - system-01-data-pipelines/pubmed/parse_pubmed_xml.py
    - system-01-data-pipelines/pubmed/parse_mesh_nodes.py
    - system-01-data-pipelines/shared/kgx_exporter.init_edges_file
    - system-01-data-pipelines/shared/kgx_exporter.append_edges
    - system-01-data-pipelines/shared/kgx_exporter.NODE_REQUIRED_COLUMNS
    - system-01-data-pipelines/shared/kgx_exporter.EDGE_REQUIRED_COLUMNS
    - system-01-data-pipelines/shared/config.PipelineConfig

Writes:
    - config.kgx_output_dir/pubmed/nodes.tsv
    - config.kgx_output_dir/pubmed/edges.tsv
"""

import csv
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import PipelineConfig
from shared.kgx_exporter import (
    EDGE_REQUIRED_COLUMNS,
    NODE_REQUIRED_COLUMNS,
    init_edges_file,
    serialize_value,
)
from shared.validator import validate_provenance

from pubmed.download import download_pubmed_files
from pubmed.parse_mesh_nodes import collect_mesh_nodes
from pubmed.parse_pubmed_xml import parse_pubmed_file

logger = logging.getLogger(__name__)

# Node columns for PubMed articles (description is optional but common)
NODE_FIELDNAMES: list[str] = NODE_REQUIRED_COLUMNS + ["description"]
EDGE_FIELDNAMES: list[str] = EDGE_REQUIRED_COLUMNS


def _init_nodes_file(output_dir: Path, database: str) -> Path:
    """Create nodes.tsv with header row only. Used for streaming writes.

    Args:
        output_dir: Root KGX output directory.
        database: Database name used as subdirectory (e.g. "pubmed").

    Returns:
        Path to the initialized nodes.tsv file.
    """
    dest_dir = output_dir / database
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / "nodes.tsv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=NODE_FIELDNAMES, delimiter="\t")
        writer.writeheader()
    logger.info("Initialized nodes file with %d columns at %s", len(NODE_FIELDNAMES), path)
    return path


def _append_nodes_batch(nodes: list[dict], nodes_path: Path) -> int:
    """Append a list of node dicts to an existing nodes.tsv file.

    Used for writing the MeSH stub nodes in one pass at the end of the pipeline.

    Args:
        nodes: List of node dicts to append.
        nodes_path: Path to an already-initialized nodes.tsv file.

    Returns:
        Number of nodes written.
    """
    with open(nodes_path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=NODE_FIELDNAMES,
            delimiter="\t",
            extrasaction="ignore",
            restval="",
        )
        for node in nodes:
            row = {field: serialize_value(node.get(field, "")) for field in NODE_FIELDNAMES}
            writer.writerow(row)
    logger.info("Appended %d nodes to %s", len(nodes), nodes_path)
    return len(nodes)


def run_pubmed_pipeline(
    config: PipelineConfig,
    skip_download: bool = False,
    force_download: bool = False,
    include_updates: bool = True,
) -> tuple[Path, Path]:
    """Run the complete PubMed ETL pipeline and return KGX output paths.

    Downloads all PubMed XML files (unless skip_download=True), then streams
    each file through the parser. Article nodes and MeSH edges are written to
    disk as each article is processed. No article dicts or edge dicts accumulate
    in memory between files.

    MeSH UIs are collected in a set during streaming (memory cost: ~3GB at 40M
    articles with 10+ MeSH terms each, but typically much less as the set only
    holds distinct UIs which number in the hundreds of thousands). MeSH stub
    nodes are written after all files are processed.

    Args:
        config: Pipeline configuration with ftp_cache_dir and kgx_output_dir set.
        skip_download: If True, use files already in config.ftp_cache_dir/pubmed/.
        force_download: If True, re-download all files even when cached.
                        Ignored when skip_download=True.
        include_updates: If True, also download and process pubmed/updatefiles/.

    Returns:
        Tuple of (nodes_path, edges_path) pointing to the written KGX TSV files.

    Raises:
        FileNotFoundError: If skip_download=True and no .xml.gz files exist in
                           config.ftp_cache_dir/pubmed/.
        urllib.error.URLError: If a download fails.
    """
    logger.info(
        "Starting PubMed ETL pipeline (skip_download=%s, include_updates=%s)",
        skip_download,
        include_updates,
    )

    # Step 1: Download (or locate cached files)
    if skip_download:
        cache_dir = config.ftp_cache_dir / "pubmed"
        xml_files = sorted(cache_dir.glob("*.xml.gz"))
        if not xml_files:
            raise FileNotFoundError(
                f"skip_download=True but no .xml.gz files found in {cache_dir}"
            )
        logger.info("Skip download: found %d cached .xml.gz files", len(xml_files))
    else:
        xml_files = download_pubmed_files(
            config, force=force_download, include_updates=include_updates
        )

    total_files = len(xml_files)
    logger.info("PubMed XML files to process: %d", total_files)

    # Step 2: Initialize KGX output files (header-only, streaming mode)
    edges_path = init_edges_file(config.kgx_output_dir, "pubmed", fieldnames=EDGE_FIELDNAMES)
    nodes_path = _init_nodes_file(config.kgx_output_dir, "pubmed")

    # Step 3: Stream all files. Keep nodes and edges files open across the
    # whole loop to avoid 40M+ open()/close() syscalls.
    mesh_uis_seen: set[str] = set()
    total_articles = 0
    total_edges = 0

    with open(nodes_path, "a", newline="", encoding="utf-8") as nodes_fh, \
         open(edges_path, "a", newline="", encoding="utf-8") as edges_fh:
        nodes_writer = csv.DictWriter(
            nodes_fh,
            fieldnames=NODE_FIELDNAMES,
            delimiter="\t",
            extrasaction="ignore",
            restval="",
        )
        edges_writer = csv.DictWriter(
            edges_fh,
            fieldnames=EDGE_FIELDNAMES,
            delimiter="\t",
            extrasaction="ignore",
            restval="",
        )

        for file_idx, xml_path in enumerate(xml_files, start=1):
            try:
                for article_node, mesh_edges in parse_pubmed_file(xml_path):
                    # Write article node row directly to the open writer
                    nodes_writer.writerow({
                        field: serialize_value(article_node.get(field, ""))
                        for field in NODE_FIELDNAMES
                    })
                    total_articles += 1

                    # Write MeSH edges; collect UIs for stub generation
                    if mesh_edges:
                        for edge in mesh_edges:
                            # object is "MeSH:D012345" - strip prefix to get raw UI
                            ui = edge["object"][5:]  # len("MeSH:") == 5
                            mesh_uis_seen.add(ui)
                            edges_writer.writerow({
                                field: serialize_value(edge.get(field, ""))
                                for field in EDGE_FIELDNAMES
                            })
                        total_edges += len(mesh_edges)

            except OSError as exc:
                logger.error("Cannot read %s: %s - skipping file", xml_path.name, exc)
                continue

            if file_idx % 100 == 0:
                # Flush periodically so progress is visible on disk
                nodes_fh.flush()
                edges_fh.flush()
                logger.info(
                    "Processed %d/%d files, %d articles so far, %d unique MeSH UIs",
                    file_idx,
                    total_files,
                    total_articles,
                    len(mesh_uis_seen),
                )

    logger.info(
        "All XML files processed: %d articles, %d MeSH edges, %d unique MeSH UIs",
        total_articles,
        total_edges,
        len(mesh_uis_seen),
    )

    # Step 4: Write MeSH stub nodes
    logger.info("Writing MeSH stub nodes...")
    mesh_nodes = collect_mesh_nodes(mesh_uis_seen)
    mesh_node_count = _append_nodes_batch(mesh_nodes, nodes_path)

    # Step 5: Spot-check provenance on a sample of MeSH nodes (full node list
    # is too large to re-read into memory; stub nodes are representative)
    if mesh_nodes:
        prov_issues = validate_provenance(mesh_nodes[:1000], label="pubmed_pipeline:mesh_nodes")
        if prov_issues:
            logger.warning(
                "Provenance issues in MeSH stub nodes: %d of %d sampled",
                len(prov_issues),
                min(1000, len(mesh_nodes)),
            )
        else:
            logger.info("MeSH stub node provenance check passed")

    # Step 6: Summary stats
    total_nodes = total_articles + mesh_node_count
    logger.info(
        "PubMed ETL pipeline complete: "
        "total_nodes=%d (articles=%d, mesh_stubs=%d), "
        "total_edges=%d (mesh_annotations=%d), "
        "nodes_file=%s edges_file=%s",
        total_nodes,
        total_articles,
        mesh_node_count,
        total_edges,
        total_edges,
        nodes_path,
        edges_path,
    )

    return nodes_path, edges_path
