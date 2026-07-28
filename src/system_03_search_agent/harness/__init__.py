"""The three-tier LLM harness (guard, plan, synth) for the search agent.

Tier resolution (`tiers.py`) maps a tier name to a concrete OpenRouter
model id, per the app-config default table in `tiers.py`, and offers
`TierContext` for holding a tier's resolved model stable across one query
(system-design-patterns.md pattern 11; prompt-cache-discipline.md
obligation 1).

`harness.py` wraps LiteLLM/OpenRouter calls with cost accounting and
per-step timeouts. `cost_control.py` owns the four Section 19.1 cost
caps and the `cost` event. `coordinator_worker.py` implements the
Section 3.4 coordinator-worker split. `cache.py` builds the Section 4.2
prompt-cache stable prefix. All four were built in build phase 2.0
(T-2.0-02 through T-2.0-06) and are wired into `core/graph.py`'s
five-node loop.
"""

from system_03_search_agent.harness.tiers import (
    Tier,
    TierContext,
    UnknownTierError,
    resolve_model,
)

__all__ = ["Tier", "TierContext", "UnknownTierError", "resolve_model"]
