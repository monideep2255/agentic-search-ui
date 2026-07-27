"""Tests for the stub run() entry point (Section 2.1)."""

import inspect

import pytest

from system_03_search_agent.contracts.events import DonePayload, Event, GuardPayload
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import run as run_module
from system_03_search_agent.core.run import run


def _valid_query(**overrides: object) -> Query:
    base: dict[str, object] = {
        "text": "What gene is BRCA1?",
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
        assert payload.total_cost_usd == 0.0
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


class TestRunMakesNoDirectLlmOrToolCall:
    def test_run_module_source_has_no_llm_or_tool_imports(self) -> None:
        source = inspect.getsource(run_module)
        forbidden_substrings = [
            "litellm",
            "anthropic",
            "openai",
            "system_03_search_agent.tools",
            "system_03_search_agent.harness",
        ]
        for forbidden in forbidden_substrings:
            assert forbidden not in source
