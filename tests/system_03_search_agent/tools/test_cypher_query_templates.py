"""Pipeline tests for the template path in `cypher_query._run_pipeline`
(UI fix set 10, item 10.1, R34).

`test_cypher_query.py` switches templates OFF with an autouse fixture and
tests the generated path. This file tests the opposite property on the
same pipeline: for a known shape the harness is never called, the
template still passes through the validator and the binding checks, the
rows are shaped and cited exactly as a generated query's would be, and
the output records which template ran.

How each arm was shown able to fail:

- No model call: `_RefusingHarness.call_tier` raises. Mutation: deleting
  the `if template is not None` branch in `_run_pipeline` made every
  template arm raise `AssertionError("plan tier called")`.
- Fallback calls the model: the harness's scripted Cypher is what runs and
  `template` is None. Mutation: making `select_template` return the
  record template for any input turned it red (harness never called).
- Validator still gates the template: a monkeypatched `select_template`
  returns a template with a forbidden write clause, then one with an
  unanchored decoy. Mutation: skipping `validate_cypher` on the template
  path executed the DELETE text against the fake graph and the arm went
  red on `status == "ok"`.
- Same rows, same order, live: gated on `live_graph_arms_enabled`, runs
  the BRCA1 disease template twice against the real graph and asserts the
  CURIE list is identical and sorted. Mutation: replacing the template's
  `ORDER BY x.id` with `ORDER BY x.name` made the sorted-by-id assertion
  fail on the real data (the four MedGen ids are not in name order).
"""

from __future__ import annotations

import json
import os
from typing import Any

import pytest

from system_03_search_agent.tools import cypher_query as cypher_query_module
from system_03_search_agent.tools.cypher_query import cypher_query
from system_03_search_agent.tools.cypher_schemas import CypherQueryInput
from system_03_search_agent.tools.cypher_templates import CypherTemplate

BRCA1 = "NCBIGene:672"


class _RefusingHarness:
    """A harness whose plan tier must never be reached. The template path's
    whole point is that it makes no model call, so a call is a failure,
    not a fixture to script."""

    trace_id = "template-trace"

    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    def get_query_cost_usd(self, trace_id: str) -> float:
        return 0.0

    async def call_tier(self, tier: str, messages: list[dict[str, str]], **_: Any) -> Any:
        self.calls.append(messages)
        raise AssertionError("plan tier called on the template path")


class _ScriptedHarness(_RefusingHarness):
    def __init__(self, cypher: str) -> None:
        super().__init__()
        self._cypher = cypher

    async def call_tier(self, tier: str, messages: list[dict[str, str]], **_: Any) -> Any:
        self.calls.append(messages)
        from types import SimpleNamespace

        return SimpleNamespace(content=self._cypher)


def _vertex(label: str, curie: str, name: str, url: str) -> str:
    payload = {
        "id": 844424930131969,
        "label": label,
        "properties": {"id": curie, "name": name, "source_url": url},
    }
    return json.dumps(payload) + "::vertex"


_DISEASES = [
    ("MedGen:C0346153", "Familial cancer of breast"),
    ("MedGen:C2676676", "Breast-ovarian cancer, familial 1"),
    ("MedGen:C3280442", "Pancreatic cancer, susceptibility to, 4"),
    ("MedGen:C4554406", "Fanconi anemia, complementation group S"),
]


def _disease_rows() -> list[dict[str, str]]:
    return [
        {"c0": _vertex("Disease", curie, name, f"https://www.ncbi.nlm.nih.gov/medgen/{curie[7:]}")}
        for curie, name in _DISEASES
    ]


def _input(intent: str, query_class: str = "single_hop", entities: list[str] | None = None):
    return CypherQueryInput(
        query_intent=intent, query_class=query_class, target_entities=entities or [BRCA1]
    )


@pytest.mark.asyncio
async def test_a_known_shape_makes_no_model_call_and_records_its_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executed: list[tuple[str, dict[str, Any] | None]] = []

    def _fake_execute(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        executed.append((cypher, params))
        return _disease_rows(), len(_DISEASES)

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute)
    harness = _RefusingHarness()

    output = await cypher_query(harness, _input("Which diseases are associated with BRCA1?"))

    assert harness.calls == []
    assert output.status == "ok"
    assert output.template == "gene_diseases_one"
    assert output.cypher_executed is not None
    assert "ORDER BY x.id LIMIT 100" in output.cypher_executed
    assert executed[0][1] == {"e_NCBIGene_672": BRCA1}
    assert [row.curie for row in output.rows] == [curie for curie, _ in _DISEASES]
    assert all(row.source_url for row in output.rows)
    assert {row.traversed_edge_type for row in output.rows} == {"gene_associated_with_condition"}
    assert output.row_count == 4 and output.total_available == 4 and output.truncated is False


@pytest.mark.asyncio
async def test_an_unknown_shape_still_runs_the_model_path(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_execute(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        return _disease_rows()[:1], 1

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute)
    scripted = "MATCH (g:Gene {id: $e_NCBIGene_672})-[:gene_associated_with_condition]->(d:Disease) RETURN d"
    harness = _ScriptedHarness(scripted)

    output = await cypher_query(harness, _input("Tell me about BRCA1", query_class="exploratory"))

    assert len(harness.calls) == 1, "the plan tier must write the Cypher when no template matches"
    assert output.status == "ok"
    assert output.template is None
    assert output.cypher_executed == scripted + " LIMIT 100"


@pytest.mark.parametrize(
    ("bad_template", "expected_reason_fragment"),
    [
        (
            CypherTemplate(
                name="broken_write",
                cypher="MATCH (a:Gene {id: $e_NCBIGene_672}) DELETE a RETURN a",
                edge_label=None,
            ),
            "write clause",
        ),
        (
            CypherTemplate(
                name="broken_decoy",
                cypher=(
                    "MATCH (a:Gene {id: $e_NCBIGene_672}) WITH a "
                    "MATCH (g:Gene)-[:gene_associated_with_condition]->(x:Disease) "
                    "RETURN x ORDER BY x.id"
                ),
                edge_label="gene_associated_with_condition",
            ),
            "not connected to any bound entity",
        ),
        (
            CypherTemplate(
                name="broken_param",
                cypher="MATCH (a:Gene {id: $e_invented}) RETURN a",
                edge_label=None,
            ),
            "unbound parameter",
        ),
    ],
)
@pytest.mark.asyncio
async def test_a_template_that_fails_the_gate_is_an_error_not_a_bypass(
    monkeypatch: pytest.MonkeyPatch,
    bad_template: CypherTemplate,
    expected_reason_fragment: str,
) -> None:
    executed: list[str] = []

    def _fake_execute(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        executed.append(cypher)
        return _disease_rows(), 4

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute)
    monkeypatch.setattr(cypher_query_module, "select_template", lambda *_: bad_template)
    harness = _RefusingHarness()

    output = await cypher_query(harness, _input("Which diseases are associated with BRCA1?"))

    assert output.status == "error"
    assert output.template == bad_template.name
    assert output.error is not None
    assert "code defect" in output.error
    assert expected_reason_fragment in output.error
    assert executed == [], "a rejected template must never reach the graph"
    assert harness.calls == [], "a rejected template is not handed to the model either"
    assert output.rows == []


@pytest.mark.asyncio
async def test_the_empty_and_error_outputs_carry_the_template_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _no_rows(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        return [], 0

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _no_rows)
    output = await cypher_query(_RefusingHarness(), _input("What variants cause it?"))
    assert output.status == "empty"
    assert output.template == "gene_variants_one"

    from system_03_search_agent.tools.graph_connection import GraphConnectionError

    def _down(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        raise GraphConnectionError("graph unreachable")

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _down)
    output = await cypher_query(_RefusingHarness(), _input("What variants cause it?"))
    assert output.status == "error"
    assert output.template == "gene_variants_one"


# ---------------------------------------------------------------------------
# Live: same rows, same order, against the real graph.
# ---------------------------------------------------------------------------


def _live_enabled() -> bool:
    from tests.system_03_search_agent.graph_gate import live_graph_arms_enabled

    return live_graph_arms_enabled()


_LIVE_ENABLED = _live_enabled()
# Captured at import, AFTER the gate loaded `.env`, because this directory's
# `conftest.py` clears GRAPH_QUERY_URL before every test so that each test
# states its own transport. Without re-stating it the arm below would run
# against psycopg2 on a tunnel port nothing listens on, report "connection
# refused", and read as a template defect. Measured 2026-09-13: the tool's
# own premise gate had been doing exactly that.
_GRAPH_QUERY_URL = os.environ.get("GRAPH_QUERY_URL", "")


@pytest.mark.skipif(
    not _LIVE_ENABLED,
    reason="needs the live graph (GRAPH_QUERY_URL) and RUN_PREMISE_GATE=1",
)
@pytest.mark.asyncio
async def test_live_repeated_retrieval_is_identical_and_ordered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _GRAPH_QUERY_URL, "the gate said live arms are enabled but GRAPH_QUERY_URL is empty"
    monkeypatch.setenv("GRAPH_QUERY_URL", _GRAPH_QUERY_URL)
    harness = _RefusingHarness()
    question = _input("Which diseases are associated with BRCA1?")
    first = await cypher_query(harness, question)
    second = await cypher_query(harness, question)

    assert harness.calls == []
    assert first.status == "ok" and second.status == "ok"
    assert first.template == second.template == "gene_diseases_one"
    first_ids = [row.curie for row in first.rows]
    second_ids = [row.curie for row in second.rows]
    assert first_ids, "the graph returned no diseases for BRCA1; the premise changed"
    assert first_ids == second_ids
    assert first_ids == sorted(first_ids)
    assert [row.source_url for row in first.rows] == [row.source_url for row in second.rows]

    variants = _input("What variants cause it?")
    first_v = await cypher_query(harness, variants)
    second_v = await cypher_query(harness, variants)
    assert first_v.template == "gene_variants_one"
    ids_v = [row.curie for row in first_v.rows]
    assert ids_v == [row.curie for row in second_v.rows]
    assert ids_v == sorted(ids_v)
    assert first_v.truncated is True and first_v.total_available not in (None, 0)
