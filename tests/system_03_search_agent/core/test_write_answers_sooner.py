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
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import decide as decide_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness.jev_client import JevCallError, JevResult
from system_03_search_agent.synthesis.findings import SYNTH_SYSTEM_INSTRUCTION
from system_03_search_agent.synthesis.grounding import GroundingResult

# The five-disease write state and its environment, one definition each.
from tests.system_03_search_agent.core.test_write_completeness import (  # noqa: F401
    _env,
    _fake_response,
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
# question's words.
# ---------------------------------------------------------------------------


def _count_line(events: list) -> str:
    return next(t["text"] for t in _tokens(events) if t["text"].startswith(COUNT_LINE_START))


@pytest.mark.asyncio
async def test_the_count_line_says_the_records_lack_what_was_asked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`think.asks_features` picked "asks_features", and none of the five
    disease records carries a clinical feature: the line says so."""
    _models(monkeypatch)
    monkeypatch.setattr(graph_module, "_clinical_features_asked", AsyncMock(return_value=True))

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))

    assert _count_line(result["events"]).rstrip().endswith(
        ", none of which gives clinical features."
    ), _count_line(result["events"])


@pytest.mark.asyncio
async def test_the_count_line_is_unchanged_when_nothing_was_asked_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _models(monkeypatch)
    monkeypatch.setattr(graph_module, "_clinical_features_asked", AsyncMock(return_value=False))

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))

    assert "clinical features" not in _count_line(result["events"])


def test_the_lead_options_are_closed_and_end_on_neither() -> None:
    assert decide_module.lead_sentence_options(1) == ("first", "neither")
    assert decide_module.lead_sentence_options(2) == ("first", "second", "neither")
    with pytest.raises(ValueError):
        decide_module.lead_sentence_options(3)
    # A pick naming a candidate that was not offered never leads.
    assert decide_module.lead_sentence_index("second", 1) is None
    assert decide_module.lead_sentence_index("neither", 2) is None
    assert decide_module.lead_sentence_index("second", 2) == 1
