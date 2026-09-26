"""`system3-cli` stays small: exact pins, and nothing of the server's.

Build phase 8.10, T-8.10-04, the acceptance line "I install one small
package and get `s3` and an MCP server, without the whole backend."

`clients/system3-cli/pyproject.toml` builds its wheel from this repository's
own `src/`, listing only the packages `s3` needs. Two things can break that
without anyone editing the pyproject, and each has an arm here:

    - `s3` starts importing a first-party module outside those packages.
      The installed wheel would then fail with ModuleNotFoundError, the
      exact defect T-8.10-01 found in `s3-kgx-export`.
    - `s3` starts importing a third-party package the wheel does not
      declare, or one of the server's (FastAPI, LangGraph, the MCP SDK...).
      The small package would then either break or quietly grow.

Both are checked by importing every `s3` module, and running `s3 --help`, in
a fresh interpreter that behaves like a clean `system3-cli` install: an import
hook makes every third-party package the wheel does not declare unimportable,
exactly as it would be after `pip install system3-cli` into an empty
environment. The dev environment has every server package installed, so
without the hook "it imported" would prove nothing. With it, a hard import of
anything undeclared fails the probe and names the package, while an optional
import (`httpx` tries `zstandard`, `rich` and `click` if present) degrades the
way it would for a real user.

The CI check `.github/gates/gate_packages_install.sh` then builds the real
wheel and runs `s3 --help` from it in a clean environment.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
CLIENT_PYPROJECT = REPO_ROOT / "clients" / "system3-cli" / "pyproject.toml"
ROOT_PYPROJECT = REPO_ROOT / "pyproject.toml"

# The only distributions the package may install: `httpx`, `pydantic` and
# their closure. The MCP SDK is deliberately not here (`mcp==2.0.0` requires
# uvicorn and starlette); see `adapters/cli/mcp_bridge.py`.
ALLOWED_DISTRIBUTIONS = {
    "httpx",
    "pydantic",
    "annotated-types",
    "anyio",
    "certifi",
    "h11",
    "httpcore",
    "idna",
    "pydantic-core",
    "typing-extensions",
    "typing-inspection",
}

# The import names those distributions provide.
ALLOWED_THIRD_PARTY_IMPORTS = {
    "httpx",
    "pydantic",
    "annotated_types",
    "anyio",
    "certifi",
    "h11",
    "httpcore",
    "idna",
    "pydantic_core",
    "typing_extensions",
    "typing_inspection",
}

# Named in the ticket's acceptance, plus the rest of the server's own
# dependencies, so a failure names the culprit.
SERVER_ONLY = {
    "fastapi",
    "uvicorn",
    "starlette",
    "sse_starlette",
    "langgraph",
    "langchain_core",
    "litellm",
    "anthropic",
    "openai",
    "psycopg2",
    "redis",
    "sqlalchemy",
    "alembic",
    "strawberry",
    "mcp",
    "mcp_types",
    "httpx2",
    "jwt",
    "argon2",
    "dotenv",
    "yaml",
}

_PROBE = """
import importlib.abc, json, sys

ALLOWED = set(json.loads(sys.argv[1]))
already_loaded = set(sys.modules)


class OnlyWhatTheWheelDeclares(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        top = name.split(".")[0]
        if (
            top in sys.stdlib_module_names
            or top == "system_03_search_agent"
            or top in ALLOWED
            or top.startswith("_")
        ):
            return None
        raise ModuleNotFoundError(
            f"{name} is not installed with system3-cli", name=name
        )


sys.meta_path.insert(0, OnlyWhatTheWheelDeclares())

import contextlib, io
import system_03_search_agent.adapters.cli.client
import system_03_search_agent.adapters.cli.credentials
import system_03_search_agent.adapters.cli.main as main
import system_03_search_agent.adapters.cli.mcp_bridge
import system_03_search_agent.adapters.cli.render
import system_03_search_agent.adapters.cli.sse
with contextlib.redirect_stdout(io.StringIO()):
    code = main.main(["--help"])
print(json.dumps({"code": code, "modules": sorted(set(sys.modules) - already_loaded)}))
"""


def _client_config() -> dict:
    return tomllib.loads(CLIENT_PYPROJECT.read_text(encoding="utf-8"))


def _imported_by_s3() -> tuple[int, list[str]]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("S3_")}
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-c", _PROBE, json.dumps(sorted(ALLOWED_THIRD_PARTY_IMPORTS))],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT / "clients" / "system3-cli"),
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout.strip().splitlines()[-1])
    return report["code"], report["modules"]


def test_every_dependency_is_pinned_exactly_and_is_on_the_allowed_list() -> None:
    # Mutation: loosen any pin to `>=`, or add `mcp==2.0.0` -> this fails.
    dependencies = _client_config()["project"]["dependencies"]
    names = set()
    for requirement in dependencies:
        match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([0-9][0-9A-Za-z.]*)", requirement)
        assert match, f"not an exact pin: {requirement!r}"
        names.add(match.group(1).lower().replace("_", "-"))
    assert names == ALLOWED_DISTRIBUTIONS


def test_the_build_backend_is_pinned_too() -> None:
    requires = _client_config()["build-system"]["requires"]
    assert all("==" in item for item in requires), requires


def test_s3_is_the_same_entry_point_as_the_servers_distribution() -> None:
    root = tomllib.loads(ROOT_PYPROJECT.read_text(encoding="utf-8"))
    assert _client_config()["project"]["scripts"]["s3"] == root["project"]["scripts"]["s3"]


def test_the_wheel_is_built_from_the_servers_own_source_files() -> None:
    """No second copy: the package directory tracks no Python at all.

    Tracked files, not the directory's contents: building the wheel in place
    leaves a gitignored `build/lib` copy there, which is build output rather
    than a second source."""
    assert _client_config()["tool"]["setuptools"]["package-dir"] == {"": "../../src"}
    listed = subprocess.run(
        ["git", "ls-files", "--", "clients/system3-cli"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert "clients/system3-cli/pyproject.toml" in listed
    assert [name for name in listed if name.endswith(".py")] == []


def test_s3_imports_only_what_the_package_ships_and_declares() -> None:
    # Mutation: add `import fastapi` (or `from system_03_search_agent.harness
    # import cost_control`) to `mcp_bridge.py` -> this fails, naming it.
    code, modules = _imported_by_s3()
    assert code == 0

    packaged = set(_client_config()["tool"]["setuptools"]["packages"])
    first_party = [m for m in modules if m.split(".")[0] == "system_03_search_agent"]
    outside = [
        m for m in first_party if m not in packaged and m.rsplit(".", 1)[0] not in packaged
    ]
    assert outside == [], f"s3 imports modules the wheel does not ship: {outside}"

    top_level = {m.split(".")[0] for m in modules}
    third_party = {
        name
        for name in top_level
        if name not in sys.stdlib_module_names
        and name != "system_03_search_agent"
        and not name.startswith("_")
        and name not in {"__main__", "__mp_main__"}
    }
    assert third_party & SERVER_ONLY == set(), f"server packages imported: {third_party & SERVER_ONLY}"
    assert third_party <= ALLOWED_THIRD_PARTY_IMPORTS, (
        f"undeclared packages imported: {sorted(third_party - ALLOWED_THIRD_PARTY_IMPORTS)}"
    )
