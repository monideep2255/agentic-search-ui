"""Run the /ship public-leak scan the way /ship does, against throwaway repositories.

`.claude/skills/ship/scripts/check_public_leaks.py` scans what a push would
publish: every commit in `<base>..HEAD` one at a time (added lines, new file
names, message, author and committer email), the staged and unstaged diff, and
every untracked file. It exits 1 on a finding, 2 when it could not run, and 0
when clean.

WHAT THIS COVERS, stated so a gap is arguable rather than discovered:

    Covered      Every category fires on a planted value, from a commit, a
                 message and an untracked file; no run of more than four
                 characters of any planted value reaches the output; every
                 placeholder and every known false alarm stays quiet; the allow
                 marker exempts only its own physical line and never a secret;
                 a value added then removed in unpushed history; a change made
                 only in a merge; the base fetched before the scan; long lines,
                 files over the size limit, NUL bytes, UTF-16, binary names and
                 `.gitattributes`; file and directory names; the machine-local
                 private-name check found only as `verify_no_local_refs.py` on
                 the hook's exec line, run in `--message` and `--all` modes,
                 never relayed raw; exit codes 0, 1 and 2, timeouts and crashes.
    Not covered  The owner's real private-name check. It cannot live in this
                 public repository, so a stand-in script of the same name and
                 output format plays its part.

Every planted value is assembled from parts at run time. No real-looking secret
is committed, and this file must pass the scan it tests. Test names carry the
review finding each one closes (J for the judge, A for the adversary, report of
2026-09-29_ship_leak_scan).

MUTATION PROOF: set CHECK_PUBLIC_LEAKS_SCRIPT to another copy of the script
(the pre-fix one, or one with a detector disabled) and the tests for what it
lacks go red. The runs are recorded in that report folder's fix.md.
"""

from __future__ import annotations

import ast
import base64
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(
    os.environ.get(
        "CHECK_PUBLIC_LEAKS_SCRIPT",
        REPO_ROOT / ".claude" / "skills" / "ship" / "scripts" / "check_public_leaks.py",
    )
)

NOREPLY = "1+tester@users.noreply.github.com"
TAIL = "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5xZ8cV2bN4mK6"
HOME_ROOT = "/Us" + "ers/"
OWNER_TERM = "owner" + "-term-zq"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_public_leaks_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


leaks = _load()


def planted(kind: str) -> str:
    """One fake value per category, assembled here so no literal is committed."""
    dashes = "-" * 5
    basic = base64.b64encode(("svc9" + ":" + "Zq8vR2xT9mKp").encode()).decode()
    values = {
        "private-key": f"{dashes}BEGIN RSA " + "PRIVATE" + f" KEY{dashes}",
        "pgp-private-key": f"{dashes}BEGIN PGP " + "PRIVATE" + f" KEY BLOCK{dashes}",
        "aws-access-key": "AK" + "IA" + "QW3ERTY5UIOP7ASD",
        "github-token": "gh" + "p_" + TAIL[:36],
        "provider-api-key": "s" + "k-" + TAIL[:32],
        "stripe-key": "s" + "k_live_" + TAIL[:24],
        "gitlab-token": "gl" + "pat-" + TAIL[:20],
        "huggingface-token": "h" + "f_" + TAIL[:34],
        "npm-token": "np" + "m_" + TAIL[:36],
        "slack-token": "xo" + "xb-1234567890-" + "abcdefghij",
        "slack-webhook": "https://hooks.sl" + "ack.com/services/T0ZQ8K2/B0ZQ9M4/" + TAIL[:24],
        "discord-webhook": "https://disc"
        + "ord.com/api/webhooks/"
        + "123456789012345678/"
        + TAIL[:40],
        "google-api-key": "AI" + "za" + TAIL[:35],
        "jwt": "ey"
        + "JhbGciOiJIUzI1NiJ9."
        + "ey"
        + "JzdWIiOiIxMjM0NTY3ODkwIn0."
        + "dBjftJeZ4CVPmB92K27u",
        "bearer-token": "Bearer " + TAIL[:24],
        "basic-auth": "Authorization: Ba" + "sic " + basic,
        "url-password": "postgresql://"
        + "appuser"
        + ":"
        + "Zq8"
        + "vR2xT9mK"
        + "@db.qzvx.io:5432/x",
        "short-url-password": "redis://app9:" + "Qz7vR2" + "@cache.qzvx.io:6379/0",
        "secret-assignment": "api" + "_key = " + '"' + "a8Kd93jLq0Zx7MvB2nRt" + '"',
        "password-assignment": "db_pass" + "word = '" + "Qz7!vR2#pL" + "'",
        "notebook-key": '"api' + '_key = \\"' + "a8Kd93jLq0Zx7MvB2nRt" + '\\"\\n",',
        "local-path": HOME_ROOT + "jdoe42" + "/project/x.py",
        "personal-email": "jdoe42" + "@" + "gmail.com",
        "ipv4-address": "172." + "16.4.9",
        "ipv4-ten": "10." + "20.30.41",
        "ipv4-one-nine-two": "192." + "168.7.23",
        "ipv6-address": "2600:1f18:24e6:b90" + "0::17",
        "internal-host": "https://qzwiki9.intr" + "anet/browse/QZ-9",
        "ssh-host": "ssh " + "deploy" + "@" + "gw7.qzvx.io",
        "git-remote": "git" + "@" + "code.qzvx.io:team/repository.git",
    }
    return values[kind]


def secret_of(kind: str) -> str:
    """The part of a planted value that must never appear in the output."""
    value = planted(kind)
    parts = {
        "url-password": "Zq8" + "vR2xT9mK",
        "short-url-password": "Qz7" + "vR2",
        "secret-assignment": "a8Kd93jLq0" + "Zx7MvB2nRt",
        "notebook-key": "a8Kd93jLq0" + "Zx7MvB2nRt",
        "password-assignment": "Qz7!v" + "R2#pL",
        "local-path": "jdoe42",
        "ssh-host": "gw7.qzvx.io",
        "git-remote": "code.qzvx.io",
        "internal-host": "qzwiki9.intr" + "anet",
        "pgp-private-key": " PGP " + "PRIVATE" + " KEY",
        "private-key": " RSA " + "PRIVATE" + " KEY",
        "slack-webhook": TAIL[:24],
        "discord-webhook": TAIL[:40],
    }
    if kind == "bearer-token":
        return value.split(" ", 1)[1]
    if kind == "basic-auth":
        return value.rsplit(" ", 1)[1]
    return parts.get(kind, value)


# Planted kind -> the category the scan must report for it.
CATEGORY = {
    "private-key": "private-key",
    "pgp-private-key": "private-key",
    "aws-access-key": "aws-access-key",
    "github-token": "github-token",
    "provider-api-key": "provider-api-key",
    "stripe-key": "stripe-key",
    "gitlab-token": "gitlab-token",
    "huggingface-token": "huggingface-token",
    "npm-token": "npm-token",
    "slack-token": "slack-token",
    "slack-webhook": "slack-webhook",
    "discord-webhook": "discord-webhook",
    "google-api-key": "google-api-key",
    "jwt": "jwt",
    "bearer-token": "bearer-token",
    "basic-auth": "basic-auth",
    "url-password": "url-password",
    "short-url-password": "url-password",
    "secret-assignment": "secret-assignment",
    "password-assignment": "password-assignment",
    "notebook-key": "secret-assignment",
    "local-path": "local-path",
    "personal-email": "personal-email",
    "ipv4-address": "ipv4-address",
    "ipv4-ten": "ipv4-address",
    "ipv4-one-nine-two": "ipv4-address",
    "ipv6-address": "ipv6-address",
    "internal-host": "internal-host",
    "ssh-host": "ssh-host",
    "git-remote": "ssh-host",
}
ALL_KINDS = list(CATEGORY)
PRIVATE_VALUE_CATEGORIES = {
    "local-path",
    "personal-email",
    "ipv4-address",
    "ipv6-address",
    "internal-host",
    "ssh-host",
}
SECRET_KINDS = [k for k in ALL_KINDS if CATEGORY[k] not in PRIVATE_VALUE_CATEGORIES]


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path / "home"),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CEILING_DIRECTORIES": str(tmp_path.parent),
        "GIT_AUTHOR_NAME": "Tester",
        "GIT_AUTHOR_EMAIL": NOREPLY,
        "GIT_COMMITTER_NAME": "Tester",
        "GIT_COMMITTER_EMAIL": NOREPLY,
    }
    env.update(extra)
    return env


def git(repo: Path, *args: str, **extra: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        env=_env(repo.parent, **extra),
    )
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository with one commit tagged `base`, so `--base base` is the push range."""
    (tmp_path / "home").mkdir()
    root = tmp_path / "work"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "README.md").write_text("# fixture\n")
    git(root, "add", "README.md")
    git(root, "commit", "-q", "-m", "docs: start")
    git(root, "tag", "base")
    return root


def commit_file(
    repo: Path, name: str, text: str | bytes, message: str = "chore: add file", **extra: str
) -> str:
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        target.write_bytes(text)
    else:
        target.write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", message, **extra)
    return git(repo, "rev-parse", "HEAD")


def scan(repo: Path, *args: str, allow_missing: bool = True) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT), "--base", "base", *args]
    if allow_missing:
        command.append("--allow-missing-private-check")
    return subprocess.run(
        command, cwd=repo, capture_output=True, text=True, env=_env(repo.parent), check=False
    )


def no_run_of(secret: str, output: str, width: int = 5) -> list[str]:
    """Every run of `width` characters of the secret that appears in the output."""
    return [
        secret[i : i + width]
        for i in range(len(secret) - width + 1)
        if secret[i : i + width] in output
    ]


STAND_IN = """\
import pathlib, subprocess, sys
TERM = "owner" + "-term-zq"
here = pathlib.Path(__file__).resolve().parent
with (here / "calls.log").open("a") as log:
    log.write(sys.argv[1] + "\\n")
found = 0
if sys.argv[1] == "--message":
    text = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8")
    (here / "message_copy.txt").write_text(text, encoding="utf-8")
    for number, line in enumerate(text.splitlines(), start=1):
        if line.startswith("#"):
            continue
        if TERM in line:
            print(f"FAIL: commit message:{number}: owner-term", file=sys.stderr)
            found += 1
elif sys.argv[1] == "--all":
    names = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True).stdout
    for name in filter(None, names.split("\\0")):
        if TERM in name:
            print(f"FAIL: {name} (file path): owner-term", file=sys.stderr)
            found += 1
        body = pathlib.Path(name).read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(body.splitlines(), start=1):
            if TERM in line:
                print(f"FAIL: {name}:{number}: owner-term", file=sys.stderr)
                found += 1
else:
    sys.exit(2)
if found:
    print(f"BLOCKED: {found} local reference finding(s).", file=sys.stderr)
    sys.exit(1)
print("PASS: no local references found.")
"""


def install_check(
    repo: Path,
    body: str = STAND_IN,
    *,
    script_name: str = "verify_no_local_refs.py",
    folder: str = "priv dir",
    exec_line: str | None = None,
) -> Path:
    """Install a stand-in machine-local check and a hook whose exec line names it."""
    directory = repo.parent / folder
    directory.mkdir(exist_ok=True)
    script = directory / script_name
    script.write_text(body)
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(exist_ok=True)
    hook = hooks / "pre-commit"
    line = exec_line if exec_line is not None else f'exec python3 "{script}" --staged'
    hook.write_text(f"#!/bin/sh\n# local only\n{line}\n")
    hook.chmod(0o755)
    return directory


# ---------------------------------------------------------------------------
# Every category fires, from each source, and the value never reaches the output
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_category_fires_from_a_commit(repo: Path, kind: str) -> None:
    """A01 A09 A19 J09 J16: every shape, including those the first round missed."""
    commit_file(repo, "docs/notes.txt", f"first line\nvalue: {planted(kind)}\n")
    result = scan(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"docs/notes.txt:2 [{CATEGORY[kind]}]" in result.stdout


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_no_run_of_five_characters_of_any_value_is_printed(repo: Path, kind: str) -> None:
    """J16: the value is masked from a commit, a commit message and an untracked file."""
    commit_file(
        repo,
        "docs/notes.txt",
        f"value: {planted(kind)}\n",
        message=f"chore: add\n\n{planted(kind)}",
    )
    (repo / "loose.txt").write_text(f"{planted(kind)}\n")
    result = scan(repo)
    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert output.count(f"[{CATEGORY[kind]}]") >= 3, output
    assert no_run_of(secret_of(kind), output) == []


def test_masking_shows_only_the_first_character_and_the_length() -> None:
    """J16: a mask that reveals a tail or a middle slice is caught here, not by luck."""
    value = "Qz7vR2xT9mKpL4"
    shown = leaks.mask(value)
    assert shown == f"Q***({len(value)} chars)"
    assert no_run_of(value, shown, width=2) == []
    assert leaks.mask("abc") == "***"


@pytest.mark.parametrize(
    "value",
    [
        "gh" + "p_" + TAIL[:36],
        "gh" + "o_" + TAIL[:36],
        "gh" + "s_" + TAIL[:36],
        "gh" + "u_" + TAIL[:36],
        "github" + "_pat_" + TAIL[:22],
    ],
    ids=["p", "o", "s", "u", "fine-grained"],
)
def test_every_github_token_prefix_fires(repo: Path, value: str) -> None:
    commit_file(repo, "a.txt", f"token in prose {value}\n")
    result = scan(repo)
    assert result.returncode == 1
    assert "[github-token]" in result.stdout
    assert value not in result.stdout


@pytest.mark.parametrize("prefix", ["sk-", "sk-ant-", "sk-or-"])
def test_provider_key_styles_fire(repo: Path, prefix: str) -> None:
    commit_file(repo, "a.txt", "key " + "s" + prefix[1:] + TAIL[:30] + "\n")
    result = scan(repo)
    assert result.returncode == 1
    assert "[provider-api-key]" in result.stdout


LOCAL_PATH_SHAPES = {
    "linux": "/hom" + "e/jdoe42/repo/file.py",
    "windows": "C:" + "\\Us" + "ers\\jdoe42\\repo\\file.py",
    "windows-lower-case": "c:" + "\\us" + "ers\\jdoe42\\x",
    "no-trailing-slash": "cwd was " + HOME_ROOT + "jdoe42",
    "dash-encoded": "/private/tmp/claude-501/-Us" + "ers-jdoe42-Desktop-proj/scratchpad/x.txt",
    "agent-project": "projects/-Us" + "ers-jdoe42-Desktop-proj/memory/a.md",
    "wsl": "/mnt/c" + HOME_ROOT + "jdoe42/x",
    "name-with-a-space": '"' + HOME_ROOT + "jdoe42 smith/x" + '"',
    "json-escaped": "\\/Us" + "ers\\/jdoe42\\/x",
    "url-encoded": "%2FUs" + "ers%2Fjdoe42%2FDesktop",
    "pytest-temp": "/var/folders/ab/pytest-of-" + "jdoe42/x",
    "home-relative": "see ~" + "/Desk" + "top/proj/notes.md",
}


@pytest.mark.parametrize("path", LOCAL_PATH_SHAPES.values(), ids=LOCAL_PATH_SHAPES.keys())
def test_other_local_path_shapes_fire(repo: Path, path: str) -> None:
    """A02 J18: the dash-encoded agent path, no trailing slash, WSL, escapes and more."""
    commit_file(repo, "a.txt", f"see {path}\n")
    result = scan(repo)
    assert result.returncode == 1, result.stdout
    assert "[local-path]" in result.stdout
    assert "jdoe42" not in result.stdout


@pytest.mark.parametrize(
    "line",
    [
        "zelda7" + "@snake.py",
        "zelda7" + "@noreply.qzvx.io",
        "zelda7" + "[at]gmail[.]com",
        "mailto:zelda7" + "%40gmail.com",
    ],
    ids=["py-country-domain", "noreply-label", "bracket-obfuscated", "url-encoded"],
)
def test_address_shapes_that_used_to_pass_fire(repo: Path, line: str) -> None:
    """A19: country domains that look like file types, noreply labels, obfuscation."""
    commit_file(repo, "a.txt", f"{line}\n")
    result = scan(repo)
    assert result.returncode == 1, result.stdout
    assert "[personal-email]" in result.stdout


def test_git_remote_on_a_public_forge_is_quiet_and_on_any_other_host_fires(repo: Path) -> None:
    """A19: `git@` was exempt whatever the host."""
    commit_file(repo, "a.txt", "clone git" + "@github.com:owner/repository.git\n")
    assert scan(repo).returncode == 0
    commit_file(repo, "b.txt", planted("git-remote") + "\n")
    result = scan(repo)
    assert result.returncode == 1
    assert "b.txt:1 [ssh-host]" in result.stdout


# ---------------------------------------------------------------------------
# Placeholders and known false alarms stay quiet
# ---------------------------------------------------------------------------

PLACEHOLDER_LINES = [
    'token = "<your-token>"',
    'api_key = "${API_KEY}"',
    'secret = "your-secret-value-here"',
    'api_key = "' + "x" * 24 + '"',
    'password = "changeme"',
    'api_key = "example-api-key-12345678"',
    'token = "dummy-token-value-1234"',
    'secret = "fake-secret-value-1234"',
    'password = "short"',
    "postgresql://" + "user:password@localhost/db",
    "postgres://" + "user:${DB_PASSWORD}@host/db",
    "postgresql://" + "postgres:postgres@localhost:5432/db",
    "postgresql://" + "app:app@localhost/app",
    "http://localhost:3000/@vite/client",
    "key " + "s" + "k-" + "x" * 30,
    "AK" + "IAIOSFODNN7EXAMPLE",
    "ssh root@<server-ip>",
    "ssh git@github.com",
    "clone git@github.com:owner/repository.git",
    HOME_ROOT + "<user>/project",
    HOME_ROOT + ".../project",
    "/hom" + "e/runner/work/repository",
    "C:" + "\\Us" + "ers\\runner\\work",
    "write to owner@example.com or a@example.org",
    "Co-Authored-By: someone <noreply@anthropic.com>",
    "identity " + NOREPLY,
    "reserved mailbox tester@example.invalid",
    "loopback 127.0.0.1 any 0.0.0.0 broadcast 255.255.255.255",
    "documentation 192.0.2.10 and 198.51.100.7 and 203.0.113.9",
    "asset logo@2x.png",
    "version 300.400.1.2 is not an address",
    "::1 and fe80::1 and 2001:db8::1 and 12:30:45 and aa:bb:cc:dd:ee:ff and x[1::2]",
    "std::vector and Foo::Bar::baz",
    'autoComplete: "current-password",',
    "  password: formValues.password,",
    "password = request.form",
]

# A16 J20: lines this repository already carries, each once a false alarm.
FALSE_ALARM_LINES = {
    "svg-path": '<path d="M8 1.2 15 14H1L8 1.2Zm0 4.3a.8.8 0 0 0-.8.8v3a.8.8 0 0 0 1.6 0'
    'v-3a.8.8 0 0 0-.8-.8Zm0 6.2a.9.9 0 1 0 0 1.8.9.9 0 0 0 0-1.8Z"/>',
    "section-number": "see Section 5.2.2.3 of the specification",
    "section-number-wide": "Section 12.4.10.3 applies",
    "python-version": "Requires Python 3.11.4.1",
    "numbered-clauses": "clauses 4.2.1.3 and 4.2.1.4 cover it",
    "cidr-range": "the 10.0.0.0/8 and 192.168.0.0/16 ranges, and 10/8 in short",
    "role-addresses": "contact eutilities"
    + "@ncbi.nlm.nih.gov, support"
    + "@nih.gov or help"
    + "@ncbi.nlm.nih.gov",
    "placeholder-addresses": "you@institute.edu, x@x.com and my@email.com",
    "storage-key-name": 'export const TOUR_SEEN_KEY = "agentic-search-ui.tour-seen.v1";',
    "eval-key-field": '"key": "q4_caffeine_papers"',
    "sql-token-hash": "refresh_token_hash = 'quarantined-0002:'",
    "integrity-hash": 'integrity_key = "sha256-' + TAIL[:43] + '"',
    "env-name-to-env-name": "SECRET_KEY_2 = OTHER_SECRET_NAME_3",
    "leak-canary": 'secret = "SUPER-' + 'SECRET-NCBI-KEY-24601"',
    "obvious-test-password": 'const TEST_PASSWORD = "Str0ng' + 'Passw0rd!";',
    "schema-regex": '"pattern": "^https://(?:([A-Za-z0-9-]+\\\\.)*ncbi\\\\.nlm\\\\.nih\\\\.gov/)[A-Za-z0-9:/?#\\\\[\\\\]@!$&]*$"',
    "credential-for-a-test-host": "https://al:" + "ice:hun@ter2@example.test:8443/",
    "manifest-keyed-by-file": '"tests/fixtures/test_pass' + 'words.py": "' + "0a1b2c3d" * 8 + '"',
}


@pytest.mark.parametrize("line", PLACEHOLDER_LINES)
def test_placeholder_does_not_fire(repo: Path, line: str) -> None:
    commit_file(repo, "docs/notes.txt", f"{line}\n")
    result = scan(repo)
    assert result.returncode == 0, f"{line!r} fired:\n{result.stdout}"


@pytest.mark.parametrize("line", FALSE_ALARM_LINES.values(), ids=FALSE_ALARM_LINES.keys())
def test_known_false_alarm_does_not_fire(repo: Path, line: str) -> None:
    """A16 J20: SVG path data, section numbers, CIDR ranges, role addresses, storage keys."""
    commit_file(repo, "docs/notes.txt", f"{line}\n")
    result = scan(repo)
    assert result.returncode == 0, f"{line!r} fired:\n{result.stdout}"


# ---------------------------------------------------------------------------
# The allow marker
# ---------------------------------------------------------------------------


def test_allow_marker_exempts_a_private_value_on_its_line(repo: Path) -> None:
    commit_file(repo, "docs/notes.txt", f"mail {planted('personal-email')} # local-refs: allow\n")
    assert scan(repo).returncode == 0


def test_allow_marker_only_exempts_its_own_line(repo: Path) -> None:
    text = f"mail {planted('personal-email')} local-refs: allow\nmail {planted('personal-email')}\n"
    commit_file(repo, "docs/notes.txt", text)
    result = scan(repo)
    assert result.returncode == 1
    assert "docs/notes.txt:2 [personal-email]" in result.stdout
    assert "docs/notes.txt:1 " not in result.stdout


@pytest.mark.parametrize("kind", SECRET_KINDS)
def test_allow_marker_never_exempts_a_secret(repo: Path, kind: str) -> None:
    """J12 A11: a secret can only be removed, never marked."""
    commit_file(repo, "docs/notes.txt", f"{planted(kind)}  # local-refs: allow\n")
    result = scan(repo)
    assert result.returncode == 1, result.stdout
    assert f"[{CATEGORY[kind]}]" in result.stdout


@pytest.mark.parametrize("ending", ["\r", "\r\n"], ids=["cr-only", "crlf"])
def test_allow_marker_covers_one_physical_line_whatever_the_line_endings(
    repo: Path, ending: str
) -> None:
    """A10: a CR-only file once let one marker exempt every line in it."""
    lines = [
        "note local-refs: allow",
        f"mail {planted('personal-email')}",
        f"ip {planted('ipv4-ten')}",
    ]
    commit_file(repo, "old.txt", ending.join(lines).encode() + ending.encode())
    result = scan(repo)
    assert result.returncode == 1, result.stdout
    assert "[personal-email]" in result.stdout
    assert "[ipv4-address]" in result.stdout


# ---------------------------------------------------------------------------
# Every commit in the range, not the net diff
# ---------------------------------------------------------------------------


def test_value_added_then_removed_in_a_later_commit_is_found(repo: Path) -> None:
    """J02 A03 A21: the push still publishes the first commit."""
    sha = commit_file(repo, "conf.txt", f"cfg {planted('aws-access-key')}\n")
    commit_file(repo, "conf.txt", "cfg clean\n", message="chore: remove the key")
    result = scan(repo)
    assert result.returncode == 1, result.stdout
    assert f"commit {sha[:8]} conf.txt:1 [aws-access-key]" in result.stdout
    assert "take it out of that commit" in result.stdout
    assert "git reset --soft" in result.stdout


def test_file_added_then_deleted_is_found(repo: Path) -> None:
    """A03: `git rm` in a later commit does not unpublish the first one."""
    sha = commit_file(repo, "cfg.txt", f"key {planted('aws-access-key')}\n")
    git(repo, "rm", "-q", "cfg.txt")
    git(repo, "commit", "-q", "-m", "chore: drop it")
    result = scan(repo)
    assert f"commit {sha[:8]} cfg.txt:1 [aws-access-key]" in result.stdout


def test_a_change_made_only_in_a_merge_commit_is_found(repo: Path) -> None:
    """J02: a merge's own change is read through its remerge diff."""
    git(repo, "checkout", "-q", "-b", "side")
    commit_file(repo, "side.txt", "side\n")
    git(repo, "checkout", "-q", "main")
    commit_file(repo, "main.txt", "main\n")
    git(repo, "merge", "-q", "--no-ff", "--no-commit", "side")
    (repo / "main.txt").write_text(f"main\n{planted('personal-email')}\n")
    git(repo, "add", "main.txt")
    git(repo, "commit", "-q", "-m", "merge side")
    merge = git(repo, "rev-parse", "HEAD")
    result = scan(repo)
    assert result.returncode == 1, result.stdout
    assert f"commit {merge[:8]} main.txt:2 [personal-email]" in result.stdout


def test_staged_value_cleaned_only_in_the_working_copy_is_found(repo: Path) -> None:
    """A18: the next commit carries the index, not the working file."""
    (repo / "s.txt").write_text(f"k {planted('aws-access-key')}\n")
    git(repo, "add", "s.txt")
    (repo / "s.txt").write_text("clean\n")
    result = scan(repo)
    assert result.returncode == 1
    assert "s.txt:1 [aws-access-key]" in result.stdout


# ---------------------------------------------------------------------------
# The base is fetched first
# ---------------------------------------------------------------------------


def _clone_pair(tmp_path: Path) -> tuple[Path, Path, Path]:
    (tmp_path / "home").mkdir(exist_ok=True)
    seed = tmp_path / "seed"
    seed.mkdir()
    git(seed, "init", "-q", "-b", "develop")
    (seed / "README.md").write_text("# fixture\n")
    git(seed, "add", "README.md")
    git(seed, "commit", "-q", "-m", "docs: start")
    bare = tmp_path / "remote.git"
    subprocess.run(
        ["git", "clone", "-q", "--bare", str(seed), str(bare)],
        check=True,
        env=_env(tmp_path),
        capture_output=True,
    )
    first, second = tmp_path / "first", tmp_path / "second"
    for clone in (first, second):
        subprocess.run(
            ["git", "clone", "-q", str(bare), str(clone)],
            check=True,
            env=_env(tmp_path),
            capture_output=True,
        )
    return bare, first, second


def _scan_default(clone: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--allow-missing-private-check", *args],
        cwd=clone,
        capture_output=True,
        text=True,
        env=_env(clone.parent),
        check=False,
    )


def test_stale_base_after_a_force_push_is_fetched_first(tmp_path: Path) -> None:
    """J11: a commit removed from the remote on purpose would be pushed again."""
    _, first, second = _clone_pair(tmp_path)
    sha = commit_file(first, "leak.txt", f"{planted('aws-access-key')}\n")
    git(first, "push", "-q", "origin", "develop")
    # The second clone never saw that commit; its force-push takes it off the remote.
    git(second, "push", "-q", "--force", "origin", "develop")
    commit_file(first, "next.txt", "clean\n")
    stale = _scan_default(first, "--no-fetch")
    assert stale.returncode == 0, stale.stdout
    fetched = _scan_default(first)
    assert fetched.returncode == 1, fetched.stdout + fetched.stderr
    assert f"commit {sha[:8]} leak.txt:1 [aws-access-key]" in fetched.stdout


def test_branch_with_no_upstream_is_scanned_against_the_fetched_base(tmp_path: Path) -> None:
    """J11: a brand new branch has no upstream; the base still sets the range."""
    _, first, _ = _clone_pair(tmp_path)
    git(first, "checkout", "-q", "-b", "feature")
    commit_file(first, "a.txt", f"{planted('personal-email')}\n")
    result = _scan_default(first)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "a.txt:1 [personal-email]" in result.stdout
    assert "against origin/develop" in result.stdout


def test_fetch_that_fails_is_exit_two_and_names_the_way_out(tmp_path: Path) -> None:
    _, first, _ = _clone_pair(tmp_path)
    git(first, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    result = _scan_default(first)
    assert result.returncode == 2
    assert "--no-fetch" in result.stderr


# ---------------------------------------------------------------------------
# Nothing passes unread
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("filler", [20_001, 150_000])
def test_value_deep_in_a_long_line_is_found(repo: Path, filler: int) -> None:
    """J03 A07: no line is cut short."""
    commit_file(
        repo, "min.json", '{"a":"' + "b" * filler + '","k":"' + planted("aws-access-key") + '"}\n'
    )
    result = scan(repo)
    assert result.returncode == 1, result.stdout
    assert "min.json:1 [aws-access-key]" in result.stdout


def test_committed_text_file_over_the_limit_fails(repo: Path) -> None:
    """J04 A04: too large to read is a failure, never a pass."""
    commit_file(repo, "big.log", "a line of log text\n" * 130_000)
    result = scan(repo)
    assert result.returncode == 1
    assert "TOO LARGE" in result.stdout and "big.log" in result.stdout
    assert "shrink or split" in result.stdout
    assert "PASS: nothing" not in result.stdout


def test_untracked_text_file_over_the_limit_fails(repo: Path) -> None:
    (repo / "big.txt").write_text("a" * (2 * 1024 * 1024 + 10))
    result = scan(repo)
    assert result.returncode == 1
    assert "TOO LARGE big.txt" in result.stdout


def test_committed_content_is_read_even_when_the_working_copy_grew(repo: Path) -> None:
    """A20: the size that counts is what the commit carries."""
    sha = commit_file(repo, "run.log", f"k {planted('aws-access-key')}\n")
    with (repo / "run.log").open("a") as handle:
        handle.write("x" * (2 * 1024 * 1024 + 10) + "\n")
    result = scan(repo)
    assert f"commit {sha[:8]} run.log:1 [aws-access-key]" in result.stdout


@pytest.mark.parametrize("where", ["commit", "untracked"])
def test_text_with_a_nul_byte_is_read(repo: Path, where: str) -> None:
    """J05 A06 J16: a stray NUL made git call the file binary."""
    data = b"head\0\n" + f"cfg {planted('aws-access-key')}\n".encode()
    if where == "commit":
        commit_file(repo, "dump.txt", data)
    else:
        (repo / "dump.txt").write_bytes(data)
    result = scan(repo)
    assert result.returncode == 1, result.stdout
    assert "dump.txt:2 [aws-access-key]" in result.stdout  # read as text, line by line
    assert "NOT SCANNED" not in result.stdout


@pytest.mark.parametrize("codec", ["utf-16", "utf-16-le"])
def test_utf16_file_is_decoded_and_read(repo: Path, codec: str) -> None:
    """A06: Windows editors and PowerShell write UTF-16."""
    commit_file(repo, "u16.txt", f"key {planted('aws-access-key')}\n".encode(codec))
    result = scan(repo)
    assert result.returncode == 1, result.stdout
    assert "u16.txt:1 [aws-access-key]" in result.stdout


def test_gitattributes_cannot_hide_a_file(repo: Path) -> None:
    """J06 A17: `-diff` and `binary` change what git shows, not what a push sends."""
    (repo / ".gitattributes").write_text("*.cfg -diff\n*.ipynb binary\n")
    (repo / "app.cfg").write_text(f"cfg {planted('aws-access-key')}\n")
    (repo / "nb.ipynb").write_text('{"k": "' + planted("github-token") + '"}\n')
    git(repo, "add", ".gitattributes", "app.cfg", "nb.ipynb")
    git(repo, "commit", "-q", "-m", "chore: add")
    result = scan(repo)
    assert "app.cfg:1 [aws-access-key]" in result.stdout
    assert "nb.ipynb:1 [github-token]" in result.stdout


@pytest.mark.parametrize("name", ["notes.pdf", "cache.db", "logo.png"])
def test_text_under_a_binary_name_is_read(repo: Path, name: str) -> None:
    """A05: the content decides, not the name."""
    commit_file(repo, name, f"key {planted('aws-access-key')}\n")
    result = scan(repo)
    assert result.returncode == 1
    assert f"{name}:1 [aws-access-key]" in result.stdout


def test_real_binary_is_listed_for_a_person_and_its_text_runs_are_read(repo: Path) -> None:
    """A05: an image cannot be read, so a person is told to look; embedded text is still read."""
    image = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 40
    commit_file(repo, "shot.png", image)
    clean = scan(repo)
    assert clean.returncode == 0, clean.stdout
    assert "NOT SCANNED" in clean.stdout and "shot.png" in clean.stdout
    assert "a person must look at it" in clean.stdout
    database = (
        b"SQLite format 3\0"
        + bytes(300)
        + f"row {planted('aws-access-key')} end".encode()
        + bytes(300)
    )
    commit_file(repo, "rows.sqlite", database)
    result = scan(repo)
    assert result.returncode == 1
    assert "rows.sqlite (binary, text run" in result.stdout


# ---------------------------------------------------------------------------
# File and directory names
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("where", ["commit", "untracked"])
def test_file_and_directory_names_are_scanned_and_hidden(repo: Path, where: str) -> None:
    """J07 A08: a path is published exactly like content."""
    name = f"mail/{planted('personal-email')}/notes.txt"
    if where == "commit":
        commit_file(repo, name, "clean\n")
    else:
        (repo / "mail" / planted("personal-email")).mkdir(parents=True)
        (repo / name).write_text("clean\n")
    result = scan(repo)
    assert result.returncode == 1, result.stdout
    assert "[personal-email]" in result.stdout
    assert "file name <file name hidden" in result.stdout
    assert no_run_of(planted("personal-email"), result.stdout) == []


@pytest.mark.parametrize(
    "name",
    ["Us" + "ers/jdoe42/notes.txt", planted("ipv4-ten") + "_ssh_login.txt"],
    ids=["home-folder", "address"],
)
def test_other_revealing_file_names_fire(repo: Path, name: str) -> None:
    commit_file(repo, name, "clean\n")
    result = scan(repo)
    assert result.returncode == 1, result.stdout


# ---------------------------------------------------------------------------
# Commit messages, identity, and what is deliberately not read
# ---------------------------------------------------------------------------


def test_commit_message_is_scanned(repo: Path) -> None:
    commit_file(
        repo, "a.txt", "clean\n", message=f"chore: note\n\nreach me at {planted('personal-email')}"
    )
    result = scan(repo)
    assert result.returncode == 1
    assert "message:3 [personal-email]" in result.stdout


@pytest.mark.parametrize("role", ["AUTHOR", "COMMITTER"])
def test_non_noreply_identity_is_a_finding(repo: Path, role: str) -> None:
    commit_file(repo, "a.txt", "clean\n", **{f"GIT_{role}_EMAIL": planted("personal-email")})
    result = scan(repo)
    assert result.returncode == 1
    assert "[identity-email]" in result.stdout
    assert planted("personal-email") not in result.stdout


def test_author_display_name_is_not_scanned(repo: Path) -> None:
    """A12, by decision: the owner's name is public, and other names cannot be listed here."""
    commit_file(repo, "a.txt", "clean\n", GIT_AUTHOR_NAME="Zelda Quentin-Realname")
    assert scan(repo).returncode == 0


@pytest.mark.parametrize("byte", ["\x1e", "\x1f", "\x07", "\x1b"])
def test_control_bytes_in_a_message_cannot_crash_the_scan(repo: Path, byte: str) -> None:
    """J08: a record separator in a message once raised a traceback read as a finding."""
    commit_file(repo, "a.txt", "clean\n", message=f"chore: add\n\nrecord{byte}separator")
    result = scan(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Traceback" not in result.stderr


def test_noreply_identity_is_clean(repo: Path) -> None:
    commit_file(repo, "a.txt", "clean\n")
    assert scan(repo).returncode == 0


def test_a_commit_before_the_base_is_out_of_range(repo: Path) -> None:
    (repo / "old.txt").write_text(f"{planted('personal-email')}\n")
    git(repo, "add", "old.txt")
    git(
        repo,
        "commit",
        "-q",
        "-m",
        "chore: old",
        "--author",
        f"Tester <{planted('personal-email')}>",
    )
    git(repo, "tag", "-f", "base")
    assert scan(repo).returncode == 0


def test_untracked_file_is_scanned_whole(repo: Path) -> None:
    (repo / "new.txt").write_text(f"a\nb\n{planted('github-token')}\n")
    result = scan(repo)
    assert result.returncode == 1
    assert "new.txt:3 [github-token]" in result.stdout


def test_unstaged_change_to_a_tracked_file_is_scanned(repo: Path) -> None:
    (repo / "README.md").write_text(f"# fixture\n{planted('personal-email')}\n")
    result = scan(repo)
    assert result.returncode == 1
    assert "README.md:2 [personal-email]" in result.stdout


def test_a_line_removed_beside_an_added_one_keeps_its_line_number(repo: Path) -> None:
    commit_file(repo, "conf.txt", "one\ntwo\nthree\n")
    (repo / "conf.txt").write_text(f"one\n{planted('personal-email')}\nthree\n")
    git(repo, "add", "conf.txt")
    git(repo, "commit", "-q", "-m", "chore: edit")
    result = scan(repo)
    assert "conf.txt:2 [personal-email]" in result.stdout


# ---------------------------------------------------------------------------
# Exit codes, timeouts and crashes
# ---------------------------------------------------------------------------


def test_exit_zero_when_clean(repo: Path) -> None:
    commit_file(repo, "a.txt", "nothing private here\n")
    result = scan(repo)
    assert result.returncode == 0
    assert "PASS" in result.stdout


def test_exit_two_outside_a_git_repository(tmp_path: Path) -> None:
    empty = tmp_path / "not_a_repo"
    empty.mkdir()
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=empty,
        capture_output=True,
        text=True,
        env=_env(tmp_path),
        check=False,
    )
    assert result.returncode == 2
    assert "not a git repository" in result.stderr


def test_exit_two_when_the_base_is_missing(repo: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", "origin/develop", "--allow-missing-private-check"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=_env(repo.parent),
        check=False,
    )
    assert result.returncode == 2
    assert "git fetch origin" in result.stderr


def test_default_base_is_origin_develop(tmp_path: Path) -> None:
    _, first, _ = _clone_pair(tmp_path)
    commit_file(first, "a.txt", f"{planted('personal-email')}\n")
    result = _scan_default(first)
    assert result.returncode == 1
    assert "against origin/develop" in result.stdout


def test_every_subprocess_call_has_a_timeout() -> None:
    """J01: a git lock or a credential prompt must not hang /ship."""
    tree = ast.parse(SCRIPT.read_text())
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in ("run", "Popen", "check_output", "call")
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
    ]
    assert calls
    assert all(any(k.arg == "timeout" for k in call.keywords) for call in calls)


def test_a_git_timeout_is_exit_two(repo: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """J01: a timeout says what to do next and is never read as a finding."""

    def hang(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout", 0))

    monkeypatch.setattr(leaks.subprocess, "run", hang)
    code = leaks.main(["--base", "base", "--allow-missing-private-check"], cwd=repo)
    assert code == 2
    assert "took longer than" in capsys.readouterr().err


def test_an_internal_error_is_exit_two(repo: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """J08: a crash is 'could not run', never 'a finding'."""

    def broken(*args, **kwargs):
        raise ValueError("boom " + planted("personal-email"))

    monkeypatch.setattr(leaks, "run_scan", broken)
    code = leaks.main(["--base", "base", "--allow-missing-private-check"], cwd=repo)
    err = capsys.readouterr().err
    assert code == 2
    assert "internal error (ValueError)" in err
    assert planted("personal-email") not in err


# ---------------------------------------------------------------------------
# The machine-local private-name check
# ---------------------------------------------------------------------------


def test_missing_private_check_fails_closed(repo: Path) -> None:
    commit_file(repo, "a.txt", "clean\n")
    result = scan(repo, allow_missing=False)
    assert result.returncode == 1
    assert "private-name check NOT RUN on this machine:" in result.stdout


def test_missing_private_check_can_be_allowed(repo: Path) -> None:
    commit_file(repo, "a.txt", "clean\n")
    result = scan(repo, allow_missing=True)
    assert result.returncode == 0
    assert "private-name check NOT RUN on this machine:" in result.stdout


def test_hook_naming_a_missing_script_is_not_run(repo: Path) -> None:
    commit_file(repo, "a.txt", "clean\n")
    directory = install_check(repo)
    (directory / "verify_no_local_refs.py").unlink()
    result = scan(repo, allow_missing=False)
    assert result.returncode == 1
    assert "does not exist" in result.stdout


def test_private_check_that_passes_is_reported(repo: Path) -> None:
    commit_file(repo, "a.txt", "clean\n")
    install_check(repo)
    result = scan(repo, allow_missing=False)
    assert result.returncode == 0, result.stdout
    assert "private-name check: PASS" in result.stdout


def test_private_check_runs_in_message_and_all_modes(repo: Path) -> None:
    """J10 J16: the check reads the outgoing lines and the whole tree, never an empty staged diff."""
    commit_file(repo, "a.txt", "clean\n")
    directory = install_check(repo)
    scan(repo, allow_missing=False)
    calls = (directory / "calls.log").read_text().split()
    assert calls == ["--message", "--all"]


@pytest.mark.parametrize(
    "where", ["content", "message", "untracked", "file-name", "hash-line", "removed-later"]
)
def test_private_check_sees_every_outgoing_line(repo: Path, where: str) -> None:
    """J10 A13: a name in a commit made with --no-verify, a message, a new file or a name."""
    if where == "content":
        commit_file(repo, "a.txt", f"by {OWNER_TERM}\n")
    elif where == "message":
        commit_file(repo, "a.txt", "clean\n", message=f"chore: note\n\nfrom {OWNER_TERM}")
    elif where == "untracked":
        (repo / "loose.txt").write_text(f"{OWNER_TERM}\n")
    elif where == "file-name":
        commit_file(repo, f"notes_{OWNER_TERM}.txt", "clean\n")
    elif where == "hash-line":
        (repo / "loose.md").write_text(f"# heading by {OWNER_TERM}\n")  # only --message sees it
    else:
        commit_file(repo, "a.txt", f"by {OWNER_TERM}\n")
        commit_file(repo, "a.txt", "clean\n", message="chore: tidy")
    install_check(repo)
    result = scan(repo, allow_missing=False)
    assert result.returncode == 1, result.stdout
    assert "FAIL private-name check:" in result.stdout
    assert "[owner-term]" in result.stdout
    assert OWNER_TERM not in result.stdout + result.stderr


def test_private_check_finding_already_on_the_base_says_so(repo: Path) -> None:
    (repo / "old.md").write_text(f"{OWNER_TERM}\n")
    git(repo, "add", "old.md")
    git(repo, "commit", "-q", "-m", "chore: old")
    git(repo, "tag", "-f", "base")
    install_check(repo)
    result = scan(repo, allow_missing=False)
    assert result.returncode == 1
    assert "old.md:1 [owner-term] (already on the base" in result.stdout


@pytest.mark.parametrize(
    "exec_line",
    [
        'exec python3 "{dir}/unrelated_lint.py" "$@"',
        'python3 "{dir}/verify_no_local_refs.py" --staged || exit 1\nexec python3 "{dir}/unrelated_lint.py"',
        'exec python3 "{dir}/linked_as_the_check.py" --staged',
    ],
    ids=["other-script", "not-on-the-exec-line", "wrongly-named-link"],
)
def test_only_verify_no_local_refs_on_the_exec_line_is_trusted(repo: Path, exec_line: str) -> None:
    """A14: an unrelated script that exits 0 once read as 'private-name check: PASS'."""
    commit_file(repo, "a.txt", f"by {OWNER_TERM}\n")
    directory = install_check(repo)
    (directory / "unrelated_lint.py").write_text("print('formatted')\n")
    (directory / "linked_as_the_check.py").symlink_to(directory / "unrelated_lint.py")
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\n" + exec_line.format(dir=directory) + "\n")
    result = scan(repo, allow_missing=False)
    assert result.returncode == 1
    assert "private-name check NOT RUN" in result.stdout
    assert "private-name check: PASS" not in result.stdout


def test_a_link_to_the_check_through_a_quoted_path_with_spaces_is_trusted(repo: Path) -> None:
    commit_file(repo, "a.txt", "clean\n")
    directory = install_check(repo, folder="dir with spaces")
    (directory / "hooklink.py").symlink_to(directory / "verify_no_local_refs.py")
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(f'#!/bin/sh\nexec python3 "{directory}/hooklink.py" --staged\n')
    result = scan(repo, allow_missing=False)
    assert result.returncode == 0, result.stdout
    assert "private-name check: PASS" in result.stdout


@pytest.mark.parametrize("exit_code", [1, 3])
def test_private_check_raw_output_is_never_relayed(repo: Path, exit_code: int) -> None:
    """A15 J16: a crash prints its source line and a home path; neither may be relayed."""
    commit_file(repo, "a.txt", "clean\n")
    fake_home = HOME_ROOT + "jdoe42/private/check.py"
    body = (
        "import sys\n"
        f'print(\'Traceback: File "{fake_home}", line 9, TERMS = {{"{OWNER_TERM}": 1}}\', file=sys.stderr)\n'
        f"sys.exit({exit_code})\n"
    )
    install_check(repo, body)
    result = scan(repo, allow_missing=False)
    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "private-name check NOT RUN" in output
    assert OWNER_TERM not in output
    assert "jdoe42" not in output


def test_private_check_that_cannot_check_counts_as_not_run(repo: Path) -> None:
    commit_file(repo, "a.txt", "clean\n")
    install_check(repo, "import sys\nsys.exit(2)\n")
    assert scan(repo, allow_missing=False).returncode == 1
    assert scan(repo, allow_missing=True).returncode == 0


def test_private_check_is_found_from_a_linked_worktree(repo: Path) -> None:
    commit_file(repo, "a.txt", "clean\n")
    install_check(repo)
    linked = repo.parent / "linked"
    git(repo, "worktree", "add", "-q", "-b", "side", str(linked))
    result = scan(linked, allow_missing=False)
    assert result.returncode == 0, result.stdout
    assert "private-name check: PASS" in result.stdout


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------


def test_placeholder_rules() -> None:
    assert leaks.is_placeholder("short")
    assert leaks.is_placeholder("<your-token>")
    assert leaks.is_placeholder("${SECRET_VALUE}")
    assert leaks.is_placeholder("your-api-key-here")
    assert not leaks.is_placeholder("a8Kd93jLq0Zx7MvB2nRt")


def test_scan_line_exempts_only_private_values_on_an_allowed_line() -> None:
    assert leaks.scan_line(f"{planted('personal-email')} local-refs: allow") == []
    hits = leaks.scan_line(f"{planted('aws-access-key')} local-refs: allow")
    assert [category for category, _ in hits] == ["aws-access-key"]
