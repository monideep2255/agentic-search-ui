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
