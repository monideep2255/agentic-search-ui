"""Unit tests for the bounded subgraph traversal in traversal.py (T-4.4-02).

Every test here mocks `graph_connection.execute_cypher` by monkeypatching
the name `traversal.py` imported it under, so none of these need the live
graph or the tunnel. `FakeGraph` routes by matching the exact Cypher
shapes `traversal.py` builds (a seed lookup, an outbound hop, an inbound
hop), which doubles as a check that every query this module issues stays
inside those three shapes: an unrecognized shape raises inside the fake
rather than being silently accepted.

Covers what the premise gate deliberately omits (its own module
docstring): multi-hop traversal, edge labels other than
`gene_associated_with_condition`, and the ambiguous-prefix seed lookup
(MedGen resolves to either Disease or PhenotypicFeature). Also covers a
cap of zero, which is not a shape the premise gate's live fixtures were
built to exercise at all.
"""

from __future__ import annotations

import re

import pytest

from system_03_search_agent.export import traversal
from system_03_search_agent.tools.graph_connection import GraphTimeoutError

_SEED_QUERY_RE = re.compile(r"^MATCH \(n:(?P<label>\w+) \{id: \$seed_id\}\) RETURN n LIMIT 1$")
_OUT_QUERY_RE = re.compile(
    r"^MATCH \(a:(?P<seed_label>\w+) \{id: \$seed_id\}\)-\[r:(?P<edge_label>\w+)\]->"
    r"\(b(?::(?P<far_label>\w+))?\) RETURN r, b LIMIT (?P<limit>\d+)$"
)
_IN_QUERY_RE = re.compile(
    r"^MATCH \(b(?::(?P<far_label>\w+))?\)-\[r:(?P<edge_label>\w+)\]->"
    r"\(a:(?P<seed_label>\w+) \{id: \$seed_id\}\) RETURN r, b LIMIT (?P<limit>\d+)$"
)


class FakeGraph:
    """A stand-in for `graph_connection.execute_cypher`.

    Registered responses are keyed by exactly what the real graph would
    need to answer: a seed CURIE plus label for a seed lookup, or a seed
    CURIE plus edge label plus direction for a hop. Any query text that
    does not match one of the three shapes `traversal.py` is documented to
    emit raises `AssertionError`, which is itself a check that this
    module never drifts onto a fourth query shape unnoticed.
    """

    def __init__(self) -> None:
        self.seed_vertices: dict[str, dict] = {}
        self.hop_rows: dict[tuple[str, str, str], list[dict]] = {}
        self.calls: list[str] = []
        self.raise_timeout_on_call_index: int | None = None

    def register_seed(self, curie: str, entity: dict) -> None:
        self.seed_vertices[curie] = entity

    def register_hop(
        self, seed_curie: str, edge_label: str, direction: str, rows: list[dict]
    ) -> None:
        self.hop_rows[(seed_curie, edge_label, direction)] = rows

    def __call__(
        self,
        cypher,
        params=None,
        row_limit=100,
        timeout_s=30.0,
        connection_factory=None,
        as_clause="(result agtype)",
    ):
        call_index = len(self.calls)
        self.calls.append(cypher)
        if self.raise_timeout_on_call_index == call_index:
            raise GraphTimeoutError("fake timeout for test")

        seed_match = _SEED_QUERY_RE.match(cypher)
        if seed_match:
            seed_id = params["seed_id"]
            entity = self.seed_vertices.get(seed_id)
            if entity is None or entity.get("label") != seed_match.group("label"):
                return [], 0
            return [{"n": entity}], 1

        out_match = _OUT_QUERY_RE.match(cypher)
        in_match = _IN_QUERY_RE.match(cypher)
        match = out_match or in_match
        if match:
            direction = "out" if out_match else "in"
            seed_id = params["seed_id"]
            edge_label = match.group("edge_label")
            limit = int(match.group("limit"))
            rows = self.hop_rows.get((seed_id, edge_label, direction), [])
            return rows[:limit], min(len(rows), limit)

        raise AssertionError("FakeGraph received an unrecognized query shape: " + cypher)


def _gene_entity(internal_id: int, curie: str, name: str) -> dict:
    return {
        "id": internal_id,
        "label": "Gene",
        "properties": {
            "id": curie,
            "name": name,
            "source": "NCBI Gene",
            "source_url": "https://www.ncbi.nlm.nih.gov/gene/" + curie.split(":")[1],
        },
    }


def _disease_entity(internal_id: int, curie: str) -> dict:
    return {
        "id": internal_id,
        "label": "Disease",
        "properties": {"id": curie, "name": "MedGen", "source": "MedGen"},
    }


def _edge_entity(internal_id: int, label: str, start_id: int, end_id: int) -> dict:
    return {
        "id": internal_id,
        "label": label,
        "start_id": start_id,
        "end_id": end_id,
        "properties": {
            "source": "NCBI",
            "source_url": "",
            "agent_type": "manual_agent",
            "knowledge_level": "knowledge_assertion",
        },
    }


class TestCapOfZero:
    def test_max_nodes_zero_makes_no_graph_calls_and_is_truncated(self, monkeypatch) -> None:
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "G1"))
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(seeds=["NCBIGene:1"], hops=1, max_nodes=0)

        assert fake.calls == []
        assert result.nodes == {}
        assert result.edges == []
        assert result.truncated is True
        assert {"cap": "max_nodes", "value": 0} in result.truncation
        assert result.empty_reason is not None

    def test_max_edges_zero_still_resolves_the_seed_but_traverses_no_hop(
        self, monkeypatch
    ) -> None:
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "G1"))
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(seeds=["NCBIGene:1"], hops=1, max_edges=0)

        # Exactly one call: the seed lookup. max_edges=0 must not block the
        # seed itself from resolving, since a seed vertex never consumes
        # edge budget on its own.
        assert len(fake.calls) == 1
        assert "NCBIGene:1" in result.nodes
        assert result.edges == []
        assert result.truncated is True
        assert {"cap": "max_edges", "value": 0} in result.truncation


class TestAmbiguousPrefixSeedLookup:
    def test_medgen_prefix_tries_disease_then_phenotypic_feature(self, monkeypatch) -> None:
        fake = FakeGraph()
        # Only registered under PhenotypicFeature: the Disease attempt
        # must come back empty, then the second candidate label succeeds.
        entity = {
            "id": 42,
            "label": "PhenotypicFeature",
            "properties": {"id": "MedGen:CN000001", "name": "some phenotype", "source": "HPO"},
        }
        fake.register_seed("MedGen:CN000001", entity)
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(seeds=["MedGen:CN000001"], hops=0)

        assert len(fake.calls) == 2
        assert fake.calls[0] == "MATCH (n:Disease {id: $seed_id}) RETURN n LIMIT 1"
        assert fake.calls[1] == "MATCH (n:PhenotypicFeature {id: $seed_id}) RETURN n LIMIT 1"
        assert "MedGen:CN000001" in result.nodes
        assert result.nodes["MedGen:CN000001"]["label"] == "PhenotypicFeature"
        assert result.seeds_resolved == ["MedGen:CN000001"]

    def test_unrecognized_prefix_never_issues_a_query(self, monkeypatch) -> None:
        fake = FakeGraph()
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(seeds=["NOPREFIX:1"], hops=1)

        assert fake.calls == []
        assert result.nodes == {}
        assert result.empty_reason is not None


class TestAmbiguousMaxRowLimitTruncation:
    def test_exactly_max_row_limit_rows_is_disclosed_even_with_room_left_under_both_caps(
        self, monkeypatch
    ) -> None:
        # max_nodes and max_edges are both set far above
        # graph_schema_constants.MAX_ROW_LIMIT (500), so the query's own
        # LIMIT is capped at 500 rather than at either configured budget.
        # Getting exactly 500 rows back proves nothing about whether more
        # exist beyond 500: this must still be disclosed as truncated,
        # conservatively, rather than reported as complete just because
        # neither max_nodes nor max_edges reads as exhausted by counting
        # rows already collected.
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "TP53"))
        rows = []
        for i in range(2, 502):
            edge = _edge_entity(1000 + i, "gene_associated_with_condition", start_id=1, end_id=i)
            disease = _disease_entity(i, "MedGen:C" + str(i))
            rows.append({"r": edge, "b": disease})
        fake.register_hop("NCBIGene:1", "gene_associated_with_condition", "out", rows)
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(
            seeds=["NCBIGene:1"],
            hops=1,
            edge_labels=("gene_associated_with_condition",),
            max_nodes=1000,
            max_edges=1000,
        )

        assert result.truncated is True
        caps = {entry["cap"]: entry["value"] for entry in result.truncation}
        assert caps.get("max_nodes") == 1000
        assert caps.get("max_edges") == 1000
        # Exactly 500 disease nodes plus the seed itself.
        assert len(result.nodes) == 501

    def test_an_earlier_unrelated_cap_hit_does_not_suppress_this_disclosure(self) -> None:
        # Regression guard on _Budget directly, the unit the fix actually
        # lives in. The ambiguous-truncation branch in traverse_subgraph
        # decides whether to force-mark max_nodes/max_edges by comparing
        # caps_hit before and after a mark_binding_cap call, specifically
        # so an earlier, unrelated cap already recorded earlier in the
        # same traversal can never suppress a later, distinct disclosure.
        # This reproduces exactly that shape at the _Budget level: an
        # earlier cap is already recorded, then mark_binding_cap is called
        # with plenty of room left under both caps (so it adds nothing new
        # on its own), which is the exact condition
        # traverse_subgraph's own comparison must still catch.
        budget = traversal._Budget(max_nodes=5000, max_edges=5000, time_budget_s=60.0)
        budget.mark("max_nodes", 5000)  # an earlier, unrelated cap hit
        caps_before = set(budget.caps_hit)

        budget.mark_binding_cap(node_count=10, edge_count=10)  # plenty of room left

        # mark_binding_cap itself added nothing new, which is exactly the
        # signal traverse_subgraph's own comparison (`set(budget.caps_hit)
        # == caps_before`) uses to know it must force-mark both caps for
        # this query's own ambiguous-truncation disclosure, rather than
        # wrongly treating the pre-existing "max_nodes" entry as if it
        # already covered this separate, later event.
        assert set(budget.caps_hit) == caps_before


class TestEdgeLabelSkippedWhenEndpointsDoNotMatch:
    def test_gene_seed_skips_an_edge_label_with_no_gene_endpoint(self, monkeypatch) -> None:
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "G1"))
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        # has_mesh_annotation's endpoints are (Article, OntologyClass);
        # Gene appears at neither end, so _directions_for must return no
        # directions and no hop query is ever built.
        result = traversal.traverse_subgraph(
            seeds=["NCBIGene:1"], hops=1, edge_labels=("has_mesh_annotation",)
        )

        assert len(fake.calls) == 1  # only the seed lookup
        assert result.edges == []


class TestMultiHopTraversal:
    def test_two_hops_expand_the_frontier_gene_to_disease_to_phenotype(self, monkeypatch) -> None:
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "TP53"))

        edge1 = _edge_entity(501, "gene_associated_with_condition", start_id=1, end_id=2)
        disease = _disease_entity(2, "MedGen:C0001")
        fake.register_hop(
            "NCBIGene:1",
            "gene_associated_with_condition",
            "out",
            [{"r": edge1, "b": disease}],
        )

        edge2 = _edge_entity(502, "has_phenotype", start_id=2, end_id=3)
        phenotype = {
            "id": 3,
            "label": "PhenotypicFeature",
            "properties": {"id": "HP:0001", "name": "some phenotype", "source": "HPO"},
        }
        fake.register_hop("MedGen:C0001", "has_phenotype", "out", [{"r": edge2, "b": phenotype}])

        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(
            seeds=["NCBIGene:1"],
            hops=2,
            edge_labels=("gene_associated_with_condition", "has_phenotype"),
        )

        assert set(result.nodes.keys()) == {"NCBIGene:1", "MedGen:C0001", "HP:0001"}
        assert len(result.edges) == 2
        subjects_objects = {
            (edge["subject_curie"], edge["object_curie"]) for edge in result.edges
        }
        assert ("NCBIGene:1", "MedGen:C0001") in subjects_objects
        assert ("MedGen:C0001", "HP:0001") in subjects_objects
        assert result.truncated is False

    def test_hops_zero_returns_only_the_resolved_seed_no_edges(self, monkeypatch) -> None:
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "TP53"))
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(seeds=["NCBIGene:1"], hops=0)

        assert list(result.nodes.keys()) == ["NCBIGene:1"]
        assert result.edges == []
        # No hop query was ever issued: only the one seed lookup call.
        assert len(fake.calls) == 1


class TestGraphTimeoutDuringHop:
    def test_a_timeout_on_a_hop_query_marks_time_budget_and_returns_partial(
        self, monkeypatch
    ) -> None:
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "TP53"))
        # Call 0 is the seed lookup (succeeds); call 1 is the first hop
        # query, made to time out.
        fake.raise_timeout_on_call_index = 1
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(
            seeds=["NCBIGene:1"],
            hops=1,
            edge_labels=("gene_associated_with_condition",),
            time_budget_s=5.0,
        )

        assert result.truncated is True
        assert {"cap": "time_budget_s", "value": 5} in result.truncation
        assert list(result.nodes.keys()) == ["NCBIGene:1"]
        assert result.edges == []


class TestEdgeLabelValidation:
    def test_unknown_edge_label_raises_before_any_query(self, monkeypatch) -> None:
        def _explode(*args, **kwargs):
            raise AssertionError("execute_cypher must never be called for an invalid edge label")

        monkeypatch.setattr(traversal, "execute_cypher", _explode)

        with pytest.raises(ValueError, match="not_a_real_label"):
            traversal.traverse_subgraph(seeds=["NCBIGene:1"], edge_labels=("not_a_real_label",))

    def test_negative_hops_raises(self) -> None:
        with pytest.raises(ValueError, match="hops"):
            traversal.traverse_subgraph(seeds=["NCBIGene:1"], hops=-1)


class TestNoVariableLengthPatternEverEmitted:
    def test_hop_cypher_never_contains_an_asterisk(self) -> None:
        cypher = traversal._hop_cypher("Gene", "gene_associated_with_condition", "Disease", "out", 5)
        assert "*" not in cypher
        assert "[r:gene_associated_with_condition]" in cypher

    def test_hop_cypher_rejects_an_unknown_vertex_label(self) -> None:
        with pytest.raises(ValueError):
            traversal._hop_cypher("NotARealLabel", "gene_associated_with_condition", "Disease", "out", 5)

    def test_hop_cypher_rejects_an_unknown_edge_label(self) -> None:
        with pytest.raises(ValueError):
            traversal._hop_cypher("Gene", "not_a_real_edge", "Disease", "out", 5)

    def test_hop_cypher_rejects_a_non_positive_limit(self) -> None:
        with pytest.raises(ValueError):
            traversal._hop_cypher("Gene", "gene_associated_with_condition", "Disease", "out", 0)


class TestDirectionsFor:
    def test_mixed_endpoint_label_tries_both_directions_unlabelled(self) -> None:
        directions = traversal._directions_for("Gene", "close_match")
        assert set(directions) == {("out", None), ("in", None)}

    def test_self_pair_label_tries_both_directions_labelled(self) -> None:
        directions = traversal._directions_for("Gene", "orthologous_to")
        assert set(directions) == {("out", "Gene"), ("in", "Gene")}

    def test_asymmetric_pair_where_seed_is_the_start_is_outbound_only(self) -> None:
        directions = traversal._directions_for("Gene", "gene_associated_with_condition")
        assert directions == [("out", "Disease")]

    def test_asymmetric_pair_where_seed_is_the_end_is_inbound_only(self) -> None:
        directions = traversal._directions_for("Gene", "is_sequence_variant_of")
        assert directions == [("in", "SequenceVariant")]

    def test_label_with_no_endpoint_at_this_vertex_label_yields_nothing(self) -> None:
        directions = traversal._directions_for("Gene", "has_mesh_annotation")
        assert directions == []
