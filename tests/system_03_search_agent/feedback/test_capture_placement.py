"""The saved answer reads the summary above the listing (build phase 8.7, card 50),
and keeps one row per citation id (F-8.7-A04, card 57)."""

from __future__ import annotations

from datetime import UTC, datetime

from system_03_search_agent.contracts.events import Event
from system_03_search_agent.contracts.query import Query
from system_03_search_agent.feedback.capture import answer_markdown_from, assemble_interaction


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


# ---------------------------------------------------------------------------
# F-8.7-A04, card 57: the saved answer keeps one row per citation id, the
# payload sent again once the summary is checked in the first one's place.
# ---------------------------------------------------------------------------


def _citation(seq: int, n: int, claim_text: str, **extra: object) -> Event:
    payload: dict = {
        "citation_id": f"c{n}",
        "display_index": n,
        "source": "MedGen",
        "source_id": f"MedGen:C{n}",
        "source_url": f"https://www.ncbi.nlm.nih.gov/medgen/C{n}",
        "layer": "layer_1_graph",
        "field": "name",
        "claim_text": claim_text,
        "evidence_kind": "curated assertion",
        "assertion_confidence": "not provided",
        "population_ancestry_context": None,
        "license": "public_domain_us_gov",
        "snapshot_date": None,
        "entity_name": f"disease {n}",
    }
    payload.update(extra)
    return Event(
        type="citation", version="v1", trace_id="t", seq=seq, ts=datetime.now(UTC), payload=payload
    )


def test_a_citation_sent_again_is_saved_once_with_its_checked_words() -> None:
    """Mutation that turns this red: list every citation event as it came
    (drop `one_per_citation_id` in `assemble_interaction`)."""
    done = Event(
        type="done",
        version="v1",
        trace_id="t",
        seq=9,
        ts=datetime.now(UTC),
        payload={
            "total_cost_usd": 0.01,
            "total_tool_calls": 1,
            "elapsed_ms": 10,
            "trust_outcome": "answer",
        },
    )
    events = [
        _token("Disease 1 [1]. ", "listing", 0),
        _citation(1, 1, "Disease 1"),
        _citation(2, 2, "Disease 2"),
        _token("BRCA1 is linked to disease 1 [1]. ", "summary", 3),
        _citation(4, 1, "Disease 1 BRCA1 is linked to disease 1"),
        # Another number for an id already shown is not an update: dropped.
        _citation(5, 2, "Disease 2 again", display_index=7),
        done,
    ]
    query = Query(
        text="Which diseases?",
        session_id="session-1",
        trace_id="t",
        owner_id="guest:aaaaaaaa-0000-0000-0000-000000000000",
    )

    row = assemble_interaction(query, events)

    assert row is not None
    assert [c["citation_id"] for c in row.citations] == ["c1", "c2"]
    assert row.citations[0]["claim_text"] == "Disease 1 BRCA1 is linked to disease 1"
    assert row.citations[1]["display_index"] == 2
