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

Reads:
    - Environment variable: S3_CREDENTIALS_PATH (overrides the default
      `~/.system3/credentials` location; read once at import time into the
      CREDENTIALS_PATH module attribute, which callers and tests then
      treat as the single source of truth, per this module's own
      docstring convention of resolving the path through that attribute
      rather than re-reading the environment on every call).
    - CREDENTIALS_PATH: the stored `base_url`, `access_token` and
      `refresh_token`.

Writes:
    - CREDENTIALS_PATH: created at mode 600 from the first byte, replaced
      atomically on every `store()` call, never widened then narrowed.
    - CREDENTIALS_PATH's parent directory: created at mode 700 if absent.
    - A dedicated lock file beside CREDENTIALS_PATH (`.<name>.lock`), held
      only for the duration of `refresh_locked`'s critical section.

Never writes an access token, a refresh token, or a password to a log
message or an exception string anywhere in this module, per
`.claude/rules/production-standards.md`'s secrets gate. Every error below
names a status code, a mode, or a path; never a credential value.
"""

from __future__ import annotations

import asyncio
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
        return Path(override)
    return Path.home() / ".system3" / "credentials"


CREDENTIALS_PATH: Path = _default_credentials_path()

# Owner read/write only. Any bit outside this mask (group or other access,
# or even owner-execute) is what "wider than 600" refuses.
_SECURE_MODE = 0o600
_FORBIDDEN_MODE_BITS = 0o777 & ~_SECURE_MODE
_SECURE_DIR_MODE = 0o700

# This is an internal call to this system's own auth router, not one of the
# seven NCBI/graph tools `.claude/rules/tool-call-budgets.md` tabulates,
# but the same rule's "every outbound HTTP call carries an explicit
# timeout" line is not scoped to that table alone. 15 seconds matches the
# per-call budget this repo already uses for every other interactive HTTPS
# call.
REFRESH_TIMEOUT_SECONDS = 15.0

_warned_no_flock = False


class Credentials(NamedTuple):
    base_url: str
    access_token: str | None
    refresh_token: str


class InsecureCredentialsError(Exception):
    """The credential file's POSIX mode is wider than 0600.

    Raised instead of reading the file and warning: a file another local
    account can read is already compromised, and continuing would
    normalize the state the mode exists to prevent. The message names the
    exact remediation, per `.claude/rules/tool-call-budgets.md`'s
    actionable-error rule.
    """


class RefreshError(Exception):
    """`POST /auth/refresh` did not return 200.

    The stored refresh token is most likely expired, already rotated by a
    prior use, or revoked. The message never includes the token value.
    """


def load() -> Credentials:
    """Read `Credentials` from CREDENTIALS_PATH.

    Raises `InsecureCredentialsError` if the file's POSIX mode is wider
    than 0600 (skipped on a non-POSIX platform, where mode bits are not
    meaningful; see this module's docstring). Raises `FileNotFoundError`
    if no credential file exists yet.
    """
    path = CREDENTIALS_PATH
    if not path.exists():
        raise FileNotFoundError(f"No credentials at {path}. Run: s3 login")

    if os.name == "posix":
        mode = stat.S_IMODE(os.stat(path).st_mode)
        if mode & _FORBIDDEN_MODE_BITS:
            raise InsecureCredentialsError(
                f"{path} has mode {oct(mode)}, wider than 0600. Another local "
                f"account may be able to read it, so it is being refused rather "
                f"than read. Run: chmod 600 {path}"
            )

    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return Credentials(
        base_url=raw["base_url"],
        access_token=raw.get("access_token"),
        refresh_token=raw["refresh_token"],
    )


def store(creds: Credentials) -> None:
    """Persist `creds` to CREDENTIALS_PATH.

    Mode 600 from creation, never a widen-then-narrow: the temp file is
    opened with `os.open(..., O_CREAT | O_EXCL | O_WRONLY, 0o600)` so the
    permission bits are correct at the syscall that creates the file, not
    applied afterward by a separate `chmod`. The replace onto the final
    path is atomic (`os.replace`), so a reader never observes a
    partially-written file. The parent directory is created at mode 700 if
    absent, with the same discipline.
    """
    path = CREDENTIALS_PATH
    parent = path.parent
    if not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            os.chmod(parent, _SECURE_DIR_MODE)

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


def _lock_path() -> Path:
    return CREDENTIALS_PATH.parent / f".{CREDENTIALS_PATH.name}.lock"


class _CredentialFileLock:
    """An exclusive lock on a dedicated file beside CREDENTIALS_PATH.

    A SEPARATE lock file, never CREDENTIALS_PATH itself, so the lock's
    open file description is never affected by `store()`'s atomic
    temp-file-then-`os.replace()` sequence on the credential file proper.

    Acquisition runs in a worker thread via `run_in_executor`. `fcntl.
    flock` is a blocking OS call, and this lock is held across an `await`
    (the refresh HTTP call in `refresh_locked`). Calling it directly on
    the event-loop thread would block that thread until the lock is free,
    but the current holder's own coroutine needs the event loop to run in
    order to finish its await and release the lock, so a synchronous call
    here would deadlock a contending waiter against the holder it is
    waiting on. Running the blocking wait in a thread keeps the event loop
    free to schedule the holder's continuation.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._fd: int | None = None

    async def __aenter__(self) -> Self:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self._path), os.O_CREAT | os.O_RDWR, 0o600)
        if _HAS_FLOCK:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, fcntl.flock, self._fd, fcntl.LOCK_EX)
        return self

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
            f"refresh token is expired, already used, or revoked. Run: s3 login"
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
    store(new_creds)
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
