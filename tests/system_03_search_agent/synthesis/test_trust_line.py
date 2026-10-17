"""Card 8 (owner, 2026-10-16): the trust line names the databases behind it.

Every "Based on" line says which databases the cited pages come from, keyed
by `record_database`; "not yet confirmed" is gone; the clause "; their
values could not be compared" shows only on an `ask` from two or more
databases with a high-risk claim that came back `insufficient`. Wording
only: these tests never change a verdict, they pass verdicts in.
"""

from __future__ import annotations

from functools import cache
from itertools import combinations

import pytest

from system_03_search_agent.synthesis.findings import SynthFinding
from system_03_search_agent.synthesis.grounding import GroundedClaim
from system_03_search_agent.synthesis.trust import (
    _DATABASE_NAMES,
    ClaimTrust,
    answer_trust_line,
    record_database,
)

#: `DonePayload.trust_line` is capped at 200 characters (contracts/events.py).
_CAP = 200
_COMPARE = "; their values could not be compared"

_PAGES = {
    "medgen": "https://www.ncbi.nlm.nih.gov/medgen/C{n}",
    "omim": "https://omim.org/entry/{n}",
    "clinvar": "https://www.ncbi.nlm.nih.gov/clinvar/variation/{n}",
    "pubmed": "https://pubmed.ncbi.nlm.nih.gov/{n}/",
    "gene": "https://www.ncbi.nlm.nih.gov/gene/{n}",
    "trials": "https://clinicaltrials.gov/study/NCT{n}",
    "snp": "https://www.ncbi.nlm.nih.gov/snp/rs{n}",
}
_NAMES = {
    "medgen": "MedGen",
    "omim": "OMIM",
    "clinvar": "ClinVar",
    "pubmed": "PubMed",
    "gene": "NCBI Gene",
    "trials": "ClinicalTrials.gov",
    "snp": "dbSNP",
}


def _claims(spec: dict[str, int]) -> list[GroundedClaim]:
    """`{database: pages}` becomes that many distinct cited pages in each."""
    out: list[GroundedClaim] = []
    index = 0
    for database, pages in spec.items():
        for n in range(1, pages + 1):
            index += 1
            url = _PAGES[database].format(n=n) if database in _PAGES else database.format(n=n)
            finding = SynthFinding(
                ref_index=index,
                citation_id=f"c-{index}",
                layer="layer_1_graph",
                tool="cypher_query",
                field="name",
                field_value=f"record {index}",
                source_url=url,
                entity_type="Disease",
                curie="",
            )
            out.append(GroundedClaim(claim_text=finding.field_value, finding=finding))
    return out


def _trust(tier: str, triangulation: str, outcome: str) -> list[ClaimTrust]:
    return [ClaimTrust("c-1", tier, True, triangulation, outcome)]  # type: ignore[arg-type]


HIGH_INSUFFICIENT = _trust("high", "insufficient", "ask")
LOW = _trust("low", "insufficient", "ask")


# ---------------------------------------------------------------- the table


def test_refuse_and_nothing_grounded_have_no_line() -> None:
    assert answer_trust_line("refuse", [], _claims({"medgen": 1})) is None
    assert answer_trust_line("answer", [], []) is None


def test_flag_is_unchanged() -> None:
    line = answer_trust_line("flag", _trust("high", "discordant", "flag"), _claims({"medgen": 2}))
    assert line == "Sources disagree on at least one claim"


def test_confirmed_is_unchanged() -> None:
    from system_03_search_agent.synthesis.trust import trust_for_claims

    graph = _claims({"clinvar": 1})[0].finding
    snp = _claims({"snp": 1})[0].finding
    tools = ["cypher_query", "ncbi_dbsnp"]
    facts = [
        SynthFinding(
            ref_index=i + 1,
            citation_id=f"c-{i + 1}",
            layer="layer_1_graph",
            tool=tools[i],
            field="clinical_significance",
            field_value="Pathogenic",
            source_url=f.source_url,
            entity_type="Variant",
            curie="",
        )
        for i, f in enumerate([graph, snp])
    ]
    claims = [GroundedClaim(claim_text="x", finding=f) for f in facts]
    trusts = trust_for_claims(claims, facts)
    assert answer_trust_line("answer", trusts, claims) == "Confirmed by 2 independent databases"


def test_all_low_risk_names_one_database() -> None:
    line = answer_trust_line("answer", [], _claims({"medgen": 4}))
    assert line == "Based on 4 sources cited, all from MedGen"


def test_all_low_risk_names_two_databases() -> None:
    line = answer_trust_line("answer", [], _claims({"medgen": 3, "omim": 1}))
    assert line == "Based on 4 sources cited from MedGen and OMIM"


def test_one_source_reads_singular() -> None:
    assert answer_trust_line("answer", [], _claims({"medgen": 1})) == (
        "Based on 1 source cited, from MedGen"
    )


def test_high_risk_concordant_under_two_databases_has_no_clause() -> None:
    trusts = _trust("high", "concordant", "answer")
    line = answer_trust_line("answer", trusts, _claims({"clinvar": 2}))
    assert line == "Based on 2 sources cited, all from ClinVar"


def test_ask_one_database_has_no_clause() -> None:
    line = answer_trust_line("ask", HIGH_INSUFFICIENT, _claims({"clinvar": 4}))
    assert line == "Based on 4 sources cited, all from ClinVar"
    one = answer_trust_line("ask", HIGH_INSUFFICIENT, _claims({"medgen": 1}))
    assert one == "Based on 1 source cited, from MedGen"


def test_ask_two_databases_with_a_high_risk_insufficient_claim_shows_the_clause() -> None:
    line = answer_trust_line("ask", HIGH_INSUFFICIENT, _claims({"medgen": 9, "omim": 7}))
    assert line == "Based on 16 sources cited from MedGen and OMIM" + _COMPARE


def test_ask_two_databases_from_a_floor_only_has_no_clause() -> None:
    # A floor sets `ask` through `trust_outcome` while every claim's own
    # verdict is concordant (or there are no high-risk claims at all).
    concordant = _trust("high", "concordant", "answer")
    floored = answer_trust_line("ask", concordant, _claims({"medgen": 2, "omim": 1}))
    assert floored == "Based on 3 sources cited from MedGen and OMIM"
    no_claims = answer_trust_line("ask", [], _claims({"medgen": 2, "omim": 1}))
    assert no_claims == "Based on 3 sources cited from MedGen and OMIM"


def test_ask_two_databases_all_low_risk_has_no_clause() -> None:
    # Low-risk claims are marked `insufficient` by design (trust.py).
    line = answer_trust_line("ask", LOW, _claims({"medgen": 2, "omim": 1}))
    assert _COMPARE not in line
    assert line == "Based on 3 sources cited from MedGen and OMIM"


def test_four_or_more_databases_name_the_three_most_cited() -> None:
    spec = {"medgen": 5, "omim": 4, "clinvar": 3, "pubmed": 2, "gene": 1}
    line = answer_trust_line("answer", [], _claims(spec))
    assert line == "Based on 15 sources cited from MedGen, OMIM, ClinVar and 2 other databases"


def test_four_databases_say_one_other_database() -> None:
    spec = {"medgen": 5, "omim": 4, "clinvar": 3, "pubmed": 2}
    line = answer_trust_line("answer", [], _claims(spec))
    assert line == "Based on 14 sources cited from MedGen, OMIM, ClinVar and 1 other database"


def test_four_databases_with_a_failed_comparison_keep_the_clause() -> None:
    spec = {"medgen": 5, "omim": 4, "clinvar": 3, "pubmed": 2}
    line = answer_trust_line("ask", HIGH_INSUFFICIENT, _claims(spec))
    assert line.endswith("and 1 other database" + _COMPARE)


def test_an_unknown_database_counts_as_other_and_is_never_printed() -> None:
    line = answer_trust_line(
        "answer", [], _claims({"medgen": 2, "https://evil.example.com/x/{n}": 1})
    )
    assert line == "Based on 3 sources cited from MedGen and 1 other database"
    assert "evil" not in line


def test_only_unknown_databases_are_not_named() -> None:
    line = answer_trust_line("answer", [], _claims({"https://evil.example.com/x/{n}": 2}))
    assert line == "Based on 2 sources cited, from 1 other database"


# ---------------------------------------------------------------- properties


@cache
def _all_lines() -> tuple[str, ...]:
    lines: list[str] = []
    keys = list(_PAGES) + ["https://unknown.example.org/{n}"]
    states = [
        ("answer", []),
        ("answer", _trust("high", "concordant", "answer")),
        ("ask", HIGH_INSUFFICIENT),
        ("ask", LOW),
        ("ask", []),
        ("flag", _trust("high", "discordant", "flag")),
    ]
    for size in range(1, len(keys) + 1):
        for combo in combinations(keys, size):
            for pages in (1, 123):
                spec = {key: pages for key in combo}
                for outcome, trusts in states:
                    line = answer_trust_line(outcome, trusts, _claims(spec))  # type: ignore[arg-type]
                    assert line is not None
                    lines.append(line)
    return tuple(lines)


def test_every_line_stays_within_the_done_payload_cap() -> None:
    lines = _all_lines()
    assert len(lines) > 1000, "populate-check: the sweep must cover many combinations"
    assert max(map(len, lines)) <= _CAP


def test_only_the_confirmed_branch_starts_with_confirmed() -> None:
    # `_all_lines` never reaches the confirmed branch (it needs concordant
    # records from two databases, covered above), so none may start with it.
    for line in _all_lines():
        assert not line.startswith("Confirmed")
        if not line.startswith(("Based on ", "Sources disagree")):
            pytest.fail(line)


def test_no_branch_says_not_yet_confirmed_or_which_differ() -> None:
    for line in _all_lines():
        lowered = line.lower()
        assert "not yet confirmed" not in lowered
        assert "which differ" not in lowered


def test_the_clause_needs_ask_a_high_risk_insufficient_claim_and_two_databases() -> None:
    for line in _all_lines():
        if _COMPARE in line:
            assert line.startswith("Based on ")
            assert " from " in line and " all from " not in line


# ---------------------------------------------------------------- the sweep

_SAMPLE_URLS = {
    "ncbi.nlm.nih.gov/assembly": "https://www.ncbi.nlm.nih.gov/assembly/GCF_1",
    "ncbi.nlm.nih.gov/bioproject": "https://www.ncbi.nlm.nih.gov/bioproject/1",
    "ncbi.nlm.nih.gov/biosample": "https://www.ncbi.nlm.nih.gov/biosample/1",
    "ncbi.nlm.nih.gov/clinvar": "https://www.ncbi.nlm.nih.gov/clinvar/variation/1",
    "ncbi.nlm.nih.gov/datasets": "https://www.ncbi.nlm.nih.gov/datasets/gene/1",
    "ncbi.nlm.nih.gov/dbvar": "https://www.ncbi.nlm.nih.gov/dbvar/variants/1",
    "ncbi.nlm.nih.gov/gds": "https://www.ncbi.nlm.nih.gov/gds/1",
    "ncbi.nlm.nih.gov/gene": "https://www.ncbi.nlm.nih.gov/gene/672",
    "ncbi.nlm.nih.gov/gtr": "https://www.ncbi.nlm.nih.gov/gtr/tests/1",
    "ncbi.nlm.nih.gov/medgen": "https://www.ncbi.nlm.nih.gov/medgen/C1",
    "ncbi.nlm.nih.gov/mesh": "https://www.ncbi.nlm.nih.gov/mesh/1",
    "ncbi.nlm.nih.gov/nuccore": "https://www.ncbi.nlm.nih.gov/nuccore/1",
    "ncbi.nlm.nih.gov/pathogens": "https://www.ncbi.nlm.nih.gov/pathogens/isolates/1",
    "ncbi.nlm.nih.gov/pmc": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1/",
    "ncbi.nlm.nih.gov/pubchem": "https://pubchem.ncbi.nlm.nih.gov/compound/1",
    "ncbi.nlm.nih.gov/pubmed": "https://pubmed.ncbi.nlm.nih.gov/12345/",
    "ncbi.nlm.nih.gov/research/litvar2": "https://www.ncbi.nlm.nih.gov/research/litvar2/1",
    "ncbi.nlm.nih.gov/research/pubtator3": "https://www.ncbi.nlm.nih.gov/research/pubtator3/publication/1",
    "ncbi.nlm.nih.gov/snp": "https://www.ncbi.nlm.nih.gov/snp/rs1",
    "ncbi.nlm.nih.gov/sra": "https://www.ncbi.nlm.nih.gov/sra/1",
    "ncbi.nlm.nih.gov/taxonomy": "https://www.ncbi.nlm.nih.gov/taxonomy/1",
    "omim.org": "https://www.omim.org/entry/113705",
    "clinicaltrials.gov": "https://clinicaltrials.gov/study/NCT1",
}
_CURIE_KEYS = {key for key in _DATABASE_NAMES if "." not in key}


def _one(url: str, curie: str = "") -> SynthFinding:
    return SynthFinding(
        ref_index=1,
        citation_id="c-1",
        layer="layer_1_graph",
        tool="cypher_query",
        field="name",
        field_value="x",
        source_url=url,
        entity_type="Disease",
        curie=curie,
    )


def test_the_sample_pages_cover_every_page_key_in_the_table() -> None:
    assert set(_SAMPLE_URLS) == {key for key in _DATABASE_NAMES if "." in key}


@pytest.mark.parametrize(("key", "url"), sorted(_SAMPLE_URLS.items()))
def test_every_page_database_maps_to_a_proper_name(key: str, url: str) -> None:
    assert record_database(_one(url)) == key
    line = answer_trust_line("answer", [], [GroundedClaim("x", _one(url))])
    assert line == f"Based on 1 source cited, from {_DATABASE_NAMES[key]}"


@pytest.mark.parametrize("prefix", sorted(_CURIE_KEYS))
def test_every_curie_fallback_maps_to_a_proper_name(prefix: str) -> None:
    finding = _one("", curie=f"{prefix.upper()}:1")
    assert record_database(finding) == prefix
    line = answer_trust_line("answer", [], [GroundedClaim("x", finding)])
    assert line == f"Based on 1 source cited, from {_DATABASE_NAMES[prefix]}"


def test_display_names_are_proper_names_not_hosts() -> None:
    for name in _DATABASE_NAMES.values():
        assert name and "/" not in name and not name.startswith("www.")


def test_a_graph_row_and_a_live_fetch_of_one_database_name_it_once() -> None:
    claims = [
        GroundedClaim("a", _one("https://www.ncbi.nlm.nih.gov/clinvar/variation/1")),
        GroundedClaim(
            "b",
            SynthFinding(
                ref_index=2,
                citation_id="c-2",
                layer="layer_2_api",
                tool="ncbi_efetch",
                field="name",
                field_value="y",
                source_url="https://www.ncbi.nlm.nih.gov/clinvar/variation/2",
                entity_type="Variant",
                curie="",
            ),
        ),
    ]
    assert answer_trust_line("ask", HIGH_INSUFFICIENT, claims) == (
        "Based on 2 sources cited, all from ClinVar"
    )
