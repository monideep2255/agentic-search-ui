"""cli.py - Command-line entrypoint for the PubMed ETL pipeline.

Loads configuration from environment variables via PipelineConfig.from_env()
and delegates to run_pubmed_pipeline.

Usage:
    python -m pubmed.cli [OPTIONS]

Options:
    --skip-download   Skip the FTP download step; assume files are cached.
    --force-download  Re-download all files even when already cached.
    --no-updates      Skip the updatefiles/ directory (baseline only).

Depends on:
    - system-01-data-pipelines/pubmed/pipeline.run_pubmed_pipeline
    - system-01-data-pipelines/shared/config.PipelineConfig
    - click
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import click

from shared.config import PipelineConfig
from pubmed.pipeline import run_pubmed_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


@click.command("pubmed-etl")
@click.option(
    "--skip-download",
    is_flag=True,
    default=False,
    help="Skip FTP download; assume all XML files are already in the cache directory.",
)
@click.option(
    "--force-download",
    is_flag=True,
    default=False,
    help="Re-download all files even when already cached. Ignored if --skip-download is set.",
)
@click.option(
    "--no-updates",
    is_flag=True,
    default=False,
    help="Skip the pubmed/updatefiles/ directory and process baseline only.",
)
def main(skip_download: bool, force_download: bool, no_updates: bool) -> None:
    """Run the PubMed ETL pipeline.

    Downloads ~1334 baseline XML files (plus update files unless --no-updates),
    parses 40M articles, streams nodes and MeSH edges to KGX TSV files.

    Configuration is read from environment variables (NCBI_EMAIL, DATA_DIR, etc.)
    or a .env file in the current directory.
    """
    logger.info("PubMed ETL CLI starting")
    try:
        config = PipelineConfig.from_env()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    nodes_path, edges_path = run_pubmed_pipeline(
        config=config,
        skip_download=skip_download,
        force_download=force_download,
        include_updates=not no_updates,
    )

    logger.info("PubMed ETL complete.")
    logger.info("  nodes: %s", nodes_path)
    logger.info("  edges: %s", edges_path)


if __name__ == "__main__":
    main()
