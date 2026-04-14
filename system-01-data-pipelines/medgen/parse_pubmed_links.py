"""parse_pubmed_links.py - Parse medgen_pubmed_lnk.txt.gz for concept-publication edges.

Extracts biolink:mentioned_in edges linking MedGen concepts to PubMed articles.
Each concept-PMID pair becomes one edge with full provenance.

Depends on:
    - system-01-data-pipelines/shared/biolink_mapper.py

Reads:
    - config.ftp_cache_dir/medgen_pubmed_lnk.txt.gz (gzipped, tab-separated with header)

Writes:
    - nothing (returns parsed edge dicts to pipeline.py)
"""

import gzip
import logging
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.biolink_mapper import map_edge

logger = logging.getLogger(__name__)


def parse_pubmed_links(path: Path) -> list[dict]:
    """Parse medgen_pubmed_lnk.txt.gz and return biolink:mentioned_in edge dicts.

    The file is gzipped and tab-separated with a header line. Columns:
        UID (CUI) | PMID | ...

    Each row becomes one edge: MedGen:{UID} mentioned_in PMID:{PMID}.
    Rows with empty or invalid UID/PMID values are skipped with a debug log.

    Args:
        path: Local path to medgen_pubmed_lnk.txt.gz.

    Returns:
        List of edge dicts, each with subject=MedGen:{UID},
        predicate=biolink:mentioned_in, object=PMID:{PMID}, plus provenance.
    """
    logger.info("Parsing medgen_pubmed_lnk from %s", path)

    edges: list[dict] = []
    skipped = 0
    header_seen = False

    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line_num, line in enumerate(fh, start=1):
            line = line.rstrip("\n")
            if not line:
                continue

            # Skip comment lines
            if line.startswith("#"):
                continue

            parts = line.split("\t")
            if len(parts) < 2:
                logger.debug("Line %d: too few columns, skipping", line_num)
                continue

            uid = parts[0].strip()
            pmid = parts[1].strip()

            # Skip header row only when the first column is a known column label.
            # Real data rows have numeric UIDs or C-prefixed CUI strings.
            if not header_seen and uid.upper() in ("UID", "#UID", "CUI", "MEDGENCUI"):
                header_seen = True
                logger.debug("Skipped header line %d", line_num)
                continue
            header_seen = True

            if not uid or uid in ("-", "") or not pmid or pmid in ("-", ""):
                skipped += 1
                continue

            # Validate that UID and PMID look like integers
            if not uid.isdigit() and not uid.startswith("C"):
                skipped += 1
                continue
            if not pmid.isdigit():
                skipped += 1
                continue

            # CUIs start with C; numeric UIDs may be CUIs without the C prefix
            subject_id = f"MedGen:{uid}" if uid.startswith("C") else f"MedGen:C{uid.zfill(7)}"

            try:
                edge = map_edge(
                    subject=subject_id,
                    predicate="biolink:mentioned_in",
                    object=f"PMID:{pmid}",
                    source="MedGen",
                    source_url=f"https://www.ncbi.nlm.nih.gov/medgen/{uid}",
                )
                edges.append(edge)
            except ValueError as exc:
                logger.warning("Skipping line %d: %s", line_num, exc)
                skipped += 1

    logger.info(
        "parse_pubmed_links: %d mentioned_in edges produced, %d skipped from %s",
        len(edges),
        skipped,
        path.name,
    )
    return edges
