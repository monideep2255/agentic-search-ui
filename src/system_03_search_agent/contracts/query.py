"""The Query and RequestContext models: the single request shape every
surface (web_ui, rest_sse, mcp, cli, graphql) builds before calling
`run()`.

Section 2.1, Technical_specification.md.
"""

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Placeholder bound until SessionMemorySummary (Section 14, phase 4.5) lands
# with its own per-field caps. session_memory is typed Any | None because the
# real typed model doesn't exist yet, but a placeholder type is not license
# for an unbounded payload: production-standards.md's "bounded context
# items" rule requires a hard cap on every context fragment injected into a
# model prompt before the real per-field caps replace this one.
SESSION_MEMORY_MAX_SERIALIZED_LENGTH = 5000


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
    # SessionMemorySummary (Section 14) is not built until phase 4.5.
    session_memory: Any | None = None
    operator_mode: bool = False

    @field_validator("session_memory")
    @classmethod
    def _bound_session_memory_size(cls, value: Any | None) -> Any | None:
        if value is None:
            return value
        serialized_length = len(json.dumps(value))
        if serialized_length > SESSION_MEMORY_MAX_SERIALIZED_LENGTH:
            raise ValueError(
                "session_memory serialized length "
                f"{serialized_length} exceeds the placeholder cap of "
                f"{SESSION_MEMORY_MAX_SERIALIZED_LENGTH} characters"
            )
        return value
