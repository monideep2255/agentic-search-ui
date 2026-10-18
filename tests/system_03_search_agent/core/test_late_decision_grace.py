"""F-8.6-V07: the late-read grace that fixed A14 was protected by no test
that could see the grace grow. The two tests meant to pin it both defeat
themselves: `test_a_literature_decision_still_running_at_plan_gets_only_
the_grace` (test_bare_topic_clarification.py) patches
`_LATE_DECISION_GRACE_S` to 0.05 itself, so a real regression in the
constant is invisible behind the patch, and `test_plans_literature_read_
takes_not_literature_after_the_grace` (same file) asserts
`elapsed < graph_module._LATE_DECISION_GRACE_S + 0.5`, measuring the
constant against itself, so it passes whatever the grace is set to.

This file adds the one test the phase's own re-land ticket (R-04) asks
for: a decision that never finishes, read through `_literature_choice`
with the REAL, unpatched `_LATE_DECISION_GRACE_S`, and a hard, absolute
ceiling on how long Plan may wait for it. `_LATE_DECISION_GRACE_S` is 1.0
second (`core/graph.py`); this test's 2.0-second ceiling gives the real
grace, plus scheduling slack, all the room it needs while still catching
the regression the verifier measured: setting the constant to 30.0 held
Plan for the full 30 seconds.

MUTATION PROOF: `_LATE_DECISION_GRACE_S: Final[float] = 1.0` raised to
30.0 in `core/graph.py` turns this test red (measured by the verifier,
F-8.6-V07, at 14.00s with a 14-second hang).
"""
from __future__ import annotations

import asyncio
import time

import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import harness as harness_module


@pytest.mark.asyncio
async def test_plan_never_waits_past_two_seconds_for_a_decision_that_never_finishes() -> None:
    """The real `_LATE_DECISION_GRACE_S` is never patched here. A decision
    started by Think and never returning is read by `_literature_choice`,
    the way Plan reads it, and Plan must move on well under 2 seconds,
    not merely under whatever the grace constant currently says."""
    harness = harness_module.Harness("t-late-grace-v07")
    entry = graph_module._run_decisions(harness)
    stopped = asyncio.Event()

    async def _hang() -> None:
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            stopped.set()
            raise

    entry.literature_task = asyncio.create_task(_hang())
    started = time.monotonic()
    choice = await graph_module._literature_choice(
        harness,
        "t-late-grace-v07",
        "papers on statins",
        ask_if_missing=True,
        deadline=time.monotonic() + 45.0,
    )
    elapsed = time.monotonic() - started
    await asyncio.sleep(0)

    assert choice is None
    assert elapsed < 2.0, elapsed
    assert entry.literature_asked and entry.literature_task is None
    assert stopped.is_set()
