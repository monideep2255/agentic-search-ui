"""Mutation coverage for build phase 5.1's dataset arms: can each arm FAIL?

Scope narrowed 2026-08-30 by product-owner decision: the grading harness moved
to build phase 5.2 after both review rounds returned FAIL on it, and its
mutation cases moved with it, unchanged, to `test_phase_5_2_mutation.py`.
Nothing was deleted and nothing was weakened.

## Coverage: computed, never claimed

Build phase 4.15 filed the same defect three times: a mutation harness
claiming complete coverage in a comment, once inside the fix for the previous
claim, naming an uncovered arm as covered. The first version of this file did
it a fourth time.

So the claim is not prose. `test_coverage_claim_is_computed_not_asserted`
introspects both modules, derives which arms have a mutation case, and
requires the difference to equal `_EXEMPT_ARMS` exactly. Adding an arm without
a mutation case fails the suite and names the arm. It has been proven able to
fail.
"""


from __future__ import annotations

import pytest
from _pytest.outcomes import Failed

from system_03_search_agent.eval import dataset
from tests.system_03_search_agent.eval import test_phase_5_1_premise as gate

# An arm "goes red" if it raises an assertion failure, or if a
# `pytest.raises` block it depends on finds no exception (which pytest
# reports as `Failed`). Both are the arm doing its job.
_RED = (AssertionError, Failed)

# Arms with no mutation case, each with the reason it has none. This mapping
# is enforced by the computed coverage check at the bottom of the file, so it
# cannot silently disagree with what is actually here.
_EXEMPT_ARMS: dict[str, str] = {
    "p1c": "populate-check: its whole job is to fail when the subject does "
    "nothing, so 'mutate the subject to do nothing' is what it already asserts",
    "p9e": "populate-check, same reason as p1c",
    "p8": "its subject is the shipped 50-row file on disk. Mutating it needs "
    "write access to the very artifact the arm protects, so that run was done "
    "by hand and its result recorded in tracker/phase_5.1.md",
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



def test_m_p1a_provenance_requirement_removed(monkeypatch, tmp_path):
    monkeypatch.setattr(dataset, "_REQUIRED_ROW_FIELDS", ("id", "question"))
    monkeypatch.setattr(
        dataset,
        "_validate_provenance",
        lambda row_id, raw: dataset.Provenance("live_source", "s", "d", "p", "b"),
    )
    _must_go_red(gate.test_p1a_row_without_provenance_is_refused, tmp_path)


def test_m_p1b_agent_output_becomes_allowed(monkeypatch, tmp_path):
    """THE MOST IMPORTANT CASE IN THIS FILE.

    If P1b can stay green while `agent_output` is accepted, then nothing in
    the system stops a dataset curated from the agent's own answers, and the
    product-owner decision of 2026-08-30 is a comment rather than a control.
    """
    monkeypatch.setattr(dataset, "_REFUSED_AUTHORED_FROM", frozenset())
    monkeypatch.setattr(
        dataset,
        "_ALLOWED_AUTHORED_FROM",
        frozenset({"live_source", "locked_requirements", "agent_output"}),
    )
    _must_go_red(gate.test_p1b_row_authored_from_the_agent_is_refused, tmp_path)


def test_m_p1d_sign_off_bound_becomes_optional(monkeypatch, tmp_path):
    monkeypatch.setattr(
        dataset,
        "_REQUIRED_PROVENANCE_FIELDS",
        ("authored_from", "source", "read_on", "signed_off_by"),
    )
    _must_go_red(gate.test_p1d_sign_off_bound_is_required_not_optional, tmp_path)


def test_m_p9a_category_requirement_removed(monkeypatch, tmp_path):
    monkeypatch.setattr(
        dataset, "_SEARCH_CATEGORIES", frozenset({"kiss", "kisses", "discovery", None})
    )
    _must_go_red(gate.test_p9a_a_row_with_no_search_category_is_refused, tmp_path)


def test_m_p9b_discovery_no_longer_needs_follow_ups(monkeypatch, tmp_path):
    monkeypatch.setattr(dataset, "_SEARCH_CATEGORIES", frozenset({"kiss", "kisses"}))
    _must_go_red(
        gate.test_p9b_a_discovery_row_with_no_follow_ups_is_refused, tmp_path
    )


def test_m_p9c_follow_ups_allowed_on_a_kiss_row(monkeypatch, tmp_path):
    """Turns attached to a row nothing will ever run them for.

    In the file that reads as coverage which does not exist, which is the
    same class of lie as a vacuous arm, one level up.
    """
    monkeypatch.setattr(dataset, "_SEARCH_CATEGORIES", frozenset({"discovery"}))
    _must_go_red(gate.test_p9c_a_kiss_row_carrying_follow_ups_is_refused, tmp_path)


def test_m_p9d_truncation_constraint_dropped(monkeypatch, tmp_path):
    monkeypatch.setattr(dataset, "_TRUNCATION_CONSTRAINT", "never_present_anywhere")
    _must_go_red(
        gate.test_p9d_a_kisses_row_must_forbid_undisclosed_truncation, tmp_path
    )


def test_the_arms_pass_when_nothing_is_broken(tmp_path):
    """The populate-check for this whole file.

    Every case above asserts an arm goes RED under mutation. If the arms
    were red for some unrelated reason, all of them would pass and this file
    would certify a gate that never works. So one case runs a representative
    arm with nothing patched and requires it to be GREEN.
    """
    gate.test_p1c_populate_check_a_valid_row_actually_loads(tmp_path)


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
