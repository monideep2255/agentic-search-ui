"""Prove the stable prefix is byte-identical before and after the speed fix.

Builds the prefix twice: once from the working tree's `core/graph.py`, once
from a copy of `src/` whose `core/graph.py` is the committed version at the
given revision (every other module identical), and prints both SHA-256
digests. `prompt-cache-discipline.md` asks for exactly this comparison.

Usage: python3 prefix_sha256.py <git revision>
"""
import os
import shutil
import subprocess
import sys
import tempfile

root = "<repo-root>"
rev = sys.argv[1]
with open(os.path.join(root, ".env")) as env_file:
    for line in env_file:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

snippet = (
    "import hashlib, sys; sys.path.insert(0, sys.argv[1]);"
    "from system_03_search_agent.core import graph as g;"
    "print(hashlib.sha256(g._STABLE_PREFIX.encode('utf-8')).hexdigest(), len(g._STABLE_PREFIX))"
)

def digest(src_dir: str) -> str:
    out = subprocess.run([sys.executable, "-c", snippet, src_dir], capture_output=True, text=True, check=True)
    return out.stdout.strip()

with tempfile.TemporaryDirectory() as tmp:
    before_src = os.path.join(tmp, "src")
    shutil.copytree(os.path.join(root, "src"), before_src)
    committed = subprocess.run(
        ["git", "-C", root, "show", f"{rev}:src/system_03_search_agent/core/graph.py"],
        capture_output=True, text=True, check=True,
    ).stdout
    with open(os.path.join(before_src, "system_03_search_agent", "core", "graph.py"), "w") as handle:
        handle.write(committed)
    before = digest(before_src)
after = digest(os.path.join(root, "src"))
print(f"before ({rev} graph.py): {before}")
print(f"after  (working tree):   {after}")
print("BYTE-IDENTICAL" if before.split()[0] == after.split()[0] else "DIFFERENT")
sys.exit(0 if before.split()[0] == after.split()[0] else 1)
