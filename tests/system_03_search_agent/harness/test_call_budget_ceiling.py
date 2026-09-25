"""Ordinary unit test: at most 20 Layer 2/3 calls per query.

Moved out of the deleted `test_rate_limit_concurrency_premise.py` and
`test_rate_limit_concurrency_mutation.py` (build phase 4.14 bossman
redesign, 2026-09-24,
`docs/build/Bossman_redesign_deletion_inventory.md`). Section 21.3
requires a hard per-query ceiling on Layer 2/3 calls, counted at the
transport chokepoint (`charge_one_call`), never at `act_node`. This test
pins the ceiling itself: the 21st call in one query scope is refused, a
fresh scope resets the count to zero, and no scope means the charge is a
no-op rather than an error (a KGX export or maintenance script is not a
query).
"""

from __future__ import annotations

import pytest

from system_03_search_agent.harness import call_budget


def test_the_ceiling_constant_is_twenty() -> None:
    assert call_budget.MAX_LAYER_2_3_CALLS_PER_QUERY == 20


def test_the_21st_call_in_one_query_scope_is_refused() -> None:
    with call_budget.query_budget_scope("lookup"):
        for _ in range(20):
            call_budget.charge_one_call(tool="ncbi_efetch", layer=2)
        with pytest.raises(call_budget.CallBudgetExceededError):
            call_budget.charge_one_call(tool="ncbi_efetch", layer=2)


def test_a_fresh_scope_resets_the_count() -> None:
    with call_budget.query_budget_scope("lookup"):
        for _ in range(20):
            call_budget.charge_one_call(tool="ncbi_efetch", layer=2)
    with call_budget.query_budget_scope("lookup"):
        assert call_budget.calls_made() == 0
        call_budget.charge_one_call(tool="ncbi_efetch", layer=2)
        assert call_budget.calls_made() == 1


def test_charging_with_no_bound_scope_is_a_silent_no_op() -> None:
    assert call_budget.calls_made() is None
    call_budget.charge_one_call(tool="ncbi_efetch", layer=2)
    assert call_budget.calls_made() is None
