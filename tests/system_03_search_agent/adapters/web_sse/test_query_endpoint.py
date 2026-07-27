"""Tests for the POST /query endpoint (Section 2.1 run() wired to the API)."""

from fastapi.testclient import TestClient

from system_03_search_agent.adapters.web_sse.app import app


def _valid_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "query": {
            "text": "What gene is BRCA1?",
            "session_id": "session-1",
            "trace_id": "trace-1",
            "user_id": None,
            "audience_depth": "researcher",
        },
        "context": {
            "surface": "web_ui",
            "session_memory": None,
            "operator_mode": False,
        },
    }
    body.update(overrides)
    return body


class TestPostQueryValidRequest:
    def test_valid_request_returns_200(self) -> None:
        client = TestClient(app)
        response = client.post("/query", json=_valid_body())
        assert response.status_code == 200

    def test_response_body_is_a_json_array(self) -> None:
        client = TestClient(app)
        response = client.post("/query", json=_valid_body())
        assert isinstance(response.json(), list)

    def test_response_contains_guard_and_done_events(self) -> None:
        client = TestClient(app)
        response = client.post("/query", json=_valid_body())
        events = response.json()
        types = [event["type"] for event in events]
        assert "guard" in types
        assert "done" in types
        assert types[-1] == "done"

    def test_response_events_carry_the_request_trace_id(self) -> None:
        client = TestClient(app)
        body = _valid_body()
        body["query"]["trace_id"] = "trace-abc-123"
        response = client.post("/query", json=body)
        events = response.json()
        assert len(events) > 0
        for event in events:
            assert event["trace_id"] == "trace-abc-123"

    def test_response_events_declare_v1_version(self) -> None:
        client = TestClient(app)
        response = client.post("/query", json=_valid_body())
        events = response.json()
        for event in events:
            assert event["version"] == "v1"


class TestPostQueryValidation:
    def test_missing_query_text_returns_422(self) -> None:
        client = TestClient(app)
        body = _valid_body()
        del body["query"]["text"]
        response = client.post("/query", json=body)
        assert response.status_code == 422

    def test_query_text_over_max_length_returns_422(self) -> None:
        client = TestClient(app)
        body = _valid_body()
        body["query"]["text"] = "x" * 2001
        response = client.post("/query", json=body)
        assert response.status_code == 422

    def test_query_text_at_max_length_is_accepted(self) -> None:
        client = TestClient(app)
        body = _valid_body()
        body["query"]["text"] = "x" * 2000
        response = client.post("/query", json=body)
        assert response.status_code == 200

    def test_missing_query_object_returns_422(self) -> None:
        client = TestClient(app)
        body = _valid_body()
        del body["query"]
        response = client.post("/query", json=body)
        assert response.status_code == 422

    def test_missing_context_object_returns_422(self) -> None:
        client = TestClient(app)
        body = _valid_body()
        del body["context"]
        response = client.post("/query", json=body)
        assert response.status_code == 422

    def test_invalid_surface_value_returns_422(self) -> None:
        client = TestClient(app)
        body = _valid_body()
        body["context"]["surface"] = "carrier_pigeon"
        response = client.post("/query", json=body)
        assert response.status_code == 422

    def test_invalid_audience_depth_returns_422(self) -> None:
        client = TestClient(app)
        body = _valid_body()
        body["query"]["audience_depth"] = "not_a_real_depth"
        response = client.post("/query", json=body)
        assert response.status_code == 422

    def test_unknown_top_level_field_rejected(self) -> None:
        client = TestClient(app)
        body = _valid_body(extra_field="nope")
        response = client.post("/query", json=body)
        assert response.status_code == 422

    def test_unknown_query_field_rejected(self) -> None:
        client = TestClient(app)
        body = _valid_body()
        body["query"]["unexpected"] = "nope"
        response = client.post("/query", json=body)
        assert response.status_code == 422

    def test_empty_body_returns_422_not_500(self) -> None:
        client = TestClient(app)
        response = client.post("/query", json={})
        assert response.status_code == 422
