"""parse_hpo_omim.py - Parse MedGen_HPO_OMIM_Mapping.txt.gz for cross-reference edges.

Extracts biolink:close_match edges from MedGen concepts to HPO and OMIM identifiers.
Each valid HPO or OMIM mapping becomes one edge.

Depends on:
    - system-01-data-pipelines/shared/biolink_mapper.py

Reads:
    - config.ftp_cache_dir/MedGen_HPO_OMIM_Mapping.txt.gz (gzipped, pipe-delimited with header)

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

_EMPTY_VALUES: frozenset[str] = frozenset(["", "-", ".", "N/A", "na", "NA"])


def _is_valid(value: str) -> bool:
    """Return True if value is non-empty and not a placeholder."""
    return bool(value) and value not in _EMPTY_VALUES


def parse_hpo_omim(path: Path) -> list[dict]:
    """Parse MedGen_HPO_OMIM_Mapping.txt.gz and return biolink:close_match edges.

    The file is gzipped and pipe-delimited with a header line. Columns:
        #OMIM_CUI|MIM_number|OMIM_name|relationship|HPO_CUI|HPO_ID|HPO_name|MedGen_name|MedGen_source|STY|

    For each row:
    - If HPO_ID is valid: emit MedGen:{CUI} close_match HP:{HPO_ID}
    - If OMIM_ID is valid: emit MedGen:{CUI} close_match OMIM:{OMIM_ID}

    Both edges can be emitted from the same row. HPO IDs may arrive with or
    without the "HP:" prefix; the prefix is normalised before use.

    Args:
        path: Local path to MedGen_HPO_OMIM_Mapping.txt.gz.

    Returns:
        List of edge dicts, each with predicate=biolink:close_match plus
        subject, object, source, and source_url fields.
    """
    logger.info("Parsing MedGen_HPO_OMIM_Mapping from %s", path)

    edges: list[dict] = []
    skipped = 0
    header_seen = False

    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line_num, line in enumerate(fh, start=1):
            line = line.rstrip("\n")
            if not line:
                continue
            if line.startswith("#"):
                continue

            parts = line.split("|")
            if len(parts) < 3:
                logger.debug("Line %d: too few columns, skipping", line_num)
                continue

            # Columns: OMIM_CUI|MIM_number|OMIM_name|relationship|HPO_CUI|HPO_ID|HPO_name|...
            cui = parts[0].strip()
            omim_id_raw = parts[1].strip() if len(parts) > 1 else ""
            hpo_id_raw = parts[5].strip() if len(parts) > 5 else ""

            # Skip header row
            if not header_seen and (cui.upper() in ("CUI", "#CUI", "MEDGENCUI", "OMIM_CUI")):
                header_seen = True
                logger.debug("Skipped header line %d", line_num)
                continue
            header_seen = True

            if not _is_valid(cui):
                skipped += 1
                continue

            subject = f"MedGen:{cui}"
            source_url = f"https://www.ncbi.nlm.nih.gov/medgen/{cui}"

            # Emit HPO edge
            if _is_valid(hpo_id_raw):
                hpo_id = hpo_id_raw if hpo_id_raw.startswith("HP:") else f"HP:{hpo_id_raw}"
                try:
                    edge = map_edge(
                        subject=subject,
                        predicate="biolink:close_match",
                        object=hpo_id,
                        source="MedGen",
                        source_url=source_url,
                    )
                    edges.append(edge)
                except ValueError as exc:
                    logger.warning("Skipping HPO edge at line %d: %s", line_num, exc)
                    skipped += 1

            # Emit OMIM edge
            if _is_valid(omim_id_raw):
                omim_id = omim_id_raw if omim_id_raw.startswith("OMIM:") else f"OMIM:{omim_id_raw}"
                try:
                    edge = map_edge(
                        subject=subject,
                        predicate="biolink:close_match",
                        object=omim_id,
                        source="MedGen",
                        source_url=source_url,
                    )
                    edges.append(edge)
                except ValueError as exc:
                    logger.warning("Skipping OMIM edge at line %d: %s", line_num, exc)
                    skipped += 1

    logger.info(
        "parse_hpo_omim: %d close_match edges produced, %d skipped from %s",
        len(edges),
        skipped,
        path.name,
    )
    return edges
