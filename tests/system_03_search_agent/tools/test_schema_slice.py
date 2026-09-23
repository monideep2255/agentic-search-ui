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


def test_build_schema_slice_lookup_stays_bounded_but_reaches_two_hops() -> None:
    """A lookup slice is bounded, and bounded at two hops, not zero or one.

    This assertion has moved twice, and both moves are the same lesson.

    It first asserted `Article` was ABSENT, which followed correctly from
    `lookup` mapping to 0 hops. That was right for the design and wrong
    for the system, and the difference cost four review rounds: `lookup`
    is not a classification at this phase, Think emits it as a hardcoded
    stub for EVERY query (T-2.0-07), so a 0-hop Gene slice was the only
    schema the generator ever saw and it held exactly one edge,
    `orthologous_to`. Asked which diseases are associated with BRCA1, the
    model was handed a schema with no disease in it and returned
    twenty-five non-human orthologs, `status="ok"`, every row cited.

    It then asserted `OntologyClass` and `PhenotypicFeature` were absent,
    which followed from a floor of 1. Finding F-2.1-A5-03: a floor of 1
    was also the CEILING, because no class Think emits maps above it, so
    every question in the system got exactly one hop and any two-hop
    question was unanswerable by construction. A phenotypic-feature
    question returned four cited DISEASES, which is the same failure
    displaced by one hop.

    What is asserted now is the property that survives both moves: the
    slice must CONTAIN what a question anchored here plausibly needs, and
    must still be strictly narrower than the full schema. Both halves
    matter. Without the first, the generator answers a question the schema
    cannot express. Without the second, this stops being a slice at all
    and the cost control it exists for is gone.

    IT HAS NOW MOVED A THIRD TIME, 2026-09-23, and the lesson is a new one
    rather than a repeat. The property was right and its WITNESS was wrong:
    this asserted that PhenotypicFeature sits two hops from Gene via
    Disease, which was true of `EDGE_ENDPOINTS` and never true of the
    graph. Measured that night: no Disease vertex anywhere has an outgoing
    `has_phenotype` edge, every PhenotypicFeature vertex is an unpopulated
    `[stub]`, and `has_phenotype` actually joins SequenceVariant to
    Disease. So this arm passed for fourteen months by agreeing with a
    constant that was wrong, while the model's own schema prompt, built
    from that same constant, was being told the same false thing.

    The witness is now OntologyClass, two hops from Gene via Article
    through `mentioned_in` then `has_mesh_annotation`, a path with real
    data on both edges (probed 2026-09-23: 25 articles for BRCA1, 14 MeSH
    annotations for a sampled PMID). The guard against F-2.1-A5-03, that a
    hop floor must not also be a ceiling, is unchanged and is what this arm
    is still for.
    """
    sliced = schema_slice.build_schema_slice("lookup", ["NCBIGene:672"])
    label_lines = [line.strip() for line in _vertex_label_lines(sliced)]

    # One hop from Gene, and the flagship question's answer.
    assert any(line.startswith("Disease:") for line in label_lines), (
        "a Gene lookup cannot answer a disease question without the "
        f"Disease label in scope. Got: {label_lines}"
    )
    # Two hops from Gene, via Article. F-2.1-A5-03's own reproduction,
    # re-witnessed 2026-09-23 on a path the graph actually has.
    assert any(line.startswith("OntologyClass:") for line in label_lines), (
        "OntologyClass is two hops from Gene, via Article, and a question "
        "about a gene's MeSH topics cannot be expressed without it. A floor "
        f"that is also a ceiling is the defect this asserts against. Got: {label_lines}"
    )
    assert "has_mesh_annotation" in sliced, (
        "the Article to OntologyClass edge must be offered, not just its "
        "endpoint labels; _edges_for_labels needs BOTH endpoints in scope "
        "and that is exactly what the old floor cut off"
    )
    # The counterpart, and the reason this arm changed. PhenotypicFeature is
    # unreachable in the real graph, so a slice that offers it is describing
    # a path the generator cannot use. Measured 2026-09-23.
    assert not any(line.startswith("PhenotypicFeature:") for line in label_lines), (
        "PhenotypicFeature has no incoming edge in the live graph and every "
        "such vertex is an unpopulated stub, so offering it to the generator "
        f"invites a query that can only return zero rows. Got: {label_lines}"
    )
    # Still a slice, not the whole topology.
    assert len(sliced) < len(schema_slice.full_schema_text()), (
        "a lookup slice must still be narrower than the full schema, or "
        "it is not a slice and the cost control it exists for is gone"
    )


def test_the_hop_floor_keeps_lookup_from_slicing_on_a_stub_classification() -> None:
    """Pin the floor itself, so removing it fails loudly rather than quietly.

    The per-class table still records the intended design (`lookup` is 0
    hops). The floor is what stands between that design and a stub
    classifier, and it is the fix for the fourth judge's PREMISE failure.
    """
    assert schema_slice._QUERY_CLASS_HOPS["lookup"] == 0, (
        "the intended design is unchanged: a true lookup needs 0 hops"
    )
    assert schema_slice._STUB_CLASSIFIER_HOP_FLOOR >= 1, (
        "with Think emitting a hardcoded 'lookup', a 0-hop slice offers a "
        "Gene query only orthologous_to and no disease at all"
    )


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
