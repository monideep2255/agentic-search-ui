"""Reading order for answer tokens (build phase 8.7, T-8.7-03, card 50).

The server may send the record listing before the written summary. A surface
that joins token text into one answer, such as an agent, the command line, a
saved answer or the golden harness, must read the summary first, then the
listing, each in arrival order. This is the one place that rule lives.

A token without `placement`, or with a value this module does not know,
counts as the summary. Every stream built before this phase therefore joins
byte for byte as it did, in arrival order.
"""

from collections.abc import Iterable
from typing import Any, TypeVar

T = TypeVar("T")

LISTING = "listing"
SUMMARY = "summary"


def placement_of(token: Any) -> str:
    """The placement of one token, a payload model or a plain dict.

    Anything but the exact value "listing" reads as "summary".
    """
    if isinstance(token, dict):
        value = token.get("placement")
    else:
        value = getattr(token, "placement", None)
    return LISTING if value == LISTING else SUMMARY


def in_reading_order(tokens: Iterable[T]) -> list[T]:
    """The tokens with every summary token first, then every listing token.

    Stable: each group keeps its arrival order. A stream with no listing
    token comes back unchanged.
    """
    summary: list[T] = []
    listing: list[T] = []
    for token in tokens:
        (listing if placement_of(token) == LISTING else summary).append(token)
    return summary + listing


def joined_text(tokens: Iterable[Any]) -> str:
    """Token text joined in reading order, with no separator added."""
    return "".join(_text_of(t) for t in in_reading_order(tokens))


def _text_of(token: Any) -> str:
    if isinstance(token, dict):
        return str(token.get("text") or "")
    return str(getattr(token, "text", "") or "")
