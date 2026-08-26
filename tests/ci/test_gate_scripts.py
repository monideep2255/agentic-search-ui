"""Execute the gate scripts and prove they go RED on a broken input.

Build phase 4.14, round 3. This is the half of the CI premise gate that reading
cannot provide.

`test_ci_workflow_premise.py` proves each gate script is canonical and runs the
command Section 24 names. That is a property of TEXT, and this phase has now
been beaten twice by text that looked right and executed nothing. Whether a gate
actually FAILS when the thing it guards is broken is behavioural, and the only
way to know is to break something and run it.

WHAT THIS COVERS, stated so a gap is arguable rather than discovered:

    Covered      Gates 2, 3 and 6 executed for real against deliberately broken
                 fixtures, each asserted to exit non-zero, and each asserted to
                 exit ZERO on a clean fixture. Both directions, because a script
                 that fails on everything is as useless as one that fails on
                 nothing. Gate 5's not-run branch executed for real. The gate 10
                 filter executed for real across all four of its paths,
                 including the two error paths that must FAIL CLOSED.

    NOT covered  Gates 1, 4, 7, 8, 9 and 10 are not executed here. Each needs
                 either the full 4000-test suite, a network fetch, a node
                 install, or a browser, and a premise gate that takes ten
                 minutes is one somebody stops running. They are covered by
                 CI itself, where they run on every pull request, and by the
                 canonical-command arms in the premise gate.

    NOT covered  Whether the gates BLOCK a merge. They do not (F-4.14-A-04).

Depends on:
    - .github/gates/*.sh

Writes:
    - Nothing outside pytest's own tmp_path.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATES = REPO_ROOT / ".github" / "gates"

# Long enough for ruff or isort over a tiny fixture; short enough that a hung
# script fails the suite rather than stalling it.
_TIMEOUT_S = 120


def run_gate(script: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    environment = {**os.environ, **(env or {})}
    return subprocess.run(
        [str(GATES / script)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_S,
        check=False,
        env=environment,
    )


@pytest.fixture
def clean_tree(tmp_path: Path) -> Path:
    """A minimal tree the import-order and lint gates can be pointed at."""
    for name in ("src", "tests", "services", "tracker", "alembic", ".claude", ".github"):
        directory = tmp_path / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "ok.py").write_text(
            "import os\nimport sys\n\nprint(os, sys)\n", encoding="utf-8"
        )
    (tmp_path / "pyproject.toml").write_text(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return tmp_path


class TestGate2ImportOrder:
    """isort, both directions."""

    def test_it_passes_on_sorted_imports(self, clean_tree):
        result = run_gate("gate02_import_order.sh", clean_tree)
        assert result.returncode == 0, (
            f"gate 2 failed on a clean tree, so it cannot distinguish good from "
            f"bad:\n{result.stdout}\n{result.stderr}"
        )

    def test_it_fails_on_unsorted_imports(self, clean_tree):
        (clean_tree / "src" / "ok.py").write_text(
            "import sys\nimport os\nfrom pathlib import Path\nimport json\n\n"
            "print(sys, os, Path, json)\n",
            encoding="utf-8",
        )
        result = run_gate("gate02_import_order.sh", clean_tree)
        assert result.returncode != 0, (
            "gate 2 passed over deliberately unsorted imports. It cannot fail, so "
            "its green in CI means nothing."
        )

    def test_it_does_not_rewrite_the_file(self, clean_tree):
        """`--check-only` is the difference between checking and formatting."""
        target = clean_tree / "src" / "ok.py"
        broken = "import sys\nimport os\n\nprint(sys, os)\n"
        target.write_text(broken, encoding="utf-8")
        run_gate("gate02_import_order.sh", clean_tree)
        assert target.read_text(encoding="utf-8") == broken, (
            "gate 2 REWROTE the file instead of checking it. Without --check-only "
            "isort formats and exits 0, so the gate silently fixes what it is "
            "supposed to report."
        )


class TestGate3Lint:
    """ruff, both directions."""

    def test_it_passes_on_clean_code(self, clean_tree):
        result = run_gate("gate03_lint.sh", clean_tree)
        assert result.returncode == 0, (
            f"gate 3 failed on clean code:\n{result.stdout}\n{result.stderr}"
        )

    def test_it_fails_on_a_lint_error(self, clean_tree):
        (clean_tree / "src" / "bad.py").write_text(
            "import os\n\n\ndef f():\n    try:\n        pass\n    except Exception:\n        pass\n",
            encoding="utf-8",
        )
        result = run_gate("gate03_lint.sh", clean_tree)
        assert result.returncode != 0, (
            "gate 3 passed over code carrying a lint error it is configured to "
            "catch. It cannot fail."
        )

    def test_it_covers_every_directory_not_just_src(self, clean_tree):
        """The regression T-4.14-03 fixed: `ruff check src` left `tests/` unlinted."""
        (clean_tree / "tests" / "bad.py").write_text(
            "import os\n\n\ndef f():\n    try:\n        pass\n    except Exception:\n        pass\n",
            encoding="utf-8",
        )
        result = run_gate("gate03_lint.sh", clean_tree)
        assert result.returncode != 0, (
            "gate 3 did not catch an error under tests/, so it is narrowed to a "
            "subset of the repository again."
        )


class TestGate6PythonAudit:
    """pip-audit, scoped to the requirements file (F-4.14-01)."""

    def test_it_passes_on_this_project_s_requirements(self, tmp_path):
        (tmp_path / "requirements.txt").write_text(
            (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8"), encoding="utf-8"
        )
        result = run_gate("gate06_python_audit.sh", tmp_path)
        assert result.returncode == 0, (
            f"gate 6 failed on this project's own requirements:\n{result.stdout}\n{result.stderr}"
        )

    def test_it_fails_on_a_dependency_with_a_known_vulnerability(self, tmp_path):
        # An old release with published advisories. Pinned exactly so this test
        # asserts a fixed historical fact rather than whatever is current.
        (tmp_path / "requirements.txt").write_text("jinja2==2.11.2\n", encoding="utf-8")
        result = run_gate("gate06_python_audit.sh", tmp_path)
        assert result.returncode != 0, (
            "gate 6 passed a dependency with known published vulnerabilities. It "
            "cannot fail, so its green means nothing."
        )


class TestGate5NotRunBranch:
    """Gate 5's honest not-run path, executed rather than read."""

    def test_no_credential_exits_zero_and_says_NOT_RUN(self, tmp_path):
        summary = tmp_path / "summary.md"
        result = run_gate(
            "gate05_integration.sh",
            REPO_ROOT,
            env={
                "GRAPH_QUERY_URL": "",
                "GRAPH_PG_HOST": "",
                "GITHUB_STEP_SUMMARY": str(summary),
            },
        )
        assert result.returncode == 0, "gate 5's not-run path must not fail the build"
        assert "NOT RUN" in result.stdout, "gate 5 did not say it had not run"
        assert "::warning" in result.stdout, (
            "gate 5 exited 0 with no warning annotation, so it renders as an "
            "ordinary green check and a reviewer cannot tell it from a real pass"
        )
        assert "NOT RUN" in summary.read_text(encoding="utf-8"), (
            "gate 5 wrote nothing to the job summary"
        )


class TestGate10Filter:
    """The path filter, all four paths, executed. It must FAIL CLOSED."""

    def _run(self, tmp_path: Path, **env: str) -> tuple[int, str]:
        output = tmp_path / "gh_output"
        output.touch()
        result = run_gate(
            "gate10_filter.sh",
            REPO_ROOT,
            env={"GITHUB_OUTPUT": str(output), "GITHUB_STEP_SUMMARY": str(tmp_path / "s.md"), **env},
        )
        return result.returncode, output.read_text(encoding="utf-8")

    def test_no_base_sha_runs_the_gate(self, tmp_path):
        code, output = self._run(tmp_path, BASE_SHA="", HEAD_SHA="")
        assert code == 0
        assert "touched=true" in output, "a push event must run the gate, not skip it"

    def test_an_unresolvable_commit_runs_the_gate(self, tmp_path):
        """F-4.14-A-07: this is the path that used to skip silently."""
        code, output = self._run(
            tmp_path, BASE_SHA="0" * 40, HEAD_SHA="1" * 40
        )
        assert code == 0
        assert "touched=true" in output, (
            "an unresolvable base commit SKIPPED the accessibility gate. The "
            "filter must fail closed: a shallow clone or a garbage-collected SHA "
            "runs the gate rather than silently dropping it."
        )

    def _synthetic_repo(self, tmp_path: Path, second_commit_path: str) -> tuple[Path, str, str]:
        """A throwaway git repository with two commits, and their SHAs.

        Built rather than borrowed from this repository's own history, and that
        is a correction. The first version of these two arms diffed real commits
        found with `git rev-list --all -- frontend/`, and CI checks out at
        depth 1, so on a runner there was no such commit and the arm SKIPPED.
        The skip guard caught it, correctly: a test that quietly does not run is
        the exact thing this phase exists to stop, and it does not stop being
        that because the test is one of ours.

        A synthetic repository has no ambient dependency at all, so the arm runs
        identically on a developer machine, a shallow clone, and a fork.
        """
        repo = tmp_path / "repo"
        repo.mkdir()

        def git(*args: str) -> str:
            return subprocess.run(
                ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True
            ).stdout.strip()

        git("init", "-q")
        git("config", "user.email", "ci@example.invalid")
        git("config", "user.name", "CI")
        (repo / "README.md").write_text("base\n", encoding="utf-8")
        git("add", "README.md")
        git("commit", "-q", "-m", "base")
        base = git("rev-parse", "HEAD")

        target = repo / second_commit_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("changed\n", encoding="utf-8")
        git("add", second_commit_path)
        git("commit", "-q", "-m", "change")
        head = git("rev-parse", "HEAD")
        return repo, base, head

    def _run_in(self, repo: Path, tmp_path: Path, **env: str) -> tuple[int, str]:
        output = tmp_path / "gh_output_repo"
        output.touch()
        result = run_gate(
            "gate10_filter.sh",
            repo,
            env={
                "GITHUB_OUTPUT": str(output),
                "GITHUB_STEP_SUMMARY": str(tmp_path / "s2.md"),
                **env,
            },
        )
        return result.returncode, output.read_text(encoding="utf-8")

    def test_a_frontend_change_runs_the_gate(self, tmp_path):
        repo, base, head = self._synthetic_repo(tmp_path, "frontend/src/App.tsx")
        code, output = self._run_in(repo, tmp_path, BASE_SHA=base, HEAD_SHA=head)
        assert code == 0
        assert "touched=true" in output, "a frontend change did not trigger the gate"

    def test_a_backend_only_change_skips_the_gate(self, tmp_path):
        """The other direction: a filter that always runs is not a filter."""
        repo, base, head = self._synthetic_repo(tmp_path, "src/system_03_search_agent/thing.py")
        code, output = self._run_in(repo, tmp_path, BASE_SHA=base, HEAD_SHA=head)
        assert code == 0
        assert "touched=false" in output, (
            "a backend-only change still ran the gate, so the filter never skips "
            "and Section 24's 'UI-touching pull requests only' is not honoured"
        )


class TestEveryGateScriptIsRunnable:
    """A script that cannot be executed is a gate that cannot run."""

    def test_every_script_is_executable_and_has_a_bash_shebang(self):
        scripts = sorted(GATES.glob("*.sh"))
        assert scripts, "no gate scripts found; this arm ran empty"
        for script in scripts:
            assert script.stat().st_mode & 0o111, f"{script.name} is not executable"
            first = script.read_text(encoding="utf-8").splitlines()[0]
            assert first == "#!/usr/bin/env bash", (
                f"{script.name} starts with {first!r}, not a bash shebang"
            )

    def test_every_script_passes_bash_syntax_checking(self):
        """`bash -n` parses without executing, which catches an unclosed quote."""
        scripts = sorted(GATES.glob("*.sh"))
        assert scripts, "no gate scripts found; this arm ran empty"
        for script in scripts:
            result = subprocess.run(
                ["bash", "-n", str(script)], capture_output=True, text=True, check=False
            )
            assert result.returncode == 0, (
                f"{script.name} is not valid bash:\n{result.stderr}"
            )
