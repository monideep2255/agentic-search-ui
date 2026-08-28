"""Tests for the /health endpoint."""

import os

from fastapi.testclient import TestClient

from system_03_search_agent.adapters.web_sse.app import app


def test_health_returns_200() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_json_body() -> None:
    """The body reports liveness AND which deployment answered.

    Was `== {"status": "ok"}`. Build phase 4.15 added `app_env`, an ADDITIVE
    change under `system-design-patterns` pattern 10, so the exact-equality
    assertion became false while the property it protected stayed true.

    Widened rather than loosened, and the distinction matters: the old
    assertion pinned one key, this one pins two, including that `app_env`
    carries the value the process was actually configured with rather than any
    non-empty string. `.claude/rules/goal-contracts.md` forbids weakening a
    check to make it pass; this is strictly more coverage than before.
    """
    client = TestClient(app)
    response = client.get("/health")
    body = response.json()
    assert body["status"] == "ok"
    assert body["app_env"] == os.environ.get("APP_ENV", "unknown")
    assert set(body) == {"status", "app_env"}, (
        f"/health grew a field nobody updated this test for: {sorted(body)}. "
        f"Adding one is allowed and additive; adding one silently is not."
    )


def test_health_requires_no_authentication() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code not in (401, 403)
