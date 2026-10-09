# Card 19 diagnosis: the paced handoff may show a false writing step

Diagnosis only, 2026-10-08 overnight, read against `develop` at `c916cfa3`. Paths are relative to `<repo-root>`. No code was changed and no model was called.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The cause](#the-cause)
- [Every path checked](#every-path-checked)
- [The smallest fix](#the-smallest-fix)
- [Overlap with phase 8.7 and the guardrail](#overlap-with-phase-87-and-the-guardrail)
- [Needs the owner](#needs-the-owner)
- [Proposed test query](#proposed-test-query)

## Status today

Cannot tell for certain without a live run, but reading every path finds no false writing step the backend can cause today. The open question from 11.28 (2026-09-20) is answered by code: every tool start is written before any tool runs, and Act runs once per question. One related gap is real, in the other direction: on one rare path the steps stay on Act through the whole writing wait.

`frontend/src/hooks/useRunView.writeState.test.tsx` passes 7 of 7 on develop (vitest, one file).

## What a person sees

The risk named in 11.28: during the wait, the steps jump to "writing the answer" for under a second, then back to the helpers' searches. Pacing stretched any such jump from under a millisecond to about 700 ms. Nobody has seen it on a real question; it was found only in a test fixture that described a stream the backend cannot send.

The gap that is real: when a question plans more than 20 live lookups, the ones over the limit never start. The steps then show the helpers still searching for the whole writing wait, 2 to 22 seconds, and switch to writing only when the first sentence lands.

## The cause

The steps are inferred in the browser, not read from the backend.

| Where | What it does |
|---|---|
| `frontend/src/hooks/useRunView.ts:441` to `470` | Write starts when every opened tool call has a result (`actComplete`), when the plan chose no tool (`planSelectedNoTool`), or when a sentence arrives. |
| `useRunView.ts:458` to `461` | Once any planned call id has appeared on the wire, every planned id must close before Write. |
| `src/system_03_search_agent/core/graph.py:8591` to `8607`, `act_node` | All `tool_start` frames, the follow-ups included, are written before any call runs. |
| `core/graph.py:14141` to `14144` | The graph runs Act once and then Write; nothing loops back to Act. |
| `core/graph.py:8579` to `8585` | A Layer 2 or 3 call over `MAX_LAYER_2_3_CALLS_PER_QUERY` (20, `harness/call_budget.py:101`) is skipped with `continue`, so it never gets a start frame. The cost cap's `break` (line 8570) does the same. |
| `core/graph.py:12864` | The backend already sends an honest signal, `step` with `step="write", status="started"`, the moment writing begins. |
| `frontend/src/hooks/useAgentRun.ts:138` | The web app drops `step` by name (`FORWARD_COMPATIBLE_EVENT_NAMES`), so that signal is never used. |

The real gap follows from rows 4 and 2: a skipped call's id is in the plan's `tool_calls`, appears on no frame, and so never closes. `actComplete` stays false until the first sentence arrives.

## Every path checked

| Path | Events in order | What the steps show | False Write? |
|---|---|---|---|
| Normal question, one round | plan, all starts, results | Act, then Write once the last result lands | No |
| Question with follow-up lookups (11.21 two stages) | plan, all starts for both stages, stage one results, stage two results | Act until stage two closes | No: stage two ids are already open |
| Plan chose no tool: ask-back, unresolved name, no data (`plan_node`, lines 6617, 6862, 6875) | plan with `tool_calls=[]`, then Write's own events | Plan, then Write | No: Write does run, to write the reply or the question back |
| Guardrail refusal | guard, then done | No live step | No |
| A call skipped by the 20-call limit or the cost cap | plan lists it, no start, others close | Act until the first sentence | No, but Act is false for the whole writing wait |
| A fatal error mid-run | error with `fatal: true` | No live step (line 493) | No |
| A new question in the same tab | events reset per run (`useAgentRun.ts:236`, `App.tsx:1081`) | Starts clean | No |

`usePacedEvents.ts` only releases a prefix of the events in arrival order (its header, line 38), so pacing cannot reorder a start behind a result.

## The smallest fix

Two options. The first closes the real gap; the second removes the inference for good.

| Field | Option 1: skipped calls do not hold Write | Option 2: read the backend's own write signal |
|---|---|---|
| Files and functions | `frontend/src/hooks/useRunView.ts`, the `actComplete` block (lines 441 to 470): Act is complete when every call that started has a result, without also waiting on planned ids that never started. Safe because `act_node` writes every start before any result; a test in `useRunView.writeState.test.tsx` | `useAgentRun.ts` (stop dropping `step`), `frontend/src/lib/events.ts` (accept `step`), `useRunView.ts` (Write starts on `step` write started or on a sentence) |
| Answer path | No, the wait screen only | No, the wait screen only |
| Dial position | 2, runnable behaviour | 3, the web app starts reading an event it skips today |
| Size | S | M |
| Migration, package, event schema | None | The backend schema is unchanged; the web app's event reader changes |

Option 1 alone also needs the backend to say why a call never started. That is out of this fence and not needed for the steps.

## Overlap with phase 8.7 and the guardrail

| Fence | Phase 8.7 | Guardrail |
|---|---|---|
| `frontend/src/hooks/useRunView.ts` | Yes: on tonight's rewrite list | Yes: `FATAL_COPY` lives in the same file |
| `useAgentRun.ts`, `lib/events.ts` (option 2) | No | No |
| `usePacedEvents.ts` | Not touched by either option | None |

Both options touch `useRunView.ts`, so build after 8.7 and the guardrail work merge.

## Needs the owner

No for option 1. Option 2 changes which events the web app reads, which is dial 3; ask the owner only if option 2 is chosen.

## Proposed test query

Existing query 18 ("The wait stays readable", 11.28) covers the normal paths. Proposed line to add under its "What you should see":

```markdown
- Once "writing the answer" shows, the steps never go back to the helpers' searches, and the helpers' line never stays up for more than a second after the last helper reports.
```
