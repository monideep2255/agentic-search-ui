"""Tests for catalogue.py: the in-process function catalogue of every
existing action of the seven tools (build phase 8.2, card 9).
"""

from __future__ import annotations

from system_03_search_agent.tools.catalogue import (
    CATALOGUE,
    ToolAction,
    get_catalogue,
    resource_options,
)

_EXPECTED_TOOLS = {
    "cypher_query",
    "ncbi_efetch",
    "ncbi_dbsnp",
    "pubtator_annotate",
    "litvar2_lookup",
    "pathogen_detection",
    "clinicaltrials_search",
}

# One action per tool that has no Literal-discriminated action set
# (cypher_query, clinicaltrials_search, ncbi_dbsnp), and every action name
# for the four tools that do (ncbi_efetch, litvar2_lookup,
# pathogen_detection, pubtator_annotate).
_EXPECTED_ACTION_NAMES = {
    "cypher_query.query",
    "clinicaltrials_search.search",
    "ncbi_dbsnp.query",
    "ncbi_efetch.search",
    "ncbi_efetch.fetch",
    "ncbi_efetch.summary",
    "ncbi_efetch.link",
    "ncbi_efetch.coordinate_overlap",
    "ncbi_efetch.dataset_report",
    "ncbi_efetch.pubchem_property",
    "litvar2_lookup.variant_search",
    "litvar2_lookup.publications_lookup",
    "pathogen_detection.isolate_lookup",
    "pathogen_detection.cluster_snp_neighbors",
    "pathogen_detection.isolate_search",
    "pubtator_annotate.entity_lookup",
    "pubtator_annotate.annotate_publications",
}


def test_every_expected_action_is_catalogued() -> None:
    names = {action.name for action in CATALOGUE}
    assert names == _EXPECTED_ACTION_NAMES
    assert len(CATALOGUE) == 17


def test_every_tool_appears_at_least_once() -> None:
    tools = {action.tool for action in CATALOGUE}
    assert tools == _EXPECTED_TOOLS


def test_catalogue_is_sorted_by_name_and_fixed() -> None:
    names = [action.name for action in CATALOGUE]
    assert names == sorted(names)
    # Fixed in code: two reads return the identical tuple, not a
    # freshly-reordered one (prompt-cache-discipline.md's never-reorder
    # discipline, applied here even though this catalogue is not itself a
    # prompt today; see the module docstring).
    assert get_catalogue() == CATALOGUE


def test_every_action_has_a_valid_input_json_schema() -> None:
    for action in CATALOGUE:
        assert isinstance(action, ToolAction)
        assert action.name
        assert action.description
        schema = action.input_schema
        assert isinstance(schema, dict)
        assert schema.get("type") == "object"
        assert "properties" in schema
        assert action.timeout_s > 0
        assert action.rate_limit_pool is not None


def test_timeouts_match_tool_call_budgets_rule() -> None:
    by_name = {action.name: action for action in CATALOGUE}
    assert by_name["cypher_query.query"].timeout_s == 30.0
    assert by_name["ncbi_efetch.search"].timeout_s == 15.0
    assert by_name["ncbi_dbsnp.query"].timeout_s == 15.0
    assert by_name["pubtator_annotate.entity_lookup"].timeout_s == 15.0
    assert by_name["litvar2_lookup.variant_search"].timeout_s == 15.0
    assert by_name["pathogen_detection.isolate_lookup"].timeout_s == 60.0
    assert by_name["clinicaltrials_search.search"].timeout_s == 15.0


def test_resource_options_returns_the_seven_tool_names_sorted() -> None:
    options = resource_options()
    assert set(options) == _EXPECTED_TOOLS
    assert list(options) == sorted(options)
    assert len(options) == 7
    # Fits within DecisionRecord.options' max_length=12 bound, unlike the
    # finer-grained 17 action names would.
    assert len(options) <= 12
