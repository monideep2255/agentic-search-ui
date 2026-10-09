"""Build phase 8.7: answers that answer, sooner.

The owner's words, one arm group each:

- "The first sentence answers what I asked, or tells me the records do not
  say." Card 2, design C: after grounding, one classifier decision (Jev, the
  guard tier only when Jev fails) reads the question and the first one or
  two grounded, cited sentences. Yes: that sentence opens the answer and the
  code-built count line follows it. No, or any failure, late pick or too
  little budget: the count line opens it, as before. Only sentences the
  grounding pass accepted are ever offered, so a sentence it stripped can
  never lead.
- "The written summary arrives sooner on questions where the first draft
  leaves records out, and records are numbered in the order the list shows
  them." Card 50. Option E's server half: the listing is grounded and
  numbered before the writer call, and once the contract carries
  `placement` it is sent at once with its citations, each token placed
  "listing"; the written summary follows placed "summary". Option B: when
  the listing cannot cite a finding the writer is shown, the completeness
  draft starts beside the first draft, when both fit the cost cap at the
  answering model's price, and is dropped the moment the first leaves it
  nothing to do. Each of the seven points the plan's "What the hand merges
  must get right" names has an arm here that fails if the point is broken.

The placement arms stand in for the contract's field with a subclass of
`TokenPayload` carrying exactly the field the lead fixed: `placement`, one of
"listing" or "summary", default "summary". Another builder adds it to
`contracts/events.py`; this code works with or without it.
"""

from __future__ import annotations

import asyncio
import re
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
from system_03_search_agent.synthesis.findings import (
    SYNTH_SYSTEM_INSTRUCTION,
    build_synth_messages,
)
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
    """`TokenPayload` with the one field the contract adds in this phase."""

    placement: Literal["listing", "summary"] = "summary"


@pytest.fixture
def placement_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(graph_module, "TokenPayload", _PlacedToken)
    monkeypatch.setitem(events_module.PAYLOAD_MODEL_BY_TYPE, "token", _PlacedToken)


@pytest.fixture
def no_placement_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """The contract as it was before `placement`, whether or not today's
    `TokenPayload` carries the field: nothing may leave early."""
    monkeypatch.setattr(graph_module, "_contract_carries_placement", lambda: False)


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
    price: tuple[float, float] = (1e-6, 2e-6),
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
        lambda model: {"input_cost_per_token": price[0], "output_cost_per_token": price[1]},
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
    reader meets them: tokens placed "summary" when the contract carries
    `placement` (the listing may then arrive first), every token otherwise,
    when the listing leaves after the summary."""
    texts: list[str] = []
    for payload in _tokens(events):
        if payload.get("placement", "summary") != "summary":
            continue
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
# Card 2, design C: the lead sentence.
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
    grounding = GroundingResult(
        narrative="x",
        claims=[],
        stripped_count=0,
        refused=False,
        sentences=("NCBIGene:672 is associated with disease name number 1 [1].",),
        sentence_origins=(0,),
    )
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
# Card 2, the honest gap: wired from the decision already made, never the
# question's words, and said only when the absence is known (fix round,
# F-8.7-J01, J02, A02): the field's source read the record and found none,
# every search finished, and no shown record carries anything that might
# state it.
# ---------------------------------------------------------------------------


def _count_line(events: list) -> str:
    return next(t["text"] for t in _tokens(events) if t["text"].startswith(COUNT_LINE_START))


def _researcher() -> dict[str, object]:
    return _write_state(audience_depth="researcher")


@pytest.mark.asyncio
async def test_records_whose_features_were_never_read_leave_the_count_line_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-8.7-J02: `think.asks_features` picked "asks_features", but the five
    graph Disease rows were never read for features (no MedGen lookup ran),
    so nothing is known about them. The line is exactly develop's."""
    _models(monkeypatch)
    monkeypatch.setattr(graph_module, "_clinical_features_asked", AsyncMock(return_value=True))
    asked = _count_line((await graph_module.write_node(_researcher()))["events"])
    monkeypatch.setattr(graph_module, "_clinical_features_asked", AsyncMock(return_value=False))
    unasked = _count_line((await graph_module.write_node(_researcher()))["events"])

    assert asked == unasked, asked
    assert "clinical features" not in asked


@pytest.mark.asyncio
async def test_the_count_line_is_unchanged_when_nothing_was_asked_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _models(monkeypatch)
    monkeypatch.setattr(graph_module, "_clinical_features_asked", AsyncMock(return_value=False))

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))

    assert "clinical features" not in _count_line(result["events"])


def _medgen_lists_none_state(
    audience_depth: str, *, definition: str | None = None, failed: bool = False
) -> dict[str, object]:
    """One MedGen disease record fetched and read through the real row
    builder, listing no clinical features: the only state in which the
    product knows the record gives none."""
    from system_03_search_agent.harness.coordinator_worker import Finding
    from system_03_search_agent.tools.ncbi_efetch_schemas import (
        NcbiEfetchOutput,
        NcbiEfetchRecord,
    )

    fields: dict[str, object] = {
        "title": "Malignant tumor of breast",
        "semantictype": {"value": "Neoplastic Process"},
        "clinical_features": [],
        "clinical_features_total": 0,
    }
    if definition is not None:
        fields["definition"] = {"value": definition}
    record = NcbiEfetchRecord(
        id="651", db="medgen", fields=fields, source_url="https://www.ncbi.nlm.nih.gov/medgen/651"
    )
    output = NcbiEfetchOutput(
        status="ok",
        action="summary",
        records=[record],
        record_count=1,
        total_available=1,
        truncated=False,
    )
    rows = graph_module._ncbi_efetch_output_to_structured_fields(output, "medgen_summary")["rows"]
    state = _write_state(audience_depth=audience_depth)
    state["findings"] = [
        Finding(
            call_id="ne-medgen",
            tool="ncbi_efetch",
            layer="layer_2_api",
            source="structured_pass_through",
            structured_fields={"status": "ok", "row_count": len(rows), "rows": rows},
            extracted_entities=None,
            normalized_ids=None,
            evidence_summary=None,
        )
    ]
    if failed:
        state["failed_searches"] = [
            {
                "tool": "ncbi_efetch",
                "layer": "layer_2_ncbi",
                "reason": "search: timed out",
                "kind": "timeout",
                "source": "medgen",
            }
        ]
    return state


async def _medgen_count_line(monkeypatch: pytest.MonkeyPatch, state: dict[str, object]) -> str:
    _models(monkeypatch, first="Malignant tumor of breast [1].")
    monkeypatch.setattr(graph_module, "_clinical_features_asked", AsyncMock(return_value=True))
    result = await graph_module.write_node(state)
    return _summary_claims(result["events"])[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("depth", "line"),
    [
        (
            "researcher",
            (
                "Found 1 medgen record: Malignant tumor of breast [1], "
                "and its MedGen record lists no clinical features. "
            ),
        ),
        (
            "plain_language",
            (
                "I found 1 condition on this topic [1], "
                "and its MedGen record lists no clinical features. "
            ),
        ),
    ],
)
async def test_a_record_read_and_listing_none_is_said_to_in_both_depths(
    monkeypatch: pytest.MonkeyPatch, depth: str, line: str
) -> None:
    """The positive case, and F-8.7-A13's wording: the clause names the
    record as what lists nothing, never the condition."""
    assert await _medgen_count_line(monkeypatch, _medgen_lists_none_state(depth)) == line


@pytest.mark.asyncio
async def test_a_search_that_did_not_finish_keeps_the_count_line_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-8.7-A02: the same record, but a MedGen search of this question timed
    out. The searches' state, passed by the loop, holds the clause back."""
    state = _medgen_lists_none_state("researcher", failed=True)
    assert await _medgen_count_line(monkeypatch, state) == (
        "Found 1 medgen record: Malignant tumor of breast [1]. "
    )


@pytest.mark.asyncio
async def test_a_definition_on_the_record_keeps_the_count_line_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-8.7-J01: the record's own definition may state the features in
    prose, so the line cannot say the record gives none."""
    state = _medgen_lists_none_state(
        "researcher", definition="A cancer that presents as a breast lump with nipple discharge."
    )
    assert await _medgen_count_line(monkeypatch, state) == (
        "Found 1 medgen record: Malignant tumor of breast [1]. "
    )


def test_the_lead_options_are_closed_and_end_on_neither() -> None:
    assert decide_module.lead_sentence_options(1) == ("first", "neither")
    assert decide_module.lead_sentence_options(2) == ("first", "second", "neither")
    with pytest.raises(ValueError):
        decide_module.lead_sentence_options(3)
    # A pick naming a candidate that was not offered never leads.
    assert decide_module.lead_sentence_index("second", 1) is None
    assert decide_module.lead_sentence_index("neither", 2) is None
    assert decide_module.lead_sentence_index("second", 2) == 1


# ---------------------------------------------------------------------------
# Card 50, option E: the listing first, with its placement.
# ---------------------------------------------------------------------------

#: Opus 5.5's price per token, input and output, the writer since step 1.
OPUS_PRICE = (4e-6, 20e-6)


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


def _rows(events: list) -> list[tuple[str, tuple[str, ...], tuple[str, ...]]]:
    return [
        (t["text"], tuple(t["marker_ids"]), tuple(t.get("cells") or ()))
        for t in _tokens(events)
        if t["kind"] in ("table_row", "list_item")
    ]


def _notes(events: list) -> list[str]:
    return [t["text"] for t in _tokens(events) if t["kind"] == "note"]


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
async def test_without_the_contract_field_nothing_leaves_before_the_writer(
    monkeypatch: pytest.MonkeyPatch, no_placement_contract: None
) -> None:
    _models(monkeypatch)
    timeline = _record_timeline(monkeypatch)

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))

    writer_at = next(i for i, (kind, _) in enumerate(timeline) if kind == "writer_call")
    assert [kind for kind, _ in timeline[:writer_at]] == ["step"], timeline[:writer_at]
    assert _summary_claims(result["events"])[0].startswith(COUNT_LINE_START)


@pytest.mark.asyncio
async def test_without_the_contract_field_a_writer_failure_still_refuses_as_before(
    monkeypatch: pytest.MonkeyPatch, no_placement_contract: None
) -> None:
    _models(monkeypatch, writer_error=RuntimeError("provider went away"))

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))

    assert any(event.type == "error" for event in result["events"])
    assert _done(result["events"])["trust_outcome"] == "refuse"


# Merge point 6: the early listing's numbering. A number on screen never
# changes, by construction: the listing's claims lead the merged claims.


@pytest.mark.asyncio
async def test_a_number_shown_early_is_the_number_the_answer_ends_with(
    monkeypatch: pytest.MonkeyPatch, placement_contract: None
) -> None:
    """Record 3 is cited first in the prose. It keeps the listing's [3] in
    the prose, in its chip and everywhere else, and its citation is sent
    once, early, never again with another number."""
    _models(
        monkeypatch,
        first=(
            "Disease name number 3 is associated with NCBIGene:672 [3]. "
            "NCBIGene:672 is also associated with disease name number 1 [1]."
        ),
    )
    timeline = _record_timeline(monkeypatch)

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))

    writer_at = next(i for i, (kind, _) in enumerate(timeline) if kind == "writer_call")
    early = {
        payload.citation_id: payload.display_index  # type: ignore[attr-defined]
        for kind, payload in timeline[:writer_at]
        if kind == "citation"
    }
    final = [
        (e.payload["citation_id"], e.payload["display_index"])
        for e in result["events"]
        if e.type == "citation"
    ]
    assert len(final) == len({cid for cid, _ in final}), final
    for citation_id, number in final:
        if citation_id in early:
            assert number == early[citation_id], (citation_id, number, early)
    assert early["cq-completeness-3"] == 3, early

    prose = [
        t
        for t in _tokens(result["events"])
        if t["placement"] == "summary" and t["kind"] == "claim" and "Found" not in t["text"]
    ]
    assert prose[0]["text"] == "Disease name number 3 is associated with NCBIGene:672 [3]. "
    assert prose[0]["marker_ids"] == ["cq-completeness-3"]
    # The count line names each record by the number its row shows.
    count_line = _count_line(result["events"])
    assert re.findall(r"\[(\d+)\]", count_line) == ["1", "2", "3", "4", "5"], count_line


@pytest.mark.asyncio
async def test_without_the_contract_field_the_records_still_take_the_first_numbers(
    monkeypatch: pytest.MonkeyPatch, no_placement_contract: None
) -> None:
    """Records numbered in the order the list shows them, early send or
    not: the prose citing record 3 first no longer makes it [1]."""
    _models(
        monkeypatch,
        first="Disease name number 3 is associated with NCBIGene:672 [3].",
    )
    result = await graph_module.write_node(_write_state(audience_depth="researcher"))

    numbers = [int(re.findall(r"\[(\d+)\]", text)[0]) for text, _, _ in _rows(result["events"])]
    assert numbers == [1, 2, 3, 4, 5], numbers


# Merge point 5: one row per record, the early listing deduped exactly as the
# final answer is, since the final answer never builds it again.


@pytest.mark.asyncio
async def test_the_early_listing_is_the_listing_the_answer_would_show(
    monkeypatch: pytest.MonkeyPatch, placement_contract: None
) -> None:
    """The rows sent early are, row for row, the rows the answer shows when
    nothing is sent early: same text, same citations, same cells."""
    _models(monkeypatch)
    early = await graph_module.write_node(_write_state(audience_depth="researcher"))
    monkeypatch.setattr(graph_module, "_contract_carries_placement", lambda: False)
    late = await graph_module.write_node(_write_state(audience_depth="researcher"))

    assert _rows(early["events"]) == _rows(late["events"]), (
        _rows(early["events"]),
        _rows(late["events"]),
    )
    assert len(_rows(early["events"])) == 5


@pytest.mark.asyncio
async def test_two_claims_on_one_record_leave_early_as_one_row(
    monkeypatch: pytest.MonkeyPatch, placement_contract: None
) -> None:
    """Card 104 (#166): a repeat of a shown record joins its row. The early
    listing is built whole before any of it leaves, so a row is final when
    it is sent and never becomes one row after it was two."""
    _models(monkeypatch)
    original = graph_module.build_structured_fallback_narrative

    def _twice_for_record_1(findings: list) -> str:
        narrative = original(findings)
        first_sentence = narrative.split(". ")[0].rstrip(".") + "."
        return narrative + " " + first_sentence

    monkeypatch.setattr(graph_module, "build_structured_fallback_narrative", _twice_for_record_1)
    timeline = _record_timeline(monkeypatch)

    await graph_module.write_node(_write_state(audience_depth="researcher"))

    writer_at = next(i for i, (kind, _) in enumerate(timeline) if kind == "writer_call")
    early_rows = [
        payload
        for kind, payload in timeline[:writer_at]
        if kind == "token" and payload.kind == "table_row"  # type: ignore[attr-defined]
    ]
    first_cells = [row.cells[0] for row in early_rows]  # type: ignore[attr-defined]
    assert len(first_cells) == len(set(first_cells)) == 5, first_cells


# Merge point 7: nothing shown is taken back.


@pytest.mark.asyncio
async def test_a_writer_failing_after_the_listing_keeps_the_listing_as_the_answer(
    monkeypatch: pytest.MonkeyPatch, placement_contract: None
) -> None:
    """No refusal, no error, and a shown note saying why there is no
    summary."""
    _models(monkeypatch, writer_error=RuntimeError("provider went away"))

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))
    events = result["events"]

    assert not any(event.type == "error" for event in events)
    assert _done(events)["trust_outcome"] == "ask"
    note = graph_module._build_writer_failed_note()
    assert note in _notes(events), _notes(events)
    assert len(_rows(events)) == 5
    # Shown on the answer screen, not hidden: `AnswerScreen.tsx` hides only
    # notes matching `HIDDEN_NOTE_PATTERNS`, today this one pattern.
    assert not re.match(r"^Note: (?:one|\d+) further ", note)
    # One sentence, opening "Note:", no interior period, like card 46's.
    assert note.startswith("Note: ") and "." not in note, note


# Merge point 2: the cost limit. One path and one note, card 46's.


@pytest.mark.asyncio
async def test_a_cap_hit_on_the_writer_after_the_listing_takes_card_46s_path(
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

    assert _notes(events) == [graph_module._build_cap_list_note()], _notes(events)
    assert not hasattr(graph_module, "_build_writer_cap_note")
    narrative = "".join(t["text"] for t in _tokens(events))
    assert cost_control.PER_QUERY_CAP_PARTIAL_RESULT_NOTE not in narrative
    assert _done(events)["trust_outcome"] == "ask"
    assert len(_rows(events)) == 5


# ---------------------------------------------------------------------------
# Card 50, option B: the order of the two drafts.
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


# Merge point 1: the repair-keep rule. A second draft started beside the
# first is judged by card 88's full rule, not by the strict superset alone.


@pytest.mark.asyncio
async def test_a_second_draft_on_the_same_records_with_more_sentences_is_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _listing_cannot_cite(monkeypatch, 4)
    extra = "Disease name number 1 is also associated with NCBIGene:672 [1]."
    one_sentence = (
        "NCBIGene:672 is associated with disease name number 1 [1] "
        "and disease name number 2 [2]."
    )
    calls = _models(
        monkeypatch,
        first=one_sentence,
        second=f"{one_sentence} {extra}",
        first_delay_s=0.1,
    )

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))

    assert calls.index("second") < calls.index("first_done"), calls
    texts = [t["text"] for t in _tokens(result["events"])]
    assert any(text.startswith("Disease name number 1 is also associated") for text in texts), texts


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
    # Metered at the writer tier's full output ceiling (F-2.1-B02).
    ceiling = harness_module._TIER_MAX_TOKENS["synth"] * 2e-6
    assert harness.get_query_cost_usd(state["query"].trace_id) >= ceiling  # type: ignore[union-attr]


# Merge points 3 and 4: the second draft's cap check, at the answering
# model's price, and what a dropped draft is metered at.


@pytest.mark.asyncio
async def test_two_opus_drafts_never_start_together_under_a_25_cent_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Priced at Opus's real price, two writer calls are estimated at $0.264,
    over a 25-cent cap, so the second waits for the first and its own check
    sees the first call's real cost. The old static estimate ($0.025 a call)
    would have started both together."""
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "0.25")
    _listing_cannot_cite(monkeypatch, 4)
    calls = _models(monkeypatch, first=ANSWERING, first_delay_s=0.2, price=OPUS_PRICE)

    await graph_module.write_node(_write_state(audience_depth="researcher"))

    assert calls.count("second") == 1, calls
    assert calls.index("first_done") < calls.index("second"), calls


@pytest.mark.asyncio
async def test_two_opus_drafts_start_together_when_both_fit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "0.30")
    _listing_cannot_cite(monkeypatch, 4)
    calls = _models(monkeypatch, first=ANSWERING, first_delay_s=0.2, price=OPUS_PRICE)

    await graph_module.write_node(_write_state(audience_depth="researcher"))

    assert calls.index("second") < calls.index("first_done"), calls


def test_the_drafts_price_bounds_what_a_dropped_draft_is_metered_at() -> None:
    """A dropped draft is charged the writer tier's whole output ceiling. The
    price `_two_drafts_fit_cap` admits each draft at must be at least that,
    or a draft started and then dropped could carry a question past the cap
    that admitted it."""

    class _OpusHarness:
        def price_per_token(self, tier: str) -> tuple[float, float]:
            return OPUS_PRICE

    per_draft = cost_control.estimate_next_call_cost_usd(_OpusHarness(), "synth")  # type: ignore[arg-type]
    metered_if_dropped = harness_module._TIER_MAX_TOKENS["synth"] * OPUS_PRICE[1]
    assert per_draft >= metered_if_dropped, (per_draft, metered_if_dropped)
    assert per_draft > cost_control.estimate_call_cost_usd("synth")


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

