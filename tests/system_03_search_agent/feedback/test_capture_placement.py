"""The saved answer reads the summary above the listing (build phase 8.7, card 50)."""

from __future__ import annotations

from datetime import UTC, datetime

from system_03_search_agent.contracts.events import Event
from system_03_search_agent.feedback.capture import answer_markdown_from


def _token(text: str, placement: str | None = None, seq: int = 0) -> Event:
    payload: dict = {"text": text, "marker_ids": []}
    if placement is not None:
        payload["placement"] = placement
    return Event(
        type="token", version="v1", trace_id="t", seq=seq, ts=datetime.now(UTC), payload=payload
    )


def test_listing_first_stream_stores_summary_first() -> None:
    # Mutation that turns this red: iterate the events in arrival order.
    events = [
        _token("Record A. ", "listing", 0),
        _token("Summary. ", "summary", 1),
        _token("Record B. ", "listing", 2),
    ]
    assert answer_markdown_from(events) == "Summary. Record A. Record B."


def test_stream_without_placement_is_unchanged() -> None:
    events = [_token("One. ", None, 0), _token("Two. ", None, 1)]
    assert answer_markdown_from(events) == "One. Two."
