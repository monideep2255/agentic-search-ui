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

import codecs
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import ValidationError

from system_03_search_agent.adapters.cli.sse import _SseLineAccumulator
from system_03_search_agent.contracts.events import (
    PAYLOAD_MODEL_BY_TYPE,
    CitationPayload,
    ErrorPayload,
    Event,
)

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
# F-4.2-A-02: `httpx.Response.aiter_lines()` decodes with `httpx`'s own
# `LineDecoder`, which splits on the WHATWG `str.splitlines()` separator
# set: "\n\r\x0b\x0c\x1c\x1d\x1e\x85" plus U+2028/U+2029, not on LF/CR/CRLF
# alone. U+2028 (LINE SEPARATOR), U+2029 (PARAGRAPH SEPARATOR), and U+0085
# (NEL) are ordinary characters in biomedical free text
# (`adapters/web_sse/app.py`'s serializer emits them raw inside a `data:`
# line's JSON string), so a citation claim or an abstract fragment
# containing one gets cut in half mid-line by `aiter_lines()`, corrupting
# the JSON and losing the whole answer. A browser `EventSource` only ever
# splits on LF, CR, and CRLF, per the `text/event-stream` grammar
# (WHATWG HTML "Interpreting an SSE event stream"), which is why the web
# UI never hits this and only this CLI reader does.
#
# `_ChunkSafeLineSplitter` below replicates that narrower grammar
# directly over `httpx.Response.aiter_bytes()`, decoding UTF-8
# incrementally (`codecs.getincrementaldecoder`) so a multi-byte
# character split across two network chunks reassembles correctly rather
# than raising or corrupting on the boundary. It feeds the same shared
# `_SseLineAccumulator` core `sse.py`'s `parse_sse_lines` uses, per this
# module's docstring ("share one accumulator, as the module already
# does"); `parse_sse_lines` itself is untouched; it never had a raw
# `httpx` byte stream to mis-split in the first place.
# ---------------------------------------------------------------------------


class _ChunkSafeLineSplitter:
    """Splits a raw byte stream into text lines on LF, CR, or CRLF ONLY,
    never on U+2028, U+2029, U+0085, or any other `str.splitlines()`
    separator, decoding UTF-8 incrementally across chunk boundaries.

    Three boundary cases a naive `"".join(chunks).split("\\n")` approach
    gets wrong, all handled here:

        - A multi-byte UTF-8 character's bytes split across two `feed()`
          calls: `codecs.getincrementaldecoder("utf-8")` buffers the
          incomplete trailing bytes internally and completes the
          character on the next `feed()`, never raising and never
          silently dropping a byte.
        - A CRLF pair split across two `feed()` calls (the `\\r` in one
          chunk, the `\\n` in the next): a lone trailing `\\r` is held
          back rather than immediately emitted as a line terminator,
          since it might be the first half of a `\\r\\n` pair. `close()`
          resolves it as its own line terminator once no more data is
          coming.
        - F-4.2-RR-04: a byte (or byte run) that is NEVER valid UTF-8 at
          all, for example a lone `0xFF`, arriving mid-stream rather than
          at the connection's own end. `feed()` used to let the
          incremental decoder's `UnicodeDecodeError` escape uncaught,
          which propagated all the way to `main.py`'s broad catch-all and
          ended the run with a generic "the event stream ended
          unexpectedly" message, even though the connection itself was
          very likely still alive and more valid frames may still follow.
          `feed()` now recovers locally, replacing exactly the
          undecodable byte(s) with the standard U+FFFD replacement
          character and continuing, the SAME "never crash, always leave
          something visible" discipline `close()` already applies at the
          stream's own end, deliberately NOT treated as
          `self.truncated_utf8` (see `feed()`'s own docstring for why the
          two are kept distinct).
    """

    def __init__(self) -> None:
        self._decoder = codecs.getincrementaldecoder("utf-8")()
        self._buffer = ""
        self.truncated_utf8 = False
        self.replaced_invalid_utf8 = False

    def feed(self, raw_bytes: bytes) -> list[str]:
        """Decode `raw_bytes` (plus any bytes the incremental decoder
        already held back from a previous call as a possibly-incomplete
        trailing sequence) and extract every complete line.

        F-4.2-RR-04: an incremental decoder in the default `strict` error
        mode does NOT raise for a merely-incomplete trailing sequence in
        non-final mode (that case is buffered internally without error,
        which is the whole reason this class uses an incremental decoder
        at all); it raises only when a byte is definitively, unambiguously
        invalid UTF-8 regardless of what follows. So a `UnicodeDecodeError`
        caught here is never a false positive against the legitimate
        chunk-boundary case `close()` already handles.

        Recovery replaces the bad byte(s) with U+FFFD and keeps going,
        rather than ending the whole splitter, because a genuinely
        invalid byte does not mean the connection ended: unlike `close()`'s
        own truncation case, more valid frames may still arrive after it.
        Whatever event the corrupted bytes actually belonged to almost
        always still fails its own JSON parse or `Event` schema
        validation downstream (`_decode_stream_event`), which already
        classifies that failure correctly (a benign skip for an
        unrecognized frame, or a fatal, surfaced failure for a known-type
        frame per F-4.2-RR-03); this method's only job is to never let one
        bad byte crash the reader before that classification gets a
        chance to run.

        `exc.object` (not `raw_bytes` alone) is what gets re-decoded with
        `errors="replace"`: `codecs`' own incremental-decoder exceptions
        report the FULL bytes it was working over, including any prefix
        the decoder was already holding back from a previous `feed()`
        call as a possibly-incomplete sequence, so recovering from
        `exc.object` never silently drops that carried-over prefix. The
        decoder itself is replaced with a fresh instance afterward, since
        its own internal buffer state is now fully accounted for by the
        one-shot recovery decode and must not be reused.
        """
        try:
            self._buffer += self._decoder.decode(raw_bytes)
        except UnicodeDecodeError as exc:
            self._buffer += exc.object.decode("utf-8", errors="replace")
            self._decoder = codecs.getincrementaldecoder("utf-8")()
            self.replaced_invalid_utf8 = True
        return self._extract_complete_lines()

    def close(self) -> list[str]:
        """Call once after the byte source is exhausted. Finalizes the
        UTF-8 decoder (an incomplete trailing multi-byte sequence here
        means the connection was cut mid-character, itself a genuine
        transport truncation, recorded via `self.truncated_utf8` rather
        than raised, since a stream-end truncation is an expected shape
        this reader must survive, not a programming error) and returns
        any remaining lines, including a final unterminated one.
        """
        try:
            self._buffer += self._decoder.decode(b"", final=True)
        except UnicodeDecodeError:
            self.truncated_utf8 = True
        lines = self._extract_complete_lines()
        if self._buffer:
            lines.append(self._buffer)
            self._buffer = ""
        return lines

    def _extract_complete_lines(self) -> list[str]:
        lines: list[str] = []
        start = 0
        length = len(self._buffer)
        i = 0
        while i < length:
            ch = self._buffer[i]
            if ch == "\n":
                lines.append(self._buffer[start:i])
                i += 1
                start = i
            elif ch == "\r":
                if i + 1 < length:
                    if self._buffer[i + 1] == "\n":
                        lines.append(self._buffer[start:i])
                        i += 2
                    else:
                        lines.append(self._buffer[start:i])
                        i += 1
                    start = i
                else:
                    # This \r is the last character seen so far: it may
                    # be the first half of a \r\n pair split across a
                    # chunk boundary. Stop and hold it (and everything
                    # from `start`) in the buffer for the next feed().
                    break
            else:
                i += 1
        self._buffer = self._buffer[start:]
        return lines


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


def _parse_json_body(
    response: httpx.Response, *, endpoint: str, expected_statuses: frozenset[int]
) -> Any:
    """Parse `response`'s body as JSON, or raise a `CliApiError` with an
    actionable message instead of letting a non-JSON or unexpected-status
    success response crash on a raw `json.JSONDecodeError` or a raw
    `KeyError` further down the call chain (F-4.2-A-24). Only called
    after `_raise_for_status`, so `response.status_code` is already known
    to be below 400; a 204 No Content, a followed 302/303, or any other
    2xx/3xx this repo's server never intentionally sends for this
    endpoint still needs an explicit reject here, since `< 400` alone
    does not mean "has a JSON body".
    """
    if response.status_code not in expected_statuses:
        raise CliApiError(
            response.status_code,
            None,
            f"{endpoint} returned an unexpected status {response.status_code} "
            f"(expected one of {sorted(expected_statuses)}); this indicates a "
            "server or proxy misconfiguration, not a normal failure. Retry "
            "later, or report this to the operator if it recurs.",
        )
    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise CliApiError(
            response.status_code,
            None,
            f"{endpoint} returned a non-JSON response (status "
            f"{response.status_code}, content-type "
            f"{content_type or 'none'}); this indicates a server or proxy "
            "misconfiguration, not a normal failure. Retry later, or report "
            "this to the operator if it recurs.",
        )
    try:
        return response.json()
    except ValueError as exc:
        raise CliApiError(
            response.status_code,
            None,
            f"{endpoint} declared a JSON content type but the body did not "
            f"parse as JSON ({type(exc).__name__}); retry, or report this to "
            "the operator if it recurs.",
        ) from exc


# F-4.2-RR-03: the closed, eleven-member envelope-`type` taxonomy
# (`contracts.events.PAYLOAD_MODEL_BY_TYPE`), used by `_decode_stream_event`
# to tell an ADDITIVE, not-yet-taught event type (system-design-patterns
# rule 10, benign, safe to skip) apart from a frame that claims to be one
# of the types this build already knows but whose envelope or payload
# failed to validate against it (a defect, never silently absorbed).
_KNOWN_EVENT_TYPES: frozenset[str] = frozenset(PAYLOAD_MODEL_BY_TYPE)


def _payload_declares_unknown_type(data: str) -> bool:
    """F-4.2-D-02 (round-4 fix): the ONLY source of positive evidence that
    a frame is benignly skippable, replacing the round-3 fix's SSE
    `event:` check.

    The round-3 comment this replaced claimed `event:` "survives even
    when the `data:` body itself is too corrupted to parse as JSON at
    all", and used it as the discriminator instead of peeking into
    `data:`. That claim was true and beside the point: `event:` is set by
    THE SAME SENDER as `data:` (`adapters/web_sse/app.py`'s
    `_event_stream` writes both from the same envelope on a healthy
    frame, but nothing downstream of that enforces they still agree once
    a frame is corrupted or truncated), so a corrupted or missing
    `event:` line is not evidence about whether `data:` is dangerous, it
    is silence. `sse.py`'s own parser leaves `event_type` as `None`
    whenever no `event:` line arrives at all (`sse.py`'s `feed`), and a
    single invalid byte inside the `event:` line's own bytes survives as
    a substituted U+FFFD rather than ending the stream, per F-4.2-RR-04's
    own "replace and keep going" recovery. Both shapes reached
    `_decode_stream_event` with an `event_type` that was never a member
    of `_KNOWN_EVENT_TYPES`, so the round-3 `event_type in
    _KNOWN_EVENT_TYPES` check silently classified the exact same fatal,
    malformed payload the control case (`event: error` intact) correctly
    rejects, as a benign, forward-compatible skip.

    This function reads `data`, the SAME bytes `Event.model_validate_json`
    already failed to validate, never `event:`. It returns `True` only
    when `data` is independent, positive proof that the frame is a
    well-formed envelope of a type this build has not been taught yet:
    valid JSON, a JSON object, carrying a string `type` key whose value
    is not in `_KNOWN_EVENT_TYPES`. That is exactly the additive,
    forward-compatible shape system-design-patterns rule 10 protects: a
    real new event type is well-formed JSON with an unrecognized `type`,
    not garbage.

    It returns `False`, the safe default, for everything else: `data`
    that is not valid JSON at all, that parses to something other than a
    JSON object, or an object with no string `type` key. `False` here
    means the caller cannot positively establish this frame is benign, so
    it is routed to `_synthesize_decode_failure_event` as a potential
    fatal instead. A false alarm there costs a spurious nonzero exit; a
    missed case costs a confident, cited answer that silently dropped a
    fatal frame, which is the asymmetry this function is built to resolve
    in the safe direction.
    """
    try:
        parsed = json.loads(data)
    except (ValueError, TypeError):
        return False
    if not isinstance(parsed, dict):
        return False
    declared_type = parsed.get("type")
    if not isinstance(declared_type, str):
        return False
    return declared_type not in _KNOWN_EVENT_TYPES

# The `trace_id` `_synthesize_decode_failure_event` stamps on a locally
# built `error` Event: a fixed literal, never derived from anything the
# server sent, so it is immediately recognizable in a log or a trace tool
# as client-manufactured rather than server-emitted.
_STREAM_DECODE_FAILURE_TRACE_ID = "cli-stream-decode-failure"


def _is_terminal_event(event: Event) -> bool:
    """True for a `done` event, or a fatal `error` event (F-4.2-A-12).

    A `done`.`error_class` other than "transient" or "recoverable" per
    `contracts/events.py`'s `ErrorPayload.error_class`, "unexpected" and
    "cancelled" are the two fatal values, `error.fatal` itself is a
    simpler, already-validated boolean the server sets for exactly this
    purpose, so this reads `event.payload["fatal"]` directly rather than
    re-deriving fatality from `error_class`. `event.payload` is the raw
    input dict `Event`'s own model validator already proved conforms to
    `ErrorPayload`, so the key is always present; `bool(...)` guards only
    against a value pydantic's lax bool coercion would accept (e.g. `1`)
    but the raw dict still carries un-coerced.
    """
    if event.type == "done":
        return True
    if event.type == "error":
        return bool(event.payload.get("fatal"))
    return False


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
        # F-4.2-A-10, narrowed at the round-3 fix (F-4.2-RR-03): the two
        # `stream_events` disclosures, reset at the start of every call.
        # `stream_skipped_frame_count` counts frames this call decoded but
        # discarded as BENIGN, i.e. an additive `type` value this build
        # has not been taught yet (system-design-patterns.md rule 10, an
        # unrecognized SSE `event:` field) rather than aborting the run
        # over one forward-compatible frame. It no longer counts a frame
        # whose `event:` field WAS one of the eleven known types but still
        # failed to decode: that shape is a genuine defect, not a
        # forward-compatibility gap, and is never silently counted here;
        # `_decode_stream_event` turns it into a fatal, rendered `error`
        # Event instead, so it surfaces through the normal error path
        # rather than through this counter. `stream_truncated` is a
        # distinct signal: it is set only when the LAST frame of the
        # stream, the one produced by a stream-end flush rather than a
        # normal blank-line dispatch, fails to decode, or when the
        # connection closed mid multi-byte UTF-8 character. A mid-stream
        # skip is "kept going"; a trailing decode failure is "the stream
        # ended mid-frame", a genuinely different shape a caller may want
        # to disclose differently.
        self.stream_skipped_frame_count: int = 0
        self.stream_truncated: bool = False

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

        `follow_redirects=False` is explicit here (F-4.2-A-29): the
        "exactly one HTTP request" guarantee this docstring and
        `TestCreateIsNeverRetried` both assert is only as real as the
        setting that controls it, and that setting otherwise lives
        outside this module, on whatever `httpx.AsyncClient` the caller
        injected. An injected client constructed with
        `follow_redirects=True` and a server that ever answered `POST
        /v1/query` with a 3xx would turn one CLI command into an
        unbounded chain of creates, each spending its own allowance
        slot, silently. Pinning it here means the guarantee holds
        wherever this method is called from, not only when the caller
        happened to construct its client a particular way.
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
            follow_redirects=False,
        )
        _raise_for_status(response)
        body = _parse_json_body(
            response, endpoint="create run", expected_statuses=frozenset({200, 201, 202})
        )
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

        Three fixes past the original T-4.2-03 shape, all filed by the
        adversary round against the merged branch:

            F-4.2-A-02: lines are split with `_ChunkSafeLineSplitter` over
            `aiter_bytes()`, never `aiter_lines()`, so a `data:` line
            carrying a raw U+2028, U+2029, or U+0085 character (ordinary
            in biomedical free text) is never cut in half. See this
            module's `_ChunkSafeLineSplitter` docstring.

            F-4.2-A-10, narrowed at the round-3 fix (F-4.2-RR-03): a frame
            whose SSE `event:` field is an additive `type` value this
            build has not been taught is SKIPPED rather than raised:
            `system-design-patterns.md` rule 10 makes a new event type an
            allowed additive v1 change, and a client that aborts a
            complete, otherwise-successful answer over one unrecognized
            frame is exactly the failure that rule exists to prevent.
            Skipped frames are counted on `self.stream_skipped_frame_count`
            rather than swallowed invisibly. A frame whose `event:` field
            IS one of the eleven types this build already knows, but whose
            envelope or payload still fails to decode (malformed JSON, or
            JSON that does not match the declared type's schema), is a
            DEFECT, not a forward-compatibility gap, and is no longer
            silently skipped: `_decode_stream_event` synthesizes a fatal
            `error` Event for it instead, so it renders, sets a nonzero
            exit code, and ends the stream exactly like a genuinely
            server-sent fatal error would. See `_decode_stream_event`'s
            own docstring for the full three-way split. A decode failure
            on the STREAM-END trailing flush is a different, genuine shape
            again (the connection ended mid-frame, not "the server sent
            one bad, complete frame") and is recorded separately on
            `self.stream_truncated`, never folded into either of the above.

            F-4.2-A-12: this method now ends the generator itself,
            immediately after yielding a `done` or a fatal `error`
            (`error_class` other than "transient" or "recoverable"),
            instead of relying on the server closing the HTTP response
            body. The prior shape made the "the CLI ends on a stopped
            run" guarantee the SERVER's rather than the client's; a
            server that ever held the connection open past a terminal
            event would hang this method for the full 45s stream read
            timeout. Ending locally, on the envelope's own terminal
            shape, is a client-side guarantee that holds regardless of
            what the transport does next.
        """
        headers = self._auth_headers()
        headers["Accept"] = "text/event-stream"
        if last_event_id is not None:
            headers["Last-Event-ID"] = last_event_id

        self.stream_skipped_frame_count = 0
        self.stream_truncated = False

        accumulator = _SseLineAccumulator()
        splitter = _ChunkSafeLineSplitter()
        async with self._http.stream(
            "GET",
            f"/v1/query/{run_id}/events",
            headers=headers,
            timeout=_STREAM_TIMEOUT,
        ) as response:
            if response.status_code >= 400:
                await response.aread()
                _raise_for_status(response)

            def _feed_and_decode(line: str) -> Event | None:
                # A normal, blank-line-terminated dispatch, whether it
                # arrives mid-stream or among `splitter.close()`'s
                # leftover complete lines: always `is_trailing=False`.
                # Only `accumulator.flush()`'s own result (below) can be
                # the OTHER kind, an event with no closing blank line at
                # all.
                parsed = accumulator.feed(line)
                if parsed is None:
                    return None
                return self._decode_stream_event(parsed, is_trailing=False)

            async for raw_bytes in response.aiter_bytes():
                for line in splitter.feed(raw_bytes):
                    event = _feed_and_decode(line)
                    if event is None:
                        continue
                    yield event
                    if _is_terminal_event(event):
                        return
            for line in splitter.close():
                event = _feed_and_decode(line)
                if event is None:
                    continue
                yield event
                if _is_terminal_event(event):
                    return
            if splitter.truncated_utf8:
                self.stream_truncated = True
            trailing = accumulator.flush()
            if trailing is not None:
                event = self._decode_stream_event(trailing, is_trailing=True)
                if event is not None:
                    yield event

    def _decode_stream_event(
        self, parsed: tuple[str | None, str, str | None], *, is_trailing: bool
    ) -> Event | None:
        """Decode one SSE tuple into an `Event`, or return `None`/a
        synthesized fatal `Event` and record the failure appropriately
        (F-4.2-A-10, hardened at the round-3 fix F-4.2-RR-03, and again at
        the round-4 fix F-4.2-D-02).

        Three distinct outcomes, not two, since round 2's own fix
        collapsed a case that needed to stay separate:

            1. `is_trailing=True` (the stream ended without a closing
               blank line): unchanged from F-4.2-A-10/F-4.2-A-16.
               `stream_truncated = True`, `None` returned. This is a
               transport-level truncation, not "the server sent one bad,
               complete frame and kept going", and it is deliberately NOT
               folded into the fatal-synthesis path below: a stream that
               ends here has, by definition, nothing after it in the SAME
               connection that could go on to report a false clean
               success, and `Renderer.finish()` already defaults to a
               nonzero exit whenever no terminal event ever reached it,
               which is exactly this shape.
            2. `is_trailing=False` and `_payload_declares_unknown_type(data)`
               is `True`: `data` itself, independent of the SSE `event:`
               field, is positive proof of a well-formed envelope of an
               additive, not-yet-taught type (system-design-patterns rule
               10). Benign. Skipped and counted on
               `stream_skipped_frame_count`.
            3. `is_trailing=False` and `_payload_declares_unknown_type(data)`
               is `False`: `data` offers no positive proof of being
               benign, either because it fails to parse as JSON at all,
               parses to something other than an object, has no string
               `type` key, or DOES carry a `type` that is a member of
               `_KNOWN_EVENT_TYPES` but still failed envelope or payload
               validation. Every one of these is a genuine defect, not a
               forward-compatibility gap, so it is no longer silently
               skipped: a locally synthesized fatal `error` Event is
               returned instead (`_synthesize_decode_failure_event`),
               routed through the SAME `Event`/`ErrorPayload` models and
               the same `render.py`/`_is_terminal_event` machinery every
               genuinely server-sent fatal error already uses, so this
               frame renders an actionable message, sets a nonzero exit
               code, and ends the stream, exactly like a frame that
               explicitly claimed `type: "error"` always has.

        The classification deliberately never reads the SSE `event:`
        field (`event_type` below is passed to
        `_synthesize_decode_failure_event` only for the human-readable
        message, never for this decision). F-4.2-D-02: `event:` is
        written by the same sender as `data:`, so it can be missing
        (`sse.py` leaves `event_type` as `None` when no `event:` line
        arrives) or corrupted independently of whatever `data:` actually
        contains (a single invalid byte inside `event:`'s own bytes
        survives as a substituted U+FFFD per F-4.2-RR-04's "replace and
        keep going" recovery, rather than ending the stream). Keying the
        skip-or-fail decision on that field let the exact same fatal,
        malformed payload the control case (`event: error` intact)
        correctly rejects slip through as a benign skip whenever
        `event:` was merely absent or garbled, letting a later
        well-formed `done` report a false clean success. See
        `_payload_declares_unknown_type`'s own docstring for the full
        account.
        """
        event_type, data, seq_id = parsed
        try:
            return Event.model_validate_json(data)
        except ValidationError:
            if is_trailing:
                self.stream_truncated = True
                return None
            if _payload_declares_unknown_type(data):
                self.stream_skipped_frame_count += 1
                return None
            return self._synthesize_decode_failure_event(event_type, seq_id)

    def _synthesize_decode_failure_event(
        self, claimed_type: str | None, seq_id: str | None
    ) -> Event:
        """Builds a fatal, run-scoped `error` Event LOCALLY, never
        received from the server, for a frame whose `data:` body could
        not be positively established as benign
        (`_payload_declares_unknown_type` returned `False`) after
        `Event.model_validate_json` already failed on it (F-4.2-RR-03,
        re-scoped at F-4.2-D-02).

        `claimed_type` is the SSE `event:` field exactly as `sse.py`
        parsed it (`None` when no `event:` line arrived at all, or a
        garbled value if the line's own bytes were corrupted and
        recovered via F-4.2-RR-04's U+FFFD substitution): it is used
        ONLY to make the rendered message more specific when the server
        did send a recognizable label, never to decide whether this
        method gets called in the first place. That decision already
        happened in `_decode_stream_event`, from `data:` alone
        (F-4.2-D-02). A caller must not read this parameter as
        trustworthy provenance; it is display text, not evidence.

        `error_class="transient"` is a deliberate choice, not the more
        obvious `"unexpected"`: `render.py`'s own fixed disclosure table
        (`_CLI_FATAL_ERROR_DISCLOSURE`) renders actionable copy for
        `"transient"` ("Run 's3 ask' again to start a new attempt"),
        while `"unexpected"`'s copy names no next step at all. Whether
        the exit code goes nonzero does not depend on this choice either
        way: `fatal=True` alone already forces it, per `render.py`'s
        `_handle_error` (`if payload.fatal or ...`). Choosing the
        disclosure that tells the user what to do next, when either
        choice sets the same exit code, is what
        `tool-call-budgets.md`'s "an error message must say what to do
        next" already asks for.

        `message` is set for completeness and for any caller that reads
        the raw `Event` directly (this module's own tests, for example),
        even though `render.py`'s `_handle_error` never renders
        `ErrorPayload.message` verbatim for any error, synthesized or
        server-sent (see that module's own `_CLI_FATAL_ERROR_DISCLOSURE`
        comment for why); the rendered line comes entirely from the
        fixed `"transient"` disclosure copy plus `source`, both already
        safe to display.
        """
        try:
            seq = int(seq_id) if seq_id is not None else 0
        except ValueError:
            seq = 0
        seq = max(seq, 0)
        # `None` (no `event:` line arrived) gets its own label rather
        # than rendering the literal text "None": both are display-only,
        # neither changes whether this method was ever called.
        type_label = repr(claimed_type) if claimed_type is not None else "<no event: field>"
        payload = ErrorPayload(
            fatal=True,
            scope="run",
            source="cli_stream_decode",
            error_class="transient",
            message=(
                f"the server sent a {type_label} event that this client "
                "could not decode; the run cannot be trusted to have "
                "completed as reported."
            )[:256],
            retry_after_s=0,
        )
        return Event(
            type="error",
            version="v1",
            trace_id=_STREAM_DECODE_FAILURE_TRACE_ID,
            seq=seq,
            ts=datetime.now(UTC),
            payload=payload.model_dump(),
        )

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
        body = _parse_json_body(response, endpoint="stop", expected_statuses=frozenset({200}))
        return bool(body["stopped"])

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
        body = _parse_json_body(
            response, endpoint="fetch citations", expected_statuses=frozenset({200})
        )
        self.citations_run_cancelled = response.headers.get("x-run-cancelled") == "true"
        self.citations_export_truncated = (
            response.headers.get("x-citations-export-truncated") == "true"
        )
        return [CitationPayload.model_validate(item) for item in body]
