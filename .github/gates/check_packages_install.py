"""Every wheel this repository makes installs and its commands start.

Build phase 8.10, T-8.10-01 (`tracker/phase_8.10.md`): "A package that
leaves out a module fails CI, not a user." Run by
`.github/gates/gate_packages_install.sh`.

The defect this exists for. `pyproject.toml` kept a hand-written package list
that missed `observability` and `eval`, so `s3-kgx-export --help` crashed with
ModuleNotFoundError from every installed copy, and the wheel also left out
the two JSON files the server reads. Nothing noticed for four weeks, because
every test and every deployment reads the source tree through `PYTHONPATH`,
never the package. This check reads the package.

For each distribution (the root `pyproject.toml`, and every
`clients/*/pyproject.toml`), in order:

    1. Stage: copy the git-tracked files a build reads (`pyproject.toml`,
       `src/`, `clients/`) into a temporary tree. The build then sees what a
       clean checkout holds: no untracked file can hide a gap, and no stale
       `build/` directory can carry a deleted module into a wheel.
    2. Build its wheel with pip.
    3. Compare (the root distribution only): every tracked file under
       `src/system_03_search_agent/`, Python or data, must be in the wheel.
       A client distribution ships a deliberate subset, so it is not
       compared; step 5 catches a module it needs and lacks.
    4. Install the wheel, with no dependencies, into a new, empty virtual
       environment. Its third-party dependencies are reached through one path
       entry to this interpreter's own site-packages, so no network is used
       and the versions are the ones this environment already vetted. The
       first-party code can only come from the wheel: the source tree is not
       on the path, the working directory is a temporary one, and a `.pth`
       file inside that site-packages (such as an editable install's) is not
       processed, because Python processes `.pth` files only in a site
       directory, never in a path a `.pth` line adds.
    5. Import every first-party module the wheel ships.
    6. Run every console script the wheel declares with `--help`: it must
       exit 0, print something, and print no traceback.

What this does NOT cover, stated so a gap is arguable rather than discovered
(`.claude/rules/goal-contracts.md`):

    - Resolving the declared dependencies from a package index. Step 4 uses
      this environment's copies, so a dependency the wheel forgets to declare
      is not caught here. `test_system3_cli_package.py` covers that for
      `system3-cli`, which is the package people outside the project install.
    - Whether a command works beyond `--help`. The unit suite covers that.
    - A module that needs a running service at import time. None does today;
      the environment variables CI sets are enough to import every module.

Usage:
    python .github/gates/check_packages_install.py [--repo-root DIR]
        [--build-isolation auto|on|off]

`auto`, the default, builds without isolation when this interpreter can build
a wheel itself (setuptools 70.1 or later, or the `wheel` package), so a local
run needs no network, and with isolation otherwise, which is the case on CI.

Depends on:
    - pip, venv and zipfile, from this interpreter
    - git, to list tracked files (a tree that is not a git checkout is
      staged from the filesystem instead)

Writes:
    - Nothing outside a temporary directory, removed on exit.
"""

from __future__ import annotations

import argparse
import configparser
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import tomllib
import zipfile
from pathlib import Path

_TIMEOUT_S = 600
_STAGED_TOP_LEVEL = ("pyproject.toml", "src", "clients")
_SKIPPED_PARTS = {"__pycache__", "build", "dist"}

# Run by the fresh environment's own interpreter, with the wheel's module
# names as its argument. Prints a JSON list of "module: ErrorType: message".
_IMPORT_EVERY_MODULE = """
import importlib, json, sys, traceback
failures = []
for name in json.loads(sys.argv[1]):
    try:
        importlib.import_module(name)
    except BaseException as exc:
        last = traceback.format_exception_only(type(exc), exc)[-1].strip()
        failures.append(f"{name}: {last}")
print(json.dumps(failures))
"""


# Never inherited by anything this check starts. Found on the check's own
# final run: CI's Python job sets `PYTHONPATH: src`, and `pip install -e .`
# leaves `src/agentic_search_ui.egg-info` behind. With both, the "empty"
# environment's pip saw the distribution as already installed, installed
# nothing, and the check then looked for a command that was never created.
_NEVER_INHERITED = ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE")


def _base_env() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in _NEVER_INHERITED}
    env["PYTHONNOUSERSITE"] = "1"
    return env


def _run(
    command: list[str], *, env: dict[str, str] | None = None, **kwargs: object
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_S,
        check=False,
        env=_base_env() if env is None else env,
        **kwargs,
    )


def distributions(repo_root: Path) -> list[Path]:
    """Every directory holding a `pyproject.toml` with a `[project]` table:
    the root, then each `clients/*` in name order."""
    found = []
    for candidate in [repo_root, *sorted((repo_root / "clients").glob("*"))]:
        pyproject = candidate / "pyproject.toml"
        if pyproject.is_file() and "project" in tomllib.loads(pyproject.read_text("utf-8")):
            found.append(candidate)
    return found


def tracked_files(repo_root: Path) -> list[Path]:
    """The files a build reads, as a clean checkout holds them."""
    listed = _run(["git", "ls-files", "-z", "--", *_STAGED_TOP_LEVEL], cwd=str(repo_root))
    if listed.returncode == 0 and listed.stdout:
        return [Path(p) for p in listed.stdout.split("\0") if p]
    files = []
    for top in _STAGED_TOP_LEVEL:
        root = repo_root / top
        if root.is_file():
            files.append(Path(top))
        elif root.is_dir():
            for path in root.rglob("*"):
                relative = path.relative_to(repo_root)
                if path.is_file() and not _SKIPPED_PARTS & set(relative.parts) and not any(
                    part.endswith(".egg-info") for part in relative.parts
                ) and path.suffix != ".pyc":
                    files.append(relative)
    return sorted(files)


def stage(repo_root: Path, destination: Path) -> list[Path]:
    files = tracked_files(repo_root)
    for relative in files:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo_root / relative, target)
    return files


def can_build_without_isolation() -> bool:
    try:
        version = importlib.metadata.version("setuptools")
    except importlib.metadata.PackageNotFoundError:
        return False
    major, minor = (int(part) for part in version.split(".")[:2])
    if (major, minor) >= (70, 1):
        return True
    try:
        importlib.metadata.version("wheel")
    except importlib.metadata.PackageNotFoundError:
        return False
    return True


def build_wheel(project: Path, out_dir: Path, *, isolation: bool) -> Path:
    command = [sys.executable, "-m", "pip", "wheel", "--no-deps", "-q", "-w", str(out_dir)]
    if not isolation:
        command.append("--no-build-isolation")
    result = _run([*command, str(project)])
    if result.returncode != 0:
        tail = (result.stderr or result.stdout).strip().splitlines()[-5:]
        raise RuntimeError("the wheel did not build: " + " | ".join(tail))
    wheels = sorted(out_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected one wheel, found {len(wheels)}")
    return wheels[0]


def wheel_names(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as archive:
        return archive.namelist()


def missing_from_wheel(wheel: Path, source_files: list[Path]) -> list[str]:
    """Every tracked file under a top-level package the wheel ships, that the
    wheel does not contain. `source_files` are relative to the directory the
    packages live in (`src/` for this repository)."""
    names = set(wheel_names(wheel))
    top_level = {name.split("/")[0] for name in names if "/" in name and ".dist-info" not in name}
    missing = []
    for relative in source_files:
        if (
            relative.parts
            and relative.parts[0] in top_level
            and relative.as_posix() not in names
        ):
            missing.append(relative.as_posix())
    return sorted(missing)


def first_party_modules(wheel: Path) -> list[str]:
    modules = []
    for name in wheel_names(wheel):
        if not name.endswith(".py") or ".dist-info/" in name or ".data/" in name:
            continue
        parts = name[: -len(".py")].split("/")
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if parts:
            modules.append(".".join(parts))
    return sorted(modules)


def console_scripts(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as archive:
        entry_points = [n for n in archive.namelist() if n.endswith(".dist-info/entry_points.txt")]
        if not entry_points:
            return []
        parser = configparser.ConfigParser()
        parser.read_string(archive.read(entry_points[0]).decode("utf-8"))
    if not parser.has_section("console_scripts"):
        return []
    return sorted(parser.options("console_scripts"))


def clean_environment(directory: Path) -> tuple[Path, Path]:
    """A new virtual environment with no packages, whose third-party imports
    resolve through this interpreter's site-packages. Returns its Python and
    its scripts directory."""
    result = _run([sys.executable, "-m", "venv", "--without-pip", str(directory)])
    if result.returncode != 0:
        raise RuntimeError(f"could not create a virtual environment: {result.stderr.strip()}")
    scripts = directory / ("Scripts" if os.name == "nt" else "bin")
    python = scripts / ("python.exe" if os.name == "nt" else "python")
    site = _run(
        [str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"]
    ).stdout.strip()
    ours = {sysconfig.get_paths()["purelib"], sysconfig.get_paths()["platlib"]}
    (Path(site) / "_dependencies_from_the_checking_interpreter.pth").write_text(
        "".join(f"{path}\n" for path in sorted(ours)), encoding="utf-8"
    )
    return python, scripts


def isolated_env(home: Path) -> dict[str, str]:
    """This process's environment without anything that would put the source
    tree or a stored sign-in in reach of the installed commands."""
    env = {
        key: value
        for key, value in _base_env().items()
        if key != "VIRTUAL_ENV" and not key.startswith("S3_")
    }
    env["S3_CREDENTIALS_PATH"] = str(home / "credentials")
    return env


def check_installed_wheel(wheel: Path, work: Path) -> list[str]:
    """Steps 4 to 6 for one wheel. Returns the problems found."""
    problems: list[str] = []
    python, scripts = clean_environment(work / "venv")
    installed = _run(
        [
            sys.executable, "-m", "pip", "--python", str(python), "install",
            "--no-deps", "--no-index", "-q", str(wheel),
        ]
    )
    if installed.returncode != 0:
        return [f"the wheel did not install: {installed.stderr.strip()[-300:]}"]
    if "already installed" in installed.stdout + installed.stderr:
        # An empty environment cannot already hold the distribution. If pip
        # says it does, something outside the environment is on its path,
        # and every result below would be about that, not the wheel.
        return [
            (
                "pip reported the wheel as already installed in an empty environment, so "
                "something outside it is on the path; nothing below would test the wheel"
            )
        ]

    home = work / "home"
    home.mkdir(mode=0o700)
    env = isolated_env(home)
    imported = _run(
        [str(python), "-c", _IMPORT_EVERY_MODULE, json.dumps(first_party_modules(wheel))],
        cwd=str(work),
        env=env,
    )
    try:
        failures = json.loads(imported.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        failures = [f"the import check itself failed: {imported.stderr.strip()[-300:]}"]
    problems.extend(f"import {failure}" for failure in failures)

    for script in console_scripts(wheel):
        path = scripts / (f"{script}.exe" if os.name == "nt" else script)
        if not path.exists():
            problems.append(f"{script} was not installed as a command")
            continue
        ran = _run([str(path), "--help"], cwd=str(work), env=env)
        output = ran.stdout + ran.stderr
        if ran.returncode != 0 or not ran.stdout.strip() or "Traceback" in output:
            last = (output.strip().splitlines() or ["no output"])[-1]
            problems.append(f"{script} --help exited {ran.returncode}: {last[:200]}")
    return problems


def check(repo_root: Path, *, isolation: bool) -> list[tuple[str, list[str]]]:
    """Every distribution's name and its problems, in order."""
    results: list[tuple[str, list[str]]] = []
    with tempfile.TemporaryDirectory(prefix="packages_install_") as temporary:
        work_root = Path(temporary)
        staged = work_root / "tree"
        files = stage(repo_root, staged)
        for index, project in enumerate(distributions(staged)):
            label = project.relative_to(staged).as_posix() or "."
            work = work_root / f"dist{index}"
            work.mkdir()
            try:
                wheel = build_wheel(project, work / "wheel", isolation=isolation)
            except RuntimeError as exc:
                results.append((label, [str(exc)]))
                continue
            problems: list[str] = []
            if project == staged:
                source = [f.relative_to("src") for f in files if f.parts[:1] == ("src",)]
                problems.extend(
                    f"left out of the wheel: src/{name}"
                    for name in missing_from_wheel(wheel, source)
                )
            problems.extend(check_installed_wheel(wheel, work))
            results.append((f"{label} ({wheel.name})", problems))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo-root", default=".", help="the checkout to check (default: .)")
    parser.add_argument(
        "--build-isolation",
        choices=["auto", "on", "off"],
        default="auto",
        help="build each wheel in an isolated environment (default: auto)",
    )
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    if args.build_isolation == "auto":
        isolation = not can_build_without_isolation()
    else:
        isolation = args.build_isolation == "on"

    results = check(repo_root, isolation=isolation)
    if not results:
        print("FAIL no distribution found; this check ran empty")
        return 1
    for label, problems in results:
        if problems:
            print(f"FAIL {label}")
            for problem in problems:
                print(f"     {problem}")
        else:
            print(f"PASS {label}: installs cleanly, every module imports, every command's --help works")
    failed = sum(1 for _, problems in results if problems)
    print(f"{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
