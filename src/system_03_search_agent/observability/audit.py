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

## The lock and the field caps are ONE control, not two

Read those two words literally, because this paragraph replaces two
earlier ones that each described its half as if it stood alone, and the
gap between them was measured (A-5.0-19).

A `threading.Lock` is per-PROCESS. Two PROCESSES on one sink is ordinary
use here, not a hypothetical: `s3-kgx-export` is a separate CLI process
that reaches the graph through the same audited chokepoint and resolves
the same default `logs/tool_audit.jsonl`, and any multi-worker uvicorn
configuration is a third. Four processes writing 1200 short lines
produced 1200 intact lines and zero unparseable ones; the same four
writing 20 KB lines produced 924 lines and 251 unparseable ones, permanent
damage in a file that by contract is never rewritten.

What separates those two runs is LINE SIZE and nothing else. Below the
platform text-buffer size, roughly 8 KB, one `write` call reaches the
kernel and POSIX `O_APPEND` keeps it whole across processes; above it,
Python emits several syscalls and they interleave. So the lock covers
threads within a process, and the SIZE CAPS are what cover processes,
by keeping every line inside the size where the kernel's own guarantee
holds. Neither is sufficient alone, and weakening either one silently
removes half of a single guarantee.

That is why `_MAX_LINE_BYTES` exists as a whole-line bound rather than as
arithmetic over the per-field caps stated in a comment. Per-field caps
that happen to sum to something under the buffer today are a sentence
about the code, not a check in it, and this repository has shipped four
defects that were exactly that (build phase 4.15). The whole-line bound
holds even after a field is added, widened, or its cap is changed.

## Never raises AND always records

Two guarantees, not one, and they were not always both true. The module
promised the first and the second was assumed to follow from it
(A-5.0-05). It did not: one value `json.dumps` refuses removed the entire
line, leaving a `logger.warning` and nothing in the file. For an audit
sink that is the worse failure of the two, because an absent line is
indistinguishable from the call never having happened, and the file is
append-only so nothing can be added later to correct it.

Every field is therefore reduced to something writable rather than
allowed to fail: a value that cannot be converted becomes
`_UNREPRESENTABLE_PLACEHOLDER` (`_stringify_leaf`), a value too large is
dropped with a disclosure (`_bounded`, `_bounded_text`), a line too large
is reduced (`_bounded_line`), and a line that cannot be serialized at all
still gets written in a degraded form (`_degraded_line`). One policy at
four points on the same path: name what was lost, write the line.

## Best-effort by construction

Matches `feedback/writer.py`'s discipline exactly: audit failure must
never propagate to the caller, because a tool call that already reached a
live NCBI host or the graph must not be failed a second time by its own
bookkeeping. `record_tool_call` never raises. On failure it logs the
exception's CLASS NAME only, never `str(exc)`: a driver or client
exception can carry a DSN, an API key, or a connection string in its
message text, and Section 16 and the production-standards secrets gate
both apply here exactly as they do to the interactions writer.

## Why the error field is a code, not a message

Three consecutive rounds of this phase (F-5.0-13, F-5.0-14, F-5.0-19)
tried to make a string scanner safe enough to let a caught exception's
message reach this append-only sink. Each round passed its own tests and
was then defeated by an input of the same family: something upstream of
the credential consumed it before it was ever scanned. Build phase 4.14
recorded the durable lesson that this phase then reproduced three more
times, when a check keeps losing to inputs of the same shape, stop
hardening the check and change what it is checking.

So the error field no longer accepts free text at all. It accepts a code
drawn from `AUDIT_ERROR_CODES`, a closed vocabulary defined below, plus
optionally the exception's CLASS NAME. The distinction that makes this
structural rather than another scanner is the one `feedback/writer.py`
already relies on: an exception's class name is chosen by the code that
declares it, while an exception's message is assembled from data, which
in this system means URLs, DSNs and response bodies that carry
credentials.

## The two halves are not bounded to the same degree

Stated because the sentence that used to sit here said they were, and it
was false in the dangerous direction (F-5.0-21). Build phase 4.15's
durable lesson is that the fix for a confident sentence describing a
check that is not there is deletion plus a test, never a better sentence.

The closed vocabulary IS a complete bound. A value that is not a member
is discarded, so nothing derived from data has a path through it.

`str.isidentifier()` is NOT a bound of that kind. It is a SHAPE guard: it
excludes every character a URL, a DSN or a query-string assignment needs,
which is what makes an exception MESSAGE unspellable as a class name, and
it does not exclude a bare alphanumeric token, which is the shape of an
opaque API key. Measured on this branch: `"a" + uuid.uuid4().hex` is 33
characters and `isidentifier()` returns True, and the check accepts the
full Unicode ID_Start range, so a Cyrillic-led token passes too.
`_MAX_ERROR_CLASS_CHARS` bounds length and nothing else.

What keeps a credential out of `error_class` today is therefore the
CALLER, not the guard: both shipped call sites pass `type(exc).__name__`,
a source-code literal rather than data. That guarantee is pinned where it
actually lives rather than asserted here, by
`test_audit.TestErrorClassCallSitesPassAClassNameLiteral`, which parses
both modules and turns red the moment a `record_tool_call` call site
passes anything else. The guard behind it is what stops a wrong caller
writing a URL or a message; it is not the reason the field is safe.

A value that is not in the vocabulary FAILS CLOSED to `unexpected`
(`UNEXPECTED_ERROR_CODE`) rather than being passed through. A permissive
fallback here would reintroduce exactly the hole this design removes, so
there is deliberately no way for a caller to widen the vocabulary at a
call site.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from system_03_search_agent.observability.config import audit_enabled, audit_log_path

__all__ = [
    "AUDIT_ERROR_CODES",
    "UNEXPECTED_ERROR_CODE",
    "classify_error_code",
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

#: Cap on the SERIALIZED, already-redacted `params` value, in UTF-8 bytes.
#: One oversized retrieved or returned payload must not blow up a log line
#: or crowd out the rest of the record (tool-call-budgets.md's
#: bounded-context principle, applied here to an audit line instead of a
#: model prompt). It briefly also covered the `error` field, between
#: F-5.0-13's fix and this design change; the error half is now bounded by
#: its own vocabulary rather than by a size cap, so `params` is the only
#: field a cap can still apply to.
_MAX_PARAMS_BYTES = 4096

#: Cap on each already-redacted TEXT field, in UTF-8 bytes: `tool`,
#: `endpoint`, `authorization` and `trace_id`. A-5.0-03: every one of these
#: reached the append-only line verbatim, with no redaction and no bound of
#: any kind, which made the sink itself exactly as defenceless as the day
#: F-5.0-08 was filed as a critical. That finding was closed CALLER-side,
#: at one of three chokepoints, so the other two and every future caller
#: were one careless argument away from reproducing it. 256 bytes sits far
#: above any endpoint path, tool name or credential NAME this system uses,
#: and far below the line budget below.
_MAX_TEXT_FIELD_BYTES = 256

#: `maxItems` and a size cap for `record_ids` (A-5.0-04). This is the one
#: field on the line whose contents are by design whatever a third party
#: returned, which `.claude/rules/ai-security-standards.md` classifies as
#: untrusted external content by name, and it had the fewest controls of
#: any field on the line: `list(record_ids)` and nothing else.
_MAX_RECORD_IDS = 256
_MAX_RECORD_IDS_BYTES = 2048

#: THE WHOLE-LINE BOUND, in UTF-8 bytes, and the half of the append-only
#: guarantee that covers other PROCESSES (A-5.0-19; see the module
#: docstring section "The lock and the field caps are ONE control"). Set
#: below the roughly 8 KB platform text-buffer size at which Python stops
#: emitting one `write` per line and concurrent appends begin interleaving.
#: A whole-line check rather than arithmetic over the per-field caps
#: because a sum stated in a comment is a sentence about the code rather
#: than a check in it, and it stops being true the moment a field is added
#: or widened.
_MAX_LINE_BYTES = 7168

#: The code recorded when a caller supplies anything this module does not
#: recognize. Named separately from the tuple below so a caller and a test
#: can both refer to the fail-closed outcome without spelling it.
UNEXPECTED_ERROR_CODE = "unexpected"

#: THE CLOSED VOCABULARY. The only values that may ever reach the audit
#: line's `error_code` field. Closed rather than open because the whole
#: point of this design is that the field's contents are chosen by code
#: rather than derived from data: an enumerated set has no path a
#: credential can travel down, and a free string has several, all three of
#: which this phase measured (F-5.0-13, F-5.0-14, F-5.0-19).
#:
#: Which codes have a producer TODAY, stated rather than implied so a
#: reader does not assume every member is exercised:
#:
#: - `timeout`, `connection`, `auth`: raised by `graph_connection`'s typed
#:   GraphError family and by `ncbi_transport`'s TransportError family.
#: - `rate_limited`: `TransportRateLimitedError` and, over the HTTPS graph
#:   transport, `graph_http_transport.GraphRateLimitedError`.
#: - `unexpected`: the fail-closed outcome, and the mapping for a bare
#:   base-class exception that no more specific rule claimed.
#: - `http_error` and `empty`: reserved for Section 20.3's "body-level
#:   error and empty signal" case, which today is classified inside the
#:   action modules above the transport (`classify_eutils_response`,
#:   `classify_status_coded_response`) and never reaches a chokepoint as
#:   an exception. They are declared here so the action layer has a code
#:   to use when it is wired, not because a chokepoint emits them now.
AUDIT_ERROR_CODES: tuple[str, ...] = (
    "timeout",
    "connection",
    "auth",
    "rate_limited",
    "http_error",
    "empty",
    UNEXPECTED_ERROR_CODE,
)

#: Cap on a recorded exception class name. A real class name is a short
#: Python identifier; this bounds a caller that passes something else
#: entirely, so the field cannot become a channel for bulk text. It bounds
#: LENGTH and nothing else: at 128 it sits far above every credential this
#: system handles, so it is not a second bound on secrecy (F-5.0-21).
_MAX_ERROR_CLASS_CHARS = 128

#: The exact scalar types `json.dumps` serializes from the VALUE rather
#: than by calling `str()` on it. Exact types via `type(...) is`, not
#: `isinstance`, and the difference is the whole point: a subclass of one
#: of these is not guaranteed to take the same encoder path, so it is
#: routed through the stringify-then-redact branch instead of being
#: trusted. See `_stringify_leaf` for the ordering defect this closes.
_JSON_NATIVE_SCALARS: tuple[type, ...] = (bool, int, float)

#: What replaces a value this module could not turn into text at all. It
#: DISCLOSES the substitution rather than dropping the field or the line:
#: this repository's standing rule is that a system dropping something says
#: so, and in an append-only sink a silent omission can never be corrected
#: afterwards.
_UNREPRESENTABLE_PLACEHOLDER = "[unrepresentable value]"

#: What is recorded when `error_class` is present but is not a plain
#: identifier. A constant rather than silence, because this repository's
#: standing rule is that a system dropping something says that it did;
#: it carries no part of the refused value.
_REFUSED_ERROR_CLASS = "[not-an-identifier]"

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


def classify_error_code(value: Any) -> str | None:
    """Reduce a caller-supplied error code to the closed vocabulary, or fail closed.

    Three outcomes, and there is deliberately no fourth:

    - `None` in, `None` out. A call that succeeded records no code, and
      routing None through the vocabulary check would turn a success into
      an `unexpected` failure.
    - A member of `AUDIT_ERROR_CODES` is recorded as the VOCABULARY
      MEMBER, not as the caller's object (F-5.0-22). The two are equal by
      definition when the caller passed a plain `str`, so this changes
      nothing for a real caller and removes a class of problem for a
      hostile one.
    - EVERYTHING ELSE becomes `UNEXPECTED_ERROR_CODE`. Not the value, not
      a truncated or redacted form of the value, not a scanned form of the
      value: the value is discarded entirely and never touches the line.

    That last branch is the whole design. It is what makes this a
    structural bound rather than a fourth attempt at a scanner: a caller
    that passes `str(exc)`, a URL, a DSN or a response body gets
    `unexpected` written, so no amount of hostile message text has a path
    to the append-only sink. It also means a legitimate but MISSPELLED
    code is silently downgraded rather than recorded, which is the correct
    trade when the alternative is a credential in a file that is never
    rewritten. The enumerating tests in `test_audit.py` are what catch a
    misspelling, at build time rather than at read time.

    `type(value) is str` rather than `isinstance` (F-5.0-22): tuple
    containment evaluates `value.__eq__(member)`, so a `str` subclass
    overriding `__eq__` was measured being admitted and then returned
    VERBATIM, writing a value that is in no vocabulary at all. An exact
    type test is the one check a subclass cannot override, and returning
    the matched member rather than the caller's object closes the same
    hole from the other side.
    """
    if value is None:
        return None
    if type(value) is str:
        for code in AUDIT_ERROR_CODES:
            if value == code:
                return code
    return UNEXPECTED_ERROR_CODE


def _safe_error_class(value: Any) -> str | None:
    """Admit an exception CLASS NAME, refuse anything that is not one.

    A class name is developer-controlled: it is written in a `class`
    statement, never assembled from a URL, a response body or a driver's
    message text. `feedback/writer.py` already relies on exactly this
    distinction, logging `type(exc).__name__` and never `str(exc)`, and
    this module's own failure handler does the same.

    `str.isidentifier()` is the check because it is the same rule Python
    itself applies to a class name, and it structurally excludes every
    character a credential needs to travel: no `=`, no `:`, no `/`, no
    `@`, no `?`, no `&`, no whitespace and no quote can appear in an
    identifier, so neither a query-string assignment nor a DSN's userinfo
    segment can be spelled as one.

    What it does NOT exclude is a bare alphanumeric token, the shape of an
    opaque API key: this is a SHAPE guard, not a secrecy guard (F-5.0-21).
    The length cap bounds bulk text only. The module docstring above names
    what the field's safety actually rests on, and the arm that pins it.

    `type(value) is str` rather than `isinstance` (F-5.0-22): both bounds
    below are `str` METHODS, and a subclass whose `isidentifier()` returns
    True and whose `__len__` returns 4 was measured being returned
    verbatim carrying `=`, `:`, `/` and `?`, the exact character class the
    paragraph above says an identifier cannot contain. An exact type test
    is the one check a subclass cannot override, so it stands in front of
    the two it can.
    """
    if value is None:
        return None
    if (
        type(value) is str
        and len(value) <= _MAX_ERROR_CLASS_CHARS
        and value.isidentifier()
    ):
        return value
    return _REFUSED_ERROR_CLASS


def _plain_str(value: str) -> str:
    """The real character data of a `str`, with no subclass method consulted.

    A-5.0-01: F-5.0-22 closed the `str`-subclass family at two guards by
    replacing `isinstance` with `type(value) is str`, and MISSED the third
    site, `_is_secret_key`, which both redaction rules delegate to. A
    subclass overriding `lower()` to return `"harmless"` was measured
    writing a live credential onto the line under a key literally named
    `api_key`, and a subclass overriding `__contains__` to return False was
    measured defeating `_redact_value_string`'s early return the same way.

    An exact type test is the wrong shape of fix HERE, and this is the one
    place in this module where that is true. At the two guards F-5.0-22
    changed, refusing a subclass FAILS CLOSED: the value is discarded and
    replaced with a marker. Refusing a subclass KEY would fail OPEN
    instead, because `_is_secret_key` returning False means "this key is
    not secret-ish, keep the value", which is exactly what the attack
    wanted. So the fix is to keep accepting a subclass and stop trusting
    its methods.

    `str.__str__` is the unbound base method, so a subclass override cannot
    intercept it, and like every base `str` method it returns an exact
    `str`. Measured on this branch against a subclass overriding `lower`,
    `__contains__` and `__str__` together: it returned the genuine
    characters as `type(...) is str`.
    """
    return str.__str__(value)


def _is_secret_key(key: Any) -> bool:
    """Whether a params key name matches the secret-ish category, not a specific name.

    `isinstance` is deliberate rather than F-5.0-22's exact type test: see
    `_plain_str` for why refusing a subclass here would fail open. The
    subclass is admitted and then read through base methods only.
    """
    if not isinstance(key, str):
        return False
    lowered = _plain_str(key).lower()
    return any(marker in lowered for marker in _SECRET_KEY_MARKERS)


#: Matches `://user:password@` wherever it occurs, with no attempt to find
#: where the surrounding URL ends. The leading `://` is a literal, so the
#: regex engine skips straight to each candidate rather than scanning a
#: scheme name from every position, which is what keeps this linear on a
#: long string. The username half excludes `:` so the first colon is always
#: the split, matching RFC 3986's userinfo rule; the password half allows
#: `:` and `@` but not `/?#`, so it stops at the netloc's own end and,
#: being greedy, takes the LAST `@` inside it, which is the host delimiter
#: when a password itself contains one.
_NETLOC_CREDENTIAL_PATTERN = re.compile(r"://([^\s/?#@:\"'<>]*):([^\s/?#\"'<>]*)@")

#: The single characters that end a `name=value` assignment's value, beyond
#: whitespace: an ampersand, a fragment marker, a quote of either kind, or
#: an angle bracket. Named once so `_ASSIGNMENT_PATTERN` below and the
#: `_redact_value_string` docstring can both point at this set instead of
#: each spelling it out separately, which is how F-5.0-16 and F-5.0-18
#: happened, one round declared the set in prose and the next round's
#: prose drifted from it in opposite directions, one dropping a real
#: member and the other inventing members that were never in it. Brackets,
#: parentheses, braces, commas and semicolons are deliberately NOT in this
#: set: they are legal inside a query value (Entrez's own field syntax
#: puts square brackets there) and treating them as boundaries is exactly
#: what F-5.0-14 measured leaking.
_VALUE_TERMINATOR_CHARS = "&#\"'<>"

#: Matches a `name=value` assignment wherever it occurs. The lookbehind
#: pins the name to its own start so a longer name cannot match by its
#: suffix, and it is also what keeps this linear: inside a run of name
#: characters every position but the first fails in one step, so the
#: unbounded `+` is paid once per run rather than once per character. The
#: value runs to whatever terminates it locally per `_VALUE_TERMINATOR_CHARS`
#: plus whitespace, which is a far more local decision than finding the end
#: of the enclosing URL.
_ASSIGNMENT_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.%+\-])([A-Za-z0-9_.%+\-]+)=([^\s" + _VALUE_TERMINATOR_CHARS + r"]*)"
)


def _redact_netloc_credential(match: re.Match[str]) -> str:
    """Blank the password half of one `://user:password@` match.

    A password in a userinfo segment is sensitive by position rather than
    by name: there is no key name attached to it to test against
    `_SECRET_KEY_MARKERS`, only where it sits. The username and everything
    after the `@` are preserved so the audit line still names who connected
    and to which host, which is what Section 20.3 wants the line for.
    """
    return "://" + match.group(1) + ":" + REDACTED_PLACEHOLDER + "@"


def _redact_secret_assignment(match: re.Match[str]) -> str:
    """Blank the value of one `name=value` match whose NAME is secret-ish.

    Reuses `_is_secret_key`, and therefore `_SECRET_KEY_MARKERS`, rather
    than a second marker list: the key-name rule in `redact_params` and
    this value-level rule must not be able to drift into two different
    definitions of "secret".

    An empty value is left exactly as it was, because a name with nothing
    after the equals sign carries no secret, and writing a placeholder
    there would tell an operator a credential had been present when none
    was.
    """
    name, value = match.group(1), match.group(2)
    if not value or not _is_secret_key(name):
        return match.group(0)
    return name + "=" + REDACTED_PLACEHOLDER


def _redact_netloc_credentials(value: str) -> str:
    """Apply the netloc-credential rule everywhere it matches in a string."""
    return _NETLOC_CREDENTIAL_PATTERN.sub(_redact_netloc_credential, value)


def _redact_secret_assignments(value: str) -> str:
    """Apply the secret-assignment rule everywhere it matches in a string."""
    return _ASSIGNMENT_PATTERN.sub(_redact_secret_assignment, value)


def _redact_value_string(value: str) -> str:
    """BEST EFFORT defense in depth over caller-supplied `params`. NOT a control.

    Read this paragraph before relying on anything below it. This function
    is not a guarantee and must never be cited as one. A KNOWN GAP EXISTS
    and is open: F-5.0-19 measured that a non-secret assignment whose value
    is a URL swallows a secret assignment inside it, so
    `url=https://h/x?api_key=<secret>` passes through BYTE-IDENTICAL with
    nothing redacted at all. That gap is pinned by an executable arm,
    `TestKnownGapF5019` in `test_audit.py`, which asserts the leak still
    happens, so it cannot be quietly forgotten and cannot be closed
    without someone also correcting this paragraph.

    What this is FOR, and why it is kept despite that gap: `params` is a
    caller-supplied mapping whose values this module does not control, and
    on the shapes it does catch (F-5.0-08's and F-5.0-13's measured
    reproductions) it is the only thing standing between a DSN or an
    api_key query parameter and an append-only file. Removing it would
    regress that coverage for no gain, so it stays, demoted to what it
    actually is.

    What the REAL controls are, neither of which is a scanner:

    - For the transport: `ncbi_transport._endpoint_for_audit` records host
      plus path and never the raw URL, so the credential
      `_append_api_key` appends is never handed to this module in the
      first place. That is unchanged by this demotion and stays.
    - For the error field: `record_tool_call` accepts a code from
      `AUDIT_ERROR_CODES` and an exception class name, never free text,
      so there is no longer any message body for this function to be the
      last line of defense over.

    ## What it does, on the shapes it does catch

    Three rounds of this control tried to DELIMIT a URL inside prose and
    then redact within it, and each round was defeated by an input of the
    same family, because the end of a URL embedded in human text is
    genuinely ambiguous: brackets, parentheses and quotes are all legal in
    a query value and all ordinary prose punctuation, so every boundary
    rule is wrong for some real input. F-5.0-14 measured the last one
    failing on Entrez's own bracketed field syntax, and the failure was not
    a leak of the bracketed value: the bracket TRUNCATED the token, so the
    credential appended after it was never scanned at all.

    So this attacks the secret assignment directly instead, and never asks
    where the URL ends:

    1. `_redact_netloc_credentials`: a password in a `scheme://user:pw@host`
       userinfo segment, wherever that segment occurs.
    2. `_redact_secret_assignments`: the value of any `name=value` whose
       name matches `_SECRET_KEY_MARKERS`, wherever it occurs, ending at
       the value's own local terminator rather than at the enclosing URL's.

    Neither needs to know where the URL ends, which is the whole point.
    Rule 2 also covers, for free, the case the previous implementation
    declared out of scope: a bare secret-ish assignment sitting in prose
    with no URL wrapper around it at all.

    When nothing actually needed redacting, the ORIGINAL string is returned
    rather than a rebuilt one. Section 20.3 records the endpoint and the
    error so an operator can diagnose a failure, and a line redacted into
    uselessness defeats the purpose of writing it, so an ordinary URL or
    message carrying no secret must come back byte-identical.

    What genuinely defeats this is a test rather than a sentence here:
    `TestSecretAssignmentRedaction` and `TestValueTerminatorSet` in
    `test_audit.py` pin it, a raw character from `_VALUE_TERMINATOR_CHARS`
    (an ampersand, a fragment marker, a quote of either kind, or an angle
    bracket) or whitespace inside the credential itself ends the value
    there, because under URL rules those characters end a value and no
    parser could decide otherwise. This paragraph names the set by
    reference to `_VALUE_TERMINATOR_CHARS` rather than spelling it out a
    third time in prose: F-5.0-16 found a previous version of this exact
    sentence had dropped the angle bracket, and F-5.0-18 found the
    following attempt to correct it invented several characters, brackets,
    braces, commas, a semicolon, that were never in the set at all,
    because prose enumerated here has no way to stay tied to the regex it
    describes. Nothing else in this docstring asserts a security property,
    deliberately: build phase 4.15 shipped four defects that were a
    confident sentence describing a check that was not there, and the
    durable fix recorded there was deletion plus a test, never a more
    careful sentence.
    """
    if "=" not in value and "://" not in value:
        return value
    redacted = _redact_secret_assignments(_redact_netloc_credentials(value))
    return redacted if redacted != value else value


def _stringify_leaf(value: Any) -> str:
    """Convert a non-JSON-native leaf to text HERE, so redaction can see it.

    A-5.0-02, THE ORDERING GAP, and it is worth naming precisely because it
    is not another scanner gap and no fix to a pattern would have closed
    it. `redact_params` used to inspect `dict`, `list` and `str` and return
    every other leaf unchanged. `record_tool_call` then serialized the
    whole entry with `json.dumps(entry, default=str)`, and `default=str` is
    what converted the leaf to text, AFTER redaction was over. So an
    object whose `__str__` returns a DSN, an `httpx.URL` carrying a query
    string, a `pathlib.Path`, an exception object, travelled past every
    rule as an opaque leaf and was re-materialized as a credential at write
    time with nothing left to look at it.

    Every previous defeat in this phase was "something upstream consumed
    the credential before the check saw it". Here the upstream was the type
    system. The fix is therefore the ORDER, not a new pattern: convert
    first, then redact, so the string that `json.dumps` would eventually
    have produced is the same string the value rules actually inspect.

    A conversion that raises is not allowed to propagate: this module is
    best-effort by construction, and a hostile or half-constructed
    `__str__` must not be able to fail the tool call being described. It
    yields `_UNREPRESENTABLE_PLACEHOLDER`, which is the SAME disclosure
    substitution `_bounded` makes for a value `json.dumps` cannot encode
    (A-5.0-05). The two are one policy applied at two points on the same
    path, deliberately not two different answers to the same question: a
    value that cannot be represented is replaced by a marker naming that
    fact, and the line is still written.
    """
    try:
        return str(value)
    except Exception:  # noqa: BLE001 - a hostile __str__ must not fail the caller
        return _UNREPRESENTABLE_PLACEHOLDER


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
    2. Value-scanning rule (F-5.0-08, extended by F-5.0-13 and F-5.0-14):
       BEST EFFORT ONLY, with a known open gap. A string value that
       SURVIVES rule 1, because its key name was innocuous, is itself
       scanned for a secret-ish `name=value` assignment and for a
       connection-string password (`_redact_value_string`). Read that
       function's own docstring before relying on this: F-5.0-19 measured
       a shape it does not catch, and it must not be described as a
       guarantee. It exists because `params` is caller-supplied and a
       credential can ride inside a value under a key like `endpoint`
       that the key-name rule structurally cannot see. Both rules decide
       "secret" from `_SECRET_KEY_MARKERS`, so they cannot drift into two
       different definitions of the word.

    3. Deferred-stringification rule (A-5.0-02): a leaf that is neither a
       container nor a `str` nor a JSON-native scalar is converted to text
       HERE and then run through rule 2, rather than being passed through
       as an opaque object for `json.dumps(default=str)` to convert after
       redaction has finished. See `_stringify_leaf` for why this is an
       ordering fix and not a pattern fix.

    `None` and the exact scalar types in `_JSON_NATIVE_SCALARS` still pass
    through unchanged, and they are the only leaves that do. They carry no
    text, and `json.dumps` encodes them from the value rather than through
    `str()`, so there is no deferred conversion for rule 3 to get in front
    of. Stringifying them anyway would turn an HTTP status into `"200"` and
    lose the line's machine-readability for no gain.

    This function is no longer on the error field's path at all. It was,
    between F-5.0-13's fix and this design change, and that arrangement
    made a best-effort scanner the ONLY thing between a caught exception's
    message and an append-only file. `record_tool_call` now takes a code
    from a closed vocabulary instead, so the message never exists as a
    field for this to guard.

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
        # A-5.0-01: `_redact_value_string` calls `str` methods on what it
        # is given, including the `in` test its early return depends on. A
        # subclass overriding `__contains__` was measured defeating that
        # return outright, so the subclass is flattened to its real
        # characters before any method of its own can answer for it.
        return _redact_value_string(_plain_str(value))
    if value is None or type(value) in _JSON_NATIVE_SCALARS:
        return value
    return _redact_value_string(_stringify_leaf(value))


def _bounded_text(value: Any, *, field_name: str) -> str:
    """Redact and cap one scalar TEXT field on the line.

    A-5.0-03. `tool`, `endpoint`, `authorization` and `trace_id` were each
    placed into the entry dict verbatim. `authorization`'s own docstring
    states the rule it did not enforce, "the NAME of the credential used
    ... Never the credential value itself", which is build phase 4.15's
    recorded defect class exactly: a confident sentence describing a check
    that is not there.

    Redaction is the SAME `_redact_value_string` `params` values get, and
    that is deliberate rather than convenient. Two different definitions of
    "secret" on one line is how a control drifts; the caveats on that
    function apply here unchanged, including the open gap its own docstring
    pins, and it is best effort here for the same reason it is best effort
    there. What is NOT best effort is the cap.

    Over the cap the value is DROPPED and the drop is disclosed, never
    truncated. A truncated redaction can leave a fragment of a credential
    while reading as complete, and the disclosure marker names the field
    and the real size so an operator can tell a dropped field from a field
    that was never populated.
    """
    if isinstance(value, str):
        text = _redact_value_string(_plain_str(value))
    else:
        text = _redact_value_string(_stringify_leaf(value))
    encoded_len = len(text.encode("utf-8"))
    if encoded_len <= _MAX_TEXT_FIELD_BYTES:
        return text
    return (
        f"[{field_name} exceeded the audit log size cap and was dropped: "
        f"{encoded_len} bytes, cap {_MAX_TEXT_FIELD_BYTES}]"
    )


def _bounded_record_ids(record_ids: Sequence[Any] | None) -> Any:
    """Redact, item-cap and size-cap the one field filled by a third party.

    A-5.0-04. `record_ids` holds identifiers a live NCBI or enrichment API
    returned, and it got `list(record_ids)` and nothing else: no redaction,
    no element handling, no `maxItems`, no size bound. Both halves of the
    adversary's reproduction landed verbatim, a credential assignment as a
    string element and a deferred-`__str__` object as the next one.

    Three bounds, in this order, and the order is the same one `_bounded`
    already relies on:

    1. `maxItems` FIRST, so a pathological element count cannot make the
       redaction walk itself the expensive part.
    2. `redact_params` over the truncated list, which is what gives each
       element the value rule and, since fix A-5.0-02, the deferred
       stringification rule as well.
    3. The size cap last, over the already-redacted list, so no fragment of
       a secret is ever produced by shortening.

    Item truncation appends a marker element rather than dropping silently.
    That keeps the field a list, which every reader of the line expects,
    and it discloses the loss: whole elements are dropped, never split, so
    a marker here cannot expose half a value.
    """
    if record_ids is None:
        return []
    items = list(record_ids)
    dropped = len(items) - _MAX_RECORD_IDS
    if dropped > 0:
        items = items[:_MAX_RECORD_IDS]
    redacted = redact_params(items)
    if dropped > 0:
        redacted.append(f"[record_ids truncated, {dropped} more not recorded]")
    return _bounded(redacted, field_name="record_ids", cap_bytes=_MAX_RECORD_IDS_BYTES)


def _bounded(
    redacted: Any, *, field_name: str = "params", cap_bytes: int = _MAX_PARAMS_BYTES
) -> Any:
    """Cap the serialized size of an already-redacted value.

    `params` and `record_ids` are the two callers, the second added under
    A-5.0-04 with its own smaller `cap_bytes`. `field_name` names the field
    the disclosure marker refers to, which is why it was already a
    parameter before a second caller existed; it is not kept because
    `error` still uses it, which it no longer does. The error half is
    bounded by `AUDIT_ERROR_CODES`
    and `_MAX_ERROR_CLASS_CHARS` instead, which is a stronger bound than a
    size cap: a size cap shortens an oversized value, while a closed
    vocabulary means an oversized value never becomes a field value at
    all.

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
            "_audit_note": f"{field_name} could not be serialized and was dropped",
        }
    encoded_len = len(serialized.encode("utf-8"))
    if encoded_len <= cap_bytes:
        return redacted
    return {
        "_audit_note": f"{field_name} exceeded the audit log size cap and was dropped",
        "_audit_original_bytes": encoded_len,
        "_audit_cap_bytes": cap_bytes,
    }


def _bounded_line(entry: dict[str, Any]) -> str:
    """Serialize one entry, guaranteed to fit inside one atomic append.

    A-5.0-19, and the half of the append-only guarantee the per-process
    lock cannot provide. See the module docstring section "The lock and the
    field caps are ONE control" for the measurement: four processes writing
    short lines lost nothing, and the same four writing 20 KB lines lost a
    quarter of every line permanently.

    The two variable-size fields are the only ones that can push a line
    over, and both are replaced wholesale rather than shortened, for the
    same reason `_bounded` drops rather than truncates: a fragment of a
    redacted structure reads as complete. The reduction is disclosed on the
    line itself, so a reader can tell a reduced record from a record whose
    call genuinely carried nothing.

    Section 20.3's required fields all survive a reduction: `trace_id`,
    `tool`, `layer`, `endpoint`, `authorization`, `http_status`,
    `error_code`, `error_class`, `latency_ms` and the timestamp are each
    bounded by their own cap already, so the reduced line is bounded by
    construction rather than by a second measurement.
    """
    try:
        line = json.dumps(entry, default=str)
    except Exception:  # noqa: BLE001 - see _degraded_line: never lose the record
        return _degraded_line(entry)
    encoded_len = len(line.encode("utf-8"))
    if encoded_len <= _MAX_LINE_BYTES:
        return line
    reduced = dict(entry)
    reduced["params"] = {"_audit_note": "params dropped to keep the line atomic"}
    reduced["record_ids"] = ["[record_ids dropped to keep the line atomic]"]
    reduced["_audit_note"] = (
        f"line was {encoded_len} bytes, over the {_MAX_LINE_BYTES} byte cap, "
        "and was reduced so a concurrent process cannot interleave with it"
    )
    try:
        return json.dumps(reduced, default=str)
    except Exception:  # noqa: BLE001 - the reduced form can fail for the same reason
        return _degraded_line(entry)


def _degraded_line(entry: dict[str, Any]) -> str:
    """The line that gets written when the entry cannot be serialized at all.

    A-5.0-05, and it is the OPPOSITE failure to a leak. `record_tool_call`
    guaranteed "never raises" and never separately guaranteed "always
    records", and the gap between those two sentences was measurable: one
    value `json.dumps` refuses, a non-string dict key inside `record_ids`
    being the shape that `default=str` is never even consulted for, and the
    whole line vanished. Zero lines written, one `logger.warning` naming an
    exception class, and nothing else. In a sink whose entire purpose is
    proving what happened, an absent line is indistinguishable from the
    call never having happened, and the file is append-only so it can never
    be reconstructed afterwards.

    Every value is reduced to a JSON primitive it already is, or to
    `_UNREPRESENTABLE_PLACEHOLDER`, and the disclosure says so. That makes
    this function's own `json.dumps` unable to fail: it is handed nothing
    but `None`, `bool`, `int`, `float` and `str`, with no `default` hook to
    invoke and therefore no third-party code left to run.

    Note what is NOT attempted: no `str()` is called on the offending
    value. `_stringify_leaf` already tried that upstream for the leaves it
    owns, and calling it again here on a value that has already refused to
    serialize would be running the same hostile code a second time to
    salvage a field, in the one code path whose whole job is to stop
    failing. The composition with fix A-5.0-02 is therefore: convert early
    where a conversion is safe and useful, and here, at the last step,
    convert nothing and disclose instead.
    """
    safe: dict[str, Any] = {}
    for key, value in entry.items():
        if value is None or type(value) in _JSON_NATIVE_SCALARS or type(value) is str:
            safe[str(key)] = value
        else:
            safe[str(key)] = _UNREPRESENTABLE_PLACEHOLDER
    safe["_audit_note"] = (
        "one or more fields could not be serialized and were replaced; "
        "the record is degraded rather than dropped"
    )
    return json.dumps(safe)


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
    error_code: str | None = None,
    error_class: str | None = None,
    error: str | None = None,
) -> None:
    """Append one Section 20.3 audit line for a single Layer 1/2/3 access.

    Writes nothing at all when `audit_enabled()` is False, checked first
    and before any other work, so the disabled path costs one function call
    and touches the filesystem not at all.

    Args:
        tool: the tool or caller name (for example "cypher_query",
            "ncbi_efetch", or the KGX export traversal that bypasses the
            tool layer entirely). Redacted and capped like every other
            text field on the line (A-5.0-03).
        layer: 1, 2, or 3, naming which of the three data-access layers
            this call reached (system-design-patterns.md pattern 3).
        endpoint: the endpoint or database called (a URL path, an NCBI
            db name, or the graph database name). Redacted and capped
            (A-5.0-03). That is a bound at the SINK, and it does not
            replace `ncbi_transport._endpoint_for_audit`, which stops the
            raw URL being handed here in the first place; a caller-side
            fix covers one caller, this covers every caller.
        latency_ms: wall-clock time the call took, measured by the
            transport that holds the actual request, never estimated here.
        authorization: the NAME of the credential used, for example
            "ncbi_api_key", "kg_reader", or "none". Never the credential
            value itself (PRD: every Layer 2/3 access logged with its
            authorization, by identifier, never by value). That sentence
            described a rule nothing enforced until A-5.0-03; the field is
            now redacted and capped, which is a bound rather than a
            guarantee that a caller passed a name.
        params: the call's parameters, redacted by category and size
            capped before they are written. May be None or empty.
        record_ids: identifiers the call returned, for example a list of
            NCBI UIDs or graph node ids. May be None, recorded as an empty
            list. UNTRUSTED EXTERNAL CONTENT by definition, since its
            contents are whatever a third-party API returned, so it is
            item-capped, redacted element by element and size-capped
            (A-5.0-04). See `_bounded_record_ids`.
        http_status: the numeric HTTP status, or None for a call with no
            HTTP semantics (a graph query, an FTP transfer) or a
            body-level failure E-utilities reports with no status code at
            all (Section 20.3's own "empty signal for E-utilities" case).
        error_code: one member of `AUDIT_ERROR_CODES`, or None for a call
            that succeeded. NOT free text, and not derived from any
            exception message, URL or response body: see this module's
            docstring for why three rounds of scanning free text were
            abandoned in favour of a closed vocabulary. Anything outside
            the vocabulary FAILS CLOSED to `unexpected` and the supplied
            value is discarded, never written in any form.
        error_class: the exception's class name, `type(exc).__name__`, or
            None. Developer-controlled by construction, the same thing
            `feedback/writer.py` logs and for the same reason. Admitted
            only when it is a plain Python identifier within
            `_MAX_ERROR_CLASS_CHARS`; anything else records
            `_REFUSED_ERROR_CLASS` instead of the value.
        error: DEPRECATED legacy keyword, kept only so a caller this
            design change may not edit keeps working. It is routed through
            the SAME `classify_error_code` as `error_code`, so a message
            string passed here is not in the vocabulary and records
            `unexpected`. It can therefore never carry text onto the line,
            only lose fidelity relative to a converted call site.
            `src/system_03_search_agent/tools/pathogen_ftp_transport.py`
            is the one remaining caller, tracked as F-5.0-20 in
            `tracker/phase_5.0.md` with the one-line change it needs.
            `error_code` wins when both are supplied.

    Section 20.3 compliance for the error half of "HTTP status or the
    body-level error and empty signal": the line carries `http_status`
    (the numeric status, unchanged) alongside `error_code`, so a reader
    gets the status where one exists and a classified reason where the
    failure had no HTTP semantics at all, which is every graph call and
    every connection-level failure. A code plus a status is strictly more
    machine-readable than the free-text message it replaces, and it is
    what the premise gate's Section 20.3 field-completeness arm now
    checks for.

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
        raw_trace_id = current_trace_id()
        entry: dict[str, Any] = {
            # A-5.0-03: every text field below now carries the same
            # redaction and the same cap. Before this, four of them were
            # placed here verbatim, which left the SINK exactly as
            # defenceless as the day F-5.0-08 was filed, since that
            # critical was closed at one caller rather than here.
            "trace_id": (
                None
                if raw_trace_id is None
                else _bounded_text(raw_trace_id, field_name="trace_id")
            ),
            "timestamp": _utc_timestamp(),
            "tool": _bounded_text(tool, field_name="tool"),
            "layer": layer,
            "endpoint": _bounded_text(endpoint, field_name="endpoint"),
            "authorization": _bounded_text(authorization, field_name="authorization"),
            "params": _bounded(redact_params(dict(params) if params else {})),
            "record_ids": _bounded_record_ids(record_ids),
            "http_status": http_status,
            # Neither of these two runs through `redact_params`, and that
            # is the point rather than an omission: a closed vocabulary
            # and a Python identifier have no path a credential can travel
            # down, so there is nothing for a redactor to find. Sending
            # them through one anyway would restate the scanner as the
            # control, which is the arrangement this change removes.
            "error_code": classify_error_code(
                error_code if error_code is not None else error
            ),
            "error_class": _safe_error_class(error_class),
            "latency_ms": latency_ms,
        }
        line = _bounded_line(entry)
        path = audit_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        _append_line(path, line)
    except Exception as exc:  # noqa: BLE001 - a best-effort write must catch any failure mode
        logger.warning(
            "tool-call audit write failed for tool=%s (%s)",
            tool,
            type(exc).__name__,
        )
