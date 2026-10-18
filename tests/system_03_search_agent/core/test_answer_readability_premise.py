"""The premise gate for build phase 6.2: can a person READ the answer?

Build phase 2.2's gate asked whether the answer is grounded and honest.
This one asks the question a researcher actually asks, and it is a
different question: given a grounded, honest, fully cited answer, does it
say anything a human can use?

The answer that opened this phase passed every gate this repository has:

    The knowledge graph associates the gene BRCA1 with four disease
    records: MedGen:C0346153, MedGen:C2676676, MedGen:C3280442, and
    MedGen:C4554406.

Three claims, all grounded, all cited, trust-gated, and useless. No
existing arm can see that, because every one of them asserts on structure
(a citation exists, a marker resolves, an outcome is a valid enum) and
this defect is entirely in the semantics. That gap is what this file
closes.

`docs/build/Build_workflow_cadence.md` stage 5 makes this file mandatory
and blocking, since 6.2's deliverable is model-generated output. The four
properties that stage requires, and where each lives here:

    THE MODEL CALL IS NOT MOCKED. Arms A1 to A3 go through
    `core.run.run()`, the entry point every surface calls, with nothing
    hand-fed.

    ASSERTIONS ARE ON MEANING. "A citation was emitted" and "the narrative
    is non-empty" both pass on the unreadable answer above. What must hold
    is that the SENTENCE NAMES THE DISEASE, checked against titles read
    from MedGen on a path that touches none of this agent's machinery.

    GROUND TRUTH IS READ FROM THE LIVE SOURCE AND PINNED. The four titles
    below were read from live NCBI on 2026-09-01 by the two-call sequence
    in `_live_medgen_title`. Arm A6 re-reads them at run time and fails if
    the pin has drifted, so a stale constant cannot silently protect a
    wrong assertion. When a title moves, RE-VERIFY THE PIN, never weaken
    the arm that uses it.

    IT RUNS THE WAY PRODUCTION RUNS. Same `run()`, same `Query`, same
    `RequestContext(surface="rest_sse")`.

## Why the graph cannot answer this, established before the gate was written

Measured against the live graph 2026-08-31, and recorded so nobody
re-derives it: Disease nodes carry the SOURCE VOCABULARY in `name`, not a
disease name. Across 25 sampled nodes it takes three distinct values,
`MedGen`, `MeSH` and `SNOMEDCT_US`. Gene nodes are fine, 23 distinct
values across 23 nodes.

Two consequences that shape every arm below:

- A readable answer was never EXPRESSIBLE from Layer 1. Exposing `name` to
  the Cypher generator would return the word `SNOMEDCT_US` four times,
  which is worse than four identifiers.
- The CURIE fallback is DELIBERATE, not an oversight.
  `core.graph._is_vocabulary_token_artifact` already detects the corrupted
  value and downgrades confidence rather than asserting it. The moat and
  the defect are one mechanism, so no arm here may be satisfied by
  weakening that detector.

The fix this gate demands is therefore a Layer 2 resolution path, and arm
A4 pins its honest-failure direction.

## The correction to the brief, verified rather than inherited

`docs/build/UI_feedback.md` and `requirements/phase_6/Continuation_prompt.md` both
state that `ncbi_efetch` already reaches MedGen in that query, so the fix
"looks closer to wiring than to building", and both instructed the reader
to verify it. Verified 2026-09-01, and it is half true.

A MedGen ESummary keyed on a concept id is REJECTED by NCBI:

    {"error":"Invalid uid C0346153 at position= 0","result":{"uids":[]}}

Resolution takes TWO calls: ESearch on `C0346153[ConceptId]` returns UID
`87542`, then ESummary on `87542` returns `Familial cancer of breast`.
Both actions already exist in the shipped tool with `medgen` on each db
enum and `title` already on the `medgen` field allowlist, so it stays
wiring. It is not free: two extra live calls on a path already taking 12
to 14 seconds, which is why caching is in T-6.2-02's criteria.

## Coverage: what this gate exercises and what it deliberately omits

`.claude/rules/goal-contracts.md` requires this statement, and build phase
2.1 is why: its gate missed a defect that made every two-hop question
unanswerable, because all nine of its questions were one hop from a single
anchor type. A gap that is written down is arguable; a gap that is not is
invisible.

Exercised here:

- The exact question that opened this phase, gene to disease, four
  results, against the live loop (A1, A2, A3).
- Both directions of the readability property: the names ARE present (A1)
  and the raw identifiers are NOT presented in their place (A2). One
  without the other is satisfiable by an empty answer, which is why A2
  carries a populate-check rather than standing alone.
- Provenance of a resolved name: it is a Layer 2 fact and must be cited as
  one, never laundered into the Layer 1 citation it was resolved from (A3).
- The honest-failure direction: a concept id that does not resolve keeps
  its identifier and is disclosed, and is never given an invented name
  (A4). This is the arm that stops the fix from being a fluent guess.
- That the internal findings-accounting sentence never reaches a reader
  (A5).
- That the pinned ground truth still matches live MedGen (A6).

Deliberately NOT exercised, each with its reason:

- Any node label other than Disease. The same ETL corruption may exist
  elsewhere; `_LEAKED_VOCABULARY_NAMES` suggests it does not, and that is
  an inference from a census rather than a proof. A defect in another
  label is invisible here.
- Any route to a Disease node other than gene-to-disease association. This
  is the same single-anchor blind spot 2.1's gate had, named here rather
  than discovered later.
- MeSH and SNOMEDCT_US concept ids. Only MedGen ids are resolved and
  asserted. A Disease node whose id carries another prefix is not covered.
- Latency. Nothing here bounds how long the answer takes, and this phase
  ADDS two calls to that path. T-6.2-05 covers the wait's presentation and
  no arm here would notice a regression in it.
- The five interface complaints. They are browser-visible and belong to
  the journey captures in T-6.2-11, not to this gate.
- Cost. `total_cost_usd` reporting 0.0 is T-6.2-13 and no arm here reads
  it.

Cost and speed: two real full-loop runs plus four live NCBI lookups.
Roughly $0.01 and about a minute.

Depends on:
    - system_03_search_agent.core.run (the real loop, real model calls)
    - system_03_search_agent.synthesis.disease_names (T-6.2-02's
      deliverable, which does not exist yet: that is why A4 fails today)
    - A reachable Layer 1 graph over whichever transport is live
    - OPENROUTER_API_KEY, since synthesis is real
    - Live network access to eutils.ncbi.nlm.nih.gov

Writes:
    - Nothing. Layer 1 access is read-only by credential.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]

# Ground truth. Read from live NCBI on 2026-09-01 by the two-call sequence
# `_live_medgen_title` performs, on a path that touches none of the agent's
# own machinery: no graph, no tool module, no model. Arm A6 re-reads these
# at run time, so a drifted pin fails loudly instead of quietly protecting
# a wrong assertion elsewhere in this file.
BRCA1_DISEASE_TITLES = {
    "C0346153": "Familial cancer of breast",
    "C2676676": "Breast-ovarian cancer, familial, susceptibility to, 1",
    "C3280442": "Pancreatic cancer, susceptibility to, 4",
    "C4554406": "Fanconi anemia, complementation group S",
}

BRCA1_DISEASE_QUESTION = "Which diseases are associated with BRCA1?"

# A syntactically valid MedGen concept id that MedGen does not hold. Used
# by A4 to drive the honest-failure direction. Its shape passes
# `cypher_provenance`'s `^CN?\d+$` local-id rule, so nothing upstream
# rejects it for looking wrong: the resolver has to actually fail to find
# it, which is the case A4 exists to pin.
UNRESOLVABLE_CONCEPT_ID = "C9999999"

# The user-visible shape of the defect: a bare MedGen CURIE sitting in the
# narrative where a disease name belongs. A citation payload may and should
# carry the identifier; the NARRATIVE may not.
_BARE_MEDGEN_CURIE = re.compile(r"MedGen:CN?\d+")

_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# The internal accounting sentence from `docs/build/UI_feedback.md`, which reached a
# real user on 2026-08-31: "this answer reports 3 of the 5 findings
# prepared for it". A5 matches its shape rather than that literal string,
# so a reworded version of the same disclosure is still caught.
_FINDINGS_ACCOUNTING = re.compile(
    r"\b\d+\s+of\s+the\s+\d+\s+findings\b|\bfindings\s+prepared\s+for\s+it\b",
    re.IGNORECASE,
)


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
    """Whether Layer 1 answers right now, over whichever transport is live.

    Delegates to the ONE implementation, which dispatches on
    `GRAPH_QUERY_URL` exactly as `graph_connection.execute_cypher` and
    `tracker/preflight.py` do. Build phase 4.12 measured what happens when
    a gate keeps its own copy of this probe: it returned False on a machine
    where the graph was perfectly reachable, and every live arm behind it
    SKIPPED while printing a reason that was false.
    """
    from tests.system_03_search_agent.graph_gate import live_graph_arms_enabled

    return live_graph_arms_enabled()


def _model_is_configured() -> bool:
    _load_env_explicitly()
    return bool(os.environ.get("OPENROUTER_API_KEY"))


premise_gate = pytest.mark.skipif(
    not (_graph_is_reachable() and _model_is_configured()),
    reason=(
        "the premise gate needs the live graph AND a real model key, since "
        "its whole purpose is to exercise a real answer. Check .env and "
        "`python3 tracker/preflight.py`"
    ),
)


# `.claude/rules/tool-call-budgets.md`: E-utilities is 3 requests/second
# unauthenticated, the pool belongs to NCBI PER HOST rather than to this
# test run, and "an integration suite that fires faster than the limit it
# is testing against is a self-inflicted failure". Measured on the first
# run of this gate, which is why the pacer exists: A6 makes eight calls
# (two per concept id) and issuing them back to back returned an HTTP
# error from NCBI, so the gate failed for its own impatience rather than
# for anything about the product. One call per second sits comfortably
# under the unauthenticated ceiling and leaves headroom for the agent's
# own eutils traffic, which draws on the same bucket.
_EUTILS_MIN_INTERVAL_S = 1.0
_last_eutils_call_at = 0.0


def _get_json(url: str) -> dict[str, Any]:
    global _last_eutils_call_at
    elapsed = time.monotonic() - _last_eutils_call_at
    if elapsed < _EUTILS_MIN_INTERVAL_S:
        time.sleep(_EUTILS_MIN_INTERVAL_S - elapsed)
    _last_eutils_call_at = time.monotonic()

    request = urllib.request.Request(url, headers={"User-Agent": "system3-premise-gate"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _live_medgen_title(concept_id: str) -> str | None:
    """Read one MedGen title from live NCBI, independently of the agent.

    Deliberately does NOT import `ncbi_efetch`, `ncbi_eutils_actions` or
    anything else under `src/`. A gate that verified the agent's answer
    using the agent's own resolver would certify that the two agree, not
    that either is right, which is the same circularity build phase 5.1
    avoided when it built the golden dataset from an independent path.

    Two calls, because one does not work: ESummary rejects a concept id
    outright, so the concept id is first resolved to a numeric UID.
    """
    term = urllib.parse.quote(f"{concept_id}[ConceptId]")
    search = _get_json(f"{_EUTILS}/esearch.fcgi?db=medgen&term={term}&retmode=json")
    uids = search.get("esearchresult", {}).get("idlist", [])
    if not uids:
        return None
    summary = _get_json(f"{_EUTILS}/esummary.fcgi?db=medgen&id={uids[0]}&retmode=json")
    result = summary.get("result", {})
    for uid in result.get("uids", []):
        title = result[uid].get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    return None


class Answer:
    """One full-loop run, decomposed into the things worth asserting on.

    Deliberately not a bag of raw events: an assertion written against a
    raw event list tends to check that an event exists rather than what it
    says, which is the exact failure this file exists to catch.
    """

    def __init__(self, events: list[Any]) -> None:
        self.events = events
        self.narrative = "".join(e.payload["text"] for e in events if e.type == "token")
        self.citations = [e.payload for e in events if e.type == "citation"]
        self.errors = [e.payload for e in events if e.type == "error"]
        done = [e.payload for e in events if e.type == "done"]
        self.done = done[-1] if done else None
        self.trust_outcome = self.done["trust_outcome"] if self.done else None

    def describe(self) -> str:
        """A failure message that shows the actual answer, not a count.

        The whole point of this gate is that counts pass on unreadable
        answers, so a failure has to print what was actually said.
        """
        cites = [
            f"[{c.get('display_index')}] {c.get('source_id')} layer={c.get('layer')} "
            f"{c.get('field')}={c.get('claim_text')!r} {c.get('source_url')}"
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
            f"\n  errors={errors}"
        )


async def _run_once(question: str) -> Answer:
    from system_03_search_agent.contracts.query import Query, RequestContext
    from system_03_search_agent.core.run import run

    query = Query(
        text=question,
        session_id="premise-gate-6-2",
        trace_id=f"premise62-{uuid.uuid4().hex[:12]}",
    )
    context = RequestContext(surface="rest_sse")
    return Answer([event async for event in run(query, context)])


def _assert_answered(answer: Answer) -> None:
    """The populate-check every readability arm sits behind.

    Build phase 4.11's durable lesson, applied here: an arm that cannot
    distinguish the property holding from NOTHING HAVING HAPPENED is not an
    arm. "The narrative contains no bare CURIE" is true of an empty
    narrative, of a refusal, and of a transport failure. Each readability
    arm therefore proves first that a real answer arrived, and only then
    asserts what it says.
    """
    assert not answer.errors, f"the run errored before it answered{answer.describe()}"
    assert len(answer.narrative.strip()) >= 40, (
        f"no substantive answer to assert on{answer.describe()}"
    )
    assert answer.citations, f"an answer with no citations{answer.describe()}"


# ----------------------------------------------------------------------
# A6 runs first in file order on purpose: if the pinned ground truth has
# drifted, every other arm in this file is asserting against a stale
# constant, and that is worth knowing before reading their failures.
# ----------------------------------------------------------------------


@pytest.mark.integration
def test_a6_pinned_ground_truth_still_matches_live_medgen() -> None:
    """A6: the four pinned titles are what MedGen says today.

    Drives: the ground-truth constants every other arm depends on.

    A gate whose ground truth has silently drifted reports on the pin
    rather than on the product. When this fails, RE-VERIFY AND REPIN. Never
    relax the arms that use these values to accommodate a drifted pin,
    which is the `goal-contracts` corrupt-the-subject failure seen from the
    other side.

    T-8.1-08 (tracker/phase_8.1.md): this test makes a live call to NCBI
    via `_get_json`/`_live_medgen_title` with `urllib.request.urlopen`,
    bypassing the hermetic guard in `tests/conftest.py`. Unmarked, it was
    collected by the unit gate (`pytest -m "not integration"`,
    `.github/gates/gate04_unit_suite.sh`) and could turn CI red on a bare
    NCBI HTTP error with nothing wrong in the product
    (LEARNINGS.md, 2026-09-24). The `integration` marker moves it to gate
    5 (`.github/gates/gate05_integration.sh`, `pytest -m integration`),
    which is allowed to hit the network. The check itself is unchanged.
    """
    for concept_id, expected in BRCA1_DISEASE_TITLES.items():
        live = _live_medgen_title(concept_id)
        assert live is not None, (
            f"MedGen no longer resolves {concept_id}; the pin is stale, repin it"
        )
        assert live == expected, (
            f"pinned title for {concept_id} has drifted: "
            f"pinned {expected!r}, live {live!r}. Repin, do not weaken the arms"
        )


@premise_gate
@pytest.mark.asyncio
async def test_a1_answer_names_the_diseases_in_words() -> None:
    """A1: the answer says what the diseases ARE.

    Drives: T-6.2-02, the resolution path.

    THE CENTRAL ARM OF THIS PHASE. It is the one assertion that the answer
    which opened build phase 6.2 fails, and every structural arm in this
    repository passes.

    Three of four rather than four of four, deliberately. The graph's
    association set is a snapshot and the tool truncates, so requiring all
    four couples this arm to row ordering, which is not the property under
    test (the same reasoning build phase 2.2 recorded as finding F-2.2-07).
    Three names is unambiguously a readable answer; zero names is the
    defect.
    """
    answer = await _run_once(BRCA1_DISEASE_QUESTION)
    _assert_answered(answer)

    lowered = answer.narrative.lower()
    named = [
        title for title in BRCA1_DISEASE_TITLES.values() if title.lower() in lowered
    ]
    assert len(named) >= 3, (
        f"the answer names {len(named)} of the four diseases in words, "
        f"needed at least 3. Named: {named}{answer.describe()}"
    )


@premise_gate
@pytest.mark.asyncio
async def test_a2_answer_does_not_show_bare_identifiers_in_place_of_names() -> None:
    """A2: no `MedGen:C0346153` sits where a disease name belongs.

    Drives: T-6.2-02.

    The other half of A1, and neither is sufficient alone. A1 alone is
    satisfiable by an answer that names the diseases AND still prints the
    raw identifiers beside them, which is what a partial fix produces. A2
    alone is satisfiable by an empty answer, which is why it sits behind
    `_assert_answered` and re-checks that the names are present before
    asserting the identifiers are absent.

    Scope is the NARRATIVE only. A citation payload carrying
    `source_id="MedGen:C0346153"` is correct and required; this arm must
    never be read as an argument against that.
    """
    answer = await _run_once(BRCA1_DISEASE_QUESTION)
    _assert_answered(answer)

    lowered = answer.narrative.lower()
    named = [
        title for title in BRCA1_DISEASE_TITLES.values() if title.lower() in lowered
    ]
    assert named, (
        f"populate-check: this arm cannot distinguish a fixed answer from an "
        f"unanswered one unless at least one disease is named{answer.describe()}"
    )

    leaked = _BARE_MEDGEN_CURIE.findall(answer.narrative)
    assert not leaked, (
        f"the narrative still shows raw identifiers: {sorted(set(leaked))}"
        f"{answer.describe()}"
    )


@premise_gate
@pytest.mark.asyncio
async def test_a3_a_resolved_name_is_cited_to_the_record_it_came_from() -> None:
    """A3: a Layer 2 name is cited as a Layer 2 fact.

    Drives: T-6.2-02's provenance criterion.

    The dangerous partial fix is to resolve a name over Layer 2 and then
    attach it to the Layer 1 citation the identifier came from. The answer
    then reads correctly and its provenance is a lie, which is worse than
    the unreadable answer this phase started with:
    `production-standards.md`'s layer authority gate exists for exactly
    that. So the name must carry its own MedGen citation.
    """
    answer = await _run_once(BRCA1_DISEASE_QUESTION)
    _assert_answered(answer)

    lowered = answer.narrative.lower()
    named = [
        title for title in BRCA1_DISEASE_TITLES.values() if title.lower() in lowered
    ]
    assert named, (
        f"populate-check: no disease is named, so there is no resolved name "
        f"whose provenance could be checked{answer.describe()}"
    )

    medgen_records = [
        c
        for c in answer.citations
        if "ncbi.nlm.nih.gov/medgen/" in str(c.get("source_url", ""))
    ]
    assert medgen_records, (
        f"the answer names a disease but cites no MedGen record for the name"
        f"{answer.describe()}"
    )
    layers = {str(c.get("layer")) for c in medgen_records}
    assert not layers <= {"layer_1_graph"}, (
        f"every MedGen citation reports Layer 1, so a name read live from "
        f"MedGen is being presented as a graph fact. Layers seen: {layers}"
        f"{answer.describe()}"
    )


@pytest.mark.asyncio
async def test_a4_an_unresolvable_concept_id_is_disclosed_and_never_invented() -> None:
    """A4: the honest-failure direction of the resolver.

    Drives: T-6.2-02's non-invention criterion.

    THE ARM THAT STOPS THE FIX FROM BECOMING A GUESS. A resolver that
    returns a plausible name for an id MedGen does not hold turns this
    system's one real asset, a citation that can be checked, into a
    confident wrong answer. Under-resolution is cheap; invention is not.

    Offline and independent of the loop on purpose: the failure it pins is
    a property of the resolver, and driving it through a live question
    would need a graph row that does not exist.

    Written before the resolver existed, and it failed with an ImportError
    on the gate's first run, which is the point: the gate named the
    contract the fix had to satisfy before the fix was written.

    Made `async` on 2026-09-01 when the resolver landed, because every
    E-utilities action in this repository is a coroutine and a synchronous
    resolver would have needed its own HTTP path, invisible to the shared
    rate pool, to the per-query call ceiling and to the audit log. The
    ASSERTIONS BELOW ARE UNCHANGED: this is the arm adapting to the
    contract's real shape, not the check being relaxed to let something
    pass. Recorded here rather than silently, since editing a verify
    surface mid-run is exactly the move `goal-contracts` forbids doing
    quietly.
    """
    from system_03_search_agent.synthesis.disease_names import resolve_concept_ids

    resolved = await resolve_concept_ids([UNRESOLVABLE_CONCEPT_ID])

    assert UNRESOLVABLE_CONCEPT_ID in resolved, (
        "an unresolvable id must be reported, not dropped: a dropped id "
        "disappears from the answer with no disclosure"
    )
    assert resolved[UNRESOLVABLE_CONCEPT_ID] is None, (
        f"a name was invented for an id MedGen does not hold: "
        f"{resolved[UNRESOLVABLE_CONCEPT_ID]!r}"
    )


@premise_gate
@pytest.mark.asyncio
async def test_a5_internal_findings_accounting_never_reaches_the_reader() -> None:
    """A5: no user-facing sentence reports an internal findings count.

    Drives: T-6.2-03.

    The observed text was "this answer reports 3 of the 5 findings prepared
    for it, and the 2 not reported are absent from the citations as well as
    from the text above". It tells a researcher nothing actionable and
    undermines the results that did survive. The pattern matched here is a
    SHAPE rather than that literal string, so a reworded version of the
    same disclosure is caught too.

    This arm does not object to disclosing that information was withheld.
    It objects to disclosing it as internal bookkeeping.

    ## Why this arm is now DETERMINISTIC, and what it looked like when it
    ## was not (F-6.2-04)

    As first written this arm ran a live question and asserted the note was
    absent from whatever came back. It reported GREEN on the run right
    after T-6.2-02 landed, while T-6.2-03 had not been started and the note
    was fully live: the very next run of the same question produced

        ... Note: this answer reports 4 of the 5 findings prepared for it,
        and the one not reported is absent from the citations as well as
        from the text above

    The note only appears when synthesis actually omits a prepared finding,
    and whether it does varies run to run (F-6.2-03). So the arm was a coin
    flip that read as coverage, which is precisely the "a gate that cannot
    distinguish the property holding from nothing having happened is not a
    gate" failure `goal-contracts.md` names.

    The fix is NOT to retry the live question until the note appears, which
    would be tuning the arm to the defect and would still be probabilistic.
    It is to drive the omission DIRECTLY, by calling the note builder with
    an omission, so the disclosure is guaranteed to exist and this arm can
    assert on what a reader is shown WHEN it does. That is the case the note
    exists for, and it is the only case in which this arm ever had anything
    to say.

    The live half is not discarded, because an offline call to one builder
    cannot see the note reaching a real answer. It moves to a POPULATE-CHECK
    shape: run the real question, and if a disclosure appears in it, hold it
    to the same rule. A run with no omission now SKIPS that half explicitly
    instead of passing it silently.

    `test_write_completeness.py::test_the_incomplete_note_counts_findings_handed_to_synthesis`
    carries the same assertion through the real `write_node`, with the
    omission forced by fixtures. Between them the property is pinned at the
    builder, at the node, and opportunistically at the live answer.
    """
    from system_03_search_agent.core.graph import _build_incomplete_answer_note
    from system_03_search_agent.synthesis.findings import SynthFinding

    def _omitted(count: int) -> list[SynthFinding]:
        return [
            SynthFinding(
                ref_index=i,
                citation_id=f"omitted-{i}",
                layer="layer_1_graph",
                tool="cypher_query",
                field="curie",
                field_value=f"MedGen:C{i}",
                source_url=f"https://www.ncbi.nlm.nih.gov/medgen/C{i}",
                entity_type="Disease",
                curie=f"MedGen:C{i}",
            )
            for i in range(1, count + 1)
        ]

    # The deterministic half. Both the singular and plural branches are
    # exercised, because the note has two of them and an arm that only ever
    # sees one leaves the other free to say anything.
    for count in (1, 3):
        note = _build_incomplete_answer_note(_omitted(count), reported=2)
        leaked = _FINDINGS_ACCOUNTING.findall(note)
        assert not leaked, (
            f"internal findings accounting is what the reader is shown when "
            f"{count} finding(s) are omitted: {leaked}. Note: {note!r}"
        )
        assert "not covered in the summary above" in note, (
            f"the omission must still be DISCLOSED, and this arm must never "
            f"be satisfiable by deleting the note: {note!r}"
        )

    # The live half, now explicit about when it has nothing to say.
    answer = await _run_once(BRCA1_DISEASE_QUESTION)
    _assert_answered(answer)

    leaked = _FINDINGS_ACCOUNTING.findall(answer.narrative)
    assert not leaked, (
        f"internal findings accounting reached the reader: {leaked}"
        f"{answer.describe()}"
    )
    if "not covered in the summary above" not in answer.narrative:
        pytest.skip(
            "the live half of A5 had nothing to assert on: this run omitted "
            "no finding, so no disclosure was produced. The deterministic "
            "half above ran and passed. Recorded as a skip rather than a "
            "pass so a green run is never read as evidence the live path "
            "was exercised (F-6.2-04)"
        )
