"""Offline, deterministic probe of run_grounding_pass against candidate
plain-language sentence shapes, for the 2026-09-21 11.31 divergence report.

Does not start a server, does not call any model. Imports and runs the
shipped grounding module exactly as tests under
tests/system_03_search_agent/synthesis/ do.

Run with (from the repository root, using the repository's own
environment):

    PYTHONPATH=src python3 testing/Developer/reports/2026-09-21_11.31_divergence/probe_grounding.py

Every verdict below (SURVIVED / STRIPPED) comes from actually calling
run_grounding_pass, the real, unmodified production entry point. The three
sub-checks (ground_claim, numbers_are_supported,
claim_introduces_no_new_content) are ALSO called directly, on the same
claim text and the same finding, purely to report WHICH of the three gates
inside run_grounding_pass caused a strip, since run_grounding_pass itself
only returns an aggregate stripped_count. This diagnostic layer never
substitutes a guess for the real run_grounding_pass call; it explains it.
"""

from __future__ import annotations

import json

from system_03_search_agent.synthesis.findings import SynthFinding
from system_03_search_agent.synthesis.grounding import (
    _canonicalize_relational,
    _licensed_question_content,
    content_tokens,
    ground_claim,
    numbers_are_supported,
    run_grounding_pass,
)

# ---------------------------------------------------------------------------
# Fixture data
# ---------------------------------------------------------------------------

# Quoted verbatim from the repository's own test fixture:
# tests/system_03_search_agent/synthesis/test_pubmed_abstract_grounding.py,
# module-level `_ABSTRACT`. Real structured-abstract prose (not a synthetic
# stand-in), already used by the shipped test suite as an abstract finding's
# field_value.
ABSTRACT_TEXT = (
    "Background: BRCA1 encodes a tumor suppressor. Methods: we sequenced "
    "312 tumors. Results: pathogenic BRCA1 variants abolish homologous "
    "recombination in this cohort. Conclusion: carriers should be offered "
    "enhanced surveillance."
)
PMID = "30000003"
ABSTRACT_URL = f"https://pubmed.ncbi.nlm.nih.gov/{PMID}/"

ABSTRACT_FINDING = SynthFinding(
    ref_index=1,
    citation_id=f"pubmed-{PMID}-abstract",
    layer="layer3",
    tool="ncbi_efetch",
    field="abstract",
    field_value=ABSTRACT_TEXT,
    source_url=ABSTRACT_URL,
    entity_type="Publication",
    curie=f"PMID:{PMID}",
)

# A Layer 1 graph-record finding: a short, dense value naming a relation
# with one of the four relational synonyms _RELATIONAL_SYNONYMS folds
# together (grounding.py).
DISEASE_FINDING = SynthFinding(
    ref_index=2,
    citation_id="MedGen:C0346153-disease_association",
    layer="layer1",
    tool="cypher_query",
    field="disease_association",
    field_value="BRCA1 is associated with MedGen:C0346153",
    source_url="https://www.ncbi.nlm.nih.gov/medgen/C0346153",
    entity_type="Disease",
    curie="MedGen:C0346153",
)

QUESTION_WH_OPEN = "Which mechanism does BRCA1 disrupt in tumors?"
QUESTION_DISEASE_WH_OPEN = "Which diseases are associated with BRCA1?"


def _supporting_text(finding: SynthFinding, licensed_question: str) -> str:
    """Reproduces run_grounding_pass's own supporting_text assembly
    (grounding.py, inside run_grounding_pass, the `supporting_text = (...)`
    block), verbatim, so the diagnostic layer checks the same string
    run_grounding_pass actually builds.
    """
    return (
        f"{finding.field_value} {finding.field} "
        f"{finding.field.replace('_', ' ')} {finding.curie} "
        f"{finding.entity_type} {licensed_question}"
    )


def diagnose(claim_text: str, finding: SynthFinding, raw_question: str) -> dict:
    """Run the three sub-checks run_grounding_pass composes, directly, and
    report which one(s) fail and the exact offending content-token set for
    the allowlist check.
    """
    licensed_question = _licensed_question_content(raw_question)
    supporting_text = _supporting_text(finding, licensed_question)

    ground_ok = ground_claim(claim_text, finding.field_value)
    numbers_ok = numbers_are_supported(
        claim_text,
        finding.field_value,
        licensed_question,
        record_context=f"{finding.curie} {finding.entity_type}",
    )
    claim_tokens = _canonicalize_relational(content_tokens(claim_text))
    support_tokens = _canonicalize_relational(content_tokens(supporting_text))
    allowlist_ok = claim_tokens <= support_tokens
    offending = sorted(claim_tokens - support_tokens)

    return {
        "licensed_question": licensed_question,
        "supporting_text": supporting_text,
        "ground_claim_ok": ground_ok,
        "numbers_are_supported_ok": numbers_ok,
        "claim_introduces_no_new_content_ok": allowlist_ok,
        "offending_tokens": offending,
    }


def run_case(case: dict) -> dict:
    findings = case["findings"]
    question = case.get("question", "")
    result = run_grounding_pass(
        narrative=case["narrative"],
        synth_findings=findings,
        core_ask_required=False,
        question=question,
    )
    survived = (
        result.stripped_count == 0
        and not result.refused
        and bool(result.narrative.strip())
    )
    out = {
        "name": case["name"],
        "shape": case["shape"],
        "input_narrative": case["narrative"],
        "question": question,
        "output_narrative": result.narrative,
        "stripped_count": result.stripped_count,
        "claim_count": len(result.claims),
        "refused": result.refused,
        "verdict": "SURVIVED" if survived else "STRIPPED",
    }
    if "claim_text" in case and "primary_finding" in case:
        out["diagnosis"] = diagnose(case["claim_text"], case["primary_finding"], question)
    return out


CASES: list[dict] = [
    # --- Shape 1: restates the abstract's mechanism, everyday syntax, only
    # words present in the abstract itself.
    {
        "name": "shape1_restate_mechanism_abstract_words_only",
        "shape": "1",
        "narrative": "BRCA1 encodes a tumor suppressor [1].",
        "claim_text": "BRCA1 encodes a tumor suppressor",
        "findings": [ABSTRACT_FINDING],
        "primary_finding": ABSTRACT_FINDING,
    },
    {
        "name": "shape1b_restate_recombination_abstract_words_only",
        "shape": "1",
        "narrative": "Pathogenic BRCA1 variants abolish homologous recombination in this cohort [1].",
        "claim_text": "Pathogenic BRCA1 variants abolish homologous recombination in this cohort",
        "findings": [ABSTRACT_FINDING],
        "primary_finding": ABSTRACT_FINDING,
    },
    # --- Shape 2: everyday synonym for a technical word that IS in the
    # abstract ("tumor suppressor" -> "brake on cell growth").
    {
        "name": "shape2_synonym_brake_on_cell_growth",
        "shape": "2",
        "narrative": "BRCA1 acts as a brake on cell growth [1].",
        "claim_text": "BRCA1 acts as a brake on cell growth",
        "findings": [ABSTRACT_FINDING],
        "primary_finding": ABSTRACT_FINDING,
    },
    {
        "name": "shape2b_synonym_stops_tumors_forming",
        "shape": "2",
        "narrative": "BRCA1 helps stop tumors from forming [1].",
        "claim_text": "BRCA1 helps stop tumors from forming",
        "findings": [ABSTRACT_FINDING],
        "primary_finding": ABSTRACT_FINDING,
    },
    # --- Shape 3: a general definitional sentence with no source behind it.
    {
        "name": "shape3_general_definition_marked",
        "shape": "3",
        "narrative": "A gene is a stretch of DNA that carries instructions [1].",
        "claim_text": "A gene is a stretch of DNA that carries instructions",
        "findings": [ABSTRACT_FINDING],
        "primary_finding": ABSTRACT_FINDING,
    },
    {
        "name": "shape3b_general_definition_unmarked",
        "shape": "3",
        # No marker at all: tests the framing/no-narrative-only-claims path
        # rather than the allowlist path.
        "narrative": "A gene is a stretch of DNA that carries instructions.",
        "findings": [ABSTRACT_FINDING],
    },
    # --- Shape 4: draws on BOTH the user's question wording and the
    # abstract's/record's wording, via an open (wh-) question so its
    # content is licensed.
    {
        "name": "shape4_question_plus_abstract_wording",
        "shape": "4",
        "narrative": "Which mechanism does BRCA1 disrupt in tumors [1]?",
        "claim_text": "Which mechanism does BRCA1 disrupt in tumors",
        "findings": [ABSTRACT_FINDING],
        "question": QUESTION_WH_OPEN,
        "primary_finding": ABSTRACT_FINDING,
    },
    {
        "name": "shape4b_disease_question_plus_record_wording_same_order",
        "shape": "4",
        # Same subject/predicate order as the finding's own field_value, so
        # ground_claim's substring/equality step also passes, isolating the
        # allowlist question-licensing behaviour.
        "narrative": "BRCA1 is associated with MedGen:C0346153, which the question asks about [2].",
        "claim_text": "BRCA1 is associated with MedGen:C0346153, which the question asks about",
        "findings": [DISEASE_FINDING],
        "question": QUESTION_DISEASE_WH_OPEN,
        "primary_finding": DISEASE_FINDING,
    },
    {
        "name": "shape4c_disease_question_reordered_fails_ground_claim",
        "shape": "4",
        # Reordered relative to the finding's own field_value: demonstrates
        # that ground_claim (equality-or-substring) is a SEPARATE, stricter
        # gate than the content-token allowlist, and reordering alone can
        # strip a claim whose every word is licensed.
        "narrative": "MedGen:C0346153 is associated with BRCA1 [2].",
        "claim_text": "MedGen:C0346153 is associated with BRCA1",
        "findings": [DISEASE_FINDING],
        "question": QUESTION_DISEASE_WH_OPEN,
        "primary_finding": DISEASE_FINDING,
    },
    # --- Shape 5: one dense Layer 1 record finding, split into 2-3 short
    # one-idea sentences, each carrying the same marker.
    {
        "name": "shape5_split_two_sentences_same_marker",
        "shape": "5",
        "narrative": "BRCA1 is associated with a disease [2]. That disease is MedGen:C0346153 [2].",
        "findings": [DISEASE_FINDING],
    },
    {
        "name": "shape5b_split_reusing_finding_words_verbatim",
        "shape": "5",
        # Each sentence individually is an exact substring of the finding's
        # field_value ("BRCA1 is associated with MedGen:C0346153"), so this
        # isolates whether SPLITTING a dense finding into several short
        # verbatim fragments survives, independent of paraphrase.
        "narrative": "BRCA1 is associated with [2]. MedGen:C0346153 [2].",
        "findings": [DISEASE_FINDING],
    },
    # --- Shape 6: a relational synonym where the finding uses a different
    # one of the four (associated <-> related / linked / connected).
    {
        "name": "shape6a_related_vs_associated_synonym",
        "shape": "6",
        "narrative": "BRCA1 is related to MedGen:C0346153 [2].",
        "claim_text": "BRCA1 is related to MedGen:C0346153",
        "findings": [DISEASE_FINDING],
        "primary_finding": DISEASE_FINDING,
    },
    {
        "name": "shape6b_linked_vs_associated_synonym",
        "shape": "6",
        "narrative": "BRCA1 is linked to MedGen:C0346153 [2].",
        "claim_text": "BRCA1 is linked to MedGen:C0346153",
        "findings": [DISEASE_FINDING],
        "primary_finding": DISEASE_FINDING,
    },
    {
        "name": "shape6c_causes_vs_associated_not_in_synonym_set",
        "shape": "6",
        # `causes` is deliberately EXCLUDED from _RELATIONAL_SYNONYMS
        # (grounding.py docstring above _RELATIONAL_SYNONYMS): a stronger
        # clinical claim than the finding supports. Included to mark the
        # boundary of shape 6, not just its interior.
        "narrative": "BRCA1 causes MedGen:C0346153 [2].",
        "claim_text": "BRCA1 causes MedGen:C0346153",
        "findings": [DISEASE_FINDING],
        "primary_finding": DISEASE_FINDING,
    },
    # --- Shape 7: a framing opener with nothing content-bearing after it,
    # and a framing opener followed by a factual claim.
    {
        "name": "shape7a_framing_opener_nothing_after",
        "shape": "7",
        "narrative": "In summary, the following was found [1].",
        "findings": [ABSTRACT_FINDING],
    },
    {
        "name": "shape7b_framing_opener_then_factual_claim_unmarked",
        "shape": "7",
        "narrative": "In summary, BRCA1 encodes a tumor suppressor.",
        "findings": [ABSTRACT_FINDING],
    },
    {
        "name": "shape7c_framing_opener_then_factual_claim_marked",
        "shape": "7",
        "narrative": "In summary, BRCA1 encodes a tumor suppressor [1].",
        # NOTE: the real claim clause run_grounding_pass extracts here is
        # the WHOLE segment before the marker, "In summary, BRCA1 encodes
        # a tumor suppressor" (_clean_claim only lstrips ",;: " characters,
        # never the word "In summary"). An earlier draft of this probe used
        # claim_text="BRCA1 encodes a tumor suppressor" here, which made
        # the diagnosis disagree with the real run_grounding_pass verdict.
        # Fixed so the diagnostic checks the same string the real pass does.
        "claim_text": "In summary, BRCA1 encodes a tumor suppressor",
        "findings": [ABSTRACT_FINDING],
        "primary_finding": ABSTRACT_FINDING,
    },
    # --- Shape 8: adds a cautious hedge or an interpretation.
    {
        "name": "shape8a_hedge_this_suggests_plus_grounded_fact",
        "shape": "8",
        "narrative": "This suggests BRCA1 encodes a tumor suppressor [1].",
        "claim_text": "This suggests BRCA1 encodes a tumor suppressor",
        "findings": [ABSTRACT_FINDING],
        "primary_finding": ABSTRACT_FINDING,
    },
    {
        "name": "shape8b_hedge_may_be_higher_ungrounded_interpretation",
        "shape": "8",
        "narrative": "This suggests the risk may be higher [1].",
        "claim_text": "This suggests the risk may be higher",
        "findings": [ABSTRACT_FINDING],
        "primary_finding": ABSTRACT_FINDING,
    },
]


def main() -> None:
    results = [run_case(case) for case in CASES]
    print(json.dumps(results, indent=2))
    survived = sum(1 for r in results if r["verdict"] == "SURVIVED")
    stripped = sum(1 for r in results if r["verdict"] == "STRIPPED")
    print(f"\nTOTALS: {len(results)} cases, {survived} SURVIVED, {stripped} STRIPPED", flush=True)


if __name__ == "__main__":
    main()
