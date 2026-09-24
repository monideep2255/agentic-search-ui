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

Item 12.9 (2026-09-23, product owner: "The plain vs researcher should vary
duh for all questions. Not just a few"). The code-built half of the page now
speaks to its reader too, under the product owner's six rules:

- Rule 1: the opening sentence. Plain language reads "I found 5 published
  papers on this topic [1][2]...", everyday nouns and no titles inline
  (`answer_summary_sentence`'s plain branch, `plain_noun`); every other depth
  keeps the technical "Found 5 pubmed records: <titles>" form.
- Rule 2: the record list. Plain language gets ONE list under
  `PLAIN_SOURCES_HEADING`, titles only (`plain_record_label`); Researcher gets
  the records grouped by type as tables with an `IDENTIFIER_COLUMN_LABEL`
  column (`record_identifier`) and a status or year column where the record
  carries one (`record_status_or_year`).
- Rule 5, the line not crossed (Section 14.1's firewall): depth changes the
  wording, the headings, the layout and the display cells, NEVER which
  records are cited or listed. The grounded sentence behind every row, its
  marker and the citation set are built before any of this runs and are the
  same at every depth; everything in this module that reads the depth only
  chooses how an already-cited record is displayed.

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

from system_03_search_agent.core.next_step import entity_type_noun
from system_03_search_agent.synthesis.disease_names import (
    is_placeholder_condition_title,
    readable_disease_name,
)
from system_03_search_agent.synthesis.findings import SynthFinding, one_finding_per_record
from system_03_search_agent.synthesis.grounding import (
    _MARKER,
    GroundedClaim,
    GroundingResult,
    _canonicalize_relational,
    _licensed_question_content,
    _split_sentences,
    content_tokens,
    display_index_by_citation_id,
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


# The two-column mappings this graph's records support (variant-to-disease
# detail, 2026-09-14). The earlier version of this comment said the graph
# has no variant-to-disease edge; it has one, `has_phenotype` from a
# SequenceVariant to a Disease, asserted by ClinVar, and the fold templates
# in `tools/cypher_templates.py` write the linked Disease CURIEs onto each
# variant row as `clinvar_condition_ids` (and onto each gene row of the
# disease-genes shape as `medgen_condition_ids`). The second cell shows the
# MedGen titles those CURIEs resolve to, read live, never the CURIE.
TABLE_COLUMNS: dict[str, tuple[str, str, str]] = {
    "SequenceVariant": ("clinvar_condition_ids", "Variant", "Associated disease(s)"),
    "Gene": ("medgen_condition_ids", "Gene", "Associated disease"),
    # Product-owner direction 2026-09-14: a trial row has a second field of
    # its own, its recruitment status, read verbatim from the record.
    "Clinical trial": ("overall_status", "Trial", "Status"),
    # The isolate search (G-035, 2026-09-22): the person asked which
    # isolates carry the genes, so each row shows its AMR genotype list,
    # read verbatim from the record, beside the isolate's name.
    "Pathogen Detection isolate": ("amr_genotypes", "Isolate", "AMR genes"),
}

# The code-built heading over a mapping table, per anchor type, in place of
# the generic "<Type> records found".
TABLE_HEADINGS: dict[str, str] = {
    "SequenceVariant": "Variant-to-disease mapping",
    "Gene": "Gene-to-disease mapping",
    "Pathogen Detection isolate": "Isolates and their AMR genes",
}


# ---------------------------------------------------------------------------
# Item 12.9 (2026-09-23): what each depth's reader is shown.
# ---------------------------------------------------------------------------

#: The one depth that speaks to a reader with no technical background. Every
#: other depth (`researcher`, and the `clinical_brief` and `deep_technical`
#: values only GraphQL, the CLI and MCP can send) keeps the technical form,
#: so this item changes nothing for them beyond the Researcher tables.
PLAIN_LANGUAGE_DEPTH = "plain_language"

#: Rule 2's heading over the one plain-language list, in the product owner's
#: words.
PLAIN_SOURCES_HEADING = "Where this answer comes from"

#: The Researcher tables' identifier column. One label for every record
#: type, as the approved Researcher layout's mixed-record table has it
#: (`testing/Developer/reports/2026-09-14_handover_inputs/design/
#: Researcher.dc.html`), because a single table can hold a graph gene
#: ("NCBIGene:672") beside a live one, and each cell already names its own
#: system.
IDENTIFIER_COLUMN_LABEL = "Identifier"


def is_plain_language(audience_depth: str) -> bool:
    """Whether the code-built half of the page speaks plain language."""
    return audience_depth == PLAIN_LANGUAGE_DEPTH


#: Everyday nouns for rule 1, keyed by `entity_type_noun` of a record's type
#: (so the graph's "Gene" and `ncbi_efetch`'s "gene" share one entry), as
#: (singular, plural). The product owner named papers, clinical trials,
#: conditions, genes and genetic variants; the rest follow the same rule, a
#: word a reader with no technical background would use. A type not listed
#: is a "record", never a guess at what it is.
_PLAIN_NOUNS: dict[str, tuple[str, str]] = {
    "disease": ("condition", "conditions"),
    "medgen": ("condition", "conditions"),
    "gene": ("gene", "genes"),
    "sequence variant": ("genetic variant", "genetic variants"),
    "variant record": ("genetic variant", "genetic variants"),
    "literature variant": ("genetic variant", "genetic variants"),
    "clinvar": ("genetic variant", "genetic variants"),
    "dbvar": ("genetic variant", "genetic variants"),
    "clinical trial": ("clinical trial", "clinical trials"),
    "pubmed": ("published paper", "published papers"),
    "pmc": ("published paper", "published papers"),
    "publication": ("published paper", "published papers"),
    "article": ("published paper", "published papers"),
    "literature entity": ("literature index entry", "literature index entries"),
    "pathogen detection isolate": ("pathogen sample", "pathogen samples"),
    "organism taxon": ("organism", "organisms"),
    "taxonomy": ("organism", "organisms"),
    "biological process": ("body process", "body processes"),
    "molecular activity": ("molecular activity", "molecular activities"),
    "cellular component": ("part of the cell", "parts of the cell"),
    "ontology class": ("medical topic", "medical topics"),
    "mesh": ("medical topic", "medical topics"),
    "omim": ("genetics catalogue entry", "genetics catalogue entries"),
    "gtr": ("genetic test", "genetic tests"),
    "gds": ("research dataset", "research datasets"),
    "bioproject": ("research project", "research projects"),
    "biosample": ("biological sample", "biological samples"),
    "sra": ("sequencing dataset", "sequencing datasets"),
    "assembly": ("genome assembly", "genome assemblies"),
    "protein": ("protein", "proteins"),
    "chemical entity": ("chemical", "chemicals"),
}
_PLAIN_NOUN_FALLBACK = ("record", "records")


def plain_noun(entity_type: str, count: int = 1) -> str:
    """The everyday word for `count` records of `entity_type`."""
    singular, plural = _PLAIN_NOUNS.get(
        entity_type_noun(entity_type) if entity_type else "", _PLAIN_NOUN_FALLBACK
    )
    return singular if count == 1 else plural


#: The first column's label in a Researcher table whose type has no mapping
#: column of its own, keyed like `_PLAIN_NOUNS`. "Record" otherwise, the
#: approved layout's word for a table of mixed records.
_FIRST_COLUMN_LABELS: dict[str, str] = {
    "disease": "Disease",
    "medgen": "Disease",
    "gene": "Gene",
    "sequence variant": "Variant",
    "variant record": "Variant",
    "literature variant": "Variant",
    "clinvar": "Variant",
    "clinical trial": "Trial",
    "pubmed": "Paper",
    "pmc": "Paper",
    "publication": "Paper",
    "article": "Paper",
    "pathogen detection isolate": "Isolate",
}


def first_column_label(entity_type: str) -> str:
    """The label over a Researcher table's name column."""
    spec = TABLE_COLUMNS.get(entity_type)
    if spec is not None:
        return spec[1]
    return _FIRST_COLUMN_LABELS.get(entity_type_noun(entity_type) if entity_type else "", "Record")


#: The longest an identifier or a status cell may run. `CitationPayload.
#: source_id` is bounded at the same 128.
MAX_IDENTIFIER_CHARS = 128

#: A row field that IS its record's identifier, in the order
#: `core.graph._layer3_citation_for_synth_finding` reads a Layer 3 record's
#: identity, then the accession fields the Layer 2 summaries carry, each
#: with the prefix that makes a bare number say which system it belongs to.
#: The prefixes are the graph's own (`tools.graph_schema_constants.
#: CURIE_PREFIXES`), so a paper reads "PMID:..." whichever layer found it.
_IDENTIFIER_FIELDS: tuple[tuple[str, str], ...] = (
    ("nct_id", ""),
    ("pubtator_id", ""),
    ("rsid", ""),
    ("pmid", "PMID:"),
    ("biosample_acc", ""),
    ("accession", ""),
    ("project_acc", ""),
    ("assemblyaccession", ""),
    ("taxid", "NCBITaxon:"),
)

#: The Layer 2 databases whose records the graph also holds, and the graph's
#: CURIE prefix for them. Deliberately NOT MedGen: a MedGen ESummary's id is
#: its UID, and "MedGen:" in this graph prefixes a concept id (C0346153), a
#: different number, so the two must never be written the same way.
_LAYER2_CURIE_PREFIXES: dict[str, str] = {
    "pubmed": "PMID",
    "gene": "NCBIGene",
    "taxonomy": "NCBITaxon",
}


def record_identifier(
    row: dict[str, Any] | None, citation_source: str = "", citation_source_id: str = ""
) -> str:
    """The record's own identifier for a Researcher table cell, or "".

    Read only from the record itself, never from a model: first a row field
    that IS an identifier (`_IDENTIFIER_FIELDS`), then the graph row's CURIE,
    then, for a live NCBI record whose row keeps only its title (a PubMed
    paper's row is `{"title": ...}`), the record id its own citation already
    carries (`CitationPayload.source_id`, built from the same retrieved
    record by `tools.ncbi_efetch.build_layer2_citation`). So the cell always
    names the record the row's citation chip opens, in the words its source
    card uses.

    A bare Layer 2 number is given its system, "PMID:12345678" rather than
    "12345678", from `_LAYER2_CURIE_PREFIXES`; any other database is written
    as the source card writes it ("omim 138079").
    """
    fields = (row or {}).get("fields")
    if isinstance(fields, dict):
        for key, prefix in _IDENTIFIER_FIELDS:
            value = fields.get(key)
            if isinstance(value, bool) or not isinstance(value, (str, int)):
                continue
            text = str(value).strip()
            if not text:
                continue
            if prefix and not text.startswith(prefix):
                text = prefix + text
            return text[:MAX_IDENTIFIER_CHARS]
    curie = str((row or {}).get("curie") or "").strip()
    if curie:
        return curie[:MAX_IDENTIFIER_CHARS]
    source_id = (citation_source_id or "").strip()
    if not source_id or source_id == "unknown":
        return ""
    if not source_id.isdigit():
        return source_id[:MAX_IDENTIFIER_CHARS]
    database = (citation_source or "").strip()
    prefix = _LAYER2_CURIE_PREFIXES.get(database.lower())
    if prefix:
        return f"{prefix}:{source_id}"[:MAX_IDENTIFIER_CHARS]
    return (f"{database} {source_id}" if database else source_id)[:MAX_IDENTIFIER_CHARS]


#: A record's own status field, for the Researcher table's last column.
_STATUS_FIELDS: tuple[str, ...] = ("overall_status", "assemblystatus")

#: A record's own date fields, each with the label its year is shown under.
#: Only the year is shown, read from the field's own text.
_YEAR_FIELDS: tuple[tuple[str, str], ...] = (
    ("pdat", "Published"),
    ("publicationdate", "Published"),
    ("registration_date", "Registered"),
    ("submissiondate", "Submitted"),
    ("createdate", "Created"),
    ("collection_date", "Collected"),
)
_YEAR = re.compile(r"(?<!\d)(1[89]\d{2}|20\d{2})(?!\d)")


def record_status_or_year(
    entity_type: str, row_fields: dict[str, Any] | None, *, mapping_shown: bool = True
) -> tuple[str, str] | None:
    """`(column label, value)` for the Researcher table's status or year
    column, or None when the record's own fields carry neither.

    A status is shown verbatim; a date field contributes only its year,
    under a label naming what the date is ("Published", "Collected"). A
    field that is already this type's mapping column (a trial's
    `overall_status`) is skipped while that column is on the table
    (`mapping_shown`), so a table never shows one value twice, and is used
    here when it is not, so a status is never lost. Nothing here reads a
    model or fills a gap: a record with no such field gets None, and its
    cell stays empty.
    """
    if not isinstance(row_fields, dict):
        return None
    mapped = TABLE_COLUMNS.get(entity_type, ("",))[0] if mapping_shown else ""
    for key in _STATUS_FIELDS:
        value = row_fields.get(key)
        if key != mapped and isinstance(value, str) and value.strip():
            return ("Status", value.strip()[:MAX_IDENTIFIER_CHARS])
    for key, label in _YEAR_FIELDS:
        value = row_fields.get(key)
        if not isinstance(value, str):
            continue
        match = _YEAR.search(value)
        if match:
            return (label, match.group(1))
    return None


def condition_ids_for_row(entity_type: str, row_fields: dict[str, Any] | None) -> list[str]:
    """The fold's CURIE list on one row, or an empty list."""
    spec = TABLE_COLUMNS.get(entity_type)
    if spec is None or not row_fields:
        return []
    value = row_fields.get(spec[0])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def condition_titles(
    curies: list[str], condition_names: dict[str, str | None] | None
) -> tuple[list[str], int, int]:
    """Resolve fold CURIEs to readable titles for display.

    Returns `(titles, placeholder_count, unresolved_count)`. A CURIE whose
    title is a ClinVar placeholder (`disease_names.PLACEHOLDER_CONDITION_
    TITLES`, exact match) is counted and not shown; a CURIE with no
    resolved title is counted and not shown either, so a raw MedGen code
    never reaches answer words.
    """
    titles: list[str] = []
    placeholders = 0
    unresolved = 0
    for curie in curies:
        title = (condition_names or {}).get(curie)
        if not isinstance(title, str) or not title.strip():
            unresolved += 1
            continue
        if is_placeholder_condition_title(title):
            placeholders += 1
            continue
        readable = clip_to_word(readable_disease_name(title.strip()), 200)
        if readable not in titles:
            titles.append(readable)
    return titles, placeholders, unresolved


# Fields that NAME a record, in preference order, for a list label.
#: The longest a record's own value may run in a label or a summary line.
#: Unchanged at 500; what changed on 2026-09-21 is WHERE it cuts.
MAX_LABEL_CHARS = 500


def clip_to_word(value: str, limit: int = MAX_LABEL_CHARS) -> str:
    """Clip `value` to `limit` characters WITHOUT cutting a word in half.

    Item 11.33. Measured live on develop: the BRCA1 gene summary rendered
    as "... and through the C-terminal d", and PubMed abstracts rendered as
    "... or 'mutational signatures', wer" and "... has been uncle". Every
    one of those is this function's caller slicing at exactly 500
    characters and landing mid-word, which makes the product look like it
    is quoting NCBI badly.

    The cause took two attempts to find, and the first investigation ruled
    this slice out on a measurement that looked decisive: the visible
    fragments were 49 to 153 characters, far short of 500, so a 500-char
    cap "could not" be responsible. What that missed is that a fragment
    began at the last sentence boundary INSIDE the 500-char slice, so the
    fragment's length says nothing about where the slice fell. The way it
    was finally settled is worth repeating: fetch the real source value and
    find the offset of the rendered fragment's end in it. It was 500
    exactly.

    Cuts at the last word boundary at or before `limit` and appends a
    single-character ellipsis, so the reader can see the value continues.
    A value with no whitespace before `limit` (a long identifier, an HGVS
    name) is cut at `limit` unchanged, because breaking such a value at an
    arbitrary point is worse than a hard cut and there is no word boundary
    to honour.

    Returns the value unchanged when it already fits, so nothing that fits
    today renders differently tomorrow.
    """
    text = value.strip()
    if len(text) <= limit:
        return text
    head = text[:limit]
    cut = head.rfind(" ")
    if cut <= 0:
        return head
    return head[:cut].rstrip(" ,;:") + "\u2026"


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
    # Answer quality fix (2026-09-14): a resolved MedGen title lives on the
    # finding, not the row (whose own `name` is the vocabulary artifact
    # F-2.1-B07 describes), so it is preferred over any row field. The row's
    # `vocabulary_artifact_fields` list is deliberately NOT consulted here:
    # measured live, it flags the intronic HGVS names this label exists to
    # show, so skipping flagged fields listed "ClinVar:1179956" in place of
    # "NM_000162.5(GCK):c.363+318G>A". The row's name is retrieved data
    # shown verbatim.
    if finding.name_resolved and finding.field_value.strip():
        return clip_to_word(finding.field_value)
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


def plain_record_label(
    finding: SynthFinding, row_fields: dict[str, Any] | None, identifier: str = ""
) -> str:
    """The one cell a plain-language list row shows: the record's title.

    Item 12.9, rule 2: titles only, no identifiers or type codes. It is
    `record_label` unchanged whenever that is a name or a title, which is
    nearly always. Only when the label is a code does the row read as its
    everyday noun instead ("Medical topic"), so no code reaches a reader who
    asked for plain language. A label is a code when it IS one of the
    record's codes (its identifier, its CURIE, its row `id`, the citation
    id), or when it carries the identifier's own accession as a word: the
    graph names every MeSH class "[MeSH] D000818" (golden question G-019),
    which is the identifier wearing a name. The record is not hidden: the
    row keeps its own grounded sentence and its citation chip, which is
    where the code lives for anyone who wants it.
    """
    label = record_label(finding, row_fields)
    codes = {
        code
        for code in (
            identifier,
            finding.curie,
            finding.citation_id,
            str((row_fields or {}).get("id") or ""),
        )
        if code
    }
    if label not in codes and not _carries_accession(label, codes):
        return label
    noun = plain_noun(finding.entity_type)
    return noun[:1].upper() + noun[1:]


def _carries_accession(label: str, codes: set[str]) -> bool:
    """Whether `label` contains a code's accession (the part after its last
    colon) as a whole word. Only accessions of five or more characters with
    a digit count, so a gene symbol or a short number in a real title can
    never trip it."""
    for code in codes:
        accession = code.rsplit(":", 1)[-1].strip()
        if len(accession) < 5 or not any(ch.isdigit() for ch in accession):
            continue
        if re.search(r"(?<![\w])" + re.escape(accession) + r"(?![\w])", label):
            return True
    return False


def table_second_cell(
    entity_type: str,
    row_fields: dict[str, Any] | None,
    condition_names: dict[str, str | None] | None = None,
) -> str | None:
    """The second column's value for one record, or None when it has none.

    A fold field (a list of CURIEs) becomes the resolved titles joined by
    "; ", through `condition_titles`. A row whose every CURIE was a
    placeholder or unresolved gets the EMPTY string, not None: the row
    still belongs in the table (its variant is a real, cited record) and
    an empty cell asserts nothing. None is only for a row with no fold
    field at all.
    """
    spec = TABLE_COLUMNS.get(entity_type)
    if spec is None or not row_fields:
        return None
    value = row_fields.get(spec[0])
    if isinstance(value, list):
        titles, _placeholders, _unresolved = condition_titles(
            condition_ids_for_row(entity_type, row_fields), condition_names
        )
        return "; ".join(titles)[:500]
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()[:500]


def placeholder_link_count(
    anchor_rows: list[tuple[str, dict[str, Any] | None]],
    condition_names: dict[str, str | None] | None,
) -> int:
    """How many links from the shown anchor rows pointed at a placeholder
    condition and were therefore not listed. `anchor_rows` is
    `(entity_type, row_fields)` per shown row. The real count, for the
    disclosure note under the table."""
    total = 0
    for entity_type, row_fields in anchor_rows:
        _titles, placeholders, _unresolved = condition_titles(
            condition_ids_for_row(entity_type, row_fields), condition_names
        )
        total += placeholders
    return total


def placeholder_links_note(count: int) -> str | None:
    """The disclosure under a mapping table (decision D2), or None."""
    if count <= 0:
        return None
    links = "link" if count == 1 else "links"
    return (
        f"{count} variant {links} to ClinVar placeholder conditions "
        "('not provided', 'not specified' or 'see cases') are not listed."
    )


# ---------------------------------------------------------------------------
# Answer quality fix (2026-09-14): a one-record restatement in Researcher
# prose, and the code-built summary sentence that opens an answer.
# ---------------------------------------------------------------------------


def _record_support_tokens(finding: SynthFinding) -> set[str]:
    """Every content token the record's own rendering carries: its value,
    its field name in both spellings, its CURIE, its type as written and as
    the plain noun a heading uses ("sequence variant")."""
    return _canonicalize_relational(
        content_tokens(
            f"{finding.field_value} {finding.field} {finding.field.replace('_', ' ')} "
            f"{finding.curie} {finding.entity_type} {entity_type_noun(finding.entity_type)}"
        )
    )


def is_record_restatement(
    sentence: str, cited: list[SynthFinding], shown: SynthFinding | None = None
) -> bool:
    """Whether a grounded prose sentence only restates one listed record.

    Measured live on "Variants in GCK causing MODY" in Researcher: the
    prose that survived the grounding pass was "The clinical trial named A
    Study of LY2599506 (...) [3]." five times over, and the code-built list
    under it then showed the same five trials again. A sentence is a
    restatement when it cites exactly one finding and every content word
    in it is already in that record's own rendering, so it adds nothing a
    reader does not get from the list row. A sentence that relates the
    record to the question's subject ("BRCA1 is associated with Familial
    cancer of breast [1]") carries words from the question and is kept.

    Deterministic containment over `content_tokens`, the same tokenizer the
    gate uses; never a similarity score.

    `shown` is the finding the listing actually renders for this record
    (item 12.12, 2026-09-23). Comparing against the CITED finding was wrong
    for a paper: a sentence drawn from its abstract was "already in the
    record", so it was dropped, while the list row shows only the title. The
    comparison is now against what the reader can see below the prose.
    """
    if len({finding.citation_id for finding in cited}) != 1:
        return False
    tokens = _canonicalize_relational(content_tokens(_MARKER.sub(" ", sentence)))
    return tokens <= _record_support_tokens(shown or cited[0])


def drop_record_restatements(
    grounding: GroundingResult, synth_findings: list[SynthFinding]
) -> tuple[GroundingResult, int]:
    """Remove one-record restatements from grounded prose, renumbering.

    For every depth since item 12.12 (2026-09-23), since every depth's
    code-built listing carries every prepared record: the prose is for what
    the list cannot say, so a sentence the list already says is dropped
    whole. A sentence carrying a quoted synthesis (items 12.9 and 12.10) is
    never a restatement: it says what a record means, not what it is. Nothing is written
    after the gate; sentences are only removed, and every record a dropped
    sentence cited is still cited by its list row.

    Returns the filtered result and how many sentences were dropped. The
    input is returned unchanged when its sentence structure is not known
    (a result built by hand) or when the one-claim-per-marker invariant
    `run_grounding_pass` maintains does not hold, so this can only ever
    remove what it can account for.
    """
    if not grounding.sentences or not grounding.claims:
        return grounding, 0
    claims = list(grounding.claims)
    shown_by_url = {
        (finding.source_url or "").strip(): finding
        for finding in one_finding_per_record(synth_findings)
        if (finding.source_url or "").strip()
    }
    cursor = 0
    kept: list[tuple[str, int, list[GroundedClaim]]] = []
    dropped = 0
    for sentence, origin in zip(grounding.sentences, grounding.sentence_origins, strict=False):
        marker_count = len(_MARKER.findall(sentence))
        if cursor + marker_count > len(claims):
            return grounding, 0
        own = claims[cursor : cursor + marker_count]
        cursor += marker_count
        cited = [claim.finding for claim in own]
        shown = shown_by_url.get((cited[0].source_url or "").strip()) if cited else None
        if (
            own
            and not any(claim.evidence_quote for claim in own)
            and is_record_restatement(sentence, cited, shown)
        ):
            dropped += 1
            continue
        kept.append((sentence, origin, own))
    if cursor != len(claims):
        return grounding, 0
    if not dropped:
        return grounding, 0

    old_slots = display_index_by_citation_id(grounding)
    kept_claims = [claim for _, _, own in kept for claim in own]
    filtered = GroundingResult(
        narrative="", claims=kept_claims, stripped_count=grounding.stripped_count, refused=False
    )
    new_slots = display_index_by_citation_id(filtered)
    citation_id_by_old = {slot: citation_id for citation_id, slot in old_slots.items()}

    def renumber(match: re.Match[str]) -> str:
        citation_id = citation_id_by_old.get(int(match.group(1)))
        if citation_id is None or citation_id not in new_slots:
            return match.group(0)
        return f"[{new_slots[citation_id]}]"

    sentences = tuple(_MARKER.sub(renumber, sentence) for sentence, _, _ in kept)
    return (
        GroundingResult(
            narrative=" ".join(sentences).strip(),
            claims=kept_claims,
            stripped_count=grounding.stripped_count,
            refused=False,
            sentences=sentences,
            sentence_origins=tuple(origin for _, origin, _ in kept),
        ),
        dropped,
    )


# Answer findings named inline in the summary sentence up to this many;
# beyond it the sentence carries the count and the list carries the names.
MAX_SUMMARY_NAMES = 6


def summary_label(finding: SynthFinding, row: dict[str, Any] | None) -> str:
    """The name the summary sentence prints for one answer finding, from
    the finding's own value when that value names the record, else the same
    label the list row shows. `row` is the dumped tool row, or None."""
    if finding.name_resolved or finding.field in _LABEL_FIELDS:
        return clip_to_word(finding.field_value)
    fields = (row or {}).get("fields")
    return record_label(finding, fields if isinstance(fields, dict) else None)


def answer_summary_sentence(
    answer_findings: list[SynthFinding],
    display_slots: dict[str, int],
    entity_label: str,
    total_available: int | None,
    row_for: Any,
    condition_names: dict[str, str | None] | None = None,
    *,
    audience_depth: str = "researcher",
) -> str | None:
    """The code-built sentence that opens an answer (2026-09-14).

    Item 12.9, rule 1 (2026-09-23): in plain language the same sentence
    speaks to a reader with no technical background: "I found 4 conditions
    related to BRCA1 [1][2][3][4]." Everyday nouns (`plain_noun`), no titles
    inline, and EXACTLY the records, the count, the total and the markers of
    the technical form below, in the same order, because both are built from
    the one `counted` list and the one fold computation here. Only the words
    around the markers differ. With no subject to name (a topic question
    names no gene), it says "on this topic", the question shown above it.

    "Found 4 disease records for BRCA1: Familial cancer of breast [1],
    ... and Fanconi anemia complementation group S [4]." or, past
    `MAX_SUMMARY_NAMES`, "Found 13 sequence variant records for GCK, of
    1333 available [1][2]...[13]."

    Every part is retrieval bookkeeping the code knows, in the same class
    as the truncation note and the listing headings: the count is the
    number of answer findings the answer cites, the nouns are the records'
    own types, the label is the entity the plan resolved, the total is the
    graph's own `total_available`, and each name is a finding's value as
    stored, with that finding's marker. It is not run through the grounding
    pass, which is written for MODEL prose and would reject its own count;
    it is instead built only from values the pass already accepted (every
    finding here has a display slot, so its list row or a prose clause
    grounded) and it cites every record it counts. None when no answer
    finding was cited, so a summary can never open a refusal.

    The fold clause (variant-to-disease detail, 2026-09-14). When cited
    anchor rows carry a fold (`condition_ids_for_row`), the Disease records
    those folds point at are reported as the anchors' LINKED diseases
    rather than counted as records of their own: "Found 13 sequence
    variant records for HNF1A, of 1212 available [1]...[13], linked to 6
    diseases: Maturity-onset diabetes of the young [14], Monogenic
    diabetes [15] and 4 others." The count is the distinct non-placeholder
    CURIEs across the cited anchors' folds; a disease is named only when
    it is itself a cited finding, with that finding's marker, and the rest
    are counted. Nothing here is written by a model.
    """
    cited = [f for f in answer_findings if f.citation_id in display_slots]
    if not cited:
        return None

    # Anchors: cited findings whose row carries a fold. Their linked CURIEs
    # decide which cited Disease findings move from the count to the clause.
    linked_curies: list[str] = []
    anchors: list[SynthFinding] = []
    for finding in cited:
        row = row_for(finding)
        fields = (row or {}).get("fields") if isinstance(row, dict) else None
        ids = condition_ids_for_row(finding.entity_type, fields if isinstance(fields, dict) else None)
        if ids:
            anchors.append(finding)
            for curie in ids:
                if curie not in linked_curies:
                    linked_curies.append(curie)
    linked_set = set(linked_curies)
    counted = [f for f in cited if not (anchors and f.curie in linked_set)]
    if not counted:
        counted = list(anchors)
    # Items 12.9 and 12.10 (2026-09-23), measured live: once the prose could
    # cite a paper's abstract as well as its title, "Found 10 pubmed records"
    # sat above a list of 5 papers, because two citations of one paper were
    # counted as two records. One record per page, keyed by exact
    # `source_url` as the list and the trust line key it, keeping the
    # finding that NAMES the record (its title) when there is one.
    by_page: dict[str, SynthFinding] = {}
    unkeyed: list[SynthFinding] = []
    for finding in sorted(counted, key=lambda f: display_slots[f.citation_id]):
        page = (finding.source_url or "").strip()
        if not page:
            unkeyed.append(finding)
            continue
        kept = by_page.get(page)
        if kept is None or (kept.field not in _LABEL_FIELDS and finding.field in _LABEL_FIELDS):
            by_page[page] = finding
    counted = list(by_page.values()) + unkeyed

    def joined(items: list[str]) -> str:
        return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]

    markers = sorted(display_slots[f.citation_id] for f in counted)
    total = (
        total_available
        if total_available is not None and total_available > len(counted)
        else None
    )
    # The fold: every linked condition's readable title, and the cited ones
    # named with their markers. One computation serves both depths, so the
    # plain sentence cannot cite a different condition from the technical one.
    titles: list[str] = []
    named_diseases: list[SynthFinding] = []
    if anchors:
        titles, _placeholders, _unresolved = condition_titles(linked_curies, condition_names)
        named_diseases = [
            f
            for f in sorted(cited, key=lambda f: display_slots[f.citation_id])
            if f.curie in linked_set
            and f.name_resolved
            and not is_placeholder_condition_title(f.field_value)
        ][:MAX_SUMMARY_NAMES]

    if is_plain_language(audience_depth):
        # Grouped by the everyday noun, so the graph's "Gene" and a live
        # "gene" record are one count, as they are in the technical form.
        nouns: dict[str, list[Any]] = {}
        for finding in counted:
            singular = plain_noun(finding.entity_type, 1)
            entry = nouns.setdefault(singular, [0, plain_noun(finding.entity_type, 2)])
            entry[0] += 1
        what = joined(
            [
                f"{count} {singular if count == 1 else plural}"
                for singular, (count, plural) in nouns.items()
            ]
        )
        about = (
            f" related to {clip_to_word(entity_label, 200)}"
            if entity_label and entity_label.strip()
            else " on this topic"
        )
        body = f"I found {what}{about}"
        if total is not None:
            body += f", out of {total} available"
        body += " " + "".join(f"[{slot}]" for slot in markers)
        if not titles:
            return body + "."
        conditions = "condition" if len(titles) == 1 else "conditions"
        clause = f", linked to {len(titles)} {conditions}"
        if named_diseases:
            clause += " " + "".join(f"[{display_slots[f.citation_id]}]" for f in named_diseases)
        return body + clause + "."

    counts: dict[str, int] = {}
    for finding in counted:
        noun = entity_type_noun(finding.entity_type) if finding.entity_type else "record"
        counts[noun] = counts.get(noun, 0) + 1

    def plural(noun: str, count: int) -> str:
        unit = "record" if count == 1 else "records"
        return f"{count} {noun} {unit}" if noun != "record" else f"{count} {unit}"

    parts = [plural(noun, count) for noun, count in counts.items()]
    what = joined(parts)
    subject = f" for {clip_to_word(entity_label, 200)}" if entity_label and entity_label.strip() else ""
    head = f"Found {what}{subject}"
    if total is not None:
        head += f", of {total} available"

    if len(counted) <= MAX_SUMMARY_NAMES:
        named = [
            f"{summary_label(f, row_for(f))} [{display_slots[f.citation_id]}]"
            for f in sorted(counted, key=lambda f: display_slots[f.citation_id])
        ]
        body = f"{head}: {joined(named)}"
    else:
        body = f"{head} " + "".join(f"[{slot}]" for slot in markers)

    if not titles:
        return body + "."
    others = len(titles) - len(named_diseases)
    noun = "disease" if len(titles) == 1 else "diseases"
    clause = f", linked to {len(titles)} {noun}"
    if named_diseases:
        clause += ": " + joined(
            [
                f"{clip_to_word(f.field_value, 200)} [{display_slots[f.citation_id]}]"
                for f in named_diseases
            ]
        )
        if others > 0:
            clause += f" and {others} {'other' if others == 1 else 'others'}"
    return body + clause + "."
