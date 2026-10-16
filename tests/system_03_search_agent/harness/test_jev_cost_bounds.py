"""Step 3a of the guardrail design (cards 84 and 72): what one Jev reply is
charged, as the pure functions `_stated_cost_usd` and `jev_charge_usd` fix
it, by the product owner's rule of 2026-09-29, as written: "the cost it
states when that is above $0 and at most `MAX_JEV_COST_USD`, otherwise a
floor near Jev's real price, about $0.0001, never $0".

| What the reply states | Charged |
|---|---|
| a finite cost above $0 and at most `MAX_JEV_COST_USD` | that cost |
| a cost above `MAX_JEV_COST_USD`, however spelled: 0.05, 1e309, Infinity, an integer too large for a float, a numeric string | `JEV_FLOOR_COST_USD` (fix round, J-GRS-03, J-GRS-04, A-GRS-03; develop charged the ceiling) |
| $0, no cost, or an unreadable amount (not a number, negative, a boolean, `NaN`) | `JEV_FLOOR_COST_USD` (F-72-J02, A03) |

Usable or not makes no difference (F-84-J04); `test_jev_followup_costs.py`
proves that end to end through `call_jev`, `call_jev_batch` and the three
charge sites, with the error statuses and the timeout.

MUTATION PROOF: `jev_charge_usd` returning the ceiling above it (develop's
rule, F-84-A06) turns `test_a_stated_cost_above_the_ceiling_is_charged_the_floor`
and `test_the_boundary_at_the_ceiling` red; returning the stated $0 turns `test_a_stated_zero_is_charged_the_floor`
red; returning `MAX_JEV_COST_USD` for no amount (develop's rule) turns
`test_no_amount_is_charged_the_floor` red.
"""

from __future__ import annotations

import math
import sys

import pytest

from system_03_search_agent.harness.jev_client import (
    JEV_FLOOR_COST_USD,
    MAX_JEV_COST_USD,
    _stated_cost_usd,
    jev_charge_usd,
)


def _charge(raw: object) -> float:
    return jev_charge_usd(_stated_cost_usd({"usage": {"cost": raw}}))


def test_the_constants_are_the_owners() -> None:
    assert JEV_FLOOR_COST_USD == 0.0001
    assert MAX_JEV_COST_USD == 0.01


@pytest.mark.parametrize("raw", [0.0000148, 0.00002, 0.005, MAX_JEV_COST_USD, "0.003"])
def test_a_sensible_stated_cost_is_charged_as_stated(raw: object) -> None:
    assert _charge(raw) == pytest.approx(float(raw))  # type: ignore[arg-type]


def test_a_stated_cost_under_the_floor_is_charged_as_stated() -> None:
    """The owner's rule charges what a reply states when that is above $0 and
    at most the ceiling: Jev's real price, about $0.00002, is under the
    $0.0001 floor and is charged $0.00002, not raised to the floor (the
    verifier's V-GR-11 on the parked fix round, 1ce2c8d4 not taken)."""
    assert _charge(0.00002) == 0.00002
    assert _charge(1e-12) == 1e-12
    assert jev_charge_usd(0.0000148) == 0.0000148


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan, -1.0, -1e-9])
def test_infinity_nan_and_negative_are_unreadable_and_charged_the_floor(value: float) -> None:
    """The lead's reading of the owner's rule, 2026-10-09: infinity, NaN and a
    negative figure are unreadable amounts, charged the floor, whether they
    reach `jev_charge_usd` directly or through `_stated_cost_usd`."""
    assert jev_charge_usd(value) == JEV_FLOOR_COST_USD
    assert _stated_cost_usd({"usage": {"cost": value}}) is None


def test_a_stated_zero_is_charged_the_floor() -> None:
    """F-72-J02: a usable reply stating $0 was charged $0, invisible to every cap."""
    assert _charge(0.0) == JEV_FLOOR_COST_USD
    assert _charge(0) == JEV_FLOOR_COST_USD


@pytest.mark.parametrize(
    "raw",
    [
        float("nan"), float("inf"), float("-inf"), "Infinity", -0.1, -(10**400),
        True, False, "not a number", None, [], {},
    ],
    ids=[
        "nan", "infinity", "minus infinity", "the string Infinity", "negative",
        "a negative overflowing int", "true", "false", "a string", "null", "a list", "a map",
    ],
)
def test_no_amount_is_charged_the_floor(raw: object) -> None:
    """F-72-A03: develop charged the one-cent ceiling here, so a drift in
    Jev's reply shape cost about $0.07 a question."""
    assert _charge(raw) == JEV_FLOOR_COST_USD


@pytest.mark.parametrize("payload", [{"usage": {}}, {}, "not even a dict", None, {"usage": None}])
def test_no_cost_field_is_charged_the_floor(payload: object) -> None:
    assert _stated_cost_usd(payload) is None
    assert jev_charge_usd(_stated_cost_usd(payload)) == JEV_FLOOR_COST_USD


@pytest.mark.parametrize(
    "raw",
    [0.0100001, 0.05, 12.5, 1e300, 1e309, math.inf, "Infinity", "0.05", "1e309", 10**400, 10**5000],
    ids=[
        "just above", "five cents", "a units slip", "a huge finite figure", "1e309",
        "infinity", "the string Infinity", "a numeric string", "the string 1e309",
        "an overflowing int", "an int of 5001 digits",
    ],
)
def test_a_stated_cost_above_the_ceiling_is_charged_the_floor(raw: object) -> None:
    """The owner's rule as written: above `MAX_JEV_COST_USD` is "otherwise",
    so the floor, whatever the figure's spelling (fix round, J-GRS-03,
    J-GRS-04, A-GRS-03; develop charged the ceiling). F-8.6-V01: never the
    stated figure either."""
    assert _charge(raw) == JEV_FLOOR_COST_USD


def test_the_boundary_at_the_ceiling() -> None:
    """Exactly `MAX_JEV_COST_USD` is "at most", so charged as stated; the
    next float above it is "otherwise", so the floor."""
    above = math.nextafter(MAX_JEV_COST_USD, math.inf)
    assert jev_charge_usd(MAX_JEV_COST_USD) == MAX_JEV_COST_USD
    assert jev_charge_usd(above) == JEV_FLOOR_COST_USD
    assert jev_charge_usd(sys.float_info.max) == JEV_FLOOR_COST_USD


def test_the_boundary_at_zero() -> None:
    """$0 is not "above $0", so the floor; the smallest float above it is,
    so charged as stated (A-GRS-04, J-GRS-05: left as the rule reads)."""
    smallest = math.nextafter(0.0, 1.0)
    assert jev_charge_usd(0.0) == JEV_FLOOR_COST_USD
    assert jev_charge_usd(-0.0) == JEV_FLOOR_COST_USD
    assert jev_charge_usd(smallest) == smallest


def test_every_charge_is_above_zero_and_at_most_the_ceiling() -> None:
    """Never $0 for a reply that came back, never above the ceiling. A stated
    cost below the floor but above $0 is charged as stated, the owner's
    words."""
    raws: list[object] = [
        float("nan"), float("-inf"), float("inf"), -1.0, 0.0, 1e-12, 0.005, MAX_JEV_COST_USD,
        0.5, 999.9, 10**400, 10**5000, -(10**400), "abc", "0.002", "1e309", True, None,
    ]
    for raw in raws:
        charged = _charge(raw)
        assert 0.0 < charged <= MAX_JEV_COST_USD, (raw, charged)
