"""Copy the audit's evidence into the report folder with local paths scrubbed,
then scan the destination for anything that must not be committed."""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parent
REPO = Path(sys.argv[1])
DEST = REPO / "testing/Developer/reports/2026-09-26_integrations_audit"
EV = DEST / "evidence"
(EV / "runs").mkdir(parents=True, exist_ok=True)
(EV / "scripts").mkdir(parents=True, exist_ok=True)

LITERAL = [(str(SCRATCH), "<scratch>"), (str(REPO), "<repo-root>")]
REGEX = [
    ("/" + r"(?:private/)?var/folders/[^\s'\"]*", "<tmp>"),
    ("/" + r"Users/[^\s\"']+", "<home-path>"),
    (r"s3-consistency-[ab]-20260926int@example\.com", "<throwaway-email>"),
]


def scrub(text: str) -> str:
    for old, new in LITERAL:
        text = text.replace(old, new)
    for pat, new in REGEX:
        text = re.sub(pat, new, text)
    return text


files = {
    "unauth_probes.out": "unauth_probes.out",
    "page_snippets_as_copied.txt": "page_snippets_as_copied.txt",
    "mcp_no_cost.out": "mcp_no_cost.out",
    "cli_no_cost.out": "cli_no_cost.out",
    "s3_import_probe.out": "s3_import_probe.out",
    "pypi_names.out": "pypi_names.out",
    "missing_packages.txt": "wheel_missing_packages.txt",
    "kgx_fix_probe.out": "kgx_fix_probe.out",
    "adapter_tests.out": "adapter_tests.out",
    "parity_runs.out": "parity_runs.out",
    "parity_summary.json": "parity_summary.json",
    "history_feedback.out": "history_feedback.out",
    "event_types_and_links.out": "event_types_and_links.out",
    "old_client_compat.out": "old_client_compat.out",
    "resume_probe.out": "resume_probe.out",
    "smoke_run_1.out": "smoke_run_1.out",
    "smoke_negative.out": "smoke_negative.out",
    "smoke_run_2.out": "smoke_run_2_relative_path_bug.out",
    "smoke_run_3.out": "smoke_run_3_final.out",
    "question_count.log": "question_count.log",
}
for src, dst in files.items():
    p = HERE / src
    if p.exists():
        (EV / dst).write_text(scrub(p.read_text()))
for p in sorted((HERE / "runs").glob("*.json")):
    (EV / "runs" / p.name).write_text(scrub(p.read_text()))
for name in ("live_lib.py", "parity_runs.py", "mcp_no_cost.py", "cli_no_cost.py", "history_feedback.py",
             "old_client_compat.py", "s3_import_probe.py", "resume_probe.py", "run_adapter_tests.sh"):
    (EV / "scripts" / name).write_text(scrub((HERE / name).read_text()))
# This script holds no path of its own, and scrubbing it would rewrite its patterns.
shutil.copyfile(HERE / "publish_evidence.py", EV / "scripts" / "publish_evidence.py")
shutil.copyfile(HERE / "integrations_smoke.py", DEST / "integrations_smoke.py")

# Scan everything written.
bad = []
patterns = {
    "JWT-shaped token": r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    "bearer value": r"Bearer (?!\$TOKEN|\{tok|\{token|\{guest|\{account|\$\{|<)[A-Za-z0-9._-]{16,}",
    "home path": "/" + "Users/",
    "scratch path": "/" + r"private/(?:tmp|var)|" + "/" + "var/folders",
    "example.com email": r"[A-Za-z0-9._-]+@example\.com",
    "refresh token key with value": r'"(?:a|b)_refresh"\s*:\s*"',
}
for f in DEST.rglob("*"):
    if f.is_file():
        text = f.read_text(errors="replace")
        for label, pat in patterns.items():
            for m in re.finditer(pat, text):
                bad.append(f"{f.relative_to(DEST)}: {label}: {text[max(0, m.start() - 30):m.end() + 10]!r}")
print(f"wrote {sum(1 for f in DEST.rglob('*') if f.is_file())} files under {DEST.relative_to(REPO)}")
print("scan findings:", len(bad))
for b in bad[:40]:
    print("  ", b)
