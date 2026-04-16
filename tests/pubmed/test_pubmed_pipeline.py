"""Tests for the PubMed ETL pipeline modules.

All tests use tmp_path for file I/O. Downloads are mocked. Inline fixture
XML is used throughout - no network access, no real FTP downloads.

Tests:
    test_parse_pubmed_xml_basic               - node structure from 2-article fixture
    test_parse_pubmed_xml_pmid_extraction     - PMID formatted as PMID:12345 CURIE
    test_parse_pubmed_xml_mesh_edges          - MeSH edges with correct predicate
    test_parse_pubmed_xml_mesh_ui_curie       - MeSH UI formatted as MeSH:D012345
    test_parse_pubmed_xml_missing_abstract    - article without Abstract yields valid node
    test_parse_pubmed_xml_no_mesh             - article without MeshHeadingList yields 0 edges
    test_parse_pubmed_xml_skip_missing_pmid   - article without PMID is skipped, not raised
    test_collect_mesh_nodes_creates_stubs     - stub nodes have correct format and provenance
    test_pubmed_pipeline_end_to_end           - full pipeline on small XML files in tmp_path
"""

import csv
import gzip
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Make the shared and pubmed packages importable from test context
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "system-01-data-pipelines"))

from pubmed.parse_pubmed_xml import parse_pubmed_file
from pubmed.parse_mesh_nodes import collect_mesh_nodes
from pubmed.pipeline import run_pubmed_pipeline
from shared.config import PipelineConfig


# ── XML Fixture Helpers ───────────────────────────────────────────────────────

_FULL_ARTICLE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID Version="1">12345678</PMID>
      <Article>
        <ArticleTitle>Test article one</ArticleTitle>
        <Abstract><AbstractText>Sample abstract.</AbstractText></Abstract>
      </Article>
      <MeshHeadingList>
        <MeshHeading>
          <DescriptorName UI="D012345" MajorTopicYN="N">Sample Term</DescriptorName>
        </MeshHeading>
      </MeshHeadingList>
    </MedlineCitation>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID Version="1">87654321</PMID>
      <Article>
        <ArticleTitle>Test article two</ArticleTitle>
        <Abstract><AbstractText>Another abstract.</AbstractText></Abstract>
      </Article>
      <MeshHeadingList>
        <MeshHeading>
          <DescriptorName UI="D000818" MajorTopicYN="Y">Animals</DescriptorName>
        </MeshHeading>
        <MeshHeading>
          <DescriptorName UI="D006801" MajorTopicYN="N">Humans</DescriptorName>
        </MeshHeading>
      </MeshHeadingList>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""

_NO_ABSTRACT_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID Version="1">11111111</PMID>
      <Article>
        <ArticleTitle>Article without abstract</ArticleTitle>
      </Article>
      <MeshHeadingList>
        <MeshHeading>
          <DescriptorName UI="D002318" MajorTopicYN="N">Cardiovascular Diseases</DescriptorName>
        </MeshHeading>
      </MeshHeadingList>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""

_NO_MESH_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID Version="1">22222222</PMID>
      <Article>
        <ArticleTitle>Article without MeSH</ArticleTitle>
        <Abstract><AbstractText>Has an abstract but no MeSH.</AbstractText></Abstract>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""

_MISSING_PMID_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <Article>
        <ArticleTitle>Article without PMID</ArticleTitle>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID Version="1">33333333</PMID>
      <Article>
        <ArticleTitle>Article with PMID</ArticleTitle>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""


def _write_gz(path: Path, content: str) -> Path:
    """Write a string as a gzipped file at path."""
    with gzip.open(path, "wb") as fh:
        fh.write(content.encode("utf-8"))
    return path


def _make_config(tmp_path: Path) -> PipelineConfig:
    """Create a minimal PipelineConfig pointing at tmp_path."""
    return PipelineConfig(
        ncbi_email="test@example.com",
        data_dir=tmp_path / "data",
        ftp_cache_dir=tmp_path / "data" / "ftp_cache",
        kgx_output_dir=tmp_path / "data" / "kgx",
        raw_data_dir=tmp_path / "data" / "raw",
    )


# ── Tests: parse_pubmed_file ──────────────────────────────────────────────────

def test_parse_pubmed_xml_basic(tmp_path: Path) -> None:
    """Two articles in fixture XML yield two (node, edges) tuples."""
    gz_path = _write_gz(tmp_path / "pubmed_test.xml.gz", _FULL_ARTICLE_XML)

    results = list(parse_pubmed_file(gz_path))

    assert len(results) == 2, f"Expected 2 articles, got {len(results)}"
    for node, edges in results:
        assert node["category"] == "biolink:Article"
        assert node["source"] == "PubMed"
        assert node["source_url"].startswith("https://pubmed.ncbi.nlm.nih.gov/")
        assert node["name"]


def test_parse_pubmed_xml_pmid_extraction(tmp_path: Path) -> None:
    """PMID is extracted and formatted as PMID:<number> CURIE."""
    gz_path = _write_gz(tmp_path / "pubmed_test.xml.gz", _FULL_ARTICLE_XML)

    results = list(parse_pubmed_file(gz_path))

    node_ids = [node["id"] for node, _ in results]
    assert "PMID:12345678" in node_ids
    assert "PMID:87654321" in node_ids


def test_parse_pubmed_xml_mesh_edges(tmp_path: Path) -> None:
    """MeSH edges use the biolink:has_mesh_annotation predicate."""
    gz_path = _write_gz(tmp_path / "pubmed_test.xml.gz", _FULL_ARTICLE_XML)

    results = list(parse_pubmed_file(gz_path))
    all_edges = [edge for _, edges in results for edge in edges]

    assert len(all_edges) == 3, f"Expected 3 edges total, got {len(all_edges)}"
    for edge in all_edges:
        assert edge["predicate"] == "biolink:has_mesh_annotation"
        assert edge["source"] == "PubMed"
        assert "source_url" in edge and edge["source_url"]


def test_parse_pubmed_xml_mesh_ui_curie(tmp_path: Path) -> None:
    """MeSH object ID is formatted as MeSH:<UI>."""
    gz_path = _write_gz(tmp_path / "pubmed_test.xml.gz", _FULL_ARTICLE_XML)

    results = list(parse_pubmed_file(gz_path))
    all_edges = [edge for _, edges in results for edge in edges]

    object_ids = {edge["object"] for edge in all_edges}
    assert "MeSH:D012345" in object_ids
    assert "MeSH:D000818" in object_ids
    assert "MeSH:D006801" in object_ids


def test_parse_pubmed_xml_missing_abstract(tmp_path: Path) -> None:
    """Article without Abstract element still produces a valid node."""
    gz_path = _write_gz(tmp_path / "no_abstract.xml.gz", _NO_ABSTRACT_XML)

    results = list(parse_pubmed_file(gz_path))

    assert len(results) == 1
    node, edges = results[0]
    assert node["id"] == "PMID:11111111"
    assert node["name"] == "Article without abstract"
    assert "description" not in node or node.get("description") == ""
    assert node["category"] == "biolink:Article"


def test_parse_pubmed_xml_no_mesh(tmp_path: Path) -> None:
    """Article without MeshHeadingList produces 0 edges."""
    gz_path = _write_gz(tmp_path / "no_mesh.xml.gz", _NO_MESH_XML)

    results = list(parse_pubmed_file(gz_path))

    assert len(results) == 1
    node, edges = results[0]
    assert node["id"] == "PMID:22222222"
    assert edges == []


def test_parse_pubmed_xml_skip_missing_pmid(tmp_path: Path) -> None:
    """Article without PMID is silently skipped; pipeline does not raise."""
    gz_path = _write_gz(tmp_path / "missing_pmid.xml.gz", _MISSING_PMID_XML)

    results = list(parse_pubmed_file(gz_path))

    # Only the second article (with PMID:33333333) should be yielded
    assert len(results) == 1
    node, _ = results[0]
    assert node["id"] == "PMID:33333333"


# ── Tests: collect_mesh_nodes ─────────────────────────────────────────────────

def test_collect_mesh_nodes_creates_stubs() -> None:
    """Stub nodes have correct id format, category, and provenance."""
    uis = {"D012345", "D000818", "D006801"}
    nodes = collect_mesh_nodes(uis)

    assert len(nodes) == 3

    for node in nodes:
        assert node["id"].startswith("MeSH:")
        assert node["category"] == "biolink:OntologyClass"
        assert node["source"] == "MeSH (via PubMed)"
        assert "meshb.nlm.nih.gov" in node["source_url"]
        assert node["name"].startswith("[MeSH]")

    node_ids = {n["id"] for n in nodes}
    assert "MeSH:D012345" in node_ids
    assert "MeSH:D000818" in node_ids
    assert "MeSH:D006801" in node_ids


def test_collect_mesh_nodes_empty_input() -> None:
    """Empty set input returns an empty list without error."""
    nodes = collect_mesh_nodes(set())
    assert nodes == []


# ── Tests: full pipeline end-to-end ──────────────────────────────────────────

def test_pubmed_pipeline_end_to_end(tmp_path: Path) -> None:
    """Pipeline runs on small in-memory XML files; KGX output has correct shape.

    Mocks download_pubmed_files to return two small XML files already written
    to tmp_path, then runs the full pipeline and verifies:
    - nodes.tsv and edges.tsv exist
    - nodes.tsv has required columns
    - edges.tsv has required columns
    - article nodes are present
    - MeSH stub nodes are present
    - MeSH edges have the correct predicate
    """
    config = _make_config(tmp_path)

    pubmed_cache = config.ftp_cache_dir / "pubmed"
    pubmed_cache.mkdir(parents=True, exist_ok=True)

    file1 = _write_gz(pubmed_cache / "pubmed26n0001.xml.gz", _FULL_ARTICLE_XML)
    file2 = _write_gz(pubmed_cache / "pubmed26n0002.xml.gz", _NO_ABSTRACT_XML)

    with patch("pubmed.pipeline.download_pubmed_files", return_value=[file1, file2]):
        nodes_path, edges_path = run_pubmed_pipeline(
            config=config,
            skip_download=False,
            force_download=False,
            include_updates=False,
        )

    # Both files exist
    assert nodes_path.exists(), f"nodes.tsv not found at {nodes_path}"
    assert edges_path.exists(), f"edges.tsv not found at {edges_path}"

    # Read and validate nodes
    with open(nodes_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        nodes = list(reader)
        fieldnames = reader.fieldnames or []

    for required_col in ["id", "category", "name", "source", "source_url"]:
        assert required_col in fieldnames, f"Missing column: {required_col}"

    node_ids = {n["id"] for n in nodes}

    # Articles from fixture files
    assert "PMID:12345678" in node_ids, "Missing PMID:12345678"
    assert "PMID:87654321" in node_ids, "Missing PMID:87654321"
    assert "PMID:11111111" in node_ids, "Missing PMID:11111111 (no-abstract article)"

    # MeSH stubs from fixture files
    assert "MeSH:D012345" in node_ids, "Missing MeSH:D012345 stub"
    assert "MeSH:D000818" in node_ids, "Missing MeSH:D000818 stub"

    # Read and validate edges
    with open(edges_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        edges = list(reader)
        edge_fieldnames = reader.fieldnames or []

    for required_col in ["subject", "predicate", "object", "source", "source_url"]:
        assert required_col in edge_fieldnames, f"Missing edge column: {required_col}"

    assert len(edges) > 0, "edges.tsv should have at least one edge"
    for edge in edges:
        assert edge["predicate"] == "biolink:has_mesh_annotation"
        assert edge["subject"].startswith("PMID:")
        assert edge["object"].startswith("MeSH:")
        assert edge["source"] == "PubMed"
        assert edge["source_url"].startswith("https://pubmed.ncbi.nlm.nih.gov/")


def test_pubmed_pipeline_skip_download(tmp_path: Path) -> None:
    """skip_download=True uses cached files without calling the download function."""
    config = _make_config(tmp_path)

    pubmed_cache = config.ftp_cache_dir / "pubmed"
    pubmed_cache.mkdir(parents=True, exist_ok=True)
    _write_gz(pubmed_cache / "pubmed26n0001.xml.gz", _NO_MESH_XML)

    # download_pubmed_files should NOT be called when skip_download=True
    with patch("pubmed.pipeline.download_pubmed_files") as mock_dl:
        nodes_path, edges_path = run_pubmed_pipeline(
            config=config,
            skip_download=True,
        )
        mock_dl.assert_not_called()

    assert nodes_path.exists()
    assert edges_path.exists()

    with open(nodes_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        nodes = list(reader)

    node_ids = {n["id"] for n in nodes}
    assert "PMID:22222222" in node_ids


def test_pubmed_pipeline_no_cached_files_raises(tmp_path: Path) -> None:
    """skip_download=True raises FileNotFoundError if no cached files exist."""
    config = _make_config(tmp_path)
    # Do NOT create any files in the cache directory

    with pytest.raises(FileNotFoundError, match="no .xml.gz files found"):
        run_pubmed_pipeline(config=config, skip_download=True)
