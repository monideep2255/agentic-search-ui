"""Summarise the develop live timelines written by live_timeline.py.

Prints one row per question: when each moment ARRIVED on this client, seconds
after the question was submitted, plus the longest silence (the largest gap
between two consecutive arrivals) and where it fell. Also prints the stream
headers once and the largest arrival lag seen, the check on transport
buffering. Output: live_summary.md.
"""
import json
from pathlib import Path

here = Path(__file__).parent
rows = []
headers = None
for f in sorted((here / "live_develop").glob("dev_*.json")):
    r = json.loads(f.read_text())
    m = r["moments"]
    ev = r["events"]
    headers = headers or r["headers"]
    gaps = [(ev[i + 1]["arrive_s"] - ev[i]["arrive_s"], ev[i]["type"] + ">" + ev[i + 1]["type"]) for i in range(len(ev) - 1)]
    g = max(gaps) if gaps else (0, "")
    toks = [e for e in ev if e["type"] == "token"]
    spread = (toks[-1]["arrive_s"] - toks[0]["arrive_s"]) if toks else None

    def a(k, m=m):
        v = m.get(k)
        return None if not v else v["arrive_s"]

    rows.append((r["id"], r["create_s"], a("first_event"), a("guard"), a("think"), a("last_tool_result"), a("write_started"),
                 a("first_token"), a("done"), round(g[0], 1), g[1], len(toks), spread, m["max_lag_s"], m["withdrawn"]))
out = ["# Develop live timelines, 2026-09-26", "",
       "Seconds after the question was submitted, as each moment arrived on the client. Researcher depth, fresh session per question.", "",
       "| Question | POST returned | First event | Guard | Think | Last tool result | Write started | First word | Done | Longest silence s | Between | Tokens | Token spread s | Max arrival lag s | Withdrawn |",
       "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for row in rows:
    out.append("| " + " | ".join("n/a" if x is None else (f"{x:.2f}" if isinstance(x, float) else str(x)) for x in row) + " |")
out += ["", "Stream response headers (cookie-shaped headers excluded): " + json.dumps(headers)]
(here / "live_summary.md").write_text("\n".join(out) + "\n")
print("\n".join(out))
