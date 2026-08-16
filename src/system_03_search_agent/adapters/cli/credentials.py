"""The `s3` CLI's credential store: build phase 4.2, `tracker/phase_4.2.md`.

Reads and writes the on-disk file the CLI's three bearer-JWT credentials
(base URL, access token, refresh token) live in between invocations. Two
properties carry the whole risk this module exists to bound, both measured
hazards named in the phase premise, not stylistic preferences:

Refuse, do not warn. `load()` raises `InsecureCredentialsError` on a file
whose POSIX mode is wider than 0600 rather than reading it and warning. A
credential file another local account can read is already compromised;
continuing normalizes the state the mode exists to prevent.

The lock is a data-loss bound. The server's refresh tokens are single-use
and rotating (`auth/router.py`), and replaying an already-rotated one
revokes the caller's ENTIRE session family, every surface, logged out. Two
concurrent `s3` invocations that both notice an expired access token and
both refresh is therefore a full logout as a routine consequence of running
two commands at once. `refresh_locked` holds an exclusive `fcntl.flock`
across the whole read-refresh-write critical section and RE-READS the file
after acquiring the lock, because the other process may have already
rotated while this one waited; if the re-read shows a different refresh
token than the caller passed in, the rotation already happened, so the
on-disk value is used and the caller's stale token is never spent against
the server a second time.

Depends on:
    - httpx.AsyncClient, injected by the caller (never constructed here),
      the same seam `tracker/phase_4.2.md`'s fixed interfaces name for
      `client.py` (T-4.2-03): this module never opens its own socket, so
      the premise gate can drive it entirely over `ASGITransport`.
    - The wire shape of `POST /auth/refresh`
      (`system_03_search_agent.auth.router.refresh`,
      `system_03_search_agent.auth.schemas.RefreshRequest`,
      `system_03_search_agent.auth.schemas.TokenResponse`): a JSON body of
      `{"refresh_token": str}` in, `{"access_token": str, "refresh_token":
      str, "token_type": "bearer"}` out on success, read from the router
      source directly rather than assumed.

A third property, added responding to the round-1 adversary and judge
reports (`tracker/phase_4.2_adversary_report.md`,
`tracker/phase_4.2_judge_report.md`), bounds what "the lock is a data-loss
bound" leaves open: the lock serializes concurrent refreshes, but nothing
originally bounded a single refresh whose OWN write-back failed after the
server had already rotated (F-4.2-A-03), or a foreign lock holder that
never released (F-4.2-A-11). `_refresh_and_store` now treats a failed
`store()` after a successful rotation as reportable and recoverable rather
than silent: it attempts a best-effort recovery write before raising
`SessionLostError`, and `load()` promotes that recovery copy on the very
next invocation. `_CredentialFileLock` now polls a non-blocking flock
bounded by REFRESH_LOCK_WAIT_TIMEOUT_SECONDS instead of waiting on the
blocking form forever, per `.claude/rules/tool-call-budgets.md`.

Depends on:
    - httpx.AsyncClient, injected by the caller (never constructed here),
      the same seam `tracker/phase_4.2.md`'s fixed interfaces name for
      `client.py` (T-4.2-03): this module never opens its own socket, so
      the premise gate can drive it entirely over `ASGITransport`.
    - The wire shape of `POST /auth/refresh`
      (`system_03_search_agent.auth.router.refresh`,
      `system_03_search_agent.auth.schemas.RefreshRequest`,
      `system_03_search_agent.auth.schemas.TokenResponse`): a JSON body of
      `{"refresh_token": str}` in, `{"access_token": str, "refresh_token":
      str, "token_type": "bearer"}` out on success, read from the router
      source directly rather than assumed.

Reads:
    - Environment variable: S3_CREDENTIALS_PATH (overrides the default
      `~/.system3/credentials` location; read once at import time into the
      CREDENTIALS_PATH module attribute, which callers and tests then
      treat as the single source of truth, per this module's own
      docstring convention of resolving the path through that attribute
      rather than re-reading the environment on every call). Expanded via
      `Path.expanduser()`, so a `~`-prefixed override resolves against the
      caller's home directory rather than creating a literal `./~/`.
    - CREDENTIALS_PATH: the stored `base_url`, `access_token` and
      `refresh_token`.
    - The recovery file beside CREDENTIALS_PATH (`<name>.recovery`), if
      present, at the top of every `load()` call.

Writes:
    - CREDENTIALS_PATH: created at mode 600 from the first byte, replaced
      atomically on every `store()` call, never widened then narrowed.
    - CREDENTIALS_PATH's parent directory: created at mode 700 if absent;
      refused rather than trusted or silently narrowed if it already
      exists and is group- or other-writable.
    - A dedicated lock file beside CREDENTIALS_PATH (`.<name>.lock`), held
      only for the duration of `refresh_locked`'s critical section.
    - The recovery file beside CREDENTIALS_PATH (`<name>.recovery`),
      best-effort, only when a normal `store()` call inside a refresh has
      already failed; removed once its contents are promoted.

Never writes an access token, a refresh token, or a password to a log
message or an exception string anywhere in this module, per
`.claude/rules/production-standards.md`'s secrets gate. Every error below
names a status code, a mode, or a path; never a credential value.
"""

from __future__ import annotations

import asyncio
import errno
import json
import os
import stat
import uuid
import warnings
from pathlib import Path
from typing import NamedTuple, Self

import httpx

try:
    import fcntl

    _HAS_FLOCK = True
except ImportError:  # pragma: no cover - exercised only on a non-POSIX platform
    fcntl = None  # type: ignore[assignment]
    _HAS_FLOCK = False


def _default_credentials_path() -> Path:
    override = os.environ.get("S3_CREDENTIALS_PATH")
    if override:
        # expanduser(): S3_CREDENTIALS_PATH="~/foo" must resolve to the
        # caller's home directory, not create a literal "./~/" directory.
        # A no-op on an already-absolute path, so the existing env-override
        # test (which sets an absolute path) is unaffected (F-4.2-A-23).
        return Path(override).expanduser()
    return Path.home() / ".system3" / "credentials"


CREDENTIALS_PATH: Path = _default_credentials_path()

# Owner read/write only. Any bit outside this mask (group or other access,
# or even owner-execute) is what "wider than 600" refuses.
_SECURE_MODE = 0o600
_FORBIDDEN_MODE_BITS = 0o777 & ~_SECURE_MODE
_SECURE_DIR_MODE = 0o700

# Group- or other-WRITE on the parent directory is refused (F-4.2-A-18 /
# J-4.2-10): a writable-by-others parent lets another local account
# replace the credential file outright, or plant a symlink where the
# credential or lock file is expected, defeating the mode-600 file check
# entirely since it never gets a chance to run against the real file.
# Read/execute bits are not checked here; they only reveal filenames, not
# write access, so they are outside this threat model.
_DIR_FORBIDDEN_BITS = stat.S_IWGRP | stat.S_IWOTH

# This is an internal call to this system's own auth router, not one of the
# seven NCBI/graph tools `.claude/rules/tool-call-budgets.md` tabulates,
# but the same rule's "every outbound HTTP call carries an explicit
# timeout" line is not scoped to that table alone. 15 seconds matches the
# per-call budget this repo already uses for every other interactive HTTPS
# call.
REFRESH_TIMEOUT_SECONDS = 15.0

# F-4.2-A-11: the refresh lock must fail fast, per
# `.claude/rules/tool-call-budgets.md`'s bounded-wait requirement, rather
# than block forever on a foreign holder. The ceiling is deliberately tied
# to REFRESH_TIMEOUT_SECONDS, the one genuinely slow step in the critical
# section the lock guards (load() and store() are local disk I/O, low
# single-digit milliseconds on any sane filesystem). It must be set ABOVE
# REFRESH_TIMEOUT_SECONDS, not below it: a ceiling shorter than the
# operation it guards would spuriously fail the two-concurrent-refreshes
# case the phase premise requires to serialize successfully, since a
# legitimate holder can occupy the lock for nearly the full refresh
# timeout. The margin above 15s is a small, fixed allowance for that local
# I/O plus poll granularity, not a second independent budget chosen
# without reference to what it bounds.
REFRESH_TIMEOUT_SECONDS_MARGIN = 5.0
REFRESH_LOCK_WAIT_TIMEOUT_SECONDS = REFRESH_TIMEOUT_SECONDS + REFRESH_TIMEOUT_SECONDS_MARGIN
_LOCK_POLL_INTERVAL_SECONDS = 0.05

_warned_no_flock = False


class Credentials(NamedTuple):
    base_url: str
    access_token: str | None
    refresh_token: str


class CredentialsError(Exception):
    """Common base for every exception this module raises.

    This is the fix for a defect that hit this phase three times already,
    always the same shape: a raiser and a catcher, each correct alone, and
    the seam between them left unwired because the contract lived in two
    files nobody diffed together. F-4.2-08: `render.py` dispatched on
    `httpx` types while `client.py` raised its own. J-4.2-02: `main.py`
    caught `httpx.HTTPStatusError` while this module raises `RefreshError`.
    F-4.2-A-05: `CliApiError`'s own base was left out of the caught tuple,
    so a 500 escaped uncaught. A catcher that lists six named types is the
    same defect waiting to happen a fifth time, the moment a seventh type
    is added and the list is not.

    A single base makes the seam impossible instead of merely documented:
    `except CredentialsError` catches every exception this module raises
    today and every one it raises after this file is next touched, with no
    per-type list to fall out of sync. `remedy`, the actionable next step,
    is a required keyword argument on every instance, set by whichever
    subclass and call site actually raises, and readable through this base
    without knowing which of the six fired. `str(exc)` is always the
    explanation followed by the remedy, assembled once here rather than
    hand-formatted at each of this module's raise sites, which is one more
    place the two could drift apart. A caller that wants only the remedy,
    for example to render a separate "Next step:" line, reads `exc.remedy`
    directly instead of parsing it back out of the message.

    `test_every_exception_class_in_this_module_derives_from_credentials_error`
    (`test_credentials.py`) enumerates every exception class this module
    defines and asserts each one derives from `CredentialsError`. That
    test fails the moment a seventh exception type is added without
    deriving from this base, which is the only thing that actually stops
    a fifth instance of this defect; a comment saying so would not.
    """

    def __init__(self, explanation: str, *, remedy: str) -> None:
        self.explanation = explanation
        self.remedy = remedy
        super().__init__(f"{explanation} {remedy}")


class InsecureCredentialsError(CredentialsError):
    """The credential file's POSIX mode is wider than 0600, or its parent
    directory is writable by group or other.

    Raised instead of reading the file and warning: a file or directory
    another local account can write to is already compromised, and
    continuing would normalize the state the mode exists to prevent. The
    `remedy` names the exact remediation, per
    `.claude/rules/tool-call-budgets.md`'s actionable-error rule.
    """


class RefreshError(CredentialsError):
    """`POST /auth/refresh` did not return 200.

    The stored refresh token is most likely expired, already rotated by a
    prior use, or revoked. Never includes the token value.
    """


class SessionLostError(RefreshError):
    """The server rotated the refresh token, but this side could not
    durably record the new one (F-4.2-A-03).

    A subclass of RefreshError, deliberately: the correct next step is
    identical either way, re-authenticate, because the caller's old
    on-disk token is dead server-side the instant the rotation response
    arrives, regardless of whether the write meant to replace it also
    succeeded. Anything that already special-cases RefreshError therefore
    does the right thing here too. Names the write failure and any
    recovery copy left behind, never the raw OSError or KeyboardInterrupt
    that triggered it, and never a token value.
    """


class CorruptCredentialsError(CredentialsError):
    """CREDENTIALS_PATH exists but its contents are not usable (F-4.2-A-13).

    Covers every shape observed: an empty file, truncated JSON, valid JSON
    that is not an object, a missing required field, a field of the wrong
    type, or a path that is not a regular file at all (F-4.2-A-22). Raised
    instead of letting a bare `JSONDecodeError`, `TypeError` or `KeyError`
    reach the caller, per this module's actionable-error discipline. Never
    includes the file's contents in the message.
    """


class RefreshLockTimeoutError(CredentialsError):
    """Another process held the credential refresh lock past
    REFRESH_LOCK_WAIT_TIMEOUT_SECONDS (F-4.2-A-11).

    Fails fast rather than waiting forever, per
    `.claude/rules/tool-call-budgets.md`'s bounded-wait-and-fail-fast
    requirement. Names what is contended and what to do about it: wait for
    the other command, or remove a genuinely stale lock file.
    """


class RefreshLockUnavailableError(CredentialsError):
    """The credential refresh lock file itself could not be opened.

    Covers a lock file at a permission-denied mode (F-4.2-A-13's mode-000
    case) and a lock path that is a symlink (F-4.2-A-17). Distinct from
    RefreshLockTimeoutError, which means the lock file opened fine but a
    holder would not release it in time.
    """


def _ensure_parent_dir_secure(parent: Path) -> None:
    """Refuse a parent directory that is writable by group or other
    (F-4.2-A-18 / J-4.2-10).

    Checked on every load(), store() and lock acquisition, not only at
    directory-creation time (store() previously set mode 700 only when it
    created the directory itself, leaving a pre-existing wide directory
    neither narrowed nor refused). Refuses rather than silently
    narrowing: narrowing after the fact does not undo access already
    granted during the window the directory was wide, and silently fixing
    it would hide that the directory was ever compromised, the same
    refuse-do-not-warn reasoning already applied to the file itself.

    This check is a stat-then-later-open race like the file's own check
    used to be (a directory could theoretically be widened between this
    check and the file open that follows it). Closing it fully would need
    directory-fd-relative opens throughout this module, a materially
    larger change than the finding asked for; recorded here rather than
    silently left unstated, per this repo's coverage-declaration
    discipline.
    """
    if os.name != "posix":
        return
    try:
        mode = stat.S_IMODE(os.stat(parent).st_mode)
    except FileNotFoundError:
        return
    if mode & _DIR_FORBIDDEN_BITS:
        raise InsecureCredentialsError(
            f"{parent} is writable by group or other (mode {oct(mode)}). "
            f"Another local account could replace the credential file "
            f"through this directory, so it is being refused.",
            remedy=f"Run: chmod 700 {parent}",
        )


def _describe_non_regular(mode: int) -> str:
    if stat.S_ISDIR(mode):
        return "a directory"
    if stat.S_ISFIFO(mode):
        return "a FIFO"
    if stat.S_ISSOCK(mode):
        return "a socket"
    if stat.S_ISBLK(mode) or stat.S_ISCHR(mode):
        return "a device file"
    return "not a regular file"


def _credentials_from_raw(raw: object, path: Path) -> Credentials:
    """Validate and construct `Credentials` from parsed JSON (F-4.2-A-30).

    Never trusts the shape: a missing key, a non-string field, or a
    top-level value that is not even an object (e.g. a JSON array) each
    get one clear CorruptCredentialsError rather than the KeyError,
    TypeError, or AttributeError that indexing an unvalidated value would
    raise.
    """
    if not isinstance(raw, dict):
        raise CorruptCredentialsError(
            f"{path} does not contain a credentials object.", remedy="Run: s3 login"
        )
    missing = [key for key in ("base_url", "refresh_token") if key not in raw]
    if missing:
        raise CorruptCredentialsError(
            f"{path} is missing required field(s): {', '.join(missing)}.",
            remedy="Run: s3 login",
        )
    base_url = raw["base_url"]
    access_token = raw.get("access_token")
    refresh_token = raw["refresh_token"]
    if not isinstance(base_url, str):
        raise CorruptCredentialsError(f"{path}'s base_url is not a string.", remedy="Run: s3 login")
    if access_token is not None and not isinstance(access_token, str):
        raise CorruptCredentialsError(
            f"{path}'s access_token is not a string.", remedy="Run: s3 login"
        )
    if not isinstance(refresh_token, str):
        raise CorruptCredentialsError(
            f"{path}'s refresh_token is not a string.", remedy="Run: s3 login"
        )
    return Credentials(base_url=base_url, access_token=access_token, refresh_token=refresh_token)


def _recovery_path() -> Path:
    return CREDENTIALS_PATH.parent / f"{CREDENTIALS_PATH.name}.recovery"


def _promote_recovery_copy_if_present() -> None:
    """Self-heal from a prior write-back failure (F-4.2-A-03).

    If `_write_recovery_copy` left a recovery file behind after a failed
    `store()`, promote it into CREDENTIALS_PATH now, before this load()
    reads anything, so the run that follows a disk-full or Ctrl-C write
    failure picks up the rotated token instead of replaying the dead one
    CREDENTIALS_PATH still held. The promotion write goes through
    `store()`, so it is atomic and mode 600 like every other write this
    module makes.

    Best-effort and silent on its own failure at every step, including the
    promotion write itself: a recovery file that is unreadable or
    malformed (the same disk pressure that broke the primary write could
    have truncated this one too) is removed and ignored, and a promotion
    write that fails again (e.g. the disk is still full) leaves the
    recovery file in place for a later attempt rather than raising a raw
    write error out of what is meant to be a read path. Either way, load()
    always falls through to reading CREDENTIALS_PATH as it stands.
    """
    recovery = _recovery_path()
    try:
        if not recovery.exists():
            return
        with recovery.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        recovered_creds = _credentials_from_raw(raw, recovery)
    except (OSError, json.JSONDecodeError, CorruptCredentialsError):
        try:
            recovery.unlink()
        except OSError:
            pass
        return

    try:
        store(recovered_creds)
    except OSError:
        return

    try:
        recovery.unlink()
    except OSError:
        pass


def load() -> Credentials:
    """Read `Credentials` from CREDENTIALS_PATH.

    Raises `InsecureCredentialsError` if the file's POSIX mode is wider
    than 0600, or if its parent directory is writable by group or other
    (skipped on a non-POSIX platform, where mode bits are not meaningful;
    see this module's docstring). Raises `FileNotFoundError` if no
    credential file exists yet. Raises `CorruptCredentialsError` if the
    file exists but is not a regular file, is not valid JSON, or does not
    have the shape a credentials file needs (F-4.2-A-13, F-4.2-A-22,
    F-4.2-A-30).

    The mode check and the read happen against the SAME open file
    descriptor (`os.open` then `os.fstat`), not a separate `os.stat` on
    the path followed by a separate `open()`: the previous stat-then-open
    form was a TOCTOU window where the path could be swapped between the
    two calls. `O_NOFOLLOW` additionally refuses a credentials path that
    is itself a symlink, so the descriptor this function inspects and the
    one it reads from are always the same underlying file.
    """
    path = CREDENTIALS_PATH
    _ensure_parent_dir_secure(path.parent)
    _promote_recovery_copy_if_present()

    open_flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        open_flags |= os.O_NOFOLLOW
    try:
        fd = os.open(str(path), open_flags)
    except FileNotFoundError:
        raise FileNotFoundError(f"No credentials at {path}. Run: s3 login") from None
    except OSError as exc:
        if getattr(exc, "errno", None) == errno.ELOOP:
            raise CorruptCredentialsError(
                f"{path} is a symlink; refusing to read a credential file "
                f"through a symlink, since its target could differ from "
                f"what any check on the path itself inspected.",
                remedy="Remove the symlink. Run: s3 login",
            ) from exc
        raise

    try:
        if os.name == "posix":
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                raise CorruptCredentialsError(
                    f"{path} is {_describe_non_regular(st.st_mode)}, not a "
                    f"regular file; the credential store expects a plain "
                    f"file there.",
                    remedy="Move it aside. Run: s3 login",
                )
            mode = stat.S_IMODE(st.st_mode)
            if mode & _FORBIDDEN_MODE_BITS:
                raise InsecureCredentialsError(
                    f"{path} has mode {oct(mode)}, wider than 0600. Another local "
                    f"account may be able to read it, so it is being refused rather "
                    f"than read.",
                    remedy=f"Run: chmod 600 {path}",
                )
    except BaseException:
        os.close(fd)
        raise

    # os.fdopen takes ownership of fd from here; the `with` block closes it
    # on every exit path below, success or exception.
    with os.fdopen(fd, "r", encoding="utf-8") as fh:
        try:
            raw = json.load(fh)
        except json.JSONDecodeError as exc:
            raise CorruptCredentialsError(
                f"{path} is not readable as valid credentials (unreadable "
                f"or corrupt JSON).",
                remedy="Run: s3 login",
            ) from exc

    return _credentials_from_raw(raw, path)


def store(creds: Credentials) -> None:
    """Persist `creds` to CREDENTIALS_PATH.

    Mode 600 from creation, never a widen-then-narrow: the temp file is
    opened with `os.open(..., O_CREAT | O_EXCL | O_WRONLY, 0o600)` so the
    permission bits are correct at the syscall that creates the file, not
    applied afterward by a separate `chmod`. The replace onto the final
    path is atomic (`os.replace`), so a reader never observes a
    partially-written file. The parent directory is created at mode 700 if
    absent, with the same discipline. A pre-existing parent directory that
    is group- or other-writable is refused rather than silently trusted or
    silently narrowed (F-4.2-A-18 / J-4.2-10): see `_ensure_parent_dir_secure`.
    """
    path = CREDENTIALS_PATH
    parent = path.parent
    if not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            os.chmod(parent, _SECURE_DIR_MODE)
    _ensure_parent_dir_secure(parent)

    payload = (
        json.dumps(
            {
                "base_url": creds.base_url,
                "access_token": creds.access_token,
                "refresh_token": creds.refresh_token,
            }
        )
        + "\n"
    ).encode("utf-8")

    tmp_path = parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    create_mode = _SECURE_MODE if os.name == "posix" else 0o666
    fd = os.open(str(tmp_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, create_mode)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(str(tmp_path), str(path))
    except BaseException:
        try:
            os.remove(str(tmp_path))
        except OSError:
            pass
        raise


def _write_recovery_copy(creds: Credentials) -> bool:
    """Best-effort emergency write of `creds` to `_recovery_path()`, used
    only after `store()`'s own atomic write already failed (F-4.2-A-03).

    Returns whether it succeeded. Never raises: compounding the original
    write failure with a second, unhandled one would be strictly worse
    than reporting "the recovery write also failed" honestly, which is
    what the caller does when this returns False. Mode 600 at creation,
    the same discipline `store()` uses, since this file holds live bearer
    tokens too. Not atomic like `store()`'s temp-file-then-replace (there
    is no guarantee a second temp file would succeed when the first write
    just failed, plausibly for lack of disk space), so a reader must treat
    a partially written recovery file as possible; `_promote_recovery_copy_if_present`
    already does, by discarding anything that fails JSON or shape
    validation.
    """
    path = _recovery_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = (
            json.dumps(
                {
                    "base_url": creds.base_url,
                    "access_token": creds.access_token,
                    "refresh_token": creds.refresh_token,
                }
            )
            + "\n"
        ).encode("utf-8")
        create_mode = _SECURE_MODE if os.name == "posix" else 0o666
        fd = os.open(str(path), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, create_mode)
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        if os.name == "posix":
            os.chmod(path, _SECURE_MODE)
    except OSError:
        return False
    return True


def _lock_path() -> Path:
    return CREDENTIALS_PATH.parent / f".{CREDENTIALS_PATH.name}.lock"


class _CredentialFileLock:
    """An exclusive lock on a dedicated file beside CREDENTIALS_PATH.

    A SEPARATE lock file, never CREDENTIALS_PATH itself, so the lock's
    open file description is never affected by `store()`'s atomic
    temp-file-then-`os.replace()` sequence on the credential file proper.

    Acquisition polls `LOCK_EX | LOCK_NB` directly on the event-loop
    thread, bounded by REFRESH_LOCK_WAIT_TIMEOUT_SECONDS (F-4.2-A-11).
    This replaces a prior design that called the plain blocking `LOCK_EX`
    in a worker thread via `run_in_executor`: that call had no timeout
    parameter at all (`fcntl.flock` does not offer one), so a foreign
    holder hung `s3` forever with no message. Non-blocking polling has a
    second benefit beyond the bound itself: each poll attempt returns
    immediately (acquired, or `BlockingIOError`), so it never blocks the
    event-loop thread the way the old blocking call would have, which
    removes the deadlock hazard that call's own docstring used to justify
    the executor-thread indirection: a synchronous blocking wait on the
    event loop would have starved a contending holder of the very loop it
    needed to finish its `await` and release the lock. Polling sidesteps
    that class of problem rather than merely working around it.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._fd: int | None = None

    async def __aenter__(self) -> Self:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        _ensure_parent_dir_secure(self._path.parent)
        open_flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            open_flags |= os.O_NOFOLLOW
        try:
            self._fd = os.open(str(self._path), open_flags, 0o600)
        except PermissionError as exc:
            raise RefreshLockUnavailableError(
                f"Cannot open the credential refresh lock at {self._path} "
                f"(permission denied).",
                remedy="Check its ownership and mode. Run: s3 login if the problem persists.",
            ) from exc
        except OSError as exc:
            if getattr(exc, "errno", None) == errno.ELOOP:
                raise RefreshLockUnavailableError(
                    f"{self._path} is a symlink; refusing to open the "
                    f"credential refresh lock through it, since it could "
                    f"point at an arbitrary file this process would then "
                    f"create and lock.",
                    remedy="Remove the symlink and retry.",
                ) from exc
            raise
        if _HAS_FLOCK:
            await self._acquire_bounded()
        return self

    async def _acquire_bounded(self) -> None:
        """Poll for the exclusive lock, failing fast at the bound named in
        this class's docstring rather than waiting forever."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + REFRESH_LOCK_WAIT_TIMEOUT_SECONDS
        while True:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except BlockingIOError:
                pass
            remaining = deadline - loop.time()
            if remaining <= 0:
                os.close(self._fd)
                self._fd = None
                raise RefreshLockTimeoutError(
                    f"Another s3 process is holding the credential refresh "
                    f"lock at {self._path} and did not release it within "
                    f"{REFRESH_LOCK_WAIT_TIMEOUT_SECONDS:.0f}s.",
                    remedy=(
                        f"Wait for the other s3 command to finish, or if none "
                        f"is actually running, remove the stale lock file and "
                        f"retry: rm {self._path}"
                    ),
                )
            await asyncio.sleep(min(_LOCK_POLL_INTERVAL_SECONDS, remaining))

    async def __aexit__(self, *exc_info: object) -> None:
        if self._fd is not None:
            if _HAS_FLOCK:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None


async def _refresh_and_store(client: httpx.AsyncClient, creds: Credentials) -> Credentials:
    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": creds.refresh_token},
        timeout=REFRESH_TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        raise RefreshError(
            f"POST /auth/refresh returned {response.status_code}; the stored "
            f"refresh token is expired, already used, or revoked.",
            remedy="Run: s3 login",
        )
    body = response.json()
    new_creds = Credentials(
        base_url=creds.base_url,
        access_token=body["access_token"],
        refresh_token=body["refresh_token"],
    )
    # Persist BEFORE the caller can issue its retried request: this is an
    # ordering property, not merely an eventual one. If the process dies
    # between the server rotating the token and this write landing, the
    # stored token is already dead and the user is locked out, so the
    # write happens here, synchronously within this same call, before
    # `refresh_locked` returns control to whatever retries the request.
    #
    # F-4.2-A-03: by the time execution reaches this point the SERVER has
    # already rotated. creds.refresh_token is dead there regardless of
    # what happens next on this side, and nothing below can undo that.
    # The window between the rotation response arriving and this store()
    # call is already minimal: no other I/O, logging, or awaited call sits
    # between them, so there is little left to narrow structurally. What
    # this can still do is make sure a failure here is never silent and
    # never a raw OSError or an uncaught KeyboardInterrupt: on failure, it
    # attempts a best-effort recovery write of the new token before
    # surfacing anything, and reports what actually happened either way.
    # A REMAINING WINDOW is stated rather than hidden: if the recovery
    # write also fails (the same disk-full condition can defeat a second,
    # smaller write too), the new token is genuinely lost from this
    # process, and a later invocation will replay the dead old token and
    # trigger the server's full-family revocation, now reported honestly
    # by SessionLostError rather than masked, but not prevented. A hard
    # process kill (SIGKILL) at this exact instant is not catchable by
    # Python at all; no exception handler below can see it.
    try:
        store(new_creds)
    except (OSError, KeyboardInterrupt) as exc:
        recovered = _write_recovery_copy(new_creds)
        if recovered:
            raise SessionLostError(
                f"The server rotated your session, but the new credentials "
                f"could not be saved to {CREDENTIALS_PATH} "
                f"({type(exc).__name__}: {exc}).",
                remedy=(
                    f"A recovery copy was written to {_recovery_path()} and "
                    f"will be used automatically the next time s3 runs. If "
                    f"that also fails, run: s3 login."
                ),
            ) from exc
        raise SessionLostError(
            f"The server rotated your session, but the new credentials "
            f"could not be saved to {CREDENTIALS_PATH} "
            f"({type(exc).__name__}: {exc}), and the emergency recovery "
            f"write also failed.",
            remedy="Your old session is no longer valid anywhere. Run: s3 login.",
        ) from exc
    return new_creds


async def refresh_locked(client: httpx.AsyncClient, creds: Credentials) -> Credentials:
    """Refresh the access token under an exclusive lock on the whole
    read-refresh-write critical section, and return the new `Credentials`.

    Re-reads CREDENTIALS_PATH after acquiring the lock. If the on-disk
    refresh token no longer matches `creds.refresh_token`, another
    invocation already rotated it while this one waited; the on-disk
    result is returned directly and the caller's stale token is never
    presented to the server, since doing so would trip the server's reuse
    detection and revoke the entire session family (`auth/router.py`'s
    `_revoke_family_on_reuse`).

    On a platform without `fcntl` (non-POSIX), this degrades to an
    unlocked refresh rather than raising: a single `s3` invocation still
    works, only the any-two-concurrent-invocations guarantee is lost. That
    loss is surfaced with a `RuntimeWarning` the first time it happens in
    a process, per `.claude/rules/production-standards.md`'s instruction
    to degrade honestly rather than silently proceed as if locked.
    """
    if not _HAS_FLOCK:
        global _warned_no_flock
        if not _warned_no_flock:
            warnings.warn(
                "fcntl is unavailable on this platform; refresh_locked is "
                "proceeding WITHOUT the exclusive lock that normally serializes "
                "concurrent refreshes. Two concurrent `s3` invocations here can "
                "both spend the same refresh token and log the user out of "
                "every surface.",
                RuntimeWarning,
                stacklevel=2,
            )
            _warned_no_flock = True
        return await _refresh_and_store(client, creds)

    async with _CredentialFileLock(_lock_path()):
        current = load()
        if current.refresh_token != creds.refresh_token:
            return current
        return await _refresh_and_store(client, current)
