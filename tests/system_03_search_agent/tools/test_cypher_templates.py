"""Unit tests for `cypher_templates`: the code-chosen queries behind UI fix
set 10, item 10.1 (R34), "the same question returns the same sources every
time".

No model, no graph, no network. Everything here is a pure function of the
tool input and the entity bindings.

What each arm proves, and how it was shown to be able to fail (each was
run against a deliberate mutation of the module before it was kept; a
green arm that cannot go red is the failure this repository has shipped
more than once):

- Selection per shape: the flagship shapes map to the named template.
  Mutation: swapping the `diseases` and `variants` rows of `_HOPS` turned
  every one of these red.
- Fallback: an intent naming no shape on a non-lookup class, several
  anchors with three shapes, or two shapes on a multi-hop question, an
  unknown CURIE prefix, or a Gene mixed with an Article, all return None.
  A SINGLE anchor with several shapes takes the first-named shape on any
  class (the multi_hop "What variants cause disease in BRCA1?" arm).
  Mutation: returning the first matched shape unconditionally from
  `_resolve_shape` turned the several-anchor multi-hop arm red; gating the
  single-anchor case on query class again turned the multi_hop variants
  arm red; dropping the `anchor_label is None` branch turned the
  mixed-prefix arm red.
- ORDER BY: every record-returning template orders on the record id and
  the validator's injected LIMIT lands after it. Mutation: removing
  `ORDER BY` from `_hop_template` turned the arm red, and putting `LIMIT
  1` inside the template text made the validator's normalised form carry
  the LIMIT before the ORDER BY, which the arm also rejects.
- The validator gate: every template `all_template_examples` can produce
  passes `validate_cypher` and references only its bound names. Mutation:
  an untyped edge `-[]->` in one hop is rejected by the validator and the
  arm names which template.
- Determinism: selecting twice gives byte-identical Cypher. Mutation: a
  per-call `uuid` suffix on the record variable inside `_hop_template`
  turned it red. A suffix computed once at import did NOT, and that
  first attempt is recorded here so nobody re-runs it as proof: the arm
  catches a query that differs between calls, not one that differs
  between processes.
- The golden flagship questions route as intended, one row per question,
  so the next keyword edit that changes a route is a visible diff here
  rather than a surprise in a live run.
"""

from __future__ import annotations

import re

import pytest

from system_03_search_agent.tools import cypher_templates
from system_03_search_agent.tools.cypher_query import (
    _bound_param_names,
    _unanchored_returned_variables,
    _unknown_param_names,
    entity_param_bindings,
)
from system_03_search_agent.tools.cypher_schemas import CypherQueryInput
from system_03_search_agent.tools.cypher_templates import (
    CypherTemplate,
    all_template_examples,
    anchor_label_for,
    matched_shapes,
    select_template,
)
from system_03_search_agent.tools.cypher_validator import validate_cypher

BRCA1 = "NCBIGene:672"
BRCA2 = "NCBIGene:675"
BREAST_CANCER = "MedGen:C0346153"
PMID = "PMID:11237011"


def _select(
    intent: str, entities: list[str], query_class: str = "single_hop"
) -> CypherTemplate | None:
    tool_input = CypherQueryInput(
        query_intent=intent, query_class=query_class, target_entities=entities
    )
    return select_template(tool_input, entity_param_bindings(entities))


# ---------------------------------------------------------------------------
# Selection per shape.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("intent", "entities", "query_class", "expected_name", "expected_edge"),
    [
        (
            "Which diseases are associated with BRCA1?",
            [BRCA1],
            "single_hop",
            "gene_diseases_one",
            "gene_associated_with_condition",
        ),
        (
            "what diseases are linked to brca1?",
            [BRCA1],
            "single_hop",
            "gene_diseases_one",
            "gene_associated_with_condition",
        ),
        (
            "Welche Krankheiten sind mit dem Gen BRCA1 assoziiert?",
            [BRCA1],
            "single_hop",
            "gene_diseases_one",
            "gene_associated_with_condition",
        ),
        (
            "What variants cause it?",
            [BRCA1],
            "single_hop",
            "gene_variants_one",
            "is_sequence_variant_of",
        ),
        (
            "What variants cause disease in BRCA1?",
            [BRCA1],
            "single_hop",
            "gene_variant_diseases_one",
            "has_phenotype",
        ),
        # Measured on develop 2026-09-13: Think classifies this question
        # `multi_hop`, and the first cut declined two-shape questions on
        # that class, so the model wrote a Cypher over a variant-to-disease
        # edge the graph does not have and cited nine gene records. The
        # query class is a model's guess; with one gene bound the first-named
        # shape wins on every class.
        (
            "What variants cause disease in BRCA1?",
            [BRCA1],
            "multi_hop",
            "gene_variant_diseases_one",
            "has_phenotype",
        ),
        (
            "What variants cause disease in BRCA1?",
            [BRCA1],
            "exploratory",
            "gene_variant_diseases_one",
            "has_phenotype",
        ),
        (
            ("Give me everything NCBI knows about BRCA1: the gene record, associated "
             "conditions, clinically significant variants, and key literature."),
            [BRCA1],
            "multi_hop",
            "gene_variant_diseases_one",
            "has_phenotype",
        ),
        (
            "Which diseases are associated with BRCA1 variants?",
            [BRCA1],
            "single_hop",
            "gene_variant_diseases_one",
            "has_phenotype",
        ),
        ("gene lookup for BRCA1", [BRCA1], "lookup", "gene_record_one", None),
        # Decided from the user's chair, 2026-09-22: an exploratory question
        # naming an entity and no shape gets the record, not the model path
        # whose generated query timed out on every pass (G-039, G-033).
        ("Tell me about BRCA1", [BRCA1], "exploratory", "gene_record_one", None),
        (
            "I am a student. Explain in plain terms what the BRCA1 gene does and why it matters, with sources.",
            [BRCA1],
            "exploratory",
            "gene_record_one",
            None,
        ),
        (
            "Explain in plain terms what the BRCA1 gene does and why it matters, with sources.",
            [BRCA1],
            "lookup",
            "gene_record_one",
            None,
        ),
        (
            "Which diseases are associated with BRCA1 and BRCA2?",
            [BRCA1, BRCA2],
            "multi_hop",
            "gene_diseases_many",
            "gene_associated_with_condition",
        ),
        (
            "What are the known orthologs of TP53 in other species?",
            ["NCBIGene:7157"],
            "single_hop",
            "gene_orthologs_one",
            "orthologous_to",
        ),
        (
            "Which biological processes is BRCA1 actively involved in?",
            [BRCA1],
            "single_hop",
            "gene_processes_one",
            "participates_in",
        ),
        (
            "Where in the cell is the TP53 protein located?",
            ["NCBIGene:7157"],
            "single_hop",
            "gene_components_one",
            "located_in",
        ),
        (
            "Which organism does the gene CFTR belong to?",
            ["NCBIGene:1080"],
            "lookup",
            "gene_taxon_one",
            "in_taxon",
        ),
        (
            "Which papers in the graph mention the CFTR gene, and what do they cover?",
            ["NCBIGene:1080"],
            "single_hop",
            "gene_articles_one",
            "mentioned_in",
        ),
        (
            "Which genes are associated with cystic fibrosis?",
            ["MedGen:C0010674"],
            "single_hop",
            "disease_genes_one",
            "gene_associated_with_condition",
        ),
        (
            "What phenotypic features are associated with Marfan syndrome?",
            ["MedGen:C0024796"],
            "single_hop",
            "disease_phenotypes_one",
            "has_phenotype",
        ),
        (
            "What MeSH terms are assigned to PMID 11237011?",
            [PMID],
            "single_hop",
            "article_mesh_one",
            "has_mesh_annotation",
        ),
        (
            "How many genes in the graph are associated with breast cancer?",
            [BREAST_CANCER],
            "aggregate",
            "disease_genes_one_count",
            "gene_associated_with_condition",
        ),
        (
            "How many ClinVar variants does NCBIGene:672 have?",
            [BRCA1],
            "lookup",
            "gene_variants_one_count",
            "is_sequence_variant_of",
        ),
        (
            "Variants in GCK causing MODY",
            ["NCBIGene:2645", "MedGen:C0342276"],
            "single_hop",
            "gene_variant_disease_link",
            "has_phenotype",
        ),
        (
            "Is BRCA1 linked to breast cancer?",
            [BRCA1, BREAST_CANCER],
            "lookup",
            "gene_disease_link",
            "gene_associated_with_condition",
        ),
    ],
)
def test_known_shapes_select_the_named_template(
    intent: str,
    entities: list[str],
    query_class: str,
    expected_name: str,
    expected_edge: str | None,
) -> None:
    template = _select(intent, entities, query_class)
    assert template is not None, f"no template for {intent!r}"
    assert template.name == expected_name
    assert template.edge_label == expected_edge


def test_the_two_gene_disease_template_binds_both_genes_and_returns_both_endpoints() -> None:
    template = _select("Which diseases are associated with BRCA1 and BRCA2?", [BRCA1, BRCA2])
    assert template is not None
    assert "$e_NCBIGene_672" in template.cypher and "$e_NCBIGene_675" in template.cypher
    assert re.search(r"RETURN a, x ORDER BY a\.id, x\.id$", template.cypher)


def test_the_mixed_variants_template_binds_the_gene_and_the_disease() -> None:
    """Before 2026-09-14 the disease binding went unused, on the belief that
    the graph had no variant-to-disease edge. It has one (`has_phenotype`
    from a SequenceVariant, measured live), so the template now anchors
    both ends and folds the matched Disease records onto each variant."""
    template = _select("Variants in GCK causing MODY", ["NCBIGene:2645", "MedGen:C0342276"])
    assert template is not None
    assert template.name == "gene_variant_disease_link"
    assert "$e_NCBIGene_2645" in template.cypher
    assert "$e_MedGen_C0342276" in template.cypher
    assert template.fold == ("v", "xs", "clinvar_condition_ids")


# ---------------------------------------------------------------------------
# Fallback: None means the model path runs exactly as before.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("intent", "entities", "query_class"),
    [
        ("Tell me about BRCA1", [BRCA1], "single_hop"),
        # 2026-09-22: an exploratory no-shape question now takes the record
        # template (see the template table); the other three classes with
        # no shape still take the model path, each for a measured reason
        # (the single_hop case is index 0 of this table).
        ("Tell me about BRCA1", [BRCA1], "multi_hop"),
        (
            ("Which diseases are associated with BRCA1 and BRCA2 variants, and which "
             "papers mention them?"),
            [BRCA1, BRCA2],
            "multi_hop",
        ),
        ("Which diseases are associated with rs334?", ["ClinVar:17661"], "single_hop"),
        ("Which diseases are associated with BRCA1?", [BRCA1, PMID], "single_hop"),
        ("How many variants does BRCA1 have compared with BRCA2?", [BRCA1, BRCA2], "aggregate"),
        ("Compare NCBIGene:7157 and NCBIGene:672: how many diseases is NCBIGene:672 linked to?", [BRCA1, "NCBIGene:7157"], "lookup"),
        ("How many variants of GCK cause MODY?", ["NCBIGene:2645", "MedGen:C0342276"], "lookup"),
        ("Compare MLH1 and MSH2 in colorectal cancer risk.", ["NCBIGene:4292", "NCBIGene:4436", "MedGen:C0009402"], "multi_hop"),
        ("Which diseases are associated with BRCA1?", ["not-a-curie"], "single_hop"),
    ],
)
def test_ambiguous_or_unknown_shapes_fall_back_to_the_model(
    intent: str, entities: list[str], query_class: str
) -> None:
    assert _select(intent, entities, query_class) is None


def test_no_bindings_means_no_template() -> None:
    tool_input = CypherQueryInput(query_intent="x", query_class="lookup", target_entities=[])
    assert select_template(tool_input, {}) is None


def test_anchor_label_for_requires_one_known_label() -> None:
    assert anchor_label_for([BRCA1, BRCA2]) == "Gene"
    assert anchor_label_for([BREAST_CANCER, "MONDO:0007254"]) == "Disease"
    assert anchor_label_for([PMID]) == "Article"
    assert anchor_label_for([BRCA1, BREAST_CANCER]) is None
    assert anchor_label_for(["ClinVar:17661"]) is None
    assert anchor_label_for([]) is None
    assert anchor_label_for(["nocolon"]) is None


def test_matched_shapes_are_ordered_by_position_in_the_question() -> None:
    assert matched_shapes("What variants cause disease in BRCA1?", "Gene") == [
        "variants",
        "diseases",
    ]
    assert matched_shapes("Which diseases are associated with BRCA1 variants?", "Gene") == [
        "diseases",
        "variants",
    ]
    # A gene-anchored question is never routed by the disease anchor's
    # "gene" keyword, which would otherwise match nearly every question.
    assert matched_shapes("what the BRCA1 gene does", "Gene") == []


# ---------------------------------------------------------------------------
# Every template: validator, bindings, ORDER BY, determinism.
# ---------------------------------------------------------------------------


def test_every_template_passes_the_validator_and_binds_only_its_names() -> None:
    examples = all_template_examples()
    assert len(examples) >= 40, "the example set shrank; a shape was dropped"
    bindings = {"e_one": "NCBIGene:672", "e_two": "NCBIGene:675", "e_three": "MedGen:C0342276"}
    for template in examples:
        result = validate_cypher(template.cypher, 100)
        assert result.ok, f"{template.name}: {result.reason} {result.message}"
        normalized = result.normalized_cypher or ""
        assert _unknown_param_names(normalized, bindings) == [], template.name
        assert _bound_param_names(normalized, bindings), template.name
        assert _unanchored_returned_variables(normalized, bindings) == [], template.name
        assert normalized.rstrip().endswith("LIMIT 100"), template.name


def test_every_record_template_orders_by_the_record_id_before_its_limit() -> None:
    for template in all_template_examples():
        if template.name.endswith("_count") or template.name.endswith("_record_one"):
            # A count returns one row; a single record lookup returns one
            # row. Neither has an order to fix.
            continue
        normalized = validate_cypher(template.cypher, 25).normalized_cypher or ""
        order = re.search(r"ORDER BY ((?:[axv]\.id(?:, )?)+) LIMIT 25$", normalized)
        assert order is not None, f"{template.name}: {normalized}"
        assert "LIMIT" not in template.cypher, template.name


def test_selection_is_byte_identical_across_calls() -> None:
    first = _select("Which diseases are associated with BRCA1?", [BRCA1])
    second = _select("Which diseases are associated with BRCA1?", [BRCA1])
    assert first is not None and second is not None
    assert first.cypher == second.cypher
    assert first == second


def test_template_names_fit_the_output_field() -> None:
    for template in all_template_examples():
        assert len(template.name) <= cypher_templates.MAX_TEMPLATE_NAME_CHARS
