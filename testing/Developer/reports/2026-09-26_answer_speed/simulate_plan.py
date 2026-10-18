"""Project the re-land's answered runs under the plan's first options. An estimate.

Inputs, all measured:
- each answered run's own step times, from the re-land's saved events
  (golden_timing.json, analyze_golden_timing.py);
- each tool call's start and end, from the same saved events;
- the local traces' split of the write step (traces_summary.md): the two writer
  calls are 99 percent of it, the first a median 2.9 s and the repair a median
  4.5 s, and the repair fired on 8 of 8, so the first call is 39 percent of the
  writer time.

Options projected:
- B, both drafts at once: the write step loses FIRST_CALL_SHARE of itself
  (wall time becomes the longer draft, not the sum). A run is not credited for
  anything else.
- C, a 6 s cap on a PubTator call: every pubtator_annotate call's end is
  clipped to its start plus 6 s, and the Act span is recomputed from the
  clipped ends. Tools chained after a clipped call are not moved earlier, so
  this under-counts rather than over-counts.
- E, the records shown when Write starts: the time to the first useful thing
  on screen is the server time at which Write starts plus the client's own
  overhead; it changes nothing about when the answer is done.

Output: simulate_plan_output.txt.
"""
import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE.parent / "2026-09-26_phase_8.6-reland_golden" / "raw"
FIRST_CALL_SHARE = 2.9 / (2.9 + 4.5)
PUBTATOR_CAP_S = 6.0


def ts(e):
    return datetime.fromisoformat(e["ts"]).timestamp()


def pct(v, q):
    v = sorted(v)
    k = (len(v) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


timing = {(r["id"], r["pass"]): r for r in json.loads((HERE / "golden_timing.json").read_text())["8.6 re-land (09-26)"]["runs"]}
base, with_b, with_bc, first_useful, first_word = [], [], [], [], []
per_run = []
for f in sorted(RAW.glob("G-*_run*.json")):
    d = json.loads(f.read_text())
    rec = d["record"]
    if rec.get("outcome") != "answered":
        continue
    t = timing[(rec["id"], rec["pass"])]
    # Act runs its planned calls in two batches (`act_node`,
    # `_gather_planned_calls`): follow-up calls start only when the whole first
    # batch is done. Every call, follow-ups included, announces its start with
    # the plan, so the batches are told apart by their ENDS: the first batch
    # closes at the first result after the longest silence (when that silence
    # exceeds 2 s), and every later result is a follow-up whose own duration is
    # its end minus that close. Capping PubTator at 6 s moves the close to the
    # cap when PubTator was the long pole, and every follow-up moves with it;
    # a follow-up PubTator call is capped at 6 s of its own too.
    plan_t = ts(next(e for e in d["events"] if e["type"] == "plan"))
    results = sorted(
        ((ts(e) - plan_t, e["payload"].get("tool")) for e in d["events"] if e["type"] == "tool_result"),
        key=lambda x: x[0],
    )
    save_c = 0.0
    if results:
        ends = [r[0] for r in results]
        gaps = [(ends[i + 1] - ends[i], i + 1) for i in range(len(ends) - 1)]
        big = max(gaps) if gaps else (0.0, 0)
        old_last = ends[-1]
        if big[0] > 2.0:
            close_i = big[1]
            before = ends[:close_i]
            pole_end, pole_tool = results[close_i]
            new_close = min(pole_end, PUBTATOR_CAP_S) if pole_tool == "pubtator_annotate" else pole_end
            new_close = max([new_close] + before)
            later = []
            for end, tool in results[close_i + 1:]:
                dur = end - pole_end
                if tool == "pubtator_annotate":
                    dur = min(dur, PUBTATOR_CAP_S)
                later.append(new_close + dur)
            new_last = max([new_close] + later)
        else:
            new_last = max(min(end, PUBTATOR_CAP_S) if tool == "pubtator_annotate" else end for end, tool in results)
        save_c = max(0.0, old_last - new_last)
    save_b = FIRST_CALL_SHARE * (t.get("write") or 0.0)
    s0 = rec["seconds"]
    base.append(s0)
    with_b.append(s0 - save_b)
    with_bc.append(s0 - save_b - save_c)
    server_write_start = sum(t.get(k) or 0.0 for k in ("guardrail", "think", "plan", "act", "act_tail"))
    first_useful.append(server_write_start + (t.get("client_overhead") or 0.5))
    if rec.get("first_word_s") is not None:
        first_word.append(rec["first_word_s"])
    per_run.append((rec["id"], rec["pass"], s0, round(s0 - save_b - save_c, 1), round(save_b, 1), round(save_c, 1)))

lines = [
    f"Answered runs: {len(base)}",
    f"Today (re-land): median {pct(base, .5):.1f}, p90 {pct(base, .9):.1f}, max {max(base):.1f}, over 20 s {sum(1 for x in base if x > 20)}",
    f"With B, both drafts at once: median {pct(with_b, .5):.1f}, p90 {pct(with_b, .9):.1f}, max {max(with_b):.1f}, over 20 s {sum(1 for x in with_b if x > 20)}",
    f"With B and C, PubTator capped at {PUBTATOR_CAP_S:g} s: median {pct(with_bc, .5):.1f}, p90 {pct(with_bc, .9):.1f}, max {max(with_bc):.1f}, over 20 s {sum(1 for x in with_bc if x > 20)}",
    f"First word today (client): median {pct(first_word, .5):.1f}, p90 {pct(first_word, .9):.1f}",
    f"With E, records on screen when Write starts: median {pct(first_useful, .5):.1f}, p90 {pct(first_useful, .9):.1f}, max {max(first_useful):.1f}",
    "",
    "Runs still over 20 s with B and C (id, pass, today, projected, saved by B, saved by C):",
]
for row in sorted(per_run, key=lambda r: -r[3]):
    if row[3] > 20:
        lines.append(f"  {row}")
(HERE / "simulate_plan_output.txt").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
