"""The three-tier LLM harness (guard, plan, synth) for the search agent.

Tier resolution (`tiers.py`) is the only module here so far: it maps a
tier name to a concrete OpenRouter model id, per the app-config default
table in `tiers.py`, and offers `TierContext` for holding a tier's
resolved model stable across one query (system-design-patterns.md pattern
11; prompt-cache-discipline.md obligation 1).

The LiteLLM/OpenRouter call wrapper, cost accounting, cost caps, per-step
timeouts, the coordinator-worker split, and the prompt-cache stable-prefix
scaffold are separate, later tickets (T-2.0-02 through T-2.0-06) and do
not live in this package yet.
"""

from system_03_search_agent.harness.tiers import (
    Tier,
    TierContext,
    UnknownTierError,
    resolve_model,
)

__all__ = ["Tier", "TierContext", "UnknownTierError", "resolve_model"]
