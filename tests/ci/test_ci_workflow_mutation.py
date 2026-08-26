"""Mutation harness for build phase 4.14's CI premise gate.

Assertions that cannot fail are the single most repeated failure in this
repository's `LEARNINGS.md`. Build phase 4.3 shipped fourteen, build phase 4.7
produced three in a file whose own docstring quoted the lesson against them, and
build phase 4.16 found six, five written by the lead in one phase, none caught
by reading.

This phase added its own instance, and it is the reason this file was rewritten.
Its first version mutated the workflow's STRUCTURE, deleting a gate, reordering
steps, emptying a key, and every one of those was caught. Then the judge and the
adversary each attacked the CONTENT of a gate's command, independently, and
between them landed 32 mutations that the premise gate did not notice, including
replacing every gate body with `true` while keeping the command in a comment.
Sixteen of the strongest are now permanent arms below.

The lesson, which generalises past this file: a mutation harness proves only
what it mutates. Structural mutations prove the arms read the file. They say
nothing about whether the arms read the part of the file that matters.

Every arm CALLS THE REAL PREMISE ARM against a mutated workflow rather than
re-implementing its check, because a re-implementation proves only that the copy
works. A control arm runs first: every arm must pass on the unmutated workflow,
without which an unconditionally-failing arm would look like a perfect detector.

Depends on:
    - tests.ci.test_ci_workflow_premise
    - .github/workflows/ci.yml

Writes:
    - Nothing outside pytest's own tmp_path.
"""

from __future__ import annotations

import copy
import inspect
import re
from pathlib import Path

import pytest
import yaml

from tests.ci import test_ci_workflow_premise as premise

# `pytest.fail` raises `Failed`, which is NOT an AssertionError. An arm that
# reports a missing file via `pytest.fail` would otherwise escape every check
# here, so both are caught everywhere below.
Failed = pytest.fail.Exception
RED = (AssertionError, Failed)


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


@pytest.fixture(scope="module")
def spec_gates() -> list[tuple[int, str]]:
    rows = premise.parse_spec_gates(premise.SPEC_PATH.read_text(encoding="utf-8"))
    assert len(rows) == premise.EXPECTED_GATE_COUNT
    return rows


def mutant(workflow: dict) -> dict:
    return copy.deepcopy(workflow)


def gate_step_pairs(workflow: dict):
    """Yield (job, step) for every step named `Gate N...`."""
    for job in workflow["jobs"].values():
        for step in job.get("steps", []) or []:
            if str(step.get("name", "")).startswith("Gate"):
                yield job, step


def steps_for(workflow: dict, prefix: str) -> list[dict]:
    return [step for _job, step in gate_step_pairs(workflow) if str(step["name"]).startswith(prefix)]


def job_with_gate(workflow: dict, order: int) -> dict:
    return premise.job_containing_gate(workflow, order)[1]


def step_with_gate(workflow: dict, order: int) -> dict:
    steps = steps_for(workflow, f"Gate {order}")
    assert steps, f"no step for gate {order}"
    return steps[0]


def assert_arm_goes_red(arm, *args, **kwargs) -> None:
    """The arm must raise. A mutation that leaves it green is a vacuous arm."""
    with pytest.raises(RED):
        arm(*args, **kwargs)


def run_every_arm(workflow: dict, spec_gates: list[tuple[int, str]]) -> list[str]:
    """Run every premise arm against `workflow`; return the names that went red.

    Used by the content mutations below, because a mutation like "replace every
    gate body with `true`" is not aimed at one arm: what matters is that SOME
    arm notices. Asserting a specific arm would make this file brittle against
    an honest refactor of the premise gate.
    """
    red: list[str] = []
    for name, arm in sorted(vars(premise).items()):
        if not name.startswith("test_p") or not callable(arm):
            continue
        params = inspect.signature(arm).parameters
        cases: list[dict] = [{}]
        if "order" in params:
            cases = [
                {"order": order, "required": required, "description": description}
                for order, required, description in premise._REQUIRED_COMMANDS
            ]
        for case in cases:
            kwargs = dict(case)
            if "workflow" in params:
                kwargs["workflow"] = workflow
            if "spec_gates" in params:
                kwargs["spec_gates"] = spec_gates
            try:
                arm(**kwargs)
            except RED:
                red.append(name)
                break
    return red


# ---------------------------------------------------------------------------
# The control. Without this, an unconditionally-failing arm scores perfectly.
# ---------------------------------------------------------------------------


def test_m0_control_every_arm_passes_on_the_real_workflow(real_workflow, spec_gates):
    red = run_every_arm(real_workflow, spec_gates)
    assert not red, f"these arms fail on the UNMUTATED workflow, so every mutation below is noise: {red}"


# ---------------------------------------------------------------------------
# Content mutations: the class the first version of this harness missed entirely
# ---------------------------------------------------------------------------


def _blank_every_gate_body(workflow: dict) -> None:
    """The attack that beat the first premise gate: 15 of 16 arms stayed green."""
    for _job, step in gate_step_pairs(workflow):
        step["run"] = "true  # " + str(step.get("run", "")).replace("\n", " ; ")


def _continue_on_error(workflow: dict) -> None:
    for _job, step in gate_step_pairs(workflow):
        step["continue-on-error"] = True


def _or_true_on_gate_4(workflow: dict) -> None:
    for step in steps_for(workflow, "Gate 4:"):
        step["run"] = str(step["run"]).rstrip() + " || true"


def _rescope_gate_3_to_src(workflow: dict) -> None:
    step_with_gate(workflow, 3)["run"] = "ruff check src"


def _narrow_gate_4_to_one_directory(workflow: dict) -> None:
    for step in steps_for(workflow, "Gate 4:"):
        step["run"] = 'pytest -m "not integration" -q tests/ci/'


def _relax_gate_7_threshold(workflow: dict) -> None:
    step_with_gate(workflow, 7)["run"] = "npm audit --audit-level=critical"


def _strip_isort_check_only(workflow: dict) -> None:
    step = step_with_gate(workflow, 2)
    step["run"] = str(step["run"]).replace("--check-only", "")


def _disable_gate_10(workflow: dict) -> None:
    step_with_gate(workflow, 10)["if"] = False


def _hoist_a_secret_to_workflow_env(workflow: dict) -> None:
    workflow.setdefault("env", {})["SNEAKY_TOKEN"] = "${{ secrets.SNEAKY_TOKEN }}"


def _swap_postgres_for_redis(workflow: dict) -> None:
    for job in workflow["jobs"].values():
        for spec in (job.get("services") or {}).values():
            if str(spec.get("image", "")).startswith("postgres"):
                spec["image"] = "redis:7"


def _empty_user_db_url(workflow: dict) -> None:
    for job in workflow["jobs"].values():
        if "USER_DB_URL" in (job.get("env") or {}):
            job["env"]["USER_DB_URL"] = ""


def _remove_postgres_service(workflow: dict) -> None:
    for job in workflow["jobs"].values():
        job.pop("services", None)


def _remove_alembic_upgrade(workflow: dict) -> None:
    for job in workflow["jobs"].values():
        job["steps"] = [
            step
            for step in job.get("steps", []) or []
            if "alembic upgrade" not in str(step.get("run", ""))
        ]


def _remove_db_skip_assertion(workflow: dict) -> None:
    for job in workflow["jobs"].values():
        job["steps"] = [
            step
            for step in job.get("steps", []) or []
            if "assert_no_db_skips.py" not in str(step.get("run", ""))
        ]


def _gate_5_loses_its_ran_anything_assertion(workflow: dict) -> None:
    step = step_with_gate(workflow, 5)
    step["run"] = "\n".join(
        line for line in str(step["run"]).splitlines() if "assert_gate_ran" not in line
    )


def _gate_5_loses_run_premise_gate(workflow: dict) -> None:
    step = step_with_gate(workflow, 5)
    (step.get("env") or {}).pop("RUN_PREMISE_GATE", None)


def _gate_5_loses_its_warning(workflow: dict) -> None:
    step = step_with_gate(workflow, 5)
    step["run"] = "\n".join(
        line for line in str(step["run"]).splitlines() if "::warning" not in line
    )


def _gate_10_filter_fails_open_again(workflow: dict) -> None:
    for job in workflow["jobs"].values():
        for step in job.get("steps", []) or []:
            if "touched" in str(step.get("run", "")):
                step["run"] = (
                    'base="$BASE_SHA"\n'
                    'if [ -z "$base" ]; then echo "touched=true" >> "$GITHUB_OUTPUT"; exit 0; fi\n'
                    "if git diff --name-only \"$base\" \"$HEAD_SHA\" | grep -qE '^frontend/'; then\n"
                    '  echo "touched=true" >> "$GITHUB_OUTPUT"\n'
                    "else\n"
                    '  echo "touched=false" >> "$GITHUB_OUTPUT"\n'
                    "fi"
                )


def _gate_9_points_at_a_renamed_file(workflow: dict) -> None:
    step = step_with_gate(workflow, 9)
    step["run"] = str(step["run"]).replace("test_required_paths.py", "test_renamed_away.py")


def _gate_6_audits_the_ambient_environment(workflow: dict) -> None:
    step = step_with_gate(workflow, 6)
    step["run"] = str(step["run"]).replace("-r requirements.txt", "")


def _drop_the_pull_request_trigger(workflow: dict) -> None:
    key = "on" if "on" in workflow else True
    workflow[key] = {"push": {"branches": ["develop"]}}


def _remove_concurrency(workflow: dict) -> None:
    workflow.pop("concurrency", None)


def _delete_gate_7(workflow: dict) -> None:
    for job in workflow["jobs"].values():
        job["steps"] = [
            step
            for step in job.get("steps", []) or []
            if not str(step.get("name", "")).startswith("Gate 7")
        ]


def _invent_a_gate(workflow: dict) -> None:
    job = job_with_gate(workflow, 7)
    job["steps"].append({"name": "Gate 11: something nobody agreed to", "run": "true"})


def _reorder_gates_within_a_job(workflow: dict) -> None:
    job = job_with_gate(workflow, 1)
    indices = [
        index
        for index, step in enumerate(job["steps"])
        if re.match(r"^Gate \d+\b", str(step.get("name", "")))
    ]
    first, last = indices[0], indices[-1]
    job["steps"][first], job["steps"][last] = job["steps"][last], job["steps"][first]


def _gate_2_loses_every_path(workflow: dict) -> None:
    step_with_gate(workflow, 2)["run"] = "isort --check-only --diff"


def _gate_2_points_at_a_missing_path(workflow: dict) -> None:
    step = step_with_gate(workflow, 2)
    step["run"] = str(step["run"]).rstrip() + " src_typo_that_does_not_exist"


def _npm_script_that_does_not_exist(workflow: dict) -> None:
    step_with_gate(workflow, 8)["run"] = "npm run buidl"


def _gate_10_points_at_a_missing_spec(workflow: dict) -> None:
    step = step_with_gate(workflow, 10)
    step["run"] = str(step["run"]).replace("accessibility.spec.ts", "does-not-exist.spec.ts")


def _missing_helper_script(workflow: dict) -> None:
    step = step_with_gate(workflow, 9)
    step["run"] = str(step["run"]).replace(
        "assert_required_paths_ran.py", "assert_nothing_at_all.py"
    )


# Each entry is (id, description, mutation). The id names the finding or review
# round that produced it, so a future reader can trace why the arm exists.
_MUTATIONS = (
    ("A-05", "every gate body replaced by `true`, command kept in a comment", _blank_every_gate_body),
    ("J-02", "continue-on-error: true on every gate", _continue_on_error),
    ("J-02", "`|| true` appended to gate 4", _or_true_on_gate_4),
    ("J-02", "gate 3 re-scoped to `ruff check src`", _rescope_gate_3_to_src),
    ("J-02", "gate 4 narrowed to a single directory", _narrow_gate_4_to_one_directory),
    ("J-02", "gate 7 relaxed to --audit-level=critical", _relax_gate_7_threshold),
    ("J-02", "gate 2 stripped of --check-only, so isort rewrites and exits 0", _strip_isort_check_only),
    ("J-02", "`if: false` on gate 10", _disable_gate_10),
    ("J-02", "a secret hoisted to workflow-level env", _hoist_a_secret_to_workflow_env),
    ("J-04", "the postgres service swapped for redis:7", _swap_postgres_for_redis),
    ("J-04", "USER_DB_URL set to the empty string", _empty_user_db_url),
    ("F-4.14-03", "the postgres service removed entirely", _remove_postgres_service),
    ("F-4.14-03", "the alembic upgrade step removed", _remove_alembic_upgrade),
    ("F-4.14-03", "the no-silent-skip assertion removed", _remove_db_skip_assertion),
    ("A-03", "gate 5 loses its ran-anything assertion", _gate_5_loses_its_ran_anything_assertion),
    ("A-03", "gate 5 loses RUN_PREMISE_GATE, so its arms can never run", _gate_5_loses_run_premise_gate),
    ("A-03", "gate 5's not-run path loses its warning annotation", _gate_5_loses_its_warning),
    ("A-07", "gate 10's filter reverted to the fail-open form", _gate_10_filter_fails_open_again),
    ("F-4.14-02", "gate 9 pointed at a renamed file", _gate_9_points_at_a_renamed_file),
    ("F-4.14-01", "gate 6 scoped back to the ambient environment", _gate_6_audits_the_ambient_environment),
    ("round 1", "the pull_request trigger dropped", _drop_the_pull_request_trigger),
    ("round 1", "the concurrency block removed", _remove_concurrency),
    ("round 1", "a Section 24 gate deleted", _delete_gate_7),
    ("round 1", "a gate invented that Section 24 does not list", _invent_a_gate),
    ("round 1", "gates reordered within a job", _reorder_gates_within_a_job),
    ("round 1", "gate 2 stripped of every path", _gate_2_loses_every_path),
    ("round 1", "gate 2 pointed at a path that does not exist", _gate_2_points_at_a_missing_path),
    ("round 1", "an npm script package.json does not define", _npm_script_that_does_not_exist),
    ("round 1", "gate 10 pointed at a spec that does not exist", _gate_10_points_at_a_missing_spec),
    ("round 1", "a helper script that does not exist", _missing_helper_script),
)


@pytest.mark.parametrize(
    ("origin", "description", "mutation"),
    _MUTATIONS,
    ids=[f"{origin}-{description[:45]}" for origin, description, _ in _MUTATIONS],
)
def test_m_every_mutation_is_caught_by_some_arm(
    origin, description, mutation, real_workflow, spec_gates
):
    """SOME arm must go red. Which one is not asserted, deliberately.

    Pinning a mutation to a named arm makes this file brittle against an honest
    refactor of the premise gate, and what actually matters is that the defect
    cannot reach `develop` unnoticed, not which assertion notices it.
    """
    broken = mutant(real_workflow)
    mutation(broken)
    red = run_every_arm(broken, spec_gates)
    assert red, (
        f"NO premise arm noticed this mutation ({origin}: {description}). "
        f"That is a vacuous gate: the workflow can be changed this way and CI "
        f"will not tell anyone."
    )


# ---------------------------------------------------------------------------
# Mutations against the two arms that read pyproject.toml from disk
# ---------------------------------------------------------------------------


def _premise_rooted_at(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(premise, "REPO_ROOT", root)


def _write_pyproject(tmp_path: Path, transform) -> None:
    real = (premise.REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(transform(real), encoding="utf-8")


def test_m17_unpinning_ruff_is_caught(tmp_path, monkeypatch):
    """A floor lets a minor release silently change what gate 3 enforces."""
    _write_pyproject(tmp_path, lambda text: re.sub(r'"ruff==[\d.]+"', '"ruff>=0.4"', text))
    _premise_rooted_at(monkeypatch, tmp_path)
    assert_arm_goes_red(premise.test_p12_ruff_is_pinned_exactly_so_the_lint_gate_cannot_drift)


def test_m17b_a_commented_out_pin_is_caught(tmp_path, monkeypatch):
    """F-4.14-A-10: the first version matched raw text, so a comment satisfied it."""
    _write_pyproject(
        tmp_path, lambda text: text.replace('"ruff==0.16.0",', '# "ruff==0.16.0",\n    "ruff",')
    )
    _premise_rooted_at(monkeypatch, tmp_path)
    assert_arm_goes_red(premise.test_p12_ruff_is_pinned_exactly_so_the_lint_gate_cannot_drift)


def test_m18_disabling_ruffs_import_rule_is_caught(tmp_path, monkeypatch):
    """The correction to this phase's own worst judgement call.

    Ignoring `I001` repository-wide leaves every isort-skipped file unchecked by
    anything. This is the exact change the first version of this phase made and
    then defended in three documents.
    """
    _write_pyproject(
        tmp_path,
        lambda text: text.replace(
            "[tool.ruff.lint.isort]", '[tool.ruff.lint]\nignore = ["I001"]\n\n[tool.ruff.lint.isort]'
        ),
    )
    _premise_rooted_at(monkeypatch, tmp_path)
    assert_arm_goes_red(premise.test_p13_import_order_is_checked_by_at_least_one_tool_everywhere)


def test_m19_removing_the_alembic_classification_is_caught(tmp_path, monkeypatch):
    """Without it ruff and isort disagree on 21 files and gate 2 or 3 is always red."""
    _write_pyproject(
        tmp_path, lambda text: text.replace('known-third-party = ["alembic"]', "known-third-party = []")
    )
    _premise_rooted_at(monkeypatch, tmp_path)
    assert_arm_goes_red(premise.test_p13_import_order_is_checked_by_at_least_one_tool_everywhere)


def test_m19b_removing_the_isort_configuration_entirely_is_caught(tmp_path, monkeypatch):
    _write_pyproject(tmp_path, lambda text: text.replace("[tool.isort]", "[tool.isort_disabled]"))
    _premise_rooted_at(monkeypatch, tmp_path)
    assert_arm_goes_red(premise.test_p13_import_order_is_checked_by_at_least_one_tool_everywhere)


# ---------------------------------------------------------------------------
# The mutation that checks the POPULATE-CHECK rather than the arm
# ---------------------------------------------------------------------------


def test_m20_a_specification_table_that_stops_parsing_fails_loudly(tmp_path, monkeypatch):
    """The arm that would otherwise hide every other spec-fidelity failure.

    If Section 24's table were reworded so `parse_spec_gates` matched nothing,
    P1 and P1b would compare the workflow against an empty list and pass. The
    populate-check in the `spec_gates` fixture turns that into a failure.

    F-4.14-A-12: the first version of this test asserted only that
    `parse_spec_gates` returns `[]` on reworded text, which is a CORRELATE of
    the populate-check rather than the populate-check itself. It never ran the
    fixture. This drives the real fixture against a real file.
    """
    reworded = "Merge-blocking gates, in order:\n\nnothing resembling a table here.\n"
    assert premise.parse_spec_gates(reworded) == []
    assert premise.parse_spec_gates("the gates are described in prose now.\n") == []

    spec = tmp_path / "requirements" / "Technical_specification.md"
    spec.parent.mkdir(parents=True)
    spec.write_text(reworded, encoding="utf-8")
    monkeypatch.setattr(premise, "SPEC_PATH", spec)

    # The fixture itself, invoked the way pytest would, must now fail.
    with pytest.raises(RED):
        premise.spec_gates.__wrapped__()

    # Positive control: the real document still parses to ten.
    real = premise.parse_spec_gates(
        (premise.REPO_ROOT / "requirements" / "Technical_specification.md").read_text(
            encoding="utf-8"
        )
    )
    assert len(real) == premise.EXPECTED_GATE_COUNT
