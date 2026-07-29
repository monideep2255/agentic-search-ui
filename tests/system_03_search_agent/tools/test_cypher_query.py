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

Fixture note (phase 2.1 defect fix, findings F-2.1-A1/F-01/A2): the raw
rows `_fake_execute_cypher` returns here are now real agtype wire text,
keyed by AGE output column name, exactly what `graph_connection.
execute_cypher` actually hands back over the wire. Earlier versions of
these fixtures returned already-parsed dicts shaped like
`{"label": "Gene", "id": "NCBIGene:672", "properties": {...}}`, which is
not what execute_cypher ever returns; every one of these tests still
passed while the assembled tool silently dropped every real row, because
nothing here exercised the agtype-parsing seam. That seam is exactly what
`test_cypher_query_e2e.py` exists to close; these fixtures are corrected
to match reality rather than the prior (wrong) assumption.
"""

from __future__ import annotations

import asyncio
import json
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

    Finding F-04's fix note: `trace_id` and `get_query_cost_usd` are added
    so `cost_control.check_per_query_cap` (now called before every
    `generate_cypher` attempt) has something real to read, the same shape
    the real `Harness` exposes. `query_cost_usd` defaults to 0.0, a fresh
    query that has made no billable calls yet, so none of the existing
    tests below cross the cap unless a test explicitly sets it higher to
    exercise the breach path.
    """

    def __init__(
        self,
        responses: list[str] | None = None,
        response_fn: Any = None,
        delay: float = 0.0,
        trace_id: str = "fake-trace-id",
        query_cost_usd: float = 0.0,
    ) -> None:
        self._responses = list(responses or [])
        self._response_fn = response_fn
        self._delay = delay
        self.calls: list[list[dict[str, str]]] = []
        self.trace_id = trace_id
        self._query_cost_usd = query_cost_usd

    def get_query_cost_usd(self, trace_id: str) -> float:
        return self._query_cost_usd

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


def _agtype_vertex_text(label: str, curie: str, properties: dict[str, Any]) -> str:
    """Build the raw agtype wire text AGE emits for one vertex.

    Matches the exact shape `graph_connection.execute_cypher` reads off
    the wire: a JSON object with the graph-internal `id` (never the
    CURIE), `label`, and `properties`, suffixed with `::vertex`. The CURIE
    this system cites lives inside `properties["id"]`.
    """
    merged_properties = {"id": curie, **properties}
    payload = {
        "id": 844424930131969,
        "label": label,
        "properties": merged_properties,
    }
    return json.dumps(payload) + "::vertex"



def _raw_gene_row(curie: str = "NCBIGene:672", symbol: str = "BRCA1") -> dict[str, Any]:
    """One raw AGE result row, single column, real agtype wire text."""
    return {"result": _agtype_vertex_text("Gene", curie, {"symbol": symbol})}


# ---------------------------------------------------------------------------
# Successful lookup.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_lookup_returns_ok_status_with_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _FakeHarness(responses=["MATCH (g:Gene {id: $gene_id}) RETURN g"])
    captured: dict[str, Any] = {}

    def _fake_execute_cypher(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        captured["cypher"] = cypher
        captured["params"] = params
        captured["as_clause"] = as_clause
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
    assert row.node_or_edge_type == "Gene"
    assert row.fields.get("symbol") == "BRCA1"
    assert row.source_url == "https://www.ncbi.nlm.nih.gov/gene/672"
    assert row.graph_snapshot_version

    # The generated Cypher is present in the audit-trail field, and only
    # there: LIMIT was injected by the validator's normalization step.
    assert output.cypher_executed is not None
    assert "LIMIT" in output.cypher_executed

    # target_entities bound positionally to the generated parameter name.
    assert captured["params"] == {"gene_id": "NCBIGene:672"}

    # Finding F-01's fix: a single-item RETURN gets a single-column
    # as_clause, derived from the RETURN clause, never the raw caller text.
    assert captured["as_clause"] == "(c0 agtype)"


# ---------------------------------------------------------------------------
# Successful multi-hop query.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_multi_hop_query_returns_ok_status_with_multiple_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Finding F-01: a two-item RETURN (v, g) is one raw graph row carrying
    two agtype columns, `c0` and `c1`. `to_output_rows` splits that one raw
    row into two output rows, one per column, since `CypherQueryRow` has
    no shape for merging two distinct cited entities into a single row.
    """
    harness = _FakeHarness(
        responses=[
            (
                "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $gene_id}) "
                "RETURN v, g"
            )
        ]
    )
    captured: dict[str, Any] = {}

    def _fake_execute_cypher(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        captured["as_clause"] = as_clause
        return (
            [
                {
                    "c0": _agtype_vertex_text("SequenceVariant", "ClinVar:12345", {}),
                    "c1": _agtype_vertex_text("Gene", "NCBIGene:672", {"symbol": "BRCA1"}),
                }
            ],
            1,
        )

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute_cypher)

    tool_input = _gene_lookup_input(query_class="multi_hop")
    output = await cypher_query(harness, tool_input)

    assert output.status == "ok"
    assert output.row_count == 2
    # total_available reflects the one raw graph row that matched, not the
    # two output rows it was split into: one graph row was returned, and it
    # was fewer than the 100-row limit, so no truncation is possible.
    assert output.total_available == 1
    assert output.truncated is False
    types_seen = {row.node_or_edge_type for row in output.rows}
    assert types_seen == {"SequenceVariant", "Gene"}

    # Finding F-01's fix: a two-item RETURN gets a two-column as_clause.
    assert captured["as_clause"] == "(c0 agtype, c1 agtype)"


# ---------------------------------------------------------------------------
# Finding A2: total_available and truncated when the row limit is hit.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_row_count_under_the_limit_needs_no_count_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fewer rows than row_limit is already the true total: no second call."""
    harness = _FakeHarness(responses=["MATCH (g:Gene {id: $gene_id}) RETURN g"])
    calls: list[str] = []

    def _fake_execute_cypher(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        calls.append(cypher)
        return [_raw_gene_row()], 1

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute_cypher)

    output = await cypher_query(harness, _gene_lookup_input(row_limit=100))

    assert output.row_count == 1
    assert output.total_available == 1
    assert output.truncated is False
    assert len(calls) == 1  # no count-only second call was needed


@pytest.mark.asyncio
async def test_truncated_result_issues_a_count_query_for_the_true_total(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Finding A2: hitting the row limit exactly must trigger a second,
    count-only query, and the true count it returns, not the row limit,
    must be reported as total_available.
    """
    harness = _FakeHarness(
        responses=[
            "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $gene_id}) RETURN v"
        ]
    )
    calls: list[tuple[str, str | None]] = []

    def _fake_execute_cypher(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        calls.append((cypher, as_clause))
        if "count(*)" in cypher:
            return [{"total_count": "15310"}], 1
        return (
            [{"result": _agtype_vertex_text("SequenceVariant", "ClinVar:1", {})}] * 2,
            2,
        )

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute_cypher)

    output = await cypher_query(harness, _gene_lookup_input(row_limit=2))

    assert output.status == "ok"
    assert output.row_count == 2
    assert output.truncated is True
    assert output.total_available == 15310, (
        f"total_available was {output.total_available}, expected the true count "
        "from the count-only query, never the row limit itself"
    )
    assert len(calls) == 2
    count_call = next(c for c, _ in calls if "count(*)" in c)
    assert "LIMIT" not in count_call, "the count query must not carry the original LIMIT"
    assert "RETURN v" not in count_call, "the count query must discard the original RETURN"


@pytest.mark.asyncio
async def test_count_query_failure_reports_total_available_as_unknown_not_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A count-query failure must never fall back to reporting the row
    limit as if it were the true total: that is finding A2 in a different
    shape. total_available must be absent (None) instead.
    """
    harness = _FakeHarness(
        responses=[
            "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $gene_id}) RETURN v"
        ]
    )

    def _fake_execute_cypher(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        if "count(*)" in cypher:
            raise GraphTimeoutError("graph query exceeded 30s, retry with a narrower query_class")
        return (
            [{"result": _agtype_vertex_text("SequenceVariant", "ClinVar:1", {})}] * 2,
            2,
        )

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute_cypher)

    output = await cypher_query(harness, _gene_lookup_input(row_limit=2))

    assert output.status == "ok"
    assert output.row_count == 2
    assert output.truncated is True
    assert output.total_available is None, (
        "a failed count query must report total_available as unknown, "
        f"got {output.total_available!r} instead of None"
    )


# ---------------------------------------------------------------------------
# Cite-or-refuse: an entity with no resolvable citation is omitted.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_row_with_no_resolvable_citation_is_omitted_not_emitted_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An OntologyClass vertex with a GO CURIE has no NCBI-hosted record
    page (`cypher_provenance`'s documented gap), so it must never reach the
    caller as a content row with no citation. CLAUDE.md: every fact must
    link back to its source.
    """
    harness = _FakeHarness(responses=["MATCH (o:OntologyClass {id: $go_id}) RETURN o"])

    def _fake_execute_cypher(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        return (
            [{"result": _agtype_vertex_text("OntologyClass", "GO:0006096", {"name": "x"})}],
            1,
        )

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute_cypher)

    output = await cypher_query(harness, _gene_lookup_input())

    assert output.status == "empty", "an uncitable row must never surface as status=ok"
    assert output.rows == []
    assert output.row_count == 0


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


# ---------------------------------------------------------------------------
# Finding F-04: a per-query cost cap breach must never issue the call.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cap_already_breached_blocks_the_first_generate_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A harness whose running cost already exceeds the cap must never see
    even the first `generate_cypher` call: `harness.calls` must stay empty,
    and the breach surfaces as a normal `status: "error"`, not an
    exception escaping `cypher_query`.
    """
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "0.10")
    harness = _FakeHarness(
        responses=["MATCH (g:Gene {id: $gene_id}) RETURN g"],
        query_cost_usd=1.00,  # already well past the 0.10 cap
    )

    output = await cypher_query(harness, _gene_lookup_input())

    assert output.status == "error"
    assert harness.calls == [], "a cap breach must never dispatch the model call at all"
    assert output.error


@pytest.mark.asyncio
async def test_cap_breach_mid_retry_blocks_the_second_generate_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cap check runs before every attempt, not only the first: a
    harness that starts under the cap but crosses it before the retry
    (simulated here by raising cost after the first call records) must
    block the retry's own `generate_cypher` call too.
    """
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "0.10")
    harness = _FakeHarness(responses=["MATCH (g:Gene)-->(v:SequenceVariant) RETURN g"])

    original_call_tier = harness.call_tier

    async def _call_tier_then_blow_the_cap(tier, messages, *, cache_prefix=None):
        result = await original_call_tier(tier, messages, cache_prefix=cache_prefix)
        harness._query_cost_usd = 1.00  # simulate the first call's real cost landing
        return result

    harness.call_tier = _call_tier_then_blow_the_cap

    output = await cypher_query(harness, _gene_lookup_input())

    assert output.status == "error"
    # Exactly one generate_cypher call happened (the first, untyped-edge
    # attempt, itself rejected by the validator); the retry never reached
    # generate_cypher because the cap check blocked it first.
    assert len(harness.calls) == 1
