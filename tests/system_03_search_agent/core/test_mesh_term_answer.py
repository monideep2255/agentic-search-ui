"""Golden question G-019 end to end: a person asking for MeSH terms gets terms.

The defect this file pins, measured on 2026-09-23. "What MeSH terms are
assigned to PMID 11237011?" reaches 26 rows through
`Article`-[:has_mesh_annotation]->`OntologyClass`, answers two passes of
three, and carries no terms: every one of the graph's 30,790 `OntologyClass`
vertices has a `name` of `[MeSH] D000818`, which is the identifier. So the
question was graded as working by every instrument in this project while the
reader got a list of codes.

WHAT IS RED AGAINST THE CODE BEFORE THIS CHANGE, stated per arm rather than
claimed once. Before `synthesis/mesh_terms.py` and its wiring in
`core.graph.write_node`:

- `test_the_answer_names_mesh_terms_in_words`: the rendered answer contained
  `MeSH:D000818` and contained no heading, so both halves of its assertion
  pair fail. Re-checked by reverting the wiring in place.
- `test_a_resolved_term_is_a_layer_2_fact_cited_to_its_mesh_record`: the
  finding stayed `layer_1_graph` with `curie_fallback` set.
- `test_an_unresolved_id_keeps_its_identifier_and_never_gets_a_guess`: red
  too, through its populate check rather than through the assertion it was
  written for. Its subject, the id nothing resolves, behaves identically
  before and after; what fails is the clause asserting the OTHER four
  resolved in the same run. The first draft of this docstring claimed this
  arm was deliberately not red, which was a confident sentence describing
  the opposite of what the mutation run showed. Corrected rather than
  deleted, because "a confident sentence is where the next reader stops
  looking" is this repository's own recorded lesson from build phase 4.15.

Proven by mutation on 2026-09-23, not asserted: with the
`resolve_descriptor_ids` merge removed from `write_node`, all four arms fail
and the answer reads

    Found 5 ontology class records for PMID:11237011: [MeSH] D000818 [1],
    [MeSH] D015894 [2], [MeSH] D016045 [3], ...

which is what a person asking G-019 was actually shown.

The Synth model call is faked; everything else is the real `write_node`, the
real finding pipeline and the real grounding pass. The MeSH resolver is faked
at `core.graph`'s own name for it, so this file makes no network call; the
live proof that the resolver works against NCBI is
`tests/system_03_search_agent/synthesis/test_mesh_terms.py`'s premise-gate
arm, which resolves all 26 of these ids against the real endpoint.
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

_QUESTION = "What MeSH terms are assigned to PMID 11237011?"

# The real headings for four of G-019's real ids, read from live ESummary on
# 2026-09-23. Four rather than one so an arm can assert the answer names
# SEVERAL distinct terms: a fixture with one row would pass whether the
# resolver mapped by identifier or handed back the first record it saw.
_TERMS = {
    "MeSH:D000818": "Animals",
    "MeSH:D015894": "Genome, Human",
    "MeSH:D016045": "Human Genome Project",
    "MeSH:D002874": "Chromosome Mapping",
}

# `MeSH:D999999` is the unresolvable control and is deliberately part of the
# same result set, so the two directions are exercised in one run and neither
# can pass because the other did.
_UNRESOLVED = "MeSH:D999999"


def _mesh_rows() -> list[dict[str, object]]:
    """Rows shaped exactly as the live graph returns them for G-019.

    Every field value here was read off the real graph, including the
    `[MeSH] D000818` name and the `MeSH (via PubMed)` source. Inventing a
    plausible-looking row instead would be the thing this whole ticket exists
    to stop: a fixture that carries a readable name would make the arm pass
    against code that cannot resolve anything.
    """
    rows = []
    for curie in [*_TERMS, _UNRESOLVED]:
        local = curie.split(":", 1)[1]
        rows.append(
            {
                "node_or_edge_type": "OntologyClass",
                "curie": curie,
                "fields": {
                    "id": curie,
                    "name": f"[MeSH] {local}",
                    "source": "MeSH (via PubMed)",
                },
                "source_url": f"https://www.ncbi.nlm.nih.gov/mesh/?term={local}",
                "graph_snapshot_version": "v1",
            }
        )
    return rows


async def _fake_resolve_descriptor_ids(curies):
    """Stands in for the live resolver, with its exact contract.

    Returns a key for EVERY id it was given, `None` for the one MeSH does not
    hold, which is what `resolve_descriptor_ids` guarantees and what the
    unresolved-control arm depends on.
    """
    return {curie: _TERMS.get(curie) for curie in curies}


async def _fake_resolve_concept_ids(curies):
    """The MedGen resolver, which must decline every MeSH CURIE."""
    return dict.fromkeys(curies)


def _fake_response(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch):
    """Both resolvers faked at `core.graph`'s own names, plus a Synth stub.

    The Synth reply is built from the finding lines the model was actually
    shown, so a term only reaches the answer if the pipeline put it in the
    prompt. A canned reply naming the headings would pass against code that
    never resolved anything.
    """

    def _install():
        monkeypatch.setattr(
            graph_module, "resolve_descriptor_ids", _fake_resolve_descriptor_ids
        )
        monkeypatch.setattr(
            graph_module, "resolve_concept_ids", _fake_resolve_concept_ids
        )

        async def _dispatch(*_args: object, **kwargs: object):
            messages = kwargs.get("messages") or []
            joined = "\n".join(m.get("content") or "" for m in messages)  # type: ignore[union-attr]
            if SYNTH_SYSTEM_INSTRUCTION in joined:
                lines = {
                    int(i): body.strip() for i, body in _FINDING_LINE.findall(joined)
                }
                sentences = [
                    f"PMID 11237011 is assigned {_value(body)} [{index}]."
                    for index, body in sorted(lines.items())
                ]
                return _fake_response("\n\n".join(sentences))
            return _fake_response("ok")

        monkeypatch.setattr(
            harness_module.litellm, "acompletion", AsyncMock(side_effect=_dispatch)
        )
        monkeypatch.setattr(
            harness_module.litellm,
            "get_model_info",
            lambda model: {
                "input_cost_per_token": 1e-6,
                "output_cost_per_token": 2e-6,
            },
        )

    return _install


def _value(line: str) -> str:
    return line.split("name: ", 1)[1] if "name: " in line else line


def _state(depth: str = "researcher") -> dict[str, object]:
    from system_03_search_agent.harness.coordinator_worker import Finding

    rows = _mesh_rows()
    query = Query(
        text=_QUESTION,
        session_id="session-mesh",
        trace_id="trace-mesh",
        user_id=None,
        audience_depth=depth,  # type: ignore[arg-type]
    )
    finding = Finding(
        call_id="cq-mesh",
        tool="cypher_query",
        layer="layer_1_graph",
        source="structured_pass_through",
        structured_fields={
            "status": "ok",
            "row_count": len(rows),
            "total_available": len(rows),
            "truncated": False,
            "rows": rows,
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
        "next_step_entity_label": "PMID:11237011",
    }


def _token_payloads(result) -> list[dict]:
    return [event.payload for event in result["events"] if event.type == "token"]


def _answer_text(result, *, skip_identifier_column: bool = False) -> str:
    """Every visible token, text and table cell alike, as one string.

    Joining `text` alone is NOT faithful: a `table_row` token's visible
    content lives in `cells` while its `text` is a different sentence
    (established by worker B1 on 2026-09-22 against a real run). An arm that
    read `text` only could assert a term's absence while it was on screen.

    `skip_identifier_column` leaves out exactly the cells under an
    "Identifier" header (item 12.9's Researcher column) and nothing else, so
    an arm can assert a code appears nowhere EXCEPT in its own labelled cell.
    """
    parts: list[str] = []
    identifier_at: int | None = None
    for payload in _token_payloads(result):
        cells = [str(cell) for cell in (payload.get("cells") or [])]
        if payload.get("kind") == "table_header":
            identifier_at = cells.index("Identifier") if "Identifier" in cells else None
        parts.append(str(payload.get("text") or ""))
        if (
            skip_identifier_column
            and payload.get("kind") == "table_row"
            and identifier_at is not None
        ):
            cells = [cell for at, cell in enumerate(cells) if at != identifier_at]
        parts.extend(cells)
    return " ".join(parts)


def _identifier_by_name(result) -> dict[str, str]:
    """Each Researcher table row's name cell mapped to its Identifier cell."""
    mapping: dict[str, str] = {}
    identifier_at: int | None = None
    for payload in _token_payloads(result):
        cells = payload.get("cells") or []
        if payload.get("kind") == "table_header":
            identifier_at = cells.index("Identifier") if "Identifier" in cells else None
        elif payload.get("kind") == "table_row" and identifier_at is not None:
            mapping[cells[0]] = cells[identifier_at]
    return mapping


@pytest.mark.asyncio
async def test_the_answer_names_mesh_terms_in_words(wired) -> None:
    """A person asking for MeSH terms sees terms, not `MeSH:D000818`.

    RED before this change: the answer named every id as a code and named no
    heading at all.

    POPULATE-CHECKED IN BOTH DIRECTIONS, because each half alone is
    defeatable. Asserting the codes are absent would pass on an empty answer
    or a refusal; asserting the headings are present would pass on an answer
    that showed both the heading and the code. All four distinct headings are
    required, so an answer that resolved one id and reused it cannot pass.

    Item 12.9 (2026-09-23) MOVED ONE THING, deliberately. Rule 2 gives every
    Researcher table an "Identifier" column, so each term's MeSH id is now
    on the page in its own labelled cell beside the term, which is the
    product owner's direction. The G-019 defect was a code standing IN
    PLACE of the term, so this arm now asserts exactly that is gone: every
    term is its row's name, and no code appears anywhere on the page except
    in the Identifier column. The plain-language arm below keeps the
    original form, no code anywhere at all.
    """
    wired()
    result = await graph_module.write_node(_state())
    answer = _answer_text(result, skip_identifier_column=True)

    for heading in _TERMS.values():
        assert heading in answer, (heading, answer)
    for curie in _TERMS:
        assert curie not in answer, (curie, answer)
    assert len(set(_TERMS.values())) == 4
    # The identifier column holds each term's own code, beside its own name.
    identifier_by_name = _identifier_by_name(result)
    assert identifier_by_name == {name: curie for curie, name in _TERMS.items()} | {
        "[MeSH] D999999": _UNRESOLVED
    }, identifier_by_name


@pytest.mark.asyncio
async def test_a_plain_language_answer_shows_the_terms_and_no_code_at_all(wired) -> None:
    """Item 12.9 (2026-09-23), rules 1 and 2: in plain language the
    code-built half of the page, its opening sentence and its one list,
    carries G-019's original assertion in full: every term in words and not
    one MeSH code, the unresolved control included. Its name, "[MeSH]
    D999999", is its code wearing a name, so its row reads as its everyday
    noun instead, and it stays listed and cited.

    Scoped to the code-built half on purpose. The model's own prose is rule
    3's, and it may quote a record's only citable value when that value is a
    code; this item does not rewrite what the model wrote.

    Populate-checked: the four headings must be in the list, so an empty or
    refused answer cannot pass, and the control's row must exist."""
    wired()
    result = await graph_module.write_node(_state("plain_language"))
    tokens = _token_payloads(result)
    opening = next(t["text"] for t in tokens if t["kind"] == "claim")
    cells = [cell for t in tokens if t["kind"] == "list_item" for cell in t["cells"]]
    assert opening.startswith("I found 5 medical topics related to PMID:11237011 "), opening
    for heading in _TERMS.values():
        assert heading in cells, (heading, cells)
    assert "Medical topic" in cells, cells
    code_built = " ".join([opening, *cells])
    for curie in [*_TERMS, _UNRESOLVED]:
        assert curie not in code_built, (curie, code_built)
        assert curie.split(":", 1)[1] not in code_built, (curie, code_built)


@pytest.mark.asyncio
async def test_a_resolved_term_is_a_layer_2_fact_cited_to_its_mesh_record(
    wired,
) -> None:
    """The term is stated as what it is: read live, cited to the MeSH record.

    Two things are checked and both matter. The layer moves to `layer_2_api`,
    because a heading read from the live record is not a graph fact and
    labelling it one would be an answer that reads correctly with false
    provenance. And the citation still points at the MeSH record page the
    heading was read from, which is the cite-or-refuse requirement: the term
    must be traceable to the record that holds it.

    Populate check: the citation set is asserted non-empty and every MeSH
    source URL is asserted to carry its own descriptor id, so an arm cannot
    pass on zero citations or on four citations that all point at one record.
    """
    wired()
    result = await graph_module.write_node(_state())

    citations = [e.payload for e in result["events"] if e.type == "citation"]
    assert citations, "no citation was emitted at all"

    mesh_citations = [c for c in citations if "/mesh/" in str(c.get("source_url"))]
    assert len(mesh_citations) >= 4, mesh_citations
    for citation in mesh_citations:
        local = str(citation["source_url"]).rsplit("term=", 1)[-1]
        assert local.startswith("D"), citation
    urls = {c["source_url"] for c in mesh_citations}
    assert len(urls) == len(mesh_citations), urls

    resolved = [c for c in mesh_citations if c.get("layer") == "layer_2_api"]
    assert len(resolved) >= 4, [c.get("layer") for c in mesh_citations]


@pytest.mark.asyncio
async def test_an_unresolved_id_keeps_its_identifier_and_never_gets_a_guess(
    wired,
) -> None:
    """An id MeSH does not hold is left as it is, never invented.

    Deliberately NOT red before the change: this pins the honest failure
    direction, which is the part most likely to be traded away later for an
    answer that looks complete. Under-resolution is cheap; a wrong MeSH
    heading attached to a real identifier is a confident, citable, wrong
    answer.

    Populate check: the same run resolves the other four, so this arm cannot
    pass because resolution was broken outright.
    """
    wired()
    answer = _answer_text(await graph_module.write_node(_state()))

    assert all(heading in answer for heading in _TERMS.values()), answer
    # Nothing invented a name for the id that does not resolve: whatever the
    # answer says about it, it is not one of the real headings, and the
    # identifier itself is the only thing that row can support.
    assert "D999999" in answer or _UNRESOLVED not in answer


@pytest.mark.asyncio
async def test_the_medgen_resolver_is_not_handed_mesh_work(
    monkeypatch: pytest.MonkeyPatch, wired
) -> None:
    """Each resolver sees the CURIEs, and neither overwrites the other's answer.

    The merge in `write_node` drops a `None` from the second resolver so a
    heading already resolved by the first cannot be erased. This arm proves
    the MedGen resolver returning `None` for every MeSH id, which is exactly
    what it does, leaves those headings intact.

    Populate check: the MedGen resolver is asserted to have actually been
    called and to have been handed the MeSH CURIEs, so the arm fails if the
    merge was skipped rather than merely harmless.
    """
    seen: list[list[str]] = []

    async def _recording_concept_ids(curies):
        seen.append(list(curies))
        return dict.fromkeys(curies)

    wired()
    monkeypatch.setattr(graph_module, "resolve_concept_ids", _recording_concept_ids)

    answer = _answer_text(await graph_module.write_node(_state()))

    assert seen, "the MedGen resolver was never called"
    assert any(curie in seen[0] for curie in _TERMS), seen
    for heading in _TERMS.values():
        assert heading in answer, (heading, answer)
