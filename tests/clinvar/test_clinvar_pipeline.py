"""Tests for the ClinVar ETL pipeline.

Tests cover:
    - parse_variant_summary: basic parsing, assembly filtering, gene edges,
      phenotype edges, missing gene handling
    - parse_var_citations: cited_in edges, PubMed-only filtering
    - run_clinvar_pipeline: end-to-end with mocked downloads

All file I/O uses tmp_path. Downloads are mocked.
"""

import csv
import gzip
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "system-01-data-pipelines"))

from clinvar.parse_variant_summary import parse_variant_summary
from clinvar.parse_var_citations import parse_var_citations
from clinvar.pipeline import run_clinvar_pipeline
from shared.config import PipelineConfig

# ---------------------------------------------------------------------------
# Header matching the real variant_summary.txt.gz format (tab-separated)
# ---------------------------------------------------------------------------
VARIANT_SUMMARY_HEADER = (
    "#AlleleID\tType\tName\tGeneID\tGeneSymbol\tHGNC_ID\t"
    "ClinicalSignificance\tClinSigSimple\tLastEvaluated\t"
    "RS# (dbSNP)\tnsv/esv (dbVar)\tRCVaccession\t"
    "PhenotypeIDS\tPhenotypeList\tOrigin\tOriginSimple\t"
    "Assembly\tChromosomeAccession\tChromosome\tStart\tStop\t"
    "ReferenceAllele\tAlternateAllele\tCytogenetic\t"
    "ReviewStatus\tNumberSubmitters\tGuidelines\tTestedInGTR\t"
    "OtherIDs\tSubmitterCategories\tVariationID\t"
    "PositionVCF\tReferenceAlleleVCF\tAlternateAlleleVCF\t"
    "Copychange\tFixedVariationID"
)

# Indices corresponding to the header above (0-based, after stripping '#')
# We build fixture rows as dicts and then serialise to avoid index errors.
_COLS = [c.lstrip("#") for c in VARIANT_SUMMARY_HEADER.lstrip("#").split("\t")]


def _make_variant_row(**overrides) -> str:
    """Build a tab-separated variant_summary row with sensible defaults."""
    defaults = {
        "AlleleID": "100001",
        "Type": "single nucleotide variant",
        "Name": "NM_007294.4(BRCA1):c.5266dupC (p.Gln1756ProfsTer25)",
        "GeneID": "672",
        "GeneSymbol": "BRCA1",
        "HGNC_ID": "HGNC:1100",
        "ClinicalSignificance": "Pathogenic",
        "ClinSigSimple": "1",
        "LastEvaluated": "2023-01-01",
        "RS# (dbSNP)": "80357906",
        "nsv/esv (dbVar)": "-",
        "RCVaccession": "RCV000031116",
        "PhenotypeIDS": "MedGen:C0006142,OMIM:114480",
        "PhenotypeList": "Breast-ovarian cancer, familial, susceptibility to, 1",
        "Origin": "germline",
        "OriginSimple": "germline",
        "Assembly": "GRCh38",
        "ChromosomeAccession": "NC_000017.11",
        "Chromosome": "17",
        "Start": "43045629",
        "Stop": "43045629",
        "ReferenceAllele": "C",
        "AlternateAllele": "CC",
        "Cytogenetic": "17q21.31",
        "ReviewStatus": "reviewed by expert panel",
        "NumberSubmitters": "1",
        "Guidelines": "-",
        "TestedInGTR": "N",
        "OtherIDs": "-",
        "SubmitterCategories": "3",
        "VariationID": "17599",
        "PositionVCF": "43045629",
        "ReferenceAlleleVCF": "C",
        "AlternateAlleleVCF": "CC",
        "Copychange": "-",
        "FixedVariationID": "-",
    }
    defaults.update(overrides)
    return "\t".join(defaults[c] if c in defaults else "-" for c in _COLS)


def _write_variant_summary_gz(path: Path, rows: list[str]) -> None:
    """Write a gzipped variant_summary.txt with header + given data rows."""
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(VARIANT_SUMMARY_HEADER + "\n")
        for row in rows:
            fh.write(row + "\n")


def _write_var_citations(path: Path, rows: list[dict]) -> None:
    """Write var_citations.txt with header + given data rows."""
    fieldnames = ["VariationID", "AlleleID", "citation_source", "citation_id"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


# ---------------------------------------------------------------------------
# parse_variant_summary tests
# ---------------------------------------------------------------------------

class TestParseVariantSummaryBasic:
    def test_basic_parsing(self, tmp_path: Path) -> None:
        """Five valid GRCh38 rows produce five variant nodes with correct fields."""
        rows = [
            _make_variant_row(VariationID=str(i), GeneID="672")
            for i in range(10001, 10006)
        ]
        gz_path = tmp_path / "variant_summary.txt.gz"
        _write_variant_summary_gz(gz_path, rows)

        nodes, gene_edges, pheno_edges = parse_variant_summary(gz_path)

        assert len(nodes) == 5
        for node in nodes:
            assert node["id"].startswith("ClinVar:")
            assert node["category"] == "biolink:SequenceVariant"
            assert node["source"] == "ClinVar"
            assert node["source_url"].startswith("https://www.ncbi.nlm.nih.gov/clinvar/variation/")
            assert "clinical_significance" in node
            assert node["clinical_significance"] == "Pathogenic"


class TestParseVariantSummaryAssemblyFilter:
    def test_only_grch38_rows_kept(self, tmp_path: Path) -> None:
        """Rows with Assembly != GRCh38 are excluded."""
        rows = [
            _make_variant_row(VariationID="20001", Assembly="GRCh38"),
            _make_variant_row(VariationID="20002", Assembly="GRCh37"),
            _make_variant_row(VariationID="20003", Assembly="GRCh38"),
        ]
        gz_path = tmp_path / "variant_summary.txt.gz"
        _write_variant_summary_gz(gz_path, rows)

        nodes, _, _ = parse_variant_summary(gz_path, assembly="GRCh38")

        assert len(nodes) == 2
        node_ids = {n["id"] for n in nodes}
        assert "ClinVar:20001" in node_ids
        assert "ClinVar:20003" in node_ids
        assert "ClinVar:20002" not in node_ids

    def test_custom_assembly_filter(self, tmp_path: Path) -> None:
        """assembly parameter controls which rows are kept."""
        rows = [
            _make_variant_row(VariationID="30001", Assembly="GRCh37"),
            _make_variant_row(VariationID="30002", Assembly="GRCh38"),
        ]
        gz_path = tmp_path / "variant_summary.txt.gz"
        _write_variant_summary_gz(gz_path, rows)

        nodes, _, _ = parse_variant_summary(gz_path, assembly="GRCh37")

        assert len(nodes) == 1
        assert nodes[0]["id"] == "ClinVar:30001"


class TestParseVariantSummaryGeneEdges:
    def test_gene_edges_produced(self, tmp_path: Path) -> None:
        """Rows with a valid GeneID produce is_sequence_variant_of edges."""
        rows = [_make_variant_row(VariationID="40001", GeneID="672")]
        gz_path = tmp_path / "variant_summary.txt.gz"
        _write_variant_summary_gz(gz_path, rows)

        _, gene_edges, _ = parse_variant_summary(gz_path)

        assert len(gene_edges) == 1
        edge = gene_edges[0]
        assert edge["subject"] == "ClinVar:40001"
        assert edge["predicate"] == "biolink:is_sequence_variant_of"
        assert edge["object"] == "NCBIGene:672"
        assert edge["source"] == "ClinVar"
        assert edge["source_url"] == "https://www.ncbi.nlm.nih.gov/clinvar/variation/40001"

    def test_multiple_gene_edges(self, tmp_path: Path) -> None:
        """Multiple rows each with a gene ID produce one edge per row."""
        rows = [
            _make_variant_row(VariationID="40010", GeneID="672"),
            _make_variant_row(VariationID="40011", GeneID="7157"),
        ]
        gz_path = tmp_path / "variant_summary.txt.gz"
        _write_variant_summary_gz(gz_path, rows)

        _, gene_edges, _ = parse_variant_summary(gz_path)

        assert len(gene_edges) == 2
        objects = {e["object"] for e in gene_edges}
        assert "NCBIGene:672" in objects
        assert "NCBIGene:7157" in objects


class TestParseVariantSummaryPhenotypeEdges:
    def test_phenotype_edges_from_medgen_ids(self, tmp_path: Path) -> None:
        """MedGen CUIs in PhenotypeIDS produce has_phenotype edges."""
        rows = [
            _make_variant_row(
                VariationID="50001",
                PhenotypeIDS="MedGen:C0006142,OMIM:114480,MedGen:C0027672",
            )
        ]
        gz_path = tmp_path / "variant_summary.txt.gz"
        _write_variant_summary_gz(gz_path, rows)

        _, _, pheno_edges = parse_variant_summary(gz_path)

        assert len(pheno_edges) == 2
        objects = {e["object"] for e in pheno_edges}
        assert "MedGen:C0006142" in objects
        assert "MedGen:C0027672" in objects
        for edge in pheno_edges:
            assert edge["predicate"] == "biolink:has_phenotype"
            assert edge["subject"] == "ClinVar:50001"

    def test_no_phenotype_edge_when_ids_missing(self, tmp_path: Path) -> None:
        """Rows with empty or '-' PhenotypeIDS produce no phenotype edges."""
        rows = [
            _make_variant_row(VariationID="50010", PhenotypeIDS="-"),
            _make_variant_row(VariationID="50011", PhenotypeIDS=""),
            _make_variant_row(VariationID="50012", PhenotypeIDS="na"),
        ]
        gz_path = tmp_path / "variant_summary.txt.gz"
        _write_variant_summary_gz(gz_path, rows)

        _, _, pheno_edges = parse_variant_summary(gz_path)

        assert len(pheno_edges) == 0

    def test_no_phenotype_edge_when_only_non_medgen(self, tmp_path: Path) -> None:
        """Rows with only OMIM/Orphanet IDs produce no phenotype edges."""
        rows = [
            _make_variant_row(
                VariationID="50020",
                PhenotypeIDS="OMIM:114480,Orphanet:ORPHA227535",
            )
        ]
        gz_path = tmp_path / "variant_summary.txt.gz"
        _write_variant_summary_gz(gz_path, rows)

        _, _, pheno_edges = parse_variant_summary(gz_path)

        assert len(pheno_edges) == 0


class TestParseVariantSummarySkipsNoGene:
    def test_gene_id_minus_one_skips_gene_edge(self, tmp_path: Path) -> None:
        """GeneID == -1 produces no gene edge."""
        rows = [_make_variant_row(VariationID="60001", GeneID="-1")]
        gz_path = tmp_path / "variant_summary.txt.gz"
        _write_variant_summary_gz(gz_path, rows)

        nodes, gene_edges, _ = parse_variant_summary(gz_path)

        assert len(nodes) == 1
        assert len(gene_edges) == 0

    def test_gene_id_missing_value_skips_gene_edge(self, tmp_path: Path) -> None:
        """GeneID of '-' or empty produces no gene edge."""
        rows = [
            _make_variant_row(VariationID="60010", GeneID="-"),
            _make_variant_row(VariationID="60011", GeneID=""),
        ]
        gz_path = tmp_path / "variant_summary.txt.gz"
        _write_variant_summary_gz(gz_path, rows)

        nodes, gene_edges, _ = parse_variant_summary(gz_path)

        assert len(nodes) == 2
        assert len(gene_edges) == 0


# ---------------------------------------------------------------------------
# parse_var_citations tests
# ---------------------------------------------------------------------------

class TestParseVarCitations:
    def test_pubmed_edges_produced(self, tmp_path: Path) -> None:
        """PubMed citation rows produce cited_in edges."""
        citations_path = tmp_path / "var_citations.txt"
        rows = [
            {"VariationID": "17599", "AlleleID": "100001",
             "citation_source": "PubMed", "citation_id": "12345678"},
            {"VariationID": "17600", "AlleleID": "100002",
             "citation_source": "PubMed", "citation_id": "98765432"},
        ]
        _write_var_citations(citations_path, rows)

        edges = parse_var_citations(citations_path)

        assert len(edges) == 2
        subjects = {e["subject"] for e in edges}
        objects = {e["object"] for e in edges}
        assert "ClinVar:17599" in subjects
        assert "ClinVar:17600" in subjects
        assert "PMID:12345678" in objects
        assert "PMID:98765432" in objects
        for edge in edges:
            assert edge["predicate"] == "biolink:cited_in"
            assert edge["source"] == "ClinVar"

    def test_non_pubmed_citations_skipped(self, tmp_path: Path) -> None:
        """Only PubMed citations are kept; BookShelf and other sources are skipped."""
        citations_path = tmp_path / "var_citations.txt"
        rows = [
            {"VariationID": "17599", "AlleleID": "100001",
             "citation_source": "PubMed", "citation_id": "11111111"},
            {"VariationID": "17600", "AlleleID": "100002",
             "citation_source": "BookShelf", "citation_id": "NBK12345"},
            {"VariationID": "17601", "AlleleID": "100003",
             "citation_source": "OMIM", "citation_id": "114480"},
        ]
        _write_var_citations(citations_path, rows)

        edges = parse_var_citations(citations_path)

        assert len(edges) == 1
        assert edges[0]["object"] == "PMID:11111111"

    def test_empty_file_returns_empty_list(self, tmp_path: Path) -> None:
        """A file with header only returns an empty edge list."""
        citations_path = tmp_path / "var_citations.txt"
        _write_var_citations(citations_path, [])

        edges = parse_var_citations(citations_path)

        assert edges == []

    def test_provenance_on_edges(self, tmp_path: Path) -> None:
        """Each cited_in edge has source and source_url."""
        citations_path = tmp_path / "var_citations.txt"
        rows = [
            {"VariationID": "17599", "AlleleID": "100001",
             "citation_source": "PubMed", "citation_id": "22222222"},
        ]
        _write_var_citations(citations_path, rows)

        edges = parse_var_citations(citations_path)

        assert edges[0]["source"] == "ClinVar"
        assert "clinvar/variation/17599" in edges[0]["source_url"]


# ---------------------------------------------------------------------------
# End-to-end pipeline test
# ---------------------------------------------------------------------------

class TestClinvarPipelineEndToEnd:
    def test_end_to_end_with_mocked_downloads(self, tmp_path: Path) -> None:
        """Pipeline produces KGX files with correct columns given small fixtures."""
        # Set up temp config
        config = PipelineConfig(
            ncbi_email="test@example.com",
            data_dir=tmp_path / "data",
            ftp_cache_dir=tmp_path / "ftp_cache",
            kgx_output_dir=tmp_path / "kgx",
            raw_data_dir=tmp_path / "raw",
        )

        # Write fixture files into the expected cache locations
        gz_path = config.ftp_cache_dir / "variant_summary.txt.gz"
        citations_path = config.ftp_cache_dir / "var_citations.txt"

        rows_vs = [
            _make_variant_row(
                VariationID="100001",
                GeneID="672",
                PhenotypeIDS="MedGen:C0006142",
            ),
            _make_variant_row(
                VariationID="100002",
                GeneID="-1",
                PhenotypeIDS="-",
            ),
        ]
        _write_variant_summary_gz(gz_path, rows_vs)

        rows_cit = [
            {"VariationID": "100001", "AlleleID": "200001",
             "citation_source": "PubMed", "citation_id": "33333333"},
        ]
        _write_var_citations(citations_path, rows_cit)

        # Mock download to avoid network access (use skip_download=True instead)
        nodes_path, edges_path = run_clinvar_pipeline(
            config=config,
            assembly="GRCh38",
            skip_download=True,
        )

        assert nodes_path.exists(), "nodes.tsv not created"
        assert edges_path.exists(), "edges.tsv not created"

        # Check nodes.tsv columns
        with open(nodes_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            node_rows = list(reader)

        assert len(node_rows) == 2
        for row in node_rows:
            assert "id" in row
            assert row["id"].startswith("ClinVar:")
            assert row["category"] == "biolink:SequenceVariant"
            assert row["source"] == "ClinVar"
            assert row["source_url"] != ""

        # Check edges.tsv columns
        with open(edges_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            edge_rows = list(reader)

        assert len(edge_rows) == 3  # 1 gene_edge + 1 phenotype_edge + 1 citation_edge
        predicates = {e["predicate"] for e in edge_rows}
        assert "biolink:is_sequence_variant_of" in predicates
        assert "biolink:has_phenotype" in predicates
        assert "biolink:cited_in" in predicates

        required_edge_cols = ["subject", "predicate", "object", "source", "source_url"]
        for row in edge_rows:
            for col in required_edge_cols:
                assert col in row, f"Missing column '{col}' in edges.tsv"

    def test_skip_download_raises_on_missing_file(self, tmp_path: Path) -> None:
        """skip_download=True raises FileNotFoundError if cache files are absent."""
        config = PipelineConfig(
            ncbi_email="test@example.com",
            data_dir=tmp_path / "data",
            ftp_cache_dir=tmp_path / "ftp_cache",
            kgx_output_dir=tmp_path / "kgx",
            raw_data_dir=tmp_path / "raw",
        )

        with pytest.raises(FileNotFoundError):
            run_clinvar_pipeline(config=config, skip_download=True)
