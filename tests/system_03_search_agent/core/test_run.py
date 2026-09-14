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
def _stub_symbol_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """See test_graph.py's identical fixture docstring for the rationale.

    T-3.1-11 made gene-symbol resolution a live NCBI call, and
    `_GRAPH_ANSWERABLE_QUERY_TEXT` below names BRCA1 in several tests here.
    """
    from system_03_search_agent.core import graph as graph_module

    known = {"BRCA1": "NCBIGene:672", "TP53": "NCBIGene:7157"}

    async def _fake_resolve_symbol_to_curie(symbol: str, **kwargs: object) -> str | None:
        return known.get(symbol.strip().upper())

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _fake_resolve_symbol_to_curie)


@pytest.fixture(autouse=True)
def _stub_ncbi_efetch_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """T-3.4-05/T-3.1-28: see test_graph.py's identical fixture docstring
    for the rationale. `_GRAPH_ANSWERABLE_QUERY_TEXT` below also names
    BRCA1, so `plan_node` also dispatches a second, Layer 2 `ncbi_efetch`
    call for the tests below; stubbed to a genuine, never-fabricated
    "empty" result by default, which `build_synth_findings`/citations/
    trust all skip (only a "ok" finding contributes), so no pre-existing
    assertion about citations, trust signals, or narrative content here is
    affected.
    """
    from system_03_search_agent.core import graph as graph_module
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput

    async def _fake_ncbi_efetch(tool_input: object, **kwargs: object) -> NcbiEfetchOutput:
        return NcbiEfetchOutput(
            status="empty",
            action="dataset_report",
            records=[],
            record_count=0,
            total_available=None,
            truncated=False,
            error=None,
        )

    monkeypatch.setattr(graph_module, "ncbi_efetch", _fake_ncbi_efetch)


@pytest.fixture(autouse=True)
def _stub_layer3_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """UI fix set 8 (R29): a gene question now also plans pubtator_annotate
    and clinicaltrials_search. Stubbed to genuine "empty" outputs, the same
    discipline as `_stub_ncbi_efetch_dispatch` above, so no test here ever
    reaches the network blocker and no pre-existing assertion about
    citations or trust changes (an empty finding contributes nothing).
    """
    from system_03_search_agent.core import graph as graph_module
    from system_03_search_agent.tools.clinicaltrials_search_schemas import (
        ClinicalTrialsSearchOutput,
    )
    from system_03_search_agent.tools.pubtator_annotate_schemas import PubtatorAnnotateOutput

    async def _fake_pubtator(tool_input: object, **kwargs: object) -> PubtatorAnnotateOutput:
        return PubtatorAnnotateOutput(status="empty", mode="entity_lookup")

    async def _fake_trials(tool_input: object, **kwargs: object) -> ClinicalTrialsSearchOutput:
        return ClinicalTrialsSearchOutput(status="empty")

    monkeypatch.setattr(graph_module, "pubtator_annotate", _fake_pubtator)
    monkeypatch.setattr(graph_module, "clinicaltrials_search", _fake_trials)


@pytest.fixture(autouse=True)
def _mock_litellm(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    # T-3.0-06: dispatches per tier. See `tests/system_03_search_agent/
    # model_stub.py` for why a single fixed response stopped working the
    # moment the guardrail began parsing its own model output.
    from tests.system_03_search_agent.model_stub import install_dispatching_acompletion

    return install_dispatching_acompletion(monkeypatch, harness_module)


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
        """Build phase 4.7 (T-4.7-04): `query_class` is a real classification
        now, not a hardcoded `"lookup"` stub literal, so the assertion checks
        membership in Section 17's five shapes rather than pinning the
        retired stub's own fixed value.
        """
        events = [event async for event in run(_valid_query(), _valid_context())]
        think_event = next(event for event in events if event.type == "think")
        payload_model = PAYLOAD_MODEL_BY_TYPE["think"]
        payload_model.model_validate(think_event.payload)
        assert think_event.payload["query_class"] in (
            "lookup",
            "single_hop",
            "multi_hop",
            "aggregate",
            "exploratory",
        )

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
    # T-3.4-05: BRCA1 resolves to a Gene CURIE, so plan_node also selects
    # ncbi_efetch as a second, Layer 2 call (stubbed to a genuine "empty"
    # result by the autouse `_stub_ncbi_efetch_dispatch` fixture). UI fix
    # set 8 (R29): plus pubtator_annotate and clinicaltrials_search on
    # Layer 3, stubbed "empty" by `_stub_layer3_dispatch`, so four in all.
    assert len(tool_calls) == 4
    assert tool_calls[0]["tool"] == "cypher_query"
    assert tool_calls[1]["tool"] == "ncbi_efetch"

    done_event = events[-1]
    assert done_event.type == "done"
    assert done_event.payload["total_tool_calls"] == 4
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
    # T-3.4-05 and UI fix set 8: see the sibling non-streaming test above.
    assert len(tool_calls) == 4
    assert tool_calls[0]["tool"] == "cypher_query"
    assert tool_calls[1]["tool"] == "ncbi_efetch"

    done_event = events[-1]
    assert done_event.type == "done"
    assert done_event.payload["total_tool_calls"] == 4
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
        # The graph fires exactly three sequential model calls for one
        # no-tool query, in this fixed order: guardrail (guard tier), think
        # (plan tier), write (synth tier). Four until 2026-09-14, when the
        # speed fix deleted `plan_node`'s discarded Plan-tier call, which
        # used to be the third; the delayed node is therefore `write` now.
        # Delaying the third call delays exactly the `write` node's own
        # emitted events (its `cost` and `done` events), while `guardrail`'s
        # `guard`/`cost`, `think`'s `think`/`cost` and `plan`'s `plan`/`cost`
        # events were already produced (and, under real streaming, already
        # yielded to the caller) before that delay even begins.
        # T-3.0-06: the guardrail's call is a real classification now, so a
        # stub that answers every call identically fails to parse there and
        # the run never reaches `think`. The guard branch below is what keeps
        # this test measuring streaming rather than accidentally measuring
        # the guardrail's error path.
        #
        # Build phase 4.7 (T-4.7-04): `think_node`'s own call is a real
        # classification too, now the SECOND call in sequence (still the
        # second chronologically, only the tier that answers it changed from
        # guard to plan), so it needs the same treatment or the run never
        # reaches `plan` either.
        from system_03_search_agent.core.graph import _THINK_SYSTEM_INSTRUCTION
        from system_03_search_agent.guardrail.classifier import GUARD_SYSTEM_INSTRUCTION
        from tests.system_03_search_agent.model_stub import (
            COMPLIANT_GUARD_CLASSIFICATION,
            compliant_think_classification,
        )

        delay_s = 0.25
        call_count = 0

        async def _acompletion(*args: object, **kwargs: object):
            nonlocal call_count
            call_count += 1
            messages = kwargs.get("messages") or []
            joined = "\n".join(
                message.get("content") or ""
                for message in messages  # type: ignore[union-attr]
            )
            if GUARD_SYSTEM_INSTRUCTION in joined:
                return _fake_response(COMPLIANT_GUARD_CLASSIFICATION)
            if _THINK_SYSTEM_INSTRUCTION in joined:
                return _fake_response(compliant_think_classification(messages))  # type: ignore[arg-type]
            if call_count == 3:  # the write node's call_tier call
                await asyncio.sleep(delay_s)
            return _fake_response()

        monkeypatch.setattr(harness_module.litellm, "acompletion", _acompletion)

        arrival_time_by_type: dict[str, float] = {}
        async for event in run_streaming(_valid_query(), _valid_context()):
            arrival_time_by_type.setdefault(event.type, time.monotonic())

        assert call_count == 3, call_count
        assert "plan" in arrival_time_by_type
        assert "done" in arrival_time_by_type
        gap_s = arrival_time_by_type["done"] - arrival_time_by_type["plan"]
        # A generous margin below the real delay (not the full delay_s),
        # so ordinary scheduling jitter cannot make a genuinely-streaming
        # implementation fail this assertion; a buffered implementation
        # would show a gap near 0, far below this margin, regardless of
        # jitter.
        assert gap_s >= delay_s * 0.6, (
            f"expected the 'done' event to arrive at least "
            f"{delay_s * 0.6:.3f}s after 'plan' (proving the delayed "
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


@pytest.mark.asyncio
async def test_remember_turn_records_the_citations_the_answer_showed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UI fix set 7, item 7.2 (2026-09-13). The end-of-run write hands memory
    the `source_url` of every citation emitted, deduplicated, in order, so
    the next go-deeper turn knows what the reader has already seen.

    Read off the citation EVENTS, the same ones the chips were built from,
    never off retrieval. MUTATION PROOF: dropping
    `reported_record_ids=reported_record_ids` from the
    `remember_turn_for_caller` call in `core/run.py` turns this arm red
    (`KeyError: 'reported_record_ids'`).
    """
    from datetime import UTC, datetime

    from system_03_search_agent.core import run as run_module
    from system_03_search_agent.core import session_memory as session_memory_module

    captured: dict[str, object] = {}

    async def _fake_remember(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(session_memory_module, "remember_turn_for_caller", _fake_remember)

    now = datetime.now(UTC)
    url_a = "https://www.ncbi.nlm.nih.gov/clinvar/variation/1/"
    url_b = "https://www.ncbi.nlm.nih.gov/clinvar/variation/2/"

    def _event(seq: int, kind: str, payload: dict) -> Event:
        return Event(type=kind, version="v1", trace_id="t-remember", seq=seq, ts=now, payload=payload)

    def _citation(index: int, url: str, claim: str) -> dict:
        from system_03_search_agent.contracts.events import CitationPayload

        return CitationPayload(
            citation_id=f"c-{index}",
            display_index=index,
            source="clinvar",
            source_id=f"ClinVar:{index}",
            source_url=url,
            layer="layer_1_graph",
            field="name",
            claim_text=claim,
            evidence_kind="graph_edge",
            assertion_confidence="asserted",
            license="public_domain",
        ).model_dump(mode="json")

    events = [
        _event(0, "plan", {
            "narrative": "selected cypher_query",
            "tool_calls": [],
            "resolved_entities": [{"text": "BRCA1", "curie": "NCBIGene:672", "confidence": 1.0}],
        }),
        _event(1, "citation", _citation(1, url_a, "a")),
        _event(2, "citation", _citation(2, url_a, "a again")),
        _event(3, "citation", _citation(3, url_b, "b")),
    ]
    query = Query(text="What variants cause it?", session_id="s", trace_id="t-remember",
                  owner_id="guest:remember-test")

    await run_module._remember_turn(query, events)

    assert captured["reported_record_ids"] == [url_a, url_b], captured
    assert captured["question"] == "What variants cause it?"
