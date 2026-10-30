"""Card 17 fix round (2026-10-16): the lead-in pass runs on the order the reader sees.

Two arms:

- The unit arm builds the judge's reproduction of J-17-02 (card 111 leaves a
  sentence out of the prose, so the sentence above a switched one is another)
  and the lead pick's reordering (A-17-01, J-17-08a), against the two helpers
  `_prose_echo_positions` and `_prose_reading_order` that `_write_answer`
  hands to `name_switched_records`.
- The write arm drives the real `write_node` on two neutral papers and fails
  when the call to the pass is removed from the write step (J-17-03), or when
  it is moved ahead of the lead pick.

Every record is neutral and built here, never a test question.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.contracts.query import Query
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.synthesis.answer_layout import name_switched_records
from system_03_search_agent.synthesis.findings import SYNTH_SYSTEM_INSTRUCTION, SynthFinding
from system_03_search_agent.synthesis.grounding import GroundedClaim, GroundingResult

_VALLEY = "Valley floors."


def _finding(ref: int, page: int, field: str, value: str) -> SynthFinding:
    return SynthFinding(
        ref_index=ref,
        citation_id=f"c{ref}",
        layer="layer_2_ncbi_api",
        tool="ncbi_efetch",
        field=field,
        field_value=value,
        source_url=f"https://pubmed.ncbi.nlm.nih.gov/{page}/",
        entity_type="Publication",
    )


def _grounding(pairs: list[tuple[str, list[tuple[SynthFinding, str | None]]]]) -> GroundingResult:
    claims = [
        GroundedClaim(claim_text=sentence, finding=finding, evidence_quote=quote)
        for sentence, cited in pairs
        for finding, quote in cited
    ]
    sentences = tuple(sentence for sentence, _ in pairs)
    return GroundingResult(
        narrative=" ".join(sentences),
        claims=claims,
        stripped_count=0,
        refused=False,
        sentences=sentences,
        sentence_origins=tuple(range(len(sentences))),
    )


def _citations(findings: list[SynthFinding]) -> list[SimpleNamespace]:
    return [SimpleNamespace(display_index=f.ref_index, citation_id=f.citation_id) for f in findings]


def test_a_sentence_card_111_leaves_out_is_not_the_sentence_above() -> None:
    """J-17-02, the judge's reproduction. s1 repeats one title cited to two
    records, so card 111 leaves it out; the reader then sees s0 (page 1)
    directly above s2 (page 2). Judged in the pass's own order s2 shares page
    2 with s1 and ships bare; judged in the reading order it is led in."""
    lake = _finding(1, 1, "title", "Alpine lakes and glacier melt.")
    floor_a = _finding(2, 2, "title", _VALLEY)
    floor_b = _finding(4, 3, "title", _VALLEY)
    floor_a_text = _finding(3, 2, "abstract", "Cores show valleys filled with fine silt.")
    findings = [lake, floor_a, floor_a_text, floor_b]
    sentences = [
        ("Glacier melt feeds the high lakes [1].", [(lake, None)]),
        ("Valley floors [2] and Valley floors [4].", [(floor_a, None), (floor_b, None)]),
        (
            "Valleys like these hold fine silt [3].",
            [(floor_a_text, "Cores show valleys filled with fine silt")],
        ),
    ]
    grounding = _grounding(sentences)
    listing = ["Valley floors [2].", "Valley floors [4]."]

    left_out = graph_module._label_only_positions(
        grounding.sentences, _citations(findings), findings, listing
    )
    order = graph_module._prose_reading_order(
        grounding, None, _citations(findings), findings, listing
    )
    assert left_out == {1}
    assert order == [0, 2]

    _, in_pass_order = name_switched_records(grounding, findings)
    after, in_reading_order = name_switched_records(grounding, findings, order)

    assert in_pass_order == 0
    assert in_reading_order == 1
    # Two listed papers carry this title and neither record has a year, so the
    # words say "another paper titled" (A-17-02).
    assert after.sentences[2] == (
        'From another paper titled "Valley floors": ' + sentences[2][0]
    )
    assert after.sentences[:2] == grounding.sentences[:2]


def test_the_lead_sentence_is_first_in_the_reading_order_and_is_never_led_in() -> None:
    """A-17-01 and J-17-08a. The lead pick lifts s1 above s0: s1 opens the
    answer and gets no lead-in; s2 is judged against s0, the sentence it now
    follows, and a sentence that follows the lead is judged against it."""
    lake = _finding(1, 1, "title", "Alpine lakes and glacier melt.")
    core = _finding(2, 2, "title", "Lake sediment cores from northern valleys.")
    ice = _finding(3, 3, "title", "Glacial history.")
    findings = [lake, core, ice]
    grounding = _grounding(
        [
            ("Glacier melt feeds the high lakes [1].", [(lake, None)]),
            ("Valleys like these hold fine silt [2].", [(core, "Cores show valleys filled with silt")]),
            ("The ice is glacial here [3].", [(ice, "The ice is glacial")]),
        ]
    )
    order = graph_module._prose_reading_order(grounding, 1, [], findings, [])
    assert order == [1, 0, 2]

    after, named = name_switched_records(grounding, findings, order)

    assert named == 1
    assert after.sentences[1] == grounding.sentences[1]  # opens the answer, bare
    assert after.sentences[2].startswith('From the paper "Glacial history": ')
    # Without a lead, the same pass leads in s1 as well.
    _, no_lead = name_switched_records(grounding, findings, graph_module._prose_reading_order(grounding, None, [], findings, []))
    assert no_lead == 2


def test_every_sentence_stays_when_card_111_would_leave_none_and_no_lead_was_picked() -> None:
    lake = _finding(1, 1, "title", _VALLEY)
    other = _finding(2, 2, "title", _VALLEY)
    findings = [lake, other]
    grounding = _grounding([("Valley floors [1] and Valley floors [2].", [(lake, None), (other, None)])])
    citations = _citations(findings)
    listing = ["Valley floors [1].", "Valley floors [2]."]

    assert graph_module._prose_echo_positions(grounding, None, citations, findings, listing) == set()
    assert graph_module._prose_echo_positions(grounding, 0, citations, findings, listing) == {0}


# ---------------------------------------------------------------------------
# The write step.
# ---------------------------------------------------------------------------

_PAPERS = (
    ("11111111", "Alpine lakes and glacier melt"),
    ("22222222", "Lake sediment cores from northern valleys"),
)
_ABSTRACTS = {
    "11111111": "Glacier melt feeds the high lakes each summer. Lake levels peak in July.",
    "22222222": "Cores show valleys filled with fine silt. Silt layers record past floods.",
}


def _reply(lines: dict[int, str]) -> str:
    first = next(i for i, body in lines.items() if "Glacier melt feeds" in body)
    second = next(i for i, body in lines.items() if "Cores show valleys" in body)
    return (
        f"Glacier melt feeds the high lakes each summer [{first}]. "
        f'Valleys like these hold fine silt [{second}: "Cores show valleys filled with fine silt"].'
    )


def _fake_response(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


@pytest.fixture
def _write_env(monkeypatch: pytest.MonkeyPatch) -> None:
    import re

    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")
    finding_line = re.compile(r"^\[(\d+)\]\s+(.+)$", re.MULTILINE)

    async def _dispatch(*_args: object, **kwargs: object):
        messages = kwargs.get("messages") or []
        joined = "\n".join(m.get("content") or "" for m in messages)  # type: ignore[union-attr]
        if SYNTH_SYSTEM_INSTRUCTION in joined:
            lines = {int(i): body.strip() for i, body in finding_line.findall(joined)}
            return _fake_response(_reply(lines))
        return _fake_response("ok")

    monkeypatch.setattr(harness_module.litellm, "acompletion", AsyncMock(side_effect=_dispatch))
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )

    async def _approve(candidates, **_kwargs):
        return frozenset(candidate.key for candidate in candidates)

    monkeypatch.setattr(graph_module, "check_reworded_sentences", _approve)


def _state() -> dict[str, object]:
    from system_03_search_agent.harness.coordinator_worker import Finding
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput, NcbiEfetchRecord

    query = Query(
        text="What do these papers say about valleys and lakes?",
        session_id="session-card17",
        trace_id="trace-card17",
        user_id=None,
        audience_depth="researcher",
    )
    records = [
        NcbiEfetchRecord(
            id=pmid,
            db="pubmed",
            fields={"title": title, "abstract": _ABSTRACTS[pmid]},
            source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        )
        for pmid, title in _PAPERS
    ]
    output = NcbiEfetchOutput(
        status="ok", action="fetch", records=records, record_count=2, total_available=2, truncated=False
    )
    finding = Finding(
        call_id="ne-card17",
        tool="ncbi_efetch",
        layer="layer_2_api",
        source="structured_pass_through",
        structured_fields=graph_module._ncbi_efetch_output_to_structured_fields(
            output, "pubmed_abstracts"
        ),
        extracted_entities=None,
        normalized_ids=None,
        evidence_summary=None,
    )
    return {
        "query": query,
        "harness": harness_module.Harness(trace_id=query.trace_id),
        "seq": 0,
        "start_monotonic": time.monotonic(),
        "findings": [finding],
        "findings_count": 1,
        "layer2_raw_outputs": {"ne-card17": output},
        "topic_search_term": "valleys lakes",
    }


def _prose(result) -> list[str]:
    return [
        e.payload["text"]
        for e in result["events"]
        if e.type == "token" and e.payload["kind"] == "claim"
    ]


@pytest.mark.asyncio
async def test_the_write_step_names_the_paper_a_switched_sentence_comes_from(
    _write_env, monkeypatch
) -> None:
    """J-17-03. Mutation that turns this red: remove the call to
    `name_switched_records` from `_write_answer` (the second half of this test
    does it by replacing the name in `graph_module`)."""
    result = await graph_module.write_node(_state())
    led = [text for text in _prose(result) if text.startswith("From the paper ")]
    assert len(led) == 1, _prose(result)
    assert led[0].startswith(
        'From the paper "Lake sediment cores from northern valleys": Valleys like these hold fine silt'
    )

    monkeypatch.setattr(graph_module, "name_switched_records", lambda g, f, o=None: (g, 0))
    bare = await graph_module.write_node(_state())
    assert not [text for text in _prose(bare) if text.startswith("From ")], _prose(bare)


@pytest.mark.asyncio
async def test_the_lead_pick_sees_the_bare_sentences_and_a_picked_lead_is_not_led_in(
    _write_env, monkeypatch
) -> None:
    """J-17-08a. The pick is asked before the pass runs, so it sees develop's
    sentences; when it picks the switched sentence, that sentence opens the
    answer bare."""
    seen: list[tuple[str, ...]] = []

    async def _pick(harness, trace_id, question, model_grounding, budget_s, skip=frozenset()):
        seen.append(tuple(model_grounding.sentences))
        return 1

    monkeypatch.setattr(graph_module, "_lead_sentence_choice", _pick)
    result = await graph_module.write_node(_state())

    assert seen and not any(s.startswith("From ") for s in seen[0]), seen
    claims = _prose(result)
    assert claims, result
    assert claims[0].startswith("Valleys like these hold fine silt"), claims
    assert not any(text.startswith("From ") for text in claims), claims
