"""parse_gene2go.py - Parse gene2go.gz into GO annotation nodes and edges.

Reads the tab-separated, gzip-compressed gene2go file from NCBI Gene FTP.
Produces GO term nodes (BiologicalProcess, MolecularActivity, CellularComponent)
and edges linking Gene nodes to GO terms via BioLink predicates.

Category-to-predicate mapping:
    Process  -> biolink:participates_in  (GO node: biolink:BiologicalProcess)
    Function -> biolink:actively_involved_in  (GO node: biolink:MolecularActivity)
    Component -> biolink:located_in  (GO node: biolink:CellularComponent)

Depends on:
    - system-01-data-pipelines/shared/biolink_mapper (map_node, map_edge)

Reads:
    - config.ftp_cache_dir/gene2go.gz

Column layout (0-indexed):
    0  tax_id
    1  GeneID
    2  GO_ID
    3  Evidence
    4  Qualifier
    5  GO_term
    6  PubMed
    7  Category
"""

import gzip
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.biolink_mapper import map_edge, map_node

logger = logging.getLogger(__name__)

GENE_SOURCE = "NCBI Gene"
GO_SOURCE = "Gene Ontology"

# Maps GO Category column value to (BioLink predicate, BioLink node category)
CATEGORY_MAP: dict[str, tuple[str, str]] = {
    "Process": ("biolink:participates_in", "biolink:BiologicalProcess"),
    "Function": ("biolink:actively_involved_in", "biolink:MolecularActivity"),
    "Component": ("biolink:located_in", "biolink:CellularComponent"),
}


def _format_go_id(raw_go_id: str) -> str:
    """Normalise a GO identifier to GO:NNNNNNN (7 digits).

    Args:
        raw_go_id: Raw GO ID from the file, e.g. "GO:0008150" or "0008150".

    Returns:
        Normalised CURIE e.g. "GO:0008150".
    """
    if raw_go_id.startswith("GO:"):
        local = raw_go_id[3:]
    else:
        local = raw_go_id
    return "GO:" + local.zfill(7)


def iter_gene2go(
    path: Path,
    tax_id: int | None = None,
):
    """Generator variant: yield (go_node_or_None, go_edge) per valid row.

    The first time a GO CURIE is encountered, the tuple contains both the
    new GO node and the edge. Subsequent rows for the same GO CURIE yield
    (None, edge). Caller accumulates GO nodes into an internal dict/set;
    edges stream straight to disk.

    Memory: O(unique_go_nodes) for the internal dedup set (~26K entries on
    real data, a few MB). Edges are yielded one at a time.

    Yields:
        (go_node_dict | None, gene_go_edge_dict) tuples.
    """
    logger.info("Streaming gene2go from %s (tax_id=%s)", path, tax_id)
    seen_go: set[str] = set()
    tax_id_str = str(tax_id) if tax_id is not None else None

    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")
            if line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) < 8:
                continue

            row_tax_id = fields[0].strip()
            gene_id = fields[1].strip()
            raw_go_id = fields[2].strip()
            evidence = fields[3].strip()
            go_term = fields[5].strip()
            category = fields[7].strip()

            if not gene_id or gene_id == "-":
                continue
            if tax_id_str is not None and row_tax_id != tax_id_str:
                continue
            if category not in CATEGORY_MAP:
                continue

            predicate, node_category = CATEGORY_MAP[category]
            go_curie = _format_go_id(raw_go_id)
            gene_curie = f"NCBIGene:{gene_id}"
            gene_source_url = f"https://www.ncbi.nlm.nih.gov/gene/{gene_id}"
            go_source_url = f"http://amigo.geneontology.org/amigo/term/{go_curie}"

            new_node = None
            if go_curie not in seen_go:
                go_name = go_term if go_term and go_term != "-" else go_curie
                try:
                    new_node = map_node(
                        id=go_curie,
                        category=node_category,
                        name=go_name,
                        source=GO_SOURCE,
                        source_url=go_source_url,
                    )
                    seen_go.add(go_curie)
                except ValueError as exc:
                    logger.warning("Skipping GO node %s: %s", go_curie, exc)
                    continue

            try:
                edge = map_edge(
                    subject=gene_curie,
                    predicate=predicate,
                    object=go_curie,
                    source=GENE_SOURCE,
                    source_url=gene_source_url,
                    evidence_code=evidence,
                )
            except ValueError as exc:
                logger.warning(
                    "Skipping GO edge %s -[%s]-> %s: %s",
                    gene_curie,
                    predicate,
                    go_curie,
                    exc,
                )
                continue

            yield new_node, edge


def parse_gene2go(
    path: Path,
    tax_id: int | None = None,
) -> tuple[list[dict], list[dict]]:
    """List-returning wrapper around iter_gene2go. Use for tests only.

    Do NOT use in production pipelines — 117M GO annotation edges do not fit
    in RAM on a laptop-scale machine.

    Args:
        path: Local path to the gzip-compressed gene2go file.
        tax_id: NCBI Taxonomy ID to filter on. If None, all organisms.

    Returns:
        Tuple of (go_nodes, go_edges) as deduplicated lists.
    """
    go_nodes: list[dict] = []
    go_edges: list[dict] = []
    for node, edge in iter_gene2go(path, tax_id=tax_id):
        if node is not None:
            go_nodes.append(node)
        go_edges.append(edge)
    logger.info(
        "gene2go parse complete: %d GO nodes, %d GO edges",
        len(go_nodes),
        len(go_edges),
    )
    return go_nodes, go_edges
