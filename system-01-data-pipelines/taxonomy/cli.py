"""cli.py - Click CLI entry point for the Taxonomy ETL pipeline.

Registered as the 'taxonomy-etl' command in pyproject.toml.

Usage:
    taxonomy-etl [--skip-download] [--force-download]

Depends on:
    - system-01-data-pipelines/shared/config.py
    - system-01-data-pipelines/taxonomy/pipeline.py
"""

import logging
import sys
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.config import PipelineConfig
from taxonomy.pipeline import run_taxonomy_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


@click.command(name="taxonomy-etl")
@click.option(
    "--skip-download",
    is_flag=True,
    default=False,
    help="Skip FTP download and use files already extracted in ftp_cache_dir/taxonomy/.",
)
@click.option(
    "--force-download",
    is_flag=True,
    default=False,
    help="Re-download and re-extract taxdump.tar.gz even if cached files exist.",
)
def main(skip_download: bool, force_download: bool) -> None:
    """Run the NCBI Taxonomy ETL pipeline.

    Downloads taxdump.tar.gz from the NCBI FTP server, extracts nodes.dmp
    and names.dmp, builds biolink:OrganismTaxon nodes and biolink:subclass_of
    edges, and exports BioLink-compliant KGX TSV files.

    By default, downloads are cached and skipped on subsequent runs.
    Use --force-download to refresh the archive from NCBI.
    """
    if skip_download and force_download:
        raise click.UsageError(
            "--skip-download and --force-download are mutually exclusive."
        )

    try:
        config = PipelineConfig.from_env()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    try:
        nodes_path, edges_path = run_taxonomy_pipeline(
            config=config,
            skip_download=skip_download,
            force_download=force_download,
        )
        click.echo(f"Nodes: {nodes_path}")
        click.echo(f"Edges: {edges_path}")
    except FileNotFoundError as exc:
        logger.error("Missing file: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.error("Pipeline failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
