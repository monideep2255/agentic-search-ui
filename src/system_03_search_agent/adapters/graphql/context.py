"""Auth and context: build phase 4.3, ticket T-4.3-03.

Spec: `tracker/phase_4.3.md`'s "Module contracts" section and scope
reading 2 ("The surface is registered-account only, with no guest path").

This module is the ONE place this surface decides who is calling. It runs
as a FastAPI dependency (`get_context`, wired to `GraphQLRouter`'s own
`context_getter=` parameter by T-4.3-07's router), so FastAPI resolves it
before the GraphQL handler ever parses or executes a document. A caller
with a missing, malformed, expired, or unknown-user token, or a genuinely
valid GUEST token, never reaches a resolver and never causes a run to be
created: `get_context` raises `fastapi.HTTPException` directly, which
FastAPI's own exception handling turns into a response before `GraphQL
Router.run(...)` is ever called (verified against the installed
`strawberry-graphql==0.324.0` router source: `context_getter` is wired as
a `Depends(...)` sub-dependency of the POST/GET route functions, resolved
strictly before their bodies run).

Registered accounts only, deliberately. `get_caller` (`auth/dependencies.
py`) resolves a guest token exactly as happily as a registered user's
access token, and importing it here would open a second, unhardened
anonymous-allowance path on this surface with one import. This module
therefore reuses `resolve_user_from_bearer_token`, the registered-only
path `get_current_user` already uses, never `get_caller`. Full argument:
`tracker/phase_4.3.md` scope reading 2, three reasons in order of weight:
the guest allowance is an ORDERING (precheck, spend, create_run, refund on
refusal), not one function, and reproducing that ordering here doubles a
surface the product owner has already accepted a known residual on; a
guest token exists to spare a first-time web visitor from signing up
before asking one question, and a GraphQL client is a developer
integration by construction, so there is no first-contact anonymous
visitor to serve; and the direction of the error is safe; refusing a
guest is a recoverable inconvenience, letting guest allowance be spent
through an unhardened second path is not.

Depends on:
    - strawberry.fastapi (BaseContext)
    - system_03_search_agent.auth.dependencies (InvalidBearerTokenError,
      has_bearer_scheme, resolve_user_from_bearer_token): the exact
      decode-then-lookup logic `get_current_user` already uses.
    - system_03_search_agent.auth.guest (decode_guest_token): to tell a
      genuinely valid guest token apart from a bogus credential, so the
      two get different, non-identical refusals.
    - system_03_search_agent.data.models (User)
    - system_03_search_agent.data.session (get_session)

Reads:
    - The `Authorization` request header on every GraphQL request, via the
      ambient `starlette.requests.Request` FastAPI injects into this
      dependency.

Writes:
    - Nothing.

Never logs the raw `Authorization` header, the decoded token, or any
token value in an exception string or HTTP response body: only literal
field names and fixed sentences appear in any message this module
produces, the same discipline `auth/dependencies.py` holds itself to.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from starlette.requests import Request
from strawberry.fastapi import BaseContext

from system_03_search_agent.auth.dependencies import (
    InvalidBearerTokenError,
    has_bearer_scheme,
    resolve_user_from_bearer_token,
)
from system_03_search_agent.auth.guest import decode_guest_token
from system_03_search_agent.data.models import User
from system_03_search_agent.data.session import get_session

# ---------------------------------------------------------------------------
# Exception base. One class, no enumerated subclasses to catch: the two
# refusal shapes this module produces (a generic invalid credential, and an
# actionable guest refusal) are carried as STRUCTURAL attributes on this one
# exception type (status_code, detail), the same pattern `core/run_registry.
# py`'s `ConcurrentRunCapExceededError.bound` already uses, rather than a
# subclass per shape. tracker/phase_4.3.md calls this out by name: an
# enumerated catch list drifted out of sync with its raiser three separate
# times inside build phase 4.2 alone, and `get_context` below has exactly
# one `except GraphQLAuthError:` site.
# ---------------------------------------------------------------------------


class GraphQLAuthError(Exception):
    """Raised internally by `_resolve_registered_principal`. `get_context`
    is the single catch site and translates this into `HTTPException`.
    """

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


# Matches auth/dependencies.py's single-detail-string discipline for every
# failure mode EXCEPT the guest case below: a missing header, a malformed
# scheme, an empty token, an undecodable access token, and a guest-shaped
# token that itself fails to decode all collapse to this one sentence, so
# none of them discloses which check tripped.
_INVALID_CREDENTIAL_DETAIL = "invalid or expired credentials"

# Deliberate, reasoned exception to the single-string discipline above,
# per tracker/phase_4.3.md's own instruction to write the reasoning down
# rather than let a future reader "simplify" it back. auth/dependencies.py
# collapses every failure to one string so a 401 can never tell an
# attacker which check tripped; that threat model does not apply here,
# because reaching this branch already REQUIRES the caller to hold a
# token that verifies as a genuine, signed, unexpired guest token (`decode
# _guest_token` succeeded below). The caller already knows, with
# certainty, that it is holding a guest token; telling them so discloses
# nothing they did not already have. This is not an enumeration oracle
# (it reveals no information about anyone else's credentials or about
# which check an INVALID token failed), and tool-call-budgets.md's
# actionability rule then requires the message say what to do next, not
# only what is wrong.
_GUEST_REFUSAL_DETAIL = (
    "this bearer token is a guest credential; the GraphQL API is "
    "registered-account only, sign in or create an account to obtain an "
    "access token, then retry this request with that token"
)

# "Bearer " and "bearer " are both 7 characters; has_bearer_scheme already
# matched the scheme case-insensitively (F-4.1-A-12's precedent), so a
# fixed-length slice is safe regardless of the caller's casing. Mirrors
# auth/dependencies.py's own `_BEARER_SCHEME_LOWER`-length slice rather
# than importing that module's private, underscore-prefixed constant
# across a module boundary.
_BEARER_PREFIX_LENGTH = len("Bearer ")


def _extract_bearer_header(request: Request) -> str | None:
    """Read the raw `Authorization` header off the incoming GraphQL
    request.

    Mirrors `adapters/mcp/server.py`'s `_extract_bearer_header` (F-4.1-A-11):
    a genuine DUPLICATE `Authorization` header (two distinct values on one
    request, not a casing variant, which Starlette's `Headers.get` already
    merges case-insensitively) is treated as absent rather than resolved
    first-wins, since this surface has no way to know whether a fronting
    proxy authorizes on the first value, the last value, or rejects the
    request outright; picking one silently would be a confused-deputy risk
    for whichever caller assumed the other convention. `request.headers`
    is Starlette's own `Headers` type for every transport this surface
    serves (HTTP POST/GET; T-4.3-04 disables the WebSocket upgrade path
    entirely), so `getlist` is always available here; the `hasattr` guard
    is defensive only, matching the MCP precedent's own reasoning.
    """
    headers = request.headers
    if hasattr(headers, "getlist") and len(headers.getlist("authorization")) > 1:
        return None
    return headers.get("authorization")


def _resolve_registered_principal(authorization: str | None, session: Session) -> User:
    """Resolve a registered `User` from a raw `Authorization` header value,
    or raise `GraphQLAuthError`.

    Reuses `resolve_user_from_bearer_token` verbatim (the exact decode-
    then-lookup logic `get_current_user` uses on the REST surface), never
    `get_caller`, per this module's own docstring and scope reading 2.

    A token that fails the registered-user path is not immediately
    reported as generically invalid: it is checked against
    `decode_guest_token` first, because the two token families are signed
    with cryptographically domain-separated keys (`auth/guest.py`'s own
    module docstring), so this is a deterministic dispatch on which of two
    disjoint keys actually verifies, not an ambiguous heuristic, the same
    reasoning `resolve_caller_from_bearer_token` already documents for its
    own two-path fallback.

    Raises:
        GraphQLAuthError: for every failure mode, carrying `status_code`
            401 and the generic detail for a missing, malformed, empty,
            undecodable, or unknown-user token; carrying `status_code` 403
            and the actionable guest-specific detail for a token that
            verifies as a genuine guest token.
    """
    if not has_bearer_scheme(authorization):
        raise GraphQLAuthError(status.HTTP_401_UNAUTHORIZED, _INVALID_CREDENTIAL_DETAIL)
    assert authorization is not None  # narrowed by has_bearer_scheme above

    try:
        return resolve_user_from_bearer_token(authorization, session)
    except InvalidBearerTokenError:
        pass  # not a valid registered-user token; check the guest path below.

    token = authorization[_BEARER_PREFIX_LENGTH:].strip()
    try:
        decode_guest_token(token)
    except (TypeError, ValueError):
        # Neither a valid access token nor a valid guest token. Generic
        # detail: this branch must not disclose that a guest-shaped check
        # was even attempted, matching auth/dependencies.py's discipline.
        raise GraphQLAuthError(status.HTTP_401_UNAUTHORIZED, _INVALID_CREDENTIAL_DETAIL) from None

    # decode_guest_token succeeded: a genuine, signed, unexpired guest
    # token. See _GUEST_REFUSAL_DETAIL's own comment for why naming
    # "guest" here is safe rather than an enumeration oracle.
    raise GraphQLAuthError(status.HTTP_403_FORBIDDEN, _GUEST_REFUSAL_DETAIL)


class GraphQLContext(BaseContext):
    """The context every resolver on this surface reads. `request` is set
    by `strawberry.fastapi.GraphQLRouter` itself immediately after
    `get_context` returns (verified against the installed router source:
    the wrapping dependency assigns `custom_context.request = request` for
    any `BaseContext` subclass), never by this module.
    """

    def __init__(self, principal: User) -> None:
        super().__init__()
        self.principal = principal


async def get_context(
    request: Request,
    session: Session = Depends(get_session),  # noqa: B008 - idiomatic FastAPI dependency injection
) -> GraphQLContext:
    """The `context_getter` `GraphQLRouter` is constructed with (T-4.3-07).

    Runs, and can fail, strictly BEFORE any GraphQL document is parsed or
    executed: see this module's own docstring for why that ordering holds
    against the installed Strawberry version. `HTTPException` raised here
    is what makes that ordering real, not merely documented: FastAPI's own
    exception handling turns it into a response during dependency
    resolution, so no resolver, and therefore no `RunRegistry.create_run`,
    is ever reached for an unauthenticated or guest caller.
    """
    authorization = _extract_bearer_header(request)
    try:
        principal = _resolve_registered_principal(authorization, session)
    except GraphQLAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    return GraphQLContext(principal=principal)
