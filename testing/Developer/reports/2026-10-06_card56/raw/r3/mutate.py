"""Card 56 round 3: single-property mutants of the change, each run against
the new test file in a scratch copy of the branch, never in the worktree.

Usage: python mutate.py <scratch-copy-root>
The scratch copy holds `src/`, `tests/` and `pyproject.toml` from the branch.
Each mutant edits one line of the copy's graph.py, runs the test file, prints
which tests failed, then restores the file byte for byte.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
GRAPH = ROOT / "src/system_03_search_agent/core/graph.py"
TESTS = "tests/system_03_search_agent/core/test_think_sra_disease_fallback.py"

MUTANTS = {
    "M1 the piece is never skipped": (
        "skip_name_pieces = classification.record_type in breadth_plan.ORGANISM_RECORD_DBS",
        "skip_name_pieces = False",
    ),
    "M2 skipped on SRA questions only": (
        "skip_name_pieces = classification.record_type in breadth_plan.ORGANISM_RECORD_DBS",
        'skip_name_pieces = classification.record_type == "sra"',
    ),
    "M3 only the ASCII hyphen joins a name": (
        'return unicodedata.category(char) == "Pd" or char == "\\u2212"',
        'return char == "-"',
    ),
    "M4 every candidate is skipped on an SRA question": (
        "if skip_name_pieces and _only_a_piece_of_a_joined_name(query.text, candidate):",
        "if skip_name_pieces:",
    ),
    "M5 the skip ignores the record type": (
        "skip_name_pieces = classification.record_type in breadth_plan.ORGANISM_RECORD_DBS",
        "skip_name_pieces = True",
    ),
    "M6 the whole disease fallback is skipped on an SRA question": (
        (
            "            if skip_name_pieces and _only_a_piece_of_a_joined_name(query.text, candidate):\n"
            "                continue"
        ),
        "            if skip_name_pieces:\n                break",
    ),
    "M7 the retry lists the three hand-kept keys": (
        'f"using exactly these keys: {_THINK_RETRY_KEY_LIST}. "',
        '\'using exactly these keys: "query_class", "narrative", "entities". \'',
    ),
    "M8 the repair knows the three hand-kept keys": (
        "known_keys = set(_ThinkClassification.model_fields)",
        'known_keys = {"query_class", "narrative", "entities"}',
    ),
}


def main() -> None:
    original = GRAPH.read_text(encoding="utf-8")
    try:
        for name, (before, after) in MUTANTS.items():
            if original.count(before) != 1:
                print(f"{name}: anchor found {original.count(before)} times, not run")
                continue
            GRAPH.write_text(original.replace(before, after), encoding="utf-8")
            run = subprocess.run(
                [sys.executable, "-m", "pytest", TESTS, "-q", "-p", "no:cacheprovider", "-rf"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            failed = [
                line.split("::", 1)[1].split(" ")[0]
                for line in run.stdout.splitlines()
                if line.startswith("FAILED ")
            ]
            summary = run.stdout.strip().splitlines()[-1] if run.stdout.strip() else "no output"
            print(f"{name}: {summary}")
            for test in failed:
                print(f"    red: {test}")
    finally:
        GRAPH.write_text(original, encoding="utf-8")


if __name__ == "__main__":
    main()
