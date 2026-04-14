"""parse_variant_summary.py - Parse ClinVar variant_summary.txt.gz.

Streams the gzipped tabular file line by line for memory safety (the file is
~500 MB uncompressed). Produces three lists:
    - variant_nodes:          biolink:SequenceVariant nodes
    - variant_gene_edges:     biolink:is_sequence_variant_of edges (Variant -> Gene)
    - variant_phenotype_edges: biolink:has_phenotype edges (Variant -> MedGen concept)

Filters to a single genome assembly (default GRCh38) to avoid duplicating
variants that appear for both GRCh37 and GRCh38.

Depends on:
    - system-01-data-pipelines/shared/biolink_mapper.py

Reads:
    - config.ftp_cache_dir/variant_summary.txt.gz

Writes:
    - nothing (returns in-memory lists to the pipeline orchestrator)
"""

import gzip
import logging
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.biolink_mapper import map_node, map_edge

logger = logging.getLogger(__name__)

_MISSING_VALUES: frozenset[str] = frozenset(["-", "", "na", "NA", "n/a", "N/A"])
_MEDGEN_PATTERN = re.compile(r"MedGen:([A-Z0-9]+)")


def _is_missing(value: str) -> bool:
    """Return True if value represents a missing/empty field."""
    return value.strip() in _MISSING_VALUES


def _parse_phenotype_ids(phenotype_ids_str: str) -> list[str]:
    """Extract MedGen CUIs from the PhenotypeIDS column.

    The PhenotypeIDS column contains entries like:
        "MedGen:C0006142,OMIM:114480,Orphanet:ORPHA227535"
    Multiple phenotypes are separated by "|".

    Args:
        phenotype_ids_str: Raw PhenotypeIDS column value.

    Returns:
        List of MedGen CUI strings (e.g. "C0006142"). Empty list if none found.
    """
    if _is_missing(phenotype_ids_str):
        return []
    return _MEDGEN_PATTERN.findall(phenotype_ids_str)


def parse_variant_summary(
    path: Path,
    assembly: str = "GRCh38",
    chunk_size: int = 100_000,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Parse variant_summary.txt.gz and return three lists of BioLink records.

    Streams the file line by line using gzip.open to avoid loading ~500 MB into
    memory at once. Only rows where the Assembly column matches the assembly
    parameter are processed.

    Args:
        path:       Path to variant_summary.txt.gz (gzipped, tab-separated).
        assembly:   Genome assembly to filter on. Rows with a different Assembly
                    value are skipped. Defaults to "GRCh38".
        chunk_size: Log a progress message every N records processed.
                    Defaults to 100_000.

    Returns:
        Tuple of three lists:
            variant_nodes:            biolink:SequenceVariant node dicts
            variant_gene_edges:       biolink:is_sequence_variant_of edge dicts
            variant_phenotype_edges:  biolink:has_phenotype edge dicts

    Raises:
        FileNotFoundError: If path does not exist.
        KeyError: If an expected column is missing from the header.
    """
    logger.info("Parsing %s (assembly=%s)", path, assembly)

    variant_nodes: list[dict] = []
    variant_gene_edges: list[dict] = []
    variant_phenotype_edges: list[dict] = []

    n_total = 0
    n_filtered = 0
    n_skipped_assembly = 0

    with gzip.open(path, "rt", encoding="utf-8") as fh:
        raw_header = fh.readline().rstrip("\n")
        # Header line starts with '#'; strip it for column lookup
        header_clean = raw_header.lstrip("#")
        columns = header_clean.split("\t")

        # Build column index for fast lookup
        col_idx: dict[str, int] = {col.strip(): idx for idx, col in enumerate(columns)}

        # Validate required columns are present
        required_cols = [
            "VariationID", "Name", "Type", "ClinicalSignificance",
            "ReviewStatus", "Assembly", "GeneID", "GeneSymbol",
            "PhenotypeList", "PhenotypeIDS", "Chromosome",
        ]
        for col in required_cols:
            if col not in col_idx:
                raise KeyError(
                    f"Expected column '{col}' not found in variant_summary header. "
                    f"Available columns: {list(col_idx.keys())}"
                )

        for line in fh:
            n_total += 1

            if n_total % chunk_size == 0:
                logger.info(
                    "Progress: %d records processed, %d kept, %d skipped (assembly mismatch)",
                    n_total,
                    n_filtered,
                    n_skipped_assembly,
                )

            fields = line.rstrip("\n").split("\t")
            if len(fields) < len(columns):
                logger.debug("Skipping short line %d", n_total)
                continue

            row_assembly = fields[col_idx["Assembly"]].strip()
            if row_assembly != assembly:
                n_skipped_assembly += 1
                continue

            n_filtered += 1

            variation_id = fields[col_idx["VariationID"]].strip()
            name = fields[col_idx["Name"]].strip()
            variant_type = fields[col_idx["Type"]].strip()
            clinical_sig = fields[col_idx["ClinicalSignificance"]].strip()
            review_status = fields[col_idx["ReviewStatus"]].strip()
            chromosome = fields[col_idx["Chromosome"]].strip()
            gene_id_raw = fields[col_idx["GeneID"]].strip()
            phenotype_ids_raw = fields[col_idx["PhenotypeIDS"]].strip()

            if _is_missing(variation_id):
                logger.debug("Skipping row with missing VariationID at line %d", n_total)
                continue

            node_id = f"ClinVar:{variation_id}"
            source_url = f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{variation_id}"

            # Use a fallback name if the Name column is empty
            node_name = name if not _is_missing(name) else f"ClinVar variant {variation_id}"

            node = map_node(
                id=node_id,
                category="biolink:SequenceVariant",
                name=node_name,
                source="ClinVar",
                source_url=source_url,
                variant_type=variant_type if not _is_missing(variant_type) else "",
                clinical_significance=clinical_sig if not _is_missing(clinical_sig) else "",
                review_status=review_status if not _is_missing(review_status) else "",
                chromosome=chromosome if not _is_missing(chromosome) else "",
            )
            variant_nodes.append(node)

            # Gene edge: skip when GeneID is -1, empty, or missing
            try:
                gene_id_int = int(gene_id_raw)
            except ValueError:
                gene_id_int = -1

            if gene_id_int != -1 and not _is_missing(gene_id_raw):
                gene_edge = map_edge(
                    subject=node_id,
                    predicate="biolink:is_sequence_variant_of",
                    object=f"NCBIGene:{gene_id_raw}",
                    source="ClinVar",
                    source_url=source_url,
                )
                variant_gene_edges.append(gene_edge)

            # Phenotype edges: one per MedGen CUI in PhenotypeIDS
            medgen_cuis = _parse_phenotype_ids(phenotype_ids_raw)
            for cui in medgen_cuis:
                phenotype_edge = map_edge(
                    subject=node_id,
                    predicate="biolink:has_phenotype",
                    object=f"MedGen:{cui}",
                    source="ClinVar",
                    source_url=source_url,
                )
                variant_phenotype_edges.append(phenotype_edge)

    logger.info(
        "Parsed variant_summary: %d total rows, %d kept (%s), "
        "%d skipped (assembly mismatch). "
        "Produced: %d variant nodes, %d gene edges, %d phenotype edges.",
        n_total,
        n_filtered,
        assembly,
        n_skipped_assembly,
        len(variant_nodes),
        len(variant_gene_edges),
        len(variant_phenotype_edges),
    )

    return variant_nodes, variant_gene_edges, variant_phenotype_edges
