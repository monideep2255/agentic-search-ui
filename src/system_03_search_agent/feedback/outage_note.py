"""Date the outage note in a reopened answer (card 67, owner decision D17).

The live answer says a database "is down at NCBI right now" and "Try again
later". Saved as it stood and reopened days later, those words state an old
outage as current fact. A reopened answer's note must name the day the
answer was written instead.

WHERE THE DATE COMES FROM. The stored text cannot carry it: the answer
markdown is captured while the run is still streaming, and the row's
`created_at` is a server default the database fills on insert, so the
capture code does not hold the stored timestamp. Dating at save time would
mean a guessed clock, and it would leave every answer saved before this card
undated. So the date is written when the saved answer is read, from the
row's own `created_at`. One mechanism covers old and new rows, and no
schema change is needed.

The wording is matched, not flagged, because the stored note is plain text.
`core/graph.py`'s `_build_failed_search_note` is the producer of the three
live openers; `tests/unit/feedback/test_outage_note.py` builds each one from
that function and fails if this module stops recognising it. The older card
63 sentence ("has no papers from it") is covered too, since rows saved
before the wording change carry it.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

_SINGLE = re.compile(r"^(?P<name>[^.\n]+?) is down at NCBI right now, so ", re.MULTILINE)
_PLURAL = re.compile(r"^(?P<names>[^.\n]+?) are down at NCBI right now, so ", re.MULTILINE)
_GENERIC = re.compile(r"^Some of NCBI's databases are down right now, so ", re.MULTILINE)

_RETRY_NOW = "Ask the question again to search afresh."


def format_written_day(when: datetime) -> str:
    """`7 October 2026`: plain words, UTC, no leading zero."""
    moment = when.astimezone(UTC) if when.tzinfo else when
    return f"{moment.day} {moment.strftime('%B %Y')}"


def date_outage_notes(markdown: str, written_at: datetime) -> str:
    """Return `markdown` with each outage note anchored to the day it was written.

    A block without an outage opener is returned untouched, so an answer with
    no outage note is byte for byte what was saved.
    """
    day = format_written_day(written_at)
    lead = f"When this answer was written on {day}, "
    blocks = markdown.split("\n\n")
    changed = False
    for index, block in enumerate(blocks):
        new = _SINGLE.sub(
            lambda m: f"{lead}NCBI's {m['name']} database was not answering, so ", block, 1
        )
        if new == block:
            new = _PLURAL.sub(
                lambda m: f"{lead}{m['names']} were not answering at NCBI, so ", block, 1
            )
        if new == block:
            new = _GENERIC.sub(f"{lead}some of NCBI's databases were not answering, so ", block, 1)
        if new == block:
            continue
        blocks[index] = new.replace("Try again later.", _RETRY_NOW)
        changed = True
    return "\n\n".join(blocks) if changed else markdown
