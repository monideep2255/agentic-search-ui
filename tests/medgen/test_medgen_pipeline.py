"""Tests for the MedGen ETL pipeline modules.

Covers:
- parse_id_mappings: disease/phenotypic feature nodes, MONDO priority, xrefs
- parse_names: CUI-to-name mapping
- parse_mgrel: subclass_of edges (correct direction)
- parse_pubmed_links: mentioned_in edges
- parse_hpo_omim: close_match edges to HPO and OMIM
- end-to-end pipeline run on small fixture files with mocked downloads

All file operations use tmp_path. Downloads are mocked; no network access needed.
"""

import gzip
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure shared modules are importable
PIPELINE_ROOT = Path(__file__).resolve().parent.parent.parent / "system-01-data-pipelines"
sys.path.insert(0, str(PIPELINE_ROOT))

from medgen.parse_id_mappings import parse_id_mappings
from medgen.parse_names import parse_names
from medgen.parse_mgrel import parse_mgrel
from medgen.parse_pubmed_links import parse_pubmed_links
from medgen.parse_hpo_omim import parse_hpo_omim
from medgen.pipeline import run_medgen_pipeline
from shared.config import PipelineConfig


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _write_gz(path: Path, content: str) -> Path:
    """Write a gzipped UTF-8 text file at path."""
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(content)
    return path


def _make_config(tmp_path: Path) -> PipelineConfig:
    """Build a minimal PipelineConfig pointed at tmp_path directories."""
    return PipelineConfig(
        ncbi_email="test@example.com",
        ftp_cache_dir=tmp_path / "ftp_cache",
        kgx_output_dir=tmp_path / "kgx",
        data_dir=tmp_path / "data",
        raw_data_dir=tmp_path / "raw",
    )


# ---------------------------------------------------------------------------
# ID mappings tests
# ---------------------------------------------------------------------------

ID_MAPPINGS_FIXTURE = """\
#CUI|source|source_id|source_name|STY
C0006142|OMIM|114480|Breast Cancer|Disease or Syndrome
C0006142|MONDO|MONDO:0007254|breast cancer|Disease or Syndrome
C0006142|MeSH|D001943|Breast Neoplasms|Disease or Syndrome
C0006142|HPO|HP:0100013|Neoplasm of the breast|Disease or Syndrome
C1704292|OMIM|604685|Congenital Nystagmus|Finding
C1704292|MeSH|D009759|Nystagmus, Congenital|Sign or Symptom
"""


def test_parse_id_mappings_disease_node(tmp_path: Path) -> None:
    """Disease or Syndrome STY maps to biolink:Disease."""
    path = _write_gz(tmp_path / "MedGenIDMappings.txt.gz", ID_MAPPINGS_FIXTURE)
    nodes, _ = parse_id_mappings(path)

    ids = {n["id"] for n in nodes}
    # C0006142 has a MONDO row so node id should be MONDO:0007254
    assert "MONDO:0007254" in ids

    disease_node = next(n for n in nodes if n["id"] == "MONDO:0007254")
    assert disease_node["category"] == "biolink:Disease"
    assert disease_node["source"] == "MedGen"
    assert "ncbi.nlm.nih.gov/medgen/" in disease_node["source_url"]


def test_parse_id_mappings_phenotypic_feature(tmp_path: Path) -> None:
    """STY containing 'Sign or Symptom' maps to biolink:PhenotypicFeature."""
    path = _write_gz(tmp_path / "MedGenIDMappings.txt.gz", ID_MAPPINGS_FIXTURE)
    nodes, _ = parse_id_mappings(path)

    # C1704292 has Sign or Symptom STY
    phenotype_node = next(
        (n for n in nodes if n["id"] == "MedGen:C1704292"), None
    )
    assert phenotype_node is not None, "Expected MedGen:C1704292 node"
    assert phenotype_node["category"] == "biolink:PhenotypicFeature"


def test_parse_id_mappings_mondo_priority(tmp_path: Path) -> None:
    """When MONDO source_id exists it becomes the canonical node id."""
    path = _write_gz(tmp_path / "MedGenIDMappings.txt.gz", ID_MAPPINGS_FIXTURE)
    nodes, _ = parse_id_mappings(path)

    ids = {n["id"] for n in nodes}
    assert "MONDO:0007254" in ids
    # MedGen:C0006142 should NOT appear since MONDO took over
    assert "MedGen:C0006142" not in ids


def test_parse_id_mappings_xrefs(tmp_path: Path) -> None:
    """OMIM, MeSH, and HPO source_ids are collected as xrefs."""
    path = _write_gz(tmp_path / "MedGenIDMappings.txt.gz", ID_MAPPINGS_FIXTURE)
    nodes, _ = parse_id_mappings(path)

    disease_node = next(n for n in nodes if n["id"] == "MONDO:0007254")
    xrefs: list[str] = disease_node.get("xrefs", [])

    # OMIM:114480, MeSH:D001943, HPO:HP:0100013 should all appear
    assert any("114480" in x for x in xrefs), f"OMIM xref missing from {xrefs}"
    assert any("D001943" in x for x in xrefs), f"MeSH xref missing from {xrefs}"


def test_parse_id_mappings_no_mondo_fallback(tmp_path: Path) -> None:
    """When no MONDO row exists the node id falls back to MedGen:{CUI}."""
    fixture = """\
#CUI|source|source_id|source_name|STY
C9999999|OMIM|999999|Some Rare Disease|Disease or Syndrome
"""
    path = _write_gz(tmp_path / "MedGenIDMappings.txt.gz", fixture)
    nodes, _ = parse_id_mappings(path)

    assert len(nodes) == 1
    assert nodes[0]["id"] == "MedGen:C9999999"


# ---------------------------------------------------------------------------
# Names tests
# ---------------------------------------------------------------------------

NAMES_FIXTURE = """\
C0006142|Malignant neoplasm of breast|MTH|N|
C0006142|Breast Cancer|NCI|N|
C1704292|Nystagmus, Congenital|MSH|N|
C0000001|Suppressed name|SRC|Y|
C0000001|Real name|NCI|N|
"""


def test_parse_names(tmp_path: Path) -> None:
    """parse_names returns a CUI-to-name dict with preferred names."""
    path = _write_gz(tmp_path / "NAMES.RRF.gz", NAMES_FIXTURE)
    names = parse_names(path)

    assert isinstance(names, dict)
    assert "C0006142" in names
    assert names["C0006142"] == "Malignant neoplasm of breast"
    assert "C1704292" in names
    assert names["C1704292"] == "Nystagmus, Congenital"


def test_parse_names_suppressed_fallback(tmp_path: Path) -> None:
    """Non-suppressed name wins over suppressed even if suppressed came first."""
    path = _write_gz(tmp_path / "NAMES.RRF.gz", NAMES_FIXTURE)
    names = parse_names(path)
    # C0000001 has a suppressed row first but a real name second
    assert names.get("C0000001") == "Real name"


# ---------------------------------------------------------------------------
# MGREL tests
# ---------------------------------------------------------------------------

MGREL_FIXTURE = """\
C0006142|A123|AUI|CHD|C0027651|A456|AUI|isa|RB|SIB|0|N|256|AT17
C1111111|B789|AUI|PAR|C0006142|A123|AUI||RN|SIB|0|N|256|AT18
C2222222|C001|AUI|SIB|C3333333|D002|AUI||RN|SIB|0|N|256|AT19
"""


def test_parse_mgrel_subclass(tmp_path: Path) -> None:
    """CHD rows produce biolink:subclass_of edges with correct direction."""
    path = _write_gz(tmp_path / "MGREL.RRF.gz", MGREL_FIXTURE)
    edges = parse_mgrel(path)

    assert len(edges) >= 1
    edge = edges[0]
    # CUI1 is the child (subclass), CUI2 is the parent
    assert edge["subject"] == "MedGen:C0006142"
    assert edge["predicate"] == "biolink:subclass_of"
    assert edge["object"] == "MedGen:C0027651"
    assert edge["source"] == "MedGen"
    assert "ncbi.nlm.nih.gov/medgen/" in edge["source_url"]


def test_parse_mgrel_skips_non_child(tmp_path: Path) -> None:
    """PAR and SIB rows are not included in the output."""
    path = _write_gz(tmp_path / "MGREL.RRF.gz", MGREL_FIXTURE)
    edges = parse_mgrel(path)

    # Only the CHD row should be emitted
    predicates = {e["predicate"] for e in edges}
    assert predicates == {"biolink:subclass_of"}
    # The SIB/PAR rows involve C1111111->C0006142 (PAR) and C2222222 (SIB)
    subjects = {e["subject"] for e in edges}
    assert "MedGen:C1111111" not in subjects
    assert "MedGen:C2222222" not in subjects


# ---------------------------------------------------------------------------
# PubMed link tests
# ---------------------------------------------------------------------------

PUBMED_LINKS_FIXTURE = """\
#UID\tPMID
C0006142\t12345678
C0006142\t87654321
C1704292\t11111111
"""


def test_parse_pubmed_links(tmp_path: Path) -> None:
    """Rows produce biolink:mentioned_in edges with correct subject/object."""
    path = _write_gz(tmp_path / "medgen_pubmed_lnk.txt.gz", PUBMED_LINKS_FIXTURE)
    edges = parse_pubmed_links(path)

    assert len(edges) >= 1
    pmid_edges = [e for e in edges if e["predicate"] == "biolink:mentioned_in"]
    assert len(pmid_edges) >= 1

    first = pmid_edges[0]
    assert first["subject"].startswith("MedGen:")
    assert first["object"].startswith("PMID:")
    assert first["source"] == "MedGen"
    assert "ncbi.nlm.nih.gov/medgen/" in first["source_url"]


def test_parse_pubmed_links_multiple_pmids(tmp_path: Path) -> None:
    """Each CUI-PMID pair produces a separate edge."""
    path = _write_gz(tmp_path / "medgen_pubmed_lnk.txt.gz", PUBMED_LINKS_FIXTURE)
    edges = parse_pubmed_links(path)
    # Fixture has 3 data rows after the header
    assert len(edges) == 3


# ---------------------------------------------------------------------------
# HPO/OMIM mapping tests
# ---------------------------------------------------------------------------

HPO_OMIM_FIXTURE = """\
CUI\tMedGenName\tHPO_ID\tOMIM_ID\trelationship_type
C0006142\tBreast Cancer\tHP:0100013\t114480\tOMIM
C1704292\tCongenital Nystagmus\tHP:0000589\t604685\tOMIM
C3333333\tSome Condition\t-\t123456\tOMIM
C4444444\tAnother Condition\tHP:1234567\t-\tHPO
"""


def test_parse_hpo_omim_hpo_edge(tmp_path: Path) -> None:
    """Rows with valid HPO_ID produce biolink:close_match edges to HP: CURIEs."""
    path = _write_gz(tmp_path / "MedGen_HPO_OMIM_Mapping.txt.gz", HPO_OMIM_FIXTURE)
    edges = parse_hpo_omim(path)

    hpo_edges = [e for e in edges if e["object"].startswith("HP:")]
    assert len(hpo_edges) >= 1

    first = hpo_edges[0]
    assert first["predicate"] == "biolink:close_match"
    assert first["source"] == "MedGen"
    assert "ncbi.nlm.nih.gov/medgen/" in first["source_url"]


def test_parse_hpo_omim_omim_edge(tmp_path: Path) -> None:
    """Rows with valid OMIM_ID produce biolink:close_match edges to OMIM: CURIEs."""
    path = _write_gz(tmp_path / "MedGen_HPO_OMIM_Mapping.txt.gz", HPO_OMIM_FIXTURE)
    edges = parse_hpo_omim(path)

    omim_edges = [e for e in edges if e["object"].startswith("OMIM:")]
    assert len(omim_edges) >= 1

    first = omim_edges[0]
    assert first["predicate"] == "biolink:close_match"


def test_parse_hpo_omim_skips_dash_values(tmp_path: Path) -> None:
    """Rows where HPO_ID or OMIM_ID is '-' do not produce edges for that field."""
    path = _write_gz(tmp_path / "MedGen_HPO_OMIM_Mapping.txt.gz", HPO_OMIM_FIXTURE)
    edges = parse_hpo_omim(path)

    # C3333333 has '-' for HPO so should only produce an OMIM edge
    c3_edges = [e for e in edges if e["subject"] == "MedGen:C3333333"]
    assert all(e["object"].startswith("OMIM:") for e in c3_edges)

    # C4444444 has '-' for OMIM so should only produce an HPO edge
    c4_edges = [e for e in edges if e["subject"] == "MedGen:C4444444"]
    assert all(e["object"].startswith("HP:") for e in c4_edges)


def test_parse_hpo_omim_both_edges_per_row(tmp_path: Path) -> None:
    """Rows with both HPO_ID and OMIM_ID produce two edges."""
    path = _write_gz(tmp_path / "MedGen_HPO_OMIM_Mapping.txt.gz", HPO_OMIM_FIXTURE)
    edges = parse_hpo_omim(path)

    # C0006142 has both HP:0100013 and 114480
    c1_edges = [e for e in edges if e["subject"] == "MedGen:C0006142"]
    assert len(c1_edges) == 2
    objects = {e["object"] for e in c1_edges}
    assert any(o.startswith("HP:") for o in objects)
    assert any(o.startswith("OMIM:") for o in objects)


# ---------------------------------------------------------------------------
# End-to-end pipeline test
# ---------------------------------------------------------------------------

def _write_fixture_files(ftp_cache_dir: Path) -> None:
    """Write minimal fixture files for all five MedGen inputs."""
    _write_gz(
        ftp_cache_dir / "MedGenIDMappings.txt.gz",
        "#CUI|source|source_id|source_name|STY\n"
        "C0006142|OMIM|114480|Breast Cancer|Disease or Syndrome\n"
        "C0006142|MONDO|MONDO:0007254|breast cancer|Disease or Syndrome\n"
        "C0006142|MeSH|D001943|Breast Neoplasms|Disease or Syndrome\n"
        "C1704292|OMIM|604685|Congenital Nystagmus|Sign or Symptom\n",
    )
    _write_gz(
        ftp_cache_dir / "NAMES.RRF.gz",
        "C0006142|Malignant neoplasm of breast|MTH|N|\n"
        "C1704292|Nystagmus, Congenital|MSH|N|\n",
    )
    _write_gz(
        ftp_cache_dir / "MGREL.RRF.gz",
        "C1704292|A789|AUI|CHD|C0006142|A123|AUI|isa|RB|SIB|0|N|256|AT17\n",
    )
    _write_gz(
        ftp_cache_dir / "medgen_pubmed_lnk.txt.gz",
        "#UID\tPMID\n"
        "C0006142\t12345678\n",
    )
    _write_gz(
        ftp_cache_dir / "MedGen_HPO_OMIM_Mapping.txt.gz",
        "CUI\tMedGenName\tHPO_ID\tOMIM_ID\trelationship_type\n"
        "C0006142\tBreast Cancer\tHP:0100013\t114480\tOMIM\n",
    )


def test_medgen_pipeline_end_to_end(tmp_path: Path) -> None:
    """Run the full pipeline on small fixtures; verify KGX TSV output exists and is valid."""
    config = _make_config(tmp_path)
    _write_fixture_files(config.ftp_cache_dir)

    # Mock download so no network is touched
    with patch("medgen.pipeline.download_medgen_files") as mock_dl:
        mock_dl.return_value = {
            "id_mappings": config.ftp_cache_dir / "MedGenIDMappings.txt.gz",
            "names": config.ftp_cache_dir / "NAMES.RRF.gz",
            "mgrel": config.ftp_cache_dir / "MGREL.RRF.gz",
            "pubmed_links": config.ftp_cache_dir / "medgen_pubmed_lnk.txt.gz",
            "hpo_omim": config.ftp_cache_dir / "MedGen_HPO_OMIM_Mapping.txt.gz",
        }
        nodes_path, edges_path = run_medgen_pipeline(config, skip_download=False)

    # Both output files must exist
    assert nodes_path.exists(), f"nodes.tsv not found at {nodes_path}"
    assert edges_path.exists(), f"edges.tsv not found at {edges_path}"

    # nodes.tsv must have a header and at least one data row
    nodes_lines = nodes_path.read_text().strip().splitlines()
    assert len(nodes_lines) >= 2, "nodes.tsv should have header + data rows"
    header = nodes_lines[0].split("\t")
    assert "id" in header
    assert "category" in header
    assert "source" in header
    assert "source_url" in header

    # edges.tsv must have a header and at least one data row
    edges_lines = edges_path.read_text().strip().splitlines()
    assert len(edges_lines) >= 2, "edges.tsv should have header + data rows"
    edge_header = edges_lines[0].split("\t")
    assert "subject" in edge_header
    assert "predicate" in edge_header
    assert "object" in edge_header

    # Verify that MONDO:0007254 node appears in nodes output
    nodes_content = nodes_path.read_text()
    assert "MONDO:0007254" in nodes_content

    # Verify biolink:subclass_of edge appears in edges output
    edges_content = edges_path.read_text()
    assert "biolink:subclass_of" in edges_content


def test_medgen_pipeline_skip_download(tmp_path: Path) -> None:
    """Pipeline with skip_download=True reads from ftp_cache_dir without downloading."""
    config = _make_config(tmp_path)
    _write_fixture_files(config.ftp_cache_dir)

    # No mock needed; skip_download=True means no download call
    nodes_path, edges_path = run_medgen_pipeline(config, skip_download=True)

    assert nodes_path.exists()
    assert edges_path.exists()


def test_medgen_pipeline_missing_file_raises(tmp_path: Path) -> None:
    """Pipeline with skip_download=True raises FileNotFoundError for missing files."""
    config = _make_config(tmp_path)
    # Do NOT write fixture files

    with pytest.raises(FileNotFoundError):
        run_medgen_pipeline(config, skip_download=True)
