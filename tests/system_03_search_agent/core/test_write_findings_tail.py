"""The findings tail in `write_node` (UI fix set 10, item 10.1, second cut).

The product owner's standard: "the exact words can be different but a user
should get exact sources which must be consistent." After the first cut
made retrieval deterministic, the cited set still varied run to run because
a citation exists only where the model's prose made a grounded claim. The
tail appends one code-built sentence per prepared finding the model left
out, grounded by the same pass, so the cited set equals the prepared set.

Every arm drives the real `write_node` with the real grounding pass; only
the model call is faked, echoing a chosen subset of the findings it is
shown, the same fixture shape `test_write_completeness.py` uses.

How each arm was shown able to fail (run against a mutation before being
kept):

- The tail fires for unreported findings and the cited set equals the
  prepared set. Mutation: adding `and False` to the tail's trigger turned
  it red (one citation of three).
- The note precedes the tail with no marker, and the tail's chunks carry
  the tail's own citation ids. Mutation: passing offset 0 to
  `_renumber_markers` made the tail chunks resolve to the model's slot,
  so the tail token's marker_ids named the wrong citation and the arm went
  red; deleting the note from the merged narrative turned the note arm red.
- The tail stays out when the model reported everything, and out after
  the structured fallback. Mutation: adding `and False` to the trigger
  turned the first arm red (above). The second arm did NOT go red when
  `not structured_fallback_used` was removed from the trigger, and that is
  recorded rather than claimed away: after a full fallback nothing is left
  unreported, so the tail has nothing to fire on whatever the guard says.
  The guard is defence for the case the fallback leaves a stripped value
  behind, where the tail would re-fail on the same sentence; the arm pins
  the observable property (no tail note in a fallback answer), not the
  guard.
- A tail sentence the pass strips leaves the incompleteness note and the
  `ask` floor. Mutation: dropping the `if omitted_findings` note block made
  the answer ship as `answer` with no disclosure, red.
- The offer keys on records beyond the prepared list. Mutation: keying
  `more_records_exist` on `omitted_findings` again made the offer vanish
  on a truncated answer, red, and appear on a complete one, red.
- A go-deeper turn after a full-tail answer still cites the unseen records
  first. Mutation: dropping `defer_source_urls=` from the
  `build_synth_findings` call made the first citation row 1 again.
"""

from __future__ import annotations

import re
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.contracts.query import Query
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.synthesis.findings import SYNTH_SYSTEM_INSTRUCTION

_FINDING_LINE = re.compile(r"^\[(\d+)\]\s+(.+)$", re.MULTILINE)
_CORRECTION_MARKER = "COMPLETENESS CORRECTION"

_ROWS = [
    {
        "node_or_edge_type": "Disease",
        "curie": f"MedGen:C{index}",
        "fields": {"name": f"disease name number {index}"},
        "source_url": f"https://www.ncbi.nlm.nih.gov/medgen/{index}",
        "graph_snapshot_version": "v1",
    }
    for index in range(1, 4)
]


def _fake_response(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


def _narrative_covering(prompt: str, ref_indices: set[int]) -> str:
    clauses = [
        f"{body.strip()} [{index}]"
        for index, body in _FINDING_LINE.findall(prompt)
        if int(index) in ref_indices
    ]
    if not clauses:
        return "I could not find information on this."
    return ". ".join(clauses) + "."


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")


@pytest.fixture
def model_reports(monkeypatch: pytest.MonkeyPatch):
    """Install a Synth fake that reports exactly `first` on the first call
    and `repaired` on the completeness repair (empty means the repair
    returns nothing new, so the first answer stands)."""

    def _install(first: set[int], repaired: set[int] | None = None) -> AsyncMock:
        async def _dispatch(*_args: object, **kwargs: object):
            messages = kwargs.get("messages") or []
            joined = "\n".join(m.get("content") or "" for m in messages)  # type: ignore[union-attr]
            if _CORRECTION_MARKER in joined:
                return _fake_response(_narrative_covering(joined, repaired or first))
            if SYNTH_SYSTEM_INSTRUCTION in joined:
                return _fake_response(_narrative_covering(joined, first))
            return _fake_response("ok")

        mock = AsyncMock(side_effect=_dispatch)
        monkeypatch.setattr(harness_module.litellm, "acompletion", mock)
        monkeypatch.setattr(
            harness_module.litellm,
            "get_model_info",
            lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
        )
        return mock

    return _install


def _state(total_available: int | None = 3, truncated: bool = False) -> dict[str, object]:
    from system_03_search_agent.harness.coordinator_worker import Finding

    query = Query(
        text="Which diseases are associated with NCBIGene:672?",
        session_id="session-tail",
        trace_id="trace-tail",
        user_id=None,
        # UI fix set 9: a Researcher answer now lists every record in code in
        # place of the findings-tail note (`test_write_answer_structure.py`),
        # so the tail's own contract is pinned on a depth that still carries it.
        audience_depth="clinical_brief",
    )
    finding = Finding(
        call_id="cq-tail",
        tool="cypher_query",
        layer="layer_1_graph",
        source="structured_pass_through",
        structured_fields={
            "status": "ok",
            "row_count": len(_ROWS),
            "total_available": total_available,
            "truncated": truncated,
            "rows": _ROWS,
            "error": None,
        },
        extracted_entities=None,
        normalized_ids=None,
        evidence_summary=None,
    )
    return {
        "query": query,
        "harness": harness_module.Harness(trace_id=query.trace_id),
        "seq": 0,
        "start_monotonic": time.monotonic(),
        "findings": [finding],
        "findings_count": 1,
        "next_step_entity_label": "BRCA1",
    }


def _events(result, event_type: str) -> list:
    return [e for e in result["events"] if e.type == event_type]


def _tokens(result) -> list[tuple[str, list[str]]]:
    return [(e.payload["text"], list(e.payload["marker_ids"])) for e in _events(result, "token")]


def _source_ids(result) -> list[str]:
    return [e.payload["source_id"] for e in _events(result, "citation")]


PREPARED = [row["curie"] for row in _ROWS]


@pytest.mark.asyncio
async def test_the_tail_reports_what_the_model_left_out_so_sources_equal_prepared(
    model_reports,
) -> None:
    model_reports(first={1})
    result = await graph_module.write_node(_state())

    citations = sorted(_events(result, "citation"), key=lambda e: e.payload["display_index"])
    assert [c.payload["source_id"] for c in citations] == PREPARED, citations
    assert [c.payload["display_index"] for c in citations] == [1, 2, 3]
    done = _events(result, "done")[0].payload
    assert done["trust_outcome"] == "answer", done
    narrative = "".join(text for text, _ in _tokens(result))
    assert "further disease record" not in narrative, narrative


@pytest.mark.asyncio
async def test_the_note_precedes_the_tail_and_carries_no_marker(model_reports) -> None:
    model_reports(first={1})
    result = await graph_module.write_node(_state())
    tokens = _tokens(result)
    citation_id_by_source = {
        e.payload["source_id"]: e.payload["citation_id"] for e in _events(result, "citation")
    }

    # Product-owner direction 2026-09-14: the findings tail note is gone in
    # every depth; the records the model left out are listed in code under
    # a code-built heading instead, each row carrying its own marker.
    assert not any(text.startswith("Note: the records below") for text, _ in tokens), tokens
    heading_positions = [i for i, (text, _) in enumerate(tokens) if text.startswith("Disease records found")]
    assert len(heading_positions) == 1, tokens
    note_at = heading_positions[0]
    assert tokens[note_at][1] == [], "the heading must carry no marker"

    # Answer quality fix (2026-09-14): the first token is the code-built
    # summary sentence, which cites every answer record; the model's own
    # prose follows it, and its markers are what this arm pins.
    summary_text, summary_markers = tokens[0]
    assert summary_text.startswith("Found 3 disease records"), summary_text
    assert sorted(summary_markers) == sorted(citation_id_by_source.values()), summary_markers
    before = [m for _, markers in tokens[1:note_at] for m in markers]
    after = [m for _, markers in tokens[note_at + 1 :] for m in markers]
    assert before == [citation_id_by_source["MedGen:C1"]], before
    # The listing carries EVERY prepared record, the one the prose already
    # cited included, one row each in prepared order.
    assert after == [
        citation_id_by_source["MedGen:C1"],
        citation_id_by_source["MedGen:C2"],
        citation_id_by_source["MedGen:C3"],
    ], after


@pytest.mark.asyncio
async def test_the_tail_stays_out_when_the_model_reported_everything(model_reports) -> None:
    model_reports(first={1, 2, 3})
    result = await graph_module.write_node(_state())
    assert _source_ids(result) == PREPARED
    assert not any(text.startswith("Note: the records below") for text, _ in _tokens(result))


@pytest.mark.asyncio
async def test_the_tail_never_follows_the_structured_fallback(model_reports) -> None:
    """The model grounds nothing, the fallback lists every finding and floors
    at `ask`; the tail has nothing left to add and must not add its note."""
    model_reports(first=set())
    result = await graph_module.write_node(_state())
    assert _source_ids(result) == PREPARED
    tokens = _tokens(result)
    assert not any(text.startswith("Note: the records below") for text, _ in tokens), tokens
    assert _events(result, "done")[0].payload["trust_outcome"] == "ask"


@pytest.mark.asyncio
async def test_a_tail_the_pass_strips_leaves_the_incompleteness_note(
    model_reports, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the code-built sentence cannot be grounded (here: it carries no
    marker at all, standing in for a value the pass strips), the finding
    stays unreported and the existing disclosure and `ask` floor apply."""
    model_reports(first={1})
    monkeypatch.setattr(
        graph_module, "build_structured_fallback_narrative", lambda findings: "nothing here."
    )
    result = await graph_module.write_node(_state())
    assert _source_ids(result) == ["MedGen:C1"]
    narrative = "".join(text for text, _ in _tokens(result))
    assert "Note: 2 further disease records were found" in narrative, narrative
    assert _events(result, "done")[0].payload["trust_outcome"] == "ask"


@pytest.mark.asyncio
async def test_the_offer_keys_on_records_beyond_the_prepared_list(model_reports) -> None:
    model_reports(first={1})
    complete = _events(await graph_module.write_node(_state()), "done")[0].payload
    assert complete["next_step"] is None and complete["next_step_query"] is None, complete

    model_reports(first={1})
    truncated = _events(
        await graph_module.write_node(_state(total_available=10, truncated=True)), "done"
    )[0].payload
    assert truncated["next_step"] == (
        "Would you like me to go through the 7 further disease records found for this question?"
    ), truncated
    assert truncated["next_step_query"] == "Which other disease records are linked to BRCA1?"

    model_reports(first={1})
    unknown_total = _events(
        await graph_module.write_node(_state(total_available=None, truncated=True)), "done"
    )[0].payload
    assert unknown_total["next_step"] == (
        "Would you like me to go through the further disease records found for this question?"
    ), unknown_total
    assert unknown_total["next_step_query"] is not None


@pytest.mark.asyncio
async def test_a_go_deeper_turn_after_a_full_tail_answer_cites_unseen_records_first(
    model_reports,
) -> None:
    model_reports(first={1})
    state = _state()
    state["deferred_record_ids"] = [_ROWS[0]["source_url"], _ROWS[1]["source_url"]]
    result = await graph_module.write_node(state)
    citations = sorted(_events(result, "citation"), key=lambda e: e.payload["display_index"])
    assert [c.payload["source_id"] for c in citations] == ["MedGen:C3", "MedGen:C1", "MedGen:C2"]


def test_renumber_markers_shifts_every_marker() -> None:
    assert graph_module._renumber_markers("a [1]. b [2] and [1].", 5) == "a [6]. b [7] and [6]."
    assert graph_module._renumber_markers("no markers.", 3) == "no markers."
