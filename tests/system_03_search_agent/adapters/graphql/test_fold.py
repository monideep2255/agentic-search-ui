"""Unit tests for `system_03_search_agent.adapters.graphql.fold`.

Covers T-4.3-02's own acceptance surface directly: `fold_run`, `fold_run_
snapshot`, and `fold_citations` are exercised against a real, isolated
`RunRegistry` instance (never the module-level `default_registry`, and
never the full HTTP/schema stack `tests/.../test_phase_4_3_premise.py`
drives, since `schema.py` and `router.py` do not exist yet). Every
assertion names, in a comment beside it, the mutation that turns it red,
matching this repository's mutation-proof discipline for a gate file.

`system_03_search_agent.core.run_registry.run_streaming` is monkeypatched
at its SOURCE module, the same seam every adapter gate in this repository
already uses (`_drain_into_entry` reads `run_streaming` off its own
enclosing module namespace), and `fold_module.default_registry` is
monkeypatched to point at a fresh, test-local `RunRegistry()` instance per
test, so no test shares state with another or with the process-wide
default registry.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest

from system_03_search_agent.adapters.graphql import fold as fold_module
from system_03_search_agent.adapters.graphql.types import MAX_ANSWER_LENGTH, MAX_CITATIONS
from system_03_search_agent.contracts.events import (
    CitationPayload,
    DonePayload,
    ErrorPayload,
    Event,
    GuardPayload,
    TokenPayload,
    ToolResultPayload,
    TrustSignalPayload,
)
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import run_registry as run_registry_module
from system_03_search_agent.core.run_registry import RunEntry, RunRegistry

# ---------------------------------------------------------------------------
# Fixtures and fake event streams.
# ---------------------------------------------------------------------------


def _event(event_type: str, trace_id: str, seq: int, payload: Any) -> Event:
    return Event(
        type=event_type,  # type: ignore[arg-type]
        version="v1",
        trace_id=trace_id,
        seq=seq,
        ts=datetime.now(UTC),
        payload=payload.model_dump(),
    )


def _citation(index: int, *, citation_id: str | None = None) -> CitationPayload:
    return CitationPayload(
        citation_id=citation_id or f"c{index}",
        display_index=index,
        source="NCBI Gene",
        source_id=f"{670 + index}",
        source_url=f"https://www.ncbi.nlm.nih.gov/gene/{670 + index}",
        layer="layer_1_graph",
        field="gene_symbol",
        claim_text=f"claim number {index}",
        evidence_kind="curated_assertion",
        assertion_confidence="high",
        population_ancestry_context=None,
        license="public_domain",
        snapshot_date="2026-07-01",
        entity_name="BRCA1",
    )


async def _golden_path_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event(
        "token", trace_id, 1, TokenPayload(text="BRCA1 is a protein-coding gene [1]. ", marker_ids=["c1"])
    )
    yield _event("citation", trace_id, 2, _citation(1))
    yield _event(
        "trust_signal",
        trace_id,
        3,
        TrustSignalPayload(
            outcome="answer",
            risk_tier="low",
            grounded=True,
            triangulated=None,
            citation_id="c1",
            scope="answer",
            message=None,
            fallback_link=None,
        ),
    )
    yield _event(
        "done",
        trace_id,
        4,
        DonePayload(total_cost_usd=0.01, total_tool_calls=1, elapsed_ms=100, trust_outcome="answer"),
    )


async def _uncited_answer_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event("token", trace_id, 1, TokenPayload(text="BRCA1 causes every known disease.", marker_ids=[]))
    yield _event(
        "trust_signal",
        trace_id,
        2,
        TrustSignalPayload(
            outcome="answer",
            risk_tier="low",
            grounded=True,
            triangulated=None,
            citation_id=None,
            scope="answer",
            message=None,
            fallback_link=None,
        ),
    )
    yield _event(
        "done",
        trace_id,
        3,
        DonePayload(total_cost_usd=0.004, total_tool_calls=1, elapsed_ms=210, trust_outcome="answer"),
    )


async def _claim_scoped_trust_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event("token", trace_id, 1, TokenPayload(text="Claim one [1]. ", marker_ids=["c1"]))
    yield _event("citation", trace_id, 2, _citation(1))
    yield _event(
        "trust_signal",
        trace_id,
        3,
        TrustSignalPayload(
            outcome="answer",
            risk_tier="low",
            grounded=True,
            triangulated=None,
            citation_id="c1",
            scope="claim",
            message=None,
            fallback_link=None,
        ),
    )
    yield _event("token", trace_id, 4, TokenPayload(text="Claim two [2]. ", marker_ids=["c2"]))
    yield _event("citation", trace_id, 5, _citation(2, citation_id="c2"))
    yield _event(
        "trust_signal",
        trace_id,
        6,
        TrustSignalPayload(
            outcome="flag",
            risk_tier="high",
            grounded=True,
            triangulated=False,
            citation_id="c2",
            scope="claim",
            message="a second source disagrees",
            fallback_link=None,
        ),
    )
    yield _event(
        "done",
        trace_id,
        7,
        DonePayload(total_cost_usd=0.02, total_tool_calls=2, elapsed_ms=1400, trust_outcome="flag"),
    )


async def _oversized_answer_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    seq = 1
    for chunk in range(12):
        yield _event("token", trace_id, seq, TokenPayload(text=("x" * 900) + f" chunk{chunk} ", marker_ids=[]))
        seq += 1
    for index in range(1, MAX_CITATIONS + 6):
        yield _event("citation", trace_id, seq, _citation(index, citation_id=f"c{index}"))
        seq += 1
    yield _event(
        "trust_signal",
        trace_id,
        seq,
        TrustSignalPayload(
            outcome="answer",
            risk_tier="low",
            grounded=True,
            triangulated=None,
            citation_id="c1",
            scope="answer",
            message=None,
            fallback_link=None,
        ),
    )
    seq += 1
    yield _event(
        "done", trace_id, seq, DonePayload(total_cost_usd=0.3, total_tool_calls=4, elapsed_ms=5000, trust_outcome="answer")
    )


async def _fatal_error_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event(
        "error",
        trace_id,
        1,
        ErrorPayload(
            fatal=True,
            scope="run",
            source="graph_connection",
            error_class="unexpected",
            message="could not connect to host db-internal.example:5432 as user kg_reader",
            retry_after_s=0,
        ),
    )
    yield _event(
        "done", trace_id, 2, DonePayload(total_cost_usd=0.001, total_tool_calls=0, elapsed_ms=95, trust_outcome="refuse")
    )


async def _never_terminating_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event("citation", trace_id, 1, _citation(1))
    while True:  # pragma: no cover - the wall-clock bound is what ends this
        await asyncio.sleep(0.02)


def _isolated_registry_and_run(
    monkeypatch: pytest.MonkeyPatch, stream_fn: Any
) -> tuple[RunRegistry, str]:
    """Build a fresh, test-local `RunRegistry`, point `fold_module.
    default_registry` at it, monkeypatch `run_streaming` at its source
    module, create one run against `stream_fn`, and return the registry
    and the minted run_id. `query.trace_id` is set to the same value as
    `run_id`, matching how every real caller (schema.py's future `ask`
    resolver) mints and threads the two together.
    """
    registry = RunRegistry()
    monkeypatch.setattr(run_registry_module, "run_streaming", stream_fn)
    monkeypatch.setattr(fold_module, "default_registry", registry)
    run_id = str(uuid.uuid4())
    query = Query(
        text="Which diseases are associated with BRCA1?",
        session_id="s-fold-test",
        trace_id=run_id,
        user_id="u1",
    )
    context = RequestContext(surface="graphql")
    registry.create_run(query, context, run_id=run_id)
    return registry, run_id


# ---------------------------------------------------------------------------
# fold_run: the golden path.
# ---------------------------------------------------------------------------


class TestFoldRunGoldenPath:
    @pytest.mark.asyncio
    async def test_fold_run_returns_a_grounded_cited_answer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: drop citations from the fold, or
        # fail to carry the answer-scope trust_signal's grounded=True
        # through unchanged.
        _registry, run_id = _isolated_registry_and_run(monkeypatch, _golden_path_stream)
        result = await fold_module.fold_run(run_id)

        assert result.run_id == run_id
        assert result.persona_name == "Assistant"
        assert "protein-coding gene" in result.answer
        assert result.trust_signal.outcome == "answer"
        assert result.trust_signal.grounded is True
        assert len(result.citations) == 1
        assert result.citations[0].citation_id == "c1"
        assert result.disclosures.answer_truncated is False
        assert result.disclosures.citations_omitted == 0

    @pytest.mark.asyncio
    async def test_fold_run_never_calls_run_streaming_a_second_time(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: fold_run calling core.run.
        # run_streaming (or default_registry.create_run) itself instead of
        # only subscribing to the run someone else already created, which
        # would start a second run.
        calls: list[str] = []

        async def _counting_golden_path(query: Query, context: RequestContext) -> AsyncIterator[Event]:
            calls.append(query.trace_id)
            async for event in _golden_path_stream(query, context):
                yield event

        _registry, run_id = _isolated_registry_and_run(monkeypatch, _counting_golden_path)
        await fold_module.fold_run(run_id)
        assert calls == [run_id]


# ---------------------------------------------------------------------------
# fold_run: cite-or-refuse and claim-scoped aggregation.
# ---------------------------------------------------------------------------


class TestFoldRunGrounding:
    @pytest.mark.asyncio
    async def test_an_uncited_answer_is_never_reported_as_grounded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: report grounded=true (or
        # outcome="answer") whenever a trust_signal event says so, without
        # checking that any citation actually arrived. The stream here
        # emits an answer-scope trust_signal CLAIMING grounded=True with
        # zero citation events; the floor in _finalize must correct that
        # claim, not trust it.
        _registry, run_id = _isolated_registry_and_run(monkeypatch, _uncited_answer_stream)
        result = await fold_module.fold_run(run_id)

        assert result.citations == []
        assert result.trust_signal.grounded is False
        assert result.trust_signal.outcome != "answer"

    @pytest.mark.asyncio
    async def test_claim_scoped_trust_is_aggregated_not_first_wins(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: take the first claim-scoped
        # trust_signal (outcome="answer", risk_tier="low") and ignore the
        # rest, instead of aggregating to the most restrictive
        # (outcome="flag", risk_tier="high").
        _registry, run_id = _isolated_registry_and_run(monkeypatch, _claim_scoped_trust_stream)
        result = await fold_module.fold_run(run_id)

        assert result.trust_signal.outcome == "flag"
        assert result.trust_signal.risk_tier == "high"
        assert len(result.citations) == 2


# ---------------------------------------------------------------------------
# fold_run: truncation with disclosure.
# ---------------------------------------------------------------------------


class TestFoldRunTruncationDisclosure:
    @pytest.mark.asyncio
    async def test_an_oversized_answer_is_truncated_and_disclosed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: drop the MAX_ANSWER_LENGTH
        # truncation, which would let `answer` exceed the cap and leave
        # disclosures.answer_truncated False on a run that plainly
        # overflowed it.
        _registry, run_id = _isolated_registry_and_run(monkeypatch, _oversized_answer_stream)
        result = await fold_module.fold_run(run_id)

        assert len(result.answer) <= MAX_ANSWER_LENGTH
        assert result.disclosures.answer_truncated is True
        assert result.disclosures.notes, "a truncation must be named, not just flagged"

    @pytest.mark.asyncio
    async def test_an_over_cap_citation_list_discloses_the_real_omitted_count(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: cap the citation list without
        # counting what was dropped (citations_omitted stays 0), or return
        # more than MAX_CITATIONS citations.
        _registry, run_id = _isolated_registry_and_run(monkeypatch, _oversized_answer_stream)
        result = await fold_module.fold_run(run_id)

        assert len(result.citations) == MAX_CITATIONS
        assert result.disclosures.citations_omitted == 5  # MAX_CITATIONS+6-1 emitted, 5 over cap
        assert result.disclosures.notes


# ---------------------------------------------------------------------------
# fold_run: a fatal error never leaks, and floors trust.
# ---------------------------------------------------------------------------


class TestFoldRunFatalError:
    @pytest.mark.asyncio
    async def test_a_fatal_errors_internal_message_never_reaches_the_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: interpolate ErrorPayload.message
        # directly into the answer or the disclosure note instead of using
        # the fixed, error_class-keyed literal.
        _registry, run_id = _isolated_registry_and_run(monkeypatch, _fatal_error_stream)
        result = await fold_module.fold_run(run_id)

        serialized = " ".join(
            [result.answer, result.trust_signal.message or "", *result.disclosures.notes]
        )
        assert "db-internal.example" not in serialized
        assert "kg_reader" not in serialized

    @pytest.mark.asyncio
    async def test_a_fatal_error_floors_trust_to_high_risk_and_ungrounded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: skip the trust floor on a fatal
        # error, leaving whatever risk_tier/grounded value the synthetic
        # default branch produced (which could read as safe on a run that
        # crashed mid-answer).
        _registry, run_id = _isolated_registry_and_run(monkeypatch, _fatal_error_stream)
        result = await fold_module.fold_run(run_id)

        assert result.trust_signal.grounded is False
        assert result.trust_signal.risk_tier == "high"
        assert result.disclosures.notes  # the fixed literal is disclosed by name


# ---------------------------------------------------------------------------
# fold_run: the wall-clock bound.
# ---------------------------------------------------------------------------


class TestFoldRunWallClockBound:
    @pytest.mark.asyncio
    async def test_a_never_terminating_run_is_bounded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: drop the `asyncio.timeout(...)`
        # wrap around the subscribe loop. Without it, this test's own
        # `asyncio.wait_for` safety net would fire instead (a plain
        # `TimeoutError`, not `fold_module.FoldTimeoutError`), so
        # `pytest.raises(FoldTimeoutError)` below would fail rather than
        # the test hanging forever.
        monkeypatch.setattr(fold_module, "_FOLD_LOOP_TIMEOUT_S", 0.3, raising=True)
        _registry, run_id = _isolated_registry_and_run(monkeypatch, _never_terminating_stream)

        with pytest.raises(fold_module.FoldTimeoutError):
            await asyncio.wait_for(fold_module.fold_run(run_id), timeout=2.0)


# ---------------------------------------------------------------------------
# fold_run_snapshot: reports partial state without waiting.
# ---------------------------------------------------------------------------


class TestFoldRunSnapshot:
    @pytest.mark.asyncio
    async def test_snapshot_reports_unfinished_and_partial_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: implement fold_run_snapshot via
        # default_registry.subscribe (which would await the run's live
        # tail forever on this never-terminating stream, since the stream
        # never reaches a terminal event). This test's outer `wait_for`
        # safety net makes that failure mode a fast, clean red instead of
        # a hang.
        _registry, run_id = _isolated_registry_and_run(monkeypatch, _never_terminating_stream)
        # Let the background task advance past its guard and citation
        # yields (real, not mocked, scheduling: the task only runs when
        # control returns to the event loop).
        await asyncio.sleep(0.05)

        result = await asyncio.wait_for(fold_module.fold_run_snapshot(run_id), timeout=1.0)

        assert result.run_id == run_id
        assert result.finished is False
        assert len(result.citations) == 1

    @pytest.mark.asyncio
    async def test_snapshot_reports_finished_true_once_the_run_completes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The second arm. Mutation that turns it red: hardcode finished=
        # True (or False) regardless of entry.finished, which would make
        # the arm above pass while this one silently lies.
        _registry, run_id = _isolated_registry_and_run(monkeypatch, _golden_path_stream)
        await fold_module.fold_run(run_id)  # drains the run to completion first

        result = await fold_module.fold_run_snapshot(run_id)
        assert result.finished is True
        assert result.trust_signal.outcome == "answer"


# ---------------------------------------------------------------------------
# fold_citations.
# ---------------------------------------------------------------------------


async def _finished_entry(
    *, events: list[Event], finished: bool = True, cancelled: bool = False
) -> RunEntry:
    async def _noop() -> None:
        return None

    task = asyncio.create_task(_noop())
    await task
    return RunEntry(
        run_id="r-citations-test",
        user_id="u1",
        owner_id="user:u1",
        queue=asyncio.Queue(),
        task=task,
        events=events,
        finished=finished,
        cancelled=cancelled,
    )


class TestFoldCitations:
    @pytest.mark.asyncio
    async def test_mirrors_rest_export_and_discloses_both_header_facts(self) -> None:
        # Mutation that turns this red: drop export_truncated or
        # run_cancelled, the two facts REST sends as X-Citations-Export-
        # Truncated and X-Run-Cancelled response headers, which GraphQL
        # has no channel for.
        events = [
            _event("citation", "t1", index, _citation(index, citation_id=f"c{index}"))
            for index in range(1, MAX_CITATIONS + 6)
        ]
        entry = await _finished_entry(events=events, finished=True, cancelled=True)

        export = fold_module.fold_citations(entry)

        assert export.run_id == "r-citations-test"
        assert export.export_truncated is True
        assert export.run_cancelled is True
        assert len(export.citations) == MAX_CITATIONS

    @pytest.mark.asyncio
    async def test_an_uncapped_export_does_not_falsely_claim_truncation(self) -> None:
        # The second arm. Mutation that turns it red: hardcode
        # export_truncated True, which would make the arm above pass while
        # every honest export lies about itself.
        events = [_event("citation", "t1", 1, _citation(1))]
        entry = await _finished_entry(events=events, finished=True, cancelled=False)

        export = fold_module.fold_citations(entry)

        assert export.export_truncated is False
        assert export.run_cancelled is False
        assert len(export.citations) == 1

    @pytest.mark.parametrize(
        ("error_class", "expected_note"),
        [
            ("unexpected", "This query failed unexpectedly before finishing."),
            (
                "transient",
                "This query hit a temporary error before finishing. Retrying may succeed.",
            ),
            ("recoverable", "This query could not complete as requested."),
            ("cancelled", "This query was stopped before it finished."),
        ],
    )
    @pytest.mark.asyncio
    async def test_a_dead_runs_export_says_the_run_died(
        self, error_class: str, expected_note: str
    ) -> None:
        # Review round 6, F1, MAJOR and blocking. `run_failed` was the literal
        # `False` here, with a comment claiming "the citations export carries
        # no fatal-error signal of its own". It has one: the run's own fatal
        # `error` event, in `entry.events`, which the loop below was ALREADY
        # reading in order to know where to stop. So a run that died returned
        # a `Disclosures` byte-identical to a healthy run's, on the one type
        # whose premise is that anything the surface drops or shortens it says
        # so, and on a surface a caller reaches through `citations(runId:)`
        # for any finished run.
        #
        # Mutation that turns this red: put `run_failed=False` back, or drop
        # the fatal-error branch from the loop.
        events = [
            _event("citation", "t1", 0, _citation(1)),
            _event(
                "error",
                "t1",
                1,
                ErrorPayload(
                    fatal=True,
                    scope="run",
                    source="graph_connection",
                    error_class=error_class,
                    # Internal text, on purpose: the export must report the
                    # FACT of the failure and never this sentence (F-4.1-A-09).
                    message="could not connect to host db-internal.example:5432 as kg_reader",
                    retry_after_s=0,
                ),
            ),
        ]
        entry = await _finished_entry(events=events, finished=True, cancelled=False)

        export = fold_module.fold_citations(entry)

        assert export.disclosures.run_failed is True
        assert expected_note in export.disclosures.notes
        joined = " ".join(export.disclosures.notes)
        assert "db-internal.example" not in joined
        assert "kg_reader" not in joined
        # The export itself is still returned, with whatever the run produced
        # before it died. Disclosing the death must not empty the payload.
        assert len(export.citations) == 1

    @pytest.mark.asyncio
    async def test_a_healthy_runs_export_is_not_accused_of_failing(self) -> None:
        # The second arm. Mutation that turns it red: hardcode
        # `run_failed=True`, which would make the arm above pass while every
        # healthy export lies about itself. A surface that reports every run
        # as failed is exactly as dishonest as one that reports none.
        events = [
            _event("citation", "t1", 0, _citation(1)),
            _event(
                "done",
                "t1",
                1,
                DonePayload(
                    total_cost_usd=0.0,
                    total_tool_calls=1,
                    elapsed_ms=12,
                    trust_outcome="answer",
                ),
            ),
        ]
        entry = await _finished_entry(events=events, finished=True, cancelled=False)

        export = fold_module.fold_citations(entry)

        assert export.disclosures.run_failed is False
        assert export.disclosures.notes == []

    @pytest.mark.asyncio
    async def test_an_export_from_a_run_that_never_reached_a_terminal_event_says_so(
        self,
    ) -> None:
        # The other half of F1, found while verifying the first half live. A
        # run whose stream dies WITHOUT appending a terminal event leaves no
        # fatal error payload behind, so `run_failed` is False here and in
        # `_finalize` alike, by the same rule. Without a note the export was
        # again byte-identical to a healthy run's.
        #
        # Mutation that turns this red: drop `terminal_event_seen` from
        # `fold_citations`, or stop prepending its note.
        events = [_event("citation", "t1", 0, _citation(1))]
        entry = await _finished_entry(events=events, finished=True, cancelled=False)

        export = fold_module.fold_citations(entry)

        assert export.disclosures.run_failed is False
        assert export.disclosures.notes == [
            fold_module._CITATIONS_RUN_ENDED_WITHOUT_TERMINAL_EVENT_NOTE
        ]

    @pytest.mark.asyncio
    async def test_an_unfinished_run_raises_rather_than_returning_a_silent_partial_export(
        self,
    ) -> None:
        # Mutation that turns this red: drop the entry.finished check,
        # which would silently return whatever citations happened to have
        # arrived so far as if that were the complete export.
        entry = await _finished_entry(events=[], finished=False, cancelled=False)

        with pytest.raises(fold_module.RunNotYetFinishedError):
            fold_module.fold_citations(entry)


# ---------------------------------------------------------------------------
# Exception hierarchy.
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    def test_every_exception_this_module_raises_subclasses_fold_error(self) -> None:
        # Mutation that turns this red: raise a bare RuntimeError/
        # ValueError instead of a FoldError subclass somewhere in this
        # module, which would force a caller to catch an enumerated list
        # of unrelated types instead of this module's own single base.
        assert issubclass(fold_module.FoldTimeoutError, fold_module.FoldError)
        assert issubclass(fold_module.RunNotYetFinishedError, fold_module.FoldError)


# ===========================================================================
# The 2026-08-17 honesty round.
#
# Every arm below was written against one finding from build phase 4.3's
# judge and adversary rounds, and every one of those findings was the same
# defect wearing a different field name: THIS SURFACE REPORTED MORE
# CONFIDENCE THAN ITS EVIDENCE SUPPORTED. The governing rule the fixes hold
# to, and that these arms exist to keep held, is: aggregate toward LESS
# confidence, never more; where nothing assessed something, say so rather
# than default to the benign value; and disclose anything dropped,
# shortened, failed or truncated anywhere upstream.
#
# Each arm names, beside its assertions, the mutation that turns it red.
# Every mutation named here was RUN: the real source line was edited, this
# single arm was run and observed failing, and the line was restored. An arm
# that cannot be made to fail is not evidence, and this phase has already
# found nine arms that could not be.
# ===========================================================================


def _raw_event(event_type: str, trace_id: str, seq: int, payload: dict[str, Any]) -> Event:
    """An `Event` built WITHOUT the model validator that binds `payload` to
    its declared type's Section 2.3 model.

    `Event`'s own `_payload_matches_declared_type` validator rejects a
    malformed payload at construction, which is why the fold's defensive
    per-event branches are latent rather than live today (judge J-05's own
    reachability note says exactly this). `model_construct` is how a test
    reaches them: it is the same bypass `CitationPayload.model_copy` gives a
    future producer, and the point of a defensive branch is that it is
    correct on the day something does reach it.
    """
    return Event.model_construct(
        type=event_type,
        version="v1",
        trace_id=trace_id,
        seq=seq,
        ts=datetime.now(UTC),
        payload=payload,
    )


def _trust(**overrides: Any) -> TrustSignalPayload:
    base: dict[str, Any] = {
        "outcome": "answer",
        "risk_tier": "low",
        "grounded": True,
        "triangulated": None,
        "citation_id": None,
        "scope": "answer",
        "message": None,
        "fallback_link": None,
    }
    base.update(overrides)
    return TrustSignalPayload(**base)


def _stream_of(*payload_specs: tuple[str, Any]) -> Any:
    """Build a `run_streaming` stand-in from `(event_type, payload)` pairs,
    numbering `seq` in order. Payloads that are already `Event`s (built via
    `_raw_event`) are yielded as-is with their trace id rewritten.
    """

    async def _stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
        trace_id = query.trace_id
        for seq, (event_type, payload) in enumerate(payload_specs):
            if isinstance(payload, Event):
                yield Event.model_construct(
                    type=payload.type,
                    version="v1",
                    trace_id=trace_id,
                    seq=seq,
                    ts=datetime.now(UTC),
                    payload=payload.payload,
                )
            else:
                yield _event(event_type, trace_id, seq, payload)

    return _stream


_GUARD_OK = ("guard", GuardPayload(passed=True, category="ok", reason=None))


def _done(outcome: str = "answer") -> tuple[str, Any]:
    return (
        "done",
        DonePayload(
            total_cost_usd=0.01,
            total_tool_calls=1,
            elapsed_ms=100,
            trust_outcome=outcome,  # type: ignore[arg-type]
        ),
    )


async def _drain(registry: RunRegistry, run_id: str, *, timeout: float = 2.0) -> None:
    """Wait until the registry has finished draining `run_id`, so a
    snapshot read sees the WHOLE buffer, post-terminal events included.
    """
    entry = registry.get_run(run_id)
    deadline = asyncio.get_running_loop().time() + timeout
    while not entry.finished:
        if asyncio.get_running_loop().time() > deadline:  # pragma: no cover
            raise AssertionError("the run never finished draining")
        await asyncio.sleep(0.01)


def _notes_text(result: Any) -> str:
    return " ".join(result.disclosures.notes)


# ---------------------------------------------------------------------------
# F-4.3-A-01: an aggregate is never more reassuring than its worst input.
# ---------------------------------------------------------------------------


class TestRiskTierIsFlooredNotCollapsed:
    @pytest.mark.asyncio
    async def test_an_unknown_claim_risk_tier_is_never_reported_as_low(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # F-4.3-A-01. Mutation that turns this red, and the line that was
        # actually there: replace `_floor_risk_tier(...)` in
        # `_floor_trust_payloads` with the boolean collapse
        # `"high" if any(p.risk_tier == "high" for p in payloads) else "low"`.
        # RUN: this arm fails with riskTier == "low". `risk_tier` is a bare
        # `str` on the payload, not a two-value Literal, so that expression
        # turned EVERY non-"high" value into the most reassuring value the
        # field has, including the "unknown" this phase introduced to mean
        # "no assessment ran".
        stream = _stream_of(
            _GUARD_OK,
            ("token", TokenPayload(text="Claim one [1]. ", marker_ids=["c1"])),
            ("citation", _citation(1)),
            ("trust_signal", _trust(scope="claim", risk_tier="unknown", citation_id="c1")),
            ("token", TokenPayload(text="Claim two [2]. ", marker_ids=["c2"])),
            ("citation", _citation(2, citation_id="c2")),
            ("trust_signal", _trust(scope="claim", risk_tier="unknown", citation_id="c2")),
            _done("answer"),
        )
        _registry, run_id = _isolated_registry_and_run(monkeypatch, stream)
        result = await fold_module.fold_run(run_id)

        assert result.trust_signal.risk_tier == "unknown"

    @pytest.mark.asyncio
    async def test_an_unrecognized_risk_tier_is_never_downgraded_to_low(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The fix-by-category half of F-4.3-A-01, and the reason the fix is
        # a severity map rather than an added `elif` for "unknown". Mutation
        # that turns this red: give `_risk_tier_severity` a default of
        # `_RISK_TIER_SEVERITY["low"]` for a value not in the map, i.e.
        # treat anything unrecognized as benign. RUN: this arm fails with
        # riskTier == "low". A future "medium" or "critical" must never be
        # reported as the most reassuring tier the field has.
        #
        # The "low" signal is emitted FIRST on purpose: `min` returns the
        # first minimal element, so a mutation that merely ties the two
        # severities has to actually change the reported value for this arm
        # to be able to see it.
        stream = _stream_of(
            _GUARD_OK,
            ("token", TokenPayload(text="Claim one [1]. ", marker_ids=["c1"])),
            ("citation", _citation(1)),
            ("trust_signal", _trust(scope="claim", risk_tier="low", citation_id="c1")),
            ("trust_signal", _trust(scope="claim", risk_tier="critical", citation_id="c1")),
            _done("answer"),
        )
        _registry, run_id = _isolated_registry_and_run(monkeypatch, stream)
        result = await fold_module.fold_run(run_id)

        assert result.trust_signal.risk_tier == "critical"

    @pytest.mark.asyncio
    async def test_a_known_high_risk_is_never_hidden_behind_an_unknown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The other direction, and the one judge finding J-09 records the
        # frontend getting wrong: "unknown" must rank BETTER than "high", so
        # that mixing an unassessed claim into a run carrying a flagged one
        # cannot make the flag disappear. Mutation that turns this red: swap
        # the severities of "high" and "unknown" in `_RISK_TIER_SEVERITY`.
        # RUN: this arm fails with riskTier == "unknown", i.e. the known
        # high-risk claim vanishes.
        stream = _stream_of(
            _GUARD_OK,
            ("token", TokenPayload(text="Claim one [1]. ", marker_ids=["c1"])),
            ("citation", _citation(1)),
            ("trust_signal", _trust(scope="claim", risk_tier="unknown", citation_id="c1")),
            ("trust_signal", _trust(scope="claim", risk_tier="high", citation_id="c1")),
            _done("answer"),
        )
        _registry, run_id = _isolated_registry_and_run(monkeypatch, stream)
        result = await fold_module.fold_run(run_id)

        assert result.trust_signal.risk_tier == "high"

    @pytest.mark.asyncio
    async def test_an_answer_scope_signal_is_floored_by_a_worse_claim_scope_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The governing principle, applied to the branch structure itself.
        # Mutation that turns this red: restore the two disjoint branches
        # (`if acc.answer_trust_signal is not None: use it` / `elif
        # acc.claim_trust_signals: aggregate those`), under which an
        # answer-scope "low / answer / grounded" signal won outright and
        # every claim-scoped verdict it disagreed with was discarded. RUN:
        # this arm fails with outcome == "answer" and riskTier == "low".
        stream = _stream_of(
            _GUARD_OK,
            ("token", TokenPayload(text="Claim one [1]. ", marker_ids=["c1"])),
            ("citation", _citation(1)),
            ("trust_signal", _trust(scope="claim", outcome="flag", risk_tier="high",
                                    grounded=False, citation_id="c1")),
            ("trust_signal", _trust(scope="answer", outcome="answer", risk_tier="low",
                                    grounded=True)),
            _done("answer"),
        )
        _registry, run_id = _isolated_registry_and_run(monkeypatch, stream)
        result = await fold_module.fold_run(run_id)

        assert result.trust_signal.outcome == "flag"
        assert result.trust_signal.risk_tier == "high"
        assert result.trust_signal.grounded is False


# ---------------------------------------------------------------------------
# F-4.3-A-02: no trust assessment is ever discarded, whatever its scope.
# ---------------------------------------------------------------------------


class TestNoTrustSignalIsDiscarded:
    @pytest.mark.asyncio
    async def test_a_scopeless_trust_signal_is_folded_not_dropped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # F-4.3-A-02, the single worst shape available on this surface.
        # Mutation that turns this red: restore the two-branch routing in
        # `_consume_event` (`if scope == "answer": ... elif scope ==
        # "claim": ...`), under which a signal whose `scope` is None (a
        # contract-legal event: `scope` is optional with a None default)
        # matched neither branch, was dropped on the floor, and was replaced
        # by a MORE REASSURING synthetic signal. RUN: this arm fails on the
        # first assertion, `outcome == "flag"`, because the flag verdict was
        # discarded and a synthetic signal manufactured in its place; the
        # high risk tier, the ungrounded verdict and the warning text go
        # with it. Every field moves in the reassuring direction at once, on
        # a system whose whole moat is an honest trust signal.
        stream = _stream_of(
            _GUARD_OK,
            ("token", TokenPayload(text="A dangerous claim [1].", marker_ids=["c1"])),
            ("citation", _citation(1)),
            (
                "trust_signal",
                _trust(
                    outcome="flag",
                    risk_tier="high",
                    grounded=False,
                    scope=None,
                    message="this answer contradicts its sources",
                ),
            ),
            _done("answer"),
        )
        _registry, run_id = _isolated_registry_and_run(monkeypatch, stream)
        result = await fold_module.fold_run(run_id)

        assert result.trust_signal.outcome == "flag"
        assert result.trust_signal.risk_tier == "high"
        assert result.trust_signal.grounded is False
        assert "contradicts its sources" in (result.trust_signal.message or "")
        assert "no recognized scope" in _notes_text(result)


# ---------------------------------------------------------------------------
# F-4.3-A-03: grounding is never asserted from an assessment that never ran.
# ---------------------------------------------------------------------------


class TestGroundingIsNeverAssertedFromNothing:
    @pytest.mark.asyncio
    async def test_a_run_with_no_trust_assessment_is_not_reported_as_grounded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # F-4.3-A-03. Mutation that turns this red, and the line that was
        # actually there: in `_finalize`'s synthetic branch, replace
        # `grounded=False` with `grounded=bool(citations) and
        # acc.terminal_trust_outcome == "answer"`. RUN: this arm fails with
        # grounded is True. That line sat DIRECTLY BELOW a six-line comment
        # explaining why asserting an unassessed risk tier is a defect, and
        # then asserted an unassessed grounding verdict from nothing but
        # "at least one citation event went past". A citation existing is
        # not the answer being tied to it; deciding that is the grounding
        # step's job, and this run never ran it.
        stream = _stream_of(
            _GUARD_OK,
            ("token", TokenPayload(text="BRCA1 is a gene [1].", marker_ids=["c1"])),
            ("citation", _citation(1)),
            _done("answer"),
        )
        _registry, run_id = _isolated_registry_and_run(monkeypatch, stream)
        result = await fold_module.fold_run(run_id)

        assert result.citations, "the citation itself is still returned"
        assert result.trust_signal.grounded is False
        assert result.trust_signal.risk_tier == "unknown"
        assert "No trust assessment" in _notes_text(result)


# ---------------------------------------------------------------------------
# F-4.3-A-04 and F-4.3-A-05: an upstream failure or truncation is disclosed.
# ---------------------------------------------------------------------------


class TestUpstreamDegradationIsDisclosed:
    @pytest.mark.asyncio
    async def test_a_non_fatal_error_is_disclosed_without_leaking_its_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # F-4.3-A-04. Mutation that turns this red: drop the `else:` arm of
        # `_consume_event`'s error branch, restoring `if payload.fatal:
        # acc.fatal_error_payload = payload` with nothing for the non-fatal
        # case. RUN: this arm fails with notes == []. A run whose Layer 1
        # call failed and was skipped reported a clean, low-risk, grounded
        # answer, and the REST surface forwards the same error event so ITS
        # callers can see it.
        #
        # The second half of the arm is F-4.1-A-09's rule holding on the new
        # path: mutation, interpolate `payload.message` (or `payload.
        # source`) into the note. RUN: fails on the two substring asserts.
        stream = _stream_of(
            _GUARD_OK,
            (
                "error",
                ErrorPayload(
                    fatal=False,
                    scope="tool",
                    source="cypher_query",
                    error_class="transient",
                    message="graph unreachable at kg-internal.example:5432, layer 1 skipped",
                    retry_after_s=2,
                ),
            ),
            ("token", TokenPayload(text="Only BRCA1 is associated [1].", marker_ids=["c1"])),
            ("citation", _citation(1)),
            ("trust_signal", _trust()),
            _done("answer"),
        )
        _registry, run_id = _isolated_registry_and_run(monkeypatch, stream)
        result = await fold_module.fold_run(run_id)

        notes = _notes_text(result)
        assert "incomplete data" in notes
        assert "kg-internal.example" not in notes
        assert "cypher_query" not in notes

    @pytest.mark.asyncio
    async def test_a_truncated_tool_result_is_disclosed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # F-4.3-A-05. Mutation that turns this red: delete the
        # `tool_result` branch from `_consume_event`, which is what the
        # module used to do deliberately ("carries nothing this surface's
        # schema has a field for"). RUN: this arm fails with notes == [].
        # `ToolResultPayload.truncated` is precisely a "the data behind this
        # answer was cut short" flag, and an answer reading "only BRCA1 is
        # associated" built from a tool that saw 500 rows and returned 25 is
        # the exact shape this surface must not present as complete.
        stream = _stream_of(
            _GUARD_OK,
            (
                "tool_result",
                ToolResultPayload(
                    call_id="call-1",
                    tool="cypher_query",
                    layer="layer_1_graph",
                    status="ok",
                    summary="500 rows found, first 25 returned",
                    result_count=25,
                    truncated=True,
                ),
            ),
            ("token", TokenPayload(text="Only BRCA1 is associated [1].", marker_ids=["c1"])),
            ("citation", _citation(1)),
            ("trust_signal", _trust()),
            _done("answer"),
        )
        _registry, run_id = _isolated_registry_and_run(monkeypatch, stream)
        result = await fold_module.fold_run(run_id)

        assert "truncated by the tool itself" in _notes_text(result)

    @pytest.mark.asyncio
    async def test_an_untruncated_tool_result_discloses_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The second arm, so the one above cannot be satisfied by a note
        # that always fires. Mutation that turns this red: disclose on every
        # `tool_result` rather than on `payload.truncated`. RUN: fails.
        stream = _stream_of(
            _GUARD_OK,
            (
                "tool_result",
                ToolResultPayload(
                    call_id="call-1",
                    tool="cypher_query",
                    layer="layer_1_graph",
                    status="ok",
                    summary="1 row found",
                    result_count=1,
                    truncated=False,
                ),
            ),
            ("token", TokenPayload(text="BRCA1 is a gene [1].", marker_ids=["c1"])),
            ("citation", _citation(1)),
            ("trust_signal", _trust()),
            _done("answer"),
        )
        _registry, run_id = _isolated_registry_and_run(monkeypatch, stream)
        result = await fold_module.fold_run(run_id)

        assert result.disclosures.notes == []


# ---------------------------------------------------------------------------
# F-4.3-A-07: duplicate citation identity is resolved and disclosed.
# ---------------------------------------------------------------------------


class TestDuplicateCitationIdentity:
    @pytest.mark.asyncio
    async def test_a_duplicate_citation_id_is_dropped_and_disclosed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # F-4.3-A-07. Mutation that turns this red: delete the
        # `citation.citation_id in self.seen_ids` check from
        # `_CitationCollector.accept`. RUN: this arm fails with two
        # citations returned, both `citationId == "c1"`, carrying opposite
        # claims, `citationsOmitted: 0` and no note. The marker `[1]` then
        # resolved to two different sources asserting opposite things with
        # no way for the caller to pick, and a claim-scoped trust signal
        # naming "c1" could not be bound to either.
        contradicting = _citation(1).model_copy(
            update={
                "claim_text": "BRCA1 does NOT cause cancer",
                "source_url": "https://www.ncbi.nlm.nih.gov/gene/9999",
            }
        )
        stream = _stream_of(
            _GUARD_OK,
            ("token", TokenPayload(text="Fact [1].", marker_ids=["c1"])),
            ("citation", _citation(1)),
            ("citation", contradicting),
            ("trust_signal", _trust()),
            _done("answer"),
        )
        _registry, run_id = _isolated_registry_and_run(monkeypatch, stream)
        result = await fold_module.fold_run(run_id)

        assert [c.citation_id for c in result.citations] == ["c1"]
        assert result.disclosures.citations_omitted == 1
        assert "repeated a citation id" in _notes_text(result)

    @pytest.mark.asyncio
    async def test_a_duplicate_display_index_is_kept_but_disclosed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The other half of F-4.3-A-07: two DISTINCT citations sharing one
        # display index are real evidence, so both are returned, but the
        # marker they share is ambiguous and the caller is told so.
        # Mutation that turns this red: delete the `citation.display_index
        # in self.seen_display_indexes` check. RUN: this arm fails with no
        # note, i.e. two sources silently answering to one `[1]`.
        collision = _citation(2, citation_id="c2").model_copy(
            update={"display_index": 1}
        )
        stream = _stream_of(
            _GUARD_OK,
            ("token", TokenPayload(text="Fact [1].", marker_ids=["c1"])),
            ("citation", _citation(1)),
            ("citation", collision),
            ("trust_signal", _trust()),
            _done("answer"),
        )
        _registry, run_id = _isolated_registry_and_run(monkeypatch, stream)
        result = await fold_module.fold_run(run_id)

        assert len(result.citations) == 2
        assert "share a display index" in _notes_text(result)


# ---------------------------------------------------------------------------
# J-05: the omission note states the REAL reason.
# ---------------------------------------------------------------------------


class TestOmissionNotesStateTheRealReason:
    @pytest.mark.asyncio
    async def test_a_rejected_citation_is_not_blamed_on_the_cap(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # J-05. Mutation that turns this red: replace `_CitationCollector.
        # disclosure_notes`'s per-reason lookup with the single sentence the
        # fold used to emit for every omission, `f"{n} citation(s) beyond
        # this surface's {MAX_CITATIONS}-citation limit were omitted"`. RUN:
        # this arm fails on the "50-citation limit" assertion. Two
        # citations existed and one was REJECTED as untrustworthy, and the
        # caller was told the surface had more evidence it was withholding
        # for capacity. Those are opposite meanings on a trust surface, and
        # the second is the one a caller needs.
        off_host = _citation(2, citation_id="c2").model_dump()
        off_host["source_url"] = "https://evil.example/gene/672"
        stream = _stream_of(
            _GUARD_OK,
            ("token", TokenPayload(text="Fact one [1]. Fact two [2].", marker_ids=["c1"])),
            ("citation", _citation(1)),
            ("citation", _raw_event("citation", "t", 0, off_host)),
            ("trust_signal", _trust()),
            _done("answer"),
        )
        _registry, run_id = _isolated_registry_and_run(monkeypatch, stream)
        result = await fold_module.fold_run(run_id)

        notes = _notes_text(result)
        assert result.disclosures.citations_omitted == 1
        assert "REJECTED" in notes
        assert "50-citation limit" not in notes

    @pytest.mark.asyncio
    async def test_an_unlisted_omission_reason_is_still_disclosed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The fix-by-category arm. Build phase 4.2 paid four times for a fix
        # that was a LIST and grew a gap at the first case nobody listed, so
        # the per-reason note table has a fallback and the emission order
        # has a sorted tail. Mutation that turns this red: in
        # `disclosure_notes`, replace `_OMISSION_NOTES.get(reason,
        # _OMISSION_FALLBACK_NOTE)` with `_OMISSION_NOTES[reason]` (which
        # raises) or iterate only `_OMISSION_ORDER` (which silently drops
        # it). RUN: fails with a KeyError and with notes == [] respectively.
        collector = fold_module._CitationCollector()
        collector.events_seen = 1
        collector.omissions["some_future_reason"] = 3

        notes = collector.disclosure_notes()
        assert len(notes) == 1
        assert "3 citation(s) were omitted" in notes[0]


# ---------------------------------------------------------------------------
# F-4.3-A-08: a run with no terminal event is not an ordinary refusal.
# ---------------------------------------------------------------------------


class TestATerminalEventIsRequired:
    @pytest.mark.asyncio
    async def test_a_run_that_ends_without_a_terminal_event_says_so(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # F-4.3-A-08. Mutation that turns this red: delete the `if not
        # acc.terminal_event_seen:` block from `_finalize`. RUN: this arm
        # fails with notes == []. `_finalize` had no notion of "did a
        # terminal event actually arrive", so a run that died halfway
        # returned partial answer text plus `outcome: refuse, grounded:
        # false, notes: []`, which is IDENTICAL IN SHAPE to a legitimate
        # guardrail refusal that produced no answer. The caller could not
        # tell "the system declined to answer" from "the system died
        # halfway and handed you half an answer".
        stream = _stream_of(
            _GUARD_OK,
            ("token", TokenPayload(text="Fact one [1]. Fact two [2].", marker_ids=["c1"])),
            ("citation", _citation(1)),
        )
        _registry, run_id = _isolated_registry_and_run(monkeypatch, stream)
        result = await fold_module.fold_run(run_id)

        assert "PARTIAL" in _notes_text(result)
        assert result.trust_signal.grounded is False
        assert result.trust_signal.outcome == "refuse"

    @pytest.mark.asyncio
    async def test_an_ordinary_refusal_does_not_claim_it_ended_abnormally(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The second arm, so the one above cannot pass on a note that always
        # fires. A guardrail refusal is a run WORKING and reaches its `done`
        # event. Mutation that turns this red: set `terminal_event_seen`
        # unconditionally False, or never set it in the `done` branch. RUN:
        # fails.
        stream = _stream_of(
            (
                "guard",
                GuardPayload(passed=False, category="off_topic", reason="outside biomedicine"),
            ),
            ("trust_signal", _trust(outcome="refuse", risk_tier="unknown", grounded=False)),
            _done("refuse"),
        )
        _registry, run_id = _isolated_registry_and_run(monkeypatch, stream)
        result = await fold_module.fold_run(run_id)

        assert "PARTIAL" not in _notes_text(result)
        assert "has not finished" not in _notes_text(result)

    @pytest.mark.asyncio
    async def test_a_mid_flight_snapshot_never_claims_the_run_ended(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Judge finding J-07, the same missing fact pointed at the answer
        # text. `Query.run` is this surface's only polling read, and a poll
        # of a HEALTHY in-progress run returned the literal sentence "the
        # run ended before producing an answer" in the same response whose
        # own `finished` field said False. Mutation that turns this red:
        # drop the `run_finished` parameter's branch from
        # `_fallback_answer_text`. RUN: this arm fails on the "ended"
        # assertion.
        _registry, run_id = _isolated_registry_and_run(monkeypatch, _never_terminating_stream)
        await asyncio.sleep(0.05)

        result = await asyncio.wait_for(fold_module.fold_run_snapshot(run_id), timeout=1.0)

        assert result.finished is False
        assert "ended" not in result.answer
        assert "has not finished" in _notes_text(result)


# ---------------------------------------------------------------------------
# F-4.3-A-13: `ask` and `run` fold the same prefix of the same run.
# ---------------------------------------------------------------------------


async def _post_terminal_leak_stream(
    query: Query, context: RequestContext
) -> AsyncIterator[Event]:
    """Terminates with a refusal and then keeps emitting: answer tokens, a
    citation, and an answer-scope trust signal claiming the whole thing is
    grounded. Nothing after the terminal event is part of what this run
    answered, on either read path.
    """
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event(
        "done",
        trace_id,
        1,
        DonePayload(total_cost_usd=0.0, total_tool_calls=0, elapsed_ms=10, trust_outcome="refuse"),
    )
    yield _event("token", trace_id, 2, TokenPayload(text="POST-TERMINAL LEAKED TEXT", marker_ids=[]))
    yield _event("citation", trace_id, 3, _citation(1))
    yield _event(
        "trust_signal",
        trace_id,
        4,
        TrustSignalPayload(
            outcome="answer",
            risk_tier="low",
            grounded=True,
            triangulated=None,
            citation_id="c1",
            scope="answer",
            message=None,
            fallback_link=None,
        ),
    )


class TestTheTwoReadPathsAgree:
    @pytest.mark.asyncio
    async def test_ask_and_run_agree_on_the_same_finished_run(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # F-4.3-A-13, and the invariant this module's own comment ASSERTED
        # while it was false: the two entry points "can never silently
        # diverge on what folding means". They diverged on WHICH EVENTS
        # THEY CONSUME. `fold_run` reads `subscribe`, which stops at the
        # terminal event; `fold_run_snapshot` read `entry.events`, the whole
        # buffer including everything appended after it. Nothing tested that
        # they agree, which is exactly the shape `self-eval-loop.md` warns
        # about: a confident comment is where the next reader stops
        # checking.
        #
        # Mutation that turns this red: delete the `if acc.
        # terminal_event_seen: break` from `fold_run_snapshot`'s loop. RUN:
        # this arm fails on every assertion below at once. `ask` returned a
        # refusal and `run` returned "POST-TERMINAL LEAKED TEXT" with
        # `grounded: true` and a citation, for one run id, one second apart.
        registry, run_id = _isolated_registry_and_run(monkeypatch, _post_terminal_leak_stream)

        ask_result = await fold_module.fold_run(run_id)
        await _drain(registry, run_id)
        run_result = await fold_module.fold_run_snapshot(run_id)

        assert run_result.finished is True
        assert run_result.answer == ask_result.answer
        assert run_result.trust_signal.outcome == ask_result.trust_signal.outcome
        assert run_result.trust_signal.grounded == ask_result.trust_signal.grounded
        assert run_result.trust_signal.risk_tier == ask_result.trust_signal.risk_tier
        assert [c.citation_id for c in run_result.citations] == [
            c.citation_id for c in ask_result.citations
        ]
        assert run_result.disclosures.notes == ask_result.disclosures.notes

    @pytest.mark.asyncio
    async def test_post_terminal_content_is_never_reported_as_the_answer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The direction that matters, stated on its own so the agreement arm
        # above cannot be satisfied by making BOTH paths leak: this one is
        # false whenever `run` leaks, whatever `ask` does. Mutation that
        # turns this red: delete the terminal-event break from
        # `fold_run_snapshot`'s loop. RUN: fails on the leaked-text
        # assertion.
        registry, run_id = _isolated_registry_and_run(monkeypatch, _post_terminal_leak_stream)
        await fold_module.fold_run(run_id)
        await _drain(registry, run_id)

        run_result = await fold_module.fold_run_snapshot(run_id)
        assert "LEAKED" not in run_result.answer
        assert run_result.trust_signal.grounded is False
        assert run_result.citations == []

    @pytest.mark.asyncio
    async def test_the_citations_export_also_stops_at_the_terminal_event(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The third read path. A citation appended after the run's terminal
        # event is not part of what the run answered, so it is not part of
        # the run's citation export either, and `citations(runId:)` must not
        # hand a caller a citation `ask` and `run` both refuse to show.
        # Mutation that turns this red: delete the terminal-event break from
        # `fold_citations`'s loop. RUN: fails with one citation exported.
        registry, run_id = _isolated_registry_and_run(monkeypatch, _post_terminal_leak_stream)
        await fold_module.fold_run(run_id)
        await _drain(registry, run_id)

        export = fold_module.fold_citations(registry.get_run(run_id))
        assert export.citations == []


# ---------------------------------------------------------------------------
# J-06 / premise clause C5: the citations export discloses what it dropped.
# ---------------------------------------------------------------------------


class TestCitationsExportDisclosesEveryDrop:
    @pytest.mark.asyncio
    async def test_a_rejected_citation_makes_the_export_report_truncated(self) -> None:
        # J-06, and premise clause C5 ("anything the surface drops or
        # shortens, it says so"), which the judge graded NOT MET on this
        # operation. Mutation that turns this red, and the line that was
        # actually there: `export_truncated=citation_events_total >
        # MAX_CITATIONS`. RUN: this arm fails with exportTruncated False
        # while the export silently omits a rejected citation, and
        # `CitationsExport` carries no other field that could have said
        # otherwise.
        #
        # REPORTED, not fixed here: the caller still cannot learn WHY the
        # export is short. That needs a `disclosures` field on
        # `CitationsExport`, which lives in `types.py`, another agent's file
        # this round. `_CitationCollector.disclosure_notes()` already
        # computes the wording.
        off_host = _citation(2, citation_id="c2").model_dump()
        off_host["source_url"] = "https://evil.example/gene/672"
        events = [
            _event("citation", "t1", 0, _citation(1)),
            _raw_event("citation", "t1", 1, off_host),
            _event("citation", "t1", 2, _citation(3, citation_id="c3")),
        ]
        entry = await _finished_entry(events=events, finished=True, cancelled=False)

        export = fold_module.fold_citations(entry)

        assert len(export.citations) == 2
        assert export.export_truncated is True

    @pytest.mark.asyncio
    async def test_a_duplicate_citation_id_makes_the_export_report_truncated(self) -> None:
        # The same rule for the other drop reason, so the fix cannot be a
        # special case for one of them. Mutation that turns this red: use
        # `collector.events_seen > MAX_CITATIONS` instead of `collector.
        # omitted_total > 0`. RUN: fails.
        events = [
            _event("citation", "t1", 0, _citation(1)),
            _event("citation", "t1", 1, _citation(1)),
        ]
        entry = await _finished_entry(events=events, finished=True, cancelled=False)

        export = fold_module.fold_citations(entry)

        assert len(export.citations) == 1
        assert export.export_truncated is True


# ---------------------------------------------------------------------------
# J-08: one malformed payload degrades one event, never the whole answer.
# ---------------------------------------------------------------------------


class TestMalformedPayloadsDegradeOneEvent:
    @pytest.mark.asyncio
    async def test_a_malformed_token_payload_does_not_lose_the_whole_answer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # J-08. Mutation that turns this red: restore the bare
        # `TokenPayload(**event.payload)` construction in `_consume_event`
        # (and the same for `trust_signal`, `guard`, `error`, `done`),
        # instead of routing every branch through `_parse_payload`. RUN:
        # this arm fails with a `ValidationError` raised out of `fold_run`,
        # which on the real surface `MaskErrors` turns into "This request
        # could not be completed due to an internal error" and the WHOLE
        # answer is lost where one record could have been dropped. The fold
        # already had exactly this defensive posture on its citation branch
        # and on no other, with a docstring arguing for it at length.
        stream = _stream_of(
            _GUARD_OK,
            ("token", TokenPayload(text="Fact one [1]. ", marker_ids=["c1"])),
            ("token", _raw_event("token", "t", 0, {"text": 12345, "marker_ids": "nope"})),
            ("citation", _citation(1)),
            ("trust_signal", _trust()),
            _done("answer"),
        )
        _registry, run_id = _isolated_registry_and_run(monkeypatch, stream)
        result = await fold_module.fold_run(run_id)

        assert "Fact one" in result.answer
        assert "could not be read by this surface" in _notes_text(result)


# ---------------------------------------------------------------------------
# The surface does not truncate its own saying-so undisclosed.
# ---------------------------------------------------------------------------


class TestDisclosuresAreThemselvesDisclosed:
    def test_capping_the_note_list_discloses_the_cap(self) -> None:
        # Judge Section 1, clause C5, hole 3: `notes[:MAX_DISCLOSURE_NOTES]`
        # silently dropped disclosures on a surface whose premise is "if we
        # drop something we say so". Mutation that turns this red: restore
        # the plain slice, i.e. `return notes[:MAX_DISCLOSURE_NOTES]` in
        # `_cap_notes`. RUN: fails on the substring assertion.
        notes = [f"note {index}" for index in range(fold_module.MAX_DISCLOSURE_NOTES + 5)]
        capped = fold_module._cap_notes(notes)

        assert len(capped) == fold_module.MAX_DISCLOSURE_NOTES
        assert "further disclosure(s) did not fit" in capped[-1]

    def test_an_uncapped_note_list_is_returned_unchanged(self) -> None:
        # The second arm. Mutation that turns this red: always append the
        # cap note. RUN: fails.
        notes = ["one", "two"]
        assert fold_module._cap_notes(notes) == ["one", "two"]

    def test_truncating_the_merged_message_discloses_the_cut(self) -> None:
        # The same rule for `trust_signal.message`, which is hard-capped at
        # `TrustSignalPayload.message`'s own 500-character bound. Mutation
        # that turns this red: restore the bare `" ".join(parts)[:MAX_
        # DISCLOSURE_NOTE_LENGTH]`. RUN: fails on the marker assertion.
        merged = fold_module._merge_disclosure_messages(None, ["x" * 400, "y" * 400])

        assert len(merged) <= 500
        assert "further disclosures omitted" in merged
