"""A reader is told when a search did not finish, and what to type when the
product could not tell what was asked.

Decided from the user's chair on 2026-09-22, after the consistency run
measured L-01 (one graph call in ten losing its result) and its causes were
read: a question naming nothing the product can look up, or a second graph
search running past the act step's budget. Before this, the first case
refused with "I could not find grounded evidence", which a reader takes as
"there is nothing on this", and the second arrived as a thinner answer with
no reason anywhere.

Drives the real `write_node` the way `test_write_answer_structure.py` does,
with only the Synth model call faked, on states whose `failed_searches`
carry the reasons the act step now records.

Populate checks: the refusal arms compare against the ORIGINAL wording on a
state with no failed search, and the note arm asserts absence on the same
state with the failure removed, so neither direction can pass vacuously.
"""

from __future__ import annotations

import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.synthesis.refuse import (
    FAILED_SEARCH_MESSAGE,
    FAILED_SEARCH_NOTE,
    REFUSE_MESSAGE,
    UNRESOLVED_QUESTION_MESSAGE,
    refusal_message_for,
)
from tests.system_03_search_agent.core.test_write_answer_structure import (
    _install,
    _state,
    _structured_reply,
    _tokens,
)

_NO_ENTITY = {
    "tool": "cypher_query",
    "layer": "layer_1_graph",
    "reason": (
        "0 row(s) of 0: no entity could be identified in this query, so no graph "
        "lookup was attempted. Name the gene, variant, disease or organism, or "
        "supply a CURIE such as NCBIGene:672. Retrying this query unchanged will "
        "not help."
    ),
}
_TIMED_OUT = {
    "tool": "cypher_query",
    "layer": "layer_1_graph",
    "reason": "0 row(s) of 0: call did not complete within its per-step timeout budget",
}


def _refusal_state(failed_searches: list[dict[str, str]]) -> dict[str, object]:
    """A state in which one graph search ran and produced no rows.

    The act step leaves a `Finding` with `status: "error"` (or `"empty"`)
    for such a call, which is what `_tool_execution_outcome` reads to make
    the run a refusal rather than a no-tool answer; the same call's reason
    is what `failed_searches` carries.
    """
    from system_03_search_agent.harness.coordinator_worker import Finding

    state = _state("researcher")
    status = "error" if failed_searches else "empty"
    reason = failed_searches[0]["reason"] if failed_searches else None
    state["findings"] = [
        Finding(
            call_id="cq-failed",
            tool="cypher_query",
            layer="layer_1_graph",
            source="structured_pass_through",
            structured_fields={
                "status": status, "row_count": 0, "total_available": 0,
                "truncated": False, "rows": [], "error": reason,
            },
            extracted_entities=None,
            normalized_ids=None,
            evidence_summary=None,
        )
    ]
    state["findings_count"] = 1
    state["failed_searches"] = failed_searches
    return state


def _events_of(result: dict, kind: str) -> list[dict]:
    return [event.payload for event in result["events"] if event.type == kind]


def test_the_chooser_ranks_a_no_entity_reason_above_any_other() -> None:
    assert refusal_message_for([]) == REFUSE_MESSAGE
    assert refusal_message_for(None) == REFUSE_MESSAGE
    assert refusal_message_for([_TIMED_OUT]) == FAILED_SEARCH_MESSAGE
    assert refusal_message_for([_TIMED_OUT, _NO_ENTITY]) == UNRESOLVED_QUESTION_MESSAGE


@pytest.mark.asyncio
async def test_a_question_the_product_could_not_read_is_asked_for_a_name(monkeypatch) -> None:
    # No finding lines reach the model on a refusal, and the shared structured
    # reply builder expects some, so the fake model answers plainly here.
    _install(monkeypatch, lambda _lines: "ok")
    result = await graph_module.write_node(_refusal_state([_NO_ENTITY]))
    text = "".join(t["text"] for t in _events_of(result, "token"))
    assert text.startswith(UNRESOLVED_QUESTION_MESSAGE), text
    signal = _events_of(result, "trust_signal")[-1]
    assert signal["outcome"] == "refuse"
    assert signal["message"] == UNRESOLVED_QUESTION_MESSAGE
    assert "could not find grounded evidence" not in text


@pytest.mark.asyncio
async def test_a_failed_search_with_nothing_found_invites_a_retry(monkeypatch) -> None:
    # No finding lines reach the model on a refusal, and the shared structured
    # reply builder expects some, so the fake model answers plainly here.
    _install(monkeypatch, lambda _lines: "ok")
    result = await graph_module.write_node(_refusal_state([_TIMED_OUT]))
    text = "".join(t["text"] for t in _events_of(result, "token"))
    assert text.startswith(FAILED_SEARCH_MESSAGE), text
    assert _events_of(result, "trust_signal")[-1]["message"] == FAILED_SEARCH_MESSAGE


@pytest.mark.asyncio
async def test_nothing_failed_and_nothing_found_keeps_the_original_wording(monkeypatch) -> None:
    # No finding lines reach the model on a refusal, and the shared structured
    # reply builder expects some, so the fake model answers plainly here.
    _install(monkeypatch, lambda _lines: "ok")
    result = await graph_module.write_node(_refusal_state([]))
    text = "".join(t["text"] for t in _events_of(result, "token"))
    assert text.startswith(REFUSE_MESSAGE), text
    assert _events_of(result, "trust_signal")[-1]["message"] == REFUSE_MESSAGE


@pytest.mark.asyncio
async def test_an_answer_that_lost_a_search_says_so_and_is_not_yet_confirmed(monkeypatch) -> None:
    _install(monkeypatch, _structured_reply)
    state = _state("researcher")
    state["failed_searches"] = [_TIMED_OUT]
    result = await graph_module.write_node(state)
    tokens = _tokens(result)
    notes = [t["text"] for t in tokens if t["kind"] == "note"]
    assert FAILED_SEARCH_NOTE in notes, notes
    assert any(t["kind"] == "claim" for t in tokens), "the answer itself still stands"
    done = _events_of(result, "done")[-1]
    assert done["trust_outcome"] in ("ask", "flag"), done


@pytest.mark.asyncio
async def test_an_answer_with_every_search_finished_carries_no_such_note(monkeypatch) -> None:
    _install(monkeypatch, _structured_reply)
    state = _state("researcher")
    state["failed_searches"] = []
    result = await graph_module.write_node(state)
    notes = [t["text"] for t in _tokens(result) if t["kind"] == "note"]
    assert FAILED_SEARCH_NOTE not in notes, notes
