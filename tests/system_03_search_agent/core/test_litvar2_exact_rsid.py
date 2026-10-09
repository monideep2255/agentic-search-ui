"""Card 37 (T-8.9-04): a search for one rs id lists only that rs id's records.

LitVar2's autocomplete returns variants that only share the first digits of
the asked rs id (rs334348 for rs334). The shaping step keeps a match only
when its rs id equals the asked one exactly. Pure shaping, no network.
"""

from __future__ import annotations

from system_03_search_agent.core.graph import (
    _layer3_base_citation,
    _layer_tool_output_to_structured_fields,
    _rsids_in_text,
)
from system_03_search_agent.synthesis.findings import SynthFinding
from system_03_search_agent.tools.litvar2_lookup_schemas import (
    Litvar2LookupInput,
    Litvar2LookupOutput,
    Litvar2VariantMatch,
)


def _match(rsid: str) -> Litvar2VariantMatch:
    return Litvar2VariantMatch(
        litvar_id=f"litvar@{rsid}##",
        rsid=rsid,
        source_url=f"https://www.ncbi.nlm.nih.gov/snp/{rsid}",
        matched_on="Matched on rsid",
    )


def _output(*rsids: str) -> Litvar2LookupOutput:
    return Litvar2LookupOutput(
        status="ok", mode="variant_search", variant_matches=[_match(r) for r in rsids]
    )


def _input(query: str) -> Litvar2LookupInput:
    return Litvar2LookupInput.model_validate({"mode": "variant_search", "query": query})


def _rsids(shaped: dict) -> list[str]:
    return [row["fields"]["rsid"] for row in shaped["rows"]]


def test_near_misses_that_share_leading_digits_are_dropped() -> None:
    out = _output("rs334", "rs334348", "rs334353", "rs334558", "rs334773")
    shaped = _layer_tool_output_to_structured_fields("litvar2_lookup", out, _input("rs334"))
    assert _rsids(shaped) == ["rs334"]
    assert shaped["row_count"] == 1


def test_only_near_misses_gives_empty_not_error() -> None:
    out = _output("rs334348", "rs334353")
    shaped = _layer_tool_output_to_structured_fields("litvar2_lookup", out, _input("rs334"))
    assert shaped["status"] == "empty"
    assert shaped["rows"] == []
    assert shaped["error"] is None


def test_match_is_case_insensitive() -> None:
    out = _output("rs334", "rs3341")
    shaped = _layer_tool_output_to_structured_fields("litvar2_lookup", out, _input("RS334"))
    assert _rsids(shaped) == ["rs334"]


def test_non_rsid_query_is_not_filtered() -> None:
    out = _output("rs334", "rs334348")
    shaped = _layer_tool_output_to_structured_fields(
        "litvar2_lookup", out, _input("HBB sickle variant")
    )
    assert sorted(_rsids(shaped)) == ["rs334", "rs334348"]


def test_no_tool_input_is_not_filtered() -> None:
    out = _output("rs334", "rs334348")
    shaped = _layer_tool_output_to_structured_fields("litvar2_lookup", out)
    assert sorted(_rsids(shaped)) == ["rs334", "rs334348"]


def test_query_that_starts_with_an_rsid_but_is_not_a_bare_one_is_not_filtered() -> None:
    out = _output("rs334", "rs334348")
    shaped = _layer_tool_output_to_structured_fields("litvar2_lookup", out, _input("rs334 HBB"))
    assert sorted(_rsids(shaped)) == ["rs334", "rs334348"]


def test_uppercase_rsid_in_a_match_is_kept_for_a_lowercase_query() -> None:
    upper = Litvar2VariantMatch(
        litvar_id="litvar@rs334##",
        rsid="RS334",
        source_url="https://www.ncbi.nlm.nih.gov/snp/rs334",
        matched_on="Matched on rsid",
    )
    out = Litvar2LookupOutput(
        status="ok", mode="variant_search", variant_matches=[upper, _match("rs3341")]
    )
    shaped = _layer_tool_output_to_structured_fields("litvar2_lookup", out, _input("rs334"))
    assert _rsids(shaped) == ["RS334"]


def test_rsid_in_capitals_is_found_in_the_question() -> None:
    assert _rsids_in_text("What is RS334?") == ["rs334"]
    assert _rsids_in_text("What is Rs334 and rs334?") == ["rs334"]
    assert _rsids_in_text("What is rs334?") == ["rs334"]


def _citation_for(first: str, first_sig: list[str], second: str, second_sig: list[str], cited: str):
    def match(rsid: str, sig: list[str]) -> Litvar2VariantMatch:
        return Litvar2VariantMatch(
            litvar_id=f"litvar@{rsid}##",
            rsid=rsid,
            source_url=f"https://www.ncbi.nlm.nih.gov/snp/{rsid}",
            clinical_significance=sig,
            matched_on="Matched on rsid",
        )

    out = Litvar2LookupOutput(
        status="ok",
        mode="variant_search",
        source_url="https://www.ncbi.nlm.nih.gov/research/litvar2/?query=rs334",
        variant_matches=[match(first, first_sig), match(second, second_sig)],
    )
    finding = SynthFinding(
        ref_index=1,
        citation_id="c1",
        layer="layer_3_enrichment",
        tool="litvar2_lookup",
        field="clinical_significance",
        field_value="x",
        source_url=f"https://www.ncbi.nlm.nih.gov/snp/{cited}",
    )
    return _layer3_base_citation(finding, out, 1)


def test_citation_label_comes_from_the_cited_record_not_the_first_match() -> None:
    near_miss_first = _citation_for("rs334348", ["likely-benign"], "rs334", ["pathogenic"], "rs334")
    assert near_miss_first is not None
    assert near_miss_first.source_id == "rs334"
    assert near_miss_first.assertion_confidence == "asserted"
    # The reverse order: a hedged cited record behind an asserted near miss.
    reverse = _citation_for("rs334348", ["pathogenic"], "rs334", ["likely-benign"], "rs334")
    assert reverse is not None
    assert reverse.assertion_confidence == "hedged"
