"""Build phase 8.7, T-8.7-02, option C: no literature search holds an answer past 6 s.

The owner's words: "No answer waits more than 6 seconds on a literature
search, and when one is cut off, the answer says one of its searches did not
finish." Plan: `testing/Developer/reports/2026-09-26_answer_speed/report.md`,
option C.

Each PubTator call is cut at 6 seconds in Act, down from 20. A cut-off call
closes as an `error` result, lands in `failed_searches`, and the answer
carries the existing "One of the background searches did not finish" note
through the mechanism that already exists (`refuse.FAILED_SEARCH_NOTE`). The
note's text is not this ticket's.

Time is scaled, not waited: Act's `enforce_timeout` is wrapped so every Act
budget is divided by `_SCALE`, and the fake PubTator sleeps its simulated
seconds divided by the same figure. The cap the code declares is what is
measured; only the clock runs faster.

Mutation: `_LAYER_TOOL_ACT_TIMEOUT_SECONDS["pubtator_annotate"]` back to 20.0,
and the seven-second search finishes, so the cut-off arms go red.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.contracts.query import Query
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness.coordinator_worker import _READER_SYSTEM_PROMPT
from system_03_search_agent.synthesis import disease_names, mesh_terms
from system_03_search_agent.synthesis.findings import SYNTH_SYSTEM_INSTRUCTION
from system_03_search_agent.synthesis.refuse import FAILED_SEARCH_NOTE
from system_03_search_agent.tools.clinicaltrials_search_schemas import (
    ClinicalTrialsSearchOutput,
    ClinicalTrialsStudy,
)
from system_03_search_agent.tools.pubtator_annotate_schemas import (
    PubtatorAnnotateOutput,
    PubtatorEntity,
)
from tests.system_03_search_agent.model_stub import compliant_synth_narrative, fake_response

_SCALE = 100.0

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


def _scale_act_budgets(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Divide every Act budget by `_SCALE`; record each declared budget."""
    declared: list[float] = []
    real = harness_module.Harness.enforce_timeout

    async def _scaled(self: Any, step: str, coro: Any, budget_s: float) -> Any:
        if step == "act":
            declared.append(budget_s)
            return await real(self, step, coro, budget_s / _SCALE)
        return await real(self, step, coro, budget_s)

    monkeypatch.setattr(harness_module.Harness, "enforce_timeout", _scaled)
    return declared


def _pubtator_output() -> PubtatorAnnotateOutput:
    return PubtatorAnnotateOutput(
        status="ok",
        mode="entity_lookup",
        entities=[
            PubtatorEntity(
                pubtator_id="@GENE_BRCA1",
                biotype="gene",
                db="ncbi_gene",
                db_id="672",
                name="BRCA1",
                description="BRCA1 DNA repair associated",
                source_url="https://www.ncbi.nlm.nih.gov/gene/672",
            )
        ],
    )


def _pubtator_taking(monkeypatch: pytest.MonkeyPatch, simulated_s: float) -> list[dict[str, Any]]:
    """A PubTator call that takes `simulated_s`; returns its own timings."""
    runs: list[dict[str, Any]] = []

    async def _pubtator(tool_input: Any, **kwargs: Any) -> PubtatorAnnotateOutput:
        run: dict[str, Any] = {"started": time.monotonic(), "cancelled": False}
        runs.append(run)
        try:
            await asyncio.sleep(simulated_s / _SCALE)
        except asyncio.CancelledError:
            run["cancelled"] = True
            raise
        finally:
            run["ended"] = time.monotonic()
        return _pubtator_output()

    async def _trials(tool_input: Any, **kwargs: Any) -> ClinicalTrialsSearchOutput:
        return ClinicalTrialsSearchOutput(
            status="ok",
            studies=[
                ClinicalTrialsStudy(
                    nct_id="NCT00000001",
                    brief_title="Trial NCT00000001",
                    overall_status="RECRUITING",
                    conditions=["BRCA1 Mutation"],
                    source_url="https://clinicaltrials.gov/study/NCT00000001",
                )
            ],
            study_count=1,
            total_count=1,
        )

    monkeypatch.setattr(graph_module, "pubtator_annotate", _pubtator)
    monkeypatch.setattr(graph_module, "clinicaltrials_search", _trials)
    return runs


async def _act(planned: list[Any]) -> dict[str, Any]:
    harness = harness_module.Harness(trace_id="trace-act-speed")
    state = {
        "harness": harness,
        "query": _query(),
        "query_class": "lookup",
        "tool_calls": planned,
        "seq": 0,
    }
    return await graph_module.act_node(state)



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



def _write_state(act_state: dict[str, Any], act_result: dict[str, Any]) -> dict[str, Any]:
    state = dict(act_state)
    state.update({k: v for k, v in act_result.items() if k != "events"})
    state.setdefault("start_monotonic", time.monotonic())
    return state




# ---------------------------------------------------------------------------
# Option C: the PubTator cap.
# ---------------------------------------------------------------------------


def test_pubtator_is_capped_at_six_seconds_in_act() -> None:
    assert graph_module._LAYER_TOOL_ACT_TIMEOUT_SECONDS["pubtator_annotate"] == 6.0


def test_the_other_layer_tools_keep_their_act_timeouts() -> None:
    """Only PubTator moves; every other tool's Act timeout is as before."""
    caps = dict(graph_module._LAYER_TOOL_ACT_TIMEOUT_SECONDS)
    caps.pop("pubtator_annotate")
    assert caps == {
        "ncbi_dbsnp": 35.0,
        "litvar2_lookup": 20.0,
        "clinicaltrials_search": 20.0,
        "pathogen_detection": 150.0,
    }


@pytest.mark.asyncio
async def test_a_seven_second_literature_search_is_cut_off_at_six(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    declared = _scale_act_budgets(monkeypatch)
    runs = _pubtator_taking(monkeypatch, 7.0)
    planned = graph_module._build_layer_tool_calls(_QUESTION, "BRCA1", [])

    result = await _act(planned)

    by_tool = {f.tool: f for f in result["findings"]}
    assert by_tool["clinicaltrials_search"].structured_fields["status"] == "ok", (
        "populate-check: the sibling search ran"
    )
    cut = by_tool["pubtator_annotate"].structured_fields
    assert cut["status"] == "error"
    assert "did not complete within its 6s" in cut["error"]
    assert 6.0 in declared, "the 6 s cap is the budget Act declared for PubTator"
    assert len(runs) == 1 and runs[0]["cancelled"], "the search was cut, not finished"
    waited_s = (runs[0]["ended"] - runs[0]["started"]) * _SCALE
    assert waited_s < 7.0, f"the search ran {waited_s:.1f} simulated seconds, past the cap"
    failed = [s["tool"] for s in result["failed_searches"]]
    assert failed == ["pubtator_annotate"], "the cut-off search is recorded for the note"


@pytest.mark.asyncio
async def test_a_five_second_literature_search_still_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cap cuts slow searches only; a search inside it is untouched."""
    _scale_act_budgets(monkeypatch)
    _pubtator_taking(monkeypatch, 5.0)
    planned = graph_module._build_layer_tool_calls(_QUESTION, "BRCA1", [])

    result = await _act(planned)

    by_tool = {f.tool: f for f in result["findings"]}
    assert by_tool["pubtator_annotate"].structured_fields["status"] == "ok"
    assert result["failed_searches"] == []


@pytest.mark.asyncio
async def test_an_answer_with_a_cut_off_search_says_one_did_not_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End to end from Act into Write: the cut-off search reaches the reader
    as the existing note, and the answer is marked not yet confirmed."""
    _scale_act_budgets(monkeypatch)
    _pubtator_taking(monkeypatch, 7.0)
    _install_models(monkeypatch, reader_delay_s=0.0)
    planned = graph_module._build_layer_tool_calls(_QUESTION, "BRCA1", [])
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

    write_result = await graph_module.write_node(_write_state(act_state, act_result))

    text = " ".join(
        e.payload["text"] for e in write_result["events"] if e.type == "token"
    )
    assert "Trial NCT00000001" in text or "NCT00000001" in text, (
        "populate-check: the answer carries the search that did finish"
    )
    assert FAILED_SEARCH_NOTE in text
    done = next(e for e in write_result["events"] if e.type == "done")
    assert done.payload["trust_outcome"] == "ask"


