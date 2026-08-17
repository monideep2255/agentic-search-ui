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

Nothing here re-decides a bound. Every value comes from `security.py`, so a
reader auditing what this surface allows reads exactly one file, and a bound
cannot be silently relaxed at the mount while the security module still
claims it.

Depends on:
    - system_03_search_agent.adapters.graphql.context (get_context)
    - system_03_search_agent.adapters.graphql.schema (schema)
    - system_03_search_agent.adapters.graphql.security (ROUTER_SETTINGS)

Reads:
    - Nothing directly. `security.py` owns every env-conditional value, and
      its safe state is its default.

Writes:
    - Nothing.
"""

from __future__ import annotations

import asyncio

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send
from strawberry.fastapi import GraphQLRouter

from system_03_search_agent.adapters.graphql import security
from system_03_search_agent.adapters.graphql.context import get_context
from system_03_search_agent.adapters.graphql.schema import schema
from system_03_search_agent.adapters.graphql.security import ROUTER_SETTINGS

# The path this surface is mounted at, named here so `app.py` and the premise
# gate cannot disagree about it.
GRAPHQL_PATH = "/graphql"


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
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith(GRAPHQL_PATH):
            await self.app(scope, receive, send)
            return

        timeout_s = security.REQUEST_TIMEOUT_S
        try:
            await asyncio.wait_for(self.app(scope, receive, send), timeout=timeout_s)
        except TimeoutError:
            # HTTP 200 with a populated `errors` array, not a 4xx or 5xx:
            # this surface reports operation-level outcomes inside the
            # GraphQL envelope, the same way a guardrail refusal is a
            # successful response carrying a refusal. A caller parses one
            # shape, never two.
            await JSONResponse(
                {
                    "data": None,
                    "errors": [
                        {
                            "message": (
                                f"This GraphQL operation exceeded this surface's "
                                f"{timeout_s:.0f}s request timeout and was aborted before "
                                "finishing. Retry with a narrower question, or select "
                                "fewer fields."
                            ),
                            "extensions": {"code": "REQUEST_TIMEOUT"},
                        }
                    ],
                },
                status_code=200,
            )(scope, receive, send)


# `context_getter` is what makes auth run BEFORE any GraphQL parsing or
# execution: FastAPI resolves it through the ordinary dependency graph, so
# `context.get_context` raising means no resolver runs, no run is created,
# and no model or tool budget is spent on an unauthenticated caller.
graphql_router: GraphQLRouter = GraphQLRouter(
    schema,
    context_getter=get_context,
    **ROUTER_SETTINGS,
)
