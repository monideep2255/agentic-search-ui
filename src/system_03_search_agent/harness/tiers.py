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
below, the single app-config default table this rule allows. The guard and
plan ids in that table are placeholders pending a model-bench (Section
3.6); the synth id is writer bench 3's winner (build phase 8.7,
DECISIONS.md 2026-09-27).

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
# Guard and plan are placeholder values drawn from the Section 3.6 candidate
# list, until a model-bench picks a winner for them. No other module, node,
# or graph file may contain a literal model id string: this table is the
# only place one is allowed to appear. Bare model ids only (no "openrouter/"
# prefix): see the module docstring for why that prefix is call_tier's job.
#
# Synth is a bench winner, not a placeholder (build phase 8.7, T-8.7-02;
# DECISIONS.md 2026-09-27). Writer bench 3 ran eight writers over 18 golden
# questions (`testing/Developer/reports/2026-09-26_writer_bench_3/`):
# Opus 5.5 at minimal reasoning effort withdrew 0 of 54 summaries across
# three runs, against glm-5.2's 9 of 18 in one, at 10.7 s median and 13.3 s
# p90 per writer call. The id is the exact one the bench called
# (`record.model_id` in its raw results). It runs at `minimal` effort, not
# `none`, which it refuses: see `_REASONING_EFFORT_BY_MODEL` below. The
# previous default, z-ai/glm-5.2, is the one-setting rollback
# (`SYNTH_MODEL=z-ai/glm-5.2`), priced by litellm's own map.
#
# Develop sets no `SYNTH_MODEL`, so this default reaches develop when the
# phase merges. Production reaches it only at a release, and only if
# production sets no `SYNTH_MODEL` of its own.
_DEFAULT_MODELS: dict[Tier, str] = {
    "guard": "deepseek/deepseek-v4-flash",
    "plan": "moonshotai/kimi-k2.6",
    "synth": "anthropic/claude-opus-5.5",
}

# Jev, the classifier-seam model (build phase 8.2, DECISIONS.md 2026-09-25,
# cards 8, 9, 10 and 13), is not a fourth tier: it answers a fixed set of
# closed-option decisions through OpenRouter's `/api/alpha/decisions`
# endpoint, never a chat-completions call, and `harness.decide.decide` is
# the only caller. Its default model id still lives in `_DEFAULT_MODELS`
# above, keyed `"jev"` rather than a `Tier`, because
# `test_no_model_id_shaped_string_outside_the_default_table` scans this
# repository for exactly one allowed table of model-id-shaped literals and
# `_DEFAULT_MODELS` is it (system-design-patterns.md pattern 11): a second
# table, even one this file also owns, would be a second place a model id
# is allowed to appear, which is the thing pattern 11 forbids. The `# type:
# ignore` documents the one place this dict's `Tier`-keyed annotation is
# knowingly widened for that reason.
_DEFAULT_MODELS["jev"] = "typesafe/jev-1.13"  # type: ignore[index]

_JEV_ENV_VAR = "JEV_MODEL"


def resolve_jev_model() -> str:
    """Resolve Jev's model id: `JEV_MODEL` env var, else `_DEFAULT_MODELS["jev"]`.

    Mirrors `resolve_model`'s env-first-then-default shape exactly, kept as
    a separate function rather than folded into `resolve_model` because Jev
    is not one of the three `Tier` values and `_validate_tier` must keep
    rejecting anything outside {"guard", "plan", "synth"}.
    """
    env_value = os.environ.get(_JEV_ENV_VAR)
    if env_value:
        return env_value
    return _DEFAULT_MODELS["jev"]  # type: ignore[index]


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
#
# Build phase 8.7, T-8.7-02: Opus 5.5 at $4 and $20 per million tokens, the
# synth default. Source: OpenRouter's catalogue read by writer bench 3 on
# 2026-09-26 (`testing/Developer/reports/2026-09-26_writer_bench_3/results.md`,
# "Candidates and prices"), the same figures litellm 1.93.0's own map
# carries. The bench's metering at this price matched OpenRouter's bill to
# the cent (G-001 run 1: 17,432 prompt and 878 output tokens, $0.087288 both
# ways). It is here although litellm prices it today because
# `requirements.txt` asks for `litellm>=1.40`, not an exact version, so the
# installed map can differ from the tested one, and the writer must stay
# priced before it is called (T-8.6-08) whatever that map holds.
#
# z-ai/glm-5.2 left this table when it stopped being a default:
# `test_no_model_id_shaped_string_outside_the_default_table` allows a model
# id in this file only as a `_DEFAULT_MODELS` value. It is still the
# one-setting rollback, and litellm's map prices it ($0.6496 and $2.0416 per
# million in 1.93.0); `tests/.../harness/test_opus_writer.py` holds that the
# installed map still does.
_FALLBACK_PRICES_USD_PER_TOKEN: dict[str, tuple[float, float]] = {
    "deepseek/deepseek-v4-flash": (0.00000014, 0.00000028),
    "moonshotai/kimi-k2.6": (0.000000646, 0.00000272),
    "anthropic/claude-opus-5.5": (0.000004, 0.00002),
}

# Per-model reasoning effort, for a model whose tier's effort it refuses
# (build phase 8.7, T-8.7-02). `harness.harness._reasoning_for` sends the
# effort named here for a model listed, and the tier's own effort from
# `harness.harness._TIER_REASONING` for every other model, unchanged.
#
# Keyed by model, not by tier, because the refusal belongs to the model:
# Opus refuses `effort: none` on any tier with "Reasoning is mandatory for
# this endpoint and cannot be disabled". Writer bench 3's probe measured
# what happens then: phase 8.6's retry drops the reasoning block, and Opus
# reasons at its own default, 21.4 s per call on the probe and 22.0 s p90 on
# the bench. At `minimal` it spent a median 170 reasoning tokens and wrote at
# 10.7 s median, 13.3 s p90, over 26 writer calls, and 10.8 s and 14.8 s over
# 78 in the finalist round.
#
# It lives here, not in harness.py, for the reason `_FALLBACK_PRICES_USD_
# PER_TOKEN` does: its keys are model ids, and the repository-wide scan
# allows a model id only in this file, and only as a `_DEFAULT_MODELS` value.
_REASONING_EFFORT_BY_MODEL: dict[str, str] = {
    "anthropic/claude-opus-5.5": "minimal",
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
