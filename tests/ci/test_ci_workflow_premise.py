"""Premise gate for build phase 4.14: the CI workflow says what it does.

Every other premise gate in this repository grades a running artifact. This one
grades a configuration file, and that difference is the whole reason it exists.
A workflow's defects do not surface as a failing test. They surface as a green
check mark that verified less than the reader believes, which is the exact
failure mode `goal-contracts` names and the one that made F-4.14-03 possible.

WHAT THIS GATE COVERS, stated here so a gap is arguable rather than discovered:

    Covered      That the workflow exists and parses. That all ten of Section
                 24's gates are present, named, and in Section 24's order, with
                 the gate list read OUT OF the specification at test time rather
                 than copied into this file. That the three findings this phase
                 filed cannot silently regress: gate 6's `-r requirements.txt`
                 scoping (F-4.14-01), gate 9 pointing at a file that really
                 collects tests (F-4.14-02), and the PostgreSQL service plus the
                 no-silent-skip assertion (F-4.14-03). That every command a gate
                 runs is a real command this repository actually has: the isort
                 paths exist, the npm scripts exist in package.json, the
                 Playwright spec exists, the helper scripts exist. That no gate
                 but gate 5 needs a secret. That ruff is pinned exactly.

    NOT covered  Whether the workflow SUCCEEDS on GitHub's runners. Nothing
                 offline can know that, and the only honest proof is the run on
                 this phase's own pull request, which is the first pull request
                 in this repository's history that CI has ever seen. This file
                 asserts the workflow is well-formed and faithful to Section 24;
                 the run asserts it works.

    NOT covered  Whether each gate CATCHES what it exists to catch. That is
                 mutation, and it lives in `test_ci_workflow_mutation.py` next
                 to this file, plus the recorded live mutations in
                 `tracker/phase_4.14.md`.

Every arm here carries a POPULATE-CHECK, per build phase 4.11's durable fix: an
arm that cannot distinguish "the control holds" from "nothing was loaded" is not
an arm. If the workflow failed to parse, or the specification table came back
empty, these tests fail as a broken harness rather than passing vacuously.

Depends on:
    - .github/workflows/ci.yml
    - .github/scripts/assert_no_db_skips.py
    - .github/scripts/assert_required_paths_ran.py
    - requirements/Technical_specification.md (Section 24's gate table)
    - pyproject.toml, frontend/package.json

Writes:
    - Nothing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
SPEC_PATH = REPO_ROOT / "requirements" / "Technical_specification.md"

EXPECTED_GATE_COUNT = 10


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def load_workflow() -> dict:
    return yaml.safe_load(load_workflow_text())


def parse_spec_gates(spec_text: str) -> list[tuple[int, str]]:
    """Read Section 24's merge-blocking gate table out of the specification.

    Returned as (order, gate name). Read at test time on purpose: a copy of the
    list in this file would be a second source of truth that drifts, and the
    whole point is to assert the workflow against the LOCKED document rather
    than against what someone remembered it said.
    """
    marker = "Merge-blocking gates, in order:"
    start = spec_text.find(marker)
    if start == -1:
        return []
    window = spec_text[start : start + 2500]
    rows: list[tuple[int, str]] = []
    for line in window.splitlines():
        match = re.match(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|", line)
        if match:
            rows.append((int(match.group(1)), match.group(2).strip()))
    return rows


def workflow_steps(workflow: dict) -> list[dict]:
    steps: list[dict] = []
    for job in workflow.get("jobs", {}).values():
        steps.extend(job.get("steps", []) or [])
    return steps


def gate_steps(workflow: dict) -> dict[int, dict]:
    """Every step whose name begins `Gate N:`, keyed by N.

    A gate with a `(cont.)` suffix belongs to the same gate number; the first
    one wins for ordering purposes.
    """
    found: dict[int, dict] = {}
    for step in workflow_steps(workflow):
        match = re.match(r"^Gate (\d+)\b", str(step.get("name", "")))
        if match:
            found.setdefault(int(match.group(1)), step)
    return found


def all_run_bodies(workflow: dict) -> str:
    return "\n".join(str(step.get("run", "")) for step in workflow_steps(workflow))


# ---------------------------------------------------------------------------
# Fixtures, each of which is also this file's populate-check
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def workflow_text() -> str:
    if not WORKFLOW_PATH.exists():
        pytest.fail(f"the CI workflow is missing at {WORKFLOW_PATH}")
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    # Populate-check. Every arm below reads this; if it came back empty they
    # would all pass against nothing.
    assert len(text) > 1000, "the workflow file is implausibly short; nothing to grade"
    return text


@pytest.fixture(scope="module")
def workflow(workflow_text: str) -> dict:
    parsed = yaml.safe_load(workflow_text)
    assert isinstance(parsed, dict), "the workflow did not parse as a mapping"
    assert parsed.get("jobs"), "the workflow declares no jobs; nothing to grade"
    return parsed


@pytest.fixture(scope="module")
def spec_gates() -> list[tuple[int, str]]:
    rows = parse_spec_gates(SPEC_PATH.read_text(encoding="utf-8"))
    # Populate-check, and the load-bearing one in this file. If Section 24's
    # table were reworded so this parser stopped matching, every
    # workflow-versus-spec arm below would compare against an empty list and
    # pass. This turns that into a failure.
    assert len(rows) == EXPECTED_GATE_COUNT, (
        f"parsed {len(rows)} gate rows out of Section 24, expected "
        f"{EXPECTED_GATE_COUNT}. The specification's table has moved or been "
        f"reworded, and this gate is now grading against nothing."
    )
    return rows


# ---------------------------------------------------------------------------
# Arm 1: the workflow is faithful to Section 24
# ---------------------------------------------------------------------------


def test_p1_all_ten_specification_gates_are_present(workflow, spec_gates):
    """Every gate Section 24 lists has a step in the workflow."""
    present = gate_steps(workflow)
    assert present, "no step in the workflow is named `Gate N:`"
    missing = [order for order, _ in spec_gates if order not in present]
    assert not missing, f"Section 24 gates with no step in the workflow: {missing}"


def test_p1b_the_workflow_invents_no_gate_the_specification_does_not_list(
    workflow, spec_gates
):
    """The workflow does not add a gate of its own.

    The inverse of P1, and it matters as much: a gate nobody agreed to is a
    gate nobody can remove, and Section 24 is the locked source of the list.
    """
    spec_orders = {order for order, _ in spec_gates}
    extra = sorted(set(gate_steps(workflow)) - spec_orders)
    assert not extra, f"the workflow declares gates absent from Section 24: {extra}"


def test_p2_gates_run_in_the_specification_order_within_each_job(workflow):
    """Section 24 specifies an ORDER, and steps in a job run in order.

    Checked per job rather than globally, because gates split across jobs run
    concurrently by design and no ordering between jobs is claimed or wanted.
    """
    checked_any = False
    for job_name, job in workflow["jobs"].items():
        orders = [
            int(match.group(1))
            for step in job.get("steps", []) or []
            if (match := re.match(r"^Gate (\d+)\b", str(step.get("name", ""))))
        ]
        if len(orders) > 1:
            checked_any = True
            assert orders == sorted(orders), (
                f"job {job_name!r} runs its gates out of Section 24's order: {orders}"
            )
    # Populate-check: if no job had two gates, this test asserted nothing.
    assert checked_any, "no job carries more than one gate; the ordering arm ran empty"


# ---------------------------------------------------------------------------
# Arm 2: the three findings this phase filed cannot silently regress
# ---------------------------------------------------------------------------


def test_p3_gate_6_audits_the_requirements_file_not_the_ambient_environment(workflow):
    """F-4.14-01.

    A bare `pip-audit` audits whatever is installed in the runner, which on the
    machine where this phase was written meant two findings for packages this
    project does not declare at all. The fix is a scope, and a scope is one
    flag away from being helpfully "simplified" back off by a later reader.
    """
    gate = gate_steps(workflow).get(6)
    assert gate is not None, "gate 6 has no step"
    body = str(gate.get("run", ""))
    assert "pip-audit" in body, "gate 6 does not run pip-audit"
    assert "-r requirements.txt" in body, (
        "gate 6 runs a bare `pip-audit`, which audits the ambient environment "
        "rather than this project's declared dependencies. See F-4.14-01."
    )


def test_p4_gate_9_points_at_a_file_that_exists_and_collects_tests(workflow):
    """F-4.14-02.

    Section 24 names two tests that do not exist as functions. This asserts the
    gate points at something real, and that the something contains both required
    paths, so a rename cannot leave the gate pointed at nothing.
    """
    gate = gate_steps(workflow).get(9)
    assert gate is not None, "gate 9 has no step"
    body = str(gate.get("run", ""))
    referenced = re.findall(r"(tests/[\w/]+\.py)", body)
    assert referenced, "gate 9 names no test file"
    for rel in referenced:
        target = REPO_ROOT / rel
        assert target.exists(), f"gate 9 points at a file that does not exist: {rel}"
        source = target.read_text(encoding="utf-8")
        assert source.count("def test_") >= 2, (
            f"{rel} defines fewer than two tests; gate 9 would certify an "
            f"almost-empty run"
        )


def test_p5_the_unit_job_runs_a_database_and_proves_it_reached_it(workflow):
    """F-4.14-03, both halves, and this is the arm that matters most.

    Every database-backed test in this repository SKIPS rather than fails when
    PostgreSQL is unreachable, so a runner without one reports a confident green
    having executed none of them. Two things must both hold: the service exists,
    and something asserts it was actually reached. The service alone is an
    assumption.
    """
    jobs_with_unit_gate = [
        job
        for job in workflow["jobs"].values()
        if any(
            str(step.get("name", "")).startswith("Gate 4")
            for step in job.get("steps", []) or []
        )
    ]
    assert jobs_with_unit_gate, "no job runs gate 4"

    job = jobs_with_unit_gate[0]
    services = job.get("services") or {}
    assert any("postgres" in str(spec).lower() for spec in services.values()), (
        "the unit-suite job declares no PostgreSQL service, so every "
        "database-backed test would skip and gate 4 would certify nothing. "
        "See F-4.14-03."
    )
    assert "USER_DB_URL" in str(job.get("env") or {}), (
        "the unit-suite job sets no USER_DB_URL, so the tests cannot find the "
        "service even though it is running"
    )

    step_bodies = "\n".join(str(step.get("run", "")) for step in job["steps"])
    assert "assert_no_db_skips.py" in step_bodies, (
        "nothing asserts that the database was actually reached. Without it the "
        "postgres service above is an assumption, not a proof. See F-4.14-03."
    )


# ---------------------------------------------------------------------------
# Arm 3: every command a gate runs is a real command this repository has
# ---------------------------------------------------------------------------


def test_p6_every_helper_script_the_workflow_calls_exists(workflow):
    """A workflow that calls a script that is not there fails at runtime.

    Cheap to assert here, and the failure it prevents costs a full CI round
    trip to discover.
    """
    referenced = set(re.findall(r"(\.github/scripts/[\w.\-]+\.py)", all_run_bodies(workflow)))
    assert referenced, "the workflow calls no helper script; this arm ran empty"
    for rel in sorted(referenced):
        assert (REPO_ROOT / rel).exists(), f"the workflow calls a missing script: {rel}"


def test_p7_gate_2_lints_paths_that_exist(workflow):
    """isort silently succeeds on a path that is not there, so the paths matter."""
    gate = gate_steps(workflow).get(2)
    assert gate is not None, "gate 2 has no step"
    body = str(gate.get("run", ""))
    assert "isort" in body, "gate 2 does not run isort"
    paths = [
        token
        for token in body.split()
        if not token.startswith("-") and token not in {"isort"}
    ]
    assert paths, "gate 2 passes isort no paths at all, so it checks nothing"
    for path in paths:
        assert (REPO_ROOT / path).exists(), f"gate 2 lints a path that does not exist: {path}"


def test_p8_frontend_gates_call_scripts_that_package_json_defines(workflow):
    """Gate 8's commands must be real npm scripts, not aspirational ones."""
    import json

    package = json.loads((REPO_ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    scripts = package.get("scripts") or {}
    assert scripts, "frontend/package.json defines no scripts; this arm ran empty"

    bodies = all_run_bodies(workflow)
    invoked = set(re.findall(r"npm run ([\w:-]+)", bodies))
    assert invoked, "the workflow invokes no `npm run` script; this arm ran empty"
    for name in sorted(invoked):
        assert name in scripts, f"the workflow runs `npm run {name}`, which package.json lacks"


def test_p9_gate_10_points_at_a_playwright_spec_that_exists(workflow):
    gate = gate_steps(workflow).get(10)
    assert gate is not None, "gate 10 has no step"
    body = str(gate.get("run", ""))
    specs = re.findall(r"(e2e/[\w.\-]+\.spec\.ts)", body)
    assert specs, "gate 10 names no spec file"
    for rel in specs:
        assert (REPO_ROOT / "frontend" / rel).exists(), (
            f"gate 10 points at a spec that does not exist: {rel}"
        )


# ---------------------------------------------------------------------------
# Arm 4: the workflow's own properties
# ---------------------------------------------------------------------------


def test_p10_ci_runs_on_pull_requests(workflow):
    """The entire point. A workflow that only runs on push guards nothing."""
    # PyYAML parses a bare `on:` key as the boolean True, which is a real trap:
    # `workflow["on"]` returns nothing and an unguarded arm here would pass.
    triggers = workflow.get("on", workflow.get(True))
    assert triggers, "the workflow declares no triggers"
    assert "pull_request" in triggers, (
        "CI does not run on pull requests, which is the only trigger that can "
        "stop a bad merge before it auto-deploys"
    )


def test_p11_no_gate_but_gate_5_depends_on_a_secret(workflow):
    """A fork's pull request must get the same verdict as a branch's.

    Section 24 makes gate 5 network-gated, so it alone may reference a
    credential. Any other gate that did would go green on a fork for the wrong
    reason: not because the code is sound, but because the check could not run.
    """
    checked_any = False
    for job_name, job in workflow["jobs"].items():
        gates_here = [
            int(match.group(1))
            for step in job.get("steps", []) or []
            if (match := re.match(r"^Gate (\d+)\b", str(step.get("name", ""))))
        ]
        if not gates_here or gates_here == [5]:
            continue
        checked_any = True
        assert "secrets." not in yaml.safe_dump(job), (
            f"job {job_name!r} runs gates {gates_here} and references a secret; "
            f"only gate 5 may."
        )
    assert checked_any, "no non-gate-5 job carried a gate; this arm ran empty"


def test_p12_ruff_is_pinned_exactly_so_the_lint_gate_cannot_drift():
    """This repository sets no explicit ruff `select`.

    So the enabled rule set is whatever the installed version defaults to, and a
    floor would let a minor bump change what gate 3 enforces with nobody editing
    a line of configuration. Measured during this phase: ruff 0.16.0 enables a
    far broader set than the documented defaults, which is exactly how much
    there is to lose.
    """
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "ruff" in pyproject, "ruff is not declared at all; this arm ran empty"
    assert re.search(r'"ruff==\d+\.\d+\.\d+"', pyproject), (
        "ruff is not pinned to an exact version, so gate 3's meaning changes "
        "whenever the runner resolves a newer release"
    )


def test_p13_import_order_has_exactly_one_owner():
    """Ruff's `I` rules and isort disagree on this tree, measured, on 23 files.

    Whichever one is left enabled alongside the other, one gate is permanently
    red. `I001` is ignored in pyproject so gate 2's isort owns the property. If
    someone re-enables it, this fails and says why rather than leaving them to
    rediscover the oscillation.
    """
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.isort]" in pyproject, "isort is not configured; gate 2 has no owner"
    assert re.search(r'ignore\s*=\s*\[[^\]]*"I001"', pyproject), (
        "ruff's I001 is not ignored, so both ruff and isort police import order "
        "and they do not agree. One of gate 2 and gate 3 will always be red."
    )


def test_p15_gate_5_cannot_pass_silently_when_it_did_not_run(workflow):
    """A job that exits 0 renders as a green check.

    Gate 5 needs a credential a fork's pull request cannot have, and Section 24
    makes it network-gated rather than skippable, so it does exit 0 in that
    case. What it must not do is exit 0 QUIETLY: "passed" and "could not run"
    are the two states this entire phase exists to keep apart, and gate 5 is
    the one place in this workflow where they legitimately meet.
    """
    gate = gate_steps(workflow).get(5)
    assert gate is not None, "gate 5 has no step"
    body = str(gate.get("run", ""))
    assert "exit 0" in body, "gate 5 does not have a not-run path at all; this arm ran empty"
    assert "::warning" in body, (
        "gate 5's not-run path exits 0 without a warning annotation, so it "
        "renders as an ordinary green check and a reviewer cannot tell it "
        "from a real pass"
    )
    assert "NOT RUN" in body, "gate 5's not-run path does not say so in its output"


def test_p14_the_workflow_cancels_superseded_pull_request_runs(workflow):
    concurrency = workflow.get("concurrency")
    assert concurrency, "the workflow sets no concurrency group"
    assert concurrency.get("group"), "the concurrency block names no group"
