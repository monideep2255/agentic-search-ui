"""Fix-plan item 12.3, REDESIGNED 2026-09-24: `core.clarify`'s own strict
parse, in isolation from the graph.

The product owner's instruction was "Please do not hardcode! Hopefully not
that dumb", so the decision and the four options now come from a guard-tier
model reply rather than a word list and four templates. What stays code, and
what this file grades, is the STRICT bound on what a reply may say: a
`ClarifyDecision` this module accepts is always safe to hand straight to
`ThinkPayload.clarifying_question`/`clarifying_options` with no further
checking, and anything this module rejects becomes `ClarifyUnavailableError`,
never a fabricated or partially-trusted decision.

Exercised:
    `ClarifyDecision` accepts a well-formed `ask_back=True` reply (2, 3 and
    4 options) and a well-formed `ask_back=False` reply, and rejects: too
    few or too many options, a question or option that does not read as a
    question, an empty question or option, a string over the character
    bound, an extra field, and a missing required field.
    `parse_clarify_reply` accepts a code-fenced reply exactly like a bare
    one, and raises `ClarifyUnavailableError`, never any other exception,
    on invalid JSON, on JSON that is not an object, and on a
    schema-invalid object.
    `build_clarify_messages` returns exactly a system and a user message,
    the system message is the fixed instruction unchanged, the user
    message carries the question inside matching delimiter tags, and two
    calls for the same text use two DIFFERENT tags.

NOT exercised: the guard-tier call itself, the 1-to-3-word trigger, or the
fail-open behaviour on a failed call. `core.graph._clarify_or_proceed` and
`think_node`'s wiring own those; `test_bare_topic_clarification.py` covers
them through the real five-node graph with the model stubbed.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from system_03_search_agent.core import clarify


def _reply(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "ask_back": True,
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


class TestClarifyDecisionAskBackTrue:
    @pytest.mark.parametrize("count", [2, 3, 4])
    def test_accepts_two_to_four_options(self, count: int) -> None:
        options = [f"Is this option {i}?" for i in range(count)]
        decision = clarify.ClarifyDecision.model_validate(_reply(options=options))
        assert decision.ask_back is True
        assert len(decision.options) == count

    def test_rejects_one_option(self) -> None:
        with pytest.raises(ValidationError):
            clarify.ClarifyDecision.model_validate(_reply(options=["Only one?"]))

    def test_rejects_zero_options(self) -> None:
        with pytest.raises(ValidationError):
            clarify.ClarifyDecision.model_validate(_reply(options=[]))

    def test_rejects_five_options(self) -> None:
        # Caught by `Field(max_length=4)` itself, before the conditional
        # validator ever runs, so this also proves the bound holds
        # regardless of `ask_back`.
        options = [f"Option {i}?" for i in range(5)]
        with pytest.raises(ValidationError):
            clarify.ClarifyDecision.model_validate(_reply(options=options))

    def test_rejects_a_question_with_no_question_mark(self) -> None:
        with pytest.raises(ValidationError):
            clarify.ClarifyDecision.model_validate(
                _reply(question="What would you like to know about insulin")
            )

    def test_rejects_an_empty_question(self) -> None:
        with pytest.raises(ValidationError):
            clarify.ClarifyDecision.model_validate(_reply(question=""))

    def test_rejects_a_whitespace_only_question(self) -> None:
        with pytest.raises(ValidationError):
            clarify.ClarifyDecision.model_validate(_reply(question="   "))

    def test_rejects_an_option_with_no_question_mark(self) -> None:
        with pytest.raises(ValidationError):
            clarify.ClarifyDecision.model_validate(
                _reply(options=["What is insulin", "A real one?"])
            )

    def test_rejects_an_empty_option(self) -> None:
        with pytest.raises(ValidationError):
            clarify.ClarifyDecision.model_validate(
                _reply(options=["", "A real one?"])
            )

    def test_rejects_a_question_over_the_character_bound(self) -> None:
        with pytest.raises(ValidationError):
            clarify.ClarifyDecision.model_validate(
                _reply(question="A" * (clarify.MAX_CLARIFY_TEXT_CHARS + 1) + "?")
            )

    def test_accepts_a_question_at_the_character_bound(self) -> None:
        # The bound counts the whole string INCLUDING its own "?", so the
        # question mark itself is the last of the allowed characters.
        question = "A" * (clarify.MAX_CLARIFY_TEXT_CHARS - 1) + "?"
        assert len(question) == clarify.MAX_CLARIFY_TEXT_CHARS
        decision = clarify.ClarifyDecision.model_validate(_reply(question=question))
        assert decision.question == question

    def test_rejects_an_option_over_the_character_bound(self) -> None:
        with pytest.raises(ValidationError):
            clarify.ClarifyDecision.model_validate(
                _reply(options=["A" * (clarify.MAX_CLARIFY_TEXT_CHARS + 1) + "?", "A real one?"])
            )


class TestClarifyDecisionAskBackFalse:
    def test_accepts_empty_question_and_options(self) -> None:
        decision = clarify.ClarifyDecision.model_validate(
            {"ask_back": False, "question": "", "options": []}
        )
        assert decision.ask_back is False
        assert decision.question == ""
        assert decision.options == []

    def test_the_looks_like_a_question_checks_do_not_apply(self) -> None:
        # The conditional validator returns immediately when ask_back is
        # false, so a false reply is never held to the "looks like a
        # question" bar its own options never need to clear.
        decision = clarify.ClarifyDecision.model_validate(
            {"ask_back": False, "question": "not a question", "options": ["also not one"]}
        )
        assert decision.ask_back is False

    def test_still_rejects_five_options(self) -> None:
        options = [f"option {i}" for i in range(5)]
        with pytest.raises(ValidationError):
            clarify.ClarifyDecision.model_validate(
                {"ask_back": False, "question": "", "options": options}
            )


class TestClarifyDecisionShape:
    def test_rejects_an_extra_field(self) -> None:
        with pytest.raises(ValidationError):
            clarify.ClarifyDecision.model_validate(_reply(extra_field="unexpected"))

    @pytest.mark.parametrize("missing", ["ask_back", "question", "options"])
    def test_rejects_a_missing_required_field(self, missing: str) -> None:
        payload = _reply()
        del payload[missing]
        with pytest.raises(ValidationError):
            clarify.ClarifyDecision.model_validate(payload)

    def test_rejects_ask_back_as_an_unrecognisable_string(self) -> None:
        # Pydantic's own lax bool coercion accepts "true"/"false"/"yes"/"no"
        # and similar, so this uses a string that is not one of those,
        # rather than asserting a coercion pydantic deliberately performs.
        with pytest.raises(ValidationError):
            clarify.ClarifyDecision.model_validate(_reply(ask_back="banana"))


class TestParseClarifyReply:
    def test_accepts_a_bare_json_object(self) -> None:
        decision = clarify.parse_clarify_reply(json.dumps(_reply()))
        assert decision.ask_back is True

    def test_accepts_a_code_fenced_json_object(self) -> None:
        fenced = "```json\n" + json.dumps(_reply()) + "\n```"
        decision = clarify.parse_clarify_reply(fenced)
        assert decision.ask_back is True

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
        # The caller (`core.graph._clarify_or_proceed`) catches exactly
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
