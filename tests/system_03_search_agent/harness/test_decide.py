"""Tests for decide.py: the classifier seam between Jev and the guard tier
(build phase 8.2, card 8, DECISIONS.md 2026-09-25).

No real network call anywhere in this file. `litellm.acompletion` (the
guard tier's own transport) and `jev_client.call_jev` (Jev's transport)
are both monkeypatched in every test.

Covers, per the tickets' explicit acceptance criteria (build phase 8.2,
card 8; build phase 8.6, T-8.6-01):
    - CLASSIFIER_PROVIDER=guard (or unset): Jev is never called, and the
      guard tier decides exactly as before build phase 8.6.
    - CLASSIFIER_PROVIDER=jev: Jev is asked alone. A valid Jev choice is
      used and the guard tier is never called, not even in the background.
    - Every way Jev can fail (timeout at its 3-second total bound, HTTP
      error, malformed reply, an option outside the offered set, the cost
      cap, an unexpected error) asks the guard tier once, uses its pick,
      and records Jev's reason.
    - The wall time of a decision Jev answers is Jev's time, with no grace
      for a comparison pick added to it.
    - The cost cap is checked before each call, and Jev's cost is charged
      through Harness.track_cost.

What it deliberately omits: whether either real model decides well. The
offline comparison script measures that
(`testing/Developer/scripts/compare_classifiers.py`).
"""

from __future__ import annotations

import asyncio
import math
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import litellm
import pytest

from system_03_search_agent.harness import decide as decide_module
from system_03_search_agent.harness import jev_client as jev_client_module
from system_03_search_agent.harness.cost_control import QueryCapExceededError
from system_03_search_agent.harness.decide import decide
from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.harness.jev_client import MAX_JEV_COST_USD, JevCallError, JevResult

_OPTIONS = ["relevant", "not_relevant"]


def _fake_llm_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


def _patch_guard(monkeypatch: pytest.MonkeyPatch, *, reply: str = "relevant") -> AsyncMock:
    mock_acompletion = AsyncMock(return_value=_fake_llm_response(reply))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)
    monkeypatch.setattr(
        litellm, "get_model_info", lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6}
    )
    return mock_acompletion


def _patch_cap(monkeypatch: pytest.MonkeyPatch, *, cap_usd: str = "1.0") -> None:
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", cap_usd)


def _jev_result(choice: str = "relevant", confidence: float = 0.9) -> JevResult:
    return JevResult(
        resolved_model="typesafe/jev-1.13-20260917",
        choice=choice,
        confidence=confidence,
        probabilities={"relevant": confidence, "not_relevant": 1 - confidence},
        input_tokens=100,
        output_tokens=20,
        cost_usd=1.5e-05,
        latency_ms=285,
    )


@pytest.mark.asyncio
async def test_guard_provider_never_calls_jev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLASSIFIER_PROVIDER", raising=False)
    _patch_cap(monkeypatch)
    _patch_guard(monkeypatch, reply="relevant")
    mock_jev = AsyncMock()
    monkeypatch.setattr(decide_module, "call_jev", mock_jev)

    harness = Harness(trace_id="t1")
    record = await decide(harness, "t1", "guardrail.relevancy", "is this relevant?", _OPTIONS)

    mock_jev.assert_not_called()
    assert record.decided_by == "guard"
    assert record.chosen == "relevant"
    assert record.jev_choice is None


@pytest.mark.asyncio
async def test_explicit_guard_provider_never_calls_jev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "guard")
    _patch_cap(monkeypatch)
    _patch_guard(monkeypatch, reply="not_relevant")
    mock_jev = AsyncMock()
    monkeypatch.setattr(decide_module, "call_jev", mock_jev)

    harness = Harness(trace_id="t2")
    record = await decide(harness, "t2", "guardrail.relevancy", "x", _OPTIONS)

    mock_jev.assert_not_called()
    assert record.decided_by == "guard"
    assert record.chosen == "not_relevant"


@pytest.mark.asyncio
async def test_jev_provider_uses_jev_alone_and_never_asks_the_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """T-8.6-01: with Jev answering, the guard tier is not called at all,
    not beside Jev and not after it."""
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    _patch_cap(monkeypatch)
    mock_guard = _patch_guard(monkeypatch, reply="not_relevant")
    mock_jev = AsyncMock(return_value=_jev_result(choice="relevant", confidence=0.86))
    monkeypatch.setattr(decide_module, "call_jev", mock_jev)

    harness = Harness(trace_id="t3")
    record = await decide(harness, "t3", "guardrail.relevancy", "x", _OPTIONS)
    await asyncio.sleep(0.05)  # anything left running in the background would have started by now

    mock_jev.assert_awaited_once()
    mock_guard.assert_not_called()
    assert record.decided_by == "jev"
    assert record.chosen == "relevant"
    assert record.jev_choice == "relevant"
    assert record.jev_confidence == pytest.approx(0.86)
    assert record.jev_latency_ms == 285
    assert record.guard_choice is None
    assert record.agreed is None
    assert record.fallback_reason is None


@pytest.mark.asyncio
async def test_jev_timeout_falls_back_to_guard_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    _patch_cap(monkeypatch)
    mock_guard = _patch_guard(monkeypatch, reply="relevant")
    monkeypatch.setattr(
        decide_module,
        "call_jev",
        AsyncMock(side_effect=JevCallError("timed out", reason="timeout")),
    )

    harness = Harness(trace_id="t4")
    record = await decide(harness, "t4", "guardrail.relevancy", "x", _OPTIONS)

    assert mock_guard.call_count == 1, "the guard tier steps in once, after Jev failed"

    assert record.decided_by == "guard"
    assert record.chosen == "relevant"
    assert record.jev_choice is None
    assert record.fallback_reason == "timeout"


@pytest.mark.asyncio
async def test_jev_http_error_falls_back_to_guard_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    _patch_cap(monkeypatch)
    mock_guard = _patch_guard(monkeypatch, reply="relevant")
    monkeypatch.setattr(
        decide_module,
        "call_jev",
        AsyncMock(side_effect=JevCallError("bad status", reason="http_error")),
    )

    harness = Harness(trace_id="t5")
    record = await decide(harness, "t5", "guardrail.relevancy", "x", _OPTIONS)

    assert mock_guard.call_count == 1, "the guard tier steps in once, after Jev failed"

    assert record.decided_by == "guard"
    assert record.fallback_reason == "http_error"


@pytest.mark.asyncio
async def test_jev_malformed_reply_falls_back_to_guard_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    _patch_cap(monkeypatch)
    mock_guard = _patch_guard(monkeypatch, reply="relevant")
    monkeypatch.setattr(
        decide_module,
        "call_jev",
        AsyncMock(side_effect=JevCallError("bad shape", reason="malformed_reply")),
    )

    harness = Harness(trace_id="t6")
    record = await decide(harness, "t6", "guardrail.relevancy", "x", _OPTIONS)

    assert mock_guard.call_count == 1, "the guard tier steps in once, after Jev failed"

    assert record.decided_by == "guard"
    assert record.fallback_reason == "malformed_reply"


@pytest.mark.asyncio
async def test_jev_invalid_option_falls_back_to_guard_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    _patch_cap(monkeypatch)
    mock_guard = _patch_guard(monkeypatch, reply="relevant")
    monkeypatch.setattr(
        decide_module,
        "call_jev",
        AsyncMock(side_effect=JevCallError("not offered", reason="invalid_option")),
    )

    harness = Harness(trace_id="t7")
    record = await decide(harness, "t7", "guardrail.relevancy", "x", _OPTIONS)

    assert mock_guard.call_count == 1, "the guard tier steps in once, after Jev failed"

    assert record.decided_by == "guard"
    assert record.fallback_reason == "invalid_option"


@pytest.mark.asyncio
async def test_cost_cap_exceeded_skips_both_calls_and_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cap so low the pre-flight check refuses before any call attempt."""
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    _patch_cap(monkeypatch, cap_usd="0.0000001")
    mock_acompletion = AsyncMock(return_value=_fake_llm_response("relevant"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)
    mock_jev = AsyncMock(return_value=_jev_result())
    monkeypatch.setattr(decide_module, "call_jev", mock_jev)

    harness = Harness(trace_id="t8")
    record = await decide(harness, "t8", "guardrail.relevancy", "x", _OPTIONS)

    mock_acompletion.assert_not_called()
    mock_jev.assert_not_called()
    # Neither model made a pick: the record says so (F-8.2-A04).
    assert record.jev_choice is None and record.guard_choice is None
    assert record.chosen == _OPTIONS[0], "no default given, so the first option"
    assert record.fallback_reason == "no_usable_pick:cost_cap"


@pytest.mark.asyncio
async def test_jev_cost_is_charged_through_track_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    _patch_cap(monkeypatch)
    _patch_guard(monkeypatch, reply="relevant")
    jev_result = _jev_result()
    monkeypatch.setattr(decide_module, "call_jev", AsyncMock(return_value=jev_result))

    harness = Harness(trace_id="t9")
    before = harness.get_query_cost_usd("t9")
    await decide(harness, "t9", "guardrail.relevancy", "x", _OPTIONS)
    after = harness.get_query_cost_usd("t9")

    # Since build phase 8.6 the guard is not called when Jev answers, so the
    # only money on the trace is Jev's. The arm below still prices a guard
    # call at zero, so it holds if a guard call ever came back (F-8.2-J05).
    assert after - before == pytest.approx(jev_result.cost_usd)


@pytest.mark.asyncio
async def test_jev_cost_reaches_the_query_total_on_its_own(monkeypatch: pytest.MonkeyPatch) -> None:
    """F-8.2-J05: the per-query, per-user and system-wide caps all read this
    accumulator. The guard call is priced at zero here, so the only money
    on the trace is Jev's, and removing its `track_cost` line turns this red."""
    _jev_mode(monkeypatch)
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_fake_llm_response("relevant")))
    monkeypatch.setattr(
        litellm, "get_model_info", lambda model: {"input_cost_per_token": 0.0, "output_cost_per_token": 0.0}
    )
    jev_result = _jev_result().model_copy(update={"cost_usd": 0.0123})
    monkeypatch.setattr(decide_module, "call_jev", AsyncMock(return_value=jev_result))

    harness = Harness(trace_id="t9b")
    await decide(harness, "t9b", "guardrail.relevancy", "x", _OPTIONS)

    assert harness.get_query_cost_usd("t9b") == pytest.approx(0.0123)


@pytest.mark.asyncio
async def test_both_models_read_at_most_the_state_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """F-8.2-J06: `_STATE_MAX_CHARS` is the bound on what reaches two
    external models. A 5000-character state reaches each as 4000: Jev when
    it is asked, and the guard tier when it steps in after Jev failed."""
    _jev_mode(monkeypatch)
    mock_acompletion = _patch_guard(monkeypatch, reply="relevant")
    mock_jev = AsyncMock(side_effect=JevCallError("down", reason="http_error"))
    monkeypatch.setattr(decide_module, "call_jev", mock_jev)

    record = await decide(Harness(trace_id="t9c"), "t9c", "guardrail.relevancy", "a" * 5000, _OPTIONS)

    assert record.decided_by == "guard", "populate-check: the guard really was asked"

    assert decide_module._STATE_MAX_CHARS == 4000
    assert len(mock_jev.await_args.kwargs["state"]) == 4000
    user_turn = next(m["content"] for m in mock_acompletion.call_args.kwargs["messages"] if m["role"] == "user")
    assert len(user_turn) == 4000


@pytest.mark.parametrize("count", [16, 17])
def test_the_done_event_carries_at_most_sixteen_decisions(count: int) -> None:
    """F-8.2-J07: the multi-agent pipeline gate's maxItems on
    `DonePayload.decisions`, unguarded until now."""
    from pydantic import ValidationError

    from system_03_search_agent.contracts.events import DecisionRecord, DonePayload

    record = DecisionRecord(name="p", options=["a", "b"], chosen="a", decided_by="guard", guard_choice="a")
    fields = {
        "total_cost_usd": 0.0,
        "total_tool_calls": 0,
        "elapsed_ms": 1,
        "trust_outcome": "answer",
        "decisions": [record] * count,
    }
    if count <= 16:
        assert len(DonePayload(**fields).decisions or []) == count
    else:
        with pytest.raises(ValidationError):
            DonePayload(**fields)


@pytest.mark.asyncio
async def test_decide_rejects_empty_options() -> None:
    harness = Harness(trace_id="t10")
    with pytest.raises(ValueError, match="empty options"):
        await decide(harness, "t10", "guardrail.relevancy", "x", [])


# ---------------------------------------------------------------------------
# Builder J, F-J-03: both models are told what is being decided. Without a
# description the guard saw only option names and Jev a generic line, and
# live probes picked wrongly on three of five decision shapes.
# ---------------------------------------------------------------------------

_INSTRUCTIONS = "Decide whether the question is about biology or medicine."
_CRITERIA = {
    "relevant": "Its subject is biological or medical.",
    "not_relevant": "Its subject is something else entirely.",
}


@pytest.mark.asyncio
async def test_guard_gets_the_description_in_its_system_message_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLASSIFIER_PROVIDER", raising=False)
    _patch_cap(monkeypatch)
    mock_acompletion = _patch_guard(monkeypatch, reply="relevant")

    harness = Harness(trace_id="t11")
    await decide(
        harness,
        "t11",
        "guardrail.relevancy",
        "the person's own words",
        _OPTIONS,
        instructions=_INSTRUCTIONS,
        criteria=_CRITERIA,
    )

    messages = mock_acompletion.call_args.kwargs["messages"]
    system = next(m["content"] for m in messages if m["role"] == "system")
    user_turns = [m["content"] for m in messages if m["role"] == "user"]
    assert _INSTRUCTIONS in system
    for text in _CRITERIA.values():
        assert text in system
    # The person's text is the user turn, alone: no instruction rides with it.
    assert user_turns == ["the person's own words"]


@pytest.mark.asyncio
async def test_jev_gets_the_same_description(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    _patch_cap(monkeypatch)
    _patch_guard(monkeypatch, reply="relevant")
    mock_jev = AsyncMock(return_value=_jev_result(choice="relevant"))
    monkeypatch.setattr(decide_module, "call_jev", mock_jev)

    harness = Harness(trace_id="t12")
    await decide(
        harness,
        "t12",
        "guardrail.relevancy",
        "the person's own words",
        _OPTIONS,
        instructions=_INSTRUCTIONS,
        criteria=_CRITERIA,
    )

    kwargs = mock_jev.await_args.kwargs
    assert kwargs["state"] == "the person's own words"
    assert kwargs["instructions"] == _INSTRUCTIONS
    assert dict(kwargs["criteria"]) == _CRITERIA


@pytest.mark.asyncio
async def test_criteria_that_do_not_name_the_options_are_refused() -> None:
    harness = Harness(trace_id="t13")
    with pytest.raises(ValueError, match="criteria must name exactly"):
        await decide(
            harness,
            "t13",
            "guardrail.relevancy",
            "x",
            _OPTIONS,
            criteria={"relevant": "only one of the two"},
        )


@pytest.mark.asyncio
async def test_no_description_keeps_the_original_guard_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLASSIFIER_PROVIDER", raising=False)
    _patch_cap(monkeypatch)
    mock_acompletion = _patch_guard(monkeypatch, reply="relevant")

    await decide(Harness(trace_id="t14"), "t14", "guardrail.relevancy", "x", _OPTIONS)

    system = next(
        m["content"] for m in mock_acompletion.call_args.kwargs["messages"] if m["role"] == "system"
    )
    assert system == (
        "Answer with exactly one of the offered options and nothing else. "
        "Options: 'relevant', 'not_relevant'"
    )


# Builder J, F-J-06: the guard reply's fallback parse matches whole tokens
# only, and only when exactly one offered option is named.


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("off_topic", "off_topic"),
        ("  on_topic\n", "on_topic"),
        ("'off_topic'", "off_topic"),
        ("The answer is on_topic.", "on_topic"),
        # A JSON reply naming a field that CONTAINS an option is not a pick.
        ('{"is_off_topic": false}', None),
        # Two options named is ambiguous, whichever is listed first.
        ("not off_topic, on_topic", None),
        # F-8.2-J08: a negated option is a denial, not a pick.
        ("This is not off_topic.", None),
        ("not off_topic", None),
        ("It isn't on_topic", None),
        ("The question is clearly off_topic, nothing else.", "off_topic"),
        ("", None),
        ("ok", None),
    ],
)
def test_guard_reply_parse_is_whole_token_and_unambiguous(reply: str, expected: str | None) -> None:
    assert decide_module._parse_guard_choice(reply, ["on_topic", "off_topic"]) == expected


def test_a_negated_literature_option_is_no_pick_but_the_option_named_not_is_one() -> None:
    options = ["wants_literature", "not_literature"]
    assert decide_module._parse_guard_choice("It does not wants_literature", options) is None
    assert decide_module._parse_guard_choice("Answer: not_literature", options) == "not_literature"


# ---------------------------------------------------------------------------
# How long decide() takes (build phase 8.2 fix round, F-8.2-J03 and J04;
# rewritten for build phase 8.6, T-8.6-01).
#
# - Jev answered in time: the decision takes Jev's time. The guard tier is
#   never called, so no comparison grace is waited for.
# - Jev failed (its 3-second TOTAL bound, measured through the real
#   `call_jev` with a 5-second fake Jev, or a fast failure): the guard tier
#   is asked AFTER Jev, within the guard's own budget, and its pick decides.
# Each arm asserts the wall time; builder K's report records them.
# ---------------------------------------------------------------------------


def _patch_slow_guard(monkeypatch: pytest.MonkeyPatch, *, delay_s: float, reply: str) -> dict[str, Any]:
    seen: dict[str, Any] = {"cancelled": False, "started": False, "started_at": None}

    async def _acompletion(*_args: object, **_kwargs: object) -> SimpleNamespace:
        seen["started"] = True
        seen["started_at"] = time.monotonic()
        try:
            await asyncio.sleep(delay_s)
        except asyncio.CancelledError:
            seen["cancelled"] = True
            raise
        return _fake_llm_response(reply)

    monkeypatch.setattr(litellm, "acompletion", _acompletion)
    monkeypatch.setattr(
        litellm, "get_model_info", lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6}
    )
    return seen


def _patch_slow_jev_post(monkeypatch: pytest.MonkeyPatch, *, delay_s: float) -> None:
    """A fake Jev endpoint that answers correctly, but only after `delay_s`,
    under the REAL `call_jev`, so its own total bound is what cuts it off."""

    async def _post(*_args: object, **_kwargs: object) -> object:
        import httpx

        await asyncio.sleep(delay_s)
        return httpx.Response(200, content=b"{}")

    monkeypatch.setattr(jev_client_module, "_post", _post)


def _jev_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    _patch_cap(monkeypatch)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "jev_failure",
    [
        JevCallError("slow", reason="timeout"),
        JevCallError("500", reason="http_error"),
        JevCallError("bad shape", reason="malformed_reply"),
        JevCallError("maybe", reason="invalid_option"),
    ],
)
async def test_both_models_failing_names_no_pick_and_says_so(
    monkeypatch: pytest.MonkeyPatch, jev_failure: JevCallError
) -> None:
    """F-8.2-A04: the adversary's 16 both-failed cells each read "the guard
    chose <first option>". Now both picks are None, the reason says no pick
    was made and keeps Jev's own failure, and `chosen` is the caller's
    fail-open default."""
    _jev_mode(monkeypatch)
    _patch_guard(monkeypatch, reply="I cannot tell.")
    monkeypatch.setattr(decide_module, "call_jev", AsyncMock(side_effect=jev_failure))

    record = await decide(
        Harness(trace_id="b1"), "b1", "think.ask_back", "x", ["ask_back", "proceed"], default="proceed"
    )

    assert record.jev_choice is None and record.guard_choice is None
    assert record.agreed is None
    assert record.chosen == "proceed", "the fail-open default, not the first option"
    assert record.fallback_reason == f"no_usable_pick:{jev_failure.reason}"


@pytest.mark.asyncio
async def test_a_failed_guard_only_decision_records_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLASSIFIER_PROVIDER", raising=False)
    _patch_cap(monkeypatch)
    _patch_guard(monkeypatch, reply="")

    record = await decide(
        Harness(trace_id="b2"),
        "b2",
        "think.recent_years",
        "x",
        ["recent_unbounded", "not_applicable"],
        default="not_applicable",
    )

    assert record.guard_choice is None
    assert record.chosen == "not_applicable"
    assert record.fallback_reason == "no_usable_pick"


@pytest.mark.asyncio
async def test_a_default_outside_the_options_is_refused() -> None:
    with pytest.raises(ValueError, match="default"):
        await decide(Harness(trace_id="b3"), "b3", "p", "x", _OPTIONS, default="maybe")


@pytest.mark.asyncio
@pytest.mark.parametrize("jev_delay_s", [0.0, 0.05, 0.4])
async def test_a_decision_jev_answers_takes_jevs_time_and_no_more(
    monkeypatch: pytest.MonkeyPatch, jev_delay_s: float
) -> None:
    """T-8.6-01's measured acceptance: with a fast fake Jev the wall time of
    decide() is Jev's own time. A guard tier that would take 5 seconds is
    patched in, so any wait on it, a grace included, shows as time; it must
    not even be started."""
    _jev_mode(monkeypatch)
    seen = _patch_slow_guard(monkeypatch, delay_s=5.0, reply="not_relevant")

    async def _fast_jev(**_kwargs: object) -> JevResult:
        await asyncio.sleep(jev_delay_s)
        return _jev_result(choice="relevant")

    monkeypatch.setattr(decide_module, "call_jev", _fast_jev)

    started = time.monotonic()
    record = await decide(Harness(trace_id="w1"), "w1", "guardrail.relevancy", "x", _OPTIONS)
    elapsed = time.monotonic() - started

    assert elapsed < jev_delay_s + 0.15, elapsed
    assert record.decided_by == "jev" and record.chosen == "relevant"
    assert record.guard_choice is None and record.fallback_reason is None
    assert not seen["started"], "the guard tier must not be called when Jev answers"


@pytest.mark.asyncio
async def test_a_slow_jev_times_out_at_three_seconds_then_the_guard_decides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-8.2-J03 with T-8.6-01's order: a 5-second Jev is cut off by its own
    total bound at 3 s, and only then is the guard asked (0.2 s here)."""
    _jev_mode(monkeypatch)
    seen = _patch_slow_guard(monkeypatch, delay_s=0.2, reply="not_relevant")
    _patch_slow_jev_post(monkeypatch, delay_s=5.0)

    started = time.monotonic()
    record = await decide(Harness(trace_id="w3"), "w3", "guardrail.relevancy", "x", _OPTIONS)
    elapsed = time.monotonic() - started

    assert 3.1 <= elapsed < 3.8, elapsed
    assert seen["started_at"] is not None and seen["started_at"] - started >= 2.9, (
        "the guard is asked after Jev failed, never beside it"
    )
    assert record.decided_by == "guard"
    assert record.chosen == "not_relevant" and record.guard_choice == "not_relevant"
    assert record.fallback_reason == "timeout"


@pytest.mark.asyncio
async def test_a_failed_jev_waits_for_a_slow_guard_pick_within_its_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Jev that fails at once hands over to a guard that takes 1.5 s; the
    decision takes about the guard's time and uses its pick."""
    _jev_mode(monkeypatch)
    _patch_slow_guard(monkeypatch, delay_s=1.5, reply="not_relevant")
    monkeypatch.setattr(
        decide_module, "call_jev", AsyncMock(side_effect=JevCallError("down", reason="http_error"))
    )

    started = time.monotonic()
    record = await decide(Harness(trace_id="w4"), "w4", "guardrail.relevancy", "x", _OPTIONS)
    elapsed = time.monotonic() - started

    assert 1.4 <= elapsed < 2.0, elapsed
    assert record.decided_by == "guard" and record.guard_choice == "not_relevant"
    assert record.chosen == "not_relevant"
    assert record.fallback_reason == "http_error"


@pytest.mark.asyncio
async def test_a_jev_that_ignores_its_own_bound_is_cut_at_the_outer_net(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The judge's F-8.2-J04 shape: a Jev call that ignores its own bound
    and hangs. decide() stops waiting at `_JEV_WAIT_S`, then the guard's
    0.2-second pick decides."""
    _jev_mode(monkeypatch)
    _patch_slow_guard(monkeypatch, delay_s=0.2, reply="not_relevant")

    async def _hanging_jev(**_kwargs: object) -> JevResult:
        await asyncio.sleep(30)
        return _jev_result()

    monkeypatch.setattr(decide_module, "call_jev", _hanging_jev)

    started = time.monotonic()
    record = await decide(Harness(trace_id="w5"), "w5", "guardrail.relevancy", "x", _OPTIONS)
    elapsed = time.monotonic() - started

    assert elapsed < decide_module._JEV_WAIT_S + 0.2 + 0.5, elapsed
    assert record.decided_by == "guard" and record.guard_choice == "not_relevant"
    assert record.chosen == "not_relevant"
    assert record.fallback_reason == "timeout"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("jev_raises", "reason"),
    [
        (JevCallError("slow", reason="timeout"), "timeout"),
        (JevCallError("500", reason="http_error"), "http_error"),
        (JevCallError("bad shape", reason="malformed_reply"), "malformed_reply"),
        (JevCallError("maybe", reason="invalid_option"), "invalid_option"),
        (
            QueryCapExceededError(
                "cap", query_cost_usd=0.1, query_cap_usd=0.1, estimated_call_cost_usd=0.01
            ),
            "cost_cap",
        ),
        (RuntimeError("a bug"), "unexpected_error"),
    ],
)
async def test_every_jev_failure_asks_the_guard_once_and_records_why(
    monkeypatch: pytest.MonkeyPatch, jev_raises: BaseException, reason: str
) -> None:
    """T-8.6-01: each way Jev can fail, raised from the Jev pick itself (so
    the cost-cap arm refuses Jev alone while the guard's own check passes)."""
    _jev_mode(monkeypatch)
    mock_guard = _patch_guard(monkeypatch, reply="not_relevant")
    monkeypatch.setattr(decide_module, "_run_jev_pick", AsyncMock(side_effect=jev_raises))

    record = await decide(Harness(trace_id="f1"), "f1", "guardrail.relevancy", "x", _OPTIONS)

    assert mock_guard.call_count == 1
    assert record.decided_by == "guard" and record.chosen == "not_relevant"
    assert record.guard_choice == "not_relevant" and record.jev_choice is None
    assert record.fallback_reason == reason


_OFFERED_MAYBE = {
    "model": "typesafe/jev-1.13-20260917",
    "answers": {
        "guardrail.relevancy": {
            "type": "choice",
            "choice": "maybe",
            "probabilities": {"maybe": 1.0},
            "confidence": 1.0,
        }
    },
    "usage": {"input_tokens": 1, "output_tokens": 1, "cost": 1e-05},
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "reason"),
    [(_OFFERED_MAYBE, "invalid_option"), ({"answers": {}}, "malformed_reply")],
)
async def test_a_bad_reply_through_the_real_client_falls_back(
    monkeypatch: pytest.MonkeyPatch, body: dict[str, object], reason: str
) -> None:
    """The same fallback through the REAL `call_jev`: an option outside the
    offered set, and a reply missing its fields."""
    import json

    import httpx

    _jev_mode(monkeypatch)
    mock_guard = _patch_guard(monkeypatch, reply="relevant")
    reply = httpx.Response(200, content=json.dumps(body).encode())
    monkeypatch.setattr(jev_client_module, "_post", AsyncMock(return_value=reply))

    record = await decide(Harness(trace_id="f2"), "f2", "guardrail.relevancy", "x", _OPTIONS)

    assert mock_guard.call_count == 1
    assert record.decided_by == "guard" and record.chosen == "relevant"
    assert record.fallback_reason == reason


# Fix round (F-8.6-J10, then clamped by F-8.6-V01 and V03): a Jev reply
# that came back unusable was billed all the same. A well-formed cost at or
# under MAX_JEV_COST_USD is charged exactly as reported; a cost above the
# ceiling, or a figure that is not a finite, non-negative amount of money,
# is charged the ceiling itself, never the reported figure and never zero.
# The cost cap then applies to the guard fallback as to any call.


def _real_jev_reply(monkeypatch: pytest.MonkeyPatch, *, cost: str, choice: str = "relevant") -> None:
    """A reply through the REAL `call_jev`, whose `usage.cost` is `cost`
    written into the JSON exactly as given."""
    import json

    import httpx

    body = {
        "model": "typesafe/jev-1.13-20260917",
        "answers": {
            "guardrail.relevancy": {
                "type": "choice",
                "choice": choice,
                "probabilities": {"relevant": 0.9, "not_relevant": 0.1},
                "confidence": 0.8,
            }
        },
        "usage": {"input_tokens": 1, "output_tokens": 1, "cost": 0.0},
    }
    raw = json.dumps(body).replace('"cost": 0.0', f'"cost": {cost}')
    monkeypatch.setattr(
        jev_client_module, "_post", AsyncMock(return_value=httpx.Response(200, content=raw.encode()))
    )


def _free_guard(monkeypatch: pytest.MonkeyPatch, *, reply: str = "relevant") -> AsyncMock:
    """A guard tier priced at zero, so the only money on the trace is Jev's."""
    mock_acompletion = AsyncMock(return_value=_fake_llm_response(reply))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)
    monkeypatch.setattr(
        litellm, "get_model_info", lambda model: {"input_cost_per_token": 0.0, "output_cost_per_token": 0.0}
    )
    return mock_acompletion


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cost", "choice", "reason", "charged"),
    [
        ("0.02", "relevant", "malformed_reply", MAX_JEV_COST_USD),
        ("0.004", "maybe", "invalid_option", 0.004),
        ("Infinity", "relevant", "malformed_reply", MAX_JEV_COST_USD),
        ("NaN", "relevant", "malformed_reply", MAX_JEV_COST_USD),
        ("-0.1", "relevant", "malformed_reply", MAX_JEV_COST_USD),
    ],
    ids=[
        "above the ceiling, charged at the ceiling",
        "an option outside the set, charged",
        "infinite, not an amount",
        "not a number, not an amount",
        "negative, not an amount",
    ],
)
async def test_an_unusable_jev_reply_is_charged_at_its_reported_cost(
    monkeypatch: pytest.MonkeyPatch, cost: str, choice: str, reason: str, charged: float
) -> None:
    _jev_mode(monkeypatch)
    mock_guard = _free_guard(monkeypatch)
    _real_jev_reply(monkeypatch, cost=cost, choice=choice)
    harness = Harness(trace_id="j10-1")

    record = await decide(harness, "j10-1", "guardrail.relevancy", "x", _OPTIONS)

    assert record.decided_by == "guard" and record.fallback_reason == reason
    assert mock_guard.call_count == 1
    total = harness.get_query_cost_usd("j10-1")
    assert math.isfinite(total), "a figure that is not an amount never reaches the caps"
    assert total == pytest.approx(charged)


@pytest.mark.asyncio
async def test_the_cost_cap_still_applies_after_an_over_ceiling_charge(monkeypatch: pytest.MonkeyPatch) -> None:
    """$0.02 reported, charged at the $0.01 ceiling (F-8.6-V01) against a
    $0.005 cap: the guard fallback is refused by the cap before it is
    sent, and the fail-open default is recorded."""
    _jev_mode(monkeypatch)
    _patch_cap(monkeypatch, cap_usd="0.005")
    mock_guard = _free_guard(monkeypatch)
    _real_jev_reply(monkeypatch, cost="0.02")
    harness = Harness(trace_id="j10-2")

    record = await decide(harness, "j10-2", "guardrail.relevancy", "x", _OPTIONS, default="relevant")

    mock_guard.assert_not_called()
    assert record.fallback_reason == "no_usable_pick:malformed_reply"
    assert record.chosen == "relevant"
    assert harness.get_query_cost_usd("j10-2") == pytest.approx(MAX_JEV_COST_USD)


def test_nothing_waits_on_a_comparison_pick_any_more() -> None:
    """T-8.6-01: the comparison grace and its "not ready" marker are gone
    from the live seam, so no caller can reintroduce the wait by name."""
    assert not hasattr(decide_module, "GUARD_COMPARISON_GRACE_S")
    assert not hasattr(decide_module, "GUARD_NOT_READY")


@pytest.mark.asyncio
async def test_cancelling_a_decision_leaves_no_unretrieved_asyncio_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """F-8.2-A05: cancelling a decision in flight used to leave the inner
    gathering future holding an error nobody read, and asyncio logged it
    at ERROR on ordinary refusals."""
    import gc

    _jev_mode(monkeypatch)
    _patch_slow_guard(monkeypatch, delay_s=5.0, reply="relevant")

    async def _failing_jev(**_kwargs: object) -> JevResult:
        await asyncio.sleep(0.05)
        raise JevCallError("down", reason="http_error")

    monkeypatch.setattr(decide_module, "call_jev", _failing_jev)

    task = asyncio.create_task(decide(Harness(trace_id="w6"), "w6", "guardrail.relevancy", "x", _OPTIONS))
    await asyncio.sleep(0.2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0)
    gc.collect()
    await asyncio.sleep(0)
    assert not [r for r in caplog.records if "never retrieved" in r.getMessage()]


# ---------------------------------------------------------------------------
# Build phase 8.6, T-8.6-03: the offline comparison. `compare_models` asks
# both models side by side, and its `live_record` is the record Jev-mode
# `decide()` returns, so a loop run under the comparison takes develop's path.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", [None, "guard", "jev"])
async def test_compare_models_asks_both_whatever_the_provider(monkeypatch: pytest.MonkeyPatch, provider) -> None:
    if provider is None:
        monkeypatch.delenv("CLASSIFIER_PROVIDER", raising=False)
    else:
        monkeypatch.setenv("CLASSIFIER_PROVIDER", provider)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    _patch_cap(monkeypatch)
    mock_guard = _patch_guard(monkeypatch, reply="not_relevant")
    mock_jev = AsyncMock(return_value=_jev_result(choice="relevant", confidence=0.7))
    monkeypatch.setattr(decide_module, "call_jev", mock_jev)

    comparison = await decide_module.compare_models(
        Harness(trace_id="c1"), "c1", "guardrail.relevancy", "x", _OPTIONS,
        instructions=_INSTRUCTIONS, criteria=_CRITERIA,
    )

    mock_jev.assert_awaited_once()
    assert mock_guard.call_count == 1
    assert comparison.jev_choice == "relevant" and comparison.jev_confidence == pytest.approx(0.7)
    assert comparison.jev_probabilities == {"relevant": 0.7, "not_relevant": pytest.approx(0.3)}
    assert comparison.guard_choice == "not_relevant"
    assert comparison.agreed is False and comparison.jev_failure is None
    assert comparison.guard_latency_ms >= 0 and comparison.jev_latency_ms == 285
    # Both got the same description and the same state.
    assert mock_jev.await_args.kwargs["instructions"] == _INSTRUCTIONS
    system = next(m["content"] for m in mock_guard.call_args.kwargs["messages"] if m["role"] == "system")
    assert _INSTRUCTIONS in system


@pytest.mark.asyncio
async def test_compare_models_asks_the_two_at_the_same_time(monkeypatch: pytest.MonkeyPatch) -> None:
    _jev_mode(monkeypatch)
    _patch_slow_guard(monkeypatch, delay_s=0.4, reply="relevant")

    async def _slow_jev(**_kwargs: object) -> JevResult:
        await asyncio.sleep(0.4)
        return _jev_result(choice="relevant")

    monkeypatch.setattr(decide_module, "call_jev", _slow_jev)
    started = time.monotonic()
    comparison = await decide_module.compare_models(Harness(trace_id="c2"), "c2", "guardrail.relevancy", "x", _OPTIONS)
    elapsed = time.monotonic() - started
    assert elapsed < 0.7, f"side by side, not one after the other: {elapsed}"
    assert comparison.agreed is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("jev_side", "guard_reply", "default"),
    [
        ("answers", "not_relevant", None),
        ("answers", "", "not_relevant"),
        (JevCallError("down", reason="http_error"), "not_relevant", None),
        (JevCallError("slow", reason="timeout"), "I cannot tell.", "not_relevant"),
        (JevCallError("bad", reason="malformed_reply"), "I cannot tell.", None),
    ],
    ids=["jev picks", "jev picks, guard none", "jev fails, guard picks", "both fail, a default", "both fail"],
)
async def test_the_live_record_is_the_record_decide_returns(
    monkeypatch: pytest.MonkeyPatch, jev_side, guard_reply: str, default: str | None
) -> None:
    """The script hands the loop `live_record(default)`; it must be exactly
    what `decide()` returns in Jev mode for the same two model behaviours."""
    _jev_mode(monkeypatch)
    _patch_guard(monkeypatch, reply=guard_reply)
    if jev_side == "answers":
        monkeypatch.setattr(decide_module, "call_jev", AsyncMock(return_value=_jev_result(choice="relevant")))
    else:
        monkeypatch.setattr(decide_module, "call_jev", AsyncMock(side_effect=jev_side))

    comparison = await decide_module.compare_models(Harness(trace_id="c3"), "c3", "guardrail.relevancy", "x", _OPTIONS)
    live = await decide(Harness(trace_id="c4"), "c4", "guardrail.relevancy", "x", _OPTIONS, default=default)

    assert comparison.live_record(default) == live


def test_a_live_record_default_outside_the_options_is_refused() -> None:
    comparison = decide_module.ModelComparison(
        point="p", options=("a", "b"), jev="timeout", guard_choice=None, guard_latency_ms=0
    )
    with pytest.raises(ValueError, match="default"):
        comparison.live_record("c")


@pytest.mark.asyncio
async def test_compare_models_refuses_what_decide_refuses() -> None:
    with pytest.raises(ValueError, match="empty options"):
        await decide_module.compare_models(Harness(trace_id="c5"), "c5", "p", "x", [])
    with pytest.raises(ValueError, match="criteria must name exactly"):
        await decide_module.compare_models(
            Harness(trace_id="c6"), "c6", "p", "x", _OPTIONS, criteria={"relevant": "only one"}
        )


def test_no_live_path_names_the_offline_comparison() -> None:
    """T-8.6-03's acceptance: the comparison runs offline only. Nothing under
    `src/` but `decide.py` itself may name `compare_models`, `ModelComparison`
    or the script that calls them."""
    from pathlib import Path

    src = Path(decide_module.__file__).resolve().parents[1]
    assert src.name == "system_03_search_agent"
    offenders = [
        str(path.relative_to(src))
        for path in src.rglob("*.py")
        if path.name != "decide.py"
        and any(name in path.read_text() for name in ("compare_models", "ModelComparison", "compare_classifiers"))
    ]
    assert offenders == []
