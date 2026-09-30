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
    - Nothing. What each reply is charged is fixed here and handed to the
      caller to charge through `Harness.track_cost`: a usable reply's own
      stated cost on `JevResult.cost_usd` when it is a sensible amount, and
      otherwise the small `JEV_FLOOR_COST_USD`, on `JevResult.cost_usd` or,
      for a reply that could not be used, on `JevCallError.billed_cost_usd`
      (`jev_charge_usd`; the R-10 fix round, the product owner's decision
      of 2026-09-29). This module never touches a `Harness` instance. It
      writes one log line whenever the floor is charged, naming the amount.

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
#: Enforced by `asyncio.wait_for` around `_post` in `call_jev`, because the
#: same float handed to `httpx.AsyncClient(timeout=...)` sets four SEPARATE
#: per-phase limits (connect, read, write, pool), and httpx's read limit is
#: the gap between two received chunks, not the response. Measured by the
#: phase 8.2 judge (F-8.2-J03): a server that sent the headers at once and
#: the body in 2-second pieces held one decision for 14 seconds, and Jev's
#: pick was still used.
_TIMEOUT_S = 3.0

#: Public name for the bound above, read by `harness.decide` to size how
#: long it waits for Jev before treating the call as timed out.
JEV_TOTAL_TIMEOUT_S = _TIMEOUT_S

JevFailureReason = str  # "timeout" | "http_error" | "malformed_reply" | "invalid_option"

#: The most one decision may report costing, in US dollars. Measured live at
#: $0.0000148 to $0.0000197 per call (builder D), so this is about 500 times
#: the real price. Jev's cost is the one model cost in the loop the loop does
#: not compute itself: it is whatever the undocumented endpoint says, and it
#: is charged straight into the per-query, per-user and system-wide caps.
#: A stated cost above it is not a sensible amount (F-8.6-V01: a reply once
#: reported 12.5 for a call that actually cost $0.0000125, and charging it
#: would have paused every person's questions for the rest of the day).
MAX_JEV_COST_USD = 0.01

#: What a Jev reply that came back is charged when it states no sensible
#: cost, in US dollars: about five times Jev's measured price, so a cap
#: still sees every call, and about a hundredth of `MAX_JEV_COST_USD`
#: (the R-10 fix round, the product owner's decision of 2026-09-29).
#:
#: A reply that reached the provider is never charged $0.0 (F-8.6-J10, V03,
#: FJ01, FA01; F-72-J02: a usable reply stating $0 used to be charged $0).
#: It is charged the cost it states when that is above zero and at most
#: `MAX_JEV_COST_USD`, and this floor otherwise: a reply that cannot be
#: used, whatever its body's shape, or one stating $0, no cost, or one
#: above the ceiling or not an amount at all. Not the ceiling: charging one
#: cent for every unusable reply made a drift in the endpoint's shape cost
#: about $0.07 a question, about 500 times develop, enough to pause every
#: person at the system's daily cap after a few hundred questions (F-72-A03).
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
    is what the caller charges: the stated cost when sensible, the
    `JEV_FLOOR_COST_USD` floor otherwise (`jev_charge_usd`).
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

    `billed_cost_usd` is what a reply that came back but could not be used
    is charged, in US dollars, on the question: always `JEV_FLOOR_COST_USD`,
    whatever the body's shape (`_unusable_reply`; the R-10 fix round). A
    malformed reply, an option outside the set and a reply reporting a cost
    above the ceiling or no usable cost are all billed that floor, never the
    reported figure and never $0.0. A reply with a status other than 200
    also came back from the provider and carries the same floor (card 84,
    F-72-V03). 0.0 only when no reply came back at all: a timeout or a
    transport error.
    """

    def __init__(self, message: str, *, reason: str, billed_cost_usd: float = 0.0) -> None:
        super().__init__(message)
        self.reason = reason
        self.billed_cost_usd = billed_cost_usd


def _reported_cost_usd(payload: object) -> float | None:
    """The amount a 200 reply states it cost, in US dollars, when it states
    a real one: a finite number, zero or more. None otherwise.

    A reply that states no cost, or a cost that is not a number, is a
    boolean, is negative, is not finite (`Infinity` and `NaN` both parse
    from JSON), or is an integer too large to become a float at all, states
    no amount. Read only to say, in the log and the error, that a reply
    claimed more than any one call should cost; what a reply is CHARGED is
    decided by `jev_charge_usd` and by whether it can be used
    (`_unusable_reply`), never by this figure alone.
    """
    try:
        raw = payload["usage"]["cost"]  # type: ignore[index]
    except Exception:  # noqa: BLE001 - any body shape that states no cost states no amount
        return None
    if isinstance(raw, bool):
        return None
    try:
        cost = float(raw)
    except Exception:  # noqa: BLE001 - not a number, or too large for a float
        return None
    return cost if math.isfinite(cost) and cost >= 0 else None


def jev_charge_usd(stated_usd: float | None) -> float:
    """What a Jev reply that came back is charged, in US dollars: the cost it
    states when that is a sensible amount, above zero and at most
    `MAX_JEV_COST_USD`; `JEV_FLOOR_COST_USD` otherwise (the R-10 fix round,
    the product owner's decision of 2026-09-29; F-72-J02, A03)."""
    if stated_usd is not None and 0.0 < stated_usd <= MAX_JEV_COST_USD:
        return stated_usd
    return JEV_FLOOR_COST_USD


def _unusable_reply(
    subject: str, detail: str, next_step: str, *, reason: str = "malformed_reply"
) -> JevCallError:
    """The error for a 200 reply that came back from the provider but cannot
    be used, charged `JEV_FLOOR_COST_USD`, and the ONE log line that says so
    (re-land follow-up R-10, F-8.6-FJ01, FA01, FJ02, FJ03; its fix round,
    F-72-A03).

    Every such reply, whatever its body's shape, is charged the floor.
    Nothing in a reply the loop cannot use is trusted, its stated cost
    included. Before R-10, a reply whose shape raised an error the parse did
    not name (`"probabilities": null`, a body nested too deep) escaped as an
    unexpected error and was charged $0 (FJ01, FA01, FJ03); R-10 then
    charged the one-cent ceiling, which made a drift in the endpoint's shape
    cost about $0.07 a question (A03). The warning below is written only
    here, at the moment the charge is fixed, and names the amount the error
    carries, which every charge site charges.

    `detail` is code-authored text plus, at most, an exception's type name
    or Jev's own bounded choice: never the key, never the state.
    """
    logger.warning(
        "Jev's reply for %s could not be used: %s; it is charged $%.4f",
        subject,
        detail,
        JEV_FLOOR_COST_USD,
    )
    return JevCallError(
        f"Jev's reply for {subject} could not be used: {detail}; it is charged "
        f"${JEV_FLOOR_COST_USD:.4f}; {next_step}",
        reason=reason,
        billed_cost_usd=JEV_FLOOR_COST_USD,
    )


def _charged_as_stated_or_floor(subject: str, stated_usd: float) -> float:
    """A USABLE reply's charge: its stated cost when sensible, else the
    floor, with one warning naming the floor (F-72-J02: a usable reply
    stating $0 used to be charged $0, invisible to every cap)."""
    charged = jev_charge_usd(stated_usd)
    if charged != stated_usd:
        logger.warning(
            "Jev's reply for %s stated a cost of $%.6f, not a sensible amount; it is charged $%.4f",
            subject,
            stated_usd,
            charged,
        )
    return charged


#: How long one look at the clock waits in `wait_counting_free_time`.
_LOOK_S = 0.05

#: A look that comes back later than asked by more than this was a stall of
#: the server's own event loop: only the time asked plus this is counted.
_STALL_SLACK_S = 0.05

#: The most real time a stalled server may add to one of Jev's bounds, so
#: a server that keeps stalling still ends the wait.
JEV_STALL_ALLOWANCE_S = 2.0


async def wait_counting_free_time(awaitable: Awaitable[_R], budget_s: float) -> _R:
    """Await `awaitable` for at most `budget_s` seconds of time the event
    loop was free to run, and never more than `budget_s` plus
    `JEV_STALL_ALLOWANCE_S` of real time; raise `TimeoutError` past that,
    after stopping it (the R-10 fix round, F-72-J03).

    Every clock on a Jev call counts this way: Jev's own total bound
    (`_send`), `decide()`'s outer net and the guardrail's injection net.
    Time the server spent frozen, on another question's synchronous work,
    is time nobody could read Jev's reply in, so it is not counted against
    Jev. Before, a stall of 0.6 s anywhere inside `decide()`'s wait spent
    its half-second margin, the net said "timeout" while Jev was still
    inside its own bound, and a question Jev judged on topic was refused as
    off topic (FA03). A reply that has arrived always wins over the clock:
    whatever finished is returned, whatever the time.

    A body that trickles in slowly (F-8.2-J03) does not stall the loop, so
    it is counted in full and cut at the bound as before.
    """
    task = asyncio.ensure_future(awaitable)
    started = last = time.monotonic()
    counted = 0.0
    try:
        while True:
            if task.done():
                return task.result()
            left_s = budget_s - counted
            real_left_s = budget_s + JEV_STALL_ALLOWANCE_S - (time.monotonic() - started)
            if left_s <= 0 or real_left_s <= 0:
                raise TimeoutError
            ask_s = min(_LOOK_S, left_s, real_left_s)
            await asyncio.wait({task}, timeout=ask_s)
            now = time.monotonic()
            counted += min(now - last, ask_s + _STALL_SLACK_S)
            last = now
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


def _json_payload(response: httpx.Response, subject: str, next_step: str) -> object:
    """The 200 reply's body read as JSON, or an unusable-reply error charged
    the ceiling (F-8.6-RJ05; R-10, F-8.6-FA01).

    A 200 came back from the provider, so the call was billed. A body that
    is empty, not JSON, not text, or nested too deep for the parser (which
    raises `RecursionError`, not `ValueError`) cannot be read, so any error
    reading it is caught, by base class, and charged the ceiling like every
    other reply that cannot be used.
    """
    try:
        return response.json()
    except Exception as exc:  # every unreadable body, by base class (R-10)
        raise _unusable_reply(
            subject, f"it could not be read as JSON ({type(exc).__name__})", next_step
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
            (charged `JEV_FLOOR_COST_USD`, since the provider replied).
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
        # Counted in time the server was free to read it (F-72-J03).
        response = await wait_counting_free_time(_post(headers, body), timeout_s)
    except (TimeoutError, httpx.TimeoutException) as exc:
        raise JevCallError(
            f"Jev did not answer within {timeout_s}s in total for {subject}; {next_step}",
            reason="timeout",
        ) from exc
    except httpx.HTTPError as exc:
        raise JevCallError(
            f"Jev transport failure for {subject} ({type(exc).__name__}: {exc}); {next_step}",
            reason="http_error",
        ) from exc
    latency_ms = int((time.monotonic() - start) * 1000)

    if response.status_code != 200:
        # A reply with a status other than 200 came back from the provider,
        # so it is charged the floor like every other reply that came back
        # and could not be used, never $0 (card 84, F-72-V03, the product
        # owner's decision of 2026-09-29). The warning names the amount.
        logger.warning(
            "Jev's reply for %s was HTTP %d, not used; it is charged $%.4f",
            subject,
            response.status_code,
            JEV_FLOOR_COST_USD,
        )
        raise JevCallError(
            f"Jev returned HTTP {response.status_code} for {subject} "
            f"({response.text[:200]!r}); it is charged ${JEV_FLOOR_COST_USD:.4f}; {next_step}",
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
    stated_usd = _reported_cost_usd(payload)
    if stated_usd is not None and stated_usd > MAX_JEV_COST_USD:
        raise _unusable_reply(
            subject,
            f"it reported a cost of ${stated_usd:.6f}, above the ${MAX_JEV_COST_USD:.2f} "
            "any one call should cost",
            next_step,
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
    except Exception as exc:  # every body shape, by base class (R-10, FJ01)
        # By base class, not a list (Review_rounds Rule 2): a list of five
        # error types missed `AttributeError` from `"probabilities": null`,
        # so that reply escaped uncharged (F-8.6-FJ01).
        raise _unusable_reply(
            subject,
            f"it did not match the confirmed response shape ({type(exc).__name__})",
            next_step,
        ) from exc

    if parsed.choice not in options:
        raise _unusable_reply(
            subject,
            f"it chose {parsed.choice!r}, which is not one of the offered options {list(options)!r}",
            next_step,
            reason="invalid_option",
        )

    # `cost_usd` is what the caller charges: the stated cost when sensible,
    # the floor otherwise, never $0 (F-72-J02).
    return parsed.model_copy(update={"cost_usd": _charged_as_stated_or_floor(subject, parsed.cost_usd)})


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
    not used, and charged `JEV_FLOOR_COST_USD` rather than the figure it
    reported; see `jev_charge_usd`). `cost_usd` is what the caller charges.
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
    stated_usd = _reported_cost_usd(payload)
    if stated_usd is not None and stated_usd > MAX_JEV_COST_USD:
        raise _unusable_reply(
            subject,
            f"it reported a cost of ${stated_usd:.6f}, above the ${MAX_JEV_COST_USD:.2f} "
            "any one call should cost",
            next_step,
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
    except Exception as exc:  # every body shape, by base class (R-10, FJ01)
        raise _unusable_reply(
            subject,
            f"it did not match the confirmed response shape ({type(exc).__name__})",
            next_step,
        ) from exc

    for key, answer in parsed.answers.items():
        if answer.choice not in questions[key].options:
            raise _unusable_reply(
                subject,
                f"it chose {answer.choice!r} for question {key!r}, which is not one of its offered options",
                next_step,
                reason="invalid_option",
            )
    return parsed.model_copy(update={"cost_usd": _charged_as_stated_or_floor(subject, parsed.cost_usd)})
