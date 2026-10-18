"""Build phase 8.7, T-8.7-01, option B: the draft orders' write-step
seconds and cost per question under the Opus writer, from writer bench 3's
saved runs only. No model is called.

Reads the bench's `results.jsonl` and `raw/` for
`anthropic/claude-opus-5.5+effort-minimal`, runs 1 to 3 (54 runs), and
`uncitable_output.txt` beside this script (written by `uncitable.py`).

The orders, all choosing the shipped draft by the same strict-superset rule:

- sequential, today: the completeness draft only after the first reply,
  and only when it has a job.
- (a) and (b) side by side, always, waiting for both drafts: the second
  draft's time on a one-call run estimated (a) as t1 times the fired runs'
  median t2 / t1, or (b) as the same question's own repair time where it
  fired in another run.
- (c) side by side, always, the second draft dropped the moment the first
  leaves it nothing to do.
- (d) side by side only when the listing cannot cite a prompt finding (known
  before any writer call), dropped as in (c); otherwise today's order. The
  order the product builds.

Each run's write step is rebuilt from its saved stamps: pre (write start to
the first writer call), t1 and t2 (each call's `elapsed_s`), g1 (the first
draft's end to the second's start: grounding and the sentence check) and
post (the last draft's end to `done`). Side by side, a two-call run takes
pre + max(t1 + g1, t2) + post.

Cost is the metered cost per question (the done event's total). A two-call
run costs the same in every order. A one-call run that sent a second draft
pays for it: estimated at the first call's metered cost times the fired
runs' median c2 / c1 under (a) to (c), and under (d), when dropped, at what
`Harness.call_tier` meters for a cancelled call, the synth tier's
4,000-token output ceiling at Opus's $20 per million, $0.08.

Usage, from the repository root:
    python testing/Developer/reports/2026-09-26_phase_8.7/draft_order/draft_order.py \
        > testing/Developer/reports/2026-09-26_phase_8.7/draft_order/draft_order_output.txt
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
HERE = REPO / "testing/Developer/reports/2026-09-26_writer_bench_3"
MODEL = "anthropic/claude-opus-5.5+effort-minimal"


def pct(values, q):
    ordered = sorted(values)
    k = (len(ordered) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


rows = []
for line in (HERE / "results.jsonl").read_text().splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    if row["model"] != MODEL or row["run"] not in (1, 2, 3):
        continue
    raw = json.loads((HERE / "raw" / f"{MODEL.replace('/', '_')}__{row['question_id']}__r{row['run']}.json").read_text())
    events = raw["events"]
    ws = next(e["emitted"] for e in events if e["type"] == "step" and e.get("step") == "write")
    done = next(e["emitted"] for e in events if e["type"] == "done")
    synth = [c for c in raw["rec"]["call_tier"] if c["tier"] == "synth"]
    llm = [c for c in raw["rec"]["llm"] if c.get("synth")]
    row.update(ws=ws, done=done, synth=synth, llm=llm)
    rows.append(row)

print(f"runs: {len(rows)}")
fired = [r for r in rows if len(r["synth"]) >= 2]
single = [r for r in rows if len(r["synth"]) == 1]
print(f"repair fired (two writer calls): {len(fired)}; one writer call: {len(single)}")
print(f"repair shipped (shipped_draft == 1): {sum(1 for r in rows if r.get('shipped_draft') == 1)}")
print(f"first draft withdrawn-alone rescued? runs whose first draft grounded nothing and repair shipped: "
      f"{sum(1 for r in fired if r.get('shipped_draft') == 1)}")

ratios, gaps, cost_ratios = [], [], []
for r in fired:
    c1, c2 = r["synth"][0], r["synth"][1]
    t1_end = c1["t"] + c1["elapsed_s"]
    gaps.append(c2["t"] - t1_end)
    ratios.append(c2["elapsed_s"] / c1["elapsed_s"])
    cost_ratios.append(c2["cost_usd"] / c1["cost_usd"])
r_med = statistics.median(ratios)
g_med = statistics.median(gaps)
c_med = statistics.median(cost_ratios)
print(f"fired runs: median t2/t1 = {r_med:.3f}; median gap between draft 1's end and draft 2's start "
      f"(grounding and sentence check) = {g_med:.3f} s; median c2/c1 = {c_med:.3f}")

# Per question, the repair's own seconds where it fired in any run.
repair_by_q: dict[str, list[float]] = {}
for r in fired:
    repair_by_q.setdefault(r["question_id"], []).append(r["synth"][1]["elapsed_s"])

seq_w, par_w_a, par_w_b = [], [], []
seq_cost_m, par_cost_m = [], []
seq_cost_or, par_cost_or = [], []
for r in rows:
    ws, done = r["ws"], r["done"]
    c1 = r["synth"][0]
    t1, t1_start = c1["elapsed_s"], c1["t"]
    t1_end = t1_start + t1
    w = done - ws
    seq_w.append(w)
    metered = float(r.get("done_cost_usd") or r["metered_cost_usd"] or 0)
    billed = float(r["openrouter_cost_usd"] or 0)
    seq_cost_m.append(metered)
    seq_cost_or.append(billed)
    if len(r["synth"]) >= 2:
        c2 = r["synth"][1]
        g1 = c2["t"] - t1_end
        t2 = c2["elapsed_s"]
        t2_end = c2["t"] + t2
        pre = t1_start - ws
        post = done - t2_end
        wp = pre + max(t1 + g1, t2) + post
        par_w_a.append(wp)
        par_w_b.append(wp)
        par_cost_m.append(metered)
        par_cost_or.append(billed)
    else:
        pre = t1_start - ws
        post1 = done - t1_end  # draft 1's grounding, sentence check and the rest
        # (a) the second draft takes the first's time scaled by the fired runs' median ratio
        t2a = t1 * r_med
        par_w_a.append(pre + max(t1 + post1, t2a + post1 + 0.0))
        # (b) the same question's own repair seconds where it fired in another run, else (a)
        own = repair_by_q.get(r["question_id"])
        t2b = statistics.median(own) if own else t2a
        par_w_b.append(pre + max(t1 + post1, t2b + post1))
        c2m = c1["cost_usd"] * c_med
        par_cost_m.append(metered + c2m)
        or1 = r["llm"][0]["openrouter_cost_usd"]
        par_cost_or.append(billed + or1 * c_med)


def show(label, values, unit="s", digits=2):
    print(f"{label}: median {statistics.median(values):.{digits}f} {unit}, p90 {pct(values, 0.9):.{digits}f}, "
          f"max {max(values):.{digits}f}, mean {statistics.mean(values):.{digits}f}")


show("sequential (today) write step", seq_w)
show("side by side, (a) ratio estimate", par_w_a)
show("side by side, (b) own-question estimate", par_w_b)
show("sequential metered $ per question", seq_cost_m, "$", 4)
show("side by side metered $ per question", par_cost_m, "$", 4)
show("sequential OpenRouter $ per question", seq_cost_or, "$", 4)
show("side by side OpenRouter $ per question", par_cost_or, "$", 4)
print(f"side by side runs over $0.25 metered: {sum(1 for v in par_cost_m if v > 0.25)} of {len(par_cost_m)}")
print(f"sequential runs over $0.25 metered: {sum(1 for v in seq_cost_m if v > 0.25)} of {len(seq_cost_m)}")
print(f"side by side runs over 20 s write step, (a): {sum(1 for v in par_w_a if v > 20)}; (b): {sum(1 for v in par_w_b if v > 20)}; sequential: {sum(1 for v in seq_w if v > 20)}")
faster_a = sum(1 for s, p in zip(seq_w, par_w_a) if p < s - 0.01)
slower_a = sum(1 for s, p in zip(seq_w, par_w_a) if p > s + 0.01)
print(f"(a) per run: faster {faster_a}, slower {slower_a}, same {len(seq_w) - faster_a - slower_a}")
faster_b = sum(1 for s, p in zip(seq_w, par_w_b) if p < s - 0.01)
slower_b = sum(1 for s, p in zip(seq_w, par_w_b) if p > s + 0.01)
print(f"(b) per run: faster {faster_b}, slower {slower_b}, same {len(seq_w) - faster_b - slower_b}")

# (c) side by side, but the second draft is dropped the moment the first
# grounds with nothing left for a repair to do (the runs where today's repair
# did not fire): those runs take today's time and still pay for the second
# draft, which was already sent. Only the fired runs change time.
par_w_c = []
for r, s, a in zip(rows, seq_w, par_w_a):
    par_w_c.append(a if len(r["synth"]) >= 2 else s)
show("side by side, (c) second draft dropped when not needed", par_w_c)
print(f"(c) over 20 s: {sum(1 for v in par_w_c if v > 20)}")
fired_saving = [s - c for r, s, c in zip(rows, seq_w, par_w_c) if len(r["synth"]) >= 2]
show("(c) seconds saved on the fired runs", fired_saving)
extra = [p - s for p, s in zip(par_cost_m, seq_cost_m)]
show("extra metered $ per question, side by side", extra, "$", 4)
print(f"golden run of 150 questions at the mean: sequential ${150 * statistics.mean(seq_cost_m):.2f}, "
      f"side by side ${150 * statistics.mean(par_cost_m):.2f}")
by_q_fired = {}
for r in rows:
    by_q_fired.setdefault(r["question_id"], []).append(len(r["synth"]) >= 2)
print("questions by runs fired (of 3):", sorted(sum(v) for v in by_q_fired.values()))
print("sequential write step sorted:", [round(v, 1) for v in sorted(seq_w)])
print("(c) write step sorted:       ", [round(v, 1) for v in sorted(par_w_c)])

# (d) side by side only when the listing cannot cite some prompt finding by
# its own id (U non-empty, computed before any writer call; per run, from
# uncitable.py's output pasted in below), and the second draft dropped as in
# (c) when draft 1 leaves it nothing to do. U empty: today's sequential order.
U_EMPTY = set()
for line in (Path(__file__).resolve().parent / "uncitable_output.txt").read_text().splitlines():
    parts = line.split(" ", 5)
    if len(parts) >= 5 and parts[0].startswith("G-") and parts[4] == "0":
        U_EMPTY.add((parts[0], int(parts[1])))
par_w_d, par_cost_d = [], []
for r, s, c, cs, cp in zip(rows, seq_w, par_w_c, seq_cost_m, par_cost_m):
    key = (r["question_id"], r["run"])
    if key in U_EMPTY:
        par_w_d.append(s)
        par_cost_d.append(cs)
    else:
        par_w_d.append(c)
        # a dropped second draft is metered at the synth ceiling when
        # cancelled (harness.call_tier's CancelledError branch): 4000 output
        # tokens at Opus's $20 per million, $0.08; a needed one costs what
        # the bench measured
        par_cost_d.append(cs if len(r["synth"]) >= 2 else cs + 4000 * 20e-6)
show("side by side when predicted, (d)", par_w_d)
print(f"(d) over 20 s: {sum(1 for v in par_w_d if v > 20)}; U empty runs: {len(U_EMPTY)}")
show("(d) metered $ per question", par_cost_d, "$", 4)
print(f"(d) runs over $0.25: {sum(1 for v in par_cost_d if v > 0.25)}; golden run at the mean: ${150 * statistics.mean(par_cost_d):.2f}")
