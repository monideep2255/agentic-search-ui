"""UI fix set 7, item 7.5 (2026-09-13): a follow-up that refers to nothing
asks for the missing detail instead of refusing.

The product owner's retest words: "the follow up must retain context or ask
clarification if the question is not clear. Because if this is a discussion,
it must flow." The retain half is Plan's antecedent binding; this file pins
the ask half through the real five-node graph with the model stubbed.

Exercised:
    "What variants cause it?" with NO session memory: Think publishes the
    clarifying question, Plan selects no tool, no tool starts, Write's text
    IS the question, and the run ends `refuse` (no claim was made).
    The same words WITH a remembered BRCA1: no clarifying question, and a
    tool runs, so the rule never fires when memory can answer the reference.
    A question that names its own entity, with no memory: no clarifying
    question, so an ordinary question is never asked to repeat itself.
    A question with no referring word and no entity ("Tell me about
    genes"): no clarifying question either.
    Card 145: a first question about to be asked back is read a second time;
    it answers when that reading resolves a subject written in the question
    word for word, is asked back otherwise, and each trigger condition is
    pinned by a question that makes one Think call. The second reading gets
    at most 4 s, fails closed on any error, and is recorded when used.

NOT exercised: the web UI's rendering of the question (frontend tests own
that), and the live models.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from system_03_search_agent.contracts.query import (
    Query,
    RequestContext,
    ResolvedEntity,
    SessionMemorySummary,
)
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.tools.cypher_schemas import CypherQueryOutput, CypherQueryRow
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput
from tests.system_03_search_agent.model_stub import (
    COMPLIANT_GUARD_CLASSIFICATION,
    compliant_synth_narrative,
    compliant_think_classification,
    fake_response,
)


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("PER_USER_DAILY_QUERY_CAP", "100")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")
    monkeypatch.setenv("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")
    monkeypatch.setattr(cost_control, "check_user_daily_query_cap", lambda *a, **k: None)
    monkeypatch.setattr(cost_control, "check_system_daily_cost_cap", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _stubbed_models_and_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    from system_03_search_agent.guardrail.classifier import GUARD_SYSTEM_INSTRUCTION
    from system_03_search_agent.synthesis.findings import SYNTH_SYSTEM_INSTRUCTION

    async def _dispatch(*args: object, **kwargs: object) -> Any:
        messages = list(kwargs.get("messages") or [])
        joined = "\n".join(str(message.get("content") or "") for message in messages)
        if GUARD_SYSTEM_INSTRUCTION in joined:
            return fake_response(COMPLIANT_GUARD_CLASSIFICATION)
        if graph_module._THINK_SYSTEM_INSTRUCTION in joined:
            return fake_response(compliant_think_classification(messages))
        if SYNTH_SYSTEM_INSTRUCTION in joined:
            return fake_response(compliant_synth_narrative(messages))
        return fake_response("MATCH (g:Gene) RETURN g LIMIT 1")

    monkeypatch.setattr(harness_module.litellm, "acompletion", _dispatch)
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )

    async def _resolve(symbol: str, *, taxon: str = "human") -> str | None:
        return {"BRCA1": "NCBIGene:672"}.get(symbol.strip().upper())

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _resolve)

    async def _cypher(harness: object, cypher_input: object) -> CypherQueryOutput:
        return CypherQueryOutput(
            status="ok",
            row_count=1,
            total_available=1,
            truncated=False,
            rows=[
                CypherQueryRow(
                    node_or_edge_type="Gene",
                    curie="NCBIGene:672",
                    fields={"name": "BRCA1 DNA repair associated"},
                    source_url="https://www.ncbi.nlm.nih.gov/gene/672",
                    graph_snapshot_version="v1",
                )
            ],
            error=None,
        )

    monkeypatch.setattr(graph_module, "cypher_query", _cypher)

    async def _efetch(tool_input: object, **kwargs: object) -> NcbiEfetchOutput:
        return NcbiEfetchOutput(
            status="empty",
            action="dataset_report",
            records=[],
            record_count=0,
            total_available=None,
            truncated=False,
            error=None,
        )

    monkeypatch.setattr(graph_module, "ncbi_efetch", _efetch)


def _memory_with_brca1() -> SessionMemorySummary:
    return SessionMemorySummary(
        session_id="clarification-test",
        last_updated=datetime.now(UTC),
        resolved_entities=[
            ResolvedEntity(mention="BRCA1", curie="NCBIGene:672", entity_type="Gene")
        ],
    )


async def _run(text: str, memory: SessionMemorySummary | None = None) -> list[Any]:
    trace_id = f"t-{uuid.uuid4().hex[:12]}"
    query = Query(text=text, session_id="clarification-test", trace_id=trace_id)
    state = {
        "query": query,
        "context": RequestContext(surface="rest_sse", session_memory=memory),
        "harness": harness_module.Harness(trace_id),
        "seq": 0,
        "start_monotonic": time.monotonic(),
        "events": [],
    }
    result = await graph_module.compiled_graph.ainvoke(state)
    return list(result.get("events", []))


def _payload(events: list[Any], event_type: str) -> dict[str, Any] | None:
    for event in events:
        if event.type == event_type:
            return event.payload
    return None


@pytest.mark.asyncio
async def test_a_follow_up_with_nothing_to_point_at_asks_which() -> None:
    """MUTATION PROOF: removing the `clarification_needed` branch in
    `write_node` turns the token arm red; removing `_needs_clarification`
    from `think_node` turns the think arm red; removing Plan's early return
    turns the tool_start arm red.
    """
    events = await _run("What variants cause it?")
    types = [event.type for event in events]
    # Populate-check: the graph ran to completion.
    assert "done" in types, types

    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] == graph_module.CLARIFICATION_QUESTION
    assert think["resolved_entities"] == []

    assert "tool_start" not in types, types
    plan = _payload(events, "plan")
    assert plan is not None and plan["tool_calls"] == []

    token = _payload(events, "token")
    assert token is not None
    assert token["text"] == graph_module.CLARIFICATION_QUESTION
    assert "which gene, variant or condition" in token["text"]

    done = _payload(events, "done")
    assert done is not None and done["trust_outcome"] == "refuse"
    assert done["total_tool_calls"] == 0


@pytest.mark.asyncio
async def test_the_same_words_with_a_remembered_gene_are_answered_not_questioned() -> None:
    """The counterfactual: memory supplies the antecedent, so the rule must
    stay silent and a tool must run."""
    events = await _run("What variants cause it?", memory=_memory_with_brca1())
    types = [event.type for event in events]
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"] is None
    assert "tool_start" in types, types
    token = _payload(events, "token")
    assert token is not None and token["text"] != graph_module.CLARIFICATION_QUESTION


@pytest.mark.asyncio
async def test_a_question_naming_its_own_entity_is_never_asked_to_repeat_itself() -> None:
    events = await _run("Which diseases are associated with BRCA1?")
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"] is None
    assert think["resolved_entities"], "populate-check: BRCA1 resolves in this stub"
    assert "tool_start" in [event.type for event in events]


@pytest.mark.asyncio
async def test_a_question_with_no_referring_word_is_not_questioned() -> None:
    events = await _run("Tell me about breast cancer genes")
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"] is None
    token = _payload(events, "token")
    assert token is None or token["text"] != graph_module.CLARIFICATION_QUESTION


# Card 145 (2026-10-22): a first question is read a second time before it is
# asked back. The owner's decision: "when the system is about to ask a first
# question back because it read no subject, it reads the question a second
# time and asks back only if that reading also finds nothing; no question
# that answers today pays for it." The fix round's terms, the owner's of the
# same day: "the second reading counts only if every subject it names is
# written word for word in the question, it runs the same organism checks as
# the first reading, it gets at most 4 s, the answer's record says it was
# used, and each trigger condition gets a test".
#
# The gap the diagnosis named: a first question that names its own subject
# in plain English, carries a referring word ("it"), and whose first reading
# does not confirm. NCBI is stubbed throughout; no test question reaches a
# prompt.

_OWN_SUBJECT_QUESTION = "What causes croup in children, and how is it usually treated?"
_BRONCHIOLITIS_QUESTION = "What causes bronchiolitis in babies, and how is it usually treated?"
_SRA_QUESTION = "Find SRA runs of SARS-CoV-2 sequenced on Illumina, and where was it collected?"
_CROUP_CURIE = "MedGen:C0010380"
_MEDGEN: dict[str, list[str]] = {
    "croup": [_CROUP_CURIE],
    "bronchiolitis": ["MedGen:C0006271", "MedGen:C0001311"],
    "cystic fibrosis": ["MedGen:C0010674"],
    "sars": ["MedGen:C1519126", "MedGen:C4302012", "MedGen:C4302019"],
}
_TAXA: dict[str, tuple[str, ...]] = {
    "mycobacterium tuberculosis": ("1773",),
    "sars-cov-2": ("2697049",),
}
_EMPTY: list[dict[str, str]] = []


def _think_reply(entities: list[dict[str, str]], record_type: str = "none") -> str:
    return json.dumps(
        {
            "query_class": "exploratory",
            "narrative": "stand-in classification for tests",
            "entities": entities,
            "record_type": record_type,
        }
    )


def _disease(text: str) -> dict[str, str]:
    return {"text": text, "entity_type": "disease"}


@pytest.fixture
def think_readings(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Count Think's classification calls and, when `script` is set, answer
    them in order from it (`slow_from` delays every reply from that call on);
    every other model call keeps the file's stub. MedGen, Gene and Taxonomy
    are stubbed from the tables above."""
    record: dict[str, Any] = {"calls": 0, "script": None, "slow_from": None}
    inner = harness_module.litellm.acompletion

    async def _dispatch(*args: object, **kwargs: object) -> Any:
        messages = list(kwargs.get("messages") or [])
        joined = "\n".join(str(message.get("content") or "") for message in messages)
        if graph_module._THINK_SYSTEM_INSTRUCTION in joined:
            record["calls"] += 1
            if record["slow_from"] is not None and record["calls"] >= record["slow_from"]:
                await asyncio.sleep(5)
            script = record["script"]
            if script is not None:
                return fake_response(script[min(record["calls"], len(script)) - 1])
        return await inner(*args, **kwargs)

    monkeypatch.setattr(harness_module.litellm, "acompletion", _dispatch)

    async def _medgen(mention: str) -> tuple[list[str], int]:
        bound = _MEDGEN.get(mention.strip().lower(), [])
        return list(bound), len(bound)

    monkeypatch.setattr(graph_module, "resolve_disease_mention_to_curies", _medgen)

    async def _gene(symbol: str, *, taxon: str = "human") -> str | None:
        return {"BRCA1": "NCBIGene:672", "CFTR": "NCBIGene:1080"}.get(symbol.strip().upper())

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _gene)

    async def _taxids(name: str, max_chars: int) -> tuple[str, ...] | None:
        return _TAXA.get(name.strip().lower(), ())

    monkeypatch.setattr(graph_module, "_organism_taxids", _taxids)
    return record


def _second_reading_decisions(events: list[Any]) -> list[dict[str, Any]]:
    done = _payload(events, "done") or {}
    return [
        dict(decision)
        for decision in done.get("decisions") or []
        if dict(decision).get("name") == graph_module._SECOND_READING_POINT
    ]


# The second reading is taken: the question answers.


@pytest.mark.asyncio
async def test_an_unread_first_question_is_read_again_and_answered(
    think_readings: dict[str, Any],
) -> None:
    """MUTATION PROOF: removing the card 145 block in `_think` asks this
    question back (think arm red) and makes one Think call (count arm red)."""
    think_readings["script"] = [_think_reply(_EMPTY), _think_reply([_disease("croup")])]
    events = await _run(_OWN_SUBJECT_QUESTION)
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] is None
    assert [entity["curie"] for entity in think["resolved_entities"]] == [_CROUP_CURIE]
    assert think_readings["calls"] == 2
    token = _payload(events, "token")
    assert token is None or token["text"] != graph_module.CLARIFICATION_QUESTION


@pytest.mark.asyncio
async def test_the_bronchiolitis_question_passes_word_for_word(
    think_readings: dict[str, Any],
) -> None:
    """Card 145's own question: the second reading names "bronchiolitis",
    written in the question as a whole word, so it is taken."""
    think_readings["script"] = [_think_reply(_EMPTY), _think_reply([_disease("Bronchiolitis")])]
    events = await _run(_BRONCHIOLITIS_QUESTION)
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"] is None
    assert {entity["curie"] for entity in think["resolved_entities"]} == set(
        _MEDGEN["bronchiolitis"]
    )
    assert think_readings["calls"] == 2


@pytest.mark.asyncio
async def test_a_used_second_reading_is_recorded_in_the_done_decisions(
    think_readings: dict[str, Any],
) -> None:
    """A-145-02: the answer's record says the question was read again and
    what that reading resolved."""
    think_readings["script"] = [_think_reply(_EMPTY), _think_reply([_disease("croup")])]
    events = await _run(_OWN_SUBJECT_QUESTION)
    recorded = _second_reading_decisions(events)
    assert len(recorded) == 1
    assert recorded[0]["chosen"] == "resolved: croup"
    assert recorded[0]["decided_by"] == "plan"
    assert recorded[0].get("fallback_reason") is None


@pytest.mark.asyncio
async def test_a_correctly_named_organism_is_handled_as_the_first_reading_would(
    think_readings: dict[str, Any],
) -> None:
    """A-145-05: a second reading naming the organism of an SRA question runs
    card 56's organism anchor, so the organism is the subject searched."""
    think_readings["script"] = [
        _think_reply(_EMPTY, record_type="sra"),
        _think_reply([{"text": "SARS-CoV-2", "entity_type": "organism"}], record_type="sra"),
    ]
    events = await _run(_SRA_QUESTION)
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"] is None
    assert [entity["curie"] for entity in think["resolved_entities"]] == ["NCBITaxon:2697049"]
    assert think_readings["calls"] == 2


# The second reading is not taken: the question is asked back as today.


@pytest.mark.asyncio
async def test_two_readings_that_find_nothing_still_ask_back(
    think_readings: dict[str, Any],
) -> None:
    think_readings["script"] = [_think_reply(_EMPTY), _think_reply(_EMPTY)]
    events = await _run(_OWN_SUBJECT_QUESTION)
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] == graph_module.CLARIFICATION_QUESTION
    assert think["resolved_entities"] == []
    assert think_readings["calls"] == 2
    assert "tool_start" not in [event.type for event in events]
    assert _second_reading_decisions(events) == []


@pytest.mark.asyncio
async def test_a_second_reading_naming_an_unknown_condition_still_asks_back(
    think_readings: dict[str, Any],
) -> None:
    """A span NCBI does not confirm resolves nothing, so it is not taken."""
    think_readings["script"] = [_think_reply(_EMPTY), _think_reply([_disease("children")])]
    events = await _run(_OWN_SUBJECT_QUESTION)
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] == graph_module.CLARIFICATION_QUESTION
    assert think_readings["calls"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "entity"),
    [
        ("Is it dangerous?", _disease("cystic fibrosis")),
        ("What variants cause it?", _disease("cystic fibrosis")),
        ("Is it dangerous?", {"text": "CFTR", "entity_type": "gene"}),
        ("What variants cause it?", {"text": "CFTR", "entity_type": "gene"}),
    ],
)
async def test_a_subject_the_question_never_names_is_asked_back(
    think_readings: dict[str, Any], question: str, entity: dict[str, str]
) -> None:
    """A-145-01, the adversary's inputs: a dangling first question whose
    second reading invents a subject NCBI confirms is asked back, because
    the subject is not written in the question."""
    think_readings["script"] = [_think_reply(_EMPTY), _think_reply([entity])]
    events = await _run(question)
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] == graph_module.CLARIFICATION_QUESTION
    assert think["resolved_entities"] == []
    assert think_readings["calls"] == 2


@pytest.mark.asyncio
async def test_an_invented_subject_never_reaches_session_memory(
    think_readings: dict[str, Any],
) -> None:
    """A-145-06: the run writes memory from the plan event's resolved
    entities and the citations (`core/run.py`, the memory write). An
    invented second-reading subject leaves both empty, so nothing is
    remembered for the next "it" to bind to."""
    think_readings["script"] = [_think_reply(_EMPTY), _think_reply([_disease("cystic fibrosis")])]
    events = await _run("Is it dangerous?")
    plan = _payload(events, "plan")
    assert plan is not None and not plan.get("resolved_entities")
    assert "citation" not in [event.type for event in events]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "second",
    [
        [_disease("SARS")],
        [{"text": "SARS-CoV-2", "entity_type": "organism"}, _disease("SARS")],
    ],
    ids=["disease_piece", "organism_and_disease_piece"],
)
async def test_the_sra_question_never_binds_the_disease_cut_from_the_virus_name(
    think_readings: dict[str, Any], second: list[dict[str, str]]
) -> None:
    """A-145-04, the adversary's input: "SARS" stands in the question only as
    a piece of "SARS-CoV-2", so it is not written there word for word and
    the reading that names it is not taken."""
    think_readings["script"] = [
        _think_reply(_EMPTY, record_type="sra"),
        _think_reply(second, record_type="sra"),
    ]
    events = await _run(_SRA_QUESTION)
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] == graph_module.CLARIFICATION_QUESTION
    assert not set(_MEDGEN["sars"]) & {e["curie"] for e in think["resolved_entities"]}
    assert think_readings["calls"] == 2


def test_written_in_question_reads_whole_phrases_only() -> None:
    written = graph_module._written_in_question
    assert written("bronchiolitis", _BRONCHIOLITIS_QUESTION)
    assert written("Bronchiolitis  in babies", _BRONCHIOLITIS_QUESTION)
    assert written("SARS-CoV-2", _SRA_QUESTION)
    assert not written("SARS", _SRA_QUESTION)
    assert not written("CoV", _SRA_QUESTION)
    assert not written("cystic fibrosis", "Is it dangerous?")
    assert not written("it", "Is this itself dangerous?")
    assert not written("", _SRA_QUESTION)


# One test per trigger condition: each question below answers, or is asked
# something other than the gene question, after one reading today, and each
# would pay a second Think call if its condition were removed from the
# trigger in `_think` (J-145-02, J-145-03).


@pytest.mark.asyncio
async def test_trigger_memory_a_session_with_memory_makes_one_call(
    think_readings: dict[str, Any],
) -> None:
    """Session memory that holds no entity: not a first turn."""
    think_readings["script"] = [_think_reply(_EMPTY), _think_reply([_disease("croup")])]
    memory = SessionMemorySummary(
        session_id="clarification-test", last_updated=datetime.now(UTC), resolved_entities=[]
    )
    await _run(_OWN_SUBJECT_QUESTION, memory=memory)
    assert think_readings["calls"] == 1


@pytest.mark.asyncio
async def test_trigger_window_a_coordinate_window_makes_one_call(
    think_readings: dict[str, Any],
) -> None:
    think_readings["script"] = [_think_reply(_EMPTY)]
    events = await _run("What genes lie in chr17:43044295-43125483 and what does it do?")
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] == graph_module.coordinate_window.ASSEMBLY_QUESTION
    assert think_readings["calls"] == 1


@pytest.mark.asyncio
async def test_trigger_accession_an_accession_makes_one_call(
    think_readings: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _not_held(record: Any) -> Any:
        return graph_module._AccessionPlan(record=record, uid=None, linked={})

    monkeypatch.setattr(graph_module, "resolve_accession", _not_held)
    think_readings["script"] = [_think_reply(_EMPTY)]
    events = await _run("What is BioSample SAMN99999999 and what does it contain?")
    think = _payload(events, "think")
    assert think is not None and "Check the accession" in (think["clarifying_question"] or "")
    assert think_readings["calls"] == 1


@pytest.mark.asyncio
async def test_trigger_isolate_an_isolate_question_makes_one_call(
    think_readings: dict[str, Any],
) -> None:
    think_readings["script"] = [_think_reply(_EMPTY)]
    events = await _run("Which E. coli isolates are in Pathogen Detection and where is it found?")
    think = _payload(events, "think")
    assert think is not None
    assert "Escherichia coli" in (think["clarifying_question"] or "")
    assert think_readings["calls"] == 1


@pytest.mark.asyncio
async def test_trigger_organism_a_named_organism_makes_one_call(
    think_readings: dict[str, Any],
) -> None:
    think_readings["script"] = [
        _think_reply([{"text": "Mycobacterium tuberculosis", "entity_type": "organism"}])
    ]
    events = await _run("Is Mycobacterium tuberculosis dangerous, and how is it spread?")
    think = _payload(events, "think")
    assert think is not None
    assert "Mycobacterium tuberculosis" in (think["clarifying_question"] or "")
    assert think_readings["calls"] == 1


@pytest.mark.asyncio
async def test_trigger_exact_id_a_typed_identifier_makes_one_call(
    think_readings: dict[str, Any],
) -> None:
    think_readings["script"] = [_think_reply(_EMPTY)]
    events = await _run("What is NCBIGene:672 and why is it studied?")
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"] is None
    assert [entity["curie"] for entity in think["resolved_entities"]] == ["NCBIGene:672"]
    assert think_readings["calls"] == 1


@pytest.mark.asyncio
async def test_trigger_resolved_a_question_that_resolves_makes_one_call(
    think_readings: dict[str, Any],
) -> None:
    events = await _run("What does the BRCA1 gene do and why is it studied?")
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"] is None
    assert think["resolved_entities"], "populate-check: BRCA1 resolves in this stub"
    assert think_readings["calls"] == 1


@pytest.mark.asyncio
async def test_trigger_resolved_a_plain_english_subject_makes_one_call(
    think_readings: dict[str, Any],
) -> None:
    think_readings["script"] = [_think_reply([_disease("croup")])]
    events = await _run(_OWN_SUBJECT_QUESTION)
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"] is None
    assert think_readings["calls"] == 1


@pytest.mark.asyncio
async def test_trigger_unresolved_a_rejected_gene_symbol_makes_one_call(
    think_readings: dict[str, Any],
) -> None:
    think_readings["script"] = [_think_reply([{"text": "BRCA9", "entity_type": "gene"}])]
    events = await _run("What does BRCA9 do and why is it studied?")
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"] is None
    assert think_readings["calls"] == 1


@pytest.mark.asyncio
async def test_trigger_referring_word_a_question_without_one_makes_one_call(
    think_readings: dict[str, Any],
) -> None:
    think_readings["script"] = [_think_reply(_EMPTY)]
    events = await _run("Tell me about breast cancer genes")
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"] is None
    assert think_readings["calls"] == 1


@pytest.mark.asyncio
async def test_trigger_memory_a_remembered_subject_makes_one_call(
    think_readings: dict[str, Any],
) -> None:
    events = await _run("What variants cause it?", memory=_memory_with_brca1())
    think = _payload(events, "think")
    assert think is not None and think["clarifying_question"] is None
    assert think_readings["calls"] == 1


@pytest.mark.asyncio
async def test_the_dangling_first_message_is_still_asked_back_after_two_readings(
    think_readings: dict[str, Any],
) -> None:
    """`test_a_follow_up_with_nothing_to_point_at_asks_which`'s question with
    the file's own stub: both readings name nothing, so it is asked back."""
    events = await _run("What variants cause it?")
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] == graph_module.CLARIFICATION_QUESTION
    assert think_readings["calls"] == 2


# Time and failure: the second reading fails closed to the ask-back.


async def _resolve_nothing(classification: Any) -> Any:
    raise AssertionError("no classification should reach the resolver here")


def test_the_second_reading_budget_is_four_seconds() -> None:
    assert graph_module._SECOND_READING_BUDGET_S == 4.0


@pytest.mark.asyncio
async def test_a_very_long_think_deadline_still_caps_the_second_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """J-145-01: the budget is min(4 s, what is left of Think's deadline), so
    an hour of Think budget does not lengthen it. The 4 s is shortened here
    only so the test runs fast; its value is pinned by the test above."""
    monkeypatch.setattr(graph_module, "_SECOND_READING_BUDGET_S", 0.2)

    async def _slow(*args: object, **kwargs: object) -> Any:
        await asyncio.sleep(5)
        raise AssertionError("the budget should have stopped this reading")

    monkeypatch.setattr(graph_module, "_run_think_classification", _slow)
    started = time.monotonic()
    result = await graph_module._read_question_again(
        harness_module.Harness("t-cap"), "t", [], time.monotonic() + 3600, "q", _resolve_nothing
    )
    assert result is None
    assert time.monotonic() - started < 1.0


@pytest.mark.asyncio
async def test_no_think_budget_left_reads_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    async def _count(*args: object, **kwargs: object) -> Any:
        calls["n"] += 1
        raise AssertionError("no budget left, so no reading")

    monkeypatch.setattr(graph_module, "_run_think_classification", _count)
    result = await graph_module._read_question_again(
        harness_module.Harness("t-spent"), "t", [], time.monotonic() - 1, "q", _resolve_nothing
    )
    assert result is None and calls["n"] == 0


@pytest.mark.asyncio
async def test_the_caller_hands_the_second_reading_think_own_deadline(
    think_readings: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """J-145-06: with Think's deadline half a second away, a slow second
    reading is cut there and the question is asked back, well inside the
    4 s budget. Passing any other deadline at the call site turns this red."""
    real_deadline = graph_module._step_deadline

    def _short_think(step: str, query_class: Any = "lookup") -> float:
        if step == "think":
            return time.monotonic() + 0.5
        return real_deadline(step, query_class)

    monkeypatch.setattr(graph_module, "_step_deadline", _short_think)
    think_readings["script"] = [_think_reply(_EMPTY), _think_reply([_disease("croup")])]
    think_readings["slow_from"] = 2
    started = time.monotonic()
    events = await _run(_OWN_SUBJECT_QUESTION)
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] == graph_module.CLARIFICATION_QUESTION
    assert time.monotonic() - started < 3.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "early_exit",
    [{"cap_exceeded": True}, {"step_error": {"source": "think"}}],
    ids=["cost_cap", "step_error"],
)
async def test_the_second_reading_fails_closed_on_an_early_exit(
    monkeypatch: pytest.MonkeyPatch, early_exit: dict[str, Any]
) -> None:
    async def _exit(*args: object, **kwargs: object) -> Any:
        return early_exit

    monkeypatch.setattr(graph_module, "_run_think_classification", _exit)
    result = await graph_module._read_question_again(
        harness_module.Harness("t-exit"), "t", [], time.monotonic() + 30, "q", _resolve_nothing
    )
    assert result is None


@pytest.mark.asyncio
async def test_an_ncbi_error_in_the_second_confirmation_asks_back(
    think_readings: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """J-145-04: a confirmation that raises on the second reading leaves the
    question asked back, not a failed query."""
    real_confirm = graph_module._confirm_extracted_entities
    confirms = {"n": 0}

    async def _second_raises(entities: Any) -> Any:
        confirms["n"] += 1
        if confirms["n"] == 2:
            raise RuntimeError("stand-in NCBI failure")
        return await real_confirm(entities)

    monkeypatch.setattr(graph_module, "_confirm_extracted_entities", _second_raises)
    think_readings["script"] = [_think_reply(_EMPTY), _think_reply([_disease("croup")])]
    events = await _run(_OWN_SUBJECT_QUESTION)
    types = [event.type for event in events]
    assert confirms["n"] == 2, "populate-check: the second confirmation ran"
    assert "error" not in types and "done" in types
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] == graph_module.CLARIFICATION_QUESTION


@pytest.mark.asyncio
async def test_a_failed_second_reading_is_not_logged_as_a_failed_step(
    think_readings: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    """J-145-05: two unusable replies on the second reading leave the run
    asking back, and nothing logs that Think failed."""
    think_readings["script"] = [_think_reply(_EMPTY), "not json", "not json"]
    with caplog.at_level(logging.INFO):
        events = await _run(_OWN_SUBJECT_QUESTION)
    think = _payload(events, "think")
    assert think is not None
    assert think["clarifying_question"] == graph_module.CLARIFICATION_QUESTION
    assert think_readings["calls"] == 3
    assert not [r for r in caplog.records if "step failed" in r.getMessage()]
    graph_warnings = [
        r
        for r in caplog.records
        if r.name == graph_module.__name__ and r.levelno >= logging.WARNING
    ]
    assert graph_warnings == [], [r.getMessage() for r in graph_warnings]
