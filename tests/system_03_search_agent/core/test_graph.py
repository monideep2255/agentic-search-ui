"""Tests for the five-node LangGraph loop (T-2.0-07): node sequence,
per-node tier assignment, event schema validation on every emitted event
type, the stub-node non-fabrication check, the per-query-cap-triggered
early exit to `write`, and the daily-cap decline path.

No real model call is made anywhere in this file: `litellm.acompletion`
and `litellm.get_model_info` are monkeypatched on `harness_module`, the
same pattern `test_harness.py` already uses, so `Harness.call_tier`'s real
code path (tier resolution, cost accounting, the retry/timeout wrapper) is
genuinely exercised end to end through the graph.

The two daily-cap checks (`cost_control.check_user_daily_query_cap`,
`cost_control.check_system_daily_cost_cap`) are monkeypatched to no-ops by
default in every test via an autouse fixture, since their own DB-backed
behavior already has a full test suite in `test_cost_control.py`; this
file's job is the graph's routing and event-emission logic, not
re-proving cost_control's counting. A `no_op` default means no test here
needs a live database connection at all: `guardrail_node`'s
`session_scope()` call still constructs a `Session` object (lazily bound,
no connection attempt), but the monkeypatched check functions never issue
a query against it.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.contracts.events import PAYLOAD_MODEL_BY_TYPE, Event, ToolCall
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.core.graph import compiled_graph
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness.coordinator_worker import (
    ToolExecutionResult,
    coordinator_worker_execute,
)
from system_03_search_agent.harness.cost_control import (
    PER_QUERY_CAP_PARTIAL_RESULT_NOTE,
    QueryCapExceededError,
    SystemDailyCostCapExceededError,
    UserDailyQueryCapExceededError,
)

_GUARD_MODEL = "test-provider/guard-model"
_PLAN_MODEL = "test-provider/plan-model"
_SYNTH_MODEL = "test-provider/synth-model"


def _fake_response(content: str = "ok", prompt_tokens: int = 10, completion_tokens: int = 5):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", _GUARD_MODEL)
    monkeypatch.setenv("PLAN_MODEL", _PLAN_MODEL)
    monkeypatch.setenv("SYNTH_MODEL", _SYNTH_MODEL)
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("PER_USER_DAILY_QUERY_CAP", "100")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")
    monkeypatch.setenv("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")


@pytest.fixture(autouse=True)
def _no_op_daily_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default both daily-cap checks to no-ops; see the module docstring.

    Both are plain sync functions (never awaited by the graph), so a
    plain callable stands in for them directly; no DB session is ever
    actually queried by these stand-ins.
    """

    def _user_check(session, user_id, **kwargs):
        return None

    def _system_check(session, **kwargs):
        return None

    monkeypatch.setattr(cost_control, "check_user_daily_query_cap", _user_check)
    monkeypatch.setattr(cost_control, "check_system_daily_cost_cap", _system_check)


@pytest.fixture(autouse=True)
def _mock_litellm(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock_acompletion = AsyncMock(return_value=_fake_response())
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )
    return mock_acompletion


def _valid_query(**overrides: object) -> Query:
    """The shared query fixture. Its default text ("hello") is
    deliberately one of `graph_module._NO_TOOL_QUERY_TEXTS` (T-2.1-08),
    so plan_node selects no tool and act_node's dispatch loop never runs,
    leaving every pre-existing stub-era test in this file (event
    sequence, tier assignment, cap handling, daily-cap declines) exactly
    as it behaved before real tool selection landed: no extra litellm
    call, no extra event, no live graph dependency. Tests that need a
    real cypher_query dispatch override `text=` to a substantive query
    explicitly (see the "plan selects cypher_query" / "act executes it"
    tests below).
    """
    base: dict[str, object] = {
        "text": "hello",
        "session_id": "session-1",
        "trace_id": "trace-graph-1",
        "user_id": None,
        "audience_depth": "researcher",
    }
    base.update(overrides)
    return Query(**base)


def _valid_context(**overrides: object) -> RequestContext:
    base: dict[str, object] = {
        "surface": "web_ui",
        "session_memory": None,
        "operator_mode": False,
    }
    base.update(overrides)
    return RequestContext(**base)


async def _run_graph(query: Query, context: RequestContext) -> list[Event]:
    """Invoke the compiled graph directly (not via `core.run.run()`).

    Wrapped in `tracing_context(enabled=False)` for the same reason
    `core.run.run()` itself is (see its module docstring): this repo's
    `.env` sets `LANGCHAIN_TRACING_V2=true` ahead of the real phase
    5.0/5.1 tracing integration, and invoking a compiled LangGraph graph
    without disabling tracing makes a real, noisy, failing outbound call
    to LangSmith on every test.
    """
    from langsmith.run_helpers import tracing_context

    from system_03_search_agent.harness.harness import Harness

    harness = Harness(trace_id=query.trace_id)
    initial_state = {
        "query": query,
        "context": context,
        "harness": harness,
        "seq": 0,
        "events": [],
        "start_monotonic": time.monotonic(),
    }
    with tracing_context(enabled=False):
        final_state = await compiled_graph.ainvoke(initial_state)
    return list(final_state["events"])


# ---------------------------------------------------------------------------
# Graph structure: five nodes, fixed names.
# ---------------------------------------------------------------------------


def test_compiled_graph_has_the_five_named_nodes() -> None:
    node_names = set(compiled_graph.get_graph().nodes.keys())
    for expected in ("guardrail", "think", "plan", "act", "write"):
        assert expected in node_names


# ---------------------------------------------------------------------------
# Happy path: full sequence, one event per expected type, in order.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_emits_the_expected_event_type_sequence() -> None:
    events = await _run_graph(_valid_query(), _valid_context())
    types = [event.type for event in events]

    assert types == [
        "guard",
        "cost",
        "think",
        "cost",
        "plan",
        "cost",
        "cost",
        "done",
    ]


@pytest.mark.asyncio
async def test_happy_path_done_event_is_the_last_event() -> None:
    events = await _run_graph(_valid_query(), _valid_context())
    assert events[-1].type == "done"


@pytest.mark.asyncio
async def test_every_emitted_event_payload_is_schema_valid() -> None:
    events = await _run_graph(_valid_query(), _valid_context())
    assert len(events) > 0
    for event in events:
        payload_model = PAYLOAD_MODEL_BY_TYPE[event.type]
        payload_model.model_validate(event.payload)  # raises on a bad shape


@pytest.mark.asyncio
async def test_seq_is_monotonic_starting_at_zero_with_no_repeats() -> None:
    events = await _run_graph(_valid_query(), _valid_context())
    seqs = [event.seq for event in events]
    assert seqs[0] == 0
    assert seqs == sorted(seqs)
    assert len(seqs) == len(set(seqs))


@pytest.mark.asyncio
async def test_trace_id_propagates_to_every_event() -> None:
    query = _valid_query(trace_id="trace-graph-xyz")
    events = await _run_graph(query, _valid_context())
    for event in events:
        assert event.trace_id == "trace-graph-xyz"


# ---------------------------------------------------------------------------
# Per-node tier assignment: guardrail/think -> guard, plan -> plan,
# write -> synth (Section 3.2's step-to-tier table).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guardrail_and_think_call_the_guard_tier_model(
    _mock_litellm: AsyncMock,
) -> None:
    await _run_graph(_valid_query(), _valid_context())
    guard_tier_calls = [
        call for call in _mock_litellm.call_args_list if call.kwargs["model"] == f"openrouter/{_GUARD_MODEL}"
    ]
    assert len(guard_tier_calls) == 2  # guardrail + think


@pytest.mark.asyncio
async def test_plan_calls_the_plan_tier_model(_mock_litellm: AsyncMock) -> None:
    """No-tool-selected path: plan_node's own dispatch is the only
    plan-tier call, since act_node never reaches cypher_query. See
    test_plan_calls_the_plan_tier_model_when_a_tool_runs below for the
    tool path, restored per the judge's T-2.1 rework finding.
    """
    await _run_graph(_valid_query(), _valid_context())
    plan_tier_calls = [
        call for call in _mock_litellm.call_args_list if call.kwargs["model"] == f"openrouter/{_PLAN_MODEL}"
    ]
    assert len(plan_tier_calls) == 1


@pytest.mark.asyncio
async def test_plan_calls_the_plan_tier_model_when_a_tool_runs(_mock_litellm: AsyncMock) -> None:
    """T-2.1 rework: the judge ruled the pre-existing version of this test
    a weakened verify surface once commit 7c5b8d6 pinned the shared query
    fixture to the no-tool path ("hello"), where exactly one plan-tier
    call was always true and the assertion never exercised the tool path
    the phase exists to build. On the tool path, three calls resolve to
    the plan tier: plan_node's own dispatch, plus cypher_query's two
    internal generate_cypher attempts (the generic "ok" mock response is
    not recoverable Cypher, so both the initial attempt and the one
    repair retry fire; see test_act_executes_the_selected_cypher_query_call's
    docstring for the same mechanics). F-06 means neither of those two
    generate_cypher calls carries the stable prefix, a documented,
    out-of-file-scope gap this pass does not close (see
    test_every_model_call_carries_the_stable_prefix_as_its_leading_message_when_a_tool_runs).
    """
    query = _valid_query(text=_GRAPH_ANSWERABLE_QUERY_TEXT)
    await _run_graph(query, _valid_context())
    plan_tier_calls = [
        call
        for call in _mock_litellm.call_args_list
        if call.kwargs["model"] == f"openrouter/{_PLAN_MODEL}"
    ]
    assert len(plan_tier_calls) == 3


@pytest.mark.asyncio
async def test_write_calls_the_synth_tier_model(_mock_litellm: AsyncMock) -> None:
    await _run_graph(_valid_query(), _valid_context())
    synth_tier_calls = [
        call for call in _mock_litellm.call_args_list if call.kwargs["model"] == f"openrouter/{_SYNTH_MODEL}"
    ]
    assert len(synth_tier_calls) == 1


@pytest.mark.asyncio
async def test_every_model_call_carries_the_stable_prefix_as_its_leading_message(
    _mock_litellm: AsyncMock,
) -> None:
    """F-2.0-03 fix: build_stable_prefix() has a real caller, not zero.

    No-tool-selected path: all four calls (guardrail, think, plan, write)
    reach litellm.acompletion with graph_module._STABLE_PREFIX prepended
    as a leading system-role message, proving the prompt-cache scaffold
    T-2.0-06 built is actually wired into the loop, not merely
    unit-tested in isolation. See the `_when_a_tool_runs` sibling below
    for the tool path, restored per the judge's T-2.1 rework finding.
    """
    await _run_graph(_valid_query(), _valid_context())
    assert _mock_litellm.call_count == 4
    for call in _mock_litellm.call_args_list:
        leading_message = call.kwargs["messages"][0]
        assert leading_message["role"] == "system"
        assert leading_message["content"] == graph_module._STABLE_PREFIX


@pytest.mark.asyncio
async def test_every_model_call_carries_the_stable_prefix_as_its_leading_message_when_a_tool_runs(
    _mock_litellm: AsyncMock,
) -> None:
    """T-2.1 rework: commit 7c5b8d6's replacement for this test filtered
    `_mock_litellm.call_args_list` down to only the calls that already
    carried the prefix, then asserted the filtered count was 4, a shape
    structurally incapable of failing regardless of how many calls fired
    in total or how many of them lacked the prefix. It concealed exactly
    the gap F-06 documents: 2 of the 6 calls a tool-path query fires
    (cypher_query's two internal generate_cypher attempts) never carry
    the prefix at all, since generate_cypher does not accept a
    cache_prefix parameter (a fix that belongs in cypher_generation.py,
    out of this file's scope). This restores a real assertion: the total
    call count (6) is checked first, then exactly 4 of those 6, the
    node-level calls (guardrail, think, plan, write), are asserted to
    carry the prefix; the other 2 are the documented, known gap, not
    silently absorbed by a filter.
    """
    query = _valid_query(text=_GRAPH_ANSWERABLE_QUERY_TEXT)
    await _run_graph(query, _valid_context())

    assert _mock_litellm.call_count == 6
    prefixed_calls = [
        call
        for call in _mock_litellm.call_args_list
        if call.kwargs["messages"][0].get("content") == graph_module._STABLE_PREFIX
    ]
    assert len(prefixed_calls) == 4
    for call in prefixed_calls:
        assert call.kwargs["messages"][0]["role"] == "system"


@pytest.mark.asyncio
async def test_exactly_four_model_calls_fire_on_the_happy_path(
    _mock_litellm: AsyncMock,
) -> None:
    """No-tool-selected path: guardrail, think, plan, write each call_tier
    once; act calls no model since no tool was selected. See
    test_six_model_calls_fire_when_a_tool_runs below for the tool path,
    restored per the judge's T-2.1 rework finding: this assertion was
    "now only true on the no-tool path" with no sibling covering the
    other one.
    """
    await _run_graph(_valid_query(), _valid_context())
    assert _mock_litellm.call_count == 4


@pytest.mark.asyncio
async def test_six_model_calls_fire_when_a_tool_runs(_mock_litellm: AsyncMock) -> None:
    """T-2.1 rework: on the tool path, the four node-level calls
    (guardrail, think, plan, write) plus cypher_query's two internal
    generate_cypher attempts (F-06's documented gap) total six, not four.
    """
    query = _valid_query(text=_GRAPH_ANSWERABLE_QUERY_TEXT)
    await _run_graph(query, _valid_context())
    assert _mock_litellm.call_count == 6


# ---------------------------------------------------------------------------
# Stub-node non-fabrication: no citation or trust_signal event, ever, at
# this phase (no real grounding exists yet to justify one).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_citation_or_trust_signal_event_is_ever_fabricated() -> None:
    events = await _run_graph(_valid_query(), _valid_context())
    types = {event.type for event in events}
    assert "citation" not in types
    assert "trust_signal" not in types


@pytest.mark.asyncio
async def test_think_event_narrative_documents_itself_as_a_stub() -> None:
    events = await _run_graph(_valid_query(), _valid_context())
    think_event = next(event for event in events if event.type == "think")
    assert think_event.payload["query_class"] == "lookup"
    assert "stub" in think_event.payload["narrative"].lower()


@pytest.mark.asyncio
async def test_plan_event_tool_calls_is_empty_for_a_no_tool_query() -> None:
    """A query with no graph-answerable content (T-2.1-08's
    `_NO_TOOL_QUERY_TEXTS`) selects nothing; this is the real,
    deterministic outcome now, not the phase 2.0 always-empty stub."""
    events = await _run_graph(_valid_query(), _valid_context())
    plan_event = next(event for event in events if event.type == "plan")
    assert plan_event.payload["tool_calls"] == []


@pytest.mark.asyncio
async def test_done_event_trust_outcome_is_answer_on_the_happy_path() -> None:
    """No-tool-selected path: no factual graph claim was attempted, so
    there is nothing to refuse. See
    test_done_event_trust_outcome_is_refuse_when_the_tool_call_errors
    below for the path this test stopped covering (findings A5/F-02),
    restored per the judge's T-2.1 rework finding.
    """
    events = await _run_graph(_valid_query(), _valid_context())
    done_event = next(event for event in events if event.type == "done")
    assert done_event.payload["trust_outcome"] == "answer"
    assert done_event.payload["total_tool_calls"] == 0


@pytest.mark.asyncio
async def test_done_event_trust_outcome_is_refuse_when_the_tool_call_errors() -> None:
    """T-2.1 rework, findings A5/F-02: before this fix, write_node emitted
    trust_outcome="answer" unconditionally on its success path, so a tool
    call that hard-errored before ever reaching the graph still reported
    "answer" (verified by both the judge and an independent adversary).
    The generic "ok" mock response cannot be parsed as Cypher (see
    test_act_executes_the_selected_cypher_query_call's docstring), so
    cypher_query returns status="error" here, and the query must
    terminate as a refusal, never a fabricated answer, and must never
    emit a citation for a row that was never found.
    """
    query = _valid_query(text=_GRAPH_ANSWERABLE_QUERY_TEXT)
    events = await _run_graph(query, _valid_context())
    done_event = events[-1]
    assert done_event.type == "done"
    assert done_event.payload["trust_outcome"] == "refuse"
    assert done_event.payload["total_tool_calls"] == 1

    citation_events = [event for event in events if event.type == "citation"]
    assert citation_events == [], "an errored tool call must never produce a citation"


@pytest.mark.asyncio
async def test_done_event_trust_outcome_is_answer_with_a_real_citation_when_the_tool_call_succeeds(
    monkeypatch: pytest.MonkeyPatch, _mock_litellm: AsyncMock
) -> None:
    """T-2.1 rework, findings A3/A5/F-02, exercised without the live graph
    tunnel (test_cypher_query_e2e.py proves the real execute_cypher path
    end to end). A real target entity (BRCA1 -> NCBIGene:672, via
    graph_module._extract_target_entities, A3's fix) reaches
    cypher_query; the mocked model response is valid, already-parameterized
    Cypher the validator accepts on the first attempt (no repair retry
    needed); execute_cypher (the one call mocked here) returns one real
    row. write_node must emit a citation for that row and
    trust_outcome="answer", never the old stub "answer" that required no
    evidence at all.
    """
    valid_cypher = "MATCH (g:Gene {id: $e_NCBIGene_672}) RETURN g"
    monkeypatch.setattr(_mock_litellm, "return_value", _fake_response(content=valid_cypher))

    def _fake_execute_cypher(cypher: str, *, params: dict, **_kwargs: object) -> tuple[list[dict], int]:
        assert params == {"e_NCBIGene_672": "NCBIGene:672"}
        # One placeholder raw AGE row; its content is irrelevant since
        # `to_output_rows` (the agtype-parsing shaping step, a different
        # builder's module) is mocked below to return the already-shaped
        # row this test needs, so this stays independent of that
        # module's own internal wire-format choices.
        return ([{"c0": "placeholder-raw-agtype-text"}], 1)

    def _fake_to_output_rows(
        raw_row: dict, snapshot_version: str, derived_source_curie: str | None = None
    ) -> list[dict]:
        return [
            {
                "node_or_edge_type": "Gene",
                "curie": "NCBIGene:672",
                "fields": {"name": "BRCA1 DNA repair associated"},
                "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
                "graph_snapshot_version": snapshot_version,
            }
        ]

    monkeypatch.setattr(
        "system_03_search_agent.tools.cypher_query.execute_cypher", _fake_execute_cypher
    )
    monkeypatch.setattr(
        "system_03_search_agent.tools.cypher_query.to_output_rows", _fake_to_output_rows
    )

    query = _valid_query(text=_GRAPH_ANSWERABLE_QUERY_TEXT)
    events = await _run_graph(query, _valid_context())

    citation_events = [event for event in events if event.type == "citation"]
    assert len(citation_events) == 1
    assert citation_events[0].payload["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/672"
    assert citation_events[0].payload["source"] == "NCBIGene"
    assert citation_events[0].payload["layer"] == "layer_1_graph"

    done_event = events[-1]
    assert done_event.type == "done"
    assert done_event.payload["trust_outcome"] == "answer"
    assert done_event.payload["total_tool_calls"] == 1


# ---------------------------------------------------------------------------
# F-2.1-10/F-2.1-11: `Finding.truncated` had no reader in `core/`, so a
# `Finding` cut by coordinator_worker's 50,000-byte ceiling reached
# write_node indistinguishable from a complete one, and a cut that erased
# every citeable row surfaced as an identical, silent refusal to a
# genuinely empty tool result. These tests build a `Finding` through the
# real `coordinator_worker_execute` capping pipeline (not a hand-set
# `truncated=True` flag) so the byte ceiling genuinely fires, then call
# `write_node` directly against a minimal state, the same node function
# `_run_graph` drives end to end elsewhere in this file.
# ---------------------------------------------------------------------------


def _citeable_row(index: int) -> dict[str, object]:
    """One graph row shaped so `_citation_for_row` can cite it: a real
    `source_url`, `curie`, and a 30-property `fields` dict at the F-03
    per-field cap (500 chars each), matching the coordinator_worker.py
    test suite's own "composed rows past per-field caps" fixture shape.
    """
    return {
        "node_or_edge_type": "Gene",
        "curie": "NCBIGene:672",
        "fields": {f"prop_{i}": "v" * 500 for i in range(30)},
        "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
        "graph_snapshot_version": f"v{index}",
    }


async def _truncated_ok_finding(row_count: int) -> object:
    """Run `row_count` copies of `_citeable_row` through the real
    `coordinator_worker_execute` structured pass-through path and return
    the resulting `Finding`. `row_count` controls whether the byte
    ceiling still leaves a citeable row (a smaller count) or erases every
    row (a large enough count that even one already-capped row plus the
    rest of the payload cannot fit)."""
    harness = harness_module.Harness(trace_id="test-trace-truncation")
    call = ToolCall(tool="cypher_query", call_id="call-truncation", layer="layer_1_graph")
    structured_fields = {
        "status": "ok",
        "row_count": row_count,
        "total_available": row_count,
        "truncated": False,
        "rows": [_citeable_row(i) for i in range(row_count)],
        "error": None,
    }
    result = ToolExecutionResult(contains_untrusted_free_text=False, structured_fields=structured_fields)
    findings = await coordinator_worker_execute(harness, [call], [result])
    return findings[0]


def _write_state(query: Query, findings: list[object]) -> dict[str, object]:
    harness = harness_module.Harness(trace_id=query.trace_id)
    return {
        "query": query,
        "harness": harness,
        "seq": 0,
        "start_monotonic": time.monotonic(),
        "findings": findings,
        "findings_count": len(findings),
    }


@pytest.mark.asyncio
async def test_truncated_ok_finding_still_answers_but_acknowledges_the_cut(
    _mock_litellm: AsyncMock,
) -> None:
    """F-2.1-10: confirmed failing against the pre-fix code, since nothing
    read `Finding.truncated` at all, so write_node emitted only
    citation/cost/done with no acknowledgement of the cut, exactly as if
    the byte ceiling had never fired. 100 citeable rows, each already
    within every per-field cap, still compose past the 50,000-byte total
    ceiling (mirrors coordinator_worker.py's own
    test_total_size_ceiling_shrinks_composed_rows_past_per_field_caps),
    so `truncated=True` while a handful of rows survive. The cite-or-
    refuse gate is satisfied (a real, citeable row exists) so the query
    must still answer, but the cut must be acknowledged, not silently
    dropped.
    """
    finding = await _truncated_ok_finding(row_count=100)
    assert finding.truncated is True, "the byte ceiling must actually have fired for this fixture"
    assert 0 < len(finding.structured_fields["rows"]) < 100, (
        "some rows must survive the cap for this to be the answer-and-acknowledge case"
    )

    query = _valid_query(text=_GRAPH_ANSWERABLE_QUERY_TEXT)
    result = await graph_module.write_node(_write_state(query, [finding]))
    events = result["events"]

    done_event = next(event for event in events if event.type == "done")
    assert done_event.payload["trust_outcome"] == "answer"

    citation_events = [event for event in events if event.type == "citation"]
    assert len(citation_events) >= 1

    token_events = [event for event in events if event.type == "token"]
    assert any("truncat" in event.payload["text"].lower() for event in token_events), (
        "a truncated-but-successful Finding answered with no acknowledgement of the cut"
    )


@pytest.mark.asyncio
async def test_truncated_to_zero_rows_refuses_but_is_distinguishable_from_genuine_empty(
    _mock_litellm: AsyncMock,
) -> None:
    """F-2.1-11: confirmed failing against the pre-fix code. A single row
    whose bulk lives in dict-key breadth rather than string length or list
    length (30 outer keys x 30 inner keys x 600 chars) cannot be shrunk by
    per-field string capping alone, and is still too large to keep even
    one copy of once every list in the structure is forced to hold at
    most one item, so the byte-ceiling binary search bottoms out at zero:
    `status` stays `"ok"` but `rows` becomes empty. Before this fix,
    write_node's `done` event for this case was byte-for-byte identical to
    a genuinely empty tool result (no citations, `trust_outcome="refuse"`,
    no other event), so a caller could not tell "nothing matched" from
    "something matched but was cut away". The cite-or-refuse gate must
    still refuse here (a truncated Finding earns no exemption), but the
    refusal must carry a distinguishing signal a genuine empty result
    never emits.
    """

    def _oversized_row() -> dict[str, object]:
        return {
            "node_or_edge_type": "Gene",
            "curie": "NCBIGene:672",
            "fields": {
                f"outer_{i}": {f"inner_{j}": "x" * 600 for j in range(30)} for i in range(30)
            },
            "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
            "graph_snapshot_version": "v1",
        }

    harness = harness_module.Harness(trace_id="test-trace-truncation-zero")
    call = ToolCall(tool="cypher_query", call_id="call-truncation-zero", layer="layer_1_graph")
    structured_fields = {
        "status": "ok",
        "row_count": 1,
        "total_available": 1,
        "truncated": False,
        "rows": [_oversized_row()],
        "error": None,
    }
    result = ToolExecutionResult(contains_untrusted_free_text=False, structured_fields=structured_fields)
    findings = await coordinator_worker_execute(harness, [call], [result])
    finding = findings[0]
    assert finding.truncated is True
    assert finding.structured_fields["status"] == "ok"
    assert finding.structured_fields["rows"] == [], (
        "this fixture must genuinely exceed the byte ceiling even at one row"
    )

    query = _valid_query(text=_GRAPH_ANSWERABLE_QUERY_TEXT)
    write_result = await graph_module.write_node(_write_state(query, [finding]))
    events = write_result["events"]

    done_event = next(event for event in events if event.type == "done")
    assert done_event.payload["trust_outcome"] == "refuse", (
        "zero citeable rows must still refuse; truncation earns no exemption from cite-or-refuse"
    )
    assert [event for event in events if event.type == "citation"] == []

    error_events = [event for event in events if event.type == "error"]
    assert len(error_events) == 1, (
        "a refusal caused by truncation must carry a distinguishing signal a genuinely "
        "empty tool result never emits"
    )
    assert error_events[0].payload["fatal"] is False
    assert "cut" in error_events[0].payload["message"].lower() or (
        "truncat" in error_events[0].payload["message"].lower()
    )


# ---------------------------------------------------------------------------
# act: proves the coordinator-worker integration point is actually wired.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_act_node_calls_coordinator_worker_execute_with_empty_lists_for_a_no_tool_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no tool selected (the default "hello" query), act_node still
    calls coordinator_worker_execute with paired empty lists, proving the
    integration point remains wired even when there is nothing to fan
    out over.
    """
    calls: list[tuple] = []
    original = graph_module.coordinator_worker_execute

    async def _spy(harness, tool_calls, results):
        calls.append((tool_calls, results))
        return await original(harness, tool_calls, results)

    monkeypatch.setattr(graph_module, "coordinator_worker_execute", _spy)
    await _run_graph(_valid_query(), _valid_context())

    assert calls == [([], [])]


# ---------------------------------------------------------------------------
# T-2.1-08: real cypher_query selection and dispatch.
# ---------------------------------------------------------------------------

_GRAPH_ANSWERABLE_QUERY_TEXT = "What gene is associated with BRCA1?"


@pytest.mark.asyncio
async def test_plan_selects_cypher_query_for_a_graph_answerable_query() -> None:
    query = _valid_query(text=_GRAPH_ANSWERABLE_QUERY_TEXT)
    events = await _run_graph(query, _valid_context())

    plan_event = next(event for event in events if event.type == "plan")
    tool_calls = plan_event.payload["tool_calls"]
    assert len(tool_calls) == 1
    assert tool_calls[0]["tool"] == "cypher_query"
    assert tool_calls[0]["layer"] == "layer_1_graph"


@pytest.mark.asyncio
async def test_act_executes_the_selected_cypher_query_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Act dispatches the real tool call plan selected: cypher_generation's
    plan-tier call fires (via the mocked litellm), the mocked response
    ("ok", from `_fake_response`) is not recoverable Cypher, so
    cypher_query's internal retry-then-error path runs and act still
    completes, passing exactly one paired (tool_call, result) into
    coordinator_worker_execute.
    """
    calls: list[tuple] = []
    original = graph_module.coordinator_worker_execute

    async def _spy(harness, tool_calls, results):
        calls.append((tool_calls, results))
        return await original(harness, tool_calls, results)

    monkeypatch.setattr(graph_module, "coordinator_worker_execute", _spy)

    query = _valid_query(text=_GRAPH_ANSWERABLE_QUERY_TEXT)
    events = await _run_graph(query, _valid_context())

    assert len(calls) == 1
    tool_calls, results = calls[0]
    assert len(tool_calls) == 1
    assert len(results) == 1
    assert results[0].contains_untrusted_free_text is False  # a Cypher row is structured data

    done_event = events[-1]
    assert done_event.type == "done"


@pytest.mark.asyncio
async def test_stable_prefix_still_reaches_every_graph_node_call_when_a_tool_runs(
    _mock_litellm: AsyncMock,
) -> None:
    """Guards the LEARNINGS row 28 regression for the scenario that
    actually exercises a tool, not only the no-tool-selected happy path:
    the four established graph.py node calls (guardrail, think, plan,
    write) must each still carry graph_module._STABLE_PREFIX as their
    leading message, even though Act's cypher_query dispatch issues
    additional plan-tier calls of its own (cypher_generation.
    generate_cypher does not accept a cache_prefix, by that module's own
    design, so those calls are expected to lack the leading system
    message; this test asserts the count that DOES carry it, not the
    total call count).
    """
    query = _valid_query(text=_GRAPH_ANSWERABLE_QUERY_TEXT)
    await _run_graph(query, _valid_context())

    node_level_calls = [
        call
        for call in _mock_litellm.call_args_list
        if call.kwargs["messages"][0].get("content") == graph_module._STABLE_PREFIX
    ]
    assert len(node_level_calls) == 4


@pytest.mark.asyncio
async def test_cost_cap_breach_during_act_ships_partial_result_without_calling_the_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Act's own pre-dispatch cost-cap check (the second "plan"-tier check
    for this query: plan_node's own dispatch is the first) breaches the
    cap, so cypher_query is never called at all, and the query still
    ships a partial result via write_node's existing cap-hit handling.
    """
    real_check = cost_control.check_per_query_cap
    plan_tier_check_count = {"n": 0}

    def _raise_on_second_plan_tier_check(harness, trace_id, tier, **kwargs):
        if tier == "plan":
            plan_tier_check_count["n"] += 1
            if plan_tier_check_count["n"] == 2:
                raise QueryCapExceededError(
                    "forced for test",
                    query_cost_usd=0.05,
                    query_cap_usd=0.05,
                    estimated_call_cost_usd=0.01,
                )
        return real_check(harness, trace_id, tier, **kwargs)

    monkeypatch.setattr(cost_control, "check_per_query_cap", _raise_on_second_plan_tier_check)

    query = _valid_query(text=_GRAPH_ANSWERABLE_QUERY_TEXT)
    events = await _run_graph(query, _valid_context())
    types = [event.type for event in events]

    assert "plan" in types  # plan_node's own dispatch succeeded and its event fired
    assert types[-2:] == ["token", "done"]
    assert events[-1].payload["trust_outcome"] == "flag"

    token_event = next(event for event in events if event.type == "token")
    assert token_event.payload["text"] == PER_QUERY_CAP_PARTIAL_RESULT_NOTE


# ---------------------------------------------------------------------------
# Per-query cap hit: short-circuits straight to write, never reaches act.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_per_query_cap_hit_on_plan_short_circuits_to_write_without_reaching_act(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_check = cost_control.check_per_query_cap

    def _raise_on_plan(harness, trace_id, tier, **kwargs):
        if tier == "plan":
            raise QueryCapExceededError(
                "forced for test", query_cost_usd=0.05, query_cap_usd=0.05,
                estimated_call_cost_usd=0.01,
            )
        return real_check(harness, trace_id, tier, **kwargs)

    monkeypatch.setattr(cost_control, "check_per_query_cap", _raise_on_plan)

    act_calls: list[object] = []
    original_act = graph_module.coordinator_worker_execute

    async def _spy_act(harness, tool_calls, results):
        act_calls.append(True)
        return await original_act(harness, tool_calls, results)

    monkeypatch.setattr(graph_module, "coordinator_worker_execute", _spy_act)

    events = await _run_graph(_valid_query(), _valid_context())
    types = [event.type for event in events]

    assert act_calls == []  # act was never reached
    assert "plan" not in types  # plan's own event never emitted; it raised first
    assert types[-2:] == ["token", "done"]

    token_event = next(event for event in events if event.type == "token")
    assert token_event.payload["text"] == PER_QUERY_CAP_PARTIAL_RESULT_NOTE

    done_event = events[-1]
    assert done_event.payload["trust_outcome"] == "flag"


@pytest.mark.asyncio
async def test_per_query_cap_hit_at_write_itself_still_ships_partial_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_check = cost_control.check_per_query_cap

    def _raise_on_write(harness, trace_id, tier, **kwargs):
        if tier == "synth":
            raise QueryCapExceededError(
                "forced for test", query_cost_usd=0.05, query_cap_usd=0.05,
                estimated_call_cost_usd=0.01,
            )
        return real_check(harness, trace_id, tier, **kwargs)

    monkeypatch.setattr(cost_control, "check_per_query_cap", _raise_on_write)

    events = await _run_graph(_valid_query(), _valid_context())
    types = [event.type for event in events]

    # guardrail, think, and plan all ran normally (their own tiers were
    # never "synth", so _raise_on_write let them through); only write's
    # own synth call hit the forced cap.
    assert "guard" in types
    assert "think" in types
    assert "plan" in types
    assert types[-2:] == ["token", "done"]
    assert events[-1].payload["trust_outcome"] == "flag"


# ---------------------------------------------------------------------------
# A non-cap HarnessCallError (a per-step timeout or classified call
# failure) also short-circuits to write, but as a refusal, not a partial
# note, since Write cannot honestly synthesize without a working step
# ahead of it.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_step_failure_on_think_routes_to_write_as_a_refusal(
    monkeypatch: pytest.MonkeyPatch, _mock_litellm: AsyncMock
) -> None:
    call_count = {"n": 0}

    async def _fail_second_call(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:  # the think node's call
            raise RuntimeError("simulated unexpected model failure")
        return _fake_response()

    monkeypatch.setattr(_mock_litellm, "side_effect", _fail_second_call)

    act_calls: list[object] = []
    original_act = graph_module.coordinator_worker_execute

    async def _spy_act(harness, tool_calls, results):
        act_calls.append(True)
        return await original_act(harness, tool_calls, results)

    monkeypatch.setattr(graph_module, "coordinator_worker_execute", _spy_act)

    events = await _run_graph(_valid_query(), _valid_context())
    types = [event.type for event in events]

    assert act_calls == []
    assert "plan" not in types
    assert types[-2:] == ["error", "done"]
    error_event = next(event for event in events if event.type == "error")
    assert error_event.payload["scope"] == "step"
    assert error_event.payload["error_class"] == "unexpected"
    done_event = events[-1]
    assert done_event.payload["trust_outcome"] == "refuse"

    # F-2.0-12 (adversary, confirmed low, 2026-07-28): the resolved model
    # id must never reach the end-user-visible error event, even though
    # HarnessCallError's own internal message deliberately includes it.
    assert _GUARD_MODEL not in error_event.payload["message"]
    assert _GUARD_MODEL not in error_event.payload["source"]


# ---------------------------------------------------------------------------
# Daily caps: declined before any per-query model call fires at all.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_daily_cap_decline_stops_before_any_model_call(
    monkeypatch: pytest.MonkeyPatch, _mock_litellm: AsyncMock
) -> None:
    def _raise_system_cap(session, **kwargs):
        raise SystemDailyCostCapExceededError(cost_control.SYSTEM_DAILY_CAP_DECLINE_MESSAGE)

    monkeypatch.setattr(cost_control, "check_system_daily_cost_cap", _raise_system_cap)

    events = await _run_graph(_valid_query(), _valid_context())

    assert [event.type for event in events] == ["error", "done"]
    assert _mock_litellm.call_count == 0
    assert events[-1].payload["trust_outcome"] == "refuse"
    assert events[0].payload["source"] == "cost_control.check_system_daily_cost_cap"


@pytest.mark.asyncio
async def test_user_daily_cap_decline_stops_before_any_model_call(
    monkeypatch: pytest.MonkeyPatch, _mock_litellm: AsyncMock
) -> None:
    def _raise_user_cap(session, user_id, **kwargs):
        raise UserDailyQueryCapExceededError(
            "forced for test", count=100, cap=100, reset_at=datetime.now(UTC)
        )

    monkeypatch.setattr(cost_control, "check_user_daily_query_cap", _raise_user_cap)

    query = _valid_query(user_id=str(uuid.uuid4()))
    events = await _run_graph(query, _valid_context())

    assert [event.type for event in events] == ["error", "done"]
    assert _mock_litellm.call_count == 0
    assert events[0].payload["source"] == "cost_control.check_user_daily_query_cap"


@pytest.mark.asyncio
async def test_none_user_id_skips_the_per_user_check_but_still_runs_system_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_check_called = {"value": False}
    system_check_called = {"value": False}

    def _user_check(session, user_id, **kwargs):
        user_check_called["value"] = True

    def _system_check(session, **kwargs):
        system_check_called["value"] = True

    monkeypatch.setattr(cost_control, "check_user_daily_query_cap", _user_check)
    monkeypatch.setattr(cost_control, "check_system_daily_cost_cap", _system_check)

    query = _valid_query(user_id=None)
    events = await _run_graph(query, _valid_context())

    assert user_check_called["value"] is False
    assert system_check_called["value"] is True
    assert events[0].type == "guard"  # the graph proceeded normally


@pytest.mark.asyncio
async def test_malformed_user_id_declines_gracefully_instead_of_crashing(
    _mock_litellm: AsyncMock,
) -> None:
    """F-2.0-13 (adversary, confirmed low, 2026-07-28).

    A non-UUID user_id used to reach `uuid.UUID(query.user_id)` unguarded
    and raise an uncaught ValueError out of the graph. Not reachable via
    POST /query today (T-2.0-08 always supplies a real UUID), but Query
    is the shared contract other surfaces will build on, so this must not
    crash regardless of which surface constructs the Query.
    """
    query = _valid_query(user_id="not-a-well-formed-uuid")
    events = await _run_graph(query, _valid_context())

    assert _mock_litellm.call_count == 0  # declined before any model call
    types = [event.type for event in events]
    assert types == ["error", "done"]
    assert events[0].payload["error_class"] == "recoverable"
    assert "uuid" in events[0].payload["message"].lower()
    assert events[-1].payload["trust_outcome"] == "refuse"
