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

# Of the seven relationship tokens above, only `gene_associated_with_
# condition` is a label `graph_schema_constants.EDGE_LABELS` actually
# carries today. The other six are not dead code: Section 8.3.1's table
# names them for PubTator3 and LitVar2 extracted relationships (cause,
# associated_with, treat) and the module docstring above already records
# that mapping. They are unreachable in build phase 2.2 because Layer 1 is
# the only source wired up, not because they are wrong, and they need no
# change here; they start firing the moment build phase 3.4 wires a Layer
# 2 or Layer 3 tool that supplies one of these relationship types.


def _canonical(token: str) -> str:
    """Fold a field, edge, or predicate name to one comparable spelling.

    Finding J-08: the tables are exact-token, so `clinicalSignificance` and
    `clinical significance` both missed `clinical_significance` and dropped
    a genuinely clinical claim to `low` risk, skipping triangulation
    entirely.

    Finding F-2.2-R-08: the first fix reinserted underscores at camelCase
    boundaries (`(?<=[a-z0-9])(?=[A-Z])`), which requires a lowercase
    character immediately before the boundary. `CLINICALSIGNIFICANCE` has
    none, every character is uppercase, so there is no boundary for that
    pattern to find, and neither a `.` separator nor a CURIE-style
    namespace prefix (`biolink:...`) was collapsed at all. Verified still
    broken: `CLINICALSIGNIFICANCE`, `clinicalsignificance`,
    `clinical.significance`, and `biolink:gene_associated_with_condition`
    all missed their table entry under the camelCase-only fix.

    Reinserting a separator at a word boundary needs a signal that an
    all-caps, no-separator string does not carry: there is nothing to look
    for, since uppercase follows uppercase the whole way through, and no
    general rule can tell "clinicalsignificance" apart from any other run
    of letters without a dictionary. So this goes the other direction
    instead of trying to reinsert boundaries: it removes every separator a
    source might use (space, hyphen, dot, underscore) from both sides of a
    comparison and compares on the bare letters alone.
    `clinical_significance`, `clinicalSignificance`,
    `CLINICALSIGNIFICANCE`, `clinical significance`, and
    `clinical.significance` all collapse to the same
    `"clinicalsignificance"`, regardless of which convention the source
    used, with no word-segmentation guess involved anywhere.

    A CURIE or BioLink-style predicate carries its namespace before a
    colon (`biolink:gene_associated_with_condition`). The live graph's
    `EDGE_LABELS` (`tools/graph_schema_constants.py`) are bare snake_case
    today, so this branch is latent, not live: no caller currently passes
    a prefixed value. It is fixed anyway because the moment a Layer 2 or
    Layer 3 tool supplies a prefixed relationship type (build phase 3.4),
    an unstripped prefix would silently sink a real
    `gene_associated_with_condition` match back to `low`, the exact
    failure this function exists to prevent, with no test in front of it
    to catch the regression before a clinical claim shipped on it.

    Still exact match, never substring, after collapsing: two names
    compare equal only when they are the same name spelled a different
    way, not when one merely contains the other.
    `not_clinical_significance` collapses to
    `"notclinicalsignificance"`, which is not `"clinicalsignificance"`, so
    a field that happens to CONTAIN the phrase is not swept in by this
    change; only a field that spells the same phrase under a different
    casing or separator convention is. This is what keeps the "no new
    false positive" property the re-review verified: collapsing widens
    which SPELLINGS of a listed token match, never which DISTINCT names
    match.
    """
    local = token.strip().rsplit(":", 1)[-1]
    return re.sub(r"[\s\-_.]+", "", local.lower())


# Precomputed once, at import time: the same collapse applied to the table
# entries themselves, so a lookup is a plain frozenset membership check
# against a value built the identical way. Recomputing this per call would
# work too, but a module-level constant is what makes it obvious the table
# is fixed and versioned rather than something that could drift between
# two calls in the same process.
_HIGH_RISK_FIELD_TOKENS_CANONICAL: frozenset[str] = frozenset(
    _canonical(token) for token in _HIGH_RISK_FIELD_TOKENS
)
_HIGH_RISK_RELATIONSHIP_TOKENS_CANONICAL: frozenset[str] = frozenset(
    _canonical(token) for token in _HIGH_RISK_RELATIONSHIP_TOKENS
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


def is_high_risk_relationship_label(label: str) -> bool:
    """Whether a single edge/relationship label is one of Section 8.3.1's
    high-risk relationship tokens (`_HIGH_RISK_RELATIONSHIP_TOKENS_
    CANONICAL`), canonicalized the same way `risk_tier_for` already
    compares `node_or_edge_type`.

    F-3.4-A-02: exposed as a read-only membership check so a caller that
    already knows a RETURNed variable is touched by MULTIPLE distinct
    edge labels (the ambiguous case `cypher_query._traversed_edge_type_
    by_column` deliberately declines to guess a single label for) can
    still ask "is at least one of the candidates high risk", without ever
    asserting to this module which specific one it was. Never widens the
    table itself: this is the exact same frozenset `risk_tier_for`
    already consults, exposed for a second caller to read.
    """
    return _canonical(label) in _HIGH_RISK_RELATIONSHIP_TOKENS_CANONICAL


def risk_tier_for(
    field: str,
    node_or_edge_type: str = "",
    *,
    ambiguous_high_risk_touch: bool = False,
) -> RiskTier:
    """Section 8.3.1: per claim, never per query.

    A single answer can mix a low-stakes identifier lookup with a
    clinical-adjacent assertion, so this takes one claim's field and the
    row type it came from, and nothing about the query as a whole.

    Defaults to `low` per the table's last row. Defaulting the other way
    would be the safer-looking choice and the wrong one: it would mark
    every gene-symbol lookup high risk, push the whole system to `ask`
    through the aggregation rule below, and train a reader to ignore the
    signal precisely when it means something.

    ## F-2.2-A-05: closed by T-3.4-03, not by widening this table

    The system's flagship question, "which diseases are associated with
    BRCA1?", returns `Disease` NODES (the `gene_associated_with_condition`
    edge's endpoint), not the edge itself. That is exactly Section
    8.3.1's "OMIM phenotype-gene mechanistic or causal mapping" row, and a
    row typed `Disease` is ALSO what a bare identifier lookup returns
    (`MATCH (d:Disease {curie: $c}) RETURN d`, no relationship at all),
    which Section 8.3.1's own table calls out as low risk ("Identifier
    lookups... cross-reference resolution"). Per `graph_schema_constants.
    EDGE_ENDPOINTS`, `Disease` is the endpoint of exactly two edges in this
    graph, `gene_associated_with_condition` (as target) and `has_phenotype`
    (as source), plus the no-edge bare-lookup case above; `node_or_edge_type`
    alone carries no signal distinguishing any of the three. Widening
    `node_or_edge_type == "disease"` to `high` unconditionally in this
    table would correctly catch the flagship question and incorrectly
    catch every plain "what is MedGen:C0346153" lookup too, misclassifying
    a case Section 8.3.1 explicitly names as low risk: the exact false
    positive `.claude/rules/goal-contracts.md` warns against manufacturing.
    That is why this table is still exactly what it was; nothing here
    changed to close this finding.

    This function's only inputs remain `field` and `node_or_edge_type`, one
    claim's finding and the row type it came from. What changed is what the
    caller now puts INTO `node_or_edge_type`: T-3.4-03 threads the
    traversed edge label from the generated Cypher's own MATCH text (never
    the model, never a runtime projection) through `cypher_provenance.
    to_output_rows` and a new, additive, optional `CypherQueryRow.
    traversed_edge_type` field
    (`cypher_query._traversed_edge_type_by_column`), and `graph.py`'s
    `_node_or_edge_type_by_citation_id` now prefers that field over the
    row's bare `node_or_edge_type` whenever the Cypher text pinned it
    unambiguously. The flagship question's `Disease` rows therefore reach
    this function with `node_or_edge_type="gene_associated_with_condition"`,
    which IS in `_HIGH_RISK_RELATIONSHIP_TOKENS_CANONICAL`, and classify
    `high` without this table changing at all. A bare identifier lookup
    has no traversed edge to thread, so the caller falls back to the row's
    own `node_or_edge_type` ("Disease", "MedGen", ...) exactly as before,
    and still classifies `low`: the four pre-existing guard tests below
    assert precisely that this table was never touched. Full account:
    `tracker/phase_3.4.md`'s T-3.4-03 entry.

    ## F-3.4-A-02: the two-hop reopening of F-2.2-A-05, closed without
    ## widening either table above

    T-3.4-03's own conservatism has a cost: when a RETURNed variable is
    touched by TWO OR MORE distinct edge labels (a two-hop question such
    as "what diseases and phenotypes are associated with BRCA1?", where
    the `Disease` column is touched by both the high-risk
    `gene_associated_with_condition` edge and the unrelated
    `has_phenotype` edge), `_traversed_edge_type_by_column` correctly
    declines to guess which one applies, and the row falls all the way
    back to its bare `node_or_edge_type` ("Disease"), reopening F-2.2-A-05
    for the exact query shape one hop past the pinned flagship case.

    `ambiguous_high_risk_touch` is the fix's other half, set only by a
    caller (`cypher_query._ambiguous_high_risk_edge_touch_by_column`) that
    has already confirmed, from the same Cypher text, that the touched
    variable's candidate edges include at least one real, known high-risk
    label. It is a strictly weaker claim than `node_or_edge_type` naming a
    single edge outright: it never says WHICH edge, only that a high-risk
    one was among the candidates, which is enough to classify `high`
    without ever asserting a specific wrong label. A second, independent
    path to `high`, not a change to either frozenset table above.
    """
    field_token = _canonical(field)
    type_token = _canonical(node_or_edge_type)
    if field_token in _HIGH_RISK_FIELD_TOKENS_CANONICAL:
        return "high"
    if type_token in _HIGH_RISK_RELATIONSHIP_TOKENS_CANONICAL:
        return "high"
    if ambiguous_high_risk_touch:
        return "high"
    return "low"


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
    *,
    ambiguous_high_risk_touch: bool = False,
) -> ClaimTrust:
    """Run Section 8.3.1 to 8.3.3 for one claim.

    Grounded is the gate every other row depends on: an ungrounded claim
    refuses regardless of risk tier, and triangulation is not even
    evaluated for it, because there is nothing established to corroborate.

    F-3.4-A-02: `ambiguous_high_risk_touch`, an additive keyword-only
    argument defaulting to `False`, is threaded straight to `risk_tier_
    for` unchanged. See that function's own docstring for what it means
    and why it never widens the risk table.
    """
    tier = risk_tier_for(
        field, node_or_edge_type, ambiguous_high_risk_touch=ambiguous_high_risk_touch
    )
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
    node_or_edge_type_by_citation_id: dict[str, tuple[str, bool]] | None = None,
) -> list[ClaimTrust]:
    """Compute one `ClaimTrust` per surviving claim, deduped by citation.

    Deduped because Section 8.3.4 attaches a signal to a CITATION, and two
    clauses citing the same finding share one citation. Emitting two
    trust_signal events for one `citation_id` would give a surface two
    verdicts to render on one chip.

    F-3.4-A-02: `node_or_edge_type_by_citation_id`'s value widened from a
    bare `str` to a `(node_or_edge_type, ambiguous_high_risk_touch)` pair;
    the caller (`core.graph._node_or_edge_type_by_citation_id`) is this
    dict's only real producer and was updated the same way. A missing
    citation_id defaults to `("", False)`, identical in effect to the old
    default of `""` plus no ambiguous signal.
    """
    types = node_or_edge_type_by_citation_id or {}
    seen: set[str] = set()
    out: list[ClaimTrust] = []

    for claim in claims:
        citation_id = claim.finding.citation_id
        if citation_id in seen:
            continue
        seen.add(citation_id)
        node_or_edge_type, ambiguous_high_risk_touch = types.get(citation_id, ("", False))
        out.append(
            decide(
                citation_id=citation_id,
                field=claim.finding.field,
                node_or_edge_type=node_or_edge_type,
                grounded=True,
                claim_finding=claim.finding,
                ambiguous_high_risk_touch=ambiguous_high_risk_touch,
                all_findings=all_findings,
            )
        )
    return out


def _origin_database(finding: SynthFinding) -> str:
    """The database a finding's record belongs to, for counting sources.

    Read from the record's CURIE prefix when it has one, so a Layer 1 snapshot
    row and a Layer 2 live fetch of the same database count ONCE, which is
    Section 8.3.2's independence rule. Falls back to the tool name only when
    the finding carries no CURIE at all.
    """
    curie = finding.curie.strip()
    if ":" in curie:
        return curie.split(":", 1)[0].lower()
    return finding.tool.lower()


def answer_trust_line(
    trust_outcome: TrustOutcome,
    claim_trusts: list[ClaimTrust],
    claims: list[GroundedClaim],
) -> str | None:
    """UI fix set 9, item 9.9 (decision U1): one plain line for an answer.

    Replaces a row of pills that could contradict each other ("Grounded ·
    every claim cited" beside "Single source, not independently confirmed").
    Every clause is derived from verdicts Section 8.3 already computed; this
    function decides nothing new about trust, it only says it once.

    - `refuse`, or nothing grounded: None. A refusal has its own block.
    - `flag`: the sources disagree, which outranks any count.
    - `answer` with at least one high-risk claim, every high-risk claim
      concordant, and two or more independent databases: "Confirmed by N
      independent sources". This is the only line that says "confirmed",
      because concordance is the only verdict that means it.
    - `ask`: "Based on N source(s), not yet confirmed".
    - Otherwise (every claim low risk): "Based on N source(s)". Low-risk
      claims are never triangulated, so "not yet confirmed" would imply a
      check that does not apply to them.

    ## Fix-plan item 12.8 (2026-09-23): two different counts, not one

    Measured against real runs (`testing/Developer/reports/2026-09-23_set12/
    both_depths/`), the "Based on" line was printing "Based on 4 sources"
    under an answer with 20 clickable citations, and after item 12.7's
    listing dedup, "Based on 1 source" over five visible papers. The line
    was never wrong about what it counted, `_origin_database`'s comment
    always said "databases, never records", and a test asserted exactly
    that. It was wrong about what the WORD "source" means to the reader
    looking at the chips underneath: to them, a source is one of those
    chips, not one of the databases those chips happen to come from.

    Section 8.3.2's independence rule is still real and still needed
    somewhere: "Confirmed by N independent sources" is a claim about
    CORROBORATION, that N separate databases agree, and counting
    citations there would overstate independence (twenty ClinVar rows are
    one database, not twenty separate confirmations). So the two counts
    now live side by side and are never conflated:

    - `citation_count`, the number of distinct `citation_id`s among the
      grounded claims. This is the same identity `display_index_by_
      citation_id` (`synthesis/grounding.py`) uses to number the chips a
      reader actually sees, so this count and the visible citation list
      can no longer disagree. It drives every "Based on N source(s))"
      line, confirmed or not: the reader is told how much evidence they
      can click through, which is the claim "Based on" actually makes.
    - `database_count`, the pre-existing independent-origin count, kept
      for exactly one job: deciding and wording "Confirmed by N
      independent sources", where "independent" is the load-bearing word
      and N must never exceed how many distinct databases actually
      agree.
    """
    if trust_outcome == "refuse" or not claims:
        return None
    citation_count = len({claim.finding.citation_id for claim in claims})
    database_count = len({_origin_database(claim.finding) for claim in claims})
    noun = "source" if citation_count == 1 else "sources"
    if trust_outcome == "flag":
        return "Sources disagree on at least one claim"
    high = [trust for trust in claim_trusts if trust.risk_tier == "high"]
    if (
        trust_outcome == "answer"
        and high
        and all(trust.triangulation == "concordant" for trust in high)
        and database_count >= 2
    ):
        return f"Confirmed by {database_count} independent sources"
    if trust_outcome == "ask":
        return f"Based on {citation_count} {noun}, not yet confirmed"
    return f"Based on {citation_count} {noun}"
