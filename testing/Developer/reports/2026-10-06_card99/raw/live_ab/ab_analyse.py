"""Card 99 A/B analysis: what the person would see per answer, item question
alone versus item question plus the pair check, two runs of each arm.

Reads run_<arm>_<rep>.jsonl (from ab_run.py) and the live traces. Usage:
    REPO_ROOT=<repo-root> python ab_analyse.py > analysis.txt
Writes analysis.json beside this script for the report.

What "shown" means here: each live answer showed one draft (the first draft
or its repair). The draft shown is found by matching the screen's prose to
each draft's grounded sentences. Its sentences are of two kinds:
- passed by code alone (copied words): shown in every arm, unchanged;
- reworded candidates: shown when the arm approves them. A candidate the live
  check approved that still did not reach the screen is counted as never
  shown (something downstream dropped it); every other candidate is counted
  as shown when approved.
Assumption: the same draft is shown in every arm. Where an arm could have
changed which draft the code keeps, the answer is flagged.
"""
from __future__ import annotations

import json
import os
import re
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ["REPO_ROOT"])
RAW = ROOT / "testing/Developer/reports/2026-10-05_wave3/sentence_check_raw"
RUNS = [("item", 1), ("item", 2), ("pair", 1), ("pair", 2)]
DEPTH = {"gp": "plain", "md": "plain", "cp": "plain", "cm": "plain", "gr": "researcher", "cr": "researcher"}


def norm(text: str) -> str:
    text = re.sub(r"\[[0-9#,\s]+\]", " ", text)
    return " ".join(re.sub(r"[()\[\]{}.,;:]", " ", text.lower()).split())


def approves(a: dict) -> bool:
    return a["choice"] == "no" and a["p_no"] is not None and a["p_yes"] is not None and a["p_no"] > a["p_yes"]


def load_live() -> dict:
    """Per answer: its checks (items, live approvals), its drafts (each a
    grounding pass that collected candidates, the check it fed, and its
    final grounded sentences: after the check when anything was approved,
    else before it), and the prose on screen."""
    answers = {}
    files = sorted(RAW.glob("*.jsonl")) + sorted((RAW / "develop_control").glob("*.jsonl"))
    for path in files:
        label = path.stem
        rows = [json.loads(x) for x in path.read_text().splitlines()]
        checks, drafts = [], []
        for r in rows:
            d = r["data"]
            if r["tag"] == "GROUNDING" and d["candidates_collected"] is not None:
                drafts.append({"pre": d["claims"], "kept": norm(" ".join(d["kept_sentences"])), "check": None,
                               "post": None})
            elif r["tag"] == "CHECK_IN":
                checks.append({"items": d["items"]})
                drafts[-1]["check"] = len(checks)
            elif r["tag"] == "CHECK_OUT":
                checks[-1]["approved_norm"] = {norm(x) for x in d["approved_sentences"]}
            elif r["tag"] == "GROUNDING" and d["verified_syntheses"] and drafts and drafts[-1]["post"] is None:
                drafts[-1]["post"] = d["claims"]
                drafts[-1]["kept"] = norm(" ".join(d["kept_sentences"]))
        for dr in drafts:
            dr["final"] = dr["post"] if dr["post"] is not None else dr["pre"]
        tokens = [r["data"] for r in rows if r["tag"] == "TOKEN"]
        prose = [t[len("claim: "):] for t in tokens if t.startswith("claim: ")
                 and not re.match(r"claim: (Found|I found) \d", t)]
        done = next((r["data"] for r in rows if r["tag"] in ("DONE", "ERROR")), {})
        answers[label] = {"checks": checks, "drafts": [x for x in drafts if x["check"]], "prose": prose,
                          "done": done}
    return answers


def main() -> None:
    live = load_live()
    runs = {}
    for arm, rep in RUNS:
        rows = [json.loads(x) for x in (HERE / f"run_{arm}_{rep}.jsonl").read_text().splitlines()]
        runs[(arm, rep)] = {(r["label"], r["check"]): r for r in rows}
    failed = [json.loads(x) for x in (HERE / "failed_pair_1.jsonl").read_text().splitlines()] \
        if (HERE / "failed_pair_1.jsonl").exists() else []

    per_answer = []
    flags = []
    for label, ans in live.items():
        if not ans["checks"]:
            per_answer.append({"label": label, "depth": DEPTH[label[:2]], "no_check": True,
                               "outcome": ans["done"].get("trust_outcome")})
            continue
        # The shown draft: the draft whose final grounded sentences hold the
        # most of the screen's prose. With no prose on screen (the record
        # list only), the last draft is taken and the answer is flagged.
        scores = [(sum(1 for p in ans["prose"] if norm(p)[:60] in dr["kept"]), k)
                  for k, dr in enumerate(ans["drafts"])]
        best = max(scores)[0]
        shown_k = max(k for sc_, k in scores if sc_ == best)
        shown_n = ans["drafts"][shown_k]["check"]
        if best == 0 and ans["prose"] and ans["drafts"][shown_k]["pre"] == 0:
            flags.append((label, "-", 0, "screen prose matched no draft"))
        if not ans["prose"]:
            flags.append((label, "-", 0, "no prose on screen live; last draft assumed"))
        c = ans["checks"][shown_n - 1]
        ids = [f"{label}c{shown_n}i{i}" for i in range(1, len(c["items"]) + 1)]
        sent_norm = {i: norm(it["sentence"]) for i, it in zip(ids, c["items"], strict=True)}
        live_ok = {i for i in ids if sent_norm[i] in c["approved_norm"]}

        def on_screen(i: str) -> bool:
            return any(sent_norm[i][:60] in norm(p) for p in ans["prose"])  # noqa: B023 - called inside the same loop pass
        live_ok_shown = {i for i in live_ok if on_screen(i)}
        live_ok_dropped = live_ok - live_ok_shown
        code_only = [p for p in ans["prose"] if not any(sent_norm[i][:60] in norm(p) for i in live_ok_shown)]
        showable = set(ids) - live_ok_dropped
        row = {"label": label, "depth": DEPTH[label[:2]], "shown_check": shown_n, "n_checks": len(ans["checks"]),
               "match_score": best, "live_prose": len(ans["prose"]), "code_only": len(code_only),
               "live_model_shown": len(live_ok_shown), "live_ok_not_shown": sorted(live_ok_dropped),
               "candidates": len(ids), "outcome": ans["done"].get("trust_outcome"), "showable": sorted(showable)}
        for arm, rep in RUNS:
            r = runs[(arm, rep)][(label, shown_n)]
            ok = set(r["approved"]) & showable
            row[f"{arm}{rep}"] = len(code_only) + len(ok)
            row[f"{arm}{rep}_model"] = len(ok)
            # Model B, "the larger draft is shown": the code keeps a repair
            # that shows more sentences on the same records (card 88), so an
            # arm that empties one draft may show the other. Each other draft
            # counts its code-only sentences plus this arm's approvals of its
            # candidates, less any the live run approved that did not ground
            # (found by matching its grounded text). Ties keep the live draft.
            best_b, best_from = row[f"{arm}{rep}"], f"c{shown_n}"
            for k, dr in enumerate(ans["drafts"]):
                if k == shown_k:
                    continue
                oc = ans["checks"][dr["check"] - 1]
                oids = [f"{label}c{dr['check']}i{i}" for i in range(1, len(oc["items"]) + 1)]
                o_norm = {i: norm(it["sentence"]) for i, it in zip(oids, oc["items"], strict=True)}
                o_live_ok = {i for i in oids if o_norm[i] in oc["approved_norm"]}
                o_drop = {i for i in o_live_ok if dr["post"] is None or o_norm[i][:60] not in dr["kept"]}
                o_ok = set(runs[(arm, rep)][(label, dr["check"])]["approved"]) - o_drop
                other_arm = dr["pre"] + len(o_ok)
                if other_arm > best_b:
                    best_b, best_from = other_arm, f"c{dr['check']}"
            row[f"{arm}{rep}_B"] = best_b
            if best_from != f"c{shown_n}":
                flags.append((label, arm, rep, (f"model B shows draft {best_from} ({best_b}) over the live draft "
                              f"c{shown_n} ({row[f'{arm}{rep}']})")))
        per_answer.append(row)

    # Pair-run attributions over all 56 checks.
    dropped = []
    not_asked_total = 0
    item_in_pair = {}
    for rep in (1, 2):
        for key, r in runs[("pair", rep)].items():
            not_asked_total += len(r["not_asked"])
            item_call = next(x for x in r["calls"] if x["kind"] == "item")
            item_ok = {r["ids"][int(k.split("_")[1]) - 1] for k, a in item_call["answers"].items() if approves(a)}
            item_in_pair[(rep, key)] = item_ok
            vetoes = {}
            for call in r["calls"]:
                if call["kind"] != "pair":
                    continue
                for k, a in call["answers"].items():
                    if not approves(a):
                        item_id, phrase, quote = r["pairs"][k]
                        vetoes.setdefault(item_id, []).append((phrase, round(a["p_no"] or 0, 2), quote))
            for item_id in sorted(item_ok - set(r["approved"])):
                dropped.append({"rep": rep, "id": item_id, "vetoes": vetoes.get(item_id, []),
                                "not_asked": item_id in r["not_asked"]})

    # Within each pair run: the same run's item call alone versus the run's
    # final verdict, on the shown draft. This difference is the pair check's
    # own effect, free of run-to-run noise in the item question.
    for row in per_answer:
        if row.get("no_check"):
            continue
        for rep in (1, 2):
            r = runs[("pair", rep)][(row["label"], row["shown_check"])]
            item_ok = item_in_pair[(rep, (row["label"], row["shown_check"]))] & set(row["showable"])
            row[f"pair{rep}_itemcall"] = row["code_only"] + len(item_ok)
            row[f"pair{rep}_vetoed_shown"] = sorted(item_ok - set(r["approved"]))

    # Candidate-level noise: item1 vs item2, and all four item readings.
    cands = sorted({i for r in runs[("item", 1)].values() for i in r["ids"]})
    def ok_set(arm, rep):
        return {i for r in runs[(arm, rep)].values() for i in r["approved"]}
    i1, i2, p1, p2 = ok_set("item", 1), ok_set("item", 2), ok_set("pair", 1), ok_set("pair", 2)
    ip1 = set().union(*[v for (rep, _k), v in item_in_pair.items() if rep == 1])
    ip2 = set().union(*[v for (rep, _k), v in item_in_pair.items() if rep == 2])
    four = [i1, i2, ip1, ip2]
    flips_any = sum(1 for c in cands if 0 < sum(c in s for s in four) < 4)

    texts = {}
    for label, ans in live.items():
        for n, c in enumerate(ans["checks"], start=1):
            for i, it in enumerate(c["items"], start=1):
                texts[f"{label}c{n}i{i}"] = it
    result = {
        "per_answer": per_answer, "flags": flags, "dropped": dropped, "not_asked_total": not_asked_total,
        "failed_checks": [{"label": f["label"], "check": f["check"], "error": f["error"]} for f in failed],
        "candidate_totals": {"candidates": len(cands), "item1": len(i1), "item2": len(i2), "pair1": len(p1),
                             "pair2": len(p2), "item_call_in_pair1": len(ip1), "item_call_in_pair2": len(ip2),
                             "item1_xor_item2": len(i1 ^ i2), "pair1_xor_pair2": len(p1 ^ p2),
                             "flip_in_any_of_4_item_readings": flips_any},
        "spend": {f"{a}{r}": round(sum(x["cost_usd"] for x in runs[(a, r)].values()), 5) for a, r in RUNS},
        "failed_spend": round(sum(f["cost_usd"] for f in failed), 5),
    }
    # Per-depth summary.
    summary = {}
    for depth in ("plain", "researcher"):
        rows = [r for r in per_answer if r["depth"] == depth and not r.get("no_check")]
        s = {"answers": len(rows)}
        cols = (["live_prose"] + [f"{a}{k}" for a, k in RUNS] + [f"{a}{k}_B" for a, k in RUNS]
                + ["pair1_itemcall", "pair2_itemcall"])
        for col in cols:
            vals = [r[col] for r in rows]
            s[col] = {"total": sum(vals), "mean": round(statistics.mean(vals), 2), "min": min(vals), "max": max(vals)}
        for model, suf in (("A", ""), ("B", "_B")):
            s[f"zero_pair_not_item_{model}"] = [r["label"] for r in rows if any(r[f"pair{k}{suf}"] == 0 for k in (1, 2))
                                                and all(r[f"item{k}{suf}"] > 0 for k in (1, 2))]
            s[f"item_noise_{model}"] = [sum(1 for r in rows if r[f"item1{suf}"] != r[f"item2{suf}"]),
                                        sum(abs(r[f"item1{suf}"] - r[f"item2{suf}"]) for r in rows)]
            s[f"pair_noise_{model}"] = [sum(1 for r in rows if r[f"pair1{suf}"] != r[f"pair2{suf}"]),
                                        sum(abs(r[f"pair1{suf}"] - r[f"pair2{suf}"]) for r in rows)]
        s["zero_pair_not_item"] = [r["label"] for r in rows
                                   if any(r[f"pair{k}"] == 0 for k in (1, 2)) and all(r[f"item{k}"] > 0 for k in (1, 2))]
        s["zero_by_run"] = {f"{a}{k}": [r["label"] for r in rows if r[f"{a}{k}"] == 0] for a, k in RUNS}
        s["item_noise_answers_differ"] = sum(1 for r in rows if r["item1"] != r["item2"])
        s["item_noise_abs_sum"] = sum(abs(r["item1"] - r["item2"]) for r in rows)
        s["pair_noise_answers_differ"] = sum(1 for r in rows if r["pair1"] != r["pair2"])
        s["pair_noise_abs_sum"] = sum(abs(r["pair1"] - r["pair2"]) for r in rows)
        summary[depth] = s
    result["summary"] = summary
    (HERE / "analysis.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))

    print(json.dumps(summary, indent=1))
    print(json.dumps(result["candidate_totals"], indent=1))
    print("spend", result["spend"], "failed", result["failed_spend"], "not asked", not_asked_total)
    print("\nper answer: label depth shown_check/n live code_only | item1 item2 pair1 pair2 | live_ok_not_shown")
    for r in per_answer:
        if r.get("no_check"):
            print(f"  {r['label']}: no check ran, outcome {r['outcome']}")
            continue
        print(f"  {r['label']} {r['depth'][:5]} c{r['shown_check']}/{r['n_checks']} match {r['match_score']}/{r['live_prose']} "
              f"live {r['live_prose']} code {r['code_only']} | {r['item1']} {r['item2']} {r['pair1']} {r['pair2']} | "
              f"B {r['item1_B']} {r['item2_B']} {r['pair1_B']} {r['pair2_B']} | "
              f"in-run item {r['pair1_itemcall']} {r['pair2_itemcall']} vetoed {r['pair1_vetoed_shown']} {r['pair2_vetoed_shown']} | "
              f"{r['live_ok_not_shown']}")
    print("\nflags (arm could change which draft is kept):")
    for f in flags:
        print("  ", f)
    print("\ndropped by the pair check (item call in the same run approved it):")
    seen = {}
    for d in dropped:
        seen.setdefault(d["id"], []).append(d)
    for item_id, ds in sorted(seen.items()):
        it = texts[item_id]
        print(f"\n[{item_id}] runs {[d['rep'] for d in ds]} S: {it['sentence']}")
        for d in ds:
            for phrase, p, quote in d["vetoes"]:
                print(f"   rep{d['rep']} PAIR '{phrase}' p_no={p}")
        for q in it["quotes"]:
            print(f"   Q: {q[:600]}")


if __name__ == "__main__":
    main()
