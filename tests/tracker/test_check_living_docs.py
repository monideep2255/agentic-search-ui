"""Does the living-documents check still catch a changed shape, with no date gate?

`tracker/check_living_docs.py` reads the registry, `tracker/Living_documents.md`,
and proves every anchor it names still exists in its document. Until
2026-09-25 it also had a `--fresh` arm that required every registered document
to carry today's date, and `/ship` refused to push until it did. Build harness
review item D2 removed that arm and the registry's Freshness column, delegated
by the product owner on 2026-09-25 (DECISIONS.md, "The lead implements both
harness reviews' takeaways").

What this file pins down:

- The registry parses as five columns, and a six-column row is refused rather
  than read with its cells shifted.
- `--shape` still reports a missing anchor, a missing file and an unpinned row,
  and passes when every anchor is present.
- An old date in a registered document is not a problem.

The shape tests build their own registry rows and documents under `tmp_path`,
so none depends on the state of this repository's real documents. The one test
that reads the real registry checks only that it parses.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKER_DIR = REPO_ROOT / "tracker"


def _load(name: str):
    """Import a `tracker/` script by path; `tracker/` is not a package."""
    if str(TRACKER_DIR) not in sys.path:
        sys.path.insert(0, str(TRACKER_DIR))
    spec = importlib.util.spec_from_file_location(name, TRACKER_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


living = _load("check_living_docs")

HEADER = "| Document | Job | Owner | Shape | Set by |\n|---|---|---|---|---|\n"


def _rows(*lines: str):
    return living.parse_registry(HEADER + "".join(line + "\n" for line in lines))


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(living, "REPO_ROOT", tmp_path)
    return tmp_path


def test_the_real_registry_parses_as_five_columns():
    """`parse_registry` raises on any row that is not five cells, so parsing
    the real registry is the assertion."""
    assert living.parse_registry(living.REGISTRY.read_text(encoding="utf-8"))


def test_a_six_column_row_is_refused():
    with pytest.raises(ValueError, match="expected 5"):
        living.parse_registry(
            "| Document | Job | Owner | Shape | Freshness | Set by |\n"
            "|---|---|---|---|---|---|\n"
            "| `HANDOFF.md` | j | o | `## A` | `Last updated:` | s |\n"
        )


def test_shape_passes_when_every_anchor_is_present(root):
    (root / "Doc.md").write_text("# Doc\n\nLast updated: 2020-01-01.\n\n## A\n\nPrefix: x\n", encoding="utf-8")
    rows = _rows("| `Doc.md` | j | o | `## A`; `Prefix:` | s |")
    assert living.check_shape(rows) == []


def test_shape_reports_a_missing_anchor(root):
    (root / "Doc.md").write_text("# Doc\n\n## B\n", encoding="utf-8")
    rows = _rows("| `Doc.md` | j | o | `## A` | s |")
    assert living.check_shape(rows) == ["Doc.md: anchor '## A' is in the registry but not in the file"]


def test_shape_reports_a_missing_file(root):
    rows = _rows("| `Gone.md` | j | o | `## A` | s |")
    assert living.check_shape(rows) == ["Gone.md: named in the registry but not on disk"]


def test_shape_reports_an_unpinned_row(root):
    rows = _rows("| `Doc.md` | j | o | `unpinned` | s |")
    assert "shape is unpinned" in living.check_shape(rows)[0]


def test_the_self_test_arms_can_fail():
    rows = living.parse_registry(living.REGISTRY.read_text(encoding="utf-8"))
    assert living.self_test(rows) == 0
