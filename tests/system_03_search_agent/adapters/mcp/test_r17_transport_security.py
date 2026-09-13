"""R17: which `Host` headers the `/mcp` surface admits, and what refuses one.

Fix set 5 item 5.3, `testing/UI_fix_plan.md`. Checked live on develop on
2026-09-12: every request to the deployed MCP endpoint came back `421
Invalid Host header`, signed in or not, because `mcp==2.0.0`'s
`streamable_http_app()` auto-enables DNS-rebinding protection with a
LOCALHOST-ONLY allowlist whenever `transport_security` is left None and
`host` is left at its default `127.0.0.1`
(`mcp/server/lowlevel/server.py` lines 739 to 745). The fix configures the
allowlist from `MCP_ALLOWED_HOSTS` and keeps the protection on.

WHY THE EXISTING MCP GATES COULD NOT CATCH THIS, which is the reason this
file exists rather than a few more arms bolted onto
`test_phase_4_1_premise.py`: every one of them drives the surface at
`_BASE_URL = "http://localhost:8000"`, and `localhost:*` is the first
entry in the allowlist the SDK builds. They were green throughout. That
file's own module docstring even describes the auto-enable behaviour and
explains that the base URL has to carry a port because of it, so the
mechanism was understood here and never followed through to the deployment.
The arms below are the first in this repository to send a Host header that
is not a localhost form.

THE ARMS, and what each one would catch:

  Arm 1, the defect itself. A public Host header is refused with the SDK's
  own 421 when the variable is unset, which is also the fail-closed
  default: a deployment that forgets `MCP_ALLOWED_HOSTS` is refused rather
  than opened to every hostname.

  Arm 2, localhost still works unset. Guards the fix against breaking
  local development and every existing MCP test.

  Arm 3, the fix. With `MCP_ALLOWED_HOSTS` set to the deployed hostname,
  the same request reaches the real MCP handler: a full `initialize` round
  trip comes back naming this server. Reaching the handler is the property
  under test, so the proof has to be a result the handler produced, not a
  200.

  Arm 4, the fix is an allowlist and not an off switch. An unlisted third
  host is still refused while the configured one passes. Without this arm
  a change that disabled the protection entirely, or that allowed every
  host, would pass arms 1 to 3 and this whole file would certify it.

  Arm 5, a malformed value fails loudly. Parametrized over the shapes an
  operator actually mistypes. A bare `*` is included deliberately: the SDK
  matches a wildcard only as a `host:*` port suffix, so `*` allows NOTHING
  while reading as "allow everything", and it fails closed and silent,
  which is this very defect again with the variable apparently set.

  Arm 6, the PRODUCTION mount is wired to the setting. Arms 1 to 5 all
  build a fresh sub-app, so on their own they prove the settings function
  works and prove nothing about the line that ships. This arm imports
  `adapters/web_sse/app.py` in a SUBPROCESS with a distinctive
  `MCP_ALLOWED_HOSTS` and reads the allowlist back off the shipped
  `_mcp_asgi_app`. The subprocess is not ceremony: the value has to be in
  the environment before that module-level line runs, and the arm has to
  be able to distinguish wired from unwired, which under an unset variable
  it cannot, since the SDK's auto-enable branch produces byte-identical
  settings to the unset default this function returns. A distinctive host
  is the only thing the two paths disagree about.

  Arm 7, the malformed value stops the real process. Same subprocess, a
  malformed value, asserting the import itself fails and names the
  variable. Arm 5 proves the function raises; this proves nothing
  downstream catches it and serves anyway.

WHAT THIS FILE DOES NOT COVER, stated here because `goal-contracts.md`
requires a verify surface to declare its own gaps:

  - The `Origin` allowlist. `MCP_ALLOWED_ORIGINS` is parsed and validated
    by the same arms in arm 5, but no arm sends an `Origin` header,
    because the SDK allows an absent Origin through and no MCP client in
    this repository sends one. A browser-based caller is untested.
  - Whether the DEPLOYED value is correct. These arms prove the mechanism
    honours whatever hostname it is given. Only setting the variable on
    Railway and re-probing the live URL proves the deployment is fixed.
  - The auth path. Every arm here is refused or admitted BEFORE
    authentication, which is the whole point of the defect, so nothing
    below carries a bearer token and nothing below says anything about
    who may call the tool.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

import httpx2
import pytest
from fastapi import FastAPI
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from system_03_search_agent.adapters.mcp import server as mcp_module

# Imported as ONE module rather than as five names. The aliased-plus-plain
# form (`import server as mcp_server` next to `import transport_security_
# settings` from the same module) is the one shape ruff's I001 and isort
# genuinely disagree about here, and `pyproject.toml` already carries two
# per-file isort skips for exactly that conflict. A third skip would widen a
# deliberate exception to buy nothing, so the shape both tools accept is
# used instead.
_MCPTransportSecurityConfigError = mcp_module.MCPTransportSecurityConfigError
_SDK_DEFAULT_ALLOWED_HOSTS = mcp_module._SDK_DEFAULT_ALLOWED_HOSTS
_SDK_DEFAULT_ALLOWED_ORIGINS = mcp_module._SDK_DEFAULT_ALLOWED_ORIGINS
_mcp_server = mcp_module.server
_transport_security_settings = mcp_module.transport_security_settings

# The live develop API hostname, the one measured refusing every request on
# 2026-09-12. A real value rather than an invented example, so this arm
# fails if the SDK's matcher ever stops handling the shape this deployment
# actually has (a long multi-label name with digits and hyphens).
_DEVELOP_HOST = "search-agent-api-develop-43b3.up.railway.app"

# A host that is never configured by any arm below. Arm 4's control.
_UNLISTED_HOST = "unlisted.example.test"

_LOCALHOST = "localhost:8000"

_SRC = str(Path(__file__).resolve().parents[4] / "src")

_INITIALIZE_BODY = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "r17-transport-security-test", "version": "0.0.0"},
    },
}


def _build_mcp_app() -> FastAPI:
    """Mount the real `MCPServer` singleton with the production recipe.

    The same recipe `adapters/web_sse/app.py` ships and the same reason
    `test_phase_4_1_premise.py`'s `_build_test_mcp_app` builds it fresh per
    call: `streamable_http_app()` makes a new
    `StreamableHTTPSessionManager` each time and that manager's `run()` may
    be entered only once for its lifetime, so a shared instance cannot
    serve many independent tests. The one difference from that helper is
    the argument this whole file is about, `transport_security=`, read
    fresh from the environment on every call.
    """
    sub_app = _mcp_server.streamable_http_app(
        stateless_http=True,
        streamable_http_path="/",
        transport_security=_transport_security_settings(),
    )

    @asynccontextmanager
    async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(sub_app.router.lifespan_context(sub_app))
            yield

    app = FastAPI(lifespan=_lifespan)
    app.mount("/mcp", sub_app)
    return app


async def _post_initialize(host: str) -> httpx2.Response:
    """Send the MCP `initialize` request with `host` in the Host header.

    A raw POST rather than the SDK client, because the refusal arms need
    the status code and body the middleware returned; the SDK client turns
    a 421 into an exception that says nothing about which check refused it.
    `follow_redirects=True` is required: the sub-app mounts at `/mcp` with
    its route at `/`, so a bare `POST /mcp` 307s first.
    """
    app = _build_mcp_app()
    async with (
        app.router.lifespan_context(app),
        httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            base_url="http://" + host,
            follow_redirects=True,
        ) as client,
    ):
        return await client.post(
            "/mcp/",
            json=_INITIALIZE_BODY,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )


def _import_app_in_subprocess(allowed_hosts: str) -> subprocess.CompletedProcess[str]:
    """Import the shipped `app` module with `MCP_ALLOWED_HOSTS` set.

    Prints the allowlist the production `_mcp_asgi_app` was actually built
    with, prefixed so the arm reads one line rather than parsing the SDK's
    own startup logging out of the stream.
    """
    program = (
        "from system_03_search_agent.adapters.web_sse.app import _mcp_asgi_app\n"
        "settings = _mcp_asgi_app.routes[0].endpoint.session_manager.security_settings\n"
        "print('R17_SETTINGS=' + __import__('json').dumps({\n"
        "    'protection': settings.enable_dns_rebinding_protection,\n"
        "    'hosts': settings.allowed_hosts,\n"
        "}))\n"
    )
    return subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        # A non-zero exit is the expected outcome of arm 7, so the caller
        # inspects `returncode` itself rather than letting this raise.
        check=False,
        timeout=180,
        env={
            "PATH": "/usr/bin:/bin",
            "PYTHONPATH": _SRC,
            "MCP_ALLOWED_HOSTS": allowed_hosts,
        },
    )


class TestUnsetFailsClosed:
    """Arms 1 and 2: the default admits localhost and refuses a public host."""

    @pytest.mark.asyncio
    async def test_a_public_host_is_refused_with_the_sdk_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
        monkeypatch.delenv("MCP_ALLOWED_ORIGINS", raising=False)

        response = await _post_initialize(_DEVELOP_HOST)

        # Pinned to the SDK's own literals (`transport_security.py` line
        # 109), not to "some 4xx": a different refusal would mean a
        # different control fired and this arm would be measuring the wrong
        # thing while still going green.
        assert response.status_code == 421
        assert response.text == "Invalid Host header"

    @pytest.mark.asyncio
    async def test_localhost_is_still_admitted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
        monkeypatch.delenv("MCP_ALLOWED_ORIGINS", raising=False)

        response = await _post_initialize(_LOCALHOST)

        assert response.status_code == 200

    def test_the_unset_default_is_the_sdks_own_localhost_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The fail-closed default, read straight off the settings object.

        Separate from the two HTTP arms above because those prove the
        BEHAVIOUR and this pins the VALUE. Without it, a fix that admitted
        localhost by admitting everything would pass both of them.
        """
        monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
        monkeypatch.delenv("MCP_ALLOWED_ORIGINS", raising=False)

        settings = _transport_security_settings()

        assert settings.enable_dns_rebinding_protection is True
        assert settings.allowed_hosts == list(_SDK_DEFAULT_ALLOWED_HOSTS)
        assert settings.allowed_origins == list(_SDK_DEFAULT_ALLOWED_ORIGINS)


class TestConfiguredHostReachesTheHandler:
    """Arm 3: the configured host reaches the real MCP handler."""

    @pytest.mark.asyncio
    async def test_an_initialize_round_trip_returns_this_servers_info(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A full SDK `initialize`, not a 200, is the proof.

        A 200 says the middleware let the request through. `serverInfo.name`
        says the request reached the registered `MCPServer` singleton and
        that singleton answered, which is what "passes to the MCP handler"
        means.
        """
        monkeypatch.setenv("MCP_ALLOWED_HOSTS", _DEVELOP_HOST)
        monkeypatch.delenv("MCP_ALLOWED_ORIGINS", raising=False)

        app = _build_mcp_app()
        base_url = "http://" + _DEVELOP_HOST
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app),
                base_url=base_url,
                follow_redirects=True,
            ) as http_client,
            streamable_http_client(base_url + "/mcp", http_client=http_client) as (read, write),
            ClientSession(read, write) as session,
        ):
            result = await session.initialize()

        assert result.server_info.name == "system3-biomedical-search"

    @pytest.mark.asyncio
    async def test_a_port_and_a_wildcard_port_both_resolve(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The two Host spellings do not cover each other.

        A deployment behind a proxy may or may not see a port in `Host`.
        Railway's edge forwards the bare hostname today, and "today" is not
        a contract. The SDK compares an allowlist entry for equality first
        and only then tries a `:*` suffix, so a bare entry does NOT admit a
        Host carrying a port and a `:*` entry does NOT admit the bare form.
        Pinned as an arm because it is the one way a configuration that
        looks right still 421s.
        """
        monkeypatch.setenv("MCP_ALLOWED_HOSTS", _DEVELOP_HOST + ":*")
        monkeypatch.delenv("MCP_ALLOWED_ORIGINS", raising=False)

        assert (await _post_initialize(_DEVELOP_HOST + ":443")).status_code == 200
        assert (await _post_initialize(_DEVELOP_HOST)).status_code == 421

        monkeypatch.setenv("MCP_ALLOWED_HOSTS", _DEVELOP_HOST)

        assert (await _post_initialize(_DEVELOP_HOST)).status_code == 200
        assert (await _post_initialize(_DEVELOP_HOST + ":443")).status_code == 421

    @pytest.mark.asyncio
    async def test_the_value_env_example_recommends_admits_both_spellings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`env.example` tells an operator to list each hostname twice.

        That advice is only worth giving if it works, and the arm above
        proves each spelling alone is insufficient, so this one proves the
        pair together is sufficient. Without it `env.example` would carry a
        confident sentence about a configuration nothing here had run.
        """
        monkeypatch.setenv("MCP_ALLOWED_HOSTS", _DEVELOP_HOST + "," + _DEVELOP_HOST + ":*")
        monkeypatch.delenv("MCP_ALLOWED_ORIGINS", raising=False)

        assert (await _post_initialize(_DEVELOP_HOST)).status_code == 200
        assert (await _post_initialize(_DEVELOP_HOST + ":443")).status_code == 200
        # Still an allowlist, not an off switch.
        assert (await _post_initialize(_UNLISTED_HOST)).status_code == 421


class TestTheFixIsAnAllowlistNotAnOffSwitch:
    """Arm 4: configuring one host does not admit every host."""

    @pytest.mark.asyncio
    async def test_an_unlisted_host_is_still_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MCP_ALLOWED_HOSTS", _DEVELOP_HOST)
        monkeypatch.delenv("MCP_ALLOWED_ORIGINS", raising=False)

        configured = await _post_initialize(_DEVELOP_HOST)
        unlisted = await _post_initialize(_UNLISTED_HOST)

        assert configured.status_code == 200
        assert unlisted.status_code == 421
        assert unlisted.text == "Invalid Host header"

    def test_protection_stays_enabled_whatever_the_variable_says(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MCP_ALLOWED_HOSTS", _DEVELOP_HOST)
        monkeypatch.setenv("MCP_ALLOWED_ORIGINS", "https://app.example.test")

        settings = _transport_security_settings()

        assert settings.enable_dns_rebinding_protection is True
        assert settings.allowed_hosts == [_DEVELOP_HOST]
        assert settings.allowed_origins == ["https://app.example.test"]


class TestMalformedValuesFailLoudly:
    """Arm 5: a value that is set but unusable raises rather than defaulting."""

    @pytest.mark.parametrize(
        "raw",
        [
            pytest.param("*", id="bare-wildcard-allows-nothing"),
            pytest.param("api.example.test,*", id="wildcard-among-valid-entries"),
            pytest.param("https://api.example.test", id="scheme-in-a-host-value"),
            pytest.param("api.example.test/mcp", id="path-in-a-host-value"),
            pytest.param("api example test", id="whitespace-inside-an-entry"),
            pytest.param("user@api.example.test", id="credentials-in-a-host-value"),
            pytest.param("api.example.test:notaport", id="non-numeric-port"),
            pytest.param(",", id="separators-only"),
            pytest.param(" , , ", id="separators-and-whitespace-only"),
        ],
    )
    def test_a_malformed_host_list_raises(
        self, monkeypatch: pytest.MonkeyPatch, raw: str
    ) -> None:
        monkeypatch.setenv("MCP_ALLOWED_HOSTS", raw)
        monkeypatch.delenv("MCP_ALLOWED_ORIGINS", raising=False)

        with pytest.raises(_MCPTransportSecurityConfigError) as excinfo:
            _transport_security_settings()

        # The message must name the variable, or an operator reading a
        # crashed startup log has to guess which of two similarly named
        # variables they mistyped.
        assert "MCP_ALLOWED_HOSTS" in str(excinfo.value)

    @pytest.mark.parametrize(
        "raw",
        [
            pytest.param("app.example.test", id="origin-without-a-scheme"),
            pytest.param("ftp://app.example.test", id="unsupported-scheme"),
            pytest.param("https://app.example.test/path", id="origin-with-a-path"),
            pytest.param("https://", id="scheme-with-no-host"),
            pytest.param("*", id="bare-wildcard"),
            pytest.param(",", id="separators-only"),
        ],
    )
    def test_a_malformed_origin_list_raises(
        self, monkeypatch: pytest.MonkeyPatch, raw: str
    ) -> None:
        monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
        monkeypatch.setenv("MCP_ALLOWED_ORIGINS", raw)

        with pytest.raises(_MCPTransportSecurityConfigError) as excinfo:
            _transport_security_settings()

        assert "MCP_ALLOWED_ORIGINS" in str(excinfo.value)

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            pytest.param("", ["127.0.0.1:*", "localhost:*", "[::1]:*"], id="empty-is-unset"),
            pytest.param("   ", ["127.0.0.1:*", "localhost:*", "[::1]:*"], id="blank-is-unset"),
            pytest.param("a.example.test,", ["a.example.test"], id="trailing-comma-tolerated"),
            pytest.param(
                "a.example.test,a.example.test", ["a.example.test"], id="duplicate-collapsed"
            ),
            pytest.param(
                " a.example.test , b.example.test ",
                ["a.example.test", "b.example.test"],
                id="surrounding-whitespace-trimmed",
            ),
            pytest.param("[::1]:8000", ["[::1]:8000"], id="bracketed-ipv6-literal"),
            pytest.param("10.0.0.1:8000", ["10.0.0.1:8000"], id="ipv4-with-port"),
        ],
    )
    def test_the_shapes_that_are_accepted(
        self, monkeypatch: pytest.MonkeyPatch, raw: str, expected: list[str]
    ) -> None:
        """The other half of arm 5.

        A validator with no accepted-shape arms is one over-tight regex away
        from rejecting a hostname a deployment genuinely has, and the
        rejection arms above would all still pass.
        """
        monkeypatch.setenv("MCP_ALLOWED_HOSTS", raw)
        monkeypatch.delenv("MCP_ALLOWED_ORIGINS", raising=False)

        assert _transport_security_settings().allowed_hosts == expected


class TestTheProductionMountIsWired:
    """Arms 6 and 7: the shipped `/mcp` mount reads the setting."""

    def test_the_shipped_mount_carries_the_configured_allowlist(self) -> None:
        completed = _import_app_in_subprocess("wired-probe.example.test")

        assert completed.returncode == 0, completed.stderr[-2000:]
        line = next(
            raw for raw in completed.stdout.splitlines() if raw.startswith("R17_SETTINGS=")
        )
        settings = json.loads(line[len("R17_SETTINGS=") :])

        assert settings["protection"] is True
        # The distinguishing assertion. An `app.py` that still passed no
        # `transport_security` would print the SDK's localhost defaults
        # here, so this value cannot be reached by the unwired path.
        assert settings["hosts"] == ["wired-probe.example.test"]

    def test_a_malformed_value_stops_the_process_at_import(self) -> None:
        completed = _import_app_in_subprocess("*")

        assert completed.returncode != 0
        # The class name as the traceback spells it, which has no leading
        # underscore: the underscored names in this file are local aliases,
        # not what the subprocess prints.
        assert "MCPTransportSecurityConfigError" in completed.stderr
        assert "MCP_ALLOWED_HOSTS" in completed.stderr
