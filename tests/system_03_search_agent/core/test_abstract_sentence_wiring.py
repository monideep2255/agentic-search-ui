"""Card 29 (2026-10-15): the one abstract sentence under a cited paper.

The owner's words: "Under each of the first five cited papers that have an
abstract, I see the one sentence of its own abstract that answers my
question, so I know why it was cited without opening it; later papers show
their title only, as today."

What this file pins, through the real Write step (`write_node`) with only the
models faked:

- Each of the first five papers with an abstract gets its own classifier
  decision, started together beside the writer; the sixth and later papers
  are never asked and show no sentence. Each decision reaches
  `done.decisions`.
- A paper PubMed marks retracted, or whose abstract carries a retraction
  notice, is never asked about and shows no sentence.
- A sentence cut short when an abstract was trimmed is never offered or
  shown.
- A sentence is attached only when it is word for word inside its own
  paper's abstract.
- A late pick, a failed batch with no usable fallback, or the guard tier as
  the only classifier shows no sentence, and the paper looks as before.
- A citation the listing already sent without a sentence is sent again with
  it, and every surface keeps the later one (`updates_citation`).
- A citation with no sentence has no `snippet` key at all.
- The pick is cancelled on every way out of `write_node`, and the grace
  never waits past the write budget.
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
from system_03_search_agent.harness.jev_client import JevCallError, JevResult
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


def _papers_state(
    count: int,
    *,
    with_abstract: set[int] | None = None,
    retracted: set[int] | None = None,
    abstracts: dict[int, str] | None = None,
) -> dict[str, object]:
    from system_03_search_agent.harness.coordinator_worker import Finding
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput, NcbiEfetchRecord

    with_abstract = set(range(count)) if with_abstract is None else with_abstract
    records = [
        NcbiEfetchRecord(
            id=_pmid(n),
            db="pubmed",
            fields={
                "title": f"Caffeine and exercise performance, study {n}",
                **(
                    {"abstract": (abstracts or {}).get(n, _abstract(n))}
                    if n in with_abstract
                    else {}
                ),
                **({"retracted": True} if n in (retracted or set()) else {}),
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


def _models(
    monkeypatch: pytest.MonkeyPatch, *, quote_abstracts: bool = True, guard_pick: str | None = None
) -> None:
    async def _dispatch(*_args: object, **kwargs: object):
        messages = kwargs.get("messages") or []
        joined = "\n".join(m.get("content") or "" for m in messages)  # type: ignore[union-attr]
        if SYNTH_SYSTEM_INSTRUCTION in joined:
            lines = {int(i): body.strip() for i, body in _FINDING_LINE.findall(joined)}
            if quote_abstracts:
                return _fake_response(_quoting_abstracts(lines))
            return _fake_response(" ".join(f"{body} [{i}]." for i, body in lines.items()))
        if guard_pick is not None and snippets_module._INSTRUCTIONS[:60] in joined:
            return _fake_response(guard_pick)
        return _fake_response("not an option")

    monkeypatch.setattr(harness_module.litellm, "acompletion", AsyncMock(side_effect=_dispatch))
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )


def _jev(
    monkeypatch: pytest.MonkeyPatch,
    *,
    choose: str | None = "s1",
    error: str | None = None,
    delay_s: float = 0.0,
) -> list[dict[str, object]]:
    """Fake the one-question Jev call every decision goes through; returns
    every request it received (one per decision)."""
    asked: list[dict[str, object]] = []

    async def _call_jev(**kwargs: object) -> JevResult:
        if kwargs.get("question_key") == "write.snippet":
            asked.append(kwargs)
        if delay_s and kwargs.get("question_key") == "write.snippet":
            await asyncio.sleep(delay_s)
        if error is not None:
            raise JevCallError(f"Jev failed: {error}", reason=error)
        options = list(kwargs["options"])  # type: ignore[arg-type]
        if choose == "last":
            pick = options[-2]
        else:
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
    return asked


@pytest.fixture
def jev_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")
    _models(monkeypatch)


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
async def test_every_cited_paper_with_an_abstract_gets_its_own_decision_and_sentence(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    asked = _jev(monkeypatch, choose="s1")

    result = await graph_module.write_node(_papers_state(5))

    assert len(asked) == 5, "one decision per paper"
    done = next(e for e in result["events"] if e.type == "done")
    points = [d["name"] for d in done.payload["decisions"] if d["name"] == "write.snippet"]
    assert len(points) == 5, "each decision reaches done.decisions"
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
    asked = _jev(monkeypatch, choose="s1")
    harness = harness_module.Harness(trace_id="trace-cap")
    citations = [_cite(n) for n in range(8)]
    findings = [_abstract_finding(n) for n in range(8)]

    graph_module._start_snippet_pick(harness, "trace-cap", _QUESTION, citations, findings)
    attached = await graph_module._attach_snippets(harness, citations)

    assert len(asked) == 5
    assert [bool(c.snippet) for c in attached] == [True] * 5 + [False] * 3


@pytest.mark.asyncio
async def test_a_paper_without_an_abstract_uses_no_slot_and_shows_nothing(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    _jev(monkeypatch, choose="s1")

    result = await graph_module.write_node(_papers_state(5, with_abstract={0, 2, 3, 4}))

    shown = _snippets_by_url(result)
    assert _url(1) not in shown
    assert set(shown) == {_url(n) for n in (0, 2, 3, 4)}, shown


@pytest.mark.asyncio
async def test_the_sentence_sits_on_the_papers_abstract_citation(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    _jev(monkeypatch, choose="s1")

    result = await graph_module.write_node(_papers_state(2))

    carriers = [c for c in _citations(result) if c.get("snippet")]
    assert carriers
    for citation in carriers:
        assert citation["field"] == "abstract", citation


@pytest.mark.asyncio
async def test_a_sentence_not_word_for_word_in_the_abstract_is_never_shown(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    _jev(monkeypatch, choose="s1")
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
    _jev(monkeypatch, choose="s1", delay_s=5.0)
    monkeypatch.setattr(graph_module, "_LATE_DECISION_GRACE_S", 0.2)

    started = time.monotonic()
    result = await graph_module.write_node(_papers_state(3))

    assert _snippets_by_url(result) == {}
    assert time.monotonic() - started < 3.0
    assert any(e.type == "done" for e in result["events"])


@pytest.mark.asyncio
async def test_when_jev_fails_the_guard_tier_decides_each_paper(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    _jev(monkeypatch, error="http_error")
    _models(monkeypatch, guard_pick="s2")

    result = await graph_module.write_node(_papers_state(2))

    shown = _snippets_by_url(result)
    assert shown[_url(0)] == (
        "The authors of study 0 conclude that moderate doses are effective for athletes."
    )


@pytest.mark.asyncio
async def test_when_neither_model_makes_a_pick_nothing_is_shown(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    _jev(monkeypatch, error="timeout")

    result = await graph_module.write_node(_papers_state(2))

    assert _snippets_by_url(result) == {}
    assert any(e.type == "done" for e in result["events"])


@pytest.mark.asyncio
async def test_none_from_the_classifier_shows_nothing_and_the_field_stays_empty(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    _jev(monkeypatch, choose="none")

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
    asked = _jev(monkeypatch, choose="s1")

    result = await graph_module.write_node(_papers_state(2))

    assert asked == []
    assert _snippets_by_url(result) == {}


@pytest.mark.asyncio
async def test_a_listing_citation_already_sent_is_sent_again_with_the_sentence(
    monkeypatch: pytest.MonkeyPatch, jev_on: None, placement_contract: None
) -> None:
    _jev(monkeypatch, choose="s1")
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


def _offered(asked: list[dict[str, object]]) -> list[str]:
    """Every sentence any decision was offered, as the model read it."""
    return [
        sentence
        for call in asked
        for option, sentence in dict(call["criteria"]).items()  # type: ignore[call-overload]
        if option != "none"
    ]


@pytest.mark.asyncio
async def test_a_paper_pubmed_marks_retracted_is_never_asked_about_and_shows_nothing(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    asked = _jev(monkeypatch, choose="s1")

    result = await graph_module.write_node(_papers_state(5, retracted={1, 3}))

    shown = _snippets_by_url(result)
    assert set(shown) == {_url(0), _url(2), _url(4)}, shown
    assert len(asked) == 3, "the retracted papers are not asked about"
    rows = _papers_state(5, retracted={1, 3})["findings"][0].structured_fields["rows"]  # type: ignore[index]
    assert all("retracted" not in row["fields"] for row in rows), "the flag is not a citable fact"
    offered = " ".join(_offered(asked))
    assert "study 1" not in offered and "study 3" not in offered


@pytest.mark.asyncio
async def test_an_abstract_carrying_a_retraction_notice_is_treated_as_retracted(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    asked = _jev(monkeypatch, choose="s1")
    notice = (
        _abstract(1)
        + " This article has been retracted: please see the publisher's policy on article withdrawal."
    )

    result = await graph_module.write_node(_papers_state(3, abstracts={1: notice}))

    shown = _snippets_by_url(result)
    assert set(shown) == {_url(0), _url(2)}, shown
    assert len(asked) == 2


def _long_abstract(n: int, *, total: int) -> str:
    filler = " ".join(
        f"Filler sentence {i} of study {n} reports an unrelated measurement in the cohort."
        for i in range(200)
    )
    text = (
        f"Caffeine intake of three milligrams per kilogram improved performance in study {n}. "
        + filler
    )
    return text[:total]


@pytest.mark.asyncio
async def test_a_sentence_cut_short_by_the_trim_is_never_offered_or_shown(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    # 5,000 characters: cut at 4,000 by the fetch ("[truncated]") and at 2,000
    # by the findings trim ("..."). The classifier takes the last option offered.
    asked = _jev(monkeypatch, choose="last")
    abstract = _long_abstract(0, total=5000)

    result = await graph_module.write_node(_papers_state(1, abstracts={0: abstract}))

    offered = _offered(asked)
    assert offered, "the complete sentences are still offered"
    for sentence in offered:
        assert not sentence.endswith(("\u2026", "[truncated]")), sentence
        assert sentence.endswith("."), sentence
        assert sentence in abstract[:4000]
    shown = _snippets_by_url(result)
    assert shown[_url(0)] in offered


@pytest.mark.asyncio
async def test_the_shown_sentence_is_checked_against_the_untrimmed_abstract(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    # The only complete sentence the paper states sits past character 2,000, where
    # the findings trim has cut the copy the writer reads.
    asked = _jev(monkeypatch, choose="last")
    lead = " ".join(f"Background sentence {i} describes the trial setting in considerable detail for readers." for i in range(30))
    closing = "Caffeine improved time trial performance in trained cyclists by four percent."
    abstract = lead + " " + closing
    assert 2000 < len(abstract) < 4000

    result = await graph_module.write_node(_papers_state(1, abstracts={0: abstract}))

    assert _snippets_by_url(result) == {_url(0): closing}
    assert closing in _offered(asked)


@pytest.mark.asyncio
async def test_a_citation_with_no_sentence_has_no_snippet_key(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    _jev(monkeypatch, choose="none")

    result = await graph_module.write_node(_papers_state(2))

    payloads = [e.payload for e in result["events"] if e.type == "citation"]
    assert payloads
    for payload in payloads:
        assert "snippet" not in payload, payload


class _PickProbe:
    """A stand-in for `pick_snippets` that never finishes by itself. It also
    keeps the task `_start_snippet_pick` makes for it, so a test can tell
    whether that task was cancelled, even one cancelled before it first ran."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.tasks: list[asyncio.Task[dict[str, str]]] = []
        monkeypatch.setattr(graph_module, "pick_snippets", self._never_finishes)
        real_start = graph_module._start_snippet_pick

        def _spy(harness: object, *args: object, **kwargs: object) -> None:
            real_start(harness, *args, **kwargs)  # type: ignore[arg-type]
            task = graph_module._run_decisions(harness).snippet_task
            if task is not None:
                self.tasks.append(task)

        monkeypatch.setattr(graph_module, "_start_snippet_pick", _spy)

    async def _never_finishes(self, *_args: object, **_kwargs: object) -> dict[str, str]:
        await asyncio.sleep(30)
        return {}

    async def settle(self) -> None:
        for _ in range(3):
            await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_the_pick_is_cancelled_when_the_answer_ends_without_reading_it(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    probe = _PickProbe(monkeypatch)
    # An answer that fails after the pick started: the writer prompt cannot be built.
    monkeypatch.setattr(
        graph_module, "build_synth_messages", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    state = _papers_state(2)

    try:
        await graph_module.write_node(state)
    except RuntimeError:
        pass
    await probe.settle()

    assert len(probe.tasks) == 1, "the pick had started beside the writer"
    assert probe.tasks[0].cancelled(), "the pick is cancelled on a failed answer too"
    assert graph_module._run_decisions(state["harness"]).snippet_task is None


@pytest.mark.asyncio
async def test_a_pick_still_running_when_the_answer_ends_is_cancelled(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    probe = _PickProbe(monkeypatch)
    monkeypatch.setattr(graph_module, "_LATE_DECISION_GRACE_S", 0.2)
    state = _papers_state(2)

    result = await graph_module.write_node(state)
    await probe.settle()

    assert any(e.type == "done" for e in result["events"])
    assert len(probe.tasks) == 1
    assert probe.tasks[0].cancelled()
    assert graph_module._run_decisions(state["harness"]).snippet_task is None


@pytest.mark.asyncio
async def test_the_grace_never_waits_past_the_write_budget(
    monkeypatch: pytest.MonkeyPatch, jev_on: None
) -> None:
    probe = _PickProbe(monkeypatch)
    harness = harness_module.Harness(trace_id="trace-grace")
    citations = [_cite(0)]
    findings = [_abstract_finding(0)]
    assert graph_module._LATE_DECISION_GRACE_S >= 1.0

    graph_module._start_snippet_pick(harness, "trace-grace", _QUESTION, citations, findings)
    await asyncio.sleep(0)
    started = time.monotonic()
    # The write budget ran out 5 s ago: no grace at all.
    attached = await graph_module._attach_snippets(harness, citations, started - 5.0)
    spent = time.monotonic() - started

    assert spent < 0.3, f"waited {spent:.2f}s past a spent budget"
    assert attached == citations
    await probe.settle()
    assert probe.tasks[0].cancelled()

    # And with 0.3 s of budget left, the wait is that, not the full grace.
    graph_module._start_snippet_pick(harness, "trace-grace", _QUESTION, citations, findings)
    await asyncio.sleep(0)
    started = time.monotonic()
    await graph_module._attach_snippets(harness, citations, started + 0.3)
    spent = time.monotonic() - started
    assert 0.2 < spent < 0.7, f"waited {spent:.2f}s with 0.3 s of budget left"
