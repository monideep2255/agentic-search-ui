"""Premise gate for build phase 4.14: the CI workflow does what it says.

Every other premise gate in this repository grades a running artifact. This one
grades a configuration file, and that difference is the whole reason it exists.
A workflow's defects do not surface as a failing test. They surface as a green
check mark that verified less than the reader believes.

REWRITTEN IN THE SAME PHASE, after the judge and the adversary independently
broke the first version. That version asserted the workflow's PROSE: step names,
and substrings that could appear anywhere in a `run:` body. Between them the two
reviews landed 32 mutations that left it green, including:

  - Replacing every gate body with `true`, keeping the magic substrings in a
    shell comment. 15 of 16 arms stayed green. This is the same defect build
    phase 4.16 shipped, where a fixture matched the old values inside the
    comment documenting them.
  - `continue-on-error: true` on every gate.
  - `|| true` appended to gate 4.
  - Re-scoping gate 3 back to `ruff check src`, the exact defect this phase's
    own T-4.14-03 existed to fix.
  - Relaxing gate 7 to `--audit-level=critical`.
  - Stripping `--check-only` from gate 2, so isort REWRITES files and exits 0.
  - `if: false` on gate 10.
  - Hoisting a secret to workflow-level `env`, invisible to a per-job check.

The correction runs through the whole file: arms now read the EXECUTABLE text of
a step with comments stripped, assert the actual command and its load-bearing
flags, and reject the constructs that neutralise a step while leaving it
present. `_command_text` is the load-bearing helper; nothing here matches raw
`run:` bodies any more.

WHAT THIS GATE COVERS, stated so a gap is arguable rather than discovered:

    Covered      That the workflow parses. That all ten of Section 24's gates
                 are present, named, and in Section 24's order, with the gate
                 list read OUT OF the specification at test time rather than
                 copied here. That each gate runs its actual command with the
                 flags that make it mean something. That no gate is neutralised
                 by `continue-on-error`, `|| true`, or `if: false`. That the
                 three findings this phase filed cannot regress. That no gate
                 but gate 5 depends on a secret, at job OR workflow level. That
                 ruff is pinned and that every file's import order is checked by
                 at least one tool.

    NOT covered  Whether the workflow SUCCEEDS on GitHub's runners. Nothing
                 offline can know that. The only honest proof is the run on this
                 phase's own pull request.

    NOT covered  Whether the ten gates are MERGE-BLOCKING. They are not, and
                 nothing in this repository can make them so today: branch
                 protection needs a paid plan or a public repository, and
                 `gh api .../branches/develop/protection` returns 403. That is
                 finding F-4.14-A-04, it is a product-owner decision, and it is
                 recorded in `tracker/phase_4.14.md` rather than papered over
                 here. A red check next to a working Merge button is a real
                 improvement over nothing running at all, and it is not the same
                 claim as "merge-blocking".

Every arm carries a POPULATE-CHECK, per build phase 4.11's durable fix: an arm
that cannot distinguish "the control holds" from "nothing was loaded" is not an
arm.

Depends on:
    - .github/workflows/ci.yml
    - .github/scripts/assert_no_db_skips.py, assert_required_paths_ran.py,
      assert_gate_ran.py
    - requirements/Technical_specification.md (Section 24's gate table)
    - pyproject.toml, frontend/package.json

Writes:
    - Nothing.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
SPEC_PATH = REPO_ROOT / "requirements" / "Technical_specification.md"

EXPECTED_GATE_COUNT = 10


# ---------------------------------------------------------------------------
# Loading and the executable-text helper every arm depends on
# ---------------------------------------------------------------------------


def load_workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def load_workflow() -> dict:
    return yaml.safe_load(load_workflow_text())


def command_text(step: dict) -> str:
    """The EXECUTABLE text of a step: its `run:` body with comments removed.

    This is the fix for the attack that beat the first version of this file.
    A `run:` body of `true  # ruff check` contains the string "ruff check" and
    runs nothing at all. Every arm below matches against this rather than
    against the raw body, so a command preserved only in a comment does not
    count as a command.

    Comment stripping is deliberately naive about `#` inside quotes. It is the
    safe direction: a stripped-too-much body makes an arm FAIL, which someone
    then looks at. A stripped-too-little body makes an arm pass on a comment,
    which is the failure being fixed.
    """
    lines = []
    for raw in str(step.get("run", "")).splitlines():
        without_comment = re.sub(r"(?<!\S)#.*$", "", raw)
        if without_comment.strip():
            lines.append(without_comment)
    return "\n".join(lines)


def parse_spec_gates(spec_text: str) -> list[tuple[int, str]]:
    """Read Section 24's merge-blocking gate table out of the specification.

    Read at test time on purpose: a copy of the list in this file would be a
    second source of truth that drifts, and the point is to assert the workflow
    against the LOCKED document rather than against what someone remembered.
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


def gate_steps(workflow: dict) -> dict[int, list[dict]]:
    """Every step named `Gate N...`, keyed by N. A gate may have several steps."""
    found: dict[int, list[dict]] = {}
    for step in workflow_steps(workflow):
        match = re.match(r"^Gate (\d+)\b", str(step.get("name", "")))
        if match:
            found.setdefault(int(match.group(1)), []).append(step)
    return found


def gate_command(workflow: dict, order: int) -> str:
    """All executable text belonging to one gate, comments stripped."""
    return "\n".join(command_text(step) for step in gate_steps(workflow).get(order, []))


def job_containing_gate(workflow: dict, order: int) -> tuple[str, dict]:
    for name, job in workflow["jobs"].items():
        for step in job.get("steps", []) or []:
            if re.match(rf"^Gate {order}\b", str(step.get("name", ""))):
                return name, job
    raise AssertionError(f"no job carries gate {order}")


def all_command_text(workflow: dict) -> str:
    return "\n".join(command_text(step) for step in workflow_steps(workflow))


def pyproject() -> dict:
    return tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Fixtures, which are also this file's populate-checks
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def workflow_text() -> str:
    if not WORKFLOW_PATH.exists():
        pytest.fail(f"the CI workflow is missing at {WORKFLOW_PATH}")
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
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
    assert len(rows) == EXPECTED_GATE_COUNT, (
        f"parsed {len(rows)} gate rows out of Section 24, expected "
        f"{EXPECTED_GATE_COUNT}. The specification's table has moved or been "
        f"reworded, and this gate is now grading against nothing."
    )
    return rows


# ---------------------------------------------------------------------------
# Arm 1: fidelity to Section 24
# ---------------------------------------------------------------------------


def test_p1_all_ten_specification_gates_are_present(workflow, spec_gates):
    present = gate_steps(workflow)
    assert present, "no step in the workflow is named `Gate N:`"
    missing = [order for order, _ in spec_gates if order not in present]
    assert not missing, f"Section 24 gates with no step in the workflow: {missing}"


def test_p1b_the_workflow_invents_no_gate_the_specification_does_not_list(workflow, spec_gates):
    spec_orders = {order for order, _ in spec_gates}
    extra = sorted(set(gate_steps(workflow)) - spec_orders)
    assert not extra, f"the workflow declares gates absent from Section 24: {extra}"


def test_p2_gates_run_in_the_specification_order_within_each_job(workflow):
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
    assert checked_any, "no job carries more than one gate; the ordering arm ran empty"


# ---------------------------------------------------------------------------
# Arm 2: each gate runs its real command, with the flags that make it mean
# something. This is the arm class the first version of this file lacked
# entirely, and it is where 16 of the reviewers' mutations landed.
# ---------------------------------------------------------------------------

# (gate, required substrings in the gate's EXECUTABLE text, human description)
_REQUIRED_COMMANDS: tuple[tuple[int, tuple[str, ...], str], ...] = (
    (1, ("compileall",), "compiles every source tree"),
    # `--check-only` is load-bearing: without it isort REWRITES the files and
    # exits 0, so the gate silently formats instead of checking.
    (2, ("isort", "--check-only"), "checks import order without rewriting"),
    (3, ("ruff check",), "lints"),
    (4, ("pytest", "-m", "not integration"), "runs the unit suite"),
    (5, ("pytest", "-m integration"), "runs the integration suite"),
    # `-r requirements.txt` is F-4.14-01: bare `pip-audit` audits the ambient
    # environment rather than the project.
    (6, ("pip-audit", "-r requirements.txt"), "audits the declared dependencies"),
    # `--audit-level=high` is the threshold Section 24 sets. `critical` would
    # pass a High CVE.
    (7, ("npm audit", "--audit-level=high"), "audits the frontend dependencies"),
    (8, ("npm run build", "npm test"), "builds and tests the frontend"),
    (9, ("pytest", "test_required_paths.py"), "runs the required paths"),
    (10, ("playwright test", "accessibility.spec.ts"), "runs the accessibility spec"),
)


@pytest.mark.parametrize(("order", "required", "description"), _REQUIRED_COMMANDS)
def test_p16_each_gate_runs_its_real_command(workflow, order, required, description):
    """The gate's EXECUTABLE text, not its prose.

    Comments are stripped before matching (`command_text`), so a gate body of
    `true  # ruff check` fails this arm. That exact substitution left 15 of the
    16 arms in this file's first version green.
    """
    command = gate_command(workflow, order)
    assert command.strip(), (
        f"gate {order} has no executable command at all, only comments or nothing. "
        f"It is supposed to be the step that {description}."
    )
    for token in required:
        assert token in command, (
            f"gate {order} ({description}) does not run `{token}`. Its executable "
            f"text is:\n{command}"
        )


def test_p17_gate_3_lints_the_whole_repository(workflow):
    """`ruff check src` was the habit this phase existed to end.

    Before build phase 4.14 the repository ran `ruff check src`, which passed
    while `tests/` carried 5 errors and the harness scripts carried 30.
    Re-narrowing the gate to a path is the regression, and it is invisible to
    any arm that only checks the string `ruff check` appears.
    """
    command = gate_command(workflow, 3)
    assert "ruff check" in command, "gate 3 does not run ruff at all"
    for line in command.splitlines():
        stripped = line.strip()
        if not stripped.startswith("ruff check"):
            continue
        remainder = stripped[len("ruff check") :].strip()
        arguments = [token for token in remainder.split() if not token.startswith("-")]
        assert not arguments, (
            f"gate 3 narrows ruff to {arguments}, so anything outside those paths "
            f"goes unlinted. It must run over the whole repository."
        )


def test_p18_gate_4_runs_the_whole_unit_suite(workflow):
    """Narrowing gate 4 to one directory leaves the rest of the suite unrun."""
    command = gate_command(workflow, 4)
    pytest_lines = [line for line in command.splitlines() if "pytest" in line]
    assert pytest_lines, "gate 4 does not invoke pytest"
    for line in pytest_lines:
        tokens = line.strip().split()
        after = tokens[tokens.index("pytest") + 1 :] if "pytest" in tokens else []
        paths = [
            token
            for token in after
            if not token.startswith("-") and ("/" in token or token.endswith(".py"))
        ]
        assert not paths, (
            f"gate 4 restricts pytest to {paths}. The unit gate must run the whole "
            f"suite; a path argument silently drops everything else."
        )


# ---------------------------------------------------------------------------
# Arm 3: a gate that is present but neutralised
# ---------------------------------------------------------------------------


def test_p19_no_gate_is_neutralised(workflow):
    """A gate can be fully present and completely inert.

    `continue-on-error: true` makes a failing step green. `|| true` makes a
    failing command succeed. `if: false` makes the step never run. All three
    leave the step's name, its command and every flag exactly where an arm
    checking for those would find them.
    """
    checked_any = False
    for order, steps in sorted(gate_steps(workflow).items()):
        for step in steps:
            checked_any = True
            name = step.get("name")

            assert step.get("continue-on-error") not in (True, "true"), (
                f"gate {order} ({name}) sets continue-on-error, so it reports "
                f"success even when it fails. It is not a gate."
            )

            condition = str(step.get("if", "")).strip().lower()
            assert condition not in ("false", "${{ false }}"), (
                f"gate {order} ({name}) is disabled by `if: {condition}` and never runs"
            )

            command = command_text(step)
            assert not re.search(r"\|\|\s*true\b", command), (
                f"gate {order} ({name}) appends `|| true`, so its command cannot "
                f"fail the step:\n{command}"
            )
            assert not re.search(r"\bset\s+\+e\b", command), (
                f"gate {order} ({name}) disables errexit with `set +e`"
            )
    assert checked_any, "no gate steps were examined; this arm ran empty"


def test_p19b_no_job_carrying_a_gate_is_neutralised(workflow):
    """The same three tricks, one level up, where they disable every gate at once."""
    checked_any = False
    for order in sorted(gate_steps(workflow)):
        job_name, job = job_containing_gate(workflow, order)
        checked_any = True
        assert job.get("continue-on-error") not in (True, "true"), (
            f"job {job_name!r} carries gate {order} and sets continue-on-error"
        )
        condition = str(job.get("if", "")).strip().lower()
        assert condition not in ("false", "${{ false }}"), (
            f"job {job_name!r} carries gate {order} and is disabled by `if: {condition}`"
        )
    assert checked_any, "no gate-carrying job was examined; this arm ran empty"


# ---------------------------------------------------------------------------
# Arm 4: the findings this phase filed cannot silently regress
# ---------------------------------------------------------------------------


def test_p3_gate_6_audits_the_requirements_file_not_the_ambient_environment(workflow):
    """F-4.14-01. Also covered by P16; kept because the reason is specific."""
    command = gate_command(workflow, 6)
    assert "pip-audit" in command, "gate 6 does not run pip-audit"
    assert "-r requirements.txt" in command, (
        "gate 6 runs a bare `pip-audit`, which audits the ambient environment "
        "rather than this project's declared dependencies. See F-4.14-01."
    )


def test_p4_gate_9_points_at_a_file_that_exists_and_collects_tests(workflow):
    """F-4.14-02."""
    command = gate_command(workflow, 9)
    referenced = re.findall(r"(tests/[\w/]+\.py)", command)
    assert referenced, "gate 9 names no test file in its executable text"
    for rel in referenced:
        target = REPO_ROOT / rel
        assert target.exists(), f"gate 9 points at a file that does not exist: {rel}"
        source = target.read_text(encoding="utf-8")
        assert source.count("def test_") >= 2, (
            f"{rel} defines fewer than two tests; gate 9 would certify an almost-empty run"
        )


def test_p5_the_unit_job_runs_a_real_database_and_proves_it_reached_it(workflow):
    """F-4.14-03, both halves, with populate-checks that are not correlates.

    The first version accepted `redis:7` as the database, because it only looked
    for the string "postgres" anywhere in the service mapping and the
    `POSTGRES_*` environment keys satisfied that. It also accepted
    `USER_DB_URL: ""`. Both are checked properly here: the IMAGE must be
    postgres, and the URL must be a non-empty postgresql DSN.
    """
    job_name, job = job_containing_gate(workflow, 4)

    services = job.get("services") or {}
    assert services, f"job {job_name!r} declares no services at all"
    images = [str((spec or {}).get("image", "")) for spec in services.values()]
    assert any(image.startswith("postgres") for image in images), (
        f"job {job_name!r} runs no PostgreSQL image (found {images}), so every "
        f"database-backed test would skip and gate 4 would certify nothing. "
        f"See F-4.14-03."
    )

    url = str((job.get("env") or {}).get("USER_DB_URL", "")).strip()
    assert url.startswith("postgresql://"), (
        f"job {job_name!r} sets USER_DB_URL to {url!r}, which is not a PostgreSQL "
        f"DSN, so the tests cannot find the service even though it is running"
    )

    step_text = "\n".join(command_text(step) for step in job["steps"])
    assert "assert_no_db_skips.py" in step_text, (
        "nothing asserts that the database was actually reached. Without it the "
        "postgres service is an assumption, not a proof. See F-4.14-03."
    )
    assert "alembic upgrade head" in step_text, (
        "the job never creates the schema, so the tests connect to an empty "
        "database and fail on missing tables"
    )


def test_p15_gate_5_cannot_pass_silently_when_it_did_not_run(workflow):
    """F-4.14-A-03, both halves.

    Gate 5 legitimately exits 0 when no credential exists, and must say so
    loudly. The subtler half: with a credential present but unreachable, its
    arms skip and pytest exits 0 having passed nothing, which renders as an
    ordinary green check. Adding a credential must make the gate stricter, not
    quieter, so the executed path is asserted too.
    """
    command = gate_command(workflow, 5)
    assert "exit 0" in command, "gate 5 has no not-run path at all; this arm ran empty"
    assert "::warning" in command, (
        "gate 5's not-run path exits 0 without a warning annotation, so it renders "
        "as an ordinary green check"
    )
    assert "NOT RUN" in command, "gate 5's not-run path does not say so in its output"
    assert "assert_gate_ran.py" in command, (
        "gate 5 does not assert that its run executed anything. With a credential "
        "present but unreachable it exits 0 having passed zero tests. See F-4.14-A-03."
    )
    _, job = job_containing_gate(workflow, 5)
    env = {**(workflow.get("env") or {}), **(job.get("env") or {})}
    step_env = {}
    for step in gate_steps(workflow)[5]:
        step_env.update(step.get("env") or {})
    assert str({**env, **step_env}.get("RUN_PREMISE_GATE", "")).strip() == "1", (
        "gate 5 never sets RUN_PREMISE_GATE, and tests/conftest.py blocks all "
        "outbound HTTP without it, so its arms cannot reach the graph service "
        "whether or not it is up. See F-4.14-A-03."
    )


def test_p20_gate_10_fails_closed(workflow):
    """F-4.14-A-07.

    The path filter decides whether the WCAG gate runs. Every uncertain path
    through it must RUN the gate, because the alternative is a gate that quietly
    does not run and prints a false statement about why.
    """
    _, job = job_containing_gate(workflow, 10)
    filters = [
        step
        for step in job["steps"]
        if "GITHUB_OUTPUT" in command_text(step) and "touched" in command_text(step)
    ]
    assert filters, "gate 10 has no path-filter step; this arm ran empty"
    body = command_text(filters[0])

    assert "git cat-file -e" in body, (
        "the filter does not verify the base and head commits exist before "
        "diffing, so a shallow clone or a garbage-collected SHA silently skips "
        "the accessibility gate. See F-4.14-A-07."
    )
    assert body.count("touched=true") >= 3, (
        "the filter has fewer than three paths that RUN the gate. It must fail "
        "closed: every error path runs the gate rather than skipping it."
    )
    assert not re.search(r"if\s+git diff", body), (
        "the filter puts `git diff` directly in an `if` condition, where errexit "
        "is suspended, so any git failure takes the skip branch. See F-4.14-A-07."
    )


# ---------------------------------------------------------------------------
# Arm 5: the commands are real commands this repository has
# ---------------------------------------------------------------------------


def test_p6_every_helper_script_the_workflow_calls_exists(workflow):
    referenced = set(re.findall(r"(\.github/scripts/[\w.\-]+\.py)", all_command_text(workflow)))
    assert referenced, "the workflow calls no helper script; this arm ran empty"
    for rel in sorted(referenced):
        assert (REPO_ROOT / rel).exists(), f"the workflow calls a missing script: {rel}"


def test_p7_gate_2_lints_paths_that_exist(workflow):
    """isort exits 0 on a path that is not there, so the paths matter."""
    command = gate_command(workflow, 2)
    assert "isort" in command, "gate 2 does not run isort"
    paths = [
        token
        for token in command.split()
        if not token.startswith("-") and token not in {"isort"} and "=" not in token
    ]
    assert paths, "gate 2 passes isort no paths at all, so it checks nothing"
    for path in paths:
        assert (REPO_ROOT / path).exists(), f"gate 2 lints a path that does not exist: {path}"


def test_p8_frontend_gates_call_scripts_that_package_json_defines(workflow):
    package = json.loads((REPO_ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    scripts = package.get("scripts") or {}
    assert scripts, "frontend/package.json defines no scripts; this arm ran empty"

    invoked = set(re.findall(r"npm run ([\w:-]+)", all_command_text(workflow)))
    assert invoked, "the workflow invokes no `npm run` script; this arm ran empty"
    for name in sorted(invoked):
        assert name in scripts, f"the workflow runs `npm run {name}`, which package.json lacks"


def test_p9_gate_10_points_at_a_playwright_spec_that_exists(workflow):
    command = gate_command(workflow, 10)
    specs = re.findall(r"(e2e/[\w.\-]+\.spec\.ts)", command)
    assert specs, "gate 10 names no spec file"
    for rel in specs:
        assert (REPO_ROOT / "frontend" / rel).exists(), (
            f"gate 10 points at a spec that does not exist: {rel}"
        )


# ---------------------------------------------------------------------------
# Arm 6: the workflow's own properties
# ---------------------------------------------------------------------------


def test_p10_ci_runs_on_pull_requests(workflow):
    """PyYAML parses a bare `on:` key as the boolean True, which is a real trap."""
    triggers = workflow.get("on", workflow.get(True))
    assert triggers, "the workflow declares no triggers"
    assert "pull_request" in triggers, (
        "CI does not run on pull requests, which is the only trigger that can stop "
        "a bad merge before it auto-deploys"
    )


def test_p11_no_gate_but_gate_5_depends_on_a_secret(workflow):
    """A fork's pull request must get the same verdict as a branch's.

    Checked at WORKFLOW level as well as job level: the first version dumped
    each job and missed a secret hoisted to the top-level `env`, which reaches
    every job including the gate-carrying ones.
    """
    workflow_env = yaml.safe_dump(workflow.get("env") or {})
    assert "secrets." not in workflow_env, (
        "a secret is declared in the workflow-level `env`, so it reaches every "
        "gate and a fork's pull request cannot get the same verdict"
    )

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
    """Parsed as TOML, not matched as raw text.

    The first version matched the raw file, so a COMMENTED-OUT pin satisfied it.
    """
    dev = pyproject()["project"]["optional-dependencies"]["dev"]
    assert dev, "the dev extra is empty; this arm ran empty"
    ruff = [item for item in dev if item.replace(" ", "").startswith("ruff")]
    assert ruff, f"ruff is not declared in the dev extra: {dev}"
    assert all(re.fullmatch(r"ruff==\d+\.\d+\.\d+", item.replace(" ", "")) for item in ruff), (
        f"ruff is not pinned to an exact version ({ruff}), so gate 3's meaning "
        f"changes whenever the runner resolves a newer release. This repository "
        f"sets no explicit `select`, so the enabled rule set IS the version."
    )


def test_p13_import_order_is_checked_by_at_least_one_tool_everywhere():
    """The correction to this phase's own worst judgement call.

    The first version disabled ruff's `I001` repository-wide and asserted that
    it stayed disabled, on the premise that ruff and isort were irreconcilable.
    Measurement rejected it: `known-third-party = ["alembic"]` takes the
    disagreement from 23 files to 2. Both tools now run, and what this arm
    defends is the real property: no file is skipped by BOTH.
    """
    config = pyproject()
    ruff_ignore = config.get("tool", {}).get("ruff", {}).get("lint", {}).get("ignore", [])
    assert "I001" not in ruff_ignore, (
        "ruff's I001 is ignored repository-wide, so every file isort skips goes "
        "completely unchecked for import order. Fix the disagreement with "
        "`known-third-party` instead of disabling the rule."
    )

    isort_config = config.get("tool", {}).get("isort", {})
    assert isort_config, "isort is not configured; gate 2 has no owner"
    ruff_isort = config["tool"]["ruff"]["lint"]["isort"]
    assert "alembic" in ruff_isort.get("known-third-party", []), (
        "ruff is not told that `alembic` is third party, so it classifies "
        "`from alembic import op` as first-party because a directory of that "
        "name exists, and disagrees with isort on 21 files"
    )

    # The files isort skips must still be covered by ruff, which they are only
    # while I001 is enabled. Asserted rather than assumed.
    for skipped in isort_config.get("extend_skip", []):
        assert (REPO_ROOT / skipped).exists(), (
            f"isort skips {skipped}, which does not exist. A stale skip entry "
            f"hides the day a real file needs one."
        )


def test_p14_the_workflow_cancels_superseded_pull_request_runs(workflow):
    concurrency = workflow.get("concurrency")
    assert concurrency, "the workflow sets no concurrency group"
    assert concurrency.get("group"), "the concurrency block names no group"
