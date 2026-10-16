"""Card 29: MCP publishes develop's citation keys, never the abstract sentence.

`_ALLOWED_RESPONSE_KEYS` in `test_no_cost_and_auth.py` is a manual control, so
the web-only `snippet` is cleared before MCP serializes a citation.
"""

from __future__ import annotations

import pytest

from system_03_search_agent.adapters.mcp import server as server_module
from system_03_search_agent.contracts.events import TokenPayload
from tests.system_03_search_agent.adapters.mcp.test_parity_tools import (
    _GUARD_OK,
    _TRUST_LINE,
    _answer_trust,
    _citation,
    _done,
    _fold,
    _stream_of,
)

# Develop's citation keys: MCP's allowlist is a manual control, so card 29's
# `snippet` must never appear in what this surface publishes.
_DEVELOP_CITATION_KEYS = {
    "citation_id",
    "display_index",
    "source",
    "source_id",
    "source_url",
    "layer",
    "field",
    "claim_text",
    "evidence_kind",
    "assertion_confidence",
    "population_ancestry_context",
    "license",
    "snapshot_date",
    "entity_name",
}


class TestMcpPublishesDevelopsCitationKeys:
    @pytest.mark.asyncio
    async def test_a_live_answer_leaves_the_abstract_sentence_out(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: pass `citations` through unchanged at
        # the fold's return.
        with_sentence = _citation(1).model_copy(update={"snippet": "A quoted abstract sentence."})
        stream = _stream_of(
            _GUARD_OK,
            ("token", TokenPayload(text="Feature 1 [1]. ", marker_ids=["c1"])),
            ("citation", with_sentence),
            ("trust_signal", _answer_trust("answer")),
            ("done", _done("answer", trust_line=_TRUST_LINE)),
        )

        result = await _fold(monkeypatch, stream)

        dumped = result.model_dump()["citations"][0]
        assert set(dumped) == _DEVELOP_CITATION_KEYS
        assert "snippet" not in result.model_dump_json()

    def test_a_reopened_answer_leaves_it_out_too(self) -> None:
        stored = [{**_citation(1).model_dump(), "snippet": "A quoted abstract sentence."}]
        citations, _ = server_module._reopened_citations(stored, "One [1].")
        assert citations[0].snippet == "A quoted abstract sentence.", "populate check"
        published = server_module._citations_without_snippet(citations)
        assert set(published[0].model_dump()) == _DEVELOP_CITATION_KEYS
