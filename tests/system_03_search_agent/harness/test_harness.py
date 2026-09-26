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
    UnknownStepError,
    budget_for_query_class,
    budget_for_step,
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


# --- _TIER_REASONING["synth"]: product-owner decision, 2026-09-14 ---


def test_synth_reasoning_effort_is_none() -> None:
    """Synth reasoning is OFF, product-owner decision of 2026-09-14.

    At effort "low" the synth model intermittently spent its whole
    4000-token ceiling on reasoning, returned `finish_reason: length` with
    empty or truncated content, and ran 20 to 45 seconds against the write
    step's 45-second budget: 3 of 25 flagship runs on develop, and 2 of 6
    direct probe calls. At "none" the same prompt finished 6 of 6 in 5.2 to
    7.2 seconds. Full measurement:
    testing/Developer/reports/2026-09-14_answer_quality/report.md.

    This is the direct regression guard on that decision: a revert to
    "low" (or any other value) must fail this test, not just a live run
    three queries later.
    """
    assert harness_module._TIER_REASONING["synth"] == {"effort": "none"}


@pytest.mark.asyncio
async def test_call_tier_sends_synth_reasoning_effort_none_to_litellm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Populate check: the configured value above must reach the actual
    LiteLLM call, not merely sit correctly in the dict `call_tier` reads
    from. `call_tier` passes `reasoning=_TIER_REASONING[tier]` straight
    through to `litellm.acompletion` (harness.py); this proves that wiring
    for the synth tier specifically, with a faked `acompletion` standing in
    for the network call.
    """
    _patch_model_env(monkeypatch, "SYNTH_MODEL")
    _patch_price(monkeypatch)
    mock_acompletion = AsyncMock(return_value=_fake_response("hi", 10, 10))
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)

    await Harness(trace_id="trace-1").call_tier("synth", [{"role": "user", "content": "hi"}])

    assert mock_acompletion.call_args.kwargs["reasoning"] == {"effort": "none"}


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


# --- budget_for_step(): per-step, per-tier timeouts ---
#
# The property that matters is not the specific numbers, which are
# provisional and model-dependent, but the SHAPE: a model-calling step is
# bounded by its own tier and does not inherit a looser budget just because
# the query is a harder class, while `act` does scale with query class
# because its work genuinely does.


@pytest.mark.parametrize("query_class", ["lookup", "single_hop", "multi_hop", "exploratory"])
def test_a_guard_step_budget_does_not_change_with_query_class(query_class) -> None:
    """A guard classification is the same size of call whatever the query.

    This is the regression guard on the original defect: Section 19.1's
    per-query-class budget was applied to every step, so an exploratory
    query handed a guard classification a 120 second timeout, and a lookup
    handed the synth write 5 seconds. Neither is what a per-step timeout is
    for.
    """
    assert budget_for_step("guardrail", query_class) == budget_for_step("guardrail", "lookup")
    assert budget_for_step("think", query_class) == budget_for_step("think", "lookup")


def test_act_budget_does_scale_with_query_class() -> None:
    """`act` is the one step whose work really does scale with the question."""
    assert budget_for_step("act", "exploratory") > budget_for_step("act", "lookup")
    assert budget_for_step("act", "lookup") == budget_for_query_class("lookup")


def test_the_reasoning_tiers_get_more_than_a_guard_step_on_a_lookup() -> None:
    """Measured latency ordering: guard is fast, plan and synth are not.

    Guard measured 719 to 4615 ms; synth measured 17527 to 21572 ms. A
    single lookup-class figure cannot bound both, which is why the budget
    resolves per tier.
    """
    guard = budget_for_step("guardrail", "lookup")
    assert budget_for_step("plan", "lookup") > guard
    assert budget_for_step("write", "lookup") > guard


def test_write_on_a_lookup_clears_the_measured_synth_worst_case() -> None:
    """21572 ms was the slowest write-shaped synth call measured."""
    assert budget_for_step("write", "lookup") > 21.572


def test_unknown_step_raises_rather_than_resolving_a_wrong_timeout() -> None:
    """A typo must surface, not silently resolve to some other step's budget."""
    with pytest.raises(UnknownStepError):
        budget_for_step("guardrial", "lookup")


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


# ---------------------------------------------------------------------------
# F-2.1-B02, second order: a timed-out call must still be metered
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_timed_out_call_still_meters_its_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cancelled model call has already been billed by the provider.

    Finding F-2.1-B02's second-order half. `enforce_timeout` cancels the
    coroutine, so `call_tier`'s metering never ran and the call recorded
    0.00 US dollars. Measured, a timed-out call actually cost 0.005 to
    0.010. Because the most expensive query class is also the one most
    likely to time out, all three caps read zero for exactly the queries
    that spend the most.

    The real usage is unknowable once the response never arrives, so the
    harness meters a deliberate over-estimate. A cost cap that has to guess
    must guess toward stopping.
    """

    async def never_returns(*args, **kwargs):
        await asyncio.sleep(30)

    monkeypatch.setattr(litellm, "acompletion", never_returns)
    monkeypatch.setattr(
        harness_module,
        "_FALLBACK_PRICES_USD_PER_TOKEN",
        {harness_module.TierContext().resolve("guard"): (1e-6, 1e-6)},
    )

    harness = Harness(trace_id="timeout-metering")
    assert harness.get_query_cost_usd("timeout-metering") == 0.0

    with pytest.raises(HarnessCallError):
        await harness.enforce_timeout(
            "guardrail",
            harness.call_tier("guard", [{"role": "user", "content": "hi"}]),
            0.2,
        )

    metered = harness.get_query_cost_usd("timeout-metering")
    assert metered > 0.0, (
        "a timed-out call recorded 0.00 US dollars; the provider billed it, "
        "so every cap is blind to the spend"
    )


# ---------------------------------------------------------------------------
# Build phase 8.6, T-8.6-08, from the product harness review
# (testing/Developer/reports/2026-09-25_harness_review/product_harness.md):
#
# - C4 / W6: a request refused because reasoning cannot be turned off is
#   retried once without the reasoning block, and the fallback is logged.
#   The refusal replayed here is the provider's live text, reached through
#   litellm exactly as builder K's report (K-13) shows it.
# - C6 / W7: a model with no known price fails before the call is sent.
# - C5: each call's elapsed seconds are carried beside its cost.
# ---------------------------------------------------------------------------

_REASONING_REFUSAL_TEXT = (
    'OpenrouterException - {"error":{"message":"Reasoning is mandatory for this endpoint '
    'and cannot be disabled.","code":400}}'
)


def _reasoning_refusal() -> litellm.BadRequestError:
    return litellm.BadRequestError(
        message=_REASONING_REFUSAL_TEXT, llm_provider="openrouter", model="test-provider/test-model"
    )


@pytest.mark.asyncio
async def test_a_reasoning_refusal_is_retried_once_without_the_block_and_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _patch_model_env(monkeypatch, "SYNTH_MODEL")
    _patch_price(monkeypatch)
    mock_acompletion = AsyncMock(side_effect=[_reasoning_refusal(), _fake_response("an answer", 50, 20)])
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)

    harness = Harness(trace_id="c4-1")
    with caplog.at_level("WARNING", logger=harness_module.__name__):
        result = await harness.call_tier("synth", [{"role": "user", "content": "hi"}])

    assert result.content == "an answer"
    assert mock_acompletion.call_count == 2
    first, second = (call.kwargs for call in mock_acompletion.call_args_list)
    assert first["reasoning"] == {"effort": "none"}, "the tier's own dial is tried first"
    assert "reasoning" not in second, "the retry drops the block entirely"
    assert second["messages"] == first["messages"] and second["max_tokens"] == first["max_tokens"]
    assert any(
        "refused the reasoning block" in record.getMessage() and "test-provider/test-model" in record.getMessage()
        for record in caplog.records
    )
    # The refused attempt billed nothing; only the answer is metered.
    assert harness.get_query_cost_usd("c4-1") == pytest.approx(50 * _INPUT_PRICE + 20 * _OUTPUT_PRICE)


@pytest.mark.asyncio
async def test_a_second_reasoning_refusal_is_not_retried_again(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_model_env(monkeypatch, "SYNTH_MODEL")
    _patch_price(monkeypatch)
    mock_acompletion = AsyncMock(side_effect=[_reasoning_refusal(), _reasoning_refusal(), _fake_response("x", 1, 1)])
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)

    with pytest.raises(HarnessCallError) as exc_info:
        await Harness(trace_id="c4-2").call_tier("synth", [{"role": "user", "content": "hi"}])

    assert mock_acompletion.call_count == 2, "once without the block, never a third time"
    assert exc_info.value.error_class == "recoverable"
    assert "Reasoning is mandatory" in str(exc_info.value), "the provider's own words reach the log"


@pytest.mark.asyncio
async def test_a_bad_request_that_does_not_name_reasoning_is_still_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_model_env(monkeypatch)
    _patch_price(monkeypatch)
    mock_acompletion = AsyncMock(
        side_effect=litellm.BadRequestError(
            message='OpenrouterException - {"error":{"message":"Invalid message role","code":400}}',
            llm_provider="openrouter",
            model="test-provider/test-model",
        )
    )
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)

    with pytest.raises(HarnessCallError) as exc_info:
        await Harness(trace_id="c4-3").call_tier("guard", [{"role": "user", "content": "hi"}])

    assert mock_acompletion.call_count == 1
    assert exc_info.value.error_class == "recoverable"


# Fix round (F-8.6-J05, A02): the retry keys on the provider's whole refusal
# phrase, never on the word "reasoning", and never on a context-window or
# content-policy error, whatever its text says. Before the fix every case
# below was retried once without the reasoning block.


def _bad_request(kind: type[litellm.BadRequestError], text: str) -> litellm.BadRequestError:
    return kind(message=text, llm_provider="openrouter", model="test-provider/test-model")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        _bad_request(
            litellm.ContextWindowExceededError,
            "This model's maximum context length is 8192 tokens, and reasoning tokens count toward it",
        ),
        _bad_request(
            litellm.ContentPolicyViolationError,
            "Your prompt was flagged: 'explain the reasoning behind BRCA1 testing'",
        ),
        _bad_request(
            litellm.ContentPolicyViolationError,
            "Your prompt was flagged: 'Reasoning is mandatory for this endpoint and cannot be disabled'",
        ),
        _bad_request(litellm.ContextWindowExceededError, _REASONING_REFUSAL_TEXT),
        _bad_request(
            litellm.BadRequestError,
            "Invalid request: 'a clinical reasoning question' does not fit this field",
        ),
    ],
    ids=[
        "context window 400 naming reasoning",
        "content policy 400 echoing the person's words",
        "content policy 400 echoing the refusal phrase",
        "context window 400 carrying the refusal phrase",
        "plain 400 echoing the person's words",
    ],
)
async def test_a_400_that_only_mentions_reasoning_is_not_retried(
    monkeypatch: pytest.MonkeyPatch, error: litellm.BadRequestError
) -> None:
    _patch_model_env(monkeypatch, "SYNTH_MODEL")
    _patch_price(monkeypatch)
    mock_acompletion = AsyncMock(side_effect=[error, _fake_response("never reached", 1, 1)])
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)

    with pytest.raises(HarnessCallError) as exc_info:
        await Harness(trace_id="j05-1").call_tier("synth", [{"role": "user", "content": "hi"}])

    assert mock_acompletion.call_count == 1, "no second request without the reasoning block"
    assert mock_acompletion.call_args.kwargs["reasoning"] == {"effort": "none"}
    assert exc_info.value.error_class == "recoverable"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        _REASONING_REFUSAL_TEXT,
        'OpenrouterException - {"error":{"message":"REASONING IS MANDATORY FOR THIS ENDPOINT AND CANNOT BE DISABLED."}}',
        "Reasoning is mandatory for this endpoint\n  and cannot be disabled.",
    ],
    ids=["the live text", "upper case", "wrapped over two lines"],
)
async def test_the_refusal_phrase_is_recognised_however_it_is_cased_or_wrapped(
    monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    _patch_model_env(monkeypatch, "SYNTH_MODEL")
    _patch_price(monkeypatch)
    refusal = _bad_request(litellm.BadRequestError, text)
    mock_acompletion = AsyncMock(side_effect=[refusal, _fake_response("an answer", 1, 1)])
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)

    result = await Harness(trace_id="j05-2").call_tier("synth", [{"role": "user", "content": "hi"}])

    assert result.content == "an answer"
    assert mock_acompletion.call_count == 2
    assert "reasoning" not in mock_acompletion.call_args_list[1].kwargs


@pytest.mark.asyncio
@pytest.mark.parametrize("transient_first", [True, False])
async def test_the_reasoning_fallback_and_the_transient_retry_are_separate(
    monkeypatch: pytest.MonkeyPatch, transient_first: bool
) -> None:
    """Each kind of failure gets its own single retry, in either order."""
    _patch_model_env(monkeypatch, "SYNTH_MODEL")
    _patch_price(monkeypatch)
    transient = litellm.RateLimitError(
        message="rate limited", llm_provider="openrouter", model="test-provider/test-model"
    )
    failures = [transient, _reasoning_refusal()] if transient_first else [_reasoning_refusal(), transient]
    mock_acompletion = AsyncMock(side_effect=[*failures, _fake_response("ok", 1, 1)])
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)

    result = await Harness(trace_id="c4-4").call_tier("synth", [{"role": "user", "content": "hi"}])

    assert result.content == "ok"
    assert mock_acompletion.call_count == 3
    assert "reasoning" not in mock_acompletion.call_args_list[2].kwargs


@pytest.mark.asyncio
async def test_the_reasoning_fallback_is_per_call_never_remembered(monkeypatch: pytest.MonkeyPatch) -> None:
    """One stray refusal must not take the reasoning dial away from later
    calls: the next call on the same harness sends the tier's block again."""
    _patch_model_env(monkeypatch, "SYNTH_MODEL")
    _patch_price(monkeypatch)
    mock_acompletion = AsyncMock(
        side_effect=[_reasoning_refusal(), _fake_response("first", 1, 1), _fake_response("second", 1, 1)]
    )
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)
    harness = Harness(trace_id="c4-5")

    await harness.call_tier("synth", [{"role": "user", "content": "one"}])
    await harness.call_tier("synth", [{"role": "user", "content": "two"}])

    assert mock_acompletion.call_args_list[2].kwargs["reasoning"] == {"effort": "none"}


@pytest.mark.asyncio
async def test_an_unpriced_model_fails_before_anything_is_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    """C6 / W7: the provider would bill a call whose reply is then thrown
    away. Now nothing is sent, and the message says what to do."""
    _patch_model_env(monkeypatch)
    _patch_price(monkeypatch, raises=True)
    monkeypatch.setattr(harness_module, "_FALLBACK_PRICES_USD_PER_TOKEN", {})
    mock_acompletion = AsyncMock(return_value=_fake_response("hi", 100, 100))
    monkeypatch.setattr(harness_module.litellm, "acompletion", mock_acompletion)

    harness = Harness(trace_id="c6-1")
    with pytest.raises(HarnessCallError) as exc_info:
        await harness.call_tier("guard", [{"role": "user", "content": "hi"}])

    mock_acompletion.assert_not_called()
    assert exc_info.value.error_class == "unexpected"
    assert exc_info.value.source == "harness.harness._price_per_token"
    assert "no OpenRouter price found for model 'test-provider/test-model'" in str(exc_info.value)
    assert "_FALLBACK_PRICES_USD_PER_TOKEN" in str(exc_info.value), "the message says where to add the price"
    assert harness.get_query_cost_usd("c6-1") == 0.0


@pytest.mark.asyncio
async def test_a_priced_model_is_priced_once_before_the_call(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_model_env(monkeypatch)
    order: list[str] = []

    def _get_model_info(model: str) -> dict[str, Any]:
        order.append("price")
        return {"input_cost_per_token": _INPUT_PRICE, "output_cost_per_token": _OUTPUT_PRICE}

    async def _acompletion(**_kwargs: Any) -> SimpleNamespace:
        order.append("call")
        return _fake_response("hi", 1, 1)

    monkeypatch.setattr(harness_module.litellm, "get_model_info", _get_model_info)
    monkeypatch.setattr(harness_module.litellm, "acompletion", _acompletion)

    await Harness(trace_id="c6-2").call_tier("guard", [{"role": "user", "content": "hi"}])

    assert order == ["price", "call"]


@pytest.mark.asyncio
async def test_each_call_carries_its_elapsed_seconds_beside_its_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    """C5: on the response, and on the harness for the operator-only cost event."""
    _patch_model_env(monkeypatch, "PLAN_MODEL")
    _patch_price(monkeypatch)

    async def _slow_acompletion(**_kwargs: Any) -> SimpleNamespace:
        await asyncio.sleep(0.2)
        return _fake_response("hi", 10, 10)

    monkeypatch.setattr(harness_module.litellm, "acompletion", _slow_acompletion)
    harness = Harness(trace_id="c5-1")
    assert harness.last_call_elapsed_s("c5-1", "plan") is None

    result = await harness.call_tier("plan", [{"role": "user", "content": "hi"}])

    assert result.elapsed_s is not None and 0.19 <= result.elapsed_s < 0.6, result.elapsed_s
    assert result.call_cost_usd == pytest.approx(10 * _INPUT_PRICE + 10 * _OUTPUT_PRICE)
    assert harness.last_call_elapsed_s("c5-1", "plan") == result.elapsed_s
    assert harness.last_call_elapsed_s("c5-1", "guard") is None, "kept per tier"
    assert harness.last_call_elapsed_s("another-trace", "plan") is None, "kept per query"


@pytest.mark.asyncio
async def test_a_calls_elapsed_seconds_include_its_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """The person waited for the retry too, so it is part of the call's time."""
    _patch_model_env(monkeypatch)
    _patch_price(monkeypatch)
    calls = {"n": 0}

    async def _fail_slowly_then_answer(**_kwargs: Any) -> SimpleNamespace:
        calls["n"] += 1
        await asyncio.sleep(0.15)
        if calls["n"] == 1:
            raise litellm.RateLimitError(
                message="rate limited", llm_provider="openrouter", model="test-provider/test-model"
            )
        return _fake_response("hi", 1, 1)

    monkeypatch.setattr(harness_module.litellm, "acompletion", _fail_slowly_then_answer)

    result = await Harness(trace_id="c5-2").call_tier("guard", [{"role": "user", "content": "hi"}])

    assert result.elapsed_s is not None and result.elapsed_s >= 0.29, result.elapsed_s


@pytest.mark.asyncio
async def test_a_failed_call_records_no_elapsed_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_model_env(monkeypatch)
    _patch_price(monkeypatch)
    monkeypatch.setattr(
        harness_module.litellm,
        "acompletion",
        AsyncMock(
            side_effect=litellm.ContextWindowExceededError(
                message="too many tokens", llm_provider="openrouter", model="test-provider/test-model"
            )
        ),
    )
    harness = Harness(trace_id="c5-3")
    with pytest.raises(HarnessCallError):
        await harness.call_tier("guard", [{"role": "user", "content": "hi"}])
    assert harness.last_call_elapsed_s("c5-3", "guard") is None
