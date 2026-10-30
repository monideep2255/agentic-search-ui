"""The web's citation host list and the server's source URL rule must agree.

Card 135.1: the server admitted OMIM on 2026-09-20 but the web list never
gained it, so a reopened answer read "Not linked" for an OMIM source. This
test reads the web list out of the component and holds it to the server's
`NCBI_SOURCE_URL_PATTERN` both ways.
"""

from __future__ import annotations

import re
from pathlib import Path

from system_03_search_agent.contracts.events import NCBI_SOURCE_URL_PATTERN

_COMPONENT = (
    Path(__file__).resolve().parents[3] / "frontend/src/components/answer/CitationMarkers.tsx"
)

# One representative path per host family, since the clinical trials rule
# admits only `/study/` pages.
_PATH = {"clinicaltrials.gov": "study/NCT00000000"}


def _web_hosts() -> list[str]:
    text = _COMPONENT.read_text(encoding="utf-8")
    block = re.search(r"ALLOWED_CITATION_HOSTS\s*=\s*\[(.*?)\];", text, re.DOTALL)
    assert block, "ALLOWED_CITATION_HOSTS not found in CitationMarkers.tsx"
    code = re.sub(r"//[^\n]*", "", block.group(1))
    return re.findall(r'"([^"]+)"', code)


def _url(host: str) -> str:
    bare = host.removeprefix("www.")
    return f"https://{host}/{_PATH.get(bare, 'entry/1')}"


def _server_literal_hosts() -> set[str]:
    """Literal hosts in the server pattern, with `(?:www\\.)?` expanded."""
    hosts: set[str] = set()
    for alt in NCBI_SOURCE_URL_PATTERN.removeprefix("^https://").split("|"):
        if "(?:www\\.)?" in alt:
            bare = alt.split("(?:www\\.)?", 1)[1].split("/", 1)[0].replace("\\.", ".")
            hosts.update({bare, f"www.{bare}"})
    return hosts


def test_every_web_host_is_accepted_by_the_server() -> None:
    pattern = re.compile(NCBI_SOURCE_URL_PATTERN)
    hosts = _web_hosts()
    assert hosts, "no hosts parsed from the web list"
    for host in hosts:
        assert pattern.match(_url(host)), f"web links {host} but the server rejects it"


def test_every_server_host_is_linked_by_the_web() -> None:
    web = set(_web_hosts())
    server = _server_literal_hosts()
    assert {"omim.org", "www.omim.org", "clinicaltrials.gov"} <= server
    missing = server - web
    assert not missing, f"server accepts but the web does not link: {sorted(missing)}"
    # The NCBI family is a wildcard on the server, so its bare host is checked
    # directly; its subdomains are covered by the first test.
    assert "ncbi.nlm.nih.gov" in web
