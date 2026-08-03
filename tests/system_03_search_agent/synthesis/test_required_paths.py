"""The two required paths from Section 23: cite-or-refuse, zero-retrieval refusal.

These are not part of the milestone-gated eval-harness sampling. They are
deterministic unit tests, merge-blocking on every PR that touches the Write
step, a tool's output schema, or the provenance model. Section 23 names both
by name, and `production-standards.md`'s AI answer grounding gate is what
makes them non-negotiable.

Section 23's own instruction about this file, quoted because it is a
standing constraint rather than a one-time note:

    They never get deleted, narrowed, or weakened to make a change land
    faster; per goal-contracts.md, changing a verify surface so it passes is
    a failed change, not a completed one.

No live tool calls and no model call. Fixture `tool_result` payloads only,
per Section 23's "Feed the test a fixture set of tool_result payloads and
assert the Write step's output against them directly".

Depends on:
    - system_03_search_agent.synthesis.grounding
    - system_03_search_agent.synthesis.findings
    - system_03_search_agent.synthesis.refuse

Writes:
    - Nothing.
"""

from __future__ import annotations

import pytest

from system_03_search_agent.synthesis.findings import (
    SynthFinding,
    build_synth_findings,
    render_findings_block,
)
from system_03_search_agent.synthesis.grounding import (
    REFUSAL_TEXT,
    ground_claim,
    normalize,
    run_grounding_pass,
)
from system_03_search_agent.synthesis.refuse import (
    FALLBACK_BASE,
    FallbackLinkError,
    build_fallback_link,
    build_refusal_text,
)


def _finding(
    ref_index: int,
    field: str,
    field_value: str,
    *,
    curie_fallback: bool = False,
) -> SynthFinding:
    return SynthFinding(
        ref_index=ref_index,
        citation_id=f"call-1-{ref_index}",
        layer="layer_1_graph",
        tool="cypher_query",
        field=field,
        field_value=field_value,
        source_url=f"https://www.ncbi.nlm.nih.gov/gene/{600 + ref_index}",
        curie_fallback=curie_fallback,
    )


# ---------------------------------------------------------------------------
# test_cite_or_refuse_compliance (Section 23, required path 1)
# ---------------------------------------------------------------------------


class TestCiteOrRefuseCompliance:
    """Every claim maps to a real source by exact or substring match after
    normalization, or the response is the refusal. Never a fuzzy threshold.
    """

    def test_a_supported_claim_survives_with_its_marker(self) -> None:
        findings = [_finding(1, "name", "BRCA1 DNA repair associated")]
        result = run_grounding_pass(
            "BRCA1 is named BRCA1 DNA repair associated [1].", findings
        )
        assert result.grounded
        assert result.stripped_count == 0
        assert len(result.claims) == 1
        assert "[1]" in result.narrative

    def test_an_unsupported_claim_is_stripped_even_with_a_valid_marker(self) -> None:
        """The core defect this gate exists for: a real citation on a claim
        the cited finding does not support. Structurally perfect, and false.
        """
        findings = [_finding(1, "name", "BRCA1 DNA repair associated")]
        result = run_grounding_pass("BRCA1 causes Marfan syndrome [1].", findings)
        assert result.refused
        assert result.stripped_count == 1
        assert "Marfan" not in result.narrative

    def test_a_hallucinated_marker_is_dropped_with_its_clause(self) -> None:
        """Section 8.2 step 2: the marker names a finding this call never got."""
        findings = [_finding(1, "name", "BRCA1 DNA repair associated")]
        result = run_grounding_pass(
            "BRCA1 is named BRCA1 DNA repair associated [1]. "
            "It also causes hypertension [7].",
            findings,
        )
        assert result.grounded
        assert result.stripped_count == 1
        assert "[7]" not in result.narrative
        assert "hypertension" not in result.narrative

    def test_an_unmarked_factual_clause_is_stripped(self) -> None:
        """Section 8.1: no narrative-only claims. An uncited sentence is
        untraceable, and untraceable is not a state this system ships.
        """
        findings = [_finding(1, "name", "BRCA1 DNA repair associated")]
        result = run_grounding_pass(
            "BRCA1 is named BRCA1 DNA repair associated [1]. "
            "It is located on chromosome 17.",
            findings,
        )
        assert result.grounded
        assert result.stripped_count == 1
        assert "chromosome 17" not in result.narrative

    def test_framing_language_survives_without_a_marker(self) -> None:
        findings = [_finding(1, "name", "BRCA1 DNA repair associated")]
        result = run_grounding_pass(
            "In summary, the following was found. "
            "BRCA1 is named BRCA1 DNA repair associated [1].",
            findings,
        )
        assert result.grounded
        assert result.stripped_count == 0
        assert "In summary" in result.narrative

    def test_every_answer_with_no_surviving_claim_refuses(self) -> None:
        """Section 8.2 step 7: a thin narrative is discarded, not shipped."""
        findings = [_finding(1, "name", "BRCA1 DNA repair associated")]
        result = run_grounding_pass(
            "In summary, these results are shown above.", findings
        )
        assert result.refused
        assert result.narrative == ""
        assert result.claims == []

    def test_matching_is_exact_or_substring_and_never_similarity(self) -> None:
        """A near-miss must fail. If this ever passes, a fuzzy matcher has
        been introduced somewhere upstream, which is the specific thing
        `production-standards.md` forbids.
        """
        assert ground_claim("15310 variants", "15310")
        assert ground_claim("15310", "15310 variants")
        assert not ground_claim("15311 variants", "15310")
        assert not ground_claim("BRCA2", "BRCA1")
        assert not ground_claim("pathogenic", "benign")

    def test_an_empty_field_value_grounds_nothing(self) -> None:
        """The substring trap: `"" in anything` is True in Python, so an
        unguarded implementation lets a finding whose value normalized away
        ground every claim in the answer, invented ones included.
        """
        assert not ground_claim("BRCA1 causes cancer", "")
        assert not ground_claim("", "BRCA1")
        assert not ground_claim("...", "   ")

    def test_normalization_keeps_internal_punctuation_in_a_curie(self) -> None:
        """A CURIE's colon is load-bearing. Strip it and every CURIE claim
        in the system stops matching the CURIE it cites.
        """
        assert normalize("  MedGen:C0346153.  ") == "medgen:c0346153"
        assert ground_claim(
            "BRCA1 is associated with MedGen:C0346153", "MedGen:C0346153"
        )

    def test_two_facts_under_one_marker_lose_the_unsupported_half(self) -> None:
        """Section 8.1's one-finding-one-fact rule, enforced by consequence
        rather than by asking the model nicely.
        """
        findings = [_finding(1, "variant_count", "15310")]
        result = run_grounding_pass(
            "BRCA1 has 15310 variants and 400 orthologs [1].", findings
        )
        assert result.refused or "400 orthologs" not in result.narrative

    def test_markers_are_renumbered_without_gaps_after_stripping(self) -> None:
        """Section 9.4 stage 2. A gap means a stripped citation left its
        number behind, which renders as a chip pointing at nothing.
        """
        findings = [
            _finding(1, "name", "alpha"),
            _finding(2, "name", "beta"),
            _finding(3, "name", "gamma"),
        ]
        result = run_grounding_pass(
            "First is alpha [1]. Second is wrong [2]. Third is gamma [3].",
            findings,
        )
        assert result.stripped_count == 1
        assert "[1]" in result.narrative
        assert "[2]" in result.narrative
        assert "[3]" not in result.narrative
        assert [claim.finding.field_value for claim in result.claims] == [
            "alpha",
            "gamma",
        ]

    def test_citation_id_is_stable_across_renumbering(self) -> None:
        """Section 9.4: `display_index` is a rendering field, `citation_id`
        is the binding key. Renumbering must move one and not the other.
        """
        findings = [_finding(1, "name", "alpha"), _finding(2, "name", "beta")]
        result = run_grounding_pass(
            "Wrong claim here [1]. Second is beta [2].", findings
        )
        assert len(result.claims) == 1
        assert result.claims[0].finding.citation_id == "call-1-2"
        assert "[1]" in result.narrative


# ---------------------------------------------------------------------------
# test_zero_retrieval_refusal (Section 23, required path 2)
# ---------------------------------------------------------------------------


class TestZeroRetrievalRefusal:
    """Given zero relevant results, the Write step refuses and never
    fabricates. A binary assertion, not a sampled score.
    """

    def test_no_findings_means_no_grounded_claim_is_possible(self) -> None:
        result = run_grounding_pass(
            "BRCA1 is associated with hereditary breast cancer [1].", []
        )
        assert result.refused
        assert result.narrative == ""
        assert result.claims == []

    def test_an_empty_narrative_refuses_rather_than_answering_blank(self) -> None:
        assert run_grounding_pass("", [_finding(1, "name", "alpha")]).refused
        assert run_grounding_pass("   \n  ", [_finding(1, "name", "alpha")]).refused

    def test_zero_rows_produce_zero_findings(self) -> None:
        from system_03_search_agent.harness.coordinator_worker import Finding

        empty = Finding(
            call_id="call-1",
            tool="cypher_query",
            layer="layer_1_graph",
            source="structured_pass_through",
            structured_fields={"status": "empty", "row_count": 0, "rows": []},
            extracted_entities=None,
            normalized_ids=None,
            evidence_summary=None,
        )
        synth_findings, capped = build_synth_findings(
            [empty], lambda fields: (None, None, False)
        )
        assert synth_findings == []
        assert capped is False
        assert render_findings_block(synth_findings) == ""

    def test_the_refusal_string_is_the_exact_spec_string(self) -> None:
        """Pinned deliberately. Reword it and the eval harness's
        abstain-as-pass detection stops recognizing a correct refusal as a
        pass, which silently converts every honest refusal into a failure.
        """
        assert REFUSAL_TEXT == "I could not find information on this."

    def test_a_refusal_carries_a_working_ncbi_fallback_link(self) -> None:
        """Section 8.4: a refuse is never a dead end."""
        link = build_fallback_link("BRCA1 founder variant Ashkenazi")
        assert link.startswith(FALLBACK_BASE)
        assert link == (
            "https://www.ncbi.nlm.nih.gov/search/all/"
            "?term=BRCA1%20founder%20variant%20Ashkenazi"
        )
        assert "BRCA1 founder variant Ashkenazi" in build_refusal_text(
            "BRCA1 founder variant Ashkenazi"
        ).replace("%20", " ")

    def test_the_fallback_link_fully_encodes_every_reserved_character(self) -> None:
        """Section 8.4 step 3's `safe=""`. Leaving `&` or `/` unencoded lets
        a crafted question append its own parameter to the link a refusal
        hands the user.
        """
        link = build_fallback_link("a/b&c=d?e#f")
        assert link == "https://www.ncbi.nlm.nih.gov/search/all/?term=a%2Fb%26c%3Dd%3Fe%23f"
        assert "&" not in link.split("?term=", 1)[1]
        assert "/" not in link.split("?term=", 1)[1]

    def test_the_fallback_link_is_host_pinned_on_the_constructed_url(self) -> None:
        """Validate what was built, never trust that the building code got
        it right (`production-examples.md`'s redirect case).
        """
        import system_03_search_agent.synthesis.refuse as refuse_module

        original = refuse_module.FALLBACK_BASE
        try:
            refuse_module.FALLBACK_BASE = "https://evil.example/search?term="
            with pytest.raises(FallbackLinkError):
                refuse_module.build_fallback_link("BRCA1")
        finally:
            refuse_module.FALLBACK_BASE = original

    def test_a_long_question_cannot_blow_the_source_url_cap(self) -> None:
        link = build_fallback_link("BRCA1 " * 500)
        assert len(link) <= 512
