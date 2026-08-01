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
import time
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
    harness = _FakeHarness(responses=["MATCH (g:Gene {id: $e_NCBIGene_672}) RETURN g"])
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
    assert captured["params"] == {"e_NCBIGene_672": "NCBIGene:672"}

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

    Finding F-2.1-B04c: total_available must match row_count's own unit,
    not the raw graph-row count, since to_output_rows can emit more
    output rows than there were graph rows. Before that fix this test
    asserted total_available == 1 next to row_count == 2, the exact
    "row_count exceeds total_available" incoherence the adversary
    reproduced (`row_count=8 total_available=4 truncated=false`) in
    miniature.
    """
    harness = _FakeHarness(
        responses=[
            (
                "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $e_NCBIGene_672}) "
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
    # Finding F-2.1-B04c's fix: total_available must equal row_count when
    # nothing was capped, since every match is already in hand and both
    # numbers describe the same output rows. One graph row was returned
    # and it was fewer than the 100-row limit, so no truncation is
    # possible; total_available is 2, not the raw graph-row count of 1.
    assert output.total_available == 2
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
    harness = _FakeHarness(responses=["MATCH (g:Gene {id: $e_NCBIGene_672}) RETURN g"])
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
            "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $e_NCBIGene_672}) RETURN v"
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
    # F-2.1-C14 changed what this number means. The fixture returns the
    # SAME variant vertex twice (`[...] * 2`), which is one record reported
    # twice, not two findings. `row_count` now counts distinct cited
    # records and `rows` holds one entry per record, so the two agree.
    # Truncation and the true total are unaffected: the row LIMIT was still
    # hit, and 15310 is still the answer.
    assert output.row_count == 1
    assert output.row_count == len(output.rows)
    assert output.truncated is True
    assert output.total_available == 15310, (
        f"total_available was {output.total_available}, expected the true count "
        "from the count-only query, never the row limit itself"
    )
    assert len(calls) == 2
    count_call = next(c for c, _ in calls if "count(*)" in c)
    assert "LIMIT 2" not in count_call, "the count query must not carry the original LIMIT"
    assert "RETURN v" not in count_call, "the count query must discard the original RETURN"
    # Finding F-2.1-13's fix: the count query is now itself passed back
    # through validate_cypher, which is what supplies this LIMIT; the
    # validator's own contract is that every query it validates leaves
    # with one.
    assert "LIMIT" in count_call, "the count query must pass through validate_cypher too"


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
            "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $e_NCBIGene_672}) RETURN v"
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
    # F-2.1-C14: the fixture returns one variant twice, so one distinct
    # record. What this test is actually about is unchanged: a failed count
    # query must report the total as unknown rather than fall back to the
    # row limit.
    assert output.row_count == 1
    assert output.row_count == len(output.rows)
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
    harness = _FakeHarness(responses=["MATCH (o:OntologyClass {id: $e_NCBIGene_672}) RETURN o"])

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
    harness = _FakeHarness(responses=["MATCH (g:Gene {id: $e_NCBIGene_672}) RETURN g"])

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
                "MATCH (g:Gene {id: $e_NCBIGene_672})<-[:is_sequence_variant_of]-(v:SequenceVariant) "
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
        responses=["MATCH (g:Gene {id: $e_NCBIGene_672}) RETURN g"], delay=0.3
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
    harness = _FakeHarness(responses=["MATCH (g:Gene {id: $e_NCBIGene_672}) RETURN g"])

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
    harness = _FakeHarness(responses=["MATCH (g:Gene {id: $e_NCBIGene_672}) RETURN g"])

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
        responses=["MATCH (g:Gene {id: $e_NCBIGene_672}) RETURN g"],
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


# ---------------------------------------------------------------------------
# F-2.1-06: the graph call must not block the event loop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_slow_graph_call_does_not_starve_the_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`execute_cypher` is synchronous and must run off-thread.

    Finding F-2.1-06. Awaiting a synchronous call directly blocks the whole
    event loop, so `asyncio.wait_for` cannot cancel it: measured, a 0.5
    second wait_for around a 4 second call returned normally after 4.01
    seconds with the loop ticking once where a healthy loop ticks about 40
    times. Both this tool's own 30 second bound and Act's `enforce_timeout`
    were dead code for the duration of every graph query, and one query
    froze every concurrent SSE stream.

    This asserts the two properties that fix has to deliver: another task
    keeps running while the graph call is in flight, and a `wait_for` above
    it can actually interrupt it.
    """
    started = asyncio.Event()

    def slow_execute(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        time.sleep(1.0)
        return ([], 0)

    monkeypatch.setattr(cypher_query_module, "execute_cypher", slow_execute)

    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        while not started.is_set():
            await asyncio.sleep(0.05)
            ticks += 1

    ticker_task = asyncio.create_task(ticker())

    harness = _FakeHarness(responses=["MATCH (g:Gene {id: $e_NCBIGene_672}) RETURN g"])
    await cypher_query(harness, _gene_lookup_input())

    started.set()
    await ticker_task

    assert ticks >= 3, (
        f"the event loop ticked only {ticks} times during a 1 second graph "
        "call; it is being starved, so the graph call is still blocking"
    )


@pytest.mark.asyncio
async def test_a_timeout_above_the_graph_call_can_actually_cancel_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A budget above a blocking call is only real if it can interrupt it."""

    def slow_execute(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        time.sleep(3.0)
        return ([], 0)

    monkeypatch.setattr(cypher_query_module, "execute_cypher", slow_execute)

    harness = _FakeHarness(responses=["MATCH (g:Gene {id: $e_NCBIGene_672}) RETURN g"])

    start = time.monotonic()
    with pytest.raises((TimeoutError, asyncio.TimeoutError)):
        await asyncio.wait_for(cypher_query(harness, _gene_lookup_input()), timeout=0.5)
    elapsed = time.monotonic() - start

    assert elapsed < 1.5, (
        f"wait_for(0.5) returned after {elapsed:.2f}s against a 3s call; the "
        "timeout is not able to interrupt the graph call"
    )


# ---------------------------------------------------------------------------
# Finding F-2.1-B04a: a model-supplied LIMIT smaller than the caller's
# row_limit must still be recognised as "the cap was hit".
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_model_supplied_limit_below_row_limit_still_triggers_true_total(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Before this fix, hitting the cap was detected by comparing the row
    count against tool_input.row_limit alone. cypher_validator preserves a
    model-supplied LIMIT smaller than row_limit rather than replacing it,
    so a generated `LIMIT 10` against a row_limit of 100 never looked
    "full" and reported 10 as the whole answer to a 15,310-row question,
    with truncated=False asserting completeness. The adversary's exact
    reproduction.
    """
    harness = _FakeHarness(
        responses=[
            (
                "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $e_NCBIGene_672}) "
                "RETURN v LIMIT 10"
            )
        ]
    )
    calls: list[str] = []

    def _fake_execute_cypher(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        calls.append(cypher)
        if "count(*)" in cypher:
            return [{"total_count": "15310"}], 1
        return (
            [
                {"result": _agtype_vertex_text("SequenceVariant", f"ClinVar:{i}", {})}
                for i in range(10)
            ],
            10,
        )

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute_cypher)

    output = await cypher_query(harness, _gene_lookup_input(row_limit=100))

    assert output.status == "ok"
    assert output.row_count == 10
    assert output.truncated is True, (
        "a model-supplied LIMIT 10 hit against a 15,310-row answer must be "
        "reported as truncated, not as a complete result"
    )
    assert output.total_available == 15310, (
        f"total_available was {output.total_available}, expected the true "
        "count behind the model's own LIMIT 10, never the limit itself"
    )
    assert len(calls) == 2, "hitting the model's own LIMIT must still trigger the count query"


# ---------------------------------------------------------------------------
# Finding F-2.1-B04b: RETURN DISTINCT must be counted as count(DISTINCT
# ...), not a bare count(*).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_return_distinct_counts_the_deduplicated_expression_not_every_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The adversary's reproduction: `RETURN DISTINCT g` over a gene with
    15,310 variant edges but exactly one distinct gene reported
    total_available=15310, because the old _build_count_cypher discarded
    DISTINCT and counted every raw match with a bare count(*). The true
    answer is 1.
    """
    harness = _FakeHarness(
        responses=[
            (
                "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $e_NCBIGene_672}) "
                "RETURN DISTINCT g"
            )
        ]
    )
    calls: list[str] = []

    def _fake_execute_cypher(cypher, params=None, row_limit=1, timeout_s=30.0, as_clause=None):
        calls.append(cypher)
        if "count(DISTINCT" in cypher:
            return [{"total_count": "1"}], 1
        if "count(*)" in cypher:
            # What the unfixed _build_count_cypher would have built: every
            # raw match before deduplication, not the distinct total.
            return [{"total_count": "15310"}], 1
        return [{"result": _agtype_vertex_text("Gene", "NCBIGene:672", {"symbol": "BRCA1"})}], 1

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute_cypher)

    output = await cypher_query(harness, _gene_lookup_input(row_limit=1))

    assert output.status == "ok"
    assert output.row_count == 1
    assert output.total_available == 1, (
        f"total_available was {output.total_available}, expected the true "
        "distinct count (1), not a raw match count that ignores DISTINCT"
    )
    assert output.truncated is False
    assert len(calls) == 2
    count_call = next(c for c in calls if "count(" in c)
    assert "count(DISTINCT" in count_call, (
        "the count query must count the deduplicated expression, not count(*)"
    )


# ---------------------------------------------------------------------------
# Finding F-2.1-B04c: total_available must never sit in a different unit
# than row_count.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multi_column_return_reports_total_available_in_row_count_units(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`RETURN v, g` explodes each raw graph row into two output rows, one
    per column, so four raw matches produce eight citable output rows.
    total_available must report 8, matching row_count, not the raw
    graph-row count of 4. The adversary's reproduction was exactly this
    shape: row_count=8 total_available=4 truncated=false, "incoherent on
    its face".
    """
    harness = _FakeHarness(
        responses=[
            (
                "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $e_NCBIGene_672}) "
                "RETURN v, g"
            )
        ]
    )

    def _fake_execute_cypher(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        return (
            [
                {
                    "c0": _agtype_vertex_text("SequenceVariant", f"ClinVar:{i}", {}),
                    "c1": _agtype_vertex_text("Gene", "NCBIGene:672", {"symbol": "BRCA1"}),
                }
                for i in range(4)
            ],
            4,
        )

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute_cypher)

    tool_input = _gene_lookup_input(query_class="multi_hop", row_limit=100)
    output = await cypher_query(harness, tool_input)

    assert output.status == "ok"
    # F-2.1-B04c's requirement still holds: total_available and row_count
    # must be in the same unit. F-2.1-C14 corrected which unit that is.
    #
    # `RETURN v, g` over 4 raw rows emits 4 variants and the SAME gene four
    # times. Reporting 8 was internally coherent and told the reader there
    # were eight findings when there are five records: four variants and
    # one gene. The repeats are dropped rather than counted, so `rows`
    # holds five entries and both numbers are five.
    assert output.row_count == 5
    assert output.row_count == len(output.rows)
    assert output.total_available == 5, (
        f"total_available was {output.total_available}, expected 5 to match "
        "row_count; the raw graph-row count of 4 and the pre-dedup row count "
        "of 8 are both the wrong unit for a reader"
    )
    # The repeated gene is present once, not four times.
    assert [row.node_or_edge_type for row in output.rows].count("Gene") == 1
    assert output.truncated is False


# ---------------------------------------------------------------------------
# Finding F-2.1-13: a UNION query's count-only rewrite must never describe
# only its first branch.
# ---------------------------------------------------------------------------


def test_build_count_cypher_returns_none_for_a_union_query() -> None:
    """A top-level UNION combines independent branches this function
    cannot count together: taking only the text before the first RETURN
    silently discarded every branch after the first, reporting one
    branch's count as the whole result's total. It must abstain (None)
    instead.
    """
    cypher = (
        "MATCH (g:Gene {id: $e_NCBIGene_672}) RETURN g LIMIT 5 "
        "UNION MATCH (d:Disease {id: $e_NCBIGene_672}) RETURN d LIMIT 5"
    )
    assert cypher_query_module._build_count_cypher(cypher) is None


@pytest.mark.asyncio
async def test_union_query_that_hits_its_cap_reports_total_available_as_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End to end: a UNION query must never even reach the count-only
    path (_build_count_cypher returns None for it), so hitting the cap
    reports total_available as unknown rather than one branch's count
    standing in for the whole result.
    """
    harness = _FakeHarness(
        responses=[
            (
                "MATCH (g:Gene {id: $e_NCBIGene_672}) RETURN g LIMIT 1 "
                "UNION MATCH (g:Gene {id: $e_NCBIGene_672}) RETURN g LIMIT 1"
            )
        ]
    )
    count_calls: list[str] = []

    def _fake_execute_cypher(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        if "count(" in cypher:
            count_calls.append(cypher)
            return [{"total_count": "999"}], 1
        return [_raw_gene_row()], 1

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute_cypher)

    output = await cypher_query(harness, _gene_lookup_input(row_limit=1))

    assert output.status == "ok"
    assert output.total_available is None, (
        "a UNION query must never report a count query's number; only one "
        "branch's true total can ever be computed, which is not the whole "
        "answer"
    )
    assert output.truncated is True
    assert count_calls == [], "a UNION query must never even attempt the count-only query"


# ---------------------------------------------------------------------------
# Finding F-2.1-09: the count-only query must get a freshly recomputed
# budget, not the main query's budget reused unchanged.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_query_gets_a_freshly_recomputed_budget_not_a_full_new_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Before this fix, the count-only query reused remaining_budget
    exactly as computed before the main query ran, handing it a full
    fresh timeout on top of whatever the main query itself had already
    spent, roughly doubling this tool's declared wall-clock bound in the
    worst case. The main query here sleeps for a real, measurable amount
    of time; the count query's timeout_s must be smaller than the main
    query's own timeout_s, not equal to it.
    """
    harness = _FakeHarness(
        responses=[
            (
                "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(g:Gene {id: $e_NCBIGene_672}) "
                "RETURN v"
            )
        ]
    )
    timeouts: dict[str, float] = {}

    def _fake_execute_cypher(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        if "count(*)" in cypher:
            timeouts["count"] = timeout_s
            return [{"total_count": "15310"}], 1
        timeouts["main"] = timeout_s
        time.sleep(0.2)  # a real, measurable delay inside the "graph call"
        return (
            [{"result": _agtype_vertex_text("SequenceVariant", "ClinVar:1", {})}] * 2,
            2,
        )

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute_cypher)

    await cypher_query(harness, _gene_lookup_input(row_limit=2))

    assert "main" in timeouts and "count" in timeouts
    assert timeouts["count"] < timeouts["main"], (
        f"count query timeout ({timeouts['count']:.3f}s) must be smaller "
        f"than the main query's ({timeouts['main']:.3f}s): the elapsed "
        "time the main query itself took must be subtracted before "
        "handing the count query its own budget, not reused unchanged"
    )


# ---------------------------------------------------------------------------
# Finding F-2.1-B11: the outer timeout message must not blame the graph
# for a delay that was actually generation latency.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_outer_timeout_message_does_not_blame_the_graph_for_generation_delay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The outer timeout fires while a plan-tier generation call is still
    in flight, well before any graph call was even attempted. The error
    message must not say the graph query itself was what exceeded the
    budget, since retrying "the graph" is the wrong next action when the
    graph was never reached; this is what made an earlier finding hard to
    diagnose.
    """
    monkeypatch.setattr(cypher_query_module, "CYPHER_QUERY_TIMEOUT_SECONDS", 0.05)
    harness = _FakeHarness(
        responses=["MATCH (g:Gene {id: $e_NCBIGene_672}) RETURN g"], delay=0.3
    )
    execute_calls: list[str] = []

    def _fake_execute_cypher(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        execute_calls.append(cypher)
        return [_raw_gene_row()], 1

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute_cypher)

    output = await cypher_query(harness, _gene_lookup_input())

    assert output.status == "error"
    assert execute_calls == [], "the graph was never reached; the delay was generation latency"
    assert "exceeded" in output.error
    assert "retry" in output.error
    assert "query_intent" in output.error or "query_class" in output.error
    assert not output.error.lower().startswith("graph query exceeded"), (
        "the message must not assert specifically that the graph query "
        f"was what exceeded the budget when the graph was never reached, got: {output.error!r}"
    )


# ---------------------------------------------------------------------------
# F-2.1-J4-03: deduplication must not be able to delete a distinct fact
#
# Filed as a coverage hole by the fourth judge, in these words: "no test
# anywhere covers J4-03. The dedup tests all use fixtures where the
# duplicate is genuinely the same record. The case where the dedup
# destroys distinct records, four edges sharing one stored source_url, is
# untested, which is why 879 green tests say nothing about it."
#
# The live premise gate covers this too, but it costs a real model call.
# This is the same property asserted as a pure function, so it runs in
# milliseconds on every suite and fails loudly if the key regresses.
# ---------------------------------------------------------------------------


def _row(curie: str, source_url: str, name: str) -> object:
    from system_03_search_agent.tools.cypher_schemas import CypherQueryRow

    return CypherQueryRow(
        node_or_edge_type="Disease",
        curie=curie,
        fields={"name": name},
        source_url=source_url,
        graph_snapshot_version="v1",
    )


def test_records_sharing_one_source_url_are_not_collapsed() -> None:
    """Four distinct diseases, one shared citation page, four rows out.

    This is BRCA1's real shape in the graph: all four of its
    `gene_associated_with_condition` edges carry the same stored
    `source_url`. Keying deduplication on that URL reported
    `row_count=1, total_available=1, truncated=False`, deleting three
    quarters of the answer while affirming that nothing was cut.

    A citation URL identifies a page, not a fact, and one NCBI page can be
    the cited source for many records. The key is the CURIE.
    """
    from system_03_search_agent.tools.cypher_query import _dedupe_by_cited_record

    shared = "https://www.ncbi.nlm.nih.gov/clinvar/?term=BRCA1"
    rows = [
        _row("MedGen:C0346153", shared, "MeSH"),
        _row("MedGen:C2676676", shared, "MONDO"),
        _row("MedGen:C3280442", shared, "MedGen"),
        _row("MedGen:C4554406", shared, "MedGen"),
    ]

    deduped = _dedupe_by_cited_record(rows)

    assert len(deduped) == 4, (
        "four distinct diseases sharing one citation page were collapsed to "
        f"{len(deduped)}. Silent deletion under a completeness claim."
    )
    assert [r.curie for r in deduped] == [r.curie for r in rows], (
        "order must be preserved so the result still reads as the graph "
        "returned it"
    )


def test_the_same_record_twice_is_still_collapsed() -> None:
    """The property F-2.1-C06 added, which must survive the J4-03 fix.

    An edge and its endpoint vertex can cite the same record twice per raw
    row, which halved the effective 20-citation budget. Repeats of one
    record still collapse; only distinct records are protected.
    """
    from system_03_search_agent.tools.cypher_query import _dedupe_by_cited_record

    url = "https://www.ncbi.nlm.nih.gov/medgen/C0346153"
    rows = [
        _row("MedGen:C0346153", url, "MeSH"),
        _row("MedGen:C0346153", url, "MeSH"),
    ]

    assert len(_dedupe_by_cited_record(rows)) == 1


# ---------------------------------------------------------------------------
# F-2.1-J4-01B and F-2.1-J5-01: the connectivity invariant
#
# Two rounds of the same lesson. First the invariant was "binds at least
# one caller entity", which a decoy binding defeated. Then the replacement
# claimed in its own comment that a WITH could not launder provenance,
# while the code never read WITH at all, and `WITH d AS x ... RETURN x`
# returned five arbitrary cited diseases for a question about BRCA1.
#
# Both directions are asserted here. A false reject means the user gets
# nothing, which is its own defect, so the legitimate shapes matter as
# much as the blocked ones.
# ---------------------------------------------------------------------------

_BINDINGS = {"e_NCBIGene_672": "NCBIGene:672", "e_NCBIGene_7157": "NCBIGene:7157"}

_DECOY_PREFIX = "MATCH (dc:Gene {id: $e_NCBIGene_672}) WITH dc "
_UNRELATED = "MATCH (g:Gene)-[:gene_associated_with_condition]->(d:Disease) "


@pytest.mark.parametrize(
    ("label", "cypher"),
    [
        ("plain decoy", _DECOY_PREFIX + _UNRELATED + "RETURN d"),
        ("WITH rename", _DECOY_PREFIX + _UNRELATED + "WITH d AS x RETURN x"),
        ("WITH property", _DECOY_PREFIX + _UNRELATED + "WITH d.id AS did RETURN did"),
        (
            "transitive rename",
            _DECOY_PREFIX + _UNRELATED + "WITH d AS x WITH x AS y RETURN y",
        ),
        (
            "comma cartesian",
            "MATCH (dc:Gene {id: $e_NCBIGene_672}), (d:Disease) RETURN d",
        ),
    ],
)
def test_a_result_not_connected_to_a_bound_entity_is_flagged(
    label: str, cypher: str
) -> None:
    """Every one of these returned real, cited records nobody asked for.

    The binding is present in all five, which is why presence was the
    wrong property. What has to hold is that the returned value traces
    back to an entity the caller supplied.
    """
    from system_03_search_agent.tools.cypher_query import _unanchored_returned_variables

    assert _unanchored_returned_variables(cypher, _BINDINGS), (
        f"{label} was accepted; it returns records unconnected to any bound "
        "entity, which is F-2.1-B01's failure class with a citation attached"
    )


@pytest.mark.parametrize(
    ("label", "cypher"),
    [
        (
            "direct pattern",
            (
                "MATCH (g:Gene {id: $e_NCBIGene_672})"
                "-[:gene_associated_with_condition]->(d:Disease) RETURN d"
            ),
        ),
        (
            "WHERE anchor",
            (
                "MATCH (g:Gene)-[:gene_associated_with_condition]->(d:Disease) "
                "WHERE g.id = $e_NCBIGene_672 RETURN d"
            ),
        ),
        (
            "IN list of params",
            (
                "MATCH (g:Gene)-[:gene_associated_with_condition]->(d:Disease) "
                "WHERE g.id IN [$e_NCBIGene_672, $e_NCBIGene_7157] RETURN g, d"
            ),
        ),
        (
            "aggregate",
            (
                "MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->"
                "(g:Gene {id: $e_NCBIGene_672}) RETURN count(v)"
            ),
        ),
        (
            "legitimate alias",
            (
                "MATCH (g:Gene {id: $e_NCBIGene_672})"
                "-[:gene_associated_with_condition]->(d:Disease) "
                "WITH d.id AS did RETURN did"
            ),
        ),
        ("property projection", "MATCH (g:Gene {id: $e_NCBIGene_672}) RETURN g.name"),
    ],
)
def test_a_legitimately_anchored_result_is_not_rejected(label: str, cypher: str) -> None:
    """The cost side, and F-2.1-J5-02 specifically.

    A first cut of this check rejected three legitimate aggregates because
    it only looked for parameters inside MATCH patterns, and a later one
    rejected `WHERE g.id IN [$p1, $p2]`, an ordinary multi-entity
    constraint. A query wrongly refused returns nothing to the user, which
    is a defect in its own right, not a safe default.
    """
    from system_03_search_agent.tools.cypher_query import _unanchored_returned_variables

    assert not _unanchored_returned_variables(cypher, _BINDINGS), (
        f"{label} is properly anchored and was rejected; a false refusal "
        "means the user gets no answer at all"
    )
