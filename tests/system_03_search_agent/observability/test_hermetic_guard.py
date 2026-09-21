"""The suite's outbound-call guard must cover `requests`, not only httpx.

F-5.0-07. `tests/conftest.py` has blocked live outbound calls since build
phase 3.1 by patching the two httpx transport classes that perform DNS and
socket I/O. That was complete when it was written, because
`ncbi_transport.execute_get` was genuinely the only place in this codebase
that opened a real connection.

Build phase 5.0 breaks that premise. The installed langsmith drives its
HTTP through `requests` rather than httpx, so once tracing is wired there
is a second library that can reach the network and the httpx patches
cannot see it. The gap was dormant only because `tracing_enabled()`
requires both the tracing flag and an API key, and no key existed. A key
now exists, so a plain `pytest` run without this guard would ship real
traces of test data to a real LangSmith project.

These arms exist because that guard is otherwise invisible: nothing else
in the suite fails if someone removes the `requests` patch, and the
symptom of its absence is silent data exfiltration rather than a red test.
Both arms construct a real call attempt rather than asserting the patch is
installed, since an arm that checks for the patch's presence passes even
when the patch does not work.
"""

import httpx
import pytest
import requests

from tests.conftest import LiveHttpCallInUnitSuiteError


def test_a_requests_call_is_blocked() -> None:
    """The F-5.0-07 arm.

    Fails if the `requests`-layer patch is removed from conftest, which is
    the regression that would let LangSmith tracing reach the network from
    the unit suite. Uses a host that would not resolve anyway, so a failure
    here means the guard did not fire rather than that the network was
    reachable.
    """
    with pytest.raises(LiveHttpCallInUnitSuiteError):
        requests.get("https://api.smith.langchain.com/does-not-matter", timeout=1)


def test_a_requests_session_call_is_blocked() -> None:
    """Sessions are the path langsmith actually uses.

    `requests.get` builds a throwaway Session internally, so the arm above
    would pass even if only that convenience wrapper were patched. This one
    goes through an explicitly constructed Session, which is what a library
    holding a long-lived client does, and pins that the patch sits at the
    adapter rather than at the module-level helper.
    """
    with pytest.raises(LiveHttpCallInUnitSuiteError), requests.Session() as session:
        session.post("https://api.smith.langchain.com/runs", json={}, timeout=1)


def test_the_httpx_guard_still_works() -> None:
    """The pre-existing guard is not regressed by adding the new one.

    Cheap to assert and worth asserting: the edit that added the `requests`
    patch also touched the install and restore block that these two share,
    which is exactly the shape of change that silently drops one of them.
    """
    with pytest.raises(LiveHttpCallInUnitSuiteError):
        httpx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi", timeout=1)


@pytest.mark.asyncio
async def test_an_in_process_asgi_client_is_not_blocked() -> None:
    """The guard must not break in-process test clients.

    This is the over-blocking arm, and it is the one most likely to be
    missing. conftest patches the transport classes rather than
    `httpx.Client.get` specifically so that ASGI-routed clients, which
    never touch a socket, keep working. An arm that only proves calls are
    blocked would stay green if the guard were widened until it broke every
    FastAPI test in the suite.
    """

    async def app(scope, receive, send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/")
    assert response.text == "ok"
