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
      charged the cost it states, naming the amount, an error status
      included. A warning carries a fixed category, the reply's length and
      the amounts, never the reply's own text: a reply can echo the
      person's question (fix round, A-GRS-05).

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
`_TIMEOUT_S`) and a host-pinned, literal URL (never
built from caller input) are both non-negotiable per
`tool-call-budgets.md` and `production-standards.md`'s multi-agent
pipeline gate.
"""

from __future__ import annotations

import asyncio
import logging
import math
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

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

#: The most one Jev reply is ever charged, in US dollars, and the most one
#: decision may report costing and still be used. Measured live at
#: $0.0000148 to $0.0000197 per call (builder D), so this is about 500 times
#: the real price. Jev's cost is the one model cost in the loop the loop does
#: not compute itself: it is whatever the undocumented endpoint says, and it
#: is charged straight into the per-query, per-user and system-wide caps.
#:
#: A reply stating more than this is not used: it is malformed, so the
#: guard's pick decides or, for the sentence check, nothing is approved. It
#: is charged the `JEV_FLOOR_COST_USD` floor, never the stated figure
#: (F-8.6-V01: a reply once reported 12.5 for a call that actually cost
#: $0.0000125, and charging it would have paused every person's questions
#: for the rest of the day). The floor, not this ceiling, because the
#: owner's rule of 2026-09-29 reads "the cost it states when that is above
#: $0 and at most `MAX_JEV_COST_USD`, otherwise a floor", and a stated cost
#: above this is "otherwise", whatever its spelling: 0.05, 1e309,
#: Infinity, an integer too large for a float, a numeric string (fix round
#: of 2026-10-09, J-GRS-03, J-GRS-04, A-GRS-03). Develop charged it this
#: ceiling (F-84-A06); the rule as written replaces that.
MAX_JEV_COST_USD = 0.01

#: What a Jev reply that came back is charged when it states no cost above
#: $0 and at most `MAX_JEV_COST_USD`, in US dollars: about five times Jev's measured price, so every cap
#: still sees the call, and a hundredth of `MAX_JEV_COST_USD` (the product
#: owner's rule of 2026-09-29, step 3a of the guardrail design).
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
    is above $0, and the `JEV_FLOOR_COST_USD` floor for a stated $0.
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
    as any reply is, the cost it states when that is above $0 and at most
    `MAX_JEV_COST_USD`, and otherwise the `JEV_FLOOR_COST_USD` floor: a
    stated cost above the ceiling, $0, no cost or no amount (F-84-J04:
    usable or not makes no difference). A reply with an error
    status (a 500, 429 or 402) reached the provider, so it is charged the
    floor (F-72-V03). 0.0 only when no reply came back at all: a timeout or
    a transport failure.
    """

    def __init__(self, message: str, *, reason: str, billed_cost_usd: float = 0.0) -> None:
        super().__init__(message)
        self.reason = reason
        self.billed_cost_usd = billed_cost_usd


def _stated_cost_usd(payload: object) -> float | None:
    """The cost a 200 reply states, in US dollars, or None when it states no
    readable amount.

    A finite number zero or more is an amount, a numeric string included, as
    `float()` reads it. A positive integer too large for a float states more
    than any call costs, so it reads as the largest float: above the
    ceiling, so the reply is not used. No `usage.cost`, a boolean, a figure
    that is not a number, a negative one, `NaN` and infinity are unreadable
    amounts. Every one of these is charged the floor by `jev_charge_usd`,
    above the ceiling included (the owner's rule of 2026-09-29, as
    written). What a reply is charged is decided by `jev_charge_usd` from
    this figure alone, whether or not the rest of the reply can be used
    (F-84-J04).
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
        return sys.float_info.max if isinstance(raw, int) and raw > 0 else None
    except Exception:  # noqa: BLE001 - not a number at all
        return None
    if not math.isfinite(cost) or cost < 0:
        return None
    return cost


def jev_charge_usd(stated_usd: float | None) -> float:
    """What a Jev reply that came back is charged, in US dollars, from the
    cost it states (the product owner's rule of 2026-09-29, step 3a of the
    guardrail design):

    - a finite cost above $0 and at most `MAX_JEV_COST_USD`: the stated
      cost, a stated cost under the floor included ($0.00002 is charged
      $0.00002);
    - everything else, "otherwise a floor" in the owner's words:
      `JEV_FLOOR_COST_USD`. That is a cost above `MAX_JEV_COST_USD`, however
      it is spelled (fix round, J-GRS-03: develop charged it the ceiling),
      $0, no stated cost, and an unreadable amount (None, `NaN`, infinity,
      a negative figure).

    The same for a usable reply and an unusable one (F-84-J04). A timeout,
    where no reply came back, is charged nothing and never reaches here.
    """
    if stated_usd is not None and math.isfinite(stated_usd) and 0.0 < stated_usd <= MAX_JEV_COST_USD:
        return stated_usd
    return JEV_FLOOR_COST_USD


#: The fixed categories an unusable reply's warning names, in place of
#: anything the reply said (fix round, A-GRS-05).
NOT_JSON = "not_json"
COST_ABOVE_CEILING = "cost_above_ceiling"
WRONG_SHAPE = "wrong_shape"
OPTION_OUTSIDE_SET = "option_outside_set"


def _unusable_reply(
    subject: str,
    category: str,
    detail: str,
    next_step: str,
    *,
    charged_usd: float,
    reply_length: int,
    reason: str = "malformed_reply",
) -> JevCallError:
    """The error for a reply that came back from the provider but cannot be
    used, charged `charged_usd` (`jev_charge_usd` of what it states, or the
    floor when the body could not be read at all), and the one log line that
    says so by amount.

    The log line carries `subject` (code-authored: a decision key or a
    count), one of the fixed categories above, the reply's length in bytes
    and the charge, and nothing the reply said (fix round, A-GRS-05). An
    option outside the set is Jev's own free text over the person's
    question, and a reply can echo that question, so it never reaches the
    log. `detail` goes only into the error's message, which callers do not
    log (they log `reason`): code-authored text plus, at most, an
    exception's type name, a bounded stated figure or Jev's own bounded
    choice, never the key, never the state.
    """
    logger.warning(
        "Jev's reply for %s could not be used: %s, reply length %d bytes; it is charged $%.6f",
        subject,
        category,
        reply_length,
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
    warning when that is not the stated cost (a stated $0 charged the floor,
    F-72-J02)."""
    charged = jev_charge_usd(stated_usd)
    if charged != stated_usd:
        logger.warning(
            "Jev's reply for %s stated a cost of $%.6f; it is charged $%.6f",
            subject,
            stated_usd,
            charged,
        )
    return charged


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
            NOT_JSON,
            f"it could not be read as JSON ({type(exc).__name__})",
            next_step,
            charged_usd=JEV_FLOOR_COST_USD,
            reply_length=len(response.content),
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
        response = await asyncio.wait_for(_post(headers, body), timeout=timeout_s)
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
        # An error status (a 500, 429 or 402) is a reply from the provider,
        # so it is charged the floor, never $0 (F-72-V03, the owner's rule of
        # 2026-09-29). A transport failure above, where nothing came back,
        # is charged nothing. Like every charge that is not a stated cost,
        # it is named in a warning, by status and length only, never the
        # body's text (fix round, J-GRS-11).
        logger.warning(
            "Jev returned HTTP %d for %s, reply length %d bytes; it is charged $%.6f",
            response.status_code,
            subject,
            len(response.content),
            JEV_FLOOR_COST_USD,
        )
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
        # `:.6g` keeps the figure short whatever its size (A-GRS-07).
        raise _unusable_reply(
            subject,
            COST_ABOVE_CEILING,
            f"it reported a cost of ${stated_usd:.6g}, above the ${MAX_JEV_COST_USD:.2f} "
            "any one call should cost",
            next_step,
            charged_usd=charged_usd,
            reply_length=len(response.content),
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
            WRONG_SHAPE,
            f"it did not match the confirmed response shape ({type(exc).__name__})",
            next_step,
            charged_usd=charged_usd,
            reply_length=len(response.content),
        ) from exc

    if parsed.choice not in options:
        raise _unusable_reply(
            subject,
            OPTION_OUTSIDE_SET,
            f"it chose {parsed.choice!r}, which is not one of the offered options {list(options)!r}",
            next_step,
            charged_usd=charged_usd,
            reply_length=len(response.content),
            reason="invalid_option",
        )

    # `cost_usd` is what the caller charges: the stated cost, or the floor
    # for a stated $0 (F-72-J02). A usable reply never states more than the
    # ceiling: `JevResult` refuses it above.
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
    not used, and charged the `JEV_FLOOR_COST_USD` floor rather than the
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
        # `:.6g` keeps the figure short whatever its size (A-GRS-07).
        raise _unusable_reply(
            subject,
            COST_ABOVE_CEILING,
            f"it reported a cost of ${stated_usd:.6g}, above the ${MAX_JEV_COST_USD:.2f} "
            "any one call should cost",
            next_step,
            charged_usd=charged_usd,
            reply_length=len(response.content),
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
            WRONG_SHAPE,
            f"it did not match the confirmed response shape ({type(exc).__name__})",
            next_step,
            charged_usd=charged_usd,
            reply_length=len(response.content),
        ) from exc

    for key, answer in parsed.answers.items():
        if answer.choice not in questions[key].options:
            raise _unusable_reply(
                subject,
                OPTION_OUTSIDE_SET,
                f"it chose {answer.choice!r} for question {key!r}, which is not one of its offered options",
                next_step,
                charged_usd=charged_usd,
                reply_length=len(response.content),
                reason="invalid_option",
            )
    return parsed.model_copy(update={"cost_usd": _charged_for_usable(subject, parsed.cost_usd)})
