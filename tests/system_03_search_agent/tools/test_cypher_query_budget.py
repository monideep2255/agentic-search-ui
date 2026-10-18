"""R-09 (phase 8.6's re-land follow-up): the graph search's time limit is
30 seconds again, the figure `tool-call-budgets.md` and technical
specification Section 6.1 state (the product owner's decision of
2026-09-26, "Back to 30 seconds").

What these arms pin:
    - `CYPHER_QUERY_TIMEOUT_SECONDS` is 30.0, and it is the value
      `cypher_query` hands to its own overall `asyncio.wait_for`.
    - A call that would take 35 seconds is cut at 30 with the actionable
      timeout message, which names the whole budget and what to retry.
    - A call that takes 3 seconds is unaffected.
    - Act never gives a graph call less than the tool's own budget, and
      its lookup-class wait is now 30 seconds, not 90.

What they deliberately omit: the live graph and a live plan-tier call. The
pipeline behind the tool's outer bound is stubbed, and the clock is scaled
a thousandfold (35 seconds is slept as 35 ms, and the 30-second bound is
applied as 30 ms) so the arm runs in milliseconds; the timeout VALUE the
tool passes is captured unscaled and asserted, so a budget other than 30
is caught whatever the scale.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from system_03_search_agent.harness.harness import budget_for_step
from system_03_search_agent.tools import cypher_query as cypher_query_module
from system_03_search_agent.tools import graph_schema_constants

_SCALE = 1000.0


def test_the_graph_search_budget_is_thirty_seconds() -> None:
    assert graph_schema_constants.CYPHER_QUERY_TIMEOUT_SECONDS == 30.0
    assert cypher_query_module.CYPHER_QUERY_TIMEOUT_SECONDS == 30.0


def _scaled_run(monkeypatch: pytest.MonkeyPatch, pipeline_s: float) -> list[float]:
    """Stub the pipeline to take `pipeline_s` seconds, scaled; record every
    timeout `cypher_query` passes to `asyncio.wait_for`, unscaled."""
    seen: list[float] = []
    real_wait_for = asyncio.wait_for

    async def _pipeline(*_args: Any, **_kwargs: Any) -> Any:
        await asyncio.sleep(pipeline_s / _SCALE)
        return SimpleNamespace(status="ok", rows=[{"id": "NCBIGene:672"}], error=None)

    async def _wait_for(awaitable: Any, timeout: float) -> Any:
        seen.append(timeout)
        return await real_wait_for(awaitable, timeout / _SCALE)

    monkeypatch.setattr(cypher_query_module, "_run_pipeline", _pipeline)
    monkeypatch.setattr(
        cypher_query_module, "asyncio", SimpleNamespace(wait_for=_wait_for), raising=True
    )
    return seen


@pytest.mark.asyncio
async def test_a_35_second_graph_call_is_cut_at_30_with_the_actionable_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MUTATION PROOF: setting the constant back to 90.0 turns this red,
    twice over: the captured budget is 90, and the 35-second call finishes
    inside it instead of being cut."""
    seen = _scaled_run(monkeypatch, pipeline_s=35.0)
    output = await cypher_query_module.cypher_query(None, None)  # type: ignore[arg-type]

    assert seen == [30.0]
    assert output.status == "error"
    assert output.rows == []
    assert "cypher_query exceeded its 30s overall budget" in output.error
    assert "retry with a narrower query_intent or a smaller query_class" in output.error


@pytest.mark.asyncio
async def test_a_3_second_graph_call_is_unaffected(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _scaled_run(monkeypatch, pipeline_s=3.0)
    output = await cypher_query_module.cypher_query(None, None)  # type: ignore[arg-type]
    assert seen == [30.0]
    assert output.status == "ok"
    assert output.rows == [{"id": "NCBIGene:672"}]


@pytest.mark.parametrize(
    ("query_class", "act_wait_s"),
    [("lookup", 30.0), ("single_hop", 30.0), ("aggregate", 30.0), ("multi_hop", 30.0), ("exploratory", 120.0)],
)
def test_act_never_cuts_a_graph_call_inside_the_tools_own_budget(
    query_class: str, act_wait_s: float
) -> None:
    """Act waits `max(class budget, the tool's own budget)` for the graph
    call (`core.graph.act_node`), so the tool's own 30 seconds is always a
    floor under Act's wait; before R-09 the first four classes waited 90.
    This arm states the values; `test_cq_routing_premise.py`'s p12b
    observes the timeout the real Act line hands to `enforce_timeout`."""
    from system_03_search_agent.core import graph as graph_module

    assert graph_module.CYPHER_QUERY_TIMEOUT_SECONDS == 30.0
    got = max(budget_for_step("act", query_class), graph_module.CYPHER_QUERY_TIMEOUT_SECONDS)  # type: ignore[arg-type]
    assert got == act_wait_s
