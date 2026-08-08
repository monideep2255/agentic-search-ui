"""Pydantic v2 input and output schemas for the ncbi_dbsnp tool (T-3.2-03).

Technical_specification.md Section 6.3 locks the JSON schema for both the
tool input and the tool output. These models are the typed, validated
implementation of that lock: every field, length cap, enum, and pattern here
mirrors the spec's `ncbi_dbsnp.input` and `ncbi_dbsnp.output` JSON schemas
exactly, plus `extra="forbid"` on every model with its own field set so an
unexpected field is rejected rather than silently dropped or passed through
(production-standards.md's multi-agent pipeline gate).

Design decision 1, the input is one flat model, not a discriminated union:
`ncbi_efetch_schemas.NcbiEfetchInput` is a 7-way union because each of its
`action` values selects a genuinely different request shape (different
required fields, different downstream endpoint). `ncbi_dbsnp`'s three
`query_type` values (`rsid`, `hgvs`, `spdi`) do not: all three share the
exact same two-field shape, `query` plus `include_clinical`, and Section
6.3's own printed input schema encodes this directly as one object with a
`query_type` enum, not three sibling branches. A discriminated union here
would model a distinction the spec itself does not draw at the schema
level; `query_type` is a plain `Literal` field on one model instead.

Design decision 2, `query` is a bounded string, not shape-validated against
`query_type`, EXCEPT for one narrow, live-confirmed-necessary carve-out for
`query_type == "rsid"` (revised 2026-08-08, F-3.2-A-02 / J-03). The
original reasoning below still holds for `spdi` and `hgvs`: the live
pre-build probes in `tracker/phase_3.2.md` confirm Variation Services
itself returns a structured 400 (`{"error": {"code": 400, "message":
"Invalid SPDI: '...'"}}`) for a malformed SPDI or HGVS expression, so
rejecting either at the schema layer would make that live classification
path unreachable and untestable from a schema-valid input, exactly the
failure mode `ncbi_efetch_schemas.py` already avoided for `db`.

CORRECTION for the `rsid` branch specifically: the claim this design
decision used to make, "the live endpoint returns a structured 400 for
malformed input", is FALSE for `refsnp/{id}`, live-verified by the judge
(J-03) and reproduced again while fixing F-3.2-A-02: `refsnp/{id}` accepts
ANY integer as a well-formed request and returns a genuine 200 with a real
(but possibly unrelated) record, so there is no malformed shape for that
endpoint to reject. Confirmed live 2026-08-08:
`GET /variation/v0/refsnp/3043` (HBB's own NCBI Gene ID, no `rs` prefix)
returns `HTTP 200` with a real, unrelated ALDH1B1 variant on chromosome 9,
not a 404 and not an error. A caller sending any bare numeric identifier
from an unrelated namespace (a Gene ID, a PMID, a ClinVar Variation ID)
with `query_type: "rsid"` therefore got back a confident, fully cited
answer about the wrong variant, with no malformed-input signal anywhere in
the pipeline: the fabricated-citation shape the whole system exists to
prevent, reached with no malformed input at all.

So `query_type == "rsid"` IS shape-validated here, narrowly: `query` must
match `^rs\\d+$` (case-insensitive), i.e. an explicit `rs`/`RS` prefix
followed by digits. This closes exactly the bare-foreign-identifier path
(a numeric id with no `rs` prefix); it does NOT validate that the digits
after `rs` name a real, existing rsid, which is still `refsnp/{id}`'s own
job to reject via its genuine 404 (a caller sending a syntactically valid
but nonexistent `rs999999999999` still reaches the live endpoint and gets
a real 404, exactly as before). `spdi` and `hgvs` are unchanged: whether
either string is well-formed for its declared `query_type` is still
`ncbi_dbsnp.py`'s job (T-3.2-04), decided from the live response, since
both of those endpoints' non-200-is-error contract was independently
live-confirmed and remains intact.

Design decision 3, `source_url` and the fetch-host-versus-record-host
split: this tool fetches from `api.ncbi.nlm.nih.gov` (Variation Services)
and `eutils.ncbi.nlm.nih.gov` (dbSNP ESummary), but a citation must resolve
to a page a human can read, `www.ncbi.nlm.nih.gov/snp/{rsid}` or
`pubmed.ncbi.nlm.nih.gov/snp/{rsid}`. Section 6.3's own pattern at line
1055 is `^https://(www\\.|pubmed\\.)?ncbi\\.nlm\\.nih\\.gov/snp/`, narrower
than `ncbi_efetch_schemas.NCBI_EFETCH_RECORD_URL_PATTERN`
(`^https://((www\\.|pubmed\\.|pubchem\\.)?ncbi\\.nlm\\.nih\\.gov|(www\\.)?
omim\\.org)/`), which has no path requirement at all: any path under the
allowed hosts passes it, including `/gene/7157`, which is not a dbSNP
record. Reusing the efetch pattern here would silently widen this tool's
contract to accept a citation URL that resolves to the wrong kind of NCBI
record entirely, a real correctness gap for a citation-grounded system, not
a cosmetic one. So `NCBI_DBSNP_RECORD_URL_PATTERN` is defined locally in
this file, copied verbatim from Section 6.3 line 1055, never imported from
`ncbi_efetch_schemas.py` or shared with it. An import-time assertion block
below proves it accepts a real `/snp/` URL on both allowed subdomains and
rejects both the fetch host and a same-host-wrong-path URL, the same
self-verification idiom `ncbi_eutils_actions.py` and `ncbi_pubchem_actions.py`
already use for their own record-URL templates, run here directly against
the pattern since this file has no per-database template dict to loop over.

Design decision 4, which output fields are required: Section 6.3's output
schema states `"required": ["status", "rsid", "spdi_canonical"]` (line
1020) and nothing else. So those three fields are non-optional, non-`None`
on `NcbiDbsnpOutput`, while every other field (`alleles`, `chrpos`,
`clinical_significance`, `functional_consequence`, `genes`,
`population_frequencies`, `source_url`, `error`) is schema-optional with a
default, the same "only what the spec's own `required` list names is
required" discipline `ncbi_efetch_schemas.NcbiEfetchRecord`'s module
docstring already documents. One consequence worth flagging for whoever
writes `ncbi_dbsnp.py` (T-3.2-04): the spec requires `rsid` and
`spdi_canonical` to be present even on `status: "error"` (a nonexistent
rsid, a malformed SPDI or HGVS expression). This schema enforces only that
the fields are present and within their length caps; it does not and
cannot decide what an error response should actually put in them (the
caller's raw, unresolved `query`? an empty string? echoing back what little
Variation Services returned before failing?). That is a T-3.2-04 judgment
call the schema surfaces but does not make.

Design decision 5, `genes` and `population_frequencies` item shapes: both
are separate nested models (`NcbiDbsnpGene`, `NcbiDbsnpPopulationFrequency`)
rather than plain `dict[str, Any]`, each with `extra="forbid"`, mirroring
Section 6.3's own `"additionalProperties": false` on both item schemas
(lines 1035, 1044). Neither nested schema's own printed `properties` block
carries a `required` list, so every field on both nested models is
schema-optional, the same reasoning as design decision 4 applied one level
down. This schema does NOT encode how the raw dbSNP ESummary response maps
onto these structured shapes: `tracker/phase_3.2.md`'s F-3.2-01
(`global_mafs[].freq` is a compound string, `"A=0.027356/137"`, not
separate `allele`/`frequency`/sample-count fields) and F-3.2-02
(`clinical_significance` and `fxn_class` are single comma-joined strings in
raw ESummary, not arrays) are both real, filed gaps between what the live
API returns and what this OUTPUT contract requires. Both are entirely
`ncbi_dbsnp.py`'s (T-3.2-04's) parsing responsibility; this schema pins
only the post-parsing shape the tool must produce, never the raw wire
shape it must parse from.

Design decision 6, `NcbiDbsnpPopulationFrequency.allele_role` (added
2026-08-08, F-3.2-A-03). Live-reproduced on rs334 itself: `global_mafs`
returns a flat list mixing the REFERENCE allele's frequency and one or
more ALT alleles' frequencies at the same position, with nothing in the
output connecting any one row back to which allele `spdi_canonical` names.
A reader sees a 50 percent frequency sitting unmarked beside the real
variant's own frequency and has no way to tell, without independently
parsing the SPDI string themselves, whether that 50 percent describes the
variant or the reference sequence at that position.

Two fixes were considered: (1) have `_extract_canonical_spdi_from_refsnp`
in `ncbi_dbsnp.py` PREFER whichever allele has the most or best-supported
population data when picking which variant `spdi_canonical` names, or (2)
leave allele SELECTION alone and LABEL each `population_frequencies` row
with its relationship to `spdi_canonical`'s own two alleles. (1) was
rejected: "most/best-supported" has no single defensible definition (by
which population database, by highest frequency, by number of studies
reporting it), changing which physical variant `spdi_canonical` names
based on incidental population-database coverage would be surprising to
any existing caller who reasonably expects `spdi_canonical` to be a stable
property of the record rather than a function of which populations happen
to have sequenced it, and reselection does nothing to help a caller
attribute the ALREADY-PRESENT reference-allele rows, which are informative
data, not noise, and must stay in the list. (2) was chosen: `allele_role`
states, for every row, whether its `allele` matches `spdi_canonical`'s own
INSERTED allele (`"variant"`), its DELETED allele (`"reference"`), or
neither (`"other"`, a third allele at a multiallelic position). This
answers the judge's stated bar directly, "which population_frequencies
rows describe the SAME allele spdi_canonical names versus a different
one", without touching allele selection, and it is deterministic and
testable from `spdi_canonical`'s own already-published string, not a new
source of truth. `None` only when `ncbi_dbsnp.py` could not parse
`spdi_canonical` into `seq_id:position:deleted:inserted` at all (should not
occur on a genuine `ok` path with clinical data, since `spdi_canonical` is
required and non-empty there); kept optional rather than required, same
reasoning as design decision 5's other two fields.

Design decision 7, `NcbiDbsnpOutput.fields_withheld` (added 2026-08-08,
F-3.2-A-15, independent re-review of the F-3.2-A-01 fix). Round 1 of the
truncation-policy fix made ANY over-cap field, an over-length
`clinical_significance` term for example, refuse the WHOLE call,
`status: "error"`, discarding gene linkage, SPDI, and population data that
had already fetched successfully. Live-measured to cost roughly 10.4
percent of real clinically-cited variants their entire record over a
single over-cap field, including flagship variants this repo already uses
as ground truth (rs429358, rs6025, rs1801133, rs1800562, rs1042522,
rs80359198). `fields_withheld` is round 2's fix: a plain string list, each
entry the name of an output field whose value was withheld because it
would have exceeded this schema's own length or count cap, e.g.
`["clinical_significance"]`. A withheld field is present in this list AND
empty/`None` in its own place in the output (never a truncated or
shortened value); a field that is genuinely absent or empty in the source
data is never added here. This is the caller-visible signal that
distinguishes "nothing here" from "something here, dropped for exceeding a
cap" from "a different, shorter, wrong value truncated into place", the
three distinct meanings a bare empty/`None` field could otherwise carry
ambiguously. `spdi_canonical` never appears in this list: it is the sole
field `ncbi_dbsnp.py` still refuses the WHOLE call for on overflow (see
that module's own docstring for why), so a response that ships at all
never has a withheld `spdi_canonical`. Bounded the same way every other
list field on this model is (`max_length` on the list, `max_length` on
each item), per the multi-agent pipeline gate; the possible values are a
small, closed set of this model's own field names (`alleles`,
`clinical_significance`, `functional_consequence`, `genes`,
`population_frequencies`, `chrpos`), so 10 items of 30 characters each is
ample headroom, not a tight fit.

Depends on:
    - Nothing repo-local. `NCBI_DBSNP_RECORD_URL_PATTERN` is defined here,
      not imported from `ncbi_efetch_schemas.py`, per design decision 3
      above.

Reads:
    - Nothing at import time, beyond its own self-verification assertions
      against literal sample strings (no environment, no filesystem).

Writes:
    - Nothing.

Depended by:
    - system_03_search_agent.tools.ncbi_dbsnp (T-3.2-04, not yet written)
    - system_03_search_agent.harness.cache, for tool schema registration
      (T-3.2-05, not yet written)
    - tests/system_03_search_agent/tools/test_ncbi_dbsnp_premise.py, via
      `NcbiDbsnpInput.model_validate` and `NcbiDbsnpOutput.model_validate`
      once T-3.2-01's gate is unblocked by T-3.2-04
"""

from __future__ import annotations

import re
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Section 6.3 line 1055, copied verbatim. Deliberately NOT
# ncbi_efetch_schemas.NCBI_EFETCH_RECORD_URL_PATTERN: see design decision 3
# in the module docstring for why the two patterns must stay independent.
# Narrower than the efetch pattern in two ways: no `pubchem.` alternative
# (dbSNP records are never PubChem-hosted) and a required `/snp/` path
# segment, which the efetch pattern has no equivalent of at all.
NCBI_DBSNP_RECORD_URL_PATTERN: Final = r"^https://(www\.|pubmed\.)?ncbi\.nlm\.nih\.gov/snp/"

# F-3.2-A-02 / J-03 (design decision 2, revised): an explicit `rs`/`RS`
# prefix followed by digits, case-insensitive. Deliberately does NOT
# require the digits to name a real, existing rsid; that classification
# stays live, via refsnp/{id}'s genuine 404, exactly as design decision 2
# describes.
#
# NEW-4 (independent re-review, fix round 1): anchored on `\Z`, not `$`.
# In Python, `$` matches immediately before a trailing newline as well as
# at the true end of string, so a naive `$`-anchored full-match check would
# accept "rs334\n" as well-formed. Not currently exploitable: this pattern
# is only ever matched against `self.query.strip()`
# (`_validate_rsid_shape` below), which already removes a trailing
# newline before the match runs. Fixed anyway as a one-line, no-risk
# correctness change, since `\Z` is the correct anchor for "end of string,
# full stop" regardless of what the caller does before matching, and a
# future refactor that drops the `.strip()` call should not silently
# reopen this gap.
_RSID_SHAPE_PATTERN: Final = re.compile(r"^rs[0-9]+\Z", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Input: one flat model. See design decision 1 for why this is not a union.
# ---------------------------------------------------------------------------


class NcbiDbsnpInput(BaseModel):
    """The tool's single input shape, Section 6.3's `ncbi_dbsnp.input`.

    `query_type` selects which Variation Services endpoint family
    `ncbi_dbsnp.py` calls (`refsnp/{rsid}`, `hgvs/{hgvs}/contextuals`, or
    `spdi/{spdi}/canonical_representative` plus
    `spdi/{spdi}/all_equivalent_contextual`). `query` is not shape-validated
    against `query_type` for `hgvs`/`spdi`: see design decision 2 above for
    why. `rsid` is the one exception, added 2026-08-08 (F-3.2-A-02 / J-03):
    `_validate_rsid_shape` below rejects a `query` with no `rs`/`RS` prefix
    when `query_type == "rsid"`, since `refsnp/{id}` accepts any bare
    integer as well-formed and returns a real, unrelated record rather than
    an error, live-confirmed to have no malformed shape for that endpoint to
    reject the way `spdi`/`hgvs` do.
    """

    model_config = ConfigDict(extra="forbid")

    query: Annotated[
        str,
        Field(max_length=200, description="rsid (rs334), HGVS expression, or SPDI"),
    ]
    query_type: Literal["rsid", "hgvs", "spdi"]
    include_clinical: Annotated[
        bool,
        Field(
            description=(
                "Also fetch dbSNP ESummary for clinical_significance, "
                "global_mafs, genes, fxn_class"
            )
        ),
    ] = True

    @model_validator(mode="after")
    def _validate_rsid_shape(self) -> NcbiDbsnpInput:
        """F-3.2-A-02 / J-03: reject a bare numeric `query` for `query_type: "rsid"`.

        Does NOT validate that the digits after `rs` name a real, existing
        rsid; `refsnp/{id}`'s own live 404 still owns that classification,
        unchanged. This closes only the narrower, live-reproduced gap: a
        numeric identifier from an unrelated namespace (a Gene ID, a PMID, a
        ClinVar Variation ID) sent with no `rs` prefix, which the live
        endpoint accepts as well-formed and answers with a real but
        unrelated record, never an error.
        """
        if self.query_type == "rsid" and not _RSID_SHAPE_PATTERN.match(self.query.strip()):
            raise ValueError(
                f"query_type 'rsid' requires query to start with 'rs' "
                f"followed by digits (e.g. 'rs334'); {self.query!r} has no "
                "'rs' prefix. Variation Services' refsnp/{id} endpoint "
                "accepts any bare integer as well-formed and would answer "
                "with a real but UNRELATED record (F-3.2-A-02), not an "
                "error; a bare numeric identifier from another namespace "
                "(a Gene ID, a PMID, a ClinVar Variation ID) is rejected "
                "here instead. Retry with an 'rs'-prefixed rsid, or use "
                "query_type 'spdi'/'hgvs' if the identifier is not an rsid."
            )
        return self


# ---------------------------------------------------------------------------
# Output: one shape, Section 6.3's `ncbi_dbsnp.output`.
# ---------------------------------------------------------------------------


class NcbiDbsnpGene(BaseModel):
    """One gene linked to the variant, from dbSNP ESummary's `genes` field.

    Both fields are schema-optional: Section 6.3's printed item schema (line
    1033-1037) carries no `required` list of its own. See design decision 5
    in the module docstring. This model does not parse dbSNP ESummary's raw
    `genes` shape; it only pins what `ncbi_dbsnp.py` must produce after
    parsing it.
    """

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str | None, Field(default=None, max_length=30)] = None
    gene_id: Annotated[str | None, Field(default=None, max_length=20)] = None


class NcbiDbsnpPopulationFrequency(BaseModel):
    """One population's allele frequency, parsed from dbSNP's `global_mafs`.

    `population`, `allele`, and `frequency` are schema-optional, same
    reasoning as `NcbiDbsnpGene` above. `frequency` is a plain `float`,
    never the raw `global_mafs[].freq` compound string
    (`"A=0.027356/137"`, F-3.2-01): parsing that string into `allele` and
    `frequency` separately is `ncbi_dbsnp.py`'s job, not this schema's,
    which only pins the already-parsed shape.

    `allele_role` (added 2026-08-08, F-3.2-A-03; see design decision 6 in
    the module docstring) states this row's relationship to
    `spdi_canonical`'s own two alleles: `"variant"` when `allele` matches
    `spdi_canonical`'s INSERTED sequence (the variant the record is
    actually about), `"reference"` when it matches the DELETED sequence,
    `"other"` for a third allele at a multiallelic position, and `None`
    only when `ncbi_dbsnp.py` could not parse `spdi_canonical` at all.
    Without this field a reader cannot tell, without independently parsing
    `spdi_canonical` themselves, whether a given frequency describes the
    variant itself or the reference sequence at the same position.
    """

    model_config = ConfigDict(extra="forbid")

    population: Annotated[str | None, Field(default=None, max_length=20)] = None
    allele: Annotated[str | None, Field(default=None, max_length=10)] = None
    frequency: float | None = None
    allele_role: Annotated[
        Literal["variant", "reference", "other"] | None,
        Field(
            default=None,
            description=(
                "This row's allele relative to spdi_canonical: 'variant' "
                "(matches the inserted/variant allele), 'reference' "
                "(matches the deleted/reference allele), or 'other' (a "
                "third allele at a multiallelic position)."
            ),
        ),
    ] = None


class NcbiDbsnpOutput(BaseModel):
    """The tool's return value. Section 6.3's `ncbi_dbsnp.output`.

    Only `status`, `rsid`, and `spdi_canonical` are required, per Section
    6.3 line 1020. See design decision 4 in the module docstring for what
    that implies for an `error`-status response, and for why every other
    field here defaults to an empty collection or `None` rather than being
    required.

    `status` uses the same three-value pattern-constraint style as
    `ncbi_efetch_schemas.NcbiEfetchOutput.status` and
    `cypher_schemas.CypherQueryOutput.status`, for the same reason: it is a
    bare string in the wire format, and a regex pattern is the direct
    implementation of the spec's `enum` rather than a Python `Enum` type the
    spec never asked for.
    """

    model_config = ConfigDict(extra="forbid")

    status: Annotated[str, Field(pattern=r"^(ok|empty|error)$")]
    rsid: Annotated[str, Field(max_length=20)]
    spdi_canonical: Annotated[str, Field(max_length=150)]
    alleles: Annotated[
        list[Annotated[str, Field(max_length=20)]],
        Field(default_factory=list, max_length=10),
    ] = Field(default_factory=list)
    chrpos: Annotated[str | None, Field(default=None, max_length=30)] = None
    clinical_significance: Annotated[
        list[Annotated[str, Field(max_length=40)]],
        Field(default_factory=list, max_length=10),
    ] = Field(default_factory=list)
    functional_consequence: Annotated[
        list[Annotated[str, Field(max_length=60)]],
        Field(default_factory=list, max_length=10),
    ] = Field(default_factory=list)
    genes: Annotated[
        list[NcbiDbsnpGene],
        Field(default_factory=list, max_length=10),
    ] = Field(default_factory=list)
    population_frequencies: Annotated[
        list[NcbiDbsnpPopulationFrequency],
        Field(default_factory=list, max_length=30),
    ] = Field(default_factory=list)
    source_url: Annotated[
        str | None,
        Field(default=None, max_length=200, pattern=NCBI_DBSNP_RECORD_URL_PATTERN),
    ] = None
    error: Annotated[str | None, Field(default=None, max_length=500)] = None
    fields_withheld: Annotated[
        list[Annotated[str, Field(max_length=30)]],
        Field(
            default_factory=list,
            max_length=10,
            description=(
                "Names of output fields whose value was withheld because it "
                "would have exceeded this schema's own length/count cap "
                "(F-3.2-A-15). A withheld field is empty/None in its own "
                "place on this output, never a truncated or shortened "
                "value; its absence from this list means any value present "
                "for that field is the REAL, COMPLETE value, not one "
                "trimmed to fit. spdi_canonical never appears here: it is "
                "the sole field this tool still refuses the WHOLE call for "
                "on overflow, so a response that ships at all never has a "
                "withheld spdi_canonical."
            ),
        ),
    ] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Self-verification: fail at import time, not at first citation, if the
# pattern above stops matching the shapes it is supposed to accept or
# reject. Mirrors the import-time assertion idiom
# `ncbi_eutils_actions.py`/`ncbi_pubchem_actions.py` use for their own
# record-URL templates (see the module docstring's design decision 3).
# ---------------------------------------------------------------------------

_ACCEPT_SAMPLES: Final[tuple[str, ...]] = (
    "https://www.ncbi.nlm.nih.gov/snp/rs334",
    "https://pubmed.ncbi.nlm.nih.gov/snp/rs334",
    # No subdomain at all is also a documented-valid form of the pattern's
    # optional (www.|pubmed.)? group.
    "https://ncbi.nlm.nih.gov/snp/rs334",
)
_REJECT_SAMPLES: Final[tuple[str, ...]] = (
    # The Variation Services fetch host itself must never validate as a
    # citation: a reader following it would get a raw API response, not
    # the human-facing dbSNP record page (Tool_implementation_mechanics.md,
    # "citation URLs pointing at the fetch host" cross-tool trap).
    "https://api.ncbi.nlm.nih.gov/variation/v0/refsnp/334",
    # The dbSNP ESummary fetch host, same reasoning.
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=snp&id=334",
    # Right host, wrong path: a real NCBI record URL that is not a dbSNP
    # record must not validate for this tool. This is the exact case
    # NCBI_EFETCH_RECORD_URL_PATTERN would wrongly accept, since it has no
    # path requirement at all; see design decision 3.
    "https://www.ncbi.nlm.nih.gov/gene/7157",
)

for _sample in _ACCEPT_SAMPLES:
    assert re.match(NCBI_DBSNP_RECORD_URL_PATTERN, _sample) is not None, (
        f"NCBI_DBSNP_RECORD_URL_PATTERN wrongly rejects a valid dbSNP record "
        f"URL: {_sample!r}"
    )
for _sample in _REJECT_SAMPLES:
    assert re.match(NCBI_DBSNP_RECORD_URL_PATTERN, _sample) is None, (
        f"NCBI_DBSNP_RECORD_URL_PATTERN wrongly accepts a non-dbSNP-record "
        f"URL: {_sample!r}"
    )
del _sample
