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


def _citation(citation_id: str, claim_text: str) -> dict[str, Any]:
    return {
        "citation_id": citation_id,
        "display_index": int(citation_id[1:]),
        "source": "MedGen",
        "source_id": f"MedGen:{citation_id}",
        "source_url": f"https://www.ncbi.nlm.nih.gov/medgen/{citation_id}",
        "claim_text": claim_text,
    }


def test_a_resent_citation_is_one_citation_and_one_claim() -> None:
    """A-87F-02: a listing citation the summary also cites is sent again
    with its checked words grown. The trace reads one citation and one
    claim per id, with the grown words. Mutation that turns this red: take
    every citation event (the reader at 9fe8f166)."""
    payloads = [
        ("citation", _citation("c1", "Disease 1")),
        ("citation", _citation("c2", "Disease 2")),
        ("token", {"text": "Summary [1]. ", "placement": "summary"}),
        ("citation", _citation("c1", "Disease 1 BRCA1 is linked to disease 1")),
    ]
    events = [
        {"type": kind, "seq": i, "payload": payload} for i, (kind, payload) in enumerate(payloads)
    ]
    run = {"trace_id": "t-resend", "inputs": {}, "outputs": {"events": events}}
    record = record_from_runs([run], query_id="q")
    assert [c["citation_id"] for c in record.citations] == ["c1", "c2"]
    assert [c["text"] for c in record.claims] == [
        "Disease 1 BRCA1 is linked to disease 1",
        "Disease 2",
    ]
