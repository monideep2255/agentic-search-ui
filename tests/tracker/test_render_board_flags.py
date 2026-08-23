"""Does the board tell open findings apart from closed ones?

`tracker/BOARD.md`'s flags table is a LEDGER, not a queue: a closed finding
keeps its row so the trail survives, which is why the table's length only ever
grows. `render_board.py` reported one number for the whole table, and on
2026-08-23 the product owner read that number, 83, as a backlog of 83
outstanding problems. Twenty-six of them were already closed.

`is_closed_flag` is the classifier that split the reporting. This file exists
because that classifier is now load-bearing for a number a person makes
decisions from, and it had no test.

THE ERROR DIRECTION THAT MATTERS IS NOT SYMMETRIC. Classifying a closed row as
open overstates the backlog, which is annoying and self-correcting: someone
reads the row and sees it is closed. Classifying an OPEN row as closed hides
real work behind a number that says it is done, and nothing prompts anyone to
look again. So the substring traps below are the point of this file, not
padding: both are real shapes that appear in live rows, and a `search`-based
implementation passes every other case here while failing exactly those two.

This is the first test in the repository for `tracker/`. The tracker scripts
are deliberately stdlib-only and portable (see CLAUDE.md's portability audit),
so this imports the module by path rather than assuming a package layout.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKER_DIR = REPO_ROOT / "tracker"


def _load_render_board():
    """Import `tracker/render_board.py` by path.

    `tracker/` is not a package and the script is meant to run standalone, so
    the directory goes on `sys.path` first: the module resolves its own
    `board.css` relative to its file, and `@dataclass` needs the module
    registered in `sys.modules` before the class bodies execute.
    """
    if str(TRACKER_DIR) not in sys.path:
        sys.path.insert(0, str(TRACKER_DIR))
    spec = importlib.util.spec_from_file_location(
        "render_board", TRACKER_DIR / "render_board.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["render_board"] = module
    spec.loader.exec_module(module)
    return module


render_board = _load_render_board()


#: Every string here is the SHAPE of a real third-column value on the live
#: board, not an invented one. The two marked as traps are the reason this
#: file exists.
CLOSED_CASES = [
    ("CLOSED 2026-08-15 by build phase 4.10, which built the anonymous run path", "a dated closure naming the phase that did it"),
    ("Closed", "the terse form, which several rows actually use"),
    ("RESOLVED (assignment), 2026-08-10", "the resolved-by-assignment form"),
    ("closed 2026-08-23 by build phase 4.7", "lowercase, since the board is hand-written"),
]

OPEN_CASES = [
    ("Build phase 6.1's hardening pass, re-homed 2026-08-15", "a live owner naming a phase"),
    ("Whenever `_stream_sigint_scope` is next touched", "a conditional note, the most common open shape"),
    ("Whichever phase next changes the event contract", "another conditional"),
    ("`fix/a01-injection-guardrail`, a dedicated branch opening when 4.7 merges", "a blocker branch"),
    ("A product-owner decision, then whichever phase adopts a router", "a pending decision"),
    ("Not closed until build phase 6.0 revisits it", "TRAP: contains the word closed, and is open"),
    ("Owned by 4.12. F-4.8-P-01 was CLOSED earlier by 4.10", "TRAP: describes ANOTHER row's closure, and is open"),
]


@pytest.mark.parametrize(
    ("disposition", "why"), CLOSED_CASES, ids=[c[1][:38] for c in CLOSED_CASES]
)
def test_a_closed_disposition_is_recognised(disposition: str, why: str) -> None:
    assert render_board.is_closed_flag(disposition) is True, (
        f"{why}: {disposition!r} should classify as closed"
    )


@pytest.mark.parametrize(
    ("disposition", "why"), OPEN_CASES, ids=[c[1][:38] for c in OPEN_CASES]
)
def test_an_open_disposition_is_not_mistaken_for_closed(
    disposition: str, why: str
) -> None:
    assert render_board.is_closed_flag(disposition) is False, (
        f"{why}: {disposition!r} must NOT classify as closed. Hiding an open "
        "finding behind a done count is the error direction that loses work, "
        "because nothing prompts anyone to look at the row again"
    )


def test_the_live_board_splits_into_two_nonzero_groups() -> None:
    """The real board, not a fixture, and both groups must be populated.

    POPULATE-CHECK, and it is the reason this arm is not just a count
    assertion. A classifier that returned False for everything would leave
    every parametrized open case above passing and would silently restore the
    single misleading number this whole change removed. Asserting both groups
    are non-empty is what makes that mutation visible.
    """
    board = (TRACKER_DIR / "BOARD.md").read_text(encoding="utf-8")
    data = render_board.parse_board(board)
    rows = data["open_flags"]

    assert rows, "the board parsed to zero flag rows, so nothing below is graded"

    closed = [row for row in rows if row["closed"]]
    still_open = [row for row in rows if not row["closed"]]

    assert closed, (
        "no row classified as closed. The board is a ledger and keeps closed "
        "findings, so an empty closed group means the classifier stopped working"
    )
    assert still_open, (
        "every row classified as closed, which would report a backlog of zero "
        "while real findings sit open"
    )
    assert len(closed) + len(still_open) == len(rows)


def test_reconciliation_still_counts_every_row_regardless_of_disposition() -> None:
    """The split is for REPORTING only; the invariant is unchanged.

    Every flag named on a phase row must have exactly one row in the table
    whether it is open or closed, or the audit trail breaks. This pins that the
    reporting change did not quietly narrow the reconciliation to open rows,
    which would let a closed flag be dropped from the table with nothing
    complaining.
    """
    board = (TRACKER_DIR / "BOARD.md").read_text(encoding="utf-8")
    data = render_board.parse_board(board)
    phase_flag_mentions = sum(len(phase.flags) for phase in data["phases"])

    assert phase_flag_mentions == len(data["open_flags"]), (
        "phase flag cells and flags-table rows must reconcile on the TOTAL, "
        "open and closed alike"
    )
