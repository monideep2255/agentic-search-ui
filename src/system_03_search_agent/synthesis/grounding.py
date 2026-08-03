"""Section 8.2: deterministic cite-or-refuse.

This is the gate `production-standards.md` calls the single highest-leverage
correctness control in the system, and the reason it is deterministic is
stated there too: a fuzzy accept silently passes a hallucinated quote. There
is no similarity score anywhere in this module. A claim is grounded when the
normalized claim text and the normalized field value are equal, or one
contains the other. Nothing else grounds a claim.

The algorithm is Section 8.2's seven steps, in order:

    1. Parse the narrative for marker spans and the clause each is next to.
    2. Resolve the marker against the findings list given to THIS call.
    3. Extract the clause text as the claim.
    4. Normalize claim and field value.
    5. Match by equality or substring, never by similarity.
    6. Strip any clause that fails, marker included.
    7. If stripping removes the query's core ask, refuse the whole answer.

Depends on:
    - system_03_search_agent.synthesis.findings (SynthFinding)

Reads:
    - Nothing.

Writes:
    - Nothing.

## What "the clause a marker is adjacent to" means here

Section 8.2 step 1 says "the clause each one is adjacent to" without fixing
a clause boundary, so this module fixes one: a clause runs from the end of
the previous marker (or the start of the sentence, whichever is later) up to
the marker itself. Sentence boundaries are `.`, `;`, `?`, `!` followed by
whitespace; clause boundaries within a sentence are the markers themselves.

That definition is what makes rule 2 in the Synth instruction ("one marker
per fact") enforceable rather than advisory. Given

    BRCA1 has 15310 variants [1] and 4 associated diseases [2].

the claim bound to [1] is "BRCA1 has 15310 variants" and the claim bound to
[2] is "and 4 associated diseases". Each is checked against its own finding.
A single marker covering both facts would bind the whole span to one
finding, and the half it does not support fails the match and is stripped,
which is the correct outcome rather than a missed one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from system_03_search_agent.synthesis.findings import SynthFinding

_MARKER = re.compile(r"\[(\d{1,3})\]")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.;?!])\s+")

# Section 8.2 step 4. Leading and trailing punctuation is stripped; internal
# whitespace collapses to a single space. Deliberately does NOT strip
# internal punctuation: "MedGen:C0346153" must keep its colon, or every
# CURIE claim in the system stops matching the CURIE it cites.
_EDGE_PUNCTUATION = " \t\n.,;:!?()[]{}\"'`-"

# Framing language asserts nothing and therefore needs no marker (Section
# 8.1, "no narrative-only claims"). A clause opening with one of these is
# kept unmarked rather than stripped. Fixed lexicon, matched on a lowercase
# prefix: never a model judgment about whether a sentence "sounds factual".
FRAMING_OPENERS: tuple[str, ...] = (
    "in summary",
    "in short",
    "overall",
    "taken together",
    "to summarize",
    "based on the knowledge graph",
    "according to the knowledge graph",
    "based on the graph",
    "these results",
    "this answer",
    "note:",
)

# The exact string Section 8.2 and the Synth instruction both name, and the
# string `test_zero_retrieval_refusal` asserts on. Never reworded to make a
# test pass: per `goal-contracts`, changing the check so the check passes is
# a failed change.
REFUSAL_TEXT = "I could not find information on this."


# A comma or thin space sitting between two digits is a thousands
# separator, not punctuation between words. Matched with lookarounds so it
# only ever fires inside a number and can never touch a comma between
# words or a colon inside a CURIE.
_DIGIT_GROUP_SEPARATOR = re.compile(r"(?<=\d)[,  ](?=\d)")


def normalize(text: str) -> str:
    """Section 8.2 step 4: lowercase, collapse whitespace, strip edge punctuation.

    Plus one addition the spec does not list, recorded as F-2.2-05: a
    thousands separator inside a number is removed, so "15,310" and "15310"
    normalize to the same string.

    Measured, not anticipated. A finding carrying `variant_count: 15310`
    produced the answer "BRCA1 has 15,310 ClinVar variants [1]", which is
    correct, well cited, and was stripped, because "15310" is not a
    substring of "15,310". The user then got a refusal for a question the
    graph had answered perfectly.

    This widens what the gate accepts, which is the direction that needs
    justifying. Two reasons it is safe. It only equates two spellings of
    the same number, never two different numbers: the lookarounds confine
    it to a separator between digits, so "400" still fails against "15310"
    exactly as before. And `LEARNINGS.md`'s 2026-08-01 entry on the
    validator makes the cost case directly, from this repo's own history: a
    false reject means the user gets nothing, so a gate needs its cost side
    tested as hard as its block side.

    Filed alongside F-2.2-02 for the Step 6.2 reconciliation, since both
    touch a locked specification's matching rule.
    """
    collapsed = " ".join(text.lower().split())
    collapsed = _DIGIT_GROUP_SEPARATOR.sub("", collapsed)
    return collapsed.strip(_EDGE_PUNCTUATION)


def ground_claim(claim_text: str, field_value: str) -> bool:
    """Section 8.2 step 5, verbatim from the spec's own code block.

    Equality or containment, in either direction. An empty normalized field
    value never grounds anything: `"" in anything` is True in Python, so
    without this guard a finding whose value normalized away to nothing
    would ground every claim in the answer, including invented ones. That
    is the one substring-matching trap in this function.
    """
    a = normalize(claim_text)
    b = normalize(field_value)
    if not a or not b:
        return False
    return a == b or a in b or b in a


# Standalone integer tokens. `\b` on both sides is what keeps this from
# firing on the digits inside an identifier: "BRCA1" and "MedGen:C0346153"
# have no word boundary before their digits, so neither yields a token,
# while "15310" and "4" do.
_STANDALONE_NUMBER = re.compile(r"\b\d+\b")


def numbers_are_supported(
    claim_text: str,
    field_value: str,
    question: str = "",
    record_context: str = "",
) -> bool:
    """Every standalone number in a claim must appear in the value it cites.

    ## Why this exists, stated plainly because it is an ADDITION

    Section 8.2 step 5 accepts a claim when "one is a substring of the
    other", and the `b in a` direction of that rule has a hole this repo
    measured rather than theorized. Given a finding whose value is
    "15310", the clause

        BRCA1 has 15310 variants and 400 orthologs [1]

    grounds cleanly: the field value is a substring of the claim. The
    orthologs count is invented, carries a real marker, cites a resolving
    URL, and ships. That is build phase 2.1's exact failure shape (a
    fluent, fully-cited answer to a different question) relocated from
    retrieval into synthesis, and `ground_claim` as the spec writes it
    cannot see it.

    So this is a second, narrower check run after `ground_claim`, not a
    replacement for it. It targets numbers specifically because a number is
    the highest-risk invented content in a biomedical answer: a count, a
    position, an allele frequency, or a patient total is load-bearing,
    unverifiable by eye, and reads as authoritative. Names and identifiers
    are already constrained by `ground_claim` itself.

    It is deterministic, exact, and directional, per
    `production-standards.md`: no similarity, no tolerance, no partial
    credit.

    ## Status

    This is a TIGHTENING of a locked specification, so it is recorded as
    finding F-2.2-02 for the Step 6.2 reconciliation rather than treated as
    a silent local decision. It only ever rejects claims Section 8.2 would
    accept; it never accepts one Section 8.2 would reject, so it cannot
    weaken the gate. Per `goal-contracts`, adding a check to a verify
    surface is allowed and weakening one is not.

    ## Why numbers from the question are allowed

    `question` is not a loophole, it is what keeps this check aimed at the
    thing it is for. Measured on the live loop: asked "Which diseases are
    associated with NCBIGene:672?", the model correctly answered "The
    diseases associated with NCBIGene:672 include Disease record
    MedGen:C0346153 [1]". That clause carries the standalone number 672,
    which is not in the finding's value, so the first version of this check
    stripped the one sentence that actually answered the question.

    672 was not invented. The user supplied it, and restating the subject
    of a question is what a readable answer does. A number already in the
    question asserts nothing new, so it cannot be a fabricated fact. A
    number in neither the question nor the cited value came from the model,
    and that is exactly the case worth stripping.

    Both sides are normalized first, for the same reason `normalize` strips
    thousands separators (F-2.2-05): without it, "15,310" tokenizes as the
    two numbers 15 and 310, neither of which appears in "15310", so the
    check would reject the very claim it is meant to pass.

    `record_context` is the rest of the finding the claim cites, its CURIE
    above all. A finding rendered as "Gene NCBIGene:672, name: BRCA1 DNA
    repair associated" supports the clause "NCBIGene:672 is named BRCA1 DNA
    repair associated", which carries the standalone number 672 that is not
    in the field value. It is not invented either: it is the identifier of
    the very record being cited, and naming the record you are citing is
    what a readable answer does. Retrieved data is retrieved data wherever
    on the finding it sits.
    """
    normalized_value = normalize(field_value)
    allowed = set(_STANDALONE_NUMBER.findall(normalized_value))
    allowed |= set(_STANDALONE_NUMBER.findall(normalize(question)))
    allowed |= set(_STANDALONE_NUMBER.findall(normalize(record_context)))
    for number in _STANDALONE_NUMBER.findall(normalize(claim_text)):
        if number in allowed or number in normalized_value:
            continue
        return False
    return True


@dataclass(frozen=True)
class GroundedClaim:
    """One surviving claim and the finding that supports it."""

    claim_text: str
    finding: SynthFinding


@dataclass(frozen=True)
class GroundingResult:
    """The outcome of one grounding pass over one Synth narrative.

    `narrative` is what a surface may show. It contains only surviving
    clauses, with markers rewritten to the post-strip `display_index`
    numbering (Section 9.4 stage 2).

    `stripped_count` is retained for the eval harness and the audit trail
    per Section 8.2 step 6, and is never surfaced as a citation.
    """

    narrative: str
    claims: list[GroundedClaim]
    stripped_count: int
    refused: bool

    @property
    def grounded(self) -> bool:
        return bool(self.claims) and not self.refused


# Words that carry no claim of their own: articles, copulas, connectives, and
# the small vocabulary an answer uses to scaffold a sentence around a fact.
# A token outside this set is CONTENT, and content has to come from somewhere.
_FUNCTION_WORDS: frozenset[str] = frozenset(
    {
        "a", "an", "the", "this", "that", "these", "those", "it", "its", "they",
        "them", "their", "there", "here", "above", "below", "following",
        "is", "are", "was", "were", "be", "been", "being", "am",
        "has", "have", "had", "having", "do", "does", "did",
        "and", "or", "but", "also", "then", "while", "with", "plus", "as",
        "well", "of", "for", "to", "in", "on", "at", "by", "from", "into",
        "which", "who", "whose", "what", "when", "where",
        "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
        "ten", "both", "all", "each", "every", "any", "some", "no", "none",
        "include", "includes", "including", "included",
        "list", "lists", "listed", "listing",
        "show", "shows", "shown", "showing",
        "found", "identified", "returned", "retrieved", "reported",
        "record", "records", "result", "results", "row", "rows",
        "answer", "answers", "information", "data", "value", "values",
        "query", "search", "graph", "knowledge", "summary", "note", "overall",
        "taken", "together", "short", "based", "according", "accordingly",
        "respectively", "namely", "total", "count", "counts",
        # Ordinals and positional words. They order a list; they assert
        # nothing about its contents.
        "first", "second", "third", "fourth", "fifth", "sixth", "seventh",
        "eighth", "ninth", "tenth", "last", "next", "other", "others",
        "another", "same", "such", "only", "just", "further", "additional",
        # Verbs that attach a value to a record without asserting anything
        # beyond what the finding already says. "X is named Y" claims
        # exactly what "name: Y" on the finding claims.
        "named", "called", "titled", "labelled", "labeled", "known",
        "corresponds", "corresponding", "matches", "matching",
    }
)

# A token runs from an alphanumeric through any internal `:._-`, which is
# what keeps a CURIE ("medgen:c0346153"), a version ("nm_007294.4") and a
# hyphenated term whole. Trailing separators are trimmed afterwards, since
# a token's own punctuation is not part of it: without that, "name:" in the
# prose failed to match "name" on the finding, and a correct claim was
# stripped for a colon.
_TOKEN = re.compile(r"[a-z0-9][a-z0-9:._-]*")
_TOKEN_EDGE = ":._-"


def content_tokens(text: str) -> set[str]:
    """The tokens in `text` that assert something, function words removed."""
    tokens = set()
    for raw in _TOKEN.findall(normalize(text)):
        token = raw.strip(_TOKEN_EDGE)
        if token and token not in _FUNCTION_WORDS:
            tokens.add(token)
    return tokens


def claim_introduces_no_new_content(
    claim_text: str, supporting_text: str
) -> bool:
    """Every content token in the claim must come from somewhere real.

    ## Why this exists: F-2.2-A-01, A-03 and A-04, all confirmed exploitable

    Section 8.2's substring rule answers "does this clause MENTION the cited
    value". It has no mechanism for "is this clause TRUE about it", and the
    adversary pass on 2026-08-03 turned that gap into a working exploit.
    Every one of these grounded cleanly against a finding whose value is
    `MedGen:C0346153`, with `stripped_count=0` and `trust_outcome="answer"`:

        BRCA1 does not cause MedGen:C0346153
        There is no evidence that MedGen:C0346153 is linked to BRCA1
        MedGen:C0346153 may be curable with vitamin C
        MedGen:C0346153 is treated with pembrolizumab and olaparib
        Smith et al. disproved MedGen:C0346153

    A negation grounded as SUPPORT for the thing it denies. An invented drug
    regimen rode along on a matched identifier. `numbers_are_supported` could
    not see any of it, because `\\b\\d+\\b` never fires inside
    `MedGen:C0346153` (no word boundary before the digits).

    Rather than enumerate the ways a sentence can be false about a record,
    which is an infinite blocklist, this inverts the question into a finite
    allowlist: every content-bearing word in the claim must appear in the
    finding it cites or in the user's own question. `LEARNINGS.md`'s
    2026-08-01 entry on the Cypher validator records the same lesson from
    the same repo, in almost the same words: a blocklist of unsafe shapes is
    infinite while an allowlist of safe ones is finite, and the validator
    only stopped leaking once it flipped to fail-closed.

    So `not`, `cause`, `curable`, `vitamin`, `pembrolizumab` and `disproved`
    are all rejected for one reason rather than five: none of them is in the
    record, and none is in what the user asked.

    ## What this costs

    It rejects claims Section 8.2 would accept, so it can only tighten the
    gate, never loosen it. The cost is a false reject when a model reaches
    for an ordinary synonym the question did not use, and that cost is real:
    the answer is withheld rather than shown wrong. In a system where a
    confident wrong answer about a disease is worse than no answer, that is
    the correct direction to fail, and the premise gate measures the cost
    every run.

    Recorded as part of F-2.2-02 for the Step 6.2 spec reconciliation, since
    it tightens a locked specification.
    """
    return content_tokens(claim_text) <= content_tokens(supporting_text)


def _is_framing(clause: str) -> bool:
    """Whether a clause is pure framing, and therefore needs no marker.

    ## Why this is not a prefix test: F-2.2-A-02, confirmed CRITICAL

    Section 8.1 exempts framing language ("in summary", "taken together")
    from needing a marker, because it asserts nothing. The first
    implementation read that as a prefix test, and the adversary pass on
    2026-08-03 showed what a prefix test buys. This shipped whole, uncited,
    with `stripped_count=0` and `trust_outcome="answer"`:

        In summary, BRCA1 also causes Marfan syndrome and responds to
        high-dose vitamin C. Note: the ACMG classification for this variant
        is Pathogenic. These results show BRCA1 has 4102 pathogenic
        variants. Overall, patients should discontinue tamoxifen.

    Four fabricated clinical claims, an invented ACMG classification, an
    invented count, and a treatment-discontinuation instruction, all reaching
    the user because each sentence began with two exempt words. The audit
    trail reported that nothing had been removed.

    The exemption is for framing, not for anything WEARING framing. So the
    opener is stripped and what remains must itself assert nothing: a clause
    is framing only if every token left is a function word. "In summary, the
    following was found" survives. "In summary, BRCA1 causes Marfan
    syndrome" does not, and is stripped as the uncited factual claim it is.
    """
    lowered = normalize(clause)
    for opener in FRAMING_OPENERS:
        if not lowered.startswith(opener):
            continue
        remainder = lowered[len(opener) :].strip(" ,.;:")
        return not content_tokens(remainder)
    return False


def _asserts_something(text: str) -> bool:
    """Whether a span of text could be a factual claim at all.

    Punctuation and connectives left over between or after markers are not
    claims, and counting them as stripped claims inflates `stripped_count`
    and, worse, can push an otherwise-fine answer toward a refusal for
    having "lost" text that never carried meaning.

    Two rejections, both conservative:
      - no alphanumeric character at all (the "." after a trailing marker,
        or a stray bracket);
      - nothing but connective words (the "and" joining two marked clauses,
        as in "X [1] and Y [2]", where the "and" segment is the connective
        rather than a second claim).

    Anything with real words in it is treated as an assertion and must be
    marked. Erring that way is deliberate: a false positive here strips a
    sentence that should have carried a citation, which is visible and
    fixable, while a false negative ships an uncited factual claim, which
    is the failure this whole module exists to prevent.
    """
    if not any(character.isalnum() for character in text):
        return False
    words = [word for word in normalize(text).split() if word]
    return bool(words) and not all(word in _CONNECTIVES for word in words)


# Words that only ever join clauses. A segment made entirely of these is
# the connective between two marked facts, not a third unmarked one.
_CONNECTIVES: frozenset[str] = frozenset(
    {"and", "or", "but", "also", "then", "while", "with", "plus", "as", "well"}
)


def _split_sentences(narrative: str) -> list[str]:
    return [s for s in _SENTENCE_BOUNDARY.split(narrative.strip()) if s.strip()]


def _segments(sentence: str) -> list[tuple[str, int | None]]:
    """Split one sentence into `(text, marker_number_or_None)` segments.

    The text of each segment is what precedes its marker, back to the
    previous marker in the same sentence. A trailing segment with no marker
    (text after the last marker, or a whole sentence with no marker at all)
    comes back with `None`.
    """
    out: list[tuple[str, int | None]] = []
    cursor = 0
    for match in _MARKER.finditer(sentence):
        out.append((sentence[cursor : match.start()], int(match.group(1))))
        cursor = match.end()
    tail = sentence[cursor:]
    if tail.strip():
        out.append((tail, None))
    return out


def _clean_claim(text: str) -> str:
    """Strip a segment down to the claim itself, dropping leading glue.

    A mid-sentence segment starts with whatever separated it from the
    previous one: ", " in a list, "and " in a conjunction. That glue is
    part of the prose and is not part of the claim, so it is removed
    before matching and before being stored as a citation's `claim_text`.
    Leaving it in produced citations reading ", and Disease record
    MedGen:C4554406", which is the claim with a comma bolted to the front.
    """
    cleaned = text.strip().lstrip(",;: ").strip()
    lowered = cleaned.lower()
    for connective in ("and ", "or ", "but ", "also ", "then "):
        if lowered.startswith(connective):
            cleaned = cleaned[len(connective) :].strip()
            break
    return cleaned


def run_grounding_pass(
    narrative: str,
    synth_findings: list[SynthFinding],
    core_ask_required: bool = True,
    question: str = "",
) -> GroundingResult:
    """Run Section 8.2's seven steps over one Synth narrative.

    `core_ask_required` implements step 7. When True (the default, and what
    `write_node` passes for a real query), an answer that loses every one of
    its factual claims to stripping is discarded entirely and refuses,
    rather than shipping whatever framing sentences happened to survive.
    Shipping "In summary, these results are shown above." with nothing left
    under it is the thin, misleading answer step 7 exists to prevent.

    Marker renumbering happens here rather than in a later pass, because
    the surviving set is only known once stripping is done. Findings are
    renumbered by order of first appearance in the surviving prose, 1..M
    with no gaps (Section 9.4 stage 2). The `citation_id` on each
    `SynthFinding` is untouched: it is the stable join key, and
    `display_index` is a rendering field derived from position.
    """
    by_ref = {finding.ref_index: finding for finding in synth_findings}

    surviving_sentences: list[str] = []
    claims: list[GroundedClaim] = []
    stripped = 0
    # Maps a surviving finding's ref_index to its new 1-based display slot,
    # assigned on first appearance so the numbering matches reading order.
    display_slot: dict[int, int] = {}

    for sentence in _split_sentences(narrative):
        kept_parts: list[str] = []
        for text, marker in _segments(sentence):
            if marker is None:
                # Unmarked text. Framing is allowed to stand; anything else
                # that actually asserts something has nothing behind it and
                # is stripped (Section 8.1's no-narrative-only-claims rule).
                # Punctuation and bare connectives assert nothing and are
                # neither kept as claims nor counted as stripped ones.
                if not _asserts_something(text):
                    continue
                if _is_framing(text):
                    kept_parts.append(text.strip())
                else:
                    stripped += 1
                continue

            finding = by_ref.get(marker)
            if finding is None:
                # Step 2: the marker names a finding this call was never
                # given. Hallucinated. Drop the clause and the marker.
                stripped += 1
                continue

            claim_text = _clean_claim(text)
            if not _asserts_something(claim_text):
                # A marker with only punctuation or a connective in front of
                # it: "X [1] and [2]". Nothing is being claimed, so there is
                # nothing to ground and nothing to strip. The marker itself
                # is dropped, since a marker with no claim is an unbound
                # chip.
                continue
            # Everything the claim is allowed to draw on: the finding it
            # cites, and the question the user actually asked. Nothing else
            # is a source, so nothing else may appear as content.
            supporting_text = (
                f"{finding.field_value} {finding.field} {finding.curie} "
                f"{finding.entity_type} {question}"
            )
            if (
                # Section 8.2 step 5, as the spec writes it.
                not ground_claim(claim_text, finding.field_value)
                # F-2.2-02: invented NUMBERS.
                or not numbers_are_supported(
                    claim_text,
                    finding.field_value,
                    question,
                    record_context=f"{finding.curie} {finding.entity_type}",
                )
                # F-2.2-A-01/03/04: invented WORDS, including the negations
                # and reversals that made a finding support its own denial.
                or not claim_introduces_no_new_content(claim_text, supporting_text)
            ):
                # Steps 5 and 6: no similarity fallback, no partial credit.
                stripped += 1
                continue

            if finding.ref_index not in display_slot:
                display_slot[finding.ref_index] = len(display_slot) + 1
            # `text`, not `claim_text`: the original span carries the
            # separators that make the rebuilt sentence read as prose. The
            # cleaned form is what gets matched and stored as the claim.
            kept_parts.append(f"{text.rstrip()} [{display_slot[finding.ref_index]}]")
            claims.append(GroundedClaim(claim_text=claim_text, finding=finding))

        if kept_parts:
            rebuilt = "".join(kept_parts).strip()
            # A surviving fragment can begin with the glue that joined it to
            # a stripped predecessor. Reading ", and Disease record X [1]."
            # as a sentence is worse than reading it without the comma.
            rebuilt = _clean_claim(rebuilt)
            if rebuilt and not rebuilt.endswith((".", ";", "?", "!")):
                rebuilt += "."
            if rebuilt:
                surviving_sentences.append(rebuilt)

    if core_ask_required and not claims:
        # Step 7: stripping removed the query's core ask. Discard the
        # partial narrative rather than ship a thin one.
        return GroundingResult(
            narrative="", claims=[], stripped_count=stripped, refused=True
        )

    return GroundingResult(
        narrative=" ".join(surviving_sentences).strip(),
        claims=claims,
        stripped_count=stripped,
        refused=False,
    )


def display_index_by_citation_id(result: GroundingResult) -> dict[str, int]:
    """Map each surviving finding's stable `citation_id` to its rendered slot.

    Section 9.4 is explicit that these are two different keys with two
    different jobs: `citation_id` is the opaque, stable binding key a
    `token` event's `marker_ids` carries and the audit trail keys on, and
    `display_index` is the number a surface prints. This function is the one
    place the two are related, so nothing downstream has to re-derive it and
    risk deriving it differently.
    """
    slots: dict[str, int] = {}
    for claim in result.claims:
        if claim.finding.citation_id not in slots:
            slots[claim.finding.citation_id] = len(slots) + 1
    return slots
