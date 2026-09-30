"""Run the /ship public-leak scan the way /ship does, against throwaway repositories.

`.claude/skills/ship/scripts/check_public_leaks.py` scans what a push would
publish: the added lines of `<base>...HEAD`, the staged and unstaged diff, every
untracked file, every commit message and every author and committer email. It
exits 1 on a finding, 2 when it could not run, and 0 when clean.

WHAT THIS COVERS, stated so a gap is arguable rather than discovered:

    Covered      Every category fires on a planted value; every placeholder
                 stays quiet; the allow marker exempts a line; a matched value
                 is never printed in full; exit codes 0, 1 and 2; the source
                 that carries each value (commit, working tree, untracked,
                 commit message, identity); the machine-local private-name
                 check found through the hook's exec line, absent, failing and
                 not runnable.
    Not covered  The owner's real private-name check. It cannot live in this
                 public repository, so a stand-in script plays its part.

Every planted value is assembled from parts at run time. No real-looking secret
is committed, and this file must pass the scan it tests.

MUTATION PROOF: set CHECK_PUBLIC_LEAKS_SCRIPT to a copy of the script with one
detector disabled, and the tests for that category must go red. The run and its
results are recorded in the builder report of 2026-09-29_ship_leak_scan.
"""

from __future__ import annotations

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
    values = {
        "private-key": f"{dashes}BEGIN RSA " + "PRIVATE" + f" KEY{dashes}",
        "aws-access-key": "AK" + "IA" + "QW3ERTY5UIOP7ASD",
        "github-token": "gh" + "p_" + TAIL[:36],
        "provider-api-key": "s" + "k-" + TAIL[:32],
        "slack-token": "xo" + "xb-1234567890-" + "abcdefghij",
        "google-api-key": "AI" + "za" + TAIL[:35],
        "jwt": "ey"
        + "JhbGciOiJIUzI1NiJ9."
        + "ey"
        + "JzdWIiOiIxMjM0NTY3ODkwIn0."
        + "dBjftJeZ4CVPmB92K27u",
        "bearer-token": "Bearer " + TAIL[:24],
        "url-password": "postgresql://"
        + "appuser"
        + ":"
        + "Zq8"
        + "vR2xT9mK"
        + "@db.internal.test:5432/x",
        "secret-assignment": "api" + "_key = " + '"' + "a8Kd93jLq0Zx7MvB2nRt" + '"',
        "local-path": "/Us" + "ers/" + "jdoe42" + "/project/x.py",
        "personal-email": "jdoe42" + "@" + "gmail.com",
        "ipv4-address": "172." + "16.4.9",
        "ssh-host": "ssh " + "deploy" + "@" + "build-box.corp.internal",
    }
    return values[kind]


def secret_of(kind: str) -> str:
    """The part of a planted value that must never appear in the output."""
    value = planted(kind)
    if kind == "url-password":
        return "Zq8" + "vR2xT9mK"
    if kind == "secret-assignment":
        return "a8Kd93jLq0Zx7MvB2nRt"
    if kind == "bearer-token":
        return value.split(" ", 1)[1]
    if kind == "local-path":
        return "jdoe42"
    if kind == "ssh-host":
        return "build-box.corp.internal"
    return value


ALL_KINDS = [
    "private-key",
    "aws-access-key",
    "github-token",
    "provider-api-key",
    "slack-token",
    "google-api-key",
    "jwt",
    "bearer-token",
    "url-password",
    "secret-assignment",
    "local-path",
    "personal-email",
    "ipv4-address",
    "ssh-host",
]


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
    repo: Path, name: str, text: str, message: str = "chore: add file", **extra: str
) -> None:
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", message, **extra)


def scan(repo: Path, *args: str, allow_missing: bool = True) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT), "--base", "base", *args]
    if allow_missing:
        command.append("--allow-missing-private-check")
    return subprocess.run(
        command, cwd=repo, capture_output=True, text=True, env=_env(repo.parent), check=False
    )


def write_private_hook(repo: Path, script_body: str | None, *, script_exists: bool = True) -> None:
    """Install a stand-in machine-local check and a hook whose exec line names it."""
    script = repo.parent / "stand_in_check.py"
    if script_body is not None and script_exists:
        script.write_text(script_body)
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(exist_ok=True)
    hook = hooks / "pre-commit"
    hook.write_text(f'#!/bin/sh\n# local only\nexec python3 "{script}" --staged\n')
    hook.chmod(0o755)


# ---------------------------------------------------------------------------
# Every category fires on a planted value, and the value is never printed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_category_fires_from_a_commit(repo: Path, kind: str) -> None:
    commit_file(repo, "docs/notes.txt", f"first line\nvalue: {planted(kind)}\n")
    result = scan(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"docs/notes.txt:2 [{kind}]" in result.stdout


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_output_never_carries_the_full_value(repo: Path, kind: str) -> None:
    commit_file(repo, "docs/notes.txt", f"value: {planted(kind)}\n")
    result = scan(repo)
    output = result.stdout + result.stderr
    secret = secret_of(kind)
    assert secret not in output
    assert planted(kind) not in output
    if len(secret) > 8:
        assert secret[1:7] not in output


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


@pytest.mark.parametrize(
    "path",
    [
        "/hom" + "e/jdoe42/repo/file.py",
        "C:" + "\\Us" + "ers\\jdoe42\\repo\\file.py",
    ],
)
def test_other_local_path_shapes_fire(repo: Path, path: str) -> None:
    commit_file(repo, "a.txt", f"see {path}\n")
    result = scan(repo)
    assert result.returncode == 1
    assert "[local-path]" in result.stdout


# ---------------------------------------------------------------------------
# Placeholders stay quiet
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
    "key " + "s" + "k-" + "x" * 30,
    "AK" + "IAIOSFODNN7EXAMPLE",
    "ssh root@<server-ip>",
    "ssh git@github.com",
    "clone git@github.com:owner/repository.git",
    "/Us" + "ers/<user>/project",
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
]


@pytest.mark.parametrize("line", PLACEHOLDER_LINES)
def test_placeholder_does_not_fire(repo: Path, line: str) -> None:
    commit_file(repo, "docs/notes.txt", f"{line}\n")
    result = scan(repo)
    assert result.returncode == 0, f"{line!r} fired:\n{result.stdout}"


# ---------------------------------------------------------------------------
# The allow marker
# ---------------------------------------------------------------------------


def test_allow_marker_exempts_a_line(repo: Path) -> None:
    commit_file(repo, "docs/notes.txt", f"mail {planted('personal-email')} # local-refs: allow\n")
    assert scan(repo).returncode == 0


def test_allow_marker_only_exempts_its_own_line(repo: Path) -> None:
    text = f"mail {planted('personal-email')} local-refs: allow\nmail {planted('personal-email')}\n"
    commit_file(repo, "docs/notes.txt", text)
    result = scan(repo)
    assert result.returncode == 1
    assert "docs/notes.txt:2 [personal-email]" in result.stdout
    assert "docs/notes.txt:1 " not in result.stdout


# ---------------------------------------------------------------------------
# Where a value can hide
# ---------------------------------------------------------------------------


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


def test_staged_change_is_scanned(repo: Path) -> None:
    (repo / "README.md").write_text(f"# fixture\n{planted('aws-access-key')}\n")
    git(repo, "add", "README.md")
    result = scan(repo)
    assert result.returncode == 1
    assert "[aws-access-key]" in result.stdout


def test_a_line_removed_beside_an_added_one_keeps_its_line_number(repo: Path) -> None:
    commit_file(repo, "conf.txt", "one\ntwo\nthree\n")
    (repo / "conf.txt").write_text(f"one\n{planted('personal-email')}\nthree\n")
    git(repo, "add", "conf.txt")
    git(repo, "commit", "-q", "-m", "chore: edit")
    result = scan(repo)
    assert "conf.txt:2 [personal-email]" in result.stdout


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


def test_binary_file_is_skipped_by_name(repo: Path) -> None:
    (repo / "logo.png").write_text(f"{planted('personal-email')}\n")
    result = scan(repo)
    assert result.returncode == 0
    assert "1 binary file(s) skipped by name" in result.stdout


def test_oversized_file_is_reported_not_silently_skipped(repo: Path) -> None:
    (repo / "big.txt").write_text("a" * (2 * 1024 * 1024 + 10))
    result = scan(repo)
    assert "NOT SCANNED big.txt" in result.stdout
    assert "1 file(s) not scanned" in result.stdout


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------


def test_exit_zero_when_clean(repo: Path) -> None:
    commit_file(repo, "a.txt", "nothing private here\n")
    result = scan(repo)
    assert result.returncode == 0
    assert "PASS" in result.stdout


def test_exit_one_when_a_finding_exists(repo: Path) -> None:
    commit_file(repo, "a.txt", f"{planted('jwt')}\n")
    assert scan(repo).returncode == 1


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
    (tmp_path / "home").mkdir()
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git(upstream, "init", "-q", "-b", "develop")
    (upstream / "README.md").write_text("# fixture\n")
    git(upstream, "add", "README.md")
    git(upstream, "commit", "-q", "-m", "docs: start")
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "-q", str(upstream), str(clone)],
        check=True,
        env=_env(tmp_path),
        capture_output=True,
    )
    commit_file(clone, "a.txt", f"{planted('personal-email')}\n")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--allow-missing-private-check"],
        cwd=clone,
        capture_output=True,
        text=True,
        env=_env(tmp_path),
        check=False,
    )
    assert result.returncode == 1
    assert "against origin/develop" in result.stdout


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
    write_private_hook(repo, None, script_exists=False)
    result = scan(repo, allow_missing=False)
    assert result.returncode == 1
    assert "does not exist" in result.stdout


def test_private_check_that_passes_is_reported(repo: Path) -> None:
    commit_file(repo, "a.txt", "clean\n")
    write_private_hook(repo, "print('PASS: stand in')\n")
    result = scan(repo, allow_missing=False)
    assert result.returncode == 0
    assert "private-name check: PASS" in result.stdout


def test_private_check_that_finds_something_fails_the_scan(repo: Path) -> None:
    commit_file(repo, "a.txt", "clean\n")
    write_private_hook(
        repo, "import sys\nprint('FAIL: a.txt:1: owner-term', file=sys.stderr)\nsys.exit(1)\n"
    )
    result = scan(repo, allow_missing=False)
    assert result.returncode == 1
    assert "private-name check: FAIL: a.txt:1: owner-term" in result.stdout


def test_private_check_that_cannot_check_counts_as_not_run(repo: Path) -> None:
    commit_file(repo, "a.txt", "clean\n")
    write_private_hook(repo, "import sys\nsys.exit(2)\n")
    assert scan(repo, allow_missing=False).returncode == 1
    assert scan(repo, allow_missing=True).returncode == 0


def test_private_check_is_found_from_a_linked_worktree(repo: Path) -> None:
    commit_file(repo, "a.txt", "clean\n")
    write_private_hook(repo, "print('PASS: stand in')\n")
    linked = repo.parent / "linked"
    git(repo, "worktree", "add", "-q", "-b", "side", str(linked))
    result = scan(linked, allow_missing=False)
    assert result.returncode == 0
    assert "private-name check: PASS" in result.stdout


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------


def test_mask_never_returns_the_value() -> None:
    value = "abcdefghij"
    assert value not in leaks.mask(value)
    assert leaks.mask("abc") == "***"
    assert leaks.mask(value).startswith("a***")


def test_placeholder_rules() -> None:
    assert leaks.is_placeholder("short")
    assert leaks.is_placeholder("<your-token>")
    assert leaks.is_placeholder("${SECRET_VALUE}")
    assert leaks.is_placeholder("your-api-key-here")
    assert not leaks.is_placeholder("a8Kd93jLq0Zx7MvB2nRt")


def test_scan_line_reports_nothing_on_an_allowed_line() -> None:
    assert leaks.scan_line(f"{planted('personal-email')} local-refs: allow") == []
