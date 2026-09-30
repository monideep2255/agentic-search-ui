"""The one classifier seam: Jev decides, and the guard tier steps in only
when Jev fails (build phase 8.2, cards 8, 9, 10 and 13; build phase 8.6,
DECISIONS.md 2026-09-25, "Jev decides; the guard tier (DeepSeek) is Jev's
fallback on failure only").

Depends on:
    - system_03_search_agent.harness.harness (Harness, HarnessCallError,
      LLMResponse, Message); `ask_guard_model` sends every guard-tier call
      the guardrail makes, one `call_tier(retry=False)` per request
    - system_03_search_agent.harness.cost_control (check_per_query_cap,
      per_query_cost_cap_usd, QueryCapExceededError)
    - system_03_search_agent.harness.jev_client (call_jev, JevCallError,
      JevResult, MAX_JEV_COST_USD, wait_counting_free_time)
    - system_03_search_agent.harness.tiers (resolve_jev_model)
    - system_03_search_agent.contracts.events (DecisionRecord)

Reads:
    - Environment: CLASSIFIER_PROVIDER ("guard" is the code default; "jev"
      switches this decision seam on), OPENROUTER_API_KEY (Jev's own
      credential, the product's existing OpenRouter key), JEV_MODEL
      (resolved via `tiers.resolve_jev_model`, falling back to
      `typesafe/jev-1.13`).

Writes:
    - Nothing directly. Jev's own `usage.cost` is charged through
      `Harness.track_cost` inside this module, the same accumulator every
      other model call in the loop uses.

WIRED INTO THE LOOP in build phase 8.2's second wave (builder J): every
caller lives in `core/graph.py`, whose "classifier seam, wired" section
holds each decision point's fixed description and the list of points.

What this decides, and what it never decides: `decide()` answers exactly
one closed-option question at a time (`point`, e.g. "guardrail.relevancy",
"think.ask_back", "think.recent_years", "think.asks_features",
"plan.literature"), never free text. "guardrail.injection" is not one of
`decide()`'s points: it is built by `core/graph.py`'s `_injection_record`,
which calls `call_jev` directly and asks the guard classifier beside it on
every Jev-mode question, never through this function (F-8.6-V05).

Who decides, since build phase 8.6. With `CLASSIFIER_PROVIDER=jev`, Jev is
asked alone. The guard tier is asked the same question over the same
bounded `state` only when Jev fails: a timeout at Jev's 3-second total
bound, an HTTP error, a malformed reply, an option outside the offered set,
the cost cap, or anything unexpected. The reason is recorded on the
`DecisionRecord`. Nothing runs beside Jev on the live path any more: the
build phase 8.2 design asked the guard tier every decision concurrently and
waited up to a one-second grace for its pick, only to record it, which
doubled the classifier calls on every question for a table that read "not
ready" in most rows. The comparison of the two models now runs offline,
through `compare_models` at the end of this module, which no live path calls;
its one caller is `testing/Developer/scripts/compare_classifiers.py`.

`ai-security-standards.md`'s prompt-injection defense applies directly
here: `state` is bounded (see `_STATE_MAX_CHARS`) and is the only free
text handed to either model. Neither model is ever asked to act on
retrieved content as an instruction; both are asked one narrow
multiple-choice question over a capped string.
"""

from __future__ import annotations

import asyncio
import contextlib
import email.utils
import logging
import math
import os
import re
import time
import weakref
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final

from system_03_search_agent.contracts.events import DecisionRecord
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness.cost_control import QueryCapExceededError
from system_03_search_agent.harness.harness import (
    Harness,
    HarnessCallError,
    LLMResponse,
    Message,
)
from system_03_search_agent.harness.jev_client import (
    JEV_TOTAL_TIMEOUT_S,
    MAX_JEV_COST_USD,
    JevCallError,
    JevResult,
    call_jev,
    wait_counting_free_time,
)
from system_03_search_agent.harness.tiers import resolve_jev_model

logger = logging.getLogger(__name__)

# Bounded per ai-security-standards.md: only bounded state, never raw
# unbounded content, reaches an external model through this seam.
_STATE_MAX_CHARS = 4000

# The guard tier's own per-step timeout budget (harness.py's
# `_TIER_STEP_BUDGET_S["guard"]`, 15.0s), reused here rather than
# re-imported as a private constant: this decision call is guard-tier
# shaped work (a short classification), the same job `_TIER_STEP_BUDGET_S`
# already budgets for.
_GUARD_BUDGET_S = 15.0

#: How long `decide()` waits for Jev before treating the call as timed out:
#: Jev's own TOTAL bound (`jev_client.JEV_TOTAL_TIMEOUT_S`, 3 s, enforced
#: around the whole request since the fix round, F-8.2-J03) plus a small
#: margin for the cap check and scheduling. A second, outer net only: the
#: client's own bound fires first.
#:
#: Both clocks count only time the server's event loop was free to read
#: Jev's reply (`jev_client.wait_counting_free_time`; R-10 fix round,
#: F-72-J03). Before, a stall of about half a second between this net
#: being armed and Jev's request going out spent the half-second margin, so
#: the net said "timeout" while Jev was still inside its own bound, and a
#: question Jev judged on topic was refused as off topic (FA03).
_JEV_WAIT_S = JEV_TOTAL_TIMEOUT_S + 0.5

#: How long `decide()` waits for the guard tier's pick once Jev has failed
#: and the guard's pick is the one that decides: the guard call's own
#: step budget plus a margin. The guard call enforces its own budget first;
#: this is the outer net, the same shape as `_JEV_WAIT_S`.
_GUARD_FALLBACK_WAIT_S = _GUARD_BUDGET_S + 1.0

#: How `DecisionRecord.fallback_reason` starts when NEITHER model made a
#: usable pick (fix round, F-8.2-A04). In Jev mode it is followed by a colon
#: and Jev's own failure reason, e.g. "no_usable_pick:timeout".
NO_USABLE_PICK: Final[str] = "no_usable_pick"


#: A ceiling on the caller's description of a decision. The text is
#: code-authored and fixed per decision point, never user content, so this
#: is a bound on a programming mistake rather than on an attacker.
_DESCRIPTION_MAX_CHARS = 1000


def _check_description(
    point: str,
    options: Sequence[str],
    instructions: str | None,
    criteria: Mapping[str, str] | None,
) -> None:
    """Reject a description that does not fit the decision it describes.

    A criterion for an option that is not offered, or an offered option
    with no criterion, would tell the two models different things about
    the same choice, so both are programming errors, raised rather than
    sent.
    """
    if instructions is not None and len(instructions) > _DESCRIPTION_MAX_CHARS:
        raise ValueError(f"decide() for {point!r}: instructions exceed {_DESCRIPTION_MAX_CHARS} characters")
    if criteria is None:
        return
    if set(criteria) != set(options):
        raise ValueError(
            f"decide() for {point!r}: criteria must name exactly the offered options "
            f"{list(options)!r}, got {sorted(criteria)!r}"
        )
    for option, text in criteria.items():
        if len(text) > _DESCRIPTION_MAX_CHARS:
            raise ValueError(f"decide() for {point!r}: the criterion for {option!r} is too long")


def _build_guard_messages(
    state: str,
    options: Sequence[str],
    instructions: str | None = None,
    criteria: Mapping[str, str] | None = None,
) -> list[Message]:
    """One narrow classification prompt: no stable prefix (this is
    classification-shaped work, the same reason `_dispatch_tier_call`
    skips the prefix for the guardrail's own attack classifier and
    Think's classification call; see `core/graph.py`'s module docstring).

    The decision's own description, when the caller gives one, goes in the
    SYSTEM message and the person's text alone in the user message, so the
    instruction and the data it judges never share a turn. Without the
    description the guard saw only option names (builder J, F-J-03): its
    reply to "What is GERD?" for `think.ask_back` was unparseable.
    """
    options_line = ", ".join(repr(opt) for opt in options)
    content = (
        "Answer with exactly one of the offered options and nothing else. "
        f"Options: {options_line}"
    )
    if instructions:
        content += f"\n\nThe decision: {instructions}"
    if criteria:
        content += "\n\nWhen to choose each option:\n" + "\n".join(
            f"- {opt!r}: {criteria[opt]}" for opt in options
        )
    return [
        {"role": "system", "content": content},
        {"role": "user", "content": state},
    ]


#: Words that, just before an option in a guard reply, turn a mention of the
#: option into its denial.
_NEGATION_WORDS: Final[frozenset[str]] = frozenset(
    {
        "not", "no", "never", "neither", "nor", "cannot", "can't", "cant",
        "isn't", "isnt", "doesn't", "doesnt", "don't", "dont", "won't", "wont",
    }
)


def _parse_guard_choice(raw: str, options: Sequence[str]) -> str | None:
    """Deterministic, exact-match-or-whole-token parse. Never a fuzzy score
    (production-standards.md's AI answer grounding gate applies the same
    exact-match discipline to this closed-option decision).

    The fallback matches an option only as a WHOLE token, and only when
    exactly one offered option appears. It was a bare substring test, which
    read "off_topic" out of `"is_off_topic": false` (builder J, F-J-06) and,
    for a reply naming two options ("not off_topic, on_topic"), returned
    whichever option happened to be listed first. Two options named, or
    none, is no usable pick, and the caller falls back or fails open.
    """
    text = raw.strip()
    for opt in options:
        if text == opt:
            return opt
    found = {
        opt: match
        for opt in options
        if (match := re.search(rf"(?<![\w-]){re.escape(opt)}(?![\w-])", text)) is not None
    }
    if len(found) != 1:
        return None
    ((opt, match),) = found.items()
    # "This is not off_topic." names one option and means the other (fix
    # round, F-8.2-J08). A negation in the three words before the option
    # makes the reply ambiguous, and an ambiguous reply is no usable pick.
    preceding = re.findall(r"[\w']+", text[: match.start()].lower())[-3:]
    if _NEGATION_WORDS.intersection(preceding):
        return None
    return opt


# ---------------------------------------------------------------------------
# Every guard-tier call the guardrail makes, one request after the other
# (card 84, re-land follow-up R-10 without card 72's hedge).
# ---------------------------------------------------------------------------

#: The most requests a RATE-LIMITED guard-tier call sends (R-10 line 4,
#: F-8.6-FJ04; card 84, the lead's correction of 2026-09-29): once any
#: request of the call meets a 429, the call sends no more than this in all.
#: Every other failure keeps develop's policy, which can send four. A resend
#: without the reasoning setting (F-72-J08) is part of the same request.
GUARD_RATE_LIMITED_MAX_REQUESTS: Final[int] = 2

#: The least time a request must keep for itself after a wait before it
#: (develop's `_CLASSIFIER_MIN_SECOND_ATTEMPT_S`, re-land follow-up R-05,
#: unchanged): phase 8.6's golden run put the guard verdict's median at
#: 1.53 s, and three seconds covers most replies. A backoff that would
#: leave less is shortened; a provider's own `Retry-After` that would leave
#: less means no further request, since asking before the provider said to
#: is the hammering R-05 removed.
GUARD_MIN_SECOND_REQUEST_S: Final[float] = 3.0

#: How long a second ATTEMPT waits after the first ended in an error that
#: is not a rate limit (develop's `_CLASSIFIER_RETRY_BACKOFF_S`, re-land
#: follow-up R-05, F-8.6-RJ01, RJ08, RA02, unchanged): two seconds outlasts
#: an error of about a second. An attempt cut by its own budget gets no wait.
GUARD_RETRY_BACKOFF_S: Final[float] = 2.0


def _attempt_wait_s(exc: HarnessCallError, remaining_s: float) -> float:
    """Develop's `_classifier_retry_wait_s` for a failure that is not a rate
    limit (a rate-limited call never reaches a second attempt here)."""
    if exc.source.startswith("harness.enforce_timeout"):
        return 0.0
    return max(0.0, min(GUARD_RETRY_BACKOFF_S, remaining_s - GUARD_MIN_SECOND_REQUEST_S))


def rate_limit_behind(exc: BaseException) -> BaseException | None:
    """The provider's HTTP 429 behind a guard call's failure, or None.

    `call_tier` raises `HarnessCallError` from the provider's own exception,
    so the 429 is on the cause chain; `litellm.RateLimitError` carries
    `status_code` 429. Read by status, not by class, so this module needs no
    import of the provider library.
    """
    cause = exc.__cause__
    for _ in range(5):
        if cause is None:
            return None
        if getattr(cause, "status_code", None) == 429:
            return cause
        cause = cause.__cause__
    return None


def _header_value(headers: Any, name: str) -> str | None:
    """One header's value from an `httpx.Headers` or a plain mapping, matched
    without regard to case; None when absent or unreadable."""
    if headers is None:
        return None
    try:
        items = headers.items()
    except AttributeError:
        return None
    try:
        for key, value in items:
            if str(key).lower() == name:
                return str(value)
    except Exception:  # noqa: BLE001 - an odd header object states no wait
        return None
    return None


def provider_retry_after_s(error: BaseException) -> float | None:
    """The wait, in seconds, a rate-limiting provider asked for in its
    `Retry-After` header: a number of seconds or an HTTP date. None when the
    error carries no such header or one that is not a usable wait.

    litellm keeps the provider's headers in one of three places depending
    on how the error was raised; each is read in turn.
    """
    sources = (
        getattr(error, "litellm_response_headers", None),
        getattr(error, "headers", None),
        getattr(getattr(error, "response", None), "headers", None),
    )
    for headers in sources:
        raw = _header_value(headers, "retry-after")
        if raw is None:
            continue
        try:
            seconds = float(raw)
        except ValueError:
            try:
                when = email.utils.parsedate_to_datetime(raw)
            except (TypeError, ValueError):
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=UTC)
            seconds = (when - datetime.now(UTC)).total_seconds()
        if math.isfinite(seconds):
            return max(0.0, seconds)
    return None


class GuardReplyUnusable(ValueError):
    """Raised by an `ask_guard_model` caller's `parse` when a reply that came
    back cannot be used. The call then goes on to its next attempt, when it
    has one, as develop's classifier did."""


#: The longest upstream host name written to the log (bounded again here,
#: though `harness._upstream_provider` already cut it).
_LOG_UPSTREAM_MAX_CHARS = 64


@dataclass
class GuardCall:
    """What one guard-tier call through `ask_guard_model` came to.

    - `parsed`: the caller's `parse` of the usable reply; None when there
      was none. `answered` says whether there was one, since a parse may
      itself return None (a guard pick that named no option).
    - `error`: the failure that ended the call without a usable reply,
      None otherwise. `unusable` is True when a reply came back but could
      not be used and no further request was sent.
    - `rate_limit_wait_s`: when a rate limit ended the call, the seconds
      still to wait before the provider said to ask again, read from
      whichever request carried a `Retry-After`, the later one winning; 0.0
      when the stated wait has already passed; None when no request
      stated one or the call did not end on a rate limit.
    - `requests`: how many requests were sent: at most four, develop's two
      attempts of two, and at most `GUARD_RATE_LIMITED_MAX_REQUESTS` once
      one of them was rate-limited (`rate_limited`).
    """

    parsed: Any = None
    answered: bool = False
    error: HarnessCallError | None = None
    unusable: bool = False
    rate_limit_wait_s: float | None = None
    requests: int = 0
    rate_limited: bool = False
    lines: list[str] = field(default_factory=list)


def _clean_upstream(response: LLMResponse | None) -> str:
    raw = getattr(response, "upstream_provider", None) if response is not None else None
    if not isinstance(raw, str):
        return "not named"
    cleaned = "".join(ch for ch in raw if ch.isprintable()).strip()[:_LOG_UPSTREAM_MAX_CHARS]
    return cleaned or "not named"


def _failure_words(exc: HarnessCallError) -> str:
    """A failed request, in words that carry no provider text: a timeout,
    or the error's class and the provider exception's type name."""
    if exc.source.startswith("harness.enforce_timeout"):
        return "cut at its budget"
    if rate_limit_behind(exc) is not None:
        return "rate limited"
    cause = exc.__cause__
    kind = type(cause).__name__ if cause is not None else "no cause"
    return f"failed, {exc.error_class} ({kind[:40]})"


class _StopCall(Exception):
    """Ends a rate-limited call: no further request may be sent."""


async def ask_guard_model(
    harness: Harness,
    trace_id: str,
    messages: list[Message],
    *,
    label: str,
    step: str,
    deadline: float,
    parse: Callable[[str], Any],
    attempts: int = 1,
    first_share: float = 1.0,
    max_tokens: int | None = None,
) -> GuardCall:
    """One guard-tier call: develop's own policy, request for request,
    except when the provider rate-limits it, and never two requests at once
    (card 84: R-10 without card 72's hedge, as the lead corrected it).

    Develop's policy, kept exactly for every failure that is not a rate
    limit, with its timing:

    - Up to `attempts` attempts (the classifier's two, re-land R-01; one
      for a guard pick). The first may run to `first_share` of what is left
      before `deadline` (two thirds for the classifier), a second to the
      rest.
    - Inside an attempt, a transient error is resent at once, once, within
      the attempt's own budget: what `call_tier`'s own retry did.
    - An attempt that ended in a transient error is followed, when another
      is allowed, after `GUARD_RETRY_BACKOFF_S` (shortened to keep
      `GUARD_MIN_SECOND_REQUEST_S`), or at once when the attempt was cut by
      its budget (R-05). An unusable reply goes to the next attempt at once.
    - The per-query cap's pre-flight runs before each attempt.

    A rate limit (R-10 line 4, F-8.6-FJ04, FA05): once any request meets a
    429, the call sends at most `GUARD_RATE_LIMITED_MAX_REQUESTS` in all. A
    `Retry-After` it states is waited out before the next request, or ends
    the call at once when it would leave that request less than
    `GUARD_MIN_SECOND_REQUEST_S`. The one request left then keeps all the
    rest of the budget.

    So every provider behaviour develop answered without a 429 is answered
    here the same, at the same moment; `test_guard_request_dominance.py`
    sweeps both over timings and verdicts. Each request is one
    `call_tier(..., retry=False)` inside `enforce_timeout(step, ...)`. One
    log line per call (`_log_guard_call`) names each request's outcome,
    time and upstream host, and the trace id; never the key, a token, the
    question or the prompt.
    """
    call = GuardCall()
    started = time.monotonic()
    stated_until: float | None = None
    outcome = "no request sent: the budget was already spent"

    async def _request(budget_s: float) -> LLMResponse:
        """One request, noted on `call`; its failure is the caller's."""
        nonlocal outcome, stated_until
        number = call.requests = call.requests + 1
        sent = time.monotonic()
        outcome = f"stopped while request {number} was running"
        if budget_s <= 0:
            # The attempt's budget was already spent: what `enforce_timeout`
            # does at once, without sending anything.
            call.requests -= 1
            spent = HarnessCallError(
                "the attempt's budget was spent before its resend could go out",
                error_class="transient",
                source=f"harness.enforce_timeout:{step}",
            )
            call.error, call.unusable = spent, False
            raise spent
        try:
            response = await harness.enforce_timeout(
                step,
                harness.call_tier("guard", messages, cache_prefix=None, max_tokens=max_tokens, retry=False),
                budget_s,
            )
        except HarnessCallError as exc:
            call.error, call.unusable = exc, False
            call.lines.append(f"request {number}: {_failure_words(exc)} after {time.monotonic() - sent:.2f}s")
            outcome = _failure_words(exc)
            rate_limit = rate_limit_behind(exc)
            if rate_limit is not None:
                call.rate_limited = True
                stated = provider_retry_after_s(rate_limit)
                if stated is not None:
                    stated_until = time.monotonic() + stated
            raise
        call.lines.append(
            f"request {number}: answered after {time.monotonic() - sent:.2f}s, upstream {_clean_upstream(response)}"
        )
        return response

    async def _after_rate_limit() -> LLMResponse:
        """The one request a rate-limited call may still send, after any
        stated wait, with all that is left; `_StopCall` when none may go."""
        nonlocal outcome
        if call.requests >= GUARD_RATE_LIMITED_MAX_REQUESTS:
            raise _StopCall
        wait_s = max(0.0, (stated_until or 0.0) - time.monotonic())
        if wait_s > 0:
            if wait_s + GUARD_MIN_SECOND_REQUEST_S > deadline - time.monotonic():
                outcome = "rate limited, and the stated wait does not fit the budget"
                raise _StopCall
            await asyncio.sleep(wait_s)
        try:
            return await _request(deadline - time.monotonic())
        except HarnessCallError:
            raise _StopCall from None

    try:
        for attempt in range(1, attempts + 1):
            remaining_s = deadline - time.monotonic()
            if remaining_s <= 0:
                if call.requests:
                    outcome = f"{outcome}; the budget ran out before another attempt"
                break
            cost_control.check_per_query_cap(harness, trace_id, "guard")
            attempt_deadline = time.monotonic() + (remaining_s * first_share if attempt == 1 else remaining_s)
            try:
                response = await _request(attempt_deadline - time.monotonic())
            except HarnessCallError as exc:
                response = None
                if call.rate_limited:
                    response = await _after_rate_limit()
                elif exc.error_class == "transient" and not exc.source.startswith("harness.enforce_timeout"):
                    try:
                        response = await _request(attempt_deadline - time.monotonic())
                    except HarnessCallError:
                        if call.rate_limited:
                            response = await _after_rate_limit()
            if response is None:
                failure = call.error
                if failure is None or attempt == attempts or failure.error_class != "transient":
                    break
                wait_s = _attempt_wait_s(failure, deadline - time.monotonic())
                if wait_s > 0:
                    await asyncio.sleep(wait_s)
                continue
            try:
                call.parsed = parse(response.content)
            except GuardReplyUnusable:
                call.error, call.unusable = None, True
                call.lines[-1] = call.lines[-1].replace(": answered after", ": answered, unusable, after", 1)
                outcome = "no usable reply"
                if call.rate_limited:
                    break
                continue
            call.answered, call.error, call.unusable = True, None, False
            outcome = "answered"
            break
    except _StopCall:
        pass
    except asyncio.CancelledError:
        outcome = f"stopped by its caller while request {call.requests} was running"
        raise
    except QueryCapExceededError:
        outcome = "refused by the per-query cost cap"
        raise
    finally:
        ended_on_rate_limit = call.error is not None and rate_limit_behind(call.error) is not None
        if ended_on_rate_limit and stated_until is not None:
            call.rate_limit_wait_s = max(0.0, stated_until - time.monotonic())
        _log_guard_call(label, trace_id, outcome, time.monotonic() - started, call)
    return call


def _log_guard_call(label: str, trace_id: str, outcome: str, elapsed_s: float, call: GuardCall) -> None:
    """One line per guard-tier call (card 72's D, card 84): its outcome, its
    time in all, and each request's outcome, time and upstream host.

    At WARNING on purpose: the service configures no logging of its own, and
    develop's only configuration sets the root level to WARN, so an INFO
    line would never reach develop's log. Every word is code-authored or a
    bounded, printable host name.
    """
    logger.warning(
        "guard call %s (trace %s): %s after %.2fs in all, %d request%s; %s",
        label,
        trace_id,
        outcome,
        elapsed_s,
        call.requests,
        "" if call.requests == 1 else "s",
        "; ".join(call.lines) or "no request",
    )


async def _run_guard_pick(
    harness: Harness,
    trace_id: str,
    state: str,
    options: Sequence[str],
    instructions: str | None = None,
    criteria: Mapping[str, str] | None = None,
    *,
    point: str = "decision",
) -> str | None:
    """The guard tier's own pick for the same closed-option question.

    Checks the per-query cost cap first, exactly like
    `core/graph.py`'s `_dispatch_tier_call` does for every other guard-tier
    call in the loop. Returns None (never raises) when the cap is
    exceeded, the call times out, or the call fails: `decide()` records a
    None guard pick as no pick, and when Jev made none either, fills
    `chosen` with the caller's fail-open default. In Jev mode this runs
    only after Jev has failed.

    Sent through `ask_guard_model` (card 84) as one attempt inside the same
    `_GUARD_BUDGET_S` develop gave it, with develop's immediate resend
    after a transient error. The only change from develop is a rate limit:
    two requests at most, and a stated `Retry-After` waited out before the
    second, or ending the pick when it does not fit (R-10 line 4,
    F-72-J05). An unusable reply is no pick, as before.
    """
    messages = _build_guard_messages(state, options, instructions, criteria)
    try:
        call = await ask_guard_model(
            harness,
            trace_id,
            messages,
            label=f"guard pick for {point[:80]}",
            step="guardrail",
            deadline=time.monotonic() + _GUARD_BUDGET_S,
            parse=lambda content: _parse_guard_choice(content, options),
            attempts=1,
        )
    except QueryCapExceededError:
        return None
    return call.parsed if call.answered else None


#: The most each Jev call already let through by the pre-flight can still be
#: charged, per `Harness` and trace, until its charge lands (card 84,
#: F-72-V02). Keyed weakly so a finished question's harness takes its entry
#: with it.
_JEV_RESERVED: weakref.WeakKeyDictionary[Harness, dict[str, float]] = weakref.WeakKeyDictionary()


def _reserved_usd(harness: Harness, trace_id: str) -> float:
    return _JEV_RESERVED.get(harness, {}).get(trace_id, 0.0)


def check_jev_per_query_cap(harness: Harness, trace_id: str) -> None:
    """The per-query cap's pre-flight for one Jev call, checked the way
    every other model call is checked: refused when the running cost plus
    what the call may be charged would pass the cap (fix round, F-72-J09).

    Jev has no tier of its own, so the guard tier's estimate is checked as
    before, and then the most one Jev call can be charged,
    `MAX_JEV_COST_USD`, since a usable reply is charged the cost it states
    up to that ceiling, on top of what every other Jev call already let
    through and not yet charged may still add (`jev_charge_reserved`, card
    84, F-72-V02). Before, a Jev call was let through on the guard tier's
    $0.003 estimate and an unusable reply then charged one cent, so a
    question at $0.0965 of a $0.10 cap ended at $0.1065; and two Jev calls
    checked at once each saw room for one.

    Raises:
        QueryCapExceededError: the call would take the question past its cap.
    """
    cost_control.check_per_query_cap(harness, trace_id, "guard")
    cap = cost_control.per_query_cost_cap_usd()
    current = harness.get_query_cost_usd(trace_id)
    reserved = _reserved_usd(harness, trace_id)
    if current + reserved + MAX_JEV_COST_USD > cap:
        raise QueryCapExceededError(
            f"asking Jev once more for query {trace_id!r} could take its running cost "
            "past the per-query cap; stop issuing further model calls for this query "
            "and move to Write with whatever tool results already exist",
            query_cost_usd=current,
            query_cap_usd=cap,
            estimated_call_cost_usd=MAX_JEV_COST_USD + reserved,
        )


@contextlib.contextmanager
def jev_charge_reserved(harness: Harness, trace_id: str) -> Iterator[None]:
    """Check the cap for one Jev call and hold its most possible charge,
    `MAX_JEV_COST_USD`, until the call's own charge has landed (card 84,
    F-72-V02, J09).

    Every Jev charge site wraps its call and its charge in this: `decide`'s
    pick, the guardrail's injection pick and the sentence check. The check
    and the hold happen together, with no await between them, so two Jev
    calls started at once cannot both see room the other will use: the
    guardrail starts its injection pick and its relevancy decision at the
    same moment, and Think starts several decisions together.

    Raises:
        QueryCapExceededError: the call would take the question past its cap;
            nothing is held.
    """
    check_jev_per_query_cap(harness, trace_id)
    held = _JEV_RESERVED.setdefault(harness, {})
    held[trace_id] = held.get(trace_id, 0.0) + MAX_JEV_COST_USD
    try:
        yield
    finally:
        left = held.get(trace_id, 0.0) - MAX_JEV_COST_USD
        if left > 1e-12:
            held[trace_id] = left
        else:
            held.pop(trace_id, None)


async def _run_jev_pick(
    harness: Harness,
    trace_id: str,
    point: str,
    state: str,
    options: Sequence[str],
    model: str,
    api_key: str,
    instructions: str | None = None,
    criteria: Mapping[str, str] | None = None,
) -> JevResult:
    """Jev's pick, cap-checked first like every other model call.

    Charges every reply that came back, never $0 (fix round, F-72-J02,
    A03, J09, the product owner's decision of 2026-09-29): a usable reply
    the cost it states when that is a sensible amount, and any other reply
    the small `JEV_FLOOR_COST_USD`, which `jev_client` has already fixed on
    `JevResult.cost_usd` or `JevCallError.billed_cost_usd` and logged by
    amount. The cap is checked first with the most one Jev call can be
    charged, held until the charge lands (`jev_charge_reserved`), so no Jev
    charge takes the question past its cap, two started at once included. Raises JevCallError (from `jev_client.call_jev`)
    or `cost_control.QueryCapExceededError` on any failure; `_jev_attempt`
    catches both.
    """
    with jev_charge_reserved(harness, trace_id):
        try:
            result = await call_jev(
                model=model,
                question_key=point,
                state=state,
                options=options,
                api_key=api_key,
                instructions=instructions,
                criteria=criteria,
            )
        except JevCallError as exc:
            # A reply that came back but could not be used (any malformed
            # body, an option outside the set, a cost that is not a sensible
            # amount, a status other than 200) was still billed: it is
            # charged the floor it carries, never zero, and the cost cap
            # then applies to the guard fallback as to any call (fix round,
            # F-8.6-J10; R-10 and its fix round; card 84).
            if exc.billed_cost_usd:
                harness.track_cost(trace_id, "guard", exc.billed_cost_usd)  # type: ignore[arg-type]
            raise
        # Charged under the "guard" tier bucket for the same reason the cap
        # check above reuses it: `Harness.track_cost`'s accumulator is not
        # broken down per tier (its own docstring says so), it only sums
        # onto `trace_id`'s running total, and Jev has no tier slot of its
        # own.
        harness.track_cost(trace_id, "guard", result.cost_usd)  # type: ignore[arg-type]
        return result


def jev_decides() -> bool:
    """Whether Jev is the classifier: `CLASSIFIER_PROVIDER=jev`, read on
    every call so a deployment's setting is the only switch.

    Anything else, unset included, means the guard tier decides alone, the
    code default that keeps production untouched until the product owner
    flips the switch. `decide()` and the reworded-sentence check
    (`synthesis/sentence_check.py`) both read it here, so the two can never
    disagree about who decides.
    """
    return os.environ.get("CLASSIFIER_PROVIDER", "guard").strip().lower() == "jev"


async def _jev_attempt(
    harness: Harness,
    trace_id: str,
    point: str,
    state: str,
    options: Sequence[str],
    model: str,
    api_key: str,
    instructions: str | None,
    criteria: Mapping[str, str] | None,
) -> JevResult | str:
    """Jev's pick, or the reason it made none.

    The reason is what `DecisionRecord.fallback_reason` records:
    `JevCallError.reason` ("timeout", "http_error", "malformed_reply",
    "invalid_option"), "cost_cap", "timeout" again when Jev's own bound did
    not fire and `_JEV_WAIT_S` did, or "unexpected_error". Never raises,
    except for cancellation: a caller that cancels the decision stops Jev's
    call with it.

    `_JEV_WAIT_S` counts only time the event loop was free, like Jev's own
    bound (`wait_counting_free_time`; fix round, F-72-J03): a stall of the
    server anywhere inside this wait, before Jev's request or while its
    reply is read, never turns a pick Jev delivers inside its own bound
    into a "timeout".
    """
    try:
        return await wait_counting_free_time(
            _run_jev_pick(
                harness, trace_id, point, state, options, model, api_key, instructions, criteria
            ),
            _JEV_WAIT_S,
        )
    except JevCallError as exc:
        return exc.reason
    except QueryCapExceededError:
        return "cost_cap"
    except TimeoutError:
        return "timeout"
    except Exception:  # noqa: BLE001 - a broken Jev call falls back, it never breaks the decision
        return "unexpected_error"


async def _guard_fallback_pick(
    harness: Harness,
    trace_id: str,
    state: str,
    options: Sequence[str],
    instructions: str | None,
    criteria: Mapping[str, str] | None,
    *,
    point: str = "decision",
) -> str | None:
    """The guard tier's pick, or None. `decide()` asks it only once Jev has
    failed; `compare_models` asks it beside Jev, offline.

    `_run_guard_pick` already returns None on the cost cap, a timeout of its
    own step budget and a failed call; the outer wait and the broad catch
    are nets for anything that slips past those, so a failed fallback reads
    as "no usable pick", never as an exception out of `decide()`.
    """
    try:
        return await asyncio.wait_for(
            _run_guard_pick(harness, trace_id, state, options, instructions, criteria, point=point),
            timeout=_GUARD_FALLBACK_WAIT_S,
        )
    except TimeoutError:
        return None
    except Exception:  # noqa: BLE001 - see the docstring
        return None


async def decide(
    harness: Harness,
    trace_id: str,
    point: str,
    state: str,
    options: Sequence[str],
    *,
    instructions: str | None = None,
    criteria: Mapping[str, str] | None = None,
    default: str | None = None,
    jev_failed: asyncio.Event | None = None,
) -> DecisionRecord:
    """Decide one closed-option question, `point`, over the bounded `state`.

    `instructions` (one line saying what is being decided) and `criteria`
    (one line per option saying when to choose it) are the caller's fixed,
    code-authored description of the decision. Whichever model answers
    receives the same description: the guard tier in its system message,
    Jev in the endpoint's own `instructions` and `criteria` fields. `state`
    stays the person's bounded text only. Every wired decision point passes
    both; without them the models see only option names, which measured
    wrong on three of the five decision shapes (builder J, F-J-03).

    With `CLASSIFIER_PROVIDER` unset or anything other than `"jev"` (the
    code default, `"guard"`): Jev is never called. The guard tier decides
    alone and its pick is used. This is what keeps production untouched
    until the product owner flips the switch.

    With `CLASSIFIER_PROVIDER=jev` (build phase 8.6):

    - Jev is asked alone. When it answers within its 3-second TOTAL bound
      with one of the offered `options`, its choice is used at once:
      `decided_by == "jev"`, `guard_choice` None, `agreed` None,
      `fallback_reason` None. The guard tier is not called, so the
      decision takes Jev's time and nothing more.
    - When Jev fails, and only then, the guard tier is asked the same
      question within its own step budget. Its pick is used and
      `fallback_reason` names Jev's failure (`JevCallError.reason`,
      `"cost_cap"`, `"unexpected_error"`).
    - When neither model produced a valid answer (either provider),
      `jev_choice` and `guard_choice` are both None, `fallback_reason`
      starts with `"no_usable_pick"` (in Jev mode followed by a colon and
      Jev's own failure, e.g. `"no_usable_pick:timeout"`), and `chosen` is
      `default`, the caller's fail-open option, so the record states what
      the loop actually did rather than a pick no model made (F-8.2-A04,
      F-8.2-J13). `decided_by` still reads `"guard"` there, because the
      contract's field allows only "jev" or "guard"; the None picks and the
      reason are what say that nobody decided. Without a `default`,
      `chosen` is `options[0]`.

    `jev_failed` (re-land follow-up R-10, F-8.6-FA03): when the caller
    passes an event, `decide()` sets it the moment Jev's OWN pick can no
    longer come back from this decision: in Jev mode as soon as Jev has
    failed, before the guard tier is asked; with the guard provider at
    once, since Jev is never asked. A caller whose outcome only Jev's own
    pick could change waits on this event rather than on a clock, so a
    stalled event loop that delays Jev's request never cuts off a pick Jev
    still delivers. It is never set when Jev made a pick: the record is
    then already returned.

    Raises:
        ValueError: if `options` is empty (there is nothing to decide
            between), the description does not fit the options (see
            `_check_description`), or `default` is not an offered option.
    """
    if not options:
        raise ValueError(f"decide() for {point!r} was given an empty options list")
    _check_description(point, options, instructions, criteria)
    if default is not None and default not in options:
        raise ValueError(
            f"decide() for {point!r}: default {default!r} is not one of the offered options"
        )
    fallback_default = default if default is not None else options[0]

    bounded_state = state[:_STATE_MAX_CHARS]

    if not jev_decides():
        if jev_failed is not None:
            jev_failed.set()
        guard_choice = await _run_guard_pick(
            harness, trace_id, bounded_state, options, instructions, criteria, point=point
        )
        return DecisionRecord(
            name=point,
            options=list(options),
            chosen=guard_choice if guard_choice is not None else fallback_default,
            decided_by="guard",
            guard_choice=guard_choice,
            fallback_reason=None if guard_choice is not None else NO_USABLE_PICK,
        )

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    model = resolve_jev_model()

    jev = await _jev_attempt(
        harness, trace_id, point, bounded_state, options, model, api_key, instructions, criteria
    )
    if isinstance(jev, JevResult):
        return _jev_mode_record(point, options, jev, None, fallback_default)

    # Jev has failed and says so, before the guard tier is asked (R-10).
    if jev_failed is not None:
        jev_failed.set()
    logger.warning(
        "Jev made no pick for decision %s (trace %s, %s); asking the guard tier",
        point,
        trace_id,
        jev,
    )
    guard_choice = await _guard_fallback_pick(
        harness, trace_id, bounded_state, options, instructions, criteria, point=point
    )
    return _jev_mode_record(point, options, jev, guard_choice, fallback_default)


def _jev_mode_record(
    point: str,
    options: Sequence[str],
    jev: JevResult | str,
    guard_choice: str | None,
    fallback_default: str,
) -> DecisionRecord:
    """The record `decide()` returns in Jev mode, built in one place so the
    offline comparison hands the loop exactly the record the live seam would.

    - Jev made a pick: it decides, and no guard pick is recorded, since the
      live seam never asks the guard then.
    - Jev failed (`jev` is its reason) and the guard made a pick: the guard
      decides and the reason is recorded.
    - Neither made a pick (F-8.2-A04, F-8.2-J13): the record names no pick
      nobody made. Both picks stay None, the reason starts with
      "no_usable_pick" and keeps Jev's own failure after the colon, and
      `chosen` is the caller's fail-open default, which is what the loop
      actually does.
    """
    if isinstance(jev, JevResult):
        return DecisionRecord(
            name=point,
            options=list(options),
            chosen=jev.choice,
            decided_by="jev",
            jev_choice=jev.choice,
            jev_confidence=jev.confidence,
            jev_latency_ms=jev.latency_ms,
        )
    if guard_choice is not None:
        return DecisionRecord(
            name=point,
            options=list(options),
            chosen=guard_choice,
            decided_by="guard",
            guard_choice=guard_choice,
            fallback_reason=jev,
        )
    return DecisionRecord(
        name=point,
        options=list(options),
        chosen=fallback_default,
        decided_by="guard",
        fallback_reason=f"{NO_USABLE_PICK}:{jev}",
    )


# ---------------------------------------------------------------------------
# The offline comparison (build phase 8.6, T-8.6-03). No live path calls
# anything below; `tests/system_03_search_agent/harness/test_decide.py`
# asserts that nothing else under `src/` names `compare_models`.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelComparison:
    """Jev's and the guard tier's answers to one decision, asked side by side.

    `jev` is Jev's validated result, or the reason it made no pick, exactly
    as `decide()` sees it. Built only by `compare_models`.
    """

    point: str
    options: tuple[str, ...]
    jev: JevResult | str
    guard_choice: str | None
    guard_latency_ms: int

    @property
    def jev_choice(self) -> str | None:
        return self.jev.choice if isinstance(self.jev, JevResult) else None

    @property
    def jev_confidence(self) -> float | None:
        return self.jev.confidence if isinstance(self.jev, JevResult) else None

    @property
    def jev_probabilities(self) -> dict[str, float] | None:
        return dict(self.jev.probabilities) if isinstance(self.jev, JevResult) else None

    @property
    def jev_latency_ms(self) -> int | None:
        return self.jev.latency_ms if isinstance(self.jev, JevResult) else None

    @property
    def jev_failure(self) -> str | None:
        return None if isinstance(self.jev, JevResult) else self.jev

    @property
    def agreed(self) -> bool | None:
        """True or False only when both models made a pick."""
        if self.jev_choice is None or self.guard_choice is None:
            return None
        return self.jev_choice == self.guard_choice

    def live_record(self, default: str | None = None) -> DecisionRecord:
        """The record Jev-mode `decide()` returns for these picks, so a loop
        run under the comparison takes the path it takes on develop.

        Raises:
            ValueError: if `default` is not one of the offered options.
        """
        if default is not None and default not in self.options:
            raise ValueError(
                f"live_record() for {self.point!r}: default {default!r} is not an offered option"
            )
        fallback_default = default if default is not None else self.options[0]
        guard_choice = None if isinstance(self.jev, JevResult) else self.guard_choice
        return _jev_mode_record(self.point, self.options, self.jev, guard_choice, fallback_default)


async def compare_models(
    harness: Harness,
    trace_id: str,
    point: str,
    state: str,
    options: Sequence[str],
    *,
    instructions: str | None = None,
    criteria: Mapping[str, str] | None = None,
) -> ModelComparison:
    """OFFLINE ONLY: ask Jev and the guard tier the same decision at once.

    Its one caller is `testing/Developer/scripts/compare_classifiers.py`.
    Both models get exactly what `decide()` gives them: the same bounded
    state, the same description, the same cost-cap checks, Jev's 3-second
    total bound and the guard's own budget. Both are asked whatever
    `CLASSIFIER_PROVIDER` says. A model's failure is recorded, never
    raised: Jev's as its reason, the guard's as no pick.

    Raises:
        ValueError: as `decide()` does, for empty options or a description
            that does not fit them.
    """
    if not options:
        raise ValueError(f"compare_models() for {point!r} was given an empty options list")
    _check_description(point, options, instructions, criteria)
    bounded_state = state[:_STATE_MAX_CHARS]

    async def _timed_guard_pick() -> tuple[str | None, int]:
        started = time.monotonic()
        choice = await _guard_fallback_pick(
            harness, trace_id, bounded_state, options, instructions, criteria
        )
        return choice, int((time.monotonic() - started) * 1000)

    jev, (guard_choice, guard_latency_ms) = await asyncio.gather(
        _jev_attempt(
            harness,
            trace_id,
            point,
            bounded_state,
            options,
            resolve_jev_model(),
            os.environ.get("OPENROUTER_API_KEY", ""),
            instructions,
            criteria,
        ),
        _timed_guard_pick(),
    )
    return ModelComparison(
        point=point,
        options=tuple(options),
        jev=jev,
        guard_choice=guard_choice,
        guard_latency_ms=guard_latency_ms,
    )
