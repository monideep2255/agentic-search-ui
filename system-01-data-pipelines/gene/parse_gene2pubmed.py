"""parse_gene2pubmed.py - Parse gene2pubmed.gz into gene-publication edges.

Reads the tab-separated, gzip-compressed gene2pubmed file from NCBI Gene FTP.
Produces biolink:mentioned_in edges from Gene nodes to Article nodes (PMID CURIEs).

Depends on:
    - system-01-data-pipelines/shared/biolink_mapper (map_edge)

Reads:
    - config.ftp_cache_dir/gene2pubmed.gz

Column layout (0-indexed):
    0  tax_id
    1  GeneID
    2  PubMed_ID
"""

import gzip
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.biolink_mapper import map_edge

logger = logging.getLogger(__name__)

GENE_SOURCE = "NCBI Gene"


def parse_gene2pubmed(
    path: Path,
    tax_id: int | None = None,
) -> list[dict]:
    """Parse gene2pubmed.gz into biolink:mentioned_in edges.

    Each row produces one edge from a Gene node to a PubMed Article node.
    Lines starting with # are skipped. Rows with missing GeneID or PubMed_ID
    are skipped with a warning.

    Args:
        path: Local path to the gzip-compressed gene2pubmed file.
        tax_id: NCBI Taxonomy ID to filter on (e.g. 9606 for human).
                If None, all organisms are parsed.

    Returns:
        List of BioLink-compliant edge dicts ready for KGX export.

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If a required BioLink field is empty (from map_edge).
    """
    logger.info("Parsing gene2pubmed from %s (tax_id=%s)", path, tax_id)

    edges: list[dict] = []
    skipped = 0
    tax_id_str = str(tax_id) if tax_id is not None else None

    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")

            if line.startswith("#"):
                continue

            fields = line.split("\t")
            if len(fields) < 3:
                skipped += 1
                continue

            row_tax_id = fields[0].strip()
            gene_id = fields[1].strip()
            pubmed_id = fields[2].strip()

            if not gene_id or gene_id == "-":
                skipped += 1
                continue

            if not pubmed_id or pubmed_id == "-":
                skipped += 1
                continue

            if tax_id_str is not None and row_tax_id != tax_id_str:
                continue

            gene_curie = f"NCBIGene:{gene_id}"
            pmid_curie = f"PMID:{pubmed_id}"
            source_url = f"https://www.ncbi.nlm.nih.gov/gene/{gene_id}"

            try:
                edge = map_edge(
                    subject=gene_curie,
                    predicate="biolink:mentioned_in",
                    object=pmid_curie,
                    source=GENE_SOURCE,
                    source_url=source_url,
                )
                edges.append(edge)
            except ValueError as exc:
                logger.warning(
                    "Skipping gene2pubmed edge %s -> %s: %s",
                    gene_curie,
                    pmid_curie,
                    exc,
                )
                skipped += 1

    logger.info(
        "gene2pubmed parse complete: %d edges, %d skipped",
        len(edges),
        skipped,
    )
    return edges
