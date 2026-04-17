"""pipeline.py - Orchestrate the full Gene ETL pipeline (streaming).

Coordinates download, parsing, KGX export, and validation for the NCBI Gene
database. Produces nodes.tsv and edges.tsv under config.kgx_output_dir/gene/.

Memory profile: streams every large parser (gene_info, gene2go, gene2pubmed,
gene_orthologs) through the shared append_nodes / append_edges helpers in
10 000-row batches. Peak memory stays at a few hundred MB even on the full
67 M gene / 278 M edge dataset, making the pipeline run on laptop-scale
hardware. See DECISIONS.md (2026-04-17) and docs/learnings.md for the
history of the streaming refactor.

Steps:
    1. Download 6 Gene FTP files (idempotent)
    2. Parse small inputs into memory (UniProt xref dict, mim2gene edges)
    3. Peek at first gene_info and first gene2go rows to compute fieldnames
    4. Init nodes.tsv and edges.tsv with union fieldnames
    5. Stream gene_info -> enrich nodes with UniProt -> append to disk
    6. Stream gene2go -> append unique GO nodes and edges
    7. Stream gene2pubmed -> append edges
    8. Stream gene_orthologs -> append edges
    9. Flush mim2gene_medgen edges
    10. Log summary stats

Depends on:
    - system-01-data-pipelines/gene/download.py
    - system-01-data-pipelines/gene/parse_gene_info.py (iter_gene_info)
    - system-01-data-pipelines/gene/parse_gene2go.py (iter_gene2go)
    - system-01-data-pipelines/gene/parse_gene2pubmed.py (iter_gene2pubmed)
    - system-01-data-pipelines/gene/parse_mim2gene.py
    - system-01-data-pipelines/gene/parse_refseq_uniprot.py
    - system-01-data-pipelines/gene/parse_orthologs.py (iter_orthologs)
    - system-01-data-pipelines/shared/kgx_exporter (init/append helpers)
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
from shared.kgx_exporter import (
    EDGE_REQUIRED_COLUMNS,
    NODE_REQUIRED_COLUMNS,
    append_edges,
    append_nodes,
    init_edges_file,
    init_nodes_file,
)

from gene.download import download_gene_files
from gene.parse_gene_info import iter_gene_info
from gene.parse_gene2go import iter_gene2go
from gene.parse_gene2pubmed import iter_gene2pubmed
from gene.parse_mim2gene import parse_mim2gene
from gene.parse_orthologs import iter_orthologs
from gene.parse_refseq_uniprot import parse_refseq_uniprot

logger = logging.getLogger(__name__)

BATCH_SIZE = 10_000
LOG_EVERY = 1_000_000


def _enrich_node_with_uniprot(
    node: dict,
    gene_to_uniprot: dict[str, list[str]],
) -> None:
    """Append UniProt xrefs to a Gene node dict in place.

    Args:
        node: Gene node dict. Must have id like "NCBIGene:{GeneID}".
        gene_to_uniprot: Map of GeneID str -> list of UniProt accession strings.
    """
    node_id = node.get("id", "")
    if not node_id.startswith("NCBIGene:"):
        return
    gene_id = node_id[len("NCBIGene:"):]
    uniprot_accs = gene_to_uniprot.get(gene_id, [])
    if not uniprot_accs:
        return

    node["uniprot_xrefs"] = uniprot_accs
    xrefs = node.get("xrefs", [])
    if isinstance(xrefs, list):
        for acc in uniprot_accs:
            curie = f"UniProtKB:{acc}"
            if curie not in xrefs:
                xrefs.append(curie)
        node["xrefs"] = xrefs


def _flush(
    batch: list[dict],
    writer,
    path: Path,
    fieldnames: list[str],
) -> int:
    """Call writer(batch, path, fieldnames=...) and clear the batch.

    Returns number of records written.
    """
    if not batch:
        return 0
    n = len(batch)
    writer(batch, path, fieldnames=fieldnames)
    batch.clear()
    return n


def run_gene_pipeline(
    config: PipelineConfig,
    tax_id: int | None = None,
    skip_download: bool = False,
    force_download: bool = False,
) -> tuple[Path, Path]:
    """Run the complete Gene ETL pipeline with streaming and return KGX paths.

    Args:
        config: Pipeline configuration with ftp_cache_dir and kgx_output_dir set.
        tax_id: NCBI Taxonomy ID filter. None = all organisms.
        skip_download: If True, skip FTP download and use cached files.
        force_download: If True, re-download even when cached. Ignored when
                        skip_download=True.

    Returns:
        (nodes_path, edges_path).

    Raises:
        FileNotFoundError: If skip_download=True and a required file is missing.
        urllib.error.URLError: If a download fails.
        RuntimeError: If gene_info.gz yields zero rows (empty file or filter too strict).
    """
    logger.info(
        "Starting Gene ETL pipeline (tax_id=%s, skip_download=%s) [streaming]",
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

    # Step 2: Parse small inputs in memory
    logger.info("Parsing small inputs (UniProt xrefs, mim2gene_medgen)...")
    gene_to_uniprot = parse_refseq_uniprot(file_paths["gene_refseq_uniprotkb_collab"])
    mim_edges = parse_mim2gene(file_paths["mim2gene_medgen"])
    logger.info(
        "Small-input parse complete: UniProt dict=%d entries, mim_edges=%d",
        len(gene_to_uniprot),
        len(mim_edges),
    )

    # Step 3: Peek at first rows of the two node-producing generators so we
    # can compute the union fieldname sets before opening the output files.
    gen_gene = iter_gene_info(file_paths["gene_info"], tax_id=tax_id)
    try:
        first_gene_node, first_taxon_edge = next(gen_gene)
    except StopIteration as exc:
        raise RuntimeError(
            f"gene_info.gz produced zero rows (tax_id={tax_id}). "
            "Filter too strict or empty source file."
        ) from exc
    _enrich_node_with_uniprot(first_gene_node, gene_to_uniprot)

    gen_gene2go = iter_gene2go(file_paths["gene2go"], tax_id=tax_id)
    first_go_node: dict | None = None
    first_go_edge: dict | None = None
    for go_node_or_none, go_edge in gen_gene2go:
        if first_go_edge is None:
            first_go_edge = go_edge
        if go_node_or_none is not None:
            first_go_node = go_node_or_none
            break
    # If gene2go is empty or only yields None-nodes, GO nodes stay empty;
    # we still need a valid edge sample for edge fieldnames.

    # Union fieldnames
    node_field_set: set[str] = set(first_gene_node.keys())
    if first_go_node is not None:
        node_field_set.update(first_go_node.keys())
    node_cols = NODE_REQUIRED_COLUMNS + sorted(node_field_set - set(NODE_REQUIRED_COLUMNS))

    edge_field_set: set[str] = set(first_taxon_edge.keys())
    if first_go_edge is not None:
        edge_field_set.update(first_go_edge.keys())
    if mim_edges:
        edge_field_set.update(mim_edges[0].keys())
    edge_cols = EDGE_REQUIRED_COLUMNS + sorted(edge_field_set - set(EDGE_REQUIRED_COLUMNS))

    # Step 4: Init output files
    nodes_path = init_nodes_file(config.kgx_output_dir, "gene", fieldnames=node_cols)
    edges_path = init_edges_file(config.kgx_output_dir, "gene", fieldnames=edge_cols)
    logger.info(
        "Initialised KGX outputs: nodes_cols=%d, edges_cols=%d", len(node_cols), len(edge_cols)
    )

    node_batch: list[dict] = []
    edge_batch: list[dict] = []
    counts = {
        "gene_nodes": 0,
        "go_nodes": 0,
        "taxon_edges": 0,
        "go_edges": 0,
        "pubmed_edges": 0,
        "ortholog_edges": 0,
        "mim_edges": 0,
    }

    # Step 5: Stream gene_info (re-inject the peeked first pair)
    logger.info("Streaming gene_info...")
    node_batch.append(first_gene_node)
    edge_batch.append(first_taxon_edge)
    for gene_node, taxon_edge in gen_gene:
        _enrich_node_with_uniprot(gene_node, gene_to_uniprot)
        node_batch.append(gene_node)
        edge_batch.append(taxon_edge)
        if len(node_batch) >= BATCH_SIZE:
            counts["gene_nodes"] += _flush(node_batch, append_nodes, nodes_path, node_cols)
            counts["taxon_edges"] += _flush(edge_batch, append_edges, edges_path, edge_cols)
            if counts["gene_nodes"] and counts["gene_nodes"] % LOG_EVERY == 0:
                logger.info(
                    "  gene_info: %d gene nodes, %d taxon edges so far",
                    counts["gene_nodes"],
                    counts["taxon_edges"],
                )
    counts["gene_nodes"] += _flush(node_batch, append_nodes, nodes_path, node_cols)
    counts["taxon_edges"] += _flush(edge_batch, append_edges, edges_path, edge_cols)
    logger.info(
        "gene_info complete: %d gene nodes, %d taxon edges",
        counts["gene_nodes"],
        counts["taxon_edges"],
    )

    # Step 6: Stream gene2go (re-inject peeked first)
    logger.info("Streaming gene2go...")
    if first_go_node is not None:
        node_batch.append(first_go_node)
    if first_go_edge is not None:
        edge_batch.append(first_go_edge)
    for go_node_or_none, go_edge in gen_gene2go:
        if go_node_or_none is not None:
            node_batch.append(go_node_or_none)
        edge_batch.append(go_edge)
        if len(edge_batch) >= BATCH_SIZE:
            counts["go_nodes"] += _flush(node_batch, append_nodes, nodes_path, node_cols)
            counts["go_edges"] += _flush(edge_batch, append_edges, edges_path, edge_cols)
            if counts["go_edges"] and counts["go_edges"] % LOG_EVERY == 0:
                logger.info(
                    "  gene2go: %d GO nodes, %d GO edges so far",
                    counts["go_nodes"],
                    counts["go_edges"],
                )
    counts["go_nodes"] += _flush(node_batch, append_nodes, nodes_path, node_cols)
    counts["go_edges"] += _flush(edge_batch, append_edges, edges_path, edge_cols)
    logger.info(
        "gene2go complete: %d GO nodes, %d GO edges",
        counts["go_nodes"],
        counts["go_edges"],
    )

    # Step 7: Stream gene2pubmed
    logger.info("Streaming gene2pubmed...")
    for edge in iter_gene2pubmed(file_paths["gene2pubmed"], tax_id=tax_id):
        edge_batch.append(edge)
        if len(edge_batch) >= BATCH_SIZE:
            counts["pubmed_edges"] += _flush(edge_batch, append_edges, edges_path, edge_cols)
            if counts["pubmed_edges"] and counts["pubmed_edges"] % LOG_EVERY == 0:
                logger.info("  gene2pubmed: %d edges so far", counts["pubmed_edges"])
    counts["pubmed_edges"] += _flush(edge_batch, append_edges, edges_path, edge_cols)
    logger.info("gene2pubmed complete: %d edges", counts["pubmed_edges"])

    # Step 8: Stream gene_orthologs
    logger.info("Streaming gene_orthologs...")
    for edge in iter_orthologs(file_paths["gene_orthologs"], tax_id=tax_id):
        edge_batch.append(edge)
        if len(edge_batch) >= BATCH_SIZE:
            counts["ortholog_edges"] += _flush(edge_batch, append_edges, edges_path, edge_cols)
    counts["ortholog_edges"] += _flush(edge_batch, append_edges, edges_path, edge_cols)
    logger.info("gene_orthologs complete: %d edges", counts["ortholog_edges"])

    # Step 9: Flush mim_edges (small)
    if mim_edges:
        counts["mim_edges"] = _flush(mim_edges, append_edges, edges_path, edge_cols)
    logger.info("mim2gene_medgen complete: %d edges", counts["mim_edges"])

    # Step 10: Summary (note: node/edge validation moved to merge phase because
    # holding all 67M nodes in memory would defeat the streaming refactor)
    total_nodes = counts["gene_nodes"] + counts["go_nodes"]
    total_edges = (
        counts["taxon_edges"]
        + counts["go_edges"]
        + counts["pubmed_edges"]
        + counts["ortholog_edges"]
        + counts["mim_edges"]
    )
    logger.info(
        "Gene ETL pipeline complete: "
        "nodes=%d (gene=%d, go=%d), "
        "edges=%d (taxon=%d, go=%d, pubmed=%d, orthologs=%d, mim=%d) "
        "nodes_file=%s edges_file=%s",
        total_nodes,
        counts["gene_nodes"],
        counts["go_nodes"],
        total_edges,
        counts["taxon_edges"],
        counts["go_edges"],
        counts["pubmed_edges"],
        counts["ortholog_edges"],
        counts["mim_edges"],
        nodes_path,
        edges_path,
    )

    return nodes_path, edges_path
