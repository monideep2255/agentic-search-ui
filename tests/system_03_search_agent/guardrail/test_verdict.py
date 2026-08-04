"""`guardrail.verdict`: the invariants that keep a refusal a refusal.

No model, no network. These are the guarantees every other module in the
package relies on without re-checking.
"""

from __future__ import annotations

import pytest

from system_03_search_agent.contracts.events import GuardPayload
from system_03_search_agent.guardrail.verdict import (
    MAX_REASON_LENGTH,
    GuardCategory,
    GuardVerdict,
    admitted,
    refused,
)


def test_guard_category_matches_the_event_contract_exactly() -> None:
    """The one test that keeps `GuardCategory` from drifting.

    `verdict.py` declares its own `Literal` rather than importing the
    contract's, so the guardrail package does not depend on the event layer
    for a type it uses internally. That is a real decoupling and it buys a
    real risk: two hand-maintained lists that must agree. This test is what
    makes a drift fail loudly instead of producing a verdict the event
    contract will later reject at emit time, deep inside a run.
    """
    contract_categories = set(GuardPayload.model_fields["category"].annotation.__args__)
    verdict_categories = set(GuardCategory.__args__)
    assert verdict_categories == contract_categories


def test_an_admitted_verdict_must_carry_ok() -> None:
    with pytest.raises(ValueError, match="must carry category 'ok'"):
        GuardVerdict(admitted=True, category="injection")


def test_a_refused_verdict_cannot_carry_ok() -> None:
    """The invariant that stops a refusal from being silently upgraded.

    A `GuardVerdict(admitted=False, category="ok")` would emit a `guard`
    event that reads as a pass to anything checking `category` and as a
    refusal to anything checking `passed`. Two consumers, two answers, from
    one event.
    """
    with pytest.raises(ValueError, match="cannot carry category 'ok'"):
        GuardVerdict(admitted=False, category="ok")


def test_refused_rejects_ok_as_a_category() -> None:
    with pytest.raises(ValueError, match="requires a refusal category"):
        refused("ok", "this is not a refusal")  # type: ignore[arg-type]


def test_admitted_takes_no_arguments_and_is_always_the_same() -> None:
    assert admitted() == GuardVerdict(admitted=True, category="ok", reason=None)


def test_a_verdict_is_frozen() -> None:
    """A verdict is evidence of a decision, not a mutable accumulator."""
    verdict = refused("off_topic", "not biomedical")
    with pytest.raises(Exception):  # noqa: B017 - pydantic/dataclass both raise
        verdict.admitted = True  # type: ignore[misc]


def test_refused_truncates_a_long_reason_rather_than_raising() -> None:
    """A refusal must never fail to be produced.

    If `refused()` raised on an over-long reason, a screen building one would
    propagate that error instead of returning its refusal, and the query it
    was trying to block would reach the next step. Truncation is the safe
    failure here and the direction is deliberate.
    """
    verdict = refused("injection", "x" * (MAX_REASON_LENGTH + 500))
    assert verdict.admitted is False
    assert verdict.reason is not None
    assert len(verdict.reason) == MAX_REASON_LENGTH


def test_a_reason_over_the_cap_cannot_be_constructed_directly() -> None:
    """Truncation is `refused()`'s job, not a silent property of the type.

    Constructing the dataclass directly with an over-long reason raises, so a
    caller that bypasses `refused()` is told rather than quietly having its
    message cut in a place it did not choose. `GuardPayload.reason` caps at
    the same 256, and a reason truncated at an arbitrary point can read as a
    different statement than the one written.
    """
    with pytest.raises(ValueError, match="exceeds"):
        GuardVerdict(
            admitted=False, category="injection", reason="x" * (MAX_REASON_LENGTH + 1)
        )


def test_every_refusal_category_can_be_emitted_on_a_real_guard_payload() -> None:
    """End-to-end on the type boundary: a verdict must survive becoming an event.

    Catches the failure where a verdict is internally valid and the contract
    rejects it at emit time, which happens inside a run rather than in a test.
    """
    for category in GuardCategory.__args__:
        if category == "ok":
            payload = GuardPayload(passed=True, category="ok", reason=None)
            assert payload.passed is True
            continue
        verdict = refused(category, "a reason")
        payload = GuardPayload(
            passed=verdict.admitted,
            category=verdict.category,
            reason=verdict.reason,
        )
        assert payload.passed is False
        assert payload.category == category
