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
