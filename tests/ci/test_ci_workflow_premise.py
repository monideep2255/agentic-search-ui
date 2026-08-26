"""Premise gate for build phase 4.14: the CI workflow does what it says.

Every other premise gate here grades a running artifact. This one grades
configuration, and that is why it exists: a workflow's defects do not surface as
a failing test, they surface as a green check that verified less than the reader
believes.

REWRITTEN TWICE IN ONE PHASE, and the second rewrite is a change of APPROACH
rather than another patch, made by product-owner decision after the phase hit
its Rule 4 stop.

    Version 1 asserted the workflow's PROSE: step names, and substrings that
    could appear anywhere in a `run:` body. The judge and the adversary landed
    32 mutations it did not notice.

    Version 2 asserted the workflow's SHELL, matching substrings after stripping
    comments. A fresh re-verifier defeated it with `:;#ruff check`, which runs
    NOTHING: bash begins a comment at `#` whenever `#` starts a word, and `;`
    ends a word, while the stripper only treated `#` as a comment after
    whitespace. Eight of ten gates were neutralised with all 97 tests green.

Handling `;#` too would have been the fifth instance of a class whose sixth was
always going to be `&&#`, `(#`, or a YAML block scalar. Matching substrings
inside arbitrary shell is the thing that cannot be made safe, so THE SHELL LEFT
THE WORKFLOW. Every gate step's `run:` is now exactly one token: the path of a
script in `.github/gates/`.

That converts the check from a substring search over arbitrary text into two
whole-string equalities, neither of which has room for a comment or a second
command:

  - A gate step's `run:` must EQUAL its script's path.
  - Each script is CANONICAL: shebang, `set -euo pipefail`, comments, and
    exactly ONE executable line, matched anchored at both ends.

WHAT THIS GATE COVERS, so a gap is arguable rather than discovered:

    Covered      That the workflow parses. That Section 24's ten gates are all
                 present, in order, with the list read OUT OF the specification
                 at test time. That every gate step is a bare script invocation
                 and nothing else. That each script is canonical and runs the
                 command Section 24 names, with the flags that make it mean
                 something. That no gate is neutralised. That no gate but gate 5
                 depends on a secret, at job OR workflow level. That ruff is
                 pinned. That no file escapes BOTH import-order checkers.

    NOT covered  Whether a gate actually goes RED when the thing it guards
                 breaks. That is behavioural and no reading proves it;
                 `tests/ci/test_gate_scripts.py` executes the cheap gates
                 against broken fixtures and states which ones it cannot.

    NOT covered  Whether the gates are MERGE-BLOCKING. They are not, and nothing
                 in this repository can make them so: branch protection needs a
                 paid plan or a public repository (F-4.14-A-04). That is a
                 product-owner decision recorded in `tracker/phase_4.14.md`, not
                 papered over here.

Every arm carries a POPULATE-CHECK: an arm that cannot distinguish "the control
holds" from "nothing was loaded" is not an arm.

Depends on:
    - .github/workflows/ci.yml, .github/gates/*.sh, .github/scripts/*.py
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
GATES_DIR = REPO_ROOT / ".github" / "gates"
SPEC_PATH = REPO_ROOT / "requirements" / "Technical_specification.md"

EXPECTED_GATE_COUNT = 10

# Lines a canonical gate script may carry that are not its command: the shebang,
# the errexit line, comments, and blanks.
_BOILERPLATE = re.compile(r"^\s*(#|$)|^#!/usr/bin/env bash$|^set -[eux]+o pipefail$|^set [+-][eux]+$")


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def load_workflow() -> dict:
    return yaml.safe_load(load_workflow_text())


def parse_spec_gates(spec_text: str) -> list[tuple[int, str]]:
    """Read Section 24's gate table out of the specification at test time.

    Read rather than copied, so this grades the workflow against the LOCKED
    document instead of against what someone remembered it said.
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
    found: dict[int, list[dict]] = {}
    for step in workflow_steps(workflow):
        match = re.match(r"^Gate (\d+)\b", str(step.get("name", "")))
        if match:
            found.setdefault(int(match.group(1)), []).append(step)
    return found


def job_containing_gate(workflow: dict, order: int) -> tuple[str, dict]:
    for name, job in workflow["jobs"].items():
        for step in job.get("steps", []) or []:
            if re.match(rf"^Gate {order}\b", str(step.get("name", ""))):
                return name, job
    raise AssertionError(f"no job carries gate {order}")


def invoked_script(step: dict) -> str:
    """The single script path a step invokes, or "" if it is not a bare call.

    This is the whole-string check that replaced substring matching. A body has
    to BE a script path. `:;#ruff check` is not one, and neither is
    `.github/gates/gate03_lint.sh; rm -rf /`.
    """
    body = str(step.get("run", "")).strip()
    if re.fullmatch(r"(\.\./)?\.github/gates/[A-Za-z0-9_]+\.sh", body):
        return body
    return ""


def script_path(step: dict) -> Path | None:
    invoked = invoked_script(step)
    if not invoked:
        return None
    return GATES_DIR / Path(invoked).name


def script_command(path: Path | None) -> str:
    """The one executable line of a canonical gate script.

    Fails as an ASSERTION rather than an OSError when the step is not a bare
    invocation or the script is missing. That distinction matters more than it
    looks: the mutation harness treats an assertion as "the arm caught it" and
    an arbitrary exception as a broken harness, so an arm that raised
    `FileNotFoundError` here would score as neither caught nor missed.
    """
    assert path is not None, (
        "this step does not invoke a gate script, so it has no command to read. "
        "A gate step's `run:` must be exactly a path under .github/gates/."
    )
    assert path.exists(), f"the gate script {path} does not exist"
    lines = [
        line.rstrip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if not _BOILERPLATE.match(line.strip())
    ]
    return "\n".join(lines)


def pyproject() -> dict:
    return tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Fixtures, which are also the populate-checks
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
        f"{EXPECTED_GATE_COUNT}. The table has moved or been reworded, and this "
        f"gate is now grading against nothing."
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
# Arm 2: the workflow contains no shell at all. THE arm of this rewrite.
# ---------------------------------------------------------------------------


def test_p21_every_gate_step_is_a_bare_script_invocation(workflow):
    """The property that removes the whole defect class.

    A step body must EQUAL a script path. Not contain one. There is no room in
    a whole-string equality for `:;#`, for a second command after `;`, or for a
    comment that hides one.
    """
    gates = gate_steps(workflow)
    assert gates, "no gate steps at all; this arm ran empty"
    for order, steps in sorted(gates.items()):
        for step in steps:
            body = str(step.get("run", "")).strip()
            assert invoked_script(step), (
                f"gate {order} ({step.get('name')}) does not invoke a gate script. "
                f"Its body must be exactly a path under .github/gates/, with no "
                f"shell around it, because shell in a workflow cannot be verified "
                f"by reading. Got:\n{body!r}"
            )


def test_p22_no_step_anywhere_in_the_workflow_contains_shell(workflow):
    """Not only the gate steps. Setup steps run before every gate.

    A compromised install step is a compromised gate, so the same rule applies
    to every `run:` in the file.
    """
    offenders = []
    for step in workflow_steps(workflow):
        body = str(step.get("run", "")).strip()
        if not body:
            continue
        if not invoked_script(step):
            offenders.append((step.get("name"), body))
    assert not offenders, (
        "these steps carry shell rather than invoking a script under "
        ".github/gates/:\n"
        + "\n".join(f"  {name}: {body!r}" for name, body in offenders)
    )


def test_p23_every_invoked_script_exists_and_is_executable(workflow):
    invoked = [script_path(step) for step in workflow_steps(workflow) if invoked_script(step)]
    assert invoked, "the workflow invokes no gate script; this arm ran empty"
    for path in invoked:
        assert path.exists(), f"the workflow invokes a script that does not exist: {path}"
        assert path.stat().st_mode & 0o111, f"{path} is not executable, so the step cannot run it"


def test_p24_every_gate_script_is_canonical(workflow):
    """Exactly one executable line, plus a shebang and errexit.

    A script with two command lines reintroduces the thing the rewrite removed:
    somewhere to hide a command that does not run, or one that does and should
    not. Gate 5 and the gate 10 filter are the deliberate exceptions, both of
    which branch, and both of which are executed for real in
    `tests/ci/test_gate_scripts.py` rather than read.
    """
    branching = {"gate05_integration.sh", "gate10_filter.sh"}
    checked_any = False
    for step in workflow_steps(workflow):
        path = script_path(step)
        if path is None or path.name in branching:
            continue
        checked_any = True
        assert path.exists(), (
            f"the workflow invokes {path.name}, which does not exist under .github/gates/"
        )
        source = path.read_text(encoding="utf-8")
        assert source.startswith("#!/usr/bin/env bash\n"), f"{path.name} has no bash shebang"
        assert "set -euo pipefail" in source, (
            f"{path.name} does not `set -euo pipefail`, so a failing command "
            f"mid-script can still exit 0"
        )
        command = script_command(path)
        assert command, f"{path.name} has no executable line at all"
        assert len(command.splitlines()) == 1, (
            f"{path.name} carries more than one executable line, which is where a "
            f"command that never runs can hide:\n{command}"
        )
    assert checked_any, "no canonical script was examined; this arm ran empty"


# ---------------------------------------------------------------------------
# Arm 3: each gate runs Section 24's command, matched whole-line
# ---------------------------------------------------------------------------

# (gate, anchored pattern the script's single command must match, description)
_GATE_COMMANDS: tuple[tuple[int, str, str], ...] = (
    (1, r"^python -m compileall -q src services tests alembic && python -c .+$", "compiles and imports"),
    (2, r"^isort --check-only --diff (?!.*--skip)[\w./ ]+$", "checks import order without rewriting"),
    (3, r"^ruff check$", "lints the whole repository, no path argument"),
    (4, r'^pytest -m "not integration" -q -rs --junitxml=unit-results\.xml$', "runs the whole unit suite"),
    (6, r"^pip-audit -r requirements\.txt$", "audits the declared dependencies"),
    (7, r"^npm audit --audit-level=high$", "audits frontend dependencies at the high threshold"),
    (8, r"^npm run build && npm test$", "builds and tests the frontend"),
    (9, r"^pytest tests/[\w/]+test_required_paths\.py .*&& python \.github/scripts/assert_required_paths_ran\.py .+$", "runs the required paths and asserts they ran"),
    (10, r"^npx playwright test e2e/accessibility\.spec\.ts$", "runs the accessibility spec"),
)


@pytest.mark.parametrize(("order", "pattern", "description"), _GATE_COMMANDS)
def test_p25_each_gate_script_runs_its_specified_command(workflow, order, pattern, description):
    """Anchored at both ends, against the script's ONE executable line.

    Anchoring is what makes this different from every previous version. A
    substring search accepts anything wrapped around the command; `^...$` on a
    single canonical line accepts only the command.
    """
    steps = gate_steps(workflow).get(order)
    assert steps, f"gate {order} has no step"
    path = script_path(steps[0])
    assert path is not None, f"gate {order} does not invoke a script"
    command = script_command(path)
    assert re.match(pattern, command), (
        f"gate {order} ({description}) does not run its specified command.\n"
        f"expected to match: {pattern}\ngot: {command!r}"
    )


def test_p26_gate_4b_asserts_the_database_was_reached(workflow):
    """F-4.14-03, and the step CI run 4 proved necessary."""
    steps = gate_steps(workflow).get(4)
    assert steps and len(steps) >= 2, "gate 4 has no follow-up assertion step"
    commands = "\n".join(
        script_command(path) for step in steps if (path := script_path(step)) is not None
    )
    assert "assert_no_db_skips.py" in commands, (
        "nothing asserts the database was actually reached, so gate 4 passes "
        "whether its database-backed tests ran or silently skipped. On CI run 4 "
        "that was 25 tests behind a green `4019 passed`."
    )


# ---------------------------------------------------------------------------
# Arm 4: a gate present but neutralised
# ---------------------------------------------------------------------------


def test_p19_no_gate_is_neutralised(workflow):
    """`continue-on-error`, `if: false`, and the same at job level.

    The `|| true` and `set +e` cases this arm used to enumerate are now
    structurally impossible in a gate step, since a step body must equal a
    script path, and inside the scripts `test_p24` permits exactly one command
    line and requires `set -euo pipefail`.
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
    assert checked_any, "no gate steps were examined; this arm ran empty"


def test_p19b_no_job_carrying_a_gate_is_neutralised(workflow):
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
# Arm 5: the database, and the commands are real
# ---------------------------------------------------------------------------


def test_p5_the_unit_job_runs_a_real_database_and_proves_it_reached_it(workflow):
    """F-4.14-03 and F-4.14-J-04.

    The populate-checks are the property, not a correlate: a `redis:7` image
    used to pass because the `POSTGRES_*` env keys satisfied a substring, and so
    did `USER_DB_URL: ""`.
    """
    job_name, job = job_containing_gate(workflow, 4)

    services = job.get("services") or {}
    assert services, f"job {job_name!r} declares no services at all"
    images = [str((spec or {}).get("image", "")) for spec in services.values()]
    assert any(image.startswith("postgres") for image in images), (
        f"job {job_name!r} runs no PostgreSQL image (found {images}), so every "
        f"database-backed test would skip and gate 4 would certify nothing."
    )

    url = str((job.get("env") or {}).get("USER_DB_URL", "")).strip()
    assert url.startswith("postgresql://"), (
        f"job {job_name!r} sets USER_DB_URL to {url!r}, which is not a PostgreSQL DSN"
    )

    commands = "\n".join(
        script_command(path)
        for step in job["steps"]
        if (path := script_path(step)) is not None
    )
    assert "alembic upgrade head" in commands, (
        "the job never creates the schema, so the tests connect to an empty "
        "database and fail on missing tables"
    )


def test_p4_gate_9_points_at_a_file_that_exists_and_collects_tests(workflow):
    """F-4.14-02."""
    steps = gate_steps(workflow).get(9)
    assert steps, "gate 9 has no step"
    command = script_command(script_path(steps[0]))
    referenced = re.findall(r"(tests/[\w/]+\.py)", command)
    assert referenced, "gate 9 names no test file"
    for rel in referenced:
        target = REPO_ROOT / rel
        assert target.exists(), f"gate 9 points at a file that does not exist: {rel}"
        assert target.read_text(encoding="utf-8").count("def test_") >= 2, (
            f"{rel} defines fewer than two tests; gate 9 would certify an almost-empty run"
        )


def test_p7_gate_2_lints_paths_that_exist(workflow):
    """isort exits 0 on a path that is not there, so the paths matter."""
    steps = gate_steps(workflow).get(2)
    assert steps, "gate 2 has no step"
    command = script_command(script_path(steps[0]))
    paths = [
        token
        for token in command.split()
        if not token.startswith("-") and token != "isort" and "=" not in token
    ]
    assert paths, "gate 2 passes isort no paths at all, so it checks nothing"
    for path in paths:
        assert (REPO_ROOT / path).exists(), f"gate 2 lints a path that does not exist: {path}"


def test_p8_frontend_gates_call_scripts_that_package_json_defines(workflow):
    package = json.loads((REPO_ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    scripts = package.get("scripts") or {}
    assert scripts, "frontend/package.json defines no scripts; this arm ran empty"

    all_commands = "\n".join(
        script_command(path)
        for step in workflow_steps(workflow)
        if (path := script_path(step)) is not None and path.name not in {"gate05_integration.sh", "gate10_filter.sh"}
    )
    invoked = set(re.findall(r"npm run ([\w:-]+)", all_commands))
    assert invoked, "the workflow invokes no `npm run` script; this arm ran empty"
    for name in sorted(invoked):
        assert name in scripts, f"the workflow runs `npm run {name}`, which package.json lacks"


def test_p9_gate_10_points_at_a_playwright_spec_that_exists(workflow):
    steps = gate_steps(workflow).get(10)
    assert steps, "gate 10 has no step"
    command = script_command(script_path(steps[0]))
    specs = re.findall(r"(e2e/[\w.\-]+\.spec\.ts)", command)
    assert specs, "gate 10 names no spec file"
    for rel in specs:
        assert (REPO_ROOT / "frontend" / rel).exists(), (
            f"gate 10 points at a spec that does not exist: {rel}"
        )


def test_p15_gate_5_cannot_pass_silently_when_it_did_not_run(workflow):
    """F-4.14-A-03, both halves."""
    steps = gate_steps(workflow).get(5)
    assert steps, "gate 5 has no step"
    path = script_path(steps[0])
    assert path is not None, "gate 5 does not invoke a script"
    source = path.read_text(encoding="utf-8")

    assert "exit 0" in source, "gate 5 has no not-run path at all; this arm ran empty"
    assert "::warning" in source, (
        "gate 5's not-run path exits 0 without a warning annotation, so it renders "
        "as an ordinary green check"
    )
    assert "NOT RUN" in source, "gate 5's not-run path does not say so in its output"
    assert "assert_gate_ran.py" in source, (
        "gate 5 does not assert that its run executed anything. With a credential "
        "present but unreachable it exits 0 having passed zero tests. F-4.14-A-03."
    )

    _, job = job_containing_gate(workflow, 5)
    env = {**(workflow.get("env") or {}), **(job.get("env") or {})}
    for step in steps:
        env.update(step.get("env") or {})
    assert str(env.get("RUN_PREMISE_GATE", "")).strip() == "1", (
        "gate 5 never sets RUN_PREMISE_GATE, and tests/conftest.py blocks all "
        "outbound HTTP without it, so its arms cannot reach the graph service."
    )


def test_p20_gate_10_fails_closed(workflow):
    """F-4.14-A-07."""
    filter_script = GATES_DIR / "gate10_filter.sh"
    assert filter_script.exists(), "the gate 10 filter script is missing; this arm ran empty"
    body = filter_script.read_text(encoding="utf-8")

    assert "git cat-file -e" in body, (
        "the filter does not verify the base and head commits exist before "
        "diffing, so a shallow clone or a garbage-collected SHA silently skips "
        "the accessibility gate. F-4.14-A-07."
    )
    assert body.count("touched=true") >= 3, (
        "the filter has fewer than three paths that RUN the gate. It must fail "
        "closed: every error path runs the gate rather than skipping it."
    )
    assert not re.search(r"if\s+git diff", body), (
        "the filter puts `git diff` directly in an `if` condition, where errexit "
        "is suspended, so any git failure takes the skip branch."
    )


# ---------------------------------------------------------------------------
# Arm 6: the workflow's own properties
# ---------------------------------------------------------------------------


def test_p10_ci_runs_on_pull_requests(workflow):
    """PyYAML parses a bare `on:` key as the boolean True, which is a real trap."""
    triggers = workflow.get("on", workflow.get(True))
    assert triggers, "the workflow declares no triggers"
    assert "pull_request" in triggers, (
        "CI does not run on pull requests, the only trigger that can stop a bad "
        "merge before it auto-deploys"
    )


def test_p11_no_gate_but_gate_5_depends_on_a_secret(workflow):
    """A fork's pull request must get the same verdict as a branch's."""
    workflow_env = yaml.safe_dump(workflow.get("env") or {})
    assert "secrets." not in workflow_env, (
        "a secret is declared in the workflow-level `env`, so it reaches every gate"
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
            f"job {job_name!r} runs gates {gates_here} and references a secret; only gate 5 may."
        )
    assert checked_any, "no non-gate-5 job carried a gate; this arm ran empty"


def test_p12_ruff_is_pinned_exactly_so_the_lint_gate_cannot_drift():
    """Parsed as TOML, so a commented-out pin does not satisfy it."""
    dev = pyproject()["project"]["optional-dependencies"]["dev"]
    assert dev, "the dev extra is empty; this arm ran empty"
    ruff = [item for item in dev if item.replace(" ", "").startswith("ruff")]
    assert ruff, f"ruff is not declared in the dev extra: {dev}"
    assert all(re.fullmatch(r"ruff==\d+\.\d+\.\d+", item.replace(" ", "")) for item in ruff), (
        f"ruff is not pinned exactly ({ruff}). This repository sets no explicit "
        f"`select`, so the enabled rule set IS the version."
    )


def test_p13_no_file_escapes_both_import_order_checkers():
    """F-4.14-RV-05: the previous version checked a spelling, not the property.

    It asserted that `I001` was absent from ruff's `ignore` list, which says
    nothing about `per-file-ignores`. Adding `per-file-ignores = {"...": ["I001"]}`
    for exactly the two files isort's `extend_skip` names left both files checked
    by NEITHER tool, and a scrambled import block passed both gates.

    This asserts the property instead: the set of files ruff excuses and the set
    isort excuses must not overlap.
    """
    config = pyproject()
    ruff_lint = config.get("tool", {}).get("ruff", {}).get("lint", {})

    assert "I001" not in ruff_lint.get("ignore", []), (
        "ruff's I001 is ignored repository-wide, so every file isort skips goes "
        "completely unchecked for import order."
    )

    isort_config = config.get("tool", {}).get("isort", {})
    assert isort_config, "isort is not configured; gate 2 has no owner"
    ruff_isort = config["tool"]["ruff"]["lint"]["isort"]
    assert "alembic" in ruff_isort.get("known-third-party", []), (
        "ruff is not told `alembic` is third party, so it disagrees with isort on 21 files"
    )

    isort_skips = {str(entry) for entry in isort_config.get("extend_skip", [])}
    ruff_excused = {
        path
        for path, rules in (ruff_lint.get("per-file-ignores") or {}).items()
        if any(rule.startswith("I") for rule in rules)
    }
    overlap = sorted(
        skip for skip in isort_skips if any(skip in excused or excused in skip for excused in ruff_excused)
    )
    assert not overlap, (
        f"these files are excused by BOTH isort's extend_skip and ruff's "
        f"per-file-ignores, so nothing checks their import order at all: {overlap}"
    )

    for skipped in isort_skips:
        assert (REPO_ROOT / skipped).exists(), (
            f"isort skips {skipped}, which does not exist. A stale skip entry hides "
            f"the day a real file needs one."
        )


def test_p14_the_workflow_cancels_superseded_pull_request_runs(workflow):
    concurrency = workflow.get("concurrency")
    assert concurrency, "the workflow sets no concurrency group"
    assert concurrency.get("group"), "the concurrency block names no group"
