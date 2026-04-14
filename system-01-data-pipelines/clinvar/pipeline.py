"""pipeline.py - Orchestrate the full ClinVar ETL pipeline.

Runs five steps in order:
    1. Download FTP files (skippable via skip_download=True)
    2. Parse variant_summary.txt.gz -> variant nodes + gene/phenotype edges
    3. Parse var_citations.txt -> citation edges
    4. Export KGX TSV files (nodes.tsv + edges.tsv)
    5. Validate output (dangling edges, duplicates, provenance)

Depends on:
    - system-01-data-pipelines/shared/config.py
    - system-01-data-pipelines/shared/kgx_exporter.py
    - system-01-data-pipelines/shared/validator.py
    - system-01-data-pipelines/clinvar/download.py
    - system-01-data-pipelines/clinvar/parse_variant_summary.py
    - system-01-data-pipelines/clinvar/parse_var_citations.py

Writes:
    - config.kgx_output_dir/clinvar/nodes.tsv
    - config.kgx_output_dir/clinvar/edges.tsv
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.config import PipelineConfig
from shared.kgx_exporter import export_kgx
from shared.validator import validate_all

from clinvar.download import download_clinvar_files
from clinvar.parse_variant_summary import parse_variant_summary
from clinvar.parse_var_citations import parse_var_citations

logger = logging.getLogger(__name__)


def run_clinvar_pipeline(
    config: PipelineConfig,
    assembly: str = "GRCh38",
    skip_download: bool = False,
    force_download: bool = False,
) -> tuple[Path, Path]:
    """Run the full ClinVar ETL pipeline.

    Steps:
        1. Download variant_summary.txt.gz and var_citations.txt from NCBI FTP
           (skipped if skip_download=True or files already cached).
        2. Parse variant_summary.txt.gz: produces variant nodes, gene edges,
           and phenotype edges (filtered to the specified assembly).
        3. Parse var_citations.txt: produces cited_in edges (PubMed only).
        4. Export all nodes and edges to KGX TSV files.
        5. Validate output: dangling edges, duplicates, provenance.
        6. Log a summary of record counts and validation result.

    Validation uses validate_all() from shared.validator. Dangling citation
    edges (PMID objects that are not in the node set) are expected because
    Article nodes are produced by the PubMed pipeline, not ClinVar. The
    validation result is logged but does not halt the pipeline.

    Args:
        config:         Pipeline configuration. Controls FTP cache dir and KGX
                        output dir.
        assembly:       Genome assembly to filter variant_summary on.
                        Defaults to "GRCh38".
        skip_download:  If True, skip the download step and use cached files.
                        Raises FileNotFoundError if expected files are absent.
        force_download: If True, re-download files even if cached copies exist.

    Returns:
        Tuple of (nodes_path, edges_path) pointing to the written KGX files.

    Raises:
        FileNotFoundError: If skip_download=True and a required file is missing.
    """
    logger.info("=== ClinVar ETL pipeline start (assembly=%s) ===", assembly)

    # Step 1: Download
    if skip_download:
        logger.info("Step 1: Skipping download (skip_download=True)")
        file_paths = {
            "variant_summary": config.ftp_cache_dir / "variant_summary.txt.gz",
            "var_citations": config.ftp_cache_dir / "var_citations.txt",
        }
        for key, path in file_paths.items():
            if not path.exists():
                raise FileNotFoundError(
                    f"skip_download=True but {key} file not found: {path}"
                )
    else:
        logger.info("Step 1: Downloading ClinVar FTP files")
        file_paths = download_clinvar_files(config, force=force_download)

    # Step 2: Parse variant_summary
    logger.info("Step 2: Parsing variant_summary.txt.gz")
    variant_nodes, gene_edges, phenotype_edges = parse_variant_summary(
        file_paths["variant_summary"],
        assembly=assembly,
        chunk_size=100_000,
    )

    # Step 3: Parse var_citations
    logger.info("Step 3: Parsing var_citations.txt")
    citation_edges = parse_var_citations(file_paths["var_citations"])

    # Step 4: Combine and export
    logger.info("Step 4: Exporting KGX files")
    all_nodes = variant_nodes
    all_edges = gene_edges + phenotype_edges + citation_edges

    nodes_path, edges_path = export_kgx(
        nodes=all_nodes,
        edges=all_edges,
        output_dir=config.kgx_output_dir,
        database="clinvar",
    )

    # Step 5: Validate
    logger.info("Step 5: Validating output")
    validation_result = validate_all(all_nodes, all_edges, label="clinvar")

    # Step 6: Summary
    logger.info(
        "=== ClinVar ETL pipeline complete ===\n"
        "  Variant nodes:    %d\n"
        "  Gene edges:       %d\n"
        "  Phenotype edges:  %d\n"
        "  Citation edges:   %d\n"
        "  Total edges:      %d\n"
        "  Validation passed: %s\n"
        "  Nodes file: %s\n"
        "  Edges file: %s",
        len(variant_nodes),
        len(gene_edges),
        len(phenotype_edges),
        len(citation_edges),
        len(all_edges),
        validation_result["passed"],
        nodes_path,
        edges_path,
    )

    if not validation_result["passed"]:
        logger.warning(
            "Validation issues - dangling_edges=%d duplicate_nodes=%d "
            "missing_provenance_nodes=%d missing_provenance_edges=%d. "
            "Dangling citation edges (PMID objects) are expected until "
            "the PubMed pipeline runs.",
            len(validation_result["dangling_edges"]),
            len(validation_result["duplicate_nodes"]),
            len(validation_result["missing_provenance_nodes"]),
            len(validation_result["missing_provenance_edges"]),
        )

    return nodes_path, edges_path
