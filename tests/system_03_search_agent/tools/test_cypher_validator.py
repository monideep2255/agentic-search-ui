"""Tests for the deterministic Cypher validator (T-2.1-04).

Depends on:
    - system_03_search_agent.tools.cypher_validator (validate_cypher,
      ValidationResult, and the REASON_* constants)
    - system_03_search_agent.tools.graph_schema_constants (MAX_ROW_LIMIT,
      DEFAULT_ROW_LIMIT, used only to build valid/invalid fixture strings)
"""

from __future__ import annotations

import pytest

from system_03_search_agent.tools.cypher_validator import (
    REASON_LITERAL_INTERPOLATION_SUSPECTED,
    REASON_MALFORMED_CYPHER,
    REASON_MISSING_EDGE_LABEL,
    REASON_UNKNOWN_EDGE_LABEL,
    REASON_UNKNOWN_VERTEX_LABEL,
    REASON_WRITE_CLAUSE_FORBIDDEN,
    ValidationResult,
    validate_cypher,
)
from system_03_search_agent.tools.graph_schema_constants import (
    DEFAULT_ROW_LIMIT,
    MAX_ROW_LIMIT,
)

# ---------------------------------------------------------------------------
# Valid queries: a single-hop and a multi-hop query both pass and get a
# LIMIT injected.
# ---------------------------------------------------------------------------


def test_valid_single_hop_query_passes() -> None:
    result = validate_cypher(
        "MATCH (g:Gene {id: $gene_id}) RETURN g", row_limit=100
    )

    assert result.ok is True
    assert result.reason is None
    assert result.normalized_cypher is not None
    assert "LIMIT 100" in result.normalized_cypher


def test_valid_multi_hop_query_passes() -> None:
    result = validate_cypher(
        "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $gene_id}) "
        "RETURN v, g",
        row_limit=50,
    )

    assert result.ok is True
    assert result.reason is None
    assert "LIMIT 50" in result.normalized_cypher


def test_valid_query_with_edge_alternation_and_multi_labels_passes() -> None:
    result = validate_cypher(
        "MATCH (n:OntologyClass:NamedThing)-[r:subclass_of|exact_match]->(m:OntologyClass) "
        "RETURN n, m",
        row_limit=10,
    )

    assert result.ok is True
    assert result.reason is None


# ---------------------------------------------------------------------------
# missing_edge_label: untyped relationship patterns of every shorthand.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cypher",
    [
        "MATCH (g:Gene)-[r]-(a:Article) RETURN g",
        "MATCH (g:Gene)-->(a:Article) RETURN g",
        "MATCH (g:Gene)<--(a:Article) RETURN g",
        "MATCH (g:Gene)-[]->(a:Article) RETURN g",
        "MATCH (g:Gene)--(a:Article) RETURN g",
    ],
)
def test_untyped_relationship_rejected(cypher: str) -> None:
    result = validate_cypher(cypher, row_limit=DEFAULT_ROW_LIMIT)

    assert result.ok is False
    assert result.reason == REASON_MISSING_EDGE_LABEL
    assert result.normalized_cypher is None
    assert result.message is not None


# ---------------------------------------------------------------------------
# unknown_edge_label: a relationship label not in EDGE_LABELS.
# ---------------------------------------------------------------------------


def test_unknown_edge_label_rejected() -> None:
    result = validate_cypher(
        "MATCH (g:Gene)-[:not_a_real_edge_label]->(a:Article) RETURN g",
        row_limit=DEFAULT_ROW_LIMIT,
    )

    assert result.ok is False
    assert result.reason == REASON_UNKNOWN_EDGE_LABEL
    assert result.normalized_cypher is None


def test_one_unknown_label_in_alternation_rejects_whole_pattern() -> None:
    result = validate_cypher(
        "MATCH (n:OntologyClass)-[r:subclass_of|not_a_real_edge]->(m:OntologyClass) "
        "RETURN n",
        row_limit=DEFAULT_ROW_LIMIT,
    )

    assert result.ok is False
    assert result.reason == REASON_UNKNOWN_EDGE_LABEL


# ---------------------------------------------------------------------------
# unknown_vertex_label: a node label not in VERTEX_LABELS.
# ---------------------------------------------------------------------------


def test_unknown_vertex_label_rejected() -> None:
    result = validate_cypher(
        "MATCH (u:NotARealVertexLabel) RETURN u",
        row_limit=DEFAULT_ROW_LIMIT,
    )

    assert result.ok is False
    assert result.reason == REASON_UNKNOWN_VERTEX_LABEL
    assert result.normalized_cypher is None


def test_unlabeled_node_pattern_is_not_a_vertex_label_violation() -> None:
    # A bare variable in parens with no label, including the shape a
    # function call like count(a) takes, is legal and is not this
    # validator's concern; it should not spuriously trip
    # unknown_vertex_label.
    result = validate_cypher(
        "MATCH (g:Gene)-[:mentioned_in]->(a:Article) RETURN count(a) AS total",
        row_limit=DEFAULT_ROW_LIMIT,
    )

    assert result.ok is True
    assert result.reason is None


# ---------------------------------------------------------------------------
# write_clause_forbidden: every forbidden clause, several casings, and the
# no-false-positive-on-substring guarantee.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cypher",
    [
        "CREATE (g:Gene {id: $id}) RETURN g",
        "create (g:Gene {id: $id}) RETURN g",
        "CrEaTe (g:Gene {id: $id}) RETURN g",
        "MATCH (g:Gene {id: $id}) MERGE (a:Article {id: $aid}) RETURN g",
        "MATCH (g:Gene {id: $id}) DELETE g",
        "MATCH (g:Gene {id: $id}) DETACH DELETE g",
        "MATCH (g:Gene {id: $id}) detach delete g",
        "MATCH (g:Gene {id: $id}) SET g.name = $name RETURN g",
        "MATCH (g:Gene {id: $id}) set g.name = $name RETURN g",
        "MATCH (g:Gene {id: $id}) REMOVE g.name RETURN g",
        "MATCH (g:Gene {id: $id}) DROP INDEX g RETURN g",
        "MATCH (g:Gene {id: $id}) LOAD CSV FROM $url AS row RETURN g",
    ],
)
def test_forbidden_write_clause_rejected_any_casing(cypher: str) -> None:
    result = validate_cypher(cypher, row_limit=DEFAULT_ROW_LIMIT)

    assert result.ok is False
    assert result.reason == REASON_WRITE_CLAUSE_FORBIDDEN
    assert result.normalized_cypher is None


def test_identifier_containing_forbidden_keyword_as_substring_is_not_flagged() -> None:
    # "dataset_id" contains "set" but must not trip the SET check: there is
    # no word boundary on either side of "set" inside "dataset_id". With a
    # parameter reference and no literal, this query should pass cleanly.
    result = validate_cypher(
        "MATCH (g:Gene {dataset_id: $dataset_id}) RETURN g.dataset_id",
        row_limit=DEFAULT_ROW_LIMIT,
    )

    assert result.ok is True
    assert result.reason is None


def test_identifier_substring_with_a_real_literal_fails_for_the_right_reason() -> None:
    # Same substring guarantee, this time with a literal value present. The
    # rejection must be literal_interpolation_suspected, never
    # write_clause_forbidden misattributed to the "set" inside "dataset_id".
    result = validate_cypher(
        "MATCH (g:Gene {dataset_id: 'abc123'}) RETURN g",
        row_limit=DEFAULT_ROW_LIMIT,
    )

    assert result.ok is False
    assert result.reason == REASON_LITERAL_INTERPOLATION_SUSPECTED


# ---------------------------------------------------------------------------
# malformed_cypher: empty input and unbalanced brackets.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cypher",
    [
        "",
        "   ",
        "MATCH (g:Gene RETURN g",
        "MATCH (g:Gene {id: $id) RETURN g",
        "MATCH (g:Gene)-[:mentioned_in->(a:Article) RETURN g",
    ],
)
def test_malformed_cypher_rejected(cypher: str) -> None:
    result = validate_cypher(cypher, row_limit=DEFAULT_ROW_LIMIT)

    assert result.ok is False
    assert result.reason == REASON_MALFORMED_CYPHER
    assert result.normalized_cypher is None


# ---------------------------------------------------------------------------
# literal_interpolation_suspected: a literal value bound where a parameter
# was expected.
# ---------------------------------------------------------------------------


def test_literal_string_in_property_map_rejected() -> None:
    result = validate_cypher(
        "MATCH (g:Gene {symbol: 'BRCA1'}) RETURN g",
        row_limit=DEFAULT_ROW_LIMIT,
    )

    assert result.ok is False
    assert result.reason == REASON_LITERAL_INTERPOLATION_SUSPECTED
    assert result.normalized_cypher is None


def test_literal_string_in_comparison_rejected() -> None:
    result = validate_cypher(
        'MATCH (g:Gene) WHERE g.symbol = "BRCA1" RETURN g',
        row_limit=DEFAULT_ROW_LIMIT,
    )

    assert result.ok is False
    assert result.reason == REASON_LITERAL_INTERPOLATION_SUSPECTED


def test_parameterized_query_is_not_flagged_as_literal_interpolation() -> None:
    result = validate_cypher(
        "MATCH (g:Gene {symbol: $symbol}) RETURN g",
        row_limit=DEFAULT_ROW_LIMIT,
    )

    assert result.ok is True
    assert result.reason is None


# ---------------------------------------------------------------------------
# LIMIT normalization: injection when absent, capping when over MAX_ROW_LIMIT.
# ---------------------------------------------------------------------------


def test_missing_limit_is_injected() -> None:
    result = validate_cypher("MATCH (g:Gene {id: $id}) RETURN g", row_limit=100)

    assert result.ok is True
    assert result.normalized_cypher == "MATCH (g:Gene {id: $id}) RETURN g LIMIT 100"


def test_trailing_semicolon_handled_when_injecting_limit() -> None:
    result = validate_cypher("MATCH (g:Gene {id: $id}) RETURN g;", row_limit=25)

    assert result.ok is True
    assert result.normalized_cypher == "MATCH (g:Gene {id: $id}) RETURN g LIMIT 25"


def test_existing_limit_under_max_is_preserved() -> None:
    result = validate_cypher(
        "MATCH (g:Gene {id: $id}) RETURN g LIMIT 10", row_limit=100
    )

    assert result.ok is True
    assert "LIMIT 10" in result.normalized_cypher


def test_existing_limit_over_max_is_capped() -> None:
    over_max = MAX_ROW_LIMIT + 500
    result = validate_cypher(
        "MATCH (g:Gene {id: $id}) RETURN g LIMIT " + str(over_max),
        row_limit=100,
    )

    assert result.ok is True
    assert "LIMIT " + str(MAX_ROW_LIMIT) in result.normalized_cypher
    assert "LIMIT " + str(over_max) not in result.normalized_cypher


def test_existing_limit_case_insensitive() -> None:
    over_max = MAX_ROW_LIMIT + 1
    result = validate_cypher(
        "MATCH (g:Gene {id: $id}) RETURN g limit " + str(over_max),
        row_limit=100,
    )

    # Lowercase "limit" must still be recognized and capped; the keyword's
    # original casing is preserved, only the number is replaced.
    assert result.ok is True
    assert result.normalized_cypher == (
        "MATCH (g:Gene {id: $id}) RETURN g limit " + str(MAX_ROW_LIMIT)
    )
    assert str(over_max) not in result.normalized_cypher


# ---------------------------------------------------------------------------
# Determinism: the same input always yields the same verdict.
# ---------------------------------------------------------------------------


def test_validation_is_deterministic_across_repeated_calls() -> None:
    cypher = "MATCH (g:Gene {symbol: $symbol}) RETURN g"

    results = [validate_cypher(cypher, row_limit=100) for _ in range(5)]

    assert all(r == results[0] for r in results)


def test_validation_result_is_frozen_dataclass() -> None:
    result = validate_cypher("MATCH (g:Gene {symbol: $symbol}) RETURN g")

    assert isinstance(result, ValidationResult)
    with pytest.raises(Exception):
        result.ok = False  # type: ignore[misc]
