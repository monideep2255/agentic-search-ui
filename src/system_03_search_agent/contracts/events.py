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
from typing import Annotated, Any, Literal

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

# Host-pinned pattern for citation.source_url, per Section 9.3's per-tool
# host table. Build phase 3.4: widened from an NCBI-only pattern (this
# constant's name is kept, only local to this file, for minimal blast
# radius) to also accept clinicaltrials.gov/study/, since `clinicaltrials_
# search` citations are a genuinely different host, never
# ncbi.nlm.nih.gov (`tools/clinicaltrials_search_schemas.CLINICALTRIALS_
# HOST`, copied verbatim here rather than imported, since `contracts/`
# does not depend on `tools/`). Every other Layer 2/3 tool this phase
# wires (ncbi_efetch, ncbi_dbsnp, pubtator_annotate, litvar2_lookup,
# pathogen_detection) cites an ncbi.nlm.nih.gov-family host, so the first
# alternative alone still covers them.
#
# Build phase 4.2 (F-4.2-A-01, closing the open flag F-3.4-A-06 that was
# tracked as "confirmed still not exploitable through any current call
# site"): this pattern used to be anchored at the START only. Pydantic's
# `pattern=` constraint compiles the string and calls `re.match`, which
# requires a match at position 0 but never requires consuming the whole
# value unless the pattern itself ends in `$`. With no end anchor,
# everything after the host prefix was free text, including a literal
# newline, so a single `source_url` field could carry a whole forged
# reference row pointing at any host. That was recorded as not
# exploitable while every surface rendered the value to a browser; build
# phase 4.2 adds the first surface (a terminal, over
# `adapters/cli/render.py`) that treats a string as something closer to
# executable content than display markup, so the gap is live now.
#
# The flag's own recorded fix is a CHARACTER-CLASS RESTRICTION on the
# remainder, not a bare `$` appended right after the host prefix: a bare
# `$` there would reject every real citation URL, since all of them carry
# a path or an id after the host (`https://www.ncbi.nlm.nih.gov/gene/672`,
# `https://clinicaltrials.gov/study/NCT00000000`, a PubTator autocomplete
# URL carrying `?query=...`, a `synthesis.refuse.build_fallback_link`
# result carrying a `urllib.parse.quote(..., safe="")`-encoded search
# term). `_URL_REMAINDER_CHARS` is that restriction: RFC 3986's unreserved
# set plus the gen-delims and sub-delims plus `%` (percent-encoding),
# which is every character a real, already-encoded HTTPS URL's path,
# query, or fragment can contain, and pointedly excludes whitespace and
# every C0/C1 control character, including `\n`. A value that needs a raw
# space or a raw newline in its remainder was never a valid encoded URL
# to begin with.
_URL_REMAINDER_CHARS = r"[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]"

NCBI_SOURCE_URL_PATTERN = (
    r"^https://(?:([A-Za-z0-9-]+\.)*ncbi\.nlm\.nih\.gov/"
    r"|(?:www\.)?clinicaltrials\.gov/study/)"
    + _URL_REMAINDER_CHARS
    + r"*$"
)


class GuardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    category: Literal[
        "ok",
        "off_topic",
        "medical_advice",
        "injection",
        "rate_limited",
        "cost_capped",
        "write_seeking",
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
    # UI fix set 8, item 8.2 (2026-09-13). The helper scientist this call is
    # handed to on the progress screen: one name per data layer, drawn per
    # run from the curated list excluding the session's lead, so the screen
    # can read "Franklin is searching the knowledge graph". ADDITIVE and
    # OPTIONAL, default None, so every consumer and every fixture built
    # before this field validates unchanged (Section 2.6). PRESENTATION
    # ONLY: `harness.coordinator_worker` copies only `call_id`, `tool` and
    # `layer` onto a `Finding`, so the name can never reach a synthesis
    # prompt or a grounding pass, and a test pins that.
    persona: str | None = Field(None, max_length=64)
    persona_about: str | None = Field(None, max_length=160)
    persona_wikipedia: str | None = Field(None, max_length=256)


class PlanPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narrative: str = Field(..., max_length=500)
    tool_calls: list[ToolCall] = Field(default_factory=list, max_length=20)
    # T-4.5-06: the entities this step actually resolved, mirroring
    # `ThinkPayload.resolved_entities` above. Additive within v1, which
    # system-design-patterns pattern 10 permits: a new field with a default,
    # never a redefinition, so every existing consumer is unaffected.
    #
    # It is on PLAN rather than THINK because Plan is where resolution
    # happens today: `think_node` is still the build-phase-2.0 stub and emits
    # an empty list, while `plan_node` runs the live symbol lookup. Build
    # phase 4.7 owns moving that to Think (F-2.0-15), at which point this
    # field becomes the redundant one rather than the useful one.
    #
    # Session memory reads THIS to learn what a turn resolved. Without it the
    # only record of a resolved CURIE was prose in the narrative, and parsing
    # a sentence to recover a value the code already had is how a fragile
    # dependency gets built.
    resolved_entities: list[ResolvedEntity] = Field(default_factory=list, max_length=20)


class ToolStartPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call_id: str = Field(..., max_length=64)
    tool: ToolName
    layer: Layer
    # T-4.16-01: `"running"` added. Additive within v1, which
    # system-design-patterns pattern 10 permits by name ("a new optional
    # field, a new enum value").
    #
    # WHY IT HAD TO BE ADDED RATHER THAN WORKED AROUND. This union was
    # `Literal["ok", "empty", "error"]`, inherited unchanged by
    # `ToolResultPayload` below, and build phase 4.16 is the first phase to
    # actually EMIT a `tool_start`. A start event is written the instant
    # before a tool is dispatched, so its outcome is not merely unknown, it
    # does not exist yet. Every available value would therefore have been a
    # claim about a call that had not run: emitting `"ok"` there asserts
    # success before the fact, which is the same assert-what-you-have-not-
    # checked shape build phase 4.3 shipped as a critical twice and build
    # phase 4.7 hit again in its own gate. The type was wrong, not the
    # caller.
    #
    # It is also what the UI already assumed. `useRunView.ts` line 231 reads
    # `event.type === "tool_result" ? ... : "running"`, hardcoding this exact
    # word for the chip's detail text since build phase 4.8, against an event
    # nothing had ever emitted.
    status: Literal["running", "ok", "empty", "error"]
    # UI fix set 8, item 8.2 (2026-09-13). The same helper the planned
    # `ToolCall` carries, repeated on the start frame (and therefore on the
    # result frame, which inherits it) so a surface that builds its tool
    # chips from these two frames alone can name the scientist without
    # joining back to the plan event. Optional, default None, additive.
    persona: str | None = Field(None, max_length=64)
    persona_about: str | None = Field(None, max_length=160)
    persona_wikipedia: str | None = Field(None, max_length=256)


class ToolResultPayload(ToolStartPayload):
    # Deliberately RE-NARROWED, not inherited. A result knows its outcome, so
    # `"running"` is not a legal value here and this field must keep refusing
    # it. Widening the parent and letting the child inherit the wider union
    # would have made "the tool finished, and it is still running" a
    # representable state, which is the kind of unrepresentable-made-
    # representable that a schema exists to prevent.
    #
    # The accepted set on THIS model is byte-for-byte what it was before
    # T-4.16-01, so no existing producer or consumer of a `tool_result`
    # changes behaviour. Only `tool_start` widened.
    status: Literal["ok", "empty", "error"]

    summary: str = Field(..., max_length=1000)
    result_count: int = Field(..., ge=0)
    truncated: bool


class TokenPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., max_length=1000)
    marker_ids: list[str] = Field(default_factory=list, max_length=20)
    # UI fix set 9, items 9.4 to 9.10 (2026-09-13). Additive and optional per
    # Section 2.6, so every token built before this validates unchanged and
    # a surface that joins `text` still reads the answer as prose.
    #
    # `kind` says what the chunk IS, so a surface never has to guess from
    # its wording: a grounded `claim`, a system `note` (never a claim), a
    # `heading` or `paragraph_break` (structure, never counted as a claim),
    # or a code-built `list_item`, `table_header` or `table_row`, each of
    # which carries a grounded sentence and its marker in `text` and the
    # display values in `cells`. None means an older producer: classify as
    # before. `emphasis` names substrings of `text` to bold, chosen in code
    # from the run's own resolved entities and record values.
    kind: (
        Literal[
            "claim",
            "note",
            "heading",
            "paragraph_break",
            "list_item",
            "table_header",
            "table_row",
        ]
        | None
    ) = None
    cells: list[Annotated[str, Field(max_length=500)]] | None = Field(None, max_length=2)
    emphasis: list[Annotated[str, Field(max_length=200)]] | None = Field(
        None, max_length=12
    )


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
    # T-4.10-07 (F-4.8-D-02, F-4.8-D-03): two additive, optional fields for
    # the source card's header and its SNAPSHOT row. Both default to None
    # so every payload built before this phase still validates unchanged
    # (Section 2.6: a new optional field is an allowed in-version change).
    #
    # `snapshot_date`: a real calendar date extracted from the Layer 1
    # row's own `graph_snapshot_version` (`synthesis.freshness.
    # graph_snapshot_date_from_version`, already live-confirmed and wired
    # for T-3.4-06's staleness check). It is NOT a genuine per-row
    # ingestion timestamp: F-3.4-T06-01 confirmed no such field exists
    # anywhere this repo's ingest can read (checked live against
    # `ag_catalog`; no ingest-metadata table is queryable). It is the
    # closest real, non-fabricated proxy this graph has for "when was this
    # graph data current", which is what Section 7's freshness argument
    # needs to be visible to a reader. Left `None`, never a guess, for
    # Layer 2/3 citations (no graph snapshot exists for a live API call)
    # and for a Layer 1 row whose `graph_snapshot_version` carries no
    # parseable date.
    #
    # `entity_name`: the citation's own record's plain-language name (e.g.
    # a gene symbol, a disease name), read directly off the row's stored
    # `name` property when one is present and not a known ETL vocabulary-
    # token artifact (`core.graph._is_vocabulary_token_artifact`, F-2.1-
    # B07). Left `None`, never a guess, when the row carries no `name`
    # property or the value is flagged as a corrupted vocabulary-token
    # artifact.
    snapshot_date: str | None = Field(None, max_length=32)
    entity_name: str | None = Field(None, max_length=256)


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
    # "cancelled" added at build phase 4.0 (F-4.0-A-04, adversary round 1):
    # additive per system-design-patterns rule 10 (a new enum value within
    # v1 is a non-breaking change). Distinguishes a caller-stopped or
    # abandonment-cancelled run from the three failure-shaped classes; a
    # cancellation is not a transient, recoverable, or unexpected error,
    # it is the run doing exactly what it was told to do.
    error_class: Literal["transient", "recoverable", "unexpected", "cancelled"] = Field(
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

    # UI fix set 9, item 9.9 (2026-09-13). The one plain trust line for the
    # answer ("Based on 1 source, not yet confirmed"), built in code by
    # `synthesis.trust.answer_trust_line` from the verdicts `trust_outcome`
    # already summarises. Additive and optional; None on a refusal. Carried
    # HERE rather than on `TrustSignalPayload` because the MCP surface
    # projects that model whole under a pinned key allowlist, and a trust
    # line is a statement about the finished answer, which is this event.
    trust_line: Annotated[str | None, Field(default=None, max_length=200)] = None

    next_step: Annotated[str | None, Field(default=None, max_length=200)] = None
    """An offer of somewhere to go next, or None when there is nowhere honest.

    Build phase 6.2, T-6.2-08, on the product-owner decision of 2026-09-01.
    ADDITIVE and OPTIONAL, which is what keeps it inside v1: `system-design-
    patterns` pattern 10 allows a new optional field within a major version
    and requires a v2 for anything that removes a field or changes one's
    meaning. Every existing consumer ignores it and behaves exactly as
    before.

    THREE THINGS THIS FIELD IS NOT, each of which it would be easy to turn
    it into:

    It is not model-generated text. `docs/build/UI_feedback.md` names that as the easy
    and dangerous path: an offer to go deeper is a claim that there IS
    something deeper, so a model-invented follow-up about data the graph does
    not hold is a confident wrong answer wearing a question mark, and it
    would defeat cite-or-refuse through a surface nothing checks. The value
    is built in code from the findings retrieval actually returned and the
    answer did not report.

    It is not `ThinkPayload.clarifying_question`, and conflating the two is
    the mistake this docstring exists to prevent. That field belongs to
    Section 22.1's ambiguous-query path, fires BEFORE any tool runs, and
    REPLACES the answer in order to disambiguate an entity. This one fires
    after a complete, cited answer and ADDS to it.

    It is not mandatory. `None` is the correct value for a refusal, an empty
    retrieval, or a single-fact lookup, because none of those has an honest
    next step and a system that always asks something will pad.
    """

    next_step_query: Annotated[str | None, Field(default=None, max_length=2000)] = None
    """The question a surface sends when the reader accepts `next_step`.

    UI fix set 7, item 7.2, 2026-09-13. `next_step` is a yes/no question
    addressed to the reader ("Would you like me to go through the 10
    further sequence variant records found for this question?"), and the
    web UI used to send that sentence verbatim as the next query when the
    reader clicked "Yes, go deeper". Think then classified it as a
    meta-question with no entities, Synth answered a yes/no question, and
    the grounding pass stripped every word of it, so accepting the offer
    refused. The offer text is for the reader; this field is for the
    system.

    ADDITIVE and OPTIONAL like `next_step`, so it stays inside v1 under
    `system-design-patterns` pattern 10. It is `None` exactly when
    `next_step` is `None`, and it is built in code by
    `core.next_step.build_next_step_query` from the omitted findings'
    record type and the turn's resolved entity, never by a model, for the
    same reason `next_step` is not: a generated follow-up is a claim about
    what the graph holds. Its shape is the one `core.next_step.
    is_go_deeper_query` recognises on the next turn, which is how that
    turn knows to put the not-yet-reported records first.

    `max_length=2000` matches `Query.text`, because this string becomes the
    next `Query.text` unchanged.
    """


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
