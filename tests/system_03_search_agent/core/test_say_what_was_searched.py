"""Cards 94 (group B), 91 and 77: the answer's notes say what was searched
and what failed, in plain words, where it used to be under Show work only or
nowhere.

Coverage: the isolate disclosure reaches the notes (and an ordinary question
carries none); a lost background search names its kind of source and, when
typed, its reason; a resolved disease whose name lookup failed says that
literature and trials were not searched, and a successful lookup does not.
Not covered: live NCBI behaviour.
"""
from __future__ import annotations

from typing import Any

import pytest

from system_03_search_agent.contracts.events import ResolvedEntity as EventResolvedEntity
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.core import isolate_search
from system_03_search_agent.synthesis.refuse import FAILED_SEARCH_NOTE
from tests.system_03_search_agent.core import test_isolate_search_wiring as _isolate_wiring
from tests.system_03_search_agent.core import test_write_answer_structure as _write_helpers

GOLDEN_QUESTION = _isolate_wiring.GOLDEN_QUESTION
_state = _isolate_wiring._state
_install = _write_helpers._install
_structured_reply = _write_helpers._structured_reply
_tokens = _write_helpers._tokens
_write_state = _write_helpers._state


def _notes(result: dict) -> list[str]:
    return [t["text"] for t in _tokens(result) if t["kind"] == "note"]


@pytest.mark.asyncio
async def test_the_isolate_disclosure_is_in_the_answers_notes(monkeypatch) -> None:
    _install(monkeypatch, _structured_reply)
    question = isolate_search.parse_isolate_question(GOLDEN_QUESTION)
    state = _write_state("researcher")
    state["isolate_question"] = question
    notes = _notes(await graph_module.write_node(state))
    joined = " ".join(notes)
    assert "blaCTX-M" in joined and "blaTEM and blaSHV alleles were not searched" in joined, notes
    # Populate check: the same answer with no isolate question has no such note.
    plain = _notes(await graph_module.write_node(_write_state("researcher")))
    assert not any("blaCTX-M" in n for n in plain), plain


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (
            {"tool": "ncbi_efetch", "kind": "rate_limited", "source": "pubmed"},
            ("The background search of PubMed did not finish because NCBI was busy, so "
                "this answer may be missing sources from it. Ask again in a minute."),
        ),
        (
            {"tool": "cypher_query", "kind": "timed_out", "source": ""},
            ("The background search of the knowledge graph did not finish because it "
                "took too long, so this answer may be missing sources from it. Ask again to retry."),
        ),
        (
            {"tool": "clinicaltrials_search", "kind": "other", "source": ""},
            ("The background search of ClinicalTrials.gov did not finish, so this "
                "answer may be missing sources from it. Ask again to retry."),
        ),
    ],
)
def test_a_lost_search_names_its_source_and_reason(failure: dict, expected: str) -> None:
    assert graph_module._build_failed_search_note([failure]) == expected


def test_a_lost_search_with_nothing_typed_keeps_the_original_sentence() -> None:
    assert graph_module._build_failed_search_note([{"tool": "x", "kind": "other"}]) == FAILED_SEARCH_NOTE


def test_two_lost_searches_are_both_named() -> None:
    note = graph_module._build_failed_search_note(
        [
            {"tool": "ncbi_efetch", "kind": "rate_limited", "source": "pubmed"},
            {"tool": "ncbi_efetch", "kind": "rate_limited", "source": "clinvar"},
        ]
    )
    assert "PubMed and ClinVar" in note and "NCBI was busy" in note and "from them" in note


@pytest.mark.asyncio
async def test_the_lost_search_note_reaches_the_answer(monkeypatch) -> None:
    _install(monkeypatch, _structured_reply)
    state = _write_state("researcher")
    state["failed_searches"] = [{"tool": "ncbi_efetch", "kind": "rate_limited", "source": "gds"}]
    notes = _notes(await graph_module.write_node(state))
    assert any("GEO DataSets" in n and "NCBI was busy" in n for n in notes), notes


@pytest.mark.asyncio
async def test_a_disease_lookup_that_failed_is_said_in_the_notes(monkeypatch) -> None:
    _install(monkeypatch, _structured_reply)
    state = _write_state("researcher")
    state["disease_lookup_failed"] = True
    notes = _notes(await graph_module.write_node(state))
    assert any("did not search the literature or clinical trials" in n for n in notes), notes
    clean = _notes(await graph_module.write_node(_write_state("researcher")))
    assert not any("clinical trials" in n for n in clean), clean


async def _plan_for_disease(monkeypatch: pytest.MonkeyPatch, name: str | None) -> dict[str, Any]:
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")

    async def _resolve(curies: Any) -> dict[str, str | None]:
        return {c: name for c in curies}

    monkeypatch.setattr(graph_module, "resolve_concept_ids", _resolve)
    state = _state(
        "Any trials for GERD?",
        resolved_entities=[EventResolvedEntity(text="GERD", curie="MedGen:C0017168", confidence=1.0)],
        query_class="single_hop",
    )
    return await graph_module.plan_node(state)


@pytest.mark.asyncio
async def test_plan_flags_a_disease_whose_name_lookup_failed(monkeypatch) -> None:
    failed = await _plan_for_disease(monkeypatch, None)
    assert failed["disease_lookup_failed"] is True
    worked = await _plan_for_disease(monkeypatch, "Gastroesophageal reflux disease")
    assert worked["disease_lookup_failed"] is False
