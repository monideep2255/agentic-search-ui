"""`RunRecord`: one agent run, assembled from its trace events (T-5.1-06).

Depends on:
    - Nothing at import time. Deliberately: this module is imported by the
      grader, and the grader must not be able to reach the agent loop.

Reads:
    - A LangSmith run payload, or an equivalent locally-captured dict.

Writes:
    - Nothing.

Section 23: "Grade against traces, not blind re-runs: build graders against
LangSmith trace output (Section 20), per the eval-harness skill's guidance,
so a grading pass does not need to re-execute the full agent loop from
scratch."

## The correction this module carries, and why it is worth reading

The first version of this file parsed a payload shaped like
`outputs.answer`, `outputs.citations`, `metadata.cost_usd`. That shape was
INVENTED. It was never checked against a real trace, it had no caller and no
test, and when it was finally run against live LangSmith on 2026-08-30 it
raised on the first record. Filed as F-5.1-05.

Two things were wrong, and the second is the structural one:

- Field names. Real `inputs` carries `query`, not `question`, and real
  `outputs` carries only `events` and `seq`.
- ONE TRACE IS NOT ONE RUN. A trace is a TREE of per-node runs (`think`,
  `plan`, `act`, `write`, the routers) that all share a `trace_id`. No single
  run holds the answer. The first version assumed one run equals one query,
  which is the kind of premise that a field-name fix would have left intact
  and still broken.

What it parses now is the system's OWN v1 typed event contract, the same
events the SSE stream carries: `guard`, `think`, `plan`, `tool_start`,
`tool_result`, `token`, `citation`, `trust_signal`, `cost`, `done`. That is
not a lucky alternative, it is the right source: the contract is versioned,
additive-only within v1, and already the thing every other surface reads.

The general lesson is `.claude/rules/attack-the-constraint.md`'s, arrived at
the expensive way: when a component is fed by an assembly step, print what
the component ACTUALLY receives before writing the code that consumes it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

# The join key across LangSmith, the `interactions` table and the audit log
# is `trace_id` (Section 20.1). It is the only field that is never optional,
# because a record that cannot be joined cannot be audited.
_REQUIRED = ("trace_id", "query_id", "question", "outcome")


@dataclass(frozen=True)
class RunRecord:
    """One graded run, flattened from a trace.

    Every field is what the grader reads. Nothing here is a handle to
    anything executable, which is the property P6 of the premise gate
    asserts with a tripwire rather than by reading this docstring.
    """

    trace_id: str
    query_id: str
    question: str
    outcome: str
    answer_text: str = ""
    resolved_curies: list[str] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    claims: list[dict[str, Any]] = field(default_factory=list)
    uncited_claims: list[str] = field(default_factory=list)
    cypher_emitted: list[str] = field(default_factory=list)
    assembly_context: str | None = None
    cost_usd: float = 0.0
    retrieval_hit_count: int = 0
    databases_reached: list[str] = field(default_factory=list)
    latency_ms: int = 0
    # Whether ANY tool result was cut short. It lives on `tool_result`,
    # never on a citation: `CitationPayload` is `extra="forbid"`, so a
    # citation carrying `truncated` would be rejected by the contract.
    # The forbidden-constraint check read it off citations and was
    # therefore dead on all 20 rows that mandate it (F-5.2-RR-03).
    truncated: bool = False

    def __post_init__(self) -> None:
        for name in _REQUIRED:
            if not getattr(self, name):
                raise ValueError(f"RunRecord requires a non-empty {name}")

    @property
    def citation_urls(self) -> list[str]:
        return [str(c.get("source_url", "")) for c in self.citations]

    @property
    def is_refusal(self) -> bool:
        """A refusal is the `refuse` outcome, never a guess from the prose.

        Read from the structured outcome rather than by matching the refusal
        string, because the string is answer text and answer text is
        model-generated. Matching on prose would make this property a
        classifier, and a classifier here would be one more thing that can
        be wrong.
        """
        return self.outcome == "refuse"

    @property
    def is_non_answer(self) -> bool:
        """A run that declined to answer, whether by refusing or by asking.

        Both are non-answering outcomes and both belong in the abstain
        branch. Treating only `refuse` that way INVERTED the dataset on the
        one row expecting a clarifying question: asking, the behaviour the
        row requires, fell through to the score path, could not reach the
        threshold, and failed with empty notes, while refusing passed
        (F-5.2-RR-02).
        """
        return self.outcome in ("refuse", "ask")


def iter_events(runs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every typed event in a set of runs, de-duplicated on `seq`.

    A LangGraph node's events appear on both the node that produced them and
    the state passed to the next node, so the same event is seen more than
    once across a trace. `seq` is the contract's own ordering key and is
    unique per run, so it is what de-duplication keys on, exactly as
    `run_streaming` already does.
    """
    by_seq: dict[Any, dict[str, Any]] = {}
    for run in runs:
        for bucket in ("inputs", "outputs"):
            events = (run.get(bucket) or {}).get("events") or []
            for event in events:
                if not isinstance(event, dict) or not event.get("type"):
                    continue
                key = event.get("seq", id(event))
                by_seq.setdefault(key, event)
    return [by_seq[k] for k in sorted(by_seq, key=lambda s: (s is None, s))]


def _payloads(events: Sequence[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [
        e.get("payload") or {}
        for e in events
        if e.get("type") == kind and isinstance(e.get("payload"), dict)
    ]


def _question_from_runs(runs: Iterable[dict[str, Any]]) -> str:
    for run in runs:
        query = (run.get("inputs") or {}).get("query")
        if isinstance(query, dict) and query.get("text"):
            return str(query["text"])
    return ""


# Genome assembly and patch identifiers, as a person would write them in an
# answer. Deliberately a closed list rather than a loose pattern: this decides
# a HARD-FAIL, and a permissive match would let any version-looking string
# satisfy a safety control.
_ASSEMBLY_PATTERN = re.compile(
    r"\b(GRCh3[78](?:\.p\d+)?|hg19|hg38|T2T-CHM13(?:v\d+(?:\.\d+)?)?|NCBI3[0-9])\b",
    re.IGNORECASE,
)


def _assembly_context(answer_text: str) -> str | None:
    """The genome assembly the ANSWER states, or None.

    Read from the answer's own words, which is the only honest source.

    The first version read a citation's `snapshot_date`, which is when a
    graph row was ingested and has nothing to do with a genome assembly.
    Parsing the committed real fixture returned `assembly_context =
    '2026-04-22'` for a non-coordinate BRCA1 question, so the hard-fail was
    satisfied by a date. Filed as F-5.1-J-12.

    The hard-fail this feeds asks whether a coordinate answer told the reader
    which assembly its coordinates are on. Only the answer text can say that.
    """
    match = _ASSEMBLY_PATTERN.search(answer_text or "")
    return match.group(1) if match else None


def _trace_id(runs: Sequence[dict[str, Any]], events: Sequence[dict[str, Any]]) -> str:
    for run in runs:
        if run.get("trace_id"):
            return str(run["trace_id"])
    for event in events:
        if event.get("trace_id"):
            return str(event["trace_id"])
    return ""


def record_from_runs(
    runs: Sequence[dict[str, Any]],
    *,
    query_id: str,
    question: str | None = None,
) -> RunRecord:
    """Assemble one `RunRecord` from every run sharing a trace.

    `query_id` is supplied by the caller rather than read from the trace,
    and that is deliberate. Nothing in the live agent knows it is being
    evaluated, so no golden-set identifier appears anywhere in a real trace.
    Inventing a field for it would mean changing the product to suit its own
    measuring device.
    """
    events = iter_events(runs)

    tokens = "".join(str(p.get("text") or "") for p in _payloads(events, "token"))
    citations = _payloads(events, "citation")
    trust = _payloads(events, "trust_signal")
    done = _payloads(events, "done")
    think = _payloads(events, "think")
    tool_results = _payloads(events, "tool_result")

    # The outcome is taken from `trust_signal` first and `done` second. Both
    # carry it, and the trust signal is the node that decides it, so it is
    # the more direct source; `done` is the fallback for a trace whose write
    # step never emitted (an error path).
    outcome = ""
    for payload in trust:
        if payload.get("outcome"):
            outcome = str(payload["outcome"])
    if not outcome:
        for payload in done:
            if payload.get("trust_outcome"):
                outcome = str(payload["trust_outcome"])

    resolved: list[str] = []
    for payload in think:
        for entity in payload.get("resolved_entities") or []:
            if isinstance(entity, dict) and entity.get("curie"):
                curie = str(entity["curie"])
                if curie not in resolved:
                    resolved.append(curie)

    # One claim per citation, which is what the contract actually provides:
    # a citation carries the `claim_text` it supports. An uncited claim
    # therefore cannot appear here by construction, and that is a real limit
    # rather than a happy result. It is stated in the premise gate's coverage
    # section rather than left for a reader to infer from a always-empty list.
    claims = [
        {
            "text": str(c.get("claim_text") or ""),
            "citation_ids": [c["citation_id"]] if c.get("citation_id") else [],
        }
        for c in citations
        if c.get("claim_text")
    ]

    cost = 0.0
    latency = 0
    for payload in done:
        cost = float(payload.get("total_cost_usd") or cost)
        latency = int(payload.get("elapsed_ms") or latency)

    hits = sum(int(p.get("result_count") or 0) for p in tool_results)
    databases = sorted(
        {str(p["tool"]) for p in tool_results if p.get("tool")}
    )

    return RunRecord(
        trace_id=_trace_id(runs, events),
        query_id=query_id,
        question=question or _question_from_runs(runs) or "(question not in trace)",
        outcome=outcome or "unknown",
        answer_text=tokens,
        resolved_curies=resolved,
        citations=citations,
        claims=claims,
        uncited_claims=[],
        # `ToolResultPayload` carries no Cypher field, so this is empty on
        # every real trace. It is kept rather than deleted because the
        # coverage metric's honest answer is "not measurable from a trace"
        # rather than "0 percent", and `coverage.py` now distinguishes those.
        # Filed as F-5.1-J-13: reporting 0 percent for a quantity nothing can
        # observe is a measurement that was never taken.
        cypher_emitted=[
            str(p["cypher"])
            for p in _payloads(events, "tool_result")
            if p.get("cypher")
        ],
        assembly_context=_assembly_context(tokens),
        cost_usd=cost,
        retrieval_hit_count=hits,
        databases_reached=databases,
        latency_ms=latency,
        truncated=any(bool(p.get("truncated")) for p in tool_results),
    )


def records_from_payload(
    payload: dict[str, Any], *, query_ids: dict[str, str]
) -> list[RunRecord]:
    """Group a LangSmith `/runs/query` response by trace and build one record each.

    `query_ids` maps `trace_id` to the golden query it was run for. A trace
    with no mapping is skipped rather than guessed at: grading a run against
    the wrong golden row would produce a confident wrong score, which is the
    failure this whole harness exists to prevent.
    """
    runs = payload.get("runs") if isinstance(payload, dict) else payload
    grouped: dict[str, list[dict[str, Any]]] = {}
    for run in runs or []:
        trace_id = run.get("trace_id")
        if trace_id:
            grouped.setdefault(str(trace_id), []).append(run)

    records = []
    for trace_id, trace_runs in grouped.items():
        query_id = query_ids.get(trace_id)
        if not query_id:
            continue
        records.append(record_from_runs(trace_runs, query_id=query_id))
    return records
