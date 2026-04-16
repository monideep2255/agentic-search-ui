"""cli.py - Click CLI for the 5-database merge pipeline.

Registered as the 'merge-etl' command in pyproject.toml.

Usage:
    merge-etl [--databases gene,clinvar,medgen,pubmed,taxonomy]
              [--output-subdir merged]

Depends on:
    - system-01-data-pipelines/shared/config.py
    - system-01-data-pipelines/merge/pipeline.py
"""

import logging
import sys
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.config import PipelineConfig

from merge.pipeline import DEFAULT_DATABASES, run_five_database_merge

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


@click.command(name="merge-etl")
@click.option(
    "--databases",
    default=",".join(DEFAULT_DATABASES),
    show_default=True,
    help="Comma-separated list of database KGX subdirs to merge.",
)
@click.option(
    "--output-subdir",
    default="merged",
    show_default=True,
    help="Subdir name under KGX_OUTPUT_DIR for the merged output.",
)
def main(databases: str, output_subdir: str) -> None:
    """Merge per-database KGX outputs into a single graph.

    Loads nodes.tsv and edges.tsv from each requested database, deduplicates,
    injects stubs for dangling cross-pipeline references, validates, and
    writes merged outputs plus a markdown merge report.
    """
    dbs = tuple(db.strip() for db in databases.split(",") if db.strip())
    if not dbs:
        raise click.UsageError("--databases must contain at least one name.")

    try:
        config = PipelineConfig.from_env()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    try:
        result = run_five_database_merge(
            config=config,
            databases=dbs,
            output_subdir=output_subdir,
        )
    except FileNotFoundError as exc:
        logger.error("Missing KGX inputs: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.error("Merge pipeline failed: %s", exc, exc_info=True)
        sys.exit(1)

    click.echo(f"Databases merged: {result['databases_found']}")
    click.echo(f"Nodes: {result['nodes_path']} ({result['node_count']})")
    click.echo(f"Edges: {result['edges_path']} ({result['edge_count']})")
    click.echo(f"Stubs injected: {result['stub_count']}")
    click.echo(f"Validation passed: {result['validation'].get('passed')}")
    click.echo(f"Report: {result['report_path']}")


if __name__ == "__main__":
    main()
