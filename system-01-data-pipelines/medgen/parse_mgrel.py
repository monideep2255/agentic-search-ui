"""parse_mgrel.py - Parse MGREL.RRF.gz for hierarchical disease relationships.

Extracts child-parent (subclass_of) edges from the MedGen relationship file.
Only CHD (child) or isa relationships are processed; all others are skipped.

Depends on:
    - system-01-data-pipelines/shared/biolink_mapper.py

Reads:
    - config.ftp_cache_dir/MGREL.RRF.gz (gzipped, pipe-delimited)

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


def parse_mgrel(path: Path) -> list[dict]:
    """Parse MGREL.RRF.gz and return biolink:subclass_of edge dicts.

    The file is gzipped and pipe-delimited. Columns:
        CUI1 | AUI1 | STYPE1 | REL | CUI2 | AUI2 | STYPE2 | RELA | ...

    CUI1 is the child (subclass) and CUI2 is the parent (superclass). Only
    rows where REL == "CHD" or RELA == "isa" are processed. All other
    relationship types are silently skipped.

    Args:
        path: Local path to MGREL.RRF.gz.

    Returns:
        List of edge dicts, each with subject=MedGen:{CUI1},
        predicate=biolink:subclass_of, object=MedGen:{CUI2}, plus provenance.
    """
    logger.info("Parsing MGREL.RRF from %s", path)

    edges: list[dict] = []
    skipped = 0
    seen: set[tuple[str, str]] = set()

    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line_num, line in enumerate(fh, start=1):
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue

            parts = line.split("|")
            if len(parts) < 8:
                logger.debug("Line %d: too few columns, skipping", line_num)
                continue

            cui1 = parts[0].strip()
            rel = parts[3].strip()
            cui2 = parts[4].strip()
            rela = parts[7].strip()

            if not cui1 or not cui2 or cui1 == "-" or cui2 == "-":
                continue

            # Only process child-of or isa relationships
            if rel != "CHD" and rela != "isa":
                continue

            # Deduplicate by (child, parent) pair
            pair = (cui1, cui2)
            if pair in seen:
                continue
            seen.add(pair)

            try:
                edge = map_edge(
                    subject=f"MedGen:{cui1}",
                    predicate="biolink:subclass_of",
                    object=f"MedGen:{cui2}",
                    source="MedGen",
                    source_url=f"https://www.ncbi.nlm.nih.gov/medgen/{cui1}",
                )
                edges.append(edge)
            except ValueError as exc:
                logger.warning("Skipping line %d: %s", line_num, exc)
                skipped += 1

    logger.info(
        "parse_mgrel: %d subclass_of edges produced, %d skipped from %s",
        len(edges),
        skipped,
        path.name,
    )
    return edges
