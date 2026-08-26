"""Tests for the three CI assertion scripts.

Build phase 4.14, finding F-4.14-A-08: these three scripts are the only new
executable logic the phase produced, they decide whether gates 4, 5 and 9 mean
anything, and the first version of the phase shipped them with no test at all.
That absence is the direct cause of F-4.14-A-01, A-02, A-06 and A-11, every one
of which a single test here would have caught.

The scripts live under `.github/scripts/` rather than in an importable package,
so they are loaded by path. That is deliberate on their side: they must run on a
runner before any install step has necessarily succeeded, so they import nothing
outside the standard library and belong to no package.

WHAT THIS COVERS, stated so a gap is arguable:

    Covered      Both directions for each script. That each one goes RED on the
                 failure it exists to catch, and stays QUIET on the real,
                 healthy reports this repository actually produces. That each
                 fails CLOSED on a missing, empty, truncated, or
                 entity-bearing report, since "I could not verify X" is a fail.

    NOT covered  The scripts' behaviour on a JUnit dialect other than pytest's.
                 Nothing else writes these reports here.

Depends on:
    - .github/scripts/assert_no_db_skips.py
    - .github/scripts/assert_required_paths_ran.py
    - .github/scripts/assert_gate_ran.py

Writes:
    - Nothing outside pytest's own tmp_path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / ".github" / "scripts"


def _load(name: str) -> ModuleType:
    path = SCRIPTS / f"{name}.py"
    assert path.exists(), f"the CI script {path} is missing"
    spec = importlib.util.spec_from_file_location(f"_ci_{name}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


no_db_skips = _load("assert_no_db_skips")
required_paths = _load("assert_required_paths_ran")
gate_ran = _load("assert_gate_ran")


# ---------------------------------------------------------------------------
# Report building
# ---------------------------------------------------------------------------


def _case(classname: str, name: str, *, skip: str | None = None, fail: bool = False) -> str:
    body = ""
    if skip is not None:
        body = f'<skipped message="{skip}"/>'
    elif fail:
        body = '<failure message="boom"/>'
    if body:
        return f'<testcase classname="{classname}" name="{name}">{body}</testcase>'
    return f'<testcase classname="{classname}" name="{name}"/>'


def _report(tmp_path: Path, cases: list[str], filename: str = "report.xml") -> str:
    path = tmp_path / filename
    path.write_text(
        '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest">'
        + "".join(cases)
        + "</testsuite></testsuites>",
        encoding="utf-8",
    )
    return str(path)


def _bulk(count: int, classname: str = "tests.some.module", prefix: str = "test_ok") -> list[str]:
    return [_case(classname, f"{prefix}_{index}") for index in range(count)]


# ---------------------------------------------------------------------------
# assert_no_db_skips
# ---------------------------------------------------------------------------


class TestNoDatabaseSkips:
    def test_a_healthy_run_passes(self, tmp_path):
        report = _report(tmp_path, _bulk(600))
        assert no_db_skips.main(["prog", report]) == 0

    def test_the_sanctioned_premise_gate_skips_stay_quiet(self, tmp_path):
        """The 104 RUN_PREMISE_GATE arms are deliberate and must not fail CI.

        A gate that fails for being right is a gate someone switches off.
        """
        cases = _bulk(600) + [
            _case("tests.x", f"test_live_{i}", skip="set RUN_PREMISE_GATE=1 to run this gate")
            for i in range(20)
        ]
        assert no_db_skips.main(["prog", _report(tmp_path, cases)]) == 0

    @pytest.mark.parametrize(
        "phrasing",
        [
            # The phrasing that actually exists in this repository and that the
            # FIRST version of the script missed (F-4.14-A-01).
            "user database unreachable at postgresql://localhost:5432/search_agent_users",
            "search_agent_users PostgreSQL database is not reachable; set USER_DB_URL",
            # Phrasings nobody has written yet. A deny-list loses to these; an
            # allow-list does not (F-4.14-A-02).
            "requires a running database",
            "PostgreSQL is not available",
            "connection refused on 127.0.0.1:5432",
            "no DB, skipping",
            "db fixture unavailable",
            "could not reach the store",
        ],
    )
    def test_any_unsanctioned_skip_fails_whatever_its_wording(self, tmp_path, phrasing):
        cases = _bulk(600) + [_case("tests.x", "test_needs_db", skip=phrasing)]
        assert no_db_skips.main(["prog", _report(tmp_path, cases)]) == 1

    def test_a_short_report_fails_rather_than_certifying_nothing(self, tmp_path):
        """F-4.14-A-11: the populate-check.

        A report with no unsanctioned skips in it, because it has almost nothing
        in it, proves nothing at all.
        """
        assert no_db_skips.main(["prog", _report(tmp_path, _bulk(5))]) == 1

    def test_an_empty_report_fails(self, tmp_path):
        assert no_db_skips.main(["prog", _report(tmp_path, [])]) == 1

    def test_a_missing_report_fails(self, tmp_path):
        assert no_db_skips.main(["prog", str(tmp_path / "nope.xml")]) == 1

    def test_a_truncated_report_fails(self, tmp_path):
        path = tmp_path / "truncated.xml"
        path.write_text('<?xml version="1.0"?><testsuites><testsuite', encoding="utf-8")
        assert no_db_skips.main(["prog", str(path)]) == 1

    def test_an_entity_bearing_report_is_refused_before_parsing(self, tmp_path):
        path = tmp_path / "entity.xml"
        path.write_text(
            '<?xml version="1.0"?><!DOCTYPE t [<!ENTITY a "b">]><testsuites/>', encoding="utf-8"
        )
        assert no_db_skips.main(["prog", str(path)]) == 1

    def test_wrong_argument_count_fails(self):
        assert no_db_skips.main(["prog"]) == 1


# ---------------------------------------------------------------------------
# assert_required_paths_ran
# ---------------------------------------------------------------------------

_REQUIRED_MODULE = "tests.system_03_search_agent.synthesis.test_required_paths"


class TestRequiredPathsRan:
    def test_the_real_report_passes(self, tmp_path):
        cases = _bulk(20, classname=_REQUIRED_MODULE, prefix="test_ground")
        assert required_paths.main(["prog", _report(tmp_path, cases)]) == 0

    def test_an_empty_collection_fails(self, tmp_path):
        """`pytest` exits 0 on an empty collection, which is the whole risk."""
        assert required_paths.main(["prog", _report(tmp_path, [])]) == 1

    def test_a_gutted_file_fails_the_count_floor(self, tmp_path):
        cases = _bulk(2, classname=_REQUIRED_MODULE)
        assert required_paths.main(["prog", _report(tmp_path, cases)]) == 1

    def test_unrelated_tests_named_for_the_required_paths_are_rejected(self, tmp_path):
        """F-4.14-A-06.

        The first version matched test NAMES against substrings, and the
        adversary satisfied it with `assert True` tests called
        `test_the_citation_widget_renders_a_blue_border` and
        `test_the_settings_page_refuses_to_scroll_horizontally`. Identity, not
        naming, is what anchors this gate now.
        """
        cases = [
            _case("tests.frontend.test_widgets", f"test_the_citation_widget_refuses_{i}")
            for i in range(20)
        ]
        assert required_paths.main(["prog", _report(tmp_path, cases)]) == 1

    def test_a_skipped_required_path_fails(self, tmp_path):
        cases = _bulk(19, classname=_REQUIRED_MODULE) + [
            _case(_REQUIRED_MODULE, "test_skipped_one", skip="whatever the reason")
        ]
        assert required_paths.main(["prog", _report(tmp_path, cases)]) == 1

    def test_a_failing_required_path_fails(self, tmp_path):
        cases = _bulk(19, classname=_REQUIRED_MODULE) + [
            _case(_REQUIRED_MODULE, "test_broken", fail=True)
        ]
        assert required_paths.main(["prog", _report(tmp_path, cases)]) == 1

    def test_a_missing_report_fails(self, tmp_path):
        assert required_paths.main(["prog", str(tmp_path / "nope.xml")]) == 1


# ---------------------------------------------------------------------------
# assert_gate_ran
# ---------------------------------------------------------------------------


class TestGateRan:
    def test_a_run_that_executed_tests_passes(self, tmp_path):
        assert gate_ran.main(["prog", _report(tmp_path, _bulk(5))]) == 0

    def test_an_all_skipped_run_fails(self, tmp_path):
        """F-4.14-A-03, the exact shape gate 5 exhibited.

        Twenty-three skipped, zero passed, `pytest` exits 0, and GitHub renders
        an ordinary green check.
        """
        cases = [_case("tests.x", f"test_{i}", skip="graph unreachable") for i in range(23)]
        assert gate_ran.main(["prog", _report(tmp_path, cases)]) == 1

    def test_an_empty_run_fails(self, tmp_path):
        assert gate_ran.main(["prog", _report(tmp_path, [])]) == 1

    def test_a_failing_run_does_not_count_as_executed(self, tmp_path):
        cases = [_case("tests.x", f"test_{i}", fail=True) for i in range(5)]
        assert gate_ran.main(["prog", _report(tmp_path, cases)]) == 1

    def test_the_minimum_is_configurable(self, tmp_path):
        report = _report(tmp_path, _bulk(3))
        assert gate_ran.main(["prog", report, "--min-passed", "3"]) == 0
        assert gate_ran.main(["prog", report, "--min-passed", "4"]) == 1

    def test_a_missing_report_fails(self, tmp_path):
        assert gate_ran.main(["prog", str(tmp_path / "nope.xml")]) == 1
