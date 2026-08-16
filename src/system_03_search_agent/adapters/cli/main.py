"""The CLI entry point: `s3 ask`, `s3 stop`, and `s3 login`.

Build phase 4.2, ticket T-4.2-05 (`tracker/phase_4.2.md`). A thin
orchestrator over three sibling modules this phase builds in parallel
(credentials.py, client.py, render.py): it parses argv, drives the run
lifecycle (create, attach immediately, stream, stop), and applies the two
policies Section 13.3 and the tracker's premise both name explicitly:
`POST /v1/query` is never retried, and an expired access token gets
exactly one transparent refresh followed by one retry of the failed call,
never a loop. No agent logic, no grounding logic, no cost logic lives
here; that all stays server-side, per this module's own scope statement
in `tracker/phase_4.2.md`.

Depends on:
    - system_03_search_agent.adapters.cli.credentials (T-4.2-02, imported
      lazily inside the functions that use it, not at module level)
    - system_03_search_agent.adapters.cli.client (T-4.2-03, imported
      lazily, same reason). `CliClient` raises typed errors for a
      non-2xx response, not a bare httpx.HTTPStatusError: AuthExpiredError
      (401), ForbiddenError (403), NotFoundError (404), ConflictError
      (409), RateLimitedError (429). AuthExpiredError is the only one this
      module treats specially (one transparent refresh, one retry); the
      other four, and a second AuthExpiredError after the retry, are
      rendered and unwound the same way.
    - system_03_search_agent.adapters.cli.render (T-4.2-04, imported
      lazily, same reason). `render_client_error(err, exc)` is the seam
      for rendering any of the five typed client errors above: it owns
      the mixed-body problem (a structured 429 detail dict versus a
      bare-string 401/403/404/409 detail), so this module never parses a
      response body itself for a CliClient-raised failure.
    - system_03_search_agent.contracts.events.Event (type-checking only;
      this module never constructs or inspects an Event, it only passes
      whatever `client.stream_events` yields straight to `renderer.handle`)
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
_DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)


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
    """Reads exactly one line from stdin and strips only the trailing
    newline. Never argv: a password passed as a command-line argument is
    visible to every process on the machine via `ps`, which is the whole
    reason `s3 login` takes it from stdin instead.
    """
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
    """Lazily imports and returns the five typed errors `CliClient`
    raises for a non-2xx response (client.py, T-4.2-03), so a call site
    can `except _client_typed_errors() as exc:` without repeating the
    same import block. Order is not meaningful; `except` accepts any
    tuple of exception types.
    """
    from system_03_search_agent.adapters.cli.client import (
        AuthExpiredError,
        ConflictError,
        ForbiddenError,
        NotFoundError,
        RateLimitedError,
    )

    return (AuthExpiredError, ForbiddenError, NotFoundError, ConflictError, RateLimitedError)


def _render_client_error(stderr: TextIO, exc: Exception) -> None:
    """Thin, lazily-imported wrapper around `render.render_client_error`
    (T-4.2-04): the single seam for rendering any of the five typed
    client errors above without this module parsing a response body
    itself.
    """
    from system_03_search_agent.adapters.cli.render import render_client_error

    render_client_error(stderr, exc)


async def _call_with_one_refresh(
    coro_factory: Callable[[Credentials], Awaitable[T]],
    *,
    http_client: httpx.AsyncClient,
    creds: Credentials,
    stderr: TextIO,
) -> tuple[T, Credentials]:
    """Calls `coro_factory(creds)` once. `coro_factory` must be a
    `CliClient` method call, since this function catches the five typed
    errors `CliClient` raises for a non-2xx response (client.py, T-4.2-03):
    `AuthExpiredError` (401), `ForbiddenError` (403), `NotFoundError`
    (404), `ConflictError` (409), `RateLimitedError` (429).

    On `AuthExpiredError`, refreshes exactly once via
    `credentials.refresh_locked` (which itself persists the rotated
    refresh token to disk, under an exclusive lock, before returning) and
    reissues the SAME call exactly once with the refreshed credentials.
    Any other typed error, or a second `AuthExpiredError` after the
    retry, is rendered via `render.render_client_error` and unwound via
    `_CommandError`. Never a loop, and never applied to a transport-level
    failure (a timeout or a connection error): those propagate to the
    caller untouched, since a 401 is rejected before any handler body
    runs and is always safe to reissue, while a network timeout carries
    no such guarantee (the server may already have processed the
    original request).

    Returns the call's result alongside whatever credentials actually
    ended up being used, so the caller's local `creds` stays current for
    any later call in the same command.
    """
    from system_03_search_agent.adapters.cli.client import AuthExpiredError

    from system_03_search_agent.adapters.cli import credentials as credentials_module

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
    # httpx.AsyncClient, never through CliClient, so its failure is not
    # one of the five typed errors above; it is credentials.py's own
    # HTTP call, rendered with this module's own _extract_error_message
    # rather than render_client_error, whose stated scope is client.py's
    # typed errors specifically.
    try:
        creds = await credentials_module.refresh_locked(http_client, creds)
    except httpx.HTTPStatusError as refresh_exc:
        stderr.write(
            "s3: session expired and could not be refreshed "
            f"({_extract_error_message(refresh_exc.response)}); run 's3 login' again\n"
        )
        raise _CommandError(1) from refresh_exc

    try:
        result = await coro_factory(creds)
    except typed_errors as exc2:
        _render_client_error(stderr, exc2)
        raise _CommandError(1) from exc2
    return result, creds


def _load_credentials_or_report(stderr: TextIO) -> Credentials | None:
    """Loads the stored credentials, or writes an actionable message and
    returns None. Never widens or repairs an insecure credential file;
    `credentials.load()` itself refuses to read one wider than mode 600,
    and this function only reports that refusal, it does not work around
    it.
    """
    from system_03_search_agent.adapters.cli import credentials as credentials_module

    try:
        return credentials_module.load()
    except FileNotFoundError:
        stderr.write("s3: not logged in; run 's3 login' first\n")
        return None
    except credentials_module.InsecureCredentialsError as exc:
        stderr.write(f"s3: {exc}\n")
        return None
    except OSError as exc:
        stderr.write(f"s3: could not read the stored credentials ({exc})\n")
        return None


# ---------------------------------------------------------------------------
# Argument parsing, one small parser per subcommand rather than argparse
# subparsers, so each carries its own injected out/err streams cleanly.
# ---------------------------------------------------------------------------


def _parse_ask_args(argv: Sequence[str], *, out: TextIO, err: TextIO) -> argparse.Namespace:
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
    parser.add_argument(
        "--operator",
        action="store_true",
        help=(
            "show cost fields if the stored credential itself carries operator scope; "
            "silently ignored server-side otherwise, and never sent to the server as a "
            "request field, since operator visibility is derived from the credential, "
            "not requested by the client"
        ),
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
    argv, never echoed, and never appears in any message this function
    writes, on success or failure. A failed login never calls
    `credentials.store`, so any pre-existing credential file is left
    byte-unchanged rather than truncated.
    """
    from system_03_search_agent.adapters.cli import credentials as credentials_module

    password = _read_password(stdin)
    if not password:
        stderr.write("s3 login: no password was provided on stdin\n")
        return 1

    try:
        response = await http_client.post(
            "/auth/login", json={"email": args.email, "password": password}
        )
    except httpx.HTTPError as exc:
        stderr.write(f"s3 login: could not reach the server ({type(exc).__name__})\n")
        return 1

    if response.status_code != 200:
        stderr.write(f"s3 login: {_extract_error_message(response)}\n")
        return 1

    body = response.json()
    creds = credentials_module.Credentials(
        base_url=str(http_client.base_url),
        access_token=body["access_token"],
        refresh_token=body["refresh_token"],
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
) -> int:
    """`POST /v1/query`, then attaches to the event stream immediately,
    then renders every event as it arrives. `POST /v1/query` itself is
    never retried by this function on any failure shape, including a
    transport timeout; only a 401 gets a single transparent refresh and
    reissue via `_call_with_one_refresh`, which is a distinct mechanism
    from a blind retry (a 401 is rejected before the handler body runs,
    so reissuing is always safe; a timeout is not, since the server may
    already have processed the original request and spent the caller's
    allowance).
    """
    from system_03_search_agent.adapters.cli.client import CliClient
    from system_03_search_agent.adapters.cli.render import Renderer

    creds = _load_credentials_or_report(stderr)
    if creds is None:
        return 1

    session_id = args.session_id or uuid.uuid4().hex

    try:
        (run_id, _persona_name), creds = await _call_with_one_refresh(
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
    renderer = Renderer(stdout, stderr, operator=args.operator)
    client = CliClient(http_client, creds)
    stream_iter = client.stream_events(run_id).__aiter__()

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
    """
    pending_next: asyncio.Task[object] | None = None
    pending_interrupt: asyncio.Task[None] | None = None
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
                    return None
                except _client_typed_errors() as exc:
                    # Opening the stream (the first __anext__) is a REST
                    # call too, and can raise the same five typed errors
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
                    stderr.write(
                        f"s3: the event stream ended unexpectedly ({type(exc).__name__}); "
                        f"{exc}\n"
                    )
                    return 1
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
        stderr.write(f"s3: unexpected error ({type(exc).__name__}): {exc}\n")
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
    handler that feeds the same `asyncio.Queue` `async_main`'s own test
    seam consumes, so the tested Ctrl-C path and the real one are the
    same code.
    """
    real_argv = list(sys.argv[1:] if argv is None else argv)
    base_url = _resolve_base_url_for_main(real_argv)
    interrupt_signals: asyncio.Queue[None] = asyncio.Queue()

    async def _run() -> int:
        async with httpx.AsyncClient(base_url=base_url, timeout=_DEFAULT_TIMEOUT) as http_client:
            loop = asyncio.get_running_loop()
            handler_installed = True
            try:
                loop.add_signal_handler(signal.SIGINT, interrupt_signals.put_nowait, None)
            except (NotImplementedError, RuntimeError):
                # Some event loops (notably Windows' ProactorEventLoop) do
                # not support add_signal_handler at all. This module does
                # not claim POSIX/non-POSIX parity for signal handling
                # any more than tracker/phase_4.2.md's own stated
                # exclusion of non-POSIX behavior elsewhere.
                handler_installed = False
            try:
                return await async_main(
                    real_argv,
                    stdin=sys.stdin,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                    http_client=http_client,
                    interrupt_signals=interrupt_signals,
                )
            finally:
                if handler_installed:
                    with contextlib.suppress(NotImplementedError, RuntimeError):
                        loop.remove_signal_handler(signal.SIGINT)

    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
