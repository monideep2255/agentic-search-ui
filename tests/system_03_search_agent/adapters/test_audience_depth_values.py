"""UI fix set 9: every hardcoded audience-depth list accepts `plain_language`.

The MCP tool joined the others in build phase 8.10 (T-8.10-05), on the product
owner's parity decision of 2026-09-26; see its arm below.

Database-free, so it runs everywhere. `test_streaming_endpoints.py` proves the
same through a real POST /v1/query when the user database is reachable.

Each arm also asserts an unknown value is rejected, so a list widened to accept
anything would fail here rather than pass.
"""

from __future__ import annotations

import inspect
import typing

import pytest
from pydantic import ValidationError

ALL_DEPTHS = ("plain_language", "researcher", "clinical_brief", "deep_technical")


def test_query_contract_accepts_every_depth() -> None:
    from system_03_search_agent.contracts.query import Query

    base = {"text": "What gene is BRCA1?", "session_id": "s", "trace_id": "t"}
    for depth in ALL_DEPTHS:
        assert Query(**base, audience_depth=depth).audience_depth == depth
    with pytest.raises(ValidationError):
        Query(**base, audience_depth="simple")
    assert Query(**base).audience_depth == "researcher"


def test_web_request_model_accepts_every_depth() -> None:
    from system_03_search_agent.adapters.web_sse.app import CreateRunRequest

    for depth in ALL_DEPTHS:
        body = CreateRunRequest(text="What gene is BRCA1?", session_id="s", audience_depth=depth)
        assert body.audience_depth == depth
    with pytest.raises(ValidationError):
        CreateRunRequest(text="What gene is BRCA1?", session_id="s", audience_depth="simple")


def test_stored_preference_allows_plain_language() -> None:
    from system_03_search_agent.auth import preferences

    assert set(ALL_DEPTHS) == set(preferences._ALLOWED)


def test_graphql_enum_carries_plain_language() -> None:
    from system_03_search_agent.adapters.graphql.types import AudienceDepth, resolve_audience_depth

    assert {member.value for member in AudienceDepth} == set(ALL_DEPTHS)
    assert resolve_audience_depth(AudienceDepth.PLAIN_LANGUAGE) == "plain_language"


def test_mcp_tool_accepts_every_depth_and_keeps_researcher_as_its_default() -> None:
    """WIDENED on the product owner's decision, not by this file's own say.

    `DECISIONS.md`, 2026-09-26: "The MCP server gets full parity with the web
    app: Plain language answers, and tools for history, reopening a past
    answer, feedback and the follow-up offers. The locked specification's
    Section 13.2, one advertised tool at Researcher depth or deeper, is
    overruled for MCP by this row, and the specification itself stays
    locked (card 49)." Build phase 8.10, T-8.10-05.

    Until that row this arm pinned MCP to Section 13.2's three values on
    purpose (UI fix set 9, F9-13), because widening a locked-spec schema was
    the owner's call. The owner made it. The default stays `researcher`, the
    ledger's own decision, so a client that names no depth gets exactly the
    answers it got before.

    Three arms, each able to fail on its own: the annotation the SDK builds
    the tool from accepts every depth and refuses an unknown one; the
    default is `researcher`; and the schema an agent actually reads lists
    all four. Mutation that turns the first red: drop `plain_language` from
    `server.AudienceDepth`. The second: change `_DEFAULT_AUDIENCE_DEPTH`.
    """
    import asyncio

    from pydantic import TypeAdapter

    from system_03_search_agent.adapters.mcp import server

    target = inspect.unwrap(server.ask_biomedical_question)
    hints = typing.get_type_hints(target, include_extras=True)
    depth = TypeAdapter(hints["audience_depth"])
    for value in ALL_DEPTHS:
        assert depth.validate_python(value) == value
    with pytest.raises(ValidationError):
        depth.validate_python("simple")

    assert inspect.signature(target).parameters["audience_depth"].default == "researcher"

    tools = {tool.name: tool for tool in asyncio.run(server.server.list_tools())}
    published = tools["ask_biomedical_question"].input_schema["properties"]["audience_depth"]
    assert set(published["enum"]) == set(ALL_DEPTHS)
    assert published["default"] == "researcher"
