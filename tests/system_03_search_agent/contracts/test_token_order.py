"""Reading order for answer tokens (build phase 8.7, T-8.7-03, card 50)."""

from __future__ import annotations

from system_03_search_agent.contracts.events import CitationPayload, TokenPayload
from system_03_search_agent.contracts.token_order import (
    in_reading_order,
    joined_text,
    one_per_citation_id,
    placement_of,
    updates_citation,
)


def _tok(text: str, placement: str | None = None) -> TokenPayload:
    if placement is None:
        return TokenPayload(text=text, marker_ids=[])
    return TokenPayload(text=text, marker_ids=[], placement=placement)  # type: ignore[arg-type]


def test_listing_before_summary_reads_summary_first() -> None:
    tokens = [_tok("L1 ", "listing"), _tok("S1 ", "summary"), _tok("L2 ", "listing"), _tok("S2 ")]
    assert joined_text(tokens) == "S1 S2 L1 L2 "


def test_dicts_and_models_order_the_same() -> None:
    dicts = [{"text": "L ", "placement": "listing"}, {"text": "S "}]
    assert joined_text(dicts) == "S L "


def test_no_placement_is_arrival_order_unchanged() -> None:
    tokens = [_tok("a "), _tok("b "), _tok("c ")]
    assert in_reading_order(tokens) == tokens
    assert joined_text(tokens) == "a b c "


def test_unknown_placement_reads_as_summary() -> None:
    assert placement_of({"placement": "weird"}) == "summary"
    assert placement_of({"text": "x"}) == "summary"


# ---------------------------------------------------------------------------
# F-8.7-A04, card 57: one citation per id, the later payload kept when it
# is the same citation sent again with its checked words joined.
# ---------------------------------------------------------------------------


def _citation(
    citation_id: str = "c_1", index: int = 1, claim_text: str = "row words", **kw: str
) -> CitationPayload:
    fields: dict[str, object] = {
        "citation_id": citation_id,
        "display_index": index,
        "source": "MedGen",
        "source_id": f"MedGen:C{index}",
        "source_url": f"https://www.ncbi.nlm.nih.gov/medgen/C{index}",
        "layer": "layer_1_graph",
        "field": "name",
        "claim_text": claim_text,
        "evidence_kind": "curated assertion",
        "assertion_confidence": "not provided",
        "license": "public domain",
    }
    fields.update(kw)
    return CitationPayload(**fields)  # type: ignore[arg-type]


def test_a_citation_sent_again_with_its_checked_words_replaces_the_first() -> None:
    early = _citation("c_1", 1, "row words")
    other = _citation("c_2", 2)
    final = _citation("c_1", 1, "row words and the summary sentence")

    kept = one_per_citation_id([early, other, final])

    assert kept == [final, other]


def test_dicts_join_by_the_same_rule() -> None:
    early = _citation("c_1", 1, "row words").model_dump()
    final = _citation("c_1", 1, "row words and more").model_dump()

    assert one_per_citation_id([early, final]) == [final]


def test_a_repeat_with_another_number_or_record_is_not_an_update() -> None:
    """A chip's number or record never changes after it is shown: the first
    payload stays, the conflicting repeat is dropped (F-4.2-A-19,
    F-4.3-A-07)."""
    early = _citation("c_1", 1, "row words")
    renumbered = _citation("c_1", 2, "row words and more")
    other_record = _citation(
        "c_1", 1, "row words", source_url="https://www.ncbi.nlm.nih.gov/medgen/C9"
    )

    assert not updates_citation(early, renumbered)
    assert not updates_citation(early, other_record)
    assert one_per_citation_id([early, renumbered, other_record]) == [early]


def test_a_stream_with_no_repeated_id_is_unchanged() -> None:
    citations = [_citation("c_1", 1), _citation("c_2", 2), _citation("c_3", 3)]

    assert one_per_citation_id(citations) == citations
