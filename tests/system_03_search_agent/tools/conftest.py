"""Make the Layer 1 transport choice EXPLICIT in tests rather than ambient.

Finding F-4.11-07, build phase 4.11.

`execute_cypher` dispatches on `GRAPH_QUERY_URL`: set it and every Layer 1
call goes over HTTPS, leave it unset and every call goes over psycopg2. That
is the right production behaviour and it collides with two facts about this
repository that are individually harmless:

- Importing `litellm` anywhere in the process calls `load_dotenv()` at import
  time, so the developer's whole `.env` becomes ambient process state. This
  is finding F-2.1-04 and it has been known since build phase 2.1.
- Passing a `connection_factory` while `GRAPH_QUERY_URL` is set raises, on
  purpose, because silently honouring one transport and discarding the other
  is how a suite goes on passing against a transport nobody is shipping.

Composed, the moment a developer cuts their `.env` over to the HTTPS service,
seventeen psycopg2 unit tests that inject a factory start failing on a
machine where nothing is wrong. Measured on 2026-08-22: those tests passed
individually and failed in the full suite, which is the signature of ambient
state rather than of a defect in the code under test.

Neither half is wrong on its own, so neither half is what changes. What
changes is that a test in this directory no longer inherits a transport from
whoever ran it. The variable is cleared before every test here, and a test
that wants the HTTPS path sets it itself with monkeypatch, which the premise
gate's dispatch arms already do. Transport selection becomes something a
test states rather than something it absorbs.

Deliberately scoped to this directory rather than to the whole suite: the
default belongs where Layer 1 is exercised, and a repository-wide autouse
fixture that silently deletes an environment variable is the kind of ambient
behaviour this file exists to remove, not to spread.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _explicit_layer_1_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear GRAPH_QUERY_URL so each test states its own transport.

    monkeypatch restores whatever was there afterwards, so this changes what
    a test sees and never what the developer's shell sees.
    """
    monkeypatch.delenv("GRAPH_QUERY_URL", raising=False)
