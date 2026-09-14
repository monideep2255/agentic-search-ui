"""The structure of a written answer: paragraphs, headings, lists, tables.

UI fix set 9, items 9.3 to 9.10 (2026-09-13). The product owner asked for
Plain language answers in three short paragraphs and Researcher answers as a
full page under short topic headings, with the records found shown as a list
or a two-column table (the reference screenshot, which supersedes decision U2
for Researcher answers).

The constraint that shapes everything here: the grounding pass
(`synthesis/grounding.py`) splits a narrative on sentence boundaries and
accepts a clause only by deterministic containment against the finding it
cites. Structure cannot ride inside that text, because a heading is not a
sentence and a blank line is not punctuation. So structure travels BESIDE the
grounded sentences:

- `parse_synth_layout` reads the model's reply into heading and paragraph
  blocks before grounding.
- `grounding_input` joins the paragraphs into the one narrative the grounding
  pass has always received, and records which paragraph each input sentence
  came from. `GroundingResult.sentence_origins` then maps every SURVIVING
  sentence back to its paragraph, so nothing about what the pass accepts
  changes.
- A heading is model text that is not a claim, so it is never grounded as
  one. It is shown only if `heading_is_supported` holds: every content word
  is either a fixed topic word or a word the findings or the open question
  already carry. A heading can therefore label a topic and never assert a
  fact nothing retrieved supports.
- Lists and tables are never written by the model. `write_node` builds them
  in code from the prepared findings, one grounded sentence per record.

Depends on:
    - system_03_search_agent.synthesis.grounding (content_tokens,
      _split_sentences, _licensed_question_content, _canonicalize_relational)
    - system_03_search_agent.synthesis.findings (SynthFinding)

Reads:
    - Nothing. Pure transforms.

Writes:
    - Nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from system_03_search_agent.synthesis.findings import SynthFinding
from system_03_search_agent.synthesis.grounding import (
    _canonicalize_relational,
    _licensed_question_content,
    _split_sentences,
    content_tokens,
)

BlockKind = Literal["heading", "paragraph"]

# A heading line in the model's reply: "## Topic", one to six hashes.
_HEADING_LINE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
# A bullet the model was told not to write. Stripped so the line still reads
# as a sentence; the sentence itself is grounded like any other.
_BULLET_PREFIX = re.compile(r"^\s*(?:[-*•]|\d{1,2}[.)])\s+")
_TERMINAL = (".", ";", "?", "!")

MAX_HEADING_CHARS = 60
MAX_HEADING_WORDS = 8
MAX_HEADINGS = 6

# Topic words a heading may use without a finding carrying them. Nouns that
# name a section, never a verb or a qualifier that could assert something:
# "risk", "causes", "not" and every treatment word are deliberately absent.
HEADING_VOCABULARY: frozenset[str] = frozenset(
    {
        "overview", "background", "summary", "context", "details", "key",
        "findings", "evidence", "sources", "records", "record", "identity",
        "names", "name", "associations", "association", "associated", "related",
        "diseases", "disease", "conditions", "condition", "phenotypes",
        "phenotype", "variants", "variant", "genes", "gene", "function",
        "role", "clinical", "significance", "interpretation", "classification",
        "classifications", "susceptibility", "cancer", "cancers", "syndromes",
        "syndrome", "about", "means", "meaning", "linked",
    }
)


@dataclass(frozen=True)
class GroundingInput:
    """What the grounding pass reads, and how to map its output back.

    `narrative` is the joined paragraphs. `sentence_paragraph[i]` is the
    paragraph ordinal of input sentence `i`, as `_split_sentences` numbers it.
    `heading_before[p]` is the heading that directly precedes paragraph `p`,
    when there is one.
    """

    narrative: str
    sentence_paragraph: tuple[int, ...]
    heading_before: dict[int, str]


def parse_synth_layout(text: str) -> list[tuple[BlockKind, str]]:
    """Split a model reply into heading and paragraph blocks.

    A blank line ends a paragraph. A line opening with hashes is a heading.
    Every other line joins the paragraph it sits in with a single space, so a
    reply with no blank lines at all is one paragraph, which is exactly what
    the grounding pass read before this module existed.
    """
    blocks: list[tuple[BlockKind, str]] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            joined = " ".join(current).strip()
            if joined:
                blocks.append(("paragraph", joined))
            current.clear()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            flush()
            continue
        heading = _HEADING_LINE.match(line)
        if heading:
            flush()
            blocks.append(("heading", heading.group(1).strip()))
            continue
        bullet = _BULLET_PREFIX.match(line)
        if bullet:
            # A bullet is its own sentence: end the one before it.
            if current and not current[-1].endswith(_TERMINAL):
                current[-1] = current[-1] + "."
            line = line[bullet.end():].strip()
            if line and not line.endswith(_TERMINAL):
                line += "."
        current.append(line)
    flush()
    return blocks


def grounding_input(blocks: list[tuple[BlockKind, str]]) -> GroundingInput:
    """Join paragraph blocks for the grounding pass, keeping the mapping.

    Each paragraph is given terminal punctuation if it lacks it, so its last
    sentence can never fuse with the next paragraph's first. Headings are not
    part of the narrative at all.
    """
    paragraphs: list[str] = []
    heading_before: dict[int, str] = {}
    pending_heading: str | None = None
    for kind, text in blocks:
        if kind == "heading":
            pending_heading = text
            continue
        paragraph = text.strip()
        if not paragraph.endswith(_TERMINAL):
            paragraph += "."
        if pending_heading is not None:
            heading_before[len(paragraphs)] = pending_heading
            pending_heading = None
        paragraphs.append(paragraph)

    sentence_paragraph: list[int] = []
    for ordinal, paragraph in enumerate(paragraphs):
        sentence_paragraph.extend([ordinal] * len(_split_sentences(paragraph)))
    return GroundingInput(
        narrative=" ".join(paragraphs),
        sentence_paragraph=tuple(sentence_paragraph),
        heading_before=heading_before,
    )


def _supporting_tokens(synth_findings: list[SynthFinding], question: str) -> set[str]:
    support: set[str] = set()
    for finding in synth_findings:
        support |= content_tokens(
            f"{finding.field_value} {finding.field} {finding.field.replace('_', ' ')} "
            f"{finding.curie} {finding.entity_type}"
        )
    support |= content_tokens(_licensed_question_content(question))
    return _canonicalize_relational(support)


def heading_is_supported(
    heading: str, synth_findings: list[SynthFinding], question: str
) -> bool:
    """Whether a model-written heading may be shown.

    Deterministic, and deliberately strict. A heading passes only when it is
    short, carries no citation marker, and every content word is either in
    `HEADING_VOCABULARY` or already carried by a finding or by the open part
    of the question (the same licence `run_grounding_pass` gives a claim).
    """
    text = heading.strip().rstrip(":").strip()
    if not text or len(text) > MAX_HEADING_CHARS:
        return False
    if len(text.split()) > MAX_HEADING_WORDS or "[" in text or "]" in text:
        return False
    words = _canonicalize_relational(content_tokens(text))
    remaining = {word for word in words if word not in HEADING_VOCABULARY}
    return remaining <= _supporting_tokens(synth_findings, question)


# Fields whose value NAMES a record, and so is a key term worth bolding.
_NAME_FIELDS = frozenset({"name", "symbol", "title", "preferred_name", "description"})
MAX_EMPHASIS = 12
_MIN_TERM_CHARS = 3


def key_terms(synth_findings: list[SynthFinding], mentions: list[str]) -> list[str]:
    """The run's own entity names and record titles, longest first.

    Built only from what retrieval and entity resolution produced, never from
    the model, so a bold word always names something this run looked up.
    """
    terms: dict[str, str] = {}
    for mention in mentions:
        cleaned = mention.strip()
        if len(cleaned) >= _MIN_TERM_CHARS:
            terms.setdefault(cleaned.lower(), cleaned)
    for finding in synth_findings:
        if finding.curie_fallback:
            continue
        if finding.field not in _NAME_FIELDS and not finding.name_resolved:
            continue
        value = finding.field_value.strip()
        if _MIN_TERM_CHARS <= len(value) <= 200 and not value.isdigit():
            terms.setdefault(value.lower(), value)
    return sorted(terms.values(), key=len, reverse=True)


def emphasis_for(text: str, terms: list[str]) -> list[str]:
    """The substrings of `text` to bold, spelled exactly as they appear.

    Case-insensitive, whole-word, non-overlapping, longest term first, so
    "BRCA1" inside "BRCA1-associated" is still found but a term is never
    bolded inside another bolded term.
    """
    taken: list[tuple[int, int]] = []
    found: list[str] = []
    for term in terms:
        pattern = re.compile(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])", re.IGNORECASE)
        for match in pattern.finditer(text):
            span = match.span()
            if any(span[0] < end and start < span[1] for start, end in taken):
                continue
            taken.append(span)
            if match.group(0) not in found:
                found.append(match.group(0))
            if len(found) >= MAX_EMPHASIS:
                return found
    return found


# The one two-column mapping this graph's records can support. The graph has
# no variant-to-disease edge (`tools/cypher_templates.py`, the variants
# shape), so the screenshot's "variant, associated disease" table is not
# expressible from retrieved data. What one variant record DOES carry beside
# its name is its clinical significance, so that is the second column, read
# verbatim from the same record the row cites.
TABLE_COLUMNS: dict[str, tuple[str, str, str]] = {
    "SequenceVariant": ("clinical_significance", "Variant", "Clinical significance"),
}


# Fields that NAME a record, in preference order, for a list label.
_LABEL_FIELDS = ("name", "title", "symbol", "preferred_name")
_URL_PREFIX = re.compile(r"^\s*https?://", re.IGNORECASE)


def record_label(finding: SynthFinding, row_fields: dict[str, Any] | None) -> str:
    """The label a code-built list row shows for one record. Never a URL.

    UI fix set 9 follow-up (2026-09-14). Measured on the live GCK question: a
    ClinVar variant whose name is an intronic HGVS expression
    ("NM_000162.5(GCK):c.363+318G>A") trips `core.graph.
    _is_vocabulary_token_artifact`, as do its id ("ClinVar:1179956") and
    source ("ClinVar"), so `_pick_representative_field` returned
    `source_url` and the listing showed the record's URL as its name.

    The label is therefore chosen here, deterministically, from the record's
    own row: the first non-blank name-like field, then the finding's CURIE,
    then its value, skipping anything that is a URL. It is retrieved data
    shown verbatim beside the citation of the record it came from, never a
    rewording. The grounded sentence and its marker are unchanged.
    """
    for key in _LABEL_FIELDS:
        value = (row_fields or {}).get(key)
        if isinstance(value, str) and value.strip() and not _URL_PREFIX.match(value):
            return value.strip()[:500]
    for candidate in (
        finding.field_value if finding.field in _LABEL_FIELDS else "",
        finding.curie,
        str((row_fields or {}).get("id") or ""),
        finding.field_value,
    ):
        if candidate and candidate.strip() and not _URL_PREFIX.match(candidate):
            return candidate.strip()[:500]
    return finding.citation_id[:500]


def table_second_cell(entity_type: str, row_fields: dict[str, Any] | None) -> str | None:
    """The second column's value for one record, or None when it has none."""
    spec = TABLE_COLUMNS.get(entity_type)
    if spec is None or not row_fields:
        return None
    value = row_fields.get(spec[0])
    if isinstance(value, list):
        value = "; ".join(str(item) for item in value if isinstance(item, (str, int)))
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()[:500]
