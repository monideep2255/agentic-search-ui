"""Every surface the Integrations page advertises must actually exist.

T-4.16-04, the product owner's defect 5 from the live demo: "I do not see
the KGX, REST API, command line or MCP setup up properly on the
integrations page."

WHY THIS TEST IS IN PYTHON, GRADING A TYPESCRIPT FILE. That inversion is
the whole point. `frontend/src/components/screens/InfoScreens.tsx` is prose
and code samples ABOUT other modules, and until this file existed nothing
connected the two. So the page drifted through two build phases while every
suite stayed green:

- It printed `ncbi-search ask "..."`. No such command has ever existed.
  `pyproject.toml` declares `s3` and `s3-kgx-export`.
- It printed `POST /v1/export/kgx`. No such route exists. Build phase 4.4
  shipped KGX as a console script, and the card's own body said "batch job"
  while its code block contradicted it.
- It omitted GraphQL entirely, which shipped in build phase 4.3 and is
  mounted at `/graphql`, while the lede said "reachable four ways".

A frontend test could not have caught any of those, because the truth lives
in `pyproject.toml` and in the FastAPI route table. A command printed on a
page is a CLAIM, exactly as a citation is, and this repository's whole
argument is that a claim gets checked against its source rather than
written from memory of what the source probably says.

WHAT THIS DELIBERATELY DOES NOT DO. It does not assert the page's wording,
its layout, or which surfaces it chooses to feature. Those are design
decisions owned by the component cards. It asserts only that what the page
tells a reader to run or call is real.

COVERAGE, stated so a gap is arguable rather than discovered:

  Exercised:
    - Every `s3...` console command named anywhere in the file resolves to
      a script declared in `pyproject.toml`.
    - Every `/v1/...`, `/graphql` or `/mcp` path named in the file resolves
      to a real mounted route or path prefix on the FastAPI app.
    - All five shipped delivery surfaces are named at all.

  NOT exercised, and named:
    - Whether a command's FLAGS are valid. `--hops` and `--output-dir` are
      read by eye against `export/cli.py` today; a wrong flag would pass
      this. Closing it means invoking each parser, which is a bigger change
      than this defect justifies.
    - The CLI's own `s3` subcommands (`ask`, `login`, `stop`) beyond the
      script name itself.
    - The GraphQL query body's field names against the schema.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PAGE = _REPO_ROOT / "frontend/src/components/screens/InfoScreens.tsx"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"


_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"^\s*//.*$", re.MULTILINE)


@pytest.fixture(scope="module")
def page_source() -> str:
    """The page with its COMMENTS STRIPPED, which is not a detail.

    The first version of this fixture returned the raw file and three arms
    failed immediately, matching `ncbi-search`, `POST /v1/export/kgx` and
    `https://...` inside the very comment that DOCUMENTS those as the old
    defect. The test was grading the file's prose about itself rather than
    what it renders.

    Recorded rather than quietly fixed, because the alternative fix was
    tempting and wrong: deleting the explanatory comment would have made
    the test pass while destroying the record of why the page is written
    the way it is. When a check and a comment collide, it is usually the
    check that is scoped wrong.

    A SECOND DEFECT IN THIS FIXTURE, found by mutation and worth as much as
    the first. The stripper's own populate-check originally asserted
    `"s3 ask" in text`, which is page CONTENT, not fixture health. Under
    the mutation that restores the shipped `ncbi-search` command it fired
    first, reporting "comment stripping removed the page body" about a page
    that was intact, and masked all four real failures. A fixture check
    must never assert the thing its arms assert, or a genuine defect
    surfaces as a broken harness. It now counts `<Card` occurrences, which
    is structural and cannot be changed by a wrong command string.
    """
    assert _PAGE.is_file(), f"the integrations page moved: {_PAGE}"
    raw = _PAGE.read_text(encoding="utf-8")
    # POPULATE-CHECK. Every arm below searches this string, so an empty or
    # relocated file would make each of them vacuously true rather than
    # false. This is the shape build phases 4.7 and 4.11 both shipped.
    assert "IntegrationsScreen" in raw, (
        "populate-check failed: the file read does not contain "
        "IntegrationsScreen, so every assertion below would search the "
        "wrong text and pass on nothing."
    )
    text = _LINE_COMMENT.sub("", _BLOCK_COMMENT.sub("", raw))
    # SECOND POPULATE-CHECK, on the stripped text specifically. A stripper
    # that ate the whole file would leave every arm below searching an
    # empty string and passing, which is the exact vacuity this repository
    # keeps shipping. So the thing the arms actually read must be shown to
    # still contain the surfaces they are about to look for.
    assert "IntegrationsScreen" in text and text.count("<Card") >= 4, (
        "populate-check failed: comment stripping removed the page body, so "
        "every arm below would search an empty string."
    )
    return text


@pytest.fixture(scope="module")
def declared_console_scripts() -> set[str]:
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    scripts = set(data.get("project", {}).get("scripts", {}))
    assert scripts, "populate-check failed: pyproject declares no console scripts at all."
    return scripts


def test_every_command_the_page_prints_is_a_real_console_script(
    page_source: str, declared_console_scripts: set[str]
) -> None:
    """The `ncbi-search ask` defect, generalised.

    Matches any token that looks like this project's own command being
    invoked at the start of a shell line inside a code sample. A page that
    invents a command name fails here rather than in a demo.
    """
    # Commands appear inside JS string literals, so a line start is `\n`,
    # a quote, or an escaped newline in the source.
    invoked = set(re.findall(r"(?:\\n|['\"`]|^)\s*(s3[a-z0-9-]*)\s", page_source, re.MULTILINE))
    assert invoked, (
        "populate-check failed: the page prints no command at all, so this "
        "arm cannot distinguish a wrong command from an absent one."
    )
    unknown = invoked - declared_console_scripts
    assert not unknown, (
        f"the integrations page tells a reader to run {sorted(unknown)}, which "
        f"pyproject.toml does not declare. Declared: {sorted(declared_console_scripts)}. "
        "A command printed on a page is a claim; check it against its source."
    )


def test_the_page_never_advertises_a_command_this_project_does_not_ship(
    page_source: str,
) -> None:
    """The specific regression, pinned by name.

    `ncbi-search` was the shipped wrong value, so it gets its own arm
    rather than relying on the general rule above to happen to catch it.
    """
    assert "ncbi-search " not in page_source, (
        "the page prints `ncbi-search`, a command that has never existed in "
        "this project. The CLI is `s3` (pyproject.toml, build phase 4.2)."
    )


def test_every_http_path_the_page_prints_is_a_real_route(page_source: str) -> None:
    """The `POST /v1/export/kgx` defect: a route advertised, never built."""
    from system_03_search_agent.adapters.web_sse.app import app

    real: set[str] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        if isinstance(path, str):
            real.add(path)
    assert real, "populate-check failed: the app exposes no routes to compare against."

    printed = set(re.findall(r"(?:POST|GET|PUT|DELETE)\s+(?:https?://[^\s/]+)?(/[\w/{}.-]+)", page_source))
    assert printed, (
        "populate-check failed: the page prints no HTTP path, so this arm "
        "cannot distinguish a fabricated route from an absent one."
    )

    def is_real(path: str) -> bool:
        # A mounted sub-app (the MCP server at `/mcp`, GraphQL at
        # `/graphql`) owns everything beneath its prefix, so a prefix match
        # is correct for those rather than an exact one.
        return path in real or any(
            path == mount or path.startswith(mount.rstrip("/") + "/")
            for mount in real
            if mount not in {"/", ""}
        )

    fabricated = {path for path in printed if not is_real(path)}
    assert not fabricated, (
        f"the integrations page advertises {sorted(fabricated)}, which the app "
        "does not serve. `POST /v1/export/kgx` was the shipped instance: KGX "
        "is a console script (build phase 4.4), never an endpoint."
    )


def test_the_page_names_every_shipped_delivery_surface(page_source: str) -> None:
    """GraphQL was missing entirely while the lede said "four ways".

    Named by their build phases so a reader can check the claim: 4.0 REST
    and SSE, 4.1 MCP, 4.2 CLI, 4.3 GraphQL, 4.4 KGX export.
    """
    # MATCHED AS AN EXACT CARD TITLE, never as a substring of the file.
    #
    # This arm originally asserted `surface in page_source`, and mutation
    # caught it: renaming the card to "GraphQLXX" left it GREEN, because
    # "GraphQLXX" contains "GraphQL". A substring check cannot see a
    # renamed or misspelled surface, which is exactly the failure it exists
    # to catch. This is the fourth assertion-that-cannot-fail found in
    # build phase 4.16, and the third written by the lead.
    for surface, phase in [
        ("REST and SSE", "4.0"),
        ("MCP server", "4.1"),
        ("Command line", "4.2"),
        ("GraphQL", "4.3"),
        ("KGX export", "4.4"),
    ]:
        assert f'title="{surface}"' in page_source, (
            f"the integrations page has no card titled {surface!r}, which shipped in "
            f"build phase {phase}. A delivery surface nobody can find is not "
            "delivered."
        )


def test_the_page_never_prints_an_elided_placeholder_url(page_source: str) -> None:
    """`https://.../mcp` cannot be copied and used, so it is not setup
    instructions, it is the shape of setup instructions."""
    elided = re.findall(r"https?://\.\.\.", page_source)
    assert not elided, (
        f"the page prints {elided}, an elided placeholder a reader cannot copy. "
        "Quote the real origin the app itself is configured with."
    )
