"""Tests for cypher_schemas.py (T-2.1-01).

Covers valid input, invalid input, and null or missing input for every
model: CypherQueryInput, CypherQueryRow, CypherQueryOutput, plus the
QueryClass enum's coercion and rejection behavior.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from system_03_search_agent.tools.cypher_schemas import (
    CypherQueryInput,
    CypherQueryOutput,
    CypherQueryRow,
    QueryClass,
)

VALID_SOURCE_URL = "https://www.ncbi.nlm.nih.gov/gene/672"
FOREIGN_SOURCE_URL = "https://evil.example/gene/672"


# ---------------------------------------------------------------------------
# CypherQueryInput
# ---------------------------------------------------------------------------


def test_input_valid_full() -> None:
    model = CypherQueryInput(
        query_intent="genes linked to BRCA1",
        query_class="single_hop",
        target_entities=["NCBIGene:672"],
        row_limit=250,
    )
    assert model.query_class is QueryClass.SINGLE_HOP
    assert model.target_entities == ["NCBIGene:672"]
    assert model.row_limit == 250


def test_input_valid_defaults() -> None:
    model = CypherQueryInput(query_intent="lookup BRCA1", query_class="lookup")
    assert model.target_entities == []
    assert model.row_limit == 100


def test_input_rejects_additional_property() -> None:
    with pytest.raises(ValidationError):
        CypherQueryInput(
            query_intent="x",
            query_class="lookup",
            unexpected_field="nope",
        )


@pytest.mark.parametrize("row_limit", [0, 501, "abc", 1.5])
def test_input_rejects_bad_row_limit(row_limit: object) -> None:
    with pytest.raises(ValidationError):
        CypherQueryInput(query_intent="x", query_class="lookup", row_limit=row_limit)


def test_input_rejects_unknown_query_class() -> None:
    with pytest.raises(ValidationError):
        CypherQueryInput(query_intent="x", query_class="not_a_real_class")


def test_input_rejects_too_many_target_entities() -> None:
    with pytest.raises(ValidationError):
        CypherQueryInput(
            query_intent="x",
            query_class="lookup",
            target_entities=[f"NCBIGene:{i}" for i in range(11)],
        )


def test_input_rejects_oversized_target_entity() -> None:
    with pytest.raises(ValidationError):
        CypherQueryInput(
            query_intent="x",
            query_class="lookup",
            target_entities=["a" * 101],
        )


def test_input_rejects_oversized_query_intent() -> None:
    with pytest.raises(ValidationError):
        CypherQueryInput(query_intent="a" * 1001, query_class="lookup")


def test_input_rejects_missing_query_intent() -> None:
    with pytest.raises(ValidationError):
        CypherQueryInput(query_class="lookup")  # type: ignore[call-arg]


def test_input_rejects_missing_query_class() -> None:
    with pytest.raises(ValidationError):
        CypherQueryInput(query_intent="x")  # type: ignore[call-arg]


def test_input_rejects_null_query_intent() -> None:
    with pytest.raises(ValidationError):
        CypherQueryInput(query_intent=None, query_class="lookup")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# CypherQueryRow
# ---------------------------------------------------------------------------


def _row_kwargs(**overrides: object) -> dict[str, object]:
    base = {
        "node_or_edge_type": "Gene",
        "curie": "NCBIGene:672",
        "fields": {"name": "BRCA1"},
        "source_url": VALID_SOURCE_URL,
        "graph_snapshot_version": "2026-07-29",
    }
    base.update(overrides)
    return base


def test_row_valid_with_source_url() -> None:
    row = CypherQueryRow(**_row_kwargs())
    assert row.source_url == VALID_SOURCE_URL


def test_row_valid_without_source_url() -> None:
    row = CypherQueryRow(**_row_kwargs(source_url=None))
    assert row.source_url is None


def test_row_rejects_foreign_source_url() -> None:
    with pytest.raises(ValidationError):
        CypherQueryRow(**_row_kwargs(source_url=FOREIGN_SOURCE_URL))


def test_row_rejects_too_many_fields() -> None:
    oversized_fields = {f"prop_{i}": i for i in range(31)}
    with pytest.raises(ValidationError):
        CypherQueryRow(**_row_kwargs(fields=oversized_fields))


def test_row_accepts_max_fields() -> None:
    max_fields = {f"prop_{i}": i for i in range(30)}
    row = CypherQueryRow(**_row_kwargs(fields=max_fields))
    assert len(row.fields) == 30


def test_row_rejects_additional_property() -> None:
    with pytest.raises(ValidationError):
        CypherQueryRow(**_row_kwargs(extra_field="nope"))


def test_row_rejects_oversized_node_or_edge_type() -> None:
    with pytest.raises(ValidationError):
        CypherQueryRow(**_row_kwargs(node_or_edge_type="x" * 51))


def test_row_rejects_oversized_curie() -> None:
    with pytest.raises(ValidationError):
        CypherQueryRow(**_row_kwargs(curie="x" * 101))


def test_row_rejects_oversized_snapshot_version() -> None:
    with pytest.raises(ValidationError):
        CypherQueryRow(**_row_kwargs(graph_snapshot_version="x" * 41))


def test_row_rejects_missing_node_or_edge_type() -> None:
    kwargs = _row_kwargs()
    del kwargs["node_or_edge_type"]
    with pytest.raises(ValidationError):
        CypherQueryRow(**kwargs)


def test_row_rejects_missing_curie() -> None:
    kwargs = _row_kwargs()
    del kwargs["curie"]
    with pytest.raises(ValidationError):
        CypherQueryRow(**kwargs)


def test_row_rejects_missing_snapshot_version() -> None:
    kwargs = _row_kwargs()
    del kwargs["graph_snapshot_version"]
    with pytest.raises(ValidationError):
        CypherQueryRow(**kwargs)


def test_row_rejects_null_curie() -> None:
    with pytest.raises(ValidationError):
        CypherQueryRow(**_row_kwargs(curie=None))


def test_row_traversed_edge_type_defaults_to_none() -> None:
    """T-3.4-03: additive field, absent by default, so every row shape
    from before this ticket still constructs unchanged."""
    row = CypherQueryRow(**_row_kwargs())
    assert row.traversed_edge_type is None


def test_row_accepts_traversed_edge_type() -> None:
    row = CypherQueryRow(**_row_kwargs(traversed_edge_type="gene_associated_with_condition"))
    assert row.traversed_edge_type == "gene_associated_with_condition"


def test_row_rejects_oversized_traversed_edge_type() -> None:
    with pytest.raises(ValidationError):
        CypherQueryRow(**_row_kwargs(traversed_edge_type="x" * 51))


def test_row_ambiguous_high_risk_edge_touch_defaults_to_false() -> None:
    """F-3.4-A-02: additive field, `False` by default, so every row shape
    from before this fix still constructs unchanged."""
    row = CypherQueryRow(**_row_kwargs())
    assert row.ambiguous_high_risk_edge_touch is False


def test_row_accepts_ambiguous_high_risk_edge_touch() -> None:
    row = CypherQueryRow(**_row_kwargs(ambiguous_high_risk_edge_touch=True))
    assert row.ambiguous_high_risk_edge_touch is True


# ---------------------------------------------------------------------------
# CypherQueryOutput
# ---------------------------------------------------------------------------


def test_output_valid_ok() -> None:
    output = CypherQueryOutput(
        status="ok",
        rows=[CypherQueryRow(**_row_kwargs())],
        row_count=1,
        total_available=1,
        truncated=False,
        cypher_executed="MATCH (g:Gene {id: $id}) RETURN g",
    )
    assert output.status == "ok"
    assert output.row_count == 1


def test_output_valid_empty() -> None:
    output = CypherQueryOutput(status="empty", rows=[], row_count=0, truncated=False)
    assert output.status == "empty"
    assert output.rows == []


def test_output_valid_error() -> None:
    output = CypherQueryOutput(
        status="error",
        rows=[],
        row_count=0,
        truncated=False,
        error="graph query exceeded 30s, retry with a narrower query_intent",
    )
    assert output.status == "error"
    assert output.error is not None


def test_output_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        CypherQueryOutput(status="weird", rows=[], row_count=0, truncated=False)


def test_output_rejects_too_many_rows() -> None:
    rows = [CypherQueryRow(**_row_kwargs()) for _ in range(501)]
    with pytest.raises(ValidationError):
        CypherQueryOutput(status="ok", rows=rows, row_count=501, truncated=False)


def test_output_rejects_additional_property() -> None:
    with pytest.raises(ValidationError):
        CypherQueryOutput(
            status="ok",
            rows=[],
            row_count=0,
            truncated=False,
            unexpected_field="nope",
        )


def test_output_rejects_oversized_cypher_executed() -> None:
    with pytest.raises(ValidationError):
        CypherQueryOutput(
            status="ok",
            rows=[],
            row_count=0,
            truncated=False,
            cypher_executed="x" * 2001,
        )


def test_output_rejects_oversized_error() -> None:
    with pytest.raises(ValidationError):
        CypherQueryOutput(
            status="error",
            rows=[],
            row_count=0,
            truncated=False,
            error="x" * 501,
        )


def test_output_rejects_missing_status() -> None:
    with pytest.raises(ValidationError):
        CypherQueryOutput(rows=[], row_count=0, truncated=False)  # type: ignore[call-arg]


def test_output_rejects_missing_row_count() -> None:
    with pytest.raises(ValidationError):
        CypherQueryOutput(status="ok", rows=[], truncated=False)  # type: ignore[call-arg]


def test_output_rejects_missing_truncated() -> None:
    with pytest.raises(ValidationError):
        CypherQueryOutput(status="ok", rows=[], row_count=0)  # type: ignore[call-arg]


def test_output_rejects_null_truncated() -> None:
    with pytest.raises(ValidationError):
        CypherQueryOutput(status="ok", rows=[], row_count=0, truncated=None)  # type: ignore[arg-type]
