"""The package check goes red when a package leaves something out.

Build phase 8.10, T-8.10-01. `.github/gates/check_packages_install.py` builds
every wheel, compares the server's with `src/`, installs each into an empty
environment, imports every module and runs every console script with
`--help`. Reading that script proves nothing about whether it can fail, so
these tests hand it broken packages and assert it says so, and a sound one
and assert it does not.

What this file covers:
    - Discovery of every distribution: the root and each `clients/*`.
    - The comparison with `src/`: a missing module and a missing data file.
    - The clean install: a module the wheel lacks, a console script whose
      `--help` fails, and the source tree kept out of reach.
    - The gate script's shape: one executable line, like every other gate.

What it does NOT cover: building a wheel. Wheels here are written by hand
with `zipfile`, so the suite needs no build backend and no network. The real
build runs in CI's own package-check step, on the real repository, and the
phase 8.10 builder report shows it red on the pre-8.10 `pyproject.toml` and
green after.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GATES = REPO_ROOT / ".github" / "gates"

_spec = importlib.util.spec_from_file_location(
    "check_packages_install", GATES / "check_packages_install.py"
)
check_packages_install = importlib.util.module_from_spec(_spec)
sys.modules["check_packages_install"] = check_packages_install
_spec.loader.exec_module(check_packages_install)

PACKAGE = "p810p_gate_demo"  # a name nothing else installs

_SOUND = {
    f"{PACKAGE}/__init__.py": "",
    f"{PACKAGE}/helper.py": "VALUE = 1\n",
    f"{PACKAGE}/cli.py": (
        f"from {PACKAGE} import helper\n\n\n"
        "def main():\n"
        "    print('usage: demo, value', helper.VALUE)\n"
        "    return 0\n"
    ),
}


def _wheel(directory: Path, files: dict[str, str], *, scripts: dict[str, str]) -> Path:
    """A minimal, valid wheel, written by hand."""
    dist_info = "p810p_gate_demo-0.1.dist-info"
    contents = dict(files)
    contents[f"{dist_info}/METADATA"] = "Metadata-Version: 2.1\nName: p810p-gate-demo\nVersion: 0.1\n"
    contents[f"{dist_info}/WHEEL"] = (
        "Wheel-Version: 1.0\nGenerator: hand\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    )
    if scripts:
        contents[f"{dist_info}/entry_points.txt"] = "[console_scripts]\n" + "".join(
            f"{name} = {target}\n" for name, target in scripts.items()
        )
    record = []
    for name, text in contents.items():
        data = text.encode()
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        record.append(f"{name},sha256={digest},{len(data)}")
    record.append(f"{dist_info}/RECORD,,")
    contents[f"{dist_info}/RECORD"] = "\n".join(record) + "\n"
    path = directory / "p810p_gate_demo-0.1-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        for name, text in contents.items():
            archive.writestr(name, text)
    return path


class TestDiscovery:
    def test_finds_the_root_and_every_client(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "root"\n')
        for name in ("zeta", "alpha"):
            (tmp_path / "clients" / name).mkdir(parents=True)
            (tmp_path / "clients" / name / "pyproject.toml").write_text(f'[project]\nname = "{name}"\n')
        (tmp_path / "clients" / "notes").mkdir()
        (tmp_path / "clients" / "tools-only").mkdir()
        (tmp_path / "clients" / "tools-only" / "pyproject.toml").write_text("[tool.ruff]\n")

        found = check_packages_install.distributions(tmp_path)
        assert found == [tmp_path, tmp_path / "clients" / "alpha", tmp_path / "clients" / "zeta"]

    def test_this_repository_has_both_distributions(self) -> None:
        found = check_packages_install.distributions(REPO_ROOT)
        assert found == [REPO_ROOT, REPO_ROOT / "clients" / "system3-cli"]


class TestTheComparisonWithSrc:
    def test_a_missing_module_and_a_missing_data_file_are_both_named(self, tmp_path: Path) -> None:
        # Mutation: compare only `.py` files -> the data file passes unseen,
        # which is how `personas_v1.json` was missing from every wheel.
        wheel = _wheel(tmp_path, {f"{PACKAGE}/__init__.py": ""}, scripts={})
        source = [
            Path(f"{PACKAGE}/__init__.py"),
            Path(f"{PACKAGE}/observability/__init__.py"),
            Path(f"{PACKAGE}/data/personas.json"),
            Path("unrelated_top_level/thing.py"),
        ]
        assert check_packages_install.missing_from_wheel(wheel, source) == [
            f"{PACKAGE}/data/personas.json",
            f"{PACKAGE}/observability/__init__.py",
        ]

    def test_a_complete_wheel_leaves_nothing_out(self, tmp_path: Path) -> None:
        wheel = _wheel(tmp_path, _SOUND, scripts={})
        source = [Path(name) for name in _SOUND]
        assert check_packages_install.missing_from_wheel(wheel, source) == []

    def test_staging_skips_what_a_clean_checkout_would_not_hold(self, tmp_path: Path) -> None:
        """Outside git, staging reads the filesystem; build output and caches
        must not stand in for a file the checkout lacks."""
        for relative in (
            "pyproject.toml",
            "src/pkg/__init__.py",
            "src/pkg/__pycache__/x.cpython-311.pyc",
            "src/pkg.egg-info/SOURCES.txt",
            "clients/c/build/lib/pkg/__init__.py",
            "clients/c/pyproject.toml",
        ):
            path = tmp_path / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("")
        listed = {p.as_posix() for p in check_packages_install.tracked_files(tmp_path)}
        assert listed == {"pyproject.toml", "src/pkg/__init__.py", "clients/c/pyproject.toml"}


class TestTheCleanInstall:
    def test_a_sound_wheel_passes(self, tmp_path: Path) -> None:
        wheel = _wheel(tmp_path, _SOUND, scripts={"p810p-demo": f"{PACKAGE}.cli:main"})
        assert check_packages_install.check_installed_wheel(wheel, tmp_path / "work") == []

    def test_a_module_the_wheel_lacks_fails_the_import_and_the_command(self, tmp_path: Path) -> None:
        # Mutation: let the clean environment see this checkout's `src/`, or
        # skip the import step -> the missing helper goes unnoticed.
        files = {k: v for k, v in _SOUND.items() if not k.endswith("helper.py")}
        wheel = _wheel(tmp_path, files, scripts={"p810p-demo": f"{PACKAGE}.cli:main"})
        problems = check_packages_install.check_installed_wheel(wheel, tmp_path / "work")
        assert any(p.startswith(f"import {PACKAGE}.cli:") and "helper" in p for p in problems), problems
        assert any(p.startswith("p810p-demo --help exited 1") for p in problems), problems

    def test_a_help_that_fails_is_named(self, tmp_path: Path) -> None:
        files = dict(_SOUND)
        files[f"{PACKAGE}/cli.py"] = "def main():\n    return 2\n"
        wheel = _wheel(tmp_path, files, scripts={"p810p-demo": f"{PACKAGE}.cli:main"})
        problems = check_packages_install.check_installed_wheel(wheel, tmp_path / "work")
        assert problems == ["p810p-demo --help exited 2: no output"]

    def test_an_egg_info_on_pythonpath_cannot_fake_an_install(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """CI's condition, found on the check's own final run: the job sets
        `PYTHONPATH: src`, and `pip install -e .` leaves an `.egg-info`
        there. The clean environment's pip then saw the distribution as
        already installed and installed nothing. Mutation: let `_run`
        inherit `PYTHONPATH` -> this reports a leak instead of passing."""
        leaked = tmp_path / "leaked_src"
        egg_info = leaked / "p810p_gate_demo.egg-info"
        egg_info.mkdir(parents=True)
        (egg_info / "PKG-INFO").write_text(
            "Metadata-Version: 2.1\nName: p810p-gate-demo\nVersion: 0.1\n", encoding="utf-8"
        )
        monkeypatch.setenv("PYTHONPATH", str(leaked))
        wheel = _wheel(tmp_path, _SOUND, scripts={"p810p-demo": f"{PACKAGE}.cli:main"})
        assert check_packages_install.check_installed_wheel(wheel, tmp_path / "work") == []

    def test_the_source_tree_and_a_stored_sign_in_are_out_of_reach(self, monkeypatch) -> None:
        monkeypatch.setenv("PYTHONPATH", "src")
        monkeypatch.setenv("S3_BASE_URL", "https://somewhere.example")
        env = check_packages_install.isolated_env(Path("/nonexistent-home"))
        assert "PYTHONPATH" not in env
        assert "S3_BASE_URL" not in env
        assert env["S3_CREDENTIALS_PATH"] == "/nonexistent-home/credentials"


class TestTheServersPyproject:
    """A fast, static half of the same check, for the unit suite: the full
    build runs only in CI's last step."""

    @staticmethod
    def _setuptools() -> dict:
        import tomllib

        return tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"][
            "setuptools"
        ]

    def test_packages_are_discovered_not_listed(self) -> None:
        """A hand-kept list missed `export`, then `observability` and `eval`."""
        packages = self._setuptools()["packages"]
        assert packages == {"find": {"where": ["src"], "include": ["system_03_search_agent*"]}}

    def test_every_data_file_under_the_package_is_declared(self) -> None:
        # Mutation: drop the `system_03_search_agent.orchestrator` line from
        # `[tool.setuptools.package-data]` -> this names few_shot_examples.json.
        from fnmatch import fnmatch

        declared = self._setuptools().get("package-data", {})
        package_root = REPO_ROOT / "src"
        undeclared = []
        for path in check_packages_install.tracked_files(REPO_ROOT):
            if path.parts[:2] != ("src", "system_03_search_agent") or path.suffix == ".py":
                continue
            package = ".".join(path.parts[1:-1])
            patterns = declared.get(package, [])
            if not any(fnmatch(path.name, pattern) for pattern in patterns):
                undeclared.append(path.as_posix())
        assert (package_root / "system_03_search_agent" / "data" / "personas_v1.json").exists()
        assert undeclared == []


class TestTheGateScript:
    def test_it_is_one_line_calling_the_check_like_every_other_gate(self) -> None:
        script = GATES / "gate_packages_install.sh"
        lines = script.read_text(encoding="utf-8").splitlines()
        assert lines[0] == "#!/usr/bin/env bash"
        executable = [line for line in lines[1:] if line.strip() and not line.lstrip().startswith("#")]
        assert executable == ["set -euo pipefail", "python .github/gates/check_packages_install.py"]
        assert script.stat().st_mode & 0o111
