import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = "<repo-root>"
path = ROOT + "/src/system_03_search_agent/core/graph.py"
old = "    if fallback_sentences:\n        # Product-owner direction 2026-09-14"
new = "    if fallback_sentences and audience_depth != 'researcher':\n        for sentence in fallback_sentences:\n            sentence_token(sentence)\n    elif fallback_sentences:\n        # Product-owner direction 2026-09-14"
original = Path(path).read_bytes()
text = original.decode()
assert text.count(old) == 1
Path(path).write_text(text.replace(old, new))
try:
    run = subprocess.run([sys.executable, "-m", "pytest", ROOT + "/tests/system_03_search_agent/core/test_write_answer_structure.py::test_the_structured_fallback_lists_records_in_every_depth", "-q", "-p", "no:cacheprovider"], capture_output=True, text=True, cwd=ROOT, check=False)
finally:
    Path(path).write_bytes(original)
print("M10 fallback rendered as run-on claims outside Researcher:", "RED (arm caught it)" if run.returncode else "GREEN", "; restored:", hashlib.sha256(Path(path).read_bytes()).hexdigest() == hashlib.sha256(original).hexdigest())
