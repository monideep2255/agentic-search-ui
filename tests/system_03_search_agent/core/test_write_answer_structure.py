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

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.contracts.token_order import in_reading_order, one_per_citation_id
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
        # The web bundle built with build phase 8.7 asks for `placement`
        # (fix round, F-8.7-A14), so the listing leaves first.
        "context": RequestContext(surface="web_ui", reads_placement=True),
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


def _read_tokens(result) -> list[dict]:
    """The tokens in reading order, as every surface lays them out.

    Build phase 8.7 sends the record listing before the summary, each token
    carrying `placement`. A reader sees the summary above the listing
    (`contracts/token_order.py`), so an arm about the answer's STRUCTURE
    reads it that way; `_tokens` keeps the arrival order for an arm about
    the stream.
    """
    return in_reading_order(_tokens(result))


def _listing_arrived_first(result) -> bool:
    """Whether the first token on the wire was placed in the listing: the
    early send this phase turns on, so a reading-order assertion is not
    passing on a stream that already arrived in reading order."""
    tokens = _tokens(result)
    return bool(tokens) and tokens[0].get("placement") == "listing"


def _citation_payloads(result) -> list[dict]:
    """The citations as every surface reads them (F-8.7-A04, card 57): one
    per citation id, a listing citation sent again with its checked words in
    the first one's place."""
    return one_per_citation_id(e.payload for e in result["events"] if e.type == "citation")


def _sources(result) -> list[str]:
    return sorted(payload["source_id"] for payload in _citation_payloads(result))


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
    record. The headings, the paragraphs and the markers are unchanged.

    Build phase 8.7: the listing now arrives before the summary, so the
    order is asserted in reading order (summary above listing), the order
    every surface shows; the populate-check proves the arrival order really
    differs."""
    _install(monkeypatch, _structured_reply)
    result = await graph_module.write_node(_state("researcher"))
    assert _listing_arrived_first(result), (
        "populate-check failed: the listing did not arrive first, so the "
        "reading order below is not doing any work."
    )
    tokens = _read_tokens(result)
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
    "Where this answer comes from", titles only.

    Build phase 8.7: read in reading order, the order every surface shows.
    The note follows the listing there, so it carries `placement`
    "listing": it is the last thing under the records, not part of the
    summary slot above them."""
    _install(
        monkeypatch, lambda lines: f"{lines[1]} [1].\n\n## Disease associations\n{lines[2]} [2]."
    )
    result = await graph_module.write_node(_state("plain_language"))
    assert _listing_arrived_first(result), (
        "populate-check failed: the listing did not arrive first, so the "
        "reading order below is not doing any work."
    )
    tokens = _read_tokens(result)
    headings = [t["text"].strip() for t in tokens if t["kind"] == "heading"]
    assert "Disease associations" not in headings, headings
    assert headings == ["Where this answer comes from"], headings
    assert any(t["kind"] == "list_item" for t in tokens), {t["kind"] for t in tokens}
    assert not any(t["text"].startswith("Note: the records below") for t in tokens)
    assert tokens[-1] == {
        "text": "This is a research summary, not medical advice.",
        "marker_ids": [],
        "kind": "note",
        "cells": None,
        "emphasis": None,
        "placement": "listing",
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
    citations = {
        e.payload["citation_id"]: e.payload["display_index"]
        for e in result["events"]
        if e.type == "citation"
    }
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
    placeholder "not provided", so its cell says why (card 103) and the disclosure
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
        # Card 103: the placeholder-only row says why its cell has no name.
        ["variant number 2", "ClinVar:2", "None named: the ClinVar record says not provided"],
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
    assert any(n.startswith("2 variant links to ClinVar placeholder conditions") for n in notes), (
        notes
    )
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
        e.payload
        for e in result["events"]
        if e.type == "trust_signal" and e.payload.get("scope") == "answer"
    ]
    assert answer and "summary" not in answer[0], answer
    claim_signals = [
        e
        for e in result["events"]
        if e.type == "trust_signal" and e.payload.get("scope") == "claim"
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
    tokens = _tokens(
        await graph_module.write_node(_state("researcher", rows=_INTRONIC_VARIANT_ROWS))
    )
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
    assert not any(t["kind"] == "claim" and t["text"].startswith("Disease name") for t in tokens), [
        t["text"] for t in tokens if t["kind"] == "claim"
    ]


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
        status="ok",
        action="fetch",
        records=records,
        record_count=len(records),
        total_available=len(records),
        truncated=False,
    )
    finding = Finding(
        call_id=call_id,
        tool="ncbi_efetch",
        layer="layer_2_api",
        source="structured_pass_through",
        structured_fields=graph_module._ncbi_efetch_output_to_structured_fields(
            output, "pubmed_abstracts"
        ),
        extracted_entities=None,
        normalized_ids=None,
        evidence_summary=None,
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
        call_id="ct-mixed",
        tool="clinicaltrials_search",
        layer="layer_3_enrichment",
        source="structured_pass_through",
        structured_fields={
            "status": "ok",
            "row_count": 2,
            "total_available": 2,
            "truncated": False,
            "rows": _STATUS_TRIAL_ROWS,
            "error": None,
        },
        extracted_entities=None,
        normalized_ids=None,
        evidence_summary=None,
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
    return sorted(payload["citation_id"] for payload in _citation_payloads(result))


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
        ["disease name number 1"],
        ["disease name number 2"],
        ["disease name number 3"],
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
async def test_12_9_a_papers_question_gives_plain_titles_and_a_researcher_pmids(
    monkeypatch,
) -> None:
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
            note.startswith("Note: no written summary could be checked against the records")
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
        _papers_with_abstracts_state,
        _quoting_abstracts,
        False,
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


def test_one_record_cited_by_two_claims_is_one_row() -> None:
    """The same OMIM record carried a title claim and a symbol claim, and the
    table listed "DNA MISMATCH REPAIR PROTEIN MLH1; MLH1" twice with the same
    citation. Rows are unique by record."""
    from system_03_search_agent.contracts.events import CitationPayload
    from system_03_search_agent.synthesis.findings import SynthFinding

    url = "https://omim.org/entry/120436"
    finding = SynthFinding(
        ref_index=1,
        citation_id="ne-omim-1",
        layer="layer_2_api",
        tool="ncbi_efetch",
        field="title",
        field_value="DNA MISMATCH REPAIR PROTEIN MLH1; MLH1",
        source_url=url,
        entity_type="omim",
    )
    citation = CitationPayload(
        citation_id="ne-omim-1",
        display_index=1,
        source="omim",
        source_id="120436",
        source_url=url,
        layer="layer_2_api",
        field="title",
        claim_text="DNA MISMATCH REPAIR PROTEIN MLH1",
        evidence_kind="primary_assertion",
        assertion_confidence="asserted",
        license="public_domain_us_gov",
    )
    for depth in ("researcher", "plain_language"):
        tokens = graph_module._answer_tokens(
            audience_depth=depth,
            question="q",
            model_grounding=None,
            model_layout=None,  # type: ignore[arg-type]
            fallback_sentences=(
                "DNA MISMATCH REPAIR PROTEIN MLH1 [1]. ",
                "MLH1 [1]. ",
            ),
            tail_sentences=(),
            tail_is_listing=False,
            citations=[citation],
            synth_findings=[finding],
            findings=[],
            mentions=[],
            notes=[],
        )
        rows = [t for t in tokens if t.kind in ("table_row", "list_item")]
        assert len(rows) == 1, (depth, [t.cells for t in rows])


_ISOLATE_ROWS = [
    {
        "node_or_edge_type": "Pathogen Detection isolate",
        "curie": f"BioSample:SAMN0000000{index}",
        "fields": {
            "name": f"strain-{index}",
            "amr_genotypes": f"blaCTX-M-15, acrF{index}",
            **({"collection_date": "2023-04-01"} if index == 1 else {}),
        },
        "source_url": f"https://www.ncbi.nlm.nih.gov/pathogens/isolates/#SAMN0000000{index}",
        "graph_snapshot_version": "v1",
    }
    for index in range(1, 3)
]


@pytest.mark.asyncio
async def test_card94_plain_language_isolates_show_the_genes_table(monkeypatch) -> None:
    """Owner decision D11 (2026-10-05): Plain language shows the isolate
    table with each isolate's genes. RED before: a one-cell list, no genes."""
    _install(monkeypatch, _no_prose)
    result = await graph_module.write_node(_state("plain_language", rows=_ISOLATE_ROWS))
    ((header, rows),) = _tables(_tokens(result))
    assert header[0] == "Isolate" and "AMR genes" in header, header
    gene_cells = [cell for row in rows for cell in row["cells"]]
    assert "blaCTX-M-15, acrF1" in gene_cells and "blaCTX-M-15, acrF2" in gene_cells
    headings = [t["text"].strip() for t in _tokens(result) if t["kind"] == "heading"]
    assert "Isolates and their AMR genes" in headings, headings
    # A row with no collection date says so instead of showing a blank cell.
    column = header.index("Collected")
    assert [row["cells"][column] for row in rows] == ["2023", "Not recorded"]
    assert all(row["marker_ids"] for row in rows)


@pytest.mark.asyncio
async def test_card94_plain_language_other_records_stay_titles_only(monkeypatch) -> None:
    """Every other record type keeps the titles-only Plain listing."""
    _install(monkeypatch, _no_prose)
    result = await graph_module.write_node(_state("plain_language"))
    assert _tables(_tokens(result)) == []
    assert [t["kind"] for t in _rows(result)] == ["list_item"] * 3


_ORGANISM_ROW = {
    "node_or_edge_type": "Organism",
    "curie": "NCBITaxon:562",
    "fields": {"name": "Escherichia coli"},
    "source_url": "https://www.ncbi.nlm.nih.gov/taxonomy/562",
    "graph_snapshot_version": "v1",
}


@pytest.mark.asyncio
async def test_card94_plain_language_isolates_with_an_organism_keep_the_table(
    monkeypatch,
) -> None:
    """Query 33's shape: isolates plus the organism's own record. The isolates
    keep their genes table; the organism is listed apart, titles only. RED
    before: one organism record sent the whole list to titles-only."""
    _install(monkeypatch, _no_prose)
    rows = [*_ISOLATE_ROWS, _ORGANISM_ROW]
    result = await graph_module.write_node(_state("plain_language", rows=rows))
    ((header, table_rows),) = _tables(_tokens(result))
    assert header[0] == "Isolate" and "AMR genes" in header, header
    assert len(table_rows) == 2
    assert "blaCTX-M-15, acrF1" in [c for row in table_rows for c in row["cells"]]
    items = [t for t in _tokens(result) if t["kind"] == "list_item"]
    assert len(items) == 1 and "Escherichia coli" in items[0]["cells"][0]
    assert items[0]["marker_ids"]


# ---------------------------------------------------------------------------
# Card 23 (owner, 2026-10-06): under the variant-to-disease table, and under
# no other table, one code-built line says where its links and its disease
# names come from. Each arm was shown red by one mutation before it was kept
# (`testing/Developer/reports/2026-10-06_card23/build.md`).
# ---------------------------------------------------------------------------

# A gene-to-disease table beside the variant one, so "under no other table"
# is tested against a real second mapping table, not only an absent one.
_FOLDED_GENE_ROW = {
    "node_or_edge_type": "Gene",
    "curie": "NCBIGene:2645",
    "fields": {"name": "GCK", "medgen_condition_ids": ["MedGen:C0342276"]},
    "source_url": "https://www.ncbi.nlm.nih.gov/gene/2645",
    "graph_snapshot_version": "v1",
}


def _source_notes(tokens: list[dict]) -> list[int]:
    from system_03_search_agent.synthesis.answer_layout import VARIANT_TO_DISEASE_SOURCE_NOTE

    return [
        index
        for index, token in enumerate(tokens)
        if token["kind"] == "note" and token["text"] == VARIANT_TO_DISEASE_SOURCE_NOTE
    ]


@pytest.mark.asyncio
async def test_card23_the_source_note_sits_directly_under_the_variant_table(monkeypatch) -> None:
    """Red when the wiring is removed (no note) or when the note is emitted
    above the table's rows instead of after them."""
    monkeypatch.setattr(graph_module, "resolve_concept_ids", _fake_resolve_concept_ids)
    _install(monkeypatch, lambda lines: f"{lines[1]} [1].")
    rows = [*_FOLDED_VARIANT_ROWS, _FOLDED_GENE_ROW]
    tokens = _tokens(await graph_module.write_node(_state("researcher", rows=rows)))
    headings = [t["text"].strip() for t in tokens if t["kind"] == "heading"]
    assert "Variant-to-disease mapping" in headings and "Gene-to-disease mapping" in headings
    (note_at,) = _source_notes(tokens)
    variant_heading = next(
        i for i, t in enumerate(tokens) if t["kind"] == "heading" and "Variant-to-disease" in t["text"]
    )
    # Everything between the variant heading and the note is that table.
    between = [t["kind"] for t in tokens[variant_heading + 1 : note_at]]
    assert between[0] == "table_header" and between[-1] == "paragraph_break", between
    assert set(between[1:-1]) == {"table_row"}, between
    # And the very next structure after the note is the gene table's heading.
    after = [t for t in tokens[note_at + 1 :] if t["kind"] != "paragraph_break"]
    assert after[0]["kind"] == "heading" and "Gene-to-disease" in after[0]["text"], after[:2]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("depth", "rows"),
    [
        # Plain language lists the same records as titles, with no table.
        ("plain_language", _FOLDED_VARIANT_ROWS),
        # Variants with no folded diseases: a variant list, not the mapping.
        ("researcher", _VARIANT_ROWS),
        # A gene-to-disease table alone: a different mapping table.
        ("researcher", [_FOLDED_GENE_ROW, *_FOLDED_VARIANT_ROWS[1:3]]),
    ],
    ids=["plain_language", "variants_without_diseases", "gene_to_disease_table"],
)
async def test_card23_no_variant_table_no_source_note(monkeypatch, depth, rows) -> None:
    """Red when the helper drops its `entity_type` check (the gene table
    gets the note), its `mapped` check (the plain variant list gets it), or
    when the note is added to the answer-wide notes (Plain language gets it)."""
    monkeypatch.setattr(graph_module, "resolve_concept_ids", _fake_resolve_concept_ids)
    _install(monkeypatch, lambda lines: f"{lines[1]} [1].")
    tokens = _tokens(await graph_module.write_node(_state(depth, rows=rows)))
    headings = [t["text"].strip() for t in tokens if t["kind"] == "heading"]
    assert "Variant-to-disease mapping" not in headings, headings
    # Populate-check: each case still lists its records, and the gene case
    # really shows its own mapping table, so the arm cannot pass on an
    # empty page.
    listed = [t for t in tokens if t["kind"] in ("table_row", "list_item")]
    assert len(listed) >= 2, tokens
    if rows[0] is _FOLDED_GENE_ROW:
        assert "Gene-to-disease mapping" in headings, headings
    assert _source_notes(tokens) == [], [t["text"] for t in tokens if t["kind"] == "note"]


def test_card23_the_note_names_the_sources_the_code_actually_uses() -> None:
    """The note's words, checked against the code that fills the table.

    - The mapping column is the fold field only the two variant templates
      write, and both traverse `has_phenotype`, the ClinVar edge.
    - A table row's anchor is a SequenceVariant, whose only CURIE prefix in
      this graph is ClinVar, cited to its ClinVar variation page.
    - The disease cell is a MedGen title, resolved by `resolve_concept_ids`.

    Red when the note names another source (LitVar2 in the mutation run) or
    stops naming ClinVar or MedGen."""
    from system_03_search_agent.synthesis.answer_layout import (
        TABLE_COLUMNS,
        VARIANT_TO_DISEASE_SOURCE_NOTE,
    )
    from system_03_search_agent.tools import cypher_templates
    from system_03_search_agent.tools.graph_schema_constants import (
        EDGE_ENDPOINTS,
        LABEL_CURIE_PREFIXES,
    )

    field = TABLE_COLUMNS["SequenceVariant"][0]
    assert field == cypher_templates.FOLD_FIELD_VARIANT_CONDITIONS
    for template in (
        cypher_templates._gene_variant_diseases_template("e0"),
        cypher_templates._gene_variant_disease_link_template("e0", ["e1"]),
    ):
        assert template.fold is not None and template.fold[2] == field
        assert template.edge_label == "has_phenotype"
    assert EDGE_ENDPOINTS["has_phenotype"] == ("SequenceVariant", "Disease")
    assert LABEL_CURIE_PREFIXES["SequenceVariant"] == ("ClinVar",)

    note = VARIANT_TO_DISEASE_SOURCE_NOTE
    assert "ClinVar record" in note
    assert "MedGen titles" in note
    for other in ("LitVar", "PubTator", "dbSNP", "OMIM"):
        assert other not in note, other


# ---------------------------------------------------------------------------
# Cards 103 and 104 (2026-10-08): no blank disease cell, no repeated record.
# ---------------------------------------------------------------------------

_HNF1A_VARIANTS = [
    ("ClinVar:1048822", ["MedGen:C3661900"]),
    ("ClinVar:1051750", ["MedGen:C3661900"]),
    ("ClinVar:1098821", ["MedGen:CN169374"]),
    ("ClinVar:1104934", ["MedGen:C3661900"]),
    ("ClinVar:1105252", ["MedGen:C3661900"]),
    ("ClinVar:2000001", ["MedGen:C0342276"]),
    ("ClinVar:2000002", ["MedGen:C9999999"]),
]
_HNF1A_TITLES = {
    "MedGen:C3661900": "not provided",
    "MedGen:CN169374": "not specified",
    "MedGen:C0342276": "Maturity-onset diabetes of the young",
    "MedGen:C9999999": None,
}


def _variant_row(curie: str, conditions: list[str]) -> dict:
    return {
        "node_or_edge_type": "SequenceVariant",
        "curie": curie,
        "fields": {"name": f"variant {curie}", "clinvar_condition_ids": conditions},
        "source_url": f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{curie.split(':')[1]}/",
        "graph_snapshot_version": "v1",
    }


@pytest.mark.asyncio
async def test_no_disease_cell_is_blank_without_a_reason(monkeypatch) -> None:
    """Card 103. Five HNF1A variants whose only ClinVar condition is a
    placeholder, one with a real name, one whose name lookup failed.
    Red before the change: the five placeholder cells and the failed-lookup
    cell were all ''. Mutation: make `empty_cell_reason` return '' and the
    assertions go red again."""

    async def _resolve(concept_ids):
        return {cid: _HNF1A_TITLES.get(cid) for cid in concept_ids}

    monkeypatch.setattr(graph_module, "resolve_concept_ids", _resolve)
    _install(monkeypatch, lambda lines: f"{lines[1]} [1].")
    rows = [_variant_row(curie, conds) for curie, conds in _HNF1A_VARIANTS]
    tokens = _tokens(await graph_module.write_node(_state("researcher", rows=rows)))
    ((header, table_rows),) = _tables(tokens)
    assert header == ["Variant", "Identifier", "Associated disease(s)"]
    cells = {t["cells"][1]: t["cells"][2] for t in table_rows}
    none_provided = "None named: the ClinVar record says not provided"
    for curie in ("ClinVar:1048822", "ClinVar:1051750", "ClinVar:1104934", "ClinVar:1105252"):
        assert cells[curie] == none_provided, cells
    assert cells["ClinVar:1098821"] == "None named: the ClinVar record says not specified"
    assert cells["ClinVar:2000001"] == "Maturity-onset diabetes of the young"
    assert cells["ClinVar:2000002"] == "Name could not be looked up"
    assert all(c.strip() for c in cells.values()), cells


_CLINVAR_PAGE = "https://www.ncbi.nlm.nih.gov/clinvar/variation/9/"


def test_empty_cell_reason_names_both_placeholders_and_a_failed_lookup() -> None:
    from system_03_search_agent.synthesis.answer_layout import empty_cell_reason

    titles = {"a": "not provided", "b": "not specified", "c": None}
    fields = {"clinvar_condition_ids": ["a", "b"]}
    assert empty_cell_reason("SequenceVariant", fields, titles, _CLINVAR_PAGE) == (
        "None named: the ClinVar record says not provided and not specified"
    )
    assert empty_cell_reason("SequenceVariant", {"clinvar_condition_ids": []}, titles) == ""


def test_a_failed_lookup_beside_a_placeholder_never_says_none_named() -> None:
    """J-103-01: the record links a condition we could not name, so the cell
    says only that. Red before the fix round: 'None named: the ClinVar
    record says not provided; Name could not be looked up'."""
    from system_03_search_agent.synthesis.answer_layout import empty_cell_reason

    titles = {"a": "not provided", "c": None}
    both = {"clinvar_condition_ids": ["a", "c"]}
    assert empty_cell_reason("SequenceVariant", both, titles, _CLINVAR_PAGE) == (
        "Name could not be looked up"
    )


def test_only_a_clinvar_variant_row_is_told_the_clinvar_record_says() -> None:
    """J-103-02, A-103-01: a gene row, or a variant row whose page is not a
    ClinVar variant record, never cites 'the ClinVar record'. Red before
    the fix round: the gene row read 'None named: the ClinVar record says
    not provided'."""
    from system_03_search_agent.synthesis.answer_layout import empty_cell_reason

    titles = {"a": "not provided", "c": None}
    gene = {"medgen_condition_ids": ["a"]}
    assert empty_cell_reason("Gene", gene, titles, "https://www.ncbi.nlm.nih.gov/gene/675") == ""
    variant = {"clinvar_condition_ids": ["a"]}
    dbsnp = "https://www.ncbi.nlm.nih.gov/snp/rs80357906"
    assert empty_cell_reason("SequenceVariant", variant, titles, dbsnp) == ""
    assert empty_cell_reason("SequenceVariant", variant, titles, _CLINVAR_PAGE) == (
        "None named: the ClinVar record says not provided"
    )
    # A failed lookup is true of any row, and names no source.
    assert empty_cell_reason("Gene", {"medgen_condition_ids": ["c"]}, titles) == (
        "Name could not be looked up"
    )


@pytest.mark.asyncio
async def test_a_gene_row_in_the_table_is_not_told_the_clinvar_record_says(monkeypatch) -> None:
    """J-103-02 through the real `write_node`: BRCA2's only linked condition
    is the placeholder 'not provided'. Its cell stays empty, as on develop,
    and never names a ClinVar record its own chip does not open."""

    async def _resolve(concept_ids):
        titles = {"MedGen:C0677776": "Hereditary breast ovarian cancer syndrome"}
        titles["MedGen:C3661900"] = "not provided"
        return {cid: titles.get(cid) for cid in concept_ids}

    monkeypatch.setattr(graph_module, "resolve_concept_ids", _resolve)
    _install(monkeypatch, lambda lines: " ".join(f"{b} [{i}]." for i, b in lines.items()))
    rows = [
        {
            "node_or_edge_type": "Gene",
            "curie": curie,
            "fields": {"name": name, "symbol": name, "medgen_condition_ids": [condition]},
            "source_url": f"https://www.ncbi.nlm.nih.gov/gene/{curie.split(':')[1]}",
            "graph_snapshot_version": "v1",
        }
        for curie, name, condition in (
            ("NCBIGene:672", "BRCA1", "MedGen:C0677776"),
            ("NCBIGene:675", "BRCA2", "MedGen:C3661900"),
        )
    ]
    tokens = _tokens(await graph_module.write_node(_state("researcher", rows=rows)))
    ((header, table_rows),) = _tables(tokens)
    assert header == ["Gene", "Identifier", "Associated disease"], header
    cells = {t["cells"][1]: t["cells"][2] for t in table_rows}
    assert cells["NCBIGene:672"] == "Hereditary breast ovarian cancer syndrome"
    assert cells["NCBIGene:675"] == "", cells
    assert not any("ClinVar" in t["cells"][2] for t in table_rows), cells


def test_only_not_provided_and_not_specified_are_quoted() -> None:
    """J-103-09, A-103-05: 'see cases' quoted bare reads as an instruction.
    Red before the fix round: 'None named: the ClinVar record says see
    cases'."""
    from system_03_search_agent.synthesis.answer_layout import empty_cell_reason

    titles = {"s": "See cases", "a": "not provided", "a2": "Not provided"}
    see_cases = {"clinvar_condition_ids": ["s"]}
    assert empty_cell_reason("SequenceVariant", see_cases, titles, _CLINVAR_PAGE) == (
        "None named: the ClinVar record gives only a placeholder"
    )
    mixed = {"clinvar_condition_ids": ["a", "s"]}
    assert empty_cell_reason("SequenceVariant", mixed, titles, _CLINVAR_PAGE) == (
        "None named: the ClinVar record gives only a placeholder"
    )
    # The same placeholder twice is said once.
    twice = {"clinvar_condition_ids": ["a", "a2"]}
    assert empty_cell_reason("SequenceVariant", twice, titles, _CLINVAR_PAGE) == (
        "None named: the ClinVar record says not provided"
    )


def test_the_notes_line_agrees_with_the_cells() -> None:
    """A-103-04, J-103-07: the cells now show placeholder rows, so the Notes
    line no longer says those links 'are not listed'. Its count stays."""
    from system_03_search_agent.synthesis.answer_layout import placeholder_links_note

    assert placeholder_links_note(4) == (
        "4 variant links to ClinVar placeholder conditions "
        "('not provided', 'not specified' or 'see cases') are not listed as diseases."
    )
    assert placeholder_links_note(1).startswith("1 variant link to ")  # type: ignore[union-attr]
    assert placeholder_links_note(0) is None


def _gene_row(url: str, name: str, curie: str = "NCBIGene:672") -> dict:
    return {
        "node_or_edge_type": "Gene",
        "curie": curie,
        "fields": {"name": name, "symbol": name},
        "source_url": url,
        "graph_snapshot_version": "v1",
    }


async def _gene_answer(monkeypatch, depth: str, rows: list[dict]):
    """One graph call per row, so each row is its own citation (the shape
    of the graph record plus a live record of one page in the evidence)."""
    from system_03_search_agent.harness.coordinator_worker import Finding

    _install(monkeypatch, lambda lines: " ".join(f"{b} [{i}]." for i, b in lines.items()))
    state = _state(depth, rows=rows[:1])
    findings = [state["findings"][0]]
    for index, row in enumerate(rows[1:], start=2):
        findings.append(
            Finding(
                call_id=f"cq-structure-{index}",
                tool="cypher_query",
                layer="layer_1_graph",
                source="structured_pass_through",
                structured_fields={
                    "status": "ok",
                    "row_count": 1,
                    "total_available": 1,
                    "truncated": False,
                    "rows": [row],
                    "error": None,
                },
                extracted_entities=None,
                normalized_ids=None,
                evidence_summary=None,
            )
        )
    state["findings"] = findings
    state["findings_count"] = len(findings)
    return await graph_module.write_node(state)


def _numbers(result, tokens: list[dict]) -> tuple[str, str, int]:
    """The opening line, the trust line and the count of distinct source
    pages (the key Sources counts on)."""
    from system_03_search_agent.contracts.events import source_page_key

    done = next(e.payload for e in result["events"] if e.type == "done")
    opening = next(t["text"] for t in tokens if t["kind"] == "claim")
    pages = {
        source_page_key(e.payload["source_url"])
        for e in result["events"]
        if e.type == "citation"
    }
    return opening, done["trust_line"], len(pages)


@pytest.mark.asyncio
async def test_one_gene_page_is_one_row_with_every_citation(monkeypatch) -> None:
    """Card 104, case A: the graph link has no trailing slash, the live link
    has one. Red before the change: two 'BRCA1 NCBIGene:672' rows.
    Mutation: key on the raw link plus cells and this goes red; drop the
    merge and the marker assertion goes red."""
    rows = [
        _gene_row("https://www.ncbi.nlm.nih.gov/gene/672", "BRCA1"),
        _gene_row("https://www.ncbi.nlm.nih.gov/gene/672/", "BRCA1"),
    ]
    result = await _gene_answer(monkeypatch, "researcher", rows)
    tokens = _tokens(result)
    ((_, table_rows),) = _tables(tokens)
    assert [t["cells"] for t in table_rows] == [["BRCA1", "NCBIGene:672"]], table_rows
    assert table_rows[0]["marker_ids"] == ["cq-structure-1", "cq-structure-2-2"], table_rows
    # Every number the answer states is the one the page alone would give.
    opening, trust, pages = _numbers(result, tokens)
    single = await _gene_answer(monkeypatch, "researcher", rows[:1])
    opening_one, trust_one, pages_one = _numbers(single, _tokens(single))
    assert pages == pages_one == 1
    assert trust == trust_one
    assert opening_one.startswith("Found 1 gene record")
    assert opening.startswith("Found 1 gene record"), opening


def _two_citations_one_page_tokens(label_a: str, label_b: str, depth: str):
    """Case B and the Plain language list: two findings of one exact link,
    two names, straight through the table builder."""
    from types import SimpleNamespace as NS

    from system_03_search_agent.contracts.events import CitationPayload
    from system_03_search_agent.harness.coordinator_worker import Finding
    from system_03_search_agent.synthesis.findings import SynthFinding

    url = "https://www.ncbi.nlm.nih.gov/gene/672"
    labels = {"cq-g-8": label_a, "cq-g-12": label_b}
    findings = [
        Finding(
            call_id=cid,
            tool="cypher_query",
            layer="layer_1_graph",
            source="structured_pass_through",
            structured_fields={
                "status": "ok",
                "row_count": 1,
                "total_available": 1,
                "truncated": False,
                "rows": [_gene_row(url, label)],
                "error": None,
            },
            extracted_entities=None,
            normalized_ids=None,
            evidence_summary=None,
        )
        for cid, label in labels.items()
    ]
    synth = [
        SynthFinding(
            ref_index=index,
            citation_id=cid,
            layer="layer_1_graph",
            tool="cypher_query",
            field="name",
            field_value=label,
            source_url=url,
            entity_type="Gene",
            curie="NCBIGene:672",
            call_id=cid,
        )
        for (cid, label), index in zip(labels.items(), (8, 12), strict=True)
    ]
    cites = [
        CitationPayload(
            citation_id=s.citation_id,
            display_index=s.ref_index,
            source="NCBIGene",
            source_id="NCBIGene:672",
            source_url=url,
            layer="layer_1_graph",
            field="name",
            claim_text="claim",
            evidence_kind="database_record",
            assertion_confidence="asserted",
            license="public domain",
        )
        for s in synth
    ]
    return graph_module._answer_tokens(
        audience_depth=depth,
        question="question",
        model_grounding=None,
        model_layout=NS(sentence_paragraph=[], heading_before={}),
        fallback_sentences=(f"{label_a} [8].", f"{label_b} [12]."),
        tail_sentences=(),
        tail_is_listing=False,
        citations=cites,
        synth_findings=synth,
        findings=findings,
        mentions=[],
        notes=[],
        condition_names=None,
    )


def test_one_page_with_two_names_stays_two_rows() -> None:
    """Card 104, case B, after the fix round (J-103-03 to J-103-05): two
    names for one page are two different cells, so both rows stay and
    neither name is hidden. Red before the fix round: one row, the second
    name gone."""
    tokens = _two_citations_one_page_tokens("BRCA1 DNA repair associated", "BRCA1", "researcher")
    rows = [t for t in tokens if t.kind == "table_row"]
    assert [t.cells for t in rows] == [
        ["BRCA1 DNA repair associated", "NCBIGene:672"],
        ["BRCA1", "NCBIGene:672"],
    ]
    assert [t.marker_ids for t in rows] == [["cq-g-8"], ["cq-g-12"]]


def test_the_plain_language_list_does_not_repeat_a_record() -> None:
    """Card 104: the Plain language list merges the same way."""
    tokens = _two_citations_one_page_tokens("BRCA1", "BRCA1", "plain_language")
    items = [t for t in tokens if t.kind == "list_item"]
    assert len(items) == 1, items
    assert items[0].marker_ids == ["cq-g-8", "cq-g-12"], items


@pytest.mark.asyncio
async def test_same_page_different_identifier_stays_two_rows(monkeypatch) -> None:
    """Two different records that share a page but differ in identifier."""
    rows = [
        _gene_row("https://www.ncbi.nlm.nih.gov/gene/672", "BRCA1", "NCBIGene:672"),
        _gene_row("https://www.ncbi.nlm.nih.gov/gene/672/", "BRCA1 copy", "NCBIGene:673"),
    ]
    tokens = _tokens(await _gene_answer(monkeypatch, "researcher", rows))
    ((_, table_rows),) = _tables(tokens)
    assert [t["cells"][1] for t in table_rows] == ["NCBIGene:672", "NCBIGene:673"]


# ---------------------------------------------------------------------------
# Cards 103 and 104 fix round (2026-10-08): a merge never loses anything a
# row showed, every citation number stays, and the numbers stay as develop.
# ---------------------------------------------------------------------------

_MODY = "MedGen:C0342276"
_NOT_PROVIDED = "MedGen:C3661900"
_TITLES = {_MODY: "Maturity-onset diabetes of the young", _NOT_PROVIDED: "not provided"}


def _direct_tokens(depth: str, records: list[dict], condition_names=None):
    """Straight through the table builder: one graph call per record, each
    its own citation. A record is `{cid, n, type, curie, url, fields,
    field, value}`; its sentence is `"<value> [n]."`."""
    from system_03_search_agent.contracts.events import CitationPayload
    from system_03_search_agent.harness.coordinator_worker import Finding
    from system_03_search_agent.synthesis.findings import SynthFinding

    findings = [
        Finding(
            call_id=r["cid"],
            tool="cypher_query",
            layer="layer_1_graph",
            source="structured_pass_through",
            structured_fields={
                "status": "ok",
                "row_count": 1,
                "total_available": 1,
                "truncated": False,
                "rows": [
                    {
                        "node_or_edge_type": r["type"],
                        "curie": r["curie"],
                        "fields": r["fields"],
                        "source_url": r["url"],
                        "graph_snapshot_version": "v1",
                    }
                ],
                "error": None,
            },
            extracted_entities=None,
            normalized_ids=None,
            evidence_summary=None,
        )
        for r in records
    ]
    synth = [
        SynthFinding(
            ref_index=r["n"],
            citation_id=r["cid"],
            layer="layer_1_graph",
            tool="cypher_query",
            field=r["field"],
            field_value=r["value"],
            source_url=r["url"],
            entity_type=r["type"],
            curie=r["curie"],
            call_id=r["cid"],
        )
        for r in records
    ]
    cites = [
        CitationPayload(
            citation_id=r["cid"],
            display_index=r["n"],
            source="graph",
            source_id=r["curie"] or "unknown",
            source_url=r["url"],
            layer="layer_1_graph",
            field=r["field"],
            claim_text="claim",
            evidence_kind="database_record",
            assertion_confidence="asserted",
            license="public domain",
        )
        for r in records
    ]
    return graph_module._answer_tokens(
        audience_depth=depth,
        question="question",
        model_grounding=None,
        model_layout=SimpleNamespace(sentence_paragraph=[], heading_before={}),
        fallback_sentences=tuple(f"{r['value']} [{r['n']}]." for r in records),
        tail_sentences=(),
        tail_is_listing=False,
        citations=cites,
        synth_findings=synth,
        findings=findings,
        mentions=[],
        notes=[],
        condition_names=condition_names,
    )


def _variant(cid: str, n: int, local_id: str, conditions: list[str], slash: bool = True) -> dict:
    url = f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{local_id}" + ("/" if slash else "")
    return {
        "cid": cid,
        "n": n,
        "type": "SequenceVariant",
        "curie": f"ClinVar:{local_id}",
        "url": url,
        "fields": {"name": f"variant ClinVar:{local_id}", "clinvar_condition_ids": conditions},
        "field": "name",
        "value": f"variant ClinVar:{local_id}",
    }


def _disease(cid: str, n: int, curie: str, name: str) -> dict:
    return {
        "cid": cid,
        "n": n,
        "type": "Disease",
        "curie": curie,
        "url": f"https://www.ncbi.nlm.nih.gov/medgen/{curie.split(':')[1]}",
        "fields": {"name": name},
        "field": "name",
        "value": name,
    }


def _rows_of(tokens, kind: str = "table_row"):
    return [t for t in tokens if t.kind == kind]


def test_a_merged_row_reads_its_citations_in_ascending_order() -> None:
    """J-103-04: one variant cited at 1 and 2, its disease at 3. Red before
    the fix round: the merged row's chips read [1][3][2]."""
    tokens = _direct_tokens(
        "researcher",
        [
            _variant("v-1", 1, "7", [_MODY]),
            _variant("v-2", 2, "7", [_MODY], slash=False),
            _disease("d-3", 3, _MODY, "Maturity-onset diabetes of the young"),
        ],
        _TITLES,
    )
    variant_rows = [t for t in _rows_of(tokens) if t.cells[1] == "ClinVar:7"]
    assert [t.cells for t in variant_rows] == [
        ["variant ClinVar:7", "ClinVar:7", "Maturity-onset diabetes of the young"]
    ]
    assert variant_rows[0].marker_ids == ["v-1", "v-2", "d-3"], variant_rows


def test_a_full_row_never_swallows_a_later_citation() -> None:
    """J-103-03: a variant linked to 22 cited diseases is cited a second
    time. Merging would need 23 chips on a row that holds 20, so the repeat
    stays its own row, as on develop. Red before the fix round: citation
    'v-24' reached no row at all."""
    conditions = [f"MedGen:C90000{index:02d}" for index in range(22)]
    titles = {curie: f"disease {index}" for index, curie in enumerate(conditions)}
    diseases = [
        _disease(f"d-{index + 2}", index + 2, curie, f"disease {index}")
        for index, curie in enumerate(conditions)
    ]
    tokens = _direct_tokens(
        "researcher",
        [
            _variant("v-1", 1, "9", conditions),
            *diseases,
            _variant("v-24", 24, "9", conditions, slash=False),
        ],
        titles,
    )
    reached = {marker for t in tokens for marker in t.marker_ids}
    assert "v-24" in reached, "citation 24 reaches no row"
    variant_rows = [t for t in _rows_of(tokens) if t.cells[1] == "ClinVar:9"]
    assert len(variant_rows) == 2, [t.marker_ids for t in variant_rows]
    assert all(len(t.marker_ids) <= 20 for t in tokens)


def test_a_merged_disease_cell_never_contradicts_its_chips() -> None:
    """A-103-02: one variant page reached twice, once folding only 'not
    provided', once folding a named disease. The two cells differ, so the
    rows stay two, each cell beside its own chips. Red before the fix
    round: one row reading 'None named' beside the disease's chip."""
    tokens = _direct_tokens(
        "researcher",
        [
            _variant("a-1", 1, "100", [_NOT_PROVIDED]),
            _variant("b-2", 2, "100", [_MODY], slash=False),
            _disease("d-3", 3, _MODY, "Maturity-onset diabetes of the young"),
        ],
        _TITLES,
    )
    variant_rows = [t for t in _rows_of(tokens) if t.cells[1] == "ClinVar:100"]
    assert [(t.cells[2], t.marker_ids) for t in variant_rows] == [
        ("None named: the ClinVar record says not provided", ["a-1"]),
        ("Maturity-onset diabetes of the young", ["b-2", "d-3"]),
    ], variant_rows


def test_a_merged_row_takes_the_disease_chip_of_the_row_that_named_it() -> None:
    """A-103-10: the first row links no condition (a blank cell), the
    repeat names one. The merged cell is recomputed from both rows' links
    and carries that disease's chip. Mutation: drop the disease-chip merge
    and 'd-3' is missing; red before the fix round: the cell stayed blank
    beside the disease's chip."""
    tokens = _direct_tokens(
        "researcher",
        [
            _variant("a-1", 1, "101", []),
            _variant("b-2", 2, "101", [_MODY], slash=False),
            _disease("d-3", 3, _MODY, "Maturity-onset diabetes of the young"),
        ],
        _TITLES,
    )
    variant_rows = [t for t in _rows_of(tokens) if t.cells[1] == "ClinVar:101"]
    assert [t.cells[2] for t in variant_rows] == ["Maturity-onset diabetes of the young"]
    assert variant_rows[0].marker_ids == ["a-1", "b-2", "d-3"], variant_rows


def _paper(cid: str, n: int, url: str, fields: dict) -> dict:
    return {
        "cid": cid,
        "n": n,
        "type": "Publication",
        "curie": "PMID:123",
        "url": url,
        "fields": {"title": "A paper", **fields},
        "field": "title",
        "value": "A paper",
    }


def test_a_merge_keeps_a_value_only_the_later_row_carried() -> None:
    """A-103-06: one paper reached twice, only the live row carrying its
    year. The merged row shows the year whichever row came first. Red
    before the fix round: with the graph row first the year was lost."""
    graph_row = _paper("c-1", 1, "https://pubmed.ncbi.nlm.nih.gov/123", {})
    live_row = _paper("c-2", 2, "https://pubmed.ncbi.nlm.nih.gov/123/", {"pdat": "2019 Jan 5"})
    for records in ([graph_row, live_row], [{**live_row, "n": 1}, {**graph_row, "n": 2}]):
        rows = _rows_of(_direct_tokens("researcher", records))
        assert [t.cells for t in rows] == [["A paper", "PMID:123", "2019"]], rows
        assert sorted(rows[0].marker_ids) == ["c-1", "c-2"]


def test_two_different_values_keep_two_rows() -> None:
    """J-103-03 to J-103-05: a merge never picks one of two shown values."""
    first = _paper("c-1", 1, "https://pubmed.ncbi.nlm.nih.gov/123", {"pdat": "2018"})
    second = _paper("c-2", 2, "https://pubmed.ncbi.nlm.nih.gov/123/", {"pdat": "2019"})
    rows = _rows_of(_direct_tokens("researcher", [first, second]))
    assert [t.cells[2] for t in rows] == ["2018", "2019"]


def _nameless(cid: str, n: int, name: str) -> dict:
    """A record with no identifier, cited through one shared page."""
    return {
        "cid": cid,
        "n": n,
        "type": "Gene Ontology term",
        "curie": "",
        "url": "https://www.ncbi.nlm.nih.gov/gene/7157",
        "fields": {"name": name},
        "field": "name",
        "value": name,
    }


@pytest.mark.parametrize("depth", ["researcher", "plain_language"])
def test_two_records_with_no_identifier_merge_only_on_the_same_name(depth: str) -> None:
    """J-103-06 (M6, M10), A-103-09: with no identifier, the name is the
    only thing that tells two records on one page apart. Different names
    stay two rows; the same name is one row with both citations, in the
    Researcher list as in the Plain language list. Mutation: let a blank
    identifier merge without comparing names, and 'second thing' is lost
    under 'first thing'."""
    different = _rows_of(
        _direct_tokens(depth, [_nameless("g-1", 1, "first thing"), _nameless("g-2", 2, "second thing")]),
        "list_item",
    )
    assert [t.cells for t in different] == [["first thing"], ["second thing"]], different
    same = _rows_of(
        _direct_tokens(depth, [_nameless("g-1", 1, "DNA repair"), _nameless("g-2", 2, "DNA repair")]),
        "list_item",
    )
    assert [(t.cells, t.marker_ids) for t in same] == [(["DNA repair"], ["g-1", "g-2"])], same


def test_a_group_of_only_placeholder_rows_gets_no_disease_column() -> None:
    """J-103-06 (M14): the reason alone never creates a mapping column."""
    tokens = _direct_tokens(
        "researcher",
        [_variant("a-1", 1, "1", [_NOT_PROVIDED]), _variant("b-2", 2, "2", [_NOT_PROVIDED])],
        _TITLES,
    )
    headers = [t.cells for t in tokens if t.kind == "table_header"]
    assert headers == [["Variant", "Identifier"]], headers


@pytest.mark.asyncio
async def test_the_command_line_prints_every_citation_of_a_merged_row(monkeypatch) -> None:
    """A-103-03: the command line prints each row's text, not its chips, so
    a merged row's text carries every grounded sentence and its number.
    Red before the fix round: only '[1]' was printed for the BRCA1 row.

    Build phase 8.7: the listing now arrives before the summary, and the
    command line holds it until the run's `done` so the summary prints
    above it. The run's whole write stream, its `done` included, is fed
    in, as the command line receives it."""
    import io

    from system_03_search_agent.adapters.cli.render import Renderer

    rows = [
        _gene_row("https://www.ncbi.nlm.nih.gov/gene/672", "BRCA1"),
        _gene_row("https://www.ncbi.nlm.nih.gov/gene/672/", "BRCA1"),
    ]
    result = await _gene_answer(monkeypatch, "researcher", rows)
    ((_, table_rows),) = _tables(_tokens(result))
    assert len(table_rows) == 1
    numbers = {
        e.payload["citation_id"]: e.payload["display_index"]
        for e in result["events"]
        if e.type == "citation"
    }
    out, err = io.StringIO(), io.StringIO()
    renderer = Renderer(out, err, operator=False)
    assert any(event.type == "done" for event in result["events"]), (
        "populate-check failed: the run sent no `done`, so the held listing "
        "would never print."
    )
    for event in result["events"]:
        if event.type in ("token", "citation", "done"):
            renderer.handle(event)
    printed = out.getvalue()
    # The summary prints above the listing, the reading order.
    assert printed.index("Found 1 gene record") < printed.index("Gene record NCBIGene:672 [1]"), (
        printed
    )
    for marker in table_rows[0]["marker_ids"]:
        assert f"[{numbers[marker]}]" in table_rows[0]["text"], table_rows[0]["text"]
        assert f"[{numbers[marker]}]" in printed, printed


async def _hnf1a_answer(monkeypatch, depth: str):
    async def _resolve(concept_ids):
        return {cid: _HNF1A_TITLES.get(cid) for cid in concept_ids}

    monkeypatch.setattr(graph_module, "resolve_concept_ids", _resolve)
    _install(monkeypatch, lambda lines: f"{lines[1]} [1].")
    rows = [_variant_row(curie, conds) for curie, conds in _HNF1A_VARIANTS]
    return await graph_module.write_node(_state(depth, rows=rows))


_SEVEN = "[1][2][3][4][5][6][7]"
# Read by running exactly these inputs against develop 2182aff3's source.
_DEVELOP_NUMBERS = {
    ("hnf1a", "researcher"): (
        f"Found 7 sequence variant records for BRCA1 {_SEVEN}, linked to 1 disease. ",
        "Based on 7 sources cited",
        7,
    ),
    ("hnf1a", "plain_language"): (
        f"I found 7 genetic variants related to BRCA1 {_SEVEN}, linked to 1 condition. ",
        "Based on 7 sources cited",
        7,
    ),
    ("case_a", "researcher"): (
        "Found 1 gene record for BRCA1: BRCA1 [1]. ",
        "Based on 1 source cited",
        1,
    ),
    ("case_a", "plain_language"): (
        "I found 1 gene related to BRCA1 [1]. ",
        "Based on 1 source cited",
        1,
    ),
    ("case_b", "researcher"): (
        "Found 1 gene record for BRCA1: BRCA1 DNA repair associated [1]. ",
        "Based on 1 source cited",
        1,
    ),
    ("case_b", "plain_language"): (
        "I found 1 gene related to BRCA1 [1]. ",
        "Based on 1 source cited",
        1,
    ),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("depth", ["researcher", "plain_language"])
async def test_the_stated_numbers_stay_as_on_develop(monkeypatch, depth: str) -> None:
    """The opening 'Found N' line, the trust line and the Sources page count
    for the diagnosis's cases, pinned to what develop 2182aff3 states for
    the same input (read by running this input against develop)."""
    hnf1a = await _hnf1a_answer(monkeypatch, depth)
    assert _numbers(hnf1a, _tokens(hnf1a)) == _DEVELOP_NUMBERS[("hnf1a", depth)]
    case_a = [
        _gene_row("https://www.ncbi.nlm.nih.gov/gene/672", "BRCA1"),
        _gene_row("https://www.ncbi.nlm.nih.gov/gene/672/", "BRCA1"),
    ]
    case_b = [
        _gene_row("https://www.ncbi.nlm.nih.gov/gene/672", "BRCA1 DNA repair associated"),
        _gene_row("https://www.ncbi.nlm.nih.gov/gene/672", "BRCA1"),
    ]
    for name, rows in (("case_a", case_a), ("case_b", case_b)):
        result = await _gene_answer(monkeypatch, depth, rows)
        assert _numbers(result, _tokens(result)) == _DEVELOP_NUMBERS[(name, depth)], name
