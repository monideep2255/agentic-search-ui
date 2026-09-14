"""UI fix set 9: every hardcoded audience-depth list accepts `plain_language`.

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


def test_mcp_tool_signature_keeps_the_section_13_2_values() -> None:
    """NOT widened, deliberately. The MCP tool's input schema is pinned to the
    locked technical specification's Section 13.2
    (`adapters/mcp/test_phase_4_1_premise.py::test_input_schema_matches_section_13_2`),
    so adding `plain_language` there is a locked-spec decision for the main
    agent and the product owner, not an additive edit this set may make."""
    from system_03_search_agent.adapters.mcp import server

    target = inspect.unwrap(server.ask_biomedical_question)
    hints = typing.get_type_hints(target, include_extras=True)
    assert set(typing.get_args(hints["audience_depth"])) == set(ALL_DEPTHS) - {"plain_language"}
