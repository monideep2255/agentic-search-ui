"""Mutation harness for build phase 4.14's CI premise gate.

Assertions that cannot fail are the single most repeated failure in this
repository's `LEARNINGS.md`. Build phase 4.3 shipped fourteen of them, build
phase 4.7 produced three in a file whose own docstring quoted the lesson
against them, and build phase 4.16 found six, five written by the lead in one
phase, none of them caught by reading. Every one of those was caught by
mutation or by a screenshot.

So this file breaks, one at a time, exactly the thing each arm of
`test_ci_workflow_premise.py` exists to catch, and asserts the arm goes RED.
It does that by CALLING THE REAL ARM against a mutated workflow rather than by
re-implementing its check, because a re-implementation proves only that the
copy works.

A control arm runs first: every mutated arm must pass on the unmutated
workflow. Without it, an arm that failed unconditionally would look like a
perfect mutation detector.

Depends on:
    - tests.ci.test_ci_workflow_premise
    - .github/workflows/ci.yml

Writes:
    - Nothing outside pytest's own tmp_path.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest
import yaml

from tests.ci import test_ci_workflow_premise as premise

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_workflow() -> dict:
    parsed = yaml.safe_load(premise.load_workflow_text())
    assert isinstance(parsed, dict) and parsed.get("jobs"), (
        "the workflow did not load; every mutation below would be measuring nothing"
    )
    return parsed


def mutant(workflow: dict) -> dict:
    return copy.deepcopy(workflow)


def job_with_gate(workflow: dict, order: int) -> dict:
    for job in workflow["jobs"].values():
        for step in job.get("steps", []) or []:
            if re.match(rf"^Gate {order}\b", str(step.get("name", ""))):
                return job
    raise AssertionError(f"no job carries gate {order}")


def step_with_gate(workflow: dict, order: int) -> dict:
    for step in job_with_gate(workflow, order).get("steps", []):
        if re.match(rf"^Gate {order}\b", str(step.get("name", ""))):
            return step
    raise AssertionError(f"no step for gate {order}")


def assert_arm_goes_red(arm, *args) -> None:
    """The arm must raise. A mutation that leaves it green is a vacuous arm."""
    with pytest.raises((AssertionError, Failed)):
        arm(*args)


# `pytest.fail` raises `Failed`, which is NOT an AssertionError. An arm that
# reports a missing file via `pytest.fail` would otherwise escape the check
# above, so both are caught.
Failed = pytest.fail.Exception


# ---------------------------------------------------------------------------
# The control. Without this, an unconditionally-failing arm scores perfectly.
# ---------------------------------------------------------------------------

_ARMS_UNDER_MUTATION = (
    premise.test_p3_gate_6_audits_the_requirements_file_not_the_ambient_environment,
    premise.test_p4_gate_9_points_at_a_file_that_exists_and_collects_tests,
    premise.test_p5_the_unit_job_runs_a_database_and_proves_it_reached_it,
    premise.test_p6_every_helper_script_the_workflow_calls_exists,
    premise.test_p7_gate_2_lints_paths_that_exist,
    premise.test_p8_frontend_gates_call_scripts_that_package_json_defines,
    premise.test_p9_gate_10_points_at_a_playwright_spec_that_exists,
    premise.test_p10_ci_runs_on_pull_requests,
    premise.test_p11_no_gate_but_gate_5_depends_on_a_secret,
    premise.test_p14_the_workflow_cancels_superseded_pull_request_runs,
    premise.test_p15_gate_5_cannot_pass_silently_when_it_did_not_run,
)


@pytest.mark.parametrize("arm", _ARMS_UNDER_MUTATION, ids=lambda a: a.__name__)
def test_m0_control_every_mutated_arm_passes_on_the_real_workflow(arm, real_workflow):
    arm(real_workflow)


def test_m0b_control_spec_dependent_arms_pass_on_the_real_workflow(real_workflow):
    spec_gates = premise.parse_spec_gates(premise.SPEC_PATH.read_text(encoding="utf-8"))
    assert len(spec_gates) == premise.EXPECTED_GATE_COUNT
    premise.test_p1_all_ten_specification_gates_are_present(real_workflow, spec_gates)
    premise.test_p1b_the_workflow_invents_no_gate_the_specification_does_not_list(
        real_workflow, spec_gates
    )
    premise.test_p2_gates_run_in_the_specification_order_within_each_job(real_workflow)


# ---------------------------------------------------------------------------
# Mutations against the three findings this phase filed
# ---------------------------------------------------------------------------


def test_m1_gate_6_scoped_back_to_the_ambient_environment_is_caught(real_workflow):
    """F-4.14-01 regressed: someone 'simplifies' `pip-audit -r ...` to `pip-audit`."""
    broken = mutant(real_workflow)
    step = step_with_gate(broken, 6)
    step["run"] = str(step["run"]).replace("-r requirements.txt", "")
    assert_arm_goes_red(
        premise.test_p3_gate_6_audits_the_requirements_file_not_the_ambient_environment,
        broken,
    )


def test_m2_the_postgres_service_removed_is_caught(real_workflow):
    """F-4.14-03, half one: the service disappears and every DB test skips."""
    broken = mutant(real_workflow)
    job_with_gate(broken, 4).pop("services", None)
    assert_arm_goes_red(
        premise.test_p5_the_unit_job_runs_a_database_and_proves_it_reached_it, broken
    )


def test_m3_the_no_silent_skip_assertion_removed_is_caught(real_workflow):
    """F-4.14-03, half two, and the subtler half.

    The service can be present and still unreachable: a wrong port, a wrong
    database name, an unhealthy container. Deleting the assertion leaves a
    workflow that LOOKS correct and certifies nothing, which is precisely the
    shape this phase exists to stop.
    """
    broken = mutant(real_workflow)
    job = job_with_gate(broken, 4)
    job["steps"] = [
        step for step in job["steps"] if "assert_no_db_skips.py" not in str(step.get("run", ""))
    ]
    assert_arm_goes_red(
        premise.test_p5_the_unit_job_runs_a_database_and_proves_it_reached_it, broken
    )


def test_m4_user_db_url_removed_is_caught(real_workflow):
    """The service runs, and nothing tells the tests where it is."""
    broken = mutant(real_workflow)
    job_with_gate(broken, 4).pop("env", None)
    assert_arm_goes_red(
        premise.test_p5_the_unit_job_runs_a_database_and_proves_it_reached_it, broken
    )


def test_m5_gate_9_pointed_at_a_renamed_file_is_caught(real_workflow):
    """F-4.14-02: the exact failure Section 24's own two test names already had."""
    broken = mutant(real_workflow)
    step = step_with_gate(broken, 9)
    step["run"] = str(step["run"]).replace(
        "tests/system_03_search_agent/synthesis/test_required_paths.py",
        "tests/system_03_search_agent/synthesis/test_renamed_away.py",
    )
    assert_arm_goes_red(
        premise.test_p4_gate_9_points_at_a_file_that_exists_and_collects_tests, broken
    )


# ---------------------------------------------------------------------------
# Mutations against fidelity to Section 24
# ---------------------------------------------------------------------------


def test_m6_a_deleted_gate_is_caught(real_workflow):
    spec_gates = premise.parse_spec_gates(premise.SPEC_PATH.read_text(encoding="utf-8"))
    broken = mutant(real_workflow)
    job = job_with_gate(broken, 7)
    job["steps"] = [
        step for step in job["steps"] if not str(step.get("name", "")).startswith("Gate 7")
    ]
    with pytest.raises((AssertionError, Failed)):
        premise.test_p1_all_ten_specification_gates_are_present(broken, spec_gates)


def test_m7_an_invented_gate_is_caught(real_workflow):
    spec_gates = premise.parse_spec_gates(premise.SPEC_PATH.read_text(encoding="utf-8"))
    broken = mutant(real_workflow)
    job_with_gate(broken, 7)["steps"].append(
        {"name": "Gate 11: something nobody agreed to", "run": "true"}
    )
    with pytest.raises((AssertionError, Failed)):
        premise.test_p1b_the_workflow_invents_no_gate_the_specification_does_not_list(
            broken, spec_gates
        )


def test_m8_gates_reordered_within_a_job_are_caught(real_workflow):
    """Section 24 specifies an order, so a workflow that ignores it is wrong."""
    broken = mutant(real_workflow)
    job = job_with_gate(broken, 1)
    gate_indices = [
        index
        for index, step in enumerate(job["steps"])
        if re.match(r"^Gate \d+\b", str(step.get("name", "")))
    ]
    first, last = gate_indices[0], gate_indices[-1]
    job["steps"][first], job["steps"][last] = job["steps"][last], job["steps"][first]
    assert_arm_goes_red(
        premise.test_p2_gates_run_in_the_specification_order_within_each_job, broken
    )


# ---------------------------------------------------------------------------
# Mutations against "the commands are real"
# ---------------------------------------------------------------------------


def test_m9_a_missing_helper_script_is_caught(real_workflow):
    broken = mutant(real_workflow)
    step = step_with_gate(broken, 9)
    step["run"] = str(step["run"]).replace(
        "assert_required_paths_ran.py", "assert_nothing_at_all.py"
    )
    assert_arm_goes_red(premise.test_p6_every_helper_script_the_workflow_calls_exists, broken)


def test_m10_gate_2_pointed_at_a_path_that_does_not_exist_is_caught(real_workflow):
    """isort exits 0 on a path that is not there, so this cannot be left to isort."""
    broken = mutant(real_workflow)
    step = step_with_gate(broken, 2)
    step["run"] = str(step["run"]) + " src_typo_that_does_not_exist"
    assert_arm_goes_red(premise.test_p7_gate_2_lints_paths_that_exist, broken)


def test_m11_gate_2_stripped_of_every_path_is_caught(real_workflow):
    """The vacuous version: isort with no paths checks nothing and exits 0."""
    broken = mutant(real_workflow)
    step_with_gate(broken, 2)["run"] = "isort --check-only --diff"
    assert_arm_goes_red(premise.test_p7_gate_2_lints_paths_that_exist, broken)


def test_m12_an_npm_script_package_json_does_not_define_is_caught(real_workflow):
    broken = mutant(real_workflow)
    step = step_with_gate(broken, 8)
    step["run"] = "npm run buidl"
    assert_arm_goes_red(
        premise.test_p8_frontend_gates_call_scripts_that_package_json_defines, broken
    )


def test_m13_gate_10_pointed_at_a_missing_spec_is_caught(real_workflow):
    broken = mutant(real_workflow)
    step = step_with_gate(broken, 10)
    step["run"] = str(step["run"]).replace(
        "e2e/accessibility.spec.ts", "e2e/does-not-exist.spec.ts"
    )
    assert_arm_goes_red(
        premise.test_p9_gate_10_points_at_a_playwright_spec_that_exists, broken
    )


# ---------------------------------------------------------------------------
# Mutations against the workflow's own properties
# ---------------------------------------------------------------------------


def test_m14_dropping_the_pull_request_trigger_is_caught(real_workflow):
    """The whole point of the phase. CI on push only guards nothing."""
    broken = mutant(real_workflow)
    key = "on" if "on" in broken else True
    broken[key] = {"push": {"branches": ["develop"]}}
    assert_arm_goes_red(premise.test_p10_ci_runs_on_pull_requests, broken)


def test_m15_a_gate_made_to_depend_on_a_secret_is_caught(real_workflow):
    """A gate that needs a credential goes green on a fork for the wrong reason."""
    broken = mutant(real_workflow)
    job = job_with_gate(broken, 4)
    job.setdefault("env", {})["SOME_TOKEN"] = "${{ secrets.SOME_TOKEN }}"
    assert_arm_goes_red(premise.test_p11_no_gate_but_gate_5_depends_on_a_secret, broken)


def test_m21_gate_5_exiting_zero_without_saying_so_is_caught(real_workflow):
    """The quiet-green mutation: drop the annotation, keep the `exit 0`.

    This is the most tempting simplification in the whole file, because the
    job still "works" afterwards. It just stops telling anyone that it
    verified nothing.
    """
    broken = mutant(real_workflow)
    step = step_with_gate(broken, 5)
    step["run"] = "\n".join(
        line for line in str(step["run"]).splitlines() if "::warning" not in line
    )
    assert_arm_goes_red(premise.test_p15_gate_5_cannot_pass_silently_when_it_did_not_run, broken)


def test_m16_removing_the_concurrency_block_is_caught(real_workflow):
    broken = mutant(real_workflow)
    broken.pop("concurrency", None)
    assert_arm_goes_red(
        premise.test_p14_the_workflow_cancels_superseded_pull_request_runs, broken
    )


# ---------------------------------------------------------------------------
# Mutations against the two arms that read pyproject.toml from disk
# ---------------------------------------------------------------------------


def _premise_rooted_at(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(premise, "REPO_ROOT", root)


def test_m17_unpinning_ruff_is_caught(tmp_path, monkeypatch):
    """A floor lets a minor bump silently change what gate 3 enforces."""
    real = (premise.REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        re.sub(r'"ruff==[\d.]+"', '"ruff>=0.4"', real), encoding="utf-8"
    )
    _premise_rooted_at(monkeypatch, tmp_path)
    assert_arm_goes_red(premise.test_p12_ruff_is_pinned_exactly_so_the_lint_gate_cannot_drift)


def test_m18_re_enabling_ruffs_import_rules_is_caught(tmp_path, monkeypatch):
    """Two tools policing import order means one gate is always red."""
    real = (premise.REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        real.replace('ignore = ["I001"]', "ignore = []"), encoding="utf-8"
    )
    _premise_rooted_at(monkeypatch, tmp_path)
    assert_arm_goes_red(premise.test_p13_import_order_has_exactly_one_owner)


def test_m19_removing_the_isort_configuration_entirely_is_caught(tmp_path, monkeypatch):
    real = (premise.REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        real.replace("[tool.isort]", "[tool.isort_disabled]"), encoding="utf-8"
    )
    _premise_rooted_at(monkeypatch, tmp_path)
    assert_arm_goes_red(premise.test_p13_import_order_has_exactly_one_owner)


# ---------------------------------------------------------------------------
# The mutation that checks the POPULATE-CHECK, not the arm
# ---------------------------------------------------------------------------


def test_m20_a_specification_table_that_stops_parsing_fails_loudly(tmp_path):
    """The arm that would otherwise hide every other spec-fidelity failure.

    If Section 24's table were reworded so `parse_spec_gates` matched nothing,
    P1 and P1b would compare the workflow against an empty list and pass. The
    populate-check in the `spec_gates` fixture turns that into a failure. This
    proves the populate-check itself works, which is the arm build phase 4.7
    found could survive its own repair by verifying a correlate instead.
    """
    reworded = "Merge-blocking gates, in order:\n\nnothing resembling a table here.\n"
    assert premise.parse_spec_gates(reworded) == []

    marker_gone = "the gates are described in prose now.\n"
    assert premise.parse_spec_gates(marker_gone) == []

    # And the positive control: the real document still parses to ten.
    real = premise.parse_spec_gates(premise.SPEC_PATH.read_text(encoding="utf-8"))
    assert len(real) == premise.EXPECTED_GATE_COUNT
