# Builder D, build phase 8.2 wave 1: the classifier seam

Scope: `harness/decide.py`, `harness/jev_client.py`, `harness/task_tiers.py`, `tools/catalogue.py`, plus the additive `DonePayload.decisions` field, the `resolve_jev_model` addition to `harness/tiers.py`, tests, and this report. Nothing wired into the agent loop yet, per the brief.

## Table of contents

- [The Jev decisions endpoint, pinned live](#the-jev-decisions-endpoint-pinned-live)
- [decide(): the seam itself](#decide-the-seam-itself)
- [The tool catalogue](#the-tool-catalogue)
- [task_tiers.py](#task_tierspy)
- [DonePayload.decisions and the frontend](#donepayloaddecisions-and-the-frontend)
- [Live probe result](#live-probe-result)
- [Tests and gates](#tests-and-gates)
- [Files touched](#files-touched)

## The Jev decisions endpoint, pinned live

The public OpenRouter page names the endpoint but not its request or response shape. Four live requests against `POST https://openrouter.ai/api/alpha/decisions`, using the main repository's `OPENROUTER_API_KEY` from `.env` (never printed or logged), pinned the exact shape by reading each 400 error's validation trail:

Request 1, guessing a shape mirroring chat completions with an `input` wrapper:

```json
{"model": "typesafe/jev-1.13", "input": {"state": "...", "options": [...]}}
```

Response: 400, naming `state` (a union: string, record, or array) and `questions` (a record) as required top-level fields, `input` ignored entirely.

Request 2, `state` and `questions` at top level, `questions.relevancy` as an array of option strings: 400, `questions.relevancy` must be an object, not an array.

Request 3, `questions.relevancy = {"options": [...]}`.  400, a discriminated union on a `type` field: `"noul" | "choice" | "score"`.

Request 4, `questions.relevancy = {"type": "choice", "options": [...]}`. 400, still missing `instructions` (same string/record/array union as top-level `state`) and `criteria` (a record).

Request 5, the full shape below: 200, first successful call.

Confirmed request shape (exactly one question per call; `decide()` never batches):

```json
{
  "model": "typesafe/jev-1.13",
  "state": "<bounded text>",
  "questions": {
    "<question_key>": {
      "type": "choice",
      "options": ["<opt1>", "<opt2>"],
      "instructions": "<one line>",
      "criteria": {"<opt1>": "<one line>", "<opt2>": "<one line>"}
    }
  }
}
```

Confirmed response shape on success:

```json
{
  "model": "typesafe/jev-1.13-20260917",
  "answers": {
    "<question_key>": {
      "type": "choice",
      "choice": "<one of the offered options>",
      "probabilities": {"<opt>": 0.0, "...": 1.0},
      "confidence": 0.0
    }
  },
  "usage": {"input_tokens": 352, "output_tokens": 40, "cost": 1.4784e-05},
  "id": "gen-dec-...",
  "provider": "TypeSafe"
}
```

`criteria` is required even though `decide()`'s own interface hands nothing per-option beyond the option strings themselves. `jev_client.py` synthesizes a generic one-liner per option (`"Choose '<opt>' when it is the best answer for this decision."`). A fifth probe confirmed generic criteria text is accepted and still returns a confident, sensible answer (`yes`/`no` on a relevance question, confidence 0.72 to 0.86 across the probes).

Total spend across all five probe requests: $0.0000728, well under a cent. Two probe scripts, `/private/tmp/.../scratchpad/probe_jev.py` and `probe_jev2.py`, ran the shape-discovery sequence; neither is committed (scratchpad only, per the instruction to write probe scripts to files rather than inline commands, since the secret-scan hook blocks credential-shaped words in Bash command text). The acceptance-criteria live probe, which exercises `decide()` itself, IS committed at `testing/Developer/reports/2026-09-25_phase_8.2/probe_decide_live.py`.

## decide(): the seam itself

`harness/decide.py`'s `decide(harness, trace_id, point, state, options)`:

- `state` is truncated to 4000 characters before either model sees it (ai-security-standards: only bounded state and the closed option set ever reach an external model).
- `CLASSIFIER_PROVIDER` unset or anything other than `"jev"` (the code default): only the guard tier is called. Jev is never dispatched. Verified by a unit test that asserts `call_jev` is never called.
- `CLASSIFIER_PROVIDER=jev`: the guard tier and Jev are dispatched concurrently via `asyncio.gather`, so the comparison adds no wall-clock time beyond whichever call would have run anyway. Jev's choice is used when it returns one of the offered options in time; otherwise the guard tier's choice is used and `fallback_reason` names why.
- Both calls check the per-query cost cap first, via `cost_control.check_per_query_cap(harness, trace_id, "guard")`, exactly the sequence `core/graph.py`'s `_dispatch_tier_call` uses. Jev has no `Tier` of its own to draw a token-profile estimate from (`estimate_call_cost_usd` is keyed strictly to `{"guard", "plan", "synth"}`), so it reuses the guard tier's conservative estimate; this is safe in the direction that matters, since Jev's measured live cost (~$0.000015 to $0.00002 per call) is far below the guard tier's own estimate.
- Jev's real `usage.cost` is charged onto the trace through `Harness.track_cost`, bucketed under the `"guard"` tier label (documented in code: `track_cost`'s own accumulator is not broken down per tier, and Jev has no tier slot of its own).
- Every one of Jev's four failure paths (timeout, HTTP error, malformed reply, an option outside the offered set) falls back to the guard tier's own pick, with `fallback_reason` set to the matching `JevCallError.reason`. A fifth path, the cost cap refusing the Jev call outright, falls back the same way with `fallback_reason="cost_cap"`.
- `DecisionRecord.agreed` is `true`/`false` only when both sides produced a usable pick; `null` otherwise (`guard`-only mode, or either side failed).

## The tool catalogue

`tools/catalogue.py` lists 17 actions across the seven tools:

- `cypher_query` and `clinicaltrials_search`: one action each (no `mode`/`action` discriminator in their locked schemas).
- `ncbi_dbsnp`: one action (`query_type` is an enum on one flat input model, not a set of discriminated sub-models, so it stays one catalogued action).
- `ncbi_efetch`: seven actions (search, fetch, summary, link, coordinate_overlap, dataset_report, pubchem_property).
- `litvar2_lookup`: two actions (variant_search, publications_lookup).
- `pathogen_detection`: three actions (isolate_lookup, cluster_snp_neighbors, isolate_search).
- `pubtator_annotate`: two actions (entity_lookup, annotate_publications).

Each action's `input_schema` is that action's existing Pydantic input model's own `model_json_schema()` output, unmodified. Timeout and rate-limit-pool text are copied literally from `.claude/rules/tool-call-budgets.md`'s table.

`resource_options()` returns the seven TOOL names (not the 17 finer-grained action names) for the `"plan.resource"` decision point, sorted and fixed. This was a deliberate choice against the grain of "every action": `DecisionRecord.options` caps at `max_length=12`, seventeen action names would violate that bound outright, and "which resource to pull" reads more naturally as "which of the seven tools" than "which of seventeen sub-actions" to a decision point that has to hand Jev a short, comparable option list anyway.

## task_tiers.py

`ALL_TASK_TIERS` restates `docs/architecture/Model_architecture.md`'s eight existing call sites plus the five planned classifier decision points as one sorted, fixed tuple of thirteen rows, with a `task_tier_for(call_site)` lookup. Pure data; nothing calls it yet.

## DonePayload.decisions and the frontend

`contracts/events.py` gains `DecisionRecord` (its own model, `extra="forbid"`, every string capped, `options` capped at 12) and `DonePayload.decisions: list[DecisionRecord] | None = None`, capped at 16. Both additive and optional per `system-design-patterns` pattern 10.

`frontend/src/lib/events.ts` was NOT touched. Its `isDonePayload` type guard checks only the fields it cares about (`total_cost_usd`, `total_tool_calls`, `elapsed_ms`, `trust_outcome`, `trust_line`) and does not reject an object carrying additional, unrecognized keys. An unknown `decisions` field on the wire passes through untouched rather than being rejected, so the frontend would not reject this new optional field, and the brief's own condition for touching that file ("only if the frontend would reject it") does not apply.

## Live probe result

`testing/Developer/reports/2026-09-25_phase_8.2/probe_decide_live.py` ran three real decisions through `decide()` with `CLASSIFIER_PROVIDER=jev`:

- `guardrail.relevancy`: Jev chose `relevant` (confidence 1.0, 270ms), guard chose `relevant`, agreed.
- `think.ask_back`: Jev chose `ask` (confidence 1.0, 401ms), guard chose `ask`, agreed.
- `plan.resource`: Jev chose `ncbi_efetch` (confidence 0.35, 218ms), guard chose `pubtator_annotate`, disagreed. Confidence 0.35 on a 7-way choice reads as Jev genuinely uncertain here, not a defect; the comparison table this seam exists to build is precisely for surfacing disagreements like this one before any wiring decision gets made.

Total metered cost for that trace: $0.000064.

## Tests and gates

`python3 -m pytest tests/system_03_search_agent/harness tests/system_03_search_agent/tools/test_catalogue.py tests/system_03_search_agent/test_debugging_guide_coverage.py -q` -> 245 passed.

`ruff check` and `isort --check-only` pass on every file touched.

The `Debugging_guide.md` manifest was regenerated (`python tests/system_03_search_agent/test_debugging_guide_coverage.py`); the diff adds exactly the four new files' docstring-summary hashes, nothing else.

## Files touched

New:

- `src/system_03_search_agent/harness/decide.py`
- `src/system_03_search_agent/harness/jev_client.py`
- `src/system_03_search_agent/harness/task_tiers.py`
- `src/system_03_search_agent/tools/catalogue.py`
- `tests/system_03_search_agent/harness/test_decide.py`
- `tests/system_03_search_agent/harness/test_jev_client.py`
- `tests/system_03_search_agent/harness/test_task_tiers.py`
- `tests/system_03_search_agent/tools/test_catalogue.py`
- `testing/Developer/reports/2026-09-25_phase_8.2/probe_decide_live.py`
- `testing/Developer/reports/2026-09-25_phase_8.2/builder_D.md` (this file)

Edited:

- `src/system_03_search_agent/harness/tiers.py` (Jev's default model id added to `_DEFAULT_MODELS`, plus `resolve_jev_model()`)
- `src/system_03_search_agent/contracts/events.py` (`DecisionRecord`, `DonePayload.decisions`)
- `docs/build/Debugging_guide.md` (one row per new `src/` file)
- `tests/system_03_search_agent/fixtures/debugging_guide_manifest.json` (regenerated)

Not touched, per the file fence: `core/graph.py`, `core/clarify.py`, `core/breadth_plan.py`, `guardrail/`, `synthesis/`, and every tool other than `catalogue.py`. Nothing in the agent loop calls `decide()` yet; wiring is a later wave.
