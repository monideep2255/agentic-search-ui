"""Unit tests for the `s3` CLI's credential store: `credentials.py`, T-4.2-02.

These are this ticket's OWN tests, distinct from and additional to the
phase 4.2 premise gate (`test_phase_4_2_premise.py`), which this file must
not edit. The premise gate's `TestCredentialMode`, `TestRefreshRotation`
and `TestRefreshLock` classes already pin the four properties named in the
ticket brief end to end, through the real HTTP surface; this file pins
`credentials.py` in isolation, including two properties the premise gate
does not reach directly: the widen-then-narrow ordering at file creation,
and the re-read-after-lock branch when a concurrent rotation already
happened (proven here by a call count of zero on the losing side, not
observable through the premise gate's full-stack arms).

Depends on:
    - system_03_search_agent.adapters.cli.credentials (the module under
      test)

Reads:
    - Nothing outside pytest's own tmp_path fixture.

Writes:
    - Nothing outside pytest's own tmp_path fixture.
"""

from __future__ import annotations

import asyncio
import json
import os
import stat

import httpx
import pytest

from system_03_search_agent.adapters.cli import credentials as creds_mod

pytestmark = pytest.mark.skipif(
    os.name != "posix",
    reason="mode-bit and flock assertions below assume POSIX semantics",
)


def _point_at(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(creds_mod, "CREDENTIALS_PATH", tmp_path / "sub" / "credentials")


# ---------------------------------------------------------------------------
# store() / load() round trip
# ---------------------------------------------------------------------------


def test_store_then_load_round_trips_all_three_fields(monkeypatch, tmp_path) -> None:
    _point_at(monkeypatch, tmp_path)
    creds_mod.store(
        creds_mod.Credentials(base_url="http://example.test", access_token="acc", refresh_token="ref")
    )

    loaded = creds_mod.load()

    assert loaded == creds_mod.Credentials(
        base_url="http://example.test", access_token="acc", refresh_token="ref"
    )


def test_store_round_trips_a_none_access_token(monkeypatch, tmp_path) -> None:
    _point_at(monkeypatch, tmp_path)
    creds_mod.store(creds_mod.Credentials(base_url="http://example.test", access_token=None, refresh_token="ref"))

    loaded = creds_mod.load()

    assert loaded.access_token is None
    assert loaded.refresh_token == "ref"


def test_load_on_a_missing_file_raises_file_not_found_with_a_next_step(monkeypatch, tmp_path) -> None:
    _point_at(monkeypatch, tmp_path)

    with pytest.raises(FileNotFoundError, match="s3 login"):
        creds_mod.load()


# ---------------------------------------------------------------------------
# Mode 600: creation, refusal, parent directory
# ---------------------------------------------------------------------------


def test_store_creates_the_parent_directory_at_mode_700(monkeypatch, tmp_path) -> None:
    _point_at(monkeypatch, tmp_path)
    creds_mod.store(creds_mod.Credentials(base_url="u", access_token="a", refresh_token="r"))

    parent = creds_mod.CREDENTIALS_PATH.parent
    assert stat.S_IMODE(os.stat(parent).st_mode) == 0o700


def test_store_never_creates_the_temp_file_wider_than_600(monkeypatch, tmp_path) -> None:
    """Pins the widen-then-narrow property at the syscall, not just the
    final state: the mode argument passed to os.open for the temp file
    must already be 0o600, never a wider default later chmod'd down.

    Mutation: create the temp file via plain `open()` (default umask, no
    explicit mode) and `os.chmod()` it after writing -> the recorded mode
    below would be whatever the umask produced (commonly 0o644), not
    0o600, catching the exact hazard this test exists to close.
    """
    _point_at(monkeypatch, tmp_path)
    recorded_modes: list[int] = []
    real_os_open = os.open

    def _spying_open(path, flags, mode=0o777):
        recorded_modes.append(mode)
        return real_os_open(path, flags, mode)

    monkeypatch.setattr(creds_mod.os, "open", _spying_open)

    creds_mod.store(creds_mod.Credentials(base_url="u", access_token="a", refresh_token="r"))

    assert recorded_modes, "os.open was never called for the temp file"
    assert recorded_modes[0] == 0o600


def test_store_result_is_mode_600_regardless_of_a_permissive_umask(monkeypatch, tmp_path) -> None:
    _point_at(monkeypatch, tmp_path)
    old_umask = os.umask(0o022)
    try:
        creds_mod.store(creds_mod.Credentials(base_url="u", access_token="a", refresh_token="r"))
    finally:
        os.umask(old_umask)

    mode = stat.S_IMODE(os.stat(creds_mod.CREDENTIALS_PATH).st_mode)
    assert mode == 0o600


def test_store_replaces_atomically_leaving_no_temp_file_behind(monkeypatch, tmp_path) -> None:
    _point_at(monkeypatch, tmp_path)
    creds_mod.store(creds_mod.Credentials(base_url="u", access_token="a1", refresh_token="r1"))
    creds_mod.store(creds_mod.Credentials(base_url="u", access_token="a2", refresh_token="r2"))

    parent = creds_mod.CREDENTIALS_PATH.parent
    leftovers = [p for p in parent.iterdir() if p.name != creds_mod.CREDENTIALS_PATH.name]
    assert leftovers == []
    assert creds_mod.load().access_token == "a2"


def test_load_refuses_a_file_wider_than_600_naming_the_remediation(monkeypatch, tmp_path) -> None:
    _point_at(monkeypatch, tmp_path)
    creds_mod.store(creds_mod.Credentials(base_url="u", access_token="a", refresh_token="r"))
    os.chmod(creds_mod.CREDENTIALS_PATH, 0o644)

    with pytest.raises(creds_mod.InsecureCredentialsError, match="chmod 600"):
        creds_mod.load()


def test_load_accepts_a_file_narrower_than_600(monkeypatch, tmp_path) -> None:
    """No false positive: owner-read-only (0400) is a SUBSET of 0600's
    bits, not wider, and must not be refused."""
    _point_at(monkeypatch, tmp_path)
    creds_mod.store(creds_mod.Credentials(base_url="u", access_token="a", refresh_token="r"))
    os.chmod(creds_mod.CREDENTIALS_PATH, 0o400)

    loaded = creds_mod.load()
    assert loaded.refresh_token == "r"


def test_load_refuses_owner_execute_even_with_no_group_or_other_bits(monkeypatch, tmp_path) -> None:
    """0700 is numerically wider than 0600 (owner-execute set) even though
    no other account gains access; the module's stated contract is "wider
    than 600", not "readable by another account", so this is refused too."""
    _point_at(monkeypatch, tmp_path)
    creds_mod.store(creds_mod.Credentials(base_url="u", access_token="a", refresh_token="r"))
    os.chmod(creds_mod.CREDENTIALS_PATH, 0o700)

    with pytest.raises(creds_mod.InsecureCredentialsError):
        creds_mod.load()


# ---------------------------------------------------------------------------
# Secrets never appear in an exception message
# ---------------------------------------------------------------------------


def test_insecure_credentials_error_never_names_the_token_value(monkeypatch, tmp_path) -> None:
    _point_at(monkeypatch, tmp_path)
    creds_mod.store(
        creds_mod.Credentials(base_url="u", access_token="super-secret-access", refresh_token="super-secret-refresh")
    )
    os.chmod(creds_mod.CREDENTIALS_PATH, 0o644)

    with pytest.raises(creds_mod.InsecureCredentialsError) as exc_info:
        creds_mod.load()

    message = str(exc_info.value)
    assert "super-secret-access" not in message
    assert "super-secret-refresh" not in message


# ---------------------------------------------------------------------------
# refresh_locked: the happy path, persistence ordering, and non-200
# ---------------------------------------------------------------------------


def _refresh_transport(response_body: dict, status_code: int = 200, on_call=None) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if on_call is not None:
            on_call(request)
        return httpx.Response(status_code, json=response_body)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_refresh_locked_persists_new_creds_before_returning(monkeypatch, tmp_path) -> None:
    _point_at(monkeypatch, tmp_path)
    creds_mod.store(creds_mod.Credentials(base_url="http://test", access_token="old-a", refresh_token="old-r"))
    starting = creds_mod.load()

    transport = _refresh_transport({"access_token": "new-a", "refresh_token": "new-r", "token_type": "bearer"})
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await creds_mod.refresh_locked(client, starting)
    finally:
        await client.aclose()

    assert result.access_token == "new-a"
    assert result.refresh_token == "new-r"
    # The property under test: by the time refresh_locked returns, disk
    # already reflects the rotated token, not merely "eventually".
    assert creds_mod.load().refresh_token == "new-r"


@pytest.mark.asyncio
async def test_refresh_locked_raises_refresh_error_on_a_non_200_and_names_next_step(monkeypatch, tmp_path) -> None:
    _point_at(monkeypatch, tmp_path)
    creds_mod.store(creds_mod.Credentials(base_url="http://test", access_token="old-a", refresh_token="old-r"))
    starting = creds_mod.load()

    transport = _refresh_transport({"detail": "invalid or expired refresh token"}, status_code=401)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        with pytest.raises(creds_mod.RefreshError, match="s3 login"):
            await creds_mod.refresh_locked(client, starting)
    finally:
        await client.aclose()

    # A failed refresh must not corrupt the stored credentials.
    assert creds_mod.load().refresh_token == "old-r"


@pytest.mark.asyncio
async def test_refresh_locked_raises_refresh_error_on_a_200_with_a_non_json_body(
    monkeypatch, tmp_path
) -> None:
    """F-4.2-D-05: a 200 whose body is not JSON at all used to reach the
    bare `response.json()` call at `_refresh_and_store` and escape as a
    raw `json.JSONDecodeError`, a type that is not a `CredentialsError`,
    so `_call_with_one_refresh`/`_create_run_never_retried` in main.py
    (whose callers only catch `CredentialsError`) never got the chance
    to render it as anything but "unexpected error". This asserts
    `refresh_locked` itself now raises the typed, curated `RefreshError`
    for this shape, closing the gap at its source rather than relying on
    every caller to special-case a parser exception.
    """
    _point_at(monkeypatch, tmp_path)
    creds_mod.store(
        creds_mod.Credentials(base_url="http://test", access_token="old-a", refresh_token="old-r")
    )
    starting = creds_mod.load()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json at all", headers={"content-type": "text/plain"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
    try:
        # Mutation: revert to a bare `response.json()` call with no
        # content-type or ValueError guard -- this would raise
        # json.JSONDecodeError instead of creds_mod.RefreshError, failing
        # the pytest.raises type check below.
        with pytest.raises(creds_mod.RefreshError):
            await creds_mod.refresh_locked(client, starting)
    finally:
        await client.aclose()

    # A failed refresh must not corrupt the stored credentials.
    assert creds_mod.load().refresh_token == "old-r"


@pytest.mark.asyncio
async def test_refresh_locked_raises_refresh_error_on_a_200_missing_the_token_fields(
    monkeypatch, tmp_path
) -> None:
    """F-4.2-D-05: a 200 with a syntactically valid JSON body that omits
    `access_token`/`refresh_token` used to reach `body["access_token"]`
    and raise a raw `KeyError`, the same undercaught shape as the
    non-JSON case above.
    """
    _point_at(monkeypatch, tmp_path)
    creds_mod.store(
        creds_mod.Credentials(base_url="http://test", access_token="old-a", refresh_token="old-r")
    )
    starting = creds_mod.load()

    transport = _refresh_transport({"token_type": "bearer"})  # no access_token/refresh_token
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        # Mutation: index `body["access_token"]`/`body["refresh_token"]`
        # directly instead of the isinstance-guarded `.get()` pair above
        # -- this would raise a bare KeyError instead of RefreshError.
        with pytest.raises(creds_mod.RefreshError):
            await creds_mod.refresh_locked(client, starting)
    finally:
        await client.aclose()

    assert creds_mod.load().refresh_token == "old-r"


@pytest.mark.asyncio
async def test_refresh_locked_uses_the_already_rotated_disk_value_without_calling_the_server(
    monkeypatch, tmp_path
) -> None:
    """Simulates the re-read-after-lock branch directly: the caller's
    `creds` argument carries a refresh token that is already stale on
    disk (as if another invocation rotated it first). refresh_locked must
    return the on-disk value and must NOT spend the stale token against
    the server.

    Mutation: skip the re-read and always call the server with the
    caller's argument -> the call counter below would be 1 instead of 0,
    and the reused stale token would trip the server's real reuse
    detection in the full-stack premise gate (TestRefreshLock).
    """
    _point_at(monkeypatch, tmp_path)
    creds_mod.store(creds_mod.Credentials(base_url="http://test", access_token="disk-a", refresh_token="disk-r"))
    stale_argument = creds_mod.Credentials(base_url="http://test", access_token="old-a", refresh_token="stale-r")

    calls: list[httpx.Request] = []
    transport = _refresh_transport(
        {"access_token": "unused", "refresh_token": "unused", "token_type": "bearer"},
        on_call=calls.append,
    )
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await creds_mod.refresh_locked(client, stale_argument)
    finally:
        await client.aclose()

    assert calls == []
    assert result.refresh_token == "disk-r"


@pytest.mark.asyncio
async def test_refresh_locked_serializes_two_contending_refreshes_to_one_server_call(monkeypatch, tmp_path) -> None:
    """Two coroutines race to refresh the SAME stale on-disk token. Exactly
    one of them should reach the server; the other must observe the
    winner's already-rotated result via the re-read.

    Mutation: remove the lock (call `_refresh_and_store` directly instead
    of going through `_CredentialFileLock`) -> both coroutines would race
    past the check unlocked and the call count below would be 2.
    """
    _point_at(monkeypatch, tmp_path)
    creds_mod.store(creds_mod.Credentials(base_url="http://test", access_token="old-a", refresh_token="shared-r"))
    starting = creds_mod.load()

    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200, json={"access_token": "won-a", "refresh_token": "won-r", "token_type": "bearer"}
        )

    transport = httpx.MockTransport(handler)
    client_a = httpx.AsyncClient(transport=transport, base_url="http://test")
    client_b = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result_a, result_b = await asyncio.gather(
            creds_mod.refresh_locked(client_a, starting),
            creds_mod.refresh_locked(client_b, starting),
        )
    finally:
        await client_a.aclose()
        await client_b.aclose()

    assert len(calls) == 1
    assert result_a.refresh_token == "won-r"
    assert result_b.refresh_token == "won-r"
    assert creds_mod.load().refresh_token == "won-r"


@pytest.mark.asyncio
async def test_refresh_locked_degrades_honestly_without_flock(monkeypatch, tmp_path) -> None:
    """On a platform with no fcntl, refresh_locked still functions for a
    single caller but must say so via a RuntimeWarning rather than
    silently pretending it is still locked."""
    _point_at(monkeypatch, tmp_path)
    creds_mod.store(creds_mod.Credentials(base_url="http://test", access_token="old-a", refresh_token="old-r"))
    starting = creds_mod.load()

    monkeypatch.setattr(creds_mod, "_HAS_FLOCK", False)
    monkeypatch.setattr(creds_mod, "_warned_no_flock", False)

    transport = _refresh_transport({"access_token": "new-a", "refresh_token": "new-r", "token_type": "bearer"})
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        with pytest.warns(RuntimeWarning, match="WITHOUT the exclusive lock"):
            result = await creds_mod.refresh_locked(client, starting)
    finally:
        await client.aclose()

    assert result.refresh_token == "new-r"


def test_credentials_path_reads_the_env_override(monkeypatch) -> None:
    monkeypatch.setenv("S3_CREDENTIALS_PATH", "/tmp/wherever-this-test-points")
    assert creds_mod._default_credentials_path() == creds_mod.Path("/tmp/wherever-this-test-points")


def test_default_credentials_path_expands_a_tilde_override(monkeypatch, tmp_path) -> None:
    """F-4.2-A-23: S3_CREDENTIALS_PATH="~/foo" must resolve against the
    real home directory, not create a literal "./~/" directory.

    Mutation: drop the .expanduser() call in _default_credentials_path ->
    the assertion below would compare against a literal Path("~/creds-file"),
    which does not equal tmp_path / "creds-file".
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("S3_CREDENTIALS_PATH", "~/creds-file")
    assert creds_mod._default_credentials_path() == tmp_path / "creds-file"


# ---------------------------------------------------------------------------
# F-4.2-A-03: a failed write-back after a successful server-side rotation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_and_store_reports_session_lost_never_a_raw_oserror(monkeypatch, tmp_path) -> None:
    """A failed store() after a SUCCESSFUL rotation must be reported as
    what it is (the session was rotated and could not be saved, re-login
    required), never as a raw OSError, and must leave a recovery copy of
    the NEW token rather than losing it outright.

    Mutation: remove the try/except around store() in _refresh_and_store
    -> `pytest.raises(SessionLostError)` below would need to become
    `pytest.raises(OSError)`, which is exactly the F-4.2-A-03 reproduction
    this test pins against.
    """
    _point_at(monkeypatch, tmp_path)
    creds_mod.store(creds_mod.Credentials(base_url="http://test", access_token="old-a", refresh_token="old-r"))
    starting = creds_mod.load()

    def _failing_store(creds: creds_mod.Credentials) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(creds_mod, "store", _failing_store)

    transport = _refresh_transport({"access_token": "new-a", "refresh_token": "new-r", "token_type": "bearer"})
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        with pytest.raises(creds_mod.SessionLostError) as exc_info:
            await creds_mod._refresh_and_store(client, starting)
    finally:
        await client.aclose()

    assert not isinstance(exc_info.value, OSError)
    message = str(exc_info.value)
    assert "s3 login" in message
    assert "rotated your session" in message

    recovery = creds_mod._recovery_path()
    assert recovery.exists()
    recovered_raw = json.loads(recovery.read_text())
    assert recovered_raw["refresh_token"] == "new-r"


@pytest.mark.asyncio
async def test_a_recovered_token_self_heals_on_the_next_load(monkeypatch, tmp_path) -> None:
    """Continuation of the above: the NEXT invocation's load() must pick
    up the recovery copy automatically rather than replaying the dead old
    token, which is what actually bounds the data loss rather than merely
    reporting it.

    Mutation: make _promote_recovery_copy_if_present a no-op -> the final
    assertion would see the stale "old-r" token instead of "new-r".
    """
    _point_at(monkeypatch, tmp_path)
    creds_mod.store(creds_mod.Credentials(base_url="http://test", access_token="old-a", refresh_token="old-r"))
    starting = creds_mod.load()

    real_store = creds_mod.store
    calls = {"n": 0}

    def _fail_once_then_real(creds: creds_mod.Credentials) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError(28, "No space left on device")
        real_store(creds)

    monkeypatch.setattr(creds_mod, "store", _fail_once_then_real)

    transport = _refresh_transport({"access_token": "new-a", "refresh_token": "new-r", "token_type": "bearer"})
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        with pytest.raises(creds_mod.SessionLostError):
            await creds_mod._refresh_and_store(client, starting)
    finally:
        await client.aclose()

    # Simulates the NEXT `s3` invocation: a fresh load() call self-heals by
    # promoting the recovery file, rather than replaying "old-r".
    assert creds_mod.load().refresh_token == "new-r"
    assert not creds_mod._recovery_path().exists()


@pytest.mark.asyncio
async def test_refresh_and_store_reports_when_recovery_write_also_fails(monkeypatch, tmp_path) -> None:
    """The stated remaining window: if the recovery write ALSO fails, the
    token really is lost from this process, and the message must say so
    plainly rather than implying a recovery happened.
    """
    _point_at(monkeypatch, tmp_path)
    creds_mod.store(creds_mod.Credentials(base_url="http://test", access_token="old-a", refresh_token="old-r"))
    starting = creds_mod.load()

    def _failing_store(creds: creds_mod.Credentials) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(creds_mod, "store", _failing_store)
    monkeypatch.setattr(creds_mod, "_write_recovery_copy", lambda creds: False)

    transport = _refresh_transport({"access_token": "new-a", "refresh_token": "new-r", "token_type": "bearer"})
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        with pytest.raises(creds_mod.SessionLostError, match="recovery write also failed"):
            await creds_mod._refresh_and_store(client, starting)
    finally:
        await client.aclose()

    assert not creds_mod._recovery_path().exists()


@pytest.mark.asyncio
async def test_refresh_and_store_catches_a_keyboardinterrupt_during_store(monkeypatch, tmp_path) -> None:
    """The second reproduction in F-4.2-A-03: a KeyboardInterrupt at the
    exact instant store() is writing must not escape uncaught with an
    empty stderr; it must be reported the same way an OSError is.

    Mutation: catch only OSError in _refresh_and_store (drop
    KeyboardInterrupt from the tuple) -> this would raise a raw
    KeyboardInterrupt instead of SessionLostError.
    """
    _point_at(monkeypatch, tmp_path)
    creds_mod.store(creds_mod.Credentials(base_url="http://test", access_token="old-a", refresh_token="old-r"))
    starting = creds_mod.load()

    def _interrupted_store(creds: creds_mod.Credentials) -> None:
        raise KeyboardInterrupt()

    monkeypatch.setattr(creds_mod, "store", _interrupted_store)

    transport = _refresh_transport({"access_token": "new-a", "refresh_token": "new-r", "token_type": "bearer"})
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        with pytest.raises(creds_mod.SessionLostError, match="s3 login"):
            await creds_mod._refresh_and_store(client, starting)
    finally:
        await client.aclose()

    assert creds_mod._recovery_path().exists()


def test_write_recovery_copy_is_mode_600(monkeypatch, tmp_path) -> None:
    _point_at(monkeypatch, tmp_path)
    ok = creds_mod._write_recovery_copy(
        creds_mod.Credentials(base_url="u", access_token="a", refresh_token="r")
    )
    assert ok is True
    recovery = creds_mod._recovery_path()
    assert stat.S_IMODE(os.stat(recovery).st_mode) == 0o600


# ---------------------------------------------------------------------------
# F-4.2-A-11: unbounded wait on the refresh lock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_lock_times_out_on_a_foreign_holder(monkeypatch, tmp_path) -> None:
    """A foreign flock holder must not hang refresh_locked forever.
    Bounded via a monkeypatched short ceiling so the test itself stays
    fast; the production value is REFRESH_TIMEOUT_SECONDS + 5s.

    Mutation: revert to a plain blocking LOCK_EX with no NB/poll/deadline
    -> this test would hang instead of raising within its own timeout,
    exactly the F-4.2-A-11 defect (verified by running this test with the
    fix reverted: it hangs past pytest's default collection, whereas with
    the fix it completes in well under a second).
    """
    import fcntl

    _point_at(monkeypatch, tmp_path)
    creds_mod.store(creds_mod.Credentials(base_url="http://test", access_token="old-a", refresh_token="old-r"))
    starting = creds_mod.load()
    monkeypatch.setattr(creds_mod, "REFRESH_LOCK_WAIT_TIMEOUT_SECONDS", 0.3)
    monkeypatch.setattr(creds_mod, "_LOCK_POLL_INTERVAL_SECONDS", 0.02)

    lock_path = creds_mod._lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    foreign_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(foreign_fd, fcntl.LOCK_EX)

    transport = _refresh_transport({"access_token": "x", "refresh_token": "y", "token_type": "bearer"})
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        with pytest.raises(creds_mod.RefreshLockTimeoutError, match="did not release"):
            await creds_mod.refresh_locked(client, starting)
    finally:
        await client.aclose()
        fcntl.flock(foreign_fd, fcntl.LOCK_UN)
        os.close(foreign_fd)


@pytest.mark.asyncio
async def test_refresh_lock_wait_ceiling_exceeds_the_refresh_timeout(monkeypatch, tmp_path) -> None:
    """The lock's own docstring and the module-level comment both claim
    the wait ceiling is set ABOVE REFRESH_TIMEOUT_SECONDS, never below it,
    so a legitimate holder mid-refresh is never evicted early. Assert the
    relationship directly rather than only trusting the comment (the
    self-eval-loop lesson: a comment asserting a property is a claim to
    test, not documentation)."""
    assert creds_mod.REFRESH_LOCK_WAIT_TIMEOUT_SECONDS > creds_mod.REFRESH_TIMEOUT_SECONDS


@pytest.mark.asyncio
async def test_refresh_lock_at_mode_000_reports_actionably_not_a_raw_permission_error(
    monkeypatch, tmp_path
) -> None:
    """F-4.2-A-13's lock-file-at-mode-000 case: os.open on an unreadable,
    unwritable lock file raises PermissionError. Must surface as
    RefreshLockUnavailableError with a clear message, not the raw
    PermissionError.
    """
    if hasattr(os, "getuid") and os.getuid() == 0:
        pytest.skip("permission checks do not apply when running as root")

    _point_at(monkeypatch, tmp_path)
    creds_mod.store(creds_mod.Credentials(base_url="u", access_token="a", refresh_token="r"))
    starting = creds_mod.load()

    lock_path = creds_mod._lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch()
    os.chmod(lock_path, 0o000)

    transport = _refresh_transport({"access_token": "x", "refresh_token": "y", "token_type": "bearer"})
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        with pytest.raises(creds_mod.RefreshLockUnavailableError, match="permission denied"):
            await creds_mod.refresh_locked(client, starting)
    finally:
        await client.aclose()
        os.chmod(lock_path, 0o600)


@pytest.mark.asyncio
async def test_refresh_lock_refuses_a_symlinked_lock_path(monkeypatch, tmp_path) -> None:
    """F-4.2-A-17: the lock path must not be opened through a symlink,
    since O_CREAT with no O_NOFOLLOW would create and lock whatever
    arbitrary file the symlink points at.
    """
    _point_at(monkeypatch, tmp_path)
    creds_mod.store(creds_mod.Credentials(base_url="u", access_token="a", refresh_token="r"))
    starting = creds_mod.load()

    lock_path = creds_mod._lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    target = lock_path.parent / "elsewhere-target"
    target.touch()
    lock_path.symlink_to(target)

    transport = _refresh_transport({"access_token": "x", "refresh_token": "y", "token_type": "bearer"})
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        with pytest.raises(creds_mod.RefreshLockUnavailableError, match="symlink"):
            await creds_mod.refresh_locked(client, starting)
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# F-4.2-A-13 / F-4.2-A-22 / F-4.2-A-30: corrupt or malformed credential files
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "content",
    [
        "",
        "{",
        "[1, 2, 3]",
        '{"base_url": "u"}',
        '{"base_url": null, "refresh_token": "r"}',
        '{"base_url": "u", "refresh_token": 123}',
    ],
    ids=[
        "empty-file",
        "truncated-json",
        "json-array-not-object",
        "missing-refresh-token",
        "base-url-wrong-type",
        "refresh-token-wrong-type",
    ],
)
def test_load_reports_corrupt_credentials_actionably_never_a_raw_internal_error(
    monkeypatch, tmp_path, content
) -> None:
    """Every unreadable-or-malformed shape gets one clear
    CorruptCredentialsError naming the remedy, never a bare
    JSONDecodeError, TypeError, or KeyError leaking to the caller.

    Mutation: read `raw["base_url"]` etc. directly with no isinstance/key
    validation -> the empty-file and truncated-json cases would raise
    JSONDecodeError, the json-array case would raise TypeError, and the
    missing-key case would raise KeyError, each a bare internal error
    instead of CorruptCredentialsError.
    """
    _point_at(monkeypatch, tmp_path)
    path = creds_mod.CREDENTIALS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd = os.open(str(path), os.O_CREAT | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(content)

    with pytest.raises(creds_mod.CorruptCredentialsError, match="s3 login"):
        creds_mod.load()


def test_load_on_a_directory_reports_the_real_problem_not_chmod_advice(monkeypatch, tmp_path) -> None:
    """F-4.2-A-22: when CREDENTIALS_PATH is a directory, its mode
    (typically 0o700) has the owner-execute bit set, which the old "wider
    than 600" check would trip, producing nonsense advice ("chmod 600
    <dir>" makes a directory unusable). Must instead say plainly that it
    is not a regular file.

    Mutation: check mode before checking S_ISREG -> the assertion below
    would see "InsecureCredentialsError" with "chmod 600" advice instead
    of "CorruptCredentialsError" naming "a directory".
    """
    _point_at(monkeypatch, tmp_path)
    creds_mod.CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(creds_mod.CREDENTIALS_PATH.parent, 0o700)
    creds_mod.CREDENTIALS_PATH.mkdir()
    os.chmod(creds_mod.CREDENTIALS_PATH, 0o700)

    with pytest.raises(creds_mod.CorruptCredentialsError, match="a directory") as exc_info:
        creds_mod.load()
    assert "chmod 600" not in str(exc_info.value)


def test_load_refuses_a_symlinked_credentials_path(monkeypatch, tmp_path) -> None:
    """The TOCTOU fix (os.open + O_NOFOLLOW, fstat instead of a separate
    os.stat-then-open) means a credentials path that is itself a symlink
    is refused outright: the descriptor this function checks and the one
    it reads from must always be the same underlying file.
    """
    _point_at(monkeypatch, tmp_path)
    path = creds_mod.CREDENTIALS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    target = path.parent / "elsewhere"
    target.write_text('{"base_url": "u", "access_token": "a", "refresh_token": "r"}')
    os.chmod(target, 0o600)
    path.symlink_to(target)

    with pytest.raises(creds_mod.CorruptCredentialsError, match="symlink"):
        creds_mod.load()


# ---------------------------------------------------------------------------
# F-4.2-A-18 / J-4.2-10: the parent directory's mode is never checked
# ---------------------------------------------------------------------------


def test_load_refuses_a_group_writable_pre_existing_parent_directory(monkeypatch, tmp_path) -> None:
    """A pre-existing, group-writable parent directory must be refused,
    not silently trusted: it lets another local account replace the
    credential file outright, defeating the mode-600 file check entirely.

    Mutation: drop the _ensure_parent_dir_secure call from load() -> this
    would silently read through the wide directory instead of raising.
    """
    _point_at(monkeypatch, tmp_path)
    creds_mod.store(creds_mod.Credentials(base_url="u", access_token="a", refresh_token="r"))
    parent = creds_mod.CREDENTIALS_PATH.parent
    os.chmod(parent, 0o770)

    with pytest.raises(creds_mod.InsecureCredentialsError, match="chmod 700"):
        creds_mod.load()


def test_store_refuses_an_other_writable_pre_existing_parent_directory(monkeypatch, tmp_path) -> None:
    """The same refusal on the write path: store() previously narrowed or
    checked the parent's mode only when IT created the directory, leaving
    a pre-existing wide directory untouched (F-4.2-A-18).
    """
    _point_at(monkeypatch, tmp_path)
    parent = creds_mod.CREDENTIALS_PATH.parent
    parent.mkdir(parents=True)
    os.chmod(parent, 0o707)

    with pytest.raises(creds_mod.InsecureCredentialsError, match="chmod 700"):
        creds_mod.store(creds_mod.Credentials(base_url="u", access_token="a", refresh_token="r"))


def test_ensure_parent_dir_secure_accepts_mode_700(monkeypatch, tmp_path) -> None:
    """No false positive: a properly narrow 0700 parent must not be
    refused."""
    _point_at(monkeypatch, tmp_path)
    parent = creds_mod.CREDENTIALS_PATH.parent
    parent.mkdir(parents=True)
    os.chmod(parent, 0o700)

    creds_mod._ensure_parent_dir_secure(parent)  # must not raise


# ---------------------------------------------------------------------------
# The raiser/catcher seam: every exception this module raises shares one
# base, so a single `except CredentialsError` in main.py is structurally
# sufficient. This is the fourth instance of the seam defect in this phase
# (F-4.2-08, J-4.2-02, F-4.2-A-05), and this test is the fix, not the
# exception classes alone: it is what actually stops a fifth instance,
# because it fails the moment a new exception type is added without
# deriving from CredentialsError.
# ---------------------------------------------------------------------------


def test_every_exception_class_in_this_module_derives_from_credentials_error() -> None:
    """Enumerate every exception class credentials.py actually defines,
    rather than hand-listing the six known today, so a seventh type added
    later is caught automatically without this test being edited.

    Mutation: add a new exception class to credentials.py that derives
    from `Exception` directly instead of `CredentialsError` -> this test
    fails immediately, which is the whole point: a catcher written today
    against `except CredentialsError` would otherwise silently stop
    covering the new type, exactly repeating F-4.2-08 / J-4.2-02 /
    F-4.2-A-05 a fourth time.
    """
    import inspect

    module_exception_classes = [
        obj
        for obj in vars(creds_mod).values()
        if inspect.isclass(obj)
        and issubclass(obj, BaseException)
        and obj.__module__ == creds_mod.__name__
    ]

    assert module_exception_classes, "no exception classes found in the credentials module"
    non_base = [cls for cls in module_exception_classes if cls is not creds_mod.CredentialsError]
    assert non_base, "expected at least one exception class besides the base itself"

    for cls in non_base:
        assert issubclass(cls, creds_mod.CredentialsError), (
            f"{cls.__name__} does not derive from CredentialsError, so "
            f"`except CredentialsError` in main.py would miss it"
        )


def test_credentials_error_exposes_remedy_without_reaching_into_a_subclass() -> None:
    """The base's `remedy` attribute is what lets a catcher render an
    actionable message for any of the six subclasses without a per-type
    mapping. Assert it against the base type directly, not a specific
    subclass, since that genericity is the point of the fix.
    """
    exc = creds_mod.CorruptCredentialsError("something is wrong", remedy="Run: s3 login")
    assert isinstance(exc, creds_mod.CredentialsError)
    assert exc.remedy == "Run: s3 login"
    assert "Run: s3 login" in str(exc)
    assert "something is wrong" in str(exc)


@pytest.mark.parametrize(
    "cls",
    [
        creds_mod.InsecureCredentialsError,
        creds_mod.RefreshError,
        creds_mod.SessionLostError,
        creds_mod.CorruptCredentialsError,
        creds_mod.RefreshLockTimeoutError,
        creds_mod.RefreshLockUnavailableError,
    ],
)
def test_each_known_subclass_is_catchable_as_credentials_error(cls) -> None:
    """Direct proof that `except CredentialsError` (the fix main.py is
    meant to use) actually catches each of the six named types, not just
    that they share a base in the abstract.
    """
    caught = None
    try:
        raise cls("explanation text", remedy="remedy text")
    except creds_mod.CredentialsError as exc:
        caught = exc
    assert caught is not None
    assert isinstance(caught, cls)
