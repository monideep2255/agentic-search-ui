"""Mutation harness for build phase 4.14's CI premise gate.

Assertions that cannot fail are the most repeated failure in this repository's
`LEARNINGS.md`. This phase added three of its own, and each rewrite of the
premise gate was forced by a mutation the previous harness never attempted:

    Harness 1 mutated STRUCTURE: delete a gate, reorder steps, empty a key. It
    caught every mutation it contained. Then the judge and the adversary
    attacked the CONTENT of a command and landed 32 it never noticed.

    Harness 2 added content mutations. Then a fresh re-verifier attacked the
    SHELL SEMANTICS with `:;#ruff check`, which runs nothing, and neutralised
    eight of ten gates with all 97 tests green.

The lesson is now stated in the harness itself rather than learned again: a
mutation harness proves only what it mutates, and each layer that gets attacked
is one layer beneath the one the harness was defending.

Round 3 moved the shell out of the workflow entirely, so the mutation surface is
now two things, and BOTH are mutated below:

    The workflow, where a step body must EQUAL a script path.
    The scripts, where one anchored command line lives.

Every arm CALLS THE REAL PREMISE ARM against a mutated subject rather than
re-implementing its check. A control runs first: every arm must pass on the
unmutated subject, without which an unconditionally-failing arm would look like
a perfect detector.

Depends on:
    - tests.ci.test_ci_workflow_premise
    - .github/workflows/ci.yml, .github/gates/*.sh

Writes:
    - Nothing outside pytest's own tmp_path.
"""

from __future__ import annotations

import copy
import inspect
import re
import shutil
from pathlib import Path

import pytest
import yaml

from tests.ci import test_ci_workflow_premise as premise

Failed = pytest.fail.Exception
RED = (AssertionError, Failed)


# ---------------------------------------------------------------------------
# Running every arm
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


def run_every_arm(workflow: dict, spec_gates: list[tuple[int, str]]) -> list[str]:
    """Run every premise arm against `workflow`; return the names that went red.

    Which arm notices is deliberately not asserted. Pinning a mutation to a
    named arm makes this file brittle against an honest refactor of the premise
    gate, and what matters is that the defect cannot reach `develop` unnoticed.
    """
    red: list[str] = []
    for name, arm in sorted(vars(premise).items()):
        if not name.startswith("test_p") or not callable(arm):
            continue
        params = inspect.signature(arm).parameters
        cases: list[dict] = [{}]
        if "order" in params:
            cases = [
                {"order": order, "pattern": pattern, "description": description}
                for order, pattern, description in premise._GATE_COMMANDS
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


def gate_steps_of(workflow: dict):
    for job in workflow["jobs"].values():
        for step in job.get("steps", []) or []:
            if str(step.get("name", "")).startswith("Gate"):
                yield job, step


def step_named(workflow: dict, prefix: str) -> dict:
    for _job, step in gate_steps_of(workflow):
        if str(step["name"]).startswith(prefix):
            return step
    raise AssertionError(f"no step starting {prefix!r}")


# ---------------------------------------------------------------------------
# The control
# ---------------------------------------------------------------------------


def test_m0_control_every_arm_passes_on_the_real_subject(real_workflow, spec_gates):
    red = run_every_arm(real_workflow, spec_gates)
    assert not red, (
        f"these arms fail on the UNMUTATED subject, so every mutation below is noise: {red}"
    )


# ---------------------------------------------------------------------------
# Workflow mutations
# ---------------------------------------------------------------------------


def _shell_prefix(prefix: str):
    def mutate(workflow: dict) -> None:
        for _job, step in gate_steps_of(workflow):
            step["run"] = prefix + str(step.get("run", ""))

    return mutate


def _comment_out_with(template: str):
    def mutate(workflow: dict) -> None:
        for _job, step in gate_steps_of(workflow):
            step["run"] = template.format(command=str(step.get("run", "")))

    return mutate


def _append(suffix: str):
    def mutate(workflow: dict) -> None:
        for _job, step in gate_steps_of(workflow):
            step["run"] = str(step.get("run", "")) + suffix

    return mutate


def _continue_on_error(workflow: dict) -> None:
    for _job, step in gate_steps_of(workflow):
        step["continue-on-error"] = True


def _disable_gate_10(workflow: dict) -> None:
    step_named(workflow, "Gate 10")["if"] = False


def _hoist_a_secret(workflow: dict) -> None:
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


def _remove_schema_step(workflow: dict) -> None:
    for job in workflow["jobs"].values():
        job["steps"] = [
            step
            for step in job.get("steps", []) or []
            if "setup_schema" not in str(step.get("run", ""))
        ]


def _remove_db_skip_gate(workflow: dict) -> None:
    for job in workflow["jobs"].values():
        job["steps"] = [
            step
            for step in job.get("steps", []) or []
            if "gate04b" not in str(step.get("run", ""))
        ]


def _gate_5_loses_run_premise_gate(workflow: dict) -> None:
    (step_named(workflow, "Gate 5").get("env") or {}).pop("RUN_PREMISE_GATE", None)


def _repoint_at_a_missing_script(workflow: dict) -> None:
    step_named(workflow, "Gate 3")["run"] = ".github/gates/gate99_does_not_exist.sh"


def _delete_a_gate(workflow: dict) -> None:
    for job in workflow["jobs"].values():
        job["steps"] = [
            step
            for step in job.get("steps", []) or []
            if not str(step.get("name", "")).startswith("Gate 7")
        ]


def _invent_a_gate(workflow: dict) -> None:
    next(iter(workflow["jobs"].values()))["steps"].append(
        {"name": "Gate 11: nobody agreed to this", "run": ".github/gates/gate03_lint.sh"}
    )


def _reorder_gates(workflow: dict) -> None:
    for job in workflow["jobs"].values():
        indices = [
            index
            for index, step in enumerate(job.get("steps", []) or [])
            if re.match(r"^Gate \d+\b", str(step.get("name", "")))
        ]
        if len(indices) > 1:
            first, last = indices[0], indices[-1]
            job["steps"][first], job["steps"][last] = job["steps"][last], job["steps"][first]
            return


def _drop_pull_request_trigger(workflow: dict) -> None:
    key = "on" if "on" in workflow else True
    workflow[key] = {"push": {"branches": ["develop"]}}


def _remove_concurrency(workflow: dict) -> None:
    workflow.pop("concurrency", None)


_WORKFLOW_MUTATIONS = (
    # The attack that defeated round 2, and the variants its fix would have
    # needed enumerating one at a time. All are caught by ONE structural arm.
    ("RV-03", "the `:;#command` attack that beat round 2", _shell_prefix(":;#")),
    ("RV-03", "the `&&#` variant", _shell_prefix("true &&#")),
    ("RV-03", "the `||#` variant", _shell_prefix("false ||#")),
    ("RV-03", "the `(#` variant", _shell_prefix("(#")),
    ("RV-03", "a newline-separated second command", _shell_prefix("echo hi\n")),
    ("A-05", "body replaced by `true`, command kept in a comment", _comment_out_with("true  # {command}")),
    ("round 3", "a second command appended after the script path", _append(" || true")),
    ("round 3", "a redirect appended after the script path", _append(" >/dev/null 2>&1")),
    ("J-02", "continue-on-error on every gate", _continue_on_error),
    ("J-02", "`if: false` on gate 10", _disable_gate_10),
    ("J-02", "a secret hoisted to workflow-level env", _hoist_a_secret),
    ("J-04", "the postgres service swapped for redis:7", _swap_postgres_for_redis),
    ("J-04", "USER_DB_URL set to the empty string", _empty_user_db_url),
    ("F-4.14-03", "the postgres service removed entirely", _remove_postgres_service),
    ("F-4.14-03", "the schema-creation step removed", _remove_schema_step),
    ("F-4.14-03", "the no-unsanctioned-skips gate removed", _remove_db_skip_gate),
    ("A-03", "gate 5 loses RUN_PREMISE_GATE", _gate_5_loses_run_premise_gate),
    ("round 3", "a gate repointed at a script that does not exist", _repoint_at_a_missing_script),
    ("round 1", "a Section 24 gate deleted", _delete_a_gate),
    ("round 1", "a gate invented that Section 24 does not list", _invent_a_gate),
    ("round 1", "gates reordered within a job", _reorder_gates),
    ("round 1", "the pull_request trigger dropped", _drop_pull_request_trigger),
    ("round 1", "the concurrency block removed", _remove_concurrency),
)


@pytest.mark.parametrize(
    ("origin", "description", "mutation"),
    _WORKFLOW_MUTATIONS,
    ids=[f"{origin}-{description[:44]}" for origin, description, _ in _WORKFLOW_MUTATIONS],
)
def test_m_workflow_mutation_is_caught(origin, description, mutation, real_workflow, spec_gates):
    broken = copy.deepcopy(real_workflow)
    mutation(broken)
    red = run_every_arm(broken, spec_gates)
    assert red, (
        f"NO premise arm noticed this workflow mutation ({origin}: {description}). "
        f"That is a vacuous gate: the workflow can be changed this way and CI will "
        f"not tell anyone."
    )


# ---------------------------------------------------------------------------
# Script-content mutations. The commands moved here, so the mutations must too.
# ---------------------------------------------------------------------------


def _mutated_gates_dir(tmp_path: Path, script: str, transform) -> Path:
    target = tmp_path / "gates"
    shutil.copytree(premise.GATES_DIR, target)
    path = target / script
    path.write_text(transform(path.read_text(encoding="utf-8")), encoding="utf-8")
    path.chmod(0o755)
    return target


_SCRIPT_MUTATIONS = (
    (
        "J-02",
        "gate 3 re-scoped to `ruff check src`",
        "gate03_lint.sh",
        lambda text: text.replace("ruff check", "ruff check src"),
    ),
    (
        "J-02",
        "gate 2 stripped of --check-only, so isort rewrites and exits 0",
        "gate02_import_order.sh",
        lambda text: text.replace("--check-only ", ""),
    ),
    (
        "J-02",
        "gate 7 relaxed to --audit-level=critical",
        "gate07_frontend_audit.sh",
        lambda text: text.replace("--audit-level=high", "--audit-level=critical"),
    ),
    (
        "J-02",
        "gate 4 narrowed to a single directory",
        "gate04_unit_suite.sh",
        lambda text: text.replace('-m "not integration"', '-m "not integration" tests/ci/'),
    ),
    (
        "F-4.14-01",
        "gate 6 scoped back to the ambient environment",
        "gate06_python_audit.sh",
        lambda text: text.replace(" -r requirements.txt", ""),
    ),
    (
        "F-4.14-02",
        "gate 9 pointed at a renamed file",
        "gate09_required_paths.sh",
        lambda text: text.replace("test_required_paths.py", "test_renamed_away.py"),
    ),
    (
        "round 3",
        "a second executable line smuggled into a script",
        "gate03_lint.sh",
        lambda text: text + "echo 'and something else'\n",
    ),
    (
        "round 3",
        "a script's errexit removed",
        "gate03_lint.sh",
        lambda text: text.replace("set -euo pipefail", "true"),
    ),
    (
        "round 3",
        "a script's command commented out entirely",
        "gate03_lint.sh",
        lambda text: text.replace("\nruff check", "\n# ruff check"),
    ),
    (
        "A-03",
        "gate 5 loses its did-anything-run assertion",
        "gate05_integration.sh",
        lambda text: "\n".join(
            line for line in text.splitlines() if "assert_gate_ran.py" not in line
        ),
    ),
    (
        "A-03",
        "gate 5's not-run warning annotation removed",
        "gate05_integration.sh",
        lambda text: "\n".join(line for line in text.splitlines() if "::warning" not in line),
    ),
    (
        "A-07",
        "the gate 10 filter's commit check removed",
        "gate10_filter.sh",
        lambda text: text.replace("git cat-file -e", "true #"),
    ),
    (
        "F-4.14-03",
        "the db-skip assertion swapped for a no-op",
        "gate04b_no_unsanctioned_skips.sh",
        lambda text: text.replace(
            "python .github/scripts/assert_no_db_skips.py unit-results.xml", "true"
        ),
    ),
)


@pytest.mark.parametrize(
    ("origin", "description", "script", "transform"),
    _SCRIPT_MUTATIONS,
    ids=[f"{origin}-{description[:44]}" for origin, description, _, _ in _SCRIPT_MUTATIONS],
)
def test_m_script_mutation_is_caught(
    origin, description, script, transform, real_workflow, spec_gates, tmp_path, monkeypatch
):
    """The commands live in the scripts now, so the mutations live here too."""
    mutated = _mutated_gates_dir(tmp_path, script, transform)
    monkeypatch.setattr(premise, "GATES_DIR", mutated)
    red = run_every_arm(real_workflow, spec_gates)
    assert red, (
        f"NO premise arm noticed this SCRIPT mutation ({origin}: {description}, in "
        f"{script}). The command moved out of the workflow, so a harness that only "
        f"mutates the workflow proves nothing about it."
    )


# ---------------------------------------------------------------------------
# pyproject mutations
# ---------------------------------------------------------------------------


def _premise_rooted_at(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(premise, "REPO_ROOT", root)


def _write_pyproject(tmp_path: Path, transform) -> None:
    real = (premise.REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(transform(real), encoding="utf-8")


def test_m17_unpinning_ruff_is_caught(tmp_path, monkeypatch):
    _write_pyproject(tmp_path, lambda text: re.sub(r'"ruff==[\d.]+"', '"ruff>=0.4"', text))
    _premise_rooted_at(monkeypatch, tmp_path)
    with pytest.raises(RED):
        premise.test_p12_ruff_is_pinned_exactly_so_the_lint_gate_cannot_drift()


def test_m17b_a_commented_out_pin_is_caught(tmp_path, monkeypatch):
    """A-4.14-A-10: raw-text matching accepted a commented-out pin."""
    _write_pyproject(
        tmp_path, lambda text: text.replace('"ruff==0.16.0",', '# "ruff==0.16.0",\n    "ruff",')
    )
    _premise_rooted_at(monkeypatch, tmp_path)
    with pytest.raises(RED):
        premise.test_p12_ruff_is_pinned_exactly_so_the_lint_gate_cannot_drift()


def test_m18_disabling_ruffs_import_rule_is_caught(tmp_path, monkeypatch):
    _write_pyproject(
        tmp_path,
        lambda text: text.replace(
            "[tool.ruff.lint.isort]", '[tool.ruff.lint]\nignore = ["I001"]\n\n[tool.ruff.lint.isort]'
        ),
    )
    _premise_rooted_at(monkeypatch, tmp_path)
    with pytest.raises(RED):
        premise.test_p13_no_file_escapes_both_import_order_checkers()


def test_m18b_per_file_ignores_leaving_a_file_unchecked_is_caught(tmp_path, monkeypatch):
    """F-4.14-RV-05, the loophole the previous arm's spelling-check missed.

    `ignore` is not the only way to excuse a file from `I001`. Adding
    `per-file-ignores` for exactly the files isort's `extend_skip` names leaves
    them checked by NEITHER tool, and the old arm asserted only that the string
    `I001` was absent from `ignore`.
    """
    def transform(text: str) -> str:
        return text.replace(
            "[tool.ruff.lint.isort]",
            '[tool.ruff.lint.per-file-ignores]\n'
            '"src/system_03_search_agent/core/graph.py" = ["I001"]\n'
            '"src/system_03_search_agent/adapters/web_sse/app.py" = ["I001"]\n\n'
            "[tool.ruff.lint.isort]",
        )

    _write_pyproject(tmp_path, transform)
    _premise_rooted_at(monkeypatch, tmp_path)
    with pytest.raises(RED):
        premise.test_p13_no_file_escapes_both_import_order_checkers()


def test_m19_removing_the_alembic_classification_is_caught(tmp_path, monkeypatch):
    _write_pyproject(
        tmp_path,
        lambda text: text.replace('known-third-party = ["alembic"]', "known-third-party = []"),
    )
    _premise_rooted_at(monkeypatch, tmp_path)
    with pytest.raises(RED):
        premise.test_p13_no_file_escapes_both_import_order_checkers()


def test_m19b_removing_the_isort_configuration_entirely_is_caught(tmp_path, monkeypatch):
    _write_pyproject(tmp_path, lambda text: text.replace("[tool.isort]", "[tool.isort_disabled]"))
    _premise_rooted_at(monkeypatch, tmp_path)
    with pytest.raises(RED):
        premise.test_p13_no_file_escapes_both_import_order_checkers()


# ---------------------------------------------------------------------------
# The mutation that checks the POPULATE-CHECK rather than an arm
# ---------------------------------------------------------------------------


def test_m20_a_specification_table_that_stops_parsing_fails_loudly(tmp_path, monkeypatch):
    """If Section 24's table stopped parsing, P1 and P1b would compare against
    an empty list and pass. The `spec_gates` fixture's populate-check turns that
    into a failure, and this drives the REAL fixture rather than a correlate of
    it (F-4.14-A-12).
    """
    reworded = "Merge-blocking gates, in order:\n\nnothing resembling a table here.\n"
    assert premise.parse_spec_gates(reworded) == []
    assert premise.parse_spec_gates("the gates are described in prose now.\n") == []

    spec = tmp_path / "requirements" / "Technical_specification.md"
    spec.parent.mkdir(parents=True)
    spec.write_text(reworded, encoding="utf-8")
    monkeypatch.setattr(premise, "SPEC_PATH", spec)

    with pytest.raises(RED):
        premise.spec_gates.__wrapped__()

    real = premise.parse_spec_gates(
        (premise.REPO_ROOT / "requirements" / "Technical_specification.md").read_text(
            encoding="utf-8"
        )
    )
    assert len(real) == premise.EXPECTED_GATE_COUNT
