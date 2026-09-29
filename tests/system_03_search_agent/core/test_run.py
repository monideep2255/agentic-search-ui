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
    """The shared query fixture. Its default text ("what can you do") is
    deliberately one of `core.graph._NO_TOOL_QUERY_TEXTS` (T-2.1-08), so
    plan_node selects no tool here, leaving this file's stub-era
    assertions (an empty `tool_calls` list, `total_tool_calls == 0`)
    accurate: they describe the no-tool-selected outcome, not a claim
    that no tool selection logic exists. Real cypher_query dispatch is
    covered in tests/system_03_search_agent/core/test_graph.py, which
    exercises the compiled graph directly with a substantive query text.

    FOUR WORDS, NOT ONE ("hello", changed 2026-09-24), since fix-plan item
    12.3, REDESIGNED the same day: a one-to-three-word opening question
    now makes its OWN guard-tier classifier call
    (`core.graph._clarify_or_proceed`) before any of this, which "hello"
    would have triggered, inserting an extra model call and cost event
    ahead of this file's own fixed call counts and event sequences. Four
    words is past that trigger.
    """
    base: dict[str, object] = {
        "text": "what can you do",
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
# T-2.1 rework: every `_valid_query()` use above defaults to "what can you
# do", core.graph._NO_TOOL_QUERY_TEXTS's no-tool path, leaving run() and
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
    # UI fix 11.21 wiring (2026-09-20), then item 2b (2026-09-22): thirteen
    # planned calls now. The four above plus three searches (PubMed, ClinVar,
    # OMIM), four follow-ups declared at Plan (abstracts, PubTator3
    # publications, ClinVar summary, OMIM summary), the Gene ESummary and the
    # context-only GO graph call; see test_breadth_wiring.py for the per-call
    # arms, including the one proving an OMIM record for another gene is
    # dropped before it can be cited.
    assert len(tool_calls) == 13
    assert tool_calls[0]["tool"] == "cypher_query"
    assert tool_calls[1]["tool"] == "ncbi_efetch"

    done_event = events[-1]
    assert done_event.type == "done"
    # UI fix 11.21 wiring (2026-09-20): five dispatched pairs now. The search
    # calls and the follow-ups closed `empty` by the stubs contribute no pair;
    # the GO graph call contributes one (the two-argument stand-in here does
    # not take the template keyword, so it closes as a disclosed error).
    assert done_event.payload["total_tool_calls"] == 6
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
    # UI fix 11.21 wiring (2026-09-20), then item 2b (2026-09-22): thirteen
    # planned calls now. The four above plus three searches (PubMed, ClinVar,
    # OMIM), four follow-ups declared at Plan (abstracts, PubTator3
    # publications, ClinVar summary, OMIM summary), the Gene ESummary and the
    # context-only GO graph call; see test_breadth_wiring.py for the per-call
    # arms, including the one proving an OMIM record for another gene is
    # dropped before it can be cited.
    assert len(tool_calls) == 13
    assert tool_calls[0]["tool"] == "cypher_query"
    assert tool_calls[1]["tool"] == "ncbi_efetch"

    done_event = events[-1]
    assert done_event.type == "done"
    # UI fix 11.21 wiring (2026-09-20): five dispatched pairs now. The search
    # calls and the follow-ups closed `empty` by the stubs contribute no pair;
    # the GO graph call contributes one (the two-argument stand-in here does
    # not take the template keyword, so it closes as a disclosed error).
    assert done_event.payload["total_tool_calls"] == 6
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


# Card 73: a crashed search writes its reason to the log. The person's screen
# stays generic (the tests above pin that); a developer traces the crash by
# trace id. The fake secret below is shaped like a provider key and rides in
# the exception MESSAGE, the way a provider error echoing a key would. It is
# assembled from parts so no scanner mistakes the test file for a leak.
_FAKE_KEY = "sk-" + "ant-" + "api03-" + "FAKEFAKEFAKE0123456789abcdefABCDEF"
_FAKE_PASSWORD = "hunter" + "2"


def _crash_records(caplog: pytest.LogCaptureFixture) -> list:
    return [
        r
        for r in caplog.records
        if r.name == "system_03_search_agent.core.run" and r.levelname == "ERROR"
    ]


def _install_crash(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    import system_03_search_agent.core.run as run_module

    message = f"provider rejected key {_FAKE_KEY} for dsn postgresql://u:{_FAKE_PASSWORD}@h/db"
    if path == "run":

        async def _boom(*args: object, **kwargs: object) -> None:
            raise ValueError(message)

        monkeypatch.setattr(run_module.compiled_graph, "ainvoke", _boom)
    else:

        async def _boom_astream(*args: object, **kwargs: object):
            raise ValueError(message)
            yield  # pragma: no cover

        monkeypatch.setattr(run_module.compiled_graph, "astream", _boom_astream)


async def _drain(path: str, query: Query) -> list:
    entry = run if path == "run" else run_streaming
    return [event async for event in entry(query, _valid_context())]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["run", "run_streaming"])
async def test_a_crash_logs_one_error_record_with_trace_id_and_exception_class(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, path: str
) -> None:
    _install_crash(monkeypatch, path)
    query = _valid_query()
    with caplog.at_level("ERROR", logger="system_03_search_agent.core.run"):
        events = await _drain(path, query)

    records = _crash_records(caplog)
    assert len(records) == 1
    text = records[0].getMessage()
    assert query.trace_id in text
    assert "builtins.ValueError" in text
    assert "test_run.py" in text  # a frame of the traceback is present
    assert records[0].exc_info is None  # the formatter would print the message
    # The person's screen is unchanged: the same generic pair, in order.
    assert [e.type for e in events] == ["error", "done"]
    assert (
        events[0].payload["message"]
        == "This query failed unexpectedly before it could complete."
    )
    assert events[0].payload["error_class"] == "unexpected"
    assert _FAKE_KEY not in str(events[0].payload)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["run", "run_streaming"])
async def test_a_crash_never_puts_a_secret_from_the_exception_message_in_the_log(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, path: str
) -> None:
    _install_crash(monkeypatch, path)
    with caplog.at_level("DEBUG"):
        await _drain(path, _valid_query())

    assert _crash_records(caplog)
    for record in caplog.records:
        rendered = caplog.handler.format(record)
        assert _FAKE_KEY not in rendered
        assert _FAKE_PASSWORD not in rendered
        assert "provider rejected" not in rendered


# Card 73, fix round: the record's shape and its bounds, and the promise that
# writing it can never cost the person the error event. These call
# `_log_crash` directly with built exceptions, so each bound is tested on its
# own; the two paths above and the tests below `_install_raise` cover the
# handlers.
_CRASH_LOGGER = "system_03_search_agent.core.run"
_TRACE = "2ff4e9d4-6499-4167-9e92-8c54d8ab720e"


def _crash_text(caplog: pytest.LogCaptureFixture) -> str:
    records = _crash_records(caplog)
    assert len(records) == 1, [r.getMessage() for r in records]
    return records[0].getMessage()


def _log_directly(caplog: pytest.LogCaptureFixture, exc: BaseException) -> str:
    from system_03_search_agent.core.run import _log_crash

    with caplog.at_level("ERROR", logger=_CRASH_LOGGER):
        _log_crash(_TRACE, exc)
    return _crash_text(caplog)


def _install_raise(monkeypatch: pytest.MonkeyPatch, path: str, exc: BaseException) -> None:
    import system_03_search_agent.core.run as run_module

    if path == "run":

        async def _boom(*args: object, **kwargs: object) -> None:
            raise exc

        monkeypatch.setattr(run_module.compiled_graph, "ainvoke", _boom)
    else:

        async def _boom_astream(*args: object, **kwargs: object):
            raise exc
            yield  # pragma: no cover

        monkeypatch.setattr(run_module.compiled_graph, "astream", _boom_astream)


def _assert_generic_pair(events: list) -> None:
    assert [e.type for e in events] == ["error", "done"]
    assert (
        events[0].payload["message"]
        == "This query failed unexpectedly before it could complete."
    )


def _deep(n: int, exc: BaseException) -> None:
    """Raise `exc` from n + 1 frames of `_deep` down, then one more frame."""
    if n == 0:
        _the_failing_line(exc)
    else:
        _deep(n - 1, exc)


def _the_failing_line(exc: BaseException) -> None:
    raise exc


def _raised(exc: BaseException, depth: int = 0) -> BaseException:
    try:
        _deep(depth, exc)
    except BaseException as caught:  # noqa: BLE001 - the test wants the raised object back
        return caught
    raise AssertionError("unreachable")  # pragma: no cover


# --- the first line: short, trace id first, never split (J05) -------------


@pytest.mark.parametrize("path", ["run", "run_streaming"])
@pytest.mark.asyncio
async def test_the_first_line_of_a_crash_record_starts_with_the_whole_trace_id_and_is_short(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, path: str
) -> None:
    _install_crash(monkeypatch, path)
    query = _valid_query()
    with caplog.at_level("ERROR", logger=_CRASH_LOGGER):
        await _drain(path, query)

    first = _crash_text(caplog).splitlines()[0]
    assert first.startswith("search crashed, trace ")
    assert query.trace_id in first  # unbroken, on the one line
    assert len(first) < 80, first


def test_a_very_long_trace_id_still_leaves_a_first_line_under_eighty_characters(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from system_03_search_agent.core.run import _log_crash

    with caplog.at_level("ERROR", logger=_CRASH_LOGGER):
        _log_crash("t" * 5000, ValueError("x"))
    assert len(_crash_text(caplog).splitlines()[0]) < 80


# --- the logger can never raise (J01, A08) ---------------------------------


def _exception_with_no_module() -> BaseException:
    namespace: dict = {}
    exec("E = type('E', (Exception,), {})", namespace)  # noqa: S102 - builds a class the way a template would
    return namespace["E"]()


@pytest.mark.parametrize("path", ["run", "run_streaming"])
@pytest.mark.asyncio
async def test_a_crash_whose_record_cannot_be_built_still_gives_the_person_the_error_event(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, path: str
) -> None:
    exc = _exception_with_no_module()
    with pytest.raises(AttributeError):
        _ = type(exc).__module__  # the trigger is real: reading it raises
    _install_raise(monkeypatch, path, exc)
    with caplog.at_level("ERROR", logger=_CRASH_LOGGER):
        events = await _drain(path, _valid_query())

    _assert_generic_pair(events)
    text = _crash_text(caplog)
    assert "crash record could not be built" in text
    assert "trace " in text


def test_a_record_that_cannot_be_built_logs_one_fallback_line_carrying_the_trace_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    text = _log_directly(caplog, _exception_with_no_module())
    assert text.startswith("search crashed, trace " + _TRACE)
    assert "crash record could not be built" in text


@pytest.mark.parametrize("path", ["run", "run_streaming"])
@pytest.mark.asyncio
async def test_a_logger_that_itself_raises_never_costs_the_person_the_error_event(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    import system_03_search_agent.core.run as run_module

    _install_raise(monkeypatch, path, ValueError("boom"))

    def _broken_error(*args: object, **kwargs: object) -> None:
        raise OSError("log disk full")

    monkeypatch.setattr(run_module.logger, "error", _broken_error)
    events = await _drain(path, _valid_query())
    _assert_generic_pair(events)


def test_a_cause_whose_truthiness_raises_does_not_stop_the_record() -> None:
    class Hostile(Exception):
        def __bool__(self) -> bool:
            raise RuntimeError("no truthiness")

    from system_03_search_agent.core.run import _crash_record

    try:
        raise ValueError("outer") from Hostile()
    except ValueError as caught:
        text = _crash_record(_TRACE, caught)
    assert "Hostile" in text


# --- the outermost and the innermost frames both survive (J02, A01) --------


def test_a_deep_traceback_keeps_the_entry_point_and_the_failure_and_counts_the_gap(
    caplog: pytest.LogCaptureFixture,
) -> None:
    exc = _raised(RecursionError("deep"), depth=60)
    text = _log_directly(caplog, exc)
    frames = text.split("frames:\n", 1)[1].splitlines()

    # Entry point first (this test function is where the exception was caught),
    # the failure last, and a line saying how many were left out between them.
    assert "test_a_deep_traceback_keeps_the_entry_point" not in frames[0]  # caught above _raised
    assert "_raised" in frames[0]
    assert "_the_failing_line" in frames[-1]
    omitted_lines = [f for f in frames if "frames omitted" in f]
    assert len(omitted_lines) == 1
    head = frames.index(omitted_lines[0])
    assert head >= 5  # at least 5 outer frames kept
    assert len(frames) - head - 1 >= 20  # at least 20 inner frames kept
    total = 1 + 61 + 1  # _raised, 61 frames of _deep, _the_failing_line
    kept = head + (len(frames) - head - 1)
    assert f"... {total - kept} frames omitted ..." in omitted_lines[0]


def test_a_short_traceback_is_listed_whole_with_no_omission_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    text = _log_directly(caplog, _raised(ValueError("x"), depth=3))
    assert "omitted" not in text
    assert text.count("_the_failing_line") == 1


# --- frames from the innermost exception, groups, chain rule (A02, A03, J03)


def test_the_frames_of_the_innermost_exception_in_the_chain_are_in_the_record(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def _origin_of_the_real_failure() -> None:
        raise KeyError("k")

    def _wrapper() -> None:
        try:
            _origin_of_the_real_failure()
        except KeyError as real:
            raise ValueError("wrapped") from real

    try:
        _wrapper()
    except ValueError as wrapped:
        exc = wrapped
    text = _log_directly(caplog, exc)
    assert "innermost_frames (builtins.KeyError)" in text
    assert "_origin_of_the_real_failure" in text.split("innermost_frames", 1)[1]


def test_the_innermost_exceptions_frames_obey_the_same_bounds(
    caplog: pytest.LogCaptureFixture,
) -> None:
    inner = _raised(KeyError("k"), depth=200)
    try:
        raise ValueError("outer") from inner
    except ValueError as outer:
        text = _log_directly(caplog, outer)
    innermost = text.split("innermost_frames", 1)[1].splitlines()[1:]
    assert len(innermost) == 8 + 1 + 25  # head, omission line, tail
    assert any("frames omitted" in line for line in innermost)
    assert "_the_failing_line" in innermost[-1]


def test_an_exception_group_lists_its_members_classes_and_no_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    members = [KeyError(_FAKE_KEY), TypeError(_FAKE_KEY)] + [
        ValueError(_FAKE_KEY) for _ in range(6)
    ]
    text = _log_directly(caplog, ExceptionGroup(_FAKE_KEY, members))
    line = next(x for x in text.splitlines() if x.startswith("group_members="))
    assert "builtins.KeyError" in line
    assert "builtins.TypeError" in line
    assert line.count("builtins.ValueError") == 3  # first five members only
    assert "(+3 more)" in line
    assert _FAKE_KEY not in text


def test_the_chain_follows_the_cause_and_falls_back_to_the_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    try:
        try:
            raise KeyError("k")
        except KeyError:
            raise ValueError("implicit context")
    except ValueError as caught:
        text = _log_directly(caplog, caught)
    assert "chain=builtins.ValueError <- builtins.KeyError" in text


def test_a_falsy_explicit_cause_is_still_followed(caplog: pytest.LogCaptureFixture) -> None:
    class Falsy(Exception):
        def __len__(self) -> int:
            return 0

    try:
        try:
            raise KeyError("suppressed context")
        except KeyError:
            raise ValueError("outer") from Falsy("real cause")
    except ValueError as caught:
        text = _log_directly(caplog, caught)
    chain = next(x for x in text.splitlines() if x.startswith("chain="))
    assert "Falsy" in chain
    assert "KeyError" not in chain  # an explicit cause wins over the context


def test_raise_from_none_hides_the_suppressed_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    try:
        try:
            raise KeyError("k")
        except KeyError:
            raise ValueError("outer") from None
    except ValueError as caught:
        text = _log_directly(caplog, caught)
    chain = next(x for x in text.splitlines() if x.startswith("chain="))
    assert chain == "chain=builtins.ValueError"


def test_the_chain_is_bounded_and_a_cycle_ends_it(caplog: pytest.LogCaptureFixture) -> None:
    head = ValueError("0")
    link = head
    for index in range(1, 40):
        nxt = ValueError(str(index))
        link.__cause__ = nxt
        link = nxt
    text = _log_directly(caplog, head)
    chain = next(x for x in text.splitlines() if x.startswith("chain="))
    assert chain.count("builtins.ValueError") == 8

    caplog.clear()
    a, b = ValueError("a"), KeyError("b")
    a.__cause__, b.__cause__ = b, a
    text = _log_directly(caplog, a)
    chain = next(x for x in text.splitlines() if x.startswith("chain="))
    assert chain == "chain=builtins.ValueError <- builtins.KeyError"


# --- every string and the whole record are bounded (A06) -------------------


def test_a_huge_class_name_module_file_and_function_name_are_each_cut(
    caplog: pytest.LogCaptureFixture,
) -> None:
    big_class = type("C" * 200_000, (Exception,), {"__module__": "m" * 200_000})
    code = compile("def " + "f" * 300 + "():\n    raise BIG\n", "p" * 5000 + ".py", "exec")
    scope: dict = {"BIG": big_class()}
    exec(code, scope)  # noqa: S102 - builds developer-shaped frames with hostile-length names
    try:
        scope["f" * 300]()
    except Exception as caught:  # noqa: BLE001
        exc = caught
    text = _log_directly(caplog, exc)
    assert len(text) < 1500
    assert max(len(line) for line in text.splitlines()) < 320
    assert "m" * 101 not in text
    assert "C" * 101 not in text
    assert "f" * 101 not in text
    assert "p" * 101 not in text


def test_the_whole_record_has_a_size_ceiling_and_keeps_its_first_line(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import system_03_search_agent.core.run as run_module

    monkeypatch.setattr(run_module, "_CRASH_LOG_MAX_CHARS", 500)
    text = _log_directly(caplog, _raised(ValueError("x"), depth=20))
    assert len(text) <= 500 + len("\n... record cut at its size limit")
    assert text.splitlines()[0] == "search crashed, trace " + _TRACE
    assert text.endswith("record cut at its size limit")


def test_the_worst_case_record_stays_under_the_real_ceiling(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import system_03_search_agent.core.run as run_module

    inner = _raised(KeyError("k"), depth=300)
    try:
        _deep(300, ValueError("outer"))
    except ValueError:
        try:
            raise RuntimeError("wrap") from inner
        except RuntimeError as wrapped:
            text = _log_directly(caplog, wrapped)
    assert len(text) <= run_module._CRASH_LOG_MAX_CHARS + 100


# --- the no-message rule holds across every new path (decision 6) ----------


def test_no_message_argument_or_local_reaches_the_record_from_any_link_or_group_member(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def _fail() -> None:
        secret_local = _FAKE_KEY  # a local variable must never be read into the record
        raise KeyError(secret_local, _FAKE_PASSWORD)

    try:
        try:
            _fail()
        except KeyError as inner:
            raise ExceptionGroup(_FAKE_KEY, [inner, ValueError(_FAKE_PASSWORD)]) from inner
    except ExceptionGroup as group:
        text = _log_directly(caplog, group)
    assert "innermost_frames" in text or "group_members" in text
    for rendered in [text, *(caplog.handler.format(r) for r in caplog.records)]:
        assert _FAKE_KEY not in rendered
        assert _FAKE_PASSWORD not in rendered
    assert all(r.exc_info is None for r in caplog.records)
