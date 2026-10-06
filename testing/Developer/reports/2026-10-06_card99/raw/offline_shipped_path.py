"""Card 99: re-judge the labelled set through the SHIPPED pair check.

Unlike `2026-10-05_qualifier_check/raw/offline_qualifier_judge.py`, which
asked the pair questions on their own in batches of 30, this driver calls
the product's own entry point, `sentence_check.check_reworded_sentences`, in
Jev mode, so every check runs exactly as live: the item call and its pair
calls together, packed by `build_pair_calls`, approved by the module's own
rule. Only `call_jev_batch` is wrapped, to record each call's answers, cost
and wall time; it is still the real client making the real call.

Usage (from <repo-root>):
    ENV_FILE=<path to an .env holding the key> python3 \
        testing/Developer/reports/2026-10-06_card99/raw/offline_shipped_path.py
  ITEMS_PER_CHECK=<n> sets the sentences a check carries (default 8, the
    top of the live 4 to 8).
  DRY_RUN=1 counts checks, calls and pairs without any model call.

Secrets are read into this process only and are never printed or written.
Output: offline_shipped_path.jsonl beside this file, one line per check,
appended as each check returns, so a rerun resumes.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
EVAL_SET = ROOT / "testing/Developer/reports/2026-10-05_qualifier_check/raw/eval_set.jsonl"
OUT = HERE / "offline_shipped_path.jsonl"

env_file = Path(os.environ.get("ENV_FILE", ROOT / ".env"))
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
os.environ["CLASSIFIER_PROVIDER"] = "jev"
os.environ["PER_QUERY_COST_CAP_USD"] = "1.0"
sys.path.insert(0, str(ROOT / "src"))

from system_03_search_agent.harness.cost_control import QueryCapExceededError
from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.synthesis import sentence_check as sc
from system_03_search_agent.synthesis.grounding import SynthesisCandidate

ITEMS = [json.loads(line) for line in EVAL_SET.read_text().splitlines()]
PER_CHECK = int(os.environ.get("ITEMS_PER_CHECK", "8"))
_real_call = sc.call_jev_batch
_calls: list[dict] = []


async def _recording_call(**kwargs):
    started = time.monotonic()
    kind = "pair" if next(iter(kwargs["questions"])).startswith("pair_") else "item"
    try:
        result = await _real_call(**kwargs)
    except Exception as exc:
        _calls.append({"kind": kind, "wall_ms": int((time.monotonic() - started) * 1000),
                       "error": type(exc).__name__, "reason": getattr(exc, "reason", None),
                       "billed_usd": getattr(exc, "billed_cost_usd", 0.0)})
        raise
    _calls.append({
        "kind": kind,
        "wall_ms": int((time.monotonic() - started) * 1000),
        "latency_ms": result.latency_ms,
        "cost_usd": result.cost_usd,
        "n_questions": len(kwargs["questions"]),
        "state_chars": len(kwargs["state"]),
        "answers": {k: {"choice": a.choice, "p_no": a.probabilities.get("no"), "p_yes": a.probabilities.get("yes")} for k, a in result.answers.items()},
    })
    return result


sc.call_jev_batch = _recording_call


async def _never_guard(_messages, _budget_s):
    raise AssertionError("Jev mode never asks the guard tier")


def _candidates(chunk: list[dict]) -> list[SynthesisCandidate]:
    return [SynthesisCandidate(key=(it["id"], tuple(it["quotes"])), sentence=it["sentence"], quotes=tuple(it["quotes"]))
            for it in chunk]


async def run_check(index: int, chunk: list[dict]) -> dict:
    candidates = _candidates(chunk)
    _calls.clear()
    harness = Harness(trace_id=f"card99-{index}")
    started = time.monotonic()
    try:
        approved = await sc.check_reworded_sentences(
            candidates, harness=harness, trace_id=f"card99-{index}", budget_s=12.0, ask_guard=_never_guard)
        error = None
    except (sc.SentenceCheckUnreadable, QueryCapExceededError) as exc:
        approved, error = frozenset(), type(exc).__name__
    wall_ms = int((time.monotonic() - started) * 1000)
    _state, sent = sc.build_jev_state(candidates)
    pair_calls, not_asked = sc.build_pair_calls(sent)
    phrases = {}
    for n, cand in enumerate(sent, start=1):
        for k, phrase in enumerate(sc.check_phrases(cand.sentence, cand.quotes), start=1):
            phrases[f"pair_{n}_{k}"] = (cand.key[0], phrase)
    return {
        "check": index,
        "ids": [it["id"] for it in chunk],
        "approved": sorted(key[0] for key in approved),
        "error": error,
        "wall_ms": wall_ms,
        "cost_usd": harness.get_query_cost_usd(f"card99-{index}"),
        "not_asked": sorted(sent[i - 1].key[0] for i in not_asked),
        "n_pair_calls": len(pair_calls),
        "phrases": phrases,
        "calls": list(_calls),
    }


def score(rows: list[dict]) -> None:
    by_id = {it["id"]: it for it in ITEMS}
    approved = {i for r in rows for i in r["approved"]}
    item_ok: dict[str, bool] = {}
    flagged: dict[str, list] = defaultdict(list)
    for r in rows:
        ids = r["ids"]
        for call in r["calls"]:
            for key, ans in call.get("answers", {}).items():
                # The module's own rule, `_jev_approves`.
                ok = (ans["choice"] == "no" and ans["p_no"] is not None and ans["p_yes"] is not None
                      and ans["p_no"] > ans["p_yes"])
                if call["kind"] == "item":
                    item_ok[ids[int(key.split("_")[1]) - 1]] = ok
                elif not ok:
                    item_id, phrase = r["phrases"][key]
                    flagged[item_id].append((phrase, round(ans["p_no"] or 0, 2)))
    table = defaultdict(lambda: [0, 0, 0])
    for it in ITEMS:
        sub = it["sublabel"] if it["label"] in ("A", "B") else ""
        for key in ((it["label"], ""), (it["label"], sub)) if sub else ((it["label"], ""),):
            table[key][0] += 1
            table[key][1] += item_ok.get(it["id"], False)
            table[key][2] += it["id"] in approved
    print("label/sublabel: items | item question alone approves | shipped check approves")
    for key in sorted(table):
        print(f"  {key[0]} {key[1]:20} {table[key][0]:4} | {table[key][1]:4} | {table[key][2]:4}")
    lost_f = [i for i in by_id if by_id[i]["label"] == "F" and item_ok.get(i) and i not in approved]
    print("F lost to the pair check:", [(i, flagged[i]) for i in lost_f])
    print("A approved:", [i for i in approved if by_id[i]["label"] == "A"])
    print("R approved:", [i for i in approved if by_id[i]["label"] == "R"])
    print("not asked:", [i for r in rows for i in r["not_asked"]])


async def main() -> None:
    chunks = [ITEMS[s:s + PER_CHECK] for s in range(0, len(ITEMS), PER_CHECK)]
    if os.environ.get("DRY_RUN"):
        n_pairs = n_calls = 0
        for chunk in chunks:
            _s, sent = sc.build_jev_state(_candidates(chunk))
            calls, not_asked = sc.build_pair_calls(sent)
            n_pairs += sum(len(c.questions) for c in calls)
            n_calls += 1 + len(calls)
            if not_asked:
                print("not asked in a check:", sorted(not_asked))
        print(f"{len(chunks)} checks, {n_calls} calls, {n_pairs} pairs")
        return
    done, spent = {}, 0.0
    if OUT.exists():
        for line in OUT.read_text().splitlines():
            row = json.loads(line)
            spent += row["cost_usd"]
            if not row["error"]:
                done[row["check"]] = row
    # An offline measurement script: one line per check as it returns.
    with open(OUT, "a") as out:  # noqa: ASYNC230
        for index, chunk in enumerate(chunks):
            if index in done:
                continue
            row = await run_check(index, chunk)
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            spent += row["cost_usd"]
            print(f"check {index}: {len(row['calls'])} calls, {row['wall_ms']} ms, ${row['cost_usd']:.5f}, "
                  f"error={row['error']}")
            if not row["error"]:
                done[index] = row
    rows = [done[i] for i in sorted(done)]
    if len(rows) < len(chunks):
        print(f"{len(chunks) - len(rows)} checks failed; rerun to resume")
    score(rows)
    item_wall = [max(c["wall_ms"] for c in r["calls"] if c["kind"] == "item") for r in rows]
    added = [r["wall_ms"] - w for r, w in zip(rows, item_wall, strict=True)]
    print(f"checks {len(rows)}, calls {sum(len(r['calls']) for r in rows)}, "
          f"cost of these ${sum(r['cost_usd'] for r in rows):.5f}, all spend incl. failed checks ${spent:.5f}")
    print(f"check wall ms {min(r['wall_ms'] for r in rows)} to {max(r['wall_ms'] for r in rows)}; "
          f"item call wall ms {min(item_wall)} to {max(item_wall)}; added ms {min(added)} to {max(added)}, "
          f"median {sorted(added)[len(added) // 2]}")
    print("pair-call latency ms:", sorted(c["latency_ms"] for r in rows for c in r["calls"] if c["kind"] == "pair"))


asyncio.run(main())
