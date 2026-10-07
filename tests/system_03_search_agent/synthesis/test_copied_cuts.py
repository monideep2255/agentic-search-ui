"""Card 101, round 3 (2026-10-06): a copied cut goes to the sentence check.

The owner's rule: code may hold a sentence back but never approves one on
its own; only the sentence check approves a sentence that is not the
record's own words. Round 2 sent every reworded sentence to the check, but
the strict copy path (`ground_claim`, containment) still showed any run of
record words with no check (round 2's adversary, A2-101-01 and 02):

- "Aspirin prevents colorectal cancer in adults" cut from "There is no
  evidence that aspirin prevents colorectal cancer in adults.";
- "Antibiotics are effective" cut from "... only when a bacterial infection
  is confirmed.";
- "Drug X reduces mortality [1] in men [1]" from "... in women but not in
  men".

Now a copied clause shows with no check only when it is a whole sentence of
its record, word for word (`grounding.is_whole_record_sentence`).

WHAT THIS FILE EXERCISES, offline, no model:

- Each cut above becomes a check candidate and is not shown on the first
  pass; the joined clauses are read joined.
- A whole record sentence still shows with no model call, and so does every
  row of the code-built listing, a semicolon title included.
- When the check cannot run or approves nothing, none of the cuts is shown
  and the whole sentence still is.
- A short record value wrapped in other words keeps today's path for now
  ("Ribavirin can cure bronchiolitis in babies" is still shown); the owner
  decides that one (`build_r3.md`).

Every arm was mutation-proven; each docstring names its mutation.
"""

from __future__ import annotations

import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness.harness import HarnessCallError
from system_03_search_agent.synthesis import grounding
from system_03_search_agent.synthesis.findings import (
    SynthFinding,
    build_structured_fallback_narrative,
)
from system_03_search_agent.synthesis.grounding import (
    SynthesisCandidate,
    extract_evidence_quotes,
    run_grounding_pass,
)


def _finding(ref: int, value: str, field: str = "abstract", entity: str = "Publication") -> SynthFinding:
    return SynthFinding(
        ref_index=ref,
        citation_id=f"c-{ref}",
        layer="layer_2_ncbi_api",
        tool="ncbi_efetch",
        field=field,
        field_value=value,
        source_url=f"https://pubmed.ncbi.nlm.nih.gov/{ref}/",
        entity_type=entity,
        curie=f"pubmed:{ref}",
    )


ASPIRIN_RECORD = "There is no evidence that aspirin prevents colorectal cancer in adults."
ANTIBIOTICS_RECORD = "Antibiotics are effective only when a bacterial infection is confirmed."
DRUG_X_RECORD = "Drug X reduces mortality in women but not in men."
WHOLE = "Treatment is usually symptomatic."
RECORD = _finding(1, f"{ASPIRIN_RECORD} {ANTIBIOTICS_RECORD} {DRUG_X_RECORD} {WHOLE}")
QUESTION = "Does aspirin prevent colorectal cancer, and do antibiotics work?"

ASPIRIN = "Aspirin prevents colorectal cancer in adults [1]."
ANTIBIOTICS = "Antibiotics are effective [1]."
JOINED = "Drug X reduces mortality [1] in men [1]."
WHOLE_COPY = "Treatment is usually symptomatic [1]."


def _first_pass(narrative: str, findings=None, question: str = QUESTION):
    sink: list[SynthesisCandidate] = []
    result = run_grounding_pass(
        narrative, findings or [RECORD], question=question, candidate_sink=sink
    )
    return sink, result


# ------------------------------------------------------- each cut is checked


@pytest.mark.parametrize(
    ("narrative", "record_sentence"),
    [(ASPIRIN, ASPIRIN_RECORD), (ANTIBIOTICS, ANTIBIOTICS_RECORD)],
    ids=["aspirin, head cut", "antibiotics, tail cut"],
)
def test_a_copied_cut_becomes_a_check_candidate(narrative: str, record_sentence: str) -> None:
    """MUTATION PROOF: `is_whole_record_sentence` returning True for every
    clause (code approving every copy again, as before round 3) turns both
    cases red: the cut is shown on the first pass and never collected."""
    claim = narrative.rsplit(" [", 1)[0]
    assert grounding.ground_claim(claim, RECORD.field_value), "populate-check: it is copied"

    sink, result = _first_pass(narrative)

    assert [candidate.sentence for candidate in sink] == [claim], sink
    assert sink[0].quotes == (record_sentence,), "the check reads the whole record sentence"
    assert not result.grounded, result.narrative


def test_two_copied_clauses_are_read_joined() -> None:
    """MUTATION PROOF: reading each clause alone (the candidate's sentence
    set to the clause, not the sentence up to it, in `_copied_clause_
    candidate`) turns this red: the check would never see "in men" joined
    to the claim it changes."""
    sink, result = _first_pass(JOINED)

    assert [candidate.sentence for candidate in sink] == [
        "Drug X reduces mortality",
        "Drug X reduces mortality in men",
    ], sink
    assert all(candidate.quotes == (DRUG_X_RECORD,) for candidate in sink), sink
    assert not result.grounded, result.narrative


def test_an_approved_cut_shows_and_the_fragment_rule_still_applies() -> None:
    narrative = f"{ANTIBIOTICS} only when a bacterial infection is confirmed [1]."
    sink, _ = _first_pass(narrative)
    assert len(sink) == 2, "populate-check: both cuts were asked about"
    approved = frozenset(candidate.key for candidate in sink)
    result = run_grounding_pass(
        narrative, [RECORD], question=QUESTION, verified_syntheses=approved
    )
    # The lowercase back half of a record sentence is still dropped by the
    # fragment rule (`_opens_on_record_fragment`), approved or not.
    assert result.sentences == ("Antibiotics are effective [1].",), result.sentences
    assert result.claims[0].evidence_quote is None, "an approved copy is still a copy"


# --------------------------------------------- whole sentences, no model call


@pytest.mark.parametrize(
    "narrative",
    [WHOLE_COPY, "treatment is usually symptomatic [1]", f'{WHOLE_COPY[:-5]} [1: "{WHOLE[:-1]}"].'],
    ids=["as written", "first letter and full stop changed", "with a quote"],
)
def test_a_whole_record_sentence_is_not_a_candidate(narrative: str) -> None:
    """MUTATION PROOF: `is_whole_record_sentence` returning False for every
    clause turns every case red: the copy becomes a candidate."""
    sink, result = _first_pass(narrative)
    assert sink == [], sink
    assert result.grounded


def test_the_code_built_listing_still_grounds_whole() -> None:
    """The structured fallback and the findings tail run this pass with no
    check at all, so every row they build must still be the record's own
    words: a one-sentence value with its label, each sentence of a longer
    one, and an OMIM title split at its semicolon.

    MUTATION PROOF: dropping the semicolon from `_WHOLE_SENTENCE_START` and
    `_WHOLE_SENTENCE_ENDS` turns this red: "GLUCOKINASE" and "GCK" are lost.
    """
    findings = [
        _finding(1, "Acute bronchiolitis.", field="title"),
        _finding(2, "GLUCOKINASE; GCK", field="title", entity="OMIM"),
        _finding(3, f"{ASPIRIN_RECORD} {WHOLE} Results: no harm was seen."),
    ]
    narrative = build_structured_fallback_narrative(findings)
    result = run_grounding_pass(narrative, findings)
    assert result.stripped_count == 0, (narrative, result.sentences)
    assert {claim.finding.ref_index for claim in result.claims} == {1, 2, 3}


# ------------------------------------------- the check cannot run: fail closed


class _Reply:
    def __init__(self, content: str) -> None:
        self.content = content


def _record_dispatch(monkeypatch, *, reply: str | None = None, raises: Exception | None = None):
    calls: list[object] = []

    async def fake_dispatch(*args, **kwargs):
        calls.append(args)
        if raises is not None:
            raise raises
        return _Reply(reply or "")

    monkeypatch.setattr(graph_module, "_dispatch_tier_call", fake_dispatch)
    return calls


async def _helper(narrative: str, budget_s: float = 30.0) -> grounding.GroundingResult:
    rewritten, quotes = extract_evidence_quotes(narrative)
    return await graph_module._ground_with_sentence_check(
        rewritten,
        [RECORD],
        question=QUESTION,
        evidence_quotes=quotes,
        harness=object(),
        trace_id="t-card101-r3",
        budget_s=budget_s,
    )


@pytest.fixture(autouse=True)
def _guard_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """The code default: the guard tier answers the check, one call."""
    monkeypatch.delenv("CLASSIFIER_PROVIDER", raising=False)


@pytest.mark.asyncio
async def test_a_whole_record_sentence_shows_without_a_call(monkeypatch) -> None:
    calls = _record_dispatch(monkeypatch, reply='{"supported": [1]}')
    result = await _helper(WHOLE_COPY)
    assert result.sentences == (WHOLE_COPY,), result.sentences
    assert calls == [], "a whole record sentence needs no model call"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reply", "raises", "budget_s"),
    [
        ('{"supported": []}', None, 30.0),
        ("not json", None, 30.0),
        (None, HarnessCallError("timed out", error_class="transient"), 30.0),
        (
            None,
            cost_control.QueryCapExceededError(
                "cap", query_cost_usd=1.0, query_cap_usd=1.0, estimated_call_cost_usd=0.1
            ),
            30.0,
        ),
        ('{"supported": [1, 2, 3, 4]}', None, 1.0),
    ],
    ids=["approves none", "unreadable", "call failed", "cost cap", "too little time"],
)
async def test_a_check_that_cannot_approve_shows_none_of_the_cuts(
    monkeypatch, reply, raises, budget_s
) -> None:
    """MUTATION PROOF: collecting a cut AND keeping it on the first pass
    (leaving `strict_ok` True after the candidate is collected, the shape a
    "show it unchecked when the check cannot run" fallback takes) turns
    every case red."""
    _record_dispatch(monkeypatch, reply=reply, raises=raises)
    result = await _helper(f"{WHOLE_COPY} {ASPIRIN} {ANTIBIOTICS} {JOINED}", budget_s=budget_s)
    assert result.sentences == (WHOLE_COPY,), result.sentences


@pytest.mark.asyncio
async def test_the_check_approving_the_cuts_shows_them(monkeypatch) -> None:
    calls = _record_dispatch(monkeypatch, reply='{"supported": [1, 2, 3, 4]}')
    result = await _helper(f"{WHOLE_COPY} {ASPIRIN} {ANTIBIOTICS} {JOINED}")
    assert len(calls) == 1, "every cut in the answer goes in the one check call"
    assert len(result.sentences) == 4, result.sentences


# ------------------------------------------------ not changed in this round


def test_a_wrapped_record_value_keeps_todays_path_for_now() -> None:
    """Pins the open owner decision, so changing it is a visible choice.

    A short value wrapped in the question's words still shows with no check:
    "Ribavirin can cure bronchiolitis in babies" (A2-101-03) and the correct
    gene sentence of the same shape alike. Live, the check held both back 3
    of 3 times, so sending wraps to it would also hide gene answers.

    MUTATION PROOF: removing the `_wraps_record_value` exemption in
    `run_grounding_pass` turns this red: both become candidates.
    """
    ribavirin = _finding(3, "Ribavirin", field="name", entity="Drug")
    disease = _finding(2, "Familial cancer of breast", field="name", entity="Disease")
    for narrative, finding, question in (
        ("Ribavirin can cure bronchiolitis in babies [3].", ribavirin,
         "Which drugs can cure bronchiolitis in babies?"),
        ("BRCA1 is associated with familial cancer of breast [2].", disease,
         "What diseases is BRCA1 associated with?"),
    ):
        sink, result = _first_pass(narrative, [finding], question)
        assert sink == [] and result.grounded, (narrative, sink)
