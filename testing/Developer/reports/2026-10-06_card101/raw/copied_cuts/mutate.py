"""Card 101 round 3: mutate each property, run the test file, record, restore.

Run from the worktree root with the project's Python on PATH:
    python testing/Developer/reports/2026-10-06_card101/raw/copied_cuts/mutate.py
Writes `mutations.txt` beside this file. The source is restored after every
mutation, and checked byte for byte at the end.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

SOURCE = Path("src/system_03_search_agent/synthesis/grounding.py")
TESTS = "tests/system_03_search_agent/synthesis/test_copied_cuts.py"

MUTATIONS = {
    "M1 code approves every copy again (is_whole_record_sentence always True)": (
        "    claim = _whole_form(claim_text)\n    if not claim:\n        return False\n",
        "    return True\n    claim = _whole_form(claim_text)\n",
    ),
    "M2 no copy is ever whole (is_whole_record_sentence always False)": (
        "    claim = _whole_form(claim_text)\n    if not claim:\n        return False\n",
        "    return False\n    claim = _whole_form(claim_text)\n",
    ),
    "M3 the check reads the clause alone, not the sentence up to it": (
        '    prefix = prefix.rstrip(" ,;:")\n',
        "    prefix = _clean_claim(segments[upto][0])\n",
    ),
    "M4 a collected cut is also kept on the first pass": (
        (
            "                    elif candidate_sink is not None:\n"
            "                        candidate_sink.append(copied)\n"
        ),
        (
            "                    elif candidate_sink is not None:\n"
            "                        candidate_sink.append(copied)\n"
            "                        strict_ok = True\n"
        ),
    ),
    "M5 a semicolon is not a sentence boundary": (
        '_WHOLE_SENTENCE_START = re.compile(r"[.;!?:]\\s+")',
        '_WHOLE_SENTENCE_START = re.compile(r"[.!?:]\\s+")',
    ),
    "M6 a wrapped value goes to the check too": (
        "                and not _wraps_record_value(claim_text, finding)\n",
        "",
    ),
}


def main() -> None:
    original = SOURCE.read_text()
    lines = []
    for name, (old, new) in MUTATIONS.items():
        assert original.count(old) == 1, f"{name}: anchor not found exactly once"
        SOURCE.write_text(original.replace(old, new))
        try:
            run = subprocess.run(
                ["python", "-m", "pytest", TESTS, "-q", "-p", "no:cacheprovider"],
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            SOURCE.write_text(original)
        failed = sorted(
            {line.split("::", 1)[1].split(" ")[0] for line in run.stdout.splitlines() if line.startswith("FAILED")}
        )
        summary = run.stdout.strip().splitlines()[-1] if run.stdout.strip() else "no output"
        lines.append(f"{name}\n  {summary}\n" + "".join(f"  red: {test}\n" for test in failed))
    assert SOURCE.read_text() == original, "source not restored"
    out = Path(__file__).with_name("mutations.txt")
    out.write_text("\n".join(lines))
    print(out.read_text())


if __name__ == "__main__":
    main()
