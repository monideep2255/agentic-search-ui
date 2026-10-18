"""Card 94 (2026-10-16): "When the Pathogen Detection search behind an isolate
question runs out of time, I still get the rest of my answer with a plain
note, instead of losing the whole answer."

The tool's deadline cutoff returns status "timeout", a fifth status the Act
result cannot carry, which crashed Act for every isolate mode. It is now shaped
as an error result (failure kind `timed_out`), so Act carries on and Write
shows the existing unfinished-search note.

Mutation proof (recorded in the report): drop the `timeout` to `error` mapping
in `_layer_tool_output_to_structured_fields` and each arm goes red.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from system_03_search_agent.contracts.events import ToolCall
from system_03_search_agent.contracts.query import Query
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.tools.cypher_schemas import (
    CypherQueryInput,
    CypherQueryOutput,
    CypherQueryRow,
)
from system_03_search_agent.tools.pathogen_detection_schemas import (
    PathogenDetectionInput,
    PathogenDetectionOutput,
)

_QUESTION = "Which E. coli isolates in Pathogen Detection carry blaCTX-M genes?"

_INPUTS = {
    "isolate_search": {
        "mode": "isolate_search",
        "taxon": "Escherichia_coli_Shigella",
        "amr_gene_prefixes": ["blaCTX-M"],
    },
    "isolate_lookup": {
        "mode": "isolate_lookup",
        "taxon": "Salmonella",
        "biosample_acc": "SAMN02442784",
    },
    "cluster_snp_neighbors": {
        "mode": "cluster_snp_neighbors",
        "taxon": "Salmonella",
        "pds_cluster": "PDS000001",
    },
}


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", sorted(_INPUTS))
async def test_a_timed_out_pathogen_search_is_an_error_result_and_act_carries_on(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    graph_row = CypherQueryRow(
        node_or_edge_type="Gene",
        curie="NCBIGene:672",
        fields={"name": "BRCA1"},
        source_url="https://www.ncbi.nlm.nih.gov/gene/672",
        graph_snapshot_version="v1",
    )

    async def _cypher(harness: Any, cypher_input: Any, **kwargs: Any) -> CypherQueryOutput:
        return CypherQueryOutput(
            status="ok", row_count=1, total_available=1, truncated=False, rows=[graph_row], error=None
        )

    async def _timed_out(tool_input: Any) -> PathogenDetectionOutput:
        return PathogenDetectionOutput(
            status="timeout",
            mode=mode,
            isolate_count=0,
            total_available=0,
            truncated=True,
            error="deadline",
        )

    monkeypatch.setattr(graph_module, "cypher_query", _cypher)
    monkeypatch.setattr(graph_module, "pathogen_detection", _timed_out)
    pd_call = graph_module._PlannedLayerToolCall(
        tool_call=ToolCall(tool="pathogen_detection", call_id="pd-t1", layer="layer_2_api"),
        tool_input=PathogenDetectionInput.model_validate(_INPUTS[mode]),
    )
    graph_call = graph_module._PlannedToolCall(
        tool_call=ToolCall(tool="cypher_query", call_id="cq-t1", layer="layer_1_graph"),
        cypher_input=CypherQueryInput(
            query_intent=_QUESTION, query_class="lookup", target_entities=["NCBIGene:672"], row_limit=100
        ),
    )
    state: dict[str, Any] = {
        "harness": harness_module.Harness(trace_id="trace-pd-timeout"),
        "query": Query(text=_QUESTION, session_id="s-pd", trace_id="trace-pd-timeout", user_id=None),
        "query_class": "lookup",
        "tool_calls": [graph_call, pd_call],
        "seq": 0,
        "start_monotonic": time.monotonic(),
    }
    result = await graph_module.act_node(state)

    # Act completed, the other layer's finding stands, and the timeout is a
    # failed search of kind timed_out for Write's existing note.
    assert result["findings_count"] >= 1
    assert any(f.tool == "cypher_query" for f in result["findings"])
    assert [(f["tool"], f["kind"]) for f in result["failed_searches"]] == [
        ("pathogen_detection", "timed_out")
    ]
