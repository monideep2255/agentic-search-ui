"""Card 67: a reopened outage answer names the day it was written."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.feedback import history
from system_03_search_agent.feedback.outage_note import date_outage_notes

WRITTEN = datetime(2026, 10, 7, 9, 30, tzinfo=UTC)
PUBMED = {"source": "pubmed", "kind": "service_down", "tool": "ncbi_esearch"}
CLINVAR = {"source": "clinvar", "kind": "service_down", "tool": "ncbi_esearch"}
OTHER = {"source": "pubmed", "kind": "timed_out", "tool": "ncbi_esearch"}


def _answer(note: str) -> str:
    return f"## TP53\n\nTP53 is a tumour suppressor [1].\n\n{note}"


@pytest.mark.parametrize(
    "failed",
    [
        [PUBMED],
        [PUBMED, CLINVAR],
        [PUBMED, OTHER],
        [{"kind": "service_down"}],
        [{"source": "unknown", "kind": "service_down"}],
    ],
)
def test_every_live_outage_wording_is_dated_when_reopened(failed: list[dict[str, str]]) -> None:
    live = graph_module._build_failed_search_note(failed)
    assert "right now" in live  # the live answer keeps its present tense
    reopened = date_outage_notes(_answer(live), WRITTEN)
    assert "When this answer was written on 7 October 2026," in reopened
    assert "right now" not in reopened
    assert "Try again later" not in reopened
    assert "TP53 is a tumour suppressor [1]." in reopened


def test_the_older_saved_wording_is_dated_too() -> None:
    old = "PubMed's search is down at NCBI right now, so this answer has no papers from it. Try again later."
    reopened = date_outage_notes(_answer(old), WRITTEN)
    assert "When this answer was written on 7 October 2026," in reopened
    assert "right now" not in reopened
    assert "try again later" not in reopened.lower()


def test_an_answer_without_an_outage_note_is_unchanged() -> None:
    plain = _answer("The background search did not finish. Ask again to retry.")
    assert date_outage_notes(plain, WRITTEN) == plain
    ordinary = "Rates are high right now in some regions. Try again later in the season."
    assert date_outage_notes(ordinary, WRITTEN) == ordinary


def test_the_live_note_is_not_touched_by_the_builder() -> None:
    assert "down at NCBI right now" in graph_module._build_failed_search_note([PUBMED])


def test_get_saved_answer_dates_the_note_from_the_row(monkeypatch: pytest.MonkeyPatch) -> None:
    stored = _answer(graph_module._build_failed_search_note([PUBMED]))
    row = SimpleNamespace(
        trace_id="t1",
        query_text="What does TP53 do?",
        created_at=WRITTEN,
        trust_signal="ask",
        citations=[],
        answer_markdown=stored,
        audience_depth="researcher",
        answer_trust_line="Based on 9 sources, not yet confirmed",
    )

    class _Session:
        def execute(self, *_a: object, **_k: object) -> SimpleNamespace:
            return SimpleNamespace(first=lambda: row)

    @contextmanager
    def _scope():  # type: ignore[no-untyped-def]
        yield _Session()

    monkeypatch.setattr(history, "session_scope", _scope)
    saved = history.get_saved_answer(owner_id="acct", trace_id="t1")
    assert saved is not None
    assert "written on 7 October 2026" in saved.answer_markdown
    assert "right now" not in saved.answer_markdown
    assert row.answer_markdown == stored  # the stored text itself is unchanged
