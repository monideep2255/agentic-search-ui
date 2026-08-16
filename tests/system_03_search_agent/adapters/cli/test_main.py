"""Unit tests for the CLI entry point, `main.py` (T-4.2-05).

The three sibling modules `main.py` depends on (credentials.py, client.py,
render.py; T-4.2-02/03/04) are being built in parallel by other builders
for this same phase and do not exist in this worktree yet. `main.py`
defers importing each of them into the function bodies that actually use
them (see its own module docstring), so this file installs minimal, fully
controllable fake stand-ins into `sys.modules` before invoking those
functions. That lets this file exercise `main.py`'s own orchestration
logic (argument parsing, the refresh-on-401-once policy, the login
stdin/password handling, the immediate-attach ordering, and the two Ctrl-C
races) in isolation, entirely independent of whether the real sibling
modules exist yet.

This file does NOT re-prove the real, end-to-end integration: that is
`tests/system_03_search_agent/adapters/cli/test_phase_4_2_premise.py`'s
job, driven against the real FastAPI app once all four modules exist
together (the lead's merge step, per this ticket's own brief). Every fake
class below matches the fixed interfaces and the two corrections relayed
during this ticket's build (`credentials.refresh_locked` is `async`;
`CliClient` raises five typed errors -- `AuthExpiredError`,
`ForbiddenError`, `NotFoundError`, `ConflictError`, `RateLimitedError` --
rendered through `render.render_client_error`, not a bare
`httpx.HTTPStatusError`), so a signature drift here is a signal this
file's own fakes need updating, not that `main.py` is wrong.
"""

from __future__ import annotations

import asyncio
import io
import sys
import types
from typing import NamedTuple

import httpx
import pytest


class FakeCredentials(NamedTuple):
    base_url: str
    access_token: str | None
    refresh_token: str


# credentials.py's exception hierarchy, reproduced here as stand-ins.
# Per the lead's phase-4.2 correction, credentials.py grew from two
# exception types (RefreshError, InsecureCredentialsError) to six, all
# under one `CredentialsError` base, mid-phase: `CorruptCredentialsError`
# (an unreadable or malformed credential file), `RefreshLockTimeoutError`
# and `RefreshLockUnavailableError` (the bounded-lock-wait fix), and
# `SessionLostError(RefreshError)` (a rotation that could not be
# persisted, meaning the caller's session is dead on every surface, not
# just this command). main.py now catches the BASE everywhere
# `credentials.load()` or `credentials.refresh_locked()` can fail, never
# an enumerated list (`_render_credentials_error`'s own docstring), so
# this fake module mirrors the real hierarchy rather than flattening it:
# a fake missing from this tree is exactly the ImportError/AttributeError
# class of failure the real fix exists to make impossible to reintroduce.
class FakeCredentialsError(Exception):
    remedy: str | None = None


class FakeInsecureCredentialsError(FakeCredentialsError):
    pass


class FakeRefreshError(FakeCredentialsError):
    """Stand-in for credentials.py's `RefreshError` (J-4.2-02/F-4.2-A-06):
    `_call_with_one_refresh` and `_create_run_never_retried` both catch
    the `CredentialsError` base now, off the fake `credentials` module,
    in place of the `httpx.HTTPStatusError` `refresh_locked` never
    actually raises.
    """


class FakeSessionLostError(FakeRefreshError):
    """Stand-in for credentials.py's `SessionLostError(RefreshError)`:
    `_render_credentials_error` renders this one with distinct wording
    (logged out on every surface) BEFORE falling back to the generic
    `CredentialsError` rendering the other five types share.
    """


class FakeCorruptCredentialsError(FakeCredentialsError):
    """Stand-in for credentials.py's `CorruptCredentialsError`: an
    unreadable or malformed credential file. `load()` used to leak a bare
    `json.JSONDecodeError`/`KeyError`/`TypeError` here (F-4.2-A-13); this
    typed replacement is what `_load_credentials_or_report` now catches
    via the `CredentialsError` base.
    """


class FakeRefreshLockTimeoutError(FakeCredentialsError):
    """Stand-in for credentials.py's `RefreshLockTimeoutError`: the
    bounded-wait fix for F-4.2-A-11 (an unbounded wait on the refresh
    lock)."""


class FakeRefreshLockUnavailableError(FakeCredentialsError):
    """Stand-in for credentials.py's `RefreshLockUnavailableError`: the
    lock file itself could not be opened (e.g. a mode-000 parent
    directory)."""


# The typed-error hierarchy client.py (T-4.2-03) raises for a non-2xx
# response, reproduced here as simple stand-ins so this file's fakes can
# raise the same names main.py imports by name. `FakeCliApiError` mirrors
# the real `CliApiError` base (F-4.2-A-05): `_client_typed_errors()` now
# imports and returns it alongside the five named subclasses, so this
# fake client module must define it too, or that import raises
# ImportError before any test body using it even runs.
class FakeCliApiError(Exception):
    pass


class FakeAuthExpiredError(FakeCliApiError):
    def __init__(self, response: httpx.Response) -> None:
        super().__init__("auth expired")
        self.response = response


class FakeForbiddenError(FakeCliApiError):
    def __init__(self, response: httpx.Response) -> None:
        super().__init__("forbidden")
        self.response = response


class FakeNotFoundError(FakeCliApiError):
    def __init__(self, response: httpx.Response) -> None:
        super().__init__("not found")
        self.response = response


class FakeConflictError(FakeCliApiError):
    def __init__(self, response: httpx.Response) -> None:
        super().__init__("conflict")
        self.response = response


class FakeRateLimitedError(FakeCliApiError):
    def __init__(self, response: httpx.Response) -> None:
        super().__init__("rate limited")
        self.response = response


class _FakeEvent:
    """A minimal stand-in for contracts.events.Event: main.py never
    inspects an event's payload itself, it only passes whatever
    `client.stream_events` yields straight to `renderer.handle`, so a
    plain marker object is enough to prove ordering and count.

    The one exception, added for F-4.2-A-16/F-4.2-A-15's regression
    coverage: `_consume_stream_with_interrupt` reads the bare
    `event.type` string (never the payload) to detect a truncated stream
    and an empty `done`. `type` is aliased to `marker` here, rather than
    a second constructor argument, since every call site in this file
    already spells its marker as a real event-type string ("guard",
    "token", "done"), so the alias needs no call site to change.
    """

    def __init__(self, marker: str) -> None:
        self.marker = marker
        self.type = marker

    def __repr__(self) -> str:
        return f"_FakeEvent({self.marker!r})"


@pytest.fixture
def fake_modules(monkeypatch: pytest.MonkeyPatch):
    """Installs empty, minimal fake modules for credentials.py, client.py
    and render.py into `sys.modules`, so `main.py`'s lazy imports resolve
    to these instead of raising `ModuleNotFoundError`. Each test then
    configures the specific attributes it needs directly on the returned
    module objects.

    `main.py` resolves `credentials` through `from
    system_03_search_agent.adapters.cli import credentials as
    credentials_module` (a function-body import; see `_call_with_one_refresh`,
    `_load_credentials_or_report`, and two more call sites). CPython's
    fromlist import resolves that statement as `getattr(cli_package,
    "credentials")` FIRST and only falls back to `sys.modules` when the
    parent package has no such attribute yet (`importlib._bootstrap.
    _handle_fromlist`). Once any code in the same process performs a REAL
    import of `system_03_search_agent.adapters.cli.credentials` (this
    happens whenever `test_phase_4_2_premise.py` or `test_credentials.py`
    runs first in the same session and drives the real module), the `cli`
    package object keeps a `credentials` attribute pointing at the real
    module. `monkeypatch.setitem` on `sys.modules` alone never touches that
    attribute, so `main.py`'s fromlist import silently keeps resolving the
    real module instead of the fake one installed below, regardless of
    what this fixture put in `sys.modules`. `client.py` and `render.py` are
    not affected today because every call site imports them with `from
    system_03_search_agent.adapters.cli.client import ...` (a direct
    dotted-submodule import, which checks `sys.modules` by full dotted
    name at every level, including the leaf); patch their parent-package
    attributes too so this fixture stays correct if a call site ever
    switches to the same `from package import submodule` form credentials
    uses.
    """
    import system_03_search_agent.adapters.cli as cli_package

    credentials_module = types.ModuleType("system_03_search_agent.adapters.cli.credentials")
    credentials_module.Credentials = FakeCredentials
    credentials_module.CredentialsError = FakeCredentialsError
    credentials_module.InsecureCredentialsError = FakeInsecureCredentialsError
    credentials_module.RefreshError = FakeRefreshError
    credentials_module.SessionLostError = FakeSessionLostError
    credentials_module.CorruptCredentialsError = FakeCorruptCredentialsError
    credentials_module.RefreshLockTimeoutError = FakeRefreshLockTimeoutError
    credentials_module.RefreshLockUnavailableError = FakeRefreshLockUnavailableError
    credentials_module.CREDENTIALS_PATH = None

    client_module = types.ModuleType("system_03_search_agent.adapters.cli.client")
    client_module.CliApiError = FakeCliApiError
    client_module.AuthExpiredError = FakeAuthExpiredError
    client_module.ForbiddenError = FakeForbiddenError
    client_module.NotFoundError = FakeNotFoundError
    client_module.ConflictError = FakeConflictError
    client_module.RateLimitedError = FakeRateLimitedError

    render_module = types.ModuleType("system_03_search_agent.adapters.cli.render")

    monkeypatch.setitem(
        sys.modules, "system_03_search_agent.adapters.cli.credentials", credentials_module
    )
    monkeypatch.setitem(sys.modules, "system_03_search_agent.adapters.cli.client", client_module)
    monkeypatch.setitem(sys.modules, "system_03_search_agent.adapters.cli.render", render_module)

    monkeypatch.setattr(cli_package, "credentials", credentials_module, raising=False)
    monkeypatch.setattr(cli_package, "client", client_module, raising=False)
    monkeypatch.setattr(cli_package, "render", render_module, raising=False)

    return types.SimpleNamespace(
        credentials=credentials_module, client=client_module, render=render_module
    )


@pytest.fixture
def main_module(fake_modules):
    """Imports main.py fresh for each test, after the fake sibling
    modules are already installed, and clears it afterward so no test
    leaks module-level state into the next (main.py itself has none
    today, but this keeps that invariant true by construction).
    """
    sys.modules.pop("system_03_search_agent.adapters.cli.main", None)
    import system_03_search_agent.adapters.cli.main as module

    yield module
    sys.modules.pop("system_03_search_agent.adapters.cli.main", None)


def _response(status_code: int, json_body: object) -> httpx.Response:
    return httpx.Response(status_code, json=json_body, request=httpx.Request("GET", "http://test"))


# ---------------------------------------------------------------------------
# _extract_error_message: pure function, no stubbing needed
# ---------------------------------------------------------------------------


class TestExtractErrorMessage:
    def test_structured_dict_detail_returns_the_message(self, main_module) -> None:
        response = _response(
            429, {"detail": {"reason": "concurrent_run_cap_exceeded", "message": "wait a bit"}}
        )
        assert main_module._extract_error_message(response) == "wait a bit"

    def test_structured_dict_detail_falls_back_to_reason_with_no_message(self, main_module) -> None:
        response = _response(429, {"detail": {"reason": "concurrent_run_cap_exceeded"}})
        assert main_module._extract_error_message(response) == "concurrent_run_cap_exceeded"

    def test_bare_string_detail_returns_the_string(self, main_module) -> None:
        response = _response(401, {"detail": "invalid or expired refresh token"})
        assert main_module._extract_error_message(response) == "invalid or expired refresh token"

    def test_unparsable_body_falls_back_to_status_code(self, main_module) -> None:
        response = httpx.Response(
            500, content=b"not json", request=httpx.Request("GET", "http://test")
        )
        assert main_module._extract_error_message(response) == "request failed with status 500"


# ---------------------------------------------------------------------------
# Argument parsing and top-level dispatch
# ---------------------------------------------------------------------------


class TestArgumentParsingAndDispatch:
    @pytest.mark.asyncio
    async def test_empty_argv_returns_2_and_writes_usage(self, main_module) -> None:
        out, err = io.StringIO(), io.StringIO()
        exit_code = await main_module.async_main(
            [], stdin=io.StringIO(""), stdout=out, stderr=err, http_client=object()
        )
        assert exit_code == 2
        assert "usage" in err.getvalue().lower()

    @pytest.mark.asyncio
    async def test_unknown_command_returns_2_and_names_the_valid_ones(self, main_module) -> None:
        out, err = io.StringIO(), io.StringIO()
        exit_code = await main_module.async_main(
            ["frobnicate"], stdin=io.StringIO(""), stdout=out, stderr=err, http_client=object()
        )
        assert exit_code == 2
        assert "ask" in err.getvalue()
        assert "stop" in err.getvalue()
        assert "login" in err.getvalue()

    @pytest.mark.asyncio
    async def test_ask_with_no_question_is_a_parse_error_exit_2(self, main_module) -> None:
        out, err = io.StringIO(), io.StringIO()
        exit_code = await main_module.async_main(
            ["ask"], stdin=io.StringIO(""), stdout=out, stderr=err, http_client=object()
        )
        assert exit_code == 2
        assert err.getvalue() != ""

    @pytest.mark.asyncio
    async def test_ask_rejects_an_invalid_depth_choice(self, main_module) -> None:
        out, err = io.StringIO(), io.StringIO()
        exit_code = await main_module.async_main(
            ["ask", "hi", "--depth", "not-a-real-depth"],
            stdin=io.StringIO(""),
            stdout=out,
            stderr=err,
            http_client=object(),
        )
        assert exit_code == 2


# ---------------------------------------------------------------------------
# s3 login
# ---------------------------------------------------------------------------


class TestLogin:
    @pytest.mark.asyncio
    async def test_successful_login_stores_both_tokens_at_the_clients_base_url(
        self, main_module, fake_modules
    ) -> None:
        store_calls: list[FakeCredentials] = []
        fake_modules.credentials.store = store_calls.append

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/auth/login"
            body = request.read()
            assert b"hunter2" in body  # the request body itself, never a log or error
            return httpx.Response(200, json={"access_token": "a1", "refresh_token": "r1"})

        http_client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://example.test"
        )
        out, err = io.StringIO(), io.StringIO()
        try:
            exit_code = await main_module.async_main(
                ["login", "person@example.com"],
                stdin=io.StringIO("hunter2\n"),
                stdout=out,
                stderr=err,
                http_client=http_client,
            )
        finally:
            await http_client.aclose()

        assert exit_code == 0
        assert err.getvalue() == ""
        assert len(store_calls) == 1
        assert store_calls[0].base_url == "http://example.test"
        assert store_calls[0].access_token == "a1"
        assert store_calls[0].refresh_token == "r1"
        # Mutation: interpolate the password into the success message.
        assert "hunter2" not in out.getvalue()

    @pytest.mark.asyncio
    async def test_password_never_appears_in_argv(self, main_module, fake_modules) -> None:
        """The whole reason `s3 login` takes a positional email and reads
        the password from stdin: argv is visible to every process on the
        machine via `ps`. This asserts the parsed namespace never even
        has a slot for a password positional/flag to land in.
        """
        args = main_module._parse_login_args(
            ["person@example.com"], out=io.StringIO(), err=io.StringIO()
        )
        assert not hasattr(args, "password")

    @pytest.mark.asyncio
    async def test_failed_login_does_not_store_and_never_leaks_the_password(
        self, main_module, fake_modules
    ) -> None:
        store_calls: list[FakeCredentials] = []
        fake_modules.credentials.store = store_calls.append

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"detail": "invalid email or password"})

        http_client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://example.test"
        )
        out, err = io.StringIO(), io.StringIO()
        try:
            exit_code = await main_module.async_main(
                ["login", "person@example.com"],
                stdin=io.StringIO("wrong-password\n"),
                stdout=out,
                stderr=err,
                http_client=http_client,
            )
        finally:
            await http_client.aclose()

        assert exit_code != 0
        assert store_calls == []
        assert "wrong-password" not in out.getvalue()
        assert "wrong-password" not in err.getvalue()
        assert "invalid email or password" in err.getvalue()

    @pytest.mark.asyncio
    async def test_empty_stdin_is_refused_before_any_request(
        self, main_module, fake_modules
    ) -> None:
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return httpx.Response(200, json={"access_token": "a", "refresh_token": "r"})

        http_client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://example.test"
        )
        out, err = io.StringIO(), io.StringIO()
        try:
            exit_code = await main_module.async_main(
                ["login", "person@example.com"],
                stdin=io.StringIO(""),
                stdout=out,
                stderr=err,
                http_client=http_client,
            )
        finally:
            await http_client.aclose()

        assert exit_code != 0
        assert calls == []


# ---------------------------------------------------------------------------
# _call_with_one_refresh: the refresh-on-401-once policy
# ---------------------------------------------------------------------------


class TestCallWithOneRefresh:
    @pytest.mark.asyncio
    async def test_success_on_first_try_never_touches_refresh(
        self, main_module, fake_modules
    ) -> None:
        refresh_calls: list[FakeCredentials] = []

        async def refresh_locked(client: object, creds: FakeCredentials) -> FakeCredentials:
            refresh_calls.append(creds)
            raise AssertionError("refresh_locked should not be called on a clean success")

        fake_modules.credentials.refresh_locked = refresh_locked
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")

        async def coro_factory(c: FakeCredentials) -> str:
            assert c is creds
            return "ok"

        result, out_creds = await main_module._call_with_one_refresh(
            coro_factory, http_client=object(), creds=creds, stderr=io.StringIO()
        )
        assert result == "ok"
        assert out_creds is creds
        assert refresh_calls == []

    @pytest.mark.asyncio
    async def test_401_then_success_uses_the_refreshed_credentials(
        self, main_module, fake_modules
    ) -> None:
        stale = FakeCredentials(base_url="http://test", access_token="stale", refresh_token="r0")
        fresh = FakeCredentials(base_url="http://test", access_token="fresh", refresh_token="r1")
        refresh_calls: list[FakeCredentials] = []

        async def refresh_locked(client: object, creds: FakeCredentials) -> FakeCredentials:
            refresh_calls.append(creds)
            return fresh

        fake_modules.credentials.refresh_locked = refresh_locked

        attempts: list[FakeCredentials] = []

        async def coro_factory(c: FakeCredentials) -> str:
            attempts.append(c)
            if c is stale:
                raise FakeAuthExpiredError(_response(401, {"detail": "expired"}))
            return "ok-with-fresh-token"

        stderr = io.StringIO()
        result, out_creds = await main_module._call_with_one_refresh(
            coro_factory, http_client=object(), creds=stale, stderr=stderr
        )
        assert result == "ok-with-fresh-token"
        assert out_creds is fresh
        assert attempts == [stale, fresh]
        assert refresh_calls == [stale]
        # Mutation: retry a second time on a second 401 instead of
        # unwinding -- would show a third attempt here.
        assert len(attempts) == 2
        assert stderr.getvalue() == ""

    @pytest.mark.asyncio
    async def test_a_second_401_after_the_retry_renders_and_does_not_loop(
        self, main_module, fake_modules
    ) -> None:
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")
        refreshed = FakeCredentials(base_url="http://test", access_token="a2", refresh_token="r2")
        refresh_call_count = 0

        async def refresh_locked(client: object, c: FakeCredentials) -> FakeCredentials:
            nonlocal refresh_call_count
            refresh_call_count += 1
            return refreshed

        fake_modules.credentials.refresh_locked = refresh_locked

        rendered: list[Exception] = []
        fake_modules.render.render_client_error = lambda err, exc: rendered.append(exc)

        call_count = 0

        async def coro_factory(c: FakeCredentials) -> str:
            nonlocal call_count
            call_count += 1
            raise FakeAuthExpiredError(_response(401, {"detail": "still expired"}))

        with pytest.raises(main_module._CommandError) as excinfo:
            await main_module._call_with_one_refresh(
                coro_factory, http_client=object(), creds=creds, stderr=io.StringIO()
            )
        assert excinfo.value.exit_code == 1
        # Mutation: refresh and retry a second time instead of unwinding
        # -- call_count/refresh_call_count would both read 3 or more.
        assert call_count == 2
        assert refresh_call_count == 1
        assert len(rendered) == 1
        assert isinstance(rendered[0], FakeAuthExpiredError)

    @pytest.mark.asyncio
    async def test_a_non_auth_error_renders_immediately_without_refreshing(
        self, main_module, fake_modules
    ) -> None:
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")
        refresh_calls: list[object] = []

        async def refresh_locked(client: object, c: object) -> object:
            refresh_calls.append(c)
            raise AssertionError("a 403 must never trigger a refresh")

        fake_modules.credentials.refresh_locked = refresh_locked

        rendered: list[Exception] = []
        fake_modules.render.render_client_error = lambda err, exc: rendered.append(exc)

        call_count = 0

        async def coro_factory(c: FakeCredentials) -> str:
            nonlocal call_count
            call_count += 1
            raise FakeForbiddenError(_response(403, {"detail": "not your run"}))

        with pytest.raises(main_module._CommandError) as excinfo:
            await main_module._call_with_one_refresh(
                coro_factory, http_client=object(), creds=creds, stderr=io.StringIO()
            )
        assert excinfo.value.exit_code == 1
        assert call_count == 1
        assert refresh_calls == []
        assert len(rendered) == 1
        assert isinstance(rendered[0], FakeForbiddenError)

    @pytest.mark.asyncio
    async def test_a_transport_error_is_not_caught_here_at_all(
        self, main_module, fake_modules
    ) -> None:
        """`_call_with_one_refresh` only ever catches the five typed
        client errors. A raw transport failure (a timeout, a connection
        error) must propagate straight through untouched, since the
        caller (`_run_ask`/`_run_stop`) is what decides never to retry
        `create_run` on this class of failure.
        """
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")

        async def coro_factory(c: FakeCredentials) -> str:
            raise httpx.ReadTimeout("simulated timeout", request=httpx.Request("GET", "http://t"))

        with pytest.raises(httpx.ReadTimeout):
            await main_module._call_with_one_refresh(
                coro_factory, http_client=object(), creds=creds, stderr=io.StringIO()
            )

    @pytest.mark.asyncio
    async def test_a_refresh_error_from_refresh_locked_is_reported_not_unexpected(
        self, main_module, fake_modules
    ) -> None:
        """J-4.2-02/F-4.2-A-06: `refresh_locked` never raises
        `httpx.HTTPStatusError`; it raises credentials.py's own typed
        `RefreshError`. Before the fix, this fell through to
        `async_main`'s generic catch-all and was reported as "unexpected
        error (RefreshError)" instead of the curated message below, with
        the intended remedy text dead code.
        """
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")

        async def refresh_locked(client: object, c: FakeCredentials) -> FakeCredentials:
            raise FakeRefreshError(
                "POST /auth/refresh returned 401; the stored refresh token is "
                "expired, already used, or revoked. Run: s3 login"
            )

        fake_modules.credentials.refresh_locked = refresh_locked

        async def coro_factory(c: FakeCredentials) -> str:
            raise FakeAuthExpiredError(_response(401, {"detail": "expired"}))

        stderr = io.StringIO()
        with pytest.raises(main_module._CommandError) as excinfo:
            await main_module._call_with_one_refresh(
                coro_factory, http_client=object(), creds=creds, stderr=stderr
            )
        assert excinfo.value.exit_code == 1
        # The curated RefreshError message reaches the user, not a bare
        # "unexpected error (RefreshError)" from the generic catch-all.
        assert "unexpected error" not in stderr.getvalue()
        assert "s3 login" in stderr.getvalue()

    @pytest.mark.asyncio
    async def test_a_session_lost_error_gets_distinct_logged_out_everywhere_wording(
        self, main_module, fake_modules
    ) -> None:
        """`SessionLostError(RefreshError)` means the server rotated the
        token and this process could not persist the rotation, so the
        user's session is dead on EVERY surface, not just this command.
        It must not render as a generic credential problem.
        """
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")

        async def refresh_locked(client: object, c: FakeCredentials) -> FakeCredentials:
            raise FakeSessionLostError("the rotated token could not be saved")

        fake_modules.credentials.refresh_locked = refresh_locked

        async def coro_factory(c: FakeCredentials) -> str:
            raise FakeAuthExpiredError(_response(401, {"detail": "expired"}))

        stderr = io.StringIO()
        with pytest.raises(main_module._CommandError):
            await main_module._call_with_one_refresh(
                coro_factory, http_client=object(), creds=creds, stderr=stderr
            )
        message = stderr.getvalue()
        assert "every surface" in message
        assert "s3 login" in message

    @pytest.mark.asyncio
    async def test_a_corrupt_credentials_error_from_refresh_locked_is_also_caught(
        self, main_module, fake_modules
    ) -> None:
        """F-4.2-A-05/J-4.2-02, the fourth instance found at the merge
        boundary: credentials.py grew from two exception types to six
        mid-phase. Catching the `CredentialsError` BASE, not a list of
        the two original names, is what makes a type this module never
        explicitly names (here, `CorruptCredentialsError`, raised by the
        re-read `load()` call `refresh_locked` makes under its lock)
        still get a curated message instead of falling through to the
        generic catch-all.
        """
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")

        async def refresh_locked(client: object, c: FakeCredentials) -> FakeCredentials:
            raise FakeCorruptCredentialsError("the credential file is malformed")

        fake_modules.credentials.refresh_locked = refresh_locked

        async def coro_factory(c: FakeCredentials) -> str:
            raise FakeAuthExpiredError(_response(401, {"detail": "expired"}))

        stderr = io.StringIO()
        with pytest.raises(main_module._CommandError):
            await main_module._call_with_one_refresh(
                coro_factory, http_client=object(), creds=creds, stderr=stderr
            )
        assert "unexpected error" not in stderr.getvalue()
        assert "malformed" in stderr.getvalue()

    @pytest.mark.asyncio
    async def test_a_bare_cli_api_error_not_one_of_the_five_named_subclasses_is_rendered(
        self, main_module, fake_modules
    ) -> None:
        """F-4.2-A-05: `client.py`'s `_raise_for_status` raises the bare
        `CliApiError` base directly for a status code outside its five-
        entry map (400, 500, 502, 503...). Before the fix,
        `_client_typed_errors()` returned only the five named subclasses,
        so an instance of the bare base matched none of them and fell
        through to whatever generic handling sat downstream instead of
        `render.render_client_error`.
        """
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")
        rendered: list[Exception] = []
        fake_modules.render.render_client_error = lambda err, exc: rendered.append(exc)

        async def coro_factory(c: FakeCredentials) -> str:
            raise FakeCliApiError("the server returned 500")

        with pytest.raises(main_module._CommandError) as excinfo:
            await main_module._call_with_one_refresh(
                coro_factory, http_client=object(), creds=creds, stderr=io.StringIO()
            )
        assert excinfo.value.exit_code == 1
        assert len(rendered) == 1
        assert type(rendered[0]) is FakeCliApiError


# ---------------------------------------------------------------------------
# create_run: F-4.2-A-08/J-4.2-09, never retried on ANY failure, 401 included
# ---------------------------------------------------------------------------


class TestCreateRunNeverRetried:
    @pytest.mark.asyncio
    async def test_a_401_is_never_reissued_but_the_stored_credentials_are_refreshed(
        self, main_module, fake_modules
    ) -> None:
        """F-4.2-A-08/J-4.2-09: the phase premise's rule is unconditional,
        "The CLI's retry policy NEVER covers POST /v1/query", with no 401
        carve-out. `_call_with_one_refresh`'s "a 401 is always safe to
        reissue" reasoning does not hold for `POST /v1/query` in general
        (`app.py`'s create-run handler can also raise a 401 from inside
        the handler body, after the concurrency count and the anonymous
        spend, for a revoked guest session), so `create_run` gets its own
        function that calls exactly once, full stop, while still
        refreshing the STORED credentials in the background so the next
        `s3 ask` is not immediately handed the same expired token.
        """
        creds = FakeCredentials(base_url="http://test", access_token="stale", refresh_token="r0")
        refresh_calls: list[FakeCredentials] = []

        async def refresh_locked(client: object, c: FakeCredentials) -> FakeCredentials:
            refresh_calls.append(c)
            return FakeCredentials(base_url="http://test", access_token="fresh", refresh_token="r1")

        fake_modules.credentials.refresh_locked = refresh_locked
        rendered: list[Exception] = []
        fake_modules.render.render_client_error = lambda err, exc: rendered.append(exc)

        call_count = 0

        async def coro_factory(c: FakeCredentials) -> tuple[str, str]:
            nonlocal call_count
            call_count += 1
            raise FakeAuthExpiredError(_response(401, {"detail": "expired"}))

        with pytest.raises(main_module._CommandError) as excinfo:
            await main_module._create_run_never_retried(
                coro_factory, http_client=object(), creds=creds, stderr=io.StringIO()
            )
        assert excinfo.value.exit_code == 1
        # Mutation: reissue create_run after the refresh -- call_count
        # would read 2.
        assert call_count == 1
        assert refresh_calls == [creds]
        assert len(rendered) == 1
        assert isinstance(rendered[0], FakeAuthExpiredError)

    @pytest.mark.asyncio
    async def test_the_original_401_is_still_reported_even_if_the_background_refresh_fails(
        self, main_module, fake_modules
    ) -> None:
        """The background refresh is best-effort: whether it succeeds or
        fails, the fact reported to the user is the same, the create did
        not happen, never a swallowed or replaced error from the refresh
        attempt itself.
        """
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")

        async def refresh_locked(client: object, c: FakeCredentials) -> FakeCredentials:
            raise FakeRefreshError("POST /auth/refresh returned 401; run: s3 login")

        fake_modules.credentials.refresh_locked = refresh_locked
        rendered: list[Exception] = []
        fake_modules.render.render_client_error = lambda err, exc: rendered.append(exc)

        async def coro_factory(c: FakeCredentials) -> tuple[str, str]:
            raise FakeAuthExpiredError(_response(401, {"detail": "expired"}))

        with pytest.raises(main_module._CommandError) as excinfo:
            await main_module._create_run_never_retried(
                coro_factory, http_client=object(), creds=creds, stderr=io.StringIO()
            )
        assert excinfo.value.exit_code == 1
        assert len(rendered) == 1
        assert isinstance(rendered[0], FakeAuthExpiredError)

    @pytest.mark.asyncio
    async def test_a_non_auth_error_is_rendered_and_never_reissued(
        self, main_module, fake_modules
    ) -> None:
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")
        rendered: list[Exception] = []
        fake_modules.render.render_client_error = lambda err, exc: rendered.append(exc)
        call_count = 0

        async def coro_factory(c: FakeCredentials) -> tuple[str, str]:
            nonlocal call_count
            call_count += 1
            raise FakeRateLimitedError(_response(429, {"detail": {"message": "slow down"}}))

        with pytest.raises(main_module._CommandError) as excinfo:
            await main_module._create_run_never_retried(
                coro_factory, http_client=object(), creds=creds, stderr=io.StringIO()
            )
        assert excinfo.value.exit_code == 1
        assert call_count == 1
        assert len(rendered) == 1
        assert isinstance(rendered[0], FakeRateLimitedError)

    @pytest.mark.asyncio
    async def test_a_transport_error_propagates_untouched(
        self, main_module, fake_modules
    ) -> None:
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")

        async def coro_factory(c: FakeCredentials) -> tuple[str, str]:
            raise httpx.ReadTimeout("simulated timeout", request=httpx.Request("POST", "http://t"))

        with pytest.raises(httpx.ReadTimeout):
            await main_module._create_run_never_retried(
                coro_factory, http_client=object(), creds=creds, stderr=io.StringIO()
            )


# ---------------------------------------------------------------------------
# s3 stop
# ---------------------------------------------------------------------------


class TestStopCommand:
    @pytest.mark.asyncio
    async def test_stop_success_prints_stopped_and_exits_0(self, main_module, fake_modules) -> None:
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")
        fake_modules.credentials.load = lambda: creds

        class FakeCliClient:
            def __init__(self, http: object, c: FakeCredentials) -> None:
                self.creds = c

            async def stop(self, run_id: str) -> bool:
                assert run_id == "run-123"
                return True

        fake_modules.client.CliClient = FakeCliClient

        out, err = io.StringIO(), io.StringIO()
        exit_code = await main_module.async_main(
            ["stop", "run-123"], stdin=io.StringIO(""), stdout=out, stderr=err, http_client=object()
        )
        assert exit_code == 0
        assert "stopped" in out.getvalue()
        assert err.getvalue() == ""

    @pytest.mark.asyncio
    async def test_stopping_an_already_finished_run_still_exits_0(
        self, main_module, fake_modules
    ) -> None:
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")
        fake_modules.credentials.load = lambda: creds

        class FakeCliClient:
            def __init__(self, http: object, c: FakeCredentials) -> None:
                pass

            async def stop(self, run_id: str) -> bool:
                return False  # the idempotent no-op shape

        fake_modules.client.CliClient = FakeCliClient

        out, err = io.StringIO(), io.StringIO()
        exit_code = await main_module.async_main(
            ["stop", "run-123"], stdin=io.StringIO(""), stdout=out, stderr=err, http_client=object()
        )
        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_stopping_someone_elses_run_renders_403_and_exits_nonzero(
        self, main_module, fake_modules
    ) -> None:
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")
        fake_modules.credentials.load = lambda: creds
        rendered: list[Exception] = []
        fake_modules.render.render_client_error = lambda err, exc: rendered.append(exc)

        class FakeCliClient:
            def __init__(self, http: object, c: FakeCredentials) -> None:
                pass

            async def stop(self, run_id: str) -> bool:
                raise FakeForbiddenError(_response(403, {"detail": "not your run"}))

        fake_modules.client.CliClient = FakeCliClient

        out, err = io.StringIO(), io.StringIO()
        exit_code = await main_module.async_main(
            ["stop", "run-123"], stdin=io.StringIO(""), stdout=out, stderr=err, http_client=object()
        )
        assert exit_code != 0
        assert len(rendered) == 1

    @pytest.mark.asyncio
    async def test_stop_with_no_stored_credentials_exits_nonzero_without_calling_the_client(
        self, main_module, fake_modules
    ) -> None:
        def load() -> FakeCredentials:
            raise FileNotFoundError()

        fake_modules.credentials.load = load

        constructed = []

        class FakeCliClient:
            def __init__(self, http: object, c: FakeCredentials) -> None:
                constructed.append(c)

        fake_modules.client.CliClient = FakeCliClient

        out, err = io.StringIO(), io.StringIO()
        exit_code = await main_module.async_main(
            ["stop", "run-123"], stdin=io.StringIO(""), stdout=out, stderr=err, http_client=object()
        )
        assert exit_code != 0
        assert constructed == []
        assert "s3 login" in err.getvalue()


# ---------------------------------------------------------------------------
# s3 ask: immediate attach, event dispatch, and Ctrl-C
# ---------------------------------------------------------------------------


class _FakeRenderer:
    def __init__(self, out: object, err: object, *, operator: bool) -> None:
        self.out = out
        self.err = err
        self.operator = operator
        self.handled: list[object] = []
        self.finished = False
        self.finish_result = 0

    def handle(self, event: object) -> None:
        self.handled.append(event)

    def finish(self) -> int:
        self.finished = True
        return self.finish_result


class TestAskCommand:
    @pytest.mark.asyncio
    async def test_events_are_dispatched_in_order_and_finish_becomes_the_exit_code(
        self, main_module, fake_modules
    ) -> None:
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")
        fake_modules.credentials.load = lambda: creds

        renderer_holder: list[_FakeRenderer] = []

        def make_renderer(out: object, err: object, *, operator: bool) -> _FakeRenderer:
            renderer = _FakeRenderer(out, err, operator=operator)
            renderer.finish_result = 0
            renderer_holder.append(renderer)
            return renderer

        fake_modules.render.Renderer = make_renderer

        events = [_FakeEvent("guard"), _FakeEvent("token"), _FakeEvent("done")]

        class FakeCliClient:
            def __init__(self, http: object, c: FakeCredentials) -> None:
                self.creds = c

            async def create_run(
                self, text: str, session_id: str, audience_depth: str
            ) -> tuple[str, str]:
                return "run-1", "persona"

            def stream_events(self, run_id: str, *, last_event_id: str | None = None):
                async def _gen():
                    for event in events:
                        yield event

                return _gen()

        fake_modules.client.CliClient = FakeCliClient

        out, err = io.StringIO(), io.StringIO()
        exit_code = await main_module.async_main(
            ["ask", "What gene is BRCA1?", "--session-id", "s1"],
            stdin=io.StringIO(""),
            stdout=out,
            stderr=err,
            http_client=object(),
        )
        assert exit_code == 0
        assert renderer_holder[0].handled == events
        assert renderer_holder[0].finished

    @pytest.mark.asyncio
    async def test_finish_return_value_becomes_the_exit_code_unmodified(
        self, main_module, fake_modules
    ) -> None:
        """main.py must not add its own exit-code logic on top of
        Renderer.finish(): a refuse-shaped run's nonzero code must pass
        through exactly, not get coerced to 0 or 1.
        """
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")
        fake_modules.credentials.load = lambda: creds

        def make_renderer(out: object, err: object, *, operator: bool) -> _FakeRenderer:
            renderer = _FakeRenderer(out, err, operator=operator)
            renderer.finish_result = 7  # a distinctive, non-conventional code
            return renderer

        fake_modules.render.Renderer = make_renderer

        class FakeCliClient:
            def __init__(self, http: object, c: FakeCredentials) -> None:
                pass

            async def create_run(
                self, text: str, session_id: str, audience_depth: str
            ) -> tuple[str, str]:
                return "run-1", "persona"

            def stream_events(self, run_id: str, *, last_event_id: str | None = None):
                async def _gen():
                    return
                    yield  # pragma: no cover - makes this a generator with zero events

                return _gen()

        fake_modules.client.CliClient = FakeCliClient

        exit_code = await main_module.async_main(
            ["ask", "hi", "--session-id", "s1"],
            stdin=io.StringIO(""),
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            http_client=object(),
        )
        assert exit_code == 7

    @pytest.mark.asyncio
    async def test_create_run_is_called_before_stream_events_with_nothing_else_between(
        self, main_module, fake_modules
    ) -> None:
        """Proxy for the "attach immediately" requirement: asserts the
        call order is exactly create_run then stream_events, with no
        other fake collaborator call recorded between them.
        """
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")
        fake_modules.credentials.load = lambda: creds
        fake_modules.render.Renderer = lambda out, err, *, operator: _FakeRenderer(
            out, err, operator=operator
        )

        call_order: list[str] = []

        class FakeCliClient:
            def __init__(self, http: object, c: FakeCredentials) -> None:
                pass

            async def create_run(
                self, text: str, session_id: str, audience_depth: str
            ) -> tuple[str, str]:
                call_order.append("create_run")
                return "run-1", "persona"

            def stream_events(self, run_id: str, *, last_event_id: str | None = None):
                call_order.append("stream_events")

                async def _gen():
                    return
                    yield  # pragma: no cover

                return _gen()

        fake_modules.client.CliClient = FakeCliClient

        await main_module.async_main(
            ["ask", "hi", "--session-id", "s1"],
            stdin=io.StringIO(""),
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            http_client=object(),
        )
        assert call_order == ["create_run", "stream_events"]

    @pytest.mark.asyncio
    async def test_create_run_timeout_is_never_retried(self, main_module, fake_modules) -> None:
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")
        fake_modules.credentials.load = lambda: creds
        fake_modules.render.Renderer = lambda out, err, *, operator: _FakeRenderer(
            out, err, operator=operator
        )

        call_count = 0

        class FakeCliClient:
            def __init__(self, http: object, c: FakeCredentials) -> None:
                pass

            async def create_run(
                self, text: str, session_id: str, audience_depth: str
            ) -> tuple[str, str]:
                nonlocal call_count
                call_count += 1
                raise httpx.ReadTimeout(
                    "simulated timeout", request=httpx.Request("POST", "http://test/v1/query")
                )

        fake_modules.client.CliClient = FakeCliClient

        out, err = io.StringIO(), io.StringIO()
        exit_code = await main_module.async_main(
            ["ask", "hi", "--session-id", "s1"],
            stdin=io.StringIO(""),
            stdout=out,
            stderr=err,
            http_client=object(),
        )
        assert exit_code != 0
        assert call_count == 1
        assert err.getvalue() != ""

    @pytest.mark.asyncio
    async def test_ctrl_c_sends_stop_before_returning_a_nonzero_exit(
        self, main_module, fake_modules
    ) -> None:
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")
        fake_modules.credentials.load = lambda: creds
        fake_modules.render.Renderer = lambda out, err, *, operator: _FakeRenderer(
            out, err, operator=operator
        )

        stop_calls: list[str] = []
        started = asyncio.Event()

        class FakeCliClient:
            def __init__(self, http: object, c: FakeCredentials) -> None:
                pass

            async def create_run(
                self, text: str, session_id: str, audience_depth: str
            ) -> tuple[str, str]:
                return "run-1", "persona"

            def stream_events(self, run_id: str, *, last_event_id: str | None = None):
                async def _gen():
                    started.set()
                    await asyncio.sleep(3600)
                    yield _FakeEvent("unreachable")  # pragma: no cover

                return _gen()

            async def stop(self, run_id: str) -> bool:
                stop_calls.append(run_id)
                return True

        fake_modules.client.CliClient = FakeCliClient

        interrupt_signals: asyncio.Queue[None] = asyncio.Queue()
        out, err = io.StringIO(), io.StringIO()
        task = asyncio.create_task(
            main_module.async_main(
                ["ask", "hi", "--session-id", "s1"],
                stdin=io.StringIO(""),
                stdout=out,
                stderr=err,
                http_client=object(),
                interrupt_signals=interrupt_signals,
            )
        )
        await asyncio.wait_for(started.wait(), timeout=5.0)
        interrupt_signals.put_nowait(None)
        exit_code = await asyncio.wait_for(task, timeout=5.0)

        assert exit_code != 0
        assert stop_calls == ["run-1"]

    @pytest.mark.asyncio
    async def test_second_ctrl_c_during_a_slow_stop_returns_without_waiting_for_it(
        self, main_module, fake_modules
    ) -> None:
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")
        fake_modules.credentials.load = lambda: creds
        fake_modules.render.Renderer = lambda out, err, *, operator: _FakeRenderer(
            out, err, operator=operator
        )

        started = asyncio.Event()

        class FakeCliClient:
            def __init__(self, http: object, c: FakeCredentials) -> None:
                pass

            async def create_run(
                self, text: str, session_id: str, audience_depth: str
            ) -> tuple[str, str]:
                return "run-1", "persona"

            def stream_events(self, run_id: str, *, last_event_id: str | None = None):
                async def _gen():
                    started.set()
                    await asyncio.sleep(3600)
                    yield _FakeEvent("unreachable")  # pragma: no cover

                return _gen()

            async def stop(self, run_id: str) -> bool:
                await asyncio.sleep(2.0)  # a slow stop, to open a real race window
                return True

        fake_modules.client.CliClient = FakeCliClient

        interrupt_signals: asyncio.Queue[None] = asyncio.Queue()
        task = asyncio.create_task(
            main_module.async_main(
                ["ask", "hi", "--session-id", "s1"],
                stdin=io.StringIO(""),
                stdout=io.StringIO(),
                stderr=io.StringIO(),
                http_client=object(),
                interrupt_signals=interrupt_signals,
            )
        )
        await asyncio.wait_for(started.wait(), timeout=5.0)
        interrupt_signals.put_nowait(None)
        await asyncio.sleep(0.2)  # let the CLI actually enter the (slow) stop call
        interrupt_signals.put_nowait(None)

        import time

        start = time.monotonic()
        exit_code = await asyncio.wait_for(task, timeout=3.0)
        elapsed = time.monotonic() - start

        assert exit_code != 0
        # Mutation: wait for the slow stop call's response before honoring
        # the second interrupt -- would take >= the 2.0s artificial delay.
        assert elapsed < 1.5

    @pytest.mark.asyncio
    async def test_operator_flag_no_longer_exists(self, main_module, fake_modules) -> None:
        """F-4.2-A-09/J-4.2-03: `--operator` used to be a client-supplied
        flag reaching `Renderer(operator=...)` with no credential check
        anywhere in between, so anyone could type it to defeat the CLI's
        cost suppression. Removed rather than wired to a check this
        module has no way to perform (operator status is server-side
        truth, an allowlist keyed on user id). `s3 ask ... --operator` is
        now simply not a recognized flag and is a parse error.
        """
        out, err = io.StringIO(), io.StringIO()
        exit_code = await main_module.async_main(
            ["ask", "hi", "--operator"],
            stdin=io.StringIO(""),
            stdout=out,
            stderr=err,
            http_client=object(),
        )
        assert exit_code == 2
        assert err.getvalue() != ""
        args = main_module._parse_ask_args(["hi"], out=io.StringIO(), err=io.StringIO())
        assert not hasattr(args, "operator")

    @pytest.mark.asyncio
    async def test_the_renderer_is_always_constructed_with_operator_false(
        self, main_module, fake_modules
    ) -> None:
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")
        fake_modules.credentials.load = lambda: creds
        captured: dict[str, object] = {}

        def make_renderer(out: object, err: object, *, operator: bool) -> _FakeRenderer:
            captured["operator"] = operator
            return _FakeRenderer(out, err, operator=operator)

        fake_modules.render.Renderer = make_renderer

        class FakeCliClient:
            def __init__(self, http: object, c: FakeCredentials) -> None:
                pass

            async def create_run(
                self, text: str, session_id: str, audience_depth: str
            ) -> tuple[str, str]:
                return "run-1", "persona"

            def stream_events(self, run_id: str, *, last_event_id: str | None = None):
                async def _gen():
                    return
                    yield  # pragma: no cover

                return _gen()

        fake_modules.client.CliClient = FakeCliClient

        await main_module.async_main(
            ["ask", "hi", "--session-id", "s1"],
            stdin=io.StringIO(""),
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            http_client=object(),
        )
        assert captured["operator"] is False

    @pytest.mark.asyncio
    async def test_sigint_scope_wraps_only_the_stream_consumption_window(
        self, main_module, fake_modules
    ) -> None:
        """F-4.2-A-04: the real SIGINT handler `main()` installs must be
        active ONLY around `_consume_stream_with_interrupt`, never around
        `create_run` or `Renderer`/`CliClient` construction, so that
        Ctrl-C outside the stream falls through to Python's default
        `KeyboardInterrupt` handling instead of being silently absorbed
        by a handler nothing outside the stream drains.
        """
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")
        fake_modules.credentials.load = lambda: creds
        fake_modules.render.Renderer = lambda out, err, *, operator: _FakeRenderer(
            out, err, operator=operator
        )

        events_log: list[str] = []

        class FakeSigintScope:
            def __enter__(self) -> None:
                events_log.append("enter")

            def __exit__(self, *exc_info: object) -> bool:
                events_log.append("exit")
                return False

        class FakeCliClient:
            def __init__(self, http: object, c: FakeCredentials) -> None:
                pass

            async def create_run(
                self, text: str, session_id: str, audience_depth: str
            ) -> tuple[str, str]:
                assert "enter" not in events_log
                events_log.append("create_run")
                return "run-1", "persona"

            def stream_events(self, run_id: str, *, last_event_id: str | None = None):
                events_log.append("stream_events_called")

                async def _gen():
                    assert "enter" in events_log
                    return
                    yield  # pragma: no cover

                return _gen()

        fake_modules.client.CliClient = FakeCliClient

        exit_code = await main_module.async_main(
            ["ask", "hi", "--session-id", "s1"],
            stdin=io.StringIO(""),
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            http_client=object(),
            sigint_scope=FakeSigintScope(),
        )
        assert exit_code == 0
        assert events_log.index("create_run") < events_log.index("stream_events_called")
        assert events_log.index("stream_events_called") < events_log.index("enter")
        assert "exit" in events_log


# ---------------------------------------------------------------------------
# s3 ask: the three independent post-stream disclosures
# (F-4.2-A-16/F-4.2-A-15/F-4.2-A-28)
# ---------------------------------------------------------------------------


class _FakeCliClientForStream:
    """A `CliClient` stand-in whose `stream_events` yields a fixed event
    list and which carries the two post-stream attributes the lead's
    phase-4.2 correction added to the real `client.py`:
    `stream_skipped_frame_count` and `stream_truncated`. Defaults mirror
    a clean, complete stream (0 skipped, not truncated), matching a
    real `CliClient` that never hit either condition.
    """

    def __init__(
        self,
        http: object,
        creds: FakeCredentials,
        *,
        events: list[_FakeEvent],
        skipped: int = 0,
        truncated: bool = False,
    ) -> None:
        self._events = events
        self.stream_skipped_frame_count = skipped
        self.stream_truncated = truncated

    async def create_run(self, text: str, session_id: str, audience_depth: str) -> tuple[str, str]:
        return "run-1", "persona"

    def stream_events(self, run_id: str, *, last_event_id: str | None = None):
        events = self._events

        async def _gen():
            for event in events:
                yield event

        return _gen()


class TestStreamDisclosures:
    async def _run_ask(
        self, main_module, fake_modules, *, events: list[_FakeEvent], skipped: int, truncated: bool
    ) -> tuple[int, str]:
        creds = FakeCredentials(base_url="http://test", access_token="a", refresh_token="r")
        fake_modules.credentials.load = lambda: creds
        fake_modules.render.Renderer = lambda out, err, *, operator: _FakeRenderer(
            out, err, operator=operator
        )
        fake_modules.client.CliClient = lambda http, c: _FakeCliClientForStream(
            http, c, events=events, skipped=skipped, truncated=truncated
        )

        stderr = io.StringIO()
        exit_code = await main_module.async_main(
            ["ask", "hi", "--session-id", "s1"],
            stdin=io.StringIO(""),
            stdout=io.StringIO(),
            stderr=stderr,
            http_client=object(),
        )
        return exit_code, stderr.getvalue()

    @pytest.mark.asyncio
    async def test_a_truncated_stream_is_disclosed_on_stderr(self, main_module, fake_modules) -> None:
        """F-4.2-A-16: `client.stream_truncated` is the authoritative
        signal that the stream ended mid-frame; before this, a truncated
        stream produced a partial answer, exit 1, and NOTHING on stderr.
        """
        _exit_code, err = await self._run_ask(
            main_module,
            fake_modules,
            events=[_FakeEvent("token")],
            skipped=0,
            truncated=True,
        )
        assert "stopped early" in err
        # Distinct from the skipped-frame and empty-done sentences: this
        # test must not accidentally also trip either.
        assert "skipped" not in err
        assert "no answer text" not in err

    @pytest.mark.asyncio
    async def test_skipped_frames_are_disclosed_with_a_count(
        self, main_module, fake_modules
    ) -> None:
        _exit_code, err = await self._run_ask(
            main_module,
            fake_modules,
            events=[_FakeEvent("token"), _FakeEvent("done")],
            skipped=3,
            truncated=False,
        )
        assert "3 frames" in err
        assert "skipped" in err
        assert "stopped early" not in err

    @pytest.mark.asyncio
    async def test_one_skipped_frame_uses_singular_wording(
        self, main_module, fake_modules
    ) -> None:
        _exit_code, err = await self._run_ask(
            main_module,
            fake_modules,
            events=[_FakeEvent("token"), _FakeEvent("done")],
            skipped=1,
            truncated=False,
        )
        assert "1 frame " in err
        assert "1 frames" not in err

    @pytest.mark.asyncio
    async def test_skipped_frames_and_truncation_are_reported_as_separate_sentences(
        self, main_module, fake_modules
    ) -> None:
        """Both can be true at once (a skipped frame followed by a
        genuinely truncated connection), and collapsing them into one
        sentence would lose which one, or both, actually happened.
        """
        _exit_code, err = await self._run_ask(
            main_module,
            fake_modules,
            events=[_FakeEvent("token")],
            skipped=2,
            truncated=True,
        )
        assert "2 frames" in err
        assert "skipped" in err
        assert "stopped early" in err

    @pytest.mark.asyncio
    async def test_an_empty_done_with_no_tokens_or_citations_is_disclosed(
        self, main_module, fake_modules
    ) -> None:
        """F-4.2-A-15: a `done` arrives, nothing was ever printed and no
        citation was ever delivered, so a pipeline reading only the exit
        code would see success with nothing actually behind it.
        """
        _exit_code, err = await self._run_ask(
            main_module,
            fake_modules,
            events=[_FakeEvent("guard"), _FakeEvent("done")],
            skipped=0,
            truncated=False,
        )
        assert "no answer text and no citations" in err

    @pytest.mark.asyncio
    async def test_a_normal_complete_stream_discloses_nothing_extra(
        self, main_module, fake_modules
    ) -> None:
        """The negative case: a clean stream with tokens, a citation, and
        a `done` must not trip any of the three disclosures, or every
        ordinary successful run would grow spurious stderr noise.
        """
        _exit_code, err = await self._run_ask(
            main_module,
            fake_modules,
            events=[_FakeEvent("token"), _FakeEvent("citation"), _FakeEvent("done")],
            skipped=0,
            truncated=False,
        )
        assert err == ""


# ---------------------------------------------------------------------------
# _read_password: getpass on a real TTY, a plain line read otherwise
# ---------------------------------------------------------------------------


class TestReadPassword:
    def test_falls_back_to_readline_on_a_non_tty_stdin(self, main_module) -> None:
        stdin = io.StringIO("hunter2\n")
        assert main_module._read_password(stdin) == "hunter2"

    def test_uses_getpass_on_a_real_tty_and_never_reads_a_line(
        self, main_module, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-4.2-A-14: verified against a real pty that a plain
        `stdin.readline()` left the terminal's ECHO bit on. When stdin
        reports itself as a TTY, this must go through `getpass.getpass`
        instead, and must never call `readline` at all.
        """
        prompts: list[str] = []
        monkeypatch.setattr(
            main_module.getpass, "getpass", lambda prompt="": prompts.append(prompt) or "typed-secret"
        )

        class FakeTtyStdin:
            def isatty(self) -> bool:
                return True

            def readline(self) -> str:
                raise AssertionError("must not read a line when stdin is a TTY")

        result = main_module._read_password(FakeTtyStdin())
        assert result == "typed-secret"
        assert prompts == [""]


# ---------------------------------------------------------------------------
# s3 login: its own declared timeout (J-4.2-07)
# ---------------------------------------------------------------------------


class TestLoginTimeout:
    @pytest.mark.asyncio
    async def test_login_declares_its_own_timeout_not_the_streams_120s(
        self, main_module, fake_modules
    ) -> None:
        """J-4.2-07: `POST /auth/login` used to declare no timeout of its
        own and silently inherited the injected client's 120.0s read
        timeout (sized for the SSE stream), an eightfold drift from the
        15s budget `credentials.py`'s `REFRESH_TIMEOUT_SECONDS` already
        applies to `POST /auth/refresh`, the identical auth-router call
        shape.
        """
        captured_timeout: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_timeout["value"] = request.extensions.get("timeout")
            return httpx.Response(200, json={"access_token": "a", "refresh_token": "r"})

        http_client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://example.test"
        )
        fake_modules.credentials.store = lambda creds: None
        try:
            exit_code = await main_module.async_main(
                ["login", "person@example.com"],
                stdin=io.StringIO("hunter2\n"),
                stdout=io.StringIO(),
                stderr=io.StringIO(),
                http_client=http_client,
            )
        finally:
            await http_client.aclose()

        assert exit_code == 0
        expected = httpx.Timeout(main_module._LOGIN_TIMEOUT_SECONDS).as_dict()
        assert captured_timeout["value"] == expected


# ---------------------------------------------------------------------------
# main(): converts a KeyboardInterrupt outside the stream window into 130
# ---------------------------------------------------------------------------


class TestMainEntryPoint:
    def test_a_keyboard_interrupt_outside_the_stream_becomes_exit_130(
        self, main_module, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """F-4.2-A-04: outside the stream window, Ctrl-C now relies on
        Python's default `KeyboardInterrupt` handling (the custom
        queue-based handler is scoped to the stream loop only, see
        `TestAskCommand.test_sigint_scope_wraps_only_the_stream_consumption_window`),
        so `main()` itself must convert a `KeyboardInterrupt` escaping
        `asyncio.run` into the same 130 exit code an interrupted stream
        already produces, rather than a raw traceback.
        """

        def fake_run(coro: object) -> int:
            coro.close()  # type: ignore[attr-defined]
            raise KeyboardInterrupt()

        monkeypatch.setattr(main_module.asyncio, "run", fake_run)

        exit_code = main_module.main([])
        captured = capsys.readouterr()
        assert exit_code == main_module.EXIT_INTERRUPTED
        assert "interrupted" in captured.err
