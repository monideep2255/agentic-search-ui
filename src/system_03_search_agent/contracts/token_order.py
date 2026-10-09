"""Reading order for answer tokens (build phase 8.7, T-8.7-03, card 50).

The server may send the record listing before the written summary. A surface
that joins token text into one answer, such as an agent, the command line, a
saved answer or the golden harness, must read the summary first, then the
listing, each in arrival order. This is the one place that rule lives.

A token without `placement`, or with a value this module does not know,
counts as the summary. Every stream built before this phase therefore joins
byte for byte as it did, in arrival order.

Citations joined beside those tokens follow one rule too, also kept here
(F-8.7-A04, card 57): `one_per_citation_id`. A citation the listing sent
early is sent again once the summary is checked, with the same id, number
and record and the words each summary sentence was checked against joined
into `claim_text`. A surface keeps one row per citation id, the later
payload in place of the earlier.
"""

from collections.abc import Iterable, Mapping
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


#: The one field a citation sent again may change (F-8.7-A04, card 57):
#: its checked record words, which gain the summary sentences' words once
#: the summary is checked. Its number, record, link and every other field
#: stay as they were sent, because a chip with that number may already be
#: on screen.
CITATION_UPDATABLE_FIELDS = frozenset({"claim_text"})


def citation_fields(citation: Any) -> dict[str, Any]:
    """A citation's fields as a plain mapping, from a payload model or a dict."""
    if isinstance(citation, Mapping):
        return dict(citation)
    dump = getattr(citation, "model_dump", None)
    if callable(dump):
        fields = dump()
        if isinstance(fields, dict):
            return fields
    return dict(vars(citation))


def citation_id_of(citation: Any) -> str:
    """The citation's join key, `citation_id`, from a model or a dict."""
    return str(citation_fields(citation).get("citation_id") or "")


def updates_citation(earlier: Any, later: Any) -> bool:
    """True when `later` is `earlier` sent again: the same `citation_id` and
    every field equal except those in `CITATION_UPDATABLE_FIELDS`. Anything
    else sharing the id (another number, record or link) is a conflicting
    redefinition, never an update."""
    before = citation_fields(earlier)
    after = citation_fields(later)
    if not before.get("citation_id") or before.get("citation_id") != after.get("citation_id"):
        return False
    keys = (set(before) | set(after)) - CITATION_UPDATABLE_FIELDS
    return all(before.get(key) == after.get(key) for key in keys)


def one_per_citation_id(citations: Iterable[T]) -> list[T]:
    """One citation per `citation_id`, in the order the ids first arrived.

    A citation sent again (`updates_citation`) takes the earlier one's
    place, so its later `claim_text` is the one kept. Any other repeat of an
    id is dropped and the first kept, since a chip with its number may
    already be on screen. A stream with no repeated id comes back unchanged.
    """
    kept: list[T] = []
    position: dict[str, int] = {}
    for citation in citations:
        citation_id = citation_id_of(citation)
        if not citation_id:
            # No join key, so nothing can repeat it: kept as it came.
            kept.append(citation)
            continue
        at = position.get(citation_id)
        if at is None:
            position[citation_id] = len(kept)
            kept.append(citation)
        elif updates_citation(kept[at], citation):
            kept[at] = citation
    return kept
