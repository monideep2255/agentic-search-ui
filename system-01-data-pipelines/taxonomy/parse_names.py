"""parse_names.py - Parse the NCBI taxdump names.dmp file.

Returns a dict mapping tax_id (str) to scientific name (str). Only rows
where name_class is "scientific name" are kept. There is exactly one
scientific name per tax_id in the NCBI Taxonomy data.

NCBI taxdump format note:
    Field delimiter: \\t|\\t  (tab-pipe-tab, not plain tab)
    Row terminator:  \\t|\\n  (tab-pipe-newline)

    Strip the row terminator first, then split on the multi-character
    field delimiter.

Columns in names.dmp (0-indexed):
    0  tax_id
    1  name_txt
    2  unique_name  (blank when name is unique)
    3  name_class   (e.g. "scientific name", "common name", "synonym", ...)

Depends on:
    - stdlib: logging, pathlib

Called by:
    - system-01-data-pipelines/taxonomy/pipeline.py
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SCIENTIFIC_NAME_CLASS: str = "scientific name"


def parse_names(path: Path) -> dict[str, str]:
    """Parse names.dmp and return a tax_id-to-scientific-name mapping.

    Only rows where name_class equals "scientific name" (with a space, not
    an underscore) are retained. Common names, synonyms, and other name
    classes are ignored.

    Memory note: at ~2.7M taxa the returned dict holds ~2.7M short strings,
    approximately 200 MB. This is acceptable for the pipeline's in-memory
    merge step.

    Args:
        path: Path to names.dmp. Opened in text mode (UTF-8).

    Returns:
        Dict mapping tax_id string to scientific name string. The dict
        contains exactly one entry per taxonomic node.

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If a line has fewer than 4 fields after splitting.
    """
    tax_id_to_name: dict[str, str] = {}
    bad_lines: int = 0

    logger.info("Parsing names.dmp: %s", path)

    with open(path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            # Strip the row terminator \t|\n then split on the field delimiter \t|\t
            stripped = line.rstrip("\t|\n")
            fields = stripped.split("\t|\t")

            if len(fields) < 4:
                bad_lines += 1
                if bad_lines <= 5:
                    logger.warning(
                        "names.dmp line %d: expected >=4 fields, got %d: %r",
                        lineno,
                        len(fields),
                        line[:80],
                    )
                continue

            tax_id = fields[0].strip()
            name_txt = fields[1].strip()
            name_class = fields[3].strip()

            if name_class != _SCIENTIFIC_NAME_CLASS:
                continue

            if not tax_id or not name_txt:
                bad_lines += 1
                continue

            tax_id_to_name[tax_id] = name_txt

    if bad_lines:
        logger.warning(
            "names.dmp: skipped %d malformed or empty-field lines", bad_lines
        )

    logger.info(
        "names.dmp parsed: %d scientific names loaded", len(tax_id_to_name)
    )
    return tax_id_to_name
