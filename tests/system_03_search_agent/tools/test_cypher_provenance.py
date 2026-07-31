"""Tests for Layer 1 provenance and source URL mapping (T-2.1-05).

Depends on:
    - system_03_search_agent.tools.cypher_provenance
      (source_url_for_curie, to_output_row)
    - system_03_search_agent.tools.graph_schema_constants
      (CURIE_PREFIXES, used only to assert every documented prefix in the
      graph is covered by a test, never to duplicate the mapping logic
      under test)
"""

from __future__ import annotations

import re

import pytest

from system_03_search_agent.tools.cypher_provenance import (
    source_url_for_curie,
    to_output_row,
    to_output_rows,
)
from system_03_search_agent.tools.graph_schema_constants import (
    CURIE_PREFIXES,
    NCBI_RECORD_URL_PATTERN,
)

# ---------------------------------------------------------------------------
# The six prefixes with a documented NCBI record page.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("curie", "expected_url"),
    [
        ("NCBIGene:672", "https://www.ncbi.nlm.nih.gov/gene/672"),
        ("ClinVar:17660", "https://www.ncbi.nlm.nih.gov/clinvar/variation/17660/"),
        ("MedGen:C0031485", "https://www.ncbi.nlm.nih.gov/medgen/C0031485"),
        ("PMID:34567890", "https://pubmed.ncbi.nlm.nih.gov/34567890/"),
        (
            "NCBITaxon:9606",
            "https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=9606",
        ),
        ("MeSH:D012345", "https://www.ncbi.nlm.nih.gov/mesh/?term=D012345"),
    ],
)
def test_documented_prefix_maps_to_expected_ncbi_record_url(
    curie: str, expected_url: str
) -> None:
    assert source_url_for_curie(curie) == expected_url


def test_mesh_url_matches_the_host_pinned_ncbi_record_pattern() -> None:
    url = source_url_for_curie("MeSH:D012345")
    assert url is not None
    assert re.match(NCBI_RECORD_URL_PATTERN, url)


def test_mesh_local_id_needing_encoding_is_encoded_correctly() -> None:
    # A local id with a character that needs encoding must still resolve to
    # a well-formed query-string value, matching the same encoding path
    # every other prefix's local id goes through.
    url = source_url_for_curie("MeSH:D012345 supplement")
    assert url == "https://www.ncbi.nlm.nih.gov/mesh/?term=D012345%20supplement"


# ---------------------------------------------------------------------------
# The three prefixes with no NCBI-hosted record page: GO, HP, MONDO.
# Returning None here is the correct, documented behavior, not a gap: none
# of the three is an NCBI database, so no host-pinned URL can be built
# without fabricating one.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("curie", ["GO:0006096", "HP:0001250", "MONDO:0009861"])
def test_non_ncbi_ontology_prefix_returns_none(curie: str) -> None:
    assert source_url_for_curie(curie) is None


def test_every_curie_prefix_in_the_graph_schema_is_covered_by_a_test() -> None:
    # Guards against a tenth prefix being added to CURIE_PREFIXES with no
    # corresponding test above, either in the documented-mapping test or
    # the non-NCBI-ontology test.
    documented = {"NCBIGene", "ClinVar", "MedGen", "PMID", "NCBITaxon", "MeSH"}
    non_ncbi = {"GO", "HP", "MONDO"}

    assert documented | non_ncbi == set(CURIE_PREFIXES)
    assert len(CURIE_PREFIXES) == 9


# ---------------------------------------------------------------------------
# An unrecognized prefix, outside the graph's nine entirely.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "curie",
    ["UNKNOWNPREFIX:123", "OMIM:600123", "", "NoColonAtAll", ":123", "NCBIGene:"],
)
def test_unrecognized_or_malformed_curie_returns_none(curie: str) -> None:
    assert source_url_for_curie(curie) is None


def test_url_encodes_the_local_id() -> None:
    # A local id with a character that needs encoding must not break the
    # constructed URL's path structure.
    url = source_url_for_curie("NCBIGene:67 2")
    assert url == "https://www.ncbi.nlm.nih.gov/gene/67%202"


def test_local_id_cannot_escape_the_pinned_host_via_path_traversal() -> None:
    url = source_url_for_curie("NCBIGene:../../evil.example")
    assert url is not None
    assert url.startswith("https://www.ncbi.nlm.nih.gov/gene/")
    assert "evil.example" not in url or "%2F" in url


# ---------------------------------------------------------------------------
# to_output_row: stored-URL passthrough and foreign-host discard.
# ---------------------------------------------------------------------------


def test_to_output_row_keeps_a_valid_stored_source_url() -> None:
    raw_row = {
        "label": "Gene",
        "id": "NCBIGene:672",
        "properties": {"symbol": "BRCA1"},
        "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
    }

    row = to_output_row(raw_row, snapshot_version="2026-07-01")

    assert row["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/672"
    assert row["node_or_edge_type"] == "Gene"
    assert row["curie"] == "NCBIGene:672"
    assert row["fields"] == {"symbol": "BRCA1"}
    assert row["graph_snapshot_version"] == "2026-07-01"


def test_to_output_row_discards_a_stored_source_url_on_a_foreign_host() -> None:
    raw_row = {
        "label": "Gene",
        "id": "NCBIGene:672",
        "properties": {"symbol": "BRCA1"},
        "source_url": "https://evil.example/gene/672",
    }

    row = to_output_row(raw_row, snapshot_version="2026-07-01")

    # The foreign-host URL is discarded, never passed through, and the
    # module falls back to deriving a fresh URL from the CURIE.
    assert row["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/672"


def test_to_output_row_falls_back_to_none_when_no_valid_url_can_be_derived() -> None:
    raw_row = {
        "label": "OntologyClass",
        "id": "GO:0006096",
        "properties": {"name": "glycolytic process"},
        "source_url": "https://evil.example/go/0006096",
    }

    row = to_output_row(raw_row, snapshot_version="2026-07-01")

    # No documented NCBI mapping for GO, and the stored URL is a foreign
    # host, so the row correctly carries no fabricated source_url.
    assert row["source_url"] is None
    assert row["curie"] == "GO:0006096"


def test_to_output_row_derives_url_when_no_stored_url_present() -> None:
    raw_row = {
        "label": "SequenceVariant",
        "id": "ClinVar:17660",
        "properties": {},
    }

    row = to_output_row(raw_row, snapshot_version="2026-07-01")

    assert row["source_url"] == "https://www.ncbi.nlm.nih.gov/clinvar/variation/17660/"


def test_to_output_row_accepts_node_or_edge_type_and_curie_keys_directly() -> None:
    raw_row = {
        "node_or_edge_type": "Gene",
        "curie": "NCBIGene:672",
        "fields": {"symbol": "BRCA1"},
    }

    row = to_output_row(raw_row, snapshot_version="2026-07-01")

    assert row["node_or_edge_type"] == "Gene"
    assert row["curie"] == "NCBIGene:672"
    assert row["fields"] == {"symbol": "BRCA1"}


def test_to_output_row_always_returns_exactly_the_five_expected_keys() -> None:
    raw_row = {"label": "Gene", "id": "NCBIGene:672", "properties": {}}

    row = to_output_row(raw_row, snapshot_version="2026-07-01")

    assert set(row.keys()) == {
        "node_or_edge_type",
        "curie",
        "fields",
        "source_url",
        "graph_snapshot_version",
    }


# ---------------------------------------------------------------------------
# to_output_rows: the real integration path, agtype wire text in, zero or
# more shaped rows out (finding F-2.1-A1's fix).
# ---------------------------------------------------------------------------


def test_to_output_rows_parses_a_single_vertex_column() -> None:
    raw_row = {
        "result": (
            '{"id": 1125899906858506, "label": "Gene", "properties": '
            '{"id": "NCBIGene:672", "symbol": "BRCA1"}}::vertex'
        )
    }

    rows = to_output_rows(raw_row, snapshot_version="2026-07-01")

    assert len(rows) == 1
    row = rows[0]
    assert row["node_or_edge_type"] == "Gene"
    assert row["curie"] == "NCBIGene:672"
    assert row["fields"]["symbol"] == "BRCA1"
    assert row["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/672"
    assert row["graph_snapshot_version"] == "2026-07-01"


def test_to_output_rows_splits_a_multi_column_row_into_multiple_output_rows() -> None:
    raw_row = {
        "c0": (
            '{"id": 1, "label": "SequenceVariant", "properties": '
            '{"id": "ClinVar:17660", "name": "variant"}}::vertex'
        ),
        "c1": (
            '{"id": 2, "label": "Gene", "properties": '
            '{"id": "NCBIGene:672", "symbol": "BRCA1"}}::vertex'
        ),
    }

    rows = to_output_rows(raw_row, snapshot_version="2026-07-01")

    assert len(rows) == 2
    types_seen = {row["node_or_edge_type"] for row in rows}
    assert types_seen == {"SequenceVariant", "Gene"}
    curies_seen = {row["curie"] for row in rows}
    assert curies_seen == {"ClinVar:17660", "NCBIGene:672"}


def test_to_output_rows_maps_an_edge_including_start_and_end_id() -> None:
    raw_row = {
        "result": (
            '{"id": 5, "label": "is_sequence_variant_of", "start_id": 1, '
            '"end_id": 2, "properties": {"id": "ClinVar:17660"}}::edge'
        )
    }

    rows = to_output_rows(raw_row, snapshot_version="2026-07-01")

    assert len(rows) == 1
    row = rows[0]
    assert row["node_or_edge_type"] == "is_sequence_variant_of"
    assert row["fields"]["_edge_start_id"] == 1
    assert row["fields"]["_edge_end_id"] == 2


def test_to_output_rows_shapes_a_bare_scalar_as_a_derived_row() -> None:
    """A scalar is an answer, not an absence.

    This test previously asserted `rows == []` and was WRONG, in the sense
    that mattered: finding F-2.1-B05 showed that dropping scalars made the
    tool report `status="empty"` for `RETURN count(sv)` while
    `total_available` sat non-zero. It knew the graph had answered and said
    nothing was found, and it did that for five of the six query shapes the
    real plan model actually produces, including every "how many" question.

    The test encoded the defect as intended behaviour, which is why nothing
    caught it. It is changed here deliberately, not to make a failure go
    away: the assertion below is the opposite claim, and it fails against
    the old code.
    """
    raw_row = {"result": "42"}

    rows = to_output_rows(raw_row, snapshot_version="2026-07-01", derived_source_curie="NCBIGene:672")

    assert len(rows) == 1
    row = rows[0]
    assert row["node_or_edge_type"] == "derived", (
        "a computed value must be distinguishable from a retrieved record"
    )
    assert row["fields"] == {"result": 42}
    assert row["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/672", (
        "a derived value is cited to the entity it was computed from"
    )


def test_a_derived_row_with_no_source_entity_carries_no_citation() -> None:
    """The guarantee the old assertion was really protecting.

    Shaping a scalar into a row must not become a way to emit an uncitable
    number. Without an entity to attribute it to, the row carries no
    `source_url`, and `cypher_query._run_pipeline`'s cite-or-refuse gate
    drops it exactly as it drops any other uncitable row.
    """
    rows = to_output_rows({"result": "42"}, snapshot_version="2026-07-01")

    assert len(rows) == 1
    assert rows[0]["source_url"] is None, (
        "an uncitable computed number must not acquire a citation it has no "
        "basis for; the caller drops it on this being None"
    )


def test_to_output_rows_omits_an_unparseable_column() -> None:
    raw_row = {"result": "not valid agtype at all {{{"}

    rows = to_output_rows(raw_row, snapshot_version="2026-07-01")

    assert rows == []


# ---------------------------------------------------------------------------
# F-2.1-B06: an edge with no CURIE of its own must never keep a citation
# that points at a different record than the row itself. Reproduces the
# adversary's live finding: a real AGE edge carries source, agent_type,
# source_url, and knowledge_level, but never an "id" property.
# ---------------------------------------------------------------------------


def test_edge_only_row_with_no_curie_and_no_endpoint_carries_no_citation() -> None:
    """The exact adversary reproduction: `RETURN e` alone.

    Live probe of `is_sequence_variant_of` confirmed the edge carries a
    real, host-valid `source_url` (the ClinVar variation page for its
    start endpoint) but no `properties["id"]`. Before the fix, this row
    shipped `curie=""` (source_id="unknown" downstream) next to that
    ClinVar URL, a citation that resolves to a genuine record the row
    itself never names. With no sibling vertex present in the row to
    verify an attribution against, the only honest outcome is no
    citation at all.
    """
    raw_row = {
        "result": (
            '{"id": 4222124650659841, "label": "is_sequence_variant_of", '
            '"start_id": 1125899906842625, "end_id": 844424943788979, '
            '"properties": {"source": "ClinVar", "agent_type": "manual_agent", '
            '"source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/2", '
            '"knowledge_level": "knowledge_assertion"}}::edge'
        )
    }

    rows = to_output_rows(raw_row, snapshot_version="2026-07-01")

    assert len(rows) == 1
    row = rows[0]
    assert row["curie"] == "", "an edge with no id property has no CURIE of its own"
    assert row["source_url"] is None, (
        "a citation must never point at a record the row itself does not name; "
        "an unattributable edge carries no citation, not a borrowed one"
    )


def test_edge_with_no_curie_is_attributed_to_a_sibling_endpoint_vertex() -> None:
    """When the query also returns an endpoint vertex, attribution is honest.

    `RETURN v, e` (the SequenceVariant and the edge, as separate columns
    of the same row) gives this module a genuine, verified CURIE for the
    edge's start endpoint, taken from data already in the row, never
    fetched or guessed. The row's own `curie` and `source_url` are then
    set from that endpoint, so the two agree, and the row is marked as
    endpoint-attributed rather than presented as the edge's own identity.
    """
    raw_row = {
        "c0": (
            '{"id": 1125899906842625, "label": "SequenceVariant", "properties": '
            '{"id": "ClinVar:2", "name": "NM_000059.4(BRCA2):c.1_10del"}}::vertex'
        ),
        "c1": (
            '{"id": 4222124650659841, "label": "is_sequence_variant_of", '
            '"start_id": 1125899906842625, "end_id": 844424943788979, '
            '"properties": {"source": "ClinVar", "agent_type": "manual_agent", '
            '"source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/2", '
            '"knowledge_level": "knowledge_assertion"}}::edge'
        ),
    }

    rows = to_output_rows(raw_row, snapshot_version="2026-07-01")

    assert len(rows) == 2
    edge_row = next(row for row in rows if row["node_or_edge_type"] == "is_sequence_variant_of")
    assert edge_row["curie"] == "ClinVar:2"
    assert edge_row["source_url"] == "https://www.ncbi.nlm.nih.gov/clinvar/variation/2/"
    assert edge_row["fields"]["_cited_via_endpoint_curie"] == "ClinVar:2"


def test_edge_with_no_curie_and_a_foreign_endpoint_id_still_carries_no_citation() -> None:
    """A sibling vertex present in the row does not help if it is not this
    edge's own endpoint: the vertex's internal id must actually match the
    edge's start_id or end_id, never merely be present somewhere in the row.
    """
    raw_row = {
        "c0": (
            '{"id": 999, "label": "Gene", "properties": '
            '{"id": "NCBIGene:672", "symbol": "BRCA1"}}::vertex'
        ),
        "c1": (
            '{"id": 4222124650659841, "label": "is_sequence_variant_of", '
            '"start_id": 1125899906842625, "end_id": 844424943788979, '
            '"properties": {"source": "ClinVar", '
            '"source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/2"}}::edge'
        ),
    }

    rows = to_output_rows(raw_row, snapshot_version="2026-07-01")

    edge_row = next(row for row in rows if row["node_or_edge_type"] == "is_sequence_variant_of")
    assert edge_row["curie"] == ""
    assert edge_row["source_url"] is None


def test_edge_with_a_genuine_curie_of_its_own_is_unaffected_by_the_fix() -> None:
    """Defensive: if an edge ever does carry its own properties["id"], the
    fix's new branch never runs, and the pre-existing behaviour (keep a
    valid stored source_url, else derive from the CURIE) is unchanged.
    """
    raw_row = {
        "result": (
            '{"id": 5, "label": "is_sequence_variant_of", "start_id": 1, '
            '"end_id": 2, "properties": {"id": "ClinVar:17660"}}::edge'
        )
    }

    rows = to_output_rows(raw_row, snapshot_version="2026-07-01")

    assert len(rows) == 1
    row = rows[0]
    assert row["curie"] == "ClinVar:17660"
    assert row["source_url"] == "https://www.ncbi.nlm.nih.gov/clinvar/variation/17660/"
    assert "_cited_via_endpoint_curie" not in row["fields"]


def test_to_output_rows_flattens_a_path_into_its_vertex_and_edge_elements() -> None:
    raw_row = {
        "result": (
            "["
            '{"id": 1, "label": "Gene", "properties": {"id": "NCBIGene:672"}}, '
            '{"id": 5, "label": "is_sequence_variant_of", "start_id": 1, '
            '"end_id": 2, "properties": {"id": "ClinVar:17660"}}, '
            '{"id": 2, "label": "SequenceVariant", "properties": '
            '{"id": "ClinVar:17660"}}'
            "]::path"
        )
    }

    rows = to_output_rows(raw_row, snapshot_version="2026-07-01")

    assert len(rows) == 3
    types_seen = {row["node_or_edge_type"] for row in rows}
    assert types_seen == {"Gene", "is_sequence_variant_of", "SequenceVariant"}
