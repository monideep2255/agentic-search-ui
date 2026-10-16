"""Card 29 (2026-10-15): the one abstract sentence under a cited paper.

The owner's words: "Under each of the first five cited papers that have an
abstract, I see the one sentence of its own abstract that answers my
question, so I know why it was cited without opening it; later papers show
their title only, as today."

What this file pins, through the real Write step (`write_node`) with only the
models faked:

- One batched classifier call carries the first five papers with an
  abstract, started beside the writer; the sixth and later papers are never
  in it and show no sentence.
- A sentence is attached only when it is word for word inside its own
  paper's abstract.
- A late pick, a failed batch with no usable fallback, or the guard tier as
  the only classifier shows no sentence, and the paper looks as before.
- A citation the listing already sent without a sentence is sent again with
  it, and every surface keeps the later one (`updates_citation`).
- A paper's citation carries no `snippet` key value when nothing was picked.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.contracts.events import CitationPayload
from system_03_search_agent.contracts.query import Query
from system_03_search_agent.contracts.token_order import one_per_citation_id
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import decide as decide_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness.jev_client import (
    JevAnswer,
    JevBatchResult,
    JevCallError,
    JevResult,
)
from system_03_search_agent.synthesis import snippets as snippets_module
from system_03_search_agent.synthesis.findings import SYNTH_SYSTEM_INSTRUCTION, SynthFinding
from tests.system_03_search_agent.core.test_write_answer_structure import (
    _FINDING_LINE,
    _fake_response,
    _quoting_abstracts,
)
from tests.system_03_search_agent.core.test_write_completeness import _env  # noqa: F401

_QUESTION = "Does caffeine improve exercise performance?"


def _abstract(n: int) -> str:
    return (
        f"Background sentence number {n} describes the setting of the caffeine trial in detail. "
        f"Caffeine intake of three milligrams per kilogram improved performance in study {n}. "
        f"The authors of study {n} conclude that moderate doses are effective for athletes."
    )


def _pmid(n: int) -> str:
    return str(30000000 + n)


def _papers_state(count: int, *, with_abstract: set[int] | None = None) -> dict[str, object]:
    from system_03_search_agent.harness.coordinator_worker import Finding
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput, NcbiEfetchRecord

    with_abstract = set(range(count)) if with_abstract is None else with_abstract
    records = [
        NcbiEfetchRecord(
            id=_pmid(n),
            db="pubmed",
            fields={
                "title": f"Caffeine and exercise performance, study {n}",
                **({"abstract": _abstract(n)} if n in with_abstract else {}),
            },
            source_url=f"https://pubmed.ncbi.nlm.nih.gov/{_pmid(n)}/",
        )
        for n in range(count)
    ]
    output = NcbiEfetchOutput(
        status="ok",
        action="fetch",
        records=records,
        record_count=len(records),
        total_available=len(records),
        truncated=False,
    )
    finding = Finding(
        call_id="ne-snip",
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
    query = Query(
        text=_QUESTION,
        session_id="session-snippet",
        trace_id="trace-snippet",
        user_id=None,
        audience_depth="researcher",  # type: ignore[arg-type]
    )
    return {
        "query": query,
        "harness": harness_module.Harness(trace_id=query.trace_id),
        "seq": 0,
        "start_monotonic": time.monotonic(),
        "findings": [finding],
        "findings_count": 1,
        "layer2_raw_outputs": {"ne-snip": output},
        "topic_search_term": "caffeine AND exercise AND performance",
    }


def _models(monkeypatch: pytest.MonkeyPatch, *, quote_abstracts: bool = True) -> None:
    async def _dispatch(*_args: object, **kwargs: object):
        messages = kwargs.get("messages") or []
        joined = "\n".join(m.get("content") or "" for m in messages)  # type: ignore[union-attr]
        if SYNTH_SYSTEM_INSTRUCTION in joined:
            lines = {int(i): body.strip() for i, body in _FINDING_LINE.findall(joined)}
            if quote_abstracts:
                return _fake_response(_quoting_abstracts(lines))
            return _fake_response(" ".join(f"{body} [{i}]." for i, body in lines.items()))
        return _fake_response("not an option")

    monkeypatch.setattr(harness_module.litellm, "acompletion", AsyncMock(side_effect=_dispatch))
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )


def _batch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    choose: str = "s1",
    error: str | None = None,
    delay_s: float = 0.0,
) -> list[dict[str, object]]:
    """Fake the one batched Jev call; returns every request it received."""
    asked: list[dict[str, object]] = []

    async def _call(**kwargs: object) -> JevBatchResult:
        asked.append(kwargs)
        if delay_s:
            await asyncio.sleep(delay_s)
        if error is not None:
            raise JevCallError(f"Jev failed: {error}", reason=error)
        questions = kwargs["questions"]
        return JevBatchResult(
            resolved_model="typesafe/jev-1.13",
            answers={
                key: JevAnswer(choice=choose, confidence=0.9, probabilities={choose: 0.9})
                for key in questions  # type: ignore[attr-defined]
            },
            input_tokens=10,
            output_tokens=1,
            cost_usd=0.00002,
            latency_ms=300,
        )

    monkeypatch.setattr(snippets_module, "call_jev_batch", _call)
    return asked


def _single_jev(monkeypatch: pytest.MonkeyPatch, *, choose: str | None, error: str | None = None) -> None:
    """Fake the one-question Jev call every other decision goes through."""

    async def _call_jev(**kwargs: object) -> JevResult:
        if error is not None:
            raise JevCallError(f"Jev failed: {error}", reason=error)
        options = list(kwargs["options"])  # type: ignore[arg-type]
        pick = choose if choose in options else options[-1]
        return JevResult(
            resolved_model="typesafe/jev-1.13",
            choice=pick,
            confidence=0.9,
            probabilities={option: (0.9 if option == pick else 0.1) for option in options},
            input_tokens=10,
            output_tokens=1,
            cost_usd=0.00002,
            latency_ms=300,
        )

    monkeypatch.setattr(decide_module, "call_jev", _call_jev)


@pytest.fixture
def jev_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")
    _models(monkeypatch)
    _single_jev(monkeypatch, choose=None)


@pytest.fixture
def placement_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(graph_module, "_request_reads_placement", lambda _state: True)


def _citations(result: dict) -> list[dict]:
    return one_per_citation_id(e.payload for e in result["events"] if e.type == "citation")


def _snippets_by_url(result: dict) -> dict[str, str]:
    return {c["source_url"]: c["snippet"] for c in _citations(result) if c.get("snippet")}


def _url(n: int) -> str:
    return f"https://pubmed.ncbi.nlm.nih.gov/{_pmid(n)}/"


@pytest.mark.asyncio
async def test_every_cited_paper_with_an_abstract_gets_its_sentence_from_one_batched_call(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    asked = _batch(monkeypatch, choose="s1")

    result = await graph_module.write_node(_papers_state(5))

    assert len(asked) == 1, "one batched call, not one per paper"
    assert len(asked[0]["questions"]) == 5  # type: ignore[arg-type]
    shown = _snippets_by_url(result)
    assert set(shown) == {_url(n) for n in range(5)}, shown
    for n in range(5):
        assert shown[_url(n)] == (
            f"Caffeine intake of three milligrams per kilogram improved performance in study {n}."
        )
        assert shown[_url(n)] in _abstract(n)


def _cite(n: int) -> CitationPayload:
    return CitationPayload(
        citation_id=f"c{n}",
        display_index=n + 1,
        source="pubmed",
        source_id=_pmid(n),
        source_url=_url(n),
        layer="layer_2_api",
        field="abstract",
        claim_text="x",
        evidence_kind="primary_assertion",
        assertion_confidence="asserted",
        population_ancestry_context=None,
        license="public_domain_us_gov",
    )


def _abstract_finding(n: int) -> SynthFinding:
    return SynthFinding(
        ref_index=n + 1,
        citation_id=f"c{n}",
        layer="layer_2_api",
        tool="ncbi_efetch",
        field="abstract",
        field_value=_abstract(n),
        source_url=_url(n),
    )


@pytest.mark.asyncio
async def test_only_the_first_five_papers_are_ever_asked_about(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    asked = _batch(monkeypatch, choose="s1")
    harness = harness_module.Harness(trace_id="trace-cap")
    citations = [_cite(n) for n in range(8)]
    findings = [_abstract_finding(n) for n in range(8)]

    graph_module._start_snippet_pick(harness, "trace-cap", _QUESTION, citations, findings)
    attached = await graph_module._attach_snippets(harness, citations)

    assert len(asked) == 1 and len(asked[0]["questions"]) == 5  # type: ignore[arg-type]
    assert [bool(c.snippet) for c in attached] == [True] * 5 + [False] * 3


@pytest.mark.asyncio
async def test_a_paper_without_an_abstract_uses_no_slot_and_shows_nothing(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    _batch(monkeypatch, choose="s1")

    result = await graph_module.write_node(_papers_state(5, with_abstract={0, 2, 3, 4}))

    shown = _snippets_by_url(result)
    assert _url(1) not in shown
    assert set(shown) == {_url(n) for n in (0, 2, 3, 4)}, shown


@pytest.mark.asyncio
async def test_the_sentence_sits_on_the_papers_abstract_citation(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    _batch(monkeypatch, choose="s1")

    result = await graph_module.write_node(_papers_state(2))

    carriers = [c for c in _citations(result) if c.get("snippet")]
    assert carriers
    for citation in carriers:
        assert citation["field"] == "abstract", citation


@pytest.mark.asyncio
async def test_a_sentence_not_word_for_word_in_the_abstract_is_never_shown(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    _batch(monkeypatch, choose="s1")
    real_split = snippets_module.split_abstract_sentences
    monkeypatch.setattr(
        snippets_module,
        "split_abstract_sentences",
        lambda text: [sentence + " (reworded)" for sentence in real_split(text)],
    )

    result = await graph_module.write_node(_papers_state(3))

    assert _snippets_by_url(result) == {}


@pytest.mark.asyncio
async def test_a_late_pick_shows_nothing_and_the_answer_does_not_wait_for_it(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    _batch(monkeypatch, choose="s1", delay_s=5.0)
    monkeypatch.setattr(graph_module, "_LATE_DECISION_GRACE_S", 0.2)

    started = time.monotonic()
    result = await graph_module.write_node(_papers_state(3))

    assert _snippets_by_url(result) == {}
    assert time.monotonic() - started < 3.0
    assert any(e.type == "done" for e in result["events"])


@pytest.mark.asyncio
async def test_a_failed_batch_falls_back_to_the_seam_and_shows_what_it_picks(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    _batch(monkeypatch, error="http_error")
    _single_jev(monkeypatch, choose="s2")

    result = await graph_module.write_node(_papers_state(2))

    shown = _snippets_by_url(result)
    assert shown[_url(0)] == (
        "The authors of study 0 conclude that moderate doses are effective for athletes."
    )


@pytest.mark.asyncio
async def test_a_failed_batch_with_no_usable_fallback_shows_nothing(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    _batch(monkeypatch, error="timeout")
    _single_jev(monkeypatch, choose=None, error="timeout")

    result = await graph_module.write_node(_papers_state(2))

    assert _snippets_by_url(result) == {}
    assert any(e.type == "done" for e in result["events"])


@pytest.mark.asyncio
async def test_none_from_the_classifier_shows_nothing_and_the_field_stays_empty(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    _batch(monkeypatch, choose="none")

    result = await graph_module.write_node(_papers_state(2))

    assert _snippets_by_url(result) == {}
    for citation in _citations(result):
        assert citation.get("snippet") is None


@pytest.mark.asyncio
async def test_with_the_guard_tier_as_classifier_no_pick_is_asked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLASSIFIER_PROVIDER", raising=False)
    _models(monkeypatch)
    asked = _batch(monkeypatch, choose="s1")

    result = await graph_module.write_node(_papers_state(2))

    assert asked == []
    assert _snippets_by_url(result) == {}


@pytest.mark.asyncio
async def test_a_listing_citation_already_sent_is_sent_again_with_the_sentence(
    monkeypatch: pytest.MonkeyPatch, jev_on: None, placement_contract: None
) -> None:
    _batch(monkeypatch, choose="s1")
    # The writer quotes no abstract, so only the listing's title citations
    # exist, already sent before the pick came back.
    _models(monkeypatch, quote_abstracts=False)

    result = await graph_module.write_node(_papers_state(2))

    events = [e.payload for e in result["events"] if e.type == "citation"]
    by_id: dict[str, list[dict]] = {}
    for payload in events:
        by_id.setdefault(payload["citation_id"], []).append(payload)
    resent = [sends for sends in by_id.values() if len(sends) > 1]
    assert resent, "a listing citation must be sent again once its sentence is known"
    for sends in resent:
        assert sends[0].get("snippet") is None
        assert sends[-1]["snippet"]
    assert _snippets_by_url(result), "every surface keeps the later send"
