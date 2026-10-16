"""Card 111: a summary never ends on one title said twice.

The owner's words: "A summary never ends on a sentence made only of record
titles the answer already lists, such as 'Marfan syndrome and Marfan
syndrome.'" The fix round (2026-10-15) narrowed the rule to that case: a
sentence is left out only when it repeats ONE title or name, cited to two or
more different records, and every record it cites is in the listing shown.
The check reads structure only.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import harness as harness_module
from tests.system_03_search_agent.core import test_write_completeness as completeness
from tests.system_03_search_agent.core.test_write_completeness import (  # noqa: F401
    _env,
    _fake_response,
    _tail_cannot_ground,
    _write_state,
)

LABELS = {
    1: "Marfan syndrome",
    2: "Marfan syndrome",
    3: "Loeys-Dietz syndrome",
    4: "What Is Marfan Syndrome?",
    5: "What Is Marfan Syndrome?",
    6: "BRCA1-BARD1 promotes RAD51-mediated homologous DNA pairing",
}
LISTED = frozenset({1, 2, 3, 4, 5, 6})


@pytest.mark.parametrize(
    ("sentence", "listed", "expected"),
    [
        # The case reported: one title, two records, both in the listing.
        ("Marfan syndrome [1] and Marfan syndrome [2].", LISTED, True),
        ("Marfan syndrome [1], Marfan syndrome [2].", LISTED, True),
        ("marfan syndrome [1] and Marfan syndrome [2]!", LISTED, True),
        # A-111-04: a marker before or after "?" or "!" is handled alike.
        ("What Is Marfan Syndrome? [4] and What Is Marfan Syndrome? [5].", LISTED, True),
        ("What Is Marfan Syndrome [4] and What Is Marfan Syndrome [5]?", LISTED, True),
        # A-111-01: a cited list of DISTINCT names is the answer to "which",
        # never dropped.
        ("Marfan syndrome [1] and Loeys-Dietz syndrome [3].", LISTED, False),
        ("Marfan syndrome [1], Loeys-Dietz syndrome [3] and Marfan syndrome [2].", LISTED, False),
        # A-111-02: a single title, even one stating a finding, is kept.
        ("BRCA1-BARD1 promotes RAD51-mediated homologous DNA pairing [6].", LISTED, False),
        ("Marfan syndrome [1].", LISTED, False),
        ("Marfan syndrome [1] and Marfan syndrome [1].", LISTED, False),
        # J-111-01: dropped only when every cited record is in the listing.
        ("Marfan syndrome [1] and Marfan syndrome [2].", frozenset({1}), False),
        ("Marfan syndrome [1] and Marfan syndrome [2].", frozenset(), False),
        # Says something beyond the labels: never matched.
        ("Marfan syndrome [1] is seen with Marfan syndrome [2].", LISTED, False),
        ("Marfan syndrome [1] and Marfan syndrome [2] are recent reviews.", LISTED, False),
        ("Its name is Marfan syndrome [1] and Marfan syndrome [2].", LISTED, False),
        # A piece that is not the cited record's label, a marker citing no
        # labelled record, and a sentence with no marker.
        ("Marfan syndrome [1] and Marfan syndrome [3].", LISTED, False),
        ("Marfan syndrome [1] and Marfan syndrome [9].", LISTED | {9}, False),
        ("Marfan syndrome and Marfan syndrome.", LISTED, False),
    ],
)
def test_label_only_is_decided_from_structure(
    sentence: str, listed: frozenset[int], expected: bool
) -> None:
    assert graph_module._is_label_only_sentence(sentence, LABELS, listed) is expected


def test_the_label_fields_are_the_listing_rows_own_list() -> None:
    """J-111-03: one list of label fields, the one a listing row's label is
    chosen from, not a second copy in graph.py.

    Mutation that turns this red: give graph.py its own `LABEL_FIELDS`."""
    from system_03_search_agent.synthesis import answer_layout

    assert graph_module.LABEL_FIELDS is answer_layout.LABEL_FIELDS
    assert graph_module.LABEL_FIELDS == answer_layout._LABEL_FIELDS


def _marfan_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Records 1 and 2 share one title; the rest are distinct."""
    rows = [
        {
            "node_or_edge_type": "Disease",
            "curie": f"MedGen:C{index}",
            "fields": {"name": "Marfan syndrome" if index <= 2 else f"disease name number {index}"},
            "source_url": f"https://www.ncbi.nlm.nih.gov/medgen/{index}",
            "graph_snapshot_version": "v1",
        }
        for index in range(1, 6)
    ]
    monkeypatch.setattr(completeness, "_ROWS", rows)


def _writer_says(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    async def _dispatch(*_args: object, **_kwargs: object):
        return _fake_response(text)

    monkeypatch.setattr(harness_module.litellm, "acompletion", AsyncMock(side_effect=_dispatch))
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )


def _prose_claims(events: list) -> list[str]:
    texts: list[str] = []
    for event in events:
        if event.type != "token":
            continue
        payload = event.payload
        if payload.get("kind") == "heading":
            break
        if payload.get("kind") == "claim":
            texts.append(payload["text"])
    return texts


WRITER = (
    "NCBIGene:672 is associated with disease name number 3 [3]. "
    "Marfan syndrome [1] and Marfan syndrome [2]."
)


@pytest.mark.asyncio
async def test_a_summary_does_not_end_on_one_title_said_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sentence that only repeats one listed title, cited to two records,
    is left out of the prose; the sentence that says something stays.

    Mutation that turns this red: make `_is_label_only_sentence` return False
    for a sentence whose pieces all match (the check then never drops)."""
    _marfan_rows(monkeypatch)
    _writer_says(monkeypatch, WRITER)

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))
    claims = _prose_claims(result["events"])

    assert any("associated with disease name number 3" in claim.lower() for claim in claims), claims
    assert not any(claim.strip().startswith("Marfan syndrome [1] and") for claim in claims), claims


@pytest.mark.asyncio
async def test_with_no_listing_the_repeated_title_stays(monkeypatch: pytest.MonkeyPatch) -> None:
    """J-111-01: the listing grounds nothing, so the sentence is the only
    place in the visible answer that names those records. It stays.

    Mutation that turns this red: pass every marker as listed (ignore the
    listing)."""
    _marfan_rows(monkeypatch)
    _writer_says(monkeypatch, WRITER)
    _tail_cannot_ground(monkeypatch)

    result = await graph_module.write_node(_write_state(audience_depth="plain_language"))
    claims = _prose_claims(result["events"])

    assert any(claim.startswith("Marfan syndrome [") for claim in claims), claims


@pytest.mark.asyncio
async def test_a_cited_list_of_distinct_names_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    """A-111-01: the names are the answer to "which diseases".

    Mutation that turns this red: drop the "one label" test in
    `_is_label_only_sentence`."""
    _marfan_rows(monkeypatch)
    _writer_says(
        monkeypatch,
        "NCBIGene:672 is associated with disease name number 3 [3]. "
        "Marfan syndrome [1], disease name number 4 [4] and disease name number 5 [5].",
    )

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))
    claims = _prose_claims(result["events"])

    assert any(
        claim.lower().startswith("marfan syndrome [1], disease name number 4") for claim in claims
    ), claims


def test_a_single_title_that_states_a_finding_is_kept() -> None:
    """A-111-02: one paper title with one marker is a claim, never dropped,
    while the same title cited to two records is.

    Mutation that turns this red: allow a single marker in
    `_is_label_only_sentence`."""
    title = "Targeting GPX4-mediated ferroptosis protection sensitizes BRCA1-deficient cells"
    citations = [
        SimpleNamespace(display_index=index, citation_id=f"c{index}") for index in (1, 2)
    ]
    findings = [
        SimpleNamespace(citation_id=f"c{index}", field="title", field_value=title)
        for index in (1, 2)
    ]
    sentences = [f"{title} [1].", f"{title} [1] and {title} [2]."]
    listing = [f"{title} [1].", f"{title} [2]."]

    kept = graph_module._label_only_positions(sentences, citations, findings, listing)

    assert kept == {1}


@pytest.mark.asyncio
async def test_a_summary_made_only_of_one_repeated_title_is_kept_not_emptied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A-111-03, as designed: when every model sentence would be left out and
    no lead is picked, all of them stay and the summary prints the repeat
    after the count line. The card said "never"; this is the one case where
    the writer's whole prose is that sentence, so dropping it would print
    nothing from the writer.

    Mutation that turns this red: change the keep-all guard's `>=` to `>`."""
    _marfan_rows(monkeypatch)
    _writer_says(monkeypatch, "Marfan syndrome [1] and Marfan syndrome [2].")

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))
    claims = _prose_claims(result["events"])

    assert any(claim.startswith("Marfan syndrome [1] and") for claim in claims), claims


@pytest.mark.asyncio
async def test_a_sentence_the_prose_leaves_out_is_never_a_lead_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A-110-02: the sentence card 111 leaves out of the prose is not offered
    to the lead decision, so it cannot open the answer either.

    Mutation that turns this red: pass no `skip` to `_lead_sentence_choice`."""
    from tests.system_03_search_agent.core.test_write_answers_sooner import _jev

    monkeypatch.setenv("CLASSIFIER_PROVIDER", "jev")
    _marfan_rows(monkeypatch)
    _writer_says(
        monkeypatch,
        "Marfan syndrome [1] and Marfan syndrome [2]. "
        "NCBIGene:672 is associated with disease name number 3 [3].",
    )
    asked = _jev(monkeypatch, choice="first")

    result = await graph_module.write_node(_write_state(audience_depth="researcher"))
    claims = _prose_claims(result["events"])

    state = str(asked[0]["state"])
    assert "Sentence 1: NCBIGene:672 is associated" in state, state
    assert "Sentence 2" not in state, state
    assert claims[0].startswith("NCBIGene:672 is associated"), claims
