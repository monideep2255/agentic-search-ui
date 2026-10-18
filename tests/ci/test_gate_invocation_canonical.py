"""Ordinary unit test: a CI gate step's `run:` body cannot be neutralised.

Moved out of the deleted `test_ci_workflow_premise.py` (build phase 4.14
bossman redesign, 2026-09-24,
`docs/build/Bossman_redesign_deletion_inventory.md`). That file's P21/P22
arms pinned the property this file keeps: a gate step's `run:` value must
EQUAL a script path under `.github/gates/`, not merely contain one, because
`.github/workflows/ci.yml`'s own comment records that `:;#ruff check` runs
NOTHING (bash treats `#` as a comment start whenever it begins a word) while
looking, to a substring check, like it ran `ruff check`. Eight of ten gates
were neutralised this way in build phase 4.14 with every premise test green.

This file cannot prove the property by mutating `.github/workflows/ci.yml`
itself (that file is not this test's to write, and CI configuration changes
belong on a reviewed branch). Instead it proves the DETECTOR can fail, on a
synthetic in-memory copy of a neutralised step, and then applies the same
detector to the real workflow file, read-only.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
GATES_DIR = REPO_ROOT / ".github" / "gates"


def invoked_script(run_body: str) -> str:
    """The single script path a step invokes, or "" if it is not a bare call.

    A whole-string match: a body has to BE a script path. `:;#ruff check`
    is not one, and neither is `.github/gates/gate03_lint.sh; rm -rf /`.
    """
    body = run_body.strip()
    if re.fullmatch(r"(\.\./)?\.github/gates/[A-Za-z0-9_]+\.sh", body):
        return body
    return ""


def test_the_detector_rejects_a_neutralised_step_body() -> None:
    """The exact historical defect: a comment that eats the whole command."""
    assert invoked_script(":;#.github/gates/gate03_lint.sh") == ""


def test_the_detector_rejects_a_second_command_appended_after_the_script() -> None:
    assert invoked_script(".github/gates/gate03_lint.sh; rm -rf /") == ""


def test_the_detector_accepts_a_bare_script_invocation() -> None:
    assert invoked_script(".github/gates/gate03_lint.sh") == ".github/gates/gate03_lint.sh"


def test_every_step_in_the_real_workflow_is_a_bare_script_invocation_or_empty() -> None:
    """Applied read-only to the actual CI workflow.

    A neutralised gate in the real file fails this test the same way the
    synthetic cases above fail the detector.
    """
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    offenders = []
    for job in workflow.get("jobs", {}).values():
        for step in job.get("steps", []) or []:
            body = str(step.get("run", "")).strip()
            if not body:
                continue
            if not invoked_script(body):
                offenders.append((step.get("name"), body))
    assert not offenders, (
        "these workflow steps carry shell rather than a bare script "
        f"invocation under .github/gates/: {offenders}"
    )


def test_every_invoked_script_in_the_real_workflow_exists() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    checked_any = False
    for job in workflow.get("jobs", {}).values():
        for step in job.get("steps", []) or []:
            body = str(step.get("run", "")).strip()
            invoked = invoked_script(body)
            if invoked:
                checked_any = True
                target = GATES_DIR / Path(invoked).name
                assert target.exists(), f"missing gate script: {invoked}"
    assert checked_any, "no gate script invocation found; this test ran empty"
