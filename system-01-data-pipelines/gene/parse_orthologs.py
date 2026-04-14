"""parse_orthologs.py - Parse gene_orthologs.gz into orthologous_to edges.

Reads the tab-separated, gzip-compressed gene_orthologs file from NCBI Gene FTP.
Produces biolink:orthologous_to edges between Gene nodes across different organisms.

When a tax_id filter is applied, edges where either GeneID or Other_GeneID belongs
to that organism are included. This captures all orthology relationships where the
target organism is one endpoint.

Depends on:
    - system-01-data-pipelines/shared/biolink_mapper (map_edge)

Reads:
    - config.ftp_cache_dir/gene_orthologs.gz

Column layout (0-indexed):
    0  tax_id
    1  GeneID
    2  relationship
    3  Other_tax_id
    4  Other_GeneID
"""

import gzip
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.biolink_mapper import map_edge

logger = logging.getLogger(__name__)

ORTHOLOGS_SOURCE = "NCBI Gene Orthologs"


def parse_orthologs(
    path: Path,
    tax_id: int | None = None,
) -> list[dict]:
    """Parse gene_orthologs.gz into biolink:orthologous_to edges.

    Each row produces one edge from NCBIGene:{GeneID} to
    NCBIGene:{Other_GeneID}. When tax_id is supplied, only rows where
    the given tax_id appears in either the tax_id or Other_tax_id column
    are included.

    Args:
        path: Local path to the gzip-compressed gene_orthologs file.
        tax_id: NCBI Taxonomy ID to filter on (e.g. 9606 for human).
                Includes edges where either endpoint belongs to this organism.
                If None, all orthology pairs are parsed.

    Returns:
        List of BioLink-compliant edge dicts ready for KGX export.

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If a required BioLink field is empty (from map_edge).
    """
    logger.info("Parsing gene_orthologs from %s (tax_id=%s)", path, tax_id)

    edges: list[dict] = []
    skipped = 0
    tax_id_str = str(tax_id) if tax_id is not None else None

    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")

            if line.startswith("#"):
                continue

            fields = line.split("\t")
            if len(fields) < 5:
                skipped += 1
                continue

            row_tax_id = fields[0].strip()
            gene_id = fields[1].strip()
            # fields[2] = relationship (e.g. "Ortholog"), kept for reference
            other_tax_id = fields[3].strip()
            other_gene_id = fields[4].strip()

            if not gene_id or gene_id == "-":
                skipped += 1
                continue

            if not other_gene_id or other_gene_id == "-":
                skipped += 1
                continue

            # Apply filter: include if either endpoint belongs to the target taxon
            if tax_id_str is not None:
                if row_tax_id != tax_id_str and other_tax_id != tax_id_str:
                    continue

            gene_curie = f"NCBIGene:{gene_id}"
            other_gene_curie = f"NCBIGene:{other_gene_id}"
            source_url = f"https://www.ncbi.nlm.nih.gov/gene/{gene_id}"

            try:
                edge = map_edge(
                    subject=gene_curie,
                    predicate="biolink:orthologous_to",
                    object=other_gene_curie,
                    source=ORTHOLOGS_SOURCE,
                    source_url=source_url,
                )
                edges.append(edge)
            except ValueError as exc:
                logger.warning(
                    "Skipping ortholog edge %s -> %s: %s",
                    gene_curie,
                    other_gene_curie,
                    exc,
                )
                skipped += 1

    logger.info(
        "gene_orthologs parse complete: %d edges, %d skipped",
        len(edges),
        skipped,
    )
    return edges
