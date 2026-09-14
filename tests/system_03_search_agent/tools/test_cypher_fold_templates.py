"""The variant-to-disease fold templates (2026-09-14), through the real tool.

No model, no network: `execute_cypher` is replaced by a fake that returns
raw AGE wire text shaped exactly as the live graph returned it on
2026-09-14 (`testing/Developer/reports/2026-09-14_variant_disease_detail/`),
including the `[{...}::vertex, {...}::vertex]` list column that
`collect(DISTINCT x)` produces.

What each arm proves, and the mutation that turns it red (each run by hand
against the module before the arm was kept):

- Selection: the gene "diseases caused by variants" question, the mixed
  "variants in GCK causing MODY" question and the disease "genes" question
  each pick their fold template. Mutation: dropping the
  `{"variants", "diseases"} <= set(shapes)` branch from `select_template`
  sends the first back to `gene_diseases_one` (red on the name).
- Parameterisation: no fold template carries a quoted literal, every `$`
  name it references is a bound entity, and `_build_params` binds exactly
  those. Mutation: writing the disease id into the Cypher text as a
  literal is rejected by the validator arm.
- The fold: each variant row carries `clinvar_condition_ids` with the
  CURIEs of the Disease vertices collected beside it, the Disease rows are
  emitted and cited as records of their own, and the list is capped at
  `MAX_FOLD_ITEMS`. Mutation: deleting the `_apply_fold` call in
  `_run_pipeline` leaves every variant row without the field (red).
- The list column: `parse_agtype` decodes a list of suffixed vertices.
  Mutation: removing `_INNER_SUFFIX_PATTERN.sub` makes the list decode to
  None and the Disease rows vanish (red on the Disease count).
- The fallback: when the gene-edge template returns no rows, the variant
  path runs and its name is reported. Mutation: dropping the
  `candidates.append(template.fallback)` line leaves the output `empty`.
- The model path is untouched: a template without a fold writes no field.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from system_03_search_agent.tools import cypher_query as cypher_query_module
from system_03_search_agent.tools.agtype import parse_agtype
from system_03_search_agent.tools.cypher_query import _build_params, cypher_query
from system_03_search_agent.tools.cypher_schemas import CypherQueryInput
from system_03_search_agent.tools.cypher_templates import (
    MAX_FOLD_ITEMS,
    all_template_examples,
    select_template,
)
from system_03_search_agent.tools.cypher_validator import validate_cypher

HNF1A = "NCBIGene:6927"
GCK = "NCBIGene:2645"
MODY3 = "MedGen:C1838100"
MODY2 = "MedGen:C0342277"


class _RefusingHarness:
    trace_id = "fold-trace"

    def __init__(self) -> None:
        self.calls: list[Any] = []

    def get_query_cost_usd(self, trace_id: str) -> float:
        return 0.0

    async def call_tier(self, tier: str, messages: list[dict[str, str]], **_: Any) -> Any:
        self.calls.append(messages)
        raise AssertionError("plan tier called on the template path")


def _vertex_text(label: str, curie: str, name: str, url: str, internal: int) -> str:
    return (
        json.dumps({"id": internal, "label": label, "properties": {"id": curie, "name": name, "source_url": url}})
        + "::vertex"
    )


def _variant(curie: str, internal: int) -> str:
    local = curie.split(":")[1]
    return _vertex_text(
        "SequenceVariant", curie, f"NM_000545.8(HNF1A):c.{local}G>A",
        f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{local}", internal,
    )


def _disease(curie: str, internal: int) -> str:
    local = curie.split(":")[1]
    return _vertex_text("Disease", curie, "OMIM", f"https://www.ncbi.nlm.nih.gov/medgen/{local}", internal)


def _list_column(items: list[str]) -> str:
    return "[" + ", ".join(items) + "]"


def _folded_rows() -> list[dict[str, str]]:
    """Two variants: the first linked to two diseases, the second to one of
    the same two (so the Disease record is deduplicated across rows)."""
    return [
        {
            "c0": _variant("ClinVar:1025247", 11),
            "c1": _list_column([_disease("MedGen:C0342276", 21), _disease("MedGen:C3661900", 22)]),
        },
        {
            "c0": _variant("ClinVar:1026109", 12),
            "c1": _list_column([_disease("MedGen:C3661900", 22)]),
        },
    ]


def _input(intent: str, entities: list[str], query_class: str = "single_hop") -> CypherQueryInput:
    return CypherQueryInput(query_intent=intent, query_class=query_class, target_entities=entities)


def _install(monkeypatch: pytest.MonkeyPatch, rows_by_call: list[list[dict[str, str]]]):
    executed: list[tuple[str, dict[str, Any] | None]] = []
    calls = iter(rows_by_call)

    def _fake_execute(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        executed.append((cypher, params))
        rows = next(calls, [])
        return rows, len(rows)

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute)
    return executed


# ---------------------------------------------------------------------------
# Selection and parameterisation.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("intent", "entities", "expected"),
    [
        ("What diseases are caused by variants in the HNF1A gene?", [HNF1A], "gene_variant_diseases_one"),
        ("What variants cause disease in BRCA1?", ["NCBIGene:672"], "gene_variant_diseases_one"),
        ("Variants in GCK causing MODY", [GCK, MODY3], "gene_variant_disease_link"),
        ("Variants in GCK causing MODY", [GCK, MODY3, MODY2], "gene_variant_disease_link"),
        ("What genes are associated with MODY?", [MODY3], "disease_genes_one"),
        ("What genes are associated with MODY?", [MODY3, MODY2], "disease_genes_many"),
    ],
)
def test_the_fold_shapes_select_their_template(intent: str, entities: list[str], expected: str) -> None:
    bindings = cypher_query_module.entity_param_bindings(entities)
    template = select_template(_input(intent, entities), bindings)
    assert template is not None and template.name == expected
    assert template.fold is not None, "a fold template must declare its fold"
    if expected.startswith("disease_genes"):
        assert template.fallback is not None and template.fallback.name.startswith("disease_variant_genes")


def test_single_shape_questions_keep_their_single_hop_template() -> None:
    bindings = cypher_query_module.entity_param_bindings(["NCBIGene:672"])
    diseases = select_template(_input("Which diseases are associated with BRCA1?", ["NCBIGene:672"]), bindings)
    variants = select_template(_input("What variants does BRCA1 have?", ["NCBIGene:672"]), bindings)
    assert diseases is not None and diseases.name == "gene_diseases_one" and diseases.fold is None
    assert variants is not None and variants.name == "gene_variants_one" and variants.fold is None


def test_every_fold_template_is_parameterised_and_binds_only_its_names() -> None:
    bindings = {"e_one": HNF1A, "e_two": MODY3, "e_three": MODY2}
    folded = [t for t in all_template_examples() if t.fold is not None]
    assert folded, "no fold template in the example set"
    for template in folded:
        assert not re.search(r"['\"]", template.cypher), f"{template.name} carries a quoted literal"
        assert re.search(r"^MATCH", template.cypher)
        referenced = set(re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", template.cypher))
        assert referenced and referenced <= set(bindings), template.name
        result = validate_cypher(template.cypher, 100)
        assert result.ok, f"{template.name}: {result.message}"
        params = _build_params(result.normalized_cypher or "", bindings)
        assert set(params) == referenced, template.name
        assert template.cypher.rstrip().endswith("ORDER BY " + template.fold[0] + ".id"), template.name


# ---------------------------------------------------------------------------
# The fold and the list column, through the tool.
# ---------------------------------------------------------------------------


def test_parse_agtype_decodes_a_list_of_suffixed_vertices() -> None:
    parsed = parse_agtype(_list_column([_disease("MedGen:C1", 1), _disease("MedGen:C2", 2)]))
    assert isinstance(parsed, list) and [item["properties"]["id"] for item in parsed] == ["MedGen:C1", "MedGen:C2"]
    # A single vertex and a bare scalar are decoded exactly as before.
    single = parse_agtype(_disease("MedGen:C1", 1))
    assert isinstance(single, dict) and single["properties"]["id"] == "MedGen:C1"
    assert parse_agtype("42") == 42 and parse_agtype('"text"') == "text"
    # Stated limitation, not a claim of immunity: a string VALUE that itself
    # contains `}::vertex,` is rewritten by the list branch. No NCBI title
    # carries that text; it is recorded here so nobody reads the pattern as
    # string-aware.
    tricky = json.dumps({"id": 3, "label": "Disease", "properties": {"id": "MedGen:C3", "name": "a}::vertex, b"}})
    parsed_tricky = parse_agtype("[" + tricky + "::vertex]")
    assert isinstance(parsed_tricky, list) and parsed_tricky[0]["properties"]["id"] == "MedGen:C3"


@pytest.mark.asyncio
async def test_variant_rows_carry_their_conditions_and_disease_rows_are_cited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executed = _install(monkeypatch, [_folded_rows()])
    output = await cypher_query(
        _RefusingHarness(), _input("What diseases are caused by variants in the HNF1A gene?", [HNF1A])
    )
    assert output.status == "ok" and output.template == "gene_variant_diseases_one"
    assert executed and executed[0][1] == {"e_NCBIGene_6927": HNF1A}
    variants = [row for row in output.rows if row.node_or_edge_type == "SequenceVariant"]
    diseases = [row for row in output.rows if row.node_or_edge_type == "Disease"]
    # POPULATE-CHECK: both kinds of row exist before their contents are asserted.
    assert len(variants) == 2 and len(diseases) == 2, [(r.node_or_edge_type, r.curie) for r in output.rows]
    by_curie = {row.curie: row for row in variants}
    assert by_curie["ClinVar:1025247"].fields["clinvar_condition_ids"] == ["MedGen:C0342276", "MedGen:C3661900"]
    assert by_curie["ClinVar:1026109"].fields["clinvar_condition_ids"] == ["MedGen:C3661900"]
    assert all(row.source_url and "medgen" in row.source_url for row in diseases)
    assert {row.curie for row in diseases} == {"MedGen:C0342276", "MedGen:C3661900"}


@pytest.mark.asyncio
async def test_the_fold_is_capped_at_max_fold_items(monkeypatch: pytest.MonkeyPatch) -> None:
    many = [_disease(f"MedGen:C{index}", 100 + index) for index in range(MAX_FOLD_ITEMS + 5)]
    _install(monkeypatch, [[{"c0": _variant("ClinVar:1", 1), "c1": _list_column(many)}]])
    output = await cypher_query(
        _RefusingHarness(), _input("What diseases are caused by variants in the HNF1A gene?", [HNF1A])
    )
    variant = next(row for row in output.rows if row.node_or_edge_type == "SequenceVariant")
    assert len(variant.fields["clinvar_condition_ids"]) == MAX_FOLD_ITEMS


@pytest.mark.asyncio
async def test_the_disease_genes_fallback_runs_only_when_the_gene_edge_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gene_row = {
        "c0": _vertex_text("Gene", GCK, "glucokinase", "https://www.ncbi.nlm.nih.gov/gene/2645", 31),
        "c1": _list_column([_disease(MODY2, 41)]),
    }
    executed = _install(monkeypatch, [[], [gene_row]])
    output = await cypher_query(_RefusingHarness(), _input("What genes are associated with MODY?", [MODY2]))
    assert len(executed) == 2, "the fallback must run after an empty primary"
    assert "is_sequence_variant_of" in executed[1][0] and "gene_associated_with_condition" in executed[0][0]
    assert output.status == "ok" and output.template == "disease_variant_genes_one"
    gene = next(row for row in output.rows if row.node_or_edge_type == "Gene")
    assert gene.fields["medgen_condition_ids"] == [MODY2]

    executed_again = _install(monkeypatch, [[gene_row], [gene_row]])
    output_again = await cypher_query(
        _RefusingHarness(), _input("What genes are associated with MODY?", [MODY2])
    )
    assert len(executed_again) == 1, "a primary with rows must not trigger the fallback"
    assert output_again.template == "disease_genes_one"


@pytest.mark.asyncio
async def test_a_template_without_a_fold_writes_no_field(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, [[{"c0": _disease("MedGen:C0342276", 21)}]])
    output = await cypher_query(_RefusingHarness(), _input("Which diseases are associated with BRCA1?", ["NCBIGene:672"]))
    assert output.template == "gene_diseases_one"
    assert all("clinvar_condition_ids" not in row.fields for row in output.rows)
