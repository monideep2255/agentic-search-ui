"""Tier resolution for the three-tier LLM harness (guard, plan, synth).

Depends on:
    - Environment variables: GUARD_MODEL, PLAN_MODEL, SYNTH_MODEL (env.example)

Reads:
    - GUARD_MODEL, PLAN_MODEL, SYNTH_MODEL, at most once per tier per
      TierContext (see below); read fresh on every bare resolve_model() call.

Writes:
    - Nothing.

Model identity is a config value, never a harness or agent decision
(system-design-patterns.md pattern 11; Technical_specification.md Section
3.1, lines 419-427, and Section 3.3, lines 450-465). resolve_model() never
hardcodes a model id inline: the one exception is the _DEFAULT_MODELS table
below, the single app-config default table this rule allows. Every id in
that table is a placeholder pending the Phase 6 model-bench (Section 3.6),
which benches the candidate list named there and writes the winners back
into this table.

This module resolves a tier to a bare model id only (for example
"deepseek/deepseek-v4-flash"), the same shape GUARD_MODEL/PLAN_MODEL/
SYNTH_MODEL hold in env.example. It never places a model call and never
constructs the OpenRouter-prefixed call target itself: wrapping the
resolved id as the literal string passed to LiteLLM (`openrouter/` plus
this function's return value) is `harness.harness.Harness.call_tier`'s job
(T-2.0-02, Section 3.3), not this module's.
"""

from __future__ import annotations

import os
import threading
from typing import Literal

Tier = Literal["guard", "plan", "synth"]

_TIERS: frozenset[str] = frozenset({"guard", "plan", "synth"})

_ENV_VAR_BY_TIER: dict[Tier, str] = {
    "guard": "GUARD_MODEL",
    "plan": "PLAN_MODEL",
    "synth": "SYNTH_MODEL",
}

# The one app-config default table (system-design-patterns.md pattern 11).
# Placeholder values only, drawn from the Section 3.6 candidate list, until
# the Phase 6 model-bench picks a winner per tier. No other module, node, or
# graph file may contain a literal model id string: this table is the only
# place one is allowed to appear. Bare model ids only (no "openrouter/"
# prefix): see the module docstring for why that prefix is call_tier's job.
_DEFAULT_MODELS: dict[Tier, str] = {
    "guard": "deepseek/deepseek-v4-flash",
    "plan": "moonshotai/kimi-k2.6",
    "synth": "z-ai/glm-5.2",
}


# Fallback OpenRouter per-model pricing, (input_price_per_token,
# output_price_per_token) in USD, for models litellm's own static map does
# not yet carry. `harness.harness._price_per_token` tries litellm first and
# falls back to this table.
#
# It lives here rather than in harness.py for the same reason _DEFAULT_MODELS
# does: its keys are literal model ids, and system-design-patterns.md
# pattern 11 permits a model-id-shaped string in this file only. Pricing
# keyed by model identity belongs beside the model identity it prices.
#
# Provenance, and this matters because a wrong price silently mis-bills every
# query: every value below was read from OpenRouter's own public catalogue
# (GET https://openrouter.ai/api/v1/models, fields `pricing.prompt` and
# `pricing.completion`) on 2026-07-29. That is the same source OpenRouter
# bills from. Nothing here is estimated, and nothing is copied from
# documentation that could have drifted.
#
# Why it stopped being empty: none of the three tier defaults above appears
# in litellm's map, so `_price_per_token` raised on every real call and the
# harness could not complete a single model call end to end. The call itself
# succeeded and was billed by OpenRouter; only the pricing lookup failed, so
# the money was spent and the response discarded. Verified live 2026-07-29.
#
# When a price changes, re-read the catalogue rather than hand-editing, and
# never invent a price for a model missing from both sources.
_FALLBACK_PRICES_USD_PER_TOKEN: dict[str, tuple[float, float]] = {
    "deepseek/deepseek-v4-flash": (0.00000014, 0.00000028),
    "moonshotai/kimi-k2.6": (0.000000646, 0.00000272),
    "z-ai/glm-5.2": (0.0000007182, 0.0000022572),
}


class UnknownTierError(ValueError):
    """Raised when a tier outside {"guard", "plan", "synth"} is requested."""


def _validate_tier(tier: str) -> Tier:
    """Return `tier` if it is a recognized tier, else raise UnknownTierError.

    Raised before any environment lookup or model call is attempted, so an
    invalid tier never reaches LiteLLM, OpenRouter, or the network.
    """
    if tier not in _TIERS:
        raise UnknownTierError(f"unknown tier {tier!r}: expected one of {sorted(_TIERS)}")
    return tier  # type: ignore[return-value]


def resolve_model(tier: Tier) -> str:
    """Resolve a harness tier to a concrete, bare model id.

    Reads GUARD_MODEL, PLAN_MODEL, or SYNTH_MODEL from the environment
    depending on `tier` and returns it when set to a non-empty value. Falls
    back to the app-config default in `_DEFAULT_MODELS` when the env var is
    unset or empty. Model identity is a config value; swapping a model is
    an env edit or a `_DEFAULT_MODELS` edit, never a code change elsewhere.
    The returned id is bare (e.g. "deepseek/deepseek-v4-flash"); prefixing
    it as the `openrouter/<model_id>` LiteLLM call target is the caller's
    job (`Harness.call_tier`, T-2.0-02), not this function's.

    This function reads the environment fresh on every call. A caller that
    needs the same tier's model held stable for an entire query, per
    prompt-cache-discipline.md obligation 1 ("the model per tier never
    switches mid-query"), should resolve through a `TierContext` instead of
    calling this function directly inside a running query.

    Raises:
        UnknownTierError: if `tier` is not one of "guard", "plan", "synth".
            Raised before the environment is read.
    """
    validated = _validate_tier(tier)
    env_value = os.environ.get(_ENV_VAR_BY_TIER[validated])
    if env_value:
        return env_value
    return _DEFAULT_MODELS[validated]


class TierContext:
    """Per-query cache of resolved tier-to-model-id values.

    A tier's resolved model is fetched once at query start and held for
    the query's duration (system-design-patterns.md pattern 11;
    prompt-cache-discipline.md obligation 1). A caller constructs exactly
    one `TierContext` per query and resolves every tier through it, so a
    query never re-reads the environment mid-flight and never observes a
    tier's model id change partway through, even if `GUARD_MODEL`,
    `PLAN_MODEL`, or `SYNTH_MODEL` is mutated in the environment while the
    query is in flight.

    Thread-safe: a lock guards the resolved-value cache so two Act-step
    tool calls resolving the same tier concurrently within one query
    context never each race into their own `resolve_model()` call.
    """

    def __init__(self) -> None:
        self._resolved: dict[Tier, str] = {}
        self._lock = threading.Lock()

    def resolve(self, tier: Tier) -> str:
        """Return this query's cached model id for `tier`.

        Resolves and caches via `resolve_model()` on the first call for a
        given tier within this context. Every later call for the same tier
        on this same context returns the cached value without re-reading
        the environment.

        Raises:
            UnknownTierError: if `tier` is not one of "guard", "plan",
                "synth". Raised before any cache lookup or environment read.
        """
        validated = _validate_tier(tier)
        with self._lock:
            if validated not in self._resolved:
                self._resolved[validated] = resolve_model(validated)
            return self._resolved[validated]
