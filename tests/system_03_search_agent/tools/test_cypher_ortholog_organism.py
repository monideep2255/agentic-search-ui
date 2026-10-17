"""Card 38, slice B: TP53's orthologs carry their species.

No model, no network: `execute_cypher` is replaced by a fake returning raw
AGE wire text shaped like the live rows of phase 8.9's probe 1 (591 of 591
TP53 orthologs have an `in_taxon` edge; the Gene vertex's keys carry no
organism). The live graph was not reachable when this was built.

What each arm proves, and that it fails on develop (the template there is
`MATCH ... RETURN x ORDER BY x.id` with no fold):

- Shape: the single-gene ortholog template is parameterized, read-only, and
  uses OPTIONAL MATCH so an ortholog with no taxon edge still appears.
- Total: a two-column RETURN used to report its total as unknown; a stubbed
  count of 591 now stays 591 while the rows stay at 100.
- Fold: each ortholog row carries `fields["organism"]`; a taxon never
  becomes a row; a list or dict item is ignored, never `str()`-rendered.
- Edge type: the ortholog rows keep `orthologous_to`.
- Every other template's Cypher is byte-identical to develop's.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from system_03_search_agent.tools import cypher_query as cypher_query_module
from system_03_search_agent.tools.cypher_query import cypher_query
from system_03_search_agent.tools.cypher_schemas import CypherQueryInput
from system_03_search_agent.tools.cypher_templates import (
    FOLD_FIELD_ORGANISM,
    MAX_FOLD_ITEMS,
    all_template_examples,
    select_template,
)
from system_03_search_agent.tools.cypher_validator import validate_cypher

TP53 = "NCBIGene:7157"
# sha256 of repr([(name, cypher), ...]) over every template but
# gene_orthologs_one, taken from develop 655e9dfe (45 templates).
OTHER_TEMPLATES_SHA256 = "21d2aa9d99ea9c94739f5b5d79ba1887ea72de616e140bc7926d038ff6abd0ed"


class _RefusingHarness:
    trace_id = "ortholog-trace"

    def get_query_cost_usd(self, trace_id: str) -> float:
        return 0.0

    async def call_tier(self, tier: str, messages: list[dict[str, str]], **_: Any) -> Any:
        raise AssertionError("plan tier called on the template path")


def _gene(curie: str, name: str = "tumor protein p53") -> str:
    payload = {
        "id": 1,
        "label": "Gene",
        "properties": {
            "id": curie,
            "name": name,
            "source_url": f"https://www.ncbi.nlm.nih.gov/gene/{curie.split(':')[1]}",
        },
    }
    return json.dumps(payload) + "::vertex"


def _row(n: int, organisms: Any) -> dict[str, str]:
    return {"c0": _gene(f"NCBIGene:{100000 + n}"), "c1": json.dumps(organisms)}


def _input() -> CypherQueryInput:
    return CypherQueryInput(
        query_intent="What are the known orthologs of TP53 in other species?",
        query_class="single_hop",
        target_entities=[TP53],
    )


def _ortholog_template():
    return next(t for t in all_template_examples() if t.name == "gene_orthologs_one")


def test_the_ortholog_template_reads_each_organism_and_stays_read_only() -> None:
    template = select_template(_input(), {"e_NCBIGene_7157": TP53})
    assert template is not None and template.name == "gene_orthologs_one"
    assert template.edge_label == "orthologous_to"
    assert template.value_fold is True
    assert template.fold == ("x", "xs", FOLD_FIELD_ORGANISM) and FOLD_FIELD_ORGANISM == "organism"
    cypher = template.cypher
    assert "OPTIONAL MATCH (x)-[:in_taxon]->(t:OrganismTaxon)" in cypher
    assert "$e_NCBIGene_7157" in cypher and "NCBIGene:7157" not in cypher and "'" not in cypher
    for word in ("CREATE", "MERGE", "SET ", "DELETE", "REMOVE"):
        assert word not in cypher
    assert validate_cypher(cypher, row_limit=100).ok


def test_only_the_single_gene_ortholog_template_changed() -> None:
    rest = [(t.name, t.cypher) for t in all_template_examples() if t.name != "gene_orthologs_one"]
    assert len(rest) == 45
    assert hashlib.sha256(repr(rest).encode()).hexdigest() == OTHER_TEMPLATES_SHA256
    assert all(
        t.value_fold is False for t in all_template_examples() if t.name != "gene_orthologs_one"
    )


@pytest.mark.asyncio
async def test_the_list_carries_species_and_the_total_stays_591(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executed: list[str] = []
    species = [
        ["Oryctolagus cuniculus"],
        ["Oryzias latipes"],
        ["Mus musculus", "Mus  musculus", "  ", "Mus\tmusculus domesticus\n"],
    ]
    rows = [_row(n, species[n % 3]) for n in range(100)]

    def _fake_execute(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        executed.append(cypher)
        if "total_count" in cypher:
            return [{"c0": "591"}], 1
        return rows, 591

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute)
    output = await cypher_query(_RefusingHarness(), _input())

    assert output.status == "ok" and output.template == "gene_orthologs_one"
    assert output.row_count == 100 and len(output.rows) == 100
    assert output.total_available == 591 and output.truncated is True
    assert any("total_count" in c for c in executed)
    assert all(row.curie.startswith("NCBIGene:") for row in output.rows)
    organisms = [row.fields["organism"] for row in output.rows]
    assert organisms[0] == "Oryctolagus cuniculus"
    assert organisms[1] == "Oryzias latipes"
    assert organisms[2] == "Mus musculus, Mus musculus domesticus"
    assert {row.traversed_edge_type for row in output.rows} == {"orthologous_to"}


def test_the_count_query_counts_one_row_per_ortholog() -> None:
    from system_03_search_agent.tools.cypher_query import _build_count_cypher

    normalized = validate_cypher(_ortholog_template().cypher, row_limit=100).normalized_cypher
    count = _build_count_cypher(normalized)
    assert count is not None
    assert count.endswith("WITH x, collect(DISTINCT t.name) AS xs RETURN count(*) AS total_count")
    assert validate_cypher(count, row_limit=1).ok


@pytest.mark.asyncio
async def test_a_taxon_never_becomes_a_row_and_odd_values_never_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        _row(1, [{"name": "x"}, ["Nested"], 7, None, "Danio rerio"]),
        _row(2, []),
        {"c0": _gene("NCBIGene:100003"), "c1": json.dumps({"not": "a list"})},
        {
            "c0": _gene("NCBIGene:100004"),
            "c1": json.dumps(["Z", "A"] + [f"S{n:02d}" for n in range(30)]),
        },
    ]
    monkeypatch.setattr(cypher_query_module, "execute_cypher", lambda *a, **k: (rows, len(rows)))
    output = await cypher_query(_RefusingHarness(), _input())

    assert [row.curie for row in output.rows] == [
        f"NCBIGene:{n}" for n in (100001, 100002, 100003, 100004)
    ]
    assert output.rows[0].fields["organism"] == "Danio rerio"
    assert "organism" not in output.rows[1].fields
    assert "organism" not in output.rows[2].fields
    capped = output.rows[3].fields["organism"].split(", ")
    assert len(capped) == MAX_FOLD_ITEMS and capped == sorted(capped)
    for row in output.rows:
        text = str(row.fields.get("organism", ""))
        assert "{" not in text and "[" not in text and "None" not in text
