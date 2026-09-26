"""Where the seconds go in the golden consistency runs, step by step.

Read-only. Reads the saved golden runs under testing/Developer/reports/ and
writes golden_timing.json and golden_timing.md beside this script.

Every stage is measured on ONE clock, so no client-server clock skew enters:

- Server stages use the server's own event `ts` values, plus `done.elapsed_ms`,
  which counts from the server's run start (`start_monotonic`, set before
  session memory loads and before the guardrail).
  - Phase 8.6 onward (T-8.6-07, W3): `elapsed_ms` is read when `done` is
    built, so run start to guard = elapsed_ms - (done.ts - guard.ts).
  - Before phase 8.6: `elapsed_ms` was read at the top of the write step, so
    run start to guard = elapsed_ms - (write_started.ts - guard.ts).
- Client overhead is `seconds` (client clock, sign in to stream end) minus the
  server's run start to done. It is sign in, the create call, the stream
  connection and delivery.
- Time to the first word, where recorded (phase 8.6 onward), is the client's
  own `first_word_s`.

Stages, in order:
  guardrail   run start -> guard event
  think       guard -> think event
  plan        think -> plan event
  act         plan -> last tool_result (first tool_start follows plan in ms)
  act_tail    last tool_result -> write started
  write       write started -> first token (phase 8.6 onward) or -> done
  emit        first token -> done (phase 8.6 onward only)
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORTS = HERE.parent
RUNS = [
    ("10.3 (09-22)", "2026-09-22_10.3_consistency", "old"),
    ("8.1 (09-25)", "2026-09-25_phase_8.1_golden", "old"),
    ("8.2 floor (09-25)", "2026-09-25_phase_8.2_golden", "old"),
    ("8.6 first (09-26)", "2026-09-26_phase_8.6_golden", "new"),
    ("8.6 re-land (09-26)", "2026-09-26_phase_8.6-reland_golden", "new"),
]
WITHDRAWN = "could not be verified against them"
STAGES = ["guardrail", "think", "plan", "act", "act_tail", "write", "emit"]


def ts(e):
    return datetime.fromisoformat(e["ts"]).timestamp()


def pct(values, q):
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    if len(v) == 1:
        return v[0]
    k = (len(v) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def med(values):
    return pct(values, 0.5)


def p90(values):
    return pct(values, 0.9)


def fmt(x, nd=1):
    return "n/a" if x is None else f"{x:.{nd}f}"


def run_timeline(doc, mode):
    ev = doc["events"]
    rec = doc["record"]
    first = {}
    for e in ev:
        first.setdefault(e["type"], e)
    guard = first.get("guard")
    think = first.get("think")
    plan = first.get("plan")
    done = first.get("done")
    write = next(
        (e for e in ev if e["type"] == "step" and (e.get("payload") or {}).get("step") == "write"),
        None,
    )
    token = first.get("token")
    starts = [e for e in ev if e["type"] == "tool_start"]
    results = [e for e in ev if e["type"] == "tool_result"]
    out = {
        "id": rec["id"],
        "pass": rec.get("pass") or rec.get("run"),
        "outcome": rec.get("outcome"),
        "query_class": rec.get("query_class"),
        "seconds": rec.get("seconds"),
        "first_word_s": rec.get("first_word_s"),
        "withdrawn": WITHDRAWN in (doc.get("answer_text") or ""),
        "answer_words": rec.get("answer_words"),
        "n_tools": len(starts),
    }
    if not (guard and done):
        return out, []
    t_guard, t_done = ts(guard), ts(done)
    elapsed = (done.get("payload") or {}).get("elapsed_ms")
    if elapsed is not None:
        elapsed_s = elapsed / 1000
        if mode == "new":
            out["guardrail"] = elapsed_s - (t_done - t_guard)
        elif write is not None:
            out["guardrail"] = elapsed_s - (ts(write) - t_guard)
    if think:
        out["think"] = ts(think) - t_guard
    if think and plan:
        out["plan"] = ts(plan) - ts(think)
    if plan and results:
        out["act"] = max(ts(e) for e in results) - ts(plan)
    elif plan and write:
        out["act"] = 0.0
    if write is not None:
        base = max([ts(e) for e in results], default=ts(plan) if plan else ts(write))
        out["act_tail"] = ts(write) - base
        if token is not None and mode == "new" and ts(token) >= ts(write):
            out["write"] = ts(token) - ts(write)
            out["emit"] = t_done - ts(token)
        else:
            out["write"] = t_done - ts(write)
    if out.get("guardrail") is not None:
        out["server_total"] = out["guardrail"] + (t_done - t_guard)
        if out["seconds"] is not None:
            out["client_overhead"] = out["seconds"] - out["server_total"]
    # Per tool call durations.
    by_id = {}
    for e in starts:
        by_id[(e["payload"] or {}).get("call_id")] = e
    calls = []
    last_result = max([ts(e) for e in results], default=None)
    for e in results:
        p = e.get("payload") or {}
        s = by_id.get(p.get("call_id"))
        if s is None:
            continue
        calls.append(
            {
                "tool": p.get("tool"),
                "status": p.get("status"),
                "dur": ts(e) - ts(s),
                "last": ts(e) == last_result,
            }
        )
    return out, calls


def main():
    all_out = {}
    md = []
    stage_rows = []
    trend_rows = []
    tool_tables = []
    p01_rows = []
    for label, folder, mode in RUNS:
        raw = REPORTS / folder / "raw"
        runs, calls_all = [], []
        for f in sorted(raw.glob("G-*_run*.json")):
            doc = json.loads(f.read_text())
            t, calls = run_timeline(doc, mode)
            runs.append(t)
            if t["outcome"] == "answered":
                calls_all.extend(calls)
        ans = [r for r in runs if r["outcome"] == "answered"]
        all_out[label] = {"runs": runs}
        row = {"run": label, "answered": len(ans)}
        for s in STAGES + ["server_total", "client_overhead", "seconds", "first_word_s"]:
            vals = [r.get(s) for r in ans if r.get(s) is not None]
            row[s] = (med(vals), p90(vals), len(vals))
        stage_rows.append(row)
        # Tools
        by_tool = defaultdict(list)
        crit = defaultdict(int)
        for c in calls_all:
            by_tool[c["tool"]].append(c["dur"])
            if c["last"]:
                crit[c["tool"]] += 1
        tool_tables.append((label, by_tool, crit))
        # P01
        kept = [r for r in ans if not r["withdrawn"]]
        wd = [r for r in ans if r["withdrawn"]]
        p01_rows.append(
            (
                label,
                len(ans),
                len(wd),
                med([r["seconds"] for r in kept]),
                med([r["seconds"] for r in wd]),
                med([r.get("write") for r in kept if r.get("write") is not None]),
                med([r.get("write") for r in wd if r.get("write") is not None]),
                p90([r.get("write") for r in kept if r.get("write") is not None]),
                p90([r.get("write") for r in wd if r.get("write") is not None]),
            )
        )
        over20 = sum(1 for r in ans if (r["seconds"] or 0) > 20)
        trend_rows.append((label, len(ans), over20))

    md.append("# Golden run timing, step by step\n")
    md.append("Answered runs only. Seconds, median / p90 (n). Generated by analyze_golden_timing.py.\n")
    md.append("## Stage medians and p90, answered runs\n")
    head = ["Run", "Answered"] + STAGES + ["Server total", "Client overhead", "Client seconds", "First word (client)"]
    md.append("| " + " | ".join(head) + " |")
    md.append("|" + "---|" * len(head))
    for row in stage_rows:
        cells = [row["run"], str(row["answered"])]
        for s in STAGES + ["server_total", "client_overhead", "seconds", "first_word_s"]:
            m, p, n = row[s]
            cells.append(f"{fmt(m)} / {fmt(p)} ({n})" if n else "n/a")
        md.append("| " + " | ".join(cells) + " |")
    md.append("")
    md.append("## Answered runs over 20 seconds (client seconds)\n")
    md.append("| Run | Answered | Over 20 s |")
    md.append("|---|---|---|")
    for label, n, o in trend_rows:
        md.append(f"| {label} | {n} | {o} |")
    md.append("")
    md.append("## Tool call durations, answered runs\n")
    for label, by_tool, crit in tool_tables:
        md.append(f"### {label}\n")
        md.append("| Tool | Calls | Median s | p90 s | Max s | Times it finished last |")
        md.append("|---|---|---|---|---|---|")
        for tool, vals in sorted(by_tool.items(), key=lambda kv: -len(kv[1])):
            md.append(
                f"| {tool} | {len(vals)} | {fmt(med(vals), 2)} | {fmt(p90(vals), 2)} | {fmt(max(vals), 2)} | {crit.get(tool, 0)} |"
            )
        md.append("")
    md.append("## Withdrawn summary (P01) against time\n")
    md.append(
        "| Run | Answered | Withdrawn | Median seconds, kept | Median seconds, withdrawn | Median write s, kept | Median write s, withdrawn | p90 write kept | p90 write withdrawn |"
    )
    md.append("|---|---|---|---|---|---|---|---|---|")
    for row in p01_rows:
        label, n, w, sk, sw, wk, ww, pk, pw = row
        md.append(
            f"| {label} | {n} | {w} | {fmt(sk)} | {fmt(sw)} | {fmt(wk)} | {fmt(ww)} | {fmt(pk)} | {fmt(pw)} |"
        )
    md.append("")
    (HERE / "golden_timing.md").write_text("\n".join(md) + "\n")
    (HERE / "golden_timing.json").write_text(json.dumps(all_out, indent=1, default=str))
    print("\n".join(md))


if __name__ == "__main__":
    sys.exit(main())
