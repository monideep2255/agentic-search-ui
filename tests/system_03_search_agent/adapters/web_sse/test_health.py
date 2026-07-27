"""Tests for the /health endpoint."""

from fastapi.testclient import TestClient

from system_03_search_agent.adapters.web_sse.app import app


def test_health_returns_200() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_json_body() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.json() == {"status": "ok"}


def test_health_requires_no_authentication() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code not in (401, 403)
