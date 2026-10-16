"""Card 15 (2026-10-15): the checked graph searches for question shapes
`select_template` has no template for, as pure functions and through the
`cypher_query` pipeline with a fake graph. No model, no network.

The classifier decision that picks a shape is tested in
`core/test_graph_shape_wiring.py`; this file tests what a pick builds.

Mutations each arm was shown to fail under (restored after each):

- Papers named: making `possible_graph_shapes` accept one paper turned the
  count arm red.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from system_03_search_agent.tools import cypher_query as cypher_query_module
from system_03_search_agent.tools.cypher_query import (
    _bound_param_names,
    _unanchored_returned_variables,
    _unknown_param_names,
    cypher_query,
    entity_param_bindings,
)
from system_03_search_agent.tools.cypher_schemas import CypherQueryInput
from system_03_search_agent.tools.cypher_templates import (
    SHAPE_PAPERS_NAMED,
    graph_shape_template,
    possible_graph_shapes,
    select_template,
)
from system_03_search_agent.tools.cypher_validator import validate_cypher

PMID_A = "PMID:11237011"
PMID_B = "PMID:11237012"
BRCA1 = "NCBIGene:672"


def _bindings(*curies: str) -> dict[str, str]:
    return entity_param_bindings(list(curies))


def _assert_checked(cypher: str, bindings: dict[str, str]) -> str:
    result = validate_cypher(cypher, 100)
    assert result.ok, f"{result.reason} {result.message}"
    normalized = result.normalized_cypher or ""
    assert _unknown_param_names(normalized, bindings) == []
    assert _bound_param_names(normalized, bindings)
    assert _unanchored_returned_variables(normalized, bindings) == []
    return normalized


# ---------------------------------------------------------------------------
# Papers named
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("curies", "expected"),
    [
        ([PMID_A, PMID_B], [SHAPE_PAPERS_NAMED]),
        ([f"PMID:{n}" for n in range(1, 11)], [SHAPE_PAPERS_NAMED]),
        ([PMID_A], []),
        ([f"PMID:{n}" for n in range(1, 12)], []),
        ([PMID_A, PMID_B, BRCA1], []),
        ([], []),
        (["Unknown:1", "Unknown:2"], []),
    ],
)
def test_papers_named_is_possible_only_for_two_to_ten_papers_and_nothing_else(
    curies: list[str], expected: list[str]
) -> None:
    assert possible_graph_shapes(_bindings(*curies)) == expected


def test_the_papers_named_template_is_one_inline_match_per_paper_in_name_order() -> None:
    bindings = _bindings(PMID_B, PMID_A)
    template = graph_shape_template(SHAPE_PAPERS_NAMED, bindings)
    assert template is not None
    assert template.name == "article_record_many"
    names = sorted(bindings)
    assert template.cypher == " UNION ALL ".join(
        f"MATCH (a:Article {{id: ${name}}}) RETURN a ORDER BY a.id" for name in names
    )
    assert "WHERE" not in template.cypher and " IN " not in template.cypher
    _assert_checked(template.cypher, bindings)


def test_the_same_papers_in_either_order_build_the_same_query() -> None:
    one = graph_shape_template(SHAPE_PAPERS_NAMED, _bindings(PMID_A, PMID_B))
    two = graph_shape_template(SHAPE_PAPERS_NAMED, _bindings(PMID_B, PMID_A))
    assert one is not None and two is not None
    assert one.cypher == two.cypher


def test_a_shape_the_identifiers_do_not_allow_builds_nothing() -> None:
    assert graph_shape_template(SHAPE_PAPERS_NAMED, _bindings(PMID_A)) is None
    assert graph_shape_template("not_a_shape", _bindings(PMID_A, PMID_B)) is None


def test_develop_has_no_template_for_two_papers_on_a_hop_class() -> None:
    """The precondition the decision rests on: this is a question develop's
    own selection leaves to a written search today."""
    bindings = _bindings(PMID_A, PMID_B)
    intent = CypherQueryInput(
        query_intent="Compare PMID 11237011 and PMID 11237012",
        query_class="single_hop",
        target_entities=[PMID_A, PMID_B],
    )
    assert select_template(intent, bindings) is None


def _vertex(label: str, curie: str, name: str, url: str) -> str:
    payload = {
        "id": 844424930131969,
        "label": label,
        "properties": {"id": curie, "name": name, "source_url": url},
    }
    return json.dumps(payload) + "::vertex"


class _RefusingHarness:
    trace_id = "shape-trace"

    def get_query_cost_usd(self, trace_id: str) -> float:
        return 0.0

    async def call_tier(self, tier: str, messages: Any, **_: Any) -> Any:
        raise AssertionError("plan tier called on the checked path")


@pytest.mark.asyncio
async def test_a_forced_papers_template_returns_each_paper_cited_and_writes_no_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executed: list[tuple[str, Any]] = []

    def _fake(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        executed.append((cypher, params))
        return [
            {"c0": _vertex("Article", c, f"Paper {c[5:]}", f"https://pubmed.ncbi.nlm.nih.gov/{c[5:]}/")}
            for c in (PMID_A, PMID_B)
        ], 2

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake)
    bindings = _bindings(PMID_A, PMID_B)
    template = graph_shape_template(SHAPE_PAPERS_NAMED, bindings)
    output = await cypher_query(
        _RefusingHarness(),
        CypherQueryInput(
            query_intent="Compare PMID 11237011 and PMID 11237012",
            query_class="single_hop",
            target_entities=[PMID_A, PMID_B],
        ),
        template=template,
    )
    assert output.status == "ok"
    assert output.template == "article_record_many"
    assert [row.curie for row in output.rows] == [PMID_A, PMID_B]
    assert all(row.source_url.startswith("https://pubmed.ncbi.nlm.nih.gov/") for row in output.rows)
    assert executed[0][1] == bindings
