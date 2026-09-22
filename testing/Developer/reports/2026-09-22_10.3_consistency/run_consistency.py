"""Item 10.3, the consistency run: every golden question three times on develop.

One-off, read-only instrument in the shape of
testing/Developer/reports/2026-09-21_L01/capture_tool_results_v2.py: same base
URL, same SSE reassembly. It touches no tracked file except the ones it writes
into its own output directory (argv[1]).

Design, each line a measured constraint rather than a preference:

- SIGNED IN, one account per worker. `PER_USER_DAILY_QUERY_CAP` is 100 on
  develop, which is what turned 65 of the 2026-09-12 baseline's 150 runs into
  refusals when every run used one account. Two workers of 75 runs each sit
  under it. The anonymous path is worse: one source may take a tenth of
  `ANON_DAILY_RUN_CAP` per UTC day.
- CONCURRENCY 2, partitioned by QUESTION (odd and even ids), never by run.
  The E-utilities pool is 10 requests per second with a queue depth of 15
  and fail-fast beyond it, and one run makes about six `ncbi_efetch` calls
  (L-01 captures, 2026-09-21). Two runs worst case is 12 queued calls, under
  15. Three would be 18, over it, and .claude/rules/tool-call-budgets.md
  forbids an integration run that trips the limit it is measuring. Any
  tool_result whose summary mentions a rate pool is counted in
  `rate_limit_signals` so a contaminated run is visible rather than assumed
  absent.
- THREE PASSES per worker rather than three back-to-back tries: pass 1 asks
  each of the worker's questions once, then pass 2, then pass 3, so the three
  runs of one question are minutes apart. Back-to-back tries measure a
  minute; passes measure the hour.
- `audience_depth` OMITTED, so it resolves to the account's stored preference,
  which for a fresh account is the contract default `researcher`. The
  2026-09-12 baseline ran "at the default depth" the same way.
- A FRESH `session_id` per run, so no session memory carries between runs.
- SIGN IN BEFORE EVERY RUN: an access credential lives 15 minutes and a
  worker runs for about 40.
- WRITE FIRST: every record is appended to runs.jsonl the moment its run ends,
  before the next run starts, so an interrupted process loses at most the run
  in flight. Re-running with the same output directory resumes.

Outcome labels keep the 2026-09-12 baseline's meanings so the two can be set
side by side: `answered` is at least one citation with a non-refuse trust
outcome; `refused_no_evidence` is a completed run with zero citations;
`refused_offtopic` and the other `refused_<guard category>` labels are the
guardrail; `capped` is a daily-cap decline; `timeout` is the client giving up
on a stream; `error` is a fatal error event; `transport_error` is the client
failing to reach the API at all.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_BASE = "https://search-agent-api-develop-43b3.up.railway.app"
GOLDEN = Path(__file__).resolve().parents[4] / "eval" / "golden" / "golden_dataset.json"

STREAM_LINE_TIMEOUT_S = 200  # PER_STEP_TIMEOUT_SECONDS on develop is 90
RUN_DEADLINE_S = 420
PAUSE_BETWEEN_RUNS_S = 2.0
KEPT_CITATION_FIELDS = (
    "source_id",
    "source_url",
    "layer",
    "source",
    "field",
    "entity_name",
    "evidence_kind",
)

_jsonl_lock = threading.Lock()
_print_lock = threading.Lock()


def _post(base, path, body, bearer=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if bearer:
        req.add_header("Authorization", "Bearer " + bearer)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def sign_in(base, account):
    """Return the short-lived bearer credential for this account."""
    return _post(base, "/auth/login", account)["access_token"]


def stream(base, run_id, bearer, deadline_at):
    """Return (events, timed_out). Stops at the deadline or when the socket stalls."""
    req = urllib.request.Request(base + f"/v1/query/{run_id}/events")
    req.add_header("Accept", "text/event-stream")
    req.add_header("Authorization", "Bearer " + bearer)
    out = []
    timed_out = False
    try:
        with urllib.request.urlopen(req, timeout=STREAM_LINE_TIMEOUT_S) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").rstrip("\n")
                if line.startswith("data:"):
                    try:
                        out.append(json.loads(line[5:].strip()))
                    except json.JSONDecodeError:
                        pass
                if time.time() > deadline_at:
                    timed_out = True
                    break
    except TimeoutError:  # socket.timeout is an alias since 3.10
        timed_out = True
    return out, timed_out


def _events_of(events, kind):
    return [e.get("payload") or {} for e in events if e.get("type") == kind]


def classify(events, timed_out):
    guard = next(iter(_events_of(events, "guard")), None)
    fatal = next((p for p in _events_of(events, "error") if p.get("fatal")), None)
    done = next(iter(_events_of(events, "done")), None)
    citations = _events_of(events, "citation")
    if guard is not None and guard.get("passed") is False:
        cat = guard.get("category") or "unknown"
        return "refused_offtopic" if cat == "off_topic" else f"refused_{cat}"
    if fatal is not None and "daily" in (fatal.get("source") or ""):
        return "capped"
    if fatal is not None:
        return "error"
    if timed_out:
        return "timeout"
    if done is None:
        return "no_done"
    if citations and done.get("trust_outcome") != "refuse":
        return "answered"
    if citations:
        return "refused_with_sources"
    return "refused_no_evidence"


def _fail(record, t0, outcome, stage, exc):
    record.update(
        outcome=outcome,
        stage=stage,
        exception=str(exc)[:300],
        seconds=round(time.time() - t0, 1),
    )
    return record


def run_once(base, account, row, pass_index, worker, commit):
    session_id = "c103-" + uuid.uuid4().hex[:12]
    started_at = datetime.now(UTC).isoformat(timespec="seconds")
    t0 = time.time()
    record = {
        "id": row["id"],
        "run": pass_index,
        "pass": pass_index,
        "worker": worker,
        "account": account["email"],
        "category": row["search_category"],
        "query_class": row["query_class"],
        "expected_outcome": row["expected_outcome"],
        "question": row["question"],
        "session_id": session_id,
        "audience_depth": "researcher (omitted, account default)",
        "deployed_commit": commit,
        "started_at": started_at,
    }
    raw = {"record": None, "events": [], "answer_text": ""}
    try:
        bearer = sign_in(base, account)
    except Exception as exc:  # noqa: BLE001
        return _fail(record, t0, "transport_error", "sign_in", exc), raw
    try:
        created = _post(
            base, "/v1/query", {"text": row["question"], "session_id": session_id}, bearer
        )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        return _fail(record, t0, f"http_{exc.code}", "create", body), raw
    except Exception as exc:  # noqa: BLE001
        return _fail(record, t0, "transport_error", "create", exc), raw
    run_id = created.get("run_id")
    record["run_id"] = run_id
    try:
        events, timed_out = stream(base, run_id, bearer, t0 + RUN_DEADLINE_S)
    except Exception as exc:  # noqa: BLE001
        return _fail(record, t0, "transport_error", "stream", exc), raw
    if timed_out:
        try:
            _post(base, f"/v1/query/{run_id}/stop", None, bearer, timeout=20)
        except Exception as exc:  # noqa: BLE001
            record["stop_exception"] = str(exc)[:120]
    seconds = round(time.time() - t0, 1)

    guard = next(iter(_events_of(events, "guard")), None)
    think = next(iter(_events_of(events, "think")), None)
    done = next(iter(_events_of(events, "done")), None)
    fatal = next((p for p in _events_of(events, "error") if p.get("fatal")), None)
    tool_results = _events_of(events, "tool_result")
    citations = _events_of(events, "citation")
    text = "".join(p.get("text", "") for p in _events_of(events, "token"))
    words = text.split()

    tool_calls = [
        {k: tr.get(k) for k in ("tool", "layer", "status", "result_count", "truncated")}
        for tr in tool_results
    ]
    tool_errors = [
        {"tool": tr.get("tool"), "layer": tr.get("layer"), "summary": (tr.get("summary") or "")[:300]}
        for tr in tool_results
        if tr.get("status") == "error"
    ]
    rate_limit_signals = sum(
        1
        for tr in tool_results
        if "rate" in (tr.get("summary") or "").lower() and "pool" in (tr.get("summary") or "").lower()
    )
    if fatal and "rate" in (fatal.get("message") or "").lower():
        rate_limit_signals += 1

    by_layer = Counter(c.get("layer") for c in citations)
    distinct_sources = {c.get("source_id") for c in citations}
    must_cite = row.get("must_cite") or []
    cited_urls = [c.get("source_url") or "" for c in citations]
    must_cite_hits = sum(1 for prefix in must_cite if any(u.startswith(prefix) for u in cited_urls))

    record.update(
        outcome=classify(events, timed_out),
        timed_out=timed_out,
        guard_passed=None if guard is None else guard.get("passed"),
        guard_category=None if guard is None else guard.get("category"),
        guard_reason=None if guard is None else guard.get("reason"),
        think_query_class=None if think is None else think.get("query_class"),
        resolved_entities=None
        if think is None
        else [e.get("curie") for e in (think.get("resolved_entities") or [])],
        trust_outcome=None if done is None else done.get("trust_outcome"),
        trust_line=None if done is None else done.get("trust_line"),
        citations=len(citations),
        distinct_sources=len(distinct_sources),
        citations_by_layer=dict(by_layer),
        must_cite_total=len(must_cite),
        must_cite_hits=must_cite_hits,
        tools=[tc["tool"] for tc in tool_calls],
        layers=sorted({tc["layer"] for tc in tool_calls if tc.get("layer")}),
        tool_calls=tool_calls,
        l1_row_counts=[tc["result_count"] for tc in tool_calls if tc.get("layer") == "layer_1_graph"],
        l1_empty_calls=sum(
            1 for tc in tool_calls if tc.get("layer") == "layer_1_graph" and tc.get("status") == "empty"
        ),
        tool_errors=tool_errors,
        rate_limit_signals=rate_limit_signals,
        answer_words=len(words),
        answer_start=text[:160],
        error_payload=fatal,
        total_cost_usd=None if done is None else done.get("total_cost_usd"),
        total_tool_calls=None if done is None else done.get("total_tool_calls"),
        server_elapsed_s=None if done is None else round((done.get("elapsed_ms") or 0) / 1000, 3),
        seconds=seconds,
        event_types=dict(Counter(e.get("type") for e in events)),
    )
    raw["events"] = [
        e
        if e.get("type") != "citation"
        else {
            "type": "citation",
            "payload": {k: (e.get("payload") or {}).get(k) for k in KEPT_CITATION_FIELDS},
        }
        for e in events
        if e.get("type") not in ("token", "trust_signal")
    ]
    raw["answer_text"] = text
    return record, raw


def worker_main(worker, base, account, rows, passes, out_dir, commit, started_ids):
    jsonl = out_dir / "runs.jsonl"
    for pass_index in range(1, passes + 1):
        for row in rows:
            if (row["id"], pass_index) in started_ids:
                continue
            record, raw = run_once(base, account, row, pass_index, worker, commit)
            raw["record"] = record
            with _jsonl_lock:
                with jsonl.open("a") as f:
                    f.write(json.dumps(record) + "\n")
                with (out_dir / "raw" / f"{row['id']}_run{pass_index}.json").open("w") as f:
                    json.dump(raw, f, indent=1)
            with _print_lock:
                print(
                    f"[{worker}] pass {pass_index} {row['id']} {record['outcome']:22} "
                    f"{record.get('seconds', 0):6}s cites={record.get('citations', 0):3} "
                    f"layers={','.join(record.get('layers') or ['none'])} "
                    f"l1_rows={record.get('l1_row_counts', [])} rl={record.get('rate_limit_signals', 0)} "
                    f"cost={record.get('total_cost_usd')}",
                    flush=True,
                )
            time.sleep(PAUSE_BETWEEN_RUNS_S)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--accounts", required=True, help="JSON list of sign-in bodies; never committed")
    ap.add_argument("--ids", default="", help="comma-separated golden ids; default all 50")
    ap.add_argument("--passes", type=int, default=3)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--commit", default="unknown")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    (out_dir / "raw").mkdir(parents=True, exist_ok=True)
    accounts = json.loads(Path(args.accounts).read_text())
    if len(accounts) < args.workers:
        sys.exit("one account per worker is required: the per-user daily cap is 100")

    rows = json.loads(GOLDEN.read_text())["queries"]
    if args.ids:
        wanted = set(args.ids.split(","))
        rows = [r for r in rows if r["id"] in wanted]

    # Resume support: a record already in runs.jsonl is not re-run.
    started_ids = set()
    jsonl = out_dir / "runs.jsonl"
    if jsonl.exists():
        for line in jsonl.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                started_ids.add((rec["id"], rec["pass"]))

    partitions = [rows[i :: args.workers] for i in range(args.workers)]
    print(
        f"base={args.base} commit={args.commit} questions={len(rows)} passes={args.passes} "
        f"workers={args.workers} already_done={len(started_ids)} "
        f"started={datetime.now(UTC).isoformat(timespec='seconds')}",
        flush=True,
    )
    threads = []
    for i, part in enumerate(partitions):
        name = "AB"[i] if i < 2 else str(i)
        t = threading.Thread(
            target=worker_main,
            args=(name, args.base, accounts[i], part, args.passes, out_dir, args.commit, started_ids),
            daemon=True,
        )
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    print(f"finished={datetime.now(UTC).isoformat(timespec='seconds')}", flush=True)


if __name__ == "__main__":
    main()
