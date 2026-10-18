"""Item 11.31 (2026-09-21): the explanatory finding, and why it exists.

`_pick_representative_field` returns one field per row and prefers `name`,
which is right for identifying a record and is why a gene row reached the
model as "gene symbol: BRCA1" and nothing else. NCBI's own plain-English
Gene ESummary `summary` field was retrieved and then discarded before
synthesis.

That mattered more than it looks, and the measurement is the reason this
module exists rather than a style preference. `grounding.ground_claim`
accepts a claim only on contiguous containment. For a short value the
`b in a` direction does the work, so a sentence can wrap the value in
ordinary English. For a long free-text value the only remaining direction
is `a in b`, a verbatim excerpt. So against long source text the gate
permits quoting and forbids explaining: a faithful paraphrase using only
the source's own words, merely reordered, is stripped. Three successive
rewrites of the plain-language depth directive failed on that before the
cause was located.

The fix is `attack-the-constraint`'s, applied to the assembly step rather
than to the model: change the input. Retrieve source text that is already
plain, and quoting it verbatim is both grounded and readable.

Coverage statement (goal-contracts): these arms exercise a row whose
explanatory field is present and long, present and too short, absent,
non-string, and identical to the field the picker already chose. They
exercise the cap and the dedup interaction. They do NOT exercise the live
model, the live NCBI API or the grounding pass itself; the retrieval half
is covered in `tests/system_03_search_agent/tools/test_ncbi_eutils_actions.py`
and the gate's behaviour in `test_pubmed_abstract_grounding.py`.

Every control below has a populate-check, and the mutation arms assert the
defect returns when the control is removed. An arm that cannot go red is
not an arm.

Depends on:
    - system_03_search_agent.synthesis.findings (build_synth_findings,
      explanatory_value_for_row, _MIN_EXPLANATORY_CHARS)
    - system_03_search_agent.harness.coordinator_worker (Finding)
"""

from __future__ import annotations

from typing import Any

from system_03_search_agent.harness.coordinator_worker import Finding
from system_03_search_agent.synthesis.findings import (
    _MIN_EXPLANATORY_CHARS,
    build_synth_findings,
    explanatory_value_for_row,
)

_SOURCE_URL = "https://www.ncbi.nlm.nih.gov/gene/672"
_CURIE = "NCBIGene:672"

# The real value, retrieved live from NCBI Gene ESummary for gene id 672 on
# 2026-09-21. Kept verbatim rather than paraphrased, because the whole point
# of this feature is that only verbatim source text survives the gate.
_REAL_SUMMARY = (
    "This gene encodes a 190 kD nuclear phosphoprotein that plays a role in "
    "maintaining genomic stability, and it also acts as a tumor suppressor."
)


def _stub(field_name: str, field_value: Any) -> Any:
    """A `pick_representative_field` stand-in returning a fixed tuple.

    Accepts and ignores `**kwargs` so it tolerates
    `apply_vocabulary_artifact_check`, the same injection pattern the
    neighbouring finding tests already use.
    """

    def _pick(_fields: dict[str, Any], **_kwargs: Any) -> tuple[str, Any, bool]:
        return field_name, field_value, False

    return _pick


def _row(fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "curie": _CURIE,
        "source_url": _SOURCE_URL,
        "node_or_edge_type": "Gene",
        "fields": fields,
    }


def _finding_with_row(row: dict[str, Any]) -> Finding:
    return Finding(
        call_id="call-1",
        tool="ncbi_efetch",
        layer="layer_2_api",
        source="structured_pass_through",
        structured_fields={"status": "ok", "row_count": 1, "rows": [row]},
        extracted_entities=None,
        normalized_ids=None,
        evidence_summary=None,
    )


class TestExplanatoryValueForRow:
    def test_a_long_summary_is_returned(self) -> None:
        got = explanatory_value_for_row(
            _row({"name": "BRCA1", "summary": _REAL_SUMMARY}), "name"
        )
        assert got == ("summary", _REAL_SUMMARY), (
            "populate-check: the live-probed gene summary must be offered as "
            "an explanatory value"
        )

    def test_a_short_summary_is_rejected(self) -> None:
        """Below the bound a "summary" is a label, not an explanation, and a
        second finding for it would restate the first."""
        short = "x" * (_MIN_EXPLANATORY_CHARS - 1)
        assert explanatory_value_for_row(_row({"name": "BRCA1", "summary": short}), "name") is None

    def test_the_bound_is_inclusive_at_its_own_edge(self) -> None:
        """The boundary itself, so a later reader changing `<` to `<=` has an
        arm that notices."""
        edge = "x" * _MIN_EXPLANATORY_CHARS
        got = explanatory_value_for_row(_row({"name": "BRCA1", "summary": edge}), "name")
        assert got == ("summary", edge)

    def test_the_field_the_picker_already_chose_is_not_repeated(self) -> None:
        """Otherwise the row ships the same claim twice under two markers."""
        assert explanatory_value_for_row(_row({"summary": _REAL_SUMMARY}), "summary") is None

    def test_a_row_with_no_explanatory_field_yields_nothing(self) -> None:
        assert explanatory_value_for_row(_row({"name": "BRCA1"}), "name") is None

    def test_a_non_string_value_is_ignored(self) -> None:
        """Finding J-10 and F-2.2-R-06: a JSON null, a bool and a container
        all reach this dict, and a truthiness test alone ships them."""
        for value in (None, True, 12345, [{"a": 1}], {"a": 1}):
            assert explanatory_value_for_row(
                _row({"name": "BRCA1", "summary": value}), "name"
            ) is None, f"a {type(value).__name__} value must never be explanatory"


class TestBuildSynthFindingsEmitsTheExplanatoryFinding:
    def test_a_gene_row_yields_both_the_symbol_and_the_summary(self) -> None:
        findings, _capped = build_synth_findings(
            [_finding_with_row(_row({"name": "BRCA1", "summary": _REAL_SUMMARY}))],
            _stub("name", "BRCA1"),
        )
        assert len(findings) == 2, (
            "populate-check: the row must produce its identifying finding AND "
            f"its explanatory one, got {[(f.field, f.field_value) for f in findings]}"
        )
        assert (findings[0].field, findings[0].field_value) == ("name", "BRCA1")
        assert (findings[1].field, findings[1].field_value) == ("summary", _REAL_SUMMARY)

    def test_the_explanatory_finding_is_numbered_next_to_its_own_row(self) -> None:
        """Adjacent, so the two read together and the prompt slice cannot cut
        the explanation off the end."""
        findings, _capped = build_synth_findings(
            [_finding_with_row(_row({"name": "BRCA1", "summary": _REAL_SUMMARY}))],
            _stub("name", "BRCA1"),
        )
        assert [f.ref_index for f in findings] == [1, 2]

    def test_it_carries_the_rows_own_provenance(self) -> None:
        """A citation with no provenance is the one thing this product may
        never emit, so the second finding must be as citeable as the first."""
        findings, _capped = build_synth_findings(
            [_finding_with_row(_row({"name": "BRCA1", "summary": _REAL_SUMMARY}))],
            _stub("name", "BRCA1"),
        )
        explanatory = findings[1]
        assert explanatory.source_url == _SOURCE_URL
        assert explanatory.curie == _CURIE
        assert explanatory.entity_type == "Gene"
        assert explanatory.layer == "layer_2_api"
        assert explanatory.citation_id, "an uncitable finding must never ship"

    def test_it_is_never_flagged_suspect_or_a_curie_fallback(self) -> None:
        findings, _capped = build_synth_findings(
            [_finding_with_row(_row({"name": "BRCA1", "summary": _REAL_SUMMARY}))],
            _stub("name", "BRCA1"),
        )
        assert findings[1].value_is_suspect is False
        assert findings[1].curie_fallback is False

    def test_a_row_without_a_summary_still_yields_exactly_one_finding(self) -> None:
        """The mutation arm for the feature as a whole: with the explanatory
        field absent the old single-finding behaviour must be unchanged."""
        findings, _capped = build_synth_findings(
            [_finding_with_row(_row({"name": "BRCA1"}))], _stub("name", "BRCA1")
        )
        assert len(findings) == 1
        assert findings[0].field == "name"

    def test_the_cap_still_binds(self) -> None:
        """An explanatory finding may never smuggle a row past a bound: a
        record that did not fit still does not fit."""
        findings, capped = build_synth_findings(
            [_finding_with_row(_row({"name": "BRCA1", "summary": _REAL_SUMMARY}))],
            _stub("name", "BRCA1"),
            max_findings=1,
        )
        assert len(findings) == 1, "the cap must bound the explanatory finding too"
        assert capped is True, (
            "populate-check: dropping a citable value must be disclosed, or "
            "the answer under-reports without saying so"
        )

    def test_the_same_summary_on_two_rows_of_one_record_is_not_duplicated(self) -> None:
        """Dedup is keyed on (source_url, field, value), so one record
        returned twice contributes its explanation once."""
        row = _row({"name": "BRCA1", "summary": _REAL_SUMMARY})
        findings, _capped = build_synth_findings(
            [_finding_with_row(row), _finding_with_row(row)], _stub("name", "BRCA1")
        )
        summaries = [f for f in findings if f.field == "summary"]
        assert len(summaries) == 1, (
            f"the explanation must appear once, got {len(summaries)}"
        )


class TestTheFeatureIsDepthIndependent:
    def test_the_same_findings_are_built_regardless_of_audience_depth(self) -> None:
        """Section 14.1's firewall, pinned.

        A depth directive may change register, ordering and how much is
        explained. It may NEVER change which findings were retrieved or
        which claims can be made. `build_synth_findings` takes no depth
        argument at all, which is what makes that true by construction
        rather than by discipline, and this arm fails loudly if someone
        adds one.
        """
        import inspect

        params = inspect.signature(build_synth_findings).parameters
        offenders = [p for p in params if "depth" in p.lower() or "audience" in p.lower()]
        assert not offenders, (
            f"build_synth_findings must not take a depth argument, found "
            f"{offenders}; that would put the answer set under a "
            f"presentation control, which is Section 14.1's firewall and a "
            f"breach `_DEPTH_DIRECTIVES`' own history records twice"
        )


class TestPlanGeneSummary:
    """The retrieval half: the call that fetches the explanatory text.

    Found live rather than by reading: after the allowlist and the finding
    were both in place and green, a real run at both depths still carried no
    gene summary, because `_summary_call` was wired only for `clinvar` and
    `omim` and NOTHING ever asked NCBI for a gene ESummary. The feature was
    correct and unreachable. That is why these arms exist and why they check
    the planner rather than the constant.
    """

    def test_a_resolved_gene_curie_plans_one_summary_call(self) -> None:
        from system_03_search_agent.core import breadth_plan

        planned = breadth_plan.plan_gene_summary("NCBIGene:672")
        assert len(planned) == 1, (
            f"populate-check: expected exactly one call, got {planned}"
        )
        call = planned[0]
        assert call.purpose == "gene_summary"
        payload = call.tool_input.model_dump()
        assert payload["action"] == "summary"
        assert payload["db"] == "gene"
        assert payload["ids"] == ["672"], (
            "the uid must come from the CURIE itself, never from a second "
            "lookup that could resolve a different gene"
        )

    def test_the_curie_prefix_is_matched_case_insensitively(self) -> None:
        from system_03_search_agent.core import breadth_plan

        assert breadth_plan.plan_gene_summary("ncbigene:7157")[0].purpose == "gene_summary"

    def test_anything_that_is_not_a_gene_uid_plans_nothing(self) -> None:
        """Planning nothing is the planner's own contract for an unusable
        input, matching `plan_first_stage`, rather than raising."""
        from system_03_search_agent.core import breadth_plan

        for bad in (
            None,
            672,
            "MedGen:C0346153",
            "NCBIGene:",
            "NCBIGene:0",
            "NCBIGene:-1",
            "NCBIGene:672abc",
        ):
            assert breadth_plan.plan_gene_summary(bad) == (), (
                f"{bad!r} must plan no call, or the product asks NCBI about a "
                f"gene the question never resolved"
            )
