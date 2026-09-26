"""Ask develop a few golden questions and timestamp every event as it arrives.

Read-only instrument. One question at a time, one fresh session per question,
the account's default depth (researcher), exactly as the golden run asks.

For every SSE `data:` line it records:
- `arrive_s`: this client's monotonic clock, seconds since the question was
  submitted (the POST to /v1/query), so no clock is compared across machines;
- the server's own `ts` and `seq`, the event type, and a short payload summary
  (step name, tool and status, token text length).

From those it derives, per question, the moments a person could see
something: the first event of any kind, the guard, think and plan events, the
first and last tool events, the write step's start, the first token, the last
token and `done`. It also records how late each event arrived relative to when
the server stamped it (`lag_s`, the arrival gap minus the smallest gap seen on
that question), which separates "the server was working" from "the event was
held back on the way".

Response headers of the event stream are kept, minus anything cookie-shaped,
to answer whether the transport buffers.

Credentials: sign-in bodies are read from the scratch accounts file whose path
is argv[1]; nothing credential-shaped is printed or written.

Usage: live_timeline.py <accounts_json> <out_dir> <label> <question_id>...
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path

BASE = "https://search-agent-api-develop-43b3.up.railway.app"
HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[3] / "eval" / "golden" / "golden_dataset.json"
KEEP_HEADERS = {
    "content-type",
    "cache-control",
    "x-accel-buffering",
    "content-encoding",
    "transfer-encoding",
    "connection",
    "server",
    "via",
    "x-railway-edge",
}


def post(path, body, bearer=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if bearer:
        req.add_header("Authorization", "Bearer " + bearer)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def summarize(ev):
    p = ev.get("payload") or {}
    t = ev.get("type")
    if t == "step":
        return f"{p.get('step')}:{p.get('status')}"
    if t in ("tool_start", "tool_result"):
        return f"{p.get('tool')}:{p.get('status')}"
    if t == "token":
        return f"len={len(p.get('text') or '')} kind={p.get('kind')}"
    if t == "done":
        return f"elapsed_ms={p.get('elapsed_ms')} outcome={p.get('trust_outcome')}"
    if t == "guard":
        return f"passed={p.get('passed')}"
    if t == "think":
        return f"class={p.get('query_class')}"
    return ""


def ask(account, qid, text):
    bearer = post("/auth/login", account)["access_token"]
    session_id = "spd-" + uuid.uuid4().hex[:12]
    started_at = datetime.now(UTC).isoformat(timespec="seconds")
    t0 = time.monotonic()
    created = post("/v1/query", {"text": text, "session_id": session_id}, bearer)
    t_created = time.monotonic() - t0
    run_id = created.get("run_id")
    req = urllib.request.Request(BASE + f"/v1/query/{run_id}/events")
    req.add_header("Accept", "text/event-stream")
    req.add_header("Authorization", "Bearer " + bearer)
    events = []
    headers = {}
    t_open = None
    with urllib.request.urlopen(req, timeout=200) as resp:
        t_open = time.monotonic() - t0
        headers = {k.lower(): v for k, v in resp.headers.items() if k.lower() in KEEP_HEADERS}
        for raw in resp:
            line = raw.decode("utf-8", "replace").rstrip("\n")
            if not line.startswith("data:"):
                continue
            arrive = time.monotonic() - t0
            try:
                ev = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            events.append(
                {
                    "arrive_s": round(arrive, 3),
                    "type": ev.get("type"),
                    "seq": ev.get("seq"),
                    "ts": ev.get("ts"),
                    "summary": summarize(ev),
                    "payload": ev.get("payload") if ev.get("type") in ("done", "error", "step", "guard") else None,
                    "text": (ev.get("payload") or {}).get("text") if ev.get("type") == "token" else None,
                }
            )
            if ev.get("type") == "done":
                break
            if arrive > 240:
                break
    return {
        "id": qid,
        "question": text,
        "started_at": started_at,
        "run_id": run_id,
        "create_s": round(t_created, 3),
        "stream_open_s": round(t_open or 0, 3),
        "headers": headers,
        "events": events,
    }


def ts_s(e):
    return datetime.fromisoformat(e["ts"]).timestamp()


def moments(rec):
    ev = rec["events"]
    if not ev:
        return {}
    # Server run start, from done.elapsed_ms (read when done is built since phase 8.6).
    done = next((e for e in ev if e["type"] == "done"), None)
    server_start = None
    if done and done.get("payload") and done["payload"].get("elapsed_ms") is not None:
        server_start = ts_s(done) - done["payload"]["elapsed_ms"] / 1000
    gaps = [e["arrive_s"] - ts_s(e) for e in ev if e.get("ts")]
    base_gap = min(gaps)
    for e in ev:
        e["lag_s"] = round(e["arrive_s"] - ts_s(e) - base_gap, 3) if e.get("ts") else None
        e["server_s"] = round(ts_s(e) - server_start, 3) if server_start and e.get("ts") else None

    def first(pred):
        return next((e for e in ev if pred(e)), None)

    def last(pred):
        return next((e for e in reversed(ev) if pred(e)), None)

    picks = {
        "first_event": ev[0],
        "guard": first(lambda e: e["type"] == "guard"),
        "think": first(lambda e: e["type"] == "think"),
        "plan": first(lambda e: e["type"] == "plan"),
        "first_tool_start": first(lambda e: e["type"] == "tool_start"),
        "last_tool_result": last(lambda e: e["type"] == "tool_result"),
        "write_started": first(lambda e: e["type"] == "step" and e["summary"] == "write:started"),
        "first_token": first(lambda e: e["type"] == "token"),
        "last_token": last(lambda e: e["type"] == "token"),
        "done": done,
    }
    out = {}
    for name, e in picks.items():
        if e is None:
            out[name] = None
        else:
            out[name] = {"arrive_s": e["arrive_s"], "server_s": e.get("server_s"), "lag_s": e.get("lag_s")}
    out["n_events"] = len(ev)
    out["n_tokens"] = sum(1 for e in ev if e["type"] == "token")
    out["max_lag_s"] = max((e["lag_s"] or 0) for e in ev)
    out["withdrawn"] = any("could not be verified against them" in (e.get("text") or "") for e in ev)
    return out


def main():
    accounts = json.loads(Path(sys.argv[1]).read_text())
    out_dir = Path(sys.argv[2])
    label = sys.argv[3]
    ids = sys.argv[4:]
    out_dir.mkdir(parents=True, exist_ok=True)
    golden = {q["id"]: q for q in json.loads(GOLDEN.read_text())["queries"]}
    for i, qid in enumerate(ids):
        text = golden[qid]["question"]
        account = accounts[i % len(accounts)]
        try:
            rec = ask(account, qid, text)
        except Exception as exc:  # noqa: BLE001
            print(f"{qid}: failed {type(exc).__name__}", flush=True)
            continue
        rec["moments"] = moments(rec)
        path = out_dir / f"{label}_{i:02d}_{qid}.json"
        path.write_text(json.dumps(rec, indent=1))
        m = rec["moments"]

        def a(name, m=m):
            v = m.get(name)
            return "  -  " if not v else f"{v['arrive_s']:5.1f}"

        print(
            f"{qid} guard {a('guard')} think {a('think')} plan {a('plan')} tool1 {a('first_tool_start')} "
            f"toolN {a('last_tool_result')} write {a('write_started')} tok1 {a('first_token')} "
            f"done {a('done')} tokens {m.get('n_tokens')} maxlag {m.get('max_lag_s')} withdrawn {m.get('withdrawn')}",
            flush=True,
        )
        time.sleep(2)


if __name__ == "__main__":
    main()
