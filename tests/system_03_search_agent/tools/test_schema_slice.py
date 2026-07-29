"""Tests for schema_slice.py (T-2.1-02).

Covers: full_schema_text's completeness and determinism, build_schema_slice
filtering by query_class and target_entities, the endpoint-pair guarantee
for every emitted edge label, the presence of the three performance rules,
and byte-identical determinism proven by SHA-256 comparison.
"""

from __future__ import annotations

import hashlib

import pytest

from system_03_search_agent.tools import schema_slice
from system_03_search_agent.tools.graph_schema_constants import (
    CURIE_PREFIXES,
    EDGE_LABELS,
    VERTEX_LABELS,
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# GRAPH_NAME re-export
# ---------------------------------------------------------------------------


def test_graph_name_reexported() -> None:
    assert schema_slice.GRAPH_NAME == "ncbi_kg"


# ---------------------------------------------------------------------------
# full_schema_text
# ---------------------------------------------------------------------------


def test_full_schema_text_contains_every_vertex_label() -> None:
    text = schema_slice.full_schema_text()
    for label in VERTEX_LABELS:
        assert label in text


def test_full_schema_text_contains_every_edge_label() -> None:
    text = schema_slice.full_schema_text()
    for edge in EDGE_LABELS:
        assert edge in text


def test_full_schema_text_contains_every_curie_prefix() -> None:
    text = schema_slice.full_schema_text()
    for prefix in CURIE_PREFIXES:
        assert prefix in text


def test_full_schema_text_states_performance_rules() -> None:
    text = schema_slice.full_schema_text()
    assert "always specify the edge label" in text
    assert "match by id" in text.lower() or "matching by name falls back" in text
    assert "regex" in text.lower()


def test_full_schema_text_deterministic_across_calls() -> None:
    first = schema_slice.full_schema_text()
    second = schema_slice.full_schema_text()
    assert first == second
    assert _sha256(first) == _sha256(second)


def test_full_schema_text_every_edge_has_endpoint_pair_stated() -> None:
    text = schema_slice.full_schema_text()
    # Every edge line must state either an explicit "X to Y" pair or the
    # mixed-pair note; no edge line may be silent about its endpoints.
    for edge in EDGE_LABELS:
        line = next(line for line in text.splitlines() if line.strip().startswith(f"{edge}:"))
        assert "to" in line or "mixed" in line


# ---------------------------------------------------------------------------
# build_schema_slice
# ---------------------------------------------------------------------------


def test_build_schema_slice_rejects_unknown_query_class() -> None:
    with pytest.raises(ValueError):
        schema_slice.build_schema_slice("not_a_real_class")


def test_build_schema_slice_exploratory_is_full_schema() -> None:
    sliced = schema_slice.build_schema_slice("exploratory", ["NCBIGene:672"])
    assert sliced == schema_slice.full_schema_text()


def test_build_schema_slice_no_target_entities_is_full_schema() -> None:
    sliced = schema_slice.build_schema_slice("lookup", None)
    assert sliced == schema_slice.full_schema_text()


def test_build_schema_slice_unrecognized_prefix_falls_back_to_full() -> None:
    sliced = schema_slice.build_schema_slice("lookup", ["UNKNOWNPREFIX:1"])
    assert sliced == schema_slice.full_schema_text()


def test_build_schema_slice_lookup_is_narrower_than_full() -> None:
    sliced = schema_slice.build_schema_slice("lookup", ["NCBIGene:672"])
    full = schema_slice.full_schema_text()
    assert len(sliced) < len(full)
    assert "Gene" in sliced


def _vertex_label_lines(text: str) -> list[str]:
    """Extract just the "Vertex labels:" section's lines, since the always
    present performance-rules text (Rule 3) legitimately names Article and
    Gene as illustrative large-label examples regardless of what the slice
    actually restricts, so a whole-text substring check is the wrong tool
    for asserting which labels a slice restricts itself to.
    """
    lines = text.splitlines()
    start = lines.index("Vertex labels:") + 1
    end = next(i for i in range(start, len(lines)) if not lines[i].strip())
    return lines[start:end]


def test_build_schema_slice_lookup_excludes_unrelated_labels() -> None:
    sliced = schema_slice.build_schema_slice("lookup", ["NCBIGene:672"])
    # A lookup with only a Gene target should not need to mention a wholly
    # unrelated large label such as Article in its vertex label section.
    label_lines = _vertex_label_lines(sliced)
    assert not any(line.strip().startswith("Article:") for line in label_lines)


def test_build_schema_slice_single_hop_includes_direct_neighbor() -> None:
    sliced = schema_slice.build_schema_slice("single_hop", ["NCBIGene:672"])
    # Gene participates_in BiologicalProcess is a direct one-hop edge.
    assert "participates_in" in sliced
    assert "BiologicalProcess" in sliced


def test_build_schema_slice_multi_hop_reaches_further_than_single_hop() -> None:
    single = schema_slice.build_schema_slice("single_hop", ["NCBIGene:672"])
    multi = schema_slice.build_schema_slice("multi_hop", ["NCBIGene:672"])
    assert len(multi) >= len(single)


def test_build_schema_slice_variant_target_reaches_gene_via_labeled_edge() -> None:
    sliced = schema_slice.build_schema_slice("single_hop", ["ClinVar:17660"])
    assert "is_sequence_variant_of" in sliced
    assert "Gene" in sliced


def test_build_schema_slice_states_performance_rules() -> None:
    sliced = schema_slice.build_schema_slice("single_hop", ["NCBIGene:672"])
    assert "always specify the edge label" in sliced
    assert "regex" in sliced.lower()


def test_build_schema_slice_deterministic_same_args() -> None:
    first = schema_slice.build_schema_slice("multi_hop", ["NCBIGene:672", "ClinVar:17660"])
    second = schema_slice.build_schema_slice("multi_hop", ["NCBIGene:672", "ClinVar:17660"])
    assert first == second
    assert _sha256(first) == _sha256(second)


def test_build_schema_slice_edges_carry_endpoint_pairs() -> None:
    sliced = schema_slice.build_schema_slice("multi_hop", ["NCBIGene:672"])
    lines = sliced.splitlines()
    edge_section = False
    for line in lines:
        if line.startswith("Edge labels"):
            edge_section = True
            continue
        if edge_section:
            if not line.strip():
                break
            assert "typical endpoints" in line
