"""Pydantic v2 input and output schemas for the pubtator_annotate tool (T-3.3-03).

Technical_specification.md Section 6.4 locks the JSON schema for both the
tool input and the tool output. These models are the typed, validated
implementation of that lock: every field, length cap, enum, and pattern here
mirrors the spec's `pubtator_annotate.input` and `pubtator_annotate.output`
JSON schemas exactly, plus `extra="forbid"` on every model with its own field
set so an unexpected field is rejected rather than silently dropped or passed
through (production-standards.md's multi-agent pipeline gate), with the
`pmids_not_found` addition named explicitly by `tracker/phase_3.3.md`
(T-3.3-03's own ticket line) and re-verified live against the real API on
2026-08-08 while writing this file, plus a `min_length` tightening and a
second additive field, `matched_on`, both added 2026-08-08 in the
adversary-round fix that closed F-3.3-A-01/A-02/A-03/A-06 (design
decisions 5 and 7 below).

Design decision 1, the input is a 2-way discriminated union on `mode`,
following `ncbi_efetch_schemas.py`'s documented idiom (design decision 1
there): each mode gets its own sibling model
(`PubtatorEntityLookupInput`/`PubtatorAnnotatePublicationsInput`), each with a
`Literal["<mode>"]` discriminator and `extra="forbid"`, and
`PubtatorAnnotateInput` is a `RootModel` wrapping
`Annotated[Union[...], Field(discriminator="mode")]`. Unlike `ncbi_dbsnp`'s
single flat model (which shares one two-field shape across all three
`query_type` values), `entity_lookup` (`query` + `limit`) and
`annotate_publications` (`pmids`) genuinely have different required fields
and hit different endpoints, the same reasoning `ncbi_efetch_schemas.py`
gives for its own 7-way union. A validated instance's mode-specific fields
live under `.root`, not on `PubtatorAnnotateInput` directly:
`PubtatorAnnotateInput(mode="entity_lookup", query="BRCA1").root.query` is
`"BRCA1"`. `RootModel.__init__` accepts either a single `root=` value or bare
keyword arguments (pydantic v2 treats supplied `**data` as the root value
when no explicit `root` is given), so both
`PubtatorAnnotateInput.model_validate(payload)` and
`PubtatorAnnotateInput(**payload)` construct the same validated instance;
the premise gate (`tests/system_03_search_agent/tools/
test_pubtator_annotate_premise.py`, `_run`) uses the latter form directly,
confirmed live against this exact class while writing this file.

Design decision 2, `minLength: 1` on `entity_lookup.query` (F-3.3-02,
`tracker/phase_3.3.md`). Live-confirmed 2026-08-08: an empty `query` string
returns HTTP 400 with a bare JSON array of strings,
`["query is a mandatory parameter."]`, a THIRD PubTator3 error-body shape
neither this tool's `annotate_publications` branch (`{"detail": ...}`) nor
any other tool in this repo's error-message extraction
(`ncbi_transport._extract_status_coded_error_message`) recognizes; a caller
that reached it would get the generic `"HTTP 400 with no structured error
body"` fallback message, a safe but non-specific outcome. Rejecting an empty
`query` at the schema layer, before any network call, closes the only
realistic path a caller could reach that shape from in production, per the
finding's own disposition ("owned by T-3.3-02/03, closed by `minLength: 1`
at the schema layer"). The locked schema's `maxLength: 200` alone does not
imply `minLength: 1`; JSON Schema and Pydantic both treat an absent
`minLength` as "any length including zero", so this is a genuine, deliberate
addition, not a restatement of what `maxLength` already covers.

Design decision 3, `NCBI_PUBTATOR_RECORD_URL_PATTERN`, scoped to `pubmed.`
only, defined locally in this file rather than imported from
`ncbi_efetch_schemas.NCBI_EFETCH_RECORD_URL_PATTERN` or
`ncbi_dbsnp_schemas.NCBI_DBSNP_RECORD_URL_PATTERN`. Mirrors design decision 3
in both of those files: this tool fetches from
`www.ncbi.nlm.nih.gov/research/pubtator3-api` (the PubTator3 API host) but a
citation must resolve to the human-facing PubMed record page,
`pubmed.ncbi.nlm.nih.gov/{pmid}/` (Section 6 line 1787's own compliance
table: "pubtator_annotate | Layer 3 enrichment | NCBI_RECORD_HOST |
`https://pubmed.ncbi.nlm.nih.gov/32942285/`"). Section 6.4's own output
schema pattern at line 1162 is
`^https://pubmed\\.ncbi\\.nlm\\.nih\\.gov/`, copied verbatim here.
Deliberately narrower than both `NCBI_EFETCH_RECORD_URL_PATTERN` (which also
accepts `www.`, `pubchem.`, and `omim.org`) and
`NCBI_DBSNP_RECORD_URL_PATTERN` (which accepts `www.` or `pubmed.` plus a
required `/snp/` path segment): this tool's only citable record type is a
PubMed publication, so a `www.ncbi.nlm.nih.gov/gene/...` or a
`www.ncbi.nlm.nih.gov/snp/...` URL, both real NCBI record pages, would be the
WRONG kind of citation for a `pubtator_annotate` publication row and must not
validate here, the same correctness argument `ncbi_dbsnp_schemas.py`'s
design decision 3 makes for its own narrower pattern. An import-time
self-verification assertion block below proves the pattern accepts a real
`pubmed.ncbi.nlm.nih.gov` record URL and rejects the fetch host
(`www.ncbi.nlm.nih.gov/research/pubtator3-api/...`), the bare `www.`
subdomain on a non-PubMed path, and the unrelated `eutils.ncbi.nlm.nih.gov`
host, the same self-verification idiom `ncbi_dbsnp_schemas.py` and
`ncbi_eutils_actions.py`/`ncbi_pubchem_actions.py` already use for their own
record-URL templates.

Design decision 4, `PubtatorAnnotateOutput.pmids_not_found` (F-3.3-01,
`tracker/phase_3.3.md`), an ADDITIVE, optional field, following the exact
precedent `ncbi_dbsnp_schemas.NcbiDbsnpOutput.fields_withheld` set in build
phase 3.2: a new optional field within v1 is additive, not a breaking
change, per `system-design-patterns` pattern 10. Live-confirmed 2026-08-08
(re-confirmed while writing this file, see the module docstring in
`pubtator_annotate.py`): a mixed batch of one real and one nonexistent PMID
in the SAME `annotate_publications` request returns HTTP 200 with only the
real PMID's document present in `PubTator3[]`, no per-PMID error signal
anywhere in the body. Section 6.4's own output schema is `additionalProperties:
false` with a fixed property set (`status`, `mode`, `entities`,
`publications`, `error`), so there is no existing field to carry this
signal; `pmids_not_found` is the one new key this ticket adds, bounded the
same way the request's own `pmids` field is (`max_length=20` items,
`max_length=15` per item, matching `pmids`' own `maxItems`/`maxLength`
exactly, since this field can never legitimately name more PMIDs than were
ever requested). `status` stays `"ok"` when at least one requested PMID
resolved (PubTator3's own convention: a partial result is not an error);
`pmids_not_found` is empty (`[]`), never populated, when every requested
PMID resolved. This is entirely distinct from `NcbiDbsnpOutput.fields_withheld`
in shape and purpose: that field names OUTPUT FIELDS this tool itself
declined to populate for exceeding a length cap; this field names REQUESTED
PMIDS the upstream API itself silently dropped from its own response. Both
are additive-field disclosure mechanisms for a silent-drop failure mode, the
same house pattern applied to two different silent-drop problems.

Design decision 5, `pmids.min_length: 1` (F-3.3-A-06, added 2026-08-08,
fix round 3). Design decision 2 above closed the empty-string path on
`entity_lookup.query` but never looked at `annotate_publications.pmids`,
the sibling list field: `pmids` carried `max_length=20` and no
`min_length`, so `pmids=[]` validated at the schema layer, joined to an
empty CSV, and reached the live API, landing on the EXACT F-3.3-02
undocumented bare-array error shape (`["pmids is a mandatory
parameter."]`) design decision 2's own disposition claimed was fully
closed. `min_length=1` on `pmids` mirrors the treatment `query` already
got, for the same reason: an empty list can never resolve to a real
batch and is a guaranteed-useless network call the schema layer can
reject for free.

Design decision 6, per-item field withholding within `entities[]` and
`publications[].annotations[]` has no dedicated disclosure field, unlike
`pmids_not_found` above. Section 6.4's locked item schemas for both arrays
are `additionalProperties: false` with a fixed, small property set and no
room for a per-item "this field was withheld" signal, and this ticket's own
authorization (`tracker/phase_3.3.md`'s T-3.3-03 line) names exactly one
additive field, `pmids_not_found`; widening the locked item schemas further
with a second additive field is a scope decision beyond what this ticket
authorizes, not one this file makes unilaterally. So `pubtator_annotate.py`
withholds (sets to `None`, never truncates into a real-looking-but-wrong
value, per F-3.2-A-01's precedent) any individual `entities[]` or
`annotations[]` field that exceeds its own cap, with no separate signal
naming which field was withheld beyond the field itself reading `None`. This
is a narrower disclosure guarantee than `ncbi_dbsnp`'s `fields_withheld`
provides at the top level, flagged here rather than silently absent, per
`goal-contracts.md`'s "a verify surface must state its own coverage": a
future ticket that needs stronger disclosure at this granularity would add a
new additive field the same way `pmids_not_found` was added here, as its own
reviewed decision.

Design decision 7, `matched_on` (F-3.3-A-01/F-3.3-A-02/F-3.3-A-03, added
2026-08-08, fix round 3). PubTator3's `/entity/autocomplete/` response
carries a `match` field on every row (e.g. `"Multiple matches"`,
`"Matched on name <m>BRCA1</m>"`), the upstream's own statement of why a
row matched the caller's query. Before this fix neither
`pubtator_annotate.py` nor this schema carried it, so a real, correctly
normalized entity resolved from an exact term and one resolved from a
common English word (`query="the"` returning ten confidently normalized
MeSH/Gene entities, F-3.3-A-03) were byte-indistinguishable downstream.
`matched_on` is an additive, optional `str | None` field on
`PubtatorEntity`, capped at `max_length=200` (mirrors
`litvar2_lookup_schemas.Litvar2VariantMatch.matched_on`'s own cap and
reasoning, added in the same fix round for the sibling tool). This is a
DISCLOSURE fix only, matching design decision 6's own scope discipline:
it surfaces PubTator3's own relevance signal, and deliberately does not
attempt to judge match quality or auto-refuse a weak match; that
judgment call is its own reviewed decision, not folded into this one.
`matched_on` follows design decision 6's own withhold-not-truncate
policy: an over-length value is withheld (`None`) via `_withhold_if_over`,
the same as every other `PubtatorEntity` field.

Depends on:
    - Nothing repo-local. `NCBI_PUBTATOR_RECORD_URL_PATTERN` is defined here,
      not imported from `ncbi_efetch_schemas.py` or `ncbi_dbsnp_schemas.py`,
      per design decision 3 above.

Reads:
    - Nothing at import time, beyond its own self-verification assertions
      against literal sample strings (no environment, no filesystem).

Writes:
    - Nothing.

Depended by:
    - system_03_search_agent.tools.pubtator_annotate (T-3.3-05)
    - system_03_search_agent.harness.cache, for tool schema registration
      (T-3.3-07, not yet done)
    - tests/system_03_search_agent/tools/test_pubtator_annotate_premise.py,
      via `PubtatorAnnotateInput(**payload)` in its `_run` helper
"""

from __future__ import annotations

import re
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

# Section 6.4 line 1162, copied verbatim. Deliberately NOT
# ncbi_efetch_schemas.NCBI_EFETCH_RECORD_URL_PATTERN or
# ncbi_dbsnp_schemas.NCBI_DBSNP_RECORD_URL_PATTERN: see design decision 3 in
# the module docstring for why this tool's pattern must stay independent and
# scoped to `pubmed.` only.
NCBI_PUBTATOR_RECORD_URL_PATTERN: Final = r"^https://pubmed\.ncbi\.nlm\.nih\.gov/"

_MAX_QUERY_CHARS: Final[int] = 200
_MAX_LIMIT: Final[int] = 20
_MAX_PMID_CHARS: Final[int] = 15
_MAX_PMIDS: Final[int] = 20

_MAX_MODE_CHARS: Final[int] = 25
_MAX_ENTITIES: Final[int] = 20
_MAX_PUBTATOR_ID_CHARS: Final[int] = 40
_MAX_BIOTYPE_CHARS: Final[int] = 20
_MAX_DB_CHARS: Final[int] = 20
_MAX_DB_ID_CHARS: Final[int] = 30
_MAX_ENTITY_NAME_CHARS: Final[int] = 100
_MAX_DESCRIPTION_CHARS: Final[int] = 300

_MAX_PUBLICATIONS: Final[int] = 20
_MAX_ANNOTATIONS: Final[int] = 100
_MAX_ANNOTATION_TYPE_CHARS: Final[int] = 20
_MAX_ANNOTATION_IDENTIFIER_CHARS: Final[int] = 60
_MAX_ANNOTATION_NORMALIZED_ID_CHARS: Final[int] = 60
_MAX_ANNOTATION_BIOTYPE_CHARS: Final[int] = 20
_MAX_ANNOTATION_NAME_CHARS: Final[int] = 100
_MAX_SOURCE_URL_CHARS: Final[int] = 200

_MAX_ERROR_CHARS: Final[int] = 500


# ---------------------------------------------------------------------------
# Input: a 2-way discriminated union on `mode`. See design decision 1.
# ---------------------------------------------------------------------------


class PubtatorEntityLookupInput(BaseModel):
    """`GET /entity/autocomplete/?query={text}&limit={n}`. The `entity_lookup` branch.

    `query` carries `min_length=1` (design decision 2, F-3.3-02): an empty
    query is rejected here, before any network call, closing the only
    realistic path to PubTator3's undocumented third error-body shape (a
    bare JSON array of strings on an empty-query 400).
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["entity_lookup"]
    query: Annotated[str, Field(min_length=1, max_length=_MAX_QUERY_CHARS)]
    limit: Annotated[int, Field(ge=1, le=_MAX_LIMIT)] = 10


class PubtatorAnnotatePublicationsInput(BaseModel):
    """`GET /publications/export/biocjson?pmids={csv}`. The `annotate_publications` branch.

    `pmids` carries `min_length=1` (design decision 5, F-3.3-A-06): an
    empty list is a guaranteed-useless network call that lands on
    PubTator3's undocumented bare-array error shape (F-3.3-02), the exact
    gap design decision 2's own `query` fix left open on this sibling
    field.
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["annotate_publications"]
    pmids: Annotated[
        list[Annotated[str, Field(max_length=_MAX_PMID_CHARS)]],
        Field(min_length=1, max_length=_MAX_PMIDS),
    ]


_PubtatorAnnotateModeUnion = PubtatorEntityLookupInput | PubtatorAnnotatePublicationsInput
PubtatorAnnotateMode = Annotated[_PubtatorAnnotateModeUnion, Field(discriminator="mode")]


class PubtatorAnnotateInput(RootModel[PubtatorAnnotateMode]):
    """The 2-way discriminated union entry point. See design decision 1 in
    the module docstring for the `.root` access pattern callers must use,
    and for why both `.model_validate(payload)` and `(**payload)`
    construction work identically for a `RootModel`.
    """


# ---------------------------------------------------------------------------
# Output: one shape for both modes (Section 6.4's single output schema).
# ---------------------------------------------------------------------------


class PubtatorEntity(BaseModel):
    """One entity match, from `entity/autocomplete`'s response array.

    All seven fields are schema-optional: Section 6.4's printed item schema
    (lines 1126-1136) carries no `required` list of its own, and
    `matched_on` is this file's own additive field (design decision 7).
    Each field that exceeds its own cap is withheld (set to `None`), never
    truncated; see design decision 6 in the module docstring for why there
    is no per-item disclosure field naming which one, unlike the top-level
    `pmids_not_found`.
    """

    model_config = ConfigDict(extra="forbid")

    pubtator_id: Annotated[str | None, Field(default=None, max_length=_MAX_PUBTATOR_ID_CHARS)] = None
    biotype: Annotated[str | None, Field(default=None, max_length=_MAX_BIOTYPE_CHARS)] = None
    db: Annotated[str | None, Field(default=None, max_length=_MAX_DB_CHARS)] = None
    db_id: Annotated[str | None, Field(default=None, max_length=_MAX_DB_ID_CHARS)] = None
    name: Annotated[str | None, Field(default=None, max_length=_MAX_ENTITY_NAME_CHARS)] = None
    description: Annotated[str | None, Field(default=None, max_length=_MAX_DESCRIPTION_CHARS)] = None
    matched_on: Annotated[str | None, Field(default=None, max_length=200)] = None


class PubtatorAnnotation(BaseModel):
    """One annotation, from `.PubTator3[i].passages[].annotations[].infons`.

    All six fields are schema-optional, same reasoning as `PubtatorEntity`
    above. `normalized_id` is nullable per Section 6.4's own
    `"type": ["string", "null"]`; PubTator3's raw `infons.normalized_id` is
    sometimes an int (live-confirmed 2026-08-08, e.g. `672`) rather than a
    string, so `pubtator_annotate.py` coerces it to `str` before this model
    ever sees it, never passes the raw int through.
    """

    model_config = ConfigDict(extra="forbid")

    type: Annotated[str | None, Field(default=None, max_length=_MAX_ANNOTATION_TYPE_CHARS)] = None
    identifier: Annotated[
        str | None, Field(default=None, max_length=_MAX_ANNOTATION_IDENTIFIER_CHARS)
    ] = None
    normalized_id: Annotated[
        str | None, Field(default=None, max_length=_MAX_ANNOTATION_NORMALIZED_ID_CHARS)
    ] = None
    valid: bool | None = None
    biotype: Annotated[
        str | None, Field(default=None, max_length=_MAX_ANNOTATION_BIOTYPE_CHARS)
    ] = None
    name: Annotated[str | None, Field(default=None, max_length=_MAX_ANNOTATION_NAME_CHARS)] = None


class PubtatorPublication(BaseModel):
    """One publication, unwrapped from `.PubTator3[i]`.

    `source_url` is the human-facing PubMed record page
    (`https://pubmed.ncbi.nlm.nih.gov/{pmid}/`), never the PubTator3 API host
    this tool actually fetches from; see design decision 3 in the module
    docstring.
    """

    model_config = ConfigDict(extra="forbid")

    pmid: Annotated[str | None, Field(default=None, max_length=_MAX_PMID_CHARS)] = None
    annotations: Annotated[
        list[PubtatorAnnotation],
        Field(default_factory=list, max_length=_MAX_ANNOTATIONS),
    ] = Field(default_factory=list)
    source_url: Annotated[
        str | None,
        Field(
            default=None,
            max_length=_MAX_SOURCE_URL_CHARS,
            pattern=NCBI_PUBTATOR_RECORD_URL_PATTERN,
        ),
    ] = None


class PubtatorAnnotateOutput(BaseModel):
    """The tool's return value. Section 6.4's `pubtator_annotate.output`,
    plus the additive `pmids_not_found` field (design decision 4, F-3.3-01).

    Only `status` and `mode` are required, per Section 6.4 line 1117.
    `status` uses the same three-value pattern-constraint style as every
    other tool's output in this repo (`cypher_schemas.CypherQueryOutput`,
    `NcbiEfetchOutput`, `NcbiDbsnpOutput`), for the same reason: it is a bare
    string in the wire format, and a regex pattern is the direct
    implementation of the spec's `enum`.
    """

    model_config = ConfigDict(extra="forbid")

    status: Annotated[str, Field(pattern=r"^(ok|empty|error)$")]
    mode: Annotated[str, Field(max_length=_MAX_MODE_CHARS)]
    entities: Annotated[
        list[PubtatorEntity],
        Field(default_factory=list, max_length=_MAX_ENTITIES),
    ] = Field(default_factory=list)
    publications: Annotated[
        list[PubtatorPublication],
        Field(default_factory=list, max_length=_MAX_PUBLICATIONS),
    ] = Field(default_factory=list)
    error: Annotated[str | None, Field(default=None, max_length=_MAX_ERROR_CHARS)] = None
    pmids_not_found: Annotated[
        list[Annotated[str, Field(max_length=_MAX_PMID_CHARS)]],
        Field(
            default_factory=list,
            max_length=_MAX_PMIDS,
            description=(
                "PMIDs requested in an annotate_publications call that "
                "PubTator3 silently dropped from its own response (F-3.3-01). "
                "Empty when every requested PMID resolved. Additive field, "
                "not part of the locked Section 6.4 property set; see design "
                "decision 4 in this module's docstring."
            ),
        ),
    ] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Self-verification: fail at import time, not at first citation, if the
# pattern above stops matching the shapes it is supposed to accept or
# reject. Mirrors the import-time assertion idiom `ncbi_dbsnp_schemas.py`
# and `ncbi_eutils_actions.py`/`ncbi_pubchem_actions.py` already use for
# their own record-URL templates (see design decision 3 above).
# ---------------------------------------------------------------------------

_ACCEPT_SAMPLES: Final[tuple[str, ...]] = (
    "https://pubmed.ncbi.nlm.nih.gov/34083286/",
    "https://pubmed.ncbi.nlm.nih.gov/32942285/",
)
_REJECT_SAMPLES: Final[tuple[str, ...]] = (
    # The PubTator3 API host itself must never validate as a citation: a
    # reader following it would get a raw API response, not the human-facing
    # PubMed record page (Tool_implementation_mechanics.md, "citation URLs
    # pointing at the fetch host" cross-tool trap).
    "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/entity/autocomplete/?query=BRCA1",
    # A real NCBI record page, but the WRONG kind of citation for this
    # tool's only citable record type (a PubMed publication): this is the
    # exact case a broader, unscoped pattern (like NCBI_EFETCH_RECORD_URL_
    # PATTERN, which has no path or subdomain requirement narrow enough to
    # exclude it) would wrongly accept. See design decision 3.
    "https://www.ncbi.nlm.nih.gov/gene/7157",
    # A dbSNP record page: also a real, wrong-kind-of-record NCBI URL for
    # this tool specifically.
    "https://www.ncbi.nlm.nih.gov/snp/rs334",
    # An unrelated NCBI fetch host, same reasoning as the PubTator3 host
    # above.
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=34083286",
)

for _sample in _ACCEPT_SAMPLES:
    assert re.match(NCBI_PUBTATOR_RECORD_URL_PATTERN, _sample) is not None, (
        f"NCBI_PUBTATOR_RECORD_URL_PATTERN wrongly rejects a valid PubMed "
        f"record URL: {_sample!r}"
    )
for _sample in _REJECT_SAMPLES:
    assert re.match(NCBI_PUBTATOR_RECORD_URL_PATTERN, _sample) is None, (
        f"NCBI_PUBTATOR_RECORD_URL_PATTERN wrongly accepts a non-PubMed-record "
        f"URL: {_sample!r}"
    )
del _sample
