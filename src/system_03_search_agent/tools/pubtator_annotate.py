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

## Withhold-not-truncate, and its narrower guarantee on this tool

Every string field this module extracts from PubTator3's response is
untrusted upstream content (`ai-security-standards.md`): never executed,
never treated as an instruction, only ever capped or withheld before it
reaches the output schema, per production-standards.md's bounded-context-items
gate and the withhold-not-truncate precedent `ncbi_dbsnp.py`'s
`_cap_or_withhold` set in build phase 3.2 (F-3.2-A-15): a value that would
need truncation to fit its schema cap is instead set to `None`
(`_withhold_if_over` below), never shortened into a real-looking-but-wrong
value under a confident `status: "ok"`.

This tool's guarantee is narrower than `ncbi_dbsnp`'s at the per-item level:
`pubtator_annotate_schemas.py`'s design decision 5 explains why there is no
per-item `fields_withheld`-style disclosure field on `entities[]` or
`annotations[]` (Section 6.4's own item schemas are `additionalProperties:
false` with no room for one, and this ticket's authorization names exactly
one additive field, `pmids_not_found`, not a second one at item
granularity). A withheld per-item field is silently `None`, distinguishable
from a genuinely absent one only by re-fetching and comparing, a known,
narrower gap than `ncbi_dbsnp` provides, flagged rather than silently
absent.

`pmids_not_found` itself (top-level, F-3.3-01) is the one disclosure this
tool DOES make with a dedicated signal, because it is the phase's own named
reason for existing (`tracker/phase_3.3.md`'s F-3.3-01), not merely a
generic overflow case.

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

import urllib.parse
from typing import Any, Final

from system_03_search_agent.tools import ncbi_transport
from system_03_search_agent.tools.pubtator_annotate_schemas import (
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

_MAX_ERROR_CHARS: Final[int] = 500


def _withhold_if_over(value: str | None, limit: int) -> str | None:
    """Return `value` unchanged if within `limit`, else `None` (withheld).

    Never truncates: a truncated string looks like a real, complete, wrong
    value (F-3.2-A-01's original failure mode); withholding is safer even
    without a per-item disclosure field naming which field was dropped. See
    this module's docstring, "Withhold-not-truncate", and
    `pubtator_annotate_schemas.py`'s design decision 5 for why no such field
    exists at this granularity on this tool.
    """
    if value is None:
        return None
    return value if len(value) <= limit else None


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


def _parse_entity(raw: Any) -> PubtatorEntity | None:
    """Build one `PubtatorEntity` from one element of the autocomplete array.

    Returns `None`, never raises, when `raw` is not an object: fail-closed
    by design, the same discipline `ncbi_dbsnp.py`'s own parsing functions
    use for a response shape this module cannot make sense of.
    """
    if not isinstance(raw, dict):
        return None
    return PubtatorEntity(
        pubtator_id=_withhold_if_over(_str_or_none(raw.get("_id")), _MAX_PUBTATOR_ID_CHARS),
        biotype=_withhold_if_over(_str_or_none(raw.get("biotype")), _MAX_BIOTYPE_CHARS),
        db=_withhold_if_over(_str_or_none(raw.get("db")), _MAX_DB_CHARS),
        db_id=_withhold_if_over(_str_or_none(raw.get("db_id")), _MAX_DB_ID_CHARS),
        name=_withhold_if_over(_str_or_none(raw.get("name")), _MAX_ENTITY_NAME_CHARS),
        description=_withhold_if_over(_str_or_none(raw.get("description")), _MAX_DESCRIPTION_CHARS),
        # F-3.3-A-01/F-3.3-A-02/F-3.3-A-03: disclose PubTator3's own
        # relevance signal rather than discarding it. See the module
        # docstring's "matched_on" section.
        matched_on=_withhold_if_over(_str_or_none(raw.get("match")), _MAX_MATCHED_ON_CHARS),
    )


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
    for raw in body[:_MAX_ENTITIES]:
        parsed = _parse_entity(raw)
        if parsed is not None:
            entities.append(parsed)

    if not entities:
        # Every element failed to parse as an object: treat the same as a
        # genuine no-match rather than a confident "ok" with an empty list,
        # since nothing usable was actually extracted.
        return PubtatorAnnotateOutput(status="empty", mode="entity_lookup", entities=[])

    return PubtatorAnnotateOutput(status="ok", mode="entity_lookup", entities=entities)


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


def _parse_annotation(raw: Any) -> PubtatorAnnotation | None:
    """Build one `PubtatorAnnotation` from one `passages[].annotations[]` entry.

    Section 6.4's endpoint table: annotation fields live inside each
    entry's `infons` object (`type`, `identifier`, `normalized_id`, `valid`,
    `biotype`, `database`, `accession`, `name`), not on the entry itself.
    Only the fields this tool's locked output schema names are extracted;
    `database`/`accession` are PubTator3-specific fields with no matching
    output slot and are intentionally not carried through.
    """
    if not isinstance(raw, dict):
        return None
    infons = raw.get("infons")
    if not isinstance(infons, dict):
        return None
    valid = infons.get("valid")
    return PubtatorAnnotation(
        type=_withhold_if_over(_str_or_none(infons.get("type")), _MAX_ANNOTATION_TYPE_CHARS),
        identifier=_withhold_if_over(
            _str_or_none(infons.get("identifier")), _MAX_ANNOTATION_IDENTIFIER_CHARS
        ),
        normalized_id=_withhold_if_over(
            _str_or_none(infons.get("normalized_id")), _MAX_ANNOTATION_NORMALIZED_ID_CHARS
        ),
        valid=valid if isinstance(valid, bool) else None,
        biotype=_withhold_if_over(
            _str_or_none(infons.get("biotype")), _MAX_ANNOTATION_BIOTYPE_CHARS
        ),
        name=_withhold_if_over(_str_or_none(infons.get("name")), _MAX_ANNOTATION_NAME_CHARS),
    )


def _parse_publication(doc: Any) -> PubtatorPublication | None:
    """Unwrap one `.PubTator3[i]` document into a `PubtatorPublication`.

    Section 6.4's drift point: annotations live at
    `.PubTator3[i].passages[].annotations[]`, not at the document's top
    level and not in a bare BioC shape. Returns `None`, never raises, when
    `doc` carries no extractable `id` (the reliable PMID field, fact 1
    above): a document this module cannot identify cannot be matched back
    against the caller's requested `pmids` list either.
    """
    if not isinstance(doc, dict):
        return None
    pmid = _extract_pmid(doc)
    if not pmid:
        return None

    annotations: list[PubtatorAnnotation] = []
    passages = doc.get("passages")
    if isinstance(passages, list):
        for passage in passages:
            if len(annotations) >= _MAX_ANNOTATIONS:
                break
            if not isinstance(passage, dict):
                continue
            raw_annotations = passage.get("annotations")
            if not isinstance(raw_annotations, list):
                continue
            for raw_annotation in raw_annotations:
                if len(annotations) >= _MAX_ANNOTATIONS:
                    break
                parsed = _parse_annotation(raw_annotation)
                if parsed is not None:
                    annotations.append(parsed)

    capped_pmid = _withhold_if_over(pmid, _MAX_PMID_CHARS)
    source_url = (
        f"https://pubmed.ncbi.nlm.nih.gov/{urllib.parse.quote(pmid, safe='')}/"
        if capped_pmid is not None
        else None
    )
    return PubtatorPublication(pmid=capped_pmid, annotations=annotations, source_url=source_url)


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
    for doc in docs[:_MAX_PUBLICATIONS]:
        pub = _parse_publication(doc)
        if pub is not None and pub.pmid:
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
        )

    return PubtatorAnnotateOutput(
        status="ok",
        mode="annotate_publications",
        publications=publications,
        pmids_not_found=pmids_not_found,
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
