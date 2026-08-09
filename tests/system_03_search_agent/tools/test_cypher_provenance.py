"""Tests for Layer 1 provenance and source URL mapping (T-2.1-05).

Depends on:
    - system_03_search_agent.tools.cypher_provenance
      (source_url_for_curie, to_output_row, _CURIE_LOCAL_ID_SHAPES, used
      only to assert directly against the compiled shapes for finding
      F-2.1-A5-07, never to duplicate the mapping logic under test)
    - system_03_search_agent.tools.graph_schema_constants
      (CURIE_PREFIXES, used only to assert every documented prefix in the
      graph is covered by a test, never to duplicate the mapping logic
      under test)
"""

from __future__ import annotations

import re

import pytest

from system_03_search_agent.tools.cypher_provenance import (
    _CURIE_LOCAL_ID_SHAPES,
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


def test_mesh_local_id_with_extra_text_returns_none() -> None:
    # F-2.1-C09: a MeSH local id is a letter followed by digits. Anything
    # else, including a trailing "supplement" annotation, is not a real
    # MeSH descriptor id and must not be built into a citation URL, even
    # though it would previously have quoted cleanly into one.
    assert source_url_for_curie("MeSH:D012345 supplement") is None


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


def test_ncbigene_local_id_with_a_space_returns_none() -> None:
    # F-2.1-C09: an NCBIGene local id is digits only. A space-containing
    # string is not a real gene id, so no URL is built from it, even
    # though it would previously have quoted cleanly into one.
    assert source_url_for_curie("NCBIGene:67 2") is None


def test_local_id_cannot_escape_the_pinned_host_via_path_traversal() -> None:
    # F-2.1-C09: a path-traversal-shaped local id fails the digit-only
    # shape check for NCBIGene outright, so no URL is built at all, not
    # merely one whose traversal characters happen to be percent-encoded.
    assert source_url_for_curie("NCBIGene:../../evil.example") is None


# ---------------------------------------------------------------------------
# F-2.1-C09: a CURIE prefix having a documented URL builder never meant the
# text after the colon was checked against the real shape for that prefix.
# Every string below passes the prefix lookup and would previously have
# quoted cleanly into a syntactically valid, host-pinned URL; the adversary
# verified live that every one of these exact URLs 404s. The host is
# genuine, only the path is attacker-controlled, so the shape check must
# reject the local id itself.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "curie",
    [
        "NCBIGene:672.",
        "NCBIGene:672-related",
        "NCBIGene:not_a_number",
        "NCBIGene:672 OR 1=1",
        "MedGen:../../etc/passwd",
        "NCBIGene:672-VALIDATED-BY-FDA",
    ],
)
def test_local_id_with_wrong_shape_for_its_prefix_returns_none(curie: str) -> None:
    assert source_url_for_curie(curie) is None


# ---------------------------------------------------------------------------
# F-2.1-J4-05: the C09 fix's shape table was itself too narrow. It rejected
# `MedGen:CN517202`, a genuine two-letter MedGen concept id (assigned when a
# concept has no UMLS CUI), stripping a real citation from a real record.
# Verified against the live graph on 2026-07-31: an exhaustive aggregate over
# every row of the Disease table (200,845 rows) found exactly two MedGen
# shapes, `C` plus digits (196,444 rows) and `CN` plus digits (4,401 rows),
# and an exhaustive aggregate over every row of the OntologyClass table
# (30,790 rows) found exactly two MeSH shapes, `D` plus 6 digits (27,177
# rows, the legacy length) and `D` plus 9 digits (3,613 rows, the length NLM
# introduced once 6 digits ran out for newer descriptors). These are real
# ids sampled directly off the graph, not fabricated for this test.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("curie", "expected_url"),
    [
        ("MedGen:CN517202", "https://www.ncbi.nlm.nih.gov/medgen/CN517202"),
        ("MedGen:CN043618", "https://www.ncbi.nlm.nih.gov/medgen/CN043618"),
        ("MeSH:D000066388", "https://www.ncbi.nlm.nih.gov/mesh/?term=D000066388"),
    ],
)
def test_real_ids_the_c09_fix_had_wrongly_stripped_now_keep_their_citation(
    curie: str, expected_url: str
) -> None:
    assert source_url_for_curie(curie) == expected_url


def test_medgen_local_id_is_case_sensitive_to_the_verified_shape() -> None:
    # F-2.1-J4-05: the exhaustive Disease scan found only uppercase `C` and
    # `CN` prefixes, never a lowercase variant, so a lowercase local id is
    # not a real MedGen id and must not resolve to a citation.
    assert source_url_for_curie("MedGen:cn517202") is None


def test_medgen_local_id_with_an_unverified_second_letter_returns_none() -> None:
    # The exhaustive Disease scan found exactly two shapes, `C` and `CN`.
    # A different second letter is not one of them and must not be treated
    # as a plausible third shape.
    assert source_url_for_curie("MedGen:CX517202") is None


def test_mesh_local_id_with_an_unverified_letter_returns_none() -> None:
    # The exhaustive OntologyClass scan found only the `D` prefix. A
    # different letter is not a shape this module has verified.
    assert source_url_for_curie("MeSH:M000123") is None


def test_no_documented_prefix_url_ever_contains_a_percent_encoded_local_id() -> None:
    """F-2.1-J4-05 aftermath: every shape in `_CURIE_LOCAL_ID_SHAPES` is
    restricted to uppercase ASCII letters and digits, so `urllib.parse.quote`
    never has a character to escape for any local id that passes the shape
    check today. The two tests that used to exercise `quote` on a local id
    that genuinely needed encoding, `test_url_encodes_the_local_id` and
    `test_mesh_local_id_needing_encoding_is_encoded_correctly`, were
    inverted to assert None during the F-2.1-C09 fix, because the exact
    strings they encoded (`NCBIGene:67 2`, `MeSH:D012345 supplement`) are
    also the ones that fix correctly rejects, and F-2.1-J4-05's widened
    MedGen and MeSH shapes still admit no character that needs escaping.
    This test does not exercise the encoding branch, since no currently
    valid shape reaches it; it exists as a guard so a future change that
    loosens a shape to admit a special character is forced to notice this
    assertion fail and add real encoding coverage back, rather than leaving
    the branch silently untested indefinitely.
    """
    for curie in [
        "NCBIGene:672",
        "ClinVar:17660",
        "MedGen:CN517202",
        "MedGen:C0346153",
        "PMID:34567890",
        "NCBITaxon:9606",
        "MeSH:D000066388",
    ]:
        url = source_url_for_curie(curie)
        assert url is not None
        assert "%" not in url, (
            f"{curie} produced a percent-encoded URL: a valid shape now "
            "needs real encoding coverage, not just this guard"
        )


# ---------------------------------------------------------------------------
# F-2.1-A5-07: Python's `\d` matches every Unicode decimal digit, not only
# ASCII 0-9, so a shape compiled without `re.ASCII` accepted Arabic-Indic,
# Devanagari, and fullwidth digits as if they were real numeric local ids.
# Each one quoted cleanly into a syntactically valid, host-pinned URL for a
# record that cannot exist, reopening F-2.1-C09's citation-spoofing class
# through a character class instead of a shape.
#
# The guard test just above this one, added for F-2.1-J4-05, could not
# catch this: it only checks that seven hand-picked, already-ASCII CURIEs
# do not need percent-encoding. It never feeds the shapes a non-ASCII
# digit, so a shape that lost `re.ASCII` would keep passing it. A guard
# that asserts a property over a hand-listed sample rather than over the
# shapes themselves does not guard the property. The test below asserts
# directly against `_CURIE_LOCAL_ID_SHAPES`, the compiled patterns under
# test, so a future edit that drops `re.ASCII` from any of them fails this
# test directly instead of merely going unnoticed.
# ---------------------------------------------------------------------------

# Each is a real Unicode decimal digit, `str.isdigit()` and `\d` both agree,
# but none is one of the ASCII characters '0' through '9'.
_NON_ASCII_DIGIT_SAMPLES = [
    "٦٧٢",  # Arabic-Indic digits for 672
    "६७२",  # Devanagari digits for 672
    "６７２",  # fullwidth digits for 672
]

# The literal, prefix-specific text each shape in `_CURIE_LOCAL_ID_SHAPES`
# requires before its digit run, so a candidate actually reaches the `\d+`
# portion of its own shape rather than failing to match for an unrelated
# reason (a missing letter prefix). Kept here, next to the shapes dict
# import, rather than re-deriving it from the compiled patterns, since the
# point of this test is to exercise each shape's digit class specifically.
_LOCAL_ID_PREFIX_LITERAL: dict[str, str] = {
    "NCBIGene": "",
    "ClinVar": "",
    "PMID": "",
    "NCBITaxon": "",
    "MedGen": "CN",
    "MeSH": "D",
}


def test_curie_local_id_shapes_reject_non_ascii_digits() -> None:
    assert set(_LOCAL_ID_PREFIX_LITERAL) == set(_CURIE_LOCAL_ID_SHAPES)
    for prefix, shape in _CURIE_LOCAL_ID_SHAPES.items():
        literal = _LOCAL_ID_PREFIX_LITERAL[prefix]
        for digits in _NON_ASCII_DIGIT_SAMPLES:
            candidate = literal + digits
            assert not shape.fullmatch(candidate), (
                f"{prefix} shape {shape.pattern!r} fullmatched the "
                f"non-ASCII-digit local id {candidate!r}; \\d without "
                "re.ASCII matches Unicode digits, not only 0-9"
            )


@pytest.mark.parametrize(
    "curie",
    [
        "NCBIGene:٦٧٢",  # Arabic-Indic 672
        "NCBIGene:6７2",  # fullwidth 7 mixed into an otherwise-ASCII id
        "PMID:１２３",  # fullwidth 123
        "MedGen:CN٤٥٦",  # Arabic-Indic digits after CN
        "MeSH:D００００００",  # fullwidth zeros after D
    ],
)
def test_non_ascii_digit_curie_returns_none(curie: str) -> None:
    # F-2.1-A5-07: the adversary's own reproduction. Before the re.ASCII
    # fix, every one of these fullmatched its prefix's shape and built a
    # syntactically valid, host-pinned URL that 404s live, since none of
    # these local ids names a real record.
    assert source_url_for_curie(curie) is None


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


# ---------------------------------------------------------------------------
# F-2.1-C02: a derived/projected value that is itself a resolvable CURIE
# must be cited to its own record, not to the entity the query was computed
# from. Only a genuine non-identifier scalar falls back to that entity.
# ---------------------------------------------------------------------------


def test_derived_row_cites_a_projected_identifier_rather_than_the_source_entity() -> None:
    """`RETURN d.id AS disease_id` projects a real MedGen CURIE. That CURIE
    is itself a resolvable, citable identifier, so the derived row must
    cite the disease's own record, not BRCA1's gene page just because the
    query started from BRCA1.
    """
    rows = to_output_rows(
        # A string scalar's raw agtype wire text is JSON-quoted, the same
        # way `graph_connection.execute_cypher` reads it off the socket.
        {"result": '"MedGen:C0346153"'},
        snapshot_version="2026-07-01",
        derived_source_curie="NCBIGene:672",
        column_labels={"result": "disease_id"},
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["curie"] == "MedGen:C0346153", (
        "a projected identifier is cited to its own record, not the "
        "computed-from entity"
    )
    assert row["source_url"] == "https://www.ncbi.nlm.nih.gov/medgen/C0346153"
    assert row["fields"] == {"disease_id": "MedGen:C0346153"}


def test_derived_row_falls_back_to_source_entity_when_nothing_projected_is_an_identifier() -> None:
    """A count or a name string is not itself a citable record, so the
    original F-2.1-B05 behaviour (cite the computed-from entity) still
    applies when nothing projected is a resolvable CURIE.
    """
    rows = to_output_rows(
        {"result": "4"},
        snapshot_version="2026-07-01",
        derived_source_curie="NCBIGene:672",
        column_labels={"result": "disease_count"},
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["curie"] == "NCBIGene:672"
    assert row["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/672"
    assert row["fields"] == {"disease_count": 4}


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


def test_edge_alone_with_a_valid_own_source_url_is_cited_to_its_own_record() -> None:
    """F-2.1-C04/C05: `RETURN e` alone, no sibling vertex in the row at all.

    Before the C04/C05 fix this returned no citation (F-2.1-B06's original
    outcome: no endpoint vertex in the row to verify an attribution
    against). The edge's own stored `source_url` is data already in hand
    on the edge itself, live-verified in F-2.1-B06's own probe
    (`is_sequence_variant_of`, `gene_associated_with_condition`,
    `has_mesh_annotation`, `in_taxon`, `orthologous_to` all carry one), and
    F-2.1-C05 found it is also the MORE PRECISE citation: for
    `is_sequence_variant_of` it is the ClinVar variation page, exactly the
    record that asserts the relationship. Reverse-deriving the CURIE from
    that URL needs no sibling vertex at all, so it is honest even with
    nothing else in the row.
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
    assert row["curie"] == "ClinVar:2", (
        "the edge's own stored source_url reverse-derives a verified CURIE, "
        "with no sibling vertex needed"
    )
    assert row["source_url"] == "https://www.ncbi.nlm.nih.gov/clinvar/variation/2/"
    assert row["fields"]["_cited_via_endpoint_curie"] == "ClinVar:2"


def test_edge_alone_with_no_valid_own_source_url_still_carries_no_citation() -> None:
    """The honest "cannot attribute" case survives the C04/C05 fix: an edge
    with neither a verifiable own `source_url` (here, a foreign host) nor
    any sibling vertex in the row gets no citation. Nothing is invented to
    fill the gap.
    """
    raw_row = {
        "result": (
            '{"id": 4222124650659841, "label": "is_sequence_variant_of", '
            '"start_id": 1125899906842625, "end_id": 844424943788979, '
            '"properties": {"source": "ClinVar", '
            '"source_url": "https://evil.example/clinvar/variation/2"}}::edge'
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

    `RETURN e, v` (the edge and the SequenceVariant, as separate columns
    of the same row) gives this module a genuine, verified CURIE for the
    edge's start endpoint, taken from data already in the row, never
    fetched or guessed.

    F-2.1-C06: the edge's own stored `source_url` and the sibling vertex's
    own citation now resolve to the identical record (both `ClinVar:2`),
    so `to_output_rows`'s dedup collapses the pair to one row rather than
    emitting the same citation twice. The edge column comes first here,
    so it is the edge row, carrying the endpoint-attribution marker, that
    survives.
    """
    raw_row = {
        "c0": (
            '{"id": 4222124650659841, "label": "is_sequence_variant_of", '
            '"start_id": 1125899906842625, "end_id": 844424943788979, '
            '"properties": {"source": "ClinVar", "agent_type": "manual_agent", '
            '"source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/2", '
            '"knowledge_level": "knowledge_assertion"}}::edge'
        ),
        "c1": (
            '{"id": 1125899906842625, "label": "SequenceVariant", "properties": '
            '{"id": "ClinVar:2", "name": "NM_000059.4(BRCA2):c.1_10del"}}::vertex'
        ),
    }

    rows = to_output_rows(raw_row, snapshot_version="2026-07-01")

    assert len(rows) == 1
    edge_row = rows[0]
    assert edge_row["node_or_edge_type"] == "is_sequence_variant_of"
    assert edge_row["curie"] == "ClinVar:2"
    assert edge_row["source_url"] == "https://www.ncbi.nlm.nih.gov/clinvar/variation/2/"
    assert edge_row["fields"]["_cited_via_endpoint_curie"] == "ClinVar:2"


def test_edge_with_a_foreign_endpoint_id_and_no_valid_own_url_still_carries_no_citation() -> None:
    """Priority 2's safety net (F-2.1-B06's original mechanism): a sibling
    vertex present in the row does not help if it is not this edge's own
    endpoint, its internal id must actually match the edge's start_id or
    end_id, never merely be present somewhere in the row. This only comes
    into play once priority 1 (the edge's own stored source_url,
    F-2.1-C04/C05) has nothing valid to offer, here because the URL is on
    a foreign host.
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
            '"source_url": "https://evil.example/clinvar/variation/2"}}::edge'
        ),
    }

    rows = to_output_rows(raw_row, snapshot_version="2026-07-01")

    edge_row = next(row for row in rows if row["node_or_edge_type"] == "is_sequence_variant_of")
    assert edge_row["curie"] == ""
    assert edge_row["source_url"] is None


def test_edge_citation_is_deterministic_regardless_of_which_endpoint_column_is_returned() -> None:
    """F-2.1-C04: the identical edge must resolve to the identical citation
    whether the query also returns its start endpoint, its end endpoint,
    or neither, since the edge's own stored source_url, not the sibling
    vertex, drives the citation.
    """
    edge_json = (
        '{"id": 555, "label": "gene_associated_with_condition", '
        '"start_id": 10, "end_id": 20, "properties": {"source": "NCBI MIM2Gene", '
        '"source_url": "https://www.ncbi.nlm.nih.gov/gene/672"}}::edge'
    )
    gene_json = (
        '{"id": 10, "label": "Gene", "properties": '
        '{"id": "NCBIGene:672", "symbol": "BRCA1"}}::vertex'
    )
    disease_json = (
        '{"id": 20, "label": "Disease", "properties": '
        '{"id": "MedGen:C0346153", "name": "Breast cancer"}}::vertex'
    )

    def edge_row_of(rows: list[dict]) -> dict:
        return next(
            row for row in rows if row["node_or_edge_type"] == "gene_associated_with_condition"
        )

    alone = edge_row_of(to_output_rows({"result": edge_json}, snapshot_version="2026-07-01"))
    with_gene = edge_row_of(
        to_output_rows({"c0": edge_json, "c1": gene_json}, snapshot_version="2026-07-01")
    )
    with_disease = edge_row_of(
        to_output_rows({"c0": edge_json, "c1": disease_json}, snapshot_version="2026-07-01")
    )

    assert alone["curie"] == with_gene["curie"] == with_disease["curie"] == "NCBIGene:672"
    assert (
        alone["source_url"]
        == with_gene["source_url"]
        == with_disease["source_url"]
        == "https://www.ncbi.nlm.nih.gov/gene/672"
    )


# ---------------------------------------------------------------------------
# F-2.1-C06: two output rows citing the identical record collapse to one.
# ---------------------------------------------------------------------------


def test_to_output_rows_deduplicates_rows_citing_the_identical_record() -> None:
    """Two columns of the same raw row resolving to the same citable record
    must produce one output row, not two, so the caller's fixed citation
    budget is not halved by a duplicate.
    """
    gene_json = (
        '{"id": 1, "label": "Gene", "properties": '
        '{"id": "NCBIGene:672", "symbol": "BRCA1"}}::vertex'
    )
    raw_row = {"c0": gene_json, "c1": gene_json}

    rows = to_output_rows(raw_row, snapshot_version="2026-07-01")

    assert len(rows) == 1
    assert rows[0]["curie"] == "NCBIGene:672"


def test_to_output_rows_keeps_distinct_records_when_no_identity_collides() -> None:
    """The dedup must never merge two output rows that cite genuinely
    different records.
    """
    gene_json = (
        '{"id": 1, "label": "Gene", "properties": '
        '{"id": "NCBIGene:672", "symbol": "BRCA1"}}::vertex'
    )
    disease_json = (
        '{"id": 2, "label": "Disease", "properties": '
        '{"id": "MedGen:C0346153", "name": "Breast cancer"}}::vertex'
    )
    raw_row = {"c0": gene_json, "c1": disease_json}

    rows = to_output_rows(raw_row, snapshot_version="2026-07-01")

    assert len(rows) == 2
    assert {row["curie"] for row in rows} == {"NCBIGene:672", "MedGen:C0346153"}


def test_dedup_never_drops_a_derived_row_sharing_its_entitys_own_url() -> None:
    """F-2.1-C03 x C06 interaction: `RETURN g, count(v)` cites the derived
    count to the same entity (and therefore the same `source_url`) as the
    Gene row in the same raw row. The two rows are NOT a duplicate
    citation of the same fact: the derived row is new information (the
    count) the entity row does not itself carry, so the dedup added for
    F-2.1-C06 must never drop it just because it shares a URL with the
    entity it was computed from. Dropping it here would silently remove
    the very number the user asked for, F-2.1-C03's original symptom.
    """
    gene_json = (
        '{"id": 1, "label": "Gene", "properties": '
        '{"id": "NCBIGene:672", "symbol": "BRCA1"}}::vertex'
    )
    raw_row = {"c0": gene_json, "c1": "15310"}

    rows = to_output_rows(
        raw_row,
        snapshot_version="2026-07-01",
        derived_source_curie="NCBIGene:672",
        column_labels={"c1": "variant_count"},
    )

    kinds = {row["node_or_edge_type"] for row in rows}
    assert kinds == {"Gene", "derived"}, (
        f"the derived count must survive alongside the entity row; got {kinds}"
    )
    derived_row = next(row for row in rows if row["node_or_edge_type"] == "derived")
    assert derived_row["fields"] == {"variant_count": 15310}
    assert derived_row["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/672"


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
    # The edge carries its own distinct CURIE (`ClinVar:999999`), not the
    # same one as either endpoint vertex, so all three path elements cite
    # three genuinely different records and F-2.1-C06's dedup has nothing
    # to collapse; the path-flattening mechanic this test targets is
    # otherwise indistinguishable from a duplicate-citation collision.
    raw_row = {
        "result": (
            "["
            '{"id": 1, "label": "Gene", "properties": {"id": "NCBIGene:672"}}, '
            '{"id": 5, "label": "is_sequence_variant_of", "start_id": 1, '
            '"end_id": 2, "properties": {"id": "ClinVar:999999"}}, '
            '{"id": 2, "label": "SequenceVariant", "properties": '
            '{"id": "ClinVar:17660"}}'
            "]::path"
        )
    }

    rows = to_output_rows(raw_row, snapshot_version="2026-07-01")

    assert len(rows) == 3
    types_seen = {row["node_or_edge_type"] for row in rows}
    assert types_seen == {"Gene", "is_sequence_variant_of", "SequenceVariant"}


def test_to_output_rows_collapses_a_path_edge_attributed_to_its_own_path_vertex() -> None:
    """F-2.1-J4-09 (judge audit of the previous round): the realistic case a
    path can actually produce, restored here after it was replaced by the
    distinct-records fixture above.

    A real AGE edge carries no `properties["id"]` (F-2.1-B06), so the
    `is_sequence_variant_of` edge below is attributed via its own stored
    `source_url` (F-2.1-C04/C05's priority 1), and that URL happens to name
    the exact same ClinVar variation as the SequenceVariant vertex already
    present later in the same path. This is not a contrived collision: it is
    the ordinary shape of `RETURN p = (g)-[e:is_sequence_variant_of]->(v)`,
    where the edge's relationship IS the fact that `e` and `v` describe the
    same ClinVar record. F-2.1-C06's dedup must collapse the two, so a
    3-element path yields 2 output rows, not 3, and the surviving row is the
    edge, which carries the `_cited_via_endpoint_curie` marker, not a bare
    vertex row indistinguishable from an accidental duplicate.

    The assertions below pin the exact curie and the endpoint-attribution
    marker, not just the row count, precisely so this is verifiably the
    edge-equals-endpoint case and not merely two unrelated rows that
    happened to share a URL by coincidence.
    """
    raw_row = {
        "result": (
            "["
            '{"id": 1, "label": "Gene", "properties": {"id": "NCBIGene:672"}}, '
            '{"id": 5, "label": "is_sequence_variant_of", "start_id": 1, '
            '"end_id": 2, "properties": {"source": "ClinVar", '
            '"source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/17660/"}}, '
            '{"id": 2, "label": "SequenceVariant", "properties": '
            '{"id": "ClinVar:17660", "name": "variant"}}'
            "]::path"
        )
    }

    rows = to_output_rows(raw_row, snapshot_version="2026-07-01")

    assert len(rows) == 2, (
        "the edge and the SequenceVariant vertex it connects to cite the "
        "identical ClinVar record and must collapse to one row"
    )
    types_seen = {row["node_or_edge_type"] for row in rows}
    assert types_seen == {"Gene", "is_sequence_variant_of"}, (
        "the surviving row for the collapsed pair must be the edge, the "
        "first of the two in path order, not the bare vertex"
    )
    edge_row = next(row for row in rows if row["node_or_edge_type"] == "is_sequence_variant_of")
    assert edge_row["curie"] == "ClinVar:17660"
    assert edge_row["source_url"] == "https://www.ncbi.nlm.nih.gov/clinvar/variation/17660/"
    assert edge_row["fields"]["_cited_via_endpoint_curie"] == "ClinVar:17660", (
        "the surviving row must be traceable to endpoint attribution, not "
        "presented as if it had its own independent citation"
    )


# ---------------------------------------------------------------------------
# T-3.4-03, closing F-2.2-A-05: `traversed_edge_type_by_column` threads the
# edge label the caller determined from the Cypher text onto the entity row
# it describes, only for a column that decoded to exactly one entity.
# ---------------------------------------------------------------------------


def test_to_output_rows_attaches_the_traversed_edge_type_to_its_column() -> None:
    raw_row = {
        "c0": (
            '{"id": 2, "label": "Disease", "properties": '
            '{"id": "MedGen:C0346153", "name": "disease"}}::vertex'
        ),
    }

    rows = to_output_rows(
        raw_row,
        snapshot_version="2026-07-01",
        traversed_edge_type_by_column={"c0": "gene_associated_with_condition"},
    )

    assert len(rows) == 1
    assert rows[0]["traversed_edge_type"] == "gene_associated_with_condition"


def test_to_output_rows_leaves_traversed_edge_type_none_when_not_supplied() -> None:
    """The bare identifier lookup case: no map entry, no attachment, the
    same output shape this function always produced before T-3.4-03."""
    raw_row = {
        "result": (
            '{"id": 2, "label": "Disease", "properties": '
            '{"id": "MedGen:C0346153", "name": "disease"}}::vertex'
        )
    }

    rows = to_output_rows(raw_row, snapshot_version="2026-07-01")

    assert len(rows) == 1
    assert rows[0]["traversed_edge_type"] is None


def test_to_output_rows_never_attaches_traversed_edge_type_to_a_path_column() -> None:
    """A path column can decode to more than one entity, so which of them
    the traversed label describes is ambiguous; T-3.4-03's own
    `to_output_rows` docstring requires this to stay unattached rather
    than guess."""
    raw_row = {
        "result": (
            "["
            '{"id": 1, "label": "Gene", "properties": {"id": "NCBIGene:672"}}, '
            '{"id": 5, "label": "is_sequence_variant_of", "start_id": 1, '
            '"end_id": 2, "properties": {"id": "ClinVar:999999"}}, '
            '{"id": 2, "label": "SequenceVariant", "properties": '
            '{"id": "ClinVar:17660"}}'
            "]::path"
        )
    }

    rows = to_output_rows(
        raw_row,
        snapshot_version="2026-07-01",
        traversed_edge_type_by_column={"result": "gene_associated_with_condition"},
    )

    assert len(rows) == 3
    assert all(row["traversed_edge_type"] is None for row in rows)
