"""Build phase 8.7, T-8.7-02, option H's Act half: the name lookups run in Act.

Plan: `testing/Developer/reports/2026-09-26_answer_speed/report.md`, option H.
The disease and MeSH name lookups the Write step makes before its model call
run at the end of Act instead, beside the reader pass, so their time hides
behind it. Write then finds every name in the lookup cache and makes no
lookup of its own.

Where they run, and why only there:

- Never beside Act's searches: there they would compete for the question's
  20 Layer 2 and 3 calls and could turn a finished search into a failed one.
- Only when a reader pass runs, since without one there is nothing in Act
  to hide the lookup behind.
- Only when every id fits one lookup, so the question makes exactly the NCBI
  calls it made before.

The resolvers are the real ones; only the two NCBI calls below them
(`ncbi_eutils_actions.search` and `summary`) are faked, so the cache and the
call count are real.

Mutation: remove the Act-time lookup and the "during Act" arms go red (no
lookup inside act_node, and Write makes two calls of its own). Remove the
one-lookup guard and the "more names than one lookup holds" arm goes red.

Build phase 8.7, step 8 (card 50, option K, the owner's yes of 2026-10-05):
the reader pass came off the answer path, so on every question there is now
no reader pass in Act. By the rule above, the lookups stay in Write. The
first two arms and the variant arm now hold that: Act makes no lookup and
no reader call on a paper question, and Write makes the same lookups, with
the same answer, it makes on every other question. The comparison arms
still hold as they are: the same NCBI calls and the same answer whichever
step looks the names up.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.contracts.events import ToolCall
from system_03_search_agent.contracts.query import Query
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness.coordinator_worker import _READER_SYSTEM_PROMPT
from system_03_search_agent.synthesis import disease_names, mesh_terms
from system_03_search_agent.synthesis.findings import SYNTH_SYSTEM_INSTRUCTION
from system_03_search_agent.tools import ncbi_eutils_actions
from system_03_search_agent.tools.cypher_schemas import (
    CypherQueryInput,
    CypherQueryOutput,
    CypherQueryRow,
)
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput, NcbiEfetchRecord
from tests.system_03_search_agent.model_stub import compliant_synth_narrative, fake_response

_QUESTION = "Which diseases are associated with BRCA1?"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.delenv("CLASSIFIER_PROVIDER", raising=False)
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )
    disease_names.reset_cache_for_tests()
    mesh_terms.reset_cache_for_tests()


def _query() -> Query:
    return Query(
        text=_QUESTION,
        session_id="s-act",
        trace_id="trace-act-speed",
        user_id=None,
        audience_depth="researcher",
    )


# ---------------------------------------------------------------------------
# Option H, Act's half: the name lookups.
# ---------------------------------------------------------------------------

#: MedGen titles the fake ESummary returns, keyed by concept id.
_MEDGEN_TITLES = {
    "C0346153": "Familial cancer of breast",
    "C2676676": "Breast-ovarian cancer, familial, susceptibility to, 1",
}


class _NcbiLog:
    """The two NCBI calls under the real resolvers, faked and timed."""

    def __init__(self, delay_s: float) -> None:
        self.delay_s = delay_s
        self.calls: list[tuple[str, float, float]] = []

    async def search(self, params: Any) -> NcbiEfetchOutput:
        started = time.monotonic()
        await asyncio.sleep(self.delay_s)
        self.calls.append(("search", started, time.monotonic()))
        ids = re.findall(r"(C\d+)\[ConceptId\]", params.term)
        uids = [str(1000 + list(_MEDGEN_TITLES).index(i)) for i in ids if i in _MEDGEN_TITLES]
        return NcbiEfetchOutput(
            status="ok",
            action="search",
            records=[NcbiEfetchRecord(fields={"idlist": uids})],
            record_count=1,
            truncated=False,
        )

    async def summary(self, params: Any) -> NcbiEfetchOutput:
        started = time.monotonic()
        await asyncio.sleep(self.delay_s)
        self.calls.append(("summary", started, time.monotonic()))
        by_uid = {str(1000 + n): cid for n, cid in enumerate(_MEDGEN_TITLES)}
        records = [
            NcbiEfetchRecord(
                id=uid,
                db="medgen",
                fields={"conceptid": by_uid[uid], "title": _MEDGEN_TITLES[by_uid[uid]]},
            )
            for uid in params.ids
            if uid in by_uid
        ]
        return NcbiEfetchOutput(
            status="ok",
            action="summary",
            records=records,
            record_count=len(records),
            truncated=False,
        )


def _install_ncbi(monkeypatch: pytest.MonkeyPatch, delay_s: float) -> _NcbiLog:
    log = _NcbiLog(delay_s)
    monkeypatch.setattr(ncbi_eutils_actions, "search", log.search)
    monkeypatch.setattr(ncbi_eutils_actions, "summary", log.summary)
    return log


class _Models:
    """The model stand-in: the reader, the writer and anything else."""

    def __init__(self) -> None:
        self.reader_calls: list[tuple[float, float]] = []


def _install_models(monkeypatch: pytest.MonkeyPatch, *, reader_delay_s: float) -> _Models:
    models = _Models()

    async def _dispatch(*args: Any, **kwargs: Any) -> Any:
        messages = kwargs.get("messages") or []
        joined = "\n".join(m.get("content") or "" for m in messages)
        if _READER_SYSTEM_PROMPT in joined:
            started = time.monotonic()
            await asyncio.sleep(reader_delay_s)
            models.reader_calls.append((started, time.monotonic()))
            return fake_response(
                json.dumps({"entities": [], "normalized_ids": [], "evidence_summary": "none"})
            )
        if SYNTH_SYSTEM_INSTRUCTION in joined:
            return fake_response(compliant_synth_narrative(messages))
        return fake_response("ok")

    monkeypatch.setattr(harness_module.litellm, "acompletion", AsyncMock(side_effect=_dispatch))
    return models


def _disease_row(concept_id: str, name: str) -> CypherQueryRow:
    return CypherQueryRow(
        node_or_edge_type="Disease",
        curie=f"MedGen:{concept_id}",
        # The graph's vocabulary token in place of a name, the defect the
        # name lookup exists for (`synthesis/disease_names.py`).
        fields={"name": name},
        source_url=f"https://www.ncbi.nlm.nih.gov/medgen/{concept_id}",
        graph_snapshot_version="v1",
    )


_ARTICLE_ROW = CypherQueryRow(
    node_or_edge_type="Article",
    curie="PMID:1",
    fields={"name": "An article title the reader pass reads"},
    source_url="https://www.ncbi.nlm.nih.gov/pubmed/1",
    graph_snapshot_version="v1",
)


def _graph_call(monkeypatch: pytest.MonkeyPatch, rows: list[CypherQueryRow]) -> list[Any]:
    output = CypherQueryOutput(
        status="ok",
        row_count=len(rows),
        total_available=len(rows),
        truncated=False,
        rows=rows,
        error=None,
    )

    async def _cypher(harness: Any, cypher_input: Any, **kwargs: Any) -> CypherQueryOutput:
        return output

    monkeypatch.setattr(graph_module, "cypher_query", _cypher)
    return [
        graph_module._PlannedToolCall(
            tool_call=ToolCall(tool="cypher_query", call_id="cq-act-speed", layer="layer_1_graph"),
            cypher_input=CypherQueryInput(
                query_intent=_QUESTION,
                query_class="lookup",
                target_entities=["NCBIGene:672"],
                row_limit=100,
            ),
        )
    ]


def _write_state(act_state: dict[str, Any], act_result: dict[str, Any]) -> dict[str, Any]:
    state = dict(act_state)
    state.update({k: v for k, v in act_result.items() if k != "events"})
    state.setdefault("start_monotonic", time.monotonic())
    return state


async def _act_then_write(
    planned: list[Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    harness = harness_module.Harness(trace_id="trace-act-speed")
    act_state = {
        "harness": harness,
        "query": _query(),
        "query_class": "lookup",
        "tool_calls": planned,
        "seq": 0,
        "start_monotonic": time.monotonic(),
    }
    act_result = await graph_module.act_node(act_state)
    return act_state, act_result, _write_state(act_state, act_result)


_DISEASE_ROWS = [_disease_row("C0346153", "MedGen"), _disease_row("C2676676", "OMIM included")]


@pytest.mark.asyncio
async def test_on_a_paper_question_act_runs_no_reader_and_no_name_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Step 8: a question with an Article row no longer runs the reader pass
    in Act, so there is nothing to hide a lookup behind and Act makes none."""
    ncbi = _install_ncbi(monkeypatch, delay_s=0.15)
    models = _install_models(monkeypatch, reader_delay_s=0.4)
    planned = _graph_call(monkeypatch, [*_DISEASE_ROWS, _ARTICLE_ROW])

    _, act_result, write_state = await _act_then_write(planned)
    # Only Act has run at this point, so everything below was inside act_node.

    assert act_result["findings_count"] == 2, "populate-check: the Article pair was assembled"
    assert models.reader_calls == [], "the reader pass ran on the answer path"
    assert ncbi.calls == [], "Act made a name lookup with no reader pass to hide it behind"

    await graph_module.write_node(write_state)
    assert [name for name, _, _ in ncbi.calls] == ["search", "summary"], (
        "Write made the one MedGen lookup itself"
    )


@pytest.mark.asyncio
async def test_write_makes_the_name_lookup_and_names_the_diseases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ncbi = _install_ncbi(monkeypatch, delay_s=0.0)
    _install_models(monkeypatch, reader_delay_s=0.0)
    planned = _graph_call(monkeypatch, [*_DISEASE_ROWS, _ARTICLE_ROW])

    _, _, write_state = await _act_then_write(planned)
    made_in_act = len(ncbi.calls)
    write_result = await graph_module.write_node(write_state)

    assert made_in_act == 0, "Act made a name lookup"
    assert len(ncbi.calls) == 2, "Write made the one MedGen lookup"
    text = " ".join(e.payload["text"] for e in write_result["events"] if e.type == "token")
    assert "Familial cancer of breast" in text, "the answer names the disease in words"


@pytest.mark.asyncio
async def test_a_question_makes_the_same_ncbi_calls_as_before(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lookups move; they are not added. One lookup, two calls, whether
    it runs in Act or in Write, and the same answer either way."""
    answers: list[str] = []
    counts: list[int] = []
    for prefetch in (True, False):
        disease_names.reset_cache_for_tests()
        ncbi = _install_ncbi(monkeypatch, delay_s=0.0)
        _install_models(monkeypatch, reader_delay_s=0.0)
        planned = _graph_call(monkeypatch, [*_DISEASE_ROWS, _ARTICLE_ROW])
        if not prefetch:
            monkeypatch.setattr(
                graph_module, "_prefetch_answer_names", _no_prefetch, raising=False
            )
        _, _, write_state = await _act_then_write(planned)
        write_result = await graph_module.write_node(write_state)
        answers.append(
            " ".join(e.payload["text"] for e in write_result["events"] if e.type == "token")
        )
        counts.append(len(ncbi.calls))

    assert counts == [2, 2]
    assert answers[0] == answers[1]


async def _no_prefetch(*args: Any, **kwargs: Any) -> None:
    return None


#: A variant row that names its linked conditions (the fold), beside the
#: Disease records themselves, as `cypher_query` returns them for one gene.
_FOLD_ROWS = [
    CypherQueryRow(
        node_or_edge_type="SequenceVariant",
        curie="ClinVar:1",
        fields={
            "name": "variant number 1",
            "clinvar_condition_ids": ["MedGen:C0346153", "MedGen:C2676676"],
        },
        source_url="https://www.ncbi.nlm.nih.gov/clinvar/variation/1",
        graph_snapshot_version="v1",
    ),
    _disease_row("C0346153", "OMIM included"),
]


@pytest.mark.asyncio
async def test_a_variant_question_makes_the_same_calls_and_write_looks_up_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second of Write's two MedGen lookups, the linked conditions of a
    variant row, stays in Write with the first (step 8), with the same calls
    and the same answer."""
    counts: list[int] = []
    answers: list[str] = []
    in_act: list[int] = []
    for prefetch in (True, False):
        disease_names.reset_cache_for_tests()
        ncbi = _install_ncbi(monkeypatch, delay_s=0.0)
        _install_models(monkeypatch, reader_delay_s=0.0)
        planned = _graph_call(monkeypatch, [*_FOLD_ROWS, _ARTICLE_ROW])
        if not prefetch:
            monkeypatch.setattr(
                graph_module, "_prefetch_answer_names", _no_prefetch, raising=False
            )
        _, _, write_state = await _act_then_write(planned)
        in_act.append(len(ncbi.calls))
        write_result = await graph_module.write_node(write_state)
        counts.append(len(ncbi.calls))
        answers.append(
            " ".join(e.payload["text"] for e in write_result["events"] if e.type == "token")
        )

    assert counts[1] >= 2, "populate-check: the variant question makes name lookups"
    assert counts[0] == counts[1], f"NCBI calls with and without the Act lookup: {counts}"
    assert in_act == [0, 0], "Act made a name lookup with no reader pass to hide it behind"
    assert answers[0] == answers[1]
    assert "Familial cancer of breast" in answers[0]


@pytest.mark.asyncio
async def test_with_no_reader_pass_the_lookups_stay_in_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a reader pass there is nothing in Act to hide a lookup behind,
    so Act makes none and Write's own lookup is exactly as before."""
    ncbi = _install_ncbi(monkeypatch, delay_s=0.0)
    _install_models(monkeypatch, reader_delay_s=0.0)
    planned = _graph_call(monkeypatch, list(_DISEASE_ROWS))

    _, _, write_state = await _act_then_write(planned)
    assert ncbi.calls == [], "Act made a lookup with no reader pass to overlap"
    await graph_module.write_node(write_state)
    assert [name for name, _, _ in ncbi.calls] == ["search", "summary"]


@pytest.mark.asyncio
async def test_more_names_than_one_lookup_holds_are_left_to_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MedGen resolves at most 25 ids in one lookup and does not remember the
    rest, so a larger set looked up in Act would make Write look up the
    remainder: NCBI calls the question never made before. Act skips it, and
    the question makes the same calls, with the same answer, as without the
    Act-time lookup.

    Found while writing this arm, and not this ticket's: 25 MedGen ids of
    eight characters build an ESearch term over the 500-character schema
    limit, so today that one lookup fails validation and resolves nothing.
    The comparison below holds whatever the resolver does."""
    asked_in_act: list[list[str]] = []
    real_resolve = graph_module.resolve_concept_ids

    async def _spy(concept_ids: Any) -> Any:
        asked_in_act.append(list(concept_ids))
        return await real_resolve(concept_ids)

    many = [_disease_row(f"C{9000000 + n}", "MedGen") for n in range(30)]
    counts: list[int] = []
    answers: list[str] = []
    for prefetch in (True, False):
        disease_names.reset_cache_for_tests()
        ncbi = _install_ncbi(monkeypatch, delay_s=0.0)
        _install_models(monkeypatch, reader_delay_s=0.0)
        planned = _graph_call(monkeypatch, [*many, _ARTICLE_ROW])
        if not prefetch:
            monkeypatch.setattr(
                graph_module, "_prefetch_answer_names", _no_prefetch, raising=False
            )
        monkeypatch.setattr(graph_module, "resolve_concept_ids", _spy)
        asked_in_act.clear()
        _, _, write_state = await _act_then_write(planned)
        if prefetch:
            assert asked_in_act == [], "Act looked up more names than one lookup holds"
        write_result = await graph_module.write_node(write_state)
        assert asked_in_act, "populate-check: Write asked for the names"
        counts.append(len(ncbi.calls))
        answers.append(
            " ".join(e.payload["text"] for e in write_result["events"] if e.type == "token")
        )

    assert counts[0] == counts[1], f"NCBI calls with and without the Act lookup: {counts}"
    assert answers[0] == answers[1]
