"""`s3 mcp`: a local MCP server on stdio that forwards to System 3's remote one.

Build phase 8.10, T-8.10-04 (`tracker/phase_8.10.md`), on the product owner's
decision of 2026-09-26: people outside the project get the MCP server through
one small package, `system3-cli`, and an AI agent that can only run a command
can still use System 3.

What a person does: `s3 login` once in a terminal, then point their agent at
the command `s3 mcp`. The agent speaks MCP to this process over stdin and
stdout. This process forwards every message to the deployed server's `/mcp/`
endpoint over streamable HTTP, adds the bearer token `s3 login` stored, and
writes the server's replies back. It renews that token itself before it
expires, through the same locked refresh `s3 ask` uses, so the fifteen-minute
access token never reaches the agent's configuration.

Why a forwarder rather than an MCP server of its own:

    - Every tool the remote server lists is offered here unchanged, with no
      tool name, schema or description written in this file. The remote
      server is the one place tools are defined, so a tool it adds tomorrow
      works here tomorrow.
    - No MCP package is needed at run time. `mcp==2.0.0` requires `uvicorn`
      and `starlette`, which `system3-cli` must not pull (the ticket's
      acceptance). The stdio side of MCP is newline-delimited JSON-RPC and
      the HTTP side is a POST per message, so `httpx` and the standard
      library are enough. The tests drive this module with the MCP SDK's own
      stdio client, which is what proves it speaks the protocol.

The token's handling, since it is the one secret here:

    - It is sent only as the `Authorization` header, only to the origin
      `s3 login` stored, on a client that never follows a redirect, so a
      redirect can never carry it to another host.
    - It is never written to stdout, stderr or an error message.
    - Renewal fails closed. When the refresh is refused, the agent gets an
      error that says to run `s3 login`, never a request sent without a
      token or with a dead one.
    - The access token's expiry is read from its payload WITHOUT verifying
      the signature, only to decide when to renew. Nothing here trusts a
      claim in it; the server verifies every request.

Depends on:
    - httpx (an injected `AsyncClient` whose base URL is the signed-in server)
    - system_03_search_agent.adapters.cli.credentials (`Credentials`,
      `refresh_locked`, `CredentialsError`)
    - system_03_search_agent.adapters.cli.client (`_ChunkSafeLineSplitter`,
      the line splitter `s3 ask` already uses for the event stream)

Reads:
    - stdin: newline-delimited JSON-RPC messages from the MCP client.
    - The credential file, through `credentials.refresh_locked`, only when
      the token needs renewing.

Writes:
    - stdout: JSON-RPC messages, one per line, ASCII only, and nothing else.
    - stderr: one line when it starts, and one line per failure a person
      reading the host's log would need. Never a token.
    - The credential file, through `credentials.refresh_locked`, when the
      token is renewed.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import threading
import time
from collections.abc import Callable
from typing import Any, TextIO

import httpx

from system_03_search_agent.adapters.cli import credentials as credentials_module
from system_03_search_agent.adapters.cli.client import _ChunkSafeLineSplitter
from system_03_search_agent.adapters.cli.render import _sanitize_untrusted

# The remote endpoint. The trailing slash is the mounted path itself: a bare
# `/mcp` answers 307, and this client follows no redirect.
MCP_PATH = "/mcp/"

# `.claude/rules/tool-call-budgets.md`: every outbound call declares its
# timeout. The read leg is long because one `tools/call` waits for a whole
# answer, which the server itself bounds by its per-query budgets; the other
# legs are ordinary request legs.
_REQUEST_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)

# One message from the agent. MCP requests are small (a question and a few
# arguments), so a megabyte is generous and still caps a runaway client.
MAX_INBOUND_LINE_BYTES = 1024 * 1024

# One reply from the server, whether a JSON body or a whole event stream. A
# long answer with every citation, carried twice (structured and as text),
# is a few hundred kilobytes; sixteen megabytes caps a hostile server.
MAX_REMOTE_REPLY_BYTES = 16 * 1024 * 1024

# Renew when the access token has less than this left, so a question that is
# sent just before expiry is not refused mid-flight.
RENEW_WHEN_SECONDS_LEFT = 60.0

# At most this many messages forwarded at once. An agent that sends more
# waits; nothing is dropped.
MAX_IN_FLIGHT = 8

# JSON-RPC error codes. The -32000 range is the server-defined range.
PARSE_ERROR = -32700
SIGN_IN_NEEDED = -32001
REMOTE_UNREACHABLE = -32002
REMOTE_FAILED = -32003

_SIGN_IN_AGAIN = "In a terminal, run: s3 login, then restart this MCP server."


class BridgeError(Exception):
    """A failure the agent is told about as a JSON-RPC error.

    `message` always says what to do next (`production-standards.md`'s
    retry-safety gate: the reader here is an agent, and an actionable error
    is what lets it decide). It never carries a token.
    """

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def access_token_expires_at(token: str) -> float | None:
    """The `exp` claim of a JWT, read WITHOUT verifying the signature.

    Used only to decide when to renew. None when the token is not a JWT or
    carries no numeric `exp`, in which case renewal happens only when the
    server refuses the token."""
    parts = token.split(".")
    if len(parts) != 3:
        return None
    segment = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(segment.encode("ascii")))
    except (ValueError, UnicodeEncodeError, binascii.Error):
        return None
    expiry = claims.get("exp") if isinstance(claims, dict) else None
    if isinstance(expiry, bool) or not isinstance(expiry, int | float):
        return None
    return float(expiry)


def _is_request(message: Any) -> bool:
    return isinstance(message, dict) and "method" in message and "id" in message


def _is_response_to(message: Any, request_id: Any) -> bool:
    return (
        isinstance(message, dict)
        and "method" not in message
        and ("result" in message or "error" in message)
        and message.get("id") == request_id
    )


def _is_token_refusal(message: Any) -> bool:
    """The remote server's answer to a missing or invalid bearer token.

    `adapters/mcp/server.py` raises `MCPError(INVALID_REQUEST, "missing,
    malformed, or invalid bearer token")` before any run starts (T-4.1-03),
    so resending the same message after a renewal can never start a second
    run. Matching the words rather than only the code keeps an ordinary
    invalid request from triggering a renewal."""
    if not isinstance(message, dict):
        return False
    error = message.get("error")
    if not isinstance(error, dict):
        return False
    text = error.get("message")
    return isinstance(text, str) and "bearer token" in text.lower()


def _error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _message_from_credentials_error(exc: Exception) -> str:
    """What the agent is told when renewal fails, in fixed words.

    The credential module's own text can name local paths and, for a
    malformed refresh reply, a response header; the agent needs neither, so
    it gets one of three fixed sentences and the host's log gets the rest."""
    if isinstance(exc, credentials_module.RefreshError):
        return (
            "Your System 3 sign-in has expired or was signed out, so this "
            f"request was not sent. {_SIGN_IN_AGAIN}"
        )
    if isinstance(exc, credentials_module.InsecureCredentialsError):
        return (
            "The s3 credential file on this computer can be read or changed by "
            "other accounts, so it was not used. This server's log names the "
            f"command that fixes its permissions. {_SIGN_IN_AGAIN}"
        )
    return f"The s3 sign-in on this computer could not be used. {_SIGN_IN_AGAIN}"


class McpBridge:
    """Forwards one MCP client's messages to the remote server.

    One instance per `s3 mcp` process. `handle_line` is called once per line
    read from stdin; replies are written through `write_line`, which must
    write one complete line and flush."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        creds: credentials_module.Credentials,
        *,
        write_line: Callable[[bytes], None],
        stderr: TextIO,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._http = http
        self._creds = creds
        self._write_line = write_line
        self._stderr = stderr
        self._clock = clock
        self._renew_lock = asyncio.Lock()
        self._slots = asyncio.Semaphore(MAX_IN_FLIGHT)
        self._protocol_version: str | None = None
        self._session_id: str | None = None
        self._tasks: set[asyncio.Task[None]] = set()
        self._in_flight: dict[str, asyncio.Task[None]] = {}

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def send(self, message: Any) -> None:
        """One JSON-RPC message, one line, ASCII only.

        `ensure_ascii=True` escapes every non-ASCII character, so a raw line
        separator such as U+2028 can never split a message for a client that
        reads lines more broadly than the MCP stdio transport says to."""
        line = json.dumps(message, ensure_ascii=True, separators=(",", ":"))
        self._write_line(line.encode("ascii") + b"\n")

    def log(self, text: str) -> None:
        self._stderr.write(f"s3 mcp: {text}\n")
        self._stderr.flush()

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    async def handle_line(self, line: bytes | None, *, oversized: bool = False) -> None:
        """Dispatch one line from the agent. Returns as soon as the line is
        handed off; a request is answered by its own task."""
        if oversized:
            self.send(
                _error_response(
                    None,
                    PARSE_ERROR,
                    f"The message was larger than {MAX_INBOUND_LINE_BYTES} bytes, so it "
                    "was not sent. Send a shorter message.",
                )
            )
            return
        if line is None or not line.strip():
            return
        try:
            message = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            self.send(
                _error_response(
                    None,
                    PARSE_ERROR,
                    "The message was not valid JSON, so it was not sent. Send one "
                    "JSON-RPC message per line.",
                )
            )
            return

        if _is_request(message) and message.get("method") == "ping":
            # The agent is checking that this process is alive, which it can
            # answer without the network.
            self.send({"jsonrpc": "2.0", "id": message["id"], "result": {}})
            return

        if isinstance(message, dict) and message.get("method") == "notifications/cancelled":
            # The agent gave up on a request. Stop waiting for it, which
            # closes its connection to the server, and send no reply.
            params = message.get("params")
            request_id = params.get("requestId") if isinstance(params, dict) else None
            task = self._in_flight.pop(json.dumps(request_id), None)
            if task is not None:
                task.cancel()
            return

        task = asyncio.create_task(self._forward(message))
        self._tasks.add(task)
        key = json.dumps(message["id"]) if _is_request(message) else None
        if key is not None:
            self._in_flight[key] = task

        def _done(finished: asyncio.Task[None]) -> None:
            self._tasks.discard(finished)
            if key is not None and self._in_flight.get(key) is finished:
                del self._in_flight[key]

        task.add_done_callback(_done)

    async def drain(self) -> None:
        """Wait for every forwarded message to finish, each bounded by its
        own timeout, so a reply already on its way is not cut off."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    # ------------------------------------------------------------------
    # Forwarding
    # ------------------------------------------------------------------

    async def _forward(self, message: Any) -> None:
        is_request = _is_request(message)
        request_id = message["id"] if is_request else None
        async with self._slots:
            try:
                replies = await self._exchange(message, request_id if is_request else _NO_ID)
            except BridgeError as exc:
                if is_request:
                    self.send(_error_response(request_id, exc.code, exc.message))
                else:
                    self.log(exc.message)
                return
        for reply in replies:
            self.send(reply)
        if is_request and not any(_is_response_to(reply, request_id) for reply in replies):
            # Never leave the agent waiting on a request nobody will answer.
            self.send(
                _error_response(
                    request_id,
                    REMOTE_FAILED,
                    "System 3 closed the connection without answering this request. "
                    "Try again.",
                )
            )

    async def _exchange(self, message: Any, request_id: Any) -> list[Any]:
        if isinstance(message, dict) and message.get("method") == "initialize":
            # A new conversation starts with no session and no version.
            self._session_id = None
            self._protocol_version = None
        await self._renew_if_expiring()
        used_token = self._creds.access_token
        replies, refused = await self._post(message, request_id)
        if not refused:
            return replies
        # The server refused the token before doing anything else. Renew
        # once and send the same message once more; if the renewed token is
        # refused too, the agent sees the server's own refusal.
        await self._renew(stale_token=used_token)
        replies_again, refused_again = await self._post(message, request_id)
        if refused_again:
            raise BridgeError(
                SIGN_IN_NEEDED,
                f"System 3 refused your sign-in even after renewing it. {_SIGN_IN_AGAIN}",
            )
        return replies + replies_again

    async def _post(self, message: Any, request_id: Any) -> tuple[list[Any], bool]:
        """Send one message. Returns the replies to pass on, and whether the
        server refused the token (in which case the refusal itself is held
        back, for the caller to retry once)."""
        headers = {
            "Authorization": f"Bearer {self._creds.access_token}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self._protocol_version:
            headers["MCP-Protocol-Version"] = self._protocol_version
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        body = json.dumps(message, ensure_ascii=True).encode("ascii")
        base = str(self._http.base_url).rstrip("/")
        try:
            async with self._http.stream(
                "POST",
                MCP_PATH,
                content=body,
                headers=headers,
                timeout=_REQUEST_TIMEOUT,
                follow_redirects=False,
            ) as response:
                status = response.status_code
                if status == 401:
                    return [], True
                if status == 202:
                    return [], False
                if 300 <= status < 400:
                    raise BridgeError(
                        REMOTE_FAILED,
                        f"System 3 at {base} redirected the request instead of answering "
                        "it. This bridge never follows a redirect, so your sign-in is "
                        "only ever sent to that address. Check the address s3 login used.",
                    )
                if status >= 400:
                    raise BridgeError(
                        REMOTE_FAILED,
                        f"System 3 at {base} answered HTTP {status}. Try again shortly; "
                        "if it keeps happening, the service may be down.",
                    )
                self._remember_session(response)
                content_type = (
                    response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                )
                if content_type == "text/event-stream":
                    replies = await self._read_event_stream(response, request_id)
                elif content_type == "application/json":
                    replies = await self._read_json(response)
                else:
                    raise BridgeError(
                        REMOTE_FAILED,
                        f"System 3 at {base} answered with an unexpected content type, so "
                        "the reply was not passed on. Check that s3 login used the right "
                        "address.",
                    )
        except httpx.TimeoutException as exc:
            raise BridgeError(
                REMOTE_UNREACHABLE,
                f"System 3 at {base} did not answer in time ({type(exc).__name__}). "
                "Try again; a long question can take a minute or two.",
            ) from exc
        except httpx.TransportError as exc:
            raise BridgeError(
                REMOTE_UNREACHABLE,
                f"Could not reach System 3 at {base} ({type(exc).__name__}). Check the "
                "network connection, then try again.",
            ) from exc

        self._remember_protocol_version(message, replies, request_id)
        if request_id is not _NO_ID:
            for index, reply in enumerate(replies):
                if _is_response_to(reply, request_id) and _is_token_refusal(reply):
                    return replies[:index] + replies[index + 1 :], True
        return replies, False

    def _remember_session(self, response: httpx.Response) -> None:
        session = response.headers.get("mcp-session-id")
        if session and len(session) <= 256 and session.isascii() and session.isprintable():
            self._session_id = session

    def _remember_protocol_version(
        self, message: Any, replies: list[Any], request_id: Any
    ) -> None:
        if not (isinstance(message, dict) and message.get("method") == "initialize"):
            return
        for reply in replies:
            if _is_response_to(reply, request_id) and isinstance(reply.get("result"), dict):
                version = reply["result"].get("protocolVersion")
                if isinstance(version, str) and len(version) <= 64 and version.isprintable():
                    self._protocol_version = version

    async def _read_json(self, response: httpx.Response) -> list[Any]:
        raw = bytearray()
        async for chunk in response.aiter_bytes():
            raw.extend(chunk)
            if len(raw) > MAX_REMOTE_REPLY_BYTES:
                raise _too_large()
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise BridgeError(
                REMOTE_FAILED,
                "System 3 sent a reply that was not valid JSON, so it was not passed "
                "on. Try again.",
            ) from exc
        return parsed if isinstance(parsed, list) else [parsed]

    async def _read_event_stream(self, response: httpx.Response, request_id: Any) -> list[Any]:
        """The JSON-RPC messages in an event stream, until the reply to
        `request_id` arrives or the stream ends. A comment line, an `event:`
        line or an `id:` line carries no message and is skipped."""
        splitter = _ChunkSafeLineSplitter()
        replies: list[Any] = []
        data_lines: list[str] = []
        received = 0

        def dispatch() -> bool:
            if not data_lines:
                return False
            text = "\n".join(data_lines)
            data_lines.clear()
            try:
                message = json.loads(text)
            except ValueError as exc:
                raise BridgeError(
                    REMOTE_FAILED,
                    "System 3 sent a reply that was not valid JSON, so it was not "
                    "passed on. Try again.",
                ) from exc
            replies.append(message)
            return request_id is not _NO_ID and _is_response_to(message, request_id)

        def take(line: str) -> bool:
            if line == "":
                return dispatch()
            if line.startswith("data:"):
                value = line[5:]
                data_lines.append(value.removeprefix(" "))
            return False

        async for chunk in response.aiter_bytes():
            received += len(chunk)
            if received > MAX_REMOTE_REPLY_BYTES:
                raise _too_large()
            for line in splitter.feed(chunk):
                if take(line):
                    return replies
        for line in splitter.close():
            if take(line):
                return replies
        dispatch()
        return replies

    # ------------------------------------------------------------------
    # The sign-in
    # ------------------------------------------------------------------

    def _token_is_expiring(self) -> bool:
        token = self._creds.access_token
        if not token:
            return True
        expiry = access_token_expires_at(token)
        return expiry is not None and expiry - self._clock() < RENEW_WHEN_SECONDS_LEFT

    async def _renew_if_expiring(self) -> None:
        if self._token_is_expiring():
            await self._renew(stale_token=self._creds.access_token)

    async def _renew(self, *, stale_token: str | None) -> None:
        """Renew the access token once, however many requests notice at the
        same moment. Fails closed: on any failure the request is not sent."""
        async with self._renew_lock:
            if self._creds.access_token != stale_token and not self._token_is_expiring():
                return  # another request renewed it while this one waited
            try:
                self._creds = await credentials_module.refresh_locked(self._http, self._creds)
            except credentials_module.CredentialsError as exc:
                # The module's text never holds a token, but it can quote a
                # response header, so it is sanitized like any server text
                # before it reaches a terminal or a host's log.
                self.log(f"could not renew the sign-in: {_sanitize_untrusted(str(exc))}")
                raise BridgeError(SIGN_IN_NEEDED, _message_from_credentials_error(exc)) from exc
            except FileNotFoundError as exc:
                raise BridgeError(
                    SIGN_IN_NEEDED, f"You are not signed in to System 3. {_SIGN_IN_AGAIN}"
                ) from exc
            except httpx.HTTPError as exc:
                raise BridgeError(
                    REMOTE_UNREACHABLE,
                    f"Could not reach System 3 to renew your sign-in ({type(exc).__name__}). "
                    "Check the network connection, then try again.",
                ) from exc
            self.log("renewed the sign-in")


# A sentinel for "this message expects no reply", distinct from a JSON null
# id, which a request may legally carry.
_NO_ID = object()


def _too_large() -> BridgeError:
    return BridgeError(
        REMOTE_FAILED,
        f"System 3's reply was larger than {MAX_REMOTE_REPLY_BYTES // (1024 * 1024)} MB, "
        "so it was not passed on. Ask a narrower question.",
    )


def start_line_reader(
    read_line: Callable[[int], bytes], loop: asyncio.AbstractEventLoop
) -> asyncio.Queue[tuple[bytes | None, bool]]:
    """Read stdin on a daemon thread, one line at a time, into a queue.

    A thread rather than the event loop's own pipe reader, because a
    blocking `readline` works the same on every platform and for every kind
    of stdin (a pipe, a file, a test's `BytesIO`). Daemon, so a process that
    is exiting never waits on it. Each item is `(line, oversized)`; `(None,
    False)` means stdin closed. A line longer than `MAX_INBOUND_LINE_BYTES`
    is read to its end and reported as oversized rather than buffered."""
    queue: asyncio.Queue[tuple[bytes | None, bool]] = asyncio.Queue()

    def put(item: tuple[bytes | None, bool]) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, item)

    def run() -> None:
        try:
            while True:
                line = read_line(MAX_INBOUND_LINE_BYTES + 1)
                if not line:
                    break
                if len(line) > MAX_INBOUND_LINE_BYTES and not line.endswith(b"\n"):
                    while line and not line.endswith(b"\n"):
                        line = read_line(MAX_INBOUND_LINE_BYTES + 1)
                    put((None, True))
                    continue
                put((line, False))
        except (OSError, ValueError):
            pass
        put((None, False))

    threading.Thread(target=run, name="s3-mcp-stdin", daemon=True).start()
    return queue


async def serve(
    http: httpx.AsyncClient,
    creds: credentials_module.Credentials,
    *,
    read_line: Callable[[int], bytes],
    write_line: Callable[[bytes], None],
    stderr: TextIO,
) -> int:
    """Run the bridge until stdin closes, then finish what is in flight."""
    bridge = McpBridge(http, creds, write_line=write_line, stderr=stderr)
    base = str(http.base_url).rstrip("/")
    bridge.log(f"forwarding MCP messages to {base}{MCP_PATH} with your s3 sign-in")
    queue = start_line_reader(read_line, asyncio.get_running_loop())
    while True:
        line, oversized = await queue.get()
        if line is None and not oversized:
            break
        await bridge.handle_line(line, oversized=oversized)
    await bridge.drain()
    return 0
