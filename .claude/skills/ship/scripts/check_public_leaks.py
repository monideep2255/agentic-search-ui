#!/usr/bin/env python3
"""check_public_leaks.py - stop a push that would publish a secret or a private value.

This repository is public. Anything a push carries is world-readable and
effectively permanent, so /ship runs this scan last, before anything is pushed.
Stdlib only, no network, and it never prints a matched value in full.

What it scans, which is exactly what a push would publish:

- every added line of `git diff <base>...HEAD`, the commits not yet on the base
- every added line of the staged and unstaged diff against HEAD
- every untracked, non-ignored file, whole, because a brand new file is the
  usual leak and a diff against HEAD cannot see it
- every commit message in `<base>..HEAD`
- every author and committer email in `<base>..HEAD`

`<base>` defaults to `origin/develop` (flag `--base`).

What it looks for, one category name each:

- private-key, aws-access-key, github-token, provider-api-key, slack-token,
  google-api-key, jwt, bearer-token, url-password, secret-assignment: secrets by
  shape
- local-path: a `/Users/<name>/`, `/home/<name>/` or drive-letter users path
- personal-email: any email address that is not a documented placeholder
- identity-email: an author or committer email that is not a GitHub noreply address
- ipv4-address: an address outside loopback, broadcast and the documentation ranges
- ssh-host: `ssh <user>@<host>` with a real host

A line carrying `local-refs: allow` is exempt, the same marker the owner's
machine-local hook uses. Use it only for information that is genuinely public.

A private name or the owner's work identity cannot be listed in a public
repository, so this script also runs the owner's machine-local check when the
repository's pre-commit hook points at one. When that check is absent the script
says so and exits 1, unless `--allow-missing-private-check` is passed, so a
machine without it is never silently treated as clean.

Exit codes: 0 clean, 1 findings (or the private-name check not run), 2 could
not run at all (not a git repository, base ref not found, git failed).
"""

from __future__ import annotations

import argparse
import math
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

ALLOW_MARKER = "local-refs: allow"
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_LINE_CHARS = 20000
PRIVATE_CHECK_NAME = "private-name check"

BINARY_SUFFIXES = frozenset(
    [
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".icns",
        ".webp",
        ".bmp",
        ".tif",
        ".tiff",
        ".pdf",
        ".zip",
        ".gz",
        ".tgz",
        ".bz2",
        ".xz",
        ".7z",
        ".tar",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".eot",
        ".mp3",
        ".mp4",
        ".mov",
        ".wav",
        ".ogg",
        ".webm",
        ".parquet",
        ".pkl",
        ".pickle",
        ".sqlite",
        ".db",
        ".pyc",
        ".so",
        ".dylib",
        ".dll",
        ".exe",
        ".jar",
        ".whl",
        ".npy",
        ".npz",
        ".wasm",
    ]
)

# Words that mark a value as a stand-in and never a live secret.
PLACEHOLDER_WORDS = frozenset(
    [
        "password",
        "passwd",
        "pass",
        "secret",
        "changeme",
        "change-me",
        "example",
        "dummy",
        "fake",
        "placeholder",
        "redacted",
        "postgres",
        "admin",
        "test",
        "root",
        "token",
        "key",
        "none",
        "null",
    ]
)
PLACEHOLDER_SUBSTRINGS = (
    "example",
    "dummy",
    "fake",
    "changeme",
    "change-me",
    "placeholder",
    "redacted",
)

# Path names that are CI users, generic stand-ins or system folders, not a person.
SAFE_PATH_NAMES = frozenset(
    [
        "runner",
        "ubuntu",
        "root",
        "vsts",
        "circleci",
        "travis",
        "github",
        "docker",
        "node",
        "vscode",
        "app",
        "appuser",
        "user",
        "username",
        "you",
        "yourname",
        "name",
        "me",
        "someone",
        "example",
        "foo",
        "bar",
        "jovyan",
        "shared",
        "public",
        "default",
        "all",
        "pi",
        "build",
        "builder",
        "worker",
    ]
)

SAFE_EMAIL_DOMAINS = ("example.com", "example.org", "example.net")
# RFC 2606 reserved top level names, which can never be a real mailbox.
RESERVED_TLDS = frozenset({"invalid", "test", "example", "localhost"})
FILE_LIKE_TLDS = frozenset(
    [
        "png",
        "jpg",
        "jpeg",
        "gif",
        "svg",
        "webp",
        "ico",
        "css",
        "js",
        "jsx",
        "ts",
        "tsx",
        "py",
        "json",
        "md",
        "txt",
        "yml",
        "yaml",
        "html",
        "htm",
        "toml",
        "lock",
    ]
)
SAFE_EMAIL_LOCALS = frozenset({"noreply", "no-reply", "git"})
NOREPLY_IDENTITY_RE = re.compile(
    r"^(?:[0-9]+\+)?[A-Za-z0-9-]+@users\.noreply\.github\.com$|^noreply@github\.com$", re.IGNORECASE
)

SAFE_SSH_HOSTS = frozenset(
    {"github.com", "gitlab.com", "bitbucket.org", "localhost", "ssh.github.com"}
)
SSH_PLACEHOLDER_HOST_WORDS = ("host", "server", "remote", "machine", "vps", "your", "example")

# Literals a scanner needs are assembled from parts, so this file never contains
# the marker text that a secret scanner looks for and cannot flag itself.
_DASHES = "-" * 5
_KEY_WORDS = "PRIVATE" + " KEY"
PRIVATE_KEY_RE = re.compile(_DASHES + r"BEGIN (?:[A-Z0-9]+ )*" + _KEY_WORDS + _DASHES)
AWS_KEY_RE = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")
GITHUB_TOKEN_RE = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})\b")
PROVIDER_KEY_RE = re.compile(r"\bsk-(?:ant-|or-|proj-)?[A-Za-z0-9][A-Za-z0-9_-]{19,}")
SLACK_TOKEN_RE = re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")
GOOGLE_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")
BEARER_RE = re.compile(r"\bBearer\s+([A-Za-z0-9._~+/=-]{20,})", re.IGNORECASE)
URL_PASSWORD_RE = re.compile(
    r"\b[A-Za-z][A-Za-z0-9+.-]*://([^\s:/@<>{}$'\"]+):([^\s@/<>{}'\"]+)@[^\s/'\"]+"
)
ASSIGNMENT_RE = re.compile(
    r"([A-Za-z0-9_.-]*(?:key|secret|token|password|passwd)[A-Za-z0-9_.-]*)[\"']?\s*[:=]\s*[\"']?"
    r"([A-Za-z0-9+/=_.~-]{16,})",
    re.IGNORECASE,
)
UNIX_PATH_RE = re.compile(r"(?<![\w])/(?:Users|home)/([^/\s\"'`<>{}$()\[\]*:]+)/")
WINDOWS_PATH_RE = re.compile(
    r"(?<![\w])[A-Za-z]:[\\/]+Users[\\/]+([^\\/\s\"'`<>{}$()\[\]*:]+)[\\/]"
)
EMAIL_RE = re.compile(
    r"(?<![\w.%+-])([A-Za-z0-9][A-Za-z0-9._%+-]*)@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.([A-Za-z]{2,}))\b"
)
IPV4_RE = re.compile(r"(?<![\d.])((?:\d{1,3}\.){3}\d{1,3})(?![\d]|\.\d)")
SSH_RE = re.compile(r"\b(?:ssh|scp)\s+(?:[^\n]*?\s)?([A-Za-z0-9._<>${}-]+)@([^\s:'\"`)]+)")


@dataclass(frozen=True)
class Finding:
    where: str
    category: str
    masked: str

    def render(self) -> str:
        return f"FAIL {self.where} [{self.category}] {self.masked}"


class CannotRun(Exception):
    """The scan could not start: the message says what to do next."""


def mask(value: str) -> str:
    """Show at most the first character and the length, never the value."""
    if len(value) <= 4:
        return "***"
    return f"{value[0]}***({len(value)} chars)"


def entropy(value: str) -> float:
    counts: dict[str, int] = {}
    for char in value:
        counts[char] = counts.get(char, 0) + 1
    total = len(value)
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


def is_placeholder(value: str) -> bool:
    """True for a stand-in value: never a live secret, so it must not fire."""
    lowered = value.lower().strip("\"'")
    if len(lowered) < 8:
        return True
    if any(
        mark in lowered for mark in ("<", ">", "${", "$(", "{{", "%(", "%s")
    ) or lowered.startswith("$"):
        return True
    if lowered in PLACEHOLDER_WORDS or any(mark in lowered for mark in PLACEHOLDER_SUBSTRINGS):
        return True
    if (
        re.match(r"^(?:your|my)[-_ ]", lowered)
        or re.search(r"x{3,}", lowered)
        or re.search(r"\*{3,}", lowered)
    ):
        return True
    return len(set(lowered)) <= 2


def _mixed(value: str) -> bool:
    return any(c.isdigit() for c in value) and any(c.isalpha() for c in value)


def _ip_is_allowed(text: str) -> bool:
    parts = [int(p) for p in text.split(".")]
    if any(p > 255 for p in parts):
        return True  # not an address at all, for example a four part version number
    if text in ("127.0.0.1", "0.0.0.0", "255.255.255.255"):
        return True
    if parts[0] == 127:
        return True
    return tuple(parts[:3]) in ((192, 0, 2), (198, 51, 100), (203, 0, 113))


def _email_is_allowed(local: str, domain: str, tld: str) -> bool:
    domain_lower = domain.lower()
    if local.lower() in SAFE_EMAIL_LOCALS:
        return True
    if any(domain_lower == d or domain_lower.endswith("." + d) for d in SAFE_EMAIL_DOMAINS):
        return True
    if "noreply" in domain_lower.split(".") or "no-reply" in domain_lower.split("."):
        return True
    return tld.lower() in FILE_LIKE_TLDS or tld.lower() in RESERVED_TLDS


def scan_line(text: str) -> list[tuple[str, str]]:
    """Return (category, matched text) for every finding on one line."""
    if ALLOW_MARKER in text:
        return []
    text = text[:MAX_LINE_CHARS]
    hits: list[tuple[str, str]] = []

    def add(category: str, matched: str, *, check_placeholder: bool = True) -> None:
        if check_placeholder and is_placeholder(matched):
            return
        hits.append((category, matched))

    for match in PRIVATE_KEY_RE.finditer(text):
        add("private-key", match.group(0), check_placeholder=False)
    for match in AWS_KEY_RE.finditer(text):
        add("aws-access-key", match.group(0))
    for match in GITHUB_TOKEN_RE.finditer(text):
        add("github-token", match.group(0))
    for match in PROVIDER_KEY_RE.finditer(text):
        if any(c.isdigit() for c in match.group(0)):
            add("provider-api-key", match.group(0))
    for match in SLACK_TOKEN_RE.finditer(text):
        add("slack-token", match.group(0))
    for match in GOOGLE_KEY_RE.finditer(text):
        add("google-api-key", match.group(0))
    for match in JWT_RE.finditer(text):
        add("jwt", match.group(0))
    for match in BEARER_RE.finditer(text):
        if _mixed(match.group(1)):
            add("bearer-token", match.group(1))
    for match in URL_PASSWORD_RE.finditer(text):
        add("url-password", match.group(2))
    shaped = [matched for _, matched in hits]
    for match in ASSIGNMENT_RE.finditer(text):
        value = match.group(2)
        if any(value in earlier for earlier in shaped):
            continue
        if _mixed(value) and entropy(value) >= 3.3:
            add("secret-assignment", value)

    for match in UNIX_PATH_RE.finditer(text):
        if match.group(1).lower() not in SAFE_PATH_NAMES:
            add("local-path", match.group(0), check_placeholder=False)
    for match in WINDOWS_PATH_RE.finditer(text):
        if match.group(1).lower() not in SAFE_PATH_NAMES:
            add("local-path", match.group(0), check_placeholder=False)

    for match in EMAIL_RE.finditer(text):
        if not _email_is_allowed(match.group(1), match.group(2), match.group(3)):
            add("personal-email", match.group(0), check_placeholder=False)
    for match in IPV4_RE.finditer(text):
        if not _ip_is_allowed(match.group(1)):
            add("ipv4-address", match.group(1), check_placeholder=False)
    for match in SSH_RE.finditer(text):
        host = match.group(2).lower().rstrip(".,;")
        if host in SAFE_SSH_HOSTS or any(mark in host for mark in "<>${}[]"):
            continue
        if any(word in host for word in SSH_PLACEHOLDER_HOST_WORDS) and "." not in host:
            continue
        add("ssh-host", match.group(0), check_placeholder=False)
    return hits


def _dedupe(findings: Iterable[Finding]) -> list[Finding]:
    seen: set[tuple[str, str, str]] = set()
    out: list[Finding] = []
    for finding in findings:
        key = (finding.where, finding.category, finding.masked)
        if key not in seen:
            seen.add(key)
            out.append(finding)
    return out


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if check and result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip().splitlines()
        raise CannotRun(
            f"git {args[0]} failed ({detail[0] if detail else 'no message'}). "
            "Run the scan from inside the repository."
        )
    return result


def repo_root(start: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True,
            check=False,
        )
    except OSError as error:
        raise CannotRun(
            f"git could not run ({error.strerror}). Install git or fix the PATH."
        ) from error
    if result.returncode != 0:
        raise CannotRun(
            "this is not a git repository. Run the scan from inside the repository you are about to push."
        )
    return Path(result.stdout.decode("utf-8", "replace").strip())


def check_base(root: Path, base: str) -> None:
    result = _git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}", check=False)
    if result.returncode != 0:
        raise CannotRun(
            f"base ref '{base}' was not found. Run `git fetch origin` or pass an existing ref with --base."
        )


def _is_binary_name(path: str) -> bool:
    return Path(path).suffix.lower() in BINARY_SUFFIXES


HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def parse_added_lines(diff_text: str) -> dict[str, list[tuple[int, str]]]:
    """Map each file to its added (line number, text) pairs from a -U0 diff."""
    files: dict[str, list[tuple[int, str]]] = {}
    current: str | None = None
    remaining = 0
    line_no = 0
    for raw in diff_text.split("\n"):
        if remaining > 0 and raw.startswith("+"):
            if current is not None:
                files.setdefault(current, []).append((line_no, raw[1:]))
            line_no += 1
            remaining -= 1
            continue
        if raw.startswith("\\") or (remaining > 0 and raw.startswith("-")):
            continue
        remaining = 0
        if raw.startswith("+++ "):
            name = raw[4:].split("\t")[0]
            if name == "/dev/null":
                current = None
            else:
                name = name.strip('"')
                current = name.removeprefix("b/")
                files.setdefault(current, [])
            continue
        match = HUNK_RE.match(raw)
        if match:
            line_no = int(match.group(1))
            remaining = int(match.group(2)) if match.group(2) is not None else 1
    return files


def _file_bytes(root: Path, rel: str, lines: list[tuple[int, str]]) -> int:
    added = sum(len(text.encode("utf-8", "replace")) + 1 for _, text in lines)
    try:
        return max(added, os.path.getsize(root / rel))
    except OSError:
        return added


@dataclass
class ScanReport:
    findings: list[Finding]
    not_scanned: list[str]
    binary_skipped: int
    lines_scanned: int
    commits: int


def _scan_added(
    root: Path, label: str, files: dict[str, list[tuple[int, str]]], report: ScanReport
) -> None:
    for rel, lines in sorted(files.items()):
        if not lines:
            continue
        if _is_binary_name(rel):
            report.binary_skipped += 1
            continue
        if _file_bytes(root, rel, lines) > MAX_FILE_BYTES:
            report.not_scanned.append(f"{rel} (larger than 2 MB, {label})")
            continue
        for number, text in lines:
            report.lines_scanned += 1
            for category, matched in scan_line(text):
                report.findings.append(Finding(f"{rel}:{number}", category, mask(matched)))


def _scan_untracked(root: Path, report: ScanReport) -> None:
    listing = _git(root, "ls-files", "--others", "--exclude-standard", "-z")
    for rel in listing.stdout.decode("utf-8", "replace").split("\0"):
        if not rel:
            continue
        path = root / rel
        if _is_binary_name(rel):
            report.binary_skipped += 1
            continue
        try:
            if path.is_symlink() or not path.is_file():
                continue
            if path.stat().st_size > MAX_FILE_BYTES:
                report.not_scanned.append(f"{rel} (larger than 2 MB, untracked)")
                continue
            data = path.read_bytes()
        except OSError:
            report.not_scanned.append(f"{rel} (unreadable, untracked)")
            continue
        if b"\0" in data[:8192]:
            report.binary_skipped += 1
            continue
        for number, text in enumerate(data.decode("utf-8", "replace").split("\n"), start=1):
            report.lines_scanned += 1
            for category, matched in scan_line(text):
                report.findings.append(Finding(f"{rel}:{number}", category, mask(matched)))


def _scan_commits(root: Path, base: str, report: ScanReport) -> None:
    fmt = "%H%x1f%ae%x1f%ce%x1f%B%x1e"
    result = _git(root, "log", f"--format={fmt}", f"{base}..HEAD")
    for record in result.stdout.decode("utf-8", "replace").split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        sha, author, committer, message = record.split("\x1f", 3)
        report.commits += 1
        short = sha[:8]
        for role, email in (("author", author), ("committer", committer)):
            if email and not NOREPLY_IDENTITY_RE.match(email):
                report.findings.append(
                    Finding(f"commit {short} {role}-email", "identity-email", mask(email))
                )
        for number, text in enumerate(message.split("\n"), start=1):
            report.lines_scanned += 1
            for category, matched in scan_line(text):
                report.findings.append(
                    Finding(f"commit {short} message:{number}", category, mask(matched))
                )


def run_scan(root: Path, base: str) -> ScanReport:
    check_base(root, base)
    report = ScanReport([], [], 0, 0, 0)
    range_diff = _git(
        root, "diff", "--no-color", "--no-ext-diff", "--no-renames", "-U0", f"{base}...HEAD"
    )
    _scan_added(
        root, "commits", parse_added_lines(range_diff.stdout.decode("utf-8", "replace")), report
    )
    work_diff = _git(
        root, "diff", "--no-color", "--no-ext-diff", "--no-renames", "-U0", "HEAD", check=False
    )
    if work_diff.returncode == 0:
        _scan_added(
            root,
            "working tree",
            parse_added_lines(work_diff.stdout.decode("utf-8", "replace")),
            report,
        )
    _scan_untracked(root, report)
    _scan_commits(root, base, report)
    report.findings = _dedupe(report.findings)
    return report


def _redact(text: str) -> str:
    """Keep the owner's home directory and user name out of relayed output."""
    home = Path.home()
    text = text.replace(str(home), "<user-home>")
    if len(home.name) > 2:
        text = text.replace(f"/{home.name}/", "/<user>/")
    return text


def locate_private_check(root: Path) -> tuple[list[str] | None, str]:
    """Find the machine-local check from the hook's exec line, never a fixed path.

    Returns (command, reason). The command is None when the check cannot run, and
    the reason then says why, without naming any path.
    """
    hook_result = _git(root, "rev-parse", "--git-path", "hooks/pre-commit", check=False)
    if hook_result.returncode != 0:
        return None, "git could not locate the pre-commit hook"
    hook = Path(hook_result.stdout.decode("utf-8", "replace").strip())
    if not hook.is_absolute():
        hook = root / hook
    if not hook.is_file():
        return None, "no pre-commit hook is installed in this repository"
    try:
        lines = hook.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None, "the pre-commit hook could not be read"
    for line in lines:
        try:
            tokens = shlex.split(line, comments=True)
        except ValueError:
            continue
        if len(tokens) >= 2 and tokens[0] == "exec":
            scripts = [t for t in tokens[1:] if t.endswith(".py")]
            if not scripts:
                continue
            script = Path(scripts[0]).expanduser()
            if not script.is_file():
                return None, "the script named by the pre-commit hook does not exist"
            interpreter = tokens[1] if tokens[1] != scripts[0] else "python3"
            return [interpreter, str(script), "--staged"], ""
    return None, "the pre-commit hook has no exec line that names a Python check"


def run_private_check(root: Path) -> tuple[str, list[str]]:
    """Return ("pass" | "findings" | "not-run", output lines)."""
    command, reason = locate_private_check(root)
    if command is None:
        return "not-run", [reason]
    try:
        result = subprocess.run(
            command, cwd=root, capture_output=True, text=True, check=False, timeout=120
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return "not-run", [f"the check could not start ({type(error).__name__})"]
    output = [
        _redact(line) for line in (result.stdout + result.stderr).splitlines() if line.strip()
    ]
    if result.returncode == 0:
        return "pass", output[:3]
    if result.returncode == 1:
        return "findings", output
    return "not-run", [
        f"the check exited {result.returncode} (it could not check); run it by hand",
        *output[:2],
    ]


def main(argv: list[str] | None = None, cwd: Path | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan what a push would publish for secrets and private values."
    )
    parser.add_argument(
        "--base",
        default="origin/develop",
        help="the ref the push would be added to (default origin/develop)",
    )
    parser.add_argument(
        "--allow-missing-private-check",
        action="store_true",
        help="do not fail when the machine-local private-name check is absent",
    )
    args = parser.parse_args(argv)

    try:
        root = repo_root(cwd or Path.cwd())
        report = run_scan(root, args.base)
    except CannotRun as error:
        print(f"CANNOT RUN: {error}", file=sys.stderr)
        return 2

    for finding in report.findings:
        print(finding.render())
    for item in report.not_scanned:
        print(f"NOT SCANNED {item}")
    exit_code = 1 if report.findings else 0

    status, private_lines = run_private_check(root)
    if status == "pass":
        print(f"{PRIVATE_CHECK_NAME}: PASS (machine-local check ran on the staged diff)")
    elif status == "findings":
        for line in private_lines:
            print(f"{PRIVATE_CHECK_NAME}: {line}")
        exit_code = 1
    else:
        print(f"{PRIVATE_CHECK_NAME} NOT RUN on this machine: {'; '.join(private_lines)}")
        if not args.allow_missing_private_check:
            print(
                "A push from a machine without it is unchecked for private names. "
                "Run it where the check exists, or pass --allow-missing-private-check."
            )
            exit_code = 1

    print(
        f"scanned {report.lines_scanned} lines and {report.commits} commit(s) against {args.base}; "
        f"{len(report.findings)} finding(s), {len(report.not_scanned)} file(s) not scanned, "
        f"{report.binary_skipped} binary file(s) skipped by name"
    )
    if report.findings:
        print(
            "BLOCKED: remove each line, or mark a genuinely public one with "
            f"`{ALLOW_MARKER}` on the same line. A finding in an already pushed commit needs the owner."
        )
    elif exit_code == 0:
        print("PASS: nothing to publish looks like a secret or a private value.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
