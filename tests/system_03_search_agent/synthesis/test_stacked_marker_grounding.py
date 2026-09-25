"""T-8.1-04 (2026-09-25): a clause naming two facts, one marker per fact,
both stacked at the clause's end.

Measured live: "What genes are associated with MODY?" carried the fallback
note ("the written summary of these records could not be verified against
them") on 5 of 6 runs on 2026-09-20, and the pattern replays here from a
captured live narrative
(`testing/Developer/reports/2026-09-25_phase_8.1/run1.log`). The model wrote
clauses shaped "GENE NAME ... DISEASE NAME [5][6]": one marker per fact,
Section 8.1's rule 2, but both stacked at the clause's end rather than each
immediately after its own fact. `run_grounding_pass` checked the whole
clause against ONLY the first marker's finding, which can license at most
half of a two-fact clause, so every such clause failed regardless of how
faithfully the model transcribed each fact, and `write_node` fell back to
its code-built listing on nearly every run.

The fix (`ground_claim_multi`, and the `stack_findings` gathering in
`run_grounding_pass`) is additive: a single-marker clause is checked exactly
as before, byte for byte. A clause whose markers stack at the end, with
nothing asserted in between, is checked against the UNION of the findings it
actually cites, one containment test per finding, never a fuzzy or partial
one. It cannot license a word the model did not already choose to cite,
because every finding in the union came from a marker the model itself
wrote in that same clause.

Depends on:
    - system_03_search_agent.synthesis.grounding
    - system_03_search_agent.synthesis.findings

Writes:
    - Nothing.
"""

from __future__ import annotations

from system_03_search_agent.synthesis.findings import SynthFinding
from system_03_search_agent.synthesis.grounding import (
    claim_introduces_no_new_content,
    ground_claim,
    ground_claim_multi,
    run_grounding_pass,
)


def _finding(
    field: str,
    field_value: str,
    *,
    curie: str = "",
    entity_type: str = "",
    ref_index: int = 1,
) -> SynthFinding:
    return SynthFinding(
        ref_index=ref_index,
        citation_id=f"call-1-{ref_index}",
        layer="layer_1_graph",
        tool="cypher_query",
        field=field,
        field_value=field_value,
        source_url=f"https://www.ncbi.nlm.nih.gov/gene/{600 + ref_index}",
        curie=curie,
        entity_type=entity_type,
    )


# ---------------------------------------------------------------------------
# ground_claim_multi: the pure function, in isolation
# ---------------------------------------------------------------------------


class TestGroundClaimMulti:
    def test_every_value_present_grounds(self) -> None:
        claim = "hepatocyte nuclear factor 4 alpha is linked to maturity-onset diabetes of the young type 1"
        assert ground_claim_multi(
            claim, ["hepatocyte nuclear factor 4 alpha", "maturity-onset diabetes of the young type 1"]
        )

    def test_one_missing_value_fails(self) -> None:
        # The disease half is present; the gene half is not (a different
        # gene's name is substituted). Every stacked finding's own value
        # must appear, not just one of them.
        claim = "glucokinase is linked to maturity-onset diabetes of the young type 1"
        assert not ground_claim_multi(
            claim, ["hepatocyte nuclear factor 4 alpha", "maturity-onset diabetes of the young type 1"]
        )

    def test_empty_claim_never_grounds(self) -> None:
        assert not ground_claim_multi("", ["glucokinase"])

    def test_a_blank_field_value_never_grounds(self) -> None:
        # Same guard `ground_claim` documents: an empty normalized value
        # must never license by vacuously being "in" everything.
        assert not ground_claim_multi("glucokinase causes something", ["glucokinase", "   "])

    def test_single_value_list_matches_ground_claim(self) -> None:
        # `run_grounding_pass` only ever calls `ground_claim_multi` when a
        # clause stacks more than one marker; a single-finding clause keeps
        # using `ground_claim` unchanged. This just proves the two agree
        # on the one-value case, so the new function is a genuine
        # generalization rather than a different rule in disguise.
        claim = "glucokinase [3]"
        assert ground_claim_multi(claim, ["glucokinase"]) == ground_claim(claim, "glucokinase")


# ---------------------------------------------------------------------------
# The synthetic two-fact, two-marker clause
# ---------------------------------------------------------------------------


class TestStackedTwoFactClause:
    """The exact shape measured live, reduced to its minimal reproduction:
    one clause naming a gene and the disease it is linked to, citing both
    findings with markers stacked at the clause's end."""

    def _gene_and_disease(self) -> list[SynthFinding]:
        return [
            _finding(
                "name",
                "hepatocyte nuclear factor 4 alpha",
                curie="NCBIGene:3172",
                entity_type="Gene",
                ref_index=5,
            ),
            _finding(
                "name",
                "Maturity-onset diabetes of the young type 1",
                curie="MedGen:C0271650",
                entity_type="Disease",
                ref_index=6,
            ),
        ]

    def test_stacked_markers_ground_both_facts(self) -> None:
        narrative = (
            "Hepatocyte nuclear factor 4 alpha (NCBIGene:3172) is linked to "
            "Maturity-onset diabetes of the young type 1 [5][6]."
        )
        result = run_grounding_pass(
            narrative,
            self._gene_and_disease(),
            question="What genes are associated with MODY?",
        )
        assert not result.refused
        assert len(result.claims) == 2
        cited = {c.finding.ref_index for c in result.claims}
        assert cited == {5, 6}

    def test_a_single_bare_marker_is_unaffected(self) -> None:
        # No stacking at all: the ordinary, pre-existing single-marker path,
        # unchanged. This is the regression guard for the "len(stack) == 1"
        # branch added alongside the multi-marker one.
        narrative = "Hepatocyte nuclear factor 4 alpha [5]."
        result = run_grounding_pass(
            narrative,
            self._gene_and_disease(),
            question="What genes are associated with MODY?",
        )
        assert not result.refused
        assert len(result.claims) == 1
        assert result.claims[0].finding.ref_index == 5

    def test_stacking_does_not_license_an_invented_word(self) -> None:
        # Adversarial: stacking two real findings must not license a THIRD,
        # uncited word. "causes" is not in either finding's value, the
        # question, or the field names, so the clause still fails.
        narrative = (
            "Hepatocyte nuclear factor 4 alpha (NCBIGene:3172) causes "
            "Maturity-onset diabetes of the young type 1 [5][6]."
        )
        result = run_grounding_pass(
            narrative,
            self._gene_and_disease(),
            question="What genes are associated with MODY?",
            core_ask_required=False,
        )
        assert not result.claims

    def test_stacking_does_not_let_one_value_borrow_the_others_number(self) -> None:
        # Adversarial: a clause naming finding 5's value plus an invented
        # number that belongs to neither stacked finding must still fail
        # `numbers_are_supported`, run over the UNION rather than skipped.
        narrative = (
            "Hepatocyte nuclear factor 4 alpha (NCBIGene:3172) is linked to "
            "Maturity-onset diabetes of the young type 1, affecting 4102 "
            "patients [5][6]."
        )
        result = run_grounding_pass(
            narrative,
            self._gene_and_disease(),
            question="What genes are associated with MODY?",
            core_ask_required=False,
        )
        assert not result.claims


# ---------------------------------------------------------------------------
# The exact failing case, replayed from a captured live run
# ---------------------------------------------------------------------------


def _mody_findings() -> list[SynthFinding]:
    """The 13 gene and disease findings behind "What genes are associated
    with MODY?", read verbatim off the code-built fallback narrative
    captured in `testing/Developer/reports/2026-09-25_phase_8.1/run1.log`
    (the pre-fix run, which fell back after both real Synth attempts
    grounded zero claims)."""
    return [
        _finding("name", "adaptor protein, phosphotyrosine interacting with PH domain and leucine zipper 1", curie="NCBIGene:26060", entity_type="Gene", ref_index=1),
        _finding("name", "Maturity-onset diabetes of the young type 14", entity_type="Disease", ref_index=2),
        _finding("name", "glucokinase", curie="NCBIGene:2645", entity_type="Gene", ref_index=3),
        _finding("name", "Maturity-onset diabetes of the young type 2", entity_type="Disease", ref_index=4),
        _finding("name", "hepatocyte nuclear factor 4 alpha", curie="NCBIGene:3172", entity_type="Gene", ref_index=5),
        _finding("name", "Maturity-onset diabetes of the young type 1", entity_type="Disease", ref_index=6),
        _finding("name", "Fanconi renotubular syndrome 4 with maturity-onset diabetes of the young", entity_type="Disease", ref_index=7),
        _finding("name", "pancreatic and duodenal homeobox 1", curie="NCBIGene:3651", entity_type="Gene", ref_index=8),
        _finding("name", "Maturity-onset diabetes of the young type 4", entity_type="Disease", ref_index=9),
        _finding("name", "potassium inwardly rectifying channel subfamily J member 11", curie="NCBIGene:3767", entity_type="Gene", ref_index=10),
        _finding("name", "Maturity-onset diabetes of the young type 13", entity_type="Disease", ref_index=11),
        _finding("name", "HNF1 homeobox A", curie="NCBIGene:6927", entity_type="Gene", ref_index=12),
        _finding("name", "Maturity-onset diabetes of the young type 3", entity_type="Disease", ref_index=13),
    ]


def test_replays_the_captured_mody_genes_failing_case() -> None:
    """Six standalone sentences, each shaped exactly as the ones that
    grounded live after the fix
    (`testing/Developer/reports/2026-09-25_phase_8.1/run2.log`, second
    Synth attempt: `[GROUNDING_RESULT] claims=10 stripped=7 refused=False`,
    where 10 of those 12 possible claims came from exactly this
    gene-then-disease, two-stacked-marker shape) and that grounded ZERO
    claims under the OLD single-finding check on the pre-fix run captured
    the same day
    (`[GROUNDING_RESULT] claims=0 stripped=13 refused=True` and
    `claims=0 stripped=18 refused=True` in `run1.log`, both Synth
    attempts). Confirmed directly: `ground_claim` alone passes the first
    clause below, since finding 5's short value ("hepatocyte nuclear
    factor 4 alpha") IS a substring of the longer two-fact clause. The
    OLD single-finding path's SECOND check is what actually rejected the
    pre-fix answer: `claim_introduces_no_new_content` against finding 5's
    supporting text alone does not license the disease half of the clause
    ("maturity-onset", "diabetes", "young", "type"), so a single-finding
    check still fails this exact clause.
    """
    sentences = [
        (
            "Hepatocyte nuclear factor 4 alpha (NCBIGene:3172) is "
            "associated with Maturity-onset diabetes of the young "
            "type 1 [5][6]."
        ),
        (
            "Glucokinase (NCBIGene:2645) is associated with "
            "Maturity-onset diabetes of the young type 2 [3][4]."
        ),
        (
            "HNF1 homeobox A (NCBIGene:6927) is associated with "
            "Maturity-onset diabetes of the young type 3 [12][13]."
        ),
        (
            "Pancreatic and duodenal homeobox 1 (NCBIGene:3651) is "
            "associated with Maturity-onset diabetes of the young "
            "type 4 [8][9]."
        ),
        (
            "Potassium inwardly rectifying channel subfamily J member 11 "
            "(NCBIGene:3767) is associated with Maturity-onset diabetes "
            "of the young type 13 [10][11]."
        ),
        (
            "Adaptor protein, phosphotyrosine interacting with PH domain "
            "and leucine zipper 1 (NCBIGene:26060) is associated with "
            "Maturity-onset diabetes of the young type 14 [1][2]."
        ),
    ]
    narrative = " ".join(sentences)
    findings = _mody_findings()

    first_clause = sentences[0][: sentences[0].index(" [5][6]")]
    hnf4a_value = next(f.field_value for f in findings if f.ref_index == 5)
    assert ground_claim(first_clause, hnf4a_value), (
        "ground_claim alone passes this clause; the old rejection came from "
        "claim_introduces_no_new_content, checked next"
    )
    assert not claim_introduces_no_new_content(first_clause, hnf4a_value), (
        "the single-finding content check must still fail this clause on "
        "its own, since the disease half is not licensed by finding 5 alone"
    )

    result = run_grounding_pass(
        narrative,
        findings,
        question="What genes are associated with MODY?",
    )
    assert not result.refused
    # Six gene-disease pairs, two findings cited each: 12 claims.
    assert len(result.claims) == 12
    cited = {c.finding.ref_index for c in result.claims}
    assert cited == {1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13}
