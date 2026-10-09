"""The golden harness reads the summary above the listing (build phase 8.7, card 50)."""

from __future__ import annotations

from typing import Any

from system_03_search_agent.eval.trace_source import record_from_runs


def _run(tokens: list[dict[str, Any]]) -> dict[str, Any]:
    events = [{"type": "token", "seq": i, "payload": p} for i, p in enumerate(tokens)]
    return {"trace_id": "t-place", "inputs": {}, "outputs": {"events": events}}


def test_listing_first_trace_reads_summary_first() -> None:
    # Mutation that turns this red: join token text in arrival order.
    run = _run(
        [
            {"text": "Record A. ", "placement": "listing"},
            {"text": "Summary. ", "placement": "summary"},
        ]
    )
    assert record_from_runs([run], query_id="q").answer_text == "Summary. Record A. "


def test_trace_without_placement_is_unchanged() -> None:
    run = _run([{"text": "One. "}, {"text": "Two. "}])
    assert record_from_runs([run], query_id="q").answer_text == "One. Two. "
