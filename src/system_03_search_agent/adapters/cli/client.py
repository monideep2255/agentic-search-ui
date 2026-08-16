"""The HTTP and SSE client T-4.2-03 owns: `tracker/phase_4.2.md`.

`CliClient` wraps the four REST/SSE calls the `s3` CLI makes against the
surface build phase 4.0 finalized (`adapters/web_sse/app.py`): create a
run, stream its events, stop it, and export its citations. It holds no
retry policy of its own beyond the one hard rule `create_run` enforces
structurally (never retried, see below); the caller (`main.py`, T-4.2-05)
decides whether and how to retry a failed call, per `tracker/phase_4.2.md`'s
"retry is confined to the idempotent reads and to stop".

Seven wire facts this module is built against, each verified live this
session against the running server (`tracker/phase_4.2.md`'s pre-build
source read):

    1. `data:` carries the FULL `Event` envelope, decoded here into
       `contracts.events.Event` via `Event.model_validate_json`.
    2. A `: ping - <ts>` keepalive comment line is skipped by `sse.py`'s
       parser before it ever reaches this module.
    3. `id:` gaps for a non-operator caller are expected (`cost` events
       are stripped server-side while `seq` keeps counting) and are never
       treated as a dropped event; this module does not even look at the
       gap, it only ever forwards the decoded `Event`.
    4. `Last-Event-ID` is sent as a request HEADER (never a query
       parameter) on every `stream_events` call that carries one.
    5. `POST /v1/query` (`create_run`) issues exactly ONE HTTP request, no
       matter what happens: a network error propagates uncaught, an HTTP
       error status raises a typed `CliApiError`, and NOTHING in this
       function ever issues a second attempt. The endpoint carries no
       idempotency key, so a client-level retry after a timeout could
       spend a second allowance slot against a run the server may already
       have created. This is the one property `TestCreateIsNeverRetried`
       pins directly, and it is why `create_run` is written with no
       shared "retry on transient failure" helper the other three methods
       could reuse: sharing one would risk this exact property leaking a
       retry into `create_run` in a later edit.
    6. A stopped run's terminal event is a fatal `error` with
       `error_class: "cancelled"`, never a `done`. This module does not
       special-case that: `stream_events` yields every decoded `Event`
       exactly as the server sent it, including that one, and it is
       `main.py`'s and `render.py`'s job to treat a fatal `error` as
       stream-ending. Manufacturing a fake `done` here to paper over that
       shape would be the exact laxer-path failure
       `tracker/phase_4.2.md`'s refusal-path arm exists to catch.
    7. `GET /v1/query/{run_id}/citations` returns 409 before the run
       reaches a terminal state, and discloses `X-Run-Cancelled` /
       `X-Citations-Export-Truncated` as RESPONSE HEADERS, not body
       fields. The fixed interface's return type is `list[CitationPayload]`
       only, so those two disclosures are surfaced as instance attributes
       (`citations_run_cancelled`, `citations_export_truncated`) rather
       than folded into, or silently dropped from, the return value.

Depends on:
    - httpx (the injected `httpx.AsyncClient`; this module never
      constructs one of its own, per `tracker/phase_4.2.md`'s "the CLI's
      HTTP client MUST be injectable" finding)
    - system_03_search_agent.contracts.events (Event, CitationPayload)
    - system_03_search_agent.adapters.cli.sse (_SseLineAccumulator, the
      shared incremental parser core)
    - system_03_search_agent.adapters.cli.credentials (Credentials; a
      TYPE_CHECKING-only import, see the note below)

Reads:
    - Nothing directly. Every request carries the bearer token from the
      `Credentials` passed at construction; this module never reads
      `~/.system3/credentials` itself, that is `credentials.py`'s job.

Writes:
    - Nothing.

`Credentials` is a sibling module built in parallel this phase
(T-4.2-02). Importing it only under `TYPE_CHECKING`, combined with
`from __future__ import annotations` deferring every annotation to a
string, means this module's own tests and this module's own runtime
behavior never depend on `credentials.py` existing yet: `CliClient` only
ever touches `creds.access_token` and `creds.base_url` as plain
attributes, never anything `credentials.py`-specific.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

import httpx

from system_03_search_agent.adapters.cli.sse import _SseLineAccumulator
from system_03_search_agent.contracts.events import CitationPayload, Event

if TYPE_CHECKING:
    from system_03_search_agent.adapters.cli.credentials import Credentials

# ---------------------------------------------------------------------------
# Declared timeouts (tool-call-budgets.md: "a call without a declared
# timeout is not finished"). Two distinct values, not one, because the two
# call shapes have genuinely different failure-detection requirements:
#
#   _REST_CALL_TIMEOUT_S covers create_run, stop, and fetch_citations: a
#   plain request/response round trip against this repo's own backend,
#   never a live third-party API. 15.0s matches the interactive-HTTPS-call
#   budget `tool-call-budgets.md`'s table already sets for every other
#   15-second-class tool in this repo (ncbi_efetch, ncbi_dbsnp,
#   pubtator_annotate, litvar2_lookup, clinicaltrials_search): none of
#   these three calls does agent work inline (POST /v1/query returns as
#   soon as the run is registered, per app.py's own handler, not after the
#   agent loop finishes), so the same interactive-call budget is the right
#   fit rather than a bespoke number.
#
#   _STREAM_READ_TIMEOUT_S covers stream_events' one long-lived connection.
#   It cannot reuse the 15.0s figure above: the server's own
#   `sse_starlette` keepalive fires every 15 seconds
#   (tracker/phase_4.2.md's pre-build source read, row 2), so a read
#   timeout AT 15s would race a perfectly healthy connection's own
#   keepalive and could time out on ordinary jitter between "the ping was
#   sent" and "this client's read call actually observed it". The read
#   timeout has to be a small multiple of the keepalive interval, not
#   equal to it or below it, for the CLI to tell "the stream is idle but
#   alive" apart from "the stream is dead". 45.0s (3x the keepalive
#   interval) is that multiple: it survives two full missed keepalive
#   beats before giving up, which absorbs realistic network jitter or a
#   momentarily slow server without masking a connection that is
#   genuinely gone, since a truly dead connection is caught within one
#   keepalive cycle of that 45s bound, not left hanging indefinitely.
# ---------------------------------------------------------------------------
_REST_CALL_TIMEOUT_S: float = 15.0
_STREAM_CONNECT_TIMEOUT_S: float = 10.0
_STREAM_READ_TIMEOUT_S: float = 45.0
_STREAM_WRITE_TIMEOUT_S: float = 10.0
_STREAM_POOL_TIMEOUT_S: float = 10.0

_STREAM_TIMEOUT = httpx.Timeout(
    connect=_STREAM_CONNECT_TIMEOUT_S,
    read=_STREAM_READ_TIMEOUT_S,
    write=_STREAM_WRITE_TIMEOUT_S,
    pool=_STREAM_POOL_TIMEOUT_S,
)


# ---------------------------------------------------------------------------
# Typed errors. production-standards.md's retry-safety gate: an error must
# say what to do next, not just what failed. Each carries the server's own
# `reason` (when the body was the structured shape) and `message` (either
# shape) so `main.py`/`render.py` can act on it without re-parsing a
# response body a second time, and without ever needing to know which of
# the two mixed shapes (structured `{reason, message}` vs. a bare string)
# the server happened to use for this particular status code.
# ---------------------------------------------------------------------------


class CliApiError(Exception):
    """The server reached a response and returned a non-2xx status.

    `message` is always the server's own, already-human-readable text
    (never a raw exception string, never an interpolated token, matching
    `adapters/mcp/server.py`'s `_fatal_error_disclosure` precedent of a
    fixed, vetted message rather than anything untrusted flowing through
    verbatim: here the "vetting" is that `message` is always literally the
    server's own `detail`/`detail.message` field, a value this same
    codebase's other surfaces already render directly, never a client-
    invented string and never the raw response body dumped unparsed).
    """

    def __init__(self, status_code: int, reason: str | None, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason
        self.message = message


class AuthExpiredError(CliApiError):
    """401: the access token is missing, expired, invalid, or (per
    `tracker/phase_4.2.md`'s pre-build source read) belongs to a guest
    session that was migrated at signup/login and is no longer spendable.

    This module never reissues the failed call itself. The caller may
    call `credentials.refresh_locked(...)` and construct a fresh
    `CliClient` with the rotated token to retry, EXCEPT after a
    `create_run` call: `tracker/phase_4.2.md`'s phase premise confines
    retry, including a refresh-triggered reissue, to the idempotent reads
    and to `stop`. A 401 is always safe to reissue after a refresh (the
    dependency rejects it before any handler body runs, so the server
    never acted on the original request), which is the property that
    makes ANY reissue here safe at all, discussed at more length on
    `create_run`'s own docstring below.
    """


class ForbiddenError(CliApiError):
    """403: the caller is authenticated but not the run's owner, or (for
    `create_run`) a guest allowance is exhausted rather than merely
    rate-limited."""


class NotFoundError(CliApiError):
    """404: no run exists with the given run_id."""


class ConflictError(CliApiError):
    """409: `fetch_citations` called before the run reached a terminal
    state (a `done`, a stop, or an abandonment cancellation)."""


class RateLimitedError(CliApiError):
    """429: a concurrent-run cap or a daily allowance ceiling. Carries
    `retry_after_s`, parsed from the response's `Retry-After` header, when
    the server sent one (every 429 this backend emits does)."""

    def __init__(
        self,
        status_code: int,
        reason: str | None,
        message: str,
        *,
        retry_after_s: int | None = None,
    ) -> None:
        super().__init__(status_code, reason, message)
        self.retry_after_s = retry_after_s


_ERROR_CLASS_BY_STATUS: dict[int, type[CliApiError]] = {
    401: AuthExpiredError,
    403: ForbiddenError,
    404: NotFoundError,
    409: ConflictError,
    429: RateLimitedError,
}


def _parse_error_detail(response: httpx.Response) -> tuple[str | None, str]:
    """Parse the mixed error-body shapes this backend actually sends
    (`tracker/phase_4.2.md`'s pre-build source read, row 8): a 429 body is
    structured (`{"detail": {"reason": ..., "message": ...}}`), while
    401/403/404/409 bodies are bare strings (`{"detail": "..."}`). Handles
    either shape, and degrades to the raw response text (never raising)
    for anything that is neither, so a future, differently-shaped error
    body still produces a renderable message instead of crashing this
    call.
    """
    try:
        body: Any = response.json()
    except ValueError:
        return None, response.text.strip() or f"HTTP {response.status_code}"
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, dict):
        reason = detail.get("reason")
        message = detail.get("message")
        return (
            reason if isinstance(reason, str) else None,
            message if isinstance(message, str) else str(detail),
        )
    if isinstance(detail, str):
        return None, detail
    return None, response.text.strip() or f"HTTP {response.status_code}"


def _parse_retry_after(raw_value: str | None) -> int | None:
    if raw_value is None:
        return None
    try:
        return int(raw_value)
    except ValueError:
        return None


def _raise_for_status(response: httpx.Response) -> None:
    """Raise the typed `CliApiError` subclass matching `response`'s status
    code, or return normally for a 2xx response. Never called on a
    response whose body has not already been read (a streamed response
    must `await response.aread()` first)."""
    if response.status_code < 400:
        return
    reason, message = _parse_error_detail(response)
    error_cls = _ERROR_CLASS_BY_STATUS.get(response.status_code, CliApiError)
    if error_cls is RateLimitedError:
        raise RateLimitedError(
            response.status_code,
            reason,
            message,
            retry_after_s=_parse_retry_after(response.headers.get("retry-after")),
        )
    raise error_cls(response.status_code, reason, message)


class CliClient:
    """A thin client over the four calls `s3` makes. Holds an injected
    `httpx.AsyncClient` (never constructs its own, so the premise gate can
    pass an `ASGITransport` and exercise this exact code end to end) and a
    fixed `Credentials` snapshot for the duration of its lifetime: it never
    mutates `creds` and never refreshes a token itself. A caller that
    needs to retry after a refresh constructs a new `CliClient` with the
    rotated `Credentials`, which is cheap: this class holds no other state.
    """

    def __init__(self, http: httpx.AsyncClient, creds: Credentials) -> None:
        self._http = http
        self._creds = creds
        # The two response-header disclosures `fetch_citations` surfaces.
        # The fixed interface's return type is `list[CitationPayload]`
        # only, so these live as instance attributes a caller reads after
        # the call returns, per this module's docstring, item 7. `None`
        # until the first successful `fetch_citations` call; a caller must
        # not read either before calling `fetch_citations` at least once.
        self.citations_run_cancelled: bool | None = None
        self.citations_export_truncated: bool | None = None

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._creds.access_token}"}

    async def create_run(
        self, text: str, session_id: str, audience_depth: str
    ) -> tuple[str, str]:
        """`POST /v1/query`. Returns `(run_id, persona_name)`.

        NEVER retried, under any circumstance: not a network timeout, not
        a connection error, not an HTTP error status. Exactly one request
        is issued. See this module's docstring, item 5, and
        `TestCreateIsNeverRetried` (both the direct-timeout unit arm and
        the end-to-end 429 arm) for what this property is proven against.
        A caller MAY reissue this call itself after observing a raised
        `AuthExpiredError` and refreshing the token (the one case where a
        second attempt is known-safe, since a 401 means the server never
        acted on the first request), but that reissue is the caller's own,
        separate, deliberate call, never something this function does on
        its own behalf.
        """
        response = await self._http.post(
            "/v1/query",
            json={
                "text": text,
                "session_id": session_id,
                "audience_depth": audience_depth,
            },
            headers=self._auth_headers(),
            timeout=_REST_CALL_TIMEOUT_S,
        )
        _raise_for_status(response)
        body = response.json()
        return body["run_id"], body["persona_name"]

    async def stream_events(
        self, run_id: str, *, last_event_id: str | None = None
    ) -> AsyncIterator[Event]:
        """`GET /v1/query/{run_id}/events`, an SSE stream. Yields every
        decoded `Event` the server sends, in order, including a terminal
        fatal `error` (`error_class="cancelled"` for a stopped or
        abandoned run) exactly as received: this method makes no judgment
        about what ends the stream, it only decodes and forwards what the
        server wrote, per this module's docstring, item 6.

        `last_event_id`, when given, is sent as the `Last-Event-ID`
        request HEADER (never a query parameter, per this module's
        docstring, item 4), letting a reconnecting caller resume from the
        `seq` it last saw. A malformed or out-of-range value is rejected
        by the server with a 400 BEFORE the stream body opens, which
        surfaces here as a raised `CliApiError` before any `Event` is
        yielded, never as a mid-stream failure.
        """
        headers = self._auth_headers()
        headers["Accept"] = "text/event-stream"
        if last_event_id is not None:
            headers["Last-Event-ID"] = last_event_id

        accumulator = _SseLineAccumulator()
        async with self._http.stream(
            "GET",
            f"/v1/query/{run_id}/events",
            headers=headers,
            timeout=_STREAM_TIMEOUT,
        ) as response:
            if response.status_code >= 400:
                await response.aread()
                _raise_for_status(response)
            async for raw_line in response.aiter_lines():
                parsed = accumulator.feed(raw_line)
                if parsed is None:
                    continue
                _event_type, data, _seq_id = parsed
                yield Event.model_validate_json(data)
            trailing = accumulator.flush()
            if trailing is not None:
                _event_type, data, _seq_id = trailing
                yield Event.model_validate_json(data)

    async def stop(self, run_id: str) -> bool:
        """`POST /v1/query/{run_id}/stop`. Returns the server's own
        `stopped` field. The endpoint is idempotent server-side (stopping
        an already-finished run is a no-op, still 200), so this call is
        safe for a caller's retry policy to reissue, unlike `create_run`.
        """
        response = await self._http.post(
            f"/v1/query/{run_id}/stop",
            headers=self._auth_headers(),
            timeout=_REST_CALL_TIMEOUT_S,
        )
        _raise_for_status(response)
        return bool(response.json()["stopped"])

    async def fetch_citations(self, run_id: str) -> list[CitationPayload]:
        """`GET /v1/query/{run_id}/citations`. Raises `ConflictError`
        (409) if the run has not reached a terminal state yet. Reads the
        two disclosure headers into `self.citations_run_cancelled` and
        `self.citations_export_truncated` as a side effect (see this
        module's docstring, item 7, and `CliClient.__init__`'s comment on
        why they cannot live on the return value itself); a caller that
        needs either disclosure must read the attribute immediately after
        this call returns.
        """
        response = await self._http.get(
            f"/v1/query/{run_id}/citations",
            headers=self._auth_headers(),
            timeout=_REST_CALL_TIMEOUT_S,
        )
        _raise_for_status(response)
        self.citations_run_cancelled = response.headers.get("x-run-cancelled") == "true"
        self.citations_export_truncated = (
            response.headers.get("x-citations-export-truncated") == "true"
        )
        return [CitationPayload.model_validate(item) for item in response.json()]
