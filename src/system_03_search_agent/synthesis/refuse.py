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

# The cap that actually matters: the ENCODED url must fit the 512-character
# limit `TrustSignalPayload.fallback_link` declares, which is the same cap
# every `source_url` in this system respects.
#
# F-2.2-A-06 / J-03: capping the term at 300 CHARACTERS does not cap the
# link, because percent-encoding is not length-preserving. One character
# becomes up to nine bytes ("%F0%9F%98%80" for an emoji, "%E7%96%BE" for a
# CJK character), so 300 characters of non-ASCII text produced a 2746- and
# in one probe a 3646-character link. Two consequences, and the second is
# the serious one: the link blew the 512 cap that exists to keep it
# renderable, and `TrustSignalPayload` then rejected it with an unhandled
# `ValidationError` raised INSIDE the refuse path, which is the one path
# whose entire job is to fail gracefully. `write_node` also truncates the
# refusal token at 1000 characters, so before the validation error the user
# would have seen a URL cut mid-escape ("...%E7%96%BE%E"), a dead link
# offered as somewhere to go next.
MAX_ENCODED_LINK_CHARS = 512

# A starting cap on the term, tightened by the loop below until the encoded
# link fits. Not the guarantee, just the first guess.
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

    # Shrink the TERM until the ENCODED link fits, rather than truncating
    # the encoded string, which would cut a percent-escape in half and hand
    # the user a dead link. Dropping whole characters keeps every escape
    # intact, so a shortened link still resolves.
    while term:
        link = FALLBACK_BASE + urllib.parse.quote(term, safe="")
        if len(link) <= MAX_ENCODED_LINK_CHARS:
            break
        term = term[: len(term) - max(1, len(term) // 8)].rstrip()
    else:
        # Every character was dropped, so search the base with no term at
        # all. Still a working NCBI page, still not a dead end.
        link = FALLBACK_BASE

    if not _HOST_PATTERN.match(link):
        raise FallbackLinkError(
            "the constructed fallback link is not on an allowed NCBI host"
        )
    if len(link) > MAX_ENCODED_LINK_CHARS:
        # Unreachable given the loop above, and asserted rather than assumed
        # because the cost of being wrong is a ValidationError raised inside
        # the refuse path itself (J-03).
        raise FallbackLinkError(
            f"the constructed fallback link is {len(link)} characters, over "
            f"the {MAX_ENCODED_LINK_CHARS}-character limit"
        )
    return link


def build_refusal_text(query_term: str) -> str:
    """The user-facing refusal: the message, then the link.

    One string rather than a message plus a separate link field, because
    this is what reaches a `token` event and therefore what a user reads.
    The structured form travels on the `trust_signal` event alongside it.
    """
    return f"{REFUSE_MESSAGE} {build_fallback_link(query_term)}"
