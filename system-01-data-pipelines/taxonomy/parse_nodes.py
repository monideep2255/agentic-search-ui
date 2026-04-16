"""parse_nodes.py - Parse the NCBI taxdump nodes.dmp file.

Produces a list of partial biolink:OrganismTaxon node dicts (without names,
which come from names.dmp) and a list of biolink:subclass_of edge dicts
representing the parent-child hierarchy.

NCBI taxdump format note:
    Field delimiter: \\t|\\t  (tab-pipe-tab, not plain tab)
    Row terminator:  \\t|\\n  (tab-pipe-newline)

    Each line must have the row terminator stripped FIRST, then split on the
    multi-character field delimiter. Using split("\\t") or csv readers will
    silently mis-parse the last field.

Depends on:
    - stdlib: logging, pathlib

Called by:
    - system-01-data-pipelines/taxonomy/pipeline.py
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SOURCE: str = "NCBI Taxonomy"
_SOURCE_URL_TEMPLATE: str = (
    "https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id={tax_id}"
)


def parse_nodes(path: Path) -> tuple[list[dict], list[dict]]:
    """Parse nodes.dmp and return partial taxon nodes and subclass_of edges.

    Each row in nodes.dmp describes one taxon. The root taxon (tax_id == 1)
    is its own parent in the NCBI data; it does not produce a subclass_of
    edge to itself.

    Node dicts returned here are *partial*: the "name" field is set to None
    and must be filled in from names.dmp before calling map_node. This
    two-phase approach avoids holding two full datasets in memory simultaneously
    while names are merged.

    Fields in each partial node dict:
        id           - "NCBITaxon:{tax_id}"
        category     - "biolink:OrganismTaxon"
        name         - None (caller must fill this in)
        source       - "NCBI Taxonomy"
        source_url   - NCBI Taxonomy Browser URL for this taxon
        rank         - taxonomic rank string (e.g. "species", "genus")

    Fields in each edge dict:
        subject      - "NCBITaxon:{tax_id}"  (child)
        predicate    - "biolink:subclass_of"
        object       - "NCBITaxon:{parent_tax_id}"  (parent)
        source       - "NCBI Taxonomy"
        source_url   - NCBI Taxonomy Browser URL for the child taxon

    Args:
        path: Path to nodes.dmp. The file is opened in text mode; encoding
              is assumed to be UTF-8 / ASCII-safe (NCBI taxdump is ASCII).

    Returns:
        A tuple (partial_nodes, subclass_edges) where:
            partial_nodes   - list of partial node dicts (name=None)
            subclass_edges  - list of edge dicts (root excluded)

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If a line has fewer than 3 fields after splitting.
    """
    partial_nodes: list[dict] = []
    subclass_edges: list[dict] = []
    bad_lines: int = 0

    logger.info("Parsing nodes.dmp: %s", path)

    with open(path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            # Strip the row terminator \t|\n then split on the field delimiter \t|\t
            stripped = line.rstrip("\t|\n")
            fields = stripped.split("\t|\t")

            if len(fields) < 3:
                bad_lines += 1
                if bad_lines <= 5:
                    logger.warning(
                        "nodes.dmp line %d: expected >=3 fields, got %d: %r",
                        lineno,
                        len(fields),
                        line[:80],
                    )
                continue

            tax_id = fields[0].strip()
            parent_tax_id = fields[1].strip()
            rank = fields[2].strip()

            if not tax_id:
                bad_lines += 1
                continue

            source_url = _SOURCE_URL_TEMPLATE.format(tax_id=tax_id)

            partial_nodes.append(
                {
                    "id": f"NCBITaxon:{tax_id}",
                    "category": "biolink:OrganismTaxon",
                    "name": None,
                    "source": _SOURCE,
                    "source_url": source_url,
                    "rank": rank,
                }
            )

            # Root taxon (tax_id == parent_tax_id == "1") has no parent edge
            if parent_tax_id and parent_tax_id != tax_id:
                parent_url = _SOURCE_URL_TEMPLATE.format(tax_id=tax_id)
                subclass_edges.append(
                    {
                        "subject": f"NCBITaxon:{tax_id}",
                        "predicate": "biolink:subclass_of",
                        "object": f"NCBITaxon:{parent_tax_id}",
                        "source": _SOURCE,
                        "source_url": parent_url,
                    }
                )

    if bad_lines:
        logger.warning(
            "nodes.dmp: skipped %d malformed lines total", bad_lines
        )

    logger.info(
        "nodes.dmp parsed: %d taxon nodes, %d subclass_of edges",
        len(partial_nodes),
        len(subclass_edges),
    )
    return partial_nodes, subclass_edges
