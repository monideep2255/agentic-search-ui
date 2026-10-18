"""Card 101 replay, copied from `2026-10-06_card99/raw/live_ab/ab_run.py` with
only its paths adapted (the .env path is ENV_FILE, default REPO_ROOT/.env).
Run here for the "pair" arm only: the shipped check, now with card 101's
word forms. The card 99 text follows.

Card 99 A/B: the same live candidate sentences through the shipped sentence
check, with the pair check off (item question alone) and on (as shipped).

Inputs: every CHECK_IN record of the 2026-10-05 wave 3 live traces
(`testing/Developer/reports/2026-10-05_wave3/sentence_check_raw/`, the branch
runs gp, gr, md and the develop control runs cp, cr, cm). Each record is one
call of `check_reworded_sentences`, with the sentence and the quotes exactly
as the check received them, so each is replayed as one check, same batching.

Arms:
- item: `_proposed_pairs` patched to propose nothing, so `build_pair_calls`
  makes no call and only the item call runs (the check before card 99).
- pair: the module as shipped.

Usage (from the repository root, with the repository's virtual environment):
    python ab_run.py dry            # rebuild and count, no model call
    python ab_run.py run item 1     # one arm, one repetition
Output: run_<arm>_<rep>.jsonl beside this script, one line per check.
Secrets are read from the repository's .env into this process only and are
never printed or written.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ["REPO_ROOT"])
RAW = ROOT / "testing/Developer/reports/2026-10-05_wave3/sentence_check_raw"
SPEND_STOP_USD = float(os.environ.get("SPEND_STOP_USD", "0.19"))

for raw in Path(os.environ.get("ENV_FILE", ROOT / ".env")).read_text().splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
os.environ["CLASSIFIER_PROVIDER"] = "jev"
# Each replayed check gets its own trace, so the per-query cap never binds
# here; the verifier showed no live check is refused at $0.10 (V-99-01).
os.environ["PER_QUERY_COST_CAP_USD"] = "1.0"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
sys.path.insert(0, str(ROOT / "src"))

from system_03_search_agent.harness.cost_control import QueryCapExceededError
from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.synthesis import sentence_check as sc
from system_03_search_agent.synthesis.grounding import SynthesisCandidate

DEPTH = {"gp": "plain", "md": "plain", "cp": "plain", "cm": "plain", "gr": "researcher", "cr": "researcher"}


def load_checks() -> list[dict]:
    files = sorted(RAW.glob("*.jsonl")) + sorted((RAW / "develop_control").glob("*.jsonl"))
    checks = []
    for path in files:
        label = path.stem
        rows = [json.loads(x) for x in path.read_text().splitlines()]
        jev = [r["data"] for r in rows if r["tag"] in ("JEV_RESULT", "JEV_RAISED")]
        for n, d in enumerate([r["data"] for r in rows if r["tag"] == "CHECK_IN"], start=1):
            cands = [
                SynthesisCandidate(
                    key=(f"{label}c{n}i{i}", tuple(it["writer_quotes"])),
                    sentence=it["sentence"],
                    quotes=tuple(it["quotes"]),
                )
                for i, it in enumerate(d["items"], start=1)
            ]
            checks.append({"label": label, "depth": DEPTH[label[:2]], "check": n, "budget_s": d["budget_s"],
                           "candidates": cands, "live_state": jev[n - 1].get("state") if n <= len(jev) else None})
    return checks


_real_call = sc.call_jev_batch
_calls: list[dict] = []


async def _recording_call(**kwargs):
    kind = "pair" if next(iter(kwargs["questions"])).startswith("pair_") else "item"
    started = time.monotonic()
    try:
        result = await _real_call(**kwargs)
    except Exception as exc:
        _calls.append({"kind": kind, "error": type(exc).__name__, "reason": getattr(exc, "reason", None),
                       "billed_usd": getattr(exc, "billed_cost_usd", 0.0),
                       "wall_ms": int((time.monotonic() - started) * 1000)})
        raise
    _calls.append({"kind": kind, "cost_usd": result.cost_usd, "latency_ms": result.latency_ms,
                   "wall_ms": int((time.monotonic() - started) * 1000), "n_questions": len(kwargs["questions"]),
                   "answers": {k: {"choice": a.choice, "p_no": a.probabilities.get("no"),
                                   "p_yes": a.probabilities.get("yes")} for k, a in result.answers.items()}})
    return result


sc.call_jev_batch = _recording_call
_shipped_proposed_pairs = sc._proposed_pairs


async def _never_guard(_messages, _budget_s):
    raise AssertionError("Jev mode never asks the guard tier")


def pair_map(cands: list[SynthesisCandidate]) -> tuple[dict, list]:
    """pair key -> (item id, phrase, quote), and the not-asked item ids, from
    the shipped packing (the same functions `_ask_jev` calls)."""
    _state, sent = sc.build_jev_state(cands)
    calls, not_asked = sc.build_pair_calls(sent)
    out = {}
    for n, cand in enumerate(sent, start=1):
        for k, (phrase, quote) in enumerate(_shipped_proposed_pairs(cand.sentence, cand.quotes), start=1):
            out[f"pair_{n}_{k}"] = (cand.key[0], phrase, quote)
    return out, sorted(sent[i - 1].key[0] for i in not_asked), len(calls), len(sent)


async def run_arm(arm: str, rep: int) -> None:
    sc._proposed_pairs = (lambda _s, _q: []) if arm == "item" else _shipped_proposed_pairs
    out_path = HERE / f"run_{arm}_{rep}.jsonl"
    spent_before = 0.0
    for p in HERE.glob("run_*.jsonl"):
        if p != out_path:
            spent_before += sum(json.loads(x)["cost_usd"] for x in p.read_text().splitlines())
    done = set()
    spent = spent_before
    if out_path.exists():
        for x in out_path.read_text().splitlines():
            row = json.loads(x)
            spent += row["cost_usd"]
            done.add((row["label"], row["check"]))
    checks = load_checks()
    with open(out_path, "a") as out:  # noqa: ASYNC230 - a measurement script
        for c in checks:
            if (c["label"], c["check"]) in done:
                continue
            if spent > SPEND_STOP_USD:
                print(f"STOP: spend ${spent:.4f} past ${SPEND_STOP_USD}")
                return
            _calls.clear()
            trace = f"card101-{arm}{rep}-{c['label']}-{c['check']}"
            harness = Harness(trace_id=trace)
            started = time.monotonic()
            try:
                approved = await sc.check_reworded_sentences(
                    c["candidates"], harness=harness, trace_id=trace, budget_s=c["budget_s"],
                    ask_guard=_never_guard)
                error = None
            except (sc.SentenceCheckUnreadable, QueryCapExceededError) as exc:
                approved, error = frozenset(), f"{type(exc).__name__}: {str(exc)[:120]}"
            wall = int((time.monotonic() - started) * 1000)
            pmap, not_asked, n_pair_calls, _n_sent = pair_map(c["candidates"]) if arm == "pair" else ({}, [], 0, 0)
            cost = harness.get_query_cost_usd(trace)
            spent += cost
            row = {"label": c["label"], "depth": c["depth"], "check": c["check"], "arm": arm, "rep": rep,
                   "ids": [x.key[0] for x in c["candidates"]], "approved": sorted(k[0] for k in approved),
                   "error": error, "wall_ms": wall, "cost_usd": cost, "not_asked": not_asked,
                   "n_pair_calls": n_pair_calls,
                   "pairs": {k: list(v) for k, v in pmap.items()}, "calls": list(_calls)}
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            print(f"{arm}{rep} {c['label']} c{c['check']}: {len(row['approved'])}/{len(row['ids'])} approved, "
                  f"{len(_calls)} calls, {wall} ms, ${cost:.5f}, error={error}")
    print(f"done {arm}{rep}; cumulative spend ${spent:.4f}")


def dry() -> None:
    checks = load_checks()
    n_cand = sum(len(c["candidates"]) for c in checks)
    same = differ = missing = 0
    tot_pairs = tot_calls = tot_not = 0
    for c in checks:
        state, sent = sc.build_jev_state(c["candidates"])
        if c["live_state"] is None:
            missing += 1
        elif state == c["live_state"]:
            same += 1
        else:
            differ += 1
        assert len(sent) == len(c["candidates"])
        calls, not_asked = sc.build_pair_calls(sent)
        tot_pairs += sum(len(x.questions) for x in calls)
        tot_calls += 1 + len(calls)
        tot_not += len(not_asked)
    by_depth = {}
    for c in checks:
        by_depth.setdefault(c["depth"], [0, 0, set()])
        by_depth[c["depth"]][0] += 1
        by_depth[c["depth"]][1] += len(c["candidates"])
        by_depth[c["depth"]][2].add(c["label"])
    print(f"{len(checks)} checks, {n_cand} candidates; item state byte-identical to the live state sent: "
          f"{same}, different: {differ}, no live state: {missing}")
    print(f"shipped arm: {tot_calls} calls a run ({len(checks)} item, {tot_calls - len(checks)} pair), "
          f"{tot_pairs} pairs, {tot_not} sentences not asked")
    for d, (n, k, labels) in by_depth.items():
        print(f"  {d}: {n} checks, {k} candidates, {len(labels)} answers")


if __name__ == "__main__":
    if sys.argv[1] == "dry":
        dry()
    else:
        asyncio.run(run_arm(sys.argv[2], int(sys.argv[3])))
