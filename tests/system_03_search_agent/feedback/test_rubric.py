"""Unit tests for `feedback.rubric.rubric_outcome_for` (T-4.6-04).

The premise gate's own P11 arm
(`tests/system_03_search_agent/core/test_feedback_capture_premise.py`)
already exercises this function end to end and asserts it never calls a
model tier. These tests cover the function's three branches directly, so a
regression is caught at the unit level before the (slower, database-backed)
premise gate would ever see it.
"""

from __future__ import annotations

from system_03_search_agent.feedback.rubric import rubric_outcome_for


def test_refuse_is_always_abstain_even_with_a_hard_fail() -> None:
    """A `refuse` trust signal is `abstain` regardless of `hard_fails`.

    Per Evaluation_playbook.md, abstain is the outcome for a run that
    "returned the refusal string"; the playbook names one condition for it,
    not a composition with the hard-fail check.

    Mutation run: changed the function's first branch from
    `if trust_signal == "refuse":` to `if trust_signal == "answer":`. The
    second assertion below went red (`rubric_outcome_for(trust_signal=
    "refuse", hard_fails=["uncited_claim"])` returned `"fail"` instead of
    `"abstain"`, since the mutated first branch no longer matched and the
    non-empty `hard_fails` list fell through to the second branch).
    Reverted after confirming the failure.
    """
    assert rubric_outcome_for(trust_signal="refuse", hard_fails=[]) == "abstain"
    assert (
        rubric_outcome_for(trust_signal="refuse", hard_fails=["uncited_claim"])
        == "abstain"
    )


def test_a_hard_fail_fails_a_non_refusal_outcome() -> None:
    """Any non-empty `hard_fails` list on `answer` or `flag` produces `fail`.

    Mutation run: changed the second branch from `if hard_fails:` to
    `if False:`. Both assertions below went red (both calls returned
    `"pass"` instead of `"fail"`, since the mutated branch could never be
    taken). Reverted after confirming the failure.
    """
    assert rubric_outcome_for(trust_signal="answer", hard_fails=["uncited_claim"]) == (
        "fail"
    )
    assert rubric_outcome_for(trust_signal="flag", hard_fails=["a", "b"]) == "fail"


def test_no_hard_fails_and_not_refuse_is_pass() -> None:
    """`answer` or `ask` with an empty `hard_fails` list is `pass`.

    Mutation run: changed the final `return "pass"` to `return "fail"`. Both
    assertions below went red (both calls returned `"fail"` instead of
    `"pass"`). Reverted after confirming the failure.
    """
    assert rubric_outcome_for(trust_signal="answer", hard_fails=[]) == "pass"
    assert rubric_outcome_for(trust_signal="ask", hard_fails=[]) == "pass"
