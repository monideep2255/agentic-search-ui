"""cli.py - Click CLI entry point for the Gene ETL pipeline.

Entry point registered as gene-etl in pyproject.toml.

Usage:
    gene-etl [OPTIONS]

Options:
    --tax-id INTEGER    Filter to a single NCBI Taxonomy ID (e.g. 9606 for human).
                        Omit to process all organisms (large memory requirement).
    --skip-download     Skip FTP download and use files already in ftp_cache_dir.
    --force-download    Re-download all files even when cached. Ignored with
                        --skip-download.

Depends on:
    - system-01-data-pipelines/gene/pipeline.run_gene_pipeline
    - system-01-data-pipelines/shared/config.PipelineConfig
"""

import logging
import sys
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import PipelineConfig

from gene.pipeline import run_gene_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

logger = logging.getLogger(__name__)


@click.command(name="gene-etl")
@click.option(
    "--tax-id",
    type=int,
    default=None,
    help=(
        "NCBI Taxonomy ID to filter genes (e.g. 9606 for human). "
        "Omit to process all organisms."
    ),
)
@click.option(
    "--skip-download",
    is_flag=True,
    default=False,
    help="Skip FTP download and use files already in ftp_cache_dir.",
)
@click.option(
    "--force-download",
    is_flag=True,
    default=False,
    help="Re-download all files even when cached. Ignored with --skip-download.",
)
def main(tax_id: int | None, skip_download: bool, force_download: bool) -> None:
    """Run the NCBI Gene ETL pipeline and export BioLink-compliant KGX files.

    Downloads Gene FTP files, parses them into BioLink nodes and edges,
    and writes nodes.tsv and edges.tsv to the configured KGX output directory.

    Configuration is loaded from environment variables (or .env file at the
    repo root). At minimum, NCBI_EMAIL must be set.
    """
    try:
        config = PipelineConfig.from_env()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        raise SystemExit(1) from exc

    logger.info(
        "Gene ETL starting: tax_id=%s skip_download=%s force_download=%s",
        tax_id,
        skip_download,
        force_download,
    )

    nodes_path, edges_path = run_gene_pipeline(
        config=config,
        tax_id=tax_id,
        skip_download=skip_download,
        force_download=force_download,
    )

    click.echo(f"nodes: {nodes_path}")
    click.echo(f"edges: {edges_path}")


if __name__ == "__main__":
    main()
