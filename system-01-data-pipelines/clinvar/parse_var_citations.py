"""parse_var_citations.py - Parse ClinVar var_citations.txt for citation edges.

Parses the plain-text, tab-separated var_citations.txt file. Produces
biolink:cited_in edges connecting ClinVar variants to PubMed articles.

Only PubMed citations are processed. Other citation sources (e.g. BookShelf,
OMIM) are skipped.

Depends on:
    - system-01-data-pipelines/shared/biolink_mapper.py

Reads:
    - config.ftp_cache_dir/var_citations.txt

Writes:
    - nothing (returns in-memory list to the pipeline orchestrator)
"""

import csv
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.biolink_mapper import map_edge

logger = logging.getLogger(__name__)

_MISSING_VALUES: frozenset[str] = frozenset(["-", "", "na", "NA", "n/a", "N/A"])


def _is_missing(value: str) -> bool:
    """Return True if value represents a missing/empty field."""
    return value.strip() in _MISSING_VALUES


def parse_var_citations(path: Path) -> list[dict]:
    """Parse var_citations.txt and return cited_in edge dicts.

    Reads the plain-text (not gzipped), tab-separated var_citations.txt file.
    Only rows where citation_source equals "PubMed" are processed. Other
    citation sources (e.g. BookShelf) are silently skipped.

    The file uses a tab-separated header. Columns expected:
        VariationID, AlleleID, citation_source, citation_id

    Args:
        path: Path to var_citations.txt (plain text, tab-separated).

    Returns:
        List of biolink:cited_in edge dicts. Each edge connects
        ClinVar:{VariationID} to PMID:{citation_id}.

    Raises:
        FileNotFoundError: If path does not exist.
        KeyError: If VariationID, citation_source, or citation_id columns
                  are missing from the header.
    """
    logger.info("Parsing %s", path)

    edges: list[dict] = []
    n_total = 0
    n_pubmed = 0
    n_skipped = 0

    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")

        # Validate required columns
        if reader.fieldnames is None:
            logger.warning("var_citations.txt appears to be empty: %s", path)
            return edges

        fieldnames_set = set(reader.fieldnames)
        required_cols = ["VariationID", "citation_source", "citation_id"]
        for col in required_cols:
            if col not in fieldnames_set:
                raise KeyError(
                    f"Expected column '{col}' not found in var_citations header. "
                    f"Available columns: {list(reader.fieldnames)}"
                )

        for row in reader:
            n_total += 1

            variation_id = row.get("VariationID", "").strip()
            citation_source = row.get("citation_source", "").strip()
            citation_id = row.get("citation_id", "").strip()

            if _is_missing(variation_id) or _is_missing(citation_id):
                n_skipped += 1
                continue

            if citation_source != "PubMed":
                n_skipped += 1
                continue

            n_pubmed += 1
            source_url = (
                f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{variation_id}"
            )

            edge = map_edge(
                subject=f"ClinVar:{variation_id}",
                predicate="biolink:cited_in",
                object=f"PMID:{citation_id}",
                source="ClinVar",
                source_url=source_url,
            )
            edges.append(edge)

    logger.info(
        "Parsed var_citations: %d total rows, %d PubMed edges produced, %d skipped.",
        n_total,
        n_pubmed,
        n_skipped,
    )
    return edges
