"""Tests for cypher_generation.py (T-2.1-03).

Mocks the harness entirely: no network call, no database call anywhere in
this file. Covers a clean generation, a generation with prior_error set,
a fenced response, a response wrapped in the forbidden SQL wrapper, and a
response with no recoverable Cypher.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from system_03_search_agent.tools.cypher_generation import (
    CypherGenerationError,
    generate_cypher,
)
from system_03_search_agent.tools.cypher_schemas import CypherQueryInput


class _FakeHarness:
    """A minimal stand-in for Harness: records every call_tier invocation
    and returns a fixed response content, so tests assert both the
    returned Cypher and exactly what was sent to the model.
    """

    def __init__(self, content: str) -> None:
        self._content = content
        self.calls: list[tuple[str, list[dict[str, str]]]] = []

    async def call_tier(
        self,
        tier: str,
        messages: list[dict[str, str]],
        *,
        cache_prefix: str | None = None,
    ) -> SimpleNamespace:
        self.calls.append((tier, messages))
        return SimpleNamespace(content=self._content)


def _tool_input(**overrides: object) -> CypherQueryInput:
    base = {
        "query_intent": "genes linked to BRCA1",
        "query_class": "single_hop",
        "target_entities": ["NCBIGene:672"],
    }
    base.update(overrides)
    return CypherQueryInput(**base)


@pytest.mark.asyncio
async def test_generate_cypher_clean_response() -> None:
    harness = _FakeHarness("MATCH (g:Gene {id: $gene_id}) RETURN g")
    result = await generate_cypher(harness, _tool_input(), schema_slice="schema text")
    assert result == "MATCH (g:Gene {id: $gene_id}) RETURN g"
    assert len(harness.calls) == 1
    tier, _messages = harness.calls[0]
    assert tier == "plan"


@pytest.mark.asyncio
async def test_generate_cypher_issues_exactly_one_call() -> None:
    harness = _FakeHarness("MATCH (g:Gene {id: $gene_id}) RETURN g")
    await generate_cypher(harness, _tool_input(), schema_slice="schema text")
    assert len(harness.calls) == 1


@pytest.mark.asyncio
async def test_generate_cypher_prompt_includes_schema_slice() -> None:
    harness = _FakeHarness("MATCH (g:Gene {id: $gene_id}) RETURN g")
    await generate_cypher(harness, _tool_input(), schema_slice="UNIQUE_SCHEMA_MARKER_XYZ")
    _tier, messages = harness.calls[0]
    joined = "\n".join(message["content"] for message in messages)
    assert "UNIQUE_SCHEMA_MARKER_XYZ" in joined


@pytest.mark.asyncio
async def test_generate_cypher_prompt_instructs_edge_labels_and_parameters() -> None:
    harness = _FakeHarness("MATCH (g:Gene {id: $gene_id}) RETURN g")
    await generate_cypher(harness, _tool_input(), schema_slice="schema text")
    _tier, messages = harness.calls[0]
    system_content = messages[0]["content"]
    assert "explicit edge label" in system_content
    assert "$param_name" in system_content or "parameter" in system_content.lower()


@pytest.mark.asyncio
async def test_generate_cypher_with_prior_error_includes_error_and_prior_cypher() -> None:
    harness = _FakeHarness("MATCH (g:Gene {id: $gene_id}) RETURN g")
    prior_error = (
        "reason: missing_edge_label; rejected Cypher: "
        "MATCH (g:Gene {id: $gene_id})-->(d) RETURN g"
    )
    await generate_cypher(
        harness, _tool_input(), schema_slice="schema text", prior_error=prior_error
    )
    _tier, messages = harness.calls[0]
    joined = "\n".join(message["content"] for message in messages)
    assert "missing_edge_label" in joined
    assert "MATCH (g:Gene {id: $gene_id})-->(d) RETURN g" in joined


@pytest.mark.asyncio
async def test_generate_cypher_without_prior_error_omits_retry_language() -> None:
    harness = _FakeHarness("MATCH (g:Gene {id: $gene_id}) RETURN g")
    await generate_cypher(harness, _tool_input(), schema_slice="schema text", prior_error=None)
    _tier, messages = harness.calls[0]
    joined = "\n".join(message["content"] for message in messages)
    assert "Validator error" not in joined


@pytest.mark.asyncio
async def test_generate_cypher_strips_fenced_response_with_language_tag() -> None:
    harness = _FakeHarness("```cypher\nMATCH (g:Gene {id: $gene_id}) RETURN g\n```")
    result = await generate_cypher(harness, _tool_input(), schema_slice="schema text")
    assert result == "MATCH (g:Gene {id: $gene_id}) RETURN g"


@pytest.mark.asyncio
async def test_generate_cypher_strips_bare_fenced_response() -> None:
    harness = _FakeHarness("```\nMATCH (g:Gene {id: $gene_id}) RETURN g\n```")
    result = await generate_cypher(harness, _tool_input(), schema_slice="schema text")
    assert result == "MATCH (g:Gene {id: $gene_id}) RETURN g"


@pytest.mark.asyncio
async def test_generate_cypher_strips_prose_before_cypher_keyword() -> None:
    harness = _FakeHarness(
        "Here is the query you asked for:\nMATCH (g:Gene {id: $gene_id}) RETURN g"
    )
    result = await generate_cypher(harness, _tool_input(), schema_slice="schema text")
    assert result == "MATCH (g:Gene {id: $gene_id}) RETURN g"


@pytest.mark.asyncio
async def test_generate_cypher_strips_sql_wrapper_inside_fence() -> None:
    harness = _FakeHarness(
        "```sql\n"
        "SELECT * FROM cypher('ncbi_kg', $$ MATCH (g:Gene) RETURN g $$) AS (g agtype)\n"
        "```"
    )
    result = await generate_cypher(harness, _tool_input(), schema_slice="schema text")
    assert result == "MATCH (g:Gene) RETURN g"
    assert "SELECT" not in result
    assert "cypher(" not in result


@pytest.mark.asyncio
async def test_generate_cypher_strips_sql_wrapper_without_fence() -> None:
    harness = _FakeHarness(
        "SELECT * FROM cypher('ncbi_kg', $$ MATCH (g:Gene) RETURN g $$) AS (g agtype)"
    )
    result = await generate_cypher(harness, _tool_input(), schema_slice="schema text")
    assert result == "MATCH (g:Gene) RETURN g"


@pytest.mark.asyncio
async def test_generate_cypher_raises_on_no_recoverable_cypher() -> None:
    harness = _FakeHarness("I'm sorry, I cannot help construct that query.")
    with pytest.raises(CypherGenerationError):
        await generate_cypher(harness, _tool_input(), schema_slice="schema text")


@pytest.mark.asyncio
async def test_generate_cypher_raises_on_empty_response() -> None:
    harness = _FakeHarness("")
    with pytest.raises(CypherGenerationError):
        await generate_cypher(harness, _tool_input(), schema_slice="schema text")


@pytest.mark.asyncio
async def test_generate_cypher_raises_on_empty_fence() -> None:
    harness = _FakeHarness("```cypher\n\n```")
    with pytest.raises(CypherGenerationError):
        await generate_cypher(harness, _tool_input(), schema_slice="schema text")


@pytest.mark.asyncio
async def test_content_none_raises_generation_error_not_attribute_error() -> None:
    """Finding F-2.1-B03, observed live.

    A provider genuinely returns `content=None`. `_extract_cypher_body` was
    annotated `raw: str` and called `raw.strip()`, so it raised
    `AttributeError` out of a pipeline documented "Never raises".
    `act_node` catches only `HarnessCallError`, so it escaped `run()` and
    crashed the query instead of degrading to a refusal.

    The right failure is `CypherGenerationError`, which the caller already
    handles as retry-then-error like any other unrecoverable response.
    """

    class _NoContentHarness:
        trace_id = "test-none-content"

        async def call_tier(self, tier, messages, *, cache_prefix=None):
            return SimpleNamespace(content=None)

    tool_input = CypherQueryInput(
        query_intent="Look up BRCA1",
        query_class="lookup",
        target_entities=["NCBIGene:672"],
        row_limit=1,
    )

    with pytest.raises(CypherGenerationError) as excinfo:
        await generate_cypher(_NoContentHarness(), tool_input, "schema", None, {})

    assert "content=None" in str(excinfo.value) or "no content" in str(excinfo.value).lower()
