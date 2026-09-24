"""Answer quality fix (2026-09-14): the write-node arms.

Drives the real `write_node` with the real grounding pass over a THREE-CALL
state in set 8's handoff order (a trials call, a literature call, then the
graph call), which is the order the live BRCA1 question's prompt had. Only
the Synth model call is faked, and the fake records the exact prompt it was
shown, so an arm can assert on what the writer was given as well as on what
was emitted.

Populate-checks and mutation arms:
- The prompt numbers the graph findings first and carries the ANSWER /
  CONTEXT line. Mutation: `_answer_call_ids` patched to return nothing
  restores the handoff order and drops the line.
- The first claim token names a disease in both modes, and trials come
  after. Same mutation, same arm.
- A Researcher reply made only of one-record restatements produces no prose
  claim, a cited summary, and the list. Mutation: `drop_record_restatements`
  patched to the identity puts the restatements back.
- No URL reaches the prompt for the intronic-variant row. Mutation: the URL
  guard patched out puts it back (`synthesis/test_answer_quality.py`).
- The cited source set is identical in both modes and equal to the prepared
  set, with the summary in place.

Coverage statement (goal-contracts): a plain-language and a researcher run
of the same three-call state; a trials question; a restatement-only reply
and a relating reply. Not exercised here: the live model, the live graph,
the completeness repair (its own file), the structured fallback's ordering
(covered by the live-run table in the report).
"""

from __future__ import annotations

import re
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.contracts.events import ToolCall
from system_03_search_agent.contracts.query import Query
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.harness.coordinator_worker import Finding
from system_03_search_agent.synthesis import answer_layout
from system_03_search_agent.synthesis.findings import SYNTH_SYSTEM_INSTRUCTION
from system_03_search_agent.tools.cypher_query import CypherQueryInput

_FINDING_LINE = re.compile(r"^\[(\d+)\]\s+(.+)$", re.MULTILINE)

_DISEASE_ROWS = [
    {
        "node_or_edge_type": "Disease",
        "curie": f"MedGen:C{index}",
        "fields": {"name": f"disease name number {index}"},
        "source_url": f"https://www.ncbi.nlm.nih.gov/medgen/{index}",
        "graph_snapshot_version": "v1",
        "vocabulary_artifact_fields": [],
    }
    for index in range(1, 4)
]

_TRIAL_ROWS = [
    graph_module._pseudo_row(
        "Clinical trial",
        {"name": f"trial title number {index}", "nct_id": f"NCT0000000{index}"},
        f"https://clinicaltrials.gov/study/NCT0000000{index}",
    )
    for index in range(1, 3)
]

_LITERATURE_ROWS = [
    graph_module._pseudo_row(
        "Literature entity",
        {"name": "BRCA1", "biotype": "gene", "pubtator_id": "@GENE_BRCA1"},
        "https://www.ncbi.nlm.nih.gov/research/pubtator3/?text=@GENE_BRCA1",
    )
]


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


def _install(monkeypatch: pytest.MonkeyPatch, reply) -> list[str]:
    """`reply(lines)` receives `{ref_index: body}`; returns the prompts seen."""
    prompts: list[str] = []

    async def _dispatch(*_args: object, **kwargs: object):
        messages = kwargs.get("messages") or []
        joined = "\n".join(m.get("content") or "" for m in messages)  # type: ignore[union-attr]
        if SYNTH_SYSTEM_INSTRUCTION in joined:
            prompts.append(messages[-1]["content"])  # type: ignore[index]
            lines = {int(i): body.strip() for i, body in _FINDING_LINE.findall(joined)}
            return _fake_response(reply(lines))
        return _fake_response("ok")

    monkeypatch.setattr(harness_module.litellm, "acompletion", AsyncMock(side_effect=_dispatch))
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )
    return prompts


def _finding(call_id: str, tool: str, layer: str, rows: list[dict]) -> Finding:
    return Finding(
        call_id=call_id, tool=tool, layer=layer, source="structured_pass_through",
        structured_fields={
            "status": "ok", "row_count": len(rows), "total_available": len(rows),
            "truncated": False, "rows": rows, "error": None,
        },
        extracted_entities=None, normalized_ids=None, evidence_summary=None,
    )


def _state(depth: str, question: str = "Which diseases are associated with NCBIGene:672?") -> dict:
    query = Query(
        text=question, session_id="session-aq", trace_id="trace-aq", user_id=None,
        audience_depth=depth,  # type: ignore[arg-type]
    )
    planned = [
        graph_module._PlannedToolCall(
            tool_call=ToolCall(tool="cypher_query", call_id="cq-aq", layer="layer_1_graph"),
            cypher_input=CypherQueryInput(
                query_intent="q", query_class="lookup", target_entities=["NCBIGene:672"], row_limit=10,
            ),
        ),
        *graph_module._build_layer_tool_calls(question, "BRCA1", []),
    ]
    trials_id = next(p.tool_call.call_id for p in planned if p.tool_call.tool == "clinicaltrials_search")
    literature_id = next(p.tool_call.call_id for p in planned if p.tool_call.tool == "pubtator_annotate")
    # Set 8's handoff order: Layer 3 first, the graph call last.
    findings = [
        _finding(literature_id, "pubtator_annotate", "layer_3_enrichment", _LITERATURE_ROWS),
        _finding(trials_id, "clinicaltrials_search", "layer_3_enrichment", _TRIAL_ROWS),
        _finding("cq-aq", "cypher_query", "layer_1_graph", _DISEASE_ROWS),
    ]
    return {
        "query": query,
        "harness": harness_module.Harness(trace_id=query.trace_id),
        "seq": 0,
        "start_monotonic": time.monotonic(),
        "findings": findings,
        "findings_count": len(findings),
        "tool_calls": planned,
        "next_step_entity_label": "BRCA1",
    }


def _tokens(result) -> list[dict]:
    return [e.payload for e in result["events"] if e.type == "token"]


def _claims(result) -> list[dict]:
    return [t for t in _tokens(result) if t["kind"] in ("claim", None)]


def _sources(result) -> list[str]:
    return sorted(e.payload["source_id"] for e in result["events"] if e.type == "citation")


def _relating_reply(lines: dict[int, str]) -> str:
    """One relating sentence per finding, in prompt order, as a compliant
    model writes them: the diseases relate to the gene, the rest restate."""
    sentences = []
    for index, body in lines.items():
        value = body.split("name: ", 1)[1] if "name: " in body else body
        if body.startswith("Disease"):
            sentences.append(f"NCBIGene:672 is associated with {value} [{index}].")
        else:
            sentences.append(f"{body} [{index}].")
    return " ".join(sentences)


@pytest.mark.asyncio
@pytest.mark.parametrize("depth", ["plain_language", "researcher"])
async def test_the_prompt_leads_with_the_answer_findings_and_says_so(monkeypatch, depth: str) -> None:
    prompts = _install(monkeypatch, _relating_reply)
    await graph_module.write_node(_state(depth))
    assert prompts, "populate-check: the synth call was not made"
    lines = _FINDING_LINE.findall(prompts[0])
    assert [body[:7] for _, body in lines[:3]] == ["Disease", "Disease", "Disease"], lines
    assert "ANSWER FINDINGS: [1] to [3] " in prompts[0], prompts[0]
    assert "CONTEXT FINDINGS: [4] to [6] " in prompts[0], prompts[0]


@pytest.mark.asyncio
async def test_without_the_answer_ids_the_prompt_returns_to_the_handoff_order(monkeypatch) -> None:
    prompts = _install(monkeypatch, _relating_reply)
    monkeypatch.setattr(graph_module, "_answer_call_ids", lambda *_a, **_k: frozenset())
    await graph_module.write_node(_state("plain_language"))
    first = _FINDING_LINE.findall(prompts[0])[0][1]
    assert first.startswith("Literature entity"), (
        f"the mutation did not restore the handoff order ({first!r}); the order arm could not have caught it"
    )
    assert "ANSWER FINDINGS" not in prompts[0]


#: The opening sentence per depth. Item 12.9 (2026-09-23) REVERSED this arm's
#: old expectation that both depths open identically: rule 1 has Plain
#: language speak to a reader with no technical background, everyday nouns
#: and no titles inline, over the same three records and the same markers.
_OPENING_BY_DEPTH = {
    "plain_language": "I found 3 conditions related to BRCA1 [1][2][3].",
    "researcher": "Found 3 disease records for BRCA1: disease name number 1 [1], ",
}


@pytest.mark.asyncio
@pytest.mark.parametrize("depth", ["plain_language", "researcher"])
async def test_the_first_sentence_names_a_disease_and_trials_follow(monkeypatch, depth: str) -> None:
    """The answer opens on the diseases, cited, with the trials after them.

    Item 12.9 (2026-09-23) REVERSED this arm's old expectation that both
    depths open with the same "Found 3 disease records for BRCA1: <titles>"
    sentence: rule 1 has Plain language open "I found 3 conditions related
    to BRCA1 [1][2][3]." (`_OPENING_BY_DEPTH`). What stays pinned at both
    depths is the property: the same three records and markers, then the
    trials."""
    _install(monkeypatch, _relating_reply)
    result = await graph_module.write_node(_state(depth))
    claims = _claims(result)
    first = claims[0]["text"]
    assert first.startswith(_OPENING_BY_DEPTH[depth]), first
    assert claims[0]["marker_ids"] and len(claims[0]["marker_ids"]) == 3, claims[0]
    # Trials follow the diseases: as prose in Plain language, as list rows in
    # Researcher (where their restatements are dropped for the list).
    shown = [t["text"] + " ".join(t.get("cells") or []) for t in _tokens(result)]
    trial_at = next(i for i, text in enumerate(shown) if "trial title" in text)
    disease_at = next(i for i, text in enumerate(shown) if "disease name" in text)
    assert disease_at < trial_at, shown
    assert _sources(result) == sorted(
        ["MedGen:C1", "MedGen:C2", "MedGen:C3", "NCT00000001", "NCT00000002", "@GENE_BRCA1"]
    ), _sources(result)


@pytest.mark.asyncio
async def test_both_modes_cite_the_prepared_set(monkeypatch) -> None:
    _install(monkeypatch, _relating_reply)
    plain = await graph_module.write_node(_state("plain_language"))
    _install(monkeypatch, _relating_reply)
    researcher = await graph_module.write_node(_state("researcher"))
    assert _sources(plain) == _sources(researcher)
    assert len(_sources(plain)) == 6


def _restating_reply(lines: dict[int, str]) -> str:
    return " ".join(f"{body} [{index}]." for index, body in lines.items())


@pytest.mark.asyncio
async def test_researcher_drops_restatements_the_list_carries_and_keeps_a_cited_summary(monkeypatch) -> None:
    """Item 12.9 (2026-09-23) REVERSED the shape this arm pinned, one-cell
    `list_item` rows: rule 2 makes each Researcher group a table with an
    identifier column, so the rows are read from `table_row` too. The
    property is unchanged: the restatements go, and the list names all six
    records once, in order."""
    _install(monkeypatch, _restating_reply)
    result = await graph_module.write_node(_state("researcher"))
    tokens = _tokens(result)
    prose = [t for t in tokens if t["kind"] == "claim"]
    assert len(prose) == 1, [t["text"] for t in prose]
    assert prose[0]["text"].startswith("Found 3 disease records for BRCA1: "), prose[0]
    assert prose[0]["marker_ids"], "the summary must be cited"
    # Item 12.9 (2026-09-23): Researcher records are table rows now, each
    # group a table with an identifier column (rule 2), so the rows are read
    # from `table_row` as well as `list_item`. The first cell is still the
    # record's name, and the six records and their order are unchanged.
    list_rows = [t["cells"][0] for t in tokens if t["kind"] in ("list_item", "table_row")]
    assert list_rows == [
        "disease name number 1", "disease name number 2", "disease name number 3",
        "BRCA1", "trial title number 1", "trial title number 2",
    ], list_rows
    assert not any(t["kind"] == "note" and "could not be verified" in t["text"] for t in tokens), (
        "restatements are not a grounding failure; the fallback note must not appear"
    )
    done = next(e.payload for e in result["events"] if e.type == "done")
    assert done["trust_outcome"] == "answer", done
    assert len(_sources(result)) == 6


@pytest.mark.asyncio
async def test_without_the_drop_the_restatements_are_rendered_twice(monkeypatch) -> None:
    _install(monkeypatch, _restating_reply)
    monkeypatch.setattr(graph_module, "drop_record_restatements", lambda grounding, _f: (grounding, 0))
    tokens = _tokens(await graph_module.write_node(_state("researcher")))
    prose = [t["text"] for t in tokens if t["kind"] == "claim"]
    assert any("Disease MedGen:C1, name: disease name number 1" in text for text in prose), (
        "the mutation did not put the restatements back; the drop arm could not have caught it"
    )


@pytest.mark.asyncio
async def test_plain_language_drops_restatements_the_list_already_shows(monkeypatch) -> None:
    """Item 12.12 (2026-09-23), REVERSING the arm that stood here.

    It pinned "plain language keeps restatements since it has no list". Both
    halves stopped being true: every depth has listed every record since
    2026-09-14, and a tester's plain-language answers read "One trial is
    named X. Another is named Y" above a list naming the same trials. The
    product owner directed the repetition fixed, so the restatements go at
    this depth too, and the listing still names every record once.
    """
    _install(monkeypatch, _restating_reply)
    tokens = _tokens(await graph_module.write_node(_state("plain_language")))
    prose = [t["text"] for t in tokens if t["kind"] == "claim"]
    listed = [t["text"] for t in tokens if t["kind"] in ("list_item", "table_row")]
    assert any("disease name number 1" in text for text in listed), (
        f"populate-check: the listing must still name the record: {tokens}"
    )
    assert not any("disease name number 1" in text for text in prose[1:]), prose


@pytest.mark.asyncio
async def test_a_trials_question_counts_the_trials_as_answer_findings(monkeypatch) -> None:
    prompts = _install(monkeypatch, _relating_reply)
    question = "Which trials are recruiting for NCBIGene:672?"
    result = await graph_module.write_node(_state("researcher", question=question))
    assert "ANSWER FINDINGS: [1] to [5] " in prompts[0], prompts[0]
    first = _claims(result)[0]["text"]
    # Both lead calls are numbered in handoff order (trials before the graph),
    # so the summary groups the trials first; the property is that BOTH are
    # counted as answer records and named inline.
    assert first.startswith("Found 2 clinical trial records and 3 disease records for BRCA1: "), first
    assert "trial title number 1 [1]" in first and "disease name number 3 [5]" in first, first


_MANY_DISEASE_ROWS = [
    {
        "node_or_edge_type": "Disease",
        "curie": f"MedGen:D{index}",
        "fields": {"name": f"disease name number {index}"},
        "source_url": f"https://www.ncbi.nlm.nih.gov/medgen/D{index}",
        "graph_snapshot_version": "v1",
        "vocabulary_artifact_fields": [],
    }
    for index in range(1, 27)
]


@pytest.mark.asyncio
async def test_the_opening_count_matches_the_list_beneath_it(monkeypatch) -> None:
    """The opening sentence counts what the READER is shown, not the prompt slice.

    Measured on develop 2026-09-23 across five consecutive live runs of golden
    question G-019: the answer opened "Found 20 ontology class records" above a
    list of 26, carrying 26 citations. A count that disagrees with the list
    under it costs the reader their trust in every other number on the page.

    THE CAUSE was one variable serving two consumers whose correct scopes
    differ. `answer_findings` is sliced to `_MAX_FINDINGS_FOR_MODEL_PROMPT`
    because it feeds `build_answer_context_directive`, which the MODEL reads,
    and naming a ref_index the model was never shown would be an instruction
    about content that is not there. That is right, and unchanged. It does not
    transfer to the code-built opening sentence, which cites every record it
    counts, so `write_node` now derives `summary_findings` over the full
    display list for that one caller.

    RED AGAINST THE OLD CODE by construction: with 26 display rows and a prompt
    slice of 20, the pre-fix build opened "Found 20 disease records".

    POPULATE CHECK: the row count here (26) must exceed
    `_MAX_FINDINGS_FOR_MODEL_PROMPT` (20) or the two scopes coincide and this
    arm proves nothing, so it asserts that relationship rather than trusting
    the literal.
    """
    assert len(_MANY_DISEASE_ROWS) > graph_module._MAX_FINDINGS_FOR_MODEL_PROMPT, (
        "this arm only distinguishes the two scopes when the display list is "
        "longer than the prompt slice; with fewer rows it passes vacuously"
    )

    _install(monkeypatch, _relating_reply)
    state = _state("researcher")
    state["findings"] = [
        _finding("cq-aq", "cypher_query", "layer_1_graph", _MANY_DISEASE_ROWS)
    ]
    state["findings_count"] = 1
    result = await graph_module.write_node(state)

    claims = _claims(result)
    assert claims, "expected a cited opening sentence"
    first = claims[0]["text"]
    assert first.startswith("Found "), first

    # What the reader is actually shown, measured from the citation events the
    # answer emits rather than from a token field: the opening sentence cites
    # every record it counts, so the citation list is the list it must agree
    # with. A first attempt read `citation_id` off the token payloads and got
    # zero, which would have made this arm pass vacuously on any count at all.
    shown = len(_sources(result))
    counted = int(first.split("Found ", 1)[1].split(" ", 1)[0])
    assert shown > 0, "no citations were emitted, so there is nothing to agree with"
    assert counted != graph_module._MAX_FINDINGS_FOR_MODEL_PROMPT or shown == counted, (
        f"the opening counted {counted}, which is exactly the prompt slice, "
        f"while the answer shows {shown}. This is the G-019 defect: {first!r}"
    )
    assert counted == shown, (
        f"the opening sentence counted {counted} records while the answer "
        f"shows {shown}. The two must agree: {first!r}"
    )


def test_answer_call_ids_pick_the_graph_call_and_trials_only_when_asked() -> None:
    planned = _state("researcher")["tool_calls"]
    ids = graph_module._answer_call_ids(planned, "Which diseases are associated with NCBIGene:672?")
    assert ids == frozenset({"cq-aq"})
    with_trials = graph_module._answer_call_ids(planned, "What trials are recruiting?")
    trials_id = next(p.tool_call.call_id for p in planned if p.tool_call.tool == "clinicaltrials_search")
    assert with_trials == frozenset({"cq-aq", trials_id})


@pytest.mark.asyncio
async def test_no_url_reaches_the_prompt_for_an_intronic_variant_row(monkeypatch) -> None:
    """Item 12.9 (2026-09-23) moved where this arm finds the variant's name
    cell: a Researcher record is now a `table_row` in a table with an
    identifier column (rule 2), no longer a one-cell `list_item`. The
    property is unchanged: no URL anywhere, and the cell reads the name."""
    row = {
        "node_or_edge_type": "SequenceVariant",
        "curie": "ClinVar:1179956",
        "fields": {
            "name": "NM_000162.5(GCK):c.363+318G>A", "id": "ClinVar:1179956", "source": "ClinVar",
            "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/1179956",
        },
        "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/1179956",
        "graph_snapshot_version": "v1",
        "vocabulary_artifact_fields": ["id", "name", "source"],
    }
    state = _state("researcher", question="Variants in NCBIGene:2645 causing MODY")
    state["findings"][-1] = _finding("cq-aq", "cypher_query", "layer_1_graph", [row])
    prompts = _install(monkeypatch, _restating_reply)
    result = await graph_module.write_node(state)
    assert "http" not in "\n".join(_FINDING_LINE.findall(prompts[0])[0]).lower(), prompts[0]
    texts = [t["text"] for t in _tokens(result)]
    assert not any("source URL" in text or "source_url" in text for text in texts), texts
    # Item 12.9 (2026-09-23): a Researcher record is a table row now (rule
    # 2), so its name cell is read from `table_row` as well as `list_item`.
    cells = [t["cells"][0] for t in _tokens(result) if t["kind"] in ("list_item", "table_row")]
    assert "NM_000162.5(GCK):c.363+318G>A" in cells, cells


def test_summary_and_drop_are_wired_from_answer_layout() -> None:
    assert graph_module.answer_summary_sentence is answer_layout.answer_summary_sentence
    assert graph_module.drop_record_restatements is answer_layout.drop_record_restatements


@pytest.mark.asyncio
async def test_without_the_summary_the_answer_opens_on_the_models_prose(monkeypatch) -> None:
    _install(monkeypatch, _relating_reply)
    monkeypatch.setattr(graph_module, "answer_summary_sentence", lambda *_a, **_k: None)
    first = _claims(await graph_module.write_node(_state("plain_language")))[0]["text"]
    assert not first.startswith("Found "), (
        f"the mutation did not remove the summary ({first!r}); the summary arms could not have caught it"
    )
    assert first.startswith("NCBIGene:672 is associated with disease name number 1 [1]"), first


@pytest.mark.asyncio
async def test_a_two_gene_question_names_both_genes_in_the_summary(monkeypatch) -> None:
    _install(monkeypatch, _relating_reply)
    state = _state("researcher", question="Which diseases are associated with NCBIGene:672 and NCBIGene:675?")
    state["resolved_entities"] = [
        SimpleNamespace(text="BRCA1", curie="NCBIGene:672"),
        SimpleNamespace(text="BRCA2", curie="NCBIGene:675"),
        SimpleNamespace(text="brca1", curie="NCBIGene:672"),
    ]
    first = _claims(await graph_module.write_node(state))[0]["text"]
    assert first.startswith("Found 3 disease records for BRCA1 and BRCA2: "), first


@pytest.mark.asyncio
async def test_graph_and_efetch_gene_records_share_one_listing_heading(monkeypatch) -> None:
    """The graph writes `Gene`, `ncbi_efetch` writes `gene`; the listing keys
    on the noun so a two-gene answer does not show "Gene records found"
    twice (measured 2026-09-14)."""
    state = _state("researcher")
    gene_rows = [
        {
            "node_or_edge_type": "Gene", "curie": "NCBIGene:672",
            "fields": {"name": "BRCA1 DNA repair associated", "symbol": "BRCA1"},
            "source_url": "https://www.ncbi.nlm.nih.gov/gene/672", "graph_snapshot_version": "v1",
            "vocabulary_artifact_fields": [],
        }
    ]
    efetch_rows = [
        {"curie": "", "node_or_edge_type": "gene", "fields": {"symbol": "BRCA2"},
         "source_url": "https://www.ncbi.nlm.nih.gov/gene/675"}
    ]
    state["findings"] = [
        _finding("ef-aq", "ncbi_efetch", "layer_2_api", efetch_rows),
        _finding("cq-aq", "cypher_query", "layer_1_graph", gene_rows),
    ]
    _install(monkeypatch, _restating_reply)
    tokens = _tokens(await graph_module.write_node(state))
    headings = [t["text"].strip() for t in tokens if t["kind"] == "heading"]
    assert headings.count("Gene records found") == 1, headings
