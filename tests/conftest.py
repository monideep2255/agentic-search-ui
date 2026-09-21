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
import requests

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


def _blocked_requests_send(self: requests.adapters.HTTPAdapter, request, **kwargs):
    """Block a live call made through `requests`, which httpx patching cannot see.

    F-5.0-07, build phase 5.0. The two httpx blockers above were written
    when `ncbi_transport.execute_get` was genuinely the only place in this
    codebase that opened a real outbound connection, and they are patched
    at the transport classes that perform DNS and socket I/O precisely so
    in-process ASGI test clients are unaffected. That reasoning is right
    and is reused verbatim here.

    What changed is the premise. The installed langsmith drives its HTTP
    through `requests`, not httpx (38 references in its `client.py`), so
    once build phase 5.0 wires tracing there is a second library that can
    reach the network and nothing above can see it. Until a LANGSMITH_API_
    KEY existed this was latent, because `tracing_enabled()` requires both
    the flag and a key. A key now exists, which turns a dormant gap into a
    live one: without this blocker a plain `pytest` run would ship real
    traces of test data, including whatever a fixture used as a question,
    to a real LangSmith project.

    Patched at `HTTPAdapter.send` for the same reason the httpx blockers
    sit at the transport: it is the layer that actually performs I/O, so a
    library that mounts its own adapter or a test that injects a fake
    session is left alone.
    """
    url = getattr(request, "url", "<unknown>")
    raise LiveHttpCallInUnitSuiteError(
        f"Unit suite attempted a live `requests` HTTP call to {str(url)!r}. "
        "This is most likely LangSmith tracing: set LANGSMITH_API_KEY empty "
        "for the suite, or disable tracing in the test. See tests/conftest.py's "
        "LiveHttpCallInUnitSuiteError docstring."
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
    original_requests_send = requests.adapters.HTTPAdapter.send
    httpx.AsyncHTTPTransport.handle_async_request = _blocked_async_handle_request
    httpx.HTTPTransport.handle_request = _blocked_sync_handle_request
    requests.adapters.HTTPAdapter.send = _blocked_requests_send
    try:
        yield
    finally:
        httpx.AsyncHTTPTransport.handle_async_request = original_async_handler
        httpx.HTTPTransport.handle_request = original_sync_handler
        requests.adapters.HTTPAdapter.send = original_requests_send


def _user_db_engine_is_stale() -> bool:
    """True when a process-wide user-data engine exists and was built from a
    different `USER_DB_URL` than the one the environment carries right now."""
    from sqlalchemy.engine import make_url

    from system_03_search_agent.data import base

    engine = base._engine
    if engine is None:
        return False
    ambient = os.environ.get("USER_DB_URL")
    if not ambient:
        return True
    try:
        return make_url(ambient) != engine.url
    except Exception:  # noqa: BLE001 - an unparseable ambient URL is a mismatch, not a crash
        return True


def _drop_stale_user_db_engine() -> None:
    from system_03_search_agent.data import base, session

    if _user_db_engine_is_stale():
        base.reset_engine()
        session.reset_session_factory()


@pytest.fixture(autouse=True)
def _user_db_engine_matches_the_ambient_url():
    """The process-wide user-data engine never outlives the `USER_DB_URL` it was built from.

    CI run 34892563076 (2026-09-14) and every push after it: three tests in
    `tests/system_03_search_agent/core/test_think_retry.py` failed with
    `fe_sendauth: no password supplied` from
    `Engine(postgresql://localhost:5432/search_agent_users)`, a URL with no
    user and no password, while CI's own `USER_DB_URL` carried
    `postgres:postgres@`. The URL had not come from the environment. Nine
    test files `monkeypatch.setenv("USER_DB_URL", ...)` to that credential-
    less form (the first in collection order is
    `core/test_clarification.py`); the first of them to touch the database
    builds `data/base.py`'s `_engine` singleton from it, `monkeypatch`
    restores the environment variable at teardown, and the engine, which is
    module state rather than environment state, survives into every later
    test in the process. On a developer's machine the credential-less URL
    happens to work through trust authentication, so the leak is invisible
    locally and red in CI. Reproduced locally with
    `PGUSER=<nonexistent role>` and a user-bearing ambient `USER_DB_URL`,
    which fails the credential-less URL and keeps the ambient one working,
    CI's exact asymmetry: the same three tests fail.

    Why a guard on BOTH sides of every test rather than a teardown in the
    nine files: the next file to set `USER_DB_URL` would reintroduce the
    leak, and teardown-only ordering depends on whether this fixture or the
    test's `monkeypatch` tears down first. Checking at setup makes the
    invariant hold regardless of collection order or fixture order: a test
    starts with either no engine or an engine that matches the environment
    it is about to run under. Checking again at teardown returns the process
    to that state as early as possible. A stale engine is disposed, and the
    session factory bound to it (`data/session.py`) is cleared with it, since
    a factory bound to a disposed engine is the same leak one layer up.

    The `reset_engine()` calls that `core/test_feedback_capture_premise.py`,
    `feedback/test_writer.py` and `feedback/test_capture_bypasses.py` already
    make inside their own fixtures are unaffected: those tests then build an
    engine that matches the URL they set, which this guard leaves alone.
    """
    _drop_stale_user_db_engine()
    try:
        yield
    finally:
        _drop_stale_user_db_engine()
