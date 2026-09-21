"""Does `docs/build/Debugging_guide.md` still describe the code that exists?

The guide names every Python file under `src/system_03_search_agent/` and says
what each one is for. That is a claim about the tree, and a claim about a tree
goes stale the moment someone adds a file. Nothing in this repository would
notice: a missing row reads exactly like a file nobody has needed yet.

THREE ARMS, because "the guide is stale" has three shapes and a path check
only sees two of them.

  Arm 1, a file was added or deleted. Set equality between the tree and the
  paths the guide names.

  Arm 2, a path the guide names does not exist. Catches a rename that updated
  the code and not the document, and catches an invented path.

  Arm 3, a file was REPURPOSED. Arms 1 and 2 both pass while a row describes
  a job the file no longer does, because the path is still correct. The
  manifest stores a hash of each file's docstring summary line, which is the
  exact sentence each row was written from. Change that line and the arm goes
  red asking for the row to be re-checked.

WHAT THIS FILE DOES NOT COVER, stated here rather than left to be discovered,
because `goal-contracts.md` requires a verify surface to declare its own gaps:

  - A behaviour change that leaves the docstring untouched. The guide
    describes stated purpose. Arm 3 proves a row still matches the statement,
    never that the statement is true.
  - Whether any row's prose is ACCURATE. No arm reads the row's meaning.
  - Files with no module docstring. They are exempt from arm 3 by necessity
    and are listed by name in the manifest under `no_docstring`, so the gap is
    countable rather than silent.
  - Backticked paths with no `/` in them, for example a bare `check_style.py`.
    Arm 2 skips those because a bare filename is ambiguous about its directory.
  - Paths outside `CHECKED_ROOTS`, notably `logs/`, which holds runtime
    artifacts that are gitignored and legitimately absent on a clean checkout.

Arm 3's noise trade-off is deliberate. A typo fix in a docstring fires it. That
is the price of catching a real repurpose, and the fix is one manifest line.
If it ever becomes not worth paying, DELETE the arm rather than loosening it.
An arm that cannot fail is not an arm, which is why each of the three has a
mutation case below proving it goes red.

Regenerate the manifest after a deliberate change:

    python tests/system_03_search_agent/test_debugging_guide_coverage.py

The generator and the arms share `docstring_summary`, so the two cannot drift.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "system_03_search_agent"
GUIDE = REPO_ROOT / "docs" / "build" / "Debugging_guide.md"
MANIFEST = Path(__file__).parent / "fixtures" / "debugging_guide_manifest.json"

# Arm 2 only resolves paths whose first segment is one of these. `logs/` is
# absent on purpose: it holds gitignored runtime artifacts. `reference/` is
# absent because it is a symlink into a different repository.
CHECKED_ROOTS = frozenset(
    {
        ".claude",
        ".github",
        "alembic",
        "docs",
        "eval",
        "frontend",
        "requirements",
        "services",
        "src",
        "tests",
        "tracker",
    }
)

# A backticked token with a dot and at least one slash. The slash requirement
# is what keeps a bare filename out; see the coverage note in the docstring.
_BACKTICKED_PATH = re.compile(r"`([A-Za-z0-9_.][A-Za-z0-9_.\-]*(?:/[A-Za-z0-9_.\-]+)+)`")


def src_files() -> list[str]:
    """Every Python file under `src/system_03_search_agent/`, repo-relative."""
    return sorted(
        str(path.relative_to(REPO_ROOT)) for path in SRC_ROOT.rglob("*.py")
    )


def docstring_summary(path: Path) -> str | None:
    """The first non-empty line of a module docstring, or None if there is none.

    This is the sentence each inventory row in the guide is written from, so it
    is the right thing to watch for drift. Shared by the arms and by the
    manifest generator so the two cannot disagree.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return None
    doc = ast.get_docstring(tree)
    if not doc:
        return None
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _digest(summary: str) -> str:
    return hashlib.sha256(summary.encode("utf-8")).hexdigest()


def build_manifest() -> dict:
    """Compute the manifest from the tree as it stands right now."""
    purposes: dict[str, str] = {}
    no_docstring: list[str] = []
    for relpath in src_files():
        summary = docstring_summary(REPO_ROOT / relpath)
        if summary is None:
            no_docstring.append(relpath)
        else:
            purposes[relpath] = _digest(summary)
    return {
        "note": (
            "Generated. Regenerate with: python "
            "tests/system_03_search_agent/test_debugging_guide_coverage.py"
        ),
        "purposes": purposes,
        "no_docstring": no_docstring,
    }


# --------------------------------------------------------------------------
# The three arms, as plain functions so the mutation cases can drive them.
# --------------------------------------------------------------------------


def missing_rows(guide_text: str) -> list[str]:
    """Arm 1: source files the guide never names."""
    return [relpath for relpath in src_files() if relpath not in guide_text]


def phantom_paths(guide_text: str) -> list[str]:
    """Arm 2: paths the guide names that are not on disk."""
    found = {match.group(1) for match in _BACKTICKED_PATH.finditer(guide_text)}
    phantoms = []
    for candidate in sorted(found):
        root = candidate.split("/", 1)[0]
        if root not in CHECKED_ROOTS:
            continue
        if not (REPO_ROOT / candidate).exists():
            phantoms.append(candidate)
    return phantoms


def drifted_purposes(manifest: dict) -> list[str]:
    """Arm 3: files whose docstring summary changed since their row was written."""
    drifted = []
    for relpath, recorded in sorted(manifest["purposes"].items()):
        summary = docstring_summary(REPO_ROOT / relpath)
        if summary is None or _digest(summary) != recorded:
            drifted.append(relpath)
    return drifted


# --------------------------------------------------------------------------
# The arms as tests.
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def guide_text() -> str:
    if not GUIDE.exists():
        pytest.fail(f"{GUIDE.relative_to(REPO_ROOT)} is missing")
    return GUIDE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def manifest() -> dict:
    if not MANIFEST.exists():
        pytest.fail(f"{MANIFEST.relative_to(REPO_ROOT)} is missing")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_every_source_file_has_a_row(guide_text: str) -> None:
    missing = missing_rows(guide_text)
    assert not missing, (
        f"{len(missing)} source file(s) have no row in the debugging guide. "
        f"Add a row for each, then regenerate the manifest. Missing: {missing}"
    )


def test_no_phantom_paths(guide_text: str) -> None:
    phantoms = phantom_paths(guide_text)
    assert not phantoms, (
        f"The debugging guide names {len(phantoms)} path(s) that do not exist. "
        f"A rename updated the code and not the document: {phantoms}"
    )


def test_no_repurposed_file_keeps_a_stale_row(manifest: dict) -> None:
    drifted = drifted_purposes(manifest)
    assert not drifted, (
        f"{len(drifted)} file(s) changed their docstring summary line since the "
        "debugging guide's row was written. Re-check each row against the file, "
        "then regenerate the manifest in the same commit. "
        f"Changed: {drifted}"
    )


def test_manifest_covers_every_source_file(manifest: dict) -> None:
    """The manifest itself must not silently drop a file."""
    recorded = set(manifest["purposes"]) | set(manifest["no_docstring"])
    assert recorded == set(src_files()), (
        "The manifest and the source tree disagree. Regenerate it: "
        "python tests/system_03_search_agent/test_debugging_guide_coverage.py"
    )


# --------------------------------------------------------------------------
# Mutation cases. Each proves its arm can go red, not merely that it is green.
# --------------------------------------------------------------------------


def test_arm_one_goes_red_when_a_row_is_deleted(guide_text: str) -> None:
    victim = src_files()[0]
    mutated = guide_text.replace(victim, "")
    assert victim in missing_rows(mutated)


def test_arm_two_goes_red_on_an_invented_path(guide_text: str) -> None:
    invented = "src/system_03_search_agent/does_not_exist_anywhere.py"
    mutated = f"{guide_text}\n\n| `{invented}` | x | y |\n"
    assert invented in phantom_paths(mutated)


def test_arm_three_goes_red_when_a_summary_changes(manifest: dict) -> None:
    victim = next(iter(sorted(manifest["purposes"])))
    mutated = {
        "purposes": dict(manifest["purposes"], **{victim: _digest("a different purpose")}),
        "no_docstring": manifest["no_docstring"],
    }
    assert victim in drifted_purposes(mutated)


if __name__ == "__main__":
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(
        json.dumps(build_manifest(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {MANIFEST.relative_to(REPO_ROOT)}")
