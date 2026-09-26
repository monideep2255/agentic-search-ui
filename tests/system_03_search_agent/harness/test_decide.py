"""Tests for decide.py: the classifier seam between Jev and the guard tier
(build phase 8.2, card 8, DECISIONS.md 2026-09-25).

No real network call anywhere in this file. `litellm.acompletion` (the
guard tier's own transport) and `jev_client.call_jev` (Jev's transport)
are both monkeypatched in every test.

Covers, per the ticket's explicit acceptance criteria:
    - CLASSIFIER_PROVIDER=guard (or unset): Jev is never called.
    - CLASSIFIER_PROVIDER=jev: a valid Jev choice is used and the guard
      choice is recorded.
    - Each of Jev's four failure paths (timeout, HTTP error, malformed
      reply, an option outside the offered set) falls back to the guard
      choice with the reason recorded.
    - The cost cap is checked before each call, and Jev's cost is charged
      through Harness.track_cost.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import litellm
import pytest

from system_03_search_agent.harness import decide as decide_module
from system_03_search_agent.harness import jev_client as jev_client_module
from system_03_search_agent.harness.decide import decide
from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.harness.jev_client import JevCallError, JevResult

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
async def test_jev_provider_uses_jev_choice_and_records_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    _patch_cap(monkeypatch)
    _patch_guard(monkeypatch, reply="not_relevant")
    monkeypatch.setattr(
        decide_module, "call_jev", AsyncMock(return_value=_jev_result(choice="relevant", confidence=0.86))
    )

    harness = Harness(trace_id="t3")
    record = await decide(harness, "t3", "guardrail.relevancy", "x", _OPTIONS)

    assert record.decided_by == "jev"
    assert record.chosen == "relevant"
    assert record.jev_choice == "relevant"
    assert record.jev_confidence == pytest.approx(0.86)
    assert record.guard_choice == "not_relevant"
    assert record.agreed is False
    assert record.fallback_reason is None


@pytest.mark.asyncio
async def test_jev_timeout_falls_back_to_guard_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    _patch_cap(monkeypatch)
    _patch_guard(monkeypatch, reply="relevant")
    monkeypatch.setattr(
        decide_module,
        "call_jev",
        AsyncMock(side_effect=JevCallError("timed out", reason="timeout")),
    )

    harness = Harness(trace_id="t4")
    record = await decide(harness, "t4", "guardrail.relevancy", "x", _OPTIONS)

    assert record.decided_by == "guard"
    assert record.chosen == "relevant"
    assert record.jev_choice is None
    assert record.fallback_reason == "timeout"


@pytest.mark.asyncio
async def test_jev_http_error_falls_back_to_guard_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    _patch_cap(monkeypatch)
    _patch_guard(monkeypatch, reply="relevant")
    monkeypatch.setattr(
        decide_module,
        "call_jev",
        AsyncMock(side_effect=JevCallError("bad status", reason="http_error")),
    )

    harness = Harness(trace_id="t5")
    record = await decide(harness, "t5", "guardrail.relevancy", "x", _OPTIONS)

    assert record.decided_by == "guard"
    assert record.fallback_reason == "http_error"


@pytest.mark.asyncio
async def test_jev_malformed_reply_falls_back_to_guard_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    _patch_cap(monkeypatch)
    _patch_guard(monkeypatch, reply="relevant")
    monkeypatch.setattr(
        decide_module,
        "call_jev",
        AsyncMock(side_effect=JevCallError("bad shape", reason="malformed_reply")),
    )

    harness = Harness(trace_id="t6")
    record = await decide(harness, "t6", "guardrail.relevancy", "x", _OPTIONS)

    assert record.decided_by == "guard"
    assert record.fallback_reason == "malformed_reply"


@pytest.mark.asyncio
async def test_jev_invalid_option_falls_back_to_guard_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    _patch_cap(monkeypatch)
    _patch_guard(monkeypatch, reply="relevant")
    monkeypatch.setattr(
        decide_module,
        "call_jev",
        AsyncMock(side_effect=JevCallError("not offered", reason="invalid_option")),
    )

    harness = Harness(trace_id="t7")
    record = await decide(harness, "t7", "guardrail.relevancy", "x", _OPTIONS)

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

    # Guard's own real call_tier cost plus Jev's cost_usd both landed on
    # the same running total. On its own this arm cannot tell the two apart
    # (F-8.2-J05: deleting Jev's charge left it green, because the guard
    # call alone costs more than Jev); the arm below isolates Jev's charge.
    assert after - before >= jev_result.cost_usd


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
    external models. A 5000-character state reaches each as 4000."""
    _jev_mode(monkeypatch)
    mock_acompletion = _patch_guard(monkeypatch, reply="relevant")
    mock_jev = AsyncMock(return_value=_jev_result())
    monkeypatch.setattr(decide_module, "call_jev", mock_jev)

    await decide(Harness(trace_id="t9c"), "t9c", "guardrail.relevancy", "a" * 5000, _OPTIONS)

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
# Build phase 8.2 fix round, F-8.2-J03, J04 and A12: how long decide() waits.
#
# - Jev answered in time: the guard's comparison pick gets at most
#   GUARD_COMPARISON_GRACE_S, then is recorded as not ready.
# - Jev failed (its 3-second TOTAL bound, measured through the real
#   `call_jev` with a 5-second fake Jev): the guard's pick decides, waited
#   for within the guard's own budget.
# - A guard pick that has arrived is never discarded by an outer limit.
# Each arm asserts the wall time; the fix round's report records them.
# ---------------------------------------------------------------------------


def _patch_slow_guard(monkeypatch: pytest.MonkeyPatch, *, delay_s: float, reply: str) -> dict[str, bool]:
    seen = {"cancelled": False}

    async def _acompletion(*_args: object, **_kwargs: object) -> SimpleNamespace:
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


def test_the_comparison_grace_is_at_most_one_second() -> None:
    assert 0 < decide_module.GUARD_COMPARISON_GRACE_S <= 1.0


@pytest.mark.asyncio
async def test_jev_in_time_does_not_wait_for_a_slow_guard_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _jev_mode(monkeypatch)
    seen = _patch_slow_guard(monkeypatch, delay_s=5.0, reply="not_relevant")
    monkeypatch.setattr(decide_module, "call_jev", AsyncMock(return_value=_jev_result(choice="relevant")))

    started = time.monotonic()
    record = await decide(Harness(trace_id="w1"), "w1", "guardrail.relevancy", "x", _OPTIONS)
    elapsed = time.monotonic() - started
    await asyncio.sleep(0.05)  # let the cancellation reach the call

    assert elapsed < decide_module.GUARD_COMPARISON_GRACE_S + 0.5, elapsed
    assert record.decided_by == "jev" and record.chosen == "relevant"
    assert record.guard_choice is None and record.agreed is None
    assert record.fallback_reason == decide_module.GUARD_NOT_READY
    assert seen["cancelled"], "a comparison nobody will read must stop spending"


@pytest.mark.asyncio
async def test_a_guard_comparison_inside_the_grace_is_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    _jev_mode(monkeypatch)
    _patch_slow_guard(monkeypatch, delay_s=0.3, reply="not_relevant")
    monkeypatch.setattr(decide_module, "call_jev", AsyncMock(return_value=_jev_result(choice="relevant")))

    record = await decide(Harness(trace_id="w2"), "w2", "guardrail.relevancy", "x", _OPTIONS)

    assert record.decided_by == "jev"
    assert record.guard_choice == "not_relevant" and record.agreed is False
    assert record.fallback_reason is None


@pytest.mark.asyncio
async def test_a_slow_jev_times_out_at_three_seconds_and_the_ready_guard_pick_decides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-8.2-J03 and J04 together: a 5-second Jev is cut off by its own
    total bound, and the guard pick that arrived at 0.2 s is used."""
    _jev_mode(monkeypatch)
    _patch_slow_guard(monkeypatch, delay_s=0.2, reply="not_relevant")
    _patch_slow_jev_post(monkeypatch, delay_s=5.0)

    started = time.monotonic()
    record = await decide(Harness(trace_id="w3"), "w3", "guardrail.relevancy", "x", _OPTIONS)
    elapsed = time.monotonic() - started

    assert 2.9 <= elapsed < 3.6, elapsed
    assert record.decided_by == "guard"
    assert record.chosen == "not_relevant" and record.guard_choice == "not_relevant"
    assert record.fallback_reason == "timeout"


@pytest.mark.asyncio
async def test_a_failed_jev_waits_for_a_slow_guard_pick_within_its_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _jev_mode(monkeypatch)
    _patch_slow_guard(monkeypatch, delay_s=4.0, reply="not_relevant")
    _patch_slow_jev_post(monkeypatch, delay_s=5.0)

    started = time.monotonic()
    record = await decide(Harness(trace_id="w4"), "w4", "guardrail.relevancy", "x", _OPTIONS)
    elapsed = time.monotonic() - started

    assert 3.9 <= elapsed < 4.6, elapsed
    assert record.decided_by == "guard" and record.guard_choice == "not_relevant"
    assert record.chosen == "not_relevant"


@pytest.mark.asyncio
async def test_a_guard_pick_that_arrived_is_never_discarded_by_the_outer_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The judge's F-8.2-J04 shape: a Jev call that ignores its own bound
    and hangs. decide() stops waiting at its outer net, and the guard pick
    that arrived at 0.2 s still decides."""
    _jev_mode(monkeypatch)
    _patch_slow_guard(monkeypatch, delay_s=0.2, reply="not_relevant")

    async def _hanging_jev(**_kwargs: object) -> JevResult:
        await asyncio.sleep(30)
        return _jev_result()

    monkeypatch.setattr(decide_module, "call_jev", _hanging_jev)

    started = time.monotonic()
    record = await decide(Harness(trace_id="w5"), "w5", "guardrail.relevancy", "x", _OPTIONS)
    elapsed = time.monotonic() - started

    assert elapsed < decide_module._JEV_WAIT_S + 0.5, elapsed
    assert record.decided_by == "guard" and record.guard_choice == "not_relevant"
    assert record.chosen == "not_relevant"
    assert record.fallback_reason == "timeout"


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
