"""parse_refseq_uniprot.py - Parse gene_refseq_uniprotkb_collab.gz for UniProt xrefs.

Reads the gzip-compressed RefSeq-UniProt collaboration file from NCBI Gene FTP.
Builds a dict mapping GeneID -> list of UniProt accessions. This data is used
by pipeline.py to enrich Gene nodes with uniprot_xrefs rather than producing
separate edges.

The file has variable column layouts across releases. The strategy is to scan
the header for column indices rather than relying on hardcoded positions.
Expected header contains at least:
    #NCBI_protein_accession  UniProtKB_protein_accession
A GeneID column may also be present. When absent, the mapping is by protein
accession only and GeneID is not available from this file; the function
returns an empty dict in that case and logs a warning.

Depends on:
    - stdlib: gzip, logging, pathlib

Reads:
    - config.ftp_cache_dir/gene_refseq_uniprotkb_collab.gz
"""

import gzip
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_refseq_uniprot(path: Path) -> dict[str, list[str]]:
    """Parse gene_refseq_uniprotkb_collab.gz and return GeneID -> UniProt accessions.

    Scans the header line to locate the GeneID and UniProtKB_protein_accession
    columns by name. If GeneID is not present in the header, logs a warning
    and returns an empty dict (the file version does not support this mapping).

    Multiple UniProt accessions for the same GeneID are accumulated into a list.
    If the same accession appears more than once for a given gene, it is
    deduplicated.

    Args:
        path: Local path to the gzip-compressed collaboration file.

    Returns:
        Dict mapping GeneID string (e.g. "672") to a deduplicated list of
        UniProt accession strings (e.g. ["P38398", "Q6IS14"]).
        Returns empty dict if GeneID column is not found.

    Raises:
        FileNotFoundError: If path does not exist.
    """
    logger.info("Parsing gene_refseq_uniprotkb_collab from %s", path)

    gene_to_uniprot: dict[str, list[str]] = {}
    seen: dict[str, set[str]] = {}  # for dedup within each gene

    gene_id_col: int | None = None
    uniprot_col: int | None = None
    header_parsed = False
    skipped = 0

    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")

            if not line:
                continue

            # The header line starts with # and defines column names
            if line.startswith("#"):
                # Strip leading # and split
                header_fields = line.lstrip("#").strip().split("\t")
                for idx, col_name in enumerate(header_fields):
                    col_clean = col_name.strip()
                    if col_clean in ("GeneID", "gene_id"):
                        gene_id_col = idx
                    elif col_clean in ("UniProtKB_protein_accession", "uniprot_accession"):
                        uniprot_col = idx
                header_parsed = True

                if gene_id_col is None:
                    logger.warning(
                        "GeneID column not found in %s header. "
                        "File may be a different version. Returning empty dict.",
                        path.name,
                    )
                    return {}
                if uniprot_col is None:
                    logger.warning(
                        "UniProtKB_protein_accession column not found in %s header. "
                        "Returning empty dict.",
                        path.name,
                    )
                    return {}
                continue

            if not header_parsed:
                # Data line before any header - skip
                skipped += 1
                continue

            fields = line.split("\t")

            if gene_id_col >= len(fields) or uniprot_col >= len(fields):
                skipped += 1
                continue

            gene_id = fields[gene_id_col].strip()
            uniprot_acc = fields[uniprot_col].strip()

            if not gene_id or gene_id == "-":
                skipped += 1
                continue

            if not uniprot_acc or uniprot_acc == "-":
                skipped += 1
                continue

            if gene_id not in gene_to_uniprot:
                gene_to_uniprot[gene_id] = []
                seen[gene_id] = set()

            if uniprot_acc not in seen[gene_id]:
                gene_to_uniprot[gene_id].append(uniprot_acc)
                seen[gene_id].add(uniprot_acc)

    logger.info(
        "gene_refseq_uniprotkb_collab parse complete: %d genes with UniProt xrefs, %d rows skipped",
        len(gene_to_uniprot),
        skipped,
    )
    return gene_to_uniprot
