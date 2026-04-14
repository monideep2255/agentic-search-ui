"""parse_names.py - Parse NAMES.RRF.gz for concept names and synonyms.

Builds a lookup dict mapping each CUI to its preferred display name. Used by
pipeline.py to enrich nodes from id_mappings that may be missing a name.

Depends on:
    - stdlib only (gzip, logging, pathlib)

Reads:
    - config.ftp_cache_dir/NAMES.RRF.gz (gzipped, pipe-delimited)

Writes:
    - nothing (returns lookup dict to pipeline.py)
"""

import gzip
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_names(path: Path) -> dict[str, str]:
    """Parse NAMES.RRF.gz and return a CUI-to-name mapping.

    The file is gzipped and pipe-delimited. Columns:
        CUI | name | source | SUPPRESS | ...

    For each CUI the first non-suppressed, non-empty name is kept. Rows where
    SUPPRESS is "Y" are skipped. If all rows for a CUI are suppressed, the
    first name regardless of suppression is used.

    Args:
        path: Local path to NAMES.RRF.gz.

    Returns:
        Dict mapping CUI strings to preferred name strings. CUIs that appear
        in the file but have only empty names are excluded from the result.
    """
    logger.info("Parsing NAMES.RRF from %s", path)

    # Two-pass accumulation: preferred (non-suppressed) then fallback
    preferred: dict[str, str] = {}
    fallback: dict[str, str] = {}

    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line_num, line in enumerate(fh, start=1):
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue

            parts = line.split("|")
            if len(parts) < 2:
                logger.debug("Line %d: too few columns, skipping", line_num)
                continue

            cui = parts[0].strip()
            name = parts[1].strip()
            suppress = parts[3].strip() if len(parts) > 3 else ""

            if not cui or cui == "-" or not name or name == "-":
                continue

            # Record fallback name for every CUI (first seen)
            if cui not in fallback:
                fallback[cui] = name

            # Record preferred name only for non-suppressed rows
            if suppress != "Y" and cui not in preferred:
                preferred[cui] = name

    # Merge: use preferred when available, fall back to any name
    result: dict[str, str] = {**fallback, **preferred}

    logger.info(
        "parse_names: %d CUI-to-name mappings loaded from %s",
        len(result),
        path.name,
    )
    return result
