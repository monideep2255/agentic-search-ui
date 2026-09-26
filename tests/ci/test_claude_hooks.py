"""Run the two Bash guard hooks the way the harness does, and assert block or allow.

`.claude/settings.json` wires `block-bash-delete.sh` and `scan-secrets.sh` as
PreToolUse hooks on every Bash call. The harness runs each as `bash <hook>`,
writes the tool call to its stdin as JSON, and treats exit 2 as "blocked" and
exit 0 as "allowed". This file does exactly that, once per case below.

Why it exists. The product owner approved two narrowings on 2026-09-25
(DECISIONS.md, "Four security-layer changes approved item by item", items 1
and 2), after the build harness review found both hooks blocking harmless
commands. A narrowing is the kind of change that quietly lets a destructive
command through, so every destructive shape the delete guard names is pinned
here next to the harmless ones, in both directions.

WHAT THIS COVERS, stated so a gap is arguable rather than discovered:

    Covered      The delete guard: every rm and rmdir shape its patterns name
                 (command start, after a shell separator, inside each
                 execution wrapper), writes to disk devices, the /dev/null
                 exemption and proof that it cannot hide an rm, and the false
                 blocks the review measured ("perform", `2>/dev/null` inside a
                 wrapper).
    Covered      The secret scan: the token-prefix check on every command,
                 grep included; the field-assignment check skipped only when
                 the first word is grep, rg or git grep; the same field check
                 still firing on every other command.

    NOT covered  The hooks' no-Python fallback in `lib/_json.sh`. Every case
                 here runs with a working Python on PATH, as it does on the
                 owner's machine and in CI.
    NOT covered  Deletion that never names rm or rmdir: `find -delete`,
                 `unlink`, `shred`, `git clean`, Python's `os.remove`. Neither
                 the old hook nor the new one looks for these.
    NOT covered  A grep-led chain that sets a literal value after the grep,
                 for example `grep x f; export ...=<literal>`. The approved
                 exemption is by first word, so the field check does not see
                 it; the token-prefix check still does.
    NOT covered  Whether the permission rules in `.claude/settings.json` also
                 deny a command. This file tests the hooks alone.

Secret-shaped values are assembled from fragments at run time, so no literal
the scanners look for ever sits in this file.

Depends on:
    - .claude/hooks/block-bash-delete.sh
    - .claude/hooks/scan-secrets.sh
    - .claude/hooks/lib/_json.sh

Writes:
    - Nothing. The hooks only read stdin.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS = REPO_ROOT / ".claude" / "hooks"
DELETE_GUARD = "block-bash-delete.sh"
SECRET_SCAN = "scan-secrets.sh"

BLOCKED = 2
ALLOWED = 0

# A hook is a few greps and one Python call. Anything slower has hung.
_TIMEOUT_S = 30

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="the hooks run under bash")


def run_hook(hook: str, command: str) -> subprocess.CompletedProcess:
    """Feed one Bash tool call to a hook exactly as the harness does."""
    payload = json.dumps(
        {
            "session_id": "hook-regression",
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command, "description": "hook regression case"},
        }
    )
    return subprocess.run(
        ["bash", str(HOOKS / hook)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_S,
        check=False,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(REPO_ROOT)},
    )


def assert_verdict(hook: str, command: str, expected: int) -> None:
    result = run_hook(hook, command)
    verdict = {BLOCKED: "blocked", ALLOWED: "allowed"}
    assert result.returncode == expected, (
        f"{hook} {verdict.get(result.returncode, f'exited {result.returncode}')} "
        f"what should be {verdict[expected]}: {command!r}\nstderr: {result.stderr.strip()}"
    )


# ---------------------------------------------------------------------------
# The delete guard, block-bash-delete.sh
#
# Every command in this file is a string handed to a hook on stdin, which only
# greps it. None is ever executed, so `rm` and `os.system` below are test data.
# ---------------------------------------------------------------------------

DELETE_GUARD_BLOCKS = [
    # The destructive cases named in the builder brief.
    pytest.param("rm -rf build/", id="rm-rf"),
    pytest.param("rm -r x", id="rm-r"),
    pytest.param("rmdir d", id="rmdir"),
    pytest.param("sudo rm -rf /", id="sudo-rm"),
    pytest.param(r"find . -name x -exec rm {} \;", id="find-exec-rm"),
    pytest.param("xargs rm", id="xargs-rm"),
    pytest.param("python3 -c \"import os; os.system('rm -rf ~')\"", id="python-os-system-rm"),
    pytest.param("python3 -c \"import shutil; shutil.rmtree('x')\"", id="python-rmtree"),
    pytest.param('bash -c "rm -rf /tmp/x"', id="bash-c-rm"),
    pytest.param('ssh host "rm -rf /data"', id="ssh-rm"),
    pytest.param("dd if=/dev/zero of=/dev/disk2", id="dd-to-disk"),
    pytest.param("echo x > /dev/sda", id="redirect-to-disk"),
    # The old pattern 1: rm or rmdir at the start or after a shell separator.
    pytest.param("ls; rm -rf x", id="after-semicolon"),
    pytest.param("true && rm -rf x", id="after-and"),
    pytest.param("false || rm -rf x", id="after-or"),
    pytest.param("true | rm -rf x", id="after-pipe"),
    pytest.param("sleep 1 & rm -rf x", id="after-background"),
    pytest.param("rm --recursive --force x", id="rm-long-options"),
    pytest.param("echo start\nrm -rf x", id="rm-on-second-line"),
    # The old pattern 2: every execution wrapper, and every destructive word.
    pytest.param("python -c \"import os; os.system('rm -rf /')\"", id="python-c-rm"),
    pytest.param("perl -e 'system(\"rm -rf x\")'", id="perl-e-rm"),
    pytest.param("ruby -e 'system(\"rm -rf x\")'", id="ruby-e-rm"),
    pytest.param(
        "node -e \"require('child_process').execSync('rm -rf x')\"", id="node-e-rm"
    ),
    pytest.param('sh -c "rm -rf x"', id="sh-c-rm"),
    pytest.param('zsh -c "rm -rf x"', id="zsh-c-rm"),
    pytest.param('eval "rm -rf x"', id="eval-rm"),
    pytest.param('ssh host "rmdir /data/old"', id="ssh-rmdir"),
    pytest.param("node -e \"require('fs').rmdirSync('x')\"", id="node-rmdirsync"),
    pytest.param("python3 -c \"import os; os.rmdir('x')\"", id="python-os-rmdir"),
    pytest.param("perl -e 'use File::Path; rmtree(\"x\")'", id="perl-rmtree"),
    pytest.param('bash -c "dd if=/dev/zero of=/dev/sda"', id="bash-c-dd"),
    pytest.param('ssh host "dd if=/dev/zero of=/dev/sdb bs=1M"', id="ssh-dd"),
    pytest.param('ssh host "mkfs.ext4 /dev/sdb1"', id="ssh-mkfs"),
    pytest.param('bash -c "echo x > /dev/sda"', id="bash-c-redirect-to-disk"),
    pytest.param('ssh host "cat disk.img > /dev/disk2"', id="ssh-redirect-to-disk"),
    # A redirect to /dev/null must never hide the rm next to it.
    pytest.param('ssh host "rm -rf /data" 2>/dev/null', id="ssh-rm-then-devnull"),
    pytest.param("rm -rf x 2>/dev/null", id="rm-then-devnull"),
    pytest.param("kill -0 1 2>/dev/null && rm -rf x", id="devnull-then-rm"),
    pytest.param('bash -c "rm -rf /tmp/x 2>/dev/null"', id="bash-c-rm-devnull-inside"),
    pytest.param(">/dev/null rm -rf x", id="redirect-before-rm"),
    # bash reads &> as one redirect, but in POSIX sh the & ends a command and rm
    # runs, so the & before a /dev/null redirect is never dropped with it.
    pytest.param("true&>/dev/null rm -rf x", id="ampersand-before-devnull"),
    # rm in command position after a prefix word, a path or a quote.
    pytest.param("sudo -u root rm -rf /var/www", id="sudo-u-rm"),
    pytest.param("ls | xargs -0 rm -f", id="pipe-xargs-rm"),
    pytest.param("find . -type f -exec /bin/rm -f {} +", id="find-exec-bin-rm"),
    pytest.param("/bin/rm -rf x", id="absolute-path-rm"),
    pytest.param(r"\rm -rf x", id="backslash-rm"),
    pytest.param('for f in a b; do rm "$f"; done', id="loop-rm"),
    pytest.param("if [ -d x ]; then rm -rf x; fi", id="then-rm"),
    pytest.param("echo $(rm -rf x)", id="command-substitution-rm"),
    pytest.param("{ rm -rf x; }", id="group-rm"),
    pytest.param("echo `rm -rf x`", id="backtick-rm"),
    pytest.param("nohup rm -rf x &", id="nohup-rm"),
    pytest.param("env FOO=1 rm -rf x", id="env-rm"),
    pytest.param("exec rm -rf x", id="exec-rm"),
    pytest.param("timeout 5 rm -rf x", id="timeout-rm"),
    pytest.param("xargs -I {} rm {}", id="xargs-I-rm"),
    pytest.param('"rm" -rf x', id="quoted-rm"),
    pytest.param(
        "python3 -c \"import subprocess; subprocess.run(['rm', '-rf', 'x'])\"",
        id="python-subprocess-list-rm",
    ),
    # Writes to a disk device, wrapper or not.
    pytest.param("dd if=/dev/zero of=/dev/rdisk2 bs=1m", id="dd-to-raw-disk"),
    pytest.param("cat image.iso > /dev/disk2", id="cat-to-disk"),
    pytest.param("echo x >> /dev/sda", id="append-to-disk"),
    pytest.param("echo x 1> /dev/sda", id="fd-redirect-to-disk"),
    pytest.param('echo x > "/dev/sda"', id="quoted-disk-path"),
    pytest.param("mkfs.ext4 /dev/sdb1", id="mkfs"),
    pytest.param("sudo mkfs -t ext4 /dev/sdb1", id="sudo-mkfs"),
    # The /dev/null exemption is exact: a longer device name is not /dev/null.
    pytest.param("echo x > /dev/nullb0", id="devnull-prefix-is-not-devnull"),
    # Inside a wrapper the approval exempts /dev/null only. Any other write into
    # /dev stays blocked there, as before, even to a stream such as stderr.
    pytest.param('bash -c "echo hi > /dev/stderr"', id="wrapper-stderr-as-before"),
]

DELETE_GUARD_ALLOWS = [
    # The false blocks the build harness review measured.
    pytest.param('bash -c "kill -0 12345 2>/dev/null && echo alive"', id="bash-c-devnull"),
    pytest.param(
        "python3 -c \"import json; d=json.load(open('runs.json')); print(d)\" 2>/dev/null",
        id="python-c-then-devnull",
    ),
    pytest.param("python3 -c \"print('perform the check')\"", id="perform"),
    pytest.param('ssh host "systemctl status caddy 2>/dev/null"', id="ssh-devnull"),
    # Named in the builder brief.
    pytest.param("git rm --cached file.txt", id="git-rm-cached"),
    pytest.param("ls -la", id="ls"),
    pytest.param("echo perform", id="echo-perform"),
    pytest.param('python3 -c "print(1)" 2>/dev/null', id="python-print-devnull"),
    pytest.param("cmd > /dev/null", id="redirect-devnull"),
    # The rest of the review's probe script.
    pytest.param("kill -0 12345 2>/dev/null && echo alive || echo gone", id="kill-devnull"),
    pytest.param("kill -0 12345 && echo alive", id="kill"),
    pytest.param(
        r'python3 -c "import json; d=json.load(open(\"runs.json\")); print(len(d))"',
        id="python-escaped-quotes",
    ),
    pytest.param("python3 -c \"import platform; print(platform.platform())\"", id="platform"),
    pytest.param('ssh host "uptime"', id="ssh-uptime"),
    # Every redirect form that only discards output.
    pytest.param("cmd >/dev/null 2>&1", id="devnull-and-stderr"),
    pytest.param("cmd &>/dev/null", id="both-to-devnull"),
    pytest.param("cmd >> /dev/null", id="append-devnull"),
    pytest.param("cmd 2> /dev/null", id="stderr-devnull-spaced"),
    pytest.param('cmd > "/dev/null"', id="quoted-devnull"),
    pytest.param('bash -c "make build > /dev/null"', id="bash-c-build-devnull"),
    pytest.param('ssh host "tail -n 50 /var/log/app.log 2>/dev/null"', id="ssh-tail-devnull"),
    pytest.param("python3 -m pytest tests/ci -q 2>/dev/null", id="pytest-devnull"),
    pytest.param("dd if=big.img of=/dev/null bs=1m", id="dd-to-devnull"),
    # Words that contain rm, and rm that is not a command.
    pytest.param(
        "python3 -c \"print('transform the uniform format')\"", id="words-containing-rm"
    ),
    pytest.param('grep -rn "rm -rf" docs/', id="grep-for-rm"),
    pytest.param('git commit -m "docs: explain the rm guard"', id="commit-mentions-rm"),
    pytest.param(
        'git commit -m "Block sudo rm and xargs rm in the delete guard"',
        id="commit-mentions-prefixed-rm",
    ),
    pytest.param("docker run --rm alpine echo hi", id="docker-rm-flag"),
    # Reading a device, or writing to a stream, is not a disk write. Outside a
    # wrapper the stream devices were never checked, and they still are not.
    pytest.param("echo hi >&2", id="stderr-fd"),
    pytest.param("echo hi > /dev/stderr", id="stderr-device"),
    pytest.param("printf x >/dev/fd/2", id="fd-device"),
    pytest.param("head -c 16 < /dev/urandom", id="read-from-device"),
    pytest.param("ls /dev/ | head", id="list-dev"),
]


@pytest.mark.parametrize("command", DELETE_GUARD_BLOCKS)
def test_delete_guard_blocks_destructive_command(command: str) -> None:
    assert_verdict(DELETE_GUARD, command, BLOCKED)


@pytest.mark.parametrize("command", DELETE_GUARD_ALLOWS)
def test_delete_guard_allows_harmless_command(command: str) -> None:
    assert_verdict(DELETE_GUARD, command, ALLOWED)


# ---------------------------------------------------------------------------
# The secret scan, scan-secrets.sh
# ---------------------------------------------------------------------------

# Shaped like real credentials, one per prefix the scan knows, assembled so the
# literal never sits in this file.
_SK_TOKEN = "sk" + "-" + "a1B2c3D4e5F6g7H8i9J0k1L2"
_GHP_TOKEN = "gh" + "p_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
_AKIA_KEY = "AK" + "IA" + "ABCDEFGHIJKLMNOP"
_XOXB_TOKEN = "xo" + "xb-" + "123456789012-abcdefghij"
_KEY_HEADER = "PRIVATE" + " KEY"

SECRET_SCAN_BLOCKS = [
    # A literal value set on a command that is not a search: blocked, as today.
    pytest.param("export NCBI_API_KEY=abcdefgh12345", id="export-literal-key"),
    pytest.param(
        'curl -s -X POST https://example.invalid/login -d "email=a@b.c&password=Passw0rd123"',
        id="curl-literal-password",
    ),
    # A real secret's shape is blocked on every command, a search included.
    pytest.param(f"echo {_SK_TOKEN}", id="token-in-echo"),
    pytest.param(f'grep -rn "{_GHP_TOKEN}" src/', id="token-inside-grep"),
    pytest.param(f'rg "{_AKIA_KEY}" .', id="token-inside-rg"),
    pytest.param(f'git grep "{_XOXB_TOKEN}"', id="token-inside-git-grep"),
    pytest.param(f'grep -rn "{_KEY_HEADER}" .', id="key-header-inside-grep"),
]

# The exemption is by first word only. Each of these carries a field-shaped
# string and is not led by grep, rg or git grep, so the field check still runs.
SECRET_SCAN_FIELD_CHECK_KEPT = [
    pytest.param('cat config.py | grep "api_key=settings"', id="grep-after-a-pipe"),
    pytest.param('cd src && grep -rn "api_key=settings" .', id="grep-after-cd"),
    pytest.param('egrep "api_key=settings" src/', id="egrep-is-not-grep"),
    pytest.param("echo api_key=settings123", id="echo-field-literal"),
]

SECRET_SCAN_ALLOWS = [
    # Searches that name a field in order to find it.
    pytest.param('grep -rn "api_key=settings" src/', id="grep-field-name"),
    pytest.param('rg "token=" docs', id="rg-field-name"),
    pytest.param('git grep "password="', id="git-grep-field-name"),
    pytest.param(
        'grep -rn "AUTH_SECRET=ci-not-a-real-secret" .github/', id="grep-ci-placeholder"
    ),
    pytest.param('rg -n "PG_PASSWORD=postgres123" tests/', id="rg-field-with-value"),
    pytest.param('git grep -n "NCBI_API_KEY=os.environ"', id="git-grep-env-lookup"),
    pytest.param('  grep -rn "api_key=settings" src/', id="grep-after-leading-space"),
    pytest.param('grep -rn "api_key=settings" src/ | head -20', id="grep-piped-to-head"),
    # Harmless on any command, before and after the change.
    pytest.param('grep -n "PASSWORD" env.example', id="grep-bare-field"),
    pytest.param("export OPENROUTER_API_KEY=$OPENROUTER_API_KEY", id="export-reference"),
    pytest.param('echo "the AUTH_SECRET variable must be set"', id="prose-mentions-field"),
    pytest.param("python3 scripts/sign_in.py --accounts accounts.json", id="sign-in-script"),
]


@pytest.mark.parametrize("command", SECRET_SCAN_BLOCKS)
def test_secret_scan_blocks_secret(command: str) -> None:
    assert_verdict(SECRET_SCAN, command, BLOCKED)


@pytest.mark.parametrize("command", SECRET_SCAN_FIELD_CHECK_KEPT)
def test_secret_scan_keeps_field_check_unless_led_by_a_search(command: str) -> None:
    assert_verdict(SECRET_SCAN, command, BLOCKED)


@pytest.mark.parametrize("command", SECRET_SCAN_ALLOWS)
def test_secret_scan_allows_search_and_reference(command: str) -> None:
    assert_verdict(SECRET_SCAN, command, ALLOWED)
