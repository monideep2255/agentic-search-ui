"""Build phase 8.7, T-8.7-02: Opus 5.5 writes, at minimal effort, inside 25 cents.

The owner's words for this ticket: "The answer is written by Opus at minimal
effort, and a question never costs more than 25 cents." The decision is
DECISIONS.md 2026-09-27, taken on writer bench 3
(`testing/Developer/reports/2026-09-26_writer_bench_3/`).

What each group below pins, and the one-line mutation that turns it red:

- THE DEFAULT. With no `SYNTH_MODEL` override, the synth tier is
  `anthropic/claude-opus-5.5`, the exact OpenRouter id the bench called
  (its raw records, `record.model_id`). Red when the default reverts.
- THE EFFORT. Opus is sent `effort: minimal` on whichever tier resolves to
  it, because it refuses `none` ("Reasoning is mandatory for this endpoint
  and cannot be disabled", the bench's probe). Every other model keeps its
  tier's effort exactly. Red when Opus is sent `none`, or when another
  model's effort moves.
- THE PRICE. Opus is priced before it is called even when litellm's own map
  does not carry it, at $4 and $20 per million tokens, the bench's
  catalogue price. Red when the fallback entry is removed.
- THE CAP. The pre-flight check prices the next call at the resolved
  model's real price, never below today's static estimate. A normal Opus
  question, first call and repair, fits the owner's 25 cents; a call that
  would cross it is refused; a 10-cent cap refuses every Opus writer call
  and says so in an error log naming the setting. Red when the approved cap
  below is set to 0.10, or when the check goes back to the static estimate.

No network call is made: `litellm.acompletion` is faked wherever a call is
placed, and `litellm.get_model_info` is faked wherever the price must not
depend on the installed litellm's map. The rollback arm and the cheaper
models' arm read the installed map on purpose.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.harness.tiers import _DEFAULT_MODELS, resolve_model

#: The exact id writer bench 3 called: `record.model_id` in every
#: `raw/anthropic_claude-opus-5.5+effort-minimal__*.json`.
_OPUS = "anthropic/claude-opus-5.5"

#: OpenRouter's catalogue price for Opus 5.5, per token, as the bench's
#: "Candidates and prices" table records it ($4 and $20 per million) and as
#: the bench's own metering reproduced it to the cent (G-001 run 1: 17,432
#: prompt and 878 output tokens metered $0.087288, OpenRouter billed
#: $0.087288).
_OPUS_INPUT_PRICE = 4e-06
_OPUS_OUTPUT_PRICE = 2e-05

#: The owner's per-question cap, DECISIONS.md 2026-09-27. Setting this to
#: 0.10 is the "cap at ten cents" mutation: the normal-question arm goes red.
_OWNER_APPROVED_CAP_USD = 0.25

#: Measured on bench 3's 54 Opus runs at minimal effort, 78 writer calls:
#: the median and p90 cost of one writer call, and the largest non-writer
#: spend of any one question (guard, plan and Jev together).
_MEDIAN_WRITER_CALL_USD = 0.0855
_P90_WRITER_CALL_USD = 0.0988
_LARGEST_NON_WRITER_SPEND_USD = 0.00023

_ENV_BY_TIER = {"guard": "GUARD_MODEL", "plan": "PLAN_MODEL", "synth": "SYNTH_MODEL"}


def _fake_response(prompt_tokens: int = 10, completion_tokens: int = 5) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


def _litellm_map_lacks_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force `_price_per_token` onto the local fallback table."""

    def _missing(model: str) -> dict[str, Any]:
        raise RuntimeError(f"{model!r} is not in litellm's map in this test")

    monkeypatch.setattr(harness_module.litellm, "get_model_info", _missing)


@pytest.fixture(autouse=True)
def _no_tier_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _ENV_BY_TIER.values():
        monkeypatch.delenv(name, raising=False)


# ---------------------------------------------------------------------------
# The default.
# ---------------------------------------------------------------------------


def test_the_synth_tier_defaults_to_opus_5_5() -> None:
    assert _DEFAULT_MODELS["synth"] == _OPUS
    assert resolve_model("synth") == _OPUS


def test_the_guard_and_plan_defaults_are_unchanged() -> None:
    """Only the writer moves; the two other tiers keep their defaults."""
    assert resolve_model("guard") == "deepseek/deepseek-v4-flash"
    assert resolve_model("plan") == "moonshotai/kimi-k2.6"


@pytest.mark.asyncio
async def test_a_question_with_no_synth_override_calls_opus_at_minimal_effort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _litellm_map_lacks_everything(monkeypatch)
    acompletion = AsyncMock(return_value=_fake_response())
    monkeypatch.setattr(harness_module.litellm, "acompletion", acompletion)

    await Harness(trace_id="trace-opus").call_tier("synth", [{"role": "user", "content": "q"}])

    sent = acompletion.call_args.kwargs
    assert sent["model"] == f"openrouter/{_OPUS}"
    assert sent["reasoning"] == {"effort": "minimal"}
    assert sent["max_tokens"] == 4_000, "the synth ceiling is unchanged"


# ---------------------------------------------------------------------------
# The effort.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("tier", ["guard", "plan", "synth"])
async def test_opus_is_never_sent_effort_none_on_any_tier(
    tier: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Per model, not per tier: Opus refuses `none` wherever it answers."""
    monkeypatch.setenv(_ENV_BY_TIER[tier], _OPUS)
    _litellm_map_lacks_everything(monkeypatch)
    acompletion = AsyncMock(return_value=_fake_response())
    monkeypatch.setattr(harness_module.litellm, "acompletion", acompletion)

    await Harness(trace_id="trace-opus").call_tier(tier, [{"role": "user", "content": "q"}])  # type: ignore[arg-type]

    assert acompletion.call_count == 1, "one request, no refusal retry needed"
    assert acompletion.call_args.kwargs["reasoning"] == {"effort": "minimal"}


@pytest.mark.asyncio
@pytest.mark.parametrize("tier", ["guard", "plan", "synth"])
@pytest.mark.parametrize(
    "model_id",
    [
        "deepseek/deepseek-v4-flash",
        "moonshotai/kimi-k2.6",
        "z-ai/glm-5.2",
        "test-provider/test-model",
    ],
)
async def test_every_other_model_keeps_its_tiers_effort_exactly(
    tier: str, model_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_ENV_BY_TIER[tier], model_id)
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )
    acompletion = AsyncMock(return_value=_fake_response())
    monkeypatch.setattr(harness_module.litellm, "acompletion", acompletion)

    await Harness(trace_id="trace-other").call_tier(tier, [{"role": "user", "content": "q"}])  # type: ignore[arg-type]

    sent = acompletion.call_args.kwargs["reasoning"]
    assert sent == harness_module._TIER_REASONING[tier]  # type: ignore[index]
    assert sent == {"effort": "none"}, "today every tier runs at none"


# ---------------------------------------------------------------------------
# The price.
# ---------------------------------------------------------------------------


def test_opus_is_priced_even_when_litellms_map_does_not_carry_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`requirements.txt` asks for `litellm>=1.40`, not an exact version, so
    the map a deployment installs can differ from the one tested. The
    fallback table keeps Opus priced whatever that map holds."""
    _litellm_map_lacks_everything(monkeypatch)
    assert harness_module._price_per_token(_OPUS) == (_OPUS_INPUT_PRICE, _OPUS_OUTPUT_PRICE)


@pytest.mark.asyncio
async def test_an_opus_call_is_priced_and_sent_when_only_the_fallback_knows_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _litellm_map_lacks_everything(monkeypatch)
    acompletion = AsyncMock(return_value=_fake_response(17_432, 878))
    monkeypatch.setattr(harness_module.litellm, "acompletion", acompletion)
    harness = Harness(trace_id="trace-price")

    result = await harness.call_tier("synth", [{"role": "user", "content": "q"}])

    assert acompletion.call_count == 1, "priced before the call, so the call is sent"
    # Bench 3, G-001 run 1: the same token counts OpenRouter billed $0.087288.
    assert result.call_cost_usd == pytest.approx(0.087288)
    assert harness.get_query_cost_usd("trace-price") == pytest.approx(0.087288)


def test_the_harness_reports_the_price_of_the_model_a_question_resolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _litellm_map_lacks_everything(monkeypatch)
    harness = Harness(trace_id="trace-p")
    assert harness.model_for("synth") == _OPUS
    assert harness.price_per_token("synth") == (_OPUS_INPUT_PRICE, _OPUS_OUTPUT_PRICE)


def test_the_rollback_writer_glm_5_2_is_still_priced_by_the_installed_map() -> None:
    """Setting `SYNTH_MODEL=z-ai/glm-5.2` is the one-setting rollback. Its
    fallback entry left the table together with its place in
    `_DEFAULT_MODELS` (the repository-wide model-id scan allows no other),
    so this arm holds that the installed litellm map still prices it."""
    input_price, output_price = harness_module._price_per_token("z-ai/glm-5.2")
    assert input_price > 0 and output_price > 0


# ---------------------------------------------------------------------------
# The cap.
# ---------------------------------------------------------------------------


def _opus_harness(monkeypatch: pytest.MonkeyPatch, spent_usd: float) -> Harness:
    _litellm_map_lacks_everything(monkeypatch)
    harness = Harness(trace_id="trace-cap")
    if spent_usd:
        harness.track_cost("trace-cap", "synth", spent_usd)
    return harness


def test_the_pre_flight_estimate_prices_an_opus_writer_call_at_opus_price(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _opus_harness(monkeypatch, 0.0)
    estimate = cost_control.estimate_call_cost_usd("synth", harness.price_per_token("synth"))
    # 23,000 prompt and 2,000 output tokens at Opus's price: above every one
    # of the bench's 78 Opus writer calls (largest: 22,839 and 1,869).
    assert estimate == pytest.approx(23_000 * _OPUS_INPUT_PRICE + 2_000 * _OPUS_OUTPUT_PRICE)
    assert estimate > cost_control.estimate_call_cost_usd("synth"), "above today's static figure"


def test_a_normal_opus_question_fits_the_owners_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first writer call, then the repair after a median and after a p90
    first call, are all admitted at the owner's cap. At 0.10 the first call
    is refused."""
    first = _opus_harness(monkeypatch, _LARGEST_NON_WRITER_SPEND_USD)
    cost_control.check_per_query_cap(
        first, "trace-cap", "synth", query_cap_usd=_OWNER_APPROVED_CAP_USD
    )

    after_median = _opus_harness(
        monkeypatch, _LARGEST_NON_WRITER_SPEND_USD + _MEDIAN_WRITER_CALL_USD
    )
    cost_control.check_per_query_cap(
        after_median, "trace-cap", "synth", query_cap_usd=_OWNER_APPROVED_CAP_USD
    )

    after_p90 = _opus_harness(monkeypatch, _LARGEST_NON_WRITER_SPEND_USD + _P90_WRITER_CALL_USD)
    cost_control.check_per_query_cap(
        after_p90, "trace-cap", "synth", query_cap_usd=_OWNER_APPROVED_CAP_USD
    )


def test_an_opus_call_that_would_cross_the_cap_is_refused_before_it_is_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """$0.13 spent plus one Opus writer call's bound ($0.132) passes 25
    cents, so the call is never sent. Under the static estimate ($0.025)
    it was admitted, and the question could end near $0.26."""
    harness = _opus_harness(monkeypatch, 0.13)
    with pytest.raises(cost_control.QueryCapExceededError) as caught:
        cost_control.check_per_query_cap(
            harness, "trace-cap", "synth", query_cap_usd=_OWNER_APPROVED_CAP_USD
        )
    assert caught.value.estimated_call_cost_usd == pytest.approx(0.132)


def test_a_ten_cent_cap_refuses_every_opus_writer_call_and_logs_an_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A deployment that ships Opus under the old 10-cent cap would stop
    every question at Write. The call is refused, as it must be, and the
    refusal is logged as an error naming the setting, so it is caught on the
    first question rather than read as a run of partial answers."""
    harness = _opus_harness(monkeypatch, 0.0)
    with (
        caplog.at_level(logging.ERROR, logger=cost_control.__name__),
        pytest.raises(cost_control.QueryCapExceededError),
    ):
        cost_control.check_per_query_cap(harness, "trace-cap", "synth", query_cap_usd=0.10)

    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors, "populate-check: no error was logged"
    assert "PER_QUERY_COST_CAP_USD" in errors[0]
    assert _OPUS in errors[0]


def test_an_ordinary_cap_hit_is_not_logged_as_a_misconfiguration(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The error log is for a cap below ONE call. Running out of cap after
    real spending is the cap doing its job, and stays quiet."""
    harness = _opus_harness(monkeypatch, 0.20)
    with (
        caplog.at_level(logging.ERROR, logger=cost_control.__name__),
        pytest.raises(cost_control.QueryCapExceededError),
    ):
        cost_control.check_per_query_cap(
            harness, "trace-cap", "synth", query_cap_usd=_OWNER_APPROVED_CAP_USD
        )
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


@pytest.mark.parametrize(
    ("tier", "model_id"),
    [
        ("guard", "deepseek/deepseek-v4-flash"),
        ("plan", "deepseek/deepseek-v4-flash"),
        ("plan", "moonshotai/kimi-k2.6"),
        ("synth", "z-ai/glm-5.2"),
    ],
)
def test_the_cheaper_models_keep_todays_static_estimate(
    tier: str, model_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Develop's guard and plan model and the old writer price below the
    static figure, so their pre-flight estimate is exactly what it was: the
    change can only make the check stricter, and only for a costlier model."""
    monkeypatch.setenv(_ENV_BY_TIER[tier], model_id)
    harness = Harness(trace_id="trace-cheap")
    price = harness.price_per_token(tier)  # type: ignore[arg-type]
    static = cost_control.estimate_call_cost_usd(tier)  # type: ignore[arg-type]
    assert cost_control.estimate_call_cost_usd(tier, price) == static  # type: ignore[arg-type]


def test_an_unpriced_model_gets_todays_static_estimate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unpriced model is refused by `call_tier` itself, with its own
    actionable message, exactly as before; the cap check neither raises a
    new error nor admits on a guessed price. The static synth estimate is
    $0.025, so 0.026 admits and 0.024 refuses."""
    monkeypatch.setenv("SYNTH_MODEL", "unpriced-provider/unpriced-model")
    _litellm_map_lacks_everything(monkeypatch)
    harness = Harness(trace_id="trace-unpriced")
    cost_control.check_per_query_cap(harness, "trace-unpriced", "synth", query_cap_usd=0.026)
    with pytest.raises(cost_control.QueryCapExceededError):
        cost_control.check_per_query_cap(harness, "trace-unpriced", "synth", query_cap_usd=0.024)
