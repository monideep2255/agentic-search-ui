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
    numbers_are_supported,
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

    def test_a_thousands_separator_does_not_break_grounding(self) -> None:
        """F-2.2-05, measured on the live loop rather than anticipated.

        A finding worth `15310` produced "BRCA1 has 15,310 ClinVar variants
        [1]", which is correct and well cited, and was stripped, so the user
        got a refusal for a question the graph had answered perfectly. A
        false reject costs the user the whole answer, so a gate's cost side
        needs testing as hard as its block side (LEARNINGS.md, 2026-08-01).
        """
        assert ground_claim("BRCA1 has 15,310 ClinVar variants", "15310")
        assert numbers_are_supported("BRCA1 has 15,310 ClinVar variants", "15310")
        assert normalize("15,310") == normalize("15310")

        findings = [_finding(1, "variant_count", "15310")]
        # The question is supplied because production always supplies it,
        # and the content check (F-2.2-A-01) draws on it: "ClinVar" and
        # "variants" are the user's own words, not the model's invention. A
        # fixture that omits the question is testing a configuration the
        # system never runs, which is the same trap build phase 2.1's first
        # premise gate fell into with `query_class`.
        result = run_grounding_pass(
            "BRCA1 has 15,310 ClinVar variants [1].",
            findings,
            question="How many ClinVar variants does BRCA1 have?",
        )
        assert result.grounded
        assert result.stripped_count == 0

    def test_the_separator_fix_does_not_equate_two_different_numbers(self) -> None:
        """The widening must be exactly one spelling of one number.

        If this ever fails, the lookarounds have been loosened and the
        separator rule is now eating punctuation between words, which would
        let real digits merge into numbers nobody stated.
        """
        assert not ground_claim("15,311 variants", "15310")
        assert not numbers_are_supported(
            "BRCA1 has 15,310 variants and 400 orthologs", "15310"
        )
        assert normalize("alpha, beta") == "alpha, beta"
        assert normalize("MedGen:C0346153") == "medgen:c0346153"

    def test_a_negation_never_grounds_as_support_for_what_it_denies(self) -> None:
        """F-2.2-A-01, confirmed exploitable by an adversary pass 2026-08-03.

        Section 8.2's substring rule answers "does this clause MENTION the
        cited value". Every string below mentions it and every one of them
        shipped, cited, with `stripped_count=0` and `trust_outcome="answer"`,
        until `claim_introduces_no_new_content` landed.

        A mutation test found this gate had NO test at all: neutering it to
        `return True` left the whole required-path suite green while four of
        five exploits sailed through. This is that test. Deleting the gate
        must fail the merge-blocking suite, or the gate is a comment.
        """
        findings = [_finding(1, "curie", "MedGen:C0346153", curie_fallback=True)]
        question = "Which diseases are associated with BRCA1?"
        for exploit in (
            "BRCA1 does not cause MedGen:C0346153",
            "There is no evidence that MedGen:C0346153 is linked to BRCA1",
            "MedGen:C0346153 may be curable with vitamin C",
            "MedGen:C0346153 is treated with pembrolizumab and olaparib",
            "Smith et al. disproved MedGen:C0346153",
            "BRCA1 confers a 97 percent lifetime risk of MedGen:C0346153",
            "Patients with MedGen:C0346153 should stop tamoxifen",
            "MedGen:C0346153 is Lynch syndrome",
        ):
            result = run_grounding_pass(f"{exploit} [1].", findings, True, question)
            assert result.refused, (
                f"a fabrication grounded as support for the record it names: "
                f"{exploit!r} survived with narrative {result.narrative!r}"
            )

    def test_a_framing_prefix_cannot_smuggle_an_uncited_claim(self) -> None:
        """F-2.2-A-02, confirmed CRITICAL by an adversary pass 2026-08-03.

        `FRAMING_OPENERS` exempts framing from needing a marker. Reading that
        as a prefix test let any fabricated sentence ship uncited by opening
        with two words, with the audit trail reporting nothing was removed.

        The exploit below shipped whole: four fabricated clinical claims, an
        invented ACMG classification, an invented count, and a
        treatment-discontinuation instruction, all with `stripped_count=0`
        and `trust_outcome="answer"`.
        """
        findings = [_finding(1, "curie", "MedGen:C0346153", curie_fallback=True)]
        question = "Which diseases are associated with BRCA1?"
        result = run_grounding_pass(
            "BRCA1 is associated with MedGen:C0346153 [1]. "
            "In summary, BRCA1 also causes Marfan syndrome and responds to "
            "high-dose vitamin C. "
            "Note: the ACMG classification for this variant is Pathogenic. "
            "These results show BRCA1 has 4102 pathogenic variants. "
            "Overall, patients should discontinue tamoxifen.",
            findings,
            True,
            question,
        )
        lowered = result.narrative.lower()
        for fabrication in (
            "marfan", "vitamin", "acmg", "pathogenic", "4102", "tamoxifen",
        ):
            assert fabrication not in lowered, (
                f"the framing exemption smuggled {fabrication!r} into an "
                f"uncited sentence: {result.narrative!r}"
            )
        assert result.stripped_count >= 4, (
            f"four fabricated sentences must be counted as stripped, not "
            f"silently kept; stripped_count={result.stripped_count}"
        )

    def test_contentless_framing_still_survives(self) -> None:
        """The cost side of the fix above, per LEARNINGS.md 2026-08-01.

        A gate needs its false-reject side tested as hard as its block side.
        Genuine framing asserts nothing and must not be stripped, or the fix
        for F-2.2-A-02 has simply deleted a legitimate sentence class.
        """
        findings = [_finding(1, "name", "alpha")]
        result = run_grounding_pass(
            "In summary, the following was found. First is alpha [1].",
            findings,
            True,
            "what is alpha",
        )
        assert result.grounded
        assert "In summary" in result.narrative
        assert result.stripped_count == 0

    def test_a_question_number_is_not_a_licence_for_every_claim(self) -> None:
        """F-2.2-A-03: the question whitelist was answer-wide.

        `numbers_are_supported` allows numbers the user themselves supplied,
        which is right for restating a question's subject. The first version
        granted that allowance to every clause in the answer, so seeding a
        number in the question licensed a fabricated statistic anywhere.
        """
        findings = [_finding(1, "curie", "MedGen:C0346153", curie_fallback=True)]
        result = run_grounding_pass(
            "MedGen:C0346153 affects 15310 patients with 87 percent "
            "mortality [1].",
            findings,
            True,
            "Which diseases are associated with BRCA1? Context: 15310 and 87.",
        )
        assert result.refused, (
            f"a fabricated statistic rode in on numbers seeded in the "
            f"question: {result.narrative!r}"
        )

    def test_the_fallback_link_stays_under_the_wire_cap_for_non_ascii(self) -> None:
        """F-2.2-A-06 / J-03. Percent-encoding is not length-preserving.

        Capping the TERM at 300 characters does not cap the LINK: one CJK
        character encodes to nine. A 300-character CJK term produced a
        2746-character link, over `TrustSignalPayload.fallback_link`'s
        512-char cap, which raised an unhandled ValidationError inside the
        refuse path itself, the one path whose job is to fail gracefully.

        A mutation test confirmed the existing ASCII-only length test cannot
        catch this: ASCII never forces the shrink loop to iterate.
        """
        for term in ("疾病" * 300, "😀" * 300, "BRCA1 " * 500):
            link = build_fallback_link(term)
            assert len(link) <= 512, f"link is {len(link)} chars for {term[:12]!r}"
            assert link.startswith(FALLBACK_BASE)
            # A link cut mid-escape is a dead link. Every escape must be a
            # complete three-character sequence.
            tail = link[len(FALLBACK_BASE):]
            for index, char in enumerate(tail):
                if char == "%":
                    assert index + 2 < len(tail), f"truncated escape: {tail[-8:]!r}"

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
