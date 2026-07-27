"""The event envelope and the eleven-member event payload taxonomy.

Sections 2.2 (envelope) and 2.3 (payload shapes), Technical_specification.md.

`Event.payload` is typed as a plain JSON object (`dict[str, Any]`), matching
the envelope schema in Section 2.2 literally (`"payload": {"type": "object"}`).
The per-type payload models below (GuardPayload, ThinkPayload, ...) are the
typed, field-constrained shapes from Section 2.3 and are validated on their
own; wiring them into a discriminated union keyed off the sibling `type`
field is left to a later ticket that builds the Guardrail-to-Write pipeline
these events flow through.

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

from pydantic import BaseModel, ConfigDict, Field

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
    model_config = ConfigDict(extra="forbid")

    outcome: TrustOutcome
    risk_tier: str = Field(..., max_length=16)
    grounded: bool
    triangulated: bool | None = None


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
