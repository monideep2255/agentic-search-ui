"""`CitationPayload.snippet` (build phase 8.8, "card 44", "answer on top,
evidence below"): the third additive, optional field, same pattern as
`snapshot_date` and `entity_name`.

Kept in its own file rather than added to `test_events.py` directly, since
that shared file may be edited concurrently by another builder this same
phase; this file only imports `CitationPayload` and duplicates the small
`_valid_kwargs` baseline `test_events.py`'s own `TestCitationPayload`
class already uses, so there is nothing here for the two files to
conflict over.

Covers: the field defaults to `None` (every payload built before this
phase still validates unchanged, per Section 2.6's additive-only rule),
accepts a real value, accepts an explicit `None`, and rejects a value over
its 500-character `max_length`, matching `synthesis.snippets.
MAX_SENTENCE_CHARS`. Does not cover whether a `snippet` value actually
came from the cited paper's own abstract; that is a property of the
caller (the future `core/graph.py` wiring), not of the schema, and no
schema-level check can enforce it.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from system_03_search_agent.contracts.events import CitationPayload


def _valid_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "citation_id": "c_1",
        "display_index": 1,
        "source": "PubMed",
        "source_id": "12345",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/12345",
        "layer": "layer_3_enrichment",
        "field": "abstract",
        "claim_text": "The gene increases risk of early onset disease.",
        "evidence_kind": "literature_comention",
        "assertion_confidence": "moderate",
        "population_ancestry_context": None,
        "license": "publisher_terms_apply",
    }
    base.update(overrides)
    return base


class TestCitationSnippet:
    def test_defaults_to_none(self) -> None:
        payload = CitationPayload(**_valid_kwargs())
        assert payload.snippet is None

    def test_explicit_none_accepted(self) -> None:
        payload = CitationPayload(**_valid_kwargs(snippet=None))
        assert payload.snippet is None

    def test_a_real_sentence_is_accepted_verbatim(self) -> None:
        sentence = "The gene increases risk of early onset disease across every cohort tested."
        payload = CitationPayload(**_valid_kwargs(snippet=sentence))
        assert payload.snippet == sentence

    def test_exactly_500_characters_accepted(self) -> None:
        sentence = "x" * 500
        payload = CitationPayload(**_valid_kwargs(snippet=sentence))
        assert payload.snippet == sentence

    def test_over_500_characters_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CitationPayload(**_valid_kwargs(snippet="x" * 501))

    def test_still_forbids_an_unrelated_extra_field(self) -> None:
        # Guards against a future edit accidentally dropping
        # `model_config = ConfigDict(extra="forbid")` while adding a field.
        with pytest.raises(ValidationError):
            CitationPayload(**_valid_kwargs(some_field_nobody_declared="x"))

    def test_a_citation_with_no_sentence_has_no_snippet_key(self) -> None:
        # Develop's reader forbids extra keys and a saved row is read back by
        # it on a rollback, so an absent sentence leaves the key out.
        dumped = CitationPayload(**_valid_kwargs()).model_dump()
        assert "snippet" not in dumped
        assert "snippet" not in CitationPayload(**_valid_kwargs(snippet=None)).model_dump_json()

    def test_a_citation_with_a_sentence_carries_the_key(self) -> None:
        sentence = "The gene increases risk of early onset disease across every cohort tested."
        assert CitationPayload(**_valid_kwargs(snippet=sentence)).model_dump()["snippet"] == sentence

