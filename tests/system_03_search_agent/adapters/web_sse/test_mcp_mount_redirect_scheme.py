"""UI fix 11.30, fix B: the `/mcp` mount's trailing-slash redirect must never
downgrade the scheme.

Verified live on 2026-09-20 against
`https://search-agent-api-develop-43b3.up.railway.app` (full account:
`testing/Developer/reports/2026-09-20_integrations/findings.md`):

    POST /mcp   -> HTTP/2 307, Location: http://search-agent-api-develop-...
    POST /mcp/  -> 200, a valid MCP initialize response

The redirect itself, `app.mount("/mcp", ...)` plus Starlette's
`redirect_slashes` behavior (`app.py`'s own comment above the mount
documents why the mount exists at all), is not the defect. Every
spec-compliant client, including the MCP SDK's own default HTTP client,
follows a same-scheme redirect transparently. The defect is that the
`Location` header this app emits, in production, names `http://` for a
request that arrived over `https://`. A client that honors that literally
sends its NEXT request, a bearer token included, over plaintext before a
second redirect brings it back to https.

WHERE THE DOWNGRADE COMES FROM, established here rather than guessed. The
redirect is built by `starlette.routing.Router.app`, which constructs the
`Location` from `URL(scope=redirect_scope)`; that reads `scope["scheme"]`,
which the ASGI server (uvicorn) sets from the RAW connection unless
`ProxyHeadersMiddleware` translates an `X-Forwarded-Proto` header from a
CLIENT ADDRESS uvicorn has been told to trust (`forwarded_allow_ips`,
CLI flag `--forwarded-allow-ips`, default `"127.0.0.1"`). Railway
terminates TLS at its own edge and forwards to this container in plain
HTTP from an address that is not `127.0.0.1`, and `railway.json`'s
`startCommand` passes uvicorn no `--forwarded-allow-ips` override, so the
header is never trusted and the redirect is built from the container's own
plaintext view of the connection.

THIS IS A DEPLOYMENT-CONFIGURATION FACT, NOT SOMETHING `app.py` CAN FIX BY
ITSELF, and this repository already has a considered, on-the-record reason
not to paper over it with an in-code fallback:
`auth/router.py::source_hash_for_request` treats trusting a forwarded
header as a DEPLOYMENT decision precisely because the header is
client-settable, and a control an attacker can opt out of by omitting or
forging it is not a control. Reading `X-Forwarded-Proto` unconditionally in
`app.py` to force the redirect's scheme would be exactly that shape: it
would trust the header from every caller, proxied or not, which is the
`ai-security-standards` "ask before changing auth config" line and the
`v1-scope-boundary` "do not guess at infrastructure" instruction both firing
on the same change. The fix that keeps the boundary intact is telling
uvicorn WHICH connections to trust (`FORWARDED_ALLOW_IPS` or
`--forwarded-allow-ips` naming Railway's proxy, in `railway.json`'s
`startCommand`), which is an infrastructure change this ticket's own
instructions say to stop and report rather than take unilaterally.

So this file's job is narrower than "fix the downgrade": prove exactly
where it comes from, using the real `uvicorn.middleware.proxy_headers.
ProxyHeadersMiddleware` this project already depends on (`uvicorn[standard]`,
`pyproject.toml`) rather than a hand-rolled stand-in, and prove that nothing
in `app.py` reads or trusts the header on its own.
"""

from __future__ import annotations

import httpx
import pytest
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from system_03_search_agent.adapters.web_sse.app import app

# The address Railway's edge is not: loopback. Standing in for "some address
# uvicorn was not told to trust", which is the actual production shape (the
# container never learns Railway's edge IP is 127.0.0.1, because it is not).
_UNTRUSTED_PROXY_ADDRESS = ("203.0.113.5", 12345)


async def _post_mcp_and_read_location(
    *, trusted_hosts: str, client_address: tuple[str, int]
) -> tuple[int, str | None]:
    """POST /mcp through uvicorn's own ProxyHeadersMiddleware, wired exactly
    as it would be by `uvicorn ... --host 0.0.0.0` (proxy_headers=True is
    uvicorn's own CLI default; `trusted_hosts` is what `forwarded_allow_ips`
    controls), and report the redirect this app actually emits.

    The request itself arrives with `scheme="http"`, matching the RAW
    connection uvicorn's HTTP server sees when Railway terminates TLS
    upstream, and carries the `X-Forwarded-Proto: https` header Railway's
    proxy actually sends. That combination is the production shape, not a
    contrived one.
    """
    wrapped = ProxyHeadersMiddleware(app, trusted_hosts=trusted_hosts)
    transport = httpx.ASGITransport(app=wrapped, client=client_address)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.post(
            "/mcp", headers={"x-forwarded-proto": "https"}, follow_redirects=False
        )
        return response.status_code, response.headers.get("location")


@pytest.mark.asyncio
async def test_untrusted_proxy_address_downgrades_the_redirect_scheme() -> None:
    """The reproduction. `forwarded_allow_ips` at its uvicorn default
    (`"127.0.0.1"`), the client address is NOT loopback (Railway's actual
    shape), so `X-Forwarded-Proto: https` is never trusted and the
    `Location` this app emits names `http://` even though the header said
    the real request was https.

    This is the live defect, reproduced from this app's own mount and
    Starlette's own redirect construction, not asserted from documentation.
    """
    status, location = await _post_mcp_and_read_location(
        trusted_hosts="127.0.0.1", client_address=_UNTRUSTED_PROXY_ADDRESS
    )
    assert status == 307
    assert location is not None
    assert location.startswith("http://"), (
        f"expected the untrusted-proxy-address case to reproduce the scheme "
        f"downgrade this app ships with today, got {location!r}. If this "
        "now passes with https, either uvicorn's ProxyHeadersMiddleware "
        "default changed, or this app started trusting the header on its "
        "own; either way the doc comment above needs updating, not this "
        "assertion."
    )


@pytest.mark.asyncio
async def test_a_trusted_proxy_address_would_not_downgrade_the_scheme() -> None:
    """The control. Same request, same headers, the ONLY thing that changes
    is that uvicorn has been told to trust the connecting address. The
    `Location` then correctly reads `https://`.

    This is what makes the arm above a real test of the mechanism rather
    than a test that `/mcp` redirects at all: flipping exactly one input,
    the trust configuration, and nothing about the request, flips the
    scheme. Naming this the fix trades one guess (which address to trust)
    for a bounded one; the specific address is Railway's, which is the part
    this ticket's own instructions say not to guess at, so it is not
    applied here.
    """
    status, location = await _post_mcp_and_read_location(
        trusted_hosts="*", client_address=_UNTRUSTED_PROXY_ADDRESS
    )
    assert status == 307
    assert location is not None
    assert location.startswith("https://"), (
        f"expected trusting the proxy address to produce an https Location, "
        f"got {location!r}. If this fails, ProxyHeadersMiddleware's own "
        "trust semantics changed underneath this test."
    )


def test_app_py_does_not_read_x_forwarded_proto_itself() -> None:
    """A populate-check on the argument this file's docstring makes: that
    the downgrade is entirely a deployment-layer fact and `app.py` contains
    no in-code fallback that reads the header on its own (which would be
    the exact unconditional-trust shape `ai-security-standards` and
    `auth/router.py`'s own reasoning both rule out).

    If this ever goes red because someone added such a fallback, that is
    the signal to re-read this file's docstring before approving it: an
    unconditional read of a client-settable header is not the fix, telling
    uvicorn which connections to trust is.
    """
    import inspect

    from system_03_search_agent.adapters.web_sse import app as app_module

    source = inspect.getsource(app_module)
    assert "x-forwarded-proto" not in source.lower(), (
        "app.py now reads X-Forwarded-Proto directly. That is an "
        "unconditional trust of a client-settable header, the exact shape "
        "`auth/router.py::source_hash_for_request`'s own docstring argues "
        "against for the identical header family; the fix belongs in the "
        "deployment's proxy-trust configuration, not here."
    )
