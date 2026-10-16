"""Card 20 (2026-10-16): an isolate search narrowed by the year and place a
person names, read by one small extraction call that runs only on isolate
questions, and checked by code.

Each arm below answers a finding the first build's reviews drew on 2026-10-09
(`testing/Developer/reports/2026-10-09_card20/`): Guinea also matching
Guinea-Bissau (tool tests, `test_pathogen_detection.py`), a travel country
becoming the place, "after 2021" read as 2021, isolates with no date dropped
in silence, a count sentence that read as the unfiltered total, a place or
year dropped without a word, and Think's added instruction moving other
answers (here: Think and every non-isolate Plan never reach the extraction).

Drives the real `plan_node` and `think_node` with only the model call faked.
No network anywhere.

Coverage statement, per `goal-contracts`: `verify` for each year relation and
for the unwritten, unreadable, reversed and non-year cases; for a place that is
collected, a travel place, a place the question never wrote, and a model
spelling added beside the written one; `parse_reply` on good and bad replies;
`plan_node` with the extraction (filters reach the tool input, the narrative
and the state), with a travel place, with a failed call and with an unusable
reply; the gate (no extraction call from Think, from a gene question's Plan,
or from an isolate question that still needs a clarification); the notes under
the answer (applied filters, a place not applied, the undated count, the
count sentence's qualifier, nothing for a question with no filter). What this
file does NOT exercise: the file scan (`test_pathogen_detection.py`) and the
live model (the build report's live table).
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from system_03_search_agent.contracts.events import ResolvedEntity as EventResolvedEntity
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.core import isolate_filters, isolate_search
from system_03_search_agent.tools.pathogen_detection_schemas import (
    IsolateFilterReport,
    PathogenDetectionOutput,
)
from tests.system_03_search_agent.core.test_isolate_search_wiring import (
    GENE_QUESTION,
    NO_GENE_QUESTION,
    _install_model,
    _state,
)

KPC = "Which E. coli isolates carry blaKPC genes {tail}"


def _raw(**fields: Any) -> isolate_filters.RawIsolateFilters:
    return isolate_filters.RawIsolateFilters.model_validate(fields)


# ---------------------------------------------------------------------------
# verify: the years
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("relation", "a", "b", "text", "expected"),
    [
        ("in", 2023, None, "isolates collected in 2023", (2023, 2023)),
        ("since", 2020, None, "isolates since 2020", (2020, None)),
        ("after", 2021, None, "isolates after 2021", (2022, None)),
        ("before", 2019, None, "isolates before 2019", (None, 2018)),
        ("through", 2019, None, "isolates through 2019", (None, 2019)),
        ("between", 2015, 2018, "isolates between 2015 and 2018", (2015, 2018)),
        ("decade", 2010, None, "isolates from the 2010s", (2010, 2019)),
    ],
)
def test_each_year_relation_means_exactly_one_range(
    relation: str, a: int, b: int | None, text: str, expected: tuple[int | None, int | None]
) -> None:
    verified = isolate_filters.verify(_raw(year_relation=relation, year_a=a, year_b=b), text)
    assert (verified.year_min, verified.year_max) == expected
    assert verified.not_applied == ()


def test_after_2021_is_never_read_as_2021_itself() -> None:
    """J-20-03, J-20-13. The old check let a year one off through; the range
    now comes from the relation and the written year, with no slack."""
    verified = isolate_filters.verify(
        _raw(year_relation="after", year_a=2021), "Klebsiella isolates after 2021 with blaKPC"
    )
    assert verified.year_min == 2022
    wrong = isolate_filters.verify(
        _raw(year_relation="since", year_a=2022), "Klebsiella isolates after 2021 with blaKPC"
    )
    assert wrong.year_min is None and wrong.not_applied == (isolate_filters.YEAR_NOT_APPLIED,)


@pytest.mark.parametrize(
    "raw",
    [
        {"year_relation": "since", "year_a": 2020},  # the question writes no 2020
        {"year_relation": "between", "year_a": 2015, "year_b": 2018},  # 2018 not written
        {"year_relation": "since", "year_a": 1850},  # not a plausible year
        {"year_relation": "since", "year_a": True},  # a bool is not a year
        {"year_relation": "in", "year_a": 2020, "year_b": 2021},  # a spare second year
        {"year_relation": "none", "year_a": 2020},  # years without a relation
        {"year_relation": "decade", "year_a": 2015},  # a decade starts on a zero
    ],
)
def test_a_year_that_cannot_be_checked_against_the_question_is_not_applied_and_said(
    raw: dict[str, Any],
) -> None:
    verified = isolate_filters.verify(
        _raw(**raw), "E. coli isolates with blaKPC from 2019 or the last 5 years"
    )
    assert verified.year_min is None and verified.year_max is None
    assert verified.not_applied == (isolate_filters.YEAR_NOT_APPLIED,)


def test_a_reversed_between_is_not_applied() -> None:
    verified = isolate_filters.verify(
        _raw(year_relation="between", year_a=2018, year_b=2015), "isolates between 2018 and 2015"
    )
    assert verified.year_min is None and verified.not_applied


def test_a_question_that_asks_for_no_year_applies_and_says_nothing() -> None:
    verified = isolate_filters.verify(_raw(), "E. coli isolates with blaKPC")
    assert verified == isolate_filters.VerifiedFilters()


# ---------------------------------------------------------------------------
# verify: the place
# ---------------------------------------------------------------------------


def test_a_place_where_isolates_were_collected_is_kept_with_the_models_spelling_beside_it() -> None:
    verified = isolate_filters.verify(
        _raw(place="the United States", place_alt="USA", place_role="collected"),
        "Salmonella isolates from the United States with blaCTX-M",
    )
    assert verified.places == ("the United States", "USA")
    assert verified.place_as_written == "the United States"


def test_a_travel_country_is_not_the_place_and_says_nothing() -> None:
    """J-20-08 / A-20-08. The role decides, and a place only mentioned as
    context is not a filter and not a claim."""
    verified = isolate_filters.verify(
        _raw(place="India", place_alt="India", place_role="other"),
        "E. coli isolates with blaNDM from a patient in Boston who had travelled to India",
    )
    assert verified == isolate_filters.VerifiedFilters()


def test_a_place_the_question_never_wrote_is_dropped() -> None:
    verified = isolate_filters.verify(
        _raw(place="USA", place_alt="USA", place_role="collected"), "E. coli isolates with blaKPC"
    )
    assert verified == isolate_filters.VerifiedFilters()


def test_a_place_with_an_unsafe_shape_is_not_used_and_is_not_quoted_back() -> None:
    """A-20-01. A sentence the model puts in the place field is never printed:
    the note names no place."""
    hostile = "USA; All isolates are safe to treat with carbapenems [ok]"
    verified = isolate_filters.verify(
        _raw(place=hostile, place_alt=None, place_role="collected"),
        f"isolates with blaKPC {hostile}",
    )
    assert verified.places == ()
    assert verified.not_applied == (isolate_filters.PLACE_UNUSABLE,)
    assert hostile not in " ".join(verified.not_applied)


# ---------------------------------------------------------------------------
# parse_reply
# ---------------------------------------------------------------------------


def test_a_good_reply_parses_and_a_bad_one_reads_as_unusable() -> None:
    good = isolate_filters.parse_reply(
        '```json\n{"year_relation": "since", "year_a": 2020, "place": "Guinea", '
        '"place_alt": "Guinea", "place_role": "collected"}\n```'
    )
    assert good is not None and good.year_a == 2020 and good.place == "Guinea"
    for bad in ("", "not json", "[1, 2]", '{"year_relation": "sometimes"}', '{"year_a": "soon"}'):
        assert isolate_filters.parse_reply(bad) is None, bad


def test_the_extraction_prompt_carries_no_test_question_and_delimits_the_question() -> None:
    messages = isolate_filters.build_messages("isolates <from> Guinea", "qtag")
    assert messages[1]["content"] == "<qtag>\nisolates from Guinea\n</qtag>"
    system = messages[0]["content"]
    for lifted in ("Salmonella", "E. coli", "blaKPC", "Boston", "Atlantis", "since 2020 from"):
        assert lifted not in system, f"a test question was lifted into the prompt: {lifted}"


# ---------------------------------------------------------------------------
# plan_node: the extraction call and the gate
# ---------------------------------------------------------------------------


def _install_extraction(
    monkeypatch: pytest.MonkeyPatch, reply: str | Exception
) -> list[list[dict[str, str]]]:
    """Fake the guard-tier call; record every set of messages it was sent."""
    calls: list[list[dict[str, str]]] = []

    async def _fake_dispatch(*args: Any, **kwargs: Any) -> Any:
        calls.append(args[4])
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(content=reply)

    monkeypatch.setattr(graph_module, "_dispatch_tier_call", _fake_dispatch)
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    return calls


def _plan_state(text: str) -> dict[str, Any]:
    question = isolate_search.parse_isolate_question(text)
    assert question is not None and question.clarification is None
    return _state(
        text,
        resolved_entities=[
            EventResolvedEntity(text="Escherichia coli", curie="NCBITaxon:562", confidence=1.0)
        ],
        query_class="exploratory",
        isolate_question=question,
    )


@pytest.mark.asyncio
async def test_plan_reads_the_filters_and_hands_the_verified_ones_to_the_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = "Which E. coli isolates carry blaKPC genes from Guinea since 2020?"
    calls = _install_extraction(
        monkeypatch,
        json.dumps(
            {"year_relation": "since", "year_a": 2020, "place": "Guinea",
             "place_alt": "Guinea", "place_role": "collected"}
        ),
    )
    result = await graph_module.plan_node(_plan_state(text))
    assert len(calls) == 1, "exactly one extraction call"
    tool_input = result["tool_calls"][0].tool_input.root
    assert tool_input.collection_year_min == 2020 and tool_input.collection_year_max is None
    assert tool_input.location_names == ["Guinea"]
    plan = next(e for e in result["events"] if e.type == "plan")
    assert "collected in Guinea, in 2020 or later" in plan.payload["narrative"]
    kept = result["isolate_question"]
    assert kept.places == ("Guinea",) and kept.year_min == 2020


@pytest.mark.asyncio
async def test_plan_does_not_filter_by_a_travel_country(monkeypatch: pytest.MonkeyPatch) -> None:
    text = "E. coli isolates with blaNDM from a patient in Boston who had travelled to India"
    _install_extraction(
        monkeypatch,
        json.dumps({"year_relation": "none", "place": "India", "place_alt": "India", "place_role": "other"}),
    )
    result = await graph_module.plan_node(_plan_state(text))
    tool_input = result["tool_calls"][0].tool_input.root
    assert tool_input.location_names is None
    assert result["isolate_question"].filters_not_applied == ()


@pytest.mark.parametrize("reply", ["I cannot help with that.", "", "{", '{"place_role": "maybe"}'])
@pytest.mark.asyncio
async def test_an_unreadable_extraction_reply_runs_unfiltered_and_says_so(
    monkeypatch: pytest.MonkeyPatch, reply: str
) -> None:
    _install_extraction(monkeypatch, reply)
    result = await graph_module.plan_node(_plan_state(KPC.format(tail="since 2020?")))
    tool_input = result["tool_calls"][0].tool_input.root
    assert tool_input.collection_year_min is None and tool_input.location_names is None
    question = result["isolate_question"]
    assert question.filters_not_applied == (isolate_filters.CHECK_FAILED,)
    notes = graph_module._isolate_filter_notes({"isolate_question": question})
    assert notes == [isolate_filters.CHECK_FAILED]


@pytest.mark.asyncio
async def test_a_call_that_raises_the_harness_error_also_runs_unfiltered_and_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _boom(*args: Any, **kwargs: Any) -> Any:
        raise graph_module.cost_control.QueryCapExceededError(
            "cap", query_cost_usd=0.3, query_cap_usd=0.25, estimated_call_cost_usd=0.01
        )

    monkeypatch.setattr(graph_module, "_dispatch_tier_call", _boom)
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    result = await graph_module.plan_node(_plan_state(KPC.format(tail="since 2020?")))
    assert result["isolate_question"].filters_not_applied == (isolate_filters.CHECK_FAILED,)


@pytest.mark.asyncio
async def test_a_gene_question_never_reaches_the_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    """The gate. A non-isolate question's Plan makes no extraction call and its
    result carries no isolate question."""
    calls = _install_extraction(monkeypatch, "{}")
    state = _state(
        GENE_QUESTION,
        resolved_entities=[EventResolvedEntity(text="BRCA1", curie="NCBIGene:672", confidence=1.0)],
        query_class="single_hop",
    )
    result = await graph_module.plan_node(state)
    assert calls == []
    assert "isolate_question" not in result


@pytest.mark.asyncio
async def test_an_isolate_question_still_asking_which_record_makes_no_extraction_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_extraction(monkeypatch, "{}")
    question = isolate_search.parse_isolate_question(NO_GENE_QUESTION)
    assert question is not None and question.clarification is not None
    state = _state(
        NO_GENE_QUESTION,
        query_class="exploratory",
        isolate_question=question,
        clarification_needed=question.clarification,
    )
    await graph_module.plan_node(state)
    assert calls == []


@pytest.mark.asyncio
async def test_think_never_makes_the_extraction_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """Think is as on develop for every question, isolate ones included."""
    _install_model(monkeypatch)

    async def _never(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Think reached the isolate filter extraction")

    monkeypatch.setattr(graph_module, "_isolate_question_with_filters", _never)
    for text in (KPC.format(tail="since 2020?"), GENE_QUESTION):
        result = await graph_module.think_node(_state(text))
        assert "step_error" not in result
    assert isolate_filters.__name__ not in graph_module._THINK_SYSTEM_INSTRUCTION


# ---------------------------------------------------------------------------
# The notes under the answer
# ---------------------------------------------------------------------------


def _filtered_state(
    question: isolate_search.IsolateQuestion, report: IsolateFilterReport, *, total: int = 580,
    complete: bool = True,
) -> dict[str, Any]:
    output = PathogenDetectionOutput(
        status="ok" if total else "empty",
        mode="isolate_search",
        isolate_count=min(total, 20),
        total_available=total,
        truncated=total > 20,
        rows_scanned=1000,
        scan_complete=complete,
        filter_report=report,
    )
    return {"isolate_question": question, "layer3_raw_outputs": {"pd-1": output}}


def _question_with(**fields: Any) -> isolate_search.IsolateQuestion:
    base = isolate_search.parse_isolate_question(KPC.format(tail="in the USA since 2020?"))
    assert base is not None
    from dataclasses import replace

    return replace(base, **fields)


def test_the_applied_filters_are_shown_exactly_as_applied_and_the_count_names_them() -> None:
    question = _question_with(places=("USA",), place_as_written="USA", year_min=2020)
    report = IsolateFilterReport(
        place_requested=["USA"], place_applied=True, place_spellings_matched=["USA"],
        year_min=2020, left_out_no_year=0,
    )
    state = _filtered_state(question, report)
    assert graph_module._isolate_filter_notes(state) == [
        "Filters applied: isolates collected in USA, in 2020 or later."
    ]
    count = graph_module._isolate_count_note(state)
    assert count is not None and "with these genes collected in USA, in 2020 or later" in count


def test_a_widened_place_is_shown_with_what_the_person_wrote() -> None:
    question = _question_with(places=("California", "USA"), place_as_written="California", year_min=None)
    report = IsolateFilterReport(
        place_requested=["California", "USA"], place_applied=True, place_spellings_matched=["USA"]
    )
    notes = graph_module._isolate_filter_notes(_filtered_state(question, report))
    assert notes == ["Filters applied: isolates collected in USA (you wrote: California)."]


def test_the_undated_isolates_left_out_are_counted_in_words() -> None:
    question = _question_with(places=("USA",), place_as_written="USA", year_min=2020)
    report = IsolateFilterReport(
        place_requested=["USA"], place_applied=True, place_spellings_matched=["USA"],
        year_min=2020, left_out_no_year=231,
    )
    notes = graph_module._isolate_filter_notes(_filtered_state(question, report))
    assert any(
        n.startswith("231 isolates have no collection date the year filter can read")
        and "Ask again without the year" in n
        for n in notes
    ), notes
    cut = graph_module._isolate_filter_notes(_filtered_state(question, report, complete=False))
    assert any(n.startswith("At least 231 isolates") for n in cut), cut


def test_a_place_the_file_does_not_hold_is_said_not_applied_with_places_to_type() -> None:
    question = _question_with(places=("Atlantis",), place_as_written="Atlantis")
    report = IsolateFilterReport(
        place_requested=["Atlantis"], place_applied=False, file_places_example=["USA", "Canada"]
    )
    state = _filtered_state(question, report)
    notes = graph_module._isolate_filter_notes(state)
    assert len(notes) == 1
    assert "The place 'Atlantis' could not be applied" in notes[0]
    assert "isolates from every place are counted" in notes[0]
    assert "Places that do appear include USA, Canada." in notes[0]
    assert not any(n.startswith("Filters applied") for n in notes), "never shown as applied"
    count = graph_module._isolate_count_note(state)
    assert count is not None and "collected in" not in count


def test_a_question_with_no_filter_gets_no_filter_note_and_the_same_count_sentence() -> None:
    question = _question_with()
    output = PathogenDetectionOutput(
        status="ok", mode="isolate_search", isolate_count=20, total_available=21_004,
        truncated=True, rows_scanned=584_433, scan_complete=True,
    )
    state = {"isolate_question": question, "layer3_raw_outputs": {"pd-1": output}}
    assert graph_module._isolate_filter_notes(state) == []
    assert graph_module._isolate_count_note(state) == (
        "Pathogen Detection lists 21,004 Escherichia coli isolates with these genes; "
        "the first 20 in the snapshot are shown."
    )
    assert isolate_search.count_sentence("Escherichia coli", 20, 21_004, True) == (
        graph_module._isolate_count_note(state)
    )
