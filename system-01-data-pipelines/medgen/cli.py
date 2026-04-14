"""cli.py - Click CLI entry point for the MedGen ETL pipeline.

Registered as the 'medgen-etl' command in pyproject.toml.

Usage:
    medgen-etl [--skip-download] [--force-download]

Depends on:
    - system-01-data-pipelines/shared/config.py
    - system-01-data-pipelines/medgen/pipeline.py
"""

import logging
import sys
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.config import PipelineConfig
from medgen.pipeline import run_medgen_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


@click.command(name="medgen-etl")
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
    help="Re-download all files even if cached copies exist.",
)
def main(skip_download: bool, force_download: bool) -> None:
    """Run the MedGen ETL pipeline.

    Downloads MedGen FTP files, parses disease/phenotype concepts and
    relationships, and exports BioLink-compliant KGX TSV files.

    By default, downloads are cached and skipped on subsequent runs.
    Use --force-download to refresh all files from NCBI.
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
        nodes_path, edges_path = run_medgen_pipeline(
            config=config,
            skip_download=skip_download,
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
