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


def iter_gene2pubmed(
    path: Path,
    tax_id: int | None = None,
):
    """Generator variant: yield one edge per valid row. O(1) memory.

    Yields:
        biolink:mentioned_in edge dict per row.
    """
    logger.info("Streaming gene2pubmed from %s (tax_id=%s)", path, tax_id)
    tax_id_str = str(tax_id) if tax_id is not None else None

    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")
            if line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) < 3:
                continue

            row_tax_id = fields[0].strip()
            gene_id = fields[1].strip()
            pubmed_id = fields[2].strip()

            if not gene_id or gene_id == "-":
                continue
            if not pubmed_id or pubmed_id == "-":
                continue
            if tax_id_str is not None and row_tax_id != tax_id_str:
                continue

            gene_curie = f"NCBIGene:{gene_id}"
            pmid_curie = f"PMID:{pubmed_id}"
            source_url = f"https://www.ncbi.nlm.nih.gov/gene/{gene_id}"

            try:
                yield map_edge(
                    subject=gene_curie,
                    predicate="biolink:mentioned_in",
                    object=pmid_curie,
                    source=GENE_SOURCE,
                    source_url=source_url,
                )
            except ValueError as exc:
                logger.warning(
                    "Skipping gene2pubmed edge %s -> %s: %s", gene_curie, pmid_curie, exc
                )


def parse_gene2pubmed(
    path: Path,
    tax_id: int | None = None,
) -> list[dict]:
    """List-returning wrapper around iter_gene2pubmed. Use for tests only.

    Do NOT use in production pipelines — 76M edges do not fit in RAM on a
    laptop-scale machine. The Gene pipeline uses iter_gene2pubmed directly.

    Args:
        path: Local path to the gzip-compressed gene2pubmed file.
        tax_id: NCBI Taxonomy ID to filter on. If None, all organisms.

    Returns:
        List of BioLink-compliant edge dicts.
    """
    edges = list(iter_gene2pubmed(path, tax_id=tax_id))
    logger.info("gene2pubmed parse complete: %d edges", len(edges))
    return edges
