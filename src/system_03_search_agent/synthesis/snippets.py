"""The one-sentence abstract snippet under a cited paper (build phase 8.8,
DECISIONS.md 2026-09-25, "card 44" and "answer on top, evidence below").

Product-owner decision: under each cited paper in the answer's sources
list, show the ONE sentence of that paper's OWN abstract that answers the
question, quoted verbatim and cited to that paper. Nothing is added to the
answer text itself. The LitSense route was closed because LitSense cannot
be pointed at a paper; this route cannot cite the wrong paper because the
sentence comes from the cited paper's own abstract, which the product
already fetches.

Two functions, split deliberately so the deterministic half never touches
a model:

    split_abstract_sentences: a pure, bounded sentence splitter. No model
        call, no network call, testable with nothing but strings in and
        strings out.
    pick_snippet: the one model call, routed through the classifier seam
        (`harness.decide.decide`), the same seam every other closed-option
        choice in the loop already goes through (`core.graph`'s
        "classifier seam, wired" section). It never paraphrases: the
        model picks WHICH sentence answers the question, or "none", and
        the sentence text returned is always one of the exact strings
        `split_abstract_sentences` produced, never text the model wrote.

Depends on:
    - system_03_search_agent.harness.decide (decide)
    - system_03_search_agent.harness.harness (Harness)

Reads:
    - Nothing beyond its arguments. No environment variable, no network
      call of its own; `decide()` is the only thing here that reaches a
      model, and it owns its own CLASSIFIER_PROVIDER read.

Writes:
    - Nothing. `pick_snippet` records its decision through `decide()`
      exactly like every other decision point; this module does not
      append to any log itself.

WIRED INTO THE LOOP (card 29, 2026-10-15): `core/graph.py`'s Write step
starts `pick_snippets` once, beside the writer, for the first
`MAX_SNIPPET_PAPERS` cited papers that have an abstract, and attaches each
verified sentence to that paper's citation. Each paper is its own
`pick_snippet` decision through `decide()` (Jev first, the guard tier when
Jev fails), all asked together. A retracted paper is never asked about, and
a sentence cut short by a trim is never offered or shown.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

from system_03_search_agent.contracts.events import DecisionRecord
from system_03_search_agent.harness.decide import decide
from system_03_search_agent.harness.harness import Harness

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# split_abstract_sentences: deterministic, bounded, no model, no network.
# ---------------------------------------------------------------------------

#: The count cap on what this function returns. An abstract is a few
#: hundred words in practice; this bound exists so a malformed or
#: adversarial "abstract" (production-standards.md's untrusted-content
#: gate: a Layer 3 fetch is data, never a trusted length) cannot make the
#: caller iterate an unbounded list.
MAX_SENTENCES: Final[int] = 40

#: The per-sentence character cap. Matches `CitationPayload.snippet`'s own
#: `max_length=500` (contracts/events.py): a sentence too long to ever fit
#: the field it would be stored in is not offered as a candidate at all,
#: rather than being truncated and handed to a model as something other
#: than the exact text it will be cited as.
MAX_SENTENCE_CHARS: Final[int] = 500

#: A sentence shorter than this many words is a fragment, not a claim: a
#: figure caption fragment, a running head, a stray heading line inside an
#: abstract field. Skipped rather than offered as a candidate.
MIN_SENTENCE_WORDS: Final[int] = 8

#: A private-use codepoint, never legitimately present in a PubMed
#: abstract, used to shield a period inside an abbreviation or a decimal
#: number from the sentence-boundary split, then restored afterward.
_PERIOD_SHIELD: Final[str] = ""

#: Abbreviations whose trailing period is not a sentence boundary. Matched
#: case-insensitively, longest-first is not required here because none is
#: a prefix of another in this list.
_ABBREVIATIONS: Final[tuple[str, ...]] = (
    "et al.",
    "e.g.",
    "i.e.",
    "cf.",
    "vs.",
    "approx.",
    "fig.",
    "figs.",
    "no.",
    "nos.",
    "dr.",
    "mr.",
    "mrs.",
    "ms.",
    "prof.",
    "inc.",
    "jr.",
    "sr.",
    "vol.",
    "ed.",
    "eds.",
    "eq.",
    "ref.",
    "refs.",
)

#: `\b` before the alternation is load-bearing, not decoration. Without it
#: "ed." (an abbreviation for "edition") matched inside the last four
#: letters of "tested.", "reported.", "increased." and every other past-
#: tense verb ending a sentence, which is most of them; a word boundary
#: only asserts between a word character and a non-word character (or a
#: string edge), and every character inside "tested" is a word character,
#: so `\btested` never crosses one, but `\bed\.` still matches a genuine
#: standalone "Ed." (e.g. "Ed. Smith"). Caught by
#: `test_et_al_does_not_split_the_sentence` before this guard existed:
#: that test's second sentence, "...cell line tested. A follow-up...",
#: silently failed to split at all.
_ABBREV_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:" + "|".join(re.escape(abbr) for abbr in _ABBREVIATIONS) + ")", re.IGNORECASE
)

#: A period between two digits, e.g. the "0.05" in "p < 0.05" or a percent
#: like "12.3%". Never a sentence boundary.
_DECIMAL_PERIOD: Final[re.Pattern[str]] = re.compile(r"(?<=\d)\.(?=\d)")

#: A sentence boundary: one or more of `.`, `!`, `?`, followed by
#: whitespace and then an uppercase letter, a digit (a sentence can open a
#: new numbered point), or end of string. The shielded periods above never
#: match this, because they are no longer literal periods by the time this
#: pattern runs.
_SENTENCE_BOUNDARY: Final[re.Pattern[str]] = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")

#: A crude, deliberately bounded stand-in for "this sentence has a verb".
#: No part-of-speech tagger is a dependency this module wants (production-
#: standards.md's untrusted-content gate already means every abstract
#: sentence is untrusted text handed to no model at this stage), so the
#: check is: does any word look like a finite or non-finite verb form,
#: either one of a fixed closed set of common auxiliary and copular verbs,
#: or a word ending in a common verb inflection. This under- and over-
#: matches at the margins by design; its only job is to reject a fragment
#: with no verb at all, such as a running head or a figure caption, not to
#: parse grammar.
_VERB_WORDS: Final[frozenset[str]] = frozenset(
    {
        "is", "are", "was", "were", "be", "been", "being",
        "has", "have", "had",
        "do", "does", "did",
        "can", "could", "will", "would", "shall", "should", "may", "might", "must",
    }
)
_VERB_SUFFIX_RE: Final[re.Pattern[str]] = re.compile(r"[a-z]{3,}(?:s|ed|ing)$")


def _looks_like_a_verb(word: str) -> bool:
    lowered = word.strip(".,;:()[]\"'").lower()
    if not lowered:
        return False
    if lowered in _VERB_WORDS:
        return True
    return bool(_VERB_SUFFIX_RE.search(lowered))


def _has_verb_like_token(sentence: str) -> bool:
    return any(_looks_like_a_verb(word) for word in sentence.split())


def _shield_periods(text: str) -> str:
    shielded = _ABBREV_PATTERN.sub(lambda m: m.group(0)[:-1] + _PERIOD_SHIELD, text)
    shielded = _DECIMAL_PERIOD.sub(_PERIOD_SHIELD, shielded)
    return shielded


def _unshield(sentence: str) -> str:
    return sentence.replace(_PERIOD_SHIELD, ".")


def split_abstract_sentences(text: str) -> list[str]:
    """Split `text` (a paper's abstract) into candidate sentences.

    Deterministic and bounded, per `goal-contracts.md`'s "a verify surface
    must state its own coverage": this function protects "et al.", "e.g.",
    "i.e." and a fixed list of similar abbreviations, and any period
    between two digits (a decimal number, including the "0.05" in a "p <
    0.05" style clause), from being read as a sentence boundary. It does
    NOT protect every abbreviation in the English language, an ellipsis
    followed by a capital letter, or a period inside a quotation mark
    immediately followed by a capital word; those remaining shapes are the
    coverage gap this docstring names rather than hides.

    A resulting fragment is dropped, never returned, when it has fewer
    than `MIN_SENTENCE_WORDS` words, when it has no verb-like token at all
    (`_has_verb_like_token`), or when it exceeds `MAX_SENTENCE_CHARS`
    characters (a sentence that long could never be stored in
    `CitationPayload.snippet` anyway, so it is not offered as a candidate).
    The returned list is capped at `MAX_SENTENCES` entries.

    Returns:
        The kept sentences, in the order they appeared in `text`, each
        stripped of leading and trailing whitespace, with no abbreviation
        or decimal period altered from the source text.
    """
    stripped = text.strip()
    if not stripped:
        return []

    shielded = _shield_periods(stripped)
    raw_pieces = _SENTENCE_BOUNDARY.split(shielded)

    sentences: list[str] = []
    for piece in raw_pieces:
        sentence = _unshield(piece).strip()
        if not sentence:
            continue
        if len(sentence) > MAX_SENTENCE_CHARS:
            continue
        word_count = len(sentence.split())
        if word_count < MIN_SENTENCE_WORDS:
            continue
        if not _has_verb_like_token(sentence):
            continue
        sentences.append(sentence)
        if len(sentences) >= MAX_SENTENCES:
            break
    return sentences


# ---------------------------------------------------------------------------
# pick_snippet: the one model call, through the classifier seam.
# ---------------------------------------------------------------------------

#: `DecisionRecord.options` (contracts/events.py) caps the options LIST at
#: 12 entries. One of those slots is always "none", so at most this many
#: sentence candidates are ever offered in a single decision.
MAX_CANDIDATE_SENTENCES: Final[int] = 11

#: How many leading sentences a long abstract keeps; the rest of the window
#: is its last sentences (`candidate_window`).
_HEAD_SENTENCES: Final[int] = 3

#: The option id meaning "no sentence in the abstract answers the
#: question". Always offered, always last.
_NONE_OPTION: Final[str] = "none"

_INSTRUCTIONS: Final[str] = (
    "The state is a question a person typed into a biomedical evidence search "
    "engine. Each numbered option is one verbatim sentence from a single "
    "paper's own abstract, to be shown under that paper. Pick the one sentence "
    "that states a finding or result that answers the question and can be read "
    "on its own, without the sentences before it. Aims, objectives, methods, "
    "scope, background and sentences saying what a review covers are not "
    "findings: pick 'none' when no sentence is a finding that answers the "
    "question. Never combine sentences, never reword: pick exactly one option "
    "as written."
)

_NONE_CRITERION: Final[str] = (
    "No sentence states a finding or result that answers the question and "
    "reads on its own. The closest ones are an aim, objective, method, scope, "
    "background or review-coverage sentence, lean on the sentences before "
    "them, or are about a different aspect of the subject."
)

#: How a trimmed abstract ends. `ncbi_eutils_actions._cap_text` appends the
#: first at 4,000 characters; the structured-field cap in
#: `harness/coordinator_worker.py` ends a 2,000-character trim with the
#: second. A sentence that reaches either is a fragment, never offered.
_TRIM_MARKER_TEXT: Final[str] = "[truncated]"
_TRIM_MARKER_ELLIPSIS: Final[str] = "\u2026"

#: The length at which the findings trim cuts a field value (2,000
#: characters, `synthesis.findings.MAX_FIELD_VALUE_CHARS`). A value this
#: long may have been cut without a marker.
TRIM_LIMIT_CHARS: Final[int] = 2000

#: A retraction or withdrawal NOTICE inside an abstract: the shape of a
#: publisher's notice about the paper itself ("This article has been
#: retracted", "Notice of retraction", "Elsevier Policy on Article
#: Withdrawal"). It reads no topic word of any question; it only recognises
#: a paper that says of itself that it was retracted. A paper whose
#: abstract carries one is treated as retracted, whatever its record says.
_RETRACTION_NOTICE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:this|the)\s+(?:article|paper|publication|manuscript|study|work|report)\b"
    r"[^.]{0,60}\b(?:retracted|withdrawn)\b"
    r"|\bretraction\s+notice\b|\bnotice\s+of\s+retraction\b"
    r"|\bwithdrawal\s+policy\b|\bpolicy\s+on\s+article\s+withdrawal\b"
    r"|\bhas\s+been\s+retracted\b",
    re.IGNORECASE,
)


def has_retraction_notice(text: str) -> bool:
    """Whether `text` (an abstract) carries a retraction or withdrawal notice."""
    return bool(text) and _RETRACTION_NOTICE.search(text) is not None


def abstract_candidates(abstract: str, *, cut: bool = False) -> list[str]:
    """The candidate window of `abstract`, with a trimmed tail left out.

    `cut` says the caller knows the text was trimmed. The trim markers are
    also read from the text itself. When the text was trimmed, its last
    piece ends mid-sentence, so it is never offered; neither is any
    sentence that ends in a trim marker.
    """
    text = abstract.strip()
    trimmed = cut
    if text.endswith(_TRIM_MARKER_TEXT):
        text = text[: -len(_TRIM_MARKER_TEXT)].rstrip()
        trimmed = True
    elif text.endswith(_TRIM_MARKER_ELLIPSIS):
        trimmed = True
    sentences = split_abstract_sentences(text)
    if trimmed and sentences and text.endswith(sentences[-1]):
        sentences = sentences[:-1]
    sentences = [
        sentence
        for sentence in sentences
        if not sentence.endswith((_TRIM_MARKER_ELLIPSIS, _TRIM_MARKER_TEXT))
    ]
    return candidate_window(sentences)


@dataclass(frozen=True)
class Snippet:
    """The one sentence chosen to sit under a cited paper.

    `text` is always one of the exact strings `split_abstract_sentences`
    returned for that paper's abstract: `pick_snippet` never lets a model's
    own wording reach this field. Never paraphrase, never join sentences.
    """

    text: str


def candidate_window(sentences: Sequence[str]) -> list[str]:
    """At most `MAX_CANDIDATE_SENTENCES` sentences to offer, in abstract order.

    An abstract with more sentences keeps its first `_HEAD_SENTENCES` and its
    last ones: the closing sentences of a structured abstract are where it
    states what it found, so cutting from the end would drop the likeliest
    answer. Position only; no word of the abstract or the question is read.
    """
    if len(sentences) <= MAX_CANDIDATE_SENTENCES:
        return list(sentences)
    tail = MAX_CANDIDATE_SENTENCES - _HEAD_SENTENCES
    return [*sentences[:_HEAD_SENTENCES], *sentences[-tail:]]


def _option_id(index: int) -> str:
    return f"s{index}"


def _index_from_option_id(option_id: str, candidate_count: int) -> int | None:
    if not option_id.startswith("s"):
        return None
    try:
        index = int(option_id[1:])
    except ValueError:
        return None
    if not (0 <= index < candidate_count):
        return None
    return index


async def pick_snippet(
    harness: Harness,
    trace_id: str,
    question: str,
    abstract_sentences: Sequence[str],
    on_decision: Callable[[DecisionRecord], None] | None = None,
) -> Snippet | None:
    """Ask `decide(point="write.snippet", ...)` which sentence, if any, of
    `abstract_sentences` most directly answers `question`.

    `abstract_sentences` is truncated to `MAX_CANDIDATE_SENTENCES` before
    building the decision (the abstract's own sentence order is preserved;
    a caller that cares which of a long abstract's sentences are offered
    should already have picked its most relevant slice, since this
    function does not re-rank). An empty `abstract_sentences` list is not
    a decision to make at all: `decide()` is never called, and this
    returns `None` immediately.

    Returns:
        A `Snippet` carrying the exact sentence text picked, or `None`
        when the sentence "none" was chosen, when nobody made a usable
        pick (`decide()`'s own fail-open path), or when the decision
        itself could not be reached at all. A failed decision returns
        `None`: show nothing. Silence is honest here; a wrong snippet is
        not, so this function never guesses.
    """
    candidates = candidate_window(abstract_sentences)
    if not candidates:
        return None

    options = [_option_id(i) for i in range(len(candidates))] + [_NONE_OPTION]
    criteria = {_option_id(i): sentence for i, sentence in enumerate(candidates)}
    criteria[_NONE_OPTION] = _NONE_CRITERION

    try:
        record = await decide(
            harness,
            trace_id,
            "write.snippet",
            question,
            options,
            instructions=_INSTRUCTIONS,
            criteria=criteria,
            default=_NONE_OPTION,
        )
    except Exception:  # noqa: BLE001 - a broken seam must never break the answer
        return None

    if on_decision is not None:
        on_decision(record)
    if record.chosen == _NONE_OPTION:
        return None
    index = _index_from_option_id(record.chosen, len(candidates))
    if index is None:
        return None
    return Snippet(text=candidates[index])


# ---------------------------------------------------------------------------
# pick_snippets: one decision per paper, all asked together.
# ---------------------------------------------------------------------------

#: The most papers one answer shows a sentence under (the owner's choice,
#: DECISIONS.md 2026-10-15): the first five cited papers with an abstract.
MAX_SNIPPET_PAPERS: Final[int] = 5


@dataclass(frozen=True)
class SnippetPaper:
    """One cited paper offered to the pick.

    `abstract` is the fullest text the caller holds. `cut` says it was
    trimmed (the caller knows the limit it came through). `retracted` says
    the paper's own record marks it retracted. A retracted paper uses its
    place among the first five and is never asked about.
    """

    key: str
    abstract: str
    cut: bool = False
    retracted: bool = False


def verified_sentence(sentence: str | None, abstract: str) -> str | None:
    """The sentence when it is word for word inside `abstract` and fits the
    field it is stored in, and is not a cut-off piece; otherwise None.

    `abstract` is the untrimmed text the sentence was drawn from, never a
    shortened copy of it.
    """
    if not sentence or sentence not in abstract or len(sentence) > MAX_SENTENCE_CHARS:
        return None
    if sentence.endswith((_TRIM_MARKER_ELLIPSIS, _TRIM_MARKER_TEXT)):
        return None
    return sentence


async def pick_snippets(
    harness: Harness,
    trace_id: str,
    question: str,
    papers: Sequence[SnippetPaper],
    on_decision: Callable[[DecisionRecord], None] | None = None,
) -> dict[str, str]:
    """The sentence that answers `question` for each of the first
    `MAX_SNIPPET_PAPERS` papers, as `{key: sentence}`.

    `papers` is in the order the answer lists them. A paper with no
    abstract, or none that splits into candidates, is skipped and uses no
    place. A retracted paper (its record says so, or its abstract carries a
    retraction notice) uses a place, is never asked about and shows
    nothing. Every other paper is asked on its own through `decide()` (Jev
    first, the guard tier when Jev fails), all together, each passing its
    record to `on_decision`. A paper whose pick is "none", unusable, cut
    off, or not word for word inside its own untrimmed abstract is left
    out. Never raises.
    """
    asked: list[tuple[str, str, list[str]]] = []
    seen: set[str] = set()
    placed = 0
    for paper in papers:
        if placed >= MAX_SNIPPET_PAPERS:
            break
        if not paper.abstract or not paper.abstract.strip() or paper.key in seen:
            continue
        candidates = abstract_candidates(paper.abstract, cut=paper.cut)
        if not candidates and not paper.retracted:
            continue
        seen.add(paper.key)
        placed += 1
        if paper.retracted or has_retraction_notice(paper.abstract):
            continue
        asked.append((paper.key, paper.abstract, candidates))
    if not asked:
        return {}

    picks = await asyncio.gather(
        *(
            pick_snippet(harness, trace_id, question, candidates, on_decision)
            for _key, _abstract, candidates in asked
        ),
        return_exceptions=True,
    )
    shown: dict[str, str] = {}
    for (key, abstract, _candidates), pick in zip(asked, picks, strict=True):
        if not isinstance(pick, Snippet):
            continue
        verified = verified_sentence(pick.text, _untrimmed(abstract))
        if verified is not None:
            shown[key] = verified
    return shown


def _untrimmed(abstract: str) -> str:
    """The abstract as the sentence was drawn from it, trim marker removed."""
    text = abstract.strip()
    if text.endswith(_TRIM_MARKER_TEXT):
        text = text[: -len(_TRIM_MARKER_TEXT)].rstrip()
    return text
