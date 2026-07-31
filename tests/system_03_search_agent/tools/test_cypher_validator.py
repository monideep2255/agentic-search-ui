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
    REASON_INVALID_ROW_LIMIT,
    REASON_LITERAL_INTERPOLATION_SUSPECTED,
    REASON_MALFORMED_CYPHER,
    REASON_MISSING_EDGE_LABEL,
    REASON_UNKNOWN_EDGE_LABEL,
    REASON_UNKNOWN_VERTEX_LABEL,
    REASON_UNSAFE_LIMIT_CLAUSE,
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


def test_valid_typed_hop_with_whitespace_variants_still_passes() -> None:
    # F-2.1-A4's fix must not overcorrect: a typed edge with generous
    # whitespace around every token is still a legitimate, safe query.
    result = validate_cypher(
        "MATCH (v:SequenceVariant) - [ :is_sequence_variant_of ] -> (g:Gene) "
        "RETURN v, g",
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
        # F-2.1-A4: whitespace around the hop tokens must not defeat the
        # untyped-edge gate. AGE compiles this to the identical all-edge-
        # table Append plan as the tight-spacing form above.
        "MATCH (a:Gene) - [x] -> (b:Article) RETURN a",
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


# ---------------------------------------------------------------------------
# F-2.1-A8: a comment must not defeat LIMIT injection, a mid-query
# WITH ... LIMIT must not be mistaken for the trailing cap, and every
# UNION branch must be capped independently.
# ---------------------------------------------------------------------------


def test_limit_hidden_in_a_line_comment_is_not_treated_as_real() -> None:
    result = validate_cypher(
        "MATCH (a:Article) RETURN a // LIMIT 999999", row_limit=500
    )

    assert result.ok is True
    assert result.normalized_cypher is not None
    assert "LIMIT 500" in result.normalized_cypher
    assert "999999" not in result.normalized_cypher
    assert "//" not in result.normalized_cypher


def test_mid_query_with_limit_is_not_mistaken_for_the_trailing_cap() -> None:
    result = validate_cypher(
        "MATCH (g:Gene) WHERE g.id=$x WITH g LIMIT 1 MATCH "
        "(v:SequenceVariant)-[:is_sequence_variant_of]->(g) RETURN v",
        row_limit=500,
    )

    assert result.ok is True
    assert result.normalized_cypher is not None
    # The inner scoping LIMIT survives untouched, and a genuine outer LIMIT
    # is appended after the final RETURN.
    assert result.normalized_cypher.count("LIMIT 1") == 1
    assert result.normalized_cypher.rstrip().endswith("LIMIT 500")


def test_every_union_branch_gets_its_own_limit() -> None:
    result = validate_cypher(
        "MATCH (a:Gene) WHERE a.id=$x RETURN a UNION MATCH (b:Gene) "
        "WHERE b.id=$y RETURN b",
        row_limit=500,
    )

    assert result.ok is True
    assert result.normalized_cypher is not None
    assert result.normalized_cypher.count("LIMIT 500") == 2


def test_union_all_branches_each_get_a_limit_and_keyword_is_preserved() -> None:
    result = validate_cypher(
        "MATCH (a:Gene) RETURN a UNION ALL MATCH (b:Gene) RETURN b",
        row_limit=100,
    )

    assert result.ok is True
    assert result.normalized_cypher is not None
    assert result.normalized_cypher.count("LIMIT 100") == 2
    assert "UNION ALL" in result.normalized_cypher


def test_block_comment_stripped_without_gluing_tokens() -> None:
    result = validate_cypher(
        "MATCH (g:Gene) /* internal note */ RETURN g", row_limit=50
    )

    assert result.ok is True
    assert result.normalized_cypher is not None
    assert "/*" not in result.normalized_cypher
    assert "RETURNg" not in result.normalized_cypher


# ---------------------------------------------------------------------------
# F-2.1-A9: a node pattern with a nested function call in its property map
# must still have its label checked.
# ---------------------------------------------------------------------------


def test_unknown_label_behind_a_nested_function_call_is_rejected() -> None:
    result = validate_cypher(
        "MATCH (n:TotallyFakeLabel {name: coalesce($a, $b)}) RETURN n",
        row_limit=500,
    )

    assert result.ok is False
    assert result.reason == REASON_UNKNOWN_VERTEX_LABEL
    assert result.normalized_cypher is None


def test_known_label_behind_a_nested_function_call_still_passes() -> None:
    result = validate_cypher(
        "MATCH (n:Gene {name: coalesce($a, $b)}) RETURN n",
        row_limit=500,
    )

    assert result.ok is True
    assert result.reason is None


# ---------------------------------------------------------------------------
# F-08 / bypass 4: row_limit is coerced and bounds-checked inside the
# validator itself, and the final normalized string is re-validated so a
# corrupted normalization can never slip through as ok=True.
# ---------------------------------------------------------------------------


def test_string_row_limit_carrying_injected_cypher_is_rejected() -> None:
    result = validate_cypher(
        "MATCH (g:Gene) RETURN g",
        row_limit="500 } MATCH (n) DETACH DELETE n RETURN n // ",
    )

    assert result.ok is False
    assert result.reason == REASON_INVALID_ROW_LIMIT
    assert result.normalized_cypher is None


def test_float_row_limit_is_rejected() -> None:
    result = validate_cypher("MATCH (g:Gene) RETURN g", row_limit=100.0)

    assert result.ok is False
    assert result.reason == REASON_INVALID_ROW_LIMIT


def test_bool_row_limit_is_rejected() -> None:
    result = validate_cypher("MATCH (g:Gene) RETURN g", row_limit=True)

    assert result.ok is False
    assert result.reason == REASON_INVALID_ROW_LIMIT


def test_out_of_bounds_int_row_limit_is_rejected() -> None:
    over_max = validate_cypher(
        "MATCH (g:Gene) RETURN g", row_limit=MAX_ROW_LIMIT + 1
    )
    zero = validate_cypher("MATCH (g:Gene) RETURN g", row_limit=0)
    negative = validate_cypher("MATCH (g:Gene) RETURN g", row_limit=-5)

    for result in (over_max, zero, negative):
        assert result.ok is False
        assert result.reason == REASON_INVALID_ROW_LIMIT


# ---------------------------------------------------------------------------
# F-2.1-A17: a literal bound to a known internal-constant field is allowed;
# a literal bound to a caller-facing identifying field is still rejected.
# ---------------------------------------------------------------------------


def test_literal_on_internal_constant_field_is_allowed() -> None:
    result = validate_cypher(
        "MATCH (a:Article) WHERE a.source = 'PubMed' RETURN a",
        row_limit=DEFAULT_ROW_LIMIT,
    )

    assert result.ok is True
    assert result.reason is None


def test_literal_on_caller_facing_field_is_still_rejected() -> None:
    # The allowlist must not swallow the general case: a literal bound to
    # an identifying field such as symbol is exactly what the check exists
    # to catch.
    result = validate_cypher(
        "MATCH (g:Gene {symbol: 'BRCA1'}) RETURN g",
        row_limit=DEFAULT_ROW_LIMIT,
    )

    assert result.ok is False
    assert result.reason == REASON_LITERAL_INTERPOLATION_SUSPECTED


def test_allowlisted_and_caller_facing_literal_together_still_rejects() -> None:
    # An allowlisted literal elsewhere in the query must not mask a second,
    # caller-facing literal that should have been a parameter.
    result = validate_cypher(
        "MATCH (a:Article) WHERE a.source = 'PubMed' AND a.name = 'x' "
        "RETURN a",
        row_limit=DEFAULT_ROW_LIMIT,
    )

    assert result.ok is False
    assert result.reason == REASON_LITERAL_INTERPOLATION_SUSPECTED


# ---------------------------------------------------------------------------
# F-2.1-B08: the fifth validator bypass. Six comparison forms other than
# `=`/`:` followed directly by a quote used to carry a literal straight
# through unchecked. Reproductions are the adversary report's exact
# strings. Each was confirmed FAILING (ok=True, no rejection) against the
# validator before this fix.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cypher",
    [
        "MATCH (g:Gene) WHERE g.name STARTS WITH 'BRCA' RETURN g",
        "MATCH (g:Gene) WHERE g.name CONTAINS 'BRCA1' RETURN g",
        "MATCH (g:Gene) WHERE g.name ENDS WITH 'X' RETURN g",
        "MATCH (g:Gene) WHERE g.id =~ '.*' RETURN g",
        "MATCH (g:Gene) WHERE g.id IN ['NCBIGene:672'] RETURN g",
        "MATCH (g:Gene) WHERE g.id <> 'x' RETURN g",
        "MATCH (g:Gene {taxon: 9606}) RETURN g",
    ],
    ids=[
        "starts_with",
        "contains",
        "ends_with",
        "regex_match",
        "in_list",
        "not_equal",
        "bare_numeric",
    ],
)
def test_literal_via_every_bypassed_comparison_form_is_rejected(cypher: str) -> None:
    result = validate_cypher(cypher, row_limit=DEFAULT_ROW_LIMIT)

    assert result.ok is False
    assert result.reason == REASON_LITERAL_INTERPOLATION_SUSPECTED
    assert result.normalized_cypher is None


def test_literal_via_a_novel_symbol_operator_is_still_caught() -> None:
    # The connector is matched by character class, not by naming every
    # operator, so a comparison symbol this validator has never been
    # told about by name (here a made-up doubled "==") is still
    # recognized as a connector between a field and a literal.
    result = validate_cypher(
        "MATCH (g:Gene) WHERE g.id == 'NCBIGene:672' RETURN g",
        row_limit=DEFAULT_ROW_LIMIT,
    )

    assert result.ok is False
    assert result.reason == REASON_LITERAL_INTERPOLATION_SUSPECTED


def test_internal_constant_field_still_allowed_via_the_new_connectors() -> None:
    # The generalized connector must not swallow the F-2.1-A17 allowlist:
    # an internal constant field bound through one of the newly-caught
    # comparison forms is still exempt.
    result = validate_cypher(
        "MATCH (a:Article) WHERE a.source STARTS WITH 'Pub' RETURN a",
        row_limit=DEFAULT_ROW_LIMIT,
    )

    assert result.ok is True
    assert result.reason is None


# ---------------------------------------------------------------------------
# F-2.1-B09: LIMIT normalization must not hand back invalid Cypher. Two
# shapes come out of the old normalizer syntactically broken: a LIMIT
# followed by SKIP in the wrong order, and a parameterized LIMIT. Both are
# confirmed against the live graph (in the fix report) to actually fail at
# execution, one with a genuine AGE syntax error and one with
# UndefinedParameter. Each reproduction was confirmed FAILING (ok=True,
# with a syntactically doubled LIMIT in normalized_cypher) before this
# fix.
# ---------------------------------------------------------------------------


def test_limit_before_skip_at_the_end_is_rejected_not_double_limited() -> None:
    result = validate_cypher(
        "MATCH (g:Gene)-[:mentioned_in]->(a:Article) RETURN g LIMIT 10 SKIP 5",
        row_limit=100,
    )

    assert result.ok is False
    assert result.reason == REASON_UNSAFE_LIMIT_CLAUSE
    assert result.normalized_cypher is None


def test_parameterized_limit_is_rejected_not_double_limited() -> None:
    result = validate_cypher(
        "MATCH (g:Gene)-[:mentioned_in]->(a:Article) RETURN g LIMIT $n",
        row_limit=100,
    )

    assert result.ok is False
    assert result.reason == REASON_UNSAFE_LIMIT_CLAUSE
    assert result.normalized_cypher is None


def test_skip_before_limit_the_conventional_order_still_passes() -> None:
    # The conventional clause order (SKIP then LIMIT) was already handled
    # correctly before this fix and must remain so: it is a genuine
    # trailing LIMIT with nothing after it.
    result = validate_cypher(
        "MATCH (g:Gene {id: $id}) RETURN g SKIP 5 LIMIT 10",
        row_limit=100,
    )

    assert result.ok is True
    assert result.normalized_cypher == (
        "MATCH (g:Gene {id: $id}) RETURN g SKIP 5 LIMIT 10"
    )


def test_mid_query_scoping_limit_still_left_untouched_by_the_new_classifier() -> None:
    # F-2.1-A8's legitimate case must survive the rewritten classifier:
    # a `WITH ... LIMIT n` scoping clause followed by more query
    # structure is not the branch's terminal LIMIT, so it is left alone
    # and the validator's own cap is still appended at the true end.
    result = validate_cypher(
        "MATCH (g:Gene) WHERE g.id=$x WITH g LIMIT 1 MATCH "
        "(v:SequenceVariant)-[:is_sequence_variant_of]->(g) RETURN v",
        row_limit=500,
    )

    assert result.ok is True
    assert result.normalized_cypher is not None
    assert result.normalized_cypher.count("LIMIT 1") == 1
    assert result.normalized_cypher.rstrip().endswith("LIMIT 500")


def test_unsafe_limit_clause_in_one_union_branch_rejects_the_whole_query() -> None:
    result = validate_cypher(
        "MATCH (a:Gene) WHERE a.id=$x RETURN a LIMIT $n UNION MATCH "
        "(b:Gene) WHERE b.id=$y RETURN b",
        row_limit=500,
    )

    assert result.ok is False
    assert result.reason == REASON_UNSAFE_LIMIT_CLAUSE
    assert result.normalized_cypher is None
