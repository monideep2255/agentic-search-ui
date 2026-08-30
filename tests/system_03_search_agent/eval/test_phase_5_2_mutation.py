"""Mutation coverage for build phase 5.2's grading arms: can each arm FAIL?

Moved here from build phase 5.1 on 2026-08-30, unchanged.

## Every case here passes, and the harness is still wrong

That is not a contradiction, it is the central finding of build phase 5.1's
review. A mutation harness proves an arm is FALSIFIABLE. It cannot prove the
arm measures the RIGHT property.

Both review rounds measured, against the real shipped dataset, that 34 of 50
rows pass a wholly fabricated answer and that refusing every question scores
pass@3 and pass^3 of 100 percent. No arm below noticed either.

Read `tracker/phase_5.2.md` before trusting a green run of this file.

## Coverage: computed, never claimed

`test_coverage_claim_is_computed_not_asserted` derives which arms have a
mutation case and requires the difference to equal `_EXEMPT_ARMS` exactly.
"""


from __future__ import annotations

import pytest
from _pytest.outcomes import Failed

from system_03_search_agent.eval import (
    aggregate,
    coverage,
    hard_fails,
    replay,
    rubric_grader,
    trace_source,
)
from tests.system_03_search_agent.eval import test_phase_5_2_premise as gate

# An arm "goes red" if it raises an assertion failure, or if a
# `pytest.raises` block it depends on finds no exception (which pytest
# reports as `Failed`). Both are the arm doing its job.
_RED = (AssertionError, Failed)

# Arms with no mutation case, each with the reason it has none. This mapping
# is enforced by the computed coverage check at the bottom of the file, so it
# cannot silently disagree with what is actually here.
_EXEMPT_ARMS: dict[str, str] = {
    "p3d": "populate-check: its whole job is to fail when the subject does "
    "nothing, so 'mutate the subject to do nothing' is what it already asserts",
}


def _must_go_red(arm, *args, **kwargs) -> None:
    """Call a premise arm and require it to fail.

    The failure mode this guards against is subtle: an arm can also fail for
    an UNRELATED reason (an import error, a TypeError from a bad patch), and
    counting that as success would certify a mutation that never reached the
    control. So only assertion-shaped failures count, and anything else
    propagates.
    """
    try:
        arm(*args, **kwargs)
    except _RED:
        return
    raise AssertionError(
        f"{arm.__name__} stayed GREEN while the control it grades was broken. "
        "An arm that cannot fail is not an arm."
    )



def test_m_p2a_grader_scores_everything_zero(monkeypatch):
    monkeypatch.setattr(rubric_grader, "_score_entity_normalization", lambda r, q: 0)
    monkeypatch.setattr(rubric_grader, "_score_database_routing", lambda r, q: 0)
    monkeypatch.setattr(rubric_grader, "_score_evidence_quality", lambda r, q: 0)
    monkeypatch.setattr(rubric_grader, "_score_freshness", lambda r, q: 0)
    monkeypatch.setattr(rubric_grader, "_score_output_usability", lambda r: 0)
    _must_go_red(gate.test_p2a_known_good_answer_meets_the_threshold)


def test_m_p2b_grader_scores_everything_two(monkeypatch):
    """The direction that matters most for a grader.

    A grader that awards full marks to everything passes P2a forever. Only
    P2b can catch it, so P2b must be provably able to fail.
    """
    monkeypatch.setattr(rubric_grader, "_score_entity_normalization", lambda r, q: 2)
    monkeypatch.setattr(rubric_grader, "_score_database_routing", lambda r, q: 2)
    monkeypatch.setattr(rubric_grader, "_score_evidence_quality", lambda r, q: 2)
    monkeypatch.setattr(rubric_grader, "_score_freshness", lambda r, q: 2)
    monkeypatch.setattr(rubric_grader, "_score_output_usability", lambda r: 2)
    monkeypatch.setattr(rubric_grader, "_JUDGED_CRITERIA", frozenset())
    _must_go_red(gate.test_p2b_known_bad_answer_falls_below_the_threshold)


def test_m_p2c_clamp_removed(monkeypatch):
    monkeypatch.setattr(rubric_grader, "_clamp", lambda value: int(value) + 7)
    _must_go_red(gate.test_p2c_every_criterion_scores_only_0_1_or_2)


def test_m_p2d_a_criterion_is_dropped(monkeypatch):
    """Patches `gate.RUBRIC_CRITERIA`, NOT the module's.

    The gate does `from ...rubric_grader import RUBRIC_CRITERIA`, which binds
    its own name at import. Patching the module attribute leaves that binding
    untouched, so the first version of this case mutated nothing and reported
    the arm as vacuous. The arm was fine; the mutation never reached it.
    That is the failure `_must_go_red` cannot detect on its own, and the
    reason every case here names the reference it patches.
    """
    monkeypatch.setattr(gate, "RUBRIC_CRITERIA", rubric_grader.RUBRIC_CRITERIA[:7])
    _must_go_red(gate.test_p2d_the_rubric_has_exactly_the_playbook_s_eight_criteria)


def test_m_p3a_hard_fails_stop_overriding_the_score(monkeypatch):
    monkeypatch.setattr(rubric_grader, "check_hard_fails", lambda **kw: [])
    _must_go_red(gate.test_p3a_provenance_hard_fail_beats_a_passing_score)


def test_m_p3b_verdict_detection_disabled(monkeypatch):
    monkeypatch.setattr(hard_fails, "renders_a_verdict", lambda text: False)
    _must_go_red(gate.test_p3b_verdict_on_a_clinical_question_is_a_hard_fail)


def test_m_p3b_attribution_admits_a_bare_reporting_verb(monkeypatch):
    """The regression case for F-5.1-01, the finding this phase actually hit.

    The original attribution list admitted the bare verb "reported", and the
    gate's own probe sentence is "...should be reported as such", which
    attributes to nobody. Restoring that one pattern must make P3b red
    again, which is what proves the fix is load-bearing rather than
    cosmetic.
    """
    monkeypatch.setattr(
        hard_fails,
        "_ATTRIBUTION_PATTERNS",
        hard_fails._ATTRIBUTION_PATTERNS + (r"\breported\b",),
    )
    _must_go_red(gate.test_p3b_verdict_on_a_clinical_question_is_a_hard_fail)


def test_m_p3c_assembly_context_check_removed(monkeypatch):
    original = hard_fails.check_hard_fails

    def without_assembly(**kwargs):
        return [f for f in original(**kwargs) if f != "assembly_context"]

    monkeypatch.setattr(hard_fails, "check_hard_fails", without_assembly)
    monkeypatch.setattr(gate, "check_hard_fails", without_assembly)
    _must_go_red(
        gate.test_p3c_missing_assembly_context_is_a_hard_fail_on_a_coordinate_question
    )


def test_m_p4a_abstain_always_counts_as_fail(monkeypatch):
    """Patches `is_non_answer`, which is what the grader actually reads.

    It patched `is_refusal` until `ask` became a second non-answering
    outcome and the grader moved to `is_non_answer`. The mutation then
    stopped reaching the control and reported a healthy arm as vacuous.
    A mutation case names a specific reference, so it goes stale exactly
    when that reference changes, which is the cost of the technique and
    the reason every case here says which reference it patches.
    """
    monkeypatch.setattr(
        rubric_grader.RunRecord, "is_non_answer", property(lambda s: False)
    )
    _must_go_red(gate.test_p4a_refusal_with_zero_retrieval_is_a_pass)


def test_m_p4b_abstain_always_counts_as_pass(monkeypatch):
    """The dangerous direction, and the reason P4a and P4b are separate arms.

    If abstain always counts as a pass, the agent scores 100 percent by
    refusing every question. Only P4b catches that.
    """
    original = rubric_grader.grade_run

    def always_pass(**kwargs):
        result = original(**kwargs)
        if result.outcome == "abstain":
            return rubric_grader.RubricResult(
                criteria=result.criteria,
                hard_fails=result.hard_fails,
                outcome="abstain",
                counts_as_pass=True,
                notes=result.notes,
            )
        return result

    monkeypatch.setattr(gate, "grade_run", always_pass)
    _must_go_red(gate.test_p4b_refusal_when_a_correct_source_existed_is_a_fail)


def test_m_p5a_pass_caret_k_collapses_into_pass_at_k(monkeypatch):
    monkeypatch.setattr(gate, "pass_caret_k", aggregate.pass_at_k)
    _must_go_red(gate.test_p5a_pass_at_k_and_pass_caret_k_diverge_on_a_mixed_sample)


def test_m_p5b_pass_caret_k_ignores_later_samples(monkeypatch):
    monkeypatch.setattr(
        gate,
        "pass_caret_k",
        lambda outcomes, *, k: 1.0
        if outcomes[0] in aggregate.PASSING_TOKENS
        else 0.0,
    )
    _must_go_red(gate.test_p5b_pass_caret_k_requires_every_sample)


def test_m_p5c_abstain_pass_stops_counting_as_a_pass(monkeypatch):
    monkeypatch.setattr(aggregate, "PASSING_TOKENS", frozenset({"pass"}))
    monkeypatch.setattr(gate, "pass_at_k", aggregate.pass_at_k)
    _must_go_red(gate.test_p5c_abstain_as_pass_aggregates_as_a_pass)


def test_m_p6_grader_starts_calling_the_loop(monkeypatch):
    """Proves the tripwire is armed rather than decorative.

    Without this case, P6 passes trivially forever, because a grader that
    never had a reason to call the loop also never calls it by accident.
    """
    import system_03_search_agent.core.run as run_module

    original = rubric_grader.grade_run

    def grade_and_rerun(**kwargs):
        run_module.run()
        return original(**kwargs)

    monkeypatch.setattr(gate, "grade_run", grade_and_rerun)
    _must_go_red(gate.test_p6_grading_never_invokes_the_agent_loop, monkeypatch)


def test_m_p7a_a_combined_ratio_appears(monkeypatch):
    original = coverage.coverage_report

    class WithCombined(coverage.CoverageReport):
        @property
        def combined_coverage(self) -> float:
            return (self.concept_coverage + self.predicate_coverage) / 2

    def combined(**kwargs):
        base = original(**kwargs)
        return WithCombined(
            concepts_exercised=base.concepts_exercised,
            predicates_exercised=base.predicates_exercised,
        )

    monkeypatch.setattr(gate, "coverage_report", combined)
    _must_go_red(gate.test_p7a_coverage_reports_two_separate_ratios)


def test_m_p7b_coverage_starts_gating(monkeypatch):
    original = coverage.coverage_report

    def gating(**kwargs):
        base = original(**kwargs)
        return coverage.CoverageReport(
            concepts_exercised=base.concepts_exercised,
            predicates_exercised=base.predicates_exercised,
            is_diagnostic_only=False,
        )

    monkeypatch.setattr(gate, "coverage_report", gating)
    _must_go_red(gate.test_p7b_low_coverage_raises_nothing_and_gates_nothing)


def test_m_p10a_short_samples_get_averaged_in(monkeypatch):
    """The mutation that makes a replay report a number it never measured."""
    original = replay.replay

    def score_everything(**kwargs):
        report = original(**kwargs)
        return replay.ReplayReport(
            graded=report.graded,
            metrics=report.metrics,
            coverage=report.coverage,
            cost=report.cost,
            k=report.k,
            queries_in_dataset=report.queries_in_dataset,
            queries_scored=report.queries_in_dataset,
            unscored_query_ids=[],
        )

    monkeypatch.setattr(replay, "replay", score_everything)
    _must_go_red(gate.test_p10a_a_query_with_fewer_than_k_samples_is_reported_unscored)


def test_m_p10b_the_score_leads_the_summary(monkeypatch):
    def score_first(self):
        return [f"pass@{self.k}: 100%", f"scored {self.queries_scored} of 1"]

    monkeypatch.setattr(replay.ReplayReport, "summary_lines", score_first)
    _must_go_red(gate.test_p10b_the_denominator_leads_the_summary)


def test_m_p10c_unknown_query_ids_are_skipped(monkeypatch):
    original = replay.replay

    # The signature mirrors the real `replay`, `acknowledge_parked`
    # included. A stand-in whose signature drifts from the function it
    # replaces stops exercising the arm and starts testing the stand-in.
    def skipping(*, records, dataset, judge=None, k=3, acknowledge_parked=False):
        known = {q.id for q in dataset.queries}
        return original(
            records=[r for r in records if r.query_id in known],
            dataset=dataset,
            judge=judge,
            k=k,
            acknowledge_parked=acknowledge_parked,
        )

    monkeypatch.setattr(replay, "replay", skipping)
    _must_go_red(gate.test_p10c_a_record_naming_an_unknown_query_is_an_error, None)


def test_m_p10d_scores_default_to_zero(monkeypatch):
    monkeypatch.setattr(replay, "rubric_score_updates", lambda report: {"t0": 0})
    _must_go_red(gate.test_p10d_rubric_score_updates_are_keyed_on_trace_id)


def test_the_arms_pass_when_nothing_is_broken():
    """The populate-check for this whole file.

    Every case above asserts an arm goes RED under mutation. If the arms
    were red for some unrelated reason, all of them would pass and this file
    would certify a gate that never works. So one case runs a representative
    arm with nothing patched and requires it to be GREEN.
    """
    gate.test_p2a_known_good_answer_meets_the_threshold()
    gate.test_p2b_known_bad_answer_falls_below_the_threshold()
    gate.test_p3b_verdict_on_a_clinical_question_is_a_hard_fail()
    gate.test_p5a_pass_at_k_and_pass_caret_k_diverge_on_a_mixed_sample()


def test_must_go_red_rejects_a_non_assertion_failure():
    """The helper itself must not count an unrelated crash as success.

    A `TypeError` from a bad patch means the mutation never reached the
    control, and treating that as "the arm went red" would certify a
    mutation that proved nothing.
    """

    def explodes():
        raise TypeError("bad patch, never reached the control")

    with pytest.raises(TypeError):
        _must_go_red(explodes)


def test_m_p11a_parser_extracts_nothing(monkeypatch):
    """The mutation that reproduces F-5.1-05 itself.

    A parser that reads the wrong fields returns an empty record. That is
    exactly what the first version did against real data, and no arm existed
    to notice.
    """
    monkeypatch.setattr(trace_source, "iter_events", lambda runs: [])
    _must_go_red(gate.test_p11a_a_real_trace_parses_into_a_gradeable_record)


def test_m_p11b_the_record_stops_grading_on_every_criterion(monkeypatch):
    monkeypatch.setattr(gate, "RUBRIC_CRITERIA", rubric_grader.RUBRIC_CRITERIA[:6])
    _must_go_red(gate.test_p11b_the_record_is_gradeable_end_to_end)


def test_m_p11c_deduplication_disabled(monkeypatch):
    """Counting one event twice inflates the hit count.

    An inflated `retrieval_hit_count` silently flips the abstain rule from
    pass to fail, so this is a scoring defect wearing a parsing costume.
    """

    def no_dedup(runs):
        out = []
        for run in runs:
            for bucket in ("inputs", "outputs"):
                for event in (run.get(bucket) or {}).get("events") or []:
                    if isinstance(event, dict) and event.get("type"):
                        out.append(event)
        return out

    monkeypatch.setattr(trace_source, "iter_events", no_dedup)
    _must_go_red(gate.test_p11c_events_are_deduplicated_on_seq)


def test_m_p11d_unmapped_traces_get_graded_anyway(monkeypatch):
    original = trace_source.record_from_runs

    def map_everything(payload, *, query_ids):
        runs = payload.get("runs") or []
        grouped: dict[str, list] = {}
        for run in runs:
            grouped.setdefault(str(run.get("trace_id")), []).append(run)
        return [
            original(rs, query_id=query_ids.get(tid, "G-001"))
            for tid, rs in grouped.items()
        ]

    monkeypatch.setattr(trace_source, "records_from_payload", map_everything)
    _must_go_red(gate.test_p11d_a_trace_with_no_mapped_query_id_is_skipped)


def test_m_p11e_a_fixture_carrying_an_identifier(monkeypatch, tmp_path):
    """Points the arm at a fixture that DOES carry an identifier.

    The real fixture cannot be mutated in place without writing to a
    committed artifact, so the arm's SUBJECT is swapped instead of its
    content. Same proof, no write to the repository.
    """
    poisoned = tmp_path / "poisoned.json"
    poisoned.write_text('{"runs": [{"inputs": {"user_id": "someone"}}]}')
    monkeypatch.setattr(gate, "_FIXTURE", poisoned)
    _must_go_red(gate.test_p11e_the_fixture_carries_no_account_identifier)


def test_coverage_claim_is_computed_not_asserted():
    """Every premise arm has a mutation case, or an explicit reason it does not.

    THIS REPLACES A PROSE COVERAGE CLAIM, deliberately. Build phase 4.15
    filed three separate findings where a mutation harness asserted complete
    coverage in a comment and the comment was wrong, once inside the fix for
    the previous one. The first version of this file's docstring made the
    same mistake a fourth time.

    A sentence describing coverage goes stale the moment an arm is added and
    nothing notices. A computation cannot: add an arm without a mutation case
    and this fails, naming the arm.
    """
    import inspect

    arms = {
        name[len("test_") :]
        for name, _ in inspect.getmembers(gate, inspect.isfunction)
        if name.startswith("test_p")
    }
    # An arm is "p3c" in "test_p3c_missing_assembly_context...". Take the
    # label up to the first underscore.
    arm_labels = {name.split("_", 1)[0] for name in arms}

    mutated = {
        name[len("test_m_") :].split("_", 1)[0]
        for name, _ in inspect.getmembers(
            __import__(__name__, fromlist=["x"]), inspect.isfunction
        )
        if name.startswith("test_m_p")
    }

    uncovered = arm_labels - mutated
    assert uncovered == set(_EXEMPT_ARMS), (
        f"arms with no mutation case: {sorted(uncovered)}; "
        f"declared exempt: {sorted(_EXEMPT_ARMS)}. "
        "Add a mutation case in the same edit as the arm, or add the arm to "
        "_EXEMPT_ARMS with the reason it cannot be mutated."
    )
    # Every exemption carries a real reason, not an empty string.
    assert all(reason.strip() for reason in _EXEMPT_ARMS.values())
    # And the harness actually mutates the large majority. A degenerate
    # _EXEMPT_ARMS listing everything would satisfy the check above.
    assert len(mutated) >= len(arm_labels) - 6, (
        f"only {len(mutated)} of {len(arm_labels)} arms are mutated"
    )
