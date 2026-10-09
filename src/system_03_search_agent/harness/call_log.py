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
reported for that call, "unknown" when the reply carried none, no reply
came, or the field was not shaped like a host name). Every text field is
cut to `_FIELD_MAX_CHARS`, so the whole line has a bounded length
(`LINE_MAX_CHARS`).

Outcomes: ok, timeout, rate_limited, error, unusable_reply.

The level is WARNING on purpose, for every outcome, ok included. The service
configures no root log level, so Python's default (WARNING) drops INFO
lines before they reach the deployment's log, and the data this line exists
to gather is the latency of the calls that succeeded as much as of the ones
that failed. Lower it to INFO once step 2 of the guardrail design (host
routing) has ranked the upstream hosts from a week of these lines
(F-84-A08); the design is decided, the ranking is not.
"""

from __future__ import annotations

import contextlib
import logging
import re
import time
from typing import Any, Final

logger = logging.getLogger(__name__)

#: The longest provider name believed. The name is the router's own text,
#: so a longer one is not a host name and logs as "unknown".
_PROVIDER_MAX_CHARS: Final[int] = 64

#: A host-name-shaped provider: ASCII letters, digits, dots, hyphens and
#: underscores only, 1 to `_PROVIDER_MAX_CHARS` of them. The router's field
#: is untrusted text from outside, so a value with any other character, a
#: space, a line break, an escape sequence, a slash or an equals sign
#: included, is not repaired: it logs as "unknown" (step 3c of the
#: guardrail design, F-84-J07; fix round, A-GRS-01, J-GRS-10).
_HOST_NAME_SHAPED: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9._-]{1,64}")

#: The openings of a credential or token, lower-cased: router and model
#: keys, a bearer header, a JWT's encoded header, common access tokens.
_CREDENTIAL_OPENINGS: Final[tuple[str, ...]] = (
    "sk-", "sk_", "pk-", "pk_", "rk-", "rk_", "bearer", "eyj", "ghp_", "gho_", "github_pat", "xox", "akia",
)

#: A run between separators this long with a digit in it, or longer than
#: `_LONG_RUN_CHARS` at all, is a key or a token, not a part of a host
#: name: provider names and host labels are short words.
_DIGIT_RUN_CHARS: Final[int] = 16
_LONG_RUN_CHARS: Final[int] = 32
_SEPARATORS: Final[re.Pattern[str]] = re.compile(r"[._-]")

#: Every other text field's cap: `point`, `trace`, `kind` and `outcome`.
_FIELD_MAX_CHARS: Final[int] = 64

#: The longest line `log_model_call` can write: the fixed words, five text
#: fields at their cap and two integers.
LINE_MAX_CHARS: Final[int] = 512

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


def _looks_like_a_credential(value: str) -> bool:
    """Whether a host-name-shaped value is shaped like a key or a token: a
    known credential opening, or a run between separators of 16 or more
    characters with a digit in it, or of more than 32 characters."""
    if value.lower().startswith(_CREDENTIAL_OPENINGS):
        return True
    for run in _SEPARATORS.split(value):
        if len(run) > _LONG_RUN_CHARS:
            return True
        if len(run) >= _DIGIT_RUN_CHARS and any(ch.isdigit() for ch in run):
            return True
    return False


def provider_of(response: Any) -> str | None:
    """The upstream provider the router reported on `response`, or None.

    OpenRouter names the provider that served a call in a top-level
    `provider` field of its reply. Only a plain string is believed, so a
    reply without one, or a test double, reads as None. Outer whitespace is
    trimmed; then the value is kept only when it is shaped like a host name
    (`_HOST_NAME_SHAPED`: letters, digits, dots, hyphens and underscores, at
    most 64 characters) and not like a key or a token
    (`_looks_like_a_credential`). Anything else reads as None and logs as
    "unknown", never a repaired or cut copy, so no part of a secret, a URL
    or a forged field reaches the log (step 3c of the guardrail design,
    F-84-J07; fix round, A-GRS-01, J-GRS-10).
    """
    value = getattr(response, "provider", None)
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not _HOST_NAME_SHAPED.fullmatch(value) or _looks_like_a_credential(value):
        return None
    return value


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

    Every text field is cut to `_FIELD_MAX_CHARS` and the line to
    `LINE_MAX_CHARS`, whatever a caller passes (fix round, A-GRS-07).
    Never raises: a logging fault must not change what a search does.
    """
    with contextlib.suppress(Exception):  # observability only, never a failure of the call
        line = (
            f"model call point={str(point)[:_FIELD_MAX_CHARS]} trace={str(trace_id)[:_FIELD_MAX_CHARS]} "
            f"kind={str(kind)[:_FIELD_MAX_CHARS]} elapsed_ms={int((time.monotonic() - started) * 1000)} "
            f"outcome={str(outcome)[:_FIELD_MAX_CHARS]} attempt={int(attempt)} "
            f"provider={str(provider or 'unknown')[:_FIELD_MAX_CHARS]}"
        )
        logger.warning("%s", line[:LINE_MAX_CHARS])
