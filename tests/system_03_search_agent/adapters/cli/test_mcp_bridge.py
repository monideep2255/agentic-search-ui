"""`s3 mcp`, the local MCP server that forwards to System 3's remote one.

Build phase 8.10, T-8.10-04 (`tracker/phase_8.10.md`). These tests drive the
real `McpBridge` against an in-process stand-in for the remote `/mcp/`
endpoint and `/auth/refresh`, served through `httpx.MockTransport`. The
stand-in answers in both shapes the MCP SDK's streamable HTTP server uses: a
JSON body and an event stream. `test_mcp_bridge_stdio.py` drives the same
code as a real process with the MCP SDK's own client.

What this file covers, one class each:
    - Forwarding: every message reaches the remote with the stored token,
      every tool the remote lists comes back unchanged, whatever its name.
    - Renewal: before expiry, after a refusal, and failing closed.
    - The token never reaches stdout, stderr or an error message.
    - Refusals the bridge makes itself: a redirect, bad JSON, an unreachable
      server, an oversized reply, a server that never answers.
    - Every request gets exactly one answer, whatever the server or the agent
      sends: JSON nested thousands deep, a body that cannot be decoded, a
      failure nobody foresaw (fix round, F-8.10-J01 and A01).
    - The bounds: a reply's size, sized from the server's own schemas; a
      request's total time; JSON-RPC only, in both directions (fix round,
      F-8.10-A04, A06, A07 and J12).
    - Protocol care: ping answered locally, a cancelled request gets no
      reply, stdout carries one ASCII JSON message per line.
    - `s3 mcp` with no sign-in stops before reading a line.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

import system_03_search_agent.adapters.cli.main as main_module
from system_03_search_agent.adapters.cli import credentials, mcp_bridge

BASE = "https://system3.test"
STAND_IN_TOOLS = [
    {"name": "stand_in_alpha", "description": "a tool this file made up", "inputSchema": {"type": "object"}},
    {"name": "stand_in_beta", "description": "another one", "inputSchema": {"type": "object"}},
]


def jwt(expires_in_s: float, marker: str) -> str:
    """A JWT-shaped token. Unsigned: the bridge never verifies one, it only
    reads `exp` to decide when to renew."""

    def part(value: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    return ".".join(
        [part({"alg": "HS256"}), part({"exp": int(time.time() + expires_in_s), "m": marker}), "sig"]
    )


class StandIn:
    """The remote server, as far as the bridge can tell."""

    def __init__(self, *, valid_tokens: set[str], reply_as: str = "json") -> None:
        self.valid_tokens = set(valid_tokens)
        self.reply_as = reply_as
        self.valid_refresh_tokens = {"refresh-1"}
        self.mcp_requests: list[httpx.Request] = []
        self.refresh_calls = 0
        self.issued: list[str] = []
        self.override: Any = None  # a callable(request) -> Response to take over

    def _reply(self, message: dict) -> httpx.Response:
        if self.reply_as == "sse":
            body = f"event: message\ndata: {json.dumps(message)}\n\n".encode()
            return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})
        return httpx.Response(200, json=message)

    async def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/refresh":
            # Yield to the event loop, as a real network call would, so a
            # second request can arrive while this renewal is in flight.
            # `MockTransport` alone never yields, and a concurrency test
            # without this would pass whether or not renewals are shared.
            await asyncio.sleep(0.02)
            self.refresh_calls += 1
            refresh = json.loads(request.content)["refresh_token"]
            if refresh not in self.valid_refresh_tokens:
                return httpx.Response(401, json={"detail": "invalid or expired refresh token"})
            self.valid_refresh_tokens.discard(refresh)
            new_access = jwt(900, f"renewed-{self.refresh_calls}")
            new_refresh = f"refresh-{self.refresh_calls + 1}"
            self.valid_tokens.add(new_access)
            self.valid_refresh_tokens.add(new_refresh)
            self.issued.append(new_access)
            return httpx.Response(200, json={"access_token": new_access, "refresh_token": new_refresh})
        assert request.url.path == "/mcp/", request.url.path
        self.mcp_requests.append(request)
        if self.override is not None:
            return await self.override(request)
        message = json.loads(request.content)
        if "id" not in message:
            return httpx.Response(202)
        method = message.get("method")
        if method == "initialize":
            return self._reply(
                {
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "result": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "system3-biomedical-search", "version": "1.0.0"},
                    },
                }
            )
        if method == "tools/list":
            return self._reply({"jsonrpc": "2.0", "id": message["id"], "result": {"tools": STAND_IN_TOOLS}})
        if method == "tools/call":
            token = request.headers.get("authorization", "").removeprefix("Bearer ")
            if token not in self.valid_tokens:
                return self._reply(
                    {
                        "jsonrpc": "2.0",
                        "id": message["id"],
                        "error": {
                            "code": -32600,
                            "message": "invalid bearer token",
                            "data": {"reason": "sign_in_refused"},
                        },
                    }
                )
            text = f"{message['params']['name']} answered {json.dumps(message['params'].get('arguments'))}"
            return self._reply(
                {
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "result": {"content": [{"type": "text", "text": text}], "isError": False},
                }
            )
        return self._reply({"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32601, "message": "no such method"}})


class Harness:
    def __init__(self, stand_in: StandIn, creds: credentials.Credentials) -> None:
        self.stand_in = stand_in
        self.lines: list[bytes] = []
        self.stderr = io.StringIO()
        self.http = httpx.AsyncClient(transport=httpx.MockTransport(stand_in.handler), base_url=BASE)
        self.bridge = mcp_bridge.McpBridge(
            self.http, creds, write_line=self.lines.append, stderr=self.stderr
        )

    async def send(self, *messages: Any) -> list[dict]:
        for message in messages:
            raw = message if isinstance(message, bytes) else json.dumps(message).encode() + b"\n"
            await self.bridge.handle_line(raw)
            await self.bridge.drain()
        return self.replies()

    def replies(self) -> list[dict]:
        return [json.loads(line) for line in self.lines]

    def output(self) -> str:
        return b"".join(self.lines).decode("ascii") + self.stderr.getvalue()


@pytest.fixture
def signed_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Stores a sign-in in a private credential file and returns a factory
    for the bridge's starting credentials."""
    directory = tmp_path / "s3home"
    directory.mkdir(mode=0o700)
    monkeypatch.setattr(credentials, "CREDENTIALS_PATH", directory / "credentials")

    def make(access_token: str | None) -> credentials.Credentials:
        creds = credentials.Credentials(base_url=BASE, access_token=access_token, refresh_token="refresh-1")
        credentials.store(creds)
        return creds

    return make


def _request(request_id: int, method: str, params: dict | None = None) -> dict:
    message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        message["params"] = params
    return message


INITIALIZE = _request(
    1,
    "initialize",
    {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}},
)
INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}
LIST = _request(2, "tools/list")


def CALL(request_id: int = 3) -> dict:
    return _request(request_id, "tools/call", {"name": "stand_in_alpha", "arguments": {"q": "BRCA1"}})


# ---------------------------------------------------------------------------
# Forwarding
# ---------------------------------------------------------------------------


class TestForwarding:
    @pytest.mark.parametrize("reply_as", ["json", "sse"])
    @pytest.mark.asyncio
    async def test_every_tool_the_remote_lists_is_offered_and_answers(self, signed_in, reply_as) -> None:
        # Mutation: drop the Authorization header in `_post` -> the stand-in
        # refuses the call, renewal cannot fix it, and no result comes back.
        token = jwt(900, "first")
        harness = Harness(StandIn(valid_tokens={token}, reply_as=reply_as), signed_in(token))
        replies = await harness.send(INITIALIZE, INITIALIZED, LIST, CALL())

        assert [r["id"] for r in replies] == [1, 2, 3]
        assert replies[0]["result"]["serverInfo"]["name"] == "system3-biomedical-search"
        assert [t["name"] for t in replies[1]["result"]["tools"]] == ["stand_in_alpha", "stand_in_beta"]
        assert replies[2]["result"]["content"][0]["text"] == 'stand_in_alpha answered {"q": "BRCA1"}'
        sent = harness.stand_in.mcp_requests
        assert all(r.headers["authorization"] == f"Bearer {token}" for r in sent)
        assert all(r.url == httpx.URL(f"{BASE}/mcp/") for r in sent)
        # The version the server agreed to rides on every later request.
        assert "mcp-protocol-version" not in sent[0].headers
        assert all(r.headers["mcp-protocol-version"] == "2025-06-18" for r in sent[1:])
        assert token not in harness.output()

    @pytest.mark.asyncio
    async def test_a_notification_is_forwarded_and_gets_no_reply(self, signed_in) -> None:
        token = jwt(900, "n")
        harness = Harness(StandIn(valid_tokens={token}), signed_in(token))
        assert await harness.send(INITIALIZED) == []
        assert len(harness.stand_in.mcp_requests) == 1


# ---------------------------------------------------------------------------
# Renewal
# ---------------------------------------------------------------------------


class TestRenewal:
    @pytest.mark.asyncio
    async def test_a_token_about_to_expire_is_renewed_before_it_is_sent(self, signed_in) -> None:
        # Mutation: make `_renew_if_expiring` a no-op -> the expiring token is
        # sent, the stand-in refuses it once, and the renewal happens only
        # reactively, so the first tools/call carries the old token.
        expiring = jwt(20, "expiring")
        stand_in = StandIn(valid_tokens=set())  # the expiring token is already refused
        harness = Harness(stand_in, signed_in(expiring))
        replies = await harness.send(CALL())

        assert replies[0]["result"]["isError"] is False
        assert stand_in.refresh_calls == 1
        assert len(stand_in.mcp_requests) == 1
        assert stand_in.mcp_requests[0].headers["authorization"] == f"Bearer {stand_in.issued[0]}"
        stored = credentials.load()
        assert stored.access_token == stand_in.issued[0]
        assert stored.refresh_token == "refresh-2"
        assert expiring not in harness.output()
        assert stand_in.issued[0] not in harness.output()

    @pytest.mark.asyncio
    async def test_a_refused_token_is_renewed_and_the_request_sent_once_more(self, signed_in) -> None:
        # Mutation: return the refusal instead of retrying -> the agent gets
        # the server's "invalid bearer token" error.
        stand_in = StandIn(valid_tokens=set())
        harness = Harness(stand_in, signed_in("an-opaque-token-with-no-expiry"))
        replies = await harness.send(CALL())

        assert len(replies) == 1
        assert replies[0]["result"]["isError"] is False
        assert stand_in.refresh_calls == 1
        assert [r.headers["authorization"] for r in stand_in.mcp_requests] == [
            "Bearer an-opaque-token-with-no-expiry",
            f"Bearer {stand_in.issued[0]}",
        ]

    @pytest.mark.asyncio
    async def test_an_http_401_is_renewed_the_same_way(self, signed_in) -> None:
        stand_in = StandIn(valid_tokens=set())
        calls = 0

        async def first_401(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(401, json={"detail": "expired"})
            stand_in.override = None
            return await stand_in.handler(request)

        stand_in.override = first_401
        harness = Harness(stand_in, signed_in("opaque"))
        replies = await harness.send(CALL())
        assert replies[0]["result"]["isError"] is False
        assert stand_in.refresh_calls == 1

    @pytest.mark.asyncio
    async def test_renewal_that_fails_sends_nothing_and_says_to_sign_in(self, signed_in) -> None:
        # Mutation: catch the refresh failure and send the request anyway ->
        # the expired token reaches the server and a tools/call is recorded.
        expired = jwt(-5, "expired")
        stand_in = StandIn(valid_tokens={expired})
        stand_in.valid_refresh_tokens = set()  # the refresh token was revoked
        harness = Harness(stand_in, signed_in(expired))
        replies = await harness.send(CALL())

        assert stand_in.mcp_requests == []
        assert replies[0]["error"]["code"] == mcp_bridge.SIGN_IN_NEEDED
        assert "s3 login" in replies[0]["error"]["message"]
        assert expired not in harness.output()
        assert "refresh-1" not in harness.output()

    @pytest.mark.asyncio
    async def test_a_renewed_token_refused_again_is_an_error_not_silence(self, signed_in) -> None:
        stand_in = StandIn(valid_tokens=set())

        async def always_refuse(request: httpx.Request) -> httpx.Response:
            message = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "error": {"code": -32600, "message": "invalid bearer token", "data": {"reason": "sign_in_refused"}},
                },
            )

        stand_in.override = always_refuse
        harness = Harness(stand_in, signed_in("opaque"))
        replies = await harness.send(CALL())
        assert len(replies) == 1
        assert replies[0]["error"]["code"] == mcp_bridge.SIGN_IN_NEEDED
        assert len(stand_in.mcp_requests) == 2

    @pytest.mark.asyncio
    async def test_two_requests_at_once_renew_only_once(self, signed_in) -> None:
        """The refresh token rotates on every use, and replaying a used one
        signs the person out everywhere. Two requests that notice the same
        expiry must share one renewal."""
        stand_in = StandIn(valid_tokens=set())
        harness = Harness(stand_in, signed_in(jwt(10, "expiring")))
        for request_id in (11, 12):
            await harness.bridge.handle_line(json.dumps(CALL(request_id)).encode())
        await harness.bridge.drain()
        assert stand_in.refresh_calls == 1
        assert sorted(r["id"] for r in harness.replies()) == [11, 12]
        assert all("result" in r for r in harness.replies())


class TestOnlyTheStructuredFieldMeansSignInRefused:
    """Card 62's fix round, F-62-A06. `s3 mcp` decides the sign-in was
    refused from the INVALID_REQUEST code and `data.reason`, never from the
    message's words. Mutation that turns these red: match "bearer token" in
    the message again, or drop the code check."""

    @pytest.mark.asyncio
    async def test_an_error_that_only_mentions_a_bearer_token_is_passed_on_unchanged(
        self, signed_in
    ) -> None:
        stand_in = StandIn(valid_tokens=set())
        server_error = {"code": -32602, "message": "unknown argument(s): bearer token"}

        async def unknown_argument(request: httpx.Request) -> httpx.Response:
            message = json.loads(request.content)
            return httpx.Response(
                200, json={"jsonrpc": "2.0", "id": message["id"], "error": server_error}
            )

        stand_in.override = unknown_argument
        harness = Harness(stand_in, signed_in("opaque"))
        replies = await harness.send(CALL())
        assert replies == [{"jsonrpc": "2.0", "id": 3, "error": server_error}]
        assert stand_in.refresh_calls == 0
        assert len(stand_in.mcp_requests) == 1
        assert "renewed" not in harness.stderr.getvalue()

    @pytest.mark.parametrize(
        ("error", "refused"),
        [
            ({"code": -32600, "message": "anything at all", "data": {"reason": "sign_in_refused"}}, True),
            ({"code": -32600, "message": "invalid bearer token"}, False),
            ({"code": -32600, "message": "invalid bearer token", "data": {"reason": "other"}}, False),
            ({"code": -32602, "message": "x", "data": {"reason": "sign_in_refused"}}, False),
            ({"code": -32600, "message": "x", "data": "sign_in_refused"}, False),
        ],
    )
    def test_the_decision_reads_structure_not_words(self, error: dict, refused: bool) -> None:
        assert mcp_bridge._is_token_refusal({"jsonrpc": "2.0", "id": 1, "error": error}) is refused


class TestAccessTokenExpiry:
    def test_reads_exp_from_a_jwt(self) -> None:
        token = jwt(100, "x")
        assert abs(mcp_bridge.access_token_expires_at(token) - (time.time() + 100)) < 5

    @pytest.mark.parametrize("token", ["opaque", "a.b", "a.!!!.c", "a.bm90IGpzb24.c"])
    def test_anything_else_has_no_expiry(self, token: str) -> None:
        assert mcp_bridge.access_token_expires_at(token) is None


# ---------------------------------------------------------------------------
# Refusals the bridge makes itself
# ---------------------------------------------------------------------------


class TestTheBridgeRefusesSafely:
    @pytest.mark.asyncio
    async def test_a_redirect_is_never_followed_so_the_token_goes_nowhere_else(self, signed_in) -> None:
        # Mutation: pass `follow_redirects=True` -> a second request, carrying
        # the Authorization header, goes to the other host.
        token = jwt(900, "r")
        stand_in = StandIn(valid_tokens={token})
        seen_hosts: list[str] = []

        async def redirect(request: httpx.Request) -> httpx.Response:
            seen_hosts.append(request.url.host)
            return httpx.Response(307, headers={"location": "https://elsewhere.example/steal"})

        stand_in.override = redirect
        harness = Harness(stand_in, signed_in(token))
        replies = await harness.send(CALL())
        assert seen_hosts == ["system3.test"]
        assert replies[0]["error"]["code"] == mcp_bridge.REMOTE_FAILED
        assert "redirect" in replies[0]["error"]["message"]

    @pytest.mark.asyncio
    async def test_a_line_that_is_not_json_gets_a_parse_error(self, signed_in) -> None:
        harness = Harness(StandIn(valid_tokens=set()), signed_in(jwt(900, "p")))
        replies = await harness.send(b"{this is not json\n")
        assert replies == [
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": replies[0]["error"]["message"]},
            }
        ]
        assert harness.stand_in.mcp_requests == []

    @pytest.mark.asyncio
    async def test_an_unreachable_server_says_to_check_the_network(self, signed_in) -> None:
        stand_in = StandIn(valid_tokens=set())

        async def down(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        stand_in.override = down
        harness = Harness(stand_in, signed_in(jwt(900, "d")))
        replies = await harness.send(CALL())
        assert replies[0]["error"]["code"] == mcp_bridge.REMOTE_UNREACHABLE
        assert "network" in replies[0]["error"]["message"]

    @pytest.mark.asyncio
    async def test_a_reply_past_the_bound_is_not_passed_on(self, signed_in, monkeypatch) -> None:
        monkeypatch.setattr(mcp_bridge, "MAX_REMOTE_REPLY_BYTES", 1000)
        token = jwt(900, "big")
        stand_in = StandIn(valid_tokens={token}, reply_as="sse")

        async def huge(request: httpx.Request) -> httpx.Response:
            message = json.loads(request.content)
            payload = {"jsonrpc": "2.0", "id": message["id"], "result": {"blob": "x" * 5000}}
            return httpx.Response(
                200,
                content=f"data: {json.dumps(payload)}\n\n".encode(),
                headers={"content-type": "text/event-stream"},
            )

        stand_in.override = huge
        harness = Harness(stand_in, signed_in(token))
        replies = await harness.send(CALL())
        assert replies[0]["error"]["code"] == mcp_bridge.REMOTE_FAILED
        assert "larger than" in replies[0]["error"]["message"]
        assert "xxxx" not in harness.output()

    @pytest.mark.asyncio
    async def test_a_server_that_never_answers_still_gets_the_agent_a_reply(self, signed_in) -> None:
        # Mutation: remove the "closed the connection without answering"
        # fallback in `_forward` -> no line at all, and the agent waits forever.
        token = jwt(900, "silent")
        stand_in = StandIn(valid_tokens={token})

        async def silent(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b": keepalive\n\n", headers={"content-type": "text/event-stream"})

        stand_in.override = silent
        harness = Harness(stand_in, signed_in(token))
        replies = await harness.send(CALL(7))
        assert replies[0]["id"] == 7
        assert replies[0]["error"]["code"] == mcp_bridge.REMOTE_FAILED


# ---------------------------------------------------------------------------
# Every request gets exactly one answer, whatever comes back (fix round,
# F-8.10-J01 and A01)
# ---------------------------------------------------------------------------


def _nested(depth: int) -> str:
    return "[" * depth + "]" * depth


def _answers_for(replies: list[dict], request_id: int) -> list[dict]:
    return [r for r in replies if r.get("id") == request_id]


class TestEveryRequestGetsOneAnswer:
    @pytest.mark.parametrize("reply_as", ["json", "sse"])
    @pytest.mark.parametrize("depth", [5000, 100000])
    @pytest.mark.asyncio
    async def test_a_reply_nested_thousands_deep_is_answered_with_an_error(
        self, signed_in, reply_as: str, depth: int
    ) -> None:
        # Mutation: catch only `(UnicodeDecodeError, ValueError)` around the
        # parse again -> `RecursionError` escapes, and the agent gets nothing.
        token = jwt(900, "deep")
        stand_in = StandIn(valid_tokens={token})
        body = '{"jsonrpc":"2.0","id":4,"result":' + _nested(depth) + "}"

        async def deep(request: httpx.Request) -> httpx.Response:
            if reply_as == "sse":
                return httpx.Response(
                    200,
                    content=f"event: message\ndata: {body}\n\n".encode(),
                    headers={"content-type": "text/event-stream"},
                )
            return httpx.Response(200, content=body.encode(), headers={"content-type": "application/json"})

        stand_in.override = deep
        harness = Harness(stand_in, signed_in(token))
        replies = await harness.send(CALL(4))

        assert len(replies) == 1
        assert replies[0]["id"] == 4
        assert replies[0]["error"]["code"] == mcp_bridge.REMOTE_FAILED
        assert "not valid JSON" in replies[0]["error"]["message"]

    @pytest.mark.asyncio
    async def test_a_body_labelled_gzip_that_is_not_gzip_is_answered_with_an_error(
        self, signed_in
    ) -> None:
        # The judge's case: reading the body raises `httpx.DecodingError`,
        # which is neither a `TransportError` nor a `TimeoutException`.
        # Mutation: catch only `BridgeError` in `_forward` again -> no reply.
        token = jwt(900, "gzip")
        stand_in = StandIn(valid_tokens={token})

        async def not_gzip(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=b"not gzip",
                headers={"content-type": "application/json", "content-encoding": "gzip"},
            )

        stand_in.override = not_gzip
        harness = Harness(stand_in, signed_in(token))
        replies = await harness.send(CALL(6))

        assert len(replies) == 1
        assert replies[0]["id"] == 6
        assert replies[0]["error"]["code"] == mcp_bridge.INTERNAL_ERROR
        assert "DecodingError" in replies[0]["error"]["message"]
        assert "Try again" in replies[0]["error"]["message"]
        assert "DecodingError" in harness.stderr.getvalue()
        assert token not in harness.output()

    @pytest.mark.asyncio
    async def test_any_unforeseen_failure_still_answers_the_request_once(self, signed_in) -> None:
        # The property itself, independent of which exception it is.
        # Mutation: catch a list of types in `_forward` -> RuntimeError is not
        # on it, and the request is never answered.
        harness = Harness(StandIn(valid_tokens=set()), signed_in(jwt(900, "boom")))

        async def explode(message: Any, request_id: Any) -> list[Any]:
            raise RuntimeError("a failure no one listed")

        harness.bridge._exchange = explode  # type: ignore[method-assign]
        replies = await harness.send(CALL(8), INITIALIZED)

        assert replies == [
            {
                "jsonrpc": "2.0",
                "id": 8,
                "error": {"code": mcp_bridge.INTERNAL_ERROR, "message": replies[0]["error"]["message"]},
            }
        ]
        assert "RuntimeError" in replies[0]["error"]["message"]
        assert "a failure no one listed" not in harness.output()

    @pytest.mark.parametrize("depth", [5000, 100000])
    @pytest.mark.asyncio
    async def test_a_line_nested_thousands_deep_from_the_agent_does_not_end_serve(
        self, signed_in, depth: int
    ) -> None:
        # Mutation: catch only `(UnicodeDecodeError, ValueError)` around the
        # agent's line again -> `RecursionError` ends `serve`, and the
        # request on the next line is never read.
        token = jwt(900, "agent-deep")
        stand_in = StandIn(valid_tokens={token})
        stdin = io.BytesIO(_nested(depth).encode() + b"\n" + json.dumps(LIST).encode() + b"\n")
        lines: list[bytes] = []
        err = io.StringIO()
        async with httpx.AsyncClient(transport=httpx.MockTransport(stand_in.handler), base_url=BASE) as http:
            exit_code = await asyncio.wait_for(
                mcp_bridge.serve(
                    http, signed_in(token), read_line=stdin.readline, write_line=lines.append, stderr=err
                ),
                30,
            )

        assert exit_code == 0
        replies = [json.loads(line) for line in lines]
        assert [r["id"] for r in replies] == [None, 2]
        assert replies[0]["error"]["code"] == mcp_bridge.PARSE_ERROR
        assert [t["name"] for t in replies[1]["result"]["tools"]] == ["stand_in_alpha", "stand_in_beta"]


# ---------------------------------------------------------------------------
# The bridge's bounds: a reply's size, a request's time, and what counts as a
# message (fix round, F-8.10-A04, A06, A07 and J12)
# ---------------------------------------------------------------------------


def _longest_strings(model: Any) -> dict[str, str]:
    """Every string field of a Pydantic model at its own `max_length`."""
    values: dict[str, str] = {}
    for name, field in model.model_fields.items():
        bounds = [m.max_length for m in field.metadata if hasattr(m, "max_length")]
        if bounds and field.annotation in (str, str | None):
            values[name] = "x" * bounds[0]
    return values


def _largest_real_reply(request_id: int) -> dict:
    """The largest `tools/call` reply the remote server's own output schemas
    allow: `reopen_past_answer` with every field at its bound, carried the
    way the MCP SDK carries a structured result, once as structured content
    and once as the same JSON in a text block."""
    from system_03_search_agent.adapters.mcp.server import ReopenedAnswerOutput
    from system_03_search_agent.contracts.events import CitationPayload

    citation: dict[str, Any] = _longest_strings(CitationPayload)
    citation.update(display_index=100, layer="layer_2_api")
    most_citations = next(
        m.max_length for m in ReopenedAnswerOutput.model_fields["citations"].metadata if hasattr(m, "max_length")
    )
    structured: dict[str, Any] = _longest_strings(ReopenedAnswerOutput)
    structured.update(
        asked_at="2026-09-26T12:00:00Z",
        audience_depth="deep_technical",
        citations=[dict(citation, citation_id=f"c{i}") for i in range(most_citations)],
        citations_omitted=0,
    )
    assert len(structured["answer_markdown"]) == 32000, "populate check: the answer is at its bound"
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": json.dumps(structured, indent=2)}],
            "structuredContent": structured,
            "isError": False,
        },
    }


class TestTheBridgesBounds:
    @pytest.mark.parametrize("reply_as", ["json", "sse"])
    @pytest.mark.asyncio
    async def test_the_largest_reply_the_schemas_allow_passes_whole(self, signed_in, reply_as: str) -> None:
        # F-8.10-A04: the cap sits well above every real reply and well below
        # the old 16 MiB. Mutation: set the cap under the largest real reply
        # -> this reply is refused; set it back to 16 MiB -> the second
        # assertion fails.
        token = jwt(900, "largest")
        stand_in = StandIn(valid_tokens={token}, reply_as=reply_as)
        largest = _largest_real_reply(3)
        size = len(json.dumps(largest).encode())

        async def reply(request: httpx.Request) -> httpx.Response:
            return stand_in._reply(largest)

        stand_in.override = reply
        harness = Harness(stand_in, signed_in(token))
        replies = await harness.send(CALL(3))

        assert replies == [largest]
        assert size * 4 <= mcp_bridge.MAX_REMOTE_REPLY_BYTES, (size, mcp_bridge.MAX_REMOTE_REPLY_BYTES)
        assert mcp_bridge.MAX_REMOTE_REPLY_BYTES * 4 <= 16 * 1024 * 1024

    @pytest.mark.asyncio
    async def test_a_reply_past_the_real_bound_is_not_passed_on(self, signed_in) -> None:
        # Mutation: raise the cap back to 16 MiB -> this reply reaches the
        # agent whole.
        token = jwt(900, "past")
        stand_in = StandIn(valid_tokens={token})
        filler = "x" * (mcp_bridge.MAX_REMOTE_REPLY_BYTES + 1024)

        async def huge(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=json.dumps({"jsonrpc": "2.0", "id": 3, "result": {"blob": filler}}).encode(),
                headers={"content-type": "application/json"},
            )

        stand_in.override = huge
        harness = Harness(stand_in, signed_in(token))
        replies = await harness.send(CALL(3))

        assert len(replies) == 1
        assert replies[0]["id"] == 3
        assert replies[0]["error"]["code"] == mcp_bridge.REMOTE_FAILED
        assert "larger than 4 MB" in replies[0]["error"]["message"]

    @pytest.mark.asyncio
    async def test_a_request_that_takes_too_long_is_answered_at_the_deadline(
        self, signed_in, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # F-8.10-A07. Mutation: drop the deadline -> the stand-in never
        # answers, the request is never answered, and `wait_for` gives up.
        monkeypatch.setattr(mcp_bridge, "REQUEST_DEADLINE_SECONDS", 0.3)
        token = jwt(900, "stuck")
        stand_in = StandIn(valid_tokens={token})
        never = asyncio.Event()

        async def stuck(request: httpx.Request) -> httpx.Response:
            await never.wait()
            raise AssertionError("unreachable")

        stand_in.override = stuck
        harness = Harness(stand_in, signed_in(token))
        started = time.monotonic()
        replies = await asyncio.wait_for(harness.send(CALL(5)), 5)

        assert time.monotonic() - started < 3
        assert len(replies) == 1
        assert replies[0]["id"] == 5
        assert replies[0]["error"]["code"] == mcp_bridge.REMOTE_UNREACHABLE
        assert "did not answer within 0.3 seconds" in replies[0]["error"]["message"]

    @pytest.mark.asyncio
    async def test_eight_stuck_requests_do_not_block_a_later_one_for_good(
        self, signed_in, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A07's case: eight requests the server never finishes fill every
        # slot. Mutation: drop the deadline -> the ninth waits for good.
        monkeypatch.setattr(mcp_bridge, "REQUEST_DEADLINE_SECONDS", 1.0)
        token = jwt(900, "slots")
        stand_in = StandIn(valid_tokens={token})
        never = asyncio.Event()

        async def first_eight_stick(request: httpx.Request) -> httpx.Response:
            if json.loads(request.content)["id"] <= mcp_bridge.MAX_IN_FLIGHT:
                await never.wait()
            stand_in.override = None
            response = await stand_in.handler(request)
            stand_in.override = first_eight_stick
            return response

        stand_in.override = first_eight_stick
        harness = Harness(stand_in, signed_in(token))
        for request_id in range(1, mcp_bridge.MAX_IN_FLIGHT + 1):
            await harness.bridge.handle_line(json.dumps(CALL(request_id)).encode())
        await asyncio.sleep(0.5)
        later = mcp_bridge.MAX_IN_FLIGHT + 1
        await harness.bridge.handle_line(json.dumps(CALL(later)).encode())
        await asyncio.wait_for(harness.bridge.drain(), 5)

        by_id = {r["id"]: r for r in harness.replies()}
        assert sorted(by_id) == list(range(1, later + 1))
        assert all(by_id[i]["error"]["code"] == mcp_bridge.REMOTE_UNREACHABLE for i in range(1, later))
        assert by_id[later]["result"]["isError"] is False

    @pytest.mark.asyncio
    async def test_the_deadline_never_loses_a_renewal_the_server_already_made(
        self, signed_in, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The deadline is a new way to cancel a request, and a request can be
        # cancelled while its renewal is in flight. The server rotates the
        # refresh token the moment it answers, so a renewal cut off after that
        # loses the only live token, and the next one replays a used token,
        # which signs the person out everywhere. Mutation: drop the
        # `asyncio.shield` around `refresh_locked` -> the second request fails
        # with "s3 login".
        monkeypatch.setattr(mcp_bridge, "REQUEST_DEADLINE_SECONDS", 0.2)
        stand_in = StandIn(valid_tokens=set())
        signed_in(jwt(10, "expiring"))

        async def slow_after_rotating(request: httpx.Request) -> httpx.Response:
            response = await stand_in.handler(request)
            if request.url.path == "/auth/refresh":
                await asyncio.sleep(0.5)  # rotated on the server, not yet read here
            return response

        harness = Harness(stand_in, credentials.load())
        harness.http = httpx.AsyncClient(transport=httpx.MockTransport(slow_after_rotating), base_url=BASE)
        harness.bridge._http = harness.http
        first = await harness.send(CALL(1))
        assert first[0]["error"]["code"] == mcp_bridge.REMOTE_UNREACHABLE, "populate check: the deadline hit"
        await asyncio.sleep(0.8)  # the renewal the server made finishes in the background

        assert credentials.load().refresh_token == "refresh-2"
        monkeypatch.setattr(mcp_bridge, "REQUEST_DEADLINE_SECONDS", 30.0)
        second = await harness.send(CALL(2))
        assert second[-1]["id"] == 2
        assert second[-1]["result"]["isError"] is False
        assert stand_in.refresh_calls == 1

    @pytest.mark.parametrize(
        ("line", "echoed_id"),
        [
            (json.dumps([LIST, _request(9, "ping")]), None),  # a batch
            (json.dumps("hello"), None),
            ("null", None),
            ("42", None),
            (json.dumps({"id": 5, "method": "tools/list"}), 5),  # no "jsonrpc"
            (json.dumps({"jsonrpc": "1.0", "id": 5, "method": "tools/list"}), 5),
            (json.dumps({"jsonrpc": "2.0", "id": {"a": 1}, "method": "ping"}), None),
            (json.dumps({"jsonrpc": "2.0", "id": True, "method": "tools/list"}), None),
            (json.dumps({"jsonrpc": "2.0", "id": None, "method": "tools/list"}), None),
            (json.dumps({"jsonrpc": "2.0", "id": 5, "method": 7}), 5),
            (json.dumps({"jsonrpc": "2.0", "id": 5, "method": "tools/list", "params": "x"}), 5),
            (json.dumps({"jsonrpc": "2.0", "id": 7}), None),  # a response with no result or error
            (json.dumps({"jsonrpc": "2.0", "id": 7, "result": {}, "error": {}}), None),
        ],
    )
    @pytest.mark.asyncio
    async def test_only_json_rpc_is_forwarded_and_anything_else_is_answered_here(
        self, signed_in, line: str, echoed_id: Any
    ) -> None:
        # F-8.10-J12. Mutation: forward every parsed line again -> the
        # stand-in receives it, with the token attached.
        harness = Harness(StandIn(valid_tokens=set()), signed_in(jwt(900, "shape")))
        replies = await harness.send(line.encode() + b"\n")

        assert harness.stand_in.mcp_requests == []
        assert len(replies) == 1
        assert replies[0]["id"] == echoed_id
        assert replies[0]["error"]["code"] == mcp_bridge.INVALID_REQUEST
        assert '"jsonrpc": "2.0"' in replies[0]["error"]["message"]

    @pytest.mark.asyncio
    async def test_nan_is_not_json_and_is_never_echoed(self, signed_in) -> None:
        # Python reads NaN as a number and writes it back as NaN, which no
        # JSON parser on the agent's side reads. Mutation: parse with plain
        # `json.loads` again -> the bridge answers `"id":NaN`.
        harness = Harness(StandIn(valid_tokens=set()), signed_in(jwt(900, "nan")))
        replies = await harness.send(b'{"jsonrpc":"2.0","id":NaN,"method":"ping"}\n')

        assert b"NaN" not in b"".join(harness.lines)
        assert replies == [
            {"jsonrpc": "2.0", "id": None, "error": {"code": mcp_bridge.PARSE_ERROR, "message": replies[0]["error"]["message"]}}
        ]

    @pytest.mark.asyncio
    async def test_only_the_reply_to_this_request_reaches_the_agent(self, signed_in) -> None:
        # F-8.10-A06: a stream that also carries an answer to an id the agent
        # did not send in this exchange, and a second answer to this one.
        # Mutation: forward every reply in the stream again -> the agent sees
        # ids 42 and 1, or two answers to 1.
        token = jwt(900, "ids")
        stand_in = StandIn(valid_tokens={token})
        progress = {"jsonrpc": "2.0", "method": "notifications/progress", "params": {"progressToken": 1, "progress": 1}}
        forged = {"jsonrpc": "2.0", "id": 42, "result": {"content": [{"type": "text", "text": "forged"}]}}
        real = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
        second = {"jsonrpc": "2.0", "id": 1, "result": {"tools": [{"name": "second"}]}}

        async def mixed(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[progress, forged, "not json-rpc", real, second])

        stand_in.override = mixed
        harness = Harness(stand_in, signed_in(token))
        replies = await harness.send(_request(1, "tools/list"))

        assert replies == [progress, real]
        assert "dropped 3 message(s)" in harness.stderr.getvalue()


# ---------------------------------------------------------------------------
# Protocol care
# ---------------------------------------------------------------------------


class TestProtocolCare:
    @pytest.mark.asyncio
    async def test_ping_is_answered_here_without_the_network(self, signed_in) -> None:
        harness = Harness(StandIn(valid_tokens=set()), signed_in(jwt(900, "ping")))
        replies = await harness.send(_request(9, "ping"))
        assert replies == [{"jsonrpc": "2.0", "id": 9, "result": {}}]
        assert harness.stand_in.mcp_requests == []

    @pytest.mark.asyncio
    async def test_a_cancelled_request_gets_no_reply(self, signed_in) -> None:
        token = jwt(900, "slow")
        stand_in = StandIn(valid_tokens={token})
        release = asyncio.Event()

        async def slow(request: httpx.Request) -> httpx.Response:
            await release.wait()
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 5, "result": {}})

        stand_in.override = slow
        harness = Harness(stand_in, signed_in(token))
        await harness.bridge.handle_line(json.dumps(CALL(5)).encode())
        await asyncio.sleep(0.05)
        await harness.bridge.handle_line(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 5}}).encode()
        )
        release.set()
        await harness.bridge.drain()
        assert harness.replies() == []

    @pytest.mark.asyncio
    async def test_stdout_is_one_ascii_json_message_per_line(self, signed_in) -> None:
        token = jwt(900, "lines")
        stand_in = StandIn(valid_tokens={token})
        separator = chr(0x2028)

        async def tricky(request: httpx.Request) -> httpx.Response:
            message = json.loads(request.content)
            text = f"line one{separator}line two\nline three"
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": message["id"], "result": {"content": [{"type": "text", "text": text}]}},
            )

        stand_in.override = tricky
        harness = Harness(stand_in, signed_in(token))
        await harness.send(CALL())
        raw = b"".join(harness.lines)
        assert raw.count(b"\n") == 1 and raw.endswith(b"\n")
        raw.decode("ascii")  # raises on any non-ASCII byte
        assert json.loads(raw)["result"]["content"][0]["text"].endswith("line three")


class TestTheLineReader:
    @pytest.mark.asyncio
    async def test_an_oversized_line_is_reported_not_buffered(self, monkeypatch) -> None:
        monkeypatch.setattr(mcp_bridge, "MAX_INBOUND_LINE_BYTES", 16)
        stdin = io.BytesIO(b"x" * 100 + b"\n" + b'{"ok":1}\n')
        queue = mcp_bridge.start_line_reader(stdin.readline, asyncio.get_running_loop())
        items = [await asyncio.wait_for(queue.get(), 5) for _ in range(3)]
        assert items == [(None, True), (b'{"ok":1}\n', False), (None, False)]


# ---------------------------------------------------------------------------
# `s3 mcp` through the real entry point
# ---------------------------------------------------------------------------


class TestS3McpCommand:
    @pytest.mark.asyncio
    async def test_without_a_sign_in_it_stops_before_reading_and_writes_no_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        directory = tmp_path / "empty"
        directory.mkdir(mode=0o700)
        monkeypatch.setattr(credentials, "CREDENTIALS_PATH", directory / "credentials")
        out, err = io.StringIO(), io.StringIO()
        exit_code = await main_module.async_main(
            ["mcp"], stdin=io.StringIO(json.dumps(LIST) + "\n"), stdout=out, stderr=err, http_client=object()
        )
        assert exit_code == 1
        assert out.getvalue() == ""
        assert "s3 login" in err.getvalue()

    @pytest.mark.asyncio
    async def test_a_password_in_the_base_url_is_never_printed(self, signed_in) -> None:
        # Fix round, F-8.10-A05: the start-up line on stderr and every error
        # the agent reads named the base URL whole. Mutation: use
        # `str(http.base_url)` for either again -> the userinfo is shown.
        base_url = "https://alice:hunter2@system3.test"
        token = jwt(900, "userinfo")
        signed_in(token)
        credentials.store(credentials.Credentials(base_url=base_url, access_token=token, refresh_token="refresh-1"))

        async def down(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, content=b"x")

        out, err = io.StringIO(), io.StringIO()
        async with httpx.AsyncClient(transport=httpx.MockTransport(down), base_url=base_url) as http:
            exit_code = await main_module.async_main(
                ["mcp"], stdin=io.StringIO(json.dumps(LIST) + "\n"), stdout=out, stderr=err, http_client=http
            )

        assert exit_code == 0
        replies = [json.loads(line) for line in out.getvalue().splitlines()]
        assert replies[0]["error"]["message"].startswith("System 3 at https://system3.test answered HTTP 500")
        assert "forwarding MCP messages to https://system3.test/mcp/" in err.getvalue()
        assert "hunter2" not in out.getvalue() + err.getvalue()
        assert "alice" not in out.getvalue() + err.getvalue()

    @pytest.mark.asyncio
    async def test_it_serves_until_stdin_closes(self, signed_in) -> None:
        token = jwt(900, "cmd")
        stand_in = StandIn(valid_tokens={token})
        signed_in(token)
        stdin = io.StringIO(json.dumps(INITIALIZE) + "\n" + json.dumps(LIST) + "\n" + json.dumps(CALL()) + "\n")
        out, err = io.StringIO(), io.StringIO()
        async with httpx.AsyncClient(transport=httpx.MockTransport(stand_in.handler), base_url=BASE) as http:
            exit_code = await main_module.async_main(["mcp"], stdin=stdin, stdout=out, stderr=err, http_client=http)
        assert exit_code == 0
        replies = [json.loads(line) for line in out.getvalue().splitlines()]
        assert sorted(r["id"] for r in replies) == [1, 2, 3]
        assert "forwarding MCP messages to https://system3.test/mcp/" in err.getvalue()
        assert token not in out.getvalue() + err.getvalue()
