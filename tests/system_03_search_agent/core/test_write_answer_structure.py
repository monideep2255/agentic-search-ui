"""UI fix set 9: the typed token stream `write_node` emits.

Drives the real `write_node` with the real grounding pass; only the Synth
model call is faked, returning a reply built from the finding lines it was
shown, the same fixture shape `test_write_findings_tail.py` uses.

Populate-checks, each shown red by patching the control out inside the test:
- An unsupported heading is withheld: patching `heading_is_supported` to
  accept everything makes "Treatment options" appear.
- Notes are typed `note`: asserted per token, and the medical-advice note is
  asserted present in one mode and absent in the other, so neither direction
  can pass vacuously.
- The cited source set is the prepared set in both modes: compared across a
  Plain language and a Researcher run of the same reply.
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

_VARIANT_ROWS = [
    {
        "node_or_edge_type": "SequenceVariant",
        "curie": f"ClinVar:{index}",
        "fields": {"name": f"variant number {index}", "clinical_significance": "Pathogenic"},
        "source_url": f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{index}",
        "graph_snapshot_version": "v1",
    }
    for index in range(1, 3)
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


def _install(monkeypatch: pytest.MonkeyPatch, reply) -> None:
    """`reply(lines)` receives `{ref_index: body}` and returns the reply text."""

    async def _dispatch(*_args: object, **kwargs: object):
        messages = kwargs.get("messages") or []
        joined = "\n".join(m.get("content") or "" for m in messages)  # type: ignore[union-attr]
        if SYNTH_SYSTEM_INSTRUCTION in joined:
            lines = {int(i): body.strip() for i, body in _FINDING_LINE.findall(joined)}
            return _fake_response(reply(lines))
        return _fake_response("ok")

    monkeypatch.setattr(harness_module.litellm, "acompletion", AsyncMock(side_effect=_dispatch))
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )


def _state(depth: str, rows=None) -> dict[str, object]:
    from system_03_search_agent.harness.coordinator_worker import Finding

    rows = rows if rows is not None else _ROWS
    query = Query(
        text="Which diseases are associated with NCBIGene:672?",
        session_id="session-structure",
        trace_id="trace-structure",
        user_id=None,
        audience_depth=depth,  # type: ignore[arg-type]
    )
    finding = Finding(
        call_id="cq-structure",
        tool="cypher_query",
        layer="layer_1_graph",
        source="structured_pass_through",
        structured_fields={
            "status": "ok", "row_count": len(rows), "total_available": len(rows),
            "truncated": False, "rows": rows, "error": None,
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


def _relates(line: str) -> str:
    """A prose sentence that relates the record to the question's subject.

    Answer quality fix (2026-09-14): a Researcher sentence that only restates
    one record's rendered body is dropped, because the code-built list under
    the prose already carries it. The reply here therefore adds the question's
    own licensed words ("NCBIGene:672", "associated"), which is what a real
    answer sentence does and what keeps it in the prose.
    """
    value = line.split("name: ", 1)[1] if "name: " in line else line
    return f"NCBIGene:672 is associated with {value}"


def _structured_reply(lines: dict[int, str]) -> str:
    return (
        f"{_relates(lines[1])} [1].\n\n"
        "## Disease associations\n"
        f"{_relates(lines[2])} [2].\n\n"
        "## Treatment options\n"
        f"{_relates(lines[1])} [1]."
    )


def _tokens(result) -> list[dict]:
    return [e.payload for e in result["events"] if e.type == "token"]


def _sources(result) -> list[str]:
    return sorted(e.payload["source_id"] for e in result["events"] if e.type == "citation")


@pytest.mark.asyncio
async def test_researcher_carries_supported_headings_paragraphs_and_a_listing(monkeypatch) -> None:
    _install(monkeypatch, _structured_reply)
    tokens = _tokens(await graph_module.write_node(_state("researcher")))
    kinds = [t["kind"] for t in tokens]

    headings = [t["text"].strip() for t in tokens if t["kind"] == "heading"]
    assert headings == ["Disease associations", "Disease records found"], headings
    assert "paragraph_break" in kinds
    list_items = [t for t in tokens if t["kind"] == "list_item"]
    assert [t["cells"] for t in list_items] == [
        ["disease name number 1"], ["disease name number 2"], ["disease name number 3"]
    ]
    for token in tokens:
        if token["kind"] in ("claim", "list_item", "table_row"):
            assert token["marker_ids"], token
        else:
            assert token["marker_ids"] == [], token
    assert not any(t["kind"] == "note" and "medical advice" in t["text"] for t in tokens)
    # Answer quality fix (2026-09-14): the answer opens on the code-built
    # summary, then the model's prose. Bold terms come from the run's own
    # record names on both.
    claims = [t for t in tokens if t["kind"] == "claim"]
    assert claims[0]["text"].startswith("Found 3 disease records for BRCA1: "), claims[0]
    assert claims[0]["emphasis"] and "disease name number 1" in claims[0]["emphasis"], claims[0]
    assert claims[1]["emphasis"] == ["disease name number 1"], claims[1]


@pytest.mark.asyncio
async def test_an_unsupported_heading_appears_without_the_check(monkeypatch) -> None:
    _install(monkeypatch, _structured_reply)
    monkeypatch.setattr(graph_module, "heading_is_supported", lambda *_a, **_k: True)
    tokens = _tokens(await graph_module.write_node(_state("researcher")))
    headings = [t["text"].strip() for t in tokens if t["kind"] == "heading"]
    assert "Treatment options" in headings, headings


@pytest.mark.asyncio
async def test_plain_language_lists_its_records_in_code_and_ends_on_the_note(monkeypatch) -> None:
    """Product-owner direction 2026-09-14: the structure is the same in every
    mode. Plain language shows no MODEL heading (its prose stays short and
    unheaded), but the records are grouped in code under a code-built
    heading as list or table rows, never the run-on findings tail, and the
    answer still ends on the medical-advice note."""
    _install(monkeypatch, lambda lines: f"{lines[1]} [1].\n\n## Disease associations\n{lines[2]} [2].")
    tokens = _tokens(await graph_module.write_node(_state("plain_language")))
    headings = [t["text"].strip() for t in tokens if t["kind"] == "heading"]
    assert "Disease associations" not in headings, headings
    assert "Disease records found" in headings, headings
    assert any(t["kind"] == "list_item" for t in tokens), {t["kind"] for t in tokens}
    assert not any(t["text"].startswith("Note: the records below") for t in tokens)
    assert tokens[-1] == {
        "text": "This is a research summary, not medical advice.",
        "marker_ids": [], "kind": "note", "cells": None, "emphasis": None,
    }


@pytest.mark.asyncio
async def test_plain_language_lead_summary_still_carries_emphasis(monkeypatch) -> None:
    """UI fix 11.27 over-corrected: gating `key_terms` to Researcher left
    every Plain language claim's `emphasis` empty, so `mainPointFor` on the
    frontend always fell back to null and nothing but the title ever bolded
    ("now nothing is bold", product owner, live test after `aedf53d`). The
    lead (code-built) summary sentence must carry a non-empty `emphasis` in
    Plain language too, the one arm that would have caught this."""
    _install(monkeypatch, _structured_reply)
    tokens = _tokens(await graph_module.write_node(_state("plain_language")))
    claims = [t for t in tokens if t["kind"] == "claim"]
    assert claims[0]["text"].startswith("Found 3 disease records for BRCA1: "), claims[0]
    assert claims[0]["emphasis"] and "disease name number 1" in claims[0]["emphasis"], claims[0]


@pytest.mark.asyncio
async def test_the_source_set_is_the_same_in_both_modes(monkeypatch) -> None:
    _install(monkeypatch, _structured_reply)
    plain = await graph_module.write_node(_state("plain_language"))
    researcher = await graph_module.write_node(_state("researcher"))
    assert _sources(plain) == _sources(researcher) == ["MedGen:C1", "MedGen:C2", "MedGen:C3"]


@pytest.mark.asyncio
async def test_a_listing_marker_reuses_the_number_the_prose_gave_it(monkeypatch) -> None:
    _install(monkeypatch, lambda lines: f"{lines[2]} [2].")
    result = await graph_module.write_node(_state("researcher"))
    citations = {e.payload["citation_id"]: e.payload["display_index"] for e in result["events"] if e.type == "citation"}
    for token in _tokens(result):
        numbers = [int(n) for n in re.findall(r"\[(\d+)\]", token["text"])]
        assert [citations[m] for m in token["marker_ids"]] == numbers, token


# Variant-to-disease detail (2026-09-14): what the fold template returns for
# one gene, as `cypher_query` shapes it. Each variant row carries the CURIEs
# of the Disease records its ClinVar entry asserts (`clinvar_condition_ids`),
# and the Disease records follow as rows of their own, with the graph's
# vocabulary-token `name` that the live MedGen resolution replaces.
_FOLDED_VARIANT_ROWS = [
    {
        "node_or_edge_type": "SequenceVariant",
        "curie": "ClinVar:1",
        "fields": {
            "name": "variant number 1",
            "clinvar_condition_ids": ["MedGen:C0342276", "MedGen:C3661900"],
        },
        "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/1",
        "graph_snapshot_version": "v1",
    },
    {
        "node_or_edge_type": "Disease",
        "curie": "MedGen:C0342276",
        "fields": {"name": "OMIM included"},
        "source_url": "https://www.ncbi.nlm.nih.gov/medgen/C0342276",
        "graph_snapshot_version": "v1",
    },
    {
        "node_or_edge_type": "Disease",
        "curie": "MedGen:C3661900",
        "fields": {"name": "OMIM allelic variant"},
        "source_url": "https://www.ncbi.nlm.nih.gov/medgen/C3661900",
        "graph_snapshot_version": "v1",
    },
    {
        "node_or_edge_type": "SequenceVariant",
        "curie": "ClinVar:2",
        "fields": {"name": "variant number 2", "clinvar_condition_ids": ["MedGen:C3661900"]},
        "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/2",
        "graph_snapshot_version": "v1",
    },
]

_MEDGEN_TITLES = {
    "MedGen:C0342276": "Maturity-onset diabetes of the young",
    "MedGen:C3661900": "not provided",
}


async def _fake_resolve_concept_ids(concept_ids):
    return {cid: _MEDGEN_TITLES.get(cid) for cid in concept_ids}


@pytest.mark.asyncio
async def test_variant_records_become_a_variant_to_disease_table(monkeypatch) -> None:
    """The mapping table, the disease list before it, the placeholder rule
    and the summary clause, from one folded graph result (2026-09-14).

    Populate-checked: the fixture's second variant links ONLY to the
    placeholder "not provided", so its cell is empty and the disclosure
    counts two excluded links (one per variant). Mutation-proven by hand
    before this test was kept: removing `_apply_fold`'s effect (a fixture
    with no `clinvar_condition_ids`) turns the table into a list and the
    header assertion red; dropping `drop_placeholder_condition_findings`
    puts "not provided" into the disease list and the placeholder
    assertion red; dropping the fold clause from `answer_summary_sentence`
    turns the "linked to 1 disease" assertion red.
    """
    monkeypatch.setattr(graph_module, "resolve_concept_ids", _fake_resolve_concept_ids)
    _install(monkeypatch, lambda lines: f"{lines[1]} [1].")
    tokens = _tokens(await graph_module.write_node(_state("researcher", rows=_FOLDED_VARIANT_ROWS)))
    header = [t for t in tokens if t["kind"] == "table_header"]
    assert header and header[0]["cells"] == ["Variant", "Associated disease(s)"]
    rows = [t["cells"] for t in tokens if t["kind"] == "table_row"]
    assert rows == [
        ["variant number 1", "Maturity-onset diabetes of the young"],
        ["variant number 2", ""],
    ]
    # Every row cites its own record; the first row also cites the disease
    # its cell names, and no cell carries a raw code.
    table_rows = [t for t in tokens if t["kind"] == "table_row"]
    assert len(table_rows[0]["marker_ids"]) == 2 and len(table_rows[1]["marker_ids"]) == 1
    assert not any("MedGen:" in cell for row in rows for cell in row)
    headings = [t["text"].strip() for t in tokens if t["kind"] == "heading"]
    assert "Variant-to-disease mapping" in headings
    assert headings.index("Disease records found") < headings.index("Variant-to-disease mapping")
    list_items = [t["cells"][0] for t in tokens if t["kind"] == "list_item"]
    assert list_items == ["Maturity-onset diabetes of the young"], list_items
    assert "not provided" not in " ".join(list_items)
    notes = [t["text"] for t in tokens if t["kind"] == "note"]
    assert any(n.startswith("2 variant links to ClinVar placeholder conditions") for n in notes), notes
    first = next(t["text"] for t in tokens if t["kind"] == "claim")
    assert first.startswith("Found 2 sequence variant records for BRCA1"), first
    assert "linked to 1 disease: Maturity-onset diabetes of the young [" in first, first


@pytest.mark.asyncio
async def test_the_done_event_carries_one_trust_line(monkeypatch) -> None:
    _install(monkeypatch, _structured_reply)
    result = await graph_module.write_node(_state("researcher"))
    done = [e.payload for e in result["events"] if e.type == "done"]
    assert done and done[0]["trust_line"].startswith("Based on 1 source"), done
    # Not on the trust signal: the MCP surface projects that model whole under
    # a pinned key allowlist (`adapters/mcp/test_phase_4_1_premise.py`).
    answer = [
        e.payload for e in result["events"]
        if e.type == "trust_signal" and e.payload.get("scope") == "answer"
    ]
    assert answer and "summary" not in answer[0], answer
    claim_signals = [
        e for e in result["events"] if e.type == "trust_signal" and e.payload.get("scope") == "claim"
    ]
    assert claim_signals, "per-claim signals must stay on the wire"


# A real ClinVar row shape measured on the live GCK question (set 9's
# `record_label` docstring): the variant's name is an intronic HGVS
# expression, which `_is_vocabulary_token_artifact` flags, as it flags the
# id and the source, so `_pick_representative_field` falls to the URL. The
# list cell must still read the variant's name, never the URL.
_INTRONIC_VARIANT_ROWS = [
    {
        "node_or_edge_type": "SequenceVariant",
        "curie": "ClinVar:1179956",
        "fields": {
            "name": "NM_000162.5(GCK):c.363+318G>A",
            "id": "ClinVar:1179956",
            "source": "ClinVar",
            "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/1179956",
        },
        "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/1179956",
        "graph_snapshot_version": "v1",
    }
]


@pytest.mark.asyncio
async def test_a_listing_cell_reads_the_variant_name_when_the_pick_was_the_url(monkeypatch) -> None:
    field_name, _, _ = graph_module._pick_representative_field(_INTRONIC_VARIANT_ROWS[0]["fields"])
    assert field_name == "source_url", (
        f"populate-check: the upstream pick must be the URL for this row, got {field_name!r}"
    )
    _install(monkeypatch, lambda lines: f"{lines[1]} [1].")
    tokens = _tokens(await graph_module.write_node(_state("researcher", rows=_INTRONIC_VARIANT_ROWS)))
    cells = [t["cells"] for t in tokens if t["kind"] in ("list_item", "table_row") and t["cells"]]
    assert cells, "populate-check: no list or table row was emitted"
    for cell in cells:
        assert cell[0] == "NM_000162.5(GCK):c.363+318G>A", cell
        assert not cell[0].startswith("https://"), cell


@pytest.mark.asyncio
async def test_the_structured_fallback_lists_records_in_every_depth(monkeypatch) -> None:
    """Product-owner direction 2026-09-14. When the model's prose grounds
    nothing, the records themselves are the answer, and they render as a
    grouped listing in Plain language exactly as in Researcher, never as
    run-on "Disease name: ..." claims. Measured live: 3 of 5 Plain language
    runs of "What genes are associated with MODY?" took this branch.
    Mutation that turns this red: render `fallback_sentences` as plain
    `sentence_token`s for non-Researcher depths again."""
    _install(monkeypatch, lambda lines: "Nothing here matches any record at all.")
    tokens = _tokens(await graph_module.write_node(_state("plain_language")))
    kinds = [t["kind"] for t in tokens]
    assert "list_item" in kinds, kinds
    assert "Disease records found" in [t["text"].strip() for t in tokens if t["kind"] == "heading"]
    assert not any(
        t["kind"] == "claim" and t["text"].startswith("Disease name") for t in tokens
    ), [t["text"] for t in tokens if t["kind"] == "claim"]
