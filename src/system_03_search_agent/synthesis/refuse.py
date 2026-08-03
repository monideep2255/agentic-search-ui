"""Section 8.4: the refuse path, and why it is never a dead end.

A refuse is an intentional content-safety outcome, not a system failure.
Section 8.4 requires every refusal to carry an NCBI cross-database fallback
link, so a user who asked a reasonable question the graph cannot answer gets
somewhere to go rather than a shrug.

Depends on:
    - system_03_search_agent.tools.graph_schema_constants (NCBI_RECORD_URL_PATTERN)

Reads:
    - Nothing.

Writes:
    - Nothing.
"""

from __future__ import annotations

import re
import urllib.parse

from system_03_search_agent.tools.graph_schema_constants import NCBI_RECORD_URL_PATTERN

FALLBACK_BASE = "https://www.ncbi.nlm.nih.gov/search/all/?term="

REFUSE_MESSAGE = (
    "I could not find grounded evidence for this. Try NCBI's cross-database "
    "search:"
)

# The Section 9.3 host pin, applied to the CONSTRUCTED url rather than to
# the input. Same defense-in-depth posture as the redirect example in
# `production-examples.md`: validate what was built, never trust that the
# building code got it right.
_HOST_PATTERN = re.compile(NCBI_RECORD_URL_PATTERN)

# Bounds the query term reaching the URL. A 2000-character question (the
# `Query.text` cap) percent-encodes to well over the 512-character
# `source_url` cap every other URL in this system respects.
MAX_QUERY_TERM_CHARS = 300


class FallbackLinkError(ValueError):
    """Raised when a constructed fallback link fails its own host pin.

    Unreachable with the fixed base above, which is exactly why it raises
    rather than returning None: reaching it means `FALLBACK_BASE` was edited
    to point off NCBI, and a refusal quietly linking somewhere else is worse
    than a refusal that fails loudly in a test.
    """


def build_fallback_link(query_term: str) -> str:
    """Section 8.4's five construction steps.

    Step 3's `safe=""` is load-bearing and easy to get wrong: this is a full
    query string, not a path segment, so nothing is exempted from
    percent-encoding. Leaving `/` or `&` unencoded would let a crafted
    question inject an extra URL parameter into the link a refusal hands the
    user.
    """
    term = " ".join(query_term.split())[:MAX_QUERY_TERM_CHARS]
    encoded = urllib.parse.quote(term, safe="")
    link = FALLBACK_BASE + encoded
    if not _HOST_PATTERN.match(link):
        raise FallbackLinkError(
            "the constructed fallback link is not on an allowed NCBI host"
        )
    return link


def build_refusal_text(query_term: str) -> str:
    """The user-facing refusal: the message, then the link.

    One string rather than a message plus a separate link field, because
    this is what reaches a `token` event and therefore what a user reads.
    The structured form travels on the `trust_signal` event alongside it.
    """
    return f"{REFUSE_MESSAGE} {build_fallback_link(query_term)}"
