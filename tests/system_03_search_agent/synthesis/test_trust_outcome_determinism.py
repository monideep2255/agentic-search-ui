"""T-8.1-05 (2026-09-25): does `trust.py` give the same verdict on the same
evidence, every time?

Measured live and recorded 2026-09-23
(`testing/Developer/reports/2026-09-23_overnight/findings.md`): five runs of
"What diseases are caused by variants in the HNF1A gene?" against
BYTE-IDENTICAL Layer 1 results (86 sources, 63 Layer 1 citations, every run)
came back `trust_outcome` `flag` four times and `ask` once.

## What this file proves, and what it does not

`decide()`, `triangulate()` and `aggregate()` in `synthesis/trust.py` are
pure functions: no randomness, no wall-clock read, no set or dict whose
ITERATION ORDER can change the result (`buckets = {...}`'s membership and
`len()` do not depend on insertion order; `aggregate`'s `min()` picks by
severity value, never by position). `TestFiveIdenticalRuns` below computes
the full `trust_for_claims` -> `aggregate` pipeline five times from ONE
fixture and asserts byte-identical output every time. It passes, and it
was always going to pass: nothing in this module reads anything outside
its own arguments.

That is the finding, not a formality. Read live with
`testing/Developer/reports/2026-09-25_phase_8.1/diag_trust.py`, which
monkeypatches `core.graph.trust_for_claims` (the one real call site) to
print exactly what it receives: two live runs of the SAME question, same
develop code, gave `trust_for_claims` two DIFFERENT sets of claims
(`n_claims` and the citations among them varied), because the model's own
synthesized prose does not cite the same subset of the 63 available Layer 1
records on every run. `trust_for_claims` and `aggregate` are deterministic
FUNCTIONS OF THEIR INPUT; the input itself is not stable, because it is
built from which sentences the model's own synthesis grounds that run, and
`core/graph.py` then applies further floors on top of that
(`_apply_conflict_flags_to_claim_trusts` at line 8577, and the several
`aggregate([trust_outcome, "ask"])` completeness and cap floors at lines
10245, 10275, 10327 and 10346) before the `done` event's `trust_outcome`
is set. None of that lives in `trust.py`, and none of it is reachable from
this ticket's file fence (`synthesis/grounding.py`, `synthesis/trust.py`);
it is `core/graph.py`, owned by another builder this phase.

`TestSameClaimsIdenticalFindingsGiveSameTriangulation` goes one step
further than the plain determinism proof: it constructs the SHAPE the live
report's own numbers imply (a high-risk claim whose only same-field peer
from an independent origin is a genuine categorical mismatch, so
`triangulate` returns `discordant` and the answer floors at `flag`), and
shows that changing NOTHING about which finding is cited, only re-running
the same pipeline, never moves the verdict from `flag` to `ask`. The move
the live report measured therefore has to come from the CITED SET itself
changing between runs, not from `trust.py` computing two different answers
to the same question.

Depends on:
    - system_03_search_agent.synthesis.trust
    - system_03_search_agent.synthesis.grounding (GroundedClaim)
    - system_03_search_agent.synthesis.findings (SynthFinding)

Reads:
    - Nothing.

Writes:
    - Nothing.
"""

from __future__ import annotations

from system_03_search_agent.synthesis.findings import SynthFinding
from system_03_search_agent.synthesis.grounding import GroundedClaim
from system_03_search_agent.synthesis.trust import (
    ClaimTrust,
    aggregate,
    decide,
    trust_for_claims,
)


def _finding(
    field: str,
    field_value: str,
    *,
    curie: str,
    entity_type: str,
    tool: str = "cypher_query",
    ref_index: int = 1,
) -> SynthFinding:
    return SynthFinding(
        ref_index=ref_index,
        citation_id=f"call-1-{ref_index}",
        layer="layer_1_graph",
        tool=tool,
        field=field,
        field_value=field_value,
        source_url=f"https://www.ncbi.nlm.nih.gov/gene/{600 + ref_index}",
        curie=curie,
        entity_type=entity_type,
    )


def _claim(finding: SynthFinding, claim_text: str | None = None) -> GroundedClaim:
    return GroundedClaim(
        claim_text=claim_text or finding.field_value,
        finding=finding,
    )


class TestFiveIdenticalRuns:
    """`trust_for_claims` plus the answer-level `aggregate` computed five
    times from one fixture. Every run must agree, and this file states in
    its own module docstring which layer this actually tests (trust.py's
    pure logic) versus which layer produced the live-measured instability
    (core/graph.py's per-run cited set and floors, out of fence)."""

    def _fixture(self) -> tuple[list[GroundedClaim], list[SynthFinding]]:
        # A high-risk gene-disease claim (OMIM's own mechanistic mapping,
        # Section 8.3.1's row), plus an independent-origin same-field
        # finding whose value falls in a DIFFERENT bucket, so triangulation
        # genuinely returns "discordant" rather than "insufficient".
        graph_finding = _finding(
            "clinical_significance",
            "Pathogenic",
            curie="ClinVar:1043641",
            entity_type="SequenceVariant",
            tool="cypher_query",
            ref_index=1,
        )
        live_finding = _finding(
            "clinical_significance",
            "Benign",
            curie="ClinVar:1043641",
            entity_type="SequenceVariant",
            tool="ncbi_efetch",
            ref_index=2,
        )
        low_risk_finding = _finding(
            "name",
            "Maturity-onset diabetes of the young type 3",
            curie="MedGen:C1838100",
            entity_type="Disease",
            ref_index=3,
        )
        all_findings = [graph_finding, live_finding, low_risk_finding]
        claims = [_claim(graph_finding), _claim(live_finding), _claim(low_risk_finding)]
        return claims, all_findings

    def test_trust_for_claims_is_byte_identical_five_times(self) -> None:
        claims, all_findings = self._fixture()
        results = [
            trust_for_claims(claims, all_findings) for _ in range(5)
        ]
        first = [
            (t.citation_id, t.risk_tier, t.grounded, t.triangulation, t.outcome)
            for t in results[0]
        ]
        for later in results[1:]:
            assert [
                (t.citation_id, t.risk_tier, t.grounded, t.triangulation, t.outcome)
                for t in later
            ] == first

    def test_answer_level_trust_outcome_is_identical_five_times(self) -> None:
        claims, all_findings = self._fixture()
        outcomes = []
        for _ in range(5):
            claim_trusts = trust_for_claims(claims, all_findings)
            outcomes.append(aggregate([t.outcome for t in claim_trusts]))
        assert len(set(outcomes)) == 1, (
            f"trust_outcome varied across five identical-evidence runs: {outcomes}"
        )
        # The fixture's own shape: a discordant high-risk claim floors the
        # whole answer at "flag" (Section 8.3.4's most-restrictive-wins).
        assert outcomes[0] == "flag"


class TestSameClaimsIdenticalFindingsGiveSameTriangulation:
    """The `discordant` (-> flag) versus `insufficient` (-> ask) shape the
    live report actually measured, computed five times to show `decide`
    itself never drifts between the two for one fixed claim."""

    def _decide_hnf1a_shape(self) -> ClaimTrust:
        graph_finding = _finding(
            "clinical_significance",
            "Pathogenic",
            curie="ClinVar:1043641",
            entity_type="SequenceVariant",
            tool="cypher_query",
            ref_index=1,
        )
        live_finding = _finding(
            "clinical_significance",
            "Benign",
            curie="ClinVar:1043641",
            entity_type="SequenceVariant",
            tool="ncbi_efetch",
            ref_index=2,
        )
        return decide(
            citation_id="cq-hnf1a-1",
            field=graph_finding.field,
            node_or_edge_type=graph_finding.entity_type,
            grounded=True,
            claim_finding=graph_finding,
            all_findings=[graph_finding, live_finding],
        )

    def test_five_calls_agree_on_discordant_and_flag(self) -> None:
        results = [self._decide_hnf1a_shape() for _ in range(5)]
        assert all(r.triangulation == "discordant" for r in results)
        assert all(r.outcome == "flag" for r in results)

    def test_removing_the_independent_peer_moves_to_insufficient_and_ask(
        self,
    ) -> None:
        # This is the ONE thing that legitimately moves the verdict: a
        # DIFFERENT set of findings reaching `decide`, not `decide` itself
        # computing two answers for the same set. This is exactly the
        # mechanism named in the module docstring: which records the
        # model's own synthesis grounds varies run to run, so the "all
        # findings this claim can triangulate against" set is not the
        # constant the live report's "byte-identical evidence" framing
        # assumed it was.
        graph_finding = _finding(
            "clinical_significance",
            "Pathogenic",
            curie="ClinVar:1043641",
            entity_type="SequenceVariant",
            ref_index=1,
        )
        result = decide(
            citation_id="cq-hnf1a-1",
            field=graph_finding.field,
            node_or_edge_type=graph_finding.entity_type,
            grounded=True,
            claim_finding=graph_finding,
            all_findings=[graph_finding],  # the live-fetched peer is absent
        )
        assert result.triangulation == "insufficient"
        assert result.outcome == "ask"
