"""Pydantic v2 input and output schemas for the ncbi_efetch tool (T-3.1-03).

Technical_specification.md Section 6.2 locks the JSON schema for both the
tool input and the tool output. These models are the typed, validated
implementation of that lock: every field, length cap, enum, and pattern here
mirrors the spec's `ncbi_efetch.input` and `ncbi_efetch.output` JSON schemas
exactly, plus `extra="forbid"` on every model with its own field set so an
unexpected field is rejected rather than silently dropped or passed through
(production-standards.md's multi-agent pipeline gate).

Design decision 1, the union structure: the input is a 7-way discriminated
union on `action` (search, fetch, summary, link, coordinate_overlap,
dataset_report, pubchem_property). The premise gate
(tests/system_03_search_agent/tools/test_ncbi_efetch_premise.py, `_call_input`)
pins only one contract: `NcbiEfetchInput.model_validate(<plain dict>)` must
exist and accept the spec's documented dict shape for each action. How the
union is structured internally is a builder decision, made here as follows.

Each action gets its own sibling model (`NcbiEfetchSearchInput`,
`NcbiEfetchFetchInput`, ...), each with a `Literal["<action>"]` discriminator
field and `extra="forbid"`. `NcbiEfetchInput` is a `pydantic.RootModel`
wrapping `Annotated[Union[...], Field(discriminator="action")]`. RootModel
was chosen over a hand-rolled `__new__`/factory-function approach because it
is pydantic v2's own documented idiom for "one name, `model_validate` works,
routes to the right member on a discriminator field", and because it keeps
`NcbiEfetchInput` a real class other modules can import, type-hint against,
and construct with `NcbiEfetchInput(root=...)`, not a bare type alias.

The one consequence worth flagging for whoever writes `ncbi_efetch.py`
(T-3.1-06 or later): a validated instance's action-specific fields live under
`.root`, not on `NcbiEfetchInput` directly. `NcbiEfetchInput.model_validate(
{"action": "search", "db": "gene", "term": "BRCA1"}).root.db` is `"gene"`.
`extra="forbid"` is not set on `NcbiEfetchInput` itself: a `RootModel` has a
single `root` field, not an open field dict, so there is no "additional
property" surface at that level to forbid. Each of the seven action models
underneath it carries `extra="forbid"` individually, which is where the
spec's per-branch `additionalProperties` behavior actually lives.

Design decision 2, `db` is a bounded string, not a closed enum, for
`search`, `fetch`, `summary`, and `link` (`dbfrom`/`db` both). Section 6.2's
printed schema lists an `enum` for `db` on three of those four branches (14
databases for `search`, 8 for `fetch`, 12 for `summary`; `link`'s `dbfrom`/
`db` were never enum-constrained in the spec, just `maxLength: 20`
free-text). Enforcing that enum in the schema was the first draft here, and
it is wrong: the premise gate's case 9, the single most load-bearing case in
that file by its own account, sends `db: "notadatabase"` for `search` and
requires the payload to reach the LIVE ESearch endpoint, which returns HTTP
200 with `esearchresult.ERROR: "Invalid db name specified: notadatabase"` in
the body. That is the whole point of the near-miss pair the premise gate
documents: an invalid db name and a genuine zero-hit search both arrive as
HTTP 200, and only body inspection tells them apart. A schema-level enum
would reject `db: "notadatabase"` with a `pydantic.ValidationError` before
`ncbi_efetch.py` ever runs, so the near-miss classification logic the whole
tool exists to get right would never be exercised, and the premise gate's
own `_call_input` helper (a bare `model_validate`, no try/except) would raise
instead of producing a gradeable `NcbiEfetchOutput`. So `db` is
`Annotated[str, Field(max_length=20)]` for these four branches: the caller
can send anything shaped like a db name, and it is `ncbi_efetch.py`'s job,
using the LIVE response, to decide `ok`/`empty`/`error`, exactly as
Section 6.2's own error-and-empty-behavior table specifies.

`coordinate_overlap`'s `db` (`dbvar`/`clinvar`), `dataset_report`'s
`report_type` (`gene`/`genome`), `pubchem_property`'s `lookup_type`
(`cid`/`name`), and `fetch`'s `rettype`/`retmode` stay `Literal[...]`. None
of the premise gate's dicts send an invalid value for any of these four, and
each one selects a genuinely different code path in tool code, not merely a
different value of the same NCBI query parameter: `coordinate_overlap`'s
`db` picks between dbVar's `ASSM`/`BASE` fields and ClinVar's `C37`/`CPOS`
fields (Section 6.2's coordinate-overlap procedure); `report_type` picks
between the `gene/id|symbol` and `genome/accession` Datasets v2 endpoint
families; `lookup_type` picks between PubChem's `cid` and `name` URL shapes.
An invalid value for any of these four cannot be classified by calling a
live endpoint the way an invalid `db` can, because there is no single
downstream endpoint to call until the value is known, so client-side
rejection is the correct and only available behavior, and a `Literal` is the
direct implementation of the spec for that case.

Design decision 3, `source_url` and the fetch-host-versus-record-host split:
this is the first tool in the repo where the host it fetches from
(`eutils.ncbi.nlm.nih.gov`, `api.ncbi.nlm.nih.gov`) differs from the host a
citation must resolve to (`www.ncbi.nlm.nih.gov`, `pubmed.ncbi.nlm.nih.gov`,
`omim.org`). `graph_schema_constants.NCBI_RECORD_URL_PATTERN`
(`^https://(www\\.|pubmed\\.)?ncbi\\.nlm\\.nih\\.gov/`) is `cypher_query`'s
pattern and does not include `omim.org`, which Section 6.2's own pattern at
line 921 does. Reusing it here would silently narrow the spec's contract (a
correct OMIM citation would fail validation) or, if `omim.org` were added to
that shared constant instead, would silently widen `cypher_query`'s contract
for a host it never emits. Both are cross-tool coupling this ticket has no
mandate to introduce, and `graph_schema_constants.py` belongs to a different
ticket. So `NCBI_EFETCH_RECORD_URL_PATTERN` is defined locally in this file,
copied verbatim from Section 6.2 line 921. It is verified, in the paired test
file, to reject both `eutils.ncbi.nlm.nih.gov` and `api.ncbi.nlm.nih.gov`
(the fetch hosts) while accepting `www.ncbi.nlm.nih.gov`,
`pubmed.ncbi.nlm.nih.gov`, and `omim.org` record URLs: the pattern has no
wildcard subdomain, so `eutils.` and `api.` never match the fixed
`(www\\.|pubmed\\.)?ncbi\\.nlm\\.nih\\.gov` alternative, the same anchoring
property `NCBI_RECORD_URL_PATTERN` already relies on for `cypher_query`.

Design decision 4, the output record's `fields` maxProperties cap: Section
6.2's output schema states `"fields": {"type": "object", "maxProperties": 40}`
(line 917), 40 rather than cypher_query's 30, because a `summary` action's
verified per-database field set (Section 6.2's ESummary table, up to 12
named fields for `sra` alone before the 7 per-population dbVar frequency
fields are added for `dbvar`) is wider than one graph row's fields. Pydantic
has no native dict-length constraint, so it is enforced with an explicit
`@field_validator`, the same approach `cypher_schemas.CypherQueryRow` uses
for its own 30-property cap.

Depends on:
    - Nothing repo-local. `NCBI_EFETCH_RECORD_URL_PATTERN` is defined here,
      not imported from graph_schema_constants.py, per design decision 3
      above.

Reads:
    - Nothing at import time.

Writes:
    - Nothing.

Depended by:
    - system_03_search_agent.tools.ncbi_efetch (not yet written; T-3.1-06 or
      later in this phase)
    - tests/system_03_search_agent/tools/test_ncbi_efetch_premise.py, via
      `NcbiEfetchInput.model_validate` in its `_call_input` helper
"""

from __future__ import annotations

from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator

# Section 6.2 output schema's maxProperties bound on a record's `fields`
# object (line 917). Wider than cypher_query's 30 because a `summary`
# action's verified per-database field set runs wider than one graph row.
_MAX_RECORD_FIELDS = 40

# Section 6.2 line 921, copied verbatim. Deliberately NOT
# graph_schema_constants.NCBI_RECORD_URL_PATTERN: see design decision 3 in
# the module docstring for why the two patterns must stay independent.
NCBI_EFETCH_RECORD_URL_PATTERN: Final = (
    r"^https://((www\.|pubmed\.)?ncbi\.nlm\.nih\.gov|(www\.)?omim\.org)/"
)


# ---------------------------------------------------------------------------
# Input: seven action models, discriminated on `action`.
# ---------------------------------------------------------------------------


class NcbiEfetchSearchInput(BaseModel):
    """ESearch: `db=<db>&term=<term>`. Section 6.2, the `search` branch.

    `db` is a bounded string, not the spec's printed 14-value enum. See
    design decision 2 in the module docstring: the premise gate's case 9
    requires an invalid db name to reach the live endpoint and be classified
    from its response body, not rejected at schema validation.
    """

    model_config = ConfigDict(extra="forbid")

    action: Literal["search"]
    db: Annotated[str, Field(max_length=20)]
    term: Annotated[str, Field(max_length=500)]
    field_tags: Annotated[
        list[Annotated[str, Field(max_length=20)]],
        Field(default_factory=list, max_length=5),
    ] = Field(default_factory=list)
    retmax: Annotated[int, Field(ge=1, le=500)] = 100
    use_history: bool = False


class NcbiEfetchFetchInput(BaseModel):
    """EFetch: `db=<db>&id=<ids>&rettype=&retmode=`. The `fetch` branch.

    `db` is a bounded string rather than the spec's printed 8-value enum;
    see design decision 2 in the module docstring.
    """

    model_config = ConfigDict(extra="forbid")

    action: Literal["fetch"]
    db: Annotated[str, Field(max_length=20)]
    ids: Annotated[
        list[Annotated[str, Field(max_length=30)]],
        Field(max_length=50),
    ]
    rettype: Literal["abstract", "docsum", "full"] = "docsum"
    retmode: Literal["xml", "text", "json"] = "json"


class NcbiEfetchSummaryInput(BaseModel):
    """ESummary: `db=<db>&id=<ids>&retmode=json`. The `summary` branch.

    `db` is a bounded string rather than the spec's printed 12-value enum;
    see design decision 2 in the module docstring.
    """

    model_config = ConfigDict(extra="forbid")

    action: Literal["summary"]
    db: Annotated[str, Field(max_length=20)]
    ids: Annotated[
        list[Annotated[str, Field(max_length=30)]],
        Field(max_length=50),
    ]


class NcbiEfetchLinkInput(BaseModel):
    """ELink: `dbfrom=<dbfrom>&db=<db>&id=<ids>`. The `link` branch.

    `db` is required and explicit per Section 6.2's own note: never left to
    the ELink default, which can be dominated by computed `pubmed_pubmed*`
    neighbors instead of the direct cross-reference the caller asked for
    (`Tool_implementation_mechanics.md:89-94`, premise gate case 5).
    """

    model_config = ConfigDict(extra="forbid")

    action: Literal["link"]
    dbfrom: Annotated[str, Field(max_length=20)]
    db: Annotated[str, Field(max_length=20)]
    ids: Annotated[
        list[Annotated[str, Field(max_length=30)]],
        Field(max_length=20),
    ]


class NcbiEfetchCoordinateOverlapInput(BaseModel):
    """dbVar/ClinVar coordinate overlap. The `coordinate_overlap` branch.

    Schema-level validation only: the exact overlap predicate
    (`placement.chr_start <= end AND placement.chr_end >= start`) is applied
    in tool code against the resolved per-assembly placement, never at the
    ESearch coarse-prefilter stage (Section 6.2's coordinate-overlap
    procedure, steps 1-4). This model does not and cannot enforce that; it
    only pins the shape of the request.
    """

    model_config = ConfigDict(extra="forbid")

    action: Literal["coordinate_overlap"]
    db: Literal["dbvar", "clinvar"]
    chromosome: Annotated[str, Field(max_length=5)]
    start: int
    end: int
    assembly: Literal["GRCh37", "GRCh38"]


class NcbiEfetchDatasetReportInput(BaseModel):
    """Datasets API v2 gene/genome report. The `dataset_report` branch.

    `gene_id`, `symbol`, `taxon`, and `accession` are all schema-optional
    because the three underlying endpoints (`gene/id/{gene_id}`,
    `gene/symbol/{symbol}/taxon/{taxon}`, `genome/accession/{accession}
    /dataset_report`) each need a different subset. Section 6.2 does not
    encode a conditional "symbol requires taxon" constraint in the printed
    JSON schema (no per-endpoint `oneOf` beneath this branch), so none is
    added here; enforcing which combination is actually callable is tool
    code's job, not this schema's.
    """

    model_config = ConfigDict(extra="forbid")

    action: Literal["dataset_report"]
    report_type: Literal["gene", "genome"]
    gene_id: Annotated[str | None, Field(default=None, max_length=20)] = None
    symbol: Annotated[str | None, Field(default=None, max_length=30)] = None
    taxon: Annotated[str | None, Field(default=None, max_length=30)] = None
    accession: Annotated[str | None, Field(default=None, max_length=20)] = None


class NcbiEfetchPubchemPropertyInput(BaseModel):
    """PubChem PUG REST property lookup. The `pubchem_property` branch."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["pubchem_property"]
    lookup_type: Literal["cid", "name"]
    value: Annotated[str, Field(max_length=200)]
    properties: Annotated[
        list[Annotated[str, Field(max_length=40)]],
        Field(default_factory=list, max_length=10),
    ] = Field(default_factory=list)


_NcbiEfetchActionUnion = (
    NcbiEfetchSearchInput
    | NcbiEfetchFetchInput
    | NcbiEfetchSummaryInput
    | NcbiEfetchLinkInput
    | NcbiEfetchCoordinateOverlapInput
    | NcbiEfetchDatasetReportInput
    | NcbiEfetchPubchemPropertyInput
)

NcbiEfetchAction = Annotated[_NcbiEfetchActionUnion, Field(discriminator="action")]


class NcbiEfetchInput(RootModel[NcbiEfetchAction]):
    """The 7-way discriminated union entry point. See design decision 1 in
    the module docstring for why this is a `RootModel` rather than a plain
    type alias, and for the `.root` access pattern callers must use.

    `NcbiEfetchInput.model_validate(payload)` is the exact contract the
    premise gate pins (`_call_input` in
    test_ncbi_efetch_premise.py): a plain dict shaped like one of the seven
    Section 6.2 branches in, a validated, action-routed model out. An
    unrecognized `action` value, or a payload matching no branch's required
    fields, raises `pydantic.ValidationError`, the same failure mode as
    every other model in this file.
    """


# ---------------------------------------------------------------------------
# Output: one shape for every action (Section 6.2, "one shape for every
# action; per-action content is documented in the endpoint table below").
# ---------------------------------------------------------------------------


class NcbiEfetchRecord(BaseModel):
    """One returned record, from any of the three API families.

    All four fields are schema-optional: Section 6.2's printed output JSON
    schema declares no `required` list inside the `records` item schema
    (only the outer object has one), so none is added here. In particular a
    `link` record may carry `db` and no `fields`, and a record whose CURIE
    cannot be resolved to a record-page URL is emitted with `source_url`
    absent rather than a fabricated one, the same discipline
    `cypher_schemas.CypherQueryRow.source_url` already documents.
    """

    model_config = ConfigDict(extra="forbid")

    id: Annotated[str | None, Field(default=None, max_length=30)] = None
    db: Annotated[str | None, Field(default=None, max_length=20)] = None
    fields: dict[str, Any] = Field(default_factory=dict)
    source_url: Annotated[
        str | None,
        Field(default=None, max_length=300, pattern=NCBI_EFETCH_RECORD_URL_PATTERN),
    ] = None

    @field_validator("fields")
    @classmethod
    def _cap_fields_count(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Enforce Section 6.2's `maxProperties: 40` on the `fields` object.

        Pydantic v2's built-in length constraints cover str, bytes, and
        sequence types; a mapping's property count is enforced here
        explicitly instead of relying on undocumented dict support, so the
        rejection reason is unambiguous. Same approach as
        `cypher_schemas.CypherQueryRow._cap_fields_count`.
        """
        if len(value) > _MAX_RECORD_FIELDS:
            raise ValueError(
                f"fields carries {len(value)} properties, exceeding the "
                f"maxProperties bound of {_MAX_RECORD_FIELDS}"
            )
        return value


class NcbiEfetchOutput(BaseModel):
    """The tool's return value, identical in shape across all 7 actions.

    `status` uses the same three-value pattern constraint style as
    `cypher_schemas.CypherQueryOutput.status` rather than an `Enum`, for the
    same reason: it is a bare string in the wire format and a regex pattern
    is the direct implementation of the spec's `enum`. The premise gate's
    entire reason for existing is that E-utilities, Datasets v2, and PubChem
    disagree on how `ok`/`empty`/`error` map to HTTP status and response
    body, so this model only pins the OUTPUT shape; the classification logic
    itself belongs to `ncbi_efetch.py`, not this schema.
    """

    model_config = ConfigDict(extra="forbid")

    status: Annotated[str, Field(pattern=r"^(ok|empty|error)$")]
    action: Annotated[str, Field(max_length=20)]
    records: Annotated[
        list[NcbiEfetchRecord],
        Field(default_factory=list, max_length=100),
    ] = Field(default_factory=list)
    record_count: int
    total_available: int | None = None
    truncated: bool
    error: Annotated[str | None, Field(default=None, max_length=500)] = None
