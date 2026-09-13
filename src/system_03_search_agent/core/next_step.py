"""The go-deeper follow-up: the query an accepted next-step offer sends, and
how the next turn recognises it (UI fix set 7, item 7.2, 2026-09-13).

Depends on:
    - system_03_search_agent.synthesis.findings (SynthFinding, read for its
      `entity_type` only)

Reads:
    - Nothing at import time. No environment, no network.

Writes:
    - Nothing. Pure functions over strings.

## What broke

`DonePayload.next_step` is a yes/no question for the reader: "Would you like
me to go through the 10 further sequence variant records found for this
question?". The web UI sent that sentence verbatim as the next query when
the reader clicked "Yes, go deeper". Measured on 2026-09-13 with the real
models: the guardrail admitted it, Think classified it as a question with
no entities, session memory bound BRCA1, the graph returned the same
variants, Synth wrote prose answering a yes/no question, the grounding pass
stripped all of it, and the turn refused. Even when it grounded, it would
have reported the SAME first twenty records again, because nothing told
the write step which records the reader had already seen.

## The two halves, kept in one file on purpose

`build_next_step_query` writes the sentence the surface should send, and
`is_go_deeper_query` recognises that sentence when it comes back as the
next `Query.text`. They are one template and one pattern derived from it,
side by side, so an edit to the wording cannot leave the detector matching
a sentence nobody sends any more. `test_next_step_offer.py` asserts the
round trip: every sentence the builder can produce is one the detector
accepts.

The sentence is built IN CODE from two things already known to be true:
the record type of the findings the answer left out, and the entity the
turn was about. Never a model, for the reason `DonePayload.next_step`'s
docstring gives: a generated follow-up is a claim about what the graph
holds.

## Why the entity is named rather than left to a pronoun

"Which other sequence variant records are linked to it?" would work only
while session memory still binds "it" to the right entity. Naming the
entity makes the follow-up self-contained: Think resolves "BRCA1" or
"NCBIGene:672" on its own, through the same exact-identifier and
live-confirmation path any first question takes, so the go-deeper turn
does not depend on the memory antecedent still pointing where it pointed
one turn ago.
"""

from __future__ import annotations

import re
from typing import Any

#: The sentence an accepted offer sends. `{noun}` is the plural record-type
#: noun (`entity_type_noun`), `{entity}` the entity label of the turn.
GO_DEEPER_TEMPLATE = "Which other {noun} records are linked to {entity}?"

#: The same sentence as a pattern. Anchored at both ends and case-folded, so
#: a question that merely contains the words is not mistaken for the
#: follow-up. The two capture groups are the noun and the entity, in the
#: template's order.
_GO_DEEPER_PATTERN = re.compile(
    r"^\s*which other (?P<noun>.+?) records are linked to (?P<entity>.+?)\?\s*$",
    re.IGNORECASE,
)

#: Splits a CamelCase BioLink category such as `SequenceVariant` into its
#: words. A lower-case boundary followed by an upper-case letter is the
#: seam; runs of capitals (`RNA`) are left whole.
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

_MAX_ENTITY_LABEL_CHARS = 200


def entity_type_noun(entity_type: str) -> str:
    """`SequenceVariant` becomes `sequence variant`, `Disease` becomes `disease`.

    Lower-cased plain words, because the sentence is shown to a reader in
    the history rail and sent to Think, and a BioLink category name in the
    middle of an English question reads as a code rather than a subject.
    """
    words = _CAMEL_BOUNDARY.split(entity_type.strip())
    return " ".join(word.lower() for word in words if word)


#: `cypher_provenance._shape_derived_value` labels a projected scalar column
#: (`RETURN v, v.name` yields a `v.name` row beside the `v` row) with this
#: pseudo-type. It is a second view of a record already in the result, never a
#: record type of its own, so it carries no vote on what the omitted records
#: ARE. There is no shared constant for it in `tools/`; the literal is the
#: same one `cypher_query.py` and `cypher_provenance.py` compare against.
_DERIVED_ROW_TYPE = "derived"


def shared_record_type(omitted: list[Any]) -> str | None:
    """The ONE graph record type the omitted findings share, or None.

    Used by the incompleteness note, the offer and the follow-up query, so
    the three can never disagree about what kind of record is being offered.

    Measured live on 2026-09-13 before this helper existed: the flagship
    variant query returned every ClinVar variant twice, once as a
    `SequenceVariant` node row and once as a `derived` projection row of the
    same record, and the offer was built from the bare set of types. When the
    omitted rows happened to be all `derived` the offer read "10 further
    derived records" and the follow-up "Which other derived records are
    linked to BRCA1?"; when they mixed, the offer declined outright and the
    reader never saw a button. Ignoring the projection rows gives the answer
    the reader would give: these are sequence variant records.

    A genuinely mixed bag (Disease rows beside Gene rows) still returns None,
    because the only honest phrasing for it is too vague to be worth
    showing. Rows with no type at all are ignored the same way.
    """
    types = {
        entity_type.strip()
        for finding in omitted
        if (entity_type := str(getattr(finding, "entity_type", "") or ""))
        and entity_type.strip().lower() != _DERIVED_ROW_TYPE
    }
    if len(types) != 1:
        return None
    return types.pop()


def build_next_step_query(omitted: list[Any], entity_label: str) -> str | None:
    """The question to send when the reader accepts the offer, or None.

    Declines under exactly the conditions `core.graph._build_next_step_offer`
    declines for the offer text itself, so the two fields on `DonePayload`
    are set together or not at all: nothing omitted, a mixed bag of record
    types, or rows with no usable type. It also declines when the turn has
    no entity label to name, because a follow-up that names nothing is the
    pronoun form this module exists to replace.
    """
    label = " ".join(entity_label.split())[:_MAX_ENTITY_LABEL_CHARS]
    if not omitted or not label:
        return None
    record_type = shared_record_type(omitted)
    if record_type is None:
        return None
    noun = entity_type_noun(record_type)
    if not noun:
        return None
    return GO_DEEPER_TEMPLATE.format(noun=noun, entity=label)


def is_go_deeper_query(text: str) -> bool:
    """Whether `text` is a sentence `build_next_step_query` produces.

    Deterministic and exact by construction: this is the template's own
    pattern, not a similarity test. A reader who types the sentence by hand
    gets the same treatment as one who clicked the button, which is correct,
    since the sentence means the same thing either way.
    """
    return _GO_DEEPER_PATTERN.match(text) is not None


__all__ = [
    "GO_DEEPER_TEMPLATE",
    "build_next_step_query",
    "entity_type_noun",
    "is_go_deeper_query",
    "shared_record_type",
]
