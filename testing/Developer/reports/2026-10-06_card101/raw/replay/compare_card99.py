"""Card 101 replay: each candidate's verdict in card 99's two pair runs
against this folder's two pair runs (the shipped check with word forms),
with the vetoing pairs of each. No model call. Usage, from the repository
root: python testing/Developer/reports/2026-10-06_card101/raw/replay/compare_card99.py
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parents[2] / "2026-10-06_card99/raw/live_ab"


def approves(a: dict) -> bool:
    return a["choice"] == "no" and a["p_no"] is not None and a["p_yes"] is not None and a["p_no"] > a["p_yes"]


def load(folder: Path, rep: int) -> dict:
    """candidate id -> (item approved, final approved, [(phrase, p_no) of vetoing pairs], [all phrases])"""
    out = {}
    for line in (folder / f"run_pair_{rep}.jsonl").read_text().splitlines():
        r = json.loads(line)
        item = next(c for c in r["calls"] if c["kind"] == "item")
        item_ok = {r["ids"][int(k.split("_")[1]) - 1] for k, a in item["answers"].items() if approves(a)}
        vetoes: dict = {}
        phrases: dict = {}
        for k, (cid, phrase, _q) in r["pairs"].items():
            phrases.setdefault(cid, []).append(phrase)
        for c in r["calls"]:
            if c["kind"] != "pair":
                continue
            for k, a in c["answers"].items():
                if not approves(a):
                    cid, phrase, _q = r["pairs"][k]
                    vetoes.setdefault(cid, []).append((phrase, round(a["p_no"] or 0, 2)))
        for cid in r["ids"]:
            out[cid] = (cid in item_ok, cid in r["approved"], vetoes.get(cid, []), phrases.get(cid, []))
    return out


def main() -> None:
    old = [load(OLD, 1), load(OLD, 2)]
    new = [load(HERE, 1), load(HERE, 2)]
    print("candidates whose final verdict differs between card 99 and card 101 in any run")
    for cid in sorted(old[0]):
        o = [x[cid][1] for x in old]
        n = [x[cid][1] for x in new]
        if o != n or sorted(old[0][cid][3]) != sorted(new[0][cid][3]):
            if o == n and not any(o) and not any(x[cid][0] for x in old + new):
                continue
            print(f"{cid}: card99 {o} card101 {n} | item99 {[x[cid][0] for x in old]} item101 {[x[cid][0] for x in new]}")
            print(f"   card99 vetoes {old[0][cid][2]} | {old[1][cid][2]}")
            print(f"   card101 vetoes {new[0][cid][2]} | {new[1][cid][2]}")
            print(f"   pairs removed {sorted(set(old[0][cid][3]) - set(new[0][cid][3]))} added {sorted(set(new[0][cid][3]) - set(old[0][cid][3]))}")
    for name, runs in (("card99", old), ("card101", new)):
        print(name, "approved per run", [sum(v[1] for v in r.values()) for r in runs],
              "item-approved then vetoed", [sum(v[0] and not v[1] for v in r.values()) for r in runs])


if __name__ == "__main__":
    main()
