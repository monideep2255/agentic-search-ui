"""Reading order for answer tokens (build phase 8.7, T-8.7-03, card 50)."""

from __future__ import annotations

from system_03_search_agent.contracts.events import TokenPayload
from system_03_search_agent.contracts.token_order import (
    in_reading_order,
    joined_text,
    placement_of,
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
