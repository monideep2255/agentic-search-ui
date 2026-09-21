"""The persona chip's "about" line and Wikipedia link, product-owner request
of 2026-09-13.

Exercised:
    That every shipped entry carries a non-empty `about` line within the
    length the chip's card is designed for, and a Wikipedia address under
    the one pinned host.
    That the loader REJECTS an entry with no `about`, an over-long one, or
    a link to any other host, so a data edit cannot ship a card the chip
    was not designed for or a link to anywhere else. Each rejection is
    pinned by writing a second file and pointing the real loader at it,
    the same way `test_persona.py` varies the list.
    That `persona_record_for_session` returns the record behind the SAME
    name `persona_for_session` draws, for both an anonymous and an
    account-keyed identity, so the card can never describe a different
    scientist than the chip names.
    That `GET /v1/persona` and `POST /v1/query`'s response models carry
    the two fields, and that the endpoint's values match the shipped file
    for the name it returns.

NOT exercised: the live Wikipedia pages themselves. Every link answered
200 on 2026-09-13 when the data was written; a dead link is a data defect
found by a person, not a code defect this file can see.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from system_03_search_agent.core import persona as persona_module
from system_03_search_agent.core.persona import (
    MAX_ABOUT_LENGTH,
    WIKIPEDIA_PREFIX,
    load_persona_list,
    persona_for_session,
    persona_record,
    persona_record_for_session,
)

_SHIPPED_FILE = (
    Path(persona_module.__file__).resolve().parent.parent / "data" / "personas_v1.json"
)


def _shipped_entries() -> list[dict[str, Any]]:
    return list(json.loads(_SHIPPED_FILE.read_text(encoding="utf-8"))["personas"])


def _load_against(tmp_path: Path, entries: list[dict[str, Any]], monkeypatch: Any) -> None:
    target = tmp_path / "personas_test.json"
    target.write_text(json.dumps({"version": 1, "basis": "test", "personas": entries}))
    load_persona_list.cache_clear()
    try:
        monkeypatch.setattr(persona_module, "_PERSONA_FILE", target)
        load_persona_list()
    finally:
        monkeypatch.undo()
        load_persona_list.cache_clear()


class TestTheShippedFile:
    def test_every_entry_has_an_about_line_and_a_wikipedia_link(self) -> None:
        entries = _shipped_entries()
        assert len(entries) >= 30, "populate-check: the shipped list is the real one"
        for entry in entries:
            about = entry["about"]
            assert isinstance(about, str) and about.strip(), entry["name"]
            assert len(about) <= MAX_ABOUT_LENGTH, (entry["name"], len(about))
            assert entry["wikipedia"].startswith(WIKIPEDIA_PREFIX), entry["name"]
            assert "/" not in entry["wikipedia"][len(WIKIPEDIA_PREFIX) :], entry["name"]

    def test_the_loader_carries_both_fields_onto_the_record(self) -> None:
        load_persona_list.cache_clear()
        by_name = {p.name: p for p in load_persona_list()}
        for entry in _shipped_entries():
            record = by_name[entry["name"]]
            assert record.about == entry["about"].strip()
            assert record.wikipedia == entry["wikipedia"]


class TestTheLoaderRejectsBadData:
    def test_an_entry_with_no_about_line_is_refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entries = _shipped_entries()
        del entries[0]["about"]
        with pytest.raises(ValueError, match="no 'about' line"):
            _load_against(tmp_path, entries, monkeypatch)

    def test_an_over_long_about_line_is_refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entries = _shipped_entries()
        entries[0]["about"] = "x" * (MAX_ABOUT_LENGTH + 1)
        with pytest.raises(ValueError, match="past the"):
            _load_against(tmp_path, entries, monkeypatch)

    @pytest.mark.parametrize(
        "bad_link",
        [
            "http://en.wikipedia.org/wiki/Gregor_Mendel",
            "https://en.wikipedia.org.evil.example/wiki/Gregor_Mendel",
            "https://de.wikipedia.org/wiki/Gregor_Mendel",
            "https://example.com/Gregor_Mendel",
            "",
        ],
    )
    def test_a_link_off_the_pinned_host_is_refused(
        self, bad_link: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entries = _shipped_entries()
        entries[0]["wikipedia"] = bad_link
        with pytest.raises(ValueError, match="host-pinned"):
            _load_against(tmp_path, entries, monkeypatch)

    def test_the_shipped_file_itself_still_loads(self) -> None:
        # The counterfactual for the three arms above: the real file passes
        # every rule they exercise, so a rejection there is the rule firing
        # and not the loader being broken.
        load_persona_list.cache_clear()
        assert len(load_persona_list()) >= 30


class TestTheRecordMatchesTheDraw:
    @pytest.mark.parametrize("user_id", [None, "account-7f3a"])
    def test_the_record_carries_the_drawn_name(self, user_id: str | None) -> None:
        load_persona_list.cache_clear()
        for session_id in ("session-a", "session-b", "session-c"):
            name = persona_for_session(session_id=session_id, user_id=user_id)
            record = persona_record_for_session(session_id=session_id, user_id=user_id)
            assert record.name == name
            assert record.about and record.wikipedia.startswith(WIKIPEDIA_PREFIX)

    def test_an_unknown_name_is_a_key_error(self) -> None:
        load_persona_list.cache_clear()
        with pytest.raises(KeyError):
            persona_record("Nobody")


class _FakeSession:
    def execute(self, _statement: Any) -> Any:
        class _Result:
            @staticmethod
            def scalar_one_or_none() -> None:
                return None

        return _Result()

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def add(self, _row: Any) -> None:
        return None

    def flush(self) -> None:
        return None


@pytest.fixture
def app_client(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("AUTH_SECRET", "persona about arms deterministic signing input")
    from system_03_search_agent.adapters.web_sse.app import app

    return app


class TestThePersonaEndpointCarriesTheCard:
    def test_the_endpoint_returns_the_about_line_and_link_for_the_name_it_draws(
        self, app_client: Any
    ) -> None:
        from system_03_search_agent.data.session import get_session

        session_id = "landing-session-about"
        app_client.dependency_overrides[get_session] = lambda: _FakeSession()
        try:
            client = TestClient(app_client)
            response = client.get("/v1/persona", params={"session_id": session_id})
        finally:
            app_client.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        load_persona_list.cache_clear()
        record = persona_record(body["persona_name"])
        assert body["persona_about"] == record.about
        assert body["persona_wikipedia"] == record.wikipedia
        # Mutation: returning a fixed or a different scientist's line passes
        # a "has the field" check and fails this equality.
        assert body["persona_wikipedia"].startswith(WIKIPEDIA_PREFIX)

    def test_the_create_run_response_model_declares_both_fields(self) -> None:
        from system_03_search_agent.adapters.web_sse.app import CreateRunResponse

        assert {"persona_about", "persona_wikipedia"} <= set(CreateRunResponse.model_fields)
