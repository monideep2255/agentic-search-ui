"""UI fix 11.30, fix B: the `/mcp` mount's trailing-slash redirect must never
downgrade the scheme.

REWRITTEN 2026-09-23, when the fix landed. This file previously proved where
the downgrade came from and argued that application code must not fix it. The
first half was right and is kept below. The second half is now false, and the
history is kept rather than deleted because the argument it made is a good one
that the fix had to answer rather than override.

Verified live on 2026-09-20 against
`https://search-agent-api-develop-43b3.up.railway.app` (full account:
`testing/Developer/reports/2026-09-20_integrations/findings.md`):

    POST /mcp   -> HTTP/2 307, Location: http://search-agent-api-develop-...
    POST /mcp/  -> 200, a valid MCP initialize response

The redirect itself, `app.mount("/mcp", ...)` plus Starlette's
`redirect_slashes` behavior, is not the defect. Every spec-compliant client
follows a same-scheme redirect transparently. The defect is that the `Location`
this app emits, in production, names `http://` for a request that arrived over
`https://`. A client that honors it literally sends its NEXT request, bearer
token included, over plaintext before a second redirect brings it back.

WHERE THE DOWNGRADE COMES FROM, unchanged and still proven by the two arms
below. The redirect is built by `starlette.routing.Router.app`, which
constructs the `Location` from `URL(scope=redirect_scope)`; that reads
`scope["scheme"]`, which uvicorn sets from the RAW connection unless
`ProxyHeadersMiddleware` translates an `X-Forwarded-Proto` header arriving from
a client address uvicorn has been told to trust (`forwarded_allow_ips`, default
`"127.0.0.1"`). Railway terminates TLS at its own edge and forwards to this
container in plain HTTP from an address that is not loopback, and
`railway.json`'s `startCommand` passes no `--forwarded-allow-ips` override, so
the header is never trusted and the redirect is built from the container's own
plaintext view of the connection.

WHAT THIS FILE USED TO CONCLUDE, AND WHY THAT CHANGED. It concluded that this
was a deployment fact application code must not paper over, because reading
`X-Forwarded-Proto` in `app.py` would trust a client-settable header from every
caller. It cited `auth/router.py::source_hash_for_request`, which refuses to
read any forwarded header because "a control an attacker can opt out of is not
a control". Its third arm asserted that `app.py` contains no such read.

That objection was correct about the danger and wrong about the only remedy, in
two ways that only became visible once the alternative was costed.

- The remedy it recommended is WORSE, not safer. Telling uvicorn to trust the
  proxy address (`--forwarded-allow-ips`) also makes uvicorn rewrite
  `scope["client"]` from `X-Forwarded-For`, taking the LEFTMOST entry, which the
  caller controls end to end. Two controls here hash the client address for rate
  limiting, so that switch would have traded a plaintext redirect for a sign-in
  rate-limit bypass. It also needs Railway's edge address, an infrastructure
  fact this container cannot verify from inside itself.
- The danger is removable rather than merely manageable. `proxy_scheme.py`
  UPGRADES ONLY: the header can move the scheme to `https` and can never move it
  to `http`. So no value a caller can put in that header makes any redirect less
  secure than it is with the header absent, which is a stronger guarantee than
  trusting an address, and it is the guarantee the arms below pin.

`source_hash_for_request`'s reasoning is untouched by this and remains correct
on its own terms: the client ADDRESS still comes from the connection and never
from a header, and `proxy_scheme.py` never touches `scope["client"]`. The two
positions are compatible because they are about different fields with different
blast radii, which is the distinction this file previously did not draw.
"""

from __future__ import annotations

import httpx
import pytest
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from system_03_search_agent.adapters.web_sse.app import app


def _untrusted_address() -> tuple[str, int]:
    """An address uvicorn was not told to trust, standing in for Railway's edge.

    The container never learns that Railway's edge is loopback, because it is
    not, so this is the production shape rather than a contrived one.
    """
    return ("203.0.113.5", 12345)


async def _post_mcp(
    *,
    trusted_hosts: str,
    forwarded_proto: str | None,
) -> tuple[int, str | None]:
    """POST /mcp through uvicorn's own ProxyHeadersMiddleware and report the redirect.

    The request arrives with `scheme="http"`, matching the raw connection
    uvicorn sees when Railway terminates TLS upstream, and carries whatever
    `x-forwarded-proto` the caller is simulating.
    """
    wrapped = ProxyHeadersMiddleware(app, trusted_hosts=trusted_hosts)
    transport = httpx.ASGITransport(app=wrapped, client=_untrusted_address())
    headers = {} if forwarded_proto is None else {"x-forwarded-proto": forwarded_proto}
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.post("/mcp", headers=headers, follow_redirects=False)
        return response.status_code, response.headers.get("location")


@pytest.mark.asyncio
async def test_untrusted_proxy_address_no_longer_downgrades_the_redirect() -> None:
    """THE FIX, stated as the inverse of what this arm used to assert.

    `forwarded_allow_ips` is at uvicorn's default, the client address is not
    loopback, so uvicorn itself discards the header exactly as it did before.
    The `Location` is `https` anyway, because `proxy_scheme.py` reads the header
    inside the application, which is what makes the fix travel with the code
    instead of living in a deployment setting that the develop and production
    services could silently disagree about.

    Would fail against the pre-fix tree, where this same call produced `http://`.
    """
    status, location = await _post_mcp(trusted_hosts="127.0.0.1", forwarded_proto="https")
    assert status == 307
    assert location is not None
    assert location.startswith("https://"), (
        f"expected the app's own middleware to produce an https Location even "
        f"with an untrusted proxy address, got {location!r}"
    )


@pytest.mark.asyncio
async def test_a_forged_http_header_cannot_force_a_downgrade() -> None:
    """THE SECURITY PROPERTY, and the reason application code may read this
    header at all.

    A caller sends `x-forwarded-proto: http`, which is the one thing an attacker
    would actually want from a header the application reads: make the app emit a
    plaintext `Location` for a request that was not plaintext. It does not work.
    `_forwarded_scheme` returns None for anything that is not `https`, so the
    scheme falls back to what the server itself observed.

    Populate check: the assertion below is not "the header was ignored", which
    would pass vacuously on a request that never carried one. The paired arm
    above proves the header IS read when it says `https`, so the two together
    show the read is real and the downgrade direction is closed.

    Would fail against an implementation that accepted `http` from the header,
    which is exactly what the first version of `proxy_scheme.py` did.
    """
    status, location = await _post_mcp(trusted_hosts="127.0.0.1", forwarded_proto="http")
    assert status == 307
    assert location is not None
    assert location.startswith("http://"), (
        f"a forged `http` must leave the server's own scheme alone, got {location!r}"
    )

    _, upgraded = await _post_mcp(trusted_hosts="127.0.0.1", forwarded_proto="https")
    assert upgraded is not None and upgraded.startswith("https://"), (
        "the control for the arm above: the header must genuinely be read when "
        f"it says https, otherwise the assertion above proves nothing, got {upgraded!r}"
    )


@pytest.mark.asyncio
async def test_no_header_leaves_the_scheme_the_server_observed() -> None:
    """Local development, and any deployment with no TLS-terminating proxy, are
    unchanged. No header, no rewrite, `http` in and `http` out.

    This is what makes the fix safe to carry in code rather than in a per-service
    deployment setting: with nothing in front of the app, it behaves exactly as
    it did before the fix existed.
    """
    status, location = await _post_mcp(trusted_hosts="127.0.0.1", forwarded_proto=None)
    assert status == 307
    assert location is not None
    assert location.startswith("http://"), (
        f"with no forwarded header the server's own scheme must stand, got {location!r}"
    )


@pytest.mark.asyncio
async def test_trusting_the_proxy_address_reaches_the_same_place() -> None:
    """The rejected alternative, kept as a control and as documentation.

    Telling uvicorn to trust the connecting address also produces an https
    `Location`, which is why it looked like the obvious one-line fix. It was
    rejected because the same switch rewrites `scope["client"]` from the
    caller-controlled leftmost `X-Forwarded-For` entry, and two controls in this
    system hash the client address for rate limiting. This arm exists so that
    the alternative stays visible and measured rather than becoming folklore.
    """
    status, location = await _post_mcp(trusted_hosts="*", forwarded_proto="https")
    assert status == 307
    assert location is not None
    assert location.startswith("https://")
