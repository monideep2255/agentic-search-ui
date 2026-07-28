"""Tests for Harness.call_tier and Harness.track_cost (T-2.0-02).

Covers the success-path cost math, one-retry-on-transient-failure with
independent per-attempt metering, recoverable and unexpected failures
raising without a retry, the invalid-tier path raising before any call
attempt, track_cost's additive (never-overwriting) accumulation, the
cache_prefix placeholder threading, and the OpenRouter pricing fallback.

No real network call is made anywhere in this file: litellm.acompletion
and litellm.get_model_info are monkeypatched in every test.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import litellm
import pytest

from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness.harness import Harness, HarnessCallError
from system_03_search_agent.harness.tiers import UnknownTierError

_INPUT_PRICE = 3e-06
_OUTPUT_PRICE = 1.5e-05


def _fake_response(content: str, prompt_tokens: int, completion_tokens: int) -> SimpleNamespace:
    """A minimal stand-in for litellm's ModelResponse shape: only the
    fields call_tier actually reads (.choices[0].message.content,
    .usage.prompt_tokens, .usage.completion_tokens)."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


def _patch_price(monkeypatch: pytest.MonkeyPatch, *, raises: bool = False) -> None:
    def _get_model_info(model: str) -> dict[str, Any]:
        if raises:
            raise Exception(f"model {model!r} not in litellm's price map")
        return {"input_cost_per_token": _INPUT_PRICE, "output_cost_per_token": _OUTPUT_PRICE}

    monkeypatch.setattr(harness_module.litellm, "get_model_info", _get_model_info)


def _patch_model_env(monkeypatch: pytest.MonkeyPatch, tier_env_var: str = "GUARD_MODEL") -> str:
    monkeypatch.setenv(tier_env_var, "test-provider/test-model")
    return "test-provider/test-model"


# --- call_tier(): success path, cost computation ---


@pytest.mark.asyncio
async def test_call_tier_valid_input_computes_cost_from_usage_and_price(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_id = _patch_model_env(monkeypatch)
    _patch_price(monkeypatch)
    mock_acompletion = AsyncMock(return_value=_fake_response("hello", 100, 50))
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)

    result = await Harness(trace_id="trace-1").call_tier("guard", [{"role": "user", "content": "hi"}])

    expected_cost = 100 * _INPUT_PRICE + 50 * _OUTPUT_PRICE
    assert result.content == "hello"
    assert result.prompt_tokens == 100
    assert result.completion_tokens == 50
    assert result.call_cost_usd == pytest.approx(expected_cost)
    assert result.model_id == model_id
    assert result.tier == "guard"


@pytest.mark.asyncio
async def test_call_tier_targets_openrouter_prefixed_model(monkeypatch: pytest.MonkeyPatch) -> None:
    model_id = _patch_model_env(monkeypatch)
    _patch_price(monkeypatch)
    mock_acompletion = AsyncMock(return_value=_fake_response("hi", 1, 1))
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)

    await Harness(trace_id="trace-1").call_tier("guard", [{"role": "user", "content": "hi"}])

    called_kwargs = mock_acompletion.call_args.kwargs
    assert called_kwargs["model"] == f"openrouter/{model_id}"


@pytest.mark.asyncio
async def test_call_tier_success_meters_cost_onto_the_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_model_env(monkeypatch)
    _patch_price(monkeypatch)
    mock_acompletion = AsyncMock(return_value=_fake_response("hi", 10, 10))
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)

    harness = Harness(trace_id="trace-1")
    result = await harness.call_tier("guard", [{"role": "user", "content": "hi"}])

    assert harness.get_query_cost_usd("trace-1") == pytest.approx(result.call_cost_usd)


# --- call_tier(): cache_prefix placeholder threading ---


@pytest.mark.asyncio
async def test_call_tier_prepends_cache_prefix_as_leading_system_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_model_env(monkeypatch)
    _patch_price(monkeypatch)
    mock_acompletion = AsyncMock(return_value=_fake_response("hi", 1, 1))
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)

    await Harness(trace_id="trace-1").call_tier(
        "guard",
        [{"role": "user", "content": "hi"}],
        cache_prefix="system instructions + tool schemas + graph schema",
    )

    sent_messages = mock_acompletion.call_args.kwargs["messages"]
    assert sent_messages[0] == {
        "role": "system",
        "content": "system instructions + tool schemas + graph schema",
    }
    assert sent_messages[1] == {"role": "user", "content": "hi"}


@pytest.mark.asyncio
async def test_call_tier_missing_cache_prefix_leaves_messages_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_model_env(monkeypatch)
    _patch_price(monkeypatch)
    mock_acompletion = AsyncMock(return_value=_fake_response("hi", 1, 1))
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)

    original_messages = [{"role": "user", "content": "hi"}]
    await Harness(trace_id="trace-1").call_tier("guard", original_messages)

    assert mock_acompletion.call_args.kwargs["messages"] == original_messages


# --- call_tier(): invalid tier raises before any call attempt ---


@pytest.mark.asyncio
async def test_call_tier_invalid_tier_raises_before_any_call_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_acompletion = AsyncMock()
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)

    with pytest.raises(UnknownTierError):
        await Harness(trace_id="trace-1").call_tier("bogus", [{"role": "user", "content": "hi"}])  # type: ignore[arg-type]

    mock_acompletion.assert_not_called()


# --- call_tier(): transient failure retries once, independently metered ---


@pytest.mark.asyncio
async def test_call_tier_transient_failure_retries_once_and_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_model_env(monkeypatch)
    _patch_price(monkeypatch)
    mock_acompletion = AsyncMock(
        side_effect=[
            litellm.RateLimitError(
                message="rate limited", llm_provider="openrouter", model="test-provider/test-model"
            ),
            _fake_response("recovered", 20, 10),
        ]
    )
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)

    harness = Harness(trace_id="trace-1")
    result = await harness.call_tier("guard", [{"role": "user", "content": "hi"}])

    assert mock_acompletion.call_count == 2
    assert result.content == "recovered"
    expected_cost = 20 * _INPUT_PRICE + 10 * _OUTPUT_PRICE
    assert result.call_cost_usd == pytest.approx(expected_cost)
    # The failed first attempt billed nothing (no tokens returned by the
    # provider for a rejected request): the running total reflects exactly
    # the one successful, independently-metered attempt, never doubled.
    assert harness.get_query_cost_usd("trace-1") == pytest.approx(expected_cost)


@pytest.mark.asyncio
async def test_call_tier_transient_failure_exhausts_retry_and_raises_classified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_model_env(monkeypatch)
    _patch_price(monkeypatch)
    mock_acompletion = AsyncMock(
        side_effect=[
            litellm.RateLimitError(
                message="rate limited", llm_provider="openrouter", model="test-provider/test-model"
            ),
            litellm.RateLimitError(
                message="rate limited again",
                llm_provider="openrouter",
                model="test-provider/test-model",
            ),
        ]
    )
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)

    harness = Harness(trace_id="trace-1")
    with pytest.raises(HarnessCallError) as exc_info:
        await harness.call_tier("guard", [{"role": "user", "content": "hi"}])

    assert mock_acompletion.call_count == 2
    assert exc_info.value.error_class == "transient"
    # No successful attempt ever returned, so nothing was billed.
    assert harness.get_query_cost_usd("trace-1") == 0.0


# --- call_tier(): recoverable and unexpected failures never retry ---


@pytest.mark.asyncio
async def test_call_tier_recoverable_failure_raises_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_model_env(monkeypatch)
    _patch_price(monkeypatch)
    mock_acompletion = AsyncMock(
        side_effect=litellm.ContextWindowExceededError(
            message="too many tokens",
            llm_provider="openrouter",
            model="test-provider/test-model",
        )
    )
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)

    harness = Harness(trace_id="trace-1")
    with pytest.raises(HarnessCallError) as exc_info:
        await harness.call_tier("guard", [{"role": "user", "content": "hi"}])

    assert mock_acompletion.call_count == 1
    assert exc_info.value.error_class == "recoverable"


@pytest.mark.asyncio
async def test_call_tier_unexpected_failure_raises_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_model_env(monkeypatch)
    _patch_price(monkeypatch)
    mock_acompletion = AsyncMock(side_effect=RuntimeError("something unrelated broke"))
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)

    harness = Harness(trace_id="trace-1")
    with pytest.raises(HarnessCallError) as exc_info:
        await harness.call_tier("guard", [{"role": "user", "content": "hi"}])

    assert mock_acompletion.call_count == 1
    assert exc_info.value.error_class == "unexpected"


# --- call_tier(): pricing fallback and pricing gap ---


@pytest.mark.asyncio
async def test_call_tier_falls_back_to_local_price_table_when_litellm_has_no_price(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_model_env(monkeypatch)
    _patch_price(monkeypatch, raises=True)
    monkeypatch.setitem(
        harness_module._FALLBACK_PRICES_USD_PER_TOKEN,
        "test-provider/test-model",
        (1e-06, 2e-06),
    )
    mock_acompletion = AsyncMock(return_value=_fake_response("hi", 100, 100))
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)

    result = await Harness(trace_id="trace-1").call_tier("guard", [{"role": "user", "content": "hi"}])

    assert result.call_cost_usd == pytest.approx(100 * 1e-06 + 100 * 2e-06)


@pytest.mark.asyncio
async def test_call_tier_raises_unexpected_when_no_price_is_known_anywhere(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_model_env(monkeypatch)
    _patch_price(monkeypatch, raises=True)
    monkeypatch.setattr(harness_module, "_FALLBACK_PRICES_USD_PER_TOKEN", {})
    mock_acompletion = AsyncMock(return_value=_fake_response("hi", 100, 100))
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)

    with pytest.raises(HarnessCallError) as exc_info:
        await Harness(trace_id="trace-1").call_tier("guard", [{"role": "user", "content": "hi"}])

    assert exc_info.value.error_class == "unexpected"


# --- track_cost(): additive accumulation, never overwritten ---


def test_track_cost_accumulates_across_multiple_calls_on_the_same_trace() -> None:
    harness = Harness(trace_id="trace-1")
    harness.track_cost("trace-1", "guard", 0.001)
    harness.track_cost("trace-1", "plan", 0.002)

    assert harness.get_query_cost_usd("trace-1") == pytest.approx(0.003)


def test_track_cost_keeps_separate_traces_isolated() -> None:
    harness = Harness(trace_id="trace-1")
    harness.track_cost("trace-1", "guard", 0.001)
    harness.track_cost("trace-2", "guard", 0.005)

    assert harness.get_query_cost_usd("trace-1") == pytest.approx(0.001)
    assert harness.get_query_cost_usd("trace-2") == pytest.approx(0.005)


def test_get_query_cost_usd_missing_trace_returns_zero_not_a_keyerror() -> None:
    harness = Harness(trace_id="trace-1")
    assert harness.get_query_cost_usd("never-metered-trace") == 0.0
