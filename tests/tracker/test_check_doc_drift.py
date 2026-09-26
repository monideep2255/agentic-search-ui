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
