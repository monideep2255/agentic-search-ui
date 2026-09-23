"""Trust the edge proxy's `x-forwarded-proto`, and nothing else about it.

Item 11.30 fix B, 2026-09-22. A `POST` to `/mcp` with no trailing slash answered
`307` with `location: http://...`, a scheme downgrade from HTTPS to plaintext on
a public endpoint. Fix A already stopped the Integrations page printing the
address that triggers it; this module stops the downgrade happening at all.

Depends on:
    - Nothing. Pure ASGI, no imports from this package.

Reads:
    - The request's `x-forwarded-proto` header only.

Writes:
    - `scope["scheme"]`, and no other key of the ASGI scope.

THE MECHANISM, established by live reproduction on develop rather than assumed.
Railway terminates TLS at its edge and forwards plain HTTP to this app with
`X-Forwarded-Proto: https`. Uvicorn's own proxy-header handling is enabled by
default but `--forwarded-allow-ips` defaults to `127.0.0.1`, and Railway's proxy
is not on loopback, so the header is discarded and the scope keeps
`scheme: "http"`. Starlette's `Mount` builds its trailing-slash redirect as an
ABSOLUTE url from that scope, so the `Location` it emits is plaintext. Followed
literally, the plaintext hop answers `301` back to HTTPS, a `301` drops the
`POST` method and body, and a real MCP client hangs in `initialize()`.

WHY THIS IS NOT `--forwarded-allow-ips='*'`, which is the one-line fix and was
REJECTED. That switch also makes uvicorn rewrite the client address from
`X-Forwarded-For`, and uvicorn takes the LEFTMOST entry of that header, which
the caller controls end to end. Two controls in this system read the client
address: `auth/router.py` hashes it for the sign-in rate limit (lines 284 and
314), and `data/guest_sessions.py` binds a guest session to it. Turning the
switch on would therefore hand any caller a way to forge their address and walk
past the sign-in rate limit. A plaintext redirect is worth fixing; it is not
worth a rate-limit bypass.

AND IT UPGRADES ONLY, NEVER DOWNGRADES. The header can move the scheme to
`https` and can never move it to `http`, so no value a caller can put in it
makes a redirect less secure than it is with the header absent. That is what
answers the standing objection in this repository to reading a client-settable
header in application code at all, and `_forwarded_scheme` below carries the
full argument. It also removes the need for a trusted-hop list, which would
mean guessing at an infrastructure fact from inside the container.

So this middleware trusts the SCHEME and never the ADDRESS. `scope["client"]`
is left exactly as the server set it, which means the identity every existing
rate limit reads does not move by one byte. `tests/.../test_proxy_scheme.py`
asserts that directly, and that arm is the point of the design: if this module
ever starts trusting the address, it goes red.

A CONSEQUENCE WORTH KNOWING, recorded rather than silently accepted, and NOT
changed here because it is the product owner's call. Because the address is not
rewritten, every caller behind the edge proxy shares one address, so the
per-address sign-in rate limit is effectively global rather than per person.
That is PRE-EXISTING and unchanged by this module. Fixing it properly needs the
number of trusted hops in front of this app, which is a deployment fact to
confirm with the platform rather than a value to guess at, and guessing it wrong
reintroduces exactly the spoofing hole the paragraph above refuses.

WHY IN THE APP RATHER THAN IN THE START COMMAND. The fix travels with the code,
is covered by the same gates as the code, and is visible to anyone reading the
app. A deployment setting in `railway.json` is none of those things, and it is
also per-service, so the develop and production apps could silently disagree.
"""

from collections.abc import Awaitable, Callable
from typing import Any

#: THE ONLY VALUE THIS MODULE EVER ACTS ON, and the narrowness is the whole
#: security argument rather than a simplification. See `_forwarded_scheme`.
_UPGRADE_SCHEME = "https"


def _forwarded_scheme(headers: list[tuple[bytes, bytes]]) -> str | None:
    """`"https"` when the header asks for it, else None. It can never return `"http"`.

    UPGRADE ONLY, NEVER DOWNGRADE, and this is the answer to the strongest
    objection against reading this header in application code at all. That
    objection is on the record in two places in this repository:
    `auth/router.py::source_hash_for_request` refuses to read any forwarded
    header because "a control an attacker can opt out of is not a control", and
    `tests/.../test_mcp_mount_redirect_scheme.py` argued from it that the scheme
    downgrade was a deployment fact that application code must not paper over.

    Both are right that `x-forwarded-proto` is client-settable and therefore
    cannot be trusted. The resolution is not to trust it more carefully, it is
    to make the only thing an attacker could want from it unreachable:

    - A forged `https` on a genuinely plaintext connection makes a redirect name
      `https`. That is the safe direction, and nothing else in this application
      reads the scheme (verified across `src/` on 2026-09-22: no secure-cookie
      flag, no `https_only`, no `url_for`), so the blast radius is one
      `Location` header pointing at TLS.
    - A forged `http` on a genuine HTTPS request is what would actually hurt
      somebody, because it is the very downgrade item 11.30 exists to close. It
      is unreachable here: `http` is not `_UPGRADE_SCHEME`, so this returns None
      and the caller keeps the scheme the server itself observed.

    So there is no input to this header that makes the redirect less secure than
    it is with the header absent. That is a stronger guarantee than trusting a
    proxy address, which is why it needs no trusted-hop list and no
    infrastructure fact guessed at from outside the container.

    The header is a comma-separated list when a request crosses more than one
    proxy, and its FIRST entry is the one the original client spoke to. Case is
    not significant in the value, so it is folded before comparison.
    """
    for name, value in headers:
        if name.lower() != b"x-forwarded-proto":
            continue
        first = value.decode("latin-1").split(",")[0].strip().lower()
        return _UPGRADE_SCHEME if first == _UPGRADE_SCHEME else None
    return None


class ProxySchemeMiddleware:
    """Set `scope["scheme"]` from `x-forwarded-proto`. Touch nothing else.

    Pure ASGI rather than a `BaseHTTPMiddleware` subclass, on purpose: this has
    to run OUTSIDE the router so the scope is already corrected by the time
    `Mount` builds a trailing-slash redirect from it, and it must not buffer or
    re-frame a response, since this app streams every answer over SSE.
    """

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[..., Awaitable[Any]],
        send: Callable[..., Awaitable[None]],
    ) -> None:
        if scope["type"] in ("http", "websocket"):
            scheme = _forwarded_scheme(scope.get("headers") or [])
            if scheme is not None:
                # A new dict, never a mutation of the caller's: an ASGI server
                # may reuse a scope across a request's lifetime, and a
                # middleware that edits in place makes that reuse its problem.
                scope = {**scope, "scheme": scheme}
        await self.app(scope, receive, send)
