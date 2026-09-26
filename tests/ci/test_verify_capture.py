"""Run the /verify capture script's guards the way a caller would.

`.claude/skills/verify/scripts/capture.mjs` captures the running app at 1280
and 390 pixels, and a pass at both widths starts the seven-day close for a
wording or layout card. Three guards keep a failing screen from passing, found
by the fresh-context check of pull request #114 on 2026-09-26:

- A spec whose widths are not exactly 1280 and 390 is refused, unless
  --allow-partial-widths is passed, because dropping the width a screen fails
  at turned a failing run into a passing one.
- A run in which no check ran exits non-zero, because an empty widths list
  once printed "0 pass, 0 fail" and exited 0.
- An output folder that already holds files is refused, unless --overwrite is
  passed, because a same-day rerun overwrote committed evidence.

WHAT THIS COVERS, stated so a gap is arguable rather than discovered:

    Covered      The script's own --self-test, which asserts each guard
                 against fixed inputs and was seen going red with each guard
                 removed; and the three refusals from the command line, each
                 before any network call or browser.
    Not covered  A real capture. That needs a browser and a running app, so it
                 is the skill's own proof run, not a unit test.

Needs `node` on the PATH, and nothing from `frontend/node_modules`: every path
exercised here stops before the script loads Playwright.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".claude" / "skills" / "verify" / "scripts" / "capture.mjs"
UNREACHABLE_API = "http://127.0.0.1:9"
# Inside the repository, since --out must be, and gitignored. Every command
# line test passes --out here, so even a broken guard never writes into
# testing/, where committed evidence lives.
SCRATCH_ROOT = REPO_ROOT / "frontend" / "test-results"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is not on the PATH, so the /verify capture guards cannot be checked")
    return subprocess.run(
        [node, str(SCRIPT), *args],
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
        cwd=REPO_ROOT,
    )


@pytest.fixture
def out_dir() -> Iterator[Path]:
    folder = SCRATCH_ROOT / f"verify_guard_{uuid.uuid4().hex}"
    yield folder
    if folder.exists():
        shutil.rmtree(folder)


def _refused(spec: Path, out: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return _run(
        "--spec", str(spec), "--target", "local", "--api", UNREACHABLE_API, "--out", str(out), *extra,
    )


def _spec(tmp_path: Path, **overrides: object) -> Path:
    spec = {
        "topic": "guard_test",
        "screens": [{"name": "home", "path": "/", "steps": [{"do": "disclaimer"}]}],
    }
    spec.update(overrides)
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    return path


def test_self_test_passes() -> None:
    result = _run("--self-test")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "self-test FAIL" not in result.stdout
    assert "self-test:" in result.stdout


def test_one_width_is_refused(tmp_path: Path, out_dir: Path) -> None:
    spec = _spec(tmp_path, widths=[{"width": 1280, "height": 900}])
    result = _refused(spec, out_dir)
    assert result.returncode == 2
    assert not out_dir.exists()
    assert "widths must be exactly 1280 and 390" in result.stderr


def test_empty_widths_are_refused_even_when_partial_widths_are_allowed(
    tmp_path: Path, out_dir: Path,
) -> None:
    spec = _spec(tmp_path, widths=[])
    result = _refused(spec, out_dir, "--allow-partial-widths")
    assert result.returncode == 2
    assert not out_dir.exists()
    assert "non-empty list" in result.stderr


def test_a_spec_with_no_screens_is_refused(tmp_path: Path, out_dir: Path) -> None:
    spec = _spec(tmp_path, screens=[])
    result = _refused(spec, out_dir)
    assert result.returncode == 2
    assert not out_dir.exists()
    assert "no screens" in result.stderr


def test_a_folder_that_holds_files_is_refused(tmp_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True)
    (out_dir / "results.json").write_text("{}\n")
    result = _refused(_spec(tmp_path), out_dir)
    assert result.returncode == 2
    assert "already holds" in result.stderr
    assert sorted(p.name for p in out_dir.iterdir()) == ["results.json"]
    assert (out_dir / "results.json").read_text() == "{}\n"
