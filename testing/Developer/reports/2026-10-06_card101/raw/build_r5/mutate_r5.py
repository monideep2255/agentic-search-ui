"""Card 101 round 5: mutations of each change, on a scratch copy of the tree.

Usage: python mutate_r5.py <scratch-tree>

<scratch-tree> is a copy of the repository's `src`, `tests` and
`pyproject.toml`, never a worktree. Each mutation is applied, the round 5
test files are run, and the file is restored and compared byte for byte.
Prints, per mutation, the count of failed tests and their names.
"""

import subprocess
import sys
from pathlib import Path

TREE = Path(sys.argv[1])
GROUNDING = "src/system_03_search_agent/synthesis/grounding.py"
CHECK = "src/system_03_search_agent/synthesis/sentence_check.py"
GRAPH = "src/system_03_search_agent/core/graph.py"
TESTS = [
    "tests/system_03_search_agent/synthesis/test_copied_cuts.py",
    "tests/system_03_search_agent/synthesis/test_sentence_check.py",
]

MUTATIONS = {
    "R1 no whole-sentence drop for a held copy": (
        GROUNDING,
        "        if held_for_check:\n            dropped_from_middle = True\n",
        "",
    ),
    "R2 no length filter, every item sent": (
        CHECK,
        "readable = [candidate for candidate in candidates if _read_whole(candidate)]",
        "readable = list(candidates)",
    ),
    "R3 a cut with no run falls back to the cut as its quote": (
        GROUNDING,
        "    return record_sentence_run(claim_text, finding.field_value)\n",
        "    return widen_to_record_sentences(claim_text, finding.field_value)\n",
    ),
    "R4 listing pieces compared with their separators kept": (
        GROUNDING,
        "        _whole_form(_without_glue(piece)) for piece in split_into_sentences(finding.field_value)",
        "        _whole_form(piece) for piece in split_into_sentences(finding.field_value)",
    ),
    "R5 no catch around the guard-tier call": (
        GRAPH,
        "        except Exception as exc:\n            # Card 101, round 5 (J4-101-08)",
        "        except ZeroDivisionError as exc:\n            # Card 101, round 5 (J4-101-08)",
    ),
    "R6 the length filter reads the sentence only": (
        CHECK,
        "    return len(candidate.sentence) <= MAX_SENTENCE_CHARS and all(",
        "    return len(candidate.sentence) <= MAX_SENTENCE_CHARS or all(",
    ),
}


def run_tests() -> list[str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *TESTS],
        cwd=TREE,
        capture_output=True,
        text=True,
        check=False,
    )
    return [line.split(" - ")[0] for line in proc.stdout.splitlines() if line.startswith("FAILED")]


baseline = run_tests()
print(f"baseline: {len(baseline)} failed")
for name, (path, old, new) in MUTATIONS.items():
    target = TREE / path
    original = target.read_bytes()
    text = original.decode()
    if text.count(old) != 1:
        print(f"{name}: SKIPPED, anchor found {text.count(old)} times")
        continue
    target.write_text(text.replace(old, new))
    try:
        failed = run_tests()
    finally:
        target.write_bytes(original)
    assert target.read_bytes() == original
    print(f"{name}: {len(failed)} failed")
    for line in failed:
        print(f"    {line.replace('FAILED ', '')}")
