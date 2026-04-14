"""parse_id_mappings.py - Parse MedGenIDMappings.txt.gz for disease/phenotype nodes.

Groups rows by CUI to build one BioLink node per concept. Assigns MONDO IDs
as canonical identifiers when available, falls back to MedGen:{CUI}. Collects
OMIM, MeSH, Orphanet, SNOMED, and HPO identifiers as xrefs.

Depends on:
    - system-01-data-pipelines/shared/biolink_mapper.py

Reads:
    - config.ftp_cache_dir/MedGenIDMappings.txt.gz (gzipped, pipe-delimited)

Writes:
    - nothing (returns parsed data to pipeline.py)
"""

import gzip
import logging
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.biolink_mapper import map_node

logger = logging.getLogger(__name__)

# Semantic type fragments that map to BioLink categories
_DISEASE_STY_FRAGMENTS: tuple[str, ...] = (
    "Disease",
    "Syndrome",
    "Neoplastic Process",
)
_PHENOTYPIC_STY_FRAGMENTS: tuple[str, ...] = (
    "Finding",
    "Sign or Symptom",
)

# Source prefixes whose source_ids become xrefs
_XREF_SOURCES: frozenset[str] = frozenset(
    ["OMIM", "Orphanet", "MeSH", "SNOMED", "HPO", "SNOMEDCT_US"]
)


def _assign_category(sty: str) -> str:
    """Return the BioLink category for a MedGen semantic type string.

    Args:
        sty: Semantic type string from the STY column, e.g. "Disease or Syndrome".

    Returns:
        "biolink:Disease" or "biolink:PhenotypicFeature". Defaults to
        "biolink:Disease" when no fragment matches.
    """
    for fragment in _PHENOTYPIC_STY_FRAGMENTS:
        if fragment in sty:
            return "biolink:PhenotypicFeature"
    return "biolink:Disease"


def parse_id_mappings(path: Path) -> tuple[list[dict], dict[str, str]]:
    """Parse MedGenIDMappings.txt.gz and return BioLink nodes plus a CUI map.

    The file is gzipped and pipe-delimited with a header line starting with "#".
    Columns: CUI|source|source_id|source_name|STY|...

    For each CUI the function:
    - Sets the canonical node id to MONDO:{id} if any source_id starts with
      "MONDO:", otherwise uses MedGen:{CUI}.
    - Assigns biolink:Disease or biolink:PhenotypicFeature based on STY.
    - Uses the source_name from the MONDO row (or first row) as the node name.
    - Collects all source_ids from OMIM, Orphanet, MeSH, SNOMED, and HPO as xrefs.

    Args:
        path: Local path to MedGenIDMappings.txt.gz.

    Returns:
        Tuple of (nodes, cui_to_canonical_id) where nodes is a list of node
        dicts and cui_to_canonical_id maps each CUI to its final node id
        (MONDO:{id} or MedGen:{CUI}). The map is used by pipeline.py to
        rewrite edge references after MONDO promotion.
    """
    logger.info("Parsing MedGenIDMappings from %s", path)

    # Accumulate per-CUI data: {cui -> {"mondo_id": str|None, "name": str, "category": str, "xrefs": list}}
    cui_data: dict[str, dict] = {}

    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line_num, line in enumerate(fh, start=1):
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue

            parts = line.split("|")
            if len(parts) < 5:
                logger.debug("Line %d: too few columns, skipping", line_num)
                continue

            cui = parts[0].strip()
            source = parts[1].strip()
            source_id = parts[2].strip()
            source_name = parts[3].strip()
            sty = parts[4].strip() if len(parts) > 4 else ""

            if not cui or cui == "-":
                continue

            if cui not in cui_data:
                cui_data[cui] = {
                    "mondo_id": None,
                    "name": "",
                    "category": _assign_category(sty),
                    "xrefs": [],
                }

            entry = cui_data[cui]

            # Update category if we see a more specific STY
            if sty:
                entry["category"] = _assign_category(sty)

            # Prefer MONDO as canonical id
            if source == "MONDO" and source_id and source_id not in ("-", ""):
                entry["mondo_id"] = source_id
                if not entry["name"] and source_name and source_name != "-":
                    entry["name"] = source_name

            # Collect xrefs from known external sources
            if source in _XREF_SOURCES and source_id and source_id not in ("-", ""):
                xref = source_id if ":" in source_id else f"{source}:{source_id}"
                if xref not in entry["xrefs"]:
                    entry["xrefs"].append(xref)

            # Fill in name from first non-empty source_name
            if not entry["name"] and source_name and source_name not in ("-", ""):
                entry["name"] = source_name

    nodes: list[dict] = []
    cui_to_canonical_id: dict[str, str] = {}
    skipped = 0

    for cui, entry in cui_data.items():
        node_id = entry["mondo_id"] if entry["mondo_id"] else f"MedGen:{cui}"
        cui_to_canonical_id[cui] = node_id
        name = entry["name"] or cui  # fall back to CUI if no name found

        try:
            node = map_node(
                id=node_id,
                category=entry["category"],
                name=name,
                source="MedGen",
                source_url=f"https://www.ncbi.nlm.nih.gov/medgen/{cui}",
                xrefs=entry["xrefs"],
            )
            nodes.append(node)
        except ValueError as exc:
            logger.warning("Skipping CUI %s: %s", cui, exc)
            skipped += 1

    logger.info(
        "parse_id_mappings: %d nodes produced, %d skipped from %s",
        len(nodes),
        skipped,
        path.name,
    )
    return nodes, cui_to_canonical_id
