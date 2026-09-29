"""An agent that only runs commands can connect: `s3 mcp` over real stdio.

Build phase 8.10, T-8.10-04, the acceptance line "A test drives `s3 mcp` over
stdio with the MCP SDK's client: initialize, list tools, and call a tool
against a stand-in server."

Three real pieces, nothing mocked between them:

    - The MCP SDK's own stdio client, the one agents built on the SDK use,
      starts `python -m system_03_search_agent.adapters.cli.main mcp` as a
      child process and speaks MCP to it over its stdin and stdout.
    - That child is the real `s3 mcp`, reading a real credential file.
    - The stand-in remote is a real MCP SDK server (`MCPServer`, the class
      `adapters/mcp/server.py` uses), served by uvicorn on a loopback port in
      stateless streamable HTTP mode, as the deployed `/mcp/` mount is. Its
      two tools have names the bridge has never seen, and a tool call without
      the stored token is refused, as the real server refuses one.

The unit suite blocks outbound HTTP inside the test process
(`tests/conftest.py`). Nothing here makes an outbound call from it: the child
process makes the calls, to a server on 127.0.0.1 that this process serves.
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn

# Plain imports, never `importorskip`: the MCP SDK and uvicorn are the
# server's own dependencies, always installed where this suite runs, and a
# missing one must fail loudly rather than skip the acceptance test.
from mcp.client import session as mcp_client_session
from mcp.client import stdio as mcp_client_stdio
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError

SRC = Path(__file__).resolve().parents[4] / "src"


def _jwt(expires_in_s: float) -> str:
    def part(value: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    return ".".join([part({"alg": "HS256"}), part({"exp": int(time.time() + expires_in_s)}), "sig"])


TOKEN = _jwt(3600)


def _stand_in_server(seen_authorization: list[str | None]) -> MCPServer:
    server = MCPServer(name="stand-in-remote", version="0.0.1")

    def check(ctx: Context) -> None:
        headers = ctx.headers
        value = headers.get("authorization") if headers is not None else None
        seen_authorization.append(value)
        if value != f"Bearer {TOKEN}":
            raise MCPError(
                code=-32600,
                message="invalid bearer token",
                data={"reason": "sign_in_refused"},
            )

    @server.tool(description="A tool name the bridge has never seen.")
    async def stand_in_lookup(term: str, ctx: Context) -> str:
        check(ctx)
        return f"stand-in looked up {term}"

    @server.tool(description="A second tool, to show every tool is offered.")
    async def stand_in_second(ctx: Context) -> str:
        check(ctx)
        return "second"

    return server


class _ServedInAThread:
    """uvicorn on 127.0.0.1, an ephemeral port, in a daemon thread."""

    def __init__(self, app: object) -> None:
        self.server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning", lifespan="on")
        )
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self) -> str:
        self.thread.start()
        deadline = time.time() + 15
        while not self.server.started:
            if time.time() > deadline or not self.thread.is_alive():
                raise RuntimeError("the stand-in MCP server did not start")
            time.sleep(0.05)
        port = self.server.servers[0].sockets[0].getsockname()[1]
        return f"http://127.0.0.1:{port}"

    def __exit__(self, *exc_info: object) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=15)


def _credential_file(tmp_path: Path, base_url: str) -> Path:
    directory = tmp_path / "s3home"
    directory.mkdir(mode=0o700)
    path = directory / "credentials"
    path.write_text(
        json.dumps({"base_url": base_url, "access_token": TOKEN, "refresh_token": "r"}) + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


@pytest.mark.asyncio
async def test_an_agent_on_the_mcp_sdk_can_initialize_list_and_call_through_s3_mcp(
    tmp_path: Path,
) -> None:
    # Mutations that turn this red, each checked while building 8.10:
    #   - write anything but JSON-RPC to stdout (for example the startup line)
    #     -> the SDK client reports a parse failure to `message_handler`. It
    #     does not stop the session, which is why the handler is recorded
    #     and asserted empty rather than trusted to crash the test;
    #   - drop the Authorization header in `mcp_bridge._post` -> the stand-in
    #     refuses the call and `is_error` is True;
    #   - hard-code the tool list -> the stand-in's names are missing.
    seen_authorization: list[str | None] = []
    server = _stand_in_server(seen_authorization)
    app = server.streamable_http_app(
        stateless_http=True,
        streamable_http_path="/mcp/",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    with _ServedInAThread(app) as base_url:
        credentials_path = _credential_file(tmp_path, base_url)
        params = mcp_client_stdio.StdioServerParameters(
            command=sys.executable,
            args=["-m", "system_03_search_agent.adapters.cli.main", "mcp"],
            env={"PYTHONPATH": str(SRC), "S3_CREDENTIALS_PATH": str(credentials_path)},
            cwd=str(tmp_path),
        )
        stderr_log = (tmp_path / "s3_mcp_stderr.log").open("w+", encoding="utf-8")

        transport_faults: list[Exception] = []

        async def record(message: object) -> None:
            if isinstance(message, Exception):
                transport_faults.append(message)

        async def drive() -> tuple[object, object, object, object]:
            async with (
                mcp_client_stdio.stdio_client(params, errlog=stderr_log) as (read, write),
                mcp_client_session.ClientSession(read, write, message_handler=record) as session,
            ):
                initialized = await session.initialize()
                listed = await session.list_tools()
                called = await session.call_tool("stand_in_lookup", {"term": "BRCA1"})
                second = await session.call_tool("stand_in_second", {})
                return initialized, listed, called, second

        try:
            initialized, listed, called, second = await asyncio.wait_for(drive(), timeout=60)
        finally:
            stderr_log.seek(0)
            log = stderr_log.read()
            stderr_log.close()

    # stdout carried JSON-RPC and nothing else.
    assert transport_faults == []
    assert initialized.server_info.name == "stand-in-remote"
    assert sorted(tool.name for tool in listed.tools) == ["stand_in_lookup", "stand_in_second"]
    assert called.is_error is False, called
    assert called.content[0].text == "stand-in looked up BRCA1"
    assert second.content[0].text == "second"
    # Every tool call reached the stand-in carrying the stored sign-in.
    assert seen_authorization and all(v == f"Bearer {TOKEN}" for v in seen_authorization)
    # The log a host shows a person says where messages go, and never the token.
    assert f"forwarding MCP messages to {base_url}/mcp/" in log
    assert TOKEN not in log
