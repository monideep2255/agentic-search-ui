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


def parse_gene2go(
    path: Path,
    tax_id: int | None = None,
) -> tuple[list[dict], list[dict]]:
    """Parse gene2go.gz into GO term nodes and gene-GO edges.

    Reads the file line by line. Deduplicates GO nodes by GO ID so that
    each GO term appears only once in the output even when referenced by
    many genes. Edges are not deduplicated since the same gene-GO pair
    can appear with different evidence codes.

    Args:
        path: Local path to the gzip-compressed gene2go file.
        tax_id: NCBI Taxonomy ID to filter on (e.g. 9606 for human).
                If None, all organisms are parsed.

    Returns:
        Tuple of (go_nodes, go_edges) where each element is a list of
        BioLink-compliant dicts ready for KGX export.

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If a required BioLink field is empty.
    """
    logger.info("Parsing gene2go from %s (tax_id=%s)", path, tax_id)

    go_nodes: dict[str, dict] = {}  # keyed by GO CURIE to deduplicate
    go_edges: list[dict] = []
    skipped = 0
    tax_id_str = str(tax_id) if tax_id is not None else None

    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")

            if line.startswith("#"):
                continue

            fields = line.split("\t")
            if len(fields) < 8:
                skipped += 1
                continue

            row_tax_id = fields[0].strip()
            gene_id = fields[1].strip()
            raw_go_id = fields[2].strip()
            evidence = fields[3].strip()
            # fields[4] = Qualifier, skip
            go_term = fields[5].strip()
            # fields[6] = PubMed, skip
            category = fields[7].strip()

            if not gene_id or gene_id == "-":
                skipped += 1
                continue

            if tax_id_str is not None and row_tax_id != tax_id_str:
                continue

            if category not in CATEGORY_MAP:
                logger.debug("Unknown GO category %r for gene %s, skipping", category, gene_id)
                skipped += 1
                continue

            predicate, node_category = CATEGORY_MAP[category]
            go_curie = _format_go_id(raw_go_id)
            gene_curie = f"NCBIGene:{gene_id}"
            gene_source_url = f"https://www.ncbi.nlm.nih.gov/gene/{gene_id}"
            go_source_url = f"http://amigo.geneontology.org/amigo/term/{go_curie}"

            # Build GO node (deduplicated)
            if go_curie not in go_nodes:
                go_name = go_term if go_term and go_term != "-" else go_curie
                try:
                    go_node = map_node(
                        id=go_curie,
                        category=node_category,
                        name=go_name,
                        source=GO_SOURCE,
                        source_url=go_source_url,
                    )
                    go_nodes[go_curie] = go_node
                except ValueError as exc:
                    logger.warning("Skipping GO node %s: %s", go_curie, exc)
                    skipped += 1
                    continue

            # Build gene-GO edge
            try:
                edge = map_edge(
                    subject=gene_curie,
                    predicate=predicate,
                    object=go_curie,
                    source=GENE_SOURCE,
                    source_url=gene_source_url,
                    evidence_code=evidence,
                )
                go_edges.append(edge)
            except ValueError as exc:
                logger.warning(
                    "Skipping GO edge %s -[%s]-> %s: %s",
                    gene_curie,
                    predicate,
                    go_curie,
                    exc,
                )
                skipped += 1

    logger.info(
        "gene2go parse complete: %d GO nodes, %d GO edges, %d skipped",
        len(go_nodes),
        len(go_edges),
        skipped,
    )
    return list(go_nodes.values()), go_edges
