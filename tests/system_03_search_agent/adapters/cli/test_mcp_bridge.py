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
from collections.abc import Callable
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
                        "error": {"code": -32600, "message": "missing, malformed, or invalid bearer token"},
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


def _refresh_harness(
    stand_in: StandIn, creds: credentials.Credentials, answer: Callable[[httpx.Request], Any]
) -> tuple[Harness, list[int]]:
    """A harness whose `/auth/refresh` is answered by `answer(request)` (it
    may return None to fall through to the stand-in). The list counts calls."""
    calls: list[int] = []

    async def wrapper(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/refresh":
            calls.append(1)
            result = answer(request)
            if asyncio.iscoroutine(result):
                result = await result
            if result is not None:
                return result
        return await stand_in.handler(request)

    harness = Harness(stand_in, creds)
    harness.http = httpx.AsyncClient(transport=httpx.MockTransport(wrapper), base_url=BASE)
    harness.bridge._http = harness.http
    return harness, calls


def _unreadable(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        content=b"not gzip",
        headers={"content-type": "application/json", "content-encoding": "gzip"},
    )


def _assert_no_secret(harness: Harness, *tokens: str) -> None:
    for token in (*tokens, "refresh-1"):
        assert token not in harness.output()


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
    async def test_unreadable_renewal_reply_names_decode_failure_and_logs_it(
        self,
        signed_in: Callable[[str | None], credentials.Credentials],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        expired = jwt(-5, "decode")
        stand_in = StandIn(valid_tokens={expired})
        harness = Harness(stand_in, signed_in(expired))

        async def unreadable_reply(
            _http: httpx.AsyncClient, _creds: credentials.Credentials
        ) -> credentials.Credentials:
            raise httpx.DecodingError("bad gzip payload: secret-like server text")

        monkeypatch.setattr(credentials, "refresh_locked", unreadable_reply)
        replies = await harness.send(CALL())

        assert stand_in.mcp_requests == [], "a failed renewal never forwards the request"
        assert replies[0]["error"]["code"] == mcp_bridge.SIGN_IN_NEEDED
        assert "Could not read System 3's sign-in renewal reply" in replies[0]["error"]["message"]
        assert "s3 login" in replies[0]["error"]["message"]
        assert "Try again" not in replies[0]["error"]["message"]
        assert "could not decode the sign-in renewal reply" in harness.stderr.getvalue()
        assert "s3 login" in harness.stderr.getvalue()
        assert "secret-like" not in harness.output()
        assert expired not in harness.output()

    @pytest.mark.asyncio
    async def test_unreadable_200_renewal_never_reuses_the_rotated_token(
        self, signed_in: Callable[[str | None], credentials.Credentials]
    ) -> None:
        expired = jwt(-5, "rotated")
        creds = signed_in(expired)
        stand_in = StandIn(valid_tokens={expired})
        refresh_calls = 0

        async def reply(request: httpx.Request) -> httpx.Response:
            nonlocal refresh_calls
            if request.url.path == "/auth/refresh":
                refresh_calls += 1
                return httpx.Response(
                    200, content=b"not gzip",
                    headers={"content-type": "application/json", "content-encoding": "gzip"},
                )
            return await stand_in.handler(request)

        lines: list[bytes] = []
        err = io.StringIO()
        async with httpx.AsyncClient(transport=httpx.MockTransport(reply), base_url=BASE) as http:
            bridge = mcp_bridge.McpBridge(http, creds, write_line=lines.append, stderr=err)
            await bridge.handle_line(json.dumps(CALL()).encode())
            await bridge.drain()

        response = json.loads(lines[0])
        assert len(lines) == 1
        assert refresh_calls == 1
        assert stand_in.mcp_requests == []
        assert response["error"]["code"] == mcp_bridge.SIGN_IN_NEEDED
        assert "s3 login" in response["error"]["message"]
        assert "Try again" not in response["error"]["message"]
        assert "s3 login" in err.getvalue()
        assert expired not in str(response) + err.getvalue()

    @pytest.mark.asyncio
    async def test_a_renewed_token_refused_again_is_an_error_not_silence(self, signed_in) -> None:
        stand_in = StandIn(valid_tokens=set())

        async def always_refuse(request: httpx.Request) -> httpx.Response:
            message = json.loads(request.content)
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32600, "message": "invalid bearer token"}},
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

    # -- Card 75: a renewal that cannot be read must never be replayed -----

    @pytest.mark.asyncio
    async def test_unreadable_reply_latches_two_requests_in_turn(self, signed_in) -> None:
        # Mutation: drop `httpx.DecodingError` from `_latch_if_spent` -> the
        # second request renews again with the spent token.
        expired = jwt(-5, "latch-gzip")
        stand_in = StandIn(valid_tokens={expired})
        harness, calls = _refresh_harness(stand_in, signed_in(expired), _unreadable)
        replies = await harness.send(CALL(11), CALL(12))

        assert len(calls) == 1
        assert stand_in.mcp_requests == []
        assert [r["error"]["code"] for r in replies] == [mcp_bridge.SIGN_IN_NEEDED] * 2
        assert "s3 login" in replies[0]["error"]["message"]
        assert replies[1]["error"]["message"] == mcp_bridge._SIGN_IN_SPENT
        _assert_no_secret(harness, expired)

    @pytest.mark.asyncio
    async def test_unreadable_reply_latches_a_request_waiting_on_the_lock(self, signed_in) -> None:
        # Mutation: drop the latch check inside `_renew`'s lock -> the waiting
        # request renews a second time.
        expired = jwt(-5, "latch-wait")
        stand_in = StandIn(valid_tokens={expired})

        async def slow_unreadable(request: httpx.Request) -> httpx.Response:
            await asyncio.sleep(0.02)
            return _unreadable(request)

        harness, calls = _refresh_harness(stand_in, signed_in(expired), slow_unreadable)
        for request_id in (11, 12):
            await harness.bridge.handle_line(json.dumps(CALL(request_id)).encode())
        await harness.bridge.drain()

        assert len(calls) == 1
        assert stand_in.mcp_requests == []
        assert sorted(r["id"] for r in harness.replies()) == [11, 12]
        assert all(r["error"]["code"] == mcp_bridge.SIGN_IN_NEEDED for r in harness.replies())
        _assert_no_secret(harness, expired)

    @pytest.mark.asyncio
    async def test_a_refused_renewal_latches(self, signed_in) -> None:
        # Mutation: drop `credentials.RefreshError` from `_latch_if_spent`.
        expired = jwt(-5, "latch-refused")
        stand_in = StandIn(valid_tokens={expired})
        stand_in.valid_refresh_tokens = set()
        harness = Harness(stand_in, signed_in(expired))
        replies = await harness.send(CALL(11), CALL(12))

        assert stand_in.refresh_calls == 1
        assert stand_in.mcp_requests == []
        assert replies[0]["error"]["code"] == mcp_bridge.SIGN_IN_NEEDED
        assert replies[1]["error"]["message"] == mcp_bridge._SIGN_IN_SPENT
        _assert_no_secret(harness, expired)

    @pytest.mark.asyncio
    async def test_nothing_is_sent_after_the_latch(self, signed_in) -> None:
        # Mutation: drop the check at the top of `_exchange` -> the second
        # request reaches `/mcp/`.
        stand_in = StandIn(valid_tokens=set())
        stand_in.valid_refresh_tokens = set()
        harness = Harness(stand_in, signed_in("opaque"))
        replies = await harness.send(CALL(11), CALL(12))

        assert len(stand_in.mcp_requests) == 1
        assert stand_in.refresh_calls == 1
        assert replies[1]["error"]["message"] == mcp_bridge._SIGN_IN_SPENT
        _assert_no_secret(harness, "opaque")

    @pytest.mark.asyncio
    async def test_a_renewal_that_fails_after_its_request_was_cancelled_still_latches(
        self, signed_in, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation: set the latch in the `except` branches of `_renew` instead
        # of the done callback -> the cancelled request never reaches them and
        # the second request renews with the spent token.
        monkeypatch.setattr(mcp_bridge, "REQUEST_DEADLINE_SECONDS", 0.2)
        expired = jwt(-5, "latch-cancel")
        stand_in = StandIn(valid_tokens={expired})

        async def slow_unreadable(request: httpx.Request) -> httpx.Response:
            await asyncio.sleep(0.5)
            return _unreadable(request)

        harness, calls = _refresh_harness(stand_in, signed_in(expired), slow_unreadable)
        first = await harness.send(CALL(1))
        assert first[0]["error"]["code"] == mcp_bridge.REMOTE_UNREACHABLE, (
            "populate check: the deadline hit"
        )
        await asyncio.sleep(0.8)
        monkeypatch.setattr(mcp_bridge, "REQUEST_DEADLINE_SECONDS", 30.0)
        second = await harness.send(CALL(2))

        assert second[-1]["id"] == 2
        assert second[-1]["error"]["code"] == mcp_bridge.SIGN_IN_NEEDED
        assert len(calls) == 1
        assert stand_in.mcp_requests == []
        _assert_no_secret(harness, expired)

    @pytest.mark.asyncio
    async def test_a_network_failure_does_not_latch(self, signed_in) -> None:
        # Mutation: latch on every failure (`if exc is not None`) -> the
        # second request is refused without renewing.
        expired = jwt(-5, "no-latch-net")
        stand_in = StandIn(valid_tokens={expired})

        def fail_once(request: httpx.Request) -> httpx.Response | None:
            if len(calls) == 1:
                raise httpx.ConnectError("down", request=request)
            return None

        harness, calls = _refresh_harness(stand_in, signed_in(expired), fail_once)
        first = await harness.send(CALL(11))
        assert first[0]["error"]["code"] == mcp_bridge.REMOTE_UNREACHABLE
        second = await harness.send(CALL(12))

        assert len(calls) == 2
        assert second[-1]["id"] == 12
        assert second[-1]["result"]["isError"] is False
        _assert_no_secret(harness, expired)

    @pytest.mark.asyncio
    async def test_a_missing_credential_file_does_not_latch(self, signed_in) -> None:
        # Mutation: latch on every failure -> the second request is refused
        # with the "earlier in this MCP server" sentence.
        expired = jwt(-5, "no-latch-file")
        stand_in = StandIn(valid_tokens={expired})
        creds = signed_in(expired)
        harness = Harness(stand_in, creds)
        credentials.CREDENTIALS_PATH.unlink()
        first = await harness.send(CALL(11))
        assert first[0]["error"]["code"] == mcp_bridge.SIGN_IN_NEEDED
        assert "not signed in" in first[0]["error"]["message"]
        signed_in(expired)
        second = await harness.send(CALL(12))

        assert second[-1]["result"]["isError"] is False
        _assert_no_secret(harness, expired)


# ---------------------------------------------------------------------------
# Card 75, fix round: the latch holds at the moment of the POST, an unknown
# outcome latches, and a new sign-in is picked up without a restart.
# ---------------------------------------------------------------------------


class RotatingRefresh:
    """`/auth/refresh` as `auth/router.py` answers it: a live refresh token is
    swapped for a new one and recorded as used, and a used one revokes every
    live sign-in (`_revoke_family_on_reuse`) and answers 401. `plan` gives the
    action for each call in order, "ok" once it runs out:

        ("proxy", status)           a proxy answers; the server never sees it
        ("unreadable", delay)       rotates, waits, then answers an unreadable 200
        ("lose", exception, delay)  rotates, waits, then the reply is lost
        ("status", status)          rotates, then answers this status
                                    (an optional third item: Response kwargs)
        ("html",)                   a proxy answers 200 text/html; no rotation
        ("emptyjson",)              a proxy answers 200 application/json with no body
        ("raise", exception)        the request fails before the app sees it
    """

    def __init__(self, stand_in: StandIn, plan: list[tuple] | None = None) -> None:
        self.stand_in = stand_in
        self.plan = list(plan or [])
        self.active = {"refresh-1"}
        self.used: set[str] = set()
        self.sent: list[str] = []  # every refresh token posted, proxy answers included
        self.spent_sends = 0  # a used token reaching the server
        self.family_revoked = 0
        self.count = 0

    async def answer(self, request: httpx.Request) -> httpx.Response:
        self.count += 1
        action = self.plan.pop(0) if self.plan else ("ok",)
        token = json.loads(request.content)["refresh_token"]
        self.sent.append(token)
        if action[0] == "proxy":
            return httpx.Response(action[1], **(action[2] if len(action) > 2 else {}))
        if action[0] == "html":
            return httpx.Response(
                200, content=b"<html>maintenance</html>", headers={"content-type": "text/html"}
            )
        if action[0] == "emptyjson":
            return httpx.Response(200, content=b"", headers={"content-type": "application/json"})
        if action[0] == "raise":
            raise action[1]("never reached the app", request=request)
        if token in self.used:
            self.spent_sends += 1
            self.family_revoked += 1
            self.active.clear()
            return httpx.Response(401, json={"detail": "revoked"})
        if token not in self.active:
            return httpx.Response(401, json={"detail": "invalid"})
        self.active.discard(token)
        self.used.add(token)
        new_refresh = f"refresh-{len(self.used) + 1}"
        new_access = jwt(900, f"renewed-{self.count}")
        self.active.add(new_refresh)
        self.stand_in.valid_tokens.add(new_access)
        if action[0] == "ok":
            return httpx.Response(
                200, json={"access_token": new_access, "refresh_token": new_refresh}
            )
        if action[0] == "unreadable":
            await asyncio.sleep(action[1])
            return _unreadable(request)
        if action[0] == "lose":
            await asyncio.sleep(action[2])
            raise action[1]("reply lost", request=request)
        return httpx.Response(action[1], **(action[2] if len(action) > 2 else {}))


def _cancel(request_id: int) -> bytes:
    return json.dumps(
        {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": request_id}}
    ).encode()


async def _line(harness: Harness, message: Any) -> None:
    await harness.bridge.handle_line(json.dumps(message).encode())


def _assert_no_tokens(harness: Harness, *tokens: str) -> None:
    for token in (*tokens, "refresh-1", "refresh-2", "refresh-3", "login-1"):
        assert token not in harness.output()


class TestRenewalLatchFixRound:
    # -- the check at the moment of the POST (A-75-01, J-75-04, A-75-07) ----

    @pytest.mark.asyncio
    async def test_a_waiting_request_never_sends_the_spent_token_when_the_renewer_is_cancelled(
        self, signed_in
    ) -> None:
        # A-75-01. Mutation: drop the `if sent in wired: raise` check in
        # `_RenewalClient.post` -> request 4 posts refresh-1 and the family
        # is revoked.
        expired = jwt(-5, "a7501")
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [("unreadable", 0.3)])
        harness, _ = _refresh_harness(stand_in, signed_in(expired), server.answer)
        await _line(harness, CALL(3))
        await asyncio.sleep(0.05)
        await _line(harness, CALL(4))
        await asyncio.sleep(0.05)
        await harness.bridge.handle_line(_cancel(3))
        await harness.bridge.drain()

        assert server.sent == ["refresh-1"]
        assert server.family_revoked == 0
        assert stand_in.mcp_requests == []
        replies = harness.replies()
        assert [r["id"] for r in replies] == [4]
        assert replies[0]["error"]["message"] == mcp_bridge._SIGN_IN_SPENT
        _assert_no_tokens(harness, expired)

    @pytest.mark.asyncio
    async def test_a_request_that_arrives_after_a_cancel_never_sends_the_spent_token(
        self, signed_in
    ) -> None:
        # J-75-04. Mutation: as above.
        expired = jwt(-5, "j7504")
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [("unreadable", 0.4)])
        harness, _ = _refresh_harness(stand_in, signed_in(expired), server.answer)
        await _line(harness, CALL(3))
        await asyncio.sleep(0.1)
        await harness.bridge.handle_line(_cancel(3))
        await asyncio.sleep(0.05)
        await _line(harness, CALL(4))  # starts while the renewal is still in flight
        await harness.bridge.drain()

        assert server.sent == ["refresh-1"]
        assert server.family_revoked == 0
        assert [r["id"] for r in harness.replies()] == [4]
        _assert_no_tokens(harness, expired)

    @pytest.mark.asyncio
    async def test_asking_again_after_a_timeout_never_sends_the_spent_token(
        self, signed_in, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A-75-07. Mutation: as above.
        monkeypatch.setattr(mcp_bridge, "REQUEST_DEADLINE_SECONDS", 0.2)
        expired = jwt(-5, "a7507")
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [("unreadable", 0.5)])
        harness, _ = _refresh_harness(stand_in, signed_in(expired), server.answer)
        await _line(harness, CALL(3))
        await asyncio.sleep(0.3)  # request 3 has been answered, its renewal still runs
        assert [r["id"] for r in harness.replies()] == [3], "populate check: the deadline hit"
        await _line(harness, CALL(4))
        await harness.bridge.drain()

        assert server.sent == ["refresh-1"]
        assert server.family_revoked == 0
        assert stand_in.mcp_requests == []
        _assert_no_tokens(harness, expired)

    # -- a reply lost after the request was sent (A-75-02, J-75-02) -------

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "error", [httpx.ReadTimeout, httpx.ReadError, httpx.RemoteProtocolError]
    )
    async def test_a_renewal_reply_lost_after_it_was_sent_latches(self, signed_in, error) -> None:
        # A-75-02 and J-75-02. Mutation: in `_RenewalClient.post`, take the
        # token back on every `httpx.HTTPError` -> the second request posts
        # the rotated-away refresh-1 and the family is revoked.
        expired = jwt(-5, "a7502")
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [("lose", error, 0.0)])
        harness, _ = _refresh_harness(stand_in, signed_in(expired), server.answer)
        replies = await harness.send(CALL(11), CALL(12))

        assert server.sent == ["refresh-1"]
        assert server.family_revoked == 0
        assert stand_in.mcp_requests == []
        assert replies[0]["error"]["code"] == mcp_bridge.REMOTE_UNREACHABLE
        assert replies[1]["error"]["message"] == mcp_bridge._SIGN_IN_SPENT
        _assert_no_tokens(harness, expired)

    # -- a new sign-in is picked up without a restart (A-75-05, J-75-07) ---

    @pytest.mark.asyncio
    async def test_s3_login_revives_a_latched_bridge_without_a_restart(self, signed_in) -> None:
        # A-75-05 and J-75-07. Mutation: `_resume_from_file` returns False
        # -> the request after `s3 login` is still refused.
        expired = jwt(-5, "a7505")
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in)
        server.active.clear()  # the stored sign-in was revoked: the server answers 401
        harness, _ = _refresh_harness(stand_in, signed_in(expired), server.answer)
        first = await harness.send(CALL(11))
        assert first[0]["error"]["code"] == mcp_bridge.SIGN_IN_NEEDED, "populate check: latched"

        login_access = jwt(900, "login")
        stand_in.valid_tokens.add(login_access)
        server.active.add("login-1")
        credentials.store(
            credentials.Credentials(
                base_url=BASE, access_token=login_access, refresh_token="login-1"
            )
        )
        second = await harness.send(CALL(12))

        assert second[-1]["id"] == 12
        assert second[-1]["result"]["isError"] is False
        assert [r.headers["authorization"] for r in stand_in.mcp_requests] == [
            f"Bearer {login_access}"
        ]
        assert server.sent == ["refresh-1"], "the new sign-in needed no renewal at all"
        assert server.spent_sends == 0
        _assert_no_tokens(harness, expired, login_access)

    @pytest.mark.asyncio
    async def test_a_latched_bridge_never_resumes_with_the_spent_token_itself(
        self, signed_in
    ) -> None:
        # The re-read exit compares against the spent token held in memory.
        # Mutation: the check `current.refresh_token in self._wired` replaced
        # by False -> the file's unchanged refresh-1 resumes the bridge and a
        # request reaches `/mcp/` after the latch.
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in)
        server.active.clear()
        harness, _ = _refresh_harness(stand_in, signed_in("opaque"), server.answer)
        replies = await harness.send(CALL(11), CALL(12), CALL(13))

        assert len(stand_in.mcp_requests) == 1, "only the request that found the token refused"
        assert server.sent == ["refresh-1"]
        assert replies[1]["error"]["message"] == mcp_bridge._SIGN_IN_SPENT
        assert replies[2]["error"]["message"] == mcp_bridge._SIGN_IN_SPENT
        assert "picked up" not in harness.stderr.getvalue()
        _assert_no_tokens(harness, "opaque")

    # -- a saved recovery copy is picked up (A-75-06, J-75-03) -------------

    @pytest.mark.asyncio
    async def test_a_renewal_saved_to_the_recovery_copy_is_picked_up_not_locked_out(
        self, signed_in, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A-75-06 and J-75-03. Mutation: `_resume_from_file` returns False ->
        # the second request is refused although nothing was lost.
        expired = jwt(-5, "a7506")
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in)
        harness, _ = _refresh_harness(stand_in, signed_in(expired), server.answer)
        real_store = credentials.store
        failures = [OSError(28, "No space left on device")]

        def store_fails_once(creds: credentials.Credentials) -> None:
            if failures:
                raise failures.pop()
            real_store(creds)

        monkeypatch.setattr(credentials, "store", store_fails_once)
        first = await harness.send(CALL(11))
        assert first[0]["error"]["code"] == mcp_bridge.SIGN_IN_NEEDED
        assert "could not be saved" in first[0]["error"]["message"]
        assert "expired" not in first[0]["error"]["message"]
        second = await harness.send(CALL(12))

        assert second[-1]["id"] == 12
        assert second[-1]["result"]["isError"] is False
        assert server.sent == ["refresh-1"]
        assert server.family_revoked == 0
        _assert_no_tokens(harness, expired)

    @pytest.mark.asyncio
    async def test_a_renewal_that_could_not_be_saved_anywhere_latches(
        self, signed_in, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # J-75-05. Mutation: `_latch_if_spent` returns early for a
        # `SessionLostError` -> the second request reaches `/mcp/`.
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in)
        harness, _ = _refresh_harness(stand_in, signed_in("opaque"), server.answer)

        def store_always_fails(_creds: credentials.Credentials) -> None:
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(credentials, "store", store_always_fails)
        monkeypatch.setattr(credentials, "_write_recovery_copy", lambda _creds: False)
        replies = await harness.send(CALL(11), CALL(12))

        assert replies[0]["error"]["code"] == mcp_bridge.SIGN_IN_NEEDED
        assert replies[1]["error"]["message"] == mcp_bridge._SIGN_IN_SPENT
        assert len(stand_in.mcp_requests) == 1, "nothing is sent after the latch"
        assert server.sent == ["refresh-1"]
        assert server.family_revoked == 0
        _assert_no_tokens(harness, "opaque")

    @pytest.mark.asyncio
    async def test_a_renewal_cancelled_after_it_was_sent_latches(self, signed_in) -> None:
        # The design: an outcome the bridge cannot know latches. Mutation: in
        # `_latch_if_spent`, return early for a cancelled task -> the second
        # request reaches `/mcp/`.
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [("unreadable", 5.0)])
        harness, _ = _refresh_harness(stand_in, signed_in("opaque"), server.answer)
        await _line(harness, CALL(11))
        await asyncio.sleep(0.1)
        renewal = [t for t in harness.bridge._tasks if "refresh_locked" in repr(t.get_coro())]
        assert len(renewal) == 1
        assert server.sent == ["refresh-1"], "populate check: the renewal was sent"
        renewal[0].cancel()
        await asyncio.gather(*renewal, return_exceptions=True)
        await asyncio.sleep(0.05)
        before = len(stand_in.mcp_requests)
        await harness.send(CALL(12))

        assert len(stand_in.mcp_requests) == before
        assert server.sent == ["refresh-1"]
        _assert_no_tokens(harness, "opaque")

    # -- a proxy 429 does not latch (J-75-01), a 5xx is told truthfully (J-75-06)

    @pytest.mark.asyncio
    async def test_a_proxy_429_on_renewal_does_not_latch(self, signed_in) -> None:
        # J-75-01, the 429 half. Mutation: remove the `== 429` discard in
        # `_RenewalClient.post` -> the second request is refused.
        expired = jwt(-5, "j7501")
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [("proxy", 429)])
        harness, _ = _refresh_harness(stand_in, signed_in(expired), server.answer)
        replies = await harness.send(CALL(11), CALL(12))

        assert replies[0]["error"]["code"] == mcp_bridge.REMOTE_UNREACHABLE
        assert "429" in replies[0]["error"]["message"]
        assert "expired" not in replies[0]["error"]["message"]
        assert replies[1]["id"] == 12
        assert replies[1]["result"]["isError"] is False
        assert server.sent == ["refresh-1", "refresh-1"]
        assert server.family_revoked == 0
        _assert_no_tokens(harness, expired)

    @pytest.mark.asyncio
    async def test_the_message_after_a_server_error_says_the_renewal_failed(
        self, signed_in
    ) -> None:
        # J-75-06. Mutation: make the status branch in `_renew` never match
        # -> the person is told the sign-in "has expired or was signed out".
        expired = jwt(-5, "j7506")
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [("proxy", 503)])
        harness, _ = _refresh_harness(stand_in, signed_in(expired), server.answer)
        replies = await harness.send(CALL(11), CALL(12))

        message = replies[0]["error"]["message"]
        assert replies[0]["error"]["code"] == mcp_bridge.REMOTE_UNREACHABLE
        assert "could not renew your sign-in right now (it answered 503)" in message
        assert "try again" in message.lower()
        assert "s3 login" not in message
        assert "expired" not in message
        assert "expired, already used" not in harness.stderr.getvalue()
        assert "503" in harness.stderr.getvalue()
        assert replies[1]["result"]["isError"] is False, "a brief server error recovers by itself"
        assert server.sent == ["refresh-1", "refresh-1"]
        _assert_no_tokens(harness, expired)


# ---------------------------------------------------------------------------
# Card 75, owner's decision of 2026-10-16: clear server errors retry quietly,
# only a truly unknown outcome asks the person to run `s3 login` once.
# Each row names what a person sees. Row numbers are the verifier's.
# ---------------------------------------------------------------------------

# (row, plan for the first renewal, the first reply's code, whether the next
# request is answered, spent tokens that reach the server)
_RECOVERS = [
    ("02 a proxy's web page instead of the reply", ("html",), mcp_bridge.REMOTE_UNREACHABLE),
    ("05 a proxy 502", ("proxy", 502), mcp_bridge.REMOTE_UNREACHABLE),
    ("06 a proxy 503", ("proxy", 503), mcp_bridge.REMOTE_UNREACHABLE),
    ("07 a proxy 429", ("proxy", 429), mcp_bridge.REMOTE_UNREACHABLE),
    (
        "11 a connection that was refused",
        ("raise", httpx.ConnectError),
        mcp_bridge.REMOTE_UNREACHABLE,
    ),
    (
        "V4 a write that failed before the request was sent",
        ("raise", httpx.WriteError),
        mcp_bridge.REMOTE_UNREACHABLE,
    ),
    (
        "V5 a proxy that could not be reached",
        ("raise", httpx.ProxyError),
        mcp_bridge.REMOTE_UNREACHABLE,
    ),
]

_ASKS_FOR_LOGIN = [
    ("08 a read timeout after the request was sent", ("lose", httpx.ReadTimeout, 0.0)),
    ("09 a read error after the request was sent", ("lose", httpx.ReadError, 0.0)),
    (
        "10 a dropped connection after the request was sent",
        ("lose", httpx.RemoteProtocolError, 0.0),
    ),
]


class TestRenewalOutcomes:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("row", "action", "code"), _RECOVERS, ids=[r[0][:3] for r in _RECOVERS]
    )
    async def test_a_clear_failure_retries_quietly_and_the_next_request_is_answered(
        self, signed_in, row, action, code
    ) -> None:
        # Mutation: classify a 5xx as unknown (drop `status >= 500` from the
        # discard in `_RenewalClient.post`) -> rows 05 and 06 go red.
        expired = jwt(-5, "recover")
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [action])
        harness, _ = _refresh_harness(stand_in, signed_in(expired), server.answer)
        replies = await harness.send(CALL(11), CALL(12))

        assert replies[0]["error"]["code"] == code
        assert "s3 login" not in replies[0]["error"]["message"]
        assert replies[1]["result"]["isError"] is False
        assert server.sent == ["refresh-1", "refresh-1"]
        assert server.spent_sends == 0
        assert server.family_revoked == 0
        _assert_no_tokens(harness, expired)

    @pytest.mark.asyncio
    async def test_a_proxy_503_then_healthy_answers_every_later_request(self, signed_in) -> None:
        # Row VC. Four requests in turn, only the first meets the error.
        expired = jwt(-5, "vc")
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [("proxy", 503)])
        harness, _ = _refresh_harness(stand_in, signed_in(expired), server.answer)
        replies = await harness.send(CALL(10), CALL(11), CALL(12), CALL(13))

        assert [r["id"] for r in replies] == [10, 11, 12, 13]
        assert "error" in replies[0]
        assert all(r["result"]["isError"] is False for r in replies[1:])
        assert server.spent_sends == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("row", "action"), _ASKS_FOR_LOGIN, ids=[r[0][:2] for r in _ASKS_FOR_LOGIN]
    )
    async def test_a_renewal_with_no_readable_answer_asks_for_s3_login_once(
        self, signed_in, row, action
    ) -> None:
        # Rows 08, 09, 10, and V2 and V3 (a timeout or protocol error the
        # client cannot tell from these). Mutation: take the token back on
        # every `httpx.HTTPError` -> the second request resends refresh-1.
        expired = jwt(-5, "unknown")
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [action])
        harness, _ = _refresh_harness(stand_in, signed_in(expired), server.answer)
        replies = await harness.send(CALL(11), CALL(12), CALL(13))

        first = replies[0]["error"]["message"]
        assert "s3 login" in first
        assert "no need to restart" in first or "picks up the new sign-in by itself" in first
        assert replies[1]["error"]["message"] == mcp_bridge._SIGN_IN_SPENT
        assert replies[2]["error"]["message"] == mcp_bridge._SIGN_IN_SPENT
        assert server.sent == ["refresh-1"]
        assert server.spent_sends == 0
        assert server.family_revoked == 0
        assert stand_in.mcp_requests == []
        _assert_no_tokens(harness, expired)

    @pytest.mark.asyncio
    async def test_a_reply_that_cannot_be_read_asks_for_s3_login_in_the_log_too(
        self, signed_in
    ) -> None:
        # Row 01 and V-75-04: the log and the agent's reply give one instruction.
        expired = jwt(-5, "row01")
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [("unreadable", 0.0)])
        harness, _ = _refresh_harness(stand_in, signed_in(expired), server.answer)
        replies = await harness.send(CALL(11), CALL(12))

        assert "s3 login" in replies[0]["error"]["message"]
        assert "restart" not in harness.stderr.getvalue()
        assert replies[1]["error"]["message"] == mcp_bridge._SIGN_IN_SPENT
        assert server.spent_sends == 0 and server.family_revoked == 0

    @pytest.mark.asyncio
    async def test_a_500_after_the_server_rotated_is_retried_as_before(self, signed_in) -> None:
        # Row 04, the owner's call: a 500 is a clear error and is retried
        # quietly, as develop does. The server rotated before it failed, so
        # the retry is refused; the person is signed out, as on develop. This
        # pins the accepted cost so a change shows up here.
        expired = jwt(-5, "row04")
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [("status", 500)])
        harness, _ = _refresh_harness(stand_in, signed_in(expired), server.answer)
        await harness.send(CALL(11), CALL(12))

        assert server.sent == ["refresh-1", "refresh-1"]
        assert server.spent_sends == 1

    # -- the status classes (J-75B-01, A-75B-01, A-75B-04, J-75B-05) --------

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [400, 403, 404, 408, 421, 301, 307, 500, 502, 503, 429])
    async def test_a_status_the_app_cannot_send_after_renewing_retries_quietly(
        self, signed_in, status
    ) -> None:
        # J-75B-01 and A-75B-01. Mutation: take the token back only for 429
        # and 5xx (the old rule) -> 4xx and 3xx rows latch and the second
        # request is refused.
        expired = jwt(-5, f"c{status}")
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [("proxy", status)])
        harness, _ = _refresh_harness(stand_in, signed_in(expired), server.answer)
        replies = await harness.send(CALL(11), CALL(12))

        assert replies[0]["error"]["code"] == mcp_bridge.REMOTE_UNREACHABLE
        assert f"it answered {status}" in replies[0]["error"]["message"]
        assert "s3 login" not in replies[0]["error"]["message"]
        assert replies[1]["result"]["isError"] is False
        assert server.sent == ["refresh-1", "refresh-1"]
        assert server.spent_sends == 0 and server.family_revoked == 0
        _assert_no_tokens(harness, expired)

    @pytest.mark.asyncio
    async def test_a_401_on_renewal_latches(self, signed_in) -> None:
        # The sign-in is dead. Mutation: add 401 to the quiet statuses -> the
        # second request posts refresh-1 again.
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [("proxy", 401)])
        harness, _ = _refresh_harness(stand_in, signed_in(jwt(-5, "c401")), server.answer)
        replies = await harness.send(CALL(11), CALL(12))

        assert replies[0]["error"]["code"] == mcp_bridge.SIGN_IN_NEEDED
        assert replies[1]["error"]["message"] == mcp_bridge._SIGN_IN_SPENT
        assert server.sent == ["refresh-1"]
        assert stand_in.mcp_requests == []

    @pytest.mark.asyncio
    async def test_a_504_on_renewal_asks_for_s3_login_once(self, signed_in) -> None:
        # A-75B-04. A gateway stopped waiting for a server that may have
        # renewed: the outcome is unknown. Mutation: treat 504 as quiet ->
        # the second request resends refresh-1 and the family is revoked.
        expired = jwt(-5, "c504")
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [("status", 504)])
        harness, _ = _refresh_harness(stand_in, signed_in(expired), server.answer)
        replies = await harness.send(CALL(11), CALL(12))

        assert replies[0]["error"]["code"] == mcp_bridge.SIGN_IN_NEEDED  # J-118-03
        assert "s3 login" in replies[0]["error"]["message"]
        assert replies[1]["error"]["message"] == mcp_bridge._SIGN_IN_SPENT
        assert server.sent == ["refresh-1"]
        assert server.spent_sends == 0 and server.family_revoked == 0
        _assert_no_tokens(harness, expired)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "extra",
        [{}, {"content": b"<html>gateway</html>", "headers": {"content-type": "text/html"}}],
        ids=["empty", "not-json"],
    )
    @pytest.mark.parametrize("status", [201, 202, 204])
    async def test_a_2xx_other_than_200_retries_quietly(self, signed_in, status, extra) -> None:
        # V-75B-01. Mutation: quiet only for 300 <= status < 600 -> latches.
        expired = jwt(-5, f"c{status}x")
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [("proxy", status, extra)])
        harness, _ = _refresh_harness(stand_in, signed_in(expired), server.answer)
        replies = await harness.send(CALL(11), CALL(12))

        assert replies[0]["error"]["code"] == mcp_bridge.REMOTE_UNREACHABLE
        assert "s3 login" not in replies[0]["error"]["message"]
        assert "expired" not in replies[0]["error"]["message"]
        assert replies[1]["result"]["isError"] is False
        assert server.sent == ["refresh-1", "refresh-1"]
        assert server.family_revoked == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [201, 202, 206, 299])
    async def test_a_2xx_with_a_json_body_after_a_saved_renewal_asks_for_s3_login(
        self, signed_in, status
    ) -> None:
        # A-118-01, J-118-02. The body may carry a renewal the app saved, so
        # the spent token is never resent. Mutation: quiet for every 2xx ->
        # the second request resends refresh-1 and the family is revoked.
        expired = jwt(-5, f"j{status}x")
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [("status", status, {"json": {"ok": True}})])
        harness, _ = _refresh_harness(stand_in, signed_in(expired), server.answer)
        replies = await harness.send(CALL(11), CALL(12))

        assert replies[0]["error"]["code"] == mcp_bridge.SIGN_IN_NEEDED
        assert "s3 login" in replies[0]["error"]["message"]
        assert replies[1]["error"]["message"] == mcp_bridge._SIGN_IN_SPENT
        assert server.sent == ["refresh-1"]
        assert server.spent_sends == 0 and server.family_revoked == 0
        _assert_no_tokens(harness, expired)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [600, 650, 999])
    async def test_a_status_of_600_or_more_asks_for_s3_login(self, signed_in, status) -> None:
        # A-118-02. Mutation: drop the `status < 600` bound -> quiet retry,
        # the second request resends refresh-1 and the family is revoked.
        expired = jwt(-5, f"h{status}x")
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [("status", status)])
        harness, _ = _refresh_harness(stand_in, signed_in(expired), server.answer)
        replies = await harness.send(CALL(11), CALL(12))

        assert replies[0]["error"]["code"] == mcp_bridge.SIGN_IN_NEEDED
        assert replies[1]["error"]["message"] == mcp_bridge._SIGN_IN_SPENT
        assert server.sent == ["refresh-1"]
        assert server.spent_sends == 0 and server.family_revoked == 0

    @pytest.mark.asyncio
    async def test_a_504_says_the_outcome_is_unknown_not_expired(self, signed_in) -> None:
        # V-75B-02. Mutation: remove the 504 branch in `_renew` -> the old
        # "expired" words return.
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [("status", 504)])
        harness, _ = _refresh_harness(stand_in, signed_in(jwt(-5, "u504")), server.answer)
        replies = await harness.send(CALL(11))

        message = replies[0]["error"]["message"]
        assert "may have renewed" in message and "s3 login" in message
        assert "expired" not in message and "signed out" not in message
        log = harness.stderr.getvalue()
        assert "unknown" in log and "504" in log
        # A-118-03: one clean sentence, no capital after a semicolon.
        assert "unknown. In a terminal, run: s3 login." in log and "; In a" not in log
        assert "expired" not in log and "revoked" not in log

    # -- an empty 200 versus an unreadable one (A-75B-02) -------------------

    @pytest.mark.asyncio
    async def test_an_empty_json_200_retries_quietly(self, signed_in) -> None:
        # A-75B-02. Mutation: drop the `not response.content` branch in
        # `_RenewalClient.post` -> the bridge latches.
        expired = jwt(-5, "a7502e")
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [("emptyjson",)])
        harness, _ = _refresh_harness(stand_in, signed_in(expired), server.answer)
        replies = await harness.send(CALL(11), CALL(12))

        assert replies[0]["error"]["code"] == mcp_bridge.REMOTE_UNREACHABLE
        assert "s3 login" not in replies[0]["error"]["message"]
        assert replies[1]["result"]["isError"] is False
        assert server.sent == ["refresh-1", "refresh-1"]
        assert server.family_revoked == 0

    @pytest.mark.asyncio
    async def test_a_non_empty_unreadable_json_200_still_latches(self, signed_in) -> None:
        # A-75B-02's other half. Mutation: treat every unreadable 200 as quiet.
        expired = jwt(-5, "a7502u")
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [("unreadable", 0.0)])
        harness, _ = _refresh_harness(stand_in, signed_in(expired), server.answer)
        replies = await harness.send(CALL(11), CALL(12))

        assert "s3 login" in replies[0]["error"]["message"]
        assert replies[1]["error"]["message"] == mcp_bridge._SIGN_IN_SPENT
        assert server.sent == ["refresh-1"]

    # -- the quiet-retry words claim nothing (J-75B-02, A-75B-03) -----------

    @pytest.mark.asyncio
    @pytest.mark.parametrize("plan", [("proxy", 503), ("html",), ("emptyjson",), ("status", 500)])
    async def test_the_quiet_retry_message_does_not_claim_the_sign_in_is_good(
        self, signed_in, plan
    ) -> None:
        # Mutation: restore "Your sign-in is still good" in `_renew`.
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [plan])
        harness, _ = _refresh_harness(stand_in, signed_in(jwt(-5, "words")), server.answer)
        replies = await harness.send(CALL(11))

        message = replies[0]["error"]["message"]
        assert "good" not in message
        assert "try again in a moment" in message.lower()

    # -- the outcome belongs to one renewal (J-75B-04, A-75B-06) ------------

    @pytest.mark.asyncio
    async def test_one_renewals_outcome_does_not_leak_into_another(self, signed_in) -> None:
        # Mutation: keep the outcome fields on the bridge -> a second client
        # inherits the first one's "not JSON" mark.
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in, [("html",), ("proxy", 401)])
        harness, _ = _refresh_harness(stand_in, signed_in(jwt(-5, "own")), server.answer)
        first = mcp_bridge._RenewalClient(harness.bridge)
        second = mcp_bridge._RenewalClient(harness.bridge)
        await first.post("/auth/refresh", json={"refresh_token": "t-a"})
        await second.post("/auth/refresh", json={"refresh_token": "t-b"})

        assert first.not_json is True and first.quiet is True
        assert second.status == 401 and second.not_json is False and second.quiet is False
        assert not hasattr(harness.bridge, "_refresh_not_json")
        assert not hasattr(harness.bridge, "_refresh_status")

    # -- a new sign-in for a differently written address (A-75B-05) ---------

    @pytest.mark.asyncio
    async def test_a_new_sign_in_with_a_trailing_slash_address_is_picked_up(
        self, signed_in
    ) -> None:
        # Mutation: compare `base_url` as raw strings -> still latched.
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in)
        server.active.clear()
        harness, _ = _refresh_harness(stand_in, signed_in(jwt(-5, "slash")), server.answer)
        first = await harness.send(CALL(11))
        assert first[0]["error"]["code"] == mcp_bridge.SIGN_IN_NEEDED, "populate check: latched"

        login_access = jwt(900, "slashlogin")
        stand_in.valid_tokens.add(login_access)
        credentials.store(
            credentials.Credentials(
                base_url=BASE.replace("https://", "HTTPS://") + "/",
                access_token=login_access,
                refresh_token="login-1",
            )
        )
        second = await harness.send(CALL(12))

        assert second[-1]["result"]["isError"] is False

    @pytest.mark.asyncio
    async def test_a_default_port_is_the_same_server(self, signed_in) -> None:
        # V-75B-03. Mutation: drop the default-port strip in `_normalised_address`.
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in)
        server.active.clear()
        harness, _ = _refresh_harness(stand_in, signed_in(jwt(-5, "p443")), server.answer)
        await harness.send(CALL(11))

        login_access = jwt(900, "p443login")
        stand_in.valid_tokens.add(login_access)
        credentials.store(
            credentials.Credentials(
                base_url=BASE + ":443", access_token=login_access, refresh_token="login-1"
            )
        )
        second = await harness.send(CALL(12))
        assert second[-1]["result"]["isError"] is False

    def test_only_a_default_port_is_dropped_from_an_address(self) -> None:
        norm = mcp_bridge._normalised_address
        assert norm("https://h:443") == norm("https://h")
        assert norm("http://h:80/") == norm("http://h")
        assert norm("https://h:8443") != norm("https://h")
        assert norm("https://h:80") != norm("https://h")

    @pytest.mark.asyncio
    async def test_a_lock_timeout_on_a_latched_bridge_is_named_in_the_log(
        self, signed_in, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # V-75B-04. Mutation: remove the `RefreshLockTimeoutError` clause.
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in)
        server.active.clear()
        harness, _ = _refresh_harness(stand_in, signed_in(jwt(-5, "lk")), server.answer)
        await harness.send(CALL(11))

        class Busy:
            def __init__(self, _path) -> None:
                pass

            async def __aenter__(self):
                raise credentials.RefreshLockTimeoutError("held at /secret/path", remedy="x")

            async def __aexit__(self, *exc_info):
                return False

        monkeypatch.setattr(credentials, "_CredentialFileLock", Busy)
        second = await harness.send(CALL(12))

        # J-118-01, A-118-04. Mutation: return None from the clause -> the
        # reply tells a person who already ran s3 login to run it again.
        message = second[-1]["error"]["message"]
        assert message == mcp_bridge._SIGN_IN_FILE_BUSY
        assert "Wait for that command to finish" in message and "try again" in message
        assert "If you have not run s3 login yet" in message
        assert "could not be renewed earlier" not in message
        log = harness.stderr.getvalue()
        assert "another s3 command is using the sign-in file" in log
        assert "Wait for that command to finish and try again" in log
        assert "/secret/path" not in log

    @pytest.mark.asyncio
    async def test_a_new_sign_in_for_another_server_says_to_restart(self, signed_in) -> None:
        # Mutation: restore the "picks up the new sign-in by itself" refusal.
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in)
        server.active.clear()
        harness, _ = _refresh_harness(stand_in, signed_in(jwt(-5, "other")), server.answer)
        await harness.send(CALL(11))
        before = len(stand_in.mcp_requests)
        credentials.store(
            credentials.Credentials(
                base_url="https://other-server.test", access_token="x", refresh_token="login-1"
            )
        )
        second = await harness.send(CALL(12))

        message = second[-1]["error"]["message"]
        assert "Restart this MCP server" in message
        assert "by itself" not in message
        assert len(stand_in.mcp_requests) == before

    # -- the latched read takes the refresh lock (A-75B-08) -----------------

    @pytest.mark.asyncio
    async def test_a_latched_bridge_reads_the_credential_file_under_the_refresh_lock(
        self, signed_in, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation: call `credentials.load()` with no lock in `_resume_from_file`.
        stand_in = StandIn(valid_tokens=set())
        server = RotatingRefresh(stand_in)
        server.active.clear()
        harness, _ = _refresh_harness(stand_in, signed_in(jwt(-5, "lock")), server.answer)
        await harness.send(CALL(11))  # latches

        held = {"now": False}
        read_outside_lock: list[bool] = []
        real_lock = credentials._CredentialFileLock
        real_load = credentials.load

        class WatchedLock(real_lock):  # type: ignore[misc, valid-type]
            async def __aenter__(self):
                result = await super().__aenter__()
                held["now"] = True
                return result

            async def __aexit__(self, *exc_info):
                held["now"] = False
                return await super().__aexit__(*exc_info)

        def watched_load():
            read_outside_lock.append(not held["now"])
            return real_load()

        monkeypatch.setattr(credentials, "_CredentialFileLock", WatchedLock)
        monkeypatch.setattr(credentials, "load", watched_load)
        await harness.send(CALL(12))

        assert read_outside_lock == [False], "one read, made while the lock was held"


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
    async def test_a_queued_request_gets_its_own_deadline_after_a_slot_opens(
        self,
        signed_in: Callable[[str | None], credentials.Credentials],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # V01: nine 0.22-second calls through eight slots with a 0.31-second
        # exchange budget. The ninth must not spend its own budget in the queue.
        monkeypatch.setattr(mcp_bridge, "REQUEST_DEADLINE_SECONDS", 0.31)
        token = jwt(900, "queued")
        stand_in = StandIn(valid_tokens={token})
        first_eight_started = asyncio.Event()
        started = 0

        async def slow_answer(request: httpx.Request) -> httpx.Response:
            nonlocal started
            started += 1
            if started == mcp_bridge.MAX_IN_FLIGHT:
                first_eight_started.set()
            await asyncio.sleep(0.22)
            message = json.loads(request.content)
            return httpx.Response(200, json={
                "jsonrpc": "2.0", "id": message["id"], "result": {"isError": False},
            })

        stand_in.override = slow_answer
        harness = Harness(stand_in, signed_in(token))
        for request_id in range(1, mcp_bridge.MAX_IN_FLIGHT + 1):
            await harness.bridge.handle_line(json.dumps(CALL(request_id)).encode())
        await asyncio.wait_for(first_eight_started.wait(), 2)
        later = mcp_bridge.MAX_IN_FLIGHT + 1
        await harness.bridge.handle_line(json.dumps(CALL(later)).encode())
        await asyncio.wait_for(harness.bridge.drain(), 3)

        by_id = {reply["id"]: reply for reply in harness.replies()}
        assert sorted(by_id) == list(range(1, later + 1))
        assert "result" in by_id[later], by_id[later]
        assert all(reply["result"]["isError"] is False for reply in by_id.values())

    @pytest.mark.asyncio
    async def test_a_deep_queue_is_refused_before_its_slot_wait_grows_without_bound(
        self,
        signed_in: Callable[[str | None], credentials.Credentials],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(mcp_bridge, "REQUEST_DEADLINE_SECONDS", 0.30)
        monkeypatch.setattr(mcp_bridge, "QUEUE_WAIT_SECONDS", 0.30)
        token = jwt(900, "deep-queue")
        stand_in = StandIn(valid_tokens={token})

        async def slow_answer(request: httpx.Request) -> httpx.Response:
            await asyncio.sleep(0.18)
            message = json.loads(request.content)
            return httpx.Response(
                200, json={"jsonrpc": "2.0", "id": message["id"], "result": {"isError": False}}
            )

        stand_in.override = slow_answer
        harness = Harness(stand_in, signed_in(token))
        count = mcp_bridge.MAX_IN_FLIGHT * 3
        for request_id in range(1, count + 1):
            await harness.bridge.handle_line(json.dumps(CALL(request_id)).encode())
        await asyncio.wait_for(harness.bridge.drain(), 3)

        by_id = {reply["id"]: reply for reply in harness.replies()}
        assert sorted(by_id) == list(range(1, count + 1))
        for request_id in range(2 * mcp_bridge.MAX_IN_FLIGHT + 1, count + 1):
            assert "System 3 is busy" in by_id[request_id]["error"]["message"]
        forwarded = {json.loads(request.content)["id"] for request in stand_in.mcp_requests}
        assert forwarded == set(range(1, 2 * mcp_bridge.MAX_IN_FLIGHT + 1))

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
