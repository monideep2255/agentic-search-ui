"""Integration tests for the 5-database merge pipeline.

Writes minimal per-database KGX fixtures to a temporary kgx output dir, runs
run_five_database_merge, and asserts on the merged outputs, stub injection,
validation, and markdown report. No network, no FTP.

The synthetic graph used here mirrors the real cross-pipeline edges that
gate 2 must validate:

  Gene       NCBIGene:672 (BRCA1) --in_taxon-->            NCBITaxon:9606
  Gene       NCBIGene:672         --mentioned_in-->        PMID:12345678
  ClinVar    ClinVar:12345        --is_sequence_variant_of--> NCBIGene:672
  ClinVar    ClinVar:12345        --has_phenotype-->       MedGen:C0006142
  PubMed     PMID:12345678        --has_mesh_annotation--> MeSH:D001943
  Taxonomy   NCBITaxon:9606       --subclass_of-->         NCBITaxon:9605

Depends on:
    - system-01-data-pipelines/shared/config.py
    - system-01-data-pipelines/shared/merger.py
    - system-01-data-pipelines/merge/pipeline.py
"""

import csv
from pathlib import Path

import pytest

from merge.pipeline import DEFAULT_DATABASES, run_five_database_merge
from shared.config import PipelineConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_nodes(path: Path, rows: list[dict]) -> None:
    """Write a minimal nodes.tsv with required KGX columns."""
    fieldnames = ["id", "category", "name", "source", "source_url"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=fieldnames, delimiter="\t",
            extrasaction="ignore", restval="",
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_edges(path: Path, rows: list[dict]) -> None:
    """Write a minimal edges.tsv with required KGX columns."""
    fieldnames = ["subject", "predicate", "object", "source", "source_url"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=fieldnames, delimiter="\t",
            extrasaction="ignore", restval="",
        )
        writer.writeheader()
        writer.writerows(rows)


def _build_five_database_fixture(kgx_dir: Path) -> None:
    """Create nodes.tsv and edges.tsv for all 5 databases under kgx_dir."""

    # Gene pipeline
    _write_nodes(kgx_dir / "gene" / "nodes.tsv", [
        {"id": "NCBIGene:672", "category": "biolink:Gene", "name": "BRCA1",
         "source": "ncbi_gene", "source_url": "https://www.ncbi.nlm.nih.gov/gene/672"},
    ])
    _write_edges(kgx_dir / "gene" / "edges.tsv", [
        {"subject": "NCBIGene:672", "predicate": "biolink:in_taxon",
         "object": "NCBITaxon:9606", "source": "ncbi_gene",
         "source_url": "https://www.ncbi.nlm.nih.gov/gene/672"},
        {"subject": "NCBIGene:672", "predicate": "biolink:mentioned_in",
         "object": "PMID:12345678", "source": "ncbi_gene",
         "source_url": "https://www.ncbi.nlm.nih.gov/gene/672"},
    ])

    # ClinVar pipeline
    _write_nodes(kgx_dir / "clinvar" / "nodes.tsv", [
        {"id": "ClinVar:12345", "category": "biolink:SequenceVariant",
         "name": "BRCA1 variant", "source": "ncbi_clinvar",
         "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/12345"},
    ])
    _write_edges(kgx_dir / "clinvar" / "edges.tsv", [
        {"subject": "ClinVar:12345", "predicate": "biolink:is_sequence_variant_of",
         "object": "NCBIGene:672", "source": "ncbi_clinvar",
         "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/12345"},
        {"subject": "ClinVar:12345", "predicate": "biolink:has_phenotype",
         "object": "MedGen:C0006142", "source": "ncbi_clinvar",
         "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/12345"},
    ])

    # MedGen pipeline
    _write_nodes(kgx_dir / "medgen" / "nodes.tsv", [
        {"id": "MedGen:C0006142", "category": "biolink:Disease",
         "name": "Breast cancer", "source": "ncbi_medgen",
         "source_url": "https://www.ncbi.nlm.nih.gov/medgen/C0006142"},
    ])
    _write_edges(kgx_dir / "medgen" / "edges.tsv", [])

    # PubMed pipeline (article + MeSH stub + has_mesh_annotation edge)
    _write_nodes(kgx_dir / "pubmed" / "nodes.tsv", [
        {"id": "PMID:12345678", "category": "biolink:Article",
         "name": "BRCA1 breast cancer review", "source": "PubMed",
         "source_url": "https://pubmed.ncbi.nlm.nih.gov/12345678/"},
        {"id": "MeSH:D001943", "category": "biolink:OntologyClass",
         "name": "Breast Neoplasms", "source": "PubMed MeSH",
         "source_url": "https://www.ncbi.nlm.nih.gov/mesh/?term=D001943"},
    ])
    _write_edges(kgx_dir / "pubmed" / "edges.tsv", [
        {"subject": "PMID:12345678", "predicate": "biolink:has_mesh_annotation",
         "object": "MeSH:D001943", "source": "PubMed",
         "source_url": "https://pubmed.ncbi.nlm.nih.gov/12345678/"},
    ])

    # Taxonomy pipeline
    _write_nodes(kgx_dir / "taxonomy" / "nodes.tsv", [
        {"id": "NCBITaxon:9606", "category": "biolink:OrganismTaxon",
         "name": "Homo sapiens", "source": "NCBI Taxonomy",
         "source_url": "https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=9606"},
        {"id": "NCBITaxon:9605", "category": "biolink:OrganismTaxon",
         "name": "Homo", "source": "NCBI Taxonomy",
         "source_url": "https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=9605"},
    ])
    _write_edges(kgx_dir / "taxonomy" / "edges.tsv", [
        {"subject": "NCBITaxon:9606", "predicate": "biolink:subclass_of",
         "object": "NCBITaxon:9605", "source": "NCBI Taxonomy",
         "source_url": "https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=9606"},
    ])


@pytest.fixture
def full_fixture_config(tmp_path: Path) -> PipelineConfig:
    """Config pointing at a tmp_path KGX dir containing all 5 databases."""
    kgx_dir = tmp_path / "kgx"
    _build_five_database_fixture(kgx_dir)
    return PipelineConfig(
        ncbi_email="test@example.com",
        data_dir=tmp_path,
        ftp_cache_dir=tmp_path / "ftp_cache",
        kgx_output_dir=kgx_dir,
        raw_data_dir=tmp_path / "raw",
    )


# ---------------------------------------------------------------------------
# Base wiring: all five databases merged, output files written
# ---------------------------------------------------------------------------

def test_run_five_database_merge_writes_outputs(full_fixture_config: PipelineConfig) -> None:
    result = run_five_database_merge(full_fixture_config)

    assert result["databases_found"] == list(DEFAULT_DATABASES)
    assert result["nodes_path"].exists()
    assert result["edges_path"].exists()
    assert result["report_path"].exists()


def test_run_five_database_merge_no_stubs_when_all_endpoints_resolve(
    full_fixture_config: PipelineConfig,
) -> None:
    result = run_five_database_merge(full_fixture_config)

    # Every edge endpoint in the fixture resolves to a real node.
    assert result["stub_count"] == 0
    assert result["validation"]["dangling_edges"] == []


def test_merged_nodes_cover_all_five_categories(full_fixture_config: PipelineConfig) -> None:
    result = run_five_database_merge(full_fixture_config)
    categories = set(result["validation"]["category_counts"].keys())

    assert "biolink:Gene" in categories
    assert "biolink:SequenceVariant" in categories
    assert "biolink:Disease" in categories
    assert "biolink:Article" in categories
    assert "biolink:OntologyClass" in categories
    assert "biolink:OrganismTaxon" in categories


# ---------------------------------------------------------------------------
# Cross-pipeline edge resolution (the reason this phase exists)
# ---------------------------------------------------------------------------

def test_gene2pubmed_edges_resolve_to_pubmed_articles(
    full_fixture_config: PipelineConfig,
) -> None:
    """Gene's mentioned_in edges must resolve to PubMed Article nodes with zero stubs."""
    result = run_five_database_merge(full_fixture_config)

    report = result["report_path"].read_text(encoding="utf-8")
    assert "Gene mentioned_in PubMed Article edges resolved: 1" in report
    # And that edge is not dangling.
    dangling_subjects = {e.get("subject") for e in result["validation"]["dangling_edges"]}
    dangling_objects = {e.get("object") for e in result["validation"]["dangling_edges"]}
    assert "NCBIGene:672" not in dangling_subjects
    assert "PMID:12345678" not in dangling_objects


def test_in_taxon_edges_resolve_to_taxonomy_nodes(
    full_fixture_config: PipelineConfig,
) -> None:
    """Gene's in_taxon edges must resolve to NCBITaxon nodes from the taxonomy pipeline."""
    result = run_five_database_merge(full_fixture_config)

    report = result["report_path"].read_text(encoding="utf-8")
    assert "Gene in_taxon NCBITaxon edges resolved: 1" in report


def test_pubmed_mesh_edges_resolve_to_mesh_nodes(
    full_fixture_config: PipelineConfig,
) -> None:
    """PubMed has_mesh_annotation edges must resolve to MeSH OntologyClass nodes."""
    result = run_five_database_merge(full_fixture_config)

    report = result["report_path"].read_text(encoding="utf-8")
    assert "PubMed Article has_mesh_annotation MeSH edges resolved: 1" in report


def test_taxonomy_subclass_edges_resolve(full_fixture_config: PipelineConfig) -> None:
    """NCBITaxon subclass_of edges must resolve to other NCBITaxon nodes."""
    result = run_five_database_merge(full_fixture_config)

    report = result["report_path"].read_text(encoding="utf-8")
    assert "NCBITaxon subclass_of NCBITaxon edges resolved: 1" in report


# ---------------------------------------------------------------------------
# Dangling-reference behavior: stubs created when a cross-pipeline endpoint is missing
# ---------------------------------------------------------------------------

def test_missing_pubmed_database_triggers_pmid_stub(tmp_path: Path) -> None:
    """If gene2pubmed references a PMID and pubmed is missing, a PMID stub is injected."""
    kgx_dir = tmp_path / "kgx"
    _build_five_database_fixture(kgx_dir)

    config = PipelineConfig(
        ncbi_email="test@example.com",
        data_dir=tmp_path,
        ftp_cache_dir=tmp_path / "ftp_cache",
        kgx_output_dir=kgx_dir,
        raw_data_dir=tmp_path / "raw",
    )

    # Merge only gene + taxonomy; omit pubmed so PMID:12345678 is dangling.
    result = run_five_database_merge(config, databases=("gene", "taxonomy"))

    assert result["stub_count"] >= 1
    nodes = list(csv.DictReader(
        result["nodes_path"].open(encoding="utf-8"), delimiter="\t"
    ))
    stub_ids = {n["id"] for n in nodes if n.get("source") == "stub"}
    assert "PMID:12345678" in stub_ids


def test_missing_taxonomy_triggers_ncbitaxon_stub(tmp_path: Path) -> None:
    """If in_taxon references NCBITaxon and taxonomy is missing, a Taxon stub is injected."""
    kgx_dir = tmp_path / "kgx"
    _build_five_database_fixture(kgx_dir)

    config = PipelineConfig(
        ncbi_email="test@example.com",
        data_dir=tmp_path,
        ftp_cache_dir=tmp_path / "ftp_cache",
        kgx_output_dir=kgx_dir,
        raw_data_dir=tmp_path / "raw",
    )

    result = run_five_database_merge(config, databases=("gene", "pubmed"))

    nodes = list(csv.DictReader(
        result["nodes_path"].open(encoding="utf-8"), delimiter="\t"
    ))
    stub_ids = {n["id"] for n in nodes if n.get("source") == "stub"}
    assert "NCBITaxon:9606" in stub_ids

    # Verify the stub carries the correct inferred category.
    taxon_stub = next(n for n in nodes if n["id"] == "NCBITaxon:9606")
    assert taxon_stub["category"] == "biolink:OrganismTaxon"


# ---------------------------------------------------------------------------
# Graceful handling of missing databases
# ---------------------------------------------------------------------------

def test_skips_database_with_no_kgx_output(tmp_path: Path) -> None:
    """If a database subdir has no TSVs, the merge logs a warning and skips it."""
    kgx_dir = tmp_path / "kgx"
    _build_five_database_fixture(kgx_dir)

    # Delete pubmed outputs so the merge has to skip that database.
    (kgx_dir / "pubmed" / "nodes.tsv").unlink()
    (kgx_dir / "pubmed" / "edges.tsv").unlink()

    config = PipelineConfig(
        ncbi_email="test@example.com",
        data_dir=tmp_path,
        ftp_cache_dir=tmp_path / "ftp_cache",
        kgx_output_dir=kgx_dir,
        raw_data_dir=tmp_path / "raw",
    )
    result = run_five_database_merge(config)

    assert "pubmed" not in result["databases_found"]
    assert "gene" in result["databases_found"]
    # The missing pubmed nodes now cause a PMID stub rather than a dangling edge.
    assert result["validation"]["dangling_edges"] == []


def test_raises_when_no_databases_found(tmp_path: Path) -> None:
    """If no databases have outputs, the pipeline raises FileNotFoundError."""
    kgx_dir = tmp_path / "kgx"
    kgx_dir.mkdir()
    config = PipelineConfig(
        ncbi_email="test@example.com",
        data_dir=tmp_path,
        ftp_cache_dir=tmp_path / "ftp_cache",
        kgx_output_dir=kgx_dir,
        raw_data_dir=tmp_path / "raw",
    )

    with pytest.raises(FileNotFoundError):
        run_five_database_merge(config)
