"""Adversary, card 101: live Jev on the A-101-01 shape, develop's sentence
check (exported from origin/develop to the scratchpad) against the branch's,
both through `check_reworded_sentences`. Only `call_jev_batch` is wrapped,
to record answers. Hard budget in live_calls_used.txt (20 calls).

Usage (worktree root): ENV_FILE=... DEV_SRC=... python live_forms.py dry|dev|branch
Secrets are read into this process only, never printed or written.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
LIVE_BUDGET = 20
USED = HERE / "live_calls_used.txt"
OUT = HERE / "live_forms.jsonl"

mode = sys.argv[1]
if mode != "dry":
    for line in Path(os.environ["ENV_FILE"]).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
os.environ["CLASSIFIER_PROVIDER"] = "jev"
os.environ["PER_QUERY_COST_CAP_USD"] = "1.0"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
sys.path.insert(0, str(ROOT / "src"))

from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.synthesis.grounding import SynthesisCandidate


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


new = _load(ROOT / "src/system_03_search_agent/synthesis/sentence_check.py", "sc_branch")
old = _load(Path(os.environ["DEV_SRC"]) / "system_03_search_agent/synthesis/sentence_check.py", "sc_dev")


def c(tag: str, sentence: str, *quotes: str) -> SynthesisCandidate:
    return SynthesisCandidate(key=(tag, quotes), sentence=sentence, quotes=quotes)


ITEMS = [
    c("potentially",
      "Symptoms attributable to GERD are among those most commonly reported to primary care providers in the outpatient setting, and untreated GERD carries potential complications such as esophagitis and stricture",
      "Symptoms potentially attributable to gastroesophageal reflux disease are among those most commonly reported to primary care providers in the outpatient setting.",
      "Untreated GERD carries potential complications such as esophagitis and stricture."),
    c("commonly",
      "G6PD deficiency, the most common enzyme deficiency worldwide, is an X-linked disorder that affects persons of African, Asian, Mediterranean, or Middle-Eastern descent",
      "G6PD deficiency is the most common enzyme deficiency worldwide.",
      "This X-linked disorder most commonly affects persons of African, Asian, Mediterranean, or Middle-Eastern descent."),
    c("generally",
      "Proton pump inhibitors are safe for long-term use, and their use in the general population has increased",
      "Proton pump inhibitors are generally safe for long-term use.",
      "Their use in the general population has increased."),
    c("usually",
      "GERD symptoms respond to proton pump inhibitor therapy, with usual dosing once daily before breakfast",
      "GERD symptoms usually respond to proton pump inhibitor therapy.",
      "Usual dosing is once daily before breakfast."),
    c("frequently",
      "Patients with long-segment Barrett esophagus develop dysplasia, so frequent endoscopic surveillance is recommended",
      "Patients with long-segment Barrett esophagus frequently develop dysplasia.",
      "Frequent endoscopic surveillance is recommended."),
    c("treated",
      "Complications are rare in patients, and treatment with proton pump inhibitors heals esophagitis",
      "Complications are rare in treated patients.",
      "Treatment with proton pump inhibitors heals esophagitis."),
    c("transient",
      "Risk factors include abnormal relaxations of the lower esophageal sphincter, which relaxes transiently during swallowing",
      "Risk factors include abnormal transient relaxations of the lower esophageal sphincter.",
      "The sphincter relaxes transiently during swallowing."),
]


def dry() -> None:
    for it in ITEMS:
        print(it.key[0], "develop", old.check_phrases(it.sentence, it.quotes), "branch", new.check_phrases(it.sentence, it.quotes))


async def run(mod, label: str) -> None:
    used = int(USED.read_text()) if USED.exists() else 0
    _s, sent = mod.build_jev_state(ITEMS)
    calls, _na = mod.build_pair_calls(sent)
    need = 1 + len(calls)
    if used + need > LIVE_BUDGET:
        print("budget would be exceeded", used, need)
        return
    real = mod.call_jev_batch
    rec: list[dict] = []

    async def wrapped(**kw):
        t = time.monotonic()
        kind = "pair" if next(iter(kw["questions"])).startswith("pair_") else "item"
        r = await real(**kw)
        rec.append({"kind": kind, "wall_ms": int((time.monotonic() - t) * 1000), "cost_usd": r.cost_usd,
                    "answers": {k: {"choice": a.choice, "p_no": a.probabilities.get("no")} for k, a in r.answers.items()}})
        return r

    mod.call_jev_batch = wrapped
    tid = f"adv101-{label}-{int(time.time())}"
    harness = Harness(trace_id=tid)
    err = None
    try:
        approved = await mod.check_reworded_sentences(ITEMS, harness=harness, trace_id=tid,
                                                      budget_s=10.0, ask_guard=None)
    except Exception as exc:  # record, never retry  # noqa: BLE001 - a probe records any failure and carries on
        approved, err = frozenset(), f"{type(exc).__name__}: {exc}"[:300]
    USED.write_text(str(used + len(rec) if rec else used + need))
    pairs = {}
    for n, cand in enumerate(sent, start=1):
        for k, (phrase, _q) in enumerate(mod._proposed_pairs(cand.sentence, cand.quotes), start=1):
            pairs[f"pair_{n}_{k}"] = (cand.key[0], phrase)
    row = {"arm": label, "approved": sorted(k[0] for k in approved), "error": err, "calls": rec, "pairs": pairs,
           "items": {f"item_{n}": cand.key[0] for n, cand in enumerate(sent, start=1)}}
    with OUT.open("a") as fh:
        fh.write(json.dumps(row) + "\n")
    print(label, "approved:", row["approved"], "error:", err)
    for call in rec:
        for k, a in call["answers"].items():
            name = row["items"].get(k) or pairs.get(k)
            print(f"   {call['kind']:4} {k:10} {name} {a['choice']} p_no={a['p_no']}")
    print("calls used:", USED.read_text(), "cost:", sum(x["cost_usd"] for x in rec))


if __name__ == "__main__":
    if mode == "dry":
        dry()
    else:
        asyncio.run(run(old if mode == "dev" else new, mode))
