"""One implementation of "is the Layer 1 graph reachable right now".

Build phase 4.12. Before this module, EIGHT premise-gate files each carried
their own byte-identical copy of a reachability probe, and every one of them
was wrong in the same way: they opened a TCP socket to `GRAPH_PG_HOST` and
`GRAPH_PG_PORT`, the local port of an SSH tunnel that build phase 4.11
deleted.

The consequence was not a failing test, which is what makes it worth a module
of its own. On a machine where the graph is perfectly reachable over HTTPS,
every arm behind one of those probes SKIPPED, and printed a skip reason that
was false, several of them telling the reader to reopen a tunnel that no
longer exists. A green run then reads as "this class is covered" when the arms
did not run at all, which is the same shape as a gate arm that cannot fail.

## Why one module rather than eight corrected copies

Eight copies of a probe that must not drift IS the drift problem. This
repository has already paid for that twice: `check_drift.sh` exists because a
second copy of the validator on the graph box could silently become a
different validator, and F-4.6-A-08's fix was explicit that there be "exactly
ONE writer implementation". Correcting eight copies would have left eight
places for the next transport change to be applied seven times.

## The rule this follows

`tracker/preflight.py`'s `probe_graph` states it, and this module deliberately
mirrors it rather than inventing a second policy:

    That module dispatches on GRAPH_QUERY_URL, so this one does too: probing
    the psycopg2 port while the tool is talking HTTPS would report on a
    transport nothing is using, which is worse than not probing at all,
    because it looks like an answer.

So the dispatch here matches `graph_connection.execute_cypher`'s own: if
`GRAPH_QUERY_URL` is set, the HTTPS service is the transport and its health
endpoint is what gets probed. Only when it is unset does the direct
`GRAPH_PG_*` connection apply, and only then is a socket probe meaningful.

The legacy branch is kept rather than deleted because `graph_connection.py`
still has that fallback. A probe that could not follow the code down its
other branch would be a second policy, which is the thing this module exists
to prevent.

## What this does NOT tell you

It answers "did something answer", never "is the graph healthy". The health
endpoint is deliberately unauthenticated and returns 200 once the proxy, the
certificate and the service process are up; it does not prove the AGE graph
behind it is answering queries. An arm that needs that must assert on its own
query result, not on this function.

It also cannot distinguish a closed port from a filtered one. This harness
renders "nothing listening" and "blocked by the sandbox" identically, as a
timeout (`LEARNINGS.md`, 2026-08-22, where that ambiguity cost a wrong
blocker reported to the product owner and an infrastructure credential
requested for a firewall that does not exist). A `False` from this function
means "do not run the live arm", never "the graph is down".

Depends on:
    - Nothing in `src/`. Stdlib only, deliberately, so importing it from a
      conftest or a gate cannot pull the application into a test that meant
      to stay offline.

Reads:
    - `.env`, for `GRAPH_QUERY_URL`, `GRAPH_PG_HOST`, `GRAPH_PG_PORT`.
"""

import http.client
import os
import socket
import ssl
from pathlib import Path

__all__ = [
    "SKIP_REASON",
    "graph_is_reachable",
    "live_graph_arms_enabled",
    "live_network_is_permitted",
    "load_env_explicitly",
]

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The one skip reason these gates print. It names the variable that decides
#: the transport rather than an operator action, because the previous reason
#: named an operator action ("reopen the tunnel") that stopped being possible
#: when build phase 4.11 deleted the tunnel, and nothing updated it.
SKIP_REASON = (
    "the live graph did not answer. Layer 1 dispatches on GRAPH_QUERY_URL: "
    "when it is set, the read-only HTTPS query service is the transport and "
    "its /healthz endpoint must answer; when it is unset, GRAPH_PG_HOST and "
    "GRAPH_PG_PORT must accept a connection. Check .env and "
    "`python3 tracker/preflight.py --transport graph`"
)


def load_env_explicitly() -> None:
    """Populate os.environ from `.env` without adding a dependency.

    `setdefault`, never assignment, so a value already exported in the shell
    wins. Deliberately the same seven lines `tracker/preflight.py` uses, and
    for the reason stated there: adding python-dotenv to a diagnostic path
    would take it off CLAUDE.md's portability list to save nothing.
    """
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _https_service_answers(service_url: str, timeout: float) -> bool:
    """Probe the query service's unauthenticated health endpoint.

    Any HTTP status counts as an answer. Comparing against 200 would make the
    probe fail on an endpoint requiring auth, which is a false alarm, and a
    guard that cries wolf gets ignored and then protects nothing. That is
    `preflight.py`'s reasoning and it applies unchanged here.
    """
    if not service_url.startswith("https://"):
        return False
    host = service_url.split("://", 1)[1].split("/", 1)[0]
    conn = None
    try:
        conn = http.client.HTTPSConnection(
            host, timeout=timeout, context=ssl.create_default_context()
        )
        conn.request("HEAD", "/healthz")
        conn.getresponse()
        return True
    except (OSError, ssl.SSLError, http.client.HTTPException):
        return False
    finally:
        if conn is not None:
            # Narrow, not blind. Closing a connection that never opened raises
            # OSError or an http.client error; anything else is a real defect
            # in this helper and should surface rather than be swallowed by a
            # cleanup path.
            try:
                conn.close()
            except (OSError, http.client.HTTPException):
                pass


def graph_is_reachable(timeout: float = 8.0) -> bool:
    """Whether Layer 1 answers right now, over whichever transport is live.

    Checked fresh per call rather than once at import (finding F-2.1-B12).
    That reasoning survives the tunnel's deletion intact: a remote service can
    stop answering mid-session just as a tunnel could drop, and a guard
    evaluated at import cannot notice either.

    The default timeout is 8 seconds rather than the 3 the tunnel-era probes
    used. Measured 2026-08-24: the HTTPS service answers in roughly 350ms
    warm, and a cold first TLS negotiation through this harness's proxy has
    been observed exceeding 6 seconds and being reported as `down` by
    `preflight.py`, which was a false alarm. A too-tight timeout on a live
    check produces exactly the silent, false skip this module exists to end.
    """
    load_env_explicitly()

    service_url = os.environ.get("GRAPH_QUERY_URL")
    if service_url:
        return _https_service_answers(service_url, timeout)

    host = os.environ.get("GRAPH_PG_HOST")
    port = os.environ.get("GRAPH_PG_PORT")
    if not host or not port:
        return False
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def live_network_is_permitted() -> bool:
    """Whether `tests/conftest.py` is letting real outbound HTTP through.

    A separate fact from `graph_is_reachable`, and keeping them separate is
    the point. The graph can be perfectly reachable from this machine while
    this process is forbidden to talk to it.
    """
    load_env_explicitly()
    return os.environ.get("RUN_PREMISE_GATE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def live_graph_arms_enabled(timeout: float = 8.0) -> bool:
    """May this process run an arm that reaches the live graph?

    BOTH facts, and this function exists because getting that wrong has now
    happened twice in this repository in opposite directions.

    - Before build phase 4.12, eight gates asked only "is the graph
      reachable" and asked it of a deleted tunnel, so the answer was always
      no and every live arm skipped while printing a false reason.
    - Correcting that probe alone immediately produced the OTHER failure, and
      it was measured rather than reasoned about: with the probe answering
      truthfully, arms that had been skipping began to RUN in the ordinary
      offline suite, hit `tests/conftest.py`'s block, and FAILED. One file
      went from a clean skip to `6 failed` in 169 seconds. That is exactly
      the shape of `test_citation_trust_full_premise.py`'s `live_only` mark,
      which gated on a credential existing and produced this repository's
      standing six-failure baseline.

    So "the dependency answers" and "this process may talk to it" are two
    facts, a gate needs both, and neither is a proxy for the other. Gating on
    one and calling it the other is the safety-by-proxy shape build phase 4.3
    shipped as a critical twice.

    `graph_is_reachable` is deliberately NOT changed to fold the permission
    check into itself. A function named "is it reachable" that answers "am I
    allowed" is a lie at the call site, and the next reader would have to
    discover it the way this one was discovered.
    """
    return live_network_is_permitted() and graph_is_reachable(timeout)
