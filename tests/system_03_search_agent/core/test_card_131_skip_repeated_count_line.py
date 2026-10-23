"""Card 131 part 2 (owner, 2026-10-22): the count line is skipped when the
opening sentence cites every record it cites.

Structural only: the tests compare markers, never words. Every record is
neutral and built here, never a test question.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.synthesis.answer_layout import GroundingInput
from system_03_search_agent.synthesis.findings import SynthFinding
from system_03_search_agent.synthesis.grounding import GroundingResult

_LEAD = "Four widgets belong to the set [1][2][3][4]."
_COUNT = "I found 4 conditions related to X [1][2][3][4]."


def _finding(ref: int) -> SynthFinding:
    return SynthFinding(
        ref_index=ref,
        citation_id=f"c{ref}",
        layer="layer_1_graph",
        tool="cypher_query",
        field="name",
        field_value=f"Widget {ref}",
        source_url=f"https://www.ncbi.nlm.nih.gov/medgen/{ref}",
        entity_type="Disease",
    )


def _summary_text(
    count_line: str,
    *,
    lead: str | None = _LEAD,
    extra: bool = False,
    depth: str = "plain_language",
) -> str:
    findings = [_finding(n) for n in range(1, 5)]
    sentences = (lead,) if lead is not None else ()
    grounding = GroundingResult(
        narrative=" ".join(sentences),
        claims=[],
        stripped_count=0,
        refused=False,
        sentences=sentences,
        sentence_origins=tuple(range(len(sentences))),
    )
    citations = [
        SimpleNamespace(display_index=f.ref_index, citation_id=f.citation_id) for f in findings
    ]
    parts = graph_module._answer_parts(
        audience_depth=depth,
        question="q",
        model_grounding=grounding,
        model_layout=GroundingInput(
            narrative="", sentence_paragraph=(0,) * len(sentences), heading_before={}
        ),
        fallback_sentences=(),
        tail_sentences=(),
        tail_is_listing=False,
        citations=citations,
        synth_findings=findings,
        findings=[],
        mentions=[],
        notes=[],
        summary_sentence=count_line,
        lead_index=0 if lead is not None else None,
        summary_has_extra_clause=extra,
    )
    return " ".join(t.text for t in parts.summary)


@pytest.mark.parametrize("depth", ["plain_language", "researcher"])
def test_count_line_is_skipped_when_the_lead_cites_every_record(depth: str) -> None:
    text = _summary_text(_COUNT, depth=depth)
    assert "Four widgets" in text
    assert "I found 4" not in text


@pytest.mark.parametrize("depth", ["plain_language", "researcher"])
def test_count_line_stays_when_the_lead_cites_only_some_records(depth: str) -> None:
    text = _summary_text(_COUNT, lead="Two of them [1][2].", depth=depth)
    assert "Two of them" in text
    assert "I found 4" in text


def test_count_line_stays_when_it_has_an_extra_clause() -> None:
    line = "I found 4 conditions related to X, out of 90 available [1][2][3][4]."
    assert "out of 90" in _summary_text(line, extra=True)


def test_count_line_stays_when_it_has_no_markers_to_compare() -> None:
    assert "I found 4" in _summary_text("I found 4 conditions related to X.")


def test_count_line_opens_as_before_when_no_lead_is_picked() -> None:
    assert _summary_text(_COUNT, lead=None).startswith("I found 4")
