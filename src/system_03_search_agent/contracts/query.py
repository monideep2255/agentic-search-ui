"""The Query and RequestContext models: the single request shape every
surface (web_ui, rest_sse, mcp, cli) builds before calling `run()`.

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

    text: str = Field(..., max_length=2000)
    session_id: str = Field(..., max_length=64)
    trace_id: str = Field(..., max_length=64)
    # T-2.0-08 (closes F-1.1-17): on the authenticated rest_sse surface
    # (adapters/web_sse/app.py's POST /query), any client-submitted value
    # here is advisory only. The endpoint always overwrites it with the
    # server-derived subject of the caller's verified access token before
    # this Query is passed to run(), so it is never trusted from the
    # request body. The field stays optional so a client may omit it.
    user_id: str | None = Field(None, max_length=64)
    audience_depth: Literal["clinical_brief", "researcher", "deep_technical"] = (
        "researcher"
    )


class RequestContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    surface: Literal["web_ui", "rest_sse", "mcp", "cli"]
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
