"""Card 15 (2026-10-15): the checked graph searches for question shapes
`select_template` has no template for, as pure functions and through the
`cypher_query` pipeline with a fake graph. No model, no network.

The classifier decision that picks a shape is tested in
`core/test_graph_shape_wiring.py`; this file tests what a pick builds.

Mutations each arm was shown to fail under (restored after each):

- Papers named: making `possible_graph_shapes` accept one paper turned the
  count arm red.
- Gene in a paper: swapping the template's edge direction turned the
  template-text arm red.
- Genes' variants: dropping the template's `branch_row_cap` turned the
  capped-result arm red.
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
    SHAPE_GENE_IN_PAPER,
    SHAPE_GENES_VARIANTS_FOR_CONDITION,
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


# ---------------------------------------------------------------------------
# Gene in a paper
# ---------------------------------------------------------------------------

LINKED_PAPER = "PMID:10026184"


@pytest.mark.parametrize(
    ("curies", "expected"),
    [
        ([BRCA1, PMID_A], [SHAPE_GENE_IN_PAPER]),
        ([PMID_A, BRCA1], [SHAPE_GENE_IN_PAPER]),
        ([BRCA1, "NCBIGene:675", PMID_A], []),
        ([BRCA1, PMID_A, PMID_B], []),
        ([BRCA1], []),
        ([BRCA1, PMID_A, "MedGen:C0346153"], []),
    ],
)
def test_gene_in_paper_is_possible_only_for_one_gene_and_one_paper_and_nothing_else(
    curies: list[str], expected: list[str]
) -> None:
    assert possible_graph_shapes(_bindings(*curies)) == expected


def test_the_gene_in_paper_template_anchors_both_ends_inline_from_the_gene_end() -> None:
    bindings = _bindings(BRCA1, PMID_A)
    template = graph_shape_template(SHAPE_GENE_IN_PAPER, bindings)
    assert template is not None
    assert template.name == "gene_article_link"
    assert template.edge_label == "mentioned_in"
    assert template.cypher == (
        "MATCH (a:Gene {id: $e_NCBIGene_672})-[:mentioned_in]->"
        "(x:Article {id: $e_PMID_11237011}) RETURN x ORDER BY x.id"
    )
    _assert_checked(template.cypher, bindings)


def test_develop_has_no_template_for_a_gene_and_a_paper() -> None:
    intent = CypherQueryInput(
        query_intent="Does PMID 11237011 discuss BRCA1?",
        query_class="single_hop",
        target_entities=[BRCA1, PMID_A],
    )
    assert select_template(intent, _bindings(BRCA1, PMID_A)) is None


@pytest.mark.asyncio
async def test_an_unlinked_gene_and_paper_return_no_row_and_no_claim_about_the_paper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The graph can say it holds no link. It cannot say what the paper discusses."""
    monkeypatch.setattr(
        cypher_query_module, "execute_cypher", lambda *a, **k: ([], 0)
    )
    bindings = _bindings(BRCA1, PMID_A)
    output = await cypher_query(
        _RefusingHarness(),
        CypherQueryInput(
            query_intent="Does PMID 11237011 discuss BRCA1?",
            query_class="single_hop",
            target_entities=[BRCA1, PMID_A],
        ),
        template=graph_shape_template(SHAPE_GENE_IN_PAPER, bindings),
    )
    assert output.template == "gene_article_link"
    assert output.status == "empty"
    assert output.rows == []
    assert output.error is None


@pytest.mark.asyncio
async def test_a_linked_gene_and_paper_return_the_paper_cited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cypher_query_module,
        "execute_cypher",
        lambda *a, **k: (
            [{"c0": _vertex("Article", LINKED_PAPER, "Mapping BRCA1 domains", "https://pubmed.ncbi.nlm.nih.gov/10026184/")}],
            1,
        ),
    )
    bindings = _bindings(BRCA1, LINKED_PAPER)
    output = await cypher_query(
        _RefusingHarness(),
        CypherQueryInput(
            query_intent="Does PMID 10026184 discuss BRCA1?",
            query_class="single_hop",
            target_entities=[BRCA1, LINKED_PAPER],
        ),
        template=graph_shape_template(SHAPE_GENE_IN_PAPER, bindings),
    )
    assert [row.curie for row in output.rows] == [LINKED_PAPER]
    assert output.rows[0].source_url == "https://pubmed.ncbi.nlm.nih.gov/10026184/"
    assert {row.traversed_edge_type for row in output.rows} == {"mentioned_in"}


# ---------------------------------------------------------------------------
# Several genes' variants for a condition
# ---------------------------------------------------------------------------

MLH1 = "NCBIGene:4292"
MSH2 = "NCBIGene:4436"
MSH6 = "NCBIGene:2956"
LYNCH = "MedGen:C1333990"
LYNCH_2 = "MedGen:C4552100"


@pytest.mark.parametrize(
    ("curies", "expected"),
    [
        ([MLH1, MSH2, LYNCH], [SHAPE_GENES_VARIANTS_FOR_CONDITION]),
        ([MLH1, MSH2, LYNCH, LYNCH_2], [SHAPE_GENES_VARIANTS_FOR_CONDITION]),
        ([MLH1, MSH2, MSH6, "MONDO:0005835"], [SHAPE_GENES_VARIANTS_FOR_CONDITION]),
        ([MLH1, LYNCH], []),
        ([MLH1, MSH2], []),
        ([LYNCH, LYNCH_2], []),
        ([MLH1, MSH2, LYNCH, PMID_A], []),
        ([f"NCBIGene:{n}" for n in range(1, 12)] + [LYNCH], []),
    ],
)
def test_genes_variants_is_possible_only_for_several_genes_and_a_condition_and_nothing_else(
    curies: list[str], expected: list[str]
) -> None:
    assert possible_graph_shapes(_bindings(*curies)) == expected


def test_the_several_genes_template_gives_each_gene_an_equal_share_before_its_return() -> None:
    bindings = _bindings(MSH2, MLH1, LYNCH)
    template = graph_shape_template(SHAPE_GENES_VARIANTS_FOR_CONDITION, bindings)
    assert template is not None
    assert template.name == "gene_variant_disease_link_many"
    branches = template.cypher.split(" UNION ALL ")
    assert len(branches) == 2
    gene_names = sorted(n for n, c in bindings.items() if c.startswith("NCBIGene"))
    disease_name = next(n for n, c in bindings.items() if c.startswith("MedGen"))
    for branch, gene in zip(branches, gene_names, strict=True):
        assert branch == (
            f"MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(a:Gene {{id: ${gene}}}) "
            f"MATCH (v)-[:has_phenotype]->(x:Disease {{id: ${disease_name}}}) "
            "WITH v, collect(DISTINCT x) AS xs ORDER BY v.id LIMIT 50 "
            "RETURN v, xs ORDER BY v.id"
        )
    assert template.branch_row_cap == 50
    assert template.fold == ("v", "xs", "clinvar_condition_ids")
    _assert_checked(template.cypher, bindings)


def test_the_share_is_the_budget_divided_by_the_genes() -> None:
    three = graph_shape_template(SHAPE_GENES_VARIANTS_FOR_CONDITION, _bindings(MLH1, MSH2, MSH6, LYNCH))
    assert three is not None
    assert three.cypher.count("LIMIT 33 ") == 3 and three.branch_row_cap == 33


def test_several_conditions_use_the_in_clause_the_one_gene_template_uses() -> None:
    bindings = _bindings(MLH1, MSH2, LYNCH, LYNCH_2)
    template = graph_shape_template(SHAPE_GENES_VARIANTS_FOR_CONDITION, bindings)
    assert template is not None
    assert template.cypher.count("WHERE x.id IN [") == 2
    _assert_checked(template.cypher, bindings)


def test_develop_leaves_several_genes_and_a_condition_to_a_written_search_only_with_a_variants_word() -> None:
    bindings = _bindings(MLH1, MSH2, LYNCH)
    entities = [MLH1, MSH2, LYNCH]
    variants = CypherQueryInput(
        query_intent="Variants in MLH1 and MSH2 causing Lynch syndrome",
        query_class="single_hop",
        target_entities=entities,
    )
    assert select_template(variants, bindings) is None
    no_word = CypherQueryInput(
        query_intent="MLH1 and MSH2 in Lynch syndrome", query_class="single_hop", target_entities=entities
    )
    kept = select_template(no_word, bindings)
    assert kept is not None and kept.name == "gene_diseases_many"


def _variant(curie: str, gene: str, internal: int) -> str:
    local = curie.split(":")[1]
    return _vertex(
        "SequenceVariant", curie, f"NM_000249.4({gene}):c.{local}G>A",
        f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{local}",
    ).replace("844424930131969", str(internal))


def _disease(curie: str) -> str:
    return _vertex("Disease", curie, "Lynch syndrome", f"https://www.ncbi.nlm.nih.gov/medgen/{curie[7:]}")


def _variant_rows(count: int) -> list[dict[str, str]]:
    return [
        {"c0": _variant(f"ClinVar:{1000 + i}", "MLH1" if i % 2 else "MSH2", 100 + i), "c1": "[" + _disease(LYNCH) + "]"}
        for i in range(count)
    ]


def _many_input() -> CypherQueryInput:
    return CypherQueryInput(
        query_intent="Variants in MLH1 and MSH2 causing Lynch syndrome",
        query_class="single_hop",
        target_entities=[MLH1, MSH2, LYNCH],
    )


async def _run_many(monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, str]]) -> tuple[Any, list[str]]:
    executed: list[str] = []

    def _fake(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        executed.append(cypher)
        return rows, len(rows)

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake)
    template = graph_shape_template(
        SHAPE_GENES_VARIANTS_FOR_CONDITION, _bindings(MLH1, MSH2, LYNCH)
    )
    output = await cypher_query(_RefusingHarness(), _many_input(), template=template)
    return output, executed


@pytest.mark.asyncio
async def test_each_variant_row_carries_the_conditions_its_clinvar_record_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, executed = await _run_many(monkeypatch, _variant_rows(6))
    variants = [r for r in output.rows if r.node_or_edge_type == "SequenceVariant"]
    assert len(variants) == 6
    assert all(r.fields["clinvar_condition_ids"] == [LYNCH] for r in variants)
    assert all(r.source_url and "clinvar" in r.source_url for r in variants)
    assert output.truncated is False
    assert len(executed) == 1


@pytest.mark.asyncio
async def test_a_result_as_large_as_one_genes_share_reports_capped_with_the_total_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One gene with hundreds of variants fills its share of 50 and the other has
    30, so 80 rows come back, under the overall limit of 100. The answer must still
    say there are more, and no count query may run (a UNION cannot be counted)."""
    output, executed = await _run_many(monkeypatch, _variant_rows(80))
    assert output.truncated is True
    assert output.total_available is None
    assert len(executed) == 1, "a count query ran for a UNION"


@pytest.mark.asyncio
async def test_a_result_smaller_than_one_share_is_not_reported_capped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, _ = await _run_many(monkeypatch, _variant_rows(49))
    assert output.truncated is False
