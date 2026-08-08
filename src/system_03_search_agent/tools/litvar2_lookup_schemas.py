"""Pydantic v2 input and output schemas for the litvar2_lookup tool (T-3.3-04).

Technical_specification.md Section 6.5 locks the JSON schema for both the
tool input and the tool output (see `tracker/phase_3.3.md`'s reproduction).
These models are the typed, validated implementation of that lock: every
field, length cap, enum, and pattern here mirrors the spec's
`litvar2_lookup.input` and `litvar2_lookup.output` JSON schemas exactly,
plus `extra="forbid"` on every model with its own field set so an
unexpected field is rejected rather than silently dropped or passed through
(production-standards.md's multi-agent pipeline gate), plus two additive
fields the phase's own pre-build probes and findings require (below).

Design decision 1, the input IS a discriminated union, unlike
`ncbi_dbsnp_schemas.py`'s deliberate choice NOT to be one. Section 6.5's own
input schema is a genuine `oneOf` on `mode`: `variant_search` needs `query`,
`publications_lookup` needs `litvar_id`, and neither field is meaningful, or
even present, on the other branch. This is the opposite situation from
`ncbi_dbsnp`'s three `query_type` values, which all share one flat two-field
shape (see that file's own design decision 1). So this file follows
`ncbi_efetch_schemas.py`'s discriminated-union idiom instead (that file's
design decision 1): each branch gets its own sibling model with a
`Literal["<mode>"]` discriminator field and `extra="forbid"`, and
`Litvar2LookupInput` is a `pydantic.RootModel` wrapping
`Annotated[Union[...], Field(discriminator="mode")]`.

One consequence worth flagging for whoever writes `litvar2_lookup.py`
(T-3.3-06): a validated instance's mode-specific fields live under `.root`,
not on `Litvar2LookupInput` directly, the same access pattern
`NcbiEfetchInput` already documents. `Litvar2LookupInput(**payload)` (a
plain dict's keys as kwargs, the exact construction the premise gate uses
in `test_litvar2_lookup_premise.py`'s `_run` helper) works directly without
callers needing to know this is a `RootModel`: pydantic's
`RootModel.__init__` accepts `**data` and validates it against the wrapped
union when no explicit `root=` kwarg is given. Verified live against this
project's pinned pydantic (2.13.4) before relying on it here, since a
`RootModel` construction contract is exactly the kind of thing worth
confirming rather than assuming.

Design decision 2, `query` and `litvar_id` both get `minLength: 1`, added
2026-08-08 (F-3.3-02's sibling concern). Section 6.5's own `maxLength`
caps (100 for `query`, 60 for `litvar_id`) do not by themselves reject an
empty string, and this repo's pre-build probes never live-verified what
LitVar2's OWN `/variant/autocomplete/` endpoint does with an empty query
(only PubTator3's sibling endpoint was probed for that shape, returning a
THIRD undocumented error-body shape, F-3.3-02, a bare JSON array of
strings that `ncbi_transport._extract_status_coded_error_message` cannot
parse a specific reason out of). Rejecting an empty value here, before any
network call, closes the only realistic path a caller could reach an
unverified shape from in production, exactly the reasoning F-3.3-02 itself
states. `litvar_id` gets the same treatment for a related but distinct
reason: an empty id can never resolve to a real LitVar2 record and would
otherwise reach `litvar2_lookup.py`'s own encoding and request-building
logic with nothing meaningful to encode.

Design decision 3, `source_url` and the fetch-host-versus-UI-host split,
and why this tool cannot lean on its own URL pattern the way `ncbi_dbsnp`
does. Section 6.5 line 1242's own locked pattern is
`^https://(www\\.|pubmed\\.)?ncbi\\.nlm\\.nih\\.gov/`, UNSCOPED beyond host,
unlike `ncbi_dbsnp_schemas.NCBI_DBSNP_RECORD_URL_PATTERN`
(`^https://(www\\.|pubmed\\.)?ncbi\\.nlm\\.nih\\.gov/snp/`, a required
`/snp/` path segment) or `ncbi_efetch_schemas.NCBI_PUBTATOR...`-style
patterns. This file copies the spec's pattern verbatim, never imported from
either sibling file, per the same "never share a record-URL pattern across
tools" discipline `ncbi_dbsnp_schemas.py`'s own design decision 3 states.

The unscoped pattern has a real, spec-authorized consequence this tool must
handle by construction rather than by regex: LitVar2's fetch API host
(`www.ncbi.nlm.nih.gov/research/litvar2-api/...`) and a plausible
human-facing LitVar2 UI host (`www.ncbi.nlm.nih.gov/research/litvar2/...`)
are the SAME hostname, unlike `ncbi_dbsnp`'s Variation Services
(`api.ncbi.nlm.nih.gov`) and dbSNP ESummary (`eutils.ncbi.nlm.nih.gov`),
both genuinely different hosts from the citable `www.ncbi.nlm.nih.gov/snp/`
page. So `NCBI_LITVAR2_RECORD_URL_PATTERN` CANNOT, by itself, distinguish
this tool's own fetch host from a citable record page the way
`NCBI_DBSNP_RECORD_URL_PATTERN` can: both paths validate against the
pattern, since the pattern has no path requirement at all, exactly matching
Section 6.5's own text. This is not a defect in the pattern; it is what the
locked spec states, and narrowing the pattern unilaterally to add a path
requirement Section 6.5 does not name would silently tighten a locked
contract. The self-verification block below documents this residual gap
directly rather than asserting a rejection the pattern was never designed
to guarantee. It is `litvar2_lookup.py`'s own responsibility, not this
schema's, to never CONSTRUCT a `source_url` under the `/research/litvar2-api/`
path in the first place; see that module's own docstring for how.

Design decision 4, `fields_withheld` (F-3.3-03, added 2026-08-08). Section
6.5's locked output schema caps each `variant_matches[i].clinical_significance`
item at `maxLength: 30` (line 1236). The live rs334 response carries
`"conflicting-interpretations-of-pathogenicity"`, 44 characters, a standard
ClinVar significance term, not a malformed or adversarial value, exactly
the same class of finding build phase 3.2 made for `ncbi_dbsnp`'s own
(there 40-char) `clinical_significance` cap. Following that exact
precedent (field-level withholding via `_cap_or_withhold` in
`ncbi_dbsnp.py`, never silent truncation), `fields_withheld` is an
additive, optional `list[str] | None` field naming which
`variant_matches[i].clinical_significance` entries (and any other capped
field this tool withholds rather than truncates) were dropped and why, per
`system-design-patterns` pattern 10 ("within v1, service contract changes
are additive only: a new optional field"). Unlike `ncbi_dbsnp`'s own
`fields_withheld` (a bare list defaulting to `[]`), this field is typed
`list[str] | None` defaulting to `None`, matching this ticket's own
instruction; a caller checks truthiness (`output.fields_withheld or []`) to
treat both the same way, the exact pattern the premise gate's own case 3
already uses.

Depends on:
    - Nothing repo-local. `NCBI_LITVAR2_RECORD_URL_PATTERN` is defined
      here, not imported from `ncbi_dbsnp_schemas.py`,
      `ncbi_efetch_schemas.py`, or any sibling tool schema file, per design
      decision 3 above.

Reads:
    - Nothing at import time, beyond its own self-verification assertions
      against literal sample strings (no environment, no filesystem).

Writes:
    - Nothing.

Depended by:
    - system_03_search_agent.tools.litvar2_lookup (T-3.3-06)
    - system_03_search_agent.harness.cache, for tool schema registration
      (T-3.3-07, not yet written)
    - tests/system_03_search_agent/tools/test_litvar2_lookup_premise.py,
      via `Litvar2LookupInput(**payload)` and `Litvar2LookupOutput`
      attribute access
    - tests/system_03_search_agent/tools/test_litvar2_lookup.py
    - tests/system_03_search_agent/tools/test_litvar2_lookup_schemas.py
"""

from __future__ import annotations

import re
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

# Section 6.5 line 1242, copied verbatim. Deliberately NOT
# ncbi_dbsnp_schemas.NCBI_DBSNP_RECORD_URL_PATTERN or any other tool's
# pattern object: see design decision 3 in the module docstring for why the
# patterns must stay independent, and for the residual gap this specific
# pattern carries (it cannot, by itself, distinguish this tool's own fetch
# host from a citable UI page, since both share www.ncbi.nlm.nih.gov).
NCBI_LITVAR2_RECORD_URL_PATTERN: Final = r"^https://(www\.|pubmed\.)?ncbi\.nlm\.nih\.gov/"


# ---------------------------------------------------------------------------
# Input: a genuine 2-way discriminated union. See design decision 1.
# ---------------------------------------------------------------------------


class Litvar2VariantSearchInput(BaseModel):
    """`variant_search` branch: `GET /variant/autocomplete/?query=...`.

    `query` accepts an rsid, an HGVS expression, or a free-text variant
    name (Section 6.5's own description). `min_length=1` per design
    decision 2 in the module docstring.
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["variant_search"]
    query: Annotated[
        str,
        Field(min_length=1, max_length=100, description="rsid, HGVS, or variant name"),
    ]


class Litvar2PublicationsLookupInput(BaseModel):
    """`publications_lookup` branch: `GET /variant/get/{litvar_id}/publications`.

    `litvar_id` is the RAW, unencoded id (e.g. `litvar@rs334##`), the same
    shape `variant_search`'s own `Litvar2VariantMatch.litvar_id` output
    field returns. `litvar2_lookup.py` URL-encodes it internally before
    every call, unconditionally, regardless of whether the caller already
    encoded it; see that module's own docstring for the live-confirmed
    encoding trap this closes (an unencoded id is silently truncated at the
    `#` boundary by LitVar2 itself and 400s with a wrong "not found"
    message naming the truncated id). `min_length=1` per design decision 2
    in the module docstring.
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["publications_lookup"]
    litvar_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=60,
            description="e.g. litvar@rs334##, URL-encoded by the tool before the call",
        ),
    ]


_Litvar2ActionUnion = Litvar2VariantSearchInput | Litvar2PublicationsLookupInput
Litvar2Action = Annotated[_Litvar2ActionUnion, Field(discriminator="mode")]


class Litvar2LookupInput(RootModel[Litvar2Action]):
    """The 2-way discriminated union entry point, Section 6.5's `oneOf`.

    `Litvar2LookupInput.model_validate(payload)` and
    `Litvar2LookupInput(**payload)` both work identically: a plain dict
    shaped like one of the two Section 6.5 branches in, a validated,
    mode-routed model out. An unrecognized `mode` value, or a payload
    matching no branch's required fields, raises `pydantic.ValidationError`.
    Mode-specific fields live under `.root`
    (`Litvar2LookupInput(mode="variant_search", query="rs334").root.query`),
    the same access pattern `NcbiEfetchInput` already documents.
    """


# ---------------------------------------------------------------------------
# Output: one shape for both modes, Section 6.5's `litvar2_lookup.output`.
# ---------------------------------------------------------------------------


class Litvar2VariantMatch(BaseModel):
    """One variant match from `/variant/autocomplete/`.

    Section 6.5's item schema (lines 1227-1238) carries no `required` list
    of its own, so every field here is schema-optional with a default, the
    same "only what the spec's own `required` list names is required"
    discipline `ncbi_dbsnp_schemas.py`'s design decision 4/5 already
    documents. `litvar2_lookup.py` never truncates any of these fields to
    fit its cap: an over-length `clinical_significance` item is dropped and
    named in the output-level `fields_withheld` (F-3.3-03); an over-length
    `litvar_id` or `rsid`, the identity fields for this match, causes the
    WHOLE match to be excluded rather than shipped with a truncated,
    real-looking-but-wrong identity, the same "an identity field is never
    silently truncated" discipline `ncbi_dbsnp_schemas.py`'s
    `spdi_canonical` applies at the whole-call level, applied here at the
    single-item level instead.
    """

    model_config = ConfigDict(extra="forbid")

    litvar_id: Annotated[str | None, Field(default=None, max_length=60)] = None
    rsid: Annotated[str | None, Field(default=None, max_length=20)] = None
    gene: Annotated[
        list[Annotated[str, Field(max_length=30)]],
        Field(default_factory=list, max_length=5),
    ] = Field(default_factory=list)
    name: Annotated[str | None, Field(default=None, max_length=60)] = None
    hgvs: Annotated[str | None, Field(default=None, max_length=80)] = None
    pmids_count: Annotated[int, Field(ge=0)] = 0
    clinical_significance: Annotated[
        list[Annotated[str, Field(max_length=30)]],
        Field(default_factory=list, max_length=10),
    ] = Field(default_factory=list)


class Litvar2LookupOutput(BaseModel):
    """The tool's return value. Section 6.5's `litvar2_lookup.output`.

    Only `status` and `mode` are required, per Section 6.5 line 1218; every
    other field defaults to an empty collection, zero, or `None`, the same
    discipline `ncbi_dbsnp_schemas.py`'s design decision 4 documents for its
    own output. `status` uses the same three-value pattern-constraint style
    as `NcbiDbsnpOutput.status` and `NcbiEfetchOutput.status`, for the same
    reason: it is a bare string in the wire format, and a regex pattern is
    the direct implementation of the spec's `enum` rather than a Python
    `Enum` type the spec never asked for.

    `fields_withheld` (design decision 4) is additive, not in Section 6.5's
    own printed schema.
    """

    model_config = ConfigDict(extra="forbid")

    status: Annotated[str, Field(pattern=r"^(ok|empty|error)$")]
    mode: Annotated[str, Field(max_length=25)]
    variant_matches: Annotated[
        list[Litvar2VariantMatch],
        Field(default_factory=list, max_length=10),
    ] = Field(default_factory=list)
    pmids: Annotated[
        list[Annotated[str, Field(max_length=15)]],
        Field(default_factory=list, max_length=50),
    ] = Field(default_factory=list)
    total_pmids: Annotated[int, Field(ge=0)] = 0
    source_url: Annotated[
        str | None,
        Field(default=None, max_length=200, pattern=NCBI_LITVAR2_RECORD_URL_PATTERN),
    ] = None
    error: Annotated[str | None, Field(default=None, max_length=500)] = None
    fields_withheld: Annotated[
        list[Annotated[str, Field(max_length=150)]] | None,
        Field(
            default=None,
            max_length=20,
            description=(
                "Names/describes output values withheld because they would "
                "have exceeded this schema's own length/count cap (F-3.3-03), "
                "e.g. 'variant_matches[0].clinical_significance: "
                "conflicting-interpretations-of-pathogenicity'. A withheld "
                "value is dropped entirely (or, for an identity field, the "
                "whole match is excluded), never a truncated or shortened "
                "value. `None` or an empty list means nothing was withheld; "
                "callers should treat both the same way "
                "(`output.fields_withheld or []`)."
            ),
        ),
    ] = None


# ---------------------------------------------------------------------------
# Self-verification: fail at import time, not at first citation, if the
# pattern above stops matching the shapes it is supposed to accept or
# reject. Mirrors the import-time assertion idiom `ncbi_dbsnp_schemas.py`
# and `ncbi_eutils_actions.py`/`ncbi_pubchem_actions.py` already use for
# their own record-URL templates.
# ---------------------------------------------------------------------------

_ACCEPT_SAMPLES: Final[tuple[str, ...]] = (
    "https://www.ncbi.nlm.nih.gov/research/litvar2/?query=rs334",
    "https://pubmed.ncbi.nlm.nih.gov/33593344/",
    # No subdomain at all is also a documented-valid form of the pattern's
    # optional (www.|pubmed.)? group, matching Section 6.5's own pattern.
    "https://ncbi.nlm.nih.gov/anything",
)
_REJECT_SAMPLES: Final[tuple[str, ...]] = (
    # A different NCBI-family host entirely (Variation Services' own fetch
    # host, unrelated to LitVar2) must never validate.
    "https://api.ncbi.nlm.nih.gov/research/litvar2-api/variant/autocomplete/?query=rs334",
    # A non-NCBI host must never validate, regardless of path.
    "https://evil.example.com/ncbi.nlm.nih.gov/",
    # Plain HTTP, not HTTPS, must never validate.
    "http://www.ncbi.nlm.nih.gov/research/litvar2/?query=rs334",
)

for _sample in _ACCEPT_SAMPLES:
    assert re.match(NCBI_LITVAR2_RECORD_URL_PATTERN, _sample) is not None, (
        f"NCBI_LITVAR2_RECORD_URL_PATTERN wrongly rejects a valid LitVar2/PubMed "
        f"record URL: {_sample!r}"
    )
for _sample in _REJECT_SAMPLES:
    assert re.match(NCBI_LITVAR2_RECORD_URL_PATTERN, _sample) is None, (
        f"NCBI_LITVAR2_RECORD_URL_PATTERN wrongly accepts a non-LitVar2 URL: {_sample!r}"
    )
del _sample

# Deliberately NOT asserted as a reject sample, per design decision 3 above:
# the pattern has no path requirement at all (Section 6.5's own text), so
# this tool's OWN fetch host under the SAME hostname as a plausible UI page
# (https://www.ncbi.nlm.nih.gov/research/litvar2-api/...) also matches this
# pattern. Asserting its rejection here would fail on a pattern that is
# correctly implementing the locked spec; the real protection against ever
# citing the fetch host is `litvar2_lookup.py` never constructing that URL
# in the first place, not this pattern.
