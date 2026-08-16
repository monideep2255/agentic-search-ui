"""The SSE frame parser T-4.2-03 owns: `tracker/phase_4.2.md`.

Parses the wire the server actually writes
(`adapters/web_sse/app.py`'s `get_v1_query_events`, via `sse_starlette`'s
default `EventSourceResponse` writer), not the full WHATWG
`text/event-stream` grammar. Three facts from this phase's pre-build
source read shape everything below:

    - `sse_starlette` emits a keepalive COMMENT line, `: ping - <ts>`,
      every 15 seconds. A `:`-prefixed line is a comment in the SSE
      grammar and carries no field; it must be skipped, never parsed as
      data and never dispatched as an event with no data.
    - `data:` carries the FULL `Event` envelope
      (`{type, version, trace_id, seq, ts, payload}`), never a bare
      payload. This module hands the caller the raw JSON string; decoding
      it into `contracts.events.Event` is `client.py`'s job, not this
      one's, so this parser stays independently testable against plain
      text with no `contracts` import at all.
    - `id:` carries the envelope's real `seq`, and the server strips
      `cost` events before a non-operator caller ever sees them
      (`harness/cost_control.py`'s `sanitize_event_for_end_user`) while
      `seq` keeps counting regardless. A non-operator's visible `id:`
      sequence therefore has gaps BY DESIGN (0, 2, 4, ...). This module
      has no cross-event state beyond one buffered, in-flight event, so
      it cannot and does not infer anything from a gap between two
      dispatched tuples; that non-inference is the point, not an
      omission. The caller must not treat a gap as a dropped event either
      (`tracker/phase_4.2.md`'s SSE wire tolerance arm).

Depends on:
    - Nothing beyond the stdlib. A pure, transport-agnostic line parser,
      deliberately: `client.py`'s `stream_events` drives the same
      incremental core (`_SseLineAccumulator`) over `httpx.Response.
      aiter_lines()`, a true async iterator no sync generator can pull
      from directly, while `parse_sse_lines` below drives it over a
      plain, static `Iterable[str]` for direct, fixture-free unit testing.

Reads:
    - Nothing. Every function here is pure over its arguments.

Writes:
    - Nothing.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

# One dispatched SSE event, restated from the fixed interface
# `tracker/phase_4.2.md` gives this module: (event_type, data, last_event_id).
# `data` is the raw, undecoded JSON text of the `data:` field(s) joined by
# `\n` per the SSE multi-line-data rule; decoding it into a typed `Event`
# is `client.py`'s job.
SseTuple = tuple[str | None, str, str | None]

# F-4.2-A-25: the accumulator had no bound on a single event's `data:`
# field, so a hostile or corrupted stream could grow one event's buffer
# without limit before ever reaching a JSON-parse or Pydantic failure. 64
# KiB is comfortably above any real envelope this repo's server can emit
# (contracts/events.py's own `max_length` caps put the largest realistic
# payload, a full ThinkPayload with 20 ResolvedEntity items, at well under
# 10 KiB) and far below a pathological multi-megabyte line
# (`production-standards.md`'s bounded-context-items gate).
_MAX_ACCUMULATED_DATA_CHARS: int = 65536


class SseFrameTooLargeError(Exception):
    """A single SSE event's accumulated `data:` field exceeded
    `_MAX_ACCUMULATED_DATA_CHARS` before a blank line (or a stream-end
    flush) closed it. Raised eagerly, at the `data:` line that pushes the
    running total over the cap, rather than after buffering an unbounded
    amount and only failing later at JSON-parse time (F-4.2-A-25).
    Actionable: no legitimate event from this repo's server approaches
    this size, so a caller should abort the stream rather than retry the
    same connection; retrying the whole run from a fresh `s3 ask` is the
    reasonable next step if this recurs.
    """

    def __init__(self, accumulated_chars: int) -> None:
        super().__init__(
            f"one SSE event's data field exceeded {_MAX_ACCUMULATED_DATA_CHARS} "
            f"characters ({accumulated_chars} accumulated before this line); "
            "aborting the stream rather than buffering further. This is not a "
            "normal server response; do not retry the same connection."
        )
        self.accumulated_chars = accumulated_chars


class _SseLineAccumulator:
    """The incremental, one-line-at-a-time core both `parse_sse_lines`
    (over a static `Iterable[str]`) and `client.py`'s `stream_events`
    (over `httpx.Response.aiter_lines()`, an async iterator) drive.

    Follows the WHATWG SSE field-parsing algorithm's shape closely enough
    to interoperate with `sse_starlette`'s writer, the only producer this
    parser ever has to agree with: a `:`-prefixed line is a comment and
    produces no field; a blank line dispatches whatever was buffered since
    the last dispatch (or nothing, if no `data:` line arrived); a `field:
    value` line with exactly one leading space after the colon stripped
    updates the named field. It deliberately does NOT implement the full
    grammar: no `retry:` field, no default-event-name fallback, no BOM
    handling. This repo's server never emits those shapes, and a
    spec-complete parser is strictly more untested surface than the wire
    this repo actually writes.

    `last_event_id` is intentionally NOT reset when an event dispatches:
    real `EventSource` semantics keep the "last event ID buffer" live
    across dispatches (a later event that carries no `id:` line of its own
    still resumes from the most recently seen one), and `client.py`'s
    reconnect logic depends on that value staying meaningful across the
    whole stream, not just the one event that happened to set it.
    """

    def __init__(self) -> None:
        self._event_type: str | None = None
        self._data_lines: list[str] = []
        self._data_seen = False
        self._data_chars = 0
        self._last_event_id: str | None = None

    def feed(self, raw_line: str) -> SseTuple | None:
        """Consume one line (no trailing newline required; a trailing
        `\\r` is stripped if present, tolerating CRLF-terminated streams).
        Returns a dispatched tuple on a blank line that closes a buffered
        event, `None` otherwise (a field line, a comment, or a blank line
        with nothing buffered).
        """
        line = raw_line.removesuffix("\r")
        if line == "":
            return self._dispatch()
        if line.startswith(":"):
            # Comment / keepalive line (sse_starlette's `: ping - ...`).
            # Never buffered, never dispatched, per the field-parsing
            # algorithm this module's docstring describes.
            return None
        if ":" in line:
            field, _, value = line.partition(":")
            value = value.removeprefix(" ")
        else:
            # A field-name-only line with no colon: the algorithm treats
            # this as the field set to the empty string. Not a shape this
            # repo's server ever writes, but handled rather than silently
            # dropped, since dropping it would be a different, undeclared
            # parsing decision.
            field, value = line, ""
        if field == "event":
            self._event_type = value
        elif field == "data":
            # +1 for the "\n" joiner every line after the first will need
            # at dispatch time (`_dispatch`'s "\n".join), so the bound
            # matches what will actually be handed to a JSON parser.
            joiner = 1 if self._data_lines else 0
            prospective_chars = self._data_chars + joiner + len(value)
            if prospective_chars > _MAX_ACCUMULATED_DATA_CHARS:
                raise SseFrameTooLargeError(prospective_chars)
            self._data_lines.append(value)
            self._data_chars = prospective_chars
            self._data_seen = True
        elif field == "id":
            self._last_event_id = value
        # Any other field name (e.g. a hypothetical future `retry:`) is
        # intentionally ignored: this repo's server never emits one, and
        # silently dropping an unrecognized field matches the WHATWG
        # algorithm's own behavior more closely than raising on it.
        return None

    def _dispatch(self) -> SseTuple | None:
        if not self._data_seen:
            self._reset_event()
            return None
        result: SseTuple = (
            self._event_type,
            "\n".join(self._data_lines),
            self._last_event_id,
        )
        self._reset_event()
        return result

    def _reset_event(self) -> None:
        self._event_type = None
        self._data_lines = []
        self._data_seen = False
        self._data_chars = 0

    def flush(self) -> SseTuple | None:
        """Dispatch whatever is buffered even without a trailing blank
        line, for a stream that ends (or is cut off) mid-event. Never
        called by `parse_sse_lines` in a way that changes its documented
        behavior on well-formed input (every event in this repo's wire is
        blank-line-terminated); it exists for `client.py`'s benefit, where
        a real connection can end without one.
        """
        return self._dispatch()


def parse_sse_lines(lines: Iterable[str]) -> Iterator[SseTuple]:
    """Parse a decoded SSE text stream into `(event_type, data,
    last_event_id)` tuples, one per dispatched event.

    Skips every comment line (`:` prefix) and yields nothing for a blank
    line that closes no buffered `data:` field, so a bare keepalive
    (`: ping - ...` followed by a blank line) never produces a tuple, per
    `tracker/phase_4.2.md`'s SSE wire tolerance arm. A gap in the `id:`
    values across successive yielded tuples is not this function's
    concern: it holds no state beyond the one event currently buffered,
    so it cannot and does not infer anything about what a gap means.
    """
    accumulator = _SseLineAccumulator()
    for raw_line in lines:
        parsed = accumulator.feed(raw_line)
        if parsed is not None:
            yield parsed
    trailing = accumulator.flush()
    if trailing is not None:
        yield trailing
