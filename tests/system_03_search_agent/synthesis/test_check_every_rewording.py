"""Card 101 (2026-10-06): every reworded sentence goes to the sentence check.

The owner's decision, on `testing/Developer/reports/2026-10-06_card101/
diagnosis.md`: code may still hold a reworded sentence back, but never
approves one on its own. Before it, code's word check
(`grounding.synthesis_is_supported_by`) approved a sentence whose every
word sat in its quote, the record's title, the question or the reporting
vocabulary, and the model never read it. In run hb4 that showed "For babies
with severe bronchiolitis, use of a high-flow nasal cannula is becoming
common" where the paper says children: "babies" came from the question.

WHAT THIS FILE EXERCISES, offline, no model:

- hb4's sentence, rebuilt from the diagnosis: code's word check would still
  approve it (populate-check), and it now becomes a check candidate and is
  not shown on the first pass.
- A copied record sentence still shows with no model call, with or without
  a quote attached.
- When the check cannot run or approves nothing, none of the sentences
  that moved to it is shown, and the copied sentence still is.
- The completeness repair reply goes through the same two passes: its
  rewording is shown only when the check approved it.

Every arm was mutation-proven; each docstring names its mutation.

WHAT IT DELIBERATELY OMITS: what the live model decides. That is measured
by the live runs in the card's build report, not here.
"""

from __future__ import annotations

import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness.harness import HarnessCallError
from system_03_search_agent.synthesis import grounding
from system_03_search_agent.synthesis.findings import SynthFinding
from system_03_search_agent.synthesis.grounding import (
    SynthesisCandidate,
    extract_evidence_quotes,
    run_grounding_pass,
)
from system_03_search_agent.synthesis.sentence_check import SentenceCheckUnreadable

# hb4's record, the public abstract of PubMed 24093893, as the diagnosis
# quotes it, and its title on the same page.
_URL = "https://pubmed.ncbi.nlm.nih.gov/24093893/"
_ABSTRACT = (
    "Bronchiolitis is the most common lower respiratory tract infection to affect infants "
    "and toddlers. Bronchiolitis is a self-limited disease in healthy infants and children. "
    "Treatment is usually symptomatic, and the goal of therapy is to maintain adequate "
    "oxygenation and hydration. Use of a high-flow nasal cannula is becoming common for "
    "children with severe bronchiolitis."
)
ABSTRACT = SynthFinding(
    ref_index=22,
    citation_id="c-22",
    layer="layer_2_ncbi_api",
    tool="ncbi_efetch",
    field="abstract",
    field_value=_ABSTRACT,
    source_url=_URL,
    entity_type="Publication",
    curie="pubmed:24093893",
)
TITLE = SynthFinding(
    ref_index=13,
    citation_id="c-13",
    layer="layer_2_ncbi_api",
    tool="ncbi_efetch",
    field="title",
    field_value="Acute bronchiolitis.",
    source_url=_URL,
    entity_type="Publication",
    curie="pubmed:24093893",
)
FINDINGS = [ABSTRACT, TITLE]
QUESTION = "What causes bronchiolitis in babies, and how is it usually treated?"

COPIED = "Bronchiolitis is the most common lower respiratory tract infection to affect infants and toddlers [22]."
BABIES = "For babies with severe bronchiolitis, use of a high-flow nasal cannula is becoming common"
BABIES_QUOTE = "use of a high-flow nasal cannula is becoming common for children with severe bronchiolitis"
HB4 = f'{COPIED} {BABIES} [22: "{BABIES_QUOTE}"].'


def _first_pass(narrative: str) -> tuple[list[SynthesisCandidate], grounding.GroundingResult]:
    sink: list[SynthesisCandidate] = []
    result = run_grounding_pass(narrative, FINDINGS, question=QUESTION, candidate_sink=sink)
    return sink, result


# ------------------------------------------------------------ hb4's sentence


def test_the_babies_sentence_becomes_a_check_candidate() -> None:
    """MUTATION PROOF: restoring code's approval in `run_grounding_pass`
    (`synthesized = not strict_ok and bool(pairs) and
    synthesis_is_supported_by(...)`) turns this red: the sentence is shown
    on the first pass and never collected."""
    licensed = grounding._licensed_question_content(QUESTION)
    assert grounding.synthesis_is_supported_by(
        BABIES, [(BABIES_QUOTE, ABSTRACT)], licensed, TITLE.field_value
    ), "populate-check: code's word check must still approve it, or this arm tests nothing"
    assert not grounding.ground_claim(BABIES, _ABSTRACT), "populate-check: it is a rewording"

    sink, result = _first_pass(HB4)

    assert [candidate.sentence for candidate in sink] == [BABIES], sink
    assert "babies" not in result.narrative, result.narrative
    assert result.narrative.startswith("Bronchiolitis is the most common"), result.narrative


def test_the_babies_sentence_shows_only_with_the_checks_approval() -> None:
    sink, _ = _first_pass(HB4)
    approved = run_grounding_pass(
        HB4, FINDINGS, question=QUESTION, verified_syntheses=frozenset({sink[0].key})
    )
    assert BABIES in approved.narrative
    assert approved.claims[-1].evidence_quote == BABIES_QUOTE


# ------------------------------------------- copied record words, no call


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
        FINDINGS,
        question=QUESTION,
        evidence_quotes=quotes,
        harness=object(),
        trace_id="t-card101",
        budget_s=budget_s,
    )


@pytest.fixture(autouse=True)
def _guard_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """The code default: the guard tier answers the check, one call."""
    monkeypatch.delenv("CLASSIFIER_PROVIDER", raising=False)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "narrative",
    [
        COPIED,
        (
            "Treatment is usually symptomatic, and the goal of therapy is to maintain adequate "
            'oxygenation and hydration [22: "Treatment is usually symptomatic"].'
        ),
    ],
    ids=["no quote", "with a quote"],
)
async def test_a_copied_record_sentence_shows_without_a_call(monkeypatch, narrative: str) -> None:
    """MUTATION PROOF: dropping `not strict_ok` from the candidate condition
    in `run_grounding_pass` sends the quoted copy to the check, and the
    "with a quote" case goes red on the call count."""
    calls = _record_dispatch(monkeypatch, reply='{"supported": [1]}')
    result = await _helper(narrative)
    assert result.grounded, result
    assert calls == [], "a copied record sentence needs no model call"


# ------------------------------------------- the check cannot run: fail closed


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
        ('{"supported": [1]}', None, 1.0),
    ],
    ids=["approves none", "unreadable", "call failed", "cost cap", "too little time"],
)
async def test_a_check_that_cannot_approve_shows_none_of_the_moved_sentences(
    monkeypatch, reply, raises, budget_s
) -> None:
    """MUTATION PROOF: collecting the sentence AND accepting it on code's
    word check in the same first pass (the shape a "show it unchecked when
    the check cannot run" fallback would take) turns every case red."""
    _record_dispatch(monkeypatch, reply=reply, raises=raises)
    result = await _helper(HB4, budget_s=budget_s)
    assert "babies" not in result.narrative, result.narrative
    assert result.narrative.startswith("Bronchiolitis is the most common"), (
        "the copied sentence still shows"
    )


@pytest.mark.asyncio
async def test_the_check_approving_it_shows_it(monkeypatch) -> None:
    calls = _record_dispatch(monkeypatch, reply='{"supported": [1]}')
    result = await _helper(HB4)
    assert len(calls) == 1
    assert BABIES in result.narrative


# ------------------------------------------------ the completeness repair


def _repair_state(monkeypatch):
    """A plain-language answer over two graph diseases and one paper; the
    first draft reports the diseases only, so the repair runs (the same
    state and environment `test_write_completeness.py` uses)."""
    from tests.system_03_search_agent.core import test_write_completeness as completeness

    monkeypatch.setenv("GUARD_MODEL", completeness._GUARD_MODEL)
    monkeypatch.setenv("PLAN_MODEL", completeness._PLAN_MODEL)
    monkeypatch.setenv("SYNTH_MODEL", completeness._SYNTH_MODEL)
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")
    return completeness, completeness._paper_write_state("plain_language")


_REWORDED_RISK = "By age 80 years, female BRCA1 carriers had a cumulative breast cancer risk of 72%"
_RISK_QUOTE = "Female BRCA1 carriers had a cumulative breast cancer risk of 72% by age 80 years"


def _install_repair_writer(monkeypatch, completeness) -> None:
    """The first draft copies the disease lines; the repair copies them too
    and adds one rewording of the abstract that code's word check would
    have approved alone."""
    from unittest.mock import AsyncMock

    from system_03_search_agent.harness import harness as harness_module
    from system_03_search_agent.synthesis.findings import SYNTH_SYSTEM_INSTRUCTION

    async def _dispatch(*_args, **kwargs):
        messages = kwargs.get("messages") or []
        joined = "\n".join(m.get("content") or "" for m in messages)
        lines = completeness._FINDING_LINE.findall(joined)
        diseases = {int(index) for index, body in lines if "disease name number" in body}
        first = completeness._narrative_covering(joined, diseases)
        if completeness._CORRECTION_MARKER in joined:
            paper = next(int(index) for index, body in lines if "72%" in body)
            return completeness._fake_response(
                f'{first} {_REWORDED_RISK} [{paper}: "{_RISK_QUOTE}"].'
            )
        if SYNTH_SYSTEM_INSTRUCTION in joined:
            return completeness._fake_response(first)
        return completeness._fake_response("ok")

    monkeypatch.setattr(harness_module.litellm, "acompletion", AsyncMock(side_effect=_dispatch))
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )


def _fake_check(monkeypatch, *, approve: bool) -> list[list[str]]:
    seen: list[list[str]] = []

    async def fake_check(candidates, **_kwargs):
        seen.append([candidate.sentence for candidate in candidates])
        if not approve:
            raise SentenceCheckUnreadable("stand-in for any check failure")
        return frozenset(candidate.key for candidate in candidates)

    monkeypatch.setattr(graph_module, "check_reworded_sentences", fake_check)
    return seen


def _shown(result) -> str:
    return "".join(event.payload["text"] for event in result["events"] if event.type == "token")


@pytest.mark.asyncio
async def test_the_repairs_rewording_goes_to_the_check_and_is_hidden_when_it_fails(
    monkeypatch,
) -> None:
    """MUTATION PROOF: restoring code's approval (as in the first arm) turns
    this red: the check is never asked and the rewording is shown."""
    completeness, state = _repair_state(monkeypatch)
    _install_repair_writer(monkeypatch, completeness)
    seen = _fake_check(monkeypatch, approve=False)

    result = await graph_module.write_node(state)

    assert any(_REWORDED_RISK in sentence for batch in seen for sentence in batch), seen
    assert "By age 80 years" not in _shown(result)


@pytest.mark.asyncio
async def test_the_repairs_rewording_shows_when_the_check_approves_it(monkeypatch) -> None:
    """MUTATION PROOF: grounding the repair reply with a plain
    `run_grounding_pass` in place of `_ground_with_sentence_check` in
    `core/graph.py` turns this red: the approved rewording is not shown."""
    completeness, state = _repair_state(monkeypatch)
    _install_repair_writer(monkeypatch, completeness)
    seen = _fake_check(monkeypatch, approve=True)

    result = await graph_module.write_node(state)

    assert seen, "populate-check: the repair's rewording reached the check"
    assert "By age 80 years" in _shown(result), _shown(result)
