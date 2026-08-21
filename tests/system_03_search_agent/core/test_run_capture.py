"""Focused unit tests for T-4.6-07 (dispatch capture from the run
epilogue), plus a regression guard for F-4.6-06 (see
`TestServerTraceIdIsNeverOverwritten` below).

`tests/system_03_search_agent/core/test_feedback_capture_premise.py` is
the phase's own premise gate and is the primary grading surface for
T-4.6-07 (its P1 through P12 arms drive `run()` end to end against a real
database). This file exists beside it for the one property the premise
gate cannot cheaply exercise: the CRASH-fallback path in `run()` and
`run_streaming()`, where `compiled_graph.ainvoke`/`astream` raises before
producing a real `done` event. Standing that scenario up against a real
Postgres database, the way the premise gate does for its other arms,
would require a second scratch-database fixture purely to prove a code
path the premise gate's own coverage statement does not name; mocking
`feedback.capture_run` here is cheaper and just as direct a proof that
`core.run._capture_interaction` is actually called on that path, with the
right events.

Every test here follows `test_run.py`'s own established pattern for this
module: no real model or network call, `litellm.acompletion`/
`get_model_info` monkeypatched, gene-symbol resolution and the Layer 2
`ncbi_efetch` dispatch stubbed so a query naming BRCA1 cannot reach a live
NCBI endpoint. Mutation-proven per `.claude/rules/goal-contracts.md`: each
test's docstring names the control it exists to catch.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

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
    """See test_graph.py's identical fixture docstring for the rationale:
    the two daily caps' own DB-backed behavior has a full suite in
    test_cost_control.py, and this file is not re-proving that."""

    def _user_check(session, user_id, **kwargs):
        return None

    def _system_check(session, **kwargs):
        return None

    monkeypatch.setattr(cost_control, "check_user_daily_query_cap", _user_check)
    monkeypatch.setattr(cost_control, "check_system_daily_cost_cap", _system_check)


@pytest.fixture(autouse=True)
def _stub_symbol_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """See test_run.py's identical fixture docstring: gene-symbol
    resolution is a live NCBI call (T-3.1-11), and this file's default
    query text ("hello") never names a gene, but a test that overrides the
    text with BRCA1 must not reach the real network either."""
    from system_03_search_agent.core import graph as graph_module

    known = {"BRCA1": "NCBIGene:672", "TP53": "NCBIGene:7157"}

    async def _fake_resolve_symbol_to_curie(symbol: str, **kwargs: object) -> str | None:
        return known.get(symbol.strip().upper())

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _fake_resolve_symbol_to_curie)


@pytest.fixture(autouse=True)
def _stub_ncbi_efetch_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """See test_run.py's identical fixture docstring."""
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
def _mock_litellm(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    from tests.system_03_search_agent.model_stub import install_dispatching_acompletion

    return install_dispatching_acompletion(monkeypatch, harness_module)


def _valid_query(**overrides: object) -> Query:
    """Deliberately the same "hello" default as test_run.py's own fixture:
    one of `core.graph._NO_TOOL_QUERY_TEXTS`, so plan_node selects no tool
    and this file's tests do not depend on the graph stubs above at all
    for their default case."""
    base: dict[str, object] = {
        "text": "hello",
        "session_id": "session-1",
        "trace_id": "caller-supplied-trace-id",
        "user_id": None,
        "owner_id": "guest:11111111-1111-1111-1111-111111111111",
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


def _mock_capture_run(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Patch `feedback.capture_run` at the module `core.run._capture_
    interaction` actually reads it from (a deferred import inside that
    function body, so the patch target is the `feedback` package's own
    attribute, not a name bound inside `core.run` at import time)."""
    import system_03_search_agent.feedback as feedback_module

    mock = AsyncMock(return_value=None)
    monkeypatch.setattr(feedback_module, "capture_run", mock)
    return mock


# ---------------------------------------------------------------------------
# F-4.6-06 regression guard: run() must never mint its own trace_id.
# ---------------------------------------------------------------------------


class TestServerTraceIdIsNeverOverwritten:
    @pytest.mark.asyncio
    async def test_run_does_not_overwrite_the_trace_id_it_was_given(self) -> None:
        """F-4.6-06, Technical_specification.md Section 13.1: `run_id` is
        "the external-facing name for `trace_id`, not a second identifier
        scheme". Every callable surface (`adapters/web_sse/app.py`,
        `adapters/mcp/server.py`, `adapters/graphql/schema.py`) mints one
        `uuid.uuid4()` BEFORE calling into `core.run`, sets it as both
        `Query.trace_id` and the `run_id` returned to the caller, and
        depends on `run()` leaving that value alone so the two stay equal
        on the wire (see `test_run_id_and_the_events_trace_id_are_the_same_
        identifier` in `tests/system_03_search_agent/adapters/web_sse/
        test_streaming_endpoints.py`). Build phase 4.6 briefly added a
        second, in-process mint (`core.run._mint_server_trace_id`) to
        satisfy a gate arm (P5) that called `run()` directly with no
        adapter in front of it; no real caller can reach that path, and the
        mint necessarily produced a value different from the `run_id`
        already handed back to the caller, splitting the "same identifier
        under two names" pair Section 13.1 requires. The mint was reverted
        (F-4.6-06). This test is the guard against it, or anything shaped
        like it, coming back after a future reader sees Section 20.1's
        "trace_id is minted at the Guardrail step" line in isolation and
        reintroduces a second mint inside `run()`. Mutation: reintroduce
        `_mint_server_trace_id` (or any equivalent unconditional
        `query.trace_id = str(uuid.uuid4())`) at the top of `run()`. This
        test goes red because the events would then never carry the
        caller-supplied `trace_id`."""
        query = _valid_query(trace_id="adapter-minted-trace-id")
        events = [event async for event in run(query, _valid_context())]
        assert events
        for event in events:
            assert event.trace_id == "adapter-minted-trace-id"

    @pytest.mark.asyncio
    async def test_run_streaming_does_not_overwrite_the_trace_id_it_was_given(
        self,
    ) -> None:
        """The `run_streaming()` sibling of the guard above. See that
        test's docstring (F-4.6-06, Section 13.1) for the full account."""
        query = _valid_query(trace_id="adapter-minted-trace-id")
        events = [event async for event in run_streaming(query, _valid_context())]
        assert events
        for event in events:
            assert event.trace_id == "adapter-minted-trace-id"


# ---------------------------------------------------------------------------
# T-4.6-07: capture dispatch, including the crash-fallback path.
# ---------------------------------------------------------------------------


class TestCaptureDispatchedFromTheEpilogue:
    @pytest.mark.asyncio
    async def test_run_dispatches_capture_after_yielding_every_event(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mutation: delete the `await _capture_interaction(...)` call in
        `run()`'s `finally` block. This test goes red because `capture_run`
        would never be called at all. (The call moved out of the success
        path and into a `finally` at F-4.6-A-02; see
        `TestCaptureSurvivesEveryTerminationPath` below for why.)"""
        mock_capture = _mock_capture_run(monkeypatch)

        events = [event async for event in run(_valid_query(), _valid_context())]

        assert mock_capture.await_count == 1
        called_query, called_events = mock_capture.await_args.args
        assert called_query.trace_id == events[0].trace_id
        assert called_events == events

    @pytest.mark.asyncio
    async def test_run_streaming_dispatches_capture_after_yielding_every_event(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The run_streaming() sibling of the test above."""
        mock_capture = _mock_capture_run(monkeypatch)

        events = [event async for event in run_streaming(_valid_query(), _valid_context())]

        assert mock_capture.await_count == 1
        called_query, called_events = mock_capture.await_args.args
        assert called_query.trace_id == events[0].trace_id
        assert called_events == events

    @pytest.mark.asyncio
    async def test_run_captures_on_the_crash_fallback_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T-4.6-07's explicit requirement: the crash-fallback path (the
        graph invocation itself raising, F-2.0-11) still captures exactly
        one row's worth of events. Mutation: drop the `emitted.extend(
        crash_events)` line in `run()`'s crash `except` block. This test
        goes red on `called_events == events`, because the `finally` would
        then capture an empty list and `_terminal_events_for_capture` would
        hand the assembler a synthesized `done` alone rather than the real
        error/done pair the caller saw."""
        import system_03_search_agent.core.run as run_module

        mock_capture = _mock_capture_run(monkeypatch)

        async def _boom(*args: object, **kwargs: object) -> None:
            raise RuntimeError("simulated unreachable database or unhandled node bug")

        monkeypatch.setattr(run_module.compiled_graph, "ainvoke", _boom)

        events = [event async for event in run(_valid_query(), _valid_context())]

        assert [event.type for event in events] == ["error", "done"]
        assert mock_capture.await_count == 1
        called_query, called_events = mock_capture.await_args.args
        assert called_events == events
        assert called_query.trace_id == events[0].trace_id

    @pytest.mark.asyncio
    async def test_run_streaming_captures_on_the_crash_fallback_path_with_real_events_first(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T-4.6-07: the same crash-path requirement for `run_streaming()`,
        where a crash partway through `astream` leaves some real events
        already yielded before the synthetic pair. Mutation: replace
        `seen_events.extend(crash_events)` in the crash `except` block with
        `seen_events.clear()` followed by that extend. Ran it. This test
        goes red on `called_events == events`, the assertion above the
        length one, because the captured list loses the real `guard` event
        that fired before the simulated crash and therefore stops matching
        what the caller saw. The length assertion below it is the one that
        states the property in words; the equality assertion is the one that
        fires first."""
        import system_03_search_agent.core.run as run_module

        mock_capture = _mock_capture_run(monkeypatch)

        real_astream = run_module.compiled_graph.astream

        async def _astream_then_boom(*args: object, **kwargs: object):
            first = True
            async for update in real_astream(*args, **kwargs):
                yield update
                if first:
                    first = False
                    raise RuntimeError("simulated crash partway through the graph run")

        monkeypatch.setattr(run_module.compiled_graph, "astream", _astream_then_boom)

        events = [
            event async for event in run_streaming(_valid_query(), _valid_context())
        ]

        assert events[-1].type == "done"
        assert mock_capture.await_count == 1
        _called_query, called_events = mock_capture.await_args.args
        assert called_events == events
        assert len(called_events) > 2, (
            "the captured events must include the real pre-crash events, "
            "not only the synthetic error/done pair"
        )

    @pytest.mark.asyncio
    async def test_a_capture_failure_never_reaches_the_caller(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """P6's property, exercised at the unit level: `_capture_interaction`
        catches and logs rather than propagating. Mutation: remove the
        try/except around the `await capture_run(...)` call inside
        `_capture_interaction`. This test goes red because the
        `RuntimeError` below would then propagate out of `run()`, breaking
        its own documented never-raises contract."""
        import system_03_search_agent.feedback as feedback_module

        async def _explode(*args: object, **kwargs: object) -> None:
            raise RuntimeError("user-data database is unreachable")

        monkeypatch.setattr(feedback_module, "capture_run", _explode)

        events = [event async for event in run(_valid_query(), _valid_context())]

        assert events[-1].type == "done"

    @pytest.mark.asyncio
    async def test_capture_still_runs_when_session_memory_recording_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Capture is independent of `_remember_turn`: a session-memory
        write failure must not skip capture. Mutation: move the `await
        _capture_interaction(...)` call out of `run()`'s `finally` and into
        the `_remember_turn` try block. This test goes red because
        `capture_run` would then never be called once `_remember_turn`
        itself raises."""
        import system_03_search_agent.core.run as run_module

        mock_capture = _mock_capture_run(monkeypatch)

        async def _explode(*args: object, **kwargs: object) -> None:
            raise RuntimeError("session memory store unreachable")

        monkeypatch.setattr(run_module, "_remember_turn", _explode)

        events = [event async for event in run(_valid_query(), _valid_context())]

        assert events[-1].type == "done"
        assert mock_capture.await_count == 1


# ---------------------------------------------------------------------------
# F-4.6-A-02: capture survives every way a run can end, not only exhaustion.
# ---------------------------------------------------------------------------


class TestCaptureSurvivesEveryTerminationPath:
    """The category, not the two instances the adversary reached.

    `run()` and `run_streaming()` are async generators. Code written after
    their last `yield` runs ONLY when a consumer drives the generator to
    exhaustion. Every other way a generator ends finalizes it instead:

    - the consumer breaks out of its `async for`
    - the consumer's task is cancelled at a `yield` (the Stop endpoint, and
      the registry's abandonment timer)
    - something calls `aclose()` explicitly
    - something calls `athrow()`
    - the collector reaches it

    F-4.6-A-02 measured two of those (a stopped run and an abandoned one)
    and found zero rows for twelve queries against a per-user cap of three.
    Enumerating those two would leave the other three, so capture moved
    into a `finally`, which every one of them runs, and these arms exercise
    the class rather than the members: a `break`, an `aclose()`, and an
    `athrow()`, plus the one shape that must NOT capture (a generator that
    was never started, and therefore never ran).
    """

    @pytest.mark.asyncio
    async def test_a_consumer_that_stops_reading_still_leaves_a_capture(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mutation: move the `await _capture_interaction(...)` call out of
        `run_streaming()`'s `finally` and back to the end of its body. Ran
        it. What ACTUALLY happened is not what a first reading predicts:
        `capture_run` was not merely late, it was never awaited at all
        within the test, because a generator abandoned mid-iteration is
        finalized by the collector on its own schedule rather than at the
        `break`. `mock_capture.await_count` read 0 and the assertion below
        went red on that. Recorded because "it would run later" is the
        plausible-sounding wrong answer here, and a cap that counts rows
        cannot depend on a collection schedule."""
        mock_capture = _mock_capture_run(monkeypatch)

        stream = run_streaming(_valid_query(), _valid_context())
        seen = []
        async for event in stream:
            seen.append(event)
            break
        await stream.aclose()

        assert seen, "the generator produced no event, so nothing is being graded"
        assert mock_capture.await_count == 1, (
            "a consumer that stopped reading left no capture, so the run is "
            "invisible to both daily caps (F-4.6-A-02)"
        )

    @pytest.mark.asyncio
    async def test_a_cancelled_consumer_still_leaves_a_capture(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The Stop button's shape, at the generator level: a consumer task
        cancelled while suspended on `__anext__`, then the generator closed
        the way `core/run_registry.py::_drain_into_entry` now closes it.
        Control: the `try`/`finally` around `run_streaming`'s body. Ran the
        mutation of moving the capture dispatch back out of that `finally`
        and to the end of the body; this arm goes red with
        `await_count == 0`.

        This arm deliberately does NOT grade `_drain_into_entry`'s
        `await stream.aclose()`, because it calls `aclose()` itself. That
        split is on purpose: this arm grades the GENERATOR's contract and
        `test_run_registry.py`'s `test_a_run_suspended_at_a_yield_is_
        finalized_by_the_explicit_close` grades the CONSUMER's use of it.
        Either one alone stays green while the pair is broken."""
        import asyncio

        mock_capture = _mock_capture_run(monkeypatch)
        stream = run_streaming(_valid_query(), _valid_context())

        async def _consume() -> None:
            async for _event in stream:
                pass

        task = asyncio.create_task(_consume())
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await stream.aclose()

        assert mock_capture.await_count == 1, (
            "a cancelled run left no capture (F-4.6-A-02)"
        )

    @pytest.mark.asyncio
    async def test_a_generator_that_was_never_started_captures_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The boundary of the rule above, and the reason capture sits in a
        `finally` inside the generator rather than in a wrapper around it: a
        `run()` object that nobody ever iterated is not a run. Its body
        never executed, so the `try` was never entered and the `finally`
        never fires, and no row is written for a query that was never
        asked. Mutation: replace the `finally`-based dispatch with an
        unconditional capture in a wrapper that runs whether or not the
        body did. This arm goes red, because a never-started generator
        would then leave a row."""
        mock_capture = _mock_capture_run(monkeypatch)

        stream = run(_valid_query(), _valid_context())
        await stream.aclose()

        assert mock_capture.await_count == 0, (
            "a generator that was never iterated must not leave a row"
        )

    @pytest.mark.asyncio
    async def test_a_run_that_never_reached_done_still_captures_a_terminal_done(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The other half of the fix, and the half that decides whether a
        row actually lands. `feedback.capture.assemble_interaction` returns
        `None` when the events carry no `done`, so dispatching capture on a
        stopped run and handing it a truncated event list would still write
        nothing. `_terminal_events_for_capture` supplies the terminal record
        the assembler needs.

        Mutation: make `_terminal_events_for_capture` return `events`
        unchanged. Ran it. This arm goes red on the final assertion, and the
        REAL failure mode is worth recording because it is quieter than the
        prediction: nothing raises and nothing logs, the captured list is
        simply short one event, and every other assertion here still
        passes. That is exactly the silence F-4.6-A-02 shipped under."""
        mock_capture = _mock_capture_run(monkeypatch)

        stream = run_streaming(_valid_query(), _valid_context())
        async for _event in stream:
            break
        await stream.aclose()

        assert mock_capture.await_count == 1
        _called_query, called_events = mock_capture.await_args.args
        assert called_events[-1].type == "done", (
            "a stopped run must still hand the assembler a terminal `done`, "
            "or `assemble_interaction` returns None and no row is written"
        )
        assert called_events[-1].payload["trust_outcome"] == "refuse"

    @pytest.mark.asyncio
    async def test_the_synthesized_done_carries_the_cost_actually_incurred(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-4.6-A-01 and F-4.6-A-02 both name the SYSTEM-WIDE daily cost
        cap alongside the per-user query cap. A stopped run that captured a
        row with `cost_usd = 0` would restore the query count and still
        leave the money invisible, so the synthesized `done` reads the
        harness's own running total off the last `cost` event rather than
        defaulting to zero.

        Mutation: hardcode `total_cost_usd=0.0` in
        `_terminal_events_for_capture`. This arm goes red on the assertion
        below."""
        mock_capture = _mock_capture_run(monkeypatch)

        stream = run_streaming(_valid_query(), _valid_context())
        collected = []
        async for event in stream:
            collected.append(event)
            # Read far enough to have paid for at least one model call, then
            # stop the way a caller pressing Stop does.
            if any(item.type == "cost" for item in collected):
                break
        await stream.aclose()

        assert any(event.type == "cost" for event in collected), (
            "the run was stopped before any cost event, so this arm is not "
            "measuring what it claims to"
        )
        _called_query, called_events = mock_capture.await_args.args
        assert called_events[-1].type == "done"
        assert called_events[-1].payload["total_cost_usd"] > 0.0, (
            "a stopped run reported zero cost, so the system-wide daily cost "
            "cap cannot see what it paid for (F-4.6-A-02)"
        )
