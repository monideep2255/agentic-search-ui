"""Build phase 8.7, T-8.7-02, option K's first step: does the reader's output
reach any answer?

The question, from `testing/Developer/reports/2026-09-26_answer_speed/report.md`
option K: the reader pass (`harness/coordinator_worker.py`, `_reader_pass`)
reads the free text of an article row with a guard-tier model call, up to 10
seconds after the last search, before Write can start. Skipping it, or
starting it per result, is only safe if nothing it returns reaches an answer.
This probe answers that, and changes nothing: the skip itself is a later
phase's, after the judge and the adversary.

THE RESULT, as of this commit: the reader's output reaches no answer.

- Dynamic half: one question with an article row, run twice through the real
  `act_node` and `write_node`, with the reader returning two different sets
  of canary strings. Both canaries reach the reader's `Finding` (the
  populate-check), and neither appears in any model prompt after the
  reader's own, nor in any event Act or Write emits. The two answers are
  identical, token for token, citation for citation, down to the trust
  verdict and `done`, apart from its cost and elapsed time.
- Static half: no module under `src/` other than `coordinator_worker.py`
  reads `extracted_entities`, `normalized_ids` or `evidence_summary`.
  `synthesis/findings.py` `build_synth_findings` skips any finding without
  `structured_fields`, which every reader finding is.
- What does reach the wire: the reader's `Finding` is counted in
  `done.total_tool_calls` (one per reader pass, whatever it read), and its
  model call is in `done.total_cost_usd`.

THE PROBE CAN FAIL. `test_the_probe_sees_a_canary_that_does_reach_the_answer`
puts a canary in a structured row instead and finds it in the answer, so an
empty result above is the reader's output being absent, not the detector
being blind. And the static scan goes red the day any module starts reading
one of the three fields.

Build phase 8.7, step 8 (card 50, option K, the owner's yes of 2026-10-05):
on this probe's result the reader pass came off the answer path. `act_node`
no longer hands the quarantine pair to `coordinator_worker_execute`, so a
paper question no longer waits on a guard-model read. The arms now say so:

- `test_the_answer_does_not_wait_on_the_reader_pass`: a reader that would
  take 9 simulated seconds is never called, and Act returns well inside that.
  Red on the code before step 8, which waited for it.
- The dynamic arm above still runs two different reader replies and finds
  the same answer with no canary anywhere, now because the reader is never
  asked, which the arm checks first.
- The static scan is unchanged. It is what keeps the skip safe: the day a
  module reads one of the reader's fields, the skip has to be revisited.
"""

from __future__ import annotations

import ast
import asyncio
import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.contracts.events import ToolCall
from system_03_search_agent.contracts.query import Query
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness.coordinator_worker import _READER_SYSTEM_PROMPT
from system_03_search_agent.synthesis.findings import SYNTH_SYSTEM_INSTRUCTION
from system_03_search_agent.tools.cypher_schemas import (
    CypherQueryInput,
    CypherQueryOutput,
    CypherQueryRow,
)
from tests.system_03_search_agent.model_stub import compliant_synth_narrative, fake_response

_QUESTION = "What gene is associated with BRCA1?"

#: Real seconds are simulated seconds divided by this, the pattern
#: `test_pubtator_act_cap.py` uses. A reader that takes 9 simulated seconds,
#: just inside its 10 s budget, takes 0.9 real seconds here.
_SCALE = 10.0
_READER_SIMULATED_S = 9.0
_READER_FIELDS = ("extracted_entities", "normalized_ids", "evidence_summary")
_SRC = Path(__file__).resolve().parents[3] / "src" / "system_03_search_agent"


def _canaries(tag: str) -> dict[str, Any]:
    return {
        "entities": [f"CANARYENTITY{tag}"],
        "normalized_ids": [f"CANARY:ID{tag}"],
        "evidence_summary": f"CANARYSUMMARY{tag} the article says something",
    }


def _canary_words(tag: str) -> list[str]:
    return [f"CANARYENTITY{tag}", f"CANARY:ID{tag}", f"CANARYSUMMARY{tag}"]


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


class _Run:
    """One question, act then write, with every prompt and event kept."""

    def __init__(self) -> None:
        self.reader_calls = 0
        self.prompts: list[str] = []
        self.events: list[Any] = []
        self.reader_finding: Any = None
        self.act_result: dict[str, Any] = {}
        self.act_elapsed_s = 0.0


async def _run_once(
    monkeypatch: pytest.MonkeyPatch,
    reader_reply: dict[str, Any],
    gene_name: str,
    *,
    reader_delay_s: float = 0.0,
) -> _Run:
    run = _Run()

    async def _dispatch(*args: Any, **kwargs: Any) -> Any:
        messages = kwargs.get("messages") or []
        joined = "\n".join(m.get("content") or "" for m in messages)
        if _READER_SYSTEM_PROMPT in joined:
            run.reader_calls += 1
            await asyncio.sleep(reader_delay_s)
            return fake_response(json.dumps(reader_reply))
        run.prompts.append(joined)
        if SYNTH_SYSTEM_INSTRUCTION in joined:
            return fake_response(compliant_synth_narrative(messages))
        return fake_response("ok")

    monkeypatch.setattr(harness_module.litellm, "acompletion", AsyncMock(side_effect=_dispatch))

    output = CypherQueryOutput(
        status="ok",
        row_count=2,
        total_available=2,
        truncated=False,
        rows=[
            CypherQueryRow(
                node_or_edge_type="Gene",
                curie="NCBIGene:672",
                fields={"name": gene_name},
                source_url="https://www.ncbi.nlm.nih.gov/gene/672",
                graph_snapshot_version="v1",
            ),
            CypherQueryRow(
                node_or_edge_type="Article",
                curie="PMID:1",
                fields={"name": "An article about BRCA1 the reader pass reads"},
                source_url="https://www.ncbi.nlm.nih.gov/pubmed/1",
                graph_snapshot_version="v1",
            ),
        ],
        error=None,
    )

    async def _cypher(harness: Any, cypher_input: Any, **kwargs: Any) -> CypherQueryOutput:
        return output

    monkeypatch.setattr(graph_module, "cypher_query", _cypher)
    planned = [
        graph_module._PlannedToolCall(
            tool_call=ToolCall(tool="cypher_query", call_id="cq-probe", layer="layer_1_graph"),
            cypher_input=CypherQueryInput(
                query_intent=_QUESTION,
                query_class="lookup",
                target_entities=["NCBIGene:672"],
                row_limit=100,
            ),
        )
    ]
    query = Query(
        text=_QUESTION,
        session_id="s-probe",
        trace_id="trace-reader-probe",
        user_id=None,
        audience_depth="researcher",
    )
    state: dict[str, Any] = {
        "harness": harness_module.Harness(trace_id=query.trace_id),
        "query": query,
        "query_class": "lookup",
        "tool_calls": planned,
        "seq": 0,
        "start_monotonic": time.monotonic(),
    }
    act_started = time.monotonic()
    act_result = await graph_module.act_node(state)
    run.act_elapsed_s = time.monotonic() - act_started
    run.act_result = act_result
    run.events.extend(act_result["events"])
    run.reader_finding = next((f for f in act_result["findings"] if f.source == "reader"), None)
    state.update({k: v for k, v in act_result.items() if k != "events"})
    write_result = await graph_module.write_node(state)
    run.events.extend(write_result["events"])
    return run


def _wire(events: list[Any]) -> str:
    return json.dumps([{"type": e.type, "payload": e.payload} for e in events], default=str)


def _answer(events: list[Any]) -> list[dict[str, Any]]:
    """Every event a reader sees, with the done event's cost and time taken
    out, since a reader call's cost and duration are expected to differ."""
    shaped = []
    for event in events:
        payload = dict(event.payload)
        if event.type == "done":
            payload.pop("total_cost_usd", None)
            payload.pop("elapsed_ms", None)
        if event.type == "cost":
            continue
        shaped.append({"type": event.type, "payload": payload})
    return shaped


@pytest.mark.asyncio
async def test_the_readers_output_reaches_no_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    alpha = await _run_once(monkeypatch, _canaries("ALPHA"), "BRCA1 DNA repair associated")
    beta = await _run_once(monkeypatch, _canaries("BETA"), "BRCA1 DNA repair associated")

    # Step 8: the reader is not asked on the answer path at all, so its
    # output cannot reach an answer. Checked first, so the arms below are
    # read as what they now are.
    for run in (alpha, beta):
        assert run.reader_calls == 0, "the reader pass ran on the answer path"
        assert run.reader_finding is None, "a reader Finding reached Write"
    assert alpha.prompts, "populate-check: Write called a model"

    for run, tag in ((alpha, "ALPHA"), (beta, "BETA")):
        wire = _wire(run.events)
        prompts = "\n".join(run.prompts)
        for word in _canary_words(tag):
            assert word not in wire, f"{word} reached an emitted event"
            assert word not in prompts, f"{word} reached a model prompt"

    assert _answer(alpha.events) == _answer(beta.events), (
        "two different reader outputs produced two different answers"
    )


@pytest.mark.asyncio
async def test_the_answer_does_not_wait_on_the_reader_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Step 8's ticket, in the user's words: paper questions come up to 10
    seconds faster, with the same answer. A reader that would take 9
    simulated seconds is never called, Act returns in well under half of
    that, and the Article row's quarantine pair is still assembled and
    counted, so `done.total_tool_calls` reads as before."""
    reader_real_s = _READER_SIMULATED_S / _SCALE
    run = await _run_once(
        monkeypatch,
        _canaries("DELTA"),
        "BRCA1 DNA repair associated",
        reader_delay_s=reader_real_s,
    )

    assert run.reader_calls == 0, "the reader pass ran on the answer path"
    assert run.act_elapsed_s < reader_real_s / 2, (
        f"Act took {run.act_elapsed_s:.3f} s against a {reader_real_s:.1f} s reader: "
        "the answer waited on the reader pass"
    )
    assert [f.source for f in run.act_result["findings"]] == ["structured_pass_through"]
    assert run.act_result["findings_count"] == 2, (
        "the quarantine pair is still assembled and counted"
    )
    done = next(e for e in run.events if e.type == "done")
    assert done.payload["total_tool_calls"] == 2
    assert done.payload["trust_outcome"] == "answer"


@pytest.mark.asyncio
async def test_the_probe_sees_a_canary_that_does_reach_the_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The control: the same detector finds a canary placed where an answer
    does draw from, a structured row's field, so the empty result above is
    not a blind detector."""
    run = await _run_once(monkeypatch, _canaries("GAMMA"), "CANARYGENENAMEGAMMA")
    tokens = " ".join(e.payload.get("text", "") for e in run.events if e.type == "token")
    assert "CANARYGENENAMEGAMMA" in tokens
    assert "CANARYGENENAMEGAMMA" in _wire(run.events), "the detector the main arm uses sees it"


def test_no_module_outside_the_coordinator_reads_the_readers_fields() -> None:
    """The static half: no attribute read of `extracted_entities`,
    `normalized_ids` or `evidence_summary` anywhere under `src/` except the
    module that builds them."""
    readers: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
        if path.name == "coordinator_worker.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in _READER_FIELDS:
                readers.append(f"{path.relative_to(_SRC)}:{node.lineno}: .{node.attr}")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value in _READER_FIELDS
            ):
                readers.append(f"{path.relative_to(_SRC)}:{node.lineno}: getattr")
    assert readers == [], f"the reader's output is read here: {readers}"
