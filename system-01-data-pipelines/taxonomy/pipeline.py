"""pipeline.py - Orchestrate the full NCBI Taxonomy ETL pipeline.

Downloads, parses, maps to BioLink, exports KGX TSVs, and validates the
result. This is the single entry point called by cli.py and by integration
tests.

Depends on:
    - system-01-data-pipelines/shared/config.py
    - system-01-data-pipelines/shared/biolink_mapper.py
    - system-01-data-pipelines/shared/kgx_exporter.py
    - system-01-data-pipelines/shared/validator.py
    - system-01-data-pipelines/taxonomy/download.py
    - system-01-data-pipelines/taxonomy/parse_nodes.py
    - system-01-data-pipelines/taxonomy/parse_names.py

Reads:
    - config.ftp_cache_dir/taxonomy/nodes.dmp
    - config.ftp_cache_dir/taxonomy/names.dmp

Writes:
    - config.kgx_output_dir/taxonomy/nodes.tsv
    - config.kgx_output_dir/taxonomy/edges.tsv
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.biolink_mapper import map_node, map_edge
from shared.config import PipelineConfig
from shared.kgx_exporter import export_kgx
from shared.validator import validate_all

from taxonomy.download import download_taxonomy_files
from taxonomy.parse_names import parse_names
from taxonomy.parse_nodes import parse_nodes

logger = logging.getLogger(__name__)


def run_taxonomy_pipeline(
    config: PipelineConfig,
    skip_download: bool = False,
    force_download: bool = False,
) -> tuple[Path, Path]:
    """Run the full NCBI Taxonomy ETL pipeline end-to-end.

    Steps:
        1. Download and extract taxdump.tar.gz (skipped if skip_download=True).
        2. Parse names.dmp -> tax_id-to-scientific-name dict.
        3. Parse nodes.dmp -> (partial_nodes, subclass_edges).
        4. Merge names into nodes; call map_node for each. Skip nameless nodes
           with a warning (should be zero in a valid taxdump).
        5. Call map_edge for each subclass_of edge.
        6. Export KGX TSVs to config.kgx_output_dir/taxonomy/.
        7. Run validate_all; log results.
        8. Return (nodes_path, edges_path).

    Args:
        config:         Pipeline configuration with ftp_cache_dir and
                        kgx_output_dir.
        skip_download:  If True, skip step 1 and read .dmp files from
                        config.ftp_cache_dir/taxonomy/.
        force_download: If True, re-download and re-extract even when cached
                        files exist. Ignored when skip_download=True.

    Returns:
        Tuple of (nodes_path, edges_path) for the written KGX TSV files.

    Raises:
        FileNotFoundError: If skip_download=True but nodes.dmp or names.dmp
                           is absent from the expected cache location.
        urllib.error.URLError: If the FTP download fails and
                               skip_download=False.
    """
    logger.info(
        "Taxonomy pipeline starting (skip_download=%s, force_download=%s)",
        skip_download,
        force_download,
    )

    # Step 1: Download and extract
    if skip_download:
        taxonomy_dir = _resolve_taxonomy_dir(config)
        logger.info("Skipping download; loading from %s", taxonomy_dir)
    else:
        taxonomy_dir = download_taxonomy_files(config, force=force_download)

    nodes_dmp = taxonomy_dir / "nodes.dmp"
    names_dmp = taxonomy_dir / "names.dmp"

    # Step 2: Parse names
    logger.info("Step 2: parsing names.dmp")
    tax_id_to_name: dict[str, str] = parse_names(names_dmp)

    # Step 3: Parse nodes and raw edges
    logger.info("Step 3: parsing nodes.dmp")
    partial_nodes, raw_edges = parse_nodes(nodes_dmp)

    # Step 4: Merge names, call map_node
    logger.info("Step 4: merging names and mapping %d nodes", len(partial_nodes))
    nodes: list[dict] = []
    no_name_count: int = 0

    for partial in partial_nodes:
        node_id: str = partial["id"]
        # Extract numeric tax_id from "NCBITaxon:{tax_id}"
        tax_id = node_id.split(":", 1)[1]
        name = tax_id_to_name.get(tax_id)

        if not name:
            no_name_count += 1
            if no_name_count <= 10:
                logger.warning(
                    "No scientific name for tax_id=%s (%s); skipping",
                    tax_id,
                    node_id,
                )
            continue

        mapped = map_node(
            id=node_id,
            category=partial["category"],
            name=name,
            source=partial["source"],
            source_url=partial["source_url"],
            rank=partial["rank"],
        )
        nodes.append(mapped)

    if no_name_count:
        logger.warning(
            "Step 4: skipped %d nodes with no scientific name", no_name_count
        )

    logger.info("Step 4 complete: %d nodes mapped", len(nodes))

    # Step 5: Map edges
    logger.info("Step 5: mapping %d subclass_of edges", len(raw_edges))
    edges: list[dict] = []

    for raw in raw_edges:
        mapped_edge = map_edge(
            subject=raw["subject"],
            predicate=raw["predicate"],
            object=raw["object"],
            source=raw["source"],
            source_url=raw["source_url"],
        )
        edges.append(mapped_edge)

    logger.info("Step 5 complete: %d edges mapped", len(edges))

    # Step 6: Export KGX TSVs
    logger.info("Step 6: exporting KGX TSVs")
    nodes_path, edges_path = export_kgx(
        nodes=nodes,
        edges=edges,
        output_dir=config.kgx_output_dir,
        database="taxonomy",
    )

    # Step 7: Validate
    logger.info("Step 7: running validation")
    validation = validate_all(nodes, edges, label="taxonomy")

    if not validation["passed"]:
        logger.warning(
            "Taxonomy pipeline completed with validation warnings: "
            "dangling=%d duplicates=%d missing_prov_nodes=%d missing_prov_edges=%d",
            len(validation["dangling_edges"]),
            len(validation["duplicate_nodes"]),
            len(validation["missing_provenance_nodes"]),
            len(validation["missing_provenance_edges"]),
        )
    else:
        logger.info("Taxonomy pipeline validation passed")

    logger.info(
        "Taxonomy pipeline complete: %d nodes, %d edges. "
        "nodes=%s edges=%s",
        len(nodes),
        len(edges),
        nodes_path,
        edges_path,
    )
    return nodes_path, edges_path


def _resolve_taxonomy_dir(config: PipelineConfig) -> Path:
    """Resolve the extracted taxonomy cache directory and verify required files.

    Args:
        config: Pipeline configuration with ftp_cache_dir.

    Returns:
        Path to the directory containing nodes.dmp and names.dmp.

    Raises:
        FileNotFoundError: If nodes.dmp or names.dmp is absent.
    """
    taxonomy_dir = config.ftp_cache_dir / "taxonomy"
    for filename in ("nodes.dmp", "names.dmp"):
        path = taxonomy_dir / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Required taxonomy file not found: {path}. "
                "Run without --skip-download to fetch and extract it."
            )
    return taxonomy_dir
