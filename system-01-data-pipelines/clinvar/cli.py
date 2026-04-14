"""cli.py - Click CLI entry point for the ClinVar ETL pipeline.

Registered as the `clinvar-etl` command in pyproject.toml.

Depends on:
    - system-01-data-pipelines/shared/config.py
    - system-01-data-pipelines/clinvar/pipeline.py

Usage:
    clinvar-etl [OPTIONS]

Options:
    --assembly TEXT        Genome assembly to filter on (default: GRCh38).
    --skip-download        Skip FTP downloads; use cached files.
    --force-download       Re-download files even if cached copies exist.
"""

import logging
import sys
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.config import PipelineConfig
from clinvar.pipeline import run_clinvar_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@click.command("clinvar-etl")
@click.option(
    "--assembly",
    default="GRCh38",
    show_default=True,
    help="Genome assembly to filter variant_summary on.",
)
@click.option(
    "--skip-download",
    is_flag=True,
    default=False,
    help="Skip FTP downloads and use cached files.",
)
@click.option(
    "--force-download",
    is_flag=True,
    default=False,
    help="Re-download FTP files even when a cached copy exists.",
)
def main(assembly: str, skip_download: bool, force_download: bool) -> None:
    """Run the ClinVar ETL pipeline.

    Downloads variant_summary.txt.gz and var_citations.txt from the NCBI
    ClinVar FTP server, parses them into BioLink-compliant KGX files, and
    writes nodes.tsv and edges.tsv to the configured KGX output directory.

    Configuration is loaded from environment variables or a .env file.
    Required: NCBI_EMAIL. Optional: NCBI_API_KEY, DATA_DIR, FTP_CACHE_DIR,
    KGX_OUTPUT_DIR, RAW_DATA_DIR, PG_*.
    """
    try:
        config = PipelineConfig.from_env()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    if skip_download and force_download:
        logger.error("--skip-download and --force-download are mutually exclusive.")
        sys.exit(1)

    try:
        nodes_path, edges_path = run_clinvar_pipeline(
            config=config,
            assembly=assembly,
            skip_download=skip_download,
            force_download=force_download,
        )
    except FileNotFoundError as exc:
        logger.error("File not found: %s", exc)
        sys.exit(1)

    click.echo(f"Nodes: {nodes_path}")
    click.echo(f"Edges: {edges_path}")


if __name__ == "__main__":
    main()
