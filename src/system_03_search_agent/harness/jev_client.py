"""The one HTTP call to Jev, the classifier-seam model, over OpenRouter's
alpha decisions endpoint (build phase 8.2, DECISIONS.md 2026-09-25, cards
8, 9, 10 and 13).

Depends on:
    - httpx (already a repo dependency via litellm's own transports),
      called directly here rather than through `litellm.acompletion`,
      because the decisions endpoint is not a chat-completions call and
      carries its own request and response shape.

Reads:
    - Nothing from the environment directly. The caller (`harness.decide`)
      resolves `JEV_MODEL` (via `harness.tiers.resolve_jev_model`) and
      reads `OPENROUTER_API_KEY`, then passes both in.

Writes:
    - Nothing. Jev's own `usage.cost` is returned on `JevResult` for the
      caller to charge through `Harness.track_cost`, and, for a reply that
      came back but could not be used, on `JevCallError.billed_cost_usd`
      (build phase 8.6 fix round, F-8.6-J10); this module never touches a
      `Harness` instance.

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
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

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

#: The most one decision may report costing, in US dollars. Measured live at
#: $0.0000148 to $0.0000197 per call (builder D), so this is about 500 times
#: the real price. Jev's cost is the one model cost in the loop the loop does
#: not compute itself: it is whatever the undocumented endpoint says, and it
#: is charged straight into the per-query, per-user and system-wide caps.
#:
#: A reply reporting more than this is not used: it is malformed, so the
#: guard's pick decides or, for the sentence check, nothing is approved. It
#: IS charged (build phase 8.6 fix round, F-8.6-J10), because the money was
#: spent either way and a reply the caps never see is exactly the expensive
#: one, but at this ceiling, never in full (F-8.6-V01): a reply once reported
#: 12.5 for a call that actually cost $0.0000125, and charging the full
#: figure would have paused every person's questions for the rest of the
#: day on one units slip from the undocumented alpha endpoint. The cost cap
#: then applies to the rest of the question as to any charge.
#:
#: A figure that is not a finite, non-negative amount is charged this same
#: ceiling too, never $0.0 (`_reported_cost_usd`, F-8.6-V03): `Infinity`
#: stopped every later model call in the question and turned the done
#: event's cost into null (F-8.2-J15), `NaN` would switch the per-query cap
#: off since no comparison with it is ever true, and a $0.0 charge for a
#: call that reached the provider and was billed left the cap blind to it.
MAX_JEV_COST_USD = 0.01

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
    for the same reason (F-8.2-J15).
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
    is charged, in US dollars, on the question (fix round, F-8.6-J10, then
    clamped to the ceiling by F-8.6-V01 and V03): a malformed reply, an
    option outside the set and a reply reporting a cost above
    `MAX_JEV_COST_USD` are all billed, but never above the ceiling. A
    well-formed cost at or under `MAX_JEV_COST_USD` is billed exactly as
    reported; anything else, a cost above the ceiling or a reply that
    states no amount, or one that is not a finite, non-negative number, is
    billed the ceiling itself, never the reported figure and never $0.0
    (`_reported_cost_usd`, `_cost_ceiling_error`). 0.0 only when no reply
    came back at all, for example a timeout or a transport error.
    """

    def __init__(self, message: str, *, reason: str, billed_cost_usd: float = 0.0) -> None:
        super().__init__(message)
        self.reason = reason
        self.billed_cost_usd = billed_cost_usd


def _reported_cost_usd(payload: object, subject: str) -> float:
    """What a 200 reply says the call cost, in US dollars, for the caller
    to charge; `MAX_JEV_COST_USD`, the ceiling, logged, when the reply
    states no usable amount (F-8.6-V03).

    A real amount only: a finite number, zero or more, read the way a
    usable reply's `usage.cost` is read. A reply that states no cost, or a
    cost that is not a number, is negative, is not finite (`Infinity` and
    `NaN` both parse from JSON), or is an integer too large to become a
    float at all (`float()` raises `OverflowError`), charges the ceiling
    instead of the stated amount, because no trustworthy amount was
    stated: `harness.py`'s rule is that a cost cap which guesses must guess
    toward stopping (F-2.1-B02), and a conservative finite charge is safer
    than the $0.0 this used to charge, which left the per-query cap blind
    to a call that reached the provider and was billed. The warning says
    so, so the ceiling charge is never silent. A finite, non-negative
    amount at or under the ceiling is returned exactly as reported; a
    finite amount above the ceiling is returned as reported too, since the
    caller (`_cost_ceiling_error`) is the one that clamps it, not this
    function.
    """
    try:
        raw = payload["usage"]["cost"]  # type: ignore[index]
    except (KeyError, TypeError, IndexError):
        logger.warning(
            "Jev's reply for %s states no cost, so it is charged the $%.2f ceiling",
            subject,
            MAX_JEV_COST_USD,
        )
        return MAX_JEV_COST_USD
    try:
        cost = None if isinstance(raw, bool) else float(raw)
    except (TypeError, ValueError, OverflowError):
        cost = None
    if cost is None or not math.isfinite(cost) or cost < 0:
        logger.warning(
            "Jev's reply for %s states a cost that is not an amount of money (%s), "
            "so it is charged the $%.2f ceiling",
            subject,
            repr(raw)[:40],
            MAX_JEV_COST_USD,
        )
        return MAX_JEV_COST_USD
    return cost


def _cost_ceiling_error(
    subject: str, cost_usd: float, next_step: str
) -> JevCallError:
    """The error for a reply that reports more than any one call should
    cost: not used, and charged at the ceiling instead of the reported
    figure (F-8.6-V01)."""
    logger.warning(
        "Jev's reply for %s reported a cost of $%.6f, above the $%.2f ceiling; "
        "the reply is not used and it is charged the $%.2f ceiling, not the reported figure",
        subject,
        cost_usd,
        MAX_JEV_COST_USD,
        MAX_JEV_COST_USD,
    )
    return JevCallError(
        f"Jev's reply for {subject} reported a cost of ${cost_usd:.6f}, above the "
        f"${MAX_JEV_COST_USD:.2f} any one call should cost, so it is not used and it is "
        f"charged the ${MAX_JEV_COST_USD:.2f} ceiling, not the reported figure; {next_step}",
        reason="malformed_reply",
        billed_cost_usd=MAX_JEV_COST_USD,
    )


_GENERIC_INSTRUCTIONS = "Read the state and answer with exactly one of the offered options."


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
            on a transport failure or a non-200 status.
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
        raise JevCallError(
            f"Jev returned HTTP {response.status_code} for {subject} "
            f"({response.text[:200]!r}); {next_step}",
            reason="http_error",
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

    billed_usd = 0.0
    try:
        payload = response.json()
        billed_usd = _reported_cost_usd(payload, subject)
        if billed_usd > MAX_JEV_COST_USD:
            raise _cost_ceiling_error(subject, billed_usd, next_step)
        answer = payload["answers"][question_key]
        usage = payload["usage"]
        parsed = JevResult(
            resolved_model=str(payload["model"]),
            choice=str(answer["choice"]),
            confidence=float(answer["confidence"]),
            probabilities={str(k): float(v) for k, v in answer.get("probabilities", {}).items()},
            input_tokens=int(usage["input_tokens"]),
            output_tokens=int(usage["output_tokens"]),
            cost_usd=float(usage["cost"]),
            latency_ms=latency_ms,
        )
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise JevCallError(
            f"Jev's reply for decision {question_key!r} did not match the confirmed response "
            f"shape ({type(exc).__name__}: {exc}); fall back to the guard tier's pick for this decision",
            reason="malformed_reply",
            billed_cost_usd=billed_usd,
        ) from exc

    if parsed.choice not in options:
        raise JevCallError(
            f"Jev chose {parsed.choice!r} for decision {question_key!r}, which is not one of "
            f"the offered options {list(options)!r}; fall back to the guard tier's pick for this decision",
            reason="invalid_option",
            billed_cost_usd=parsed.cost_usd,
        )

    return parsed


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
    not used, though its reported cost is still charged; see
    `MAX_JEV_COST_USD`).
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

    billed_usd = 0.0
    try:
        payload = response.json()
        billed_usd = _reported_cost_usd(payload, subject)
        if billed_usd > MAX_JEV_COST_USD:
            raise _cost_ceiling_error(subject, billed_usd, next_step)
        raw_answers = payload["answers"]
        if not isinstance(raw_answers, dict) or set(raw_answers) != set(questions):
            raise KeyError("the reply's answers do not match the questions asked, key for key")
        usage = payload["usage"]
        parsed = JevBatchResult(
            resolved_model=str(payload["model"]),
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
    except (KeyError, TypeError, ValueError, AttributeError, ValidationError) as exc:
        raise JevCallError(
            f"Jev's reply for {subject} did not match the confirmed response shape "
            f"({type(exc).__name__}); {next_step}",
            reason="malformed_reply",
            billed_cost_usd=billed_usd,
        ) from exc

    for key, answer in parsed.answers.items():
        if answer.choice not in questions[key].options:
            raise JevCallError(
                f"Jev chose {answer.choice!r} for question {key!r}, which is not one of its "
                f"offered options; {next_step}",
                reason="invalid_option",
                billed_cost_usd=parsed.cost_usd,
            )
    return parsed
