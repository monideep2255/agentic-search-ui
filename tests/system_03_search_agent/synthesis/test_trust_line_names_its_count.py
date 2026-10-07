"""Card 22 (owner, 2026-10-06): every total says what it counts.

One BRCA1 Researcher answer showed "18 sources" in the meta line, 17 in the
Sources heading and "Based on 17 sources" in the trust line. The owner chose
one count everywhere: every number that says "sources" counts distinct pages
under one key, and two links to one page (a trailing slash) count once.

These tests hold the backend half: the page key, the trust line's wording,
and the agreement with the frontend on the 2026-09-27 evidence. The fix
round of the same day adds the confirmed line's database count and every
other backend total a reader sees: the history rail after a reload, the
truncation note, the opening line and the command line's references. The cases
and the evidence live in one fixture the frontend tests read too
(`frontend/e2e/fixtures/card22_brca1_citations.json`), so the two page keys
are checked against the same inputs.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from system_03_search_agent.adapters.cli.render import Renderer
from system_03_search_agent.contracts.events import CitationPayload, Event
from system_03_search_agent.core.graph import _cited_page_count
from system_03_search_agent.feedback.history import _citation_count
from system_03_search_agent.synthesis.answer_layout import answer_summary_sentence
from system_03_search_agent.synthesis.findings import SynthFinding
from system_03_search_agent.synthesis.grounding import GroundedClaim
from system_03_search_agent.synthesis.trust import (
    ClaimTrust,
    answer_trust_line,
    record_database,
    source_page_key,
    trust_for_claims,
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


# ------------------------------------------------- the fix round, 2026-10-06
#
# "Confirmed by N independent databases" (A-22-01, A-22-02, J-22-03): N is the
# number of databases whose records state the confirmed fact, read off the
# record page, never off the tool that fetched it.

_CLINVAR = "https://www.ncbi.nlm.nih.gov/clinvar/variation/17661"
_LITVAR = "https://www.ncbi.nlm.nih.gov/research/litvar2/docsum?variant=rs80357906"


def _fact(
    index: int,
    url: str,
    *,
    tool: str = "cypher_query",
    curie: str = "",
    value: str = "Pathogenic",
    layer: str = "layer_1_graph",
) -> SynthFinding:
    """A record stating a variant's clinical significance."""
    return SynthFinding(
        ref_index=index,
        citation_id=f"c-{index}",
        layer=layer,
        tool=tool,
        field="clinical_significance",
        field_value=value,
        source_url=url,
        entity_type="Variant",
        curie=curie,
    )


def _confirmed(*high_ids: str) -> list[ClaimTrust]:
    return [ClaimTrust(cid, "high", True, "concordant", "answer") for cid in high_ids]


@pytest.mark.parametrize(
    ("url", "curie", "tool", "database"),
    [
        (_GENE, "NCBIGene:672", "cypher_query", "ncbi.nlm.nih.gov/gene"),
        (_GENE + "/", "", "ncbi_datasets", "ncbi.nlm.nih.gov/gene"),
        (_CLINVAR, "ClinVar:17661", "cypher_query", "ncbi.nlm.nih.gov/clinvar"),
        (_CLINVAR + "/", "", "ncbi_efetch", "ncbi.nlm.nih.gov/clinvar"),
        ("https://pubmed.ncbi.nlm.nih.gov/12345/", "", "ncbi_efetch", "ncbi.nlm.nih.gov/pubmed"),
        ("https://www.ncbi.nlm.nih.gov/pubmed/12345", "", "ncbi_efetch", "ncbi.nlm.nih.gov/pubmed"),
        (_LITVAR, "", "litvar2_lookup", "ncbi.nlm.nih.gov/research/litvar2"),
        (
            "https://www.ncbi.nlm.nih.gov/research/pubtator3/publication/123",
            "",
            "pubtator_annotate",
            "ncbi.nlm.nih.gov/research/pubtator3",
        ),
        ("https://www.omim.org/entry/113705", "", "ncbi_efetch", "omim.org"),
        ("https://omim.org/entry/113705", "", "ncbi_efetch", "omim.org"),
        ("https://clinicaltrials.gov/study/NCT00590109", "", "clinicaltrials_search", "clinicaltrials.gov"),
        ("", "MedGen:C1", "cypher_query", "medgen"),
        ("", "", "ncbi_efetch", ""),
    ],
)
def test_a_record_counts_by_its_database_not_its_tool(
    url: str, curie: str, tool: str, database: str
) -> None:
    """A graph row and a live fetch of one database name the same database;
    a record with neither a page nor a CURIE names none, never its tool."""
    assert record_database(_fact(1, url, tool=tool, curie=curie)) == database


def test_confirmed_counts_only_the_databases_that_state_the_fact() -> None:
    """A-22-02, J-22-03 probe (a): one fact two databases agree on, beside
    three low-risk records about other things, read "Confirmed by 5". Two
    databases agree. Mutation: count every claim's database again and this
    reads 5."""
    claims = _claims(
        _fact(1, _CLINVAR, curie="ClinVar:17661"),
        _fact(2, _LITVAR, tool="litvar2_lookup", layer="layer_3_enrichment"),
        _finding(3, "https://www.ncbi.nlm.nih.gov/medgen/C1"),
        _finding(4, _GENE, curie="NCBIGene:672"),
        _finding(5, "https://clinicaltrials.gov/study/NCT00590109", curie=""),
    )
    assert answer_trust_line("answer", _confirmed("c-1"), claims) == (
        "Confirmed by 2 independent databases"
    )


def test_a_graph_row_and_a_live_fetch_of_one_record_confirm_nothing() -> None:
    """A-22-01: the graph's ClinVar row and a live fetch of the same ClinVar
    record. The per-claim check compares tools, so it calls them concordant
    (pinned below, a separate card); the line must not repeat that as two
    databases. Mutation: key `record_database` by tool and this reads
    "Confirmed by 2 independent databases"."""
    graph = _fact(1, _CLINVAR, curie="ClinVar:17661")
    live = _fact(2, _CLINVAR + "/", tool="ncbi_efetch", layer="layer_2_api")
    claims = _claims(graph, live)
    trusts = trust_for_claims(claims, [graph, live])
    assert [t.triangulation for t in trusts] == ["concordant", "concordant"], (
        "populate-check: the per-claim verdict still compares tools; if this "
        "changes, the case below no longer reaches the line"
    )
    line = answer_trust_line("answer", trusts, claims, all_findings=[graph, live])
    assert line == "Based on 1 source cited, not yet confirmed"


def test_the_graph_gene_page_and_the_live_gene_page_are_one_database() -> None:
    """A-22-01 case 3 (J-22-03 probe b): `ncbigene` and `ncbi_datasets` were
    two keys for one database."""
    graph = _fact(1, _GENE, curie="NCBIGene:672")
    live = _fact(2, _GENE + "/", tool="ncbi_datasets", layer="layer_2_api")
    line = answer_trust_line("answer", _confirmed("c-1"), _claims(graph, live), all_findings=[graph, live])
    assert line == "Based on 1 source cited, not yet confirmed"


def test_agreement_is_read_from_the_whole_findings_pool() -> None:
    """The second database's record need not be cited in the prose: the
    pool `triangulate` compared against is the pool counted. Mutation: ignore
    `all_findings` and this reads "not yet confirmed"."""
    cited = _fact(1, _CLINVAR, curie="ClinVar:17661")
    corroborator = _fact(2, _LITVAR, tool="litvar2_lookup", layer="layer_3_enrichment")
    line = answer_trust_line(
        "answer", _confirmed("c-1"), _claims(cited), all_findings=[cited, corroborator]
    )
    assert line == "Confirmed by 2 independent databases"


def test_a_record_stating_a_different_value_does_not_count_as_agreeing() -> None:
    cited = _fact(1, _CLINVAR, curie="ClinVar:17661")
    other = _fact(2, _LITVAR, tool="litvar2_lookup", value="Benign")
    line = answer_trust_line("answer", _confirmed("c-1"), _claims(cited), all_findings=[cited, other])
    assert line == "Based on 1 source cited, not yet confirmed"


def test_with_several_confirmed_facts_n_is_what_every_one_of_them_has() -> None:
    """Fact one has three databases behind it and fact two has two. "Confirmed
    by 3" would overstate fact two, so N is the smaller count."""
    one = _fact(1, _CLINVAR, curie="ClinVar:17661")
    one_litvar = _fact(2, _LITVAR, tool="litvar2_lookup")
    one_omim = _fact(3, "https://omim.org/entry/113705", tool="ncbi_efetch")
    two = SynthFinding(
        ref_index=4,
        citation_id="c-4",
        layer="layer_1_graph",
        tool="cypher_query",
        field="review_status",
        field_value="Likely benign",
        source_url="https://www.ncbi.nlm.nih.gov/clinvar/variation/99",
        entity_type="Variant",
    )
    two_litvar = SynthFinding(**{**two.__dict__, "ref_index": 5, "citation_id": "c-5", "source_url": _LITVAR})
    pool = [one, one_litvar, one_omim, two, two_litvar]
    line = answer_trust_line("answer", _confirmed("c-1", "c-4"), _claims(one, two), all_findings=pool)
    assert line == "Confirmed by 2 independent databases"


# --------------------------------------- every other total counts pages too


def test_the_history_rail_count_after_a_reload_counts_pages() -> None:
    """J-22-05, A-22-06: the same search read "16 sources cited" live and "18
    sources" after a reload. The stored citations carry their links, so the
    reloaded count is their distinct pages. Mutation: `len(stored)` again and
    this reads 4."""
    stored = [
        {"source_url": _GENE},
        {"source_url": _GENE + "/"},
        {"source_url": "https://www.ncbi.nlm.nih.gov/medgen/C1"},
        {"source_url": ""},
    ]
    assert _citation_count(stored) == 3


def test_the_history_rail_never_merges_what_it_cannot_read() -> None:
    assert _citation_count([{"source_url": ""}, {"no_link": 1}, "not an object", 5]) == 4
    assert _citation_count([]) == 0
    assert _citation_count("abc") is None


def test_the_history_rail_count_agrees_with_the_trust_line_on_the_evidence() -> None:
    stored = [{"source_url": citation["source_url"]} for citation in _DATA["citations"]]
    assert _citation_count(stored) == _DATA["expected_after"]["sources_cited"]


def _payload(index: int, url: str) -> CitationPayload:
    return CitationPayload(
        citation_id=f"cid-{index}",
        display_index=index,
        source="NCBIGene",
        source_id="NCBIGene:672",
        source_url=url,
        layer="layer_1_graph",
        field="symbol",
        claim_text="x",
        evidence_kind="primary_assertion",
        assertion_confidence="asserted",
        population_ancestry_context=None,
        license="public_domain_us_gov",
    )


def test_the_truncation_count_counts_pages() -> None:
    """A-22-04: the helper both the truncation note and the "more to show"
    count call (their call sites are held by `core/test_graph.py`'s
    `test_truncation_note_and_more_to_show_count_record_pages_not_citations`)."""
    citations = [
        _payload(1, _GENE),
        _payload(2, _GENE + "/"),
        _payload(3, "https://www.ncbi.nlm.nih.gov/medgen/C1"),
    ]
    assert _cited_page_count(citations) == 2


def test_the_opening_line_counts_one_record_per_page() -> None:
    """A-22-03: "Found 2 gene records for BRCA1: BRCA1 [1] and BRCA1 [2]"
    above one gene card. Mutation: key `by_page` by exact URL again and this
    reads 2."""
    graph = SynthFinding(
        ref_index=1,
        citation_id="c1",
        layer="layer_1_graph",
        tool="cypher_query",
        field="symbol",
        field_value="BRCA1",
        source_url=_GENE,
        entity_type="Gene",
        curie="NCBIGene:672",
    )
    live = SynthFinding(
        ref_index=2,
        citation_id="c2",
        layer="layer_2_api",
        tool="ncbi_datasets",
        field="symbol",
        field_value="BRCA1",
        source_url=_GENE + "/",
        entity_type="Gene",
    )
    slots = {"c1": 1, "c2": 2}
    researcher = answer_summary_sentence(
        [graph, live], slots, "BRCA1", None, lambda finding: None, audience_depth="researcher"
    )
    assert researcher is not None
    assert "2 gene records" not in researcher, researcher
    assert "[2]" not in researcher, researcher


def test_the_command_line_lists_one_reference_per_page() -> None:
    """J-22-06, A-22-08: "Based on 16 sources cited" above 18 numbered
    references, the gene page three times. Mutation: print one line per
    citation again and this reads 18 lines."""
    out, err = io.StringIO(), io.StringIO()
    renderer = Renderer(out, err, operator=False)
    seq = 0

    def event(kind: str, payload: dict) -> Event:
        nonlocal seq
        seq += 1
        return Event.model_validate(
            {
                "type": kind,
                "version": "v1",
                "trace_id": "card22",
                "seq": seq,
                "ts": "2026-10-06T00:00:00Z",
                "payload": payload,
            }
        )

    ids = [f"cid-{c['display_index']}" for c in _DATA["citations"]]
    renderer.handle(event("guard", {"passed": True, "category": "ok", "reason": None}))
    renderer.handle(event("token", {"text": "BRCA1 claims. ", "marker_ids": ids}))
    for c in _DATA["citations"]:
        renderer.handle(
            event(
                "citation",
                {
                    "citation_id": f"cid-{c['display_index']}",
                    "display_index": c["display_index"],
                    "source": c["source"],
                    "source_id": c["source_id"],
                    "source_url": c["source_url"],
                    "layer": c["layer"],
                    "field": c["field"],
                    "claim_text": "x",
                    "evidence_kind": "primary_assertion",
                    "assertion_confidence": "asserted",
                    "population_ancestry_context": None,
                    "license": "public_domain_us_gov",
                },
            )
        )
    after = _DATA["expected_after"]
    renderer.handle(
        event(
            "done",
            {
                "total_cost_usd": 0,
                "total_tool_calls": 13,
                "elapsed_ms": 1,
                "trust_outcome": "ask",
                "trust_line": after["trust_line"],
            },
        )
    )
    text = out.getvalue()
    assert after["trust_line"] in text
    references = text.split("References:\n", 1)[1].splitlines()
    numbered = [line for line in references if line.startswith("[")]
    assert len(numbered) == after["sources_cited"], text
    gene = [line for line in numbered if "/gene/672" in line]
    assert gene == ["[1][6][9] NCBIGene - https://www.ncbi.nlm.nih.gov/gene/672/"], gene
    for marker in range(1, len(_DATA["citations"]) + 1):
        assert f"[{marker}]" in "".join(numbered), f"marker {marker} lost its reference"


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
