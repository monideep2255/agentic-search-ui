"""The one classifier seam: Jev decides, and the guard tier steps in only
when Jev fails (build phase 8.2, cards 8, 9, 10 and 13; build phase 8.6,
DECISIONS.md 2026-09-25, "Jev decides; the guard tier (DeepSeek) is Jev's
fallback on failure only").

Depends on:
    - system_03_search_agent.harness.harness (Harness, HarnessCallError,
      Message)
    - system_03_search_agent.harness.cost_control (check_per_query_cap,
      per_query_cost_cap_usd, QueryCapExceededError)
    - system_03_search_agent.harness.jev_client (call_jev, JevCallError,
      JevResult, MAX_JEV_COST_USD, wait_counting_free_time)

Depended on by:
    - system_03_search_agent.core.graph: `decide` at every decision point,
      and `ask_guard_model` for the guardrail's own classifier requests, so
      every guard-tier request the guardrail makes takes one path (card 72;
      R-10's fix round).
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
import email.utils
import logging
import math
import os
import re
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final, Generic, TypeVar

from system_03_search_agent.contracts.events import DecisionRecord
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness.cost_control import QueryCapExceededError
from system_03_search_agent.harness.harness import Harness, HarnessCallError, Message
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
# Guard-model requests: at most two, the second sent when the old policy's
# would have been, a provider's Retry-After honoured (card 72; R-10 and its
# fix round). Every guard-tier request the guardrail makes goes through
# `ask_guard_model`: its own classifier (`core/graph.py`,
# `_classify_within_budget`) and every guard pick asked through this seam
# (`_run_guard_pick`), the relevancy decision's included.
# ---------------------------------------------------------------------------

#: The most requests one guard-model question sends: the first and one more.
#: Never more in flight or in total (R-10, F-8.6-FJ04: a persistent 429 used
#: to cost four). Each request is one `call_tier(..., retry=False)` call.
GUARD_MAX_REQUESTS: Final[int] = 2

#: Where the second request goes beside a first that has not ended: this
#: share of what was left of the budget when the first was sent. It is the
#: moment develop's policy before card 72 (re-land R-01) cut its first
#: attempt and sent a fresh one, and it is kept on purpose (fix round,
#: F-72-A04). With two requests at most, a hedge sent earlier lands inside
#: a slow spell that develop's later request outlasts: a spell of 4 to 10 s
#: in which every request sent hangs lost the search on the 4-second hedge
#: and was answered on develop at 10.6 s. No two-request policy that sends
#: its second before this point can answer every spell develop answers.
#: What card 72 still gains here: the first request is never cut, so a slow
#: first reply at 10 to 15 s now decides instead of being thrown away.
GUARD_HEDGE_SHARE: Final[float] = 2 / 3

#: The backoff after an error, as develop's R-05 used it (F-8.6-RJ01, RJ08,
#: RA02); see `second_request_at` for how it now enters the second
#: request's time.
GUARD_RETRY_BACKOFF_S: Final[float] = 2.0

#: The least time a second request must keep after a provider's own
#: `Retry-After` wait. A stated wait that would leave less means no second
#: request: asking before the provider said to is the hammering R-05
#: removed. Phase 8.6's golden run put the guard verdict's median at 1.53 s.
GUARD_MIN_SECOND_ATTEMPT_S: Final[float] = 3.0

#: No hedge goes out with less than this left of the budget (fix round,
#: F-72-A05). A request that cannot answer in the time left only adds load
#: to a provider already slow, and is charged as a cancelled call.
GUARD_MIN_HEDGE_S: Final[float] = 2.0


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


def rate_limit_behind(exc: BaseException) -> BaseException | None:
    """The provider's HTTP 429 behind a guard request's failure, or None.

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


def _develop_last_send(sent_at: float, failed_at: float, hedge_at: float, deadline: float) -> float:
    """When develop's policy before card 72 (R-01 and R-05) would have sent
    its LAST request, had each of its requests failed the way this first one
    did, `failed_at - sent_at` after it went out.

    That policy sent up to four: `call_tier`'s immediate resend inside the
    first attempt; the first attempt cut at `hedge_at`, or ended by the
    resend's failure; a backoff of `GUARD_RETRY_BACKOFF_S`, shortened to
    keep `GUARD_MIN_SECOND_ATTEMPT_S`; a fresh attempt; and its own
    immediate resend.
    """
    took = failed_at - sent_at
    resend_failed_at = failed_at + took
    if resend_failed_at >= hedge_at:
        # The first attempt was cut at the hedge point with its resend still
        # running, and a fresh attempt went out there at once.
        return hedge_at + took if hedge_at + took < deadline else hedge_at
    wait_s = max(0.0, min(GUARD_RETRY_BACKOFF_S, deadline - resend_failed_at - GUARD_MIN_SECOND_ATTEMPT_S))
    fresh_at = resend_failed_at + wait_s
    return fresh_at + took if fresh_at + took < deadline else fresh_at


def second_request_at(
    error: HarnessCallError | None,
    *,
    sent_at: float,
    failed_at: float,
    hedge_at: float,
    deadline: float,
) -> float | None:
    """When the second request goes out after the first ended at
    `failed_at` without a verdict and before the hedge point, on the
    monotonic clock; None when no second request is made (fix round,
    F-72-A04; before it R-05 and R-10).

    - `error` None, an unusable reply: at once, as develop did.
    - An error that is not transient (a refused key, a bad request): none.
    - A rate limit whose provider named a wait (`Retry-After`): that wait,
      at least `GUARD_RETRY_BACKOFF_S`, when it still leaves
      `GUARD_MIN_SECOND_ATTEMPT_S`; otherwise none, and the question ends at
      once saying when to come back (R-10, F-8.6-FA02).
    - Any other transient error, a rate limit that named no wait included:
      when develop's policy would have sent its last request
      (`_develop_last_send`), so an error spell develop's four requests
      outlast, the second outlasts too; but never so late that it keeps
      less time than develop gave its own second chance, which is
      `failed_at` plus what the hedge point leaves (`deadline - hedge_at`),
      and never after the hedge point itself (F-8.6-FJ11: a slow failure is
      followed at the hedge point, never a backoff past it). An error
      lasting about a second (RJ08's blip) is outlasted, and a first request
      that failed at 9.8 s gets its second at 10 s. At a hedge share of two
      thirds the first two terms already keep the time at or before the
      hedge point; the third states the promise so a different share
      cannot break it.
    """
    if error is None:
        return failed_at
    if error.error_class != "transient":
        return None
    rate_limit = rate_limit_behind(error)
    stated = provider_retry_after_s(rate_limit) if rate_limit is not None else None
    if stated is not None:
        wait_s = max(stated, GUARD_RETRY_BACKOFF_S)
        return failed_at + wait_s if failed_at + wait_s + GUARD_MIN_SECOND_ATTEMPT_S <= deadline else None
    at = min(
        _develop_last_send(sent_at, failed_at, hedge_at, deadline),
        failed_at + (deadline - hedge_at),
        hedge_at,
    )
    return max(failed_at, at)


class UnusableGuardReply(Exception):
    """Raised by the `parse` given to `ask_guard_model` when a reply came
    back from the guard model but cannot be used. The next request, if
    there is one, goes at once."""


_V = TypeVar("_V")


@dataclass
class GuardAsked(Generic[_V]):
    """What `ask_guard_model` got: the verdict, or why there is none.

    - `decided` and `value`: a usable reply's parsed value, the strictest of
      every usable reply in hand when the question was decided.
    - `cap_refused`: a request was refused by the per-query cost cap before
      it was sent; `cap_refused_first` when it was the first.
    - `rate_limited` and `stated_waits`: the provider rate-limited a request,
      with every `Retry-After` any request carried and when it was read.
    - `last_failure`, `last_was_unusable`: the error, or the unusable reply,
      that the question ends on when no request gave a verdict.
    """

    decided: bool = False
    value: _V | None = None
    requests: int = 0
    cap_refused: bool = False
    cap_refused_first: bool = False
    rate_limited: bool = False
    stated_waits: list[tuple[float, float]] = field(default_factory=list)
    last_failure: HarnessCallError | None = None
    last_was_unusable: bool = False


@dataclass
class _GuardRequest:
    """One guard-model request in flight."""

    number: int
    task: asyncio.Future[Any]
    sent_at: float


async def ask_guard_model(
    *,
    trace_id: str,
    send: Callable[[float], Awaitable[Any]],
    parse: Callable[[Any], _V],
    strictness: Callable[[_V], int],
    deadline: float,
    what: str,
) -> GuardAsked[_V]:
    """Ask the guard model one question with at most `GUARD_MAX_REQUESTS`
    requests, all inside `deadline` (card 72; R-10 and its fix round).

    `send(budget_s)` makes one request, one `call_tier(..., retry=False)`
    call with its own per-query cap check, and returns the reply. `parse`
    turns a reply into a value or raises `UnusableGuardReply`. `strictness`
    ranks values: when more than one usable reply is in hand at the moment
    of deciding, the higher wins, so a refusal beats an admission whatever
    order or tick the replies came in (fix round, F-72-J01, J10). `what`
    names the question in the log, code-authored words only.

    - The first request is sent at once and may run to `deadline`.
    - Not ended at the hedge point (`GUARD_HEDGE_SHARE` of the budget left
      when it was sent), a second goes beside it, the first NOT cancelled,
      unless less than `GUARD_MIN_HEDGE_S` would be left (F-72-A05).
    - Ended earlier without a verdict, the second goes at
      `second_request_at` (an unusable reply at once; a `Retry-After`
      honoured; other errors when develop's last request would have gone).
    - Every request that has ended is read, not only the ones a wait
      returned, and when a usable reply decides, any other request that has
      already ended is read too before the verdict is chosen (F-72-J01). The
      requests still running are then cancelled, which `call_tier` charges
      as it charges any cancelled call, and awaited so that charge lands
      first. A request never sent is never charged.
    - One log line per request, with its time, its outcome and the upstream
      host OpenRouter named (card 72, D's logging), at WARNING because
      develop's log keeps WARNING and above only.

    Raises whatever `send` raises other than `HarnessCallError` and
    `QueryCapExceededError`, which are recorded on the result.
    """
    asked: GuardAsked[_V] = GuardAsked()
    started = time.monotonic()
    if deadline - started <= 0:
        return asked
    hedge_at = started + (deadline - started) * GUARD_HEDGE_SHARE
    hedge_allowed = deadline - hedge_at >= GUARD_MIN_HEDGE_S
    requests: list[_GuardRequest] = []
    in_flight: dict[asyncio.Future[Any], _GuardRequest] = {}
    usable: list[tuple[_GuardRequest, _V, str | None]] = []
    unusable_seen = False
    retry_at: float | None = None
    stopped_because = "the question ended"

    def _log(request: _GuardRequest, outcome: str, upstream: str | None = None) -> None:
        logger.warning(
            "%s request %d of %d (trace %s): %s after %.2fs, upstream %s",
            what,
            request.number,
            GUARD_MAX_REQUESTS,
            trace_id,
            outcome,
            time.monotonic() - request.sent_at,
            upstream or "not named",
        )

    def _send() -> None:
        budget_s = max(0.0, deadline - time.monotonic())
        task = asyncio.ensure_future(send(budget_s))
        request = _GuardRequest(number=len(requests) + 1, task=task, sent_at=time.monotonic())
        requests.append(request)
        in_flight[task] = request
        asked.requests = len(requests)

    def _read(request: _GuardRequest) -> None:
        """Record one ended request: a usable value, an unusable reply, or
        a failure, and when the first ends alone, when the second goes."""
        nonlocal unusable_seen, retry_at
        task = request.task
        if task.cancelled():
            _log(request, "cancelled")
            return
        exc = task.exception()
        if isinstance(exc, QueryCapExceededError):
            _log(request, "not sent, the per-query cost cap")
            asked.cap_refused = True
            asked.cap_refused_first = asked.cap_refused_first or request.number == 1
            return
        alone = len(requests) == 1
        if isinstance(exc, HarnessCallError):
            rate_limit = rate_limit_behind(exc)
            stated = provider_retry_after_s(rate_limit) if rate_limit is not None else None
            if rate_limit is not None:
                asked.rate_limited = True
            if stated is not None:
                asked.stated_waits.append((stated, time.monotonic()))
            asked.last_failure = exc
            # A cut at the deadline of a request still running after another
            # reply came back unusable does not override that reply.
            if not (unusable_seen and exc.source.startswith("harness.enforce_timeout")):
                asked.last_was_unusable = False
            _log(
                request,
                f"failed ({exc.source}, {exc.error_class}"
                + (", rate-limited" if rate_limit is not None else "")
                + (f", Retry-After {stated:.1f}s" if stated is not None else "")
                + ")",
            )
            if alone:
                retry_at = second_request_at(
                    exc,
                    sent_at=request.sent_at,
                    failed_at=time.monotonic(),
                    hedge_at=hedge_at,
                    deadline=deadline,
                )
                if retry_at is None and stated is not None:
                    logger.warning(
                        "%s rate-limited (trace %s) and the provider asked for a wait "
                        "the budget cannot fit; not asking again",
                        what,
                        trace_id,
                    )
            return
        if exc is not None:
            raise exc
        response = task.result()
        upstream = getattr(response, "upstream_provider", None)
        try:
            value = parse(response)
        except UnusableGuardReply:
            unusable_seen = True
            asked.last_was_unusable = True
            _log(request, "answered, unusable", upstream)
            if alone:
                retry_at = time.monotonic()
            return
        usable.append((request, value, upstream))

    _send()
    try:
        while not usable:
            if in_flight:
                first = requests[0]
                hedge_due = len(requests) == 1 and hedge_allowed and first.task in in_flight
                wait_until = hedge_at if hedge_due else deadline
                await asyncio.wait(
                    set(in_flight),
                    timeout=max(0.0, wait_until - time.monotonic()),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                # Every request that has ended, not only those the wait
                # returned: two replies can end in the same pass (F-72-J01).
                ended = [request for task, request in in_flight.items() if task.done()]
                for request in sorted(ended, key=lambda r: r.number):
                    del in_flight[request.task]
                    _read(request)
                if ended:
                    continue
                now = time.monotonic()
                if now >= deadline:
                    if not unusable_seen:
                        asked.last_failure = HarnessCallError(
                            f"{what} got no usable reply within its budget; retry the query",
                            error_class="transient",
                            source="harness.enforce_timeout:guardrail",
                        )
                    stopped_because = "cut at the budget"
                    break
                if hedge_due and now >= hedge_at:
                    logger.warning(
                        "%s slow (trace %s): no answer after %.1fs; sending an identical "
                        "second request without cancelling the first",
                        what,
                        trace_id,
                        now - first.sent_at,
                    )
                    _send()
                continue

            # Nothing in flight and no verdict: the second request, or the end.
            if len(requests) >= GUARD_MAX_REQUESTS or asked.cap_refused or retry_at is None:
                break
            wait_s = retry_at - time.monotonic()
            if wait_s > 0:
                logger.warning(
                    "%s failed (trace %s); asking once more within the budget after %.1fs",
                    what,
                    trace_id,
                    wait_s,
                )
                await asyncio.sleep(wait_s)
            if time.monotonic() >= deadline:
                break
            _send()

        if usable:
            # Decided. Any other request that ended before the verdict is
            # acted on is read too; the rest are stopped first, so what
            # they cost is charged before the question's cost is read.
            stopped_because = "cancelled, the other request answered first"
            leftover = dict(in_flight)
            in_flight.clear()
            for task in leftover:
                task.cancel()
            if leftover:
                await asyncio.gather(*leftover, return_exceptions=True)
            for request in sorted(leftover.values(), key=lambda r: r.number):
                task = request.task
                if task.cancelled() or task.exception() is not None:
                    _log(request, stopped_because)
                    continue
                _read(request)
            chosen = max(usable, key=lambda item: strictness(item[1]))
            for request, value, upstream in usable:
                if request is chosen[0]:
                    _log(request, "answered", upstream)
                elif strictness(value) < strictness(chosen[1]):
                    _log(request, "answered, a stricter reply decided", upstream)
                else:
                    _log(request, "answered, the same verdict", upstream)
            asked.decided = True
            asked.value = chosen[1]
            return asked
    finally:
        # A request nobody will read is stopped, so it spends nothing more;
        # `call_tier`'s cancellation arm charges it (F-2.1-B02). Awaited, so
        # the charge is on the question before its cost event is built.
        leftover = dict(in_flight)
        in_flight.clear()
        for task in leftover:
            task.cancel()
        if leftover:
            await asyncio.gather(*leftover, return_exceptions=True)
        for request in leftover.values():
            _log(request, stopped_because)
    return asked


def _pick_strictness(default: str | None) -> Callable[[str | None], int]:
    """A guard pick's rank for `ask_guard_model`: a reply naming no single
    option lowest, the caller's fail-open default next, any other pick
    highest. For `guardrail.relevancy` that is: off topic beats on topic,
    the refusal over the admission (fix round, F-72-J01)."""

    def _rank(choice: str | None) -> int:
        if choice is None:
            return 0
        return 1 if choice == default else 2

    return _rank


async def _run_guard_pick(
    harness: Harness,
    trace_id: str,
    state: str,
    options: Sequence[str],
    instructions: str | None = None,
    criteria: Mapping[str, str] | None = None,
    *,
    point: str = "decision",
    default: str | None = None,
    deadline: float | None = None,
) -> str | None:
    """The guard tier's own pick for the same closed-option question,
    asked through `ask_guard_model`, the guardrail classifier's own path
    (fix round, F-72-A02, J05): at most two requests, a hedge at the hedge
    point, a `Retry-After` honoured, one log line per request.

    Each request checks the per-query cost cap first, exactly like
    `core/graph.py`'s `_dispatch_tier_call` does for every other guard-tier
    call in the loop. `deadline` is the caller's own, the guardrail's for
    `guardrail.relevancy`; without one, `_GUARD_BUDGET_S` from now. Returns
    None (never raises for a cap, a timeout or a failed call): `decide()`
    records a None guard pick as no pick, and when Jev made none either,
    fills `chosen` with the caller's fail-open default. A reply that names
    no single option is final, no pick, as before: it came back, so no
    second request is sent for it. In Jev mode this runs only after Jev
    has failed.
    """
    messages = _build_guard_messages(state, options, instructions, criteria)
    if deadline is None:
        deadline = time.monotonic() + _GUARD_BUDGET_S

    async def _send(budget_s: float) -> Any:
        cost_control.check_per_query_cap(harness, trace_id, "guard")
        return await harness.enforce_timeout(
            "guardrail", harness.call_tier("guard", messages, retry=False), budget_s
        )

    asked = await ask_guard_model(
        trace_id=trace_id,
        send=_send,
        parse=lambda response: _parse_guard_choice(response.content, options),
        strictness=_pick_strictness(default),
        deadline=deadline,
        what=f"guard pick for {point}",
    )
    return asked.value if asked.decided else None


def check_jev_per_query_cap(harness: Harness, trace_id: str) -> None:
    """The per-query cap's pre-flight for one Jev call, checked the way
    every other model call is checked: refused when the running cost plus
    what the call may be charged would pass the cap (fix round, F-72-J09).

    Jev has no tier of its own, so the guard tier's estimate is checked as
    before, and then the most one Jev call can be charged,
    `MAX_JEV_COST_USD`, since a usable reply is charged the cost it states
    up to that ceiling. Before, a Jev call was let through on the guard
    tier's $0.003 estimate and an unusable reply then charged one cent, so
    a question at $0.0965 of a $0.10 cap ended at $0.1065.

    Raises:
        QueryCapExceededError: the call would take the question past its cap.
    """
    cost_control.check_per_query_cap(harness, trace_id, "guard")
    cap = cost_control.per_query_cost_cap_usd()
    current = harness.get_query_cost_usd(trace_id)
    if current + MAX_JEV_COST_USD > cap:
        raise QueryCapExceededError(
            f"asking Jev once more for query {trace_id!r} could take its running cost "
            "past the per-query cap; stop issuing further model calls for this query "
            "and move to Write with whatever tool results already exist",
            query_cost_usd=current,
            query_cap_usd=cap,
            estimated_call_cost_usd=MAX_JEV_COST_USD,
        )


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
    charged (`check_jev_per_query_cap`), so no Jev charge takes the
    question past its cap. Raises JevCallError (from `jev_client.call_jev`)
    or `cost_control.QueryCapExceededError` on any failure; `_jev_attempt`
    catches both.
    """
    check_jev_per_query_cap(harness, trace_id)
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
        # A reply that came back but could not be used (any malformed body, an
        # option outside the set, a cost that is not a sensible amount) was
        # still billed: it is charged the floor it carries, never zero, and
        # the cost cap then applies to the guard fallback as to any call
        # (fix round, F-8.6-J10; R-10 and its fix round).
        if exc.billed_cost_usd:
            harness.track_cost(trace_id, "guard", exc.billed_cost_usd)  # type: ignore[arg-type]
        raise
    # Charged under the "guard" tier bucket for the same reason the cap
    # check above reuses it: `Harness.track_cost`'s accumulator is not
    # broken down per tier (its own docstring says so), it only sums onto
    # `trace_id`'s running total, and Jev has no tier slot of its own.
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
    default: str | None = None,
    deadline: float | None = None,
) -> str | None:
    """The guard tier's pick, or None. `decide()` asks it only once Jev has
    failed; `compare_models` asks it beside Jev, offline.

    `_run_guard_pick` already returns None on the cost cap, a timeout of its
    own budget and a failed call; the outer wait and the broad catch are
    nets for anything that slips past those, so a failed fallback reads as
    "no usable pick", never as an exception out of `decide()`. With a
    `deadline`, the net is that deadline plus the same one-second margin.
    """
    net_s = (
        _GUARD_FALLBACK_WAIT_S
        if deadline is None
        else max(0.0, deadline - time.monotonic()) + (_GUARD_FALLBACK_WAIT_S - _GUARD_BUDGET_S)
    )
    try:
        return await asyncio.wait_for(
            _run_guard_pick(
                harness,
                trace_id,
                state,
                options,
                instructions,
                criteria,
                point=point,
                default=default,
                deadline=deadline,
            ),
            timeout=net_s,
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
    deadline: float | None = None,
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

    `deadline` (fix round, F-72-A02, J05): the caller's own deadline on the
    monotonic clock, the guardrail's for `guardrail.relevancy`. The guard
    tier's pick is asked through `ask_guard_model` to that deadline, with a
    hedge at its hedge point; without one, to `_GUARD_BUDGET_S` from when
    the guard tier is asked, as before.

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
            harness,
            trace_id,
            bounded_state,
            options,
            instructions,
            criteria,
            point=point,
            default=fallback_default,
            deadline=deadline,
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
        harness,
        trace_id,
        bounded_state,
        options,
        instructions,
        criteria,
        point=point,
        default=fallback_default,
        deadline=deadline,
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
