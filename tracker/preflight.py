#!/usr/bin/env python3
"""One probe per transport, run before dispatching anything expensive.

Why this exists
---------------
`docs/build/Build_velocity_post_mortem.md` ranks this priority 1: on 2026-08-03
an estimated 1 to 1.5 hours went to agent dispatches that died against a dead
connection, and twice the outage was read as a defect in the work rather than as
an outage, which cost debugging time on top of the dead dispatch.

Its 2026-08-04 correction is the part that matters, and the reason a single
`curl` was not enough. There is more than one independent transport in play, and
a green probe against one says nothing about the others:

    product-model   the product's own model provider (OpenRouter).
                    Gates: premise-gate runs, and any test that calls
                    harness.call_tier.
                    A dead run here costs 6 to 10 minutes.

    harness-model   the build harness's own provider, a different endpoint.
                    Gates: EVERY agent dispatch, so judge, adversary, builder,
                    researcher, fix agent.
                    A dead dispatch here costs 15 to 25 minutes, and this is the
                    transport the post-mortem records as having no probe written
                    down anywhere in the repository. This file is that probe.

    graph           the Layer 1 AGE graph over TCP.
                    Gates: any tool-phase premise gate or live graph test.

WHAT THIS DOES NOT CHECK, stated so the gap is arguable rather than discovered
-----------------------------------------------------------------------------
- It proves a transport answers, never that it answers CORRECTLY. A provider
  returning 503 to every request will probe `ok` here, because the failure mode
  this guards is a dead or stalled connection, which is what actually happened.
- It is a point-in-time sample. A transport can die in the second after a green
  probe. This lowers the odds of a wasted dispatch, it does not remove them.
- It cannot always tell a sandbox denial from a real outage. Both surface as a
  connection failure at this layer. When a probe reports `down` for a host you
  have not allowlisted, suspect the allowlist first; the output says so.
- It says nothing about model quality, rate limits, quota, or cost caps.
- It does not probe the enrichment APIs (Layer 3) or NCBI E-utilities (Layer 2).
  Those are per-tool concerns with their own timeouts and are not what a
  dispatch dies against.

Usage
-----
    python3 tracker/preflight.py                     # probe every transport
    python3 tracker/preflight.py --transport harness-model
    python3 tracker/preflight.py --timeout 5

Exit codes
----------
    0   every transport that could be probed answered
    1   at least one transport is down; do not dispatch what it gates
    2   bad invocation

A transport whose configuration is absent reports `skipped`, not `ok`, and does
not fail the run. `skipped` means nothing was verified, which is different from
a verified pass, and the summary keeps the two apart on purpose.
"""

from __future__ import annotations

import argparse
import http.client
import os
import socket
import ssl
import sys
import time

# Endpoint per transport. Overridable by environment so this file never needs
# editing when a host moves, and so a test can point it at a dead host.
HTTPS_TRANSPORTS = {
    "product-model": (
        os.environ.get("PREFLIGHT_PRODUCT_MODEL_HOST", "openrouter.ai"),
        os.environ.get("PREFLIGHT_PRODUCT_MODEL_PATH", "/api/v1/models"),
        "premise-gate runs, and any test calling harness.call_tier",
    ),
    "harness-model": (
        os.environ.get("PREFLIGHT_HARNESS_MODEL_HOST", "api.anthropic.com"),
        os.environ.get("PREFLIGHT_HARNESS_MODEL_PATH", "/"),
        "every agent dispatch: judge, adversary, builder, researcher, fix agent",
    ),
}

GRAPH_GATES = "tool-phase premise gates, and any live graph test"

OK, DOWN, SKIPPED = "ok", "down", "skipped"


def probe_https(host: str, path: str, timeout: float) -> tuple[str, str]:
    """Return (state, detail). Any HTTP status proves the transport answered.

    A status code is deliberately not compared against 200. This guard exists to
    catch a dead or stalled connection, and a 401 or 404 is a live server, which
    is the whole question being asked. Comparing against 200 would make the
    probe fail on an endpoint that requires auth, which is a false alarm, and a
    guard that cries wolf gets ignored and then protects nothing.
    """
    started = time.monotonic()
    conn = None
    try:
        conn = http.client.HTTPSConnection(
            host, timeout=timeout, context=ssl.create_default_context()
        )
        conn.request("HEAD", path)
        status = conn.getresponse().status
        ms = int((time.monotonic() - started) * 1000)
        return OK, f"HTTP {status} in {ms}ms"
    except ssl.SSLError as exc:
        return DOWN, f"TLS failed: {type(exc).__name__}"
    except socket.timeout:
        return DOWN, f"no response within {timeout:g}s"
    except OSError as exc:
        # Covers refused, unreachable, DNS failure, and a sandbox denial. These
        # are not distinguishable here; see the coverage note in the docstring.
        return DOWN, f"{type(exc).__name__}: {exc}"
    finally:
        if conn is not None:
            conn.close()


def probe_graph(timeout: float) -> tuple[str, str]:
    """TCP reachability for the Layer 1 graph, from the same env the tool reads.

    Variable names match `graph_connection.py` so this probe and the real
    connection cannot drift apart. Only host and port are read: a credential is
    never needed to answer "is the port open", and reading one here would put a
    secret in a diagnostic script for no gain.
    """
    host = os.environ.get("GRAPH_PG_HOST")
    port_raw = os.environ.get("GRAPH_PG_PORT", "5432")
    if not host:
        return SKIPPED, "GRAPH_PG_HOST is unset, so there is no tunnel to probe"
    try:
        port = int(port_raw)
    except ValueError:
        # The variable name, never its value: an invalid port is not a secret,
        # but keeping the habit uniform is what stops the one that is.
        return DOWN, "GRAPH_PG_PORT is set to a non-integer value"

    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            ms = int((time.monotonic() - started) * 1000)
            return OK, f"TCP {port} open in {ms}ms"
    except socket.timeout:
        return DOWN, f"TCP {port} did not answer within {timeout:g}s"
    except OSError as exc:
        return DOWN, f"TCP {port}: {type(exc).__name__}: {exc}"


def run(selected: list[str], timeout: float) -> int:
    results: list[tuple[str, str, str, str]] = []

    for name in selected:
        if name == "graph":
            state, detail = probe_graph(timeout)
            gates = GRAPH_GATES
        else:
            host, path, gates = HTTPS_TRANSPORTS[name]
            state, detail = probe_https(host, path, timeout)
            detail = f"{host} {detail}"
        results.append((name, state, detail, gates))

    width = max(len(name) for name, _, _, _ in results)
    for name, state, detail, _ in results:
        print(f"  {name:<{width}}  {state:<7}  {detail}")

    down = [(n, g) for n, s, _, g in results if s == DOWN]
    skipped = [n for n, s, _, _ in results if s == SKIPPED]

    print()
    if down:
        print("NOT READY. Do not dispatch against a dead transport:")
        for name, gates in down:
            print(f"  {name} is down, which gates {gates}")
        print()
        print("What to do, in this order:")
        print("  1. If this host is not on the sandbox allowlist, a denial and an")
        print("     outage look identical here. Check the allowlist first.")
        print("  2. If it is a real outage, wait and re-probe. Do not read a dead")
        print("     dispatch as a defect in the work; that misreading has already")
        print("     cost this project time twice.")
        print("  3. If the task is small, do it inline. The post-mortem measured a")
        print("     two-file read costing less inline than either dead dispatch.")
        return 1

    if skipped:
        print(f"READY, with nothing verified for: {', '.join(skipped)}.")
        print("A skipped transport is not a passing one. If a phase needs it,")
        print("configure it and re-probe rather than dispatching on this result.")
    else:
        print("READY. Every transport answered.")
    return 0


def main(argv: list[str]) -> int:
    names = list(HTTPS_TRANSPORTS) + ["graph"]
    parser = argparse.ArgumentParser(
        description="Probe one transport per dispatch target before spending on it."
    )
    parser.add_argument(
        "--transport",
        action="append",
        choices=names,
        help="Probe only this transport. Repeatable. Default: all of them.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("PREFLIGHT_TIMEOUT", "6")),
        help="Seconds per probe (default 6). This is a guard, not a test.",
    )
    args = parser.parse_args(argv)

    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")

    return run(args.transport or names, args.timeout)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
