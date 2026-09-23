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

# Decided from the user's chair on 2026-09-22, after the consistency run
# measured L-01 and its causes were read. A refusal must say what to type
# next, and an answer that lost a search must say so, or the reader takes
# "could not find" as "there is nothing on this" and a thinner answer as a
# complete one. Three wordings, each true of exactly one situation:
#
# - The question named nothing the product could look up. The graph tool's
#   own error text says so (`NO_ENTITY_REASON_MARKER` is its opening
#   clause), and the honest reply is to ask for a name.
# - A search failed for any other reason, a timeout being the measured one.
#   The honest reply is to say so and invite a retry.
# - Nothing failed and nothing was found: the original `REFUSE_MESSAGE`.
NO_ENTITY_REASON_MARKER = "no entity could be identified"
UNRESOLVED_QUESTION_MESSAGE = (
    "I could not tell which gene, variant, disease or organism you mean. "
    "Name one and I will search. Or try NCBI's cross-database search:"
)
FAILED_SEARCH_MESSAGE = (
    "One of my searches did not finish, so I could not find grounded "
    "evidence this time. Ask again to retry, or try NCBI's cross-database "
    "search:"
)
# Fix-plan item 12.7 (2026-09-23). A question that named no gene and no
# disease is now answered by searching the published literature for its own
# words, so when that search comes back empty the honest reply is to say
# what was searched and that nothing was found. The wording it REPLACES on
# this path is `UNRESOLVED_QUESTION_MESSAGE`, and that replacement is the
# point of the ticket: asking a person to "name a gene, variant, disease or
# organism" when they asked about caffeine and exercise demands a
# vocabulary they do not have and never will.
TOPIC_NOT_FOUND_PREFIX = "I searched the published literature for "
TOPIC_NOT_FOUND_SUFFIX = (
    " and found nothing. Try different words, or NCBI's cross-database "
    "search:"
)
# The searched words are the user's own, already stripped to letters,
# digits, apostrophes and hyphens by `breadth_plan._TOPIC_WORD`, and capped
# here as well so a pathological question cannot lengthen the sentence that
# reports it. Defence in depth, the same posture `build_fallback_link`
# takes towards its own input.
MAX_TOPIC_TERM_CHARS = 200


def topic_not_found_message(topic_term: str) -> str:
    """The refusal for a topic search that ran and matched nothing.

    `topic_term` is `breadth_plan.build_topic_term`'s output, the content
    words joined with ` AND `. It is shown to the reader with the operators
    turned back into plain words, since "coffee AND exercise AND effective"
    is machinery and "coffee, exercise, effective" is what they typed.
    """
    words = [part.strip() for part in topic_term.split(" AND ") if part.strip()]
    shown = ", ".join(words)[:MAX_TOPIC_TERM_CHARS].strip().rstrip(",")
    if not shown:
        return REFUSE_MESSAGE
    return f"{TOPIC_NOT_FOUND_PREFIX}{shown}{TOPIC_NOT_FOUND_SUFFIX}"


# The note under an answer that still stands but lost a search.
FAILED_SEARCH_NOTE = (
    "One of the background searches did not finish, so this answer may be "
    "missing sources. Ask again to retry."
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


def refusal_message_for(
    failed_searches: list[dict[str, str]] | None, topic_term: str | None = None
) -> str:
    """The refusal sentence that is true of what the act step recorded.

    `failed_searches` is `GraphState["failed_searches"]`: one mapping per
    planned call that ended with `status == "error"`, carrying the tool's
    own `reason`. A no-entity reason outranks any other, since a question
    the product could not read is the thing to fix before retrying.

    `topic_term` (fix-plan item 12.7) is set only when Plan took the topic
    path, meaning the question named no gene and no disease and the
    literature was searched for its own words instead. A FAILED search
    still outranks it, because "nothing was published" and "the search did
    not finish" are different facts and only one of them is this path's to
    report.
    """
    reasons = [str(item.get("reason") or "") for item in (failed_searches or [])]
    if any(NO_ENTITY_REASON_MARKER in reason for reason in reasons):
        return UNRESOLVED_QUESTION_MESSAGE
    if reasons:
        return FAILED_SEARCH_MESSAGE
    if topic_term:
        return topic_not_found_message(topic_term)
    return REFUSE_MESSAGE


def build_refusal_text(query_term: str, message: str = REFUSE_MESSAGE) -> str:
    """The user-facing refusal: the message, then the link.

    One string rather than a message plus a separate link field, because
    this is what reaches a `token` event and therefore what a user reads.
    The structured form travels on the `trust_signal` event alongside it.
    """
    return f"{message} {build_fallback_link(query_term)}"
