"""Section 8.3: the deterministic trust signal.

Decision E fixes the shape: a decision table over risk tier, grounded, and
triangulated, yielding one of answer, flag, ask, or refuse. No step is
model-judged, and every step in this module is a lookup or a comparison.

Depends on:
    - system_03_search_agent.synthesis.findings (SynthFinding)
    - system_03_search_agent.synthesis.grounding (GroundedClaim)

Reads:
    - Nothing.

Writes:
    - Nothing.

## What this phase can and cannot reach

Section 8.3.2 requires two INDEPENDENT-ORIGIN sources to triangulate, and
explicitly rules out counting a Layer 1 snapshot of a database and a Layer 2
live fetch of the same database as two. Build phase 2.2 is the graph-only
path: every finding has origin Layer 1, so the independent-source count is
at most one and triangulation always returns INSUFFICIENT.

That is not a stub, and the distinction matters. The rule is implemented in
full and evaluated for real; it is the DATA that is currently single-origin.
When build phase 3.4 extends provenance to Layers 2 and 3, concordant and
discordant become reachable with no change to this module beyond the origin
table below. The premise gate asserts the consequence directly: a graph-only
answer must never come back `triangulated=True`.

The practical effect on today's answers: a high-risk claim resting on the
graph alone yields `ask`, not `answer`. Decision E's "accepting some
over-flagging" is that trade taken on purpose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from system_03_search_agent.synthesis.findings import SynthFinding
from system_03_search_agent.synthesis.grounding import GroundedClaim

RiskTier = Literal["low", "high"]
TriangulationResult = Literal["concordant", "discordant", "insufficient"]
TrustOutcome = Literal["answer", "flag", "ask", "refuse"]

# Section 8.3.1's high-risk rows, expressed as the field names and edge
# predicates a Layer 1 row can actually carry. Matched case-insensitively
# against a finding's `field`, and against the `node_or_edge_type` the
# caller passes alongside it.
#
# Every entry traces to a specific Section 8.3.1 table row:
#   clinical_significance / review_status -> the ClinVar row
#   gene_associated_with_condition       -> the OMIM phenotype-gene row,
#                                           which is the graph's own
#                                           mechanistic gene-disease mapping
#   causes / contributes_to / treats     -> the extracted-relationship row
_HIGH_RISK_FIELD_TOKENS: frozenset[str] = frozenset(
    {
        "clinical_significance",
        "clinical_significance_ordered",
        "review_status",
        "acmg_criteria",
        "acmg_classification",
        "interpretation",
        "pathogenicity",
        "amr_genotype",
        "antimicrobial_resistance",
    }
)

_HIGH_RISK_RELATIONSHIP_TOKENS: frozenset[str] = frozenset(
    {
        "gene_associated_with_condition",
        "condition_associated_with_gene",
        "causes",
        "contributes_to",
        "treats",
        "associated_with",
        "biomarker_for",
    }
)

# Section 8.3.2's equivalence buckets. A fixed, versioned lookup table:
# categorical values are bucketed before comparison, never compared as free
# text. Bump `EQUIVALENCE_BUCKET_VERSION` when a value moves buckets, so a
# stored trust verdict can be traced to the table that produced it.
EQUIVALENCE_BUCKET_VERSION = "v1"

_BUCKET_BY_VALUE: dict[str, str] = {
    "pathogenic": "pathogenic_leaning",
    "likely pathogenic": "pathogenic_leaning",
    "benign": "benign_leaning",
    "likely benign": "benign_leaning",
    "uncertain significance": "uncertain",
    "conflicting interpretations of pathogenicity": "uncertain",
    "no assertion criteria provided": "uncertain",
}


@dataclass(frozen=True)
class ClaimTrust:
    """One claim's trust verdict, ready to become a `trust_signal` event."""

    citation_id: str
    risk_tier: RiskTier
    grounded: bool
    triangulation: TriangulationResult
    outcome: TrustOutcome

    @property
    def triangulated(self) -> bool | None:
        """The wire-level `triangulated` field on `TrustSignalPayload`.

        Three wire states, and they do NOT map one-to-one onto the three
        triangulation results:

            None   triangulation did not run (a low-risk claim, Section
                   8.3.3's "not evaluated")
            True   ran, and the sources concorded
            False  ran, and did not concord

        Finding J-07: an earlier docstring here called this a tri-state that
        distinguishes "ran and disagreed" from "not evaluated". Only the
        first half was true. `discordant` and `insufficient` BOTH map to
        False, so this field alone cannot tell a consumer whether the
        sources actively disagreed or whether there was only one of them.

        That distinction is not lost, it just lives on a different field of
        the same event: `outcome` is `flag` for discordant and `ask` for
        insufficient (Section 8.3.3). A consumer needing the difference
        reads `outcome`, which is the field Section 8.3 makes authoritative
        anyway. The docstring is corrected rather than the contract widened,
        because `TrustSignalPayload.triangulated` is a `bool | None` on a
        locked v1 contract and Section 2.6 permits adding an optional field,
        not redefining an existing one's type.
        """
        if self.risk_tier == "low":
            return None
        return self.triangulation == "concordant"


def risk_tier_for(field: str, node_or_edge_type: str = "") -> RiskTier:
    """Section 8.3.1: per claim, never per query.

    A single answer can mix a low-stakes identifier lookup with a
    clinical-adjacent assertion, so this takes one claim's field and the
    row type it came from, and nothing about the query as a whole.

    Defaults to `low` per the table's last row. Defaulting the other way
    would be the safer-looking choice and the wrong one: it would mark
    every gene-symbol lookup high risk, push the whole system to `ask`
    through the aggregation rule below, and train a reader to ignore the
    signal precisely when it means something.
    """
    field_token = _canonical(field)
    type_token = _canonical(node_or_edge_type)
    if field_token in _HIGH_RISK_FIELD_TOKENS:
        return "high"
    if type_token in _HIGH_RISK_RELATIONSHIP_TOKENS:
        return "high"
    return "low"


def _canonical(token: str) -> str:
    """Fold a field or type name to the spelling the risk tables use.

    Finding J-08: the tables are exact-token, so `clinicalSignificance` and
    `clinical significance` both missed `clinical_significance` and dropped a
    genuinely clinical claim to `low` risk, skipping triangulation entirely.
    Graph properties, API fields and BioLink predicates do not agree on a
    casing convention, and this rule must not depend on which one a given
    source happened to use.

    Lowercases, then collapses spaces, hyphens and camelCase boundaries to
    underscores, so all three spellings above canonicalize to one.
    """
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", token.strip())
    return re.sub(r"[\s\-]+", "_", spaced.lower())


def bucket_for(value: str) -> str | None:
    """Map a categorical value into its Section 8.3.2 equivalence bucket.

    None when the value is not in the table. An unmapped value never
    silently becomes its own bucket: two unmapped values would then compare
    as concordant purely because they are both unknown.
    """
    return _BUCKET_BY_VALUE.get(" ".join(value.strip().lower().split()))


def _origin_of(finding: SynthFinding) -> str:
    """The origin DATABASE a finding came from, not the layer it came through.

    Section 8.3.2's independence rule turns on origin, and layer is not
    origin: a Layer 1 snapshot of ClinVar and a Layer 2 live ClinVar fetch
    are one origin reached two ways. Deriving origin from the CURIE prefix
    (or the tool, when there is no CURIE) is what keeps the two distinct
    once Layers 2 and 3 arrive in build phase 3.4.
    """
    value = finding.field_value.strip()
    if ":" in value and finding.field == "curie":
        return value.split(":", 1)[0].lower()
    return finding.tool.lower()


def triangulate(
    claim_finding: SynthFinding,
    all_findings: list[SynthFinding],
) -> TriangulationResult:
    """Section 8.3.2's structural concordance check.

    Only ever called for high-risk claims (Section 8.3.2's first line);
    `decide` enforces that, not this function.

    Compares categorical values across independent-origin sources. Two
    findings count as independent only when their origin databases differ.
    A claim with fewer than two independent origins is INSUFFICIENT, which
    is the only branch a graph-only phase can reach. See the module
    docstring.
    """
    claim_origin = _origin_of(claim_finding)
    same_field = [
        f
        for f in all_findings
        if f.field == claim_finding.field and _origin_of(f) != claim_origin
    ]
    independent_origins = {_origin_of(f) for f in same_field}
    if not independent_origins:
        return "insufficient"

    buckets = {bucket_for(claim_finding.field_value)}
    for other in same_field:
        buckets.add(bucket_for(other.field_value))
    if None in buckets:
        # At least one value is outside the versioned bucket table, so the
        # comparison cannot be made structurally. Insufficient, never a
        # guess in either direction.
        return "insufficient"
    return "concordant" if len(buckets) == 1 else "discordant"


# Section 8.3.3, transcribed as data rather than as branching code, so a
# reader can check it against the spec table line by line. Keyed by
# `(risk_tier, grounded, triangulation)`; triangulation is None where the
# table says "not applicable" or "not evaluated".
DECISION_TABLE: dict[tuple[RiskTier, bool, TriangulationResult | None], TrustOutcome] = {
    ("low", False, None): "refuse",
    ("low", True, None): "answer",
    ("high", False, None): "refuse",
    ("high", True, "concordant"): "answer",
    ("high", True, "discordant"): "flag",
    ("high", True, "insufficient"): "ask",
}


def decide(
    citation_id: str,
    field: str,
    node_or_edge_type: str,
    grounded: bool,
    claim_finding: SynthFinding | None,
    all_findings: list[SynthFinding],
) -> ClaimTrust:
    """Run Section 8.3.1 to 8.3.3 for one claim.

    Grounded is the gate every other row depends on: an ungrounded claim
    refuses regardless of risk tier, and triangulation is not even
    evaluated for it, because there is nothing established to corroborate.
    """
    tier = risk_tier_for(field, node_or_edge_type)
    if not grounded:
        return ClaimTrust(
            citation_id=citation_id,
            risk_tier=tier,
            grounded=False,
            triangulation="insufficient",
            outcome=DECISION_TABLE[(tier, False, None)],
        )

    if tier == "low":
        return ClaimTrust(
            citation_id=citation_id,
            risk_tier="low",
            grounded=True,
            triangulation="insufficient",
            outcome=DECISION_TABLE[("low", True, None)],
        )

    triangulation: TriangulationResult = (
        triangulate(claim_finding, all_findings) if claim_finding is not None else "insufficient"
    )
    return ClaimTrust(
        citation_id=citation_id,
        risk_tier="high",
        grounded=True,
        triangulation=triangulation,
        outcome=DECISION_TABLE[("high", True, triangulation)],
    )


# Section 8.3.4: refuse outranks ask, ask outranks flag, flag outranks
# answer. Lower number wins.
_SEVERITY: dict[TrustOutcome, int] = {"refuse": 0, "ask": 1, "flag": 2, "answer": 3}


def aggregate(outcomes: list[TrustOutcome], default: TrustOutcome = "refuse") -> TrustOutcome:
    """Section 8.3.4: the answer-level signal is the most restrictive claim.

    An empty list means no claim survived grounding, which is a refusal
    rather than an answer with nothing in it. That is why `default` is
    `refuse` and not `answer`: defaulting the other way would make an
    answer with zero grounded claims report as fully trustworthy, the exact
    inversion this whole section exists to prevent.
    """
    if not outcomes:
        return default
    return min(outcomes, key=lambda outcome: _SEVERITY[outcome])


def trust_for_claims(
    claims: list[GroundedClaim],
    all_findings: list[SynthFinding],
    node_or_edge_type_by_citation_id: dict[str, str] | None = None,
) -> list[ClaimTrust]:
    """Compute one `ClaimTrust` per surviving claim, deduped by citation.

    Deduped because Section 8.3.4 attaches a signal to a CITATION, and two
    clauses citing the same finding share one citation. Emitting two
    trust_signal events for one `citation_id` would give a surface two
    verdicts to render on one chip.
    """
    types = node_or_edge_type_by_citation_id or {}
    seen: set[str] = set()
    out: list[ClaimTrust] = []
    for claim in claims:
        citation_id = claim.finding.citation_id
        if citation_id in seen:
            continue
        seen.add(citation_id)
        out.append(
            decide(
                citation_id=citation_id,
                field=claim.finding.field,
                node_or_edge_type=types.get(citation_id, ""),
                grounded=True,
                claim_finding=claim.finding,
                all_findings=all_findings,
            )
        )
    return out
