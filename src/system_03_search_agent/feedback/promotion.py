"""Stage 5: few-shot promotion (Section 16 stage 5, Section 17's two payload shapes).

Depends on:
    - system_03_search_agent.data.models (CqCandidate, Interaction)
    - system_03_search_agent.data.session (session_scope)
    - system_03_search_agent.feedback.contracts (QueryClass, the same
      five-value Literal `interactions.query_class`'s CHECK constraint
      restates)

Reads:
    - The `cq_candidates` and `interactions` tables in the user-data
      database
    - orchestrator/few_shot_examples.json and eval/golden_dataset.json, to
      check idempotency before appending

Writes:
    - The `cq_candidates` table (`status`, `promoted_at`, `few_shot_example`,
      `eval_case`, `updated_at`)
    - orchestrator/few_shot_examples.json (append only)
    - eval/golden_dataset.json (append only)

## The scope seam with build phase 4.7

Section 17 places the few-shot pool in a versioned file loaded once at
process start, and build phase 4.7 owns the routing that CONSUMES it. This
module owns the path that WRITES to it. As of build phase 4.7's T-4.7-02
and T-4.7-03, `orchestrator.few_shot_pool` is the loader that reads
`orchestrator/few_shot_examples.json` once per process
(`few_shot_pool.load_pool`) and the single writer both this module and any
other caller append through (`few_shot_pool.append_example`, closing
F-4.6-A-08: two promotions running at once could previously interleave a
bare read-modify-write and corrupt the file). `_append_pool_entry` below
delegates to it rather than keeping a second, independently-drifting copy
of the write logic. `_append_golden_entry`, the golden-dataset half, is
unaffected: F-4.6-A-08 and build phase 4.7's premise gate (T-4.7-09, arm
P11) are both scoped to the pool file specifically, since that is the file
a running process reads at startup; the golden dataset has no such reader
yet.

## Why the golden dataset lives at `eval/golden_dataset.json`

The Phase 4 golden dataset itself, the 50-query expansion set, is a
Section 25 build-order item owned by build phase 5.1, not this phase. This
module only needs somewhere durable to append one `eval_case` at a time as
candidates get promoted, in the shape Section 17 already fixes, so that
build phase 5.1 has real promoted cases waiting when it opens rather than
starting from zero. `eval/` at the repository root, sibling to `src/` and
`tests/`, is data rather than test code or application code, and
`tests/system_03_search_agent/eval/` (which already exists) is reserved for
this repository's own test suite, not for a data artifact a running
promotion script writes to. `golden_dataset.json` was not claimed by any
other module, path, or convention at the time this file was written
(verified by search before creating it).

## Loader-friendliness (`.claude/rules/prompt-cache-discipline.md`)

Both destination files are a single JSON object (`{"schema_version": 1,
"examples": [...]}` and `{"schema_version": 1, "cases": [...]}`), not a
bare array and not one-object-per-line. A loader reads the whole file once
at process start and holds it in memory; this shape is exactly what
`json.load()` wants and needs no streaming or line-splitting logic on the
reading side. Nothing in this repository reads either file per request, and
this module does not add such a reader.
"""

from __future__ import annotations

import argparse
import copy
import json
import uuid
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from system_03_search_agent.data.models import CqCandidate, Interaction
from system_03_search_agent.data.session import session_scope
from system_03_search_agent.feedback.contracts import QueryClass

#: `src/system_03_search_agent/feedback/promotion.py` -> parents[1] is
#: `src/system_03_search_agent`, so this resolves to
#: `src/system_03_search_agent/orchestrator/few_shot_examples.json`
#: regardless of the working directory a script is invoked from.
DEFAULT_POOL_PATH = Path(__file__).resolve().parents[1] / "orchestrator" / "few_shot_examples.json"

#: `parents[3]` from this file is the repository root
#: (`feedback` -> `system_03_search_agent` -> `src` -> root).
DEFAULT_GOLDEN_DATASET_PATH = Path(__file__).resolve().parents[3] / "eval" / "golden_dataset.json"

#: `few_shot_pool.append_example` (T-4.7-03) now owns the pool file's own
#: empty-document default; this module no longer needs one for the pool
#: side, only for the golden dataset below, which `_append_pool_entry` does
#: not touch.
_EMPTY_GOLDEN_DATASET: dict[str, Any] = {
    "schema_version": 1,
    "_scope_note": (
        "Written by build phase 4.6's promotion path (T-4.6-11), one "
        "`eval_case` per approved cq_candidates row. The full Phase 4 "
        "golden dataset (the 50-query expansion set) is built by build "
        "phase 5.1 (Section 25); this file seeds it with real promoted "
        "cases rather than starting build phase 5.1 from zero."
    ),
    "cases": [],
}


class PrivacyViolationError(ValueError):
    """A promoted payload carries a verbatim copy of a source interaction's `query_text`.

    Section 16: "nothing promoted is a verbatim copy of one user's exact
    sentence." That sentence states the rule about what gets promoted, not
    about which field of `few_shot_example` or `eval_case` it happens to
    sit in, so the check this error guards walks every string field of
    both payloads rather than naming `query_pattern` alone (F-4.6-A-04
    found the unguarded field: `eval_case.question` landed byte-identical
    to a user's sentence in `eval/golden_dataset.json`, a file Section 16's
    own retention table keeps indefinitely even after the source
    `interactions` row is deleted). Raised rather than silently rewritten,
    because a promotion script that "fixed" the wording itself would be
    guessing at a generalization no human reviewed.
    """


class SourceInteractionsUnavailableError(PrivacyViolationError):
    """The privacy check could not verify safety: a source row it needs is gone.

    Subclasses `PrivacyViolationError` rather than a plain `ValueError` so a
    caller catching the parent still catches this. It is a distinct privacy
    refusal, not a different failure mode: `candidate.source_interaction_ids`
    names one or more rows, and fewer of them resolved to an `interactions`
    row than were named. F-4.6-A-05 found the previous check pass silently
    in exactly this case, because `any(...)` over an empty comparison set is
    `False`. A privacy control that cannot see its own input must refuse,
    not report a safety it never established. This case is distinct from a
    candidate whose `source_interaction_ids` is empty by construction (a
    hand-authored candidate with no source interactions at all, the shape
    Section 17's seed few-shot pool uses): that candidate carries no user
    sentence to protect, so it is not covered by this error and promotes
    normally once the payload check below passes.
    """


# ---------------------------------------------------------------------------
# Section 17's two JSONB payload shapes, restated as Pydantic models so a
# malformed payload fails before it ever reaches a file or a row, per
# `production-standards`' multi-agent schema gate (every payload this
# repository writes declares a schema, not just the ones that cross a model
# boundary).
# ---------------------------------------------------------------------------


class ResolvedEntityExample(BaseModel):
    """One entry of `few_shot_example.resolved_entities` (Section 17)."""

    model_config = ConfigDict(extra="forbid")

    surface_form: str = Field(..., min_length=1, max_length=200)
    curie: str = Field(..., min_length=1, max_length=200)
    entity_type: str = Field(..., min_length=1, max_length=100)


class RoutePattern(BaseModel):
    """`few_shot_example.route` (Section 17): `{layers, tools}`."""

    model_config = ConfigDict(extra="forbid")

    layers: list[str] = Field(..., min_length=1, max_length=3)
    tools: list[str] = Field(..., min_length=1, max_length=7)


class FewShotExample(BaseModel):
    """Section 17's `few_shot_example` payload, field for field.

    `query_class` reuses `feedback.contracts.QueryClass`, the same Literal
    `interactions.query_class`'s CHECK constraint restates, since Section
    17's own worked example ("exploratory") is one of that same five-value
    set and there is no reason for a second, independently-drifting copy
    of it.
    """

    model_config = ConfigDict(extra="forbid")

    query_pattern: str = Field(..., min_length=1, max_length=500)
    query_class: QueryClass
    resolved_entities: list[ResolvedEntityExample] = Field(default_factory=list, max_length=20)
    route: RoutePattern
    narrative_pattern: str = Field(..., min_length=1, max_length=500)
    citation_pattern: list[str] = Field(..., min_length=1, max_length=20)


class EvalCase(BaseModel):
    """Section 17's `eval_case` payload, field for field."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=1, max_length=500)
    expected_entities: list[str] = Field(default_factory=list, max_length=20)
    expected_layers: list[str] = Field(..., min_length=1, max_length=3)
    expected_tools: list[str] = Field(..., min_length=1, max_length=7)
    expected_citation_sources: list[str] = Field(default_factory=list, max_length=20)
    fixture_ref: str = Field(..., min_length=1, max_length=200)
    rubric_hint: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# File helpers. Read-modify-write with an atomic replace, so a promotion
# that dies mid-write never leaves a half-written JSON file behind for the
# next promotion (or a loader) to trip over.
# ---------------------------------------------------------------------------


def _read_json_object(path: Path, *, default: dict[str, Any]) -> dict[str, Any]:
    """Read `path` as a JSON object, or a fresh copy of `default` when it does not exist yet.

    As of T-4.7-03, `_append_golden_entry` is this helper's only remaining
    caller (the pool side now goes through `few_shot_pool.append_example`'s
    own atomic, lock-serialized write, which owns its own empty-document
    default). `copy.deepcopy`, not `dict(default)`: a shallow copy still
    shares the nested `"cases"` list object with the module-level
    `_EMPTY_GOLDEN_DATASET` constant, so an append below would mutate that
    shared constant in place and leak entries into every later call in the
    same process, including calls against a different file. Caught by
    `test_promote_candidate_is_idempotent_on_repeat_run`.
    """
    if not path.exists():
        return copy.deepcopy(default)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json_object(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    tmp_path.replace(path)


def _append_pool_entry(pool_path: Path, entry: dict[str, Any]) -> None:
    """Append one `few_shot_example` entry via the single, lock-serialized writer.

    Delegates to `orchestrator.few_shot_pool.append_example` (T-4.7-03),
    which closes F-4.6-A-08: this function's previous body did a bare
    read-modify-write with no lock between the two, so two promotions
    running at once could interleave and either lose an entry or leave the
    file as invalid JSON. There is now exactly one writer implementation
    for this file; this function is a thin, import-boundary-preserving
    call to it, not a second copy of the same logic.

    Imported inside the function body, not at module top, to avoid a
    circular import: `few_shot_pool` imports `FewShotExample` and
    `DEFAULT_POOL_PATH` from this module at ITS top level (T-4.7-02's
    "reuse the model rather than declaring a second one"), so this module
    cannot also import `few_shot_pool` at its own top level without the two
    trying to finish loading each other first.
    """
    from system_03_search_agent.orchestrator.few_shot_pool import append_example

    append_example(pool_path, entry)


def _append_golden_entry(golden_path: Path, entry: dict[str, Any]) -> None:
    """Append one `eval_case` entry, unless this candidate is already tagged in the file."""
    data = _read_json_object(golden_path, default=_EMPTY_GOLDEN_DATASET)
    data.setdefault("cases", [])
    if any(e.get("cq_candidate_id") == entry.get("cq_candidate_id") for e in data["cases"]):
        return
    data["cases"].append(entry)
    _write_json_object(golden_path, data)


def _source_query_texts(session: Session, candidate: CqCandidate) -> list[str]:
    if not candidate.source_interaction_ids:
        return []
    stmt = select(Interaction.query_text).where(
        Interaction.id.in_(candidate.source_interaction_ids)
    )
    return [text for (text,) in session.execute(stmt)]


def _normalize_for_comparison(text: str) -> str:
    """Collapse internal whitespace runs to one space, strip the ends, casefold.

    Still a deterministic, non-fuzzy rule: two strings either normalize to
    the same value or they do not, with no scored middle ground, which is
    what `.claude/rules/production-standards.md`'s AI answer grounding gate
    requires ("a fuzzy accept silently passes a hallucinated quote").
    Widened from a bare `.strip()` because F-4.6-A-04 defeated the
    strip-only check with a single `.capitalize()` call: `"Does my patient
    jane q doe..."` differs from the source sentence in bytes and passed,
    while remaining the identical sentence a human reader would recognize
    as unchanged. A real generalization ('{gene}' in place of the literal
    'BRCA1') changes actual words, so it still differs after this
    normalization; only a change in whitespace or letter case, neither of
    which is a generalization, is now insufficient to pass.
    """
    return " ".join(text.split()).casefold()


def _is_verbatim_copy(candidate_text: str, source_query_text: str) -> bool:
    """True when `candidate_text` is the same sentence as `source_query_text`."""
    return _normalize_for_comparison(candidate_text) == _normalize_for_comparison(source_query_text)


def _iter_string_leaves(value: Any) -> Iterator[str]:
    """Yield every string leaf inside a (possibly nested) JSON-shaped value.

    Structural coverage for the privacy check below: rather than naming the
    fields believed to carry user-authored prose (`query_pattern`,
    `question`), this walks every string anywhere in the dumped payload, so
    a field added to `FewShotExample` or `EvalCase` later is covered by
    construction the moment it exists, with nothing here to remember to
    update. F-4.6-A-04 is exactly a field, `eval_case.question`, that
    carried the same risk as the one field the previous check guarded and
    was never added to the check by hand.
    """
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_string_leaves(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_string_leaves(item)


def _find_verbatim_leaf(payload: dict[str, Any], source_texts: Sequence[str]) -> str | None:
    """Return the first string leaf of `payload` that copies a source text verbatim, or None.

    `payload` is a Section 17 payload after `.model_dump()`
    (`few_shot_example` or `eval_case`, field for field), so every string
    anywhere in either shape is checked: this is the class of "every field
    of a promoted payload that carries user-authored prose into a file
    retained indefinitely", not a list of the two fields known today.
    """
    for leaf in _iter_string_leaves(payload):
        for source_text in source_texts:
            if _is_verbatim_copy(leaf, source_text):
                return leaf
    return None


def promote_candidate(
    session: Session,
    *,
    candidate_id: uuid.UUID,
    few_shot_example: FewShotExample,
    eval_case: EvalCase,
    pool_path: Path = DEFAULT_POOL_PATH,
    golden_dataset_path: Path = DEFAULT_GOLDEN_DATASET_PATH,
) -> CqCandidate:
    """Stage 5: promote one human-approved candidate.

    Requires `review_decision == 'approve'` on the row already (set by the
    weekly review ritual, `feedback.review.upsert_candidate`); this
    function never sets `review_decision` itself, only `status`,
    `promoted_at`, `few_shot_example`, and `eval_case`.

    Refuses with `PrivacyViolationError` when any string field of either
    `few_shot_example` or `eval_case`, not just `query_pattern`, is a
    verbatim copy of any of the candidate's source interactions'
    `query_text`. This is the privacy step from Section 16, enforced here
    rather than trusted to the reviewer having done it by hand.

    Refuses with `SourceInteractionsUnavailableError`, a `PrivacyViolationError`
    subclass, when `candidate.source_interaction_ids` names one or more rows
    and fewer of them resolve to a live `interactions` row than were named.
    The check cannot verify a payload is safe against source text it cannot
    read, so it refuses rather than passing by default (F-4.6-A-05). A
    candidate whose `source_interaction_ids` is empty by construction, the
    hand-authored shape Section 17's seed few-shot pool uses, carries no
    source sentence to protect and is not covered by this refusal.

    Idempotent: a second call with the same candidate and the same payloads
    appends nothing further to either file (both append helpers dedupe on
    `cq_candidate_id`) and leaves the row's `promoted_at` at its first value.
    """
    candidate = session.get(CqCandidate, candidate_id)
    if candidate is None:
        raise ValueError(f"no cq_candidates row with id {candidate_id}")
    if candidate.review_decision != "approve":
        raise ValueError(
            f"cq_candidates {candidate_id} has review_decision="
            f"{candidate.review_decision!r}, not 'approve'; promotion only "
            "runs on a human-approved row (Section 16 stage 5)"
        )

    if candidate.source_interaction_ids:
        distinct_source_ids = set(candidate.source_interaction_ids)
        source_texts = _source_query_texts(session, candidate)
        if len(source_texts) < len(distinct_source_ids):
            raise SourceInteractionsUnavailableError(
                f"cq_candidates {candidate_id} names "
                f"{len(distinct_source_ids)} source_interaction_ids but "
                f"only {len(source_texts)} resolved to a live interactions "
                "row; the privacy check cannot verify the promoted payload "
                "against source text it cannot read, so promotion refuses "
                "rather than proceeding on an unverifiable input (Section "
                "16 stage 5 privacy step; F-4.6-A-05)"
            )
    else:
        source_texts = []

    verbatim_leaf = _find_verbatim_leaf(few_shot_example.model_dump(), source_texts)
    if verbatim_leaf is None:
        verbatim_leaf = _find_verbatim_leaf(eval_case.model_dump(), source_texts)
    if verbatim_leaf is not None:
        raise PrivacyViolationError(
            f"a field of the promoted payload ({verbatim_leaf!r}) is a "
            "verbatim copy of a source interaction's query_text; "
            "generalize the wording (for example '{gene}' rather than the "
            "literal phrasing one user typed) before promoting. This check "
            "covers every string field of both few_shot_example and "
            "eval_case, not only few_shot_example.query_pattern (Section "
            "16 stage 5 privacy step; F-4.6-A-04)"
        )

    fs_entry = few_shot_example.model_dump()
    fs_entry["cq_candidate_id"] = str(candidate_id)
    ec_entry = eval_case.model_dump()
    ec_entry["cq_candidate_id"] = str(candidate_id)

    _append_pool_entry(pool_path, fs_entry)
    _append_golden_entry(golden_dataset_path, ec_entry)

    now = datetime.now(UTC)
    candidate.status = "promoted"
    candidate.promoted_at = candidate.promoted_at or now
    candidate.few_shot_example = fs_entry
    candidate.eval_case = ec_entry
    candidate.updated_at = now
    session.flush()
    return candidate


# ---------------------------------------------------------------------------
# CLI: `python -m system_03_search_agent.feedback.promotion promote ...`
# ---------------------------------------------------------------------------


def _cmd_promote(args: argparse.Namespace) -> None:
    with args.payload_file.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    few_shot_example = FewShotExample.model_validate(payload["few_shot_example"])
    eval_case = EvalCase.model_validate(payload["eval_case"])
    with session_scope() as session:
        candidate = promote_candidate(
            session,
            candidate_id=uuid.UUID(args.candidate_id),
            few_shot_example=few_shot_example,
            eval_case=eval_case,
        )
        print(f"cq_candidates row {candidate.id} promoted_at={candidate.promoted_at}")


def build_arg_parser() -> argparse.ArgumentParser:
    """The promotion path's CLI. See `docs/build/Feedback_review_ritual.md`."""
    parser = argparse.ArgumentParser(
        prog="feedback-promotion",
        description="Stage 5 few-shot promotion (Section 16, Section 17).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_promote = sub.add_parser(
        "promote", help="Promote one review_decision='approve' cq_candidates row."
    )
    p_promote.add_argument("--candidate-id", required=True)
    p_promote.add_argument(
        "--payload-file",
        required=True,
        type=Path,
        help="A JSON file shaped {'few_shot_example': {...}, 'eval_case': {...}}, "
        "generalized wording already applied by the reviewer.",
    )
    p_promote.set_defaults(func=_cmd_promote)

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
