"""Is the drift check quiet about counts and dates, and still loud about structure?

Build harness review item D1, delegated by the product owner on 2026-09-25
(DECISIONS.md, "The lead implements both harness reviews' takeaways"): the
documents stop stating test, decision and learning counts, and
`tracker/check_doc_drift.py --check` stops failing because a count or a date
moved. Before, 87 of the 92 commits to CLAUDE.md in two weeks changed only a
count or a date, and every checkpoint ran the whole pytest collection twice to
compute counts nobody acted on
(`testing/Developer/reports/2026-09-25_harness_review/build_harness.md`).

What this file pins down, one claim per test:

- `--check` passes a document that states a stale count or an old "Last
  updated" line, and never calls the counting code, so it runs no tests.
- The checks that stayed still fail: a table of contents that does not match
  its headings, a blank line inside an append-only table, a wrong
  phase-to-pull-request reference.
- `--counts` still computes the counts, prints them, and reads no document.

Build harness review item S3, same delegation: the check never prints "ok"
over something it could not compute. It used to skip the Python test count in
any worktree with no `venv/bin/python` and still say "ok" (F-8.5-J04 and
F-8.5-V05, `tracker/phase_8.5.md`), and it read pytest's "N tests collected"
without the error count beside it, so a module that failed to import lowered
the count instead of failing the run. The tests below pin down:

- `--check` fails, naming the reason, when a fact it reads could not be
  computed or the tracked files could not be listed.
- `--counts` fails, naming the reason, when a count could not be computed.
- The pytest summary parser reads the error count from pytest's own output,
  and a collection with errors never yields a count.

Every test builds its own documents under `tmp_path` and stubs the facts, so
none of them depends on the state of this repository's real documents.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKER_DIR = REPO_ROOT / "tracker"


def _load(name: str):
    """Import a `tracker/` script by path. `tracker/` is not a package and the
    scripts are meant to run standalone, so the directory goes on `sys.path`
    first (the drift check imports `render_board` from beside itself), and the
    module is registered before execution so `@dataclass` can resolve it.
    """
    if str(TRACKER_DIR) not in sys.path:
        sys.path.insert(0, str(TRACKER_DIR))
    spec = importlib.util.spec_from_file_location(name, TRACKER_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


drift = _load("check_doc_drift")

COUNT_FUNCTIONS = [
    "compute_python_test_count",
    "compute_premise_gate_count",
    "compute_frontend_test_counts",
    "compute_playwright_test_count",
    "compute_decisions_row_count",
    "compute_learnings_entry_count",
    "compute_open_flags_count",
]


def _good_check_facts(statuses=None, prs=None) -> dict:
    statuses = statuses if statuses is not None else {"3.1": "done"}
    prs = prs if prs is not None else {"3.1": 23}
    return {
        "build_phase_statuses": drift.Fact(
            "build_phase_statuses", "Build phase statuses", statuses, "stub", "stub"
        ),
        "merged_prs": drift.Fact(
            "merged_prs", "Merged PR numbers per phase", prs, "stub", "stub"
        ),
    }


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A throwaway repository root. `write(rel, text)` adds a tracked markdown
    file; `check()` runs `main(["--check"])` over exactly those files with
    healthy check facts, and returns (exit code, stdout).
    """
    monkeypatch.setattr(drift, "REPO_ROOT", tmp_path)
    files: list[Path] = []
    monkeypatch.setattr(drift, "tracked_markdown_files", lambda: list(files))
    monkeypatch.setattr(drift, "compute_check_facts", _good_check_facts)

    class Repo:
        root = tmp_path

        def write(self, rel: str, text: str) -> Path:
            path = tmp_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            files.append(path)
            return path

    return Repo()


def _check(capsys) -> tuple[int, str]:
    rc = drift.main(["--check"])
    return rc, capsys.readouterr().out


# ---------------------------------------------------------------------------
# D1: a count or a date moving no longer turns the check red
# ---------------------------------------------------------------------------


def test_check_passes_a_document_that_states_stale_counts(repo, capsys):
    repo.write(
        "CLAUDE.md",
        "# Title\n\n"
        "Current counts: 99999 Python tests, 1 frontend tests, 3 Playwright tests, "
        "4 decisions (DECISIONS.md), 5 learnings plus a retrospective, "
        "premise gate 1 of 2, 7 open flags.\n"
        "Decisions logged: 12345\n",
    )
    rc, out = _check(capsys)
    assert rc == 0, out
    assert out.startswith("ok:")


def test_check_passes_a_last_updated_line_older_than_its_body(repo, capsys):
    repo.write(
        "PROGRESS.md",
        "# Progress\n\nLast updated: 2020-01-01.\n\n"
        "- 2026-09-25: something happened long after the date above.\n",
    )
    rc, out = _check(capsys)
    assert rc == 0, out


def test_check_never_calls_the_counting_code(repo, capsys, monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("--check computed a count; it must run no tests")

    for name in COUNT_FUNCTIONS + ["compute_count_facts"]:
        monkeypatch.setattr(drift, name, refuse)
    repo.write("README.md", "# Readme\n\nNothing to see.\n")
    rc, out = _check(capsys)
    assert rc == 0, out


# ---------------------------------------------------------------------------
# The checks that stayed must still be able to fail
# ---------------------------------------------------------------------------


def test_check_still_fails_on_a_table_of_contents_that_misses_a_heading(repo, capsys):
    repo.write(
        "docs/Guide.md",
        "# Guide\n\n## Table of contents\n\n- [First](#first)\n\n"
        "## First\n\ntext\n\n## Second\n\ntext\n",
    )
    rc, out = _check(capsys)
    assert rc == 1
    assert "docs/Guide.md:3: table of contents does not match" in out


def test_check_still_fails_on_a_blank_line_inside_the_decisions_table(repo, capsys):
    row = "| 2026-09-25 | A choice | Another | <details><summary>why</summary>Because</details> |\n"
    repo.write(
        "DECISIONS.md",
        "# Decisions\n\n| Date | Decision | Alternatives considered | Why |\n"
        "|------|----------|------------------------|-----|\n" + row + "\n" + row,
    )
    rc, out = _check(capsys)
    assert rc == 1
    assert "blank line INSIDE the table" in out


def test_check_still_fails_on_a_wrong_pull_request_reference(repo, capsys):
    repo.write("docs/Notes.md", "# Notes\n\nBuild phase 3.1 merged as PR #99.\n")
    rc, out = _check(capsys)
    assert rc == 1
    assert "says build phase 3.1 merged as PR #99 (computed: PR #23)" in out


def test_check_still_fails_when_a_done_phase_is_called_next(repo, capsys):
    repo.write("docs/Notes.md", "# Notes\n\nNext: build phase 3.1, the next one to open.\n")
    rc, out = _check(capsys)
    assert rc == 1
    assert "describes build phase 3.1 as next" in out


# ---------------------------------------------------------------------------
# --counts: the counting code stays reachable, print-only
# ---------------------------------------------------------------------------


def _count_facts() -> dict:
    return {
        "python_tests": drift.Fact("python_tests", "Python tests", 5704, "5704", "stub"),
        "decisions_rows": drift.Fact("decisions_rows", "DECISIONS.md rows", 698, "698", "stub"),
    }


def test_counts_prints_every_count_and_reads_no_document(monkeypatch, capsys):
    def refuse():
        raise AssertionError("--counts read the tracked documents; it must be print-only")

    monkeypatch.setattr(drift, "tracked_markdown_files", refuse)
    monkeypatch.setattr(drift, "compute_count_facts", _count_facts)
    rc = drift.main(["--counts"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "Python tests: 5704" in out
    assert "DECISIONS.md rows: 698" in out


def test_counts_computes_decision_rows_from_the_file(tmp_path, monkeypatch):
    decisions = tmp_path / "DECISIONS.md"
    decisions.write_text(
        "| Date | Decision |\n|---|---|\n| 2026-09-24 | a |\n| 2026-09-25 | b |\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(drift, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(drift, "DECISIONS_MD", decisions)
    fact = drift.compute_decisions_row_count()
    assert (fact.skipped, fact.value) == (False, 2)


def test_self_test_passes():
    assert drift.run_self_test() == 0


# ---------------------------------------------------------------------------
# S3: never a silent ok
# ---------------------------------------------------------------------------

#: The last lines of `pytest --collect-only -q` as pytest 9.1.1 printed them on
#: 2026-09-25, for a directory holding one importable test module (two tests)
#: and, in the first two cases, one or two modules importing a missing name.
PYTEST_TWO_ERRORS = (
    "E   ModuleNotFoundError: No module named 'also_missing_abc'\n"
    "=========================== short test summary info ============================\n"
    "ERROR tests/test_bad.py\n"
    "ERROR tests/test_bad2.py\n"
    "!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!\n"
    "2 tests collected, 2 errors in 0.12s"
)
PYTEST_ONE_ERROR = (
    "E   ModuleNotFoundError: No module named 'no_such_module_xyz'\n"
    "=========================== short test summary info ============================\n"
    "ERROR tests/test_bad.py\n"
    "!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!\n"
    "2 tests collected, 1 error in 0.11s"
)
PYTEST_CLEAN = (
    "tests/test_good.py::test_a\n"
    "tests/test_good.py::test_b\n"
    "\n"
    "2 tests collected in 0.00s"
)


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        # Measured with pytest 9.1.1 on 2026-09-25.
        pytest.param(PYTEST_CLEAN, (2, 0), id="clean"),
        pytest.param(PYTEST_ONE_ERROR, (2, 1), id="one-error"),
        pytest.param(PYTEST_TWO_ERRORS, (2, 2), id="two-errors"),
        pytest.param("1 test collected in 0.02s", (1, 0), id="one-test"),
        pytest.param("no tests collected in 0.01s", (0, 0), id="no-tests"),
        pytest.param("no tests collected, 1 error in 0.24s", (0, 1), id="no-tests-one-error"),
        # Synthetic, not measured: a warning is not an error, and the
        # interrupted line alone still counts, so an error is never missed
        # because the summary line is absent or cut off.
        pytest.param("5704 tests collected, 3 warnings in 12.00s", (5704, 0), id="warnings"),
        pytest.param(
            "!!!! Interrupted: 3 errors during collection !!!!", (None, 3), id="interrupted-only"
        ),
        pytest.param("something that is not pytest output", (None, 0), id="not-pytest"),
    ],
)
def test_collection_summary_reads_the_count_and_the_errors(output, expected):
    assert drift.parse_collection_summary(output) == expected


def test_a_test_id_that_quotes_pytest_is_not_read_as_an_error():
    """The measured false positive, 2026-09-25: `--collect-only -q` lists every
    test id before the summary, and this file's own parametrized ids once
    carried the fixture text above, so a clean collection of this repository
    read as "1 collection error". The ids are plain now, and the parser only
    reads lines that start the way pytest's own lines do.
    """
    output = (
        "tests/tracker/test_x.py::test_y[!!!! Interrupted: 1 error during collection !!!!]\n"
        "tests/tracker/test_x.py::test_y[2 tests collected, 1 error in 0.11s]\n"
        "\n"
        "5730 tests collected in 8.84s"
    )
    assert drift.parse_collection_summary(output) == (5730, 0)


def _stub_pytest(monkeypatch, tmp_path, output: str, returncode: int) -> None:
    python = tmp_path / "python"
    python.write_text("", encoding="utf-8")
    monkeypatch.setattr(drift, "VENV_PYTHON", python)

    def fake_run(cmd, cwd, timeout):
        return drift.subprocess.CompletedProcess(cmd, returncode, stdout=output, stderr="")

    monkeypatch.setattr(drift, "_run", fake_run)


def test_a_collection_with_errors_yields_no_python_test_count(monkeypatch, tmp_path):
    _stub_pytest(monkeypatch, tmp_path, PYTEST_TWO_ERRORS, returncode=2)
    fact = drift.compute_python_test_count()
    assert fact.skipped
    assert fact.value is None
    assert "pytest reported 2 collection errors" in fact.skip_reason


def test_a_clean_collection_yields_the_count(monkeypatch, tmp_path):
    _stub_pytest(monkeypatch, tmp_path, PYTEST_CLEAN, returncode=0)
    fact = drift.compute_python_test_count()
    assert (fact.skipped, fact.value) == (False, 2)


def test_a_nonzero_pytest_exit_without_an_error_count_yields_no_count(monkeypatch, tmp_path):
    _stub_pytest(monkeypatch, tmp_path, PYTEST_CLEAN, returncode=3)
    fact = drift.compute_python_test_count()
    assert fact.skipped
    assert "pytest exited 3" in fact.skip_reason


def test_no_venv_is_a_named_reason(monkeypatch, tmp_path):
    monkeypatch.setattr(drift, "VENV_PYTHON", tmp_path / "venv" / "bin" / "python")
    fact = drift.compute_python_test_count()
    assert fact.skipped
    assert "not found, so pytest could not run" in fact.skip_reason


def test_check_fails_when_a_fact_it_reads_could_not_be_computed(repo, capsys, monkeypatch):
    def facts_with_a_gap() -> dict:
        facts = _good_check_facts()
        facts["merged_prs"] = drift.Fact(
            "merged_prs", "Merged PR numbers per phase", None, "SKIPPED", "stub",
            True, "git log exited non-zero",
        )
        return facts

    monkeypatch.setattr(drift, "compute_check_facts", facts_with_a_gap)
    repo.write("README.md", "# Readme\n\nNothing wrong here.\n")
    rc, out = _check(capsys)
    assert rc == 1
    assert "could not compute Merged PR numbers per phase: git log exited non-zero" in out
    assert out.strip().splitlines()[-1].startswith("error:")


def test_check_fails_when_the_tracked_files_cannot_be_listed(repo, capsys, monkeypatch):
    monkeypatch.setattr(drift, "tracked_markdown_files", lambda: None)
    rc, out = _check(capsys)
    assert rc == 1
    assert "could not list the tracked markdown files" in out


def test_counts_fails_when_a_count_could_not_be_computed(monkeypatch, capsys):
    def counts_with_a_gap() -> dict:
        facts = _count_facts()
        facts["python_tests"] = drift.Fact(
            "python_tests", "Python tests", None, "SKIPPED", "stub", True,
            "pytest reported 2 collection errors",
        )
        return facts

    monkeypatch.setattr(drift, "compute_count_facts", counts_with_a_gap)
    rc = drift.main(["--counts"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "could not compute Python tests: pytest reported 2 collection errors" in out
    assert out.strip().splitlines()[-1].startswith("error:")
