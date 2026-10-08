"""Put the outage note of a reopened answer in the past tense (card 67).

The live answer says a database "is down at NCBI right now" and "Try again
later". Saved as it stood and reopened days later, those words state an old
outage as current fact. A reopened answer's note says instead that the
database was not answering when the answer was written, and that asking
again searches afresh.

NO DATE IN THE SENTENCE. The saved screen already shows when the question
was asked, in its header and in the reader's own time zone, and MCP's
`reopen_past_answer` returns the same instant as `asked_at` with its UTC
offset. A date written into the note would be a second statement of the
same fact that could disagree with the first (a UTC day under a local
evening header is the next day). The note points at the header's time by
saying "when this answer was written", so the two can never disagree.

WHY ON READING, NOT ON SAVING (decision D17 says "on saving"). The answer
markdown is captured while the run is still streaming, and the row's
`created_at` is a server default filled on insert, and every answer saved
before this card would stay in the present tense. Rewriting on read covers
old and new rows, and the stored text is never modified.

ONLY THE NOTE ITSELF IS REWRITTEN. `feedback/capture.py` stores a `note`
token as its own paragraph, and the note's text is exactly what
`core/graph.py`'s `_build_failed_search_note` returns. So a paragraph is
rewritten only when the WHOLE paragraph is one of those notes, word for
word, with a database name from the builder's own list. A table row, a list
item, a quote, or a paragraph that carries anything else (a record's text,
a writer's sentence) is never touched, even if it repeats the same words.

Two generations of wording are recognised: the current one (card 63's
second wording, "may be missing ... from it") and card 63's first wording
("PubMed's search is down ...", "The PubMed and ClinVar searches are
down ...", "Some of NCBI's searches are down ..."). An older note is
rewritten into the current past-tense wording, because the older one said
"has no papers from it", an absence card 63 withdrew (F-63-A01).

THE LENGTH LIMIT. The rewrite is longer than the note it replaces, and both
readers cap `answer_markdown` at `MAX_ANSWER_MARKDOWN`. When the rewritten
answer would exceed it, the stored text is returned unchanged: a present
tense note is better than an answer that will not open.

`tests/system_03_search_agent/feedback/test_outage_note_dated.py` builds
every live note from `_build_failed_search_note`, checks the database list
below against the builder's, and fails if this module stops recognising a
note or rewords one differently.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Final

from system_03_search_agent.feedback.capture import MAX_ANSWER_MARKDOWN

#: The databases `_build_failed_search_note` names, and what each holds, as
#: its `_DOWN_SOURCE_WORDS` spells them. A test keeps the two equal.
SOURCE_WORDS: Final[dict[str, str]] = {
    "PubMed": "papers",
    "ClinVar": "variant records",
    "OMIM": "records",
    "GEO DataSets": "datasets",
    "MedGen": "records",
    "Gene": "gene records",
}

_NAME = "(?:" + "|".join(re.escape(name) for name in SOURCE_WORDS) + ")"
_MISSING = "(?:" + "|".join(sorted({re.escape(w) for w in SOURCE_WORDS.values()})) + ")"
_NAMES = rf"{_NAME}(?:, {_NAME})* and {_NAME}"
_ALSO = " Another background search did not finish, so other sources may be missing too."
_TAIL = rf"(?P<also>{re.escape(_ALSO)})? Try again later\."

#: Each live or older note, as a whole paragraph and nothing else.
_SINGLE = (
    re.compile(
        rf"(?P<name>{_NAME}) is down at NCBI right now, so this answer may be missing "
        rf"(?P<missing>{_MISSING}) from it\.{_TAIL}"
    ),
    re.compile(
        rf"(?P<name>{_NAME})'s search is down at NCBI right now, so this answer has no "
        rf"(?P<missing>{_MISSING}) from it\.{_TAIL}"
    ),
)
_PLURAL = (
    re.compile(
        rf"(?P<names>{_NAMES}) are down at NCBI right now, so this answer may be missing "
        rf"sources from them\.{_TAIL}"
    ),
    re.compile(
        rf"The (?P<names>{_NAMES}) searches are down at NCBI right now, so this answer has "
        rf"nothing from them\.{_TAIL}"
    ),
)
_GENERIC = re.compile(
    r"Some of NCBI's (?:databases|searches) are down right now, so this answer may be "
    rf"missing sources from them\.{_TAIL}"
)

_WHEN = "When this answer was written, "
_ASK_AGAIN = " Ask the question again to search afresh."


def _past_tense(paragraph: str) -> str | None:
    """The paragraph's past-tense note, or None when it is not exactly a note."""
    for pattern in _SINGLE:
        match = pattern.fullmatch(paragraph)
        if match and SOURCE_WORDS[match["name"]] == match["missing"]:
            first = (
                f"{_WHEN}NCBI's {match['name']} was not answering, so this answer may be "
                f"missing {match['missing']} from it."
            )
            return first + (match["also"] or "") + _ASK_AGAIN
    for pattern in _PLURAL:
        match = pattern.fullmatch(paragraph)
        if match:
            first = (
                f"{_WHEN}NCBI's {match['names']} were not answering, so this answer may be "
                "missing sources from them."
            )
            return first + (match["also"] or "") + _ASK_AGAIN
    match = _GENERIC.fullmatch(paragraph)
    if match:
        first = (
            f"{_WHEN}some of NCBI's databases were not answering, so this answer may be "
            "missing sources from them."
        )
        return first + (match["also"] or "") + _ASK_AGAIN
    return None


def past_tense_outage_notes(markdown: str, written_at: datetime | None) -> str:
    """Return `markdown` with each outage note put in the past tense.

    Returned unchanged, the same string object, when nothing matched, when
    `written_at` is missing (the note points at the time the screen shows,
    and without one there is no time to point at), and when the rewritten
    answer would exceed `MAX_ANSWER_MARKDOWN`.
    """
    if written_at is None:
        return markdown
    paragraphs = markdown.split("\n\n")
    changed = False
    for index, paragraph in enumerate(paragraphs):
        rewritten = _past_tense(paragraph)
        if rewritten is not None:
            paragraphs[index] = rewritten
            changed = True
    if not changed:
        return markdown
    result = "\n\n".join(paragraphs)
    if len(result) > MAX_ANSWER_MARKDOWN:
        return markdown
    return result
