"""Unit coverage for `adapters/cli/sse.py`'s `parse_sse_lines`.

This is direct, fixture-free coverage of the parser in isolation, one
level below `tests/system_03_search_agent/adapters/cli/
test_phase_4_2_premise.py`'s `TestSseWireTolerance` (which exercises the
same module through the real `s3 ask` entry point over a real server). The
premise gate pins the phase's own done-when; this file pins the parser's
own contract more exhaustively, including several shapes the premise gate
has no reason to construct itself (CRLF line endings, a field-name-only
line, an unrecognized field, a trailing unterminated event).

Depends on:
    - system_03_search_agent.adapters.cli.sse (parse_sse_lines)

Reads:
    - Nothing.

Writes:
    - Nothing.
"""

from __future__ import annotations

import pytest

from system_03_search_agent.adapters.cli.sse import (
    _MAX_ACCUMULATED_DATA_CHARS,
    SseFrameTooLargeError,
    parse_sse_lines,
)


def test_a_single_well_formed_event_round_trips() -> None:
    lines = [
        "event: guard",
        'data: {"type": "guard"}',
        "id: 0",
        "",
    ]
    results = list(parse_sse_lines(lines))
    assert results == [("guard", '{"type": "guard"}', "0")]


def test_comment_lines_are_skipped_and_never_yield() -> None:
    lines = [": ping - 2026-08-16T00:00:00Z", ""]
    assert list(parse_sse_lines(lines)) == []


def test_a_blank_line_with_no_data_seen_yields_nothing() -> None:
    # A bare "event:" with no "data:" line, terminated by a blank line:
    # the SSE spec's own dispatch rule requires a buffered data field
    # before a dispatch fires, so nothing is emitted.
    lines = ["event: something", ""]
    assert list(parse_sse_lines(lines)) == []


def test_multi_line_data_fields_join_with_newline() -> None:
    lines = [
        "event: token",
        "data: line one",
        "data: line two",
        "id: 5",
        "",
    ]
    results = list(parse_sse_lines(lines))
    assert results == [("token", "line one\nline two", "5")]


def test_a_leading_space_after_the_colon_is_stripped_exactly_once() -> None:
    lines = ["event: guard", "data:  two leading spaces", "id: 0", ""]
    results = list(parse_sse_lines(lines))
    # Only the FIRST space after the colon is stripped, per the SSE field
    # algorithm; the second is real payload content.
    assert results == [("guard", " two leading spaces", "0")]


def test_crlf_terminated_lines_are_tolerated() -> None:
    lines = ["event: guard\r", 'data: {"a": 1}\r', "id: 0\r", "\r"]
    results = list(parse_sse_lines(lines))
    assert results == [("guard", '{"a": 1}', "0")]


def test_a_field_name_only_line_with_no_colon_sets_the_field_to_empty() -> None:
    lines = ["event", 'data: {"a": 1}', ""]
    results = list(parse_sse_lines(lines))
    # "event" alone (no colon) sets event_type to the empty string, not
    # None and not "event": the WHATWG algorithm treats a colon-less line
    # as "field: ''", not as junk to discard.
    assert results == [("", '{"a": 1}', None)]


def test_an_unrecognized_field_is_ignored_without_raising() -> None:
    lines = ["retry: 3000", "event: guard", 'data: {"a": 1}', "id: 0", ""]
    results = list(parse_sse_lines(lines))
    assert results == [("guard", '{"a": 1}', "0")]


def test_last_event_id_persists_across_a_dispatch_with_no_new_id_line() -> None:
    # Real EventSource semantics: the "last event ID buffer" is not reset
    # on dispatch. A second event with no id: line of its own still
    # resumes from the most recently seen id.
    lines = [
        "event: guard",
        'data: {"a": 1}',
        "id: 7",
        "",
        "event: token",
        'data: {"b": 2}',
        "",
    ]
    results = list(parse_sse_lines(lines))
    assert results == [
        ("guard", '{"a": 1}', "7"),
        ("token", '{"b": 2}', "7"),
    ]


def test_multiple_events_separated_by_keepalive_comments_all_dispatch() -> None:
    lines = [
        "event: guard",
        'data: {"type": "guard"}',
        "id: 0",
        "",
        ": ping - t1",
        "",
        "event: done",
        'data: {"type": "done"}',
        "id: 2",
        "",
        ": ping - t2",
        "",
    ]
    results = list(parse_sse_lines(lines))
    assert [r[0] for r in results] == ["guard", "done"]
    assert [r[2] for r in results] == ["0", "2"]


def test_a_trailing_event_with_no_final_blank_line_still_dispatches() -> None:
    # A real connection can end mid-event (no trailing blank line); the
    # parser flushes whatever was buffered rather than silently dropping
    # the last event.
    lines = ["event: done", 'data: {"type": "done"}', "id: 9"]
    results = list(parse_sse_lines(lines))
    assert results == [("done", '{"type": "done"}', "9")]


def test_an_empty_input_yields_nothing() -> None:
    assert list(parse_sse_lines([])) == []


def test_a_trailing_flush_with_nothing_buffered_yields_nothing() -> None:
    lines = ["event: guard", 'data: {"a": 1}', "id: 0", "", ": ping - t1"]
    results = list(parse_sse_lines(lines))
    # The keepalive comment at the end leaves nothing buffered, so the
    # trailing flush produces no phantom second tuple.
    assert results == [("guard", '{"a": 1}', "0")]


# ---------------------------------------------------------------------------
# F-4.2-A-25: a single event's data field is bounded, and fails fast
# rather than buffering an unbounded amount before a later JSON-parse
# failure.
# ---------------------------------------------------------------------------


def test_a_data_field_within_the_cap_still_dispatches_normally() -> None:
    value = "x" * (_MAX_ACCUMULATED_DATA_CHARS - 1)
    lines = ["event: token", f"data: {value}", "id: 0", ""]
    results = list(parse_sse_lines(lines))
    assert results == [("token", value, "0")]


def test_a_single_data_line_exceeding_the_cap_raises_immediately() -> None:
    value = "x" * (_MAX_ACCUMULATED_DATA_CHARS + 1)
    lines = ["event: token", f"data: {value}", "id: 0", ""]
    with pytest.raises(SseFrameTooLargeError):
        list(parse_sse_lines(lines))


def test_multiple_data_lines_that_cumulatively_exceed_the_cap_raise() -> None:
    # Neither line alone exceeds the cap; their sum (plus the "\n" joiner
    # `_dispatch` would insert) does. The bound is on the accumulated
    # total, not on any single physical line.
    half = "x" * (_MAX_ACCUMULATED_DATA_CHARS // 2 + 10)
    lines = ["event: token", f"data: {half}", f"data: {half}", "id: 0", ""]
    with pytest.raises(SseFrameTooLargeError):
        list(parse_sse_lines(lines))


def test_the_cap_violation_message_names_the_accumulated_size() -> None:
    value = "x" * (_MAX_ACCUMULATED_DATA_CHARS + 500)
    lines = ["event: token", f"data: {value}", "id: 0", ""]
    with pytest.raises(SseFrameTooLargeError) as exc_info:
        list(parse_sse_lines(lines))
    # Actionable per tool-call-budgets.md: names the bound, not just "too
    # big", and does not silently retry the same connection.
    assert str(_MAX_ACCUMULATED_DATA_CHARS) in str(exc_info.value)
    assert "retry" in str(exc_info.value).lower()
