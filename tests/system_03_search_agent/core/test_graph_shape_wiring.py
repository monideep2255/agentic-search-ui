"""Card 15 (2026-10-15): Plan's decision `plan.graph_shape` forces a checked
graph search for a question develop has no template for.

Drives the real `plan_node` with only the classifier faked. No network.

Coverage statement, per `goal-contracts`: a question develop's own selection
templates today never asks the decision; a question whose identifiers allow no
shape never asks it; an eligible question asks it with exactly the shapes its
identifiers allow plus "none_of_these"; a pick forces the shape's template; and
"none_of_these", no usable pick, a failed seam and a stalled decision each leave
the planned call equal to develop's. What this file does NOT exercise: the live
classifier and the live graph (the card's build report has both).

Mutations each arm was shown to fail under (restored after each):

- Papers named: ignoring the pick (always returning `planned`) turned the
  forcing arm red; inverting the eligibility turned the never-asked arms red.
"""

from __future__ import annotations

from typing import Any

import pytest

from system_03_search_agent.contracts.events import DecisionRecord
from system_03_search_agent.contracts.events import ResolvedEntity as EventResolvedEntity
from system_03_search_agent.contracts.query import Query
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import harness as harness_module

POINT = "plan.graph_shape"
PMID_A = EventResolvedEntity(text="PMID 11237011", curie="PMID:11237011", confidence=1.0)
PMID_B = EventResolvedEntity(text="PMID 11237012", curie="PMID:11237012", confidence=1.0)
BRCA1 = EventResolvedEntity(text="BRCA1", curie="NCBIGene:672", confidence=1.0)

TWO_PAPERS = "Compare PMID 11237011 and PMID 11237012"


def _stub_decisions(
    monkeypatch: pytest.MonkeyPatch,
    pick: str | None,
    *,
    raises: bool = False,
    literature: str | None = None,
) -> list[dict[str, Any]]:
    """`plan.graph_shape` answers `pick` (None: no usable pick). Returns what was asked."""
    asked: list[dict[str, Any]] = []

    async def _decide(
        harness: Any, trace_id: str, point: str, state: str, options: Any, **kwargs: Any
    ) -> Any:
        if point == POINT:
            asked.append({"state": state, "options": tuple(options), "kwargs": kwargs})
            if raises:
                raise RuntimeError("seam down")
        if point == "plan.literature" and literature is not None:
            return DecisionRecord(
                name=point, options=list(options), chosen=literature, decided_by="jev",
                jev_choice=literature, guard_choice=literature, agreed=True,
            )
        if point != POINT or pick is None:
            return DecisionRecord(
                name=point, options=list(options), chosen=next(iter(options)),
                decided_by="guard", fallback_reason="timeout",
            )
        assert pick in options
        return DecisionRecord(
            name=point, options=list(options), chosen=pick, decided_by="jev",
            jev_choice=pick, guard_choice=pick, agreed=True,
        )

    monkeypatch.setattr(graph_module, "decide", _decide)
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    return asked


def _state(
    text: str, entities: list[EventResolvedEntity], query_class: str = "single_hop"
) -> dict[str, Any]:
    query = Query(text=text, session_id="s-gs", trace_id="t-gs", user_id=None)
    return {
        "query": query,
        "harness": harness_module.Harness(trace_id="t-gs"),
        "seq": 0,
        "findings": [],
        "findings_count": 0,
        "resolved_entities": entities,
        "query_class": query_class,
    }


def _graph_call(result: dict[str, Any]) -> graph_module._PlannedToolCall:
    calls = [c for c in result["tool_calls"] if isinstance(c, graph_module._PlannedToolCall) and not c.context_only]
    assert len(calls) == 1
    return calls[0]


def _same_call_as_develop(call: graph_module._PlannedToolCall, develop: graph_module._PlannedToolCall) -> None:
    """Everything but the per-call random id is equal."""
    assert call.cypher_input == develop.cypher_input
    assert call.template == develop.template
    assert call.context_only == develop.context_only
    assert call.memory_bound == develop.memory_bound
    assert call.tool_call.tool == develop.tool_call.tool
    assert call.tool_call.layer == develop.tool_call.layer


async def _develop_call(
    monkeypatch: pytest.MonkeyPatch, text: str, entities: list[EventResolvedEntity]
) -> graph_module._PlannedToolCall:
    """What develop plans: the same plan with the shape step switched out."""

    async def _identity(harness: Any, trace_id: str, text: str, planned: Any, deadline: float) -> Any:
        return planned

    with monkeypatch.context() as patch:
        _stub_decisions(patch, None)
        patch.setattr(graph_module, "_checked_graph_shape", _identity)
        return _graph_call(await graph_module.plan_node(_state(text, entities)))


# ---------------------------------------------------------------------------
# Papers named
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_named_papers_ask_the_decision_with_only_the_shapes_they_allow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked = _stub_decisions(monkeypatch, "papers_named")
    await graph_module.plan_node(_state(TWO_PAPERS, [PMID_A, PMID_B]))
    assert len(asked) == 1
    assert asked[0]["options"] == ("papers_named", "none_of_these")
    assert asked[0]["kwargs"]["default"] == "none_of_these"
    assert asked[0]["state"] == TWO_PAPERS


@pytest.mark.asyncio
async def test_a_papers_named_pick_forces_the_checked_record_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_decisions(monkeypatch, "papers_named")
    call = _graph_call(await graph_module.plan_node(_state(TWO_PAPERS, [PMID_A, PMID_B])))
    assert call.template is not None
    assert call.template.name == "article_record_many"
    assert call.context_only is False
    assert call.cypher_input.target_entities == ["PMID:11237011", "PMID:11237012"]


@pytest.mark.asyncio
@pytest.mark.parametrize("pick", ["none_of_these", None])
async def test_none_of_these_or_no_usable_pick_leaves_develops_call_unchanged(
    monkeypatch: pytest.MonkeyPatch, pick: str | None
) -> None:
    develop = await _develop_call(monkeypatch, TWO_PAPERS, [PMID_A, PMID_B])
    asked = _stub_decisions(monkeypatch, pick)
    call = _graph_call(await graph_module.plan_node(_state(TWO_PAPERS, [PMID_A, PMID_B])))
    assert asked, "the decision must have been asked for the populate check to mean anything"
    assert call.template is None
    _same_call_as_develop(call, develop)


@pytest.mark.asyncio
async def test_a_failed_decision_seam_leaves_develops_call_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    develop = await _develop_call(monkeypatch, TWO_PAPERS, [PMID_A, PMID_B])
    asked = _stub_decisions(monkeypatch, "papers_named", raises=True)
    call = _graph_call(await graph_module.plan_node(_state(TWO_PAPERS, [PMID_A, PMID_B])))
    assert asked
    _same_call_as_develop(call, develop)


@pytest.mark.asyncio
async def test_one_paper_and_a_gene_question_never_ask_the_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked = _stub_decisions(monkeypatch, "papers_named")
    one = await graph_module.plan_node(_state("What MeSH terms are assigned to PMID 11237011?", [PMID_A]))
    gene = await graph_module.plan_node(_state("Which diseases are associated with BRCA1?", [BRCA1]))
    assert asked == []
    assert _graph_call(one).template is None or _graph_call(one).template.name != "article_record_many"
    assert _graph_call(gene).template is None


@pytest.mark.asyncio
async def test_two_papers_develop_already_templates_never_ask_the_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lookup question about two papers already takes develop's record template."""
    asked = _stub_decisions(monkeypatch, "papers_named")
    result = await graph_module.plan_node(
        _state("What are PMID 11237011 and PMID 11237012?", [PMID_A, PMID_B], query_class="lookup")
    )
    assert asked == []
    assert _graph_call(result).template is None


def _has_literature_search(result: dict[str, Any]) -> bool:
    return any(
        isinstance(c, graph_module._PlannedNcbiEfetchToolCall) for c in result["tool_calls"]
    )


@pytest.mark.asyncio
async def test_a_picked_shape_is_not_displaced_by_the_literature_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live finding: "Compare PMID ... and PMID ..." was read as wanting papers and
    planned a PubMed search for the words "compare, pmid", showing unrelated papers."""
    _stub_decisions(monkeypatch, "papers_named", literature="wants_literature")
    result = await graph_module.plan_node(_state(TWO_PAPERS, [PMID_A, PMID_B]))
    assert _graph_call(result).template is not None
    assert not _has_literature_search(result)


@pytest.mark.asyncio
async def test_without_a_pick_the_literature_search_is_planned_as_it_is_on_develop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Populate check for the arm above: only the shape pick differs."""
    _stub_decisions(monkeypatch, "none_of_these", literature="wants_literature")
    result = await graph_module.plan_node(_state(TWO_PAPERS, [PMID_A, PMID_B]))
    assert _has_literature_search(result)


# ---------------------------------------------------------------------------
# Gene in a paper
# ---------------------------------------------------------------------------

GENE_IN_PAPER = "Does PMID 11237011 discuss BRCA1?"


@pytest.mark.asyncio
async def test_a_gene_and_a_paper_ask_the_decision_with_only_their_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked = _stub_decisions(monkeypatch, "gene_in_paper")
    await graph_module.plan_node(_state(GENE_IN_PAPER, [PMID_A, BRCA1]))
    assert [a["options"] for a in asked] == [("gene_in_paper", "none_of_these")]


@pytest.mark.asyncio
async def test_a_gene_in_paper_pick_forces_the_checked_link_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_decisions(monkeypatch, "gene_in_paper")
    call = _graph_call(await graph_module.plan_node(_state(GENE_IN_PAPER, [PMID_A, BRCA1])))
    assert call.template is not None and call.template.name == "gene_article_link"
    assert call.context_only is False


@pytest.mark.asyncio
@pytest.mark.parametrize("pick", ["none_of_these", None])
async def test_gene_and_paper_none_of_these_leaves_develops_call_unchanged(
    monkeypatch: pytest.MonkeyPatch, pick: str | None
) -> None:
    develop = await _develop_call(monkeypatch, GENE_IN_PAPER, [PMID_A, BRCA1])
    asked = _stub_decisions(monkeypatch, pick)
    call = _graph_call(await graph_module.plan_node(_state(GENE_IN_PAPER, [PMID_A, BRCA1])))
    assert asked
    assert call.template is None
    _same_call_as_develop(call, develop)


@pytest.mark.asyncio
async def test_two_genes_and_a_paper_ask_no_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _stub_decisions(monkeypatch, "gene_in_paper")
    brca2 = EventResolvedEntity(text="BRCA2", curie="NCBIGene:675", confidence=1.0)
    await graph_module.plan_node(_state(GENE_IN_PAPER, [PMID_A, BRCA1, brca2]))
    assert asked == []
