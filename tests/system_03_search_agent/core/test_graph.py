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

from system_03_search_agent.contracts.events import PAYLOAD_MODEL_BY_TYPE, Event
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.core.graph import compiled_graph
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import harness as harness_module
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
    base: dict[str, object] = {
        "text": "What gene is BRCA1?",
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
    await _run_graph(_valid_query(), _valid_context())
    plan_tier_calls = [
        call for call in _mock_litellm.call_args_list if call.kwargs["model"] == f"openrouter/{_PLAN_MODEL}"
    ]
    assert len(plan_tier_calls) == 1


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

    Every guardrail/think/plan/write call reaches litellm.acompletion with
    graph_module._STABLE_PREFIX prepended as a leading system-role
    message, proving the prompt-cache scaffold T-2.0-06 built is actually
    wired into the loop, not merely unit-tested in isolation.
    """
    await _run_graph(_valid_query(), _valid_context())
    assert _mock_litellm.call_count == 4
    for call in _mock_litellm.call_args_list:
        leading_message = call.kwargs["messages"][0]
        assert leading_message["role"] == "system"
        assert leading_message["content"] == graph_module._STABLE_PREFIX


@pytest.mark.asyncio
async def test_exactly_four_model_calls_fire_on_the_happy_path(
    _mock_litellm: AsyncMock,
) -> None:
    """guardrail, think, plan, write each call_tier once; act calls no model."""
    await _run_graph(_valid_query(), _valid_context())
    assert _mock_litellm.call_count == 4


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
async def test_plan_event_tool_calls_is_empty_stub() -> None:
    events = await _run_graph(_valid_query(), _valid_context())
    plan_event = next(event for event in events if event.type == "plan")
    assert plan_event.payload["tool_calls"] == []


@pytest.mark.asyncio
async def test_done_event_trust_outcome_is_answer_on_the_happy_path() -> None:
    events = await _run_graph(_valid_query(), _valid_context())
    done_event = next(event for event in events if event.type == "done")
    assert done_event.payload["trust_outcome"] == "answer"
    assert done_event.payload["total_tool_calls"] == 0


# ---------------------------------------------------------------------------
# act: proves the coordinator-worker integration point is actually wired.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_act_node_calls_coordinator_worker_execute_with_empty_lists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple] = []
    original = graph_module.coordinator_worker_execute

    async def _spy(harness, tool_calls, results):
        calls.append((tool_calls, results))
        return await original(harness, tool_calls, results)

    monkeypatch.setattr(graph_module, "coordinator_worker_execute", _spy)
    await _run_graph(_valid_query(), _valid_context())

    assert calls == [([], [])]


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
