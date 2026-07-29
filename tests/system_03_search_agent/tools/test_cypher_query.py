"""Tests for the cypher_query three-step pipeline (T-2.1-07).

No live database call and no live model call anywhere in this file: the
harness's `call_tier` is a hand-written async fake, and
`graph_connection.execute_cypher` is monkeypatched on the module object
`cypher_query` imported it into, the same pattern the sibling tool test
files already use (`test_cypher_generation.py`'s `_FakeHarness`,
`test_graph_connection.py`'s mocked psycopg2 connection).

Covers: a successful lookup, a successful multi-hop query, zero rows, a
first-attempt validation failure the retry repairs, two consecutive
validation failures, and both timeout paths (the tool's own outer
30-second budget, and a `GraphTimeoutError` raised by `execute_cypher`
itself).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from system_03_search_agent.tools import cypher_query as cypher_query_module
from system_03_search_agent.tools.cypher_query import cypher_query
from system_03_search_agent.tools.cypher_schemas import CypherQueryInput
from system_03_search_agent.tools.graph_connection import (
    GraphConnectionError,
    GraphTimeoutError,
)


class _FakeHarness:
    """A minimal `HarnessLike` stand-in: `call_tier` returns each of
    `responses` in order (or calls `response_fn(call_number)` when given),
    optionally sleeping `delay` seconds first, to exercise the timeout path
    without a real model call.
    """

    def __init__(
        self,
        responses: list[str] | None = None,
        response_fn: Any = None,
        delay: float = 0.0,
    ) -> None:
        self._responses = list(responses or [])
        self._response_fn = response_fn
        self._delay = delay
        self.calls: list[list[dict[str, str]]] = []

    async def call_tier(
        self, tier: str, messages: list[dict[str, str]], *, cache_prefix: str | None = None
    ) -> Any:
        self.calls.append(messages)
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._response_fn is not None:
            content = self._response_fn(len(self.calls))
        else:
            content = self._responses[len(self.calls) - 1]
        return SimpleNamespace(content=content)


def _gene_lookup_input(**overrides: object) -> CypherQueryInput:
    base: dict[str, object] = {
        "query_intent": "gene lookup for BRCA1",
        "query_class": "lookup",
        "target_entities": ["NCBIGene:672"],
        "row_limit": 100,
    }
    base.update(overrides)
    return CypherQueryInput(**base)


def _raw_gene_row(curie: str = "NCBIGene:672", symbol: str = "BRCA1") -> dict[str, Any]:
    return {
        "label": "Gene",
        "id": curie,
        "properties": {"symbol": symbol},
    }


# ---------------------------------------------------------------------------
# Successful lookup.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_lookup_returns_ok_status_with_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _FakeHarness(responses=["MATCH (g:Gene {id: $gene_id}) RETURN g"])
    captured: dict[str, Any] = {}

    def _fake_execute_cypher(cypher, params=None, row_limit=100, timeout_s=30.0, **kwargs):
        captured["cypher"] = cypher
        captured["params"] = params
        return [_raw_gene_row()], 1

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute_cypher)

    output = await cypher_query(harness, _gene_lookup_input())

    assert output.status == "ok"
    assert output.row_count == 1
    assert output.truncated is False
    assert output.error is None
    assert len(harness.calls) == 1  # exactly one generation call, no retry needed

    row = output.rows[0]
    assert row.curie == "NCBIGene:672"
    assert row.source_url == "https://www.ncbi.nlm.nih.gov/gene/672"
    assert row.graph_snapshot_version

    # The generated Cypher is present in the audit-trail field, and only
    # there: LIMIT was injected by the validator's normalization step.
    assert output.cypher_executed is not None
    assert "LIMIT" in output.cypher_executed

    # target_entities bound positionally to the generated parameter name.
    assert captured["params"] == {"gene_id": "NCBIGene:672"}


# ---------------------------------------------------------------------------
# Successful multi-hop query.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_multi_hop_query_returns_ok_status_with_multiple_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _FakeHarness(
        responses=[
            (
                "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $gene_id}) "
                "RETURN v, g"
            )
        ]
    )

    def _fake_execute_cypher(cypher, params=None, row_limit=100, timeout_s=30.0, **kwargs):
        return (
            [
                {"label": "SequenceVariant", "id": "ClinVar:12345", "properties": {}},
                {"label": "Gene", "id": "NCBIGene:672", "properties": {"symbol": "BRCA1"}},
            ],
            2,
        )

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute_cypher)

    tool_input = _gene_lookup_input(query_class="multi_hop")
    output = await cypher_query(harness, tool_input)

    assert output.status == "ok"
    assert output.row_count == 2
    assert output.total_available == 2
    assert output.truncated is False
    types_seen = {row.node_or_edge_type for row in output.rows}
    assert types_seen == {"SequenceVariant", "Gene"}


# ---------------------------------------------------------------------------
# Zero rows: status "empty", never "error".
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zero_rows_returns_empty_status_not_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _FakeHarness(responses=["MATCH (g:Gene {id: $gene_id}) RETURN g"])

    def _fake_execute_cypher(cypher, params=None, row_limit=100, timeout_s=30.0, **kwargs):
        return [], 0

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute_cypher)

    output = await cypher_query(harness, _gene_lookup_input())

    assert output.status == "empty"
    assert output.rows == []
    assert output.row_count == 0
    assert output.error is None


# ---------------------------------------------------------------------------
# First-attempt validation failure repaired by the one retry.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_attempt_validation_failure_is_repaired_by_the_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _FakeHarness(
        responses=[
            "MATCH (g:Gene)-->(v:SequenceVariant) RETURN g",  # untyped edge, rejected
            (
                "MATCH (g:Gene {id: $gene_id})<-[:is_sequence_variant_of]-(v:SequenceVariant) "
                "RETURN g"
            ),  # repaired: explicit edge label
        ]
    )

    def _fake_execute_cypher(cypher, params=None, row_limit=100, timeout_s=30.0, **kwargs):
        return [_raw_gene_row()], 1

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute_cypher)

    output = await cypher_query(harness, _gene_lookup_input())

    assert output.status == "ok"
    assert len(harness.calls) == 2  # exactly one repair retry, never a third attempt

    # The retry's user message carries the validator's error from the
    # first attempt, so the repair is informed, not a blind resample.
    retry_message = harness.calls[1][-1]["content"]
    assert "Validator error" in retry_message
    assert "missing_edge_label" in retry_message or "untyped relationship" in retry_message


# ---------------------------------------------------------------------------
# Two consecutive validation failures: status "error", never a third attempt.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_consecutive_validation_failures_return_error_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _FakeHarness(
        responses=[
            "MATCH (g:Gene)-->(v:SequenceVariant) RETURN g",
            "MATCH (g:Gene)-->(v:SequenceVariant) RETURN g",  # still untyped
        ]
    )
    execute_calls: list[object] = []

    def _fake_execute_cypher(cypher, params=None, row_limit=100, timeout_s=30.0, **kwargs):
        execute_calls.append(cypher)
        return [_raw_gene_row()], 1

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute_cypher)

    output = await cypher_query(harness, _gene_lookup_input())

    assert output.status == "error"
    assert output.rows == []
    assert output.row_count == 0
    assert output.error
    assert len(harness.calls) == 2  # never a third generation attempt
    assert execute_calls == []  # never reached execution


# ---------------------------------------------------------------------------
# Timeout: the tool's own outer 30s budget.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_outer_timeout_returns_error_status_with_actionable_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cypher_query_module, "CYPHER_QUERY_TIMEOUT_SECONDS", 0.05)
    harness = _FakeHarness(
        responses=["MATCH (g:Gene {id: $gene_id}) RETURN g"], delay=0.3
    )

    output = await cypher_query(harness, _gene_lookup_input())

    assert output.status == "error"
    assert output.rows == []
    assert "exceeded" in output.error
    assert "retry" in output.error
    assert "query_intent" in output.error or "query_class" in output.error


# ---------------------------------------------------------------------------
# Timeout: execute_cypher's own GraphTimeoutError surfaces as status=error.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graph_execution_timeout_returns_error_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _FakeHarness(responses=["MATCH (g:Gene {id: $gene_id}) RETURN g"])

    def _raise_timeout(cypher, params=None, row_limit=100, timeout_s=30.0, **kwargs):
        raise GraphTimeoutError(
            "graph query exceeded 30s, retry with a narrower query_intent or a "
            "smaller query_class"
        )

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _raise_timeout)

    output = await cypher_query(harness, _gene_lookup_input())

    assert output.status == "error"
    assert "exceeded 30s" in output.error
    assert output.cypher_executed is not None  # the executed Cypher is still recorded


@pytest.mark.asyncio
async def test_graph_connection_error_returns_error_status_not_a_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _FakeHarness(responses=["MATCH (g:Gene {id: $gene_id}) RETURN g"])

    def _raise_connection_error(cypher, params=None, row_limit=100, timeout_s=30.0, **kwargs):
        raise GraphConnectionError("graph connection refused or unreachable, retry")

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _raise_connection_error)

    output = await cypher_query(harness, _gene_lookup_input())

    assert output.status == "error"
    assert "connection" in output.error.lower()


# ---------------------------------------------------------------------------
# No-recoverable-Cypher generation failure is treated as a validation
# failure: one retry, then error.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unrecoverable_generation_response_triggers_the_retry_then_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _FakeHarness(responses=["not any recoverable cypher at all", "still nothing"])

    output = await cypher_query(harness, _gene_lookup_input())

    assert output.status == "error"
    assert len(harness.calls) == 2
    assert output.error
