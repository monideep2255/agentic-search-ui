"""Card 101 round 3 adversary: the code-built listing (structured fallback and
findings tail) over every recorded answer's findings, grounded with no check
(as `core.graph` calls it), on develop and on the branch. No model call.
Usage: python fallback_replay.py <develop-src> <branch-src> <trace-folder>...
"""
import importlib
import json
import re
import sys
from pathlib import Path


def load(src):
    for name in list(sys.modules):
        if name.startswith("system_03_search_agent"):
            del sys.modules[name]
    sys.path.insert(0, src)
    gr = importlib.import_module("system_03_search_agent.synthesis.grounding")
    fi = importlib.import_module("system_03_search_agent.synthesis.findings")
    sys.path.remove(src)
    return gr, fi


def strip(text):
    return [s.strip() for s in re.split(r"(?<=[.;?!])\s+", re.sub(r"\s*\[\d{1,3}\]", "", text or "").strip()) if s.strip()]


trees = {"develop": load(sys.argv[1]), "branch": load(sys.argv[2])}
seen = set()
tot = {"answers": 0, "develop_rows": 0, "branch_rows": 0, "answers_with_loss": 0}
for folder in sys.argv[3:]:
    for path in sorted(Path(folder).glob("*.jsonl")):
        frows = None
        for line in path.read_text().splitlines():
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001, S112
                continue
            if isinstance(r, dict) and r.get("tag") == "FINDINGS":
                frows = r["data"]
                break
        if not frows:
            continue
        sig = json.dumps(frows, sort_keys=True)
        if sig in seen:
            continue
        seen.add(sig)
        out = {}
        for name, (gr, fi) in trees.items():
            fs = [fi.SynthFinding(ref_index=int(f["ref"]), citation_id=f"c-{f['ref']}", layer="", tool=f.get("tool", ""),
                                  field=f["field"], field_value=f["text"] or "", source_url=f.get("url", ""))
                  for f in frows]
            narrative = fi.build_structured_fallback_narrative(fs)
            res = gr.run_grounding_pass(narrative, fs, core_ask_required=True, question="")
            out[name] = strip(res.narrative)
        lost = [s for s in out["develop"] if s not in out["branch"]]
        tot["answers"] += 1
        tot["develop_rows"] += len(out["develop"])
        tot["branch_rows"] += len(out["branch"])
        tot["answers_with_loss"] += bool(lost)
        if lost:
            print(f"{path.parent.name}/{path.stem}: develop {len(out['develop'])} rows, branch {len(out['branch'])}")
            for s in lost:
                print("   LOST:", s[:160])
print(json.dumps(tot))
