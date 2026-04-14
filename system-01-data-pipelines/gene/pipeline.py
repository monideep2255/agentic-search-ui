"""pipeline.py - Orchestrate the full Gene ETL pipeline.

Coordinates download, parsing, node enrichment, KGX export, and validation
for the NCBI Gene database. Produces nodes.tsv and edges.tsv under
config.kgx_output_dir/gene/.

Steps:
    1. Download 6 Gene FTP files (idempotent)
    2. Parse gene_info -> Gene nodes + in_taxon edges
    3. Parse gene2go -> GO nodes + GO annotation edges
    4. Parse gene2pubmed -> mentioned_in edges
    5. Parse mim2gene_medgen -> gene_associated_with_condition edges
    6. Parse gene_refseq_uniprotkb_collab -> UniProt xrefs for node enrichment
    7. Parse gene_orthologs -> orthologous_to edges
    8. Enrich Gene nodes with UniProt xrefs
    9. Export via shared KGX exporter
    10. Validate via shared validator
    11. Log summary stats

Depends on:
    - system-01-data-pipelines/gene/download.py
    - system-01-data-pipelines/gene/parse_gene_info.py
    - system-01-data-pipelines/gene/parse_gene2go.py
    - system-01-data-pipelines/gene/parse_gene2pubmed.py
    - system-01-data-pipelines/gene/parse_mim2gene.py
    - system-01-data-pipelines/gene/parse_refseq_uniprot.py
    - system-01-data-pipelines/gene/parse_orthologs.py
    - system-01-data-pipelines/shared/kgx_exporter.export_kgx
    - system-01-data-pipelines/shared/validator.validate_all
    - system-01-data-pipelines/shared/config.PipelineConfig

Writes:
    - config.kgx_output_dir/gene/nodes.tsv
    - config.kgx_output_dir/gene/edges.tsv
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import PipelineConfig
from shared.kgx_exporter import export_kgx
from shared.validator import validate_all

from gene.download import download_gene_files
from gene.parse_gene_info import parse_gene_info
from gene.parse_gene2go import parse_gene2go
from gene.parse_gene2pubmed import parse_gene2pubmed
from gene.parse_mim2gene import parse_mim2gene
from gene.parse_orthologs import parse_orthologs
from gene.parse_refseq_uniprot import parse_refseq_uniprot

logger = logging.getLogger(__name__)


def _enrich_gene_nodes_with_uniprot(
    gene_nodes: list[dict],
    gene_to_uniprot: dict[str, list[str]],
) -> list[dict]:
    """Add UniProt xrefs to Gene nodes in-place.

    For each Gene node whose id is NCBIGene:{GeneID}, looks up
    gene_to_uniprot[GeneID] and appends the UniProt accessions to the
    node's xrefs list and sets a uniprot_xrefs field.

    Args:
        gene_nodes: List of Gene node dicts (mutated in-place).
        gene_to_uniprot: Dict from parse_refseq_uniprot mapping
                         GeneID str -> list of UniProt accession strings.

    Returns:
        The same list with enriched nodes.
    """
    enriched = 0
    for node in gene_nodes:
        node_id = node.get("id", "")
        if not node_id.startswith("NCBIGene:"):
            continue
        gene_id = node_id[len("NCBIGene:"):]
        uniprot_accs = gene_to_uniprot.get(gene_id, [])
        if uniprot_accs:
            node["uniprot_xrefs"] = uniprot_accs
            existing_xrefs = node.get("xrefs", [])
            if isinstance(existing_xrefs, list):
                for acc in uniprot_accs:
                    curie = f"UniProtKB:{acc}"
                    if curie not in existing_xrefs:
                        existing_xrefs.append(curie)
                node["xrefs"] = existing_xrefs
            enriched += 1
    logger.info("Enriched %d Gene nodes with UniProt xrefs", enriched)
    return gene_nodes


def run_gene_pipeline(
    config: PipelineConfig,
    tax_id: int | None = None,
    skip_download: bool = False,
    force_download: bool = False,
) -> tuple[Path, Path]:
    """Run the complete Gene ETL pipeline and return KGX output paths.

    Downloads all required FTP files (unless skip_download=True), runs all
    parsers, merges results, exports KGX TSV files, and runs the validation
    suite. Validation failures are logged as warnings but do not abort the
    pipeline.

    Args:
        config: Pipeline configuration with ftp_cache_dir and kgx_output_dir set.
        tax_id: NCBI Taxonomy ID to filter all parsers on (e.g. 9606 for human).
                If None, all organisms are included. Recommended to set for
                development/testing to avoid multi-GB memory usage.
        skip_download: If True, skip the FTP download step and assume all files
                       are already in config.ftp_cache_dir.
        force_download: If True, re-download all files even when cached.
                        Ignored when skip_download=True.

    Returns:
        Tuple of (nodes_path, edges_path) pointing to the written KGX TSV files.

    Raises:
        FileNotFoundError: If skip_download=True and a required file is missing.
        urllib.error.URLError: If a download fails (when skip_download=False).
    """
    logger.info(
        "Starting Gene ETL pipeline (tax_id=%s, skip_download=%s)",
        tax_id,
        skip_download,
    )

    # Step 1: Download
    if skip_download:
        logger.info("Skipping download step")
        file_paths = {
            "gene_info": config.ftp_cache_dir / "gene_info.gz",
            "gene2go": config.ftp_cache_dir / "gene2go.gz",
            "gene2pubmed": config.ftp_cache_dir / "gene2pubmed.gz",
            "gene_refseq_uniprotkb_collab": config.ftp_cache_dir / "gene_refseq_uniprotkb_collab.gz",
            "mim2gene_medgen": config.ftp_cache_dir / "mim2gene_medgen",
            "gene_orthologs": config.ftp_cache_dir / "gene_orthologs.gz",
        }
    else:
        file_paths = download_gene_files(config, force=force_download)

    # Step 2: Parse gene_info -> Gene nodes + in_taxon edges
    logger.info("Parsing gene_info...")
    gene_nodes, taxon_edges = parse_gene_info(file_paths["gene_info"], tax_id=tax_id)

    # Step 3: Parse gene2go -> GO nodes + GO annotation edges
    logger.info("Parsing gene2go...")
    go_nodes, go_edges = parse_gene2go(file_paths["gene2go"], tax_id=tax_id)

    # Step 4: Parse gene2pubmed -> mentioned_in edges
    logger.info("Parsing gene2pubmed...")
    pubmed_edges = parse_gene2pubmed(file_paths["gene2pubmed"], tax_id=tax_id)

    # Step 5: Parse mim2gene_medgen -> gene_associated_with_condition edges
    logger.info("Parsing mim2gene_medgen...")
    mim_edges = parse_mim2gene(file_paths["mim2gene_medgen"])

    # Step 6: Parse gene_refseq_uniprotkb_collab -> UniProt xrefs
    logger.info("Parsing gene_refseq_uniprotkb_collab...")
    gene_to_uniprot = parse_refseq_uniprot(file_paths["gene_refseq_uniprotkb_collab"])

    # Step 7: Parse gene_orthologs -> orthologous_to edges
    logger.info("Parsing gene_orthologs...")
    ortholog_edges = parse_orthologs(file_paths["gene_orthologs"], tax_id=tax_id)

    # Step 8: Enrich Gene nodes with UniProt xrefs
    logger.info("Enriching Gene nodes with UniProt xrefs...")
    gene_nodes = _enrich_gene_nodes_with_uniprot(gene_nodes, gene_to_uniprot)

    # Merge all nodes and edges
    all_nodes: list[dict] = gene_nodes + go_nodes
    all_edges: list[dict] = (
        taxon_edges + go_edges + pubmed_edges + mim_edges + ortholog_edges
    )

    logger.info(
        "Merge complete: %d total nodes (%d gene, %d GO), %d total edges",
        len(all_nodes),
        len(gene_nodes),
        len(go_nodes),
        len(all_edges),
    )

    # Step 9: Export KGX
    logger.info("Exporting KGX files...")
    nodes_path, edges_path = export_kgx(all_nodes, all_edges, config.kgx_output_dir, "gene")

    # Step 10: Validate
    logger.info("Running validation...")
    validation_result = validate_all(all_nodes, all_edges, label="gene_pipeline")

    if validation_result["passed"]:
        logger.info("Gene pipeline validation passed")
    else:
        logger.warning(
            "Gene pipeline validation warnings: dangling_edges=%d, "
            "duplicate_nodes=%d, missing_provenance_nodes=%d, "
            "missing_provenance_edges=%d",
            len(validation_result["dangling_edges"]),
            len(validation_result["duplicate_nodes"]),
            len(validation_result["missing_provenance_nodes"]),
            len(validation_result["missing_provenance_edges"]),
        )

    # Step 11: Summary stats
    logger.info(
        "Gene ETL pipeline complete: "
        "nodes=%d (gene=%d, go=%d), "
        "edges=%d (taxon=%d, go=%d, pubmed=%d, mim=%d, orthologs=%d) "
        "nodes_file=%s edges_file=%s",
        len(all_nodes),
        len(gene_nodes),
        len(go_nodes),
        len(all_edges),
        len(taxon_edges),
        len(go_edges),
        len(pubmed_edges),
        len(mim_edges),
        len(ortholog_edges),
        nodes_path,
        edges_path,
    )

    return nodes_path, edges_path
