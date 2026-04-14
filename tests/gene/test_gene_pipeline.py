"""Tests for the Gene ETL pipeline modules.

All tests use tmp_path for file I/O. Downloads are mocked. Inline fixture
data is used throughout - no separate fixture files.

Tests:
    test_parse_gene_info_basic          - node structure from 5-line fixture
    test_parse_gene_info_tax_filter     - tax_id filter correctness
    test_parse_gene2go_predicates       - correct predicate for P/F/C categories
    test_parse_gene2pubmed              - mentioned_in edges
    test_parse_mim2gene                 - gene_associated_with_condition, skip "-" rows
    test_parse_orthologs                - orthologous_to edges
    test_gene_pipeline_end_to_end       - full pipeline with mocked downloads
"""

import gzip
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make the shared and gene packages importable from test context
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "system-01-data-pipelines"))

from gene.parse_gene2go import parse_gene2go
from gene.parse_gene2pubmed import parse_gene2pubmed
from gene.parse_gene_info import parse_gene_info
from gene.parse_mim2gene import parse_mim2gene
from gene.parse_orthologs import parse_orthologs
from gene.parse_refseq_uniprot import parse_refseq_uniprot
from gene.pipeline import run_gene_pipeline
from shared.config import PipelineConfig


# ── Fixtures ──────────────────────────────────────────────────────────────────

GENE_INFO_HEADER = (
    "#tax_id\tGeneID\tSymbol\tLocusTag\tSynonyms\tdbXrefs\t"
    "chromosome\tmap_location\tdescription\ttype_of_gene\t"
    "Symbol_from_nomenclature_authority\tFull_name_from_nomenclature_authority\t"
    "Nomenclature_status\tOther_designations\tModification_date\tFeature_type\n"
)

GENE_INFO_ROWS = [
    # human BRCA1
    "9606\t672\tBRCA1\t-\tRNF53|BRCA1\tHGNC:HGNC:1100|MIM:113705|Ensembl:ENSG00000012048\t17\t17q21.31\tBRCA1 DNA repair associated\tprotein-coding\tBRCA1\tBRCA1 DNA repair associated\tO\t-\t20230101\tmain\n",
    # human TP53
    "9606\t7157\tTP53\t-\tLFS1|TRP53\tHGNC:HGNC:11998|MIM:191170|Ensembl:ENSG00000141510\t17\t17p13.1\ttumor protein p53\tprotein-coding\tTP53\ttumor protein p53\tO\t-\t20230101\tmain\n",
    # human EGFR
    "9606\t1956\tEGFR\t-\tERBB|ERBB1\tHGNC:HGNC:3236|MIM:131550|Ensembl:ENSG00000146648\t7\t7p11.2\tepidermal growth factor receptor\tprotein-coding\tEGFR\tepidermal growth factor receptor\tO\t-\t20230101\tmain\n",
    # mouse Brca1 (tax_id 10090)
    "10090\t12189\tBrca1\t-\t-\t-\t11\t11 B1.1\tbreast cancer 1, early onset\tprotein-coding\tBrca1\tbreast cancer 1, early onset\tO\t-\t20230101\tmain\n",
    # human gene with no description
    "9606\t100\t-\t-\t-\t-\t-\t-\t-\tpseudo\t-\t-\t-\t-\t20230101\tmain\n",
]

GENE2GO_HEADER = "#tax_id\tGeneID\tGO_ID\tEvidence\tQualifier\tGO_term\tPubMed\tCategory\n"
GENE2GO_ROWS = [
    "9606\t672\tGO:0006281\tTAS\t-\tDNA repair\t-\tProcess\n",
    "9606\t672\tGO:0003677\tIDA\t-\tDNA binding\t1234567\tFunction\n",
    "9606\t672\tGO:0005634\tIDA\t-\tnucleus\t-\tComponent\n",
    "9606\t7157\tGO:0006281\tIC\t-\tDNA repair\t-\tProcess\n",
]

GENE2PUBMED_HEADER = "#tax_id\tGeneID\tPubMed_ID\n"
GENE2PUBMED_ROWS = [
    "9606\t672\t11780052\n",
    "9606\t672\t12477932\n",
    "9606\t7157\t9811853\n",
    "10090\t12189\t9500320\n",
]

MIM2GENE_HEADER = "#MIM number\tGeneID\ttype\tSource\tMedGenCUI\tComment\n"
MIM2GENE_ROWS = [
    # valid row
    "113705\t672\tgene\tOMIM\tC0006142\t-\n",
    # GeneID is "-" - should be skipped
    "114480\t-\tphenotype\tOMIM\tC3553468\t-\n",
    # MedGenCUI is "-" - should be skipped
    "191170\t7157\tgene\tOMIM\t-\t-\n",
    # valid row
    "131550\t1956\tgene\tOMIM\tC0007134\t-\n",
]

ORTHOLOGS_HEADER = "#tax_id\tGeneID\trelationship\tOther_tax_id\tOther_GeneID\n"
ORTHOLOGS_ROWS = [
    # human BRCA1 <-> mouse Brca1
    "9606\t672\tOrtholog\t10090\t12189\n",
    # human TP53 <-> mouse Trp53
    "9606\t7157\tOrtholog\t10090\t22059\n",
    # two non-human genes (should be excluded when filtering by 9606)
    "10090\t12189\tOrtholog\t10116\t307560\n",
]

REFSEQ_UNIPROT_HEADER = "#NCBI_protein_accession\tUniProtKB_protein_accession\tGeneID\n"
REFSEQ_UNIPROT_ROWS = [
    "NP_009225.1\tP38398\t672\n",
    "NP_009226.2\tQ6IS14\t672\n",
    "NP_000537.3\tP04637\t7157\n",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_gzip(path: Path, header: str, rows: list[str]) -> None:
    """Write a gzip-compressed fixture file."""
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(header)
        fh.writelines(rows)


def _write_plain(path: Path, header: str, rows: list[str]) -> None:
    """Write a plain-text fixture file."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(header)
        fh.writelines(rows)


def make_config(tmp_path: Path) -> PipelineConfig:
    """Return a PipelineConfig pointing to tmp_path subdirectories."""
    return PipelineConfig(
        ncbi_email="test@example.com",
        ftp_cache_dir=tmp_path / "ftp_cache",
        kgx_output_dir=tmp_path / "kgx",
        data_dir=tmp_path / "data",
        raw_data_dir=tmp_path / "raw",
    )


# ── Tests: parse_gene_info ────────────────────────────────────────────────────

def test_parse_gene_info_basic(tmp_path: Path) -> None:
    """Parse a 5-line gene_info fixture and verify node structure."""
    fixture = tmp_path / "gene_info.gz"
    _write_gzip(fixture, GENE_INFO_HEADER, GENE_INFO_ROWS)

    nodes, edges = parse_gene_info(fixture)

    # We have 5 rows; the last row has symbol "-" so name becomes "Gene 100"
    # and all other rows are valid
    assert len(nodes) >= 4  # at least 4 valid gene nodes

    # Find BRCA1 node
    brca1 = next((n for n in nodes if n["id"] == "NCBIGene:672"), None)
    assert brca1 is not None
    assert brca1["category"] == "biolink:Gene"
    assert brca1["name"] == "BRCA1 DNA repair associated"
    assert brca1["symbol"] == "BRCA1"
    assert brca1["source"] == "NCBI Gene"
    assert brca1["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/672"
    assert brca1["in_taxon"] == "NCBITaxon:9606"
    assert brca1["chromosome"] == "17"
    assert brca1["gene_type"] == "protein-coding"
    assert "HGNC:1100" in brca1["hgnc_id"]
    assert "OMIM:113705" in brca1["omim_ids"]
    assert "ENSG00000012048" in brca1["ensembl_ids"]

    # Each node should have a corresponding taxon edge
    assert len(edges) == len(nodes)
    brca1_edge = next((e for e in edges if e["subject"] == "NCBIGene:672"), None)
    assert brca1_edge is not None
    assert brca1_edge["predicate"] == "biolink:in_taxon"
    assert brca1_edge["object"] == "NCBITaxon:9606"
    assert brca1_edge["source"] == "NCBI Gene"
    assert brca1_edge["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/672"


def test_parse_gene_info_tax_filter(tmp_path: Path) -> None:
    """Verify tax_id filter excludes non-matching organisms."""
    fixture = tmp_path / "gene_info.gz"
    _write_gzip(fixture, GENE_INFO_HEADER, GENE_INFO_ROWS)

    # Filter to human only (9606)
    nodes, edges = parse_gene_info(fixture, tax_id=9606)

    node_ids = {n["id"] for n in nodes}

    # Human genes should be present
    assert "NCBIGene:672" in node_ids
    assert "NCBIGene:7157" in node_ids
    assert "NCBIGene:1956" in node_ids

    # Mouse gene should be excluded
    assert "NCBIGene:12189" not in node_ids

    # Filter to mouse only
    mouse_nodes, _ = parse_gene_info(fixture, tax_id=10090)
    mouse_ids = {n["id"] for n in mouse_nodes}
    assert "NCBIGene:12189" in mouse_ids
    assert "NCBIGene:672" not in mouse_ids


# ── Tests: parse_gene2go ──────────────────────────────────────────────────────

def test_parse_gene2go_predicates(tmp_path: Path) -> None:
    """Verify correct BioLink predicate for each GO category (P/F/C)."""
    fixture = tmp_path / "gene2go.gz"
    _write_gzip(fixture, GENE2GO_HEADER, GENE2GO_ROWS)

    go_nodes, go_edges = parse_gene2go(fixture, tax_id=9606)

    # 3 unique GO terms: GO:0006281, GO:0003677, GO:0005634
    go_node_ids = {n["id"] for n in go_nodes}
    assert "GO:0006281" in go_node_ids
    assert "GO:0003677" in go_node_ids
    assert "GO:0005634" in go_node_ids

    # Check categories on GO nodes
    go_node_map = {n["id"]: n for n in go_nodes}
    assert go_node_map["GO:0006281"]["category"] == "biolink:BiologicalProcess"
    assert go_node_map["GO:0003677"]["category"] == "biolink:MolecularActivity"
    assert go_node_map["GO:0005634"]["category"] == "biolink:CellularComponent"

    # Check predicates on edges
    edge_map: dict[str, str] = {}
    for e in go_edges:
        key = (e["subject"], e["object"])
        edge_map[key] = e["predicate"]

    assert edge_map[("NCBIGene:672", "GO:0006281")] == "biolink:participates_in"
    assert edge_map[("NCBIGene:672", "GO:0003677")] == "biolink:actively_involved_in"
    assert edge_map[("NCBIGene:672", "GO:0005634")] == "biolink:located_in"

    # Provenance on all edges
    for edge in go_edges:
        assert edge["source"] == "NCBI Gene"
        assert edge["source_url"].startswith("https://www.ncbi.nlm.nih.gov/gene/")

    # Evidence code carried through
    repair_edges = [e for e in go_edges if e["object"] == "GO:0006281" and e["subject"] == "NCBIGene:672"]
    assert len(repair_edges) == 1
    assert repair_edges[0]["evidence_code"] == "TAS"


def test_parse_gene2go_no_tax_filter(tmp_path: Path) -> None:
    """When no tax_id is set, all rows are parsed."""
    fixture = tmp_path / "gene2go.gz"
    _write_gzip(fixture, GENE2GO_HEADER, GENE2GO_ROWS)

    _, go_edges = parse_gene2go(fixture)

    # All 4 rows should produce edges (3 for gene 672, 1 for gene 7157)
    assert len(go_edges) == 4


# ── Tests: parse_gene2pubmed ──────────────────────────────────────────────────

def test_parse_gene2pubmed(tmp_path: Path) -> None:
    """Verify mentioned_in edges and tax_id filtering."""
    fixture = tmp_path / "gene2pubmed.gz"
    _write_gzip(fixture, GENE2PUBMED_HEADER, GENE2PUBMED_ROWS)

    # Human-only filter: rows 0, 1, 2 (3 edges)
    edges = parse_gene2pubmed(fixture, tax_id=9606)
    assert len(edges) == 3

    subjects = {e["subject"] for e in edges}
    objects = {e["object"] for e in edges}
    assert "NCBIGene:672" in subjects
    assert "NCBIGene:7157" in subjects
    assert "PMID:11780052" in objects
    assert "PMID:12477932" in objects
    assert "PMID:9811853" in objects

    for edge in edges:
        assert edge["predicate"] == "biolink:mentioned_in"
        assert edge["source"] == "NCBI Gene"
        assert edge["source_url"].startswith("https://www.ncbi.nlm.nih.gov/gene/")

    # Mouse edge should be excluded
    gene_ids = {e["subject"] for e in edges}
    assert "NCBIGene:12189" not in gene_ids

    # No filter: all 4 rows
    all_edges = parse_gene2pubmed(fixture)
    assert len(all_edges) == 4


# ── Tests: parse_mim2gene ─────────────────────────────────────────────────────

def test_parse_mim2gene(tmp_path: Path) -> None:
    """Verify gene_associated_with_condition edges and skipping of '-' rows."""
    fixture = tmp_path / "mim2gene_medgen"
    _write_plain(fixture, MIM2GENE_HEADER, MIM2GENE_ROWS)

    edges = parse_mim2gene(fixture)

    # Rows with GeneID="-" or MedGenCUI="-" must be skipped
    # Only rows 0 and 3 are valid
    assert len(edges) == 2

    subjects = {e["subject"] for e in edges}
    objects = {e["object"] for e in edges}
    assert "NCBIGene:672" in subjects
    assert "NCBIGene:1956" in subjects
    assert "MedGen:C0006142" in objects
    assert "MedGen:C0007134" in objects

    # Row with GeneID="-" excluded
    assert "NCBIGene:-" not in subjects

    # Row with MedGenCUI="-" excluded (TP53 row)
    assert "NCBIGene:7157" not in subjects

    for edge in edges:
        assert edge["predicate"] == "biolink:gene_associated_with_condition"
        assert edge["source"] == "NCBI MIM2Gene"
        assert edge["source_url"].startswith("https://www.ncbi.nlm.nih.gov/gene/")


# ── Tests: parse_orthologs ────────────────────────────────────────────────────

def test_parse_orthologs(tmp_path: Path) -> None:
    """Verify orthologous_to edges and tax_id filter logic."""
    fixture = tmp_path / "gene_orthologs.gz"
    _write_gzip(fixture, ORTHOLOGS_HEADER, ORTHOLOGS_ROWS)

    # Filter to human (9606): rows 0 and 1 have tax_id=9606, row 2 does not
    edges = parse_orthologs(fixture, tax_id=9606)
    assert len(edges) == 2

    subjects = {e["subject"] for e in edges}
    objects = {e["object"] for e in edges}
    assert "NCBIGene:672" in subjects
    assert "NCBIGene:7157" in subjects
    assert "NCBIGene:12189" in objects
    assert "NCBIGene:22059" in objects

    for edge in edges:
        assert edge["predicate"] == "biolink:orthologous_to"
        assert edge["source"] == "NCBI Gene Orthologs"
        assert edge["source_url"].startswith("https://www.ncbi.nlm.nih.gov/gene/")

    # No filter: all 3 rows
    all_edges = parse_orthologs(fixture)
    assert len(all_edges) == 3

    # Filter to mouse (10090): rows 0, 1, 2 all include a mouse gene
    # row 0: Other_tax_id=10090, row 1: Other_tax_id=10090, row 2: tax_id=10090
    mouse_edges = parse_orthologs(fixture, tax_id=10090)
    assert len(mouse_edges) == 3


# ── Tests: parse_refseq_uniprot ───────────────────────────────────────────────

def test_parse_refseq_uniprot(tmp_path: Path) -> None:
    """Verify GeneID -> UniProt accession mapping."""
    fixture = tmp_path / "gene_refseq_uniprotkb_collab.gz"
    _write_gzip(fixture, REFSEQ_UNIPROT_HEADER, REFSEQ_UNIPROT_ROWS)

    result = parse_refseq_uniprot(fixture)

    assert "672" in result
    assert set(result["672"]) == {"P38398", "Q6IS14"}

    assert "7157" in result
    assert result["7157"] == ["P04637"]


# ── Tests: end-to-end pipeline ────────────────────────────────────────────────

def test_gene_pipeline_end_to_end(tmp_path: Path) -> None:
    """Run the full pipeline with mocked downloads and verify KGX output."""
    config = make_config(tmp_path)
    ftp_cache = config.ftp_cache_dir

    # Write all fixture files to the fake ftp cache
    _write_gzip(ftp_cache / "gene_info.gz", GENE_INFO_HEADER, GENE_INFO_ROWS)
    _write_gzip(ftp_cache / "gene2go.gz", GENE2GO_HEADER, GENE2GO_ROWS)
    _write_gzip(ftp_cache / "gene2pubmed.gz", GENE2PUBMED_HEADER, GENE2PUBMED_ROWS)
    _write_plain(ftp_cache / "mim2gene_medgen", MIM2GENE_HEADER, MIM2GENE_ROWS)
    _write_gzip(ftp_cache / "gene_refseq_uniprotkb_collab.gz", REFSEQ_UNIPROT_HEADER, REFSEQ_UNIPROT_ROWS)
    _write_gzip(ftp_cache / "gene_orthologs.gz", ORTHOLOGS_HEADER, ORTHOLOGS_ROWS)

    # Run with skip_download=True so no network calls are made
    nodes_path, edges_path = run_gene_pipeline(
        config=config,
        tax_id=9606,
        skip_download=True,
    )

    # Output files must exist
    assert nodes_path.exists(), f"nodes.tsv not created at {nodes_path}"
    assert edges_path.exists(), f"edges.tsv not created at {edges_path}"
    assert nodes_path.name == "nodes.tsv"
    assert edges_path.name == "edges.tsv"
    assert nodes_path.parent.name == "gene"
    assert edges_path.parent.name == "gene"

    # Verify nodes.tsv content
    nodes_lines = nodes_path.read_text(encoding="utf-8").splitlines()
    assert len(nodes_lines) > 1, "nodes.tsv should have a header plus at least one data row"

    header = nodes_lines[0].split("\t")
    assert "id" in header
    assert "category" in header
    assert "name" in header
    assert "source" in header
    assert "source_url" in header

    # Verify edges.tsv content
    edges_lines = edges_path.read_text(encoding="utf-8").splitlines()
    assert len(edges_lines) > 1, "edges.tsv should have a header plus at least one data row"

    edge_header = edges_lines[0].split("\t")
    assert "subject" in edge_header
    assert "predicate" in edge_header
    assert "object" in edge_header
    assert "source" in edge_header
    assert "source_url" in edge_header

    # Verify known gene appears in nodes
    node_ids_in_file = {line.split("\t")[0] for line in nodes_lines[1:] if line.strip()}
    assert "NCBIGene:672" in node_ids_in_file, "BRCA1 node must be in nodes.tsv"

    # Verify predicates appear in edges
    predicates_in_file = {line.split("\t")[1] for line in edges_lines[1:] if line.strip()}
    assert "biolink:in_taxon" in predicates_in_file
    assert "biolink:participates_in" in predicates_in_file
    assert "biolink:mentioned_in" in predicates_in_file
    assert "biolink:gene_associated_with_condition" in predicates_in_file
    assert "biolink:orthologous_to" in predicates_in_file


def test_gene_pipeline_skip_download_missing_file(tmp_path: Path) -> None:
    """Pipeline with skip_download=True raises when a file is missing."""
    config = make_config(tmp_path)

    # Write only some files - leave gene2go.gz missing
    ftp_cache = config.ftp_cache_dir
    _write_gzip(ftp_cache / "gene_info.gz", GENE_INFO_HEADER, GENE_INFO_ROWS)
    # gene2go.gz intentionally omitted

    with pytest.raises((FileNotFoundError, OSError)):
        run_gene_pipeline(config=config, tax_id=9606, skip_download=True)
