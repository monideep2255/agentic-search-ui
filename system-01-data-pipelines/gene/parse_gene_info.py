"""parse_gene_info.py - Parse gene_info.gz into BioLink Gene nodes and in_taxon edges.

Reads the tab-separated, gzip-compressed gene_info file from NCBI Gene FTP.
Produces Gene nodes with cross-references (HGNC, OMIM, Ensembl, UniProt) and
one in_taxon edge per gene linking it to its NCBI Taxon node.

Depends on:
    - system-01-data-pipelines/shared/biolink_mapper (map_node, map_edge)

Reads:
    - config.ftp_cache_dir/gene_info.gz

Column layout (0-indexed):
    0  tax_id
    1  GeneID
    2  Symbol
    3  LocusTag
    4  Synonyms
    5  dbXrefs
    6  chromosome
    7  map_location
    8  description
    9  type_of_gene
    10 Symbol_from_nomenclature_authority
    11 Full_name_from_nomenclature_authority
    12 Nomenclature_status
    13 Other_designations
    14 Modification_date
    15 Feature_type
"""

import gzip
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.biolink_mapper import map_edge, map_node

logger = logging.getLogger(__name__)

GENE_SOURCE = "NCBI Gene"


def _parse_dbxrefs(dbxrefs_str: str) -> dict:
    """Parse the dbXrefs column into typed cross-reference lists.

    The dbXrefs column contains pipe-separated key:value pairs.
    Example: "HGNC:HGNC:1100|MIM:143100|Ensembl:ENSG00000121410"

    Args:
        dbxrefs_str: Raw dbXrefs column value. "-" means no xrefs.

    Returns:
        Dict with keys hgnc_id (str or None), omim_ids (list[str]),
        ensembl_ids (list[str]).
    """
    result: dict = {
        "hgnc_id": None,
        "omim_ids": [],
        "ensembl_ids": [],
    }

    if not dbxrefs_str or dbxrefs_str == "-":
        return result

    for xref in dbxrefs_str.split("|"):
        xref = xref.strip()
        if not xref or xref == "-":
            continue

        if xref.startswith("HGNC:HGNC:"):
            # Format: HGNC:HGNC:NNN -> store as HGNC:NNN
            result["hgnc_id"] = "HGNC:" + xref[len("HGNC:HGNC:"):]
        elif xref.startswith("HGNC:"):
            result["hgnc_id"] = xref
        elif xref.startswith("MIM:"):
            result["omim_ids"].append("OMIM:" + xref[4:])
        elif xref.startswith("Ensembl:"):
            result["ensembl_ids"].append(xref[8:])

    return result


def iter_gene_info(
    path: Path,
    tax_id: int | None = None,
):
    """Generator variant: yield one (node, edge) tuple per valid gene row.

    Used by the pipeline for streaming. Memory stays O(1) per row instead of
    O(67M) for the full list. Skipped rows do not yield anything.

    Args:
        path: Local path to the gzip-compressed gene_info file.
        tax_id: Optional NCBI Taxonomy ID filter.

    Yields:
        (gene_node_dict, taxon_edge_dict) — both BioLink-compliant dicts.

    Raises:
        FileNotFoundError: If path does not exist.
    """
    logger.info("Streaming gene_info from %s (tax_id=%s)", path, tax_id)
    tax_id_str = str(tax_id) if tax_id is not None else None

    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")
            if line.startswith("#"):
                continue

            fields = line.split("\t")
            if len(fields) < 10:
                continue

            row_tax_id = fields[0].strip()
            gene_id = fields[1].strip()
            symbol = fields[2].strip()
            dbxrefs_raw = fields[5].strip()
            chromosome = fields[6].strip()
            description = fields[8].strip()
            type_of_gene = fields[9].strip()

            if not gene_id or gene_id == "-":
                continue
            if tax_id_str is not None and row_tax_id != tax_id_str:
                continue

            name = description if description and description != "-" else symbol
            if not name or name == "-":
                name = f"Gene {gene_id}"

            node_id = f"NCBIGene:{gene_id}"
            source_url = f"https://www.ncbi.nlm.nih.gov/gene/{gene_id}"
            taxon_curie = f"NCBITaxon:{row_tax_id}"

            xrefs = _parse_dbxrefs(dbxrefs_raw)
            xrefs_list: list[str] = []
            if xrefs["hgnc_id"]:
                xrefs_list.append(xrefs["hgnc_id"])
            xrefs_list.extend(xrefs["omim_ids"])
            for ens in xrefs["ensembl_ids"]:
                xrefs_list.append(f"ENSEMBL:{ens}")

            extra: dict = {
                "symbol": symbol if symbol != "-" else "",
                "gene_type": type_of_gene if type_of_gene != "-" else "",
                "chromosome": chromosome if chromosome != "-" else "",
                "in_taxon": taxon_curie,
                "xrefs": xrefs_list,
                "hgnc_id": xrefs["hgnc_id"] or "",
                "omim_ids": xrefs["omim_ids"],
                "ensembl_ids": xrefs["ensembl_ids"],
            }

            try:
                node = map_node(
                    id=node_id,
                    category="biolink:Gene",
                    name=name,
                    source=GENE_SOURCE,
                    source_url=source_url,
                    **extra,
                )
            except ValueError as exc:
                logger.warning("Skipping gene %s: %s", gene_id, exc)
                continue

            try:
                edge = map_edge(
                    subject=node_id,
                    predicate="biolink:in_taxon",
                    object=taxon_curie,
                    source=GENE_SOURCE,
                    source_url=source_url,
                )
            except ValueError as exc:
                logger.warning("Skipping taxon edge for gene %s: %s", gene_id, exc)
                continue

            yield node, edge


def parse_gene_info(
    path: Path,
    tax_id: int | None = None,
) -> tuple[list[dict], list[dict]]:
    """List-returning wrapper around iter_gene_info. Use for tests only.

    Do NOT use in production pipelines — 67M gene nodes do not fit in RAM on
    a laptop-scale machine. The Gene pipeline uses iter_gene_info directly.

    Args:
        path: Local path to the gzip-compressed gene_info file.
        tax_id: NCBI Taxonomy ID to filter on. If None, all organisms.

    Returns:
        Tuple of (gene_nodes, taxon_edges) as lists.
    """
    logger.info("Parsing gene_info from %s (tax_id=%s) - LIST MODE", path, tax_id)
    gene_nodes: list[dict] = []
    taxon_edges: list[dict] = []
    for node, edge in iter_gene_info(path, tax_id=tax_id):
        gene_nodes.append(node)
        taxon_edges.append(edge)
    logger.info(
        "gene_info parse complete: %d gene nodes, %d taxon edges",
        len(gene_nodes),
        len(taxon_edges),
    )
    return gene_nodes, taxon_edges
