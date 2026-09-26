"""Dry run of the golden client against a fake event stream (build phase 8.6, T-8.6-09).

Proves, with no live model call and no network beyond this machine, that
`testing/Developer/reports/2026-09-22_10.3_consistency/run_consistency.py`
records the time to the first word and keeps the first token event, and that
`summarize.py` reports the median time to the first word and the run's UTC
start time.

It starts a fake API on 127.0.0.1, runs the real client over two golden
questions (G-013, answered after a 0.4-second pause before its first word,
and G-042, refused at the guardrail with no word at all), runs the real
summarizer over the result, and checks every new field. Everything it writes
goes to a temporary directory that is removed at the end; the account file it
hands the client is obviously fake. Exit status 0 means every check passed.

Usage, from the repository root:

    python3 testing/Developer/reports/2026-09-26_phase_8.6/golden_client_dry_run.py

What it does not cover: a real server's timing, and a run the client times
out on. A live golden run measures the first; the client's timeout path is
unchanged by T-8.6-09.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

REPO_ROOT = Path(__file__).resolve().parents[4]
CLIENT_DIR = REPO_ROOT / "testing" / "Developer" / "reports" / "2026-09-22_10.3_consistency"
FIRST_WORD_PAUSE_S = 0.4
FIRST_TOKEN_TS = "2026-09-26T00:00:01.000000Z"


def _event(kind: str, seq: int, ts: str, payload: dict) -> dict:
    return {"type": kind, "version": "v1", "trace_id": "dry-run", "seq": seq, "ts": ts, "payload": payload}


def _answered_stream() -> list[tuple[float, dict]]:
    """(pause before sending, event) for a question that gets an answer."""
    return [
        (0.0, _event("guard", 0, "2026-09-26T00:00:00.000000Z", {"passed": True, "category": "ok", "reason": None})),
        (0.0, _event("think", 1, "2026-09-26T00:00:00.100000Z", {
            "query_class": "single_hop", "resolved_entities": [{"curie": "NCBIGene:672"}],
        })),
        (FIRST_WORD_PAUSE_S, _event("token", 2, FIRST_TOKEN_TS, {"text": "BRCA1 "})),
        (0.0, _event("token", 3, "2026-09-26T00:00:01.100000Z", {"text": "is linked to breast cancer."})),
        (0.0, _event("citation", 4, "2026-09-26T00:00:01.200000Z", {
            "source_id": "clinvar:1", "source_url": "https://www.ncbi.nlm.nih.gov/clinvar/1",
            "layer": "layer_2_api", "source": "clinvar", "field": "clinical_significance",
            "entity_name": "BRCA1", "evidence_kind": "record",
        })),
        (0.0, _event("trust_signal", 5, "2026-09-26T00:00:01.300000Z", {"outcome": "answer"})),
        (0.0, _event("done", 6, "2026-09-26T00:00:01.400000Z", {
            "trust_outcome": "answer", "trust_line": "Based on 1 source", "total_cost_usd": 0.01,
            "total_tool_calls": 1, "elapsed_ms": 1400,
        })),
    ]


def _refused_stream() -> list[tuple[float, dict]]:
    """A question the guardrail refuses: no answer word ever arrives."""
    return [
        (0.0, _event("guard", 0, "2026-09-26T00:00:00.000000Z", {
            "passed": False, "category": "off_topic", "reason": "not biomedical",
        })),
        (0.0, _event("done", 1, "2026-09-26T00:00:00.100000Z", {
            "trust_outcome": "refuse", "total_cost_usd": 0.0, "total_tool_calls": 0, "elapsed_ms": 100,
        })),
    ]


class _FakeApi(BaseHTTPRequestHandler):
    runs: ClassVar[dict[str, str]] = {}
    lock = threading.Lock()

    def log_message(self, *_args: object) -> None:  # keep the dry run's output readable
        return

    def _json(self, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/auth/login":
            self._json({"access_token": "fake-access-for-a-dry-run"})
        elif self.path == "/v1/query":
            with self.lock:
                run_id = f"run-{len(self.runs) + 1}"
                self.runs[run_id] = body.get("text", "")
            self._json({"run_id": run_id})
        else:
            self._json({})

    def do_GET(self) -> None:
        run_id = self.path.split("/")[3]
        question = self.runs.get(run_id, "")
        stream = _refused_stream() if "weather" in question.lower() else _answered_stream()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for pause, event in stream:
            if pause:
                time.sleep(pause)
            self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
            self.wfile.flush()


def _check(label: str, ok: bool, detail: object, failures: list[str]) -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {label}: {detail}")
    if not ok:
        failures.append(label)


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeApi)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "out"
        accounts = Path(tmp) / "accounts.json"
        accounts.write_text(json.dumps([{"email": "dry-run@example.invalid", "password": "not-a-real-one"}]))
        subprocess.run(
            [
                sys.executable, str(CLIENT_DIR / "run_consistency.py"), str(out_dir),
                "--accounts", str(accounts), "--ids", "G-013,G-042", "--passes", "1",
                "--workers", "1", "--base", base, "--commit", "dry-run",
            ],
            check=True,
        )
        subprocess.run([sys.executable, str(CLIENT_DIR / "summarize.py"), str(out_dir)], check=True)

        records = {
            r["id"]: r
            for r in (json.loads(line) for line in (out_dir / "runs.jsonl").read_text().splitlines() if line.strip())
        }
        answered, refused = records.get("G-013", {}), records.get("G-042", {})
        _check("two runs recorded", sorted(records) == ["G-013", "G-042"], sorted(records), failures)
        _check("G-013 answered", answered.get("outcome") == "answered", answered.get("outcome"), failures)
        word_s = answered.get("first_word_s")
        _check(
            "G-013 time to the first word covers the pause before it",
            isinstance(word_s, float) and FIRST_WORD_PAUSE_S <= word_s < 5.0, word_s, failures,
        )
        _check(
            "G-013 keeps its first token's server timestamp",
            answered.get("first_token_ts") == FIRST_TOKEN_TS, answered.get("first_token_ts"), failures,
        )
        _check("G-013 answer text still whole", answered.get("answer_words") == 6, answered.get("answer_words"), failures)
        _check("G-042 refused", refused.get("outcome") == "refused_offtopic", refused.get("outcome"), failures)
        _check(
            "G-042 has no first word",
            refused.get("first_word_s") is None and refused.get("first_token_ts") is None,
            (refused.get("first_word_s"), refused.get("first_token_ts")), failures,
        )

        raw_answered = json.loads((out_dir / "raw" / "G-013_run1.json").read_text())
        tokens = [e for e in raw_answered["events"] if e.get("type") == "token"]
        _check(
            "the saved G-013 run keeps exactly its first token event",
            len(tokens) == 1 and tokens[0].get("ts") == FIRST_TOKEN_TS and tokens[0]["payload"]["text"] == "BRCA1 ",
            [(e.get("ts"), e["payload"].get("text")) for e in tokens], failures,
        )
        _check(
            "the saved run still drops trust_signal and keeps citations",
            not any(e.get("type") == "trust_signal" for e in raw_answered["events"])
            and any(e.get("type") == "citation" for e in raw_answered["events"]),
            sorted({e.get("type") for e in raw_answered["events"]}), failures,
        )
        raw_refused = json.loads((out_dir / "raw" / "G-042_run1.json").read_text())
        _check(
            "the saved G-042 run has no token event",
            not any(e.get("type") == "token" for e in raw_refused["events"]),
            [e.get("type") for e in raw_refused["events"]], failures,
        )

        summary = (out_dir / "summary.md").read_text()
        start_row = next((line for line in summary.splitlines() if line.startswith("| Run started (UTC) |")), "")
        median_row = next(
            (line for line in summary.splitlines() if line.startswith("| Median time to the first word |")), ""
        )
        latency_line = next((line for line in summary.splitlines() if line.startswith("Time to the first word")), "")
        _check("the summary states the run's UTC start time", start_row.endswith(" UTC |"), start_row, failures)
        _check(
            "the summary states the median time to the first word",
            "seconds, over 1 of 2 runs" in median_row, median_row, failures,
        )
        _check("the latency section states it too", "over 1 of 2 runs" in latency_line, latency_line, failures)
    server.shutdown()
    print("dry run:", "every check passed" if not failures else f"{len(failures)} check(s) failed")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
