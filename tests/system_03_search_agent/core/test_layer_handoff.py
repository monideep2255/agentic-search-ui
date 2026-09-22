"""UI fix set 8 (R29, R30, R31, R43): every layer is searched, with the scientists.

What this file grades, offline, with the model and every tool replaced by
fakes whose bytes the test controls (the same discipline as
`test_cq_routing_mutation.py`: the loop's own nodes run their real bodies):

    PLAN SELECTION PER ENTITY KIND. A resolved gene plans Layer 1
    (cypher_query), Layer 2 (ncbi_efetch) and Layer 3 (pubtator_annotate,
    clinicaltrials_search); an rs id in the question adds ncbi_dbsnp and
    litvar2_lookup; a disease named only as a typed CURIE plans the graph
    call alone; every input is deterministic for a given question.

    CONCURRENCY. Two slow fakes finish in about one timeout, not two, and
    the arm is shown to FAIL when `_gather_planned_calls` is made
    sequential.

    GRACEFUL DEGRADATION. A layer that times out or raises lands as an
    `"error"` `tool_result` with a disclosure, its sibling's `"ok"` result
    stands, and the run still answers.

    THE HELPER DRAW. Three helpers, none the lead, varying between runs
    while the tool set is identical, present on the plan and tool frames,
    and never in a synthesis prompt. Shown to FAIL when the draw is made
    to include the lead.

    THE GCK FALLBACK. When the model extracts no gene span, a gene-shaped
    token that the live lookup confirms is resolved; when the model DID
    extract a span the fallback never consults the lookup; an unconfirmed
    token is dropped silently and never becomes a refusal. Shown to FAIL
    when the candidate extractor is emptied.

    THE CONTRACT. `ToolCall` and `ToolStartPayload` accept the persona
    fields and validate without them.

EVERY ARM CARRIES A POPULATE-CHECK: a negative or comparative assertion
first proves the thing it measures was there to be measured.

Not exercised here, stated so the gap is arguable: the live APIs' own
behaviour (whether PubTator3 and ClinicalTrials.gov return the same records
run to run), which the live-run table in the set 8 report measures, and the
rendering of the handoff on screen, which `RunProgress.handoff.test.tsx`
grades.
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from typing import Any

import pytest

from system_03_search_agent.contracts.events import ToolCall, ToolStartPayload
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.core import persona as persona_module
from system_03_search_agent.core.run import run_streaming
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.tools.clinicaltrials_search_schemas import (
    ClinicalTrialsSearchOutput,
    ClinicalTrialsStudy,
)
from system_03_search_agent.tools.cypher_schemas import (
    CypherQueryInput,
    CypherQueryOutput,
    CypherQueryRow,
)
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput
from system_03_search_agent.tools.pubtator_annotate_schemas import (
    PubtatorAnnotateOutput,
    PubtatorEntity,
)
from tests.system_03_search_agent.model_stub import (
    COMPLIANT_GUARD_CLASSIFICATION,
    compliant_synth_narrative,
    fake_response,
)

_GENE_QUESTION = "Which diseases are associated with BRCA1?"
_GCK_QUESTION = "Variants in GCK causing MODY"
_KNOWN = {"BRCA1": "NCBIGene:672", "TP53": "NCBIGene:7157", "GCK": "NCBIGene:2645"}


# ---------------------------------------------------------------------------
# Fixtures: environment, caps, model, tools.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGSMITH_API_KEY", "")


@pytest.fixture(autouse=True)
def _no_op_daily_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    def _user_check(session: Any, user_id: Any, **kwargs: Any) -> None:
        return None

    def _system_check(session: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(cost_control, "check_user_daily_query_cap", _user_check)
    monkeypatch.setattr(cost_control, "check_system_daily_cost_cap", _system_check)


class _ModelSpy:
    """Installs the per-tier model stand-in and records every synth prompt."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, think_entities: list[dict[str, str]]):
        from system_03_search_agent.core.graph import _THINK_SYSTEM_INSTRUCTION
        from system_03_search_agent.guardrail.classifier import GUARD_SYSTEM_INSTRUCTION
        from system_03_search_agent.synthesis.findings import SYNTH_SYSTEM_INSTRUCTION

        self.synth_prompts: list[str] = []

        async def _dispatch(*args: Any, **kwargs: Any) -> Any:
            messages = kwargs.get("messages") or []
            joined = "\n".join(m.get("content") or "" for m in messages)
            if GUARD_SYSTEM_INSTRUCTION in joined:
                return fake_response(COMPLIANT_GUARD_CLASSIFICATION)
            if _THINK_SYSTEM_INSTRUCTION in joined:
                return fake_response(
                    json.dumps(
                        {
                            "query_class": "single_hop",
                            "narrative": "stand-in classification",
                            "entities": think_entities,
                        }
                    )
                )
            if SYNTH_SYSTEM_INSTRUCTION in joined:
                self.synth_prompts.append(joined)
                return fake_response(compliant_synth_narrative(messages))
            return fake_response("ok")

        monkeypatch.setattr(harness_module.litellm, "acompletion", _dispatch)
        monkeypatch.setattr(
            harness_module.litellm,
            "get_model_info",
            lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
        )


def _install_lookup(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """A live-lookup stand-in over `_KNOWN`; returns the list of symbols asked."""
    asked: list[str] = []

    async def _resolve(symbol: str, **kwargs: Any) -> str | None:
        asked.append(symbol.strip().upper())
        return _KNOWN.get(symbol.strip().upper())

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _resolve)
    return asked


def _cypher_output() -> CypherQueryOutput:
    return CypherQueryOutput(
        status="ok",
        row_count=1,
        total_available=1,
        truncated=False,
        rows=[
            CypherQueryRow(
                node_or_edge_type="Disease",
                curie="MedGen:C0346153",
                fields={"name": "familial cancer of breast"},
                source_url="https://www.ncbi.nlm.nih.gov/medgen/C0346153",
                graph_snapshot_version="v1",
            )
        ],
        error=None,
    )


def _trials_output(*nct_ids: str) -> ClinicalTrialsSearchOutput:
    studies = [
        ClinicalTrialsStudy(
            nct_id=nct,
            brief_title=f"Trial {nct}",
            overall_status="RECRUITING",
            conditions=["BRCA1 Mutation"],
            source_url=f"https://clinicaltrials.gov/study/{nct}",
        )
        for nct in nct_ids
    ]
    return ClinicalTrialsSearchOutput(
        status="ok" if studies else "empty",
        studies=studies,
        study_count=len(studies),
        total_count=len(studies),
    )


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


def _install_tools(
    monkeypatch: pytest.MonkeyPatch,
    *,
    trials: ClinicalTrialsSearchOutput | None = None,
    pubtator: PubtatorAnnotateOutput | None = None,
) -> None:
    # Accepts the `template` keyword the real tool takes for a breadth
    # follow-up, like the sibling stubs below. Without it the follow-up
    # graph call raised inside the stub and closed as a disclosed error,
    # which was silent until 2026-09-22, when a failed search started to
    # downgrade the answer to "not yet confirmed" and the arm at the
    # bottom of this file, which expects "answer", went red in CI.
    async def _cypher(harness: Any, cypher_input: Any, **kwargs: Any) -> CypherQueryOutput:
        return _cypher_output()

    async def _efetch(tool_input: Any, **kwargs: Any) -> NcbiEfetchOutput:
        return NcbiEfetchOutput(
            status="empty", action="dataset_report", records=[], record_count=0,
            total_available=None, truncated=False, error=None,
        )

    async def _pubtator(tool_input: Any, **kwargs: Any) -> PubtatorAnnotateOutput:
        return pubtator or _pubtator_output()

    async def _trials_fn(tool_input: Any, **kwargs: Any) -> ClinicalTrialsSearchOutput:
        return trials or _trials_output("NCT00000002", "NCT00000001")

    monkeypatch.setattr(graph_module, "cypher_query", _cypher)
    monkeypatch.setattr(graph_module, "ncbi_efetch", _efetch)
    monkeypatch.setattr(graph_module, "pubtator_annotate", _pubtator)
    monkeypatch.setattr(graph_module, "clinicaltrials_search", _trials_fn)


def _query(text: str, session_id: str = "s-1") -> Query:
    return Query(
        text=text, session_id=session_id, trace_id=f"trace-{session_id}",
        user_id=None, audience_depth="researcher",
    )


async def _events(text: str, session_id: str = "s-1") -> list[Any]:
    context = RequestContext(surface="web_ui", session_memory=None, operator_mode=False)
    return [event async for event in run_streaming(_query(text, session_id), context)]


def _plan_tools(events: list[Any]) -> list[dict[str, Any]]:
    plan = next(e for e in events if e.type == "plan")
    return list(plan.payload["tool_calls"])


# ---------------------------------------------------------------------------
# Plan selection per entity kind.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_resolved_gene_plans_all_three_layers(monkeypatch: pytest.MonkeyPatch) -> None:
    _ModelSpy(monkeypatch, [{"text": "BRCA1", "entity_type": "gene"}])
    _install_lookup(monkeypatch)
    _install_tools(monkeypatch)

    tools = _plan_tools(await _events(_GENE_QUESTION))

    assert tools, "populate-check: nothing was planned"
    assert [t["tool"] for t in tools[:2]] == ["cypher_query", "ncbi_efetch"]
    assert {t["tool"] for t in tools} == {
        "cypher_query", "ncbi_efetch", "pubtator_annotate", "clinicaltrials_search"
    }
    assert {t["layer"] for t in tools} == {"layer_1_graph", "layer_2_api", "layer_3_enrichment"}
    plan = next(e for e in (await _events(_GENE_QUESTION)) if e.type == "plan")
    narrative = plan.payload["narrative"]
    for word in ("Layer 1", "Layer 2", "Layer 3", "cypher_query", "pubtator_annotate"):
        assert word in narrative, narrative


def test_an_rs_id_adds_dbsnp_and_litvar2_and_a_typed_disease_adds_nothing() -> None:
    with_rs = graph_module._build_layer_tool_calls(
        "Is rs334 in HBB pathogenic?", "HBB", graph_module._rsids_in_text("Is rs334 in HBB pathogenic?")
    )
    assert [c.tool_call.tool for c in with_rs] == [
        "pubtator_annotate", "clinicaltrials_search", "ncbi_dbsnp", "litvar2_lookup",
    ]
    assert with_rs[2].tool_input.query == "rs334"
    assert with_rs[3].tool_input.root.query == "rs334"

    # A disease named only as a typed CURIE: no symbol, no rs id, nothing.
    assert graph_module._build_layer_tool_calls("Tell me about MedGen:C0346153", None, []) == []


def test_layer_inputs_are_deterministic_for_one_question() -> None:
    first = graph_module._build_layer_tool_calls(_GENE_QUESTION, "BRCA1", [])
    second = graph_module._build_layer_tool_calls(_GENE_QUESTION, "BRCA1", [])
    assert first, "populate-check: nothing was planned"
    assert [c.tool_input.model_dump() for c in first] == [c.tool_input.model_dump() for c in second]

    recruiting = graph_module._build_layer_tool_calls(
        "What trials are recruiting for EGFR?", "EGFR", []
    )
    trials = next(c for c in recruiting if c.tool_call.tool == "clinicaltrials_search")
    assert trials.tool_input.overall_status == "RECRUITING"
    assert trials.tool_input.query_cond == "EGFR"
    plain = next(c for c in first if c.tool_call.tool == "clinicaltrials_search")
    assert plain.tool_input.overall_status is None


def test_shaping_sorts_by_a_stable_key_and_caps_and_drops_uncitable_rows() -> None:
    ids = ["NCT00000009", "NCT00000003", "NCT00000007", "NCT00000001", "NCT00000005", "NCT00000002"]
    output = _trials_output(*ids)
    output.studies.append(ClinicalTrialsStudy(nct_id="NCT00000000", brief_title="no url"))
    shaped = graph_module._layer_tool_output_to_structured_fields("clinicaltrials_search", output)

    assert shaped["status"] == "ok"
    assert [r["fields"]["nct_id"] for r in shaped["rows"]] == sorted(ids)[: graph_module._LAYER_TOOL_ROW_CAP]
    assert all(r["source_url"] for r in shaped["rows"])
    assert all(r["curie"] == "" for r in shaped["rows"]), "a Layer 3 row never fabricates a CURIE"

    # PubTator's entity index answers a symbol with every species' homonym;
    # when an entity's name IS the queried symbol, only those rows survive.
    from system_03_search_agent.tools.pubtator_annotate_schemas import PubtatorAnnotateInput

    frog = PubtatorEntity(
        pubtator_id="@GENE_brca1.L", biotype="gene", db="ncbi_gene", db_id="399391",
        name="brca1.L", source_url="https://www.ncbi.nlm.nih.gov/gene/399391",
    )
    mixed = PubtatorAnnotateOutput(
        status="ok", mode="entity_lookup", entities=[frog, *_pubtator_output().entities]
    )
    query_input = PubtatorAnnotateInput.model_validate(
        {"mode": "entity_lookup", "query": "BRCA1", "limit": 5}
    )
    shaped_pt = graph_module._layer_tool_output_to_structured_fields(
        "pubtator_annotate", mixed, query_input
    )
    assert [r["fields"]["name"] for r in shaped_pt["rows"]] == ["BRCA1"]
    other = PubtatorAnnotateInput.model_validate({"mode": "entity_lookup", "query": "XYZ", "limit": 5})
    assert len(graph_module._layer_tool_output_to_structured_fields(
        "pubtator_annotate", mixed, other
    )["rows"]) == 2, "with no exact-name match every citeable entity is kept"

    # An "ok" output with no citeable row is reported empty, not ok.
    none_citeable = ClinicalTrialsSearchOutput(
        status="ok", studies=[ClinicalTrialsStudy(nct_id="NCT1", brief_title="x")],
        study_count=1, total_count=1,
    )
    assert graph_module._layer_tool_output_to_structured_fields(
        "clinicaltrials_search", none_citeable
    )["status"] == "empty"


# ---------------------------------------------------------------------------
# Concurrency and graceful degradation, driven through act_node directly.
# ---------------------------------------------------------------------------


def _two_slow_layer_calls(monkeypatch: pytest.MonkeyPatch, delay_s: float) -> list[Any]:
    async def _slow_pubtator(tool_input: Any, **kwargs: Any) -> PubtatorAnnotateOutput:
        await asyncio.sleep(delay_s)
        return _pubtator_output()

    async def _slow_trials(tool_input: Any, **kwargs: Any) -> ClinicalTrialsSearchOutput:
        await asyncio.sleep(delay_s)
        return _trials_output("NCT00000001")

    monkeypatch.setattr(graph_module, "pubtator_annotate", _slow_pubtator)
    monkeypatch.setattr(graph_module, "clinicaltrials_search", _slow_trials)
    return graph_module._build_layer_tool_calls(_GENE_QUESTION, "BRCA1", [])


async def _act(planned: list[Any]) -> tuple[float, dict[str, Any]]:
    harness = harness_module.Harness(trace_id="trace-act")
    state = {
        "harness": harness, "query": _query("q"), "query_class": "lookup",
        "tool_calls": planned, "seq": 0,
    }
    started = time.monotonic()
    result = await graph_module.act_node(state)
    return time.monotonic() - started, result


async def _sequential(coroutines: list[Any]) -> None:
    for coroutine in coroutines:
        await coroutine


@pytest.mark.asyncio
async def test_two_slow_layer_calls_finish_in_about_one_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """Measured against a SEQUENTIAL baseline taken in the same process, not
    against a fixed number of seconds: a fixed 0.85s threshold went red
    under a loaded machine on 2026-09-14 (set 9's full-suite run) while the
    dispatch was concurrent. A ratio survives load, because the load slows
    both runs alike.
    """
    planned = _two_slow_layer_calls(monkeypatch, 0.4)
    assert len(planned) == 2, "populate-check: two calls must be planned"

    real_gather = graph_module._gather_planned_calls
    monkeypatch.setattr(graph_module, "_gather_planned_calls", _sequential)
    sequential_s, seq_result = await _act(planned)
    monkeypatch.setattr(graph_module, "_gather_planned_calls", real_gather)
    concurrent_s, result = await _act(planned)

    assert len(seq_result["findings"]) == 2 and len(result["findings"]) == 2, (
        "populate-check: both calls must have run in both modes"
    )
    assert sequential_s >= 0.8, f"populate-check: the sequential baseline took {sequential_s:.2f}s"
    assert concurrent_s < 0.75 * sequential_s, (
        f"concurrent {concurrent_s:.2f}s versus sequential {sequential_s:.2f}s; "
        "the two calls did not overlap"
    )


@pytest.mark.asyncio
async def test_the_concurrency_arm_goes_red_when_dispatch_is_made_sequential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation: under a sequential runner the concurrent measurement is no
    faster than the baseline, so the arm above's ratio assertion fails."""
    monkeypatch.setattr(graph_module, "_gather_planned_calls", _sequential)
    planned = _two_slow_layer_calls(monkeypatch, 0.4)
    baseline_s, _ = await _act(planned)
    mutated_s, result = await _act(planned)
    assert len(result["findings"]) == 2
    assert baseline_s >= 0.8
    assert not (mutated_s < 0.75 * baseline_s), (
        "the mutation did not remove the overlap; the arm could not have caught it"
    )


@pytest.mark.asyncio
async def test_a_layer_that_times_out_degrades_with_a_disclosure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(graph_module._LAYER_TOOL_ACT_TIMEOUT_SECONDS, "pubtator_annotate", 0.2)
    planned = _two_slow_layer_calls(monkeypatch, 0.0)

    async def _hangs(tool_input: Any, **kwargs: Any) -> PubtatorAnnotateOutput:
        await asyncio.sleep(2.0)
        return _pubtator_output()

    monkeypatch.setattr(graph_module, "pubtator_annotate", _hangs)
    _, result = await _act(planned)

    by_tool = {f.tool: f for f in result["findings"]}
    assert by_tool["clinicaltrials_search"].structured_fields["status"] == "ok"
    failed = by_tool["pubtator_annotate"].structured_fields
    assert failed["status"] == "error"
    assert "did not complete within its 0.2s" in failed["error"]
    assert "the other layers' results stand" in failed["error"]
    results = [e for e in result["events"] if e.type == "tool_result"]
    assert {r.payload["status"] for r in results} == {"ok", "error"}
    assert all(
        s.payload["call_id"] in {r.payload["call_id"] for r in results}
        for s in result["events"] if s.type == "tool_start"
    ), "every tool_start is closed by a tool_result"


@pytest.mark.asyncio
async def test_a_layer_that_raises_degrades_instead_of_failing_the_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    planned = _two_slow_layer_calls(monkeypatch, 0.0)

    async def _broken(tool_input: Any, **kwargs: Any) -> ClinicalTrialsSearchOutput:
        raise RuntimeError("simulated defect below the tool's own boundary")

    monkeypatch.setattr(graph_module, "clinicaltrials_search", _broken)
    _, result = await _act(planned)
    by_tool = {f.tool: f for f in result["findings"]}
    assert by_tool["pubtator_annotate"].structured_fields["status"] == "ok"
    assert by_tool["clinicaltrials_search"].structured_fields["status"] == "error"
    assert "failed unexpectedly" in by_tool["clinicaltrials_search"].structured_fields["error"]
    assert "simulated defect" not in json.dumps(
        [e.payload for e in result["events"]]
    ), "exception text never reaches the wire"


@pytest.mark.asyncio
async def test_a_full_run_with_layer_3_results_cites_them(monkeypatch: pytest.MonkeyPatch) -> None:
    _ModelSpy(monkeypatch, [{"text": "BRCA1", "entity_type": "gene"}])
    _install_lookup(monkeypatch)
    _install_tools(monkeypatch)

    events = await _events(_GENE_QUESTION)
    citations = [e.payload for e in events if e.type == "citation"]
    assert citations, "populate-check: the run cited nothing"
    layers = {c["layer"] for c in citations}
    assert "layer_3_enrichment" in layers, layers
    assert "layer_1_graph" in layers, layers
    trial = next(c for c in citations if c["source_url"].startswith("https://clinicaltrials.gov/study/"))
    assert trial["source"] == "clinicaltrials.gov"
    done = events[-1]
    assert done.type == "done" and done.payload["trust_outcome"] == "answer"


# ---------------------------------------------------------------------------
# The helper draw.
# ---------------------------------------------------------------------------


def test_draw_helpers_never_includes_the_lead_and_varies_between_draws() -> None:
    lead = persona_module.load_persona_list()[0].name
    draws = [persona_module.draw_helpers(lead_name=lead) for _ in range(25)]
    assert all(len(d) == 3 for d in draws)
    assert all(lead not in {p.name for p in d} for d in draws)
    assert all(len({p.name for p in d}) == 3 for d in draws), "helpers are distinct"
    assert len({tuple(p.name for p in d) for d in draws}) > 1, "25 draws never varied"
    seeded_a = persona_module.draw_helpers(lead_name=lead, rng=random.Random(7))
    seeded_b = persona_module.draw_helpers(lead_name=lead, rng=random.Random(7))
    assert seeded_a == seeded_b, "a seeded draw is reproducible for tests"


def test_assign_helpers_stamps_one_name_per_layer_and_leaves_inputs_alone() -> None:
    planned = [
        graph_module._PlannedToolCall(
            tool_call=ToolCall(tool="cypher_query", call_id="cq-1", layer="layer_1_graph"),
            cypher_input=CypherQueryInput(
                query_intent="q", query_class="lookup", target_entities=["NCBIGene:672"], row_limit=10,
            ),
        ),
        graph_module._build_planned_ncbi_efetch_call("NCBIGene:672"),
        *graph_module._build_layer_tool_calls(_GENE_QUESTION, "BRCA1", []),
    ]
    lead = persona_module.load_persona_list()[0].name
    stamped = graph_module._assign_helpers(planned, lead_name=lead, rng=random.Random(3))

    names_by_layer: dict[str, set[str]] = {}
    for call in stamped:
        names_by_layer.setdefault(call.tool_call.layer, set()).add(call.tool_call.persona)
    assert set(names_by_layer) == {"layer_1_graph", "layer_2_api", "layer_3_enrichment"}
    assert all(len(names) == 1 for names in names_by_layer.values()), names_by_layer
    assert len({next(iter(n)) for n in names_by_layer.values()}) == 3, "one helper per layer, distinct"
    assert all(call.tool_call.persona != lead for call in stamped)
    assert all(call.tool_call.persona_about and call.tool_call.persona_wikipedia for call in stamped)
    assert stamped[0].cypher_input == planned[0].cypher_input
    assert [c.tool_call.tool for c in stamped] == [c.tool_call.tool for c in planned]


def test_the_helper_arm_goes_red_when_the_draw_includes_the_lead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation: with the lead exclusion removed, the exclusion assertion fails."""
    lead = persona_module.load_persona_list()[0].name

    def _draw_with_lead(*, lead_name: str, count: int = 3, rng: Any = None) -> tuple[Any, ...]:
        return tuple(persona_module.load_persona_list()[:count])

    monkeypatch.setattr(graph_module, "draw_helpers", _draw_with_lead)
    # All three layers, so whichever slot the lead lands in is observable.
    planned = [
        graph_module._PlannedToolCall(
            tool_call=ToolCall(tool="cypher_query", call_id="cq-1", layer="layer_1_graph"),
            cypher_input=CypherQueryInput(
                query_intent="q", query_class="lookup", target_entities=["NCBIGene:672"], row_limit=10,
            ),
        ),
        graph_module._build_planned_ncbi_efetch_call("NCBIGene:672"),
        *graph_module._build_layer_tool_calls(_GENE_QUESTION, "BRCA1", []),
    ]
    stamped = graph_module._assign_helpers(planned, lead_name=lead)
    assert {call.tool_call.layer for call in stamped} == {
        "layer_1_graph", "layer_2_api", "layer_3_enrichment"
    }, "populate-check: all three layers must be planned"
    assert any(call.tool_call.persona == lead for call in stamped), (
        "the mutation did not leak the lead; the exclusion arm could not have caught it"
    )


@pytest.mark.asyncio
async def test_helpers_reach_the_wire_and_never_the_synthesis_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spy = _ModelSpy(monkeypatch, [{"text": "BRCA1", "entity_type": "gene"}])
    _install_lookup(monkeypatch)
    _install_tools(monkeypatch)

    events = await _events(_GENE_QUESTION)
    tools = _plan_tools(events)
    helper_names = {t["persona"] for t in tools}
    assert helper_names and None not in helper_names, tools
    lead = persona_module.persona_for_session(session_id="s-1", user_id=None)
    assert lead not in helper_names
    starts = [e.payload for e in events if e.type == "tool_start"]
    assert starts, "populate-check: no tool_start frames"
    assert {s["persona"] for s in starts} == helper_names
    results = [e.payload for e in events if e.type == "tool_result"]
    assert {r["persona"] for r in results} == helper_names

    assert spy.synth_prompts, "populate-check: the synth call never ran"
    for name in helper_names:
        assert name not in "\n".join(spy.synth_prompts), f"helper {name!r} reached synthesis"
    citations = [e.payload for e in events if e.type == "citation"]
    assert citations
    for name in helper_names:
        assert name not in json.dumps(citations)


@pytest.mark.asyncio
async def test_helpers_vary_between_runs_while_the_tool_set_is_identical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ModelSpy(monkeypatch, [{"text": "BRCA1", "entity_type": "gene"}])
    _install_lookup(monkeypatch)
    _install_tools(monkeypatch)

    seen_names: set[tuple[str, ...]] = set()
    tool_sets: set[tuple[str, ...]] = set()
    for _ in range(8):
        tools = _plan_tools(await _events(_GENE_QUESTION))
        seen_names.add(tuple(t["persona"] for t in tools))
        tool_sets.add(tuple(t["tool"] for t in tools))
    assert len(tool_sets) == 1, tool_sets
    assert len(seen_names) > 1, "eight runs drew the same helpers every time"


# ---------------------------------------------------------------------------
# The GCK fallback.
# ---------------------------------------------------------------------------


def test_fallback_candidates_admit_gene_shapes_only() -> None:
    exact: list[Any] = []
    assert graph_module._gene_shaped_fallback_candidates(_GCK_QUESTION, exact) == ["GCK", "MODY"]
    assert graph_module._gene_shaped_fallback_candidates(
        "what diseases are linked to brca1?", exact
    ) == ["brca1"]
    # Lowercase words and Title-case words are never candidates.
    assert graph_module._gene_shaped_fallback_candidates("which genes cause disease in mice", exact) == []
    # A typed identifier's span is excluded, and the cap is three.
    exact_matches = graph_module.resolve_exact_identifiers("NCBIGene:672 with rs334, CFTR, EGFR, TP53, KRAS")
    assert exact_matches, "populate-check: the pre-pass resolved nothing"
    candidates = graph_module._gene_shaped_fallback_candidates(
        "NCBIGene:672 with rs334, CFTR, EGFR, TP53, KRAS", exact_matches
    )
    assert candidates == ["CFTR", "EGFR", "TP53"]
    assert "NCBIGene" not in candidates and "rs334" not in candidates


@pytest.mark.asyncio
async def test_fallback_resolves_gck_when_the_model_found_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    _ModelSpy(monkeypatch, [])
    asked = _install_lookup(monkeypatch)
    _install_tools(monkeypatch)

    events = await _events(_GCK_QUESTION)
    think = next(e for e in events if e.type == "think")
    resolved = {r["curie"]: r["text"] for r in think.payload["resolved_entities"]}
    assert resolved == {"NCBIGene:2645": "GCK"}, resolved
    assert "GCK" in asked and "MODY" in asked, asked
    plan = next(e for e in events if e.type == "plan")
    assert "unresolved" not in plan.payload["narrative"], "MODY must not become a refusal"
    assert plan.payload["tool_calls"], "the gene question must plan tools"
    assert events[-1].payload["trust_outcome"] != "refuse"


@pytest.mark.asyncio
async def test_fallback_does_not_run_when_the_model_extracted_a_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ModelSpy(monkeypatch, [{"text": "BRCA1", "entity_type": "gene"}])
    asked = _install_lookup(monkeypatch)
    _install_tools(monkeypatch)

    events = await _events("Which diseases are linked to BRCA1 and MODY?")
    assert asked == ["BRCA1"], asked
    think = next(e for e in events if e.type == "think")
    assert [r["curie"] for r in think.payload["resolved_entities"]] == ["NCBIGene:672"]


@pytest.mark.asyncio
async def test_an_unconfirmed_model_span_still_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    """The refusal path is untouched for a span the MODEL extracted."""
    _ModelSpy(monkeypatch, [{"text": "BRCA9", "entity_type": "gene"}])
    _install_lookup(monkeypatch)
    _install_tools(monkeypatch)

    events = await _events("Which diseases are associated with BRCA9?")
    plan = next(e for e in events if e.type == "plan")
    assert "unresolved gene symbol candidate(s): BRCA9" in plan.payload["narrative"]
    assert events[-1].payload["trust_outcome"] == "refuse"


@pytest.mark.asyncio
async def test_the_fallback_arm_goes_red_when_the_extractor_is_emptied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation: with no candidates the GCK question resolves nothing."""
    monkeypatch.setattr(graph_module, "_gene_shaped_fallback_candidates", lambda text, exact: [])
    _ModelSpy(monkeypatch, [])
    asked = _install_lookup(monkeypatch)
    _install_tools(monkeypatch)

    events = await _events(_GCK_QUESTION)
    think = next(e for e in events if e.type == "think")
    assert think.payload["resolved_entities"] == []
    assert asked == []


# ---------------------------------------------------------------------------
# The contract.
# ---------------------------------------------------------------------------


def test_tool_call_and_tool_start_accept_and_default_the_persona_fields() -> None:
    bare = ToolCall(tool="cypher_query", call_id="c1", layer="layer_1_graph")
    assert bare.persona is None and bare.persona_about is None and bare.persona_wikipedia is None
    full = ToolCall(
        tool="cypher_query", call_id="c1", layer="layer_1_graph",
        persona="Franklin", persona_about="x", persona_wikipedia="https://en.wikipedia.org/wiki/F",
    )
    assert full.persona == "Franklin"
    start = ToolStartPayload(call_id="c1", tool="cypher_query", layer="layer_1_graph", status="running")
    assert start.persona is None
    with pytest.raises(ValueError):
        ToolCall(tool="cypher_query", call_id="c1", layer="layer_1_graph", persona="x" * 65)


# ---------------------------------------------------------------------------
# The order the coordinator receives, accepted by the coordinator on
# 2026-09-14: Layer 2, then Layer 3, then Layer 1, and the Layer 3 stash.
# ---------------------------------------------------------------------------


def _three_layer_plan() -> list[Any]:
    return [
        graph_module._PlannedToolCall(
            tool_call=ToolCall(tool="cypher_query", call_id="cq-1", layer="layer_1_graph"),
            cypher_input=CypherQueryInput(
                query_intent="q", query_class="lookup", target_entities=["NCBIGene:672"], row_limit=10,
            ),
        ),
        graph_module._build_planned_ncbi_efetch_call("NCBIGene:672"),
        *graph_module._build_layer_tool_calls(_GENE_QUESTION, "BRCA1", []),
    ]


@pytest.mark.asyncio
async def test_findings_reach_the_coordinator_layer_2_then_3_then_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_tools(monkeypatch)
    _, result = await _act(_three_layer_plan())
    layers = [f.layer for f in result["findings"]]
    assert layers == [
        "layer_2_api", "layer_3_enrichment", "layer_3_enrichment", "layer_1_graph"
    ], layers
    # The Layer 3 stash carries the typed outputs, keyed by call_id.
    stash = result["layer3_raw_outputs"]
    assert {type(v).__name__ for v in stash.values()} == {
        "PubtatorAnnotateOutput", "ClinicalTrialsSearchOutput"
    }
    assert set(stash) == {
        f.call_id for f in result["findings"] if f.layer == "layer_3_enrichment"
    }
    assert set(result["layer2_raw_outputs"]) == {
        f.call_id for f in result["findings"] if f.tool == "ncbi_efetch"
    }


@pytest.mark.asyncio
async def test_the_order_arm_goes_red_when_plan_order_is_restored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation: an identity `sorted` key restores plan order (1, 2, 3, 3)."""
    _install_tools(monkeypatch)
    real_sorted = sorted

    def _plan_order(items: Any, key: Any = None) -> list[Any]:
        return real_sorted(items, key=lambda pair: pair[0])

    monkeypatch.setattr(graph_module, "sorted", _plan_order, raising=False)
    _, result = await _act(_three_layer_plan())
    assert next(f.layer for f in result["findings"]) == "layer_1_graph", (
        "the mutation did not restore plan order; the order arm could not have caught it"
    )


# ---------------------------------------------------------------------------
# The Layer 3 citation branch (approved 2026-09-14): a grounded claim from
# one of the four other Layer 2/3 tools is cited through the tool's own
# builder, with the record's own identity and the tool's own provenance.
# ---------------------------------------------------------------------------

import re as _re

from system_03_search_agent.contracts.events import NCBI_SOURCE_URL_PATTERN
from system_03_search_agent.synthesis.provenance_defaults import defaults_for_tool


async def _cited_run(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    _ModelSpy(monkeypatch, [{"text": "BRCA1", "entity_type": "gene"}])
    _install_lookup(monkeypatch)
    _install_tools(monkeypatch)
    events = await _events(_GENE_QUESTION)
    citations = [e.payload for e in events if e.type == "citation"]
    assert citations, "populate-check: the run cited nothing"
    return citations


@pytest.mark.asyncio
async def test_a_trial_citation_carries_its_own_source_id_and_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    citations = await _cited_run(monkeypatch)
    trials = [c for c in citations if c["source_url"].startswith("https://clinicaltrials.gov/study/")]
    assert trials, "populate-check: no trial was cited"
    defaults = defaults_for_tool("clinicaltrials_search")
    for c in trials:
        assert c["source"] == "clinicaltrials.gov", c
        assert c["source_id"] == c["source_url"].rsplit("/", 1)[1], c
        assert c["evidence_kind"] == defaults["evidence_kind"], c
        assert c["license"] == defaults["license"], c
        assert c["layer"] == "layer_3_enrichment"
    # The registry's trials license happens to equal the Layer 1 literal, so
    # `source` and `source_id` are what separate the branch from the generic
    # path; the mutation arm below keys on them for that reason.
    assert all(c["source"] != "clinicaltrials_search" for c in trials)


@pytest.mark.asyncio
async def test_a_pubtator_citation_carries_the_pubtator_id_and_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    citations = await _cited_run(monkeypatch)
    literature = [c for c in citations if c["source"] not in ("clinicaltrials.gov", "MedGen", "cypher_query", "NCBIGene") and c["layer"] == "layer_3_enrichment"]
    assert literature, [c["source"] for c in citations]
    defaults = defaults_for_tool("pubtator_annotate")
    for c in literature:
        assert c["source_id"] == "@GENE_BRCA1", c
        assert c["evidence_kind"] == defaults["evidence_kind"]
        assert c["license"] == defaults["license"]
        assert c["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/672"


@pytest.mark.asyncio
async def test_every_citation_stays_host_pinned(monkeypatch: pytest.MonkeyPatch) -> None:
    citations = await _cited_run(monkeypatch)
    pattern = _re.compile(NCBI_SOURCE_URL_PATTERN)
    assert {c["layer"] for c in citations} >= {"layer_1_graph", "layer_3_enrichment"}
    for c in citations:
        assert pattern.match(c["source_url"]), c["source_url"]


def test_dbsnp_branch_uses_the_rs_id_and_its_own_builder() -> None:
    from system_03_search_agent.harness.coordinator_worker import Finding
    from system_03_search_agent.synthesis.findings import SynthFinding
    from system_03_search_agent.tools.ncbi_dbsnp_schemas import NcbiDbsnpOutput

    out = NcbiDbsnpOutput(
        status="ok", rsid="rs334", spdi_canonical="NC_000011.10:5227001:T:A",
        clinical_significance=["pathogenic"], source_url="https://www.ncbi.nlm.nih.gov/snp/rs334",
    )
    shaped = graph_module._layer_tool_output_to_structured_fields("ncbi_dbsnp", out)
    finding = Finding(
        call_id="db-1", tool="ncbi_dbsnp", layer="layer_2_api", source="structured_pass_through",
        structured_fields=shaped, extracted_entities=None, normalized_ids=None, evidence_summary=None,
    )
    sf = SynthFinding(
        ref_index=1, citation_id="db-1-1", layer="layer_2_api", tool="ncbi_dbsnp",
        field="clinical_significance", field_value="pathogenic",
        source_url="https://www.ncbi.nlm.nih.gov/snp/rs334", value_is_suspect=False,
        curie_fallback=False, entity_type="Variant record", curie="",
    )
    citation = graph_module._layer3_citation_for_synth_finding(
        sf, [finding], {"db-1": out}, "db-1-1", 3, "rs334 is pathogenic [3]"
    )
    assert citation is not None
    assert citation.source == "dbsnp" and citation.source_id == "rs334"
    assert citation.license == defaults_for_tool("ncbi_dbsnp")["license"]
    assert citation.display_index == 3 and citation.citation_id == "db-1-1"


def test_layer3_branch_falls_back_to_tool_defaults_without_a_stash() -> None:
    from system_03_search_agent.synthesis.findings import SynthFinding

    sf = SynthFinding(
        ref_index=1, citation_id="ct-1-1", layer="layer_3_enrichment", tool="clinicaltrials_search",
        field="name", field_value="Trial", source_url="https://clinicaltrials.gov/study/NCT00000001",
        value_is_suspect=False, curie_fallback=False, entity_type="Clinical trial", curie="",
    )
    citation = graph_module._layer3_citation_for_synth_finding(sf, [], {}, "ct-1-1", 1, "Trial [1]")
    assert citation is not None
    assert citation.source_id == "unknown" and citation.source == "clinicaltrials_search"
    assert citation.license == defaults_for_tool("clinicaltrials_search")["license"]


@pytest.mark.asyncio
async def test_the_provenance_arm_goes_red_when_the_branch_is_bypassed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation: with the branch's tool set emptied every Layer 3 claim takes
    the generic path again, and the trial citation reverts to the Layer 1
    literals and the tool name, which is exactly what the first arm refuses."""
    monkeypatch.setattr(graph_module, "_LAYER3_CITATION_TOOLS", frozenset())
    citations = await _cited_run(monkeypatch)
    trials = [c for c in citations if c["source_url"].startswith("https://clinicaltrials.gov/study/")]
    assert trials
    assert all(c["source"] == "clinicaltrials_search" and c["source_id"] == "unknown" for c in trials), (
        "the mutation did not reach the generic path; the provenance arm could not have caught it"
    )
