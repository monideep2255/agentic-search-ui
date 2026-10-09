"""Card 67: a reopened outage answer puts its note in the past tense.

Every assertion on a rewritten note is the exact final sentence, so a
garbled or still present-tense rewrite goes red (A-67-09, J-67-04).
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.feedback import history
from system_03_search_agent.feedback.capture import MAX_ANSWER_MARKDOWN
from system_03_search_agent.feedback.outage_note import SOURCE_WORDS, past_tense_outage_notes

WRITTEN = datetime(2026, 10, 7, 9, 30, tzinfo=UTC)
PUBMED = {"source": "pubmed", "kind": "service_down", "tool": "ncbi_esearch"}
CLINVAR = {"source": "clinvar", "kind": "service_down", "tool": "ncbi_esearch"}
GENE = {"source": "gene", "kind": "service_down", "tool": "ncbi_esearch"}
OTHER = {"source": "pubmed", "kind": "timed_out", "tool": "ncbi_esearch"}

ALSO = " Another background search did not finish, so other sources may be missing too."
ASK = " Ask the question again to search afresh."


def _down(source: str) -> dict[str, str]:
    return {"source": source, "kind": "service_down", "tool": "ncbi_esearch"}


def _answer(note: str) -> str:
    return f"## TP53\n\nTP53 is a tumour suppressor [1].\n\n{note}"


# (failed searches, the live note today, the note on reopening)
LIVE_CASES = [
    *[
        (
            [_down(source)],
            (
                f"{name} is down at NCBI right now, so this answer may be missing {what} from it."
                " Try again later."
            ),
            (
                f"When this answer was written, NCBI's {name} was not answering, so this answer"
                f" may be missing {what} from it.{ASK}"
            ),
        )
        for source, name, what in [
            ("pubmed", "PubMed", "papers"),
            ("clinvar", "ClinVar", "variant records"),
            ("omim", "OMIM", "records"),
            ("gds", "GEO DataSets", "datasets"),
            ("medgen", "MedGen", "records"),
            ("gene", "Gene", "gene records"),
        ]
    ],
    (
        [PUBMED, OTHER],
        (
            "PubMed is down at NCBI right now, so this answer may be missing papers from it."
            f"{ALSO} Try again later."
        ),
        (
            "When this answer was written, NCBI's PubMed was not answering, so this answer may be"
            f" missing papers from it.{ALSO}{ASK}"
        ),
    ),
    (
        [PUBMED, CLINVAR],
        (
            "PubMed and ClinVar are down at NCBI right now, so this answer may be missing sources"
            " from them. Try again later."
        ),
        (
            "When this answer was written, NCBI's PubMed and ClinVar were not answering, so this"
            f" answer may be missing sources from them.{ASK}"
        ),
    ),
    (
        [PUBMED, CLINVAR, GENE, OTHER],
        (
            "PubMed, ClinVar and Gene are down at NCBI right now, so this answer may be missing"
            f" sources from them.{ALSO} Try again later."
        ),
        (
            "When this answer was written, NCBI's PubMed, ClinVar and Gene were not answering, so"
            f" this answer may be missing sources from them.{ALSO}{ASK}"
        ),
    ),
    (
        [{"kind": "service_down"}],
        (
            "Some of NCBI's databases are down right now, so this answer may be missing sources"
            " from them. Try again later."
        ),
        (
            "When this answer was written, some of NCBI's databases were not answering, so this"
            f" answer may be missing sources from them.{ASK}"
        ),
    ),
    (
        [{"source": "unknown", "kind": "service_down"}, PUBMED],
        (
            "Some of NCBI's databases are down right now, so this answer may be missing sources"
            " from them. Try again later."
        ),
        (
            "When this answer was written, some of NCBI's databases were not answering, so this"
            f" answer may be missing sources from them.{ASK}"
        ),
    ),
]


@pytest.mark.parametrize(("failed", "live", "reopened"), LIVE_CASES)
def test_every_live_outage_note_reopens_as_this_exact_sentence(
    failed: list[dict[str, str]], live: str, reopened: str
) -> None:
    assert graph_module._build_failed_search_note(failed) == live
    assert past_tense_outage_notes(_answer(live), WRITTEN) == _answer(reopened)


# Card 63's first wording (bf4a697e), each opener, and what it reopens as.
OLDER_CASES = [
    (
        (
            "PubMed's search is down at NCBI right now, so this answer has no papers from it."
            " Try again later."
        ),
        (
            "When this answer was written, NCBI's PubMed was not answering, so this answer may be"
            f" missing papers from it.{ASK}"
        ),
    ),
    (
        (
            "ClinVar's search is down at NCBI right now, so this answer has no variant records"
            f" from it.{ALSO} Try again later."
        ),
        (
            "When this answer was written, NCBI's ClinVar was not answering, so this answer may be"
            f" missing variant records from it.{ALSO}{ASK}"
        ),
    ),
    (
        (
            "The PubMed and ClinVar searches are down at NCBI right now, so this answer has"
            " nothing from them. Try again later."
        ),
        (
            "When this answer was written, NCBI's PubMed and ClinVar were not answering, so this"
            f" answer may be missing sources from them.{ASK}"
        ),
    ),
    (
        (
            "Some of NCBI's searches are down right now, so this answer may be missing sources"
            " from them. Try again later."
        ),
        (
            "When this answer was written, some of NCBI's databases were not answering, so this"
            f" answer may be missing sources from them.{ASK}"
        ),
    ),
]


@pytest.mark.parametrize(("older", "reopened"), OLDER_CASES)
def test_every_older_wording_reopens_as_a_clean_sentence(older: str, reopened: str) -> None:
    assert past_tense_outage_notes(_answer(older), WRITTEN) == _answer(reopened)


def test_the_database_list_is_the_builders_own() -> None:
    assert SOURCE_WORDS == dict(graph_module._DOWN_SOURCE_WORDS.values())


@pytest.mark.parametrize("failed", [case[0] for case in LIVE_CASES])
def test_no_present_tense_outage_words_survive(failed: list[dict[str, str]]) -> None:
    reopened = past_tense_outage_notes(
        _answer(graph_module._build_failed_search_note(failed)), WRITTEN
    )
    for stale in ("right now", " is down", " are down", "Try again later"):
        assert stale not in reopened
    assert "October" not in reopened  # no date inside the sentence


NOTE = graph_module._build_failed_search_note([PUBMED])


@pytest.mark.parametrize(
    "text",
    [
        f"| Source | Status |\n|---|---|\n| {NOTE} | x |",
        f"| {NOTE} |",
        f"- {NOTE}",
        f"> {NOTE}",
        f"{NOTE} Variant X is pathogenic [1].",
        f"Study: {NOTE}",
        f"The authors wrote: {NOTE}",
        f"{NOTE}\nTP53 [1].",
        (
            "Our mirror is down at NCBI right now, so this answer may be missing papers from it."
            " Try again later."
        ),
        (
            "PubMed is down at NCBI right now, so this answer may be missing variant records"
            " from it. Try again later."
        ),
        (
            "A source I needed is down at NCBI right now, so I could not find grounded evidence"
            " this time. Try again later, or try NCBI's cross-database search."
        ),
        "The background search did not finish. Ask again to retry.",
        "Rates are high right now in some regions. Try again later in the season.",
    ],
)
def test_text_that_is_not_the_note_paragraph_is_never_touched(text: str) -> None:
    markdown = _answer(text)
    assert past_tense_outage_notes(markdown, WRITTEN) is markdown


def test_a_missing_timestamp_leaves_the_text_unchanged() -> None:
    markdown = _answer(NOTE)
    assert past_tense_outage_notes(markdown, None) is markdown
    plain = _answer("TP53 [1].")
    assert past_tense_outage_notes(plain, None) is plain


# Measured lengths of the one-database note, present and past tense.
PRESENT_PUBMED = NOTE
PAST_PUBMED = LIVE_CASES[0][2]


def test_measured_growth_of_the_rewrite() -> None:
    assert len(PRESENT_PUBMED) == 96
    assert len(PAST_PUBMED) == 149


def _padded(note: str, total: int) -> str:
    head = "## TP53\n\n"
    tail = f"\n\n{note}"
    return head + "x" * (total - len(head) - len(tail)) + tail


def test_an_answer_at_the_length_limit_is_returned_unchanged() -> None:
    stored = _padded(NOTE, MAX_ANSWER_MARKDOWN)
    assert len(stored) == MAX_ANSWER_MARKDOWN
    assert past_tense_outage_notes(stored, WRITTEN) is stored


def test_an_answer_whose_rewrite_just_fits_is_rewritten() -> None:
    growth = len(PAST_PUBMED) - len(PRESENT_PUBMED)
    stored = _padded(NOTE, MAX_ANSWER_MARKDOWN - growth)
    reopened = past_tense_outage_notes(stored, WRITTEN)
    assert len(reopened) == MAX_ANSWER_MARKDOWN
    assert reopened.endswith(PAST_PUBMED)


def _serve(monkeypatch: pytest.MonkeyPatch, stored: str, created_at: Any) -> Any:
    row = SimpleNamespace(
        trace_id="t1",
        query_text="What does TP53 do?",
        created_at=created_at,
        trust_signal="ask",
        citations=[],
        answer_markdown=stored,
        audience_depth="researcher",
        answer_trust_line="Based on 9 sources, not yet confirmed",
        risk_tier=None,
    )

    class _Session:
        def execute(self, *_a: object, **_k: object) -> SimpleNamespace:
            return SimpleNamespace(first=lambda: row)

    @contextmanager
    def _scope():  # type: ignore[no-untyped-def]
        yield _Session()

    monkeypatch.setattr(history, "session_scope", _scope)
    saved = history.get_saved_answer(owner_id="acct", trace_id="t1")
    assert row.answer_markdown == stored  # the stored text itself is unchanged
    return saved


def test_get_saved_answer_reopens_the_note_in_the_past_tense(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved = _serve(monkeypatch, _answer(NOTE), WRITTEN)
    assert saved is not None
    assert saved.answer_markdown == _answer(PAST_PUBMED)
    assert saved.asked_at == WRITTEN


@pytest.mark.parametrize(
    "failed", [[PUBMED], [PUBMED, CLINVAR, OTHER], [{"kind": "service_down"}, OTHER]]
)
def test_a_saved_answer_at_the_limit_still_opens_on_the_web_and_over_mcp(
    monkeypatch: pytest.MonkeyPatch, failed: list[dict[str, str]]
) -> None:
    from system_03_search_agent.adapters.mcp.server import ReopenedAnswerOutput
    from system_03_search_agent.adapters.web_sse.app import SavedAnswerResponse

    stored = _padded(graph_module._build_failed_search_note(failed), MAX_ANSWER_MARKDOWN)
    saved = _serve(monkeypatch, stored, WRITTEN)
    SavedAnswerResponse(
        trace_id=saved.trace_id,
        question=saved.question,
        asked_at=saved.asked_at,
        depth="researcher",
        answer_markdown=saved.answer_markdown,
        trust_signal=saved.trust_signal,
    )
    mcp = ReopenedAnswerOutput(
        trace_id=saved.trace_id,
        question=saved.question,
        asked_at=saved.asked_at,
        audience_depth="researcher",
        answer_markdown=saved.answer_markdown,
        trust_signal=saved.trust_signal,
    )
    # MCP's reopen output states when the answer was asked, in UTC.
    assert mcp.model_dump(mode="json")["asked_at"] == "2026-10-07T09:30:00Z"
