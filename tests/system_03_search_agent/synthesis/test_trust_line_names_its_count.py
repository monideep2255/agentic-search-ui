"""Card 22 (owner, 2026-10-06): every total says what it counts.

One BRCA1 Researcher answer showed "18 sources" in the meta line, 17 in the
Sources heading and "Based on 17 sources" in the trust line. The owner chose
one count everywhere: every number that says "sources" counts distinct pages
under one key, and two links to one page (a trailing slash) count once.

These tests hold the backend half: the page key, the trust line's wording,
and the agreement with the frontend on the 2026-09-27 evidence. The cases
and the evidence live in one fixture the frontend tests read too
(`frontend/e2e/fixtures/card22_brca1_citations.json`), so the two page keys
are checked against the same inputs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from system_03_search_agent.synthesis.findings import SynthFinding
from system_03_search_agent.synthesis.grounding import GroundedClaim
from system_03_search_agent.synthesis.trust import (
    ClaimTrust,
    answer_trust_line,
    source_page_key,
)

_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "e2e"
    / "fixtures"
    / "card22_brca1_citations.json"
)
_DATA = json.loads(_FIXTURE.read_text(encoding="utf-8"))
_GENE = "https://www.ncbi.nlm.nih.gov/gene/672"
_HIGH_ASK = [ClaimTrust("c-1", "high", True, "insufficient", "ask")]


def _finding(index: int, url: str, *, curie: str = "MedGen:C1", layer: str = "layer_1_graph") -> SynthFinding:
    return SynthFinding(
        ref_index=index,
        citation_id=f"c-{index}",
        layer=layer,
        tool="cypher_query",
        field="name",
        field_value=f"record {index}",
        source_url=url,
        entity_type="Disease",
        curie=curie,
    )


def _claims(*findings: SynthFinding) -> list[GroundedClaim]:
    return [GroundedClaim(claim_text=f.field_value, finding=f) for f in findings]


@pytest.mark.parametrize(("url", "key"), [tuple(case) for case in _DATA["page_key_cases"]])
def test_page_key_drops_only_whitespace_and_trailing_slashes(url: str, key: str) -> None:
    assert source_page_key(url) == key


def test_page_key_of_none_is_empty() -> None:
    assert source_page_key(None) == ""


def test_a_trailing_slash_is_the_same_source() -> None:
    """The measured duplicate: the graph's gene link and the live Datasets
    gene link name one page. Mutation: drop `.rstrip("/")` and this reads 2."""
    line = answer_trust_line("answer", [], _claims(_finding(1, _GENE), _finding(2, _GENE + "/")))
    assert line == "Based on 1 source cited"


def test_a_query_string_is_not_guessed_away() -> None:
    """Narrow on purpose: a different query string can name a different
    record, so it stays a different source."""
    base = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/entity/autocomplete/"
    line = answer_trust_line(
        "answer", [], _claims(_finding(1, base + "?query=BRCA1"), _finding(2, base + "?query=TP53"))
    )
    assert line == "Based on 2 sources cited"


def test_a_record_without_a_link_is_never_merged() -> None:
    line = answer_trust_line("answer", [], _claims(_finding(1, ""), _finding(2, "")))
    assert line == "Based on 2 sources cited"


@pytest.mark.parametrize(
    ("outcome", "count", "expected"),
    [
        ("answer", 1, "Based on 1 source cited"),
        ("answer", 2, "Based on 2 sources cited"),
        ("ask", 1, "Based on 1 source cited, not yet confirmed"),
        ("ask", 3, "Based on 3 sources cited, not yet confirmed"),
    ],
)
def test_based_on_says_sources_cited(outcome: str, count: int, expected: str) -> None:
    findings = [_finding(n, f"https://www.ncbi.nlm.nih.gov/medgen/C{n}") for n in range(1, count + 1)]
    trusts = _HIGH_ASK if outcome == "ask" else []
    assert answer_trust_line(outcome, trusts, _claims(*findings)) == expected  # type: ignore[arg-type]


def test_confirmed_line_names_databases_and_keeps_its_count() -> None:
    """The "Confirmed by" number counts independent DATABASES, not pages, so
    its noun says so. Three pages from two databases still read 2."""
    trusts = [ClaimTrust("c-1", "high", True, "concordant", "answer")]
    claims = _claims(
        _finding(1, "https://www.ncbi.nlm.nih.gov/medgen/C1", curie="MedGen:C1"),
        _finding(2, "https://www.ncbi.nlm.nih.gov/medgen/C2", curie="MedGen:C2"),
        _finding(3, _GENE, curie="NCBIGene:672"),
    )
    assert answer_trust_line("answer", trusts, claims) == "Confirmed by 2 independent databases"


def _evidence_claims() -> list[GroundedClaim]:
    return _claims(
        *(
            _finding(
                citation["display_index"],
                citation["source_url"],
                curie=citation["source_id"],
                layer=citation["layer"],
            )
            for citation in _DATA["citations"]
        )
    )


def test_evidence_reconstruction_reproduces_the_old_screen() -> None:
    """Populate-check: the rebuilt citations give the 2026-09-27 numbers
    under the OLD exact-URL key, or the agreement test below proves nothing."""
    before = _DATA["evidence_before"]
    urls = [citation["source_url"] for citation in _DATA["citations"]]
    assert len(urls) == before["meta_sources"]
    assert len(set(urls)) == before["sources_heading"]


def test_evidence_trust_line_agrees_with_the_screen() -> None:
    """On the BRCA1 evidence the trust line now states the same 16 the
    frontend's meta line and Sources heading state (its own test,
    `AnswerScreen.card22.test.tsx`, reads this fixture too)."""
    after = _DATA["expected_after"]
    assert answer_trust_line("ask", _HIGH_ASK, _evidence_claims()) == after["trust_line"]
    assert after["trust_line"] == f"Based on {after['sources_cited']} sources cited, not yet confirmed"
