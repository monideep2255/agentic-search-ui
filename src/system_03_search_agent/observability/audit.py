"""T-5.0-02: the append-only tool-call audit log, tech spec Section 20.3.

Depends on:
    - system_03_search_agent.observability.config (audit_log_path,
      audit_enabled). Env values are read once, at that module's boundary,
      never re-read here.

Reads:
    - Nothing beyond config's two functions above.

Writes:
    - The audit sink `audit_log_path()` names, default
      `logs/tool_audit.jsonl`. Append-only. A written line is never
      rewritten, truncated or otherwise mutated by anything in this module.

## Why this is a transport-layer concern, not a caller-layer one

Section 20.3 requires `trace_id`, HTTP status and latency in milliseconds
on every line. `trace_id` is a run-scoped value with no natural home at a
transport call, which has no run in scope. HTTP status and latency are the
opposite: they exist only where the response actually lands, which is the
transport, not any of the seven tool wrappers above it (each of which
classifies a numeric status down to `ok|empty|error` before returning, per
`tracker/phase_5.0.md`'s finding two). A `ContextVar` is what lets a value
with run-scoped lifetime reach a call site with no run-scoped argument, in
either direction: this module supplies the piece the transport cannot hold
on its own, and leaves the piece the transport already has (status,
latency, endpoint, params) to be passed in directly by the caller building
each ticket's transport hook (T-5.0-05).

## Append-only, one handle per write

Each write opens the file, appends one line, and closes it, rather than
holding one handle open for the life of the process. A single long-lived
handle survives external log rotation as a dangling reference to a deleted
inode and keeps writing into nothing forever; opening fresh each time means
a rotated-in file is picked up on the very next line with no restart and no
signal handler. This module owns no process-lifecycle hook to close a
handle on shutdown either, so a per-write open is also the only shape that
needs no such hook. The cost, one extra open/close syscall pair per tool
call, is negligible next to a live HTTPS or graph round trip.

A module-level `threading.Lock` serializes every write. `open(..., "a")`
gives POSIX callers atomic appends only up to the platform pipe-buffer
size and gives no such guarantee at all on every platform this project
might run on; the lock removes the dependency on that guarantee rather
than relying on it, which is what Section 20.3's "one writer per process"
line actually asks for.

## Best-effort by construction

Matches `feedback/writer.py`'s discipline exactly: audit failure must
never propagate to the caller, because a tool call that already reached a
live NCBI host or the graph must not be failed a second time by its own
bookkeeping. `record_tool_call` never raises. On failure it logs the
exception's CLASS NAME only, never `str(exc)`: a driver or client
exception can carry a DSN, an API key, or a connection string in its
message text, and Section 16 and the production-standards secrets gate
both apply here exactly as they do to the interactions writer.
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.parse
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from system_03_search_agent.observability.config import audit_enabled, audit_log_path

__all__ = [
    "current_trace_id",
    "record_tool_call",
    "redact_params",
    "reset_trace_id",
    "set_trace_id",
    "trace_id_scope",
]

logger = logging.getLogger(__name__)

#: The placeholder a redacted value is replaced with. A constant string
#: rather than something derived from the original value, since the whole
#: point is that nothing derived from a secret ever reaches the line.
REDACTED_PLACEHOLDER = "[REDACTED]"

#: Category match, not an enumerated key list (this ticket's own
#: instruction): a key name is treated as secret-ish if it CONTAINS any of
#: these substrings, case-insensitively, regardless of nesting depth or
#: what the calling tool happens to name its own parameters today. This is
#: deliberately broad. "author" contains "auth" and gets redacted too; a
#: false positive here costs a placeholder in a log line, and a false
#: negative costs a live credential in an append-only file that is never
#: rewritten. The asymmetry is the whole reason this is substring matching
#: rather than an exact-name allowlist.
_SECRET_KEY_MARKERS: tuple[str, ...] = (
    "key",
    "token",
    "secret",
    "password",
    "credential",
    "auth",
    "dsn",
    "connection",
)

#: Cap on the SERIALIZED, already-redacted params, in UTF-8 bytes. One
#: oversized retrieved or returned payload must not blow up a log line or
#: crowd out the rest of the record (tool-call-budgets.md's bounded-context
#: principle, applied here to an audit line instead of a model prompt).
_MAX_PARAMS_BYTES = 4096

#: One writer per process (Section 20.3, stated explicitly). Guards every
#: append so two concurrent tool calls can never interleave their lines or
#: leave a partially written one for a third to land inside.
_write_lock = threading.Lock()

#: Run-scoped trace_id, reaching call sites (the transport layer) that have
#: no run argument to carry it through. Unset by default: a caller with no
#: run in scope, such as s3-kgx-export, gets None back rather than a
#: fabricated id, and the recorded line carries a genuine null instead of
#: a value nobody minted.
_trace_id_var: ContextVar[str | None] = ContextVar("audit_trace_id", default=None)


def set_trace_id(trace_id: str | None) -> Token[str | None]:
    """Bind the current run's trace_id for every audit line written from here on.

    Returns the token `reset_trace_id` needs to restore the previous value.
    Prefer `trace_id_scope` over calling this directly: a bare set with no
    matching reset leaks the value into whatever runs next on this context,
    which for a ContextVar can mean a later, unrelated request on the same
    thread or task.
    """
    return _trace_id_var.set(trace_id)


def reset_trace_id(token: Token[str | None]) -> None:
    """Undo one `set_trace_id` call, restoring the value it overrode."""
    _trace_id_var.reset(token)


@contextmanager
def trace_id_scope(trace_id: str | None) -> Iterator[None]:
    """Bind trace_id for the duration of the `with` block, then restore it.

    The one entry point a run should actually use. Set-then-reset by hand
    is exposed above for a caller with a shape a context manager cannot fit
    (a manual try/finally spanning a callback boundary), but every ordinary
    call site should prefer this.
    """
    token = set_trace_id(trace_id)
    try:
        yield
    finally:
        reset_trace_id(token)


def current_trace_id() -> str | None:
    """The trace_id bound by the innermost enclosing `trace_id_scope`, or None."""
    return _trace_id_var.get()


def _is_secret_key(key: Any) -> bool:
    """Whether a params key name matches the secret-ish category, not a specific name."""
    if not isinstance(key, str):
        return False
    lowered = key.lower()
    return any(marker in lowered for marker in _SECRET_KEY_MARKERS)


def _redact_netloc(netloc: str) -> str:
    """Blank a connection-string password living in a URL's userinfo segment.

    `user:password@host:port` is the shape, and the password half is
    sensitive by definition, not because its own name matches a marker.
    Unlike the query-string case below, nothing here checks
    `_SECRET_KEY_MARKERS` before redacting: there is no key name attached to
    a netloc password to check against, only its position. A bare username
    with no password (`user@host`, no colon) carries nothing to redact and
    is left alone.
    """
    if "@" not in netloc:
        return netloc
    userinfo, _, hostpart = netloc.rpartition("@")
    if ":" not in userinfo:
        return netloc
    user, _, _password = userinfo.partition(":")
    return user + ":" + REDACTED_PLACEHOLDER + "@" + hostpart


def _redact_query(query: str) -> str:
    """Replace the value of any secret-ish-NAMED query parameter.

    Reuses `_is_secret_key` (and therefore `_SECRET_KEY_MARKERS`) rather
    than a second, separately maintained marker list, per F-5.0-08's
    instruction: the key-name rule and this value-level rule must not be
    able to drift into two different definitions of "secret". A parameter
    whose name does not match passes through with its original value.
    """
    if not query:
        return query
    pairs = urllib.parse.parse_qsl(query, keep_blank_values=True)
    redacted_pairs = [
        (key, REDACTED_PLACEHOLDER if _is_secret_key(key) else value) for key, value in pairs
    ]
    return urllib.parse.urlencode(redacted_pairs)


def _redact_value_string(value: str) -> str:
    """Scan a single string leaf for a credential riding inside a URL or DSN.

    F-5.0-08: a key-name rule alone cannot see `_append_api_key`'s
    `api_key=` query parameter once it is embedded in a URL held under an
    innocuous key such as `endpoint`. This is the category fix: not a list
    of known secret-carrying URLs, but a structural read of any string that
    is shaped like `scheme://...`, redacting whatever sits in the two
    places a credential actually rides (a netloc password, a secret-ish
    query parameter) and leaving everything else, scheme, host, path,
    non-secret query, byte-identical.

    Only strings containing "://" are inspected at all, since anything else
    cannot be this shape. `urlsplit` never raises on a plain string, so no
    exception handling is needed here; a string that merely contains "://"
    without being real URL/DSN syntax fails the `scheme and netloc` check
    below and is returned untouched. When nothing in the string actually
    needed redacting, the ORIGINAL string is returned rather than a
    reserialized one, since `urlencode`'s percent-encoding style need not
    match the caller's, and a value with nothing to hide should never come
    back byte-different from what it went in as.
    """
    if "://" not in value:
        return value
    parsed = urllib.parse.urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return value
    netloc = _redact_netloc(parsed.netloc)
    query = _redact_query(parsed.query)
    if netloc == parsed.netloc and query == parsed.query:
        return value
    return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path, query, parsed.fragment))


def redact_params(value: Any) -> Any:
    """Recursively replace any secret-ish-keyed value, or embedded secret, with a placeholder.

    Walks dicts and lists to any depth. Two independent rules apply, in
    this order, so the second can never re-expose what the first already
    hid:

    1. Key-name rule: a dict key matching the category in
       `_SECRET_KEY_MARKERS` has its ENTIRE value replaced, whatever shape
       that value is (a string, a nested dict, a list), because a value
       under a key named `credentials` might itself be a structure carrying
       more than one secret, and redacting only a leaf inside it would
       still leak the rest.
    2. Value-scanning rule (F-5.0-08): a string value that SURVIVES rule 1,
       because its key name was innocuous, is itself inspected for a
       credential embedded in a URL query parameter or a connection-string
       password (`_redact_value_string`). This is the case a key-name rule
       structurally cannot see: `_append_api_key` in `ncbi_transport.py`
       appends the NCBI API key to a query string, so a field named
       `endpoint` or `url` can carry the credential with no secret-ish key
       anywhere above it.

    Non-dict, non-list, non-string leaves (numbers, booleans, None) pass
    through unchanged.

    This is a pure function with no knowledge of the size cap or the
    disclosure marker below; `record_tool_call` composes it with both.
    """
    if isinstance(value, dict):
        return {
            key: (REDACTED_PLACEHOLDER if _is_secret_key(key) else redact_params(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_params(item) for item in value]
    if isinstance(value, str):
        return _redact_value_string(value)
    return value


def _bounded(redacted: Any) -> Any:
    """Cap the serialized size of an already-redacted params value.

    Applied AFTER redaction, never before: redacting a value that has
    already been truncated could redact a fragment of a secret while
    leaving the rest, which is worse than either redacting the whole thing
    or not touching it at all.

    A payload over the cap is not silently shortened. This repository's
    standing rule is that a system dropping or shortening something
    discloses that it did, so the oversized value is replaced with a marker
    object naming what happened and how large the payload actually was,
    rather than a truncated fragment that reads as complete.
    """
    try:
        serialized = json.dumps(redacted, default=str)
    except (TypeError, ValueError):
        # A value this module cannot serialize at all (a non-JSON-able
        # object slipping through as a leaf) is exactly as reportable as an
        # oversized one: name what happened, never raise.
        return {
            "_audit_note": "params could not be serialized and were dropped",
        }
    encoded_len = len(serialized.encode("utf-8"))
    if encoded_len <= _MAX_PARAMS_BYTES:
        return redacted
    return {
        "_audit_note": "params exceeded the audit log size cap and were dropped",
        "_audit_original_bytes": encoded_len,
        "_audit_cap_bytes": _MAX_PARAMS_BYTES,
    }


def _utc_timestamp() -> str:
    """The current instant, UTC, ISO 8601, always carrying an explicit offset."""
    return datetime.now(UTC).isoformat()


def _append_line(path: Path, line: str) -> None:
    """The one place a byte is written to the audit sink.

    Opens, writes exactly one line terminated by exactly one newline,
    closes. See the module docstring for why this reopens per write rather
    than holding a handle, and why the lock is what actually guarantees no
    interleaving rather than the platform's append-mode behaviour.
    """
    with _write_lock, path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.write("\n")


def record_tool_call(
    *,
    tool: str,
    layer: int,
    endpoint: str,
    latency_ms: float,
    authorization: str = "none",
    params: Mapping[str, Any] | None = None,
    record_ids: Sequence[Any] | None = None,
    http_status: int | None = None,
    error: str | None = None,
) -> None:
    """Append one Section 20.3 audit line for a single Layer 1/2/3 access.

    Writes nothing at all when `audit_enabled()` is False, checked first
    and before any other work, so the disabled path costs one function call
    and touches the filesystem not at all.

    Args:
        tool: the tool or caller name (for example "cypher_query",
            "ncbi_efetch", or the KGX export traversal that bypasses the
            tool layer entirely).
        layer: 1, 2, or 3, naming which of the three data-access layers
            this call reached (system-design-patterns.md pattern 3).
        endpoint: the endpoint or database called (a URL path, an NCBI
            db name, or the graph database name).
        latency_ms: wall-clock time the call took, measured by the
            transport that holds the actual request, never estimated here.
        authorization: the NAME of the credential used, for example
            "ncbi_api_key", "kg_reader", or "none". Never the credential
            value itself (PRD: every Layer 2/3 access logged with its
            authorization, by identifier, never by value).
        params: the call's parameters, redacted by category and size
            capped before they are written. May be None or empty.
        record_ids: identifiers the call returned, for example a list of
            NCBI UIDs or graph node ids. May be None, recorded as an empty
            list.
        http_status: the numeric HTTP status, or None for a call with no
            HTTP semantics (a graph query, an FTP transfer) or a
            body-level failure E-utilities reports with no status code at
            all (Section 20.3's own "empty signal for E-utilities" case).
        error: a short error string, or None for a call that succeeded.
        trace_id is not a parameter here: it is read from the ContextVar
        this module owns, via `current_trace_id()`, so every caller in a
        given run threads the same value with no argument to remember to
        pass. A caller with no run in scope, such as s3-kgx-export, simply
        never bound one, and the line records null.

    Never raises. A failure at any point, including a path that cannot be
    created and a value that cannot be serialized, is caught, logged by
    exception CLASS NAME only, and swallowed: an audit failure must never
    fail the tool call it is describing (production-standards' retry-safety
    gate and Section 16's best-effort principle, applied here the same way
    `feedback/writer.py` applies them to the interactions table).
    """
    if not audit_enabled():
        return
    try:
        entry: dict[str, Any] = {
            "trace_id": current_trace_id(),
            "timestamp": _utc_timestamp(),
            "tool": tool,
            "layer": layer,
            "endpoint": endpoint,
            "authorization": authorization,
            "params": _bounded(redact_params(dict(params) if params else {})),
            "record_ids": list(record_ids) if record_ids is not None else [],
            "http_status": http_status,
            "error": error,
            "latency_ms": latency_ms,
        }
        line = json.dumps(entry, default=str)
        path = audit_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        _append_line(path, line)
    except Exception as exc:  # noqa: BLE001 - a best-effort write must catch any failure mode
        logger.warning(
            "tool-call audit write failed for tool=%s (%s)",
            tool,
            type(exc).__name__,
        )
