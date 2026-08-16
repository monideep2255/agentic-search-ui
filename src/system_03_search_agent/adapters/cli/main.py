"""The CLI entry point: `s3 ask`, `s3 stop`, and `s3 login`.

Build phase 4.2, ticket T-4.2-05 (`tracker/phase_4.2.md`). A thin
orchestrator over three sibling modules this phase builds in parallel
(credentials.py, client.py, render.py): it parses argv, drives the run
lifecycle (create, attach immediately, stream, stop), and applies the two
policies Section 13.3 and the tracker's premise both name explicitly:
`POST /v1/query` is never retried, UNCONDITIONALLY, including on a 401
(`_create_run_never_retried`, F-4.2-A-08/J-4.2-09); every other typed
client call (`stop`, and any future idempotent read) gets an expired
access token refreshed exactly once, transparently, followed by exactly
one retry of the failed call, never a loop (`_call_with_one_refresh`). No
agent logic, no grounding logic, no cost logic lives here; that all stays
server-side, per this module's own scope statement in
`tracker/phase_4.2.md`.

Depends on:
    - system_03_search_agent.adapters.cli.credentials (T-4.2-02, imported
      lazily inside the functions that use it, not at module level)
    - system_03_search_agent.adapters.cli.client (T-4.2-03, imported
      lazily, same reason). `CliClient` raises typed errors for a
      non-2xx response, not a bare httpx.HTTPStatusError: the base
      `CliApiError` itself (for any status this module's five named
      subclasses do not cover, F-4.2-A-05), `AuthExpiredError` (401),
      `ForbiddenError` (403), `NotFoundError` (404), `ConflictError`
      (409), `RateLimitedError` (429). `AuthExpiredError` is the only one
      this module ever reissues a call over, and only for calls that go
      through `_call_with_one_refresh` (never `create_run`, which has its
      own stricter `_create_run_never_retried`); every other typed error,
      and a second `AuthExpiredError` after a retry, is rendered and
      unwound the same way. `CliClient` also carries two post-stream
      attributes this module reads (never sets) after the stream ends,
      `stream_skipped_frame_count` and `stream_truncated` (F-4.2-A-28,
      the lead's phase-4.2 correction): see
      `_consume_stream_with_interrupt`'s own docstring.
    - system_03_search_agent.adapters.cli.credentials's `CredentialsError`
      base and its six subclasses (`InsecureCredentialsError`,
      `RefreshError`, `SessionLostError`, `CorruptCredentialsError`,
      `RefreshLockTimeoutError`, `RefreshLockUnavailableError`, per the
      lead's phase-4.2 correction): this module catches the BASE
      wherever a `credentials.load()` or `credentials.refresh_locked()`
      call can fail, never an enumerated subclass list, so a new
      subclass added to credentials.py later needs no matching change
      here (`_render_credentials_error`'s own docstring explains why,
      including `SessionLostError`'s distinct wording).
    - system_03_search_agent.adapters.cli.render (T-4.2-04, imported
      lazily, same reason). `render_client_error(err, exc)` is the seam
      for rendering any of the five typed client errors above: it owns
      the mixed-body problem (a structured 429 detail dict versus a
      bare-string 401/403/404/409 detail), so this module never parses a
      response body itself for a CliClient-raised failure.
    - system_03_search_agent.contracts.events.Event (type-checking only;
      this module never constructs an Event, and passes whatever
      `client.stream_events` yields straight to `renderer.handle`. The
      one exception is `_consume_stream_with_interrupt` reading the bare
      `event.type` string, never the payload, to detect a truncated
      stream and an empty `done` (F-4.2-A-16/F-4.2-A-15); see that
      function's own docstring)
    - httpx (the injected or self-constructed async HTTP client)

The three lazy imports above are deferred into function bodies rather
than hoisted to the top of the file on purpose: this file, in isolation,
is testable against stubbed collaborators (`tests/system_03_search_agent/
adapters/cli/test_main.py` injects fakes into `sys.modules`) even before
the sibling modules exist on disk, which matters during this phase's
parallel build. Once all four modules exist together, importing this
module the normal way (as the shared premise gate's `_require_cli_main_
module` fixture does) behaves identically either way; the deferral only
changes when the ModuleNotFoundError would surface, not whether it does.

Reads:
    - stdin: `s3 login`'s password, one line, never a command-line
      argument (argv is visible to every process on the machine via `ps`).
    - Environment variable: S3_CREDENTIALS_PATH, indirectly, since
      credentials.py reads it, not this module.
    - Environment variable: S3_BASE_URL, read only by `main()`'s own
      sync wrapper, as the fallback base URL for `s3 login` when no
      `--base-url` flag and no stored credential file exist yet.

Writes:
    - stdout, stderr: the rendered answer, status lines, and error
      messages (via the injected streams in `async_main`, or real
      `sys.stdout`/`sys.stderr` in `main`).
    - The credential file at `credentials.CREDENTIALS_PATH`, indirectly,
      through `credentials.store()` and `credentials.refresh_locked()`.
      This module never opens or writes that file itself.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import getpass
import os
import signal
import sys
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, NoReturn, TextIO, TypeVar

import httpx

if TYPE_CHECKING:
    from system_03_search_agent.adapters.cli.client import CliClient
    from system_03_search_agent.adapters.cli.credentials import Credentials
    from system_03_search_agent.adapters.cli.render import Renderer
    from system_03_search_agent.contracts.events import Event

T = TypeVar("T")

# The exit code Ctrl-C produces: 128 + SIGINT(2), the conventional shell
# signal-exit code, and in every case still nonzero, which is all the
# premise gate itself asserts.
EXIT_INTERRUPTED = 130

# No canonical production host is named anywhere in the locked spec or
# the tracker; this is a local-dev fallback only, used when `s3 login`
# is run with neither `--base-url` nor `S3_BASE_URL` set. `ask` and
# `stop` never use it: they always read the base_url a prior `s3 login`
# already recorded in the credential file.
_DEFAULT_BASE_URL = "http://127.0.0.1:8000"

# connect/write/pool stay short since those are quick request/response
# legs; read stays generous since the SSE stream for a deep_technical
# query can run for minutes. The server's own per-query cost cap and
# per-step timeouts (system-design-patterns.md pattern 4) are what
# actually bound total run time, not this client-side socket timeout.
# `_run_login`'s own POST /auth/login call does NOT use this generous
# read timeout (see _LOGIN_TIMEOUT_SECONDS below): the http_client's
# default here only ever bounds the one long-lived call, the SSE stream.
_DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)

# J-4.2-07: `POST /auth/login` declared no timeout of its own, so it
# silently inherited `_DEFAULT_TIMEOUT`'s 120.0s read leg, an eightfold
# drift from the 15s budget credentials.py's `REFRESH_TIMEOUT_SECONDS`
# already applies to `POST /auth/refresh`, the identical auth-router call
# shape (a plain request/response round trip against this repo's own
# backend, never a live third-party API). Matched here rather than left
# to inherit the stream's own generous budget.
_LOGIN_TIMEOUT_SECONDS: float = 15.0


class _ArgparseExit(Exception):
    """Raised by `_CliArgumentParser` in place of `sys.exit`, so a parse
    failure or `--help` is testable through the same captured-stream
    seam as every other path in this module rather than killing the
    whole test process.
    """

    def __init__(self, code: int) -> None:
        super().__init__(f"argument parsing exited with code {code}")
        self.code = code


class _CommandError(Exception):
    """Unwinds a command to an already-rendered stderr message and a
    fixed nonzero exit code, so the top-level dispatcher has one place to
    turn a caught, already-explained failure into a return value.
    """

    def __init__(self, exit_code: int) -> None:
        super().__init__(f"command failed, exit code {exit_code}")
        self.exit_code = exit_code


class _CliArgumentParser(argparse.ArgumentParser):
    """An `ArgumentParser` that raises `_ArgparseExit` instead of calling
    `sys.exit`, and writes usage, help, and error text to the injected
    streams instead of the real `sys.stdout`/`sys.stderr`.
    """

    def __init__(self, *args: object, out: TextIO, err: TextIO, **kwargs: object) -> None:
        self._out = out
        self._err = err
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

    def print_usage(self, file: TextIO | None = None) -> None:
        super().print_usage(self._err)

    def print_help(self, file: TextIO | None = None) -> None:
        super().print_help(self._out)

    def error(self, message: str) -> NoReturn:
        self.print_usage()
        self._err.write(f"{self.prog}: error: {message}\n")
        raise _ArgparseExit(2)

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        if message:
            self._err.write(message)
        raise _ArgparseExit(status)


def _read_password(stdin: TextIO) -> str:
    """Reads exactly one line of password input. Never argv: a password
    passed as a command-line argument is visible to every process on the
    machine via `ps`, which is the whole reason `s3 login` takes it from
    stdin instead.

    F-4.2-A-14: verified against a real pty that a plain `stdin.readline()`
    here left the terminal's ECHO bit on, so the typed password was
    printed to the screen and left in scrollback. When `stdin` is a real,
    interactive terminal (`stdin.isatty()`), this reads through
    `getpass.getpass` instead, which disables echo at the terminal driver
    for the duration of the read. When `stdin` is not a TTY, this falls
    back to a plain line read, since `getpass.getpass` itself refuses a
    non-interactive stream; this is also the path the premise gate and
    every test in this file exercise, per `tracker/phase_4.2.md`'s own
    stated coverage exclusion ("Interactive password entry... reads the
    password from a non-TTY stream in the gate").
    """
    isatty = getattr(stdin, "isatty", None)
    if callable(isatty) and isatty():
        return getpass.getpass("")
    line = stdin.readline()
    return line.rstrip("\n").rstrip("\r")


def _extract_error_message(response: httpx.Response) -> str:
    """Renders either error-body shape `app.py` actually produces,
    without crashing on either: a structured 429
    (`{"detail": {"reason": ..., "message": ...}}`) and a bare-string
    401/403/404/409 (`{"detail": "..."}`). Falls back to the bare status
    code if the body is not JSON at all, or carries neither shape.

    Scoped to the two call sites that never go through `CliClient` and
    therefore never raise one of its five typed errors: `s3 login`'s
    direct `POST /auth/login` call, and `credentials.refresh_locked`'s
    `POST /auth/refresh` call. Every `CliClient` method failure (create,
    stop, stream open) uses `render.render_client_error` instead, per the
    lead's phase-4.2 correction: that function is the single seam for
    the same mixed-body problem this one also handles, scoped to the
    typed errors client.py actually raises.
    """
    try:
        body = response.json()
    except ValueError:
        return f"request failed with status {response.status_code}"

    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, dict):
        message = detail.get("message")
        if isinstance(message, str) and message:
            return message
        reason = detail.get("reason")
        if isinstance(reason, str) and reason:
            return reason
    if isinstance(detail, str) and detail:
        return detail
    return f"request failed with status {response.status_code}"


def _client_typed_errors() -> tuple[type[Exception], ...]:
    """Lazily imports and returns `CliClient`'s typed-error hierarchy for
    a non-2xx response (client.py, T-4.2-03): the five named subclasses
    PLUS the `CliApiError` base itself, so a call site can
    `except _client_typed_errors() as exc:` without repeating the same
    import block. Order is not meaningful; `except` accepts any tuple of
    exception types.

    F-4.2-A-05: `client.py`'s `_raise_for_status` raises the bare
    `CliApiError` base directly for any status code NOT in its five-entry
    `_ERROR_CLASS_BY_STATUS` map (400, 500, 502, 503, and any other status
    the server might one day return): `error_cls =
    _ERROR_CLASS_BY_STATUS.get(response.status_code, CliApiError)`. A
    tuple of only the five named subclasses never matches an instance of
    the bare base, so every one of those status codes fell through every
    `except _client_typed_errors()` clause in this module to the nearest
    unrelated generic catch, dumping a raw, uncapped body to the terminal
    instead of going through `render.render_client_error`. This is the
    THIRD instance of that same shape this phase (see
    `_call_with_one_refresh`'s refresh-failure handling below, and its own
    comment for the second).
    """
    from system_03_search_agent.adapters.cli.client import (
        AuthExpiredError,
        CliApiError,
        ConflictError,
        ForbiddenError,
        NotFoundError,
        RateLimitedError,
    )

    return (
        CliApiError,
        AuthExpiredError,
        ForbiddenError,
        NotFoundError,
        ConflictError,
        RateLimitedError,
    )


def _render_client_error(stderr: TextIO, exc: Exception) -> None:
    """Thin, lazily-imported wrapper around `render.render_client_error`
    (T-4.2-04): the single seam for rendering any of the five typed
    client errors above without this module parsing a response body
    itself.
    """
    from system_03_search_agent.adapters.cli.render import render_client_error

    render_client_error(stderr, exc)


def _render_credentials_error(stderr: TextIO, exc: Exception) -> None:
    """Renders any of credentials.py's `CredentialsError` subclasses
    (`InsecureCredentialsError`, `RefreshError`, `SessionLostError`,
    `CorruptCredentialsError`, `RefreshLockTimeoutError`,
    `RefreshLockUnavailableError`, per the lead's phase-4.2 correction)
    off the COMMON BASE, never a per-type mapping this module would have
    to keep hand-synced with credentials.py's own exception list. That
    hand-synced list is exactly the defect this function replaces: this
    phase already caught the same shape three times over (F-4.2-A-05,
    F-4.2-A-06/J-4.2-02, and a fourth found at the merge boundary when
    credentials.py grew from two exception types to six mid-phase), and a
    list is a second place to forget a type, so catching the base is what
    makes a seventh type added later need no matching change here.

    `SessionLostError` gets distinct, more alarming wording FIRST: it
    means the server rotated the refresh token and this process could not
    persist the rotation, so the caller's ENTIRE session, on every
    surface, is already dead, not just this command. Rendering it as an
    ordinary "could not refresh" message would let a caller waste real
    time retrying a session that structurally cannot come back; the only
    remedy is `s3 login`.

    Every other `CredentialsError` renders its own `str(exc)` (already the
    curated, actionable message per credentials.py's own docstring
    convention, e.g. `RefreshError`'s message already ends "Run: s3
    login") plus a `.remedy` attribute, when the base class carries one
    and it is not already part of that message, rather than this module
    re-deriving what the remedy is per type.
    """
    from system_03_search_agent.adapters.cli import credentials as credentials_module

    if isinstance(exc, credentials_module.SessionLostError):
        stderr.write(
            f"s3: your session was logged out on every surface, not just this "
            f"command ({exc}); run 's3 login' to sign in again\n"
        )
        return

    message = str(exc)
    remedy = getattr(exc, "remedy", None)
    if remedy and remedy not in message:
        stderr.write(f"s3: {message} {remedy}\n")
    else:
        stderr.write(f"s3: {message}\n")


async def _call_with_one_refresh(
    coro_factory: Callable[[Credentials], Awaitable[T]],
    *,
    http_client: httpx.AsyncClient,
    creds: Credentials,
    stderr: TextIO,
) -> tuple[T, Credentials]:
    """Calls `coro_factory(creds)` once. `coro_factory` must be a
    `CliClient` method call whose reissue on a fresh token is safe, i.e.
    every call EXCEPT `create_run` (see `_create_run_never_retried`
    below, which owns that one instead, per F-4.2-A-08/J-4.2-09). This
    function catches `CliClient`'s typed-error hierarchy for a non-2xx
    response (client.py, T-4.2-03): `AuthExpiredError` (401),
    `ForbiddenError` (403), `NotFoundError` (404), `ConflictError` (409),
    `RateLimitedError` (429), and the bare `CliApiError` base itself for
    any other status.

    On `AuthExpiredError`, refreshes exactly once via
    `credentials.refresh_locked` (which itself persists the rotated
    refresh token to disk, under an exclusive lock, before returning) and
    reissues the SAME call exactly once with the refreshed credentials.
    Any other typed error, or a second `AuthExpiredError` after the
    retry, is rendered via `render.render_client_error` and unwound via
    `_CommandError`. Never a loop, and never applied to a transport-level
    failure (a timeout or a connection error): those propagate to the
    caller untouched, since a 401 on one of the calls THIS function
    covers (stop, and any future idempotent read) is rejected before any
    handler body runs and is always safe to reissue, while a network
    timeout carries no such guarantee (the server may already have
    processed the original request).

    Returns the call's result alongside whatever credentials actually
    ended up being used, so the caller's local `creds` stays current for
    any later call in the same command.
    """
    from system_03_search_agent.adapters.cli import credentials as credentials_module
    from system_03_search_agent.adapters.cli.client import AuthExpiredError

    typed_errors = _client_typed_errors()
    non_auth_errors = tuple(err for err in typed_errors if err is not AuthExpiredError)

    try:
        result = await coro_factory(creds)
        return result, creds
    except AuthExpiredError:
        pass
    except non_auth_errors as exc:
        _render_client_error(stderr, exc)
        raise _CommandError(1) from exc

    # Only an AuthExpiredError reaches here. It is rejected before any
    # handler body runs (get_caller's dependency fails first), so
    # reissuing the SAME call once with a freshly refreshed token is
    # always safe, unlike a blind retry on a network timeout, which this
    # function never touches (see the httpx.TransportError handling at
    # each call site instead).
    #
    # refresh_locked wraps POST /auth/refresh directly against the given
    # httpx.AsyncClient, never through CliClient, so its failure is never
    # one of client.py's typed errors, and it is NOT an httpx.HTTPStatusError
    # either: credentials.py raises off its own `CredentialsError` base
    # (InsecureCredentialsError, RefreshError, SessionLostError,
    # CorruptCredentialsError, RefreshLockTimeoutError,
    # RefreshLockUnavailableError, per the lead's phase-4.2 correction),
    # caught here by that base rather than a hand-maintained list of
    # subclasses (J-4.2-02/F-4.2-A-06: this catch used to be `except
    # httpx.HTTPStatusError`, a type refresh_locked never raises, so this
    # repo's most routine failure, an expired session, fell straight
    # through to async_main's generic catch-all and was reported as
    # "unexpected" instead of a curated message; catching by base, not by
    # an enumerated list, is what stops the same defect recurring a
    # fourth time as credentials.py's own exception set keeps growing).
    # `FileNotFoundError` stays separate: it means "no credential file at
    # all" (the re-read `load()` call under the lock can hit this if
    # another process deleted the file while this one waited), a
    # different situation from a malformed or insecure one, and it is a
    # plain builtin, not part of credentials.py's own hierarchy.
    try:
        creds = await credentials_module.refresh_locked(http_client, creds)
    except credentials_module.CredentialsError as refresh_exc:
        _render_credentials_error(stderr, refresh_exc)
        raise _CommandError(1) from refresh_exc
    except FileNotFoundError as refresh_exc:
        stderr.write("s3: not logged in; run 's3 login' first\n")
        raise _CommandError(1) from refresh_exc

    try:
        result = await coro_factory(creds)
    except typed_errors as exc2:
        _render_client_error(stderr, exc2)
        raise _CommandError(1) from exc2
    return result, creds


async def _create_run_never_retried(
    coro_factory: Callable[[Credentials], Awaitable[T]],
    *,
    http_client: httpx.AsyncClient,
    creds: Credentials,
    stderr: TextIO,
) -> T:
    """Calls `coro_factory(creds)` (a `CliClient.create_run` call) EXACTLY
    ONCE, no matter what happens, including an `AuthExpiredError`.

    F-4.2-A-08/J-4.2-09: `_call_with_one_refresh`'s "a 401 is always safe
    to reissue" reasoning does not hold for `POST /v1/query` in general.
    That reasoning is true for the ordinary case, an expired access
    token, rejected by `get_caller`'s dependency before the handler body
    ever runs. But `app.py`'s create-run handler ALSO raises a 401 from
    INSIDE the handler body, after `count_active_runs_for_owner` and
    after `spend_one_anonymous_run`, when a guest session was migrated or
    revoked at signup (`SpendState.REVOKED_OR_UNKNOWN`,
    `adapters/web_sse/app.py`). A comment in an earlier version of this
    function claimed the dependency-rejection shape held universally for
    every call this module makes; it does not, for this specific
    endpoint. `tracker/phase_4.2.md`'s phase premise states the rule this
    function exists to guarantee without exception: "The CLI's retry
    policy NEVER covers POST /v1/query. That endpoint carries no
    idempotency key, so retrying a timed-out create spends a second
    allowance slot against a run that may already exist." A 401-triggered
    refresh-and-reissue IS a retry of that call, so `create_run` gets this
    stricter, separate function instead of `_call_with_one_refresh`,
    rather than a carve-out inside it. (In practice, the CLI never even
    holds a guest token today, since `s3 login` only ever mints a user
    session; that is an accident of how login is built, not a structural
    guarantee this function relies on, per this same finding's own
    wording, so the fix does not lean on it.)

    On `AuthExpiredError`, this refreshes the STORED credentials via
    `credentials.refresh_locked` so the NEXT `s3 ask` invocation is not
    immediately handed the same expired token, but it never reissues
    THIS create call. The original `AuthExpiredError` is always what gets
    rendered and raised as `_CommandError(1)`, regardless of whether the
    background refresh itself succeeded or failed, since the create
    already did not happen either way and that is the fact the user
    needs reported.
    """
    from system_03_search_agent.adapters.cli import credentials as credentials_module
    from system_03_search_agent.adapters.cli.client import AuthExpiredError

    typed_errors = _client_typed_errors()
    non_auth_errors = tuple(err for err in typed_errors if err is not AuthExpiredError)

    try:
        return await coro_factory(creds)
    except AuthExpiredError as exc:
        # Best-effort only, made STRUCTURAL rather than a list of
        # suppressed types (F-4.2-D-05, the composition case). Whether
        # this background refresh succeeds or fails changes nothing
        # about what gets reported below: the original `AuthExpiredError`
        # is ALWAYS what gets rendered and raised, because the create
        # already did not happen either way and that is the fact the
        # user needs reported. A named list here
        # (`credentials_module.CredentialsError`, `FileNotFoundError`,
        # `httpx.HTTPError`) is a second place to forget a type the
        # instant `refresh_locked` grows a new failure shape, which is
        # exactly the defect this phase already hit three times over
        # naming a catcher whose raiser had moved on (F-4.2-A-05,
        # J-4.2-02, and this finding itself: a bare
        # `json.JSONDecodeError`/`KeyError` out of `refresh_locked`
        # escaped this exact suppress list, none of `CredentialsError`,
        # `FileNotFoundError`, or `httpx.HTTPError`, and replaced the
        # curated "Run `s3 login`" message with a bare "unexpected
        # error"). `except Exception` is the structural fix: it is a
        # closed Python guarantee that every ordinary exception
        # `refresh_locked` raises or ever will raise is caught here,
        # with no enumerated list to keep in sync, while
        # `KeyboardInterrupt`/`SystemExit`/`GeneratorExit` (the three
        # `BaseException` siblings `Exception` deliberately excludes)
        # still propagate, since swallowing a user-issued interrupt
        # inside a best-effort side call would be its own defect.
        with contextlib.suppress(Exception):
            await credentials_module.refresh_locked(http_client, creds)
        _render_client_error(stderr, exc)
        raise _CommandError(1) from exc
    except non_auth_errors as exc:
        _render_client_error(stderr, exc)
        raise _CommandError(1) from exc


def _load_credentials_or_report(stderr: TextIO) -> Credentials | None:
    """Loads the stored credentials, or writes an actionable message and
    returns None. Never widens or repairs an insecure or corrupt
    credential file; `credentials.load()` itself refuses to read one
    wider than mode 600 (and, per the lead's phase-4.2 correction, now
    raises a typed `CorruptCredentialsError` rather than leaking a bare
    `json.JSONDecodeError`/`KeyError`/`TypeError` for an unreadable or
    malformed file), and this function only reports that refusal, it does
    not work around it.
    """
    from system_03_search_agent.adapters.cli import credentials as credentials_module

    try:
        return credentials_module.load()
    except FileNotFoundError:
        stderr.write("s3: not logged in; run 's3 login' first\n")
        return None
    except credentials_module.CredentialsError as exc:
        # The base class, not a per-type list: see
        # `_render_credentials_error`'s own docstring for why.
        _render_credentials_error(stderr, exc)
        return None
    except OSError as exc:
        # type(exc).__name__ only, never str(exc): an OSError's message
        # can carry a full filesystem path, and this module's own
        # constraint is no raw exception text in user-facing output,
        # anywhere. A defensive fallback: every failure mode `load()`
        # itself documents is one of the two branches above; this only
        # fires if a future filesystem-level failure escapes both.
        stderr.write(
            f"s3: could not read the stored credentials ({type(exc).__name__}); "
            "check that the file exists and is readable\n"
        )
        return None


# ---------------------------------------------------------------------------
# Argument parsing, one small parser per subcommand rather than argparse
# subparsers, so each carries its own injected out/err streams cleanly.
# ---------------------------------------------------------------------------


def _parse_ask_args(argv: Sequence[str], *, out: TextIO, err: TextIO) -> argparse.Namespace:
    # No --operator flag. F-4.2-A-09/J-4.2-03: it used to exist here,
    # `action="store_true"`, reaching `Renderer(operator=...)` straight
    # from argv with no credential check anywhere in between. Operator
    # status is server-side truth, derived from an allowlist keyed on
    # user id (`harness/cost_control.py`'s `is_operator_user`), and a
    # client cannot determine it without a server round trip this module
    # does not make. The phase premise's claim that the CLI's cost
    # suppression is "a second, independent layer" that "holds
    # independently" was false while a caller could flip that layer off
    # by typing a flag; removing the flag is what makes the remaining
    # claim (this module never prints a dollar figure) actually true,
    # rather than wiring the flag to a check this module has no way to
    # perform. `_run_ask` below always constructs `Renderer(...,
    # operator=False)` now, unconditionally.
    parser = _CliArgumentParser(prog="s3 ask", out=out, err=err)
    parser.add_argument("question", help="the question to ask")
    parser.add_argument(
        "--session-id",
        default=None,
        help="a session id to group related questions; a fresh one is generated if omitted",
    )
    parser.add_argument(
        "--depth",
        choices=["clinical_brief", "researcher", "deep_technical"],
        default="researcher",
        help="the audience depth for the answer",
    )
    return parser.parse_args(list(argv))


def _parse_stop_args(argv: Sequence[str], *, out: TextIO, err: TextIO) -> argparse.Namespace:
    parser = _CliArgumentParser(prog="s3 stop", out=out, err=err)
    parser.add_argument("run_id", help="the run id to stop")
    return parser.parse_args(list(argv))


def _parse_login_args(argv: Sequence[str], *, out: TextIO, err: TextIO) -> argparse.Namespace:
    parser = _CliArgumentParser(prog="s3 login", out=out, err=err)
    parser.add_argument("email", help="the account email")
    parser.add_argument(
        "--base-url",
        default=None,
        help=(
            "the server to log into; consumed by main()'s sync wrapper before the HTTP "
            "client is built, not read here, since async_main is always handed an "
            "already-constructed client"
        ),
    )
    return parser.parse_args(list(argv))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


async def _run_login(
    args: argparse.Namespace,
    *,
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    http_client: httpx.AsyncClient,
) -> int:
    """Wraps `POST /auth/login`. The password is read from stdin, never
    argv, and never appears in any message this function writes, on
    success or failure. When stdin is a real, interactive terminal, it is
    also never echoed to the screen (`_read_password` uses
    `getpass.getpass` in that case, F-4.2-A-14); when stdin is not a TTY,
    for example the injected stream every test in this file and the
    premise gate drive `s3 login` with, there is no terminal to echo to
    in the first place. A failed login never calls `credentials.store`,
    so any pre-existing credential file is left byte-unchanged rather
    than truncated.
    """
    from system_03_search_agent.adapters.cli import credentials as credentials_module
    from system_03_search_agent.adapters.cli.render import _sanitize_untrusted

    password = _read_password(stdin)
    if not password:
        stderr.write("s3 login: no password was provided on stdin\n")
        return 1

    try:
        response = await http_client.post(
            "/auth/login",
            json={"email": args.email, "password": password},
            timeout=_LOGIN_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        stderr.write(f"s3 login: could not reach the server ({type(exc).__name__})\n")
        return 1

    if response.status_code != 200:
        # F-4.2-D-03: this is the FIRST command anyone runs, before any
        # credential exists, and it is reachable through a user-supplied
        # `--base-url`/`S3_BASE_URL`, so a mistyped or hostile host owns
        # this write before authentication. `_extract_error_message`
        # returns the server's own `detail`/`detail.message`/
        # `detail.reason` text verbatim, which is untrusted content by
        # `ai-security-standards.md`'s "treat AI output as untrusted"
        # rule the same way any other server-controlled field is,
        # regardless of which endpoint delivered it. Routed through
        # `render.py`'s own `_sanitize_untrusted`, the single sanitizer
        # this codebase has for exactly this class of write, rather than
        # a second copy: it neutralizes ANSI control sequences and bidi
        # overrides (Cc/Cf/Cs/Co Unicode categories) before this ever
        # reaches a terminal.
        stderr.write(f"s3 login: {_sanitize_untrusted(_extract_error_message(response))}\n")
        return 1

    # F-4.2-D-05: a 200 with a non-JSON body, or a JSON body missing
    # `access_token`/`refresh_token`, used to crash raw
    # (`json.JSONDecodeError`/`KeyError`) instead of failing with an
    # actionable message. This validates the same three things
    # `client.py`'s own `_parse_json_body` validates for its four
    # `CliClient`-routed endpoints (F-4.2-A-24: content type, then that
    # the body actually parses as JSON), inline rather than imported,
    # since `/auth/login` is never called through `CliClient` and this
    # function already owns its own status-code check above; the shape
    # of the check is intentionally identical, not a different policy.
    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        stderr.write(
            f"s3 login: the server returned a non-JSON response (content-type "
            f"{content_type or 'none'}); this indicates a server or proxy "
            "misconfiguration, not a normal failure. Retry, or report this "
            "if it recurs.\n"
        )
        return 1
    try:
        body = response.json()
    except ValueError as exc:
        stderr.write(
            f"s3 login: the server declared a JSON content type but the body "
            f"did not parse as JSON ({type(exc).__name__}); retry, or report "
            "this if it recurs.\n"
        )
        return 1

    access_token = body.get("access_token") if isinstance(body, dict) else None
    refresh_token = body.get("refresh_token") if isinstance(body, dict) else None
    if not isinstance(access_token, str) or not isinstance(refresh_token, str):
        stderr.write(
            "s3 login: the server's response was missing the expected "
            "access_token/refresh_token fields; try again, or report this "
            "if it recurs\n"
        )
        return 1

    creds = credentials_module.Credentials(
        base_url=str(http_client.base_url),
        access_token=access_token,
        refresh_token=refresh_token,
    )
    credentials_module.store(creds)
    stdout.write("logged in\n")
    return 0


async def _run_stop(
    args: argparse.Namespace,
    *,
    stdout: TextIO,
    stderr: TextIO,
    http_client: httpx.AsyncClient,
) -> int:
    """`POST /v1/query/{run_id}/stop`. Idempotent server-side (Section
    13.1): stopping an already-finished run is still a 200, so this
    command exits 0 either way. Stopping a run owned by someone else
    surfaces the real 403 through `_call_with_one_refresh`'s generic
    error path and exits nonzero.
    """
    from system_03_search_agent.adapters.cli.client import CliClient

    creds = _load_credentials_or_report(stderr)
    if creds is None:
        return 1

    try:
        stopped, _creds = await _call_with_one_refresh(
            lambda c: CliClient(http_client, c).stop(args.run_id),
            http_client=http_client,
            creds=creds,
            stderr=stderr,
        )
    except _CommandError as exc:
        return exc.exit_code
    except httpx.TransportError as exc:
        stderr.write(f"s3 stop: could not reach the server ({type(exc).__name__})\n")
        return 1

    stdout.write("run stopped\n" if stopped else "run was already finished\n")
    return 0


async def _run_ask(
    args: argparse.Namespace,
    *,
    stdout: TextIO,
    stderr: TextIO,
    http_client: httpx.AsyncClient,
    interrupt_signals: asyncio.Queue[None] | None,
    sigint_scope: contextlib.AbstractContextManager[None] | None = None,
) -> int:
    """`POST /v1/query`, then attaches to the event stream immediately,
    then renders every event as it arrives. `POST /v1/query` itself is
    never retried by this function on any failure shape, including a
    transport timeout and including a 401 (`_create_run_never_retried`,
    F-4.2-A-08/J-4.2-09): the phase premise's rule is unconditional, "The
    CLI's retry policy NEVER covers POST /v1/query", with no 401
    exception. `sigint_scope`, when given, is entered ONLY around the
    stream-consumption call below (F-4.2-A-04): see `main()`'s own
    docstring for why the real SIGINT handler is scoped that narrowly
    rather than installed for this function's whole body.
    """
    from system_03_search_agent.adapters.cli.client import CliClient
    from system_03_search_agent.adapters.cli.render import Renderer

    creds = _load_credentials_or_report(stderr)
    if creds is None:
        return 1

    session_id = args.session_id or uuid.uuid4().hex

    try:
        run_id, _persona_name = await _create_run_never_retried(
            lambda c: CliClient(http_client, c).create_run(
                text=args.question, session_id=session_id, audience_depth=args.depth
            ),
            http_client=http_client,
            creds=creds,
            stderr=stderr,
        )
    except _CommandError as exc:
        return exc.exit_code
    except httpx.TransportError as exc:
        stderr.write(
            "s3 ask: could not reach the server to start the run "
            f"({type(exc).__name__}); the request is not retried, since a timed-out "
            "create may already have been processed and spent an allowance slot\n"
        )
        return 1

    # Attach to the event stream IMMEDIATELY. The server cancels a run
    # with zero attached subscribers for a cumulative 30 seconds, and
    # reconnect churn does not reset that budget (tracker/phase_4.2.md's
    # pre-build source read on core/run_registry.py). Nothing awaits
    # between the create_run call above and the first __anext__ below, on
    # purpose: not a log line, not a second round trip, not even
    # constructing Renderer or CliClient after the stream starts, since
    # every statement here up to the first `await` inside
    # `_consume_stream_with_interrupt` is plain, synchronous Python.
    #
    # operator=False, unconditionally. F-4.2-A-09/J-4.2-03: there is no
    # client-supplied way left to ask for cost fields (see
    # `_parse_ask_args`'s comment on why `--operator` was removed rather
    # than wired to a check this module cannot perform).
    renderer = Renderer(stdout, stderr, operator=False)
    client = CliClient(http_client, creds)
    stream_iter = client.stream_events(run_id).__aiter__()

    with sigint_scope or contextlib.nullcontext():
        outcome = await _consume_stream_with_interrupt(
            stream_iter,
            renderer,
            client=client,
            run_id=run_id,
            interrupt_signals=interrupt_signals,
            stderr=stderr,
        )
    if outcome is not None:
        return outcome
    return renderer.finish()


# ---------------------------------------------------------------------------
# Streaming loop with a Ctrl-C race
# ---------------------------------------------------------------------------


def _swallow_task_exception(task: asyncio.Task[object]) -> None:
    """Prevents an "exception was never retrieved" warning from a
    best-effort background stop call that nobody waits on after a second
    Ctrl-C.
    """
    if not task.cancelled():
        task.exception()


async def _handle_interrupt_during_stream(
    pending_next: asyncio.Task[object],
    *,
    client: CliClient,
    run_id: str,
    interrupt_signals: asyncio.Queue[None] | None,
    stderr: TextIO,
) -> int:
    """Ctrl-C sends `POST /v1/query/{run_id}/stop` before the process
    exits, so an interrupted session halts the server-side loop instead
    of leaving it running unseen. A second Ctrl-C arriving while that
    stop call is still in flight exits immediately rather than waiting
    for its response: a user who interrupts twice wants out, and the
    stop call is best-effort at that point, not something worth blocking
    exit on.
    """
    stderr.write("s3: interrupted, stopping the run...\n")
    if not pending_next.done():
        pending_next.cancel()

    stop_task: asyncio.Task[bool] = asyncio.ensure_future(client.stop(run_id))
    stop_task.add_done_callback(_swallow_task_exception)

    second_interrupt_task: asyncio.Task[None] | None = None
    if interrupt_signals is not None:
        second_interrupt_task = asyncio.ensure_future(interrupt_signals.get())

    wait_for: set[asyncio.Future[object]] = {stop_task}
    if second_interrupt_task is not None:
        wait_for.add(second_interrupt_task)

    done, _pending = await asyncio.wait(wait_for, return_when=asyncio.FIRST_COMPLETED)

    if second_interrupt_task is not None and second_interrupt_task in done:
        # The stop call is left running in the background, best-effort:
        # not awaited further, not cancelled, since cancelling an
        # in-flight HTTP request here would abandon it mid-write with no
        # cleaner outcome either way. We simply stop waiting on it.
        stderr.write("s3: interrupted again, exiting immediately\n")
        return EXIT_INTERRUPTED

    if second_interrupt_task is not None and not second_interrupt_task.done():
        second_interrupt_task.cancel()
    return EXIT_INTERRUPTED


async def _consume_stream_with_interrupt(
    stream_iter: AsyncIterator[Event],
    renderer: Renderer,
    *,
    client: CliClient,
    run_id: str,
    interrupt_signals: asyncio.Queue[None] | None,
    stderr: TextIO,
) -> int | None:
    """Feeds every event to `renderer.handle` until the stream ends on
    its own, which happens when the server closes the SSE response after
    `done` or a fatal `error` (including a stopped run's `error`/
    `cancelled`, which is a fatal terminal event, never a `done`, so
    exit logic must never key only on `done`). Returns None in that
    case, meaning the caller should finish normally via
    `renderer.finish()`. Returns an exit code directly if Ctrl-C
    interrupted the run first, in which case no further event is
    rendered and the caller must not also call `renderer.finish()`.

    F-4.2-A-16/F-4.2-A-15/F-4.2-A-28: three genuinely different things can
    go wrong on the way to a normal-looking stream end, and this function
    reports each with its OWN sentence rather than collapsing them into
    one, since a user piping to a file has no other channel to learn
    which one actually happened:

    1. `client.stream_skipped_frame_count` (new client.py attribute, per
       the lead's phase-4.2 correction): a frame that could not be
       decoded, or carried an event type this codebase does not
       recognize, is now SKIPPED rather than aborting the whole run
       (`system-design-patterns` rule 10 names a new enum value as an
       allowed additive v1 change, so client.py must tolerate one). But
       tolerating it silently would be its own defect: the answer above
       may be missing whatever those frames carried, with nothing to say
       so. Read after the stream ends and disclosed if non-zero.
    2. `client.stream_truncated` (same new attribute set): set when the
       stream ended MID-FRAME, genuine truncation, distinct from a
       skipped-but-otherwise-intact frame above. This is the direct fix
       for F-4.2-A-16 (a truncated stream used to produce a partial
       answer, exit 1, and nothing on stderr): any partial answer already
       written to stdout is genuinely partial when this is set.
    3. An empty `done`: the stream DID end cleanly on a `done` event, but
       neither a `token` nor a `citation` event was ever seen along the
       way, so nothing was actually delivered even though the run did not
       fail (F-4.2-A-15's "state the emptiness" option, since this module
       does not own `render.py`'s exit-code policy to instead make that
       case exit nonzero). This function tracks the type of the last
       event it forwards to `renderer.handle` (`event.type`, the one
       field this module reads off an `Event` rather than treating it as
       fully opaque) purely to detect this third case.

    A non-zero skip count is not equivalent to a truncated stream, and
    neither is equivalent to a fatal `error` (already reported by
    `renderer.handle` when it arrived, via a distinct stderr line):
    collapsing any two of these into one sentence would be honest-looking
    and wrong.
    """
    pending_next: asyncio.Task[object] | None = None
    pending_interrupt: asyncio.Task[None] | None = None
    last_event_type: str | None = None
    saw_token = False
    saw_citation = False
    try:
        while True:
            if pending_next is None:
                pending_next = asyncio.ensure_future(stream_iter.__anext__())
            wait_for: set[asyncio.Future[object]] = {pending_next}
            if interrupt_signals is not None:
                if pending_interrupt is None:
                    pending_interrupt = asyncio.ensure_future(interrupt_signals.get())
                wait_for.add(pending_interrupt)

            done, _pending = await asyncio.wait(wait_for, return_when=asyncio.FIRST_COMPLETED)

            if pending_interrupt is not None and pending_interrupt in done:
                interrupted_pending_next = pending_next
                pending_next = None
                pending_interrupt = None
                return await _handle_interrupt_during_stream(
                    interrupted_pending_next,
                    client=client,
                    run_id=run_id,
                    interrupt_signals=interrupt_signals,
                    stderr=stderr,
                )

            if pending_next in done:
                task = pending_next
                pending_next = None
                try:
                    event = task.result()
                except StopAsyncIteration:
                    # Three independent disclosures (F-4.2-A-16/F-4.2-A-15/
                    # F-4.2-A-28, this function's own docstring): a
                    # skipped-frame count, genuine mid-frame truncation,
                    # and an empty `done`. None of the three implies any
                    # of the others, and more than one CAN be true at
                    # once (e.g. a skipped frame followed by a genuinely
                    # truncated connection), so each gets its own
                    # unconditional check and its own sentence rather
                    # than an elif chain that would silently drop one.
                    skipped_frames = getattr(client, "stream_skipped_frame_count", 0)
                    if skipped_frames:
                        frame_word = "frame" if skipped_frames == 1 else "frames"
                        stderr.write(
                            f"s3: {skipped_frames} {frame_word} in the event stream "
                            "could not be decoded and were skipped; the answer "
                            "above may be missing content from them.\n"
                        )
                    if getattr(client, "stream_truncated", False):
                        stderr.write(
                            "s3: the event stream stopped early, before a final "
                            "answer or error was received; the connection may "
                            "have been interrupted. Any answer text above may be "
                            "incomplete.\n"
                        )
                    if last_event_type == "done" and not saw_token and not saw_citation:
                        stderr.write(
                            "s3: the run finished with no answer text and no "
                            "citations; nothing was actually delivered even "
                            "though the run did not fail.\n"
                        )
                    return None
                except _client_typed_errors() as exc:
                    # Opening the stream (the first __anext__) is a REST
                    # call too, and can raise the same typed errors
                    # create_run and stop do (client.py, T-4.2-03); render
                    # it the same way. A 401 here is not retried: the
                    # token was valid moments ago for create_run, so a
                    # second refresh mid-stream is not worth the added
                    # complexity for a case this phase's gate does not
                    # exercise (tracker/phase_4.2.md's stated coverage).
                    _render_client_error(stderr, exc)
                    return 1
                except Exception as exc:  # noqa: BLE001 - any other stream-level failure
                    # ends the run cleanly with a message, rather than an
                    # unhandled traceback; genuine network flakiness
                    # mid-stream is explicitly out of this phase's gate
                    # coverage (tracker/phase_4.2.md), but a real CLI
                    # still needs to fail cleanly rather than crash.
                    # type(exc).__name__ only, never str(exc): this is
                    # the same no-raw-exception-text constraint as every
                    # other user-facing message in this module.
                    stderr.write(
                        f"s3: the event stream ended unexpectedly ({type(exc).__name__})\n"
                    )
                    return 1
                if event.type == "token":
                    saw_token = True
                elif event.type == "citation":
                    saw_citation = True
                last_event_type = event.type
                renderer.handle(event)
    finally:
        if pending_next is not None and not pending_next.done():
            pending_next.cancel()
        if pending_interrupt is not None and not pending_interrupt.done():
            pending_interrupt.cancel()


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


async def async_main(
    argv: Sequence[str],
    *,
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    http_client: httpx.AsyncClient,
    interrupt_signals: asyncio.Queue[None] | None = None,
    sigint_scope: contextlib.AbstractContextManager[None] | None = None,
) -> int:
    """The real entry point, driven directly by both the shared premise
    gate and `main()` below. `argv[0]` is the subcommand (`ask`, `stop`,
    or `login`); `http_client` is always supplied by the caller, since
    `tests/conftest.py` forbids a real outbound socket and the gate needs
    to pass an `ASGITransport`-backed client while still exercising this
    module's real code end to end. `interrupt_signals` is the Ctrl-C test
    seam: one `put_nowait(None)` per simulated `SIGINT`; `main()` wires
    the real `SIGINT` handler to feed the same queue, so the tested path
    and the production path are the same code.

    `sigint_scope`, new for F-4.2-A-04, is an additive optional parameter
    (no existing call site, including the premise gate, passes it, so
    this is a backward-compatible addition per `system-design-patterns`
    rule 10): a context manager `_run_ask` enters ONLY around the actual
    stream-consumption call, never for this function's whole body. See
    `main()`'s own docstring for why the real handler needs to be scoped
    that narrowly rather than installed once for the whole run.
    """
    if not argv:
        stderr.write("usage: s3 <ask|stop|login> ...\n")
        return 2

    command, rest = argv[0], argv[1:]

    try:
        if command == "ask":
            args = _parse_ask_args(rest, out=stdout, err=stderr)
            return await _run_ask(
                args,
                stdout=stdout,
                stderr=stderr,
                http_client=http_client,
                interrupt_signals=interrupt_signals,
                sigint_scope=sigint_scope,
            )
        if command == "stop":
            args = _parse_stop_args(rest, out=stdout, err=stderr)
            return await _run_stop(args, stdout=stdout, stderr=stderr, http_client=http_client)
        if command == "login":
            args = _parse_login_args(rest, out=stdout, err=stderr)
            return await _run_login(
                args, stdin=stdin, stdout=stdout, stderr=stderr, http_client=http_client
            )
    except _ArgparseExit as exc:
        return exc.code
    except _CommandError as exc:
        # A defensive catch: every current call site already handles its
        # own _CommandError locally, but a future call site that forgets
        # to still unwinds cleanly here instead of crashing.
        return exc.exit_code
    except (KeyboardInterrupt, asyncio.CancelledError):
        raise
    except Exception as exc:  # noqa: BLE001 - a CLI's last line of defense: never spill
        # a raw traceback to the user's terminal for a genuinely
        # unexpected internal failure; print something actionable and
        # exit nonzero instead. Every currently tested failure path is
        # handled well before this point, so this branch is not expected
        # to fire during normal operation.
        #
        # type(exc).__name__ only, never str(exc): a raw exception string
        # from a genuinely unanticipated failure is exactly the shape
        # J-4.2-02 named as the F-4.1-A-09 pattern this module otherwise
        # avoids everywhere else, and this catch-all is the one place a
        # str(exc) leak could still slip through unnoticed, since it is
        # by definition the path nothing else in this module was written
        # to handle.
        stderr.write(f"s3: unexpected error ({type(exc).__name__})\n")
        return 1

    stderr.write(f"s3: unknown command {command!r}; expected ask, stop, or login\n")
    return 2


def _resolve_base_url_for_main(argv: Sequence[str]) -> str:
    """Picks the base URL for the one `httpx.AsyncClient` that `main()`
    builds before calling `async_main`, which always receives an
    already-constructed client per this module's own test seam. `login`
    is the only command that can run with no stored credential yet, so it
    is the only one that reads `--base-url` or `S3_BASE_URL` here; every
    other command reads the base_url a prior `s3 login` already recorded
    in the credential file.
    """
    if argv and argv[0] == "login":
        for index, token in enumerate(argv):
            if token == "--base-url" and index + 1 < len(argv):
                return argv[index + 1]
            if token.startswith("--base-url="):
                return token.split("=", 1)[1]
        return os.environ.get("S3_BASE_URL", _DEFAULT_BASE_URL)

    from system_03_search_agent.adapters.cli import credentials as credentials_module

    try:
        return credentials_module.load().base_url
    except Exception:  # noqa: BLE001 - any load failure here just falls back to a
        # default transport; async_main's own credentials.load() call
        # raises the real, specific error and prints it. This pre-parse
        # only needs SOME base_url to construct the HTTP client with.
        return os.environ.get("S3_BASE_URL", _DEFAULT_BASE_URL)


def main(argv: Sequence[str] | None = None) -> int:
    """Production entry point: real `sys.argv[1:]` (or an explicit
    override), real stdio, a real `httpx.AsyncClient` built from the
    resolved base URL with a declared timeout, and a real `SIGINT`
    handler.

    F-4.2-A-04: that handler is now installed ONLY for the duration of
    `_run_ask`'s stream-consumption window, never for this function's
    whole body. Installing `loop.add_signal_handler(SIGINT, ...)`
    replaces Python's default `KeyboardInterrupt`-on-Ctrl-C behaviour
    with a callback that enqueues into `interrupt_signals`, and only
    `_consume_stream_with_interrupt` ever drains that queue. Installed
    for the whole process, as this used to be, every OTHER await (the
    create call, `s3 stop`, `s3 login`, a mid-refresh wait) had Ctrl-C
    silently absorbed into a queue nobody was watching, so the process
    kept waiting on that call's own network timeout, or forever, instead
    of responding to the interrupt at all: verified against a real
    socket and a real signal, Ctrl-C during create or during `s3 stop`
    needed `SIGKILL`. Scoping the handler to the stream window means
    every path OUTSIDE the stream falls back to Python's own default
    handling: Ctrl-C raises a genuine `KeyboardInterrupt` in whatever is
    currently awaiting, which propagates out of `asyncio.run(_run())`
    below and is caught there, so create, stop, login, and a mid-refresh
    wait are all interruptible the same way any ordinary Python process
    responds to Ctrl-C, while the stream itself keeps the gentler
    stop-then-exit handling `_consume_stream_with_interrupt` already
    implements (unchanged: a mid-stream interrupt still sends `stop` and
    exits 130, and a second interrupt during that stop still exits
    immediately without waiting for it).
    """
    real_argv = list(sys.argv[1:] if argv is None else argv)
    base_url = _resolve_base_url_for_main(real_argv)
    interrupt_signals: asyncio.Queue[None] = asyncio.Queue()

    async def _run() -> int:
        async with httpx.AsyncClient(base_url=base_url, timeout=_DEFAULT_TIMEOUT) as http_client:
            loop = asyncio.get_running_loop()

            @contextlib.contextmanager
            def _stream_sigint_scope():
                """Installs the real SIGINT handler ONLY while entered,
                i.e. only around `_consume_stream_with_interrupt`'s
                `await`. Removed again on exit, restoring Python's
                default `KeyboardInterrupt` behaviour for everything
                that runs after the stream (there is nothing today, but
                nothing here relies on that), and, symmetrically,
                nothing runs with the custom handler installed before
                `_run_ask` explicitly enters this scope.
                """
                try:
                    loop.add_signal_handler(signal.SIGINT, interrupt_signals.put_nowait, None)
                except (NotImplementedError, RuntimeError):
                    # Some event loops (notably Windows' ProactorEventLoop)
                    # do not support add_signal_handler at all. This
                    # module does not claim POSIX/non-POSIX parity for
                    # signal handling any more than tracker/phase_4.2.md's
                    # own stated exclusion of non-POSIX behavior
                    # elsewhere; the stream simply runs without the
                    # gentler stop-then-exit handling on such a platform,
                    # falling back to whatever that platform's own
                    # Ctrl-C handling does.
                    yield
                    return
                try:
                    yield
                finally:
                    with contextlib.suppress(NotImplementedError, RuntimeError):
                        loop.remove_signal_handler(signal.SIGINT)

            return await async_main(
                real_argv,
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr,
                http_client=http_client,
                interrupt_signals=interrupt_signals,
                sigint_scope=_stream_sigint_scope(),
            )

    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:
        # Every path outside the streaming window now relies on Python's
        # default SIGINT handling (see this function's own docstring
        # above), so a Ctrl-C there surfaces here as a genuine
        # KeyboardInterrupt instead of hanging with nothing draining an
        # enqueued signal. Reported the same conventional way an
        # interrupted stream already exits: a message on stderr and 130.
        sys.stderr.write("s3: interrupted\n")
        return EXIT_INTERRUPTED


if __name__ == "__main__":
    sys.exit(main())
