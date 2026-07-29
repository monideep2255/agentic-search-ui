"""Tests for Harness.call_tier, Harness.track_cost (T-2.0-02), and
Harness.enforce_timeout plus the query_class to budget_s mapping (T-2.0-04).

Covers the success-path cost math, one-retry-on-transient-failure with
independent per-attempt metering, recoverable and unexpected failures
raising without a retry, the invalid-tier path raising before any call
attempt, track_cost's additive (never-overwriting) accumulation, the
cache_prefix placeholder threading, the OpenRouter pricing fallback, a
fast-completing step returning its real result under budget, a slow step
being aborted at budget_s with its underlying task actually cancelled (not
orphaned), a non-timeout failure propagating unchanged and distinguishable
from a timeout, and the query_class-to-budget_s mapping resolving all five
ThinkPayload query classes.

No real network call is made anywhere in this file: litellm.acompletion
and litellm.get_model_info are monkeypatched in every test. The
enforce_timeout tests use real, short asyncio.sleep calls rather than a
mocked clock, since a mock cannot prove a real cancellation happened.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import litellm
import pytest

from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness.harness import (
    Harness,
    HarnessCallError,
    budget_for_query_class,
)
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
            raise RuntimeError(f"model {model!r} not in litellm's price map")
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


# --- enforce_timeout(): fast step returns its real result, not a false abort ---


@pytest.mark.asyncio
async def test_enforce_timeout_fast_step_returns_real_result_within_budget() -> None:
    async def _fast_step() -> str:
        await asyncio.sleep(0.05)
        return "real-result"

    harness = Harness(trace_id="trace-1")
    result = await harness.enforce_timeout("act", _fast_step(), budget_s=1.0)

    assert result == "real-result"


# --- enforce_timeout(): slow step aborts at budget_s and raises HarnessCallError ---


@pytest.mark.asyncio
async def test_enforce_timeout_slow_step_aborts_and_raises_harness_call_error() -> None:
    async def _slow_step() -> str:
        await asyncio.sleep(1.0)
        return "should-never-return"

    harness = Harness(trace_id="trace-1")
    with pytest.raises(HarnessCallError) as exc_info:
        await harness.enforce_timeout("act", _slow_step(), budget_s=0.05)

    assert exc_info.value.error_class == "transient"
    assert exc_info.value.source == "harness.enforce_timeout:act"


@pytest.mark.asyncio
async def test_enforce_timeout_names_the_step_that_timed_out() -> None:
    async def _slow_step() -> str:
        await asyncio.sleep(1.0)
        return "should-never-return"

    harness = Harness(trace_id="trace-1")
    with pytest.raises(HarnessCallError) as think_exc:
        await harness.enforce_timeout("think", _slow_step(), budget_s=0.05)
    with pytest.raises(HarnessCallError) as act_exc:
        await harness.enforce_timeout("act", _slow_step(), budget_s=0.05)

    # Two different steps timing out are distinguishable from each other
    # by source, not just both generically "a timeout happened".
    assert think_exc.value.source == "harness.enforce_timeout:think"
    assert act_exc.value.source == "harness.enforce_timeout:act"
    assert think_exc.value.source != act_exc.value.source


# --- enforce_timeout(): the aborted coroutine's task is actually cancelled ---


@pytest.mark.asyncio
async def test_enforce_timeout_aborted_step_is_actually_cancelled_not_orphaned() -> None:
    completed = {"flag": False}

    async def _slow_step_that_flags_on_graceful_completion() -> str:
        # Only reaches the flag-set line if it runs to completion
        # uninterrupted; a real cancellation raises CancelledError inside
        # asyncio.sleep and this line is never executed.
        await asyncio.sleep(0.3)
        completed["flag"] = True
        return "should-never-return"

    harness = Harness(trace_id="trace-1")
    with pytest.raises(HarnessCallError):
        await harness.enforce_timeout(
            "act", _slow_step_that_flags_on_graceful_completion(), budget_s=0.05
        )

    # Wait past the original 0.3s sleep duration. If the underlying task
    # were left running in the background instead of being cancelled, the
    # flag would be set by now. It must not be.
    await asyncio.sleep(0.35)
    assert completed["flag"] is False


# --- enforce_timeout(): a non-timeout failure propagates unchanged ---


@pytest.mark.asyncio
async def test_enforce_timeout_non_timeout_failure_propagates_unchanged() -> None:
    class _StepSpecificError(RuntimeError):
        pass

    async def _failing_step() -> str:
        await asyncio.sleep(0.01)
        raise _StepSpecificError("this step failed for a reason unrelated to timing")

    harness = Harness(trace_id="trace-1")
    with pytest.raises(_StepSpecificError):
        await harness.enforce_timeout("act", _failing_step(), budget_s=1.0)


@pytest.mark.asyncio
async def test_enforce_timeout_call_tier_failure_inside_step_keeps_its_own_source(
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

    async def _step_calling_the_model() -> Any:
        return await harness.call_tier("guard", [{"role": "user", "content": "hi"}])

    with pytest.raises(HarnessCallError) as exc_info:
        await harness.enforce_timeout("think", _step_calling_the_model(), budget_s=5.0)

    # Distinguishable from a timeout: error_class is "recoverable" (from
    # call_tier's own classification), source stays "harness.call_tier",
    # never rewritten to "harness.enforce_timeout:think".
    assert exc_info.value.error_class == "recoverable"
    assert exc_info.value.source == "harness.call_tier"


# --- budget_for_query_class(): the five ThinkPayload query classes resolve ---


# `lookup` and `single_hop` were widened from 5.0 and 10.0 on 2026-07-29,
# with product-owner approval, after the first end-to-end run through a
# browser showed 5.0 seconds was not survivable: five warm guard calls on
# the configured model measured 719, 1380, 1433, 783, and 4615 ms, plus
# roughly 6000 ms cold, so the spread reached the old budget and queries
# died at the guardrail. The expected values here are updated to match the
# approved change, not loosened to make a failure go away; the three larger
# classes are deliberately unchanged, since nothing measured suggests they
# are tight. See `_QUERY_CLASS_BUDGET_S`'s own comment for the full record.
@pytest.mark.parametrize(
    ("query_class", "expected_budget_s"),
    [
        ("lookup", 15.0),
        ("single_hop", 20.0),
        ("aggregate", 30.0),
        ("multi_hop", 30.0),
        ("exploratory", 120.0),
    ],
)
def test_budget_for_query_class_resolves_all_five_query_classes(
    query_class: str, expected_budget_s: float
) -> None:
    assert budget_for_query_class(query_class) == expected_budget_s  # type: ignore[arg-type]


def test_budget_for_query_class_raises_value_error_for_an_unmapped_class() -> None:
    with pytest.raises(ValueError):
        budget_for_query_class("bogus_class")  # type: ignore[arg-type]
