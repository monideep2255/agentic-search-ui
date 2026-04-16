"""Tests for the NCBI Taxonomy ETL pipeline modules.

Covers:
- parse_nodes: correct CURIEs, root exclusion, edge direction, rank field
- parse_names: scientific-name-only filtering, dict return type
- end-to-end pipeline run on small fixture files with no network access

All file operations use tmp_path. No downloads; no network.

Format note:
    NCBI taxdump uses \\t|\\t as field delimiter and \\t|\\n as row terminator.
    These fixtures use the exact delimiter - do NOT substitute plain tabs.
"""

import sys
from pathlib import Path

import pytest

PIPELINE_ROOT = Path(__file__).resolve().parent.parent.parent / "system-01-data-pipelines"
sys.path.insert(0, str(PIPELINE_ROOT))

from taxonomy.parse_nodes import parse_nodes
from taxonomy.parse_names import parse_names
from taxonomy.pipeline import run_taxonomy_pipeline
from shared.config import PipelineConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Real taxdump format: \t|\t between fields, \t|\n at line end
NODES_DMP = (
    "1\t|\t1\t|\tno rank\t|\t\t|\n"
    "2\t|\t131567\t|\tdomain\t|\t\t|\n"
    "9606\t|\t9605\t|\tspecies\t|\t\t|\n"
)

NAMES_DMP = (
    "1\t|\troot\t|\t\t|\tscientific name\t|\n"
    "2\t|\tBacteria\t|\t\t|\tscientific name\t|\n"
    "9606\t|\tHomo sapiens\t|\t\t|\tscientific name\t|\n"
    "9606\t|\thuman\t|\t\t|\tcommon name\t|\n"
)


def _write_dmp(path: Path, content: str) -> Path:
    """Write a plain-text .dmp fixture file."""
    path.write_text(content, encoding="utf-8")
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
# parse_nodes tests
# ---------------------------------------------------------------------------

def test_parse_nodes_basic(tmp_path: Path) -> None:
    """Three lines in nodes.dmp produce exactly three partial node dicts."""
    nodes_dmp = _write_dmp(tmp_path / "nodes.dmp", NODES_DMP)
    partial_nodes, _ = parse_nodes(nodes_dmp)

    assert len(partial_nodes) == 3

    node_ids = {n["id"] for n in partial_nodes}
    assert "NCBITaxon:1" in node_ids
    assert "NCBITaxon:2" in node_ids
    assert "NCBITaxon:9606" in node_ids


def test_parse_nodes_root_has_no_edge(tmp_path: Path) -> None:
    """The root taxon (tax_id == parent_tax_id == 1) produces no subclass_of edge."""
    nodes_dmp = _write_dmp(tmp_path / "nodes.dmp", NODES_DMP)
    _, edges = parse_nodes(nodes_dmp)

    subjects = {e["subject"] for e in edges}
    assert "NCBITaxon:1" not in subjects, (
        "Root taxon should not produce a self-referential subclass_of edge"
    )


def test_parse_nodes_edge_direction(tmp_path: Path) -> None:
    """Edge subject is the child; edge object is the parent."""
    nodes_dmp = _write_dmp(tmp_path / "nodes.dmp", NODES_DMP)
    _, edges = parse_nodes(nodes_dmp)

    # 9606 -> parent 9605
    human_edge = next(
        (e for e in edges if e["subject"] == "NCBITaxon:9606"), None
    )
    assert human_edge is not None, "Expected edge for NCBITaxon:9606"
    assert human_edge["predicate"] == "biolink:subclass_of"
    assert human_edge["object"] == "NCBITaxon:9605"


def test_parse_nodes_rank_field(tmp_path: Path) -> None:
    """Rank is populated from column 2 of nodes.dmp."""
    nodes_dmp = _write_dmp(tmp_path / "nodes.dmp", NODES_DMP)
    partial_nodes, _ = parse_nodes(nodes_dmp)

    human_node = next(n for n in partial_nodes if n["id"] == "NCBITaxon:9606")
    assert human_node["rank"] == "species"

    root_node = next(n for n in partial_nodes if n["id"] == "NCBITaxon:1")
    assert root_node["rank"] == "no rank"


def test_parse_nodes_category_and_provenance(tmp_path: Path) -> None:
    """Every node has the correct category, source, and source_url."""
    nodes_dmp = _write_dmp(tmp_path / "nodes.dmp", NODES_DMP)
    partial_nodes, _ = parse_nodes(nodes_dmp)

    for node in partial_nodes:
        assert node["category"] == "biolink:OrganismTaxon"
        assert node["source"] == "NCBI Taxonomy"
        assert "ncbi.nlm.nih.gov" in node["source_url"]
        assert "wwwtax.cgi" in node["source_url"]


def test_parse_nodes_non_root_edges_count(tmp_path: Path) -> None:
    """Three nodes (root self-parent, plus two real children) produce two edges."""
    nodes_dmp = _write_dmp(tmp_path / "nodes.dmp", NODES_DMP)
    _, edges = parse_nodes(nodes_dmp)

    # Root (1) excluded; nodes 2 and 9606 each produce one edge
    assert len(edges) == 2


# ---------------------------------------------------------------------------
# parse_names tests
# ---------------------------------------------------------------------------

def test_parse_names_scientific_only(tmp_path: Path) -> None:
    """Common name rows are filtered out; only scientific names are kept."""
    names_dmp = _write_dmp(tmp_path / "names.dmp", NAMES_DMP)
    result = parse_names(names_dmp)

    # Fixture has one common name row for 9606 ("human"); must not appear
    # in the dict (only the scientific name "Homo sapiens" should be there)
    assert result["9606"] == "Homo sapiens"
    # Dict should have exactly 3 entries (root, Bacteria, Homo sapiens)
    assert len(result) == 3


def test_parse_names_returns_dict(tmp_path: Path) -> None:
    """parse_names returns a dict mapping str tax_id to str name."""
    names_dmp = _write_dmp(tmp_path / "names.dmp", NAMES_DMP)
    result = parse_names(names_dmp)

    assert isinstance(result, dict)
    for key, value in result.items():
        assert isinstance(key, str)
        assert isinstance(value, str)


def test_parse_names_all_entries(tmp_path: Path) -> None:
    """Each of the three taxa in the fixture gets its scientific name."""
    names_dmp = _write_dmp(tmp_path / "names.dmp", NAMES_DMP)
    result = parse_names(names_dmp)

    assert result["1"] == "root"
    assert result["2"] == "Bacteria"
    assert result["9606"] == "Homo sapiens"


# ---------------------------------------------------------------------------
# End-to-end pipeline test
# ---------------------------------------------------------------------------

def test_taxonomy_pipeline_end_to_end(tmp_path: Path) -> None:
    """Run the pipeline on fixture files; verify KGX TSV output is correct."""
    config = _make_config(tmp_path)

    # Write fixture .dmp files into the taxonomy cache directory
    taxonomy_dir = config.ftp_cache_dir / "taxonomy"
    taxonomy_dir.mkdir(parents=True, exist_ok=True)
    _write_dmp(taxonomy_dir / "nodes.dmp", NODES_DMP)
    _write_dmp(taxonomy_dir / "names.dmp", NAMES_DMP)

    # Run pipeline with skip_download=True (no network)
    nodes_path, edges_path = run_taxonomy_pipeline(
        config=config,
        skip_download=True,
        force_download=False,
    )

    # Both output files must exist
    assert nodes_path.exists(), f"nodes.tsv not found at {nodes_path}"
    assert edges_path.exists(), f"edges.tsv not found at {edges_path}"

    # nodes.tsv must have a header and data rows
    nodes_lines = nodes_path.read_text().strip().splitlines()
    assert len(nodes_lines) >= 2, "nodes.tsv should have header + at least one data row"

    node_header = nodes_lines[0].split("\t")
    assert "id" in node_header
    assert "category" in node_header
    assert "name" in node_header
    assert "source" in node_header
    assert "source_url" in node_header

    # edges.tsv must have a header and data rows
    edges_lines = edges_path.read_text().strip().splitlines()
    assert len(edges_lines) >= 2, "edges.tsv should have header + at least one data row"

    edge_header = edges_lines[0].split("\t")
    assert "subject" in edge_header
    assert "predicate" in edge_header
    assert "object" in edge_header
    assert "source" in edge_header
    assert "source_url" in edge_header

    # Verify key content
    nodes_content = nodes_path.read_text()
    assert "NCBITaxon:9606" in nodes_content
    assert "Homo sapiens" in nodes_content
    assert "biolink:OrganismTaxon" in nodes_content

    edges_content = edges_path.read_text()
    assert "biolink:subclass_of" in edges_content
    assert "NCBITaxon:9606" in edges_content

    # Root taxon should not appear as a subclass_of subject
    edge_data_lines = edges_lines[1:]
    root_self_edges = [
        line for line in edge_data_lines
        if line.split("\t")[0] == "NCBITaxon:1"
    ]
    assert len(root_self_edges) == 0, (
        "Root taxon NCBITaxon:1 should not appear as a subclass_of subject"
    )


def test_taxonomy_pipeline_missing_files_raises(tmp_path: Path) -> None:
    """Pipeline with skip_download=True raises FileNotFoundError for missing .dmp files."""
    config = _make_config(tmp_path)
    # Do NOT write .dmp files

    with pytest.raises(FileNotFoundError):
        run_taxonomy_pipeline(config, skip_download=True)
