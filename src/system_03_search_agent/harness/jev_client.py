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
      caller to charge through `Harness.track_cost`; this module never
      touches a `Harness` instance.

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

Confirmed request shape, exactly one question per call (`decide()` calls
this once per decision point, never batched):

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
since exactly one question is ever sent, `answers[question_key]` is read
back directly.

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
import time
from collections.abc import Mapping, Sequence
from typing import Annotated, Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

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
#: A reply of `Infinity` stopped every later model call in the question and
#: turned the done event's cost into null; a reply of 0.5 would have pushed
#: every question past its $0.10 cap (fix round, F-8.2-J15). A reply above
#: this is malformed, so the guard's pick decides and nothing is charged.
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
    """

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


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
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = _build_body(
        model=model,
        question_key=question_key,
        state=state,
        options=options,
        instructions=instructions,
        criteria=criteria,
    )

    start = time.monotonic()
    try:
        # The TOTAL bound (F-8.2-J03): connect, send, and the whole body
        # read, however it trickles in. `_post` finishes reading the body
        # before it returns, so nothing slow is left outside this wait.
        response = await asyncio.wait_for(_post(headers, body), timeout=_TIMEOUT_S)
    except (TimeoutError, httpx.TimeoutException) as exc:
        raise JevCallError(
            f"Jev did not answer within {_TIMEOUT_S}s in total for decision {question_key!r}; "
            "fall back to the guard tier's pick for this decision",
            reason="timeout",
        ) from exc
    except httpx.HTTPError as exc:
        raise JevCallError(
            f"Jev transport failure for decision {question_key!r} ({type(exc).__name__}: {exc}); "
            "fall back to the guard tier's pick for this decision",
            reason="http_error",
        ) from exc
    latency_ms = int((time.monotonic() - start) * 1000)

    if response.status_code != 200:
        raise JevCallError(
            f"Jev returned HTTP {response.status_code} for decision {question_key!r} "
            f"({response.text[:200]!r}); fall back to the guard tier's pick for this decision",
            reason="http_error",
        )

    try:
        payload = response.json()
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
        ) from exc

    if parsed.choice not in options:
        raise JevCallError(
            f"Jev chose {parsed.choice!r} for decision {question_key!r}, which is not one of "
            f"the offered options {list(options)!r}; fall back to the guard tier's pick for this decision",
            reason="invalid_option",
        )

    return parsed
