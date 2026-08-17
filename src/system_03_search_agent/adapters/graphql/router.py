"""The hardened `GraphQLRouter`: build phase 4.3, the second half of ticket
T-4.3-07.

Spec: `tracker/phase_4.3.md`'s "The library, verified against the installed
version rather than the docs", whose table of wrong-for-production defaults
this module is the answer to, and `requirements/Technical_specification.md`
Section 24 (GraphQL is a router mounted in the same FastAPI process).

The whole job of this module is to construct the router with the settings
`security.py` owns, and to be the one place the surface is assembled. It is
separate from `schema.py` so the schema can be built and tested without
constructing an HTTP router around it, the same split the MCP surface used
for its own production-mount test (F-4.1-J-02: mixing per-call-isolated and
singleton-lifespan tests in one file risked a later edit violating a
one-shot constraint).

Nothing here re-decides a bound that `security.py` owns. Every SCHEMA-level
value comes from `security.py`, so a reader auditing what the schema allows
reads exactly one file, and a bound cannot be silently relaxed at the mount
while the security module still claims it.

Three bounds are owned HERE rather than there, and that is structural rather
than a drift from the rule above: all three must act on a request before a
schema exists to act on it.

    - The request timeout cannot live in a schema extension, because the task
      it must cancel is the task that would then have to serialize the
      response. `RequestTimeoutMiddleware`'s own note records the measurement.
    - `MAX_REQUEST_BODY_BYTES` (F-4.3-A-15) is only a cap if it is applied
      before the bytes are read.
    - `MAX_DOCUMENT_NESTING_DEPTH` (F-4.3-A-14) is only a cap if it is applied
      before `graphql.parse` recurses into the document and exhausts the
      stack.

Each is a named module constant whose number is derived at the constant, not
picked.

Depends on:
    - system_03_search_agent.adapters.graphql.context (get_context)
    - system_03_search_agent.adapters.graphql.schema (schema)
    - system_03_search_agent.adapters.graphql.security (ROUTER_SETTINGS,
      REQUEST_TIMEOUT_S, MAX_TOKEN_COUNT, MAX_QUERY_DEPTH)

Reads:
    - The request body, up to `MAX_REQUEST_BODY_BYTES`, which it then replays
      to the application unchanged. `security.py` owns every env-conditional
      value, and its safe state is its default.

Writes:
    - Nothing.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from strawberry.fastapi import GraphQLRouter

from system_03_search_agent.adapters.graphql import security
from system_03_search_agent.adapters.graphql.context import get_context
from system_03_search_agent.adapters.graphql.schema import schema
from system_03_search_agent.adapters.graphql.security import ROUTER_SETTINGS

# The path this surface is mounted at, named here so `app.py` and the premise
# gate cannot disagree about it.
GRAPHQL_PATH = "/graphql"

# F-4.3-A-10. The one alternative spelling this surface answers to. Starlette's
# router has `redirect_slashes=True`, so without this the trailing-slash form
# 307-redirects, and a 307 on a POST is where the request body goes to die:
# a large fraction of HTTP clients and proxies drop the body or downgrade the
# method on a redirect, so the symptom a developer sees is not "you were
# redirected" but "my GraphQL request arrived empty". `app.py` already records
# paying for this exact trap once in the OTHER direction (a bare `POST
# /graphql` 307-redirecting under `app.mount`); this is the mirror case, and
# the fix is to serve both spellings rather than to redirect either.
GRAPHQL_PATH_WITH_SLASH = GRAPHQL_PATH + "/"

# F-4.3-A-15 and J-11. THE bound on how many bytes one request may spend, and
# the reason it has to live at the transport layer rather than in the schema.
#
# `MaxTokensLimiter(1000)` bounds the DOCUMENT. It bounds nothing about the
# `variables` object, and neither does anything else: an adversary probe sent
# roughly 20 MB of entirely unused variables alongside a two-field question,
# and the surface JSON-parsed all of it, created a run, and answered in 0.11
# seconds. That is the cheapest possible asymmetry to hand an attacker, since
# the send costs them one buffer and the serve costs this process a full parse
# and coercion of every byte, on a surface that has no rate limit until build
# phase 6.0.
#
# 256 KiB, and the number is derived rather than picked. The largest request
# this schema can legitimately serve is bounded on both halves: the document
# by `security.MAX_TOKEN_COUNT` (1000 tokens, which at a generous 256 bytes
# per token is 256 KB even if every token were a maximal identifier), and the
# variables by `contracts.query.Query`, whose `text` is capped at 2000
# characters and whose `session_id` is capped at 64. A real request on this
# surface is single-digit kilobytes. 256 KiB therefore sits roughly two orders
# of magnitude above anything a legitimate caller sends and roughly two orders
# of magnitude below the probe, which is the right side of both errors: it
# cannot refuse real traffic, and it turns the unbounded allocation into a
# bounded one.
#
# It is enforced BEFORE authentication, which is deliberate and is a change
# from today's ordering. Bounding the bytes you are willing to read is not a
# privilege check and cannot wait behind one, because reading the request is
# how you authenticate it in the first place. The refusal discloses only this
# module's own cap.
MAX_REQUEST_BODY_BYTES = 256 * 1024

# F-4.3-A-14. THE bound on how deeply a document may nest, enforced here on
# the raw bytes because by the time the schema sees the document it is already
# too late.
#
# graphql-core's parser is recursive descent with no depth bound of its own,
# so a sufficiently nested document exhausts the Python stack inside
# `graphql.parse`. The resulting `RecursionError` is a `builtins` exception,
# which `strawberry.Schema._prepare_operation_async` converts to a bare
# `GraphQLError` and `MaskErrors` then replaces with the generic internal-error
# string, because `builtins` is not on the trusted-module allowlist. The net
# effect measured by the adversary is perverse: a 200-deep document is refused
# with an actionable token-limit message, and a 400-deep document, which is
# strictly LARGER, gets a non-actionable "internal error" instead. Making the
# attack bigger walks past the bound that exists.
#
# It fails closed today (no run is created, no budget is spent, confirmed at
# depths 300 through 2000), so this is a reporting defect rather than a money
# defect. The fix is still to refuse before the parser rather than to report
# the crash more nicely, because the pre-parse refusal is both actionable AND
# removes the stack exhaustion.
#
# 64, and again derived. This schema's own selection-set limit is
# `security.MAX_QUERY_DEPTH = 10`, so any document that survives execution
# nests around 6 levels; 64 is more than six times the depth the schema will
# execute at all, which means this bound can only ever fire on a document the
# schema was going to refuse anyway. The measured parser failure sits between
# 200 and 400 levels under a bare interpreter, and a request served under a
# real ASGI server starts from a much deeper stack than a bare interpreter
# does, so 64 keeps a wide margin on the side that matters.
MAX_DOCUMENT_NESTING_DEPTH = 64

# Error codes this module refuses with. Named rather than inlined so the
# premise gate asserts against the same string the response carries.
BODY_TOO_LARGE_CODE = "REQUEST_BODY_TOO_LARGE"
DOCUMENT_TOO_DEEPLY_NESTED_CODE = "DOCUMENT_TOO_DEEPLY_NESTED"
REQUEST_TIMEOUT_CODE = "REQUEST_TIMEOUT"


def _graphql_error_body(message: str, code: str) -> dict[str, Any]:
    """One GraphQL error envelope, the single response shape this surface
    speaks.

    HTTP 200 with a populated `errors` array, never a 4xx or 5xx: this
    surface reports operation-level outcomes inside the GraphQL envelope, the
    same way a guardrail refusal is a successful response carrying a refusal.
    A caller writes one parser, not two, and every refusal this module can
    produce (oversized body, over-nested document, expired request) therefore
    comes back in the shape the caller already handles.
    """
    return {
        "data": None,
        "errors": [{"message": message, "extensions": {"code": code}}],
    }


def _declared_content_length(scope: Scope) -> int | None:
    """The request's declared `content-length`, or None when it declares one
    that is absent or unparseable.

    A fast path only. An honest client declares its size, so this refuses a
    20 MB body without reading a byte of it. A dishonest or chunked client
    declares nothing, or lies, and is caught by the counting drain below
    instead, which is why this returning None is never a way through.
    """
    for name, value in scope.get("headers") or ():
        if name.lower() == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


async def _drain_bounded_body(receive: Receive) -> tuple[list[Message], bool]:
    """Read the request body, stopping the moment it exceeds
    `MAX_REQUEST_BODY_BYTES`.

    Returns the messages read and whether the cap was blown. The cap is
    enforced on the RUNNING total, so the largest allocation this function can
    make is the cap plus one chunk, whatever the sender claimed or omitted in
    its headers. On the over-cap path the remaining body is deliberately left
    unread: refusing to read it is the entire point of having a cap.

    Buffering here rather than streaming through is safe for this surface
    specifically, because a GraphQL POST body is fully buffered by the library
    downstream regardless; nothing on this path streams a request.
    """
    messages: list[Message] = []
    total = 0
    while True:
        message = await receive()
        messages.append(message)
        if message["type"] == "http.disconnect":
            return messages, False
        total += len(message.get("body") or b"")
        if total > MAX_REQUEST_BODY_BYTES:
            return messages, True
        if not message.get("more_body", False):
            return messages, False


def _replay(messages: list[Message]) -> Receive:
    """Hand an already-drained body back to the application unchanged.

    The ORIGINAL messages are replayed byte for byte. Nothing downstream sees
    a re-encoded body, so the inspection this middleware performs cannot
    change what the schema parses.
    """
    remaining = iter(messages)

    async def receive() -> Message:
        try:
            return next(remaining)
        except StopIteration:
            return {"type": "http.disconnect"}

    return receive


def _max_nesting_depth(document: str) -> int:
    """The deepest run of nested `{`, `(` or `[` in a GraphQL document,
    counting only STRUCTURAL brackets.

    A bracket inside a string literal or a comment is text, not structure, so
    this skips both. GraphQL has three such regions and all three are handled:
    a block string (`\"\"\"..."\"\"`), an ordinary string (with backslash
    escapes), and a `#` comment to end of line. Missing any of them would let
    a user's question ("what does {BRCA1} regulate?") inflate the count toward
    a bound it has no business approaching.

    Unbalanced closers drive the running depth negative, which is harmless:
    the maximum is what is returned, and a malformed document is the parser's
    problem to report, not this function's.
    """
    depth = 0
    maximum = 0
    index = 0
    length = len(document)
    while index < length:
        char = document[index]
        if char == "#":
            newline = document.find("\n", index)
            index = length if newline == -1 else newline + 1
            continue
        if char == '"':
            if document.startswith('"""', index):
                end = document.find('"""', index + 3)
                index = length if end == -1 else end + 3
                continue
            index += 1
            while index < length:
                if document[index] == "\\":
                    index += 2
                    continue
                if document[index] == '"':
                    index += 1
                    break
                index += 1
            continue
        if char in "{([":
            depth += 1
            maximum = max(maximum, depth)
        elif char in "})]":
            depth -= 1
        index += 1
    return maximum


def _document_is_too_deeply_nested(messages: list[Message]) -> bool:
    """Whether the buffered body carries a document this process must not
    hand to `graphql.parse`.

    Anything unreadable returns False rather than refusing. A body that is not
    JSON, or carries no `query` string, is a request the schema layer already
    rejects with its own actionable message, and inventing a second, wronger
    refusal here would take that message away from the caller. This function
    has exactly one job and declines every other one.

    `json.loads` recursing to death on a deeply nested JSON body is caught
    here too, and is treated as a refusal for the same reason the document
    case is: a body that cannot be decoded without exhausting the stack is not
    a body this process should keep working on.
    """
    body = b"".join(message.get("body") or b"" for message in messages)
    if not body:
        return False
    try:
        payload = json.loads(body)
    except RecursionError:
        return True
    except Exception:  # noqa: BLE001 - any malformed body is the schema's to report
        return False
    if not isinstance(payload, dict):
        return False
    document = payload.get("query")
    if not isinstance(document, str):
        return False
    return _max_nesting_depth(document) > MAX_DOCUMENT_NESTING_DEPTH


class RequestTimeoutMiddleware:
    """THE per-request wall-clock bound for this surface, and the reason it
    lives here rather than in a schema extension.

    Strawberry ships no timeout, so one had to be built (`tool-call-
    budgets.md`: a call path with no declared timeout is not finished). The
    obvious place was a `SchemaExtension`, and that was built first, and it
    did not work, in a way worth recording because the failure looked like
    success. `asyncio.timeout` inside an extension bounds the request by
    CANCELLING THE RUNNING TASK. The cancel fired on time, converted to
    `TimeoutError`, and the extension's handler set a correct short-circuit
    result. The request still died with `CancelledError`, because the task
    that was cancelled is the same task that then has to serialize the
    response: suppressing the error at one point in that task does not undo
    the cancellation, and `Task.uncancel()` did not either.

    So the bound is enforced here instead, one layer out, where the fix is
    structural rather than defensive. The GraphQL request runs as a CHILD
    task under `asyncio.wait_for`. On expiry the CHILD is cancelled and
    discarded, and this parent task, which was never cancelled and is
    therefore perfectly healthy, writes an ordinary GraphQL error response.
    A caller gets an actionable error rather than a dropped connection.

    `security.REQUEST_TIMEOUT_S` is read through the MODULE on every request,
    never captured at import, so a test or a future reconfiguration that
    reassigns it takes effect on the very next request. Binding it at import
    would turn the premise gate's timeout arm into a test that cannot fail,
    which is this repository's single most repeated failure class.

    Non-HTTP scopes (a websocket handshake, a lifespan message) pass through
    untouched: there is no HTTP response to write for them, and this surface
    advertises no subscription protocol anyway. So does every path outside
    this surface: it is installed app-wide, because that is how ASGI
    middleware attaches, but it bounds only its own surface and costs every
    other route one string comparison.

    It also carries this surface's two INPUT bounds, and they live here rather
    than in `security.py` for the same structural reason the timeout does: both
    have to act on the request before the schema exists to act on. A body cap
    (F-4.3-A-15) is only a cap if it is applied before the bytes are read, and
    a nesting cap (F-4.3-A-14) is only a cap if it is applied before
    `graphql.parse` recurses into the document. Every refusal this class can
    produce comes back in one shape, `_graphql_error_body`, with a code.

    F-4.3-A-11: the path test is an EXACT match against this surface's own two
    spellings, not a prefix test. `startswith("/graphql")` also matched
    `/graphqlXYZ` and `/graphql-admin`, which cost nothing today because
    nothing answers on those paths, and would silently wrap the first future
    route named under a `/graphql` prefix in this surface's request timeout
    and this surface's GraphQL-shaped response body, which for a non-GraphQL
    route is the wrong shape entirely. The docstring above already claimed the
    middleware "bounds only its own surface"; the code now says it too.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or path not in (GRAPHQL_PATH, GRAPHQL_PATH_WITH_SLASH):
            await self.app(scope, receive, send)
            return

        if path != GRAPHQL_PATH:
            # F-4.3-A-10: serve the trailing-slash spelling instead of
            # redirecting it, so the body survives. The scope is COPIED rather
            # than mutated, so anything outside this middleware (a server's
            # access log, most usefully) still sees the URL the caller
            # actually requested.
            scope = {**scope, "path": GRAPHQL_PATH}
            if scope.get("raw_path") is not None:
                scope["raw_path"] = GRAPHQL_PATH.encode("ascii")

        declared_length = _declared_content_length(scope)
        if declared_length is not None and declared_length > MAX_REQUEST_BODY_BYTES:
            await self._refuse(scope, receive, send, *_body_too_large())
            return

        messages, over_cap = await _drain_bounded_body(receive)
        if over_cap:
            await self._refuse(scope, receive, send, *_body_too_large())
            return
        receive = _replay(messages)

        if _document_is_too_deeply_nested(messages):
            await self._refuse(scope, receive, send, *_document_too_deeply_nested())
            return

        timeout_s = security.REQUEST_TIMEOUT_S
        try:
            await asyncio.wait_for(self.app(scope, receive, send), timeout=timeout_s)
        except TimeoutError:
            # F-4.3-A-17. This used to say the operation "was aborted", which
            # was false about the only thing the caller is billed for. What
            # `asyncio.wait_for` cancels is the child task serving THIS
            # REQUEST. The run itself is a separate background task created by
            # `default_registry.create_run`, deliberately independent of the
            # request that started it (that independence is what lets a caller
            # reconnect and keep watching), and nothing on this path calls
            # `cancel_run`.
            #
            # Cancelling the run here was considered and is not cleanly
            # reachable from this layer: the middleware never learns the
            # `runId`, because the run is created inside a resolver and the
            # response carrying its id is exactly the response that never
            # arrived. Threading the id back out would mean the resolver
            # publishing it into the ASGI scope for the middleware to read,
            # which is a change to `schema.py` and a new coupling between the
            # transport and the resolver layer. So the message is corrected
            # instead of the behaviour, and it now says plainly that the spend
            # continues and that retrying starts a SECOND run rather than
            # replacing the first. A caller told the truth can decide; a
            # caller told "aborted" retries into a doubled bill.
            await self._refuse(scope, receive, send, *_request_timed_out(timeout_s))

    @staticmethod
    async def _refuse(
        scope: Scope, receive: Receive, send: Send, message: str, code: str
    ) -> None:
        await JSONResponse(_graphql_error_body(message, code), status_code=200)(
            scope, receive, send
        )


def _body_too_large() -> tuple[str, str]:
    return (
        (
            f"This GraphQL request body exceeds this surface's "
            f"{MAX_REQUEST_BODY_BYTES // 1024} KiB limit and was refused without being "
            "read. The document itself is separately capped at "
            f"{security.MAX_TOKEN_COUNT} tokens, so a body this size is almost always "
            "oversized `variables`. Send the question as a variable rather than "
            "inlining large data, and remove any variables the document does not use."
        ),
        BODY_TOO_LARGE_CODE,
    )


def _document_too_deeply_nested() -> tuple[str, str]:
    return (
        (
            f"This GraphQL document nests deeper than this surface's "
            f"{MAX_DOCUMENT_NESTING_DEPTH}-level limit and was refused before parsing. "
            f"This schema executes at most {security.MAX_QUERY_DEPTH} levels of "
            "selection, so flatten the document: remove redundant inline fragments "
            "and fragment nesting, and select fewer nested fields."
        ),
        DOCUMENT_TOO_DEEPLY_NESTED_CODE,
    )


def _request_timed_out(timeout_s: float) -> tuple[str, str]:
    return (
        (
            f"This GraphQL operation exceeded this surface's {timeout_s:.0f}s request "
            "timeout, so no result will be returned on this connection. The run itself "
            "was NOT stopped and continues to execute and to bill server-side; this "
            "surface cannot address it, because the response carrying its runId is the "
            "one that timed out. Retrying starts a SECOND run alongside the first. "
            "Retry with a narrower question, or select fewer fields."
        ),
        REQUEST_TIMEOUT_CODE,
    )


# `context_getter` is what makes auth run BEFORE any GraphQL parsing or
# execution: FastAPI resolves it through the ordinary dependency graph, so
# `context.get_context` raising means no resolver runs, no run is created,
# and no model or tool budget is spent on an unauthenticated caller.
graphql_router: GraphQLRouter = GraphQLRouter(
    schema,
    context_getter=get_context,
    **ROUTER_SETTINGS,
)
