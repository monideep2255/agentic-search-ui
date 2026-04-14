"""parse_mim2gene.py - Parse mim2gene_medgen for gene-disease associations.

Reads the plain-text (not gzipped), tab-separated mim2gene_medgen file
from NCBI Gene FTP. Produces biolink:gene_associated_with_condition edges
from Gene nodes to MedGen disease nodes.

Rows where GeneID or MedGenCUI is "-" are skipped.

Depends on:
    - system-01-data-pipelines/shared/biolink_mapper (map_edge)

Reads:
    - config.ftp_cache_dir/mim2gene_medgen

Column layout (0-indexed):
    0  MIM_number
    1  GeneID
    2  type
    3  Source
    4  MedGenCUI
    5  Comment
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.biolink_mapper import map_edge

logger = logging.getLogger(__name__)

MIM2GENE_SOURCE = "NCBI MIM2Gene"


def parse_mim2gene(path: Path) -> list[dict]:
    """Parse mim2gene_medgen into gene_associated_with_condition edges.

    Only produces edges where both GeneID and MedGenCUI are present
    (i.e. not "-"). Rows with missing values are skipped silently (counted).

    Note: This file is NOT gzip-compressed. Open with plain open(), not
    gzip.open().

    Args:
        path: Local path to the plain-text mim2gene_medgen file.

    Returns:
        List of BioLink-compliant edge dicts ready for KGX export.

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If a required BioLink field is empty (from map_edge).
    """
    logger.info("Parsing mim2gene_medgen from %s", path)

    edges: list[dict] = []
    skipped = 0

    with open(path, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")

            # Skip comment lines
            if line.startswith("#"):
                continue

            fields = line.split("\t")
            if len(fields) < 5:
                skipped += 1
                continue

            # mim_number = fields[0].strip()  # not used in edge
            gene_id = fields[1].strip()
            # gene_type = fields[2].strip()  # not used in edge
            # source = fields[3].strip()  # not used in edge
            medgen_cui = fields[4].strip()

            if not gene_id or gene_id == "-":
                skipped += 1
                continue

            if not medgen_cui or medgen_cui == "-":
                skipped += 1
                continue

            gene_curie = f"NCBIGene:{gene_id}"
            medgen_curie = f"MedGen:{medgen_cui}"
            source_url = f"https://www.ncbi.nlm.nih.gov/gene/{gene_id}"

            try:
                edge = map_edge(
                    subject=gene_curie,
                    predicate="biolink:gene_associated_with_condition",
                    object=medgen_curie,
                    source=MIM2GENE_SOURCE,
                    source_url=source_url,
                )
                edges.append(edge)
            except ValueError as exc:
                logger.warning(
                    "Skipping mim2gene edge %s -> %s: %s",
                    gene_curie,
                    medgen_curie,
                    exc,
                )
                skipped += 1

    logger.info(
        "mim2gene_medgen parse complete: %d edges, %d skipped",
        len(edges),
        skipped,
    )
    return edges
