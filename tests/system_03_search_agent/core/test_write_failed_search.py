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

Card 63 (2026-09-27), the outage arms at the end of this file: when NCBI
itself says a database is down, the note names the database, says the
answer may be missing what it holds, and says "Try again later", never "Ask again to
retry", which during an outage sends a person straight back into it. A
timeout or a rate limit keeps the original note, where asking again can
help. The note is chosen from the typed `kind` and `source` keys the act
step records, and every arm pairs the outage wording with the original
wording on the same state, so neither can pass on a builder that returns a
constant.
"""

from __future__ import annotations

import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.synthesis.refuse import (
    FAILED_SEARCH_MESSAGE,
    FAILED_SEARCH_NOTE,
    REFUSE_MESSAGE,
    SEARCH_DOWN_MESSAGE,
    SERVICE_DOWN_KIND,
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


# ---------------------------------------------------------------------------
# Card 63: a search that is down at NCBI says "try again later".
# ---------------------------------------------------------------------------

_PUBMED_DOWN = {
    "tool": "ncbi_efetch",
    "layer": "layer_2_api",
    "reason": "search error: the service is down at NCBI",
    "kind": "service_down",
    "source": "pubmed",
}
_CLINVAR_DOWN = {**_PUBMED_DOWN, "source": "clinvar"}
_PUBMED_DOWN_NOTE = (
    "PubMed is down at NCBI right now, so this answer may be missing papers "
    "from it. Try again later."
)


def _note_texts(result: dict) -> list[str]:
    return [t["text"] for t in _tokens(result) if t["kind"] == "note"]


@pytest.mark.asyncio
async def test_an_answer_that_lost_a_search_to_an_outage_says_try_later_not_ask_again(
    monkeypatch,
) -> None:
    _install(monkeypatch, _structured_reply)
    state = _state("researcher")
    state["failed_searches"] = [_PUBMED_DOWN]
    result = await graph_module.write_node(state)
    notes = _note_texts(result)

    assert _PUBMED_DOWN_NOTE in notes, notes
    assert FAILED_SEARCH_NOTE not in notes, notes
    assert not any("ask again" in note.lower() for note in notes), notes
    # Unchanged by card 63: the answer still stands and is still marked
    # "not yet confirmed". What counts as confirmed did not move.
    assert any(t["kind"] == "claim" for t in _tokens(result)), "the answer itself still stands"
    done = _events_of(result, "done")[-1]
    assert done["trust_outcome"] in ("ask", "flag"), done


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["timed_out", "rate_limited", "other"])
async def test_a_failure_asking_again_can_help_keeps_the_original_note(
    monkeypatch, kind: str
) -> None:
    """The populate check for the arm above: the SAME state, with the same
    database, under a kind where asking again can help, still gets the
    original "Ask again to retry" note, so the outage wording is about the
    kind and not a builder that stopped saying it."""
    _install(monkeypatch, _structured_reply)
    state = _state("researcher")
    state["failed_searches"] = [{**_PUBMED_DOWN, "kind": kind}]
    result = await graph_module.write_node(state)
    notes = _note_texts(result)
    assert FAILED_SEARCH_NOTE in notes, notes
    assert _PUBMED_DOWN_NOTE not in notes, notes


def test_the_outage_note_names_each_database_that_is_down_once() -> None:
    build = graph_module._build_failed_search_note
    assert build([_PUBMED_DOWN]) == _PUBMED_DOWN_NOTE
    assert build([_PUBMED_DOWN, _CLINVAR_DOWN, _PUBMED_DOWN]) == (
        "PubMed and ClinVar are down at NCBI right now, so this answer may be "
        "missing sources from them. Try again later."
    )


def test_the_outage_note_says_when_another_search_also_failed() -> None:
    note = graph_module._build_failed_search_note([_PUBMED_DOWN, _TIMED_OUT])
    assert note == (
        "PubMed is down at NCBI right now, so this answer may be missing papers "
        "from it. Another background search did not finish, so other sources may "
        "be missing too. Try again later."
    )
    assert "ask again" not in note.lower()


def test_an_outage_on_a_database_the_note_cannot_name_is_still_disclosed() -> None:
    note = graph_module._build_failed_search_note([{**_PUBMED_DOWN, "source": "bioproject"}])
    assert note == (
        "Some of NCBI's databases are down right now, so this answer may be "
        "missing sources from them. Try again later."
    )


def test_a_failed_search_recorded_before_card_63_keeps_the_original_note() -> None:
    """A mapping with no `kind` key, the shape every earlier caller and test
    builds, is read as `other`: the original note, never a false outage."""
    assert graph_module._build_failed_search_note([_TIMED_OUT]) == FAILED_SEARCH_NOTE
    assert graph_module._build_failed_search_note([_NO_ENTITY]) == FAILED_SEARCH_NOTE


# ---------------------------------------------------------------------------
# Card 63, the refusal: when every search failed and one of them is down at
# NCBI, the refusal says "try again later", never "ask again to retry".
# ---------------------------------------------------------------------------


def test_the_refusal_chooser_says_try_later_when_ncbi_said_a_search_is_down() -> None:
    assert refusal_message_for([_PUBMED_DOWN]) == SEARCH_DOWN_MESSAGE
    # One search down is enough, as for the note under an answer: asking
    # again at once cannot help while it is down.
    assert refusal_message_for([_TIMED_OUT, _PUBMED_DOWN]) == SEARCH_DOWN_MESSAGE
    # A question the product could not read still outranks it: naming the
    # gene is the thing to fix first.
    assert refusal_message_for([_PUBMED_DOWN, _NO_ENTITY]) == UNRESOLVED_QUESTION_MESSAGE
    assert "ask again" not in SEARCH_DOWN_MESSAGE.lower()
    assert "try again later" in SEARCH_DOWN_MESSAGE.lower()


def test_the_outage_refusal_says_a_source_is_down_not_a_search() -> None:
    """F-63-A02: the failed call can be a record fetch, a summary or a link,
    so the refusal names a "source", never a "search"."""
    assert SEARCH_DOWN_MESSAGE == (
        "A source I needed is down at NCBI right now, so I could not find "
        "grounded evidence this time. Try again later, or try NCBI's "
        "cross-database search:"
    )
    assert "A search I needed" not in SEARCH_DOWN_MESSAGE


@pytest.mark.parametrize("kind", ["timed_out", "rate_limited", "other"])
def test_the_refusal_chooser_keeps_ask_again_where_asking_again_can_help(kind: str) -> None:
    """The populate check for the arm above: the SAME mapping, with the same
    database, under a kind where asking again can help, keeps today's
    wording, so the outage wording is about the kind and not a chooser
    that stopped saying "ask again"."""
    assert refusal_message_for([{**_PUBMED_DOWN, "kind": kind}]) == FAILED_SEARCH_MESSAGE


def test_the_refusal_reads_the_kind_the_transport_names() -> None:
    """`refuse.py` writes the value out rather than importing tool transport
    code; this pins the two equal, so neither can drift from the other."""
    from system_03_search_agent.tools import ncbi_transport

    assert SERVICE_DOWN_KIND in ncbi_transport.FAILURE_KINDS
    assert _PUBMED_DOWN["kind"] == SERVICE_DOWN_KIND


@pytest.mark.asyncio
async def test_a_refusal_during_an_outage_says_try_later_not_ask_again(monkeypatch) -> None:
    # No finding lines reach the model on a refusal, and the shared structured
    # reply builder expects some, so the fake model answers plainly here.
    _install(monkeypatch, lambda _lines: "ok")
    result = await graph_module.write_node(_refusal_state([_PUBMED_DOWN]))
    text = "".join(t["text"] for t in _events_of(result, "token"))
    assert text.startswith(SEARCH_DOWN_MESSAGE), text
    assert "ask again" not in text.lower(), text
    # Section 8.4, unchanged: a refusal is never a dead end.
    assert "https://www.ncbi.nlm.nih.gov/search/all/?term=" in text, text
    signal = _events_of(result, "trust_signal")[-1]
    assert signal["outcome"] == "refuse"
    assert signal["message"] == SEARCH_DOWN_MESSAGE
    assert signal["fallback_link"].startswith("https://www.ncbi.nlm.nih.gov/search/all/")
