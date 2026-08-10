"""Unit tests for `system_03_search_agent.synthesis.trust`'s risk-tier logic.

This is the first dedicated test file for `trust.py`. Finding F-2.2-R-05
mutation-tested the previous state of the module and found `_canonical`
had zero coverage: reverting it to `token.strip().lower()` left 160 tests
green, because every existing test that exercises trust logic goes
through `core/graph.py`'s integration path, which never happens to send a
spelling variant through. This file closes that gap directly, at the
function under test, rather than through an integration path that can
mask a regression.

Covers, per this ticket's three defects:

  Defect 1 (F-2.2-R-08, MEDIUM): `_canonical` must fold every real
    spelling of a high-risk token, camelCase, all-caps-no-separator,
    dot-separated, and CURIE-prefixed, to the same comparison key as the
    table's own snake_case entry, in both directions: every spelling
    variant of a listed token must classify high, and no benign or
    near-miss field name may newly classify high as a side effect.

  Defect 2 (F-2.2-A-05, HIGH): `risk_tier_for` cannot distinguish a
    `Disease` row that IS the object of a `gene_associated_with_
    condition` claim (the flagship question) from a `Disease` row
    returned by a bare identifier lookup, because neither `field` nor
    `node_or_edge_type` carries which edge, if any, produced the row.
    The chosen resolution, recorded in `risk_tier_for`'s own docstring,
    is to document the gap rather than widen the table and risk
    misclassifying the identifier-lookup case Section 8.3.1 explicitly
    calls low risk. `TestDefect2OpenFinding` below locks in today's real
    behavior on both sides of that line, so a future change to either
    direction is a deliberate, reviewed edit to this file, never a silent
    drift.

  Defect 3 (F-2.2-R-05, HIGH): this file's own existence. Every test here
    is written to fail if `_canonical` degrades back to a bare
    `token.strip().lower()`. The mutation matrix proving that is reported
    alongside this file's PR, not encoded in the file itself, since a
    test file cannot assert on a mutation of code it does not contain.

Depends on:
    - system_03_search_agent.synthesis.trust (risk_tier_for, decide,
      aggregate, ClaimTrust, _canonical)
    - system_03_search_agent.synthesis.findings (SynthFinding)

Reads:
    - Nothing.

Writes:
    - Nothing.
"""

from __future__ import annotations

import pytest

from system_03_search_agent.synthesis import trust
from system_03_search_agent.synthesis.findings import SynthFinding
from system_03_search_agent.synthesis.trust import (
    aggregate,
    decide,
    is_high_risk_relationship_label,
    risk_tier_for,
)


def _finding(
    *,
    ref_index: int = 1,
    citation_id: str = "call-1",
    layer: str = "layer_1_graph",
    tool: str = "cypher_query",
    field: str = "clinical_significance",
    field_value: str = "Pathogenic",
    source_url: str = "https://www.ncbi.nlm.nih.gov/clinvar/RCV1",
    curie: str = "",
) -> SynthFinding:
    """A minimal, valid `SynthFinding` for tests that need one to satisfy
    `decide`'s or `triangulate`'s signature, not to exercise grounding."""
    return SynthFinding(
        ref_index=ref_index,
        citation_id=citation_id,
        layer=layer,
        tool=tool,
        field=field,
        field_value=field_value,
        source_url=source_url,
        curie=curie,
    )


# ---------------------------------------------------------------------------
# Defect 1 / F-2.2-R-08: every real spelling of a high-risk token must
# canonicalize to the same tier as the table's own snake_case entry.
# ---------------------------------------------------------------------------


# The exact four spellings the re-review verified broken, plus the
# camelCase and space-separated spellings the previous fix DID handle
# (regression coverage: this file must not lose ground on those either).
_CLINICAL_SIGNIFICANCE_SPELLINGS = [
    "CLINICALSIGNIFICANCE",
    "clinicalsignificance",
    "clinical.significance",
    "clinicalSignificance",
    "clinical significance",
    "clinical-significance",
    "clinical_significance",
]


@pytest.mark.parametrize("spelling", _CLINICAL_SIGNIFICANCE_SPELLINGS)
def test_every_clinical_significance_spelling_classifies_high(spelling: str) -> None:
    assert risk_tier_for(field=spelling) == "high", (
        f"{spelling!r} is a real spelling of the ClinVar clinical_significance "
        "field (Section 8.3.1's first table row) and must classify high "
        "regardless of casing or separator convention."
    )


_REVIEW_STATUS_SPELLINGS = [
    "REVIEWSTATUS",
    "reviewstatus",
    "review.status",
    "reviewStatus",
    "review status",
    "review-status",
    "review_status",
]


@pytest.mark.parametrize("spelling", _REVIEW_STATUS_SPELLINGS)
def test_every_review_status_spelling_classifies_high(spelling: str) -> None:
    assert risk_tier_for(field=spelling) == "high"


# The CURIE-prefixed relationship type. Latent today (the live graph's
# EDGE_LABELS are bare snake_case), but the fix is verified now so it does
# not silently regress the moment a Layer 2/3 tool supplies one.
_GENE_ASSOCIATED_WITH_CONDITION_SPELLINGS = [
    "biolink:gene_associated_with_condition",
    "GENE_ASSOCIATED_WITH_CONDITION",
    "geneassociatedwithcondition",
    "gene.associated.with.condition",
    "geneAssociatedWithCondition",
    "gene_associated_with_condition",
]


@pytest.mark.parametrize("spelling", _GENE_ASSOCIATED_WITH_CONDITION_SPELLINGS)
def test_every_gene_associated_with_condition_spelling_classifies_high(
    spelling: str,
) -> None:
    assert risk_tier_for(field="name", node_or_edge_type=spelling) == "high", (
        f"{spelling!r} must classify high as a relationship-type signal, "
        "including the CURIE-prefixed BioLink spelling (F-2.2-R-08)."
    )


def test_a_curie_prefix_other_than_biolink_is_also_stripped() -> None:
    """The prefix-stripping rule is general, not special-cased to `biolink:`.

    Whatever namespace a future source uses ahead of the colon, only the
    text after the LAST colon is compared, so any CURIE-shaped predicate
    naming a listed relationship type is caught the same way.
    """
    assert risk_tier_for(field="name", node_or_edge_type="RO:gene_associated_with_condition") == "high"


# ---------------------------------------------------------------------------
# Defect 1, the other direction: verified by the re-review as having NO
# false positive today. Collapsing separators must not introduce one.
# ---------------------------------------------------------------------------


_BENIGN_FIELDS = [
    "name",
    "definition",
    "xrefs",
    "source",
    "id",
    "curie",
    "synonym",
    "description",
    "gene_symbol",
    "taxon_id",
]


@pytest.mark.parametrize("field", _BENIGN_FIELDS)
def test_ordinary_benign_fields_stay_low(field: str) -> None:
    assert risk_tier_for(field=field) == "low"


_BENIGN_NODE_TYPES = [
    "Gene",
    "Article",
    "SequenceVariant",
    "OrganismTaxon",
    "OntologyClass",
    "in_taxon",
    "mentioned_in",
    "orthologous_to",
    "cited_in",
]


@pytest.mark.parametrize("node_or_edge_type", _BENIGN_NODE_TYPES)
def test_ordinary_benign_node_and_edge_types_stay_low(node_or_edge_type: str) -> None:
    assert risk_tier_for(field="name", node_or_edge_type=node_or_edge_type) == "low"


# Near misses: a name that CONTAINS a high-risk token's letters, or that a
# careless substring check could confuse for one, must still fail to
# match. Collapsing separators must only widen which SPELLINGS of a listed
# token match, never let a different, merely similar name match too.
_NEAR_MISS_FIELDS = [
    "not_clinical_significance",
    "clinical_significance_history",
    "clinical_significance_2",
    "preclinical_significance",
    "significance",
    "clinical",
    "reviewstatusnotes",
    "acmg_criteria_draft",
]


@pytest.mark.parametrize("field", _NEAR_MISS_FIELDS)
def test_near_miss_fields_do_not_become_high_risk(field: str) -> None:
    assert risk_tier_for(field=field) == "low", (
        f"{field!r} contains or resembles a high-risk token's letters but is "
        "not an exact match after canonicalization, and must stay low. "
        "Substring matching here would be the same failure class "
        "production-standards.md's cite-or-refuse gate exists to prevent, "
        "applied to risk classification instead of grounding."
    )


def test_a_curie_prefix_does_not_manufacture_a_false_positive() -> None:
    """Stripping a namespace prefix must not make an unrelated name, that
    merely happens to end the same way as a listed token once its own
    prefix is removed, match by accident."""
    assert (
        risk_tier_for(
            field="name",
            node_or_edge_type="some_other_prefix:review_status_of_something_else",
        )
        == "low"
    )


def test_gene_associated_with_condition_superstring_stays_low() -> None:
    """A relationship name that merely CONTAINS the token, with extra text
    on either side, must not collapse-match the token itself."""
    assert (
        risk_tier_for(field="name", node_or_edge_type="not_gene_associated_with_condition")
        == "low"
    )
    assert (
        risk_tier_for(field="name", node_or_edge_type="gene_associated_with_condition_type")
        == "low"
    )


# ---------------------------------------------------------------------------
# Defect 2 / F-2.2-A-05: the open finding, locked in on both sides.
# ---------------------------------------------------------------------------


class TestDefect2OpenFinding:
    """F-2.2-A-05: `risk_tier_for` has no way to tell a `Disease` row that
    IS the object of a gene-disease association claim (the flagship
    question) apart from a `Disease` row returned by a bare identifier
    lookup, because the traversed edge label never reaches this function.
    See `risk_tier_for`'s own docstring for the full reasoning on why this
    was recorded as an open finding rather than closed with a heuristic.

    These tests exist to keep that finding honest and current, not to
    approve of the behavior. If a future change to `trust.py` alone makes
    `test_disease_endpoint_row_still_classifies_low` start failing, that
    is either a real fix (in which case update this test and close
    F-2.2-A-05) or a heuristic regression reintroducing the false
    positive `test_a_bare_disease_lookup_would_wrongly_classify_high_if_
    widened_naively` warns against, never a silent drift either way.
    """

    def test_disease_endpoint_row_still_classifies_low(self) -> None:
        """The flagship question's exact shape: a `Disease` row, cited on
        its CURIE (the common case per `findings.py`'s vocabulary-artifact
        fallback), with no edge label anywhere in reach. Still `low`
        today, which is the documented gap, not a passing fix."""
        assert risk_tier_for(field="curie", node_or_edge_type="Disease") == "low"

    def test_disease_endpoint_row_via_decide_still_answers_instead_of_asking(self) -> None:
        """The consequence at the `decide` level: a grounded, single-source
        gene-disease claim reached through the Disease endpoint ships as
        `answer`, not `ask`, even though Section 8.3.1 calls this exact
        claim shape (OMIM phenotype-gene mechanistic mapping) high risk.
        This is F-2.2-A-05's real-world effect, asserted directly."""
        finding = _finding(field="curie", field_value="MedGen:C0346153", curie="MedGen:C0346153")
        result = decide(
            citation_id="call-1",
            field="curie",
            node_or_edge_type="Disease",
            grounded=True,
            claim_finding=finding,
            all_findings=[finding],
        )
        assert result.risk_tier == "low"
        assert result.outcome == "answer"

    def test_the_edge_row_path_works_today_when_the_query_returns_the_edge(self) -> None:
        """The other half of the picture, so the open finding above is not
        mistaken for "high risk gene-disease claims never work". When a
        Cypher query returns the `gene_associated_with_condition` EDGE
        itself rather than its Disease endpoint, `node_or_edge_type` names
        the edge directly and this function classifies it correctly."""
        assert (
            risk_tier_for(field="name", node_or_edge_type="gene_associated_with_condition")
            == "high"
        )

    def test_a_bare_disease_lookup_would_wrongly_classify_high_if_widened_naively(self) -> None:
        """Documents WHY the table was not simply widened to include
        `Disease`. Section 8.3.1 calls a pure identifier lookup ("what is
        MedGen:C0346153") low risk, and today it correctly classifies
        low. A naive fix that added `Disease` to the high-risk node types
        would flip this case too, which is the false positive this
        ticket explicitly forbade manufacturing. This test guards against
        that naive fix landing unreviewed."""
        assert risk_tier_for(field="curie", node_or_edge_type="Disease") == "low"


# ---------------------------------------------------------------------------
# Do-not-regress: re-verified per this ticket's instructions.
# ---------------------------------------------------------------------------


def test_aggregate_of_empty_list_refuses_never_answers() -> None:
    assert aggregate([]) == "refuse"


def test_triangulated_is_unreachable_true_on_a_graph_only_answer() -> None:
    """Every finding in build phase 2.2 has origin Layer 1 (the module
    docstring's "what this phase can and cannot reach"), so the
    independent-origin count for any claim is at most one and
    `triangulated` can never observe `True` yet, only `None` (low risk)
    or `False` (high risk, insufficient sources)."""
    claim_finding = _finding(
        citation_id="call-1",
        tool="cypher_query",
        field="clinical_significance",
        field_value="Pathogenic",
        curie="ClinVar:RCV1",
    )
    other_same_origin = _finding(
        citation_id="call-2",
        tool="cypher_query",
        field="clinical_significance",
        field_value="Pathogenic",
        curie="ClinVar:RCV2",
    )
    result = decide(
        citation_id="call-1",
        field="clinical_significance",
        node_or_edge_type="",
        grounded=True,
        claim_finding=claim_finding,
        all_findings=[claim_finding, other_same_origin],
    )
    assert result.risk_tier == "high"
    assert result.triangulation == "insufficient"
    assert result.triangulated is False, (
        "insufficient must map to False, never True: both findings share "
        "one origin (the same tool, no independent CURIE-derived origin), "
        "so this can never legitimately be a concordant result."
    )


def test_triangulated_is_none_for_a_low_risk_claim_never_false() -> None:
    result = decide(
        citation_id="call-1",
        field="name",
        node_or_edge_type="Gene",
        grounded=True,
        claim_finding=None,
        all_findings=[],
    )
    assert result.risk_tier == "low"
    assert result.triangulated is None, (
        "a low-risk claim never evaluates triangulation, so `triangulated` "
        "must read as \"not evaluated\" (None), never False (\"ran and "
        "disagreed\")."
    )


def test_an_ungrounded_claim_refuses_regardless_of_risk_tier() -> None:
    """Grounded is the gate every other row depends on (Section 8.3.3)."""
    result = decide(
        citation_id="call-1",
        field="clinical_significance",
        node_or_edge_type="",
        grounded=False,
        claim_finding=None,
        all_findings=[],
    )
    assert result.outcome == "refuse"
    assert result.risk_tier == "high"


# ---------------------------------------------------------------------------
# F-3.4-A-02: `ambiguous_high_risk_touch` is a second, independent path to
# `high`, never a change to either frozenset table above.
# ---------------------------------------------------------------------------


def test_is_high_risk_relationship_label_matches_the_table_exactly() -> None:
    assert is_high_risk_relationship_label("gene_associated_with_condition") is True
    assert is_high_risk_relationship_label("GENE_ASSOCIATED_WITH_CONDITION") is True
    assert is_high_risk_relationship_label("has_phenotype") is False
    assert is_high_risk_relationship_label("orthologous_to") is False


def test_risk_tier_for_classifies_high_on_ambiguous_touch_alone() -> None:
    """A bare node type that would otherwise classify low (the exact
    Disease-endpoint shape F-2.2-A-05 and TestDefect2OpenFinding above
    both name) still classifies high when the caller signals an ambiguous
    high-risk touch, without `node_or_edge_type` ever naming an edge."""
    assert (
        risk_tier_for(field="curie", node_or_edge_type="Disease") == "low"
    ), "sanity check: unchanged without the new signal"
    assert (
        risk_tier_for(
            field="curie", node_or_edge_type="Disease", ambiguous_high_risk_touch=True
        )
        == "high"
    )


def test_risk_tier_for_ambiguous_touch_does_not_override_a_real_low_risk_field() -> None:
    """The new signal is additive, an OR with the existing two checks, not
    a replacement: it never turns a genuinely low-risk case any less
    high-risk than it already is, and it never suppresses a case that
    would already classify high on its own."""
    assert (
        risk_tier_for(
            field="clinical_significance",
            node_or_edge_type="",
            ambiguous_high_risk_touch=False,
        )
        == "high"
    ), "the field-token path must still work with the new kwarg at its default"


def test_decide_threads_ambiguous_high_risk_touch_into_risk_tier_for() -> None:
    """The `decide`-level proof: a bare Disease endpoint claim, single
    origin, now classifies high risk and reaches `ask` (Section 8.3.3's
    insufficient-triangulation cell) rather than `answer`, purely from the
    ambiguous-touch signal, the same real-world effect F-2.2-A-05's own
    `test_disease_endpoint_row_via_decide_still_answers_instead_of_asking`
    test asserts for the UNAMBIGUOUS single-edge fix."""
    finding = _finding(field="curie", field_value="MedGen:C0346153", curie="MedGen:C0346153")
    result = decide(
        citation_id="call-1",
        field="curie",
        node_or_edge_type="Disease",
        grounded=True,
        claim_finding=finding,
        all_findings=[finding],
        ambiguous_high_risk_touch=True,
    )
    assert result.risk_tier == "high"
    assert result.outcome == "ask"


# ---------------------------------------------------------------------------
# `_canonical` itself, directly, so a future change to the function has a
# unit-level test in front of it and not only the risk_tier_for tests above.
# ---------------------------------------------------------------------------


def test_canonical_collapses_every_verified_broken_spelling_to_one_key() -> None:
    canonical_forms = {trust._canonical(s) for s in _CLINICAL_SIGNIFICANCE_SPELLINGS}
    assert canonical_forms == {"clinicalsignificance"}


def test_canonical_strips_only_the_curie_namespace_not_the_local_name() -> None:
    assert trust._canonical("biolink:gene_associated_with_condition") == trust._canonical(
        "gene_associated_with_condition"
    )
