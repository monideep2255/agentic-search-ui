"""The Query and RequestContext models: the single request shape every
surface (web_ui, rest_sse, mcp, cli, graphql) builds before calling
`run()`.

Section 2.1, Technical_specification.md.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# T-4.5-02, Section 14.3. The per-field caps below REPLACE the placeholder
# serialized-length bound this module used to carry
# (`SESSION_MEMORY_MAX_SERIALIZED_LENGTH = 5000`, with a validator on
# `RequestContext.session_memory`). Both were removed in the same change
# rather than kept alongside each other: two bounds on one field that do not
# agree is worse than either alone, because a reader cannot tell which one is
# load-bearing, and the placeholder's own comment named this phase as the one
# that would retire it.
#
# The caps are not decoration. production-standards.md's multi-agent pipeline
# gate requires `maxLength` on every string and a length cap on every array,
# because they bound the blast radius when one upstream document goes
# hostile, and session memory is the ONE context fragment that persists
# across turns rather than arriving fresh each time.

#: Section 14.3's hard cap, in tokens. Enforced server-side at injection by
#: `core.session_memory.build_session_context`, never a soft target and never
#: a client-supplied number.
SESSION_MEMORY_TOKEN_BUDGET = 1500

#: Section 14.3's per-list ceilings.
MAX_RESOLVED_ENTITIES = 50
MAX_COMPRESSED_FINDINGS = 20
MAX_OPEN_THREADS = 10
MAX_CITATION_IDS_PER_FINDING = 5


class ResolvedEntity(BaseModel):
    """An entity this session has already resolved (Section 14.3).

    Its purpose is orchestration convenience, so Think does not re-resolve a
    mention it already resolved this session, and reference resolution, so a
    later turn's pronoun has something to bind to. It is never a citation:
    Section 14.1's firewall puts personalization in orchestration and
    presentation, never in grounding.
    """

    model_config = ConfigDict(extra="forbid")

    mention: str = Field(..., max_length=200)
    """The free-text phrase the user actually used."""

    curie: str = Field(..., max_length=100)
    """The identifier it resolved to, e.g. "NCBIGene:672"."""

    entity_type: str = Field(..., max_length=50)
    """e.g. "Gene", "Variant", "Disease"."""


class CompressedFinding(BaseModel):
    """A prior turn's finding, compressed, with a reference back to its run.

    The `trace_id` is what makes this safe. Section 14.4 forbids asserting
    `claim_summary` straight into an answer: if the claim is relevant to the
    current turn, Plan must schedule it to be re-verified, either a fresh Act
    step or a reuse of that trace's `tool_result` if it is still in the
    per-run cache. The summary exists to tell Think and Plan what has already
    been established, not to be quoted.
    """

    model_config = ConfigDict(extra="forbid")

    claim_summary: str = Field(..., max_length=280)
    """A compressed restatement. Never re-asserted verbatim into an answer."""

    trace_id: str = Field(..., max_length=64)
    """The run this finding came from (Sections 2.2 and 20)."""

    citation_ids: list[str] = Field(
        default_factory=list, max_length=MAX_CITATION_IDS_PER_FINDING
    )
    """The markers that supported the claim in its original run."""


class SessionMemorySummary(BaseModel):
    """Bounded in-conversation memory (Section 14.3), and nothing more.

    Decision F scopes v1 to in-conversation memory only. Persistent
    cross-session per-user memory is named out of scope by
    `.claude/rules/v1-scope-boundary.md` with its own trigger, so this model
    deliberately has no `user_id` and no durable-history field: the shape
    itself refuses to become the thing that is out of scope.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., max_length=64)
    resolved_entities: list[ResolvedEntity] = Field(
        default_factory=list, max_length=MAX_RESOLVED_ENTITIES
    )
    compressed_findings: list[CompressedFinding] = Field(
        default_factory=list, max_length=MAX_COMPRESSED_FINDINGS
    )
    open_threads: list[str] = Field(default_factory=list, max_length=MAX_OPEN_THREADS)

    token_budget: int = Field(default=SESSION_MEMORY_TOKEN_BUDGET, ge=1, le=8000)
    """The hard cap, enforced at injection. Bounded on both sides on purpose:
    a caller-supplied budget of zero would silently disable memory, and an
    unbounded one would defeat the cap this field exists to impose."""

    last_updated: datetime

    @field_validator("open_threads")
    @classmethod
    def _bound_each_open_thread(cls, value: list[str]) -> list[str]:
        """Section 14.3 caps each thread at 200 characters, not just the list.

        A `max_length` on the list bounds how MANY threads arrive; it says
        nothing about how long one may be. Without this, ten threads of a
        megabyte each satisfy every declared cap on this model, which is
        exactly the bounded-context hole production-standards names.
        """
        for thread in value:
            if len(thread) > 200:
                raise ValueError(
                    f"each open_thread is capped at 200 characters, got {len(thread)}"
                )
        return value


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # T-3.0-05, Section 10.3. `min_length=1` was specified from the start and
    # was missing until build phase 3.0, so an empty-string query was
    # contract-valid and reached the guardrail. The paired validator below
    # closes the whitespace-only case, which `min_length` alone admits: a
    # query of three spaces has length three and asks nothing.
    text: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(..., max_length=64)
    trace_id: str = Field(..., max_length=64)
    # T-2.0-08 (closes F-1.1-17): on the authenticated rest_sse surface
    # (adapters/web_sse/app.py's POST /v1/query), any client-submitted value
    # here is advisory only. The endpoint always overwrites it with the
    # server-derived subject of the caller's verified access token before
    # this Query is passed to run(), so it is never trusted from the
    # request body. The field stays optional so a client may omit it.
    user_id: str | None = Field(None, max_length=64)
    audience_depth: Literal["clinical_brief", "researcher", "deep_technical"] = (
        "researcher"
    )

    @field_validator("text")
    @classmethod
    def _reject_whitespace_only_text(cls, value: str) -> str:
        """T-3.0-05, Section 10.3: a query must actually ask something.

        Rejects rather than strips. Stripping would silently rewrite the
        user's input before the guardrail classifies it, and every check in
        `guardrail/` would then be reasoning about text the user did not
        send. A boundary validator's job is to accept or refuse, not to
        edit.

        Covers Unicode whitespace, not just ASCII spaces, since `str.strip()`
        is Unicode-aware. That matters here: build phase 2.2's finding
        F-2.2-R-02 was an ASCII-only tokenizer that made every non-Latin
        script invisible to two separate gates, and an ASCII-only emptiness
        check would repeat the same mistake in the opposite direction.
        """
        if not value.strip():
            raise ValueError("text must contain at least one non-whitespace character")
        return value


class RequestContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # T-4.3-05, build phase 4.3: "graphql" added. Additive-only within v1
    # (system-design-patterns.md pattern 10) since this is a new enum
    # member, not a redefinition of an existing one. Every hand-maintained
    # consumer copy of this closed set was searched for (backend: grepped
    # the whole repo for the literal strings "web_ui"/"rest_sse"/"mcp"/
    # "cli" together; only this declaration and the two surfaces' own
    # `RequestContext(surface=...)` call sites reference the set at all.
    # Frontend: grepped frontend/src for the same four strings and for
    # "surface"; the only "surface" field on that side is an unrelated
    # feature-stub registry key (frontend/src/stubs/registry.ts), not a
    # copy of this Literal) so there is no second closed enum to widen,
    # unlike build phase 3.0's F-3.0-01 precedent this ticket was briefed
    # against.
    surface: Literal["web_ui", "rest_sse", "mcp", "cli", "graphql"]
    # T-4.5-02: the real typed model, replacing the `Any | None` placeholder
    # and its serialized-length validator. Every bound this field needs now
    # lives on SessionMemorySummary itself, per field, which is both stricter
    # than the old 5000-character total and legible to a reader asking what
    # any one part of it may contain.
    session_memory: SessionMemorySummary | None = None
    operator_mode: bool = False
