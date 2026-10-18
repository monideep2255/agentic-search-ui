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
from system_03_search_agent.tools.graph_schema_constants import (
    MAX_ROW_LIMIT,
    VERTEX_LABELS,
)

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
        # Finding F-4.4-09: the per-call budget was implemented and never
        # asserted, because the fake accepted `timeout_s` and threw it
        # away. It is recorded now, and TestPerCallTimeout reads it.
        self.timeouts: list[float] = []
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
        self.timeouts.append(timeout_s)
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

    def test_an_unrecognized_prefix_still_sweeps_every_vertex_label(
        self, monkeypatch
    ) -> None:
        # Finding F-4.4-52. `LABEL_CURIE_PREFIXES` is a convention about
        # which prefixes a label typically carries, not an exhaustive
        # index, and treating it as one made a whole region of the graph
        # unreachable as a seed. A prefix nothing maps must still be
        # looked for under every vertex label before the export is allowed
        # to say the graph does not hold it.
        fake = FakeGraph()
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(seeds=["NOPREFIX:1"], hops=1)

        assert len(fake.calls) == len(VERTEX_LABELS)
        assert result.nodes == {}
        assert result.empty_reason is not None

    def test_a_namedthing_seed_resolves_though_no_prefix_maps_to_that_label(
        self, monkeypatch
    ) -> None:
        # The live case F-4.4-52 was reproduced from: `OMIM:100070` is a
        # real `NamedThing` vertex, `NamedThing` maps to the EMPTY prefix
        # tuple, and `OMIM` is not a key under any label, so before this
        # fix the export reported a vertex the graph demonstrably holds as
        # absent, with exit code 0.
        fake = FakeGraph()
        fake.register_seed(
            "OMIM:100070",
            {
                "id": 77,
                "label": "NamedThing",
                "properties": {"id": "OMIM:100070", "name": "[stub] OMIM:100070"},
            },
        )
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(seeds=["OMIM:100070"], hops=0)

        assert result.seeds_resolved == ["OMIM:100070"]
        assert "OMIM:100070" in result.nodes
        assert result.nodes["OMIM:100070"]["label"] == "NamedThing"
        assert result.empty_reason is None

    def test_the_prefix_hint_is_tried_before_the_rest_of_the_sweep(self) -> None:
        # The hint still orders the search; it just no longer bounds it.
        candidates = traversal._seed_candidate_labels("NCBIGene:7157")
        assert candidates[0] == "Gene"
        assert set(candidates) == set(VERTEX_LABELS)
        assert len(candidates) == len(VERTEX_LABELS)


class TestTruncationIsAttributedToTheBoundThatCausedIt:
    """Finding F-4.4-51: a cap that was not reached must not be reported.

    The live reproduction was `--max-nodes 1200 --max-edges 1200` on a hub
    gene, which collected 501 nodes and 500 edges and reported hitting
    both caps. The real limiter was the traversal's own per-query row
    ceiling, a constant that appeared in no cap, no truncation entry, and
    no output line, and raising the caps could not change the outcome.
    """

    def test_the_per_query_row_limit_is_named_and_the_unreached_caps_are_not(
        self, monkeypatch
    ) -> None:
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "TP53"))
        rows = []
        for i in range(2, 2 + MAX_ROW_LIMIT):
            edge = _edge_entity(1000 + i, "gene_associated_with_condition", start_id=1, end_id=i)
            disease = _disease_entity(i, "MedGen:C" + str(i))
            rows.append({"r": edge, "b": disease})
        fake.register_hop("NCBIGene:1", "gene_associated_with_condition", "out", rows)
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(
            seeds=["NCBIGene:1"],
            hops=1,
            edge_labels=("gene_associated_with_condition",),
            max_nodes=1200,
            max_edges=1200,
        )

        caps = {entry["cap"]: entry["value"] for entry in result.truncation}
        assert result.truncated is True
        assert caps == {"per_query_row_limit": MAX_ROW_LIMIT}
        # The counts the manifest would sit beside: 501 nodes is nowhere
        # near a cap of 1200, so naming max_nodes here would be a claim
        # contradicted by the manifest's own numbers.
        assert len(result.nodes) == MAX_ROW_LIMIT + 1
        assert len(result.edges) == MAX_ROW_LIMIT

    def test_a_cap_below_the_row_ceiling_is_named_and_the_row_ceiling_is_not(
        self, monkeypatch
    ) -> None:
        # The mirror case, so neither assertion above is passing for the
        # trivial reason that one of the two names is never emitted.
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "TP53"))
        rows = []
        for i in range(2, 2 + MAX_ROW_LIMIT):
            edge = _edge_entity(1000 + i, "gene_associated_with_condition", start_id=1, end_id=i)
            disease = _disease_entity(i, "MedGen:C" + str(i))
            rows.append({"r": edge, "b": disease})
        fake.register_hop("NCBIGene:1", "gene_associated_with_condition", "out", rows)
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(
            seeds=["NCBIGene:1"],
            hops=1,
            edge_labels=("gene_associated_with_condition",),
            max_nodes=20,
            max_edges=1000,
        )

        caps = {entry["cap"]: entry["value"] for entry in result.truncation}
        assert caps.get("max_nodes") == 20
        assert "per_query_row_limit" not in caps
        assert len(result.nodes) == 20
        assert result.rows_fetched_not_exported > 0

    def test_a_complete_small_neighbourhood_reports_no_cap_at_all(
        self, monkeypatch
    ) -> None:
        # The third arm. Without it, an implementation that always marked
        # something would pass both assertions above.
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "TP53"))
        rows = [
            {
                "r": _edge_entity(2000 + i, "gene_associated_with_condition", 1, i),
                "b": _disease_entity(i, "MedGen:C" + str(i)),
            }
            for i in range(2, 14)
        ]
        fake.register_hop("NCBIGene:1", "gene_associated_with_condition", "out", rows)
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(
            seeds=["NCBIGene:1"],
            hops=1,
            edge_labels=("gene_associated_with_condition",),
        )

        assert result.truncation == []
        assert result.truncated is False
        assert len(result.edges) == 12
        assert result.rows_fetched_not_exported == 0


class TestNoEdgeLabelCanStarveAnother:
    """Finding F-4.4-50, the phase's only critical, as an offline case.

    The premise gate pins the same property against the live graph. This
    is its unit-level mirror, so the property is checkable without the
    tunnel and so a future change that reintroduces first-come, first
    -served scheduling fails here in 0.1 seconds rather than only in a
    live run.
    """

    def _fake_with_one_hub_and_one_small_label(self) -> FakeGraph:
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "TP53"))
        # `mentioned_in` comes SECOND in EDGE_LABELS and is the hub;
        # `gene_associated_with_condition` comes thirteenth and holds the
        # twelve rows a consumer actually asked the graph for.
        hub_rows = []
        for i in range(1000, 1000 + MAX_ROW_LIMIT):
            hub_rows.append(
                {
                    "r": _edge_entity(90000 + i, "mentioned_in", 1, i),
                    "b": {
                        "id": i,
                        "label": "Article",
                        "properties": {"id": "PMID:" + str(i), "name": "an article"},
                    },
                }
            )
        fake.register_hop("NCBIGene:1", "mentioned_in", "out", hub_rows)
        small_rows = [
            {
                "r": _edge_entity(3000 + i, "gene_associated_with_condition", 1, i),
                "b": _disease_entity(i, "MedGen:C" + str(i)),
            }
            for i in range(2, 14)
        ]
        fake.register_hop(
            "NCBIGene:1", "gene_associated_with_condition", "out", small_rows
        )
        return fake

    def test_the_low_cardinality_label_survives_a_default_export(self, monkeypatch) -> None:
        fake = self._fake_with_one_hub_and_one_small_label()
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(seeds=["NCBIGene:1"], hops=1)

        predicates = {edge["label"] for edge in result.edges}
        assert "gene_associated_with_condition" in predicates
        assert len(predicates) > 1, "one predicate is the starvation shape itself"
        diseases = {curie for curie in result.nodes if curie.startswith("MedGen:")}
        assert len(diseases) == 12, "all twelve low-cardinality neighbours must survive"

    def test_the_hub_label_still_gets_its_share(self, monkeypatch) -> None:
        # The fair share cuts both ways: the fix must not starve the hub
        # either, or it would just be the same defect pointed the other
        # way round.
        fake = self._fake_with_one_hub_and_one_small_label()
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(seeds=["NCBIGene:1"], hops=1)

        articles = {curie for curie in result.nodes if curie.startswith("PMID:")}
        assert len(articles) > 100

    def test_the_manifest_input_lists_only_the_labels_a_query_was_issued_for(
        self, monkeypatch
    ) -> None:
        # Finding F-4.4-02 / F-4.4-50's disclosure half, at the traversal
        # layer where the value is produced.
        fake = self._fake_with_one_hub_and_one_small_label()
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(seeds=["NCBIGene:1"], hops=1)

        traversed = set(result.edge_labels_traversed)
        # A Gene seed cannot match has_mesh_annotation, has_phenotype,
        # cited_in or subclass_of at either endpoint, so no query is ever
        # issued for them and they must not appear.
        assert "has_mesh_annotation" not in traversed
        assert "has_phenotype" not in traversed
        assert "cited_in" not in traversed
        assert "subclass_of" not in traversed
        assert "mentioned_in" in traversed
        assert "gene_associated_with_condition" in traversed
        assert set(result.edge_labels_requested) != traversed

    def test_a_budget_smaller_than_the_work_item_count_is_disclosed_not_hidden(
        self, monkeypatch
    ) -> None:
        # The one case fairness cannot save: room smaller than the number
        # of work items means some items are never queried at all. The
        # stated contract is that those are visible in
        # edge_labels_traversed rather than implied.
        fake = self._fake_with_one_hub_and_one_small_label()
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(seeds=["NCBIGene:1"], hops=1, max_nodes=3)

        assert len(result.edge_labels_traversed) < len(result.edge_labels_requested)
        assert result.truncated is True
        assert {"cap": "max_nodes", "value": 3} in result.truncation


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
        assert result.edge_labels_traversed == ()
        # And the reason is not misreported as the hop limit: no requested
        # label can attach to this vertex, so nothing was left unexpanded
        # that this request could ever have reached.
        assert result.hop_limit_reached is False
        assert result.unexpanded_frontier_nodes == 0


class TestMultiHopTraversal:
    def test_two_hops_expand_the_frontier_gene_to_article_to_mesh(self, monkeypatch) -> None:
        """Two hops really expand the frontier, over a path the graph has.

        REWITNESSED 2026-09-23. This arm used to walk Gene to Disease to
        PhenotypicFeature through `has_phenotype`, and it passed because
        `EDGE_ENDPOINTS` said that edge joined Disease to PhenotypicFeature.
        It does not. Measured against the live graph that night: no Disease
        vertex anywhere has an outgoing `has_phenotype` edge, every
        PhenotypicFeature vertex is an unpopulated `[stub]`, and
        `has_phenotype` actually joins SequenceVariant to Disease.

        So the arm was exercising a traversal the exporter can never perform
        against real data, while agreeing with a constant that was wrong. The
        PROPERTY it exists for is untouched and still asserted here: a
        two-hop request must reach a vertex that is two hops out, not stop at
        one. Only the witness moved, to Gene through `mentioned_in` to
        Article through `has_mesh_annotation` to OntologyClass, which is a
        real path on both edges (probed the same night: 25 articles for
        BRCA1, 14 MeSH annotations for a sampled PMID).
        """
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "TP53"))

        edge1 = _edge_entity(501, "mentioned_in", start_id=1, end_id=2)
        article = {
            "id": 2,
            "label": "Article",
            "properties": {
                "id": "PMID:1",
                "name": "some article",
                "source": "PubMed",
            },
        }
        fake.register_hop(
            "NCBIGene:1",
            "mentioned_in",
            "out",
            [{"r": edge1, "b": article}],
        )

        edge2 = _edge_entity(502, "has_mesh_annotation", start_id=2, end_id=3)
        mesh_term = {
            "id": 3,
            "label": "OntologyClass",
            "properties": {
                "id": "MeSH:D000001",
                "name": "[MeSH] D000001",
                "source": "MeSH (via PubMed)",
            },
        }
        fake.register_hop(
            "PMID:1", "has_mesh_annotation", "out", [{"r": edge2, "b": mesh_term}]
        )

        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(
            seeds=["NCBIGene:1"],
            hops=2,
            edge_labels=("mentioned_in", "has_mesh_annotation"),
        )

        assert set(result.nodes.keys()) == {"NCBIGene:1", "PMID:1", "MeSH:D000001"}
        assert len(result.edges) == 2
        subjects_objects = {
            (edge["subject_curie"], edge["object_curie"]) for edge in result.edges
        }
        assert ("NCBIGene:1", "PMID:1") in subjects_objects
        assert ("PMID:1", "MeSH:D000001") in subjects_objects
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

    def test_seed_lookup_cypher_rejects_an_unknown_vertex_label(self) -> None:
        with pytest.raises(ValueError):
            traversal._seed_lookup_cypher("NotARealLabel")

    def test_seed_lookup_cypher_never_contains_an_asterisk(self) -> None:
        assert "*" not in traversal._seed_lookup_cypher("Gene")

    def test_hop_cypher_rejects_an_unknown_vertex_label(self) -> None:
        with pytest.raises(ValueError):
            traversal._hop_cypher("NotARealLabel", "gene_associated_with_condition", "Disease", "out", 5)

    def test_hop_cypher_rejects_an_unknown_edge_label(self) -> None:
        with pytest.raises(ValueError):
            traversal._hop_cypher("Gene", "not_a_real_edge", "Disease", "out", 5)

    def test_hop_cypher_rejects_a_non_positive_limit(self) -> None:
        with pytest.raises(ValueError):
            traversal._hop_cypher("Gene", "gene_associated_with_condition", "Disease", "out", 0)


class TestDuplicateSeeds:
    """Finding F-4.4-60: a repeated seed cost a second round of queries."""

    def test_a_repeated_seed_is_looked_up_once_and_expanded_once(
        self, monkeypatch
    ) -> None:
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "TP53"))
        fake.register_hop(
            "NCBIGene:1",
            "gene_associated_with_condition",
            "out",
            [
                {
                    "r": _edge_entity(4001, "gene_associated_with_condition", 1, 2),
                    "b": _disease_entity(2, "MedGen:C1"),
                }
            ],
        )
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(
            seeds=["NCBIGene:1", "NCBIGene:1"],
            hops=1,
            edge_labels=("gene_associated_with_condition",),
        )

        # One seed lookup and one hop query, not two of each.
        assert len(fake.calls) == 2
        assert len(result.edges) == 1
        # The requested list is echoed as given, never deduplicated, so a
        # consumer can still compare it against what they asked for.
        assert result.seeds_requested == ["NCBIGene:1", "NCBIGene:1"]
        assert result.seeds_resolved == ["NCBIGene:1", "NCBIGene:1"]


class TestEveryDiscardedRowIsCounted:
    """Finding F-4.4-08: a dropped row was counted nowhere and disclosable nowhere.

    The judge could not construct a live input that reaches either drop
    path, which is precisely why each one needs a test that does: an
    uncounted drop is invisible the day the graph first produces one, and
    a counter nothing exercises is a branch nobody has proved works.
    """

    def test_an_edge_whose_endpoints_do_not_resolve_is_counted(self, monkeypatch) -> None:
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "TP53"))
        # end_id 999 belongs to no vertex this traversal collected, and
        # the far vertex carries no CURIE of its own, so the edge cannot
        # be attributed to two real endpoints.
        orphan_edge = _edge_entity(5001, "gene_associated_with_condition", 1, 999)
        far_vertex_without_curie = {"id": 999, "label": "Disease", "properties": {}}
        fake.register_hop(
            "NCBIGene:1",
            "gene_associated_with_condition",
            "out",
            [{"r": orphan_edge, "b": far_vertex_without_curie}],
        )
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(
            seeds=["NCBIGene:1"],
            hops=1,
            edge_labels=("gene_associated_with_condition",),
        )

        assert result.edges == []
        assert result.dropped[traversal.DROP_UNRESOLVED_ENDPOINT] == 1

    def test_a_malformed_edge_payload_is_counted(self, monkeypatch) -> None:
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "TP53"))
        fake.register_hop(
            "NCBIGene:1",
            "gene_associated_with_condition",
            "out",
            [{"r": {"not": "an edge entity"}, "b": _disease_entity(2, "MedGen:C1")}],
        )
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(
            seeds=["NCBIGene:1"],
            hops=1,
            edge_labels=("gene_associated_with_condition",),
        )

        assert result.edges == []
        assert result.dropped[traversal.DROP_MALFORMED_EDGE] == 1

    def test_a_repeated_edge_id_is_counted_as_a_duplicate_not_a_loss(
        self, monkeypatch
    ) -> None:
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "TP53"))
        edge = _edge_entity(6001, "gene_associated_with_condition", 1, 2)
        disease = _disease_entity(2, "MedGen:C1")
        fake.register_hop(
            "NCBIGene:1",
            "gene_associated_with_condition",
            "out",
            [{"r": edge, "b": disease}, {"r": edge, "b": disease}],
        )
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(
            seeds=["NCBIGene:1"],
            hops=1,
            edge_labels=("gene_associated_with_condition",),
        )

        assert len(result.edges) == 1
        assert result.dropped[traversal.DROP_DUPLICATE_EDGE] == 1

    def test_a_clean_traversal_reports_every_counter_at_zero(self, monkeypatch) -> None:
        # "Nothing was dropped" is stated, not inferred from an absent key.
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "TP53"))
        fake.register_hop(
            "NCBIGene:1",
            "gene_associated_with_condition",
            "out",
            [
                {
                    "r": _edge_entity(7001, "gene_associated_with_condition", 1, 2),
                    "b": _disease_entity(2, "MedGen:C1"),
                }
            ],
        )
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(
            seeds=["NCBIGene:1"],
            hops=1,
            edge_labels=("gene_associated_with_condition",),
        )

        assert set(result.dropped) == {
            traversal.DROP_MALFORMED_EDGE,
            traversal.DROP_UNRESOLVED_ENDPOINT,
            traversal.DROP_DUPLICATE_EDGE,
        }
        assert sum(result.dropped.values()) == 0


class TestPerCallTimeout:
    """Finding F-4.4-09: the 30 second per-call budget had no test at all.

    T-4.4-02's fifth criterion is that each individual graph call returns
    or errors within the `cypher_query` per-call budget. It was met by
    inspection and asserted nowhere, because the fake accepted `timeout_s`
    and ignored it.
    """

    def test_every_call_carries_a_timeout_inside_the_per_call_budget(
        self, monkeypatch
    ) -> None:
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "TP53"))
        fake.register_hop(
            "NCBIGene:1",
            "gene_associated_with_condition",
            "out",
            [
                {
                    "r": _edge_entity(8001, "gene_associated_with_condition", 1, 2),
                    "b": _disease_entity(2, "MedGen:C1"),
                }
            ],
        )
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        traversal.traverse_subgraph(seeds=["NCBIGene:1"], hops=1)

        assert fake.timeouts, "no call was made, so nothing was asserted"
        for timeout_s in fake.timeouts:
            assert 1.0 <= timeout_s <= traversal._PER_CALL_TIMEOUT_S

    def test_a_wall_clock_budget_below_the_per_call_budget_shortens_each_call(
        self, monkeypatch
    ) -> None:
        # The clamp is against the REMAINING wall clock, not only against
        # the constant, so a small overall budget must produce small
        # per-call timeouts rather than 30 second ones.
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "TP53"))
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        traversal.traverse_subgraph(seeds=["NCBIGene:1"], hops=0, time_budget_s=4.0)

        assert fake.timeouts
        assert max(fake.timeouts) <= 4.0

    def test_a_nearly_exhausted_budget_never_asks_for_a_zero_or_negative_timeout(
        self,
    ) -> None:
        budget = traversal._Budget(max_nodes=10, max_edges=10, time_budget_s=0.0)
        assert traversal._per_call_timeout(budget) == 1.0


class TestHopLimitIsReportedAsABound:
    """Finding F-4.4-10: T-4.4-02's criterion names three bounds, two were reported.

    Reported as its own explicit field rather than as a truncation entry;
    see the comment in `traverse_subgraph` for why. Both states are
    asserted here, so the field cannot pass by only ever reading one way.
    """

    def test_a_frontier_left_unexpanded_at_the_hop_limit_is_reported(
        self, monkeypatch
    ) -> None:
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "TP53"))
        fake.register_hop(
            "NCBIGene:1",
            "gene_associated_with_condition",
            "out",
            [
                {
                    "r": _edge_entity(9001, "gene_associated_with_condition", 1, 2),
                    "b": _disease_entity(2, "MedGen:C1"),
                }
            ],
        )
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(
            seeds=["NCBIGene:1"],
            hops=1,
            edge_labels=("gene_associated_with_condition",),
        )

        assert result.hop_limit_reached is True
        assert result.unexpanded_frontier_nodes == 1
        # And it is deliberately NOT a cap: `truncated` means smaller than
        # what was asked for, and one hop is what was asked for.
        assert result.truncated is False

    def test_a_cap_stopping_first_is_not_reported_as_a_hop_bound(
        self, monkeypatch
    ) -> None:
        # The pairing a live run surfaced: 499 vertices left unexpanded
        # with `hop_limit_reached` False. Not a contradiction, and this
        # pins the reading: the count is unconditional, the flag names the
        # hop limit specifically, and the cap that actually stopped the
        # traversal is the one in `truncation`.
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "TP53"))
        rows = [
            {
                "r": _edge_entity(9500 + i, "gene_associated_with_condition", 1, i),
                "b": _disease_entity(i, "MedGen:C" + str(i)),
            }
            for i in range(2, 40)
        ]
        fake.register_hop("NCBIGene:1", "gene_associated_with_condition", "out", rows)
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(
            seeds=["NCBIGene:1"],
            hops=1,
            edge_labels=("gene_associated_with_condition",),
            max_nodes=6,
        )

        assert result.hop_limit_reached is False
        assert result.unexpanded_frontier_nodes > 0
        assert {"cap": "max_nodes", "value": 6} in result.truncation

    def test_a_neighbourhood_that_ends_naturally_reports_no_hop_bound(
        self, monkeypatch
    ) -> None:
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "TP53"))
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        result = traversal.traverse_subgraph(
            seeds=["NCBIGene:1"],
            hops=1,
            edge_labels=("gene_associated_with_condition",),
        )

        assert result.hop_limit_reached is False
        assert result.unexpanded_frontier_nodes == 0


class TestQueryRowLimitIsConstant:
    """The Cypher LIMIT no longer varies with the caller's remaining budget.

    Measured on the live graph 2026-08-19: sizing the LIMIT from a small
    remaining budget made the planner unstable, with one query at LIMIT 5
    exceeding the 30 second per-call budget while the same query at LIMIT
    1, 13, 39, 100 and 500 returned in under 9 seconds. A constant LIMIT
    was also cheaper overall, 34.4 seconds against 50.2 seconds for a full
    pass. This pins the constant so a future change back to a
    budget-derived LIMIT is a failing test rather than a slow surprise.
    """

    def test_every_hop_query_asks_for_the_same_row_ceiling(self, monkeypatch) -> None:
        fake = FakeGraph()
        fake.register_seed("NCBIGene:1", _gene_entity(1, "NCBIGene:1", "TP53"))
        monkeypatch.setattr(traversal, "execute_cypher", fake)

        traversal.traverse_subgraph(seeds=["NCBIGene:1"], hops=1, max_nodes=7, max_edges=9)

        hop_limits = [
            int(match.group("limit"))
            for match in (
                _OUT_QUERY_RE.match(call) or _IN_QUERY_RE.match(call)
                for call in fake.calls
            )
            if match
        ]
        assert hop_limits, "no hop query was issued, so nothing was asserted"
        assert set(hop_limits) == {MAX_ROW_LIMIT}

    def test_the_server_side_result_set_stays_bounded(self) -> None:
        # The property the literal LIMIT exists for: AGE must never be
        # asked to materialize an unbounded result set, whatever the
        # caller's caps say.
        assert traversal._QUERY_ROW_LIMIT == MAX_ROW_LIMIT


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
