"""Session-wide test configuration.

## Finding 4 (MAJOR, re-review, build phase 3.1): the unit suite is not hermetic

`tests/system_03_search_agent/adapters/web_sse/test_streaming_endpoints.py`
used "What gene is BRCA1?" as its query text and was the only agent-loop
test file that had not been given the `_stub_symbol_resolution`-style
fixture the other three agent-loop test files carry
(`tests/system_03_search_agent/core/test_graph.py:115`,
`tests/system_03_search_agent/core/test_run.py:91`,
`tests/system_03_search_agent/adapters/web_sse/test_query_endpoint.py:109`).
A judge proved a live GET to `api.ncbi.nlm.nih.gov` during a plain
`pytest tests/ -q` run: the suite's green depended on NCBI being up, and
it silently burned E-utilities quota every run.

Stubbing that one file closes the symptom, not the defect. The next new
agent-loop test file can reintroduce the identical leak, and nothing
would catch it until it flaked in CI or tripped a rate limit against a
shared NCBI pool (`tool-call-budgets.md`'s "live integration tests must
not trip their own rate limits"). This fixture is the durable fix: a
session-scoped, autouse hard fail at the one place in this codebase that
ever opens a REAL outbound HTTP connection,
`system_03_search_agent.tools.ncbi_transport.execute_get`'s bare
`httpx.AsyncClient()` (see that module's own comment on why it is
per-call rather than a module-level singleton). Any future test file
that forgets to stub `resolve_symbol_to_curie` or pass a fake `client=`
now fails loudly and immediately, in that test, rather than silently
succeeding against the real network.

## Why this patches the transport layer, not `httpx.AsyncClient.get`

The FastAPI test clients in this suite
(`tests/system_03_search_agent/adapters/web_sse/test_streaming_endpoints.py`,
`test_query_endpoint.py`, and the `starlette.testclient.TestClient` used
by `test_health.py`, `test_router.py`) also call `.get()`/`.post()` on an
`httpx.AsyncClient` or `httpx.Client`, but routed through an in-process
ASGI transport (`httpx.ASGITransport` or Starlette's own
`_TestClientTransport`), never through the network. Patching
`httpx.AsyncClient.get` at the class level would block those in-process
calls too, since the patch cannot distinguish which transport a given
client instance was built with. Patching `httpx.AsyncHTTPTransport.
handle_async_request` and `httpx.HTTPTransport.handle_request` instead,
the transport classes that actually perform DNS and socket I/O, blocks
only genuine outbound network calls and leaves every ASGI-routed test
client completely unaffected, since those clients are built with a
different transport class entirely.

## The one exemption: the live premise gate

`tests/system_03_search_agent/tools/test_ncbi_efetch_premise.py` is
deliberately, explicitly live: its own module docstring states "the
network call is not mocked" as one of the four properties the gate
requires, because a mocked NCBI response tests what the author already
believed the API sends, which is precisely the belief the gate exists to
check. That file is already gated behind the `RUN_PREMISE_GATE=1`
opt-in (`_opted_in()`/`premise_gate` in that module); this fixture reads
the exact same environment variable and stands entirely aside when it is
set, so `RUN_PREMISE_GATE=1 pytest tests/system_03_search_agent/tools/
test_ncbi_efetch_premise.py` keeps reaching the real endpoints exactly as
before.

Depends on:
    - httpx (patches AsyncHTTPTransport.handle_async_request and
      HTTPTransport.handle_request for the duration of the test session)

Reads:
    - Environment variable: RUN_PREMISE_GATE (the same opt-in
      tests/system_03_search_agent/tools/test_ncbi_efetch_premise.py
      already defines and uses)

Writes:
    - Nothing.
"""

from __future__ import annotations

import os

import httpx
import pytest

# Mirrors test_ncbi_efetch_premise.py's own `_OPT_IN_VAR` exactly. Not
# imported from that module: this file must stand up before any test
# module import is guaranteed to have happened, and duplicating one
# string constant is cheaper than coupling conftest.py's collection-time
# behavior to a single test file's internals.
_PREMISE_GATE_OPT_IN_VAR = "RUN_PREMISE_GATE"


def _premise_gate_is_active() -> bool:
    return os.environ.get(_PREMISE_GATE_OPT_IN_VAR, "").strip().lower() in {"1", "true", "yes"}


class LiveHttpCallInUnitSuiteError(RuntimeError):
    """Raised in place of a real outbound HTTP call from the unit suite.

    Fix by passing a fake `client=` (see test_ncbi_transport.py's or
    test_ncbi_coordinate_overlap.py's `_FakeClient`), by monkeypatching
    the specific `execute_get`-calling function, or, for a full agent-loop
    test, by stubbing `system_03_search_agent.core.graph.
    resolve_symbol_to_curie` the way test_graph.py, test_run.py, and
    test_query_endpoint.py already do. If this call is genuinely meant to
    reach live NCBI, it belongs in the RUN_PREMISE_GATE=1 gate
    (test_ncbi_efetch_premise.py), not the plain unit run.
    """


async def _blocked_async_handle_request(
    self: httpx.AsyncHTTPTransport, request: httpx.Request
) -> httpx.Response:
    raise LiveHttpCallInUnitSuiteError(
        f"Unit suite attempted a live async HTTP request to {str(request.url)!r}. "
        f"See tests/conftest.py's LiveHttpCallInUnitSuiteError docstring for how to fix it."
    )


def _blocked_sync_handle_request(self: httpx.HTTPTransport, request: httpx.Request) -> httpx.Response:
    raise LiveHttpCallInUnitSuiteError(
        f"Unit suite attempted a live sync HTTP request to {str(request.url)!r}. "
        f"See tests/conftest.py's LiveHttpCallInUnitSuiteError docstring for how to fix it."
    )


@pytest.fixture(autouse=True, scope="session")
def _forbid_live_http_in_the_unit_suite():
    """The durable fix Finding 4 asked for, not merely the one-file stub.

    Session-scoped so the patch is installed once and every test in the
    run, regardless of file, is covered, including test files written
    after this fixture was added. Autouse so no test file has to opt in.
    """
    if _premise_gate_is_active():
        # The live premise gate needs real network reach. Stand aside
        # entirely rather than patching and immediately restoring, so a
        # `RUN_PREMISE_GATE=1` run of any other test file in the same
        # session is unaffected either way.
        yield
        return

    original_async_handler = httpx.AsyncHTTPTransport.handle_async_request
    original_sync_handler = httpx.HTTPTransport.handle_request
    httpx.AsyncHTTPTransport.handle_async_request = _blocked_async_handle_request
    httpx.HTTPTransport.handle_request = _blocked_sync_handle_request
    try:
        yield
    finally:
        httpx.AsyncHTTPTransport.handle_async_request = original_async_handler
        httpx.HTTPTransport.handle_request = original_sync_handler
