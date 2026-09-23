"""Re-run the seven questions the skip manager asked on the 2026-09-14 build,
against TODAY's code, one at a time so the shared NCBI rate pools are never
contended. Writes one JSON line per question to runs.jsonl plus the full
transcript per question, so a refusal can be read back to its cause.

Run from the repository root:
    python testing/Developer/reports/2026-09-23_user_feedback/run_feedback_questions.py
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
OUT = pathlib.Path(__file__).parent
RUNNER = ROOT / "testing/Developer/scripts/local_loop_run.py"

QUESTIONS = [
    ("q1_reflux", "reflux disease"),
    ("q2_gerd", "GERD"),
    ("q3_trials_gerd", "Any trials for GERD?"),
    ("q4_caffeine_papers", "papers on the effects of caffeine on exercise performance"),
    ("q5_coffee_exercise", "Does coffee help make exercise more effective?"),
    ("q6_mediterranean", "Are there any beneficial variants typically found in people of mediterranean descent?"),
    ("q7_ashkenazi", "What positive and negative genes do ashkenazi jewish people have?"),
]

records = []
for key, text in QUESTIONS:
    print(f"=== {key}: {text!r}", flush=True)
    proc = subprocess.run(
        [sys.executable, str(RUNNER), text, "--no-memory", "--plain", "--summary"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=300,
    )
    (OUT / f"{key}.txt").write_text(proc.stdout + "\n--- STDERR ---\n" + proc.stderr)
    summary = None
    guard = None
    for line in proc.stdout.splitlines():
        if line.startswith("[SUMMARY] "):
            summary = json.loads(line[len("[SUMMARY] "):])
        if line.startswith("[guard] "):
            guard = json.loads(line[len("[guard] "):])
    rec = {"key": key, "question": text, "rc": proc.returncode,
           "guard": guard, "summary": summary}
    records.append(rec)
    print(json.dumps({"key": key, "guard_outcome": (guard or {}).get("outcome"),
                      "tools": [t["tool"] for t in (summary or {}).get("tools", [])],
                      "citations": len((summary or {}).get("citations", [])),
                      "trust": (summary or {}).get("trust_outcome")}), flush=True)

(OUT / "runs.jsonl").write_text("\n".join(json.dumps(r, default=str) for r in records) + "\n")
print("wrote runs.jsonl")
