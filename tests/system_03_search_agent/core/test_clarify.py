"""Fix-plan item 12.3: `core.clarify`'s own strict parse, in isolation from
the graph.

REDESIGNED 2026-09-24 ("Please do not hardcode! Hopefully not that dumb")
and SPLIT 2026-09-25 (build phase 8.2, builder J): whether to ask back is
now `decide(point="think.ask_back")`'s call, and `core.clarify` only WRITES
the question and the choices. What stays code, and what this file grades,
is the STRICT bound on what a reply may say: a `ClarifyChoices` this module
accepts is always safe to hand straight to
`ThinkPayload.clarifying_question`/`clarifying_options` with no further
checking, and anything this module rejects becomes `ClarifyUnavailableError`,
never a fabricated or partially-trusted question.

Exercised:
    `ClarifyChoices` accepts a well-formed reply (2, 3 and 4 options), and
    rejects: too few or too many options, a question or option that does not
    read as a question, an empty question or option, a string over the
    character bound, an extra field (including the retired `ask_back`, so
    the writer can never make the decision again), and a missing required
    field.
    `parse_clarify_reply` accepts a code-fenced reply exactly like a bare
    one, and raises `ClarifyUnavailableError`, never any other exception,
    on invalid JSON, on JSON that is not an object, and on a
    schema-invalid object.
    `build_clarify_messages` returns exactly a system and a user message,
    the system message is the fixed instruction unchanged, the user
    message carries the question inside matching delimiter tags, and two
    calls for the same text use two DIFFERENT tags.

NOT exercised: the guard-tier call itself, the ask-back decision, the
1-to-3-word trigger, or the fail-open behaviour on a failed call.
`core.graph`'s `think_node` and `_write_clarify_choices` own those;
`test_bare_topic_clarification.py` covers them through the real five-node
graph with the model and `decide()` stubbed.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from system_03_search_agent.core import clarify


def _reply(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "question": "What would you like to know about insulin?",
        "options": [
            "What is insulin?",
            "Which genes are linked to insulin production?",
            "Are there clinical trials on insulin resistance?",
            "What does recent research say about insulin?",
        ],
    }
    base.update(overrides)
    return base


class TestClarifyChoices:
    @pytest.mark.parametrize("count", [2, 3, 4])
    def test_accepts_two_to_four_options(self, count: int) -> None:
        options = [f"Is this option {i}?" for i in range(count)]
        choices = clarify.ClarifyChoices.model_validate(_reply(options=options))
        assert len(choices.options) == count

    def test_rejects_one_option(self) -> None:
        with pytest.raises(ValidationError):
            clarify.ClarifyChoices.model_validate(_reply(options=["Only one?"]))

    def test_rejects_zero_options(self) -> None:
        with pytest.raises(ValidationError):
            clarify.ClarifyChoices.model_validate(_reply(options=[]))

    def test_rejects_five_options(self) -> None:
        # Caught by `Field(max_length=4)` itself, before the validator runs.
        options = [f"Option {i}?" for i in range(5)]
        with pytest.raises(ValidationError):
            clarify.ClarifyChoices.model_validate(_reply(options=options))

    def test_rejects_a_question_with_no_question_mark(self) -> None:
        with pytest.raises(ValidationError):
            clarify.ClarifyChoices.model_validate(
                _reply(question="What would you like to know about insulin")
            )

    def test_rejects_an_empty_question(self) -> None:
        with pytest.raises(ValidationError):
            clarify.ClarifyChoices.model_validate(_reply(question=""))

    def test_rejects_a_whitespace_only_question(self) -> None:
        with pytest.raises(ValidationError):
            clarify.ClarifyChoices.model_validate(_reply(question="   "))

    def test_rejects_an_option_with_no_question_mark(self) -> None:
        with pytest.raises(ValidationError):
            clarify.ClarifyChoices.model_validate(
                _reply(options=["What is insulin", "A real one?"])
            )

    def test_rejects_an_empty_option(self) -> None:
        with pytest.raises(ValidationError):
            clarify.ClarifyChoices.model_validate(
                _reply(options=["", "A real one?"])
            )

    def test_rejects_a_question_over_the_character_bound(self) -> None:
        with pytest.raises(ValidationError):
            clarify.ClarifyChoices.model_validate(
                _reply(question="A" * (clarify.MAX_CLARIFY_TEXT_CHARS + 1) + "?")
            )

    def test_accepts_a_question_at_the_character_bound(self) -> None:
        # The bound counts the whole string INCLUDING its own "?", so the
        # question mark itself is the last of the allowed characters.
        question = "A" * (clarify.MAX_CLARIFY_TEXT_CHARS - 1) + "?"
        assert len(question) == clarify.MAX_CLARIFY_TEXT_CHARS
        choices = clarify.ClarifyChoices.model_validate(_reply(question=question))
        assert choices.question == question

    def test_rejects_an_option_over_the_character_bound(self) -> None:
        with pytest.raises(ValidationError):
            clarify.ClarifyChoices.model_validate(
                _reply(options=["A" * (clarify.MAX_CLARIFY_TEXT_CHARS + 1) + "?", "A real one?"])
            )


class TestClarifyChoicesShape:
    def test_rejects_an_extra_field(self) -> None:
        with pytest.raises(ValidationError):
            clarify.ClarifyChoices.model_validate(_reply(extra_field="unexpected"))

    @pytest.mark.parametrize("missing", ["question", "options"])
    def test_rejects_a_missing_required_field(self, missing: str) -> None:
        payload = _reply()
        del payload[missing]
        with pytest.raises(ValidationError):
            clarify.ClarifyChoices.model_validate(payload)

    def test_rejects_the_retired_ask_back_field(self) -> None:
        # The writer no longer decides whether to ask (build phase 8.2):
        # a reply that tries to is rejected whole, never half-read.
        with pytest.raises(ValidationError):
            clarify.ClarifyChoices.model_validate(_reply(ask_back=True))


class TestParseClarifyReply:
    def test_accepts_a_bare_json_object(self) -> None:
        choices = clarify.parse_clarify_reply(json.dumps(_reply()))
        assert choices.question == "What would you like to know about insulin?"

    def test_accepts_a_code_fenced_json_object(self) -> None:
        fenced = "```json\n" + json.dumps(_reply()) + "\n```"
        choices = clarify.parse_clarify_reply(fenced)
        assert len(choices.options) == 4

    def test_raises_clarify_unavailable_on_invalid_json(self) -> None:
        with pytest.raises(clarify.ClarifyUnavailableError):
            clarify.parse_clarify_reply("this is not json at all")

    def test_raises_clarify_unavailable_on_a_json_array(self) -> None:
        with pytest.raises(clarify.ClarifyUnavailableError):
            clarify.parse_clarify_reply(json.dumps([1, 2, 3]))

    def test_raises_clarify_unavailable_on_a_json_string(self) -> None:
        with pytest.raises(clarify.ClarifyUnavailableError):
            clarify.parse_clarify_reply(json.dumps("just a string"))

    def test_raises_clarify_unavailable_on_a_schema_invalid_object(self) -> None:
        with pytest.raises(clarify.ClarifyUnavailableError):
            clarify.parse_clarify_reply(json.dumps(_reply(options=["only one?"])))

    def test_raises_clarify_unavailable_never_a_bare_validation_error(self) -> None:
        # The caller (`core.graph._write_clarify_choices`) catches exactly
        # `ClarifyUnavailableError`. A `ValidationError` escaping this
        # function unwrapped would not be caught there and would crash
        # `think_node` instead of falling through to search.
        try:
            clarify.parse_clarify_reply(json.dumps(_reply(options=["only one?"])))
        except clarify.ClarifyUnavailableError:
            pass
        except ValidationError:
            pytest.fail("ValidationError escaped parse_clarify_reply unwrapped")


class TestBuildClarifyMessages:
    def test_returns_exactly_a_system_and_a_user_message(self) -> None:
        messages = clarify.build_clarify_messages("insulin")
        assert [m["role"] for m in messages] == ["system", "user"]

    def test_the_system_message_is_the_fixed_instruction(self) -> None:
        messages = clarify.build_clarify_messages("insulin")
        assert messages[0]["content"] == clarify.CLARIFY_SYSTEM_INSTRUCTION

    def test_the_user_message_carries_the_question_inside_matching_tags(self) -> None:
        messages = clarify.build_clarify_messages("insulin")
        content = messages[1]["content"]
        assert content.startswith("<clarify-")
        assert content.rstrip().endswith(">")
        assert "\ninsulin\n" in content
        # The opening and closing tags share one identifier.
        opening = content.split(">", 1)[0].removeprefix("<")
        assert f"</{opening}>" in content

    def test_two_calls_use_two_different_tags(self) -> None:
        # An unguessable per-request tag, not character stripping, is what
        # stops the question from forging the closing tag (a variant name
        # can legitimately contain "<" or ">"). Two calls must not reuse
        # the same tag, or it would not be unguessable.
        first = clarify.build_clarify_messages("insulin")[1]["content"]
        second = clarify.build_clarify_messages("insulin")[1]["content"]
        assert first != second

    def test_does_not_strip_angle_brackets_from_the_question(self) -> None:
        # HGVS variant notation uses ">" (c.123A>G). Stripping it would
        # corrupt exactly the identifiers this system exists to look up.
        messages = clarify.build_clarify_messages("c.123A>G")
        assert "c.123A>G" in messages[1]["content"]


class TestRecentWindowChoices:
    """Build phase 8.2, card 4: the three windows, in the person's words,
    each readable back by the planner as exactly the window it names."""

    def test_three_windows_in_the_product_owners_order(self) -> None:
        choices = clarify.recent_window_choices("recent papers on statins")
        assert choices.question == clarify.RECENT_WINDOW_QUESTION
        assert choices.options == [
            "Recent papers on statins from the last 12 months?",
            "Recent papers on statins from the last 5 years?",
            "Recent papers on statins from the last 10 years?",
        ]

    def test_each_choice_reads_back_as_its_own_window(self) -> None:
        from datetime import date

        from system_03_search_agent.core import breadth_plan

        today = date(2026, 9, 25)
        labels = [
            breadth_plan.parse_publication_window(option, today=today).label  # type: ignore[union-attr]
            for option in clarify.recent_window_choices("recent papers on statins?").options
        ]
        assert labels == ["the last 12 months", "the last 5 years", "the last 10 years"]

    def test_a_long_question_is_cut_at_a_word_and_stays_in_bounds(self) -> None:
        long_question = "recent papers on " + "statin " * 60
        choices = clarify.recent_window_choices(long_question)
        for option in choices.options:
            assert len(option) <= clarify.MAX_CLARIFY_TEXT_CHARS
            assert option.endswith("?")
            assert " stati from" not in option
