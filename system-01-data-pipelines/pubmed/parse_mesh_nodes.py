"""parse_mesh_nodes.py - Build stub MeSH nodes from UIs collected during PubMed parsing.

These are minimal stubs that allow the knowledge graph to have complete nodes
for every MeSH term referenced in PubMed edges. The stub name is a placeholder;
if full MeSH descriptor names are needed, a separate MeSH XML descriptor download
can enrich these records in a future enhancement.

Depends on:
    - system-01-data-pipelines/shared/biolink_mapper.map_node

Called by:
    - system-01-data-pipelines/pubmed/pipeline.py
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.biolink_mapper import map_node

logger = logging.getLogger(__name__)

_MESH_CATEGORY = "biolink:OntologyClass"
_MESH_SOURCE = "MeSH (via PubMed)"


def _mesh_url(ui: str) -> str:
    """Build the canonical MeSH browser URL for a descriptor UI."""
    return f"https://meshb.nlm.nih.gov/record/ui?ui={ui}"


def collect_mesh_nodes(mesh_uis_seen: set[str]) -> list[dict]:
    """Build stub MeSH OntologyClass nodes from the set of UIs seen during parsing.

    Creates one node per unique MeSH UI. The name is a placeholder in the format
    "[MeSH] {ui}" because the PubMed XML does not carry canonical MeSH descriptor
    names (only the UI attribute). Full names can be loaded from the MeSH RDF
    descriptor download in a future enhancement.

    Args:
        mesh_uis_seen: Set of MeSH descriptor UI strings collected while parsing
                       PubMed articles (e.g. {"D012345", "D000818"}).

    Returns:
        List of BioLink OntologyClass node dicts, one per UI. Returns an empty
        list if mesh_uis_seen is empty.
    """
    if not mesh_uis_seen:
        logger.info("collect_mesh_nodes: no MeSH UIs provided, returning empty list")
        return []

    nodes: list[dict] = []
    for ui in sorted(mesh_uis_seen):  # sorted for deterministic output order
        node = map_node(
            id=f"MeSH:{ui}",
            category=_MESH_CATEGORY,
            name=f"[MeSH] {ui}",
            source=_MESH_SOURCE,
            source_url=_mesh_url(ui),
        )
        nodes.append(node)

    logger.info("collect_mesh_nodes: built %d MeSH stub nodes", len(nodes))
    return nodes
