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
    - `enforce_timeout` -- T-2.0-04's ticket. When T-2.0-04 lands, it
      extends this same class; no stub for it exists in this file, so
      there is nothing for that ticket to remove first.
    - `coordinator_worker_execute` -- T-2.0-05's ticket, a separate module
      (`coordinator_worker.py`). Not present on this class either.

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

import threading
from dataclasses import dataclass
from typing import Any, Literal

import litellm

from system_03_search_agent.harness.tiers import Tier, TierContext

# A LiteLLM chat message: {"role": "system" | "user" | "assistant", "content": str}.
# LiteLLM's own `completion`/`acompletion` accept `list[dict]`; this alias
# names the shape without introducing a new dependency or schema.
Message = dict[str, str]

ErrorClass = Literal["transient", "recoverable", "unexpected"]


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
_FALLBACK_PRICES_USD_PER_TOKEN: dict[str, tuple[float, float]] = {}


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
    except Exception:  # noqa: BLE001 - fall through to the local table below
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
                response: Any = await litellm.acompletion(model=target, messages=final_messages)
            except Exception as exc:  # noqa: BLE001 - classified immediately below
                error_class = _classify_exception(exc)
                if error_class == "transient" and attempt < max_attempts:
                    continue
                raise HarnessCallError(
                    f"call_tier failed for tier {tier!r} (model {model_id!r}) "
                    f"after {attempt} attempt(s): {error_class} error "
                    f"({type(exc).__name__})",
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
