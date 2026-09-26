"""F-8.6-V01 and V03: every Jev charge lands between $0 and
`MAX_JEV_COST_USD`, inclusive.

`test_jev_client.py` already exercises the clamp through `call_jev` and
`call_jev_batch` end to end (the parametrized cost arms of
`test_a_cost_no_decision_could_have_is_a_malformed_reply`,
`test_an_unusable_reply_still_reports_what_it_cost`,
`test_a_batch_cost_no_call_could_have_is_malformed` and
`test_an_unusable_batch_reply_still_reports_what_it_cost`, all updated for
this ticket). This file is the unit-level proof, directly against
`_reported_cost_usd` and `_cost_ceiling_error`, the two of the three fixed
sites that are pure functions (the third, the reply's `answers` block once
parsed, is bounded by `JevResult.cost_usd`'s own Pydantic `le` constraint
and needs no separate test here).

MUTATION PROOF for each arm below: reverting `_reported_cost_usd`'s
invalid branch to `return 0.0` (F-8.6-V03), or `_cost_ceiling_error` to
`billed_cost_usd=cost_usd` (F-8.6-V01), turns the matching arm red. Both
were run by hand and reverted; see the builder's report.
"""
from __future__ import annotations

import math

import pytest

from system_03_search_agent.harness.jev_client import (
    MAX_JEV_COST_USD,
    _cost_ceiling_error,
    _reported_cost_usd,
)


class TestReportedCostUsd:
    """`_reported_cost_usd`: the source of `billed_usd` at two of the three
    fixed sites (the single-decision and batch malformed-reply errors)."""

    @pytest.mark.parametrize(
        "raw",
        [float("nan"), float("inf"), -0.1, True, "not a number", 10**400],
        ids=["nan", "infinity", "negative", "a bool", "a string", "an overflowing int"],
    )
    def test_a_non_amount_is_charged_the_ceiling_never_zero(self, raw: object) -> None:
        assert _reported_cost_usd({"usage": {"cost": raw}}, "test") == MAX_JEV_COST_USD

    def test_no_cost_field_at_all_is_charged_the_ceiling(self) -> None:
        assert _reported_cost_usd({"usage": {}}, "test") == MAX_JEV_COST_USD
        assert _reported_cost_usd({}, "test") == MAX_JEV_COST_USD
        assert _reported_cost_usd("not even a dict", "test") == MAX_JEV_COST_USD

    def test_a_well_formed_cost_at_or_under_the_ceiling_is_returned_exactly(self) -> None:
        assert _reported_cost_usd({"usage": {"cost": 0.0}}, "test") == 0.0
        assert _reported_cost_usd({"usage": {"cost": 0.005}}, "test") == pytest.approx(0.005)
        assert _reported_cost_usd({"usage": {"cost": MAX_JEV_COST_USD}}, "test") == pytest.approx(
            MAX_JEV_COST_USD
        )

    def test_a_well_formed_cost_above_the_ceiling_is_still_returned_as_reported(self) -> None:
        """`_reported_cost_usd` itself does not clamp an over-ceiling but
        otherwise valid amount; `_cost_ceiling_error`, the caller that
        raises on it, is the one that clamps (below)."""
        assert _reported_cost_usd({"usage": {"cost": 12.5}}, "test") == pytest.approx(12.5)


class TestCostCeilingError:
    """`_cost_ceiling_error`: the third fixed site, called by both
    `call_jev` and `call_jev_batch` once a finite reported cost exceeds the
    ceiling."""

    @pytest.mark.parametrize("reported", [0.011, 0.5, 12.5, 999.9])
    def test_billed_cost_usd_is_always_the_ceiling_never_the_reported_figure(
        self, reported: float
    ) -> None:
        err = _cost_ceiling_error("test", reported, "fall back")
        assert err.billed_cost_usd == pytest.approx(MAX_JEV_COST_USD)
        assert err.reason == "malformed_reply"

    def test_every_charge_this_module_can_produce_stays_in_bounds(self) -> None:
        """The property acceptance item 1 actually asks for: no combination
        of `_reported_cost_usd` and `_cost_ceiling_error` can produce a
        `billed_cost_usd` outside `[0, MAX_JEV_COST_USD]`."""
        raws: list[object] = [
            float("nan"),
            float("-inf"),
            -1.0,
            0.0,
            0.005,
            MAX_JEV_COST_USD,
            0.5,
            999.9,
            10**400,
            "abc",
            True,
            None,
        ]
        for raw in raws:
            reported = _reported_cost_usd({"usage": {"cost": raw}}, "test")
            assert math.isfinite(reported)
            assert 0.0 <= reported
            if reported > MAX_JEV_COST_USD:
                billed = _cost_ceiling_error("test", reported, "fall back").billed_cost_usd
            else:
                billed = reported
            assert 0.0 <= billed <= MAX_JEV_COST_USD, (raw, billed)
