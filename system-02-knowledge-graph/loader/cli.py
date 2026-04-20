"""cli.py - Click CLI for the AGE knowledge graph loader.

Registered as the 'age-load' command in pyproject.toml.

Usage:
    age-load --kgx-dir /path/to/merged --dsn "host=localhost ..."
    age-load --kgx-dir /path/to/merged --graph-name ncbi_kg --drop-existing

    AGE_DSN env var is accepted in place of --dsn.

Depends on:
    - system-02-knowledge-graph/loader/pipeline.py
    - click
    - stdlib: logging, sys, pathlib

Reads:
    - {kgx_dir}/nodes.tsv
    - {kgx_dir}/edges.tsv

Writes:
    - AGE graph, vertices, edges, and indexes in PostgreSQL (via pipeline.py)
"""

import logging
import sys
from pathlib import Path

import click

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


@click.command(name="age-load")
@click.option(
    "--kgx-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory containing merged nodes.tsv and edges.tsv.",
)
@click.option(
    "--graph-name",
    default="ncbi_kg",
    show_default=True,
    help="AGE graph name.",
)
@click.option(
    "--dsn",
    required=True,
    envvar="AGE_DSN",
    help="PostgreSQL DSN string (or set AGE_DSN env var).",
)
@click.option(
    "--drop-existing",
    is_flag=True,
    default=False,
    help="Drop and recreate graph before loading.",
)
@click.option(
    "--batch-size",
    default=500,
    show_default=True,
    help="UNWIND batch size for node and edge loading.",
)
def main(
    kgx_dir: Path,
    graph_name: str,
    dsn: str,
    drop_existing: bool,
    batch_size: int,
) -> None:
    """Load merged KGX files into PostgreSQL + Apache AGE."""
    # Import here so the module is importable without psycopg2 installed
    # (e.g. during --help or in test environments that mock the module).
    from .pipeline import run_age_load

    try:
        result = run_age_load(
            kgx_dir=kgx_dir,
            graph_name=graph_name,
            dsn=dsn,
            drop_existing=drop_existing,
            batch_size=batch_size,
        )
    except FileNotFoundError as exc:
        logger.error("Missing KGX inputs: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.error("AGE load failed: %s", exc, exc_info=True)
        sys.exit(1)

    click.echo(f"Graph: {graph_name}")
    click.echo(f"Nodes loaded: {result['nodes']}")
    click.echo(f"Edges loaded: {result['edges']}")


if __name__ == "__main__":
    main()
