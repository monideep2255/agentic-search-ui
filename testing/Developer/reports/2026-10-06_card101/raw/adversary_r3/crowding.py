"""Card 101 round 3 adversary: do the branch's new copied-cut items crowd
develop's own check items out (MAX_CANDIDATES, JEV_STATE_MAX_CHARS,
MAX_PAIR_CALLS)? No model call.

For each recorded GROUNDING row (writer quotes rebuilt as in replay_cost.py):
develop's candidate list and the branch's, each packed by the shipped
`build_jev_state` and `build_pair_calls` of its own tree. A develop item is
askable when it is sent and none of its pairs was left unasked. Prints rows
where a develop item askable on develop is not askable on the branch, and
the sizes of the checks.
Usage: python crowding.py <develop-src> <branch-src> <trace-folder>...
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
DEV, BR = sys.argv[1], sys.argv[2]
FOLDERS = sys.argv[3:]
sys.argv = [sys.argv[0], DEV, BR, "--counts"]  # replay_cost reads argv at import
import importlib

src = (HERE / "replay_cost.py").read_text()
helpers = src.split("dev = load(DEV)")[0]
ns = {"__name__": "helpers"}
exec(compile(helpers, "replay_cost_helpers", "exec"), ns)  # noqa: S102


def load_all(path):
    for name in list(sys.modules):
        if name.startswith("system_03_search_agent"):
            del sys.modules[name]
    sys.path.insert(0, path)
    gr = importlib.import_module("system_03_search_agent.synthesis.grounding")
    fi = importlib.import_module("system_03_search_agent.synthesis.findings")
    scm = importlib.import_module("system_03_search_agent.synthesis.sentence_check")
    sys.path.remove(path)
    return gr, fi, scm


dev = load_all(DEV)
br = load_all(BR)


def askable(cands, scm):
    _state, sent = scm.build_jev_state(cands)
    calls, not_asked = scm.build_pair_calls(sent)
    ok = {c.key for i, c in enumerate(sent, start=1) if i not in not_asked}
    return ok, len(cands), len(sent), len(calls), len(not_asked), len(_state)


tot = {"rows": 0, "rows_crowded": 0, "dev_items_crowded": 0, "max_branch_items": 0, "max_branch_state": 0,
       "rows_branch_unsent": 0, "rows_dev_unsent": 0}
for folder in FOLDERS:
    for path in sorted(Path(folder).glob("*.jsonl")):
        rows = []
        for line in path.read_text().splitlines():
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001, S112
                continue
            if isinstance(r, dict) and "tag" in r:
                rows.append(r)
        frows = next((r["data"] for r in rows if r["tag"] == "FINDINGS"), None)
        if not frows:
            continue
        q = ns["question_for"](path.stem)
        for gi, r in enumerate(x for x in rows if x["tag"] == "GROUNDING"):
            narrative = r["data"]["narrative"]
            quotes = ns["rebuild_quotes"](narrative, rows, br[0])
            _, dsink = ns["run"](dev[0], dev[1], narrative, frows, q, quotes, None)
            _, bsink = ns["run"](br[0], br[1], narrative, frows, q, quotes, None)
            dok, dn, dsent, dcalls, dna, dchars = askable(dsink, dev[2])
            bok, bn, bsent, bcalls, bna, bchars = askable(bsink, br[2])
            crowded = {k for k in dok if k not in bok}
            tot["rows"] += 1
            tot["rows_crowded"] += bool(crowded)
            tot["dev_items_crowded"] += len(crowded)
            tot["max_branch_items"] = max(tot["max_branch_items"], bn)
            tot["max_branch_state"] = max(tot["max_branch_state"], bchars)
            tot["rows_branch_unsent"] += bool(bn - bsent or bna)
            tot["rows_dev_unsent"] += bool(dn - dsent or dna)
            if crowded or bn != dn:
                print(f"{path.parent.name}/{path.stem} g{gi}: develop items {dn} sent {dsent} pair calls {dcalls} unasked {dna} chars {dchars}"
                      f" | branch items {bn} sent {bsent} pair calls {bcalls} unasked {bna} chars {bchars} | develop items crowded out {len(crowded)}")
print(json.dumps(tot))
