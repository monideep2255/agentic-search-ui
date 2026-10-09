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

from system_03_search_agent.contracts.events import source_page_key
from system_03_search_agent.core.next_step import entity_type_noun
from system_03_search_agent.synthesis.disease_names import (
    is_placeholder_condition_title,
    readable_disease_name,
)
from system_03_search_agent.synthesis.findings import (
    SynthFinding,
    one_finding_per_record,
)
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
# MedGen titles those CURIEs resolve to, looked up from NCBI, never the CURIE.
ISOLATE_ENTITY_TYPE = "Pathogen Detection isolate"

TABLE_COLUMNS: dict[str, tuple[str, str, str]] = {
    "SequenceVariant": ("clinvar_condition_ids", "Variant", "Associated disease(s)"),
    "Gene": ("medgen_condition_ids", "Gene", "Associated disease"),
    # Product-owner direction 2026-09-14: a trial row has a second field of
    # its own, its recruitment status, read verbatim from the record.
    "Clinical trial": ("overall_status", "Trial", "Status"),
    # The isolate search (G-035, 2026-09-22): the person asked which
    # isolates carry the genes, so each row shows its AMR genotype list,
    # read verbatim from the record, beside the isolate's name.
    ISOLATE_ENTITY_TYPE: ("amr_genotypes", "Isolate", "AMR genes"),
}

# The code-built heading over a mapping table, per anchor type, in place of
# the generic "<Type> records found".
TABLE_HEADINGS: dict[str, str] = {
    "SequenceVariant": "Variant-to-disease mapping",
    "Gene": "Gene-to-disease mapping",
    "Pathogen Detection isolate": "Isolates and their AMR genes",
}


# Card 32 (2026-09-25, product owner): "The variant-to-disease table says
# where it comes from." Pinned wording, exact, code-built and never
# model-written: the reader is told which two systems produced the two
# columns they are looking at, ClinVar for the variant-disease link and
# MedGen for the disease's own name.
#
# Card 23's fix round (2026-10-06, A-23-05): the first wording called every
# row a "ClinVar assertion", and beside a question about which diseases
# variants "cause" that read as "ClinVar says this variant causes this
# disease", under rows ClinVar classifies as likely benign or uncertain. The
# graph keeps no classification: the System 1 parser reads ClinVar's
# ClinicalSignificance, but the loaded SequenceVariant vertex and its
# `has_phenotype` edge carry neither it nor the review status (read-only
# probe, 2026-10-06), so the table cannot show it. The line says so instead
# of implying cause. "Looked up from NCBI", never "read live": the product
# owner's wording decision of 2026-10-06, since a title is kept for up to a
# week per process (`disease_names._CACHE_TTL_S`).
#
# Card 23's second part (2026-10-07): "Each row lists the conditions", not
# "Each row is a condition", because one row can name two conditions (live
# HNF1A c.737T>G: "Maturity-onset diabetes of the young type 3; Monogenic
# diabetes"). The screen keeps this line under its own table by its opening
# words, `VARIANT_TABLE_SOURCE_NOTE_PREFIX` in `frontend/src/hooks/
# useRunView.ts`; a test holds the two together.
VARIANT_TO_DISEASE_SOURCE_NOTE = (
    "Each row lists the conditions the variant's ClinVar record names; the "
    "record's classification (for example pathogenic, benign or uncertain) "
    "is not shown here. Disease names are MedGen titles looked up from NCBI."
)


def variant_to_disease_source_note(entity_type: str, mapped: bool) -> str | None:
    """The provenance note under the variant-to-disease mapping table, or
    None whenever that specific table is not the one on the page.

    `entity_type` is the anchor row type the table was built for and
    `mapped` is the same "does this group actually render as a mapping
    table" flag the caller already computes before choosing between
    `TABLE_HEADINGS[entity_type]` and the generic "records found" heading
    (`core.graph`'s `mapped` local, built from `TABLE_COLUMNS` membership
    and the second column actually carrying a value). Only
    `entity_type == "SequenceVariant"` with `mapped` true is the
    "Variant-to-disease mapping" table itself: the gene-to-disease table,
    the trial table, the isolate table and a plain variant list all pass a
    different value here and get None, so the note only ever sits under the
    one table it describes.
    """
    if entity_type != "SequenceVariant" or not mapped:
        return None
    return VARIANT_TO_DISEASE_SOURCE_NOTE


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


def collected_placeholder(label: str, row_fields: dict[str, Any] | None) -> str:
    """The cell for a "Collected" column on a row with no collection date:
    "Not recorded", so a blank never looks like a broken cell. Any other
    column, or a row that does carry a date field, stays empty."""
    if label != "Collected":
        return ""
    value = row_fields.get("collection_date") if isinstance(row_fields, dict) else None
    return "" if isinstance(value, str) and value.strip() else "Not recorded"


#: Card 94 (2026-10-09): what a "Collected" cell says when its record holds
#: no date. A cell that also carries a place says which half is missing.
NOT_RECORDED = "Not recorded"


#: Card 94 fix round (2026-10-09, J-94-01, A-94-05): the words a submitter
#: puts in a place field when there is no place. The first five, and the
#: "missing: <reason>" forms, are the INSDC missing value reporting list
#: (https://www.insdc.org/technical-specifications/missing-value-reporting/),
#: which BioSample and Pathogen Detection metadata follow. "NULL" is how a
#: graph row writes an empty field; "unknown", "N/A" and "NA" are the
#: informal forms submitters also use. Compared without case.
PLACE_PLACEHOLDERS = frozenset(
    {
        "missing",
        "not applicable",
        "not collected",
        "not provided",
        "restricted access",
        "null",
        "unknown",
        "n/a",
        "na",
    }
)
_MISSING_WITH_REASON = "missing:"
#: The mark a place cut at `MAX_IDENTIFIER_CHARS` ends with (J-94-02, A-94-06).
CUT_MARK = "\u2026"


def _is_placeholder(value: str) -> bool:
    """True for an INSDC missing-value word or a "missing: <reason>" form."""
    folded = value.strip().casefold()
    return folded in PLACE_PLACEHOLDERS or folded.startswith(_MISSING_WITH_REASON)


def isolate_place(entity_type: str, row_fields: dict[str, Any] | None) -> str | None:
    """An isolate row's own place, "" when it holds none, None for any other type.

    Card 94: "An isolate answer shows each isolate's place." Read verbatim
    from the isolate record's own `geo_loc_name`, the place Pathogen
    Detection holds for it ("USA: Minnesota"), never inferred. A missing
    value word ("missing", "not collected") is not a place, so the row reads
    as holding none. A place longer than `MAX_IDENTIFIER_CHARS` is cut and
    ends with a mark that says so, never cut silently.
    """
    if entity_type != ISOLATE_ENTITY_TYPE:
        return None
    value = row_fields.get("geo_loc_name") if isinstance(row_fields, dict) else None
    if not isinstance(value, str) or not value.strip() or _is_placeholder(value):
        return ""
    place = value.strip()
    if len(place) > MAX_IDENTIFIER_CHARS:
        return place[: MAX_IDENTIFIER_CHARS - len(CUT_MARK)].rstrip() + CUT_MARK
    return place


def collected_with_place(when: str, place: str) -> str:
    """An isolate's "Collected" cell: when, then where, each from its record.

    Card 94 (2026-10-09). The place shares the "Collected" cell rather than
    taking a fifth column, because a table row carries at most four cells
    (`contracts.events.TokenPayload.cells`). "2013, USA: Minnesota" reads as
    collected in 2013 in Minnesota. A half the record does not hold is
    named as missing, so a reader never takes a year for the whole story or
    a blank for a broken cell: "2013, place not recorded", "USA: Minnesota,
    date not recorded", and "Not recorded" when the record holds neither.
    """
    has_when = bool(when) and when != NOT_RECORDED
    if has_when and place:
        return f"{when}, {place}"
    if place:
        return f"{place}, date not recorded"
    if has_when:
        return f"{when}, place not recorded"
    return NOT_RECORDED


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


#: A ClinVar variant record's own page, the only source whose placeholder
#: condition the cell may attribute to "the ClinVar record" (card 103 fix
#: round, J-103-02).
_CLINVAR_VARIANT_PAGE = re.compile(
    r"^https://www\.ncbi\.nlm\.nih\.gov/clinvar/variation/[^/?#]+/?$"
)

#: The placeholder titles a cell quotes in the record's own words. Any other
#: placeholder ("see cases") reads as an instruction when quoted bare, so it
#: gets the generic wording instead (J-103-09, A-103-05).
_QUOTED_PLACEHOLDERS: tuple[str, ...] = ("not provided", "not specified")

EMPTY_CELL_LOOKUP_FAILED = "Name could not be looked up"
EMPTY_CELL_ONLY_PLACEHOLDER = "None named: the ClinVar record gives only a placeholder"


def empty_cell_reason(
    entity_type: str,
    row_fields: dict[str, Any] | None,
    condition_names: dict[str, str | None] | None,
    source_url: str | None = None,
) -> str:
    """Card 103: why a mapping cell shows no disease name, so a cell under
    "each row lists the conditions" is never blank without a reason.

    - Any linked condition whose name could not be looked up: "Name could
      not be looked up", alone. The record does link a condition there, so
      the cell never says "None named" beside it (J-103-01).
    - Otherwise, only on a ClinVar variant record's own row (a
      `SequenceVariant` whose `source_url` is a ClinVar variation page):
      placeholders "not provided" and "not specified" are quoted, "None
      named: the ClinVar record says not provided" (or "not specified", or
      both). Any other placeholder reads "None named: the ClinVar record
      gives only a placeholder".
    - A gene or any other row whose links are all placeholders, and a row
      with no linked condition at all, stay empty: the cell never names a
      source its own citation does not open (J-103-02, A-103-01).
    """
    curies = condition_ids_for_row(entity_type, row_fields)
    words: set[str] = set()
    other_placeholder = False
    unresolved = False
    for curie in curies:
        title = (condition_names or {}).get(curie)
        if not isinstance(title, str) or not title.strip():
            unresolved = True
        elif is_placeholder_condition_title(title):
            word = title.strip().casefold()
            if word in _QUOTED_PLACEHOLDERS:
                words.add(word)
            else:
                other_placeholder = True
    if unresolved:
        return EMPTY_CELL_LOOKUP_FAILED
    clinvar_record = entity_type == "SequenceVariant" and bool(
        _CLINVAR_VARIANT_PAGE.match((source_url or "").strip())
    )
    if not clinvar_record:
        return ""
    if other_placeholder:
        return EMPTY_CELL_ONLY_PLACEHOLDER
    if words:
        # Each placeholder said once, in a fixed order.
        said = " and ".join(word for word in _QUOTED_PLACEHOLDERS if word in words)
        return f"None named: the ClinVar record says {said}"
    return ""


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
        "('not provided', 'not specified' or 'see cases') are not listed as diseases."
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
    # Keyed by `source_page_key` (card 22), the one page key every count
    # uses, so a cited link with a trailing slash still finds its record.
    # Every listed row on a page is kept (card 22 last round, V-22-02):
    # `one_finding_per_record` groups by exact link, so the graph's gene
    # row and the live Datasets gene row are two rows on one page, and a
    # sentence is a restatement when it restates ANY of them. Keeping only
    # the last one written compared the sentence against the wrong row.
    shown_by_page: dict[str, list[SynthFinding]] = {}
    for finding in one_finding_per_record(synth_findings):
        page = source_page_key(finding.source_url)
        if page:
            shown_by_page.setdefault(page, []).append(finding)
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
        shown_rows: list[SynthFinding | None] = (
            list(shown_by_page.get(source_page_key(cited[0].source_url), [])) if cited else []
        ) or [None]
        if (
            own
            and not any(claim.evidence_quote for claim in own)
            and any(is_record_restatement(sentence, cited, shown) for shown in shown_rows)
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

# A token carries at most 20 `marker_ids` (`TokenPayload.marker_ids`), so a
# lead sentence that wrote more than 20 `[N]` markers showed the rest as raw
# bracketed text on screen. The lead line therefore writes at most this many
# markers; the records past it stay counted in the sentence and are listed
# and cited, one row each, in the record tables below.
MAX_SUMMARY_MARKERS = 20


@dataclass(frozen=True)
class AskedField:
    """The kind of fact a question asks for, as the loop was told it, what
    the loop knows about the source that carries it, and the record fields
    that would carry it (build phase 8.7, card 2).

    `label` is how the opening line names it ("clinical features").
    `field_names` are the row and finding fields that carry it. `source` is
    the database that carries it, as a person names it ("MedGen"), so the
    line says whose record was read. `lists_none_prefix` opens the one
    code-built statement that says a record was fetched, read, and lists
    none ("MedGen lists no clinical features for "); a record has positive
    evidence of absence only through that statement. `quiet_fields` are the
    fields the source's own rows carry beside it that say nothing about the
    record's content (a count of zero, the record's own title).
    `every_search_finished` is the loop's record that no search of this
    question failed or timed out.

    Supplied by the loop from a decision already made (today
    `think.asks_features`), never read off the question's words
    (DECISIONS.md 2026-09-24). No field has a default, so a caller cannot
    leave the source state unsaid and get the clause by accident.
    """

    label: str
    field_names: tuple[str, ...]
    source: str
    lists_none_prefix: str
    quiet_fields: tuple[str, ...]
    every_search_finished: bool


#: Fields that name, identify or classify a record and so say nothing about
#: what the record contains: the label fields, the CURIE a finding falls back
#: to, and MedGen's closed `semantictype` vocabulary. Every OTHER field with
#: a value (a definition, a summary, an abstract, a description, a list of
#: linked conditions, any field added later) might carry the asked-for fact
#: in its own words, and code cannot read prose for it, so its presence means
#: the absence is not known (F-8.7-J01, F-8.7-A03).
_IDENTITY_FIELDS: frozenset[str] = frozenset((*_LABEL_FIELDS, "curie", "semantictype"))


def _has_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return value not in (None, [], {}, ())


def records_lack_field(
    counted: list[SynthFinding],
    all_findings: list[SynthFinding],
    row_for: Any,
    asked: AskedField,
) -> bool:
    """Whether the product positively KNOWS that no record in this answer
    gives the asked-for field. The check behind the honest-gap clause of
    `answer_summary_sentence`.

    The user's chair: a confident wrong absence is worse than saying
    nothing. So the answer is True only when all four of these hold, each
    decided from the state of the field's source, never from wording:

    1. Every search of this question finished (`every_search_finished`).
       A search that failed or timed out may be the one that carries the
       field (F-8.7-A02).
    2. The source was searched, the search came back and was read, for
       EVERY counted record: each has its own code-built "lists none"
       statement (`lists_none_prefix`) on the same record page. A record
       whose field was never read, could not be read, or comes from a
       source the lookup never touches (a graph-only row, a variant, a
       gene) has no such statement, so nothing is known about it and the
       clause is not said (F-8.7-J02, F-8.1-J11, F-8.7-A13).
    3. No finding shown in this answer, counted or not, gives the field, or
       gives anything but an identity field (`_IDENTITY_FIELDS`) or one of
       the source's quiet fields. A definition, summary, abstract or
       description might state the field in prose (F-8.7-J01, F-8.7-A03).
    4. The same holds for every field of every shown record's row, which
       the listing can show beside its label.
    """
    names = set(asked.field_names)
    if not names or not asked.every_search_finished or not counted:
        return False
    quiet = _IDENTITY_FIELDS | set(asked.quiet_fields)

    def lists_none(field: str, value: Any) -> bool:
        return (
            field in names
            and isinstance(value, str)
            and value.startswith(asked.lists_none_prefix)
        )

    def says_nothing(field: str, value: Any) -> bool:
        if lists_none(field, value):
            return True
        if field in names:
            return not _has_value(value)
        return field in quiet or not _has_value(value)

    read_and_none: set[str] = set()
    shown = list(all_findings) + [f for f in counted if f not in all_findings]
    for finding in shown:
        if lists_none(finding.field, finding.field_value):
            page = source_page_key(finding.source_url)
            if page:
                read_and_none.add(page)
        elif not says_nothing(finding.field, finding.field_value):
            return False
        row = row_for(finding)
        fields = row.get("fields") if isinstance(row, dict) else None
        if isinstance(fields, dict):
            for name, value in fields.items():
                if not says_nothing(str(name), value):
                    return False
    for finding in counted:
        page = source_page_key(finding.source_url)
        if not page or page not in read_and_none:
            return False
    return True


def _gap_clause(record_count: int, asked: AskedField) -> str:
    """The words the opening line adds when the records are known to lack
    what was asked. They name the source's RECORD as what lists nothing, in
    both depths, so no reader can take them as a fact about the condition
    itself (F-8.7-A13): "and its MedGen record lists no clinical features",
    never "which does not give clinical features" after "3 conditions"."""
    if record_count == 1:
        return f", and its {asked.source} record lists no {asked.label}"
    return f", and none of their {asked.source} records lists {asked.label}"


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
    asked_field: AskedField | None = None,
    all_findings: list[SynthFinding] | None = None,
) -> str | None:
    """The code-built sentence that opens an answer (2026-09-14).

    The honest gap (build phase 8.7, card 2; fix round, F-8.7-J01, J02,
    A02, A03, A13). When the loop says what kind of fact the question asks
    for (`asked_field`) and the product positively knows that no record
    shown in the answer gives it (`records_lack_field`: every search
    finished, the field's source read every counted record and found none,
    and no shown finding or row carries anything that might state it), the
    line ends by saying so, naming the source's record as what lists
    nothing: "Found 1 disease record for Marfan syndrome: Marfan syndrome
    [1], and its MedGen record lists no clinical features." That is the
    owner's "or tells me the records do not say". Anything short of that
    knowledge leaves the line exactly as it was without the clause. It
    states an absence in a record, never a fact about the subject, and it
    adds words, never markers, so `MAX_SUMMARY_MARKERS` still holds.

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
    # counted as two records. One record per page, keeping the finding that
    # NAMES the record (its title) when there is one. Card 22 (2026-10-06):
    # keyed by `source_page_key`, the key the Sources list, the meta line and
    # the trust line all use, so the graph's gene link and the live Datasets
    # gene link (which adds a trailing slash) are one record here too, and
    # "Found 2 gene records" can no longer sit above one gene card (A-22-03).
    by_page: dict[str, SynthFinding] = {}
    unkeyed: list[SynthFinding] = []
    for finding in sorted(counted, key=lambda f: display_slots[f.citation_id]):
        page = source_page_key(finding.source_url)
        if not page:
            unkeyed.append(finding)
            continue
        kept = by_page.get(page)
        if kept is None or (kept.field not in _LABEL_FIELDS and finding.field in _LABEL_FIELDS):
            by_page[page] = finding
    counted = list(by_page.values()) + unkeyed

    def finish(sentence: str) -> str:
        # Build phase 8.7, card 2: the honest gap, only when the absence is
        # known, never when it is merely not seen (`records_lack_field`).
        if asked_field is not None and records_lack_field(
            counted, list(all_findings or answer_findings), row_for, asked_field
        ):
            return sentence[:-1] + _gap_clause(len(counted), asked_field) + "."
        return sentence

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
    # Room for the named linked diseases' markers too, so the whole sentence
    # stays within one token's marker limit.
    markers = markers[: max(MAX_SUMMARY_MARKERS - len(named_diseases), 0)]

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
            return finish(body + ".")
        conditions = "condition" if len(titles) == 1 else "conditions"
        clause = f", linked to {len(titles)} {conditions}"
        if named_diseases:
            clause += " " + "".join(f"[{display_slots[f.citation_id]}]" for f in named_diseases)
        return finish(body + clause + ".")

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
        return finish(body + ".")
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
    return finish(body + clause + ".")
