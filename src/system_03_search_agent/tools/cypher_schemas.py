"""Pydantic v2 input and output schemas for the cypher_query tool.

Technical_specification.md Section 6.1 locks the JSON schema for both the
tool input and the tool output. These models are the typed, validated
implementation of that lock: every field, length cap, and enum here mirrors
the spec's `cypher_query.input` and `cypher_query.output` JSON schemas
exactly, plus `extra="forbid"` on every model so an unexpected field is
rejected rather than silently dropped or passed through
(production-standards.md's multi-agent pipeline gate).

Depends on:
    - system_03_search_agent.tools.graph_schema_constants
      (NCBI_RECORD_URL_PATTERN), the single source of truth for the
      host-pinned citation pattern. Never duplicated here.

Reads:
    - Nothing at import time.

Writes:
    - Nothing.

Depended by:
    - system_03_search_agent.tools.cypher_generation (T-2.1-03)
    - system_03_search_agent.tools.cypher_query (T-2.1-07, integration)
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from system_03_search_agent.tools.graph_schema_constants import NCBI_RECORD_URL_PATTERN

# Section 6.1 input schema's maxProperties bound on a row's `fields` object.
_MAX_ROW_FIELDS = 30


class QueryClass(str, Enum):
    """The five query shapes Section 6.1 and the Think step's `query_class`
    enum both name. A string subclass so a plain string such as "lookup"
    coerces cleanly through Pydantic, and so the enum serializes to the bare
    string value rather than a repr in any JSON output.
    """

    LOOKUP = "lookup"
    SINGLE_HOP = "single_hop"
    MULTI_HOP = "multi_hop"
    AGGREGATE = "aggregate"
    EXPLORATORY = "exploratory"


class CypherQueryInput(BaseModel):
    """The Plan step's structured intent, handed to `cypher_query`.

    `additionalProperties: false` in the spec becomes `extra="forbid"`
    here: a caller passing an undeclared field is a schema violation, not a
    field silently dropped.
    """

    model_config = ConfigDict(extra="forbid")

    query_intent: Annotated[str, Field(max_length=1000)]
    query_class: QueryClass
    target_entities: Annotated[
        list[Annotated[str, Field(max_length=100)]],
        Field(default_factory=list, max_length=10),
    ] = Field(default_factory=list)
    row_limit: Annotated[int, Field(ge=1, le=500)] = 100


class CypherQueryRow(BaseModel):
    """One returned row: a node or an edge, always carrying its own
    provenance. `source_url`, when present, is validated against the same
    host-pinned pattern as the spec's output schema
    (production-standards.md: a citation URL that only checks for
    `https://` can be spoofed to point anywhere).

    `source_url` is optional at the schema level because T-2.1-05's
    `to_output_row` may legitimately be unable to produce one for a row
    (an unrecognized CURIE prefix, or a stored URL on a foreign host that
    gets discarded rather than passed through); such a row is emitted with
    `source_url` absent, never with a fabricated link.
    """

    model_config = ConfigDict(extra="forbid")

    node_or_edge_type: Annotated[str, Field(max_length=50)]
    curie: Annotated[str, Field(max_length=100)]
    fields: dict[str, Any] = Field(default_factory=dict)
    source_url: Annotated[
        str | None,
        Field(default=None, max_length=300, pattern=NCBI_RECORD_URL_PATTERN),
    ] = None
    graph_snapshot_version: Annotated[str, Field(max_length=40)]

    @field_validator("fields")
    @classmethod
    def _cap_fields_count(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Enforce the spec's `maxProperties: 30` on the `fields` object.

        Pydantic v2's built-in length constraints cover str, bytes, and
        sequence types; a mapping's property count is enforced here
        explicitly instead of relying on undocumented dict support, so the
        rejection reason is unambiguous.
        """
        if len(value) > _MAX_ROW_FIELDS:
            raise ValueError(
                f"fields carries {len(value)} properties, exceeding the "
                f"maxProperties bound of {_MAX_ROW_FIELDS}"
            )
        return value


class CypherQueryOutput(BaseModel):
    """The tool's return value. `cypher_executed` is an audit trail field
    only: production-standards.md and T-2.1-07 both require that the main
    agent never receives raw Cypher in a payload rendered to a user, so no
    caller of this model may treat `cypher_executed` as user-facing content.
    """

    model_config = ConfigDict(extra="forbid")

    status: Annotated[str, Field(pattern=r"^(ok|empty|error)$")]
    rows: Annotated[list[CypherQueryRow], Field(default_factory=list, max_length=500)] = Field(
        default_factory=list
    )
    row_count: int
    total_available: int | None = None
    truncated: bool
    cypher_executed: Annotated[str | None, Field(default=None, max_length=2000)] = None
    error: Annotated[str | None, Field(default=None, max_length=500)] = None
