"""Item 11.34: a multi-sentence finding must reach the reader WITH its citation.

The defect, reproduced before this fix: `build_structured_fallback_
narrative` rendered a finding's body followed by ONE trailing marker, on the
documented assumption (its own former docstring) that a finding's body is
one sentence ending in one period. Since 2026-09-20 (commit `9cf8572`) that
assumption is false: a whole retrieved PubMed abstract, routinely several
sentences, is a single finding's `field_value`. `run_grounding_pass` splits
a narrative on sentence boundaries BEFORE it ever sees a marker, so a
three-sentence body with one trailing marker split into three unmarked
sentences (each stripped as an uncited claim) plus a fourth "sentence" that
was the marker alone with no text in front of it to ground. The finding
contributed nothing: no partial claim, no citation, and nothing told the
reader a fact had been dropped.

The fix: `build_structured_fallback_narrative` now splits a multi-sentence
`field_value` on the same sentence boundary `run_grounding_pass` itself
reads a narrative with (`grounding.split_into_sentences`), and marks every
resulting sentence with the finding's own marker, so each one is its own
groundable clause exactly as `run_grounding_pass` already expects a clause
to be. A single-sentence body is untouched: same rendering, same output.

Every arm below has a populate-check, and the mutation arm proves the
multi-sentence arm can actually go red: it directly exercises the PRE-FIX
one-marker-at-the-end shape and shows that shape losing the citation this
fix restores. An arm that cannot go red is not an arm.

Depends on:
    - system_03_search_agent.synthesis.findings (SynthFinding,
      build_structured_fallback_narrative)
    - system_03_search_agent.synthesis.grounding (run_grounding_pass)
"""

from __future__ import annotations

from system_03_search_agent.synthesis.findings import (
    SynthFinding,
    build_structured_fallback_narrative,
)
from system_03_search_agent.synthesis.grounding import run_grounding_pass

_MULTI_SENTENCE_ABSTRACT = (
    "BRCA1 functions as a tumour suppressor. It participates in DNA repair. "
    "Loss of function raises breast cancer risk."
)


def _multi_sentence_finding() -> SynthFinding:
    return SynthFinding(
        ref_index=1,
        citation_id="c1",
        layer="layer_2_api",
        tool="ncbi_efetch",
        field="abstract",
        field_value=_MULTI_SENTENCE_ABSTRACT,
        source_url="https://www.ncbi.nlm.nih.gov/pubmed/1",
        entity_type="Publication",
        curie="PMID:1",
    )


def _single_sentence_finding() -> SynthFinding:
    return SynthFinding(
        ref_index=2,
        citation_id="c2",
        layer="layer_1_graph",
        tool="cypher_query",
        field="name",
        field_value="Familial cancer of breast",
        source_url="https://www.ncbi.nlm.nih.gov/medgen/C1",
        entity_type="Disease",
        curie="MedGen:C1",
    )


# ---------------------------------------------------------------------------
# Arm 1: the multi-sentence finding is cited, not silently lost.
# ---------------------------------------------------------------------------


def test_a_multi_sentence_finding_survives_grounding_with_its_citation() -> None:
    multi = _multi_sentence_finding()
    single = _single_sentence_finding()
    findings = [multi, single]

    # populate-check: the fixture really does span more than one sentence,
    # or this arm would pass for a reason that has nothing to do with the
    # defect it exists to catch.
    sentence_count = _MULTI_SENTENCE_ABSTRACT.count(". ") + 1
    assert sentence_count >= 3, "populate-check: fixture must be multi-sentence"

    narrative = build_structured_fallback_narrative(findings)
    result = run_grounding_pass(narrative, findings, core_ask_required=False, question="")

    cited_ids = {claim.finding.citation_id for claim in result.claims}
    assert "c1" in cited_ids, (
        "the multi-sentence finding must contribute at least one grounded "
        f"claim, got claims={[c.claim_text for c in result.claims]}"
    )
    # Every sentence of the abstract is real, retrieved content, so the fix
    # is not just "one clause survives out of three": all three should.
    multi_claims = [c.claim_text for c in result.claims if c.finding.citation_id == "c1"]
    assert len(multi_claims) == 3, (
        f"expected all three sentences of the multi-sentence finding to "
        f"ground independently, got {multi_claims}"
    )
    assert result.stripped_count == 0, (
        f"nothing here should be stripped, got stripped_count={result.stripped_count}"
    )


def test_the_multi_sentence_finding_appears_in_the_rendered_narrative_text() -> None:
    """Not just counted as a claim: the reader-visible text carries it."""
    multi = _multi_sentence_finding()
    single = _single_sentence_finding()
    findings = [multi, single]

    narrative = build_structured_fallback_narrative(findings)
    result = run_grounding_pass(narrative, findings, core_ask_required=False, question="")

    assert "It participates in DNA repair" in result.narrative, result.narrative
    assert "Loss of function raises breast cancer risk" in result.narrative, result.narrative


# ---------------------------------------------------------------------------
# Arm 2: the single-sentence case is unchanged.
# ---------------------------------------------------------------------------


def test_a_single_sentence_finding_still_grounds_exactly_as_before() -> None:
    single = _single_sentence_finding()
    findings = [single]

    narrative = build_structured_fallback_narrative(findings)
    assert narrative == "Disease MedGen:C1, name: Familial cancer of breast [2].", narrative

    result = run_grounding_pass(narrative, findings, core_ask_required=False, question="")
    assert result.stripped_count == 0, result
    assert len(result.claims) == 1, result.claims
    assert result.claims[0].finding.citation_id == "c2"
    # `run_grounding_pass` renumbers surviving markers to a dense 1-based
    # `display_index` (Section 9.4 stage 2), so the sole surviving finding's
    # marker becomes [1] regardless of its original `ref_index` of 2.
    assert result.narrative == "Disease MedGen:C1, name: Familial cancer of breast [1]."


def test_a_curie_fallback_single_sentence_finding_is_still_byte_identical() -> None:
    """A second single-sentence shape (the identifier-only fallback render),
    since `render_finding_body` branches on `curie_fallback` and the fix
    must not disturb the branch this arm exercises either."""
    finding = SynthFinding(
        ref_index=1,
        citation_id="c9",
        layer="layer_1_graph",
        tool="cypher_query",
        field="curie",
        field_value="MedGen:C0346153",
        source_url="https://www.ncbi.nlm.nih.gov/medgen/C0346153",
        entity_type="Disease",
        curie="MedGen:C0346153",
        curie_fallback=True,
    )
    narrative = build_structured_fallback_narrative([finding])
    assert narrative == "Disease record MedGen:C0346153 [1].", narrative


# ---------------------------------------------------------------------------
# Arm 3 (mutation): the pre-fix shape really does lose the citation.
# ---------------------------------------------------------------------------


def _pre_fix_narrative(synth_findings: list[SynthFinding]) -> str:
    """The exact PRE-FIX rendering: one marker appended after the whole
    rendered body, regardless of how many sentences it contains. This is
    reconstructed here, not imported, because the production function no
    longer produces this shape; that is the point of the fix. Kept
    deliberately in lockstep with `findings.render_finding_body`, the one
    piece of the old renderer this arm still needs, so the mutation targets
    only the change this ticket made (marking every sentence) and nothing
    upstream of it.
    """
    from system_03_search_agent.synthesis.findings import render_finding_body

    return " ".join(
        f"{render_finding_body(finding)} [{finding.ref_index}]."
        for finding in synth_findings
    )


def test_mutation_the_pre_fix_single_trailing_marker_shape_loses_the_citation() -> None:
    """Proves arm 1 can go red: reverting to the pre-fix rendering (one
    marker at the end of the whole body) on the SAME fixture used above
    must NOT cite the multi-sentence finding. If this assertion ever starts
    failing, `build_structured_fallback_narrative` has stopped being a
    controlling change for the defect."""
    multi = _multi_sentence_finding()
    single = _single_sentence_finding()
    findings = [multi, single]

    narrative = _pre_fix_narrative(findings)
    result = run_grounding_pass(narrative, findings, core_ask_required=False, question="")

    cited_ids = {claim.finding.citation_id for claim in result.claims}
    assert "c1" not in cited_ids, (
        "populate-check inverted: the pre-fix shape was expected to lose "
        "the multi-sentence citation, but it survived, so this mutation "
        "arm is not exercising the defect it claims to"
    )
    assert result.stripped_count > 0, result


def test_mutation_the_fixed_narrative_differs_from_the_pre_fix_one() -> None:
    """A narrower, structural pin: the real renderer's output for a
    multi-sentence finding must not equal the old one-marker-at-the-end
    shape, or the fix could regress silently while this file's other arms
    happen to still pass for an unrelated reason."""
    multi = _multi_sentence_finding()
    findings = [multi]

    fixed = build_structured_fallback_narrative(findings)
    broken = _pre_fix_narrative(findings)
    assert fixed != broken, (
        "the fixed narrative must differ from the pre-fix single-marker "
        f"rendering; both were {fixed!r}"
    )
