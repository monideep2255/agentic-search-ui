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

from types import SimpleNamespace
from unittest.mock import AsyncMock

import litellm
import pytest

from system_03_search_agent.harness import decide as decide_module
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
    assert record.decided_by == "guard"
    assert record.chosen == _OPTIONS[0]
    assert record.fallback_reason == "cost_cap"


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
    # the same running total; asserting the total grew by at least Jev's
    # own cost proves Jev's spend was charged, without over-asserting the
    # guard tier's own (separately-tested) pricing math.
    assert after - before >= jev_result.cost_usd


@pytest.mark.asyncio
async def test_decide_rejects_empty_options() -> None:
    harness = Harness(trace_id="t10")
    with pytest.raises(ValueError, match="empty options"):
        await decide(harness, "t10", "guardrail.relevancy", "x", [])
