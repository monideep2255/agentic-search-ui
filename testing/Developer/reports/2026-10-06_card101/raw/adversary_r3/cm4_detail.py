"""Card 101 round 3 adversary: why cm4 loses sentences beyond its two cuts
when the check holds the cuts. No model call.
Usage: python cm4_detail.py <develop-src> <branch-src> <trace.jsonl>
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEV, BR, TRACE = sys.argv[1:4]
sys.argv = [sys.argv[0], DEV, BR, "--counts"]
src = (HERE / "replay_cost.py").read_text().split("dev = load(DEV)")[0]
ns = {"__name__": "helpers"}
exec(compile(src, "h", "exec"), ns)  # noqa: S102
dev = ns["load"](DEV)
br = ns["load"](BR)
rows = [json.loads(x) for x in Path(TRACE).read_text().splitlines() if x.strip()]
rows = [r for r in rows if isinstance(r, dict) and "tag" in r]
frows = next(r["data"] for r in rows if r["tag"] == "FINDINGS")
g = [r for r in rows if r["tag"] == "GROUNDING"][1]
narr = g["data"]["narrative"]
q = ns["question_for"](Path(TRACE).stem)
quotes = ns["rebuild_quotes"](narr, rows, br[0])
_, dsink = ns["run"](*dev, narr, frows, q, quotes, None)
dk = frozenset(c.key for c in dsink)
d, _ = ns["run"](*dev, narr, frows, q, quotes, dk)
w, _ = ns["run"](*br, narr, frows, q, quotes, dk)
print("NARRATIVE SENTENCES:")
for s in br[0]._split_sentences(narr):
    print("  ", s[:260])
print("\nDEVELOP SHOWS:")
for s in ns["_split"](d.narrative):
    print("  ", s[:200])
print("\nBRANCH, CUTS HELD, SHOWS:")
for s in ns["_split"](w.narrative):
    print("  ", s[:200])
