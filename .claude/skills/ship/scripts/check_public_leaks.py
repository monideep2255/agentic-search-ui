#!/usr/bin/env python3
"""check_public_leaks.py - stop a push that would publish a secret or a private value.

This repository is public. Anything a push carries is world-readable and
effectively permanent, so /ship runs this scan last, before anything is pushed.
Stdlib only. It never prints a matched value, a line of content, or another
tool's raw output: only a location, a category and a mask (first character and
length).

What it reads, which is what a push would publish plus what the next commit
would carry:

- It fetches the base first (`origin/develop` by default, flag `--base`), so a
  stale or force-pushed remote cannot hide a commit. `--no-fetch` skips that.
- EVERY commit in `<base>..HEAD`, one at a time: every added line, the name of
  every file it adds, its message, and its author and committer email. A value
  added in one commit and deleted in a later one is still in the history a
  push sends, so it is still a finding, reported against the commit that added
  it. A merge commit is read through its remerge diff, so a change made only
  while resolving the merge is read too.
- The staged diff, the unstaged diff, and every untracked file git does not
  ignore, whole, with its name.

Nothing passes unread:

- No line is cut short. A very long line is read in overlapping windows.
- `.gitattributes` cannot hide a file: diffs run with `--no-textconv`, and any
  file git calls binary is read from its blob and judged by its content, not
  its name or its attributes. UTF-16 and text with a stray NUL byte are decoded
  and read. A genuinely binary file (an image, an archive, a database) has its
  printable text runs read, and is also listed as "not scanned: a person must
  look at it", because the scan cannot read a picture.
- A text file over 2 MB is a failure, exit 1, never a pass: shrink or split it.

What it looks for, one category name each:

- Secrets by shape: private-key (PEM and PGP), aws-access-key, github-token,
  provider-api-key, stripe-key, gitlab-token, huggingface-token, npm-token,
  slack-token, slack-webhook, discord-webhook, google-api-key, jwt,
  bearer-token, basic-auth, url-password (any length that is not a
  placeholder), secret-assignment, password-assignment.
- Private values: local-path (home directories with or without a trailing
  slash, the dash-encoded `-Users-<name>-` form, WSL, home-relative paths into
  the Desktop, Documents or Downloads folder, pytest's `pytest-of-<name>`),
  personal-email,  identity-email (an author or committer email that is not a GitHub noreply
  address), ipv4-address, ipv6-address, ssh-host (including a `git@` remote on
  a host that is not a public forge), internal-host.

Author and committer DISPLAY NAMES are not scanned: the owner's name is public,
and a list of other names cannot live in a public file. Annotated tag messages
are not scanned either, since /ship does not push tags.

A line carrying `local-refs: allow` is exempt from the private-value categories
on that physical line only, whatever its line endings. It never exempts a
secret: a secret can only be removed.

A private name, the owner's work identity or an employer-internal term cannot
be listed in a public file, so this script also runs the owner's machine-local
check, `verify_no_local_refs.py`, when the repository's pre-commit hook `exec`
line names a script of exactly that name. It runs it twice: with `--message`
over every line this scan read (commits, names, messages, working tree,
untracked files), and with `--all` over the whole tracked tree. Only its verdict
and its own check names are printed, mapped back to this scan's locations. When
the check is absent, is not that script, or cannot run, the scan says so and
exits 1, unless `--allow-missing-private-check` is passed.

Exit codes: 0 clean, 1 a finding, a file too large to scan, or the private-name
check not run, 2 the scan could not run (not a git repository, base missing,
fetch failed, git timed out, or an internal error). Exit 2 is never a finding.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import ipaddress
import math
import os
import re
import shlex
import subprocess
import sys
import tempfile
import urllib.parse
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

ALLOW_MARKER = "local-refs: allow"
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_BINARY_BYTES = 16 * 1024 * 1024
WINDOW = 8192
OVERLAP = 1024
GIT_TIMEOUT = 180
FETCH_TIMEOUT = 90
PRIVATE_TIMEOUT = 600
PRIVATE_CHECK_NAME = "private-name check"
PRIVATE_SCRIPT_NAME = "verify_no_local_refs.py"
COMMIT_SENTINEL = "\x00leakscan-commit "
ZERO_BLOB = re.compile(r"^0+$")

# Categories a `local-refs: allow` marker can never exempt.
SECRET_CATEGORIES = frozenset(
    [
        "private-key",
        "aws-access-key",
        "github-token",
        "provider-api-key",
        "stripe-key",
        "gitlab-token",
        "huggingface-token",
        "npm-token",
        "slack-token",
        "slack-webhook",
        "discord-webhook",
        "google-api-key",
        "jwt",
        "bearer-token",
        "basic-auth",
        "url-password",
        "secret-assignment",
        "password-assignment",
    ]
)

# Binary kinds a person has to look at: the scan cannot read a picture or an archive.
IMAGE_OR_ARCHIVE_SUFFIXES = frozenset(
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
        ".heic",
        ".pdf",
        ".zip",
        ".gz",
        ".tgz",
        ".bz2",
        ".xz",
        ".7z",
        ".tar",
        ".jar",
        ".whl",
        ".mp3",
        ".mp4",
        ".mov",
        ".wav",
        ".webm",
    ]
)

# Words that mark a value as a stand-in and never a live secret.
PLACEHOLDER_WORDS = frozenset(
    [
        "password",
        "passwd",
        "pass",
        "pwd",
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
        "hunter2",
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
    # Test sentinels this repository writes on purpose, such as a leak canary.
    "sentinel",
    "do-not-leak",
    "not-a-real",
    "secret",
    "passw",
)

# Home-directory names that are CI users, system accounts or stand-ins, not a person.
SAFE_PATH_NAMES = frozenset(
    [
        "runner",
        "runneradmin",
        "ubuntu",
        "debian",
        "centos",
        "fedora",
        "ec2-user",
        "azureuser",
        "opc",
        "root",
        "vsts",
        "agent",
        "circleci",
        "travis",
        "jenkins",
        "gitlab-runner",
        "github",
        "git",
        "docker",
        "node",
        "vscode",
        "codespace",
        "coder",
        "vagrant",
        "linuxbrew",
        "postgres",
        "nobody",
        "www-data",
        "app",
        "appuser",
        "admin",
        "dev",
        "user",
        "username",
        "you",
        "yourname",
        "your-name",
        "your_name",
        "name",
        "me",
        "someone",
        "example",
        "foo",
        "bar",
        "jovyan",
        "shared",
        "public",
        "guest",
        "default",
        "defaultuser",
        "all",
        "pi",
        "build",
        "builder",
        "worker",
    ]
)

SAFE_EMAIL_DOMAINS = (
    "example.com",
    "example.org",
    "example.net",
    "email.com",
    "domain.com",
    "yourdomain.com",
    "your-domain.com",
    "company.com",
    "yourcompany.com",
)
# RFC 2606 reserved top level names, which can never be a real mailbox or host.
RESERVED_TLDS = frozenset({"invalid", "test", "example", "localhost"})
# File extensions that follow an `@` in asset names (`logo@2x.png`). `.md` and
# `.py` are left out on purpose: they are real country domains.
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
        "json",
        "txt",
        "yml",
        "yaml",
        "html",
        "htm",
        "toml",
        "lock",
    ]
)
NOREPLY_LOCALS = frozenset({"noreply", "no-reply", "donotreply", "do-not-reply"})
NOREPLY_DOMAINS = ("noreply.github.com", "users.noreply.gitlab.com")
# Stand-in mailbox names written in documentation and tests.
PLACEHOLDER_EMAIL_LOCALS = frozenset(
    [
        "you",
        "your",
        "yourname",
        "your.name",
        "your-name",
        "my",
        "me",
        "name",
        "user",
        "username",
        "someone",
        "somebody",
        "jane.doe",
        "john.doe",
        "first.last",
        "firstname.lastname",
        "test",
        "tester",
        "x",
        "foo",
        "bar",
        "email",
        "mail",
    ]
)
# Role and service mailboxes: an organisation's public address, never a person.
ROLE_EMAIL_LOCALS = frozenset(
    [
        "support",
        "help",
        "helpdesk",
        "info",
        "contact",
        "hello",
        "feedback",
        "security",
        "privacy",
        "abuse",
        "postmaster",
        "hostmaster",
        "webmaster",
        "press",
        "media",
        "team",
        "office",
        "enquiries",
        "inquiries",
        "questions",
        "editor",
        "editors",
        "publications",
        "accessibility",
        "legal",
        "eutilities",
        "pubmed",
        "blast",
    ]
)
NOREPLY_IDENTITY_RE = re.compile(
    r"^(?:[0-9]+\+)?[A-Za-z0-9-]+@users\.noreply\.github\.com$|^noreply@github\.com$", re.IGNORECASE
)
PUBLIC_FORGES = frozenset(
    {
        "github.com",
        "ssh.github.com",
        "gitlab.com",
        "bitbucket.org",
        "codeberg.org",
        "ssh.dev.azure.com",
        "vs-ssh.visualstudio.com",
        "git.sr.ht",
        "hf.co",
        "huggingface.co",
    }
)
SAFE_SSH_HOSTS = PUBLIC_FORGES | {"localhost"}
SSH_PLACEHOLDER_HOST_WORDS = ("host", "server", "remote", "machine", "vps", "your", "example")
INTERNAL_HOST_LABELS = frozenset({"internal", "intranet", "corp", "lan", "localdomain"})

# Literals a scanner needs are assembled from parts, so this file never contains
# the marker text that a secret scanner looks for and cannot flag itself.
_DASHES = "-" * 5
_KEY_WORDS = "PRIVATE" + " KEY"
PRIVATE_KEY_RE = re.compile(
    _DASHES + r"BEGIN (?:[A-Z0-9]+ )*" + _KEY_WORDS + r"(?: BLOCK)?" + _DASHES
)
AWS_KEY_RE = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")
GITHUB_TOKEN_RE = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})\b")
PROVIDER_KEY_RE = re.compile(r"\bsk-(?:ant-|or-|proj-)?[A-Za-z0-9][A-Za-z0-9_-]{19,}")
STRIPE_KEY_RE = re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}")
GITLAB_TOKEN_RE = re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}")
HUGGINGFACE_TOKEN_RE = re.compile(r"\bhf_[A-Za-z0-9]{30,}")
NPM_TOKEN_RE = re.compile(r"\bnpm_[A-Za-z0-9]{36,}")
SLACK_TOKEN_RE = re.compile(r"\bxox[abprse]-[A-Za-z0-9-]{10,}")
SLACK_WEBHOOK_RE = re.compile(
    r"https://hooks\.slack\.com/(?:services|workflows|triggers)/[A-Za-z0-9_/-]{20,}"
)
DISCORD_WEBHOOK_RE = re.compile(
    r"https://(?:(?:ptb|canary)\.)?discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9_-]{20,}"
)
GOOGLE_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")
BEARER_RE = re.compile(r"\bBearer\s+([A-Za-z0-9._~+/=-]{20,})", re.IGNORECASE)
BASIC_AUTH_RE = re.compile(r"\bBasic\s+([A-Za-z0-9+/]{8,}={0,2})(?![A-Za-z0-9+/=])")
URL_PASSWORD_RE = re.compile(
    r"\b[A-Za-z][A-Za-z0-9+.-]*://([^\s:/@<>{}$'\"]*):([^\s@<>{}'\"]+)@([^\s/'\"@<>]+)"
)
_SECRET_NAME = r"[A-Za-z0-9_.-]*(?:key|secret|token|password|passwd|passphrase|credential|auth|pwd)[A-Za-z0-9_.-]*"
_PASSWORD_NAME = r"[A-Za-z0-9_.-]*(?:password|passwd|passphrase|pwd)[A-Za-z0-9_.-]*"
ASSIGNMENT_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])(" + _SECRET_NAME + r")[\"']?\s*(?:=>|[:=])\s*[\"']?"
    r"([A-Za-z0-9+/=_.~-]{16,})",
    re.IGNORECASE,
)
PASSWORD_QUOTED_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])(" + _PASSWORD_NAME + r")[\"']?\s*(?:=>|[:=])\s*([\"'])([^\"'\s]{8,})\2",
    re.IGNORECASE,
)
PASSWORD_BARE_RE = re.compile(
    r"^\s*(?:export\s+)?(" + _PASSWORD_NAME + r")(=|\s*:\s*)([^\s\"'#;,]{8,})\s*(?:#.*)?$",
    re.IGNORECASE,
)
_NAME = r"[^/\\\s\"'`<>{}$()\[\]*:;,|%]+"
UNIX_PATH_RE = re.compile(
    r"(?<![\w.-])/(?:Users|home)/(?:(" + _NAME + r"(?: " + _NAME + r")+)(?=/)|(" + _NAME + r"))"
)
_HOME_WORD = "Us" + "ers"  # split so this file never reads as a home path itself
WSL_PATH_RE = re.compile(
    r"(?<![\w.-])/mnt/[A-Za-z]/" + _HOME_WORD + "/(" + _NAME + r")", re.IGNORECASE
)
WINDOWS_PATH_RE = re.compile(r"(?<![\w])[A-Za-z]:[\\/]+Users[\\/]+(" + _NAME + r")", re.IGNORECASE)
DASH_PATH_RE = re.compile(r"(?<![\w-])-(?:Users|home)-([A-Za-z0-9_.]+)-")
HOME_RELATIVE_RE = re.compile(r"(?<![\w/])(?:~|\$HOME|\$\{HOME\})/(?:Desktop|Documents|Downloads)/")
PYTEST_TMP_RE = re.compile(r"\bpytest-of-([A-Za-z0-9_.-]+)")
EMAIL_RE = re.compile(
    r"(?<![\w.%+-])([A-Za-z0-9][A-Za-z0-9._%+-]*)@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.([A-Za-z]{2,}))\b"
)
IPV4_RE = re.compile(r"(?<![\w.])((?:\d{1,3}\.){3}\d{1,3})(?!\d|\.\d)")
IPV6_RE = re.compile(r"(?<![\w:.])((?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4})(?![\w:.])")
SSH_RE = re.compile(r"\b(?:ssh|scp)\s+(?:[^\n]*?\s)?([A-Za-z0-9._<>${}-]+)@([^\s:'\"`)]+)")
URL_HOST_RE = re.compile(
    r"\b[A-Za-z][A-Za-z0-9+.-]*://(?:[^\s/@'\"<>]*@)?([A-Za-z0-9.-]+\.[A-Za-z0-9-]+)"
)
SVG_ATTR_RE = re.compile(r"\b(?:d|points|viewBox|transform)\s*=\s*([\"'])(.*?)\1", re.DOTALL)
SECTION_WORD_RE = re.compile(
    r"(?:section|sections|§|step|steps|chapter|clause|appendix|version|python|rule|item|table|figure)\s*$",
    re.IGNORECASE,
)
NAMESPACED_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:[._:-][a-z0-9]+)+$")
UPPER_SNAKE_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")
LOWER_WORDS_RE = re.compile(r"^[a-z]+(?:[-_.][a-z]+)*$")
DOTTED_IDENTIFIER_RE = re.compile(r"^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*$")
FILE_NAME_RE = re.compile(
    r"\.(?:py|md|json|ts|tsx|js|jsx|txt|yml|yaml|html|css|sh|toml|cfg|ini)$", re.IGNORECASE
)
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
INDEX_RE = re.compile(r"^index ([0-9a-f,]+)\.\.([0-9a-f]+)")
LINE_BREAK_RE = re.compile(r"\r\n|\r|\n")
# Characters str.splitlines() treats as line ends; the private check's file must keep one line per unit.
SPLITLINES_CHARS = re.compile("[\n\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029]")


@dataclass(frozen=True)
class Unit:
    """One line of outgoing text and where it comes from."""

    kind: str  # "content", "name", "message", "binary"
    source: str  # "commit", "staged", "working tree", "untracked"
    commit: str | None
    path: str | None
    line: int
    text: str


@dataclass
class Finding:
    unit: Unit | None
    category: str
    masked: str
    where_override: str | None = None


@dataclass
class ScanReport:
    units: list[Unit] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    too_large: list[tuple[Unit, int]] = field(default_factory=list)
    binaries: list[Unit] = field(default_factory=list)
    commits: int = 0
    identity: list[tuple[str, str, str]] = field(default_factory=list)


class CannotRun(Exception):
    """The scan could not start or finish: the message says what to do next."""


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


def _is_stand_in(lowered: str) -> bool:
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


def is_placeholder(value: str) -> bool:
    """True for a stand-in value: never a live secret, so it must not fire."""
    lowered = value.lower().strip("\"'")
    if len(lowered) < 8:
        return True
    return _is_stand_in(lowered)


def _mixed(value: str) -> bool:
    return any(c.isdigit() for c in value) and any(c.isalpha() for c in value)


def _url_password_is_placeholder(user: str, password: str) -> bool:
    lowered = password.lower()
    if lowered == user.lower() and user:
        return True  # a local default such as app:app
    if re.match(r"^\d+(?:/|$)", password):
        return True  # a port followed by a path, not a password
    return _is_stand_in(lowered)


def _ip_is_allowed(text: str, line: str, start: int, end: int, svg: list[tuple[int, int]]) -> bool:
    parts = [int(p) for p in text.split(".")]
    if any(p > 255 for p in parts):
        return True  # not an address at all, for example a four part version number
    if parts[0] in (0, 127) or text == "255.255.255.255":
        return True
    if tuple(parts[:3]) in ((192, 0, 2), (198, 51, 100), (203, 0, 113)):
        return True
    if all(p < 10 for p in parts):
        return True  # a section or version number such as 5.2.2.3, or 1.1.1.1 public DNS
    if parts[3] in (0, 255):
        return True  # a network or broadcast address names a range, not a host (10.0.0.0/8)
    if any(s <= start and end <= e for s, e in svg):
        return True  # SVG path data
    return bool(SECTION_WORD_RE.search(line[max(0, start - 20) : start]))


def _ipv6_is_finding(text: str) -> bool:
    if len([g for g in text.split(":") if g]) < 3:
        return False
    try:
        address = ipaddress.IPv6Address(text)
    except ValueError:
        return False
    if (
        address.is_loopback
        or address.is_unspecified
        or address.is_link_local
        or address.is_multicast
    ):
        return False
    return address not in ipaddress.IPv6Network("2001:db8::/32")


def _host_is_reserved(host: str) -> bool:
    labels = host.lower().split(":")[0].rstrip(".").split(".")
    return labels[-1] in RESERVED_TLDS - {"localhost"} or "example" in labels


def _host_is_internal(host: str) -> bool:
    labels = host.lower().rstrip(".").split(".")
    if len(labels) < 2 or labels[-1] in RESERVED_TLDS or "example" in labels:
        return False
    return labels[-1] == "local" or any(label in INTERNAL_HOST_LABELS for label in labels)


def _email_category(local: str, domain: str, tld: str) -> str | None:
    """The category an address falls in, or None when it is not personal."""
    local_lower = local.lower()
    domain_lower = domain.lower()
    if tld.lower() in FILE_LIKE_TLDS:
        # `name@gmail.com.txt` is an address followed by an extension; `logo@2x.png` is not.
        stripped = domain_lower.rsplit(".", 1)[0]
        if "." not in stripped or not re.search(r"\.[a-z]{2,}$", stripped):
            return None
        domain_lower = stripped
        tld = stripped.rsplit(".", 1)[1]
    if tld.lower() in RESERVED_TLDS:
        return None
    if local_lower == "git":
        return None if domain_lower in PUBLIC_FORGES else "ssh-host"
    if _host_is_internal(domain_lower):
        return "internal-host"
    if local_lower in NOREPLY_LOCALS:
        return None
    if any(domain_lower == d or domain_lower.endswith("." + d) for d in NOREPLY_DOMAINS):
        return None
    if any(domain_lower == d or domain_lower.endswith("." + d) for d in SAFE_EMAIL_DOMAINS):
        return None
    if local_lower in PLACEHOLDER_EMAIL_LOCALS or local_lower in ROLE_EMAIL_LOCALS:
        return None
    return "personal-email"


def _svg_spans(text: str) -> list[tuple[int, int]]:
    if "=" not in text:
        return []
    return [(m.start(2), m.end(2)) for m in SVG_ATTR_RE.finditer(text)]


def _basic_auth_value(encoded: str) -> str | None:
    try:
        decoded = base64.b64decode(encoded + "=" * (-len(encoded) % 4), validate=True)
    except (binascii.Error, ValueError):
        return None
    try:
        text = decoded.decode("ascii")
    except UnicodeDecodeError:
        return None
    if ":" not in text or not text.isprintable():
        return None
    user, password = text.split(":", 1)
    if not password or _url_password_is_placeholder(user, password):
        return None
    return encoded


def _secret_assignment_ok(name: str, value: str) -> bool:
    """True when a high-entropy assignment looks like a live value."""
    if not (_mixed(value) and entropy(value) >= 3.3):
        return False
    if NAMESPACED_ID_RE.match(value) or UPPER_SNAKE_RE.match(value):
        return False  # a storage key name or an environment variable name
    if re.match(r"^sha(?:256|384|512)-", value):
        return False  # a subresource integrity hash
    if FILE_NAME_RE.search(name):
        return False  # a manifest keyed by file name
    lowered = name.lower()
    return not (
        re.fullmatch(r"[0-9a-f]{32,}", value)
        and any(w in lowered for w in ("hash", "sha", "digest", "checksum", "fingerprint", "etag"))
    )


def _password_ok(value: str) -> bool:
    # A lower-case word run such as current-password is a field name, not a password,
    # and `postgresql://` beside a key named url-password is a scheme.
    return not is_placeholder(value) and not LOWER_WORDS_RE.match(value) and "://" not in value


def _scan_window(text: str, hits: list[tuple[str, str]]) -> None:
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
    for regex, category in (
        (STRIPE_KEY_RE, "stripe-key"),
        (GITLAB_TOKEN_RE, "gitlab-token"),
        (HUGGINGFACE_TOKEN_RE, "huggingface-token"),
        (NPM_TOKEN_RE, "npm-token"),
        (SLACK_TOKEN_RE, "slack-token"),
        (SLACK_WEBHOOK_RE, "slack-webhook"),
        (DISCORD_WEBHOOK_RE, "discord-webhook"),
        (GOOGLE_KEY_RE, "google-api-key"),
        (JWT_RE, "jwt"),
    ):
        for match in regex.finditer(text):
            add(category, match.group(0))
    for match in BEARER_RE.finditer(text):
        if _mixed(match.group(1)):
            add("bearer-token", match.group(1))
    for match in BASIC_AUTH_RE.finditer(text):
        value = _basic_auth_value(match.group(1))
        if value:
            add("basic-auth", value, check_placeholder=False)
    for match in URL_PASSWORD_RE.finditer(text):
        if _url_password_is_placeholder(match.group(1), match.group(2)):
            continue
        if any(c in match.group(1) for c in "?#[]\\(") or any(
            c in match.group(2) for c in "?#[]\\"
        ):
            continue  # a regular expression or a query string, not user:password@host
        authority = re.split(r"[\s/'\"<>]", text[match.start(3) :], maxsplit=1)[0]
        if _host_is_reserved(authority.rsplit("@", 1)[-1]):
            continue  # a credential for a host that cannot exist is a test fixture
        add("url-password", match.group(2), check_placeholder=False)
    shaped = [matched for _, matched in hits]
    for match in ASSIGNMENT_RE.finditer(text):
        value = match.group(2)
        if any(value in earlier or earlier in value for earlier in shaped):
            continue
        if _secret_assignment_ok(match.group(1), value):
            add("secret-assignment", value)
    shaped = [matched for _, matched in hits]
    passwords = [
        m.group(3) for m in PASSWORD_QUOTED_RE.finditer(text) if not FILE_NAME_RE.search(m.group(1))
    ]
    bare = PASSWORD_BARE_RE.match(text)
    # NAME=value is shell or env style, always a literal. NAME: value may be code
    # (`password: form.password`), so there only a value no identifier could be, or a
    # long random-looking one, counts.
    if bare and (
        bare.group(2) == "="
        or not DOTTED_IDENTIFIER_RE.match(bare.group(3))
        or (len(bare.group(3)) >= 12 and _mixed(bare.group(3)) and entropy(bare.group(3)) >= 3.3)
    ):
        passwords.append(bare.group(3))
    for value in passwords:
        if any(value in earlier or earlier in value for earlier in shaped):
            continue
        if _password_ok(value):
            add("password-assignment", value, check_placeholder=False)

    for match in UNIX_PATH_RE.finditer(text):
        name = match.group(1) or match.group(2)
        if _person_path_name(name):
            add("local-path", match.group(0), check_placeholder=False)
    for regex in (WSL_PATH_RE, WINDOWS_PATH_RE, DASH_PATH_RE, PYTEST_TMP_RE):
        for match in regex.finditer(text):
            if _person_path_name(match.group(1)):
                add("local-path", match.group(0), check_placeholder=False)
    for match in HOME_RELATIVE_RE.finditer(text):
        add("local-path", match.group(0), check_placeholder=False)

    for match in EMAIL_RE.finditer(text):
        category = _email_category(match.group(1), match.group(2), match.group(3))
        if category:
            add(category, match.group(0), check_placeholder=False)
    for match in URL_HOST_RE.finditer(text):
        if _host_is_internal(match.group(1)):
            add("internal-host", match.group(1), check_placeholder=False)
    svg = _svg_spans(text)
    for match in IPV4_RE.finditer(text):
        if not _ip_is_allowed(match.group(1), text, match.start(1), match.end(1), svg):
            add("ipv4-address", match.group(1), check_placeholder=False)
    if "::" in text or text.count(":") >= 7:
        for match in IPV6_RE.finditer(text):
            if _ipv6_is_finding(match.group(1)):
                add("ipv6-address", match.group(1), check_placeholder=False)
    for match in SSH_RE.finditer(text):
        host = match.group(2).lower().rstrip(".,;")
        if host in SAFE_SSH_HOSTS or any(mark in host for mark in "<>${}[]"):
            continue
        if any(word in host for word in SSH_PLACEHOLDER_HOST_WORDS) and "." not in host:
            continue
        add("ssh-host", match.group(0), check_placeholder=False)


def _person_path_name(name: str) -> bool:
    lowered = name.lower().strip()
    if not lowered or lowered in SAFE_PATH_NAMES:
        return False
    return not re.fullmatch(r"[.*]+", lowered)


def _variants(text: str) -> list[str]:
    """The line, plus decoded forms that hide a value from a plain match."""
    out = [text]
    unescaped = text.replace('\\"', '"').replace("\\'", "'").replace("\\/", "/")
    if unescaped != text:
        out.append(unescaped)
    if "%" in text:
        try:
            decoded = urllib.parse.unquote(unescaped)
        except (ValueError, UnicodeError):
            decoded = unescaped
        if decoded != unescaped:
            out.append(decoded)
    lowered = text.lower()
    if "at]" in lowered or "(at)" in lowered or "{at}" in lowered:
        deobfuscated = re.sub(r"\s*[\[({]at[\])}]\s*", "@", unescaped, flags=re.IGNORECASE)
        deobfuscated = re.sub(
            r"\s*(?:\[\.\]|\(\.\)|\[dot\]|\(dot\)|\{dot\})\s*",
            ".",
            deobfuscated,
            flags=re.IGNORECASE,
        )
        out.append(deobfuscated)
    return out


def scan_line(text: str) -> list[tuple[str, str]]:
    """Return (category, matched text) for every finding on one physical line.

    A `local-refs: allow` marker on the line exempts private-value categories
    only; a secret on a marked line is still a finding.
    """
    allowed = ALLOW_MARKER in text
    hits: list[tuple[str, str]] = []
    for variant in _variants(text):
        if len(variant) <= WINDOW:
            _scan_window(variant, hits)
            continue
        for start in range(0, len(variant), WINDOW - OVERLAP):
            _scan_window(variant[start : start + WINDOW], hits)
            if start + WINDOW >= len(variant):
                break
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for category, matched in hits:
        if allowed and category not in SECRET_CATEGORIES:
            continue
        if (category, matched) in seen:
            continue
        seen.add((category, matched))
        out.append((category, matched))
    return out


def physical_lines(text: str) -> list[str]:
    """Split on every line ending, so one marker never covers another line."""
    return LINE_BREAK_RE.split(text)


# ---------------------------------------------------------------------------
# Running git, always with a timeout
# ---------------------------------------------------------------------------


def _run(
    command: list[str], *, cwd: Path | None = None, timeout: int, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[bytes]:
    what = " ".join(command[:1] + [a for a in command[1:] if not a.startswith("-")][:2])
    try:
        return subprocess.run(
            command, cwd=cwd, capture_output=True, check=False, timeout=timeout, env=env
        )
    except subprocess.TimeoutExpired as error:
        raise CannotRun(
            f"`{what}` took longer than {timeout} s and was stopped. Check for a stale git lock, "
            "a credential prompt or a slow disk, then run the scan again."
        ) from error
    except OSError as error:
        raise CannotRun(
            f"`{command[0]}` could not start ({error.strerror}). Install it or fix the PATH."
        ) from error


def _git(root: Path, *args: str, check: bool = True, timeout: int = GIT_TIMEOUT):
    result = _run(
        ["git", "-C", str(root), "-c", "core.quotePath=false", *args],
        timeout=timeout,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"},
    )
    if check and result.returncode != 0:
        raise CannotRun(
            f"git {args[0]} exited {result.returncode}. Run `git {args[0]}` by hand in the "
            "repository to see why, fix it, and run the scan again."
        )
    return result


def repo_root(start: Path) -> Path:
    result = _run(["git", "-C", str(start), "rev-parse", "--show-toplevel"], timeout=GIT_TIMEOUT)
    if result.returncode != 0:
        raise CannotRun(
            "this is not a git repository. Run the scan from inside the repository you are about to push."
        )
    return Path(result.stdout.decode("utf-8", "replace").strip())


def fetch_base(root: Path, base: str) -> None:
    """Bring the base's remote-tracking ref up to date, so a force-push cannot hide a commit."""
    remote, _, branch = base.partition("/")
    if not branch:
        return
    remotes = _git(root, "remote", check=False).stdout.decode("utf-8", "replace").split()
    if remote not in remotes:
        return
    result = _git(
        root,
        "fetch",
        "--quiet",
        "--no-tags",
        remote,
        f"+refs/heads/{branch}:refs/remotes/{remote}/{branch}",
        check=False,
        timeout=FETCH_TIMEOUT,
    )
    if result.returncode != 0:
        raise CannotRun(
            f"git fetch of {base} exited {result.returncode}, so the scan cannot know what the "
            "remote already has. Check the network and run the scan again, or pass --no-fetch to "
            "scan against the local copy of the base on purpose."
        )


def check_base(root: Path, base: str) -> str:
    result = _git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}", check=False)
    if result.returncode != 0:
        raise CannotRun(
            f"base ref '{base}' was not found. Run `git fetch origin` or pass an existing ref with --base."
        )
    merge_base = _git(root, "merge-base", "HEAD", base, check=False)
    if merge_base.returncode != 0:
        return result.stdout.decode().strip()
    return merge_base.stdout.decode().strip()


# ---------------------------------------------------------------------------
# Reading what a push publishes
# ---------------------------------------------------------------------------


def _unquote_c(text: str) -> str:
    """Undo git's C-style quoting of a path."""
    if not (text.startswith('"') and text.endswith('"')):
        return text
    body = text[1:-1]
    out = bytearray()
    i = 0
    escapes = {"n": 10, "t": 9, '"': 34, "\\": 92, "a": 7, "b": 8, "f": 12, "r": 13, "v": 11}
    while i < len(body):
        char = body[i]
        if char == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt in escapes:
                out.append(escapes[nxt])
                i += 2
                continue
            if re.match(r"[0-7]{3}", body[i + 1 : i + 4]):
                out.append(int(body[i + 1 : i + 4], 8))
                i += 4
                continue
        out.extend(char.encode("utf-8", "surrogateescape"))
        i += 1
    return out.decode("utf-8", "replace")


def _path_from_header(raw: str) -> str:
    rest = raw.split(" ", 2)[2] if raw.startswith("diff --git ") else raw.split(" ", 2)[-1]
    if rest.startswith('"'):
        end = 1
        while end < len(rest):
            if rest[end] == "\\":
                end += 2
                continue
            if rest[end] == '"':
                break
            end += 1
        first = _unquote_c(rest[: end + 1])
        return first.removeprefix("a/")
    if raw.startswith("diff --git "):
        length = (len(rest) - 5) // 2
        return rest[2 : 2 + length]
    return rest


@dataclass
class FilePatch:
    source: str
    commit: str | None
    path: str
    new_file: bool = False
    deleted: bool = False
    binary: bool = False
    old_blob: str | None = None
    new_blob: str | None = None
    added: list[tuple[int, str]] = field(default_factory=list)


def parse_patches(text: str, source: str) -> list[FilePatch]:
    """Every file's added (line number, text) pairs from a -U0 patch stream."""
    patches: list[FilePatch] = []
    commit: str | None = None
    current: FilePatch | None = None
    remaining = 0
    line_no = 0
    for raw in text.split("\n"):
        if remaining > 0:
            if raw.startswith("+"):
                if current is not None:
                    current.added.append((line_no, raw[1:]))
                line_no += 1
                remaining -= 1
                continue
            if raw.startswith(("-", "\\")):
                continue
            remaining = 0
        if raw.startswith(COMMIT_SENTINEL):
            commit = raw[len(COMMIT_SENTINEL) :].strip()
            current = None
            continue
        if raw.startswith(("diff --git ", "diff --cc ", "diff --combined ")):
            current = FilePatch(source, commit, _path_from_header(raw))
            patches.append(current)
            continue
        if current is None:
            continue
        if raw.startswith("new file mode"):
            current.new_file = True
        elif raw.startswith("deleted file mode"):
            current.deleted = True
        elif raw.startswith("index "):
            match = INDEX_RE.match(raw)
            if match:
                current.old_blob = match.group(1).split(",")[0]
                current.new_blob = match.group(2)
        elif raw.startswith(("Binary files ", "GIT binary patch")):
            current.binary = True
        elif raw.startswith("+++ "):
            name = raw[4:].split("\t")[0]
            if name != "/dev/null":
                name = _unquote_c(name)
                current.path = name.removeprefix("b/")
        else:
            match = HUNK_RE.match(raw)
            if match:
                line_no = int(match.group(1))
                remaining = int(match.group(2)) if match.group(2) is not None else 1
    return patches


def classify(data: bytes) -> tuple[str, str | None]:
    """("text", decoded) or ("binary", None), judged by content, never by name."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "text", data.decode("utf-16", "replace")
    if b"\0" not in data:
        return "text", data.decode("utf-8", "replace")
    sample = data[:65536]
    even = sample[0::2].count(0)
    odd = sample[1::2].count(0)
    half = max(1, len(sample) // 2)
    if odd / half > 0.3 and even / half < 0.05:
        return "text", data.decode("utf-16-le", "replace")
    if even / half > 0.3 and odd / half < 0.05:
        return "text", data.decode("utf-16-be", "replace")
    if data.count(0) <= max(1, len(data) // 100):
        # A stray NUL in otherwise readable text; a real binary is full of control bytes.
        rest = data.replace(b"\0", b"")
        controls = sum(1 for byte in rest if byte < 32 and byte not in (8, 9, 10, 12, 13, 27))
        if controls <= len(rest) // 20:
            return "text", data.replace(b"\0", b" ").decode("utf-8", "replace")
    return "binary", None


def printable_runs(data: bytes) -> Iterator[str]:
    for match in re.finditer(rb"[\x20-\x7e]{8,}", data):
        yield match.group(0).decode("ascii")


def _blob(root: Path, blob: str | None) -> bytes | None:
    if not blob or ZERO_BLOB.match(blob):
        return None
    result = _git(root, "cat-file", "blob", blob, check=False)
    return result.stdout if result.returncode == 0 else None


def _add_text(
    report: ScanReport, patch: FilePatch, lines: Iterable[tuple[int, str]], size: int
) -> None:
    head = Unit("content", patch.source, patch.commit, patch.path, 0, "")
    if size > MAX_FILE_BYTES:
        report.too_large.append((head, size))
        return
    for number, text in lines:
        report.units.append(Unit("content", patch.source, patch.commit, patch.path, number, text))


def _add_whole(report: ScanReport, patch: FilePatch, data: bytes, old: bytes | None = None) -> None:
    """A file git would not diff as text: judge the bytes, then read them."""
    kind, decoded = classify(data)
    if kind == "binary":
        unit = Unit("binary", patch.source, patch.commit, patch.path, 0, "")
        report.binaries.append(unit)
        if len(data) <= MAX_BINARY_BYTES:
            for number, run in enumerate(printable_runs(data), start=1):
                report.units.append(
                    Unit("binary", patch.source, patch.commit, patch.path, number, run)
                )
        return
    assert decoded is not None
    lines = physical_lines(decoded)
    numbered = list(enumerate(lines, start=1))
    if old is not None:
        old_kind, old_text = classify(old)
        if old_kind == "text" and old_text is not None:
            before = Counter(physical_lines(old_text))
            kept: list[tuple[int, str]] = []
            for number, text in numbered:
                if before[text] > 0:
                    before[text] -= 1
                else:
                    kept.append((number, text))
            numbered = kept
    _add_text(report, patch, numbered, len(data))


def _add_patches(root: Path, report: ScanReport, patches: list[FilePatch]) -> None:
    for patch in patches:
        if patch.deleted:
            continue
        if patch.new_file:
            report.units.append(Unit("name", patch.source, patch.commit, patch.path, 0, patch.path))
        needs_bytes = patch.binary or any("\0" in text for _, text in patch.added)
        if not needs_bytes:
            size = sum(len(text.encode("utf-8", "replace")) + 1 for _, text in patch.added)
            _add_text(report, patch, _split_parts(patch.added), size)
            continue
        if patch.source == "working tree":
            try:
                data: bytes | None = (root / patch.path).read_bytes()
            except OSError:
                data = None
        else:
            data = _blob(root, patch.new_blob)
        if data is None:
            report.too_large.append(
                (Unit("content", patch.source, patch.commit, patch.path, 0, ""), -1)
            )
            continue
        old = None if patch.new_file else _blob(root, patch.old_blob)
        _add_whole(report, patch, data, old)


def _split_parts(lines: list[tuple[int, str]]) -> Iterator[tuple[int, str]]:
    for number, text in lines:
        for part in physical_lines(text):
            if part:
                yield number, part


_DIFF_FLAGS = (
    "--no-color",
    "--no-ext-diff",
    "--no-textconv",
    "--no-renames",
    "--full-index",
    "-U0",
)


def scan_commits(root: Path, base: str, report: ScanReport) -> None:
    rev_range = f"{base}..HEAD"
    meta = _git(root, "log", "-z", "--format=%H%n%ae%n%ce%n%B", rev_range)
    for record in meta.stdout.decode("utf-8", "replace").split("\0"):
        if not record.strip("\n"):
            continue
        fields = record.split("\n", 3)
        while len(fields) < 4:
            fields.append("")
        sha, author, committer, message = fields
        report.commits += 1
        for role, email in (("author", author), ("committer", committer)):
            if email and not NOREPLY_IDENTITY_RE.match(email):
                report.identity.append((sha, role, email))
        for number, text in enumerate(physical_lines(message.rstrip("\n")), start=1):
            report.units.append(Unit("message", "commit", sha, None, number, text))
    patch_args = [
        "log",
        "-p",
        *_DIFF_FLAGS,
        f"--format={COMMIT_SENTINEL.replace(chr(0), '%x00')}%H",
        rev_range,
    ]
    result = _git(root, *patch_args[:2], "--diff-merges=remerge", *patch_args[2:], check=False)
    if result.returncode != 0:
        # git older than 2.36 has no remerge diff; the first-parent diff reads more, never less.
        result = _git(root, *patch_args[:2], "--diff-merges=first-parent", *patch_args[2:])
    _add_patches(root, report, parse_patches(result.stdout.decode("utf-8", "replace"), "commit"))


def scan_worktree(root: Path, report: ScanReport) -> None:
    for source, args in (("staged", ("--cached",)), ("working tree", ())):
        result = _git(root, "diff", *_DIFF_FLAGS, *args, "HEAD", check=False)
        if result.returncode != 0:
            continue  # no HEAD yet: nothing is committed, the untracked scan reads every file
        _add_patches(root, report, parse_patches(result.stdout.decode("utf-8", "replace"), source))


def scan_untracked(root: Path, report: ScanReport) -> None:
    listing = _git(root, "ls-files", "--others", "--exclude-standard", "-z")
    for rel in listing.stdout.decode("utf-8", "replace").split("\0"):
        if not rel:
            continue
        path = root / rel
        patch = FilePatch("untracked", None, rel, new_file=True)
        report.units.append(Unit("name", "untracked", None, rel, 0, rel))
        try:
            if path.is_symlink() or not path.is_file():
                continue
            size = path.stat().st_size
            with path.open("rb") as handle:
                head = handle.read(65536)
            if size > MAX_FILE_BYTES and classify(head)[0] == "text":
                report.too_large.append((Unit("content", "untracked", None, rel, 0, ""), size))
                continue
            if size > MAX_BINARY_BYTES:
                report.binaries.append(Unit("binary", "untracked", None, rel, 0, ""))
                continue
            data = path.read_bytes()
        except OSError:
            report.too_large.append((Unit("content", "untracked", None, rel, 0, ""), -1))
            continue
        _add_whole(report, patch, data)


def run_scan(root: Path, base: str, *, fetch: bool = True) -> tuple[ScanReport, str]:
    if fetch:
        fetch_base(root, base)
    merge_base = check_base(root, base)
    report = ScanReport()
    scan_commits(root, base, report)
    scan_worktree(root, report)
    scan_untracked(root, report)
    for unit in report.units:
        for category, matched in _scan_unit(unit):
            report.findings.append(Finding(unit, category, mask(matched)))
    for sha, role, email in report.identity:
        report.findings.append(
            Finding(None, "identity-email", mask(email), f"commit {sha[:8]} {role}-email")
        )
    return report, merge_base


def _scan_unit(unit: Unit) -> list[tuple[str, str]]:
    if unit.kind == "name" and unit.text.startswith(("Users/", "home/")):
        return scan_line("/" + unit.text)
    return scan_line(unit.text)


# ---------------------------------------------------------------------------
# The owner's machine-local private-name check
# ---------------------------------------------------------------------------


def locate_private_check(root: Path) -> tuple[Path | None, str]:
    """Find verify_no_local_refs.py from the hook's exec line, never a fixed path.

    Returns (script, reason). The script is None when the check cannot run, and
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
    named_elsewhere = False
    for line in lines:
        try:
            tokens = shlex.split(line, comments=True)
        except ValueError:
            continue
        if not tokens or tokens[0] != "exec":
            if any(Path(t).name == PRIVATE_SCRIPT_NAME for t in tokens):
                named_elsewhere = True
            continue
        for token in tokens[1:]:
            candidate = Path(token).expanduser()
            try:
                resolved = candidate.resolve()
            except (OSError, RuntimeError):
                continue
            if candidate.name != PRIVATE_SCRIPT_NAME and resolved.name != PRIVATE_SCRIPT_NAME:
                continue
            if not resolved.is_file():
                return (
                    None,
                    f"the {PRIVATE_SCRIPT_NAME} named by the pre-commit hook does not exist",
                )
            if resolved.name != PRIVATE_SCRIPT_NAME:
                return (
                    None,
                    f"the hook's script is a link to a file that is not {PRIVATE_SCRIPT_NAME}",
                )
            return resolved, ""
    if named_elsewhere:
        return None, f"the pre-commit hook names {PRIVATE_SCRIPT_NAME} but not on its exec line"
    return None, f"the pre-commit hook's exec line does not run {PRIVATE_SCRIPT_NAME}"


PRIVATE_MESSAGE_RE = re.compile(r"^FAIL: commit message:(\d+): ([a-z][a-z0-9-]*)$")
PRIVATE_TREE_RE = re.compile(r"^FAIL: (.+?)(?::(\d+)| \(file path\)): ([a-z][a-z0-9-]*)$")


@dataclass
class PrivateResult:
    status: str  # "pass", "findings", "not-run"
    reason: str = ""
    message_hits: list[tuple[int, str]] = field(default_factory=list)
    tree_hits: list[tuple[str, int, str]] = field(default_factory=list)


def _run_private(script: Path, root: Path, args: list[str]) -> tuple[int, list[str]]:
    result = _run([sys.executable, str(script), *args], cwd=root, timeout=PRIVATE_TIMEOUT)
    text = (result.stdout + result.stderr).decode("utf-8", "replace")
    return result.returncode, text.splitlines()


def run_private_check(root: Path, units: list[Unit]) -> PrivateResult:
    """Run the check over every scanned line and over the tracked tree; relay only verdicts."""
    script, reason = locate_private_check(root)
    if script is None:
        return PrivateResult("not-run", reason)
    descriptor, name = tempfile.mkstemp(suffix=".txt", prefix="leakscan-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", errors="replace") as handle:
            for unit in units:
                # A leading space: the check skips lines that start with `#` in a message file.
                handle.write(" " + SPLITLINES_CHARS.sub(" ", unit.text) + "\n")
        runs = (("message", ["--message", name]), ("tree", ["--all"]))
        result = PrivateResult("pass")
        for label, args in runs:
            try:
                code, lines = _run_private(script, root, args)
            except CannotRun:
                return PrivateResult("not-run", f"the check did not finish ({label} mode)")
            if code == 0:
                continue
            if code == 2:
                return PrivateResult(
                    "not-run",
                    f"the check exited 2 in {label} mode (it could not check); run it by hand",
                )
            parsed = 0
            for line in lines:
                if label == "message":
                    match = PRIVATE_MESSAGE_RE.match(line)
                    if match:
                        result.message_hits.append((int(match.group(1)), match.group(2)))
                        parsed += 1
                else:
                    match = PRIVATE_TREE_RE.match(line)
                    if match:
                        number = int(match.group(2)) if match.group(2) else 0
                        result.tree_hits.append((match.group(1), number, match.group(3)))
                        parsed += 1
            if code != 1 or parsed == 0:
                return PrivateResult(
                    "not-run",
                    f"the check exited {code} in {label} mode without a finding line it could "
                    "name (it probably crashed); run it by hand",
                )
        if result.message_hits or result.tree_hits:
            result.status = "findings"
        return result
    finally:
        try:
            os.unlink(name)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _hidden(path: str) -> str:
    return f"<file name hidden, {mask(path)}>"


def _where(unit: Unit, bad_paths: set[str]) -> str:
    prefix = f"commit {unit.commit[:8]} " if unit.commit else ""
    if unit.kind == "message":
        return f"{prefix}message:{unit.line}"
    path = unit.path or ""
    shown = _hidden(path) if path in bad_paths else path
    if unit.kind == "name":
        return f"{prefix}file name {shown}"
    if unit.kind == "binary":
        return f"{prefix}{shown} (binary, text run {unit.line})"
    return f"{prefix}{shown}:{unit.line}"


def _changed_paths(root: Path, base: str) -> set[str]:
    result = _git(root, "diff", "--name-only", "-z", "--no-renames", base, check=False)
    return set(result.stdout.decode("utf-8", "replace").split("\0")) - {""}


def main(argv: list[str] | None = None, cwd: Path | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan what a push would publish for secrets and private values."
    )
    parser.add_argument(
        "--base",
        default="origin/develop",
        help="the ref the push would be added to (default origin/develop), fetched first",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="do not fetch the base first; scan against the local copy of it",
    )
    parser.add_argument(
        "--allow-missing-private-check",
        action="store_true",
        help="do not fail when the machine-local private-name check is absent",
    )
    args = parser.parse_args(argv)
    try:
        return _main(args, cwd)
    except CannotRun as error:
        print(f"CANNOT RUN: {error} Nothing was checked, so do not push.", file=sys.stderr)
        return 2
    except Exception as error:  # noqa: BLE001 - any crash must read as "could not run", never a finding
        print(
            f"CANNOT RUN: the scan stopped on an internal error ({type(error).__name__}). Nothing "
            "was checked, so do not push. Run it again; if it repeats, report the error name.",
            file=sys.stderr,
        )
        return 2


def _main(args: argparse.Namespace, cwd: Path | None) -> int:
    root = repo_root(cwd or Path.cwd())
    report, merge_base = run_scan(root, args.base, fetch=not args.no_fetch)
    private = run_private_check(root, report.units)

    bad_paths = {
        f.unit.path for f in report.findings if f.unit and f.unit.kind == "name" and f.unit.path
    }
    for number, _ in private.message_hits:
        if 1 <= number <= len(report.units):
            unit = report.units[number - 1]
            if unit.kind == "name" and unit.path:
                bad_paths.add(unit.path)
    bad_paths.update(path for path, number, _ in private.tree_hits if number == 0)

    exit_code = 0
    fails: list[str] = []
    for finding in report.findings:
        where = finding.where_override or _where(finding.unit, bad_paths)  # type: ignore[arg-type]
        fails.append(f"FAIL {where} [{finding.category}] {finding.masked}")
    fails = list(dict.fromkeys(fails))
    for line in fails:
        print(line)
    if fails:
        exit_code = 1
    for unit, size in report.too_large:
        where = _where(unit, bad_paths).rsplit(":", 1)[0]
        if size < 0:
            print(
                f"TOO LARGE {where} (could not be read): read it by hand, then run the scan again"
            )
        else:
            print(
                f"TOO LARGE {where} ({size} bytes, over the {MAX_FILE_BYTES // (1024 * 1024)} MB "
                "scan limit): shrink or split it, then run the scan again"
            )
        exit_code = 1
    for unit in report.binaries:
        where = _where(unit, bad_paths).split(" (binary", 1)[0]
        print(
            f"NOT SCANNED {where}: binary, a person must look at it (only its text runs were read)"
        )

    if private.status == "pass":
        print(
            f"{PRIVATE_CHECK_NAME}: PASS (it read every line, file name and message this scan read, "
            f"in {report.commits} commit(s) and the working tree, and every tracked file)"
        )
    elif private.status == "findings":
        changed = _changed_paths(root, args.base)
        private_lines: list[tuple[str, str, str]] = []
        for number, name in private.message_hits:
            if 1 <= number <= len(report.units):
                private_lines.append((name, _where(report.units[number - 1], bad_paths), ""))
            else:
                private_lines.append((name, "an unplaced line", ""))
        for path, number, name in private.tree_hits:
            shown = _hidden(path) if path in bad_paths else path
            location = f"{shown}:{number}" if number else f"file name {shown}"
            note = ""
            if path not in changed:
                note = " (already on the base: remove it here and tell the owner)"
            private_lines.append((name, location, note))
        for name, location, note in dict.fromkeys(private_lines):
            print(f"FAIL {PRIVATE_CHECK_NAME}: {location} [{name}]{note}")
            fails.append(name)
        exit_code = 1
    else:
        print(f"{PRIVATE_CHECK_NAME} NOT RUN on this machine: {private.reason}")
        if not args.allow_missing_private_check:
            print(
                "A push from a machine without it is unchecked for private names. "
                "Run it where the check exists, or pass --allow-missing-private-check."
            )
            exit_code = 1

    scanned = sum(1 for u in report.units if u.kind != "name")
    names = sum(1 for u in report.units if u.kind == "name")
    print(
        f"scanned {scanned} lines, {names} file names and {report.commits} commit(s) against "
        f"{args.base} (merge base {merge_base[:8]}); {len(fails)} finding(s), "
        f"{len(report.too_large)} file(s) too large to scan, "
        f"{len(report.binaries)} binary file(s) for a person to look at"
    )
    if exit_code:
        print(
            "BLOCKED. A finding in a commit is in the history this push would publish, so a later "
            "commit that deletes the line does not remove it: take it out of that commit. Nothing "
            f"in the range is pushed yet, so for example `git reset --soft {merge_base[:8]}`, fix "
            "the files, and make one fresh commit. A finding in the working tree or an untracked "
            f"file: remove the line before committing. `{ALLOW_MARKER}` on the same line exempts "
            "only a genuinely public path, address or host, never a secret. A secret already in a "
            "pushed commit needs the owner and a rotation."
        )
    else:
        print("PASS: nothing to publish looks like a secret or a private value.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
