"""Harness.call_tier: the LiteLLM/OpenRouter call wrapper with cost accounting.

Depends on:
    - system_03_search_agent.harness.tiers (Tier, TierContext, resolve_model,
      UnknownTierError)
    - litellm (>=1.40, pinned in requirements.txt): litellm.acompletion for
      the model call, litellm.get_model_info for OpenRouter per-model
      pricing, and the litellm.exceptions hierarchy for failure
      classification

Reads:
    - Environment: GUARD_MODEL, PLAN_MODEL, SYNTH_MODEL, indirectly, via
      system_03_search_agent.harness.tiers.TierContext
    - litellm's static OpenRouter price map (litellm.get_model_info), to
      compute call_cost_usd

Writes:
    - Nothing. This module has no side effects beyond the outbound LiteLLM
      call itself. Running cost totals live in-process on the Harness
      instance (Section 19.2's in-process, single-instance v1 model); they
      are not persisted here. Persisting to the interactions table and
      emitting the `cost` event onto the Section 2 stream are T-2.0-03's
      job (cost_control.py), built against the accumulator this module
      exposes (get_query_cost_usd).

Ticket and scope boundary (Technical_specification.md Section 3.3 lines
450-465, Section 3.5 lines 508-540, Section 19.2 lines 2813-2819;
tracker/phase_2.0.md T-2.0-02): this ticket implements exactly two of the
five methods on Section 3.5's `Harness` class shape: `call_tier` and
`track_cost`. The other three are explicitly out of scope for this file
and are NOT implemented here:

    - `resolve_model` -- already implemented in `tiers.py` (T-2.0-01).
      This class does not re-implement tier resolution; `call_tier` calls
      it indirectly through one `TierContext` instance held per `Harness`.
    - `enforce_timeout` -- implemented below by T-2.0-04
      (Technical_specification.md Section 19.1 lines 2800-2811, Section
      3.5 lines 508-540; tracker/phase_2.0.md T-2.0-04), which also adds
      the `query_class` to `budget_s` mapping table
      (`_QUERY_CLASS_BUDGET_S`/`budget_for_query_class`), decided and
      logged in DECISIONS.md 2026-07-28. Nothing in T-2.0-02's own code
      above was changed to add it.
    - `coordinator_worker_execute` -- T-2.0-05's ticket, a separate module
      (`coordinator_worker.py`). Not present on this class either.

`QueryClass` (used only by the T-2.0-04 addition below) mirrors
`contracts.events.ThinkPayload.query_class`'s five-value Literal. It is
declared locally rather than imported, since `events.py` does not export a
standalone name for it; keep the two in sync by hand if that Literal ever
changes.

`cache_prefix` placeholder (T-2.0-06, Section 4.2, prompt-cache-discipline
obligation 1): `call_tier` accepts a `cache_prefix` parameter and, when
given, prepends it to `messages` as a leading system-role message, since
the stable prefix's fixed position is the head of the message list sent to
the model. The actual prefix-assembly logic (`build_stable_prefix()`, the
SHA-256 byte-equality guarantee across differing dynamic suffixes) is
T-2.0-06's ticket (`cache.py`), not built yet. `cache_prefix` is typed
`str | None` here, not the eventual `CachePrefix` type named in Section
3.5's signature, since that type does not exist until T-2.0-06 defines it;
it defaults to `None` so this ticket does not block on an unbuilt module.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any, Literal

import litellm

from system_03_search_agent.harness.tiers import (
    _FALLBACK_PRICES_USD_PER_TOKEN as _TIER_FALLBACK_PRICES,
)
from system_03_search_agent.harness.tiers import Tier, TierContext

# A LiteLLM chat message: {"role": "system" | "user" | "assistant", "content": str}.
# LiteLLM's own `completion`/`acompletion` accept `list[dict]`; this alias
# names the shape without introducing a new dependency or schema.
Message = dict[str, str]

ErrorClass = Literal["transient", "recoverable", "unexpected"]

# Mirrors contracts.events.ThinkPayload.query_class (see module docstring).
QueryClass = Literal["lookup", "single_hop", "multi_hop", "aggregate", "exploratory"]


class UnknownStepError(ValueError):
    """Raised when a budget is requested for a step outside the five-step loop.

    A typo in a caller would otherwise resolve to a silently wrong timeout,
    which is the failure a per-step budget exists to prevent.
    """


class HarnessCallError(RuntimeError):
    """A classified call_tier failure (transient, recoverable, or unexpected).

    Section 3.5's fail-fast discipline: every tool or model-call failure is
    classified before any retry decision, so a model-caused failure (a bad
    completion, `recoverable`) is distinguishable from a harness-caused one
    (a timeout or rate limit, `transient`) and from anything else
    (`unexpected`). `call_tier` raises this, never a silent default or an
    empty completion, on an exhausted-retry transport failure or a pricing
    gap it cannot resolve.
    """

    def __init__(
        self, message: str, *, error_class: ErrorClass, source: str = "harness.call_tier"
    ) -> None:
        super().__init__(message)
        self.error_class: ErrorClass = error_class
        self.source = source


@dataclass(frozen=True)
class LLMResponse:
    """One successful `call_tier` result: the completion plus its metering.

    `call_cost_usd` is this call's own cost, not a running total; `Harness`
    accumulates running totals separately via `track_cost`/
    `get_query_cost_usd`.
    """

    content: str
    prompt_tokens: int
    completion_tokens: int
    call_cost_usd: float
    model_id: str
    tier: Tier


# Exceptions where the request itself was never the problem: a provider- or
# network-side hiccup that a bare retry can plausibly clear. Section 3.5
# names these "harness-caused" (a timeout, a rate limit). Exactly one retry.
_TRANSIENT_EXCEPTIONS: tuple[type[BaseException], ...] = (
    litellm.RateLimitError,
    litellm.APIConnectionError,
    litellm.Timeout,
    litellm.ServiceUnavailableError,
    litellm.InternalServerError,
    litellm.BadGatewayError,
)

# Exceptions where the request shape itself is the problem: retrying the
# identical request would fail identically. Section 3.5 names this class
# "model-caused" (a bad completion / a bad request). No automatic retry
# inside call_tier; the caller (Think/Plan/Write) decides whether to
# reissue a *different* call_tier invocation with an adjusted request.
_RECOVERABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    litellm.BadRequestError,
    litellm.ContextWindowExceededError,
    litellm.ContentPolicyViolationError,
    litellm.UnprocessableEntityError,
)


def _classify_exception(exc: BaseException) -> ErrorClass:
    """Classify a call failure as transient, recoverable, or unexpected.

    Order matters: check the narrower, more specific transient/recoverable
    sets before falling through to unexpected, since some litellm exception
    types subclass others (e.g. every listed exception ultimately derives
    from `litellm.exceptions.APIError`).
    """
    if isinstance(exc, _TRANSIENT_EXCEPTIONS):
        return "transient"
    if isinstance(exc, _RECOVERABLE_EXCEPTIONS):
        return "recoverable"
    return "unexpected"


# Fallback OpenRouter per-model pricing, (input_price_per_token,
# output_price_per_token) in USD. Primary pricing comes from litellm's own
# maintained static map (litellm.get_model_info); this table exists only
# for the gap where a resolved tier's model id (including the
# tiers.py._DEFAULT_MODELS placeholders, themselves pending the Phase 6
# model-bench) is not yet present in litellm's map. OpenRouter's live
# catalog is larger than the ~96 "openrouter/*" entries litellm ships, so
# this gap is real, not hypothetical. Extend this table, or wait for
# litellm to add the model upstream, whichever lands first; never invent a
# price for a model missing from both sources (see _price_per_token below).
# Fallback OpenRouter per-model pricing, re-exported from tiers.py.
#
# The table itself lives in tiers.py, not here, because its keys are model
# ids and system-design-patterns.md pattern 11 allows a literal model id in
# exactly one file. Pricing keyed by model identity belongs next to the
# model identity it prices. This name is kept so existing callers and tests
# that patch harness._FALLBACK_PRICES_USD_PER_TOKEN keep working.
_FALLBACK_PRICES_USD_PER_TOKEN = _TIER_FALLBACK_PRICES


def _price_per_token(model_id: str) -> tuple[float, float]:
    """Return (input_price_per_token, output_price_per_token) in USD for model_id.

    Primary source: `litellm.get_model_info(model=f"openrouter/{model_id}")`,
    LiteLLM's own maintained OpenRouter price map. Section 19.2 requires
    "the OpenRouter price for the exact model that answered"; this is the
    most direct way to get that price without hand-maintaining a duplicate
    table for models litellm already prices, and it stays current as
    litellm updates its map upstream.

    Fallback: `_FALLBACK_PRICES_USD_PER_TOKEN`, for a model litellm does not
    yet map.

    Raises:
        HarnessCallError: error_class="unexpected", if neither source has a
            price for model_id. A resolved model with no known price is a
            configuration gap to surface, never silently priced at zero.
    """
    target = f"openrouter/{model_id}"
    try:
        info = litellm.get_model_info(model=target)
        input_price = info.get("input_cost_per_token")
        output_price = info.get("output_cost_per_token")
        if input_price is not None and output_price is not None:
            return float(input_price), float(output_price)
    except Exception:  # noqa: BLE001, S110 - fall through to the local table below; no data is lost, the fallback path is exercised next
        pass

    if model_id in _FALLBACK_PRICES_USD_PER_TOKEN:
        return _FALLBACK_PRICES_USD_PER_TOKEN[model_id]

    raise HarnessCallError(
        f"no OpenRouter price found for model {model_id!r} in litellm's "
        "price map or the local fallback table; add it to "
        "harness.harness._FALLBACK_PRICES_USD_PER_TOKEN or wait for "
        "litellm's static map to include it, then retry the query",
        error_class="unexpected",
        source="harness.harness._price_per_token",
    )


# T-2.0-04 / Section 19.1's per-step timeout budgets, in seconds, keyed by
# Think's emitted query_class. Section 19.1's table names four classes
# (lookup, single-hop, multi-hop, deep research); ThinkPayload.query_class
# ships five. Mapping decided and logged in DECISIONS.md 2026-07-28:
# `aggregate` reads as multi-hop-shaped work (combining several
# already-resolved facts), so it takes the multi-hop budget; `exploratory`
# reads as the deep-research class Section 19.1 already budgets for at 2
# minutes. Do not re-derive this mapping; it is a settled decision.
# Per-tier reasoning depth and output ceiling.
#
# OpenRouter exposes one `reasoning.effort` dial that drives each provider's
# own native control (a token budget on Anthropic, an effort tier on OpenAI,
# a thinking flag on Google), so switching models does not mean rewriting
# the control. Verified live on 2026-07-29: all three tier defaults report
# `reasoning` in OpenRouter's `supported_parameters`, and litellm passes the
# block straight through.
#
# The effort per tier follows Section 3.1's tier purposes exactly, not a new
# decision: Guard is classification, Plan is decomposition and the Cypher
# generation call, Synth assembles already-verified data and is explicitly
# forbidden from open-ended reasoning over unverified payloads.
#
# max_tokens is not decoration. Reasoning tokens are counted inside
# `completion_tokens` (verified live: a trivial prompt spent 74 of its 76
# output tokens on reasoning), so they are billed at the output rate and an
# uncapped reasoning model is an uncapped bill. Every call carries a ceiling.
_TIER_REASONING: dict[Tier, dict[str, Any]] = {
    # Guard reasoning is OFF, not merely minimal. Section 3.1 specifies this
    # tier as "sub-second, fractions of a cent", and its job is validation
    # and classification, which is not a reasoning task.
    #
    # Measured: with `effort: "minimal"` a guard call did not return inside
    # the 5-second per-step budget, so `enforce_timeout` killed it and the
    # harness classified the result as a transient failure. Every query then
    # died at the guardrail with "a step hit a temporary error", which is
    # true but unhelpful, since the real cause was the tier's own reasoning
    # budget. "minimal" still emits reasoning tokens on the current guard
    # model; only "none" actually turns them off.
    "guard": {"effort": "none"},
    # F-2.1-C11. The plan tier ran at "high", and that single setting was
    # the whole of F-2.1-B02: 9 of 10 real queries timed out, first against
    # a 30-second budget and then, unchanged, against the 90-second budget
    # commit 9a3f50a widened it to. Widening treated the symptom. The cause
    # was that this tier spent almost its entire output on reasoning tokens
    # to write one line of Cypher: 1014 output tokens for a single query, of
    # which 970 were reasoning.
    #
    # Measured over the five query shapes that were timing out (two-entity
    # compare, disease list, plain lookup, node-plus-aggregate, multi-hop),
    # two runs each:
    #
    #   effort "high": 163.0s total, up to 84.3s on multi-hop alone
    #   effort "none":   6.1s total, 2.2s at worst
    #
    # All five were CORRECT at both settings, and neither setting ever
    # interpolated an entity id as a literal. The reasoning tokens bought
    # nothing measurable on this tier's actual workload and cost roughly a
    # 27x latency multiple, so the budget could never have been widened far
    # enough to hide it.
    #
    # Scope this honestly: today the plan tier generates one Cypher query
    # against a fixed schema, which is translation, not reasoning. When
    # build phase 3.x gives this tier real multi-tool decomposition, this
    # setting is measured again on that workload rather than assumed to
    # carry over.
    "plan": {"effort": "none"},
    "synth": {"effort": "low"},
}

_TIER_MAX_TOKENS: dict[Tier, int] = {
    # Guard is validation and classification, which Section 3.1 budgets as
    # "sub-second, fractions of a cent". 1000 was not a ceiling this tier
    # ever approached on purpose, it was a ceiling it hit: a Guard call
    # measured `out=1000` exactly, every time, because the step sent a bare
    # question with no instruction and the model answered it at length.
    # 128 is ample for a verdict and makes the ceiling a real bound rather
    # than a target.
    "guard": 128,
    "plan": 4_000,
    "synth": 4_000,
}


# Section 19.1's per-step budgets, widened for `lookup` and `single_hop`
# against measured model latency.
#
# Section 19.1's original figures were written before any model call had
# been made, and the first end-to-end run through a browser showed the
# `lookup` budget of 5.0 seconds was not survivable. Measured on the
# configured guard model (deepseek-v4-flash via OpenRouter), five warm
# guard-shaped calls: 719, 1380, 1433, 783, and 4615 ms, plus roughly
# 6000 ms for the first call in a cold process. The spread reaches the old
# budget, so a query died at the guardrail more often than not, and the
# failure surfaced as a generic "a step hit a temporary error" that gave no
# hint the cause was the budget rather than the provider.
#
# Every model call in the loop is a step under one of these budgets, and
# the guardrail hardcodes the `lookup` figure regardless of the eventual
# query class, so `lookup` is the floor every single query must clear.
#
# `lookup` moves 5.0 -> 15.0 and `single_hop` 10.0 -> 20.0, roughly three
# times the observed worst case, which leaves headroom for provider
# variance without masking a genuinely hung call. The three larger classes
# are untouched: nothing measured suggests they are tight, and widening a
# budget nobody has evidence against would be guessing in the other
# direction.
#
# These are latency budgets, not cost caps. The per-query and daily dollar
# caps in Section 19.1 are unchanged, so a slower step still cannot spend
# more than its cap allows. Product owner approved this change on
# 2026-07-29 on the strength of the measurements above.
#
# The `aggregate` and `exploratory` mapping below is a settled decision
# (DECISIONS.md 2026-07-28); do not re-derive it.
_QUERY_CLASS_BUDGET_S: dict[QueryClass, float] = {
    "lookup": 15.0,
    "single_hop": 20.0,
    "aggregate": 30.0,
    "multi_hop": 30.0,
    "exploratory": 120.0,
}


# Which tier each step of the loop runs on (Section 3.2's step-to-tier
# assignment, restated here so a budget can be resolved from a step name).
# `act` is deliberately absent: it is not a single tier's call, it runs the
# tool plus a Guard-tier reader pass, and its budget comes from the query
# class instead. See `budget_for_step`.
#
# `think` maps to `"guard"` through build phase 2.0's stub, which made a
# Guard-tier call whose response it discarded. Build phase 4.7 (T-4.7-04)
# gives `think_node` a real classification and entity-extraction call, and
# Section 17 is explicit that this call runs "via the Plan-tier model, on
# every query", not the Guard tier: `think` moved here so this step's own
# per-step timeout budget (below, `_TIER_STEP_BUDGET_S`) tracks the tier
# that actually answers it, the same principle this table's own docstring
# already states for why the budget is keyed on tier rather than on query
# class. Left mapped to `"guard"` here, the plan-tier call (documented at
# roughly 15 to 45 seconds in the measurements above) would race a 15
# second guard-tier budget on every query.
_STEP_TIER: dict[str, Tier] = {
    "guardrail": "guard",
    "think": "plan",
    "plan": "plan",
    "write": "synth",
}

# Per-step timeout by tier, in seconds.
#
# Section 19.1 budgets a per-step timeout but selects the value by QUERY
# CLASS alone, so every step of a lookup query got the same 5.0 s. The two
# axes are not the same thing: query class describes how hard the question
# is, while what a step actually costs is driven by which tier answers it.
# Measured on the configured models at the reasoning effort each tier runs:
#
#   guard  deepseek-v4-flash, effort none:               719 to 4615 ms
#   plan   kimi-k2.6, effort high, 4000-token ceiling:   both completed and
#                                                        exceeded 15 s on
#                                                        the same query
#   synth  glm-5.2, effort low, over real graph rows:    17527, 19196,
#                                                        19343, 21572 ms
#
# No single per-query-class number fits those three at once. Raising the
# query-class figure until synth fits hands the same loose budget to a
# guard classification, which is exactly where a tight timeout is worth
# having; leaving it where synth cannot fit kills every query at Write.
#
# A per-step timeout exists to kill a HUNG step, so each value answers
# "this step should never legitimately take this long" for its own tier,
# rather than inheriting a number chosen for the query as a whole.
#
# PROVISIONAL. These come from three or four calls per tier, enough to show
# the original figures were unworkable and not enough to set a production
# value. They are also model-dependent: build phase 7.0 (model-bench) picks
# the tier winners, and these should be re-measured against whatever wins.
# `Technical_specification.md` Section 19.1 still describes the old
# query-class-only shape and is a Step 6.2 reconciliation item.
_TIER_STEP_BUDGET_S: dict[Tier, float] = {
    "guard": 15.0,
    "plan": 45.0,
    "synth": 45.0,
}


def budget_for_step(step: str, query_class: QueryClass) -> float:
    """Per-step timeout in seconds for `step` on a query of `query_class`.

    Two shapes, because two kinds of step:

    - A model-calling step (guardrail, think, plan, write) is bounded by
      what its own tier costs, from `_TIER_STEP_BUDGET_S`. A guard
      classification does not become slower because the question is a
      deep-research one; it makes the same size of call either way.
    - `act` is bounded by the query class, from `_QUERY_CLASS_BUDGET_S`,
      because it is the step whose work genuinely scales with how hard the
      question is: a multi-hop query runs more tool calls and traverses
      more graph than a lookup does.

    Raises:
        UnknownStepError: for a step name outside the five loop steps,
            before any budget is returned, so a typo in a caller surfaces
            as a named error rather than a silently wrong timeout.
    """
    if step == "act":
        return _QUERY_CLASS_BUDGET_S[query_class]
    tier = _STEP_TIER.get(step)
    if tier is None:
        raise UnknownStepError(
            f"unknown loop step {step!r}; expected one of "
            f"{sorted([*_STEP_TIER, 'act'])}"
        )
    return _TIER_STEP_BUDGET_S[tier]


def budget_for_query_class(query_class: QueryClass) -> float:
    """Return the per-step timeout budget, in seconds, for `query_class`.

    Raises:
        ValueError: if `query_class` is not one of the five values
            `contracts.events.ThinkPayload.query_class` can emit. Think's
            own Pydantic validation (`extra="forbid"`, a Literal field)
            should make this unreachable in practice; this is a defensive
            guard against a caller passing a plain, unvalidated string.
    """
    try:
        return _QUERY_CLASS_BUDGET_S[query_class]
    except KeyError:
        raise ValueError(
            f"no per-step timeout budget mapped for query_class {query_class!r}; "
            f"expected one of {sorted(_QUERY_CLASS_BUDGET_S)}"
        ) from None


def _with_cache_prefix(messages: list[Message], cache_prefix: str | None) -> list[Message]:
    """Prepend `cache_prefix` as a leading system message, if one is given.

    T-2.0-06 placeholder wiring only (see the module docstring): this is
    the "obvious natural way" to thread a future stable-prefix string into
    the message list without building the prefix-assembly logic itself.
    """
    if not cache_prefix:
        return messages
    return [{"role": "system", "content": cache_prefix}, *messages]


class Harness:
    """In-process module owning tier resolution, cost accounting, timeout
    enforcement, and the coordinator-worker split (Section 3.5). This
    ticket (T-2.0-02) implements only `call_tier` and `track_cost`; see the
    module docstring for the three sibling methods intentionally absent
    from this class.

    One `Harness` instance is constructed per query, holding that query's
    `trace_id` (minted at the Guardrail step, production-standards.md
    observability gate) and exactly one `TierContext` (system-design-
    patterns.md pattern 11; prompt-cache-discipline.md obligation 1: a
    tier's resolved model never changes mid-query).
    """

    def __init__(self, trace_id: str) -> None:
        self.trace_id = trace_id
        self._tier_context = TierContext()
        self._query_cost_usd: dict[str, float] = {}
        self._cost_lock = threading.Lock()

    async def call_tier(
        self,
        tier: Tier,
        messages: list[Message],
        *,
        cache_prefix: str | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Issue one model call for `tier` through LiteLLM/OpenRouter.

        Every model call in the loop goes through here, never a direct
        provider SDK call (Section 3.5). Resolves `tier` to a bare model id
        via this Harness's `TierContext` (raises `UnknownTierError`, a
        `ValueError` subclass, before any network attempt if `tier` is not
        one of "guard", "plan", "synth"), builds the literal
        `openrouter/<model_id>` LiteLLM call target, and issues the call
        via `litellm.acompletion`.

        On success: computes `call_cost_usd` from the returned token usage
        and the model's OpenRouter price, meters it via `track_cost`, and
        returns an `LLMResponse`.

        On failure: classifies the exception transient, recoverable, or
        unexpected (Section 3.5) before deciding whether to retry. Exactly
        one retry fires, and only for a transient failure; a recoverable
        or unexpected failure raises immediately. A retried call is a
        genuinely new attempt against the same target, so if it succeeds
        its own `call_cost_usd` is computed and metered independently of
        the first attempt's outcome; the first attempt, having failed
        before returning a response, contributes no cost (no tokens were
        billed by the provider for a rejected or timed-out request).

        Raises:
            UnknownTierError: for a tier outside {"guard", "plan", "synth"},
                before any call attempt.
            HarnessCallError: for an exhausted-retry transport failure, or
                a model resolved with no known OpenRouter price.
        """
        model_id = self._tier_context.resolve(tier)  # UnknownTierError surfaces here, unwrapped
        final_messages = _with_cache_prefix(messages, cache_prefix)
        target = f"openrouter/{model_id}"

        max_attempts = 2  # one retry, transient failures only
        for attempt in range(1, max_attempts + 1):
            try:
                response: Any = await litellm.acompletion(
                    model=target,
                    messages=final_messages,
                    reasoning=_TIER_REASONING[tier],
                    # Per-call override, defaulting to the tier's own cap.
                    # F-4.12-01: a caller that KNOWS it is going to discard the
                    # reply should not pay for a tier-sized one. The tier cap
                    # stays the default so nothing that does not opt in
                    # changes.
                    max_tokens=(
                        _TIER_MAX_TOKENS[tier] if max_tokens is None else max_tokens
                    ),
                )
            except asyncio.CancelledError:
                # F-2.1-B02, second order. `enforce_timeout` cancels this
                # coroutine on a timeout, so the metering below never runs
                # and the call records 0.00 US dollars. The provider has
                # already billed it: measured, a timed-out call cost 0.005
                # to 0.010 while reporting cost_usd=0.000000. Since the most
                # expensive query class is also the one most likely to time
                # out, all three caps read zero for exactly the queries that
                # spend the most, and spend accumulates invisibly.
                #
                # The real usage is unknowable here, because the response
                # never arrived. So this meters a deliberate OVER-estimate:
                # the tier's full output ceiling at its output price. A cost
                # cap that guesses must guess toward stopping, never toward
                # letting the next call through, and this is the only place
                # that knows a billable call happened at all.
                #
                # Estimation has precedent in this file: Section 19.2
                # already has the pre-flight check estimate a call's likely
                # cost from the tier's token profile before dispatching it.
                _, output_price = _price_per_token(model_id)
                self.track_cost(
                    self.trace_id, tier, _TIER_MAX_TOKENS[tier] * output_price
                )
                raise
            except Exception as exc:
                error_class = _classify_exception(exc)
                if error_class == "transient" and attempt < max_attempts:
                    continue
                # F-3.4-A-07: the internal message carries str(exc), the
                # provider's own error text (e.g. an OpenRouter 402
                # affordability message), not just the exception type name.
                # This never reaches the end user: _STEP_ERROR_END_USER_MESSAGES
                # (graph.py, F-2.0-12) stays the deliberately generic
                # client-facing string regardless of error_class. Without
                # this, an "unexpected"-classed provider error (never
                # auto-retried, unlike "transient") was root-caused only by
                # live manual reproduction, since nothing else surfaced or
                # logged the real cause.
                raise HarnessCallError(
                    f"call_tier failed for tier {tier!r} (model {model_id!r}) "
                    f"after {attempt} attempt(s): {error_class} error "
                    f"({type(exc).__name__}): {exc}",
                    error_class=error_class,
                ) from exc
            else:
                usage = response.usage
                prompt_tokens = int(usage.prompt_tokens)
                completion_tokens = int(usage.completion_tokens)
                input_price, output_price = _price_per_token(model_id)
                call_cost_usd = (
                    prompt_tokens * input_price + completion_tokens * output_price
                )
                self.track_cost(self.trace_id, tier, call_cost_usd)
                return LLMResponse(
                    content=response.choices[0].message.content,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    call_cost_usd=call_cost_usd,
                    model_id=model_id,
                    tier=tier,
                )

        # Unreachable: the loop above always returns (success) or raises
        # (exhausted retries) before falling through.
        raise HarnessCallError(
            "call_tier retry loop exited without returning or raising",
            error_class="unexpected",
        )

    def track_cost(self, trace_id: str, tier: Tier, usd: float) -> None:
        """Accumulate one metered call's cost against `trace_id`'s running total.

        Section 3.5 assigns this method both emitting a `cost` event
        (Section 2.3) and enforcing caps (Section 19); both are T-2.0-03's
        job (`cost_control.py`), not yet built. This ticket implements only
        the counter-accumulation half: `usd` is added to an in-process
        running total keyed by `trace_id`, never assigned over the prior
        value, so two calls in the same query accumulate rather than one
        overwriting the other. T-2.0-03 reads this running total (via
        `get_query_cost_usd`) to build the pre-flight cap check and the
        `CostPayload` event on top of it.

        `tier` is accepted, matching the Section 3.5 signature, but this
        ticket's accumulator is not yet broken down per tier; a per-tier
        breakdown is available to a future ticket if the cap or event
        design needs it.
        """
        with self._cost_lock:
            self._query_cost_usd[trace_id] = self._query_cost_usd.get(trace_id, 0.0) + usd

    def get_query_cost_usd(self, trace_id: str) -> float:
        """Return `trace_id`'s running metered-cost total so far.

        Zero for a `trace_id` that has never been metered, not a KeyError:
        a query that has made no billable calls yet has legitimately spent
        nothing.
        """
        with self._cost_lock:
            return self._query_cost_usd.get(trace_id, 0.0)

    async def enforce_timeout(self, step: str, coro: Awaitable[Any], budget_s: float) -> Any:
        """Abort `coro` if it has not completed within `budget_s` seconds
        (Section 3.5's `enforce_timeout`, Section 19.1's per-step timeout
        cap).

        `asyncio.wait_for` wraps `coro` in a Task (if it is not one
        already) and, on timeout, cancels that Task and awaits its
        cancellation before raising `asyncio.TimeoutError`. That await is
        what keeps this method from leaving an unbounded background task:
        by the time `enforce_timeout` raises, the original coroutine has
        already been cancelled and has finished unwinding, not merely
        "asked" to stop. A test in `test_harness.py` proves this
        end-to-end with a real (short) `asyncio.sleep`, not a mock: a flag
        the coroutine sets only after its sleep completes is asserted to
        never be set once the timeout has fired, even after waiting past
        the sleep's original duration.

        On success, returns `coro`'s real result unchanged. A step that
        completes just under `budget_s` is not falsely aborted, since
        `asyncio.wait_for` only cancels after the full timeout elapses;
        this is covered by a fast-completing-coroutine test using a real,
        short sleep rather than a mocked clock.

        On timeout, raises `HarnessCallError` (never a sentinel, `None`,
        or a swallowed exception), so a genuinely failed step is never
        mistaken for a zero-result success further down the loop:

        - `error_class="transient"`: Section 3.5 calls a timeout
          harness-caused, not model-caused, the same class as a rate limit
          or a dropped connection in `call_tier`, and distinct from
          `call_tier`'s "recoverable" class for a bad request the model
          itself could not have satisfied differently no matter how long
          it ran.
        - `source=f"harness.enforce_timeout:{step}"`: naming the step that
          timed out, so a timeout on "act" is distinguishable from one on
          "think", and from any `call_tier` failure in that same step
          (which keeps `source="harness.call_tier"`). This is also what
          makes a timeout distinguishable from a step that failed for a
          non-timeout reason: a non-timeout failure inside `coro`
          propagates unchanged (its own type and its own `source`, if any),
          since `asyncio.wait_for` re-raises an inner exception as-is and
          only wraps the `TimeoutError` case.

        This ticket's file scope (`harness.py`, `test_harness.py`; see the
        module docstring) does not itself construct or emit an
        `ErrorPayload` (Section 2.3) or drive a partial-synthesis handoff
        to Write: the Guardrail-to-Write loop nodes that will call
        `enforce_timeout` per step are not built yet (T-2.0-05 onward).
        The `scope="step"` half of that future event is implied by this
        method's own per-step framing and by the step name threaded into
        `source` above; the loop node that eventually builds the
        `ErrorPayload` and proceeds to synthesize from partial results
        needs no further classification logic to fill it in, only to
        catch this exception instead of letting it crash the run.

        Raises:
            HarnessCallError: error_class="transient", if `coro` does not
                complete within `budget_s` seconds.
        """
        try:
            return await asyncio.wait_for(coro, timeout=budget_s)
        except TimeoutError as exc:
            raise HarnessCallError(
                f"step {step!r} exceeded its {budget_s}s budget and was "
                "aborted; the loop should proceed to Write and synthesize "
                "from whatever partial tool results already exist for this "
                "step (Section 19.1), not retry this same call_tier or "
                "tool invocation blindly",
                error_class="transient",
                source=f"harness.enforce_timeout:{step}",
            ) from exc
