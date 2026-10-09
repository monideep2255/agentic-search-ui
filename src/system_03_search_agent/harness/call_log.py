"""One structured log line per classifier-model call (card 72, logging half).

A search can end with "This run could not be completed" because the guard
model did not answer in time. Before the guardrail's design is decided, the
deployment's log has to say how long each call took, how it ended, and which
upstream provider the router sent it to. This module is that line, and
nothing else: it reads no state, changes no timeout, retry or verdict, and
never sees the question, the prompt, the reply or a token.

Fields, in order: `point` (the decision point or step name), `trace` (the
trace id, the join key to every other event), `kind` ("guard" or "jev"),
`elapsed_ms`, `outcome`, `attempt` and `provider` (the upstream the router
reported for that call, "unknown" when the reply carried none or no reply
came).

Outcomes: ok, timeout, rate_limited, error, unusable_reply.

The level is WARNING on purpose, for every outcome, ok included. The service
configures no root log level, so Python's default (WARNING) drops INFO
lines before they reach the deployment's log, and the data this line exists
to gather is the latency of the calls that succeeded as much as of the ones
that failed. Lower it to INFO once the guardrail's design is decided.
"""

from __future__ import annotations

import contextlib
import logging
import time
from typing import Any, Final

logger = logging.getLogger(__name__)

#: The provider name is the router's own text; cap it so a log line stays
#: one short line whatever the router sent.
_PROVIDER_MAX_CHARS: Final[int] = 64

OK: Final[str] = "ok"
TIMEOUT: Final[str] = "timeout"
RATE_LIMITED: Final[str] = "rate_limited"
ERROR: Final[str] = "error"
UNUSABLE_REPLY: Final[str] = "unusable_reply"


def outcome_for_error(exc: BaseException) -> str:
    """The outcome word for a failed `call_tier`/`enforce_timeout` call.

    A `HarnessCallError` from `enforce_timeout` is a timeout; one with an
    HTTP 429 on its cause chain is a rate limit (read by status, not class,
    as `core/graph.py`'s `_rate_limit_behind` does); anything else is an
    error. Duck-typed on `source`, so this module imports nothing from
    `harness.harness`.
    """
    if str(getattr(exc, "source", "")).startswith("harness.enforce_timeout"):
        return TIMEOUT
    cause = exc.__cause__
    for _ in range(5):
        if cause is None:
            break
        if getattr(cause, "status_code", None) == 429:
            return RATE_LIMITED
        cause = cause.__cause__
    return ERROR


def jev_outcome(reason: str) -> str:
    """The outcome word for a `JevCallError.reason`: a reply that came back
    but could not be used is `unusable_reply`, a transport failure `error`."""
    if reason == "timeout":
        return TIMEOUT
    if reason in ("malformed_reply", "invalid_option"):
        return UNUSABLE_REPLY
    return ERROR


def provider_of(response: Any) -> str | None:
    """The upstream provider the router reported on `response`, or None.

    OpenRouter names the provider that served a call in a top-level
    `provider` field of its reply. Only a plain string is believed, so a
    reply without one, or a test double, reads as None.
    """
    value = getattr(response, "provider", None)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()[:_PROVIDER_MAX_CHARS]


def log_model_call(
    *,
    point: str,
    trace_id: str,
    kind: str,
    started: float,
    outcome: str,
    attempt: int = 1,
    provider: str | None = None,
) -> None:
    """Emit the one line. `started` is a `time.monotonic()` reading.

    Never raises: a logging fault must not change what a search does.
    """
    with contextlib.suppress(Exception):  # observability only, never a failure of the call
        logger.warning(
            "model call point=%s trace=%s kind=%s elapsed_ms=%d outcome=%s attempt=%d provider=%s",
            point,
            trace_id,
            kind,
            int((time.monotonic() - started) * 1000),
            outcome,
            attempt,
            provider or "unknown",
        )
