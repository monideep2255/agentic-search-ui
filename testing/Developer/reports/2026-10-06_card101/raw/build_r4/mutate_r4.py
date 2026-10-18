"""Card 101 round 4: apply each mutation to a scratch copy of the tree, run the
round's tests, restore the file and check it byte for byte.

Usage: python mutate_r4.py <scratch-tree> ; the tree holds src/, tests/,
pyproject.toml, copied from the worktree. Never touches the worktree.
"""
import subprocess
import sys
from pathlib import Path

TREE = Path(sys.argv[1])
TARGET = TREE / "src/system_03_search_agent/synthesis/grounding.py"
TESTS = [
    "tests/system_03_search_agent/synthesis/test_copied_cuts.py",
    "tests/system_03_search_agent/synthesis/test_pubmed_abstract_grounding.py",
    "tests/system_03_search_agent/synthesis/test_quote_anchored_synthesis.py",
]
BOUNDARY = "return [part for part in _RECORD_SENTENCE_BOUNDARY.split(value) if part.strip()]"

MUTATIONS = [
    ("M1 a colon starts a record sentence", BOUNDARY,
     "return [part for part in re.split(r\"(?<=[.!?])\\s+(?=[A-Z\\\"(])|(?<=:)\\s+\", value) if part.strip()]"),
    ("M2 a semicolon ends a record sentence", BOUNDARY,
     "return [part for part in re.split(r\"(?<=[.!?])\\s+(?=[A-Z\\\"(])|(?<=;)\\s+\", value) if part.strip()]"),
    ("M3 no capital needed after a full stop", BOUNDARY,
     "return [part for part in re.split(r\"(?<=[.!?])\\s+\", value) if part.strip()]"),
    ("M4 a record question counts as a statement",
     "        if _ends_as_question(sentence) and not asks:\n            continue\n", ""),
    ("M5 quote marks and brackets stripped from a record sentence",
     BOUNDARY + "\n",
     ("return [part.strip(\"\\\"“”()\") for part in re.split("
      "r\"(?:(?<=[.!?])|(?<=[.!?][\\\"”)]))\\s+(?=[A-Z\\\"“(])\", value) if part.strip()]\n")),
    ("M6 the listing flag ignored",
     "or (code_built_listing and _is_code_built_row(text, finding))", "or False"),
    ("M7 only the claim after its connective is tested",
     "forms = {_whole_form(_without_glue(claim_text)), _whole_form(_clean_claim(claim_text))}",
     "forms = {_whole_form(_clean_claim(claim_text))}"),
    ("M7b the listing row tested after its connective",
     "segment = _whole_form(_without_glue(segment_text))",
     "segment = _whole_form(_clean_claim(segment_text))"),
    ("M7c both tested after the connective",
     [("forms = {_whole_form(_without_glue(claim_text)), _whole_form(_clean_claim(claim_text))}",
       "forms = {_whole_form(_clean_claim(claim_text))}"),
      ("segment = _whole_form(_without_glue(segment_text))",
       "segment = _whole_form(_clean_claim(segment_text))")], None),
    ("M8 clauses after a cut not read joined", "if is_cut or cut_in_sentence:", "if is_cut:"),
    ("M9 the joined item keeps only the last record's text",
     "quotes = tuple(dict.fromkeys(spans))", "quotes = tuple(dict.fromkeys(spans[-1:]))"),
    ("M10 held clauses not counted by the middle-strip rule",
     "or (index not in held_for_check and later in held_for_check)", "or False"),
    ("M11 a verdict-opening cut not held by code",
     "held_by_code = is_cut and _VERDICT_OPENER.match(claim_text) is not None", "held_by_code = False"),
    ("M12 the whole-sentence match ignores case",
     "and claim[1:] == record[1:]", "and claim[1:].lower() == record[1:].lower()"),
]

original = TARGET.read_bytes()
for name, old, new in MUTATIONS:
    text = original.decode()
    for one_old, one_new in (old if new is None else [(old, new)]):
        assert text.count(one_old) >= 1, name
        text = text.replace(one_old, one_new, 1)
    TARGET.write_text(text)
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *TESTS],
        cwd=TREE, capture_output=True, text=True, check=False,
    )
    TARGET.write_bytes(original)
    assert TARGET.read_bytes() == original
    failed = sorted({line.split(" - ")[0].split("::", 1)[1] for line in run.stdout.splitlines()
                     if line.startswith("FAILED")})
    summary = run.stdout.strip().splitlines()[-1] if run.stdout.strip() else run.stderr[-300:]
    print(f"{name}: {len(failed)} red | {summary}")
    for test in failed:
        print(f"    {test}")
print("restored byte for byte:", TARGET.read_bytes() == original)
