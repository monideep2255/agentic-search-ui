"""pubtator_annotate: entity normalization and publication annotation via PubTator3 (T-3.3-05).

Section 6.4's two-mode tool, over `https://www.ncbi.nlm.nih.gov/research/
pubtator3-api` (no API key). The two modes hit genuinely different endpoints
with genuinely different response shapes and error conventions
(`Tool_implementation_mechanics.md`'s "one error convention assumed across
both actions" trap, the same trap `ncbi_efetch.py` avoids per-action), so
each is handled by its own function below, never a shared code path:

    entity_lookup: `GET /entity/autocomplete/?query={text}&limit={n}`. A
    real match is a bare JSON array of objects, HTTP 200. A no-match is `[]`,
    also HTTP 200 (Layer 3's cite-or-refuse empty signal, mapped to
    `status: "empty"`).

    annotate_publications: `GET /publications/export/biocjson?pmids={csv}`.
    A real batch is `{"PubTator3": [...]}`, HTTP 200; an all-invalid batch is
    `{"detail": "Could not retrieve publications"}`, HTTP 400.

Both are classified with `ncbi_transport.classify_status_coded_response`:
PubTator3 is genuinely HTTP-status-coded, the same convention as Datasets
v2/PubChem/Variation Services, never the E-utilities 200-with-body-error
pattern (confirmed live below and in `tracker/phase_3.3.md`'s pre-build
probes).

## Three live-probed facts this module resolves, re-verified directly
## against the real API on 2026-08-08 while writing this file, not merely
## carried forward from the ticket tracker's own probes (LEARNINGS.md row
## 60's discipline: fixtures and assumptions come from the real endpoint)

1. THE RELIABLE PMID FIELD ON A `.PubTator3[i]` DOCUMENT IS `id`, A PLAIN
   STRING (`"34083286"`), NOT `_id`. `_id` is a COMPOUND string
   (`"34083286|None"`, live-confirmed), not usable directly as a PMID
   without further parsing. `_extract_pmid` below reads `id` only. Section
   6.4's own endpoint table names `_id` as PubTator3's convention for the
   ENTITY id on the `entity_lookup` response (a different, unrelated field
   on a different endpoint's response), which this module maps to
   `PubtatorEntity.pubtator_id`; the two `_id`-shaped fields on the two
   endpoints are not the same kind of value and must not be confused.

2. F-3.3-01, RE-CONFIRMED: a mixed batch of one real and one nonexistent
   PMID in the SAME `annotate_publications` request returns HTTP 200 with
   `PubTator3` carrying only the real PMID's document
   (`{"PubTator3": [<A's document>]}`), no per-PMID error signal anywhere in
   the body. `_annotate_publications` below diffs the REQUESTED `pmids` list
   against every `id` actually present across the returned documents and
   reports the gap via `pmids_not_found`
   (`pubtator_annotate_schemas.PubtatorAnnotateOutput.pmids_not_found`,
   design decision 4), the only place this silent drop becomes visible to a
   caller.

3. `infons.normalized_id` IS SOMETIMES AN INT, NOT A STRING, DESPITE
   Section 6.4's own output schema declaring `normalized_id` as
   `["string", "null"]`. Live-confirmed on the BRCA1 gene annotation above:
   `"normalized_id": 672` (a JSON number), sibling to `"identifier": "672"`
   (a JSON string, the SAME value, different type). `_parse_annotation`
   below coerces `normalized_id` to `str` before it ever reaches
   `PubtatorAnnotation`, rather than passing the raw int through and letting
   Pydantic coerce it silently (which it would also do, since Pydantic's
   default `str` field accepts an int input by lossless coercion, but doing
   it explicitly here documents the fact rather than leaving a silent
   implicit conversion for the next reader to rediscover).

## Withhold-not-truncate, and its per-item disclosure (F-3.3-J-04, fix round 4)

Every string field this module extracts from PubTator3's response is
untrusted upstream content (`ai-security-standards.md`): never executed,
never treated as an instruction, only ever capped or withheld before it
reaches the output schema, per production-standards.md's bounded-context-items
gate and the withhold-not-truncate precedent `ncbi_dbsnp.py`'s
`_cap_or_withhold` set in build phase 3.2 (F-3.2-A-15): a value that would
need truncation to fit its schema cap is instead set to `None`
(`_withhold_if_over` below), never shortened into a real-looking-but-wrong
value under a confident `status: "ok"`.

CORRECTED 2026-08-08 (F-3.3-J-04, fix round 4): an earlier version of this
module set an over-cap `entities[]` or `annotations[]` field to `None`
with no disclosure of any kind, a narrower guarantee than `litvar2_lookup`
shipped for the sibling per-item case in the same phase. That gap was a
scoping accident (T-3.3-03's original authorization named exactly one
additive field, `pmids_not_found`, because that was the finding on the
table at the time), not a considered product tradeoff, so it is closed
here: `_withhold_if_over` now returns `(value_or_None, note_or_None)`, and
`_parse_entity`/`_parse_annotation`/`_parse_publication` all thread the
resulting notes up to `PubtatorAnnotateOutput.fields_withheld`
(`pubtator_annotate_schemas.py`'s design decision 9), a `list[str] | None`
naming every withheld field by its OUTPUT position, e.g.
`"entities[2].description: <original value>"` or
`"publications[0].annotations[3].name: <original value>"`, mirroring
`litvar2_lookup_schemas.Litvar2LookupOutput.fields_withheld` exactly,
including its 20-item cap and overflow-summary behavior
(`_cap_fields_withheld` below mirrors `litvar2_lookup.py`'s function of the
same name).

`pmids_not_found` (top-level, F-3.3-01) remains a SEPARATE, dedicated
disclosure signal, not folded into `fields_withheld`: it names REQUESTED
PMIDS the upstream API itself silently dropped from its own response, a
different silent-drop problem than a field this tool itself declined to
populate for exceeding a length cap. Both are additive-field disclosure
mechanisms for a silent-drop failure mode, the same house pattern applied
to two different silent-drop problems, per design decision 4 in
`pubtator_annotate_schemas.py`.

`error` IS untrusted content too, even though it is a diagnostic string
this module builds rather than a value copied straight off a response
field: `_error_output`'s message can interpolate PubTator3's own
`{"detail": ...}` echo of a caller-supplied identifier, so a crafted
`pmids` or `query` value can round-trip into `output.error` (LitVar2's
sibling tool reproduces this directly, F-3.3-A-08). `error` is capped at
`_MAX_ERROR_CHARS` (500) the same as every other field this module
withholds rather than truncates, and, like every other field this module
reads, it is data for a downstream Write step to report or discard, never
an instruction to execute, format as a template, or act on. 500 chars is
kept as is rather than tightened further here: it already matches the
cap every other tool in this repo uses for the same field, and this
finding's fix is documentation plus the existing cap, not a new
sanitization layer (see `tracker/phase_3.3.md`'s F-3.3-A-08 disposition
for why a narrower cap was considered and declined).

## matched_on: disclosing PubTator3's own relevance signal (F-3.3-A-01/
## F-3.3-A-02/F-3.3-A-03, fix round 3)

PubTator3's `/entity/autocomplete/` response carries a `match` field on
every row (e.g. `"Multiple matches"`, `"Matched on name <m>BRCA1</m>"`),
its own statement of why a row matched the caller's query. Before this
fix `_parse_entity` never read it, so a query resolving to an exact term
and a query resolving to a common English word (`query="the"` returning
ten confidently normalized MeSH/Gene entities under `status: "ok"`,
F-3.3-A-03) were indistinguishable in the output. `_parse_entity` now
reads `raw.get("match")` into `PubtatorEntity.matched_on`
(`pubtator_annotate_schemas.py`'s design decision 7), withheld like any
other over-length field via `_withhold_if_over`, never truncated. This is
a DISCLOSURE fix only: it surfaces the raw signal for a downstream
consumer to weigh. It deliberately does not build a match-quality
heuristic or auto-refuse a weak match; that judgment call is its own
scoped decision, not folded into this fix.

## pmids_not_found: an identity diff, not a raw-string diff (F-3.3-A-04,
## fix round 3)

The original F-3.3-01 fix computed `pmids_not_found` by comparing the
caller's raw requested `pmids` strings against the returned PMIDs with
exact string equality. PubTator3 itself normalizes a leading zero or
surrounding whitespace and answers with the canonical id
(`pmids=["034083286"]` returns the real `34083286` document), so the
raw-string diff reported a drop that never happened, right next to the
data proving it did not: `pmids_not_found: ["034083286"]` alongside a
`publications` entry for that exact paper. `_canonical_pmid` below
normalizes both sides of the diff (`str(int(pmid.strip()))`, falling back
to the stripped-but-unparsed form on a non-numeric value rather than
raising) before comparing, so a requested id that normalizes to the same
value as a returned id can never appear in `pmids_not_found`.
`pmids_not_found` itself still reports the caller's ORIGINAL requested
string, never the canonicalized form: canonicalization is for identity
comparison only, not for what gets disclosed.

## source_url for entity_lookup, deliberately partial (F-3.3-A-05, fix round 4)

`entity_lookup` mode shipped no provenance of any kind before this fix,
while `annotate_publications`'s sibling `PubtatorPublication.source_url`
gave every publication its own PubMed link. `_entity_source_url` below
builds `PubtatorEntity.source_url` ONLY for `db == "ncbi_gene"` (`https://
www.ncbi.nlm.nih.gov/gene/{db_id}`) and `db == "ncbi_mesh"` (`https://
www.ncbi.nlm.nih.gov/mesh/{db_id}`), the two `db` values this phase's own
live probing has actually observed and verified live 2026-08-08 as real,
distinct, server-rendered NCBI record pages, not a shared client-rendered
shell the way `litvar2_lookup`'s own UI citation was found to be
(F-3.3-A-09). Every other `db` value (`litvar`, `cvcl`, and anything else
PubTator3 might return) gets `None`: this module does not guess a URL
shape for a db type it has not verified live, per LEARNINGS.md row 60's
discipline, and does not silently claim coverage it does not have. See
`pubtator_annotate_schemas.py`'s design decision 8 for the full coverage
statement and the live-verification evidence.

## total_annotations, a companion count for a pre-existing silent cap
## (F-3.3-A-12, fix round 4)

`_MAX_ANNOTATIONS` (100) capped a publication's `annotations` list with no
companion total, unlike this tool's own `pmids_not_found`/`pmids` pairing
and `litvar2_lookup`'s `pmids`/`total_pmids` pairing built in this same
phase. `_parse_publication` now computes `total_annotations`, the TRUE
count of well-formed annotation entries across every passage, before the
100-item cap, mirroring `litvar2_lookup._parse_pmids`'s own `total_pmids`
discipline (a basic-type-validity count over the full response, not merely
`len(annotations)` after capping): see `_is_annotation_shaped` below. This
does not fully parse, or generate `fields_withheld` notes for, entries
beyond the cap, the same scope discipline `litvar2_lookup.
_parse_variant_matches`'s own F-3.3-A-12 fix applies to
`total_variant_matches`.

Depends on:
    - system_03_search_agent.tools.ncbi_transport (T-3.3-02's `"pubtator"`
      rate-limit family and the `{"detail": ...}` error-message branch;
      `execute_get`, `classify_status_coded_response`, `TransportError`)
    - system_03_search_agent.tools.pubtator_annotate_schemas (T-3.3-03;
      `PubtatorAnnotateInput`, `PubtatorAnnotateOutput`, `PubtatorEntity`,
      `PubtatorAnnotation`, `PubtatorPublication`)

Reads:
    - Nothing. PubTator3 needs no API key (Section 6.4: "no API key").

Writes:
    - Nothing. Outbound HTTPS requests only, via `ncbi_transport`.

Depended by:
    - system_03_search_agent.harness.cache (T-3.3-07, tool registration, not
      yet done)
    - tests/system_03_search_agent/tools/test_pubtator_annotate_premise.py,
      via its `_run` helper, which imports `pubtator_annotate` from this
      module by name
    - tests/system_03_search_agent/tools/test_pubtator_annotate.py
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any, Final

from system_03_search_agent.tools import ncbi_transport
from system_03_search_agent.tools.pubtator_annotate_schemas import (
    NCBI_PUBTATOR_ENTITY_RECORD_URL_PATTERN,
    PubtatorAnnotateInput,
    PubtatorAnnotateOutput,
    PubtatorAnnotatePublicationsInput,
    PubtatorAnnotation,
    PubtatorEntity,
    PubtatorEntityLookupInput,
    PubtatorPublication,
)

_ENTITY_AUTOCOMPLETE_URL: Final[str] = (
    "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/entity/autocomplete/"
)
_PUBLICATIONS_EXPORT_URL: Final[str] = (
    "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/publications/export/biocjson"
)

# Field length caps, mirroring pubtator_annotate_schemas.py's own
# Field(max_length=...) constraints exactly. Pydantic raises on an
# over-length string rather than truncating it, so every value that could
# plausibly come from untrusted upstream content is checked here, before
# construction, per production-standards.md's bounded-context-items gate.
_MAX_MODE_CHARS: Final[int] = 25
_MAX_ENTITIES: Final[int] = 20
_MAX_PUBTATOR_ID_CHARS: Final[int] = 40
_MAX_BIOTYPE_CHARS: Final[int] = 20
_MAX_DB_CHARS: Final[int] = 20
_MAX_DB_ID_CHARS: Final[int] = 30
_MAX_ENTITY_NAME_CHARS: Final[int] = 100
_MAX_DESCRIPTION_CHARS: Final[int] = 300
_MAX_MATCHED_ON_CHARS: Final[int] = 200

_MAX_PMID_CHARS: Final[int] = 15
_MAX_PUBLICATIONS: Final[int] = 20
_MAX_ANNOTATIONS: Final[int] = 100
_MAX_ANNOTATION_TYPE_CHARS: Final[int] = 20
_MAX_ANNOTATION_IDENTIFIER_CHARS: Final[int] = 60
_MAX_ANNOTATION_NORMALIZED_ID_CHARS: Final[int] = 60
_MAX_ANNOTATION_BIOTYPE_CHARS: Final[int] = 20
_MAX_ANNOTATION_NAME_CHARS: Final[int] = 100
_MAX_SOURCE_URL_CHARS: Final[int] = 200

_MAX_ERROR_CHARS: Final[int] = 500

# F-3.3-J-04: per-item withholding disclosure, mirroring
# litvar2_lookup.py's _MAX_WITHHELD_NOTE_CHARS/_MAX_FIELDS_WITHHELD_ITEMS
# and pubtator_annotate_schemas.py's own matching Field(max_length=...)
# constraints exactly.
_MAX_WITHHELD_NOTE_CHARS: Final[int] = 150
_MAX_FIELDS_WITHHELD_ITEMS: Final[int] = 20


def _withheld_note(text: str) -> str:
    """Cap a diagnostic fields_withheld entry to its schema limit (F-3.3-J-04).

    Mirrors `litvar2_lookup._withheld_note` exactly: this truncates a NOTE
    describing what was withheld, never the withheld DATA itself (which is
    dropped entirely, not shipped in any form). A truncated note is a
    cosmetic limitation on a diagnostic string, not a wrong-answer risk the
    way truncating an actual citable field would be.
    """
    return text[:_MAX_WITHHELD_NOTE_CHARS]


def _cap_fields_withheld(notes: list[str]) -> list[str]:
    """Cap `fields_withheld` at the schema's own `max_length=20` (F-3.3-J-04).

    Mirrors `litvar2_lookup._cap_fields_withheld` exactly, applying that
    ticket's own F-3.3-J-01 precedent here from the start rather than
    discovering it as a second regression: silently dropping overflow
    notes would itself be a silent-truncation failure (the class this
    whole module's withhold-not-truncate policy exists to avoid), so when
    there are more than `_MAX_FIELDS_WITHHELD_ITEMS` notes, the first
    `_MAX_FIELDS_WITHHELD_ITEMS - 1` ship unchanged and the final slot is
    replaced with a summary naming how many additional notes did not fit.
    """
    if len(notes) <= _MAX_FIELDS_WITHHELD_ITEMS:
        return notes
    kept = notes[: _MAX_FIELDS_WITHHELD_ITEMS - 1]
    overflow = len(notes) - len(kept)
    kept.append(
        _withheld_note(
            f"...and {overflow} more fields withheld (the withholding count "
            f"exceeded the {_MAX_FIELDS_WITHHELD_ITEMS}-item disclosure cap)"
        )
    )
    return kept


def _withhold_if_over(
    value: str | None, limit: int, note_label: str
) -> tuple[str | None, str | None]:
    """Return `(value_or_None, note_or_None)`: withhold, and disclose it (F-3.3-J-04).

    Never truncates: a truncated string looks like a real, complete, wrong
    value (F-3.2-A-01's original failure mode). Now also returns a
    disclosure note whenever a value IS withheld, naming the field by its
    OUTPUT position (`note_label`, e.g. `f"entities[{output_index}].name"`,
    never a raw response index, the F-3.3-J-03 indexing discipline
    `litvar2_lookup.py` already established) and the full original value,
    closing the gap `pubtator_annotate_schemas.py`'s design decision 6
    originally left open: see design decision 9 there for why this tool now
    ships the same `fields_withheld` disclosure `litvar2_lookup.py` does.
    """
    if value is None:
        return None, None
    if len(value) <= limit:
        return value, None
    return None, _withheld_note(f"{note_label}: {value}")


def _str_or_none(value: Any) -> str | None:
    """Coerce a raw JSON value to `str`, or `None` if absent/null.

    PubTator3's own response mixes string and non-string JSON types for
    what is conceptually the same field across sibling keys (see the module
    docstring's fact 3, `infons.normalized_id`): this coerces explicitly
    rather than passing a raw int/bool/float through to a `str`-typed
    Pydantic field and relying on implicit coercion.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _error_output(mode: str, message: str) -> PubtatorAnnotateOutput:
    """Build a `status: "error"` output with an actionable message.

    Same shape `ncbi_efetch.py`'s and `ncbi_dbsnp.py`'s own `_error_output`
    helpers build: no records/entities/publications, the message capped to
    the schema's own `error` field length so a pathological exception
    string cannot itself violate `PubtatorAnnotateOutput`'s `max_length`.
    """
    return PubtatorAnnotateOutput(
        status="error",
        mode=mode[:_MAX_MODE_CHARS],
        error=message[:_MAX_ERROR_CHARS],
    )


def _status_error_reason(error_message: str | None, http_status: int) -> str | None:
    """`error_message`, unless it is ncbi_transport's own content-free fallback (F-3.3-A-07).

    Both status-coded call sites below built their message with
    `classification.error_message or <locally generated actionable text>`,
    which looks like a safe fallback but is not:
    `ncbi_transport._extract_status_coded_error_message`'s own generic
    fallback string, `"HTTP {status} with no structured error body"`, is
    non-empty and therefore TRUTHY, so the `or` always picked it over this
    module's own actionable fallback text whenever PubTator3's error body
    fell through every recognized shape (reachable live via F-3.3-A-06's
    `pmids=[]` repro). The result was a message naming no next step at
    all, the one violation of `production-standards.md`'s retry-safety
    gate in this module.

    Returning `None` for exactly that one generic-fallback shape restores
    the `or` at each call site to the actionable branch it was always
    meant to reach. Any other, genuinely PubTator3-authored reason (e.g.
    `"Could not retrieve publications"`) passes through unchanged: that
    text already carries real information the generic fallback does not,
    so it is not replaced, only the content-free case is.
    """
    if error_message is None:
        return None
    if error_message == f"HTTP {http_status} with no structured error body":
        return None
    return error_message


def _canonical_pmid(pmid: str) -> str:
    """Normalize a PMID string for identity comparison only (F-3.3-A-04).

    PubTator3 normalizes a leading zero or surrounding whitespace on a
    requested PMID and answers with the canonical numeric id
    (`pmids=["034083286"]` returns the real `34083286` document); the
    original `pmids_not_found` diff compared raw strings, so a caller's
    own formatting variant of a PMID that WAS found could still be
    reported as not found, right alongside the very document that
    disproves it. This never raises on a non-numeric value: an id that is
    not parseable as an int has no canonical numeric form to fall to, so
    it is compared on its stripped-but-otherwise-unparsed form instead.
    Used ONLY to decide set membership for the diff; `pmids_not_found`
    itself still reports the caller's original, uncanonicalized string.
    """
    stripped = pmid.strip()
    try:
        return str(int(stripped))
    except ValueError:
        return stripped


# ---------------------------------------------------------------------------
# entity_lookup: GET /entity/autocomplete/?query={text}&limit={n}
# ---------------------------------------------------------------------------


def _entity_source_url(db: str | None, db_id: str | None) -> str | None:
    """The human-facing NCBI record page for an entity_lookup result (F-3.3-A-05).

    DELIBERATELY PARTIAL: only `db == "ncbi_gene"` and `db == "ncbi_mesh"`
    build a URL, the two db values this phase's own live probing verified
    live 2026-08-08 as real, distinct, server-rendered NCBI record pages
    (gene 672 and gene 7157 return genuinely different content, 734671 and
    527847 bytes respectively; mesh D001943 and D003924 likewise, 65216 and
    64837 bytes), not a shared client-rendered shell the way
    `litvar2_lookup`'s own UI citation was found to be (F-3.3-A-09). Every
    other `db` value (`litvar`, `cvcl`, and anything else PubTator3 might
    return) gets `None`: this function does not guess a URL shape for a db
    type it has not verified live. See
    `pubtator_annotate_schemas.py`'s design decision 8 for the full
    coverage statement.
    """
    if db_id is None:
        return None
    if db == "ncbi_gene":
        url = f"https://www.ncbi.nlm.nih.gov/gene/{urllib.parse.quote(db_id, safe='')}"
    elif db == "ncbi_mesh":
        url = f"https://www.ncbi.nlm.nih.gov/mesh/{urllib.parse.quote(db_id, safe='')}"
    else:
        return None
    if len(url) > _MAX_SOURCE_URL_CHARS:
        return None
    if re.match(NCBI_PUBTATOR_ENTITY_RECORD_URL_PATTERN, url) is None:
        # Defense in depth, matching litvar2_lookup._build_source_url's own
        # "fail closed to no citation rather than raise" discipline: should
        # never actually fire since the two URL shapes above are fixed
        # templates already verified against the pattern, but a wrong URL
        # here must never surface as a pydantic.ValidationError out of a
        # tool call.
        return None
    return url


def _parse_entity(raw: Any, output_index: int) -> tuple[PubtatorEntity | None, list[str]]:
    """Build one `PubtatorEntity` from one element of the autocomplete array.

    Returns `(None, [])`, never raises, when `raw` is not an object:
    fail-closed by design, the same discipline `ncbi_dbsnp.py`'s own
    parsing functions use for a response shape this module cannot make
    sense of.

    `output_index` (F-3.3-J-04) is this entity's position in the OUTPUT
    `entities` list if kept, i.e. how many entities have already been kept
    before this one, never the raw response array's own index: a raw row
    that fails to parse as an object is skipped entirely and never
    occupies a position, so only `output_index` stays correct for every
    field-level disclosure note about a KEPT entity, the same F-3.3-J-03
    discipline `litvar2_lookup.py` already established.
    """
    if not isinstance(raw, dict):
        return None, []

    notes: list[str] = []

    def _field(value: str | None, limit: int, label: str) -> str | None:
        capped, note = _withhold_if_over(value, limit, f"entities[{output_index}].{label}")
        if note is not None:
            notes.append(note)
        return capped

    pubtator_id = _field(_str_or_none(raw.get("_id")), _MAX_PUBTATOR_ID_CHARS, "pubtator_id")
    biotype = _field(_str_or_none(raw.get("biotype")), _MAX_BIOTYPE_CHARS, "biotype")
    db = _field(_str_or_none(raw.get("db")), _MAX_DB_CHARS, "db")
    db_id = _field(_str_or_none(raw.get("db_id")), _MAX_DB_ID_CHARS, "db_id")
    name = _field(_str_or_none(raw.get("name")), _MAX_ENTITY_NAME_CHARS, "name")
    description = _field(_str_or_none(raw.get("description")), _MAX_DESCRIPTION_CHARS, "description")
    # F-3.3-A-01/F-3.3-A-02/F-3.3-A-03: disclose PubTator3's own relevance
    # signal rather than discarding it. See the module docstring's
    # "matched_on" section.
    matched_on = _field(_str_or_none(raw.get("match")), _MAX_MATCHED_ON_CHARS, "matched_on")

    entity = PubtatorEntity(
        pubtator_id=pubtator_id,
        biotype=biotype,
        db=db,
        db_id=db_id,
        name=name,
        description=description,
        matched_on=matched_on,
        # F-3.3-A-05: derived from the already-withheld db/db_id (never the
        # raw pre-withholding values), so a db_id that was itself withheld
        # for exceeding its own cap never contributes to a source_url.
        source_url=_entity_source_url(db, db_id),
    )
    return entity, notes


async def _entity_lookup(input_data: PubtatorEntityLookupInput) -> PubtatorAnnotateOutput:
    """`entity_lookup`: a real match, a genuine no-match, or a transport/status error.

    The locked schema's `minLength: 1` on `query` already closes the only
    realistic path to PubTator3's undocumented bare-array error shape
    (F-3.3-02); this function does not special-case it, matching the
    disposition `tracker/phase_3.3.md` records for that finding.
    """
    try:
        response = await ncbi_transport.execute_get(
            _ENTITY_AUTOCOMPLETE_URL,
            {"query": input_data.query, "limit": input_data.limit},
            family="pubtator",
        )
    except ncbi_transport.TransportError as exc:
        return _error_output("entity_lookup", str(exc))

    classification = ncbi_transport.classify_status_coded_response(
        http_status=response.status_code, text=response.text, headers=response.headers,
    )
    if classification.status == "error":
        return _error_output(
            "entity_lookup",
            _status_error_reason(classification.error_message, response.status_code)
            or f"PubTator3 entity_lookup returned HTTP {response.status_code} with "
            "no structured error body. Retry once; if this recurs, PubTator3 may "
            "be degraded.",
        )

    body = classification.body
    if not isinstance(body, list):
        return _error_output(
            "entity_lookup",
            "PubTator3 entity_lookup returned an unrecognized response shape "
            "(expected a bare JSON array), refusing to guess its meaning. Retry "
            "once; if this recurs, report it.",
        )

    if not body:
        return PubtatorAnnotateOutput(status="empty", mode="entity_lookup", entities=[])

    entities: list[PubtatorEntity] = []
    all_notes: list[str] = []
    for raw in body[:_MAX_ENTITIES]:
        output_index = len(entities)
        parsed, entity_notes = _parse_entity(raw, output_index)
        if parsed is not None:
            all_notes.extend(entity_notes)
            entities.append(parsed)

    if not entities:
        # Every element failed to parse as an object: treat the same as a
        # genuine no-match rather than a confident "ok" with an empty list,
        # since nothing usable was actually extracted.
        return PubtatorAnnotateOutput(status="empty", mode="entity_lookup", entities=[])

    return PubtatorAnnotateOutput(
        status="ok",
        mode="entity_lookup",
        entities=entities,
        fields_withheld=_cap_fields_withheld(all_notes) if all_notes else None,
    )


# ---------------------------------------------------------------------------
# annotate_publications: GET /publications/export/biocjson?pmids={csv}
# ---------------------------------------------------------------------------


def _extract_pmid(doc: dict[str, Any]) -> str | None:
    """The reliable PMID field on a `.PubTator3[i]` document is `id`, a plain
    string. `_id` is a compound `"{pmid}|{something}"` string, live-confirmed
    NOT directly usable as a PMID. See the module docstring's fact 1.
    """
    pmid = doc.get("id")
    if pmid is None:
        return None
    return _str_or_none(pmid)


def _is_annotation_shaped(raw: Any) -> bool:
    """Basic-type validity check for F-3.3-A-12's `total_annotations`.

    A dict carrying an `infons` object, the same minimal shape
    `_parse_annotation` itself requires before extracting anything. Used
    ONLY to compute a total count over the FULL annotation list before the
    `_MAX_ANNOTATIONS` cap, never to decide whether to actually parse and
    keep an entry (that remains `_parse_annotation`'s own job).
    """
    return isinstance(raw, dict) and isinstance(raw.get("infons"), dict)


def _parse_annotation(
    raw: Any, pub_index: int, ann_index: int
) -> tuple[PubtatorAnnotation | None, list[str]]:
    """Build one `PubtatorAnnotation` from one `passages[].annotations[]` entry.

    Section 6.4's endpoint table: annotation fields live inside each
    entry's `infons` object (`type`, `identifier`, `normalized_id`, `valid`,
    `biotype`, `database`, `accession`, `name`), not on the entry itself.
    Only the fields this tool's locked output schema names are extracted;
    `database`/`accession` are PubTator3-specific fields with no matching
    output slot and are intentionally not carried through.

    `pub_index`/`ann_index` (F-3.3-J-04) are OUTPUT positions, the
    publication's position in `publications[]` and this annotation's
    position in that publication's `annotations[]`, never raw response
    indices: a raw annotation entry that fails to parse (not a dict, or no
    `infons` object) is skipped entirely and never occupies a position, so
    only the OUTPUT index stays correct for a field-level disclosure note
    about a KEPT annotation, the same F-3.3-J-03 discipline
    `litvar2_lookup.py` already established.
    """
    if not isinstance(raw, dict):
        return None, []
    infons = raw.get("infons")
    if not isinstance(infons, dict):
        return None, []

    notes: list[str] = []

    def _field(value: str | None, limit: int, label: str) -> str | None:
        capped, note = _withhold_if_over(
            value, limit, f"publications[{pub_index}].annotations[{ann_index}].{label}"
        )
        if note is not None:
            notes.append(note)
        return capped

    valid = infons.get("valid")
    annotation = PubtatorAnnotation(
        type=_field(_str_or_none(infons.get("type")), _MAX_ANNOTATION_TYPE_CHARS, "type"),
        identifier=_field(
            _str_or_none(infons.get("identifier")), _MAX_ANNOTATION_IDENTIFIER_CHARS, "identifier"
        ),
        normalized_id=_field(
            _str_or_none(infons.get("normalized_id")),
            _MAX_ANNOTATION_NORMALIZED_ID_CHARS,
            "normalized_id",
        ),
        valid=valid if isinstance(valid, bool) else None,
        biotype=_field(
            _str_or_none(infons.get("biotype")), _MAX_ANNOTATION_BIOTYPE_CHARS, "biotype"
        ),
        name=_field(_str_or_none(infons.get("name")), _MAX_ANNOTATION_NAME_CHARS, "name"),
    )
    return annotation, notes


def _parse_publication(doc: Any, pub_index: int) -> tuple[PubtatorPublication | None, list[str]]:
    """Unwrap one `.PubTator3[i]` document into a `PubtatorPublication`.

    Section 6.4's drift point: annotations live at
    `.PubTator3[i].passages[].annotations[]`, not at the document's top
    level and not in a bare BioC shape. Returns `(None, [])`, never raises,
    when `doc` carries no extractable `id` (the reliable PMID field, fact 1
    above): a document this module cannot identify cannot be matched back
    against the caller's requested `pmids` list either.

    `pub_index` (F-3.3-J-04) is this publication's position in the OUTPUT
    `publications` list if kept, never the raw `.PubTator3[]` array's own
    index, the same F-3.3-J-03 discipline applied here for
    `pubtator_annotate` the way `litvar2_lookup.py` already applies it for
    `variant_matches`.
    """
    if not isinstance(doc, dict):
        return None, []
    pmid = _extract_pmid(doc)
    if not pmid:
        return None, []

    passages = doc.get("passages")
    all_raw_annotations: list[Any] = []
    if isinstance(passages, list):
        for passage in passages:
            if not isinstance(passage, dict):
                continue
            raw_annotations = passage.get("annotations")
            if isinstance(raw_annotations, list):
                all_raw_annotations.extend(raw_annotations)

    # F-3.3-A-12: total_annotations is a basic-type-validity count over
    # EVERY raw annotation entry across every passage, computed BEFORE the
    # maxItems: 100 cap, mirroring litvar2_lookup._parse_pmids's own
    # total_pmids discipline. Deliberately does NOT fully parse (or
    # generate fields_withheld notes for) entries beyond the cap: doing so
    # would widen the disclosure surface to rows this tool never actually
    # surfaces in `annotations`, beyond what F-3.3-A-12 asked for (a
    # companion total count, not a companion withheld-notes scope). See
    # litvar2_lookup._parse_variant_matches's own F-3.3-A-12 docstring for
    # the identical reasoning applied to variant_matches/total_variant_matches.
    total_annotations = sum(1 for raw in all_raw_annotations if _is_annotation_shaped(raw))

    notes: list[str] = []
    annotations: list[PubtatorAnnotation] = []
    for raw_annotation in all_raw_annotations:
        if len(annotations) >= _MAX_ANNOTATIONS:
            break
        ann_index = len(annotations)
        parsed, ann_notes = _parse_annotation(raw_annotation, pub_index, ann_index)
        if parsed is None:
            continue
        notes.extend(ann_notes)
        annotations.append(parsed)

    capped_pmid, pmid_note = _withhold_if_over(
        pmid, _MAX_PMID_CHARS, f"publications[{pub_index}].pmid"
    )
    if pmid_note is not None:
        notes.append(pmid_note)
    source_url = (
        f"https://pubmed.ncbi.nlm.nih.gov/{urllib.parse.quote(pmid, safe='')}/"
        if capped_pmid is not None
        else None
    )
    publication = PubtatorPublication(
        pmid=capped_pmid,
        annotations=annotations,
        total_annotations=total_annotations,
        source_url=source_url,
    )
    return publication, notes


async def _annotate_publications(
    input_data: PubtatorAnnotatePublicationsInput,
) -> PubtatorAnnotateOutput:
    """`annotate_publications`: unwraps `.PubTator3[i].passages[].annotations[]`
    and owns F-3.3-01, the silent-drop diff against the requested `pmids` list.

    The documented all-invalid-batch shape (HTTP 400, `{"detail": ...}`) is
    handled by the generic status-coded error branch below, before any body
    unwrapping is attempted, matching `classify_status_coded_response`'s own
    "always decides ok/error from http_status alone" contract.
    """
    requested_pmids = list(input_data.pmids)
    try:
        response = await ncbi_transport.execute_get(
            _PUBLICATIONS_EXPORT_URL,
            {"pmids": ",".join(requested_pmids)},
            family="pubtator",
        )
    except ncbi_transport.TransportError as exc:
        return _error_output("annotate_publications", str(exc))

    classification = ncbi_transport.classify_status_coded_response(
        http_status=response.status_code, text=response.text, headers=response.headers,
    )
    if classification.status == "error":
        return _error_output(
            "annotate_publications",
            _status_error_reason(classification.error_message, response.status_code)
            or f"PubTator3 annotate_publications returned HTTP {response.status_code} "
            "with no structured error body. Retry once; if this recurs, PubTator3 "
            "may be degraded.",
        )

    body = classification.body
    if not isinstance(body, dict):
        return _error_output(
            "annotate_publications",
            "PubTator3 annotate_publications returned an unrecognized response "
            "shape (expected an object with a PubTator3 key), refusing to guess "
            "its meaning. Retry once; if this recurs, report it.",
        )

    docs = body.get("PubTator3")
    if not isinstance(docs, list):
        return _error_output(
            "annotate_publications",
            "PubTator3 annotate_publications response has no PubTator3 array, "
            "cannot unwrap annotations. Retry once; if this recurs, report it.",
        )

    publications: list[PubtatorPublication] = []
    found_pmids_canonical: set[str] = set()
    all_notes: list[str] = []
    for doc in docs[:_MAX_PUBLICATIONS]:
        pub_index = len(publications)
        pub, pub_notes = _parse_publication(doc, pub_index)
        if pub is None or not pub.pmid:
            # F-3.3-J-04: a publication that never makes it into `publications`
            # (no extractable pmid, or its pmid itself got withheld) must not
            # contribute notes keyed to a `publications[pub_index]` position
            # that no output publication ever occupies; the next KEPT
            # publication reuses this same pub_index correctly only if this
            # discarded document's own notes are dropped here, not appended.
            continue
        all_notes.extend(pub_notes)
        found_pmids_canonical.add(_canonical_pmid(pub.pmid))
        publications.append(pub)

    # F-3.3-A-04: diff on CANONICAL identity, not the raw requested string.
    # `pmids_not_found` still names the caller's ORIGINAL string (never the
    # canonicalized form), since canonicalization here is only for deciding
    # whether a requested id was actually satisfied, not for what gets
    # disclosed.
    pmids_not_found = [
        pmid for pmid in requested_pmids if _canonical_pmid(pmid) not in found_pmids_canonical
    ]

    if not publications:
        # A 200 response that, after parsing, yielded no identifiable
        # publication at all (not the documented all-invalid-batch shape,
        # which is HTTP 400 and already handled above; this is the
        # defensive fallback for an unobserved "200 with an empty or
        # unparseable PubTator3 array" shape). Reported as empty, not a
        # fabricated ok with zero content and not an error PubTator3 itself
        # never signaled.
        return PubtatorAnnotateOutput(
            status="empty",
            mode="annotate_publications",
            publications=[],
            pmids_not_found=pmids_not_found,
            fields_withheld=_cap_fields_withheld(all_notes) if all_notes else None,
        )

    return PubtatorAnnotateOutput(
        status="ok",
        mode="annotate_publications",
        publications=publications,
        pmids_not_found=pmids_not_found,
        fields_withheld=_cap_fields_withheld(all_notes) if all_notes else None,
    )


# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------


async def pubtator_annotate(tool_input: PubtatorAnnotateInput) -> PubtatorAnnotateOutput:
    """Route a validated `PubtatorAnnotateInput` to its mode's implementation.

    `tool_input.root` is the mode-specific, already-validated pydantic model
    (`PubtatorEntityLookupInput` or `PubtatorAnnotatePublicationsInput`) per
    `pubtator_annotate_schemas.py`'s documented `.root` access pattern. The
    `mode` field on that model is the dispatch key; it is a closed
    `Literal` in a discriminated union pydantic has already validated, so
    both branches below are reachable by construction and the trailing
    branch exists only as a defensive last resort, never as evidence that a
    third mode is expected.

    Never raises: wraps dispatch in `try`/`except`, the same outer-boundary
    pattern `ncbi_efetch.py` and `ncbi_dbsnp.py` both use, so an unexpected
    exception from anywhere in this module's own parsing (not already a
    classified `ncbi_transport.TransportError`) still returns a
    `status: "error"` output with an actionable message instead of
    propagating out of a tool call.
    """
    mode = "unknown"
    try:
        resolved = tool_input.root
        mode = resolved.mode

        if mode == "entity_lookup":
            return await _entity_lookup(resolved)
        if mode == "annotate_publications":
            return await _annotate_publications(resolved)
        # Defensive, not assumed impossible: PubtatorAnnotateInput's
        # discriminated union is closed to exactly these two mode values
        # today, so pydantic validation would already have rejected
        # anything else before this function ever runs. If a future schema
        # change adds a third mode without a matching branch here, that is
        # a tool registration gap, and the caller needs to be told to
        # report it rather than retry, not handed a raised, unclassified
        # exception.
        return _error_output(
            mode,
            f"pubtator_annotate has no dispatch branch for mode {mode!r}. This is "
            "a tool registration gap, not a caller error; report it rather than "
            "retrying.",
        )
    except Exception as exc:  # noqa: BLE001 - the dispatcher's deliberate last-resort catch
        return _error_output(
            mode,
            f"pubtator_annotate's {mode!r} mode raised an unexpected "
            f"{type(exc).__name__} instead of returning a classified result: "
            f"{exc}. Retry once; if this recurs, the {mode!r} mode has a defect "
            "that needs fixing before it can be trusted.",
        )
