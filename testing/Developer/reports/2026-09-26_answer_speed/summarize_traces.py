"""Summarise the local traces written by local_trace.py.

For each question: where the time went, step by step, and inside the Write
step call by call; the provider prompt cache's hit rate on every model call;
the sentence check's verdicts beside the old guard-tier judge's on the same
sentences; and duplicate HTTP requests inside one question (the best case for
a per-question response cache). Output: traces_summary.md.

Step boundaries use each event's own emit time (`emitted`), where the trace
recorded it; G-032 and G-034 ran before that field was added, so for them the
write step is bounded by its first and last recorded write-step call instead.
"""
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

here = Path(__file__).parent
out = ["# Local traces: where the seconds go, call by call", "",
       ("Eight golden questions run locally against develop's code with develop's tier models and Jev mode "
        "(local_trace.py). Local absolute times include this machine's own start-up and network, so read the "
        "durations of calls, not the wall total."), ""]

rows = []
cache_rows = []
sc_rows = []
dup_rows = []
synth_all = []
for f in sorted((here / "local_traces").glob("G-*.json")):
    d = json.loads(f.read_text())
    rec = d["rec"]
    em = {}
    for s in d["stamps"]:
        if s.get("emitted") is not None:
            key = s["type"] if s["type"] != "step" else "write_started"
            em.setdefault(key, s["emitted"])
            if s["type"] == "tool_result":
                em["last_tool_result"] = s["emitted"]
            if s["type"] == "done":
                em["done"] = s["emitted"]
    synth = [m for m in rec["model"] if m["role"] == "synth"]
    synth_all += synth
    sc = rec["sentence_check"]
    gws = [w for w in rec["write"] if w["what"] == "ground_with_sentence_check"]
    res = [w for w in rec["write"] if w["what"] in ("resolve_concept_ids", "resolve_descriptor_ids")]
    ws = em.get("write_started")
    done = em.get("done")
    pre_synth_res = sum(w["dur"] for w in res if ws is not None and w["t"] >= ws - 0.01 and synth and w["t"] < synth[0]["t"])
    post_res = sum(w["dur"] for w in res if synth and w["t"] > synth[-1]["t"])
    reader = sum(x["dur"] for x in rec["reader"])
    rows.append({
        "id": d["id"], "withdrawn": d["withdrawn"],
        "guard_to_think": (em["think"] - em["guard"]) if "think" in em and "guard" in em else None,
        "act": (em["last_tool_result"] - em["plan"]) if "last_tool_result" in em and "plan" in em else None,
        "write": (done - ws) if (done is not None and ws is not None) else None,
        "names_before_synth": pre_synth_res,
        "synth1": synth[0]["dur"] if synth else None,
        "check1": gws[0]["dur"] if gws else None,
        "synth2": synth[1]["dur"] if len(synth) > 1 else None,
        "check2": gws[1]["dur"] if len(gws) > 1 else None,
        "names_after": post_res,
        "reader": reader,
        "out_tokens": [m["completion_tokens"] for m in synth],
    })
    for m in rec["model"]:
        if m.get("ok") and m.get("prompt_tokens"):
            cache_rows.append((d["id"], m["site"], m["prompt_tokens"], m.get("cached_tokens") or 0))
    for i, c in enumerate(sc):
        g = d["guard_sentence_check"][i] if i < len(d["guard_sentence_check"]) else {}
        sc_rows.append((d["id"], i + 1, len(c["candidates"]), len(c.get("approved") or []), len(g.get("approved") or []), c["dur"]))
    keys = Counter()
    durs = defaultdict(list)
    for h in rec["http"]:
        if h["host"] == "openrouter.ai":
            continue
        k = (h["host"], h["path"], tuple(map(tuple, h["params"])))
        keys[k] += 1
        durs[k].append(h["dur"])
    dups = {k: v for k, v in keys.items() if v > 1}
    dup_rows.append((d["id"], sum(1 for h in rec["http"] if h["host"] != "openrouter.ai"),
                     sum(v - 1 for v in dups.values()),
                     round(sum(sum(sorted(durs[k])[:-1]) for k in dups), 2)))


def f(x, nd=1):
    return "n/a" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


out += ["## Step and call durations, seconds", "",
        "| Question | Withdrawn | Think step | Act (plan to last tool) | Write step | Name lookups before writer | Writer call 1 | Check 1 (grounding and Jev) | Writer call 2 (repair) | Check 2 | Name lookups after | Reader pass in Act | Writer output tokens |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for r in rows:
    out.append(f"| {r['id']} | {r['withdrawn']} | {f(r['guard_to_think'])} | {f(r['act'])} | {f(r['write'])} | {f(r['names_before_synth'])} | "
               f"{f(r['synth1'])} | {f(r['check1'])} | {f(r['synth2'])} | {f(r['check2'])} | {f(r['names_after'])} | {f(r['reader'])} | {r['out_tokens']} |")
s1 = [r["synth1"] for r in rows if r["synth1"]]
s2 = [r["synth2"] for r in rows if r["synth2"]]
wr = [r["write"] for r in rows if r["write"]]
both = [r["synth1"] + (r["synth2"] or 0) for r in rows if r["synth1"] and r["write"]]
share = [(r["synth1"] + (r["synth2"] or 0)) / r["write"] for r in rows if r["synth1"] and r["write"]]
out += ["", (f"Writer call 1: median {statistics.median(s1):.1f} s. Writer call 2 fired on {len(s2)} of {len(rows)}: median {statistics.median(s2):.1f} s. "
        f"Both writer calls together are a median {statistics.median(share) * 100:.0f} percent of the write step where it was bounded ({len(share)} questions)."), ""]
tps = [m["completion_tokens"] / m["dur"] for m in synth_all if m.get("ok") and m["dur"]]
outs = [m["completion_tokens"] for m in synth_all if m.get("ok")]
out += [(f"Writer throughput: median {statistics.median(tps):.0f} output tokens per second (range {min(tps):.0f} to {max(tps):.0f}); "
        f"output length median {statistics.median(outs):.0f} tokens (range {min(outs)} to {max(outs)})."), ""]
out += ["## Provider prompt cache, every model call", "",
        "| Call site | Calls | Prompt tokens, median | Share of prompt tokens served from cache | Calls with any cache hit |",
        "|---|---|---|---|---|"]
by_site = defaultdict(list)
for qid, site, p, c in cache_rows:
    by_site[site].append((p, c))
for site, v in sorted(by_site.items()):
    tot_p = sum(p for p, _ in v)
    tot_c = sum(c for _, c in v)
    out.append(f"| {site} | {len(v)} | {statistics.median(p for p, _ in v):.0f} | {tot_c / tot_p * 100:.0f}% | {sum(1 for _, c in v if c)} of {len(v)} |")
out += ["", "## Sentence check: Jev against the old guard-tier judge on the same sentences", "",
        "| Question | Check | Candidate sentences | Jev approved | Guard judge approved | Jev call s |",
        "|---|---|---|---|---|---|"]
for r in sc_rows:
    out.append("| " + " | ".join(str(x) for x in r) + " |")
out += ["", f"Totals: {sum(r[2] for r in sc_rows)} candidates, Jev approved {sum(r[3] for r in sc_rows)}, guard judge approved {sum(r[4] for r in sc_rows)}.", ""]
out += ["## Duplicate HTTP requests inside one question (NCBI, PubTator, trials, graph)", "",
        "| Question | Requests | Exact repeats | Seconds spent on repeats |", "|---|---|---|---|"]
for r in dup_rows:
    out.append("| " + " | ".join(str(x) for x in r) + " |")
(here / "traces_summary.md").write_text("\n".join(out) + "\n")
print("\n".join(out))
