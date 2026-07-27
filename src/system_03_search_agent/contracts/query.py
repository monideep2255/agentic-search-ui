"""The Query and RequestContext models: the single request shape every
surface (web_ui, rest_sse, mcp, cli) builds before calling `run()`.

Section 2.1, Technical_specification.md.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., max_length=2000)
    session_id: str = Field(..., max_length=64)
    trace_id: str = Field(..., max_length=64)
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
