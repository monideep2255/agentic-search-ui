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

Round 4 (`build_r4.md`), the review's findings J3-101-01 to 06 and
A3-101-01 to 07:

- A record sentence starts only where the widener says one does: a colon
  label, a semicolon and an abbreviation's full stop are not breaks, so a
  copy that drops "RETRACTED:", "; however, ..." or "e.g." is a cut.
- A record question copied as a statement, and a copy with the record's
  quote marks or brackets left off, are cuts.
- The code-built listing keeps its rows through its own path, a semicolon
  split and a sentence opening on "But" included.
- Once a sentence holds a cut, every later copied clause is read joined to
  it, from every record it cites.
- A held cut never turns a sentence develop dropped whole into a fragment.

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
    render_finding_body,
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
    """The structured fallback, the findings tail and the repair probe run
    this pass with no check at all, so every row they build must still
    show: a one-sentence value with its label, each sentence of a longer
    one, an OMIM title split at its semicolon, and a sentence opening on a
    colon label. They
    stay whole through the listing's own path (`code_built_listing`), never
    through the writer's whole-sentence test.

    MUTATION PROOF: ignoring `code_built_listing` (`_is_code_built_row`
    never consulted) turns this red: "GLUCOKINASE" and "GCK", cut at the
    semicolon, are lost.
    """
    findings = [
        _finding(1, "Acute bronchiolitis.", field="title"),
        _finding(2, "GLUCOKINASE; GCK", field="title", entity="OMIM"),
        _finding(3, f"{ASPIRIN_RECORD} {WHOLE} Results: no harm was seen."),
    ]
    narrative = build_structured_fallback_narrative(findings)
    result = run_grounding_pass(narrative, findings, code_built_listing=True)
    assert result.stripped_count == 0, (narrative, result.sentences)
    assert {claim.finding.ref_index for claim in result.claims} == {1, 2, 3}
    assert "GLUCOKINASE [2]." in result.sentences, result.sentences


@pytest.mark.parametrize("connective", ["But", "And", "Then", "Or"])
def test_the_listing_keeps_a_record_sentence_opening_on_a_connective(connective: str) -> None:
    """J3-101-04: develop's listing showed "But bleeding increased in older
    adults." (its "But" dropped, as `_clean_claim` always drops it); round 3
    lost the row, because the whole-sentence test read the claim after the
    connective was stripped. The listing shows it exactly as develop does.

    MUTATION PROOF: testing only the stripped claim (`_clean_claim(text)`
    instead of `text`, in `is_whole_record_sentence` and
    `_is_code_built_row`) turns every case red: the second row is lost.
    """
    finding = _finding(1, f"Aspirin was well tolerated. {connective} bleeding increased in older adults.")
    narrative = build_structured_fallback_narrative([finding])
    result = run_grounding_pass(narrative, [finding], code_built_listing=True)
    assert result.sentences == (
        "Aspirin was well tolerated [1].",
        "Bleeding increased in older adults [1].",
    ), result.sentences


def test_a_writers_copy_of_a_sentence_opening_on_but_is_whole() -> None:
    """The writer's exact copy of the same record sentence needs no check.

    MUTATION PROOF: the same mutation as the listing arm above turns this
    red: the copy becomes a candidate.
    """
    finding = _finding(1, "Bronchodilators are widely used. But they do not improve oxygen saturation.")
    narrative = "Bronchodilators are widely used [1]. But they do not improve oxygen saturation [1]."
    sink, result = _first_pass(narrative, [finding])
    assert sink == [], sink
    assert len(result.sentences) == 2, result.sentences


# ------------------------------------------- round 4: where a sentence starts


def _assert_a_cut(narrative: str, finding: SynthFinding, record_sentence: str, question: str = QUESTION):
    claim = narrative.rsplit(" [", 1)[0]
    assert grounding.ground_claim(claim, finding.field_value), "populate-check: it is copied"
    sink, result = _first_pass(narrative, [finding], question)
    assert [candidate.sentence for candidate in sink] == [claim], sink
    assert sink[0].quotes == (record_sentence,), "the check reads the whole record sentence"
    assert not result.grounded, result.narrative


@pytest.mark.parametrize(
    ("value", "narrative", "record_sentence"),
    [
        (
            "RETRACTED: Drug X cures cancer in mice.",
            "Drug X cures cancer in mice [1].",
            "RETRACTED: Drug X cures cancer in mice.",
        ),
        (
            "Myth: antibiotics treat viral bronchiolitis. Fact: they do not.",
            "Antibiotics treat viral bronchiolitis [1].",
            "Myth: antibiotics treat viral bronchiolitis.",
        ),
        (
            "Hypothesis: aspirin prevents colorectal cancer in adults. Results: no effect was found.",
            "Aspirin prevents colorectal cancer in adults [1].",
            "Hypothesis: aspirin prevents colorectal cancer in adults.",
        ),
        (
            "Do not: give antibiotics routinely; use bronchodilators.",
            "Give antibiotics routinely [1].",
            "Do not: give antibiotics routinely; use bronchodilators.",
        ),
        (
            "Results: no serious harm was seen in either group.",
            "No serious harm was seen in either group [1].",
            "Results: no serious harm was seen in either group.",
        ),
    ],
    ids=["retracted", "myth", "hypothesis", "do not", "faithful results label"],
)
def test_a_copy_after_a_colon_label_goes_to_the_check(value: str, narrative: str, record_sentence: str) -> None:
    """J3-101-01, A3-101-01: a colon is not a sentence start. The faithful
    "Results:" copy goes to the check too; the check approves it (live,
    `build_r4.md`).

    MUTATION PROOF: splitting record sentences after a colon as well
    (`_record_sentences` also breaking at ": ") turns every case red but
    "do not", which is a cut at a semicolon too."""
    _assert_a_cut(narrative, _finding(1, value, field="title"), record_sentence)


@pytest.mark.parametrize(
    ("value", "narrative"),
    [
        (
            "Drug X is safe in children; however, it caused deaths in infants under 6 months.",
            "Drug X is safe in children [1].",
        ),
        (
            "Aspirin reduced colorectal cancer incidence; however, this was not seen in randomized trials.",
            "Aspirin reduced colorectal cancer incidence [1].",
        ),
        ("GLUCOKINASE; GCK", "GLUCOKINASE [1]."),
    ],
    ids=["however", "aspirin", "a listing row, copied by the writer"],
)
def test_a_copy_up_to_a_semicolon_goes_to_the_check(value: str, narrative: str) -> None:
    """J3-101-02, A3-101-06: a semicolon is not a sentence end for the
    writer's copy; only the code-built listing splits there.

    MUTATION PROOF: splitting record sentences at a semicolon too
    (`_record_sentences` also breaking at "; ") turns every case red."""
    _assert_a_cut(narrative, _finding(1, value), value)


@pytest.mark.parametrize(
    ("value", "narrative"),
    [
        (
            "Several popular claims lack support, e.g. aspirin prevents colorectal cancer.",
            "Aspirin prevents colorectal cancer [1].",
        ),
        (
            "Mortality fell in the U.S. but rose sharply in every other country studied.",
            "Mortality fell in the U.S [1].",
        ),
        (
            "Benefit was seen in patients aged 50 to 70 yrs. but not in older adults.",
            "Benefit was seen in patients aged 50 to 70 yrs [1].",
        ),
        (
            "The trial did not show that drug X vs. placebo reduces mortality in adults.",
            "Placebo reduces mortality in adults [1].",
        ),
        (
            "It is often claimed, though unproven, that approx. 30% of infants respond to bronchodilators.",
            "30% of infants respond to bronchodilators [1].",
        ),
    ],
    ids=["e.g.", "U.S.", "yrs.", "vs.", "approx."],
)
def test_a_cut_at_an_abbreviation_goes_to_the_check(value: str, narrative: str) -> None:
    """J3-101-03, A3-101-03: a full stop with no capital after it is not a
    sentence boundary, the rule the widener already uses.

    MUTATION PROOF: dropping the capital lookahead from the boundary
    `_record_sentences` splits on turns every case red."""
    _assert_a_cut(narrative, _finding(1, value), value)


@pytest.mark.parametrize(
    ("value", "narrative", "record_sentence"),
    [
        (
            "Vitamin D supplementation prevents bronchiolitis in infants?",
            "Vitamin D supplementation prevents bronchiolitis in infants [1].",
            "Vitamin D supplementation prevents bronchiolitis in infants?",
        ),
        (
            "Is it true? Nebulized epinephrine reduces admissions? No.",
            "Nebulized epinephrine reduces admissions [1].",
            "Nebulized epinephrine reduces admissions?",
        ),
    ],
    ids=["question title", "question in an abstract"],
)
def test_a_record_question_copied_as_a_statement_goes_to_the_check(
    value: str, narrative: str, record_sentence: str
) -> None:
    """A3-101-02: "X prevents Y?" shown as "X prevents Y." is the app's
    statement, not the record's.

    MUTATION PROOF: removing the question-mark rule in
    `is_whole_record_sentence` turns both cases red."""
    _assert_a_cut(narrative, _finding(1, value, field="title"), record_sentence)


@pytest.mark.parametrize(
    ("value", "narrative"),
    [
        (
            'Advertisements stated: "Drug X cures cancer." Regulators found this claim false.',
            "Drug X cures cancer [1].",
        ),
        (
            '"Vaccines cause autism." This myth persists despite a retracted study.',
            "Vaccines cause autism [1].",
        ),
        (
            "Ribavirin was ineffective in the trial. (Ribavirin was effective.) An earlier report claimed otherwise.",
            "Ribavirin was effective [1].",
        ),
    ],
    ids=["quoted in a sentence", "quoted sentence", "bracketed sentence"],
)
def test_a_copy_with_its_quote_marks_or_brackets_left_off_goes_to_the_check(
    value: str, narrative: str
) -> None:
    """A3-101-04: a sentence the record quotes or brackets is a mention, so
    a copy that drops the marks is not the record's own sentence.

    MUTATION PROOF: round 3's rule, a break allowed after a closing quote
    mark or bracket and the marks stripped from each record sentence, turns
    the quoted and the bracketed sentence red. The quote inside a sentence
    is held by the colon rule as well."""
    claim = narrative.rsplit(" [", 1)[0]
    sink, result = _first_pass(narrative, [_finding(1, value)])
    assert [candidate.sentence for candidate in sink] == [claim], sink
    assert not result.grounded, result.narrative


def test_the_whole_sentence_match_is_case_sensitive() -> None:
    """J3-101-06: only the first letter's case may differ.

    MUTATION PROOF: comparing everything after the first letter without
    case (`claim[1:].lower() == record[1:].lower()` in
    `_same_but_first_letter`) turns this red: the copy shows unchecked."""
    narrative = "Treatment is usually Symptomatic [1]."
    sink, result = _first_pass(narrative)
    assert [candidate.sentence for candidate in sink] == ["Treatment is usually Symptomatic"], sink
    assert not result.grounded, result.narrative


def test_a_cut_opening_on_a_bare_verdict_is_held_by_code() -> None:
    """J3-101-06: "Yes, ..." cut from a record sentence is held back by code,
    with no check item.

    MUTATION PROOF: `held_by_code = False` turns this red: the cut becomes a
    candidate."""
    finding = _finding(
        1, "Is aspirin effective? Yes, aspirin prevents colorectal cancer in adults, but only at high doses."
    )
    narrative = "Yes, aspirin prevents colorectal cancer in adults [1]."
    assert grounding.ground_claim(narrative[:-5], finding.field_value), "populate-check: it is copied"
    sink, result = _first_pass(narrative, [finding])
    assert sink == [], sink
    assert not result.grounded, result.narrative


# ------------------------------------- round 4: what the check reads, joined


CHILDREN = _finding(2, "Children", field="population", entity="Population")
HEART = _finding(1, "Drug X reduces mortality in adults with heart failure.")
CHILDREN_QUESTION = "Does drug X reduce mortality in children?"


def test_a_copied_clause_after_a_cut_is_read_joined_from_every_record() -> None:
    """J3-101-05 and J3-101-06: the shown sentence "Drug X reduces mortality
    in children" is what the check reads, with both records' text.

    MUTATION PROOF: (a) dropping `or cut_in_sentence` turns this red: the
    wrapped "in children" is never asked about; (b) keeping only the last
    clause's record text (`spans[-1:]` in `_copied_clause_candidate`) turns
    it red: the heart-failure sentence is missing from the joined item."""
    narrative = "Drug X reduces mortality [1] in children [2]."
    sink, result = _first_pass(narrative, [HEART, CHILDREN], CHILDREN_QUESTION)
    assert [candidate.sentence for candidate in sink] == [
        "Drug X reduces mortality",
        "Drug X reduces mortality in children",
    ], sink
    assert sink[1].quotes == (HEART.field_value, render_finding_body(CHILDREN)), sink[1].quotes
    assert not result.grounded, result.narrative


@pytest.mark.parametrize(
    ("approve", "shown"),
    [
        ((), ()),
        ((0,), ("Drug X reduces mortality [1].",)),
        ((0, 1), ("Drug X reduces mortality [1] in children [2].",)),
    ],
    ids=["none approved", "the cut alone approved", "both approved"],
)
def test_only_what_the_check_read_is_shown(approve: tuple[int, ...], shown: tuple[str, ...]) -> None:
    """Whatever is shown ending at a clause is exactly an item the check
    approved.

    MUTATION PROOF: dropping `or cut_in_sentence` turns "the cut alone
    approved" red: "in children" is joined on unchecked."""
    narrative = "Drug X reduces mortality [1] in children [2]."
    findings = [HEART, CHILDREN]
    sink, _ = _first_pass(narrative, findings, CHILDREN_QUESTION)
    approved = frozenset(sink[index].key for index in approve)
    result = run_grounding_pass(
        narrative, findings, question=CHILDREN_QUESTION, verified_syntheses=approved
    )
    assert result.sentences == shown, result.sentences


def test_a_whole_record_sentence_after_a_cut_is_read_joined() -> None:
    """A whole record sentence joined after a cut is asked about too, as the
    sentence up to it.

    MUTATION PROOF: dropping `or cut_in_sentence` turns this red."""
    whole = _finding(2, WHOLE)
    narrative = "Drug X reduces mortality [1], and treatment is usually symptomatic [2]."
    sink, _ = _first_pass(narrative, [HEART, whole], CHILDREN_QUESTION)
    assert [candidate.sentence for candidate in sink] == [
        "Drug X reduces mortality",
        "Drug X reduces mortality, and treatment is usually symptomatic",
    ], sink


# ----------------------------------------- round 4: no leftover fragment


@pytest.mark.parametrize("approve_all", [False, True], ids=["check holds", "check approves"])
def test_a_held_cut_never_leaves_a_fragment_develop_dropped(approve_all: bool) -> None:
    """A3-101-07: develop dropped this sentence whole (its middle clause
    is invented). Round 3 showed "Ribavirin [1]." when the check held the
    cut after it. Now nothing shows, whatever the check says.

    MUTATION PROOF: counting only kept clauses in the middle-strip rule
    (dropping the `held_for_check` term) turns both cases red: the first
    pass, the check not yet asked, shows "Ribavirin [1]." again."""
    findings = [
        _finding(1, "Ribavirin", field="name", entity="Drug"),
        _finding(2, "Palivizumab is not approved for treatment."),
        _finding(3, "Montelukast showed no benefit in infants with bronchiolitis."),
    ]
    narrative = (
        "Ribavirin [1] is first-line care, unlike palivizumab which is withdrawn [2], "
        "and montelukast showed no benefit in infants [3]."
    )
    sink, first = _first_pass(narrative, findings, "How is bronchiolitis in babies treated?")
    assert len(sink) == 1, "populate-check: the last clause is a cut sent to the check"
    approved = frozenset(candidate.key for candidate in sink) if approve_all else frozenset()
    result = run_grounding_pass(
        narrative,
        findings,
        question="How is bronchiolitis in babies treated?",
        verified_syntheses=approved,
    )
    assert first.sentences == () and result.sentences == (), (first.sentences, result.sentences)


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
