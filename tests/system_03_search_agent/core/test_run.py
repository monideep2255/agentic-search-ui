"""Tests for run() (Section 2.1), now backed by the real five-node
LangGraph loop (T-2.0-07).

T-2.0-07 replaced the phase 1.0 scaffold (a fixed guard-then-done round
trip with no real model call) with `core.graph.compiled_graph`. This file
is updated accordingly:

    - The phase 1.0 assertions that only depended on the typed-event
      envelope mechanism (Event instances, trace_id propagation, seq
      monotonicity, timezone-aware timestamps, exactly one terminal
      `done` event) still hold unchanged, since the envelope contract
      itself did not change.
    - `TestRunMakesNoDirectLlmOrToolCall`, which asserted `core/run.py`'s
      source contained no `litellm`/`harness` imports, is removed rather
      than kept and weakened: that assertion encoded the phase 1.0
      scaffold's defining property (no real model call anywhere), and
      this ticket's entire point is wiring a real `Harness` and a real
      LiteLLM-backed model call into every node. Keeping a test that
      asserts the opposite of what the ticket requires would not be a
      weakened verify surface, it would be a verify surface for a
      property this ticket is required to remove.
    - New assertions cover the previously-scaffolded properties this
      ticket makes real: intermediate `think`, `plan`, and `cost` events
      are now actually emitted and schema-valid, and the `done` event's
      `total_cost_usd` now reflects real (mocked) metered cost instead of
      a hardcoded `0.0`.

No real network call is made anywhere in this file: `litellm.acompletion`
and `litellm.get_model_info` are monkeypatched on `harness_module`, the
same pattern `test_harness.py` and `test_graph.py` use. The two daily-cap
DB checks are monkeypatched to no-ops for the same reason `test_graph.py`
documents: their own DB-backed behavior has a full test suite in
`test_cost_control.py`, and this file is not re-proving that.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.contracts.events import (
    PAYLOAD_MODEL_BY_TYPE,
    DonePayload,
    Event,
    GuardPayload,
)
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.run import run, run_streaming
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import harness as harness_module


def _fake_response(content: str = "ok", prompt_tokens: int = 10, completion_tokens: int = 5):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("PER_USER_DAILY_QUERY_CAP", "100")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")
    monkeypatch.setenv("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")


@pytest.fixture(autouse=True)
def _no_op_daily_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    """See test_graph.py's identical fixture docstring for the rationale."""

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
    deliberately one of `core.graph._NO_TOOL_QUERY_TEXTS` (T-2.1-08), so
    plan_node selects no tool here, leaving this file's stub-era
    assertions (an empty `tool_calls` list, `total_tool_calls == 0`)
    accurate: they describe the no-tool-selected outcome, not a claim
    that no tool selection logic exists. Real cypher_query dispatch is
    covered in tests/system_03_search_agent/core/test_graph.py, which
    exercises the compiled graph directly with a substantive query text.
    """
    base: dict[str, object] = {
        "text": "hello",
        "session_id": "session-1",
        "trace_id": "trace-1",
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


class TestRunSignature:
    def test_run_is_an_async_generator_function(self) -> None:
        assert inspect.isasyncgenfunction(run)

    def test_run_return_annotation_names_async_iterator_of_event(self) -> None:
        annotation = str(inspect.signature(run).return_annotation)
        assert "AsyncIterator" in annotation
        assert "Event" in annotation


class TestRunYieldsEvents:
    @pytest.mark.asyncio
    async def test_every_yielded_item_is_an_event_instance(self) -> None:
        events = [event async for event in run(_valid_query(), _valid_context())]
        assert len(events) > 0
        for event in events:
            assert isinstance(event, Event)

    @pytest.mark.asyncio
    async def test_yields_at_least_one_guard_event(self) -> None:
        events = [event async for event in run(_valid_query(), _valid_context())]
        guard_events = [event for event in events if event.type == "guard"]
        assert len(guard_events) >= 1

    @pytest.mark.asyncio
    async def test_guard_event_payload_is_schema_valid(self) -> None:
        events = [event async for event in run(_valid_query(), _valid_context())]
        guard_event = next(event for event in events if event.type == "guard")
        payload = GuardPayload(**guard_event.payload)
        assert payload.passed is True
        assert payload.category == "ok"

    @pytest.mark.asyncio
    async def test_guard_event_envelope_version_is_v1(self) -> None:
        events = [event async for event in run(_valid_query(), _valid_context())]
        guard_event = next(event for event in events if event.type == "guard")
        assert guard_event.version == "v1"

    @pytest.mark.asyncio
    async def test_terminates_with_exactly_one_done_event(self) -> None:
        events = [event async for event in run(_valid_query(), _valid_context())]
        done_events = [event for event in events if event.type == "done"]
        assert len(done_events) == 1
        assert events[-1].type == "done"

    @pytest.mark.asyncio
    async def test_done_event_payload_is_schema_valid(self) -> None:
        events = [event async for event in run(_valid_query(), _valid_context())]
        done_event = next(event for event in events if event.type == "done")
        payload = DonePayload(**done_event.payload)
        assert payload.trust_outcome == "answer"
        assert payload.total_tool_calls == 0
        # T-2.0-07: unlike the phase 1.0 scaffold's hardcoded 0.0, this is
        # now the harness's real (mocked) metered running total, positive
        # since four tier calls fired (guardrail, think, plan, write).
        assert payload.total_cost_usd > 0.0
        assert payload.elapsed_ms >= 0

    @pytest.mark.asyncio
    async def test_trace_id_propagates_from_query_to_every_event(self) -> None:
        query = _valid_query(trace_id="trace-xyz")
        events = [event async for event in run(query, _valid_context())]
        for event in events:
            assert event.trace_id == "trace-xyz"

    @pytest.mark.asyncio
    async def test_seq_is_monotonic_starting_at_zero_with_no_repeats(self) -> None:
        events = [event async for event in run(_valid_query(), _valid_context())]
        seqs = [event.seq for event in events]
        assert seqs[0] == 0
        assert seqs == sorted(seqs)
        assert len(seqs) == len(set(seqs))

    @pytest.mark.asyncio
    async def test_ts_is_timezone_aware_on_every_event(self) -> None:
        events = [event async for event in run(_valid_query(), _valid_context())]
        for event in events:
            assert event.ts.tzinfo is not None


class TestRunEmitsTheFullFiveNodeLoop:
    """T-2.0-07: run() is no longer a two-event scaffold. It now emits
    every intermediate event the real guardrail/think/plan/act/write loop
    produces, each schema-valid against its Section 2.3 payload model."""

    @pytest.mark.asyncio
    async def test_yields_a_think_event_and_it_is_schema_valid(self) -> None:
        events = [event async for event in run(_valid_query(), _valid_context())]
        think_event = next(event for event in events if event.type == "think")
        payload_model = PAYLOAD_MODEL_BY_TYPE["think"]
        payload_model.model_validate(think_event.payload)
        assert think_event.payload["query_class"] == "lookup"

    @pytest.mark.asyncio
    async def test_yields_a_plan_event_and_it_is_schema_valid(self) -> None:
        events = [event async for event in run(_valid_query(), _valid_context())]
        plan_event = next(event for event in events if event.type == "plan")
        payload_model = PAYLOAD_MODEL_BY_TYPE["plan"]
        payload_model.model_validate(plan_event.payload)
        assert plan_event.payload["tool_calls"] == []

    @pytest.mark.asyncio
    async def test_yields_cost_events_and_they_are_schema_valid(self) -> None:
        events = [event async for event in run(_valid_query(), _valid_context())]
        cost_events = [event for event in events if event.type == "cost"]
        payload_model = PAYLOAD_MODEL_BY_TYPE["cost"]
        assert len(cost_events) == 4  # guardrail, think, plan, write
        for event in cost_events:
            payload_model.model_validate(event.payload)

    @pytest.mark.asyncio
    async def test_every_event_in_the_full_run_is_schema_valid(self) -> None:
        events = [event async for event in run(_valid_query(), _valid_context())]
        for event in events:
            PAYLOAD_MODEL_BY_TYPE[event.type].model_validate(event.payload)

    @pytest.mark.asyncio
    async def test_no_citation_or_trust_signal_event_is_fabricated(self) -> None:
        events = [event async for event in run(_valid_query(), _valid_context())]
        types = {event.type for event in events}
        assert "citation" not in types
        assert "trust_signal" not in types


# ---------------------------------------------------------------------------
# T-2.1 rework: every `_valid_query()` use above defaults to "hello",
# core.graph._NO_TOOL_QUERY_TEXTS's no-tool path, leaving run() and
# run_streaming() with zero coverage of real tool dispatch through their
# own real entry points (tests/system_03_search_agent/core/test_graph.py
# exercises the compiled graph directly, which is a different call path).
# These exercise dispatch through run() and run_streaming() themselves,
# and pin down the cite-or-refuse fix (findings A5/F-02): the generic
# "ok" mocked model response is not recoverable Cypher (see
# test_graph.py's test_act_executes_the_selected_cypher_query_call
# docstring for the same mechanics), so cypher_query returns
# status="error" and the query must refuse, not fabricate an answer.
# ---------------------------------------------------------------------------

_GRAPH_ANSWERABLE_QUERY_TEXT = "What gene is associated with BRCA1?"


@pytest.mark.asyncio
async def test_run_dispatches_the_selected_tool_call_for_a_graph_answerable_query(
    _mock_litellm: AsyncMock,
) -> None:
    query = _valid_query(text=_GRAPH_ANSWERABLE_QUERY_TEXT)
    events = [event async for event in run(query, _valid_context())]

    plan_event = next(event for event in events if event.type == "plan")
    tool_calls = plan_event.payload["tool_calls"]
    assert len(tool_calls) == 1
    assert tool_calls[0]["tool"] == "cypher_query"

    done_event = events[-1]
    assert done_event.type == "done"
    assert done_event.payload["total_tool_calls"] == 1
    assert done_event.payload["trust_outcome"] == "refuse"

    for event in events:
        PAYLOAD_MODEL_BY_TYPE[event.type].model_validate(event.payload)


@pytest.mark.asyncio
async def test_run_streaming_dispatches_the_selected_tool_call_for_a_graph_answerable_query(
    _mock_litellm: AsyncMock,
) -> None:
    query = _valid_query(text=_GRAPH_ANSWERABLE_QUERY_TEXT)
    events = [event async for event in run_streaming(query, _valid_context())]

    plan_event = next(event for event in events if event.type == "plan")
    tool_calls = plan_event.payload["tool_calls"]
    assert len(tool_calls) == 1
    assert tool_calls[0]["tool"] == "cypher_query"

    done_event = events[-1]
    assert done_event.type == "done"
    assert done_event.payload["total_tool_calls"] == 1
    assert done_event.payload["trust_outcome"] == "refuse"

    for event in events:
        PAYLOAD_MODEL_BY_TYPE[event.type].model_validate(event.payload)


@pytest.mark.asyncio
async def test_an_otherwise_uncaught_graph_exception_yields_error_then_done_not_a_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-2.0-11 (adversary, confirmed medium, 2026-07-28).

    Before this fix, any exception `compiled_graph.ainvoke` did not
    itself handle (an unreachable database, or any bug in a node this
    phase's stub logic did not anticipate) propagated out of `run()`
    raw, with zero typed events yielded: a blank failure,
    production-standards.md's graceful-degradation gate forbids exactly
    this. `run()` must never raise; it must always yield at least an
    `error` then a `done` event.
    """
    import system_03_search_agent.core.run as run_module

    async def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated unreachable database or unhandled node bug")

    monkeypatch.setattr(run_module.compiled_graph, "ainvoke", _boom)

    events = [event async for event in run(_valid_query(), _valid_context())]

    assert [event.type for event in events] == ["error", "done"]
    assert events[0].payload["scope"] == "run"
    assert events[0].payload["error_class"] == "unexpected"
    assert events[-1].payload["trust_outcome"] == "refuse"
    for event in events:
        PAYLOAD_MODEL_BY_TYPE[event.type].model_validate(event.payload)


class TestRunStreamingSignature:
    """T-1.2-01: `run_streaming()` is the incremental sibling of `run()`,
    same event taxonomy and never-raises guarantee, added alongside
    `run()` without changing it (every `TestRun*` class above is
    untouched, still asserting `run()`'s own unchanged behavior)."""

    def test_run_streaming_is_an_async_generator_function(self) -> None:
        assert inspect.isasyncgenfunction(run_streaming)

    def test_run_streaming_return_annotation_names_async_iterator_of_event(self) -> None:
        annotation = str(inspect.signature(run_streaming).return_annotation)
        assert "AsyncIterator" in annotation
        assert "Event" in annotation


class TestRunStreamingMirrorsRunsEventContract:
    """The happy-path event stream `run_streaming()` produces must match
    `run()`'s own contract exactly, since it drives the same graph
    through the same nodes; only the delivery timing differs (proven
    separately in TestRunStreamingIsGenuinelyIncremental below)."""

    @pytest.mark.asyncio
    async def test_every_yielded_item_is_an_event_instance(self) -> None:
        events = [event async for event in run_streaming(_valid_query(), _valid_context())]
        assert len(events) > 0
        for event in events:
            assert isinstance(event, Event)

    @pytest.mark.asyncio
    async def test_every_event_is_schema_valid(self) -> None:
        events = [event async for event in run_streaming(_valid_query(), _valid_context())]
        for event in events:
            PAYLOAD_MODEL_BY_TYPE[event.type].model_validate(event.payload)

    @pytest.mark.asyncio
    async def test_terminates_with_exactly_one_done_event(self) -> None:
        events = [event async for event in run_streaming(_valid_query(), _valid_context())]
        done_events = [event for event in events if event.type == "done"]
        assert len(done_events) == 1
        assert events[-1].type == "done"

    @pytest.mark.asyncio
    async def test_done_event_reflects_real_metered_cost(self) -> None:
        events = [event async for event in run_streaming(_valid_query(), _valid_context())]
        done_event = next(event for event in events if event.type == "done")
        payload = DonePayload(**done_event.payload)
        assert payload.trust_outcome == "answer"
        assert payload.total_cost_usd > 0.0

    @pytest.mark.asyncio
    async def test_seq_is_monotonic_starting_at_zero_with_no_repeats(self) -> None:
        events = [event async for event in run_streaming(_valid_query(), _valid_context())]
        seqs = [event.seq for event in events]
        assert seqs[0] == 0
        assert seqs == sorted(seqs)
        assert len(seqs) == len(set(seqs))

    @pytest.mark.asyncio
    async def test_trace_id_propagates_to_every_event(self) -> None:
        query = _valid_query(trace_id="trace-streaming-xyz")
        events = [event async for event in run_streaming(query, _valid_context())]
        for event in events:
            assert event.trace_id == "trace-streaming-xyz"

    @pytest.mark.asyncio
    async def test_yields_the_same_event_type_sequence_as_the_buffered_run(self) -> None:
        """Not a timing claim (that is the next test class); this only
        proves `run_streaming()` drives the identical five-node loop and
        produces the identical event-type sequence `run()` does, so it is
        a genuine incremental sibling, not a different code path that
        happens to also emit events."""
        query = _valid_query(trace_id="trace-parity")
        buffered_types = [event.type async for event in run(query, _valid_context())]
        streamed_types = [
            event.type async for event in run_streaming(query, _valid_context())
        ]
        assert streamed_types == buffered_types


class TestRunStreamingIsGenuinelyIncremental:
    """T-1.2-01's core acceptance criterion: events from nodes before a
    deliberately-delayed node must be observable by the caller BEFORE the
    delayed node's own event arrives, proven with real wall-clock timing
    (no mocked clock). A buffered implementation (like `run()`) could
    never pass this test: it yields nothing until the entire graph
    finishes, so every event would arrive at nearly the same instant
    regardless of which node was internally delayed."""

    @pytest.mark.asyncio
    async def test_earlier_events_arrive_before_a_delayed_nodes_event_by_a_real_measurable_gap(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The graph fires exactly four sequential model calls for one
        # query, in this fixed order: guardrail (guard tier), think
        # (guard tier), plan (plan tier), write (synth tier). Delaying the
        # third call delays exactly the `plan` node's own emitted events
        # (its `plan` and `cost` events), while `guardrail`'s `guard`/
        # `cost` events and `think`'s `think`/`cost` events were already
        # produced (and, under real streaming, already yielded to the
        # caller) before that delay even begins.
        delay_s = 0.25
        call_count = 0

        async def _acompletion(*args: object, **kwargs: object):
            nonlocal call_count
            call_count += 1
            if call_count == 3:  # the plan node's call_tier call
                await asyncio.sleep(delay_s)
            return _fake_response()

        monkeypatch.setattr(harness_module.litellm, "acompletion", _acompletion)

        arrival_time_by_type: dict[str, float] = {}
        async for event in run_streaming(_valid_query(), _valid_context()):
            arrival_time_by_type.setdefault(event.type, time.monotonic())

        assert "think" in arrival_time_by_type
        assert "plan" in arrival_time_by_type
        gap_s = arrival_time_by_type["plan"] - arrival_time_by_type["think"]
        # A generous margin below the real delay (not the full delay_s),
        # so ordinary scheduling jitter cannot make a genuinely-streaming
        # implementation fail this assertion; a buffered implementation
        # would show a gap near 0, far below this margin, regardless of
        # jitter.
        assert gap_s >= delay_s * 0.6, (
            f"expected the 'plan' event to arrive at least "
            f"{delay_s * 0.6:.3f}s after 'think' (proving the delayed "
            f"node's own call_tier sleep was actually awaited before its "
            f"event reached the caller), observed only {gap_s:.3f}s"
        )


@pytest.mark.asyncio
async def test_run_streaming_yields_error_then_done_on_an_otherwise_uncaught_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The streaming sibling of the F-2.0-11 crash-fallback test above:
    the same graceful-degradation guarantee must hold for
    `compiled_graph.astream()` as it already does for
    `compiled_graph.ainvoke()`. Here the exception is raised on the very
    first `astream` iteration (mirroring the buffered test's own "crash
    before anything is produced" scenario), so the assertions are
    identical: exactly `error` then `done`, nothing else.
    """
    import system_03_search_agent.core.run as run_module

    async def _boom_astream(*args: object, **kwargs: object):
        raise RuntimeError("simulated unreachable database or unhandled node bug")
        yield  # pragma: no cover - unreachable; makes this an async generator function

    monkeypatch.setattr(run_module.compiled_graph, "astream", _boom_astream)

    events = [event async for event in run_streaming(_valid_query(), _valid_context())]

    assert [event.type for event in events] == ["error", "done"]
    assert events[0].payload["scope"] == "run"
    assert events[0].payload["error_class"] == "unexpected"
    assert events[0].seq == 0
    assert events[1].seq == 1
    assert events[-1].payload["trust_outcome"] == "refuse"
    for event in events:
        PAYLOAD_MODEL_BY_TYPE[event.type].model_validate(event.payload)


@pytest.mark.asyncio
async def test_run_streaming_crash_mid_stream_keeps_seq_monotonic_with_real_events_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A crash that happens AFTER some real node events were already
    yielded (unlike the "crash before anything is produced" test above)
    must still surface those real events to the caller (the whole point
    of switching to `astream`, per F-2.0-11's closure note) and the
    synthetic error/done pair appended after them must continue the same
    `seq` sequence, never restart at 0 and collide with an already-issued
    seq value.
    """
    import system_03_search_agent.core.run as run_module

    real_astream = run_module.compiled_graph.astream

    async def _astream_then_boom(*args: object, **kwargs: object):
        count = 0
        async for update in real_astream(*args, **kwargs):
            yield update
            count += 1
            if count == 2:  # after guardrail and think have both completed
                raise RuntimeError("simulated crash partway through the graph run")

    monkeypatch.setattr(run_module.compiled_graph, "astream", _astream_then_boom)

    events = [event async for event in run_streaming(_valid_query(), _valid_context())]

    # Real events from guardrail and think (guard, cost, think, cost)
    # precede the synthetic error/done pair.
    assert [event.type for event in events[:4]] == ["guard", "cost", "think", "cost"]
    assert [event.type for event in events[-2:]] == ["error", "done"]
    seqs = [event.seq for event in events]
    assert seqs == sorted(seqs)
    assert len(seqs) == len(set(seqs))
    for event in events:
        PAYLOAD_MODEL_BY_TYPE[event.type].model_validate(event.payload)
