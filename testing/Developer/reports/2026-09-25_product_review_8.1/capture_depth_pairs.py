"""Rubric line 3 capture for the phase 8.1 product review.

Creates one fresh develop account (random sign-in secret generated here, never
printed or saved), then asks each question once at plain_language and once at
researcher, sequentially, a fresh session per run. Saves each run's events and
joined answer text under raw/. Eight questions at most.
"""
import json
import secrets
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BASE = "https://search-agent-api-develop-43b3.up.railway.app"
OUT = Path(__file__).resolve().parent / "raw"
DEADLINE_S = 180

QUESTIONS = [
    ("G-013", "what diseases are linked to brca1?"),
    ("G-033", "Compare what is known about MLH1 and MSH2 in colorectal cancer risk."),
    ("G-032", "Which pathways does PTEN participate in?"),
    ("MARFAN", "What phenotypic features are associated with Marfan syndrome?"),
]
DEPTHS = ("plain_language", "researcher")


def post(path, body, bearer=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if bearer:
        req.add_header("Authorization", "Bearer " + bearer)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def stream(run_id, bearer, t0):
    req = urllib.request.Request(BASE + f"/v1/query/{run_id}/events")
    req.add_header("Accept", "text/event-stream")
    req.add_header("Authorization", "Bearer " + bearer)
    events, first_token_s, timed_out = [], None, False
    with urllib.request.urlopen(req, timeout=200) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").rstrip("\n")
            if line.startswith("data:"):
                try:
                    ev = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                events.append(ev)
                if ev.get("type") == "token" and first_token_s is None:
                    first_token_s = round(time.time() - t0, 1)
                if ev.get("type") == "done":
                    break
            if time.time() - t0 > DEADLINE_S:
                timed_out = True
                break
    return events, first_token_s, timed_out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    email = "s3-product-review-81-" + uuid.uuid4().hex[:10] + "@example.com"
    pw = secrets.token_urlsafe(24)
    creds = {"email": email, "password": pw}
    post("/auth/signup", creds)
    bearer = post("/auth/login", creds)["access_token"]
    print("signed up and signed in as", email, flush=True)
    for label, text in QUESTIONS:
        for depth in DEPTHS:
            t0 = time.time()
            session_id = "pr81-" + uuid.uuid4().hex[:12]
            rec = {"label": label, "question": text, "audience_depth": depth,
                   "session_id": session_id,
                   "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            try:
                created = post("/v1/query", {"text": text, "session_id": session_id,
                                             "audience_depth": depth}, bearer)
                rec["run_id"] = created.get("run_id")
                events, ft, to = stream(rec["run_id"], bearer, t0)
            except urllib.error.HTTPError as exc:
                rec["error"] = f"http_{exc.code}: " + exc.read().decode("utf-8", "replace")[:300]
                events, ft, to = [], None, False
            except Exception as exc:  # noqa: BLE001
                rec["error"] = repr(exc)[:300]
                events, ft, to = [], None, False
            rec["seconds"] = round(time.time() - t0, 1)
            rec["first_token_seconds"] = ft
            rec["timed_out"] = to
            done = next((e.get("payload") or {} for e in events if e.get("type") == "done"), {})
            guard = next((e.get("payload") or {} for e in events if e.get("type") == "guard"), {})
            cites = [e.get("payload") or {} for e in events if e.get("type") == "citation"]
            rec["guard"] = guard
            rec["trust_outcome"] = done.get("trust_outcome")
            rec["trust_line"] = done.get("trust_line")
            rec["citations"] = len(cites)
            rec["distinct_sources"] = len({(c.get("source"), c.get("source_id")) for c in cites})
            rec["rate_limit_signals"] = sum(
                1 for e in events if e.get("type") == "tool_result"
                and "rate" in ((e.get("payload") or {}).get("summary") or "").lower())
            answer = "".join((e.get("payload") or {}).get("text", "") for e in events
                             if e.get("type") == "token")
            (OUT / f"{label}_{depth}.json").write_text(json.dumps(
                {"record": rec, "events": events, "answer_text": answer}, indent=1))
            print(json.dumps({k: rec.get(k) for k in ("label", "audience_depth", "seconds",
                  "first_token_seconds", "trust_outcome", "trust_line", "citations",
                  "distinct_sources", "rate_limit_signals", "error")}), flush=True)
            time.sleep(3)


if __name__ == "__main__":
    sys.exit(main())
