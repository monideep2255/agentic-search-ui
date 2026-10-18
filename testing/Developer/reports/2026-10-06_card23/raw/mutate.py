"""Card 23: apply each mutation, run the card 23 tests, restore the file.

Run from the worktree root. PYTHON names the interpreter (default: this one).
Each mutation breaks one property; the arm guarding it must turn red.
"""

import os
import subprocess
import sys
from pathlib import Path

PY = os.environ.get("PYTHON", sys.executable)
G = "src/system_03_search_agent/core/graph.py"
L = "src/system_03_search_agent/synthesis/answer_layout.py"
WIRE = '''            if source_note is not None:
                paragraph_break()
                tokens.append(TokenPayload(text=source_note, marker_ids=[], kind="note"))
'''
HDR = '''                tokens.append(
                    TokenPayload(text="", marker_ids=[], kind="table_header", cells=columns)
                )
'''
NOTES = '''    for note in notes:
        paragraph_break()
        tokens.append(TokenPayload(text=note[:1000], marker_ids=[], kind="note"))
    return tokens
'''
mutations = {
    "M1 wiring removed": [(G, WIRE, "")],
    "M2 note above the rows": [
        (G, WIRE, ""),
        (
            G,
            HDR,
            HDR
            + '''                if variant_to_disease_source_note(entity_type, mapped):
                    tokens.append(TokenPayload(text=variant_to_disease_source_note(entity_type, mapped), marker_ids=[], kind="note"))
''',
        ),
    ],
    "M3 helper ignores entity_type": [
        (L, 'if entity_type != "SequenceVariant" or not mapped:', "if not mapped:")
    ],
    "M4 helper ignores mapped": [
        (L, 'if entity_type != "SequenceVariant" or not mapped:', 'if entity_type != "SequenceVariant":')
    ],
    "M5 note made answer-wide": [
        (G, WIRE, ""),
        (
            G,
            NOTES,
            '''    if any(f.entity_type == "SequenceVariant" for f in synth_findings):
        notes = [*notes, variant_to_disease_source_note("SequenceVariant", True)]
'''
            + NOTES,
        ),
    ],
    "M6 wording names LitVar2": [
        (
            L,
            '''    "Variant-to-disease links are ClinVar assertions, each cited to its "''',
            '''    "Variant-to-disease links come from LitVar2, each cited to its "''',
        )
    ],
}
tests = [
    "tests/system_03_search_agent/core/test_write_answer_structure.py",
    "tests/system_03_search_agent/synthesis/test_answer_layout.py",
    "-k",
    "card23 or variant_to_disease",
]
for name, edits in mutations.items():
    backups: dict[str, str] = {}
    for path, old, new in edits:
        if path not in backups:
            backups[path] = Path(path).read_text()
        text = Path(path).read_text()
        assert old in text, (name, old[:60])
        Path(path).write_text(text.replace(old, new, 1))
    try:
        out = subprocess.run(
            [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", *tests],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        failed = sorted(
            {line.split(" ")[1].split("::")[-1] for line in out.splitlines() if line.startswith("FAILED")}
        )
        print(f"{name}: {out.strip().splitlines()[-1]}")
        for test in failed:
            print("   red:", test)
    finally:
        for path, text in backups.items():
            Path(path).write_text(text)
