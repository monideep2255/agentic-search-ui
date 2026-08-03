"""The event envelope and the eleven-member event payload taxonomy.

Sections 2.2 (envelope) and 2.3 (payload shapes), Technical_specification.md.

`Event.payload` is typed as a plain JSON object (`dict[str, Any]`), matching
the envelope schema in Section 2.2 literally (`"payload": {"type": "object"}`).
The field's stored type stays a plain object for that reason. The per-type
payload models below (GuardPayload, ThinkPayload, ...) are the typed,
field-constrained shapes from Section 2.3, and `Event` enforces at
construction time that `payload` actually conforms to the model matching the
sibling `type` field (see `PAYLOAD_MODEL_BY_TYPE` and the model validator on
`Event`). This is an enforcement layer on top of the stored `dict[str, Any]`
field, not a change to the field's wire-level type.

Every string field declares `max_length`. Where Section 2.3 gives an
explicit number, that number is used. Where a field has no explicit number
in the spec text (e.g. `guard.reason`, `citation.claim_text`), a
conservative cap is applied per the multi-agent schema gate in
`production-standards.md`, which requires `max_length` on every string
field and `max_items` on every array regardless of whether the spec text
enumerates a number.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

ToolName = Literal[
    "cypher_query",
    "ncbi_efetch",
    "ncbi_dbsnp",
    "pubtator_annotate",
    "litvar2_lookup",
    "pathogen_detection",
    "clinicaltrials_search",
]

Layer = Literal["layer_1_graph", "layer_2_api", "layer_3_enrichment"]

# Reused between trust_signal.outcome and done.trust_outcome: Section 2.3
# gives one enum comment ("outcome enum: ...") and done.trust_outcome takes
# its value from the same trust vocabulary.
TrustOutcome = Literal["answer", "flag", "ask", "refuse"]

# Host-pinned placeholder for citation.source_url. The real Section 9.3
# regex is refined in a later phase; this only enforces an ncbi.nlm.nih.gov
# subdomain under https.
NCBI_SOURCE_URL_PATTERN = r"^https://([A-Za-z0-9-]+\.)*ncbi\.nlm\.nih\.gov/"


class GuardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    category: Literal[
        "ok", "off_topic", "medical_advice", "injection", "rate_limited", "cost_capped"
    ]
    reason: str | None = Field(None, max_length=256)


class ResolvedEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., max_length=200)
    curie: str = Field(..., max_length=128)
    confidence: float = Field(..., ge=0.0, le=1.0)


class ThinkPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narrative: str = Field(..., max_length=500)
    query_class: Literal[
        "lookup", "single_hop", "multi_hop", "aggregate", "exploratory"
    ]
    resolved_entities: list[ResolvedEntity] = Field(default_factory=list, max_length=20)
    clarifying_question: str | None = Field(None, max_length=500)


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: ToolName
    call_id: str = Field(..., max_length=64)
    layer: Layer


class PlanPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narrative: str = Field(..., max_length=500)
    tool_calls: list[ToolCall] = Field(default_factory=list, max_length=20)


class ToolStartPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call_id: str = Field(..., max_length=64)
    tool: ToolName
    layer: Layer
    status: Literal["ok", "empty", "error"]


class ToolResultPayload(ToolStartPayload):
    summary: str = Field(..., max_length=1000)
    result_count: int = Field(..., ge=0)
    truncated: bool


class TokenPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., max_length=1000)
    marker_ids: list[str] = Field(default_factory=list, max_length=20)


class CitationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    citation_id: str = Field(..., max_length=64)
    display_index: int = Field(..., ge=1)
    source: str = Field(..., max_length=128)
    source_id: str = Field(..., max_length=128)
    source_url: str = Field(
        ..., max_length=500, pattern=NCBI_SOURCE_URL_PATTERN
    )
    layer: Layer
    field: str = Field(..., max_length=128)
    claim_text: str = Field(..., max_length=1000)
    evidence_kind: str = Field(..., max_length=64)
    assertion_confidence: str = Field(..., max_length=64)
    population_ancestry_context: str | None = Field(None, max_length=256)
    license: str = Field(..., max_length=128)


class TrustSignalPayload(BaseModel):
    """Section 8.3's per-claim verdict, and Section 8.4's refuse payload.

    The four fields below `outcome` are additive within v1 (Section 2.6:
    "a new optional field" is an allowed in-version change; removing a
    field or changing one's meaning would need a v2). Each is optional and
    defaults to None, so every payload built before build phase 2.2
    validates unchanged.

    `citation_id` is the join key Section 9.1 specifies: a trust signal is
    never a field ON a citation, it is its own event bound to one by shared
    id, so a surface can render a per-chip verdict (8.3.4) without the
    citation having to be re-emitted to carry it. It is None on the
    answer-level signal, which belongs to the whole response rather than to
    any one claim.

    `message` and `fallback_link` carry Section 8.4's refuse payload, whose
    example in the spec shows exactly these two keys alongside `outcome`.
    `fallback_link` is host-pinned by the same pattern every `source_url`
    uses: a refusal that links somewhere other than NCBI is a worse failure
    than a refusal with no link at all.

    `triangulated` is a tri-state on purpose. None means triangulation was
    not evaluated (Section 8.3.3's "not evaluated" cell, i.e. every
    low-risk claim), which is a different statement from False, meaning it
    ran and did not concord.
    """

    model_config = ConfigDict(extra="forbid")

    outcome: TrustOutcome
    risk_tier: str = Field(..., max_length=16)
    grounded: bool
    triangulated: bool | None = None
    citation_id: str | None = Field(None, max_length=64)
    scope: Literal["claim", "answer"] | None = None
    message: str | None = Field(None, max_length=500)
    fallback_link: str | None = Field(
        None, max_length=512, pattern=NCBI_SOURCE_URL_PATTERN
    )


class CostPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_cost_usd: float = Field(..., ge=0.0)
    query_cap_usd: float = Field(..., ge=0.0)
    cap_fraction: float = Field(..., ge=0.0)
    model_tier: Literal["guard", "plan", "synth"] = Field(..., max_length=16)


class ErrorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fatal: bool
    scope: Literal["tool", "step", "run"] = Field(..., max_length=16)
    source: str = Field(..., max_length=64)
    error_class: Literal["transient", "recoverable", "unexpected"] = Field(
        ..., max_length=16
    )
    message: str = Field(..., max_length=256)
    retry_after_s: int = Field(..., ge=0)


class DonePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_cost_usd: float = Field(..., ge=0.0)
    total_tool_calls: int = Field(..., ge=0)
    elapsed_ms: int = Field(..., ge=0)
    trust_outcome: TrustOutcome


# Binds each envelope `type` value to the Section 2.3 payload model that
# `payload` must conform to. Keyed by the same eleven-member taxonomy as
# `Event.type` below; keep the two in sync if the taxonomy ever grows.
PAYLOAD_MODEL_BY_TYPE: dict[str, type[BaseModel]] = {
    "guard": GuardPayload,
    "think": ThinkPayload,
    "plan": PlanPayload,
    "tool_start": ToolStartPayload,
    "tool_result": ToolResultPayload,
    "token": TokenPayload,
    "citation": CitationPayload,
    "trust_signal": TrustSignalPayload,
    "cost": CostPayload,
    "error": ErrorPayload,
    "done": DonePayload,
}


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal[
        "guard",
        "think",
        "plan",
        "tool_start",
        "tool_result",
        "token",
        "citation",
        "trust_signal",
        "cost",
        "error",
        "done",
    ]
    version: Literal["v1"]
    trace_id: str = Field(..., max_length=64)
    seq: int = Field(..., ge=0)
    ts: datetime
    payload: dict[str, Any]

    @model_validator(mode="after")
    def _payload_matches_declared_type(self) -> "Event":
        """Bind `payload` to the Section 2.3 model matching `type`.

        `payload` stays typed as `dict[str, Any]` on the field itself (the
        wire-level schema in Section 2.2 specifies a generic object), but an
        arbitrary or mismatched-shape dict must never pass construction: it
        would defeat every `max_length`/`max_items` cap the multi-agent
        schema gate (`production-standards.md`) requires.
        """
        payload_model = PAYLOAD_MODEL_BY_TYPE[self.type]
        try:
            payload_model.model_validate(self.payload)
        except ValidationError as exc:
            raise ValueError(
                f"payload does not match the {self.type!r} event schema "
                f"(expected shape of {payload_model.__name__}): {exc}"
            ) from exc
        return self
