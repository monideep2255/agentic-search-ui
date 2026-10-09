"""The one HTTP call to Jev, the classifier-seam model, over OpenRouter's
alpha decisions endpoint (build phase 8.2, DECISIONS.md 2026-09-25, cards
8, 9, 10 and 13).

Depends on:
    - httpx (already a repository dependency via litellm's own transports),
      called directly here rather than through `litellm.acompletion`,
      because the decisions endpoint is not a chat-completions call and
      carries its own request and response shape.

Reads:
    - Nothing from the environment directly. The caller (`harness.decide`)
      resolves `JEV_MODEL` (via `harness.tiers.resolve_jev_model`) and
      reads `OPENROUTER_API_KEY`, then passes both in.

Writes:
    - Nothing. What each reply is charged is fixed here, by `jev_charge_usd`
      (the product owner's rule of 2026-09-29), and handed to the caller to
      charge through `Harness.track_cost`: on `JevResult.cost_usd` for a
      usable reply, on `JevCallError.billed_cost_usd` for every other reply
      that came back, an error status included. This module never touches
      a `Harness` instance. It writes one warning whenever a reply is not
      charged the cost it states, naming the amount.

THE ENDPOINT'S SHAPE IS NOT PUBLICLY DOCUMENTED. Everything below was
pinned live on 2026-09-25 against the real endpoint, `POST
https://openrouter.ai/api/alpha/decisions`, using the product's existing
`OPENROUTER_API_KEY` from the main repository's `.env`. Four requests
total, none of them logged or committed with the key value, total cost
$0.0000728 (see `testing/Developer/reports/2026-09-25_phase_8.2/
builder_D.md` for the exact request and response bodies each probe sent
and received). The shape below was reverse-engineered from a sequence of
400 validation errors, each one naming the next missing or mistyped
field, not read from documentation, because none exists yet.

Confirmed request shape for `call_jev`, one question per call (`decide()`
calls it once per decision point; `call_jev_batch` below sends several):

    POST https://openrouter.ai/api/alpha/decisions
    Authorization: Bearer <OPENROUTER_API_KEY>
    Content-Type: application/json

    {
      "model": "<bare model id, e.g. \"typesafe/jev-1.13\">",
      "state": "<bounded text the classifier reads>",
      "questions": {
        "<question_key>": {
          "type": "choice",
          "options": ["<opt1>", "<opt2>", ...],
          "instructions": "<one line telling the model how to answer>",
          "criteria": {"<opt1>": "<one line>", "<opt2>": "<one line>", ...}
        }
      }
    }

`criteria` is REQUIRED by the endpoint's own validation (confirmed by a
400 naming it missing) even though nothing in this ticket's interface
hands `decide()` per-option descriptions. This module synthesizes a
generic one-liner per option ("Choose '<opt>' when it is the best answer
for this decision.") rather than leaving the field out, and a live probe
confirmed generic criteria text is accepted and still returns a sensible,
confident answer (see the report).

Confirmed response shape on success (200):

    {
      "model": "<resolved model id, may carry a date suffix>",
      "answers": {
        "<question_key>": {
          "type": "choice",
          "choice": "<one of the offered options>",
          "probabilities": {"<opt>": <float 0..1>, ...},
          "confidence": <float 0..1>
        }
      },
      "usage": {"input_tokens": <int>, "output_tokens": <int>, "cost": <float>},
      "id": "<string>",
      "provider": "TypeSafe"
    }

`answers` is a record keyed the same way as the request's `questions`;
`call_jev` sends exactly one question and reads `answers[question_key]`
back directly.

SEVERAL QUESTIONS IN ONE CALL, `call_jev_batch` (build phase 8.6,
T-8.6-02), pinned live on 2026-09-26 (report:
`testing/Developer/reports/2026-09-26_phase_8.6/builder_K.md`, findings
K-02 to K-04). The endpoint takes any number of questions under
`questions`, each with its own options, instructions and criteria, over
one shared `state`, and answers each under its own key: thirty two-option
questions came back in 343 to 611 ms for $0.00033. The endpoint has no
`bool` question type (a `"type": "bool"` question is refused with HTTP 400
naming `noul`, `choice` and `score`); a yes-or-no question is a `choice`
between two options.

No retries inside this module (ai-security-standards, tool-call-budgets):
the caller's fallback to the guard tier's own pick IS the retry, per this
ticket's brief. A 3-second TOTAL timeout on the whole call (see
`_TIMEOUT_S`, counted by `wait_counting_free_time`) and a host-pinned,
literal URL (never built from caller input) are both non-negotiable per
`tool-call-budgets.md` and `production-standards.md`'s multi-agent
pipeline gate.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections.abc import Awaitable, Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Any, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

_R = TypeVar("_R")

JEV_DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"

#: The whole call's bound, connect to last byte of the body, in seconds.
#: Enforced by `wait_counting_free_time` around `_post` in `_send` (it was
#: `asyncio.wait_for` until step 3b of the guardrail design), because the
#: same float handed to `httpx.AsyncClient(timeout=...)` sets four SEPARATE
#: per-phase limits (connect, read, write, pool), and httpx's read limit is
#: the gap between two received chunks, not the response. Measured by the
#: phase 8.2 judge (F-8.2-J03): a server that sent the headers at once and
#: the body in 2-second pieces held one decision for 14 seconds, and Jev's
#: pick was still used. Counted in time the event loop was free, up to
#: `JEV_STALL_ALLOWANCE_S` of pause.
_TIMEOUT_S = 3.0

#: Public name for the bound above, read by `harness.decide` to size how
#: long it waits for Jev before treating the call as timed out.
JEV_TOTAL_TIMEOUT_S = _TIMEOUT_S

JevFailureReason = str  # "timeout" | "http_error" | "malformed_reply" | "invalid_option"

#: The most one Jev reply is ever charged, in US dollars, and the most one
#: decision may report costing and still be used. Measured live at
#: $0.0000148 to $0.0000197 per call (builder D), so this is about 500 times
#: the real price. Jev's cost is the one model cost in the loop the loop does
#: not compute itself: it is whatever the undocumented endpoint says, and it
#: is charged straight into the per-query, per-user and system-wide caps.
#:
#: A reply stating more than this is not used: it is malformed, so the
#: guard's pick decides or, for the sentence check, nothing is approved. It
#: is charged this ceiling, never the stated figure (F-8.6-V01: a reply once
#: reported 12.5 for a call that actually cost $0.0000125, and charging it
#: would have paused every person's questions for the rest of the day), and
#: never less than it: the more a reply says it cost, the more is counted,
#: up to here (F-84-A06).
MAX_JEV_COST_USD = 0.01

#: The least a Jev reply that came back is ever charged, in US dollars, and
#: what it is charged when it states no sensible cost: about five times
#: Jev's measured price, so every cap still sees the call, and a hundredth
#: of `MAX_JEV_COST_USD` (the product owner's rule of 2026-09-29, step 3a of
#: the guardrail design). A stated cost under it, Jev's real price among
#: them, is charged this floor (fix round, J-GR-04).
#:
#: A reply that reached the provider is never charged $0 (F-72-J02: a
#: usable reply stating $0 was charged $0, invisible to every cap; F-72-V03:
#: an error status was charged $0). Not the ceiling either: charging a cent
#: for every reply that states no cost made a drift in the endpoint's shape
#: cost about $0.07 a question, enough to stop every search at the $25
#: daily cap after a few hundred questions (F-72-A03).
JEV_FLOOR_COST_USD = 0.0001

#: At most one probability per offered option; `DecisionRecord.options`
#: allows 12.
_MAX_PROBABILITIES = 12


class JevResult(BaseModel):
    """One decisions call's parsed, schema-validated result.

    `extra="forbid"` and a `max_length` on every string field, per
    `production-standards.md`'s multi-agent pipeline gate: this is data
    read back from an external HTTPS call, and it is treated with the
    same discipline as any other untrusted response before the caller
    acts on it. `cost_usd` is bounded above and `probabilities` in size
    for the same reason (F-8.2-J15). As `call_jev` returns it, `cost_usd`
    is what the caller charges (`jev_charge_usd`): the stated cost when it
    is at least the `JEV_FLOOR_COST_USD` floor, and the floor for a stated
    cost under it, $0 included (fix round, J-GR-04).
    """

    model_config = ConfigDict(extra="forbid")

    resolved_model: Annotated[str, Field(max_length=200)]
    choice: Annotated[str, Field(max_length=200)]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    probabilities: Annotated[
        dict[Annotated[str, Field(max_length=200)], Annotated[float, Field(ge=0.0, le=1.0)]],
        Field(max_length=_MAX_PROBABILITIES),
    ]
    input_tokens: Annotated[int, Field(ge=0)]
    output_tokens: Annotated[int, Field(ge=0)]
    cost_usd: Annotated[float, Field(ge=0.0, le=MAX_JEV_COST_USD)]
    latency_ms: Annotated[int, Field(ge=0)]


class JevCallError(RuntimeError):
    """A classified Jev call failure, with an actionable message.

    `reason` is one of "timeout", "http_error", "malformed_reply", or
    "invalid_option" (production-standards.md's retry-safety gate: an
    error must say what to do next, not just what failed). `decide()`
    catches this and falls back to the guard tier's own pick, recording
    `reason` on the `DecisionRecord.fallback_reason` field; no retry
    happens inside this module.

    `billed_cost_usd` is what the question is charged for this failed call,
    in US dollars, fixed by `jev_charge_usd` (the product owner's rule of
    2026-09-29): a reply that came back but could not be used is charged
    as any reply is, the cost it states when that is at least the
    `JEV_FLOOR_COST_USD` floor and at most `MAX_JEV_COST_USD`, the ceiling
    when it states more, and the floor when it states less, $0, no cost or
    no amount
    (F-84-J04: usable or not makes no difference). A reply with an error
    status (a 500, 429 or 402) reached the provider, so it is charged the
    floor (F-72-V03). 0.0 only when no reply came back at all: a timeout or
    a transport failure.

    `after_a_pause` is True for a timeout whose wait ran out on its real-time
    cap, not on Jev's own bound (`PausedTimeoutError`): the server's own
    pauses took the time, so nobody knows what Jev would have said. A
    caller for whom a missing Jev pick would remove a refusal reads that as
    "unknown", never as "no refusal" (fix round, A-GR-11).
    """

    def __init__(
        self,
        message: str,
        *,
        reason: str,
        billed_cost_usd: float = 0.0,
        after_a_pause: bool = False,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.billed_cost_usd = billed_cost_usd
        self.after_a_pause = after_a_pause


def _stated_cost_usd(payload: object) -> float | None:
    """The cost a 200 reply states, in US dollars, or None when it states no
    amount.

    A number zero or more is an amount, a numeric string included, as
    `float()` reads it. A positive figure too large for a float, or positive
    infinity, states more than any call costs and reads as infinity, so it
    is charged the ceiling, never less (F-84-A06). No `usage.cost`, a
    boolean, a figure that is not a number, a negative one or `NaN` states
    no amount, and is charged the floor. What a reply is charged is decided
    by `jev_charge_usd` from this figure alone, whether or not the rest of
    the reply can be used (F-84-J04).
    """
    try:
        raw = payload["usage"]["cost"]  # type: ignore[index]
    except Exception:  # noqa: BLE001 - any body shape that names no cost states no amount
        return None
    if isinstance(raw, bool):
        return None
    try:
        cost = float(raw)
    except OverflowError:
        return math.inf if isinstance(raw, int) and raw > 0 else None
    except Exception:  # noqa: BLE001 - not a number at all
        return None
    if math.isnan(cost) or cost < 0:
        return None
    return cost


def jev_charge_usd(stated_usd: float | None) -> float:
    """What a Jev reply that came back is charged, in US dollars, from the
    cost it states (the product owner's rule of 2026-09-29, step 3a of the
    guardrail design):

    - at least `JEV_FLOOR_COST_USD` and at most `MAX_JEV_COST_USD`: the
      stated cost;
    - above `MAX_JEV_COST_USD`: the ceiling, never the floor (F-84-A06);
    - below the floor, $0, no stated cost, or no amount (None, `NaN`):
      `JEV_FLOOR_COST_USD`.

    A reply that came back is never charged less than the floor (fix round,
    J-GR-04, A-GR-03): the owner's rule charges a stated figure "above $0",
    and a figure such as 1e-300 is above $0 in name only, a charge every cap
    reads as nothing, the blindness F-72-J02 ended for a stated $0. So a
    stated cost under the floor, Jev's measured $0.0000148 to $0.0000197
    among them, is charged the floor: about five times Jev's real price,
    $0.0001 a reply.

    The same for a usable reply and an unusable one (F-84-J04). A timeout,
    where no reply came back, is charged nothing and never reaches here.
    """
    if stated_usd is None or not stated_usd >= JEV_FLOOR_COST_USD:
        return JEV_FLOOR_COST_USD
    if stated_usd > MAX_JEV_COST_USD:
        return MAX_JEV_COST_USD
    return stated_usd


def _unusable_reply(
    subject: str,
    detail: str,
    next_step: str,
    *,
    charged_usd: float,
    reason: str = "malformed_reply",
) -> JevCallError:
    """The error for a reply that came back from the provider but cannot be
    used, charged `charged_usd` (`jev_charge_usd` of what it states, or the
    floor when the body could not be read at all), and the one log line that
    says so by amount.

    `detail` is code-authored text plus, at most, an exception's type name,
    a stated figure or Jev's own bounded choice: never the key, never the
    state.
    """
    logger.warning(
        "Jev's reply for %s could not be used: %s; it is charged $%.6f",
        subject,
        detail,
        charged_usd,
    )
    return JevCallError(
        f"Jev's reply for {subject} could not be used: {detail}; it is charged "
        f"${charged_usd:.6f}; {next_step}",
        reason=reason,
        billed_cost_usd=charged_usd,
    )


def _charged_for_usable(subject: str, stated_usd: float) -> float:
    """A usable reply's charge, `jev_charge_usd` of its stated cost, with a
    warning when a stated $0 is charged the floor (F-72-J02). A stated cost
    above $0 but under the floor, Jev's usual price, is raised to the floor
    on every call, so that is logged at debug, not as a warning."""
    charged = jev_charge_usd(stated_usd)
    if charged != stated_usd:
        log = logger.warning if not stated_usd > 0.0 else logger.debug
        log(
            "Jev's reply for %s stated a cost of $%.6f; it is charged $%.6f",
            subject,
            stated_usd,
            charged,
        )
    return charged


#: How long one look at the clock waits in `wait_counting_free_time`.
_LOOK_S = 0.05

#: A look that comes back later than asked by more than this was a stall of
#: the server's own event loop, and none of its time is counted (fix round,
#: J-GR-01: counting the time asked plus this slack spent up to 0.1 s of
#: Jev's bound on every pause). A look back within it is counted in full,
#: so the small delays of a merely busy loop still count.
_STALL_SLACK_S = 0.05

#: The most real time a stalled server may add to one of Jev's bounds, so a
#: server that keeps stalling still ends the wait (step 3b of the guardrail
#: design). What the code does, pinned by tests (fix round, J-GR-02, J-GR-08):
#: Jev's clock ends at its bound plus this much real time from the moment
#: the wait began, whatever the pauses. A long pause is not refused as such:
#: a 4.7 s pause with a fast reply is still read, since 4.7 s plus the reply
#: fits the 5 s; a reply that comes after the 5 s is not. The look a pause
#: interrupts is not counted either, so the allowance covers a pause of up
#: to this less one `_LOOK_S`. After a pause, a verdict can come later than
#: develop's by up to the pause's length plus that look, at most this
#: allowance.
JEV_STALL_ALLOWANCE_S = 2.0

#: Time left below this is none: a wait of a few billionths of a second
#: can come back without the clock having moved, and would then never end.
_NONE_LEFT_S = 1e-6

#: Looks a wait may take beyond the ones its real-time cap allows, so a
#: clock that stands still or runs backwards still ends it (fix round,
#: J-GR-03, A-GR-09): each look waits on the event loop's own timer.
_SPARE_LOOKS = 10

#: The most turns of the event loop a wait gives a reply that arrived during
#: a pause before the real-time cap discards it (fix round, A-GR-07,
#: A-GR-11), within `_LOOK_S` of loop time: a reply that has arrived wins
#: over the clock, and a busy loop costs at most one of its turns.
_GRACE_TURNS = 20


class PausedTimeoutError(TimeoutError):
    """A `wait_counting_free_time` that ran out on its real-time cap, or on
    its look limit, with its free budget unspent: the server's own pauses
    took the time, so whether the call would have answered inside its own
    bound is not known (fix round, A-GR-11). A caller for whom a missing
    pick would remove a refusal treats this as unknown, never as "no"."""


def _is_a_budget(budget_s: object) -> bool:
    """A finite number of seconds above zero."""
    return (
        isinstance(budget_s, int | float)
        and not isinstance(budget_s, bool)
        and math.isfinite(budget_s)
        and budget_s > 0
    )


def _never_awaited(awaitable: Awaitable[Any]) -> None:
    """Close an awaitable that will not be waited for, so nothing is left
    half started or warned about."""
    if asyncio.iscoroutine(awaitable):
        awaitable.close()
    elif isinstance(awaitable, asyncio.Future):
        awaitable.cancel()


def _retrieve_quietly(task: asyncio.Future[Any]) -> None:
    """A done callback for a task stopped and not waited for: read its
    outcome so nothing is reported as never retrieved."""
    if not task.cancelled():
        task.exception()


async def _read_what_arrived(task: asyncio.Future[Any]) -> bool:
    """Give `task` up to `_GRACE_TURNS` turns of the loop, within `_LOOK_S`,
    to finish with a reply that arrived during a pause; True when it did."""
    began = time.monotonic()
    for _ in range(_GRACE_TURNS):
        if task.done():
            return True
        await asyncio.sleep(0)
        if time.monotonic() - began > _LOOK_S:
            break
    return task.done()


async def wait_counting_free_time(awaitable: Awaitable[_R], budget_s: float) -> _R:
    """Await `awaitable` for at most `budget_s` seconds of time the event
    loop was free to run, within `budget_s` plus `JEV_STALL_ALLOWANCE_S` of
    real time from the moment the wait began; past either, stop it and
    raise `TimeoutError` (step 3b of the guardrail design; F-8.6-FA03,
    F-72-J03).

    Every clock on a Jev call counts this way: Jev's own total bound
    (`_send`), `decide()`'s outer net (`_jev_attempt`) and the guardrail's
    injection net (`core.graph._jev_injection_pick`). Time the server spent
    frozen, on another question's synchronous work, is time nobody could
    read Jev's reply in, so it is not counted against Jev. On develop a
    pause of about 0.6 s inside `decide()`'s wait spent its half-second
    margin, the net said "timeout" while Jev was still inside its own bound,
    and a question Jev judged on topic was refused as off topic.

    The fix round's rules (cards 84 and 72):

    - A reply that has arrived wins over the clock: after a pause carries
      the wait past its real-time cap, the reply that landed during it is
      read before the wait gives up (`_read_what_arrived`, A-GR-07).
    - Running out on the real-time cap, or on the look limit, with Jev's own
      bound unspent raises `PausedTimeoutError`: the pause, not Jev, took
      the time (A-GR-11). Running out on Jev's own bound raises a plain
      `TimeoutError`, exactly as develop's `asyncio.wait_for` did.
    - The wall time is bounded, the allowance included (A-GR-06): when the
      last two looks both came back late, as on a busy server, the next one
      is predicted to take as long, and the wait stops rather than start a
      look that would carry it past the cap. Past the cap, what it waits on
      is stopped and not waited for. So the wait ends by the cap, give or
      take one turn of a busy loop.
    - A budget that is not a finite number above zero ends at once, and a
      clock that stands still or runs backwards still ends the wait, on its
      look limit (J-GR-03, A-GR-14, A-GR-09).

    A body that trickles in slowly (F-8.2-J03) does not stall the loop, so
    its time is counted in full and it is cut at the bound as before.
    """
    if not _is_a_budget(budget_s):
        _never_awaited(awaitable)
        raise TimeoutError
    task = asyncio.ensure_future(awaitable)
    cap_s = budget_s + JEV_STALL_ALLOWANCE_S
    looks_left = math.ceil(cap_s / _LOOK_S) + _SPARE_LOOKS
    started = last = time.monotonic()
    counted = 0.0
    stalled = False
    # How long each of the last two looks took when it came back late, 0.0
    # when it came back on time.
    late = (0.0, 0.0)
    try:
        while True:
            if task.done():
                return task.result()
            left_s = budget_s - counted
            if left_s <= _NONE_LEFT_S:
                raise TimeoutError
            next_look_s = min(late)
            real_left_s = cap_s - (time.monotonic() - started) - next_look_s
            if real_left_s <= _NONE_LEFT_S or looks_left <= 0:
                if stalled and await _read_what_arrived(task):
                    return task.result()
                raise PausedTimeoutError
            ask_s = min(_LOOK_S, left_s, real_left_s)
            await asyncio.wait({task}, timeout=ask_s)
            looks_left -= 1
            now = time.monotonic()
            took_s = max(0.0, now - last)
            last = now
            if took_s <= ask_s + _STALL_SLACK_S:
                counted += took_s
                late = (late[1], 0.0)
            else:
                stalled = True
                late = (late[1], took_s)
    except TimeoutError:
        # Past the bound: stop what it waits on, and do not wait for it to
        # wind down, so the person waits no longer than the bound (A-GR-06).
        if not task.done():
            task.cancel()
            task.add_done_callback(_retrieve_quietly)
        raise
    except BaseException as exc:
        # This wait itself stopped: stop what it waits on, and wait for it to
        # stop unless this coroutine is being closed, where no further wait
        # is allowed.
        if not task.done():
            task.cancel()
            if not isinstance(exc, GeneratorExit):
                await asyncio.gather(task, return_exceptions=True)
        raise


def _json_payload(response: httpx.Response, subject: str, next_step: str) -> object:
    """The 200 reply's body read as JSON, or an unusable-reply error charged
    the floor (F-8.6-RJ05; the owner's rule of 2026-09-29).

    A 200 came back from the provider, so the call was billed, but a body
    that cannot be read states no amount at all, so it is charged
    `JEV_FLOOR_COST_USD`, like any reply stating no cost. Any error reading
    it is caught, by base class: a body nested too deep raises
    `RecursionError`, not `ValueError`, and must not escape uncharged
    (F-8.6-FA01).
    """
    try:
        return response.json()
    except Exception as exc:  # every unreadable body, by base class
        raise _unusable_reply(
            subject,
            f"it could not be read as JSON ({type(exc).__name__})",
            next_step,
            charged_usd=JEV_FLOOR_COST_USD,
        ) from exc


_GENERIC_INSTRUCTIONS ="Read the state and answer with exactly one of the offered options."


def _build_body(
    *,
    model: str,
    question_key: str,
    state: str,
    options: Sequence[str],
    instructions: str | None = None,
    criteria: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """The request body.

    `instructions` and `criteria` are where the caller says WHAT is being
    decided (build phase 8.2 wave 2, builder J). Both are code-authored,
    fixed text, never user content: the person's words go in `state` and
    nowhere else, so an instruction and the data it judges never share a
    field. Omitted, both fall back to the generic text builder D shipped,
    byte for byte. Measured on 2026-09-25 with that generic text, Jev
    admitted "what is the best pizza in Chicago" as on topic at 0.44 and
    asked "Any trials for GERD?" back; with each decision described it
    answered 21 of 21 probes correctly (report: builder_J.md, F-J-03).
    """
    if criteria is None:
        criteria = {opt: f"Choose {opt!r} when it is the best answer for this decision." for opt in options}
    return {
        "model": model,
        "state": state,
        "questions": {
            question_key: {
                "type": "choice",
                "options": list(options),
                "instructions": instructions if instructions is not None else _GENERIC_INSTRUCTIONS,
                "criteria": dict(criteria),
            }
        },
    }


async def _post(headers: dict[str, str], body: dict[str, Any]) -> httpx.Response:
    """The bare POST, split out so tests can monkeypatch this one seam.

    No retry here (see the module docstring): a single attempt and the
    literal, host-pinned `JEV_DECISIONS_URL` constant, never a URL built
    from caller input. The per-phase httpx limits below are a first line
    only; the call's real bound is `call_jev`'s total timeout around this
    whole function, which a slow, steadily trickling body cannot outlast.
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        return await client.post(JEV_DECISIONS_URL, headers=headers, json=body)


async def _send(
    body: dict[str, Any],
    *,
    api_key: str,
    subject: str,
    next_step: str,
    timeout_s: float,
) -> tuple[httpx.Response, int]:
    """POST `body` under the TOTAL bound and return the 200 response and
    its latency in milliseconds.

    Shared by `call_jev` and `call_jev_batch`, so both carry the same
    timeout and error classes. `subject` names what was asked ("decision
    'x'", "3 questions") and `next_step` what the caller should do instead;
    both go into every error message, so an error says what to do next
    (production-standards.md's retry-safety gate). The key travels in the
    header only and is never put in a message.

    Raises:
        JevCallError: reason="timeout" when the call does not complete
            within `timeout_s` in total, body included; reason="http_error"
            on a transport failure (charged nothing) or a non-200 status
            (charged `JEV_FLOOR_COST_USD`).
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    start = time.monotonic()
    try:
        # The TOTAL bound (F-8.2-J03): connect, send, and the whole body
        # read, however it trickles in. `_post` finishes reading the body
        # before it returns, so nothing slow is left outside this wait.
        # Counted in time the server was free to read it (step 3b, F-72-J03).
        response = await wait_counting_free_time(_post(headers, body), timeout_s)
    except (TimeoutError, httpx.TimeoutException) as exc:
        # A wait that ran out on its real-time cap, the server's pauses having
        # taken the time, says so: Jev's pick is unknown, not missing (A-GR-11).
        raise JevCallError(
            f"Jev did not answer within {timeout_s}s in total for {subject}; {next_step}",
            reason="timeout",
            after_a_pause=isinstance(exc, PausedTimeoutError),
        ) from exc
    except httpx.HTTPError as exc:
        raise JevCallError(
            f"Jev transport failure for {subject} ({type(exc).__name__}: {exc}); {next_step}",
            reason="http_error",
        ) from exc
    latency_ms = int((time.monotonic() - start) * 1000)

    if response.status_code != 200:
        # An error status (a 500, 429 or 402) is a reply from the provider,
        # so it is charged the floor, never $0 (F-72-V03, the owner's rule of
        # 2026-09-29). A transport failure above, where nothing came back,
        # is charged nothing.
        raise JevCallError(
            f"Jev returned HTTP {response.status_code} for {subject} "
            f"({response.text[:200]!r}); it is charged ${JEV_FLOOR_COST_USD:.6f}; {next_step}",
            reason="http_error",
            billed_cost_usd=JEV_FLOOR_COST_USD,
        )
    return response, latency_ms


async def call_jev(
    *,
    model: str,
    question_key: str,
    state: str,
    options: Sequence[str],
    api_key: str,
    instructions: str | None = None,
    criteria: Mapping[str, str] | None = None,
) -> JevResult:
    """Ask Jev to pick one of `options` for the decision keyed by `question_key`.

    `state` is sent to Jev exactly as given; the caller (`harness.decide`)
    owns bounding its length before this function is called
    (ai-security-standards: only bounded state and the closed option set
    ever reach an external model, never raw user content unbounded).
    `instructions` and `criteria` describe the decision itself and go in
    the endpoint's own fields for them; see `_build_body`.

    Raises:
        JevCallError: reason="timeout" on a request that does not complete
            within 3 seconds in total, body included; reason="http_error" on a non-200 response or
            a transport-level failure (connection refused, DNS failure,
            and so on); reason="malformed_reply" when the response body is
            not valid JSON or does not match the confirmed response shape
            for `question_key`; reason="invalid_option" when Jev's own
            `choice` is not one of the offered `options`. Every message
            names what happened and that the caller should fall back to
            the guard tier's pick for this decision.
    """
    body = _build_body(
        model=model,
        question_key=question_key,
        state=state,
        options=options,
        instructions=instructions,
        criteria=criteria,
    )
    subject = f"decision {question_key!r}"
    next_step = "fall back to the guard tier's pick for this decision"
    response, latency_ms = await _send(
        body,
        api_key=api_key,
        subject=subject,
        next_step=next_step,
        timeout_s=_TIMEOUT_S,
    )

    payload = _json_payload(response, subject, next_step)
    stated_usd = _stated_cost_usd(payload)
    charged_usd = jev_charge_usd(stated_usd)
    if stated_usd is not None and stated_usd > MAX_JEV_COST_USD:
        raise _unusable_reply(
            subject,
            f"it reported a cost of ${stated_usd:.6f}, above the ${MAX_JEV_COST_USD:.2f} "
            "any one call should cost",
            next_step,
            charged_usd=charged_usd,
        )
    try:
        answer = payload["answers"][question_key]  # type: ignore[index]
        usage = payload["usage"]  # type: ignore[index]
        parsed = JevResult(
            resolved_model=str(payload["model"]),  # type: ignore[index]
            choice=str(answer["choice"]),
            confidence=float(answer["confidence"]),
            probabilities={str(k): float(v) for k, v in answer.get("probabilities", {}).items()},
            input_tokens=int(usage["input_tokens"]),
            output_tokens=int(usage["output_tokens"]),
            cost_usd=float(usage["cost"]),
            latency_ms=latency_ms,
        )
    except Exception as exc:  # every body shape, by base class
        # By base class, not a list: a list of five error types missed the
        # `AttributeError` of `"probabilities": null`, so that reply escaped
        # uncharged (F-8.6-FJ01). Charged what it states, as every reply is.
        raise _unusable_reply(
            subject,
            f"it did not match the confirmed response shape ({type(exc).__name__})",
            next_step,
            charged_usd=charged_usd,
        ) from exc

    if parsed.choice not in options:
        raise _unusable_reply(
            subject,
            f"it chose {parsed.choice!r}, which is not one of the offered options {list(options)!r}",
            next_step,
            charged_usd=charged_usd,
            reason="invalid_option",
        )

    # `cost_usd` is what the caller charges: the stated cost, or the floor
    # for a stated cost under it, $0 included (F-72-J02, J-GR-04).
    return parsed.model_copy(update={"cost_usd": _charged_for_usable(subject, parsed.cost_usd)})


# ---------------------------------------------------------------------------
# Several questions in one call (build phase 8.6, T-8.6-02).
# ---------------------------------------------------------------------------

#: The most questions one batch call may carry: the sentence check's own
#: `MAX_CANDIDATES`, and the size pinned live (thirty in 343 to 611 ms).
MAX_BATCH_QUESTIONS = 30

#: A ceiling on one question's code-authored text, the same bound
#: `harness.decide` puts on a decision's description.
_QUESTION_TEXT_MAX_CHARS = 1000


@dataclass(frozen=True)
class JevChoiceQuestion:
    """One closed-option question in a batch call.

    `instructions` and `criteria` are code-authored and fixed, never user
    content: the data every question judges travels once, in the call's
    shared `state`.
    """

    options: tuple[str, ...]
    instructions: str
    criteria: Mapping[str, str]


class JevAnswer(BaseModel):
    """One question's validated answer inside a batch reply."""

    model_config = ConfigDict(extra="forbid")

    choice: Annotated[str, Field(max_length=200)]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    probabilities: Annotated[
        dict[Annotated[str, Field(max_length=200)], Annotated[float, Field(ge=0.0, le=1.0)]],
        Field(max_length=_MAX_PROBABILITIES),
    ]


class JevBatchResult(BaseModel):
    """A batch call's parsed, schema-validated result: one answer per
    question asked, keyed as asked, and the call's usage.

    The same discipline as `JevResult` (`extra="forbid"`, every string and
    map bounded, and a reply reporting more than `MAX_JEV_COST_USD` for the
    whole call, about 30 times the $0.00033 measured for thirty questions,
    not used, and charged the `MAX_JEV_COST_USD` ceiling rather than the
    figure it reported; see `MAX_JEV_COST_USD`).
    """

    model_config = ConfigDict(extra="forbid")

    resolved_model: Annotated[str, Field(max_length=200)]
    answers: Annotated[dict[Annotated[str, Field(max_length=64)], JevAnswer], Field(max_length=MAX_BATCH_QUESTIONS)]
    input_tokens: Annotated[int, Field(ge=0)]
    output_tokens: Annotated[int, Field(ge=0)]
    cost_usd: Annotated[float, Field(ge=0.0, le=MAX_JEV_COST_USD)]
    latency_ms: Annotated[int, Field(ge=0)]


def _check_batch_questions(questions: Mapping[str, JevChoiceQuestion]) -> None:
    """Refuse a batch the endpoint should never be sent: a programming
    error in the caller, raised rather than sent."""
    if not questions:
        raise ValueError("call_jev_batch() was given no questions")
    if len(questions) > MAX_BATCH_QUESTIONS:
        raise ValueError(f"call_jev_batch() takes at most {MAX_BATCH_QUESTIONS} questions")
    for key, question in questions.items():
        if not key or len(key) > 64:
            raise ValueError(f"call_jev_batch(): question key {key!r} must be 1 to 64 characters")
        if len(question.options) < 2:
            raise ValueError(f"call_jev_batch(): question {key!r} offers fewer than two options")
        if set(question.criteria) != set(question.options):
            raise ValueError(f"call_jev_batch(): question {key!r} needs one criterion per option")
        texts = [question.instructions, *question.criteria.values()]
        if any(len(text) > _QUESTION_TEXT_MAX_CHARS for text in texts):
            raise ValueError(f"call_jev_batch(): question {key!r} has a description that is too long")


async def call_jev_batch(
    *,
    model: str,
    state: str,
    questions: Mapping[str, JevChoiceQuestion],
    api_key: str,
    timeout_s: float = _TIMEOUT_S,
) -> JevBatchResult:
    """Ask Jev every question in `questions` over one shared `state`, in ONE call.

    `state` is sent exactly as given; the caller owns bounding it, as for
    `call_jev`. `timeout_s` may shorten the 3-second total bound, never
    lengthen it: a caller with less time left passes what it has.

    Strict, so a reply the caller cannot trust is never half-used: every
    question asked must be answered under its own key and no other key may
    appear, or the whole reply is malformed; any answer outside its own
    question's options makes the whole reply an invalid option.

    Raises:
        ValueError: on a batch that is empty, too large, or whose questions
            do not fit their options (a programming error, see
            `_check_batch_questions`).
        JevCallError: reason="timeout", "http_error", "malformed_reply" or
            "invalid_option", each message ending in what to do next.
    """
    _check_batch_questions(questions)
    subject = f"{len(questions)} questions"
    next_step = "fall back to the guard tier for these questions"
    bound_s = min(timeout_s, _TIMEOUT_S)
    if bound_s <= 0:
        raise JevCallError(f"No time left to ask Jev {subject}; {next_step}", reason="timeout")
    body = {
        "model": model,
        "state": state,
        "questions": {
            key: {
                "type": "choice",
                "options": list(question.options),
                "instructions": question.instructions,
                "criteria": {opt: question.criteria[opt] for opt in question.options},
            }
            for key, question in questions.items()
        },
    }
    response, latency_ms = await _send(
        body, api_key=api_key, subject=subject, next_step=next_step, timeout_s=bound_s
    )

    payload = _json_payload(response, subject, next_step)
    stated_usd = _stated_cost_usd(payload)
    charged_usd = jev_charge_usd(stated_usd)
    if stated_usd is not None and stated_usd > MAX_JEV_COST_USD:
        raise _unusable_reply(
            subject,
            f"it reported a cost of ${stated_usd:.6f}, above the ${MAX_JEV_COST_USD:.2f} "
            "any one call should cost",
            next_step,
            charged_usd=charged_usd,
        )
    try:
        raw_answers = payload["answers"]  # type: ignore[index]
        if not isinstance(raw_answers, dict) or set(raw_answers) != set(questions):
            raise KeyError("the reply's answers do not match the questions asked, key for key")
        usage = payload["usage"]  # type: ignore[index]
        parsed = JevBatchResult(
            resolved_model=str(payload["model"]),  # type: ignore[index]
            answers={
                str(key): JevAnswer(
                    choice=str(answer["choice"]),
                    confidence=float(answer["confidence"]),
                    probabilities={str(k): float(v) for k, v in answer.get("probabilities", {}).items()},
                )
                for key, answer in raw_answers.items()
            },
            input_tokens=int(usage["input_tokens"]),
            output_tokens=int(usage["output_tokens"]),
            cost_usd=float(usage["cost"]),
            latency_ms=latency_ms,
        )
    except Exception as exc:  # every body shape, by base class (F-8.6-FJ01)
        raise _unusable_reply(
            subject,
            f"it did not match the confirmed response shape ({type(exc).__name__})",
            next_step,
            charged_usd=charged_usd,
        ) from exc

    for key, answer in parsed.answers.items():
        if answer.choice not in questions[key].options:
            raise _unusable_reply(
                subject,
                f"it chose {answer.choice!r} for question {key!r}, which is not one of its offered options",
                next_step,
                charged_usd=charged_usd,
                reason="invalid_option",
            )
    return parsed.model_copy(update={"cost_usd": _charged_for_usable(subject, parsed.cost_usd)})
