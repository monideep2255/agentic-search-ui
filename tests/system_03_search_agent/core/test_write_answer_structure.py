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

Item 12.9 (2026-09-23, the product owner's six rules), the arms at the end
of this file, each shown red against the code before the change:
- Rules 1 and 2: the two depths open with different sentences over the same
  markers, Plain language lists titles only under one heading, and every
  Researcher row carries its record's own identifier.
- Rule 4: with no model prose at all (the structured fallback) the two
  depths still differ.
- Rule 5, THE FIREWALL: across five fixtures, both depths emit exactly the
  same citation ids, list every cited record as its own row, and carry the
  same grounded sentence behind every row. Populate-checked: the arm first
  asserts the two pages really differ, so it can never pass by comparing a
  page with itself.

Coverage statement (goal-contracts): graph records with model prose, a
folded variant-to-disease table, the structured fallback, live PubMed papers
cited through the real Layer 2 builder, and a mix of graph, trial and paper
records. Not exercised here: the live model, the live graph, and the
`clinical_brief` and `deep_technical` depths, which take the technical form
by the same `is_plain_language` test the plain arms exercise.
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


def _tables(tokens: list[dict]) -> list[tuple[list[str], list[dict]]]:
    """Each table as `(header cells, its table_row tokens)`, in order."""
    tables: list[tuple[list[str], list[dict]]] = []
    for token in tokens:
        if token["kind"] == "table_header":
            tables.append((token["cells"], []))
        elif token["kind"] == "table_row" and tables:
            tables[-1][1].append(token)
    return tables


@pytest.mark.asyncio
async def test_researcher_carries_supported_headings_paragraphs_and_a_listing(monkeypatch) -> None:
    """Item 12.9 (2026-09-23) REVERSED the listing this arm pinned. It read
    the three diseases as one-cell `list_item`s, identical to Plain
    language. The product owner's rule 2 gives Researcher the records
    grouped by type as a table with an identifier column, so they are now
    rows of a "Disease | Identifier" table, each naming its own MedGen
    record. The headings, the paragraphs and the markers are unchanged."""
    _install(monkeypatch, _structured_reply)
    tokens = _tokens(await graph_module.write_node(_state("researcher")))
    kinds = [t["kind"] for t in tokens]

    headings = [t["text"].strip() for t in tokens if t["kind"] == "heading"]
    assert headings == ["Disease associations", "Disease records found"], headings
    assert "paragraph_break" in kinds
    headers = [t["cells"] for t in tokens if t["kind"] == "table_header"]
    assert headers == [["Disease", "Identifier"]], headers
    table_rows = [t for t in tokens if t["kind"] == "table_row"]
    assert [t["cells"] for t in table_rows] == [
        ["disease name number 1", "MedGen:C1"],
        ["disease name number 2", "MedGen:C2"],
        ["disease name number 3", "MedGen:C3"],
    ]
    assert "list_item" not in kinds, kinds
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
    """Product-owner direction 2026-09-14: the records are listed in code in
    every mode, never as the run-on findings tail, and Plain language shows
    no MODEL heading (its prose stays short and unheaded). The answer still
    ends on the medical-advice note.

    Item 12.9 (2026-09-23) REVERSED one half of the 2026-09-14 direction,
    "the structure is the same in every mode", which this arm pinned by
    asserting the Researcher heading "Disease records found" here too. Rule
    2 gives Plain language ONE list under the product owner's own heading,
    "Where this answer comes from", titles only."""
    _install(monkeypatch, lambda lines: f"{lines[1]} [1].\n\n## Disease associations\n{lines[2]} [2].")
    tokens = _tokens(await graph_module.write_node(_state("plain_language")))
    headings = [t["text"].strip() for t in tokens if t["kind"] == "heading"]
    assert "Disease associations" not in headings, headings
    assert headings == ["Where this answer comes from"], headings
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
    Plain language too, the one arm that would have caught this.

    Item 12.9 (2026-09-23) changed the sentence this arm reads, not the
    property. It pinned the Plain language lead as the Researcher's "Found
    3 disease records for BRCA1: <titles>", and rule 1 reversed that: plain
    language names no titles inline, so its main point is the subject it
    names, BRCA1, and that is what must still be emphasised."""
    _install(monkeypatch, _structured_reply)
    tokens = _tokens(await graph_module.write_node(_state("plain_language")))
    claims = [t for t in tokens if t["kind"] == "claim"]
    assert claims[0]["text"].startswith("I found 3 conditions related to BRCA1 "), claims[0]
    assert claims[0]["emphasis"] and "BRCA1" in claims[0]["emphasis"], claims[0]


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

    Item 12.9 (2026-09-23) REVERSED the two-column tables and the one-cell
    disease list this arm pinned: rule 2 adds each record's identifier, so
    the variant table reads "Variant | Identifier | Associated disease(s)"
    and the linked diseases are a "Disease | Identifier" table. The mapping,
    the markers, the placeholder rule and the summary clause are unchanged.
    """
    monkeypatch.setattr(graph_module, "resolve_concept_ids", _fake_resolve_concept_ids)
    _install(monkeypatch, lambda lines: f"{lines[1]} [1].")
    tokens = _tokens(await graph_module.write_node(_state("researcher", rows=_FOLDED_VARIANT_ROWS)))
    # Item 12.9 (2026-09-23): each table now carries its records' own
    # identifiers in an "Identifier" column (rule 2), so the variant table
    # reads "Variant | Identifier | Associated disease(s)" and the disease
    # list it links to is a "Disease | Identifier" table rather than a list.
    # The mapping itself, the markers and the placeholder rule are unchanged.
    tables = _tables(tokens)
    assert [header for header, _ in tables] == [
        ["Disease", "Identifier"],
        ["Variant", "Identifier", "Associated disease(s)"],
    ], tables
    (_, disease_rows), (_, variant_rows) = tables
    assert [t["cells"] for t in variant_rows] == [
        ["variant number 1", "ClinVar:1", "Maturity-onset diabetes of the young"],
        ["variant number 2", "ClinVar:2", ""],
    ]
    # Every row cites its own record; the first row also cites the disease
    # its cell names, and no mapping cell carries a raw code: the disease is
    # named in words, and its code lives only in its own Identifier cell.
    assert len(variant_rows[0]["marker_ids"]) == 2 and len(variant_rows[1]["marker_ids"]) == 1
    assert not any("MedGen:" in t["cells"][2] for t in variant_rows)
    headings = [t["text"].strip() for t in tokens if t["kind"] == "heading"]
    assert "Variant-to-disease mapping" in headings
    assert headings.index("Disease records found") < headings.index("Variant-to-disease mapping")
    assert [t["cells"] for t in disease_rows] == [
        ["Maturity-onset diabetes of the young", "MedGen:C0342276"]
    ], disease_rows
    assert "not provided" not in " ".join(cell for t in disease_rows for cell in t["cells"])
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
    # Fix-plan item 12.8 (2026-09-23): `_ROWS` is three distinct MedGen
    # citations (C1, C2, C3), one database. Before the fix this line
    # counted databases and read "Based on 1 source" over three visible
    # citations, the exact defect the ticket measured. It now counts the
    # distinct citation_ids a reader can see and click, so it reads three.
    assert done and done[0]["trust_line"].startswith("Based on 3 sources"), done
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
    `sentence_token`s for non-Researcher depths again.

    Item 12.9 (2026-09-23) changed the heading this arm read, not the
    property: the Plain language listing is now the one list under "Where
    this answer comes from" (rule 2), so that is the heading asserted."""
    _install(monkeypatch, lambda lines: "Nothing here matches any record at all.")
    tokens = _tokens(await graph_module.write_node(_state("plain_language")))
    kinds = [t["kind"] for t in tokens]
    assert "list_item" in kinds, kinds
    headings = [t["text"].strip() for t in tokens if t["kind"] == "heading"]
    assert headings == ["Where this answer comes from"], headings
    assert not any(
        t["kind"] == "claim" and t["text"].startswith("Disease name") for t in tokens
    ), [t["text"] for t in tokens if t["kind"] == "claim"]


# ---------------------------------------------------------------------------
# Item 12.9 (2026-09-23): the two depths differ on every question, and the
# evidence does not. The product owner's direction, in their words: "The
# plain vs researcher should vary duh for all questions. Not just a few".
# ---------------------------------------------------------------------------

# Two real-shaped papers, in the order `_ncbi_efetch_output_to_structured_
# fields` sorts a PubMed breadth result (by record URL).
_PAPERS = (
    ("31234567", "Caffeine ingestion and endurance cycling performance in trained athletes"),
    (
        "33388079",
        (
            "International society of sports nutrition position stand: caffeine and "
            "exercise performance"
        ),
    ),
)

_STATUS_TRIAL_ROWS = [
    graph_module._pseudo_row(
        "Clinical trial",
        {
            "name": f"trial title number {index}",
            "nct_id": f"NCT0000000{index}",
            "overall_status": "RECRUITING",
        },
        f"https://clinicaltrials.gov/study/NCT0000000{index}",
    )
    for index in range(1, 3)
]


#: One abstract per paper, two sentences each, so an abstract is its own
#: finding beside the title and the prose can quote it.
_ABSTRACTS = {
    "31234567": (
        "Caffeine improved time-trial performance in trained cyclists. "
        "The effect was seen at moderate doses."
    ),
    "33388079": (
        "Caffeine is effective for enhancing many types of exercise performance. "
        "Individual responses vary widely."
    ),
}


def _restating(lines: dict[int, str]) -> str:
    return " ".join(f"{body} [{index}]." for index, body in lines.items())


def _quoting_abstracts(lines: dict[int, str]) -> str:
    """A reply that quotes each abstract's first sentence verbatim, as a
    compliant model does, and restates every other finding. The quote cites
    the ABSTRACT finding, while the list row for the same paper cites its
    TITLE finding: one record, two citations."""
    parts = []
    for index, body in lines.items():
        if " abstract: " in body:
            sentence = body.split(" abstract: ", 1)[1].split(". ", 1)[0].rstrip(".")
            parts.append(f"{sentence} [{index}].")
        else:
            parts.append(f"{body} [{index}].")
    return " ".join(parts)


def _no_prose(lines: dict[int, str]) -> str:
    return "Nothing here matches any record at all."


def _papers_finding(call_id: str, *, abstracts: bool = False):
    """PubMed papers as `act_node` leaves them: the real breadth shaping, and
    the typed output kept for the Layer 2 citation builder."""
    from system_03_search_agent.harness.coordinator_worker import Finding
    from system_03_search_agent.tools.ncbi_efetch_schemas import (
        NcbiEfetchOutput,
        NcbiEfetchRecord,
    )

    records = [
        NcbiEfetchRecord(
            id=pmid,
            db="pubmed",
            fields={"title": title, **({"abstract": _ABSTRACTS[pmid]} if abstracts else {})},
            source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        )
        for pmid, title in _PAPERS
    ]
    output = NcbiEfetchOutput(
        status="ok", action="fetch", records=records, record_count=len(records),
        total_available=len(records), truncated=False,
    )
    finding = Finding(
        call_id=call_id, tool="ncbi_efetch", layer="layer_2_api",
        source="structured_pass_through",
        structured_fields=graph_module._ncbi_efetch_output_to_structured_fields(
            output, "pubmed_abstracts"
        ),
        extracted_entities=None, normalized_ids=None, evidence_summary=None,
    )
    return finding, output


def _papers_state(depth: str, *, abstracts: bool = False) -> dict[str, object]:
    """A topic question answered from PubMed alone: no gene, so no subject."""
    query = Query(
        text="Does caffeine improve exercise performance?",
        session_id="session-papers",
        trace_id="trace-papers",
        user_id=None,
        audience_depth=depth,  # type: ignore[arg-type]
    )
    finding, output = _papers_finding("ne-papers", abstracts=abstracts)
    return {
        "query": query,
        "harness": harness_module.Harness(trace_id=query.trace_id),
        "seq": 0,
        "start_monotonic": time.monotonic(),
        "findings": [finding],
        "findings_count": 1,
        "layer2_raw_outputs": {"ne-papers": output},
        "topic_search_term": "caffeine AND exercise AND performance",
    }


def _mixed_state(depth: str) -> dict[str, object]:
    """The disease question's graph records, plus trials carrying a status
    and live papers, each call under a fixed id so both depths mint the same
    citation ids."""
    from system_03_search_agent.harness.coordinator_worker import Finding

    state = _state(depth)
    trials = Finding(
        call_id="ct-mixed", tool="clinicaltrials_search", layer="layer_3_enrichment",
        source="structured_pass_through",
        structured_fields={
            "status": "ok", "row_count": 2, "total_available": 2, "truncated": False,
            "rows": _STATUS_TRIAL_ROWS, "error": None,
        },
        extracted_entities=None, normalized_ids=None, evidence_summary=None,
    )
    papers, output = _papers_finding("ne-mixed")
    state["findings"] = [*state["findings"], trials, papers]  # type: ignore[misc]
    state["findings_count"] = 3
    state["layer2_raw_outputs"] = {"ne-mixed": output}
    return state


def _folded_state(depth: str) -> dict[str, object]:
    return _state(depth, rows=_FOLDED_VARIANT_ROWS)


def _papers_with_abstracts_state(depth: str) -> dict[str, object]:
    return _papers_state(depth, abstracts=True)


def _opening(result) -> str:
    return next(t["text"] for t in _tokens(result) if t["kind"] == "claim")


def _rows(result) -> list[dict]:
    return [t for t in _tokens(result) if t["kind"] in ("list_item", "table_row")]


def _citation_ids(result) -> list[str]:
    return sorted(e.payload["citation_id"] for e in result["events"] if e.type == "citation")


def _done(result) -> dict:
    return next(e.payload for e in result["events"] if e.type == "done")


@pytest.mark.asyncio
async def test_12_9_a_disease_question_opens_and_lists_for_its_reader(monkeypatch) -> None:
    """Rules 1 and 2 on the disease question.

    RED before the change: both depths opened "Found 3 disease records for
    BRCA1: <titles>" and listed the same three one-cell rows under "Disease
    records found", so the two answers were the same text.
    """
    _install(monkeypatch, _structured_reply)
    plain = await graph_module.write_node(_state("plain_language"))
    _install(monkeypatch, _structured_reply)
    researcher = await graph_module.write_node(_state("researcher"))

    # Rule 1: the plain opening speaks to its reader, over the same records.
    assert _opening(plain) == "I found 3 conditions related to BRCA1 [1][2][3]. ", _opening(plain)
    assert _opening(researcher).startswith(
        "Found 3 disease records for BRCA1: disease name number 1 [1], "
    ), _opening(researcher)
    plain_lead = next(t for t in _tokens(plain) if t["kind"] == "claim")
    researcher_lead = next(t for t in _tokens(researcher) if t["kind"] == "claim")
    assert len(plain_lead["marker_ids"]) == 3
    assert plain_lead["marker_ids"] == researcher_lead["marker_ids"]
    assert "disease name number" not in plain_lead["text"], "plain language names no titles inline"

    # Rule 2, plain: one heading, one list, titles only.
    plain_tokens = _tokens(plain)
    headings = [t["text"].strip() for t in plain_tokens if t["kind"] == "heading"]
    assert headings == ["Where this answer comes from"], headings
    assert not any(t["kind"] in ("table_header", "table_row") for t in plain_tokens)
    assert [t["cells"] for t in _rows(plain)] == [
        ["disease name number 1"], ["disease name number 2"], ["disease name number 3"]
    ]

    # Rule 2, researcher: the identifier column names each row's own record,
    # the one its citation chip opens.
    source_id = {
        e.payload["citation_id"]: e.payload["source_id"]
        for e in researcher["events"]
        if e.type == "citation"
    }
    ((header, rows),) = _tables(_tokens(researcher))
    assert header == ["Disease", "Identifier"], header
    assert [row["cells"][1] for row in rows] == ["MedGen:C1", "MedGen:C2", "MedGen:C3"]
    for row in rows:
        assert row["cells"][1] == source_id[row["marker_ids"][0]], row


@pytest.mark.asyncio
async def test_12_9_a_papers_question_gives_plain_titles_and_a_researcher_pmids(monkeypatch) -> None:
    """The product owner's own example, a topic question answered from
    PubMed, with each paper cited through the real Layer 2 builder.

    RED before the change: both depths opened "Found 2 pubmed records:
    <titles>" and listed the two titles alone, with no PMID anywhere.
    """
    _install(monkeypatch, _restating)
    plain = await graph_module.write_node(_papers_state("plain_language"))
    _install(monkeypatch, _restating)
    researcher = await graph_module.write_node(_papers_state("researcher"))

    assert _opening(plain) == "I found 2 published papers on this topic [1][2]. ", _opening(plain)
    assert _opening(researcher).startswith("Found 2 pubmed records: "), _opening(researcher)
    assert [t["cells"] for t in _rows(plain)] == [[title] for _, title in _PAPERS]
    assert all(t["kind"] == "list_item" for t in _rows(plain))

    ((header, rows),) = _tables(_tokens(researcher))
    assert header == ["Paper", "Identifier"], header
    assert [t["cells"] for t in rows] == [[title, f"PMID:{pmid}"] for pmid, title in _PAPERS]
    # Populate check: the PMID in each row is the one its own citation carries.
    assert _sources(researcher) == [pmid for pmid, _ in _PAPERS]


@pytest.mark.asyncio
async def test_12_9_with_no_model_prose_the_two_depths_still_differ(monkeypatch) -> None:
    """Rule 4. The model's prose grounds nothing, so the code-built records
    are the whole answer. This is the branch the 2026-09-23 diagnosis found
    identical at both depths on every question where both fell back to it.

    RED before the change: same opening, same one-cell list, same heading.
    """
    _install(monkeypatch, _no_prose)
    plain = await graph_module.write_node(_state("plain_language"))
    _install(monkeypatch, _no_prose)
    researcher = await graph_module.write_node(_state("researcher"))

    for result in (plain, researcher):
        # Populate check: the structured fallback really ran, and the only
        # prose on the page is the code-built opening sentence.
        notes = [t["text"] for t in _tokens(result) if t["kind"] == "note"]
        assert any(
            note.startswith("Note: the written summary of these records could not be verified")
            for note in notes
        ), notes
        assert [t["kind"] for t in _tokens(result)].count("claim") == 1

    assert _opening(plain) != _opening(researcher)
    assert _opening(plain).startswith("I found 3 conditions related to BRCA1 "), _opening(plain)
    assert [t["kind"] for t in _rows(plain)] == ["list_item"] * 3
    assert [t["kind"] for t in _rows(researcher)] == ["table_row"] * 3
    assert [t["cells"] for t in _rows(plain)] != [t["cells"] for t in _rows(researcher)]
    assert _citation_ids(plain) == _citation_ids(researcher)


# (state builder, Synth reply, whether the fold's MedGen resolver is faked)
_FIREWALL_CASES = {
    "model prose over graph records": (_state, _structured_reply, False),
    "a folded variant-to-disease table": (_folded_state, lambda lines: f"{lines[1]} [1].", True),
    "the structured fallback": (_state, _no_prose, False),
    "live PubMed papers": (_papers_state, _restating, False),
    "papers whose abstracts the prose quotes": (
        _papers_with_abstracts_state, _quoting_abstracts, False
    ),
    "graph, trial and paper records together": (_mixed_state, _restating, False),
}


def _page_by_citation_id(result) -> dict[str, str]:
    return {
        e.payload["citation_id"]: e.payload["source_url"]
        for e in result["events"]
        if e.type == "citation"
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("case", list(_FIREWALL_CASES))
async def test_12_9_the_firewall_depth_changes_the_display_never_the_evidence(
    monkeypatch, case: str
) -> None:
    """Rule 5, THE LINE NOT CROSSED (Section 14.1's firewall): both depths
    cite exactly the same records, every one listed as its own clickable
    row, with the same grounded sentence behind it and the same verdict.
    Depth changes wording, layout and columns, never which evidence is shown.

    "Every record listed" is checked per RECORD, by its page, and not per
    citation id, because that is the rule's own word and what a reader sees:
    when the prose quotes a paper's abstract, that quote carries its own
    citation while the paper's list row carries its title's, one record and
    two chips, at both depths alike. The abstracts case exercises exactly
    that, and asserts it happened, so the per-record check cannot pass on a
    fixture where the two readings coincide.

    POPULATE-CHECKED FIRST: the two pages are asserted to differ, in their
    opening sentence and in their list cells, so this arm can never pass by
    comparing a page with itself. That is also what turns it RED against the
    code before the change, where the two pages were identical.
    """
    build, reply, folded = _FIREWALL_CASES[case]
    if folded:
        monkeypatch.setattr(graph_module, "resolve_concept_ids", _fake_resolve_concept_ids)
    _install(monkeypatch, reply)
    plain = await graph_module.write_node(build("plain_language"))
    _install(monkeypatch, reply)
    researcher = await graph_module.write_node(build("researcher"))

    assert _opening(plain) != _opening(researcher), "populate check: the openings must differ"
    assert [t["cells"] for t in _rows(plain)] != [t["cells"] for t in _rows(researcher)], (
        "populate check: the lists must differ"
    )

    # Exactly the same citations.
    assert _citation_ids(plain), "populate check: the answer cited nothing"
    assert _citation_ids(plain) == _citation_ids(researcher)
    # Every cited record has its own row, which carries a citation of it.
    for result in (plain, researcher):
        page_of = _page_by_citation_id(result)
        listed = {page_of[row["marker_ids"][0]] for row in _rows(result)}
        assert listed == set(page_of.values()), (listed, set(page_of.values()))
    if build is _papers_with_abstracts_state:
        # Populate check for the per-record reading: the prose really did
        # cite an abstract, so some citation has no list row of its own.
        own = {row["marker_ids"][0] for row in _rows(plain)}
        assert set(_citation_ids(plain)) - own, "no abstract was cited; the case proves nothing"
    # The grounded sentence behind every row, and the record it cites, are
    # the same at both depths, whatever order the rows are shown in.
    assert sorted((row["text"], row["marker_ids"][0]) for row in _rows(plain)) == sorted(
        (row["text"], row["marker_ids"][0]) for row in _rows(researcher)
    )
    # The same verdict on the same evidence.
    assert _done(plain)["trust_outcome"] == _done(researcher)["trust_outcome"]
