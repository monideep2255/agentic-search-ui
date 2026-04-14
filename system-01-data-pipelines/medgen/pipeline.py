"""pipeline.py - Orchestrate the full MedGen ETL pipeline.

Downloads, parses, maps to BioLink, exports KGX TSVs, and validates the result.
This is the single entry point called by cli.py and by integration tests.

Depends on:
    - system-01-data-pipelines/shared/config.py
    - system-01-data-pipelines/shared/kgx_exporter.py
    - system-01-data-pipelines/shared/validator.py
    - system-01-data-pipelines/medgen/download.py
    - system-01-data-pipelines/medgen/parse_id_mappings.py
    - system-01-data-pipelines/medgen/parse_names.py
    - system-01-data-pipelines/medgen/parse_mgrel.py
    - system-01-data-pipelines/medgen/parse_pubmed_links.py
    - system-01-data-pipelines/medgen/parse_hpo_omim.py

Reads:
    - All MedGen FTP files under config.ftp_cache_dir

Writes:
    - config.kgx_output_dir/medgen/nodes.tsv
    - config.kgx_output_dir/medgen/edges.tsv
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.config import PipelineConfig
from shared.kgx_exporter import export_kgx
from shared.validator import validate_all

from medgen.download import download_medgen_files
from medgen.parse_id_mappings import parse_id_mappings
from medgen.parse_names import parse_names
from medgen.parse_mgrel import parse_mgrel
from medgen.parse_pubmed_links import parse_pubmed_links
from medgen.parse_hpo_omim import parse_hpo_omim

logger = logging.getLogger(__name__)


def run_medgen_pipeline(
    config: PipelineConfig,
    skip_download: bool = False,
) -> tuple[Path, Path]:
    """Run the full MedGen ETL pipeline end-to-end.

    Steps:
        1. Download MedGen FTP files (skipped if skip_download=True).
        2. Parse NAMES.RRF.gz -> CUI-to-name lookup dict.
        3. Parse MedGenIDMappings.txt.gz -> disease/phenotype nodes.
        4. Enrich node names from step 2 where id_mappings left them blank.
        5. Parse MGREL.RRF.gz -> hierarchy (subclass_of) edges.
        6. Parse medgen_pubmed_lnk.txt.gz -> mentioned_in edges.
        7. Parse MedGen_HPO_OMIM_Mapping.txt.gz -> close_match edges.
        8. Collect all nodes and edges.
        9. Export KGX TSVs to config.kgx_output_dir/medgen/.
        10. Validate with validate_all; log results.
        11. Return (nodes_path, edges_path).

    Args:
        config: Pipeline configuration with ftp_cache_dir and kgx_output_dir.
        skip_download: If True, skip step 1 and assume files are already in
                       ftp_cache_dir.

    Returns:
        Tuple of (nodes_path, edges_path) for the written KGX TSV files.

    Raises:
        FileNotFoundError: If skip_download=True but a required file is missing
                           from ftp_cache_dir.
        urllib.error.URLError: If download fails and skip_download=False.
    """
    logger.info("MedGen pipeline starting (skip_download=%s)", skip_download)

    # Step 1: Download
    if not skip_download:
        file_paths = download_medgen_files(config)
    else:
        logger.info("Skipping download; loading from cache")
        file_paths = _resolve_cached_paths(config)

    # Step 2: Parse names for enrichment
    logger.info("Step 2: parsing concept names")
    cui_to_name = parse_names(file_paths["names"])

    # Step 3: Parse id_mappings -> disease/phenotype nodes + CUI-to-canonical map
    logger.info("Step 3: parsing id_mappings")
    nodes, cui_to_canonical_id = parse_id_mappings(file_paths["id_mappings"])

    # Step 4: Enrich names from NAMES.RRF where id_mappings left them as CUI fallback
    logger.info("Step 4: enriching node names")
    nodes = _enrich_node_names(nodes, cui_to_name)

    # Step 5: Hierarchy edges
    logger.info("Step 5: parsing MGREL hierarchy")
    hierarchy_edges = parse_mgrel(file_paths["mgrel"])

    # Step 6: PubMed link edges
    logger.info("Step 6: parsing PubMed links")
    pubmed_edges = parse_pubmed_links(file_paths["pubmed_links"])

    # Step 7: HPO/OMIM mapping edges
    logger.info("Step 7: parsing HPO/OMIM mappings")
    mapping_edges = parse_hpo_omim(file_paths["hpo_omim"])

    # Step 7.5: Rewrite MedGen CUI references in edges to canonical IDs (MONDO where promoted)
    all_edges = hierarchy_edges + pubmed_edges + mapping_edges
    rewritten = _rewrite_edge_cuis(all_edges, cui_to_canonical_id)
    logger.info(
        "Collected %d nodes, %d edges (%d hierarchy, %d pubmed, %d hpo/omim), %d CUI refs rewritten",
        len(nodes),
        len(all_edges),
        len(hierarchy_edges),
        len(pubmed_edges),
        len(mapping_edges),
        rewritten,
    )

    # Step 9: Export
    logger.info("Step 9: exporting KGX TSVs")
    nodes_path, edges_path = export_kgx(
        nodes=nodes,
        edges=all_edges,
        output_dir=config.kgx_output_dir,
        database="medgen",
    )

    # Step 10: Validate
    logger.info("Step 10: running validation")
    validation = validate_all(nodes, all_edges, label="medgen")
    if not validation["passed"]:
        logger.warning(
            "MedGen pipeline completed with validation warnings: "
            "dangling=%d duplicates=%d missing_prov_nodes=%d missing_prov_edges=%d",
            len(validation["dangling_edges"]),
            len(validation["duplicate_nodes"]),
            len(validation["missing_provenance_nodes"]),
            len(validation["missing_provenance_edges"]),
        )
    else:
        logger.info("MedGen pipeline validation passed")

    logger.info(
        "MedGen pipeline complete. nodes=%s edges=%s",
        nodes_path,
        edges_path,
    )
    return nodes_path, edges_path


def _rewrite_edge_cuis(
    edges: list[dict],
    cui_to_canonical_id: dict[str, str],
) -> int:
    """Rewrite MedGen CUI references in edge subjects/objects to canonical IDs.

    After MONDO promotion in parse_id_mappings, some nodes have MONDO:{id}
    instead of MedGen:{CUI}. Edges from MGREL, pubmed_links, and hpo_omim
    still reference MedGen:{CUI}. This function rewrites those references
    so edges point to the actual node IDs.

    Modifies edges in place. Returns the count of rewritten references.
    """
    rewritten = 0
    for edge in edges:
        for field in ("subject", "object"):
            val = edge.get(field, "")
            if val.startswith("MedGen:"):
                cui = val[len("MedGen:"):]
                canonical = cui_to_canonical_id.get(cui)
                if canonical and canonical != val:
                    edge[field] = canonical
                    rewritten += 1
    if rewritten:
        logger.info("Rewrote %d MedGen CUI references to canonical IDs", rewritten)
    return rewritten


def _resolve_cached_paths(config: PipelineConfig) -> dict[str, Path]:
    """Build the expected local paths for all MedGen files.

    Args:
        config: Pipeline configuration with ftp_cache_dir.

    Returns:
        Dict mapping file key to expected local Path.

    Raises:
        FileNotFoundError: If any required file is absent from ftp_cache_dir.
    """
    key_to_filename = {
        "id_mappings": "MedGenIDMappings.txt.gz",
        "mgrel": "MGREL.RRF.gz",
        "names": "NAMES.RRF.gz",
        "pubmed_links": "medgen_pubmed_lnk.txt.gz",
        "hpo_omim": "MedGen_HPO_OMIM_Mapping.txt.gz",
    }
    paths: dict[str, Path] = {}
    for key, filename in key_to_filename.items():
        path = config.ftp_cache_dir / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Required MedGen file not found: {path}. "
                "Run without --skip-download to fetch it."
            )
        paths[key] = path
    return paths


def _enrich_node_names(nodes: list[dict], cui_to_name: dict[str, str]) -> list[dict]:
    """Fill in missing node names from the NAMES.RRF lookup.

    Extracts the CUI from node IDs of the form MedGen:{CUI} and looks up the
    name in cui_to_name. Nodes with a MONDO id (MONDO:...) are left unchanged
    since their names came from the MONDO source row in id_mappings.

    Args:
        nodes: List of node dicts from parse_id_mappings.
        cui_to_name: Dict mapping CUI to preferred name from parse_names.

    Returns:
        The same list of nodes with names updated in-place where applicable.
    """
    enriched = 0
    for node in nodes:
        node_id: str = node.get("id", "")
        current_name: str = node.get("name", "")

        # Only try to enrich MedGen:{CUI} nodes that have a CUI-like name
        if not node_id.startswith("MedGen:"):
            continue

        cui = node_id[len("MedGen:"):]
        if current_name and current_name != cui:
            # Already has a real name
            continue

        name_from_names = cui_to_name.get(cui, "")
        if name_from_names:
            node["name"] = name_from_names
            enriched += 1

    logger.info("_enrich_node_names: enriched %d node names from NAMES.RRF", enriched)
    return nodes
