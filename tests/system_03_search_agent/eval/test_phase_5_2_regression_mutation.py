"""Mutation coverage for the P12 regression arms: can each one FAIL?

The P12 arms lock in seven findings from build phase 5.1's review. Each one
asserts that an attack which USED TO WORK no longer does. That shape has a
specific failure mode: an arm asserting "X does not pass" is satisfied by a
grader that passes nothing at all, so six of the eight could be green
against a completely broken harness.

So every case here breaks the control the arm defends and requires the arm
to go red, and `test_p12h_populate_check_a_good_answer_still_passes` covers
the opposite direction.

Coverage is COMPUTED, not claimed, by the check at the bottom. Build phase
4.15 filed three separate findings where a mutation harness asserted its own
completeness in a comment and the comment was wrong.
"""

from __future__ import annotations

import pytest
from _pytest.outcomes import Failed

from system_03_search_agent.eval import hard_fails, rubric_grader
from tests.system_03_search_agent.eval import test_phase_5_2_regression as gate

_RED = (AssertionError, Failed)

# Arms with no mutation case, and the reason. Enforced by the computed check.
_EXEMPT_ARMS: dict[str, str] = {}


def _must_go_red(arm, *args, **kwargs) -> None:
    """Call an arm and require it to fail.

    Only assertion-shaped failures count. A TypeError from a bad patch means
    the mutation never reached the control, and counting that as success
    would certify a mutation that proved nothing.
    """
    try:
        arm(*args, **kwargs)
    except _RED:
        return
    raise AssertionError(
        f"{arm.__name__} stayed GREEN while the control it grades was broken. "
        "An arm that cannot fail is not an arm."
    )


def test_m_p12a_the_default_judge_scores_again(monkeypatch):
    """Restores the exact defect: a default that reaches the threshold."""
    monkeypatch.setattr(
        rubric_grader,
        "_default_judge",
        lambda *, criterion, record, query: 1,
    )
    _must_go_red(gate.test_p12a_grading_without_a_judge_is_refused)


def test_m_p12b_the_threshold_drops_to_zero(monkeypatch):
    monkeypatch.setattr(rubric_grader, "PASS_THRESHOLD", 0)
    _must_go_red(gate.test_p12b_a_fabricated_answer_passes_no_row)


def test_m_p12c_the_abstain_rule_stops_asking_the_dataset(monkeypatch):
    """The single most important case here.

    If this arm can stay green while the abstain rule ignores the dataset,
    then an agent scores 100 percent by refusing everything, and the flag
    this whole phase exists to measure gets reported as a success.
    """
    monkeypatch.setattr(
        rubric_grader, "_dataset_says_a_source_exists", lambda query: False
    )
    _must_go_red(gate.test_p12c_refusing_everything_passes_only_the_refusal_rows)


def test_m_p12d_the_outcome_class_check_is_removed(monkeypatch):
    monkeypatch.setattr(rubric_grader, "_acceptable", lambda query: set())
    _must_go_red(gate.test_p12d_answering_a_question_that_must_be_refused_fails)


def test_m_p12e_citation_matching_goes_back_to_a_substring(monkeypatch):
    """Patches `gate.citation_satisfies`, NOT the module's.

    The arm does `from ...rubric_grader import citation_satisfies`, binding
    its own name at import, so patching the module attribute leaves that
    binding untouched. The first version of this case did exactly that and
    reported a healthy arm as vacuous. The arm was fine; the mutation never
    reached it. Both references are patched here so the case holds whichever
    one the arm ends up using.
    """
    substring = lambda required, observed: required in observed
    monkeypatch.setattr(rubric_grader, "citation_satisfies", substring)
    monkeypatch.setattr(gate, "citation_satisfies", substring)
    _must_go_red(gate.test_p12e_a_citation_must_match_at_a_path_boundary)


def test_m_p12f_hard_fails_stop_being_detected(monkeypatch):
    monkeypatch.setattr(rubric_grader, "check_hard_fails", lambda **kw: [])
    _must_go_red(gate.test_p12f_a_hard_fail_beats_an_abstain)


def test_m_p12g_forbidden_becomes_dead_data_again(monkeypatch):
    monkeypatch.setattr(hard_fails, "check_forbidden", lambda **kw: ([], []))
    monkeypatch.setattr(gate, "check_forbidden", lambda **kw: ([], []))
    _must_go_red(gate.test_p12g_forbidden_is_read_and_unchecked_tokens_are_named)


def test_m_p12h_nothing_can_pass_any_more(monkeypatch):
    """The populate-check's own mutation.

    A harness that passes nothing satisfies six of the eight P12 arms. This
    proves the arm that would catch that is itself falsifiable.
    """
    monkeypatch.setattr(rubric_grader, "PASS_THRESHOLD", 99)
    _must_go_red(gate.test_p12h_populate_check_a_good_answer_still_passes)


def test_the_arms_pass_when_nothing_is_broken():
    """If the arms were red for an unrelated reason, every case above passes."""
    gate.test_p12e_a_citation_must_match_at_a_path_boundary()
    gate.test_p12h_populate_check_a_good_answer_still_passes()


def test_must_go_red_rejects_a_non_assertion_failure():
    def explodes():
        raise TypeError("bad patch, never reached the control")

    with pytest.raises(TypeError):
        _must_go_red(explodes)


def test_coverage_claim_is_computed_not_asserted():
    """Every P12 arm has a mutation case, or an explicit reason it does not."""
    import inspect

    arms = {
        name[len("test_") :].split("_", 1)[0]
        for name, _ in inspect.getmembers(gate, inspect.isfunction)
        if name.startswith("test_p12")
    }
    mutated = {
        name[len("test_m_") :].split("_", 1)[0]
        for name, _ in inspect.getmembers(
            __import__(__name__, fromlist=["x"]), inspect.isfunction
        )
        if name.startswith("test_m_p12")
    }
    uncovered = arms - mutated
    assert uncovered == set(_EXEMPT_ARMS), (
        f"P12 arms with no mutation case: {sorted(uncovered)}; "
        f"declared exempt: {sorted(_EXEMPT_ARMS)}"
    )
    assert len(arms) >= 8, f"only {len(arms)} P12 arms found"
