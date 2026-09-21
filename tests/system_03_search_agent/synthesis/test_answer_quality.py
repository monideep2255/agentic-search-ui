"""Answer quality fix (2026-09-14): the unit-level arms.

Measured before any change (`testing/Developer/reports/2026-09-14_answer_quality/
report.md`): the BRCA1 disease question's prompt listed the four diseases
LAST behind the gene symbol and five trials with nothing saying which
answered the question; four GCK variants were offered with a URL as their
claim value; and the Researcher prose that survived was one-record
restatements the list under it repeated.

Every control here has a populate-check and a mutation arm: the property is
asserted with the control, and again with the control patched out so the
defect comes back. An arm that cannot go red is not an arm.

Coverage statement (goal-contracts): these arms exercise a Layer 1 row whose
only clean field is a URL, two-call and three-call finding lists, contiguous
and gapped answer index sets, a restatement of a trial and of a variant, a
relating sentence, and summaries of one, four and seven records. They do not
exercise the live model or the live graph; the write-node arms in
`core/test_write_answer_quality.py` drive `write_node` itself.
"""

from __future__ import annotations

import hashlib

import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness.coordinator_worker import Finding
from system_03_search_agent.synthesis import answer_layout
from system_03_search_agent.synthesis import findings as findings_module
from system_03_search_agent.synthesis.answer_layout import (
    answer_summary_sentence,
    drop_record_restatements,
    is_record_restatement,
)
from system_03_search_agent.synthesis.findings import (
    SynthFinding,
    build_answer_context_directive,
    build_synth_findings,
    build_synth_messages,
    render_findings_block,
)
from system_03_search_agent.synthesis.grounding import (
    display_index_by_citation_id,
    run_grounding_pass,
)

# The real ClinVar row shape measured live on the GCK question: an intronic
# HGVS name that `_is_vocabulary_token_artifact` flags, as it flags the id and
# the source, so the upstream pick is the URL.
_INTRONIC_ROW = {
    "node_or_edge_type": "SequenceVariant",
    "curie": "ClinVar:1179956",
    "fields": {
        "name": "NM_000162.5(GCK):c.363+318G>A",
        "id": "ClinVar:1179956",
        "source": "ClinVar",
        "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/1179956",
    },
    "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/1179956",
    "vocabulary_artifact_fields": ["id", "name", "source"],
}


def _graph_finding(call_id: str, rows: list[dict]) -> Finding:
    return Finding(
        call_id=call_id,
        tool="cypher_query",
        layer="layer_1_graph",
        source="structured_pass_through",
        structured_fields={
            "status": "ok", "row_count": len(rows), "total_available": len(rows),
            "truncated": False, "rows": rows, "error": None,
        },
        extracted_entities=None, normalized_ids=None, evidence_summary=None,
    )


def _layer3_finding(call_id: str, tool: str, rows: list[dict]) -> Finding:
    return Finding(
        call_id=call_id,
        tool=tool,
        layer="layer_3_enrichment",
        source="structured_pass_through",
        structured_fields=graph_module._shaped("ok", rows, None),
        extracted_entities=None, normalized_ids=None, evidence_summary=None,
    )


def _disease_rows(count: int) -> list[dict]:
    return [
        {
            "node_or_edge_type": "Disease",
            "curie": f"MedGen:C{index}",
            "fields": {"name": f"disease name number {index}"},
            "source_url": f"https://www.ncbi.nlm.nih.gov/medgen/{index}",
            "vocabulary_artifact_fields": [],
        }
        for index in range(1, count + 1)
    ]


def _trial_rows(count: int) -> list[dict]:
    return [
        graph_module._pseudo_row(
            "Clinical trial",
            {"name": f"trial title number {index}", "nct_id": f"NCT0000000{index}"},
            f"https://clinicaltrials.gov/study/NCT0000000{index}",
        )
        for index in range(1, count + 1)
    ]


# ------------------------------------------------------------ the URL guard


def test_the_upstream_pick_is_still_the_url_for_the_intronic_row() -> None:
    """Populate-check for the guard below: the misfire this guard exists for
    is still live upstream. If this goes red, the guard has nothing to do and
    `_is_vocabulary_token_artifact` changed; re-measure before deleting."""
    field_name, value, _ = graph_module._pick_representative_field(_INTRONIC_ROW["fields"])
    assert field_name == "source_url" and str(value).startswith("https://"), (field_name, value)


def test_a_url_is_never_offered_to_the_model_as_a_claim_value() -> None:
    synth, _ = build_synth_findings(
        [_graph_finding("cq-1", [_INTRONIC_ROW])], graph_module._pick_representative_field
    )
    assert len(synth) == 1
    assert synth[0].curie_fallback and synth[0].field_value == "ClinVar:1179956", synth[0]
    block = render_findings_block(synth)
    assert "http" not in block.lower(), block
    assert block == "[1] SequenceVariant record ClinVar:1179956", block


def test_without_the_url_guard_the_url_reaches_the_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(findings_module, "_URL_VALUE", type("Never", (), {"match": staticmethod(lambda _v: None)})())
    synth, _ = build_synth_findings(
        [_graph_finding("cq-1", [_INTRONIC_ROW])], graph_module._pick_representative_field
    )
    assert "https://www.ncbi.nlm.nih.gov/clinvar/variation/1179956" in render_findings_block(synth), (
        "the mutation did not put the URL back; the guard arm could not have caught it"
    )


# ----------------------------------------------------- lead-call ordering


def _two_call_findings() -> list[Finding]:
    # Set 8's handoff order: the context call first, the graph call last.
    return [
        _layer3_finding("ct-1", "clinicaltrials_search", _trial_rows(2)),
        _graph_finding("cq-1", _disease_rows(3)),
    ]


def test_answer_findings_are_numbered_first_and_the_admitted_set_is_unchanged() -> None:
    plain, _ = build_synth_findings(_two_call_findings(), graph_module._pick_representative_field)
    led, _ = build_synth_findings(
        _two_call_findings(), graph_module._pick_representative_field, lead_call_ids=frozenset({"cq-1"})
    )
    assert [f.entity_type for f in plain][:2] == ["Clinical trial", "Clinical trial"], (
        "populate-check: without lead ids the handoff order stands"
    )
    assert [f.entity_type for f in led] == ["Disease", "Disease", "Disease", "Clinical trial", "Clinical trial"]
    assert [f.ref_index for f in led] == [1, 2, 3, 4, 5]
    assert [f.citation_id for f in led] == ["cq-1-1", "cq-1-2", "cq-1-3", "ct-1-4", "ct-1-5"]
    assert [f.call_id for f in led] == ["cq-1", "cq-1", "cq-1", "ct-1", "ct-1"]
    # Same set either way: ordering never changes which records are admitted.
    assert {f.source_url for f in plain} == {f.source_url for f in led}


def test_lead_ordering_never_changes_admission_under_the_cap() -> None:
    """With a cap of 3, set 8's order admits the two trials and one disease.
    Leading the graph call reorders the SAME three, it does not admit a
    different three; the source set is a property of admission alone."""
    plain, capped = build_synth_findings(
        _two_call_findings(), graph_module._pick_representative_field, max_findings=3
    )
    led, led_capped = build_synth_findings(
        _two_call_findings(), graph_module._pick_representative_field, max_findings=3,
        lead_call_ids=frozenset({"cq-1"}),
    )
    assert capped and led_capped
    assert {f.source_url for f in plain} == {f.source_url for f in led}
    assert [f.entity_type for f in led] == ["Disease", "Clinical trial", "Clinical trial"]


# ------------------------------------------------- the answer/context line


def _synth(count: int) -> list[SynthFinding]:
    return [
        SynthFinding(
            ref_index=index, citation_id=f"c-{index}", layer="layer_1_graph", tool="cypher_query",
            field="name", field_value=f"value {index}", source_url=f"https://www.ncbi.nlm.nih.gov/x/{index}",
            entity_type="Disease",
        )
        for index in range(1, count + 1)
    ]


def test_the_directive_names_answer_and_context_findings() -> None:
    line = build_answer_context_directive(_synth(6), [1, 2, 3])
    assert line.startswith("ANSWER FINDINGS: [1] to [3] "), line
    assert "CONTEXT FINDINGS: [4] to [6] " in line, line
    gapped = build_answer_context_directive(_synth(4), [1, 3])
    assert "ANSWER FINDINGS: [1], [3] " in gapped and "CONTEXT FINDINGS: [2], [4] " in gapped, gapped


def test_the_directive_is_empty_when_nothing_is_context_or_nothing_answers() -> None:
    assert build_answer_context_directive(_synth(3), [1, 2, 3]) == ""
    assert build_answer_context_directive(_synth(3), []) == ""


def test_the_line_sits_in_the_dynamic_suffix_and_the_prefix_is_byte_identical() -> None:
    with_line = build_synth_messages("Which diseases?", _synth(4), "plain_language", answer_ref_indices=[1, 2])
    without = build_synth_messages("Which diseases?", _synth(4), "plain_language")
    assert "ANSWER FINDINGS: [1] to [2]" in with_line[1]["content"]
    assert "ANSWER FINDINGS" not in without[1]["content"]
    prefix = lambda messages: hashlib.sha256(messages[0]["content"].encode()).hexdigest()
    assert prefix(with_line) == prefix(without)
    # Under the findings block and above the question, so it describes what
    # precedes it and never reads as part of the question's data.
    body = with_line[1]["content"]
    assert body.index("FINDINGS:\n") < body.index("ANSWER FINDINGS") < body.index("USER QUESTION")


# ------------------------------------------------------- restatement drop

TRIAL = SynthFinding(
    ref_index=1, citation_id="ct-1-1", layer="layer_3_enrichment", tool="clinicaltrials_search",
    field="name", field_value="A Study of LY2599506 in Type 2 Diabetes Mellitus",
    source_url="https://clinicaltrials.gov/study/NCT01029795", entity_type="Clinical trial",
)
VARIANT = SynthFinding(
    ref_index=2, citation_id="cq-1-2", layer="layer_1_graph", tool="cypher_query",
    field="name", field_value="NM_000162.5(GCK):c.415A>T (p.Met139Leu)",
    source_url="https://www.ncbi.nlm.nih.gov/clinvar/variation/1028584",
    entity_type="SequenceVariant", curie="ClinVar:1028584",
)
DISEASE = SynthFinding(
    ref_index=3, citation_id="cq-1-3", layer="layer_2_api", tool="ncbi_efetch",
    field="name", field_value="Familial cancer of breast",
    source_url="https://www.ncbi.nlm.nih.gov/medgen/C0346153", entity_type="Disease",
    curie="MedGen:C0346153", name_resolved=True,
)


@pytest.mark.parametrize(
    "sentence, cited, restates",
    [
        ("The clinical trial named A Study of LY2599506 in Type 2 Diabetes Mellitus [1].", [TRIAL], True),
        ("The variant ClinVar:1028584 is named NM_000162.5(GCK):c.415A>T (p.Met139Leu) [2].", [VARIANT], True),
        ("SequenceVariant ClinVar:1028584, name: NM_000162.5(GCK):c.415A>T (p.Met139Leu) [2].", [VARIANT], True),
        ("BRCA1 is associated with Familial cancer of breast [3].", [DISEASE], False),
        ("Disease name: Familial cancer of breast [3].", [DISEASE], True),
        ("The trial and the variant [1][2].", [TRIAL, VARIANT], False),
    ],
)
def test_a_restatement_is_one_record_and_nothing_else(sentence: str, cited, restates: bool) -> None:
    assert is_record_restatement(sentence, cited) is restates


def test_restatements_are_dropped_and_survivors_renumbered() -> None:
    findings = [VARIANT, DISEASE]
    narrative = (
        "SequenceVariant ClinVar:1028584, name: NM_000162.5(GCK):c.415A>T (p.Met139Leu) [2]. "
        "Which diseases are associated with BRCA1, Familial cancer of breast [3]."
    )
    grounded = run_grounding_pass(
        narrative, findings, core_ask_required=True, question="Which diseases are associated with BRCA1?"
    )
    assert len(grounded.claims) == 2, "populate-check: both sentences must ground first"
    assert grounded.sentences[0].endswith("[1]."), grounded.sentences
    filtered, dropped = drop_record_restatements(grounded, findings)
    assert dropped == 1
    assert [claim.finding.citation_id for claim in filtered.claims] == ["cq-1-3"]
    assert filtered.sentences == ("Which diseases are associated with BRCA1, Familial cancer of breast [1].",)
    assert filtered.sentence_origins == (1,)
    assert display_index_by_citation_id(filtered) == {"cq-1-3": 1}
    assert filtered.narrative == filtered.sentences[0]


def test_dropping_every_sentence_leaves_an_empty_unrefused_result() -> None:
    grounded = run_grounding_pass(
        "SequenceVariant ClinVar:1028584, name: NM_000162.5(GCK):c.415A>T (p.Met139Leu) [2].",
        [VARIANT, DISEASE], core_ask_required=True,
    )
    filtered, dropped = drop_record_restatements(grounded, [VARIANT, DISEASE])
    assert dropped == 1 and filtered.claims == [] and filtered.narrative == "" and not filtered.refused


def test_without_the_detector_nothing_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(answer_layout, "is_record_restatement", lambda *_a, **_k: False)
    grounded = run_grounding_pass(
        "SequenceVariant ClinVar:1028584, name: NM_000162.5(GCK):c.415A>T (p.Met139Leu) [2].",
        [VARIANT, DISEASE], core_ask_required=True,
    )
    filtered, dropped = drop_record_restatements(grounded, [VARIANT, DISEASE])
    assert dropped == 0 and filtered is grounded, (
        "the mutation did not disable the drop; the restatement arm could not have caught it"
    )


def test_a_hand_built_result_is_returned_untouched() -> None:
    grounded = run_grounding_pass("Disease name: Familial cancer of breast [3].", [DISEASE])
    bare = type(grounded)(narrative=grounded.narrative, claims=grounded.claims, stripped_count=0, refused=False)
    assert drop_record_restatements(bare, [DISEASE]) == (bare, 0)


# ----------------------------------------------------------- the summary


def _slots(*findings: SynthFinding) -> dict[str, int]:
    return {f.citation_id: index for index, f in enumerate(findings, start=1)}


def test_the_summary_names_a_few_records_inline_with_their_markers() -> None:
    four = _synth(4)
    text = answer_summary_sentence(four, _slots(*four), "BRCA1", None, lambda _f: None)
    assert text == (
        "Found 4 disease records for BRCA1: value 1 [1], value 2 [2], value 3 [3] and value 4 [4]."
    ), text


def test_the_summary_counts_many_records_with_the_total_and_every_marker() -> None:
    seven = _synth(7)
    text = answer_summary_sentence(seven, _slots(*seven), "GCK", 1333, lambda _f: None)
    assert text == "Found 7 disease records for GCK, of 1333 available [1][2][3][4][5][6][7].", text


def test_the_summary_counts_only_cited_records_and_is_none_when_none_is() -> None:
    four = _synth(4)
    slots = _slots(four[1], four[3])
    text = answer_summary_sentence(four, slots, "", None, lambda _f: None)
    assert text == "Found 2 disease records: value 2 [1] and value 4 [2].", text
    assert answer_summary_sentence(four, {}, "BRCA1", 10, lambda _f: None) is None


def test_the_summary_groups_mixed_record_types_and_a_single_record() -> None:
    text = answer_summary_sentence(
        [VARIANT, DISEASE, TRIAL], _slots(VARIANT, DISEASE, TRIAL), "GCK", None, lambda _f: None
    )
    assert text.startswith("Found 1 sequence variant record, 1 disease record and 1 clinical trial record for GCK: "), text
    assert text.endswith("NM_000162.5(GCK):c.415A>T (p.Met139Leu) [1], Familial cancer of breast [2] and A Study of LY2599506 in Type 2 Diabetes Mellitus [3].")


def test_the_summary_label_for_a_curie_fallback_row_is_the_records_name_never_the_url() -> None:
    synth, _ = build_synth_findings(
        [_graph_finding("cq-1", [_INTRONIC_ROW])], graph_module._pick_representative_field
    )
    text = answer_summary_sentence(synth, _slots(*synth), "GCK", None, lambda _f: _INTRONIC_ROW)
    assert text == "Found 1 sequence variant record for GCK: NM_000162.5(GCK):c.363+318G>A [1].", text


def test_a_list_label_prefers_a_resolved_title_over_the_rows_artifact_name() -> None:
    row = {"name": "MeSH", "id": "MedGen:C1"}
    unresolved = SynthFinding(
        ref_index=1, citation_id="cq-1-1", layer="layer_1_graph", tool="cypher_query",
        field="curie", field_value="MedGen:C1", source_url="https://www.ncbi.nlm.nih.gov/medgen/C1",
        entity_type="Disease", curie="MedGen:C1", curie_fallback=True, value_is_suspect=True,
    )
    resolved = SynthFinding(
        ref_index=1, citation_id="cq-1-1", layer="layer_2_api", tool="ncbi_efetch",
        field="name", field_value="Familial cancer of breast",
        source_url="https://www.ncbi.nlm.nih.gov/medgen/C1", entity_type="Disease",
        curie="MedGen:C1", name_resolved=True,
    )
    assert answer_layout.record_label(resolved, row) == "Familial cancer of breast"
    assert answer_layout.record_label(unresolved, row) == "MeSH", (
        "populate-check: with no resolved title the row's own name shows, as set 9 built it"
    )


# ------------------------------------------- the write-step timeout cause


_WORD_ASK = __import__("re").compile(r"about (\d+) words")


@pytest.mark.parametrize("depth, ceiling", [("researcher", 250)])
def test_the_depth_directive_asks_for_no_more_than_the_answer_keeps(depth: str, ceiling: int) -> None:
    """Regression for the write-step transient error (2026-09-14).

    Measured on develop: 3 of 25 Researcher runs died at the 45-second Synth
    step budget, and locally the first Synth reply ran 300 to 740 words for
    a 700-word ask while 160 to 230 survived the gate (set 9, F9-04). The
    cause is the ASK, so the ask is pinned: each depth names a word target
    no larger than what its answer keeps, and the Researcher directive tells
    the model the records are listed by the system rather than restated.
    Raising this ceiling is decision X8 territory (the step budget) and is
    not a test edit.

    `plain_language` LEFT THIS ARM ON 2026-09-21, by product-owner decision
    under item 11.31, and it was moved rather than dropped: the arm below
    pins what replaced the word cap. Recorded here because removing a depth
    from a regression's parameter list is exactly the shape of a weakened
    verify surface, and the difference is that the property this arm
    asserted for `plain_language`, that it names a word target at all, is
    now required to be FALSE. Its own arm asserts that, so the coverage did
    not shrink. The researcher half is untouched.
    """
    directive = findings_module._DEPTH_DIRECTIVES[depth]
    match = _WORD_ASK.search(directive)
    assert match, f"populate-check: the {depth} directive names no word target: {directive!r}"
    assert int(match.group(1)) <= ceiling, (depth, match.group(1))
    if depth == "researcher":
        assert "listed below your answer by the system" in directive
        assert "Do not restate the records one by one" in directive


def test_plain_language_is_bounded_by_shape_rather_than_by_a_word_count() -> None:
    """Item 11.31 (2026-09-21): the replacement for the removed word cap.

    The product owner removed the 120-word cap ("do not limit to 120 words
    or whatever, it must be easy to understand") and chose a shape bound
    over a bigger number. A paragraph count constrains neither which tokens
    may appear nor which findings are covered, which is the one thing
    Section 14.1's firewall lets a depth directive do. The hard backstops
    stay in code: the 4000-token synth ceiling and the 45-second step
    budget.

    Populate-check: each assertion names the exact substring it needs, so a
    directive rewritten to drop the property fails here rather than passing
    on an empty search.
    """
    directive = findings_module._DEPTH_DIRECTIVES["plain_language"]

    assert not _WORD_ASK.search(directive), (
        "plain_language must not name a word target; the cap was removed by "
        f"product decision on 2026-09-21: {directive!r}"
    )
    assert "paragraphs of three to five sentences" in directive, (
        f"populate-check: the shape bound is missing: {directive!r}"
    )
    assert "as many paragraphs as the findings support" in directive, (
        f"populate-check: length must scale with the findings: {directive!r}"
    )


def test_plain_language_keeps_every_sentence_sourced_and_asks_for_no_paraphrase() -> None:
    """Item 11.31: the two constraints 11.31 may not relax, pinned.

    The product owner's words on 2026-09-21: "Everything has to have a
    source. The synthesis can be in simple terms". So plain language gets
    longer and simpler and STILL cites every sentence.

    The second half is the one a later reader is most likely to undo,
    because "quote it exactly rather than rewording it" reads like a
    style preference and is not. `grounding.ground_claim` accepts a claim
    only on contiguous containment, so against a long free-text value only
    a verbatim excerpt survives and a reworded one is stripped. A directive
    that invites rewording would make this depth refuse, which is exactly
    how version 1 of it failed.
    """
    directive = findings_module._DEPTH_DIRECTIVES["plain_language"]

    assert "must restate a finding and end with that finding's marker" in directive, (
        f"populate-check: cite-or-refuse is not stated: {directive!r}"
    )
    assert "quoting it exactly rather than rewording it" in directive, (
        f"populate-check: the no-paraphrase instruction is missing, and "
        f"without it the explanation is stripped by the gate: {directive!r}"
    )
    # The firewall: a depth directive may never constrain which tokens may
    # appear. Version 1 did ("do not print CURIEs") and made the depth
    # refuse outright, because a Layer 1 finding's value IS the identifier.
    for banned in ("do not print", "do not state the identifier", "avoid identifiers"):
        assert banned not in directive.lower(), (
            f"plain_language must not constrain which tokens may appear "
            f"({banned!r}); that is Section 14.1's firewall and version 1's "
            f"recorded failure: {directive!r}"
        )


def test_the_two_depths_ask_for_materially_different_shapes() -> None:
    """Item 11.31's whole point: the modes must not read alike.

    Measured live on develop at `46fff40` before this change, at both
    depths for two questions: the record dump was 66 rows for BRCA1 and
    about 92 for HNF1A and IDENTICAL across depths, against 89 to 164 words
    of prose. The part that did not differ was most of the page, so the
    difference that did exist was swamped.

    Removing the records from plain language was rejected: they are the
    evidence trail, and the product owner asked for plain language to stay
    grounded in sources. So the divergence has to come from the prose, and
    this arm pins that the two directives ask for structurally different
    prose rather than the same prose at two lengths.
    """
    plain = findings_module._DEPTH_DIRECTIVES["plain_language"]
    researcher = findings_module._DEPTH_DIRECTIVES["researcher"]

    # Researcher synthesises ACROSS records under headings; plain language
    # walks them one at a time with no headings. Opposite instructions, not
    # two dial settings.
    assert "Do not restate the records one by one" in researcher
    assert "give each finding its own sentence" in plain

    assert "'## Topic'" in researcher, (
        f"populate-check: researcher's heading structure is missing: {researcher!r}"
    )
    assert "No headings, no lists, no tables." in plain, (
        f"populate-check: plain language must forbid headings: {plain!r}"
    )
