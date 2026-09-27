"""Build phase 8.7, T-8.7-01: answers that answer, sooner.

The owner's words, one arm group each:

- "The first sentence answers what I asked, or tells me the records do not
  say." Design C: after grounding, one classifier decision (Jev, the guard
  tier only when Jev fails) reads the question and the first one or two
  grounded, cited sentences. Yes: that sentence opens the answer and the
  code-built count line follows it. No, or any failure, late pick or too
  little budget: the count line opens it, as before. Only sentences the
  grounding pass accepted are ever offered, so a sentence it stripped can
  never lead.
- "The list of records the answer is built from appears within a second of
  the last search finishing." Option E's server half: the listing is
  grounded before the writer call and sent at once with its citations,
  numbered by the listing, each token carrying `placement: "listing"`; the
  written summary follows with `placement: "summary"`. Sent early only once
  the contract carries the field (T-8.7-03), so no surface that joins text
  in arrival order reads the listing above the summary before then.
- "The written summary arrives sooner." Option B: when the listing cannot
  cite a finding the writer is shown, the completeness draft starts beside
  the first draft, and is dropped the moment the first leaves it nothing to
  do.

The placement arms stand in for T-8.7-03's field with a subclass of
`TokenPayload` carrying exactly the field the lead fixed: `placement`, one of
"listing" or "summary", default "summary".
"""

from __future__ import annotations

import asyncio
import time
from typing import Literal
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.contracts import events as events_module
from system_03_search_agent.contracts.events import TokenPayload
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import decide as decide_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness.jev_client import JevCallError, JevResult
from system_03_search_agent.synthesis import findings as findings_module
from system_03_search_agent.synthesis.findings import SYNTH_SYSTEM_INSTRUCTION, build_synth_messages
from system_03_search_agent.synthesis.grounding import GroundingResult

# The five-disease write state and its environment, one definition each.
from tests.system_03_search_agent.core.test_write_completeness import (  # noqa: F401
    _env,
    _fake_response,
    _synth_finding,
    _write_state,
)

ANSWERING = (
    "NCBIGene:672 is associated with disease name number 1 [1] and disease name number 2 [2]. "
    "Disease name number 3 is also associated with NCBIGene:672 [3]."
)
LEAD = "NCBIGene:672 is associated with disease name number 1 [1] and disease name number 2 [2]. "
COUNT_LINE_START = "Found 5 disease records"
HALLUCINATED = "NCBIGene:672 causes every cancer known [3]."
REQUIREMENT = "COMPLETENESS REQUIREMENT"
CORRECTION = "COMPLETENESS CORRECTION"


class _PlacedToken(TokenPayload):
    """`TokenPayload` with the one field T-8.7-03 adds."""

    placement: Literal["listing", "summary"] = "summary"


@pytest.fixture
def placement_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(graph_module, "TokenPayload", _PlacedToken)
    monkeypatch.setitem(events_module.PAYLOAD_MODEL_BY_TYPE, "token", _PlacedToken)


@pytest.fixture
def jev_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")


def _joined(messages: object) -> str:
    return "\n".join(m.get("content") or "" for m in messages or [])  # type: ignore[union-attr]


def _models(
    monkeypatch: pytest.MonkeyPatch,
    *,
    first: str = ANSWERING,
    second: str = ANSWERING,
    guard: str = "not an option",
    first_delay_s: float = 0.0,
    second_delay_s: float = 0.0,
    writer_error: Exception | None = None,
) -> list[str]:
    """Fake every model call by what its prompt is; returns, in order, each
    call as it starts ("first", "second", "guard") and "first_done" when
    the first draft returns."""
    calls: list[str] = []

    async def _dispatch(*_args: object, **kwargs: object):
        joined = _joined(kwargs.get("messages"))
        if REQUIREMENT in joined or CORRECTION in joined:
            calls.append("second")
            if second_delay_s:
                await asyncio.sleep(second_delay_s)
            return _fake_response(second)
        if SYNTH_SYSTEM_INSTRUCTION in joined:
            calls.append("first")
            if writer_error is not None:
                raise writer_error
            if first_delay_s:
                await asyncio.sleep(first_delay_s)
            calls.append("first_done")
            return _fake_response(first)
        calls.append("guard")
        return _fake_response(guard)

    monkeypatch.setattr(harness_module.litellm, "acompletion", AsyncMock(side_effect=_dispatch))
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )
    return calls


def _jev(
    monkeypatch: pytest.MonkeyPatch,
    *,
    choice: str | None = None,
    error: str | None = None,
    delay_s: float = 0.0,
) -> list[dict[str, object]]:
    """Fake Jev for the lead decision; returns every request it received."""
    asked: list[dict[str, object]] = []

    async def _call_jev(**kwargs: object) -> JevResult:
        asked.append(kwargs)
        if delay_s:
            await asyncio.sleep(delay_s)
        if error is not None:
            raise JevCallError(f"Jev failed: {error}", reason=error)
        options = list(kwargs["options"])  # type: ignore[arg-type]
        return JevResult(
            resolved_model="typesafe/jev-1.13",
            choice=choice or options[-1],
            confidence=0.9,
            probabilities={option: (0.9 if option == choice else 0.1) for option in options},
            input_tokens=10,
            output_tokens=1,
            cost_usd=0.00002,
            latency_ms=300,
        )

    monkeypatch.setattr(decide_module, "call_jev", _call_jev)
    return asked


def _tokens(events: list) -> list[dict]:
    return [event.payload for event in events if event.type == "token"]


def _summary_claims(events: list) -> list[str]:
    """The claim texts before the listing's first heading, in the order a
    reader meets them when the listing leaves after the summary."""
    texts: list[str] = []
    for payload in _tokens(events):
        if payload.get("kind") == "heading":
            break
        if payload.get("kind") == "claim":
            texts.append(payload["text"])
    return texts


def _done(events: list) -> dict:
    return next(event.payload for event in events if event.type == "done")


def _lead_record(events: list) -> dict | None:
    return next(
        (d for d in _done(events).get("decisions") or [] if d["name"] == "write.lead_sentence"),
        None,
    )


# ---------------------------------------------------------------------------
# Design C: the lead sentence.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_sentence_jev_picks_opens_the_answer_and_the_count_line_follows(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    _models(monkeypatch)
    asked = _jev(monkeypatch, choice="first")

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))
    claims = _summary_claims(result["events"])

    assert claims[0] == LEAD, claims
    assert claims[1].startswith(COUNT_LINE_START), claims
    # Said once, at the top, never repeated in the prose below it.
    assert sum(1 for payload in _tokens(result["events"]) if payload["text"] == LEAD) == 1
    assert len(asked) == 1
    record = _lead_record(result["events"])
    assert record is not None and record["decided_by"] == "jev" and record["chosen"] == "first"


@pytest.mark.asyncio
async def test_the_second_candidate_can_lead_and_the_first_stays_in_the_prose(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    _models(monkeypatch)
    _jev(monkeypatch, choice="second")

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))
    claims = _summary_claims(result["events"])

    assert claims[0].startswith("Disease name number 3 is also associated"), claims
    assert claims[1].startswith(COUNT_LINE_START), claims
    assert LEAD in claims, claims


@pytest.mark.asyncio
async def test_the_count_line_leads_when_jev_says_neither(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    _models(monkeypatch)
    _jev(monkeypatch, choice="neither")

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))
    claims = _summary_claims(result["events"])

    assert claims[0].startswith(COUNT_LINE_START), claims
    assert claims[1] == LEAD, claims


@pytest.mark.asyncio
async def test_the_count_line_leads_when_jev_fails_and_the_guard_makes_no_pick(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    calls = _models(monkeypatch, guard="I think the first one, maybe the second")
    _jev(monkeypatch, error="timeout")

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))

    assert _summary_claims(result["events"])[0].startswith(COUNT_LINE_START)
    assert "guard" in calls, "the guard tier is asked once Jev has failed"
    record = _lead_record(result["events"])
    assert record is not None and record["fallback_reason"].startswith("no_usable_pick")


@pytest.mark.asyncio
async def test_the_guard_tier_decides_only_when_jev_fails(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    """Phase 8.6's rule: the guard's pick stands in for a failed Jev."""
    calls = _models(monkeypatch, guard="first")
    _jev(monkeypatch, error="http_error")

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))

    assert _summary_claims(result["events"])[0] == LEAD
    assert calls.count("guard") == 1
    record = _lead_record(result["events"])
    assert record is not None and record["decided_by"] == "guard"
    assert record["fallback_reason"] == "http_error"


@pytest.mark.asyncio
async def test_jev_answering_means_the_guard_is_never_asked(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    calls = _models(monkeypatch, guard="first")
    _jev(monkeypatch, choice="neither")

    await graph_module.write_node(_write_state(audience_depth="researcher"))

    assert "guard" not in calls, calls


@pytest.mark.asyncio
async def test_a_late_pick_leaves_the_count_line_leading(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    _models(monkeypatch)
    _jev(monkeypatch, choice="first", delay_s=1.0)
    monkeypatch.setattr(graph_module, "_LEAD_DECISION_MAX_WAIT_S", 0.2)

    started = time.monotonic()
    result = await graph_module.write_node(_write_state(audience_depth="researcher"))

    assert _summary_claims(result["events"])[0].startswith(COUNT_LINE_START)
    assert time.monotonic() - started < 1.0, "the answer must not wait for a late pick"


@pytest.mark.asyncio
async def test_too_little_budget_asks_nothing(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    asked = _jev(monkeypatch, choice="first")
    finding = _synth_finding(1, "disease name number 1")
    grounding = GroundingResult(
        narrative="x",
        claims=[],
        stripped_count=0,
        refused=False,
        sentences=("NCBIGene:672 is associated with disease name number 1 [1].",),
        sentence_origins=(0,),
    )
    assert finding is not None
    harness = harness_module.Harness(trace_id="trace-budget")

    picked = await graph_module._lead_sentence_choice(
        harness, "trace-budget", "Which diseases?", grounding, budget_s=1.0
    )

    assert picked is None
    assert asked == []


@pytest.mark.asyncio
async def test_with_the_guard_deciding_alone_no_lead_decision_is_asked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLASSIFIER_PROVIDER unset: the answer does not wait on a guard call."""
    monkeypatch.delenv("CLASSIFIER_PROVIDER", raising=False)
    calls = _models(monkeypatch, guard="first")

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))

    assert "guard" not in calls, calls
    assert _summary_claims(result["events"])[0].startswith(COUNT_LINE_START)
    assert _lead_record(result["events"]) is None


@pytest.mark.asyncio
async def test_a_sentence_the_grounding_pass_stripped_is_never_offered_and_never_leads(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    _models(monkeypatch, first=f"{HALLUCINATED} {LEAD}")
    asked = _jev(monkeypatch, choice="first")

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))

    assert len(asked) == 1
    state = str(asked[0]["state"])
    assert "every cancer" not in state, state
    assert "Sentence 1: NCBIGene:672 is associated with disease name number 1" in state
    assert _summary_claims(result["events"])[0] == LEAD
    assert not any("every cancer" in payload["text"] for payload in _tokens(result["events"]))


@pytest.mark.asyncio
async def test_prose_that_grounds_nothing_offers_no_candidate(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    _models(monkeypatch, first=HALLUCINATED, second=HALLUCINATED)
    asked = _jev(monkeypatch, choice="first")

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))

    assert asked == []
    assert _summary_claims(result["events"])[0].startswith(COUNT_LINE_START)
    assert not any("every cancer" in payload["text"] for payload in _tokens(result["events"]))


# ---------------------------------------------------------------------------
# Option E: the listing first, with its placement.
# ---------------------------------------------------------------------------


def _record_timeline(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, object]]:
    """Every live event, and a marker each time a writer call starts."""
    timeline: list[tuple[str, object]] = []
    original_emit_live = graph_module._EventSink.emit_live
    original_dispatch = graph_module._dispatch_tier_call

    def _emit_live(self, event_type: str, payload: object):
        timeline.append((event_type, payload))
        return original_emit_live(self, event_type, payload)

    async def _dispatch(*args: object, **kwargs: object):
        if len(args) > 2 and args[2] == "synth":
            timeline.append(("writer_call", None))
        return await original_dispatch(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(graph_module._EventSink, "emit_live", _emit_live)
    monkeypatch.setattr(graph_module, "_dispatch_tier_call", _dispatch)
    return timeline


@pytest.mark.asyncio
async def test_the_listing_leaves_before_the_writer_is_called_placed_as_the_listing(
    monkeypatch: pytest.MonkeyPatch, placement_contract: None
) -> None:
    _models(monkeypatch)
    timeline = _record_timeline(monkeypatch)

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))

    writer_at = next(i for i, (kind, _) in enumerate(timeline) if kind == "writer_call")
    before = timeline[:writer_at]
    early_tokens = [payload for kind, payload in before if kind == "token"]
    early_citations = [payload for kind, payload in before if kind == "citation"]
    assert early_tokens, "the listing must leave before the writer is called"
    assert all(token.placement == "listing" for token in early_tokens)  # type: ignore[attr-defined]
    assert {token.kind for token in early_tokens} >= {"heading", "table_row"}  # type: ignore[attr-defined]
    # Its citations go with it, numbered by the listing: 1 to 5 in order.
    assert [c.display_index for c in early_citations] == [1, 2, 3, 4, 5]  # type: ignore[attr-defined]

    tokens = _tokens(result["events"])
    summary = [t for t in tokens if t["placement"] == "summary"]
    assert summary and summary[0]["text"].startswith(COUNT_LINE_START), summary
    assert all(t["kind"] in ("claim", "paragraph_break", "heading") for t in summary)
    # No listing row is ever sent twice, and every citation is sent once.
    rows = [t["text"] for t in tokens if t["kind"] == "table_row"]
    assert len(rows) == len(set(rows)) == 5, rows
    citation_ids = [e.payload["citation_id"] for e in result["events"] if e.type == "citation"]
    assert len(citation_ids) == len(set(citation_ids)), citation_ids


@pytest.mark.asyncio
async def test_notes_follow_the_listing(
    monkeypatch: pytest.MonkeyPatch, placement_contract: None
) -> None:
    _models(monkeypatch)
    result = await graph_module.write_node(_write_state(audience_depth="plain_language"))

    notes = [t for t in _tokens(result["events"]) if t["kind"] == "note"]
    assert notes, "a Plain language answer ends on its medical-advice note"
    assert all(t["placement"] == "listing" for t in notes)


@pytest.mark.asyncio
async def test_the_prose_is_numbered_by_the_listing(
    monkeypatch: pytest.MonkeyPatch, placement_contract: None
) -> None:
    """Record 3 is cited first in the prose; it keeps the listing's [3]."""
    _models(
        monkeypatch,
        first=(
            "Disease name number 3 is associated with NCBIGene:672 [3]. "
            "NCBIGene:672 is also associated with disease name number 1 [1]."
        ),
    )
    result = await graph_module.write_node(_write_state(audience_depth="researcher"))

    prose = [
        t for t in _tokens(result["events"])
        if t["placement"] == "summary" and t["kind"] == "claim" and "Found" not in t["text"]
    ]
    assert prose[0]["text"] == "Disease name number 3 is associated with NCBIGene:672 [3]. "
    assert prose[0]["marker_ids"] == ["cq-completeness-3"]
    by_id = {
        e.payload["citation_id"]: e.payload["display_index"]
        for e in result["events"]
        if e.type == "citation"
    }
    assert by_id["cq-completeness-3"] == 3


@pytest.mark.asyncio
async def test_without_the_contract_field_nothing_leaves_before_the_writer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _models(monkeypatch)
    timeline = _record_timeline(monkeypatch)

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))

    writer_at = next(i for i, (kind, _) in enumerate(timeline) if kind == "writer_call")
    assert [kind for kind, _ in timeline[:writer_at]] == ["step"], timeline[:writer_at]
    assert _summary_claims(result["events"])[0].startswith(COUNT_LINE_START)


@pytest.mark.asyncio
async def test_a_writer_failing_after_the_listing_keeps_the_listing_as_the_answer(
    monkeypatch: pytest.MonkeyPatch, placement_contract: None
) -> None:
    """Nothing shown is taken back: no refusal, no error, and a note."""
    _models(monkeypatch, writer_error=RuntimeError("provider went away"))

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))
    events = result["events"]

    assert not any(event.type == "error" for event in events)
    assert _done(events)["trust_outcome"] == "ask"
    notes = [t["text"] for t in _tokens(events) if t["kind"] == "note"]
    assert graph_module._build_writer_failed_note() in notes, notes
    assert sum(1 for t in _tokens(events) if t["kind"] == "table_row") == 5


@pytest.mark.asyncio
async def test_a_cap_hit_on_the_writer_after_the_listing_keeps_the_listing(
    monkeypatch: pytest.MonkeyPatch, placement_contract: None
) -> None:
    _models(monkeypatch)
    real_check = cost_control.check_per_query_cap

    def _check(harness, trace_id, tier, **kwargs):
        if tier == "synth":
            raise cost_control.QueryCapExceededError(
                "cap", query_cost_usd=1.0, query_cap_usd=1.0, estimated_call_cost_usd=0.1
            )
        return real_check(harness, trace_id, tier, **kwargs)

    monkeypatch.setattr(graph_module.cost_control, "check_per_query_cap", _check)

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))
    events = result["events"]

    notes = [t["text"] for t in _tokens(events) if t["kind"] == "note"]
    assert graph_module._build_writer_cap_note() in notes, notes
    assert _done(events)["trust_outcome"] == "ask"
    assert sum(1 for t in _tokens(events) if t["kind"] == "table_row") == 5


@pytest.mark.asyncio
async def test_without_the_contract_field_a_writer_failure_still_refuses_as_before(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _models(monkeypatch, writer_error=RuntimeError("provider went away"))

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))

    assert any(event.type == "error" for event in result["events"])
    assert _done(result["events"])["trust_outcome"] == "refuse"


# ---------------------------------------------------------------------------
# Option B: the order of the two drafts.
# ---------------------------------------------------------------------------


def _listing_cannot_cite(monkeypatch: pytest.MonkeyPatch, ref: int) -> None:
    """The listing builder skips one finding, standing in for a value the
    exact check strips or a view the listing folds into its record."""
    original = graph_module.build_structured_fallback_narrative
    monkeypatch.setattr(
        graph_module,
        "build_structured_fallback_narrative",
        lambda findings: original([f for f in findings if f.ref_index != ref]),
    )


@pytest.mark.asyncio
async def test_one_draft_when_the_listing_cites_every_finding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _models(monkeypatch)

    await graph_module.write_node(_write_state(audience_depth="researcher"))

    assert calls.count("first") == 1 and "second" not in calls, calls


@pytest.mark.asyncio
async def test_the_second_draft_starts_beside_the_first_when_the_listing_cannot_cite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first draft leaves finding 4 out, the listing cannot cite it, so
    the second draft has a job, and it was already running."""
    _listing_cannot_cite(monkeypatch, 4)
    calls = _models(
        monkeypatch,
        first=ANSWERING,
        second=ANSWERING + " Disease name number 4 is associated with NCBIGene:672 [4].",
        first_delay_s=0.2,
    )

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))

    assert calls.count("first") == 1 and calls.count("second") == 1, calls
    # Both were in flight together: the second started before the first returned.
    assert calls.index("second") < calls.index("first_done"), calls
    assert any("disease name number 4" in t["text"].lower() for t in _tokens(result["events"]))


@pytest.mark.asyncio
async def test_an_unneeded_second_draft_is_dropped_and_never_waited_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first draft cites the one finding the listing cannot, so the
    second draft has nothing to do: it is stopped, the answer does not wait
    for it, and its cancelled call is still metered."""
    _listing_cannot_cite(monkeypatch, 3)
    calls = _models(monkeypatch, first=ANSWERING, second=ANSWERING, second_delay_s=5.0)

    state = _write_state(audience_depth="researcher")
    started = time.monotonic()
    await graph_module.write_node(state)

    assert "second" in calls, calls
    assert time.monotonic() - started < 3.0, "the answer must not wait on a dropped draft"
    harness = state["harness"]
    assert harness not in graph_module._SECOND_DRAFTS  # type: ignore[operator]
    assert harness.get_query_cost_usd(state["query"].trace_id) > 0.0  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_two_drafts_start_together_only_when_both_fit_the_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With room for one more writer call but not two, the second waits for
    the first, so its own cap check sees the first call's real cost."""
    estimate = cost_control.estimate_call_cost_usd("synth")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", str(estimate * 1.5))
    _listing_cannot_cite(monkeypatch, 4)
    calls = _models(monkeypatch, first=ANSWERING, first_delay_s=0.2)

    await graph_module.write_node(_write_state(audience_depth="researcher"))

    assert calls.count("second") == 1, calls
    assert calls.index("first_done") < calls.index("second"), calls


def test_the_second_draft_leaves_the_stable_prefix_byte_identical() -> None:
    """Prompt-cache discipline: the directive rides in the dynamic suffix."""
    findings = [_synth_finding(index, f"disease name number {index}") for index in (1, 2, 3)]
    plain = build_synth_messages("Which diseases?", findings, "researcher")
    beside = build_synth_messages(
        "Which diseases?",
        findings,
        "researcher",
        completeness_directive=findings_module.build_listing_gap_directive(findings[2:]),
    )
    assert plain[0] == beside[0]
    assert beside[1]["content"].startswith(plain[1]["content"])
    assert REQUIREMENT in beside[1]["content"]
    assert "previous answer" not in findings_module.build_listing_gap_directive(findings)
