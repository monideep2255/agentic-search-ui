"""Ordinary unit test: the X-Forwarded-For rule the graph service's rate limit rests on.

Moved out of the deleted `test_demo_deploy_premise.py` and
`test_demo_deploy_mutation.py` (build phase 4.14 bossman redesign,
2026-09-24, `docs/build/Bossman_redesign_deletion_inventory.md`). Two
rules bound `client_source` (`services/graph_query_service/app.py`,
finding F-4.11-11): the forwarded header is honoured only when the
immediate peer is the local proxy, and only the RIGHTMOST element is
used, the value the proxy itself appended, never anything the caller sent
ahead of it. Getting either wrong turns the per-caller rate limit into
either a bypass (a direct caller spoofs its source) or a single shared
bucket (every caller behind the proxy collapses onto one key).

The second layer, the Caddyfile directive itself, is checked as a plain
text assertion against the deployed configuration file so a removed
directive is not invisible to this repository.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

from services.graph_query_service.app import client_source

REPO_ROOT = Path(__file__).resolve().parents[3]
CADDYFILE = REPO_ROOT / "services" / "graph_query_service" / "deploy" / "Caddyfile"


def _request(peer: str | None, forwarded: str | None) -> SimpleNamespace:
    client = SimpleNamespace(host=peer) if peer is not None else None
    headers = {"x-forwarded-for": forwarded} if forwarded else {}
    return SimpleNamespace(client=client, headers=headers)


def test_a_direct_caller_is_identified_by_its_own_peer_address() -> None:
    request = _request(peer="203.0.113.5", forwarded="10.0.0.1")
    assert client_source(request) == "203.0.113.5", (
        "a caller reaching the service directly (not through the local proxy) "
        "must be identified by its own peer address; its header must be ignored"
    )


def test_a_caller_behind_the_trusted_proxy_is_identified_by_the_forwarded_header() -> None:
    request = _request(peer="127.0.0.1", forwarded="203.0.113.9")
    assert client_source(request) == "203.0.113.9"


def test_only_the_rightmost_forwarded_element_is_trusted() -> None:
    """The rightmost element is the one the proxy itself appended.

    A caller-supplied leftmost entry must never be trusted as the source.
    """
    request = _request(peer="127.0.0.1", forwarded="198.51.100.1, 203.0.113.9")
    assert client_source(request) == "203.0.113.9"


def test_a_junk_header_falls_back_to_the_real_peer() -> None:
    request = _request(peer="127.0.0.1", forwarded="not-an-ip-address")
    assert client_source(request) == "127.0.0.1"


def test_no_client_and_no_header_reports_unknown() -> None:
    request = _request(peer=None, forwarded=None)
    assert client_source(request) == "unknown"


def test_the_caddyfile_replaces_rather_than_appends_x_forwarded_for() -> None:
    text = CADDYFILE.read_text(encoding="utf-8")
    match = re.search(
        r"^\s*header_up\s+X-Forwarded-For\s+(\S+)\s*$", text, re.MULTILINE | re.IGNORECASE
    )
    assert match, (
        "no `header_up X-Forwarded-For` directive. Caddy's default APPENDS, "
        "so a caller-supplied leftmost entry would still reach the rightmost "
        "position after enough hops"
    )
    assert not re.search(r"header_up\s+\+X-Forwarded-For", text, re.IGNORECASE), (
        "`header_up +X-Forwarded-For` APPENDS. Drop the leading plus"
    )
