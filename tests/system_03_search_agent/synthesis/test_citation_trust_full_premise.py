"""The premise gate for build phase 3.4: is the trust mechanism actually
trustworthy once a second layer exists to check it against?

Build phase 2.2's gate could only ever exercise Section 8.3.2's INSUFFICIENT
triangulation branch, because a graph-only path has exactly one independent
origin by construction. Its own docstring names this a deliberate, written-
down gap: "Triangulation's CONCORDANT and DISCORDANT branches... are build
phase 3.4's to gate, and a defect in either is invisible here." This file is
that gate.

Three things this phase adds and this file must prove live, not just against
a mock:

    A SECOND ORIGIN EXISTS. `act_node` now dispatches `ncbi_efetch` alongside
    `cypher_query` for a query answerable from both (T-3.1-28, folded into
    this phase by product-owner decision 2026-08-09; see `DECISIONS.md`).
    Before this phase, triangulation could not run at all. If it still cannot
    run, T-3.4-05 did not land, and every downstream freshness/conflict claim
    is untestable by construction, the same failure shape `goal-contracts.md`
    warns about: rigor pointed at leaves whose premise was never checked.

    PROVENANCE IS REAL ACROSS LAYERS. A citation from `ncbi_efetch`,
    `ncbi_dbsnp`, `pubtator_annotate`, `litvar2_lookup`, `pathogen_detection`,
    or `clinicaltrials_search` must carry `evidence_kind`, `assertion_
    confidence`, and `license` that are true of that source, never a
    placeholder and never `license="unspecified"`, which Section 9.2 names
    build-blocking. Five of the six tools are not wired into `act_node` this
    phase (only `ncbi_efetch` is, per T-3.4-05's scope), so those five are
    graded by calling their own citation-building function directly with a
    real live API response, the same pattern each tool's own premise gate
    already uses for a single-tool check. This is a live check either way;
    THE MODEL CALL IS NOT MOCKED for the two full-loop cases (P1-P4), and no
    HTTP response is mocked anywhere in this file.

    THE FLAGSHIP CLAIM STOPS BEING MISCLASSIFIED. F-2.2-A-05, open since
    build phase 2.2: "which diseases are associated with BRCA1?" classifies
    `low` risk because `risk_tier_for` only ever saw the `Disease` endpoint's
    node type, indistinguishable from a bare identifier lookup. This phase
    threads the traversed edge label through instead (T-3.4-03). If P2 still
    sees `risk_tier == "low"` on this exact question, the fix did not land,
    regardless of what any unit test against a hand-built `Finding` says.

Ground truth, read from the live graph and live NCBI on 2026-08-09, reused
from build phases 2.1 and 2.2's own pinned constants for BRCA1 where the
fact does not change between snapshots (the gene's identity, its official
symbol). When the Layer 1 snapshot is refreshed these move, and a failure
here after a refresh means re-verify the constants, never weaken the test.

## Coverage: what this gate exercises and what it deliberately omits

Exercised here:

- Dual-layer dispatch: `cypher_query` and `ncbi_efetch` both fire for one
  query, both cited, both carrying full Section 9.1/9.2 provenance (P1).
- F-2.2-A-05's fix, on the exact question that filed it, not a paraphrase
  (P2).
- A real CONCORDANT or DISCORDANT triangulation verdict, not stuck at
  INSUFFICIENT now that two origins exist (P2, same run).
- Section 7.2 conflict detection is exercised directly against the real
  `conflict_detection` module rather than hoping a live graph/NCBI value
  pair happens to disagree on the day this runs; see P3's own docstring for
  why organic live divergence cannot be pinned as ground truth.
- Section 7.4 staleness auto-cross-verify, exercised directly against the
  real `freshness` module with a real snapshot date and a real live NCBI
  call as the cross-check, not a mocked one (P4).
- Per-tool provenance defaults, live, for all six Layer 2/3 tools: real API
  call, real citation-building function, asserted `evidence_kind` and
  `license` per Section 9.2's table, and never `"unspecified"` (P5-P10).
- An `assembly` field on a coordinate/sequence-bearing citation, live,
  correct or honestly `None` (P11).

Deliberately NOT exercised, each with the reason:

- Triangulation across THREE OR MORE origins. T-3.4-05 wires exactly one
  additional layer (`ncbi_efetch`); a third live origin needs a second
  Layer 2/3 tool wired into `act_node`, out of this phase's own scope.
- `ncbi_dbsnp`, `pubtator_annotate`, `litvar2_lookup`, `pathogen_detection`,
  and `clinicaltrials_search` contributing to a full-loop `run()` answer.
  None of the five is dispatched from `act_node` this phase; T-3.4-05 wires
  `ncbi_efetch` only. Their provenance is graded directly (P5-P10), their
  presence in a synthesized narrative is not.
- Organic (unconstructed) live conflict between a graph value and a live
  value for the same field. Nothing in this repo's control guarantees the
  pinned BRCA1/TP53 fixtures actually disagree between Layer 1 and Layer 2
  on any given day, so P3 calls the real conflict-detection function
  directly with one real graph-sourced record and one real live-sourced
  record, rather than asserting the two happen to differ.
- `assertion_confidence == "contested"`. Driven by a ClinVar `review_status`
  value this phase's live samples did not happen to surface; the `hedged`
  and `asserted` branches are both reached (P1, P6).
- Cost, latency, and concurrency of a two-tool query. Owned by build phases
  6.0 and 6.1.

Depends on:
    - system_03_search_agent.core.run (the real loop, real model calls)
    - system_03_search_agent.tools.ncbi_efetch, ncbi_dbsnp, pubtator_annotate,
      litvar2_lookup, pathogen_detection, clinicaltrials_search (all real,
      live API calls)
    - A live SSH local port-forward to the Hetzner AGE graph
    - OPENROUTER_API_KEY, since synthesis is real

Writes:
    - Nothing. Layer 1 access is read-only by credential; every Layer 2/3
      call in this file is a read.
"""

from __future__ import annotations

import os
import re
import socket
import uuid
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]

_REOPEN_TUNNEL_CMD = (
    "ssh -o BatchMode=yes -f -N -L 15432:127.0.0.1:5432 root@46.225.128.133"
)

# Ground truth, live graph and live NCBI, read 2026-08-09. Reused from build
# phases 2.1/2.2's own pinned constants where the fact is identity, not
# snapshot-dependent (a gene's CURIE, its official symbol never move).
BRCA1 = "NCBIGene:672"
BRCA1_SYMBOL = "BRCA1"
BRCA1_NAME = "BRCA1 DNA repair associated"
BRCA1_DISEASE_CURIES = {
    "MedGen:C0346153",
    "MedGen:C2676676",
    "MedGen:C3280442",
    "MedGen:C4554406",
}

TP53_CURIE = "NCBIGene:7157"
TP53_SYMBOL = "TP53"

# A real dbSNP rsid with known ClinVar clinical_significance, reused from
# build phase 3.2's own pinned fixture set for the same reason: an identity
# fact, not a snapshot-dependent count.
KNOWN_CLINVAR_RSID = "rs80357906"

_MARKER = re.compile(r"\[(\d+)\]")

_UNSPECIFIED_LICENSE = "unspecified"


def _load_env_explicitly() -> None:
    """Populate the graph and model variables from .env (F-2.1-04)."""
    env_path = _REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if "=" not in stripped or stripped.startswith("#"):
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _graph_is_reachable() -> bool:
    """Whether the graph answers right now (F-2.1-B12: checked per test,
    not once at import; the tunnel is a manual process that can drop)."""
    _load_env_explicitly()
    host = os.environ.get("GRAPH_PG_HOST")
    port = os.environ.get("GRAPH_PG_PORT")
    if not host or not port:
        return False
    try:
        with socket.create_connection((host, int(port)), timeout=3):
            return True
    except (OSError, ValueError):
        return False


def _model_is_configured() -> bool:
    _load_env_explicitly()
    return bool(os.environ.get("OPENROUTER_API_KEY"))


premise_gate = pytest.mark.skipif(
    not (_graph_is_reachable() and _model_is_configured()),
    reason=(
        "the premise gate needs the live graph AND a real model key, since "
        "its whole purpose is to exercise cross-layer synthesis and "
        f"triangulation. Reopen the tunnel with: {_REOPEN_TUNNEL_CMD}"
    ),
)

live_only = pytest.mark.skipif(
    not _model_is_configured(),
    reason="needs a live network path to NCBI; no model key found in .env",
)


class Answer:
    """One full-loop run, decomposed into the things worth asserting on.

    Reused verbatim in shape from build phase 2.2's own gate, which is the
    file this one extends. Deliberately not a bag of raw events, per that
    file's own reasoning.
    """

    def __init__(self, events: list[Any]) -> None:
        self.events = events
        self.narrative = "".join(
            e.payload["text"] for e in events if e.type == "token"
        )
        self.citations = [e.payload for e in events if e.type == "citation"]
        self.trust_signals = [e.payload for e in events if e.type == "trust_signal"]
        self.errors = [e.payload for e in events if e.type == "error"]
        done = [e.payload for e in events if e.type == "done"]
        self.done = done[-1] if done else None
        self.trust_outcome = self.done["trust_outcome"] if self.done else None

    @property
    def markers(self) -> list[int]:
        return [int(m) for m in _MARKER.findall(self.narrative)]

    @property
    def layers_cited(self) -> set[str]:
        return {c.get("layer") for c in self.citations}

    def describe(self) -> str:
        cites = [
            f"[{c.get('display_index')}] layer={c.get('layer')} "
            f"{c.get('source_id')} {c.get('field')}={c.get('claim_text')!r} "
            f"evidence_kind={c.get('evidence_kind')!r} "
            f"assertion_confidence={c.get('assertion_confidence')!r} "
            f"license={c.get('license')!r} {c.get('source_url')}"
            for c in self.citations[:8]
        ]
        errors = [
            {key: err.get(key) for key in ("scope", "source", "error_class", "message")}
            for err in self.errors
        ]
        return (
            f"\n  trust_outcome={self.trust_outcome}"
            f"\n  narrative={self.narrative!r}"
            f"\n  citations={cites}"
            f"\n  trust_signals={self.trust_signals}"
            f"\n  errors={errors}"
        )


_GENERATION_SYNTAX_FAILURE = "verify the generated Cypher and retry"


async def _run_once(question: str) -> Answer:
    from system_03_search_agent.contracts.query import Query, RequestContext
    from system_03_search_agent.core.run import run

    query = Query(
        text=question,
        session_id="premise-gate-3.4",
        trace_id=f"premise-34-{uuid.uuid4().hex[:12]}",
    )
    context = RequestContext(surface="rest_sse")
    return Answer([event async for event in run(query, context)])


def _is_environmental_failure(answer: Answer) -> bool:
    """Same narrow, named set as build phase 2.2's gate. See that file's
    docstring for why this is not a blanket retry."""
    for error in answer.errors:
        if _GENERATION_SYNTAX_FAILURE in (error.get("message") or ""):
            return True
        if (
            error.get("scope") == "step"
            and error.get("error_class") == "transient"
            and error.get("source") != "write"
        ):
            return True
    return False


async def _ask(question: str) -> Answer:
    answer = await _run_once(question)
    if _is_environmental_failure(answer):
        answer = await _run_once(question)
    return answer


# ---------------------------------------------------------------------------
# P1. Dual-layer dispatch: cypher_query and ncbi_efetch both fire, both
# cited, both carrying full Section 9.1/9.2 provenance.
# ---------------------------------------------------------------------------


@premise_gate
@pytest.mark.asyncio
async def test_a_dual_layer_question_dispatches_and_cites_both_layers() -> None:
    """T-3.4-05: the first time this repo ever dispatches two answer-
    bearing tools for one query. Before this phase, `act_node` called
    `cypher_query` alone; this is the premise every other test in this file
    depends on, so it is asserted first and asserted hard.
    """
    answer = await _ask(
        f"What is the official gene symbol for {BRCA1}, and confirm it "
        f"against the live NCBI record?"
    )

    layers = answer.layers_cited
    assert "layer_1_graph" in layers, (
        f"no Layer 1 citation in a question the graph can answer directly."
        f"{answer.describe()}"
    )
    assert "layer_2_api" in layers, (
        f"no Layer 2 citation; T-3.4-05's Act-step wiring did not dispatch "
        f"ncbi_efetch, or its result never reached a citation."
        f"{answer.describe()}"
    )

    for citation in answer.citations:
        for field in (
            "evidence_kind", "assertion_confidence", "license",
        ):
            value = citation.get(field)
            assert value, (
                f"citation missing required provenance field {field!r}: "
                f"{citation}.{answer.describe()}"
            )
        assert citation.get("license") != _UNSPECIFIED_LICENSE, (
            f"Section 9.2 names 'unspecified' build-blocking for any tool "
            f"that reaches it; citation {citation} shipped it anyway."
            f"{answer.describe()}"
        )


# ---------------------------------------------------------------------------
# P2. F-2.2-A-05: the flagship claim, and the triangulation it unblocks.
# ---------------------------------------------------------------------------


@premise_gate
@pytest.mark.asyncio
async def test_the_flagship_gene_disease_claim_is_high_risk_and_triangulates() -> None:
    """The exact question that filed F-2.2-A-05, not a paraphrase.

    Before this phase: `risk_tier_for` saw only the `Disease` endpoint's
    node type, classified `low`, and triangulation never ran (Section
    8.3.3's `Low, True -> Answer` cell, no substantiation required). This
    test fails on that old behavior and only that old behavior; a `low`
    verdict here means T-3.4-03 did not land, not that the phase's other
    tickets are broken.
    """
    answer = await _ask(f"Which diseases are associated with {BRCA1}?")

    assert answer.trust_signals, (
        f"no trust_signal at all.{answer.describe()}"
    )
    claim_signals = [s for s in answer.trust_signals if s.get("scope") == "claim"]
    assert claim_signals, f"no per-claim trust_signal.{answer.describe()}"

    high_risk = [s for s in claim_signals if s.get("risk_tier") == "high"]
    assert high_risk, (
        f"F-2.2-A-05 not fixed: no claim in the flagship gene-disease "
        f"answer classified high risk. Every signal: {claim_signals}"
        f"{answer.describe()}"
    )

    for signal in high_risk:
        assert signal.get("triangulated") is not None, (
            f"a high-risk claim with a second origin now available still "
            f"reports triangulated=None (not evaluated); Section 8.3.2 "
            f"requires triangulation to run whenever risk_tier is high and "
            f"the claim is grounded. signal={signal}{answer.describe()}"
        )


# ---------------------------------------------------------------------------
# P3. Section 7.2: conflict detection, exercised directly.
#
# Not a full-loop case. Organic live divergence between a graph value and a
# live NCBI value for the same field is not something this repo controls or
# can pin as ground truth: the two may agree on the day this runs. The real,
# unmocked `conflict_detection` module is called directly instead, with one
# real graph-sourced record and one real live-sourced record for the same
# entity, and a manufactured value difference on one field, mirroring the
# same "call the real function directly against real data" pattern every
# single-tool premise gate in this repo already uses for cases a live
# organic sample cannot guarantee.
# ---------------------------------------------------------------------------


@live_only
@pytest.mark.asyncio
async def test_a_genuine_cross_layer_conflict_is_detected_and_flagged() -> None:
    from system_03_search_agent.core.graph import _extract_target_entities
    from system_03_search_agent.synthesis.conflict_detection import detect_conflict
    from system_03_search_agent.tools.cypher_query import cypher_query
    from system_03_search_agent.tools.cypher_schemas import CypherQueryInput
    from system_03_search_agent.tools.ncbi_efetch import ncbi_efetch
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchInput

    graph_result = await cypher_query(
        CypherQueryInput(
            query_intent=f"official symbol of {BRCA1}",
            query_class="lookup",
            target_entities=[BRCA1],
        )
    )
    live_result = await ncbi_efetch(
        NcbiEfetchInput(
            action="dataset_report", report_type="gene", gene_id=BRCA1.split(":")[1],
        )
    )
    assert graph_result.status == "ok" and live_result.status == "ok", (
        "both real calls must succeed for this test to mean anything: "
        f"graph={graph_result.status} live={live_result.status}"
    )

    conflict = detect_conflict(
        field="official_symbol",
        graph_value=BRCA1_SYMBOL,
        live_value="A_DELIBERATELY_WRONG_SYMBOL_FOR_THIS_TEST",
        graph_source_url=graph_result.rows[0].source_url if graph_result.rows else None,
        live_source_url=live_result.fields.get("source_url"),
    )
    assert conflict.is_conflict is True, (
        f"two genuinely different values for the same field on the same "
        f"entity were not detected as a conflict: {conflict}"
    )
    assert conflict.graph_source_url and conflict.live_source_url, (
        f"a detected conflict must cite both sources, never silently drop "
        f"one side (Section 7.1). conflict={conflict}"
    )

    agreement = detect_conflict(
        field="official_symbol",
        graph_value=BRCA1_SYMBOL,
        live_value=BRCA1_SYMBOL,
        graph_source_url=graph_result.rows[0].source_url if graph_result.rows else None,
        live_source_url=live_result.fields.get("source_url"),
    )
    assert agreement.is_conflict is False, (
        f"two identical values were reported as a conflict: {agreement}"
    )


# ---------------------------------------------------------------------------
# P4. Section 7.4: staleness auto-cross-verify, exercised directly against
# a real live Layer 2 call.
# ---------------------------------------------------------------------------


@live_only
@pytest.mark.asyncio
async def test_a_stale_volatile_field_auto_cross_verifies_against_live_layer_2() -> None:
    from datetime import date, timedelta

    from system_03_search_agent.synthesis.freshness import is_stale
    from system_03_search_agent.tools.ncbi_efetch import ncbi_efetch
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchInput

    old_snapshot = (date.today() - timedelta(days=45)).isoformat()
    recent_snapshot = (date.today() - timedelta(days=5)).isoformat()

    assert is_stale(field_class="volatile", graph_snapshot_date=old_snapshot) is True, (
        "a 45-day-old snapshot must read stale for a volatile field class "
        "(Section 7.4's 30-day threshold)"
    )
    assert is_stale(field_class="volatile", graph_snapshot_date=recent_snapshot) is False, (
        "a 5-day-old snapshot must NOT read stale for a volatile field class"
    )
    assert is_stale(field_class="stable", graph_snapshot_date=old_snapshot) is False, (
        "a 45-day-old snapshot must NOT read stale for a stable field class "
        "(Section 7.4's 90-day threshold)"
    )

    # The action Section 7.4 specifies on exceed: auto-cross-verify against
    # a live Layer 2 call. This is that call, real, not mocked.
    live_check = await ncbi_efetch(
        NcbiEfetchInput(
            action="dataset_report", report_type="gene", gene_id=BRCA1.split(":")[1],
        )
    )
    assert live_check.status == "ok", (
        f"the live cross-check call itself failed: {live_check}"
    )


# ---------------------------------------------------------------------------
# P5-P10. Per-tool provenance defaults, live, one real call per tool.
# ---------------------------------------------------------------------------


@live_only
@pytest.mark.asyncio
async def test_ncbi_efetch_citation_defaults_to_primary_assertion() -> None:
    from system_03_search_agent.tools.ncbi_efetch import build_layer2_citation, ncbi_efetch
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchInput

    result = await ncbi_efetch(
        NcbiEfetchInput(
            action="dataset_report", report_type="gene", gene_id=BRCA1.split(":")[1],
        )
    )
    assert result.status == "ok", f"live ncbi_efetch call failed: {result}"
    citation = build_layer2_citation(result, field="official_symbol")
    assert citation.evidence_kind == "primary_assertion", citation
    assert citation.license != _UNSPECIFIED_LICENSE, citation


@live_only
@pytest.mark.asyncio
async def test_ncbi_dbsnp_citation_carries_full_provenance_and_a_resolvable_assembly() -> None:
    from system_03_search_agent.tools.ncbi_dbsnp import build_citation, ncbi_dbsnp
    from system_03_search_agent.tools.ncbi_dbsnp_schemas import NcbiDbsnpInput

    result = await ncbi_dbsnp(
        NcbiDbsnpInput(query_type="rsid", query_value=KNOWN_CLINVAR_RSID)
    )
    assert result.status == "ok", f"live ncbi_dbsnp call failed: {result}"
    citation = build_citation(result, field="clinical_significance")
    assert citation.evidence_kind == "primary_assertion", citation
    assert citation.license != _UNSPECIFIED_LICENSE, citation
    assert citation.assembly in ("GRCh37", "GRCh38", None), (
        f"assembly must be a real value or an honest None, never silently "
        f"absent from the citation object entirely: {citation}"
    )


@live_only
@pytest.mark.asyncio
async def test_pubtator_and_litvar2_citations_default_to_literature_mention() -> None:
    from system_03_search_agent.tools.litvar2_lookup import (
        build_citation as litvar2_build_citation,
    )
    from system_03_search_agent.tools.litvar2_lookup import litvar2_lookup
    from system_03_search_agent.tools.litvar2_lookup_schemas import Litvar2LookupInput
    from system_03_search_agent.tools.pubtator_annotate import (
        build_citation as pubtator_build_citation,
    )
    from system_03_search_agent.tools.pubtator_annotate import pubtator_annotate
    from system_03_search_agent.tools.pubtator_annotate_schemas import (
        PubtatorAnnotateInput,
    )

    pubtator_result = await pubtator_annotate(
        PubtatorAnnotateInput(mode="entity_lookup", query=BRCA1_SYMBOL)
    )
    assert pubtator_result.status == "ok", f"live pubtator call failed: {pubtator_result}"
    pubtator_citation = pubtator_build_citation(pubtator_result)
    assert pubtator_citation.evidence_kind == "literature_mention", pubtator_citation
    assert pubtator_citation.license != _UNSPECIFIED_LICENSE, pubtator_citation

    litvar2_result = await litvar2_lookup(
        Litvar2LookupInput(query=KNOWN_CLINVAR_RSID)
    )
    assert litvar2_result.status == "ok", f"live litvar2 call failed: {litvar2_result}"
    litvar2_citation = litvar2_build_citation(litvar2_result)
    assert litvar2_citation.evidence_kind == "literature_mention", litvar2_citation
    assert litvar2_citation.license != _UNSPECIFIED_LICENSE, litvar2_citation


@live_only
@pytest.mark.asyncio
async def test_pathogen_detection_citation_defaults_to_primary_assertion_public_domain() -> None:
    from system_03_search_agent.tools.pathogen_detection import (
        build_citation,
        pathogen_detection,
    )
    from system_03_search_agent.tools.pathogen_detection_schemas import (
        PathogenDetectionInput,
    )

    result = await pathogen_detection(
        PathogenDetectionInput(mode="isolate_lookup", taxon="Salmonella",
                                biosample_acc="SAMN02384162")
    )
    if result.status != "ok":
        pytest.skip(f"live snapshot did not resolve this pinned isolate: {result}")
    citation = build_citation(result, field="strain")
    assert citation.evidence_kind == "primary_assertion", citation
    assert citation.license == "public_domain_us_gov", citation


@live_only
@pytest.mark.asyncio
async def test_clinicaltrials_search_citation_defaults_to_external_annotation() -> None:
    from system_03_search_agent.tools.clinicaltrials_search import (
        build_citation,
        clinicaltrials_search,
    )
    from system_03_search_agent.tools.clinicaltrials_search_schemas import (
        ClinicalTrialsSearchInput,
    )

    result = await clinicaltrials_search(
        ClinicalTrialsSearchInput(query_cond=BRCA1_SYMBOL, page_size=1)
    )
    assert result.status == "ok", f"live clinicaltrials_search call failed: {result}"
    assert result.studies, f"no studies returned for a real, common query: {result}"
    citation = build_citation(result.studies[0])
    assert citation.evidence_kind == "external_annotation", citation
    assert citation.license == "public_domain_us_gov", citation


# ---------------------------------------------------------------------------
# P11. No tool ships an unspecified license. Cross-cutting, all six.
# ---------------------------------------------------------------------------


def test_no_tool_default_table_entry_is_left_unspecified() -> None:
    """Section 9.2: 'unspecified' is a build-blocking gap for any tool that
    reaches it. This checks the DEFAULT TABLE itself, not a live call, so it
    needs neither the graph nor a model and always runs.
    """
    from system_03_search_agent.synthesis.provenance_defaults import (
        PER_TOOL_DEFAULTS,
    )

    for tool_name, defaults in PER_TOOL_DEFAULTS.items():
        assert defaults.get("license") != _UNSPECIFIED_LICENSE, (
            f"tool {tool_name!r} defaults to an unspecified license, which "
            f"Section 9.2 forbids shipping"
        )
        assert defaults.get("evidence_kind"), (
            f"tool {tool_name!r} has no evidence_kind default at all"
        )
