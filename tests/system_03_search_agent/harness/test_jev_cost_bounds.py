"""F-8.6-V01 and V03, then re-land follow-up R-10 (F-8.6-FJ01, FA01, FJ02,
FJ03) and its fix round (F-72-J02, A03): every Jev charge lands above $0
and at most `MAX_JEV_COST_USD`, and every reply that came back but cannot
be used is charged exactly `JEV_FLOOR_COST_USD`.

`test_jev_client.py` and `test_jev_followup_costs.py` exercise the charge
through `call_jev`, `call_jev_batch` and the three charge sites end to
end. This file is the unit-level proof, directly against the two pure
helpers:

- `_reported_cost_usd`: what a reply states it cost, or None when it
  states no real amount. Since R-10 it only reads; it never decides a
  charge and never logs one.
- `_unusable_reply`: the one place an unusable reply's charge is fixed and
  logged.
- `jev_charge_usd`: what any reply that came back is charged.

MUTATION PROOF: making `_unusable_reply` carry any `billed_cost_usd` other
than `JEV_FLOOR_COST_USD` turns `test_an_unusable_reply_is_charged_the_floor_and_the_log_says_so`
red; see the builder's report for the run.
"""
from __future__ import annotations

import logging

import pytest

from system_03_search_agent.harness import jev_client as jev_client_module
from system_03_search_agent.harness.jev_client import (
    JEV_FLOOR_COST_USD,
    MAX_JEV_COST_USD,
    _reported_cost_usd,
    _unusable_reply,
    jev_charge_usd,
)


class TestReportedCostUsd:
    @pytest.mark.parametrize(
        "raw",
        [float("nan"), float("inf"), -0.1, True, "not a number", 10**400, None, [0.001], {"a": 1}],
        ids=["nan", "infinity", "negative", "a bool", "a string", "an overflowing int", "null", "a list", "a map"],
    )
    def test_a_non_amount_states_no_cost(self, raw: object) -> None:
        assert _reported_cost_usd({"usage": {"cost": raw}}) is None

    def test_no_cost_field_at_all_states_no_cost(self) -> None:
        assert _reported_cost_usd({"usage": {}}) is None
        assert _reported_cost_usd({}) is None
        assert _reported_cost_usd({"usage": None}) is None
        assert _reported_cost_usd("not even a dict") is None
        assert _reported_cost_usd([1, 2, 3]) is None

    def test_a_real_amount_is_returned_exactly_whatever_its_size(self) -> None:
        """Reading is not charging: an amount above the ceiling is returned
        as stated, and the caller refuses the reply on it."""
        assert _reported_cost_usd({"usage": {"cost": 0.0}}) == 0.0
        assert _reported_cost_usd({"usage": {"cost": 0.005}}) == pytest.approx(0.005)
        assert _reported_cost_usd({"usage": {"cost": "0.004"}}) == pytest.approx(0.004)
        assert _reported_cost_usd({"usage": {"cost": 12.5}}) == pytest.approx(12.5)

    def test_reading_a_cost_logs_nothing(self, caplog: pytest.LogCaptureFixture) -> None:
        """FJ03: the old reader logged "charged the $0.01 ceiling" before
        the charge was decided, and a reply that then raised an unnamed
        error was charged $0 under that line."""
        with caplog.at_level(logging.DEBUG, logger=jev_client_module.__name__):
            _reported_cost_usd({"usage": {}})
            _reported_cost_usd({"usage": {"cost": "abc"}})
        assert caplog.text == ""


class TestUnusableReply:
    @pytest.mark.parametrize("reason", ["malformed_reply", "invalid_option"])
    def test_an_unusable_reply_is_charged_the_floor_and_the_log_says_so(
        self, caplog: pytest.LogCaptureFixture, reason: str
    ) -> None:
        with caplog.at_level(logging.WARNING, logger=jev_client_module.__name__):
            err = _unusable_reply("decision 'x'", "a detail", "fall back", reason=reason)
        assert err.billed_cost_usd == JEV_FLOOR_COST_USD == 0.0001
        assert err.reason == reason
        assert "it is charged $0.0001" in caplog.text
        assert len(caplog.records) == 1
        assert str(err).endswith("fall back")


@pytest.mark.parametrize(
    ("stated", "charged"),
    [
        (None, JEV_FLOOR_COST_USD),
        (0.0, JEV_FLOOR_COST_USD),
        (-0.1, JEV_FLOOR_COST_USD),
        (MAX_JEV_COST_USD * 2, JEV_FLOOR_COST_USD),
        (12.5, JEV_FLOOR_COST_USD),
        (0.00002, 0.00002),
        (MAX_JEV_COST_USD, MAX_JEV_COST_USD),
    ],
    ids=["no cost", "$0", "negative", "above the ceiling", "F-8.6-V01's 12.5", "Jev's price", "the ceiling"],
)
def test_a_reply_is_charged_its_sensible_cost_or_the_floor(stated: float | None, charged: float) -> None:
    """The product owner's decision of 2026-09-29: never $0, never one cent
    for a reply that states no sensible cost, the stated cost otherwise."""
    assert jev_charge_usd(stated) == charged
    assert 0.0 < JEV_FLOOR_COST_USD < MAX_JEV_COST_USD / 50
